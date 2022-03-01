# -*- coding: utf-8 -*-
# Copyright (c) 2021, AvN Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils.dateutils import get_dates_from_timegrain, parse_date
from datetime import date, timedelta
from frappe.utils.data import formatdate, getdate, get_datetime, get_time
from dateutil import parser
import numpy as np
import pymysql
import pymysql.cursors

class MonthlyTimesheet(Document):
	def autoname(self):
		# select a project name based on customer
		self.name = 'MTS:{0}-{1}-{2}'.format(self.employee,self.start_date,self.end_date)

	def after_insert(self):
		self.add_time_sheet_detail()
		self.get_emplyee_detail()
		self.save()

	def before_validate(self):
		if (self.monthly_time_sheet_detail and len(self.monthly_time_sheet_detail) > 0):
			self.calculate_total_hours()

	def validate(self):
		if self.status == 'Approved':
			self.validate_approved_rows()

	def on_submit(self):
		if self.status == "Open":
			frappe.throw(_("Only Timesheets with status 'Approved' can be submitted"))



	def validate_approved_rows(self):
		for row in self.monthly_time_sheet_detail:
			self.is_apporved(row)
			self.overtime_must_have_reason(row)
			self.not_missed_clocking(row)



	def is_apporved(self, row):
		if (row.is_approved == 0):
			frappe.throw(
				_("All Detail Lines must be approved before the Timesheet can be marked as Approved. {0} is Not Approved Yet.").format(row.date)
				)
	
	def overtime_must_have_reason(self, row):
		if (row.overtime_hours > 0 or row.double_overtime_hours > 0) and (row.notes == None or row.notes.strip() == ""):
			frappe.throw(
				_("Overtime must have a reason. Overtime on {0} does not have a reason").format(row.date)
				)
	def not_missed_clocking(self, row):
		if (row.checkin == row.checkout and row.checkin != '0:00:00'):
			frappe.throw(
				_("Missed Clocking Found on {0}").format(row.date)
				)

	def calculate_total_hours(self):
		total_nh = 0
		total_lunch = 0
		total_oh = 0
		total_doh = 0
		for detail in self.monthly_time_sheet_detail:
			total_nh = total_nh + (detail.normal_hours if not detail.normal_hours == None else 0)
			total_oh = total_oh + (detail.overtime_hours if not detail.overtime_hours == None else 0)
			total_lunch = total_lunch + (self.time_duration_to_hours(detail.lunch) if (not detail.lunch == None) and (detail.lunch != '0:00:00') else 0)
			total_doh = total_doh + (detail.double_overtime_hours if not detail.double_overtime_hours == None else 0)
		
		self.total_normal_hours = total_nh
		self.total_overtime_hours = total_oh
		self.total_dot_hours = total_doh
		self.total_lunch_hours = total_lunch

	def time_duration_to_hours(self,time):
		t = parser.parse(time)
		return round(t.hour + (t.minute / 60),2)

	def add_time_sheet_detail(self):
		test = get_dates_from_timegrain(self.start_date, self.end_date, "Daily")
		for dt in test:
			row = self.append('monthly_time_sheet_detail', {
				"date": dt, 
				"checkin": "00:00", 
				"checkout": "00:00", 
				"lunch": "00:00"
				})
		
	def get_emplyee_detail(self):
		self.check_sal_struct()


	def check_sal_struct(self):
		cond = """and sa.employee=%(employee)s and (sa.from_date <= %(start_date)s or
				sa.from_date <= %(end_date)s)"""

		sqldata = frappe.db.sql("""
			select sa.hourly_rate, sa.required_hours
			from `tabSalary Structure Assignment` sa
			where sa.docstatus = 1 %s
			order by sa.from_date desc
			limit 1
		""" %cond, {'employee': self.employee, 'start_date': self.start_date,
			'end_date': self.end_date},1)
		if sqldata:
			self.required_hours = sqldata[0].required_hours
			return self.required_hours

		else:
			self.required_hours = None 
			frappe.msgprint(_("No active or default Salary Structure Assignment found for employee {0} for the given dates")
				.format(self.employee), title=_('Salary Structure Assignment'))
	
	@frappe.whitelist()
	def get_employee_clockings(self):
		# Get Leave Details
		self.get_leaves_for_period()

		hr_settings = frappe.get_single('HR Settings')
		strPassword = hr_settings.get_password('zk_password')
		#print('password=',strPassword)
		db = pymysql.connect(host=hr_settings.zk_host,user=hr_settings.zk_user,password=strPassword,database=hr_settings.zk_database, cursorclass=pymysql.cursors.DictCursor)
		cursor = db.cursor()

		sql = "select pin, \
				checktime\
				from checkinout\
				where pin = %s and checktime>='%s' and checktime<='%s'\
				order by checktime" \
				% (self.employee, formatdate(self.start_date, 'yyyy-mm-dd'),formatdate(self.end_date, 'yyyy-mm-dd'))
		#print(sql)
		results = None
		try:
			cursor.execute(sql)
			# Fetch all the rows in a list of lists.
			results = cursor.fetchall()
		except:
   			frappe.msgprint(_("Unable to fetch data. Server ran into a problem.")
				.format(self.employee), title=_('Zk Server Problem'))
		# disconnect from server
		db.close()
		if (results != None):
			self.fill_employee_clocking_results(results)
		
		self.save()
	
	def fill_employee_clocking_results(self, rows):
		previous_date = None
		min_time = None
		max_time = None
		for row in rows:
			clocking_value = row['checktime']
			parsed_date = clocking_value.date()
			if (parsed_date != previous_date):
				if (previous_date != None):
					self.update_timesheet_clocking_row(parsed_date, min_time, max_time)
				previous_date = parsed_date
				min_time = clocking_value
				max_time = clocking_value
			else:
				if clocking_value < min_time:
					min_time = clocking_value
				if clocking_value > max_time:
					max_time = clocking_value
	
	def update_timesheet_clocking_row(self, _date, min, max):
		for detail in self.monthly_time_sheet_detail:
			parsed_date = getdate(detail.date)
			if parsed_date == _date :
				if (detail.is_approved == 0):
					detail.checkin = min.strftime('%H:%M:%S')
					detail.checkout = max.strftime('%H:%M:%S')
					detail.normal_hours = round(float((max - min).total_seconds()) / 3600, 6)
				break

	def get_leaves_for_period(self):
		leaves = frappe.db.get_all('Leave Application',filters={
					'employee': self.employee,
					'status': 'Approved',
				}
				,or_filters={
				'from_date': ['between', (self.start_date, self.end_date)],	
				'to_date': ['between', (self.start_date, self.end_date)],	
				},fields=['name', 'from_date', 'to_date', 'docstatus',],
				)
		if leaves and len(leaves) > 0:
			for detail in self.monthly_time_sheet_detail:
				parsed_date = getdate(detail.date)
				for leave in leaves:
					if leave['from_date'] <= parsed_date <= leave['to_date']:
						if detail.leave != leave.name:
							detail.leave = leave.name
						break
		
		


		

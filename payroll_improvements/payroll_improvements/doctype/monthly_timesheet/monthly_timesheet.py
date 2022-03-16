# -*- coding: utf-8 -*-
# Copyright (c) 2021, AvN Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils.dateutils import get_dates_from_timegrain
from datetime import timedelta
from frappe.utils.data import getdate
from dateutil import parser
import itertools
from erpnext.hr.doctype.employee_checkin.employee_checkin import (
	time_diff_in_hours,
)
from erpnext.hr.doctype.shift_assignment.shift_assignment import (
	get_employee_shift,
)
from erpnext.hr.doctype.employee.employee import get_holiday_list_for_employee
from erpnext.hr.doctype.holiday_list.holiday_list import is_holiday


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
		if (row.checkin == row.checkout and row.checkin != '0:00:00') or (row.checkin != '0:00:00' and row.checkout == '0:00:00'):
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
		#Get Leave Details
		self.get_leaves_for_period()
		#Get Holidays
		self.fill_shifts_and_holidays_for_period()
		#Get Checkins
		filters = {
			'time':('>=', self.start_date),
			'time': ('<', getdate(self.end_date) + timedelta(days=1)),
			'employee': self.employee
		}
		clockings = frappe.db.get_list('Employee Checkin', fields=["employee", "time"], filters=filters, order_by="time")

		if (clockings != None):
			#insert_employee_checkins(clockings)
			self.fill_employee_clocking_results(clockings)
			self.save()

	
	def fill_employee_clocking_results(self, rows):

		clocking_dates = []

		for key, group in itertools.groupby(rows, key=lambda x: (x['employee'], x['time'].date())):
			single_shift_logs = list(group)
			clocking_dates.append(key[1])
			total_working_hours, in_time, out_time, break_time = self.calculate_working_hours(single_shift_logs)
			self.update_timesheet_clocking_row(in_time.date(), total_working_hours, in_time, out_time,break_time, single_shift_logs)
		# After we added all of them, we can Check for missing days and mark attendance
		#print('Clocking Dates=',clocking_dates)
		# MARK MISSING DAYS ABSENT
		self.mark_missing_dates_absent(clocking_dates)
	
	def update_timesheet_clocking_row(self, _date, total_working_hours, in_time, out_time,break_time, punch_logs):
		punch_times = []
		for clocking in punch_logs:
			punch_times.append(clocking.time.strftime("%d-%m-%Y %H:%M:%S"))
 

		for detail in self.monthly_time_sheet_detail:
			parsed_date = getdate(detail.date)
			if parsed_date == _date :
				# Calculate Attendance
				if (detail.is_approved == 0):
					detail.checkin = in_time.strftime('%H:%M:%S')
					if out_time != None:
						detail.checkout = out_time.strftime('%H:%M:%S')
					else:
						detail.checkout = "00:00"
					detail.normal_hours = total_working_hours
					detail.lunch = str(timedelta(hours=break_time))
				detail.punch_times = ' , '.join(punch_times)
				detail.attendance = self.get_employee_attendance_value(detail, punch_logs)
				break
	
	def get_employee_attendance_value(self, detail, punch_logs):
		if detail.leave != None and detail.leave.strip() != "":
			return 'On Leave'
		if detail.is_holiday == 1:
			return 'Holiday'
		if len(punch_logs) != 0 and len(punch_logs) % 2 != 0:
			return "Missed Clocking"
		if detail.shift != None and detail.shift.strip() != "" \
		and detail.is_holiday == False \
		and (detail.leave == None or detail.leave.strip() == "")\
		and (detail.checkin == None or detail.checkin == "00:00" or detail.checkin == "00:00:00" or len(punch_logs) == 0):
			return 'Absent'

		return 'Present'


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
						detail.attendance = 'On Leave'
						if detail.leave != leave.name:
							detail.leave = leave.name
						break
	
	def fill_shifts_and_holidays_for_period(self):
		default_employee_holiday_list_name = get_holiday_list_for_employee(self.employee, False)
		for detail in self.monthly_time_sheet_detail:
			date_is_holiday = False
			parsed_date = getdate(detail.date)
			shift = get_employee_shift(self.employee, for_date=parsed_date, consider_default_shift=True)
			if default_employee_holiday_list_name != None:
				date_is_holiday = is_holiday(default_employee_holiday_list_name, parsed_date)
			if shift != None:
				detail.shift = shift.shift_type.name
				detail._shift = shift.shift_type
				if shift.shift_type.holiday_list != None and date_is_holiday == False:
					date_is_holiday = is_holiday(shift.shift_type.holiday_list, parsed_date)
			detail.is_holiday = date_is_holiday
			if detail.is_holiday == True:
				detail.attendance = 'Holiday'

	def mark_missing_dates_absent(self, clocking_dates):
		for detail in self.monthly_time_sheet_detail:
			parsed_date = getdate(detail.date)
			if not parsed_date in clocking_dates:
				if detail.shift != None and detail.shift.strip() != "" \
				and detail.is_holiday == False \
				and (detail.leave == None or detail.leave.strip() == ""):
					detail.attendance = 'Absent'

	def calculate_working_hours(self, logs):
		total_hours = 0
		in_time = out_time = None
		in_time = logs[0].time
		break_time = 0
		if len(logs) >= 2:
			out_time = logs[-1].time
		# If we find irregular Clockins then use First Check-in and Last Check-out
		if len(logs) >= 2 and len(logs) % 2 != 0:
			# assumption in this case: First log always taken as IN, Last log always taken as OUT
			total_hours = time_diff_in_hours(in_time, logs[-1].time)
		# If We find good Clockins then Every Valid Check-in and Check-out
		elif len(logs) >= 2 and len(logs) % 2 == 0:
			logs = logs[:]
			while len(logs) >= 2:
				total_hours += time_diff_in_hours(logs[0].time, logs[1].time)
				del logs[:2]
			break_time = time_diff_in_hours(in_time, out_time) - total_hours
		return total_hours, in_time, out_time, break_time
			

def find_index_in_dict(dict_list, key, value):
	return next((index for (index, d) in enumerate(dict_list) if d[key] == value), None)

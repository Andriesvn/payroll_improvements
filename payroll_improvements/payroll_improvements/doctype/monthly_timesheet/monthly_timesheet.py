# -*- coding: utf-8 -*-
# Copyright (c) 2021, AvN Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils.dateutils import get_dates_from_timegrain
from datetime import timedelta,datetime
from frappe.utils.data import getdate
from dateutil import parser
import itertools
import math
import json
from erpnext.hr.doctype.employee_checkin.employee_checkin import (
	time_diff_in_hours,
)
from erpnext.hr.doctype.shift_assignment.shift_assignment import (
	get_shift_details,
)
from erpnext.hr.doctype.employee.employee import get_holiday_list_for_employee
from erpnext.hr.doctype.holiday_list.holiday_list import is_holiday


class MonthlyTimesheet(Document):
	def autoname(self):
		self.name = 'MTS:{0}-{1}-{2}'.format(self.employee,self.start_date,self.end_date)

	def after_insert(self):
		self.add_time_sheet_detail()
		self.save()

	def before_validate(self):
		if (self.monthly_time_sheet_detail and len(self.monthly_time_sheet_detail) > 0):
			for detail in self.monthly_time_sheet_detail:
				self.calculate_detail_overtime(detail)
			self.calculate_total_hours()

	def validate(self):
			self.validate_all_rows()

	def on_submit(self):
		if self.status == "Open":
			frappe.throw(_("Only Timesheets with status 'Approved' can be submitted"))

	def validate_all_rows(self):
		for row in self.monthly_time_sheet_detail:
			if self.status == 'Approved':
				self.is_apporved(row)
			self.validate_row(row)

	def validate_row(self, detail):
		if detail.is_approved == 1:
			self.overtime_must_have_reason(detail)
			self.not_missed_clocking(detail)
			self.not_absent(detail)
			self.approved_hours_not_more_than_actual(detail)

	def is_apporved(self, row):
		if (row.is_approved == 0):
			frappe.throw(
				_("All Detail Lines must be approved before the Timesheet can be marked as Approved. {0} is Not Approved Yet.").format(row.date)
				)
	
	def overtime_must_have_reason(self, row):
		if row.approved_hours > row.shift_required_hours and (row.overtime_hours > 0 or row.double_overtime_hours > 0) and (row.notes == None or row.notes.strip() == ""):
			frappe.throw(
				_("Overtime must have a reason. Overtime on {0} does not have a reason").format(row.date)
				)
	def not_missed_clocking(self, row):
		if (row.checkin == row.checkout and row.checkin != '0:00:00') or (row.checkin != '0:00:00' and row.checkout == '0:00:00') \
			or row.attendance == "Missed Clocking":
			frappe.throw(
				_("Missed Clocking Not Allowed on {0}").format(row.date)
				)
	def not_absent(self, row):
		if row.attendance == "Absent":
			frappe.throw(
				_("Absent Values Not Allowed on {0}").format(row.date)
				)
	def approved_hours_not_more_than_actual(self, row):
		if row.approved_hours > row.actual_hours:
			frappe.throw(
				_("Approved Hours Cannot be more than Actual Hours on {0}").format(row.date)
				)

	def calculate_total_hours(self):
		total_ah = 0
		total_break = 0
		total_oh = 0
		total_doh = 0
		total_publich = 0
		for detail in self.monthly_time_sheet_detail:
			total_ah = total_ah + (detail.approved_hours if not detail.approved_hours == None else 0)
			total_oh = total_oh + (detail.overtime_hours if not detail.overtime_hours == None else 0)
			total_break = total_break + (self.time_duration_to_hours(detail.breaks) if (not detail.breaks == None) and (detail.breaks != '0:00:00') else 0)
			total_doh = total_doh + (detail.double_overtime_hours if not detail.double_overtime_hours == None else 0)
			total_publich = total_publich + (detail.public_hours if not detail.public_hours == None else 0)
		
		self.total_approved_hours = total_ah
		self.total_overtime_hours = total_oh
		self.total_dot_hours = total_doh
		self.total_break_hours = total_break
		self.total_public_hours = total_publich

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
				"breaks": "00:00"
				})
	
	@frappe.whitelist()
	def get_employee_clockings(self):
		#Get Leave Details
		self.get_leaves_for_period()
		#Get Holidays
		self.fill_shifts_and_holidays_for_period()
		#Get Checkins
		
		clockings = self.get_employee_checkin_for_range(self.start_date, self.end_date)

		if (clockings != None):
			#insert_employee_checkins(clockings)
			clocking_dates = self.fill_employee_clocking_results(clockings)
			# MARK MISSING DAYS ABSENT
			self.mark_missing_dates_absent(clocking_dates)
			self.save()
	
	def get_employee_clockings_for_specific_date(self,date):
		#Get Leave Details
		self.get_leaves_for_specific_date(date)
		#Get Holidays
		self.fill_shifts_and_holidays_for_specific_date(date)
		#Get Checkins
		
		clockings = self.get_employee_checkin_for_range(date, date)

		if (clockings != None):
			#insert_employee_checkins(clockings)
			self.fill_employee_clocking_results(clockings)
			self.save()


	def get_employee_checkin_for_range(self, start_date, end_date):
		filters = {
			'time':('>=', start_date),
			'time': ('<', getdate(end_date) + timedelta(days=1)),
			'employee': self.employee
		}
		clockings = frappe.db.get_list('Employee Checkin', fields=["*"], filters=filters, order_by="time")
		return clockings

	
	def fill_employee_clocking_results(self, rows):
		clocking_dates = []
		for key, group in itertools.groupby(rows, key=lambda x: (x['employee'], x['time'].date())):
			single_shift_logs = list(group)
			clocking_dates.append(key[1])
			self.find_and_update_timesheet_clocking_row(key[1], single_shift_logs)
		# MARK MISSING DAYS ABSENT
		return clocking_dates
	
	def find_and_update_timesheet_clocking_row(self, _date, punch_logs):
		for detail in self.monthly_time_sheet_detail:
			parsed_date = getdate(detail.date)
			if parsed_date == _date :
				self.update_timesheet_detail(detail, punch_logs)
				break
	
	def update_timesheet_detail(self, detail, punch_logs):
		punch_times = []
		for clocking in punch_logs:
			punch_times.append(clocking.time.strftime("%d-%m-%Y %H:%M:%S"))
		
		total_working_hours, in_time, out_time, break_time, unallowed_break, flag_manual = self.calculate_working_hours(punch_logs, detail)
		# Calculate Attendance
		detail.has_manual_checkin = flag_manual
		detail.checkin = in_time.strftime('%H:%M:%S')
		if out_time != None:
			detail.checkout = out_time.strftime('%H:%M:%S')
		else:
			detail.checkout = "00:00"
		detail.actual_hours = total_working_hours
		if break_time > 0:
			detail.breaks = str(timedelta(hours=break_time))
			detail.exceeded_break_time = hasattr(detail, '_shift') and detail._shift != None and detail._shift.breaks_allowed == 1 \
			and break_time > (detail._shift.allowed_break_time / 60)
			detail.unallowed_break = unallowed_break or (hasattr(detail, '_shift') and detail._shift != None and detail._shift.breaks_allowed != 1)
		else:
			detail.breaks = "00:00"
			detail.exceeded_break_time = False
			detail.unallowed_break = False
		#Calculate Approved Hours based on Shift Normal Time (end time - start time - allowed breaks)
		if total_working_hours > 0 and hasattr(detail, '_shift') and detail._shift != None and detail.is_approved == 0:
			is_on_leave = detail.leave != None and detail.leave.strip() != ""
			if (not is_on_leave):
				if detail.approved_hours == 0 or detail.approved_hours > total_working_hours:
					if total_working_hours < detail.shift_required_hours:
						detail.approved_hours = total_working_hours
					else:
						detail.approved_hours = detail.shift_required_hours
			else:
				detail.approved_hours = detail._shift.on_leave_hours
		else:
			if total_working_hours < 0 :
				detail.approved_hours = 0
		#Double Check that Approved hours is not more than Actual
		if detail.approved_hours > detail.actual_hours:
			detail.approved_hours = detail.actual_hours

		detail.punch_times = ' , '.join(punch_times)
		detail.attendance = self.get_employee_attendance_value(detail, punch_logs)

		return detail


	def calculate_working_hours(self, logs, detail):
		total_hours = 0
		in_time = out_time = None
		in_time = logs[0].time
		break_time = 0
		unallowed_break = False
		flag_manual = False
		#check for manual check-ins:
		for log in logs:
			if hasattr(log, 'is_manual') and log.is_manual == 1:
				flag_manual = True
		
		if len(logs) >= 2:
			out_time = logs[-1].time
		# If we find irregular Clockins then use First Check-in and Last Check-out
		if len(logs) >= 2 and len(logs) % 2 != 0:
			# assumption in this case: First log always taken as IN, Last log always taken as OUT
			total_hours = time_diff_in_hours(in_time, logs[-1].time)
		# If We find good Clockins then Every Valid Check-in and Check-out
		elif len(logs) >= 2 and len(logs) % 2 == 0:
			logs = logs[:]
			break_logs = logs.copy()
			while len(logs) >= 2:
				total_hours += time_diff_in_hours(logs[0].time, logs[1].time)
				del logs[:2]
			# Caclutate breaktime and validate
			break_time = 0
			del break_logs[0]
			del break_logs[-1]
			break_logs = break_logs[:]
			while len(break_logs) >= 2:
				break_time += time_diff_in_hours(break_logs[0].time, break_logs[1].time)
				#TODO: Check if Break time is Allowed and within allowed Limits
				if hasattr(detail, '_shift') and detail._shift != None and detail._shift.breaks_allowed \
				   and detail._shift.break_times != None and len(detail._shift.break_times) > 0:
					unallowed_break = not is_valid_breaktime(break_logs[0].time,break_logs[1].time,detail._shift.break_times,detail._shift.break_times_type)
				del break_logs[:2]

		if total_hours >= 0:
			#Round Hours down to Setting in HR Settings
			if self._hr_settings != None and self._hr_settings.round_timesheet_hours:
				total_hours = floor_to(total_hours,self._hr_settings.round_timesheet_hours_to)
		else :
			total_hours = 0
		if hasattr(detail, '_shift') and detail._shift != None and detail._shift.breaks_allowed and detail._shift.auto_deduct_break \
			and detail.override_auto_break != 1:
			#Check if we have a breaktime clocked or not to deduct from total hours
			if break_time < (detail._shift.allowed_break_time / 60):
				total_hours = total_hours - ((detail._shift.allowed_break_time / 60) - break_time)
				break_time = (detail._shift.allowed_break_time / 60)
				#else use the calculated one
		if hasattr(detail, '_shift') and detail._shift != None and detail._shift.flag_manual_checkins == 0:
			flag_manual = False
		
		return total_hours, in_time, out_time, break_time, unallowed_break, flag_manual
	
	def get_employee_attendance_value(self, detail, punch_logs):
		if detail.leave != None and detail.leave.strip() != "":
			return 'On Leave'
		if detail.is_holiday == 1 and detail.is_not_working == 1:
			return 'Public Holiday'
		if len(punch_logs) != 0 and len(punch_logs) % 2 != 0:
			return "Missed Clocking"
		if detail.shift != None and detail.shift.strip() != "" \
		and detail.is_not_working == False \
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

	def get_leaves_for_specific_date(self,date):
		leaves = frappe.db.get_all('Leave Application',filters={
					'employee': self.employee,
					'status': 'Approved',
				}
				,or_filters={
				'from_date': ['between', (date, date)],	
				'to_date': ['between', (date, date)],	
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
		public_holiday_list_name, default_employee_holiday_list_name = self.get_default_holiday_lists()

		for detail in self.monthly_time_sheet_detail:
			self.fill_shift_and_holiday_for_detail(detail, public_holiday_list_name, default_employee_holiday_list_name)
	
	def fill_shifts_and_holidays_for_specific_date(self, date):
		public_holiday_list_name, default_employee_holiday_list_name = self.get_default_holiday_lists()
		for detail in self.monthly_time_sheet_detail:
			if detail.date == date:
				self.fill_shift_and_holiday_for_detail(detail, public_holiday_list_name, default_employee_holiday_list_name)

	def get_default_holiday_lists(self):
		public_holiday_list_name = ""
		self._hr_settings = frappe.get_single('HR Settings')
		#Get Public Holiday Lists
		if self._hr_settings.use_public_hours == 1:
			public_holiday_list_name = self._hr_settings.public_holiday_list
		
		default_employee_holiday_list_name = get_holiday_list_for_employee(self.employee, False)
		return public_holiday_list_name,default_employee_holiday_list_name

	def fill_shift_and_holiday_for_detail(self, detail, public_holiday_list_name, default_employee_holiday_list_name):
		date_is_not_working = False
		parsed_date = getdate(detail.date)
		# Check if Public Holiday
		if self._hr_settings.use_public_hours == 1 and (public_holiday_list_name != None or public_holiday_list_name != "") :
			detail.is_holiday = is_holiday(public_holiday_list_name, parsed_date)
		else:
			detail.is_holiday = 0

		#Check if Employee NOT Working()
		shift = get_employee_shift(self.employee, for_date=parsed_date, consider_default_shift=(not detail.is_holiday))
		
		#if default_employee_holiday_list_name != None:
			#date_is_not_working = is_holiday(default_employee_holiday_list_name, parsed_date)
		if shift != None:
			detail.shift = shift.shift_type.name
			detail._shift = shift.shift_type
			detail.shift_required_hours = get_shift_required_hours(detail._shift)
			#Set Leave Hours
			if detail.attendance == 'On Leave':
				detail.actual_hours = detail._shift.on_leave_hours
				detail.approved_hours = detail._shift.on_leave_hours
				detail.breaks = '00:00'
		else:
			detail.shift = None
			detail.shift_required_hours = 0
			date_is_not_working = True

		detail.is_not_working = date_is_not_working
		if detail.is_not_working == True and detail.is_holiday != True:
			detail.attendance = 'Not Working'
		else:
			if detail.is_not_working == True and detail.is_holiday == True:
				detail.attendance = 'Public Holiday'
		return detail
			
	def mark_missing_dates_absent(self, clocking_dates):
		for detail in self.monthly_time_sheet_detail:
			parsed_date = getdate(detail.date)
			if not parsed_date in clocking_dates:
				if detail.shift != None and detail.shift.strip() != "" \
				and detail.is_not_working == False \
				and (detail.leave == None or detail.leave.strip() == ""):
					detail.attendance = 'Absent'
	
	def calculate_detail_overtime(self,detail):
		#If on leave, Cant have overtime
		if not (detail.leave == None or detail.leave.strip() == "") or \
		detail.approved_hours <= 0 or  detail.actual_hours <= 0:
			self.set_detail_overtime_hours(detail)
			return
		#Does detail have Shift?
		shift = None
		if hasattr(detail, '_shift') and detail._shift != None:
			shift = detail._shift
		else:
			#Get the shift for that day
			if (detail.shift != None and detail.shift.strip() != ""):
				shift = frappe.get_doc("Shift Type", detail.shift)
		if shift == None:
			#If no shift, Cant have overtime
			self.set_detail_overtime_hours(detail)
			return

		if detail.is_holiday and hasattr(self, '_hr_settings') and self._hr_settings.use_public_hours:
			#Calculate Public Hours For Public holidays (Not Sundays)
			#All Approved Hours count as public Hours on a Public Holiday
			self.set_detail_overtime_hours(detail,ph=detail.approved_hours)
			return
		else:
			overtime=0
			if (shift.shift_hours_type != 'Normal Hours'):
				overtime = detail.approved_hours
				if shift.shift_hours_type == "Overtime":
					self.set_detail_overtime_hours(detail,ot=overtime)
				if shift.shift_hours_type == "Double Overtime":
					self.set_detail_overtime_hours(detail,dot=overtime)
				if shift.shift_hours_type == "Public Hours":
					self.set_detail_overtime_hours(detail,ph=overtime)
				return
			else:
				if detail.approved_hours >= shift.required_hours_for_overtime:
					overtime = detail.approved_hours - get_shift_required_hours(shift)
				#Calculate Overtime Based on Shift Settings
				if shift.assign_overtime_to == "Overtime":
					self.set_detail_overtime_hours(detail,ot=overtime)
				#Calculate Double overtime ONLY SUNDAYS.
				if shift.assign_overtime_to == "Double Overtime":
					self.set_detail_overtime_hours(detail,dot=overtime)
				return

	def set_detail_overtime_hours(self,detail, ot=0,dot=0,ph=0):
		detail.overtime_hours = ot
		detail.double_overtime_hours = dot
		detail.public_hours = ph

	@frappe.whitelist()
	def add_manual_checkin(self,date,time,log_type,reason):
		# Add manual Check-in
		doc = frappe.new_doc("Employee Checkin")
		doc.employee = self.employee
		#doc.employee_name = employee.employee_name
		doc.is_manual = 1
		doc.time = date + ' ' + time
		doc.log_type = log_type
		doc.skip_auto_attendance = 0
		doc.notes = reason
		doc.insert()
		# Refech clockings for that date and recalculate
		self.get_employee_clockings_for_specific_date(date)

	@frappe.whitelist()
	def update_timesheet_detail_from_ui(self,row_name):
		for detail in self.monthly_time_sheet_detail:
			if detail.name == row_name:
				self.validate_row(detail)
				self.get_employee_clockings_for_specific_date(detail.date)


def get_shift_required_hours( shift):
		shift_required_hours = time_diff_in_hours(shift.start_time, shift.end_time)
		if shift.breaks_allowed == 1:
			shift_required_hours = shift_required_hours - (shift.allowed_break_time / 60)
		return shift_required_hours

def find_index_in_dict(dict_list, key, value):
	return next((index for (index, d) in enumerate(dict_list) if d[key] == value), None)

def is_valid_breaktime(start_time, end_time, break_times, break_times_type):
	breaktime_valid = True
	parsed_date = getdate(start_time)
	parsed_date = datetime(parsed_date.year,parsed_date.month, parsed_date.day, 0, 0, 0)
	for break_time in break_times:
		break_start_time = (parsed_date + break_time.start_time)
		break_end_time = (parsed_date + break_time.end_time)
		if break_times_type == 'Allowed':
			if start_time < break_start_time or start_time > break_end_time \
			   or end_time < break_start_time or end_time > break_end_time:
				breaktime_valid = False
		else:
			if (start_time >= break_start_time and start_time <= break_end_time) \
			   or (end_time >= break_start_time and end_time <= break_end_time):
				breaktime_valid = False
	return breaktime_valid

def floor_to(x, base=0.5):
     return round(base*math.floor(x/base), 2)

#Method extracted from Shift Assignment because of a bug in their code
def get_employee_shift(employee, for_date=None, consider_default_shift=False):
	"""Returns a Shift Type for the given employee on the given date. (excluding the holidays)

	:param employee: Employee for which shift is required.
	:param for_date: Date on which shift are required
	:param consider_default_shift: If set to true, default shift and holiday list is taken when no shift assignment is found.
	"""
	if for_date is None:
		for_date = nowdate()
	default_shift = frappe.db.get_value('Employee', employee, 'default_shift')
	shift_type_name = None
	shift_assignment_details = frappe.db.get_value('Shift Assignment', {'employee':employee, 'start_date':('>=', for_date),'end_date':('<=', for_date), 'docstatus': '1', 'status': "Active"}, ['shift_type', 'end_date'])

	if shift_assignment_details:
		shift_type_name = shift_assignment_details[0]

		# if end_date present means that shift is over after end_date else it is a ongoing shift.
		if shift_assignment_details[1] and for_date > shift_assignment_details[1] :
			shift_type_name = None

	if not shift_type_name and consider_default_shift:
		shift_type_name = default_shift
	else: 
		if shift_type_name and not consider_default_shift:
			return get_shift_details(shift_type_name, for_date)	
	
	if shift_type_name:
		holiday_list_name = frappe.db.get_value('Shift Type', shift_type_name, 'holiday_list')
		if not holiday_list_name:
			holiday_list_name = get_holiday_list_for_employee(employee, False)
		if holiday_list_name and is_holiday(holiday_list_name, for_date):
			shift_type_name = None
	return get_shift_details(shift_type_name, for_date)



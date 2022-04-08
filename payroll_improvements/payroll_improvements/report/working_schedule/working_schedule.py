# Copyright (c) 2022, AvN Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import date_diff
from frappe.utils.dateutils import get_dates_from_timegrain
from frappe.utils.data import get_timedelta
import datetime
from payroll_improvements.utilities.helpers import is_holiday
from payroll_improvements.payroll_improvements.doctype.monthly_timesheet.monthly_timesheet import get_employee_shift

def execute(filters=None):
	if not filters:
		return [], [], None, []
	validate_filters(filters)
	date_from, date_to = filters.get("date_from"), filters.get("date_to")
	dates = get_dates_from_timegrain(date_from, date_to, "Daily")
	columns = get_columns(filters,dates)
	data = get_data(filters,dates)
	return columns, data

def validate_filters(filters):
	date_from, date_to = filters.get("date_from"), filters.get("date_to")
	if not date_from and date_to:
		frappe.throw(_("From and To Dates are required."))
	elif date_diff(date_to, date_from) < 0:
		frappe.throw(_("To Date cannot be before From Date."))
	elif date_diff(date_to, date_from) > 31:
		frappe.throw(_("Date Range Cannot be more than one month"))

def get_data(filters,dates):
	public_holiday_list = get_public_holiday_list()
	employees = get_employees(filters)
	data = []
	for employee in employees:
		data.append(
			get_employee_data(employee,dates,public_holiday_list)
		)
	return data

def get_public_holiday_list():
		public_holiday_list = None
		hr_settings = frappe.get_single('HR Settings')
		#Get Public Holiday Lists
		if hr_settings.use_public_hours == 1:
			public_holiday_list = get_holiday_list(hr_settings.public_holiday_list)
		return public_holiday_list

def get_holiday_list(holiday_list_name):
	holiday_list = None
	if holiday_list_name != None and holiday_list_name.strip() != "":
		holiday_list = frappe.get_doc('Holiday List', holiday_list_name)
	return holiday_list

def get_employee_data(employee,dates,public_holiday_list):
	data = {
				'_employee': employee,
				'employee_name': '{0} - {1}'.format(employee.name,employee.employee_name)
	}
	for date in dates:
		is_public_holiday = is_holiday(public_holiday_list,date)
		shift = get_employee_shift(employee.name, for_date=date, consider_default_shift=(not is_public_holiday))
		date_data = {
			'is_public_holiday': is_public_holiday,
			'shift': shift,
			'is_date': True,
		}
		date_value = 'NW'
		if (is_public_holiday and shift == None):
			date_value = 'PH'
		elif (shift != None):
			date_value = '{0}-{1}'.format(get_time_str(shift.shift_type.start_time),get_time_str(shift.shift_type.end_time))
		data[date.strftime("%Y-%m-%d")] = date_value
		data["_{0}".format(date.strftime("%Y-%m-%d"))] = date_data

	return data

def get_employees(filters):
	conditions= {
			'status' : 'Active',
		}
	for key in filters:
		if not (key in ['date_from','date_to']):
			conditions[key] = filters[key]
	
	employees = frappe.db.get_list('Employee', fields=["name", "employee_name", "default_shift", "holiday_list","company","department"],
		 filters=conditions)
	return employees

def get_columns(filters, dates):
	columns = [
		{
			"label": _("Employee"),
			"fieldname": "employee_name",
			"fieldtype": "Link",
			"options": "Employee",
			"width": 160
		},
	]
	for date in dates:
		columns.append(
			{
			"label": _("{}").format(date.strftime("%a %d-%m-%Y")),
			"fieldname": date.strftime("%Y-%m-%d"),
			"fieldtype": "Data",
			"width": 100
			},
		)
	return columns

def get_time_str(timedelta_obj):
	if isinstance(timedelta_obj, str):
		timedelta_obj = get_timedelta(timedelta_obj)

	dt0 = datetime.datetime(1,1,1)
	return (dt0+timedelta_obj).strftime('%H:%M')


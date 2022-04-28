# Copyright (c) 2022, AvN Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import date_diff
from frappe.utils.dateutils import get_dates_from_timegrain
from frappe.utils.data import get_timedelta
from frappe.utils.data import getdate,nowdate
import datetime
from payroll_improvements.utilities.helpers import is_holiday

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
	date_from, date_to = filters.get("date_from"), filters.get("date_to")
	#PREFETCH ALL DATA NEEDED FOR REPORT SO WE DONT QUERY THE DATA MULTIPLE TIMES
	public_holiday_list = get_public_holiday_list()
	companies = get_companies()
	employees = get_employees(filters)
	employee_ids = get_employee_ids(employees)
	#fetch all shift assignements for all employees
	shift_assignements = get_shift_assignements(employee_ids,date_from,date_to)
	#Fetch all Approved & Submitted Leave Applications for all employees
	leave_applications = get_leave_applications(employee_ids,date_from,date_to)
	#Fetch All The Shift Types Needed
	shift_types = get_shift_types(employees,shift_assignements)
	#Fetch all Holiday Lists We will need
	holiday_lists= get_all_holiday_lists(employees, shift_types, companies)
	print('leave_applications',leave_applications)
	data = []
	for employee in employees:
		data.append(
			get_employee_data(employee,dates,public_holiday_list, companies, shift_assignements,leave_applications,shift_types, holiday_lists)
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


def get_employee_data(employee,dates,public_holiday_list, companies, shift_assignements,leave_applications,shift_types, holiday_lists):
	data = {
				'_employee': employee,
				'employee_name': '{0} - {1}'.format(employee.name,employee.employee_name)
	}

	for date in dates:
		is_public_holiday = is_holiday(public_holiday_list,date)
		leave_application = list(filter(lambda leave_application: leave_application.employee == employee.name and date >= leave_application.from_date and date <= leave_application.to_date, 
		leave_applications)) 
		if len(leave_application) > 0:
			leave_application = leave_application[0]
		else:
			leave_application = None
		shift = get_employee_shift(employee, shift_assignements, shift_types,companies,holiday_lists, for_date=date, consider_default_shift=(not is_public_holiday))
		date_data = {
			'is_public_holiday': is_public_holiday,
			'is_on_leave': (leave_application != None),
			'leave_application': leave_application,
			'shift': shift,
			'is_date': True,
		}
		date_value = 'NW'
		if (is_public_holiday and shift == None):
			date_value = 'PH'
		elif (shift != None and leave_application == None):
			date_value = '{0}-{1}'.format(get_time_str(shift.start_time),get_time_str(shift.end_time))
		elif (leave_application != None):
			date_value = leave_application.leave_type
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

def get_shift_assignements(employee_ids, start_date, end_date):
	conditions= {
		'docstatus' : '1',
		'employee' : ['in', employee_ids],
		'status': "Active",
	}
	or_filters= {
		'start_date': ['between', (start_date, end_date)],	
		'end_date': ['between', (start_date, end_date)],
	}
	shift_assignement = frappe.db.get_all('Shift Assignment',fields=["*"], filters=conditions, or_filters=or_filters)
	return shift_assignement

def get_leave_applications(employee_ids, start_date, end_date):
	conditions= {
		'docstatus' : '1',
		'employee' : ['in', employee_ids],
		'status' : 'Approved',
	}
	or_filters= {
		'from_date': ['between', (start_date, end_date)],	
		'to_date': ['between', (start_date, end_date)],
	}
	leave_applications = frappe.db.get_all('Leave Application',fields=["name","employee","leave_type","from_date","to_date"], filters=conditions, or_filters=or_filters)
	return leave_applications

def get_shift_types(employees,shift_assignements):
	default_shifts = list(set([d['default_shift'] for d in employees if 'default_shift' in d]))
	shift_in_shift_assignements = list(set([d['shift_type'] for d in shift_assignements if 'shift_type' in d]))
	all_shifts = list(filter(lambda value: value != None and value.strip() != "", list(set(default_shifts + shift_in_shift_assignements))))
	
	conditions= {
		'name' : ['in', all_shifts],
	}
	shift_types = frappe.db.get_all('Shift Type',fields=["*"], filters=conditions)
	return shift_types

def get_companies():
	companies = frappe.db.get_all('Company',fields=["name","default_holiday_list"])
	return companies

def get_all_holiday_lists(employees, shift_types, companies):
	holiday_lists=[]
	default_holiday_lists = list(set([d['holiday_list'] for d in employees if 'holiday_list' in d]))
	holiday_list_in_shift_types = list(set([d['holiday_list'] for d in shift_types if 'holiday_list' in d]))
	holiday_list_in_companies = list(set([d['default_holiday_list'] for d in companies if 'default_holiday_list' in d]))
	all_holiday_lists = list(filter(lambda value: value != None and value.strip() != "", list(set(default_holiday_lists + holiday_list_in_shift_types + holiday_list_in_companies))))
	
	for holiday_list_name in all_holiday_lists:
		holiday_list = get_holiday_list(holiday_list_name)
		holiday_lists.append(holiday_list)
	return holiday_lists

def get_employee_ids(emlpoyee_list):
	return [d['name'] for d in emlpoyee_list]

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

#Method extracted from Montly Time Sheet as all info is prefetched in this report and should not requery
def get_employee_shift(employee, shift_assignements, shift_types, companies, holiday_lists, for_date=None, consider_default_shift=False):
	"""Returns a Shift Type for the given employee on the given date. (excluding the holidays)

	:param employee: Employee for which shift is required.
	:param for_date: Date on which shift are required
	:param consider_default_shift: If set to true, default shift and holiday list is taken when no shift assignment is found.
	"""
	if for_date is None:
		for_date = nowdate()
	default_shift = employee.default_shift
	shift_type_name = None
	shift_assignment_details = list(filter(lambda shift_assignement: shift_assignement.employee == employee.name and shift_assignement.start_date >= for_date and shift_assignement.end_date <= for_date, 
		shift_assignements)) 
	
	if len(shift_assignment_details) > 0:
		shift_assignment_details = shift_assignment_details[0]
		shift_type_name = shift_assignment_details.shift_type
		# if end_date present means that shift is over after end_date else it is a ongoing shift.
		if shift_assignment_details.end_date and for_date > shift_assignment_details.end_date :
			shift_type_name = None

	if not shift_type_name and consider_default_shift:
		shift_type_name = default_shift
	else: 
		if shift_type_name and not consider_default_shift:
			return get_shift_details(shift_type_name, shift_types)	
	
	if shift_type_name:
		shift_type = get_shift_details(shift_type_name, shift_types)
		holiday_list_name = shift_type.holiday_list
		if not holiday_list_name:
			holiday_list_name = get_holiday_list_for_employee(employee,companies)
		if holiday_list_name:
			holiday_list = get_holiday_list_by_name(holiday_list_name,holiday_lists)
			if is_holiday(holiday_list, for_date):
				shift_type_name = None
	return get_shift_details(shift_type_name, shift_types)

#Method extracted from Shift Assignement as all info is prefetched in this report and should not requery
def get_shift_details(shift_type_name,shift_types):
	for shift_type in shift_types:
		if shift_type_name == shift_type.name:
			return shift_type
	return None
	

#Method extracted from Employee as all info is prefetched in this report and should not requery
def get_holiday_list_for_employee(employee,companies):
	if not employee.holiday_list:
		holiday_list = None
		for company in companies:
			if company.name == employee.company:
				return company.holiday_list	
	return employee.holiday_list

def get_holiday_list_by_name(holiday_list_name,holiday_lists):
	for holiday_list in holiday_lists:
		if holiday_list.name == holiday_list_name:
			return holiday_list
	return None

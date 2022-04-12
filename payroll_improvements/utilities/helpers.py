import frappe
from frappe.utils import today
from frappe.utils.data import getdate

def find_index_in_dict(dict_list, key, value):
	return next((index for (index, d) in enumerate(dict_list) if d.get(key) == value), None)

def is_holiday(holiday_list,date=None):
	"""Returns true if the given date is a holiday in the given holiday list
	Duplicated the function from erpnext.hr.doctype.holiday_list.holiday_list to avoid the additional Database Call
	"""
	if date is None:
		date = today()
	if holiday_list == None:
		return False
	index_of_holiday = find_index_in_dict(holiday_list.holidays,'holiday_date',date)
	return bool(index_of_holiday != None and index_of_holiday >= 0)
    
@frappe.whitelist()
def format_date_output(date,str):
	fixed_date = getdate(date)
	try:
		return fixed_date.strftime(str) 
	except:
		return fixed_date.strftime("%Y-%m-%d") 
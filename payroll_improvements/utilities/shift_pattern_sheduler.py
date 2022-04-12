import frappe
from frappe import _
from frappe.utils import today
from frappe.utils.data import getdate

def create_auto_shift_pattern_assignements():
    # Find Shift Patterns to Generate 
	filters = {
			'status' : 'Active',
            'auto_assign' : 1,
            'next_run_date': ('<=', getdate(today())),
		}
    
	patterns = frappe.db.get_list('Shift Pattern', fields=['name','next_run_date','auto_assign'],filters=filters)
	for pattern in patterns:
			shift_pattern = frappe.get_doc('Shift Pattern', pattern.name)
			shift_pattern.auto_generate_pattern()


# Copyright (c) 2022, AvN Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

class ShiftPatternAssignment(Document):
	def validate(self):
		#Remove Duplicate Employees
		self.remove_duplicate_employees()
		#Validate if any employees Have a Shift Patern Assignment in this period already
		#Validate if any employees default shift conflicts with this Shift Patern Assignment

	def on_submit(self):
		# Create All the Shift Assignments
		self.create_shift_assignments()
		

	def on_cancel(self):
		#Delete all the shift assignments created
		frappe.delete_doc("Shift Assignment", frappe.db.sql_list("""select name from `tabShift Assignment`
			where shift_pattern_assignment=%s """, (self.name)))
		

	def create_shift_assignments(self):
		#Need a list of employees:
		employees = self.get_assigned_employees()
		#Get the shift Pattern:
		shift_pattern = frappe.get_doc('Shift Pattern', self.shift_pattern)
		#Call Create for range
		shift_pattern.build_shift_assignments_for_employees_by_date_range(self.start_date, self.end_date, employees, add_data = {
			'shift_pattern_assignment': self.name
		})
	
	def get_assigned_employees(self):
		employee_name_list = []
		for e in self.employees:
			employee_name_list.append(e.employee)
		filters = {
			'name': ['in', employee_name_list ],
		}
		employees = frappe.db.get_list('Employee', fields=["name", "employee_name", "default_shift", "holiday_list","company","department"],
		 filters=filters)
		return employees


	def remove_duplicate_employees(self):
		seen = set()
		dupes = []
		for e in self.employees:
			if e.employee in seen:
				dupes.append(e)
			else:
				seen.add(e.employee)
		for doc in dupes:
			self.remove(doc)
		


	
	@frappe.whitelist()
	def add_employees(self, data):
		add_all = data.get('add_all',0)
		selections = data.get('selections',[])
		if add_all == 0 and len(selections) == 0:
			frappe.throw(
				_("Cannot Add Empolyees, No Employees Where Selected")
				)
		if add_all == 1:
			self.add_all_employees(data)
		else:
			self.add_selected_employees(selections)
	
	def add_selected_employees(self,selection):
		conditions = [{
			'name' : ['in',selection],
		}]
		self.add_employees_by_filter(conditions)

	def add_all_employees(self, data):
		conditions =  []
		for key in data:
			if not (key in ['add_all','filtered_children','selections']):
				conditions.append({
					key:data[key]
				})
		self.add_employees_by_filter(conditions)
	
	def add_employees_by_filter(self, filter):
		employees = frappe.db.get_list('Employee', fields=["*"], filters=filter)
		if employees != None and len(employees) > 0:
			for employee in employees:
				self.append('employees', {
				"employee": employee.name, 
				"employee_name": employee.employee_name, 
				"branch": employee.branch, 
				"department": employee.department,
				"designation": employee.designation,
				"grade": employee.grade,
				})
			frappe.msgprint(
				msg= _('{0} Employees where added').format(len(employees)),
				title= _('Employees Added'),
				indicator= 'green',
			)
			self.save()
		else:
			frappe.msgprint(
				msg= _('No Employees could be found to be added'),
				title= _('No Employees where Added'),
				indicator= 'red',
			)

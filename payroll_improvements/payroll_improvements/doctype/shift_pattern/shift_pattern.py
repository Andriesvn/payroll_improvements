# Copyright (c) 2022, AvN Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_to_date
from frappe.utils.data import getdate
from frappe.utils import today
from datetime import timedelta
from payroll_improvements.utilities.helpers import is_holiday


class ShiftPattern(Document):
	def validate(self):
		cur_len = len(self.shift_pattern_details)
		if cur_len != self.cycle:
			self.update_patern_details()


	def update_patern_details(self):
		cur_len = len(self.shift_pattern_details)
		if self.cycle == cur_len:
			return
		if self.cycle > cur_len:
			for i in range(self.cycle - cur_len):
				row = self.append('shift_pattern_details')
		else:
			for i in range(cur_len - self.cycle):
				row = self.shift_pattern_details[cur_len - (i + 1)]
				self.remove(row)

	
	def build_shift_assignments_for_employees_by_date_range(self,start_date, end_date, employees, add_data = None):
		"""Creates Shift Assignments based on this pattern for a specific Date Range Per Employee
		
		:param start_date: Date from.
		:param end_date: Date To
		:param employees: a List of Employee Docs. 
						  *Must contain name, employee_name, default_shift, holiday_list,company,department
		:param add_data: Additional Data to be added to the shift assignement (Dict)
		"""
		public_holiday_list = self.get_public_holiday_list()
		shift_assignments = self.get_shift_assignements_for_date_range(start_date, end_date)

		for employee in employees:
			self.build_shift_assignments_for_employee(employee,shift_assignments,public_holiday_list,add_data=add_data)
		

	def build_shift_assignments_for_employee(self, employee,shift_assignments,public_holiday_list, add_data=None):
		default_shift = None
		if employee.default_shift != None and employee.default_shift.strip() != "":
			default_shift = frappe.get_doc('Shift Type', employee.default_shift)
		if default_shift != None and default_shift.holiday_list != None and default_shift.holiday_list.strip() != "":
			default_shift._holiday_list = frappe.get_doc('Holiday List', default_shift.holiday_list)
		
		def_shift_assignment = {
			"doctype":"Shift Assignment",
			'employee': employee.name,
			'employee_name': employee.employee_name,
			'company': employee.company,
			'department': employee.department,
			'shift_type' : None,
			'start_date' : None,
			'end_date' : None,
		}
		#add Additional Data to default
		if add_data != None:
			for key in add_data:
				def_shift_assignment[key] = add_data[key]
			
		cur_shift_assignement = None
		for shift_assignment in shift_assignments:
			is_public_holiday = bool(self.skip_public_holidays == 1 and is_holiday(public_holiday_list,shift_assignment['start_date']))
			is_default_working = bool(not default_shift == None and not default_shift._holiday_list == None and not is_holiday(default_shift._holiday_list, shift_assignment['start_date']))
			is_default_shift = bool(not default_shift == None and shift_assignment['shift_type'] == default_shift.name)
			is_off = bool(shift_assignment['shift_type'] == None or shift_assignment['shift_type'].strip() == "")
			if not is_public_holiday and not is_default_shift and not is_default_working and not is_off:
				#We need to create a shift assignment
				if cur_shift_assignement == None:
					#create a new one
					cur_shift_assignement = copy_shift_assignement(def_shift_assignment,shift_assignment)
				else:
					if cur_shift_assignement['shift_type'] == shift_assignment['shift_type']:
						#just update the end_date
						cur_shift_assignement['end_date'] = shift_assignment['start_date']
					else:
						#we need to save the cur_shift_assignement and create a new one
						save_shift_assinment(cur_shift_assignement)
						cur_shift_assignement = copy_shift_assignement(def_shift_assignment,shift_assignment)
			else:
				#He is not suppose to be working or working default shift.
				if cur_shift_assignement != None:
					#we need to save the cur_shift_assignement and make it None
					save_shift_assinment(cur_shift_assignement)
					cur_shift_assignement = None
				#here we also need to validate that the default shift does not Conflict with the off day assignement	
				if is_default_working and is_off and not is_public_holiday:
					frappe.throw(
						_("Employee {0} - {1}'s Default Shift Conflicts with This shift assignemnt : {2} on {3}")
						.format(employee.name,employee.employee_name,shift_assignment['shift_type'],shift_assignment['start_date'].strftime("%Y-%m-%d"))
						)
		if cur_shift_assignement != None:
			save_shift_assinment(cur_shift_assignement)	


	def get_shift_assignements_for_date_range(self, start_date, end_date):
		"""Returns a list of start_date and shift_type from start date to end date based on this shift pattern
		
		:param start_date: Date from.
		:param end_date: Date To
		"""
		start_date = getdate(start_date)
		end_date = getdate(end_date)
		cur_date = start_date
		shift_assignments = []
		while cur_date <= end_date:
			for pattern_detail in self.shift_pattern_details:
				for key in pattern_detail.as_dict():
					if cur_date > end_date:
						break
					if key == cur_date.strftime("%a").lower():
						shift_assignments.append({
							'start_date': cur_date,
							'shift_type' : pattern_detail.get(key),
						})
						cur_date = add_to_date(cur_date,days=1)
		return shift_assignments
	
	def get_public_holiday_list(self):
		public_holiday_list = None
		self._hr_settings = frappe.get_single('HR Settings')
		#Get Public Holiday Lists
		if self._hr_settings.use_public_hours == 1:
			public_holiday_list_name = self._hr_settings.public_holiday_list
			if public_holiday_list_name != None and public_holiday_list_name.strip() != "":
				public_holiday_list = frappe.get_doc('Holiday List', public_holiday_list_name)
		return public_holiday_list

	@frappe.whitelist()
	def auto_generate_pattern(self):
		# if the next run date is not less than today or inactive, dont do anything
		# create_auto_shift_pattern_assignements()
		if self.status != 'Active' or (self.next_run_date != None and getdate(self.next_run_date) > getdate(today())):
			return

		date_from, date_to, next_run_date = self.get_auto_generate_dates()
		employees = self.get_auto_generate_employees()

		if employees != None and len(employees) > 0:
			self.build_shift_assignments_for_employees_by_date_range(date_from, date_to, employees, add_data = {
				'auto_generated_shift_pattern': self.name
			})
		self.next_run_date = next_run_date
		self.last_end_date = date_to
		self.save()

	def get_auto_generate_employees(self):
		filters = {
			'auto_shift_pattern': self.name,
			'status' : 'Active',
		}
		employees = frappe.db.get_list('Employee', fields=["name", "employee_name", "default_shift", "holiday_list","company","department"],
		 filters=filters)
		return employees

	def get_auto_generate_dates(self):
		cycle_days = self.cycle * 7
		date_from = getdate(self.start_date) - timedelta(days=1)
		date_to = getdate(today()) + timedelta(days=1)

		if self.last_end_date != None:
			date_from = getdate(self.last_end_date)
			date_to = getdate(self.last_end_date) + timedelta(days=(cycle_days * self.cycles_to_generate))

		days = (date_to - date_from).days
		# need to complete the cycle first
		extra_days_to_add = 0
		if (days % cycle_days) != 0:
			extra_days_to_add = cycle_days - (days % cycle_days)
		total_days_to_add = extra_days_to_add + (cycle_days * self.cycles_to_generate)
		if date_to <= getdate(today()):
			date_to = date_to + timedelta(days=total_days_to_add)
		# We need to stay ahead of the cycle by cycles_to_generate ammount 
		if ((date_to - (getdate(today()) + timedelta(days=cycle_days))).days + 1) < (cycle_days * self.cycles_to_generate):
			date_to = date_to + timedelta(days=cycle_days)
		next_run_date = date_to - timedelta(days=cycle_days)
		#date_from has already been generated so we skip it
		date_from = date_from + timedelta(days=1)
		return date_from, date_to, next_run_date


def save_shift_assinment(shift_assignment):
	new_doc = frappe.get_doc(shift_assignment)
	new_doc.insert()
	new_doc.submit()

def copy_shift_assignement(def_shift_assignment, shift_assignment):
	cur_shift_assignement = def_shift_assignment.copy()
	cur_shift_assignement['shift_type'] = shift_assignment['shift_type']
	cur_shift_assignement['start_date'] = shift_assignment['start_date']
	cur_shift_assignement['end_date'] = shift_assignment['start_date']
	return cur_shift_assignement
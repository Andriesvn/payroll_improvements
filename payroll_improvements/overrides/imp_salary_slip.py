import frappe
import frappe, erpnext
import math

from frappe import msgprint, _
from frappe.utils import formatdate,getdate
from erpnext.payroll.doctype.salary_slip.salary_slip import SalarySlip
from erpnext.payroll.doctype.payroll_period.payroll_period import get_period_factor, get_payroll_period
from six import iteritems

class ImpSalarySlip(SalarySlip):

	def add_structure_components(self, component_type):
		super(ImpSalarySlip, self).add_structure_components(component_type)
		# Get the salary Structure assignement as well since we will need it
		if not getattr(self, '_salary_structure_assignment_doc', None):
			self._salary_structure_assignment_doc = self.get_salary_structure_assignment()
		
		# update the hourly Rate while we are at it We need to do this here somewhere as its already set by this point
		if (self.hourly_rate != self._salary_structure_assignment_doc.hourly_rate):
			self.hourly_rate = self._salary_structure_assignment_doc.hourly_rate
			self.required_hours = self._salary_structure_assignment_doc.required_hours
		
		self.add_assignment_structure_components(component_type)
		
	
		
	#Overwride this method to get the new Monthlytimesheet as well
	def set_time_sheet(self):
		#Now get the New timesheet too
		super(ImpSalarySlip, self).set_time_sheet()
		#TODO: REWRITE USING frappe.qb instead
		#monthly_timesheet = frappe.db.sql("""Select TS.`name`, TS.`total_normal_hours`, TS.`total_overtime_hours`, TS.`total_dot_hours`, TS.`total_lunch_hours`, TS.`required_hours`, TP.`payroll_date` \
		#	FROM `tabMonthly Timesheet` as TS \
		#	LEFT OUTER JOIN `tabTimesheet Period` As TP on (TS.`timesheet_period` = TP.`name`)
		#	Where TS.`employee` = %(employee)s and TP.`payroll_date` BETWEEN %(start_date)s AND %(end_date)s \
		#	AND TS.status = 'Approved' and TS.docstatus = 1""", 
		#	{'employee': self.employee, 'start_date': self.start_date, 'end_date': self.end_date}, as_dict=1)
		
		#if monthly_timesheet != None and len(monthly_timesheet) > 0:
		#	monthly_timesheet = monthly_timesheet[0]
		#	self.monthly_timesheet = monthly_timesheet['name']
		#	self.total_normal_hours = monthly_timesheet['total_normal_hours']
		#	self.total_overtime_hours = monthly_timesheet['total_overtime_hours']
		#	self.total_double_overtime_hours = monthly_timesheet['total_dot_hours']
		#	self.total_lunch_hours = monthly_timesheet['total_lunch_hours']
	
	#Add Salary Structure Assignment components
	def add_assignment_structure_components(self, component_type):
		data = self.get_data_for_eval()
		for struct_row in self._salary_structure_assignment_doc.get(component_type):
			amount = self.eval_condition_and_formula(struct_row, data)
			if amount and struct_row.statistical_component == 0:
				self.update_component_row(struct_row, amount, component_type)
	
	
	def get_salary_structure_assignment(self):
		employee = frappe.get_doc("Employee", self.employee).as_dict()

		start_date = getdate(self.start_date)
		date_to_validate = (
			employee.date_of_joining
			if employee.date_of_joining > start_date
			else start_date
		)
		salary_structure_assignment = frappe.get_value(
			"Salary Structure Assignment",
			{
				"employee": self.employee,
				"salary_structure": self.salary_structure,
				"from_date": ("<=", date_to_validate),
				"docstatus": 1,
			},
			"*",
			order_by="from_date desc",
			as_dict=True,
		)

		if not salary_structure_assignment:
			frappe.throw(
				_("Please assign a Salary Structure for Employee {0} "
				"applicable from or before {1} first").format(
					frappe.bold(self.employee_name),
					frappe.bold(formatdate(date_to_validate)),
				)
		)
		ss_assignment = frappe.get_doc('Salary Structure Assignment', salary_structure_assignment.name)
		return ss_assignment

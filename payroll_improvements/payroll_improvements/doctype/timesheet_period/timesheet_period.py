# -*- coding: utf-8 -*-
# Copyright (c) 2021, AvN Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import msgprint, _
from frappe.model.document import Document

class TimesheetPeriod(Document):
	def autoname(self):
		# select a project name based on customer
		self.name = 'TSP:{0}-{1}-{2}'.format(self.company,self.date_from,self.date_to)

	def on_submit(self):
		# Create Time Sheets for all empolyees in this company
		self.create_monthly_timesheets()

	def on_cancel(self):
		frappe.delete_doc("Monthly Timesheet", frappe.db.sql_list("""select name from `tabMonthly Timesheet`
			where timesheet_period=%s """, (self.name)))

	def create_monthly_timesheets(self):
		# get a list of all employees with a salary structure assignment
		emp_list = [d.employee for d in self.get_employees_with_salary_structure()]
		if emp_list == None or len(emp_list) == 0 :
			frappe.throw(
				_("No Employees found with valid Salary Structure Assignments to generate Timesheets for.")
				)
		args = frappe._dict({
				"timesheet_period": self.name,
			})
		if len(emp_list) > 30:
			frappe.enqueue(insert_employee_timesheets, timeout=600, employees=emp_list, args=args)
		else:
			insert_employee_timesheets(emp_list, args, publish_progress=False)
			# since this method is called via frm.call this doc needs to be updated manually
			self.reload()

	def get_employees_with_salary_structure(self):
		emp_list = frappe.db.sql("""
			select
				distinct t1.name as employee
			from
				`tabEmployee` t1, `tabSalary Structure Assignment` t2
			where
				t1.name = t2.employee
				and t1.company = %(company)s
				and t2.docstatus = 1
				and %(from_date)s >= t2.from_date
		    order by t2.from_date desc
		""", {"company": self.company, "from_date": self.date_to}, as_dict=True)
		return emp_list

def insert_employee_timesheets(employees, args, publish_progress=True):
	existing_timesheets = get_existing_timesheets(args)
	#print("existing timesheets:", existing_timesheets)
	count=0
	for emp in employees:
		if emp not in existing_timesheets:
			args.update({
				"doctype": "Monthly Timesheet",
				"employee": emp
			})
			ss = frappe.get_doc(args)
			#print('Creating Timesheet for ', emp)
			ss.insert()
			count+=1
			if publish_progress:
				frappe.publish_progress(count*100/len(set(employees) - set(existing_timesheets)),
					title = _("Creating TimeSheets..."))


	timesheet_period = frappe.get_doc("Timesheet Period", args.timesheet_period)
	timesheet_period.notify_update()
	if publish_progress == False:
		frappe.msgprint(_("Timesheets where generated for {0} employees").
									format(len(employees)), alert=False)

def get_existing_timesheets(args):
	return frappe.db.sql_list("""
		select distinct employee from `tabMonthly Timesheet`
		where timesheet_period = %s
	""",[args.timesheet_period])


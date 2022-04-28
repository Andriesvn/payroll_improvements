// Copyright (c) 2022, AvN Technologies and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Working Schedule"] = {
	"filters": [
	{
		"fieldname": "company",
		"fieldtype": "Link",
		"label": __("Company"),
		"width": "80",
		"mandatory": 1,
		"options": "Company",
		"reqd": 1,
		"default": frappe.defaults.get_default("company")
	},
	{
		"fieldname": "date_from",
		"fieldtype": "Date",
		"label": __("From Date"),
		"width": "80",
		"mandatory": 1,
		"reqd": 1,
		"default": frappe.datetime.get_today(),
		on_change: function() {
			let date_from = frappe.query_report.get_filter_value('date_from');
			frappe.query_report.set_filter_value('date_to',frappe.datetime.add_months(date_from, 1));
		},
	},
	{
		"fieldname": "date_to",
		"fieldtype": "Date",
		"label": __("To Date"),
		"width": "80",
		"mandatory": 1,
		"reqd": 1,
	},
	{
		"fieldname": "branch",
		"fieldtype": "Link",
		"label": __("Branch"),
		"width": "80",
		"mandatory": 0,
		"options": "Branch",
		"default": frappe.defaults.get_default("branch")
	},
	{
		"fieldname": "department",
		"fieldtype": "Link",
		"label": __("Department"),
		"width": "80",
		"mandatory": 0,
		"options": "Department",
	},
	{
		"fieldname": "designation",
		"fieldtype": "Link",
		"label": __("Designation"),
		"width": "80",
		"mandatory": 0,
		"options": "Designation",
	},
	{
		"fieldname": "grade",
		"fieldtype": "Link",
		"label": __("Grade"),
		"width": "80",
		"mandatory": 0,
		"options": "Employee Grade",
	},
	],
	"formatter": function(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (data && column.fieldname=="employee_name") {
			value = `<a href="/app/employee/${data._employee.name}"
					data-doctype="Employee"
					data-name="${data._employee.name}">
					${data._employee.name} - ${data._employee.employee_name}</a>`;
					
		} else if (data && data[`_${column.fieldname}`] && data[`_${column.fieldname}`]['is_date'] ) {
			shift_data = data[`_${column.fieldname}`]
			if (shift_data.is_public_holiday && !shift_data.shift && !shift_data.is_on_leave){
				value=`<span class="bold" style="color: var(--text-on-blue)">${value}</span>`;
			} else if (!shift_data.is_public_holiday && !shift_data.shift && !shift_data.is_on_leave){
				value=`<span class="bold" style="color: var(--text-on-green)">${value}</span>`;
			}
			else if (shift_data.shift && !shift_data.is_on_leave){
				value= `<a href="/app/shift-type/${shift_data.shift.name}"
					data-doctype="Shift Type"
					data-name="${shift_data.shift.name}">
					${value}</a>`
			}
			else if (shift_data.is_on_leave){
				value= `<a href="/app/leave-application/${shift_data.leave_application.name}"
					data-doctype="Leave Application"
					data-name="${shift_data.leave_application.name}"
					class="bold" style="color: var(--text-on-orange)">
					${value}</a>`
			}	
		}
		return value;
	},
};

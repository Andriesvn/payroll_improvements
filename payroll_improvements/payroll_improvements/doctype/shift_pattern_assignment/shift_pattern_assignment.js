// Copyright (c) 2022, AvN Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Shift Pattern Assignment', {
	onload: function(frm) {
		frappe.breadcrumbs.add({
			module: 'HR',
			doctype: 'Shift Pattern Assignment'
		});
	},
	
	refresh: function(frm) {
		if (frm.doc.docstatus == 0 && !frm.is_new()) {
			frm.add_custom_button(__("Add Employees"),
				function() {
					frm.trigger("add_employees");
				}
			).toggleClass('btn-primary');
			frm.trigger("update_grid_buttons");
		}
	 },
	 update_grid_buttons:function(frm){
		frm.fields_dict['employees'].grid.clear_custom_buttons();
		frm.fields_dict['employees'].grid.add_custom_button(__("Add Employees"),
			function() {
				frm.trigger("add_employees");
			}
		).toggleClass('btn-primary');
	 },
	 add_employees:function(frm){
		console.log('Add Employees Clicked')
		let me = frm;
		me._dialog = new frappe.ui.form.MultiSelectDialog({
			doctype: "Employee",
			target: frm,
			setters: {
				employee_name: '',
				company: '',
				department: '',
				branch: '',
				department: '',
				designation: '',
				grade:'',
			},
			data_fields: [
				{
					fieldname: 'add_all',
					fieldtype: 'Check',
					label: __('Add all employees under this filter')
				},
			],
			columns: ["name", "employee_name", "company","branch","department","designation","grade"],
			primary_action_label: "Assign",
			get_query() {
				return {
					filters: { 
						status: ['=', 'Active']
					 }
				}
			},
			action(selections, args) {
				const data = {
					...args,
					selections
				}
				frappe.call({
					doc: me.doc,
					method: 'add_employees',
					args: {
						data: data,
					},
					callback: function(r) {
						me._dialog.dialog.hide();
						frm.reload_doc();
					},
					freeze: true,
					freeze_message: __("Adding Employees")
				});
			}
		});
	 },
});

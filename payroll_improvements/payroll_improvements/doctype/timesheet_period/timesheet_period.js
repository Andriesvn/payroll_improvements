// Copyright (c) 2021, AvN Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Timesheet Period', {
	// refresh: function(frm) {

	// }

	onload: function(frm) {
		frappe.breadcrumbs.add({
			module: 'HR',
			doctype: 'Timesheet Period'
		});
	},
});

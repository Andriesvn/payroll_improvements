// Copyright (c) 2022, AvN Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Shift Pattern', {
	onload: function(frm) {
		frappe.breadcrumbs.add({
			module: 'HR',
			doctype: 'Shift Pattern'
		});
	},

	 refresh: function(frm) {
		frm.fields_dict['shift_pattern_details'].grid.wrapper.find('.grid-remove-rows').hide();
		frm.fields_dict['shift_pattern_details'].grid.wrapper.find('.grid-add-row').hide();
		frm.fields_dict['shift_pattern_details'].grid.wrapper.find('.grid-add-multiple-rows').hide();	
	 },
	 shift_pattern_details_on_form_rendered: function(frm, cdt, cdn){
		frm.fields_dict['shift_pattern_details'].grid.wrapper.find('.grid-delete-row').hide();
		frm.fields_dict['shift_pattern_details'].grid.wrapper.find('.grid-duplicate-row').hide();
		frm.fields_dict['shift_pattern_details'].grid.wrapper.find('.grid-move-row').hide();
		frm.fields_dict['shift_pattern_details'].grid.wrapper.find('.grid-append-row').hide();
		frm.fields_dict['shift_pattern_details'].grid.wrapper.find('.grid-insert-row-below').hide();
		frm.fields_dict['shift_pattern_details'].grid.wrapper.find('.grid-insert-row').hide();
	},

});

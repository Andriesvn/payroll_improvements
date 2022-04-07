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
		if (frm.doc.auto_assign == 1 && !frm.is_new()) {
			frm.add_custom_button(__("Run Auto Generate"),
				function() {
					frm.trigger("run_auto_generate");
				}
			).toggleClass('btn-primary');
		}
	 },
	 run_auto_generate:function(frm){
		frappe.call({
			doc: frm.doc,
			method: 'auto_generate_pattern',
			callback: function(r) {
				frm.reload_doc();
			},
			freeze: true,
			freeze_message: __("Running Auto Generate")
		});
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

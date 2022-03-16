// Copyright (c) 2021, AvN Technologies and contributors
// For license information, please see license.txt

frappe.provide("erpnext_wb_hr.woermann_hr.weekly_timesheet");

frappe.ui.form.on('Monthly Timesheet', {
	refresh: function(frm) {
		frm.trigger("draw_on_table");
		frm.fields_dict['monthly_time_sheet_detail'].grid.wrapper.find('.grid-remove-rows').hide();
		frm.fields_dict['monthly_time_sheet_detail'].grid.wrapper.find('.grid-add-row').hide();
		frm.fields_dict['monthly_time_sheet_detail'].grid.wrapper.find('.grid-add-multiple-rows').hide();

		if (frm.doc.docstatus == 0) {
			if(!frm.is_new() && frm.doc.status != 'Approved') {
				frm.page.clear_primary_action();
				frm.add_custom_button(__("Get Employee Clockings"),
					function() {
						frm.events.get_employee_clockings(frm);
					}
				).toggleClass('btn-primary');
				
				frm.trigger("update_grid_buttons");
				
				frm.fields_dict['monthly_time_sheet_detail'].grid.get_field('leave').get_query = function(doc, cdt, cdn) {
					var child = locals[cdt][cdn];
					//console.log(child);
					return {    
						filters: [
							['employee' , '=' , frm.doc.employee],
							['status' , '=' , 'Approved'],
							['from_date', '<=', String(moment(child.date).format('YYYY-MM-DD'))],
							['to_date', '>=', String(moment(child.date).format('YYYY-MM-DD'))],
						]
					}
				}
			}
		} else if (frm.doc.docstatus == 0 && frm.doc.status == 'Approved'){
			frm.clear_custom_buttons();
		}
	},

	onload: function(frm) {
		frappe.breadcrumbs.add({
			module: 'HR',
			doctype: 'Monthly Timesheet'
		});
	},
	update_grid_buttons:function(frm){
		frm.fields_dict['monthly_time_sheet_detail'].grid.clear_custom_buttons();
		frm.fields_dict['monthly_time_sheet_detail'].grid.add_custom_button(__("Approve Selected"),
			function() {
				var selected = frm.fields_dict['monthly_time_sheet_detail'].grid.get_selected_children();
				$.each(selected || [], (i, row) => {
					frappe.model.set_value(row.doctype, row.name, "is_approved", 1);
				});
				frm.refresh_field('monthly_time_sheet_detail');
				frm.fields_dict['monthly_time_sheet_detail'].grid.wrapper.find('.grid-add-row').hide();
			}
		);
	},
	draw_on_table: function(frm){
		frm.fields_dict["monthly_time_sheet_detail"].$wrapper.find('.grid-body .rows').find(".grid-row").each(function(i, item) {
			let d = locals[frm.fields_dict["monthly_time_sheet_detail"].grid.doctype][$(item).attr('data-name')];
			if (d.is_holiday == 1){
				$(item).find('.data-row').css({'border':'1px solid #aaddff'})
				$(item).find('.row-index').css({'background-color': '#aaddff'});
			}
			if(d["is_approved"] > 0){
				$(item).find('.grid-static-col').css({'background-color': '#adffaa'});
			} else {
				$(item).find('.grid-static-col').css({ 'background-color' : ''});
			}
			if (d.leave){
				if (d.leave_doc_status == 0 || d.leave_status != 'Approved'){
					$(item).find("[data-fieldname='leave']").css({'background-color': '#ffa00a'});
				}
			}
			if (d.attendance){
				if (["Present", "Work From Home"].includes(d.attendance)){
					$(item).find("[data-fieldname='attendance']").css({'background-color': '#adffaa'});
				} else if (["Absent"].includes(d.attendance)){
					$(item).find("[data-fieldname='attendance']").css({'background-color': '#ff5858'});
				} else if (["Half Day", "On Leave"].includes(d.attendance)){
					$(item).find("[data-fieldname='attendance']").css({'background-color': '#ffa00a'});
				} else if (d.attendance == "Holiday"){
					$(item).find("[data-fieldname='attendance']").css({'background-color': '#aaddff'});
				}
			}
			if (d.lunch){
				var lunch = moment(d.lunch,"HH:mm")
				if (lunch.isValid()){
					let dec_lunch = lunch.hours() + (lunch.minutes() / 60);
					if (dec_lunch > 1.05){
						$(item).find("[data-fieldname='lunch']").css({'background-color': '#ffa00a'});
					}	
				}
			}
			if ( (d.overtime_hours > 0 || d.double_overtime_hours > 0)){
				if (!d.notes){
					$(item).find("[data-fieldname='notes']").css({'background-color': '#ff5858'});
					if (d.overtime_hours > 0) {
						$(item).find("[data-fieldname='overtime_hours']").css({'background-color': '#ff5858'});
					}
					if (d.double_overtime_hours > 0) {
						$(item).find("[data-fieldname='double_overtime_hours']").css({'background-color': '#ff5858'});
					}
				}
			}
			if (( (d.checkin == d.checkout) && (d.checkin != '0:00:00' && d.checkin != '00:00') ) || 
			   ( (d.checkin != '0:00:00' && d.checkin != '00:00') && (d.checkout == '0:00:00' || d.checkout == '00:00'))) {
					$(item).find("[data-fieldname='checkin']").css({'background-color': '#ff5858'});
					$(item).find("[data-fieldname='checkout']").css({'background-color': '#ff5858'});
			}

		});
	},
	monthly_time_sheet_detail_on_form_rendered: function(frm, cdt, cdn){
		frm.fields_dict['monthly_time_sheet_detail'].grid.wrapper.find('.grid-delete-row').hide();
		frm.fields_dict['monthly_time_sheet_detail'].grid.wrapper.find('.grid-duplicate-row').hide();
		frm.fields_dict['monthly_time_sheet_detail'].grid.wrapper.find('.grid-move-row').hide();
		frm.fields_dict['monthly_time_sheet_detail'].grid.wrapper.find('.grid-append-row').hide();
		frm.fields_dict['monthly_time_sheet_detail'].grid.wrapper.find('.grid-insert-row-below').hide();
		frm.fields_dict['monthly_time_sheet_detail'].grid.wrapper.find('.grid-insert-row').hide();
	},
	get_employee_clockings: function (frm) {
		return frappe.call({
			doc: frm.doc,
			method: 'get_employee_clockings',
			callback: function(r) {
				frm.reload_doc();
			},
			freeze: true,
			freeze_message: __("Getting Employee Clockings...")
		})
	},

});

frappe.ui.form.on('Monthly Timesheet Detail', {
    // cdt is Child DocType name i.e Quotation Item
    // cdn is the row name for e.g bbfcb8da6a
	refresh: function(frm) {
	},
    is_approved(frm) {
        frm.trigger("draw_on_table");
    },
	leave(frm) {
        frm.trigger("draw_on_table");
    },
	overtime_hours(frm) {
        frm.trigger("draw_on_table");
    },
	double_overtime_hours(frm) {
        frm.trigger("draw_on_table");
    },
	notes(frm) {
        frm.trigger("draw_on_table");
    },
	lunch(frm) {
        frm.trigger("draw_on_table");
    },
	checkin(frm) {
        frm.trigger("draw_on_table");
		//AND RECALCULATE NORMAL HOURS
    },
	checkout(frm) {
        frm.trigger("draw_on_table");
		//AND RECALCULATE NORMAL HOURS
    },
})

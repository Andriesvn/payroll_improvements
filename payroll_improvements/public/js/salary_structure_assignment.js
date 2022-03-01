frappe.ui.form.on('Salary Structure Assignment', {
    onload: function(frm) {
        frm.set_query("salary_component", "earnings", function() {
			return {
				filters: {
					type: "earning"
				}
			}
		});
		frm.set_query("salary_component", "deductions", function() {
			return {
				filters: {
					type: "deduction"
				}
			}
		});
    }
})

frappe.ui.form.on('Salary Detail', {
	salary_component: function(frm, cdt, cdn) {
		var child = locals[cdt][cdn];
		if(child.salary_component){
			frappe.call({
				method: "frappe.client.get",
				args: {
					doctype: "Salary Component",
					name: child.salary_component
				},
				callback: function(data) {
					if(data.message){
						var result = data.message;
						frappe.model.set_value(cdt, cdn, 'condition', result.condition);
						frappe.model.set_value(cdt, cdn, 'amount_based_on_formula', result.amount_based_on_formula);
						if(result.amount_based_on_formula == 1){
							frappe.model.set_value(cdt, cdn, 'formula', result.formula);
						}
						else{
							frappe.model.set_value(cdt, cdn, 'amount', result.amount);
						}
						frappe.model.set_value(cdt, cdn, 'statistical_component', result.statistical_component);
						frappe.model.set_value(cdt, cdn, 'depends_on_payment_days', result.depends_on_payment_days);
						frappe.model.set_value(cdt, cdn, 'do_not_include_in_total', result.do_not_include_in_total);
						frappe.model.set_value(cdt, cdn, 'variable_based_on_taxable_salary', result.variable_based_on_taxable_salary);
						frappe.model.set_value(cdt, cdn, 'is_tax_applicable', result.is_tax_applicable);
						frappe.model.set_value(cdt, cdn, 'is_flexible_benefit', result.is_flexible_benefit);
						refresh_field("earnings");
						refresh_field("deductions");
					}
				}
			});
		}
	},

	amount_based_on_formula: function(frm, cdt, cdn) {
		var child = locals[cdt][cdn];
		if(child.amount_based_on_formula == 1){
			frappe.model.set_value(cdt, cdn, 'amount', null);
		}
		else{
			frappe.model.set_value(cdt, cdn, 'formula', null);
		}
	}
})
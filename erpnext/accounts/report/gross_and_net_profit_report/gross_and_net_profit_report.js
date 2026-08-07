frappe.query_reports["Gross and Net Profit Report"] = $.extend({}, erpnext.financial_statements);

frappe.query_reports["Gross and Net Profit Report"]["filters"].push({
	fieldname: "accumulated_values",
	label: __("Accumulated Values"),
	fieldtype: "Check",
});

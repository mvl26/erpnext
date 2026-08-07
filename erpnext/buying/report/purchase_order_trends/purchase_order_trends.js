frappe.query_reports["Purchase Order Trends"] = $.extend({}, erpnext.purchase_trends_filters);

frappe.query_reports["Purchase Order Trends"]["filters"].push({
	fieldname: "include_closed_orders",
	label: __("Include Closed Orders"),
	fieldtype: "Check",
	default: 0,
});

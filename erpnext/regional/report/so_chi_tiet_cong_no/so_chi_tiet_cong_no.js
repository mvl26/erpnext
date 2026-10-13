// Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

frappe.query_reports["So Chi Tiet Cong No"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Công ty"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
		},
		{
			fieldname: "from_date",
			label: __("Từ ngày"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(frappe.datetime.get_today()),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("Đến ngày"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "party_type",
			label: __("Loại đối tác"),
			fieldtype: "Select",
			options: [
				{ value: "", label: "" },
				{ value: "Supplier", label: __("Nhà cung cấp (331)") },
				{ value: "Customer", label: __("Khách hàng (131)") },
			],
			on_change() {
				frappe.query_report.set_filter_value("party", "");
			},
		},
		{
			fieldname: "party",
			label: __("Đối tác"),
			fieldtype: "Dynamic Link",
			options: "party_type",
			depends_on: "eval:doc.party_type",
		},
	],
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (data && (data.is_opening || data.is_closing)) value = `<b>${value}</b>`;
		return value;
	},
};

// Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

frappe.query_reports["Doi Chieu Tong Cong No"] = {
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
			fieldname: "to_date",
			label: __("Kỳ đến ngày"),
			fieldtype: "Date",
			default: frappe.datetime.month_end(frappe.datetime.add_months(frappe.datetime.get_today(), -1)),
			reqd: 1,
		},
		{
			fieldname: "party_type",
			label: __("Loại đối tác"),
			fieldtype: "Select",
			options: [
				{ value: "Supplier", label: __("Nhà cung cấp (331)") },
				{ value: "Customer", label: __("Khách hàng (131)") },
			],
			default: "Supplier",
			reqd: 1,
		},
	],
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (data && data.bold) value = `<b>${value}</b>`;
		if (column.fieldname === "difference" && data && data.difference) {
			value = `<span style="color: var(--red-600)">${value}</span>`;
		}
		return value;
	},
};

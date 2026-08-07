// Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

frappe.query_reports["Doi Soat Hoa Don Dien Tu"] = {
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
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
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
			fieldname: "issue_type",
			label: __("Loại vấn đề"),
			fieldtype: "Select",
			options: ["", "Chưa xuất hóa đơn", "Chờ CQT quá 24 giờ", "Lỗi / cần đối soát"].join("\n"),
		},
	],

	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "issue_type" && data) {
			const colour = {
				"Chưa xuất hóa đơn": "orange",
				"Chờ CQT quá 24 giờ": "blue",
				"Lỗi / cần đối soát": "red",
			}[data.issue_type];
			if (colour) {
				value = `<span style="color:var(--text-on-${colour}, inherit)">${value}</span>`;
			}
		}
		return value;
	},
};

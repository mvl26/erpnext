// Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

frappe.query_reports["Tinh Trang Doi Chieu Cong No"] = {
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
			default: frappe.datetime.month_start(frappe.datetime.add_months(frappe.datetime.get_today(), -1)),
		},
		{
			fieldname: "to_date",
			label: __("Đến ngày"),
			fieldtype: "Date",
			default: frappe.datetime.month_end(frappe.datetime.add_months(frappe.datetime.get_today(), -1)),
		},
		{
			fieldname: "party_type",
			label: __("Loại đối tác"),
			fieldtype: "Select",
			options: ["", "Supplier", "Customer"],
		},
		{
			fieldname: "status",
			label: __("Trạng thái"),
			fieldtype: "Select",
			options: [
				"",
				"Nháp",
				"Đã duyệt",
				"Đã gửi",
				"Lỗi gửi",
				"Đã đối soát khớp",
				"Chênh lệch",
				"Đã xác nhận",
			],
		},
	],
};

// Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

// Khớp thứ tự với `TRANG_THAI` / `CHUA_KHOP` trong phan_bo.py; dòng đầu rỗng = mọi dòng.
const DCMB_TRANG_THAI = [
	"",
	"Khớp",
	"Chưa khớp (mọi loại)",
	"Thiếu đầu vào",
	"Lệch giá",
	"Lệch thuế suất",
	"Lệch ĐVT",
	"Trả hàng",
];

frappe.query_reports["Doi Chieu Mua Vao Ban Ra"] = {
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
			fieldname: "customer",
			label: __("Khách hàng"),
			fieldtype: "Link",
			options: "Customer",
			reqd: 1,
		},
		{
			fieldname: "from_date",
			label: __("Từ ngày (HĐ đầu ra)"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("Đến ngày (HĐ đầu ra)"),
			fieldtype: "Date",
			default: frappe.datetime.month_end(),
			reqd: 1,
		},
		{
			fieldname: "supplier",
			label: __("NCC"),
			fieldtype: "Link",
			options: "Supplier",
		},
		{
			fieldname: "trang_thai",
			label: __("Trạng thái"),
			fieldtype: "Select",
			options: DCMB_TRANG_THAI.join("\n"),
		},
		{
			fieldname: "ty_le_hd",
			label: __("Tỷ lệ giá hợp đồng"),
			fieldtype: "Float",
			precision: 4,
			default: 1.01,
		},
	],

	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (!data) return value;
		if (data.la_tong) return `<b>${value}</b>`;
		const lech = column.fieldname === "trang_thai" && data.trang_thai !== "Khớp";
		const am = typeof data[column.fieldname] === "number" && data[column.fieldname] < 0;
		return lech || am ? `<span style="color: var(--red-600)">${value}</span>` : value;
	},

	onload(report) {
		report.page.add_inner_button(__("Xuất Excel theo mẫu"), () => {
			const filters = report.get_values();
			if (!filters) return;
			const url =
				"/api/method/erpnext.accounts.report.doi_chieu_mua_vao_ban_ra.xuat_excel.xuat?filters=" +
				encodeURIComponent(JSON.stringify(filters));
			window.open(frappe.urllib.get_full_url(url));
		});
	},
};

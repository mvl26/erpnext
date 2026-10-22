frappe.query_reports["Doi Soat Gia Mua Gia Ban"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Công ty"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "from_date",
			label: __("Từ ngày"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
		},
		{
			fieldname: "to_date",
			label: __("Đến ngày"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
		{ fieldname: "customer", label: __("Khách hàng"), fieldtype: "Link", options: "Customer" },
		{ fieldname: "supplier", label: __("NCC"), fieldtype: "Link", options: "Supplier" },
		{ fieldname: "item_code", label: __("Mặt hàng"), fieldtype: "Link", options: "Item" },
		{ fieldname: "chi_lech", label: __("Chỉ dòng lệch / khác bảng giá"), fieldtype: "Check" },
		{ fieldname: "gom_nhap", label: __("Gồm SO nháp"), fieldtype: "Check" },
	],
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "trang_thai_gia" && data) {
			const color =
				{
					"Khớp": "green",
					"Thấp hơn": "red",
					"Cao hơn": "orange",
					"Chưa có giá mua": "red",
					"Đang trong thời hạn báo giá": "blue",
				}[data.trang_thai_gia] || "gray";
			value = `<span class="indicator-pill ${color}">${value}</span>`;
		}
		return value;
	},
};

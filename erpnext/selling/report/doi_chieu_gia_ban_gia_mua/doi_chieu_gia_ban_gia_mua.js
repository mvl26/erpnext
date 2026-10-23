frappe.query_reports["Doi Chieu Gia Ban Gia Mua"] = {
	filters: [
		{
			fieldname: "price_list",
			label: __("Bảng giá bán"),
			fieldtype: "Link",
			options: "Price List",
			reqd: 1,
			get_query: () => ({ filters: { selling: 1 } }),
		},
		{
			fieldname: "ngay",
			label: __("Tại ngày"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "customer",
			label: __("Khách (lấy hệ số; trống: khách dùng bảng giá này)"),
			fieldtype: "Link",
			options: "Customer",
		},
		{
			fieldname: "he_so",
			label: __("Hệ số (để trống: theo khách)"),
			fieldtype: "Float",
		},
		{
			fieldname: "item_group",
			label: __("Nhóm hàng"),
			fieldtype: "Link",
			options: "Item Group",
		},
		{
			fieldname: "chi_hien_lech",
			label: __("Chỉ hiện dòng lệch"),
			fieldtype: "Check",
		},
	],
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "trang_thai" && data) {
			const color =
				{
					Khớp: "green",
					"Thấp hơn": "red",
					"Cao hơn": "orange",
					"Chưa có giá mua": "red",
				}[data.trang_thai] || "gray";
			value = `<span class="indicator-pill ${color}">${value}</span>`;
		}
		return value;
	},
};

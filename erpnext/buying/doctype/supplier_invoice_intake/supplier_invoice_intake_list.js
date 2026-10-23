frappe.listview_settings["Supplier Invoice Intake"] = {
	add_fields: ["trang_thai"],
	get_indicator(doc) {
		const mau = {
			"Mới tiếp nhận": "gray",
			"Đã trích xuất": "blue",
			"Đã đối soát": "green",
			"Chờ xử lý thủ công": "orange",
			"Đã tạo nháp hóa đơn mua": "blue",
			"Đã ghi sổ": "green",
			"Từ chối": "red",
		};
		return [__(doc.trang_thai), mau[doc.trang_thai] || "gray", "trang_thai,=," + doc.trang_thai];
	},
};

frappe.listview_settings["Supplier Item Alias"] = {
	add_fields: ["trang_thai"],
	get_indicator(doc) {
		const mau = { "Chờ duyệt": "orange", "Đang dùng": "green", "Ngừng dùng": "gray" };
		return [__(doc.trang_thai), mau[doc.trang_thai] || "gray", "trang_thai,=," + doc.trang_thai];
	},
	onload(listview) {
		const doi = (trang_thai) => {
			const ten = listview.get_checked_items(true);
			if (!ten.length) return frappe.msgprint(__("Chọn ít nhất một dòng."));
			frappe
				.xcall("erpnext.buying.tiep_nhan_hoa_don.anh_xa.doi_trang_thai", {
					ten: JSON.stringify(ten),
					trang_thai,
				})
				.then((n) => {
					frappe.show_alert({ message: __("Đã cập nhật {0} dòng", [n]), indicator: "green" });
					listview.refresh();
				});
		};
		listview.page.add_action_item(__("Duyệt"), () => doi("Đang dùng"));
		listview.page.add_action_item(__("Ngừng dùng"), () => doi("Ngừng dùng"));
	},
};

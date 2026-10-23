// Bảng ánh xạ tên (Đợt 4): nút Duyệt / Ngừng dùng. Server kiểm vai trò duyệt ánh xạ.
frappe.ui.form.on("Supplier Item Alias", {
	refresh(frm) {
		if (frm.is_new()) return;
		const doi = (trang_thai) =>
			frappe
				.xcall("erpnext.buying.tiep_nhan_hoa_don.anh_xa.doi_trang_thai", {
					ten: frm.doc.name,
					trang_thai,
				})
				.then(() => frm.reload_doc());
		if (frm.doc.trang_thai !== "Đang dùng") {
			frm.add_custom_button(__("Duyệt"), () => doi("Đang dùng")).addClass("btn-primary");
		}
		if (frm.doc.trang_thai !== "Ngừng dùng") {
			frm.add_custom_button(__("Ngừng dùng"), () => doi("Ngừng dùng"));
		}
	},
});

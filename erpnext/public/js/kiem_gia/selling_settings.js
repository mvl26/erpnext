// Mục kiểm giá bán (BA12): chỉ vai trò đang chọn ở "Vai trò được sửa hệ số giá bán" được sửa.
frappe.ui.form.on("Selling Settings", {
	refresh(frm) {
		frappe
			.xcall("erpnext.selling.kiem_gia.cau_hinh.co_quyen_sua_ty_le_lai", {
				vai_tro: frm.doc.vai_tro_sua_ty_le_lai,
			})
			.then((ok) => {
				["bat_kiem_gia_ban", "bat_buoc_dinh_kem_van_ban_gia", "vai_tro_sua_ty_le_lai"].forEach((f) =>
					frm.set_df_property(f, "read_only", ok ? 0 : 1)
				);
			});
	},
});

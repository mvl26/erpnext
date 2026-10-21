frappe.ui.form.on("Selling Settings", {
	refresh(frm) {
		// Mục kiểm giá bán: chỉ vai trò đang được chọn ở "Vai trò được sửa % lãi" được sửa.
		frappe
			.xcall("erpnext.selling.kiem_gia.cau_hinh.co_quyen_sua_ty_le_lai", {
				vai_tro: frm.doc.vai_tro_sua_ty_le_lai,
			})
			.then((ok) => {
				[
					"bat_kiem_gia_ban",
					"che_do_kiem_gia",
					"ty_le_lai_mac_dinh",
					"vai_tro_sua_ty_le_lai",
					"vai_tro_duyet_gia_lech",
				].forEach((f) => frm.set_df_property(f, "read_only", ok ? 0 : 1));
			});
	},
	after_save(frm) {
		frappe.boot.user.defaults.editable_price_list_rate = frm.doc.editable_price_list_rate;
	},
});

// Giá mặt hàng: chọn bảng giá mua riêng của một NCC (Nhà cung cấp → Bảng giá mặc định) thì tự
// điền NCC đó. Giá mua HĐ nguyên tắc được nhận theo ô Nhà cung cấp, không theo tên bảng giá;
// lưu với NCC khác thì server chặn (gia_goc.kiem_ncc_item_price).
frappe.ui.form.on("Item Price", {
	price_list(frm) {
		if (!frm.doc.price_list) return;
		frappe
			.xcall("erpnext.selling.kiem_gia.gia_goc.lay_ncc_cua_bang_gia", {
				price_list: frm.doc.price_list,
			})
			.then((ncc) => {
				if (ncc && frm.doc.supplier !== ncc) frm.set_value("supplier", ncc);
			});
	},
});

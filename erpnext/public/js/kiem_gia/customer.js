// Hệ số giá bán theo khách hàng (BA12 R01). Chỉ vai trò ở Selling Settings > "Vai trò được
// sửa hệ số giá bán" được sửa (server cũng chặn). Có hệ số theo khách thì bảng hệ số theo
// mặt hàng bị khóa và không được áp.
frappe.ui.form.on("Customer", {
	refresh(frm) {
		frm.fields_dict.he_so_gia_ban.grid.update_docfield_property("item_code", "hidden", 1);
		frm.fields_dict.he_so_gia_ban.grid.update_docfield_property("so_hop_dong", "reqd", 1);
		frm.fields_dict.he_so_theo_mat_hang.grid.update_docfield_property("item_code", "reqd", 1);
		frappe.xcall("erpnext.selling.kiem_gia.cau_hinh.co_quyen_sua_ty_le_lai").then((ok) => {
			frm.__co_quyen_he_so = ok;
			erpnext.kiem_gia.khoa_he_so(frm);
		});
	},
});

frappe.ui.form.on("Customer Price Coefficient", {
	he_so_gia_ban_add: (frm) => erpnext.kiem_gia.khoa_he_so(frm),
	he_so_gia_ban_remove: (frm) => erpnext.kiem_gia.khoa_he_so(frm),
});

frappe.provide("erpnext.kiem_gia");
erpnext.kiem_gia.khoa_he_so = function (frm) {
	const ok = frm.__co_quyen_he_so;
	const co_he_so_chung = (frm.doc.he_so_gia_ban || []).length > 0;
	frm.set_df_property("he_so_gia_ban", "read_only", ok ? 0 : 1);
	frm.set_df_property("he_so_theo_mat_hang", "read_only", ok && !co_he_so_chung ? 0 : 1);
};

// Báo trước khi đổi giá (YC4): xem giá chờ và gửi thông báo đổi giá. Chỉ Giám đốc gửi được;
// server kiểm quyền.
frappe.ui.form.on("Price List", {
	refresh(frm) {
		if (!frm.doc.bao_truoc_khi_doi_gia || !frm.doc.bang_gia_cho || frm.is_dirty()) return;
		frm.add_custom_button(__("Giá chờ gửi"), () => {
			frappe.route_options = { price_list: frm.doc.bang_gia_cho };
			frappe.set_route("List", "Item Price");
		});
		frappe.xcall("erpnext.selling.kiem_gia.cau_hinh.co_quyen_sua_ty_le_lai").then((ok) => {
			if (!ok) return;
			frm.add_custom_button(__("Gửi thông báo đổi giá"), () => {
				frappe.confirm(
					__("Gửi email báo giá mới cho {0} và chuyển mọi giá chờ sang bảng giá này?", [
						frm.doc.email_nhan_thong_bao,
					]),
					() =>
						frappe
							.xcall("erpnext.selling.kiem_gia.bao_truoc.gui_thong_bao_doi_gia", {
								price_list: frm.doc.name,
							})
							.then((r) => {
								frappe.show_alert({
									message: __("Đã gửi thông báo: {0} giá", [r.so_dong]),
									indicator: "green",
								});
								frm.reload_doc();
							})
				);
			});
		});
	},
});

frappe.ui.form.on("Price List", {
	refresh: function (frm) {
		let me = this;
		frm.add_custom_button(
			__("Add / Edit Prices"),
			function () {
				frappe.route_options = {
					price_list: frm.doc.name,
				};
				frappe.set_route("Report", "Item Price");
			},
			"fa fa-money"
		);
		if (frm.doc.bao_truoc_khi_doi_gia && frm.doc.bang_gia_cho && !frm.is_dirty()) {
			// Miyano (YC4): chỉ Giám đốc gửi được; server kiểm quyền.
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
		}
	},
});

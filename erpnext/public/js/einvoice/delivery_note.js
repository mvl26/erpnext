// Copyright (c) 2026, Công ty TNHH Miyano Việt Nam
//
// Hóa đơn điện tử nhìn từ phiếu giao hàng — **chỉ xem** (đặc tả bản 3.0, mục C5).
//
// Từ bản 3.0 hóa đơn gốc chỉ lập từ hóa đơn bán: phiếu giao không còn nút tạo.
// Hai đường phát hành cùng sống là nguy cơ một lần bán ra hai số hóa đơn, vì Key
// của hai đường khác nhau nên Fast không nhận ra trùng (nguyên tắc A4 thứ năm).
// Form chỉ cho thấy hóa đơn điện tử của phiếu này — lập theo bản 2.0, hoặc suy
// ra qua hóa đơn bán — và chỉ đường sang hóa đơn bán.

frappe.ui.form.on("Delivery Note", {
	async refresh(frm) {
		if (frm.is_new() || frm.doc.docstatus !== 1) return;

		const { message: state } = await frappe.call({
			method: "erpnext.einvoice.form_state.get_delivery_note_state",
			args: { delivery_note: frm.doc.name },
		});
		if (!state) return;

		for (const doc of state.documents || []) {
			frm.add_custom_button(
				__("Mở {0}", [doc.name]),
				() => frappe.set_route("Form", "Fast EInvoice Document", doc.name),
				__("Hóa đơn điện tử")
			);
		}

		if (state.message) {
			frm.dashboard.add_comment(state.message, state.colour || "blue", true);
		}
	},
});

// Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

frappe.ui.form.on("TBYT Regulatory Document", {
	onload(frm) {
		// Nút "Tải chứng từ lên" trên form Số lưu hành (và bất kỳ nút tương tự nào
		// sau này ở cấp phạm vi khác) đặt sẵn `frappe.tbyt_pending_scope` trước khi
		// gọi `frappe.new_doc()`. KHÔNG dùng `frappe.route_options` cho việc này:
		// Frappe tự đặt nó về null trong `frappe.model.get_new_doc()` trước khi
		// trang New kịp render và bắn `onload`, nên tới đây route_options đã trống —
		// bảng con luôn phải điền tay ở onload, và phải điền từ một kênh sống sót
		// được tới lúc này.
		if (frappe.tbyt_pending_scope && !(frm.doc.pham_vi || []).length) {
			frm.add_child("pham_vi", frappe.tbyt_pending_scope);
			frm.refresh_field("pham_vi");
			delete frappe.tbyt_pending_scope;
		}
	},
});

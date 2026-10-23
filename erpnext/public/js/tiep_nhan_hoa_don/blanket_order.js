// Hợp đồng khung (Đợt 4): ô Bảng giá mua chỉ chọn bảng giá mua. Server cũng kiểm.
frappe.ui.form.on("Blanket Order", {
	setup(frm) {
		frm.set_query("bang_gia_mua", () => ({ filters: { buying: 1 } }));
	},
});

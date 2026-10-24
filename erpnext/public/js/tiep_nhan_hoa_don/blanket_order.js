// Hợp đồng khung (Đợt 4): ô Bảng giá mua chỉ chọn bảng giá mua; ô Phụ lục của hợp đồng chỉ chọn hợp
// đồng khung mua đã Nộp của cùng nhà cung cấp. Server cũng kiểm.
frappe.ui.form.on("Blanket Order", {
	setup(frm) {
		frm.set_query("bang_gia_mua", () => ({ filters: { buying: 1 } }));
		frm.set_query("hop_dong_goc", () => ({
			filters: {
				blanket_order_type: "Purchasing",
				supplier: frm.doc.supplier,
				docstatus: 1,
				name: ["!=", frm.doc.name],
			},
		}));
	},
});

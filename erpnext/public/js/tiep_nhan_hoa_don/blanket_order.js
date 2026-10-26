// Hợp đồng khung (Đợt 4): ô Bảng giá mua chỉ chọn bảng giá mua; ô Phụ lục của hợp đồng chỉ chọn hợp
// đồng khung mua đã Nộp của cùng nhà cung cấp. Server cũng kiểm.
// Hủy hợp đồng đã có chứng từ dùng nó thì phải bị chặn: không mở hộp "Hủy tất cả chứng từ" của
// Frappe (bấm nhầm là hủy luôn Đơn mua, Hóa đơn mua, phụ lục).
frappe.ui.form.on("Blanket Order", {
	setup(frm) {
		frm.ignore_doctypes_on_cancel_all = [
			"Purchase Order",
			"Purchase Receipt",
			"Purchase Invoice",
			"Supplier Quotation",
			"Sales Order",
			"Quotation",
			"Blanket Order",
		];
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
	refresh(frm) {
		// Gia hạn (sửa Đến ngày sau khi Nộp) chỉ dành cho người được Nộp: người khác thấy ô khóa.
		if (frm.doc.docstatus === 1 && !frm.perm[0].submit) frm.set_df_property("to_date", "read_only", 1);
	},
});

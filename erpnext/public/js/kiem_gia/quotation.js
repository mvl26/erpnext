// Kiểm giá bán trên Báo giá: chỉ tô màu "Trạng thái giá" của dòng (trang_thai_gia.js).
frappe.ui.form.on("Quotation", {
	setup: () => erpnext.kiem_gia.to_mau_trang_thai_gia("Quotation Item"),
});

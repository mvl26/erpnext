// Kiểm giá bán (BA12): nút "Áp giá đề xuất" — D06, giá theo hệ số được ưu tiên hơn bảng giá.
// Giá đề xuất được tính khi lưu; nút chép giá đề xuất vào đơn giá của các dòng còn lệch.
frappe.ui.form.on("Sales Order", {
	refresh(frm) {
		const lech = (frm.doc.items || []).filter(
			(d) => d.gia_de_xuat && ["Thấp hơn", "Cao hơn"].includes(d.trang_thai_gia)
		);
		if (frm.doc.docstatus !== 0 || !lech.length) return;
		frm.add_custom_button(__("Áp giá đề xuất"), () => {
			lech.forEach((d) => frappe.model.set_value(d.doctype, d.name, "rate", d.gia_de_xuat));
			frappe.show_alert({
				message: __("Đã áp giá đề xuất cho {0} dòng. Lưu để kiểm lại.", [lech.length]),
				indicator: "blue",
			});
		});
	},
});

// Kiểm giá bán (BA12): nút "Áp giá đề xuất" — D06, giá theo hệ số được ưu tiên hơn bảng giá.
// Giá đề xuất được tính khi lưu; nút chép giá đề xuất vào đơn giá của các dòng còn lệch.
// Q10: SO đã Submit còn dòng chờ khách chấp thuận giá thì nhắc ngay đầu form.
frappe.ui.form.on("Sales Order", {
	setup: () => erpnext.kiem_gia.to_mau_trang_thai_gia("Sales Order Item"),
	refresh(frm) {
		const cho = (frm.doc.items || []).filter((d) => d.cho_chap_thuan);
		if (frm.doc.docstatus === 1 && cho.length) {
			frm.set_intro(
				__(
					"Dòng {0} chờ khách chấp thuận giá: mở dòng, nhập số văn bản, người đại diện KH, ngày chấp thuận rồi bấm Cập nhật. Chưa nhập thì chưa tạo được Phiếu giao hàng / Hóa đơn bán cho các dòng này.",
					[cho.map((d) => `${d.idx} (${frappe.utils.escape_html(d.item_code)})`).join(", ")]
				),
				"orange"
			);
		}
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

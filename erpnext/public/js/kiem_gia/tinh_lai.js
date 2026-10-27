// Kiểm giá bán (BA12) trên Báo giá / Đơn bán hàng: đổi NCC dự kiến, mặt hàng, đơn giá, ĐVT,
// khách hoặc ngày thì kiểm lại ngay, không đợi lưu (trước đây đổi NCC vẫn thấy giá mua của NCC
// cũ tới lúc lưu). Đơn bán hàng đã Submit: chỉ đổi được NCC dự kiến, server kiểm lại đúng dòng
// đó. Server tính trên bản đang sửa và không ghi gì; lưu / Cập nhật vẫn kiểm lại.
frappe.provide("erpnext.kiem_gia");

erpnext.kiem_gia.hen_tinh_lai = function (frm) {
	if (frm.doc.docstatus === 2) return;
	clearTimeout(frm.__kiem_gia_hen);
	// Đợi form tính xong đơn giá / net_rate của dòng (cũng chạy theo sự kiện đổi trường).
	frm.__kiem_gia_hen = setTimeout(() => erpnext.kiem_gia.tinh_lai(frm), 500);
};

erpnext.kiem_gia.tinh_lai = function (frm) {
	const lan = (frm.__kiem_gia_lan = (frm.__kiem_gia_lan || 0) + 1);
	const docstatus = frm.doc.docstatus;
	const rong = (v) => (v === undefined || v === "" ? null : v);
	return frappe.xcall("erpnext.selling.kiem_gia.kiem_chung_tu.tinh_lai", { doc: frm.doc }).then((kq) => {
		// Có lần tính mới hơn, hoặc form đã lưu / mở chứng từ khác: bỏ kết quả này.
		if (lan !== frm.__kiem_gia_lan || frm.doc.docstatus !== docstatus || !kq) return;
		let doi = false;
		for (const d of frm.doc.items || []) {
			for (const [f, v] of Object.entries(kq[d.name] || {})) {
				if (rong(d[f]) === rong(v)) continue;
				d[f] = v;
				doi = true;
			}
		}
		if (doi) {
			frm.dirty();
			frm.refresh_field("items");
		}
		frm.trigger("kiem_gia_tinh_xong");
	});
};

for (const [dt, khach] of [
	["Quotation", "party_name"],
	["Sales Order", "customer"],
]) {
	frappe.ui.form.on(dt, {
		// Sau khi lưu / tải lại: kết quả đang chờ là của bản cũ.
		refresh(frm) {
			clearTimeout(frm.__kiem_gia_hen);
			frm.__kiem_gia_lan = (frm.__kiem_gia_lan || 0) + 1;
		},
		[khach]: erpnext.kiem_gia.hen_tinh_lai,
		transaction_date: erpnext.kiem_gia.hen_tinh_lai,
	});
	frappe.ui.form.on(`${dt} Item`, {
		item_code(frm, cdt, cdn) {
			// NCC dự kiến là của mặt hàng cũ: bỏ để lấy NCC mặc định của mặt hàng mới.
			if (locals[cdt][cdn].ncc_du_kien) frappe.model.set_value(cdt, cdn, "ncc_du_kien", null);
			erpnext.kiem_gia.hen_tinh_lai(frm);
		},
		ncc_du_kien: erpnext.kiem_gia.hen_tinh_lai,
		rate: erpnext.kiem_gia.hen_tinh_lai,
		conversion_factor: erpnext.kiem_gia.hen_tinh_lai,
	});
}

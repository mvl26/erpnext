// Nút "In nhãn" ngay trên form `Batch` — in LẠI đúng con tem của một lô.
//
// Gắn qua `doctype_js` trong `erpnext/hooks.py`, KHÔNG sửa
// `erpnext/stock/doctype/batch/batch.js` của upstream — cùng lý lẽ đã ghi ở
// `public/js/vi_tri_kho/warehouse.js`: bớt một điểm xung đột mỗi lần merge, mà
// kết quả y hệt.
//
// VÌ SAO CẦN NÚT NÀY khi `Batch Entry` đã in cả xấp: tem rách, tem dán nhầm
// thùng, thùng bị tách ra làm hai. Lúc đó người ta cầm số lô trong tay chứ
// không nhớ phiếu nhập lô nào đã tạo nó. `dat_o_in_tem` là bất biến theo lần
// gọi (§6.5) nên tem in lại ở đây RA ĐÚNG tờ giấy như lần in đầu — kể cả khi
// dữ liệu kho đã đổi. Đó là điều kiện để nút này an toàn; không có bất biến đó
// thì in lại là đẻ ra hai tờ tem nói hai chỗ khác nhau cho cùng một thùng hàng.

const DUONG_IN_NHAN = "/assets/erpnext/js/vi_tri_kho/in_nhan_lo.js";

frappe.ui.form.on("Batch", {
	refresh(frm) {
		// Bản ghi chưa lưu thì chưa có `Batch` nào trong CSDL để `dat_o_in_tem`
		// / `du_lieu_tem` đọc — bấm sẽ ra `DoesNotExistError` thô.
		if (frm.is_new() || !frm.doc.item) return;

		// Mặt hàng không bật "Có lô" vẫn có thể còn lô cũ nằm lại (ai đó tắt cờ
		// sau khi đã nhập hàng). In tem cho nó là dán một con tem lô lên thứ hệ
		// không còn theo dõi theo lô — mã vạch quét ra một lô mà mọi phiếu kho
		// sau này đều bỏ qua. `frappe.db.get_value` có bộ đệm phía client nên
		// đây không phải một lượt đi mạng mỗi lần refresh.
		frappe.db.get_value("Item", frm.doc.item, "has_batch_no").then((r) => {
			if (!r || !r.message || !r.message.has_batch_no) return;
			frm.add_custom_button(__("In nhãn"), () => in_nhan(frm));
		});
	},
});

function in_nhan(frm) {
	frappe.require(DUONG_IN_NHAN, () => {
		// Một lô — một nhãn. Cùng đúng đường ba bước với "In nhãn cả phiếu"
		// (xem `in_nhan_lo.js`), nên không có cách nào để hai màn hình in ra
		// hai con tem khác nhau cho cùng một lô.
		erpnext.vi_tri_kho.in_nhan.in_cho_cac_lo([frm.doc.name]);
	});
}

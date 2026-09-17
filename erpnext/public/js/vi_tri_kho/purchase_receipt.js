// Nút "Nhập lô & in nhãn" trên phiếu nhập kho.
//
// VÌ SAO CÓ FILE NÀY: chủ đầu tư thử luồng thật ngày 17/09/2026 và phiếu nhập
// MAT-PRE-2026-00008 được DUYỆT với số lô `17/09/2026` — một ngày tháng gõ thẳng
// vào ô lô chuẩn của ERPNext. Phiếu nhập lô (`Batch Entry`) không có lối vào nào
// từ phiếu nhập, nên đường tự nhiên nhất là gõ lô ngay trên phiếu rồi duyệt, bỏ
// qua phiếu nhập lô hoàn toàn: số lô nhà cung cấp mất, không có tem. Lời chủ đầu
// tư: "phải có nút tạo batch entry từ phiếu nhập kho thì mới đúng luồng".
//
// Gắn qua `doctype_js` trong `hooks.py`, không sửa `purchase_receipt.js` gốc —
// cùng cách module này đã làm với Warehouse và Batch, bớt một điểm xung đột mỗi
// lần merge bản ERPNext mới.
//
// Nhãn nút PHẢI khớp từng chữ `NHAN_NUT_NHAP_LO` ở `vitri/phieu_nhap.py`: câu báo
// chặn duyệt phiếu bảo người dùng "bấm nút <tên này>", lệch một chữ là thủ kho đi
// tìm một nút không tồn tại. `vi_tri_kho/tests/test_giao_dien.py` khoá việc đó.

const NHAN_NUT_NHAP_LO = "Nhập lô & in nhãn";
const PHUONG_THUC_CHAN_DOAN = "erpnext.vi_tri_kho.vitri.phieu_nhap.chan_doan_phieu_nhap";

frappe.ui.form.on("Purchase Receipt", {
	refresh(frm) {
		if (frm.doc.docstatus === 0) {
			// Hiện trên MỌI phiếu nháp, kể cả phiếu chưa lưu, chứ không hỏi máy chủ
			// trước xem có dòng nào cần khai lô không: phiếu chưa lưu thì chưa có
			// tên để hỏi, mà `refresh` cũng không chạy lại khi người dùng thêm dòng
			// hàng. Ẩn nút đi là để thủ kho thêm xong dòng rồi ngồi nhìn một phiếu
			// không có nút — đúng lỗi đã gặp trên `batch_entry.js`. Việc "có gì để
			// khai không" hỏi lúc BẤM, và câu trả lời nói rõ vì sao.
			frm.add_custom_button(__(NHAN_NUT_NHAP_LO), () => nhap_lo(frm));
			return;
		}

		if (frm.doc.docstatus === 1) {
			// Phiếu đã duyệt không khai lô được nữa — chỉ còn đường XEM phiếu nhập
			// lô đã làm cho nó (để in lại tem).
			frappe.call({ method: PHUONG_THUC_CHAN_DOAN, args: { phieu_nhap: frm.doc.name } }).then((r) => {
				const cd = r.message || {};
				const phieu = cd.phieu_nhap_lo || [];
				if (!phieu.length) return;
				frm.add_custom_button(__("Xem phiếu nhập lô"), () => {
					if (phieu.length === 1) {
						frappe.set_route("Form", "Batch Entry", phieu[0]);
					} else {
						frappe.set_route("List", "Batch Entry", { phieu_nhap: frm.doc.name });
					}
				});
			});
		}
	},
});

function nhap_lo(frm) {
	const tiep = () =>
		frappe.call({ method: PHUONG_THUC_CHAN_DOAN, args: { phieu_nhap: frm.doc.name } }).then((r) => {
			const cd = r.message || {};

			// Đã có phiếu nhập lô NHÁP cho phiếu này → mở lại nó, không tạo phiếu
			// thứ hai. Hai phiếu nháp cùng trỏ một phiếu nhập là hai chỗ gõ số lô
			// cho cùng một dòng hàng.
			if (cd.phieu_nhap_lo_nhap) {
				frappe.set_route("Form", "Batch Entry", cd.phieu_nhap_lo_nhap);
				return;
			}

			if (!cd.dong_can_khai) {
				frappe.msgprint({
					title: __("Không có dòng nào cần khai lô"),
					message: cd.cau_bao,
					indicator: (cd.dong_go_tay || []).length ? "orange" : "blue",
				});
				return;
			}

			// `batch_entry.js` tự nạp dòng hàng khi thấy một phiếu mới đã mang
			// sẵn `phieu_nhap` mà bảng con còn trống.
			frappe.new_doc("Batch Entry", { phieu_nhap: frm.doc.name });
		});

	// Phiếu chưa lưu hoặc đang sửa dở: lưu trước. Phiếu nhập lô trỏ tới phiếu
	// nhập bằng TÊN và nạp dòng theo TÊN DÒNG — cả hai chỉ có sau khi lưu; và
	// nạp theo bản đã lưu trong khi màn hình đang có dòng chưa lưu là nạp thiếu.
	if (frm.is_new() || frm.is_dirty()) {
		frm.save().then(tiep);
	} else {
		tiep();
	}
}

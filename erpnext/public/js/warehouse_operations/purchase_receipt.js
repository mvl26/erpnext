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
// tìm một nút không tồn tại. `warehouse_operations/tests/test_giao_dien.py` khoá việc đó.

const NHAN_NUT_NHAP_LO = "Nhập lô & in nhãn";
const NHAN_NUT_XEP = "Xếp hàng lên kệ";
const PHUONG_THUC_CHAN_DOAN = "erpnext.warehouse_operations.vitri.phieu_nhap.chan_doan_phieu_nhap";
const PHUONG_THUC_TIEN_DO = "erpnext.warehouse_operations.vitri.luong_nhap.tien_do_nhap_kho";

frappe.ui.form.on("Purchase Receipt", {
	refresh(frm) {
		ve_tien_do(frm);
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

// ------------------------------------------------------- thanh tiến trình luồng
//
// Chủ đầu tư 23/09/2026: "có sự liên kết luồng … sau khi submit purchase receipt
// thì có xếp hàng lên kệ nữa". Trước bản vá, mỗi bước là một màn hình rời và
// không màn nào nói bước sau là gì — thủ kho gõ lại tên chứng từ trên thanh tìm
// kiếm để đi tiếp.
//
// Cùng khuôn với thanh "Lấy hàng" của phiếu giao (`delivery_note.js`): vẽ NGAY
// TRÊN bảng dòng hàng chứ không dùng `set_headline_alert` (form chỉ có một ô
// thông báo đầu trang, `batch.js`/ERPNext cũng dùng — câu sau đè câu trước) và
// không dùng `frm.dashboard.add_progress` (ở v15 nó nằm trong tab Connections,
// người mở phiếu ở tab Details không bao giờ thấy).

function xoa_tien_do(frm) {
	$(frm.wrapper).find(".vtk-luong-nhap").remove();
}

function ve_tien_do(frm) {
	xoa_tien_do(frm);
	if (frm.is_new()) return;
	frappe.xcall(PHUONG_THUC_TIEN_DO, { phieu_nhap: frm.doc.name }).then((t) => {
		// Người dùng có thể đã sang phiếu khác trong lúc chờ.
		if (!t || frm.doc.name !== frm.docname || frm.is_new()) return;
		if (t.trang_thai === "cho_xep") {
			frm.add_custom_button(__(NHAN_NUT_XEP), () => xep_len_ke(frm, t));
		}
		hien_tien_do(frm, t);
	});
}

function hien_tien_do(frm, t) {
	const e = frappe.utils.escape_html;
	const kho = (t.kho_quan_ly || []).map(e).join(", ");
	let chu = null;
	let mau = "blue";
	switch (t.trang_thai) {
		case "can_khai_lo":
			chu = __("Còn {0} dòng chưa khai lô — bấm <b>{1}</b> để gõ số lô nhà cung cấp và in tem.", [
				t.dong_can_khai,
				e(NHAN_NUT_NHAP_LO),
			]);
			mau = "orange";
			break;
		case "khai_du_cho_duyet":
			chu = __("Đã khai lô đủ các dòng ({0}) — bấm <b>Submit</b> để ghi kho.", [kho]);
			break;
		case "cho_xep":
			// Ô "Chưa xếp vị trí" là ô DÙNG CHUNG của kho: con số này là tồn của
			// đúng các (kho, mặt hàng, lô) trên phiếu này, nên nếu lô đó còn hàng
			// của phiếu nhập khác thì nó tính chung. Câu chữ vì thế không hứa
			// "đúng bằng số của phiếu này".
			chu = __("Hàng đã vào kho nhưng còn <b>{0}</b> đang ở ô <b>Chưa xếp vị trí</b> — bấm <b>{1}</b>.", [
				so(t.tong_chua_xep),
				e(NHAN_NUT_XEP),
			]);
			mau = "orange";
			break;
		case "da_xep":
			chu = __("Đã xếp hết lên kệ — không còn gì ở ô Chưa xếp vị trí.");
			mau = "green";
			break;
		case "da_huy":
			chu = __("Phiếu đã huỷ.");
			mau = "red";
			break;
	}
	if (!chu) return; // `khong_ap_dung`: phiếu không có dòng nào ở kho quản lý vị trí
	const f = frm.fields_dict.items;
	if (!f || !f.$wrapper) return;
	$(`
		<div class="vtk-luong-nhap" style="margin-bottom: var(--margin-md);">
			<div class="d-flex align-items-center" style="gap: 8px;">
				<span class="indicator-pill ${mau}">${__("Luồng nhập kho")}</span>
				<span class="small">${chu}</span>
			</div>
		</div>
	`).insertBefore(f.$wrapper);
}

// Nút "Xếp hàng lên kệ": mở phiếu xếp NHÁP, điền sẵn kho, và bật cờ để
// `location_transfer.js` tự bấm "Lấy hàng chưa xếp" hộ.
//
// Phiếu xếp đó lấy CẢ KHO (mọi thứ đang chờ ở ô Chưa xếp), không riêng hàng của
// phiếu nhập này — chủ đầu tư chốt 23/09/2026 ("lấy cả kho"). Đúng việc hơn:
// hàng chờ ở ô chưa xếp là hàng chờ, bất kể phiếu nào đưa vào.
function xep_len_ke(frm, t) {
	const kho_ds = Object.keys(t.chua_xep_theo_kho || {});
	if (!kho_ds.length) return;
	if (kho_ds.length === 1) return mo_phieu_xep(kho_ds[0]);

	const d = new frappe.ui.Dialog({
		title: __("Xếp hàng lên kệ"),
		fields: [
			{
				fieldtype: "Select",
				fieldname: "kho",
				label: __("Kho"),
				options: kho_ds.join("\n"),
				default: kho_ds[0],
				reqd: 1,
			},
		],
		primary_action_label: __("Mở phiếu xếp"),
		primary_action: (v) => {
			d.hide();
			mo_phieu_xep(v.kho);
		},
	});
	d.show();
}

function mo_phieu_xep(kho) {
	frappe.provide("erpnext.warehouse_operations");
	erpnext.warehouse_operations.tu_lay_hang_chua_xep = kho;
	frappe.new_doc("Location Transfer", { kho });
}

function so(x) {
	return frappe.utils.escape_html(flt(x).toLocaleString("vi-VN", { maximumFractionDigits: 3 }));
}

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

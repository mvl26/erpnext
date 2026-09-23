// Nút "In nhãn" ngay trên form `Batch` — in LẠI đúng con tem của một lô.
//
// Gắn qua `doctype_js` trong `erpnext/hooks.py`, KHÔNG sửa
// `erpnext/stock/doctype/batch/batch.js` của upstream — cùng lý lẽ đã ghi ở
// `public/js/warehouse_operations/warehouse.js`: bớt một điểm xung đột mỗi lần merge, mà
// kết quả y hệt.
//
// VÌ SAO CẦN NÚT NÀY khi `Batch Entry` đã in cả xấp: tem rách, tem dán nhầm
// thùng, thùng bị tách ra làm hai. Lúc đó người ta cầm số lô trong tay chứ
// không nhớ phiếu nhập lô nào đã tạo nó. `dat_o_in_tem` là bất biến theo lần
// gọi (§6.5) nên tem in lại ở đây RA ĐÚNG tờ giấy như lần in đầu — kể cả khi
// dữ liệu kho đã đổi. Đó là điều kiện để nút này an toàn; không có bất biến đó
// thì in lại là đẻ ra hai tờ tem nói hai chỗ khác nhau cho cùng một thùng hàng.

//
// NÚT "Đặt / Đổi ô trên tem" (19/09/2026): luật mới "chỉ xếp lô vào đúng ô in
// trên tem" (`vitri/o_tem.py`) biến ô trên tem thành thứ quyết định hàng được
// nằm ở đâu. Lô chưa có ô, ô trên tem hỏng, hay cần dời hàng sang chỗ khác —
// đều đi qua nút này rồi IN LẠI TEM. Lô chưa có ô: thủ kho đặt được. Đổi ô đã
// có: chỉ trưởng kho (máy chủ kiểm, nút chỉ ẩn/hiện cho đỡ bấm nhầm).

const DUONG_IN_NHAN = "/assets/erpnext/js/warehouse_operations/in_nhan_lo.js";
const O_TEM_API = "erpnext.warehouse_operations.vitri.o_tem.";

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
			nut_phieu_nhap_lo(frm);
			frappe.xcall(O_TEM_API + "thong_tin_o_tem", { so_lo: frm.doc.name }).then((t) => {
				if (!t) return;
				if (t.loi) frm.dashboard.set_headline_alert(frappe.utils.escape_html(t.loi), "red");
				else if (!t.o)
					frm.dashboard.set_headline_alert(
						__("Lô chưa có ô trên tem — chưa xếp vào ô nào được. Bấm \"Đặt ô trên tem\"."),
						"orange"
					);
				if (!t.duoc_doi) return;
				frm.add_custom_button(t.o ? __("Đổi ô trên tem") : __("Đặt ô trên tem"), () =>
					doi_o_tem(frm, t)
				);
			});
		});
	},
});

// NÚT "Xem phiếu nhập lô" (23/09/2026) — thay cho một mục Connections KHÔNG làm
// được: tab Connections chỉ tìm trường Link trên chính doctype đích, mà số lô nằm
// ở BẢNG CON của `Batch Entry` (`Batch Entry Item.lo_da_tao`). Xem chú thích ở
// `stock/doctype/batch/batch_dashboard.py`.
//
// Từ lô đi ngược về phiếu khai ra nó là đường thật: tem rách hay sai hạn dùng thì
// người ta cầm số lô trong tay, không nhớ phiếu nào.
function nut_phieu_nhap_lo(frm) {
	frappe.xcall("erpnext.warehouse_operations.vitri.luong_nhap.phieu_nhap_lo_cua_lo", {
		so_lo: frm.doc.name,
	}).then((ds) => {
		if (!ds || !ds.length) return;
		frm.add_custom_button(__("Xem phiếu nhập lô"), () => {
			if (ds.length === 1) frappe.set_route("Form", "Batch Entry", ds[0]);
			else frappe.set_route("List", "Batch Entry", { name: ["in", ds] });
		});
	});
}

function in_nhan(frm) {
	frappe.require(DUONG_IN_NHAN, () => {
		// Một lô — một nhãn. Cùng đúng đường ba bước với "In nhãn cả phiếu"
		// (xem `in_nhan_lo.js`), nên không có cách nào để hai màn hình in ra
		// hai con tem khác nhau cho cùng một lô.
		erpnext.warehouse_operations.in_nhan.in_cho_cac_lo([frm.doc.name]);
	});
}

function doi_o_tem(frm, t) {
	const d = new frappe.ui.Dialog({
		title: t.o ? __("Đổi ô trên tem lô {0}", [frm.doc.name]) : __("Đặt ô trên tem lô {0}", [frm.doc.name]),
		fields: [
			{
				fieldtype: "HTML",
				options: t.o
					? `<p>${__("Ô hiện in trên tem")}: <b>${frappe.utils.escape_html(t.o)}</b>. ${__(
							"Sau khi đổi, lô chỉ xếp được vào ô mới — in lại tem và dán đè tem cũ."
					  )}</p>`
					: `<p>${__("Lô chỉ xếp được vào ô chọn ở đây. Lưu xong in tem và dán lên thùng.")}</p>`,
			},
			{
				fieldname: "o_moi",
				fieldtype: "Link",
				options: "Storage Location",
				label: __("Ô mới"),
				reqd: 1,
				default: t.goi_y && t.goi_y !== t.o ? t.goi_y : null,
				get_query: () => ({
					filters: Object.assign(
						{ is_group: 0, la_o_chua_xep: 0, disabled: 0 },
						t.kho ? { kho: t.kho } : {}
					),
				}),
			},
			{ fieldname: "ly_do", fieldtype: "Small Text", label: __("Lý do"), reqd: t.o ? 1 : 0 },
		],
		primary_action_label: __("Lưu và in tem"),
		primary_action(v) {
			frappe
				.xcall(O_TEM_API + "doi_o_tren_tem", { so_lo: frm.doc.name, o_moi: v.o_moi, ly_do: v.ly_do })
				.then((kq) => {
					d.hide();
					frappe.show_alert({
						message: __("Ô trên tem: {0}. Đang in tem mới.", [frappe.utils.escape_html(kq.ma_in_nhan)]),
						indicator: "green",
					});
					frm.reload_doc();
					in_nhan(frm);
				});
		},
	});
	d.show();
}

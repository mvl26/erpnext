// Cấp và in thẻ PDA.
//
// MÃ THẺ CHỈ TỒN TẠI TRONG MỘT NHỊP: `cap_the` trả mã gốc đúng một lần, màn hình
// này đẩy thẳng sang cửa sổ in rồi quên. Không lưu vào `frm.doc`, không show_alert,
// không console.log — mã nằm lại ở đâu là ở đó thành một bản sao chìa khoá.
//
// Tem in bằng ĐÚNG khuôn tem 50×30 đang chạy (`tem_lo.in_xap`, các ô F1…F11) —
// cùng cách tem kiện đã làm 22/09. Mã vạch Code128, KHÔNG dùng QR: súng quét laser
// 1D của kho không đọc được mã hai chiều.

const DUONG_NAP_TEM = [
	"/assets/erpnext/js/warehouse_operations/tem_vi_tri.js",
	"/assets/erpnext/js/warehouse_operations/tem_lo.js",
];

frappe.ui.form.on("PDA Badge", {
	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(__("Cấp thẻ & in"), () => cap_va_in(frm));
		if (frm.doc.con_hieu_luc) {
			frm.add_custom_button(__("Thu hồi thẻ"), () => thu_hoi(frm));
		}
	},
});

function cap_va_in(frm) {
	frappe.xcall("erpnext.warehouse_operations.vitri.the_pda.cap_the", { nguoi_dung: frm.doc.nguoi_dung }).then((kq) => {
		if (!kq || !kq.ma) return;
		frappe.require(DUONG_NAP_TEM, () => {
			const mo_duoc = erpnext.warehouse_operations.tem_lo.in_xap([
				{
					F1: kq.ho_ten || kq.the,
					F2: kq.the,
					F3: __("THẺ PDA — KHO"),
					F4: "",
					F5: frappe.datetime.str_to_user(kq.cap_luc),
					F6: "",
					F7: "",
					F8: "",
					F9: "PDA",
					F10: kq.ma,
					F11: kq.ma,
				},
			]);
			if (!mo_duoc) {
				// Cửa sổ in bị chặn mà thẻ ĐÃ được cấp: mã cũ đã chết, mã mới thì không in
				// ra được và không đọc lại được. Nói thẳng việc phải làm: cho phép pop-up
				// rồi bấm "Cấp thẻ & in" LẦN NỮA (cấp lại lần nữa là chuyện thường).
				frappe.msgprint({
					title: __("Trình duyệt chặn cửa sổ in"),
					message: __(
						"Thẻ đã được cấp nhưng chưa in ra được, và mã không xem lại được. "
							+ "Cho phép pop-up cho trang này rồi bấm 'Cấp thẻ & in' một lần nữa."
					),
					indicator: "red",
				});
			}
			frm.reload_doc();
		});
	});
}

function thu_hoi(frm) {
	const d = new frappe.ui.Dialog({
		title: __("Thu hồi thẻ của {0}", [frm.doc.ho_ten || frm.doc.nguoi_dung]),
		primary_action_label: __("Thu hồi"),
		primary_action: () => {
			d.hide();
			frappe.xcall("erpnext.warehouse_operations.vitri.the_pda.thu_hoi", { nguoi_dung: frm.doc.nguoi_dung }).then(() => {
				frappe.show_alert({ message: __("Đã thu hồi thẻ và đóng phiên đang mở."), indicator: "orange" });
				frm.reload_doc();
			});
		},
		secondary_action_label: __("Không"),
		secondary_action: () => d.hide(),
	});
	d.$body.append(
		`<p>${__("Thẻ hiện tại sẽ ngừng hoạt động ngay và phiên đang mở trên PDA bị đóng.")}</p>`
	);
	d.show();
}

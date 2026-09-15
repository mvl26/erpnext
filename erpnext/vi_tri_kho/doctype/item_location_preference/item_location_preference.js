// Nút mở cây chọn vị trí. Trường `vi_tri` vẫn là Link bình thường — gõ tay
// được, vì người quen mã gõ nhanh hơn bấm nhiều cấp cây. Cây (xem
// `cay_chon_vi_tri.js`) cho chọn nút BẤT KỲ CẤP nào — Khu/Dãy/Khoang/Tầng lẫn
// Ô lá — qua nút "Chọn vị trí này" trong toolbar của từng nốt (Ruling P, vòng
// sửa 1 điều phối), đúng yêu cầu chủ đầu tư 15/09: gán ở cấp Tầng/Khoang là ca
// dùng CHÍNH, gán vào một Ô lẻ mới là ca nên tránh.

const DUONG_CAY = "/assets/erpnext/js/vi_tri_kho/cay_chon_vi_tri.js";

frappe.ui.form.on("Item Location Preference", {
	refresh(frm) {
		frm.add_custom_button(__("Chọn trên cây vị trí"), () => {
			if (!frm.doc.kho) {
				frappe.msgprint(__("Chọn Kho trước — cây vị trí là của một kho."));
				return;
			}
			frappe.require(DUONG_CAY, () => {
				erpnext.vi_tri_kho.chon_vi_tri(frm.doc.kho, (o) => frm.set_value("vi_tri", o));
			});
		});
	},
});

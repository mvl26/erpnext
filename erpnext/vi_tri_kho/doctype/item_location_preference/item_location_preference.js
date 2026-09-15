// Nút mở cây chọn vị trí. Trường `vi_tri` vẫn là Link bình thường — gõ tay
// được, vì người quen mã gõ nhanh hơn bấm nhiều cấp cây, và vì cây (xem
// `cay_chon_vi_tri.js`) chỉ cho CHỌN được nút LÁ (Ô) bằng cú bấm — gán ở cấp
// Tầng trở lên vẫn phải gõ tay, không có đường nào khác trên cây cho ca đó.

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

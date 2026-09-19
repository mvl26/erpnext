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
				// `tru_ten`: khi đang SỬA một bản ghi đã lưu (không phải tạo
				// mới), truyền tên chính nó để cây loại trừ gán này ra khỏi
				// `co_gan_ben_trong` — nếu không, dời gán từ Tầng lên Khoang
				// cha của chính nó (thao tác HỢP LỆ, `validate()` phía máy
				// chủ cũng loại trừ y hệt qua `tru_ten=self.name`) sẽ bị nút
				// "Chọn vị trí này" khoá oan vì cây đếm nhầm CHÍNH gán đang
				// sửa là "gán bên trong". `frm.is_new()` chặn gửi tên tạm
				// (`new-item-location-preference-...`) khi đang tạo mới —
				// tên đó không khớp bản ghi nào nên vô hại, nhưng gửi đúng
				// `undefined` rõ ràng hơn là gửi rác.
				const tru_ten = frm.is_new() ? null : frm.doc.name;
				erpnext.vi_tri_kho.chon_vi_tri(frm.doc.kho, (o) => frm.set_value("vi_tri", o), tru_ten);
			});
		});
	},
});

// Nút mở cây chọn vị trí. Trường `vi_tri` vẫn là Link bình thường — gõ tay
// được, vì người quen mã gõ nhanh hơn bấm nhiều cấp cây. Cây (xem
// `cay_chon_vi_tri.js`) cho chọn nút BẤT KỲ CẤP nào — Khu/Dãy/Khoang/Tầng lẫn
// Ô lá — qua nút "Chọn vị trí này" trong toolbar của từng nốt (Ruling P, vòng
// sửa 1 điều phối), đúng yêu cầu chủ đầu tư 15/09: gán ở cấp Tầng/Khoang là ca
// dùng CHÍNH, gán vào một Ô lẻ mới là ca nên tránh.

const DUONG_CAY = "/assets/erpnext/js/warehouse_operations/cay_chon_vi_tri.js";

frappe.ui.form.on("Item Location Preference", {
	refresh(frm) {
		// 22/09/2026 — bản gán giữ NHIỀU vị trí (bảng `vi_tri_gan`). Nút này THÊM một
		// dòng; bỏ/sắp lại dòng dùng lưới như thường. Kho hỏi mỗi lần thêm vì các dòng
		// có thể ở các kho khác nhau.
		frm.add_custom_button(__("Thêm vị trí từ cây"), () => {
			const d = new frappe.ui.Dialog({
				title: __("Thêm vị trí — chọn kho"),
				fields: [
					{
						fieldname: "kho",
						fieldtype: "Link",
						options: "Warehouse",
						label: __("Kho"),
						reqd: 1,
						get_query: () => ({ filters: { custom_quan_ly_vi_tri: 1, is_group: 0 } }),
					},
				],
				primary_action_label: __("Chọn trên cây vị trí"),
				primary_action(v) {
					d.hide();
					frappe.require(DUONG_CAY, () => {
						const tru_ten = frm.is_new() ? null : frm.doc.name;
						const dang_co = (frm.doc.vi_tri_gan || []).map((r) => r.vi_tri).filter(Boolean);
						erpnext.warehouse_operations.chon_vi_tri(
							v.kho,
							(o) => {
								frm.add_child("vi_tri_gan", { vi_tri: o });
								frm.refresh_field("vi_tri_gan");
								frm.dirty();
							},
							tru_ten,
							dang_co
						);
					});
				},
			});
			d.show();
		});
	},
});

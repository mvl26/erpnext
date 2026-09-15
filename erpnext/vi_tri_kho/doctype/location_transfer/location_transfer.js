// Nút "Lấy hàng chưa xếp": đổ toàn bộ hàng đang ở ô "Chưa xếp vị trí" của kho
// thành các dòng sẵn.
//
// Ô ĐÍCH được GỢI Ý SẴN (`den_o`) từ máy chủ kể từ 15/09/2026 — mặt hàng có vị
// trí cố định thì "xếp đâu" trả lời được. Đây vẫn chỉ là GỢI Ý: `den_o` là
// trường `reqd` trên dòng, thủ kho đổi tay vẫn lưu bình thường, và mặt hàng
// chưa gán thì máy chủ cố tình để trống — không đoán bừa.

frappe.ui.form.on("Location Transfer", {
	refresh(frm) {
		if (frm.doc.docstatus !== 0 || !frm.doc.kho) return;
		frm.add_custom_button(__("Lấy hàng chưa xếp"), () => lay_hang_chua_xep(frm));
	},

	kho(frm) {
		// Ô của kho cũ không dùng được cho kho mới — phép kiểm K2 phía máy chủ
		// sẽ chặn lúc lưu. Xoá luôn ở đây để người dùng khỏi phải sửa từng
		// dòng rồi mới biết.
		if (frm.doc.items && frm.doc.items.length) {
			frm.clear_table("items");
			frm.refresh_field("items");
			frappe.show_alert({ message: __("Đã xoá các dòng vì đổi kho."), indicator: "orange" });
		}
	},
});

function lay_hang_chua_xep(frm) {
	frappe.call({
		method: "erpnext.vi_tri_kho.vitri.xep.hang_chua_xep",
		args: { kho: frm.doc.kho },
		callback(r) {
			const dong = r.message || [];
			if (!dong.length) {
				frappe.msgprint({
					title: __("Không có hàng chưa xếp"),
					message: __("Kho {0} không còn hàng nào ở ô 'Chưa xếp vị trí'.", [frm.doc.kho]),
					indicator: "green",
				});
				return;
			}
			frm.clear_table("items");
			dong.forEach((d) => {
				const r = frm.add_child("items");
				r.vat_tu = d.vat_tu;
				r.so_lo = d.so_lo;
				r.tu_o = d.tu_o;
				r.so_luong = d.so_luong;
				// den_o là gợi ý từ máy chủ (goi_y.goi_y_o qua xep.hang_chua_xep),
				// không phải giá trị cố định — thủ kho vẫn sửa được trên lưới.
				// Bỏ dòng này thì trường `reqd` của den_o buộc thủ kho gõ tay MỌI
				// dòng dù máy chủ đã biết câu trả lời, và cả Task 6 vô hình trên
				// màn hình dù xep.py đã trả đúng dữ liệu.
				r.den_o = d.den_o;
			});
			frm.refresh_field("items");
			frappe.show_alert({
				message: __("Đã lấy {0} dòng. Điền ô đích cho từng dòng.", [dong.length]),
				indicator: "blue",
			});

			// Tóm tắt SAU khi lưới đã có dòng: đếm bao nhiêu dòng máy chủ không
			// gợi ý được (mặt hàng chưa gán vị trí cố định) để thủ kho biết ngay
			// những dòng nào phải tự tay chọn ô, không lặng lẽ để `reqd` chặn ở
			// bước lưu rồi mới đi tìm lý do.
			const chua_gan = dong.filter((d) => !d.den_o).length;
			if (chua_gan) {
				frappe.show_alert({
					message: __("{0} dòng chưa có gợi ý — mặt hàng chưa gán vị trí cố định.", [
						chua_gan,
					]),
					indicator: "orange",
				});
			}
		},
	});
}

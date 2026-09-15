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
			// gợi ý được, để thủ kho biết ngay những dòng nào phải tự tay chọn
			// ô, không lặng lẽ để `reqd` chặn ở bước lưu rồi mới đi tìm lý do.
			//
			// Ruling O (vòng sửa 1, review điều phối): `ly_do_goi_y` của
			// `goi_y_o()` có ÍT NHẤT BA nguyên nhân khác hẳn nhau — "chưa gán",
			// "vùng đã đầy" (hết cả ô trống lẫn ô cùng hàng), và từ Ruling N,
			// "lỗi dữ liệu vị trí". Mỗi nguyên nhân cần một HÀNH ĐỘNG khác nhau
			// của thủ kho (đi gán / đi dọn hoặc mở rộng vùng / báo lỗi dữ liệu).
			// Một câu cố định "chưa gán vị trí cố định" cho MỌI dòng rỗng từng
			// khiến ca "đã gán nhưng hết chỗ" bị đọc nhầm thành "chưa gán" — đúng
			// lớp lỗi "màn hình nói sai sự thật" đã dính hai lần trước đó trong
			// dự án. Gộp theo `ly_do_goi_y` THẬT và hiện riêng từng nhóm thay vì
			// đoán hoặc rút gọn về một câu chung.
			//
			// `ly_do_goi_y` không có trường trên `Location Transfer Item` (cố ý,
			// ngoài phạm vi vòng sửa này) nên không hiện được theo TỪNG dòng
			// trên lưới — chỉ hiện được ở đây, một lần, dạng tóm tắt, lấy từ
			// `dong` (phản hồi RPC gốc), không phải từ các dòng con đã tạo.
			const thieu = dong.filter((d) => !d.den_o);
			if (thieu.length) {
				const theo_ly_do = {};
				thieu.forEach((d) => {
					const ly_do = d.ly_do_goi_y || __("không rõ lý do");
					theo_ly_do[ly_do] = (theo_ly_do[ly_do] || 0) + 1;
				});
				const chi_tiet = Object.keys(theo_ly_do)
					.map((ly_do) => __("{0} dòng ({1})", [theo_ly_do[ly_do], ly_do]))
					.join(", ");
				frappe.show_alert({
					message: __("{0} dòng chưa có gợi ý: {1}.", [thieu.length, chi_tiet]),
					indicator: "orange",
				});
			}
		},
	});
}

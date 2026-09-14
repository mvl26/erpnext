// Nút "Lấy hàng chưa xếp": đổ toàn bộ hàng đang ở ô "Chưa xếp vị trí" của kho
// thành các dòng sẵn.
//
// Ô ĐÍCH cố ý để TRỐNG. Không có căn cứ nào để gợi ý — trường `suc_chua` hiện
// bằng 0 trên cả 214 ô — mà gợi ý sai thì thủ kho tin theo rồi xếp nhầm, và
// mọi lần quét sau đó đều trỏ sai chỗ.

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
				// den_o để trống — xem chú thích đầu file.
			});
			frm.refresh_field("items");
			frappe.show_alert({
				message: __("Đã lấy {0} dòng. Điền ô đích cho từng dòng.", [dong.length]),
				indicator: "blue",
			});
		},
	});
}

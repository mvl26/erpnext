// Copyright (c) 2026, Công ty TNHH Miyano Việt Nam
//
// Cài đặt thông báo: nhắc rõ khi đang bật Chế độ thử, vì đó là trạng thái dễ
// quên nhất — thư nội bộ vẫn chạy nên nhìn bề ngoài mọi thứ vẫn "bình thường",
// trong khi NCC và khách không nhận được gì.

frappe.ui.form.on("Supply Notification Settings", {
	refresh(frm) {
		frm.dashboard.clear_headline();

		if (frm.doc.test_mode) {
			frm.dashboard.set_headline(
				__("Đang bật Chế độ thử: mọi email chuyển về {0}. Đối tác không nhận được gì.", [
					frappe.utils.escape_html(frm.doc.test_email || ""),
				]),
				"orange"
			);
		} else if (!frm.doc.enabled) {
			frm.dashboard.set_headline(__("Tính năng thông báo đang tắt toàn bộ."), "red");
		}

		frm.add_custom_button(__("Mở nhật ký gửi"), () =>
			frappe.set_route("List", "Supply Notification Dispatch Log")
		);
		frm.add_custom_button(__("Danh sách điểm thông báo"), () =>
			frappe.set_route("List", "Supply Notification Point")
		);
	},
});

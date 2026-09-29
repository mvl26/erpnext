// Copyright (c) 2026, Công ty TNHH Miyano Việt Nam
//
// Nhật ký gửi: dòng lỗi có nút "Gửi lại" để nghiệp vụ tự xử lý sau khi sửa dữ
// liệu (thêm email NCC, gắn tài khoản cho nhân viên) mà không cần gọi Dev.

frappe.ui.form.on("Supply Notification Dispatch Log", {
	refresh(frm) {
		if (frm.doc.status !== "Failed") return;

		frm.add_custom_button(__("Gửi lại"), () => {
			frappe.confirm(__("Gửi lại thông báo này theo cấu hình hiện tại?"), () => {
				frappe.call({
					method: "erpnext.supply_notification.dispatch.resend",
					args: { log: frm.doc.name },
					freeze: true,
					freeze_message: __("Đang gửi lại..."),
					callback(r) {
						if (!r.message) return;
						frappe.show_alert({ message: __("Đã gửi lại"), indicator: "green" });
						frappe.set_route("Form", "Supply Notification Dispatch Log", r.message);
					},
				});
			});
		}).addClass("btn-primary");
	},
});

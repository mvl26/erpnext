// Copyright (c) 2026, Công ty TNHH Miyano Việt Nam
//
// Nhật ký gửi: nút "Gửi lại" để nghiệp vụ tự xử lý sau khi sửa dữ liệu (thêm
// email NCC, gắn tài khoản cho nhân viên) mà không cần gọi Dev.
//
// Nút hiện ở MỌI trạng thái, nhưng câu xác nhận khác nhau: dòng `Sent` là thư đã
// đi thành công, gửi lại sẽ tạo thêm một thư nữa — phải nói rõ để không gửi trùng
// do bấm nhầm.

const CONFIRM_BY_STATUS = {
	Failed: "Thư này gửi lỗi. Gửi lại theo cấu hình hiện tại?",
	Partial:
		"Thư nội bộ đã đi nhưng đối tác (NCC/khách) chưa nhận được. Nếu đã bổ sung email liên hệ thì gửi lại ngay bây giờ?",
	Skipped: "Lần gửi này bị bỏ qua. Nếu đã sửa nguyên nhân (xem ô Lý do) thì gửi lại?",
	Sent: "Thư này ĐÃ gửi thành công. Gửi lại sẽ tạo thêm một thư nữa tới cùng người nhận. Tiếp tục?",
};

frappe.ui.form.on("Supply Notification Dispatch Log", {
	refresh(frm) {
		if (frm.is_new()) return;

		const message = CONFIRM_BY_STATUS[frm.doc.status] || CONFIRM_BY_STATUS.Sent;

		const button = frm.add_custom_button(__("Gửi lại"), () => {
			frappe.confirm(__(message), () => {
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
		});

		if (frm.doc.status !== "Sent") {
			button.addClass("btn-primary");
		}

		if (frm.doc.body || frm.doc.external_body) {
			frm.add_custom_button(__("Xem thư như người nhận thấy"), () => show_mail(frm));
		}

		if (frm.doc.status === "Partial") {
			frm.dashboard.set_headline(
				__("Đối tác chưa nhận được thư này. Lý do: {0}", [
					frappe.utils.escape_html(frm.doc.reason || ""),
				]),
				"orange"
			);
		}
	},
});

function show_mail(frm) {
	// Dựng lại đúng thứ người nhận thấy, từ BẢN CHỤP trong nhật ký — không render
	// lại từ cấu hình hiện tại, vì mẫu có thể đã bị sửa sau lần gửi này.
	const parts = [];

	if (frm.doc.external_body) {
		parts.push(
			block(
				__("Thư gửi đối tác"),
				frm.doc.external_recipients,
				frm.doc.external_subject,
				frm.doc.external_body
			)
		);
	}
	if (frm.doc.body) {
		parts.push(block(__("Thư nội bộ"), frm.doc.recipients, frm.doc.subject, frm.doc.body));
	}

	frappe.msgprint({
		title: __("Nội dung đã gửi {0}", [frappe.datetime.str_to_user(frm.doc.sent_on)]),
		message: parts.join("<hr>"),
		wide: true,
	});
}

function block(title, to, subject, body) {
	return `
		<h5>${title}</h5>
		<p class="mb-1"><b>${__("Tới")}:</b> ${frappe.utils.escape_html(to || "")}</p>
		<p class="mb-2"><b>${__("Tiêu đề")}:</b> ${frappe.utils.escape_html(subject || "")}</p>
		<div class="border p-3" style="background:#fff; max-height:420px; overflow:auto">${body}</div>`;
}

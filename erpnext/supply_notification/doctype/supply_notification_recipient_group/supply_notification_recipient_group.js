// Copyright (c) 2026, Công ty TNHH Miyano Việt Nam
//
// Nhóm người nhận: nút xem thành viên THỰC TẾ — phòng ban chỉ là cấu hình, ai
// thật sự nhận được thư còn phụ thuộc nhân viên đã gắn tài khoản hay chưa.

frappe.ui.form.on("Supply Notification Recipient Group", {
	refresh(frm) {
		if (frm.is_new()) return;

		frm.add_custom_button(__("Xem thành viên thực tế"), () => {
			frappe.call({
				method: "erpnext.supply_notification.doctype.supply_notification_recipient_group.supply_notification_recipient_group.members",
				args: { group: frm.doc.name },
				freeze: true,
				callback(r) {
					if (!r.message) return;
					frm.get_field("member_preview").$wrapper.html(render(r.message));
				},
			});
		});
	},
});

function render(data) {
	let html = "";

	if (data.warnings && data.warnings.length) {
		const items = data.warnings.map((w) => `<li>${frappe.utils.escape_html(w)}</li>`).join("");
		html += `<div class="alert alert-warning"><ul class="mb-0">${items}</ul></div>`;
	}

	if (data.recipients.length) {
		const rows = data.recipients
			.map(
				(r) =>
					`<tr><td>${frappe.utils.escape_html(
						r.full_name || r.name
					)}</td><td>${frappe.utils.escape_html(r.email)}</td></tr>`
			)
			.join("");
		html += `<table class="table table-bordered"><thead><tr><th>${__("Họ tên")}</th><th>${__(
			"Email"
		)}</th></tr></thead><tbody>${rows}</tbody></table>`;
	} else {
		html += `<p>${__("Chưa có thành viên nào nhận được thông báo.")}</p>`;
	}

	if (data.fixed_emails && data.fixed_emails.length) {
		html += `<p><b>${__("Email cố định")}:</b> ${frappe.utils.escape_html(
			data.fixed_emails.join(", ")
		)}</p>`;
	}

	return html;
}

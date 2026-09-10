// Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

frappe.ui.form.on("Supply Notification Point", {
	refresh(frm) {
		frm.add_custom_button(__("Xem trước người nhận"), () => show_preview(frm));
	},
});

function show_preview(frm) {
	frappe.call({
		method: "erpnext.supply_notification.resolver.preview",
		args: { point: frm.doc.name },
		freeze: true,
		freeze_message: __("Đang tra danh sách người nhận..."),
		callback(r) {
			if (!r.message) return;
			frappe.msgprint({
				title: __("Người nhận của {0}", [frm.doc.code]),
				message: render_preview(r.message),
				wide: true,
			});
		},
	});
}

function render_preview(data) {
	const source_label = {
		department: __("phòng ban"),
		user: __("đích danh"),
	};

	let html = "";

	if (data.warnings.length) {
		const items = data.warnings.map((w) => `<li>${frappe.utils.escape_html(w)}</li>`).join("");
		html += `<div class="alert alert-warning"><ul class="mb-0">${items}</ul></div>`;
	}

	if (data.recipients.length) {
		const rows = data.recipients
			.map((r) => {
				const sources = r.sources.map((s) => source_label[s] || s).join(", ");
				return `<tr>
					<td>${frappe.utils.escape_html(r.full_name || r.user)}</td>
					<td>${frappe.utils.escape_html(r.email)}</td>
					<td>${frappe.utils.escape_html(sources)}</td>
				</tr>`;
			})
			.join("");
		html += `<table class="table table-bordered">
			<thead><tr>
				<th>${__("Họ tên")}</th><th>${__("Email")}</th><th>${__("Nguồn")}</th>
			</tr></thead>
			<tbody>${rows}</tbody>
		</table>`;
	} else {
		html += `<p>${__("Không có người nhận nào.")}</p>`;
	}

	if (data.notify_owner) {
		html += `<p class="text-muted">${__(
			"Người lập chứng từ cũng nhận thông báo, tuỳ từng chứng từ nên không liệt kê ở đây."
		)}</p>`;
	}

	return html;
}

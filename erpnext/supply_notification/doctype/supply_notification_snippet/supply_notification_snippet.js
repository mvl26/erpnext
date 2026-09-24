// Copyright (c) 2026, Công ty TNHH Miyano Việt Nam
//
// Mẫu dùng chung: hiện ngay danh sách điểm đang dùng, để người sửa biết mình
// đang đổi câu chữ của những thư nào.

frappe.ui.form.on("Supply Notification Snippet", {
	refresh(frm) {
		if (frm.is_new()) return;

		frappe
			.call(
				"erpnext.supply_notification.doctype.supply_notification_snippet.supply_notification_snippet.usage",
				{
					snippet: frm.doc.name,
				}
			)
			.then((r) => {
				const points = r.message || [];
				const html = points.length
					? `<p>${__("Đang dùng ở")}: ${points
							.map(
								(p) =>
									`<a href="/app/supply-notification-point/${encodeURIComponent(
										p
									)}">${p}</a>`
							)
							.join(", ")}</p>`
					: `<p class="text-muted">${__("Chưa điểm nào dùng mẫu này.")}</p>`;
				frm.get_field("used_by").$wrapper.html(html);
			});

		frm.add_custom_button(__("Chèn vào điểm thông báo"), () =>
			frappe.msgprint({
				title: __("Cách chèn"),
				message: __("Dán đoạn này vào ô nội dung của điểm: {0}", [
					`<code>{{ mau("${frappe.utils.escape_html(frm.doc.name)}") }}</code>`,
				]),
			})
		);
	},
});

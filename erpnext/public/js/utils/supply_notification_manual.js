// Copyright (c) 2026, Công ty TNHH Miyano Việt Nam
//
// Nút "gửi thủ công" trên form của BẤT KỲ chứng từ nào có điểm thông báo loại
// Thủ công (CR_01: nút "Gửi cho NCC" trên Đơn mua hàng).
//
// Không nối riêng vào từng DocType: bắt sự kiện `form-refresh` chung, rồi chỉ
// hỏi máy chủ khi DocType đang mở nằm trong danh sách `frappe.boot` bơm sẵn —
// mở chứng từ khác không kéo theo lời gọi nào.
//
// Ba lớp bảo vệ trước khi thư đi: nút chỉ hiện khi đủ điều kiện, hộp xác nhận
// hiện rõ người nhận / tệp / số lần đã gửi, và máy chủ kiểm lại quyền lẫn trạng
// thái chứng từ (gọi thẳng API vẫn bị từ chối).

frappe.provide("erpnext.supply_notification");

const GROUP_LABEL = "Gửi thông báo";

erpnext.supply_notification.manual_doctypes = function () {
	return (
		(frappe.boot && frappe.boot.supply_notification && frappe.boot.supply_notification.manual_doctypes) ||
		[]
	);
};

erpnext.supply_notification.setup_manual_buttons = function (frm) {
	if (!frm.doc || frm.is_new() || frm.doc.__islocal) return;
	if (!erpnext.supply_notification.manual_doctypes().includes(frm.doctype)) return;

	frappe
		.call({
			method: "erpnext.supply_notification.manual.get_buttons",
			args: { doctype: frm.doctype, docname: frm.doc.name },
			quiet: true,
		})
		.then((r) => {
			const buttons = r.message || [];
			if (!buttons.length) return;

			buttons.forEach((button) => add_button(frm, button, buttons.length > 1));
			show_history(frm, buttons);
		});
};

function add_button(frm, button, grouped) {
	const label = button.count ? `${button.label} (${button.count})` : button.label;
	const action = () => open_confirmation(frm, button);

	if (grouped) {
		frm.add_custom_button(__(label), action, __(GROUP_LABEL));
		return;
	}

	frm.add_custom_button(__(label), action);
	if (button.color) {
		frm.change_custom_button_type(__(label), null, button.color);
	}
}

function show_history(frm, buttons) {
	const lines = buttons.filter((button) => button.summary).map((button) => button.summary);
	if (!lines.length) return;

	frm.dashboard.add_comment(lines.join("<br>"), "blue", true);
}

function open_confirmation(frm, button) {
	frappe.call({
		method: "erpnext.supply_notification.manual.get_confirmation",
		args: { point: button.point, doctype: frm.doctype, docname: frm.doc.name },
		freeze: true,
		freeze_message: __("Đang chuẩn bị thư..."),
		callback(r) {
			if (!r.message) return;
			render_confirmation(frm, r.message);
		},
	});
}

function render_confirmation(frm, data) {
	const dialog = new frappe.ui.Dialog({
		title: data.title,
		size: "large",
		fields: [{ fieldtype: "HTML", fieldname: "summary" }],
		primary_action_label: __("Gửi"),
		primary_action() {
			dialog.hide();
			send(frm, data.point);
		},
	});

	dialog.fields_dict.summary.$wrapper.html(confirmation_html(data));

	if (data.blocked) {
		dialog.get_primary_btn().addClass("disabled").attr("disabled", true);
	}

	dialog.show();
}

function confirmation_html(data) {
	let html = "";

	if (data.warnings && data.warnings.length) {
		const items = data.warnings.map((w) => `<li>${frappe.utils.escape_html(w)}</li>`).join("");
		html += `<div class="alert alert-warning"><ul class="mb-0">${items}</ul></div>`;
	}

	html += row(__("Gửi tới"), (data.to || []).join(", "));
	html += row(__("CC"), (data.cc || []).join(", "));
	html += row(__("BCC"), (data.bcc || []).join(", "));
	html += row(__("Trả lời về"), data.reply_to);
	html += row(__("Tệp đính kèm"), (data.attachments || []).join(", "));
	html += row(__("Đã gửi"), data.summary || __("chưa gửi lần nào"));
	html += row(__("Tiêu đề"), data.subject);

	html += `<div class="border p-3 mt-2" style="background:#fff; max-height:400px; overflow:auto">${data.body}</div>`;

	return html;
}

function row(label, value) {
	if (!value) return "";
	return `<p class="mb-1"><b>${label}:</b> ${frappe.utils.escape_html(value)}</p>`;
}

function send(frm, point) {
	frappe.call({
		method: "erpnext.supply_notification.manual.send",
		args: { point: point, doctype: frm.doctype, docname: frm.doc.name },
		freeze: true,
		freeze_message: __("Đang gửi..."),
		callback(r) {
			if (!r.message) return;
			frappe.show_alert({
				message: __("Đã gửi tới {0}", [r.message.to || ""]),
				indicator: "green",
			});
			frm.reload_doc();
		},
	});
}

$(document).on("form-refresh", function (event, frm) {
	erpnext.supply_notification.setup_manual_buttons(frm);
});

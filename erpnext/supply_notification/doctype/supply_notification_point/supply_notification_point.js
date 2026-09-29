// Copyright (c) 2026, Công ty TNHH Miyano Việt Nam
//
// Form điểm thông báo: nạp danh sách trường theo chứng từ nguồn, chèn trường /
// khối / mẫu vào nội dung, và bốn công cụ tự kiểm (xem trước người nhận, xem
// trước email, gửi thử, thống kê).
//
// Mọi lời gọi máy chủ ở đây đều gửi **giá trị đang có trên form** (kể cả chưa
// lưu), nên người dùng thấy đúng cái mình vừa gõ.

const FIELD_PICKERS = {
	watch_field: {},
	date_field: { only_types: "Date,Datetime" },
	party_field: {},
	amount_field: { only_types: "Currency,Float,Int" },
	main_date_field: { only_types: "Date,Datetime" },
	item_table_field: { only_types: "Table" },
	address_field: { only_types: "Link" },
	contact_field: { only_types: "Link" },
};

const BLOCKS = [
	{ value: "bang_mat_hang()", label: __("Bảng mặt hàng"), scope: "both" },
	{ value: "khoi_so_lieu()", label: __("Khối số liệu"), scope: "both" },
	{ value: "dia_chi_giao_hang()", label: __("Địa chỉ giao hàng"), scope: "both" },
	{ value: "chu_ky()", label: __("Chữ ký người phụ trách"), scope: "both" },
	{ value: "khoi_phan_hoi()", label: __("Khối phản hồi của đối tác"), scope: "external" },
	{ value: "nut_mo_chung_tu()", label: __("Liên kết mở chứng từ"), scope: "internal" },
	{ value: 'link_bao_cao("Stock Balance")', label: __("Liên kết báo cáo"), scope: "internal" },
];

frappe.ui.form.on("Supply Notification Point", {
	onload(frm) {
		frm.set_query("reference_doctype", () => ({
			query: "erpnext.supply_notification.preview.doctype_query",
		}));
		load_field_options(frm);
	},

	refresh(frm) {
		frm.trigger("render_help");
		add_toolbar(frm);
		load_stats(frm);

		if (frm.is_new() && !frm.doc.code) {
			frappe.call("erpnext.supply_notification.preview.suggest_code").then((r) => {
				if (r.message && !frm.doc.code) frm.set_value("code", r.message);
			});
		}
	},

	reference_doctype(frm) {
		load_field_options(frm);
		frm.trigger("render_help");
	},

	trigger_event(frm) {
		load_field_options(frm);
	},

	render_help(frm) {
		frm.get_field("help_content").$wrapper.html(insert_table(frm, "internal"));
		frm.get_field("help_external").$wrapper.html(insert_table(frm, "external"));
	},
});

// --- Nạp danh sách trường ------------------------------------------------

function load_field_options(frm) {
	const doctype = frm.doc.reference_doctype;
	if (!doctype) return;

	Object.entries(FIELD_PICKERS).forEach(([fieldname, args]) => {
		frappe.call("erpnext.supply_notification.preview.field_options", { doctype, ...args }).then((r) => {
			const options = (r.message || []).map((row) => ({
				value: row.value,
				label: row.label,
				description: row.description,
			}));
			frm.set_df_property(fieldname, "options", options);
		});
	});

	frappe.call("erpnext.supply_notification.preview.workflow_states", { doctype }).then((r) => {
		frm.set_df_property("workflow_state", "options", r.message || []);
	});

	frm.fields_dict.conditions.grid.update_docfield_property("fieldname", "options", []);
	frappe.call("erpnext.supply_notification.preview.field_options", { doctype }).then((r) => {
		const options = (r.message || []).map((row) => row.value);
		["conditions"].forEach((table) => {
			frm.fields_dict[table].grid.update_docfield_property("fieldname", "options", options);
		});
		["item_columns", "fact_rows"].forEach((table) => {
			frm.fields_dict[table].grid.update_docfield_property("fieldname", "options", options);
		});
	});
}

// --- Bảng "Có thể chèn" --------------------------------------------------

function insert_table(frm, scope) {
	const blocks = BLOCKS.filter((b) => b.scope === "both" || b.scope === scope);
	const rows = blocks
		.map((b) => `<tr><td><code>{{ ${b.value} }}</code></td><td>${b.label}</td></tr>`)
		.join("");

	return `
		<div class="mb-3">
			<p class="text-muted">${__("Chèn giá trị bằng nút bên dưới. Biến hay dùng: {0}", [
				"<code>{{ doc.name }}</code>, <code>{{ ten_doi_tac }}</code>, <code>{{ so_tien }}</code>, <code>{{ ngay }}</code>",
			])}</p>
			<table class="table table-bordered table-sm"><tbody>${rows}</tbody></table>
		</div>`;
}

// --- Thanh công cụ -------------------------------------------------------

function add_toolbar(frm) {
	if (frm.is_new()) return;

	frm.add_custom_button(__("Xem trước người nhận"), () => preview_recipients(frm), __("Kiểm tra"));
	frm.add_custom_button(__("Xem trước email"), () => preview_email(frm), __("Kiểm tra"));
	frm.add_custom_button(__("Gửi thử cho tôi"), () => send_test(frm), __("Kiểm tra"));
	frm.add_custom_button(__("Chèn trường"), () => insert_dialog(frm, "field"), __("Soạn nội dung"));
	frm.add_custom_button(__("Chèn khối"), () => insert_dialog(frm, "block"), __("Soạn nội dung"));
	frm.add_custom_button(
		__("Chèn mẫu dùng chung"),
		() => insert_dialog(frm, "snippet"),
		__("Soạn nội dung")
	);
	frm.add_custom_button(__("Sao chép điểm"), () => copy_point(frm));
	frm.add_custom_button(__("Nhật ký của điểm"), () =>
		frappe.set_route("List", "Supply Notification Dispatch Log", { point: frm.doc.name })
	);
}

function point_payload(frm) {
	return JSON.stringify(frm.doc);
}

function preview_recipients(frm) {
	frappe.call({
		method: "erpnext.supply_notification.resolver.preview",
		args: { point: frm.doc.name, reference: frm.doc.preview_reference },
		freeze: true,
		freeze_message: __("Đang tra danh sách người nhận..."),
		callback(r) {
			if (!r.message) return;
			frappe.msgprint({
				title: __("Người nhận của {0}", [frm.doc.code]),
				message: render_recipients(r.message),
				wide: true,
			});
		},
	});
}

function render_recipients(data) {
	let html = warnings_html(data.warnings);

	if (data.recipients.length) {
		const rows = data.recipients
			.map(
				(r) => `<tr>
					<td>${frappe.utils.escape_html(r.full_name || r.user)}</td>
					<td>${frappe.utils.escape_html(r.email)}</td>
					<td>${frappe.utils.escape_html((r.sources || []).join(", "))}</td>
				</tr>`
			)
			.join("");
		html += `<table class="table table-bordered">
			<thead><tr><th>${__("Họ tên")}</th><th>${__("Email")}</th><th>${__("Nguồn")}</th></tr></thead>
			<tbody>${rows}</tbody></table>`;
	} else {
		html += `<p>${__("Không có người nhận nội bộ nào.")}</p>`;
	}

	html += list_html(__("Email gửi ra ngoài"), data.external);
	html += list_html(__("CC"), data.cc);
	html += list_html(__("BCC"), data.bcc);
	if (data.reply_to)
		html += `<p><b>${__("Trả lời về")}:</b> ${frappe.utils.escape_html(data.reply_to)}</p>`;

	return html;
}

function list_html(label, values) {
	if (!values || !values.length) return "";
	return `<p><b>${label}:</b> ${frappe.utils.escape_html(values.join(", "))}</p>`;
}

function warnings_html(warnings) {
	if (!warnings || !warnings.length) return "";
	const items = warnings.map((w) => `<li>${frappe.utils.escape_html(w)}</li>`).join("");
	return `<div class="alert alert-warning"><ul class="mb-0">${items}</ul></div>`;
}

function preview_email(frm) {
	frappe.call({
		method: "erpnext.supply_notification.preview.preview_email",
		args: { point_json: point_payload(frm), reference: frm.doc.preview_reference },
		freeze: true,
		freeze_message: __("Đang dựng thư..."),
		callback(r) {
			const data = r.message || {};
			if (data.error) {
				frappe.msgprint(data.error);
				return;
			}

			let html = warnings_html(data.warnings);
			html += `<p class="text-muted">${__("Xem trước với chứng từ")} <b>${frappe.utils.escape_html(
				data.reference
			)}</b></p>`;
			html += list_html(__("Người nhận nội bộ"), data.recipients);
			html += list_html(__("Người nhận ngoài"), data.external);
			html += list_html(__("Tệp đính kèm"), data.attachments);

			if (data.internal) html += mail_html(__("Email nội bộ"), data.internal);
			if (data.external_mail) html += mail_html(__("Email gửi ra ngoài"), data.external_mail);

			frappe.msgprint({ title: __("Xem trước email"), message: html, wide: true });
		},
	});
}

function mail_html(title, mail) {
	return `
		<h5 class="mt-3">${title}</h5>
		<p><b>${__("Tiêu đề")}:</b> ${frappe.utils.escape_html(mail.subject)}</p>
		<div class="border p-3" style="background:#fff">${mail.body}</div>`;
}

function send_test(frm) {
	frappe.confirm(__("Gửi một thư thử tới chính email của bạn?"), () => {
		frappe.call({
			method: "erpnext.supply_notification.preview.send_test_to_me",
			args: { point_json: point_payload(frm), reference: frm.doc.preview_reference },
			freeze: true,
			callback(r) {
				if (!r.message) return;
				frappe.show_alert({
					message: __("Đã xếp thư thử gửi tới {0}", [r.message.email]),
					indicator: "green",
				});
			},
		});
	});
}

function load_stats(frm) {
	if (frm.is_new()) return;

	frappe.call("erpnext.supply_notification.preview.point_stats", { name: frm.doc.name }).then((r) => {
		const s = r.message;
		if (!s) return;
		frm.get_field("stats_html").$wrapper.html(`
			<div class="row">
				<div class="col-sm-3"><b>${s.total}</b><div class="text-muted">${__("lần gửi {0} ngày qua", [
			s.days,
		])}</div></div>
				<div class="col-sm-3"><b>${s.sent}</b><div class="text-muted">${__("thành công")}</div></div>
				<div class="col-sm-3"><b>${s.skipped}</b><div class="text-muted">${__("bỏ qua")}</div></div>
				<div class="col-sm-3"><b>${s.failed}</b><div class="text-muted">${__("lỗi")} (${s.failure_rate}%)</div></div>
			</div>`);
	});
}

// --- Chèn vào nội dung ---------------------------------------------------

const TARGETS = [
	{ value: "subject_template", label: __("Tiêu đề") },
	{ value: "body_template", label: __("Thân email") },
	{ value: "external_subject_template", label: __("Tiêu đề (ngoài)") },
	{ value: "external_body_template", label: __("Thân email (ngoài)") },
];

function insert_dialog(frm, kind) {
	source_options(frm, kind).then((options) => {
		const dialog = new frappe.ui.Dialog({
			title: { field: __("Chèn trường"), block: __("Chèn khối"), snippet: __("Chèn mẫu dùng chung") }[
				kind
			],
			fields: [
				{
					fieldname: "target",
					fieldtype: "Select",
					label: __("Chèn vào ô"),
					options: TARGETS.map((t) => ({ value: t.value, label: t.label })),
					default: "body_template",
					reqd: 1,
				},
				{
					fieldname: "value",
					fieldtype: "Autocomplete",
					label: __("Chọn"),
					options: options,
					reqd: 1,
				},
			],
			primary_action_label: __("Chèn"),
			primary_action(values) {
				const snippet = build_snippet(kind, values.value);
				const current = frm.doc[values.target] || "";
				frm.set_value(values.target, `${current}${current ? "\n" : ""}${snippet}`);
				dialog.hide();
			},
		});
		dialog.show();
	});
}

function build_snippet(kind, value) {
	if (kind === "field") return `{{ truong("${value}") }}`;
	if (kind === "block") return `{{ ${value} }}`;
	return `{{ mau("${value}") }}`;
}

function source_options(frm, kind) {
	if (kind === "block") {
		return Promise.resolve(BLOCKS.map((b) => ({ value: b.value, label: b.label })));
	}

	if (kind === "snippet") {
		return frappe.db
			.get_list("Supply Notification Snippet", { fields: ["name", "scope"], limit: 100 })
			.then((rows) => rows.map((row) => ({ value: row.name, description: row.scope })));
	}

	return frappe
		.call("erpnext.supply_notification.preview.field_options", { doctype: frm.doc.reference_doctype })
		.then((r) => (r.message || []).map((row) => ({ value: row.value, label: row.label })));
}

function copy_point(frm) {
	frappe.prompt(
		{ fieldname: "code", fieldtype: "Data", label: __("Mã điểm mới"), reqd: 1 },
		(values) => {
			frappe.model.with_doc("Supply Notification Point", frm.doc.name).then(() => {
				const copy = frappe.model.copy_doc(frm.doc);
				copy.code = values.code;
				copy.title = `${frm.doc.title} (bản sao)`;
				copy.enabled = 0;
				copy.is_seed = 0;
				frappe.set_route("Form", "Supply Notification Point", copy.name);
			});
		},
		__("Sao chép điểm"),
		__("Tạo bản sao")
	);
}

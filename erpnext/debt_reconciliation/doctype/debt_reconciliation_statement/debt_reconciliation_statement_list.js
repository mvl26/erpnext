// Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

const DR_STATUS_COLORS = {
	Nháp: "gray",
	"Đã duyệt": "blue",
	"Đã gửi": "cyan",
	"Lỗi gửi": "red",
	"Đã đối soát khớp": "purple",
	"Chênh lệch": "orange",
	"Đã xác nhận": "green",
	"Đã hủy": "red",
};

frappe.listview_settings["Debt Reconciliation Statement"] = {
	add_fields: ["status", "response_deadline", "partner_response", "docstatus"],
	has_indicator_for_draft: 1,

	get_indicator(doc) {
		// "Quá hạn" là cờ, không phải trạng thái (FR-06)
		if (
			doc.docstatus === 1 &&
			doc.partner_response === "Chưa phản hồi" &&
			doc.response_deadline &&
			doc.response_deadline < frappe.datetime.get_today() &&
			["Đã gửi", "Lỗi gửi"].includes(doc.status)
		) {
			return [__("Quá hạn"), "red", "response_deadline,<," + frappe.datetime.get_today()];
		}
		return [__(doc.status), DR_STATUS_COLORS[doc.status] || "gray", "status,=," + doc.status];
	},

	onload(listview) {
		listview.page.add_inner_button(__("Sinh biên bản kỳ"), () => show_generate_dialog(listview));

		if (frappe.user.has_role("Accounts Manager")) {
			listview.page.add_action_item(__("Duyệt & gửi"), () => {
				const names = listview.get_checked_items(true);
				if (!names.length) return;
				frappe.confirm(__("Duyệt và gửi email {0} biên bản đã chọn?", [names.length]), () => {
					frappe.call({
						method: "erpnext.debt_reconciliation.publishing.bulk_approve",
						args: { names },
						freeze: true,
						callback(r) {
							const res = r.message || { ok: [], failed: [] };
							let msg = __("Đã duyệt: {0}", [res.ok.length]);
							if (res.failed.length) {
								msg +=
									"<br>" +
									__("Lỗi: {0}", [res.failed.length]) +
									"<ul>" +
									res.failed
										.map(
											(f) => `<li>${f.name}: ${frappe.utils.escape_html(f.error)}</li>`
										)
										.join("") +
									"</ul>";
							}
							frappe.msgprint({ title: __("Duyệt & gửi"), message: msg });
							listview.refresh();
						},
					});
				});
			});
		}
	},
};

function show_generate_dialog(listview) {
	const first = frappe.datetime.month_start(frappe.datetime.add_months(frappe.datetime.get_today(), -1));
	const d = new frappe.ui.Dialog({
		title: __("Sinh biên bản kỳ"),
		fields: [
			{
				fieldname: "company",
				fieldtype: "Link",
				options: "Company",
				label: __("Công ty"),
				reqd: 1,
				default: frappe.defaults.get_user_default("Company"),
			},
			{ fieldname: "from_date", fieldtype: "Date", label: __("Từ ngày"), reqd: 1, default: first },
			{
				fieldname: "to_date",
				fieldtype: "Date",
				label: __("Đến ngày"),
				reqd: 1,
				default: frappe.datetime.month_end(first),
			},
			{ fieldname: "col", fieldtype: "Column Break" },
			{
				fieldname: "party_type",
				fieldtype: "Select",
				label: __("Loại đối tác"),
				options: [
					{ value: "Supplier", label: __("Nhà cung cấp (331)") },
					{ value: "Customer", label: __("Khách hàng (131)") },
				],
				default: "Supplier",
				reqd: 1,
				onchange: () => d.set_value("parties", []),
			},
			{
				fieldname: "parties",
				fieldtype: "MultiSelectList",
				label: __("Đối tác"),
				description: __("Để trống = mọi đối tác có số dư hoặc có phát sinh trong kỳ"),
				get_data(txt) {
					const party_type = d.get_value("party_type");
					return frappe.db.get_link_options(party_type, txt);
				},
			},
		],
		primary_action_label: __("Sinh biên bản"),
		primary_action(values) {
			frappe.call({
				method: "erpnext.debt_reconciliation.generation.generate_statements",
				args: values,
				freeze: true,
				freeze_message: __("Đang sinh biên bản..."),
				callback(r) {
					d.hide();
					show_generate_result(r.message || {});
					listview.refresh();
				},
			});
		},
	});
	d.fields_dict.from_date.df.onchange = () => {
		const from = d.get_value("from_date");
		if (from) {
			const start = frappe.datetime.month_start(from);
			if (start !== from) d.set_value("from_date", start);
			d.set_value("to_date", frappe.datetime.month_end(start));
		}
	};
	d.show();
}

function show_generate_result(res) {
	if (res.queued) {
		frappe.msgprint(__("Số đối tác lớn — đang sinh biên bản ở nền, hệ thống sẽ thông báo khi xong."));
		return;
	}
	const link = (r) => frappe.utils.get_form_link("Debt Reconciliation Statement", r.name, true);
	const rows = []
		.concat((res.created || []).map((r) => [r.party, __("Đã tạo"), link(r)]))
		.concat((res.existing || []).map((r) => [r.party, __("Đã có sẵn"), link(r)]))
		.concat((res.failed || []).map((r) => [r.party, __("Lỗi"), frappe.utils.escape_html(r.error)]));
	if (!rows.length) {
		frappe.msgprint(__("Không có đối tác nào đạt điều kiện trong kỳ."));
		return;
	}
	const body = rows
		.map((r) => `<tr><td>${frappe.utils.escape_html(r[0])}</td><td>${r[1]}</td><td>${r[2]}</td></tr>`)
		.join("");
	frappe.msgprint({
		title: __("Kết quả sinh biên bản"),
		message: `<table class="table table-bordered table-sm"><thead><tr><th>${__("Đối tác")}</th><th>${__(
			"Kết quả"
		)}</th><th></th></tr></thead><tbody>${body}</tbody></table>`,
		wide: true,
	});
}

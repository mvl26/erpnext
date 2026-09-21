// Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

frappe.ui.form.on("Debt Reconciliation Statement", {
	onload(frm) {
		if (frm.is_new() && !frm.doc.from_date) {
			const first = frappe.datetime.month_start(
				frappe.datetime.add_months(frappe.datetime.get_today(), -1)
			);
			frm.set_value("from_date", first);
			frm.set_value("to_date", frappe.datetime.month_end(first));
		}
	},

	refresh(frm) {
		const doc = frm.doc;
		const is_manager = frappe.user.has_role("Accounts Manager");

		if (doc.missing_party_warning && doc.docstatus === 0) {
			frm.dashboard.set_headline_alert(
				doc.missing_party_warning.split("\n").map(frappe.utils.escape_html).join("<br>"),
				"orange"
			);
		}

		if (doc.docstatus === 0 && !frm.is_new()) {
			frm.add_custom_button(__("Lấy số liệu từ sổ"), () => fetch_figures(frm));
			if (is_manager && doc.figures_fetched_on) {
				frm.page.set_primary_action(__("Duyệt"), () => frm.savesubmit());
			}
		}
		if (frm.is_new()) {
			frm.add_custom_button(__("Lấy số liệu từ sổ"), () => fetch_figures(frm));
		}

		if (doc.docstatus === 1 && is_manager) {
			if (doc.status === "Lỗi gửi") {
				frm.add_custom_button(__("Gửi lại"), () => resend(frm), __("Thao tác"));
			}
			if (doc.status === "Đã gửi") {
				frm.add_custom_button(
					__("Phản hồi: Khớp"),
					() => run_action(frm, "respond_match"),
					__("Thao tác")
				);
			}
			if (["Đã gửi", "Đã đối soát khớp"].includes(doc.status)) {
				frm.add_custom_button(__("Phản hồi: Chưa khớp"), () => respond_mismatch(frm), __("Thao tác"));
			}
			if (["Đã gửi", "Đã đối soát khớp", "Chênh lệch"].includes(doc.status)) {
				frm.add_custom_button(__("Xác nhận"), () => confirm_statement(frm), __("Thao tác"));
			}
		}

		if (doc.party && doc.from_date && doc.to_date) {
			frm.add_custom_button(__("Xem sổ công nợ đối tác"), () => {
				frappe.set_route("query-report", "So Chi Tiet Cong No", {
					company: doc.company,
					from_date: doc.from_date,
					to_date: doc.to_date,
					party_type: doc.party_type,
					party: doc.party,
				});
			});
		}
	},

	party_type(frm) {
		frm.set_value("party", null);
	},

	party(frm) {
		if (!frm.doc.party) return;
		frm.call({ doc: frm.doc, method: "set_party_details" }).then(() => frm.refresh_fields());
	},

	from_date(frm) {
		if (frm.doc.from_date) {
			const first = frappe.datetime.month_start(frm.doc.from_date);
			if (first !== frm.doc.from_date) frm.set_value("from_date", first);
			frm.set_value("to_date", frappe.datetime.month_end(first));
		}
	},
});

function fetch_figures(frm) {
	const missing = ["company", "party_type", "party", "from_date", "to_date"].filter((f) => !frm.doc[f]);
	if (missing.length) {
		frappe.msgprint(__("Nhập đủ Công ty, Loại đối tác, Đối tác và Kỳ đối chiếu trước."));
		return;
	}
	frappe.call({
		method: "erpnext.debt_reconciliation.generation.find_existing_statement",
		args: {
			party_type: frm.doc.party_type,
			party: frm.doc.party,
			from_date: frm.doc.from_date,
			to_date: frm.doc.to_date,
			exclude: frm.is_new() ? null : frm.doc.name,
		},
		callback(r) {
			if (r.message) {
				// R-b: đã có biên bản kỳ này → mở bản đang có, không tạo bản thứ hai
				frappe.msgprint({
					title: __("Đã có biên bản"),
					message: __("Đối tác đã có biên bản {0} cho kỳ này — mở biên bản đang có.", [r.message]),
					indicator: "orange",
				});
				frappe.set_route("Form", "Debt Reconciliation Statement", r.message);
				return;
			}
			frm.call({ doc: frm.doc, method: "fetch_figures", freeze: true }).then(() => {
				frm.dirty();
				frm.save();
			});
		},
	});
}

function run_action(frm, action, data) {
	return frm
		.call({ doc: frm.doc, method: "apply_action", args: { action, ...(data || {}) }, freeze: true })
		.then(() => frm.reload_doc());
}

function resend(frm) {
	const d = new frappe.ui.Dialog({
		title: __("Gửi lại biên bản"),
		fields: [
			{
				fieldname: "email",
				fieldtype: "Data",
				options: "Email",
				label: __("Email nhận đối chiếu"),
				default: frm.doc.reconciliation_email,
				reqd: 1,
			},
		],
		primary_action_label: __("Gửi lại"),
		primary_action(values) {
			d.hide();
			run_action(frm, "resend", values);
		},
	});
	d.show();
}

function respond_mismatch(frm) {
	const d = new frappe.ui.Dialog({
		title: __("Đối tác phản hồi: Chưa khớp"),
		fields: [
			{ fieldname: "dispute_amount", fieldtype: "Currency", label: __("Số theo đối tác"), reqd: 1 },
			{
				fieldname: "dispute_note",
				fieldtype: "Small Text",
				label: __("Diễn giải chênh lệch"),
				reqd: 1,
			},
			{
				fieldname: "responded_on",
				fieldtype: "Date",
				label: __("Ngày phản hồi"),
				default: frappe.datetime.get_today(),
			},
		],
		primary_action_label: __("Ghi nhận chênh lệch"),
		primary_action(values) {
			d.hide();
			run_action(frm, "respond_mismatch", values);
		},
	});
	d.show();
}

function confirm_statement(frm) {
	const d = new frappe.ui.Dialog({
		title: __("Xác nhận công nợ"),
		fields: [
			{
				fieldname: "confirmation_method",
				fieldtype: "Select",
				label: __("Cách xác nhận"),
				options: ["", "C1 - Bản cứng", "C2 - Ký điện tử"],
				reqd: 1,
			},
			{ fieldname: "signed_copy", fieldtype: "Attach", label: __("Bản xác nhận có ký"), reqd: 1 },
			{
				fieldname: "confirmed_on",
				fieldtype: "Date",
				label: __("Ngày xác nhận"),
				default: frappe.datetime.get_today(),
			},
			{
				fieldname: "dispute_resolution",
				fieldtype: "Small Text",
				label: __("Kết quả xử lý chênh lệch"),
				depends_on: `eval:${frm.doc.status === "Chênh lệch"}`,
			},
		],
		primary_action_label: __("Xác nhận"),
		primary_action(values) {
			d.hide();
			run_action(frm, "confirm", values);
		},
	});
	d.show();
}

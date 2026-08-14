// Copyright (c) 2026, Công ty TNHH Miyano Việt Nam
//
// Form chứng từ hóa đơn điện tử Fast.
//
// Script này cố tình "mỏng": nút nào hiện ở trạng thái nào, cấp xác nhận ra sao
// đều do server trả về qua `get_form_state` (bảng B2). Nhân bản bảng đó ở đây là
// mở đường cho giao diện và server nói hai điều khác nhau.
//
// Phần tính tiền cũng theo đúng nguyên tắc đó: ở đây chỉ có **khi nào** tính lại,
// còn **tính thế nào** thì gọi `einvoice.totals.preview_totals` trên server —
// cùng công thức mà lúc Lưu server chạy. Viết lại công thức bằng JavaScript sẽ
// nhanh hơn một nhịp mạng, nhưng đổi lại là hai công thức, và cái giá của việc
// form hiện một số rồi chứng từ lưu một số khác thì đắt hơn nhiều.

frappe.ui.form.on("Fast EInvoice Document", {
	refresh(frm) {
		apply_totals_lock(frm);
		render_override_banner(frm);
		if (frm.is_new()) return;
		frm.trigger("load_einvoice_state");
	},

	async load_einvoice_state(frm) {
		const { message: state } = await frappe.call({
			method: "erpnext.einvoice.form_state.get_form_state",
			args: { fei: frm.doc.name },
		});
		if (!state) return;

		frm.einvoice_state = state;
		render_banner(frm, state);
		render_validation(frm, state);
		render_buttons(frm, state);
	},

	// Đổi loại tiền là đổi số chữ số thập phân của mọi con số trên chứng từ.
	currency: recalculate_totals,
	deduction_amount: recalculate_totals,
	deduction_amount_other: recalculate_totals,

	lines_add: recalculate_totals,
	lines_remove: recalculate_totals,

	totals_manual_override(frm) {
		apply_totals_lock(frm);
		recalculate_totals(frm);
	},
});

// --- Tính lại số liệu khi đang gõ (server giữ công thức) ---------------------

// Trường nào của dòng hàng thay đổi thì tổng hợp phải đổi theo.
const LINE_INPUTS = [
	"qty",
	"price",
	"discount_rate",
	"discount_amount",
	"tax_rate",
	"process_type",
	"is_promotion",
];

frappe.ui.form.on(
	"Fast EInvoice Line",
	Object.fromEntries(LINE_INPUTS.map((fieldname) => [fieldname, (frm) => recalculate_totals(frm)]))
);

const request_totals = frappe.utils.debounce((frm) => {
	frappe.call({
		method: "erpnext.einvoice.totals.preview_totals",
		args: { doc: frm.doc },
		callback({ message }) {
			if (message) apply_totals(frm, message);
		},
	});
}, 300);

function recalculate_totals(frm) {
	// Hóa đơn đã khóa: số liệu là chứng từ pháp lý. Đang ghi đè: kế toán tự nhập.
	if (frm.doc.is_edit_locked || frm.doc.totals_manual_override) return;
	request_totals(frm);
}

function apply_totals(frm, totals) {
	// Gán thẳng vào `frm.doc` chứ không qua `set_value`: đây chỉ là số để **xem**.
	// Lúc Lưu, server tính lại từ đầu, nên số form hiện ra không thể lọt vào cơ sở
	// dữ liệu — và cũng không kích hoạt lại vòng tính khi vừa gán xong.
	Object.assign(frm.doc, totals.master);
	for (const values of totals.lines) {
		const row = (frm.doc.lines || []).find((line) => line.idx === values.idx);
		if (row) Object.assign(row, values);
	}

	for (const fieldname of Object.keys(totals.master)) frm.refresh_field(fieldname);
	frm.refresh_field("lines");
}

// --- Ghi đè số tổng hợp bằng tay --------------------------------------------

function apply_totals_lock(frm) {
	// `read_only_depends_on` lo phần master; bảng dòng hàng phải mở/khóa bằng tay.
	const grid = frm.fields_dict.lines && frm.fields_dict.lines.grid;
	if (!grid) return;
	const editable = frm.doc.totals_manual_override && !frm.doc.is_edit_locked;
	for (const fieldname of ["amount", "tax_amount"]) {
		grid.update_docfield_property(fieldname, "read_only", editable ? 0 : 1);
	}
}

function render_override_banner(frm) {
	if (!frm.doc.totals_manual_override) return;
	frm.dashboard.add_comment(
		__("Số tổng hợp đang GHI ĐÈ bằng tay — chứng từ không tự tính. Lý do: {0}", [
			frm.doc.override_reason || __("(chưa ghi)"),
		]),
		"red",
		true
	);
}

// --- Banner môi trường (nguyên tắc A4) --------------------------------------

function render_banner(frm, state) {
	if (!state.enabled) {
		frm.dashboard.add_comment(
			__("Tích hợp hóa đơn điện tử đang tắt trong Fast EInvoice Settings."),
			"orange",
			true
		);
		return;
	}
	frm.dashboard.add_comment(state.banner.message, state.banner.indicator, true);
}

// --- Bảng kết quả kiểm tra dữ liệu (Phần F) ---------------------------------

function render_validation(frm, state) {
	const issues = (state.validation && state.validation.issues) || [];
	if (!issues.length) return;

	const rows = issues
		.map((issue) => {
			const blocking = issue.level === "block";
			const colour = blocking ? "var(--red-500, #c0392b)" : "var(--orange-500, #d68910)";
			const tag = blocking ? __("Chặn") : __("Cảnh báo");
			return `
				<tr>
					<td style="white-space:nowrap;color:${colour}"><b>${tag}</b></td>
					<td><a href="#" data-fei-field="${frappe.utils.escape_html(issue.field || "")}">${frappe.utils.escape_html(
				issue.field || "—"
			)}</a></td>
					<td>${frappe.utils.escape_html(issue.message)}</td>
				</tr>`;
		})
		.join("");

	const html = `
		<div class="fei-validation">
			<table class="table table-bordered" style="margin-bottom:0">
				<thead><tr>
					<th style="width:90px">${__("Mức")}</th>
					<th style="width:180px">${__("Trường")}</th>
					<th>${__("Nội dung")}</th>
				</tr></thead>
				<tbody>${rows}</tbody>
			</table>
		</div>`;

	frm.dashboard.add_section(html, __("Kiểm tra dữ liệu trước khi gửi Fast"));
	frm.dashboard.wrapper.find("[data-fei-field]").on("click", function (event) {
		event.preventDefault();
		const field = $(this).data("fei-field");
		if (field && frm.fields_dict[field]) frappe.utils.scroll_to(frm.fields_dict[field].$wrapper);
	});
}

// --- Nút theo trạng thái (bảng B2) ------------------------------------------

function render_buttons(frm, state) {
	for (const button of state.buttons) {
		frm.add_custom_button(button.label, () => run_button(frm, button), button_group(button));
		if (button.name === "issue") {
			frm.change_custom_button_type(button.label, null, "danger");
		}
	}
}

function button_group(button) {
	if (["issue", "cancel"].includes(button.name)) return null;
	if (["create_adjustment", "create_replacement"].includes(button.name)) return __("Điều chỉnh");
	return __("Hóa đơn điện tử");
}

function run_button(frm, button) {
	if (button.level === 3) return confirm_level_three(frm, button);
	if (button.level === 2) return prompt_level_two(frm, button);
	return confirm_level_one(frm, button);
}

// Cấp 1 — hộp thoại Có/Không.
function confirm_level_one(frm, button) {
	frappe.confirm(__("Thực hiện: <b>{0}</b>?", [button.label]), () => call_action(frm, button, {}));
}

// Cấp 2 — nhập/sửa thông tin rồi mới chạy.
function prompt_level_two(frm, button) {
	const fields = level_two_fields(frm, button);
	if (!fields.length) return call_action(frm, button, {});

	frappe.prompt(fields, (values) => call_action(frm, button, values), button.label, __("Thực hiện"));
}

function level_two_fields(frm, button) {
	switch (button.name) {
		case "send_draft":
			return [
				{
					fieldname: "recipients",
					label: __("Người nhận"),
					fieldtype: "Data",
					reqd: 1,
					default: frm.doc.email_deliver,
				},
				{ fieldname: "cc", label: __("CC"), fieldtype: "Data" },
				{
					fieldname: "note_html",
					fieldtype: "HTML",
					options: `<p class="text-muted">${__(
						"Email sẽ ghi rõ đây là BẢN NHÁP, chưa có số hóa đơn và chưa có giá trị pháp lý."
					)}</p>`,
				},
			];
		case "record_feedback":
			return [
				{
					fieldname: "feedback",
					label: __("Khách yêu cầu sửa gì"),
					fieldtype: "Small Text",
					reqd: 1,
					description: __("Tối thiểu 10 ký tự. Nội dung được ghi nối vào lịch sử, không ghi đè."),
				},
			];
		case "override_totals":
			return [
				{
					fieldname: "reason",
					label: __("Vì sao phải ghi đè"),
					fieldtype: "Small Text",
					reqd: 1,
					description: __("Tối thiểu 10 ký tự. Ghi lại trên chứng từ để về sau giải thích được."),
				},
				{
					fieldname: "hint",
					fieldtype: "HTML",
					options: `<p class="text-muted">${__(
						"Chứng từ sẽ NGỪNG tự tính: sửa dòng hàng không còn làm đổi số tổng hợp. Phần kiểm tra dữ liệu sẽ báo cảnh báo cho tới khi bỏ ghi đè."
					)}</p>`,
				},
			];
		case "mark_approved":
			return [
				{
					fieldname: "approved_by",
					label: __("Người bên khách hàng đã xác nhận"),
					fieldtype: "Data",
					reqd: 1,
				},
				{
					fieldname: "channel",
					label: __("Hình thức xác nhận"),
					fieldtype: "Select",
					options: ["Email", "Điện thoại", "Văn bản", "Trực tiếp"].join("\n"),
					default: "Email",
					reqd: 1,
				},
			];
		case "download_converted_pdf":
			return [
				{
					fieldname: "convert_name",
					label: __("Tên người chuyển đổi"),
					fieldtype: "Data",
					reqd: 1,
					default: frappe.session.user_fullname,
					description: __("Bản in giấy hợp lệ bắt buộc ghi tên này."),
				},
			];
		case "send_invoice":
			return [
				{
					fieldname: "recipients",
					label: __("Người nhận"),
					fieldtype: "Data",
					reqd: 1,
					default: frm.doc.email_deliver,
				},
				{ fieldname: "cc", label: __("CC"), fieldtype: "Data" },
				{
					fieldname: "via",
					label: __("Gửi bằng"),
					fieldtype: "Select",
					options: [
						{ label: __("ERP tự gửi (khuyến nghị)"), value: "erp" },
						{ label: __("Nhờ Fast gửi"), value: "fast" },
					],
					default: "erp",
				},
			];
		case "create_adjustment":
			return [
				{
					fieldname: "adjustment_type",
					label: __("Loại điều chỉnh"),
					fieldtype: "Select",
					options: ["1 - Điều chỉnh giảm", "2 - Điều chỉnh tăng", "3 - Điều chỉnh thông tin"].join(
						"\n"
					),
					reqd: 1,
				},
				{ fieldname: "reason", label: __("Lý do"), fieldtype: "Small Text", reqd: 1 },
				{ fieldname: "minute_no", label: __("Số biên bản"), fieldtype: "Data" },
				{ fieldname: "minute_date", label: __("Ngày biên bản"), fieldtype: "Date" },
				{
					fieldname: "hint",
					fieldtype: "HTML",
					options: `<p class="text-muted">${__(
						"Hóa đơn điều chỉnh giảm: nhập số <b>âm</b> ở các dòng cần giảm."
					)}</p>`,
				},
			];
		case "create_replacement":
			return [
				{ fieldname: "reason", label: __("Lý do thay thế"), fieldtype: "Small Text", reqd: 1 },
				{ fieldname: "minute_no", label: __("Số biên bản"), fieldtype: "Data" },
				{ fieldname: "minute_date", label: __("Ngày biên bản"), fieldtype: "Date" },
				{
					fieldname: "hint",
					fieldtype: "HTML",
					options: `<p class="text-muted">${__(
						"Hóa đơn thay thế: nhập lại <b>toàn bộ</b> nội dung đúng."
					)}</p>`,
				},
			];
		default:
			return [];
	}
}

// Cấp 3 — bảng tóm tắt toàn màn hình, phải gõ đúng chữ mới bật nút.
function confirm_level_three(frm, button) {
	const word = button.confirm_word;
	const extra =
		button.name === "cancel"
			? [
					{
						fieldname: "reason",
						label: __("Lý do hủy"),
						fieldtype: "Small Text",
						reqd: 1,
					},
					{ fieldname: "minute_no", label: __("Số biên bản"), fieldtype: "Data" },
					{ fieldname: "minute_date", label: __("Ngày biên bản"), fieldtype: "Date" },
			  ]
			: [];

	const dialog = new frappe.ui.Dialog({
		title: button.label,
		size: "large",
		fields: [
			{ fieldname: "summary", fieldtype: "HTML", options: summary_html(frm, button) },
			...extra,
			{
				fieldname: "confirm_word",
				label: __("Gõ chính xác {0} để xác nhận", [word]),
				fieldtype: "Data",
				reqd: 1,
			},
		],
		primary_action_label: button.label,
		primary_action(values) {
			if ((values.confirm_word || "").trim().toUpperCase() !== word) {
				frappe.msgprint(__("Chưa gõ đúng chữ {0}.", [word]));
				return;
			}
			delete values.confirm_word;
			dialog.hide();
			call_action(frm, button, values);
		},
	});

	dialog.show();
	dialog.get_primary_btn().addClass("btn-danger");
}

function summary_html(frm, button) {
	const doc = frm.doc;
	const money = (value) => format_currency(value, doc.currency);
	const banner = frm.einvoice_state.banner;

	const rows = [
		[__("Khách hàng"), doc.customer_name],
		[__("Mã số thuế"), doc.customer_tax_code || "—"],
		[__("Địa chỉ"), doc.address],
		[__("Ngày hóa đơn"), frappe.datetime.str_to_user(doc.invoice_date)],
		[__("Số dòng hàng"), `${(doc.lines || []).length} ${__("dòng")}`],
		[__("Tiền hàng"), money(doc.amount)],
		[__("Tiền thuế"), money(doc.tax_amount)],
		[__("TỔNG THANH TOÁN"), `<b>${money(doc.total_amount)}</b>`],
		[__("Bằng chữ"), doc.amount_in_words],
	];

	if (button.name === "cancel") {
		rows.push([__("Số hóa đơn"), doc.fast_invoice_no]);
		rows.push([__("Lý do CQT từ chối"), doc.tax_feedback || "—"]);
	} else {
		rows.push([__("Khách duyệt"), doc.customer_approved_by || __("(bỏ qua bước duyệt)")]);
	}

	const body = rows
		.map(
			([label, value]) =>
				`<tr><td style="width:200px;color:var(--text-muted)">${label}</td><td>${
					value === undefined || value === null ? "" : value
				}</td></tr>`
		)
		.join("");

	const warning =
		button.name === "cancel"
			? __("Hủy xong không khôi phục được. Chỉ dùng cho hóa đơn bị Cơ quan Thuế từ chối.")
			: __(
					"Sau khi phát hành: hóa đơn được ký số HSM, cấp số chính thức và gửi lên Cơ quan Thuế. KHÔNG THỂ XÓA hoặc sửa. Muốn thay đổi phải lập hóa đơn điều chỉnh hoặc thay thế."
			  );

	return `
		<div class="alert alert-${banner.indicator === "red" ? "danger" : "warning"}">
			<b>${banner.message}</b>
		</div>
		<table class="table table-bordered">${body}</table>
		<div class="alert alert-danger">${warning}</div>`;
}

// --- Gọi server -------------------------------------------------------------

function call_action(frm, button, args) {
	frappe.call({
		method: button.method,
		args: { fei: frm.doc.name, ...args },
		freeze: true,
		freeze_message: __("Đang xử lý…"),
		callback(response) {
			const result = response.message || {};
			if (result.message) {
				frappe.msgprint(result.message, button.label);
			}
			if (result.file_url) {
				window.open(result.file_url, "_blank");
			}
			frm.reload_doc();
		},
	});
}

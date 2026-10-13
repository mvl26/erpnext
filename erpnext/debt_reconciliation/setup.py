# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Cài đặt module Đối chiếu công nợ — idempotent, chạy lại nhiều lần không lỗi."""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from erpnext.debt_reconciliation import constants as C


def _party_fields():
	fields = [
		{
			"fieldname": "dr_section",
			"label": "Đối chiếu công nợ",
			"fieldtype": "Section Break",
			"insert_after": "tax_id",
			"collapsible": 1,
		},
		{"fieldname": "framework_contract_no", "label": "Số HĐ nguyên tắc", "fieldtype": "Data"},
		{"fieldname": "framework_contract_date", "label": "Ngày HĐ nguyên tắc", "fieldtype": "Date"},
		{"fieldname": "representative_name", "label": "Người đại diện", "fieldtype": "Data"},
		{"fieldname": "dr_column_break", "fieldtype": "Column Break"},
		{"fieldname": "representative_title", "label": "Chức vụ người đại diện", "fieldtype": "Data"},
		{
			"fieldname": "reconciliation_email",
			"label": "Email nhận đối chiếu",
			"fieldtype": "Data",
			"options": "Email",
			"description": "Để trống = dùng Email ID của đối tác",
		},
		{
			"fieldname": "exclude_reconciliation",
			"label": "Loại trừ đối chiếu",
			"fieldtype": "Check",
			"description": "Không tự sinh biên bản đối chiếu công nợ hàng tháng",
		},
	]
	previous = None
	for field in fields:
		field["module"] = "Debt Reconciliation"
		if previous:
			field["insert_after"] = previous
		previous = field["fieldname"]
	return fields


CUSTOM_FIELDS = {"Supplier": _party_fields(), "Customer": _party_fields()}

EMAIL_TEMPLATE_SUBJECT = (
	"Biên bản đối chiếu công nợ tháng {{ frappe.utils.getdate(doc.to_date).strftime('%m/%Y') }}"
	" - {{ doc.company }} / {{ doc.party_name }}"
)

EMAIL_TEMPLATE_BODY = """<p>Kính gửi Quý công ty <b>{{ doc.party_name }}</b>,</p>
<p>{{ doc.company }} gửi Quý công ty Biên bản đối chiếu &amp; xác nhận công nợ
từ ngày {{ frappe.utils.formatdate(doc.from_date, "dd/MM/yyyy") }}
đến ngày {{ frappe.utils.formatdate(doc.to_date, "dd/MM/yyyy") }} (file PDF đính kèm).</p>
<p>Kính đề nghị Quý công ty kiểm tra số liệu và <b>phản hồi kết quả đối soát, đồng thời gửi bản xác nhận
có ký trước ngày {{ frappe.utils.formatdate(doc.response_deadline, "dd/MM/yyyy") }}</b>
theo một trong hai cách:</p>
<ol>
<li><b>C1 - Bản cứng:</b> in, ký, đóng dấu và gửi về địa chỉ:
{{ settings.hard_copy_address or "" }}{% if settings.contact_line %} (liên hệ: {{ settings.contact_line }}){% endif %};</li>
<li><b>C2 - Ký điện tử:</b> ký số file PDF và gửi lại qua email này.</li>
</ol>
<p>Nếu số liệu có chênh lệch, xin Quý công ty phản hồi kèm diễn giải để hai bên cùng đối chiếu.</p>
<p>Trân trọng,<br>{{ doc.company }}</p>"""

SETTINGS_DEFAULTS = {
	"auto_generate": 1,
	"generation_day": 1,
	"generation_hour": 10,
	"response_deadline_day": 6,
	"payable_account_number": "331",
	"receivable_account_number": "131",
	"company_legal_name": "CÔNG TY TNHH MIYANO VIỆT NAM",
	"company_address": "Số 20, Khu C17, ngõ 264/63, đường Ngọc Thụy, Phường Bồ Đề, Thành phố Hà Nội, Việt Nam",
	"company_phone": "0988806848",
	"company_tax_id": "0109529507",
	"company_representative": "Bà Đoàn Ngọc Anh",
	"company_representative_title": "Giám đốc vận hành",
	"contact_line": "Ms Hà 0949.723.444",
	"hard_copy_address": "LK21. N03 Ngõ 1 Phố Lâm Hạ, Phường Bồ Đề, Thành phố Hà Nội, Việt Nam",
	"company_email": "mvl.invoices2024@gmail.com",
	"email_template": C.EMAIL_TEMPLATE,
}


def run():
	create_custom_fields(CUSTOM_FIELDS, update=True)
	make_email_template()
	set_settings_defaults()


def make_email_template():
	if frappe.db.exists("Email Template", C.EMAIL_TEMPLATE):
		return
	frappe.get_doc(
		{
			"doctype": "Email Template",
			"__newname": C.EMAIL_TEMPLATE,
			"subject": EMAIL_TEMPLATE_SUBJECT,
			"use_html": 1,
			"response_html": EMAIL_TEMPLATE_BODY,
		}
	).insert(ignore_permissions=True)


def set_settings_defaults():
	"""Chỉ điền field còn trống — không ghi đè giá trị người dùng đã sửa."""
	settings = frappe.get_single(C.SETTINGS)
	changed = False
	for fieldname, value in SETTINGS_DEFAULTS.items():
		if settings.get(fieldname) in (None, ""):
			settings.set(fieldname, value)
			changed = True
	if changed or settings.is_new():
		settings.flags.ignore_permissions = True
		settings.save()

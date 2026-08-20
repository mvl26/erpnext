# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Dựng custom field trên Delivery Note (mục C5) và hai Role của Giai đoạn 2.

Chạy được nhiều lần: gọi lại không nhân đôi trường hay quyền. Được gọi từ patch
(cho site đang chạy) và từ VN company setup (cho công ty mới).
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.permissions import add_permission, update_permission_property

from erpnext.einvoice.constants import STATUSES

# Kế toán làm nháp, gửi khách, xem PDF. Kế toán trưởng thêm quyền phát hành,
# điều chỉnh, thay thế, hủy — tức là mọi hành động tiêu số hóa đơn thật.
ROLE_STAFF = "Kế toán HĐĐT"
ROLE_CHIEF = "Kế toán trưởng HĐĐT"

DELIVERY_NOTE_STATUS_OPTIONS = "\n".join(("", *STATUSES))


DRAFT_TEMPLATE = "Fast HĐĐT - Bản nháp gửi khách"
ISSUED_TEMPLATE = "Fast HĐĐT - Hóa đơn chính thức"


def setup_einvoice():
	_make_delivery_note_fields()
	_make_roles()
	_grant_permissions()
	_make_email_templates()


def _make_email_templates():
	"""Hai mẫu email của mục E3 / E7.

	Mẫu bản nháp **bắt buộc** có dòng cảnh báo chưa có giá trị pháp lý: bản PDF ở
	trạng thái 01—04 chưa có số hóa đơn, chưa ký số, chưa lên Cơ quan Thuế. Gửi
	đi mà không nói rõ là để khách hiểu nhầm đã có hóa đơn.
	"""
	templates = (
		(
			DRAFT_TEMPLATE,
			"[BẢN NHÁP hóa đơn] {{ doc.delivery_note }} — Miyano Việt Nam",
			"""<p>Kính gửi Quý khách,</p>
<p>Công ty TNHH Miyano Việt Nam xin gửi <b>BẢN NHÁP</b> hóa đơn cho phiếu giao
<b>{{ doc.delivery_note }}</b> để Quý khách kiểm tra thông tin: tên đơn vị, mã số thuế,
địa chỉ, tên hàng, số lượng, đơn giá và thuế suất.</p>
<table cellpadding="4">
<tr><td>Đơn vị mua</td><td><b>{{ doc.customer_name }}</b></td></tr>
<tr><td>Mã số thuế</td><td>{{ doc.customer_tax_code or "—" }}</td></tr>
<tr><td>Địa chỉ</td><td>{{ doc.address }}</td></tr>
<tr><td>Tiền hàng</td><td>{{ frappe.format_value(doc.amount, {"fieldtype": "Currency"}) }}</td></tr>
<tr><td>Tiền thuế</td><td>{{ frappe.format_value(doc.tax_amount, {"fieldtype": "Currency"}) }}</td></tr>
<tr><td>Tổng thanh toán</td><td><b>{{ frappe.format_value(doc.total_amount, {"fieldtype": "Currency"}) }}</b></td></tr>
<tr><td>Bằng chữ</td><td>{{ doc.amount_in_words }}</td></tr>
</table>
<p style="color:#b00"><b>Lưu ý: đây là BẢN NHÁP, chưa có số hóa đơn và CHƯA CÓ GIÁ TRỊ PHÁP LÝ.</b>
Sau khi Quý khách xác nhận thông tin chính xác, chúng tôi sẽ phát hành hóa đơn điện tử
chính thức và gửi lại.</p>
<p>Mọi điều chỉnh xin phản hồi lại email này.</p>
<p>Trân trọng,<br>Công ty TNHH Miyano Việt Nam</p>""",
		),
		(
			ISSUED_TEMPLATE,
			"[Hóa đơn điện tử] Số {{ doc.fast_invoice_no }} — Miyano Việt Nam",
			"""<p>Kính gửi Quý khách,</p>
<p>Công ty TNHH Miyano Việt Nam xin gửi hóa đơn điện tử cho phiếu giao
<b>{{ doc.delivery_note }}</b>.</p>
<table cellpadding="4">
<tr><td>Số hóa đơn</td><td><b>{{ doc.fast_invoice_no }}</b></td></tr>
<tr><td>Ký hiệu</td><td>{{ doc.fast_serial }}</td></tr>
<tr><td>Mẫu số</td><td>{{ doc.fast_pattern }}</td></tr>
<tr><td>Ngày phát hành</td><td>{{ frappe.format_value(doc.fast_signed_date, {"fieldtype": "Date"}) }}</td></tr>
<tr><td>Mã tra cứu</td><td><b>{{ doc.fast_key_search }}</b></td></tr>
<tr><td>Tổng thanh toán</td><td><b>{{ frappe.format_value(doc.total_amount, {"fieldtype": "Currency"}) }}</b></td></tr>
<tr><td>Bằng chữ</td><td>{{ doc.amount_in_words }}</td></tr>
</table>
<p>Quý khách có thể dùng <b>mã tra cứu</b> ở trên để tra cứu hóa đơn trên cổng của
nhà cung cấp dịch vụ hóa đơn điện tử.</p>
<p>Trân trọng,<br>Công ty TNHH Miyano Việt Nam</p>""",
		),
	)

	for name, subject, response in templates:
		if frappe.db.exists("Email Template", name):
			continue
		doc = frappe.get_doc(
			{
				"doctype": "Email Template",
				"name": name,
				"subject": subject,
				"use_html": 1,
				"response_html": response,
				"response": response,
			}
		)
		doc.flags.ignore_permissions = True
		doc.insert()


def _make_delivery_note_fields():
	"""Mục C5 — bản sao trạng thái HĐĐT ngay trên phiếu giao hàng."""
	create_custom_fields(
		{
			"Delivery Note": [
				dict(
					fieldname="fast_einvoice_section",
					fieldtype="Section Break",
					label="Hóa đơn điện tử",
					insert_after="is_return",
					collapsible=1,
				),
				dict(
					fieldname="fast_einvoice",
					fieldtype="Link",
					label="Chứng từ HĐĐT",
					options="Fast EInvoice Document",
					insert_after="fast_einvoice_section",
					read_only=1,
					no_copy=1,
				),
				dict(
					fieldname="fast_invoice_no",
					fieldtype="Data",
					label="Số hóa đơn điện tử",
					insert_after="fast_einvoice",
					read_only=1,
					no_copy=1,
					in_standard_filter=1,
				),
				dict(
					fieldname="fast_einvoice_column",
					fieldtype="Column Break",
					insert_after="fast_invoice_no",
				),
				dict(
					fieldname="fast_einvoice_status",
					fieldtype="Select",
					label="Trạng thái HĐĐT",
					options=DELIVERY_NOTE_STATUS_OPTIONS,
					insert_after="fast_einvoice_column",
					read_only=1,
					no_copy=1,
					in_standard_filter=1,
				),
				dict(
					fieldname="fast_key_search",
					fieldtype="Data",
					label="Mã tra cứu",
					insert_after="fast_einvoice_status",
					read_only=1,
					no_copy=1,
					hidden=1,
					description="Bản sao dự phòng của keySearch, phòng khi chứng từ HĐĐT bị xóa.",
				),
			]
		},
		update=True,
	)


def _make_roles():
	for role in (ROLE_STAFF, ROLE_CHIEF):
		if not frappe.db.exists("Role", role):
			doc = frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1, "is_custom": 1})
			doc.flags.ignore_permissions = True
			doc.insert()


def _grant_permissions():
	"""Kế toán soạn hóa đơn; chỉ kế toán trưởng được xóa.

	Nhật ký chỉ đọc với cả hai role: log là bằng chứng đối chiếu với Fast và Cơ
	quan Thuế, sửa được thì hết là bằng chứng.
	"""
	matrix = (
		("Fast EInvoice Document", ROLE_STAFF, {"read": 1, "write": 1, "create": 1, "delete": 0}),
		("Fast EInvoice Document", ROLE_CHIEF, {"read": 1, "write": 1, "create": 1, "delete": 1}),
		("Fast EInvoice Log", ROLE_STAFF, {"read": 1, "write": 0, "create": 0, "delete": 0}),
		("Fast EInvoice Log", ROLE_CHIEF, {"read": 1, "write": 0, "create": 0, "delete": 0}),
		("Fast EInvoice Settings", ROLE_CHIEF, {"read": 1, "write": 0, "create": 0, "delete": 0}),
		("Fast EInvoice Settings", ROLE_STAFF, {"read": 1, "write": 0, "create": 0, "delete": 0}),
	)
	for doctype, role, properties in matrix:
		if not frappe.db.exists("DocType", doctype):
			continue
		add_permission(doctype, role, 0)
		for name, value in properties.items():
			update_permission_property(doctype, role, 0, name, value)


def is_chief_accountant(user=None):
	"""Ai được bấm các nút tiêu số hóa đơn thật (phát hành, hủy nội bộ)."""
	roles = frappe.get_roles(user or frappe.session.user)
	return ROLE_CHIEF in roles or "System Manager" in roles

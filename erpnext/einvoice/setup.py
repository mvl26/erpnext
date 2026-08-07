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


def setup_einvoice():
	_make_delivery_note_fields()
	_make_roles()
	_grant_permissions()


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
			doc = frappe.get_doc(
				{"doctype": "Role", "role_name": role, "desk_access": 1, "is_custom": 1}
			)
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

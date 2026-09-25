# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Địa chỉ giao hàng thiếu người nhận hoặc điện thoại (CR_01 mục 4).

Khối `dia_chi_giao_hang` lấy người nhận từ Liên hệ gắn với địa chỉ và điện thoại
từ chính địa chỉ. Thiếu thì email gửi NCC không có dòng người nhận — báo cáo này
liệt kê đúng những địa chỉ cần bổ sung, để nghiệp vụ tự dọn trước khi bật điểm.
"""

import frappe
from frappe import _


def execute(filters=None):
	return columns(), rows(filters or {})


def columns():
	return [
		{
			"fieldname": "address",
			"label": _("Địa chỉ"),
			"fieldtype": "Link",
			"options": "Address",
			"width": 240,
		},
		{"fieldname": "address_title", "label": _("Tên địa chỉ"), "fieldtype": "Data", "width": 200},
		{"fieldname": "address_type", "label": _("Loại"), "fieldtype": "Data", "width": 110},
		{"fieldname": "phone", "label": _("Điện thoại"), "fieldtype": "Data", "width": 140},
		{"fieldname": "contact", "label": _("Người nhận"), "fieldtype": "Data", "width": 200},
		{"fieldname": "missing", "label": _("Còn thiếu"), "fieldtype": "Data", "width": 220},
	]


def rows(filters):
	address_filters = {"disabled": 0}
	if filters.get("address_type"):
		address_filters["address_type"] = filters["address_type"]

	addresses = frappe.get_all(
		"Address",
		filters=address_filters,
		fields=["name", "address_title", "address_type", "phone"],
		order_by="address_title asc",
	)
	if not addresses:
		return []

	contacts = contact_names([row.name for row in addresses])

	result = []
	for row in addresses:
		contact = contacts.get(row.name, "")
		missing = []
		if not contact:
			missing.append(_("người nhận"))
		if not row.phone:
			missing.append(_("điện thoại"))

		if not missing:
			continue

		result.append(
			{
				"address": row.name,
				"address_title": row.address_title,
				"address_type": row.address_type,
				"phone": row.phone,
				"contact": contact,
				"missing": ", ".join(missing),
			}
		)

	return result


def contact_names(addresses: list[str]) -> dict[str, str]:
	rows = frappe.get_all(
		"Contact",
		filters={"address": ("in", addresses)},
		fields=["address", "first_name", "last_name"],
	)

	names = {}
	for row in rows:
		full_name = " ".join(part for part in (row.first_name, row.last_name) if part).strip()
		if full_name and row.address not in names:
			names[row.address] = full_name
	return names

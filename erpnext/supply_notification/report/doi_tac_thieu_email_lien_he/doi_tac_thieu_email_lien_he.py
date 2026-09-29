# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Nhà cung cấp và khách hàng chưa có email liên hệ (CR_01 mục 4).

Không có email thì điểm gửi ra ngoài chỉ ghi *Skipped* — im lặng với người dùng.
Báo cáo này nêu đích danh đối tác cần bổ sung, theo đúng thứ tự mà bộ giải mã
người nhận tra: liên hệ chính trước, hồ sơ đối tác sau.
"""

import frappe
from frappe import _

PARTY_TYPES = ("Supplier", "Customer")


def execute(filters=None):
	return columns(), rows(filters or {})


def columns():
	return [
		{"fieldname": "party_type", "label": _("Loại đối tác"), "fieldtype": "Data", "width": 120},
		{
			"fieldname": "party",
			"label": _("Đối tác"),
			"fieldtype": "Dynamic Link",
			"options": "party_type",
			"width": 260,
		},
		{"fieldname": "contacts", "label": _("Số liên hệ đã gắn"), "fieldtype": "Int", "width": 150},
		{"fieldname": "missing", "label": _("Còn thiếu"), "fieldtype": "Data", "width": 260},
	]


def rows(filters):
	wanted = [filters["party_type"]] if filters.get("party_type") else list(PARTY_TYPES)

	result = []
	for party_type in wanted:
		if not frappe.db.exists("DocType", party_type):
			continue

		for party in frappe.get_all(
			party_type, filters={"disabled": 0}, fields=["name", "email_id"], order_by="name asc"
		):
			contacts = contacts_of(party_type, party.name)
			if any(contact.email_id for contact in contacts):
				continue
			if party.email_id:
				continue

			result.append(
				{
					"party_type": party_type,
					"party": party.name,
					"contacts": len(contacts),
					"missing": _("Chưa liên hệ nào có email, hồ sơ đối tác cũng chưa có email."),
				}
			)

	return result


def contacts_of(party_type: str, party: str) -> list:
	names = frappe.get_all(
		"Dynamic Link",
		filters={"link_doctype": party_type, "link_name": party, "parenttype": "Contact"},
		pluck="parent",
	)
	if not names:
		return []

	return frappe.get_all("Contact", filters={"name": ("in", names)}, fields=["name", "email_id"])

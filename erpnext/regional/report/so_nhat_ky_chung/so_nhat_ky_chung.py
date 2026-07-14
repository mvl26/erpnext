# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

"""Sổ Nhật ký chung (VN general journal) — Thông tư 99/2025/TT-BTC.

Chronological list of every voucher line (Số hiệu TK, phát sinh Nợ/Có) with a
Cộng row. Read-only over the GL; Σ Nợ == Σ Có by double entry.
"""

import frappe
from frappe import _
from frappe.utils import flt

from erpnext.regional.vietnam.utils import get_gl_entries


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"label": _("Ngày ghi sổ"), "fieldname": "posting_date", "fieldtype": "Date", "width": 110},
		{
			"label": _("Số chứng từ"),
			"fieldname": "voucher_no",
			"fieldtype": "Dynamic Link",
			"options": "voucher_type",
			"width": 170,
		},
		{"label": _("Diễn giải"), "fieldname": "remarks", "fieldtype": "Data", "width": 260},
		{"label": _("Số hiệu TK"), "fieldname": "account_number", "fieldtype": "Data", "width": 100},
		{"label": _("Phát sinh Nợ"), "fieldname": "debit", "fieldtype": "Currency", "width": 140},
		{"label": _("Phát sinh Có"), "fieldname": "credit", "fieldtype": "Currency", "width": 140},
	]


def get_data(filters):
	if not (filters.company and filters.from_date and filters.to_date):
		return []

	number_map = dict(
		frappe.get_all(
			"Account",
			filters={"company": filters.company},
			fields=["name", "account_number"],
			as_list=True,
		)
	)

	entries = get_gl_entries(filters.company, filters.from_date, filters.to_date)
	rows = []
	total_debit = total_credit = 0.0
	for e in entries:
		total_debit += flt(e.debit)
		total_credit += flt(e.credit)
		rows.append(
			{
				"posting_date": e.posting_date,
				"voucher_type": e.voucher_type,
				"voucher_no": e.voucher_no,
				"remarks": e.remarks,
				"account_number": number_map.get(e.account) or e.account,
				"debit": e.debit,
				"credit": e.credit,
			}
		)

	if rows:
		rows.append(
			{"remarks": _("Cộng"), "debit": total_debit, "credit": total_credit, "is_total": 1}
		)
	return rows

# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

"""Sổ Cái (VN general ledger, per account) — Thông tư 99/2025/TT-BTC.

For one account: số dư đầu kỳ, từng phát sinh with TK đối ứng and số dư luỹ kế
(running balance), cộng phát sinh và số dư cuối kỳ. Read-only over the GL.
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
		{"label": _("Ngày"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": _("Loại chứng từ"), "fieldname": "voucher_type", "fieldtype": "Data", "width": 130},
		{
			"label": _("Số chứng từ"),
			"fieldname": "voucher_no",
			"fieldtype": "Dynamic Link",
			"options": "voucher_type",
			"width": 160,
		},
		{"label": _("Diễn giải"), "fieldname": "remarks", "fieldtype": "Data", "width": 240},
		{"label": _("TK đối ứng"), "fieldname": "against", "fieldtype": "Data", "width": 130},
		{"label": _("Phát sinh Nợ"), "fieldname": "debit", "fieldtype": "Currency", "width": 130},
		{"label": _("Phát sinh Có"), "fieldname": "credit", "fieldtype": "Currency", "width": 130},
		{"label": _("Số dư"), "fieldname": "balance", "fieldtype": "Currency", "width": 130},
	]


def get_data(filters):
	if not (filters.company and filters.account and filters.from_date and filters.to_date):
		return []

	opening = flt(
		frappe.db.sql(
			"""select sum(debit) - sum(credit) from `tabGL Entry`
			where company=%s and account=%s and is_cancelled=0 and posting_date < %s""",
			(filters.company, filters.account, filters.from_date),
		)[0][0]
	)

	entries = get_gl_entries(
		filters.company, filters.from_date, filters.to_date, {"account": filters.account}
	)

	rows = [{"remarks": _("Số dư đầu kỳ"), "balance": opening, "is_opening": 1}]
	balance = opening
	total_debit = total_credit = 0.0
	for e in entries:
		balance += flt(e.debit) - flt(e.credit)
		total_debit += flt(e.debit)
		total_credit += flt(e.credit)
		rows.append(
			{
				"posting_date": e.posting_date,
				"voucher_type": e.voucher_type,
				"voucher_no": e.voucher_no,
				"remarks": e.remarks,
				"against": e.against,
				"debit": e.debit,
				"credit": e.credit,
				"balance": balance,
			}
		)

	rows.append(
		{"remarks": _("Cộng phát sinh"), "debit": total_debit, "credit": total_credit, "is_total": 1}
	)
	rows.append({"remarks": _("Số dư cuối kỳ"), "balance": balance, "is_closing": 1})
	return rows

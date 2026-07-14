# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

"""Sổ chi tiết tài khoản (VN account detail ledger) — Thông tư 99/2025/TT-BTC.

Like Sổ Cái but with the đối tượng (party) shown, and an optional party filter —
used for detail subledgers such as công nợ phải thu/phải trả theo đối tượng.
Read-only over the GL; running balance ties to the account's GL balance.
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
		{
			"label": _("Số chứng từ"),
			"fieldname": "voucher_no",
			"fieldtype": "Dynamic Link",
			"options": "voucher_type",
			"width": 160,
		},
		{"label": _("Diễn giải"), "fieldname": "remarks", "fieldtype": "Data", "width": 220},
		{"label": _("Đối tượng"), "fieldname": "party", "fieldtype": "Data", "width": 150},
		{"label": _("TK đối ứng"), "fieldname": "against", "fieldtype": "Data", "width": 120},
		{"label": _("Phát sinh Nợ"), "fieldname": "debit", "fieldtype": "Currency", "width": 120},
		{"label": _("Phát sinh Có"), "fieldname": "credit", "fieldtype": "Currency", "width": 120},
		{"label": _("Số dư"), "fieldname": "balance", "fieldtype": "Currency", "width": 120},
	]


def get_data(filters):
	if not (filters.company and filters.account and filters.from_date and filters.to_date):
		return []

	party_conditions = ""
	opening_params = [filters.company, filters.account, filters.from_date]
	if filters.get("party"):
		party_conditions = " and party = %s"
		opening_params.append(filters.party)

	opening = flt(
		frappe.db.sql(
			f"""select sum(debit) - sum(credit) from `tabGL Entry`
			where company=%s and account=%s and is_cancelled=0 and posting_date < %s{party_conditions}""",
			tuple(opening_params),
		)[0][0]
	)

	extra = {"account": filters.account}
	if filters.get("party_type"):
		extra["party_type"] = filters.party_type
	if filters.get("party"):
		extra["party"] = filters.party
	entries = get_gl_entries(filters.company, filters.from_date, filters.to_date, extra)

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
				"party": e.party,
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

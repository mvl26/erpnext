# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Đối chiếu tổng: Σ dư cuối các biên bản vs số dư TK 331/131 (FR-15b, T11).

Cùng tập tài khoản và cùng quy ước dấu với ``figures.py`` (dương = còn nợ). Chênh
lệch tổng phải bằng 0 khi mọi đối tác có số dư đều có biên bản chưa Hủy trong kỳ.
"""

import frappe
from frappe import _
from frappe.utils import flt

from erpnext.debt_reconciliation import constants as C
from erpnext.debt_reconciliation import figures

NO_PARTY = "(không có đối tượng)"


def execute(filters=None):
	filters = frappe._dict(filters or {})
	data = get_data(filters)
	return get_columns(), data, None, None, get_summary(data)


def get_columns():
	return [
		{"label": _("Đối tác"), "fieldname": "party", "fieldtype": "Data", "width": 160},
		{"label": _("Tên đối tác"), "fieldname": "party_name", "fieldtype": "Data", "width": 220},
		{
			"label": _("Biên bản"),
			"fieldname": "statement",
			"fieldtype": "Link",
			"options": C.DOCTYPE,
			"width": 150,
		},
		{
			"label": _("Dư cuối theo biên bản"),
			"fieldname": "statement_balance",
			"fieldtype": "Currency",
			"width": 160,
		},
		{"label": _("Dư cuối theo sổ"), "fieldname": "gl_balance", "fieldtype": "Currency", "width": 160},
		{"label": _("Chênh lệch"), "fieldname": "difference", "fieldtype": "Currency", "width": 140},
	]


def get_gl_balances(company, party_type, to_date):
	"""Số dư có hướng theo đối tác tại ``to_date``, gồm cả dòng GL thiếu đối tượng (R1)."""
	accounts = figures.get_party_accounts(company, party_type)
	rows = frappe.db.sql(
		"""
		select ifnull(party, '') as party, sum(debit) as d, sum(credit) as c
		from `tabGL Entry`
		where company = %(company)s and is_cancelled = 0 and account in %(accounts)s
			and posting_date <= %(to_date)s
		group by ifnull(party, '')
		""",
		{"company": company, "accounts": tuple(accounts), "to_date": to_date},
		as_dict=True,
	)
	return {r.party: figures.signed_opening(party_type, r.d, r.c) for r in rows}


def get_data(filters):
	if not (filters.company and filters.to_date and filters.party_type):
		return []

	gl = get_gl_balances(filters.company, filters.party_type, filters.to_date)
	statements = {
		s.party: s
		for s in frappe.get_all(
			C.DOCTYPE,
			filters={
				"company": filters.company,
				"party_type": filters.party_type,
				"to_date": filters.to_date,
				"docstatus": ["<", 2],
			},
			fields=["name", "party", "party_name", "closing_balance", "balance_direction"],
		)
	}

	rows = []
	for party in sorted(set(gl) | set(statements), key=lambda p: (p == "", p)):
		s = statements.get(party)
		statement_balance = (
			figures.to_signed(filters.party_type, s.closing_balance, s.balance_direction) if s else 0
		)
		gl_balance = flt(gl.get(party), 0)
		if not s and not gl_balance:
			continue
		rows.append(
			{
				"party": party or NO_PARTY,
				"party_name": s.party_name if s else "",
				"statement": s.name if s else None,
				"statement_balance": statement_balance,
				"gl_balance": gl_balance,
				"difference": flt(gl_balance - statement_balance, 0),
			}
		)
	if rows:
		rows.append(
			{
				"party": _("Tổng cộng"),
				"statement_balance": sum(r["statement_balance"] for r in rows),
				"gl_balance": sum(r["gl_balance"] for r in rows),
				"difference": sum(r["difference"] for r in rows),
				"bold": 1,
			}
		)
	return rows


def get_summary(data):
	if not data:
		return []
	total = data[-1]
	return [
		{"label": _("Σ biên bản"), "value": total["statement_balance"], "datatype": "Currency"},
		{"label": _("Số dư tài khoản"), "value": total["gl_balance"], "datatype": "Currency"},
		{
			"label": _("Chênh lệch"),
			"value": total["difference"],
			"datatype": "Currency",
			"indicator": "Green" if not total["difference"] else "Red",
		},
	]

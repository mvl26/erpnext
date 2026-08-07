# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Bảng cân đối số phát sinh (VN trial balance) — Thông tư 99/2025/TT-BTC.

Per non-group account: số dư đầu kỳ (Nợ/Có), số phát sinh trong kỳ (Nợ/Có), số dư
cuối kỳ (Nợ/Có). Computed read-only over the GL; the closing/opening side is
chosen by the net balance sign. Double-entry guarantees each column pair balances.
"""

import frappe
from frappe import _

from erpnext.regional.vietnam.utils import get_account_balances


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"label": _("Số hiệu TK"), "fieldname": "account_number", "fieldtype": "Data", "width": 90},
		{"label": _("Tên tài khoản"), "fieldname": "account_name", "fieldtype": "Data", "width": 280},
		{"label": _("Dư đầu kỳ - Nợ"), "fieldname": "opening_debit", "fieldtype": "Currency", "width": 130},
		{"label": _("Dư đầu kỳ - Có"), "fieldname": "opening_credit", "fieldtype": "Currency", "width": 130},
		{"label": _("Phát sinh - Nợ"), "fieldname": "debit", "fieldtype": "Currency", "width": 130},
		{"label": _("Phát sinh - Có"), "fieldname": "credit", "fieldtype": "Currency", "width": 130},
		{"label": _("Dư cuối kỳ - Nợ"), "fieldname": "closing_debit", "fieldtype": "Currency", "width": 130},
		{"label": _("Dư cuối kỳ - Có"), "fieldname": "closing_credit", "fieldtype": "Currency", "width": 130},
	]


def get_data(filters):
	if not (filters.company and filters.from_date and filters.to_date):
		return []

	balances = get_account_balances(filters.company, filters.from_date, filters.to_date)
	rows = []
	totals = frappe._dict(
		opening_debit=0.0,
		opening_credit=0.0,
		debit=0.0,
		credit=0.0,
		closing_debit=0.0,
		closing_credit=0.0,
	)

	for b in sorted(balances.values(), key=lambda x: (x.account_number or "", x.account_name)):
		if not (b.opening or b.debit or b.credit or b.closing):
			continue
		row = {
			"account_number": b.account_number,
			"account_name": b.account_name,
			"opening_debit": b.opening if b.opening > 0 else 0.0,
			"opening_credit": -b.opening if b.opening < 0 else 0.0,
			"debit": b.debit,
			"credit": b.credit,
			"closing_debit": b.closing if b.closing > 0 else 0.0,
			"closing_credit": -b.closing if b.closing < 0 else 0.0,
		}
		rows.append(row)
		for key in totals:
			totals[key] += row[key]

	if rows:
		rows.append(
			{
				"account_name": _("Tổng cộng"),
				"is_total": 1,
				**totals,
			}
		)
	return rows

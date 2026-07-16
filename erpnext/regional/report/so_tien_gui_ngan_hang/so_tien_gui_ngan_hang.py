# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

"""Sổ tiền gửi ngân hàng (S08-DN) — Thông tư 99/2025/TT-BTC.

Bank book over the TT99 112* accounts: gửi vào (debit), rút ra (credit) and the
running còn lại, with opening/period-total/closing rows. Read-only over the GL.
An optional account filter narrows the book to one bank account (một tài khoản
tại một ngân hàng), which is how the statutory book is kept per account.
"""

import frappe
from frappe import _

from erpnext.regional.vietnam.utils import get_cash_bank_book_rows

BANK_PREFIX = "112"


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
		{"label": _("Tài khoản"), "fieldname": "account", "fieldtype": "Data", "width": 150},
		{"label": _("TK đối ứng"), "fieldname": "against", "fieldtype": "Data", "width": 120},
		{"label": _("Gửi vào"), "fieldname": "thu", "fieldtype": "Currency", "width": 130},
		{"label": _("Rút ra"), "fieldname": "chi", "fieldtype": "Currency", "width": 130},
		{"label": _("Còn lại"), "fieldname": "balance", "fieldtype": "Currency", "width": 130},
	]


def get_data(filters):
	if not (filters.company and filters.from_date and filters.to_date):
		return []
	return get_cash_bank_book_rows(
		filters.company, filters.from_date, filters.to_date, BANK_PREFIX, filters.get("account")
	)

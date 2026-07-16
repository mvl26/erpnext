# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

"""Sổ quỹ tiền mặt (S07-DN) — Thông tư 99/2025/TT-BTC.

Cash book over the TT99 111* accounts: thu (debit), chi (credit) and the running
tồn quỹ, with opening/period-total/closing rows. Read-only over the GL; the
closing tồn ties to the 111* GL balance for the same range. An optional account
filter narrows the book to one quỹ.
"""

import frappe
from frappe import _

from erpnext.regional.vietnam.utils import get_cash_bank_book_rows

CASH_PREFIX = "111"


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"label": _("Ngày"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{
			"label": _("Số phiếu"),
			"fieldname": "voucher_no",
			"fieldtype": "Dynamic Link",
			"options": "voucher_type",
			"width": 160,
		},
		{"label": _("Diễn giải"), "fieldname": "remarks", "fieldtype": "Data", "width": 240},
		{"label": _("TK đối ứng"), "fieldname": "against", "fieldtype": "Data", "width": 120},
		{"label": _("Thu"), "fieldname": "thu", "fieldtype": "Currency", "width": 130},
		{"label": _("Chi"), "fieldname": "chi", "fieldtype": "Currency", "width": 130},
		{"label": _("Tồn quỹ"), "fieldname": "balance", "fieldtype": "Currency", "width": 130},
	]


def get_data(filters):
	if not (filters.company and filters.from_date and filters.to_date):
		return []
	return get_cash_bank_book_rows(
		filters.company, filters.from_date, filters.to_date, CASH_PREFIX, filters.get("account")
	)

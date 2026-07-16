# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

"""Sổ chi tiết công nợ theo đối tượng — Thông tư 99/2025/TT-BTC.

Per-party subledger over the TT99 receivable/payable control accounts (131* for
Customer, 331* for Supplier; both when no party_type filter): for each đối tượng
an opening row, the period vouchers with a running balance, and a closing row.
GL rows on a control account that carry no party are surfaced in a trailing
"(không có đối tượng)" bucket — the same integrity rule the opening-balance
validator enforces. Read-only over the GL.
"""

import frappe
from frappe import _
from frappe.utils import flt

from erpnext.regional.vietnam.utils import get_gl_entries

PARTY_ACCOUNT_PREFIXES = {"Customer": ("131",), "Supplier": ("331",)}
MISSING_PARTY_LABEL = "(không có đối tượng)"


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"label": _("Đối tượng"), "fieldname": "party", "fieldtype": "Data", "width": 200},
		{"label": _("Ngày"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{
			"label": _("Số chứng từ"),
			"fieldname": "voucher_no",
			"fieldtype": "Dynamic Link",
			"options": "voucher_type",
			"width": 160,
		},
		{"label": _("Diễn giải"), "fieldname": "remarks", "fieldtype": "Data", "width": 200},
		{"label": _("Tài khoản"), "fieldname": "account", "fieldtype": "Data", "width": 130},
		{"label": _("Phát sinh Nợ"), "fieldname": "debit", "fieldtype": "Currency", "width": 120},
		{"label": _("Phát sinh Có"), "fieldname": "credit", "fieldtype": "Currency", "width": 120},
		{"label": _("Số dư"), "fieldname": "balance", "fieldtype": "Currency", "width": 120},
	]


def _control_accounts(company, party_type):
	prefixes = PARTY_ACCOUNT_PREFIXES.get(party_type) or ("131", "331")
	return [
		a.name
		for a in frappe.get_all(
			"Account",
			filters={"company": company, "is_group": 0},
			fields=["name", "account_number"],
		)
		if (a.account_number or "").startswith(prefixes)
	]


def get_data(filters):
	if not (filters.company and filters.from_date and filters.to_date):
		return []

	accounts = _control_accounts(filters.company, filters.get("party_type"))
	if not accounts:
		return []

	party_condition = ""
	opening_params = [filters.company, filters.from_date, tuple(accounts)]
	if filters.get("party"):
		party_condition = " and party = %s"
		opening_params.append(filters.party)

	opening_by_party = {
		row.party: flt(row.bal)
		for row in frappe.db.sql(
			f"""select party, sum(debit) - sum(credit) as bal from `tabGL Entry`
			where company=%s and is_cancelled=0 and posting_date < %s and account in %s{party_condition}
			group by party""",
			tuple(opening_params),
			as_dict=True,
		)
	}

	extra = {"account": ["in", accounts]}
	if filters.get("party"):
		extra["party"] = filters.party
	entries = get_gl_entries(filters.company, filters.from_date, filters.to_date, extra)

	entries_by_party = {}
	for e in entries:
		entries_by_party.setdefault(e.party, []).append(e)

	parties = set(opening_by_party) | set(entries_by_party)
	# Real parties sorted by name; the partyless bucket, if any, always last.
	ordered = sorted(p for p in parties if p) + ([None] if None in parties else [])

	rows = []
	for party in ordered:
		label = party or MISSING_PARTY_LABEL
		opening = flt(opening_by_party.get(party))
		balance = opening
		rows.append(
			{"party": label, "party_link": party, "remarks": _("Số dư đầu kỳ"), "balance": opening, "is_opening": 1}
		)
		for e in entries_by_party.get(party, []):
			balance += flt(e.debit) - flt(e.credit)
			rows.append(
				{
					"party": label,
					"party_link": party,
					"posting_date": e.posting_date,
					"voucher_type": e.voucher_type,
					"voucher_no": e.voucher_no,
					"remarks": e.remarks,
					"account": e.account,
					"debit": e.debit,
					"credit": e.credit,
					"balance": balance,
				}
			)
		rows.append(
			{"party": label, "party_link": party, "remarks": _("Số dư cuối kỳ"), "balance": balance, "is_closing": 1}
		)
	return rows

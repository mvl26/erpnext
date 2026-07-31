# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Sổ chi tiết nguyên tệ (theo dõi ngoại tệ, thay sổ TK 007) — TT99/2025.

Per foreign-currency account (account_currency ≠ đồng tiền hạch toán): opening,
vouchers and closing with running balances in BOTH nguyên tệ and VND. Covers the
old off-balance TK 007 need for cash/bank accounts and the sổ chi tiết theo
nguyên tệ for công nợ/vay ngoại tệ. Read-only over the GL.
"""

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"label": _("Tài khoản"), "fieldname": "account", "fieldtype": "Data", "width": 180},
		{"label": _("Ngày"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{
			"label": _("Số chứng từ"),
			"fieldname": "voucher_no",
			"fieldtype": "Dynamic Link",
			"options": "voucher_type",
			"width": 150,
		},
		{"label": _("Diễn giải"), "fieldname": "remarks", "fieldtype": "Data", "width": 180},
		{"label": _("Nguyên tệ"), "fieldname": "currency", "fieldtype": "Data", "width": 80},
		{"label": _("PS Nợ (NT)"), "fieldname": "debit_nt", "fieldtype": "Float", "width": 110},
		{"label": _("PS Có (NT)"), "fieldname": "credit_nt", "fieldtype": "Float", "width": 110},
		{"label": _("Số dư (NT)"), "fieldname": "balance_nt", "fieldtype": "Float", "width": 110},
		{"label": _("PS Nợ (VND)"), "fieldname": "debit_vnd", "fieldtype": "Currency", "width": 130},
		{"label": _("PS Có (VND)"), "fieldname": "credit_vnd", "fieldtype": "Currency", "width": 130},
		{"label": _("Số dư (VND)"), "fieldname": "balance_vnd", "fieldtype": "Currency", "width": 130},
	]


def _foreign_currency_accounts(filters):
	company_currency = frappe.db.get_value("Company", filters.company, "default_currency")
	account_filters = {
		"company": filters.company,
		"is_group": 0,
		"account_currency": ["not in", ["", company_currency]],
	}
	if filters.get("account"):
		account_filters["name"] = filters.account
	if filters.get("currency"):
		account_filters["account_currency"] = filters.currency
	return frappe.get_all(
		"Account", filters=account_filters, fields=["name", "account_currency"], order_by="account_number"
	)


def get_data(filters):
	if not (filters.company and filters.from_date and filters.to_date):
		return []

	accounts = _foreign_currency_accounts(filters)
	rows = []
	for account in accounts:
		rows += _account_rows(filters, account.name, account.account_currency)
	return rows


def _account_rows(filters, account, currency):
	opening_nt, opening_vnd = (
		frappe.db.sql(
			"""select
				coalesce(sum(debit_in_account_currency) - sum(credit_in_account_currency), 0),
				coalesce(sum(debit) - sum(credit), 0)
			from `tabGL Entry`
			where company=%s and account=%s and is_cancelled=0 and posting_date < %s""",
			(filters.company, account, filters.from_date),
		)
	)[0]

	entries = frappe.get_all(
		"GL Entry",
		filters={
			"company": filters.company,
			"account": account,
			"is_cancelled": 0,
			"posting_date": ["between", [filters.from_date, filters.to_date]],
		},
		fields=[
			"posting_date",
			"voucher_type",
			"voucher_no",
			"remarks",
			"debit_in_account_currency",
			"credit_in_account_currency",
			"debit",
			"credit",
		],
		order_by="posting_date, creation",
	)

	balance_nt, balance_vnd = flt(opening_nt), flt(opening_vnd)
	rows = [
		{
			"account": account,
			"currency": currency,
			"remarks": _("Số dư đầu kỳ"),
			"balance_nt": balance_nt,
			"balance_vnd": balance_vnd,
			"is_opening": 1,
		}
	]
	for e in entries:
		balance_nt += flt(e.debit_in_account_currency) - flt(e.credit_in_account_currency)
		balance_vnd += flt(e.debit) - flt(e.credit)
		rows.append(
			{
				"account": account,
				"posting_date": e.posting_date,
				"voucher_type": e.voucher_type,
				"voucher_no": e.voucher_no,
				"remarks": e.remarks,
				"currency": currency,
				"debit_nt": e.debit_in_account_currency,
				"credit_nt": e.credit_in_account_currency,
				"debit_vnd": e.debit,
				"credit_vnd": e.credit,
				"balance_nt": balance_nt,
				"balance_vnd": balance_vnd,
			}
		)
	rows.append(
		{
			"account": account,
			"currency": currency,
			"remarks": _("Số dư cuối kỳ"),
			"balance_nt": balance_nt,
			"balance_vnd": balance_vnd,
			"is_closing": 1,
		}
	)
	return rows

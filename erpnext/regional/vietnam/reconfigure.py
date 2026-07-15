# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

"""Switch an EMPTY company onto the TT99 chart of accounts.

Used to move a company that was created on the English "Standard" chart onto the
Vietnam TT99 chart. Guarded: refuses unless the company has no transactions, and
backs up the old account list first. Safe because an empty company has nothing
referencing its accounts.
"""

import json

import frappe
from frappe import _

from erpnext.regional.vietnam.setup import setup

VN_CHART = "Vietnam - Chart of Accounts (Thông tư 99/2025/TT-BTC)"

# Doctypes that would make a chart swap unsafe if any rows exist for the company.
_TRANSACTION_DOCTYPES = (
	"GL Entry",
	"Stock Ledger Entry",
	"Journal Entry",
	"Sales Invoice",
	"Purchase Invoice",
	"Payment Entry",
	"Asset",
)

_COMPANY_ACCOUNT_FIELDS = (
	"default_receivable_account",
	"default_payable_account",
	"default_cash_account",
	"default_bank_account",
	"default_income_account",
	"default_expense_account",
	"default_inventory_account",
	"round_off_account",
	"write_off_account",
	"exchange_gain_loss_account",
	"unrealized_exchange_gain_loss_account",
	"disposal_account",
	"accumulated_depreciation_account",
	"depreciation_expense_account",
	"capital_work_in_progress_account",
	"asset_received_but_not_billed",
	"expenses_included_in_asset_valuation",
	"stock_received_but_not_billed",
	"stock_adjustment_account",
	"expenses_included_in_valuation",
	"default_provisional_account",
	"default_deferred_revenue_account",
	"default_deferred_expense_account",
	"default_discount_account",
)


def is_company_empty(company):
	return not any(frappe.db.count(dt, {"company": company}) for dt in _TRANSACTION_DOCTYPES)


def backup_accounts(company):
	"""Serialise the company's current accounts to a private-files JSON backup."""
	accounts = frappe.get_all(
		"Account",
		filters={"company": company},
		fields=["name", "account_name", "account_number", "account_type", "root_type", "parent_account"],
	)
	path = frappe.get_site_path(
		"private", "files", f"accounts_backup_{frappe.scrub(company)}.json"
	)
	with open(path, "w", encoding="utf-8") as f:
		json.dump(accounts, f, ensure_ascii=False, indent=1)
	return path


def _clear_account_links(company):
	frappe.db.set_value("Company", company, {f: None for f in _COMPANY_ACCOUNT_FIELDS})
	for warehouse in frappe.get_all("Warehouse", {"company": company}, pluck="name"):
		frappe.db.set_value("Warehouse", warehouse, "account", None)
	frappe.db.delete("Mode of Payment Account", {"company": company})
	for dt in (
		"Sales Taxes and Charges Template",
		"Purchase Taxes and Charges Template",
		"Item Tax Template",
	):
		for name in frappe.get_all(dt, {"company": company}, pluck="name"):
			frappe.delete_doc(dt, name, force=True, ignore_permissions=True)


def reconfigure_company_to_vn_chart(company):
	"""Rebuild an empty company's chart on TT99 and re-wire every default. Idempotent."""
	if frappe.db.get_value("Company", company, "chart_of_accounts") == VN_CHART:
		return None

	if not is_company_empty(company):
		frappe.throw(
			_("Company {0} has transactions; refusing to rebuild its chart of accounts.").format(company)
		)

	backup_path = backup_accounts(company)

	_clear_account_links(company)
	frappe.db.delete("Account", {"company": company})
	frappe.db.set_value("Company", company, "chart_of_accounts", VN_CHART)

	frappe.local.flags.ignore_root_company_validation = True
	comp = frappe.get_doc("Company", company)
	comp.flags.ignore_permissions = True
	comp.update_default_account = True
	comp.create_default_accounts()  # create_charts on TT99 + default receivable/payable
	comp.set_default_accounts()  # cash/bank/income/expense/inventory/round-off/FX/…
	comp.create_default_tax_template()  # GTGT templates on TT99 accounts
	setup(company)  # Mode of Payment, Asset Categories

	return backup_path

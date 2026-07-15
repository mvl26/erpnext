# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

"""Vietnam go-live: operational configuration for a TT99-wired company.

``configure_go_live(company)`` makes a Vietnam company ready to operate — a fiscal
year for the go-live year, perpetual inventory + a valuation method, VN document
naming series, and VND as the operating currency. Every step is idempotent and
VN-guarded so it is safe to re-run and never touches a non-Vietnam company.
"""

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.utils import flt, getdate, nowdate

from erpnext.regional.vietnam.constants import VN_NAMING_SERIES
from erpnext.regional.vietnam.setup import _acct

# TT99 inventory account prefixes (hàng tồn kho: nguyên vật liệu … hàng gửi bán).
STOCK_PREFIXES = ("151", "152", "153", "154", "155", "156", "157")


def _is_vn(company):
	return bool(company) and frappe.db.get_value("Company", company, "country") == "Vietnam"


@frappe.whitelist()
def configure_go_live(company=None, fiscal_year=None):
	"""Configure a Vietnam company for go-live (idempotent). Returns a summary."""
	if not _is_vn(company):
		return {"ok": False, "reason": "not a Vietnam company"}

	year = int(fiscal_year) if fiscal_year else getdate(nowdate()).year
	_ensure_fiscal_year(year)
	_ensure_stock_config(company)
	_ensure_naming_series()
	_ensure_vnd_currency(company)
	return {"ok": True, "company": company, "fiscal_year": str(year)}


def _ensure_fiscal_year(year):
	"""Ensure a Jan-1..Dec-31 Fiscal Year exists for ``year`` (global, all companies)."""
	name = str(year)
	if frappe.db.exists("Fiscal Year", name):
		return name

	start, end = getdate(f"{year}-01-01"), getdate(f"{year}-12-31")
	if frappe.db.exists("Fiscal Year", {"year_start_date": start, "year_end_date": end}):
		return None

	fy = frappe.get_doc(
		{"doctype": "Fiscal Year", "year": name, "year_start_date": start, "year_end_date": end}
	)
	fy.flags.ignore_permissions = True
	fy.insert(ignore_if_duplicate=True)
	return fy.name


def _ensure_stock_config(company):
	"""Perpetual inventory on (stock hits 156) + a stock valuation method set."""
	if not frappe.db.get_value("Company", company, "enable_perpetual_inventory"):
		frappe.db.set_value("Company", company, "enable_perpetual_inventory", 1)

	settings = frappe.get_single("Stock Settings")
	if not settings.valuation_method:
		settings.valuation_method = "Moving Average"  # bình quân gia quyền
		settings.flags.ignore_permissions = True
		settings.save()


def _ensure_naming_series():
	"""Register VN naming-series options additively on each target DocType."""
	for doctype, series in VN_NAMING_SERIES:
		_add_series_option(doctype, series)


def _add_series_option(doctype, series):
	field = frappe.get_meta(doctype).get_field("naming_series")
	if not field:
		return
	options = [o for o in (field.options or "").split("\n") if o]
	if series in options:
		return

	options.append(series)
	value = "\n".join(options)
	existing = frappe.db.exists(
		"Property Setter",
		{"doc_type": doctype, "field_name": "naming_series", "property": "options"},
	)
	if existing:
		frappe.db.set_value("Property Setter", existing, "value", value)
	else:
		make_property_setter(
			doctype, "naming_series", "options", value, "Text", validate_fields_for_doctype=False
		)
	frappe.clear_cache(doctype=doctype)


def _ensure_vnd_currency(company):
	"""Operating currency VND, and the VND currency record enabled for formatting."""
	if frappe.db.get_value("Company", company, "default_currency") != "VND":
		frappe.db.set_value("Company", company, "default_currency", "VND")
	if frappe.db.exists("Currency", "VND") and not frappe.db.get_value("Currency", "VND", "enabled"):
		frappe.db.set_value("Currency", "VND", "enabled", 1)


def post_opening_journal_entry(company, lines, posting_date=None):
	"""Post a submitted Opening Journal Entry from TT99-number lines.

	``lines``: iterable of ``(account_number, debit, credit[, party_type, party])``.
	Each number is resolved to the company's posting account via ``_acct``. Returns
	the Journal Entry name. Debits must equal credits (Journal Entry enforces this).
	"""
	je = frappe.new_doc("Journal Entry")
	je.company = company
	je.voucher_type = "Opening Entry"
	je.is_opening = "Yes"
	je.posting_date = posting_date or nowdate()

	for line in lines:
		number, debit, credit = line[0], line[1], line[2]
		account = _acct(company, number)
		if not account:
			frappe.throw(f"TT99 account {number} not found for {company}")
		row = {
			"account": account,
			"debit_in_account_currency": flt(debit),
			"credit_in_account_currency": flt(credit),
		}
		if len(line) > 4 and line[3] and line[4]:
			row["party_type"], row["party"] = line[3], line[4]
		je.append("accounts", row)

	je.flags.ignore_permissions = True
	je.insert()
	je.submit()
	return je.name


@frappe.whitelist()
def validate_opening_balances(company):
	"""Validate a VN company's opening balances. Read-only; structured pass/fail.

	Gates: the opening trial balance nets to zero, every opening entry hits a
	TT99-numbered account, and receivable/payable openings carry a party (so the
	131/331 control accounts reconcile with their subsidiary ledgers). Also reports
	the 131 / 331 / 15x opening control totals.
	"""
	rows = frappe.get_all(
		"GL Entry",
		filters={"company": company, "is_opening": "Yes", "is_cancelled": 0},
		fields=["account", "debit", "credit", "party"],
	)
	numbers = {
		a: (frappe.db.get_value("Account", a, "account_number") or "") for a in {r.account for r in rows}
	}

	total_dr = sum(flt(r.debit) for r in rows)
	total_cr = sum(flt(r.credit) for r in rows)
	non_tt99 = sorted({r.account for r in rows if not numbers[r.account]})
	orphan = sorted({r.account for r in rows if numbers[r.account].startswith(("131", "331")) and not r.party})

	def _net(prefixes):
		return sum(flt(r.debit) - flt(r.credit) for r in rows if numbers[r.account].startswith(prefixes))

	totals = {
		"receivable_131": _net(("131",)),
		"payable_331": -_net(("331",)),
		"stock_15x": _net(STOCK_PREFIXES),
	}
	checks = [
		{
			"name": "balanced",
			"ok": abs(total_dr - total_cr) < 0.005,
			"detail": f"Nợ {total_dr:,.0f} / Có {total_cr:,.0f}",
		},
		{
			"name": "all_tt99",
			"ok": not non_tt99,
			"detail": "; ".join(non_tt99) or "mọi bút toán mở sổ dùng tài khoản TT99",
		},
		{
			"name": "ar_ap_has_party",
			"ok": not orphan,
			"detail": "; ".join(orphan) or "công nợ 131/331 có đối tượng",
		},
	]
	return {"ok": all(c["ok"] for c in checks), "checks": checks, "totals": totals}

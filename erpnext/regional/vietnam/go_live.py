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
from frappe.utils import getdate, nowdate

from erpnext.regional.vietnam.constants import VN_NAMING_SERIES


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

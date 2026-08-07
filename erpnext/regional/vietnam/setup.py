# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Vietnam company setup — wire module/master-data account links to TT99 numbers.

``setup(company)`` is dispatched by ``install_country_fixtures`` when a Vietnam
company is created, and is also called standalone (e.g. when reconfiguring an
existing company onto the TT99 chart). Every step is idempotent and VN-guarded so
it is safe to re-run.
"""

import frappe


def _acct(company, number):
	"""Resolve a TT99 account number to the company's posting account name."""
	return frappe.db.get_value(
		"Account", {"company": company, "account_number": number, "is_group": 0}, "name"
	)


def setup(company=None, patch=True):
	if not company:
		return
	if frappe.db.get_value("Company", company, "country") != "Vietnam":
		return

	_wire_mode_of_payment(company)
	_create_asset_categories(company)

	from erpnext.regional.vietnam.tt45 import apply_tt45_useful_life

	apply_tt45_useful_life()


def _ensure_mode_of_payment(name, mode_type):
	if not frappe.db.exists("Mode of Payment", name):
		doc = frappe.get_doc(
			{"doctype": "Mode of Payment", "mode_of_payment": name, "type": mode_type, "enabled": 1}
		)
		doc.flags.ignore_permissions = True
		doc.insert(ignore_if_duplicate=True)


# (asset_category_name, fixed, accum_dep, dep_expense, cwip) by TT99 number.
ASSET_CATEGORIES = (
	("Tài sản cố định hữu hình", "211", "2141", "6424", "2411"),
	("Tài sản cố định vô hình", "213", "2143", "6424", "2411"),
)


def drop_rows_of_deleted_companies(category):
	"""Drop per-company account rows whose company no longer exists.

	``Asset Category`` is a global DocType with a per-company child table, so Frappe
	validates the links of EVERY row on save. A row left behind by a deleted company
	points at accounts that went with it, so it can never validate again and fails
	the save for an unrelated company — which, inside ``install_country_fixtures``,
	aborts that company's creation. Returns True when anything was dropped.
	"""
	live = [row for row in category.accounts if frappe.db.exists("Company", row.company_name)]
	if len(live) == len(category.accounts):
		return False

	category.accounts = live
	for idx, row in enumerate(live, start=1):
		row.idx = idx
	return True


def _create_asset_categories(company):
	"""Default Asset Categories wired to TT99 TSCĐ / hao mòn / khấu hao / XDCB."""
	for name, fixed, accum, dep, cwip in ASSET_CATEGORIES:
		accounts = {
			"fixed_asset_account": _acct(company, fixed),
			"accumulated_depreciation_account": _acct(company, accum),
			"depreciation_expense_account": _acct(company, dep),
			"capital_work_in_progress_account": _acct(company, cwip),
		}
		if not all(accounts.values()):
			continue

		if frappe.db.exists("Asset Category", name):
			category = frappe.get_doc("Asset Category", name)
		else:
			category = frappe.get_doc(
				{"doctype": "Asset Category", "asset_category_name": name, "enable_cwip_accounting": 1}
			)

		changed = drop_rows_of_deleted_companies(category)
		if not any(row.company_name == company for row in category.accounts):
			category.append("accounts", {"company_name": company, **accounts})
			changed = True
		if not changed:
			continue

		category.flags.ignore_permissions = True
		category.save() if not category.is_new() else category.insert()


def _wire_mode_of_payment(company):
	"""Cash -> 111 (tiền mặt), Bank -> 112 (tiền gửi ngân hàng)."""
	for name, mode_type, number in (("Cash", "Cash", "111"), ("Bank", "Bank", "112")):
		account = _acct(company, number)
		if not account:
			continue
		_ensure_mode_of_payment(name, mode_type)
		mode = frappe.get_doc("Mode of Payment", name, for_update=True)
		row = next((r for r in mode.accounts if r.company == company), None)
		if row is None:
			mode.append("accounts", {"company": company, "default_account": account})
			mode.save(ignore_permissions=True)
		elif row.default_account != account:
			row.default_account = account
			mode.save(ignore_permissions=True)

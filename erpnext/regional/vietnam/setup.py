# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

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


def _ensure_mode_of_payment(name, mode_type):
	if not frappe.db.exists("Mode of Payment", name):
		doc = frappe.get_doc(
			{"doctype": "Mode of Payment", "mode_of_payment": name, "type": mode_type, "enabled": 1}
		)
		doc.flags.ignore_permissions = True
		doc.insert(ignore_if_duplicate=True)


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

# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Vietnam company setup — wire module/master-data account links to TT99 numbers.

``setup(company)`` is dispatched by ``install_country_fixtures`` when a Vietnam
company is created, and is also called standalone (e.g. when reconfiguring an
existing company onto the TT99 chart). Every step is idempotent and VN-guarded so
it is safe to re-run.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


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
	_make_e_invoice_custom_fields()

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


# Mirrors the Vietnam E Invoice Log statuses, with a leading blank for "not issued".
E_INVOICE_SI_STATUSES = "\nDraft\nIssued\nAdjusted\nReplaced\nCancelled\nError"


def _make_e_invoice_custom_fields():
	"""Hóa đơn điện tử (NĐ 70/2025) fields on Company (settings) + Sales Invoice.

	Global, created on the first VN company's setup; ``create_custom_fields`` with
	``update=True`` keeps re-runs idempotent. Provider list grows as real adapters
	ship (mock is the only one until the HĐĐT provider is chosen).
	"""
	create_custom_fields(
		{
			"Company": [
				dict(
					fieldname="vn_einvoice_section",
					fieldtype="Section Break",
					label="Hóa đơn điện tử (Việt Nam)",
					insert_after="country",
					collapsible=1,
				),
				dict(
					fieldname="vn_einvoice_enabled",
					fieldtype="Check",
					label="Phát hành HĐĐT khi submit hóa đơn bán",
					insert_after="vn_einvoice_section",
					default="0",
				),
				dict(
					fieldname="vn_einvoice_provider",
					fieldtype="Select",
					label="Nhà cung cấp HĐĐT",
					options="mock",
					insert_after="vn_einvoice_enabled",
					depends_on="vn_einvoice_enabled",
				),
				dict(
					fieldname="vn_einvoice_symbol",
					fieldtype="Data",
					label="Ký hiệu hóa đơn",
					insert_after="vn_einvoice_provider",
					depends_on="vn_einvoice_enabled",
				),
			],
			"Sales Invoice": [
				dict(
					fieldname="vn_einvoice_section",
					fieldtype="Section Break",
					label="Hóa đơn điện tử",
					insert_after="remarks",
					collapsible=1,
				),
				dict(
					fieldname="vn_einvoice_number",
					fieldtype="Data",
					label="Số hóa đơn điện tử",
					insert_after="vn_einvoice_section",
					read_only=1,
					no_copy=1,
				),
				dict(
					fieldname="vn_einvoice_symbol",
					fieldtype="Data",
					label="Ký hiệu",
					insert_after="vn_einvoice_number",
					read_only=1,
					no_copy=1,
				),
				dict(
					fieldname="vn_einvoice_column",
					fieldtype="Column Break",
					insert_after="vn_einvoice_symbol",
				),
				dict(
					fieldname="vn_einvoice_status",
					fieldtype="Select",
					label="Trạng thái HĐĐT",
					options=E_INVOICE_SI_STATUSES,
					insert_after="vn_einvoice_column",
					read_only=1,
					no_copy=1,
					in_standard_filter=1,
				),
				dict(
					fieldname="vn_einvoice_cqt_code",
					fieldtype="Data",
					label="Mã của CQT",
					insert_after="vn_einvoice_status",
					read_only=1,
					no_copy=1,
				),
				dict(
					fieldname="vn_einvoice_log",
					fieldtype="Link",
					label="Nhật ký HĐĐT",
					options="Vietnam E Invoice Log",
					insert_after="vn_einvoice_cqt_code",
					read_only=1,
					no_copy=1,
				),
			],
		},
		update=True,
	)


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

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

from erpnext.regional.vietnam.constants import CHART_NAME, PL_ACCOUNT_PREFIXES, VN_NAMING_SERIES
from erpnext.regional.vietnam.role_profiles import VN_ROLE_PROFILES
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
def validate_opening_balances(company, as_of=None):
	"""Validate a VN company's opening balances. Read-only; structured pass/fail.

	Gates: the opening trial balance nets to zero, every opening entry hits a
	TT99-numbered account, and receivable/payable openings carry a party (so the
	131/331 control accounts reconcile with their subsidiary ledgers). Also reports
	the 131 / 331 / 15x opening control totals.

	With ``as_of`` (mid-year cutover, e.g. ``"2026-06-30"``) two more gates apply:
	the opening TB is balance-sheet-only — no account numbered loại 5–9, the H1
	result belongs in equity (4212) — and every opening entry is posted exactly on
	``as_of``. Core already blocks report_type="Profit and Loss" accounts in opening
	entries; the number-prefix gate additionally catches P&L-numbered accounts that
	were misclassified as Balance Sheet. Without ``as_of`` behavior is unchanged.
	"""
	rows = frappe.get_all(
		"GL Entry",
		filters={"company": company, "is_opening": "Yes", "is_cancelled": 0},
		fields=["account", "debit", "credit", "party", "posting_date"],
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

	if as_of:
		cutover = getdate(as_of)
		pl_accounts = sorted({r.account for r in rows if numbers[r.account].startswith(PL_ACCOUNT_PREFIXES)})
		off_date = sorted({str(r.posting_date) for r in rows if getdate(r.posting_date) != cutover})
		checks.append(
			{
				"name": "bs_only",
				"ok": not pl_accounts,
				"detail": "; ".join(pl_accounts)
				or "không có tài khoản loại 5–9 trong số dư đầu kỳ (kết quả H1 nằm ở 4212)",
			}
		)
		checks.append(
			{
				"name": "on_cutover_date",
				"ok": not off_date,
				"detail": f"bút toán mở sổ ngoài ngày chốt {cutover}: {'; '.join(off_date)}"
				if off_date
				else f"mọi bút toán mở sổ đúng ngày chốt {cutover}",
			}
		)

	return {"ok": all(c["ok"] for c in checks), "checks": checks, "totals": totals}


def _backup_key(company):
	return f"vn_go_live_backup:{frappe.scrub(company)}"


def mark_backup_verified(company, verified=True):
	"""Operator marker set once a production backup has been taken AND verified."""
	frappe.db.set_default(_backup_key(company), "1" if verified else "0")


def _check(name, ok, detail):
	return {"name": name, "ok": bool(ok), "detail": detail}


def _check_on_tt99(company):
	chart = frappe.db.get_value("Company", company, "chart_of_accounts")
	return _check("on_tt99", chart == CHART_NAME, chart or "chưa đặt biểu đồ tài khoản")


def _check_fiscal_year_open(company):
	fy = frappe.db.sql(
		"""select name from `tabFiscal Year`
		where %s between year_start_date and year_end_date and disabled = 0 limit 1""",
		(nowdate(),),
	)
	return _check("fiscal_year_open", bool(fy), fy[0][0] if fy else "không có năm tài chính cho hôm nay")


def _check_company_defaults(company):
	comp = frappe.get_doc("Company", company)
	expected = {
		"default_receivable_account": "131",
		"default_payable_account": "331",
		"default_inventory_account": "156",
		"default_expense_account": "632",
		"default_income_account": "511",
	}
	bad = []
	for field, number in expected.items():
		acc = comp.get(field)
		if (frappe.db.get_value("Account", acc, "account_number") if acc else None) != number:
			bad.append(f"{field}→{number}")
	return _check("company_defaults", not bad, "; ".join(bad) or "131/331/156/632/511 OK")


def _check_naming_series(company):
	missing = [
		s
		for dt, s in VN_NAMING_SERIES
		if s not in (frappe.get_meta(dt).get_field("naming_series").options or "").split("\n")
	]
	return _check("naming_series", not missing, "; ".join(missing) or "đủ số hiệu chứng từ VN")


def _check_perpetual_inventory(company):
	on = frappe.db.get_value("Company", company, "enable_perpetual_inventory")
	return _check("perpetual_inventory", bool(on), "bật" if on else "chưa bật kế toán kho liên tục")


def _check_has_warehouse(company):
	n = frappe.db.count("Warehouse", {"company": company, "is_group": 0})
	return _check("has_warehouse", n > 0, f"{n} kho")


def _check_role_profiles(company):
	missing = [name for name in VN_ROLE_PROFILES if not frappe.db.exists("Role Profile", name)]
	return _check("role_profiles", not missing, "; ".join(missing) or "đủ nhóm quyền VN")


def _check_no_numberless_accounts(company):
	# ERPNext creates a handful of numberless utility accounts (Round Off, SRBNB,
	# Stock Adjustment, Disposal…) that the Company references as defaults — those are
	# legitimate. Only a numberless account the Company does NOT reference is rogue
	# (e.g. an English/Standard-chart leftover the TT99 switch missed).
	comp = frappe.get_doc("Company", company)
	account_fields = frappe.get_meta("Company").get("fields", {"fieldtype": "Link", "options": "Account"})
	referenced = {comp.get(df.fieldname) for df in account_fields if comp.get(df.fieldname)}
	numberless = frappe.get_all(
		"Account",
		filters={"company": company, "is_group": 0, "account_number": ["in", ["", None]]},
		pluck="name",
	)
	rogue = [a for a in numberless if a not in referenced]
	return _check(
		"no_rogue_numberless_accounts",
		not rogue,
		f"{len(rogue)} tài khoản lạ chưa có số hiệu: {'; '.join(rogue[:5])}"
		if rogue
		else "chỉ còn tài khoản tiện ích hệ thống (hợp lệ)",
	)


def _check_opening_balanced(company, as_of=None):
	r = validate_opening_balances(company, as_of=as_of)
	bad = "; ".join(c["detail"] for c in r["checks"] if not c["ok"])
	return _check("opening_balanced", r["ok"], bad or "số dư đầu kỳ hợp lệ")


def _check_backup_verified(company):
	val = frappe.db.get_value("DefaultValue", {"defkey": _backup_key(company)}, "defvalue")
	ok = val == "1"
	return _check("backup_verified", ok, "đã sao lưu & xác minh" if ok else "chưa đánh dấu đã sao lưu")


@frappe.whitelist()
def go_live_readiness(company, as_of=None):
	"""Full go-live precondition checklist for a VN company (read-only).

	``as_of`` (optional) is passed through to the opening-balance validation for a
	mid-year cutover (see ``validate_opening_balances``).
	"""
	if not _is_vn(company):
		return {"ok": False, "checks": [_check("vietnam", False, "không phải công ty Việt Nam")]}

	checks = [
		_check_on_tt99(company),
		_check_fiscal_year_open(company),
		_check_company_defaults(company),
		_check_naming_series(company),
		_check_perpetual_inventory(company),
		_check_has_warehouse(company),
		_check_role_profiles(company),
		_check_no_numberless_accounts(company),
		_check_opening_balanced(company, as_of=as_of),
		_check_backup_verified(company),
	]
	return {"ok": all(c["ok"] for c in checks), "checks": checks}


@frappe.whitelist()
def print_go_live_readiness(company):
	"""Human-readable go-live checklist for ``bench execute``."""
	result = go_live_readiness(company)
	header = "✅ SẴN SÀNG GO-LIVE" if result["ok"] else "❌ CHƯA SẴN SÀNG"
	lines = [f"{header} — {company}"]
	lines += [f"  [{'✓' if c['ok'] else '✗'}] {c['name']}: {c['detail']}" for c in result["checks"]]
	msg = "\n".join(lines)
	print(msg)
	return msg

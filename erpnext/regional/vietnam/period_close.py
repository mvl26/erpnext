# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

"""Kết chuyển cuối kỳ về TK 911 (xác định kết quả kinh doanh) — TT99/2025.

``ket_chuyen_911(company, period)`` computes (and, with ``preview=0``, posts — Task
47) the month-end closing set: doanh thu/thu nhập (5xx/7xx) → 911, 911 → chi phí
(6xx/8xx), and the net result → 4212. The preview is pure — it reads the GL and
writes nothing. Balances are taken as of period end, so an account already zeroed
by a previous kết chuyển contributes only its new movements. Integrates with —
never replaces — ERPNext's Period Closing Voucher / Accounting Period lock.
"""

import frappe
from frappe.utils import flt, get_last_day, getdate

from erpnext.regional.vietnam.setup import _acct
from erpnext.regional.vietnam.utils import get_account_balances

INCOME_PREFIXES = ("5", "7")
EXPENSE_PREFIXES = ("6", "8")
RESULT_ACCOUNT = "911"
RETAINED_ACCOUNT = "4212"  # LNST chưa phân phối năm nay
EPOCH = "1900-01-01"


def _is_vn(company):
	return bool(company) and frappe.db.get_value("Company", company, "country") == "Vietnam"


def _period_bounds(period):
	"""``period`` = "YYYY-MM" → (first day, last day)."""
	start = getdate(f"{period}-01")
	return start, get_last_day(start)


def _zeroing_line(balance):
	"""JE amounts that bring an account with net (debit-credit) ``balance`` to zero."""
	return (flt(-balance), 0.0) if balance < 0 else (0.0, flt(balance))


def _entry(title, account_lines, company):
	"""One closing JE spec: the account lines plus the balancing 911 line."""
	dr_total = sum(line["debit"] for line in account_lines)
	cr_total = sum(line["credit"] for line in account_lines)
	diff = flt(dr_total - cr_total)
	nine_eleven = {
		"account": _acct(company, RESULT_ACCOUNT),
		"account_number": RESULT_ACCOUNT,
		"debit": flt(-diff) if diff < 0 else 0.0,
		"credit": diff if diff > 0 else 0.0,
	}
	return {"title": title, "lines": [*account_lines, nine_eleven]}


@frappe.whitelist()
def ket_chuyen_911(company, period, preview=1):
	"""Month-end kết chuyển for ``period`` ("YYYY-MM"). Structured result, never raises
	on a "nothing to close" state. ``preview=1`` (default) computes without writing."""
	if not _is_vn(company):
		return {"ok": False, "reason": "not a Vietnam company", "entries": []}

	period_start, period_end = _period_bounds(period)
	balances = get_account_balances(company, EPOCH, str(period_end))

	income_lines, expense_lines = [], []
	income_net = expense_net = 0.0
	for b in balances.values():
		number = b.account_number or ""
		balance = flt(b.closing)
		if not number or abs(balance) < 0.005:
			continue
		line_debit, line_credit = _zeroing_line(balance)
		line = {"account": b.name, "account_number": number, "debit": line_debit, "credit": line_credit}
		if number.startswith(INCOME_PREFIXES):
			income_lines.append(line)
			income_net += -balance  # credit-positive
		elif number.startswith(EXPENSE_PREFIXES):
			expense_lines.append(line)
			expense_net += balance  # debit-positive

	entries = []
	if income_lines:
		entries.append(_entry("Kết chuyển doanh thu, thu nhập → 911", income_lines, company))
	if expense_lines:
		entries.append(_entry("Kết chuyển 911 → chi phí", expense_lines, company))

	result = flt(income_net - expense_net)
	if entries and abs(result) >= 0.005:
		amount = abs(result)
		entries.append(
			{
				"title": "Kết chuyển kết quả kinh doanh 911 → 4212",
				"lines": [
					{
						"account": _acct(company, RESULT_ACCOUNT),
						"account_number": RESULT_ACCOUNT,
						"debit": amount if result > 0 else 0.0,
						"credit": amount if result < 0 else 0.0,
					},
					{
						"account": _acct(company, RETAINED_ACCOUNT),
						"account_number": RETAINED_ACCOUNT,
						"debit": amount if result < 0 else 0.0,
						"credit": amount if result > 0 else 0.0,
					},
				],
			}
		)

	return {
		"ok": True,
		"company": company,
		"period": period,
		"period_start": str(period_start),
		"period_end": str(period_end),
		"entries": entries,
		"result": result,
	}

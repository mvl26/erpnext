# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Quyết toán thuế TNDN (VN corporate income tax summary).

GL-based CIT summary (chi phí thuế TNDN từ TK 821/8211/8212 và thuế phải nộp trên
TK 3334). If mvl_accounting has computed provisional CIT (MVL CIT Provisional),
its lợi nhuận kế toán / thu nhập tính thuế / thuế tạm tính are surfaced too —
read-only, never recomputed here. Flagged for accountant verification.
"""

import frappe
from frappe import _
from frappe.utils import flt

from erpnext.regional.vietnam.utils import get_account_balances, sum_movement_by_prefix

VERIFY_NOTE = _(
	"⚠️ Bản nháp — Tổng hợp từ TK 821/3334; số liệu tạm tính lấy từ mvl_accounting "
	"nếu có. Kế toán kiểm tra trước khi nộp."
)


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters), VERIFY_NOTE


def get_columns():
	return [
		{"label": _("Chỉ tiêu"), "fieldname": "chi_tieu", "fieldtype": "Data", "width": 420},
		{"label": _("Số tiền"), "fieldname": "so_tien", "fieldtype": "Currency", "width": 180},
	]


def _read_mvl_provisional(company, from_date, to_date):
	"""Best-effort read of mvl_accounting's provisional CIT; None if unavailable."""
	try:
		if not frappe.db.table_exists("MVL CIT Provisional"):
			return None
		rows = frappe.get_all(
			"MVL CIT Provisional",
			filters={"company": company, "posting_date": ["between", [from_date, to_date]]},
			fields=["accounting_profit", "taxable_income", "cit_amount"],
		)
		if not rows:
			return None
		return {
			"accounting_profit": sum(flt(r.accounting_profit) for r in rows),
			"taxable_income": sum(flt(r.taxable_income) for r in rows),
			"cit_amount": sum(flt(r.cit_amount) for r in rows),
		}
	except Exception:
		return None


def get_data(filters):
	if not (filters.company and filters.from_date and filters.to_date):
		return []

	b = get_account_balances(filters.company, filters.from_date, filters.to_date)
	payable = [x for x in b.values() if (x.account_number or "").startswith("3334")]

	current_cit = sum_movement_by_prefix(b, ["8211"])
	deferred_cit = sum_movement_by_prefix(b, ["8212"])
	total_cit = sum_movement_by_prefix(b, ["821"])

	rows = []
	mvl = _read_mvl_provisional(filters.company, filters.from_date, filters.to_date)
	if mvl:
		rows += [
			{"chi_tieu": _("Lợi nhuận kế toán (mvl_accounting)"), "so_tien": mvl["accounting_profit"]},
			{"chi_tieu": _("Thu nhập tính thuế (mvl_accounting)"), "so_tien": mvl["taxable_income"]},
			{"chi_tieu": _("Thuế TNDN tạm tính (mvl_accounting)"), "so_tien": mvl["cit_amount"]},
		]

	rows += [
		{"chi_tieu": _("Chi phí thuế TNDN hiện hành"), "so_tien": current_cit},
		{"chi_tieu": _("Chi phí thuế TNDN hoãn lại"), "so_tien": deferred_cit},
		{"chi_tieu": _("Tổng chi phí thuế TNDN"), "so_tien": total_cit},
		{"chi_tieu": _("Thuế TNDN phải nộp phát sinh trong kỳ"), "so_tien": sum(x.credit for x in payable)},
		{"chi_tieu": _("Thuế TNDN đã nộp"), "so_tien": sum(x.debit for x in payable)},
		{
			"chi_tieu": _("Thuế TNDN còn phải nộp cuối kỳ"),
			"so_tien": -sum(x.closing for x in payable),
			"is_total": 1,
		},
	]
	return rows

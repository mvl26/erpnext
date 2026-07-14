# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

"""Quyết toán thuế TNCN (VN personal income tax summary).

Summarises PIT from the GL account 3335 (thuế thu nhập cá nhân): đã khấu trừ
(credit movement), đã nộp NSNN (debit movement), còn phải nộp (closing).

NOTE: the full 05/QTT-TNCN finalization needs per-employee income data from
payroll (hrms). This report gives the company-level GL summary; per-employee
detail is a payroll-dependent follow-up. Flagged for accountant verification.
"""

import frappe
from frappe import _

from erpnext.regional.vietnam.utils import get_account_balances

VERIFY_NOTE = _(
	"⚠️ Bản nháp — Tổng hợp từ TK 3335. Quyết toán chi tiết theo từng cá nhân cần "
	"dữ liệu tiền lương (payroll); kế toán kiểm tra trước khi nộp."
)

PIT_ACCOUNT = "3335"


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters), VERIFY_NOTE


def get_columns():
	return [
		{"label": _("Chỉ tiêu"), "fieldname": "chi_tieu", "fieldtype": "Data", "width": 420},
		{"label": _("Số tiền"), "fieldname": "so_tien", "fieldtype": "Currency", "width": 180},
	]


def get_data(filters):
	if not (filters.company and filters.from_date and filters.to_date):
		return []

	b = get_account_balances(filters.company, filters.from_date, filters.to_date)
	pit = [x for x in b.values() if (x.account_number or "").startswith(PIT_ACCOUNT)]

	opening = -sum(x.opening for x in pit)  # còn phải nộp đầu kỳ (credit-positive)
	withheld = sum(x.credit for x in pit)  # phát sinh khấu trừ
	paid = sum(x.debit for x in pit)  # đã nộp NSNN
	closing = -sum(x.closing for x in pit)  # còn phải nộp cuối kỳ

	return [
		{"chi_tieu": _("Thuế TNCN còn phải nộp đầu kỳ"), "so_tien": opening},
		{"chi_tieu": _("Thuế TNCN đã khấu trừ trong kỳ"), "so_tien": withheld},
		{"chi_tieu": _("Thuế TNCN đã nộp Ngân sách Nhà nước"), "so_tien": paid},
		{"chi_tieu": _("Thuế TNCN còn phải nộp cuối kỳ"), "so_tien": closing, "is_total": 1},
	]

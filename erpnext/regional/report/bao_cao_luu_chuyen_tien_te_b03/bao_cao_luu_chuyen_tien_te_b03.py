# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

"""B03-DN — Báo cáo lưu chuyển tiền tệ (VN cash flow, indirect method).

Đầu tư and tài chính flows are derived from the period movement of their
accounts; hoạt động kinh doanh is the residual so that 20 + 30 + 40 == biến động
tiền by double entry (Δtiền = -Σ biến động các tài khoản không phải tiền). The
account→activity classification is RESEARCH-DERIVED and must be verified by a
kế toán before filing.
"""

import frappe
from frappe import _

from erpnext.regional.vietnam.constants import CASH_ACCOUNT_PREFIXES
from erpnext.regional.vietnam.utils import get_account_balances, sum_movement_by_prefix

VERIFY_NOTE = _(
	"⚠️ Bản nháp — Mã số theo Thông tư 99/2025/TT-BTC cần kế toán kiểm tra trước khi nộp."
)

INVESTING_PREFIXES = [
	"121", "128", "171", "211", "212", "213", "214", "215", "217",
	"221", "222", "228", "229", "241", "243",
]
FINANCING_PREFIXES = ["341", "343", "344", "411", "412", "413", "414", "418", "419", "332"]


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters), VERIFY_NOTE


def get_columns():
	return [
		{"label": _("Chỉ tiêu"), "fieldname": "chi_tieu", "fieldtype": "Data", "width": 460},
		{"label": _("Mã số"), "fieldname": "ma_so", "fieldtype": "Data", "width": 80},
		{"label": _("Số tiền"), "fieldname": "so_tien", "fieldtype": "Currency", "width": 180},
	]


def get_data(filters):
	if not (filters.company and filters.from_date and filters.to_date):
		return []

	b = get_account_balances(filters.company, filters.from_date, filters.to_date)
	cash = [x for x in b.values() if (x.account_number or "").startswith(tuple(CASH_ACCOUNT_PREFIXES))]
	opening_cash = sum(x.opening for x in cash)
	closing_cash = sum(x.closing for x in cash)
	delta_cash = closing_cash - opening_cash

	investing = -sum_movement_by_prefix(b, INVESTING_PREFIXES)
	financing = -sum_movement_by_prefix(b, FINANCING_PREFIXES)
	operating = delta_cash - investing - financing

	profit_before_tax = (
		-sum(x.closing - x.opening for x in b.values() if x.root_type == "Income")
		- sum(x.closing - x.opening for x in b.values() if x.root_type == "Expense")
		+ sum_movement_by_prefix(b, ["821"])
	)

	return [
		{"chi_tieu": _("I. Lưu chuyển tiền từ hoạt động kinh doanh"), "is_header": 1},
		{"chi_tieu": _("1. Lợi nhuận trước thuế"), "ma_so": "01", "so_tien": profit_before_tax},
		{
			"chi_tieu": _("2. Điều chỉnh & thay đổi vốn lưu động"),
			"ma_so": "08",
			"so_tien": operating - profit_before_tax,
		},
		{
			"chi_tieu": _("Lưu chuyển tiền thuần từ hoạt động kinh doanh"),
			"ma_so": "20",
			"so_tien": operating,
			"is_total": 1,
		},
		{"chi_tieu": _("II. Lưu chuyển tiền từ hoạt động đầu tư"), "is_header": 1},
		{
			"chi_tieu": _("Lưu chuyển tiền thuần từ hoạt động đầu tư"),
			"ma_so": "30",
			"so_tien": investing,
			"is_total": 1,
		},
		{"chi_tieu": _("III. Lưu chuyển tiền từ hoạt động tài chính"), "is_header": 1},
		{
			"chi_tieu": _("Lưu chuyển tiền thuần từ hoạt động tài chính"),
			"ma_so": "40",
			"so_tien": financing,
			"is_total": 1,
		},
		{
			"chi_tieu": _("Lưu chuyển tiền thuần trong kỳ"),
			"ma_so": "50",
			"so_tien": delta_cash,
			"is_total": 1,
		},
		{"chi_tieu": _("Tiền và tương đương tiền đầu kỳ"), "ma_so": "60", "so_tien": opening_cash},
		{
			"chi_tieu": _("Tiền và tương đương tiền cuối kỳ"),
			"ma_so": "70",
			"so_tien": closing_cash,
			"is_total": 1,
		},
	]

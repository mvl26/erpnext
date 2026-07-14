# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

"""B02-DN — Báo cáo kết quả hoạt động kinh doanh (VN income statement).

Mã-số → account mapping is RESEARCH-DERIVED from the TT99/TT200 lineage and must
be verified by a kế toán before filing. Computed read-only over the period
movement of the P&L accounts (income = credit-net, expense = debit-net).
"""

import frappe
from frappe import _
from frappe.utils import flt

from erpnext.regional.vietnam.utils import get_account_balances, sum_movement_by_prefix

VERIFY_NOTE = _(
	"⚠️ Bản nháp — Mã số theo Thông tư 99/2025/TT-BTC cần kế toán kiểm tra trước khi nộp."
)

# (mã số, chỉ tiêu, kind, spec)
#   income  -> credit-net movement of the prefixes  (= -Σ(debit-credit))
#   expense -> debit-net movement of the prefixes   (=  Σ(debit-credit))
#   memo    -> fixed value (needs a dedicated sub-account to populate)
#   formula -> function of previously computed mã số values
B02_LINES = [
	("01", "Doanh thu bán hàng và cung cấp dịch vụ", "income", ["511"]),
	("02", "Các khoản giảm trừ doanh thu", "expense", ["521"]),
	("10", "Doanh thu thuần về bán hàng và cung cấp dịch vụ", "formula", lambda v: v["01"] - v["02"]),
	("11", "Giá vốn hàng bán", "expense", ["632"]),
	("20", "Lợi nhuận gộp về bán hàng và cung cấp dịch vụ", "formula", lambda v: v["10"] - v["11"]),
	("21", "Doanh thu hoạt động tài chính", "income", ["515"]),
	("22", "Chi phí tài chính", "expense", ["635"]),
	("23", "     Trong đó: Chi phí lãi vay", "memo", 0.0),
	("25", "Chi phí bán hàng", "expense", ["641"]),
	("26", "Chi phí quản lý doanh nghiệp", "expense", ["642"]),
	(
		"30",
		"Lợi nhuận thuần từ hoạt động kinh doanh",
		"formula",
		lambda v: v["20"] + v["21"] - v["22"] - v["25"] - v["26"],
	),
	("31", "Thu nhập khác", "income", ["711"]),
	("32", "Chi phí khác", "expense", ["811"]),
	("40", "Lợi nhuận khác", "formula", lambda v: v["31"] - v["32"]),
	("50", "Tổng lợi nhuận kế toán trước thuế", "formula", lambda v: v["30"] + v["40"]),
	("51", "Chi phí thuế TNDN hiện hành", "expense", ["8211"]),
	("52", "Chi phí thuế TNDN hoãn lại", "expense", ["8212"]),
	("60", "Lợi nhuận sau thuế thu nhập doanh nghiệp", "formula", lambda v: v["50"] - v["51"] - v["52"]),
]


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	data = get_data(filters)
	return columns, data, VERIFY_NOTE


def get_columns():
	return [
		{"label": _("Chỉ tiêu"), "fieldname": "chi_tieu", "fieldtype": "Data", "width": 420},
		{"label": _("Mã số"), "fieldname": "ma_so", "fieldtype": "Data", "width": 80},
		{"label": _("Số tiền"), "fieldname": "so_tien", "fieldtype": "Currency", "width": 180},
	]


def get_data(filters):
	if not (filters.company and filters.from_date and filters.to_date):
		return []

	balances = get_account_balances(filters.company, filters.from_date, filters.to_date)
	values = {}
	data = []
	for ma_so, chi_tieu, kind, spec in B02_LINES:
		if kind == "income":
			val = -sum_movement_by_prefix(balances, spec)
		elif kind == "expense":
			val = sum_movement_by_prefix(balances, spec)
		elif kind == "memo":
			val = flt(spec)
		else:
			val = spec(values)
		values[ma_so] = val
		data.append({"chi_tieu": chi_tieu, "ma_so": ma_so, "so_tien": val})
	return data

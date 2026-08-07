# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""B01-DN — Báo cáo tình hình tài chính (VN balance sheet).

Section TOTALS (270 Tổng tài sản, 300 Nợ phải trả, 400 Vốn CSH, 440 Tổng nguồn
vốn) are derived from account root_type sums plus current-year profit, so
270 == 440 holds by double entry regardless of the detail mapping. The caption
lines (110/120/... and 300/400 breakdown) are RESEARCH-DERIVED from TT99/TT200
and must be verified by a kế toán before filing; a catch-all line absorbs any
unmapped account so the detail still sums to the authoritative total.
"""

import frappe
from frappe import _

from erpnext.regional.vietnam.utils import get_account_balances, sum_closing_by_prefix

VERIFY_NOTE = _(
	"⚠️ Bản nháp — Mã số theo Thông tư 99/2025/TT-BTC cần kế toán kiểm tra trước khi nộp."
)

# Asset captions (debit-positive). Prefixes cover every numbered asset account.
ASSET_CURRENT = [
	("110", "I. Tiền và các khoản tương đương tiền", ["111", "112", "113"]),
	("120", "II. Đầu tư tài chính ngắn hạn", ["121", "128", "171"]),
	("130", "III. Các khoản phải thu ngắn hạn", ["131", "136", "138", "141"]),
	("140", "IV. Hàng tồn kho", ["151", "152", "153", "154", "155", "156", "157", "158"]),
	("150", "V. Tài sản ngắn hạn khác", ["133"]),
]
ASSET_LONG = [
	("220", "II. Tài sản cố định", ["211", "212", "213", "214"]),
	("230", "III. Bất động sản đầu tư", ["217"]),
	("240", "IV. Tài sản dở dang dài hạn", ["241"]),
	("250", "V. Đầu tư tài chính dài hạn", ["221", "222", "228", "229"]),
	("260", "VI. Tài sản dài hạn khác", ["215", "242", "243", "244"]),
]
# Liability captions (credit-positive).
LIABILITIES = [
	(
		"310",
		"I. Nợ ngắn hạn",
		["331", "332", "333", "334", "335", "336", "337", "338", "341", "343", "344", "353", "357"],
	),
	("330", "II. Nợ dài hạn", ["347", "352", "356"]),
]
# Equity captions (credit-positive); 421 also carries current-year profit.
EQUITY = [
	("411", "I. Vốn góp của chủ sở hữu", ["411", "412", "413", "419"]),
	("417", "II. Quỹ thuộc vốn chủ sở hữu", ["414", "418"]),
]


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters), VERIFY_NOTE


def get_columns():
	return [
		{"label": _("Chỉ tiêu"), "fieldname": "chi_tieu", "fieldtype": "Data", "width": 420},
		{"label": _("Mã số"), "fieldname": "ma_so", "fieldtype": "Data", "width": 80},
		{"label": _("Số cuối kỳ"), "fieldname": "so_tien", "fieldtype": "Currency", "width": 180},
	]


def get_data(filters):
	if not (filters.company and filters.from_date and filters.to_date):
		return []

	b = get_account_balances(filters.company, filters.from_date, filters.to_date)

	def debit(prefixes):
		return sum_closing_by_prefix(b, prefixes)

	def credit(prefixes):
		return -sum_closing_by_prefix(b, prefixes)

	def root(root_type):
		return sum(x.closing for x in b.values() if x.root_type == root_type)

	asset_total = root("Asset")
	liability_total = -root("Liability")
	equity_accounts = -root("Equity")
	profit = -root("Income") - root("Expense")  # lãi/lỗ chưa phân phối trong kỳ
	equity_total = equity_accounts + profit
	nguon_von_total = liability_total + equity_total

	rows = [{"chi_tieu": _("TÀI SẢN"), "is_header": 1}]

	current = [(mn, name, debit(p)) for mn, name, p in ASSET_CURRENT]
	rows.append({"chi_tieu": _("A. TÀI SẢN NGẮN HẠN"), "ma_so": "100",
		"so_tien": sum(x[2] for x in current)})
	rows += [{"chi_tieu": name, "ma_so": mn, "so_tien": val} for mn, name, val in current]

	longs = [(mn, name, debit(p)) for mn, name, p in ASSET_LONG]
	rows.append({"chi_tieu": _("B. TÀI SẢN DÀI HẠN"), "ma_so": "200",
		"so_tien": sum(x[2] for x in longs)})
	rows += [{"chi_tieu": name, "ma_so": mn, "so_tien": val} for mn, name, val in longs]

	other_asset = asset_total - sum(x[2] for x in current) - sum(x[2] for x in longs)
	if other_asset:
		rows.append({"chi_tieu": _("Tài sản khác chưa phân loại"), "ma_so": "268", "so_tien": other_asset})
	rows.append({"chi_tieu": _("TỔNG CỘNG TÀI SẢN"), "ma_so": "270", "so_tien": asset_total, "is_total": 1})

	rows.append({"chi_tieu": _("NGUỒN VỐN"), "is_header": 1})

	liabs = [(mn, name, credit(p)) for mn, name, p in LIABILITIES]
	other_liab = liability_total - sum(x[2] for x in liabs)
	rows += [{"chi_tieu": name, "ma_so": mn, "so_tien": val} for mn, name, val in liabs]
	if other_liab:
		rows.append({"chi_tieu": _("Nợ phải trả khác chưa phân loại"), "ma_so": "319", "so_tien": other_liab})
	rows.append({"chi_tieu": _("C. NỢ PHẢI TRẢ"), "ma_so": "300", "so_tien": liability_total, "is_total": 1})

	eq = [(mn, name, credit(p)) for mn, name, p in EQUITY]
	profit_line = credit(["421"]) + profit
	rows += [{"chi_tieu": name, "ma_so": mn, "so_tien": val} for mn, name, val in eq]
	rows.append({"chi_tieu": _("Lợi nhuận sau thuế chưa phân phối"), "ma_so": "421", "so_tien": profit_line})
	other_eq = equity_total - sum(x[2] for x in eq) - profit_line
	if other_eq:
		rows.append({"chi_tieu": _("Vốn chủ sở hữu khác"), "ma_so": "418", "so_tien": other_eq})
	rows.append({"chi_tieu": _("D. VỐN CHỦ SỞ HỮU"), "ma_so": "400", "so_tien": equity_total, "is_total": 1})

	rows.append({"chi_tieu": _("TỔNG CỘNG NGUỒN VỐN"), "ma_so": "440", "so_tien": nguon_von_total, "is_total": 1})
	return rows

# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

"""Shared TT99 constants for Vietnam accounting reports.

Statutory Mã-số → account-range tables live next to each report; the values here
are cross-report account groupings used by more than one statement/book.
"""

CHART_NAME = "Vietnam - Chart of Accounts (Thông tư 99/2025/TT-BTC)"

# Cash & cash-equivalent account prefixes (dùng cho B03 Lưu chuyển tiền tệ).
CASH_ACCOUNT_PREFIXES = ("111", "112", "113")

# GTGT (VAT) accounts.
OUTPUT_VAT_ACCOUNT = "33311"  # thuế GTGT đầu ra (phải nộp)
INPUT_VAT_ACCOUNT = "1331"  # thuế GTGT được khấu trừ

# Root-type → statement.
BALANCE_SHEET_ROOT_TYPES = ("Asset", "Liability", "Equity")
PROFIT_AND_LOSS_ROOT_TYPES = ("Income", "Expense")

# TT99 P&L account-number prefixes (loại 5–9: doanh thu, chi phí, thu nhập/chi phí
# khác, xác định KQKD) — excluded from a mid-year (BS-only) opening trial balance.
PL_ACCOUNT_PREFIXES = ("5", "6", "7", "8", "9")

# VN document naming series, added as *additional* options at go-live (never
# replacing the shipped defaults). Prefix + ".YYYY.-" yields e.g. HDB-2027-00001.
VN_NAMING_SERIES = (
	("Sales Invoice", "HDB-.YYYY.-"),  # hóa đơn bán
	("Purchase Invoice", "HDM-.YYYY.-"),  # hóa đơn mua
	("Journal Entry", "PKT-.YYYY.-"),  # phiếu kế toán
	("Payment Entry", "TT-.YYYY.-"),  # thanh toán (thu/chi)
	("Delivery Note", "PXK-.YYYY.-"),  # phiếu xuất kho
	("Stock Entry", "PK-.YYYY.-"),  # phiếu kho
)

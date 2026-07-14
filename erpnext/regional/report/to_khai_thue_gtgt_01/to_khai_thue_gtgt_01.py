# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

"""Tờ khai thuế GTGT — mẫu 01/GTGT (VN VAT return).

Output VAT from TK 33311 (thuế GTGT đầu ra) and deductible input VAT from TK 133x
(thuế GTGT được khấu trừ) over the period; số thuế phải nộp = đầu ra − khấu trừ.
Assumes full deduction (khấu trừ toàn bộ). Indicator codes are RESEARCH-DERIVED
and must be verified by a kế toán before filing.
"""

import frappe
from frappe import _

from erpnext.regional.vietnam.constants import INPUT_VAT_ACCOUNT, OUTPUT_VAT_ACCOUNT
from erpnext.regional.vietnam.utils import get_account_balances, sum_movement_by_prefix

VERIFY_NOTE = _(
	"⚠️ Bản nháp — Chỉ tiêu tờ khai 01/GTGT cần kế toán kiểm tra trước khi nộp. "
	"Giả định khấu trừ toàn bộ thuế đầu vào."
)


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters), VERIFY_NOTE


def get_columns():
	return [
		{"label": _("Chỉ tiêu"), "fieldname": "chi_tieu", "fieldtype": "Data", "width": 460},
		{"label": _("Mã chỉ tiêu"), "fieldname": "chi_tieu_code", "fieldtype": "Data", "width": 110},
		{"label": _("Số tiền"), "fieldname": "so_tien", "fieldtype": "Currency", "width": 180},
	]


def get_data(filters):
	if not (filters.company and filters.from_date and filters.to_date):
		return []

	b = get_account_balances(filters.company, filters.from_date, filters.to_date)

	# Output VAT = credit movement of 33311; input VAT = debit movement of 133x.
	output_vat = -sum_movement_by_prefix(b, [OUTPUT_VAT_ACCOUNT])
	input_vat = sum_movement_by_prefix(b, [INPUT_VAT_ACCOUNT[:3]])  # 133 -> 1331 + 1332
	deductible = input_vat  # khấu trừ toàn bộ
	payable = max(output_vat - deductible, 0.0)
	carry_forward = max(deductible - output_vat, 0.0)

	return [
		{
			"chi_tieu": _("Thuế GTGT của HHDV mua vào"),
			"chi_tieu_code": "24",
			"so_tien": input_vat,
		},
		{
			"chi_tieu": _("Thuế GTGT được khấu trừ kỳ này"),
			"chi_tieu_code": "25",
			"so_tien": deductible,
		},
		{
			"chi_tieu": _("Thuế GTGT của HHDV bán ra"),
			"chi_tieu_code": "33",
			"so_tien": output_vat,
		},
		{
			"chi_tieu": _("Thuế GTGT phải nộp trong kỳ"),
			"chi_tieu_code": "40",
			"so_tien": payable,
			"is_total": 1,
		},
		{
			"chi_tieu": _("Thuế GTGT chưa khấu trừ hết kỳ này"),
			"chi_tieu_code": "41",
			"so_tien": carry_forward,
		},
	]

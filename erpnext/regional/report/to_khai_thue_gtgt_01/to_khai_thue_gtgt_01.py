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
from frappe.utils import flt

from erpnext.regional.vietnam.constants import INPUT_VAT_ACCOUNT, OUTPUT_VAT_ACCOUNT
from erpnext.regional.vietnam.setup import _acct
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


# --- Bảng kê hóa đơn (invoice listings backing the declaration) ---------------

# kind → (invoice doctype, tax child doctype, partner-name field, GTGT account number)
BANG_KE_SOURCES = {
	"ban_ra": ("Sales Invoice", "Sales Taxes and Charges", "customer_name", OUTPUT_VAT_ACCOUNT),
	"mua_vao": ("Purchase Invoice", "Purchase Taxes and Charges", "supplier_name", INPUT_VAT_ACCOUNT),
}


@frappe.whitelist()
def bang_ke_ban_ra(company, from_date, to_date):
	"""Bảng kê hóa đơn bán ra — one row per submitted Sales Invoice in the period."""
	return _bang_ke(company, from_date, to_date, "ban_ra")


@frappe.whitelist()
def bang_ke_mua_vao(company, from_date, to_date):
	"""Bảng kê hóa đơn mua vào — one row per submitted Purchase Invoice in the period."""
	return _bang_ke(company, from_date, to_date, "mua_vao")


def _bang_ke(company, from_date, to_date, kind):
	doctype, tax_doctype, partner_field, vat_number = BANG_KE_SOURCES[kind]
	vat_account = _acct(company, vat_number)

	fields = ["name", "posting_date", partner_field, "tax_id", "base_net_total"]
	meta = frappe.get_meta(doctype)
	has_einvoice = meta.has_field("vn_einvoice_number")
	if has_einvoice:
		fields += ["vn_einvoice_number", "vn_einvoice_symbol"]

	invoices = frappe.get_all(
		doctype,
		filters={
			"company": company,
			"docstatus": 1,
			"posting_date": ["between", [from_date, to_date]],
		},
		fields=fields,
		order_by="posting_date, name",
	)
	if not invoices:
		return []

	taxes = frappe.get_all(
		tax_doctype,
		filters={
			"parenttype": doctype,
			"parent": ["in", [inv.name for inv in invoices]],
			"account_head": vat_account,
			"docstatus": 1,
		},
		fields=["parent", "rate", "base_tax_amount"],
	)
	tax_by_invoice = {}
	for tax in taxes:
		entry = tax_by_invoice.setdefault(tax.parent, {"rate": flt(tax.rate), "amount": 0.0})
		entry["amount"] += flt(tax.base_tax_amount)

	rows = []
	for inv in invoices:
		tax = tax_by_invoice.get(inv.name, {"rate": 0.0, "amount": 0.0})
		rows.append(
			{
				"so_hoa_don": (has_einvoice and inv.get("vn_einvoice_number")) or inv.name,
				"ky_hieu": (has_einvoice and inv.get("vn_einvoice_symbol")) or "",
				"ngay": str(inv.posting_date),
				"doi_tac": inv.get(partner_field),
				"mst": inv.get("tax_id") or "",
				"doanh_so": flt(inv.base_net_total),
				"thue_suat": tax["rate"],
				"tien_thue": tax["amount"],
			}
		)
	return rows


@frappe.whitelist()
def export_bang_ke(company, from_date, to_date, kind="ban_ra"):
	"""Bảng kê as CSV (UTF-8) — for filing support / import into HTKK-side tooling."""
	from frappe.utils.csvutils import to_csv

	rows = _bang_ke(company, from_date, to_date, kind)
	headers = [
		"Số hóa đơn",
		"Ký hiệu",
		"Ngày",
		"Tên đối tác",
		"MST",
		"Doanh số chưa thuế",
		"Thuế suất (%)",
		"Tiền thuế",
	]
	data = [headers] + [
		[
			r["so_hoa_don"],
			r["ky_hieu"],
			r["ngay"],
			r["doi_tac"],
			r["mst"],
			r["doanh_so"],
			r["thue_suat"],
			r["tien_thue"],
		]
		for r in rows
	]
	return to_csv(data)

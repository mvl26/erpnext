# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Tờ khai thuế GTGT — mẫu 01/GTGT (VN VAT return).

Output VAT from TK 33311 (thuế GTGT đầu ra) and deductible input VAT from TK 133x
(thuế GTGT được khấu trừ) over the period; số thuế phải nộp = đầu ra − khấu trừ.
Assumes full deduction (khấu trừ toàn bộ). Indicator codes are RESEARCH-DERIVED
and must be verified by a kế toán before filing.
"""

import frappe
from frappe import _
from frappe.utils import flt

from erpnext.regional.vietnam.constants import INPUT_VAT_PREFIX, OUTPUT_VAT_PREFIX
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
	output_vat = -sum_movement_by_prefix(b, [OUTPUT_VAT_PREFIX])
	input_vat = sum_movement_by_prefix(b, [INPUT_VAT_PREFIX])
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

# kind → (invoice doctype, tax child doctype, partner-name field, GTGT number prefix).
# The prefix is the same one the declaration sums over, so bảng kê always ties to it.
BANG_KE_SOURCES = {
	"ban_ra": ("Sales Invoice", "Sales Taxes and Charges", "customer_name", OUTPUT_VAT_PREFIX),
	"mua_vao": ("Purchase Invoice", "Purchase Taxes and Charges", "supplier_name", INPUT_VAT_PREFIX),
}


def _vat_accounts(company, prefix):
	"""Posting accounts whose TT99 number starts with ``prefix`` (133 → 1331, 1332)."""
	return frappe.get_all(
		"Account",
		filters={"company": company, "is_group": 0, "account_number": ["like", f"{prefix}%"]},
		pluck="name",
	)


@frappe.whitelist()
def bang_ke_ban_ra(company, from_date, to_date):
	"""Bảng kê hóa đơn bán ra — one row per submitted Sales Invoice in the period."""
	return _bang_ke(company, from_date, to_date, "ban_ra")


@frappe.whitelist()
def bang_ke_mua_vao(company, from_date, to_date):
	"""Bảng kê hóa đơn mua vào — one row per submitted Purchase Invoice in the period."""
	return _bang_ke(company, from_date, to_date, "mua_vao")


def _bang_ke(company, from_date, to_date, kind):
	doctype, tax_doctype, partner_field, vat_prefix = BANG_KE_SOURCES[kind]
	vat_accounts = _vat_accounts(company, vat_prefix)
	if not vat_accounts:
		return []

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
			"account_head": ["in", vat_accounts],
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
def export_to_khai_xml(company, from_date, to_date, kieu_ky="Q", ky_khai=None, so_lan="0"):
	"""Tờ khai 01/GTGT as eTax-style XML (mã tờ khai 842).

	⚠️ Draft-flagged like the on-screen declaration: the XML structure follows the
	published eTax layout (HSoThueDTu → HSoKhaiThue → TKhaiThue + CTieuTKhaiChinh
	with ct-numbered indicators) but the schema version MUST be verified by the
	kế toán against the current HTKK/eTax release before the first filing (OQ-5).

	``ky_khai`` defaults to the quarter of ``to_date`` (e.g. "3/2026").
	"""
	import xml.etree.ElementTree as ET

	from frappe.utils import getdate

	values = {
		r["chi_tieu_code"]: r["so_tien"]
		for r in get_data(frappe._dict(company=company, from_date=from_date, to_date=to_date))
		if r.get("chi_tieu_code")
	}
	if not ky_khai:
		end = getdate(to_date)
		ky_khai = f"{(end.month - 1) // 3 + 1}/{end.year}"

	root = ET.Element("HSoThueDTu")
	hs_khai_thue = ET.SubElement(root, "HSoKhaiThue")
	ttin_chung = ET.SubElement(hs_khai_thue, "TTinChung")
	tkhai = ET.SubElement(ttin_chung, "TKhaiThue")
	ET.SubElement(tkhai, "maTKhai").text = "842"
	ET.SubElement(tkhai, "tenTKhai").text = "Tờ khai thuế giá trị gia tăng (01/GTGT)"
	ET.SubElement(tkhai, "pbanTKhaiXML").text = "2.0.1"
	ET.SubElement(tkhai, "loaiTKhai").text = "C"
	ET.SubElement(tkhai, "soLan").text = str(so_lan)
	ky = ET.SubElement(tkhai, "KyKKhaiThue")
	ET.SubElement(ky, "kieuKy").text = kieu_ky
	ET.SubElement(ky, "kyKKhai").text = ky_khai
	nnt = ET.SubElement(tkhai, "NNT")
	ET.SubElement(nnt, "mst").text = frappe.db.get_value("Company", company, "tax_id") or ""
	ET.SubElement(nnt, "tenNNT").text = company

	ctieu = ET.SubElement(hs_khai_thue, "CTieuTKhaiChinh")
	for code in ("24", "25", "33", "40", "41"):
		ET.SubElement(ctieu, f"ct{code}").text = str(int(round(flt(values.get(code)))))

	return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode")


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

# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Dữ liệu mẫu dùng chung cho test HĐĐT: khách hàng, hàng hóa, phiếu giao hàng.

Site `miyano` không có Item/Customer/Delivery Note nào, nên bộ test phải tự dựng.
Tất cả đều get-or-create: chạy lại không nhân bản, và an toàn cả khi một test
trước đó đã commit (xem ghi chú về DDL trong tài liệu môi trường test).
"""

import frappe
from frappe.utils import nowdate

COMPANY = "Miyano"
WAREHOUSE = "Stores - M"
ITEM_CODE = "_TEST-HDDT-VT001"
ITEM_NAME = "Bơm kim tiêm 5ml"
CUSTOMER = "_Test HĐĐT Bệnh viện X"
CUSTOMER_TAX_ID = "0101234567"
CUSTOMER_EMAIL = "ketoan@benhvienx.test"


def _insert(doc):
	doc.flags.ignore_permissions = True
	doc.flags.ignore_mandatory = True
	doc.insert(ignore_if_duplicate=True)
	return doc


def ensure_uom(name="Cái"):
	if not frappe.db.exists("UOM", name):
		_insert(frappe.get_doc({"doctype": "UOM", "uom_name": name, "enabled": 1}))
	return name


def ensure_item():
	if frappe.db.exists("Item", ITEM_CODE):
		return ITEM_CODE
	uom = ensure_uom()
	_insert(
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": ITEM_CODE,
				"item_name": ITEM_NAME,
				"item_group": frappe.db.get_value("Item Group", {"is_group": 0}, "name") or "All Item Groups",
				"stock_uom": uom,
				"is_stock_item": 1,
				"include_item_in_manufacturing": 0,
			}
		)
	)
	return ITEM_CODE


def ensure_customer():
	if not frappe.db.exists("Customer", CUSTOMER):
		_insert(
			frappe.get_doc(
				{
					"doctype": "Customer",
					"customer_name": CUSTOMER,
					"customer_type": "Company",
					"tax_id": CUSTOMER_TAX_ID,
					"customer_group": frappe.db.get_value("Customer Group", {"is_group": 0}, "name"),
					"territory": frappe.db.get_value("Territory", {"is_group": 0}, "name"),
				}
			)
		)
	ensure_billing_address()
	return CUSTOMER


def ensure_billing_address():
	"""Đặc tả C2.3 #27: địa chỉ trên hóa đơn là địa chỉ xuất hóa đơn của khách."""
	title = f"{CUSTOMER}-Billing"
	name = f"{title}-Billing"
	if frappe.db.exists("Address", name):
		return name
	address = frappe.get_doc(
		{
			"doctype": "Address",
			"address_title": title,
			"address_type": "Billing",
			"address_line1": "Số 1 Phố Y",
			"city": "Hà Nội",
			"country": "Vietnam",
			"is_primary_address": 1,
			"phone": "0912345678",
			"email_id": CUSTOMER_EMAIL,
			"links": [{"link_doctype": "Customer", "link_name": CUSTOMER}],
		}
	)
	return _insert(address).name


def ensure_stock(qty=1000):
	"""Nhập kho để phiếu giao hàng submit được mà không cần cho phép âm kho."""
	item = ensure_item()
	entry = frappe.get_doc(
		{
			"doctype": "Stock Entry",
			"stock_entry_type": "Material Receipt",
			"company": COMPANY,
			"posting_date": nowdate(),
			"items": [
				{
					"item_code": item,
					"qty": qty,
					"t_warehouse": WAREHOUSE,
					"basic_rate": 80000,
					"uom": ensure_uom(),
					"conversion_factor": 1,
				}
			],
		}
	)
	entry.flags.ignore_permissions = True
	entry.insert()
	entry.submit()
	return entry


def output_vat_account():
	"""Tài khoản 33311 — Thuế GTGT đầu ra của hệ thống tài khoản TT99."""
	return frappe.db.get_value(
		"Account", {"company": COMPANY, "account_number": "33311", "is_group": 0}, "name"
	)


def make_delivery_note(qty=100, rate=100000, submit=True, is_return=False, vat_rate=10, **values):
	"""Phiếu giao hàng đã submit — chứng từ nguồn của hóa đơn điện tử."""
	ensure_stock(qty * 2)
	customer = ensure_customer()

	# Phiếu trả hàng phải trỏ về một phiếu giao đã submit.
	if is_return and not values.get("return_against"):
		values["return_against"] = make_delivery_note(qty=qty, rate=rate, vat_rate=vat_rate).name

	taxes = []
	if vat_rate and (account := output_vat_account()):
		taxes.append(
			{
				"charge_type": "On Net Total",
				"account_head": account,
				"rate": vat_rate,
				"description": f"Thuế GTGT {vat_rate}%",
			}
		)

	doc = frappe.get_doc(
		{
			"doctype": "Delivery Note",
			"company": COMPANY,
			"customer": customer,
			"posting_date": nowdate(),
			"currency": frappe.db.get_value("Company", COMPANY, "default_currency") or "VND",
			"conversion_rate": 1,
			"is_return": 1 if is_return else 0,
			"items": [
				{
					"item_code": ensure_item(),
					"item_name": ITEM_NAME,
					"qty": -qty if is_return else qty,
					"rate": rate,
					"uom": ensure_uom(),
					"conversion_factor": 1,
					"warehouse": WAREHOUSE,
				}
			],
			"taxes": taxes,
			**values,
		}
	)
	doc.flags.ignore_permissions = True
	doc.insert()
	if submit:
		doc.submit()
	return doc


def minimal_pdf_bytes():
	"""PDF hợp lệ tối thiểu.

	Frappe quét nội dung file PDF khi đính kèm (tìm JavaScript nhúng), nên byte
	giả không lọt được — test cần một PDF thật sự parse được.
	"""
	objects = [
		b"<< /Type /Catalog /Pages 2 0 R >>",
		b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
		b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>",
	]
	out = bytearray(b"%PDF-1.4\n")
	offsets = []
	for index, body in enumerate(objects, start=1):
		offsets.append(len(out))
		out += f"{index} 0 obj\n".encode() + body + b"\nendobj\n"

	xref_position = len(out)
	out += f"xref\n0 {len(objects) + 1}\n".encode()
	out += b"0000000000 65535 f \n"
	for offset in offsets:
		out += f"{offset:010d} 00000 n \n".encode()
	out += (
		f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
		f"startxref\n{xref_position}\n%%EOF\n"
	).encode()
	return bytes(out)

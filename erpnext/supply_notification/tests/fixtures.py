# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Dữ liệu mẫu cho bộ test thông báo chuỗi cung ứng.

Site `miyano` không sẵn Item/Customer/Supplier nào nên test phải tự dựng. Tất cả
đều get-or-create để chạy lại không nhân bản và an toàn khi một test trước đã
commit (xem ghi chú DDL trong tài liệu môi trường test).
"""

import frappe
from frappe.utils import add_days, nowdate

COMPANY = "Miyano"
WAREHOUSE = "Stores - M"
ITEM_CODE = "_TEST-TB-VT001"
CUSTOMER = "_Test TB Khach hang"
SUPPLIER = "_Test TB Nha cung cap"


def _insert(doc):
	doc.flags.ignore_permissions = True
	doc.insert(ignore_if_duplicate=True)
	return doc


def ensure_uom(name="Cái"):
	if not frappe.db.exists("UOM", name):
		_insert(frappe.get_doc({"doctype": "UOM", "uom_name": name, "enabled": 1}))
	return name


def ensure_item():
	if frappe.db.exists("Item", ITEM_CODE):
		return ITEM_CODE

	_insert(
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": ITEM_CODE,
				"item_name": "Bông băng y tế",
				"item_group": frappe.db.get_value("Item Group", {"is_group": 0}, "name"),
				"stock_uom": ensure_uom(),
				"is_stock_item": 0,
				"include_item_in_manufacturing": 0,
			}
		)
	)
	return ITEM_CODE


def ensure_customer(email=None):
	if not frappe.db.exists("Customer", CUSTOMER):
		_insert(
			frappe.get_doc(
				{
					"doctype": "Customer",
					"customer_name": CUSTOMER,
					"customer_type": "Company",
					"customer_group": frappe.db.get_value("Customer Group", {"is_group": 0}, "name"),
					"territory": frappe.db.get_value("Territory", {"is_group": 0}, "name"),
				}
			)
		)
	if email:
		frappe.db.set_value("Customer", CUSTOMER, "email_id", email)
	return CUSTOMER


def ensure_supplier(email=None):
	if not frappe.db.exists("Supplier", SUPPLIER):
		_insert(
			frappe.get_doc(
				{
					"doctype": "Supplier",
					"supplier_name": SUPPLIER,
					"supplier_group": frappe.db.get_value("Supplier Group", {"is_group": 0}, "name"),
				}
			)
		)
	if email:
		frappe.db.set_value("Supplier", SUPPLIER, "email_id", email)
	return SUPPLIER


def make_sales_order(submit=True, qty=5, rate=100000, **values):
	doc = frappe.get_doc(
		{
			"doctype": "Sales Order",
			"company": COMPANY,
			"customer": ensure_customer(),
			"transaction_date": nowdate(),
			"delivery_date": add_days(nowdate(), 7),
			"currency": frappe.get_cached_value("Company", COMPANY, "default_currency"),
			"items": [
				{
					"item_code": ensure_item(),
					"qty": qty,
					"rate": rate,
					"delivery_date": add_days(nowdate(), 7),
					"warehouse": WAREHOUSE,
				}
			],
		}
	)
	doc.update(values)
	doc.flags.ignore_permissions = True
	doc.insert()
	if submit:
		doc.submit()
	return doc


def make_material_request(request_type="Purchase", submit=True, **values):
	doc = frappe.get_doc(
		{
			"doctype": "Material Request",
			"company": COMPANY,
			"material_request_type": request_type,
			"transaction_date": nowdate(),
			"schedule_date": add_days(nowdate(), 7),
			"items": [
				{
					"item_code": ensure_item(),
					"qty": 3,
					"schedule_date": add_days(nowdate(), 7),
					"warehouse": WAREHOUSE,
				}
			],
		}
	)
	doc.update(values)
	doc.flags.ignore_permissions = True
	doc.insert()
	if submit:
		doc.submit()
	return doc


def make_purchase_invoice(submit=True, due_in_days=7, qty=2, rate=250000, **values):
	doc = frappe.get_doc(
		{
			"doctype": "Purchase Invoice",
			"company": COMPANY,
			"supplier": ensure_supplier(),
			"posting_date": nowdate(),
			"due_date": add_days(nowdate(), due_in_days),
			"currency": frappe.get_cached_value("Company", COMPANY, "default_currency"),
			"items": [
				{
					"item_code": ensure_item(),
					"qty": qty,
					"rate": rate,
				}
			],
		}
	)
	doc.update(values)
	doc.flags.ignore_permissions = True
	doc.insert()
	if submit:
		doc.submit()
	return doc


def make_sales_invoice(submit=True, due_in_days=7, qty=1, rate=500000, **values):
	doc = frappe.get_doc(
		{
			"doctype": "Sales Invoice",
			"company": COMPANY,
			"customer": ensure_customer(),
			"posting_date": nowdate(),
			"due_date": add_days(nowdate(), due_in_days),
			"currency": frappe.get_cached_value("Company", COMPANY, "default_currency"),
			"items": [
				{
					"item_code": ensure_item(),
					"qty": qty,
					"rate": rate,
				}
			],
		}
	)
	doc.update(values)
	doc.flags.ignore_permissions = True
	doc.insert()
	if submit:
		doc.submit()
	return doc

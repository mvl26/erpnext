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


def make_purchase_order(submit=True, qty=4, rate=200000, **values):
	doc = frappe.get_doc(
		{
			"doctype": "Purchase Order",
			"company": COMPANY,
			"supplier": ensure_supplier(),
			"transaction_date": nowdate(),
			"schedule_date": add_days(nowdate(), 5),
			"currency": frappe.get_cached_value("Company", COMPANY, "default_currency"),
			"items": [
				{
					"item_code": ensure_item(),
					"qty": qty,
					"rate": rate,
					"schedule_date": add_days(nowdate(), 5),
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


def build_point(**values):
	"""Điểm CHƯA lưu — dùng khi test cố tình đưa mẫu mà kiểm V2 sẽ chặn."""
	values.setdefault("_skip_insert", True)
	return make_point(**values)


def make_point(**values):
	"""Điểm thông báo tối thiểu của bộ test, theo mô hình cấu hình mới."""
	doc = frappe.new_doc("Supply Notification Point")
	doc.code = values.pop("code", f"NTF-T-{frappe.generate_hash(length=6)}")
	doc.title = values.pop("title", "Điểm thử")
	doc.reference_doctype = values.pop("reference_doctype", "Sales Order")
	doc.trigger_event = values.pop("trigger_event", "Submit")
	doc.subject_template = values.pop("subject_template", "Thử {{ doc.name }}")
	doc.send_email = values.pop("send_email", 1)
	doc.send_inapp = values.pop("send_inapp", 1)
	doc.subject_prefix = values.pop("subject_prefix", "[Thử]")

	for department in values.pop("departments", []):
		doc.append("departments", {"department": department})
	for user in values.pop("users", []):
		doc.append("users", {"user": user})
	for group in values.pop("recipient_groups", []):
		doc.append("recipient_groups", {"group": group})
	for fieldname in values.pop("user_fields", []):
		doc.append("user_fields", {"fieldname": fieldname})
	for fieldname, operator, value in values.pop("conditions", []):
		doc.append("conditions", {"fieldname": fieldname, "operator": operator, "value": value})
	for fieldname, label in values.pop("item_columns", []):
		doc.append("item_columns", {"fieldname": fieldname, "label": label})
	for row in values.pop("fact_rows", []):
		doc.append(
			"fact_rows",
			{"fieldname": row[0], "label": row[1], "only_if_previous_empty": row[2] if len(row) > 2 else 0},
		)

	skip_insert = values.pop("_skip_insert", False)
	doc.update(values)
	if not skip_insert:
		doc.insert(ignore_permissions=True)
	return doc


def make_group(name=None, users=(), departments=(), fixed_emails=""):
	doc = frappe.new_doc("Supply Notification Recipient Group")
	doc.group_name = name or f"Nhóm thử {frappe.generate_hash(length=6)}"
	for user in users:
		doc.append("users", {"user": user})
	for department in departments:
		doc.append("departments", {"department": department})
	doc.fixed_emails = fixed_emails
	doc.insert(ignore_permissions=True)
	return doc.name


def make_snippet(name=None, content="<p>Chân thư thử</p>", scope="Cả hai"):
	doc = frappe.new_doc("Supply Notification Snippet")
	doc.snippet_name = name or f"Mẫu thử {frappe.generate_hash(length=6)}"
	doc.scope = scope
	doc.content = content
	doc.insert(ignore_permissions=True)
	return doc.name


def set_settings(**values):
	"""Đổi Cài đặt thông báo trong phạm vi một test (giao dịch tự rollback)."""
	from erpnext.supply_notification import registry

	settings = frappe.get_single("Supply Notification Settings")
	settings.update(values)
	settings.flags.ignore_permissions = True
	settings.save(ignore_permissions=True)
	registry.clear_cache()
	return settings


def ensure_address(title="Kho Miyano thử", phone="0900 000 000", link=None, contact_name=None):
	"""Địa chỉ giao hàng mẫu, kèm liên hệ gắn với địa chỉ nếu cần."""
	name = f"{title}-Shipping"
	if not frappe.db.exists("Address", name):
		doc = frappe.new_doc("Address")
		doc.address_title = title
		doc.address_type = "Shipping"
		doc.address_line1 = "Số 1 đường Thử"
		doc.city = "Hà Nội"
		doc.country = frappe.db.get_single_value("System Settings", "country") or "Vietnam"
		doc.phone = phone
		if link:
			doc.append("links", {"link_doctype": link[0], "link_name": link[1]})
		doc.insert(ignore_permissions=True)
		name = doc.name

	if contact_name and not frappe.db.exists("Contact", {"address": name}):
		contact = frappe.new_doc("Contact")
		contact.first_name = contact_name
		contact.address = name
		contact.mobile_no = "0987 654 321"
		contact.insert(ignore_permissions=True)

	return name


def make_supplier(email=None) -> str:
	"""NCC riêng cho một test — tránh dùng chung khi test khẳng định *không có* email.

	`FrappeTestCase` rollback theo class, nên NCC dùng chung mang theo email và
	liên hệ do test trước đặt, và một khẳng định "NCC chưa có email" hoá ra sai.
	"""
	doc = frappe.new_doc("Supplier")
	doc.supplier_name = f"_Test NCC {frappe.generate_hash(length=8)}"
	doc.supplier_group = frappe.db.get_value("Supplier Group", {"is_group": 0}, "name")
	if email:
		doc.email_id = email
	doc.insert(ignore_permissions=True)
	return doc.name

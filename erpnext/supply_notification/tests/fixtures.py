# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Dữ liệu mẫu cho bộ test thông báo chuỗi cung ứng.

Site `miyano` không sẵn Item/Customer/Supplier nào nên test phải tự dựng. Tất cả
đều get-or-create để chạy lại không nhân bản và an toàn khi một test trước đã
commit (xem ghi chú DDL trong tài liệu môi trường test).

Công ty, kho và tài khoản mặc định lấy theo dữ liệu của site đang chạy test — không
gắn cứng tên trên `miyano` (vd. "Stores - M"), vì site local cài theo bộ tài khoản
VN có viết tắt và tên kho khác.
"""

import frappe
from frappe.utils import add_days, nowdate

from erpnext.supply_notification.setup import default_company

ITEM_CODE = "_TEST-TB-VT001"
TEST_SENDER = "thong-bao-test@example.com"
CUSTOMER = "_Test TB Khach hang"
SUPPLIER = "_Test TB Nha cung cap"


def company() -> str:
	"""Công ty mặc định của site, kèm đủ tài khoản mặc định mà PR/PI/SI cần và một tài
	khoản email gửi đi để thư thông báo vào được Email Queue."""
	name = default_company()
	if not name:
		frappe.throw("Site chưa có công ty nào — không chạy được bộ test thông báo.")
	_ensure_company_account(name, "stock_received_but_not_billed", "Stock Received But Not Billed")
	_ensure_company_account(name, "default_expense_account", "Cost of Goods Sold")
	_ensure_company_account(name, "default_income_account", "Income Account")
	ensure_outgoing_email()
	return name


def ensure_outgoing_email():
	"""Tài khoản email gửi đi mặc định, chỉ tồn tại trong giao dịch của test.

	Site local không có tài khoản gửi đi thì Email Queue hỏng ở `default_sender`. Lúc
	test, Email Account bỏ qua kiểm kết nối SMTP; thư chỉ nằm trong hàng đợi rồi bị
	rollback, không gửi ra ngoài.
	"""
	if frappe.db.exists("Email Account", {"enable_outgoing": 1, "default_outgoing": 1}):
		return
	frappe.get_doc(
		{
			"doctype": "Email Account",
			"email_account_name": "_Test Thong bao",
			"email_id": TEST_SENDER,
			"enable_outgoing": 1,
			"default_outgoing": 1,
			"smtp_server": "localhost",
			"no_smtp_authentication": 1,
		}
	).insert(ignore_permissions=True)
	_clear_email_account_cache()
	frappe.db.after_rollback.add(_clear_email_account_cache)


def _clear_email_account_cache():
	"""EmailAccount.find_outgoing nhớ tài khoản trong frappe.local suốt tiến trình."""
	for attr in ("outgoing_email_account", "incoming_email_account"):
		if hasattr(frappe.local, attr):
			delattr(frappe.local, attr)


def _ensure_company_account(company_name, fieldname, account_type):
	"""Điền tài khoản mặc định còn trống của công ty bằng tài khoản đúng loại sẵn có.

	Chỉ ghi trong giao dịch của test (rollback cuối class); sau rollback xoá cache
	Company để web server không đọc nhầm giá trị đã bị hoàn tác.
	"""
	if frappe.db.get_value("Company", company_name, fieldname):
		return
	account = frappe.db.get_value(
		"Account", {"company": company_name, "account_type": account_type, "is_group": 0}, "name"
	)
	if not account:
		frappe.throw(f"Công ty {company_name} chưa có tài khoản loại {account_type}.")
	frappe.db.set_value("Company", company_name, fieldname, account, update_modified=False)
	frappe.db.after_rollback.add(lambda: frappe.clear_document_cache("Company", company_name))


def warehouse() -> str:
	"""Kho lá của công ty: "Stores - <viết tắt>" nếu có, rồi kho mặc định trong Stock
	Settings, rồi kho lá tạo sớm nhất."""
	name = company()
	stores = f"Stores - {frappe.get_cached_value('Company', name, 'abbr')}"
	if frappe.db.exists("Warehouse", {"name": stores, "company": name, "is_group": 0}):
		return stores
	default = frappe.db.get_single_value("Stock Settings", "default_warehouse")
	if default and frappe.db.exists("Warehouse", {"name": default, "company": name, "is_group": 0}):
		return default
	found = frappe.get_all(
		"Warehouse",
		filters={"company": name, "is_group": 0, "disabled": 0},
		pluck="name",
		order_by="creation asc",
		limit=1,
	)
	if not found:
		frappe.throw(f"Công ty {name} chưa có kho nào — không chạy được bộ test thông báo.")
	return found[0]


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
			"company": company(),
			"customer": ensure_customer(),
			"transaction_date": nowdate(),
			"delivery_date": add_days(nowdate(), 7),
			"currency": frappe.get_cached_value("Company", company(), "default_currency"),
			"items": [
				{
					"item_code": ensure_item(),
					"qty": qty,
					"rate": rate,
					"delivery_date": add_days(nowdate(), 7),
					"warehouse": warehouse(),
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
			"company": company(),
			"material_request_type": request_type,
			"transaction_date": nowdate(),
			"schedule_date": add_days(nowdate(), 7),
			"items": [
				{
					"item_code": ensure_item(),
					"qty": 3,
					"schedule_date": add_days(nowdate(), 7),
					"warehouse": warehouse(),
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
			"company": company(),
			"supplier": ensure_supplier(),
			"posting_date": nowdate(),
			"due_date": add_days(nowdate(), due_in_days),
			"currency": frappe.get_cached_value("Company", company(), "default_currency"),
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
			"company": company(),
			"customer": ensure_customer(),
			"posting_date": nowdate(),
			"due_date": add_days(nowdate(), due_in_days),
			"currency": frappe.get_cached_value("Company", company(), "default_currency"),
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
			"company": company(),
			"supplier": ensure_supplier(),
			"transaction_date": nowdate(),
			"schedule_date": add_days(nowdate(), 5),
			"currency": frappe.get_cached_value("Company", company(), "default_currency"),
			"items": [
				{
					"item_code": ensure_item(),
					"qty": qty,
					"rate": rate,
					"schedule_date": add_days(nowdate(), 5),
					"warehouse": warehouse(),
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
	for fieldname in values.pop("external_email_fields", []):
		doc.append("external_email_fields", {"fieldname": fieldname})
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


def ensure_address(
	title="Kho Miyano thử", phone="0900 000 000", link=None, contact_name=None, company_address=False
):
	"""Địa chỉ giao hàng mẫu, kèm liên hệ gắn với địa chỉ nếu cần.

	`company_address`: địa chỉ của chính công ty (cờ *Is Your Company Address*).
	"""
	name = f"{title}-Shipping"
	if not frappe.db.exists("Address", name):
		doc = frappe.new_doc("Address")
		doc.address_title = title
		doc.address_type = "Shipping"
		doc.address_line1 = "Số 1 đường Thử"
		doc.city = "Hà Nội"
		doc.country = frappe.db.get_single_value("System Settings", "country") or "Vietnam"
		doc.phone = phone
		if company_address:
			doc.is_your_company_address = 1
			link = link or ("Company", company())
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

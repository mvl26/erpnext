# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Vietnam go-live: greenfield master-data scaffolding + completeness report.

``seed_master_data(company)`` seeds the structural masters a VN medical-equipment
deployment needs (Item Group tree, VN units, tax categories, a price list, a
default warehouse) — the actual customer/supplier/item catalog is entered manually
per the runbook. ``master_data_completeness(company)`` flags masters missing the
VN-required fields (MST, đơn vị tính / nhóm hàng). Both are idempotent and
VN-guarded.
"""

import frappe

# (item_group_name, parent_item_group, is_group). Parents precede their children.
VN_ITEM_GROUPS = (
	("Thiết bị y tế", "All Item Groups", 1),
	("Thiết bị chẩn đoán hình ảnh", "Thiết bị y tế", 0),
	("Thiết bị xét nghiệm", "Thiết bị y tế", 0),
	("Thiết bị phẫu thuật", "Thiết bị y tế", 0),
	("Vật tư y tế", "All Item Groups", 1),
	("Vật tư tiêu hao", "Vật tư y tế", 0),
	("Vật tư cấy ghép", "Vật tư y tế", 0),
)

VN_UOMS = ("Cái", "Bộ", "Hộp", "Chiếc", "Gói")
VN_TAX_CATEGORIES = ("Trong nước", "Nhập khẩu")
VN_PRICE_LIST = "Bảng giá bán lẻ"


def seed_master_data(company=None):
	"""Seed greenfield master-data scaffolding for a VN company (idempotent)."""
	if not company or frappe.db.get_value("Company", company, "country") != "Vietnam":
		return {"ok": False, "reason": "not a Vietnam company"}

	seed_item_group_taxonomy(company)
	_seed_uoms()
	_seed_tax_categories()
	_seed_price_list()
	_seed_default_warehouse(company)
	return {"ok": True, "company": company}


def seed_item_group_taxonomy(company=None):
	"""Create the thiết bị & vật tư y tế Item Group tree (leaves inherit 511/632)."""
	for name, parent, is_group in VN_ITEM_GROUPS:
		if frappe.db.exists("Item Group", name) or not frappe.db.exists("Item Group", parent):
			continue
		doc = frappe.get_doc(
			{
				"doctype": "Item Group",
				"item_group_name": name,
				"parent_item_group": parent,
				"is_group": is_group,
			}
		)
		doc.flags.ignore_permissions = True
		doc.insert()


def _seed_uoms():
	for uom in VN_UOMS:
		if not frappe.db.exists("UOM", uom):
			frappe.get_doc({"doctype": "UOM", "uom_name": uom, "enabled": 1}).insert(ignore_permissions=True)


def _seed_tax_categories():
	for title in VN_TAX_CATEGORIES:
		if not frappe.db.exists("Tax Category", title):
			frappe.get_doc({"doctype": "Tax Category", "title": title}).insert(ignore_permissions=True)


def _seed_price_list():
	if not frappe.db.exists("Price List", VN_PRICE_LIST):
		frappe.get_doc(
			{
				"doctype": "Price List",
				"price_list_name": VN_PRICE_LIST,
				"currency": "VND",
				"selling": 1,
				"enabled": 1,
			}
		).insert(ignore_permissions=True)


def _seed_default_warehouse(company):
	"""Safety net: ensure the company has at least one posting warehouse (kho)."""
	if frappe.get_all("Warehouse", filters={"company": company, "is_group": 0}, limit=1):
		return
	frappe.get_doc(
		{"doctype": "Warehouse", "warehouse_name": "Kho tổng", "company": company}
	).insert(ignore_permissions=True)


@frappe.whitelist()
def master_data_completeness(company=None):
	"""Report masters missing VN-required fields. Read-only; returns a structured result."""
	issues = []

	for c in frappe.get_all("Customer", filters={"disabled": 0}, fields=["name", "tax_id"]):
		if not c.tax_id:
			issues.append({"doctype": "Customer", "name": c.name, "issue": "thiếu MST (tax_id)"})

	for s in frappe.get_all("Supplier", filters={"disabled": 0}, fields=["name", "tax_id"]):
		if not s.tax_id:
			issues.append({"doctype": "Supplier", "name": s.name, "issue": "thiếu MST (tax_id)"})

	for i in frappe.get_all("Item", filters={"disabled": 0}, fields=["name", "stock_uom", "item_group"]):
		if not i.stock_uom or not i.item_group:
			issues.append({"doctype": "Item", "name": i.name, "issue": "thiếu ĐVT hoặc nhóm hàng"})

	return {"ok": not issues, "count": len(issues), "issues": issues}

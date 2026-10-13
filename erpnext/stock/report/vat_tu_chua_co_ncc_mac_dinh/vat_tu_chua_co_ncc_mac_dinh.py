# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Vật tư thuộc quy tắc sinh mã mà chưa có dòng NCC mặc định.

Đây là danh sách xử lý tay sau patch `mark_default_item_supplier`, và cũng là
chỗ theo dõi về sau: ở chế độ "Quy tắc mã vật tư", Item có nhiều NCC mà chưa
chọn mặc định sẽ bị chặn khi lưu.
"""

import frappe
from frappe import _
from frappe.utils import cint


def execute(filters=None):
	return get_columns(), get_data(frappe._dict(filters or {}))


def get_columns():
	return [
		{
			"fieldname": "item_code",
			"label": _("Mã vật tư (Item Code)"),
			"fieldtype": "Link",
			"options": "Item",
			"width": 220,
		},
		{"fieldname": "item_name", "label": _("Tên vật tư (Item Name)"), "fieldtype": "Data", "width": 280},
		{
			"fieldname": "item_group",
			"label": _("Nhóm hàng (Item Group)"),
			"fieldtype": "Link",
			"options": "Item Group",
			"width": 160,
		},
		{
			"fieldname": "brand",
			"label": _("Thương hiệu (Brand)"),
			"fieldtype": "Link",
			"options": "Brand",
			"width": 140,
		},
		{
			"fieldname": "supplier_rows",
			"label": _("Số dòng NCC (Supplier Items)"),
			"fieldtype": "Int",
			"width": 110,
		},
		{"fieldname": "reason", "label": _("Việc cần làm"), "fieldtype": "Data", "width": 300},
	]


def get_data(filters):
	item_filters = {
		"disabled": 0,
		"is_stock_item": 1,
		"is_fixed_asset": 0,
		"has_variants": 0,
		"variant_of": ("is", "not set"),
	}
	if filters.get("item_group"):
		item_filters["item_group"] = filters.item_group

	items = frappe.get_all(
		"Item",
		filters=item_filters,
		fields=["name as item_code", "item_name", "item_group", "brand"],
		order_by="name",
	)

	supplier_rows, has_default = {}, set()
	for row in frappe.get_all(
		"Item Supplier", filters={"parenttype": "Item"}, fields=["parent", "is_default"]
	):
		supplier_rows[row.parent] = supplier_rows.get(row.parent, 0) + 1
		if cint(row.is_default):
			has_default.add(row.parent)

	data = []
	for item in items:
		if item.item_code in has_default:
			continue
		item.supplier_rows = supplier_rows.get(item.item_code, 0)
		item.reason = (
			_("Nhiều NCC, chưa chọn NCC mặc định")
			if item.supplier_rows
			else _("Chưa khai NCC ở bảng Supplier Items")
		)
		data.append(item)
	return data

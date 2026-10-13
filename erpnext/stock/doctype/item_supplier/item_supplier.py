import frappe
from frappe.model.document import Document
from frappe.utils import cint


class ItemSupplier(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		is_default: DF.Check
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		supplier: DF.Link
		supplier_part_no: DF.Data | None
		supplier_part_no_key: DF.Data | None
	# end: auto-generated types

	pass


# --- NCC mặc định của vật tư ------------------------------------------------
#
# NCC mặc định của vật tư là NCC ở dòng được tích `is_default` trong bảng Supplier Items
# (tab Purchasing). Mọi luồng cần NCC mặc định đều hỏi ở đây.
#
# Cột `default_supplier` của Item Defaults không còn dùng cho vật tư: nó bị ẩn trên form
# và luôn để trống. Trường vẫn nằm trong DocType `Item Default` vì Item Group và Brand
# dùng chung DocType này cho NCC mặc định của chúng.


def get_default_supplier(item_code):
	return get_default_suppliers([item_code]).get(item_code)


def get_default_suppliers(item_codes):
	"""{mã vật tư: NCC mặc định} cho các vật tư có NCC mặc định."""
	item_codes = list({code for code in item_codes if code})
	if not item_codes:
		return {}
	return dict(
		frappe.get_all(
			"Item Supplier",
			filters={"parenttype": "Item", "parent": ("in", item_codes), "is_default": 1},
			fields=["parent", "supplier"],
			as_list=True,
		)
	)


def get_items_with_default_supplier(supplier):
	"""Các vật tư nhận `supplier` làm NCC mặc định."""
	return frappe.get_all(
		"Item Supplier",
		filters={"parenttype": "Item", "supplier": supplier, "is_default": 1},
		pluck="parent",
	)


def set_default_supplier(item_code, supplier):
	"""Đặt `supplier` làm NCC mặc định của vật tư; chưa có dòng của NCC này thì thêm."""
	item = frappe.get_doc("Item", item_code)
	_tick(item, supplier)
	item.save()
	return item.name


def take_default_supplier_from_item_defaults(doc):
	"""Gọi từ `Item.validate`: NCC mặc định ghi ở Item Defaults được chuyển sang Supplier Items.

	Người dùng không còn thấy ô đó, nhưng giá trị vẫn có thể tới từ Data Import, API,
	hoặc từ Nhóm hàng (`update_defaults_from_item_group`). Vật tư chưa tích dòng nào thì
	nhận NCC đó làm mặc định; đã tích rồi thì dòng đang tích quyết định. Xong thì ô
	được để trống, để không còn hai nơi cùng nói về NCC mặc định.
	"""
	item_defaults = doc.get("item_defaults") or []
	suppliers = [row.default_supplier for row in item_defaults if row.default_supplier]
	if not suppliers:
		return
	for row in item_defaults:
		row.default_supplier = None
	if not any(cint(row.is_default) for row in doc.get("supplier_items") or []):
		# Các công ty khai khác nhau thì lấy dòng đầu: NCC mặc định không còn theo công ty.
		_tick(doc, suppliers[0])


def _tick(item, supplier):
	row = next((row for row in item.get("supplier_items") or [] if row.supplier == supplier), None)
	if not row:
		row = item.append("supplier_items", {"supplier": supplier})
	for other in item.supplier_items:
		other.is_default = 1 if other is row else 0


def migrate_default_suppliers():
	"""Chuyển `Item Default.default_supplier` của mọi vật tư sang dòng tích mặc định, rồi để trống.

	Giá trị cũ thắng dòng đang tích nếu hai bên khác nhau: nó là thứ các luồng mua
	hàng vẫn dùng cho tới giờ, đổi đi là PO tự chuyển sang NCC khác. Riêng vật tư có
	mã do quy tắc sinh thì dòng đang tích thắng, vì mã của nó ghép từ dòng đó.

	NCC mặc định không còn theo từng công ty. Vật tư mà các công ty khai khác nhau thì
	lấy NCC của dòng đầu, và các giá trị cũ được ghi lại thành một bình luận trên vật
	tư. Trả về mã các vật tư đó.
	"""
	legacy = {}
	for row in frappe.get_all(
		"Item Default",
		filters={"parenttype": "Item", "default_supplier": ("is", "set")},
		fields=["parent", "company", "default_supplier"],
		order_by="parent, idx",
	):
		legacy.setdefault(row.parent, []).append(row)
	if not legacy:
		return []

	rows_by_item = {}
	for row in frappe.get_all(
		"Item Supplier",
		filters={"parenttype": "Item", "parent": ("in", list(legacy))},
		fields=["name", "parent", "supplier", "is_default"],
		order_by="parent, idx",
	):
		rows_by_item.setdefault(row.parent, []).append(row)
	coded_by_rule = set(
		frappe.get_all("Item", filters={"name": ("in", list(legacy)), "item_code_by_rule": 1}, pluck="name")
	)

	disagreeing = []
	for item_code, old_rows in legacy.items():
		if len({row.default_supplier for row in old_rows}) > 1:
			disagreeing.append(item_code)
			frappe.get_doc("Item", item_code).add_comment(
				"Info",
				"NCC mặc định theo từng công ty, trước khi chuyển sang bảng Supplier Items: "
				+ "; ".join(f"{row.company}: {row.default_supplier}" for row in old_rows),
			)
		supplier = old_rows[0].default_supplier
		rows = rows_by_item.get(item_code, [])
		current = next((row for row in rows if cint(row.is_default)), None)
		if current and (current.supplier == supplier or item_code in coded_by_rule):
			continue

		target = next((row for row in rows if row.supplier == supplier), None)
		if target:
			frappe.db.set_value("Item Supplier", target.name, "is_default", 1, update_modified=False)
		else:
			frappe.get_doc(
				{
					"doctype": "Item Supplier",
					"parent": item_code,
					"parenttype": "Item",
					"parentfield": "supplier_items",
					"idx": len(rows) + 1,
					"supplier": supplier,
					"is_default": 1,
				}
			).db_insert()
		if current:
			frappe.db.set_value("Item Supplier", current.name, "is_default", 0, update_modified=False)

	item_default = frappe.qb.DocType("Item Default")
	(
		frappe.qb.update(item_default)
		.set(item_default.default_supplier, None)
		.where((item_default.parenttype == "Item") & item_default.default_supplier.isnotnull())
		.run()
	)
	return disagreeing

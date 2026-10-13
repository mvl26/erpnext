from erpnext.stock.doctype.item_supplier.item_supplier import migrate_default_suppliers


def execute():
	"""NCC mặc định của vật tư chuyển từ Item Defaults sang dòng tích mặc định ở Supplier Items."""
	migrate_default_suppliers()

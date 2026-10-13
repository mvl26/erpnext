import frappe

from erpnext.stock.item_code_rule import backfill_default_supplier_rows


def execute():
	"""Đánh dấu NCC mặc định cho Item có từ trước (kế hoạch sinh mã vật tư, mục 8).

	Không đổi mã Item nào. Item không tự xác định được thì để nguyên; báo cáo
	"Vat Tu Chua Co NCC Mac Dinh" liệt kê chúng để xử lý tay.
	"""
	unresolved = backfill_default_supplier_rows()
	if unresolved:
		print(
			f"{len(unresolved)} Item chưa xác định được NCC mặc định — xem báo cáo Vat Tu Chua Co NCC Mac Dinh"
		)

# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Tra danh mục hàng hóa của ERP để tự điền một dòng hóa đơn.

Chọn hàng trên dòng thì tên hàng, đơn vị tính, đơn giá và thuế suất tự điền theo
hồ sơ Item — kế toán không phải gõ lại thứ hệ thống đã biết.

Nguyên tắc duy nhất, áp cho cả bốn trường: **chỉ trả về khóa nào tra được**.
Khóa vắng mặt nghĩa là "không biết, đừng đụng tới ô đó". Trả về rỗng hay 0 rồi
để giao diện ghi đè là xóa mất số kế toán vừa gõ, mà trên hóa đơn thì đó là làm
sai chứng từ chứ không phải tiện lợi.
"""

import frappe
from frappe.utils import flt

from erpnext.einvoice.constants import NUMERIC_TAX_RATES

# Mã thuế suất Fast tra ngược từ thuế suất số: 10.0 → "10". Chỉ có 0/5/8/10 là
# thuế suất số; các mã âm (KCT, KKKNT, KHAC…) là tính chất, không suy ra được từ
# nhóm thuế của ERP nên không bao giờ tự điền.
_RATE_TO_FAST_CODE = {rate: code for code, rate in NUMERIC_TAX_RATES.items()}


@frappe.whitelist()
def item_defaults(item_code, currency=None):
	"""Giá trị mặc định cho một dòng hóa đơn, lấy từ hồ sơ Item.

	Trả về dict chỉ chứa những khóa tra được: ``item_name``, ``uom``, ``price``,
	``tax_rate``. Mã hàng không có trong danh mục thì trả dict rỗng.
	"""
	item = frappe.db.get_value("Item", item_code, ["item_name", "stock_uom", "sales_uom"], as_dict=True)
	if not item:
		return {}

	defaults = {"item_name": item.item_name or ""}

	# Đơn vị bán mới là đơn vị ghi trên hóa đơn; chưa khai thì dùng đơn vị kho.
	if uom := (item.sales_uom or item.stock_uom):
		defaults["uom"] = uom

	if (price := _selling_price(item_code, currency)) is not None:
		defaults["price"] = price

	if tax_rate := _tax_rate(item_code):
		defaults["tax_rate"] = tax_rate

	return defaults


def _selling_price(item_code, currency):
	"""Đơn giá từ bảng giá bán mặc định. ``None`` = chưa khai giá, đừng ghi gì."""
	price_list = frappe.db.get_single_value("Selling Settings", "selling_price_list")
	if not price_list:
		return None

	filters = {"item_code": item_code, "price_list": price_list, "selling": 1}
	if currency:
		filters["currency"] = currency

	rate = flt(frappe.db.get_value("Item Price", filters, "price_list_rate"))
	return rate if rate > 0 else None


def _tax_rate(item_code):
	"""Mã thuế suất Fast suy từ nhóm thuế khai trên item.

	Chỉ trả về khi nhóm thuế cho ra **đúng một** thuế suất và thuế suất đó khớp
	một mã Fast. Nhóm thuế nhiều dòng (tách GTGT với thuế khác) không quy về một
	mã nào, và thuế suất lạ (7%) thì Fast không có mã — cả hai để kế toán tự chọn
	thay vì đoán.
	"""
	template = frappe.db.get_value(
		"Item Tax", {"parent": item_code, "parenttype": "Item"}, "item_tax_template"
	)
	if not template:
		return None

	rates = {
		flt(rate)
		for rate in frappe.get_all("Item Tax Template Detail", {"parent": template}, pluck="tax_rate")
	}
	if len(rates) != 1:
		return None

	return _RATE_TO_FAST_CODE.get(rates.pop())

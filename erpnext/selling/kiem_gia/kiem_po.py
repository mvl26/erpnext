# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Cảnh báo PO lập từ SO có giá cao hơn giá mua đã dùng ở SO (spec 6.1.3 bước 5; G22).

Quy trình Miyano là "có SO rồi mới có PO": lúc chốt SO, giá mua lấy theo BA12 D07 (báo
giá đợt, rồi HĐ nguyên tắc). Nếu khi đặt hàng NCC lại tính giá cao hơn, biên lãi đã chốt
với khách bị phá. Chỉ cảnh báo, không chặn (NCC có thể đã đổi giá; người mua vẫn phải đặt
hàng). Gắn qua hooks.py (`doc_events` của Purchase Order).

So trên cùng một mức: giá theo ĐVT kho, tiền tệ công ty, chưa gồm VAT (P8).
"""

import frappe
from frappe import _
from frappe.utils import flt

from erpnext.selling.kiem_gia.cau_hinh import cau_hinh
from erpnext.selling.kiem_gia.kiem_chung_tu import nguoi_dung_noi_bo


def kiem_po(doc, method=None):
	"""`validate` của Purchase Order."""
	if doc.doctype != "Purchase Order" or not cau_hinh().bat:
		return
	dong = [d for d in doc.get("items") if d.get("sales_order_item") and d.item_code]
	if not dong:
		return

	so_items = {
		r.name: r
		for r in frappe.get_all(
			"Sales Order Item",
			filters={"name": ("in", [d.sales_order_item for d in dong]), "docstatus": ("<", 2)},
			fields=["name", "parent", "gia_mua", "conversion_factor"],
		)
	}
	ty_gia_so = dict(
		frappe.get_all(
			"Sales Order",
			filters={"name": ("in", list({r.parent for r in so_items.values()}))},
			fields=["name", "conversion_rate"],
			as_list=True,
		)
	)

	vuot = []
	for d in dong:
		so_item = so_items.get(d.sales_order_item)
		if not so_item or not flt(so_item.gia_mua):
			continue
		precision = d.precision("rate")
		goc_kho = (
			flt(so_item.gia_mua)
			* flt(ty_gia_so.get(so_item.parent) or 1)
			/ (flt(so_item.conversion_factor) or 1)
		)
		# Giá sau chiết khấu đơn, không gồm thuế gồm trong đơn giá, tiền tệ công ty.
		po_kho = flt(d.base_net_rate) / (flt(d.conversion_factor) or 1)
		chenh = flt((po_kho - goc_kho) * (flt(d.conversion_factor) or 1), precision)
		if chenh > 0:
			vuot.append((d, so_item.parent, flt(goc_kho * (flt(d.conversion_factor) or 1), precision), chenh))

	if vuot and not frappe.flags.in_import and nguoi_dung_noi_bo():
		dong_html = "".join(
			"<li>"
			+ _("Dòng {0} - {1}: giá {2}, giá mua ở {3} là {4} (cao hơn {5})").format(
				d.idx, frappe.bold(d.item_code), flt(d.rate), so, goc, chenh
			)
			+ "</li>"
			for d, so, goc, chenh in vuot
		)
		frappe.msgprint(
			_("Giá mua cao hơn giá mua đã dùng để chốt giá bán, biên lãi với khách bị giảm:")
			+ f"<ul>{dong_html}</ul>",
			title=_("Kiểm giá mua"),
			indicator="orange",
		)
	return vuot

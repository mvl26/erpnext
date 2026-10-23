# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Đơn mua hàng gắn hợp đồng khung (spec 2026-10-23 mục 2; FR-11).

- `before_validate`: dòng chưa gắn HĐK mà có đúng một HĐK mua đã Nộp, còn hiệu lực tại ngày đơn, của
  NCC chứa mặt hàng → tự tích "Against Blanket Order". ERPNext khi đó tự cộng số đã đặt vào HĐK và
  chặn đặt vượt hạn mức (Buying Settings → Blanket Order Allowance).
- `validate`: sau đơn này số đã đặt đạt ngưỡng cảnh báo (cài đặt, mặc định 90%) thì cảnh báo.
"""

import frappe
from frappe import _
from frappe.query_builder.functions import Sum
from frappe.utils import flt

from erpnext.buying.tiep_nhan_hoa_don.cau_hinh import cai_dat


def _hdk_hieu_luc(supplier, company, ngay, items):
	bo = frappe.qb.DocType("Blanket Order")
	boi = frappe.qb.DocType("Blanket Order Item")
	ket_qua = {}
	for r in (
		frappe.qb.from_(boi)
		.join(bo)
		.on(bo.name == boi.parent)
		.select(boi.item_code, bo.name, boi.rate)
		.where(
			(bo.docstatus == 1)
			& (bo.blanket_order_type == "Purchasing")
			& (bo.supplier == supplier)
			& (bo.company == company)
			& (bo.from_date <= ngay)
			& (bo.to_date >= ngay)
			& boi.item_code.isin(list(items))
		)
		.run(as_dict=True)
	):
		ket_qua.setdefault(r.item_code, []).append(r)
	return ket_qua


def gan_hop_dong_khung(doc, method=None):
	"""`before_validate` của Purchase Order."""
	can = [d for d in doc.items if d.item_code and not d.get("blanket_order")]
	if not can or not doc.supplier or not doc.transaction_date:
		return
	hdk = _hdk_hieu_luc(doc.supplier, doc.company, doc.transaction_date, {d.item_code for d in can})
	nhieu = []
	for d in can:
		ds = hdk.get(d.item_code) or []
		if len(ds) == 1:
			d.against_blanket_order = 1
			d.blanket_order = ds[0].name
			d.blanket_order_rate = ds[0].rate
		elif len(ds) > 1:
			nhieu.append(_("Dòng {0} ({1}): {2}").format(d.idx, d.item_code, ", ".join(r.name for r in ds)))
	if nhieu:
		frappe.msgprint(
			_("Nhiều hợp đồng khung cùng hiệu lực, chưa tự gắn; chọn Hợp đồng khung trên dòng:")
			+ "<br>"
			+ "<br>".join(nhieu),
			indicator="orange",
			alert=True,
		)


def canh_bao_han_muc(doc, method=None):
	"""`validate` của Purchase Order: cảnh báo khi đạt ngưỡng hạn mức HĐK (FR-11). Vượt 100% (cộng
	dung sai) thì ERPNext đã chặn từ trước."""
	dong = {}
	for d in doc.items:
		if d.get("blanket_order"):
			dong.setdefault((d.blanket_order, d.item_code), []).append(d)
	if not dong:
		return
	nguong = cai_dat().nguong_han_muc
	poi = frappe.qb.DocType("Purchase Order Item")
	po = frappe.qb.DocType("Purchase Order")
	canh_bao = []
	for (hdk, item), cac_dong in dong.items():
		han_muc = flt(frappe.db.get_value("Blanket Order Item", {"parent": hdk, "item_code": item}, "qty"))
		if not han_muc:
			continue
		da_dat = flt(
			(
				frappe.qb.from_(poi)
				.join(po)
				.on(po.name == poi.parent)
				.select(Sum(poi.stock_qty))
				.where(
					(poi.blanket_order == hdk)
					& (poi.item_code == item)
					& (po.docstatus == 1)
					& (po.name != doc.name)
					& po.status.notin(["Stopped", "Closed"])
				)
			).run()[0][0]
		)
		sau = da_dat + sum(flt(d.stock_qty) or flt(d.qty) * (flt(d.conversion_factor) or 1) for d in cac_dong)
		phan_tram = flt(sau / han_muc * 100, 1)
		if phan_tram >= nguong:
			canh_bao.append(
				_("Dòng {0} ({1}): sau đơn này đã đặt {2}/{3} ({4}%) hạn mức hợp đồng khung {5}.").format(
					", ".join(str(d.idx) for d in cac_dong), item, flt(sau), flt(han_muc), phan_tram, hdk
				)
			)
	if canh_bao:
		frappe.msgprint("<br>".join(canh_bao), title=_("Sắp hết hạn mức hợp đồng khung"), indicator="orange")

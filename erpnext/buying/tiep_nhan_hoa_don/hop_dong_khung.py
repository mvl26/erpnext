# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Hợp đồng khung (HĐK) = Blanket Order loại Purchasing (spec 2026-10-23 mục 2; D4-1, D4-2).

- Mã dòng HĐK `[NCC]-[Số HĐK]-[Nhóm]-[STT]`: tự sinh khi có Số HĐK, sửa được trước khi Nộp, không
  trùng giữa các HĐK chưa hủy (BR-01).
- Nộp: bắt buộc đủ thông tin dòng (FR-02, áp ở dòng HĐK vì giữ mã hàng hiện tại) và ghi giá từng
  dòng vào bảng giá mua của NCC — nguồn giá "HĐ nguyên tắc" của kiểm giá Đợt 1. Hủy: xóa các giá đó.
- `da_lap_hoa_don`: lũy kế số lượng trên Hóa đơn mua đã Nộp của các dòng Đơn mua gắn HĐK (FR-23).
"""

import re

import frappe
from frappe import _
from frappe.query_builder.functions import Sum
from frappe.utils import flt

from erpnext.buying.tiep_nhan_hoa_don.chuan_hoa import bo_dau

BAT_BUOC_DONG = (
	("ten_hdk", "Tên theo hợp đồng"),
	("quy_cach", "Quy cách"),
	("hang_sx", "Hãng sản xuất"),
	("nuoc_sx", "Nước sản xuất"),
	("so_luu_hanh", "Số lưu hành / công bố"),
	("thue_suat", "Thuế suất GTGT"),
)


def la_hdk_mua(doc):
	return doc.get("blanket_order_type") == "Purchasing"


def viet_tat(doctype, name):
	ma = frappe.db.get_value(doctype, name, "ma_viet_tat") if name else None
	if ma:
		return re.sub(r"[^A-Z0-9]", "", bo_dau(ma).upper()) or "X"
	tu = re.findall(r"[A-Za-z0-9]+", bo_dau(name or ""))
	return "".join(t[0] for t in tu).upper()[:4] or "X"


def sinh_ma_dong(doc):
	if not doc.order_no:
		return
	ncc = viet_tat("Supplier", doc.supplier)
	so = re.sub(r"[^A-Z0-9]", "", bo_dau(doc.order_no).upper())
	for d in doc.items:
		if not d.get("ma_dong_hdk") and d.item_code:
			nhom = viet_tat("Item Group", frappe.get_cached_value("Item", d.item_code, "item_group"))
			d.ma_dong_hdk = f"{ncc}-{so}-{nhom}-{d.idx:03d}"


def _kiem_trung_ma(doc):
	ma = [d.ma_dong_hdk for d in doc.items if d.get("ma_dong_hdk")]
	lap = {m for m in ma if ma.count(m) > 1}
	if lap:
		frappe.throw(_("Mã dòng hợp đồng bị lặp trong hợp đồng: {0}").format(", ".join(sorted(lap))))
	da_co = frappe.get_all(
		"Blanket Order Item",
		filters={"ma_dong_hdk": ("in", ma or [""]), "parent": ("!=", doc.name), "docstatus": ("<", 2)},
		fields=["ma_dong_hdk", "parent"],
	)
	if da_co:
		frappe.throw(
			_("Mã dòng hợp đồng đã dùng: {0}").format(
				", ".join(f"{r.ma_dong_hdk} ({r.parent})" for r in da_co)
			)
		)


# --- doc_events của Blanket Order ------------------------------------------------


def khi_validate(doc, method=None):
	if not la_hdk_mua(doc):
		return
	if not doc.get("bang_gia_mua") and doc.supplier:
		pl = frappe.db.get_value("Supplier", doc.supplier, "default_price_list")
		if pl and frappe.db.get_value("Price List", pl, "buying"):
			doc.bang_gia_mua = pl
	if doc.get("bang_gia_mua") and not frappe.db.get_value("Price List", doc.bang_gia_mua, "buying"):
		frappe.throw(_("Bảng giá {0} không phải bảng giá mua.").format(frappe.bold(doc.bang_gia_mua)))
	sinh_ma_dong(doc)
	_kiem_trung_ma(doc)


def truoc_khi_nop(doc, method=None):
	if not la_hdk_mua(doc):
		return
	meta = frappe.get_meta("Blanket Order")
	thieu = [_(meta.get_label(f)) for f in ("order_no", "supplier", "bang_gia_mua") if not doc.get(f)]
	for d in doc.items:
		thieu += [_("Dòng {0}: {1}").format(d.idx, _(nhan)) for f, nhan in BAT_BUOC_DONG if not d.get(f)]
		if flt(d.rate) <= 0:
			thieu.append(_("Dòng {0}: đơn giá phải lớn hơn 0").format(d.idx))
		if flt(d.qty) <= 0:
			thieu.append(_("Dòng {0}: số lượng hợp đồng phải lớn hơn 0").format(d.idx))
	if thieu:
		frappe.throw(
			_("Hợp đồng khung thiếu thông tin:") + "<ul>" + "".join(f"<li>{t}</li>" for t in thieu) + "</ul>",
			title=_("Chưa Nộp được hợp đồng khung"),
		)


def khi_nop(doc, method=None):
	"""Ghi giá từng dòng vào bảng giá mua (D4-2). Đã có giá cùng (bảng giá, mặt hàng, NCC, từ ngày)
	thì cập nhật giá đó: hai giá cùng ngày hiệu lực làm kiểm giá Đợt 1 báo lỗi."""
	if not la_hdk_mua(doc):
		return
	for d in doc.items:
		ten = frappe.db.get_value(
			"Item Price",
			{
				"item_code": d.item_code,
				"price_list": doc.bang_gia_mua,
				"supplier": doc.supplier,
				"valid_from": doc.from_date,
			},
		)
		gia = frappe.get_doc("Item Price", ten) if ten else frappe.new_doc("Item Price")
		gia.update(
			{
				"item_code": d.item_code,
				"price_list": doc.bang_gia_mua,
				"supplier": doc.supplier,
				"uom": frappe.get_cached_value("Item", d.item_code, "stock_uom"),
				"price_list_rate": d.rate,
				"valid_from": doc.from_date,
				"valid_upto": doc.to_date,
				"hop_dong_khung": doc.name,
				"note": _("Hợp đồng khung {0}, dòng {1}").format(doc.order_no, d.ma_dong_hdk),
			}
		)
		gia.flags.ignore_permissions = True
		gia.save()


def khi_huy(doc, method=None):
	if not la_hdk_mua(doc):
		return
	for ten in frappe.get_all("Item Price", filters={"hop_dong_khung": doc.name}, pluck="name"):
		frappe.delete_doc("Item Price", ten, ignore_permissions=True, force=True)


# --- Lũy kế đã lập hóa đơn (FR-23) ------------------------------------------------


def cap_nhat_da_lap_hoa_don(po_details):
	"""Tính lại `da_lap_hoa_don` của các dòng HĐK liên quan tới các dòng Đơn mua `po_details`."""
	if not po_details:
		return
	poi = frappe.qb.DocType("Purchase Order Item")
	cap = (
		frappe.qb.from_(poi)
		.select(poi.blanket_order, poi.item_code)
		.distinct()
		.where(poi.name.isin(list(po_details)) & poi.blanket_order.isnotnull() & (poi.blanket_order != ""))
		.run()
	)
	pii = frappe.qb.DocType("Purchase Invoice Item")
	for hdk, item in cap:
		da_lap = (
			frappe.qb.from_(pii)
			.join(poi)
			.on(poi.name == pii.po_detail)
			.select(Sum(pii.stock_qty))
			.where((pii.docstatus == 1) & (poi.blanket_order == hdk) & (poi.item_code == item))
			.run()
		)[0][0]
		frappe.db.set_value(
			"Blanket Order Item", {"parent": hdk, "item_code": item}, "da_lap_hoa_don", flt(da_lap)
		)

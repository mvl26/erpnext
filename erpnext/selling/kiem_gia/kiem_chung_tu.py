# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Kiểm giá bán trên Quotation và Sales Order (thiết kế mục 6.1.4-6.1.7, bước 1.4).

Mỗi dòng được ghi lại (chỉ đọc): giá gốc, nguồn, % lãi áp dụng, giá chuẩn, chênh lệch,
trạng thái. Bước này chỉ ghi nhận và cảnh báo; chặn Submit SO là bước 1.5.

Giá gốc luôn đọc từ Item Price của bảng giá mua (P1). Supplier Quotation đi vào cùng
nguồn này khi Submit (bước 1.6), nên không cần lần theo chuỗi SO -> Quotation -> SQ.
Giá trong bảng giá chưa gồm VAT (P8): so với `net_rate` khi chứng từ có thuế gồm trong
đơn giá, ngược lại so với `rate`.
"""

import frappe
from frappe import _
from frappe.utils import cint, flt

from erpnext.selling.kiem_gia.cau_hinh import cau_hinh, ty_le_lai_nhieu
from erpnext.selling.kiem_gia.gia_goc import (
	CHUA_XAC_DINH,
	KHOP,
	so_sanh,
	tim_gia_goc_nhieu,
	tinh_gia_chuan,
)

CHUNG_TU = ("Quotation", "Sales Order")
BO_QUA = "Bỏ qua"
TRUONG_DONG = (
	"trang_thai_gia",
	"gia_goc",
	"nguon_gia_goc",
	"ty_le_lai_ap_dung",
	"gia_chuan",
	"chenh_lech",
	"ghi_chu_gia",
)


def kiem_chung_tu(doc):
	"""Gọi từ `SellingController.validate`, sau khi đã tính thuế và tổng."""
	if doc.doctype not in CHUNG_TU or not cau_hinh().bat:
		return

	dong = [d for d in doc.get("items") if d.item_code]
	if not dong:
		return

	customer = _khach(doc)
	if customer and frappe.get_cached_value("Customer", customer, "is_internal_customer"):
		for d in dong:
			_dat(d, trang_thai_gia=BO_QUA, ghi_chu_gia=_("Khách nội bộ"))
		return

	item_codes = [d.item_code for d in dong]
	gia_goc = tim_gia_goc_nhieu(item_codes, doc.transaction_date, doc.company)
	ty_le = ty_le_lai_nhieu(customer, item_codes)
	thue_gom_trong_gia = any(cint(t.get("included_in_print_rate")) for t in doc.get("taxes") or [])

	for d in dong:
		_kiem_dong(d, gia_goc[d.item_code], ty_le[d.item_code], thue_gom_trong_gia)

	_canh_bao(doc, [d for d in dong if d.trang_thai_gia not in (KHOP, BO_QUA)])


def _kiem_dong(d, goc, ty_le, thue_gom_trong_gia):
	if cint(d.get("is_free_item")):
		return _dat(d, trang_thai_gia=BO_QUA, ghi_chu_gia=_("Hàng tặng"))
	if not ty_le.kiem:
		return _dat(d, trang_thai_gia=BO_QUA, ghi_chu_gia=ty_le.nguon)
	if goc.gia_goc is None:
		return _dat(d, trang_thai_gia=CHUA_XAC_DINH, ty_le_lai_ap_dung=ty_le.ty_le_lai, ghi_chu_gia=goc.ly_do)

	precision = d.precision("rate")
	cf = flt(d.conversion_factor) or 1
	gia_chuan = tinh_gia_chuan(goc.gia_goc, cf, ty_le.ty_le_lai, precision)
	gia_ban = d.net_rate if thue_gom_trong_gia else d.rate
	chenh_lech, trang_thai = so_sanh(gia_ban, gia_chuan, precision)
	_dat(
		d,
		trang_thai_gia=trang_thai,
		gia_goc=flt(goc.gia_goc * cf, precision),
		nguon_gia_goc=goc.item_price,
		ty_le_lai_ap_dung=ty_le.ty_le_lai,
		gia_chuan=gia_chuan,
		chenh_lech=chenh_lech,
		ghi_chu_gia=_("{0}; % lãi: {1}").format(goc.ly_do, ty_le.nguon),
	)


def _dat(d, **values):
	for field in TRUONG_DONG:
		d.set(field, values.get(field))


def _khach(doc):
	if doc.doctype == "Quotation":
		return doc.party_name if doc.quotation_to == "Customer" else None
	return doc.customer


def _canh_bao(doc, lech):
	if not lech or frappe.flags.in_import or frappe.flags.in_patch:
		return
	dong = "".join(
		f"<li>{_('Dòng {0}').format(d.idx)} - {frappe.bold(d.item_code)}: {d.trang_thai_gia}"
		+ (f" ({flt(d.chenh_lech)})" if d.chenh_lech else "")
		+ "</li>"
		for d in lech
	)
	frappe.msgprint(
		_("Giá bán khác giá mua x (1 + % lãi):") + f"<ul>{dong}</ul>",
		title=_("Kiểm giá bán"),
		indicator="orange",
	)

# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Kiểm giá bán trên Quotation và Sales Order (thiết kế mục 6.1.4-6.1.7, bước 1.4).

Mỗi dòng được ghi lại (chỉ đọc): giá gốc, nguồn, % lãi áp dụng, giá chuẩn, chênh lệch,
trạng thái; có dòng lệch thì cảnh báo (bước 1.4).

Chế độ "Chặn" (bước 1.5, quyết định C3): Sales Order còn dòng lệch chỉ Submit được khi
có lý do và được người có vai trò duyệt giá lệch duyệt. Duyệt bằng nút "Duyệt giá lệch"
(người lập Submit sau), hoặc chính người duyệt Submit. Lần duyệt gắn với "dấu vân tay"
của các dòng lệch: sửa giá, số lượng ĐVT hay mặt hàng của dòng lệch thì phải duyệt lại.

Giá gốc luôn đọc từ Item Price của bảng giá mua (P1). Supplier Quotation đi vào cùng
nguồn này khi Submit (bước 1.6), nên không cần lần theo chuỗi SO -> Quotation -> SQ.
Giá trong bảng giá chưa gồm VAT (P8): so với `net_rate` khi chứng từ có thuế gồm trong
đơn giá, ngược lại so với `rate`.
"""

import hashlib
import json

import frappe
from frappe import _
from frappe.utils import cint, flt, now_datetime

from erpnext.selling.kiem_gia.cau_hinh import CHAN, cau_hinh, co_quyen_sua_ty_le_lai, ty_le_lai_nhieu
from erpnext.selling.kiem_gia.gia_goc import (
	CHUA_XAC_DINH,
	KHOP,
	so_sanh,
	tim_gia_goc_nhieu,
	tinh_gia_chuan,
)

CHUNG_TU = ("Quotation", "Sales Order")
BO_QUA = "Bỏ qua"
TRUONG_DUYET = ("nguoi_duyet_gia", "thoi_diem_duyet_gia", "ma_duyet_gia")
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

	_canh_bao(doc, dong_lech(doc))
	if doc.doctype == "Sales Order":
		_giu_hay_huy_duyet(doc)


def dong_lech(doc):
	return [d for d in doc.get("items") if d.get("trang_thai_gia") and d.trang_thai_gia not in (KHOP, BO_QUA)]


def kiem_truoc_submit(doc):
	"""Gọi từ `SalesOrder.before_submit` (sau validate, nên kết quả kiểm đã mới) và từ
	"Update Items" của SO đã Submit."""
	ch = cau_hinh()
	if doc.doctype != "Sales Order" or not ch.bat or ch.che_do != CHAN:
		return
	lech = dong_lech(doc)
	if not lech:
		return

	danh_sach = ", ".join(f"{d.idx} ({d.item_code}: {d.trang_thai_gia})" for d in lech)
	if not (doc.get("ly_do_lech_gia") or "").strip():
		frappe.throw(
			_("Dòng {0} lệch giá chuẩn. Nhập Lý do lệch giá trước khi Submit.").format(danh_sach),
			title=_("Kiểm giá bán"),
		)
	if doc.get("ma_duyet_gia") and doc.ma_duyet_gia == dau_van_tay(lech):
		return
	if co_quyen_duyet_gia():
		_ghi_duyet(doc, lech)
		return
	frappe.throw(
		_("Dòng {0} lệch giá chuẩn và chưa được duyệt. Người có vai trò {1} cần bấm Duyệt giá lệch.").format(
			danh_sach, frappe.bold(_vai_tro_duyet())
		),
		title=_("Kiểm giá bán"),
	)


@frappe.whitelist()
def co_quyen_duyet_gia():
	"""Vai trò duyệt giá lệch, hoặc người được sửa % lãi (C3)."""
	vai_tro = cau_hinh().vai_tro_duyet_gia_lech
	return bool(vai_tro and vai_tro in frappe.get_roles()) or co_quyen_sua_ty_le_lai()


@frappe.whitelist()
def duyet_gia_lech(sales_order):
	"""Nút "Duyệt giá lệch" trên Sales Order nháp."""
	doc = frappe.get_doc("Sales Order", sales_order)
	doc.check_permission("read")
	if doc.docstatus != 0:
		frappe.throw(_("Chỉ duyệt được Sales Order nháp"))
	if not cau_hinh().bat:
		frappe.throw(_("Kiểm giá bán đang tắt"))
	if not co_quyen_duyet_gia():
		frappe.throw(
			_("Chỉ vai trò {0} được duyệt giá lệch").format(frappe.bold(_vai_tro_duyet())),
			frappe.PermissionError,
		)
	if not (doc.get("ly_do_lech_gia") or "").strip():
		frappe.throw(_("Người lập cần nhập và lưu Lý do lệch giá trước khi duyệt"))

	doc.flags.dang_duyet_gia = True
	doc.save(ignore_permissions=True)
	if not doc.ma_duyet_gia:
		frappe.msgprint(_("Không có dòng lệch giá cần duyệt"))
	return {f: doc.get(f) for f in TRUONG_DUYET}


def dau_van_tay(lech):
	data = sorted(
		(d.item_code, d.uom, flt(d.qty), flt(d.rate), flt(d.gia_chuan), d.trang_thai_gia) for d in lech
	)
	return hashlib.sha1(json.dumps(data, default=str).encode()).hexdigest()


def _giu_hay_huy_duyet(doc):
	lech = dong_lech(doc)
	if doc.flags.dang_duyet_gia:
		return _ghi_duyet(doc, lech) if lech else _xoa_duyet(doc)
	if doc.get("ma_duyet_gia") and (not lech or doc.ma_duyet_gia != dau_van_tay(lech)):
		_xoa_duyet(doc)
		if lech and not frappe.flags.in_import:
			frappe.msgprint(
				_("Dòng lệch giá đã thay đổi sau khi duyệt. Cần duyệt lại."),
				title=_("Kiểm giá bán"),
				indicator="orange",
			)


def _ghi_duyet(doc, lech):
	doc.nguoi_duyet_gia = frappe.session.user
	doc.thoi_diem_duyet_gia = now_datetime()
	doc.ma_duyet_gia = dau_van_tay(lech)


def _xoa_duyet(doc):
	for f in TRUONG_DUYET:
		doc.set(f, None)


def _vai_tro_duyet():
	ch = cau_hinh()
	return ch.vai_tro_duyet_gia_lech or ch.vai_tro_sua_ty_le_lai or "System Manager"


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

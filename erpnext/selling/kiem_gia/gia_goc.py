# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Giá gốc và giá chuẩn của một dòng bán.

Giá gốc là giá NCC báo cho Miyano, đọc từ Item Price của các bảng giá mua có hiệu
lực tại ngày chứng từ. Giá chuẩn = giá gốc x (1 + % lãi). Thiết kế:
`docs/superpowers/specs/2026-10-21-kiem-gia-ban-bao-gia-doi-soat-design.md`, mục 6.1.3-6.1.4.

Quy ước:
- Mọi giá đều CHƯA gồm VAT (quyết định P8).
- Giá gốc luôn quy về ĐVT kho; khi so với một dòng bán thì nhân hệ số quy đổi của dòng.
- Làm tròn theo độ chính xác của trường đơn giá đang so (production đặt 4 chữ số cho
  `rate`, site test có thể 2) — không ghi cứng số chữ số.
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate

from erpnext.stock.doctype.item_supplier.item_supplier import get_default_suppliers

# Trạng thái giá gốc
CO_GIA_GOC = "Có giá gốc"
KHONG_CO_GIA_MUA = "Không có giá mua"
NHIEU_GIA = "Nhiều giá cùng ngày"

# Trạng thái so sánh
KHOP = "Khớp"
THAP_HON = "Thấp hơn"
CAO_HON = "Cao hơn"
CHUA_XAC_DINH = "Chưa xác định giá gốc"


def tim_gia_goc(item_code, ngay, company=None):
	"""Giá gốc (ĐVT kho) của một mặt hàng tại `ngay`. Xem `tim_gia_goc_nhieu`."""
	return tim_gia_goc_nhieu([item_code], ngay, company)[item_code]


def tim_gia_goc_nhieu(item_codes, ngay, company=None):
	"""{mã hàng: kết quả} cho nhiều mặt hàng, một lượt truy vấn.

	Kết quả là `frappe._dict` gồm `trang_thai`, `gia_goc` (ĐVT kho, None nếu không xác
	định), `item_price`, `price_list`, `supplier`, `valid_from`, `ly_do`.

	Thứ tự chọn (6.1.3 bước 2):
	1. giá của NCC mặc định (dòng `is_default` ở Supplier Items) nếu NCC đó có giá hiệu lực;
	2. ngược lại, dòng có `valid_from` mới nhất trong mọi bảng giá mua.
	Nhiều dòng cùng `valid_from` mới nhất mà giá khác nhau → không tự chọn.
	"""
	item_codes = list({code for code in item_codes if code})
	if not item_codes:
		return {}

	ngay = getdate(ngay)
	currency = _company_currency(company)
	rows = _gia_mua_hieu_luc(item_codes, ngay, currency)
	he_so = he_so_quy_doi(item_codes, {r.uom for r in rows})
	ncc_mac_dinh = get_default_suppliers(item_codes)

	theo_hang = {}
	for r in rows:
		cf = 1 if r.uom == r.stock_uom else he_so.get((r.item_code, r.uom))
		if not cf:
			# Giá theo một ĐVT mà mặt hàng không khai hệ số: không quy về ĐVT kho được.
			continue
		r.gia_kho = flt(r.price_list_rate) / flt(cf)
		theo_hang.setdefault(r.item_code, []).append(r)

	return {code: _chon(theo_hang.get(code, []), ncc_mac_dinh.get(code)) for code in item_codes}


def tinh_gia_chuan(gia_goc_kho, conversion_factor, ty_le_lai, precision):
	"""Giá chuẩn trên ĐVT của dòng: giá gốc x hệ số quy đổi x (1 + % lãi), làm tròn theo trường."""
	return flt(flt(gia_goc_kho) * flt(conversion_factor or 1) * (1 + flt(ty_le_lai) / 100), precision)


def so_sanh(gia_ban, gia_chuan, precision):
	"""(chênh lệch, trạng thái). Chênh lệch = giá bán - giá chuẩn; bằng 0 sau làm tròn là khớp."""
	chenh_lech = flt(flt(gia_ban) - flt(gia_chuan), precision)
	if chenh_lech == 0:
		return chenh_lech, KHOP
	return chenh_lech, THAP_HON if chenh_lech < 0 else CAO_HON


def _chon(rows, ncc):
	if not rows:
		return _ket_qua(KHONG_CO_GIA_MUA, ly_do=_("Không có giá mua hiệu lực tại ngày chứng từ"))

	cua_ncc = [r for r in rows if ncc and r.supplier == ncc]
	ung_vien = cua_ncc or rows
	moi_nhat = max(r.valid_from for r in ung_vien)
	top = [r for r in ung_vien if r.valid_from == moi_nhat]

	if len({flt(r.gia_kho, 9) for r in top}) > 1:
		chi_tiet = ", ".join(f"{r.price_list}: {flt(r.price_list_rate)}/{r.uom}" for r in top)
		return _ket_qua(
			NHIEU_GIA, ly_do=_("Nhiều giá mua cùng ngày hiệu lực {0}: {1}").format(moi_nhat, chi_tiet)
		)

	r = top[0]
	ly_do = _("NCC mặc định {0}").format(ncc) if cua_ncc else _("Giá mua có ngày hiệu lực mới nhất")
	return _ket_qua(
		CO_GIA_GOC,
		gia_goc=r.gia_kho,
		item_price=r.name,
		price_list=r.price_list,
		supplier=r.supplier,
		valid_from=r.valid_from,
		ly_do=ly_do,
	)


def _ket_qua(trang_thai, **fields):
	return frappe._dict(
		{
			"trang_thai": trang_thai,
			"gia_goc": None,
			"item_price": None,
			"price_list": None,
			"supplier": None,
			"valid_from": None,
			"ly_do": None,
			**fields,
		}
	)


def _gia_mua_hieu_luc(item_codes, ngay, currency):
	"""Dòng Item Price mua đang hiệu lực, cùng tiền tệ công ty, của bảng giá đang bật.

	Bỏ dòng gắn lô (`batch_no`): đó là giá riêng của một lô, không phải giá NCC báo.
	`valid_from` trống được hiểu như ERPNext: áp từ 2000-01-01.
	"""
	ip = frappe.qb.DocType("Item Price")
	pl = frappe.qb.DocType("Price List")
	item = frappe.qb.DocType("Item")
	valid_from = frappe.query_builder.functions.IfNull(ip.valid_from, "2000-01-01")
	rows = (
		frappe.qb.from_(ip)
		.join(pl)
		.on(pl.name == ip.price_list)
		.join(item)
		.on(item.name == ip.item_code)
		.select(
			ip.name,
			ip.item_code,
			ip.price_list,
			ip.supplier,
			ip.uom,
			ip.price_list_rate,
			valid_from.as_("valid_from"),
			item.stock_uom,
		)
		.where(
			(ip.item_code.isin(item_codes))
			& (ip.buying == 1)
			& (pl.enabled == 1)
			& (ip.currency == currency)
			& (valid_from <= ngay)
			& (ip.valid_upto.isnull() | (ip.valid_upto >= ngay))
			& (frappe.query_builder.functions.IfNull(ip.batch_no, "") == "")
		)
		.run(as_dict=True)
	)
	for r in rows:
		r.valid_from = getdate(r.valid_from)
	return rows


def he_so_quy_doi(item_codes, uoms):
	if not uoms:
		return {}
	return {
		(r.parent, r.uom): flt(r.conversion_factor)
		for r in frappe.get_all(
			"UOM Conversion Detail",
			filters={"parenttype": "Item", "parent": ("in", item_codes), "uom": ("in", list(uoms))},
			fields=["parent", "uom", "conversion_factor"],
		)
	}


def _company_currency(company):
	company = (
		company
		or frappe.defaults.get_user_default("Company")
		or frappe.db.get_single_value("Global Defaults", "default_company")
	)
	return frappe.get_cached_value("Company", company, "default_currency") if company else "VND"

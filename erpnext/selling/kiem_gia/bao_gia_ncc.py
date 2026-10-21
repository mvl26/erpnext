# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Supplier Quotation -> bảng giá mua (thiết kế mục 6.1.3, 6.1.7; bước 1.6, tình huống G23).

Khi báo giá NCC được Submit, mỗi mặt hàng được ghi thành một dòng Item Price MỚI trong
bảng giá mua của NCC, `valid_from` = ngày báo giá, `supplier` = NCC, `note` = "Báo giá NCC: <số>"
(không dùng `reference`: Item Price tự điền nó bằng tên NCC/khách khi lưu). Dòng cũ giữ nguyên: bộ tìm giá gốc tự chọn dòng có `valid_from` mới nhất. Nhờ vậy giá
nhập tay hay nhập tự động (YC6) đều về đúng một nơi mà bộ kiểm giá đọc.

Quy ước:
- Bảng giá: bảng giá mặc định của NCC (Supplier > Price List) nếu là bảng giá mua đang
  bật; không có thì bảng giá mua trên báo giá.
- Giá ghi theo ĐVT kho, CHƯA gồm VAT (P8): dùng `net_rate` khi báo giá có thuế gồm trong
  đơn giá, ngược lại `rate`; chia hệ số quy đổi của dòng.
- Đã có dòng cùng ngày hiệu lực: cùng giá thì bỏ qua; khác giá thì sửa dòng đó nếu chưa
  Sales Order nào dùng làm giá gốc, đã dùng thì giữ nguyên và cảnh báo.
- Hủy báo giá: xóa các dòng nó tạo mà chưa Sales Order nào dùng.
"""

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate

import erpnext


def ghi_gia_mua(doc):
	"""Gọi từ `SupplierQuotation.on_submit`."""
	price_list = _bang_gia_mua(doc)
	if not price_list:
		_bao(_("Không ghi giá vào bảng giá mua: NCC {0} chưa có bảng giá mua.").format(doc.supplier))
		return

	pl_currency = frappe.get_cached_value("Price List", price_list, "currency")
	dung_gia_quy_doi = pl_currency != doc.currency
	if dung_gia_quy_doi and pl_currency != erpnext.get_company_currency(doc.company):
		_bao(
			_("Không ghi giá: bảng giá {0} ({1}) khác tiền tệ báo giá ({2}).").format(
				price_list, pl_currency, doc.currency
			)
		)
		return

	thue_gom = any(cint(t.get("included_in_print_rate")) for t in doc.get("taxes") or [])
	gia, bo_qua = _gia_theo_mat_hang(doc, thue_gom, dung_gia_quy_doi)
	ngay = getdate(doc.transaction_date)

	moi, sua, giu = [], [], []
	for item_code, (rate, stock_uom) in gia.items():
		ket_qua = _ghi_mot_dong(doc, price_list, pl_currency, item_code, stock_uom, rate, ngay)
		{"moi": moi, "sua": sua, "giu": giu}.get(ket_qua, []).append(item_code)

	thong_bao = []
	if moi or sua:
		thong_bao.append(
			_("Đã ghi {0} giá vào bảng giá mua {1}, hiệu lực từ {2}.").format(
				len(moi) + len(sua), frappe.bold(price_list), frappe.format(ngay, "Date")
			)
		)
	if giu:
		thong_bao.append(
			_("Giữ nguyên giá cùng ngày đã dùng cho Sales Order: {0}. Sửa tay nếu cần.").format(
				", ".join(giu)
			)
		)
	if bo_qua:
		thong_bao.append(_("Bỏ qua (nhiều giá khác nhau trong cùng báo giá): {0}").format(", ".join(bo_qua)))
	if thong_bao:
		_bao("<br>".join(thong_bao), indicator="orange" if giu or bo_qua else "green")


def xoa_gia_mua(doc):
	"""Gọi từ `SupplierQuotation.on_cancel`."""
	dong = frappe.get_all("Item Price", filters={"note": ghi_chu(doc.name), "buying": 1}, pluck="name")
	da_dung = _da_dung_cho_so(dong)
	for name in dong:
		if name not in da_dung:
			frappe.delete_doc("Item Price", name, ignore_permissions=True)
	if da_dung:
		_bao(
			_("Giữ lại {0} dòng giá mua đã dùng cho Sales Order: {1}").format(
				len(da_dung), ", ".join(sorted(da_dung))
			),
			indicator="orange",
		)


def ghi_chu(supplier_quotation):
	"""Dấu nối dòng Item Price với báo giá đã tạo ra nó (so khớp nguyên văn khi hủy)."""
	return f"Báo giá NCC: {supplier_quotation}"


def _bang_gia_mua(doc):
	for name in (
		frappe.get_cached_value("Supplier", doc.supplier, "default_price_list"),
		doc.buying_price_list,
	):
		if name and frappe.db.get_value("Price List", {"name": name, "buying": 1, "enabled": 1}):
			return name


def _gia_theo_mat_hang(doc, thue_gom, dung_gia_quy_doi):
	"""{mã hàng: (giá/ĐVT kho, ĐVT kho)}; mặt hàng có nhiều giá khác nhau thì bỏ qua."""
	gia, bo_qua = {}, []
	for d in doc.get("items"):
		if not d.item_code or cint(d.get("is_free_item")):
			continue
		if dung_gia_quy_doi:
			rate = d.base_net_rate if thue_gom else d.base_rate
		else:
			rate = d.net_rate if thue_gom else d.rate
		if not flt(rate):
			continue
		rate = flt(rate) / (flt(d.conversion_factor) or 1)
		if d.item_code in gia and flt(gia[d.item_code][0], 6) != flt(rate, 6):
			bo_qua.append(d.item_code)
		gia.setdefault(d.item_code, (rate, d.stock_uom))
	for code in set(bo_qua):
		gia.pop(code, None)
	return gia, sorted(set(bo_qua))


def _ghi_mot_dong(doc, price_list, currency, item_code, uom, rate, ngay):
	precision = frappe.get_precision("Item Price", "price_list_rate")
	rate = flt(rate, precision)
	cu = frappe.db.get_value(
		"Item Price",
		{
			"price_list": price_list,
			"item_code": item_code,
			"uom": uom,
			"supplier": doc.supplier,
			"valid_from": ngay,
			"customer": ("is", "not set"),
			"batch_no": ("is", "not set"),
		},
		["name", "price_list_rate"],
		as_dict=True,
	)
	if cu:
		if flt(cu.price_list_rate, precision) == rate:
			return None
		if _da_dung_cho_so([cu.name]):
			return "giu"
		ip = frappe.get_doc("Item Price", cu.name)
		ip.price_list_rate = rate
		ip.note = ghi_chu(doc.name)
		ip.save(ignore_permissions=True)
		return "sua"

	frappe.get_doc(
		{
			"doctype": "Item Price",
			"price_list": price_list,
			"item_code": item_code,
			"uom": uom,
			"supplier": doc.supplier,
			"currency": currency,
			"price_list_rate": rate,
			"valid_from": ngay,
			"note": ghi_chu(doc.name),
		}
	).insert(ignore_permissions=True)
	return "moi"


def _da_dung_cho_so(item_prices):
	if not item_prices:
		return set()
	return set(
		frappe.get_all(
			"Sales Order Item",
			filters={"nguon_gia_goc": ("in", item_prices), "docstatus": 1},
			pluck="nguon_gia_goc",
			distinct=True,
		)
	)


def _bao(message, indicator="orange"):
	if not frappe.flags.in_import:
		frappe.msgprint(message, title=_("Bảng giá mua"), indicator=indicator)

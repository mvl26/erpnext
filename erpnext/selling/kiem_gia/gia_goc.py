# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Giá mua và giá đề xuất của một dòng bán (BA12 R02, R03, D07, D08).

Giá mua của một (mặt hàng, NCC) tại ngày chứng từ, theo D07:
1. **Báo giá đợt** — Supplier Quotation đã Submit của NCC đó, còn hiệu lực
   (ngày báo giá <= ngày chứng từ <= `valid_till`; `valid_till` trống là còn hiệu lực),
   lấy báo giá mới nhất.
2. **HĐ nguyên tắc** — nếu không có báo giá đợt: Item Price của bảng giá mua (bảng
   "Mua - <NCC>") có `supplier` là NCC đó, hiệu lực tại ngày chứng từ, `valid_from` mới nhất.
3. Không có cả hai: "Chưa có giá mua" (R08).

NCC (D08) là NCC dự kiến trên dòng; để trống thì lấy NCC mặc định của mặt hàng.

Quy ước:
- Mọi giá CHƯA gồm VAT: báo giá đợt dùng `base_net_rate` (đã bỏ thuế gồm trong đơn giá và
  chiết khấu đơn); bảng giá mua được nhập chưa VAT (P8).
- Giá mua quy về ĐVT kho, tiền tệ công ty; khi so với dòng bán thì nhân hệ số quy đổi của
  dòng và đổi sang tiền tệ chứng từ.
- Giá đề xuất = giá mua x hệ số, **làm tròn đến đồng** (R03), nửa đồng làm tròn lên,
  áp cho mọi đơn vị tiền. Không có dung sai (D04): giá bán làm tròn đến đồng khác giá đề
  xuất là lệch.
"""

from decimal import ROUND_HALF_UP, Decimal

import frappe
from frappe import _
from frappe.utils import flt, getdate

from erpnext.stock.doctype.item_supplier.item_supplier import get_default_suppliers

# Trạng thái giá mua
CO_GIA_MUA = "Có giá mua"
CHUA_CO_GIA_MUA = "Chưa có giá mua"

# Nguồn giá mua (D07)
BAO_GIA_DOT = "Báo giá đợt"
HD_NGUYEN_TAC = "HĐ nguyên tắc"

# Trạng thái so sánh
KHOP = "Khớp"
THAP_HON = "Thấp hơn"
CAO_HON = "Cao hơn"


def ncc_mac_dinh(item_codes):
	return get_default_suppliers(item_codes)


def tim_gia_mua(item_code, supplier, ngay, company=None):
	"""Giá mua (ĐVT kho) của một mặt hàng từ một NCC. Xem `tim_gia_mua_nhieu`."""
	return tim_gia_mua_nhieu([(item_code, supplier)], ngay, company)[(item_code, supplier)]


def tim_gia_mua_nhieu(cap, ngay, company=None):
	"""{(mã hàng, NCC): kết quả} cho nhiều cặp, mỗi nguồn một lượt truy vấn.

	Kết quả là `frappe._dict`: `trang_thai`, `gia_kho` (ĐVT kho, tiền tệ công ty; None nếu
	chưa có), `nguon` (Báo giá đợt / HĐ nguyên tắc), `chung_tu`, `ngay`, `ly_do`.
	"""
	cap = list({(i, s) for i, s in cap if i})
	if not cap:
		return {}
	ngay = getdate(ngay)
	company = _company(company)
	co_ncc = [(i, s) for i, s in cap if s]
	bao_gia = _bao_gia_dot(co_ncc, ngay, company)
	hop_dong = _gia_hd_nguyen_tac([(i, s) for i, s in co_ncc if (i, s) not in bao_gia], ngay, company)

	kq = {}
	for i, s in cap:
		if not s:
			kq[(i, s)] = _ket_qua(
				CHUA_CO_GIA_MUA, ly_do=_("Mặt hàng chưa có NCC mặc định, dòng chưa chọn NCC dự kiến")
			)
		else:
			kq[(i, s)] = (
				bao_gia.get((i, s))
				or hop_dong.get((i, s))
				or _ket_qua(
					CHUA_CO_GIA_MUA,
					ly_do=_(
						"NCC {0} không có báo giá đợt còn hiệu lực, cũng không có giá HĐ nguyên tắc tại ngày chứng từ"
					).format(s),
				)
			)
	return kq


def lam_tron_dong(so):
	"""Làm tròn đến đồng, nửa đồng làm tròn lên (R03: 124.691,57 -> 124.692)."""
	return float(Decimal(str(flt(so, 6))).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def tinh_gia_de_xuat(gia_mua_dong, he_so):
	"""R03: giá mua (ĐVT và tiền tệ của dòng) x hệ số, làm tròn đến đồng."""
	return lam_tron_dong(flt(gia_mua_dong) * flt(he_so))


def so_sanh(gia_ban, gia_de_xuat):
	"""(chênh lệch, trạng thái). Chênh = giá bán làm tròn đến đồng - giá đề xuất (D04)."""
	chenh_lech = lam_tron_dong(gia_ban) - lam_tron_dong(gia_de_xuat)
	if chenh_lech == 0:
		return 0.0, KHOP
	return chenh_lech, THAP_HON if chenh_lech < 0 else CAO_HON


def _bao_gia_dot(cap, ngay, company):
	if not cap:
		return {}
	rows = frappe.db.sql(
		"""
		select sqi.item_code, sq.supplier, sq.name, sq.transaction_date, sq.creation,
			sqi.base_net_rate, sqi.conversion_factor
		from `tabSupplier Quotation` sq
		join `tabSupplier Quotation Item` sqi on sqi.parent = sq.name
		where sq.docstatus = 1 and sq.status != 'Stopped' and sq.company = %(company)s
			and sqi.item_code in %(items)s and sq.supplier in %(suppliers)s
			and sq.transaction_date <= %(ngay)s
			and (sq.valid_till is null or sq.valid_till >= %(ngay)s)
		order by sq.transaction_date desc, sq.creation desc, sqi.idx
		""",
		{
			"company": company,
			"items": tuple({i for i, _s in cap}),
			"suppliers": tuple({s for _i, s in cap}),
			"ngay": ngay,
		},
		as_dict=True,
	)
	can = set(cap)
	theo_cap = {}
	for r in rows:
		key = (r.item_code, r.supplier)
		if key not in can:
			continue
		moi_nhat = theo_cap.setdefault(key, [])
		if moi_nhat and moi_nhat[0].name != r.name:
			continue  # chỉ xét báo giá mới nhất
		r.gia_kho = flt(r.base_net_rate) / (flt(r.conversion_factor) or 1)
		moi_nhat.append(r)

	kq = {}
	for key, top in theo_cap.items():
		r = top[0]
		if len({flt(x.gia_kho, 6) for x in top}) > 1:
			kq[key] = _ket_qua(
				CHUA_CO_GIA_MUA,
				ly_do=_("Báo giá {0} có nhiều giá khác nhau cho {1}").format(r.name, key[0]),
			)
			continue
		kq[key] = _ket_qua(
			CO_GIA_MUA,
			gia_kho=r.gia_kho,
			nguon=BAO_GIA_DOT,
			chung_tu=r.name,
			ngay=getdate(r.transaction_date),
			ly_do=_("Báo giá đợt {0} ngày {1}").format(r.name, frappe.format(r.transaction_date, "Date")),
		)
	return kq


def _gia_hd_nguyen_tac(cap, ngay, company):
	"""Item Price mua của NCC (bảng giá "Mua - <NCC>"), hiệu lực tại `ngay`.

	Bỏ dòng gắn lô (`batch_no`): đó là giá riêng của một lô. `valid_from` trống được hiểu như
	ERPNext: áp từ 2000-01-01. Nhiều dòng cùng `valid_from` mới nhất mà giá khác nhau: không
	tự chọn.
	"""
	if not cap:
		return {}
	ip = frappe.qb.DocType("Item Price")
	pl = frappe.qb.DocType("Price List")
	item = frappe.qb.DocType("Item")
	IfNull = frappe.query_builder.functions.IfNull
	valid_from = IfNull(ip.valid_from, "2000-01-01")
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
			(ip.item_code.isin(list({i for i, _s in cap})))
			& (ip.supplier.isin(list({s for _i, s in cap})))
			& (ip.buying == 1)
			& (pl.enabled == 1)
			& (ip.currency == _company_currency(company))
			& (valid_from <= ngay)
			& (ip.valid_upto.isnull() | (ip.valid_upto >= ngay))
			& (IfNull(ip.batch_no, "") == "")
		)
		.run(as_dict=True)
	)
	he_so = he_so_quy_doi(list({r.item_code for r in rows}), {r.uom for r in rows})
	can = set(cap)
	theo_cap, sai_dvt = {}, {}
	for r in rows:
		key = (r.item_code, r.supplier)
		if key not in can:
			continue
		cf = 1 if r.uom == r.stock_uom else he_so.get((r.item_code, r.uom))
		if not cf:
			sai_dvt.setdefault(key, set()).add(r.uom)
			continue
		r.valid_from = getdate(r.valid_from)
		r.gia_kho = flt(r.price_list_rate) / flt(cf)
		theo_cap.setdefault(key, []).append(r)

	kq = {}
	for key in can:
		rows_cap = theo_cap.get(key)
		if not rows_cap:
			if sai_dvt.get(key):
				kq[key] = _ket_qua(
					CHUA_CO_GIA_MUA,
					ly_do=_("Giá HĐ nguyên tắc theo ĐVT {0} nhưng mặt hàng chưa khai hệ số quy đổi").format(
						", ".join(sorted(sai_dvt[key]))
					),
				)
			continue
		moi_nhat = max(r.valid_from for r in rows_cap)
		top = [r for r in rows_cap if r.valid_from == moi_nhat]
		if len({flt(r.gia_kho, 6) for r in top}) > 1:
			chi_tiet = ", ".join(f"{r.price_list}: {flt(r.price_list_rate)}/{r.uom}" for r in top)
			kq[key] = _ket_qua(
				CHUA_CO_GIA_MUA,
				ly_do=_("Nhiều giá HĐ nguyên tắc cùng ngày hiệu lực {0}: {1}").format(moi_nhat, chi_tiet),
			)
			continue
		r = top[0]
		kq[key] = _ket_qua(
			CO_GIA_MUA,
			gia_kho=r.gia_kho,
			nguon=HD_NGUYEN_TAC,
			chung_tu=r.name,
			ngay=r.valid_from,
			ly_do=_("HĐ nguyên tắc: {0} (dòng {1}) từ {2}").format(
				r.price_list, r.name, frappe.format(r.valid_from, "Date")
			),
		)
	return kq


def _ket_qua(trang_thai, **fields):
	return frappe._dict(
		{
			"trang_thai": trang_thai,
			"gia_kho": None,
			"nguon": None,
			"chung_tu": None,
			"ngay": None,
			"ly_do": None,
			**fields,
		}
	)


def he_so_quy_doi(item_codes, uoms):
	if not uoms or not item_codes:
		return {}
	return {
		(r.parent, r.uom): flt(r.conversion_factor)
		for r in frappe.get_all(
			"UOM Conversion Detail",
			filters={"parenttype": "Item", "parent": ("in", item_codes), "uom": ("in", list(uoms))},
			fields=["parent", "uom", "conversion_factor"],
		)
	}


def _company(company):
	return (
		company
		or frappe.defaults.get_user_default("Company")
		or frappe.db.get_single_value("Global Defaults", "default_company")
	)


def _company_currency(company):
	return frappe.get_cached_value("Company", company, "default_currency") if company else "VND"

# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Đối chiếu mua vào - bán ra theo khách hàng (spec `2026-10-23-doi-chieu-mua-vao-ban-ra-design.md`).

Mỗi dòng hàng bán cho khách trong kỳ đặt cạnh dòng hoá đơn mua của NCC đã cấp
chính hàng đó, ghép theo đơn hàng: dòng SI → dòng SO (`so_detail`) → dòng PO lập
từ SO (`sales_order_item`) → dòng PI của PO (`po_detail`). Dòng bán chưa ghép được
ghép tiếp theo mã hàng với dòng PI thiếu liên kết (PO lập tay, HĐ bán không qua SO);
còn thiếu thì vẫn hiện, bên NCC để trống. Chỉ đọc chứng từ đã submit; không ghi gì.

Kỳ lọc theo ngày hoá đơn đầu ra; hoá đơn mua ghép được thì hiện dù ngày ở kỳ khác
(ghi chú "ngoài kỳ"). Số HĐ là số thật: HĐĐT bên bán, `bill_no` bên mua; chưa có
thì để trống và ghi chú, mã chứng từ ở cột "Chứng từ bán / mua".
"""

import calendar
import json

import frappe
from frappe import _
from frappe.utils import flt, formatdate, getdate, nowdate

from erpnext.accounts.report.doi_chieu_mua_vao_ban_ra.phan_bo import (
	TY_LE_HOP_DONG,
	chia_thue,
	chon_tai_khoan_vat,
	danh_dau_nhom,
	danh_gia,
	ghep,
	hop_trang_thai,
	tong_hop,
)
from erpnext.einvoice.builder import OUTPUT_VAT_ACCOUNT_PREFIX
from erpnext.einvoice.lookup import invoice_numbers_for

# Tiền tố số hiệu TK thuế GTGT theo TT99: đầu ra dùng chung hằng của module HĐĐT để
# hai nơi hiểu "thuế GTGT đầu ra" như nhau; đầu vào là 1331.
_TIEN_TO_VAT = (OUTPUT_VAT_ACCOUNT_PREFIX, "1331")


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def khoang_ky(filters):
	"""(từ ngày, đến ngày, nhãn kỳ). Có đủ Từ ngày / Đến ngày thì ghi đè Tháng."""
	if filters.get("from_date") and filters.get("to_date"):
		tu, den = getdate(filters.from_date), getdate(filters.to_date)
		if tu.day == 1 and tu.replace(day=calendar.monthrange(tu.year, tu.month)[1]) == den:
			return tu, den, f"THÁNG {tu.month:02d}.{tu.year}"
		return tu, den, f"TỪ {formatdate(tu, 'dd/MM/yyyy')} ĐẾN {formatdate(den, 'dd/MM/yyyy')}"
	thang = filters.get("thang") or getdate(nowdate()).strftime("%m-%Y")
	try:
		mm, yyyy = (int(x) for x in thang.split("-"))
		if not 1 <= mm <= 12:
			raise ValueError
	except ValueError:
		frappe.throw(_("Tháng phải có dạng MM-YYYY, ví dụ 10-2026."))
	tu = getdate(f"{yyyy}-{mm:02d}-01")
	den = getdate(f"{yyyy}-{mm:02d}-{calendar.monthrange(yyyy, mm)[1]}")
	return tu, den, f"THÁNG {mm:02d}.{yyyy}"


def get_columns():
	def cot(label, fieldname, fieldtype="Data", width=110, **kw):
		return {"label": _(label), "fieldname": fieldname, "fieldtype": fieldtype, "width": width, **kw}

	def khoi(hau_to, doi_tac, ten_doi_tac, so_hd):
		return [
			cot(ten_doi_tac, doi_tac, width=160),
			cot(so_hd, f"so_hd_{hau_to}", width=110),
			cot("Ngày HĐ", f"ngay_hd_{hau_to}", "Date", 95),
			cot("Tên hàng hóa (nguyên văn hóa đơn)", f"ten_hang_{hau_to}", width=260),
			cot("ĐVT", f"dvt_{hau_to}", width=70),
			cot("SL", f"sl_{hau_to}", "Float", 70),
			cot("Đơn giá (chưa VAT)", f"don_gia_{hau_to}", "Currency", 120),
			cot("Thành tiền (chưa VAT)", f"thanh_tien_{hau_to}", "Currency", 130),
			cot("Thuế suất", f"thue_suat_{hau_to}", "Percent", 80),
			cot("Tiền thuế", f"tien_thue_{hau_to}", "Currency", 110),
			cot("Tổng sau thuế", f"tong_{hau_to}", "Currency", 130),
		]

	return [
		cot("STT", "stt", "Int", 50),
		cot("Mảnh", "manh", width=60),
		*khoi("ban", "kh", "KH", "Số HĐ đầu ra"),
		*khoi("mua", "ncc", "NCC", "Số HĐ đầu vào"),
		*_cot_doi_chieu(cot),
	]


# Khối "ĐỐI CHIẾU" sau hai khối bán / mua — dùng chung cho report, trang web và Excel.
COT_DOI_CHIEU = [
	("Tỷ lệ giá bán / mua", "ty_le_gia", "Float", 100),
	("Chênh lệch giá (%)", "chenh_lech_pt", "Percent", 100),
	("Chênh lệch thành tiền", "chenh_lech_tien", "Currency", 130),
	("Trạng thái", "trang_thai", "Data", 150),
	("Ghi chú", "ghi_chu", "Data", 260),
	("Chứng từ bán", "sales_invoice", "Link", 150),
	("Chứng từ mua", "purchase_invoice", "Link", 150),
]


def _cot_doi_chieu(cot):
	ra = []
	for label, fieldname, fieldtype, width in COT_DOI_CHIEU:
		kw = {"precision": 6} if fieldname == "ty_le_gia" else {}
		if fieldtype == "Link":
			kw["options"] = "Sales Invoice" if fieldname == "sales_invoice" else "Purchase Invoice"
		ra.append(cot(label, fieldname, fieldtype, width, **kw))
	return ra


def get_data(filters):
	if not (filters.get("company") and filters.get("customer")):
		return []
	tu, den, _nhan = khoang_ky(filters)
	tk_vat = _tai_khoan_vat(filters.company)

	si_trong_ky = frappe.get_all(
		"Sales Invoice",
		filters={
			"docstatus": 1,
			"company": filters.company,
			"customer": filters.customer,
			"posting_date": ("between", [tu, den]),
		},
		pluck="name",
	)
	if not si_trong_ky:
		return []

	dong_ban = _dong_hoa_don("Sales Invoice", si_trong_ky, tk_vat, ["so_detail"])
	for d in dong_ban:
		d["trong_ky"] = True
	so_details = sorted({d.so_detail for d in dong_ban if d.so_detail and not d.is_return})
	ma_hang = sorted({d.item_code for d in dong_ban if d.item_code and not d.is_return})
	du_phong = _dong_mua_du_phong(filters.company, ma_hang, tk_vat)
	truoc = _dong_ban_ky_truoc(so_details, tu)
	if du_phong:
		# PI dự phòng không gắn với khách nào: mọi dòng bán cùng mã đến hết kỳ phải tiêu
		# trước, kẻo một PI được ghép lại ở tháng sau hay cho khách khác.
		truoc += _dong_ban_cung_ma(filters.company, ma_hang, den, si_trong_ky)
	dong_ban += list({d.name: d for d in truoc}.values())
	dong_ban.sort(key=lambda d: (getdate(d.posting_date), d.parent, d.idx))

	mua = _dong_mua_theo_so_detail(
		sorted({d.so_detail for d in dong_ban if d.so_detail and not d.is_return}), tk_vat
	)
	tra_cho = {d.return_against for d in dong_ban if d.get("trong_ky") and d.get("return_against")}
	so_hd_ban = invoice_numbers_for(sorted(set(si_trong_ky) | tra_cho))

	ty_le = flt(filters.get("ty_le_hd")) or TY_LE_HOP_DONG
	ghep_duoc = ghep([_ban_cho_ghep(d) for d in dong_ban], mua, du_phong, ty_le)
	data = [_dong_bao_cao(m, so_hd_ban) for m in ghep_duoc]
	# Sắp theo mã chứng từ, không theo số HĐ hiển thị: số HĐĐT có thể trống, khi đó
	# các hoá đơn cùng ngày xen kẽ nhau và các mảnh của một dòng bán bị tách rời.
	data.sort(key=lambda r: (getdate(r["ngay_hd_ban"]), r["sales_invoice"], r["_idx"]))
	danh_dau_nhom(data)
	for r in data:
		danh_gia(r, ty_le)
		if r.get("ngay_hd_mua") and getdate(r["ngay_hd_mua"]) < tu:
			r.setdefault("_ghi_chu", []).append(
				f"HĐ mua ngày {formatdate(r['ngay_hd_mua'], 'dd/MM/yyyy')} - ngoài kỳ"
			)

	if filters.get("supplier"):
		data = [r for r in data if r.get("_supplier") == filters.supplier]
	data = [r for r in data if hop_trang_thai(r["trang_thai"], filters.get("trang_thai"))]

	stt, dong_truoc = 0, None
	for r in data:
		if r["_dong_ban"] != dong_truoc:
			stt, dong_truoc = stt + 1, r["_dong_ban"]
		r["stt"] = stt
		r["ghi_chu"] = "; ".join(r.pop("_ghi_chu", []))
		for k in ("_idx", "_supplier", "_he_so_ban", "_he_so_mua", "_dvt_kho_ban", "_dvt_kho_mua"):
			r.pop(k, None)
	if data:
		data.append(tong_hop(data))
	return data


def _tai_khoan_vat(company):
	ds = frappe.get_all(
		"Account",
		filters={"company": company, "is_group": 0},
		fields=["name", "account_number", "account_type"],
	)
	return chon_tai_khoan_vat(ds, _TIEN_TO_VAT)


def _dong_hoa_don(doctype, ten, tk_vat, them):
	"""Mọi dòng hàng của các hoá đơn `ten`, đã gán thuế suất và tiền thuế (chia theo hoá đơn)."""
	item_dt = f"{doctype} Item"
	tax_dt = "Sales Taxes and Charges" if doctype == "Sales Invoice" else "Purchase Taxes and Charges"
	hd_fields = ["name", "posting_date", "is_return"]
	hd_fields += (
		["customer_name", "return_against"]
		if doctype == "Sales Invoice"
		else ["supplier", "supplier_name", "bill_no", "bill_date"]
	)
	hoa_don = {h.name: h for h in frappe.get_all(doctype, filters={"name": ("in", ten)}, fields=hd_fields)}

	thue = {}
	for t in frappe.get_all(
		tax_dt,
		filters={"parenttype": doctype, "parent": ("in", ten)},
		fields=["parent", "account_head", "charge_type", "rate", "base_tax_amount_after_discount_amount"],
		order_by="idx asc",
	):
		if t.account_head not in tk_vat:
			continue
		hd = thue.setdefault(t.parent, {"tong": 0.0, "thue_suat": None})
		hd["tong"] += flt(t.base_tax_amount_after_discount_amount)
		if hd["thue_suat"] is None and t.charge_type == "On Net Total":
			hd["thue_suat"] = flt(t.rate)

	dong = frappe.get_all(
		item_dt,
		filters={"parenttype": doctype, "parent": ("in", ten)},
		fields=[
			"name",
			"parent",
			"idx",
			"item_code",
			"item_name",
			"uom",
			"qty",
			"net_rate",
			"base_net_amount",
			"item_tax_rate",
			"conversion_factor",
			"stock_uom",
			*them,
		],
		order_by="parent asc, idx asc",
	)
	theo_hd = {}
	for d in dong:
		h = hoa_don[d.parent]
		d.update({k: v for k, v in h.items() if k != "name"})
		d.thanh_tien = flt(d.base_net_amount, 0)
		d.thue_suat = _thue_suat_dong(d.item_tax_rate, tk_vat, (thue.get(h.name) or {}).get("thue_suat"))
		theo_hd.setdefault(h.name, []).append(d)
	for hd, ds in theo_hd.items():
		chia_thue(ds, (thue.get(hd) or {}).get("tong", 0))
	return dong


def _thue_suat_dong(item_tax_rate, tk_vat, mac_dinh):
	try:
		bang = json.loads(item_tax_rate or "{}")
	except ValueError:
		bang = {}
	for tk, rate in bang.items():
		if tk in tk_vat:
			return flt(rate)
	return flt(mac_dinh)


def _dong_ban_ky_truoc(so_details, tu):
	"""Dòng SI trước kỳ của cùng các dòng SO — chỉ để tiêu số lượng PI đã ghép cho chúng."""
	if not so_details:
		return []
	si = frappe.qb.DocType("Sales Invoice")
	sii = frappe.qb.DocType("Sales Invoice Item")
	dong = (
		frappe.qb.from_(sii)
		.join(si)
		.on(si.name == sii.parent)
		.select(*_cot_ban_tieu(sii, si))
		.where(
			(si.docstatus == 1)
			& (si.is_return == 0)
			& (si.posting_date < tu)
			& (sii.so_detail.isin(so_details))
		)
		.run(as_dict=True)
	)
	return _ban_chi_tieu(dong)


def _dong_ban_cung_ma(company, ma_hang, den, loai_tru):
	"""Dòng SI cùng mã hàng đến hết kỳ (mọi khách, trừ các HĐ `loai_tru`) — chỉ để tiêu
	số lượng PI dự phòng theo đúng thứ tự thời gian."""
	si = frappe.qb.DocType("Sales Invoice")
	sii = frappe.qb.DocType("Sales Invoice Item")
	dong = (
		frappe.qb.from_(sii)
		.join(si)
		.on(si.name == sii.parent)
		.select(*_cot_ban_tieu(sii, si))
		.where(
			(si.docstatus == 1)
			& (si.is_return == 0)
			& (si.company == company)
			& (si.posting_date <= den)
			& (sii.item_code.isin(ma_hang))
			& (si.name.notin(loai_tru))
		)
		.run(as_dict=True)
	)
	return _ban_chi_tieu(dong)


def _cot_ban_tieu(sii, si):
	return (
		sii.name,
		sii.parent,
		sii.idx,
		sii.item_code,
		sii.so_detail,
		sii.qty,
		sii.conversion_factor,
		sii.net_rate,
		sii.base_net_amount,
		si.posting_date,
	)


def _ban_chi_tieu(dong):
	for d in dong:
		d.update({"trong_ky": False, "is_return": 0, "thanh_tien": flt(d.base_net_amount, 0), "tien_thue": 0})
	return dong


def _dong_mua_du_phong(company, ma_hang, tk_vat):
	"""Dòng PI cùng mã hàng không thuộc chuỗi nào: không qua PO, dòng PO không lập từ SO,
	hoặc lập từ một dòng SO chưa xuất HĐ bán nào (SO lập trùng, HĐ bán lại xuất từ SO
	khác). Dòng SO đã có HĐ bán — bất kể ngày nào, để mở lại kỳ cũ vẫn ra như trước —
	thì PI của nó thuộc chuỗi của dòng SO đó."""
	if not ma_hang:
		return []
	pi = frappe.qb.DocType("Purchase Invoice")
	pii = frappe.qb.DocType("Purchase Invoice Item")
	poi = frappe.qb.DocType("Purchase Order Item")
	dong = (
		frappe.qb.from_(pii)
		.join(pi)
		.on(pi.name == pii.parent)
		.left_join(poi)
		.on(poi.name == pii.po_detail)
		.select(pii.name, pii.parent, poi.sales_order_item)
		.where(
			(pi.docstatus == 1)
			& (pi.is_return == 0)
			& (pi.company == company)
			& (pii.item_code.isin(ma_hang))
		)
		.run(as_dict=True)
	)
	so_items = sorted({d.sales_order_item for d in dong if d.sales_order_item})
	da_ban = _dong_so_da_ban(so_items)
	ten = {d.name: d.parent for d in dong if not d.sales_order_item or d.sales_order_item not in da_ban}
	if not ten:
		return []
	dong = [
		d for d in _dong_hoa_don("Purchase Invoice", sorted(set(ten.values())), tk_vat, []) if d.name in ten
	]
	for d in dong:
		d.sl = flt(d.qty)
	return dong


def _dong_so_da_ban(so_items):
	"""Các dòng SO trong `so_items` đã có HĐ bán (đã submit, không phải trả hàng)."""
	if not so_items:
		return set()
	si = frappe.qb.DocType("Sales Invoice")
	sii = frappe.qb.DocType("Sales Invoice Item")
	return set(
		frappe.qb.from_(sii)
		.join(si)
		.on(si.name == sii.parent)
		.select(sii.so_detail)
		.distinct()
		.where((si.docstatus == 1) & (si.is_return == 0) & (sii.so_detail.isin(so_items)))
		.run(pluck=True)
	)


def _dong_mua_theo_so_detail(so_details, tk_vat):
	"""{dòng SO: [dòng PI đã chia thuế, theo thứ tự ngày HĐ NCC]} qua dòng PO lập từ SO."""
	if not so_details:
		return {}
	po_item = {
		p.name: p.sales_order_item
		for p in frappe.get_all(
			"Purchase Order Item",
			filters={"docstatus": 1, "sales_order_item": ("in", so_details)},
			fields=["name", "sales_order_item"],
		)
	}
	if not po_item:
		return {}
	pi = frappe.get_all(
		"Purchase Invoice Item",
		filters={"docstatus": 1, "parenttype": "Purchase Invoice", "po_detail": ("in", list(po_item))},
		pluck="parent",
		distinct=True,
	)
	pi = frappe.get_all("Purchase Invoice", filters={"name": ("in", pi), "is_return": 0}, pluck="name")
	if not pi:
		return {}

	kq = {}
	for d in _dong_hoa_don("Purchase Invoice", pi, tk_vat, ["po_detail"]):
		so = po_item.get(d.po_detail)
		if not so:
			continue
		d.sl = flt(d.qty)
		kq.setdefault(so, []).append(d)
	for ds in kq.values():
		ds.sort(key=lambda d: (getdate(d.bill_date or d.posting_date), d.parent, d.idx))
	return kq


def _ban_cho_ghep(d):
	return {**d, "sl": flt(d.get("qty")), "so_detail": None if d.get("is_return") else d.get("so_detail")}


def _so_hd(so_hd_ban, si):
	return (so_hd_ban.get(si) or {}).get("number") or ""


def _dong_bao_cao(m, so_hd_ban):
	b, p = m["ban"], m["mua"]
	ghi_chu = []
	r = {
		"_idx": b["idx"],
		"_dong_ban": b["name"],
		"_dong_mua": p["name"] if p else None,
		"_supplier": p["supplier"] if p else None,
		"_ghi_chu": ghi_chu,
		"kh": b["customer_name"],
		"so_hd_ban": _so_hd(so_hd_ban, b["parent"]),
		"ngay_hd_ban": b["posting_date"],
		"ten_hang_ban": b["item_name"],
		"dvt_ban": b["uom"],
		"sales_invoice": b["parent"],
		"tra_hang": 1 if b.get("is_return") else 0,
		"_he_so_ban": b.get("conversion_factor"),
		"_dvt_kho_ban": b.get("stock_uom"),
		**_tien(b, "ban"),
	}
	if not r["so_hd_ban"]:
		ghi_chu.append("Chưa có số HĐĐT")
	if r["tra_hang"]:
		goc = b.get("return_against")
		r["tra_cho"] = goc
		ghi_chu.append(f"Trả lại HĐ {_so_hd(so_hd_ban, goc) or goc}" if goc else "Hàng trả lại")
	if m.get("theo_ma"):
		r["theo_ma"] = 1
		ghi_chu.append(
			"Ghép theo mã hàng – thiếu liên kết SO→PO"
			if b.get("so_detail")
			else "Ghép theo mã hàng – HĐ bán không qua SO"
		)
	if p:
		if not p["bill_no"]:
			ghi_chu.append("Thiếu số HĐ NCC")
		r.update(
			{
				"ncc": p["supplier_name"],
				"so_hd_mua": p["bill_no"] or "",
				"ngay_hd_mua": p["bill_date"] or p["posting_date"],
				"ten_hang_mua": p["item_name"],
				"dvt_mua": p["uom"],
				"purchase_invoice": p["parent"],
				"_he_so_mua": p.get("conversion_factor"),
				"_dvt_kho_mua": p.get("stock_uom"),
				**_tien(p, "mua"),
			}
		)
	return r


def _tien(d, hau_to):
	return {
		f"sl_{hau_to}": d["sl"],
		f"don_gia_{hau_to}": flt(d["net_rate"]),
		f"thanh_tien_{hau_to}": d["thanh_tien"],
		f"thue_suat_{hau_to}": d["thue_suat"],
		f"tien_thue_{hau_to}": d["tien_thue"],
		f"tong_{hau_to}": flt(d["thanh_tien"] + d["tien_thue"], 0),
	}

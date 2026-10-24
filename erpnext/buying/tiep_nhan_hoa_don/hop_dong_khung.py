# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Hợp đồng khung (HĐK) = Blanket Order loại Purchasing (spec 2026-10-23 mục 2; D4-1, D4-2, D4-6 → D4-9).

- Mã dòng HĐK `[NCC]-[Mã hợp đồng]-[Nhóm]-[STT]`: tự sinh khi có Số hợp đồng, sửa được trước khi Nộp,
  không trùng giữa các HĐK chưa hủy (BR-01). STT nối tiếp số đã dùng, nên phụ lục cùng số hợp đồng
  đánh số tiếp theo hợp đồng gốc.
- Lưu: điền ô trống của thông tin các bên (thẻ công ty / NCC, hợp đồng gần nhất), ĐVT theo hợp đồng.
- Nộp: bắt buộc NCC, Số hợp đồng, Bảng giá mua và các trường chọn ở Cài đặt tiếp nhận hóa đơn NCC
  (mặc định: thông tin các bên, điều khoản, thông tin dòng theo FR-02 — áp ở dòng HĐK vì giữ mã hàng
  hiện tại); ghi giá chưa VAT từng dòng vào bảng giá mua của NCC — nguồn giá "HĐ nguyên tắc" của kiểm
  giá Đợt 1. Hủy: xóa các giá đó. Điều khoản riêng từng NCC ghi ở Điều khoản và điều kiện (mẫu tự tạo).
- Đã Nộp thì không sửa được (chuẩn ERPNext, trừ Đến ngày để gia hạn). Bổ sung mặt hàng / đổi giá
  theo phụ lục: Đơn khung mới có `hop_dong_goc`.
- `da_lap_hoa_don`: lũy kế số lượng trên Hóa đơn mua đã Nộp của các dòng Đơn mua gắn HĐK (FR-23).
"""

import re

import frappe
from frappe import _
from frappe.query_builder.functions import Sum
from frappe.utils import flt, fmt_money, getdate

from erpnext.buying.tiep_nhan_hoa_don.cau_hinh import cai_dat
from erpnext.buying.tiep_nhan_hoa_don.chuan_hoa import bo_dau

# Hệ thống luôn cần (mã dòng, ghi giá HĐ nguyên tắc); trường bắt buộc khác chọn ở Cài đặt (D4-13).
LUON_BAT_BUOC = (("supplier", "Nhà cung cấp"), ("order_no", "Số hợp đồng"), ("bang_gia_mua", "Bảng giá mua"))
BEN_A = (
	"dai_dien_ben_a",
	"chuc_vu_ben_a",
	"mst_ben_a",
	"dia_chi_ben_a",
	"tai_khoan_ben_a",
	"ngan_hang_ben_a",
)
BEN_B = (
	"dai_dien_ben_b",
	"chuc_vu_ben_b",
	"mst_ben_b",
	"dien_thoai_ben_b",
	"fax_ben_b",
	"dia_chi_ben_b",
	"tai_khoan_ben_b",
	"ngan_hang_ben_b",
)


# Giá HĐK gồm VAT quy ra chưa VAT (làm tròn đến đồng); NCC có thể làm tròn theo chiều khác 1 đồng.
# Dùng ở phiếu tiếp nhận và ở đối soát Phiếu nhập ↔ Hóa đơn (Đợt 3) — D4-6, D4-12.
DUNG_SAI_GIA_GOM_VAT = 1


def la_hdk_mua(doc):
	return doc.get("blanket_order_type") == "Purchasing"


def ty_le_thue(thue_suat):
	"""`10%` -> 0.1; `KCT`, `0%`, trống -> 0."""
	so = re.match(r"\s*(\d+(?:[.,]\d+)?)", thue_suat or "")
	return flt(so.group(1).replace(",", ".")) / 100 if so else 0


def gia_chua_vat(gia, thue_suat, gom_vat):
	"""Đơn giá HĐK quy về chưa VAT (D4-6): hợp đồng ghi giá đã gồm VAT thì chia cho (1 + thuế suất) rồi
	làm tròn đến đồng. Bảng giá mua, Đơn mua, Phiếu nhập và hóa đơn điện tử cùng ghi một số chẵn đồng,
	nên đối soát Phiếu nhập ↔ Hóa đơn (Đợt 3, so 0 đồng) không lệch vì phần lẻ của phép chia."""
	return flt(flt(gia) / (1 + ty_le_thue(thue_suat)), 0) if gom_vat else flt(gia)


def dong_don_mua_gia_gom_vat(po_details):
	"""Các dòng Đơn mua (trong `po_details`) gắn hợp đồng khung có đơn giá đã gồm VAT. Site chưa có
	trường của Đợt 4 thì rỗng."""
	if not po_details or not frappe.db.has_column("Blanket Order", "gia_gom_vat"):
		return set()
	poi = frappe.qb.DocType("Purchase Order Item")
	bo = frappe.qb.DocType("Blanket Order")
	return {
		ten
		for (ten,) in frappe.qb.from_(poi)
		.join(bo)
		.on(bo.name == poi.blanket_order)
		.select(poi.name)
		.where(poi.name.isin(list(po_details)) & (bo.gia_gom_vat == 1))
		.run()
	}


def viet_tat(doctype, name):
	ma = frappe.db.get_value(doctype, name, "ma_viet_tat") if name else None
	if ma:
		return re.sub(r"[^A-Z0-9]", "", bo_dau(ma).upper()) or "X"
	tu = re.findall(r"[A-Za-z0-9]+", bo_dau(name or ""))
	return "".join(t[0] for t in tu).upper()[:4] or "X"


def sinh_ma_dong(doc):
	so = doc.get("ma_hop_dong") or doc.order_no
	if not so:
		return
	ncc = viet_tat("Supplier", doc.supplier)
	so = re.sub(r"[^A-Z0-9]", "", bo_dau(so).upper())
	da_dung = {d.ma_dong_hdk for d in doc.items if d.get("ma_dong_hdk")} | set(
		frappe.get_all(
			"Blanket Order Item",
			filters={
				"ma_dong_hdk": ("like", f"{ncc}-{so}-%"),
				"parent": ("!=", doc.name or ""),
				"docstatus": ("<", 2),
			},
			pluck="ma_dong_hdk",
		)
	)
	for d in doc.items:
		if not d.get("ma_dong_hdk") and d.item_code:
			nhom = viet_tat("Item Group", frappe.get_cached_value("Item", d.item_code, "item_group"))
			stt = 1
			while f"{ncc}-{so}-{nhom}-{stt:03d}" in da_dung:
				stt += 1
			d.ma_dong_hdk = f"{ncc}-{so}-{nhom}-{stt:03d}"
			da_dung.add(d.ma_dong_hdk)


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


# --- Thông tin các bên ------------------------------------------------------------


def _dia_chi(ten):
	a = (
		frappe.db.get_value(
			"Address", ten, ["address_line1", "address_line2", "city", "state", "phone", "fax"], as_dict=True
		)
		if ten
		else None
	)
	if not a:
		return {}
	return {
		"dia_chi": ", ".join(x for x in (a.address_line1, a.address_line2, a.city, a.state) if x),
		"dien_thoai": a.phone,
		"fax": a.fax,
	}


def _tai_khoan(filters):
	tk = frappe.get_all(
		"Bank Account",
		filters={"disabled": 0, **filters},
		fields=["bank_account_no", "bank"],
		order_by="is_default desc, creation desc",
		limit=1,
	)
	return tk[0] if tk else frappe._dict()


def _ben_a_tu_cong_ty(company):
	from frappe.contacts.doctype.address.address import get_default_address

	dc = _dia_chi(get_default_address("Company", company))
	tk = _tai_khoan({"is_company_account": 1, "company": company})
	return {
		"mst_ben_a": frappe.get_cached_value("Company", company, "tax_id"),
		"dia_chi_ben_a": dc.get("dia_chi"),
		"tai_khoan_ben_a": tk.bank_account_no,
		"ngan_hang_ben_a": tk.bank,
	}


def _ben_b_tu_ncc(supplier):
	from frappe.contacts.doctype.address.address import get_default_address

	s = frappe.db.get_value(
		"Supplier", supplier, ["tax_id", "supplier_primary_address", "mobile_no"], as_dict=True
	)
	dc = _dia_chi(s.supplier_primary_address or get_default_address("Supplier", supplier))
	tk = _tai_khoan({"party_type": "Supplier", "party": supplier})
	return {
		"mst_ben_b": s.tax_id,
		"dia_chi_ben_b": dc.get("dia_chi"),
		"dien_thoai_ben_b": dc.get("dien_thoai") or s.mobile_no,
		"fax_ben_b": dc.get("fax"),
		"tai_khoan_ben_b": tk.bank_account_no,
		"ngan_hang_ben_b": tk.bank,
	}


def _hdk_gan_nhat(doc, loc):
	"""Thông tin các bên của hợp đồng khung mua đã Nộp gần nhất khớp `loc` (đại diện, chức vụ không có
	trên thẻ công ty / NCC)."""
	ten = frappe.get_all(
		"Blanket Order",
		filters={"blanket_order_type": "Purchasing", "docstatus": 1, "name": ("!=", doc.name or ""), **loc},
		order_by="from_date desc, creation desc",
		limit=1,
		pluck="name",
	)
	return frappe.db.get_value("Blanket Order", ten[0], [*BEN_A, *BEN_B], as_dict=True) if ten else {}


def _dien(doc, truong, nguon):
	for f in truong:
		if not doc.get(f) and nguon.get(f):
			doc.set(f, nguon[f])


def dien_thong_tin_cac_ben(doc):
	"""Chỉ điền ô còn trống: trước hết theo thẻ công ty / NCC, sau đó theo hợp đồng gần nhất."""
	if doc.company:
		_dien(doc, BEN_A, _ben_a_tu_cong_ty(doc.company))
		if any(not doc.get(f) for f in BEN_A):
			_dien(doc, BEN_A, _hdk_gan_nhat(doc, {"company": doc.company}))
	if doc.supplier:
		_dien(doc, BEN_B, _ben_b_tu_ncc(doc.supplier))
		if any(not doc.get(f) for f in BEN_B):
			_dien(doc, BEN_B, _hdk_gan_nhat(doc, {"supplier": doc.supplier}))


# --- Phụ lục, dòng -----------------------------------------------------------------


def _hop_dong_goc(doc):
	if not doc.get("hop_dong_goc"):
		return None
	goc = frappe.db.get_value(
		"Blanket Order",
		doc.hop_dong_goc,
		["name", "supplier", "blanket_order_type", "docstatus", "order_no", "ma_hop_dong", "from_date"],
		as_dict=True,
	)
	if (
		not goc
		or goc.docstatus != 1
		or goc.blanket_order_type != "Purchasing"
		or goc.supplier != doc.supplier
	):
		frappe.throw(_("Hợp đồng gốc phải là Đơn khung mua đã Nộp của cùng nhà cung cấp."))
	return goc


def _dong(doc):
	for d in doc.items:
		if not d.item_code:
			continue
		if not d.get("ma_hang_ncc") and d.party_item_code:
			d.ma_hang_ncc = d.party_item_code
		kho = frappe.get_cached_value("Item", d.item_code, "stock_uom")
		if not d.get("dvt_hdk"):
			d.dvt_hdk = kho
		elif d.dvt_hdk != kho:
			frappe.throw(
				_(
					"Dòng {0} ({1}): ĐVT theo hợp đồng {2} khác ĐVT kho của mặt hàng ({3}). Quy đổi số lượng và đơn giá về {3}, hoặc sửa ĐVT kho của mặt hàng."
				).format(d.idx, d.item_code, d.dvt_hdk, kho)
			)


# --- doc_events của Blanket Order ------------------------------------------------


def khi_validate(doc, method=None):
	if not la_hdk_mua(doc):
		return
	goc = _hop_dong_goc(doc)
	if goc:
		doc.order_no = doc.order_no or goc.order_no
		doc.ma_hop_dong = doc.get("ma_hop_dong") or goc.ma_hop_dong
	if not doc.get("bang_gia_mua") and doc.supplier:
		pl = frappe.db.get_value("Supplier", doc.supplier, "default_price_list")
		if pl and frappe.db.get_value("Price List", pl, "buying"):
			doc.bang_gia_mua = pl
	if doc.get("bang_gia_mua") and not frappe.db.get_value("Price List", doc.bang_gia_mua, "buying"):
		frappe.throw(_("Bảng giá {0} không phải bảng giá mua.").format(frappe.bold(doc.bang_gia_mua)))
	dien_thong_tin_cac_ben(doc)
	_dong(doc)
	sinh_ma_dong(doc)
	_kiem_trung_ma(doc)


def truoc_khi_nop(doc, method=None):
	if not la_hdk_mua(doc):
		return
	c = cai_dat()
	meta, meta_dong = frappe.get_meta("Blanket Order"), frappe.get_meta("Blanket Order Item")
	dau = [*LUON_BAT_BUOC, *((f, meta.get_label(f)) for f in c.truong_bat_buoc_hdk if meta.has_field(f))]
	dong = [(f, meta_dong.get_label(f)) for f in c.truong_bat_buoc_dong_hdk if meta_dong.has_field(f)]
	thieu = [_(nhan) for f, nhan in dau if not frappe.utils.strip_html(str(doc.get(f) or "")).strip()]
	goc = _hop_dong_goc(doc)
	if goc and not doc.get("so_phu_luc"):
		thieu.append(_("Số phụ lục"))
	can_so_luong = not doc.get("khong_cam_ket_so_luong")
	for d in doc.items:
		thieu += [_("Dòng {0}: {1}").format(d.idx, _(nhan)) for f, nhan in dong if not d.get(f)]
		if flt(d.rate) <= 0:
			thieu.append(_("Dòng {0}: đơn giá phải lớn hơn 0").format(d.idx))
		if can_so_luong and flt(d.qty) <= 0:
			thieu.append(
				_(
					"Dòng {0}: số lượng hợp đồng phải lớn hơn 0 (hợp đồng không cam kết số lượng thì tích Không cam kết số lượng tối thiểu)"
				).format(d.idx)
			)
	if thieu:
		frappe.throw(
			_("Hợp đồng khung thiếu thông tin:") + "<ul>" + "".join(f"<li>{t}</li>" for t in thieu) + "</ul>",
			title=_("Chưa Nộp được hợp đồng khung"),
		)
	if goc:
		# Cùng Từ ngày với giá của hợp đồng gốc thì phụ lục ghi đè giá gốc, hủy phụ lục sẽ mất giá gốc.
		trung = {d.item_code for d in doc.items} & set(
			frappe.get_all("Blanket Order Item", filters={"parent": goc.name}, pluck="item_code")
		)
		if trung and getdate(doc.from_date) <= getdate(goc.from_date):
			frappe.throw(
				_("Phụ lục đổi giá mặt hàng {0} phải có Từ ngày sau Từ ngày của hợp đồng gốc ({1}).").format(
					", ".join(sorted(trung)), frappe.format(goc.from_date, "Date")
				)
			)


def khi_nop(doc, method=None):
	"""Ghi giá chưa VAT từng dòng vào bảng giá mua (D4-2, D4-6). Đã có giá cùng (bảng giá, mặt hàng,
	NCC, từ ngày) thì cập nhật giá đó: hai giá cùng ngày hiệu lực làm kiểm giá Đợt 1 báo lỗi."""
	if not la_hdk_mua(doc):
		return
	gom_vat = doc.get("gia_gom_vat")
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
		ghi_chu = _("Hợp đồng khung {0}, dòng {1}").format(doc.order_no, d.ma_dong_hdk)
		if gom_vat:
			ghi_chu += _(" (hợp đồng ghi {0} đã gồm VAT {1})").format(
				fmt_money(d.rate, precision=0), d.thue_suat
			)
		gia.update(
			{
				"item_code": d.item_code,
				"price_list": doc.bang_gia_mua,
				"supplier": doc.supplier,
				"uom": frappe.get_cached_value("Item", d.item_code, "stock_uom"),
				"price_list_rate": gia_chua_vat(d.rate, d.thue_suat, gom_vat),
				"valid_from": doc.from_date,
				"valid_upto": doc.to_date,
				"hop_dong_khung": doc.name,
				"note": ghi_chu,
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

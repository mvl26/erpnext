# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Kiểm giá bán trên Quotation và Sales Order theo hệ số khách hàng (BA12).

Mỗi dòng được ghi lại (chỉ đọc): NCC dự kiến (D08), giá mua và nguồn (R02/D07), hệ số và
số hợp đồng (R01), giá đề xuất (R03), chênh lệch (R04), giá bảng giá KH và cờ "đề xuất
khác bảng giá" (R05), trạng thái. Lệch thì cảnh báo, vẫn lưu được (D03).

Submit Sales Order (BA12 R04, R05, R08 — không còn bước duyệt):
- còn dòng lệch giá đề xuất hoặc chưa có giá mua: bắt buộc "Lý do lệch giá";
- dòng có giá đề xuất khác bảng giá KH: bắt buộc số văn bản, người đại diện KH xác nhận,
  ngày chấp thuận trên chính dòng đó.

Khách không có hệ số: không tính, không cảnh báo (R07). Bỏ qua hàng tặng, khách nội bộ,
mặt hàng không quản lý kho.

Giá bán so ở `net_rate` (sau chiết khấu đơn, bỏ thuế gồm trong đơn giá) vì giá mua chưa
gồm VAT. Giá mua ở tiền tệ công ty, đổi sang tiền tệ chứng từ theo `conversion_rate`.
Kết quả lưu lúc lập không bị sửa khi giá mua đổi sau đó (D05) — chênh lệch đó chỉ hiện ở
báo cáo đối soát.

Gắn qua hooks.py (`doc_events`), không sửa controller chuẩn.
"""

import frappe
from frappe import _
from frappe.utils import cint, flt, get_datetime, getdate

from erpnext.selling.kiem_gia.cau_hinh import cau_hinh, he_so_ap_dung
from erpnext.selling.kiem_gia.gia_goc import (
	CAO_HON,
	CHUA_CO_GIA_MUA,
	KHOP,
	THAP_HON,
	he_so_quy_doi,
	lam_tron_dong,
	ncc_mac_dinh,
	so_sanh,
	tim_gia_mua_nhieu,
	tinh_gia_de_xuat,
)

CHUNG_TU = ("Quotation", "Sales Order")
BO_QUA = "Bỏ qua"
# YC4 (6.2.7): giá lệch nhưng giá mới đã vào bảng giá chờ / đã báo, chưa tới ngày áp.
DANG_CHO = "Đang trong thời hạn báo giá"
TRUONG_DONG = (
	"trang_thai_gia",
	"gia_mua",
	"nguon_gia_mua",
	"chung_tu_gia_mua",
	"ngay_gia_mua",
	"he_so_gia_ban",
	"so_hop_dong_he_so",
	"gia_de_xuat",
	"chenh_lech_gia",
	"gia_bang_gia",
	"khac_bang_gia",
	"ghi_chu_gia",
)
TRUONG_CHAP_THUAN = ("so_van_ban_gia", "nguoi_dai_dien_kh", "ngay_chap_thuan_gia")


# --- doc_events ----------------------------------------------------------------


def kiem_chung_tu(doc, method=None):
	"""`validate` của Quotation / Sales Order (chạy sau validate chuẩn: thuế, tổng đã tính)."""
	if doc.doctype not in CHUNG_TU or not cau_hinh().bat:
		return
	dong = [d for d in doc.get("items") if d.item_code]
	if dong:
		kiem_dong(doc, dong)
		_canh_bao(doc, dong)


def kiem_truoc_submit(doc, method=None, chi_xet=None):
	"""`before_submit` của Sales Order (sau validate, nên kết quả kiểm đã mới). `chi_xet`: chỉ
	xét các dòng này (Update Items sau Submit)."""
	if doc.doctype != "Sales Order" or not cau_hinh().bat:
		return
	dong = [d for d in doc.get("items") if chi_xet is None or d.name in chi_xet]
	lech = [d for d in dong if d in dong_lech(doc)]
	thieu = [(d, _thieu_chap_thuan(d)) for d in dong if cint(d.get("khac_bang_gia"))]
	thieu = [(d, t) for d, t in thieu if t]
	if not lech and not thieu:
		return
	if not nguoi_dung_noi_bo():
		# Khách qua cổng: không nêu chi tiết giá.
		frappe.throw(_("Đơn hàng cần Miyano kiểm tra giá trước khi xác nhận."), title=_("Kiểm giá bán"))

	if lech and not (doc.get("ly_do_lech_gia") or "").strip():
		danh_sach = ", ".join(f"{d.idx} ({d.item_code}: {d.trang_thai_gia})" for d in lech)
		frappe.throw(
			_("Dòng {0} lệch giá đề xuất hoặc chưa có giá mua. Nhập Lý do lệch giá trước khi Submit.").format(
				danh_sach
			),
			title=_("Kiểm giá bán"),
		)
	if thieu:
		meta = frappe.get_meta(doc.doctype + " Item")
		chi_tiet = "".join(
			"<li>"
			+ _("Dòng {0} - {1}: thiếu {2}").format(
				d.idx, frappe.bold(d.item_code), ", ".join(_(meta.get_label(f)) for f in t)
			)
			+ "</li>"
			for d, t in thieu
		)
		frappe.throw(
			_("Giá đề xuất khác bảng giá của khách. Ghi đủ thông tin khách chấp thuận (R05):")
			+ f"<ul>{chi_tiet}</ul>",
			title=_("Kiểm giá bán"),
		)


def kiem_sau_submit(doc, method=None):
	"""`before_update_after_submit` của Sales Order: "Update Items" thêm dòng hoặc đổi giá.

	Update Items lưu từng dòng bị đổi (`insert`/`save`) xuống DB trước khi lưu SO. Lúc này
	Frappe đã gán `modified` mới cho mọi dòng trên đối tượng đang lưu, nhưng trong DB chỉ dòng
	vừa bị đụng có `modified` mới hơn lần lưu trước của SO. Chỉ kiểm lại các dòng đó; dòng khác
	giữ nguyên kết quả lúc lập (D05).
	"""
	if not cau_hinh().bat:
		return
	truoc = doc.get_doc_before_save()
	if not truoc:
		return
	moc = get_datetime(truoc.modified)
	trong_db = dict(
		frappe.get_all(
			doc.doctype + " Item",
			filters={"parent": doc.name, "parenttype": doc.doctype},
			fields=["name", "modified"],
			as_list=True,
		)
	)
	dong = [
		d
		for d in doc.get("items")
		if d.item_code and trong_db.get(d.name) and get_datetime(trong_db[d.name]) > moc
	]
	if not dong:
		return
	kiem_dong(doc, dong)
	_canh_bao(doc, dong)
	kiem_truoc_submit(doc, chi_xet={d.name for d in dong})


# --- Tính trên dòng ------------------------------------------------------------


def kiem_dong(doc, dong):
	"""Tính và ghi kết quả kiểm cho các dòng `dong` của chứng từ."""
	customer = _khach(doc)
	if customer and frappe.get_cached_value("Customer", customer, "is_internal_customer"):
		for d in dong:
			_dat(d, trang_thai_gia=BO_QUA, ghi_chu_gia=_("Khách nội bộ"))
		return

	item_codes = [d.item_code for d in dong]
	he_so = he_so_ap_dung(customer, item_codes, doc.transaction_date)
	quan_ly_kho = dict(
		frappe.get_all(
			"Item", filters={"name": ("in", item_codes)}, fields=["name", "is_stock_item"], as_list=True
		)
	)
	mac_dinh = ncc_mac_dinh(item_codes)
	can_kiem = []
	for d in dong:
		hs = he_so.get(d.item_code)
		if not hs:
			_dat(d)  # R07: không tính, không cảnh báo
			continue
		if cint(d.get("is_free_item")):
			_dat(d, trang_thai_gia=BO_QUA, ghi_chu_gia=_("Hàng tặng"))
			continue
		if not cint(quan_ly_kho.get(d.item_code)):
			_dat(d, trang_thai_gia=BO_QUA, ghi_chu_gia=_("Mặt hàng không quản lý kho"))
			continue
		if not d.get("ncc_du_kien"):
			d.ncc_du_kien = mac_dinh.get(d.item_code)
		can_kiem.append((d, hs))

	if can_kiem:
		gia_mua = tim_gia_mua_nhieu(
			[(d.item_code, d.ncc_du_kien) for d, _hs in can_kiem], doc.transaction_date, doc.company
		)
		bang_gia = gia_bang_gia_nhieu(doc, [d for d, _hs in can_kiem])
		ty_gia = flt(doc.get("conversion_rate")) or 1
		for d, hs in can_kiem:
			_kiem_mot_dong(d, hs, gia_mua[(d.item_code, d.ncc_du_kien)], bang_gia.get(d.name), ty_gia)
		_danh_dau_dang_cho(doc, [d for d, _hs in can_kiem])

	if doc.doctype == "Sales Order":
		for d in dong:
			d.gia_da_kiem = d.rate


def _kiem_mot_dong(d, hs, mua, gia_bang_gia, ty_gia):
	chung = dict(he_so_gia_ban=hs.he_so, so_hop_dong_he_so=hs.so_hop_dong, gia_bang_gia=gia_bang_gia)
	if mua.gia_kho is None:
		return _dat(
			d,
			trang_thai_gia=CHUA_CO_GIA_MUA,
			ghi_chu_gia=_("Chưa có giá mua để đối soát: {0}").format(mua.ly_do),
			**chung,
		)
	cf = flt(d.conversion_factor) or 1
	gia_mua_dong = flt(flt(mua.gia_kho) * cf / ty_gia, d.precision("rate"))
	gia_de_xuat = tinh_gia_de_xuat(flt(mua.gia_kho) * cf / ty_gia, hs.he_so)
	chenh_lech, trang_thai = so_sanh(d.net_rate, gia_de_xuat)
	khac_bang_gia = gia_bang_gia is not None and lam_tron_dong(gia_bang_gia) != gia_de_xuat
	_dat(
		d,
		trang_thai_gia=trang_thai,
		gia_mua=gia_mua_dong,
		nguon_gia_mua=mua.nguon,
		chung_tu_gia_mua=mua.chung_tu,
		ngay_gia_mua=mua.ngay,
		gia_de_xuat=gia_de_xuat,
		chenh_lech_gia=chenh_lech,
		khac_bang_gia=1 if khac_bang_gia else 0,
		ghi_chu_gia=_("{0}; {1} {2}").format(mua.ly_do, hs.nguon, hs.he_so),
		**chung,
	)


def gia_bang_gia_nhieu(doc, dong):
	"""{tên dòng: giá bảng giá KH theo ĐVT của dòng} (R05). Bảng giá là `selling_price_list`
	của chứng từ; giá hiệu lực tại ngày chứng từ như cách ERPNext chọn (dòng của riêng khách
	ưu tiên, rồi `valid_from` mới nhất). Không có giá: không có trong kết quả."""
	pl = doc.get("selling_price_list")
	if not pl or not dong:
		return {}
	customer = _khach(doc) or ""
	rows = frappe.db.sql(
		"""select ip.item_code, ip.uom, ip.price_list_rate, ifnull(ip.customer, '') customer,
			ifnull(ip.valid_from, '2000-01-01') valid_from, it.stock_uom
		from `tabItem Price` ip join `tabItem` it on it.name = ip.item_code
		where ip.price_list = %(pl)s and ip.item_code in %(items)s
			and ifnull(ip.customer, '') in ('', %(customer)s)
			and ifnull(ip.valid_from, '2000-01-01') <= %(ngay)s
			and (ip.valid_upto is null or ip.valid_upto >= %(ngay)s)
			and ifnull(ip.batch_no, '') = ''
		order by ifnull(ip.customer, '') = '', ip.valid_from desc""",
		{
			"pl": pl,
			"items": tuple({d.item_code for d in dong}),
			"customer": customer,
			"ngay": getdate(doc.transaction_date),
		},
		as_dict=True,
	)
	he_so = he_so_quy_doi(list({r.item_code for r in rows}), {r.uom for r in rows})
	theo_hang = {}
	for r in rows:
		cf = 1 if r.uom == r.stock_uom else he_so.get((r.item_code, r.uom))
		if cf:
			theo_hang.setdefault(
				r.item_code, flt(r.price_list_rate) / cf
			)  # ĐVT kho; dòng đầu là dòng được chọn
	return {
		d.name: flt(theo_hang[d.item_code] * (flt(d.conversion_factor) or 1), d.precision("rate"))
		for d in dong
		if d.item_code in theo_hang
	}


def dong_lech(doc):
	"""Dòng phải có lý do khi Submit: lệch giá đề xuất (R04) hoặc chưa có giá mua (R08)."""
	return [d for d in doc.get("items") if d.get("trang_thai_gia") in (THAP_HON, CAO_HON, CHUA_CO_GIA_MUA)]


def _thieu_chap_thuan(d):
	return [f for f in TRUONG_CHAP_THUAN if not (str(d.get(f) or "")).strip()]


def _dat(d, **values):
	for field in TRUONG_DONG:
		d.set(field, values.get(field))


def _khach(doc):
	if doc.doctype == "Quotation":
		return doc.party_name if doc.quotation_to == "Customer" else None
	return doc.customer


def _danh_dau_dang_cho(doc, dong):
	"""Dòng Thấp hơn / Cao hơn trên bảng giá có báo trước, mà mặt hàng đã có giá mới chờ báo
	(bảng giá chờ) hoặc đã báo nhưng chưa tới ngày áp: bán giá hiện hành là đúng quy tắc 7
	ngày, không tính là lệch, không cần lý do hay văn bản chấp thuận (R05); chênh lệch vẫn
	ghi để báo cáo (6.2.7)."""
	from erpnext.selling.kiem_gia.bao_truoc import co_bao_truoc

	pl = doc.get("selling_price_list")
	lech = [d for d in dong if d.get("trang_thai_gia") in (THAP_HON, CAO_HON)]
	if not lech or not co_bao_truoc(pl):
		return
	cho = frappe.db.get_value("Price List", pl, "bang_gia_cho")
	moi = {}
	for r in frappe.db.sql(
		"""select item_code, price_list_rate, valid_from, price_list from `tabItem Price`
		where item_code in %(items)s and ifnull(customer, '') = ''
			and (price_list = %(cho)s or (price_list = %(pl)s and valid_from > %(ngay)s))
		order by valid_from""",
		{
			"items": tuple({d.item_code for d in lech}),
			"cho": cho or "",
			"pl": pl,
			"ngay": doc.transaction_date,
		},
		as_dict=True,
	):
		moi.setdefault(r.item_code, r)
	for d in lech:
		r = moi.get(d.item_code)
		if not r:
			continue
		d.trang_thai_gia = DANG_CHO
		# Giá mới đã nằm trong luồng báo trước (YC4): bán theo giá bảng hiện hành là đúng thỏa
		# thuận, không cần văn bản chấp thuận riêng cho đơn này (R05).
		d.khac_bang_gia = 0
		trang_thai = _("chờ gửi thông báo") if r.price_list == cho else _("đã báo")
		d.ghi_chu_gia = (d.ghi_chu_gia or "") + _("; giá mới {0} từ {1} ({2})").format(
			flt(r.price_list_rate), frappe.format(r.valid_from, "Date"), trang_thai
		)


def nguoi_dung_noi_bo():
	"""Chỉ người dùng nội bộ (System User) thấy cảnh báo: khách lưu chứng từ qua cổng
	(Website User) không được thấy giá mua hay hệ số."""
	return frappe.get_cached_value("User", frappe.session.user, "user_type") == "System User"


def _canh_bao(doc, dong):
	if frappe.flags.in_import or frappe.flags.in_patch or not nguoi_dung_noi_bo():
		return
	muc = []
	for d in dong:
		if d.get("trang_thai_gia") in (THAP_HON, CAO_HON):
			muc.append(
				_("Dòng {0} - {1}: giá mua {2} ({3} {4}), hệ số {5}, giá đúng {6}, chênh {7:+,.0f}").format(
					d.idx,
					frappe.bold(d.item_code),
					frappe.format(d.gia_mua, {"fieldtype": "Currency"}),
					d.nguon_gia_mua,
					d.chung_tu_gia_mua,
					d.he_so_gia_ban,
					frappe.format(d.gia_de_xuat, {"fieldtype": "Currency"}),
					flt(d.chenh_lech_gia),
				)
			)
		elif d.get("trang_thai_gia") == CHUA_CO_GIA_MUA:
			muc.append(_("Dòng {0} - {1}: {2}").format(d.idx, frappe.bold(d.item_code), d.ghi_chu_gia))
		if cint(d.get("khac_bang_gia")):
			muc.append(
				_(
					"Dòng {0} - {1}: giá đề xuất {2} khác bảng giá KH {3} — Submit cần số văn bản, người đại diện KH, ngày chấp thuận"
				).format(
					d.idx,
					frappe.bold(d.item_code),
					frappe.format(d.gia_de_xuat, {"fieldtype": "Currency"}),
					frappe.format(d.gia_bang_gia, {"fieldtype": "Currency"}),
				)
			)
	if muc:
		frappe.msgprint(
			"<ul>" + "".join(f"<li>{m}</li>" for m in muc) + "</ul>",
			title=_("Kiểm giá bán"),
			indicator="orange",
		)

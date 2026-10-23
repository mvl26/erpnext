# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Hệ số giá bán theo khách hàng và quyền sửa (BA12 R01, R07, D01).

- Công tắc chung ở Selling Settings (`bat_kiem_gia_ban`).
- Hệ số theo khách: bảng `he_so_gia_ban` (Customer Price Coefficient) trên Customer — hệ số,
  số hợp đồng, hiệu lực từ-đến. Mỗi ngày tối đa một hệ số hiệu lực (R01).
- Hệ số theo mặt hàng: bảng `he_so_theo_mat_hang` (Customer Item Price Coefficient) trên
  Customer, chỉ áp khi khách KHÔNG có dòng nào ở bảng hệ số theo khách (khi đó bảng này bị khóa
  trên form và không áp). Hai bảng con riêng vì trường bắt buộc khác nhau: form dùng chung
  thuộc tính trường cho mọi bảng cùng một bảng con.
- Khách không có hệ số hiệu lực cho mặt hàng tại ngày chứng từ: không kiểm (R07).

Chỉ vai trò ở `vai_tro_sua_ty_le_lai` (Giám đốc) được sửa hệ số và các cài đặt trên (kể cả
`bat_buoc_dinh_kem_van_ban_gia`: bắt buộc tệp văn bản chấp thuận R05). Kiểm ở server nên chặn
được cả form, import và API.
"""

from itertools import pairwise

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate

TRUONG_CAI_DAT = ("bat_kiem_gia_ban", "bat_buoc_dinh_kem_van_ban_gia", "vai_tro_sua_ty_le_lai")
BANG_HE_SO = ("he_so_gia_ban", "he_so_theo_mat_hang")


def cau_hinh():
	# Đọc thẳng DB (một truy vấn tabSingles), không qua cache Redis: cache dùng chung với web
	# server/worker nên có thể giữ giá trị cũ khi cài đặt bị ghi bằng set_single_value
	# (patch, script) — quyền và công tắc phải luôn đúng giá trị đang lưu.
	s = frappe._dict(frappe.db.get_singles_dict("Selling Settings", cast=True))
	return frappe._dict(
		bat=cint(s.get("bat_kiem_gia_ban")),
		dinh_kem=cint(s.get("bat_buoc_dinh_kem_van_ban_gia")),
		vai_tro_sua_ty_le_lai=s.get("vai_tro_sua_ty_le_lai"),
	)


def he_so_ap_dung(customer, item_codes, ngay):
	"""{mã hàng: `_dict(he_so, so_hop_dong, nguon)` hoặc None} tại `ngay`.

	None nghĩa là khách không có hệ số cho mặt hàng đó: không kiểm (R07).
	"""
	codes = [c for c in item_codes if c]
	if not customer or not codes:
		return {c: None for c in codes}
	ngay = getdate(ngay)
	loc = {"parenttype": "Customer", "parent": customer}
	chung = frappe.get_all(
		"Customer Price Coefficient",
		filters={**loc, "parentfield": "he_so_gia_ban"},
		fields=["he_so", "so_hop_dong", "tu_ngay", "den_ngay"],
		order_by="tu_ngay desc",
	)
	if chung:
		r = next((r for r in chung if _hieu_luc(r, ngay)), None)
		kq = _ket_qua(r, _("Hệ số theo khách")) if r else None
		return {c: kq for c in codes}

	theo_hang = {}
	for r in frappe.get_all(
		"Customer Item Price Coefficient",
		filters={**loc, "parentfield": "he_so_theo_mat_hang", "item_code": ("in", codes)},
		fields=["item_code", "he_so", "so_hop_dong", "tu_ngay", "den_ngay"],
		order_by="tu_ngay desc",
	):
		if _hieu_luc(r, ngay):
			theo_hang.setdefault(r.item_code, r)
	return {c: _ket_qua(theo_hang[c], _("Hệ số theo mặt hàng")) if c in theo_hang else None for c in codes}


def _hieu_luc(r, ngay):
	return getdate(r.tu_ngay) <= ngay and (not r.den_ngay or getdate(r.den_ngay) >= ngay)


def _ket_qua(r, nguon):
	return frappe._dict(he_so=flt(r.he_so), so_hop_dong=r.so_hop_dong, nguon=nguon)


@frappe.whitelist()
def co_quyen_sua_ty_le_lai(vai_tro=None):
	"""Người dùng hiện tại có được sửa hệ số không. `vai_tro` mặc định đọc từ cài đặt."""
	# Administrator có mọi vai trò (frappe.get_roles); xét thẳng để không phụ thuộc cache
	# "roles" dùng chung — worker/scheduler chạy dưới Administrator có thể nạp lại cache
	# thiếu một vai trò vừa tạo mà chưa commit.
	if frappe.session.user == "Administrator":
		return True
	vai_tro = vai_tro or cau_hinh().vai_tro_sua_ty_le_lai or "System Manager"
	return vai_tro in frappe.get_roles()


# --- doc_events ----------------------------------------------------------------


def kiem_selling_settings(doc, method=None):
	"""`Selling Settings.validate`. Quyền xét theo vai trò TRƯỚC khi sửa, để không ai tự gán
	vai trò cho mình rồi sửa luôn."""
	truoc = doc.get_doc_before_save()
	if not truoc:
		return
	doi = [f for f in TRUONG_CAI_DAT if _khac(truoc.get(f), doc.get(f))]
	if doi and not co_quyen_sua_ty_le_lai(truoc.get("vai_tro_sua_ty_le_lai")):
		_tu_choi(doc, doi)
	if cint(doc.get("bat_kiem_gia_ban")):
		_canh_bao_tu_cap_nhat_gia()


def _khac(a, b):
	if isinstance(a, int | float) or isinstance(b, int | float):
		return cint(a) != cint(b)
	return (a or "") != (b or "")


def _canh_bao_tu_cap_nhat_gia():
	"""Stock Settings tự thêm/ghi đè Item Price khi gõ giá trên chứng từ (get_item_details.
	insert_item_price): giá HĐ nguyên tắc trong bảng giá Mua - NCC có thể bị đổi ngầm."""
	s = frappe.get_cached_doc("Stock Settings")
	if cint(s.get("auto_insert_price_list_rate_if_missing")) or cint(
		s.get("update_existing_price_list_rate")
	):
		frappe.msgprint(
			_(
				"Stock Settings đang bật tự thêm/cập nhật giá vào bảng giá khi lập chứng từ. Giá HĐ nguyên tắc trong bảng giá Mua - NCC có thể bị đổi ngầm — nên tắt hai ô Auto Insert Price List Rate If Missing và Update Existing Price List Rate."
			),
			title=_("Kiểm giá bán"),
			indicator="orange",
		)


def kiem_khach(doc, method=None):
	"""`Customer.validate`: quyền sửa hệ số và quy tắc R01."""
	truoc = doc.get_doc_before_save()
	if _he_so_cua(truoc) != _he_so_cua(doc) and not co_quyen_sua_ty_le_lai():
		_tu_choi(doc, list(BANG_HE_SO))

	for d in doc.get("he_so_gia_ban") or []:
		_kiem_dong_he_so(d, _("Hệ số theo khách"))
		if not (d.so_hop_dong or "").strip():
			frappe.throw(_("Hệ số theo khách dòng {0}: nhập số hợp đồng làm căn cứ (R01)").format(d.idx))
	_kiem_chong_lan(doc.get("he_so_gia_ban") or [], _("Hệ số theo khách"))

	theo_hang = doc.get("he_so_theo_mat_hang") or []
	for d in theo_hang:
		_kiem_dong_he_so(d, _("Hệ số theo mặt hàng"))
		if not d.item_code:
			frappe.throw(_("Hệ số theo mặt hàng dòng {0}: chọn mặt hàng").format(d.idx))
	for item_code in {d.item_code for d in theo_hang}:
		_kiem_chong_lan(
			[d for d in theo_hang if d.item_code == item_code], _("Hệ số theo mặt hàng {0}").format(item_code)
		)
	if doc.get("he_so_gia_ban") and theo_hang and not frappe.flags.in_import:
		frappe.msgprint(
			_("Khách đã có hệ số theo khách: bảng hệ số theo mặt hàng không được áp."),
			title=_("Hệ số giá bán"),
			indicator="orange",
		)


def _kiem_dong_he_so(d, bang):
	if flt(d.he_so) <= 0:
		frappe.throw(_("{0} dòng {1}: hệ số phải lớn hơn 0").format(bang, d.idx))
	if d.den_ngay and getdate(d.den_ngay) < getdate(d.tu_ngay):
		frappe.throw(_("{0} dòng {1}: ngày hiệu lực đến trước ngày hiệu lực từ").format(bang, d.idx))


def _kiem_chong_lan(rows, bang):
	"""R01: hai dòng không được cùng hiệu lực ở một ngày nào."""
	rows = sorted(rows, key=lambda d: getdate(d.tu_ngay))
	for truoc, sau in pairwise(rows):
		if not truoc.den_ngay or getdate(truoc.den_ngay) >= getdate(sau.tu_ngay):
			frappe.throw(
				_(
					"{0}: dòng {1} và dòng {2} cùng hiệu lực từ {3}. Đặt ngày hiệu lực đến cho dòng {1}."
				).format(bang, truoc.idx, sau.idx, frappe.format(sau.tu_ngay, "Date"))
			)


def _he_so_cua(doc):
	if not doc:
		return set()
	return {
		(
			f,
			d.get("item_code") or "",
			flt(d.he_so, 6),
			d.so_hop_dong or "",
			str(d.tu_ngay or ""),
			str(d.den_ngay or ""),
		)
		for f in BANG_HE_SO
		for d in doc.get(f) or []
	}


def _tu_choi(doc, fields):
	meta = frappe.get_meta(doc.doctype)
	nhan = ", ".join(_(meta.get_label(f)) for f in fields)
	frappe.throw(
		_("Bạn không có quyền sửa {0}. Chỉ vai trò {1} được sửa hệ số giá bán.").format(
			nhan, frappe.bold(cau_hinh().vai_tro_sua_ty_le_lai or "System Manager")
		),
		frappe.PermissionError,
	)

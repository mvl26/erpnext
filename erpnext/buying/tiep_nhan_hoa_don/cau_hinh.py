# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Cài đặt tiếp nhận hóa đơn NCC và quyền duyệt (spec 2026-10-23 mục 7; FRD 20.3 → D4-4)."""

import frappe
from frappe.utils import cint, flt

from erpnext.buying.tiep_nhan_hoa_don.chuan_hoa import TU_BO_QUA_MAC_DINH, BoChuanHoa

CAI_DAT = "Supplier Invoice Intake Settings"
# Trường bắt buộc khi Nộp hợp đồng khung, gieo một lần vào Cài đặt (D4-13); quản trị đổi ở Cài đặt.
# Hệ thống luôn bắt buộc thêm: NCC, Số hợp đồng, Bảng giá mua, đơn giá, số lượng (hop_dong_khung).
TRUONG_BAT_BUOC_MAC_DINH = (
	"order_date",
	"dai_dien_ben_a",
	"mst_ben_a",
	"dai_dien_ben_b",
	"mst_ben_b",
	"tai_khoan_ben_b",
	"ngan_hang_ben_b",
	"terms",
)
TRUONG_DONG_BAT_BUOC_MAC_DINH = (
	"ma_hang_ncc",
	"ten_hdk",
	"quy_cach",
	"hang_sx",
	"nuoc_sx",
	"so_luu_hanh",
	"thue_suat",
)


def danh_sach_truong(text):
	"""Tên trường trong ô cài đặt (mỗi dòng một tên, chấp nhận dấu phẩy), bỏ trùng, giữ thứ tự."""
	ds = [t.strip() for dong in (text or "").splitlines() for t in dong.split(",")]
	return list(dict.fromkeys(t for t in ds if t))


def cai_dat():
	# Đọc thẳng DB (không qua cache tài liệu), như cau_hinh của BA12 / YC5.
	s = frappe._dict(frappe.db.get_singles_dict(CAI_DAT, cast=True))
	return frappe._dict(
		bat=cint(s.get("bat_tiep_nhan", 1)),
		mst_nguoi_mua=s.get("mst_nguoi_mua"),
		nguong_han_muc=flt(s.get("nguong_canh_bao_han_muc")) or 90,
		nguong_tu_dong=flt(s.get("nguong_tu_dong")) or 0.75,
		nguong_xac_nhan=flt(s.get("nguong_xac_nhan")) or 0.55,
		trong_so_jaccard=flt(s.get("trong_so_jaccard")) or 0.6,
		trong_so_chuoi=flt(s.get("trong_so_chuoi")) or 0.4,
		tu_bo_qua=s.get("tu_bo_qua") if s.get("tu_bo_qua") is not None else TU_BO_QUA_MAC_DINH,
		vai_tro_duyet_lech_gia=s.get("vai_tro_duyet_lech_gia"),
		vai_tro_duyet_anh_xa=s.get("vai_tro_duyet_anh_xa"),
		truong_bat_buoc_hdk=danh_sach_truong(s.get("truong_bat_buoc_hdk")),
		truong_bat_buoc_dong_hdk=danh_sach_truong(s.get("truong_bat_buoc_dong_hdk")),
	)


def bo_chuan_hoa(c=None):
	c = c or cai_dat()
	dong_nghia = frappe.get_all(
		"Supplier Invoice Synonym",
		filters={"parenttype": CAI_DAT, "parent": CAI_DAT},
		fields=["tu_1", "tu_2"],
		order_by="idx",
		as_list=True,
	)
	return BoChuanHoa(dong_nghia=dong_nghia, tu_bo_qua=c.tu_bo_qua)


def _co_vai_tro(vai_tro):
	if frappe.session.user == "Administrator":
		return True
	roles = set(frappe.get_roles())
	return "System Manager" in roles or vai_tro in roles


# Giám đốc duyệt lệch giá, vượt hạn mức, Bảng ánh xạ tên và Nộp hợp đồng khung (người dùng chọn
# 25/10/2026); vai trò có sẵn Sales Manager, như kiểm giá bán Đợt 1 - 2.
VAI_TRO_GIAM_DOC = "Sales Manager"


def vai_tro_duyet_lech_gia(c=None):
	"""Trống thì theo Vai trò Ban Điều hành của đối soát PR ↔ PI (Đợt 3), trống nữa: Sales Manager."""
	c = c or cai_dat()
	return (
		c.vai_tro_duyet_lech_gia
		or frappe.db.get_single_value("Buying Settings", "vai_tro_ban_dieu_hanh")
		or VAI_TRO_GIAM_DOC
	)


def co_quyen_duyet_lech_gia(c=None):
	return _co_vai_tro(vai_tro_duyet_lech_gia(c))


def co_quyen_duyet_anh_xa(c=None):
	return _co_vai_tro((c or cai_dat()).vai_tro_duyet_anh_xa or VAI_TRO_GIAM_DOC)

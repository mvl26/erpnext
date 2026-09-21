# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Nạp danh mục 23 loại chứng từ TBYT và 92 dòng quy tắc theo phân loại.

Bảng dưới đây chép từ ma trận Thông tư trong
`docs/ma-tran-chung-tu-tbyt-theo-phan-loai.md`. Sửa thông tư thì sửa bảng này
rồi chạy lại patch — không phải sửa code xử lý.

Chạy được nhiều lần: gọi lại không nhân đôi loại chứng từ hay dòng quy tắc.
"""

import frappe

from erpnext.tbyt.constants import (
	DEVICE_CLASSES,
	LEVEL_BB,
	LEVEL_BB_STAR,
	LEVEL_NA,
	LEVEL_NC,
	LEVEL_TH,
	SCOPE_AUTHORIZATION,
	SCOPE_BATCH,
	SCOPE_COMPANY,
	SCOPE_ITEM,
	SCOPE_OWNER,
	SCOPE_TRANSACTION,
)

DOCTYPE = "TBYT Document Type"

# Điều kiện của nhóm BB*. Biểu thức đánh giá trên bối cảnh số lưu hành:
# {"miyano_la_chu_so_huu": 0|1, "hang_nhap_khau": 0|1}.
#
# Ba tờ giấy này sinh ra chính vì Miyano đứng tên hộ người khác — nên điều kiện
# là "không phải chủ sở hữu", không phải "hàng nhập khẩu". Riêng CFS thì phải
# đồng thời là hàng nhập khẩu, vì hàng sản xuất trong nước không có CFS.
CONDITIONS = {
	"giay_uy_quyen_csh": "not miyano_la_chu_so_huu",
	"giay_xac_nhan_bao_hanh": "not miyano_la_chu_so_huu",
	"cfs_giay_luu_hanh": "not miyano_la_chu_so_huu and hang_nhap_khau",
}


def _spec(document_key, short_code, document_name, scope_level, levels, multi=0, expiry=0):
	"""`levels` xếp theo đúng thứ tự DEVICE_CLASSES = (A, B, C, D)."""
	return {
		"document_key": document_key,
		"short_code": short_code,
		"document_name": document_name,
		"scope_level": scope_level,
		"cho_phep_nhieu_pham_vi": multi,
		"mac_dinh_co_thoi_han": expiry,
		"levels": levels,
	}


DOCUMENT_TYPES = (
	_spec(
		"ban_ket_qua_phan_loai",
		"PL",
		"Bản kết quả phân loại thiết bị y tế",
		SCOPE_AUTHORIZATION,
		(LEVEL_BB, LEVEL_BB, LEVEL_BB, LEVEL_BB),
	),
	_spec(
		"so_cong_bo_tieu_chuan",
		"CBTC",
		"Phiếu tiếp nhận hồ sơ công bố tiêu chuẩn áp dụng",
		SCOPE_AUTHORIZATION,
		(LEVEL_BB, LEVEL_BB, LEVEL_NA, LEVEL_NA),
	),
	_spec(
		"gcn_dang_ky_luu_hanh",
		"SLH",
		"Giấy chứng nhận đăng ký lưu hành",
		SCOPE_AUTHORIZATION,
		(LEVEL_NA, LEVEL_NA, LEVEL_BB, LEVEL_BB),
		expiry=1,
	),
	_spec(
		"giay_phep_nhap_khau",
		"GPNK",
		"Giấy phép nhập khẩu",
		SCOPE_AUTHORIZATION,
		(LEVEL_NA, LEVEL_NA, LEVEL_TH, LEVEL_TH),
		expiry=1,
	),
	_spec(
		"mau_nhan_hang_hoa",
		"NHAN",
		"Mẫu nhãn hàng hóa lưu hành tại Việt Nam",
		SCOPE_AUTHORIZATION,
		(LEVEL_BB, LEVEL_BB, LEVEL_BB, LEVEL_BB),
	),
	_spec(
		"hdsd_tieng_viet",
		"HDSD",
		"Hướng dẫn sử dụng bằng tiếng Việt",
		SCOPE_AUTHORIZATION,
		(LEVEL_BB, LEVEL_BB, LEVEL_BB, LEVEL_BB),
	),
	_spec(
		"thong_tin_bao_hanh",
		"BH",
		"Thông tin cơ sở bảo hành, điều kiện và thời gian bảo hành",
		SCOPE_OWNER,
		(LEVEL_BB, LEVEL_BB, LEVEL_BB, LEVEL_BB),
	),
	_spec(
		"co_chung_nhan_xuat_xu",
		"CO",
		"Giấy chứng nhận xuất xứ (CO)",
		SCOPE_BATCH,
		(LEVEL_BB, LEVEL_BB, LEVEL_BB, LEVEL_BB),
	),
	_spec(
		"cq_chung_nhan_chat_luong",
		"CQ",
		"Giấy chứng nhận chất lượng (CQ) của từng lô",
		SCOPE_BATCH,
		(LEVEL_BB, LEVEL_BB, LEVEL_BB, LEVEL_BB),
	),
	_spec(
		"ket_qua_kiem_dinh",
		"KD",
		"Kết quả kiểm định an toàn và tính năng kỹ thuật",
		SCOPE_BATCH,
		(LEVEL_TH, LEVEL_TH, LEVEL_TH, LEVEL_TH),
		expiry=1,
	),
	_spec(
		"tai_lieu_ky_thuat_bao_duong",
		"KTBD",
		"Tài liệu kỹ thuật phục vụ sửa chữa, bảo dưỡng",
		SCOPE_AUTHORIZATION,
		(LEVEL_BB, LEVEL_BB, LEVEL_BB, LEVEL_BB),
	),
	_spec(
		"giay_uy_quyen_csh",
		"UQCSH",
		"Giấy ủy quyền của chủ sở hữu TBYT",
		SCOPE_AUTHORIZATION,
		(LEVEL_BB_STAR, LEVEL_BB_STAR, LEVEL_BB_STAR, LEVEL_BB_STAR),
		multi=1,
		expiry=1,
	),
	_spec(
		"giay_xac_nhan_bao_hanh",
		"XNBH",
		"Giấy xác nhận đủ điều kiện bảo hành",
		SCOPE_AUTHORIZATION,
		(LEVEL_BB_STAR, LEVEL_BB_STAR, LEVEL_BB_STAR, LEVEL_BB_STAR),
		multi=1,
		expiry=1,
	),
	_spec(
		"cfs_giay_luu_hanh",
		"CFS",
		"Giấy chứng nhận lưu hành tự do (CFS)",
		SCOPE_AUTHORIZATION,
		(LEVEL_BB_STAR, LEVEL_BB_STAR, LEVEL_BB_STAR, LEVEL_BB_STAR),
		multi=1,
		expiry=1,
	),
	_spec(
		"iso_13485_nha_san_xuat",
		"ISO13485",
		"Giấy chứng nhận ISO 13485 của cơ sở sản xuất",
		SCOPE_OWNER,
		(LEVEL_NC, LEVEL_NC, LEVEL_NC, LEVEL_NC),
		expiry=1,
	),
	_spec(
		"tai_lieu_ky_thuat_csdt",
		"CSDT",
		"Tài liệu mô tả tóm tắt kỹ thuật tiếng Việt / Hồ sơ kỹ thuật chung ASEAN (CSDT)",
		SCOPE_AUTHORIZATION,
		(LEVEL_NC, LEVEL_NC, LEVEL_NC, LEVEL_NC),
	),
	_spec(
		"hop_chuan_hop_quy",
		"HCHQ",
		"Giấy chứng nhận hợp chuẩn / Giấy chứng nhận hợp quy",
		SCOPE_AUTHORIZATION,
		(LEVEL_NC, LEVEL_NC, LEVEL_TH, LEVEL_TH),
		expiry=1,
	),
	_spec(
		"danh_gia_chat_luong_ivd",
		"IVD",
		"IVD: Giấy chứng nhận đánh giá chất lượng",
		SCOPE_AUTHORIZATION,
		(LEVEL_NA, LEVEL_NA, LEVEL_TH, LEVEL_TH),
		expiry=1,
	),
	_spec(
		"niem_yet_gia",
		"NYG",
		"Thông tin niêm yết giá",
		SCOPE_ITEM,
		(LEVEL_BB, LEVEL_BB, LEVEL_BB, LEVEL_BB),
	),
	_spec(
		"ke_khai_gia",
		"KKG",
		"Hồ sơ kê khai giá",
		SCOPE_ITEM,
		(LEVEL_TH, LEVEL_TH, LEVEL_TH, LEVEL_TH),
	),
	_spec(
		"ho_so_phan_phoi",
		"HSPP",
		"Hồ sơ phân phối",
		SCOPE_TRANSACTION,
		(LEVEL_BB, LEVEL_BB, LEVEL_BB, LEVEL_BB),
	),
	_spec(
		"cong_bo_dk_mua_ban",
		"CBMB",
		"Phiếu tiếp nhận công bố đủ điều kiện mua bán TBYT",
		SCOPE_COMPANY,
		(LEVEL_NA, LEVEL_BB, LEVEL_BB, LEVEL_BB),
	),
	_spec(
		"uy_quyen_nhap_khau",
		"UQNK",
		"Giấy ủy quyền nhập khẩu của chủ sở hữu số lưu hành",
		SCOPE_AUTHORIZATION,
		(LEVEL_TH, LEVEL_TH, LEVEL_TH, LEVEL_TH),
		multi=1,
		expiry=1,
	),
)


def setup_tbyt_masters():
	"""Nạp / cập nhật toàn bộ danh mục. Gọi lại nhiều lần vẫn ra đúng 23 x 4."""
	for spec in DOCUMENT_TYPES:
		_upsert_document_type(spec)


def _upsert_document_type(spec):
	key = spec["document_key"]
	if frappe.db.exists(DOCTYPE, key):
		doc = frappe.get_doc(DOCTYPE, key)
	else:
		doc = frappe.new_doc(DOCTYPE)
		doc.document_key = key

	doc.short_code = spec["short_code"]
	doc.document_name = spec["document_name"]
	doc.scope_level = spec["scope_level"]
	doc.cho_phep_nhieu_pham_vi = spec["cho_phep_nhieu_pham_vi"]
	doc.mac_dinh_co_thoi_han = spec["mac_dinh_co_thoi_han"]

	# Dựng lại toàn bộ bảng quy tắc thay vì vá từng dòng: bảng chỉ 4 dòng, và
	# dựng lại là cách duy nhất để sửa thông tư giảm mức cũng có hiệu lực.
	doc.set("rules", [])
	for device_class, level in zip(DEVICE_CLASSES, spec["levels"], strict=True):
		doc.append(
			"rules",
			{
				"device_class": device_class,
				"level": level,
				"condition": CONDITIONS.get(key) if level == LEVEL_BB_STAR else None,
			},
		)

	doc.flags.ignore_permissions = True
	if doc.is_new():
		doc.insert(ignore_permissions=True)
	else:
		doc.save()

"""Lấy hàng: phân bổ ô cho từng dòng phiếu giao, và trang PDA quét xác nhận.

VÌ SAO CÓ FILE NÀY: trước 18/09/2026, ô lấy hàng do `fefo.chon_o_xuat()` chọn
BÊN TRONG hook, đúng lúc duyệt phiếu giao — thủ kho không có danh sách đi lấy, và
không ai đối chiếu "hệ trừ ô A" với "người thật lấy ở ô B". Hai bên lệch nhau thì
TỔNG tồn kho vẫn đúng nên `doi_soat_kho` vẫn báo khớp; sai lệch chỉ lộ ra lúc
kiểm kê thực tế, khi đã mất dấu vết.

Bảng phân bổ `Location Allocation` là thứ spec nền tảng (§4.5, §5.4) đã dành sẵn
chỗ cho từ giai đoạn 1 — file này dựng tiếp đúng thiết kế đó, không nghĩ lại.
"""

import frappe
from frappe import _
from frappe.utils import flt

TEN_BANG_PHAN_BO = "custom_phan_bo_vi_tri"

# Chỉ phiếu giao có giao diện phân bổ (spec §2). Các chứng từ khác vẫn đi đường
# cũ — hằng số ở đây để nơi đọc không phải đoán, và để mở rộng sau này là sửa
# đúng một chỗ.
CHUNG_TU_CO_PHAN_BO = ("Delivery Note",)

# Cùng bộ vai trò với `xep.py`/`quet.py` — thủ kho phải tự làm được, đây là việc
# hằng ngày.
VAI_TRO_DUOC_LAY = {"System Manager", "Stock Manager", "Stock User"}


def phan_bo_cua_dong(chung_tu_type: str, chung_tu: str, dong_hang: str, so_lo: str | None) -> list[dict]:
	"""Các dòng phân bổ của ĐÚNG (dòng hàng, lô). Không có → danh sách rỗng.

	So `so_lo` TRONG PYTHON, không đưa vào `filters`: hàng không quản lý lô lưu
	`None` ở bảng phân bổ nhưng `''` ở vài chỗ khác trong module, và một bộ lọc SQL
	so thẳng sẽ khớp 0 dòng trong im lặng — đúng kiểu hỏng mà cả module này phải
	tránh (xem `xep.py`, `quet.py`).
	"""
	if chung_tu_type not in CHUNG_TU_CO_PHAN_BO or not dong_hang:
		return []

	dong = frappe.get_all(
		"Location Allocation",
		filters={
			"parenttype": chung_tu_type,
			"parent": chung_tu,
			"parentfield": TEN_BANG_PHAN_BO,
			"dong_hang": dong_hang,
		},
		fields=["name", "o", "so_lo", "so_luong"],
		order_by="idx asc",
	)
	return [d for d in dong if (d.so_lo or None) == (so_lo or None)]


def tong_phan_bo(dong: list[dict]) -> float:
	return flt(sum(flt(d["so_luong"]) for d in dong))


def chung_tu_co_phan_bo(chung_tu_type: str, chung_tu: str) -> bool:
	"""Chứng từ này có ÍT NHẤT MỘT dòng phân bổ hay không — KHÔNG lọc theo
	(dòng hàng, lô), khác với `phan_bo_cua_dong`.

	VÒNG SỬA 1 (Critical 2, review điều phối): dùng để phân biệt hai ca mà
	`phan_bo_cua_dong` trả `[]` như nhau nhưng Ý NGHĨA khác hẳn — "chứng từ
	chưa từng qua trang Lấy hàng" (đi FEFO như cũ) khỏi "chứng từ CÓ bảng
	phân bổ nhưng không dòng nào khớp đúng (dòng hàng, lô) đang ghi" (phiếu
	amend đổi tên dòng hàng, đường mất chiều lô của `tach_theo_lo`, hoặc dòng
	Packed Item của Product Bundle) — ca sau phải CHẶN theo spec §5, không
	được âm thầm rơi về FEFO. Xem `hook_sle._phan_bo_da_khai`.
	"""
	if chung_tu_type not in CHUNG_TU_CO_PHAN_BO:
		return False
	return bool(
		frappe.db.exists(
			"Location Allocation",
			{"parenttype": chung_tu_type, "parent": chung_tu, "parentfield": TEN_BANG_PHAN_BO},
		)
	)

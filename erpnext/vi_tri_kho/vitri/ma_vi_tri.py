"""Mã vị trí 10 ký tự theo chuẩn SPD của Miyano Việt Nam.

    [Khu 2][Dãy 2][Khoang 2][Tầng 2][Ô 2]  →  1B01040302

Nguồn: `SPD_VanHanh_PhanTichMaViTriKho_20260907_v2` §5.2, xác nhận lại ở
`SPD_PhanMem_DacTaNhanNhapKho_50x30_20260908_v2` trường F8.

Khu viết SỐ trước CHỮ (1B, 3B, 4B). §5.2 mô tả bằng lời là "chữ cái A-Z + số
tầng nhà" nhưng mọi ví dụ trong cả ba tài liệu — kể cả ảnh chụp kho MSC — đều
ngược lại. Chủ dự án chốt theo ví dụ (10/09/2026).

BỎ 2 KÝ TỰ MÃ KHO (Task 1, 2026-09-11): bản trước có mã 12 ký tự
`[Kho 2][Khu 2][Dãy 2][Khoang 2][Tầng 2][Ô 2]`. `Storage Location` đã có
trường `kho` trỏ thẳng `Warehouse` — lưu thêm mã kho ngay trong chuỗi mã ô là
hai nguồn sự thật cho cùng một thông tin, dễ lệch khi một trong hai bị sửa mà
cái kia không theo. Khớp luôn mã kho SPD Nhật trong tài liệu gốc (4B01-04-0302
— không có phần "kho").

`cap_do()` và `ma_cha()` là nền cho cây vị trí ở Task 2: mỗi cấp là TIỀN TỐ
của cấp sau (Khu → Dãy → Khoang → Tầng → Ô), nên mã cha luôn là `ma[:-2]` và
cây suy ra được thẳng từ mã, không cần bảng tra nào.
"""

import re

import frappe
from frappe import _

# Dải giá trị theo §5.2, cưỡng chế bằng chính regex chứ không chỉ kiểm độ dài:
# Dãy 01-99 · Khoang 01-99 · Tầng 01-09 · Ô 01-99.
_KHU = r"[0-9][A-Z]"
_HAI_SO_1_99 = r"(?:0[1-9]|[1-9][0-9])"
_HAI_SO_1_09 = r"(?:0[1-9])"

TEN_CAP = ("Khu", "Dãy", "Khoang", "Tầng", "Ô")

# Mỗi cấp là tiền tố của cấp sau. Nhờ vậy mã cha luôn là `ma[:-2]`, và cây
# suy ra từ mã không cần bảng tra nào.
_PHAN = (_KHU, _HAI_SO_1_99, _HAI_SO_1_99, _HAI_SO_1_09, _HAI_SO_1_99)
MAU_CAP = [re.compile("^" + "".join(_PHAN[: i + 1]) + "$") for i in range(5)]

MAU_MA = MAU_CAP[4]
VI_DU = "1B01040302"


def cap_do(ma: str) -> int:
	"""Trả cấp 1..5 của mã. Sai định dạng ở mọi cấp → ném lỗi tiếng Việt."""
	ma = ma or ""
	for i, mau in enumerate(MAU_CAP):
		if mau.match(ma):
			return i + 1
	frappe.throw(
		_(
			"Mã vị trí không đúng chuẩn: {0}\n\n"
			"Ô chứa hàng phải đúng 10 ký tự, không dấu gạch, theo thứ tự "
			"[Khu 2][Dãy 2][Khoang 2][Tầng 2][Ô 2] — ví dụ {1} "
			"(khu 1B, dãy 01, khoang 04, tầng 03, ô 02).\n"
			"Nút nhóm là tiền tố của mã đó: 1B / 1B01 / 1B0104 / 1B010403.\n"
			"Dãy, Khoang và Ô nhận 01–99; Tầng nhận 01–09."
		).format(ma or "(trống)", VI_DU)
	)


def phan_tich_ma(ma: str) -> dict:
	"""Tách mã ô LÁ (10 ký tự) thành 5 thành phần."""
	khop = MAU_MA.match(ma or "")
	if not khop:
		cap_do(ma)  # ném lỗi có thông báo đầy đủ
		frappe.throw(_("Mã {0} là nút nhóm, không phải ô chứa hàng.").format(ma))
	return {
		"khu": ma[0:2],
		"day": ma[2:4],
		"khoang": ma[4:6],
		"tang": ma[6:8],
		"o": ma[8:10],
	}


def dinh_dang_nhan(ma: str) -> str:
	"""Dạng IN lên nhãn ô: `1B0104-0302` (một gạch trước Tầng-Ô)."""
	p = phan_tich_ma(ma)
	return f"{p['khu']}{p['day']}{p['khoang']}-{p['tang']}{p['o']}"


def ma_cha(ma: str) -> str | None:
	"""Mã của nút cha = chính mã đó bỏ 2 ký tự cuối. Khu (cấp 1) không có cha."""
	if cap_do(ma) == 1:
		return None
	return ma[:-2]

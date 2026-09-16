"""Đếm module Code 128 — MỘT định nghĩa cho cả phép kiểm lẫn việc vẽ nhãn.

Vì sao không ước lượng theo độ dài chuỗi: Code 128 đổi bộ mã giữa chừng và mỗi
lần đổi tốn một ký hiệu. Một chuỗi TOÀN CHỮ SỐ độ dài LẺ không mã hoá hết được
trong bộ C (bộ C nuốt hai chữ số một lần), nên phải bắt đầu ở bộ B cho chữ số
đầu rồi chèn một ký hiệu chuyển — tốn hai ký hiệu, không phải làm tròn lên một.
Bản nháp spec đã tính sai đúng chỗ này.

Hệ quả nếu tính thiếu: `validate` cho qua một số lô mà nhãn không vẽ nổi trong
khung, JS buộc phải bóp mã vạch xuống dưới 2 dot, và máy quét ĐỌC RA SAI KÝ TỰ
— không phải đọc hỏng. Sai lặng lẽ, trên vật thể đã dán lên hàng.
"""

import frappe
from frappe import _

#: Bề rộng một module, mm. 2 dot trên đầu in nhiệt 203 dpi (1 dot = 1/203 inch
#: = 0,125 mm). 1 dot dưới ngưỡng đọc tin cậy của Code 128; 3 dot làm mã tràn
#: khung. Đây là giá trị DUY NHẤT dùng được trên ZD421 — xem spec §6.2.
X_MM = 0.25

#: Bố cục A (theo mockup SPD): mã vạch nằm ở cột trái, rộng 28,0 mm.
MODULE_BO_CUC_A = int(28.0 / X_MM)  # 112

#: Bố cục B: mã vạch chiếm hết chiều ngang vùng in an toàn, 47,0 mm.
MODULE_BO_CUC_B = int(47.0 / X_MM)  # 188

#: start (11) + checksum (11) + stop (13). Không phụ thuộc dữ liệu.
_MODULE_CO_DINH = 35

#: Mỗi ký hiệu Code 128 rộng đúng 11 module (trừ stop, đã tính ở trên).
_MODULE_MOI_KY_HIEU = 11


def so_ky_hieu(s: str) -> int:
	"""Số ký hiệu Code 128 cần để mã hoá `s`, kể cả ký hiệu chuyển bộ mã."""
	if not s:
		return 0
	if s.isdigit():
		if len(s) % 2 == 0:
			return len(s) // 2
		# Chữ số đầu đi bộ B, rồi một ký hiệu chuyển sang bộ C cho phần còn lại.
		return 2 + (len(s) - 1) // 2
	return len(s)


def so_module(s: str) -> int:
	"""Bề rộng `s` tính bằng module Code 128."""
	if not s:
		return 0
	return _MODULE_CO_DINH + _MODULE_MOI_KY_HIEU * so_ky_hieu(s)


def kiem_tra_do_dai(s: str, nhan: str) -> None:
	"""`throw` nếu `s` không vẽ nổi trong vùng in, kèm CON SỐ cụ thể.

	`nhan` là tên thứ đang kiểm, để câu báo đọc được ("số lô", "mã vật tư").

	Câu báo phải nói đang bao nhiêu / được bao nhiêu / suy ra bao nhiêu ký tự.
	Một câu chung chung khiến người dùng cắt bừa vài ký tự rồi thử lại — và số
	lô cắt bớt là số lô SAI dán lên hàng.
	"""
	m = so_module(s)
	if m <= MODULE_BO_CUC_B:
		return

	frappe.throw(
		_(
			"Số {0} '{1}' dài {2} ký tự, cần {3} module mã vạch nhưng nhãn 50×30 chỉ "
			"chứa được {4} module. Giới hạn thực tế: 26 chữ số (độ dài chẵn), "
			"23 chữ số (độ dài lẻ), hoặc 13 ký tự nếu có chữ. Không thu nhỏ mã vạch "
			"được: dưới 2 dot trên máy in nhiệt thì máy quét đọc ra SAI ký tự."
		).format(nhan, s, len(s), m, MODULE_BO_CUC_B)
	)

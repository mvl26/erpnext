"""Mã vị trí 12 ký tự theo chuẩn SPD của Miyano Việt Nam.

    [Kho 2][Khu 2][Dãy 2][Khoang 2][Tầng 2][Ô 2]  →  K11B01040302

Nguồn: `SPD_VanHanh_PhanTichMaViTriKho_20260907_v2` §5.2, xác nhận lại ở
`SPD_PhanMem_DacTaNhanNhapKho_50x30_20260908_v2` trường F8 (ô nhãn được nới
từ 20,0 lên 23,0 mm chính là để in đủ 12 ký tự này).

**Đừng lấy regex từ `SPD_PhanMem_QuyTacMaHoaNhan_20260908_v1`.** Tài liệu đó
ghi F8 là 11 ký tự, không có trường Khoang, vì nó tự khai kế thừa đặc tả nhãn
**v1** — bản trước khi ô F8 được nới. Cùng lỗi ở trường F9 (nó viết "5 số cuối
F10" trong khi đặc tả v2 nói rõ "bỏ phương án" đó). Hai trường độc lập cùng
lệch, cùng một nguyên nhân: tài liệu đó lỗi thời, không phải một phương án khác.

Khu viết SỐ trước CHỮ (1B, 3B, 4B). §5.2 mô tả bằng lời là "chữ cái A-Z + số
tầng nhà" nhưng mọi ví dụ trong cả ba tài liệu — kể cả ảnh chụp kho MSC — đều
ngược lại. Chủ dự án chốt theo ví dụ (10/09/2026).
"""

import re

import frappe
from frappe import _

# Dải giá trị theo §5.2, cưỡng chế bằng chính regex chứ không chỉ kiểm độ dài:
# Dãy 01-99 · Khoang 01-99 · Tầng 01-09 · Ô 01-99.
_HAI_SO_1_99 = r"(?:0[1-9]|[1-9][0-9])"
_HAI_SO_1_09 = r"(?:0[1-9])"
MAU_MA = re.compile(
	r"^(?P<ma_kho>[A-Z][0-9])"
	r"(?P<khu>[0-9][A-Z])"
	rf"(?P<day>{_HAI_SO_1_99})"
	rf"(?P<khoang>{_HAI_SO_1_99})"
	rf"(?P<tang>{_HAI_SO_1_09})"
	rf"(?P<o>{_HAI_SO_1_99})$"
)

VI_DU = "K11B01040302"


def phan_tich_ma(ma: str) -> dict:
	"""Tách mã 12 ký tự thành 6 thành phần. Sai định dạng → ném lỗi tiếng Việt."""
	khop = MAU_MA.match(ma or "")
	if not khop:
		frappe.throw(
			_(
				"Mã vị trí không đúng chuẩn: {0}\n\n"
				"Mã phải đúng 12 ký tự, không dấu gạch, theo thứ tự "
				"[Kho 2][Khu 2][Dãy 2][Khoang 2][Tầng 2][Ô 2] — ví dụ {1} "
				"(kho K1, khu 1B, dãy 01, khoang 04, tầng 03, ô 02).\n"
				"Dãy/Khoang/Ô nhận 01–99, Tầng nhận 01–09."
			).format(ma or "(trống)", VI_DU)
		)
	return khop.groupdict()


def dinh_dang_nhan(ma: str) -> str:
	"""Dạng IN lên nhãn ô: `K11B0104-0302` (đúng một gạch trước Tầng-Ô).

	Tài liệu có hai dạng hiển thị cho cùng 12 ký tự — §5.2 viết
	`K1-1B01-04-0302`, trường F8 của đặc tả nhãn v2 viết `K11B0104-0302`.
	Chốt theo nhãn: đó là thứ dán lên kệ, nhân viên đọc hằng ngày, và tài liệu
	nhãn là bản mới hơn. Mã LƯU trong CSDL vẫn là 12 ký tự liền, không gạch.
	"""
	p = phan_tich_ma(ma)
	return f"{p['ma_kho']}{p['khu']}{p['day']}{p['khoang']}-{p['tang']}{p['o']}"

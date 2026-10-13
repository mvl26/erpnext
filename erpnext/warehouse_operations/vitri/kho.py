"""Hỏi trạng thái quản lý vị trí của một kho.

Hook ghi sổ chạy trên MỌI dòng Stock Ledger Entry của toàn hệ, kể cả các kho
không bật. Nên câu hỏi "kho này có bật không" phải rẻ — đọc cache, không
truy vấn DB. Đổi lại: mọi chỗ đổi cờ đều PHẢI gọi `xoa_cache_kho()`.

CRITICAL 2 (review điều phối, sau khi 147/147 bài "xong"): `o_chua_xep()`
trước đây CHỈ hỏi `frappe.db.exists` — không kiểm bản ghi trùng mã có ĐÚNG
dạng ô "Chưa xếp vị trí" hay không (đúng kho, cờ `la_o_chua_xep`, không phải
nhóm, không bị vô hiệu hoá). `bat_kho.py::tao_o_chua_xep` (Task 12, vòng
sửa 1) đã từng kiểm đủ BỐN điều kiện này khi TẠO ô, nhưng `o_chua_xep()`
(được gọi ở MỌI lần hook chạy sau đó, không chỉ lúc tạo) lại không kiểm gì
— hai nơi cùng một khái niệm "ô CHUA-XEP hợp lệ" nhưng lệch nhau. Hậu quả
thật: `Storage Location.disabled` không read-only và `Stock Manager` có
quyền `write` — ai đó tích `disabled=1` lên ô CHUA-XEP (một checkbox, không
qua RPC nào của module này) làm hook nhập (không lọc `disabled`) vẫn ghi
vào đó bình thường, trong khi FEFO xuất (`fefo.py::chon_o_xuat`, qua vị từ
tổ-tiên-hoặc-chính-nó `_TO_TIEN_TAT` — từ Task 4, thay cho phép kiểm
`disabled=0` đơn giản đời trước) loại bỏ nó rồi `frappe.throw` giữa
`Stock Ledger Entry.on_submit` — cuộn ngược MỌI phiếu xuất của MỌI mặt hàng
đang ở CHUA-XEP. Sửa: gộp phép kiểm
dạng vào MỘT hàm dùng chung (`kiem_tra_dang_o_chua_xep`) cho cả hai nơi —
không lặp lại vị từ, đúng nguyên tắc "một nguồn sự thật duy nhất" mà cả
module `vitri/` đã áp dụng nhiều lần (xem `bat_kho.py::NGUONG_SAI_SO`,
`kiem_tra_khong_phai_kho_tong`).
"""

import frappe
from frappe import _

MA_O_CHUA_XEP = "ZZZ-CHUA-XEP"  # "ZZZ" để ô hệ thống LUÔN xếp cuối bảng chữ cái


def kho_co_quan_ly_vi_tri(kho: str) -> bool:
	"""Kho này có bật quản lý vị trí không. Kho không tồn tại → False."""
	if not kho:
		return False
	try:
		return bool(frappe.get_cached_value("Warehouse", kho, "custom_quan_ly_vi_tri"))
	except frappe.DoesNotExistError:
		return False


def xoa_cache_kho(kho: str) -> None:
	"""Xoá cache Warehouse. Bắt buộc gọi sau mỗi lần đổi cờ."""
	frappe.clear_cache(doctype="Warehouse")
	frappe.clear_document_cache("Warehouse", kho)


def ma_o_chua_xep(kho: str) -> str:
	"""Mã ô CHUA-XEP của một kho. Kèm tên kho để không trùng giữa các kho."""
	return f"{MA_O_CHUA_XEP}-{kho}"


def kiem_tra_dang_o_chua_xep(kho: str, ten: str) -> None:
	"""Ném lỗi tiếng Việt nếu bản ghi `ten` KHÔNG đúng dạng ô "Chưa xếp vị
	trí" hợp lệ của `kho`. Không làm gì (không throw) nếu đúng dạng.

	Bốn điều kiện — CÙNG bốn điều kiện `bat_kho.py::tao_o_chua_xep` kiểm
	khi TẠO ô (xem docstring module): đúng `kho`, cờ `la_o_chua_xep`, không
	phải `is_group`, không `disabled`. Dùng CHUNG giữa nơi TẠO
	(`tao_o_chua_xep`) và nơi ĐỌC (`o_chua_xep`, chạy trên mọi lần hook) —
	sai một trong hai nơi (quên cập nhật khi sửa) là đúng loại lệch mà cả
	module này lập ra để phòng.
	"""
	hien_co = frappe.db.get_value(
		"Storage Location",
		ten,
		["kho", "la_o_chua_xep", "is_group", "disabled"],
		as_dict=True,
	)
	dung_dang = (
		hien_co
		and hien_co.kho == kho
		and hien_co.la_o_chua_xep
		and not hien_co.is_group
		and not hien_co.disabled
	)
	if not dung_dang:
		frappe.throw(
			_(
				'Ô {0} không đúng dạng ô "Chưa xếp vị trí" của kho {1} (sai kho, không '
				"đánh dấu ô gom hàng, là ô nhóm, hoặc đã bị vô hiệu hoá). Kiểm tra lại ô "
				"này trước khi tiếp tục."
			).format(ten, kho)
		)


def o_chua_xep(kho: str) -> str | None:
	"""Tên bản ghi ô CHUA-XEP của kho, hoặc None nếu kho CHƯA TỪNG tạo ô
	CHUA-XEP (chưa bật quản lý vị trí lần nào).

	CRITICAL 2: docstring cũ ghi "None nếu kho chưa bật" trong khi mã chỉ
	kiểm SỰ TỒN TẠI của bản ghi — chính lời nói sai đó dẫn tới Critical 2
	(không ai kiểm dạng vì docstring không nói cần kiểm). Giờ: bản ghi
	KHÔNG tồn tại → None (đúng "chưa từng tạo"); bản ghi TỒN TẠI nhưng SAI
	DẠNG → `frappe.throw` (không phải None — None có nghĩa khác hẳn, và một
	người gọi coi `None` là "an toàn, cứ tạo mới" sẽ dẫm đúng bẫy Critical 2
	lần nữa ở một chỗ khác).
	"""
	ten = ma_o_chua_xep(kho)
	if not frappe.db.exists("Storage Location", ten):
		return None
	kiem_tra_dang_o_chua_xep(kho, ten)
	return ten

"""Cắt AN TOÀN tiêu đề `Error Log` về dưới trần `Data(140)` của CSDL.

VÌ SAO CẦN — không phải "cắt cho ngắn", mà là một ca lưới an toàn tự nó thủng
(review điều phối, vòng sửa 2/5):

`Error Log.method` (tiêu đề) là fieldtype `Data` → cột `varchar(140)`
(`frappe/database/database.py::VARCHAR_LEN`). `BaseDocument._validate_length`
so `len(cstr(value))` với trần đó ở MỌI `insert()`, và ném
`frappe.CharacterLengthExceededError` nếu vượt (xem
`throw_length_exceeded_error`, `frappe/model/base_document.py`).

Nhiều chỗ trong `warehouse_operations/vitri/` ghép DỮ LIỆU NGƯỜI DÙNG (mã vật tư, số lô,
mã quét) vào tiêu đề, BÊN TRONG một khối `except Exception: frappe.log_error(
...)` — đúng khuôn Ruling N: "một bản ghi hỏng không được làm sập cả lời gọi
cho những bản ghi lành khác". Nếu chuỗi ghép vào đủ dài (`Item.name`/số lô
GÕ TAY có thể dài tới hàng chục, hàng trăm ký tự — không có trần nào ở tầng dữ
liệu chặn việc đó), chính `frappe.log_error()` — ĐANG NẰM TRONG khối `except`
— có thể ném `CharacterLengthExceededError`, và lỗi mới đó VĂNG RA NGOÀI khối
`except` bao quanh nó, đúng thứ mà lưới an toàn được dựng lên để chặn. Tức là
"quét/gõ một mã bất kỳ không được làm nổ traceback" — điều khoản cả kế hoạch
nhấn đi nhấn lại — thủng đúng ở lối thoát hiểm của chính nó.

MỘT HÀM DÙNG CHUNG, gọi TRƯỚC khi đưa `title` cho `frappe.log_error` ở MỌI
chỗ ghép dữ liệu người dùng vào tiêu đề — năm bản cắt tay là năm cơ hội để một
bản quên (và bản quên đó vẫn nổ, đúng bug này, ở đúng một chỗ khác).
"""

#: `Data` -> `varchar(140)`, xem `frappe.database.database.Database.VARCHAR_LEN`.
#: KHÔNG suy ra hằng số này từ `frappe` lúc import module (tránh phụ thuộc vào
#: một chi tiết cài đặt CSDL cụ thể lúc nạp module) — hằng số này là giá trị
#: THẬT đã đo, và bài test khoá đúng con số 140 nếu Frappe đổi nó.
TRAN_DO_DAI_TIEU_DE = 140

#: Đuôi đánh dấu ĐÃ CẮT — người đọc `Error Log` phải biết tiêu đề thật dài
#: hơn những gì thấy (traceback đầy đủ vẫn còn nguyên trong thân bản ghi, chỉ
#: tiêu đề — thứ đi vào một cột có trần — bị rút gọn). Không cắt câm lặng.
_DUOI_DA_CAT = " …(cắt)"


def cat_tieu_de(tieu_de: str) -> str:
	"""Trả `tieu_de`, cắt ngắn NẾU CẦN để `len(...) <= 140` — an toàn cho
	`frappe.log_error(title=...)` dù chuỗi ghép vào dài bao nhiêu.

	Không cắt giữa chừng rồi im lặng: nếu phải cắt, phần cuối LUÔN là
	`_DUOI_DA_CAT`, và tổng độ dài vẫn `<= 140` — cắt xong phải còn nhận ra
	được đây là một tiêu đề bị rút gọn, không phải tiêu đề tự nhiên.
	"""
	if len(tieu_de) <= TRAN_DO_DAI_TIEU_DE:
		return tieu_de
	return tieu_de[: TRAN_DO_DAI_TIEU_DE - len(_DUOI_DA_CAT)] + _DUOI_DA_CAT

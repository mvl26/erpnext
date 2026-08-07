# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Bảng mã lỗi Fast → thông báo tiếng Việt — Phần G của đặc tả.

Kế toán không đọc được "836". Mỗi mã đi kèm một câu giải thích và một gợi ý
hành động, để người dùng biết phải sửa gì chứ không chỉ biết là hỏng.
"""

from dataclasses import dataclass

from frappe import _

# Đã phát hành rồi — gặp mã này thì tuyệt đối không phát hành lại, phải truy vấn
# (370) để lấy thông tin hóa đơn đã có.
DUPLICATE_INVOICE_CODES = frozenset({"809", "835"})

# Chứng thư số HSM chưa sẵn sàng — hỏng ở mức hệ thống, mọi hóa đơn đều tắc.
CERTIFICATE_CODES = frozenset({"500", "501", "502"})

# Trùng số do hai người phát hành cùng lúc — thử lại được (Phần G gợi ý sau 5 giây).
RETRYABLE_CODES = frozenset({"1002"})


@dataclass(frozen=True)
class ErrorInfo:
	code: str
	message: str
	hint: str = ""


def _catalogue():
	"""Từng dòng của bảng Phần G, tách ra theo mã."""
	rows = (
		(
			("152",),
			_("Số tiền bằng chữ chưa đúng với loại tiền tệ."),
			_("Hệ thống sẽ sinh lại số tiền bằng chữ — kiểm tra lại loại tiền của hóa đơn."),
		),
		(
			("460",),
			_("Có hóa đơn treo trên hệ thống Fast."),
			_("Dùng nút Truy vấn (370) để đối soát và dọn hóa đơn treo trước khi phát hành tiếp."),
		),
		(
			tuple(CERTIFICATE_CODES),
			_("Chứng thư số HSM chưa sẵn sàng (chưa có, chưa hiệu lực hoặc đã hết hạn)."),
			_("Liên hệ Fast — toàn bộ việc phát hành hóa đơn đang tắc, không phải lỗi của chứng từ này."),
		),
		(
			("601", "808"),
			_("Quyển hóa đơn đã hết số."),
			_("Báo kế toán trưởng đăng ký thêm số với Cơ quan Thuế trước khi phát hành tiếp."),
		),
		(
			("800", "801"),
			_("Lỗi kỹ thuật khi đóng gói dữ liệu gửi Fast."),
			_("Gửi mã log này cho bộ phận kỹ thuật — không phải lỗi nhập liệu."),
		),
		(
			("802",),
			_("Tài khoản API không có quyền thực hiện thao tác này."),
			_("Báo quản trị kiểm tra phân quyền của user API trên portal Fast."),
		),
		(
			tuple(DUPLICATE_INVOICE_CODES),
			_("Hóa đơn này đã được phát hành trước đó."),
			_("Bấm Truy vấn (370) để lấy về số hóa đơn đã có. TUYỆT ĐỐI không phát hành lại."),
		),
		(
			("812", "825"),
			_("Tên hàng hoặc thông tin khách hàng quá dài, hoặc có ký tự xuống dòng."),
			_("Tên hàng tối đa 500 ký tự và không được xuống dòng — sửa đúng dòng bị báo."),
		),
		(
			("819", "730", "731"),
			_("Ngày hóa đơn không hợp lệ, hoặc nhỏ hơn ngày của hóa đơn đã phát hành gần nhất."),
			_("Đặt lại ngày hóa đơn không sớm hơn hóa đơn liền trước."),
		),
		(
			("836",),
			_("Thiếu thông tin bắt buộc của người mua hoặc tính chất hàng hóa."),
			_("Chạy lại kiểm tra dữ liệu trên chứng từ — bảng lỗi sẽ chỉ đúng trường còn thiếu."),
		),
		(
			("888",),
			_("Hóa đơn chưa tồn tại trên hệ thống Fast."),
			_("Chưa phát hành lần nào — có thể phát hành."),
		),
		(
			("900", "901"),
			_("Hóa đơn gốc không hợp lệ để điều chỉnh hoặc thay thế."),
			_("Hóa đơn gốc có thể đã bị điều chỉnh/thay thế rồi — kiểm tra lại chuỗi điều chỉnh."),
		),
		(
			tuple(RETRYABLE_CODES),
			_("Số hóa đơn bị trùng do nhiều người phát hành cùng lúc."),
			_("Thử lại sau vài giây."),
		),
		(
			("3000",),
			_("Hóa đơn vượt quá 300 dòng."),
			_("Tách thành nhiều hóa đơn."),
		),
		(
			("78011", "78012"),
			_("Khai báo trên portal Fast chưa đúng (chứng thư hoặc hình thức hóa đơn chưa đăng ký)."),
			_("Báo quản trị kiểm tra khai báo trên portal Fast."),
		),
		(
			("78013",),
			_("Mã số thuế khách hàng không hợp lệ."),
			_("Mã số thuế phải đúng 10 hoặc 13 chữ số — sửa trên hồ sơ khách hàng."),
		),
		(
			("78016",),
			_("Hóa đơn đã được Cơ quan Thuế chấp nhận nên không hủy được."),
			_("Muốn thay đổi phải lập hóa đơn điều chỉnh hoặc thay thế."),
		),
		(
			("78025",),
			_("Thuế suất của dòng hàng không hợp lệ."),
			_("Mã -9 chỉ dùng cho dòng ghi chú hoặc hóa đơn điều chỉnh."),
		),
		(
			("63505", "63503", "8031", "10000"),
			_("Hệ thống ký số đang gặp sự cố."),
			_("Thử lại sau ít phút. Kiểm tra tên hàng có ký tự đặc biệt (& < >) không."),
		),
	)
	catalogue = {}
	for codes, message, hint in rows:
		for code in codes:
			catalogue[code] = ErrorInfo(code=code, message=message, hint=hint)
	return catalogue


ERROR_CATALOGUE = _catalogue()


def describe_error(code, fallback=""):
	"""Thông báo tiếng Việt cho một mã lỗi Fast."""
	code = (code or "").strip()
	if info := ERROR_CATALOGUE.get(code):
		return info
	return ErrorInfo(
		code=code,
		message=_("Fast trả về lỗi {0}{1}").format(code or _("không rõ mã"), f": {fallback}" if fallback else "."),
		hint=_("Xem nhật ký HĐĐT để biết nội dung Fast trả về."),
	)


def is_duplicate_invoice_error(code):
	return (code or "").strip() in DUPLICATE_INVOICE_CODES


def is_certificate_error(code):
	return (code or "").strip() in CERTIFICATE_CODES


def is_retryable_error(code):
	return (code or "").strip() in RETRYABLE_CODES

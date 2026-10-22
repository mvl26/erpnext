# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Đọc mã tra cứu và trang tra cứu in trên PDF chính thức của Fast (mục 4.3).

API Fast chỉ trả ``keySearch`` — chuỗi base64 dài dùng để gọi API, **không phải**
mã khách nhập trên trang tra cứu. Mã ngắn (``6D A83 217 253 61N 682``) và địa chỉ
trang tra cứu chỉ có trên PDF, nên đọc thẳng từ các byte PDF mà method 380 trả về.

Chỉ neo vào phần nhãn tiếng Anh: phần tiếng Việt tùy cách Fast nhúng font, còn
``(Invoice code)`` / ``(Search on)`` thì đọc ra ổn định. pypdf tách nhãn, dấu hai
chấm và giá trị thành nhiều dòng (``(Invoice code)\\n:\\n \\n6D A83…``), nên khoảng
trắng trước giá trị được phép gồm cả xuống dòng; còn bản thân mã thì dừng ở cuối dòng.
"""

import io
import re

_CODE = re.compile(r"\(Invoice code\)\s*:\s*([0-9A-Za-z]+(?:[ \t]+[0-9A-Za-z]+)*)")
_URL = re.compile(r"\(Search on\)\s*:\s*(https?://\S+)")


def parse_lookup_text(text):
	"""``{"code", "url"}`` từ chữ của PDF. Không thấy phần nào thì phần đó là ``""``."""
	text = text or ""
	code = _CODE.search(text)
	url = _URL.search(text)
	return {"code": code.group(1).strip() if code else "", "url": url.group(1) if url else ""}


def read_lookup_from_pdf(content):
	"""Đọc từ byte PDF. **Không bao giờ ném lỗi** — PDF hỏng hay đổi bố cục chỉ cho kết quả rỗng.

	Việc đọc mã đi kèm việc tải PDF chính thức; một lỗi ở đây mà làm hỏng việc lưu
	PDF thì mất luôn file kế toán cần để gửi tay.
	"""
	if not content:
		return parse_lookup_text("")
	try:
		from pypdf import PdfReader

		reader = PdfReader(io.BytesIO(content))
		text = "\n".join(page.extract_text() or "" for page in reader.pages)
	except Exception:
		text = ""
	return parse_lookup_text(text)

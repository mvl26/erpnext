# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Chuẩn hóa tên hàng và chấm điểm khớp tên (FRD-MAP-01 mục 10.1 - 10.3).

Không đụng DB: tham số (từ đồng nghĩa, từ bỏ qua, trọng số) do người gọi truyền vào từ cài đặt,
nên test được độc lập và dùng chung cho Bảng ánh xạ tên (tên chuẩn hóa) lẫn đối soát 4 tầng.
"""

import re
import unicodedata
from difflib import SequenceMatcher

TU_BO_QUA_MAC_DINH = "size, cỡ, loại, cái"
DONG_NGHIA_MAC_DINH = (
	("sonde", "ống thông"),
	("2 way", "2 nhánh"),
	("dùng 1 lần", "dùng một lần"),
	("găng khám", "găng tay khám"),
)
# Cỡ chữ là một phần của quy cách (găng size M khác size L).
CO_CHU = frozenset({"xs", "s", "m", "l", "xl", "xxl", "xxxl"})


def bo_dau(text):
	text = (text or "").replace("đ", "d").replace("Đ", "D")
	return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def _co_ban(text):
	"""Chữ thường, bỏ dấu, dấu phẩy thập phân thành dấu chấm, chỉ giữ chữ, số, dấu chấm."""
	text = bo_dau(text).lower()
	text = re.sub(r"(\d),(\d)", r"\1.\2", text)
	return " ".join(re.findall(r"\d+(?:\.\d+)?|[a-z]+", text))


def _tu(text):
	return re.findall(r"\d+(?:\.\d+)?|[a-z]+", text)


class BoChuanHoa:
	"""Gói tham số chuẩn hóa: `dong_nghia` là các cặp (từ, từ tương đương), `tu_bo_qua` là chuỗi
	phân cách bằng dấu phẩy. Cặp đồng nghĩa thay vế trái bằng vế phải, cụm dài thay trước."""

	def __init__(self, dong_nghia=DONG_NGHIA_MAC_DINH, tu_bo_qua=TU_BO_QUA_MAC_DINH):
		cap = [(_co_ban(a), _co_ban(b)) for a, b in dong_nghia if _co_ban(a) and _co_ban(b)]
		self.dong_nghia = sorted(cap, key=lambda p: -len(p[0]))
		self.tu_bo_qua = {_co_ban(t) for t in (tu_bo_qua or "").split(",") if _co_ban(t)}

	def chuan_hoa(self, text):
		"""Chuỗi chuẩn hóa: dùng để so khớp và làm khóa của Bảng ánh xạ tên."""
		s = f" {_co_ban(text)} "
		for a, b in self.dong_nghia:
			s = s.replace(f" {a} ", f" {b} ")
		return " ".join(t for t in _tu(s) if t not in self.tu_bo_qua)

	def khoa_quy_cach(self, text):
		"""Tập mọi con số và cỡ chữ (10.2). Hai tên phải cùng khóa mới được xét khớp (BR-03)."""
		tu = _tu(self.chuan_hoa(text))
		so = {_so(t) for t in tu if t[0].isdigit()}
		return frozenset(so | {t for t in tu if t in CO_CHU})

	def diem(self, a, b, trong_so_jaccard=0.6, trong_so_chuoi=0.4):
		"""Điểm tương đồng tên (10.3): Jaccard tập từ và SequenceMatcher trên chuỗi chuẩn hóa."""
		ca, cb = self.chuan_hoa(a), self.chuan_hoa(b)
		ta, tb = set(ca.split()), set(cb.split())
		if not (ta and tb):
			return 0.0
		jaccard = len(ta & tb) / len(ta | tb)
		return round(trong_so_jaccard * jaccard + trong_so_chuoi * SequenceMatcher(None, ca, cb).ratio(), 4)


def _so(t):
	"""`7.50` và `7.5` là một số; `016` và `16` cũng vậy."""
	if "." in t:
		t = t.rstrip("0").rstrip(".")
	return t.lstrip("0") or "0"

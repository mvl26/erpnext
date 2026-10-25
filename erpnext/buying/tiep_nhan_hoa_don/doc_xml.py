# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Đọc XML hóa đơn điện tử (định dạng Thông tư 78/2021, phần `HDon/DLHDon`) thành cấu trúc của
FRD-MAP-01 mục 11.2.

Không phụ thuộc nhà cung cấp dịch vụ hóa đơn: bỏ namespace, tìm `HDon` ở bất cứ độ sâu nào (tệp
tải từ cổng thuế bọc trong `TDiep/DLieu`). Tệp do NCC gửi là dữ liệu ngoài: parser tắt DTD, entity
và truy cập mạng (chống XXE, bom entity).
"""

import re

from frappe import _
from frappe.utils import flt
from lxml import etree

# TChat: 1 hàng hóa, dịch vụ; 2 khuyến mại; 3 chiết khấu thương mại; 4 ghi chú, diễn giải.
HANG_HOA = 1
# TTHDLQuan/TCHDon: tính chất của hóa đơn có liên quan tới một hóa đơn đã lập (NĐ 123/2020 Điều 19).
TINH_CHAT_LIEN_QUAN = {"1": "Thay thế", "2": "Điều chỉnh"}
MAU_SO_PO = re.compile(r"\bPUR-ORD-\d{4}-\d+\b")


class LoiDocHoaDon(Exception):
	pass


def _ten(el):
	return etree.QName(el).localname if isinstance(el.tag, str) else ""


def _con(el, ten):
	if el is None:
		return None
	return next((c for c in el if _ten(c) == ten), None)


def _chu(el, *duong_dan):
	for ten in duong_dan:
		el = _con(el, ten)
	return (el.text or "").strip() if el is not None and el.text else ""


def thue_suat(text):
	"""`10%` -> "10%", `KCT` -> "KCT". Giữ dạng chữ để so với thuế suất trên dòng hợp đồng khung."""
	text = (text or "").strip().upper().replace(" ", "")
	if not text:
		return ""
	so = re.fullmatch(r"(\d+(?:[.,]\d+)?)%?", text)
	if so:
		return f"{flt(so.group(1).replace(',', '.')):g}%"
	return text


def doc_hoa_don_xml(noi_dung):
	"""`noi_dung`: bytes của tệp XML. Trả về dict theo lược đồ FRD 11.2; tệp không đọc được thì
	raise `LoiDocHoaDon` với lý do người dùng hiểu được."""
	parser = etree.XMLParser(
		resolve_entities=False, no_network=True, load_dtd=False, dtd_validation=False, huge_tree=False
	)
	try:
		goc = etree.fromstring(noi_dung, parser)
	except etree.XMLSyntaxError as e:
		raise LoiDocHoaDon(_("Tệp không phải XML hợp lệ: {0}").format(e)) from e

	hdon = goc if _ten(goc) == "HDon" else next((e for e in goc.iter() if _ten(e) == "HDon"), None)
	dl = _con(hdon, "DLHDon")
	tt = _con(dl, "TTChung")
	nd = _con(dl, "NDHDon")
	if tt is None or nd is None:
		raise LoiDocHoaDon(_("Không thấy phần HDon/DLHDon của hóa đơn điện tử trong tệp."))

	dong = []
	ds = _con(nd, "DSHHDVu")
	for h in (e for e in (ds if ds is not None else ()) if _ten(e) == "HHDVu"):
		dong.append(
			{
				"stt": int(flt(_chu(h, "STT"))) or len(dong) + 1,
				"tinh_chat": int(flt(_chu(h, "TChat"))) or HANG_HOA,
				"ma_hang": _chu(h, "MHHDVu"),
				"ten_hang": _chu(h, "THHDVu"),
				"dvt": _chu(h, "DVTinh"),
				"so_luong": flt(_chu(h, "SLuong")),
				"don_gia": flt(_chu(h, "DGia")),
				"chiet_khau": flt(_chu(h, "STCKhau")),
				"thanh_tien": flt(_chu(h, "ThTien")),
				"thue_suat": thue_suat(_chu(h, "TSuat")),
			}
		)

	toan = _con(nd, "TToan")
	lq = _con(tt, "TTHDLQuan")
	van_ban = " ".join(t for t in dl.itertext() if t and t.strip())
	so_po = MAU_SO_PO.search(van_ban)
	return {
		"so_hoa_don": _chu(tt, "SHDon"),
		"ky_hieu": _chu(tt, "KHHDon"),
		"mau_so": _chu(tt, "KHMSHDon"),
		"ngay": _chu(tt, "NLap"),
		"tien_te": _chu(tt, "DVTTe") or "VND",
		"ncc": {"ten": _chu(nd, "NBan", "Ten"), "mst": _chu(nd, "NBan", "MST")},
		"nguoi_mua": {"ten": _chu(nd, "NMua", "Ten"), "mst": _chu(nd, "NMua", "MST")},
		"so_po_ghi_tren_hoa_don": so_po.group(0) if so_po else "",
		"dong_hang": dong,
		"tong_tien_hang": flt(_chu(toan, "TgTCThue")),
		"tien_thue": flt(_chu(toan, "TgTThue")),
		"tong_thanh_toan": flt(_chu(toan, "TgTTTBSo")),
		# Hóa đơn thay thế / điều chỉnh: hóa đơn bị thay thế / bị điều chỉnh. Hóa đơn điều chỉnh ghi phần
		# tăng dương, phần giảm âm.
		"lien_quan": {
			"tinh_chat": TINH_CHAT_LIEN_QUAN.get(_chu(lq, "TCHDon"), ""),
			"mau_so": _chu(lq, "KHMSHDCLQuan"),
			"ky_hieu": _chu(lq, "KHHDCLQuan"),
			"so_hoa_don": _chu(lq, "SHDCLQuan"),
			"ngay": _chu(lq, "NLHDCLQuan"),
			"ghi_chu": _chu(lq, "GChu"),
		},
	}


def chuan_mst(mst):
	"""So MST không phân biệt khoảng trắng, gạch ngang (MST chi nhánh 0109529507-001 giữ phần đuôi)."""
	return re.sub(r"[\s.]", "", (mst or "")).strip("-")

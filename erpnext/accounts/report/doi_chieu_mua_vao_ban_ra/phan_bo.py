# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Chia thuế theo dòng và ghép dòng bán - dòng mua theo số lượng (logic thuần, không đọc CSDL).

Hai bất biến báo cáo dựa vào:

- Tổng tiền thuế các dòng của một hoá đơn bằng đúng tổng VAT trên hoá đơn: thuế
  làm tròn từng dòng, phần lệch dồn vào dòng cuối (`item_wise_tax_detail` gộp theo
  mã hàng nên không dùng được khi hai dòng cùng mã).
- Tách một dòng thành nhiều mảnh không làm lệch tiền: mảnh cuối của một dòng lấy
  đúng phần tiền còn lại thay vì tự tính tỉ lệ.
"""

from frappe.utils import flt

_EPS = 1e-9
_TIEN = ("thanh_tien", "tien_thue")


def chia_thue(dong, tong_thue):
	"""Gán `tien_thue` cho từng dòng của MỘT hoá đơn; phần lệch dồn vào dòng `idx` lớn nhất."""
	if not dong:
		return
	for d in dong:
		d["tien_thue"] = flt(flt(d["thanh_tien"]) * flt(d["thue_suat"]) / 100, 0)
	cuoi = max(dong, key=lambda d: d["idx"])
	cuoi["tien_thue"] = flt(cuoi["tien_thue"] + flt(tong_thue, 0) - sum(d["tien_thue"] for d in dong), 0)


def chon_tai_khoan_vat(tai_khoan, tien_to):
	"""Tên các TK thuế GTGT trong `tai_khoan` (dict có `name`, `account_number`, `account_type`).

	TK có số hiệu thì nhận theo tiền tố (`3331`/`1331`, TT99) — TK loại "Tax" khác số
	hiệu (thuế TNCN, nhà thầu…) không phải VAT. TK chưa đánh số thì nhận theo loại
	"Tax": hệ thống tài khoản không đánh số (site thử), hoặc đánh số nhưng sót TK VAT.
	"""
	return {
		a["name"]
		for a in tai_khoan
		if (a.get("account_number") or "").startswith(tuple(tien_to))
		or (not a.get("account_number") and a.get("account_type") == "Tax")
	}


def _con_lai(dong):
	return {"goc": dong, "sl": flt(dong["sl"]), **{k: flt(dong[k]) for k in _TIEN}}


def _cat(con, sl):
	"""Cắt `sl` khỏi phần còn lại `con`; cắt hết thì lấy trọn tiền còn lại."""
	if sl >= con["sl"] - _EPS:
		manh = {"sl": con["sl"], **{k: con[k] for k in _TIEN}}
	else:
		manh = {"sl": sl, **{k: flt(con[k] * sl / con["sl"], 0) for k in _TIEN}}
	for k in ("sl", *_TIEN):
		con[k] = flt(con[k] - manh[k], 9 if k == "sl" else 0)
	return {**con["goc"], **manh}


def ghep(ban, mua):
	"""Ghép từng dòng bán với các dòng PI cùng `so_detail`, theo thứ tự, tiêu dần số lượng.

	`ban` đã sắp theo thời gian; dòng `trong_ky=False` (hoá đơn bán kỳ trước) chỉ tiêu
	số lượng PI chứ không xuất ra. Trả `[{"ban": {...}, "mua": {...} | None}]`.
	"""
	hang_doi = {so: [_con_lai(d) for d in ds] for so, ds in mua.items()}
	kq = []
	for b in ban:
		con = _con_lai(b)
		manh = []
		doi = hang_doi.get(b.get("so_detail")) if con["sl"] > _EPS else None
		while doi and con["sl"] > _EPS:
			p = doi[0]
			sl = min(con["sl"], p["sl"])
			manh.append({"ban": _cat(con, sl), "mua": _cat(p, sl)})
			if p["sl"] <= _EPS:
				doi.pop(0)
		if not manh or abs(con["sl"]) > _EPS:
			manh.append({"ban": _cat(con, con["sl"]) if manh else {**b}, "mua": None})
		if b.get("trong_ky", True):
			kq.extend(manh)
	return kq


# Hợp đồng Himedic: giá bán = giá mua x 1,01. Lệch quá dung sai thì gắn cờ.
TY_LE_HOP_DONG = 1.01
DUNG_SAI_TY_LE = 0.0005

KHOP = "Khớp"
THIEU_DAU_VAO = "Thiếu đầu vào"
LECH_GIA = "Lệch giá"
LECH_THUE = "Lệch thuế suất"
LECH_DVT = "Lệch ĐVT"
TRA_HANG = "Trả hàng"
CHUA_KHOP = "Chưa khớp (mọi loại)"
TRANG_THAI = (KHOP, THIEU_DAU_VAO, LECH_GIA, LECH_THUE, LECH_DVT, TRA_HANG)


def danh_gia(r, ty_le=TY_LE_HOP_DONG):
	"""Gán `ty_le_gia`, `chenh_lech_pt`, `chenh_lech_tien`, `trang_thai` cho một dòng báo cáo.

	Mảnh đã ghép luôn có SL bán = SL mua (`ghep` cắt theo SL), nên lệch số lượng chỉ
	còn hiện ra dưới dạng phần "Thiếu đầu vào"; khác ĐVT thì SL và giá không so được.
	"""
	if r.get("tra_hang"):
		r["trang_thai"] = TRA_HANG
		return r
	if not r.get("purchase_invoice"):
		r["trang_thai"] = THIEU_DAU_VAO
		return r
	gia_mua = flt(r.get("don_gia_mua"))
	r["ty_le_gia"] = flt(flt(r.get("don_gia_ban")) / gia_mua, 6) if gia_mua else None
	r["chenh_lech_pt"] = flt((r["ty_le_gia"] - 1) * 100, 4) if r["ty_le_gia"] else None
	r["chenh_lech_tien"] = flt(flt(r.get("thanh_tien_ban")) - flt(r.get("thanh_tien_mua")), 0)
	lech = []
	if r["ty_le_gia"] is None or abs(r["ty_le_gia"] - flt(ty_le)) > DUNG_SAI_TY_LE + _EPS:
		lech.append(LECH_GIA)
	if flt(r.get("thue_suat_ban")) != flt(r.get("thue_suat_mua")):
		lech.append(LECH_THUE)
	if (r.get("dvt_ban") or "") != (r.get("dvt_mua") or ""):
		lech.append(LECH_DVT)
	r["trang_thai"] = ", ".join(lech) or KHOP
	return r


def hop_trang_thai(trang_thai, chon):
	"""Dòng có trạng thái `trang_thai` có lọt bộ lọc `chon` không (`chon` rỗng = mọi dòng)."""
	if not chon:
		return True
	if chon == CHUA_KHOP:
		return trang_thai != KHOP
	return chon in (trang_thai or "").split(", ")


def danh_dau_nhom(data):
	"""Gắn `manh` ("i/n") cho các mảnh tách từ cùng một dòng bán (`_dong_ban`) và ghi chú
	cho dòng HĐ mua (`_dong_mua`) chia cho nhiều dòng bán. Gọi trước khi lọc để "2/2"
	vẫn cho biết dòng đang xem chỉ là một phần của dòng bán."""
	dem_ban, dem_mua = {}, {}
	for r in data:
		dem_ban[r["_dong_ban"]] = dem_ban.get(r["_dong_ban"], 0) + 1
		if r.get("_dong_mua"):
			dem_mua.setdefault(r["_dong_mua"], set()).add(r["_dong_ban"])
	thu = {}
	for r in data:
		n = dem_ban[r["_dong_ban"]]
		thu[r["_dong_ban"]] = thu.get(r["_dong_ban"], 0) + 1
		r["manh"] = f"{thu[r['_dong_ban']]}/{n}" if n > 1 else ""
		so_lan = len(dem_mua.get(r.get("_dong_mua"), ()))
		if so_lan > 1:
			r.setdefault("_ghi_chu", []).append(f"Dòng HĐ mua chia cho {so_lan} dòng bán")
	return data


def tong_hop(data):
	"""Dòng TỔNG CỘNG. Tỷ lệ giá bình quân và chênh lệch chỉ tính trên dòng đã ghép được:
	cộng cả doanh thu thiếu đầu vào vào sẽ ra một "lãi" không có thật."""
	tong = {"ten_hang_ban": "TỔNG CỘNG", "la_tong": 1}
	for hau_to in ("ban", "mua"):
		for k in ("thanh_tien", "tien_thue", "tong"):
			tong[f"{k}_{hau_to}"] = flt(sum(flt(r.get(f"{k}_{hau_to}")) for r in data), 0)
	khop = [r for r in data if r.get("purchase_invoice")]
	ban_khop = sum(flt(r.get("thanh_tien_ban")) for r in khop)
	mua_khop = sum(flt(r.get("thanh_tien_mua")) for r in khop)
	tong["chenh_lech_tien"] = flt(ban_khop - mua_khop, 0)
	tong["ty_le_gia"] = flt(ban_khop / mua_khop, 6) if mua_khop else None
	tong["chenh_lech_pt"] = flt((tong["ty_le_gia"] - 1) * 100, 4) if tong["ty_le_gia"] else None

	dem = dict.fromkeys(TRANG_THAI, 0)
	for r in data:
		for nhan in (r.get("trang_thai") or "").split(", "):
			if nhan in dem:
				dem[nhan] += 1
	thieu = [r for r in data if r.get("trang_thai") == THIEU_DAU_VAO]
	tong["tom_tat"] = {
		"so_dong": len(data),
		"so_hd_ban": len({r["sales_invoice"] for r in data if r.get("sales_invoice")}),
		"so_hd_mua": len({r["purchase_invoice"] for r in data if r.get("purchase_invoice")}),
		"so_dong_lech": sum(1 for r in khop if r.get("trang_thai") != KHOP),
		"dem": dem,
		"doanh_thu_co_dau_vao": flt(ban_khop, 0),
		"doanh_thu_thieu_dau_vao": flt(sum(flt(r.get("thanh_tien_ban")) for r in thieu), 0),
	}
	return tong

# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Chia thuế theo dòng và ghép dòng bán - dòng mua theo số lượng (logic thuần, không đọc CSDL).

Hai bất biến báo cáo dựa vào:

- Tổng tiền thuế các dòng của một hoá đơn bằng đúng tổng VAT trên hoá đơn: thuế
  làm tròn từng dòng, phần lệch dồn vào dòng cuối (`item_wise_tax_detail` gộp theo
  mã hàng nên không dùng được khi hai dòng cùng mã).
- Tách một dòng thành nhiều mảnh không làm lệch tiền: mảnh cuối của một dòng lấy
  đúng phần tiền còn lại thay vì tự tính tỉ lệ.
"""

from frappe.utils import flt, getdate

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


def ghep(ban, mua, du_phong=(), ty_le=None):
	"""Ghép dòng bán với dòng PI, tiêu dần số lượng. Trả `[{"ban", "mua" | None, "tang"?}]`.

	Ba lượt, mỗi lượt chạy hết mọi dòng bán rồi mới tới lượt sau, kẻo một dòng ghép lỏng
	giành mất PI mà một dòng bán sau với tới được bằng liên kết chặt hơn:

	1. Theo chuỗi: dòng PI cùng `so_detail` (`mua`), theo thứ tự.
	2. Trong cặp SO→PO (`tang=2`): dòng `du_phong` cùng `item_code` mà PO của nó có dòng
	   lập từ đơn bán của dòng bán (`sales_order` thuộc `so_cua_po`) — dòng hàng thêm tay
	   hoặc sửa trong PO lập từ SO, hoặc SO có hai dòng cùng mã. Có chứng từ nối nên không chặn theo
	   tỷ lệ giá; lệch thì `danh_gia` gắn cờ. Ưu tiên dòng cùng số lượng, rồi giá, rồi ngày.
	3. Theo mã hàng (`tang=3`, `theo_ma=True`): phần còn thiếu ghép với dòng `du_phong`
	   bất kỳ cùng `item_code`. Dòng PI có tỷ lệ giá (theo đơn vị kho) ngoài
	   `KHOANG_TY_LE_DU_PHONG` lần `ty_le` không được ghép: không có chứng từ nào nối hai
	   bên, chênh gấp chục lần là sai ĐVT chứ không phải lệch giá.

	Lượt 2 và 3 tính SL theo đơn vị kho (`conversion_factor`), vì NCC có thể xuất theo hộp
	còn bán theo test; mỗi bên cắt theo ĐVT trên hoá đơn của mình.

	`ban` đã sắp theo thời gian; dòng `trong_ky=False` (hoá đơn bán kỳ trước, hoặc của
	khách khác cùng mã hàng) chỉ tiêu số lượng PI chứ không xuất ra.
	"""
	ty_le = flt(ty_le) or TY_LE_HOP_DONG
	hang_doi = {so: [_con_lai(d) for d in ds] for so, ds in mua.items()}
	viec = []
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
		viec.append((b, con, manh))

	kho = {}
	for p in du_phong:
		kho.setdefault(p.get("item_code"), []).append(_con_lai(p))
	for b, con, manh in viec:
		so = b.get("sales_order")
		if so:
			ung_vien = [p for p in kho.get(b.get("item_code"), ()) if so in (p["goc"].get("so_cua_po") or ())]
			_tieu(b, con, manh, ung_vien, lambda p: _uu_tien_cap(b, con, p, ty_le), {"tang": 2})
	for b, con, manh in viec:
		ung_vien = [p for p in kho.get(b.get("item_code"), ()) if _hop_ty_le(b, p["goc"], ty_le)]
		_tieu(b, con, manh, ung_vien, lambda p: _uu_tien(b, p["goc"], ty_le), {"tang": 3, "theo_ma": True})

	kq = []
	for b, con, manh in viec:
		if not manh or abs(con["sl"]) > _EPS:
			manh.append({"ban": _cat(con, con["sl"]) if manh else {**b}, "mua": None})
		if b.get("trong_ky", True):
			kq.extend(manh)
	return kq


def _tieu(b, con, manh, ung_vien, khoa, nhan):
	"""Lượt 2/3: lấy phần SL còn thiếu của dòng bán từ `ung_vien`, theo thứ tự `khoa`."""
	if con["sl"] <= _EPS or b.get("is_return") or not b.get("item_code"):
		return
	hs_ban = _he_so(b)
	for p in sorted(ung_vien, key=khoa):
		if con["sl"] <= _EPS:
			break
		if p["sl"] > _EPS:
			hs_mua = _he_so(p["goc"])
			sl_kho = min(con["sl"] * hs_ban, p["sl"] * hs_mua)
			manh.append({"ban": _cat(con, sl_kho / hs_ban), "mua": _cat(p, sl_kho / hs_mua), **nhan})


def _he_so(d):
	return flt(d.get("conversion_factor")) or 1


def _don_gia(d):
	"""Đơn giá theo đơn vị kho."""
	sl = flt(d.get("sl") or d.get("qty"))
	gia = flt(d.get("net_rate")) or (flt(d.get("thanh_tien")) / sl if sl else 0)
	return gia / _he_so(d)


def _ty_le(b, p):
	gia_mua = _don_gia(p)
	return _don_gia(b) / gia_mua if gia_mua else None


def _hop_ty_le(b, p, ty_le):
	r = _ty_le(b, p)
	if r is None:
		return not _don_gia(b)
	return KHOANG_TY_LE_DU_PHONG[0] <= r / ty_le <= KHOANG_TY_LE_DU_PHONG[1]


def _ngay(d):
	ngay = d.get("bill_date") or d.get("posting_date")
	return getdate(ngay) if ngay else None


def _uu_tien(b, p, ty_le):
	"""Khoá xếp dòng PI dự phòng cho dòng bán `b`: HĐ mua ngày trước HĐ bán trước, rồi tỷ
	lệ giá gần `ty_le` nhất (trong dung sai coi như bằng nhau), rồi ngày gần HĐ bán nhất.

	Ngày xếp trên giá: nếu giá đứng trước, một HĐ bán tháng 9 sẽ lấy PI tháng 10 đúng giá
	thay cho PI tháng 8 lệch giá chút ít, để HĐ bán tháng 10 thiếu đầu vào (dữ liệu prod,
	mã AH-M53D-DIL). Lệch giá trong khoảng cho phép vẫn ghép và báo "Lệch giá"."""
	r = _ty_le(b, p)
	lech = abs(r - ty_le) if r is not None else 0
	if lech <= DUNG_SAI_TY_LE + _EPS:
		lech = 0
	ngay_ban, ngay_mua = _ngay(b), _ngay(p)
	if ngay_ban and ngay_mua:
		sau, cach = ngay_mua > ngay_ban, abs((ngay_ban - ngay_mua).days)
	else:
		sau, cach = False, 0
	return (sau, lech, cach, ngay_mua or getdate("1900-01-01"), p.get("parent") or "", p.get("idx") or 0)


def _uu_tien_cap(b, con, p, ty_le):
	"""Khoá xếp dòng PI trong cặp SO→PO: cùng số lượng (đơn vị kho) với phần còn thiếu của
	dòng bán trước, rồi tỷ lệ giá gần `ty_le` nhất, rồi ngày như `_uu_tien`."""
	lech_sl = abs(con["sl"] * _he_so(b) - p["sl"] * _he_so(p["goc"])) > _EPS
	sau, lech, *con_lai = _uu_tien(b, p["goc"], ty_le)
	return (lech_sl, lech, sau, *con_lai)


# Hợp đồng Himedic: giá bán = giá mua x 1,01. Lệch quá dung sai thì gắn cờ.
TY_LE_HOP_DONG = 1.01
DUNG_SAI_TY_LE = 0.0005
# Ghép theo mã hàng chỉ nhận dòng PI có tỷ lệ giá trong khoảng này (x `ty_le`).
KHOANG_TY_LE_DU_PHONG = (0.5, 2)

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

	Mảnh đã ghép luôn có SL bán = SL mua theo đơn vị kho, nên lệch số lượng chỉ còn hiện
	ra dưới dạng phần "Thiếu đầu vào". Hai bên khác ĐVT mà cùng đơn vị kho thì so giá
	theo đơn vị kho và ghi chú cách quy đổi; khác cả đơn vị kho thì không so được.
	Hai bên cùng 0 đồng (hàng tặng) không tính là lệch giá.
	"""
	if r.get("tra_hang"):
		r["trang_thai"] = TRA_HANG
		return r
	if not r.get("purchase_invoice"):
		r["trang_thai"] = THIEU_DAU_VAO
		return r
	hs_ban, hs_mua = flt(r.get("_he_so_ban")) or 1, flt(r.get("_he_so_mua")) or 1
	gia_ban, gia_mua = flt(r.get("don_gia_ban")) / hs_ban, flt(r.get("don_gia_mua")) / hs_mua
	r["ty_le_gia"] = flt(gia_ban / gia_mua, 6) if gia_mua else None
	r["chenh_lech_pt"] = flt((r["ty_le_gia"] - 1) * 100, 4) if r["ty_le_gia"] else None
	r["chenh_lech_tien"] = flt(flt(r.get("thanh_tien_ban")) - flt(r.get("thanh_tien_mua")), 0)
	lech = []
	if not gia_ban and not gia_mua:
		r.setdefault("_ghi_chu", []).append("Hàng 0 đồng")
	elif r["ty_le_gia"] is None or abs(r["ty_le_gia"] - flt(ty_le)) > DUNG_SAI_TY_LE + _EPS:
		lech.append(LECH_GIA)
	if flt(r.get("thue_suat_ban")) != flt(r.get("thue_suat_mua")):
		lech.append(LECH_THUE)
	dvt_ban, dvt_mua = r.get("dvt_ban") or "", r.get("dvt_mua") or ""
	if dvt_ban != dvt_mua:
		kho_ban, kho_mua = r.get("_dvt_kho_ban"), r.get("_dvt_kho_mua")
		if kho_ban and kho_ban == kho_mua:
			r.setdefault("_ghi_chu", []).append(_quy_doi(dvt_ban, hs_ban, dvt_mua, hs_mua, kho_ban))
		else:
			lech.append(LECH_DVT)
	r["trang_thai"] = ", ".join(lech) or KHOP
	return r


def _quy_doi(dvt_ban, hs_ban, dvt_mua, hs_mua, dvt_kho):
	vd = [
		f"1 {dvt} = {hs:g} {dvt_kho}" for dvt, hs in ((dvt_mua, hs_mua), (dvt_ban, hs_ban)) if dvt != dvt_kho
	]
	return "Quy đổi " + ", ".join(vd)


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
	theo_ma = [r for r in data if r.get("theo_ma")]
	theo_cap = [r for r in data if r.get("theo_cap")]
	tong["tom_tat"] = {
		"so_dong": len(data),
		"so_hd_ban": len({r["sales_invoice"] for r in data if r.get("sales_invoice")}),
		"so_hd_mua": len({r["purchase_invoice"] for r in data if r.get("purchase_invoice")}),
		"so_dong_lech": sum(1 for r in khop if r.get("trang_thai") != KHOP),
		"dem": dem,
		"doanh_thu_co_dau_vao": flt(ban_khop, 0),
		"doanh_thu_thieu_dau_vao": flt(sum(flt(r.get("thanh_tien_ban")) for r in thieu), 0),
		"so_dong_theo_ma": len(theo_ma),
		"doanh_thu_theo_ma": flt(sum(flt(r.get("thanh_tien_ban")) for r in theo_ma), 0),
		"so_dong_theo_cap": len(theo_cap),
		"doanh_thu_theo_cap": flt(sum(flt(r.get("thanh_tien_ban")) for r in theo_cap), 0),
	}
	return tong

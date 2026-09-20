"""Xếp hàng BẮT BUỘC đúng ô in trên tem lô (chủ đầu tư, 19/09/2026).

Lời chủ đầu tư: "vị trí phải bằng đúng trên tem, nếu không sẽ không cho xếp hàng
vào vị trí". Chốt thêm cùng ngày: áp dụng cho MỌI lần xếp/chuyển (không chỉ hàng
mới về), tem không có ô hoặc ô trên tem hỏng thì BẮT IN LẠI TEM, và KHÔNG AI được
vượt — kể cả form trên máy tính. Thay quyết định 17/09 ("cho chuyển ô, quét lại
để xác nhận").

Vì sao: tem dán trên thùng là thứ người đi lấy hàng đọc. Sổ vị trí nói một ô,
tem nói một ô khác, thì một trong hai đang nói dối — và tổng tồn vẫn khớp nên
đối soát không bao giờ bắt được.

File này là NGUỒN SỰ THẬT DUY NHẤT của câu hỏi "xếp lô này vào ô kia có được
không": `LocationTransfer.validate` (chặn thật), trang PDA và ô quét trên form
(báo sớm) đều gọi `kiem_o_tem`. Hai bản luật là hai màn hình nói ngược nhau.

Đổi chỗ để hàng đi qua `doi_o_tren_tem` — đường DUY NHẤT sửa ô trên tem một khi
đã có (`nhap_lo.dat_o_in_tem` vẫn bất biến: chỉ đặt khi còn trống). Đổi ô đã có
là quyền trưởng kho; thủ kho tự đổi được thì luật chặn không còn nghĩa lý gì.

Hàng KHÔNG quản lý lô không có tem lô → không có ô nào để so → không kiểm.
"""

import frappe
from frappe import _

from erpnext.vi_tri_kho.vitri.cay import nhanh_bi_tat
from erpnext.vi_tri_kho.vitri.kho import kho_co_quan_ly_vi_tri
from erpnext.vi_tri_kho.vitri.nhat_ky_loi import cat_tieu_de

# Đặt ô cho lô CHƯA có ô: việc hằng ngày của thủ kho (cùng bộ `nhap_lo`).
VAI_TRO_DAT_O = {"System Manager", "Stock Manager", "Stock User"}
# Đổi ô của lô ĐÃ có ô: chỉ trưởng kho.
VAI_TRO_DOI_O = {"System Manager", "Stock Manager"}

# Cờ TRONG TIẾN TRÌNH (không đặt được qua HTTP), chỉ bộ test dùng để dựng tồn
# ở nhiều ô cho các bài không nói về luật này (FEFO, lấy hàng...). Không đoạn
# mã nghiệp vụ nào được đặt cờ này — đặt là mở cửa sau cho đúng thứ chủ đầu tư
# cấm.
CO_BO_KIEM_TEST = "vi_tri_kho_bo_kiem_o_tem"


def _ly_do_o_khong_dung_duoc(o: str, vat_tu: str, kho: str | None) -> str | None:
	"""Vì sao KHÔNG xếp `vat_tu` vào `o` được — `None` nếu được.

	Cùng bốn điều kiện `goi_y.goi_y_o` dùng để coi "tem còn dùng được" (ô lá
	thật, không phải ô Chưa xếp, không dưới nhánh ngừng dùng, chưa bị mặt hàng
	KHÁC chiếm), cộng điều kiện đúng kho. KHÔNG đòi ô nằm trong vùng gán cố định:
	tem là sự thật, vùng gán chỉ là căn cứ gợi ý lúc in.
	"""
	sl = frappe.db.get_value(
		"Storage Location", o, ["name", "kho", "is_group", "la_o_chua_xep"], as_dict=True
	)
	if not sl:
		return _("ô {0} không còn tồn tại").format(o)
	if kho and sl.kho != kho:
		return _("ô {0} thuộc kho {1}, không phải kho {2}").format(o, sl.kho, kho)
	if sl.is_group:
		return _("{0} là nút nhóm, không chứa hàng được").format(o)
	if sl.la_o_chua_xep:
		return _("{0} là ô Chưa xếp, không phải chỗ để hàng").format(o)
	nut_tat = nhanh_bi_tat(o)
	if nut_tat:
		return _("ô {0} đang Ngừng dùng (vì {1})").format(o, nut_tat)
	khac = frappe.db.sql(
		"""
		select lb.vat_tu from `tabLocation Balance` lb
		where lb.o = %(o)s and lb.vat_tu != %(vat_tu)s and lb.so_luong != 0
		limit 1
		""",
		{"o": o, "vat_tu": vat_tu},
	)
	if khac:
		return _("ô {0} đang chứa mặt hàng khác ({1})").format(o, khac[0][0])
	return None


def kiem_o_tem(vat_tu: str, so_lo: str | None, kho: str | None = None) -> dict:
	"""Ô trên tem của lô, và lỗi nếu KHÔNG xếp vào đó được.

	`{"o": ô trên tem hoặc None, "ma_in_nhan": ..., "loi": câu báo hoặc None,
	"kiem": có áp luật không}`. `kiem = False` cho hàng không lô (không có tem
	lô nào để so).
	"""
	if not so_lo:
		return {"o": None, "ma_in_nhan": None, "loi": None, "kiem": False, "chua_co_o": False}
	o = frappe.db.get_value("Batch", so_lo, "custom_o_in_tem")
	if not o:
		return {
			"o": None,
			"ma_in_nhan": None,
			"kiem": True,
			# Trang PDA hiện nút "Đặt ô trên tem" ĐÚNG ở ca này (lô chưa có ô —
			# thủ kho tự đặt được). Ô trên tem HỎNG là ca khác: đổi ô là quyền
			# trưởng kho, không có nút trên PDA.
			"chua_co_o": True,
			# Câu này hiện ở CẢ trang PDA (có sẵn nút "Đặt ô trên tem" ngay dưới)
			# lẫn form máy tính (phải tự mở lô) — nên không chỉ đường theo một
			# màn hình cụ thể.
			"loi": _(
				"Lô {0} chưa có ô trên tem — đặt ô trên tem, in lại tem và dán lên thùng, "
				"rồi mới xếp được."
			).format(so_lo),
		}
	ly_do = _ly_do_o_khong_dung_duoc(o, vat_tu, kho)
	return {
		"o": o,
		"ma_in_nhan": _nhan(o),
		"kiem": True,
		"chua_co_o": False,
		"loi": _(
			"Ô trên tem lô {0} không dùng được nữa: {1}. Trưởng kho mở lô, bấm \"Đổi ô trên "
			"tem\" rồi in lại tem."
		).format(so_lo, ly_do)
		if ly_do
		else None,
	}


def chan_neu_sai_o(vat_tu: str, so_lo: str | None, kho: str, den_o: str, tien_to: str = "") -> None:
	"""Ném lỗi nếu xếp (`vat_tu`, `so_lo`) vào `den_o` trái luật tem."""
	if frappe.flags.get(CO_BO_KIEM_TEST):
		return
	t = kiem_o_tem(vat_tu, so_lo, kho)
	if not t["kiem"]:
		return
	if t["loi"]:
		frappe.throw(f"{tien_to}{t['loi']}", title=_("Không xếp được"))
	if den_o != t["o"]:
		frappe.throw(
			_("{0}Ô {1} không phải ô in trên tem lô {2}. Tem ghi ô {3} — xếp đúng ô đó.").format(
				tien_to,
				frappe.db.get_value("Storage Location", den_o, "ma_in_nhan") or den_o,
				so_lo,
				t["ma_in_nhan"] or t["o"],
			),
			title=_("Sai ô"),
		)


@frappe.whitelist()
def thong_tin_o_tem(so_lo: str) -> dict:
	"""Cho nút trên form Lô: ô hiện tại, ô gợi ý, và người xem được làm gì.

	Quyền theo VAI TRÒ KHO, không theo quyền đọc `Batch`: DocPerm gốc của
	`Batch` chỉ có Item Manager — kiểm `check_permission("read")` thì chính thủ
	kho/trưởng kho, những người luật này nhắm tới, bị khoá ngoài (đo 19/09/2026).
	"""
	vai_tro = set(frappe.get_roles())
	if not vai_tro & (VAI_TRO_DAT_O | {"Item Manager"}):
		frappe.throw(_("Bạn không có quyền xem ô trên tem lô."), frappe.PermissionError)
	lo = frappe.get_doc("Batch", so_lo)
	o_hien = lo.get("custom_o_in_tem")
	kho = _kho_cua_lo(lo)
	goi_y = None
	if kho:
		from erpnext.vi_tri_kho.vitri.goi_y import goi_y_o

		try:
			goi_y = goi_y_o(lo.item, kho, None)[0]
		except Exception:
			goi_y = None
	return {
		"o": o_hien,
		"kho": kho,
		"goi_y": goi_y,
		"duoc_doi": bool(vai_tro & (VAI_TRO_DOI_O if o_hien else VAI_TRO_DAT_O)),
		"loi": kiem_o_tem(lo.item, lo.name, kho)["loi"] if o_hien else None,
	}


def _kho_cua_lo(lo) -> str | None:
	from erpnext.vi_tri_kho.vitri.nhap_lo import _kho_cua_lo as kho_goc

	kho = kho_goc(lo)
	if kho:
		return kho
	# Lô đã nằm trong sổ vị trí ở đúng một kho quản lý vị trí: lấy kho đó.
	ds = frappe.get_all(
		"Location Balance", filters={"so_lo": lo.name, "so_luong": ["!=", 0]}, pluck="kho", distinct=True
	)
	return ds[0] if len(ds) == 1 else None


@frappe.whitelist()
def doi_o_tren_tem(so_lo: str, o_moi: str, ly_do: str | None = None) -> dict:
	"""Đặt (lô chưa có ô) hoặc đổi (lô đã có ô) ô in trên tem lô.

	Chưa có ô: thủ kho làm được. Đã có ô: chỉ trưởng kho. Ô mới phải xếp được
	(cùng luật `kiem_o_tem`) và thuộc kho đang quản lý vị trí. Mỗi lần đặt/đổi
	ghi một dòng bình luận trên lô — ai, lúc nào, từ ô nào sang ô nào, vì sao —
	vì tờ tem cũ có thể còn dán ngoài kệ.

	Quyền theo vai trò kho (xem `thong_tin_o_tem` vì sao không theo DocPerm
	của `Batch`).
	"""
	lo = frappe.get_doc("Batch", so_lo)
	o_cu = lo.get("custom_o_in_tem")
	vai_tro = set(frappe.get_roles())
	if not vai_tro & (VAI_TRO_DOI_O if o_cu else VAI_TRO_DAT_O):
		frappe.throw(
			_("Chỉ trưởng kho (Stock Manager) được đổi ô đã in trên tem lô.")
			if o_cu
			else _("Bạn không có quyền đặt ô trên tem lô."),
			frappe.PermissionError,
		)
	if o_moi == o_cu:
		frappe.throw(_("Ô mới trùng ô đang in trên tem."))
	kho = frappe.db.get_value("Storage Location", o_moi, "kho")
	if not kho or not kho_co_quan_ly_vi_tri(kho):
		frappe.throw(_("Ô {0} không thuộc kho nào đang quản lý vị trí.").format(o_moi))
	ly_do_hong = _ly_do_o_khong_dung_duoc(o_moi, lo.item, kho)
	if ly_do_hong:
		frappe.throw(_("Không đặt ô {0} lên tem được: {1}.").format(o_moi, ly_do_hong))

	frappe.db.set_value("Batch", so_lo, "custom_o_in_tem", o_moi)
	if o_cu:
		cau = _("Đổi ô trên tem: {0} → {1}.").format(_nhan(o_cu), _nhan(o_moi))
	else:
		cau = _("Đặt ô trên tem: {0}.").format(_nhan(o_moi))
	if ly_do:
		cau += " " + _("Lý do: {0}").format(frappe.utils.escape_html(ly_do))
	lo.add_comment("Comment", cau + " " + _("Nhớ in lại tem và dán thay tem cũ."))
	return {"o": o_moi, "ma_in_nhan": _nhan(o_moi), "o_cu": o_cu}


def _nhan(o: str | None) -> str | None:
	return (frappe.db.get_value("Storage Location", o, "ma_in_nhan") or o) if o else None


# ---------------------------------------------------------------------------
# Đặt ô hàng loạt (chủ đầu tư duyệt 20/09/2026).
#
# Luật "chỉ xếp vào ô trên tem" khoá cứng mọi lô chưa có ô — trên site thử là 60
# lô đang có tồn. Đặt tay từng lô qua form Lô là 60 lần mở form. Hai hàm dưới
# đây cho màn hình `dat-o-hang-loat` làm một lượt.
#
# CHỈ ĐẶT cho lô CHƯA có ô. Không đổi ô đã có: một màn hình đổi hàng loạt là
# đúng cái cửa sau mà luật này sinh ra để đóng (và đổi ô là quyền trưởng kho,
# từng lô một, có lý do — xem `doi_o_tren_tem`).
# ---------------------------------------------------------------------------


@frappe.whitelist()
def lo_chua_co_o(kho: str) -> list[dict]:
	"""Các lô ĐANG CÓ TỒN trong `kho` mà chưa có ô trên tem, kèm ô đề xuất.

	Ô đề xuất lấy từ `goi_y.goi_y_o` — đúng hàm đang dùng lúc in tem, nên màn
	hình này và con tem không bao giờ nói hai ô khác nhau. Mặt hàng chưa gán vị
	trí cố định thì để trống kèm lý do; người dùng tự chọn ô.

	Ruling N (khuôn chung của module): `goi_y_o` ném lỗi cho MỘT mặt hàng dữ
	liệu hỏng thì nuốt lỗi ở đúng dòng đó, không để sập cả danh sách.
	"""
	_kiem_quyen_dat_o()
	if not kho_co_quan_ly_vi_tri(kho):
		frappe.throw(_("Kho {0} chưa bật quản lý vị trí.").format(kho))

	dong = frappe.db.sql(
		"""
		select lb.so_lo as so_lo, lb.vat_tu as vat_tu, sum(lb.so_luong) as ton,
		       group_concat(distinct sl.ma_in_nhan order by sl.lft) as dang_o
		from `tabLocation Balance` lb
		join `tabStorage Location` sl on sl.name = lb.o
		join `tabBatch` b on b.name = lb.so_lo
		where lb.kho = %(kho)s and lb.so_luong > 0 and ifnull(lb.so_lo, '') != ''
		  and ifnull(b.custom_o_in_tem, '') = ''
		group by lb.so_lo, lb.vat_tu
		order by lb.vat_tu asc, lb.so_lo asc
		""",
		{"kho": kho},
		as_dict=True,
	)

	from erpnext.vi_tri_kho.vitri.goi_y import goi_y_o

	bo_nho: dict[tuple, tuple] = {}
	for d in dong:
		khoa = (d.vat_tu, d.so_lo)
		if khoa not in bo_nho:
			try:
				o, ly_do, _hong = goi_y_o(d.vat_tu, kho, d.so_lo)
			except Exception:
				frappe.log_error(
					title=cat_tieu_de(f"vi_tri_kho: lo_chua_co_o goi_y_o loi ({d.vat_tu}/{d.so_lo})")
				)
				o, ly_do = None, _("không gợi ý được cho {0} — xem Error Log").format(d.vat_tu)
			bo_nho[khoa] = (o, ly_do)
		d["o_de_xuat"], d["ly_do"] = bo_nho[khoa]
		d["ma_in_nhan_de_xuat"] = _nhan(d["o_de_xuat"])
		d["ten_hang"] = frappe.get_cached_value("Item", d.vat_tu, "item_name")
		d["hsd"] = frappe.db.get_value("Batch", d.so_lo, "expiry_date")
	return dong


@frappe.whitelist()
def dat_o_hang_loat(dong) -> dict:
	"""Đặt ô trên tem cho nhiều lô. `dong` = [{"so_lo": ..., "o": ...}, ...].

	Mỗi lô một SAVEPOINT riêng: một lô hỏng (ô đã bị chiếm trong lúc người dùng
	còn đang nhìn màn hình) không được kéo theo các lô đã đặt xong — người dùng
	sẽ phải làm lại cả loạt mà không biết dòng nào đã chạy.
	"""
	_kiem_quyen_dat_o()
	if isinstance(dong, str):
		dong = frappe.parse_json(dong)
	xong, loi = [], []
	for i, d in enumerate(dong or []):
		so_lo = (d.get("so_lo") or "").strip()
		o = (d.get("o") or "").strip()
		if not so_lo or not o:
			loi.append({"so_lo": so_lo, "loi": _("chưa chọn ô")})
			continue
		diem = f"vi_tri_kho_dat_o_hang_loat_{i}"
		frappe.db.savepoint(diem)
		try:
			if frappe.db.get_value("Batch", so_lo, "custom_o_in_tem"):
				# Người khác vừa đặt trong lúc màn hình này đang mở. Không ghi đè:
				# đổi ô đã có là việc của trưởng kho, từng lô, có lý do.
				frappe.throw(_("lô đã có ô trên tem (người khác vừa đặt) — nạp lại danh sách"))
			doi_o_tren_tem(so_lo, o)
			xong.append({"so_lo": so_lo, "o": o, "ma_in_nhan": _nhan(o)})
		except Exception as e:
			frappe.db.rollback(save_point=diem)
			loi.append({"so_lo": so_lo, "loi": str(e)})
			frappe.clear_last_message()
	return {"xong": xong, "loi": loi}


def _kiem_quyen_dat_o():
	if not set(frappe.get_roles()) & VAI_TRO_DAT_O:
		frappe.throw(_("Bạn không có quyền đặt ô trên tem lô."), frappe.PermissionError)

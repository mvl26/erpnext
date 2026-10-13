"""Lấy danh sách hàng đang nằm ở ô "Chưa xếp vị trí" để đổ vào phiếu xếp.

CÙNG NGUỒN DỮ LIỆU với báo cáo *Hàng chưa xếp vị trí*
(`report/hang_chua_xep_vi_tri/`) — cùng điều kiện `la_o_chua_xep = 1` và
`so_luong != 0`. Hai chỗ mà nói khác nhau thì thủ kho nhìn báo cáo rồi mở
phiếu, thấy lệch, và mất tin vào cả hai.
"""

import frappe
from frappe import _
from frappe.utils import flt, nowdate

from erpnext.warehouse_operations.vitri.goi_y import goi_y_o
from erpnext.warehouse_operations.vitri.o_tem import kiem_o_tem
from erpnext.warehouse_operations.vitri.nhat_ky_loi import cat_tieu_de
from erpnext.warehouse_operations.vitri.so import ton_o

# Giống `tem.py`: thủ kho phải tự làm được, đây là việc hằng ngày chứ không
# phải thao tác thiết lập. Khác `bat_kho.py` (sinh ô, bật kho) vốn chỉ mở
# cho quản lý.
VAI_TRO_DUOC_XEP = {"System Manager", "Stock Manager", "Stock User"}


def _kiem_tra_quyen():
	"""`@frappe.whitelist()` một mình chỉ chặn khách vãng lai.

	Danh sách này lộ ra toàn bộ hàng tồn đang chờ xếp của kho, nên đăng nhập
	hợp lệ không phải điều kiện đủ. `Website User` (khách hàng cổng) không có
	vai trò nào ở đây nên bị chặn.
	"""
	if not VAI_TRO_DUOC_XEP & set(frappe.get_roles()):
		frappe.throw(_("Bạn không có quyền xem hàng chưa xếp vị trí."), frappe.PermissionError)


@frappe.whitelist()
def hang_chua_xep(kho: str) -> list[dict]:
	"""Các dòng tồn ở ô "Chưa xếp vị trí" của `kho`, dạng dòng phiếu sẵn.

	`den_o` được ĐIỀN SẴN từ `goi_y.goi_y_o()` kể từ 15/09/2026. Trước đó nó cố
	ý để trống, vì căn cứ duy nhất khi ấy là `suc_chua` (= 0 trên cả 214 ô) và
	gợi ý sai thì thủ kho tin theo rồi xếp nhầm. Căn cứ nay khác hẳn: mặt hàng
	có vị trí cố định, nên "xếp đâu" trả lời được mà không cần sức chứa.

	Mặt hàng CHƯA gán vẫn để `den_o` trống — không đoán. `ly_do_goi_y` luôn có
	giá trị để màn hình nói được vì sao trống.

	Gợi ý KHÔNG chặn và KHÔNG ghi đè: thủ kho đứng trước kệ biết những thứ hệ
	không biết.

	Ruling N (vòng sửa 1, review điều phối): một bản gán hỏng toạ độ (`lft`/
	`rgt` = 0, xem `goi_y_o`) khiến `goi_y_o` NÉM LỖI cho ĐÚNG một mặt hàng.
	Nuốt lỗi đó ở đây — không để nó văng ra khỏi cả vòng lặp — vì cái giá
	ngược lại nặng hơn nhiều: một mặt hàng lỗi dữ liệu sẽ làm SẬP RPC này cho
	CẢ kho, nút "Lấy hàng chưa xếp" không mở nổi cho bất cứ ai, trong khi hàng
	của những mặt hàng lành vẫn đang chờ ở `ZZZ-CHUA-XEP`. Đó là hình dạng
	chặn nặng hơn hẳn tinh thần "gợi ý không chặn" ở trên. Lỗi thật không mất
	— xem Error Log tiêu đề `vi_tri_kho: hang_chua_xep goi_y_o loi`.

	Khối C §8 (Task 4): bộ đệm `goi_y_o` giờ khoá theo CẶP (mặt hàng, lô),
	không còn khoá theo riêng mặt hàng. Trước §8, gợi ý chỉ phụ thuộc vị trí
	gán — thứ CHUNG cho mọi lô của một mặt hàng — nên khoá theo mặt hàng vẫn
	đúng. Từ §8, `goi_y_o` còn nhận `so_lo` và ưu tiên đúng ô đã in trên tem
	của LÔ đó (`Batch.custom_o_in_tem`, riêng từng lô). Giữ khoá cũ thì lô
	thứ hai của cùng một mặt hàng nhận lại gợi ý của lô thứ nhất, và tem của
	nó nói dối.

	`tem_hong` (vòng sửa 2, điều phối): `goi_y_o` giờ trả BỘ BA, phần tử thứ
	ba là cờ báo "lô này có tem nhưng ô ghi trên tem không còn dùng được".
	Đổ thẳng cờ đó vào từng dòng — KHÔNG suy nó từ chuỗi `ly_do_goi_y` (đã có
	một bản làm vậy bằng `includes("tem")` ở `location_transfer.js`, và nó
	gộp nhầm luôn cả case tem ĐÚNG, vì chuỗi "theo ô đã in trên tem của lô…"
	cũng chứa chữ "tem"). Ở nhánh nuốt lỗi (`except Exception`) bên dưới,
	`tem_hong` luôn là `False`: không biết được `goi_y_o` đã đi tới đâu trước
	khi ném lỗi thì không được khẳng định gì về tem.
	"""
	_kiem_tra_quyen()
	dong = frappe.db.sql(
		"""
		select lb.vat_tu as vat_tu, nullif(lb.so_lo, '') as so_lo,
		       lb.o as tu_o, lb.so_luong as so_luong
		from `tabLocation Balance` lb
		join `tabStorage Location` sl on sl.name = lb.o
		where sl.la_o_chua_xep = 1 and lb.kho = %(kho)s and lb.so_luong != 0
		order by lb.vat_tu asc, lb.so_lo asc
		""",
		{"kho": kho},
		as_dict=True,
	)

	# Một lời gọi `goi_y_o` cho mỗi (MẶT HÀNG, LÔ).
	#
	# Trước khối C khoá đệm chỉ là `vat_tu`, vì gợi ý khi ấy chỉ phụ thuộc vị trí
	# gán — thứ chung cho mọi lô của mặt hàng. Từ khối C §8, gợi ý còn phụ thuộc
	# `Batch.custom_o_in_tem`, vốn RIÊNG từng lô. Giữ khoá cũ thì lô thứ hai
	# nhận gợi ý của lô thứ nhất và tem của nó nói dối.
	bo_nho: dict[tuple, tuple] = {}
	for d in dong:
		khoa = (d.vat_tu, d.so_lo)
		if khoa not in bo_nho:
			try:
				bo_nho[khoa] = goi_y_o(d.vat_tu, kho, d.so_lo)
			except Exception:
				# Ruling N: KHÔNG để lỗi của MỘT (mặt hàng, lô) làm sập danh sách
				# của CẢ kho — xem lý do đầy đủ ở docstring hàm này. `frappe.log_error`
				# (không truyền `message`) tự chụp traceback hiện tại, giữ dấu vết
				# thật trong Error Log để người vận hành đi sửa dữ liệu gán, thay
				# vì lỗi biến mất lặng lẽ. Tiêu đề mang cả số lô — Task 4 tách
				# khoá theo lô nên một lô lỗi (vd. tem trỏ vào dữ liệu hỏng) không
				# còn định danh đủ chỉ bằng mặt hàng.
				#
				# `cat_tieu_de` BẮT BUỘC (review điều phối, vòng sửa 2/5): `title`
				# đi vào `Error Log.method` — cột `Data(140)`. `Item.name`/số lô
				# có thể dài tới sát trần đó MỘT MÌNH, và đây là MÀN HÌNH THỦ KHO
				# DÙNG HẰNG NGÀY — không cắt thì `log_error()` này (đang NẰM
				# TRONG khối `except` dựng lên để "một dòng hỏng không sập cả
				# danh sách") tự ném `CharacterLengthExceededError`, và lỗi đó
				# văng ra NGOÀI khối `except`, làm sập đúng thứ khối này sinh ra
				# để chặn. Xem lý lẽ đầy đủ ở `nhat_ky_loi.py`.
				frappe.log_error(
					title=cat_tieu_de(
						f"vi_tri_kho: hang_chua_xep goi_y_o loi ({d.vat_tu}/{d.so_lo})"
					)
				)
				# Mục 5 (review tổng): câu cũ KHẲNG ĐỊNH đây là "lỗi dữ liệu vị
				# trí" — sai, vì `except Exception` ở trên bắt MỌI ngoại lệ,
				# kể cả một lỗi LẬP TRÌNH trong `goi_y_o` (không chỉ toạ độ
				# 0/0 của §5.1). Khẳng định nhầm nguyên nhân khiến người đọc
				# đi sửa dữ liệu trong khi thứ hỏng là mã. Câu mới chỉ nói
				# "không gợi ý được", không đoán vì sao — nhưng vẫn PHẢI giữ
				# phần phân biệt với "chưa gán" (mặt hàng đã có gán, ai đó
				# đừng tưởng nhầm là chưa gán rồi đi gán lại một gán vốn đã
				# đúng, chỉ là `goi_y_o` đang không tính được cho nó).
				bo_nho[khoa] = (
					None,
					_(
						"không gợi ý được cho {0} — xem Error Log. KHÔNG PHẢI mặt hàng "
						"chưa gán, đừng gán lại"
					).format(d.vat_tu),
					False,
				)
		d["den_o"], d["ly_do_goi_y"], d["tem_hong"] = bo_nho[khoa]
		# Luật 19/09/2026: lô CHỈ được xếp vào đúng ô in trên tem. Gợi ý khác ô
		# tem (tem hỏng, lô chưa có ô) chỉ dẫn thủ kho tới một dòng mà lúc lưu
		# sẽ bị chặn — để trống và nói thẳng phải làm gì.
		t = kiem_o_tem(d.vat_tu, d.so_lo, kho)
		if t["kiem"]:
			d["den_o"] = None if t["loi"] else t["o"]
			d["ly_do_goi_y"] = t["loi"] or _("theo ô in trên tem lô {0}").format(d.so_lo)
	return dong


# ---------------------------------------------------------------------------
# Xếp hàng trên PDA (17/09/2026)
#
# Chủ đầu tư: "giao diện xếp hàng cũng là pda … quét mã lô thì hiển thị ra mặt
# hàng và thực hiện xác nhận xếp, có thể xếp nhiều hàng trên 1 phiếu xếp".
#
# Trang `xep-hang-pda` gọi bốn hàm dưới đây. Ba quy tắc, mỗi quy tắc trả giá
# cho một kiểu mất hàng:
#
# 1. MỖI DÒNG LƯU NGAY lên một phiếu `Location Transfer` NHÁP. Không gom trong
#    bộ nhớ trình duyệt rồi gửi một lần: PDA hết pin / rớt sóng giữa ca là mất
#    hết các dòng mà thủ kho đã xếp tay ngoài kệ.
# 2. Phiếu nháp là của TỪNG NGƯỜI (`owner`) trong TỪNG KHO. Hai thủ kho cùng ca
#    không dồn dòng vào phiếu của nhau. Mở lại trang thì gặp lại đúng phiếu đó —
#    không mở phiếu mới mỗi lần, vì Stock User không có quyền XOÁ phiếu nên phiếu
#    rác sẽ nằm đó tới khi quản lý dọn.
# 3. Phép kiểm dòng (ô nhóm, nhánh ngừng dùng, sai kho, lô) là của
#    `LocationTransfer.validate` — ở đây chỉ `save()` và để nó nói. Thứ DUY NHẤT
#    kiểm thêm là "ô nguồn còn đủ hàng": controller chỉ chặn tồn âm lúc DUYỆT,
#    mà phiếu nháp thì chưa ghi sổ, nên quét một lô hai lần sẽ xếp gấp đôi số
#    đang có và chỉ nổ ở cuối ca — sau khi hàng đã nằm trên kệ.
# ---------------------------------------------------------------------------


DOCTYPE_PHIEU = "Location Transfer"
# Sai số so sánh số lượng Float (Location Balance lưu 9 chữ số thập phân).
_SAI_SO = 1e-9


def _kho_quan_ly_vi_tri() -> list[str]:
	return frappe.get_all(
		"Warehouse",
		filters={"custom_quan_ly_vi_tri": 1, "is_group": 0, "disabled": 0},
		pluck="name",
		order_by="name asc",
	)


def _phieu_nhap_cua_toi(kho: str) -> str | None:
	ten = frappe.get_all(
		DOCTYPE_PHIEU,
		filters={"docstatus": 0, "kho": kho, "owner": frappe.session.user},
		pluck="name",
		order_by="modified desc",
		limit=1,
	)
	return ten[0] if ten else None


def _mo_ta_phieu(doc) -> dict | None:
	if not doc:
		return None
	return {
		"name": doc.name,
		"kho": doc.kho,
		"dong": [
			{
				"name": d.name,
				"idx": d.idx,
				"vat_tu": d.vat_tu,
				"ten_hang": frappe.db.get_value("Item", d.vat_tu, "item_name"),
				"don_vi": frappe.db.get_value("Item", d.vat_tu, "stock_uom"),
				"so_lo": d.so_lo or None,
				"tu_o": d.tu_o,
				"tu_o_chua_xep": bool(frappe.db.get_value("Storage Location", d.tu_o, "la_o_chua_xep")),
				"den_o": d.den_o,
				"so_luong": d.so_luong,
			}
			for d in doc.items
		],
	}


def _da_len_phieu(doc, o: str, vat_tu: str, so_lo: str | None) -> float:
	"""Tổng số lượng các dòng của phiếu nháp đang lấy (vat_tu, so_lo) ra khỏi ô `o`."""
	if not doc:
		return 0.0
	return sum(
		flt(d.so_luong)
		for d in doc.items
		if d.tu_o == o and d.vat_tu == vat_tu and (d.so_lo or None) == (so_lo or None)
	)


@frappe.whitelist()
def phieu_xep_dang_lam(kho: str | None = None) -> dict:
	"""Kho để xếp + phiếu nháp đang làm dở của người dùng ở kho đó (nếu có).

	Không truyền `kho`: có đúng một kho quản lý vị trí thì chọn luôn; không thì
	lấy kho của phiếu nháp gần nhất của người dùng; vẫn không có thì để trống cho
	trang hỏi.
	"""
	_kiem_tra_quyen()
	kho_ds = _kho_quan_ly_vi_tri()
	if not kho:
		if len(kho_ds) == 1:
			kho = kho_ds[0]
		else:
			gan_nhat = frappe.get_all(
				DOCTYPE_PHIEU,
				filters={"docstatus": 0, "owner": frappe.session.user},
				pluck="kho",
				order_by="modified desc",
				limit=1,
			)
			kho = gan_nhat[0] if gan_nhat and gan_nhat[0] in kho_ds else None
	ten = _phieu_nhap_cua_toi(kho) if kho else None
	return {
		"kho_ds": kho_ds,
		"kho": kho,
		"phieu": _mo_ta_phieu(frappe.get_doc(DOCTYPE_PHIEU, ten)) if ten else None,
	}


def _mo_ta_lo(kho: str, vat_tu: str, so_lo: str | None) -> dict:
	"""Mặt hàng/lô vừa quét + các ô nguồn còn xếp được + ô gợi ý."""
	item = frappe.db.get_value("Item", vat_tu, ["item_name", "stock_uom"], as_dict=True)
	ten_phieu = _phieu_nhap_cua_toi(kho)
	phieu = frappe.get_doc(DOCTYPE_PHIEU, ten_phieu) if ten_phieu else None

	# `ifnull(so_lo,'')`: hàng không lô lưu CHUỖI RỖNG, không phải NULL — khuôn
	# `so.tong_ton_vi_tri`.
	dong_ton = frappe.db.sql(
		"""
		select lb.o as o, sl.ma_in_nhan as ma_in_nhan, sl.la_o_chua_xep as la_o_chua_xep,
			lb.so_luong as so_luong
		from `tabLocation Balance` lb
		join `tabStorage Location` sl on sl.name = lb.o
		where lb.kho = %(kho)s and lb.vat_tu = %(vat_tu)s and ifnull(lb.so_lo, '') = %(so_lo)s
			and lb.so_luong > 0
		order by sl.la_o_chua_xep desc, sl.lft asc
		""",
		{"kho": kho, "vat_tu": vat_tu, "so_lo": so_lo or ""},
		as_dict=True,
	)
	nguon = []
	for d in dong_ton:
		con = flt(d.so_luong) - _da_len_phieu(phieu, d.o, vat_tu, so_lo)
		if con <= _SAI_SO:
			continue
		nguon.append(
			{
				"o": d.o,
				"ma_in_nhan": d.ma_in_nhan,
				"la_o_chua_xep": bool(d.la_o_chua_xep),
				"con_xep_duoc": con,
			}
		)

	# Nguồn mặc định: ô Chưa xếp nếu còn hàng (việc chính của trang là XẾP hàng
	# mới về); không thì ô duy nhất đang có lô; nhiều ô thì để người dùng chọn —
	# đó là ca CHUYỂN Ô, hệ không đoán lấy từ ô nào.
	chua_xep = [d["o"] for d in nguon if d["la_o_chua_xep"]]
	if chua_xep:
		tu_o = chua_xep[0]
	elif len(nguon) == 1:
		tu_o = nguon[0]["o"]
	else:
		tu_o = None

	try:
		den_o, ly_do, tem_hong = goi_y_o(vat_tu, kho, so_lo)
	except Exception:
		# Cùng lẽ Ruling N ở `hang_chua_xep`: gợi ý hỏng không được chặn việc xếp.
		frappe.log_error(
			title=cat_tieu_de(f"vi_tri_kho: quet_de_xep goi_y_o loi ({vat_tu}/{so_lo})")
		)
		den_o, ly_do, tem_hong = None, _("không gợi ý được — xem Error Log"), False

	return {
		"loai": "lo",
		"vat_tu": vat_tu,
		"ten_hang": item.item_name if item else vat_tu,
		"don_vi": item.stock_uom if item else None,
		"so_lo": so_lo or None,
		"hsd": frappe.db.get_value("Batch", so_lo, "expiry_date") if so_lo else None,
		"nguon": nguon,
		"tu_o_mac_dinh": tu_o,
		# Ô BẮT BUỘC theo tem (luật 19/09/2026). Trang PDA chỉ cho xếp vào `o_tem.o`;
		# `o_tem.loi` khác None thì lô này chưa xếp được (chưa có ô / ô hỏng).
		"o_tem": kiem_o_tem(vat_tu, so_lo, kho),
		"goi_y": {
			"den_o": den_o,
			"ma_in_nhan": frappe.db.get_value("Storage Location", den_o, "ma_in_nhan") if den_o else None,
			"ly_do": ly_do,
			"tem_hong": bool(tem_hong),
		},
	}


@frappe.whitelist()
def quet_de_xep(kho: str, ma: str) -> dict:
	"""Nhận diện một mã quét trên trang xếp hàng.

	`loai`: `"lo"` (tem lô, hoặc mã hàng KHÔNG quản lý lô) · `"o"` (tem vị trí) ·
	`"can_quet_lo"` (mã hàng CÓ quản lý lô — không biết lô nào, không đoán) ·
	`None` (không nhận ra). Quét nhầm không bao giờ nổ — cùng lời hứa `quet.py`.
	"""
	from erpnext.stock.utils import scan_barcode
	from erpnext.warehouse_operations.vitri.quet import _tim_o

	_kiem_tra_quyen()
	ma = (ma or "").strip()
	if not ma:
		return {"loai": None}
	try:
		ket_qua = scan_barcode(ma) or {}
		if ket_qua.get("batch_no"):
			vat_tu = frappe.db.get_value("Batch", ket_qua["batch_no"], "item")
			return _mo_ta_lo(kho, vat_tu, ket_qua["batch_no"])

		vat_tu = ket_qua.get("item_code")
		if not vat_tu and not ket_qua.get("warehouse"):
			ma_o = _tim_o(ma)
			if ma_o:
				o = frappe.db.get_value(
					"Storage Location", ma_o, ["name", "ma_in_nhan", "kho", "is_group"], as_dict=True
				)
				return {
					"loai": "o",
					"ma_o": o.name,
					"ma_in_nhan": o.ma_in_nhan,
					"kho": o.kho,
					"la_nhom": bool(o.is_group),
				}
			if frappe.db.exists("Item", ma):
				vat_tu = ma

		if vat_tu:
			if frappe.db.get_value("Item", vat_tu, "has_batch_no"):
				return {
					"loai": "can_quet_lo",
					"vat_tu": vat_tu,
					"ten_hang": frappe.db.get_value("Item", vat_tu, "item_name"),
				}
			return _mo_ta_lo(kho, vat_tu, None)
	except Exception:
		frappe.log_error(title=cat_tieu_de(f"vi_tri_kho: quet_de_xep loi ({ma})"))
	return {"loai": None}


@frappe.whitelist()
def them_dong_xep(kho: str, vat_tu: str, so_lo: str | None, tu_o: str, den_o: str, so_luong) -> dict:
	"""Thêm một dòng đã xác nhận vào phiếu nháp của người dùng (tạo phiếu nếu chưa có).

	Cùng (mặt hàng, lô, từ ô, đến ô) với một dòng sẵn có thì CỘNG DỒN vào dòng
	đó — quét lại cùng một thùng lẻ vào cùng ô không nên đẻ thêm dòng.
	"""
	_kiem_tra_quyen()
	so_lo = so_lo or None
	so_luong = flt(so_luong)

	ten = _phieu_nhap_cua_toi(kho)
	if ten:
		phieu = frappe.get_doc(DOCTYPE_PHIEU, ten)
	else:
		phieu = frappe.new_doc(DOCTYPE_PHIEU)
		phieu.kho = kho
		phieu.ngay = nowdate()

	con = ton_o(tu_o, vat_tu, so_lo) - _da_len_phieu(phieu if ten else None, tu_o, vat_tu, so_lo)
	if so_luong > con + _SAI_SO:
		frappe.throw(
			_(
				"Ô {0} chỉ còn {1} của {2}{3} chưa lên phiếu — không xếp {4} được. "
				"Sửa số lượng rồi quét lại tem ô."
			).format(tu_o, flt(con, 3), vat_tu, _(" lô {0}").format(so_lo) if so_lo else "", so_luong)
		)

	trung = next(
		(
			d
			for d in phieu.items
			if d.vat_tu == vat_tu and (d.so_lo or None) == so_lo and d.tu_o == tu_o and d.den_o == den_o
		),
		None,
	)
	if trung:
		trung.so_luong = flt(trung.so_luong) + so_luong
	else:
		phieu.append(
			"items",
			{"vat_tu": vat_tu, "so_lo": so_lo, "tu_o": tu_o, "den_o": den_o, "so_luong": so_luong},
		)

	# KHÔNG `ignore_permissions`: quyền tạo/sửa phiếu là của doctype, trang PDA
	# không phải cửa sau.
	phieu.save() if ten else phieu.insert()
	return _mo_ta_phieu(phieu)


@frappe.whitelist()
def xoa_dong_xep(phieu: str, dong: str) -> dict | None:
	"""Bỏ một dòng khỏi phiếu nháp. Dòng cuối đi thì gỡ luôn phiếu nháp rỗng.

	Gỡ bằng `ignore_permissions` CHỈ cho phiếu NHÁP do CHÍNH người gọi tạo: phiếu
	phải có ít nhất một dòng (không lưu được phiếu rỗng) mà Stock User không có
	quyền xoá — không gỡ thì phiếu rỗng thành rác chỉ quản lý dọn được.
	"""
	_kiem_tra_quyen()
	doc = frappe.get_doc(DOCTYPE_PHIEU, phieu)
	if doc.docstatus != 0 or doc.owner != frappe.session.user:
		frappe.throw(_("Chỉ bỏ được dòng trên phiếu nháp của chính mình."), frappe.PermissionError)

	con_lai = [d for d in doc.items if d.name != dong]
	if not con_lai:
		frappe.delete_doc(DOCTYPE_PHIEU, doc.name, ignore_permissions=True)
		return None
	doc.set("items", con_lai)
	doc.save()
	return _mo_ta_phieu(doc)


@frappe.whitelist()
def duyet_phieu_xep(phieu: str) -> dict:
	"""Duyệt phiếu — ghi sổ vị trí. Hỏng thì phiếu nháp và các dòng còn NGUYÊN.

	Savepoint riêng quanh `submit()`: `Document.submit` ghi `docstatus = 1` xuống
	CSDL TRƯỚC khi `on_submit` chạy phép chặn tồn âm. Qua web request thì bộ xử
	lý tự rollback, nhưng gọi từ chỗ khác (test, script) thì không ai dọn — phiếu
	sẽ mang docstatus 1 mà không một dòng sổ nào. Không dựa vào người gọi.
	"""
	_kiem_tra_quyen()
	doc = frappe.get_doc(DOCTYPE_PHIEU, phieu)
	diem = "vi_tri_kho_duyet_phieu_xep_pda"
	frappe.db.savepoint(diem)
	try:
		doc.submit()
	except Exception:
		frappe.db.rollback(save_point=diem)
		raise
	return {"name": doc.name, "so_dong": len(doc.items)}

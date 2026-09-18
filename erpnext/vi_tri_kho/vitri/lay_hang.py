"""Lấy hàng: phân bổ ô cho từng dòng phiếu giao, và trang PDA quét xác nhận.

VÌ SAO CÓ FILE NÀY: trước 18/09/2026, ô lấy hàng do `fefo.chon_o_xuat()` chọn
BÊN TRONG hook, đúng lúc duyệt phiếu giao — thủ kho không có danh sách đi lấy, và
không ai đối chiếu "hệ trừ ô A" với "người thật lấy ở ô B". Hai bên lệch nhau thì
TỔNG tồn kho vẫn đúng nên `doi_soat_kho` vẫn báo khớp; sai lệch chỉ lộ ra lúc
kiểm kê thực tế, khi đã mất dấu vết.

Bảng phân bổ `Location Allocation` là thứ spec nền tảng (§4.5, §5.4) đã dành sẵn
chỗ cho từ giai đoạn 1 — file này dựng tiếp đúng thiết kế đó, không nghĩ lại.
"""

import frappe
from frappe import _
from frappe.utils import flt

from erpnext.vi_tri_kho.vitri.so import ton_o

_SAI_SO = 1e-9

TEN_BANG_PHAN_BO = "custom_phan_bo_vi_tri"

# Chỉ phiếu giao có giao diện phân bổ (spec §2). Các chứng từ khác vẫn đi đường
# cũ — hằng số ở đây để nơi đọc không phải đoán, và để mở rộng sau này là sửa
# đúng một chỗ.
CHUNG_TU_CO_PHAN_BO = ("Delivery Note",)

# Cùng bộ vai trò với `xep.py`/`quet.py` — thủ kho phải tự làm được, đây là việc
# hằng ngày.
VAI_TRO_DUOC_LAY = {"System Manager", "Stock Manager", "Stock User"}


def phan_bo_cua_dong(chung_tu_type: str, chung_tu: str, dong_hang: str, so_lo: str | None) -> list[dict]:
	"""Các dòng phân bổ của ĐÚNG (dòng hàng, lô). Không có → danh sách rỗng.

	So `so_lo` TRONG PYTHON, không đưa vào `filters`: hàng không quản lý lô lưu
	`None` ở bảng phân bổ nhưng `''` ở vài chỗ khác trong module, và một bộ lọc SQL
	so thẳng sẽ khớp 0 dòng trong im lặng — đúng kiểu hỏng mà cả module này phải
	tránh (xem `xep.py`, `quet.py`).
	"""
	if chung_tu_type not in CHUNG_TU_CO_PHAN_BO or not dong_hang:
		return []

	dong = frappe.get_all(
		"Location Allocation",
		filters={
			"parenttype": chung_tu_type,
			"parent": chung_tu,
			"parentfield": TEN_BANG_PHAN_BO,
			"dong_hang": dong_hang,
		},
		fields=["name", "o", "so_lo", "so_luong"],
		order_by="idx asc",
	)
	return [d for d in dong if (d.so_lo or None) == (so_lo or None)]


def tong_phan_bo(dong: list[dict]) -> float:
	return flt(sum(flt(d["so_luong"]) for d in dong))


def chung_tu_co_phan_bo(chung_tu_type: str, chung_tu: str) -> bool:
	"""Chứng từ này có ÍT NHẤT MỘT dòng phân bổ hay không — KHÔNG lọc theo
	(dòng hàng, lô), khác với `phan_bo_cua_dong`.

	VÒNG SỬA 1 (Critical 2, review điều phối): dùng để phân biệt hai ca mà
	`phan_bo_cua_dong` trả `[]` như nhau nhưng Ý NGHĨA khác hẳn — "chứng từ
	chưa từng qua trang Lấy hàng" (đi FEFO như cũ) khỏi "chứng từ CÓ bảng
	phân bổ nhưng không dòng nào khớp đúng (dòng hàng, lô) đang ghi" (phiếu
	amend đổi tên dòng hàng, đường mất chiều lô của `tach_theo_lo`, hoặc dòng
	Packed Item của Product Bundle) — ca sau phải CHẶN theo spec §5, không
	được âm thầm rơi về FEFO. Xem `hook_sle._phan_bo_da_khai`.
	"""
	if chung_tu_type not in CHUNG_TU_CO_PHAN_BO:
		return False
	return bool(
		frappe.db.exists(
			"Location Allocation",
			{"parenttype": chung_tu_type, "parent": chung_tu, "parentfield": TEN_BANG_PHAN_BO},
		)
	)


def kiem_phan_bo_khi_luu(doc, method=None):
	"""Lớp kiểm SỚM cho phân bổ trên chứng từ (spec §5). Gắn `doc_events` validate.

	Cho phép tổng phân bổ NHỎ HƠN số lượng dòng — đó là trạng thái "đang quét dở",
	và chặn nó ở đây là bắt thủ kho lấy xong cả phiếu trong một hơi. Phép so BẰNG
	nằm ở lúc duyệt (hook, Task 2).

	DỌN PHÂN BỔ CŨ KHI AMEND (quyết định sau review Task 2, không có trong brief
	gốc): `frappe.copy_doc` — đường amend thật cũng đi qua nó — chép bảng con
	SANG BẢN AMEND dù field có `no_copy=1` hay không (tham số mặc định của nó là
	`ignore_no_copy=True`, tức "bỏ qua cờ no_copy", nghĩa là VẪN CHÉP). Các dòng
	phân bổ chép sang đó còn giữ nguyên `dong_hang` trỏ về TÊN DÒNG HÀNG của
	phiếu GỐC, trong khi phiếu amend sinh dòng hàng MỚI (tên khác) ngay khi
	insert — nên không dòng phân bổ nào còn khớp. Bảng lại là read-only nên
	người dùng không tự xoá được: nếu không dọn ở đây, bản amend bị khoá lưu
	vĩnh viễn ngay từ lần lưu đầu tiên (vòng kiểm ở dưới sẽ luôn thấy "dòng hàng
	không thuộc phiếu này"). Về nghiệp vụ, bản amend là phiếu CHƯA ai đi lấy
	hàng lại — giữ phân bổ cũ là nói dối rằng đã lấy rồi.

	Chỉ dọn ở LẦN INSERT ĐẦU TIÊN của bản amend (`doc.is_new()` — cờ `__islocal`
	còn sống trong đúng lệnh `insert()` sinh ra bản amend, xem
	`frappe/model/document.py:insert`), KHÔNG dùng `docstatus == 0`: bản amend
	vẫn còn nháp (`docstatus == 0`) suốt quá trình thủ kho quét lại trên trang
	Lấy hàng — nếu dọn theo `docstatus` thì MỌI lần lưu nháp sau đó cũng bị dọn
	sạch, xoá luôn phân bổ vừa quét. `is_new()` chỉ đúng cho đúng một lần lưu:
	lần insert của chính bản amend.

	PHẠM VI (vòng sửa 1, Important 3): hàm này chỉ so `p.dong_hang` với tên
	các dòng `Delivery Note Item` hiện có trên CHÍNH document đang lưu — nó
	không biết gì về `Stock Ledger Entry.voucher_detail_no` lúc ghi sổ. Hai ca
	sau vẫn đi lọt qua đây (validate xanh) và CHỈ bị `hook_sle._phan_bo_da_khai`
	chặn lúc ghi sổ, không phải code chết: (1) dòng Product Bundle, nơi SLE
	của từng dòng con mang `voucher_detail_no` là tên dòng `Packed Item` —
	một dòng KHÔNG nằm trong bảng `custom_phan_bo_vi_tri` nên không có gì để
	so ở đây; (2) đường mất chiều lô của `tach_theo_lo` khi huỷ chứng từ hàng
	có lô (SLE đảo dấu mang `so_lo=None`, xem docstring module `hook_sle.py`)
	— hàm này chạy lúc LƯU/DUYỆT/HUỶ chính document, không chạy lại theo từng
	SLE mà cơ chế huỷ sinh ra. Nhánh `so_luong <= 0` ở `_phan_bo_da_khai` thì
	NGƯỢC LẠI: hàm này đã chặn đủ mọi trường hợp qua API tài liệu thường, xem
	chú thích tại đó.
	"""
	if doc.amended_from and doc.is_new():
		doc.set(TEN_BANG_PHAN_BO, [])

	bang = doc.get(TEN_BANG_PHAN_BO) or []
	if not bang:
		return

	dong_hang = {d.name: d for d in doc.items}
	# Hai sổ cộng dồn RIÊNG cho hai câu hỏi khác nhau — gộp chung một dict (như
	# bản nháp đầu) làm một dòng hàng chia cho NHIỀU ô báo nhầm "ô X không đủ"
	# dù ô X vẫn còn thừa, vì lúc đó lại so tổng CẢ DÒNG HÀNG với tồn của một
	# ô riêng lẻ. `theo_dong` gộp theo (dòng hàng, lô) cho câu "tổng phân bổ có
	# vượt số lượng dòng hàng không" ở vòng lặp thứ hai bên dưới.
	#
	# `theo_o` gộp theo (Ô, vật tư, lô) — KHÔNG theo dòng hàng (vòng sửa 1,
	# Important — review điều phối): `ton_o(o, vat_tu, so_lo)` tính tồn theo
	# đúng ba khoá đó, không biết gì về "dòng hàng". Từng gộp nhầm theo
	# (dòng hàng, lô, ô) — hai DÒNG HÀNG khác nhau nhưng cùng vật tư/lô (khác
	# đơn giá, khác đơn bán gốc — chuyện thường) cùng phân bổ vào MỘT ô thì
	# mỗi dòng hàng có sổ cộng dồn RIÊNG, mỗi sổ tự so với tồn ĐẦY ĐỦ của ô đó
	# — ô còn 20, dòng A xin 15 qua ải, dòng B xin 15 cũng qua ải (mỗi dòng tự
	# so với 20), trong khi tổng rút thật là 30 > 20. Gộp theo (o, vat_tu,
	# so_lo) thì cả hai dòng cùng cộng dồn vào MỘT sổ, khớp đúng cái mà
	# `ton_o` đo. Xem `test_hai_dong_hang_cung_o_vuot_ton_bi_chan`.
	theo_o: dict[tuple, float] = {}
	theo_dong: dict[tuple, float] = {}

	for p in bang:
		dh = dong_hang.get(p.dong_hang)
		if not dh:
			frappe.throw(
				_(
					"Phân bổ vị trí dòng {0}: dòng hàng {1} không thuộc phiếu này (có thể đã bị "
					"xoá). Mở lại trang Lấy hàng để quét lại."
				).format(p.idx, p.dong_hang)
			)
		if p.vat_tu != dh.item_code:
			frappe.throw(
				_("Phân bổ vị trí dòng {0}: mặt hàng {1} khác mặt hàng {2} của dòng hàng.").format(
					p.idx, p.vat_tu, dh.item_code
				)
			)
		if (p.so_lo or None) != (dh.get("batch_no") or None):
			frappe.throw(
				_("Phân bổ vị trí dòng {0}: lô {1} khác lô {2} của dòng hàng.").format(
					p.idx, p.so_lo or "—", dh.get("batch_no") or "—"
				)
			)
		if flt(p.so_luong) <= 0:
			frappe.throw(_("Phân bổ vị trí dòng {0}: số lượng phải lớn hơn 0.").format(p.idx))

		thong_tin = frappe.db.get_value(
			"Storage Location", p.o, ["kho", "is_group"], as_dict=True
		)
		if not thong_tin:
			frappe.throw(_("Phân bổ vị trí dòng {0}: ô {1} không tồn tại.").format(p.idx, p.o))
		if thong_tin.kho != dh.warehouse:
			frappe.throw(
				_("Phân bổ vị trí dòng {0}: ô {1} không thuộc kho {2} của dòng hàng.").format(
					p.idx, p.o, dh.warehouse
				)
			)
		if thong_tin.is_group:
			frappe.throw(
				_(
					"Phân bổ vị trí dòng {0}: {1} là nút nhóm (cấp Khu/Dãy/Khoang/Tầng), không "
					"chứa hàng được."
				).format(p.idx, p.o)
			)

		khoa_dong = (p.dong_hang, p.so_lo or "")
		theo_dong[khoa_dong] = theo_dong.get(khoa_dong, 0.0) + flt(p.so_luong)

		khoa_o = (p.o, p.vat_tu, p.so_lo or "")
		theo_o[khoa_o] = theo_o.get(khoa_o, 0.0) + flt(p.so_luong)

		# Tồn của ô đọc từ bộ đệm — đủ cho lớp sớm; phép chặn tồn âm THẬT vẫn nằm
		# ở đường ghi sổ, nơi có khoá dòng của InnoDB (xem `location_transfer.py`).
		con = flt(ton_o(p.o, p.vat_tu, p.so_lo or None))
		if theo_o[khoa_o] > con + _SAI_SO:
			# Minor (vòng sửa 1): nêu rõ số ĐANG XIN CẤP (cộng dồn của mọi dòng
			# phân bổ trỏ vào CÙNG (ô, vật tư, lô) này trên phiếu) — không bắt
			# người đọc tự lấy tổng số lượng trừ số "chỉ còn" mới ra được số dư.
			frappe.throw(
				_("Phân bổ vị trí dòng {0}: ô {1} chỉ còn {2} của {3}{4}, đang xin cấp {5}.").format(
					p.idx,
					p.o,
					flt(con, 3),
					p.vat_tu,
					_(", lô {0}").format(p.so_lo) if p.so_lo else "",
					flt(theo_o[khoa_o], 3),
				)
			)

	for (dh_ten, _lo), tong in theo_dong.items():
		dh = dong_hang[dh_ten]
		if tong > flt(dh.qty) + _SAI_SO:
			frappe.throw(
				_(
					"Phân bổ vị trí cho {0}: tổng {1} vượt số lượng {2} của dòng hàng. Bỏ bớt dòng "
					"phân bổ hoặc sửa số lượng trên phiếu."
				).format(dh.item_code, flt(tong, 3), flt(dh.qty, 3))
			)

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
from frappe.utils import flt, now, now_datetime, time_diff_in_seconds

from erpnext.vi_tri_kho.vitri.fefo import chon_o_xuat
from erpnext.vi_tri_kho.vitri.kho import kho_co_quan_ly_vi_tri
from erpnext.vi_tri_kho.vitri.nhat_ky_loi import cat_tieu_de
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

# VÒNG SỬA 1/5 (Critical, review điều phối model mạnh): TTL cờ "chốt thiếu"
# hạ từ 24h xuống MỘT CA LÀM VIỆC (8 giờ). Cờ là Ý ĐỊNH của một lượt làm việc
# — để nó sống qua đêm là để nó cắn ca sau: ca chiều mở lại phiếu, thấy cờ của
# ca sáng (nếu không có `da_chot_thieu` hiển thị rõ, xem `mo_phieu_giao`) và
# vô tình để `hoan_tat` hạ `qty` dựa trên một ý định không còn là của họ.
_TTL_CHOT_THIEU = 8 * 60 * 60


def _khoa_chot_thieu(phieu: str) -> str:
	"""Khoá Redis cho cờ "chốt thiếu" của một phiếu.

	VÒNG SỬA 1/5 (Minor): đổi tên từ `_KHOA_CHOT_THIEU` (viết hoa như hằng số
	nhưng là HÀM, dễ đọc nhầm) sang tên hàm bình thường. Đặt gần đầu file
	(không còn cạnh `chot_thieu`) vì từ vòng sửa này cả phần ĐỌC
	(`mo_phieu_giao`) lẫn phần GHI (`chot_thieu`, `bo_chot_thieu`, `hoan_tat`)
	cùng dùng chung khoá này.

	VÒNG SỬA 2/5 (Important, re-review model mạnh): hậu tố `:v2:` — TRƯỚC
	vòng sửa 1, khoá này (không có `:v2:`) lưu một LIST tên dòng hàng, TTL
	24h. Vòng sửa 1 đổi giá trị sang DICT nhưng đọc thẳng, không kiểm kiểu:
	site đang chạy nâng code lên giữa lúc một khoá LIST cũ còn sống (TTL 24h
	cũ chưa hết) sẽ làm `mo_phieu_giao` nổ `'list' object has no attribute
	'get'` — và `mo_phieu_giao` là hàm MỌI hàm ghi đều gọi ở câu return, nên
	đúng nhóm phiếu đang lấy dở (nhóm mà bản vá sinh ra để bảo vệ) sẽ nổ 500
	không tự phục hồi tới khi TTL cũ hết hạn. Đổi tên khoá là lớp chặn RẺ và
	TUYỆT ĐỐI: dữ liệu cũ nằm ở một khoá KHÁC, không bao giờ bị đọc nhầm định
	dạng nữa — không cần chờ TTL, không cần dọn tay. Giữ NGUYÊN cách đặt tên
	`chot_thieu:v2:<phieu>` (hậu tố version TRƯỚC tên phiếu, không phải sau)
	để một ngày cần liệt kê "mọi khoá chốt thiếu đang sống" bằng
	`get_keys("vi_tri_kho:lay_hang:chot_thieu:v2:*")` vẫn vét đúng, không lẫn
	phiếu có tên chứa `:`.
	"""
	return f"vi_tri_kho:lay_hang:chot_thieu:v2:{phieu}"


def _doc_chot_thieu(phieu: str) -> dict:
	"""Đọc cờ "chốt thiếu" của một phiếu — điểm đọc DUY NHẤT, dùng chung cho
	`mo_phieu_giao`, `chot_thieu`, `bo_chot_thieu`, `hoan_tat`.

	VÒNG SỬA 2/5 (Important): guard KIỂU — không phải `dict` thì coi như
	rỗng, KHÔNG ném lỗi. Đổi tên khoá (`_khoa_chot_thieu`, hậu tố `:v2:`) đã
	là lớp chặn chính cho ĐÚNG bẫy "list cũ dưới TTL 24h" đã đo được; guard
	này là lớp THỨ HAI, rẻ, phòng lần đổi định dạng SAU (nếu có) lặp lại đúng
	bẫy vừa vá — không dựa hoàn toàn vào việc "nhớ đổi tên khoá" mỗi lần.

	VÒNG SỬA 2/5 (Minor): lọc bỏ NGAY TẠI ĐÂY các dòng đã chốt quá
	`_TTL_CHOT_THIEU` giây, tính TỪ CHÍNH THỜI ĐIỂM (`luc`) dòng đó được chốt
	— không dựa vào TTL của CẢ KHOÁ Redis. `chot_thieu` phải `set_value(...,
	expires_in_sec=_TTL_CHOT_THIEU)` lại MỖI LẦN gọi (để dòng MỚI chốt không
	bị xoá theo TTL của lần set_value trước) — hệ quả phụ nếu không lọc ở
	đây: dòng A chốt lúc 8:00, dòng B (cùng phiếu) chốt lúc 15:00 sẽ "reset
	đồng hồ" của khoá, kéo dài cờ của dòng A tới tận 23:00 thay vì hết hạn
	đúng 16:00 (8:00 + 8 giờ) như Ý ĐỊNH "8 giờ kể từ lúc DÒNG ĐÓ được chốt".
	TTL của khoá Redis từ đây chỉ còn là TRẦN dọn rác an toàn (dữ liệu không
	bao giờ sống vĩnh viễn dù có lỗi ở đây), không phải cơ chế hết hạn chính.
	"""
	gia_tri = frappe.cache().get_value(_khoa_chot_thieu(phieu), expires=True)
	if not isinstance(gia_tri, dict):
		return {}
	bay_gio = now_datetime()
	con_hieu_luc = {}
	for dong_hang, thong_tin in gia_tri.items():
		luc = thong_tin.get("luc") if isinstance(thong_tin, dict) else None
		if luc:
			try:
				qua_han = time_diff_in_seconds(bay_gio, luc) > _TTL_CHOT_THIEU
			except Exception:
				qua_han = False
			if qua_han:
				continue
		con_hieu_luc[dong_hang] = thong_tin
	return con_hieu_luc


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
		# VÒNG SỬA 1/5 (Important 1, review điều phối): `doc.flags.
		# vi_tri_kho_dang_bo_phan_bo` (đặt DUY NHẤT bởi `bo_dong_da_lay`, xem
		# đó) bỏ qua ĐÚNG phép so tồn này — các phép kiểm khác phía trên (ô
		# đúng kho, không phải ô nhóm, lô khớp dòng, số lượng > 0) vẫn giữ
		# nguyên. Ca hỏng thật: dòng hàng có ≥2 dòng phân bổ, một ô bị người
		# khác rút cạn (chuyển/giao mất hàng) sau khi đã quét — bỏ MỘT dòng
		# phân bổ rồi lưu vẫn bị chặn vì (các) dòng CÒN LẠI giờ xin nhiều hơn
		# tồn hiện có, bất kể bỏ dòng nào trước, mà bảng lại `read_only` nên
		# desk cũng không xoá tay được: kẹt cứng đúng ở tình huống mà tính
		# năng "chốt thiếu" sinh ra để giải quyết. Dùng `doc.flags` (không
		# phải field CSDL) — cờ chỉ sống trong ĐÚNG một lần gọi `doc.save()`
		# của `bo_dong_da_lay`, không sống qua lần lưu sau vì mỗi lệnh gọi API
		# sau đó `frappe.get_doc()` lại một đối tượng MỚI với `flags` rỗng.
		if theo_o[khoa_o] > con + _SAI_SO and not doc.flags.vi_tri_kho_dang_bo_phan_bo:
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


# ---------------------------------------------------------------------------
# Máy chủ cho trang PDA lấy hàng (Task 4, 18/09/2026) — phần ĐỌC.
#
# Trang liệt kê phiếu giao NHÁP đang chờ lấy, mở một phiếu ra xem từng dòng
# cần lấy bao nhiêu và nên tới ô nào, và nhận diện một mã quét. Ba hàm dưới
# đây không ghi gì cả — ghi bảng `custom_phan_bo_vi_tri` là việc của Task 5.
# ---------------------------------------------------------------------------


def _kiem_tra_quyen():
	"""`@frappe.whitelist()` một mình chỉ chặn khách vãng lai — xem `xep.py`."""
	if not VAI_TRO_DUOC_LAY & set(frappe.get_roles()):
		frappe.throw(_("Bạn không có quyền lấy hàng theo vị trí."), frappe.PermissionError)


def _da_lay_theo_dong(doc) -> dict:
	"""{(tên dòng hàng): tổng đã phân bổ}."""
	tong: dict[str, float] = {}
	for p in doc.get(TEN_BANG_PHAN_BO) or []:
		tong[p.dong_hang] = tong.get(p.dong_hang, 0.0) + flt(p.so_luong)
	return tong


def _kho_quan_ly_vi_tri() -> list[str]:
	"""Các kho đang bật quản lý vị trí.

	Cùng nội dung `xep._kho_quan_ly_vi_tri` — giữ bản riêng ở đây theo đúng
	tiền lệ của module: mỗi file `vitri/*.py` tự giữ hằng số/hàm nhỏ của
	mình (xem `VAI_TRO_DUOC_LAY` so với `VAI_TRO_DUOC_XEP`/`VAI_TRO_DUOC_TRA_CUU`
	ở `xep.py`/`quet.py`), không cột chặt các module vốn độc lập vào nhau vì
	một truy vấn ba dòng.
	"""
	return frappe.get_all(
		"Warehouse",
		filters={"custom_quan_ly_vi_tri": 1, "is_group": 0, "disabled": 0},
		pluck="name",
		order_by="name asc",
	)


@frappe.whitelist()
def danh_sach_phieu_giao(kho: str | None = None) -> dict:
	"""Kho để lấy hàng + phiếu giao NHÁP đang chờ lấy của kho đó, kèm tiến độ.

	QUYẾT ĐỊNH 18/09/2026 (thay brief gốc — xem task-4-report.md): tìm phiếu
	qua KHO CỦA DÒNG HÀNG (`Delivery Note Item.warehouse`), KHÔNG qua
	`Delivery Note.set_warehouse`. `set_warehouse` là trường TUỲ CHỌN và
	THƯỜNG TRỐNG trên phiếu tạo từ đơn bán — lọc theo nó thì danh sách rỗng
	trong khi phiếu vẫn nằm đó, thủ kho không mở được gì.

	Trả DICT theo đúng khuôn `xep.phieu_xep_dang_lam` (không phải list):
	trang PDA không có nguồn nào khác để biết kho nào, và site có thể bật
	quản lý vị trí ở nhiều kho cùng lúc. Không truyền `kho`: có đúng một kho
	quản lý vị trí thì chọn luôn; nhiều kho thì để `None` cho trang hỏi.

	LỌC QUYỀN TỪNG PHIẾU (bổ sung vòng sửa 1, review điều phối): mỗi phiếu
	còn được kiểm `has_permission("read")` trước khi đưa vào danh sách — bản
	thân danh sách (tên phiếu, khách hàng, số lượng) đã là rò rỉ nếu hiện ra
	một phiếu mà `mo_phieu_giao`/`quet_de_lay` sau đó sẽ từ chối mở.
	"""
	_kiem_tra_quyen()
	kho_ds = _kho_quan_ly_vi_tri()
	if kho and kho not in kho_ds:
		# Important 2 (vòng sửa 1, review điều phối): endpoint whitelisted gọi
		# thẳng được, không chỉ qua giao diện — `kho` tuỳ ý nào cũng lọt qua
		# nếu không kiểm ở đây, lộ khách hàng/số lượng/số lô của kho đó dù
		# kho chưa từng bật quản lý vị trí (không có ý nghĩa nghiệp vụ để
		# thủ kho "lấy theo vị trí" ở một kho không quản lý vị trí).
		frappe.throw(
			_("Kho {0} chưa bật quản lý vị trí — không dùng được cho trang lấy hàng.").format(kho)
		)
	if not kho:
		kho = kho_ds[0] if len(kho_ds) == 1 else None

	phieu = []
	if kho:
		# Join thẳng bằng SQL (cùng phong cách `xep.py`/`quet.py`) thay vì lọc
		# theo `Delivery Note.set_warehouse` — xem lý do ở docstring trên.
		ten = [
			d.name
			for d in frappe.db.sql(
				"""
				select distinct dn.name, dn.modified
				from `tabDelivery Note` dn
				join `tabDelivery Note Item` dni on dni.parent = dn.name
				where dn.docstatus = 0 and dni.warehouse = %(kho)s
				order by dn.modified desc
				limit 50
				""",
				{"kho": kho},
				as_dict=True,
			)
		]
		for t in ten:
			doc = frappe.get_doc("Delivery Note", t)
			# Bổ sung vòng sửa 1 (review điều phối, sau khi Important 1 đã xong):
			# danh sách TỰ NÓ đã là rò rỉ nếu hiện tên phiếu/khách hàng/số lượng
			# của một phiếu mà chính `mo_phieu_giao`/`quet_de_lay` sau đó sẽ từ
			# chối mở — còn khiến thủ kho chạm vào rồi ăn lỗi quyền không hiểu vì
			# sao. Dùng `has_permission` (trả True/False), KHÔNG `check_permission`
			# (ném lỗi) — một phiếu bị chặn không được phép giết cả danh sách của
			# những phiếu còn lại.
			if not doc.has_permission("read"):
				continue
			dong_kho_nay = [d for d in doc.items if d.warehouse == kho]
			if not dong_kho_nay:
				continue
			da = _da_lay_theo_dong(doc)
			nguoi = {p.nguoi_lay for p in doc.get(TEN_BANG_PHAN_BO) or [] if p.nguoi_lay}
			phieu.append(
				{
					"name": doc.name,
					"khach_hang": doc.customer_name or doc.customer,
					"so_dong": len(dong_kho_nay),
					"can_lay": flt(sum(flt(d.qty) for d in dong_kho_nay)),
					"da_lay": flt(sum(da.get(d.name, 0.0) for d in dong_kho_nay)),
					"nguoi_dang_lay": sorted(nguoi - {frappe.session.user}),
				}
			)
	return {"kho_ds": kho_ds, "kho": kho, "phieu": phieu}


@frappe.whitelist()
def mo_phieu_giao(phieu: str) -> dict:
	"""Chi tiết một phiếu giao để lấy hàng: từng dòng cần bao nhiêu, nên tới ô nào.

	`o_nen_lay` gọi `fefo.chon_o_xuat` — ĐÚNG hàm mà hook sẽ dùng nếu không ai
	phân bổ, nên danh sách gợi ý và hành vi mặc định không bao giờ nói khác nhau.
	Hết hàng thì `chon_o_xuat` ném lỗi; ở đây nuốt và trả danh sách rỗng, vì màn
	hình phải mở được để thủ kho thấy vì sao (khuôn Ruling N ở `xep.hang_chua_xep`).

	`can_quet` (bổ sung điều phối, cùng đợt với quyết định mở rộng `hoan_tat`
	ở Task 5 — sửa bất đối xứng đọc/ghi): `False` khi kho của dòng đó KHÔNG
	bật quản lý vị trí — `hoan_tat` đã BỎ QUA đúng những dòng này (xem
	`kho_co_quan_ly_vi_tri`), nên trang phải biết để hiện mờ/không đòi quét,
	KHÔNG lọc bỏ hẳn dòng khỏi danh sách: thủ kho vẫn phải lấy tay những dòng
	đó (giao thường, không qua sổ vị trí) — giấu dòng đi là giấu việc còn
	phải làm. Cũng bỏ qua gọi `chon_o_xuat` cho các dòng này: kho không quản
	lý vị trí không có `Storage Location` nào để gợi ý, gọi vẫn nuốt được lỗi
	nhưng chỉ tổ ghi rác vào Error Log ở MỌI lần mở phiếu.

	`da_chot_thieu`/`chot_thieu_boi`/`chot_thieu_luc` (VÒNG SỬA 1/5, Critical,
	review điều phối model mạnh): trước sửa này, cờ "chốt thiếu" hoàn toàn VÔ
	HÌNH trên trang — thủ kho A bấm "Chốt thiếu" dòng X rồi bỏ dở ca; ca sau
	thủ kho B mở lại phiếu, màn hình sau khi A bấm giống HỆT màn hình trước
	khi A bấm, nên B không biết dòng X đang mang một ý định "coi như đủ" của
	A. B quét thiếu (vd 11/12) rồi bấm "Hoàn tất" đinh ninh sẽ bị chặn — nhưng
	`hoan_tat` thấy cờ của A vẫn còn (TTL 8 giờ, xem `_TTL_CHOT_THIEU`) nên
	lặng lẽ hạ `qty` xuống 11 và duyệt phiếu, kéo theo `delivered_qty`/
	`per_delivered` của đơn bán — gỡ chỉ còn cách huỷ + amend. Trả rõ cờ (và
	AI đặt, LÚC NÀO) để trang hiện được cảnh báo trước khi B kịp bấm "Hoàn
	tất".
	"""
	_kiem_tra_quyen()
	doc = frappe.get_doc("Delivery Note", phieu)
	# Important 1 (vòng sửa 1, review điều phối): `frappe.get_doc` KHÔNG tự
	# chạy `has_permission` — site thật có nhiều Company, User Permission theo
	# Company sẽ bị xuyên thủng nếu không kiểm tay ở đây (đã đo trên bench
	# này). `_kiem_tra_quyen()` ở trên chỉ kiểm vai trò TOÀN CỤC, không biết gì
	# về CHỨNG TỪ cụ thể này.
	doc.check_permission("read")
	da = _da_lay_theo_dong(doc)
	da_chot = _doc_chot_thieu(phieu)
	dong = []
	for d in doc.items:
		can_quet = kho_co_quan_ly_vi_tri(d.warehouse)
		con_can = flt(d.qty) - da.get(d.name, 0.0)
		goi_y = []
		if can_quet and con_can > 0:
			try:
				goi_y = chon_o_xuat(d.warehouse, d.item_code, d.batch_no or None, max(con_can, 0))
			except Exception:
				frappe.log_error(title=cat_tieu_de(f"vi_tri_kho: mo_phieu_giao goi y loi ({phieu})"))
				goi_y = []
		co_chot = da_chot.get(d.name)
		dong.append(
			{
				"dong_hang": d.name,
				"vat_tu": d.item_code,
				"ten_hang": d.item_name,
				"don_vi": d.stock_uom or d.uom,
				"so_lo": d.batch_no or None,
				"hsd": frappe.db.get_value("Batch", d.batch_no, "expiry_date") if d.batch_no else None,
				"can_lay": flt(d.qty),
				"da_lay": da.get(d.name, 0.0),
				"can_quet": can_quet,
				"da_chot_thieu": bool(co_chot),
				"chot_thieu_boi": co_chot.get("boi") if co_chot else None,
				"chot_thieu_luc": co_chot.get("luc") if co_chot else None,
				"o_nen_lay": [
					{
						"o": g["o"],
						"ma_in_nhan": frappe.db.get_value("Storage Location", g["o"], "ma_in_nhan"),
						"so_luong": flt(g["so_luong"]),
					}
					for g in goi_y
				],
				"da_lay_o": [
					{"name": p.name, "o": p.o, "so_luong": flt(p.so_luong)}
					for p in (doc.get(TEN_BANG_PHAN_BO) or [])
					if p.dong_hang == d.name
				],
			}
		)
	return {
		"name": doc.name,
		"kho": doc.set_warehouse or (doc.items[0].warehouse if doc.items else None),
		"khach_hang": doc.customer_name or doc.customer,
		"dong": dong,
	}


def _han_xa_hon(hsd_moi, hsd_cu) -> bool:
	"""Lô MỚI quét có "xa hạn hơn" lô ĐANG CHỐT trên dòng hay không.

	Important 4 (vòng sửa 1, review điều phối): lô KHÔNG có hạn dùng (`None`)
	coi như "không bao giờ hết hạn" — XA HƠN MỌI lô có hạn, đối xứng với
	`fefo.py` (`ifnull(han, '9999-12-31')`, lô không hạn xếp SAU CÙNG trong
	FEFO vì FEFO ưu tiên hạn gần trước, tức "xa hạn nhất" đứng cuối). Bản cũ
	`bool(hsd_moi and hsd_cu and hsd_moi > hsd_cu)` trả `False` ngay khi MỘT
	trong hai vế `None` — sai nghĩa cho đúng ca hay gặp nhất: lô mới không hạn
	trong khi lô đang chốt có hạn, đáng lẽ phải cảnh báo "xa hơn" thì lại im.
	"""
	if hsd_moi is None and hsd_cu is None:
		return False
	if hsd_moi is None:
		return True
	if hsd_cu is None:
		return False
	return hsd_moi > hsd_cu


def _chon_dong_ung_vien(ung_vien: list, da_lay: dict, dong_hang: str | None):
	"""Chọn MỘT dòng trong các dòng `ung_vien` (cùng mặt hàng/lô quét trúng).

	Important 3 (vòng sửa 1, review điều phối): phiếu có NHIỀU dòng cùng mặt
	hàng (khác lô, hoặc chia dòng vì khác giá/đơn bán gốc) thì lấy phần tử
	ĐẦU của danh sách (`ung_vien[0]`) là tuỳ tiện — `dong_hang`/`hsd_dang_chot`/
	`han_xa_hon` có thể tính theo dòng SAI, cảnh báo sai hướng cho thủ kho.

	Truyền `dong_hang`: CHỈ xét đúng dòng đó (trang đã hỏi lại người dùng),
	không đoán — không khớp dòng nào trong `ung_vien` thì trả `None` (không
	âm thầm rơi về một dòng khác).

	Không truyền: ưu tiên dòng CHƯA lấy đủ (số đã phân bổ < số lượng dòng),
	nhỏ `idx` nhất trong số đó — dòng đã lấy đủ hàng rồi không còn lý do để
	được gán thêm. Mọi dòng đều đã lấy đủ (hiếm, nhưng có thể xảy ra khi thủ
	kho quét lại) thì rơi về dòng đầu tiên theo `idx`, giữ hành vi cũ cho ca
	không còn lựa chọn nào tốt hơn.
	"""
	if dong_hang:
		return next((d for d in ung_vien if d.name == dong_hang), None)
	if not ung_vien:
		return None
	chua_du = [d for d in ung_vien if flt(d.qty) - da_lay.get(d.name, 0.0) > _SAI_SO]
	return (chua_du or ung_vien)[0]


@frappe.whitelist()
def quet_de_lay(phieu: str, ma: str, dong_hang: str | None = None) -> dict:
	"""Nhận diện một mã quét trên trang lấy hàng.

	`loai`: `"lo"` (lô ĐANG có trên phiếu) · `"lo_khac"` (lô khác nhưng cùng một
	mặt hàng của phiếu — kèm `han_xa_hon` để màn hình cảnh báo) · `"o"` · `None`.
	Quét nhầm không bao giờ nổ — cùng lời hứa `quet.py`.

	`dong_hang` (Important 3): phiếu có nhiều dòng cùng mặt hàng thì không thể
	tự đoán ĐÚNG dòng chỉ từ mã quét — xem `_chon_dong_ung_vien`. `nhieu_dong`
	trong kết quả báo cho màn hình biết có từ hai dòng ứng viên trở lên, để
	hỏi lại người dùng khi cần.
	"""
	from erpnext.stock.utils import scan_barcode
	from erpnext.vi_tri_kho.vitri.quet import _tim_o

	_kiem_tra_quyen()
	ma = (ma or "").strip()
	if not ma:
		return {"loai": None}
	try:
		doc = frappe.get_doc("Delivery Note", phieu)
	except frappe.DoesNotExistError:
		# Critical (vòng sửa 1, review điều phối): phiếu bị huỷ/xoá giữa lúc
		# thủ kho đang mở phiên quét (điều phối huỷ đơn giữa ca) — quét nhầm
		# không bao giờ được nổ ra màn hình, cùng lời hứa của `quet.py`.
		return {"loai": None}
	# Important 1 (vòng sửa 1, review điều phối): `frappe.get_doc` KHÔNG tự
	# chạy `has_permission` — xem chú thích tại `mo_phieu_giao`. `PermissionError`
	# ở đây phải văng ra NGUYÊN VẸN, không được lẫn vào khối `except Exception`
	# "quét nhầm" bên dưới — vì vậy đặt TRƯỚC khối `try` đó.
	doc.check_permission("read")

	da = _da_lay_theo_dong(doc)
	try:
		kq = scan_barcode(ma) or {}
		so_lo = kq.get("batch_no")
		if so_lo:
			ung_vien_lo = [d for d in doc.items if (d.batch_no or None) == so_lo]
			if ung_vien_lo:
				d = _chon_dong_ung_vien(ung_vien_lo, da, dong_hang)
				if not d:
					return {"loai": None}
				return {
					"loai": "lo",
					"so_lo": so_lo,
					"dong_hang": d.name,
					"vat_tu": d.item_code,
					"nhieu_dong": len(ung_vien_lo) > 1,
				}
			vat_tu = frappe.db.get_value("Batch", so_lo, "item")
			cung_hang = [d for d in doc.items if d.item_code == vat_tu]
			if cung_hang:
				d = _chon_dong_ung_vien(cung_hang, da, dong_hang)
				if not d:
					return {"loai": None}
				hsd_moi = frappe.db.get_value("Batch", so_lo, "expiry_date")
				hsd_cu = frappe.db.get_value("Batch", d.batch_no, "expiry_date")
				return {
					"loai": "lo_khac",
					"so_lo": so_lo,
					"dong_hang": d.name,
					"vat_tu": vat_tu,
					"hsd": hsd_moi,
					"hsd_dang_chot": hsd_cu,
					"so_lo_dang_chot": d.batch_no,
					"han_xa_hon": _han_xa_hon(hsd_moi, hsd_cu),
					"nhieu_dong": len(cung_hang) > 1,
				}
			return {"loai": None}

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
	except Exception:
		frappe.log_error(title=cat_tieu_de(f"vi_tri_kho: quet_de_lay loi ({ma})"))
	return {"loai": None}


# ---------------------------------------------------------------------------
# Máy chủ cho trang PDA lấy hàng (Task 5, 18/09/2026) — phần GHI.
#
# Ghi lượt đã lấy vào bảng phân bổ, bỏ lượt quét nhầm, đổi lô, chốt thiếu, và
# hoàn tất (duyệt phiếu giao). Mọi phép KIỂM đã có ở `kiem_phan_bo_khi_luu`
# (gắn `validate`, Task 3) — các hàm dưới đây chỉ SỬA bảng con rồi `doc.save()`,
# để lớp sớm đó làm việc của nó; không viết lại các phép kiểm ấy ở đây.
# ---------------------------------------------------------------------------


def _dong_cua(doc, dong_hang):
	d = next((x for x in doc.items if x.name == dong_hang), None)
	if not d:
		frappe.throw(_("Dòng hàng {0} không thuộc phiếu {1}.").format(dong_hang, doc.name))
	return d


def _mo_de_ghi(phieu: str):
	"""Mở phiếu giao để GHI: kiểm vai trò (toàn cục) + quyền ghi trên CHÍNH
	chứng từ này + còn đang ở trạng thái NHÁP.

	`frappe.get_doc` không tự chạy `has_permission` (cùng bẫy đã vá ở phần ĐỌC,
	xem `mo_phieu_giao`) — năm hàm GHI của file này hỏng chỗ đó còn nặng hơn.
	Kiểm `docstatus == 0` gộp vào MỘT chỗ: `ghi_da_lay`/`bo_dong_da_lay`/
	`doi_lo` vốn tự rơi vào lỗi khung ("Cannot edit submitted document", tiếng
	Anh, khó hiểu) khi thiếu, nhưng `chot_thieu` không gọi `save()` nào cả —
	không có gì chặn nó ghi một cờ Redis vô nghĩa lên một phiếu đã duyệt/đã
	huỷ nếu không kiểm tay ở đây.
	"""
	_kiem_tra_quyen()
	doc = frappe.get_doc("Delivery Note", phieu)
	doc.check_permission("write")
	if doc.docstatus != 0:
		frappe.throw(
			_("Phiếu giao {0} không còn ở trạng thái nháp — không lấy hàng tiếp được.").format(phieu)
		)
	return doc


def _chan_bundle_serial_batch(d):
	"""VÒNG SỬA 1/5 (Important 2, review điều phối): dòng đã chốt lô qua bảng
	`Serial and Batch Bundle` (luồng Pick List, hoặc hộp thoại chọn lô/serial
	trên form) thì `doi_lo`/`chot_thieu`/`hoan_tat` của trang PDA đều hỏng
	theo cách khác nhau: `hoan_tat` hạ `qty` sẽ đụng `validate_quantity` của
	bundle, ném "Total quantity does not match" (tiếng Anh, kỹ thuật);
	`doi_lo` thì LƯU TRÓT LỌT nhưng để `batch_no` trên dòng lệch hẳn với lô
	trong bundle suốt thời gian nháp — chỉ nổ ra lúc DUYỆT, xa chỗ gây ra lỗi.
	Chặn SỚM, bằng câu tiếng Việt, ngay khi phát hiện — trang Lấy hàng CHƯA
	hỗ trợ luồng Serial & Batch Bundle, thao tác trên form gốc.
	"""
	if d.get("serial_and_batch_bundle"):
		frappe.throw(
			_(
				"Dòng {0} ({1}) đã chốt lô bằng bảng Serial & Batch Bundle (Pick List, hoặc hộp "
				"thoại chọn lô/serial) — trang Lấy hàng chưa hỗ trợ luồng này. Thao tác trực tiếp "
				"trên form Phiếu giao hàng."
			).format(d.idx, d.item_code)
		)


def _luu_hoac_bao_xung_dot(doc):
	"""`doc.save()` bọc bắt `TimestampMismatchError` (VÒNG SỬA 1/5, Important
	3, review điều phối): hai người cùng thao tác một phiếu — người lưu SAU
	đang cầm bản đã cũ (`modified` lệch), Frappe tự chặn (an toàn, không cộng
	đôi dữ liệu) nhưng ném ra đúng tên lớp ngoại lệ tiếng Anh kỹ thuật
	("TimestampMismatchError") — thủ kho đọc xong không biết phải làm gì.
	Bắt riêng, ném lại câu tiếng Việt kèm hướng xử lý (nạp lại, quét lại).
	"""
	try:
		doc.save()
	except frappe.TimestampMismatchError:
		frappe.throw(
			_(
				"Phiếu giao {0} vừa được người khác sửa. Màn hình sẽ nạp lại — quét lại lượt vừa "
				"rồi."
			).format(doc.name)
		)


@frappe.whitelist()
def ghi_da_lay(phieu: str, dong_hang: str, so_lo: str | None, o: str, so_luong) -> dict:
	"""Ghi một lần quét (lô, ô, số lượng) vào bảng phân bổ và LƯU NGAY.

	Lưu ngay chứ không gom trong trình duyệt: PDA hết pin giữa ca là mất cả chục
	lượt quét mà thủ kho đã đi lấy thật ngoài kệ — cùng lẽ với trang xếp hàng.

	Cùng (dòng hàng, lô, ô) thì CỘNG DỒN vào dòng phân bổ sẵn có, không đẻ dòng mới.
	"""
	so_lo = so_lo or None
	so_luong = flt(so_luong)
	if so_luong <= 0:
		frappe.throw(_("Số lượng lấy phải lớn hơn 0."))

	doc = _mo_de_ghi(phieu)
	d = _dong_cua(doc, dong_hang)
	if (d.batch_no or None) != so_lo:
		frappe.throw(
			_("Dòng hàng đang chốt lô {0}, không phải {1}. Đổi lô trước khi ghi.").format(
				d.batch_no or "—", so_lo or "—"
			)
		)

	trung = next(
		(
			p
			for p in doc.get(TEN_BANG_PHAN_BO) or []
			if p.dong_hang == dong_hang and (p.so_lo or None) == so_lo and p.o == o
		),
		None,
	)
	if trung:
		trung.so_luong = flt(trung.so_luong) + so_luong
		trung.nguoi_lay = frappe.session.user
		trung.luc_lay = now()
	else:
		doc.append(
			TEN_BANG_PHAN_BO,
			{
				"dong_hang": dong_hang,
				"vat_tu": d.item_code,
				"so_lo": so_lo,
				"o": o,
				"so_luong": so_luong,
				"nguoi_lay": frappe.session.user,
				"luc_lay": now(),
			},
		)
	_luu_hoac_bao_xung_dot(doc)
	return mo_phieu_giao(phieu)


@frappe.whitelist()
def bo_dong_da_lay(phieu: str, ten_dong: str) -> dict:
	"""Quét nhầm thì gỡ đúng dòng phân bổ đó.

	Nếu `ten_dong` không khớp dòng nào (đã bị bỏ trước đó, hai tab cùng bấm)
	thì CHẶN thay vì âm thầm trả về nguyên trạng — một phép "bỏ" tưởng thành
	công mà thực ra không làm gì là đúng loại lỗi mà cả module này phải tránh.

	VÒNG SỬA 1/5 (Important 1, review điều phối): đặt
	`doc.flags.vi_tri_kho_dang_bo_phan_bo = True` TRƯỚC khi lưu — CHỈ hàm này
	đặt cờ đó, và `kiem_phan_bo_khi_luu` chỉ bỏ qua ĐÚNG phép so tồn khi thấy
	nó (xem đó). Ca cần: dòng hàng có ≥2 dòng phân bổ, một ô bị người khác
	rút cạn sau khi đã quét — không có cờ này thì bỏ dòng nào cũng bị chặn vì
	(các) dòng còn lại giờ xin nhiều hơn tồn hiện có, kẹt cứng đúng ở tình
	huống mà tính năng "chốt thiếu" sinh ra để giải quyết.
	"""
	doc = _mo_de_ghi(phieu)
	bang = doc.get(TEN_BANG_PHAN_BO) or []
	con_lai = [p for p in bang if p.name != ten_dong]
	if len(con_lai) == len(bang):
		frappe.throw(
			_("Dòng phân bổ {0} không tồn tại trên phiếu {1} — có thể đã bị bỏ trước đó.").format(
				ten_dong, phieu
			)
		)
	doc.set(TEN_BANG_PHAN_BO, con_lai)
	doc.flags.vi_tri_kho_dang_bo_phan_bo = True
	_luu_hoac_bao_xung_dot(doc)
	return mo_phieu_giao(phieu)


@frappe.whitelist()
def doi_lo(phieu: str, dong_hang: str, so_lo_moi: str) -> dict:
	"""Đổi lô của một dòng phiếu giao sang lô thủ kho thật sự cầm trên tay.

	Chỉ cho đổi khi dòng CHƯA có phân bổ nào: đã quét lấy ở ô nào đó rồi mà đổi
	lô là để lại một phân bổ trỏ vào lô cũ — sổ vị trí sẽ trừ nhầm lô.
	"""
	doc = _mo_de_ghi(phieu)
	d = _dong_cua(doc, dong_hang)
	_chan_bundle_serial_batch(d)
	da_lay = [p for p in doc.get(TEN_BANG_PHAN_BO) or [] if p.dong_hang == dong_hang]
	if da_lay:
		frappe.throw(
			_("Dòng này đã ghi {0} lượt lấy cho lô {1}. Bỏ các lượt đó trước khi đổi lô.").format(
				len(da_lay), d.batch_no
			)
		)
	if not frappe.db.exists("Batch", so_lo_moi):
		frappe.throw(_("Lô {0} không tồn tại.").format(so_lo_moi))
	chu = frappe.db.get_value("Batch", so_lo_moi, "item")
	if chu != d.item_code:
		frappe.throw(_("Lô {0} là lô của mặt hàng {1}, không phải {2}.").format(so_lo_moi, chu, d.item_code))
	d.batch_no = so_lo_moi
	_luu_hoac_bao_xung_dot(doc)
	return mo_phieu_giao(phieu)


@frappe.whitelist()
def chot_thieu(phieu: str, dong_hang: str) -> dict:
	"""Đánh dấu dòng này lấy được bao nhiêu thì tính bấy nhiêu.

	KHÔNG sửa số lượng ngay ở đây — `hoan_tat` mới sửa, vì thủ kho còn có thể
	quét thêm ở ô khác sau khi đã chốt thiếu.

	Cờ nằm ở `frappe.cache()` (Redis), KHÔNG phải trên chứng từ: nó là ý định
	của một lượt làm việc, không phải dữ liệu kế toán. Redis bị xoá thì cờ mất
	và `hoan_tat` báo "chưa lấy đủ" — hỏng về phía AN TOÀN (bắt quét/chốt lại),
	không bao giờ tự hạ số lượng phiếu giao vì một cờ rác.

	BẪY ĐÃ ĐO (đo trên erptest.local): PHẢI gọi `get_value(..., expires=True)`
	cho khoá này, ở MỌI lần đọc — kể cả lần đọc ĐẦU TIÊN, lúc khoá còn chưa hề
	tồn tại. `RedisWrapper.get_value` (`frappe/utils/redis_wrapper.py`) kiểm
	`frappe.local.cache` (dict trong tiến trình) TRƯỚC KHI hỏi Redis, không
	xét `expires` của LẦN GỌI NÀY: nếu một lần đọc bất kỳ TRƯỚC ĐÓ từng gọi
	không kèm `expires=True` và thấy khoá rỗng, nó tự ghi `None` vào
	`frappe.local.cache[khoa]` — và `set_value(..., expires_in_sec=...)` sau
	đó KHÔNG cập nhật `frappe.local.cache` (chỉ ghi thẳng xuống Redis qua
	`setex`), nên `None` đã lưu SỐNG SÓT vĩnh viễn trong tiến trình đó: mọi
	lần `get_value` sau, dù có `expires=True` hay không, đều trả về đúng
	`None` cũ mà không bao giờ chạm lại Redis nữa. Hậu quả đo được: gọi
	`chot_thieu` rồi `hoan_tat` TRONG CÙNG MỘT TIẾN TRÌNH PYTHON (đúng kịch
	bản `bench run-tests`, nơi cả file test chạy trong một tiến trình duy
	nhất) khiến `hoan_tat` không bao giờ thấy cờ, cứ báo "chưa lấy đủ" mãi.
	Trên web request thật, lỗi này bị CHE (không phải không tồn tại): mỗi
	request gọi lại `frappe.init()` (`frappe/app.py`), và `init()` gán lại
	`local.cache = {}` — `chot_thieu` (request A) chỉ đầu độc bản
	`local.cache` chết theo request A, `hoan_tat` (request B) khởi động với
	`local.cache` rỗng nên đọc đúng Redis. Vẫn phải sửa: đây là một bẫy thật
	sẽ tái phát bất cứ khi nào một luồng khác (test, job nền, script) đọc/ghi
	cùng khoá trong một tiến trình sống lâu.

	VÒNG SỬA 1/5 (Critical, review điều phối model mạnh): giá trị lưu trong
	Redis đổi từ MỘT DANH SÁCH tên dòng hàng sang một DICT
	`{dong_hang: {"boi": user, "luc": timestamp}}` — cờ giờ mang theo AI đặt
	và LÚC NÀO, để `mo_phieu_giao` trả lại cho trang hiện rõ (xem đó); trước
	đây cờ hoàn toàn vô hình, thủ kho ca sau không biết ca trước đã bấm. TTL
	hạ từ 24h xuống MỘT CA LÀM VIỆC (`_TTL_CHOT_THIEU`, 8 giờ).

	Chặn SỚM dòng đã chốt lô bằng Serial & Batch Bundle (Important 2) và dòng
	thuộc kho KHÔNG bật quản lý vị trí (Minor): `hoan_tat` bỏ qua đúng những
	dòng đó nên "chốt thiếu" trên chúng là một cờ không bao giờ được đọc lại
	— no-op câm, dễ khiến thủ kho tưởng đã xử lý xong.

	VÒNG SỬA 2/5: đọc/ghi qua `_doc_chot_thieu`/`_khoa_chot_thieu` — xem
	docstring hai hàm đó cho guard kiểu (dữ liệu LIST cũ trước vòng sửa 1) và
	cách khoá được đặt tên có phiên bản.
	"""
	doc = _mo_de_ghi(phieu)
	d = _dong_cua(doc, dong_hang)
	_chan_bundle_serial_batch(d)
	if not kho_co_quan_ly_vi_tri(d.warehouse):
		frappe.throw(
			_(
				"Dòng {0} ({1}) thuộc kho không quản lý vị trí — không cần (và không có tác dụng) "
				"chốt thiếu trên trang này."
			).format(d.idx, d.item_code)
		)
	danh_dau = _doc_chot_thieu(phieu)
	danh_dau[dong_hang] = {"boi": frappe.session.user, "luc": now()}
	frappe.cache().set_value(_khoa_chot_thieu(phieu), danh_dau, expires_in_sec=_TTL_CHOT_THIEU)
	return mo_phieu_giao(phieu)


@frappe.whitelist()
def bo_chot_thieu(phieu: str, dong_hang: str) -> dict:
	"""Gỡ cờ "chốt thiếu" — bấm nhầm thì phải gỡ lại được (VÒNG SỬA 1/5,
	Critical, review điều phối). Trước sửa này, cách DUY NHẤT gỡ một cờ chốt
	thiếu đặt nhầm là quét cho đủ số lượng (không phải lúc nào cũng còn hàng
	để quét) hoặc chờ hết TTL — cả hai đều không phải "gỡ".

	CHẶN nếu dòng chưa hề mang cờ, cùng nguyên tắc `bo_dong_da_lay`: một phép
	"gỡ" tưởng thành công mà thực ra không làm gì là đúng loại lỗi module này
	phải tránh.
	"""
	doc = _mo_de_ghi(phieu)
	_dong_cua(doc, dong_hang)
	khoa = _khoa_chot_thieu(phieu)
	danh_dau = _doc_chot_thieu(phieu)
	if dong_hang not in danh_dau:
		frappe.throw(
			_("Dòng {0} chưa được chốt thiếu — không có gì để gỡ.").format(dong_hang)
		)
	danh_dau.pop(dong_hang)
	if danh_dau:
		frappe.cache().set_value(khoa, danh_dau, expires_in_sec=_TTL_CHOT_THIEU)
	else:
		frappe.cache().delete_value(khoa)
	return mo_phieu_giao(phieu)


@frappe.whitelist()
def hoan_tat(phieu: str) -> dict:
	"""Chỉnh số lượng theo số lấy thật (nếu có chốt thiếu) rồi DUYỆT phiếu giao.

	QUYẾT ĐỊNH 18/09/2026 (mở rộng brief gốc, điều phối chốt): xét MỌI dòng
	hàng của phiếu thuộc kho có BẬT quản lý vị trí — không chỉ các dòng của
	kho đang mở trên màn hình PDA. Task 2 đã chốt ngữ nghĩa "một phiếu giao:
	hoặc quét trọn, hoặc không quét dòng nào" (`hook_sle._phan_bo_da_khai`
	CHẶN nếu chứng từ có bảng phân bổ mà dòng đang ghi không khớp) — nếu
	`hoan_tat` chỉ xét một phần dòng, phiếu được duyệt (docstatus ghi xuống
	CSDL) rồi CHẾT ngay trong `on_submit` với một câu báo khó hiểu, và phải
	cậy tới savepoint bên dưới để dọn. Dòng thuộc kho KHÔNG bật quản lý vị trí
	thì BỎ QUA — hook ghi sổ không đụng tới chúng (`kho_co_quan_ly_vi_tri`),
	không có ý nghĩa gì để đòi chúng "đã lấy đủ".

	Savepoint riêng bọc quanh CẢ việc lưu số lượng/ghi chú lẫn `submit()`, đặt
	TRƯỚC lần `save()` đầu tiên: `Document.submit()` ghi `docstatus = 1` xuống
	CSDL TRƯỚC khi `on_submit` chạy, nên hỏng ở hook mà không ai rollback thì
	phiếu mang docstatus 1 không một dòng sổ nào (cùng bẫy đã vá ở
	`xep.duyet_phieu_xep`). Đặt savepoint trước cả bước hạ số lượng/ghi chú —
	không chỉ trước `submit()` — để một `hoan_tat` hỏng LUÔN là một no-op
	hoàn toàn trên phiếu nháp, không để lại nửa vời số lượng đã hạ mà chưa
	duyệt được.

	`so_dong` (VÒNG SỬA 1/5, Minor): đếm đúng số dòng THUỘC KHO QUẢN LÝ VỊ TRÍ
	(dòng mà `hoan_tat` thật sự xét) — trước sửa này trả `len(doc.items)`,
	đếm nhầm CẢ dòng `can_quet=False` mà chính hàm này vừa bỏ qua, một con số
	đi thẳng ra màn hình "đã duyệt N dòng" mà không khớp việc thật đã làm.
	"""
	doc = _mo_de_ghi(phieu)
	da = _da_lay_theo_dong(doc)
	# VÒNG SỬA 1/5: giá trị là DICT `{dong_hang: {"boi":..., "luc":...}}` từ
	# đây trở đi (không còn là list tên dòng) — `in` trên dict vẫn so đúng
	# theo KHOÁ nên không cần đổi gì thêm ở các dòng dùng `thieu` bên dưới.
	# VÒNG SỬA 2/5: đọc qua `_doc_chot_thieu` (guard kiểu + lọc quá hạn từng
	# dòng) thay vì gọi thẳng `frappe.cache().get_value`.
	thieu = _doc_chot_thieu(phieu)
	lay_thieu = []
	so_dong_quan_ly = 0

	for d in doc.items:
		if not kho_co_quan_ly_vi_tri(d.warehouse):
			continue
		so_dong_quan_ly += 1
		lay = flt(da.get(d.name, 0.0))
		if abs(lay - flt(d.qty)) <= _SAI_SO:
			continue
		if d.name not in thieu:
			frappe.throw(
				_(
					"Dòng {0} ({1}) chưa lấy đủ: cần {2}, đã lấy {3}. Quét tiếp, hoặc bấm 'Chốt "
					"thiếu' cho dòng đó."
				).format(d.idx, d.item_code, flt(d.qty, 3), flt(lay, 3))
			)
		if lay <= 0:
			frappe.throw(
				_(
					"Dòng {0} ({1}) chưa lấy được gì — bỏ dòng khỏi phiếu giao thay vì chốt "
					"thiếu 0."
				).format(d.idx, d.item_code)
			)
		# Important 2 (vòng sửa 1/5): CHỈ chặn ở đây, không chặn TOÀN BỘ hàm
		# ngay từ đầu — một dòng dùng bundle mà đã lấy đủ (không cần hạ `qty`)
		# không có gì để hỏng cả, chặn sớm hơn là cấm oan những phiếu không
		# đụng gì tới bundle.
		_chan_bundle_serial_batch(d)
		lay_thieu.append({"vat_tu": d.item_code, "so_lo": d.batch_no, "thieu": flt(d.qty) - lay})
		d.qty = lay

	diem = "vi_tri_kho_hoan_tat_lay_hang"
	frappe.db.savepoint(diem)
	try:
		if lay_thieu:
			doc.save()
		doc.submit()
		if lay_thieu:
			# QUYẾT ĐỊNH ĐIỀU PHỐI (thay brief/spec §6.3 — "ghi vào remarks" viết
			# theo ERPNext gốc, không đúng fork này: `Delivery Note` KHÔNG có
			# field `remarks`, đo bằng `frappe.get_meta(...).has_field`). KHÔNG
			# dùng `instructions` (Text CÓ thật trên DocType) vì nó HIỆN TRÊN
			# BẢN IN gửi khách — nội dung "ô trống sớm hơn sổ, cần kiểm kê" là
			# chuyện NỘI BỘ kho, in ra là lộ chuyện kho ra ngoài. KHÔNG thêm
			# Custom Field mới (ngoài phạm vi file được giao). Dùng
			# `add_comment`: một bản ghi `Comment` gắn vào timeline của chính
			# phiếu — không bao giờ in ra, truy được ai/lúc nào, không đổi
			# lược đồ. Gọi SAU `doc.submit()`, trong CÙNG try/except với
			# savepoint: `add_comment` tự `insert()` ngay (không đợi
			# `doc.save()`), nên phải chắc chắn phiếu ĐÃ duyệt thật trước khi
			# gọi — nếu không, một `hoan_tat` bị chặn ở lớp kiểm sớm (`throw`,
			# ném ra TRƯỚC dòng này) sẽ không bao giờ chạm tới đây, và nếu một
			# lỗi xảy ra ngay sau khi gọi (hiếm) thì rollback theo `diem` sẽ
			# xoá luôn cả comment vừa `insert`, giữ đúng lời hứa "hỏng thì
			# không để lại gì".
			ghi_chu = "; ".join(
				_("Lấy thiếu {0} {1}{2} — ô trống sớm hơn sổ, cần kiểm kê.").format(
					flt(x["thieu"], 3), x["vat_tu"], f" lô {x['so_lo']}" if x["so_lo"] else ""
				)
				for x in lay_thieu
			)
			doc.add_comment("Comment", ghi_chu)
	except frappe.TimestampMismatchError:
		# Important 3 (vòng sửa 1/5): bắt RIÊNG trước `except Exception` chung
		# — `TimestampMismatchError` là con của `ValidationError` nên khối
		# chung phía dưới VẪN bắt được, nhưng sẽ ném NGUYÊN VĂN tên lớp tiếng
		# Anh ra ngoài thay vì câu tiếng Việt. Vẫn rollback savepoint như
		# đường hỏng thường — hướng hỏng đã AN TOÀN (Frappe tự chặn, không
		# cộng đôi dữ liệu), chỉ đổi CÂU CHỮ cho thủ kho đọc hiểu được.
		frappe.db.rollback(save_point=diem)
		frappe.throw(
			_(
				"Phiếu giao {0} vừa được người khác sửa. Màn hình sẽ nạp lại — quét lại lượt vừa "
				"rồi."
			).format(phieu)
		)
	except Exception:
		frappe.db.rollback(save_point=diem)
		raise
	frappe.cache().delete_value(_khoa_chot_thieu(phieu))
	return {"name": doc.name, "so_dong": so_dong_quan_ly, "lay_thieu": lay_thieu}

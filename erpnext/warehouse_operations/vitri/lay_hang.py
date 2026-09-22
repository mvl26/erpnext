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
from frappe.utils import cint, flt, formatdate, getdate, now, now_datetime, nowdate, time_diff_in_seconds

from erpnext.warehouse_operations.vitri.fefo import chon_o_xuat
from erpnext.warehouse_operations.vitri.kho import kho_co_quan_ly_vi_tri
from erpnext.warehouse_operations.vitri.nhat_ky_loi import cat_tieu_de
from erpnext.warehouse_operations.vitri.so import ton_o, tong_ton_vi_tri

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


# ---------------------------------------------------------------------------
# Cột "Vị trí lấy" trên từng dòng hàng (19/09/2026 — chủ đầu tư muốn thấy ô ngay
# trên dòng hàng, và phiếu in ra phải có). Cột CHỈ LÀ BẢN HIỂN THỊ: lúc nháp nó
# tóm bảng phân bổ, lúc duyệt nó tóm sổ vị trí thật. Không ai đọc cột này để ra
# quyết định — đừng đọc nó ở code khác, đọc nguồn.
# ---------------------------------------------------------------------------

COT_VI_TRI_LAY = "custom_vi_tri_lay"


def _chuoi_vi_tri(cap) -> str:
	"""[(ô, số lượng), ...] → "1A0101-0101 ×5; 1A0101-0102 ×3".

	Gộp theo ô, giữ thứ tự ô xuất hiện lần đầu (thứ tự quét / thứ tự FEFO trừ).
	Hiện `ma_in_nhan` — đúng chữ in trên tem ô ngoài kệ, thứ người đọc phiếu sẽ đi
	tìm — rơi về tên ô nếu ô chưa có mã in.
	"""
	tong: dict[str, float] = {}
	for o, sl in cap:
		tong[o] = tong.get(o, 0.0) + abs(flt(sl))
	return "; ".join(
		f"{frappe.get_cached_value('Storage Location', o, 'ma_in_nhan') or o} ×{flt(sl, 3):g}"
		for o, sl in tong.items()
		if sl > _SAI_SO
	)


def _dat_cot(d, gia_tri: str, ghi_db: bool = False) -> None:
	gia_tri = gia_tri or ""
	if (d.get(COT_VI_TRI_LAY) or "") == gia_tri:
		return
	if ghi_db:
		d.db_set(COT_VI_TRI_LAY, gia_tri, update_modified=False)
	else:
		d.set(COT_VI_TRI_LAY, gia_tri)


def dien_cot_vi_tri_tu_phan_bo(doc) -> None:
	"""Tính lại cột từ bảng phân bổ — gọi ở `kiem_phan_bo_khi_luu` (validate).

	Mọi thao tác của trang PDA (quét, bỏ lượt, đổi lô, tách dòng) đều kết thúc
	bằng `doc.save()`, nên đặt ở validate là MỘT chỗ duy nhất, không phải nhớ gọi
	lại ở từng hàm ghi. Bảng trống (chưa quét, hoặc bản amend vừa được dọn) thì
	cột trống.
	"""
	if not doc.meta.get_field(TEN_BANG_PHAN_BO) or not frappe.get_meta(
		"Delivery Note Item"
	).has_field(COT_VI_TRI_LAY):
		return
	theo_dong: dict[str, list] = {}
	for p in doc.get(TEN_BANG_PHAN_BO) or []:
		theo_dong.setdefault(p.dong_hang, []).append((p.o, p.so_luong))
	for d in doc.items:
		_dat_cot(d, _chuoi_vi_tri(theo_dong.get(d.name, [])))


def ghi_cot_vi_tri_khi_duyet(doc, method=None) -> None:
	"""`doc_events` on_submit của Delivery Note: viết cột từ SỔ VỊ TRÍ THẬT.

	Chạy SAU `on_submit` của controller — lúc đó các SLE đã được ghi và hook
	`hook_sle.ghi_so_vi_tri` đã sinh `Location Ledger Entry` đồng bộ. Đọc sổ chứ
	không đọc bảng phân bổ: phiếu không ai quét thì bảng trống nhưng FEFO vẫn
	trừ một ô cụ thể — phiếu in ra phải nói đúng ô đó (chủ đầu tư chọn "tự điền
	theo ô FEFO"). Phiếu có quét thì sổ trùng bảng, nên một đường đọc cho cả hai.

	Dòng không có dòng sổ nào (dịch vụ, kho không quản lý vị trí) → cột trống.
	Dòng Product Bundle: sổ mang tên dòng `Packed Item`, không khớp dòng hàng nào
	→ cột dòng cha trống (hàng bundle vẫn không lấy qua PDA được, xem spec).
	"""
	if not frappe.get_meta("Delivery Note Item").has_field(COT_VI_TRI_LAY):
		return
	so = frappe.get_all(
		"Location Ledger Entry",
		filters={"chung_tu_type": doc.doctype, "chung_tu": doc.name},
		fields=["chung_tu_row", "o", "so_luong"],
		order_by="creation asc, name asc",
	)
	theo_dong: dict[str, list] = {}
	for r in so:
		theo_dong.setdefault(r.chung_tu_row, []).append((r.o, r.so_luong))
	for d in doc.items:
		_dat_cot(d, _chuoi_vi_tri(theo_dong.get(d.name, [])), ghi_db=True)


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

	dien_cot_vi_tri_tu_phan_bo(doc)

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


def _da_phan_bo_o_theo_mat_hang_lo(doc, kho: str, vat_tu: str, so_lo: str | None) -> dict:
	"""{ô: tổng đã phân bổ} cho ĐÚNG (kho, vat_tu, so_lo) trên TOÀN BỘ phiếu `doc`.

	Gộp qua MỌI dòng hàng, không chỉ dòng đang xét — hai dòng hàng khác nhau
	nhưng cùng (mặt hàng, lô) vẫn cùng giữ hàng ở NHỮNG Ô ĐÓ (đúng cách
	`kiem_phan_bo_khi_luu` gộp `theo_o` để so với `ton_o` lúc validate).

	VÒNG SỬA (review độc lập, model mạnh): thêm tham số `kho`, lọc theo kho
	của TỪNG dòng hàng góp vào (không phải kho của dòng đang xét — một phiếu
	giao hiếm khi nhưng CÓ THỂ có hai dòng cùng mặt hàng/lô ở hai KHO khác
	nhau, ví dụ giao từ hai kho cho cùng khách). Thiếu bộ lọc này thì
	`thieu_trong_lo` của một dòng sẽ cộng nhầm phần đã phân bổ của dòng kia ở
	kho KHÁC — báo "thiếu" nhiều hơn tồn CỦA ĐÚNG KHO đang xét thật sự thiếu.
	Tra kho theo `Delivery Note Item.warehouse` của CHÍNH dòng hàng sở hữu mỗi
	dòng phân bổ (`p.dong_hang`), không tra theo `p.o` (Storage Location của
	một ô luôn cố định một kho, tra qua đó cũng đúng, nhưng tra qua dòng hàng
	sẵn có trên `doc.items` không cần truy vấn CSDL thêm).

	Dùng để TRỪ khỏi gợi ý `o_nen_lay` của `mo_phieu_giao` (sửa lỗi đo trên
	tài liệu ảnh `22b`): ô đã bị CHÍNH phiếu này lấy hết trên giấy (chưa
	submit nên `Location Balance` — nguồn của `fefo.chon_o_xuat` — vẫn coi ô
	đó còn nguyên) không còn lý do được gợi ý lại — thủ kho đi tới sẽ thấy ô
	vừa lấy trống, đúng cảnh lộ trên ảnh trước bản vá này.
	"""
	kho_theo_dong = {x.name: x.warehouse for x in doc.items}
	theo_o: dict[str, float] = {}
	for p in doc.get(TEN_BANG_PHAN_BO) or []:
		if p.vat_tu != vat_tu or (p.so_lo or None) != (so_lo or None):
			continue
		if kho_theo_dong.get(p.dong_hang) != kho:
			continue
		theo_o[p.o] = theo_o.get(p.o, 0.0) + flt(p.so_luong)
	return theo_o


def _ly_do_khong_quet_dong(d) -> str | None:
	"""Vì sao dòng `d` (một `Delivery Note Item`) KHÔNG quét được trên trang Lấy
	hàng — `None` nếu quét được. NGUỒN SỰ THẬT DUY NHẤT cho câu hỏi này, dùng
	chung bởi `_can_quet_dong` (bool), `mo_phieu_giao` (câu chữ hiện ở dòng mờ)
	và gián tiếp bởi `hoan_tat` (dòng nào phải xét).

	VÒNG SỬA CUỐI (review toàn nhánh, Critical): TRƯỚC bản vá này, `can_quet`
	chỉ hỏi `kho_co_quan_ly_vi_tri(d.warehouse)` — dòng phí vận chuyển/dịch vụ/
	hàng đặt ngoài/dòng cha Product Bundle (ERPNext vẫn gán `warehouse` cho
	chúng dù không phải hàng tồn kho) vẫn hiện lên đòi quét, nhưng `ton_o` của
	chúng luôn 0 nên quét gì cũng bị chặn "ô chỉ còn 0" — phiếu kẹt cứng cả hai
	chiều (quét lẫn duyệt tay). Thêm điều kiện `is_stock_item`.

	VÒNG SỬA CUỐI (Important): dòng bán theo đơn vị KHÁC đơn vị tồn kho
	(`conversion_factor != 1`, vd bán theo Hộp trong khi tồn tính theo Cái) bị
	CHẶN có chữ thay vì cho quét rồi vỡ ở hook ghi sổ — bảng phân bổ
	(`custom_phan_bo_vi_tri`) đo bằng ĐƠN VỊ TỒN KHO (hook so tổng phân bổ với
	`stock_qty`), trong khi `mo_phieu_giao`/trang PDA nói chuyện bằng đơn vị
	GIAO DỊCH (`d.qty`, `d.stock_uom` bị gán nhầm nhãn cho `d.uom`) — hai bên
	lệch hệ đơn vị thì "phân bổ 2 nhưng xuất 20" (Hộp vs Cái) là câu báo thủ
	kho không thể tự sửa. Quy đổi đúng spec §3.1 là việc RỘNG (cần bộ test đa
	đơn vị riêng, ngoài phạm vi vòng sửa cuối này) — chặn có chữ trước, quy đổi
	sau.
	"""
	if not kho_co_quan_ly_vi_tri(d.warehouse):
		return _("Kho không quản lý vị trí — lấy tay, không cần quét.")
	if not frappe.get_cached_value("Item", d.item_code, "is_stock_item"):
		return _("Mặt hàng không quản lý tồn kho — lấy tay, không cần quét.")
	if flt(d.conversion_factor) not in (0, 1):
		return _("Dòng bán theo {0}, lấy tay trên form.").format(d.uom or d.stock_uom or "—")
	return None


def _can_quet_dong(d) -> bool:
	"""Dòng `d` có quét được trên trang Lấy hàng không — xem `_ly_do_khong_quet_dong`
	cho từng lý do. Dùng CHUNG cho `mo_phieu_giao` (khoá `can_quet`) LẪN
	`hoan_tat` (dòng nào phải xét "đã lấy đủ") — lệch nhau giữa hai nơi này
	(trước bản vá: `mo_phieu_giao` hỏi kho, `hoan_tat` cũng chỉ hỏi kho, nhưng
	không hàm nào hỏi mặt hàng có phải hàng tồn kho không) là đúng bug khiến
	phiếu có dòng dịch vụ/Product Bundle kẹt cứng cả hai chiều.
	"""
	return _ly_do_khong_quet_dong(d) is None


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

	LỌC PHIẾU TRẢ HÀNG (VÒNG SỬA CUỐI, review toàn nhánh): loại bỏ
	`dn.is_return = 1` ngay trong câu SQL. Phiếu trả có `qty` ÂM — mở nó ra
	trên trang Lấy hàng (nghĩ cho hàng XUẤT) chỉ tổ nhận những câu báo khó
	hiểu (số lượng cần lấy âm, "ô chỉ còn X" so với một số âm) mà trang này
	chưa nghĩ cho luồng nhận hàng trả về.
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
				where dn.docstatus = 0 and dn.is_return = 0 and dni.warehouse = %(kho)s
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

	`thieu_trong_lo`/CHẶN XIN QUÁ TỒN TRƯỚC KHI GỌI (sửa lỗi "mở phiếu bật hộp
	lỗi", đo trên site thử, ca A→Z): TRƯỚC bản vá này, dòng cần nhiều hơn tồn
	của (mặt hàng, lô) — CA HAY GẶP NHẤT của trang (lô trên dòng không đủ cả
	dòng, phải tách sang lô khác) — gọi thẳng `chon_o_xuat(..., con_can)`,
	`chon_o_xuat` `frappe.throw` khi không đủ; ở đây bắt được ngoại lệ (không
	nổ ra ngoài) NHƯNG `frappe.throw` đã đẩy câu báo vào
	`frappe.local.message_log` TRƯỚC KHI ném — trình duyệt đọc thẳng
	`message_log` của response nên vẫn bật hộp lỗi ngay màn MỞ PHIẾU, đúng thứ
	spec §6.2 cấm. Sửa: hỏi TỔNG tồn còn lại của (mặt hàng, lô) trong CẢ KHO
	(`tong_ton_vi_tri`, cộng mọi ô kể cả ô ngừng dùng — luôn là CẬN TRÊN an
	toàn) TRƯỚC, rồi chỉ xin `chon_o_xuat` đúng `min(con_can, tong_con)` — số
	xin không bao giờ vượt tồn nên hàm không còn lý do để ném ở đúng ca này.
	`tong_con <= 0` thì trả gợi ý rỗng, KHÔNG gọi `chon_o_xuat` (không có gì để
	xin). `thieu_trong_lo` = phần CÒN THIẾU sau khi lấy hết sạch (mặt hàng, lô)
	đang chốt trên dòng (`con_can - tong_con`, không âm) — để trang hiện một
	dòng chữ BÌNH THƯỜNG ("lô này chỉ còn…"), không phải một hộp lỗi.

	`khop_nghia_so_lo_none` (đo lại sau review): cap theo `tong_con` CHỈ đúng
	khi `tong_ton_vi_tri(..., d.batch_no or None)` và `chon_o_xuat(...,
	d.batch_no or None, ...)` cùng hiểu `so_lo=None` theo MỘT nghĩa — đúng khi
	dòng ĐÃ chốt lô (`d.batch_no` có giá trị), hoặc mặt hàng KHÔNG quản lý lô
	(`has_batch_no=0`, chỉ có một "lô" duy nhất là `None`). Dòng của mặt hàng
	CÓ quản lý lô nhưng CHƯA chốt lô nào (`d.batch_no` rỗng — ca thường của
	phiếu tạo từ đơn bán, trước khi thủ kho quét tem lô đầu tiên, xem
	`quet_de_lay` nhánh `can_quet_lo`) thì HAI hàm LỆCH nghĩa:
	`tong_ton_vi_tri(..., None)` chỉ cộng các dòng KHÔNG LÔ trong bộ đệm (gần
	như luôn ~0 cho một mặt hàng có lô), trong khi `chon_o_xuat` với
	`so_lo=None` nghĩa là "mọi lô, chọn theo FEFO" và vẫn thấy đầy đủ tồn CHÉO
	LÔ. Cap theo `tong_con` ở đúng ca này sẽ SAI — biến một gợi ý cross-lô hợp
	lệ thành "cả dòng đều thiếu". Ca đó (`not khop_nghia_so_lo_none`) BỎ QUA
	cap, giữ NGUYÊN hành vi gọi thẳng `chon_o_xuat(con_can)` như TRƯỚC bản vá
	(lưới an toàn message_log bên dưới vẫn áp dụng y hệt, phòng ca hết hàng
	thật).

	Lưới an toàn: yêu cầu gửi cho `chon_o_xuat` đã bị chặn theo TỔNG tồn (gồm
	cả ô ngừng dùng) nên `chon_o_xuat` (chỉ xét ô ĐANG DÙNG) vẫn có thể ném
	nếu phần thiếu đang kẹt ở (các) ô ngừng dùng — hiếm, nhưng câu báo đó vẫn
	không được lọt ra màn mở phiếu. Ghi nhớ độ dài `frappe.local.message_log`
	TRƯỚC lần gọi, và trong `except` cắt hẳn về đúng độ dài đó — gỡ sạch các
	câu vừa bị `frappe.throw` thêm vào ở lần gọi NÀY, không đụng câu báo có
	từ trước (nếu có) — rồi vẫn `frappe.log_error` như cũ.

	TRỪ PHẦN ĐÃ LÊN PHIẾU NHÁP (sửa lỗi đo trên tài liệu ảnh `22b`, sau khi
	lỗi "mở phiếu bật hộp lỗi" ở trên đã sửa): thủ kho quét lấy hết một ô rồi
	mở lại/nạp lại phiếu — trước bản vá này, gợi ý "Nên lấy" vẫn hiện NGUYÊN
	ô đó, vì `Location Balance` (nguồn của `chon_o_xuat`/`tong_ton_vi_tri`)
	chỉ đổi lúc DUYỆT phiếu, không đổi lúc ghi bảng phân bổ nháp. Nhánh
	`khop_nghia_so_lo_none` giờ TRỪ khỏi mỗi ô đúng số đã phân bổ cho (mặt
	hàng, lô) đó trên CHÍNH phiếu này (`_da_phan_bo_o_theo_mat_hang_lo`, gộp
	qua MỌI dòng hàng cùng mặt hàng/lô — hai dòng hàng khác nhau cùng giữ
	một ô vẫn phải trừ chung) TRƯỚC khi đưa vào gợi ý và trước khi tính
	`thieu_trong_lo`. Để không cắt xén nhầm balance THẬT của một ô đang bị
	giữ một phần (xem chú thích tại chỗ gọi `chon_o_xuat(..., tong_con)`),
	luôn xin ĐỦ `tong_con` (không phải phần còn cần `con_can`) rồi TỰ gom đủ
	`con_can` theo đúng thứ tự FEFO mà `chon_o_xuat` trả về, bỏ qua (không
	đẩy vào gợi ý) mọi ô mà số dư sau khi trừ đã về `<= 0`. Chỉ áp dụng cho
	nhánh `khop_nghia_so_lo_none` — dòng CHƯA chốt lô nào (nhánh còn lại)
	không thể có phân bổ của CHÍNH nó để trừ (xem chú thích tại đó).

	`can_quet` (bổ sung điều phối, cùng đợt với quyết định mở rộng `hoan_tat`
	ở Task 5 — sửa bất đối xứng đọc/ghi): `False` khi kho của dòng đó KHÔNG
	bật quản lý vị trí — `hoan_tat` đã BỎ QUA đúng những dòng này (xem
	`kho_co_quan_ly_vi_tri`), nên trang phải biết để hiện mờ/không đòi quét,
	KHÔNG lọc bỏ hẳn dòng khỏi danh sách: thủ kho vẫn phải lấy tay những dòng
	đó (giao thường, không qua sổ vị trí) — giấu dòng đi là giấu việc còn
	phải làm.

	VÒNG SỬA CUỐI (review toàn nhánh): `can_quet`/`ly_do_khong_quet` giờ đi
	qua `_can_quet_dong`/`_ly_do_khong_quet_dong` — dùng CHUNG với `hoan_tat`,
	không hỏi lại `kho_co_quan_ly_vi_tri` một mình nữa (xem docstring hai hàm
	đó cho ba lý do phân biệt: kho không quản lý vị trí, mặt hàng không tồn
	kho, dòng đa đơn vị). `ly_do_khong_quet` cho trang hiện đúng câu thay vì
	một câu chung chung duy nhất. Cũng bỏ gọi `chon_o_xuat` cho MỌI dòng không
	quét được (không chỉ dòng kho không quản lý vị trí như trước): dòng dịch
	vụ/đa đơn vị cũng không có gợi ý ô nào có nghĩa, gọi vẫn nuốt được lỗi
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
		ly_do_khong_quet = _ly_do_khong_quet_dong(d)
		can_quet = ly_do_khong_quet is None
		con_can = flt(d.qty) - da.get(d.name, 0.0)
		goi_y = []
		thieu_trong_lo = 0.0
		if can_quet and con_can > 0:
			# Lưới AN TOÀN chỉ hợp lệ khi `tong_ton_vi_tri(..., d.batch_no or None)` và
			# `chon_o_xuat(..., d.batch_no or None, ...)` CÙNG nghĩa với `so_lo=None`
			# — đúng khi dòng ĐÃ chốt lô (`d.batch_no` có giá trị), hoặc mặt hàng
			# KHÔNG quản lý lô (`has_batch_no=0`, chỉ có một "lô" duy nhất là None).
			# Dòng của mặt hàng CÓ quản lý lô nhưng CHƯA chốt lô nào (`d.batch_no`
			# rỗng — ca thường của phiếu tạo từ đơn bán, xem `quet_de_lay` nhánh
			# `can_quet_lo`) thì hai hàm LỆCH nghĩa: `tong_ton_vi_tri(..., None)` chỉ
			# cộng các dòng KHÔNG LÔ (luôn ~0 cho mặt hàng có lô), còn `chon_o_xuat`
			# (`so_lo=None` = "mọi lô, theo FEFO") vẫn thấy đầy đủ tồn CHÉO LÔ — cap
			# theo `tong_con` sẽ SAI, biến gợi ý cross-lô hợp lệ thành "thiếu cả dòng".
			# Ca đó bỏ qua cap VÀ bỏ qua trừ phần đã lên phiếu (xem nhánh dưới) —
			# giữ NGUYÊN hành vi gọi thẳng `chon_o_xuat(con_can)` như trước bản vá
			# (lưới an toàn message_log vẫn áp dụng như cũ). Dòng kiểu này chưa từng
			# có lượt ghi nào của CHÍNH nó (ghi_da_lay đòi lô quét khớp `d.batch_no`,
			# nên `d.batch_no` rỗng thì không dòng phân bổ nào có thể thuộc về nó),
			# nên không có gì của dòng NÀY để trừ; phần "dòng khác cùng mặt hàng đã
			# chốt lô cụ thể giữ mất một ô" là một khe hẹp hơn, ngoài phạm vi bản vá
			# này (ghi vào "điều còn lo").
			khop_nghia_so_lo_none = bool(d.batch_no) or not frappe.get_cached_value(
				"Item", d.item_code, "has_batch_no"
			)
			if khop_nghia_so_lo_none:
				tong_con = flt(tong_ton_vi_tri(d.warehouse, d.item_code, d.batch_no or None))
				# Sửa lỗi đo trên tài liệu ảnh `22b`: TRỪ phần đã lên phiếu NHÁP của
				# CHÍNH (mặt hàng, lô) này — gộp qua MỌI dòng hàng cùng (mặt hàng,
				# lô), không chỉ dòng đang xét (xem `_da_phan_bo_o_theo_mat_hang_lo`)
				# — trước khi tính "còn thiếu" và trước khi đưa vào gợi ý. Không trừ
				# thì một ô vừa bị CHÍNH phiếu này lấy hết vẫn được gợi ý lại nguyên
				# vẹn, vì `Location Balance` (nguồn của `chon_o_xuat`) chỉ đổi lúc
				# DUYỆT phiếu, không đổi lúc ghi bảng phân bổ nháp.
				da_phan_bo_o = _da_phan_bo_o_theo_mat_hang_lo(
					doc, d.warehouse, d.item_code, d.batch_no or None
				)
				tong_da_phan_bo = flt(sum(da_phan_bo_o.values()))
				tong_kha_dung = flt(max(tong_con - tong_da_phan_bo, 0.0))
				thieu_trong_lo = flt(max(con_can - tong_kha_dung, 0.0))
				if tong_con > 0:
					# Xin ĐÚNG `tong_con` (không phải `min(con_can, tong_con)`): chỉ
					# yêu cầu đủ để thoả `con_can` thì `chon_o_xuat` có thể CẮT XÉN
					# balance thật của ô cuối cùng nó chạm tới giữa chừng — nếu đúng
					# ô đó lại là ô CHÍNH phiếu này đã giữ một phần, phép trừ dưới đây
					# sẽ trừ nhầm trên một con số đã bị cắt xén, không phải tồn THẬT
					# của ô. Xin đủ TOÀN BỘ `tong_con` đảm bảo mọi ô trong danh sách
					# trả về mang đúng SỐ DƯ THẬT của nó (không ô nào bị cắt giữa
					# chừng), rồi TỰ gom đủ `con_can` (sau khi trừ phần đã lên phiếu)
					# ở vòng lặp bên dưới — vẫn giữ nguyên thứ tự FEFO của
					# `chon_o_xuat` vì duyệt đúng thứ tự danh sách nó trả về.
					do_dai_truoc = len(frappe.local.message_log)
					try:
						ung_vien_tho = chon_o_xuat(d.warehouse, d.item_code, d.batch_no or None, tong_con)
					except Exception:
						del frappe.local.message_log[do_dai_truoc:]
						# `tong_con` (từ `tong_ton_vi_tri`) cộng CẢ ô ngừng dùng, còn ứng
						# viên của `chon_o_xuat` thì KHÔNG — hàng kẹt ở (các) ô ngừng dùng
						# (thao tác vận hành bình thường, xem docstring `fefo.py`) làm xin
						# đủ `tong_con` ném, dù xin đúng phần CẦN (`con_can + tong_da_phan_bo`,
						# luôn `<= tong_con`) vẫn có thể đủ. Thử lại với số nhỏ hơn đó trước
						# khi bỏ cuộc — thiếu đúng MỘT ô (ô cuối chạm ranh giới có thể bị
						# cắt xén, số gợi ý ở đó hụt) vẫn hơn hẳn MẤT TRẮNG gợi ý.
						do_dai_truoc = len(frappe.local.message_log)
						try:
							ung_vien_tho = chon_o_xuat(
								d.warehouse,
								d.item_code,
								d.batch_no or None,
								min(con_can + tong_da_phan_bo, tong_con),
							)
						except Exception:
							del frappe.local.message_log[do_dai_truoc:]
							frappe.log_error(
								title=cat_tieu_de(f"vi_tri_kho: mo_phieu_giao goi y loi ({phieu})")
							)
							ung_vien_tho = []
					can_thieu = con_can
					for g in ung_vien_tho:
						if can_thieu <= _SAI_SO:
							break
						con_o = flt(flt(g["so_luong"]) - da_phan_bo_o.get(g["o"], 0.0))
						if con_o <= _SAI_SO:
							continue
						lay = min(con_o, can_thieu)
						goi_y.append({"o": g["o"], "so_luong": lay})
						can_thieu = flt(can_thieu - lay)
			else:
				can_xin = con_can
				if can_xin > 0:
					do_dai_truoc = len(frappe.local.message_log)
					try:
						goi_y = chon_o_xuat(d.warehouse, d.item_code, d.batch_no or None, can_xin)
					except Exception:
						del frappe.local.message_log[do_dai_truoc:]
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
				"ly_do_khong_quet": ly_do_khong_quet,
				"thieu_trong_lo": thieu_trong_lo,
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
		"docstatus": doc.docstatus,
		"kho": doc.set_warehouse or (doc.items[0].warehouse if doc.items else None),
		"khach_hang": doc.customer_name or doc.customer,
		"dong": dong,
	}


def _da_het_han(hsd) -> bool:
	"""Lô có hạn dùng `hsd` đã hết hạn tính tới HÔM NAY THẬT hay chưa —
	NGUỒN SỰ THẬT DUY NHẤT cho câu hỏi này, dùng chung bởi `quet_de_lay` (cả
	nhánh `lo` lẫn `lo_khac`) và `_chan_lo_het_han` (`ghi_da_lay`).

	BẪY ĐÃ ĐO (vòng sửa cuối, khi viết bài test): `frappe.db.get_value(...,
	"expiry_date")` trả về `datetime.date`, còn `nowdate()` trả về CHUỖI
	(`"YYYY-MM-DD"`) — so trực tiếp `date < str` ném `TypeError`, và vì
	`quet_de_lay` bọc toàn bộ nhánh nhận diện trong một `except Exception`
	("quét nhầm không bao giờ nổ"), lỗi kiểu này bị NUỐT ÂM THẦM thành
	`{"loai": None}` — biến một bug thật thành "không nhận ra mã", im lặng
	đúng kiểu module này phải tránh. `getdate()` chuẩn hoá cả hai vế về cùng
	kiểu `date` trước khi so.
	"""
	if not hsd:
		return False
	return getdate(hsd) < getdate(nowdate())


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

	`loai`: `"lo"` (lô ĐANG có trên phiếu, HOẶC mã của một mặt hàng KHÔNG quản lý
	lô — xem điểm điều phối bên dưới) · `"lo_khac"` (lô khác nhưng cùng một mặt
	hàng của phiếu — kèm `han_xa_hon` để màn hình cảnh báo) · `"can_quet_lo"`
	(mã của một mặt hàng CÓ quản lý lô — không biết lô nào, không đoán) · `"o"` ·
	`None`. Quét nhầm không bao giờ nổ — cùng lời hứa `quet.py`.

	`het_han` (VÒNG SỬA CUỐI, review toàn nhánh, Critical) — cả nhánh `"lo"` lẫn
	`"lo_khac"` đều mang khoá này: `True` khi lô VỪA QUÉT đã hết hạn so với HÔM
	NAY THẬT (`nowdate()`), không phải so với `posting_date` của phiếu (lớp
	kiểm cốt lõi `StockController.validate_serialized_batch` chỉ so với
	`posting_date`, không bắt được lô hết hạn TRONG LÚC phiếu nằm nháp chờ
	lấy). Trang PHẢI chặn hẳn, không cho chuyển sang dòng đó khi thấy cờ này —
	đây là công ty vật tư y tế, giao một lô hết hạn là sự cố có hồ sơ.

	`dong_hang` (Important 3): phiếu có nhiều dòng cùng mặt hàng thì không thể
	tự đoán ĐÚNG dòng chỉ từ mã quét — xem `_chon_dong_ung_vien`. `nhieu_dong`
	trong kết quả báo cho màn hình biết có từ hai dòng ứng viên trở lên, để
	hỏi lại người dùng khi cần.

	QUYẾT ĐỊNH ĐIỀU PHỐI (sau review Task 7 — trước bản vá này, spec §6.2 bị
	thủng): `mo_phieu_giao` trả dòng của mặt hàng KHÔNG quản lý lô với
	`so_lo = None`, `can_quet = True` (đúng thiết kế — kho có quản lý vị trí thì
	dòng đó vẫn phải lấy theo ô), nhưng hàm này TRƯỚC bản vá chỉ nhận diện được
	mã quét qua `scan_barcode(...).get("batch_no")` — quét mã của một mặt hàng
	không lô luôn rơi vào `{"loai": None}` ("không nhận ra mã"). Hậu quả: dòng đó
	không bao giờ bắt đầu lấy được, và `hoan_tat` (đòi MỌI dòng thuộc kho quản lý
	vị trí phải lấy đủ) khoá cứng phiếu vĩnh viễn. Vá bằng cách thêm nhánh nhận
	diện MẶT HÀNG, theo đúng khuôn `xep.quet_de_xep` (đã có sẵn hai đường: mã vạch
	trên bao bì qua `scan_barcode` → `item_code`, hoặc mã quét trùng thẳng tên một
	`Item`) — không phải nghĩ lại, chỉ mở rộng cho đúng thiết kế đã có ở trang chị
	em. Mặt hàng CÓ quản lý lô thì KHÔNG được đoán lô: trả `can_quet_lo` để trang
	nhắc quét đúng tem lô trên thùng, cùng lời hứa "không đoán" của `_chon_dong_ung_vien`.
	Mã trùng một `Item` nhưng mặt hàng đó không có dòng nào trên phiếu thì GIỮ
	NGUYÊN hành vi cũ (không nhận bừa) — nhận diện được một `Item` bất kỳ không có
	nghĩa nó thuộc phiếu đang lấy.
	"""
	from erpnext.stock.utils import scan_barcode
	from erpnext.warehouse_operations.vitri.quet import _tim_o

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
				# VÒNG SỬA CUỐI (review toàn nhánh, Critical): lô ĐANG CHỐT trên
				# dòng có thể đã hết hạn TỪ LÚC nào đó trong khi phiếu vẫn nháp —
				# `posting_date` của phiếu không đổi nên lớp kiểm cốt lõi
				# (`StockController.validate_serialized_batch`, so `expiry_date` với
				# `posting_date`) không bắt được. Kiểm với HÔM NAY thật
				# (`nowdate()`), không phải `posting_date`.
				hsd = frappe.db.get_value("Batch", so_lo, "expiry_date")
				return {
					"loai": "lo",
					"so_lo": so_lo,
					"dong_hang": d.name,
					"vat_tu": d.item_code,
					"nhieu_dong": len(ung_vien_lo) > 1,
					"hsd": hsd,
					"het_han": _da_het_han(hsd),
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
					# VÒNG SỬA CUỐI (review toàn nhánh, Critical): lô hết hạn có HSD
					# GẦN HƠN lô đang chốt thì `han_xa_hon = False` — trang trước bản
					# vá nhận ngay, chỉ cảnh báo nhẹ. Thao tác nguy hiểm nhất (giao lô
					# hết hạn) lại dễ nhất. Kiểm ĐỘC LẬP với `han_xa_hon`, so lô MỚI
					# quét với HÔM NAY thật, không phải với lô đang chốt.
					"het_han": _da_het_han(hsd_moi),
				}
			return {"loai": None}

		vat_tu = kq.get("item_code")
		if not vat_tu and not kq.get("warehouse") and frappe.db.exists("Item", ma):
			vat_tu = ma
		if vat_tu:
			ung_vien_hang = [d for d in doc.items if d.item_code == vat_tu]
			if ung_vien_hang:
				if frappe.db.get_value("Item", vat_tu, "has_batch_no"):
					return {
						"loai": "can_quet_lo",
						"vat_tu": vat_tu,
						"ten_hang": frappe.db.get_value("Item", vat_tu, "item_name"),
					}
				d = _chon_dong_ung_vien(ung_vien_hang, da, dong_hang)
				if not d:
					return {"loai": None}
				return {
					"loai": "lo",
					"so_lo": None,
					"dong_hang": d.name,
					"vat_tu": vat_tu,
					"nhieu_dong": len(ung_vien_hang) > 1,
					# Mặt hàng không quản lý lô — không có hạn dùng để hết.
					"hsd": None,
					"het_han": False,
				}
			# Mặt hàng có thật nhưng không có dòng nào trên phiếu này — không nhận
			# bừa (cùng nguyên tắc "quét nhầm không bao giờ nổ, nhưng cũng không
			# bao giờ NHẬN NHẦM" đã áp cho nhánh lô ở trên).

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


def _chan_lo_het_han(so_lo: str | None) -> None:
	"""CHẶN ghi nhận một lượt lấy cho lô ĐÃ HẾT HẠN — quyết định vòng review
	toàn nhánh: chặn ngay ở TẦNG MÁY CHỦ, không chỉ ở trang. `quet_de_lay`
	(đọc) đã trả `het_han` để trang chặn hẳn không cho chuyển sang dòng đó,
	nhưng `ghi_da_lay` là endpoint whitelisted gọi thẳng được — một trang JS
	cũ (chưa vá) hoặc một script gọi API trực tiếp vẫn có thể lách qua lớp
	chặn ở trang nếu tầng máy chủ không tự mình kiểm lại. Đây là công ty vật
	tư y tế: giao một lô hết hạn là sự cố có hồ sơ, không phải lỗi vặt UI —
	đường API không được phép là lối thoát.

	So với HÔM NAY THẬT (`nowdate()`), không phải `posting_date` của phiếu —
	cùng lý do đã nêu ở `quet_de_lay`: lô có thể hết hạn TRONG LÚC phiếu nằm
	nháp chờ lấy, sau khi `posting_date` đã cố định.
	"""
	if not so_lo:
		return
	hsd = frappe.get_cached_value("Batch", so_lo, "expiry_date")
	if _da_het_han(hsd):
		frappe.throw(
			_(
				"Lô {0} đã hết hạn ngày {1} — không ghi nhận lấy hàng qua trang này. Muốn xuất "
				"lô hết hạn thì thao tác trực tiếp trên form Phiếu giao hàng (máy tính)."
			).format(so_lo, formatdate(hsd))
		)


def _ton_o_con_lai_tren_phieu(doc, o: str, vat_tu: str, so_lo: str | None) -> float:
	"""Tồn CÒN LẠI của một (ô, vật tư, lô) sau khi trừ các lượt ĐÃ GHI trên
	CHÍNH phiếu `doc` — gộp theo (o, vat_tu, so_lo), KHÔNG theo dòng hàng, đúng
	cách `kiem_phan_bo_khi_luu` (`theo_o`) gộp để so với `ton_o` lúc validate:
	hai DÒNG HÀNG khác nhau cùng vật tư/lô rút chung một ô vẫn phải cộng dồn
	vào MỘT sổ duy nhất, không mỗi dòng tự so với tồn ĐẦY ĐỦ của ô.

	Dùng cho `lay_toi_da_theo_o` của `ghi_da_lay`: số CÒN LẤY ĐƯỢC tiếp ở đúng
	(ô, vật tư, lô) này trên phiếu đang quét dở, TRƯỚC khi cộng thêm lượt mới.
	"""
	da = sum(
		flt(p.so_luong)
		for p in doc.get(TEN_BANG_PHAN_BO) or []
		if p.o == o and p.vat_tu == vat_tu and (p.so_lo or None) == (so_lo or None)
	)
	return flt(ton_o(o, vat_tu, so_lo) - da)


@frappe.whitelist()
def ghi_da_lay(
	phieu: str, dong_hang: str, so_lo: str | None, o: str, so_luong, lay_toi_da_theo_o: int = 0
) -> dict:
	"""Ghi một lần quét (lô, ô, số lượng) vào bảng phân bổ và LƯU NGAY.

	Lưu ngay chứ không gom trong trình duyệt: PDA hết pin giữa ca là mất cả chục
	lượt quét mà thủ kho đã đi lấy thật ngoài kệ — cùng lẽ với trang xếp hàng.

	Cùng (dòng hàng, lô, ô) thì CỘNG DỒN vào dòng phân bổ sẵn có, không đẻ dòng mới.

	VÒNG SỬA CUỐI (review toàn nhánh, Important): gọi `_chan_bundle_serial_batch`
	— hàm ghi DUY NHẤT của module này trước đó CHƯA gọi nó (`doi_lo`,
	`tach_dong_theo_lo`, `chot_thieu` đều gọi), lệch một nguồn sự thật.

	`lay_toi_da_theo_o` (sửa lỗi "số lượng mặc định không tự cắt theo tồn của
	ô", đo trên site thử): trang đặt số lượng MẶC ĐỊNH = toàn bộ phần còn thiếu
	của dòng, nhưng ô gợi ý (hoặc ô thủ kho tự quét) có thể có ÍT hơn — trước
	bản vá, lớp kiểm sớm (`kiem_phan_bo_khi_luu`) luôn chặn với "chỉ còn…",
	thủ kho phải TỰ sửa số rồi quét LẠI. `0` (mặc định) = hành vi CŨ, ghi đúng
	`so_luong` yêu cầu, để nguyên cho lớp kiểm sớm chặn nếu vượt tồn — dùng khi
	NGƯỜI DÙNG đã tự gõ số (cắt âm thầm số người dùng nhập là đổi ý định của
	họ, không được làm). Khác `0`: cắt `so_luong` xuống
	`min(so_luong, _ton_o_con_lai_tren_phieu(...))` — chỉ CẮT XUỐNG, không bao
	giờ TĂNG LÊN; tồn còn lại `<= 0` thì GIỮ NGUYÊN `so_luong` yêu cầu (không
	cắt về 0 hay số âm — để lớp kiểm sớm chặn với câu báo "chỉ còn…" như hiện
	nay, đúng hành vi cũ cho ca hết sạch ô). Trả thêm `so_luong_da_ghi` (số
	THẬT đã ghi, sau khi cắt nếu có) để trang báo đúng cho thủ kho.
	"""
	so_lo = so_lo or None
	so_luong = flt(so_luong)
	if so_luong <= 0:
		frappe.throw(_("Số lượng lấy phải lớn hơn 0."))
	_chan_lo_het_han(so_lo)

	doc = _mo_de_ghi(phieu)
	d = _dong_cua(doc, dong_hang)
	_chan_bundle_serial_batch(d)
	if (d.batch_no or None) != so_lo:
		frappe.throw(
			_("Dòng hàng đang chốt lô {0}, không phải {1}. Đổi lô trước khi ghi.").format(
				d.batch_no or "—", so_lo or "—"
			)
		)

	so_that_ghi = so_luong
	if cint(lay_toi_da_theo_o):
		con_lai = _ton_o_con_lai_tren_phieu(doc, o, d.item_code, so_lo)
		# VÒNG SỬA (review độc lập, model mạnh): `> 0` (không có ngưỡng) cho một
		# ô LẺ chút xíu (nhiễu dấu phẩy động, vd `con_lai = 0.0000000003`) ghi
		# một lượt gần-như-0 kèm câu báo "Ô X chỉ còn 0" — đúng thứ hỏng module
		# này phải tránh (`_SAI_SO` đã dùng CHUNG cho mọi so sánh `<=0`/`>0` số
		# lượng khác trong file, xem `kiem_phan_bo_khi_luu`).
		if con_lai > _SAI_SO:
			so_that_ghi = min(so_luong, con_lai)

	trung = next(
		(
			p
			for p in doc.get(TEN_BANG_PHAN_BO) or []
			if p.dong_hang == dong_hang and (p.so_lo or None) == so_lo and p.o == o
		),
		None,
	)
	if trung:
		trung.so_luong = flt(trung.so_luong) + so_that_ghi
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
				"so_luong": so_that_ghi,
				"nguoi_lay": frappe.session.user,
				"luc_lay": now(),
			},
		)
	_luu_hoac_bao_xung_dot(doc)
	ket_qua = mo_phieu_giao(phieu)
	ket_qua["so_luong_da_ghi"] = so_that_ghi
	return ket_qua


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
def tach_dong_theo_lo(phieu: str, dong_hang: str, so_lo_moi: str) -> dict:
	"""Lô cũ hết giữa chừng: chốt dòng cũ ở số ĐÃ LẤY, đẻ dòng mới cho phần còn lại.

	`Stock Settings.use_serial_batch_fields = 1` trên site này (đo 18/09/2026) nên
	MỘT DÒNG phiếu giao chỉ mang MỘT lô — không tách thì không có chỗ nào ghi lô
	thứ hai, và duyệt sẽ nổ "Batch No … has negative stock".

	Chỉ tách khi dòng cũ ĐÃ lấy được một phần: chưa lấy gì thì đó là ĐỔI LÔ
	(`doi_lo`), và tách ra một dòng 0 là để lại rác trên chứng từ bán hàng.

	Dòng mới KHÔNG mang theo `serial_and_batch_bundle` của dòng cũ — trang Lấy
	hàng chưa hỗ trợ luồng bundle (xem `_chan_bundle_serial_batch`), và bundle cũ
	dù sao cũng chỉ khớp số lượng/lô CŨ, không khớp phần tách ra.

	VÒNG SỬA 1/5 Task 6 (review điều phối), Important 3 — LỐI THOÁT nếu dòng CŨ
	sau khi tách lại bị `bo_dong_da_lay` bỏ hết phân bổ (quét nhầm rồi bỏ): dòng
	đó còn `qty > 0` nhưng `đã lấy = 0`, và `hoan_tat` sẽ chặn nó — trang PDA
	KHÔNG có hàm xoá dòng `Delivery Note Item` nào, nên lối thoát THẬT là quét
	lấy lại cho đúng dòng đó, `doi_lo` (vẫn dùng được vì dòng không còn phân bổ
	nào), hoặc bỏ dòng thẳng trên form Phiếu giao hàng ở máy tính — KHÔNG phải
	kẹt cứng, xem câu báo tại `hoan_tat`.
	"""
	doc = _mo_de_ghi(phieu)
	d = _dong_cua(doc, dong_hang)
	_chan_bundle_serial_batch(d)
	da = flt(_da_lay_theo_dong(doc).get(dong_hang, 0.0))
	con_lai = flt(d.qty) - da

	if da <= _SAI_SO:
		frappe.throw(
			_(
				"Dòng {0} ({1}) chưa lấy được gì của lô {2} — dùng 'Đổi lô' thay vì tách dòng."
			).format(d.idx, d.item_code, d.batch_no or "—")
		)
	if con_lai <= _SAI_SO:
		frappe.throw(
			_("Dòng {0} ({1}) đã lấy đủ {2}, không còn gì để tách.").format(
				d.idx, d.item_code, flt(d.qty, 3)
			)
		)

	if not frappe.db.exists("Batch", so_lo_moi):
		frappe.throw(_("Lô {0} không tồn tại.").format(so_lo_moi))
	chu = frappe.db.get_value("Batch", so_lo_moi, "item")
	if chu != d.item_code:
		frappe.throw(
			_("Lô {0} là lô của mặt hàng {1}, không phải {2}.").format(so_lo_moi, chu, d.item_code)
		)

	moi = {
		k: v
		for k, v in d.as_dict().items()
		if k
		not in (
			"name",
			"idx",
			"creation",
			"modified",
			"modified_by",
			"owner",
			"parent",
			"parentfield",
			"parenttype",
			"doctype",
			"serial_and_batch_bundle",
			# Minor 1 (vòng sửa 1/5 Task 6, review điều phối): mặt hàng vừa quản
			# lý lô vừa quản lý serial thì `serial_no` là danh sách text khớp
			# đúng `qty` CŨ — chép nguyên sang dòng mới (`qty` MỚI khác) để lại
			# một danh sách serial sai số lượng, cùng loại bẫy với
			# `serial_and_batch_bundle` ở trên.
			"serial_no",
			# Suất tính lại theo `qty` mới (recompute ở `validate`/tổng tiền) —
			# giữ nguyên số của dòng CŨ (qty=12) thì dòng mới ghi sổ nhầm số
			# lượng (`stock_qty`) dù `qty` hiển thị đã sửa đúng.
			"stock_qty",
			"amount",
			"base_amount",
			"net_amount",
			"base_net_amount",
			"amount_before_discount",
			"base_amount_before_discount",
			"tax_exclusive_amount",
			"base_tax_exclusive_amount",
		)
	}
	moi["qty"] = con_lai
	moi["batch_no"] = so_lo_moi

	# Minor 2 (vòng sửa 1/5 Task 6, review điều phối): `total_weight`/
	# `total_net_weight` chỉ được TÍNH LẠI Ở CLIENT (`transaction.js`,
	# `item.total_weight = stock_qty * weight_per_unit`) — server-side
	# `calculate_total_net_weight` (`taxes_and_totals.py`) chỉ CỘNG LẠI
	# `total_weight` có sẵn của từng dòng, không tự tính nó theo `qty` mới.
	# Chép nguyên `d.as_dict()` để lại `total_weight` của dòng CŨ (qty=12) trên
	# CẢ hai dòng sau tách — tổng trọng lượng phiếu gần gấp đôi, in sai lên vận
	# đơn. Tính tay theo đúng công thức client, không suy đoán: không có
	# `weight_per_unit` thì 0.
	conv = flt(d.conversion_factor) or 1.0
	wpu = flt(d.weight_per_unit)
	d.total_weight = flt(wpu * da * conv) if wpu else 0.0
	moi["total_weight"] = flt(wpu * con_lai * conv) if wpu else 0.0

	d.qty = da
	doc.append("items", moi)
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
	cậy tới savepoint bên dưới để dọn. Dòng KHÔNG quét được (`_can_quet_dong`
	— kho không quản lý vị trí, mặt hàng không phải hàng tồn kho, hoặc dòng
	đa đơn vị) thì BỎ QUA — hook ghi sổ không đụng tới chúng, không có ý
	nghĩa gì để đòi chúng "đã lấy đủ".

	VÒNG SỬA CUỐI (review toàn nhánh, Critical): điều kiện bỏ qua TRƯỚC ĐÂY
	chỉ hỏi `kho_co_quan_ly_vi_tri(d.warehouse)` một mình, lệch với chính
	`mo_phieu_giao` — dòng phí vận chuyển/dịch vụ/Product Bundle (kho CÓ quản
	lý vị trí nhưng KHÔNG phải hàng tồn kho, ERPNext vẫn gán `warehouse` cho
	chúng) trước đây vẫn bị hàm này đòi "đã lấy đủ" trong khi `ton_o` của
	chúng luôn 0, khoá cứng phiếu ở cả hai chiều (quét lẫn duyệt). Đổi sang
	`_can_quet_dong` — nguồn sự thật DUY NHẤT, dùng chung với `mo_phieu_giao`.

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
		if not _can_quet_dong(d):
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
			# Important 3 (vòng sửa 1/5 Task 6, review điều phối): câu báo TRƯỚC
			# đây khuyên "bỏ dòng khỏi phiếu giao" — trang PDA không có hàm nào
			# xoá dòng `Delivery Note Item`, nên đó là lời khuyên trỏ tới một
			# hành động không làm được ở đây (ca thật: `tach_dong_theo_lo` rồi
			# `bo_dong_da_lay` hết phân bổ của dòng cũ). Nêu đúng ba lối thoát
			# THẬT: quét lấy tiếp, đổi lô (`doi_lo`, vẫn dùng được vì dòng không
			# còn phân bổ), hoặc bỏ dòng trên form ở máy tính (không phải PDA).
			frappe.throw(
				_(
					"Dòng {0} ({1}) chưa lấy được gì — quét lấy cho dòng này, đổi lô nếu lấy "
					"nhầm lô, hoặc bỏ dòng trên form Phiếu giao hàng (máy tính). Không chốt "
					"thiếu 0 được."
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


@frappe.whitelist()
def tien_do_lay_hang(phieu: str) -> dict:
	"""Tiến độ lấy hàng cho dòng tóm tắt trên FORM Phiếu giao (19/09/2026).

	Nhẹ hơn `mo_phieu_giao`: không gọi FEFO, chỉ đếm từ bảng phân bổ và cờ chốt
	thiếu — form gọi hàm này MỖI lần mở phiếu. Đếm bằng đúng các luật mà trang
	PDA và `hoan_tat` dùng (`_can_quet_dong`, `_da_lay_theo_dong`,
	`_doc_chot_thieu`), nên con số trên form không bao giờ nói khác trang PDA.

	Chỉ cần quyền ĐỌC phiếu — kế toán/kinh doanh mở form cũng phải thấy tiến
	độ. `lay_duoc` cho biết người đang xem có nên thấy nút "Lấy hàng trên PDA"
	(phiếu nháp + có vai trò kho + có dòng quét được).

	`trang_thai`:
	- `khong_ap_dung`: phiếu trả hàng, hoặc không dòng nào quét được.
	- `chua_lay` / `dang_lay` / `du`: phiếu nháp. `du` = mọi dòng quét được
	  đã lấy đủ HOẶC đã chốt thiếu (đúng điều kiện `hoan_tat` cho qua).
	- `da_duyet_quet` / `da_duyet_fefo`: đã duyệt; sổ trừ theo ô đã quét hay
	  theo ô FEFO tự chọn.
	- `da_huy`.
	"""
	doc = frappe.get_doc("Delivery Note", phieu)
	doc.check_permission("read")

	dong_quet = [d for d in doc.items if _can_quet_dong(d)] if not doc.is_return else []
	bang = doc.get(TEN_BANG_PHAN_BO) or []
	da = _da_lay_theo_dong(doc)
	chot = _doc_chot_thieu(phieu) if doc.docstatus == 0 else {}

	so_du = 0
	so_chot = 0
	for d in dong_quet:
		if abs(flt(da.get(d.name, 0.0)) - flt(d.qty)) <= _SAI_SO:
			so_du += 1
		elif d.name in chot:
			so_chot += 1

	if not dong_quet:
		trang_thai = "khong_ap_dung"
	elif doc.docstatus == 2:
		trang_thai = "da_huy"
	elif doc.docstatus == 1:
		trang_thai = "da_duyet_quet" if bang else "da_duyet_fefo"
	elif not bang:
		trang_thai = "chua_lay"
	elif so_du + so_chot == len(dong_quet):
		trang_thai = "du"
	else:
		trang_thai = "dang_lay"

	return {
		"trang_thai": trang_thai,
		"so_dong_quet": len(dong_quet),
		"so_dong_du": so_du,
		"so_dong_chot_thieu": so_chot,
		"so_dong_khong_quet": len(doc.items) - len(dong_quet),
		# Theo đơn vị giao dịch của dòng — cùng thước đo `can_lay`/`da_lay` trên trang PDA.
		"tong_can": flt(sum(flt(d.qty) for d in dong_quet)),
		"tong_da_lay": flt(sum(flt(da.get(d.name, 0.0)) for d in dong_quet)),
		"nguoi_lay": sorted({p.nguoi_lay for p in bang if p.nguoi_lay}),
		"lay_duoc": bool(
			doc.docstatus == 0 and dong_quet and VAI_TRO_DUOC_LAY & set(frappe.get_roles())
		),
	}

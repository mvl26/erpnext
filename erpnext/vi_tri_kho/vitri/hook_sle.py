"""Hook ghi sổ vị trí, móc vào Stock Ledger Entry.on_submit.

Vì sao chỉ một hook: mọi chứng từ ghi sổ kho của ERPNext — Purchase Receipt,
Purchase Invoice, Delivery Note, Sales Invoice, Stock Entry, Stock
Reconciliation, Subcontracting Receipt, Asset Capitalization — đều tạo SLE
qua make_entry() rồi gọi sle.submit() (erpnext stock_ledger.py:221-227).
Móc ở đây bắt trọn cả tám, kể cả doctype ERPNext thêm về sau. Móc vào từng
doctype thì sót một cái là lệch âm thầm.

TASK 2 GĐ "Lấy hàng trên PDA" (2026-09-18, xem `_phan_bo_da_khai`): nhánh XUẤT
giờ đọc bảng phân bổ `Location Allocation` trước, chỉ rơi về FEFO khi chứng từ
không có phân bổ (đường cũ, hành vi không đổi cho Purchase Receipt/Stock
Entry/... — chỉ Delivery Note mới có giao diện phân bổ, xem `lay_hang.py`).

Thứ tự bên trong `ghi_so_vi_tri` là CỐ Ý và BẮT BUỘC: `tinh_delta(doc)` phải
chạy TRƯỚC mọi lời gọi `ghi_dong_so` cho CÙNG dòng SLE này. Nhánh kiểm kê
hàng không lô của `tinh_delta` (`vitri/delta.py`) tính delta bằng tồn mới
trừ tồn hiện có ĐỌC LẠI TỪ SỔ VỊ TRÍ (`tong_ton_vi_tri`) — nếu dòng sổ của
chính SLE đang xét đã được ghi trước đó, tồn "hiện có" đọc lại sẽ lẫn luôn
thay đổi của chính giao dịch này, delta luôn ra 0 và kiểm kê bị nuốt âm
thầm. `delta` được tính MỘT LẦN, gán vào biến cục bộ, rồi mới dùng để tách
lô và ghi sổ — không được tính lại bên trong vòng lặp ghi.

Dòng SLE có `is_cancelled = 1` (huỷ chứng từ — thứ tự THẬT trong
`erpnext/stock/stock_ledger.py:process_sl_entries`: `set_as_cancel()` cờ
CÁC DÒNG CŨ bằng SQL thô TRƯỚC (dòng ~66-70), RỒI MỚI vòng lặp sinh dòng SLE
MỚI với `actual_qty` đảo dấu qua `make_entry()` -> `sle.submit()` sau đó
(dòng ~80-90) — không phải chiều ngược lại. Hệ quả không đổi: dòng CŨ bị cờ
bằng SQL thô, không qua `submit()`, nên không tự kích hook lần hai; chỉ dòng
MỚI mới chạy hook) KHÔNG bị lọc bỏ ở đây — cố ý. Nó đi qua đúng đường của
một dòng SLE bình thường: tính delta (qua `tinh_delta`, xem `vitri/delta.py`
để biết delta có dấu đúng cho CẢ Stock Reconciliation lẫn các chứng từ khác
như thế nào), tách lô, dồn vào CHUA-XEP của `sle.warehouse`. Bỏ qua sẽ để
tồn vị trí đứng yên trong khi tồn kho ERPNext đã đổi — vi phạm bất biến
"tổng tồn các ô = tồn kho ERPNext" (spec §3) ngay từ ca huỷ đơn giản nhất.
Nhánh trả hàng về ĐÚNG Ô GỐC (không phải CHUA-XEP) là Task 9
(`dao_theo_o_goc`); ở Task 7, CHUA-XEP + `tinh_delta` đúng là điều kiện CẦN
để giữ đúng TỔNG toàn kho — đã đo đúng cho: huỷ Stock Entry hàng không lô,
huỷ Stock Entry hàng có lô (đúng ở mức TỔNG, xem phần "mất chiều lô" bên
dưới về mức lô), huỷ Stock Reconciliation hàng không lô (vòng sửa 1 dưới
đây). CHƯA đo huỷ Stock Reconciliation hàng CÓ lô, và CHƯA đo huỷ các loại
chứng từ khác (Delivery Note, Purchase Receipt, Purchase Invoice, Sales
Invoice, Subcontracting Receipt, Asset Capitalization) — không có căn cứ để
khẳng định TỔNG toàn kho luôn đúng cho MỌI tổ hợp. `da_huy` (tham số của
`ghi_dong_so`) CHƯA được set ở đây — vẫn để mặc định 0; đánh dấu dòng nào là
"bút toán đảo" thuộc về logic của Task 9, không tự suy luận trước khi có nó.

VÒNG SỬA 1 (review điều phối, model mạnh nhất, sau khi Task 7 đã "xong"):
phát hiện Critical — HUỶ MỘT KIỂM KÊ (Stock Reconciliation) HÀNG KHÔNG LÔ
làm vỡ bất biến §3 Ở CẤP KHO (không chỉ cấp lô — net KHÔNG về 0). Gốc rễ
nằm ở `vitri/delta.py` (Task 6), không phải ở file Task 7: guard chọn nhánh
kiểm kê trước đây dựa vào `actual_qty == 0`, chỉ đúng TÌNH CỜ ở đường ghi
thường; ở đường huỷ, `actual_qty` khác 0 (ERPNext tự đảo) trong khi Bin của
ERPNext vẫn lấy `qty_after_transaction` làm thẩm quyền — nhánh kiểm kê bị
bỏ qua đúng lúc cần nhất. Đã sửa `vitri/delta.py` để chọn nhánh bằng loại
chứng từ + không bundle + không `has_batch_no` + không inventory dimension,
KHÔNG dựa vào `actual_qty`. Xem docstring `vitri/delta.py` để biết chi tiết
đầy đủ và mã ERPNext trích dẫn; xem `task-7-report.md` (mục "Vòng sửa 1")
để biết output ĐỎ/XANH thật.

PHÁT HIỆN THỰC NGHIỆM (Task 7, đo trên erptest.local, Frappe 15.113.4 /
ERPNext 15.83.0, huỷ Stock Entry): dòng SLE đảo dấu khi huỷ chứng từ hàng CÓ
LÔ mang `serial_and_batch_bundle = None` — đo lại với CẢ HAI cách gán lô
(`create_new_batch=1` tự sinh, và chọn tay một Batch có sẵn), cả hai đều
mất bundle như nhau; thậm chí dòng SLE GỐC cũng bị xoá `serial_and_batch_bundle`
sau khi huỷ xong (không chỉ dòng đảo). Điều này trái với giả định trong
`vitri/lo.py` (Task 5, "vòng sửa 1") rằng "bundle không đổi khi huỷ nên tổng
bundle và delta lệch dấu" — giả định đó đúng về HẬU QUẢ (nếu bundle còn) chứ
KHÔNG đúng tiền đề cho đường huỷ của Stock Entry: bundle ở đây bị null hẳn,
không phải "còn nhưng lệch dấu". Hệ quả: `tach_theo_lo` rơi vào nhánh
"không có bundle" (không phải nhánh scale), trả `so_lo=None` — dòng sổ vị
trí đảo dấu MẤT CHIỀU LÔ. Vì `sle.batch_no` luôn rỗng trên Frappe 15
(Task 5) nên không có cách nào khác để phục hồi lô từ CHÍNH dòng SLE này;
phải tra ngược `Location Ledger Entry.chung_tu_row` (Task 9 mới làm).
CHƯA đo cho Delivery Note/Purchase Receipt/Sales Invoice — không có căn cứ
để khẳng định hành vi này đúng cho mọi loại chứng từ. Task 7 KHÔNG sửa
`tach_theo_lo` (ngoài phạm vi file được giao) — chỉ ghi log để việc mất lô
không âm thầm, và khoá lại đúng số liệu thực đo bằng test tích hợp
(`test_hook_nhap.TestHuyChungTu.test_huy_hang_co_lo_giu_dung_chieu_lo`).
Bất biến §3 ở MỨC (mặt hàng, lô, kho) do đó KHÔNG được giữ nguyên qua huỷ
hàng có lô — chỉ đúng khi cộng dồn qua TẤT CẢ các lô của mặt hàng đó
(kho-level). Xem task-7-report.md để rõ hệ quả cho Task 9.

TASK 9 (đã làm): thêm `dao_theo_o_goc(sle)`, chạy TRƯỚC toàn bộ đường mô tả
ở trên khi `sle.is_cancelled`. Nó KHÔNG dựa vào `serial_and_batch_bundle`
của dòng SLE huỷ (đã bị ERPNext xoá, xem "PHÁT HIỆN THỰC NGHIỆM" trên) mà
tra ngược các dòng `Location Ledger Entry` GỐC theo (chung_tu_type,
chung_tu, chung_tu_row, da_huy=0) — số lô đã được lưu sẵn ở đó lúc chứng từ
gốc submit, sổ chỉ ghi thêm nên còn nguyên — rồi ghi đảo ĐÚNG từng ô/lô đã
dùng và cờ `da_huy=1` lên cả dòng gốc lẫn dòng đảo. Khi tìm được dòng gốc,
hàm trả True và `ghi_so_vi_tri` return sớm, KHÔNG rơi xuống đường CHUA-XEP +
tinh_delta mô tả ở trên nữa — đường đó (và toàn bộ đoạn "mất chiều lô") chỉ
còn áp dụng cho ca `dao_theo_o_goc` trả False: chứng từ lập TRƯỚC khi kho
bật quản lý vị trí, không có dòng sổ gốc để tra. Bất biến §3 ở mức (mặt
hàng, lô, kho) giờ được giữ nguyên qua huỷ Stock Entry (Material
Receipt/Material Issue) hàng có lô — đo bằng
`test_hook_nhap.TestHuyChungTu.test_huy_hang_co_lo_giu_dung_chieu_lo`
(đã lật từ ghim khiếm khuyết sang chứng minh đã sửa) và `test_huy_chung_tu.py`
(test khoá "không chạy lại FEFO", test ca không có dòng gốc). CHƯA đo cho
Delivery Note/Purchase Receipt/Purchase Invoice/Sales Invoice/Subcontracting
Receipt/Asset Capitalization, CHƯA đo Stock Reconciliation hàng có lô, và
CHƯA đo Material Transfer (một dòng Stock Entry Detail sinh HAI SLE — nguồn
và đích — CÙNG chung_tu_row KHÁC kho; bộ lọc thêm `kho`/`vat_tu` ở trên xử
lý đúng LOGIC nhưng chưa có test tích hợp thật để đo). Xem task-9-report.md
mục "chưa kiểm chứng" để biết đầy đủ và output ĐỎ/XANH thật.
"""

import frappe
from frappe import _
from frappe.utils import flt

from erpnext.vi_tri_kho.vitri.delta import tinh_delta
from erpnext.vi_tri_kho.vitri.fefo import chon_o_xuat
from erpnext.vi_tri_kho.vitri.kho import kho_co_quan_ly_vi_tri, o_chua_xep
from erpnext.vi_tri_kho.vitri.lay_hang import phan_bo_cua_dong, tong_phan_bo
from erpnext.vi_tri_kho.vitri.lo import tach_theo_lo
from erpnext.vi_tri_kho.vitri.nhat_ky_loi import cat_tieu_de
from erpnext.vi_tri_kho.vitri.so import ghi_dong_so

# Độ chính xác/ngưỡng dùng khi scale phần trả về ô cũ — cùng quy ước với
# vitri/lo.py::_DO_CHINH_XAC_SO_LUONG (6 chữ số thập phân).
_DO_CHINH_XAC_SO_LUONG = 6
_SAI_SO_CHO_PHEP = 10**-_DO_CHINH_XAC_SO_LUONG


def ghi_so_vi_tri(doc, method=None):
	"""Điểm vào duy nhất. `doc` là một Stock Ledger Entry vừa submit."""
	if not kho_co_quan_ly_vi_tri(doc.warehouse):
		return

	if doc.get("is_cancelled") and dao_theo_o_goc(doc):
		return

	delta = tinh_delta(doc)
	if not delta:
		return

	if doc.is_cancelled and doc.get("has_batch_no") and not doc.get("serial_and_batch_bundle"):
		# Tới đây nghĩa là dao_theo_o_goc() (Task 9) đã trả False — không
		# tìm thấy dòng sổ vị trí gốc, tức chứng từ này được LẬP TRƯỚC khi
		# kho bật quản lý vị trí (điều 3 của brief Task 9). Với chứng từ
		# lập SAU khi bật, nhánh dao_theo_o_goc ở trên đã xử lý và return
		# sớm, không rơi xuống đây. Xem PHÁT HIỆN THỰC NGHIỆM ở docstring
		# module: huỷ chứng từ hàng có lô làm mất serial_and_batch_bundle
		# trên chính dòng SLE đảo dấu, nên tach_theo_lo() dưới đây chắc
		# chắn rơi về nhánh "không có bundle" và trả so_lo=None — không
		# phải lỗi ở đây (không có dòng gốc để tra ngược), nhưng không được
		# để im lặng.
		frappe.log_error(
			title="hook_sle: huỷ chứng từ hàng có lô mất chiều lô",
			message=(
				f"sle={doc.name} chung_tu={doc.voucher_type} {doc.voucher_no} "
				f"vat_tu={doc.item_code} kho={doc.warehouse} — dòng SLE đảo dấu khi "
				"huỷ không mang serial_and_batch_bundle, và không tìm thấy dòng sổ "
				"vị trí gốc để tra ngược lô (chứng từ có thể lập trước khi kho bật "
				"quản lý vị trí). Dòng sổ vị trí ghi ra sẽ mất chiều lô (so_lo rỗng)."
			),
		)

	for phan in tach_theo_lo(doc, delta):
		if not phan["so_luong"]:
			continue
		_ghi_mot_phan(doc, phan["so_lo"], phan["so_luong"])


def _ghi_mot_phan(sle, so_lo, so_luong):
	"""Ghi sổ cho một (lô, số lượng) của một dòng SLE.

	Nhập (số dương): trước tiên tra xem chứng từ này (CÙNG chung_tu_row) đã
	từng bị MỘT bút toán đảo khác (`dao_theo_o_goc`) rút hàng ra khỏi ô nào
	chưa — có thì trả hàng về ĐÚNG (các) ô đó, không dồn CHUA-XEP. Không có
	dấu vết đảo nào → dồn vào CHUA-XEP như cũ.

	Xuất (số âm): ưu tiên BẢNG PHÂN BỔ (thủ kho đã quét ngoài kệ, 18/09/2026);
	không có phân bổ thì chọn ô theo FEFO như cũ.
	"""
	if so_luong > 0:
		phan_bo = _tra_lai_o_da_dao(sle, so_lo, so_luong)
	else:
		phan_bo = _phan_bo_da_khai(sle, so_lo, -so_luong)
		if phan_bo is None:
			phan_bo = [
				{"o": p["o"], "so_luong": -p["so_luong"]}
				for p in chon_o_xuat(sle.warehouse, sle.item_code, so_lo, -so_luong)
			]

	for p in phan_bo:
		ghi_dong_so(
			o=p["o"],
			kho=sle.warehouse,
			vat_tu=sle.item_code,
			so_lo=so_lo,
			so_luong=p["so_luong"],
			chung_tu_type=sle.voucher_type,
			chung_tu=sle.voucher_no,
			chung_tu_row=sle.voucher_detail_no,
			sle=sle.name,
			ngay=sle.posting_date,
			thoi_diem=sle.get("posting_datetime") or f"{sle.posting_date} {sle.posting_time}",
			company=sle.company,
		)


def _phan_bo_da_khai(sle, so_lo, can_xuat) -> list[dict] | None:
	"""Phân bổ ô mà người lấy hàng đã quét, hoặc `None` nếu chứng từ không có.

	`None` (không phải danh sách rỗng) là tín hiệu "đi tiếp FEFO" — phân biệt rõ
	với "có phân bổ nhưng bằng 0", vốn là dữ liệu hỏng chứ không phải đường cũ.

	Tổng lệch thì CHẶN, không tự chữa: phân bổ dở dang nghĩa là mới quét được một
	phần, và im lặng chạy FEFO cho phần còn lại sẽ trừ những ô chưa ai tới lấy —
	sai lệch mà đối soát theo tổng không bao giờ bắt được (spec lấy hàng §5).
	"""
	dong = phan_bo_cua_dong(sle.voucher_type, sle.voucher_no, sle.voucher_detail_no, so_lo)
	if not dong:
		return None

	tong = tong_phan_bo(dong)
	if abs(tong - flt(can_xuat)) > _SAI_SO_CHO_PHEP:
		frappe.log_error(
			title=cat_tieu_de(f"vi_tri_kho: phan bo lech ({sle.voucher_no})"),
			message=(
				f"sle={sle.name} dong_hang={sle.voucher_detail_no} vat_tu={sle.item_code} "
				f"so_lo={so_lo} phan_bo={tong} can_xuat={can_xuat}"
			),
		)
		frappe.throw(
			_(
				"Phiếu giao {0}: dòng {1}{2} phân bổ {3} nhưng xuất {4}. Mở lại trang Lấy hàng "
				"để quét tiếp, hoặc xoá phân bổ của dòng này để hệ tự chọn ô theo hạn dùng."
			).format(
				sle.voucher_no,
				sle.item_code,
				_(", lô {0}").format(so_lo) if so_lo else "",
				flt(tong, 3),
				flt(can_xuat, 3),
			)
		)

	return [{"o": d["o"], "so_luong": -flt(d["so_luong"])} for d in dong]


def _bat_buoc_o_chua_xep(kho):
	o = o_chua_xep(kho)
	if not o:
		frappe.throw(
			_(
				'Kho {0} bật quản lý vị trí nhưng chưa có ô "Chưa xếp vị trí". '
				"Chạy lại chức năng bật quản lý vị trí cho kho này."
			).format(kho)
		)
	return o


def _tra_lai_o_da_dao(sle, so_lo, so_luong) -> list[dict]:
	"""CRITICAL 1 (review điều phối sau khi 147/147 bài "xong"): đối xứng của
	`dao_theo_o_goc`, cho đường NHẬP.

	Cơ chế đã đọc mã nguồn xác nhận (`landed_cost_voucher.py:243-250`,
	`repost_item_valuation.py::recreate_stock_ledger_entries`): cả hai
	CHỦ ĐỘNG lặp lại "docstatus=2 → ghi sổ → docstatus=1 → ghi sổ" trên một
	chứng từ NHẬP đã submit, mà không hề huỷ/nhập lại thật. Bước 1 sinh SLE
	`is_cancelled=1` → `dao_theo_o_goc()` (ở trên) đảo ĐÚNG các ô mà chứng
	từ đã dùng, cờ `da_huy=1` lên cả dòng gốc lẫn dòng đảo. Bước 2 sinh SLE
	bình thường (`is_cancelled=0`, `so_luong>0` sau delta) cho CÙNG
	chung_tu_row — nếu cứ đi thẳng vào `_bat_buoc_o_chua_xep` như trước, hàng
	ĐÃ Ở MỘT Ô THẬT (do GĐ2 Location Allocation phân bổ, hoặc do một lần
	`_tra_lai_o_da_dao` trước đó phục hồi) sẽ bị dồn nhầm sang CHUA-XEP — một
	sự di chuyển ẢO không hề tương ứng với bất kỳ thao tác kho thật nào,
	trong khi TỔNG vẫn khớp Bin nên `doi_soat_kho` (trước khi có Critical 1b)
	báo "khớp" 100%. Đã ĐO THỰC TẾ (task report): PR nhập thẳng vào CHUA-XEP
	(chưa có GĐ2) không tự lộ khiếm khuyết này vì "ô cũ" của một PR luôn là
	CHUA-XEP — cả đường buggy lẫn đường đã sửa cùng hội tụ về CHUA-XEP, không
	phân biệt được. Bài test khoá Critical 1 (`test_landed_cost_voucher.py`)
	vì vậy seed thẳng một dòng sổ vị trí tại một ô thật cho CHÍNH
	chung_tu_row của PR (mô phỏng đúng kết quả mà GĐ2 sẽ tạo ra) trước khi
	mô phỏng chuỗi hai bước — không mock hàm nào đang được kiểm.

	Tra theo ĐÚNG khoá mà `dao_theo_o_goc` dùng khi đảo
	(chung_tu_type/chung_tu/chung_tu_row/kho/vat_tu), cộng thêm `so_lo` (vì
	hàm này được gọi SAU khi `tach_theo_lo` đã tách theo lô — chỉ trả về ô
	cũ cho ĐÚNG lô đang ghi, không trộn lô).

	Phân biệt "dòng đã đảo" (thứ hàm này cần) khỏi "dòng gốc bị đảo" (cùng
	da_huy=1, nhưng KHÁC dấu): không dùng riêng `da_huy=1` vì cả dòng gốc
	(được `dao_theo_o_goc` cờ lại) LẪN dòng đảo mới ghi đều mang cờ đó — phải
	lọc thêm `so_luong < 0` (dòng đảo của một chứng từ NHẬP luôn âm) VÀ chỉ
	lấy đúng MỘT thế hệ (repost/LCV có thể chạy nhiều lần): sắp theo
	`creation desc`, lấy `sle` của dòng đảo MỚI NHẤT, rồi lọc lại đúng các
	dòng cùng `sle` đó — mọi dòng đảo trong CÙNG một lần gọi `dao_theo_o_goc`
	chia sẻ chung một `sle` (SLE `is_cancelled=1` vừa sinh ra chúng), nên lọc
	theo `sle` tách đúng thế hệ mới nhất khỏi các thế hệ cũ hơn mà không cần
	thêm field nào. Trả `[]` (rơi xuống CHUA-XEP) nếu không tìm được dòng đảo
	nào khớp lô — CHƯA kiểm chứng bằng test tích hợp thật cho ca lặp lại
	nhiều thế hệ (LCV chạy hai lần trở lên); xem báo cáo mục "chưa kiểm
	chứng".
	"""
	khoa = {
		"chung_tu_type": sle.voucher_type,
		"chung_tu": sle.voucher_no,
		"chung_tu_row": sle.voucher_detail_no,
		"kho": sle.warehouse,
		"vat_tu": sle.item_code,
		"da_huy": 1,
		"so_luong": ("<", 0),
	}
	moi_nhat = frappe.get_all(
		"Location Ledger Entry",
		filters=khoa,
		fields=["sle"],
		order_by="creation desc",
		limit=1,
	)
	if not moi_nhat or not moi_nhat[0].sle:
		return [{"o": _bat_buoc_o_chua_xep(sle.warehouse), "so_luong": so_luong}]

	o_cu = frappe.get_all(
		"Location Ledger Entry",
		filters={**khoa, "sle": moi_nhat[0].sle, "so_lo": so_lo or ""},
		fields=["o", "so_luong"],
		order_by="creation",
	)
	if not o_cu:
		return [{"o": _bat_buoc_o_chua_xep(sle.warehouse), "so_luong": so_luong}]

	tong_da_dao = flt(sum(-flt(d.so_luong) for d in o_cu))
	if abs(tong_da_dao) <= _SAI_SO_CHO_PHEP:
		return [{"o": _bat_buoc_o_chua_xep(sle.warehouse), "so_luong": so_luong}]

	if abs(tong_da_dao - so_luong) <= _SAI_SO_CHO_PHEP:
		# Khớp trong sai số: trả nguyên theo đúng ô/tỷ lệ đã đảo.
		return [{"o": d.o, "so_luong": -flt(d.so_luong)} for d in o_cu]

	# Không khớp: tầng vị trí không tự quyết số lượng (cùng nguyên tắc
	# tach_theo_lo) — scale theo so_luong đang ghi, giữ tỷ lệ giữa các ô,
	# ghi log để truy được vì đây là tình huống bất thường (LCV không đổi số
	# lượng — lệch nghĩa là có gì đó khác đã đụng vào cùng chung_tu_row giữa
	# hai lần đảo).
	frappe.log_error(
		title="hook_sle: trả hàng về ô cũ lệch số lượng, phải scale",
		message=(
			f"sle={sle.name} chung_tu={sle.voucher_type} {sle.voucher_no} "
			f"row={sle.voucher_detail_no} vat_tu={sle.item_code} so_lo={so_lo} "
			f"tong_da_dao={tong_da_dao} so_luong_dang_ghi={so_luong} — tổng các dòng "
			"đã đảo không khớp số lượng đang ghi lại; scale theo tỷ lệ, không dùng "
			"nguyên giá trị đã đảo."
		),
	)
	ket_qua = []
	da_chia = 0.0
	for d in o_cu[:-1]:
		phan = flt(-flt(d.so_luong) * so_luong / tong_da_dao, _DO_CHINH_XAC_SO_LUONG)
		ket_qua.append({"o": d.o, "so_luong": phan})
		da_chia += phan
	d_cuoi = o_cu[-1]
	ket_qua.append(
		{
			"o": d_cuoi.o,
			"so_luong": flt(so_luong - da_chia, _DO_CHINH_XAC_SO_LUONG),
		}
	)
	return ket_qua


def dao_theo_o_goc(sle) -> bool:
	"""Ghi bút toán đảo theo ĐÚNG các ô mà chứng từ gốc đã dùng.

	Trả False nếu không tìm được dòng gốc VÀ không có dấu vết dòng gốc nào
	đã bị đảo trước đó (xem "vòng sửa 2" bên dưới) — khi đó gọi bên ngoài
	sẽ đi tiếp nhánh thường (FEFO / CHUA-XEP), là hành vi đúng cho chứng từ
	phát sinh TRƯỚC khi kho bật quản lý vị trí (không có dòng sổ vị trí
	gốc nào để tra ngược).

	KHÔNG chạy lại FEFO ở đây. Chạy lại sẽ trả hàng về ô khác với ô đã lấy;
	tổng tồn vẫn đúng nên báo cáo đối soát không bắt được, và lỗi chỉ lộ ra
	lúc kiểm kê thực tế khi đã mất dấu vết. Thay vào đó, soi lại đúng các
	dòng `Location Ledger Entry` đã ghi lúc chứng từ gốc submit (cùng
	chung_tu_type/chung_tu/chung_tu_row/kho/vat_tu, da_huy=0 — sổ chỉ ghi
	thêm nên dòng gốc còn nguyên), ghi ngược đúng từng ô đã dùng bằng cùng
	hàm `ghi_dong_so` (không xoá, không sửa dòng cũ), rồi cờ `da_huy=1` lên
	các dòng gốc để phân biệt "đã bị đảo" khỏi "còn hiệu lực".

	Lọc thêm THEO KHO VÀ VẬT TƯ (không chỉ chung_tu_row) — cố ý, không phải
	brief gốc: `stock_entry.py` (`get_sl_entries`, gọi từ
	`get_sle_for_source_warehouse`/`get_sle_for_target_warehouse`) đặt
	`voucher_detail_no = d.name` (tên dòng Stock Entry Detail) cho CẢ hai
	SLE của một dòng Material Transfer — một cho kho nguồn (âm), một cho
	kho đích (dương) — CÙNG chung_tu_row nhưng KHÁC kho. Khoá phân biệt
	DUY NHẤT ở ca này là `kho` (hai SLE mang CÙNG `item_code`, lọc `vat_tu`
	không có tác dụng phân biệt cho riêng ca Material Transfer — giữ lại
	chỉ vì đúng ngữ nghĩa "dòng sổ của đúng mặt hàng đang xét", không phải
	vì cần thiết cho ca này). Nếu chỉ lọc theo chung_tu_row, khi kho nguồn
	huỷ nổ hook trước, câu SELECT sẽ vớt luôn dòng sổ gốc của KHO ĐÍCH
	(chưa tới lượt hook của nó), đảo nhầm ở cả hai kho rồi cờ da_huy cho cả
	hai; tới khi hook của SLE kho đích chạy, `goc` rỗng (đã bị cờ da_huy=1
	ở lượt trước) — xem "vòng sửa 2" ngay dưới đây về việc phân biệt ca này
	khỏi ca Task 9 gốc (chứng từ lập trước khi bật quản lý vị trí). CHƯA có
	test tích hợp Material Transfer thật để đo trực tiếp, xem
	task-9-report.md mục "chưa kiểm chứng".

	VÒNG SỬA 2 (review điều phối, model mạnh nhất): điều phối chỉ ra
	`goc` rỗng có HAI nguyên nhân khác nhau mà bản gốc (Task 9, brief
	nguyên văn) không phân biệt được:
	(a) chứng từ lập TRƯỚC khi kho bật quản lý vị trí — chưa từng có dòng
	    gốc nào (điều bắt buộc #3 của brief) — PHẢI trả False để rơi xuống
	    đường thường;
	(b) một SLE "anh em" CÙNG khoá lọc (chung_tu_type/chung_tu/chung_tu_row/
	    kho/vat_tu) đã chạy hook TRƯỚC và đảo hết dòng gốc rồi (cờ
	    da_huy=1) — PHẢI trả True (không làm gì thêm), vì rơi xuống đường
	    thường ở đây sẽ TÍNH DELTA THÊM MỘT LẦN cho SLE anh em đã xử lý
	    xong, lệch tồn Ở CẤP KHO. Ca (b) có thật: `stock_reconciliation.py`
	    (`make_sle_on_cancel`, ~903-916) sinh HAI dòng SLE huỷ cùng khoá
	    lọc cho một `row` kiểm kê hàng có lô khi cả `serial_and_batch_bundle`
	    và `current_serial_and_batch_bundle` đều có giá trị — đúng cấu trúc
	    (b). ĐO THỰC TẾ (xem docstring
	    `test_hook_nhap.TestThuTuTinhDeltaTruocKhiGhi.test_huy_kiem_ke_hang_co_lo_phai_khop_bin_doc_lap`):
	    trong kịch bản đo được, cả hai SLE anh em đều mang `actual_qty=0`
	    nên `tinh_delta` trả 0 và đường thường tự vô hại (KHÔNG đo được ca
	    thật sự ghi thừa) — nhưng phân biệt (a)/(b) vẫn là sửa ĐÚNG theo
	    đúng tài liệu ở trên (False ⟺ "chưa từng có dòng gốc", không phải
	    "goc rỗng vì lý do bất kỳ"), rẻ, không đổi bất kỳ bài nào đang xanh,
	    nên giữ lại như một lớp phòng thủ ngữ nghĩa dù chưa đo được ca nó
	    thật sự cứu.
	"""
	goc = frappe.get_all(
		"Location Ledger Entry",
		filters={
			"chung_tu_type": sle.voucher_type,
			"chung_tu": sle.voucher_no,
			"chung_tu_row": sle.voucher_detail_no,
			"kho": sle.warehouse,
			"vat_tu": sle.item_code,
			"da_huy": 0,
		},
		fields=["name", "o", "so_lo", "so_luong", "kho"],
	)
	if not goc:
		# Vòng sửa 2: phân biệt "chưa từng có dòng gốc" (True điều bắt buộc
		# #3, trả False) khỏi "SLE anh em cùng khoá lọc đã đảo xong dòng
		# này rồi" (còn dấu vết da_huy=1 khớp đúng khoá — trả True, không
		# ghi gì thêm, không rơi xuống đường thường tính delta thêm lần nữa).
		da_dao = frappe.get_all(
			"Location Ledger Entry",
			filters={
				"chung_tu_type": sle.voucher_type,
				"chung_tu": sle.voucher_no,
				"chung_tu_row": sle.voucher_detail_no,
				"kho": sle.warehouse,
				"vat_tu": sle.item_code,
				"da_huy": 1,
			},
			limit=1,
		)
		return bool(da_dao)

	for d in goc:
		ghi_dong_so(
			o=d.o,
			kho=d.kho,
			vat_tu=sle.item_code,
			so_lo=d.so_lo,
			so_luong=-d.so_luong,
			chung_tu_type=sle.voucher_type,
			chung_tu=sle.voucher_no,
			chung_tu_row=sle.voucher_detail_no,
			sle=sle.name,
			ngay=sle.posting_date,
			thoi_diem=sle.get("posting_datetime") or f"{sle.posting_date} {sle.posting_time}",
			company=sle.company,
			da_huy=1,
		)
		frappe.db.set_value("Location Ledger Entry", d.name, "da_huy", 1, update_modified=False)

	return True

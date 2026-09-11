"""So tồn vị trí với tồn kho ERPNext. Bất biến của spec §3.

So THEO TỪNG (mặt hàng, lô), không chỉ so tổng — so tổng thôi thì một lỗi
gộp lô vẫn "khớp".

VÒNG SỬA 1 (review điều phối, Critical): mốc quy chiếu KHÔNG được cộng
`sle.actual_qty` trực tiếp ở cấp mặt hàng. `sum(sle.actual_qty)` SAI với
Stock Reconciliation hàng KHÔNG LÔ — `stock_reconciliation.py ::
get_sle_for_items` đặt cứng `actual_qty = 0` khi submit và không nhánh nào
ghi đè cho trường hợp không lô/không dimension (dòng 861, 894-896); giá trị
thật nằm ở `qty_after_transaction`. Đây CHÍNH LÀ cái bẫy đã sửa ở đường GHI
(xem `vitri/delta.py`, dòng docstring "actual_qty == 0 chỉ ĐÚNG TÌNH CỜ ở
đường ghi thường") — Task 10 bản đầu đi thẳng vào nó từ đường ĐỌC. Cộng dồn
`actual_qty` cho một mặt hàng có kiểm kê hàng không lô sẽ BỎ QUA HOÀN TOÀN
lần kiểm kê đó, khiến `doi_soat_kho` báo `khop: True` trong khi cả hai vế
đều lệch khỏi `Bin` — cấp chứng nhận không có cơ sở.

Cách sửa — GHÉP nguồn, không chọn một:
- `Bin.actual_qty` làm TỔNG CÓ THẨM QUYỀN ở cấp mặt hàng. Bin không dùng
  làm nguồn DUY NHẤT được vì thiếu chiều lô, nhưng ở cấp mặt hàng nó chính
  xác — đó là con số ERPNext tự dùng, không lệ thuộc actual_qty của từng
  dòng SLE.
- Dòng con `Serial and Batch Entry` (nối qua `serial_and_batch_bundle`,
  lọc `is_cancelled = 0` trên SLE cha) cho PHẦN CHIA theo lô — số lô nằm ở
  đó, không nằm trên SLE (đã đo trên dữ liệu thật: 0/56 dòng SLE hàng có
  lô mang `batch_no` trên chính SLE).
- Phần dư không giải thích được bằng lô (Bin trừ đi tổng đã chia theo lô)
  dồn vào ngăn không-lô (`so_lo = ''`) — hàng không quản lý lô rơi trọn
  vào đây; hàng có lô mà tổng SBE không khớp Bin (bất nhất phía ERPNext)
  cũng lộ ra ở đây thay vì bị nuốt.

CRITICAL 1b (review điều phối, sau khi 147/147 bài "xong"): so TỔNG theo
(vật tư, lô) — dù đã đúng theo vòng sửa 1 ở trên — vẫn có LỖ HỔNG: một bút
toán ghi SAI Ô nhưng không đổi tổng của (vật tư, lô, kho) đó (đúng cơ chế
Critical 1, xem `hook_sle.py::_tra_lai_o_da_dao`) trôi lọt qua `dong_lech`
hoàn toàn — cả hai vế cùng là TỔNG nên không phân biệt được hàng ở ô nào.
Thêm hai phép đo Ở MỨC Ô (mịn hơn `dong_lech`): `_o_am` (không ô nào âm —
một ô âm là dấu hiệu chắc chắn của ghi sai, dù tổng vẫn khớp) và
`_lech_bo_dem` (bộ đệm `Location Balance` phải dựng lại được từ sổ
`Location Ledger Entry`, độc lập với `Bin`/ERPNext). `khop` giờ đòi CẢ BA
đo sạch — xem docstring `doi_soat_kho`.
"""

import frappe
from frappe.utils import flt

NGUONG_SAI_SO = 0.0001


def ton_kho_theo_lo(kho) -> dict:
	"""{(vat_tu, so_lo): so_luong} lấy từ tồn kho ERPNext.

	Bin.actual_qty là tổng có thẩm quyền Ở CẤP MẶT HÀNG; SLE + Serial and
	Batch Entry chỉ dùng để CHIA tổng đó theo lô, không dùng để TÍNH tổng.

	CÔNG KHAI có chủ đích (Task 11): đây là NGUỒN SỰ THẬT DUY NHẤT cho "tồn
	hiện có tách theo lô" của một kho. Đường "bật quản lý vị trí"
	(`vitri/bat_kho.py::_ton_hien_co`) dùng lại đúng hàm này thay vì chép
	lại SQL — sửa một bên quên bên kia thì "bật kho" và "đối soát" sẽ đọc
	tồn theo hai cách khác nhau, đúng loại lệch mà cả hệ này dựng ra để bắt.
	"""
	tong_theo_mat_hang = {
		d.item_code: flt(d.actual_qty)
		for d in frappe.db.sql(
			"""select item_code, actual_qty from `tabBin` where warehouse = %s""",
			(kho,),
			as_dict=True,
		)
	}

	chia_theo_lo = frappe.db.sql(
		"""
		select sle.item_code as vat_tu, sbe.batch_no as so_lo, sum(sbe.qty) as sl
		from `tabStock Ledger Entry` sle
		join `tabSerial and Batch Entry` sbe on sbe.parent = sle.serial_and_batch_bundle
		where sle.warehouse = %s and sle.is_cancelled = 0 and sbe.batch_no is not null
		group by sle.item_code, sbe.batch_no
		""",
		(kho,),
		as_dict=True,
	)

	ket_qua = {}
	tong_da_chia = {}
	for d in chia_theo_lo:
		khoa = (d.vat_tu, d.so_lo)
		ket_qua[khoa] = ket_qua.get(khoa, 0) + flt(d.sl)
		tong_da_chia[d.vat_tu] = tong_da_chia.get(d.vat_tu, 0) + flt(d.sl)

	for vat_tu in set(tong_theo_mat_hang) | set(tong_da_chia):
		du = flt(tong_theo_mat_hang.get(vat_tu, 0)) - flt(tong_da_chia.get(vat_tu, 0))
		if abs(du) > NGUONG_SAI_SO:
			khoa = (vat_tu, "")
			ket_qua[khoa] = ket_qua.get(khoa, 0) + du

	return ket_qua


def _ton_vi_tri_theo_lo(kho) -> dict:
	dong = frappe.db.sql(
		"""select vat_tu, ifnull(so_lo,'') as so_lo, sum(so_luong) as sl
		   from `tabLocation Balance` where kho = %s
		   group by vat_tu, ifnull(so_lo,'')""",
		(kho,),
		as_dict=True,
	)
	ket_qua = {}
	for d in dong:
		khoa = (d.vat_tu, d.so_lo or "")
		ket_qua[khoa] = ket_qua.get(khoa, 0) + flt(d.sl)
	return ket_qua


def _o_am(kho) -> list[dict]:
	"""Các ô đang mang tồn ÂM trong bộ đệm `Location Balance` của kho.

	CRITICAL 1b (review điều phối, sau khi 147/147 bài "xong"): đây CHÍNH LÀ
	phép đo lẽ ra đã bắt được Critical 1 — `dao_theo_o_goc` (`hook_sle.py`)
	ghi `-d.so_luong` KHÔNG kiểm tồn ô trước khi ghi, nên một ô có thể xuống
	âm mà `doi_soat_kho` bản cũ (chỉ so TỔNG theo (vật tư, lô)) không bắt
	được — tổng vẫn khớp Bin vì phần âm ở một ô được CHUA-XEP (hay một ô
	khác) bù lại đúng bằng số. Ngưỡng dùng CHUNG `NGUONG_SAI_SO` (không phải
	`< 0` trần trụi) — cùng lớp lỗi đã sửa ba lần trong dự án này (`lo.py`
	chia gần-0, `bat_kho.py` ngưỡng trôi lệch, `fefo.py` làm tròn): một ô
	mang dư làm tròn dấu phẩy động cỡ `-1e-17` không phải tồn âm THẬT, và
	không ngưỡng sẽ làm `khop` sai vĩnh viễn False vì sai số không tránh
	được của phép cộng dồn float.
	"""
	dong = frappe.db.sql(
		"""select o, vat_tu, ifnull(so_lo,'') as so_lo, so_luong
		   from `tabLocation Balance` where kho=%s and so_luong < %s""",
		(kho, -NGUONG_SAI_SO), as_dict=True,
	)
	return [
		{"o": d.o, "vat_tu": d.vat_tu, "so_lo": d.so_lo or None, "so_luong": flt(d.so_luong)}
		for d in dong
	]


def _lech_bo_dem(kho) -> list[dict]:
	"""Bộ đệm `Location Balance` có khớp sổ `Location Ledger Entry` không —
	so THEO TỪNG (ô, vật tư, lô), là mức mịn nhất mà `Location Balance` có.

	CRITICAL 1b: `Location Balance` là bộ đệm DẪN XUẤT (`so.py`, docstring
	module: "mọi con số trong đó phải dựng lại được từ sổ"). Nếu `_cong_don_ton`
	(upsert) và sổ `Location Ledger Entry` (nguồn sự thật, chỉ ghi thêm) từng
	trôi lệch nhau vì bất kỳ lý do gì (ghi trực tiếp SQL, race hiếm, patch dữ
	liệu tay), `doi_soat_kho` bản cũ — chỉ so bộ đệm với `Bin` — sẽ không bao
	giờ thấy sự trôi lệch NỘI BỘ này, vì nó không hề đọc lại sổ.
	"""
	bo_dem = frappe.db.sql(
		"""select o, vat_tu, ifnull(so_lo,'') as so_lo, sum(so_luong) as sl
		   from `tabLocation Balance` where kho=%s
		   group by o, vat_tu, ifnull(so_lo,'')""",
		(kho,), as_dict=True,
	)
	so_sach = frappe.db.sql(
		"""select o, vat_tu, ifnull(so_lo,'') as so_lo, sum(so_luong) as sl
		   from `tabLocation Ledger Entry` where kho=%s
		   group by o, vat_tu, ifnull(so_lo,'')""",
		(kho,), as_dict=True,
	)
	bo_dem_map = {(d.o, d.vat_tu, d.so_lo): flt(d.sl) for d in bo_dem}
	so_sach_map = {(d.o, d.vat_tu, d.so_lo): flt(d.sl) for d in so_sach}

	ket_qua = []
	for khoa in sorted(set(bo_dem_map) | set(so_sach_map)):
		a = bo_dem_map.get(khoa, 0)
		b = so_sach_map.get(khoa, 0)
		if abs(a - b) > NGUONG_SAI_SO:
			o, vat_tu, so_lo = khoa
			ket_qua.append({
				"o": o, "vat_tu": vat_tu, "so_lo": so_lo or None,
				"bo_dem": a, "so_sach": b, "lech": a - b,
			})
	return ket_qua


def doi_soat_kho(kho) -> dict:
	"""So tồn vị trí với tồn kho. Trả kết quả kèm danh sách dòng lệch.

	CRITICAL 1b: `khop` giờ đòi CẢ BA phép đo sạch, không chỉ `dong_lech`
	(tổng theo (vật tư, lô) so với Bin) — thêm `o_am` (không ô nào âm) và
	`lech_bo_dem` (bộ đệm khớp sổ). Ba phép đo bắt BA lớp lỗi khác nhau:
	`dong_lech` bắt lệch TỔNG với ERPNext; `o_am` bắt một dạng bút toán sai
	mà tổng vẫn khớp (đúng cơ chế Critical 1); `lech_bo_dem` bắt bộ đệm tự nó
	trôi khỏi sổ, độc lập với ERPNext. KHÔNG đổi cấu trúc `dong_lech` — 9 bài
	test cũ (`test_doi_soat.py`) dựa vào nó nguyên dạng.
	"""
	ton_kho = ton_kho_theo_lo(kho)
	ton_vt = _ton_vi_tri_theo_lo(kho)

	moi_khoa = set(ton_kho) | set(ton_vt)
	lech = []
	for vat_tu, so_lo in sorted(moi_khoa):
		a = flt(ton_vt.get((vat_tu, so_lo), 0))
		b = flt(ton_kho.get((vat_tu, so_lo), 0))
		if abs(a - b) > NGUONG_SAI_SO:
			lech.append({
				"vat_tu": vat_tu,
				"so_lo": so_lo or None,
				"ton_vi_tri": a,
				"ton_kho": b,
				"lech": a - b,
			})

	o_am = _o_am(kho)
	lech_bo_dem = _lech_bo_dem(kho)

	return {
		"kho": kho,
		"khop": not lech and not o_am and not lech_bo_dem,
		"so_dong_lech": len(lech),
		"dong_lech": lech,
		"o_am": o_am,
		"lech_bo_dem": lech_bo_dem,
	}

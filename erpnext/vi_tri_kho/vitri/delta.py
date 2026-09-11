"""Tính số lượng THẬT một dòng Stock Ledger Entry làm thay đổi tồn kho.

Với hầu hết chứng từ, `sle.actual_qty` đã là con số đó — dùng thẳng.

Ngoại lệ: `Stock Reconciliation` (kiểm kê) hàng KHÔNG LÔ, không có
inventory dimension. ERPNext (`stock_ledger.py`, nhánh
`voucher_type == "Stock Reconciliation" and not sle.batch_no and not
sle.has_batch_no and not has_dimensions`) lấy THẲNG `sle.qty_after_transaction`
làm tồn kho cuối cùng ghi vào Bin, BỎ QUA `actual_qty` HOÀN TOÀN — ở CẢ
đường ghi (`docstatus == 1`) LẪN đường huỷ (`docstatus == 2`). Nhánh này bù
lại bằng `delta = qty_after_transaction - tong_ton_vi_tri(kho, vat_tu, so_lo)`,
tức tồn mới trừ tồn cũ ĐỌC TỪ SỔ VỊ TRÍ CỦA TA (không phải Bin của ERPNext)
— vì vậy `tinh_delta()` PHẢI được gọi TRƯỚC khi dòng sổ vị trí của chính SLE
này được ghi (`ghi_dong_so`), nếu không tồn cũ đọc được đã lẫn cả thay đổi
của chính giao dịch đang tính.

VÒNG SỬA 1 (review điều phối, Task 7, model mạnh nhất): guard TRƯỚC ĐÂY chọn
nhánh này bằng `actual_qty == 0` — SAI, và sai nghiêm trọng ở đường HUỶ.
`actual_qty == 0` chỉ ĐÚNG TÌNH CỜ ở đường ghi thường
(`stock_reconciliation.py`, `get_sle_for_items`: `data.actual_qty = 0` mặc
định khi không phải đường huỷ). Ở đường HUỶ một kiểm kê hàng không lô
(`docstatus == 2`, nhánh `if row.current_qty and current_bundle`),
ERPNext đặt `data.actual_qty = -1 * row.current_qty` — KHÁC 0 — và
`data.qty_after_transaction = flt(row.current_qty)` (tồn TRƯỚC kiểm kê,
tức tồn sẽ quay về khi huỷ). Guard `not delta` (đòi actual_qty bằng 0) làm
nhánh kiểm kê bị BỎ QUA đúng lúc cần nhất ở đường huỷ: `tinh_delta` trả
thẳng `actual_qty` (sai) trong khi Bin của ERPNext vẫn đi theo
`qty_after_transaction` — tồn vị trí và Bin lệch nhau VĨNH VIỄN sau một lần
huỷ kiểm kê hàng không lô, vi phạm bất biến spec §3 Ở CẤP KHO (không chỉ ở
cấp lô — nặng hơn khuyết tật mất-chiều-lô của Task 7 vì cái đó net 0 ở cấp
kho, cái này thì không). Khoá bằng test tích hợp thật ở
`test_hook_nhap.TestThuTuTinhDeltaTruocKhiGhi.test_huy_kiem_ke_hang_khong_lo_phai_khop_bin_doc_lap`
(nhập 10 → kiểm kê 17 → huỷ kiểm kê → phải về lại 10, không phải 27 hay 7).

Điều kiện ĐÚNG (khớp nguyên văn nhánh `stock_ledger.py` ở trên) không đọc
`actual_qty` — chỉ đọc LOẠI CHỨNG TỪ + KHÔNG CÓ bundle + KHÔNG CÓ
`has_batch_no` + KHÔNG CÓ inventory dimension nào áp dụng cho dòng SLE này.
`not has_dimensions` bắt buộc phải kiểm dù site hiện có 0 `Inventory
Dimension` (không đổi hành vi đo được hôm nay) — thiếu nó là một quả mìn
hẹn giờ: hễ ai bật một Inventory Dimension, ERPNext tự động rẽ dòng SLE đó
sang nhánh khác (không còn lấy thẳng `qty_after_transaction`), và
`tinh_delta` phải theo kịp ngay từ đầu, không phải vá sau khi vỡ.

Hàng CÓ LÔ ở kiểm kê thường (`get_sle_for_serialized_items`, dòng 809/821
của cùng file ERPNext) tách thành hai dòng SLE có dấu, nên `actual_qty`
dùng được bình thường và KHÔNG được rơi vào nhánh trên — dù đôi khi
`actual_qty` của dòng đó cũng bằng 0 (kiểm kê đặt lại đúng số đang có).
Phân biệt bằng `serial_and_batch_bundle` VÀ `has_batch_no` (không chỉ một
trong hai — xem "vòng sửa 1" ở trên: dựa độc quyền vào một tín hiệu tình cờ
đã một lần gây lỗi thật, hai tín hiệu cùng khớp mã ERPNext an toàn hơn một).
Đặc biệt, KHÔNG được tra tồn qua `sle.batch_no` — trường này LUÔN RỖNG
trên Frappe 15 (số lô nằm ở `Serial and Batch Bundle`, đã đo trên
erptest.local: 0/56 dòng SLE hàng có lô mang `batch_no`, 56/56 mang
`serial_and_batch_bundle` — khớp phép đo của Task 5, xem
`vitri/lo.py`), nên tra `tong_ton_vi_tri(kho, vat_tu, "")` sẽ cộng nhầm
tồn của MỌI dòng không lô vào delta của một dòng có lô.
"""

from frappe.utils import flt

from erpnext.stock.doctype.inventory_dimension.inventory_dimension import (
	get_inventory_dimensions,
)

from erpnext.vi_tri_kho.vitri.so import tong_ton_vi_tri


def _co_inventory_dimension(sle) -> bool:
	"""Dòng SLE này có mang giá trị ở BẤT KỲ inventory dimension nào đang áp
	dụng không. Site hiện có 0 `Inventory Dimension` (không đổi hành vi hôm
	nay) — kiểm tra này chỉ để không vỡ khi có ai bật dimension sau này,
	đúng như nhánh gốc `stock_ledger.py` yêu cầu (`not has_dimensions`)."""
	for dim in get_inventory_dimensions():
		if getattr(sle, dim.get("fieldname"), None):
			return True
	return False


def tinh_delta(sle) -> float:
	"""Số lượng thật SLE này làm thay đổi tồn kho — có dấu, có thể bằng 0.

	Đa số chứng từ: trả thẳng `sle.actual_qty`.

	Kiểm kê hàng không lô (`voucher_type == "Stock Reconciliation"`, không
	có `serial_and_batch_bundle`, không có `has_batch_no`, không có
	inventory dimension nào áp dụng — KHÔNG xét `actual_qty`, xem vòng sửa 1
	ở docstring module): trả `qty_after_transaction` trừ tồn hiện có trong
	sổ vị trí. Phải gọi hàm này TRƯỚC khi ghi dòng sổ vị trí của chính SLE
	đang xét, nếu không tồn đọc được đã lẫn thay đổi của chính giao dịch
	này.
	"""
	la_kiem_ke = getattr(sle, "voucher_type", None) == "Stock Reconciliation"
	co_bundle = bool(getattr(sle, "serial_and_batch_bundle", None))
	co_lo = bool(getattr(sle, "has_batch_no", None))

	if la_kiem_ke and not co_bundle and not co_lo and not _co_inventory_dimension(sle):
		kho = getattr(sle, "warehouse", None)
		vat_tu = getattr(sle, "item_code", None)
		so_lo = getattr(sle, "batch_no", None)
		ton_hien_tai = tong_ton_vi_tri(kho, vat_tu, so_lo)
		return flt(getattr(sle, "qty_after_transaction", None)) - ton_hien_tai

	return flt(getattr(sle, "actual_qty", None))

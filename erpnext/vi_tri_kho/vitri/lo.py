"""Tách một dòng SLE thành các phần theo số lô.

ERPNext v15 KHÔNG ghi batch_no lên Stock Ledger Entry. Số lô nằm ở các dòng
con `Serial and Batch Entry` dưới `Serial and Batch Bundle`, và dòng con đã
mang dấu sẵn (xuất là số âm) — đã kiểm chứng trên erptest.local: bundle của
một Delivery Note actual_qty = -3 có dòng con qty = -3, total_qty = -3.

Một dòng SLE có thể mang nhiều lô, nên hàm này trả về DANH SÁCH.

Vòng sửa 1 (điều phối, xem task-5-report.md): huỷ chứng từ đảo dấu
`actual_qty` trên SLE (`erpnext/stock/stock_ledger.py:80`,
`sle["actual_qty"] = -flt(sle.get("actual_qty"))`) nhưng KHÔNG đổi gì trên
bản ghi `Serial and Batch Bundle` đã submit trước đó — nên ở đường huỷ,
tổng qty của bundle và `delta` LỆCH DẤU nhau. `dao_theo_o_goc()` (Task 9)
có đường riêng cho huỷ, nhưng trả `False` khi không tìm được dòng sổ gốc
(chứng từ lập trước khi kho bật quản lý vị trí) — khi đó luồng rơi xuống
hàm này.

Nguyên tắc (spec §3): tầng vị trí không bao giờ tự quyết số lượng, nó chỉ
chia nhỏ con số ERPNext đã chốt. `delta` là TỔNG có thẩm quyền; bundle chỉ
cho biết TỶ LỆ chia giữa các lô — đó là thứ duy nhất chỉ bundle mới biết.
Khi hai bên khớp nhau, dùng nguyên dòng con. Khi lệch, scale theo `delta`
và giữ nguyên tỷ lệ giữa các lô.

Vòng sửa 2 (review): thứ tự so khớp phải là (1) không có dòng con, (2)
khớp `delta` trong sai số, (3) tổng bundle ~0 (không đủ tỷ lệ để chia),
(4) scale — KHÔNG được so `tong_bundle == 0` trước khi so khớp `delta`.
Sai thứ tự đó có hai hậu quả: (a) một cặp lô trái dấu tổng đúng bằng 0
(vd. đảo lô có thật, −5/+5) với delta=0 sẽ bị nuốt mất chiều lô dù đúng
ra rơi vào nhánh "không lệch"; (b) nguy hiểm hơn — tổng bundle gần-0 do
sai số dấu phẩy động (vd. 0.1+0.2−0.3 = 5.55e-17, không bằng 0 tuyệt đối)
sẽ lọt qua so sánh `== 0`, rơi vào nhánh scale, rồi CHIA CHO SỐ GẦN-0 →
số lượng từng lô cỡ ±1e16 trong khi thủ thuật dồn phần dư vẫn ép tổng
đúng bằng `delta` — sổ vị trí rác hoàn toàn ở chiều lô mà đối soát Task 10
vẫn báo khớp. Sửa bằng ngưỡng sai số (`_SAI_SO_CHO_PHEP`) thay vì so sánh
chính xác, và kiểm tra SAU khi đã so khớp delta.
"""

import frappe
from frappe.utils import flt

# Độ chính xác dùng khi chia lẻ theo tỷ lệ bundle. Không có field cụ thể
# nào định nghĩa precision cho "số lượng" ở tầng vị trí (Location Ledger
# Entry.so_luong là Float không khai precision) nên chọn một hằng số đủ
# mịn cho số lượng kho, dùng thống nhất trong toàn hàm.
_DO_CHINH_XAC_SO_LUONG = 6
_SAI_SO_CHO_PHEP = 10**-_DO_CHINH_XAC_SO_LUONG


def tach_theo_lo(sle, delta: float) -> list[dict]:
	"""Trả [{"so_lo": str|None, "so_luong": float}], tổng so_luong == delta.

	`delta` là số lượng thật đã tính ở `vitri.delta.tinh_delta()` — LUÔN là
	nguồn thẩm quyền cho TỔNG, kể cả khi có bundle. Dòng con
	`Serial and Batch Entry` của bundle chỉ đáng tin về TỶ LỆ chia giữa các
	lô: bản ghi bundle không đổi khi chứng từ bị huỷ, nên ở đường huỷ tổng
	bundle và `delta` lệch dấu — đọc thẳng qty của bundle trong ca đó sẽ ghi
	một phiếu NHẬP đã huỷ thành một dòng sổ XUẤT (tồn ma).

	Khi tổng bundle khớp `delta` trong sai số (`abs(tong_bundle - delta) <=
	_SAI_SO_CHO_PHEP`), trả NGUYÊN dòng con — không scale, không làm tròn.
	Ở nhánh đó tổng thật sự bằng `tong_bundle`, chỉ NẰM TRONG SAI SỐ của
	`delta`, không bằng đúng tuyệt đối `delta` (hai số này có thể lệch tới
	`_SAI_SO_CHO_PHEP`). Khi lệch quá ngưỡng đó, scale theo `delta` và ép
	TỔNG SAU SCALE đúng bằng `delta` làm tròn 6 chữ số — không xấp xỉ: làm
	tròn n-1 phần tử, phần tử cuối cùng = `delta` trừ tổng các phần tử
	trước, để sai số làm tròn không cộng dồn chảy vào sổ vị trí.

	Nếu tổng bundle gần 0 (không đủ tỷ lệ để chia — hoặc do dữ liệu thật,
	hoặc do sai số dấu phẩy động khi các dòng con gần triệt tiêu nhau),
	KHÔNG chia (chia cho số gần-0 ra số lượng khổng lồ) — rơi về một dòng
	chung mất chiều lô, có ghi `frappe.log_error` để truy vết.

	Không bao giờ ném lỗi khi lệch — hàm này chạy trong
	`Stock Ledger Entry.on_submit` (Task 7); ném lỗi ở đó cuộn ngược một
	giao dịch kho hợp lệ, hậu quả tệ hơn hẳn thứ đang chữa.
	"""
	bundle = getattr(sle, "serial_and_batch_bundle", None)
	if not bundle:
		return [{"so_lo": getattr(sle, "batch_no", None) or None, "so_luong": flt(delta)}]

	dong = frappe.get_all(
		"Serial and Batch Entry",
		filters={"parent": bundle},
		fields=["batch_no", "qty"],
		order_by="idx",
	)
	delta = flt(delta)

	if not dong:
		return [{"so_lo": None, "so_luong": delta}]

	tong_bundle = flt(sum(flt(d.qty) for d in dong))

	if abs(tong_bundle - delta) <= _SAI_SO_CHO_PHEP:
		# Không lệch: bundle và delta khớp nhau (đường thường) — giữ nguyên
		# dòng con, không scale, không làm tròn mất mát.
		return [{"so_lo": d.batch_no or None, "so_luong": flt(d.qty)} for d in dong]

	if abs(tong_bundle) <= _SAI_SO_CHO_PHEP:
		# Không đủ tỷ lệ để chia (tổng bundle ~0 — chia sẽ ra số lượng
		# khổng lồ). Rơi về một dòng chung, mất chiều lô nhưng KHÔNG ghi
		# rác. Ghi log để về sau truy được — không ném lỗi (chạy trong
		# on_submit).
		frappe.log_error(
			title="tach_theo_lo: bundle tổng ~0, mất chiều lô",
			message=(
				f"bundle={bundle} delta={delta} tong_bundle={tong_bundle} — "
				"tổng dòng con bundle gần 0 nên không đủ tỷ lệ để chia theo "
				"lô; ghi một dòng chung so_lo=None, so_luong=delta."
			),
		)
		return [{"so_lo": None, "so_luong": delta}]

	# Lệch (điển hình: đường huỷ đảo dấu delta mà bundle giữ nguyên) —
	# bundle chỉ còn đáng tin về TỶ LỆ, delta mới là TỔNG có thẩm quyền.
	ket_qua = []
	tong_da_chia = 0.0
	for d in dong[:-1]:
		phan = flt(flt(d.qty) * delta / tong_bundle, _DO_CHINH_XAC_SO_LUONG)
		ket_qua.append({"so_lo": d.batch_no or None, "so_luong": phan})
		tong_da_chia += phan

	d_cuoi = dong[-1]
	ket_qua.append({
		"so_lo": d_cuoi.batch_no or None,
		"so_luong": flt(delta - tong_da_chia, _DO_CHINH_XAC_SO_LUONG),
	})
	return ket_qua

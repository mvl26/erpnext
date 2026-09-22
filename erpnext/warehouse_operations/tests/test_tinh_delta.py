"""`tinh_delta(sle)` — số lượng THẬT một dòng Stock Ledger Entry làm thay
đổi tồn kho.

Với hầu hết chứng từ, `actual_qty` trên SLE đã là con số đó. Riêng
`Stock Reconciliation` (kiểm kê) với hàng KHÔNG LÔ là ngoại lệ: ERPNext ghi
`actual_qty = 0` và chỉ đặt `qty_after_transaction = tồn mới`
(`erpnext/stock/doctype/stock_reconciliation/stock_reconciliation.py:861,
870` — đã đọc lại đúng hai dòng này trên bản cài 15.83.0, xem báo cáo).
Không xử lý nhánh này = bỏ qua ÂM THẦM mọi lần kiểm kê hàng không lô.

Hàng CÓ LÔ có tách hai dòng SLE có dấu ở kiểm kê thường
(`get_sle_for_serialized_items`, dòng 809/821) nên `actual_qty` dùng được
bình thường — NHƯNG một dòng kiểm kê hàng có lô vẫn có thể mang
`actual_qty = 0` về mặt lý thuyết, và khi đó nhánh kiểm kê không được đi
tra `tong_ton_vi_tri(kho, vat_tu, sle.batch_no)` vì `sle.batch_no` LUÔN
RỖNG trên Frappe 15 (số lô nằm ở Serial and Batch Bundle — đã đo lại trên
erptest.local: 0/56 dòng SLE hàng có lô mang batch_no, 56/56 mang
serial_and_batch_bundle, khớp phép đo của Task 5). Tra theo `batch_no`
rỗng sẽ cộng nhầm tồn của các dòng KHÔNG lô vào delta của một dòng CÓ lô.
Guard đúng: dòng SLE có `serial_and_batch_bundle` thì KHÔNG được vào nhánh
tra tồn — trả thẳng `actual_qty` (đã đọc mã ERPNext xác nhận nhánh kiểm kê
hàng có lô ở submit thường luôn cho actual_qty có dấu, khác 0, trừ khi tồn
mới đúng bằng tồn cũ — auto lúc đó actual_qty=0 mới là câu trả lời ĐÚNG,
không phải một con số tra được).
"""

from unittest.mock import patch

from frappe.tests.utils import FrappeTestCase

from erpnext.warehouse_operations.vitri.delta import tinh_delta


class _SleGia:
	"""Đủ thuộc tính cho tinh_delta, không cần chạm DB — cùng khuôn với
	`_SleGia` của test_tach_theo_lo.py (Task 5)."""

	def __init__(
		self,
		voucher_type="Stock Entry",
		actual_qty=0,
		warehouse="Kho Miyano - MYN",
		item_code="_Test Item Lo",
		batch_no=None,
		serial_and_batch_bundle=None,
		qty_after_transaction=None,
	):
		self.voucher_type = voucher_type
		self.actual_qty = actual_qty
		self.warehouse = warehouse
		self.item_code = item_code
		self.batch_no = batch_no
		self.serial_and_batch_bundle = serial_and_batch_bundle
		self.qty_after_transaction = qty_after_transaction


class TestChungTuThuong(FrappeTestCase):
	"""Mọi chứng từ không phải Stock Reconciliation: trả thẳng actual_qty,
	không bao giờ đụng tong_ton_vi_tri."""

	@patch("erpnext.warehouse_operations.vitri.delta.tong_ton_vi_tri")
	def test_actual_qty_duong_giu_nguyen(self, gia_ton):
		sle = _SleGia(voucher_type="Stock Entry", actual_qty=5)
		self.assertEqual(tinh_delta(sle), 5)
		gia_ton.assert_not_called()

	@patch("erpnext.warehouse_operations.vitri.delta.tong_ton_vi_tri")
	def test_actual_qty_am_giu_nguyen_dau(self, gia_ton):
		sle = _SleGia(voucher_type="Delivery Note", actual_qty=-8)
		self.assertEqual(tinh_delta(sle), -8)
		gia_ton.assert_not_called()

	@patch("erpnext.warehouse_operations.vitri.delta.tong_ton_vi_tri")
	def test_actual_qty_khong_thi_khong_bang_khong_van_tra_thang(self, gia_ton):
		"""actual_qty=0 ở một chứng từ KHÔNG PHẢI kiểm kê (vd Stock Entry
		điều chỉnh giá trị) không được rơi vào nhánh kiểm kê."""
		sle = _SleGia(voucher_type="Stock Entry", actual_qty=0, qty_after_transaction=999)
		self.assertEqual(tinh_delta(sle), 0)
		gia_ton.assert_not_called()


class TestKiemKeHangKhongLo(FrappeTestCase):
	"""Cái bẫy chính của Task 6: kiểm kê hàng không lô ghi actual_qty=0,
	chỉ qty_after_transaction là con số thật. delta = tồn mới - tồn cũ,
	tồn cũ đọc qua tong_ton_vi_tri (sổ vị trí CỦA TA, không phải ERPNext)."""

	@patch("erpnext.warehouse_operations.vitri.delta.tong_ton_vi_tri")
	def test_kiem_ke_tang_tra_hieu_ton_moi_tru_ton_cu(self, gia_ton):
		gia_ton.return_value = 15
		sle = _SleGia(
			voucher_type="Stock Reconciliation",
			actual_qty=0,
			batch_no=None,
			serial_and_batch_bundle=None,
			qty_after_transaction=20,
		)
		self.assertEqual(tinh_delta(sle), 5)
		gia_ton.assert_called_once()
		goi_voi = gia_ton.call_args[0]
		self.assertEqual(goi_voi[:2], ("Kho Miyano - MYN", "_Test Item Lo"))
		# so_lo: None và '' tương đương theo quy ước `so_lo or ''` của
		# so.py — không ghim đúng None, chỉ ghim "rỗng" (falsy).
		self.assertFalse(goi_voi[2])

	@patch("erpnext.warehouse_operations.vitri.delta.tong_ton_vi_tri")
	def test_kiem_ke_giam_tra_am(self, gia_ton):
		gia_ton.return_value = 30
		sle = _SleGia(
			voucher_type="Stock Reconciliation",
			actual_qty=0,
			qty_after_transaction=12,
		)
		self.assertEqual(tinh_delta(sle), -18)

	@patch("erpnext.warehouse_operations.vitri.delta.tong_ton_vi_tri")
	def test_kiem_ke_dung_tong_khong_doi_thi_delta_bang_khong(self, gia_ton):
		"""qty_after_transaction == tồn cũ → delta = 0 (tồn thật sự không đổi).

		Minh hoạ thêm (KHÔNG khoá): hình dạng mock này — `tong_ton_vi_tri`
		trả về đúng `qty_after_transaction` — cũng là thứ sẽ xảy ra nếu Task
		7 lỡ gọi `tinh_delta()` SAU khi đã `ghi_dong_so()` cho cùng SLE: tồn
		"cũ" đọc được sẽ lẫn thay đổi của chính giao dịch, delta luôn ra 0,
		kiểm kê bị nuốt âm thầm. Bài test này không phân biệt được hai
		nguyên nhân đó (tồn thật không đổi, hay gọi sai thứ tự) — ràng buộc
		thứ tự chỉ khoá được ở Task 7, nơi cả hai hàm cùng tồn tại (điều
		phối đã ghi vào sổ)."""
		gia_ton.return_value = 10
		sle = _SleGia(
			voucher_type="Stock Reconciliation",
			actual_qty=0,
			qty_after_transaction=10,
		)
		self.assertEqual(tinh_delta(sle), 0)

	@patch("erpnext.warehouse_operations.vitri.delta.tong_ton_vi_tri")
	def test_actual_qty_khac_khong_khong_dimension_van_qua_qty_after_transaction(self, gia_ton):
		"""LẬT LẠI ở vòng sửa 1 Task 7 (review điều phối, model mạnh nhất) —
		bài này (thêm ở vòng sửa Task 6, tên cũ
		`test_actual_qty_khac_khong_o_sr_khong_bundle_tra_thang_khong_tra_ton`)
		TỪNG khoá "actual_qty khác 0 ở SR không bundle → trả thẳng actual_qty,
		không tra tong_ton_vi_tri". Đó là hành vi SAI, đã bị lật lại — không
		lặng lẽ, ghi rõ tại đây.

		Vì sao sai: bài cũ suy luận "actual_qty khác 0 ở SR không bundle" từ
		nhánh `has_dimensions` của `stock_reconciliation.py`, nhưng KHÔNG mô
		phỏng chính điều kiện làm nhánh đó khác biệt — có INVENTORY DIMENSION.
		Mock ở bài cũ chỉ có "không bundle, actual_qty khác 0", đúng hệt tổ
		hợp xảy ra ở đường HUỶ MỘT KIỂM KÊ HÀNG KHÔNG LÔ (`docstatus == 2`,
		`data.actual_qty = -1 * row.current_qty` — cũng khác 0, cũng không
		bundle, cũng không dimension). Đọc lại đúng mã nguồn ERPNext
		(`stock_ledger.py`, nhánh `voucher_type == "Stock Reconciliation" and
		not sle.batch_no and not sle.has_batch_no and not has_dimensions`)
		xác nhận: điều kiện đi qua `qty_after_transaction` KHÔNG XÉT
		`actual_qty` — chỉ xét loại chứng từ + không bundle + không
		has_batch_no + không dimension. Guard đúng dựa trên đúng bốn điều
		kiện đó, không dựa trên `actual_qty == 0`.

		Bài này giờ khoá NGƯỢC LẠI: actual_qty khác 0 (7), KHÔNG bundle,
		KHÔNG has_batch_no, KHÔNG dimension (site không có `Inventory
		Dimension` nào, `_co_inventory_dimension` trả False) — vẫn phải
		ĐI QUA `qty_after_transaction - tong_ton_vi_tri(...)`, bất kể
		actual_qty là bao nhiêu. Xem
		`test_actual_qty_khac_khong_CO_dimension_tra_thang_actual_qty` ngay
		dưới đây để thấy ca `has_dimensions=True` THẬT SỰ (bài cũ tưởng mình
		đang mô phỏng ca đó nhưng không hề)."""
		gia_ton.return_value = 992
		sle = _SleGia(
			voucher_type="Stock Reconciliation",
			actual_qty=7,
			batch_no=None,
			serial_and_batch_bundle=None,
			qty_after_transaction=999,
		)
		self.assertEqual(tinh_delta(sle), 7)  # 999 - 992
		gia_ton.assert_called_once()

	@patch("erpnext.warehouse_operations.vitri.delta.get_inventory_dimensions")
	@patch("erpnext.warehouse_operations.vitri.delta.tong_ton_vi_tri")
	def test_actual_qty_khac_khong_CO_dimension_tra_thang_actual_qty(self, gia_ton, gia_dim):
		"""Ca `has_dimensions=True` THẬT (bài trên KHÔNG mô phỏng được, vì
		site không có `Inventory Dimension` nào để tự nhiên kích hoạt).
		Đây là "quả mìn hẹn giờ" nói ở docstring module `delta.py` — nếu ai
		bật một Inventory Dimension, dòng SLE mang giá trị dimension đó PHẢI
		trả thẳng actual_qty (không tra sổ vị trí), đúng như
		`stock_ledger.py` (`not has_dimensions` trong điều kiện gốc)."""
		gia_dim.return_value = [{"fieldname": "vi_tri_test_dim"}]
		sle = _SleGia(
			voucher_type="Stock Reconciliation",
			actual_qty=7,
			batch_no=None,
			serial_and_batch_bundle=None,
			qty_after_transaction=999,
		)
		sle.vi_tri_test_dim = "GIA-TRI-DIMENSION"
		self.assertEqual(tinh_delta(sle), 7)
		gia_ton.assert_not_called()

	@patch("erpnext.warehouse_operations.vitri.delta.tong_ton_vi_tri")
	def test_so_lo_rong_chuoi_cung_duoc_chap_nhan(self, gia_ton):
		"""so_lo lưu '' (không NULL) theo quy ước của so.py — batch_no=''
		trên sle (thay vì None) vẫn phải đi đúng nhánh kiểm kê."""
		gia_ton.return_value = 4
		sle = _SleGia(
			voucher_type="Stock Reconciliation",
			actual_qty=0,
			batch_no="",
			qty_after_transaction=9,
		)
		self.assertEqual(tinh_delta(sle), 5)


class TestKiemKeHangCoLo(FrappeTestCase):
	"""Ca biên brief KHÔNG nói tới — hàng CÓ LÔ cũng có thể sinh SLE
	actual_qty=0 khi kiểm kê đặt lại đúng số đang có. `sle.batch_no` LUÔN
	rỗng trên Frappe 15 (đo trên erptest.local: 0/56) nên tra tồn theo
	batch_no rỗng sẽ cộng nhầm tồn của MỌI dòng không lô. Guard đúng: có
	`serial_and_batch_bundle` thì không vào nhánh tra tồn."""

	@patch("erpnext.warehouse_operations.vitri.delta.tong_ton_vi_tri")
	def test_bundle_co_actual_qty_khong_khong_tra_tong_ton_vi_tri(self, gia_ton):
		sle = _SleGia(
			voucher_type="Stock Reconciliation",
			actual_qty=0,
			batch_no=None,  # luôn rỗng trên Frappe 15, kể cả hàng có lô
			serial_and_batch_bundle="SBB-000TEST",
			qty_after_transaction=0,
		)
		self.assertEqual(tinh_delta(sle), 0)
		gia_ton.assert_not_called()

	@patch("erpnext.warehouse_operations.vitri.delta.tong_ton_vi_tri")
	def test_bundle_co_actual_qty_khac_khong_tra_thang(self, gia_ton):
		"""Kiểm kê hàng có lô ở đường thường (dòng 809/821) luôn cho
		actual_qty có dấu — trả thẳng, không tra sổ vị trí."""
		sle = _SleGia(
			voucher_type="Stock Reconciliation",
			actual_qty=-6,
			batch_no=None,
			serial_and_batch_bundle="SBB-001TEST",
			qty_after_transaction=0,
		)
		self.assertEqual(tinh_delta(sle), -6)
		gia_ton.assert_not_called()

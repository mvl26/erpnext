"""Hook ghi sổ vị trí — nhánh nhập kho và nhánh bỏ qua.

Hook móc vào Stock Ledger Entry.on_submit. Đã xác minh mọi chứng từ đều tạo
SLE qua make_entry() -> sle.submit() (erpnext stock_ledger.py:221-227), nên
một hook này bắt trọn cả 8 loại chứng từ, kể cả doctype ERPNext thêm về sau.

Hai điều bài này khoá:
1. Kho KHÔNG bật thì hook không ghi gì. Hook chạy trên mọi dòng SLE của
   toàn hệ; ghi nhầm vào kho chưa bật là làm bẩn dữ liệu của kho đó.
2. Nhập mà không khai vị trí thì hàng vào ô CHUA-XEP, KHÔNG phải bị chặn.
   Chặn là làm người dùng không nhập kho được; CHUA-XEP biến việc bỏ sót
   thành hữu hình (có báo cáo nhắc dọn) thay vì thành lỗi.

Vòng sửa điều phối (Task 7): brief chỉ khoá được hai điều trên bằng test
mock/từng phần ở Task 1-6. Hai điều bắt buộc còn lại CHỈ khoá được ở đây,
lần đầu có chứng từ thật nối `tinh_delta` với `ghi_dong_so`:

3. Thứ tự gọi `tinh_delta(sle)` TRƯỚC `ghi_dong_so` cho CÙNG một dòng SLE.
   `TestThuTuTinhDeltaTruocKhiGhi` dùng kịch bản kiểm kê hàng không lô có
   tồn sẵn khác 0 — nhánh DUY NHẤT của `tinh_delta` đọc lại sổ vị trí
   (`vitri/delta.py`) — để buộc thứ tự sai lộ ra bằng số liệu sai, không
   phải bằng mock đếm lời gọi.
4. Dòng SLE `is_cancelled=1` (sinh ra khi huỷ chứng từ, xem
   `erpnext/stock/stock_ledger.py:66-90,212`) KHÔNG bị hook bỏ qua —
   `TestHuyChungTu` khoá lựa chọn "xử lý như dòng thường, dồn vào CHUA-XEP"
   cho giai đoạn này (xem thêm docstring `vitri/hook_sle.py`).

Ghi chú riêng cho `TestNhapHangCoLo` (test_so_lo_khong_duoc_rong): dùng
`batch_number_series` ở `_tao_item` để item có lô tự sinh số lô hợp lệ khi
Material Receipt insert — nếu không set, "has_batch_no=1" mà thiếu series sẽ
làm insert Stock Entry báo lỗi thiếu số lô, không liên quan gì tới hook.

VÒNG SỬA 1 (review điều phối, model mạnh nhất): thêm
`TestThuTuTinhDeltaTruocKhiGhi.test_huy_kiem_ke_hang_khong_lo_phai_khop_bin_doc_lap`
— khoá một Critical: HUỶ một kiểm kê (Stock Reconciliation) hàng KHÔNG LÔ
từng làm vỡ bất biến §3 Ở CẤP KHO (không chỉ cấp lô như khuyết tật đã ghim ở
`TestHuyChungTu`). Gốc rễ và cách sửa nằm ở `vitri/delta.py` (Task 6), xem
docstring ở đó. Cũng thêm
`test_kiem_ke_thuong_hang_co_lo_van_tra_thang_actual_qty` để xác nhận sửa
guard không làm hỏng đường kiểm kê thường hàng CÓ lô trên chứng từ thật.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from erpnext.warehouse_operations.vitri import kho as vk
from erpnext.warehouse_operations.vitri import so
from erpnext.warehouse_operations.vitri.bat_kho import tao_o_chua_xep
from erpnext.warehouse_operations.vitri.delta import tinh_delta

KHO = "Kho Miyano - MYN"
KHO_TAT = "Stores - MYN"


def _bat_kho_tho(kho):
	"""Bật cờ + tạo ô CHUA-XEP bằng tay, không qua Warehouse Location Setup.

	Task 11-13 mới dựng chức năng bật thật. Ở đây chỉ cần đủ điều kiện để
	hook chạy.
	"""
	# Gọi hàm production thay vì tự `insert()`. Bản trước bỏ trống
	# `thu_tu_lay_hang` nên ô test nhận 0 (lấy ĐẦU) còn ô thật là 9999 (lấy
	# CUỐI) — lệch đó đã làm một bài FEFO khoá ngược hành vi thật (xem
	# docstring `bat_kho.tao_o_chua_xep`).
	tao_o_chua_xep(kho)
	frappe.db.set_value("Warehouse", kho, "custom_quan_ly_vi_tri", 1)
	vk.xoa_cache_kho(kho)


def _tat_kho_tho(kho):
	frappe.db.set_value("Warehouse", kho, "custom_quan_ly_vi_tri", 0)
	vk.xoa_cache_kho(kho)


def _nhap_kho(item, qty, kho=KHO):
	se = frappe.get_doc(
		{
			"doctype": "Stock Entry",
			"stock_entry_type": "Material Receipt",
			"company": "Miyano Việt Nam",
			"items": [{"item_code": item, "qty": qty, "t_warehouse": kho, "basic_rate": 1000}],
		}
	)
	se.insert(ignore_permissions=True)
	se.submit()
	return se


def _tao_item(ma, co_lo=0):
	if not frappe.db.exists("Item", ma):
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": ma,
				"item_name": ma,
				"item_group": "All Item Groups",
				"stock_uom": "Nos",
				"is_stock_item": 1,
				"has_batch_no": co_lo,
				"create_new_batch": co_lo,
				"batch_number_series": f"{ma}-.###" if co_lo else None,
			}
		).insert(ignore_permissions=True)
	return ma


class TestKhoKhongBat(FrappeTestCase):
	def setUp(self):
		_tat_kho_tho(KHO_TAT)
		self.item = _tao_item("_Test WMS Bo Qua")

	def test_khong_ghi_dong_so_nao(self):
		truoc = frappe.db.count("Location Ledger Entry", {"kho": KHO_TAT})
		_nhap_kho(self.item, 5, kho=KHO_TAT)
		self.assertEqual(frappe.db.count("Location Ledger Entry", {"kho": KHO_TAT}), truoc)


class TestNhapKhongKhaiViTri(FrappeTestCase):
	def setUp(self):
		_bat_kho_tho(KHO)
		self.item = _tao_item("_Test WMS Nhap")

	def tearDown(self):
		_tat_kho_tho(KHO)

	def test_hang_vao_o_chua_xep(self):
		"""Dùng item RIÊNG cho bài này (không phải self.item dùng chung của
		lớp): FrappeTestCase chỉ rollback theo LỚP, không theo từng bài
		(đã ghi ở test_so_vi_tri.py); ba bài trong lớp này CHẠY CHUNG một
		transaction theo thứ tự alphabet của tên hàm
		(bat_bien < dong_so < hang_vao), nên nếu dùng chung self.item với
		hai bài kia thì ton_o ở đây sẽ CỘNG DỒN cả phần hai bài trước đã
		nhập, không còn đúng bằng 12 nữa. Đặt tên riêng để bài này tự đứng
		độc lập, không phụ thuộc thứ tự chạy."""
		item = _tao_item("_Test WMS Nhap Rieng")
		_nhap_kho(item, 12)
		o = vk.o_chua_xep(KHO)
		self.assertEqual(so.ton_o(o, item, None), 12)

	def test_bat_bien_tong_ton_bang_bin(self):
		_nhap_kho(self.item, 12)
		bin_qty = frappe.db.get_value("Bin", {"item_code": self.item, "warehouse": KHO}, "actual_qty")
		self.assertEqual(so.tong_ton_vi_tri(KHO, self.item, None), bin_qty)

	def test_dong_so_tro_ve_dung_chung_tu(self):
		se = _nhap_kho(self.item, 3)
		dong = frappe.get_all(
			"Location Ledger Entry",
			filters={"chung_tu": se.name},
			fields=["chung_tu_type", "so_luong", "sle"],
		)
		self.assertEqual(len(dong), 1)
		self.assertEqual(dong[0].chung_tu_type, "Stock Entry")
		self.assertEqual(dong[0].so_luong, 3)
		self.assertTrue(dong[0].sle, "phải trỏ về dòng SLE sinh ra nó, để đối soát 1-1")


class TestNhapHangCoLo(FrappeTestCase):
	def setUp(self):
		_bat_kho_tho(KHO)
		self.item = _tao_item("_Test WMS Nhap Lo", co_lo=1)

	def tearDown(self):
		_tat_kho_tho(KHO)

	def test_so_lo_khong_duoc_rong(self):
		_nhap_kho(self.item, 10)
		dong = frappe.get_all(
			"Location Ledger Entry", filters={"vat_tu": self.item}, fields=["so_lo", "so_luong"]
		)
		self.assertTrue(dong, "phải có dòng sổ")
		self.assertTrue(
			all(d.so_lo for d in dong),
			"so_lo rỗng nghĩa là hook đọc sle.batch_no thay vì Serial and Batch Bundle",
		)
		# Bất biến §3 không chỉ đúng ở chiều "có lô hay không", còn phải đúng
		# ở CON SỐ: một hook ghi đúng lô nhưng sai số lượng vẫn lọt qua assertion
		# phía trên. So khớp thẳng với Bin của ERPNext.
		bin_qty = frappe.db.get_value("Bin", {"item_code": self.item, "warehouse": KHO}, "actual_qty")
		self.assertEqual(sum(d.so_luong for d in dong), flt(bin_qty))
		self.assertEqual(sum(d.so_luong for d in dong), 10)


class TestThuTuTinhDeltaTruocKhiGhi(FrappeTestCase):
	"""Khoá ràng buộc thứ tự (điểm 1 điều phối yêu cầu, brief KHÔNG có bài
	này). Nhánh DUY NHẤT của `tinh_delta` đọc lại sổ vị trí là kiểm kê hàng
	không lô (`vitri/delta.py`): delta = qty_after_transaction (đọc từ SLE)
	trừ tồn hiện có (đọc từ `tong_ton_vi_tri`, tức sổ CỦA TA). Nếu hook lỡ
	ghi dòng sổ của SLE này TRƯỚC khi tính delta, `tong_ton_vi_tri` đọc được
	đã lẫn thay đổi của chính giao dịch đang xét → delta luôn ra 0 (đã ghim
	sẵn triệu chứng này ở test_kiem_ke_dung_tong_khong_doi_thi_delta_bang_khong
	của test_tinh_delta.py, Task 6) và tồn vị trí đứng yên dù kiểm kê đổi số.

	Kịch bản: nhập trước một số lượng X vào CHUA-XEP (qua hook, đường
	actual_qty bình thường — không phụ thuộc thứ tự). Sau đó kiểm kê đặt lại
	tồn thành Y != X cho CÙNG mặt hàng không lô, CÙNG kho. Nếu thứ tự đúng,
	tồn vị trí sau kiểm kê phải bằng Y (đúng bất biến spec §3: tổng tồn các ô
	= tồn kho ERPNext). Nếu thứ tự bị đảo, tồn vị trí đứng yên ở X.
	"""

	def setUp(self):
		_bat_kho_tho(KHO)
		self.item = _tao_item("_Test WMS Thu Tu Delta")

	def tearDown(self):
		_tat_kho_tho(KHO)

	def test_kiem_ke_sau_khi_da_co_ton_phai_khop_tong_moi(self):
		_nhap_kho(self.item, 10)
		o = vk.o_chua_xep(KHO)
		self.assertEqual(so.ton_o(o, self.item, None), 10, "tiền đề: đã có tồn 10 trước kiểm kê")

		sr = frappe.get_doc(
			{
				"doctype": "Stock Reconciliation",
				"company": "Miyano Việt Nam",
				"purpose": "Stock Reconciliation",
				"items": [
					{
						"item_code": self.item,
						"warehouse": KHO,
						"qty": 17,
						"valuation_rate": 1000,
					}
				],
			}
		)
		sr.insert(ignore_permissions=True)
		sr.submit()

		bin_qty = frappe.db.get_value("Bin", {"item_code": self.item, "warehouse": KHO}, "actual_qty")
		self.assertEqual(flt(bin_qty), 17, "tiền đề: ERPNext đã chốt tồn kho = 17")

		self.assertEqual(
			so.tong_ton_vi_tri(KHO, self.item, None),
			17,
			"tồn vị trí phải theo kịp tồn kho sau kiểm kê (=17), không đứng yên ở "
			"10 — đứng yên ở 10 nghĩa là hook đã ghi dòng sổ TRƯỚC khi tính delta, "
			"nên tinh_delta() đọc lại đúng cái nó vừa ghi và luôn ra 0",
		)
		self.assertEqual(so.ton_o(o, self.item, None), 17)

	def test_huy_kiem_ke_hang_khong_lo_phai_khop_bin_doc_lap(self):
		"""Vòng sửa 1 (review điều phối, model mạnh nhất): HUỶ một kiểm kê
		hàng KHÔNG LÔ làm vỡ bất biến §3 Ở CẤP KHO — nặng hơn hẳn khuyết tật
		mất-chiều-lô đã ghim ở `TestHuyChungTu`, vì cái đó net 0 ở cấp kho,
		cái này thì KHÔNG.

		Gốc rễ (đọc lại đúng mã ERPNext, hai mắt xích):
		1. `stock_reconciliation.py` (`get_sle_for_items`, nhánh
		   `self.docstatus == 2 and (not row.batch_no or not
		   row.serial_and_batch_bundle)`, rồi `if row.current_qty and
		   current_bundle`): khi HUỶ kiểm kê hàng không lô, ERPNext đặt
		   `data.actual_qty = -1 * row.current_qty` — KHÁC 0 (không phải 0
		   như đường ghi thường) — và `data.qty_after_transaction =
		   flt(row.current_qty)` (tồn TRƯỚC kiểm kê, tức tồn sẽ quay về sau
		   khi huỷ).
		2. `stock_ledger.py` (nhánh `voucher_type == "Stock Reconciliation"
		   and not sle.batch_no and not sle.has_batch_no and not
		   has_dimensions`): ERPNext lấy THẲNG `sle.qty_after_transaction`
		   làm tồn kho cuối cùng (Bin), bỏ qua `actual_qty` hoàn toàn — điều
		   kiện này KHÔNG phân biệt submit hay cancel.

		Guard cũ của `tinh_delta` (`not delta`, tức đòi `actual_qty == 0`)
		chỉ đúng ở đường ghi thường (actual_qty TÌNH CỜ bằng 0 ở đó) — sai ở
		đường huỷ vì actual_qty ở đó khác 0. Hệ quả: nhánh kiểm kê (đọc lại
		sổ vị trí, dùng qty_after_transaction) bị bỏ qua đúng lúc cần nhất,
		`tinh_delta` trả thẳng actual_qty sai trong khi Bin đi theo
		qty_after_transaction.

		Kịch bản: nhập 10 → kiểm kê đặt 17 → HUỶ kiểm kê. Bin phải quay về
		10 (giá trị trước kiểm kê). So `tong_ton_vi_tri` với `Bin.actual_qty`
		đọc từ NGUỒN ĐỘC LẬP (không phải chính `tinh_delta`/`tong_ton_vi_tri`
		— Bin do chính lõi ERPNext tự tính, không đi qua bất kỳ hàm nào của
		`vitri/`).

		Dùng item RIÊNG (`_Test WMS Huy Kiem Ke`), KHÔNG dùng `self.item` —
		lớp này chạy nhiều bài trong CÙNG một transaction, không rollback
		theo từng bài (đã ghi ở `test_hang_vao_o_chua_xep`); nếu dùng chung
		`self.item` với bài `test_kiem_ke_sau_khi_da_co_ton_phai_khop_tong_moi`
		thì hai bài cộng dồn lẫn nhau tuỳ thứ tự chạy alphabet.

		Ghi chú sau Task 9 (Minor 5, review điều phối vòng sửa 1): từ khi có
		`dao_theo_o_goc`, bài này KHÔNG còn đo đường "rơi xuống tinh_delta,
		đọc lại qty_after_transaction" ở lúc HUỶ nữa — `dao_theo_o_goc` tìm
		thấy đúng dòng sổ gốc (ghi lúc SR submit, do nhánh kiểm kê của
		`tinh_delta` tạo ra) và trả True, `ghi_so_vi_tri` return sớm TRƯỚC
		khi chạm `tinh_delta` ở đường huỷ. Bài vẫn xanh với đối chiếu `Bin`
		độc lập — đây là bằng chứng DUY NHẤT rằng việc `dao_theo_o_goc`
		return sớm không âm thầm phá bất biến mà vòng sửa 1 của Task 7 đã
		khoá (nhánh kiểm kê của `tinh_delta` ở đường SUBMIT vẫn đúng, và
		đường HUỶ giờ do `dao_theo_o_goc` đảm nhiệm thay vì `tinh_delta`) —
		và cũng là ca huỷ Stock Reconciliation hàng KHÔNG LÔ ĐÃ ĐƯỢC ĐO cho
		Task 9 (khác với Stock Reconciliation hàng CÓ lô, xem
		`test_huy_kiem_ke_hang_co_lo_phai_khop_bin_doc_lap` ngay dưới)."""
		item = _tao_item("_Test WMS Huy Kiem Ke")
		_nhap_kho(item, 10)
		o = vk.o_chua_xep(KHO)
		self.assertEqual(so.ton_o(o, item, None), 10, "tiền đề: đã có tồn 10 trước kiểm kê")

		sr = frappe.get_doc(
			{
				"doctype": "Stock Reconciliation",
				"company": "Miyano Việt Nam",
				"purpose": "Stock Reconciliation",
				"items": [
					{
						"item_code": item,
						"warehouse": KHO,
						"qty": 17,
						"valuation_rate": 1000,
					}
				],
			}
		)
		sr.insert(ignore_permissions=True)
		sr.submit()
		self.assertEqual(
			so.tong_ton_vi_tri(KHO, item, None),
			17,
			"tiền đề: sau kiểm kê, sổ vị trí đã theo kịp (đường submit, đã khoá ở " "bài trên)",
		)

		sr.cancel()

		bin_qty_doc_lap = frappe.db.get_value("Bin", {"item_code": item, "warehouse": KHO}, "actual_qty")
		self.assertEqual(
			flt(bin_qty_doc_lap),
			10,
			"tiền đề: ERPNext (nguồn độc lập, không qua vitri/) đã đưa tồn kho về "
			"lại 10 — giá trị TRƯỚC kiểm kê — sau khi huỷ",
		)

		self.assertEqual(
			so.tong_ton_vi_tri(KHO, item, None),
			10,
			"tồn vị trí phải khớp Bin (=10) sau khi huỷ kiểm kê, KHÔNG được ra 27 "
			"(17 giữ nguyên + actual_qty=-10 huỷ cộng nhầm theo kiểu 'giảm thêm 10 "
			"từ 17') hay 7 (delta tính sai dấu) — cả hai đều sai vì tinh_delta() đã "
			"dùng thẳng actual_qty của dòng huỷ thay vì đọc lại qty_after_transaction "
			"như đường kiểm kê thường bắt buộc phải làm",
		)

	def test_huy_kiem_ke_hang_co_lo_phai_khop_bin_doc_lap(self):
		"""Vòng sửa 2 (review điều phối, model mạnh nhất, sau khi Task 9
		"xong"): điều phối chỉ ra một Critical GIẢ ĐỊNH — huỷ kiểm kê hàng
		CÓ LÔ có thể vỡ bất biến §3 Ở CẤP KHO vì `make_sle_on_cancel`
		(`stock_reconciliation.py` ~903-916) sinh HAI dòng SLE huỷ cùng
		`voucher_detail_no`/`warehouse`/`item_code` cho MỘT `row` (khi
		`row.serial_and_batch_bundle and row.current_serial_and_batch_bundle`
		đều có) — bộ lọc `(kho, vat_tu)` của `dao_theo_o_goc` (vòng sửa 1)
		không tách được hai SLE này, nên SLE huỷ THỨ HAI có thể thấy `goc`
		rỗng (đã bị SLE thứ nhất cờ `da_huy=1`) và hiểu NHẦM thành "chứng từ
		lập trước khi bật quản lý vị trí", rơi xuống đường thường.

		ĐO THỰC TẾ (debug `Stock Ledger Entry`/`Location Ledger Entry` thật
		trên erptest.local, xoá sau khi đo — xem task-9-report.md "Vòng sửa
		2"): kịch bản này (kiểm kê lại MỘT lô đã tồn tại bằng `batch_no` +
		`use_serial_batch_fields=1`) ĐÚNG là sinh hai dòng SLE huỷ cùng
		khoá lọc như trên — nhưng CẢ HAI dòng SLE huỷ đều có `actual_qty=0`
		(không phải "khác 0" như suy luận ban đầu): điều kiện gán
		`actual_qty` khác 0 ở `get_sle_for_items` (dòng ~878) là
		`not row.batch_no or not row.serial_and_batch_bundle`; ở kịch bản
		này CẢ HAI đều có giá trị nên điều kiện sai, `actual_qty` giữ mặc
		định 0 — `tinh_delta` trả 0 bất kể nhánh nào, `if not delta: return`
		chặn hook trước khi kịp ghi thừa. Vì vậy bài này ĐÃ XANH kể cả
		TRƯỚC vòng sửa 2 (dùng để đo trước khi sửa) — sửa vẫn được áp dụng
		vì đây là hardening đúng đắn, rẻ, không đổi bất kỳ bài nào khác:
		phân biệt "chưa từng có dòng gốc" (trả False, giữ điều bắt buộc #3)
		khỏi "SLE anh em CÙNG khoá lọc đã đảo xong dòng này rồi" (còn ít
		nhất một dòng gốc `da_huy=1` khớp khoá — trả True, không rơi xuống
		đường thường) — đúng ngữ nghĩa tài liệu của `dao_theo_o_goc`, đóng
		một lỗ hổng KHÁI NIỆM dù chưa đo được ca nó thật sự gây hại (cần
		`row.batch_no` rỗng trong khi `row.serial_and_batch_bundle` có giá
		trị — chỉ xảy ra khi gắn thẳng một Serial and Batch Bundle có sẵn
		thay vì dùng `use_serial_batch_fields`; CHƯA dựng được kịch bản này
		trong ngân sách thời gian, xem "chưa kiểm chứng" trong report).
		"""
		item = _tao_item("_Test WMS Huy Kiem Ke Co Lo", co_lo=1)
		_nhap_kho(item, 10)

		so_lo_dong_truoc = frappe.get_all("Location Ledger Entry", filters={"vat_tu": item}, fields=["so_lo"])
		self.assertEqual(len(so_lo_dong_truoc), 1)
		so_lo = so_lo_dong_truoc[0].so_lo
		self.assertTrue(so_lo, "tiền đề: dòng nhập phải mang lô thật")

		sr = frappe.get_doc(
			{
				"doctype": "Stock Reconciliation",
				"company": "Miyano Việt Nam",
				"purpose": "Stock Reconciliation",
				"items": [
					{
						"item_code": item,
						"warehouse": KHO,
						"qty": 17,
						"valuation_rate": 1000,
						"batch_no": so_lo,
						"use_serial_batch_fields": 1,
					}
				],
			}
		)
		sr.insert(ignore_permissions=True)
		sr.submit()
		self.assertEqual(
			so.tong_ton_vi_tri(KHO, item, so_lo),
			17,
			"tiền đề: sau kiểm kê, sổ vị trí đã theo kịp (đường submit)",
		)

		sr.cancel()

		# Đo được (debug thật, xem task-9-report.md "Vòng sửa 2"): huỷ kiểm
		# kê hàng có lô sinh HAI dòng SLE huỷ cùng voucher_detail_no/kho/
		# vat_tu (đúng như make_sle_on_cancel), CẢ HAI dòng gốc (submit) đều
		# bị dao_theo_o_goc() của SLE huỷ ĐẦU TIÊN vớt và đảo trong MỘT lần
		# gọi (không cần SLE huỷ thứ hai) — nên đúng 4 dòng sổ cho chứng từ
		# này: 2 gốc (da_huy=1) + 2 đảo (da_huy=1).
		dong_sau_huy = frappe.get_all(
			"Location Ledger Entry",
			filters={"chung_tu": sr.name},
			fields=["so_luong", "da_huy"],
		)
		self.assertEqual(len(dong_sau_huy), 4, "2 dòng gốc (submit) + 2 dòng đảo (cancel)")
		self.assertTrue(all(d.da_huy for d in dong_sau_huy), "sổ chỉ ghi thêm — cờ da_huy, không xoá")

		bin_qty_doc_lap = frappe.db.get_value("Bin", {"item_code": item, "warehouse": KHO}, "actual_qty")
		self.assertEqual(
			flt(bin_qty_doc_lap),
			10,
			"tiền đề: ERPNext (nguồn độc lập) đã đưa tồn kho về lại 10 sau huỷ",
		)

		self.assertEqual(
			so.tong_ton_vi_tri(KHO, item, so_lo),
			10,
			"tồn vị trí phải khớp Bin (=10) sau khi huỷ kiểm kê hàng có lô — "
			"trước vòng sửa 2, hai SLE huỷ cùng voucher_detail_no/kho/vat_tu "
			"làm hook ghi thừa một dòng, tồn vị trí lệch khỏi Bin ở CẤP KHO",
		)

	def test_kiem_ke_thuong_hang_co_lo_van_tra_thang_actual_qty(self):
		"""Vòng sửa 1: điều kiện chọn nhánh giờ dựa trên has_batch_no/bundle
		thay vì actual_qty==0 — phải xác nhận hàng CÓ LÔ ở kiểm kê thường
		(không phải ca huỷ) vẫn đi đường actual_qty bình thường, không bị
		lôi nhầm vào nhánh đọc lại sổ vị trí chỉ vì batch_no luôn rỗng trên
		Frappe 15. Dùng chứng từ thật, không mock, khác với bài cùng tên ở
		test_tinh_delta.py (Task 6, mock)."""
		item = _tao_item("_Test WMS Kiem Ke Thuong Co Lo", co_lo=1)
		_nhap_kho(item, 10)

		# Mặt hàng CÓ lô: tồn nằm ở bucket đúng theo so_lo, KHÔNG phải bucket
		# rỗng (None) như hàng không lô — khác `ton_o(o, item, None)` của các
		# bài hàng-không-lô ở trên.
		so_lo_dong_truoc = frappe.get_all("Location Ledger Entry", filters={"vat_tu": item}, fields=["so_lo"])
		self.assertEqual(len(so_lo_dong_truoc), 1)
		so_lo = so_lo_dong_truoc[0].so_lo
		self.assertTrue(so_lo, "tiền đề: dòng nhập phải mang lô thật")
		self.assertEqual(so.tong_ton_vi_tri(KHO, item, so_lo), 10, "tiền đề: đã có tồn 10 theo đúng lô")

		sr = frappe.get_doc(
			{
				"doctype": "Stock Reconciliation",
				"company": "Miyano Việt Nam",
				"purpose": "Stock Reconciliation",
				"items": [
					{
						"item_code": item,
						"warehouse": KHO,
						"qty": 6,
						"valuation_rate": 1000,
						"batch_no": so_lo,
						"use_serial_batch_fields": 1,
					}
				],
			}
		)
		sr.insert(ignore_permissions=True)
		sr.submit()

		bin_qty = frappe.db.get_value("Bin", {"item_code": item, "warehouse": KHO}, "actual_qty")
		self.assertEqual(flt(bin_qty), 6)
		self.assertEqual(
			so.tong_ton_vi_tri(KHO, item, so_lo),
			6,
			"kiểm kê hàng có lô ở đường thường phải khớp Bin theo đúng lô, không "
			"bị nhánh 'không lô' của tinh_delta xử lý sai",
		)


class TestHuyChungTu(FrappeTestCase):
	"""Khoá lựa chọn cho điểm 2 điều phối yêu cầu (dòng SLE is_cancelled=1),
	brief KHÔNG có bài này. Huỷ chứng từ: `set_as_cancel()` cờ CÁC DÒNG CŨ
	bằng SQL thô TRƯỚC (erpnext stock_ledger.py, ~dòng 66-70), RỒI MỚI sinh
	SLE MỚI với actual_qty đảo dấu và is_cancelled=1 qua make_entry() ->
	submit() (~dòng 80-90) — đã sửa lại thứ tự câu chữ ở vòng sửa 1 (review
	điều phối), trước đây ghi ngược. Hệ quả không đổi: dòng cũ không qua
	submit() nên không kích hook lần hai, chỉ dòng MỚI mới chạy hook.

	Lựa chọn của Task 7 (xem docstring `hook_sle.py`): KHÔNG lọc bỏ dòng
	is_cancelled — cho nó đi qua đúng đường bình thường (tính delta, tách
	lô, dồn vào CHUA-XEP của sle.warehouse). Đường trả hàng về ĐÚNG Ô GỐC là
	Task 9; ở đây chỉ cần tồn vị trí THEO KỊP tồn kho sau khi huỷ, không rơi
	vào tồn ma."""

	def setUp(self):
		_bat_kho_tho(KHO)
		self.item = _tao_item("_Test WMS Huy Chung Tu")

	def tearDown(self):
		_tat_kho_tho(KHO)

	def test_huy_khong_bi_bo_qua_tong_ton_ve_lai_dung(self):
		se = _nhap_kho(self.item, 8)
		o = vk.o_chua_xep(KHO)
		self.assertEqual(so.ton_o(o, self.item, None), 8, "tiền đề: đã nhập 8")

		truoc = frappe.db.count("Location Ledger Entry", {"chung_tu": se.name})
		self.assertEqual(truoc, 1)

		se.cancel()

		sau = frappe.db.count("Location Ledger Entry", {"chung_tu": se.name})
		self.assertEqual(
			sau,
			2,
			"huỷ phải sinh thêm đúng 1 dòng sổ vị trí nữa (đảo dấu) — nếu vẫn là "
			"1 nghĩa là hook đã lọc bỏ dòng SLE is_cancelled=1",
		)

		dong_moi = frappe.get_all(
			"Location Ledger Entry",
			filters={"chung_tu": se.name},
			fields=["so_luong", "da_huy"],
			order_by="creation",
		)
		self.assertEqual(dong_moi[-1].so_luong, -8, "dòng đảo phải mang số lượng -8")
		self.assertEqual(
			dong_moi[-1].da_huy,
			1,
			"Task 9 (dao_theo_o_goc) đánh dấu da_huy=1 cho dòng đảo mà chính nó "
			"ghi — cập nhật từ giá trị 0 mà Task 7 để mặc định (xem docstring cũ "
			"đã lệch, task-9-report.md)",
		)

		bin_qty = frappe.db.get_value("Bin", {"item_code": self.item, "warehouse": KHO}, "actual_qty")
		self.assertEqual(flt(bin_qty), 0, "tiền đề: ERPNext đã đưa tồn kho về 0 sau huỷ")
		self.assertEqual(
			so.tong_ton_vi_tri(KHO, self.item, None),
			0,
			"tồn vị trí phải về lại 0 theo kịp tồn kho, không đứng yên ở 8 (tồn ma)",
		)

	def test_huy_hang_co_lo_giu_dung_chieu_lo(self):
		"""CHỨNG MINH ĐÃ SỬA — trước Task 9 bài này ghim một khiếm khuyết thật.

		Lịch sử (Task 7, trước khi có Task 9): dòng SLE đảo dấu khi huỷ
		Stock Entry hàng có lô mang `serial_and_batch_bundle = None` (đo
		thực tế trên erptest.local, Frappe 15.113.4 / ERPNext 15.83.0) nên
		`sle.batch_no` không dùng được và `tach_theo_lo` rơi vào nhánh
		"không có bundle", trả `so_lo=None` — dòng sổ vị trí đảo dấu MẤT
		CHIỀU LÔ (tồn ma +10 ở lô thật, tồn ảo -10 ở bucket không-lô, chỉ
		triệt tiêu ở MỨC KHO chứ không đúng ở mức (mặt hàng, lô, kho) — vi
		phạm spec §3).

		Task 9 sửa gốc rễ: KHÔNG dựa vào `serial_and_batch_bundle` của
		chính dòng SLE huỷ (đã bị ERPNext xoá) mà tra ngược dòng
		`Location Ledger Entry` GỐC theo (chung_tu_type, chung_tu,
		chung_tu_row) — nơi số lô đã được lưu sẵn lúc ghi lúc chứng từ
		submit, còn nguyên vì sổ chỉ ghi thêm — rồi ghi đảo đúng lô đó
		(`dao_theo_o_goc`, `vitri/hook_sle.py`). Bài test này giờ khẳng
		định hành vi đã sửa: dòng đảo mang ĐÚNG lô gốc, và bất biến §3 được
		giữ ở mức (mặt hàng, lô, kho), không chỉ mức kho.
		"""
		item = _tao_item("_Test WMS Huy Co Lo", co_lo=1)
		se = _nhap_kho(item, 10)

		dong_truoc = frappe.get_all(
			"Location Ledger Entry", filters={"chung_tu": se.name}, fields=["so_lo", "so_luong"]
		)
		self.assertEqual(len(dong_truoc), 1)
		so_lo = dong_truoc[0].so_lo
		self.assertTrue(so_lo, "tiền đề: dòng nhập phải mang lô thật")

		se.cancel()

		dong_sau = frappe.get_all(
			"Location Ledger Entry",
			filters={"chung_tu": se.name},
			fields=["so_lo", "so_luong", "da_huy"],
			order_by="creation",
		)
		self.assertEqual(len(dong_sau), 2, "huỷ phải sinh thêm đúng 1 dòng sổ đảo")
		dong_dao = dong_sau[-1]
		self.assertEqual(
			dong_dao.so_lo,
			so_lo,
			"dòng đảo phải mang ĐÚNG lô gốc (tra ngược qua dao_theo_o_goc), "
			"không còn mất chiều lô như trước Task 9",
		)
		self.assertEqual(dong_dao.so_luong, -10)
		self.assertEqual(
			dong_dao.da_huy,
			1,
			"dao_theo_o_goc tự cờ da_huy=1 cho dòng đảo mà chính nó ghi",
		)
		self.assertEqual(
			dong_sau[0].da_huy,
			1,
			"dòng gốc phải bị cờ da_huy=1 (không xoá, không sửa số liệu — chỉ cờ)",
		)

		ton_lo_cu = so.tong_ton_vi_tri(KHO, item, so_lo)
		ton_lo_rong = so.tong_ton_vi_tri(KHO, item, None)
		self.assertEqual(
			ton_lo_cu,
			0,
			"không còn tồn ma: dòng đảo trỏ đúng về lô gốc nên +10/-10 triệt "
			"tiêu NGAY ở mức lô, không chỉ ở mức kho",
		)
		self.assertEqual(
			ton_lo_rong,
			0,
			"không còn tồn ảo: bucket 'không lô' không bị dòng đảo đụng tới nữa",
		)
		bin_qty = frappe.db.get_value("Bin", {"item_code": item, "warehouse": KHO}, "actual_qty")
		self.assertEqual(flt(bin_qty), 0, "tiền đề: ERPNext đã đưa tồn kho về 0 sau huỷ")

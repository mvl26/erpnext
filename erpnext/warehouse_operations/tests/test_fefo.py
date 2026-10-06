"""Chọn ô khi xuất mà chứng từ không khai vị trí.

Thứ tự: hạn dùng gần nhất trước (FEFO), cùng hạn thì theo thu_tu_lay_hang
(đường đi trong kho). Lô không có hạn dùng xếp SAU CÙNG — không phải trước:
"không biết hạn" khác hẳn "hết hạn hôm nay", và đẩy nó lên đầu là ưu tiên
xuất đúng những lô mình biết ít nhất về chúng.

Ô CHUA-XEP vẫn được chọn — hàng nằm ở đó là hàng thật, chỉ là chưa ai xếp.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from erpnext.warehouse_operations.vitri import kho as vk
from erpnext.warehouse_operations.vitri import so
from erpnext.warehouse_operations.vitri.bat_kho import tao_o_chua_xep
from erpnext.warehouse_operations.vitri.fefo import chon_o_xuat

KHO = "Kho Miyano - MYN"


def _o(ma_o, thu_tu=0):
	if not frappe.db.exists("Storage Location", ma_o):
		frappe.get_doc(
			{
				"doctype": "Storage Location",
				"ma_o": ma_o,
				"kho": KHO,
				"thu_tu_lay_hang": thu_tu,
			}
		).insert(ignore_permissions=True)
	return ma_o


def _lo(ma, item, han=None):
	if not frappe.db.exists("Batch", ma):
		frappe.get_doc(
			{
				"doctype": "Batch",
				"batch_id": ma,
				"item": item,
				"expiry_date": han,
			}
		).insert(ignore_permissions=True)
	return ma


def _dat(o, vat_tu, so_lo, sl):
	# Lệch khỏi brief: brief dùng chung_tu_type="Stock Entry",
	# chung_tu="FEFO-SEED" (chứng từ giả, không tồn tại). so.ghi_dong_so
	# hiện KHÔNG ignore_links (vòng sửa 1 của Task 4, xem docstring so.py) —
	# chứng từ phải là bản ghi có thật, không thì LinkValidationError. Đổi
	# sang trỏ về chính Storage Location `o` (luôn có thật, đã tạo trước khi
	# gọi _dat), giống quy ước đã dùng ở test_so_vi_tri.py::_ghi.
	so.ghi_dong_so(
		o=o,
		kho=KHO,
		vat_tu=vat_tu,
		so_lo=so_lo,
		so_luong=sl,
		chung_tu_type="Storage Location",
		chung_tu=o,
		chung_tu_row="r",
		sle=None,
		ngay="2026-09-01",
		thoi_diem="2026-09-01 08:00:00",
		company="Miyano Việt Nam",
	)


def _dam_bao_item(ma_item="_Test FEFO Item"):
	# Lệch khỏi brief, hai điểm:
	# (a) brief chỉ tạo "_Test FEFO Item" một lần trong setUp của
	#     TestChonTheoDuongDi, ngầm định các lớp Test* khác chạy SAU sẽ thấy
	#     item đó. FrappeTestCase rollback theo LỚP (mỗi TestCase class là
	#     một transaction/savepoint riêng, không thấy dữ liệu lớp khác) —
	#     đúng cái bẫy đã ghi ở memory "test isolation". Mỗi lớp phải tự
	#     đảm bảo item tồn tại trong setUp của chính nó — hàm này nhận
	#     tham số `ma_item` để mỗi BÀI (không chỉ mỗi lớp) có thể dùng một
	#     mặt hàng riêng khi bài đó khẳng định giá trị tuyệt đối và các bài
	#     khác CÙNG LỚP (rollback theo lớp, không theo bài — chung transaction)
	#     có thể để lại tồn/lô của mặt hàng dùng chung.
	# (b) thêm has_batch_no=1 — bài viết lô (_lo) cần Item bật quản lý lô,
	#     nếu không ERPNext báo "The selected item cannot have Batch" khi
	#     insert Batch.
	if not frappe.db.exists("Item", ma_item):
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": ma_item,
				"item_name": ma_item,
				"item_group": "All Item Groups",
				"stock_uom": "Nos",
				"is_stock_item": 1,
				"has_batch_no": 1,
			}
		).insert(ignore_permissions=True)
	return ma_item


class TestChonTheoDuongDi(FrappeTestCase):
	# Ba bài dưới đây khẳng định giá trị TUYỆT ĐỐI (danh sách kết quả đầy
	# đủ), nên mỗi bài dùng mặt hàng RIÊNG: lớp này rollback theo LỚP (một
	# transaction chung cho cả 3 bài), tồn/ô của bài chạy trước còn nguyên
	# khi bài sau chạy — nếu dùng chung "_Test FEFO Item", ô "TEST-FEFO-GAN"
	# (thu_tu=1) của bài cung_lo vẫn còn tồn khi bài khong_du chạy và bị
	# chọn nhầm vào kết quả (đã đo thấy thật khi chạy với item dùng chung).
	def test_cung_lo_thi_theo_thu_tu_lay_hang(self):
		# Tên ô CỐ Ý ngược alphabet so với thu_tu_lay_hang (vòng sửa 2, review
		# điều phối): ô được ưu tiên (thu_tu=1) mang tên xếp SAU trong bảng
		# chữ cái, ô bị đẩy sau (thu_tu=9) mang tên xếp TRƯỚC. Trước sửa, tên
		# "GAN" (ưu tiên) < "XA" (không ưu tiên) tình cờ khớp luôn thứ tự ưu
		# tiên — nếu ai xoá khoá sort thu_tu_lay_hang khỏi SQL, tie-break rơi
		# xuống `lb.o asc` và VẪN ra đúng đáp án, bài không bao giờ đỏ. Đã đo
		# thật (xem task-8-report.md, "Vòng sửa 2"): xoá khoá sort đi, bài
		# NÀY đỏ đúng như kỳ vọng; phục hồi thì xanh lại.
		item = _dam_bao_item("_Test FEFO CungLo")
		xa, gan = _o("9Z01010101", thu_tu=9), _o("9Z99010101", thu_tu=1)
		_dat(xa, item, None, 10)
		_dat(gan, item, None, 10)
		ket_qua = chon_o_xuat(KHO, item, None, 4)
		self.assertEqual(ket_qua, [{"o": gan, "so_luong": 4}])

	def test_khong_du_mot_o_thi_lay_tiep_o_sau(self):
		# Cùng lý do trên: ô lấy TRƯỚC (thu_tu=1) đặt tên xếp SAU alphabet,
		# ô lấy SAU (thu_tu=2) đặt tên xếp TRƯỚC — trước sửa "A" (lấy trước)
		# < "B" (lấy sau) tình cờ khớp thứ tự.
		item = _dam_bao_item("_Test FEFO KhongDu")
		a, b = _o("9Z98010101", thu_tu=1), _o("9Z02010101", thu_tu=2)
		_dat(a, item, None, 3)
		_dat(b, item, None, 10)
		ket_qua = chon_o_xuat(KHO, item, None, 7)
		self.assertEqual(ket_qua, [{"o": a, "so_luong": 3}, {"o": b, "so_luong": 4}])

	def test_bo_qua_o_het_hang(self):
		item = _dam_bao_item("_Test FEFO BoQuaHet")
		het, con = _o("9Z03010101", thu_tu=1), _o("9Z04010101", thu_tu=2)
		_dat(het, item, None, 5)
		_dat(het, item, None, -5)
		_dat(con, item, None, 6)
		ket_qua = chon_o_xuat(KHO, item, None, 2)
		self.assertEqual(ket_qua, [{"o": con, "so_luong": 2}])


class TestChonTheoHanDung(FrappeTestCase):
	# Cùng lý do isolation như trên: hai bài dưới đây dùng mặt hàng RIÊNG vì
	# cùng lớp (rollback theo lớp) — nếu dùng chung, lô "_T-FEFO-SOM" (hạn
	# 2026-10-01) của bài han_gan_nhat vẫn còn tồn khi bài khong_han chạy và
	# có hạn gần hơn cả lô "co_han" của bài đó, làm sai lệch kết quả.
	def test_han_gan_nhat_di_truoc(self):
		item = _dam_bao_item("_Test FEFO HanGanNhat")
		som, muon = _o("9Z96010101", thu_tu=9), _o("9Z06010101", thu_tu=1)
		l_som, l_muon = _lo("_T-FEFO-SOM", item, "2026-10-01"), _lo("_T-FEFO-MUON", item, "2027-10-01")
		_dat(som, item, l_som, 5)
		_dat(muon, item, l_muon, 5)
		# gọi không chỉ định lô
		ket_qua = chon_o_xuat(KHO, item, None, 3)
		self.assertEqual(ket_qua[0]["o"], som, "lô hạn gần hơn phải đi trước dù đường đi xa hơn")

	def test_lo_khong_han_xep_sau_cung(self):
		# Tự soát thêm (vòng sửa 2): hai ô ở đây có CÙNG thu_tu_lay_hang=1
		# (cố ý, để phép so sánh chỉ còn phụ thuộc hạn dùng), nên nếu khoá
		# sort hạn dùng (`ifnull(b.expiry_date, %(han_xa)s) asc`) bị XOÁ HẲN
		# khỏi SQL, tie-break rơi thẳng xuống `lb.o asc`. Tên cũ "CH" < "KH"
		# tình cờ khớp luôn thứ tự ưu tiên (co_han trước) — CÙNG HỌ lỗi với
		# Important 1, chỉ khác khoá sort. Đổi tên ngược alphabet: ô có hạn
		# (ưu tiên, đi trước) đặt tên xếp SAU, ô không hạn (đi sau) đặt tên
		# xếp TRƯỚC. Đã đo thật: xoá khoá sort hạn dùng, bài NÀY đỏ.
		item = _dam_bao_item("_Test FEFO KhongHan")
		co_han, khong_han = _o("9Z95010101", thu_tu=1), _o("9Z07010101", thu_tu=1)
		l_han = _lo("_T-FEFO-CO-HAN", item, "2027-01-01")
		l_khong = _lo("_T-FEFO-KHONG-HAN", item, None)
		_dat(co_han, item, l_han, 5)
		_dat(khong_han, item, l_khong, 5)
		ket_qua = chon_o_xuat(KHO, item, None, 3)
		self.assertEqual(ket_qua[0]["o"], co_han, "lô không hạn phải xếp sau — xem docstring")


class TestChonDungLoDuocChiDinh(FrappeTestCase):
	def setUp(self):
		self.item = _dam_bao_item("_Test FEFO ChiDinhLo")

	def test_chi_dinh_lo_thi_khong_dung_lo_khac(self):
		item = self.item
		a, b = _o("9Z08010101", thu_tu=1), _o("9Z09010101", thu_tu=2)
		l1, l2 = _lo("_T-FEFO-L1", item, "2026-11-01"), _lo("_T-FEFO-L2", item, "2026-12-01")
		_dat(a, item, l1, 5)
		_dat(b, item, l2, 5)
		ket_qua = chon_o_xuat(KHO, item, l2, 4)
		self.assertEqual(ket_qua, [{"o": b, "so_luong": 4}])


class TestSoLuongLe(FrappeTestCase):
	"""Bổ sung NGOÀI brief (review điều phối, model mạnh hơn): mọi số lượng
	trong 7 bài gốc của brief đều là số NGUYÊN, không lộ được sai số nhị
	phân khi trừ dần `can` qua nhiều ứng viên. Với số lẻ, ví dụ hai ô tồn
	0.7 và 0.1, xuất 0.8: `0.8 - 0.7 = 0.10000000000000009`, `min(0.1,
	đó) = 0.1`, `can` còn lại ~9e-17 thay vì đúng 0 — nếu không làm tròn,
	`can > 0` sai lệch sẽ `frappe.throw` một phiếu xuất HOÀN TOÀN hợp lệ
	ngay trên đường hook bình thường (vi phạm thẳng điều bắt buộc #2).
	`chon_o_xuat` đã sửa để làm tròn `can` về 6 chữ số thập phân sau mỗi lần
	trừ (khớp `_DO_CHINH_XAC_SO_LUONG` của `vitri/lo.py`) — bài này khoá
	đúng sửa đó."""

	def test_hai_o_le_cong_du_khong_bao_thieu(self):
		# Tên ô ngược alphabet so với thu_tu_lay_hang (vòng sửa 2), cùng lý
		# do các bài trên: ô lấy trước (thu_tu=1) đặt tên xếp SAU alphabet.
		item = _dam_bao_item("_Test FEFO SoLe")
		nhieu, it = _o("9Z94010101", thu_tu=1), _o("9Z12010101", thu_tu=2)
		_dat(nhieu, item, None, 0.7)
		_dat(it, item, None, 0.1)
		ket_qua = chon_o_xuat(KHO, item, None, 0.8)
		self.assertEqual(ket_qua, [{"o": nhieu, "so_luong": 0.7}, {"o": it, "so_luong": 0.1}])


class TestKhongDuTon(FrappeTestCase):
	def setUp(self):
		# Giữ nguyên "_Test FEFO Item" (không tách riêng như các lớp trên):
		# đây là item DUY NHẤT được assertIn() khẳng định xuất hiện nguyên
		# văn trong thông báo lỗi; lớp chỉ có một bài nên không có rủi ro
		# lẫn dữ liệu giữa các bài cùng lớp.
		_dam_bao_item()

	def test_bao_loi_tieng_viet_neu_ro_thieu_bao_nhieu(self):
		o = _o("9Z13010101", thu_tu=1)
		_dat(o, "_Test FEFO Item", None, 2)
		with self.assertRaises(frappe.ValidationError) as ctx:
			chon_o_xuat(KHO, "_Test FEFO Item", None, 10)
		loi = str(ctx.exception)
		self.assertIn("_Test FEFO Item", loi)
		self.assertIn("thiếu", loi.lower())
		self.assertNotIn("Traceback", loi)


class TestThieuViONgungDung(FrappeTestCase):
	"""Bổ sung NGOÀI brief — Important 2 (vòng sửa 2, review điều phối).

	`chon_o_xuat` loại ô `disabled` khỏi ứng viên (ĐÚNG — điều phối chốt: ô
	ngừng dùng không được lấy hàng, hàng ở đó phải chuyển đi bằng phiếu
	chuyển ô của giai đoạn 4 trước đã), nhưng `tong_ton_vi_tri` (dùng để
	kiểm bất biến §3) KHÔNG lọc `disabled` nên vẫn cộng cả ô đó vào tổng —
	Bin/§3 "đủ hàng" trong khi hook vẫn throw "không đủ hàng" là đúng, nhưng
	nói "không đủ hàng" suông thì người vận hành đi tìm sai chỗ. Bài này
	khoá: khi phần thiếu đúng bằng phần đang kẹt ở ô ngừng dùng, thông báo
	phải nêu RÕ đó không phải thiếu hàng thật, nêu ô nào, còn bao nhiêu, và
	việc cần làm — không phải câu "không đủ hàng" chung chung của
	`TestKhongDuTon`."""

	def test_thong_bao_neu_ro_o_ngung_dung_khong_phai_thieu_hang_that(self):
		item = _dam_bao_item("_Test FEFO NgungDung")
		dang_dung = _o("9Z14010101", thu_tu=1)
		ngung_dung = _o("9Z15010101", thu_tu=2)
		_dat(dang_dung, item, None, 2)
		_dat(ngung_dung, item, None, 5)
		frappe.db.set_value("Storage Location", ngung_dung, "disabled", 1)

		with self.assertRaises(frappe.ValidationError) as ctx:
			chon_o_xuat(KHO, item, None, 6)
		loi = str(ctx.exception)
		self.assertIn(ngung_dung, loi, "phải nêu đích danh ô đang giữ phần thiếu")
		self.assertIn("ngừng dùng", loi.lower(), "phải nói rõ đây là hàng kẹt ở ô ngừng dùng")
		self.assertNotIn("Traceback", loi)

	def test_thieu_hang_that_van_bao_nhu_cu_neu_khong_o_nao_ngung_dung(self):
		"""Đối chứng: không có ô disabled nào giữ hàng thì vẫn phải là câu
		"không đủ hàng" thông thường — không được lúc nào cũng đổi sang câu
		mới chỉ vì CÓ ô disabled tồn tại trong kho (kể cả khi nó rỗng)."""
		item = _dam_bao_item("_Test FEFO NgungDungRong")
		dang_dung = _o("9Z16010101", thu_tu=1)
		ngung_dung_rong = _o("9Z17010101", thu_tu=2)
		_dat(dang_dung, item, None, 2)
		frappe.db.set_value("Storage Location", ngung_dung_rong, "disabled", 1)

		with self.assertRaises(frappe.ValidationError) as ctx:
			chon_o_xuat(KHO, item, None, 6)
		loi = str(ctx.exception)
		self.assertNotIn("ngừng dùng", loi.lower())
		self.assertIn("thiếu", loi.lower())


class TestXuatQuaHookThatVaBatBien(FrappeTestCase):
	"""Bổ sung NGOÀI brief — điều bắt buộc #3 của điều phối (bất biến §3
	phải đúng sau mỗi thao tác, khoá bằng test đọc tồn kho ERPNext từ
	NGUỒN ĐỘC LẬP, không tính lại từ sổ vị trí).

	Các bài ở trên gọi thẳng chon_o_xuat() với Location Balance tự seed —
	không đi qua Stock Ledger Entry.on_submit thật, nên không chứng minh
	nhánh xuất vừa nối vào hook_sle.py (_ghi_mot_phan) THẬT SỰ chạy trên
	chứng từ thật, và test_hook_nhap.py hiện chỉ có một ô CHUA-XEP giữ
	toàn bộ tồn (không có ô thứ hai để phân biệt thứ tự lấy hàng), nên
	không khoá được trường hợp hook phải CHỌN giữa nhiều ô.

	Kịch bản: nhập 12 vào CHUA-XEP qua Stock Entry thật (nhánh nhập, đã
	khoá ở test_hook_nhap.py). "San hàng" sang hai ô thật bằng cách ghi
	thẳng sổ vị trí — chỉ để SEED dữ liệu test (mô phỏng xếp vị trí thủ
	công; Location Allocation thật là GĐ 2, ngoài phạm vi Task 8), tổng
	không đổi nên không tự vi phạm bất biến. Rồi xuất hai lần qua Stock
	Entry thật KHÔNG khai vị trí — hook phải tự gọi chon_o_xuat().

	SỬA 10/09/2026: bản trước khẳng định ô CHUA-XEP bị rút TRƯỚC, vì nó tự
	`insert()` ô hệ thống và bỏ trống `thu_tu_lay_hang` (nhận mặc định 0).
	Production đặt 9999 — ô "Chưa xếp" được lấy SAU CÙNG. Bài xanh suốt
	nhiều tháng trên một thế giới production không bao giờ sinh ra; chỉ lộ
	khi `Kho Miyano - MYN` được bật thật. Nay setUp gọi
	`bat_kho.tao_o_chua_xep()` nên không lệch lại được.

	Đối chiếu bằng Bin của ERPNext — nguồn độc lập, không qua bất kỳ hàm
	nào của vitri/ — tránh đúng bẫy "bài test tự chứng minh mình" đã xảy ra
	hai lần trong dự án (xem yêu cầu điều phối)."""

	def setUp(self):
		# Gọi ĐÚNG hàm production. Bản trước tự `insert()` một ô la_o_chua_xep=1
		# và bỏ trống `thu_tu_lay_hang` → nhận mặc định 0, trong khi production
		# đặt 9999. Bài này khoá thứ tự lấy hàng, nên chênh đó làm nó khoá NGƯỢC
		# hành vi thật suốt nhiều tháng mà vẫn xanh.
		tao_o_chua_xep(KHO)
		# Lưu lại giá trị THẬT rồi trả về đúng nó ở tearDown. Bản trước ghi cứng
		# 0, nên khi kho thật đã bật (10/09/2026) bài này tắt kho của người ta.
		self._co_cu = frappe.db.get_value("Warehouse", KHO, "custom_quan_ly_vi_tri")
		frappe.db.set_value("Warehouse", KHO, "custom_quan_ly_vi_tri", 1)
		vk.xoa_cache_kho(KHO)

	def tearDown(self):
		frappe.db.set_value("Warehouse", KHO, "custom_quan_ly_vi_tri", self._co_cu)
		vk.xoa_cache_kho(KHO)

	def test_xuat_khong_khai_vi_tri_chon_dung_o_va_khop_bin(self):
		item = "_Test FEFO Hook Xuat"
		if not frappe.db.exists("Item", item):
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": item,
					"item_name": item,
					"item_group": "All Item Groups",
					"stock_uom": "Nos",
					"is_stock_item": 1,
				}
			).insert(ignore_permissions=True)

		nhap = frappe.get_doc(
			{
				"doctype": "Stock Entry",
				"stock_entry_type": "Material Receipt",
				"company": "Miyano Việt Nam",
				"items": [{"item_code": item, "qty": 12, "t_warehouse": KHO, "basic_rate": 1000}],
			}
		)
		nhap.insert(ignore_permissions=True)
		nhap.submit()

		o_chua_xep = vk.o_chua_xep(KHO)
		self.assertEqual(so.ton_o(o_chua_xep, item, None), 12, "tiền đề: hàng nhập nằm cả ở CHUA-XEP")

		# Hai ô THẬT có tên và ưu tiên NGƯỢC nhau: `...0101` đứng trước theo
		# alphabet nhưng ưu tiên thấp hơn (5 > 1). Nhờ vậy nếu ai xoá khoá sort
		# `thu_tu_lay_hang` khỏi SQL, tie-break rơi về tên ô và bài này ĐỎ.
		#
		# Bản trước dựng thế nghịch đảo đó giữa ô GAN và ô hệ thống, dựa vào
		# việc ô hệ thống có thu_tu=0. Không dùng lại được: ô hệ thống thật là
		# 9999, mà mọi mã ô hợp lệ đều mở đầu bằng một CHỮ SỐ (cấp Khu:
		# `[0-9][A-Z]`, xem `ma_vi_tri.py::_KHU`) nên luôn xếp TRƯỚC "ZZZ-..."
		# (chữ cái, mã ASCII lớn hơn chữ số) — tên và ưu tiên của ô hệ thống
		# giờ LUÔN đồng thuận, không tạo được mâu thuẫn với nó nữa. Phải lấy
		# hai ô thật.
		xa = _o("9Z18010101", thu_tu=5)
		gan = _o("9Z18010102", thu_tu=1)

		# San hàng từ CHUA-XEP sang hai ô thật — CHỈ để seed dữ liệu test (mô
		# phỏng xếp vị trí thủ công), không phải logic sản phẩm của Task 8;
		# tổng không đổi nên Bin không bị ảnh hưởng.
		def _san(den, sl):
			for o_, q in ((o_chua_xep, -sl), (den, sl)):
				so.ghi_dong_so(
					o=o_,
					kho=KHO,
					vat_tu=item,
					so_lo=None,
					so_luong=q,
					chung_tu_type="Storage Location",
					chung_tu=den,
					chung_tu_row="seed",
					sle=None,
					ngay="2026-09-01",
					thoi_diem="2026-09-01 09:00:00",
					company="Miyano Việt Nam",
				)

		_san(gan, 5)
		_san(xa, 4)
		self.assertEqual(so.ton_o(o_chua_xep, item, None), 3)
		self.assertEqual(so.ton_o(gan, item, None), 5)
		self.assertEqual(so.ton_o(xa, item, None), 4)

		def _xuat(sl):
			ct = frappe.get_doc(
				{
					"doctype": "Stock Entry",
					"stock_entry_type": "Material Issue",
					"company": "Miyano Việt Nam",
					"items": [{"item_code": item, "qty": sl, "s_warehouse": KHO, "basic_rate": 1000}],
				}
			)
			ct.insert(ignore_permissions=True)
			ct.submit()

		# LẦN 1 — xuất 7, trong khi hai ô thật đang có 9. Khoá HAI điều:
		#  (a) GAN đi trước XA dù tên XA xếp trước theo alphabet → khoá khoá
		#      sort `thu_tu_lay_hang`;
		#  (b) CHUA-XEP KHÔNG bị đụng tới chừng nào ô thật còn hàng → khoá
		#      thu_tu=9999 của ô hệ thống. Nếu ô hệ thống là 0 như bản test
		#      cũ tự dựng, nó đã bị rút sạch ở đây.
		_xuat(7)
		self.assertEqual(so.ton_o(gan, item, None), 0, "GAN (thu_tu=1) phải bị rút hết trước")
		self.assertEqual(so.ton_o(xa, item, None), 2, "XA (thu_tu=5) chỉ bị rút phần còn thiếu")
		self.assertEqual(
			so.ton_o(o_chua_xep, item, None),
			3,
			"ô 'Chưa xếp' (thu_tu=9999) phải được để yên khi ô thật còn hàng",
		)

		# LẦN 2 — xuất 4, ô thật chỉ còn 2. Khoá chiều còn lại: ô hệ thống
		# VẪN được lấy khi ô thật đã cạn (nó giữ hàng thật, không phải kho ảo).
		_xuat(4)
		self.assertEqual(so.ton_o(xa, item, None), 0)
		self.assertEqual(so.ton_o(o_chua_xep, item, None), 1, "cạn ô thật rồi mới tới 'Chưa xếp'")

		bin_qty = frappe.db.get_value("Bin", {"item_code": item, "warehouse": KHO}, "actual_qty")
		self.assertEqual(flt(bin_qty), 1, "tiền đề: ERPNext (nguồn độc lập) đã trừ tồn kho về 1")
		self.assertEqual(
			so.tong_ton_vi_tri(KHO, item, None),
			flt(bin_qty),
			"bất biến §3: tổng tồn các ô phải khớp Bin (nguồn độc lập), không "
			"được tính lại từ chính sổ vị trí",
		)

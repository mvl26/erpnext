"""Tắt và đồng bộ lại.

Cái bẫy chắc chắn có người dẫm vào nếu không chặn bằng máy: tắt quản lý vị
trí, kho vẫn xuất nhập bình thường (hook bỏ qua), rồi bật lại — tồn vị trí
đứng yên trong khi tồn kho đã đi tiếp. Vì vậy KHÔNG cho bật thẳng lại từ
"Đã tắt"; phải qua Đồng bộ lại.

Đồng bộ lại ghi bút toán BÙ vào CHUA-XEP, không sửa và không xoá dòng cũ —
sổ vẫn chỉ ghi thêm.

GHI ĐÈ so với brief gốc (điều phối, Task 13): brief KHÔNG có bài kiểm quyền
cho `tat()`/`dong_bo_lai()` và bản nháp trong brief KHÔNG gọi
`_kiem_tra_quyen()`. Cả hai hàm này GHI dữ liệu (đổi cờ Warehouse, đổi
trạng thái, và với `dong_bo_lai` còn ghi thêm dòng sổ) — cùng lý do đã áp
dụng cho `bat()` ở Task 12: site có 10 tài khoản `Website User` (khách
cổng `miyano_portal`) đang hoạt động, thiếu kiểm quyền nghĩa là một tài
khoản khách tắt/đồng bộ được kho nội bộ. Thêm `TestTatQuyen` và
`TestDongBoLaiQuyen`, gọi `_kiem_tra_quyen()` ở dòng đầu mỗi hàm.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.vi_tri_kho.tests.kho_thu import dam_bao_kho_thu
from erpnext.vi_tri_kho.tests.test_bat_kho import _don_sach
from erpnext.vi_tri_kho.tests.test_hook_nhap import _tao_item
from erpnext.vi_tri_kho.vitri import kho as vk
from erpnext.vi_tri_kho.vitri import so
from erpnext.vi_tri_kho.vitri.bat_kho import bat, dong_bo_lai, tat
from erpnext.vi_tri_kho.vitri.doi_soat import doi_soat_kho

# Kho THỬ — cùng lý do như `test_bat_kho.py`: nhóm bài này gọi `_don_sach()`,
# `tat()` và `dong_bo_lai()` trên toàn bộ trạng thái chuyển đổi của kho.
KHO = "_Test Kho Chuyen Doi - MYN"
WEBSITE_USER = "bvminhduc@demo.miyano"


def _nhap(item, qty):
	se = frappe.get_doc(
		{
			"doctype": "Stock Entry",
			"stock_entry_type": "Material Receipt",
			"company": "Miyano Việt Nam",
			"items": [{"item_code": item, "qty": qty, "t_warehouse": KHO, "basic_rate": 1000}],
		}
	)
	se.insert(ignore_permissions=True)
	se.submit()
	return se


class TestTat(FrappeTestCase):
	def setUp(self):
		dam_bao_kho_thu()
		_don_sach(KHO)
		bat(KHO)

	def tearDown(self):
		_don_sach(KHO)

	def test_tat_thi_hook_ngung_ghi(self):
		tat(KHO)
		item = _tao_item("_Test Tat Hook")
		truoc = frappe.db.count("Location Ledger Entry", {"kho": KHO})
		_nhap(item, 5)
		self.assertEqual(frappe.db.count("Location Ledger Entry", {"kho": KHO}), truoc)

	def test_doi_chung_hook_van_ghi_khi_dang_bat(self):
		"""Kiểm chứng dương cho bài trên: KHÔNG gọi `tat()`, cùng thao tác
		nhập vào cùng kho (đang "Đang bật" từ `setUp`) PHẢI ghi thêm dòng
		sổ. Thiếu bài này, `test_tat_thi_hook_ngung_ghi` không loại trừ
		được khả năng `_nhap` không ghi gì cả trong fixture này (ví dụ do
		lỗi dựng item/kho), khiến "không đổi" đúng vì lý do sai.
		"""
		item = _tao_item("_Test Tat Hook Doi Chung")
		truoc = frappe.db.count("Location Ledger Entry", {"kho": KHO})
		_nhap(item, 5)
		self.assertGreater(
			frappe.db.count("Location Ledger Entry", {"kho": KHO}),
			truoc,
			"kho đang bật thì nhập hàng phải ghi thêm dòng sổ",
		)

	def test_tat_khong_xoa_so_cu(self):
		truoc = frappe.db.count("Location Ledger Entry", {"kho": KHO})
		self.assertGreater(truoc, 0)
		tat(KHO)
		self.assertEqual(frappe.db.count("Location Ledger Entry", {"kho": KHO}), truoc)

	def test_trang_thai_thanh_da_tat(self):
		tat(KHO)
		self.assertEqual(frappe.db.get_value("Warehouse Location Setup", KHO, "trang_thai"), "Đã tắt")


class TestChanBatThangLai(FrappeTestCase):
	def setUp(self):
		dam_bao_kho_thu()
		_don_sach(KHO)
		bat(KHO)

	def tearDown(self):
		_don_sach(KHO)

	def test_bat_lai_sau_khi_tat_bi_chan(self):
		tat(KHO)
		with self.assertRaises(frappe.ValidationError) as ctx:
			bat(KHO)
		self.assertIn("đồng bộ lại", str(ctx.exception).lower())


class TestDongBoLai(FrappeTestCase):
	def setUp(self):
		dam_bao_kho_thu()
		_don_sach(KHO)
		bat(KHO)
		self.item = _tao_item("_Test Dong Bo")

	def tearDown(self):
		_don_sach(KHO)

	def test_bu_phan_lech_vao_o_chua_xep(self):
		tat(KHO)
		_nhap(self.item, 9)  # hook bỏ qua vì đã tắt
		self.assertFalse(doi_soat_kho(KHO)["khop"])

		kq = dong_bo_lai(KHO)

		self.assertTrue(kq["doi_soat"]["khop"], "đồng bộ xong phải khớp")
		o = vk.o_chua_xep(KHO)
		self.assertEqual(so.ton_o(o, self.item, None), 9)

	def test_dong_bo_khong_xoa_dong_cu(self):
		tat(KHO)
		_nhap(self.item, 4)
		truoc = frappe.db.count("Location Ledger Entry", {"kho": KHO})
		dong_bo_lai(KHO)
		self.assertGreater(
			frappe.db.count("Location Ledger Entry", {"kho": KHO}),
			truoc,
			"đồng bộ phải GHI THÊM bút toán bù, không sửa dòng cũ",
		)

	def test_dong_bo_reset_ngay_tat_va_cap_nhat_thong_tin(self):
		"""Việc (A) (review điều phối, sau khi 147/147 bài "xong"): trước sửa,
		`dong_bo_lai()` chuyển `trang_thai` "Đã tắt" -> "Đang bật" nhưng KHÔNG
		reset `ngay_tat`, KHÔNG cập nhật `ngay_bat`/`so_dong_chuyen_doi` —
		màn hình Warehouse Location Setup (điểm điều khiển DUY NHẤT) sẽ hiện
		"Đang bật" cạnh một NGÀY TẮT CŨ và SỐ DÒNG của lần BẬT ĐẦU TIÊN,
		không phải của lần đồng bộ vừa chạy."""
		item = _tao_item("_Test Dong Bo Reset")
		tat(KHO)
		ngay_tat_truoc = frappe.db.get_value("Warehouse Location Setup", KHO, "ngay_tat")
		self.assertTrue(ngay_tat_truoc, "tiền đề: tat() đã ghi ngay_tat")

		_nhap(item, 4)
		dong_bo_lai(KHO)

		st = frappe.get_doc("Warehouse Location Setup", KHO)
		self.assertIsNone(st.ngay_tat, "đồng bộ lại xong (đang bật) phải xoá ngày tắt cũ")
		self.assertTrue(st.ngay_bat, "phải cập nhật ngày bật LẠI")
		self.assertGreaterEqual(
			st.ngay_bat,
			ngay_tat_truoc,
			"ngày bật lại phải không sớm hơn ngày tắt trước đó",
		)
		self.assertEqual(
			st.so_dong_chuyen_doi,
			1,
			"phải phản ánh số dòng bù CỦA LẦN đồng bộ này (1 mặt hàng lệch), không phải "
			"số dòng chuyển đổi của lần bật ĐẦU TIÊN",
		)

	def test_dong_bo_xong_thi_bat_lai_duoc(self):
		tat(KHO)
		_nhap(self.item, 4)
		dong_bo_lai(KHO)
		self.assertEqual(frappe.db.get_value("Warehouse Location Setup", KHO, "trang_thai"), "Đang bật")
		self.assertTrue(vk.kho_co_quan_ly_vi_tri(KHO))


class TestDongBoLaiChuaTungBat(FrappeTestCase):
	"""Bổ sung sau review advisor (sau khi 9 bài đầu đã xanh).

	`dong_bo_lai()` gọi `_kiem_tra_kho(kho, cho_phep_da_bat=True)`, cố ý bỏ
	qua kiểm tra `trang_thai` để cho phép chạy trên kho "Đã tắt" (bật lại)
	hoặc "Đang bật" (đối soát lệch) — đúng brief. Nhưng điều đó cũng vô
	tình cho phép chạy trên một kho CHƯA TỪNG bật (không có bản ghi
	`Warehouse Location Setup`). Đo thật qua console TRƯỚC khi thêm
	`_kiem_tra_da_tung_bat`: `ghi_dong_so` (dòng bù đầu tiên) ném thẳng
	`LinkValidationError: Could not find Chứng từ: Kho Miyano - MYN` —
	traceback thô lộ ra qua RPC, vi phạm ràng buộc toàn cục "thông báo lỗi
	tiếng Việt, không lộ traceback". Đúng cái bẫy mà docstring `bat()`
	(Task 12) đã cảnh báo trước cho Task 13.
	"""

	def setUp(self):
		dam_bao_kho_thu()
		_don_sach(KHO)

	def tearDown(self):
		_don_sach(KHO)

	def test_bi_chan_bang_thong_bao_sach_khong_lo_traceback(self):
		self.assertIsNone(
			frappe.db.get_value("Warehouse Location Setup", KHO, "trang_thai"),
			"tiền đề: kho này chưa từng bật, không có bản ghi setup",
		)
		with self.assertRaises(frappe.ValidationError) as ctx:
			dong_bo_lai(KHO)

		# LinkValidationError LÀ một ValidationError (kế thừa) nên riêng
		# assertRaises ở trên không phân biệt được thông báo sạch của
		# _kiem_tra_da_tung_bat với traceback thô bị lộ ra từ ghi_dong_so.
		# Phải so nội dung thông báo để khoá đúng nhánh mong muốn.
		self.assertNotIsInstance(ctx.exception, frappe.exceptions.LinkValidationError)
		self.assertIn("chưa từng bật", str(ctx.exception).lower())
		self.assertNotIn("chứng từ", str(ctx.exception).lower())

		self.assertEqual(
			frappe.db.count("Location Ledger Entry", {"kho": KHO}),
			0,
			"bị chặn sớm thì không được ghi dòng bù nào",
		)

	def test_bi_chan_ca_khi_co_ban_ghi_setup_mo_coi(self):
		"""VÒNG SỬA 2 (review advisor): bản đầu của `_kiem_tra_da_tung_bat`
		chỉ chặn `trang_thai is None` — DANH SÁCH CẤM, không phải DANH SÁCH
		CHO PHÉP. `Warehouse Location Setup` cho phép `create` qua UI/Data
		Import; `trang_thai` mặc định `"Chưa bật"` (field `read_only` trên
		form không chặn được Data Import hay tạo tay). Một bản ghi MỒ CÔI
		như vậy (tồn tại nhưng `trang_thai="Chưa bật"`, chưa từng qua
		`bat()`) lọt qua bản kiểm tra cũ — ĐỦ để Dynamic Link của
		`ghi_dong_so` không còn ném lỗi, `dong_bo_lai()` chạy trọn thành
		một `bat()` cửa sau (không savepoint, không `dung_lai_ton_vi_tri`).
		Test này dựng đúng bản ghi mồ côi đó (không qua `bat()`) rồi khẳng
		định vẫn bị chặn sạch — khoá đúng lỗ hổng mà bài trên (dùng tiền đề
		"không có bản ghi nào") không chạm tới.
		"""
		frappe.get_doc({"doctype": "Warehouse Location Setup", "kho": KHO}).insert(ignore_permissions=True)
		self.assertEqual(
			frappe.db.get_value("Warehouse Location Setup", KHO, "trang_thai"),
			"Chưa bật",
			"tiền đề: bản ghi mồ côi mang đúng giá trị mặc định của field",
		)

		with self.assertRaises(frappe.ValidationError) as ctx:
			dong_bo_lai(KHO)

		self.assertNotIsInstance(ctx.exception, frappe.exceptions.LinkValidationError)
		self.assertIn("chưa từng bật", str(ctx.exception).lower())
		self.assertFalse(
			vk.kho_co_quan_ly_vi_tri(KHO),
			"bị chặn thì cờ quản lý vị trí không được bật",
		)
		self.assertEqual(
			frappe.db.count("Location Ledger Entry", {"kho": KHO}),
			0,
			"bị chặn sớm thì không được đổ tồn vào CHUA-XEP như bù trừ",
		)


class TestTatQuyen(FrappeTestCase):
	"""`tat()` GHI dữ liệu (đổi cờ Warehouse, đổi trạng thái) — kiểm quyền
	quan trọng như ở `bat()`. Site có tài khoản `Website User` thật.
	"""

	def setUp(self):
		dam_bao_kho_thu()
		_don_sach(KHO)
		bat(KHO)

	def tearDown(self):
		_don_sach(KHO)

	def test_website_user_bi_chan(self):
		self.assertTrue(
			frappe.db.exists("User", WEBSITE_USER),
			"Cần tài khoản Website User thật trên site để bài này có ý nghĩa.",
		)
		truoc = frappe.db.count("Location Ledger Entry", {"kho": KHO})
		frappe.set_user(WEBSITE_USER)
		try:
			with self.assertRaises(frappe.PermissionError):
				tat(KHO)
		finally:
			frappe.set_user("Administrator")

		self.assertTrue(vk.kho_co_quan_ly_vi_tri(KHO), "bị chặn quyền thì cờ phải vẫn bật")
		self.assertEqual(
			frappe.db.get_value("Warehouse Location Setup", KHO, "trang_thai"),
			"Đang bật",
			"bị chặn quyền thì trạng thái không được đổi",
		)
		self.assertEqual(
			frappe.db.count("Location Ledger Entry", {"kho": KHO}),
			truoc,
			"bị chặn quyền thì không được ghi/xoá dòng sổ nào",
		)


class TestDongBoLaiQuyen(FrappeTestCase):
	"""`dong_bo_lai()` GHI dữ liệu (dòng sổ bù, đổi cờ, đổi trạng thái) —
	kiểm quyền như `tat()`/`bat()`.
	"""

	def setUp(self):
		dam_bao_kho_thu()
		_don_sach(KHO)
		bat(KHO)
		tat(KHO)

	def tearDown(self):
		_don_sach(KHO)

	def test_website_user_bi_chan(self):
		self.assertTrue(
			frappe.db.exists("User", WEBSITE_USER),
			"Cần tài khoản Website User thật trên site để bài này có ý nghĩa.",
		)
		truoc = frappe.db.count("Location Ledger Entry", {"kho": KHO})
		frappe.set_user(WEBSITE_USER)
		try:
			with self.assertRaises(frappe.PermissionError):
				dong_bo_lai(KHO)
		finally:
			frappe.set_user("Administrator")

		self.assertEqual(
			frappe.db.get_value("Warehouse Location Setup", KHO, "trang_thai"),
			"Đã tắt",
			"bị chặn quyền thì trạng thái không được đổi",
		)
		self.assertFalse(
			vk.kho_co_quan_ly_vi_tri(KHO),
			"bị chặn quyền thì cờ không được bật lại",
		)
		self.assertEqual(
			frappe.db.count("Location Ledger Entry", {"kho": KHO}),
			truoc,
			"bị chặn quyền thì không được ghi bút toán bù nào",
		)


class TestDongBoLaiOAmKhongTuSua(FrappeTestCase):
	"""CRITICAL 1b (review điều phối, sau khi 147/147 bài "xong") — quyết
	định CÓ Ý THỨC ghi ở docstring `dong_bo_lai()`: bút toán bù CHỈ sửa được
	`dong_lech` (chênh TỔNG), KHÔNG sửa được `o_am`/`lech_bo_dem`. Kịch bản:
	một ô đã âm SẴN (không liên quan gì tới việc tắt/bật đang thử), cộng
	thêm một chênh dong_lech thật do tắt kho (bù được). `dong_bo_lai()` phải
	bù ĐÚNG phần dong_lech nhưng vẫn THẤT BẠI vì ô âm còn nguyên — không được
	báo "khớp" giả."""

	def setUp(self):
		dam_bao_kho_thu()
		_don_sach(KHO)
		bat(KHO)
		self.item_am = _tao_item("_Test DongBo OAm")
		self.item_lech = _tao_item("_Test DongBo OAm Lech")

	def tearDown(self):
		_don_sach(KHO)

	def test_o_am_lam_dong_bo_lai_that_bai_ro_rang(self):
		_nhap(self.item_am, 10)
		o_chua_xep = vk.o_chua_xep(KHO)

		o_gan = "9Z47010101"
		if not frappe.db.exists("Storage Location", o_gan):
			frappe.get_doc(
				{
					"doctype": "Storage Location",
					"ma_o": o_gan,
					"kho": KHO,
				}
			).insert(ignore_permissions=True)
		# San CHUA-XEP xuống -3, o_gan bù +13 — TỔNG (dong_lech) vẫn khớp,
		# chỉ o_am mới thấy — mô phỏng hư hỏng dữ liệu KHÔNG do lần tắt/đồng
		# bộ đang thử gây ra.
		frappe.db.sql(
			"update `tabLocation Balance` set so_luong = so_luong - 13 where o=%s and vat_tu=%s",
			(o_chua_xep, self.item_am),
		)
		frappe.get_doc(
			{
				"doctype": "Location Balance",
				"o": o_gan,
				"kho": KHO,
				"vat_tu": self.item_am,
				"so_lo": "",
				"so_luong": 13,
			}
		).insert(ignore_permissions=True)
		self.assertTrue(
			[d for d in doi_soat_kho(KHO)["o_am"] if d["vat_tu"] == self.item_am],
			"tiền đề: đã có ô âm",
		)

		tat(KHO)
		_nhap(self.item_lech, 4)  # nhập lúc đã tắt -> hook bỏ qua -> dong_lech thật

		with self.assertRaises(frappe.ValidationError) as ctx:
			dong_bo_lai(KHO)

		thong_bao = str(ctx.exception).lower()
		self.assertIn(
			"âm",
			thong_bao,
			f"thông báo phải nêu rõ vấn đề là Ô ÂM, không phải câu chung chung: {ctx.exception}",
		)
		self.assertNotIn(
			"0 dòng lệch",
			thong_bao,
			"không được đọc như thể không có gì lệch trong khi RPC vừa throw thật",
		)
		self.assertEqual(
			frappe.db.get_value("Warehouse Location Setup", KHO, "trang_thai"),
			"Đã tắt",
			"thất bại thì trạng thái không được đổi thành Đang bật",
		)
		self.assertFalse(
			vk.kho_co_quan_ly_vi_tri(KHO),
			"thất bại thì cờ không được bật lại",
		)

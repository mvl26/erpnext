"""Bật quản lý vị trí — được ăn cả ngã về không.

Không có trạng thái "bật được một nửa". Một kho bật dở dang thì mọi con số
sau đó vô nghĩa mà vẫn TRÔNG NHƯ đang chạy — đó là lý do bài
test_bat_that_bai_khong_de_lai_dau_vet quan trọng ngang bài đường thuận.

GHI ĐÈ so với brief gốc (điều phối, Task 12): brief KHÔNG có bài kiểm
quyền và bản nháp `bat()` trong brief KHÔNG gọi `_kiem_tra_quyen()` —
trong khi Task 11 đã xác lập `xem_truoc` (chỉ ĐỌC) phải kiểm quyền vì site
có 10 tài khoản `Website User` thật. `bat()` còn nguy hiểm hơn: nó GHI
(tạo ô, ghi sổ, đổi cờ `Warehouse`) — thiếu kiểm quyền nghĩa là một tài
khoản cổng `miyano_portal` bật được quản lý vị trí cho kho nội bộ. Thêm
`TestBatQuyen` và gọi `_kiem_tra_quyen()` ở dòng đầu `bat()`.

Cũng thêm `test_tong_theo_mat_hang_khop_bin_truc_tiep`: brief chỉ có
`test_doi_soat_khop_theo_tung_lo` dùng chính `doi_soat_kho` — cùng hàm mà
`bat()` gọi để tự kiểm trước khi commit, nên một mình nó một phần là
tautology (nếu `bat()` và `doi_soat_kho` cùng đọc sai một nguồn, bài đó
không bắt được). Bài mới so trực tiếp `Location Balance` cộng theo mặt
hàng với `Bin.actual_qty` — không đi qua `doi_soat_kho`/`ton_kho_theo_lo`.

VÒNG SỬA 1 (review điều phối, Q3): `test_ghi_mot_dong_cho_moi_lo` ở bản
đầu KHÔNG thật sự khoá chiều lô như tên nó hứa — nó so `len(dong)` với
`kq["so_dong"]`, hai con số cùng dẫn xuất từ MỘT danh sách. Đột biến
`_ton_hien_co` để gộp về (mặt hàng) thay vì (mặt hàng, lô) làm bài đó vẫn
XANH (chỉ `doi_soat_kho` mới đỏ — gián tiếp). Đã sửa: so trực tiếp tập
khoá (mặt hàng, lô) đã ghi với tập khoá của `ton_kho_theo_lo(KHO)` — xem
báo cáo phần "Vòng sửa 1" để có output đỏ thật của đột biến này.
"""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from erpnext.vi_tri_kho.vitri import kho as vk
from erpnext.vi_tri_kho.vitri.bat_kho import bat, xem_truoc
from erpnext.vi_tri_kho.vitri.doi_soat import NGUONG_SAI_SO, doi_soat_kho, ton_kho_theo_lo
from erpnext.vi_tri_kho.tests.kho_thu import dam_bao_kho_thu
from erpnext.vi_tri_kho.tests.test_hook_nhap import _tao_item

# KHO THỬ, không phải `Kho Miyano - MYN`. `_don_sach()` dưới đây xoá thẳng bằng
# SQL toàn bộ sổ vị trí + tồn vị trí + ô hệ thống + hồ sơ chuyển đổi của kho
# rồi tắt cờ — chạy trên kho thật của chủ dự án (đã bật 10/09/2026) là đặt cược
# dữ liệu thật vào việc suite không bao giờ bị giết giữa chừng. Xem `kho_thu.py`.
KHO = "_Test Kho Chuyen Doi - MYN"


def _don_sach(kho):
	frappe.db.sql("delete from `tabLocation Ledger Entry` where kho=%s", (kho,))
	frappe.db.sql("delete from `tabLocation Balance` where kho=%s", (kho,))
	ma = vk.ma_o_chua_xep(kho)
	frappe.db.sql("delete from `tabStorage Location` where name=%s", (ma,))
	frappe.db.set_value("Warehouse", kho, "custom_quan_ly_vi_tri", 0)
	if frappe.db.exists("Warehouse Location Setup", kho):
		frappe.db.sql("delete from `tabWarehouse Location Setup` where name=%s", (kho,))
	vk.xoa_cache_kho(kho)


class TestBatThanhCong(FrappeTestCase):
	def setUp(self):
		dam_bao_kho_thu()
		_don_sach(KHO)

	def tearDown(self):
		_don_sach(KHO)

	def test_tao_o_chua_xep(self):
		bat(KHO)
		o = vk.o_chua_xep(KHO)
		self.assertIsNotNone(o)
		self.assertTrue(frappe.db.get_value("Storage Location", o, "la_o_chua_xep"))

	def test_o_chua_xep_duoc_lay_sau_cung(self):
		"""Ô "Chưa xếp" phải mang `thu_tu_lay_hang = 9999`, tức lấy SAU CÙNG.

		Bài này khoá HẰNG SỐ TRONG MÃ, không phải giá trị đang nằm sẵn trong
		CSDL: `_don_sach()` ở setUp đã xoá ô hệ thống nên `bat()` đi qua đúng
		nhánh TẠO MỚI của `tao_o_chua_xep()`.

		Vì sao đáng một bài riêng: `test_fefo` khoá thứ tự lấy hàng nhưng chạy
		trên ô đã có sẵn (nhánh tái dùng), nên nếu ai sửa 9999 thành 0 trong mã
		thì bài đó vẫn xanh — ô cũ giữ nguyên 9999. Đúng loại lệch mã-với-dữ-liệu
		đã để lọt một bài khoá NGƯỢC hành vi thật suốt nhiều tháng (xem docstring
		`tao_o_chua_xep`).
		"""
		bat(KHO)
		o = vk.o_chua_xep(KHO)
		self.assertEqual(
			frappe.db.get_value("Storage Location", o, "thu_tu_lay_hang"), 9999,
			"ô 'Chưa xếp' không có vị trí trên đường đi trong kho nên phải xếp "
			"cuối hàng đợi lấy hàng, sau mọi ô đã xếp đàng hoàng",
		)

	def test_dat_co_tren_warehouse(self):
		bat(KHO)
		self.assertTrue(vk.kho_co_quan_ly_vi_tri(KHO))

	def test_doi_soat_khop_theo_tung_lo(self):
		bat(KHO)
		kq = doi_soat_kho(KHO)
		self.assertTrue(kq["khop"], f"phải khớp sau khi bật, lệch: {kq['dong_lech'][:5]}")

	def test_ghi_mot_dong_cho_moi_lo(self):
		"""VÒNG SỬA 1 (review điều phối, Q3): bản trước của bài này chỉ so
		`len(dong)` với `kq["so_dong"]` — cả hai đều DẪN XUẤT TỪ CÙNG một
		danh sách `dong` mà `bat()` tự đếm. Đột biến `_ton_hien_co` để gộp
		về (mặt hàng) thay vì (mặt hàng, lô) vẫn làm bài đó XANH, vì hai vế
		so sánh cùng gộp theo cùng một cách — không khoá được chiều lô như
		tên bài hứa.

		Sửa: so trực tiếp TẬP KHOÁ (mặt hàng, lô) đã ghi với tập khoá của
		`ton_kho_theo_lo(KHO)` — nguồn tồn ĐỘC LẬP với bất cứ thứ gì
		`bat()` tự tính ra và trả về.
		"""
		bat(KHO)
		dong = frappe.get_all(
			"Location Ledger Entry", filters={"kho": KHO}, fields=["vat_tu", "so_lo"]
		)
		khoa_da_ghi = {(d.vat_tu, d.so_lo or "") for d in dong}
		self.assertEqual(len(khoa_da_ghi), len(dong), "mỗi (mặt hàng, lô) đúng một dòng")

		khoa_nguon = {
			(vat_tu, so_lo or "")
			for (vat_tu, so_lo), sl in ton_kho_theo_lo(KHO).items()
			if abs(flt(sl)) > NGUONG_SAI_SO
		}
		self.assertEqual(
			khoa_da_ghi, khoa_nguon,
			"tập (mặt hàng, lô) đã ghi phải khớp CHÍNH XÁC nguồn tồn theo lô "
			"(ton_kho_theo_lo) — không chỉ khớp SỐ LƯỢNG dòng với con số bat() tự báo",
		)
		self.assertGreater(
			sum(1 for _, so_lo in khoa_da_ghi if so_lo), 0,
			"kho thử có mặt hàng quản lý lô — phải có ít nhất một dòng mang so_lo thật, "
			"không phải toàn bộ rơi vào ngăn không-lô",
		)

	def test_ghi_nhan_vao_setup(self):
		bat(KHO)
		st = frappe.get_doc("Warehouse Location Setup", KHO)
		self.assertEqual(st.trang_thai, "Đang bật")
		self.assertTrue(st.ngay_bat)
		self.assertEqual(st.o_chua_xep, vk.o_chua_xep(KHO))

	def test_tong_theo_mat_hang_khop_bin_truc_tiep(self):
		"""Góc đo ĐỘC LẬP với `doi_soat_kho`/`ton_kho_theo_lo` — hàm mà
		`bat()` cũng gọi để tự kiểm trước khi commit. So trực tiếp tổng
		`Location Balance` theo mặt hàng với `Bin.actual_qty` (bảng
		ERPNext gốc), không đi qua bất kỳ hàm nào của module `vitri`.
		"""
		bat(KHO)
		tong_vi_tri = frappe.db.sql(
			"""select vat_tu, sum(so_luong) as sl from `tabLocation Balance`
			   where kho=%s group by vat_tu""",
			(KHO,), as_dict=True,
		)
		self.assertGreater(len(tong_vi_tri), 0, "kho thử đã được nạp tồn nên phải có dòng")
		for d in tong_vi_tri:
			ton_bin = frappe.db.get_value(
				"Bin", {"item_code": d.vat_tu, "warehouse": KHO}, "actual_qty"
			)
			self.assertAlmostEqual(
				flt(d.sl), flt(ton_bin), places=4,
				msg=f"{d.vat_tu}: Location Balance {d.sl} != Bin {ton_bin}",
			)

		# Chiều ngược lại: một mặt hàng bị RỚT hoàn toàn (không có dòng
		# Location Balance nào) sẽ không lọt qua vòng lặp trên (không có
		# gì để so) và cũng không bị `test_ghi_mot_dong_cho_moi_lo` bắt
		# trực tiếp. Đếm số mặt hàng ở cả hai phía độc lập để lộ ra mặt
		# hàng bị rớt.
		#
		# VÒNG SỬA 1 (review điều phối, Q4a): dùng CÙNG ngưỡng
		# `NGUONG_SAI_SO` mà đường ống (`_ton_hien_co`, `doi_soat_kho`)
		# dùng — trước đây lọc `actual_qty != 0`, lệch với ngưỡng thật
		# (`abs(sl) > 0.0001`). Một `Bin` mang dư làm tròn kiểu
		# `actual_qty = 0.00005` (không hiếm ở kho dược) sẽ bị đếm là "có
		# tồn" ở vế `!= 0` nhưng KHÔNG được `bat()` chuyển đổi (dưới
		# ngưỡng) — bài đỏ không vì lỗi, mà vì hai vế dùng hai định nghĩa
		# "có tồn" khác nhau.
		so_mat_hang_bin = frappe.db.sql(
			"select count(*) from `tabBin` where warehouse=%s and abs(actual_qty) > %s",
			(KHO, NGUONG_SAI_SO),
		)[0][0]
		self.assertEqual(
			len(tong_vi_tri), so_mat_hang_bin,
			"số mặt hàng có tồn vị trí phải khớp số mặt hàng có tồn (cùng ngưỡng lọc) "
			"trên Bin — lệch nghĩa là có mặt hàng bị rớt khỏi lần chuyển đổi",
		)


class TestBatThatBai(FrappeTestCase):
	def setUp(self):
		dam_bao_kho_thu()
		_don_sach(KHO)

	def tearDown(self):
		_don_sach(KHO)

	def test_bat_that_bai_khong_de_lai_dau_vet(self):
		"""Đối soát cuối cùng lệch → phải quay về đúng như trước khi bấm."""
		with patch(
			"erpnext.vi_tri_kho.vitri.bat_kho.doi_soat_kho",
			return_value={"kho": KHO, "khop": False, "so_dong_lech": 1,
			              "dong_lech": [{"vat_tu": "X", "so_lo": None,
			                             "ton_vi_tri": 1, "ton_kho": 2, "lech": -1}],
			              "o_am": [], "lech_bo_dem": []},
		):
			with self.assertRaises(frappe.ValidationError):
				bat(KHO)

		self.assertIsNone(vk.o_chua_xep(KHO), "ô CHUA-XEP phải biến mất")
		self.assertEqual(frappe.db.count("Location Ledger Entry", {"kho": KHO}), 0)
		self.assertEqual(
			frappe.db.count("Location Balance", {"kho": KHO}), 0,
			"Location Balance được ghi HAI LẦN (ghi_dong_so → _cong_don_ton, rồi "
			"dung_lai_ton_vi_tri dựng lại) — vòng sửa 1 (Q2) thêm khoá riêng cho "
			"bảng này, trước đó không bài nào trong lớp kiểm nó dù _don_sach của "
			"chính file test này biết bảng đó tồn tại (có dòng xoá nó).",
		)
		self.assertFalse(vk.kho_co_quan_ly_vi_tri(KHO), "cờ phải vẫn tắt")
		self.assertFalse(
			frappe.db.exists("Warehouse Location Setup", KHO),
			"chứng từ `Warehouse Location Setup` dựng SỚM (trước khi ghi sổ, để "
			"Dynamic Link `chung_tu` có chỗ trỏ tới) cũng phải cuốn theo rollback — "
			"đây là điểm khác brief gốc (xem docstring `bat()`), không bài nào khác "
			"trong lớp này khoá riêng nó.",
		)

	def test_bat_lai_kho_da_bat_thi_chan(self):
		bat(KHO)
		with self.assertRaises(frappe.ValidationError):
			bat(KHO)


class TestBatQuyen(FrappeTestCase):
	"""`bat()` GHI dữ liệu (tạo ô, ghi sổ, đổi cờ) — kiểm quyền ở đây quan
	trọng hơn ở `xem_truoc` (chỉ đọc). Site có tài khoản `Website User`
	thật (khách cổng `miyano_portal`); thiếu kiểm quyền nghĩa là người
	ngoài bật được quản lý vị trí cho kho nội bộ Miyano.
	"""

	def setUp(self):
		dam_bao_kho_thu()
		_don_sach(KHO)

	def tearDown(self):
		_don_sach(KHO)

	def test_website_user_bi_chan(self):
		self.assertTrue(
			frappe.db.exists("User", "bvminhduc@demo.miyano"),
			"Cần tài khoản Website User thật trên site để bài này có ý nghĩa.",
		)
		frappe.set_user("bvminhduc@demo.miyano")
		try:
			with self.assertRaises(frappe.PermissionError):
				bat(KHO)
		finally:
			frappe.set_user("Administrator")

		self.assertIsNone(vk.o_chua_xep(KHO), "bị chặn quyền thì không được tạo ô nào")
		self.assertEqual(
			frappe.db.count("Location Ledger Entry", {"kho": KHO}), 0,
			"bị chặn quyền thì không được ghi dòng sổ nào",
		)
		self.assertFalse(vk.kho_co_quan_ly_vi_tri(KHO), "bị chặn quyền thì cờ phải vẫn tắt")
		self.assertFalse(
			frappe.db.exists("Warehouse Location Setup", KHO),
			"bị chặn quyền thì không được tạo cả chứng từ Warehouse Location Setup",
		)


class TestBatTonAm(FrappeTestCase):
	"""VÒNG SỬA (review advisor, sau khi Critical 1b đã "xong"): `_o_am`
	(Critical 1b) làm `bat()` đổi hành vi trên một kho có tồn ÂM cần chuyển
	đổi — TRƯỚC 1b, `bat()` CHUYỂN ĐỔI THÀNH CÔNG với một ô CHUA-XEP mang số
	âm (đúng như cảnh báo cũ của `xem_truoc` từng hứa: "sẽ mang số âm ngay
	từ đầu"). SAU 1b, `doi_soat_kho()` (mà `bat()` tự gọi để kiểm trước khi
	commit) thấy ô CHUA-XEP đó âm → `khop=False` → `bat()` `frappe.throw`,
	rollback sạch, KHÔNG còn "thành công với một ô âm" nữa.

	Đây là quyết định ĐÚNG (một ô âm là dữ liệu hỏng, không nên cho bật với
	nó) nhưng câu cảnh báo cũ của `xem_truoc` giờ SAI so với hành vi thật —
	đã sửa câu chữ cùng lúc (xem `xem_truoc`). Dựng tồn âm bằng cách đặt
	thẳng `Bin.actual_qty` — cùng khuôn `test_canh_bao_ton_am`
	(`test_bat_kho_xem_truoc.py`): ERPNext chặn giao dịch tạo tồn âm trên
	site này (không bật `allow_negative_stock`), nên tồn âm chỉ mô phỏng
	được qua hiệu chỉnh dữ liệu trực tiếp — đúng loại tình huống thật gây ra
	nó.
	"""

	def setUp(self):
		dam_bao_kho_thu()
		_don_sach(KHO)

	def tearDown(self):
		_don_sach(KHO)

	def test_bat_that_bai_neu_co_ton_am(self):
		item = _tao_item("_Test Bat Ton Am")
		if not frappe.db.exists("Bin", {"item_code": item, "warehouse": KHO}):
			frappe.get_doc({
				"doctype": "Bin", "item_code": item, "warehouse": KHO, "actual_qty": 0,
			}).insert(ignore_permissions=True)
		frappe.db.set_value("Bin", {"item_code": item, "warehouse": KHO}, "actual_qty", -5)

		kq_xem_truoc = xem_truoc(KHO)
		self.assertTrue(
			any("THẤT BẠI" in c for c in kq_xem_truoc["canh_bao"]),
			f"cảnh báo phải nói ĐÚNG hành vi hiện tại (bật sẽ thất bại), không hứa "
			f"'sẽ mang số âm ngay từ đầu' như trước Critical 1b: {kq_xem_truoc['canh_bao']}",
		)

		with self.assertRaises(frappe.ValidationError):
			bat(KHO)

		self.assertFalse(vk.kho_co_quan_ly_vi_tri(KHO), "bật thất bại thì cờ phải vẫn tắt")
		self.assertIsNone(vk.o_chua_xep(KHO), "bật thất bại thì không được để lại ô CHUA-XEP")
		self.assertEqual(
			frappe.db.count("Location Ledger Entry", {"kho": KHO}), 0,
			"bật thất bại thì không được để lại dòng sổ nào (kể cả dòng mang số âm)",
		)

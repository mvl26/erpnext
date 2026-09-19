"""Huỷ chứng từ — đảo ĐÚNG ô gốc, không chạy lại FEFO.

Khi huỷ, ERPNext ghi THÊM dòng SLE mới với số lượng đảo dấu rồi mới cờ
is_cancelled lên dòng cũ (erpnext stock_ledger.py:66-90, 212). Dòng mới vẫn
qua make_entry() nên hook vẫn nổ.

Cái bẫy: nếu nhánh huỷ cứ chạy FEFO như một lần xuất/nhập bình thường thì
hàng được trả về Ô KHÁC với ô đã lấy. Tổng tồn vẫn đúng nên báo cáo đối
soát KHÔNG bắt được — chỉ tới lúc kiểm kê thực tế mới lộ, và lúc đó không
còn dấu vết để lần ngược. Bộ test này là lưới duy nhất.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.vi_tri_kho.tests.test_hook_nhap import _bat_kho_tho, _tao_item, _tat_kho_tho
from erpnext.vi_tri_kho.vitri import kho as vk
from erpnext.vi_tri_kho.vitri import so

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


def _xuat_kho(item, qty):
	se = frappe.get_doc(
		{
			"doctype": "Stock Entry",
			"stock_entry_type": "Material Issue",
			"company": "Miyano Việt Nam",
			"items": [{"item_code": item, "qty": qty, "s_warehouse": KHO}],
		}
	)
	se.insert(ignore_permissions=True)
	se.submit()
	return se


def _nhap_kho(item, qty):
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


def _seed_o(item, o, so_luong):
	"""Chuyển `so_luong` từ CHUA-XEP (đã có sẵn, nhập thật trước đó) sang ô
	`o` — chỉ đổi SỔ VỊ TRÍ, không đụng ERPNext Bin (đã đúng tổng từ lần
	nhập thật). Dùng chung_tu trỏ về chính Storage Location liên quan (bản
	ghi có thật), giống quy ước test_fefo.py::_dat — xem lý do đầy đủ ở
	docstring `TestHuyPhieuXuat._seed_o_gan`.
	"""
	o_tam = vk.o_chua_xep(KHO)
	so.ghi_dong_so(
		o=o_tam,
		kho=KHO,
		vat_tu=item,
		so_lo=None,
		so_luong=-so_luong,
		chung_tu_type="Storage Location",
		chung_tu=o_tam,
		chung_tu_row="r",
		sle=None,
		ngay="2026-09-01",
		thoi_diem="2026-09-01 08:30:00",
		company="Miyano Việt Nam",
	)
	so.ghi_dong_so(
		o=o,
		kho=KHO,
		vat_tu=item,
		so_lo=None,
		so_luong=so_luong,
		chung_tu_type="Storage Location",
		chung_tu=o,
		chung_tu_row="r",
		sle=None,
		ngay="2026-09-01",
		thoi_diem="2026-09-01 08:30:00",
		company="Miyano Việt Nam",
	)


class TestHuyPhieuXuat(FrappeTestCase):
	"""Ba bài dưới đây khẳng định giá trị TUYỆT ĐỐI về tồn ở một ô.

	FrappeTestCase rollback theo LỚP, không theo từng bài (memory: "test
	isolation") — đo được thật ở lần ĐỎ đầu tiên khi cả ba bài dùng chung
	`self.item`: `test_huy_tra_hang_ve_dung_o_da_lay` cancel một Material
	Issue mà `dao_theo_o_goc` CHƯA tồn tại nên hàng bị trả về CHUA-XEP thay
	vì o_gan, để lại tồn dư trong CHUA-XEP; bài kế tiếp seed thêm 10 vào
	CHUA-XEP mà không biết còn dư, `ton_o(o_tam,...)` ra 12 thay vì 10. Mỗi
	bài vì vậy tự tạo mặt hàng riêng qua `_seed_o_gan`, không dùng chung
	`self.item`/`setUp`.
	"""

	def setUp(self):
		_bat_kho_tho(KHO)
		self.o_xa = _o("9Z21010101", thu_tu=9)
		self.o_gan = _o("9Z20010101", thu_tu=1)

	def tearDown(self):
		_tat_kho_tho(KHO)

	def _seed_o_gan(self, ma_item, so_luong=10):
		"""Tạo mặt hàng riêng, đặt `so_luong` ở o_gan.

		Lệch khỏi brief, hai điểm:
		(a) brief seed thẳng qua so.ghi_dong_so với chung_tu_type="Stock
		    Entry", chung_tu="SEED-HUY" (chứng từ giả, không tồn tại).
		    so.ghi_dong_so KHÔNG ignore_links (vòng sửa 1 Task 4) nên
		    chứng từ phải là bản ghi có thật, không thì LinkValidationError
		    — đo được ở lần chạy ĐỎ đầu (traceback thật: "Could not find
		    Chứng từ: SEED-HUY").
		(b) chỉ seed sổ vị trí mà KHÔNG có tồn kho ERPNext thật đứng sau thì
		    _xuat_kho() (Material Issue thật) ném ValidationError
		    "Valuation Rate...is required" vì ERPNext chưa từng thấy một
		    giao dịch NHẬP nào cho mặt hàng này — cũng đo được ở lần ĐỎ.
		Sửa: nhập thật (basic_rate=1000) để có tồn kho + định giá thật, hook
		tự dồn vào CHUA-XEP; rồi chuyển sổ VỊ TRÍ (không đụng ERPNext Bin)
		từ CHUA-XEP sang o_gan bằng `_seed_o`.
		"""
		item = _tao_item(ma_item)
		_nhap_kho(item, so_luong)
		o_tam = vk.o_chua_xep(KHO)
		self.assertEqual(so.ton_o(o_tam, item, None), so_luong, "tiền đề: đã nhập vào CHUA-XEP")
		_seed_o(item, self.o_gan, so_luong)
		self.assertEqual(
			so.ton_o(self.o_gan, item, None), so_luong, "tiền đề: đã chuyển sổ vị trí sang o_gan"
		)
		self.assertEqual(so.ton_o(o_tam, item, None), 0, "tiền đề: CHUA-XEP về lại 0")
		return item

	def test_huy_tra_hang_ve_dung_o_da_lay(self):
		"""Sửa (review điều phối, Minor 2): comment cũ ("đổi đường đi để
		FEFO nếu chạy lại sẽ chọn ô KHÁC") SAI ở chiều này — huỷ một Material
		Issue sinh SLE đảo dấu DƯƠNG (trả hàng lại), và `_ghi_mot_phan` chỉ
		gọi FEFO (`chon_o_xuat`) khi `so_luong < 0`; dấu dương luôn đi
		nhánh CHUA-XEP (`_bat_buoc_o_chua_xep`), KHÔNG BAO GIỜ chạm FEFO.
		Đổi `thu_tu_lay_hang` của o_xa vì vậy vô hiệu ở chiều này — xoá.
		Discriminator THẬT cho chiều huỷ-xuất: nếu `dao_theo_o_goc` không
		chạy (rơi xuống đường thường), hàng phải về CHUA-XEP chứ không phải
		o_gan — nên khoá bằng cách khẳng định CHUA-XEP vẫn ở 0 sau huỷ.
		"""
		item = self._seed_o_gan("_Test WMS Huy A")
		se = _xuat_kho(item, 4)
		self.assertEqual(so.ton_o(self.o_gan, item, None), 6)

		se.cancel()

		self.assertEqual(
			so.ton_o(self.o_gan, item, None),
			10,
			"hàng phải quay về đúng ô đã lấy",
		)
		self.assertEqual(
			so.ton_o(vk.o_chua_xep(KHO), item, None),
			0,
			"KHÔNG được rơi xuống đường thường (CHUA-XEP) — đó là nơi hàng "
			"sẽ tới nếu dao_theo_o_goc không chạy ở chiều huỷ-xuất",
		)

	def test_dong_goc_bi_co_da_huy(self):
		item = self._seed_o_gan("_Test WMS Huy B")
		se = _xuat_kho(item, 2)
		se.cancel()
		goc = frappe.get_all(
			"Location Ledger Entry",
			filters={"chung_tu": se.name, "so_luong": ("<", 0)},
			fields=["name", "da_huy"],
		)
		self.assertTrue(goc)
		self.assertTrue(all(d.da_huy for d in goc), "dòng gốc phải bị cờ đã đảo")

	def test_khong_xoa_dong_nao(self):
		item = self._seed_o_gan("_Test WMS Huy C")
		se = _xuat_kho(item, 2)
		truoc = frappe.db.count("Location Ledger Entry", {"chung_tu": se.name})
		se.cancel()
		sau = frappe.db.count("Location Ledger Entry", {"chung_tu": se.name})
		self.assertGreater(sau, truoc, "huỷ phải GHI THÊM dòng đảo, không xoá dòng cũ")

	def test_huy_tra_hang_ve_nhieu_o_dung_tung_o(self):
		"""Important 1 (review điều phối, vòng sửa 1): vòng lặp `for d in
		goc` trong `dao_theo_o_goc` — linh hồn của việc đảo ĐÚNG NHIỀU ô
		cùng lúc — chưa bài nào ở trên đo được, vì `goc` của chúng luôn có
		ĐÚNG MỘT dòng. Đột biến `for d in goc[:1]` (chỉ đảo dòng gốc đầu
		tiên) không làm bài nào ở trên đỏ.

		Seed 10 ở o_gan (thu_tu=1, gần) và 5 ở o_xa (thu_tu=9, xa — vẫn giữ
		đúng thứ tự setUp, không cần đổi). Xuất 12: FEFO lấy hết 10 từ
		o_gan rồi 2 từ o_xa — MỘT dòng SLE xuất (một dòng con Stock Entry)
		nhưng `tach_theo_lo`/`chon_o_xuat` tách thành HAI dòng Location
		Ledger Entry gốc, CÙNG `chung_tu_row` vì cùng một dòng chứng từ.
		Huỷ, rồi khẳng định CẢ HAI ô về đúng số ban đầu — không dồn hết vào
		một ô (mất `so_luong` của ô kia), không bỏ sót ô kia (giữ nguyên
		tồn ma ở đó).
		"""
		item = _tao_item("_Test WMS Huy Nhieu O")
		_nhap_kho(item, 15)
		o_tam = vk.o_chua_xep(KHO)
		_seed_o(item, self.o_gan, 10)
		_seed_o(item, self.o_xa, 5)
		self.assertEqual(so.ton_o(self.o_gan, item, None), 10, "tiền đề")
		self.assertEqual(so.ton_o(self.o_xa, item, None), 5, "tiền đề")
		self.assertEqual(so.ton_o(o_tam, item, None), 0, "tiền đề")

		se = _xuat_kho(item, 12)

		goc = frappe.get_all(
			"Location Ledger Entry",
			filters={"chung_tu": se.name, "so_luong": ("<", 0)},
			fields=["o", "so_luong"],
		)
		self.assertEqual(
			len(goc),
			2,
			"tiền đề: FEFO phải tách một dòng SLE xuất thành hai dòng sổ gốc "
			"— một cho mỗi ô — để bài này có sức phân biệt vòng lặp",
		)

		se.cancel()

		self.assertEqual(so.ton_o(self.o_gan, item, None), 10, "o_gan phải về đúng 10")
		self.assertEqual(so.ton_o(self.o_xa, item, None), 5, "o_xa phải về đúng 5, không bị bỏ sót")


class TestHuyPhieuNhap(FrappeTestCase):
	def setUp(self):
		_bat_kho_tho(KHO)
		self.item = _tao_item("_Test WMS Huy Nhap")

	def tearDown(self):
		_tat_kho_tho(KHO)

	def test_huy_nhap_lay_hang_ra_dung_o_da_dat(self):
		"""Minor 1 (review điều phối, vòng sửa 1): bản cũ của bài này xanh
		VÔ NGHĨA — lúc huỷ chỉ có đúng CHUA-XEP giữ hàng của mặt hàng này,
		nên nếu `dao_theo_o_goc` bị thay bằng đường thường (huỷ nhập →
		delta ÂM → FEFO), FEFO cũng chọn đúng CHUA-XEP vì đó là ô DUY NHẤT
		có tồn — không có sức phân biệt. Đây MỚI là chỗ điều bắt buộc #1 có
		nội dung thật: chiều huỷ-NHẬP (không phải huỷ-xuất, xem Minor 2 ở
		`TestHuyPhieuXuat`) là chiều DUY NHẤT có thể chạm FEFO nếu
		`dao_theo_o_goc` không chạy, vì SLE huỷ của Material Receipt mang
		dấu ÂM.

		Sửa: seed thêm 4 đơn vị CÙNG mặt hàng vào một ô KHÁC
		(`TEST-HUY-NHAP-KHAC`, thu_tu=-5, nhỏ hơn CHUA-XEP mặc định 0) từ
		MỘT chứng từ khác — không liên quan gì tới `se` đang huỷ. Nếu FEFO
		chạy lại (dao_theo_o_goc bị bỏ qua), nó sẽ ưu tiên rút từ ô này
		trước (thu_tu nhỏ hơn) — khoá bằng cách khẳng định ô này KHÔNG bị
		đụng sau khi huỷ `se`.
		"""
		o_khac = _o("9Z93010101", thu_tu=-5)
		_nhap_kho(self.item, 4)
		_seed_o(self.item, o_khac, 4)
		self.assertEqual(so.ton_o(o_khac, self.item, None), 4, "tiền đề: ô khác đã có sẵn hàng")

		se = _nhap_kho(self.item, 8)
		o = vk.o_chua_xep(KHO)
		self.assertEqual(so.ton_o(o, self.item, None), 8)
		se.cancel()
		self.assertEqual(so.ton_o(o, self.item, None), 0)
		self.assertEqual(
			so.ton_o(o_khac, self.item, None),
			4,
			"ô khác (thu_tu nhỏ hơn CHUA-XEP) KHÔNG được bị FEFO rút nhầm vào — "
			"nếu dao_theo_o_goc không chạy, FEFO sẽ ưu tiên rút từ đây trước",
		)


class TestHuyChungTuLapTruocKhiBatViTri(FrappeTestCase):
	"""Điều 3 bắt buộc (brief Task 9): `dao_theo_o_goc()` phải trả False khi
	không tìm thấy dòng gốc — ca chứng từ lập TRƯỚC khi kho bật quản lý vị
	trí. Khi đó luồng rơi xuống đường thường (FEFO / CHUA-XEP), là hành vi
	ĐÚNG, không phải lỗi. Bốn bài trong TestHuyPhieuXuat/TestHuyPhieuNhap
	đều seed dữ liệu SAU khi kho đã bật nên không đi qua nhánh này — chưa
	có bài nào khoá nó cho tới class này (advisor điều phối chỉ ra thiếu)."""

	def setUp(self):
		_tat_kho_tho(KHO)
		self.item = _tao_item("_Test WMS Huy Truoc Bat")

	def tearDown(self):
		_tat_kho_tho(KHO)

	def test_huy_khi_khong_co_dong_goc_roi_xuong_duong_thuong(self):
		# Lập cả nhập lẫn xuất khi kho CHƯA bật quản lý vị trí — hook bỏ qua
		# hoàn toàn (kho_co_quan_ly_vi_tri=False ở lúc submit), không ghi
		# dòng sổ vị trí nào cho hai chứng từ này.
		_nhap_kho(self.item, 10)
		se_xuat = _xuat_kho(self.item, 3)
		self.assertEqual(
			frappe.db.count("Location Ledger Entry", {"chung_tu": se_xuat.name}),
			0,
			"tiền đề: chưa có dòng sổ vị trí nào cho chứng từ này (kho chưa bật)",
		)

		# Bật quản lý vị trí RỒI MỚI huỷ phiếu xuất — dao_theo_o_goc() phải
		# trả False (không tìm thấy dòng gốc) và KHÔNG được ném lỗi; luồng
		# rơi xuống đường thường (huỷ xuất => delta dương => dồn CHUA-XEP).
		_bat_kho_tho(KHO)
		se_xuat.cancel()

		dong = frappe.get_all(
			"Location Ledger Entry",
			filters={"chung_tu": se_xuat.name},
			fields=["o", "so_luong", "da_huy"],
		)
		self.assertEqual(
			len(dong),
			1,
			"đúng MỘT dòng — đường thường (CHUA-XEP), không phải một cặp đảo "
			"của dao_theo_o_goc vì không có dòng gốc để tra",
		)
		self.assertEqual(dong[0].o, vk.o_chua_xep(KHO))
		self.assertEqual(dong[0].so_luong, 3)
		self.assertEqual(
			dong[0].da_huy,
			0,
			"đường thường (không phải dao_theo_o_goc) không tự cờ da_huy",
		)

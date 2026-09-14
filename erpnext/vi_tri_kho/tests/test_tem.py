"""Chọn ô để in tem: đúng nhánh, đúng loại ô, và không bao giờ ra thừa.

Phần VẼ tem (bố cục SPD ba nhóm số, khổ 45×25 và 50×30mm, mã vạch, cửa sổ
in) nằm trọn trong `public/js/vi_tri_kho/tem_vi_tri.js` — bộ test này là
Python nên KHÔNG bài nào ở đây chứng minh tem in ra đúng khổ hay đúng bố cục.
Đừng đọc file này như thể nó chứng minh điều đó; chỗ duy nhất kiểm được việc
đó là in thử một con tem ở tỉ lệ 100%.

Cái nó khoá là phần quyết định **in những ô nào**, và đó mới là chỗ hỏng
đắt: in thiếu thì người ta thấy ngay (kệ trống tem), còn **in thừa** thì ra
một xấp tem của kho khác, dán nhầm lên kệ, và mỗi lần quét sau đó đều trỏ
sai chỗ — không có gì báo lỗi.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.vi_tri_kho.vitri.tem import TRAN_SO_TEM, danh_sach_tem

KHO = "Kho Miyano - MYN"


def _o(ma_o, **kw):
	if not frappe.db.exists("Storage Location", ma_o):
		frappe.get_doc({"doctype": "Storage Location", "ma_o": ma_o, "kho": KHO, **kw}).insert(
			ignore_permissions=True
		)
	return ma_o


class _NenTem(FrappeTestCase):
	"""Dựng hai nhánh tách biệt dưới hai Khu khác nhau.

	Phải là hai KHU khác nhau, không phải hai dãy cùng khu: bài kiểm bẫy
	`lft = 0` bên dưới cần một nhánh hoàn toàn không dính dáng để chứng minh
	phép lọc không quét sang.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.a1 = _o("9T01010101")
		cls.a2 = _o("9T01010102")
		cls.a3 = _o("9T01020101")  # khác khoang, cùng khu
		cls.b1 = _o("9U01010101")  # khu khác hẳn
		# Năm thành phần ĐÔI MỘT KHÁC NHAU. Mọi ô khác trong nền test đều
		# toàn "01", nên một lỗi hoán vị Khoang↔Tầng vẫn xanh với chúng.
		cls.c1 = _o("9V02030405")
		cls.zzz = frappe.db.get_value("Storage Location", {"la_o_chua_xep": 1, "kho": KHO}, "name")


class TestChonDungNhanh(_NenTem):
	def test_mot_o_la_ra_dung_mot_tem(self):
		ma = [d["ma_o"] for d in danh_sach_tem(self.a1)]
		self.assertEqual(ma, [self.a1])

	def test_nut_nhom_ra_moi_o_la_ben_duoi(self):
		ma = sorted(d["ma_o"] for d in danh_sach_tem("9T"))
		self.assertEqual(ma, sorted([self.a1, self.a2, self.a3]))

	def test_khong_quet_sang_khu_khac(self):
		"""Chốt âm: bấm in ở Khu 9T không được ra tem của Khu 9U.

		Thiếu khẳng định này thì một đột biến bỏ mệnh đề `lft between` vẫn
		xanh ở bài trên (nó chỉ kiểm 3 mã CÓ mặt, không kiểm mã nào KHÔNG
		được có).
		"""
		ma = {d["ma_o"] for d in danh_sach_tem("9T")}
		self.assertNotIn(self.b1, ma)

	def test_khong_in_tem_cho_nut_nhom(self):
		"""Nút nhóm (Dãy/Khoang/Tầng) không có kệ riêng để dán."""
		ma = {d["ma_o"] for d in danh_sach_tem("9T")}
		for nhom in ("9T", "9T01", "9T0101", "9T010101"):
			self.assertNotIn(nhom, ma, f"{nhom} là nút nhóm, không được có tem")

	def test_khong_in_tem_cho_o_chua_xep(self):
		"""Ô hệ thống là ô ẢO — không có kệ thật, dán tem vào đâu?"""
		self.assertIsNotNone(self.zzz, f"{KHO} phải có đúng một ô 'Chưa xếp vị trí'")
		ma = {d["ma_o"] for d in danh_sach_tem(self.zzz)}
		self.assertEqual(ma, set(), "Ô 'Chưa xếp vị trí' không được sinh tem nào")

	def test_moi_dong_mang_du_thu_tem_can(self):
		"""Thiếu một trường thì tem in ra trống chỗ đó, không có lỗi nào."""
		d = danh_sach_tem(self.a1)[0]
		for khoa in ("ma_o", "ma_in_nhan", "ten_o", "kho"):
			self.assertIn(khoa, d, f"dòng tem thiếu {khoa!r}")
		self.assertEqual(d["ma_o"], self.a1)
		self.assertEqual(d["ma_in_nhan"], "9T0101-0101", "phải là dạng có gạch nối cho mắt người đọc")

	def test_moi_dong_mang_du_nam_thanh_phan_cua_ma(self):
		"""Tem SPD in mã tách làm ba nhóm (Khu+Dãy · Khoang · Tầng+Ô), nên
		mỗi dòng phải mang sẵn năm thành phần.

		Dùng ô có năm giá trị đôi một khác nhau: nếu chỉ thử `9T01010101`
		thì một lỗi hoán vị Khoang↔Tầng vẫn xanh, mà hậu quả của nó là cả
		xấp tem in sai tầng rồi dán lên kệ.
		"""
		d = danh_sach_tem(self.c1)[0]
		self.assertEqual(
			{k: d.get(k) for k in ("khu", "day", "khoang", "tang", "o")},
			{"khu": "9V", "day": "02", "khoang": "03", "tang": "04", "o": "05"},
		)

	def test_nam_thanh_phan_ghep_lai_dung_bang_ma_o(self):
		"""Chốt âm: ba nhóm số trên tem THAY dòng chữ dưới mã vạch, nên đọc
		liền chúng phải ra đúng chuỗi máy quét trả về. Lệch một ký tự là
		người gõ tay ra một ô khác mà không biết.
		"""
		for d in danh_sach_tem("9T") + danh_sach_tem(self.c1):
			ghep = d["khu"] + d["day"] + d["khoang"] + d["tang"] + d["o"]
			self.assertEqual(ghep, d["ma_o"], f"ba nhóm trên tem không ghép lại thành {d['ma_o']}")


class TestBayToaDoRong(_NenTem):
	"""Cùng hình dạng với bẫy F8 đã trả giá một lần ở `fefo.py`.

	Bản ghi chưa hội tụ mang `lft = rgt = 0`. Cho nó qua thì mệnh đề lọc
	thành `lft between 0 and 0`, tức `lft = 0` — khớp MỌI bản ghi 0/0 khác
	trên toàn hệ, không riêng nhánh đang chọn. Hệ quả: bấm in một khoang lại
	ra tem của những ô hoàn toàn không liên quan, có thể của kho khác. Chặn
	ở nguồn, đúng cách `fefo.py::chon_o_xuat` chặn `pham_vi`.
	"""

	def test_nut_chua_co_toa_do_bi_tu_choi(self):
		frappe.db.set_value("Storage Location", "9T0101", {"lft": 0, "rgt": 0}, update_modified=False)
		with self.assertRaises(frappe.ValidationError):
			danh_sach_tem("9T0101")

	def test_tu_choi_chu_khong_tra_ve_ban_ghi_khong_lien_quan(self):
		"""Chốt âm của bài trên: một đột biến đổi `throw` thành `return []`
		vẫn làm bài trên xanh (assertRaises đổi thành không raise thì đỏ —
		nhưng đột biến BỎ HẲN phép kiểm thì hàm chạy tiếp và trả về rác).
		Bài này bắt đúng cái rác đó.
		"""
		frappe.db.set_value("Storage Location", "9U01010101", {"lft": 0, "rgt": 0}, update_modified=False)
		frappe.db.set_value("Storage Location", "9T0101", {"lft": 0, "rgt": 0}, update_modified=False)
		try:
			ket_qua = {d["ma_o"] for d in danh_sach_tem("9T0101")}
		except frappe.ValidationError:
			return  # chặn ở nguồn — đúng ý đồ
		self.assertNotIn(
			"9U01010101",
			ket_qua,
			"lọt bản ghi của Khu khác qua phép `lft between 0 and 0` — đúng bẫy F8",
		)


class TestTranSoTem(_NenTem):
	def test_vuot_tran_thi_tu_choi_han(self):
		"""Gõ nhầm nốt gốc là cả cuộn tem chạy ra máy in.

		Từ chối hẳn chứ không cắt bớt im lặng: in 500 tem đầu rồi dừng thì
		người vận hành tưởng đã in đủ cả kho.
		"""
		self.assertGreater(TRAN_SO_TEM, 0)
		with self.assertRaises(frappe.ValidationError):
			danh_sach_tem(self.a1, so_ban=TRAN_SO_TEM + 1)

	def test_trong_tran_thi_nhan_binh_thuong(self):
		"""Đối chứng: trần CHỈ chặn cái vượt, không chặn việc in bình thường."""
		self.assertEqual(len(danh_sach_tem(self.a1, so_ban=2)), 1)


class TestQuyenInTem(_NenTem):
	def tearDown(self):
		frappe.set_user("Administrator")

	def _nguoi_dung_khong_vai_tro(self):
		ten = "tem-khong-quyen@mo-phong.local"
		if not frappe.db.exists("User", ten):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": ten,
					"first_name": "Tem",
					"send_welcome_email": 0,
					"roles": [],
				}
			).insert(ignore_permissions=True)
		return ten

	def test_nguoi_khong_co_vai_tro_bi_chan(self):
		"""Đăng nhập hợp lệ KHÔNG phải điều kiện đủ để đọc sơ đồ kho nội bộ.

		Danh mục ô lộ ra toàn bộ cách bố trí kho — `@frappe.whitelist()` một
		mình chỉ chặn khách vãng lai, không chặn người đã đăng nhập.
		"""
		frappe.set_user(self._nguoi_dung_khong_vai_tro())
		with self.assertRaises(frappe.PermissionError):
			danh_sach_tem(self.a1)

	def test_stock_user_in_duoc(self):
		"""Đối chứng: thủ kho PHẢI in lại được khi tem rách, bẩn, bong.

		Thiếu bài này thì một đột biến siết quyền xuống chỉ còn quản lý vẫn
		xanh, và thủ kho mất khả năng tự in lại mà không ai phát hiện.
		"""
		ten = "tem-thu-kho@mo-phong.local"
		if not frappe.db.exists("User", ten):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": ten,
					"first_name": "Thu Kho",
					"send_welcome_email": 0,
					"roles": [{"role": "Stock User"}],
				}
			).insert(ignore_permissions=True)
		frappe.set_user(ten)
		self.assertEqual(len(danh_sach_tem(self.a1)), 1)

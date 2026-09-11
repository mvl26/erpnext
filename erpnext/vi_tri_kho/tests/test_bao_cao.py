"""Hai báo cáo vận hành.

"Hàng chưa xếp vị trí" là danh sách việc của thủ kho — nó biến việc bỏ sót
khai vị trí thành hữu hình thay vì thành lỗi. Không có báo cáo này thì ô
CHUA-XEP âm thầm phình ra và không ai biết.

VÒNG SỬA 1/5 (review điều phối, Việc 2): thêm
`test_thu_tu_theo_thu_tu_lay_hang_khong_theo_alphabet_o`. Đột biến của
người review (xoá/đảo `order by ifnull(sl.thu_tu_lay_hang, 0) asc` trong
`ton_kho_theo_vi_tri.py`) không bị bài nào bắt — đúng khuyết tật đã trả
giá thật ở Task 8 (bảy bài FEFO xanh mà không khoá được cột quyết định vì
tên ô tình cờ trùng thứ tự alphabet). Bài mới đặt tên ô MÂU THUẪN với
`thu_tu_lay_hang` (ô "Z..." phải đứng TRƯỚC ô "A..." vì thu_tu_lay_hang
nhỏ hơn) để không thể xanh nhờ khoá sắp xếp phụ (tên ô, vốn cũng có mặt
trong `order by` làm khoá phá vỡ đồng hạng).
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.vi_tri_kho.tests.test_bat_kho import _don_sach
from erpnext.vi_tri_kho.tests.test_hook_nhap import _nhap_kho as _nhap
from erpnext.vi_tri_kho.tests.test_hook_nhap import _tao_item
from erpnext.vi_tri_kho.vitri import kho as vk
from erpnext.vi_tri_kho.vitri.bat_kho import bat

KHO = "Kho Miyano - MYN"


class TestBaoCaoTonTheoViTri(FrappeTestCase):
	def setUp(self):
		_don_sach(KHO)
		bat(KHO)

	def tearDown(self):
		_don_sach(KHO)

	def test_chay_duoc_va_co_dong(self):
		from erpnext.vi_tri_kho.report.ton_kho_theo_vi_tri.ton_kho_theo_vi_tri import execute

		cot, dong = execute({"kho": KHO})
		self.assertTrue(cot)
		self.assertTrue(dong, "kho vừa bật có tồn nên phải có dòng")

	def test_khong_hien_o_het_hang(self):
		from erpnext.vi_tri_kho.report.ton_kho_theo_vi_tri.ton_kho_theo_vi_tri import execute

		frappe.db.sql("update `tabLocation Balance` set so_luong = 0 where kho=%s", (KHO,))
		_, dong = execute({"kho": KHO})
		self.assertEqual(dong, [])

	def test_thu_tu_theo_thu_tu_lay_hang_khong_theo_alphabet_o(self):
		"""Khoá cột sort THẬT (`thu_tu_lay_hang`), không phải khoá phụ (tên ô
		trùng alphabet với nó) — xem VÒNG SỬA 1 ở docstring đầu file.

		"Z-..." mang thu_tu_lay_hang=1 (phải đứng TRƯỚC), "A-..." mang
		thu_tu_lay_hang=2 (phải đứng SAU) — cố ý MÂU THUẪN với thứ tự
		alphabet của tên ô, nên nếu code lỡ sắp theo `lb.o asc` thay vì
		`thu_tu_lay_hang asc` thì thứ tự trả về sẽ ĐẢO NGƯỢC và bài này bắt
		được ngay, không cần nhìn vào SQL.
		"""
		from erpnext.vi_tri_kho.report.ton_kho_theo_vi_tri.ton_kho_theo_vi_tri import execute

		item = _tao_item("_Test BC Thu Tu Lay Hang")
		o_truoc = "K19Z99010101"  # thu_tu_lay_hang=1, alphabet đứng SAU "A-..."
		o_sau = "K19Z01010101"  # thu_tu_lay_hang=2, alphabet đứng TRƯỚC "Z-..."

		for ma_o, thu_tu in ((o_truoc, 1), (o_sau, 2)):
			if not frappe.db.exists("Storage Location", ma_o):
				frappe.get_doc(
					{
						"doctype": "Storage Location",
						"ma_o": ma_o,
						"kho": KHO,
						"thu_tu_lay_hang": thu_tu,
					}
				).insert(ignore_permissions=True)

		for ma_o in (o_truoc, o_sau):
			frappe.get_doc(
				{
					"doctype": "Location Balance",
					"o": ma_o,
					"kho": KHO,
					"vat_tu": item,
					"so_luong": 3,
				}
			).insert(ignore_permissions=True)

		_, dong = execute({"kho": KHO, "vat_tu": item})
		thu_tu_o = [d[0] for d in dong]
		self.assertEqual(
			thu_tu_o,
			[o_truoc, o_sau],
			f"phải sắp theo thu_tu_lay_hang (1 rồi 2: {o_truoc} rồi {o_sau}), không "
			f"theo alphabet tên ô (alphabet sẽ cho '{o_sau}' trước '{o_truoc}', "
			f"ngược lại). Thứ tự thấy được: {thu_tu_o}",
		)


class TestBaoCaoHangChuaXep(FrappeTestCase):
	def setUp(self):
		_don_sach(KHO)
		bat(KHO)

	def tearDown(self):
		_don_sach(KHO)

	def test_liet_ke_hang_o_chua_xep(self):
		from erpnext.vi_tri_kho.report.hang_chua_xep_vi_tri.hang_chua_xep_vi_tri import execute

		_, dong = execute({"kho": KHO})
		self.assertTrue(dong, "vừa bật xong thì mọi thứ đang ở CHUA-XEP")

	def test_khong_liet_ke_o_khac(self):
		from erpnext.vi_tri_kho.report.hang_chua_xep_vi_tri.hang_chua_xep_vi_tri import execute

		o_thuong = "K19Z03010101"
		if not frappe.db.exists("Storage Location", o_thuong):
			frappe.get_doc(
				{
					"doctype": "Storage Location",
					"ma_o": o_thuong,
					"kho": KHO,
				}
			).insert(ignore_permissions=True)
		frappe.get_doc(
			{
				"doctype": "Location Balance",
				"o": o_thuong,
				"kho": KHO,
				"vat_tu": _tao_item("_Test BC Item"),
				"so_luong": 5,
			}
		).insert(ignore_permissions=True)

		_, dong = execute({"kho": KHO})
		# GHI ĐÈ so với brief gốc (review advisor): brief chỉ khẳng định
		# o_thuong VẮNG MẶT — bài đó cũng xanh nếu truy vấn trả rỗng vì
		# một lý do bất kỳ khác (tautology "xanh vì rỗng" đã ghim ở
		# task-10-report.md). Khẳng định thêm dong KHÔNG rỗng: báo cáo
		# phải đang thực sự liệt kê tồn CHUA-XEP tại thời điểm này (đã
		# khoá ở test_liet_ke_hang_o_chua_xep, nhưng khoá lại tại đây để
		# chính bài kiểm-vắng-mặt không tự đứng được nhờ dữ liệu rỗng).
		self.assertTrue(dong, "phải vẫn còn tồn CHUA-XEP thật để bài vắng-mặt có ý nghĩa")
		self.assertNotIn(o_thuong, [d[0] for d in dong])


class TestBaoCaoDoiSoat(FrappeTestCase):
	"""Việc (E) (review điều phối, sau khi 147/147 bài "xong") — lưới an
	toàn của TOÀN HỆ (`doi_soat_kho`) được test rất kỹ, nhưng lớp BỌC REPORT
	(`doi_soat_ton_vi_tri.execute()`, thứ thủ kho THẬT SỰ mở lên) thì chưa
	bài nào gọi. Khoá hai điều: (1) guard `frappe.throw` khi thiếu filter
	`kho` (I4, vòng sửa cũ — có mã nhưng chưa ai gọi qua để đo); (2) phép
	chiếu cột đúng với hình dạng MỚI sau Critical 1b (`loai`/`o`/`vat_tu`/
	`so_lo`/`gia_tri_1`/`gia_tri_2`/`lech` — gộp cả ba loại lệch vào một
	bảng, xem docstring module report).
	"""

	def setUp(self):
		_don_sach(KHO)
		bat(KHO)

	def tearDown(self):
		_don_sach(KHO)

	def test_thieu_filter_kho_bi_chan(self):
		from erpnext.vi_tri_kho.report.doi_soat_ton_vi_tri.doi_soat_ton_vi_tri import execute

		with self.assertRaises(frappe.ValidationError):
			execute({})

	def test_khong_truyen_filters_cung_bi_chan(self):
		from erpnext.vi_tri_kho.report.doi_soat_ton_vi_tri.doi_soat_ton_vi_tri import execute

		with self.assertRaises(frappe.ValidationError):
			execute(None)

	def test_khop_thi_rong_va_dung_cot(self):
		from erpnext.vi_tri_kho.report.doi_soat_ton_vi_tri.doi_soat_ton_vi_tri import execute

		cot, dong = execute({"kho": KHO})
		self.assertTrue(cot)
		fieldnames = {c["fieldname"] for c in cot}
		self.assertEqual(
			fieldnames,
			{"loai", "o", "vat_tu", "so_lo", "gia_tri_1", "gia_tri_2", "lech"},
			"báo cáo phải chiếu đủ cột của cả ba loại lệch (Critical 1b), gộp một bảng",
		)
		self.assertEqual(dong, [], "vừa bật xong (khớp cả ba phép đo) thì báo cáo phải rỗng")

	def test_lech_tong_hien_dung_dong(self):
		from erpnext.vi_tri_kho.report.doi_soat_ton_vi_tri.doi_soat_ton_vi_tri import execute

		item = _tao_item("_Test BC DoiSoat Lech")
		_nhap(item, 10)
		ten = frappe.db.get_value("Location Balance", {"kho": KHO, "vat_tu": item}, "name")
		frappe.db.set_value("Location Balance", ten, "so_luong", 3)

		_, dong = execute({"kho": KHO})
		# Sửa thẳng bộ đệm bằng set_value (không qua so.ghi_dong_so) đồng
		# thời làm nó trôi khỏi sổ — cả "Lệch tồn" LẪN "Lệch bộ đệm" cùng lộ
		# ra cho item này (đúng — hai phép đo bắt hai lớp lỗi khác nhau, xem
		# Critical 1b), nên lọc thêm theo LOẠI để chỉ khoá đúng dòng đang
		# xét, không giả định nó là dòng DUY NHẤT.
		lech_tong = [d for d in dong if d[2] == item and d[0] == "Lệch tồn"]
		self.assertEqual(len(lech_tong), 1, f"phải ra đúng 1 dòng 'Lệch tồn' cho item này: {dong}")
		self.assertEqual(lech_tong[0][4], 3, "gia_tri_1 phải là tồn vị trí (3)")
		self.assertEqual(lech_tong[0][5], 10, "gia_tri_2 phải là tồn kho ERPNext (10)")
		self.assertEqual(lech_tong[0][6], -7, "lech = 3 - 10")

	def test_o_am_hien_dung_dong(self):
		from erpnext.vi_tri_kho.report.doi_soat_ton_vi_tri.doi_soat_ton_vi_tri import execute

		item = _tao_item("_Test BC DoiSoat OAm")
		_nhap(item, 10)
		o_chua_xep = frappe.db.get_value("Location Balance", {"kho": KHO, "vat_tu": item}, "o")
		o_gan = "K19Z02010101"
		if not frappe.db.exists("Storage Location", o_gan):
			frappe.get_doc(
				{
					"doctype": "Storage Location",
					"ma_o": o_gan,
					"kho": KHO,
				}
			).insert(ignore_permissions=True)
		frappe.db.sql(
			"update `tabLocation Balance` set so_luong = so_luong - 13 where o=%s and vat_tu=%s",
			(o_chua_xep, item),
		)
		frappe.get_doc(
			{
				"doctype": "Location Balance",
				"o": o_gan,
				"kho": KHO,
				"vat_tu": item,
				"so_lo": "",
				"so_luong": 13,
			}
		).insert(ignore_permissions=True)

		_, dong = execute({"kho": KHO})
		# Kịch bản này cũng làm bộ đệm trôi khỏi sổ (chuyển 13 sang o_gan mà
		# không ghi sổ) nên "Lệch bộ đệm" cũng lộ ra cho item này — lọc theo
		# LOẠI để chỉ khoá đúng dòng "Ô âm" đang xét.
		o_am_cua_item = [d for d in dong if d[2] == item and d[0] == "Ô âm"]
		self.assertEqual(len(o_am_cua_item), 1, f"phải ra đúng 1 dòng 'Ô âm': {dong}")
		self.assertEqual(o_am_cua_item[0][1], o_chua_xep)
		self.assertEqual(o_am_cua_item[0][4], -3)

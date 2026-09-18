"""Lấy hàng theo phân bổ — sổ vị trí phải trừ ĐÚNG ô thủ kho đã quét.

Bài chịu lực của cả thiết kế là `test_ghi_so_theo_o_da_phan_bo_chu_khong_theo_fefo`:
nó phân bổ vào ô mà FEFO KHÔNG chọn. Thiếu chốt đó thì một cài đặt bỏ qua phân bổ
và cứ chạy FEFO vẫn xanh, vì cả hai đường đều cho ra tổng đúng.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import nowdate

from erpnext.vi_tri_kho.vitri import so

KHO = "Kho Miyano - MYN"
CTY = "Miyano Việt Nam"
KHACH = "Bệnh viện DEMO Miyano E2E"
ITEM = "9L-VT-LAY-HANG"
LO = "9L-LO-LAY-01"
O_GAN = "9L01010101"
O_XA = "9L01010102"
DIEM_TEST = "test_lay_hang"


def _o(ma_o, thu_tu=None):
	"""Tạo ô nếu chưa có; CẬP NHẬT `thu_tu_lay_hang` dù ô đã tồn tại từ lần chạy
	trước — nếu chỉ bỏ qua khi đã tồn tại, một site đã có ô này với thứ tự khác
	sẽ khiến FEFO phá hoà theo tên ô thay vì theo `thu_tu` mà bài test khẳng định.
	"""
	if not frappe.db.exists("Storage Location", ma_o):
		frappe.get_doc(
			{"doctype": "Storage Location", "ma_o": ma_o, "kho": KHO, "thu_tu_lay_hang": thu_tu}
		).insert(ignore_permissions=True)
	elif thu_tu is not None:
		frappe.db.set_value("Storage Location", ma_o, "thu_tu_lay_hang", thu_tu)
	return ma_o


def _vat_tu():
	if not frappe.db.exists("Item", ITEM):
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": ITEM,
				"item_name": "Hàng thử lấy hàng PDA",
				"item_group": "All Item Groups",
				"stock_uom": "Nos",
				"is_stock_item": 1,
				"has_batch_no": 1,
				"create_new_batch": 0,
			}
		).insert(ignore_permissions=True)
	return ITEM


def _lo():
	if not frappe.db.exists("Batch", LO):
		frappe.get_doc(
			{"doctype": "Batch", "batch_id": LO, "item": ITEM, "expiry_date": "2029-01-31"}
		).insert(ignore_permissions=True)
	return LO


def _nhap_kho(so_luong):
	"""Nhập hàng thật vào ERPNext (Bin) — phiếu giao cần tồn kho thật, không chỉ sổ vị trí."""
	se = frappe.get_doc(
		{
			"doctype": "Stock Entry",
			"stock_entry_type": "Material Receipt",
			"company": CTY,
			"items": [
				{
					"item_code": ITEM,
					"qty": so_luong,
					"t_warehouse": KHO,
					"basic_rate": 1000,
					"batch_no": LO,
					"use_serial_batch_fields": 1,
				}
			],
		}
	)
	se.insert(ignore_permissions=True)
	se.submit()
	return se


def _chuyen_vao_o(cap):
	"""Chuyển hàng từ ô Chưa xếp sang các ô thật. `cap` = [(ô, số lượng), ...]."""
	chua_xep = frappe.db.get_value("Storage Location", {"kho": KHO, "la_o_chua_xep": 1})
	pxep = frappe.get_doc(
		{
			"doctype": "Location Transfer",
			"kho": KHO,
			"ngay": nowdate(),
			"items": [
				{"vat_tu": ITEM, "so_lo": LO, "tu_o": chua_xep, "den_o": o, "so_luong": sl}
				for o, sl in cap
			],
		}
	)
	pxep.insert(ignore_permissions=True)
	pxep.submit()
	return pxep


def _phieu_giao(so_luong, phan_bo=None):
	"""Phiếu giao NHÁP cho `so_luong`, kèm phân bổ nếu có. `phan_bo` = [(ô, số lượng), ...]."""
	dn = frappe.get_doc(
		{
			"doctype": "Delivery Note",
			"company": CTY,
			"customer": KHACH,
			"posting_date": nowdate(),
			"items": [
				{
					"item_code": ITEM,
					"qty": so_luong,
					"rate": 5000,
					"warehouse": KHO,
					"batch_no": LO,
					"use_serial_batch_fields": 1,
				}
			],
		}
	)
	dn.insert(ignore_permissions=True)
	if phan_bo:
		for o, sl in phan_bo:
			dn.append(
				"custom_phan_bo_vi_tri",
				{"dong_hang": dn.items[0].name, "vat_tu": ITEM, "so_lo": LO, "o": o, "so_luong": sl},
			)
		dn.save(ignore_permissions=True)
	return dn


class TestGhiSoTheoPhanBo(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.savepoint(DIEM_TEST)
		_vat_tu()
		_lo()
		# Thứ tự lấy hàng đặt TƯỜNG MINH: O_GAN=1 đứng trước O_XA=2, để FEFO phá
		# hoà giữa hai ô CÙNG lô (cùng hạn dùng) một cách xác định, không dựa vào
		# thứ tự tình cờ của câu truy vấn.
		_o(O_GAN, thu_tu=1)
		_o(O_XA, thu_tu=2)
		_nhap_kho(30)
		_chuyen_vao_o([(O_GAN, 20), (O_XA, 10)])

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point=DIEM_TEST)

	def test_ghi_so_theo_o_da_phan_bo_chu_khong_theo_fefo(self):
		"""Phân bổ vào ô mà FEFO KHÔNG chọn — chốt chịu lực của cả thiết kế."""
		dn = _phieu_giao(10, phan_bo=[(O_XA, 10)])
		dn.submit()

		dong = frappe.get_all(
			"Location Ledger Entry", {"chung_tu": dn.name}, ["o", "so_luong"]
		)
		self.assertEqual([(d.o, d.so_luong) for d in dong], [(O_XA, -10.0)])
		# Chốt âm: ô mà FEFO lẽ ra chọn KHÔNG bị đụng tới.
		self.assertEqual(so.ton_o(O_GAN, ITEM, LO), 20.0)
		self.assertEqual(so.ton_o(O_XA, ITEM, LO), 0.0)

	def test_khong_co_phan_bo_thi_van_chay_fefo_nhu_cu(self):
		"""Chốt âm cho đường CŨ: mọi chứng từ không qua trang lấy hàng phải y như trước."""
		dn = _phieu_giao(10)
		dn.submit()

		self.assertEqual(so.ton_o(O_GAN, ITEM, LO), 10.0, "FEFO phải lấy ở ô thu_tu_lay_hang nhỏ hơn")
		self.assertEqual(so.ton_o(O_XA, ITEM, LO), 10.0)

	def test_tong_phan_bo_lech_thi_chan_va_khong_ghi_dong_so_nao(self):
		dn = _phieu_giao(10, phan_bo=[(O_XA, 4)])
		# Minor 5 (vòng sửa 1): câu throw phải nêu rõ TÊN Ô, không chỉ số lượng.
		with self.assertRaisesRegex(frappe.ValidationError, f"phân bổ.*{O_XA}"):
			dn.submit()

		self.assertEqual(
			frappe.get_all("Location Ledger Entry", {"chung_tu": dn.name}),
			[],
			"chặn rồi thì không dòng sổ nào được sống sót",
		)

	def test_phan_bo_khong_khop_dong_hang_thi_chan(self):
		"""Critical 2 (vòng sửa 1): chứng từ CÓ bảng phân bổ nhưng không dòng nào
		khớp ĐÚNG dòng hàng đang ghi (amend đổi tên dòng, dòng Packed Item, ...)
		— phải CHẶN, không được âm thầm rơi về FEFO.

		SAU TASK 3: lớp kiểm sớm (`kiem_phan_bo_khi_luu`, gắn `validate`) đã tự
		mình đọc đúng cùng dữ liệu này và chặn ngay lúc LƯU — trước khi `submit()`
		có cơ hội chạy tới `hook_sle._phan_bo_da_khai`/"không dòng nào khớp" ở
		Task 2. Vì `validate` luôn chạy trước `on_submit` trong CÙNG một lệnh
		`submit()`, nhánh "không dòng nào khớp" của hook ghi sổ không còn đường
		nào chạm tới qua API tài liệu bình thường nữa — chỉ còn tới nếu có ai gọi
		thẳng `ghi_so_vi_tri`/`_phan_bo_da_khai` mà bỏ qua `validate` (không xảy
		ra trong luồng thật). Giữ bài test này lại để khẳng định KẾT QUẢ cuối
		(chặn, không ghi sổ, không rơi về FEFO) không đổi — chỉ đổi câu thông báo
		và điểm chặn, từ Task 2 sang Task 3.
		"""
		dn = frappe.get_doc(
			{
				"doctype": "Delivery Note",
				"company": CTY,
				"customer": KHACH,
				"posting_date": nowdate(),
				"items": [
					{
						"item_code": ITEM,
						"qty": 10,
						"rate": 5000,
						"warehouse": KHO,
						"batch_no": LO,
						"use_serial_batch_fields": 1,
					}
				],
			}
		)
		dn.insert(ignore_permissions=True)
		dn.append(
			"custom_phan_bo_vi_tri",
			{"dong_hang": "khong-ton-tai", "vat_tu": ITEM, "so_lo": LO, "o": O_XA, "so_luong": 10},
		)
		with self.assertRaisesRegex(frappe.ValidationError, "không thuộc phiếu này"):
			dn.save(ignore_permissions=True)

		self.assertEqual(
			frappe.get_all("Location Ledger Entry", {"chung_tu": dn.name}),
			[],
			"chặn rồi thì không dòng sổ nào được sống sót",
		)
		# FEFO KHÔNG được âm thầm chạy thay: cả hai ô đứng yên.
		self.assertEqual(so.ton_o(O_GAN, ITEM, LO), 20.0)
		self.assertEqual(so.ton_o(O_XA, ITEM, LO), 10.0)

	def test_phan_bo_vuot_ton_o_thi_chan_va_khong_ghi_dong_so_nao(self):
		"""Important 3 (vòng sửa 1): phân bổ nhiều hơn tồn THẬT của ô (ai đó lấy
		mất hàng giữa lúc quét và lúc duyệt) — phải CHẶN, và KHÔNG dòng sổ nào
		của phiếu bị chặn được sống sót (savepoint).

		SAU TASK 3: cùng lý do như bài trên — lớp kiểm sớm đọc đúng bộ đệm tồn
		(`ton_o`, cùng nguồn dữ liệu `hook_sle._chan_ton_am_phan_bo` sẽ đọc lại ở
		bước ghi sổ) nên luôn thấy thiếu tồn TRƯỚC KHI `submit()` kịp chạy tới
		nhánh ghi sổ có khoá dòng InnoDB của Task 2. Nhánh "không đủ hàng" của
		Task 2 giờ chỉ còn bắt được một kịch bản hẹp hơn nhiều: tồn bị rút mất
		GIỮA lúc lớp sớm kiểm tra và lúc dòng sổ thật sự được ghi trong CÙNG một
		lệnh submit — tức một giao dịch khác commit xen vào giữa hai bước đó,
		việc test tuần tự một luồng không dựng lại được. Giữ bài test này để
		khẳng định KẾT QUẢ cuối không đổi, đổi điểm chặn và câu thông báo sang
		Task 3.
		"""
		# Rút hợp lệ 5 khỏi O_XA trước, còn lại đúng 5.
		dn1 = _phieu_giao(5, phan_bo=[(O_XA, 5)])
		dn1.submit()
		self.assertEqual(so.ton_o(O_XA, ITEM, LO), 5.0)

		# Phân bổ tiếp 10 vào O_XA dù chỉ còn 5 — lớp sớm chặn ngay lúc LƯU dn2.
		with self.assertRaisesRegex(frappe.ValidationError, "chỉ còn"):
			_phieu_giao(10, phan_bo=[(O_XA, 10)])

		self.assertEqual(so.ton_o(O_XA, ITEM, LO), 5.0, "tồn O_XA không đổi sau khi dn2 bị chặn")

	def test_phan_bo_co_dong_khong_duong_thi_chan(self):
		"""Important 4 (vòng sửa 1): tổng ĐÚNG nhưng có dòng phân bổ <= 0 vẫn
		phải chặn — cặp (+15, -5) cho dòng cần 10 lọt qua phép so tổng.

		SAU TASK 3: lớp kiểm sớm có phép `so_luong <= 0` RIÊNG (không phải phép
		so tổng), nên nó chặn ngay lúc LƯU, trước khi `submit()` kịp chạy tới
		phép so tổng "không hợp lệ" của Task 2 — nhánh đó với input cụ thể này
		cũng thành không tới lượt qua API tài liệu bình thường, cùng lý do hai
		bài trên. Giữ bài test để khẳng định KẾT QUẢ cuối không đổi.
		"""
		with self.assertRaisesRegex(frappe.ValidationError, "phải lớn hơn 0"):
			_phieu_giao(10, phan_bo=[(O_GAN, 15), (O_XA, -5)])

		self.assertEqual(so.ton_o(O_GAN, ITEM, LO), 20.0)
		self.assertEqual(so.ton_o(O_XA, ITEM, LO), 10.0)

	def test_phan_bo_nhieu_o_cho_mot_dong(self):
		dn = _phieu_giao(25, phan_bo=[(O_XA, 10), (O_GAN, 15)])
		dn.submit()

		con = {(d.o): d.so_luong for d in frappe.get_all(
			"Location Balance", {"vat_tu": ITEM, "so_lo": LO}, ["o", "so_luong"]
		)}
		self.assertEqual(con.get(O_XA), 0.0)
		self.assertEqual(con.get(O_GAN), 5.0)

	def test_huy_phieu_giao_tra_hang_ve_dung_o_da_lay(self):
		"""`dao_theo_o_goc` tra theo dòng sổ đã ghi — không được rơi về CHUA-XEP."""
		dn = _phieu_giao(10, phan_bo=[(O_XA, 10)])
		dn.submit()
		dn.reload()
		dn.cancel()

		self.assertEqual(so.ton_o(O_XA, ITEM, LO), 10.0)
		chua_xep = frappe.db.get_value("Storage Location", {"kho": KHO, "la_o_chua_xep": 1})
		self.assertEqual(so.ton_o(chua_xep, ITEM, LO), 0.0)


class TestKiemSom(FrappeTestCase):
	"""Chặn ngay khi LƯU NHÁP — lớp người dùng thật sự nhìn thấy (spec §5).

	Hook là lưới an toàn cuối, nhưng nó chạy sau khi đã bấm Duyệt: báo ở đó thì
	người dùng chỉ thấy phiếu bật lỗi, không biết sửa dòng nào.
	"""

	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.savepoint(DIEM_TEST)
		_vat_tu()
		_lo()
		_o(O_GAN)
		_o(O_XA)
		_nhap_kho(30)
		_chuyen_vao_o([(O_GAN, 20), (O_XA, 10)])

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point=DIEM_TEST)

	def test_o_thuoc_kho_khac_bi_chan(self):
		o_khac = "9Y09090901"
		if not frappe.db.exists("Storage Location", o_khac):
			frappe.get_doc(
				{"doctype": "Storage Location", "ma_o": o_khac, "kho": "Hàng trả về - MYN"}
			).insert(ignore_permissions=True)
		with self.assertRaisesRegex(frappe.ValidationError, "không thuộc kho"):
			_phieu_giao(5, phan_bo=[(o_khac, 5)])

	def test_o_nhom_bi_chan(self):
		with self.assertRaisesRegex(frappe.ValidationError, "nút nhóm"):
			_phieu_giao(5, phan_bo=[("9L0101", 5)])

	def test_phan_bo_vuot_so_luong_dong_bi_chan(self):
		with self.assertRaisesRegex(frappe.ValidationError, "vượt"):
			_phieu_giao(5, phan_bo=[(O_GAN, 6)])

	def test_o_khong_du_ton_bi_chan(self):
		with self.assertRaisesRegex(frappe.ValidationError, "chỉ còn"):
			_phieu_giao(30, phan_bo=[(O_XA, 30)])

	def test_dong_hang_khong_thuoc_phieu_bi_chan(self):
		dn = _phieu_giao(5)
		dn.append(
			"custom_phan_bo_vi_tri",
			{"dong_hang": "khong-co-that", "vat_tu": ITEM, "so_lo": LO, "o": O_GAN, "so_luong": 5},
		)
		with self.assertRaisesRegex(frappe.ValidationError, "không thuộc phiếu"):
			dn.save(ignore_permissions=True)

	def test_phan_bo_dang_do_van_luu_nhap_duoc(self):
		"""Quét dở vẫn phải lưu được — nếu không thì không ai lấy hàng nhiều lượt được."""
		dn = _phieu_giao(20, phan_bo=[(O_GAN, 5)])
		self.assertEqual(len(dn.custom_phan_bo_vi_tri), 1)

	def test_amend_don_sach_phan_bo_cu(self):
		"""Bản amend là phiếu CHƯA ai đi lấy hàng lại.

		`frappe.copy_doc` — con đường amend thật cũng đi qua nó — chép cả bảng
		`custom_phan_bo_vi_tri` sang bản amend dù field không đặt `no_copy`
		(tham số mặc định của nó là `ignore_no_copy=True`), và các dòng chép
		sang đó còn giữ nguyên `dong_hang` trỏ về TÊN DÒNG HÀNG của phiếu GỐC —
		phiếu amend sinh dòng hàng MỚI khi insert nên không dòng nào còn khớp.
		Bảng lại read-only nên người dùng không tự xoá được: nếu hook không tự
		dọn, bản amend bị khoá lưu vĩnh viễn ngay từ lần lưu đầu tiên.
		"""
		dn = _phieu_giao(5, phan_bo=[(O_GAN, 5)])
		dn.submit()
		dn.reload()
		dn.cancel()

		amended = frappe.copy_doc(dn)
		amended.amended_from = dn.name
		# `frappe.copy_doc` chỉ xoá `docstatus` khi KHÔNG chạy trong test
		# (`frappe/__init__.py`: `if not local.flags.in_test: fields_to_clear
		# .append("docstatus")`) — dưới test, bản copy còn giữ docstatus=2 của
		# phiếu gốc đã huỷ, khiến `insert()` từ chối bước chuyển 0→2. Đường
		# amend thật (nút "Amend" trên desk) không đi qua nhánh test này nên
		# không dính bẫy đó; ở đây trả docstatus về 0 cho đúng ý nghĩa "bản nháp
		# mới", giống những gì client-side amend làm.
		amended.docstatus = 0
		amended.insert(ignore_permissions=True)
		amended.reload()

		self.assertEqual(amended.custom_phan_bo_vi_tri, [])

		# Quét dở KHÔNG bị dọn tiếp ở những lần lưu SAU lần insert đầu tiên —
		# nếu không thủ kho quét lại trên bản amend xong lưu là mất trắng.
		amended.append(
			"custom_phan_bo_vi_tri",
			{
				"dong_hang": amended.items[0].name,
				"vat_tu": ITEM,
				"so_lo": LO,
				"o": O_GAN,
				"so_luong": 5,
			},
		)
		amended.save(ignore_permissions=True)
		amended.reload()

		self.assertEqual(len(amended.custom_phan_bo_vi_tri), 1)

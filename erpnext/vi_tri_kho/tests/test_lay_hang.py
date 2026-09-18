"""Lấy hàng theo phân bổ — sổ vị trí phải trừ ĐÚNG ô thủ kho đã quét.

Bài chịu lực của cả thiết kế là `test_ghi_so_theo_o_da_phan_bo_chu_khong_theo_fefo`:
nó phân bổ vào ô mà FEFO KHÔNG chọn. Thiếu chốt đó thì một cài đặt bỏ qua phân bổ
và cứ chạy FEFO vẫn xanh, vì cả hai đường đều cho ra tổng đúng.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt, nowdate

from erpnext.vi_tri_kho.vitri import hook_sle, so

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
		Task 2.

		SỬA (vòng sửa 1, Important — review điều phối): docstring bản trước ở
		đây khẳng định QUÁ RỘNG rằng nhánh "không dòng nào khớp" của hook ghi sổ
		"không còn đường nào chạm tới qua API tài liệu bình thường nữa" — SAI.
		Điều đó chỉ đúng cho ĐÚNG kịch bản của bài này: một `dong_hang` không
		khớp tên bất kỳ dòng nào trên CHÍNH document (kể cả ca "amend đổi tên
		dòng hàng" — lớp sớm tự dọn/tự chặn, xem `test_amend_don_sach_phan_bo_cu`).
		Nhánh đó VẪN SỐNG qua API thường cho hai ca khác mà lớp sớm không có
		cách nào thấy — dòng Product Bundle (`voucher_detail_no` là tên dòng
		Packed Item, không nằm trong `custom_phan_bo_vi_tri`) và đường mất chiều
		lô của `tach_theo_lo` lúc huỷ (SLE đảo dấu mang `so_lo=None`) — xem
		docstring `hook_sle._phan_bo_da_khai` (đoạn "TASK 3"). Hai ca đó CHƯA có
		bài test tích hợp trực tiếp. Giữ bài NÀY lại để khẳng định KẾT QUẢ cuối
		cho kịch bản CỦA NÓ (chặn, không ghi sổ, không rơi về FEFO) không đổi —
		chỉ đổi câu thông báo và điểm chặn, từ Task 2 sang Task 3.
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
		Task 2 giờ chỉ còn bắt được một kịch bản hẹp hơn nhiều qua API tài liệu
		THƯỜNG: tồn bị rút mất GIỮA lúc lớp sớm kiểm tra và lúc dòng sổ thật sự
		được ghi trong CÙNG một lệnh submit — tức một giao dịch khác commit xen
		vào giữa hai bước đó, việc test tuần tự một luồng không dựng lại được
		qua `.submit()`. Bài này giữ lại để khẳng định KẾT QUẢ cuối cho kịch bản
		CỦA NÓ (chặn ngay lúc lưu) không đổi.

		Cơ chế ghi-rồi-đọc-lại-rồi-rollback (`_chan_ton_am_phan_bo`) mà bài này
		từng là bài DUY NHẤT phủ tới thì KHÔNG mất — được khoá lại riêng, bằng
		cách gọi thẳng hàm nội bộ bỏ qua `validate`, ở
		`TestKiemSom.test_ghi_roi_rollback_khi_phan_bo_vuot_ton_thuc` (vòng sửa
		1, Critical).
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
		phép so tổng "không hợp lệ" của Task 2. Khác với bài
		`test_phan_bo_khong_khop_dong_hang_thi_chan`, ở ĐÂY điều kiện chỉ phụ
		thuộc giá trị `so_luong` của chính dòng phân bổ — không có ca nào lách
		được lớp sớm qua API tài liệu thường (không có "Product Bundle" hay
		"mất chiều lô" tương đương). Nhánh "không hợp lệ" của Task 2 vì vậy trở
		thành lưới an toàn thuần tuý cho đường ghi thẳng vào bảng, bỏ qua
		`validate` (xem docstring `hook_sle._phan_bo_da_khai`, đoạn "TASK 3" thứ
		hai) — CHƯA có bài test gọi trực tiếp hàm nội bộ để khoá riêng ca đó.
		Giữ bài NÀY để khẳng định KẾT QUẢ cuối cho đường API thường không đổi.
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

	def test_hai_dong_hang_cung_o_vuot_ton_bi_chan(self):
		"""Important (vòng sửa 1, review điều phối): `ton_o(o, vat_tu, so_lo)`
		tính tồn theo (Ô, vật tư, lô) — KHÔNG theo dòng hàng. Hai DÒNG HÀNG khác
		nhau nhưng cùng vật tư/lô (khác đơn giá, khác đơn bán gốc — chuyện
		thường) cùng phân bổ vào MỘT ô phải bị chặn khi TỔNG của cả hai vượt
		tồn ô, dù mỗi dòng riêng lẻ không vượt số lượng của chính nó (15 và 15,
		ô chỉ có 20). Bản sửa trước gộp nhầm theo (dòng hàng, lô, ô) nên mỗi
		dòng hàng tự so với tồn ĐẦY ĐỦ của ô, bỏ lọt over-draw chung — xem chú
		thích tại `theo_o` trong `lay_hang.kiem_phan_bo_khi_luu`.
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
						"qty": 15,
						"rate": 5000,
						"warehouse": KHO,
						"batch_no": LO,
						"use_serial_batch_fields": 1,
					},
					{
						"item_code": ITEM,
						"qty": 15,
						"rate": 6000,
						"warehouse": KHO,
						"batch_no": LO,
						"use_serial_batch_fields": 1,
					},
				],
			}
		)
		dn.insert(ignore_permissions=True)
		dn.append(
			"custom_phan_bo_vi_tri",
			{"dong_hang": dn.items[0].name, "vat_tu": ITEM, "so_lo": LO, "o": O_GAN, "so_luong": 15},
		)
		dn.append(
			"custom_phan_bo_vi_tri",
			{"dong_hang": dn.items[1].name, "vat_tu": ITEM, "so_lo": LO, "o": O_GAN, "so_luong": 15},
		)
		with self.assertRaisesRegex(frappe.ValidationError, f"{O_GAN}.*chỉ còn"):
			dn.save(ignore_permissions=True)

	def test_ghi_roi_rollback_khi_phan_bo_vuot_ton_thuc(self):
		"""Critical (vòng sửa 1, review điều phối): khoá lại cơ chế
		ghi-rồi-đọc-lại-rồi-rollback của `hook_sle._chan_ton_am_phan_bo`
		(Important 3, Task 2) — cơ chế chống race hai người cùng rút một ô.

		`test_phan_bo_vuot_ton_o_thi_chan_va_khong_ghi_dong_so_nao` (Task 2)
		từng là bài DUY NHẤT chạm tới cơ chế này, qua `.submit()`. Sau Task 3,
		lớp kiểm sớm đọc CÙNG một `ton_o` TRƯỚC khi ghi, và `validate` chạy lại
		ở MỌI lần save — kể cả lần bên trong `.submit()` — nên bất kỳ dữ liệu
		nào dựng qua `.save()`/`.submit()` bình thường mà đủ điều kiện chặn ở
		đây cũng đã bị lớp sớm chặn TRƯỚC đó rồi. Đã THỬ dựng lại theo hướng
		"lưu phiếu hợp lệ trước, rút tồn ở ô đó bằng phiếu khác, rồi mới
		submit": không cứu được — `validate` chạy lại ngay đầu `.submit()` và
		thấy tồn mới đã bị rút, chặn sớm với "chỉ còn" chứ không rơi được
		xuống `_chan_ton_am_phan_bo`. Bài này vì vậy gọi THẲNG
		`hook_sle._ghi_mot_phan` — bỏ qua `validate` hoàn toàn — mô phỏng đúng
		ca một giao dịch KHÁC (ở đây: một phiếu chuyển vị trí) rút mất hàng ở ô
		đó SAU KHI lớp sớm của phiếu giao đã kiểm xong, ngay trước lúc dòng sổ
		thật sự được ghi.
		"""
		dn = _phieu_giao(5, phan_bo=[(O_XA, 5)])  # O_XA đang có 10 — validate xanh lúc lưu.

		# "Ai đó" rút bớt O_XA giữa lúc lưu nháp và lúc duyệt — một phiếu
		# chuyển vị trí THẬT, không đụng gì tới `dn` hay `validate` của nó.
		chuyen = frappe.get_doc(
			{
				"doctype": "Location Transfer",
				"kho": KHO,
				"ngay": nowdate(),
				"items": [{"vat_tu": ITEM, "so_lo": LO, "tu_o": O_XA, "den_o": O_GAN, "so_luong": 8}],
			}
		)
		chuyen.insert(ignore_permissions=True)
		chuyen.submit()
		self.assertEqual(so.ton_o(O_XA, ITEM, LO), 2.0)

		# Stock Ledger Entry dựng tay: `sle.name` phải trỏ một bản ghi CÓ THẬT
		# (Location Ledger Entry.sle là Link nghiêm ngặt, không ignore_links) —
		# mượn tên SLE thật của `_nhap_kho` trong setUp, các field còn lại tự
		# khai để trỏ đúng dòng hàng/phân bổ của `dn`.
		sle_that = frappe.get_all(
			"Stock Ledger Entry", {"item_code": ITEM, "warehouse": KHO}, ["name"], limit=1
		)[0]
		sle_gia = frappe._dict(
			name=sle_that.name,
			warehouse=KHO,
			item_code=ITEM,
			voucher_type="Delivery Note",
			voucher_no=dn.name,
			voucher_detail_no=dn.items[0].name,
			posting_date=nowdate(),
			posting_time="00:00:00",
			company=CTY,
		)

		with self.assertRaisesRegex(frappe.ValidationError, "không đủ hàng"):
			hook_sle._ghi_mot_phan(sle_gia, LO, -5)

		self.assertEqual(
			frappe.get_all("Location Ledger Entry", {"chung_tu": dn.name}),
			[],
			"rollback rồi thì không dòng sổ nào của dn được sống sót",
		)
		self.assertEqual(so.ton_o(O_XA, ITEM, LO), 2.0, "tồn O_XA không đổi sau rollback")


class TestDocChoTrang(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.savepoint(DIEM_TEST)
		for ma in (LO, O_GAN, O_XA):
			frappe.cache().delete_value(f"erpnext:barcode_scan:{ma}")
		_vat_tu()
		_lo()
		_o(O_GAN)
		_o(O_XA)
		_nhap_kho(30)
		_chuyen_vao_o([(O_GAN, 20), (O_XA, 10)])
		self.dn = _phieu_giao(12)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point=DIEM_TEST)

	def test_danh_sach_hien_phieu_nhap_va_tien_do(self):
		from erpnext.vi_tri_kho.vitri.lay_hang import danh_sach_phieu_giao

		# QUYẾT ĐỊNH 18/09/2026: `danh_sach_phieu_giao` trả DICT (khuôn
		# `xep.phieu_xep_dang_lam`), không phải list — đọc khoá "phieu".
		ds = {d["name"]: d for d in danh_sach_phieu_giao(KHO)["phieu"]}
		self.assertIn(self.dn.name, ds)
		self.assertEqual(ds[self.dn.name]["can_lay"], 12.0)
		self.assertEqual(ds[self.dn.name]["da_lay"], 0.0)

	def test_mo_phieu_ra_o_nen_lay_theo_fefo(self):
		from erpnext.vi_tri_kho.vitri.lay_hang import mo_phieu_giao

		p = mo_phieu_giao(self.dn.name)
		self.assertEqual(len(p["dong"]), 1)
		d = p["dong"][0]
		self.assertEqual((d["vat_tu"], d["so_lo"], d["can_lay"]), (ITEM, LO, 12.0))
		# 12 lấy hết ô đứng trước (20) → chỉ một ô được gợi ý.
		self.assertEqual([o["o"] for o in d["o_nen_lay"]], [O_GAN])

	def test_quet_lo_cua_phieu_va_quet_o(self):
		from erpnext.vi_tri_kho.vitri.lay_hang import quet_de_lay

		self.assertEqual(quet_de_lay(self.dn.name, LO)["loai"], "lo")
		self.assertEqual(quet_de_lay(self.dn.name, O_GAN)["loai"], "o")
		self.assertEqual(quet_de_lay(self.dn.name, "9L-KHONG-CO-GI")["loai"], None)

	def test_quet_lo_khac_cung_mat_hang_bao_loai_lo_khac_kem_hsd(self):
		from erpnext.vi_tri_kho.vitri.lay_hang import quet_de_lay

		lo_khac = "9L-LO-LAY-02"
		if not frappe.db.exists("Batch", lo_khac):
			frappe.get_doc(
				{"doctype": "Batch", "batch_id": lo_khac, "item": ITEM, "expiry_date": "2030-12-31"}
			).insert(ignore_permissions=True)
		frappe.cache().delete_value(f"erpnext:barcode_scan:{lo_khac}")

		kq = quet_de_lay(self.dn.name, lo_khac)
		self.assertEqual(kq["loai"], "lo_khac")
		self.assertEqual(kq["so_lo"], lo_khac)
		self.assertTrue(kq["han_xa_hon"], "lô 2030 xa hơn lô 2029 của phiếu")

	def test_khong_co_vai_tro_kho_thi_bi_chan(self):
		from erpnext.vi_tri_kho.vitri.lay_hang import danh_sach_phieu_giao

		ten = "lay-hang-khong-quyen@mo-phong.local"
		if not frappe.db.exists("User", ten):
			frappe.get_doc(
				{"doctype": "User", "email": ten, "first_name": "Lay", "send_welcome_email": 0, "roles": []}
			).insert(ignore_permissions=True)
		frappe.set_user(ten)
		with self.assertRaises(frappe.PermissionError):
			danh_sach_phieu_giao(KHO)

	def test_quet_phieu_khong_ton_tai_khong_nem_loi(self):
		"""Critical (vòng sửa 1, review điều phối): `get_doc` từng nằm NGOÀI
		try — phiếu bị huỷ/xoá giữa lúc thủ kho đang quét thì `DoesNotExistError`
		văng thẳng ra màn hình, phá lời hứa "quét nhầm không bao giờ nổ"."""
		from erpnext.vi_tri_kho.vitri.lay_hang import quet_de_lay

		self.assertEqual(quet_de_lay("KHONG-TON-TAI-PHIEU-GIAO-9999", LO), {"loai": None})

	def test_kho_khong_bat_vi_tri_bi_chan(self):
		"""Important 2 (vòng sửa 1, review điều phối): endpoint whitelisted gọi
		thẳng được — `kho` tuỳ ý (chưa bật quản lý vị trí) không được lọt qua."""
		from erpnext.vi_tri_kho.vitri.lay_hang import danh_sach_phieu_giao

		kho_khac = "Hàng trả về - MYN"
		self.assertFalse(frappe.db.get_value("Warehouse", kho_khac, "custom_quan_ly_vi_tri"))
		with self.assertRaisesRegex(frappe.ValidationError, "chưa bật quản lý vị trí"):
			danh_sach_phieu_giao(kho_khac)

	def test_user_permission_cong_ty_khac_chan_mo_phieu_va_quet(self):
		"""Important 1 (vòng sửa 1, review điều phối): `frappe.get_doc` KHÔNG
		tự chạy `has_permission` — site thật có nhiều Company, User Permission
		theo Company bị xuyên thủng nếu không gọi `doc.check_permission("read")`
		tay. Dựng đúng ca User Permission (đã đo: `check_permission("read")`
		ném `PermissionError` khi user bị giới hạn sang Company khác — xem
		task-4-report.md), không dùng đường vòng "user không vai trò"."""
		from erpnext.vi_tri_kho.vitri.lay_hang import mo_phieu_giao, quet_de_lay

		ten = "lay-hang-cong-ty-khac@mo-phong.local"
		cong_ty_khac = "Miyano"
		if not frappe.db.exists("User", ten):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": ten,
					"first_name": "Lay Cong Ty Khac",
					"send_welcome_email": 0,
					"roles": [{"role": "Stock User"}],
				}
			).insert(ignore_permissions=True)
		if not frappe.db.exists(
			"User Permission", {"user": ten, "allow": "Company", "for_value": cong_ty_khac}
		):
			frappe.get_doc(
				{"doctype": "User Permission", "user": ten, "allow": "Company", "for_value": cong_ty_khac}
			).insert(ignore_permissions=True)

		frappe.set_user(ten)
		with self.assertRaises(frappe.PermissionError):
			mo_phieu_giao(self.dn.name)
		with self.assertRaises(frappe.PermissionError):
			quet_de_lay(self.dn.name, LO)

	def test_danh_sach_loc_theo_quyen_khong_hien_phieu_cong_ty_khac(self):
		"""Bổ sung vòng sửa 1 (review điều phối, sau Important 1): bản thân
		DANH SÁCH đã là rò rỉ nếu hiện tên phiếu/khách hàng/số lượng của một
		phiếu mà `mo_phieu_giao`/`quet_de_lay` sau đó sẽ từ chối mở — còn
		khiến thủ kho chạm vào rồi ăn lỗi quyền không hiểu vì sao.

		Dùng lại đúng ca User Permission theo Company đã dựng ở
		`test_user_permission_cong_ty_khac_chan_mo_phieu_va_quet` (đã đo bằng
		console rằng `check_permission`/`has_permission` phân biệt đúng theo
		Company trên site này) — không cần đường vòng "user không vai trò".
		"""
		from erpnext.vi_tri_kho.vitri.lay_hang import danh_sach_phieu_giao

		ten = "lay-hang-cong-ty-khac@mo-phong.local"
		cong_ty_khac = "Miyano"
		if not frappe.db.exists("User", ten):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": ten,
					"first_name": "Lay Cong Ty Khac",
					"send_welcome_email": 0,
					"roles": [{"role": "Stock User"}],
				}
			).insert(ignore_permissions=True)
		if not frappe.db.exists(
			"User Permission", {"user": ten, "allow": "Company", "for_value": cong_ty_khac}
		):
			frappe.get_doc(
				{"doctype": "User Permission", "user": ten, "allow": "Company", "for_value": cong_ty_khac}
			).insert(ignore_permissions=True)

		# Administrator vẫn thấy phiếu bình thường trước khi đổi user — chốt
		# rằng phiếu THẬT SỰ nằm trong kết quả khi không bị giới hạn quyền.
		ten_phieu = {d["name"] for d in danh_sach_phieu_giao(KHO)["phieu"]}
		self.assertIn(self.dn.name, ten_phieu)

		frappe.set_user(ten)
		ten_phieu_bi_gioi_han = {d["name"] for d in danh_sach_phieu_giao(KHO)["phieu"]}
		self.assertNotIn(self.dn.name, ten_phieu_bi_gioi_han)

	def test_quet_lo_khac_nhieu_dong_cung_mat_hang_chon_theo_quy_tac(self):
		"""Important 3 (vòng sửa 1, review điều phối): `cung_hang[0]` từng chọn
		tuỳ tiện khi phiếu có nhiều dòng cùng mặt hàng khác lô. Không truyền
		`dong_hang`: phải chọn dòng CHƯA lấy đủ (không phải dòng[0], vốn đã lấy
		đủ trong bài này). Truyền `dong_hang`: ép đúng dòng chỉ định."""
		from erpnext.vi_tri_kho.vitri.lay_hang import quet_de_lay

		lo2 = "9L-LO-LAY-03"
		lo3 = "9L-LO-LAY-04"
		for lo, han in ((lo2, "2029-06-30"), (lo3, "2030-12-31")):
			if not frappe.db.exists("Batch", lo):
				frappe.get_doc(
					{"doctype": "Batch", "batch_id": lo, "item": ITEM, "expiry_date": han}
				).insert(ignore_permissions=True)
			frappe.cache().delete_value(f"erpnext:barcode_scan:{lo}")

		dn2 = frappe.get_doc(
			{
				"doctype": "Delivery Note",
				"company": CTY,
				"customer": KHACH,
				"posting_date": nowdate(),
				"items": [
					{
						"item_code": ITEM,
						"qty": 5,
						"rate": 5000,
						"warehouse": KHO,
						"batch_no": LO,
						"use_serial_batch_fields": 1,
					},
					{
						"item_code": ITEM,
						"qty": 3,
						"rate": 5000,
						"warehouse": KHO,
						"batch_no": lo2,
						"use_serial_batch_fields": 1,
					},
				],
			}
		)
		dn2.insert(ignore_permissions=True)
		# Dòng đầu (LO) đã lấy ĐỦ — không còn là ứng viên hợp lệ khi không chỉ
		# định dong_hang.
		dn2.append(
			"custom_phan_bo_vi_tri",
			{"dong_hang": dn2.items[0].name, "vat_tu": ITEM, "so_lo": LO, "o": O_GAN, "so_luong": 5},
		)
		dn2.save(ignore_permissions=True)

		# Không truyền dong_hang: chọn dòng CHƯA lấy đủ (dòng lô2), không phải
		# dòng[0] (đúng bug Important 3).
		kq = quet_de_lay(dn2.name, lo3)
		self.assertEqual(kq["loai"], "lo_khac")
		self.assertEqual(kq["dong_hang"], dn2.items[1].name)
		self.assertEqual(kq["so_lo_dang_chot"], lo2)
		self.assertTrue(kq["nhieu_dong"])
		self.assertTrue(kq["han_xa_hon"], "lô 2030 xa hơn lô 2029-06-30")

		# Truyền dong_hang: ép đúng dòng đã chỉ định, kể cả dòng đã lấy đủ.
		kq2 = quet_de_lay(dn2.name, lo3, dong_hang=dn2.items[0].name)
		self.assertEqual(kq2["dong_hang"], dn2.items[0].name)
		self.assertEqual(kq2["so_lo_dang_chot"], LO)

	def test_han_xa_hon_lo_khong_han_dung_luon_xa_hon(self):
		"""Important 4 (vòng sửa 1, review điều phối): `bool(a and b and a > b)`
		trả `False` sai nghĩa khi một vế `None` — lô KHÔNG hạn phải bị coi là
		"xa hơn" MỌI lô có hạn."""
		from erpnext.vi_tri_kho.vitri.lay_hang import quet_de_lay

		lo_khong_han = "9L-LO-LAY-05"
		if not frappe.db.exists("Batch", lo_khong_han):
			frappe.get_doc({"doctype": "Batch", "batch_id": lo_khong_han, "item": ITEM}).insert(
				ignore_permissions=True
			)
		frappe.cache().delete_value(f"erpnext:barcode_scan:{lo_khong_han}")

		kq = quet_de_lay(self.dn.name, lo_khong_han)
		self.assertEqual(kq["loai"], "lo_khac")
		self.assertIsNone(kq["hsd"])
		self.assertTrue(kq["han_xa_hon"], "lô không hạn phải coi là xa hơn lô 2029 có hạn")


class TestGhiChoTrang(FrappeTestCase):
	def setUp(self):
		from erpnext.vi_tri_kho.vitri.lay_hang import _KHOA_CHOT_THIEU

		frappe.set_user("Administrator")
		frappe.db.savepoint(DIEM_TEST)
		_vat_tu()
		_lo()
		_o(O_GAN)
		_o(O_XA)
		_nhap_kho(30)
		_chuyen_vao_o([(O_GAN, 20), (O_XA, 10)])
		self.dn = _phieu_giao(12)
		self.dong = self.dn.items[0].name
		# Rollback bằng savepoint không đụng tới Redis — cờ chốt-thiếu của một
		# lần chạy trước, dưới TÊN PHIẾU cùng series bị dựng lại, có thể còn
		# sống sót và làm bài sau đọc nhầm cờ của bài trước.
		frappe.cache().delete_value(_KHOA_CHOT_THIEU(self.dn.name))

	def tearDown(self):
		from erpnext.vi_tri_kho.vitri.lay_hang import _KHOA_CHOT_THIEU

		frappe.set_user("Administrator")
		frappe.cache().delete_value(_KHOA_CHOT_THIEU(self.dn.name))
		frappe.db.rollback(save_point=DIEM_TEST)

	def test_ghi_da_lay_luu_ngay_len_phieu(self):
		from erpnext.vi_tri_kho.vitri.lay_hang import ghi_da_lay

		p = ghi_da_lay(self.dn.name, self.dong, LO, O_GAN, 5)
		self.assertEqual(p["dong"][0]["da_lay"], 5.0)
		doc = frappe.get_doc("Delivery Note", self.dn.name)
		self.assertEqual(len(doc.custom_phan_bo_vi_tri), 1)
		self.assertEqual(doc.custom_phan_bo_vi_tri[0].nguoi_lay, frappe.session.user)

	def test_quet_lai_cung_o_thi_cong_don(self):
		from erpnext.vi_tri_kho.vitri.lay_hang import ghi_da_lay

		ghi_da_lay(self.dn.name, self.dong, LO, O_GAN, 5)
		p = ghi_da_lay(self.dn.name, self.dong, LO, O_GAN, 3)
		self.assertEqual(len(p["dong"][0]["da_lay_o"]), 1)
		self.assertEqual(p["dong"][0]["da_lay"], 8.0)

	def test_bo_dong_da_lay(self):
		from erpnext.vi_tri_kho.vitri.lay_hang import bo_dong_da_lay, ghi_da_lay

		p = ghi_da_lay(self.dn.name, self.dong, LO, O_GAN, 5)
		ten = p["dong"][0]["da_lay_o"][0]["name"]
		p2 = bo_dong_da_lay(self.dn.name, ten)
		self.assertEqual(p2["dong"][0]["da_lay"], 0.0)

	def test_bo_dong_khong_ton_tai_bi_chan(self):
		"""Một phép 'bỏ' tưởng thành công mà thực ra không làm gì (hai tab
		cùng bấm, hoặc bấm hai lần) là đúng loại lỗi module này phải tránh."""
		from erpnext.vi_tri_kho.vitri.lay_hang import bo_dong_da_lay

		with self.assertRaisesRegex(frappe.ValidationError, "không tồn tại"):
			bo_dong_da_lay(self.dn.name, "khong-co-dong-nay")

	def test_doi_lo_sua_dong_phieu_giao(self):
		from erpnext.vi_tri_kho.vitri.lay_hang import doi_lo

		lo2 = "9L-LO-LAY-03"
		if not frappe.db.exists("Batch", lo2):
			frappe.get_doc(
				{"doctype": "Batch", "batch_id": lo2, "item": ITEM, "expiry_date": "2028-01-31"}
			).insert(ignore_permissions=True)
		doi_lo(self.dn.name, self.dong, lo2)
		self.assertEqual(frappe.db.get_value("Delivery Note Item", self.dong, "batch_no"), lo2)

	def test_doi_lo_sang_lo_khong_ton_tai_bi_chan(self):
		from erpnext.vi_tri_kho.vitri.lay_hang import doi_lo

		with self.assertRaisesRegex(frappe.ValidationError, "không tồn tại"):
			doi_lo(self.dn.name, self.dong, "9L-LO-KHONG-CO-THAT")

	def test_hoan_tat_duyet_phieu_va_tru_dung_o(self):
		from erpnext.vi_tri_kho.vitri.lay_hang import ghi_da_lay, hoan_tat

		ghi_da_lay(self.dn.name, self.dong, LO, O_XA, 10)
		ghi_da_lay(self.dn.name, self.dong, LO, O_GAN, 2)
		kq = hoan_tat(self.dn.name)

		self.assertEqual(kq["name"], self.dn.name)
		self.assertEqual(frappe.db.get_value("Delivery Note", self.dn.name, "docstatus"), 1)
		self.assertEqual(so.ton_o(O_XA, ITEM, LO), 0.0)
		self.assertEqual(so.ton_o(O_GAN, ITEM, LO), 18.0)

	def test_chot_thieu_ha_so_luong_dong_va_ghi_chu(self):
		"""Ghi chú "lấy thiếu" đi vào COMMENT của phiếu, KHÔNG vào một field nào
		hiện trên bản in (`instructions`) — quyết định điều phối 18/09/2026:
		đây là chuyện nội bộ kho, in ra bản giao cho khách là lộ chuyện kho."""
		from erpnext.vi_tri_kho.vitri.lay_hang import chot_thieu, ghi_da_lay, hoan_tat

		ghi_da_lay(self.dn.name, self.dong, LO, O_GAN, 7)
		chot_thieu(self.dn.name, self.dong)
		hoan_tat(self.dn.name)

		doc = frappe.get_doc("Delivery Note", self.dn.name)
		self.assertEqual(flt(doc.items[0].qty), 7.0)
		self.assertFalse((doc.instructions or "").strip(), "instructions không được đụng tới")
		binh_luan = frappe.get_all(
			"Comment",
			filters={
				"reference_doctype": "Delivery Note",
				"reference_name": self.dn.name,
				"comment_type": "Comment",
			},
			pluck="content",
		)
		self.assertTrue(
			any("Lấy thiếu" in c for c in binh_luan), f"không thấy ghi chú lấy thiếu trong {binh_luan}"
		)
		self.assertEqual(so.ton_o(O_GAN, ITEM, LO), 13.0)

	def test_hoan_tat_khong_lay_thieu_thi_khong_co_comment(self):
		"""Đối chứng: phiếu duyệt trọn vẹn (không chốt thiếu dòng nào) thì
		`hoan_tat` không được tự bịa ra một comment nào cả."""
		from erpnext.vi_tri_kho.vitri.lay_hang import ghi_da_lay, hoan_tat

		ghi_da_lay(self.dn.name, self.dong, LO, O_GAN, 12)
		hoan_tat(self.dn.name)

		binh_luan = frappe.get_all(
			"Comment",
			filters={
				"reference_doctype": "Delivery Note",
				"reference_name": self.dn.name,
				"comment_type": "Comment",
			},
		)
		self.assertEqual(binh_luan, [])

	def test_hoan_tat_khi_chua_lay_du_bi_chan(self):
		from erpnext.vi_tri_kho.vitri.lay_hang import ghi_da_lay, hoan_tat

		ghi_da_lay(self.dn.name, self.dong, LO, O_GAN, 5)
		with self.assertRaisesRegex(frappe.ValidationError, "chưa lấy đủ"):
			hoan_tat(self.dn.name)
		self.assertEqual(frappe.db.get_value("Delivery Note", self.dn.name, "docstatus"), 0)
		self.assertEqual(
			frappe.get_all(
				"Comment", filters={"reference_doctype": "Delivery Note", "reference_name": self.dn.name}
			),
			[],
			"hoan_tat bị chặn TRƯỚC savepoint — không được để lại comment nào",
		)

	def test_hoan_tat_lay_thieu_nhung_hong_o_hook_ghi_so_thi_khong_co_comment(self):
		"""Chốt thiếu XONG, nhưng ghi sổ hỏng (savepoint phải rollback toàn bộ,
		xem `test_duyet_hong_that_o_hook_ghi_so_thi_docstatus_van_ve_0`) — vì
		`add_comment` được gọi SAU `doc.submit()` trong CÙNG try/except, phiếu
		hỏng không được để lại một comment "lấy thiếu" mồ côi nào."""
		from unittest.mock import patch

		from erpnext.vi_tri_kho.vitri.lay_hang import chot_thieu, ghi_da_lay, hoan_tat

		ghi_da_lay(self.dn.name, self.dong, LO, O_GAN, 7)
		chot_thieu(self.dn.name, self.dong)

		with patch(
			"erpnext.vi_tri_kho.vitri.hook_sle._ghi_mot_phan",
			side_effect=frappe.ValidationError("lỗi giả lập ghi sổ vị trí"),
		):
			with self.assertRaises(frappe.ValidationError):
				hoan_tat(self.dn.name)

		self.assertEqual(frappe.db.get_value("Delivery Note", self.dn.name, "docstatus"), 0)
		self.assertEqual(flt(frappe.db.get_value("Delivery Note Item", self.dong, "qty")), 12.0)
		self.assertEqual(
			frappe.get_all(
				"Comment", filters={"reference_doctype": "Delivery Note", "reference_name": self.dn.name}
			),
			[],
		)

	def test_duyet_hong_o_lop_kiem_som_thi_phieu_con_nhap(self):
		"""Ai đó chuyển hàng khỏi ô sau khi đã quét — `validate` (lớp kiểm sớm,
		Task 3) bắt được NGAY, TRƯỚC khi `submit()` kịp ghi `docstatus=1`
		xuống CSDL. Bài này khoá kết quả cuối (nháp, phân bổ còn nguyên) cho
		đúng kịch bản của nó, nhưng KHÔNG đo được savepoint của `hoan_tat` có
		tác dụng hay không — xem
		`test_duyet_hong_that_o_hook_ghi_so_thi_docstatus_van_ve_0` ngay dưới
		đây cho bài đo ĐÚNG chỗ savepoint phải cứu (lỗi xảy ra TRONG
		`on_submit`, SAU khi `docstatus=1` đã ghi xuống CSDL)."""
		from erpnext.vi_tri_kho.vitri.lay_hang import ghi_da_lay, hoan_tat

		ghi_da_lay(self.dn.name, self.dong, LO, O_GAN, 12)
		_chuyen_vao_o_khac = frappe.get_doc(
			{
				"doctype": "Location Transfer",
				"kho": KHO,
				"ngay": nowdate(),
				"items": [
					{"vat_tu": ITEM, "so_lo": LO, "tu_o": O_GAN, "den_o": O_XA, "so_luong": 20}
				],
			}
		)
		_chuyen_vao_o_khac.insert(ignore_permissions=True)
		_chuyen_vao_o_khac.submit()

		with self.assertRaises(frappe.ValidationError):
			hoan_tat(self.dn.name)
		doc = frappe.get_doc("Delivery Note", self.dn.name)
		self.assertEqual(doc.docstatus, 0)
		self.assertEqual(len(doc.custom_phan_bo_vi_tri), 1)

	def test_duyet_hong_that_o_hook_ghi_so_thi_docstatus_van_ve_0(self):
		"""Chốt chịu lực THẬT của savepoint quanh `submit()` trong `hoan_tat`.

		`Document.submit()` ghi `docstatus=1` xuống CSDL TRƯỚC khi `on_submit`
		chạy (`_save()`: `run_before_save_methods()` — tức `validate` — chạy
		trong lúc `docstatus` MỚI đổi TRONG BỘ NHỚ, RỒI `db_update()` ghi
		xuống CSDL, RỒI MỚI `run_post_save_methods()` gọi `on_submit`). Mock
		thẳng điểm ghi sổ thật (`hook_sle._ghi_mot_phan`, chạy TRONG
		`on_submit`, khi `Delivery Note` cập nhật sổ kho) để buộc lỗi xảy ra
		SAU khi `docstatus=1` chắc chắn đã nằm trong CSDL — đúng chỗ mà thiếu
		savepoint sẽ để lại một phiếu "đã duyệt" không một dòng sổ nào."""
		from unittest.mock import patch

		from erpnext.vi_tri_kho.vitri.lay_hang import ghi_da_lay, hoan_tat

		ghi_da_lay(self.dn.name, self.dong, LO, O_GAN, 12)

		with patch(
			"erpnext.vi_tri_kho.vitri.hook_sle._ghi_mot_phan",
			side_effect=frappe.ValidationError("lỗi giả lập ghi sổ vị trí"),
		):
			with self.assertRaises(frappe.ValidationError):
				hoan_tat(self.dn.name)

		self.assertEqual(frappe.db.get_value("Delivery Note", self.dn.name, "docstatus"), 0)
		doc = frappe.get_doc("Delivery Note", self.dn.name)
		self.assertEqual(len(doc.custom_phan_bo_vi_tri), 1)

	def test_hoan_tat_hai_dong_chi_lay_mot_bi_chan_dung_dong(self):
		"""QUYẾT ĐỊNH 18/09/2026 (mở rộng brief, điều phối chốt): `hoan_tat`
		xét MỌI dòng hàng thuộc kho có bật quản lý vị trí, không chỉ dòng
		đang mở trên màn hình. Phiếu hai dòng CÙNG kho quản lý vị trí, chỉ
		lấy dòng 1 — câu báo phải nêu ĐÚNG dòng 2 (idx + mặt hàng), không lẫn
		sang dòng 1 (đã lấy đủ)."""
		from erpnext.vi_tri_kho.vitri.lay_hang import ghi_da_lay, hoan_tat

		dn2 = frappe.get_doc(
			{
				"doctype": "Delivery Note",
				"company": CTY,
				"customer": KHACH,
				"posting_date": nowdate(),
				"items": [
					{
						"item_code": ITEM,
						"qty": 5,
						"rate": 5000,
						"warehouse": KHO,
						"batch_no": LO,
						"use_serial_batch_fields": 1,
					},
					{
						"item_code": ITEM,
						"qty": 7,
						"rate": 5000,
						"warehouse": KHO,
						"batch_no": LO,
						"use_serial_batch_fields": 1,
					},
				],
			}
		)
		dn2.insert(ignore_permissions=True)
		ghi_da_lay(dn2.name, dn2.items[0].name, LO, O_GAN, 5)

		with self.assertRaisesRegex(
			frappe.ValidationError, f"Dòng {dn2.items[1].idx}.*chưa lấy đủ"
		):
			hoan_tat(dn2.name)
		self.assertEqual(frappe.db.get_value("Delivery Note", dn2.name, "docstatus"), 0)

	def test_hoan_tat_bo_qua_dong_o_kho_khong_bat_vi_tri(self):
		"""Dòng thuộc kho KHÔNG bật quản lý vị trí không đòi phân bổ — hook ghi
		sổ không đụng tới nó (`kho_co_quan_ly_vi_tri`), nên `hoan_tat` không
		được chặn vì nó. Đồng thời khoá lại `can_quet` ở phần ĐỌC
		(`mo_phieu_giao`, bổ sung điều phối để hết bất đối xứng đọc/ghi): dòng
		ở kho quản lý vị trí → `can_quet=True`; dòng ở kho thường →
		`can_quet=False`, NHƯNG vẫn còn mặt trong danh sách (không lọc bỏ) vì
		thủ kho vẫn phải lấy tay nó."""
		from erpnext.vi_tri_kho.vitri.lay_hang import ghi_da_lay, hoan_tat, mo_phieu_giao

		kho_khac = "Hàng trả về - MYN"
		self.assertFalse(frappe.db.get_value("Warehouse", kho_khac, "custom_quan_ly_vi_tri"))

		se = frappe.get_doc(
			{
				"doctype": "Stock Entry",
				"stock_entry_type": "Material Receipt",
				"company": CTY,
				"items": [
					{
						"item_code": ITEM,
						"qty": 4,
						"t_warehouse": kho_khac,
						"basic_rate": 1000,
						"batch_no": LO,
						"use_serial_batch_fields": 1,
					}
				],
			}
		)
		se.insert(ignore_permissions=True)
		se.submit()

		dn2 = frappe.get_doc(
			{
				"doctype": "Delivery Note",
				"company": CTY,
				"customer": KHACH,
				"posting_date": nowdate(),
				"items": [
					{
						"item_code": ITEM,
						"qty": 5,
						"rate": 5000,
						"warehouse": KHO,
						"batch_no": LO,
						"use_serial_batch_fields": 1,
					},
					{
						"item_code": ITEM,
						"qty": 4,
						"rate": 5000,
						"warehouse": kho_khac,
						"batch_no": LO,
						"use_serial_batch_fields": 1,
					},
				],
			}
		)
		dn2.insert(ignore_permissions=True)

		truoc = {d["dong_hang"]: d["can_quet"] for d in mo_phieu_giao(dn2.name)["dong"]}
		self.assertTrue(truoc[dn2.items[0].name], "dòng ở kho quản lý vị trí phải can_quet=True")
		self.assertFalse(truoc[dn2.items[1].name], "dòng ở kho thường phải can_quet=False")

		ghi_da_lay(dn2.name, dn2.items[0].name, LO, O_GAN, 5)

		kq = hoan_tat(dn2.name)
		self.assertEqual(kq["name"], dn2.name)
		self.assertEqual(frappe.db.get_value("Delivery Note", dn2.name, "docstatus"), 1)

	def test_khong_co_quyen_ghi_thi_ca_nam_ham_bi_chan(self):
		"""`_kiem_tra_quyen()` chặn theo vai trò TOÀN CỤC — cùng bài
		`test_khong_co_vai_tro_kho_thi_bi_chan` ở phần ĐỌC, khoá lại cho cả
		năm hàm GHI."""
		from erpnext.vi_tri_kho.vitri.lay_hang import (
			bo_dong_da_lay,
			chot_thieu,
			doi_lo,
			ghi_da_lay,
			hoan_tat,
		)

		ten = "lay-hang-ghi-khong-quyen@mo-phong.local"
		if not frappe.db.exists("User", ten):
			frappe.get_doc(
				{"doctype": "User", "email": ten, "first_name": "Ghi", "send_welcome_email": 0, "roles": []}
			).insert(ignore_permissions=True)
		frappe.set_user(ten)
		with self.assertRaises(frappe.PermissionError):
			ghi_da_lay(self.dn.name, self.dong, LO, O_GAN, 5)
		with self.assertRaises(frappe.PermissionError):
			bo_dong_da_lay(self.dn.name, "bat-ky")
		with self.assertRaises(frappe.PermissionError):
			doi_lo(self.dn.name, self.dong, "bat-ky")
		with self.assertRaises(frappe.PermissionError):
			chot_thieu(self.dn.name, self.dong)
		with self.assertRaises(frappe.PermissionError):
			hoan_tat(self.dn.name)

	def test_phieu_giao_tu_don_ban_lay_thieu_van_hoan_tat_duoc(self):
		"""CHƯA đo trước Task 5 (nêu trong task-5-report.md mục "còn nghi
		ngờ"): mọi fixture khác của module đều dựng `Delivery Note` ĐỨNG ĐỘC
		LẬP. Ở đây dựng qua đúng đường thật — `Sales Order` submit rồi
		`make_delivery_note` — để đo `hoan_tat` hạ `qty` một dòng có
		`against_sales_order`/`so_detail` có chạm `SellingController`/rollup
		"% đã giao" theo cách khác dòng thường hay không."""
		from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note
		from erpnext.vi_tri_kho.vitri.lay_hang import chot_thieu, ghi_da_lay, hoan_tat

		don_ban = frappe.get_doc(
			{
				"doctype": "Sales Order",
				"company": CTY,
				"customer": KHACH,
				"delivery_date": nowdate(),
				"items": [
					{
						"item_code": ITEM,
						"qty": 10,
						"rate": 5000,
						"warehouse": KHO,
						"delivery_date": nowdate(),
					}
				],
			}
		)
		don_ban.insert(ignore_permissions=True)
		don_ban.submit()

		dn2 = make_delivery_note(don_ban.name)
		dn2.items[0].batch_no = LO
		dn2.items[0].use_serial_batch_fields = 1
		dn2.insert(ignore_permissions=True)
		dong2 = dn2.items[0].name

		ghi_da_lay(dn2.name, dong2, LO, O_GAN, 6)
		chot_thieu(dn2.name, dong2)
		kq = hoan_tat(dn2.name)

		self.assertEqual(kq["name"], dn2.name)
		self.assertEqual(frappe.db.get_value("Delivery Note", dn2.name, "docstatus"), 1)
		self.assertEqual(flt(frappe.db.get_value("Delivery Note Item", dong2, "qty")), 6.0)
		don_ban.reload()
		self.assertEqual(flt(don_ban.items[0].delivered_qty), 6.0)

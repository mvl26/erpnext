"""Lấy hàng theo phân bổ — sổ vị trí phải trừ ĐÚNG ô thủ kho đã quét.

Bài chịu lực của cả thiết kế là `test_ghi_so_theo_o_da_phan_bo_chu_khong_theo_fefo`:
nó phân bổ vào ô mà FEFO KHÔNG chọn. Thiếu chốt đó thì một cài đặt bỏ qua phân bổ
và cứ chạy FEFO vẫn xanh, vì cả hai đường đều cho ra tổng đúng.
"""

from contextlib import contextmanager

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, flt, nowdate

from erpnext.warehouse_operations.vitri import hook_sle, so

KHO = "Kho Miyano - MYN"
CTY = "Miyano Việt Nam"
KHACH = "Bệnh viện DEMO Miyano E2E"
ITEM = "9L-VT-LAY-HANG"
LO = "9L-LO-LAY-01"
O_GAN = "9L01010101"
O_XA = "9L01010102"
DIEM_TEST = "test_lay_hang"


@contextmanager
def bo_kiem_o_tem():
	"""Dựng tồn ở NHIỀU ô cho một lô — thứ luật "xếp đúng ô trên tem"
	(`vitri/o_tem.py`) cấm ở nghiệp vụ thật. Chỉ dùng để dựng dữ liệu cho các
	bài KHÔNG nói về luật đó (FEFO, lấy hàng...)."""
	from erpnext.warehouse_operations.vitri.o_tem import CO_BO_KIEM_TEST

	cu = frappe.flags.get(CO_BO_KIEM_TEST)
	frappe.flags[CO_BO_KIEM_TEST] = True
	try:
		yield
	finally:
		frappe.flags[CO_BO_KIEM_TEST] = cu


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
	with bo_kiem_o_tem():
		pxep.insert(ignore_permissions=True)
		pxep.submit()
	return pxep


def _nhap_kho_lo(so_lo, so_luong):
	"""Nhập kho cho MỘT LÔ tuỳ ý — `_nhap_kho` khoá cứng vào `LO`, cần bản này
	cho các bài dựng lô THỨ HAI (vd `test_tach_dong_khi_lay_tu_hai_lo`)."""
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
					"batch_no": so_lo,
					"use_serial_batch_fields": 1,
				}
			],
		}
	)
	se.insert(ignore_permissions=True)
	se.submit()
	return se


def _chuyen_vao_o_lo(so_lo, cap):
	"""`_chuyen_vao_o` khoá cứng vào `LO` — bản này xếp một lô tuỳ ý vào ô."""
	chua_xep = frappe.db.get_value("Storage Location", {"kho": KHO, "la_o_chua_xep": 1})
	pxep = frappe.get_doc(
		{
			"doctype": "Location Transfer",
			"kho": KHO,
			"ngay": nowdate(),
			"items": [
				{"vat_tu": ITEM, "so_lo": so_lo, "tu_o": chua_xep, "den_o": o, "so_luong": sl}
				for o, sl in cap
			],
		}
	)
	with bo_kiem_o_tem():
		pxep.insert(ignore_permissions=True)
		pxep.submit()
	return pxep


ITEM_KHONG_LO = "9L-VT-LAY-HANG-KHONG-LO"


def _vat_tu_khong_lo():
	"""Mặt hàng KHÔNG quản lý lô — cần cho vòng sửa sau review Task 7 (spec §6.2:
	trang phải quét được MỌI dòng của phiếu, kể cả dòng không lô)."""
	if not frappe.db.exists("Item", ITEM_KHONG_LO):
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": ITEM_KHONG_LO,
				"item_name": "Hàng thử lấy hàng PDA không lô",
				"item_group": "All Item Groups",
				"stock_uom": "Nos",
				"is_stock_item": 1,
				"has_batch_no": 0,
			}
		).insert(ignore_permissions=True)
	return ITEM_KHONG_LO


def _nhap_kho_khong_lo(so_luong):
	se = frappe.get_doc(
		{
			"doctype": "Stock Entry",
			"stock_entry_type": "Material Receipt",
			"company": CTY,
			"items": [{"item_code": ITEM_KHONG_LO, "qty": so_luong, "t_warehouse": KHO, "basic_rate": 1000}],
		}
	)
	se.insert(ignore_permissions=True)
	se.submit()
	return se


def _chuyen_vao_o_khong_lo(cap):
	"""`_chuyen_vao_o`/`_chuyen_vao_o_lo` khoá cứng vào `ITEM` — bản này cho
	mặt hàng KHÔNG quản lý lô (`so_lo=None` trên cả nguồn lẫn đích)."""
	chua_xep = frappe.db.get_value("Storage Location", {"kho": KHO, "la_o_chua_xep": 1})
	pxep = frappe.get_doc(
		{
			"doctype": "Location Transfer",
			"kho": KHO,
			"ngay": nowdate(),
			"items": [
				{"vat_tu": ITEM_KHONG_LO, "so_lo": None, "tu_o": chua_xep, "den_o": o, "so_luong": sl}
				for o, sl in cap
			],
		}
	)
	with bo_kiem_o_tem():
		pxep.insert(ignore_permissions=True)
		pxep.submit()
	return pxep


ITEM_DICH_VU = "9L-VT-LAY-HANG-DICH-VU"
ITEM_DA_DON_VI = "9L-VT-LAY-HANG-DA-DON-VI"
UOM_HOP = "9L-Hop"


def _vat_tu_dich_vu():
	"""Mặt hàng KHÔNG quản lý tồn kho (`is_stock_item=0`) — ERPNext vẫn gán
	`warehouse` cho dòng loại này trên Delivery Note (phí vận chuyển/dịch vụ/
	hàng đặt ngoài/dòng cha Product Bundle đều thuộc nhóm này). Vòng sửa cuối
	(review toàn nhánh, Critical 1)."""
	if not frappe.db.exists("Item", ITEM_DICH_VU):
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": ITEM_DICH_VU,
				"item_name": "Dịch vụ thử lấy hàng PDA",
				"item_group": "All Item Groups",
				"stock_uom": "Nos",
				"is_stock_item": 0,
			}
		).insert(ignore_permissions=True)
	return ITEM_DICH_VU


def _vat_tu_da_don_vi():
	"""Mặt hàng bán theo đơn vị KHÁC đơn vị tồn kho (1 `UOM_HOP` = 10 Nos) —
	vòng sửa cuối (review toàn nhánh, Important 2)."""
	if not frappe.db.exists("UOM", UOM_HOP):
		frappe.get_doc({"doctype": "UOM", "uom_name": UOM_HOP}).insert(ignore_permissions=True)
	if not frappe.db.exists("Item", ITEM_DA_DON_VI):
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": ITEM_DA_DON_VI,
				"item_name": "Hàng thử lấy hàng PDA đa đơn vị",
				"item_group": "All Item Groups",
				"stock_uom": "Nos",
				"is_stock_item": 1,
				"has_batch_no": 0,
				"uoms": [{"uom": UOM_HOP, "conversion_factor": 10}],
			}
		).insert(ignore_permissions=True)
	return ITEM_DA_DON_VI


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

	def test_stock_entry_khong_phai_delivery_note_van_di_fefo(self):
		"""VÒNG SỬA CUỐI (review toàn nhánh, bài 4): khoá hằng `CHUNG_TU_CO_PHAN_BO
		= ("Delivery Note",)` — Stock Entry KHÔNG nằm trong đó nên phải luôn đi
		FEFO như cũ và không bao giờ đọc bảng phân bổ. Trước bài này chỉ có hồi
		quy 35 module phủ gián tiếp; một lần dọn hằng số vô ý gộp Stock Entry
		vào sẽ không bị bắt ở đâu cả nếu không có bài test đặt tên riêng này."""
		from erpnext.warehouse_operations.vitri.lay_hang import phan_bo_cua_dong

		se = frappe.get_doc(
			{
				"doctype": "Stock Entry",
				"stock_entry_type": "Material Issue",
				"company": CTY,
				"items": [
					{
						"item_code": ITEM,
						"qty": 10,
						"s_warehouse": KHO,
						"batch_no": LO,
						"use_serial_batch_fields": 1,
					}
				],
			}
		)
		se.insert(ignore_permissions=True)
		se.submit()

		self.assertEqual(so.ton_o(O_GAN, ITEM, LO), 10.0, "FEFO phải rút ở O_GAN (thu_tu nhỏ hơn) trước")
		self.assertEqual(so.ton_o(O_XA, ITEM, LO), 10.0)
		self.assertEqual(phan_bo_cua_dong("Stock Entry", se.name, se.items[0].name, LO), [])

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
		with bo_kiem_o_tem():
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
		from erpnext.warehouse_operations.vitri.lay_hang import danh_sach_phieu_giao

		# QUYẾT ĐỊNH 18/09/2026: `danh_sach_phieu_giao` trả DICT (khuôn
		# `xep.phieu_xep_dang_lam`), không phải list — đọc khoá "phieu".
		ds = {d["name"]: d for d in danh_sach_phieu_giao(KHO)["phieu"]}
		self.assertIn(self.dn.name, ds)
		self.assertEqual(ds[self.dn.name]["can_lay"], 12.0)
		self.assertEqual(ds[self.dn.name]["da_lay"], 0.0)

	def test_mo_phieu_ra_o_nen_lay_theo_fefo(self):
		from erpnext.warehouse_operations.vitri.lay_hang import mo_phieu_giao

		p = mo_phieu_giao(self.dn.name)
		self.assertEqual(len(p["dong"]), 1)
		d = p["dong"][0]
		self.assertEqual((d["vat_tu"], d["so_lo"], d["can_lay"]), (ITEM, LO, 12.0))
		# 12 lấy hết ô đứng trước (20) → chỉ một ô được gợi ý.
		self.assertEqual([o["o"] for o in d["o_nen_lay"]], [O_GAN])
		self.assertEqual(d["thieu_trong_lo"], 0.0, "đủ hàng thì không thiếu gì")

	def test_mo_phieu_thieu_hang_khong_nem_loi_va_goi_y_dung_ton_lo(self):
		"""Bài test BẮT BUỘC (sửa lỗi "mở phiếu bật hộp lỗi"): dòng cần NHIỀU
		HƠN tồn của (mặt hàng, lô) đang chốt — ca hay gặp nhất của trang (lô
		trên dòng không đủ cả dòng, phải tách sang lô thứ hai). TRƯỚC bản vá,
		`mo_phieu_giao` gọi thẳng `chon_o_xuat(..., con_can)`, hàm đó
		`frappe.throw` khi không đủ — bị bắt (không nổ) nhưng câu báo đã kịp
		đẩy vào `frappe.local.message_log` TRƯỚC KHI ném, nên trình duyệt (đọc
		thẳng message_log của response) vẫn bật hộp lỗi ngay khi MỞ PHIẾU.

		Khoá bằng CHÍNH kết quả `mo_phieu_giao` (không phải qua whitelisted
		full-stack, nhưng cùng hàm mà trang gọi): gợi ý phải KHỚP đúng các ô có
		hàng thật của lô (tổng bằng tồn lô, không hơn không kém),
		`thieu_trong_lo` đúng phần còn thiếu, và KHÔNG một câu báo nào bị đẩy
		vào `message_log` trong lúc mở phiếu.
		"""
		from erpnext.warehouse_operations.vitri.lay_hang import mo_phieu_giao

		# LO chỉ có tổng 30 (O_GAN=20 + O_XA=10, xem setUp) — dòng cần 40.
		dn = _phieu_giao(40)
		do_dai_truoc = len(frappe.local.message_log)

		p = mo_phieu_giao(dn.name)

		self.assertEqual(
			len(frappe.local.message_log), do_dai_truoc, "mở phiếu không được bật hộp lỗi nào"
		)
		d = p["dong"][0]
		self.assertEqual(d["thieu_trong_lo"], 10.0)
		self.assertEqual({o["o"]: o["so_luong"] for o in d["o_nen_lay"]}, {O_GAN: 20.0, O_XA: 10.0})
		self.assertEqual(sum(o["so_luong"] for o in d["o_nen_lay"]), 30.0, "gợi ý phải khớp đúng tồn lô")

	def test_mo_phieu_dong_chua_chot_lo_van_goi_y_cheo_lo_theo_fefo(self):
		"""Bài test BẮT BUỘC (review sau bản vá lỗi 1, phát hiện qua `advisor`):
		`tong_ton_vi_tri(kho, vat_tu, None)` và `chon_o_xuat(kho, vat_tu, None,
		...)` KHÔNG cùng nghĩa cho `so_lo=None` — hàm đầu chỉ cộng các dòng
		KHÔNG LÔ (gần như luôn 0 cho một mặt hàng CÓ quản lý lô), hàm sau hiểu
		`so_lo=None` là "mọi lô, chọn theo FEFO". Dòng của một mặt hàng CÓ quản
		lý lô nhưng CHƯA chốt lô nào (`batch_no` rỗng — ca thường của phiếu tạo
		từ đơn bán, trước khi thủ kho quét tem lô đầu tiên) mà lấy CẬN TRÊN từ
		hàm đầu để giới hạn hàm sau thì sẽ cap về 0 — biến gợi ý cross-lô hợp
		lệ (30 tồn, đủ cho dòng cần 15) thành "cả dòng đều thiếu". Bài này khoá
		lại: dòng như vậy phải vẫn nhận gợi ý ĐẦY ĐỦ (không cap sai), và không
		đẩy câu báo nào vào `message_log`.
		"""
		from erpnext.warehouse_operations.vitri.lay_hang import mo_phieu_giao

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
						"use_serial_batch_fields": 1,
					}
				],
			}
		)
		dn.insert(ignore_permissions=True)
		# `insert()` tự chọn lô khi kho chỉ có ĐÚNG một lô còn tồn (site test này
		# chỉ có `LO`) — không phải kịch bản bài test cần (dòng CHƯA chốt lô nào).
		# Ép về rỗng THẲNG trên CSDL (bỏ qua `validate`, giống cách các bài test
		# khác của module này dựng ca "mất chiều lô") rồi đọc lại — `mo_phieu_giao`
		# tự `frappe.get_doc` lại từ CSDL nên thấy đúng trạng thái đã ép.
		frappe.db.set_value("Delivery Note Item", dn.items[0].name, "batch_no", None)
		dn.reload()
		self.assertFalse(dn.items[0].batch_no, "dòng phải CHƯA chốt lô nào cho đúng kịch bản bài test")
		do_dai_truoc = len(frappe.local.message_log)

		p = mo_phieu_giao(dn.name)

		self.assertEqual(
			len(frappe.local.message_log), do_dai_truoc, "mở phiếu không được bật hộp lỗi nào"
		)
		d = p["dong"][0]
		self.assertEqual(d["thieu_trong_lo"], 0.0, "chưa chốt lô thì không có 'lô đang chốt' nào để thiếu")
		self.assertEqual(
			sum(o["so_luong"] for o in d["o_nen_lay"]), 15.0, "gợi ý cross-lô phải đủ, không bị cap sai về 0"
		)

	def test_mo_phieu_goi_y_tru_phan_da_len_phieu_nhap_khong_con_o_da_lay_het(self):
		"""Bài test BẮT BUỘC (sửa lỗi đo trên tài liệu ảnh `22b`): lô nằm ở hai
		ô (12 + 8) — ghi lấy HẾT ô A (12) trên CHÍNH phiếu (nháp, chưa submit)
		rồi mở lại phiếu. `Location Balance` (nguồn của `chon_o_xuat`) chỉ đổi
		lúc DUYỆT, không đổi lúc ghi bảng phân bổ nháp — nếu không TRỪ phần đã
		lên phiếu, gợi ý "Nên lấy" sẽ vẫn quay lại ô A (thủ kho đi tới sẽ thấy
		ô trống, đúng cảnh lộ trên ảnh `22b` trước bản vá). Gợi ý ĐÚNG phải
		chuyển hẳn sang ô B, không còn ô A."""
		from erpnext.warehouse_operations.vitri.lay_hang import ghi_da_lay, mo_phieu_giao

		o_a, o_b = "9L01020101", "9L01020102"
		lo2 = "9L-LO-LAY-22A"
		_o(o_a, thu_tu=1)
		_o(o_b, thu_tu=2)
		if not frappe.db.exists("Batch", lo2):
			frappe.get_doc(
				{"doctype": "Batch", "batch_id": lo2, "item": ITEM, "expiry_date": "2029-06-30"}
			).insert(ignore_permissions=True)
		_nhap_kho_lo(lo2, 20)
		_chuyen_vao_o_lo(lo2, [(o_a, 12), (o_b, 8)])

		dn = frappe.get_doc(
			{
				"doctype": "Delivery Note",
				"company": CTY,
				"customer": KHACH,
				"posting_date": nowdate(),
				"items": [
					{
						"item_code": ITEM,
						"qty": 20,
						"rate": 5000,
						"warehouse": KHO,
						"batch_no": lo2,
						"use_serial_batch_fields": 1,
					}
				],
			}
		)
		dn.insert(ignore_permissions=True)

		p1 = ghi_da_lay(dn.name, dn.items[0].name, lo2, o_a, 12)
		self.assertEqual(p1["dong"][0]["da_lay"], 12.0)

		p2 = mo_phieu_giao(dn.name)
		d = p2["dong"][0]
		self.assertEqual(
			[(g["o"], g["so_luong"]) for g in d["o_nen_lay"]],
			[(o_b, 8.0)],
			"gợi ý phải chuyển hẳn sang ô B, không còn gợi ý lại ô A vừa lấy hết",
		)
		self.assertEqual(d["thieu_trong_lo"], 0.0)

	def test_mo_phieu_chua_lay_gi_thi_goi_y_du_ca_hai_o_nhu_truoc_khi_sua(self):
		"""Chốt ÂM cho bản vá "trừ phần đã lên phiếu": phiếu CHƯA có lượt ghi
		nào thì không có gì để trừ — gợi ý phải đủ CẢ HAI ô, y hệt hành vi
		trước bản vá này."""
		from erpnext.warehouse_operations.vitri.lay_hang import mo_phieu_giao

		o_a, o_b = "9L01020101", "9L01020102"
		lo2 = "9L-LO-LAY-22B"
		_o(o_a, thu_tu=1)
		_o(o_b, thu_tu=2)
		if not frappe.db.exists("Batch", lo2):
			frappe.get_doc(
				{"doctype": "Batch", "batch_id": lo2, "item": ITEM, "expiry_date": "2029-06-30"}
			).insert(ignore_permissions=True)
		_nhap_kho_lo(lo2, 20)
		_chuyen_vao_o_lo(lo2, [(o_a, 12), (o_b, 8)])

		dn = frappe.get_doc(
			{
				"doctype": "Delivery Note",
				"company": CTY,
				"customer": KHACH,
				"posting_date": nowdate(),
				"items": [
					{
						"item_code": ITEM,
						"qty": 20,
						"rate": 5000,
						"warehouse": KHO,
						"batch_no": lo2,
						"use_serial_batch_fields": 1,
					}
				],
			}
		)
		dn.insert(ignore_permissions=True)

		p = mo_phieu_giao(dn.name)
		d = p["dong"][0]
		self.assertEqual(
			[(g["o"], g["so_luong"]) for g in d["o_nen_lay"]],
			[(o_a, 12.0), (o_b, 8.0)],
			"chưa lấy gì thì gợi ý phải đủ cả hai ô theo đúng thứ tự FEFO",
		)
		self.assertEqual(d["thieu_trong_lo"], 0.0)

	def test_mo_phieu_goi_y_van_ra_khi_mot_phan_lo_ket_o_ngung_dung(self):
		"""Bài test BẮT BUỘC (review sau bản vá "trừ phần đã lên phiếu",
		phát hiện qua `advisor`): xin ĐỦ `tong_ton_vi_tri` (cộng CẢ ô ngừng
		dùng) để lấy số dư THẬT của từng ô — nhưng `chon_o_xuat` (chỉ xét ô
		ĐANG DÙNG) có thể ném nếu đúng phần đó đang kẹt ở một ô ngừng dùng,
		một thao tác vận hành BÌNH THƯỜNG (xem docstring `fefo.py`). Không có
		lượt thử lại với số nhỏ hơn thì gợi ý sẽ TRẮNG hoàn toàn dù dòng vẫn
		lấy đủ được từ các ô đang dùng. Khoá lại: dòng cần 12, 12 nằm ở ô A
		(đang dùng), 8 nằm ở ô C đã Ngừng dùng (tổng CẢ kho là 20, vượt hẳn
		12 đang dùng) — gợi ý vẫn phải ra đúng ô A, không trắng, và không đẩy
		câu báo nào vào `message_log`.
		"""
		from erpnext.warehouse_operations.vitri.lay_hang import mo_phieu_giao

		o_a, o_c = "9L01020101", "9L01020103"
		lo2 = "9L-LO-LAY-22C"
		_o(o_a, thu_tu=1)
		_o(o_c, thu_tu=2)
		if not frappe.db.exists("Batch", lo2):
			frappe.get_doc(
				{"doctype": "Batch", "batch_id": lo2, "item": ITEM, "expiry_date": "2029-06-30"}
			).insert(ignore_permissions=True)
		_nhap_kho_lo(lo2, 20)
		_chuyen_vao_o_lo(lo2, [(o_a, 12), (o_c, 8)])
		frappe.db.set_value("Storage Location", o_c, "disabled", 1)

		dn = frappe.get_doc(
			{
				"doctype": "Delivery Note",
				"company": CTY,
				"customer": KHACH,
				"posting_date": nowdate(),
				"items": [
					{
						"item_code": ITEM,
						"qty": 12,
						"rate": 5000,
						"warehouse": KHO,
						"batch_no": lo2,
						"use_serial_batch_fields": 1,
					}
				],
			}
		)
		dn.insert(ignore_permissions=True)
		do_dai_truoc = len(frappe.local.message_log)

		p = mo_phieu_giao(dn.name)

		self.assertEqual(
			len(frappe.local.message_log), do_dai_truoc, "mở phiếu không được bật hộp lỗi nào"
		)
		d = p["dong"][0]
		self.assertEqual(
			[(g["o"], g["so_luong"]) for g in d["o_nen_lay"]],
			[(o_a, 12.0)],
			"gợi ý không được trắng chỉ vì tổng CẢ KHO có phần kẹt ở ô ngừng dùng",
		)

	def test_thieu_trong_lo_khong_cong_nham_phan_bo_o_kho_khac(self):
		"""Bài test BẮT BUỘC (review độc lập, model mạnh, điểm 3):
		`_da_phan_bo_o_theo_mat_hang_lo` (gộp phần đã lên phiếu để trừ khỏi gợi
		ý) TRƯỚC bản vá này không lọc theo KHO — một phiếu có HAI dòng cùng
		(mặt hàng, lô) nhưng ở HAI KHO khác nhau (hiếm nhưng có thể: giao từ
		hai kho cho cùng một khách) sẽ cộng nhầm phần đã phân bổ của dòng KHO
		KHÁC vào phép trừ của dòng đang tính, khiến `thieu_trong_lo` báo thiếu
		nhiều hơn tồn THẬT của ĐÚNG kho đang xét.

		Dòng A (KHO, `Kho Miyano - MYN`) cần ĐÚNG 30 — khớp tổng tồn LO ở KHO
		(20 + 10, xem setUp) — nên PHẢI đủ, `thieu_trong_lo` phải là 0. Dòng B
		ở kho khác (`Stores - MYN`) đã ghi lấy HẾT 5 của CÙNG (mặt hàng, lô) đó
		ở một ô của KHO ĐÓ; nếu hàm gộp không lọc kho, 5 này bị trừ NHẦM vào
		tồn khả dụng của dòng A, biến 30/30 đủ thành báo thiếu 5.
		"""
		from erpnext.warehouse_operations.vitri import kho as vk
		from erpnext.warehouse_operations.vitri.bat_kho import tao_o_chua_xep
		from erpnext.warehouse_operations.vitri.lay_hang import ghi_da_lay, mo_phieu_giao

		kho_b = "Stores - MYN"
		o_b = "8B01010101"
		co_cu = frappe.db.get_value("Warehouse", kho_b, "custom_quan_ly_vi_tri")
		frappe.db.set_value("Warehouse", kho_b, "custom_quan_ly_vi_tri", 1)
		vk.xoa_cache_kho(kho_b)

		def _don():
			frappe.db.set_value("Warehouse", kho_b, "custom_quan_ly_vi_tri", co_cu)
			vk.xoa_cache_kho(kho_b)

		self.addCleanup(_don)

		# `tao_o_chua_xep` — CÁCH DUY NHẤT được phép tạo ô hệ thống, kể cả
		# trong test (xem docstring hàm đó): hook ghi sổ (`hook_sle.py`) đòi
		# một kho ĐÃ bật quản lý vị trí phải có sẵn ô "Chưa xếp vị trí" đúng
		# dạng trước khi nhận bất kỳ dòng sổ nào, kể cả Material Receipt.
		tao_o_chua_xep(kho_b)
		if not frappe.db.exists("Storage Location", o_b):
			frappe.get_doc({"doctype": "Storage Location", "ma_o": o_b, "kho": kho_b}).insert(
				ignore_permissions=True
			)

		se = frappe.get_doc(
			{
				"doctype": "Stock Entry",
				"stock_entry_type": "Material Receipt",
				"company": CTY,
				"items": [
					{
						"item_code": ITEM,
						"qty": 5,
						"t_warehouse": kho_b,
						"basic_rate": 1000,
						"batch_no": LO,
						"use_serial_batch_fields": 1,
					}
				],
			}
		)
		se.insert(ignore_permissions=True)
		se.submit()

		# Material Receipt đổ thẳng vào ô "Chưa xếp" của kho B — chuyển sang ô
		# lá `o_b` trước khi ghi phân bổ (`ghi_da_lay` đòi phân bổ vào đúng ô
		# đang GIỮ hàng, không phải ô chưa xếp).
		chua_xep_b = frappe.db.get_value("Storage Location", {"kho": kho_b, "la_o_chua_xep": 1})
		lt = frappe.get_doc(
			{
				"doctype": "Location Transfer",
				"kho": kho_b,
				"ngay": nowdate(),
				"items": [{"vat_tu": ITEM, "so_lo": LO, "tu_o": chua_xep_b, "den_o": o_b, "so_luong": 5}],
			}
		)
		with bo_kiem_o_tem():
			lt.insert(ignore_permissions=True)
			lt.submit()

		dn = frappe.get_doc(
			{
				"doctype": "Delivery Note",
				"company": CTY,
				"customer": KHACH,
				"posting_date": nowdate(),
				"items": [
					{
						"item_code": ITEM,
						"qty": 30,
						"rate": 5000,
						"warehouse": KHO,
						"batch_no": LO,
						"use_serial_batch_fields": 1,
					},
					{
						"item_code": ITEM,
						"qty": 5,
						"rate": 5000,
						"warehouse": kho_b,
						"batch_no": LO,
						"use_serial_batch_fields": 1,
					},
				],
			}
		)
		dn.insert(ignore_permissions=True)

		ghi_da_lay(dn.name, dn.items[1].name, LO, o_b, 5)

		p = mo_phieu_giao(dn.name)
		dong_a = next(x for x in p["dong"] if x["dong_hang"] == dn.items[0].name)
		self.assertEqual(
			dong_a["thieu_trong_lo"], 0.0, "kho A đủ hàng, không được báo thiếu vì phân bổ ở kho B"
		)
		self.assertEqual(sum(o["so_luong"] for o in dong_a["o_nen_lay"]), 30.0)

	def test_quet_lo_cua_phieu_va_quet_o(self):
		from erpnext.warehouse_operations.vitri.lay_hang import quet_de_lay

		self.assertEqual(quet_de_lay(self.dn.name, LO)["loai"], "lo")
		self.assertEqual(quet_de_lay(self.dn.name, O_GAN)["loai"], "o")
		self.assertEqual(quet_de_lay(self.dn.name, "9L-KHONG-CO-GI")["loai"], None)

	def test_quet_lo_khac_cung_mat_hang_bao_loai_lo_khac_kem_hsd(self):
		from erpnext.warehouse_operations.vitri.lay_hang import quet_de_lay

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
		from erpnext.warehouse_operations.vitri.lay_hang import danh_sach_phieu_giao

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
		from erpnext.warehouse_operations.vitri.lay_hang import quet_de_lay

		self.assertEqual(quet_de_lay("KHONG-TON-TAI-PHIEU-GIAO-9999", LO), {"loai": None})

	def test_kho_khong_bat_vi_tri_bi_chan(self):
		"""Important 2 (vòng sửa 1, review điều phối): endpoint whitelisted gọi
		thẳng được — `kho` tuỳ ý (chưa bật quản lý vị trí) không được lọt qua."""
		from erpnext.warehouse_operations.vitri.lay_hang import danh_sach_phieu_giao

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
		from erpnext.warehouse_operations.vitri.lay_hang import mo_phieu_giao, quet_de_lay

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
		from erpnext.warehouse_operations.vitri.lay_hang import danh_sach_phieu_giao

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
		from erpnext.warehouse_operations.vitri.lay_hang import quet_de_lay

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
		from erpnext.warehouse_operations.vitri.lay_hang import quet_de_lay

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

	def test_quet_lo_khac_het_han_bao_het_han(self):
		"""Bài test bắt buộc (VÒNG SỬA CUỐI, review toàn nhánh, Critical 3): lô
		hết hạn có HSD GẦN HƠN lô đang chốt trên phiếu lại là con đường ÍT MA
		SÁT NHẤT trước bản vá này (`han_xa_hon=False`, trang chỉ cảnh báo nhẹ,
		không chặn). `het_han` phải báo đúng — ĐỘC LẬP với `han_xa_hon`."""
		from erpnext.warehouse_operations.vitri.lay_hang import quet_de_lay

		lo_het_han = "9L-LO-LAY-HET-HAN-01"
		han_da_qua = add_days(nowdate(), -3)
		if not frappe.db.exists("Batch", lo_het_han):
			frappe.get_doc(
				{"doctype": "Batch", "batch_id": lo_het_han, "item": ITEM, "expiry_date": han_da_qua}
			).insert(ignore_permissions=True)
		frappe.cache().delete_value(f"erpnext:barcode_scan:{lo_het_han}")

		kq = quet_de_lay(self.dn.name, lo_het_han)
		self.assertEqual(kq["loai"], "lo_khac")
		self.assertTrue(kq["het_han"])
		self.assertFalse(kq["han_xa_hon"], "lô hết hạn có HSD gần hơn lô 2029-01-31 đang chốt")

	def test_quet_lo_dang_chot_da_het_han_bao_het_han(self):
		"""VÒNG SỬA CUỐI (Critical 3): lô ĐANG CHỐT ngay trên chính dòng phiếu
		có thể hết hạn TRONG LÚC phiếu nằm nháp chờ lấy — `posting_date` cố
		định từ lúc tạo phiếu nên lớp kiểm cốt lõi
		(`StockController.validate_serialized_batch`, so `expiry_date` với
		`posting_date`) không bắt được. `quet_de_lay` phải tự so với HÔM NAY
		thật (`nowdate()`), không phải `posting_date` của phiếu."""
		from erpnext.warehouse_operations.vitri.lay_hang import quet_de_lay

		lo_het_han = "9L-LO-LAY-HET-HAN-02"
		han_da_qua = add_days(nowdate(), -3)
		# `set_posting_time=1` bên dưới BẮT BUỘC: không có nó, controller tự ghi
		# đè `posting_date` thành HÔM NAY lúc `validate()` — phá đúng kịch bản
		# "posting_date cũ hơn ngày hết hạn" mà bài này cần dựng.
		ngay_dang_phieu = add_days(nowdate(), -14)
		if not frappe.db.exists("Batch", lo_het_han):
			frappe.get_doc(
				{"doctype": "Batch", "batch_id": lo_het_han, "item": ITEM, "expiry_date": han_da_qua}
			).insert(ignore_permissions=True)
		frappe.cache().delete_value(f"erpnext:barcode_scan:{lo_het_han}")

		dn = frappe.get_doc(
			{
				"doctype": "Delivery Note",
				"company": CTY,
				"customer": KHACH,
				"posting_date": ngay_dang_phieu,
				"set_posting_time": 1,
				"items": [
					{
						"item_code": ITEM,
						"qty": 5,
						"rate": 5000,
						"warehouse": KHO,
						"batch_no": lo_het_han,
						"use_serial_batch_fields": 1,
					}
				],
			}
		)
		dn.insert(ignore_permissions=True)

		kq = quet_de_lay(dn.name, lo_het_han)
		self.assertEqual(kq["loai"], "lo")
		self.assertTrue(kq["het_han"])

	def test_phieu_tra_hang_khong_hien_trong_danh_sach(self):
		"""VÒNG SỬA CUỐI (review toàn nhánh, Minor 6a): phiếu trả (`is_return=1`)
		có `qty` ÂM — mở ra quét chỉ nhận câu báo khó hiểu, `danh_sach_phieu_giao`
		phải lọc bỏ ngay trong SQL."""
		from erpnext.warehouse_operations.vitri.lay_hang import danh_sach_phieu_giao

		tra = frappe.get_doc(
			{
				"doctype": "Delivery Note",
				"company": CTY,
				"customer": KHACH,
				"posting_date": nowdate(),
				"is_return": 1,
				"items": [
					{
						"item_code": ITEM,
						"qty": -1,
						"rate": 5000,
						"warehouse": KHO,
						"batch_no": LO,
						"use_serial_batch_fields": 1,
					}
				],
			}
		)
		tra.insert(ignore_permissions=True)

		ten_phieu = {d["name"] for d in danh_sach_phieu_giao(KHO)["phieu"]}
		self.assertNotIn(tra.name, ten_phieu)


class TestGhiChoTrang(FrappeTestCase):
	def setUp(self):
		from erpnext.warehouse_operations.vitri.lay_hang import _khoa_chot_thieu

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
		frappe.cache().delete_value(_khoa_chot_thieu(self.dn.name))

	def tearDown(self):
		from erpnext.warehouse_operations.vitri.lay_hang import _khoa_chot_thieu

		frappe.set_user("Administrator")
		frappe.cache().delete_value(_khoa_chot_thieu(self.dn.name))
		frappe.db.rollback(save_point=DIEM_TEST)

	def test_ghi_da_lay_luu_ngay_len_phieu(self):
		from erpnext.warehouse_operations.vitri.lay_hang import ghi_da_lay

		p = ghi_da_lay(self.dn.name, self.dong, LO, O_GAN, 5)
		self.assertEqual(p["dong"][0]["da_lay"], 5.0)
		doc = frappe.get_doc("Delivery Note", self.dn.name)
		self.assertEqual(len(doc.custom_phan_bo_vi_tri), 1)
		self.assertEqual(doc.custom_phan_bo_vi_tri[0].nguoi_lay, frappe.session.user)

	def test_quet_lai_cung_o_thi_cong_don(self):
		from erpnext.warehouse_operations.vitri.lay_hang import ghi_da_lay

		ghi_da_lay(self.dn.name, self.dong, LO, O_GAN, 5)
		p = ghi_da_lay(self.dn.name, self.dong, LO, O_GAN, 3)
		self.assertEqual(len(p["dong"][0]["da_lay_o"]), 1)
		self.assertEqual(p["dong"][0]["da_lay"], 8.0)

	def test_ghi_da_lay_toi_da_theo_o_cat_theo_ton_khi_bat_co(self):
		"""Bài test BẮT BUỘC (sửa lỗi "số lượng mặc định không tự cắt theo tồn
		của ô"): trang đặt số lượng mặc định = toàn bộ phần còn thiếu của dòng
		(12, xem `setUp`) — quét một ô chỉ có ÍT hơn (O_XA = 10) với cờ
		`lay_toi_da_theo_o` bật phải ghi đúng TỒN CỦA Ô (10), không ném, và trả
		đúng số THẬT đã ghi để trang báo."""
		from erpnext.warehouse_operations.vitri.lay_hang import ghi_da_lay

		p = ghi_da_lay(self.dn.name, self.dong, LO, O_XA, 12, lay_toi_da_theo_o=1)
		self.assertEqual(p["so_luong_da_ghi"], 10.0)
		self.assertEqual(p["dong"][0]["da_lay"], 10.0)
		self.assertEqual(len(p["dong"][0]["da_lay_o"]), 1)
		self.assertEqual(p["dong"][0]["da_lay_o"][0]["so_luong"], 10.0)

	def test_ghi_da_lay_khong_bat_co_van_chan_chot_am(self):
		"""Chốt ÂM cho hành vi CŨ: không truyền `lay_toi_da_theo_o` (mặc định
		0) thì phải vẫn bị chặn như trước bản vá — không được âm thầm đổi hành
		vi cho lời gọi không mang cờ."""
		from erpnext.warehouse_operations.vitri.lay_hang import ghi_da_lay

		with self.assertRaisesRegex(frappe.ValidationError, "chỉ còn"):
			ghi_da_lay(self.dn.name, self.dong, LO, O_XA, 12)
		self.assertEqual(
			frappe.get_all("Location Allocation", {"parent": self.dn.name}),
			[],
			"chặn rồi thì không ghi lượt nào cả",
		)

	def test_ghi_da_lay_toi_da_theo_o_khi_da_het_sach_o_van_chan_nhu_cu(self):
		"""Tồn còn lại của ô `<= 0` (ĐÃ lấy hết sạch ô đó qua các lượt trước
		trên CHÍNH phiếu này) thì KHÔNG được cắt số về 0 hay số âm — để nguyên
		`so_luong` yêu cầu, cho lớp kiểm sớm chặn với câu báo "chỉ còn…" như
		hiện nay (đúng hành vi cũ cho ca hết sạch ô)."""
		from erpnext.warehouse_operations.vitri.lay_hang import ghi_da_lay

		# Lấy hết sạch O_XA (10) trước — vẫn dùng cờ, không ảnh hưởng vì tồn
		# ban đầu (10) đủ cho yêu cầu (10).
		p = ghi_da_lay(self.dn.name, self.dong, LO, O_XA, 10, lay_toi_da_theo_o=1)
		self.assertEqual(p["so_luong_da_ghi"], 10.0)

		with self.assertRaisesRegex(frappe.ValidationError, "chỉ còn"):
			ghi_da_lay(self.dn.name, self.dong, LO, O_XA, 2, lay_toi_da_theo_o=1)

	def test_ghi_da_lay_lo_het_han_bi_chan(self):
		"""VÒNG SỬA CUỐI (review toàn nhánh, Critical 3): CHẶN ngay ở tầng máy
		chủ, không chỉ ở trang — `ghi_da_lay` là endpoint gọi thẳng được, đường
		API không được phép là lối thoát cho một lô đã hết hạn. Dùng đúng ca
		"lô ĐANG CHỐT trên phiếu hết hạn giữa lúc phiếu nằm nháp" (posting_date
		cố định trước khi lô hết hạn) — cùng kịch bản của
		`TestDocChoTrang.test_quet_lo_dang_chot_da_het_han_bao_het_han`."""
		from erpnext.warehouse_operations.vitri.lay_hang import ghi_da_lay

		lo_het_han = "9L-LO-LAY-HET-HAN-03"
		han_da_qua = add_days(nowdate(), -3)
		ngay_dang_phieu = add_days(nowdate(), -14)
		if not frappe.db.exists("Batch", lo_het_han):
			frappe.get_doc(
				{"doctype": "Batch", "batch_id": lo_het_han, "item": ITEM, "expiry_date": han_da_qua}
			).insert(ignore_permissions=True)

		dn = frappe.get_doc(
			{
				"doctype": "Delivery Note",
				"company": CTY,
				"customer": KHACH,
				"posting_date": ngay_dang_phieu,
				"set_posting_time": 1,
				"items": [
					{
						"item_code": ITEM,
						"qty": 5,
						"rate": 5000,
						"warehouse": KHO,
						"batch_no": lo_het_han,
						"use_serial_batch_fields": 1,
					}
				],
			}
		)
		dn.insert(ignore_permissions=True)

		with self.assertRaisesRegex(frappe.ValidationError, "hết hạn"):
			ghi_da_lay(dn.name, dn.items[0].name, lo_het_han, O_GAN, 5)
		self.assertEqual(
			frappe.get_all("Location Allocation", {"parent": dn.name}),
			[],
			"chặn rồi thì không ghi lượt nào cả",
		)

	def test_ghi_da_lay_chan_dong_dung_serial_and_batch_bundle(self):
		"""VÒNG SỬA CUỐI (review toàn nhánh, Minor 6b): `ghi_da_lay` là hàm ghi
		DUY NHẤT của module chưa gọi `_chan_bundle_serial_batch` — thêm cho
		đồng bộ với `doi_lo`/`tach_dong_theo_lo`/`chot_thieu`/`hoan_tat`."""
		from erpnext.warehouse_operations.vitri.lay_hang import ghi_da_lay

		frappe.db.set_value(
			"Delivery Note Item", self.dong, "serial_and_batch_bundle", "9L-BUNDLE-GIA-LAP"
		)
		with self.assertRaisesRegex(frappe.ValidationError, "Serial & Batch Bundle"):
			ghi_da_lay(self.dn.name, self.dong, LO, O_GAN, 5)

	def test_bo_dong_da_lay(self):
		from erpnext.warehouse_operations.vitri.lay_hang import bo_dong_da_lay, ghi_da_lay

		p = ghi_da_lay(self.dn.name, self.dong, LO, O_GAN, 5)
		ten = p["dong"][0]["da_lay_o"][0]["name"]
		p2 = bo_dong_da_lay(self.dn.name, ten)
		self.assertEqual(p2["dong"][0]["da_lay"], 0.0)

	def test_bo_dong_khong_ton_tai_bi_chan(self):
		"""Một phép 'bỏ' tưởng thành công mà thực ra không làm gì (hai tab
		cùng bấm, hoặc bấm hai lần) là đúng loại lỗi module này phải tránh."""
		from erpnext.warehouse_operations.vitri.lay_hang import bo_dong_da_lay

		with self.assertRaisesRegex(frappe.ValidationError, "không tồn tại"):
			bo_dong_da_lay(self.dn.name, "khong-co-dong-nay")

	def test_doi_lo_sua_dong_phieu_giao(self):
		from erpnext.warehouse_operations.vitri.lay_hang import doi_lo

		lo2 = "9L-LO-LAY-03"
		if not frappe.db.exists("Batch", lo2):
			frappe.get_doc(
				{"doctype": "Batch", "batch_id": lo2, "item": ITEM, "expiry_date": "2028-01-31"}
			).insert(ignore_permissions=True)
		doi_lo(self.dn.name, self.dong, lo2)
		self.assertEqual(frappe.db.get_value("Delivery Note Item", self.dong, "batch_no"), lo2)

	def test_doi_lo_sang_lo_khong_ton_tai_bi_chan(self):
		from erpnext.warehouse_operations.vitri.lay_hang import doi_lo

		with self.assertRaisesRegex(frappe.ValidationError, "không tồn tại"):
			doi_lo(self.dn.name, self.dong, "9L-LO-KHONG-CO-THAT")

	def test_hoan_tat_duyet_phieu_va_tru_dung_o(self):
		from erpnext.warehouse_operations.vitri.lay_hang import ghi_da_lay, hoan_tat

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
		from erpnext.warehouse_operations.vitri.lay_hang import chot_thieu, ghi_da_lay, hoan_tat

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
		from erpnext.warehouse_operations.vitri.lay_hang import ghi_da_lay, hoan_tat

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
		from erpnext.warehouse_operations.vitri.lay_hang import ghi_da_lay, hoan_tat

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

		from erpnext.warehouse_operations.vitri.lay_hang import chot_thieu, ghi_da_lay, hoan_tat

		ghi_da_lay(self.dn.name, self.dong, LO, O_GAN, 7)
		chot_thieu(self.dn.name, self.dong)

		with patch(
			"erpnext.warehouse_operations.vitri.hook_sle._ghi_mot_phan",
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
		from erpnext.warehouse_operations.vitri.lay_hang import ghi_da_lay, hoan_tat

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
		with bo_kiem_o_tem():
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

		from erpnext.warehouse_operations.vitri.lay_hang import ghi_da_lay, hoan_tat

		ghi_da_lay(self.dn.name, self.dong, LO, O_GAN, 12)

		with patch(
			"erpnext.warehouse_operations.vitri.hook_sle._ghi_mot_phan",
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
		from erpnext.warehouse_operations.vitri.lay_hang import ghi_da_lay, hoan_tat

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
		from erpnext.warehouse_operations.vitri.lay_hang import ghi_da_lay, hoan_tat, mo_phieu_giao

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
		# Minor (vòng sửa 1/5, bắt buộc): `so_dong` chỉ đếm dòng THUỘC KHO
		# QUẢN LÝ VỊ TRÍ (1), không đếm cả dòng `can_quet=False` (2 dòng) mà
		# chính `hoan_tat` vừa bỏ qua.
		self.assertEqual(kq["so_dong"], 1)
		self.assertEqual(frappe.db.get_value("Delivery Note", dn2.name, "docstatus"), 1)

	def test_khong_co_quyen_ghi_thi_ca_nam_ham_bi_chan(self):
		"""`_kiem_tra_quyen()` chặn theo vai trò TOÀN CỤC — cùng bài
		`test_khong_co_vai_tro_kho_thi_bi_chan` ở phần ĐỌC, khoá lại cho cả
		năm hàm GHI."""
		from erpnext.warehouse_operations.vitri.lay_hang import (
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
		from erpnext.warehouse_operations.vitri.lay_hang import chot_thieu, ghi_da_lay, hoan_tat

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
		self.assertEqual(kq["so_dong"], 1)
		self.assertEqual(frappe.db.get_value("Delivery Note", dn2.name, "docstatus"), 1)
		self.assertEqual(flt(frappe.db.get_value("Delivery Note Item", dong2, "qty")), 6.0)
		don_ban.reload()
		self.assertEqual(flt(don_ban.items[0].delivered_qty), 6.0)

		# Minor (vòng sửa 1/5, bắt buộc): số phái sinh phải tính lại đúng theo
		# `qty` MỚI (6, không phải 10 gốc) — `amount`/`stock_qty` của dòng và
		# `total`/`grand_total` của phiếu, không chỉ riêng `qty`.
		doc = frappe.get_doc("Delivery Note", dn2.name)
		self.assertEqual(flt(doc.items[0].amount), 30000.0)
		self.assertEqual(flt(doc.items[0].stock_qty), 6.0)
		self.assertEqual(flt(doc.total), 30000.0)
		self.assertEqual(flt(doc.grand_total), 30000.0)

	# ------------------------------------------------------------------
	# VÒNG SỬA 1/5 (18/09/2026, review điều phối model mạnh): 1 Critical +
	# 3 Important + vài Minor. Xem lay_hang.py cho chi tiết từng chỗ sửa.
	# ------------------------------------------------------------------

	def test_mo_phieu_giao_phan_anh_da_chot_thieu_va_go_duoc(self):
		"""Critical, bài bắt buộc (a): `mo_phieu_giao` phải phản ánh ĐÚNG
		`da_chot_thieu` sau khi bấm và sau khi gỡ (`bo_chot_thieu`) — trước
		sửa này, cờ hoàn toàn VÔ HÌNH trên trang: người ca sau mở lại phiếu
		thấy màn hình giống hệt trước khi cờ được bấm."""
		from erpnext.warehouse_operations.vitri.lay_hang import bo_chot_thieu, chot_thieu, mo_phieu_giao

		truoc = mo_phieu_giao(self.dn.name)["dong"][0]
		self.assertFalse(truoc["da_chot_thieu"])
		self.assertIsNone(truoc["chot_thieu_boi"])
		self.assertIsNone(truoc["chot_thieu_luc"])

		chot_thieu(self.dn.name, self.dong)
		sau = mo_phieu_giao(self.dn.name)["dong"][0]
		self.assertTrue(sau["da_chot_thieu"])
		self.assertEqual(sau["chot_thieu_boi"], frappe.session.user)
		self.assertIsNotNone(sau["chot_thieu_luc"])

		bo_chot_thieu(self.dn.name, self.dong)
		sau_go = mo_phieu_giao(self.dn.name)["dong"][0]
		self.assertFalse(sau_go["da_chot_thieu"])
		self.assertIsNone(sau_go["chot_thieu_boi"])

	def test_bo_chot_thieu_khi_chua_chot_bi_chan(self):
		"""Cùng nguyên tắc `bo_dong_da_lay`: một phép "gỡ" tưởng thành công mà
		thực ra không làm gì là đúng loại lỗi module này phải tránh."""
		from erpnext.warehouse_operations.vitri.lay_hang import bo_chot_thieu

		with self.assertRaisesRegex(frappe.ValidationError, "chưa được chốt thiếu"):
			bo_chot_thieu(self.dn.name, self.dong)

	def test_co_chot_thieu_boi_nguoi_khac_hien_dung_ten_cho_nguoi_sau(self):
		"""Critical, bài bắt buộc (b): cờ do NGƯỜI A đặt phải hiện ra cho
		NGƯỜI B kèm ĐÚNG TÊN A — khẳng định PAYLOAD thật (`chot_thieu_boi`),
		không chỉ khẳng định "gọi không nổ". Đây chính là ca hỏng thật đã nêu:
		A bấm rồi bỏ dở ca, B mở lại phiếu ở ca sau."""
		from erpnext.warehouse_operations.vitri.lay_hang import chot_thieu, mo_phieu_giao

		nguoi_b = "lay-hang-nguoi-b@mo-phong.local"
		if not frappe.db.exists("User", nguoi_b):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": nguoi_b,
					"first_name": "Nguoi B",
					"send_welcome_email": 0,
					"roles": [{"role": "Stock User"}],
				}
			).insert(ignore_permissions=True)

		nguoi_a = frappe.session.user  # Administrator, đóng vai "ca sáng".
		chot_thieu(self.dn.name, self.dong)

		frappe.set_user(nguoi_b)
		dong_b = mo_phieu_giao(self.dn.name)["dong"][0]
		self.assertTrue(dong_b["da_chot_thieu"])
		self.assertEqual(dong_b["chot_thieu_boi"], nguoi_a)

	def test_chot_thieu_dong_o_kho_khong_bat_vi_tri_bi_chan(self):
		"""Minor: `hoan_tat` bỏ qua dòng thuộc kho không quản lý vị trí, nên
		"chốt thiếu" trên dòng đó trước sửa này là một cờ không bao giờ được
		đọc lại — no-op câm, dễ khiến thủ kho tưởng đã xử lý xong."""
		from erpnext.warehouse_operations.vitri.lay_hang import chot_thieu

		kho_khac = "Hàng trả về - MYN"
		dn2 = frappe.get_doc(
			{
				"doctype": "Delivery Note",
				"company": CTY,
				"customer": KHACH,
				"posting_date": nowdate(),
				"items": [
					{
						"item_code": ITEM,
						"qty": 4,
						"rate": 5000,
						"warehouse": kho_khac,
						"batch_no": LO,
						"use_serial_batch_fields": 1,
					}
				],
			}
		)
		dn2.insert(ignore_permissions=True)
		with self.assertRaisesRegex(frappe.ValidationError, "không quản lý vị trí"):
			chot_thieu(dn2.name, dn2.items[0].name)

	def test_bo_dong_da_lay_khi_mot_o_da_bi_rut_can(self):
		"""Important 1, bài bắt buộc: dòng hàng có 2 dòng phân bổ, MỘT ô bị
		rút cạn bởi MỘT phiếu chuyển vị trí khác sau khi đã quét — trước sửa
		này `bo_dong_da_lay` bị kẹt cứng vì `kiem_phan_bo_khi_luu` so tồn cho
		MỌI dòng phân bổ còn lại, kể cả dòng không liên quan gì tới thao tác
		bỏ. `doc.flags.vi_tri_kho_dang_bo_phan_bo` phải cho lưu đi qua."""
		from erpnext.warehouse_operations.vitri.lay_hang import bo_dong_da_lay, ghi_da_lay

		dn2 = _phieu_giao(20)
		dong2 = dn2.items[0].name
		ghi_da_lay(dn2.name, dong2, LO, O_GAN, 12)
		p = ghi_da_lay(dn2.name, dong2, LO, O_XA, 8)
		ten_xa = next(x["name"] for x in p["dong"][0]["da_lay_o"] if x["o"] == O_XA)

		# Ai đó rút cạn O_GAN bằng MỘT phiếu chuyển vị trí khác, không liên
		# quan gì tới `dn2`.
		chuyen = frappe.get_doc(
			{
				"doctype": "Location Transfer",
				"kho": KHO,
				"ngay": nowdate(),
				"items": [
					{"vat_tu": ITEM, "so_lo": LO, "tu_o": O_GAN, "den_o": O_XA, "so_luong": 20}
				],
			}
		)
		with bo_kiem_o_tem():
			chuyen.insert(ignore_permissions=True)
			chuyen.submit()
		self.assertEqual(so.ton_o(O_GAN, ITEM, LO), 0.0)

		# TRƯỚC sửa: chặn "ô 9L01010101 chỉ còn 0" vì dòng O_GAN (12) còn lại
		# giờ vượt tồn. SAU sửa: bỏ được.
		p2 = bo_dong_da_lay(dn2.name, ten_xa)
		self.assertEqual(len(p2["dong"][0]["da_lay_o"]), 1)
		self.assertEqual(p2["dong"][0]["da_lay_o"][0]["o"], O_GAN)

	def test_doi_lo_chan_dong_dung_serial_and_batch_bundle(self):
		"""Important 2, bài bắt buộc cho ít nhất một hàm: dòng đã chốt lô qua
		bảng Serial & Batch Bundle (Pick List, hoặc hộp thoại chọn lô/serial
		trên form) — `doi_lo` phải chặn SỚM bằng câu tiếng Việt, không để
		`batch_no` lệch bundle âm thầm tới tận lúc duyệt."""
		from erpnext.warehouse_operations.vitri.lay_hang import doi_lo

		frappe.db.set_value(
			"Delivery Note Item", self.dong, "serial_and_batch_bundle", "9L-BUNDLE-GIA-LAP"
		)
		with self.assertRaisesRegex(frappe.ValidationError, "Serial & Batch Bundle"):
			doi_lo(self.dn.name, self.dong, LO)

	def test_hoan_tat_chan_dong_dung_bundle_khi_can_ha_qty(self):
		"""Important 2: `hoan_tat` cũng phải chặn SỚM bằng câu tiếng Việt khi
		dòng cần HẠ `qty` (đã chốt thiếu) mà lại đang dùng Serial & Batch
		Bundle — nếu không, `validate_quantity` của bundle ném lỗi tiếng Anh
		("Total quantity does not match") ngay giữa savepoint."""
		from erpnext.warehouse_operations.vitri.lay_hang import chot_thieu, ghi_da_lay, hoan_tat

		ghi_da_lay(self.dn.name, self.dong, LO, O_GAN, 7)
		chot_thieu(self.dn.name, self.dong)
		frappe.db.set_value(
			"Delivery Note Item", self.dong, "serial_and_batch_bundle", "9L-BUNDLE-GIA-LAP"
		)
		with self.assertRaisesRegex(frappe.ValidationError, "Serial & Batch Bundle"):
			hoan_tat(self.dn.name)
		self.assertEqual(frappe.db.get_value("Delivery Note", self.dn.name, "docstatus"), 0)

	def test_ghi_da_lay_bao_xung_dot_tieng_viet_khi_hai_nguoi_cung_sua(self):
		"""Important 3, bài bắt buộc: `TimestampMismatchError` không được lộ
		tiếng Anh kỹ thuật ra thủ kho. Mô phỏng "người khác" lưu một thay đổi
		độc lập lên CHÍNH phiếu này NGAY GIỮA lúc `ghi_da_lay` đã tải xong
		`doc` và đang chuẩn bị lưu — patch `_dong_cua` (điểm mà `ghi_da_lay`
		gọi ngay sau khi `_mo_de_ghi()` tải doc) để tự nó chèn một lần lưu
		độc lập trước khi hàm gốc kịp `save()` bản của mình."""
		from unittest.mock import patch

		import erpnext.warehouse_operations.vitri.lay_hang as lay_hang_mod

		goc = lay_hang_mod._dong_cua

		def _dong_cua_roi_nguoi_khac_sua(doc, dong_hang):
			ket_qua = goc(doc, dong_hang)
			khac = frappe.get_doc("Delivery Note", doc.name)
			khac.save()
			return ket_qua

		with patch.object(lay_hang_mod, "_dong_cua", side_effect=_dong_cua_roi_nguoi_khac_sua):
			with self.assertRaisesRegex(frappe.ValidationError, "vừa được người khác sửa"):
				lay_hang_mod.ghi_da_lay(self.dn.name, self.dong, LO, O_GAN, 5)

	# ------------------------------------------------------------------
	# VÒNG SỬA 2/5 (18/09/2026, re-review model mạnh): hỏng MỚI do chính
	# vòng sửa 1 gây ra — đổi định dạng cờ LIST -> DICT mà không kiểm kiểu,
	# nổ `mo_phieu_giao`/`chot_thieu`/`bo_chot_thieu` cho phiếu nào đang mang
	# cờ kiểu cũ (còn sống theo TTL 24h cũ). Xem `lay_hang.py` cho chi tiết.
	# ------------------------------------------------------------------

	def test_du_lieu_cu_dang_list_trong_redis_khong_lam_no_ham_nao(self):
		"""Important (vòng sửa 2/5), bài bắt buộc: ghi thẳng một giá trị LIST
		vào ĐÚNG khoá cache (định dạng trước vòng sửa 1) rồi gọi lần lượt
		`mo_phieu_giao`, `chot_thieu`, `bo_chot_thieu` — cả ba phải chạy bình
		thường, không ném lỗi kiểu (`'list' object has no attribute 'get'`,
		`list indices must be integers`). Đây đúng là nhóm phiếu mà bản vá
		sinh ra để bảo vệ (đang lấy dở, mang cờ chốt thiếu của phiên bản
		trước) — không được để nó tự nổ 500 ngay sau khi nâng code."""
		from erpnext.warehouse_operations.vitri.lay_hang import (
			_khoa_chot_thieu,
			bo_chot_thieu,
			chot_thieu,
			mo_phieu_giao,
		)

		frappe.cache().set_value(_khoa_chot_thieu(self.dn.name), [self.dong], expires_in_sec=86400)

		# mo_phieu_giao không được ném lỗi kiểu; dữ liệu cũ coi như rỗng chứ
		# không phải "cờ thật" (guard chỉ chấp nhận dict).
		p = mo_phieu_giao(self.dn.name)
		self.assertFalse(p["dong"][0]["da_chot_thieu"])

		# chot_thieu không được ném lỗi kiểu — tự thay bằng dict mới, đúng
		# định dạng, ghi đè lên giá trị list cũ.
		chot_thieu(self.dn.name, self.dong)
		sau = mo_phieu_giao(self.dn.name)["dong"][0]
		self.assertTrue(sau["da_chot_thieu"])
		self.assertEqual(sau["chot_thieu_boi"], frappe.session.user)

		# bo_chot_thieu không được ném lỗi kiểu — gỡ đúng dòng vừa chốt lại.
		bo_chot_thieu(self.dn.name, self.dong)
		self.assertFalse(mo_phieu_giao(self.dn.name)["dong"][0]["da_chot_thieu"])

	def test_khoa_chot_thieu_doi_ten_co_hau_to_phien_ban(self):
		"""Important (vòng sửa 2/5): khoá Redis đổi tên — dữ liệu LIST cũ (nếu
		còn sống ở khoá CŨ) không bao giờ bị đọc nhầm định dạng, không cần chờ
		TTL cũ hết hay dọn tay.

		VÒNG SỬA CUỐI (review toàn nhánh, Minor 5): bỏ `assertIn(":v2:", ...)`
		— đó là khẳng định vào CHI TIẾT CÀI ĐẶT (hậu tố phiên bản cụ thể), không
		phải HÀNH VI. Lần đổi tiếp sang `:v3:` (hoặc bỏ hẳn hậu tố, đổi cách
		đặt tên khác) sẽ làm bài này đỏ dù không có hành vi nào sai. Giữ đúng
		vế còn có ý nghĩa: khoá MỚI phải khác khoá CŨ."""
		from erpnext.warehouse_operations.vitri.lay_hang import _khoa_chot_thieu

		khoa_cu = f"vi_tri_kho:lay_hang:chot_thieu:{self.dn.name}"
		self.assertNotEqual(_khoa_chot_thieu(self.dn.name), khoa_cu)

	def test_chot_thieu_som_khong_bi_keo_dai_boi_lan_chot_muon_hon(self):
		"""Minor (vòng sửa 2/5): `chot_thieu` phải `set_value(...,
		expires_in_sec=_TTL_CHOT_THIEU)` lại cho CẢ khoá mỗi lần gọi (để dòng
		MỚI chốt không bị xoá theo TTL của lần set trước) — hệ quả phụ nếu
		không lọc theo `luc` từng dòng khi ĐỌC: dòng chốt SỚM bị "kéo dài"
		theo TTL của dòng chốt SAU. Ở đây khẳng định trực tiếp cơ chế lọc:
		một dòng có `luc` giả lập QUÁ 8 giờ trước phải bị `_doc_chot_thieu`
		coi là hết hạn dù khoá Redis (TTL riêng) vẫn còn sống."""
		from frappe.utils import add_to_date, now

		from erpnext.warehouse_operations.vitri.lay_hang import _doc_chot_thieu, _khoa_chot_thieu

		luc_qua_han = add_to_date(now(), hours=-9)
		luc_con_han = add_to_date(now(), hours=-1)
		frappe.cache().set_value(
			_khoa_chot_thieu(self.dn.name),
			{
				"dong-qua-han": {"boi": "a@vidu.local", "luc": luc_qua_han},
				"dong-con-han": {"boi": "b@vidu.local", "luc": luc_con_han},
			},
			expires_in_sec=86400,  # TTL khoá còn dài — lọc phải tự đứng riêng.
		)

		con_hieu_luc = _doc_chot_thieu(self.dn.name)
		self.assertNotIn("dong-qua-han", con_hieu_luc)
		self.assertIn("dong-con-han", con_hieu_luc)

	# ------------------------------------------------------------------
	# Task 6 (18/09/2026): tách dòng phiếu giao khi một dòng lấy từ hai lô.
	# ------------------------------------------------------------------

	def test_tach_dong_khi_lay_tu_hai_lo(self):
		"""Lô cũ chỉ còn 8/12 → tách: dòng cũ 8 lô cũ, dòng mới 4 lô mới."""
		from erpnext.warehouse_operations.vitri.lay_hang import ghi_da_lay, hoan_tat, tach_dong_theo_lo

		lo2 = "9L-LO-LAY-04"
		if not frappe.db.exists("Batch", lo2):
			frappe.get_doc(
				{"doctype": "Batch", "batch_id": lo2, "item": ITEM, "expiry_date": "2027-07-31"}
			).insert(ignore_permissions=True)
		_nhap_kho_lo(lo2, 10)
		_chuyen_vao_o_lo(lo2, [(O_XA, 10)])

		ghi_da_lay(self.dn.name, self.dong, LO, O_GAN, 8)
		p = tach_dong_theo_lo(self.dn.name, self.dong, lo2)

		self.assertEqual(len(p["dong"]), 2)
		cu = next(d for d in p["dong"] if d["dong_hang"] == self.dong)
		moi = next(d for d in p["dong"] if d["dong_hang"] != self.dong)
		self.assertEqual((cu["so_lo"], cu["can_lay"], cu["da_lay"]), (LO, 8.0, 8.0))
		self.assertEqual((moi["so_lo"], moi["can_lay"], moi["da_lay"]), (lo2, 4.0, 0.0))

		ghi_da_lay(self.dn.name, moi["dong_hang"], lo2, O_XA, 4)
		hoan_tat(self.dn.name)

		self.assertEqual(so.ton_o(O_GAN, ITEM, LO), 12.0)
		self.assertEqual(so.ton_o(O_XA, ITEM, lo2), 6.0)

	def test_tach_dong_khi_chua_lay_gi_thi_bi_chan(self):
		"""Chưa lấy được gì của lô cũ thì đó là ĐỔI LÔ, không phải tách."""
		from erpnext.warehouse_operations.vitri.lay_hang import tach_dong_theo_lo

		with self.assertRaisesRegex(frappe.ValidationError, "chưa lấy được gì"):
			tach_dong_theo_lo(self.dn.name, self.dong, LO)

	def test_tach_dong_khi_da_lay_du_thi_bi_chan(self):
		"""Important 2 (vòng sửa 1/5, review điều phối): điều kiện biên còn lại
		của `tach_dong_theo_lo` — dòng đã lấy ĐỦ, không còn phần dư để tách.
		Viết đúng ngay từ Step 3 nhưng chưa từng có bài đỏ/xanh riêng cho nó."""
		from erpnext.warehouse_operations.vitri.lay_hang import ghi_da_lay, tach_dong_theo_lo

		ghi_da_lay(self.dn.name, self.dong, LO, O_GAN, 12)
		with self.assertRaisesRegex(frappe.ValidationError, "đã lấy đủ"):
			tach_dong_theo_lo(self.dn.name, self.dong, "9L-LO-KHONG-CAN-TON-TAI")

	def test_tach_dong_tren_phieu_giao_tu_don_ban_khong_dem_hai_lan(self):
		"""Important 1 (vòng sửa 1/5, review điều phối): nhánh spec §8 "dễ sai
		nhất" — tách dòng trên một phiếu giao SINH TỪ ĐƠN BÁN. Cả hai dòng sau
		tách cùng trỏ một `Sales Order Item` (`so_detail` chép nguyên từ
		`d.as_dict()`) — khẳng định rollup `delivered_qty`/`per_delivered`
		CỘNG ĐÚNG tổng hai dòng (không đếm hai lần), không chỉ "gọi không nổ",
		và tồn theo Ô của CẢ HAI lô đúng sau khi duyệt."""
		from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note
		from erpnext.warehouse_operations.vitri.lay_hang import ghi_da_lay, hoan_tat, tach_dong_theo_lo

		lo2 = "9L-LO-LAY-04"
		if not frappe.db.exists("Batch", lo2):
			frappe.get_doc(
				{"doctype": "Batch", "batch_id": lo2, "item": ITEM, "expiry_date": "2027-07-31"}
			).insert(ignore_permissions=True)
		_nhap_kho_lo(lo2, 10)
		_chuyen_vao_o_lo(lo2, [(O_XA, 10)])

		don_ban = frappe.get_doc(
			{
				"doctype": "Sales Order",
				"company": CTY,
				"customer": KHACH,
				"delivery_date": nowdate(),
				"items": [
					{
						"item_code": ITEM,
						"qty": 12,
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
		# Minor 2 (vòng sửa 1/5, review điều phối): đặt weight_per_unit > 0 để
		# bài này CHỨNG MINH được phép tính lại `total_weight`/`total_net_weight`
		# theo qty MỚI — vật tư chung của module (`ITEM`) không có
		# weight_per_unit nên các bài khác chỉ đi qua nhánh "không có thì 0",
		# không tự nó khoá được công thức nhân.
		dn2.items[0].weight_per_unit = 2.5
		dn2.insert(ignore_permissions=True)
		dong2 = dn2.items[0].name

		ghi_da_lay(dn2.name, dong2, LO, O_GAN, 8)
		p = tach_dong_theo_lo(dn2.name, dong2, lo2)
		moi = next(d for d in p["dong"] if d["dong_hang"] != dong2)
		self.assertEqual((moi["so_lo"], moi["can_lay"]), (lo2, 4.0))

		# Minor 2: dòng cũ (8 x 2.5) + dòng mới (4 x 2.5) = tổng phiếu (12 x 2.5)
		# — không dòng nào còn mang trọng lượng tính theo qty=12 CŨ.
		self.assertEqual(flt(frappe.db.get_value("Delivery Note Item", dong2, "total_weight")), 20.0)
		self.assertEqual(
			flt(frappe.db.get_value("Delivery Note Item", moi["dong_hang"], "total_weight")), 10.0
		)
		self.assertEqual(flt(frappe.db.get_value("Delivery Note", dn2.name, "total_net_weight")), 30.0)

		ghi_da_lay(dn2.name, moi["dong_hang"], lo2, O_XA, 4)
		kq = hoan_tat(dn2.name)

		self.assertEqual(kq["so_dong"], 2)
		self.assertEqual(frappe.db.get_value("Delivery Note", dn2.name, "docstatus"), 1)

		don_ban.reload()
		self.assertEqual(flt(don_ban.items[0].delivered_qty), 12.0, "không đếm hai lần")
		self.assertEqual(flt(don_ban.per_delivered), 100.0)

		self.assertEqual(so.ton_o(O_GAN, ITEM, LO), 12.0)
		self.assertEqual(so.ton_o(O_XA, ITEM, lo2), 6.0)


class TestDongKhongPhaiHangTonKho(FrappeTestCase):
	"""VÒNG SỬA CUỐI (review toàn nhánh, Critical 1): dòng phí vận chuyển/dịch
	vụ/hàng đặt ngoài/dòng cha Product Bundle — ERPNext vẫn gán `warehouse` cho
	chúng dù không phải hàng tồn kho. TRƯỚC bản vá này, `can_quet` chỉ hỏi
	`kho_co_quan_ly_vi_tri(d.warehouse)`: dòng loại này vẫn hiện lên đòi quét,
	nhưng `ton_o` của chúng luôn 0 nên quét gì cũng bị chặn "ô chỉ còn 0",
	trong khi `hoan_tat` lại đòi đúng dòng đó "đã lấy đủ" — phiếu kẹt cứng cả
	hai chiều, lối thoát duy nhất trước đây là gỡ từng lượt quét rồi về máy
	tính duyệt tay.
	"""

	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.savepoint(DIEM_TEST)
		_vat_tu()
		_lo()
		_vat_tu_dich_vu()
		_o(O_GAN)
		_nhap_kho(30)
		_chuyen_vao_o([(O_GAN, 30)])

		self.dn = frappe.get_doc(
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
					{"item_code": ITEM_DICH_VU, "qty": 1, "rate": 200000, "warehouse": KHO},
				],
			}
		)
		self.dn.insert(ignore_permissions=True)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point=DIEM_TEST)

	def test_dong_dich_vu_khong_can_quet_va_khong_khoa_hoan_tat(self):
		"""Bài chịu lực: quét và hoàn tất dòng hàng THẬT, `hoan_tat` phải duyệt
		được, `so_dong` không đếm dòng dịch vụ, và `mo_phieu_giao` phải trả
		`can_quet=False` kèm lý do cho dòng dịch vụ."""
		from erpnext.warehouse_operations.vitri.lay_hang import ghi_da_lay, hoan_tat, mo_phieu_giao

		p = mo_phieu_giao(self.dn.name)
		dong_dv = next(d for d in p["dong"] if d["vat_tu"] == ITEM_DICH_VU)
		self.assertFalse(dong_dv["can_quet"])
		self.assertIn("không quản lý tồn kho", dong_dv["ly_do_khong_quet"])

		dong_hang_that = next(d for d in p["dong"] if d["vat_tu"] == ITEM)["dong_hang"]
		ghi_da_lay(self.dn.name, dong_hang_that, LO, O_GAN, 5)
		kq = hoan_tat(self.dn.name)

		self.assertEqual(frappe.db.get_value("Delivery Note", self.dn.name, "docstatus"), 1)
		self.assertEqual(kq["so_dong"], 1, "so_dong không được đếm dòng dịch vụ")


class TestDongDaDonVi(FrappeTestCase):
	"""VÒNG SỬA CUỐI (review toàn nhánh, Important 2): dòng bán theo đơn vị
	KHÁC đơn vị tồn kho (`conversion_factor != 1`) không bao giờ quét lấy
	được — bảng phân bổ đo bằng đơn vị TỒN KHO trong khi lớp kiểm sớm và
	`mo_phieu_giao` nói chuyện bằng đơn vị GIAO DỊCH. Quyết định: CHẶN có chữ,
	không quy đổi toàn hệ (việc đó rộng, cần bộ test đa đơn vị riêng)."""

	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.savepoint(DIEM_TEST)
		_vat_tu_da_don_vi()
		_o(O_GAN)
		# Tồn CORE (Bin) đủ để `hoan_tat` submit được — dòng đa đơn vị bị
		# `_can_quet_dong` chặn khỏi sổ vị trí, nhưng ERPNext lõi vẫn đòi đủ
		# tồn kho THẬT của kho để duyệt phiếu giao, bất kể ô nào.
		se = frappe.get_doc(
			{
				"doctype": "Stock Entry",
				"stock_entry_type": "Material Receipt",
				"company": CTY,
				"items": [{"item_code": ITEM_DA_DON_VI, "qty": 30, "t_warehouse": KHO, "basic_rate": 5000}],
			}
		)
		se.insert(ignore_permissions=True)
		se.submit()

		self.dn = frappe.get_doc(
			{
				"doctype": "Delivery Note",
				"company": CTY,
				"customer": KHACH,
				"posting_date": nowdate(),
				"items": [
					{
						"item_code": ITEM_DA_DON_VI,
						"qty": 2,
						"uom": UOM_HOP,
						"conversion_factor": 10,
						"rate": 50000,
						"warehouse": KHO,
					}
				],
			}
		)
		self.dn.insert(ignore_permissions=True)
		self.dong = self.dn.items[0].name

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point=DIEM_TEST)

	def test_dong_da_don_vi_khong_can_quet_va_bi_hoan_tat_bo_qua(self):
		"""Bài test bắt buộc: `can_quet=False`, có `ly_do_khong_quet`, và
		`hoan_tat` bỏ qua đúng dòng đó (không đòi quét, vẫn duyệt được)."""
		from erpnext.warehouse_operations.vitri.lay_hang import hoan_tat, mo_phieu_giao

		p = mo_phieu_giao(self.dn.name)
		dong = p["dong"][0]
		self.assertFalse(dong["can_quet"])
		self.assertIsNotNone(dong["ly_do_khong_quet"])
		self.assertIn(UOM_HOP, dong["ly_do_khong_quet"])

		kq = hoan_tat(self.dn.name)
		self.assertEqual(frappe.db.get_value("Delivery Note", self.dn.name, "docstatus"), 1)
		self.assertEqual(kq["so_dong"], 0, "hoan_tat phải bỏ qua đúng dòng đa đơn vị")


class TestQuetMaHangKhongLo(FrappeTestCase):
	"""Vòng sửa sau review chất lượng Task 7 (điều phối, 18/09/2026): mặt hàng
	KHÔNG quản lý lô, thuộc kho CÓ quản lý vị trí, trước bản vá này KHÔNG quét
	được để bắt đầu lấy. `mo_phieu_giao` đã luôn trả dòng đó với `so_lo=None`,
	`can_quet=True` (đúng thiết kế), nhưng `quet_de_lay` chỉ nhận diện mã quét
	qua `scan_barcode(...).get("batch_no")` — quét mã hàng rơi thẳng vào
	`{"loai": None}`, và `hoan_tat` (đòi MỌI dòng thuộc kho quản lý vị trí phải
	lấy đủ) khoá cứng phiếu vĩnh viễn. Thủng đúng spec §6.2 ("trang phải quét
	được mọi dòng của phiếu").
	"""

	BARCODE_KHONG_LO = "9L-BARCODE-KHONG-LO-001"
	BARCODE_CO_LO = "9L-BARCODE-CO-LO-001"

	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.savepoint(DIEM_TEST)
		for ma in (ITEM, ITEM_KHONG_LO, O_GAN, self.BARCODE_KHONG_LO, self.BARCODE_CO_LO):
			frappe.cache().delete_value(f"erpnext:barcode_scan:{ma}")
		_vat_tu()
		_lo()
		_vat_tu_khong_lo()
		_o(O_GAN)
		_nhap_kho_khong_lo(10)
		_chuyen_vao_o_khong_lo([(O_GAN, 10)])
		self._gan_barcode(ITEM_KHONG_LO, self.BARCODE_KHONG_LO)
		self._gan_barcode(ITEM, self.BARCODE_CO_LO)

		self.dn = frappe.get_doc(
			{
				"doctype": "Delivery Note",
				"company": CTY,
				"customer": KHACH,
				"posting_date": nowdate(),
				"items": [{"item_code": ITEM_KHONG_LO, "qty": 6, "rate": 5000, "warehouse": KHO}],
			}
		)
		self.dn.insert(ignore_permissions=True)
		self.dong = self.dn.items[0].name

	def _gan_barcode(self, item_code, barcode):
		"""Mã vạch THẬT trên bao bì (`Item Barcode`) — đường thật của súng quét
		PDA, khác với `frappe.db.exists("Item", ma)` (mã quét trùng thẳng TÊN
		item, chỉ xảy ra khi gõ tay hoặc mã hàng không có mã vạch riêng). Cả hai
		đường phải nhận diện được cùng một cách, theo đúng mandate review."""
		doc = frappe.get_doc("Item", item_code)
		if not any(b.barcode == barcode for b in doc.barcodes):
			doc.append("barcodes", {"barcode": barcode})
			doc.save(ignore_permissions=True)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point=DIEM_TEST)

	def test_quet_ma_hang_khong_lo_ra_loai_lo_voi_so_lo_none(self):
		from erpnext.warehouse_operations.vitri.lay_hang import quet_de_lay

		kq = quet_de_lay(self.dn.name, ITEM_KHONG_LO)
		self.assertEqual(kq["loai"], "lo")
		self.assertIsNone(kq["so_lo"])
		self.assertEqual(kq["dong_hang"], self.dong)
		self.assertEqual(kq["vat_tu"], ITEM_KHONG_LO)
		self.assertFalse(kq["nhieu_dong"])

	def test_ghi_da_lay_va_hoan_tat_tron_ven_cho_hang_khong_lo(self):
		"""Bài chịu lực: trước bản vá, không có đường nào tới được `ghi_da_lay`
		từ giao diện quét (dòng "không nhận ra mã"), nên phiếu không bao giờ
		`hoan_tat` được. Khẳng định cả sổ vị trí trừ ĐÚNG ô (không phải chỉ
		docstatus đổi)."""
		from erpnext.warehouse_operations.vitri.lay_hang import ghi_da_lay, hoan_tat

		p = ghi_da_lay(self.dn.name, self.dong, None, O_GAN, 6)
		self.assertEqual(p["dong"][0]["da_lay"], 6.0)

		kq = hoan_tat(self.dn.name)
		self.assertEqual(kq["name"], self.dn.name)
		self.assertEqual(frappe.db.get_value("Delivery Note", self.dn.name, "docstatus"), 1)
		self.assertEqual(so.ton_o(O_GAN, ITEM_KHONG_LO, None), 4.0)

	def test_quet_ma_mat_hang_co_lo_bao_can_quet_lo_khong_gia_vo_la_lo(self):
		"""Mặt hàng CÓ quản lý lô mà quét mã hàng (không phải tem lô) thì không
		biết lô nào — không đoán, cùng nguyên tắc `_chon_dong_ung_vien`."""
		from erpnext.warehouse_operations.vitri.lay_hang import quet_de_lay

		self.dn.append(
			"items",
			{
				"item_code": ITEM,
				"qty": 3,
				"rate": 5000,
				"warehouse": KHO,
				"batch_no": LO,
				"use_serial_batch_fields": 1,
			},
		)
		self.dn.save(ignore_permissions=True)

		kq = quet_de_lay(self.dn.name, ITEM)
		self.assertEqual(kq["loai"], "can_quet_lo")
		self.assertEqual(kq["vat_tu"], ITEM)

	def test_quet_ma_mat_hang_khong_thuoc_phieu_khong_nhan_bua(self):
		"""`ITEM` có thật (`_vat_tu()`) nhưng phiếu của bài này chỉ có dòng
		`ITEM_KHONG_LO` — nhận diện được MỘT `Item` bất kỳ không có nghĩa nó
		thuộc phiếu đang lấy.

		Đã đọc `_tim_o` (`quet.py`) trước khi viết bài này: nó chỉ khớp đúng
		`name`/`barcode`/`ma_in_nhan` của `Storage Location` — `ITEM`
		("9L-VT-LAY-HANG") không khớp bất kỳ ô nào dựng trong bài này, nên
		`{"loai": None}` là do KHÔNG nhận diện được gì (đúng nhánh đang khoá),
		không phải một trùng hợp tình cờ qua nhánh `_tim_o`."""
		from erpnext.warehouse_operations.vitri.lay_hang import quet_de_lay

		self.assertEqual(quet_de_lay(self.dn.name, ITEM)["loai"], None)

	def test_quet_ma_vach_hang_khong_lo_qua_scan_barcode_ra_loai_lo(self):
		"""Đường THẬT của súng quét PDA: mã vạch trên bao bì (`Item Barcode`,
		`scan_barcode(...).get("item_code")`) — khác với đường
		`frappe.db.exists("Item", ma)` mà ba bài trên đi qua (mã quét trùng
		thẳng TÊN item, coi như gõ tay). Coordinator mandate nêu rõ HAI đường,
		phải khoá cả hai."""
		from erpnext.warehouse_operations.vitri.lay_hang import quet_de_lay

		kq = quet_de_lay(self.dn.name, self.BARCODE_KHONG_LO)
		self.assertEqual(kq["loai"], "lo")
		self.assertIsNone(kq["so_lo"])
		self.assertEqual(kq["dong_hang"], self.dong)
		self.assertEqual(kq["vat_tu"], ITEM_KHONG_LO)

	def test_quet_ma_vach_hang_co_lo_qua_scan_barcode_ra_can_quet_lo(self):
		"""Cùng đường mã vạch thật, cho mặt hàng CÓ quản lý lô: `scan_barcode`
		tự điền `has_batch_no` vào kết quả (`_update_item_info`), nhưng
		`quet_de_lay` đọc lại bằng `frappe.db.get_value` độc lập với `kq` —
		bài này khoá rằng kết quả cuối vẫn đúng `can_quet_lo`, không đoán lô,
		dù `ITEM` không có dòng trên `self.dn` (phiếu chỉ có `ITEM_KHONG_LO`)."""
		from erpnext.warehouse_operations.vitri.lay_hang import quet_de_lay

		self.dn.append(
			"items",
			{
				"item_code": ITEM,
				"qty": 3,
				"rate": 5000,
				"warehouse": KHO,
				"batch_no": LO,
				"use_serial_batch_fields": 1,
			},
		)
		self.dn.save(ignore_permissions=True)

		kq = quet_de_lay(self.dn.name, self.BARCODE_CO_LO)
		self.assertEqual(kq["loai"], "can_quet_lo")
		self.assertEqual(kq["vat_tu"], ITEM)

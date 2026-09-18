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
		with self.assertRaisesRegex(frappe.ValidationError, "phân bổ"):
			dn.submit()

		self.assertEqual(
			frappe.get_all("Location Ledger Entry", {"chung_tu": dn.name}),
			[],
			"chặn rồi thì không dòng sổ nào được sống sót",
		)

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

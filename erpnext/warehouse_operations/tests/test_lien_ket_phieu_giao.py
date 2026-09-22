"""Nối Phiếu giao với việc lấy hàng (19/09/2026): cột "Vị trí lấy" trên từng dòng
hàng, tiến độ lấy hàng cho form, và nhóm "Vị trí kho" trong tab Connections.

Bài chịu lực là `test_duyet_khong_quet_cot_ghi_o_fefo_da_tru`: cột phải phản ánh
SỔ VỊ TRÍ THẬT sau khi duyệt, không chỉ bảng phân bổ — phiếu không ai quét thì
bảng trống, nhưng hàng vẫn bị trừ ở một ô cụ thể và phiếu in ra phải nói ô đó.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import nowdate

from erpnext.warehouse_operations.tests.test_lay_hang import (
	CTY,
	DIEM_TEST,
	ITEM,
	ITEM_DICH_VU,
	KHACH,
	KHO,
	LO,
	O_GAN,
	O_XA,
	_chuyen_vao_o,
	_lo,
	_nhap_kho,
	_o,
	_phieu_giao,
	_vat_tu,
	_vat_tu_dich_vu,
)

COT = "custom_vi_tri_lay"


def _nhan(o):
	return frappe.db.get_value("Storage Location", o, "ma_in_nhan") or o


def _cot(dn_name, idx=1):
	return frappe.db.get_value("Delivery Note Item", {"parent": dn_name, "idx": idx}, COT) or ""


class TestCotViTriLay(FrappeTestCase):
	def setUp(self):
		from erpnext.warehouse_operations.vitri.lay_hang import _khoa_chot_thieu

		frappe.set_user("Administrator")
		frappe.db.savepoint(DIEM_TEST)
		_vat_tu()
		_lo()
		_o(O_GAN, thu_tu=1)
		_o(O_XA, thu_tu=2)
		_nhap_kho(30)
		_chuyen_vao_o([(O_GAN, 20), (O_XA, 10)])
		self.dn = _phieu_giao(12)
		self.dong = self.dn.items[0].name
		frappe.cache().delete_value(_khoa_chot_thieu(self.dn.name))

	def tearDown(self):
		from erpnext.warehouse_operations.vitri.lay_hang import _khoa_chot_thieu

		frappe.set_user("Administrator")
		frappe.cache().delete_value(_khoa_chot_thieu(self.dn.name))
		frappe.db.rollback(save_point=DIEM_TEST)

	def test_quet_xong_cot_hien_o_va_so_luong_theo_thu_tu_quet(self):
		from erpnext.warehouse_operations.vitri.lay_hang import ghi_da_lay

		ghi_da_lay(self.dn.name, self.dong, LO, O_XA, 3)
		ghi_da_lay(self.dn.name, self.dong, LO, O_GAN, 5)
		self.assertEqual(_cot(self.dn.name), f"{_nhan(O_XA)} ×3; {_nhan(O_GAN)} ×5")

	def test_quet_lai_cung_o_cong_don_trong_cot(self):
		from erpnext.warehouse_operations.vitri.lay_hang import ghi_da_lay

		ghi_da_lay(self.dn.name, self.dong, LO, O_GAN, 5)
		ghi_da_lay(self.dn.name, self.dong, LO, O_GAN, 3)
		self.assertEqual(_cot(self.dn.name), f"{_nhan(O_GAN)} ×8")

	def test_bo_luot_quet_thi_cot_cap_nhat(self):
		from erpnext.warehouse_operations.vitri.lay_hang import bo_dong_da_lay, ghi_da_lay

		ghi_da_lay(self.dn.name, self.dong, LO, O_GAN, 5)
		p = ghi_da_lay(self.dn.name, self.dong, LO, O_XA, 2)
		luot_xa = next(x["name"] for x in p["dong"][0]["da_lay_o"] if x["o"] == O_XA)
		bo_dong_da_lay(self.dn.name, luot_xa)
		self.assertEqual(_cot(self.dn.name), f"{_nhan(O_GAN)} ×5")

		p = frappe.get_doc("Delivery Note", self.dn.name)
		bo_dong_da_lay(self.dn.name, p.custom_phan_bo_vi_tri[0].name)
		self.assertEqual(_cot(self.dn.name), "")

	def test_hoan_tat_cot_khop_so_vi_tri(self):
		from erpnext.warehouse_operations.vitri.lay_hang import ghi_da_lay, hoan_tat

		ghi_da_lay(self.dn.name, self.dong, LO, O_XA, 10)
		ghi_da_lay(self.dn.name, self.dong, LO, O_GAN, 2)
		hoan_tat(self.dn.name)
		self.assertEqual(_cot(self.dn.name), f"{_nhan(O_XA)} ×10; {_nhan(O_GAN)} ×2")

	def test_duyet_khong_quet_cot_ghi_o_fefo_da_tru(self):
		"""Bảng phân bổ trống → FEFO trừ ô O_GAN; cột phải nói đúng ô đó."""
		self.dn.reload()
		self.dn.submit()
		self.assertEqual(_cot(self.dn.name), f"{_nhan(O_GAN)} ×12")
		self.dn.reload()
		self.assertEqual(self.dn.items[0].get(COT), f"{_nhan(O_GAN)} ×12")

	def test_duyet_fefo_tran_sang_o_thu_hai(self):
		dn = _phieu_giao(25)
		dn.submit()
		self.assertEqual(_cot(dn.name), f"{_nhan(O_GAN)} ×20; {_nhan(O_XA)} ×5")

	def test_huy_giu_cot_amend_thi_cot_trong(self):
		from erpnext.warehouse_operations.vitri.lay_hang import ghi_da_lay, hoan_tat

		ghi_da_lay(self.dn.name, self.dong, LO, O_XA, 10)
		ghi_da_lay(self.dn.name, self.dong, LO, O_GAN, 2)
		hoan_tat(self.dn.name)
		dn = frappe.get_doc("Delivery Note", self.dn.name)
		dn.cancel()
		self.assertEqual(_cot(dn.name), f"{_nhan(O_XA)} ×10; {_nhan(O_GAN)} ×2")

		moi = frappe.copy_doc(dn)
		moi.amended_from = dn.name
		# Dưới test `copy_doc` giữ docstatus=2 của bản gốc — xem
		# `test_lay_hang.test_amend_don_sach_phan_bo_cu`.
		moi.docstatus = 0
		moi.insert(ignore_permissions=True)
		self.assertEqual(_cot(moi.name), "")
		self.assertFalse(moi.custom_phan_bo_vi_tri)

	def test_tach_dong_moi_dong_co_cot_rieng(self):
		from erpnext.warehouse_operations.tests.test_lay_hang import _chuyen_vao_o_lo, _nhap_kho_lo
		from erpnext.warehouse_operations.vitri.lay_hang import ghi_da_lay, tach_dong_theo_lo

		lo2 = "9L-LO-LAY-04"
		if not frappe.db.exists("Batch", lo2):
			frappe.get_doc(
				{"doctype": "Batch", "batch_id": lo2, "item": ITEM, "expiry_date": "2027-07-31"}
			).insert(ignore_permissions=True)
		_nhap_kho_lo(lo2, 10)
		_chuyen_vao_o_lo(lo2, [(O_XA, 10)])

		ghi_da_lay(self.dn.name, self.dong, LO, O_GAN, 8)
		p = tach_dong_theo_lo(self.dn.name, self.dong, lo2)
		moi = next(d for d in p["dong"] if d["dong_hang"] != self.dong)["dong_hang"]
		ghi_da_lay(self.dn.name, moi, lo2, O_XA, 4)

		self.assertEqual(frappe.db.get_value("Delivery Note Item", self.dong, COT), f"{_nhan(O_GAN)} ×8")
		self.assertEqual(frappe.db.get_value("Delivery Note Item", moi, COT), f"{_nhan(O_XA)} ×4")


class TestCotDongDichVu(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.savepoint(DIEM_TEST)
		_vat_tu()
		_lo()
		_vat_tu_dich_vu()
		_o(O_GAN, thu_tu=1)
		_nhap_kho(30)
		_chuyen_vao_o([(O_GAN, 30)])

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point=DIEM_TEST)

	def test_dong_dich_vu_cot_trong_sau_khi_duyet(self):
		dn = frappe.get_doc(
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
		dn.insert(ignore_permissions=True)
		dn.submit()
		self.assertEqual(_cot(dn.name, 1), f"{_nhan(O_GAN)} ×5")
		self.assertEqual(_cot(dn.name, 2), "")


class TestTienDoLayHang(FrappeTestCase):
	def setUp(self):
		from erpnext.warehouse_operations.vitri.lay_hang import _khoa_chot_thieu

		frappe.set_user("Administrator")
		frappe.db.savepoint(DIEM_TEST)
		_vat_tu()
		_lo()
		_o(O_GAN, thu_tu=1)
		_o(O_XA, thu_tu=2)
		_nhap_kho(30)
		_chuyen_vao_o([(O_GAN, 20), (O_XA, 10)])
		self.dn = _phieu_giao(12)
		self.dong = self.dn.items[0].name
		frappe.cache().delete_value(_khoa_chot_thieu(self.dn.name))

	def tearDown(self):
		from erpnext.warehouse_operations.vitri.lay_hang import _khoa_chot_thieu

		frappe.set_user("Administrator")
		frappe.cache().delete_value(_khoa_chot_thieu(self.dn.name))
		frappe.db.rollback(save_point=DIEM_TEST)

	def test_chua_lay(self):
		from erpnext.warehouse_operations.vitri.lay_hang import tien_do_lay_hang

		t = tien_do_lay_hang(self.dn.name)
		self.assertEqual(t["trang_thai"], "chua_lay")
		self.assertEqual((t["so_dong_quet"], t["so_dong_du"]), (1, 0))
		self.assertTrue(t["lay_duoc"])

	def test_dang_lay_roi_du(self):
		from erpnext.warehouse_operations.vitri.lay_hang import ghi_da_lay, tien_do_lay_hang

		ghi_da_lay(self.dn.name, self.dong, LO, O_GAN, 5)
		t = tien_do_lay_hang(self.dn.name)
		self.assertEqual(t["trang_thai"], "dang_lay")
		self.assertEqual(t["so_dong_du"], 0)
		self.assertEqual((t["tong_da_lay"], t["tong_can"]), (5.0, 12.0))
		self.assertEqual(t["nguoi_lay"], ["Administrator"])

		ghi_da_lay(self.dn.name, self.dong, LO, O_XA, 7)
		t = tien_do_lay_hang(self.dn.name)
		self.assertEqual(t["trang_thai"], "du")
		self.assertEqual(t["so_dong_du"], 1)

	def test_chot_thieu_dem_rieng_va_coi_nhu_xong(self):
		from erpnext.warehouse_operations.vitri.lay_hang import chot_thieu, ghi_da_lay, tien_do_lay_hang

		ghi_da_lay(self.dn.name, self.dong, LO, O_GAN, 5)
		chot_thieu(self.dn.name, self.dong)
		t = tien_do_lay_hang(self.dn.name)
		self.assertEqual(t["so_dong_chot_thieu"], 1)
		self.assertEqual(t["trang_thai"], "du")

	def test_da_duyet_theo_quet_va_theo_fefo(self):
		from erpnext.warehouse_operations.vitri.lay_hang import ghi_da_lay, hoan_tat, tien_do_lay_hang

		ghi_da_lay(self.dn.name, self.dong, LO, O_GAN, 12)
		hoan_tat(self.dn.name)
		t = tien_do_lay_hang(self.dn.name)
		self.assertEqual(t["trang_thai"], "da_duyet_quet")
		self.assertFalse(t["lay_duoc"])

		dn = _phieu_giao(3)
		dn.submit()
		self.assertEqual(tien_do_lay_hang(dn.name)["trang_thai"], "da_duyet_fefo")

	def test_phieu_tra_hang_khong_ap_dung(self):
		from erpnext.warehouse_operations.vitri.lay_hang import tien_do_lay_hang

		self.dn.db_set("is_return", 1)
		self.assertEqual(tien_do_lay_hang(self.dn.name)["trang_thai"], "khong_ap_dung")

	def test_khong_quyen_doc_bi_chan(self):
		from erpnext.warehouse_operations.vitri.lay_hang import tien_do_lay_hang

		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			tien_do_lay_hang(self.dn.name)


class TestConnectionsViTriKho(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.savepoint(DIEM_TEST)
		_vat_tu()
		_lo()
		_o(O_GAN, thu_tu=1)
		_nhap_kho(30)
		_chuyen_vao_o([(O_GAN, 30)])

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point=DIEM_TEST)

	def test_tab_connections_dem_dong_so_vi_tri_cua_phieu(self):
		from frappe.desk.notifications import get_open_count

		dn = _phieu_giao(4)
		dn.submit()
		kq = get_open_count("Delivery Note", dn.name)
		dem = {x["doctype"]: x["count"] for x in kq["count"]["external_links_found"]}
		self.assertEqual(dem.get("Location Ledger Entry"), 1)

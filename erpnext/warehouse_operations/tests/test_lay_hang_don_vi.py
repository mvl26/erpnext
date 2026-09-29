"""Lấy hàng theo phiếu giao — lô theo hạn dùng, chuyển đổi đơn vị, tem kiện, chặn
duyệt (chủ đầu tư 22/09/2026). Spec: docs/superpowers/specs/2026-09-22-lay-hang-
don-vi-tem-kien-design.md.

Dựng dữ liệu bằng helper của `test_lay_hang` — một chỗ sửa cho cả hai bộ.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.warehouse_operations.tests.test_lay_hang import (
	DIEM_TEST,
	ITEM,
	LO,
	O_GAN,
	O_XA,
	_chuyen_vao_o,
	_chuyen_vao_o_lo,
	_lo,
	_nhap_kho,
	_nhap_kho_lo,
	_o,
	_phieu_giao,
	_vat_tu,
)

LO_SOM = "9L-LO-DV-SOM"


def _lo_som():
	if not frappe.db.exists("Batch", LO_SOM):
		frappe.get_doc(
			{"doctype": "Batch", "batch_id": LO_SOM, "item": ITEM, "expiry_date": "2027-01-31"}
		).insert(ignore_permissions=True)
	return LO_SOM


class TestLoNenLay(FrappeTestCase):
	"""Lô gợi ý theo HẠN DÙNG trên màn hình lấy hàng (spec §3)."""

	def setUp(self):
		from erpnext.warehouse_operations.vitri.lay_hang import _khoa_chot_thieu

		frappe.set_user("Administrator")
		frappe.db.savepoint(DIEM_TEST)
		_vat_tu()
		_lo()  # LO: HSD 2029-01-31
		_lo_som()  # LO_SOM: HSD 2027-01-31 — hết hạn SỚM hơn
		_o(O_GAN, thu_tu=1)
		_o(O_XA, thu_tu=2)
		_nhap_kho(10)
		_chuyen_vao_o([(O_GAN, 10)])
		_nhap_kho_lo(LO_SOM, 10)
		_chuyen_vao_o_lo(LO_SOM, [(O_XA, 10)])
		self.dn = _phieu_giao(5)  # chốt LO (hết hạn MUỘN hơn)
		frappe.cache().delete_value(_khoa_chot_thieu(self.dn.name))

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point=DIEM_TEST)

	def test_goi_y_lo_het_han_som_nhat_va_canh_bao_lo_tren_phieu(self):
		from erpnext.warehouse_operations.vitri.lay_hang import mo_phieu_giao

		d = mo_phieu_giao(self.dn.name)["dong"][0]
		self.assertEqual(d["lo_nen_lay"], LO_SOM)
		self.assertEqual(str(d["lo_nen_lay_hsd"]), "2027-01-31")
		self.assertTrue(d["lo_tren_phieu_muon_hon"])

	def test_lo_tren_phieu_da_la_lo_som_nhat_thi_khong_canh_bao(self):
		from erpnext.warehouse_operations.vitri.lay_hang import mo_phieu_giao

		frappe.db.set_value("Delivery Note Item", self.dn.items[0].name, "batch_no", LO_SOM)
		d = mo_phieu_giao(self.dn.name)["dong"][0]
		self.assertEqual(d["lo_nen_lay"], LO_SOM)
		self.assertFalse(d["lo_tren_phieu_muon_hon"])


class TestPatchChonLoTheoHanDung(FrappeTestCase):
	def test_patch_dat_expiry(self):
		from erpnext.warehouse_operations.patches.v1_0.chon_lo_theo_han_dung import execute

		cu = frappe.db.get_single_value("Stock Settings", "pick_serial_and_batch_based_on")
		try:
			frappe.db.set_single_value("Stock Settings", "pick_serial_and_batch_based_on", "FIFO")
			execute()
			self.assertEqual(
				frappe.db.get_single_value("Stock Settings", "pick_serial_and_batch_based_on"), "Expiry"
			)
		finally:
			frappe.db.set_single_value("Stock Settings", "pick_serial_and_batch_based_on", cu)


VT_DV = "9L-VT-DV"
LO_DV = "9L-LO-DV-01"
HOP = "9L-Hop"
THUNG = "9L-Thung"
KHO = "Kho Miyano - MYN"
CTY = "Miyano Việt Nam"
KHACH = "Bệnh viện DEMO Miyano E2E"


def _uom(ten, tron=0):
	if not frappe.db.exists("UOM", ten):
		frappe.get_doc({"doctype": "UOM", "uom_name": ten, "must_be_whole_number": tron}).insert(
			ignore_permissions=True
		)
	else:
		frappe.db.set_value("UOM", ten, "must_be_whole_number", tron)
	return ten


def _vat_tu_dv():
	"""Mặt hàng tồn theo Nos, khai 1 Hộp = 100, 1 Thùng = 2000 (đúng ví dụ chủ đầu tư)."""
	_uom(HOP, tron=1)
	_uom(THUNG, tron=1)
	if not frappe.db.exists("Item", VT_DV):
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": VT_DV,
				"item_name": "Hàng thử lấy theo đơn vị",
				"item_group": "All Item Groups",
				"stock_uom": "Nos",
				"is_stock_item": 1,
				"has_batch_no": 1,
				"create_new_batch": 0,
				"uoms": [
					{"uom": "Nos", "conversion_factor": 1},
					{"uom": HOP, "conversion_factor": 100},
					{"uom": THUNG, "conversion_factor": 2000},
				],
			}
		).insert(ignore_permissions=True)
	if not frappe.db.exists("Batch", LO_DV):
		frappe.get_doc(
			{"doctype": "Batch", "batch_id": LO_DV, "item": VT_DV, "expiry_date": "2029-06-30"}
		).insert(ignore_permissions=True)
	return VT_DV


def _nhap_vao_o(so_luong, o=O_GAN):
	from erpnext.warehouse_operations.tests.test_lay_hang import bo_kiem_o_tem

	se = frappe.get_doc(
		{
			"doctype": "Stock Entry",
			"stock_entry_type": "Material Receipt",
			"company": CTY,
			"items": [
				{
					"item_code": VT_DV,
					"qty": so_luong,
					"t_warehouse": KHO,
					"basic_rate": 10,
					"batch_no": LO_DV,
					"use_serial_batch_fields": 1,
				}
			],
		}
	)
	se.insert(ignore_permissions=True)
	se.submit()
	chua_xep = frappe.db.get_value("Storage Location", {"kho": KHO, "la_o_chua_xep": 1})
	px = frappe.get_doc(
		{
			"doctype": "Location Transfer",
			"kho": KHO,
			"items": [{"vat_tu": VT_DV, "so_lo": LO_DV, "tu_o": chua_xep, "den_o": o, "so_luong": so_luong}],
		}
	)
	with bo_kiem_o_tem():
		px.insert(ignore_permissions=True)
		px.submit()


def _phieu_giao_dv(so_luong, uom=HOP, cf=100):
	dn = frappe.get_doc(
		{
			"doctype": "Delivery Note",
			"company": CTY,
			"customer": KHACH,
			"items": [
				{
					"item_code": VT_DV,
					"qty": so_luong,
					"uom": uom,
					"conversion_factor": cf,
					"rate": 1000,
					"warehouse": KHO,
					"batch_no": LO_DV,
					"use_serial_batch_fields": 1,
				}
			],
		}
	)
	dn.insert(ignore_permissions=True)
	return dn


class TestDonVi(FrappeTestCase):
	"""Lấy theo bất kỳ đơn vị nào khai trên mặt hàng; sổ luôn trừ theo ĐƠN VỊ TỒN (spec §4)."""

	def setUp(self):
		from erpnext.warehouse_operations.vitri.lay_hang import _khoa_chot_thieu

		frappe.set_user("Administrator")
		frappe.db.savepoint(DIEM_TEST)
		_vat_tu_dv()
		_o(O_GAN, thu_tu=1)
		_nhap_vao_o(3000)
		self.dn = _phieu_giao_dv(5)  # 5 Hộp = 500 Nos
		self.dong = self.dn.items[0].name
		frappe.cache().delete_value(_khoa_chot_thieu(self.dn.name))

	def tearDown(self):
		from erpnext.warehouse_operations.vitri.lay_hang import _khoa_chot_thieu

		frappe.set_user("Administrator")
		frappe.cache().delete_value(_khoa_chot_thieu(self.dn.name))
		frappe.db.rollback(save_point=DIEM_TEST)

	def _pb(self):
		return frappe.get_doc("Delivery Note", self.dn.name).custom_phan_bo_vi_tri

	def test_dong_ban_theo_hop_quet_duoc(self):
		from erpnext.warehouse_operations.vitri.lay_hang import mo_phieu_giao

		d = mo_phieu_giao(self.dn.name)["dong"][0]
		self.assertTrue(d["can_quet"], d["ly_do_khong_quet"])
		self.assertEqual(
			(d["can_lay"], d["can_lay_ton"], d["don_vi_dong"], d["don_vi_ton"]), (5, 500, HOP, "Nos")
		)
		self.assertEqual({x["uom"]: x["he_so"] for x in d["don_vi_chon"]}, {"Nos": 1, HOP: 100, THUNG: 2000})

	def test_lay_5_hop_tru_500_don_vi_ton(self):
		from erpnext.warehouse_operations.vitri.lay_hang import ghi_da_lay

		p = ghi_da_lay(self.dn.name, self.dong, LO_DV, O_GAN, 5, don_vi=HOP)
		pb = self._pb()[0]
		self.assertEqual(
			(pb.so_luong, pb.so_luong_lay, pb.don_vi_lay, pb.he_so, pb.so_kien), (500, 5, HOP, 100, 5)
		)
		d = p["dong"][0]
		self.assertEqual((d["da_lay"], d["da_lay_ton"]), (5, 500))

	def test_mac_dinh_don_vi_cua_dong(self):
		from erpnext.warehouse_operations.vitri.lay_hang import ghi_da_lay

		ghi_da_lay(self.dn.name, self.dong, LO_DV, O_GAN, 2)
		pb = self._pb()[0]
		self.assertEqual((pb.don_vi_lay, pb.so_luong), (HOP, 200))

	def test_lay_bang_don_vi_ton_du_dong_ban_theo_hop_roi_duyet(self):
		from erpnext.warehouse_operations.tests.test_lay_hang import bo_bat_buoc_lay_hang
		from erpnext.warehouse_operations.vitri import so
		from erpnext.warehouse_operations.vitri.lay_hang import ghi_da_lay, hoan_tat

		ghi_da_lay(self.dn.name, self.dong, LO_DV, O_GAN, 500, don_vi="Nos")
		with bo_bat_buoc_lay_hang():
			hoan_tat(self.dn.name)
		self.assertEqual(so.ton_o(O_GAN, VT_DV, LO_DV), 2500.0)

	def test_don_vi_khong_khai_bi_chan(self):
		from erpnext.warehouse_operations.vitri.lay_hang import ghi_da_lay

		with self.assertRaisesRegex(frappe.ValidationError, "không khai đơn vị"):
			ghi_da_lay(self.dn.name, self.dong, LO_DV, O_GAN, 1, don_vi="Kg")

	def test_vuot_ton_o_theo_don_vi_ton_bi_chan(self):
		from erpnext.warehouse_operations.vitri.lay_hang import ghi_da_lay

		dn = _phieu_giao_dv(2, uom=THUNG, cf=2000)  # cần 4000, ô chỉ còn 3000
		with self.assertRaisesRegex(frappe.ValidationError, "chỉ còn"):
			ghi_da_lay(dn.name, dn.items[0].name, LO_DV, O_GAN, 2, don_vi=THUNG)

	def test_cong_don_chi_khi_cung_don_vi(self):
		from erpnext.warehouse_operations.vitri.lay_hang import ghi_da_lay

		ghi_da_lay(self.dn.name, self.dong, LO_DV, O_GAN, 2, don_vi=HOP)
		ghi_da_lay(self.dn.name, self.dong, LO_DV, O_GAN, 1, don_vi=HOP)
		self.assertEqual([(p.so_luong_lay, p.so_kien) for p in self._pb()], [(3, 3)])
		ghi_da_lay(self.dn.name, self.dong, LO_DV, O_GAN, 50, don_vi="Nos")
		self.assertEqual(len(self._pb()), 2)

	def test_so_kien_mac_dinh_va_sua_duoc(self):
		from erpnext.warehouse_operations.vitri.lay_hang import ghi_da_lay

		ghi_da_lay(self.dn.name, self.dong, LO_DV, O_GAN, 300, don_vi="Nos")
		self.assertEqual(self._pb()[0].so_kien, 1)
		ghi_da_lay(self.dn.name, self.dong, LO_DV, O_GAN, 2, don_vi=HOP, so_kien=1)
		self.assertEqual(self._pb()[1].so_kien, 1)

	def test_chot_thieu_dong_hop_khong_tron_bi_chan(self):
		from erpnext.warehouse_operations.tests.test_lay_hang import bo_bat_buoc_lay_hang
		from erpnext.warehouse_operations.vitri.lay_hang import chot_thieu, ghi_da_lay, hoan_tat

		ghi_da_lay(self.dn.name, self.dong, LO_DV, O_GAN, 350, don_vi="Nos")
		chot_thieu(self.dn.name, self.dong)
		with bo_bat_buoc_lay_hang(), self.assertRaisesRegex(frappe.ValidationError, "phải tròn"):
			hoan_tat(self.dn.name)

	def test_chot_thieu_dong_hop_tron_ha_qty(self):
		from erpnext.warehouse_operations.tests.test_lay_hang import bo_bat_buoc_lay_hang
		from erpnext.warehouse_operations.vitri import so
		from erpnext.warehouse_operations.vitri.lay_hang import chot_thieu, ghi_da_lay, hoan_tat

		ghi_da_lay(self.dn.name, self.dong, LO_DV, O_GAN, 3, don_vi=HOP)
		chot_thieu(self.dn.name, self.dong)
		with bo_bat_buoc_lay_hang():
			hoan_tat(self.dn.name)
		dn = frappe.get_doc("Delivery Note", self.dn.name)
		self.assertEqual((dn.items[0].qty, dn.items[0].stock_qty), (3, 300))
		self.assertEqual(so.ton_o(O_GAN, VT_DV, LO_DV), 2700.0)


class TestTemKien(FrappeTestCase):
	"""Mỗi kiện một tem, ghi cả khách (spec §5). Tem dùng lại bố cục tem lô 50×30:
	F9 (chữ to nhất) là "i/N" để người đóng gói nhìn thấy ngay."""

	def setUp(self):
		from erpnext.warehouse_operations.vitri.lay_hang import _khoa_chot_thieu

		frappe.set_user("Administrator")
		frappe.db.savepoint(DIEM_TEST)
		_vat_tu_dv()
		_o(O_GAN, thu_tu=1)
		_nhap_vao_o(3000)
		self.dn = _phieu_giao_dv(8)  # 8 Hộp = 800 Nos
		self.dong = self.dn.items[0].name
		frappe.cache().delete_value(_khoa_chot_thieu(self.dn.name))

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point=DIEM_TEST)

	def test_5_hop_ra_5_tem_danh_so_va_noi_dung(self):
		from erpnext.warehouse_operations.vitri.lay_hang import ghi_da_lay
		from erpnext.warehouse_operations.vitri.tem_kien import du_lieu_tem_kien

		ghi_da_lay(self.dn.name, self.dong, LO_DV, O_GAN, 5, don_vi=HOP)
		tem = du_lieu_tem_kien(self.dn.name)
		self.assertEqual(len(tem), 5)
		self.assertEqual([t["kien_thu"] for t in tem], [1, 2, 3, 4, 5])
		t = tem[0]
		self.assertEqual((t["tong_kien"], t["so_luong_kien"], t["so_lo"]), (5, f"1 {HOP}", LO_DV))
		self.assertEqual(
			(t["F1"], t["F3"], t["F9"], t["F10"], t["F11"]), (VT_DV, f"1 {HOP}", "1/5", LO_DV, LO_DV)
		)
		self.assertIn(self.dn.name, t["F4"])
		self.assertIn("DEMO", t["F7"])  # tên khách
		self.assertEqual(t["F5"], "HSD 2029/06/30")

	def test_300_cai_chia_3_kien_va_danh_so_noi_tiep_ca_phieu(self):
		from erpnext.warehouse_operations.vitri.lay_hang import ghi_da_lay
		from erpnext.warehouse_operations.vitri.tem_kien import du_lieu_tem_kien

		ghi_da_lay(self.dn.name, self.dong, LO_DV, O_GAN, 5, don_vi=HOP)
		ghi_da_lay(self.dn.name, self.dong, LO_DV, O_GAN, 300, don_vi="Nos", so_kien=3)
		tem = du_lieu_tem_kien(self.dn.name)
		self.assertEqual(len(tem), 8)
		self.assertEqual([t["kien_thu"] for t in tem], list(range(1, 9)))
		self.assertTrue(all(t["tong_kien"] == 8 for t in tem))
		self.assertEqual({t["so_luong_kien"] for t in tem[5:]}, {"100 Nos"})

	def test_danh_dau_da_in_roi_chi_chua_in_rong_va_dem_kien(self):
		from erpnext.warehouse_operations.vitri.lay_hang import ghi_da_lay
		from erpnext.warehouse_operations.vitri.tem_kien import dem_kien, danh_dau_da_in, du_lieu_tem_kien

		ghi_da_lay(self.dn.name, self.dong, LO_DV, O_GAN, 5, don_vi=HOP)
		self.assertEqual(dem_kien(frappe.get_doc("Delivery Note", self.dn.name)), (0, 5))
		kq = danh_dau_da_in(self.dn.name)
		self.assertEqual((kq["so_kien_da_in"], kq["tong_kien"]), (5, 5))
		self.assertEqual(du_lieu_tem_kien(self.dn.name, chi_chua_in=1), [])
		self.assertEqual(len(du_lieu_tem_kien(self.dn.name, chi_chua_in=0)), 5)

	def test_them_luot_sau_khi_in_chi_in_phan_moi(self):
		from erpnext.warehouse_operations.vitri.lay_hang import ghi_da_lay
		from erpnext.warehouse_operations.vitri.tem_kien import danh_dau_da_in, du_lieu_tem_kien

		ghi_da_lay(self.dn.name, self.dong, LO_DV, O_GAN, 2, don_vi=HOP)
		danh_dau_da_in(self.dn.name)
		ghi_da_lay(self.dn.name, self.dong, LO_DV, O_GAN, 1, don_vi=HOP)  # cộng dồn vào dòng cũ
		tem = du_lieu_tem_kien(self.dn.name, chi_chua_in=1)
		self.assertEqual([t["kien_thu"] for t in tem], [3])


	def test_hai_luot_cung_o_khac_so_moi_kien_khong_gop(self):
		"""Bắt được khi chạy thật 22/09: lượt 20 Cái (1 kiện) rồi 80 Cái (1 kiện) cùng
		ô/lô/đơn vị từng bị GỘP thành 100 Cái / 2 kiện → hai tem "50 Cái", sai với hai
		kiện thật trên bàn. Chỉ gộp khi mỗi kiện chứa CÙNG số lượng."""
		from erpnext.warehouse_operations.vitri.lay_hang import ghi_da_lay
		from erpnext.warehouse_operations.vitri.tem_kien import du_lieu_tem_kien

		ghi_da_lay(self.dn.name, self.dong, LO_DV, O_GAN, 20, don_vi="Nos")
		ghi_da_lay(self.dn.name, self.dong, LO_DV, O_GAN, 80, don_vi="Nos")
		pb = frappe.get_doc("Delivery Note", self.dn.name).custom_phan_bo_vi_tri
		self.assertEqual([(p.so_luong_lay, p.so_kien) for p in pb], [(20, 1), (80, 1)])
		self.assertEqual([t["so_luong_kien"] for t in du_lieu_tem_kien(self.dn.name)], ["20 Nos", "80 Nos"])


class TestChanDuyet(FrappeTestCase):
	"""Bắt buộc lấy hàng + in đủ tem kiện trước khi duyệt phiếu giao (spec §6)."""

	def setUp(self):
		from erpnext.warehouse_operations.vitri.lay_hang import _khoa_chot_thieu

		frappe.set_user("Administrator")
		frappe.db.savepoint(DIEM_TEST)
		_vat_tu_dv()
		_o(O_GAN, thu_tu=1)
		_nhap_vao_o(3000)
		self.dn = _phieu_giao_dv(5)  # 5 Hộp = 500 Nos
		self.dong = self.dn.items[0].name
		frappe.cache().delete_value(_khoa_chot_thieu(self.dn.name))

	def tearDown(self):
		from erpnext.warehouse_operations.vitri.lay_hang import _khoa_chot_thieu

		frappe.set_user("Administrator")
		frappe.cache().delete_value(_khoa_chot_thieu(self.dn.name))
		frappe.db.rollback(save_point=DIEM_TEST)

	def _duyet(self):
		frappe.get_doc("Delivery Note", self.dn.name).submit()

	def test_chua_lay_gi_bi_chan(self):
		with self.assertRaisesRegex(frappe.ValidationError, "chưa lấy hàng"):
			self._duyet()

	def test_lay_do_dang_bi_chan(self):
		from erpnext.warehouse_operations.vitri.lay_hang import ghi_da_lay

		ghi_da_lay(self.dn.name, self.dong, LO_DV, O_GAN, 2, don_vi=HOP)
		with self.assertRaisesRegex(frappe.ValidationError, "mới lấy 200"):
			self._duyet()

	def test_lay_du_chua_in_tem_bi_chan_in_roi_thi_qua(self):
		from erpnext.warehouse_operations.vitri import so
		from erpnext.warehouse_operations.vitri.lay_hang import ghi_da_lay
		from erpnext.warehouse_operations.vitri.tem_kien import danh_dau_da_in

		ghi_da_lay(self.dn.name, self.dong, LO_DV, O_GAN, 5, don_vi=HOP)
		with self.assertRaisesRegex(frappe.ValidationError, "5/5 kiện chưa in tem"):
			self._duyet()
		danh_dau_da_in(self.dn.name)
		self._duyet()
		self.assertEqual(frappe.db.get_value("Delivery Note", self.dn.name, "docstatus"), 1)
		self.assertEqual(so.ton_o(O_GAN, VT_DV, LO_DV), 2500.0)

	def test_hoan_tat_cung_bi_chan_khi_thieu_tem(self):
		from erpnext.warehouse_operations.vitri.lay_hang import ghi_da_lay, hoan_tat

		ghi_da_lay(self.dn.name, self.dong, LO_DV, O_GAN, 5, don_vi=HOP)
		with self.assertRaisesRegex(frappe.ValidationError, "chưa in tem"):
			hoan_tat(self.dn.name)
		self.assertEqual(frappe.db.get_value("Delivery Note", self.dn.name, "docstatus"), 0)

	def test_co_bo_bat_buoc_cho_test_dung_du_lieu(self):
		from erpnext.warehouse_operations.tests.test_lay_hang import bo_bat_buoc_lay_hang

		with bo_bat_buoc_lay_hang():
			self._duyet()
		self.assertEqual(frappe.db.get_value("Delivery Note", self.dn.name, "docstatus"), 1)

	def test_dong_dich_vu_khong_bi_chan(self):
		if not frappe.db.exists("Item", "9L-DV-VAN-CHUYEN"):
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": "9L-DV-VAN-CHUYEN",
					"item_group": "All Item Groups",
					"stock_uom": "Nos",
					"is_stock_item": 0,
				}
			).insert(ignore_permissions=True)
		dn = frappe.get_doc(
			{
				"doctype": "Delivery Note",
				"company": CTY,
				"customer": KHACH,
				"items": [{"item_code": "9L-DV-VAN-CHUYEN", "qty": 1, "rate": 1000, "warehouse": KHO}],
			}
		).insert(ignore_permissions=True)
		dn.submit()
		self.assertEqual(dn.docstatus, 1)

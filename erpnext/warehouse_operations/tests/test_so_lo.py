"""Số lô NCC tách khỏi mã lô (spec `2026-10-19-so-lo-tach-khoi-ma-lo-design.md`).

Mã lô (tên bản ghi `Batch`) là khoá, mã vạch in nó. Số lô (`custom_so_lo`) là
chữ in trên bao bì NCC — được trùng giữa các mặt hàng — và là thứ mọi màn hình
cho người đọc.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.warehouse_operations.tests.test_hook_nhap import _tao_item

ITEM_LO = "_Test WMS So Lo A"


def _tao_lo(ten, item=ITEM_LO, **kw):
	if frappe.db.exists("Batch", ten):
		frappe.delete_doc("Batch", ten, force=True)
	return frappe.get_doc({"doctype": "Batch", "batch_id": ten, "item": item, **kw}).insert(
		ignore_permissions=True
	)


class TestTruongSoLo(FrappeTestCase):
	def setUp(self):
		_tao_item(ITEM_LO, co_lo=1)

	def test_lo_tao_tay_tu_dien_so_lo_bang_ma(self):
		lo = _tao_lo("SOLO-TAY-1")
		self.assertEqual(lo.custom_so_lo, "SOLO-TAY-1")

	def test_lo_sinh_theo_series_cua_mat_hang_cung_co_so_lo(self):
		# Không truyền batch_id: tên sinh trong `autoname`, SAU `before_insert`.
		lo = frappe.get_doc({"doctype": "Batch", "item": ITEM_LO}).insert(ignore_permissions=True)
		self.assertEqual(lo.custom_so_lo, lo.name)

	def test_title_field_la_so_lo(self):
		meta = frappe.get_meta("Batch")
		self.assertEqual(meta.title_field, "custom_so_lo")
		self.assertEqual(meta.show_title_field_in_link, 1)

	def test_patch_dien_lo_cu(self):
		from erpnext.warehouse_operations.patches.v1_0 import them_so_lo_ncc

		lo = _tao_lo("SOLO-CU-1")
		frappe.db.set_value("Batch", lo.name, "custom_so_lo", None)
		them_so_lo_ncc.execute()
		self.assertEqual(frappe.db.get_value("Batch", lo.name, "custom_so_lo"), "SOLO-CU-1")
		them_so_lo_ncc.execute()
		self.assertEqual(frappe.db.get_value("Batch", lo.name, "custom_so_lo"), "SOLO-CU-1")


ITEM_LO_B = "_Test WMS So Lo B"


class TestHelperSoLo(FrappeTestCase):
	def setUp(self):
		_tao_item(ITEM_LO, co_lo=1)
		_tao_item(ITEM_LO_B, co_lo=1)

	def test_so_lo_cua_tra_so_lo_hoac_roi_ve_ma(self):
		from erpnext.warehouse_operations.vitri.so_lo import so_lo_cua

		lo = _tao_lo("HELP-MA-1", custom_so_lo="HELP-SO-1")
		self.assertEqual(so_lo_cua(lo.name), "HELP-SO-1")
		self.assertEqual(so_lo_cua("HELP-KHONG-CO"), "HELP-KHONG-CO")
		self.assertEqual(so_lo_cua(None), "")

	def test_so_lo_theo_ma_mot_truy_van(self):
		from erpnext.warehouse_operations.vitri.so_lo import so_lo_theo_ma

		_tao_lo("HELP-MA-2", custom_so_lo="HELP-SO-2")
		_tao_lo("HELP-MA-3", custom_so_lo="HELP-SO-3")
		so_lo_theo_ma(["HELP-MA-2"])  # làm ấm cache meta/cột của `Batch`
		with self.assertQueryCount(1):
			kq = so_lo_theo_ma(["HELP-MA-2", "HELP-MA-3", "HELP-KHONG-CO"])
		self.assertEqual(
			kq,
			{"HELP-MA-2": "HELP-SO-2", "HELP-MA-3": "HELP-SO-3", "HELP-KHONG-CO": "HELP-KHONG-CO"},
		)

	def test_so_lo_theo_ma_rong_khong_truy_van(self):
		from erpnext.warehouse_operations.vitri.so_lo import so_lo_theo_ma

		with self.assertQueryCount(0):
			self.assertEqual(so_lo_theo_ma([None, ""]), {})

	def test_gan_so_lo_hien_thi_giu_khoa_ma_lo(self):
		from erpnext.warehouse_operations.vitri.so_lo import gan_so_lo_hien_thi

		_tao_lo("HELP-MA-4", custom_so_lo="HELP-SO-4")
		dong = [{"so_lo": "HELP-MA-4"}, {"so_lo": None}]
		kq = gan_so_lo_hien_thi(dong)
		self.assertIs(kq, dong)
		self.assertEqual(dong[0], {"so_lo": "HELP-MA-4", "so_lo_hien_thi": "HELP-SO-4"})
		self.assertEqual(dong[1]["so_lo_hien_thi"], "")

	def test_tim_lo_tra_ca_ten_cu_lan_so_lo_moi(self):
		"""E3: "ABC" vừa là TÊN lô cũ của mặt hàng A, vừa là SỐ LÔ của lô mới mặt hàng B."""
		from erpnext.warehouse_operations.vitri.so_lo import tim_lo

		cu = _tao_lo("HELP-ABC")
		moi = _tao_lo("HELP-L26-1", item=ITEM_LO_B, custom_so_lo="HELP-ABC", expiry_date="2030-01-31")
		kq = tim_lo("HELP-ABC")
		self.assertEqual([x["ma_lo"] for x in kq], [cu.name, moi.name])
		self.assertEqual(
			set(kq[1]), {"ma_lo", "so_lo_hien_thi", "vat_tu", "ten_hang", "hsd"}
		)
		self.assertEqual(kq[1]["so_lo_hien_thi"], "HELP-ABC")
		self.assertEqual(kq[1]["vat_tu"], ITEM_LO_B)

	def test_tim_lo_rong_tra_rong(self):
		from erpnext.warehouse_operations.vitri.so_lo import tim_lo

		self.assertEqual(tim_lo("  "), [])
		self.assertEqual(tim_lo("HELP-KHONG-CO-GI"), [])

	def test_gan_hien_thi_toan_bo_moi_do_sau(self):
		from erpnext.warehouse_operations.vitri.so_lo import gan_hien_thi_toan_bo

		_tao_lo("HELP-MA-5", custom_so_lo="HELP-SO-5")
		kq = {
			"dong": [{"so_lo": "HELP-MA-5", "lo_nen_lay": "HELP-MA-5"}, {"so_lo": None}],
			"cho": {"lo_khac": {"so_lo": "HELP-MA-5", "so_lo_dang_chot": "HELP-KHONG-CO"}},
			"khac": "HELP-MA-5",
		}
		# Làm ấm cache meta/cột của `Batch` để chỉ đếm truy vấn của chính hàm.
		gan_hien_thi_toan_bo({"so_lo": "HELP-MA-5"})
		with self.assertQueryCount(1):
			self.assertIs(gan_hien_thi_toan_bo(kq), kq)
		self.assertEqual(kq["dong"][0]["so_lo_hien_thi"], "HELP-SO-5")
		self.assertEqual(kq["dong"][0]["lo_nen_lay_hien_thi"], "HELP-SO-5")
		self.assertIsNone(kq["dong"][1]["so_lo_hien_thi"])
		lk = kq["cho"]["lo_khac"]
		self.assertEqual((lk["so_lo_hien_thi"], lk["so_lo_dang_chot_hien_thi"]), ("HELP-SO-5", "HELP-KHONG-CO"))
		self.assertEqual(kq["khac"], "HELP-MA-5")

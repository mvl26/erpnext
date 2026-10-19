"""HSD tối thiểu khách yêu cầu (19/10/2026) — trang Lấy hàng gợi ý và chặn lô theo sàn.

Sàn đến từ hook `han_toi_thieu_lo_xuat` (app ngoài, vd miyano_portal, đăng ký);
erpnext không import app đó. Bài test cài hook GIẢ bằng cách vá `frappe.get_hooks`
CHỈ cho đúng tên hook này — mọi hook khác (doc_events khi lưu phiếu…) đi qua bản
gốc. Site thử có cài miyano_portal nên hook THẬT luôn có mặt nếu không vá: mọi bài
ở đây đều vá (có sàn, hoặc danh sách rỗng) để kết quả không phụ thuộc site.
"""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, formatdate, getdate, nowdate

from erpnext.warehouse_operations.tests.test_lay_hang import (
	CTY,
	DIEM_TEST,
	ITEM,
	KHACH,
	KHO,
	LO,
	O_GAN,
	O_XA,
	_chuyen_vao_o,
	_chuyen_vao_o_lo,
	_lo,
	_nhap_kho,
	_nhap_kho_lo,
	_o,
	_vat_tu,
	bo_bat_buoc_lay_hang,
)

TEN_HOOK = "han_toi_thieu_lo_xuat"
HAM_GIA = "erpnext.warehouse_operations.tests.test_lay_hang_han_khach.san_gia"
LO_GAN_HAN = "9L-LO-HK-GAN"
LO_KHONG_HSD = "9L-LO-HK-KHONG-HSD"

# Sàn mà hook giả trả về — đặt trong từng bài.
SAN = {"gia_tri": None}


def san_gia(doc, d):
	return SAN["gia_tri"]


def hook_no(doc, d):
	frappe.throw("hook HSD hỏng")


HAM_NO = "erpnext.warehouse_operations.tests.test_lay_hang_han_khach.hook_no"

# Khoá của một dòng `mo_phieu_giao` và của kết quả `quet_de_lay` TRƯỚC tính năng —
# không hook thì phải y nguyên, không thêm khoá nào.
KHOA_DONG_CU = {
	"dong_hang", "vat_tu", "ten_hang", "don_vi", "don_vi_dong", "he_so_dong", "don_vi_ton",
	"can_lay_ton", "da_lay_ton", "don_vi_chon", "so_lo", "hsd", "lo_nen_lay", "lo_nen_lay_hsd",
	"lo_tren_phieu_muon_hon", "can_lay", "da_lay", "can_quet", "ly_do_khong_quet",
	"thieu_trong_lo", "da_chot_thieu", "chot_thieu_boi", "chot_thieu_luc", "o_nen_lay", "da_lay_o",
}  # fmt: skip
KHOA_HAN_KHACH = {"han_khach", "khong_con_lo_dat_han", "lo_dang_chot_duoi_han"}
KHOA_QUET_LO_CU = {"loai", "so_lo", "dong_hang", "vat_tu", "nhieu_dong", "hsd", "het_han"}
KHOA_QUET_LO_KHAC_CU = {
	"loai", "so_lo", "dong_hang", "vat_tu", "hsd", "hsd_dang_chot", "so_lo_dang_chot",
	"han_xa_hon", "nhieu_dong", "het_han",
}  # fmt: skip


_get_hooks_goc = frappe.get_hooks


def _hook(ds):
	"""Vá `frappe.get_hooks`: tên `han_toi_thieu_lo_xuat` trả `ds`, tên khác đi bản gốc."""

	def _thay(hook=None, *args, **kwargs):
		if hook == TEN_HOOK:
			return list(ds)
		return _get_hooks_goc(hook, *args, **kwargs)

	return patch("frappe.get_hooks", side_effect=_thay)


def _lo_moi(ten, hsd):
	if not frappe.db.exists("Batch", ten):
		frappe.get_doc({"doctype": "Batch", "batch_id": ten, "item": ITEM, "expiry_date": hsd}).insert(
			ignore_permissions=True
		)
	else:
		frappe.db.set_value("Batch", ten, "expiry_date", hsd)
	return ten


def _phieu_giao_lo(so_lo, so_luong=12):
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
					"batch_no": so_lo,
					"use_serial_batch_fields": 1,
				}
			],
		}
	)
	dn.insert(ignore_permissions=True)
	return dn


def _cau_chan(so_lo, hsd, san):
	if not hsd:
		return (
			f"Lô {so_lo} không có HSD — không đạt HSD khách yêu cầu (đến {formatdate(san, 'dd/mm/yyyy')}) "
			"— lấy lô khác, hoặc nhờ kinh doanh ghi ngoại lệ trên đơn."
		)
	return (
		f"Lô {so_lo} HSD {formatdate(hsd, 'dd/mm/yyyy')} thấp hơn HSD khách yêu cầu "
		f"(đến {formatdate(san, 'dd/mm/yyyy')}) "
		"— lấy lô khác, hoặc nhờ kinh doanh ghi ngoại lệ trên đơn."
	)


class TestLayHangHanKhach(FrappeTestCase):
	def setUp(self):
		self.enterContext(bo_bat_buoc_lay_hang())
		frappe.set_user("Administrator")
		frappe.db.savepoint(DIEM_TEST)
		_vat_tu()
		_lo()  # LO hết hạn 31/01/2029 — xa hạn
		_o(O_GAN, thu_tu=1)
		_o(O_XA, thu_tu=2)
		_nhap_kho(30)
		_chuyen_vao_o([(O_GAN, 30)])
		# Lô GẦN hạn (còn 60 ngày): FEFO thuần sẽ gợi ý lô này trước LO.
		self.hsd_gan = getdate(add_days(nowdate(), 60))
		_lo_moi(LO_GAN_HAN, self.hsd_gan)
		_nhap_kho_lo(LO_GAN_HAN, 10)
		_chuyen_vao_o_lo(LO_GAN_HAN, [(O_XA, 10)])
		# Sàn khách: còn ít nhất ~1 năm — LO đạt, LO_GAN_HAN không.
		self.san = getdate(add_days(nowdate(), 365))
		SAN["gia_tri"] = self.san

	def tearDown(self):
		SAN["gia_tri"] = None
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point=DIEM_TEST)

	def test_goi_y_bo_lo_duoi_han(self):
		"""Lô gần hạn bị bỏ khỏi gợi ý, gợi ý lô xa hạn đạt sàn."""
		from erpnext.warehouse_operations.vitri.lay_hang import _lo_nen_lay, mo_phieu_giao

		# Không sàn: FEFO thuần chọn lô gần hạn.
		self.assertEqual(_lo_nen_lay(KHO, ITEM).so_lo, LO_GAN_HAN)
		self.assertEqual(_lo_nen_lay(KHO, ITEM, han_toi_thieu=self.san).so_lo, LO)

		dn = _phieu_giao_lo(LO)
		with _hook([HAM_GIA]):
			p = mo_phieu_giao(dn.name)
		self.assertEqual(p["dong"][0]["lo_nen_lay"], LO)

	def test_goi_y_loai_lo_khong_hsd_khi_co_san(self):
		from erpnext.warehouse_operations.vitri.lay_hang import _lo_nen_lay

		frappe.db.set_value("Batch", LO_GAN_HAN, "expiry_date", None)
		self.assertEqual(_lo_nen_lay(KHO, ITEM).so_lo, LO)  # không HSD xếp sau cùng
		frappe.db.set_value("Batch", LO, "expiry_date", None)
		self.assertIsNotNone(_lo_nen_lay(KHO, ITEM))
		self.assertIsNone(_lo_nen_lay(KHO, ITEM, han_toi_thieu=self.san))

	def test_khong_hook_goi_y_nhu_cu(self):
		"""Không hook → `_han_toi_thieu` None, gợi ý y như trước (FEFO thuần)."""
		from erpnext.warehouse_operations.vitri.lay_hang import _han_toi_thieu, _lo_nen_lay, mo_phieu_giao

		dn = _phieu_giao_lo(LO)
		with _hook([]):
			self.assertIsNone(_han_toi_thieu(dn, dn.items[0]))
			p = mo_phieu_giao(dn.name)
		self.assertEqual(p["dong"][0]["lo_nen_lay"], LO_GAN_HAN)
		self.assertEqual(p["dong"][0]["lo_nen_lay_hsd"], self.hsd_gan)
		self.assertEqual(_lo_nen_lay(KHO, ITEM), _lo_nen_lay(KHO, ITEM, han_toi_thieu=None))

	def test_han_toi_thieu_goi_ham_cuoi(self):
		from erpnext.warehouse_operations.vitri.lay_hang import _han_toi_thieu

		dn = _phieu_giao_lo(LO)
		with _hook(["frappe.utils.nowdate", HAM_GIA]):
			self.assertEqual(_han_toi_thieu(dn, dn.items[0]), self.san)

	def test_doi_lo_duoi_han_bi_chan(self):
		from erpnext.warehouse_operations.vitri.lay_hang import doi_lo

		dn = _phieu_giao_lo(LO)
		dong = dn.items[0].name
		with _hook([HAM_GIA]):
			with self.assertRaises(frappe.ValidationError) as ctx:
				doi_lo(dn.name, dong, LO_GAN_HAN)
		self.assertIn(_cau_chan(LO_GAN_HAN, self.hsd_gan, self.san), str(ctx.exception))
		self.assertEqual(frappe.db.get_value("Delivery Note Item", dong, "batch_no"), LO)

	def test_doi_lo_khong_hsd_bi_chan(self):
		from erpnext.warehouse_operations.vitri.lay_hang import doi_lo

		_lo_moi(LO_KHONG_HSD, None)
		dn = _phieu_giao_lo(LO_GAN_HAN, 5)
		with _hook([HAM_GIA]):
			with self.assertRaises(frappe.ValidationError) as ctx:
				doi_lo(dn.name, dn.items[0].name, LO_KHONG_HSD)
		self.assertIn(_cau_chan(LO_KHONG_HSD, None, self.san), str(ctx.exception))

	def test_doi_lo_dat_han_van_doi_duoc(self):
		from erpnext.warehouse_operations.vitri.lay_hang import doi_lo

		dn = _phieu_giao_lo(LO_GAN_HAN, 5)
		dong = dn.items[0].name
		with _hook([HAM_GIA]):
			doi_lo(dn.name, dong, LO)
		self.assertEqual(frappe.db.get_value("Delivery Note Item", dong, "batch_no"), LO)

	def test_doi_lo_khong_san_nhu_cu(self):
		from erpnext.warehouse_operations.vitri.lay_hang import doi_lo

		dn = _phieu_giao_lo(LO, 5)
		dong = dn.items[0].name
		with _hook([]):
			doi_lo(dn.name, dong, LO_GAN_HAN)
		self.assertEqual(frappe.db.get_value("Delivery Note Item", dong, "batch_no"), LO_GAN_HAN)

	def test_ghi_da_lay_lo_duoi_han_bi_chan(self):
		from erpnext.warehouse_operations.vitri.lay_hang import ghi_da_lay

		dn = _phieu_giao_lo(LO_GAN_HAN, 5)
		with _hook([HAM_GIA]):
			with self.assertRaises(frappe.ValidationError) as ctx:
				ghi_da_lay(dn.name, dn.items[0].name, LO_GAN_HAN, O_XA, 5)
		self.assertIn(_cau_chan(LO_GAN_HAN, self.hsd_gan, self.san), str(ctx.exception))
		self.assertEqual(len(frappe.get_doc("Delivery Note", dn.name).custom_phan_bo_vi_tri), 0)

	def test_ghi_da_lay_lo_dat_han_ghi_duoc(self):
		from erpnext.warehouse_operations.vitri.lay_hang import ghi_da_lay

		dn = _phieu_giao_lo(LO, 5)
		with _hook([HAM_GIA]):
			p = ghi_da_lay(dn.name, dn.items[0].name, LO, O_GAN, 5)
		self.assertEqual(p["dong"][0]["da_lay"], 5.0)

	def test_tach_dong_lo_duoi_han_bi_chan(self):
		from erpnext.warehouse_operations.vitri.lay_hang import ghi_da_lay, tach_dong_theo_lo

		dn = _phieu_giao_lo(LO, 12)
		dong = dn.items[0].name
		with _hook([HAM_GIA]):
			ghi_da_lay(dn.name, dong, LO, O_GAN, 8)
			with self.assertRaises(frappe.ValidationError) as ctx:
				tach_dong_theo_lo(dn.name, dong, LO_GAN_HAN)
		self.assertIn(_cau_chan(LO_GAN_HAN, self.hsd_gan, self.san), str(ctx.exception))
		self.assertEqual(len(frappe.get_doc("Delivery Note", dn.name).items), 1)

	# ------------------------------------------------------------------
	# Vòng sửa 1 (spec §4.4): báo thủ kho sàn khách / hết lô đạt / lô dưới sàn.
	# ------------------------------------------------------------------

	def test_mo_phieu_co_san_tra_khoa_han_khach(self):
		from erpnext.warehouse_operations.vitri.lay_hang import mo_phieu_giao

		dn_dat = _phieu_giao_lo(LO, 5)
		dn_duoi = _phieu_giao_lo(LO_GAN_HAN, 5)
		with _hook([HAM_GIA]):
			dat = mo_phieu_giao(dn_dat.name)["dong"][0]
			duoi = mo_phieu_giao(dn_duoi.name)["dong"][0]
		self.assertEqual(set(dat), KHOA_DONG_CU | KHOA_HAN_KHACH)
		self.assertEqual(dat["han_khach"], self.san)
		self.assertFalse(dat["khong_con_lo_dat_han"])
		self.assertFalse(dat["lo_dang_chot_duoi_han"])
		self.assertEqual(duoi["han_khach"], self.san)
		self.assertFalse(duoi["khong_con_lo_dat_han"])
		self.assertTrue(duoi["lo_dang_chot_duoi_han"])
		self.assertEqual(duoi["lo_nen_lay"], LO)

	def test_mo_phieu_het_lo_dat_han_bao_ly_do(self):
		"""Còn hàng nhưng không lô nào đạt sàn → `khong_con_lo_dat_han`, không gợi ý lô."""
		from erpnext.warehouse_operations.vitri.lay_hang import mo_phieu_giao

		SAN["gia_tri"] = getdate("2030-01-01")  # xa hơn cả LO (31/01/2029)
		dn = _phieu_giao_lo(LO, 5)
		with _hook([HAM_GIA]):
			dong = mo_phieu_giao(dn.name)["dong"][0]
		self.assertTrue(dong["khong_con_lo_dat_han"])
		self.assertTrue(dong["lo_dang_chot_duoi_han"])
		self.assertIsNone(dong["lo_nen_lay"])
		self.assertEqual(dong["han_khach"], getdate("2030-01-01"))

	def test_khong_hook_payload_khong_doi(self):
		from erpnext.warehouse_operations.vitri.lay_hang import mo_phieu_giao, quet_de_lay

		dn = _phieu_giao_lo(LO, 5)
		with _hook([]):
			dong = mo_phieu_giao(dn.name)["dong"][0]
			lo = quet_de_lay(dn.name, LO)
			lo_khac = quet_de_lay(dn.name, LO_GAN_HAN)
		self.assertEqual(set(dong), KHOA_DONG_CU)
		self.assertEqual(lo["loai"], "lo")
		self.assertEqual(set(lo), KHOA_QUET_LO_CU)
		self.assertEqual(lo_khac["loai"], "lo_khac")
		self.assertEqual(set(lo_khac), KHOA_QUET_LO_KHAC_CU)

	def test_quet_de_lay_bao_duoi_han_khach(self):
		from erpnext.warehouse_operations.vitri.lay_hang import quet_de_lay

		dn = _phieu_giao_lo(LO, 5)
		with _hook([HAM_GIA]):
			lo = quet_de_lay(dn.name, LO)
			lo_khac = quet_de_lay(dn.name, LO_GAN_HAN)
		self.assertEqual(lo["loai"], "lo")
		self.assertFalse(lo["duoi_han_khach"])
		self.assertEqual(lo["han_khach"], self.san)
		self.assertEqual(lo_khac["loai"], "lo_khac")
		self.assertTrue(lo_khac["duoi_han_khach"])
		self.assertEqual(lo_khac["han_khach"], self.san)

	def test_hook_loi_mo_phieu_khong_goi_y_va_ghi_van_chan(self):
		"""Hook nổ: màn vẫn mở, KHÔNG gợi ý lô (không bao giờ gợi ý chưa lọc), có log
		lỗi; quét vẫn nhận ra lô; các hàm ghi thì nổ (chặn, không cho qua)."""
		from erpnext.warehouse_operations.vitri.lay_hang import doi_lo, mo_phieu_giao, quet_de_lay

		dn = _phieu_giao_lo(LO, 5)
		so_log = frappe.db.count("Error Log")
		with _hook([HAM_NO]):
			dong = mo_phieu_giao(dn.name)["dong"][0]
			lo = quet_de_lay(dn.name, LO)
			with self.assertRaisesRegex(frappe.ValidationError, "hook HSD hỏng"):
				doi_lo(dn.name, dn.items[0].name, LO_GAN_HAN)
		self.assertEqual(set(dong), KHOA_DONG_CU)
		self.assertIsNone(dong["lo_nen_lay"])
		self.assertEqual(set(lo), KHOA_QUET_LO_CU)
		self.assertGreater(frappe.db.count("Error Log"), so_log)
		self.assertEqual(frappe.db.get_value("Delivery Note Item", dn.items[0].name, "batch_no"), LO)

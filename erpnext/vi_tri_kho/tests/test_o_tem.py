"""Luật "xếp đúng ô in trên tem lô" (chủ đầu tư 19/09/2026) — `vitri/o_tem.py`.

Chặn ở MÁY CHỦ (`LocationTransfer.validate`), nên mọi bài đi qua phiếu xếp thật
chứ không qua trang PDA: trang chỉ báo sớm, form máy tính cũng phải bị chặn.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import nowdate

from erpnext.vi_tri_kho.tests.test_lay_hang import (
	ITEM,
	ITEM_KHONG_LO,
	KHO,
	LO,
	O_GAN,
	O_XA,
	_lo,
	_nhap_kho,
	_nhap_kho_khong_lo,
	_o,
	_vat_tu,
	_vat_tu_khong_lo,
)
from erpnext.vi_tri_kho.vitri import so

DIEM = "test_o_tem"
O_KHAC = "9L01010103"
THU_KHO = "thukho.otem@example.com"
TRUONG_KHO = "truongkho.otem@example.com"


def _chua_xep():
	return frappe.db.get_value("Storage Location", {"kho": KHO, "la_o_chua_xep": 1})


def _phieu(dong):
	return frappe.get_doc(
		{"doctype": "Location Transfer", "kho": KHO, "ngay": nowdate(), "items": dong}
	)


def _dong(den_o, tu_o=None, so_luong=5, vat_tu=ITEM, so_lo=LO):
	return {"vat_tu": vat_tu, "so_lo": so_lo, "tu_o": tu_o or _chua_xep(), "den_o": den_o, "so_luong": so_luong}


def _lo_khac(ten):
	if not frappe.db.exists("Batch", ten):
		frappe.get_doc(
			{"doctype": "Batch", "batch_id": ten, "item": ITEM, "expiry_date": "2029-06-30"}
		).insert(ignore_permissions=True)
	frappe.db.set_value("Batch", ten, "custom_o_in_tem", None)
	return ten


def _nguoi(email, vai_tro):
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": email.split("@")[0],
				"send_welcome_email": 0,
				"roles": [{"role": vai_tro}],
			}
		).insert(ignore_permissions=True)
	return email


class TestXepDungOTrenTem(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.savepoint(DIEM)
		_vat_tu()
		_lo()
		for o in (O_GAN, O_XA, O_KHAC):
			_o(o)
			frappe.db.set_value("Storage Location", o, "disabled", 0)
		_nhap_kho(30)
		frappe.db.set_value("Batch", LO, "custom_o_in_tem", O_GAN)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point=DIEM)

	def test_dung_o_tren_tem_thi_xep_duoc(self):
		p = _phieu([_dong(O_GAN)])
		p.insert(ignore_permissions=True)
		p.submit()
		self.assertEqual(so.ton_o(O_GAN, ITEM, LO), 5.0)

	def test_sai_o_bi_chan_ngay_luc_luu(self):
		with self.assertRaisesRegex(frappe.ValidationError, "không phải ô in trên tem"):
			_phieu([_dong(O_XA)]).insert(ignore_permissions=True)

	def test_chuyen_giua_hai_o_that_cung_bi_chan(self):
		"""Chủ đầu tư chọn "mọi lần xếp/chuyển" — không chỉ hàng mới về."""
		p = _phieu([_dong(O_GAN)])
		p.insert(ignore_permissions=True)
		p.submit()
		with self.assertRaisesRegex(frappe.ValidationError, "không phải ô in trên tem"):
			_phieu([_dong(O_XA, tu_o=O_GAN, so_luong=2)]).insert(ignore_permissions=True)

	def test_lo_chua_co_o_tren_tem_bi_chan(self):
		frappe.db.set_value("Batch", LO, "custom_o_in_tem", None)
		with self.assertRaisesRegex(frappe.ValidationError, "chưa có ô trên tem"):
			_phieu([_dong(O_GAN)]).insert(ignore_permissions=True)

	def test_o_tren_tem_dang_ngung_dung_bi_chan(self):
		frappe.db.set_value("Storage Location", O_GAN, "disabled", 1)
		with self.assertRaisesRegex(frappe.ValidationError, "Ngừng dùng"):
			_phieu([_dong(O_GAN)]).insert(ignore_permissions=True)

	def test_o_tren_tem_bi_mat_hang_khac_chiem_bi_chan(self):
		_vat_tu_khong_lo()
		_nhap_kho_khong_lo(3)
		frappe.flags.vi_tri_kho_bo_kiem_o_tem = True
		try:
			_phieu([_dong(O_GAN, vat_tu=ITEM_KHONG_LO, so_lo=None, so_luong=3)]).insert(
				ignore_permissions=True
			).submit()
		finally:
			frappe.flags.vi_tri_kho_bo_kiem_o_tem = None
		with self.assertRaisesRegex(frappe.ValidationError, "mặt hàng khác"):
			_phieu([_dong(O_GAN)]).insert(ignore_permissions=True)

	def test_hang_khong_lo_khong_bi_kiem(self):
		_vat_tu_khong_lo()
		_nhap_kho_khong_lo(3)
		p = _phieu([_dong(O_XA, vat_tu=ITEM_KHONG_LO, so_lo=None, so_luong=3)])
		p.insert(ignore_permissions=True)
		p.submit()
		self.assertEqual(so.ton_o(O_XA, ITEM_KHONG_LO, None), 3.0)

	def test_doi_o_tren_tem_roi_xep_o_moi_duoc(self):
		from erpnext.vi_tri_kho.vitri.o_tem import doi_o_tren_tem

		doi_o_tren_tem(LO, O_XA, "dồn kệ")
		p = _phieu([_dong(O_XA)])
		p.insert(ignore_permissions=True)
		p.submit()
		self.assertEqual(so.ton_o(O_XA, ITEM, LO), 5.0)
		ghi_chu = frappe.get_all(
			"Comment",
			filters={"reference_doctype": "Batch", "reference_name": LO, "comment_type": "Comment"},
			pluck="content",
			order_by="creation desc",
			limit=1,
		)
		self.assertIn("→", ghi_chu[0])
		self.assertIn("dồn kệ", ghi_chu[0])


class TestQuyenDoiOTrenTem(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.savepoint(DIEM)
		_vat_tu()
		_lo()
		for o in (O_GAN, O_XA):
			_o(o)
			frappe.db.set_value("Storage Location", o, "disabled", 0)
		_nguoi(THU_KHO, "Stock User")
		_nguoi(TRUONG_KHO, "Stock Manager")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point=DIEM)

	def test_thu_kho_dat_duoc_khi_lo_chua_co_o(self):
		from erpnext.vi_tri_kho.vitri.o_tem import doi_o_tren_tem

		frappe.db.set_value("Batch", LO, "custom_o_in_tem", None)
		frappe.set_user(THU_KHO)
		doi_o_tren_tem(LO, O_GAN)
		self.assertEqual(frappe.db.get_value("Batch", LO, "custom_o_in_tem"), O_GAN)

	def test_thu_kho_khong_doi_duoc_o_da_co(self):
		from erpnext.vi_tri_kho.vitri.o_tem import doi_o_tren_tem

		frappe.db.set_value("Batch", LO, "custom_o_in_tem", O_GAN)
		frappe.set_user(THU_KHO)
		with self.assertRaises(frappe.PermissionError):
			doi_o_tren_tem(LO, O_XA)
		self.assertEqual(frappe.db.get_value("Batch", LO, "custom_o_in_tem"), O_GAN)

	def test_truong_kho_doi_duoc(self):
		from erpnext.vi_tri_kho.vitri.o_tem import doi_o_tren_tem

		frappe.db.set_value("Batch", LO, "custom_o_in_tem", O_GAN)
		frappe.set_user(TRUONG_KHO)
		doi_o_tren_tem(LO, O_XA, "tách kệ")
		self.assertEqual(frappe.db.get_value("Batch", LO, "custom_o_in_tem"), O_XA)

	def test_khong_dat_duoc_o_chua_xep_hay_o_nhom(self):
		from erpnext.vi_tri_kho.vitri.o_tem import doi_o_tren_tem

		frappe.db.set_value("Batch", LO, "custom_o_in_tem", None)
		with self.assertRaisesRegex(frappe.ValidationError, "Chưa xếp"):
			doi_o_tren_tem(LO, _chua_xep())
		nhom = frappe.db.get_value("Storage Location", O_GAN, "parent_storage_location")
		with self.assertRaisesRegex(frappe.ValidationError, "nút nhóm"):
			doi_o_tren_tem(LO, nhom)


class TestManHinhBaoSom(FrappeTestCase):
	"""Trang PDA và form máy tính đọc cùng `kiem_o_tem` qua `xep.py`."""

	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.savepoint(DIEM)
		_vat_tu()
		_lo()
		_o(O_GAN)
		frappe.db.set_value("Storage Location", O_GAN, "disabled", 0)
		_nhap_kho(30)
		frappe.cache().delete_value(f"erpnext:barcode_scan:{LO}")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point=DIEM)

	def test_quet_lo_tra_o_tren_tem(self):
		from erpnext.vi_tri_kho.vitri.xep import quet_de_xep

		frappe.db.set_value("Batch", LO, "custom_o_in_tem", O_GAN)
		kq = quet_de_xep(KHO, LO)
		self.assertEqual((kq["o_tem"]["o"], kq["o_tem"]["loi"], kq["o_tem"]["kiem"]), (O_GAN, None, True))

	def test_quet_lo_chua_co_o_bao_loi_ngay(self):
		from erpnext.vi_tri_kho.vitri.xep import quet_de_xep

		frappe.db.set_value("Batch", LO, "custom_o_in_tem", None)
		kq = quet_de_xep(KHO, LO)
		self.assertIn("chưa có ô trên tem", kq["o_tem"]["loi"])

	def test_hang_chua_xep_dien_o_theo_tem_hoac_de_trong_kem_ly_do(self):
		from erpnext.vi_tri_kho.vitri.xep import hang_chua_xep

		frappe.db.set_value("Batch", LO, "custom_o_in_tem", O_GAN)
		dong = next(d for d in hang_chua_xep(KHO) if d["so_lo"] == LO)
		self.assertEqual(dong["den_o"], O_GAN)

		frappe.db.set_value("Batch", LO, "custom_o_in_tem", None)
		dong = next(d for d in hang_chua_xep(KHO) if d["so_lo"] == LO)
		self.assertIsNone(dong["den_o"])
		self.assertIn("chưa có ô trên tem", dong["ly_do_goi_y"])


class TestDatOHangLoat(FrappeTestCase):
	"""Công cụ đặt ô hàng loạt (chủ đầu tư duyệt 20/09/2026) — 60 lô đang có tồn
	mà chưa có ô trên tem bị luật khoá cứng, đặt tay từng lô là 60 lần mở form."""

	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.savepoint(DIEM)
		_vat_tu()
		_lo()
		_o(O_GAN)
		frappe.db.set_value("Storage Location", O_GAN, "disabled", 0)
		_nhap_kho(10)
		frappe.db.set_value("Batch", LO, "custom_o_in_tem", None)
		_nguoi(THU_KHO, "Stock User")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point=DIEM)

	def test_liet_ke_lo_dang_co_ton_ma_chua_co_o(self):
		from erpnext.vi_tri_kho.vitri.o_tem import lo_chua_co_o

		ds = {d["so_lo"]: d for d in lo_chua_co_o(KHO)}
		self.assertIn(LO, ds)
		self.assertEqual(ds[LO]["vat_tu"], ITEM)
		self.assertEqual(float(ds[LO]["ton"]), 10.0)

		# Đặt ô xong thì lô biến khỏi danh sách — đây là thước đo "còn bao nhiêu
		# lô đang kẹt", không phải danh sách mọi lô.
		frappe.db.set_value("Batch", LO, "custom_o_in_tem", O_GAN)
		self.assertNotIn(LO, {d["so_lo"] for d in lo_chua_co_o(KHO)})

	def test_dat_hang_loat_ghi_o_va_bao_rieng_dong_hong(self):
		from erpnext.vi_tri_kho.vitri.o_tem import dat_o_hang_loat

		kq = dat_o_hang_loat(
			[
				{"so_lo": LO, "o": O_GAN},
				{"so_lo": LO, "o": O_XA},  # lần hai: lô vừa có ô, phải bị từ chối
				{"so_lo": LO, "o": ""},  # chưa chọn ô
			]
		)
		self.assertEqual([x["so_lo"] for x in kq["xong"]], [LO])
		self.assertEqual(frappe.db.get_value("Batch", LO, "custom_o_in_tem"), O_GAN)
		self.assertEqual(len(kq["loi"]), 2)
		self.assertIn("đã có ô trên tem", kq["loi"][0]["loi"])
		self.assertIn("chưa chọn ô", kq["loi"][1]["loi"])

	def test_mot_dong_hong_khong_keo_do_dong_da_dat(self):
		"""Savepoint từng dòng: lô 2 hỏng không được xoá mất lô 1 đã đặt xong."""
		from erpnext.vi_tri_kho.vitri.o_tem import dat_o_hang_loat

		lo2 = _lo_khac("9L-LO-OTEM-2")
		kq = dat_o_hang_loat([{"so_lo": LO, "o": O_GAN}, {"so_lo": lo2, "o": "9L-KHONG-CO-O-NAY"}])
		self.assertEqual([x["so_lo"] for x in kq["xong"]], [LO])
		self.assertEqual(frappe.db.get_value("Batch", LO, "custom_o_in_tem"), O_GAN)
		self.assertIsNone(frappe.db.get_value("Batch", lo2, "custom_o_in_tem"))

	def test_thu_kho_dung_duoc_nhung_nguoi_khong_vai_tro_kho_bi_chan(self):
		from erpnext.vi_tri_kho.vitri.o_tem import dat_o_hang_loat, lo_chua_co_o

		frappe.set_user(THU_KHO)
		self.assertTrue(any(d["so_lo"] == LO for d in lo_chua_co_o(KHO)))
		dat_o_hang_loat([{"so_lo": LO, "o": O_GAN}])
		self.assertEqual(frappe.db.get_value("Batch", LO, "custom_o_in_tem"), O_GAN)

		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			lo_chua_co_o(KHO)
		with self.assertRaises(frappe.PermissionError):
			dat_o_hang_loat([{"so_lo": LO, "o": O_XA}])

	def test_kiem_o_tem_noi_ro_lo_CHUA_co_o_de_trang_pda_hien_nut(self):
		"""Trang PDA chỉ hiện nút "Đặt ô trên tem" cho ca CHƯA có ô — ô trên tem
		HỎNG là việc của trưởng kho, không có nút."""
		from erpnext.vi_tri_kho.vitri.o_tem import kiem_o_tem

		self.assertTrue(kiem_o_tem(ITEM, LO, KHO)["chua_co_o"])

		frappe.db.set_value("Batch", LO, "custom_o_in_tem", O_GAN)
		frappe.db.set_value("Storage Location", O_GAN, "disabled", 1)
		t = kiem_o_tem(ITEM, LO, KHO)
		self.assertFalse(t["chua_co_o"])
		self.assertIn("Ngừng dùng", t["loi"])

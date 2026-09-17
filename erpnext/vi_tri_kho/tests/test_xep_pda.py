"""Xếp hàng trên PDA — quét tem lô, quét tem ô, dồn nhiều dòng vào một phiếu xếp.

Chủ đầu tư 17/09/2026: "giao diện xếp hàng cũng là pda … quét mã lô thì hiển thị
ra mặt hàng và thực hiện xác nhận xếp, có thể xếp nhiều hàng trên 1 phiếu".

Điều bài này khoá, xếp theo cái giá nếu sai:

1. Mỗi dòng xác nhận được LƯU NGAY lên một phiếu nháp của chính người quét, và
   mở lại trang thì gặp lại đúng phiếu đó. Giữ dòng trong bộ nhớ trình duyệt thì
   PDA hết pin giữa ca là mất cả chục dòng đã xếp tay ngoài kệ.
2. Số "còn xếp được" ở một ô TRỪ ĐI những dòng đã nằm trên phiếu nháp — phiếu
   nháp chưa ghi sổ nên tồn của ô chưa đổi; không trừ thì quét cùng một lô hai
   lần sẽ xếp gấp đôi số hàng đang có, và chỉ tới lúc DUYỆT mới nổ.
3. Phiếu nháp là của TỪNG NGƯỜI: hai thủ kho cùng kho không dồn dòng vào nhau.
4. Mọi phép kiểm dòng đi qua `LocationTransfer.validate` — không chép lại.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import now, nowdate

from erpnext.vi_tri_kho.vitri import so
from erpnext.vi_tri_kho.vitri.xep import (
	duyet_phieu_xep,
	phieu_xep_dang_lam,
	quet_de_xep,
	them_dong_xep,
	xoa_dong_xep,
)

KHO = "Kho Miyano - MYN"
CTY = "Miyano Việt Nam"
VAT_TU = "9P-VT-PDA-CO-LO"
VAT_TU_KHONG_LO = "9P-VT-PDA-KHONG-LO"
LO = "9P-LO-PDA-01"
O_A = "9P01010101"
O_B = "9P01010102"
O_C = "9P01010103"
NGUOI_KHAC = "xep-pda-nguoi-khac@mo-phong.local"
DIEM_TEST = "test_xep_pda"


def _o(ma_o):
	if not frappe.db.exists("Storage Location", ma_o):
		frappe.get_doc({"doctype": "Storage Location", "ma_o": ma_o, "kho": KHO}).insert(
			ignore_permissions=True
		)
	return ma_o


def _vat_tu(ma, co_lo):
	if not frappe.db.exists("Item", ma):
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": ma,
				"item_name": f"Hàng thử {ma}",
				"item_group": "All Item Groups",
				"stock_uom": "Nos",
				"is_stock_item": 1,
				"has_batch_no": co_lo,
			}
		).insert(ignore_permissions=True)
	return ma


def _nap(o, vat_tu, so_lo, sl):
	"""Đặt sẵn tồn vào một ô — khuôn `test_phieu_xep_vi_tri._nap`."""
	so.ghi_dong_so(
		o=o,
		kho=KHO,
		vat_tu=vat_tu,
		so_lo=so_lo,
		so_luong=sl,
		chung_tu_type=None,
		chung_tu=None,
		chung_tu_row="NAP-TIEN-DE-TEST",
		sle=None,
		ngay=nowdate(),
		thoi_diem=now(),
		company=CTY,
	)


def _o_chua_xep():
	return frappe.db.get_value("Storage Location", {"kho": KHO, "la_o_chua_xep": 1})


class TestXepTrenPda(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		# `FrappeTestCase` rollback theo LỚP, không theo bài — không có savepoint
		# riêng thì tồn nạp ở `setUp` và phiếu nháp của bài trước dồn sang bài sau
		# (đã đỏ đúng kiểu đó ở lần chạy đầu: "178.0 != 30.0").
		frappe.db.savepoint(DIEM_TEST)
		for ma in (LO, O_A, O_B, O_C, VAT_TU_KHONG_LO, "9P01"):
			frappe.cache().delete_value(f"erpnext:barcode_scan:{ma}")

		_vat_tu(VAT_TU, 1)
		_vat_tu(VAT_TU_KHONG_LO, 0)
		if not frappe.db.exists("Batch", LO):
			frappe.get_doc(
				{"doctype": "Batch", "batch_id": LO, "item": VAT_TU, "expiry_date": "2028-05-01"}
			).insert(ignore_permissions=True)
		for o in (O_A, O_B, O_C):
			_o(o)

		self.chua_xep = _o_chua_xep()
		self.assertTrue(self.chua_xep, f"kho {KHO} phải có ô Chưa xếp vị trí")
		_nap(self.chua_xep, VAT_TU, LO, 30)
		_nap(O_A, VAT_TU, LO, 8)
		_nap(self.chua_xep, VAT_TU_KHONG_LO, None, 5)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point=DIEM_TEST)

	# ------------------------------------------------------------- quét

	def test_quet_lo_ra_mat_hang_nguon_va_mac_dinh_lay_tu_o_chua_xep(self):
		kq = quet_de_xep(KHO, LO)

		self.assertEqual(kq["loai"], "lo")
		self.assertEqual((kq["vat_tu"], kq["so_lo"]), (VAT_TU, LO))
		self.assertEqual(kq["ten_hang"], f"Hàng thử {VAT_TU}")
		self.assertEqual(str(kq["hsd"]), "2028-05-01")
		nguon = {d["o"]: d for d in kq["nguon"]}
		self.assertEqual(float(nguon[self.chua_xep]["con_xep_duoc"]), 30.0)
		self.assertTrue(nguon[self.chua_xep]["la_o_chua_xep"])
		self.assertEqual(float(nguon[O_A]["con_xep_duoc"]), 8.0)
		self.assertFalse(nguon[O_A]["la_o_chua_xep"])
		# Ô Chưa xếp còn hàng → đó là nguồn mặc định, dù lô còn nằm ở ô khác.
		self.assertEqual(kq["tu_o_mac_dinh"], self.chua_xep)
		self.assertIn("goi_y", kq)

	def test_quet_tem_o_ra_loai_o(self):
		kq = quet_de_xep(KHO, O_B)
		self.assertEqual((kq["loai"], kq["ma_o"]), ("o", O_B))

	def test_quet_ma_vat_tu_co_lo_bao_phai_quet_tem_lo(self):
		"""Mặt hàng có lô mà quét mã hàng thì không biết xếp lô nào — không đoán."""
		kq = quet_de_xep(KHO, VAT_TU)
		self.assertEqual(kq["loai"], "can_quet_lo")
		self.assertEqual(kq["vat_tu"], VAT_TU)

	def test_quet_ma_vat_tu_khong_lo_ra_dong_khong_lo(self):
		"""`Location Balance.so_lo` của hàng không lô là CHUỖI RỖNG — phải về `None`,
		nếu không K10 ("không quản lý lô, phải bỏ trống Số lô") chặn dòng."""
		kq = quet_de_xep(KHO, VAT_TU_KHONG_LO)
		self.assertEqual(kq["loai"], "lo")
		self.assertIsNone(kq["so_lo"])
		self.assertEqual(kq["tu_o_mac_dinh"], self.chua_xep)

	def test_quet_ma_la_khong_no(self):
		self.assertEqual(quet_de_xep(KHO, "9P-KHONG-CO-GI-CA")["loai"], None)
		self.assertEqual(quet_de_xep(KHO, "")["loai"], None)

	# ------------------------------------------------------ dồn dòng

	def test_hai_dong_len_cung_mot_phieu_nhap_va_mo_lai_thay_phieu_do(self):
		p1 = them_dong_xep(KHO, VAT_TU, LO, self.chua_xep, O_B, 10)
		p2 = them_dong_xep(KHO, VAT_TU_KHONG_LO, None, self.chua_xep, O_C, 5)

		self.assertEqual(p1["name"], p2["name"])
		self.assertEqual(frappe.db.get_value("Location Transfer", p2["name"], "docstatus"), 0)
		self.assertEqual(len(p2["dong"]), 2)

		mo_lai = phieu_xep_dang_lam(KHO)
		self.assertEqual(mo_lai["kho"], KHO)
		self.assertEqual(mo_lai["phieu"]["name"], p2["name"])
		self.assertEqual(
			[(d["vat_tu"], d["den_o"], float(d["so_luong"])) for d in mo_lai["phieu"]["dong"]],
			[(VAT_TU, O_B, 10.0), (VAT_TU_KHONG_LO, O_C, 5.0)],
		)

	def test_cung_lo_cung_o_dich_thi_cong_don_mot_dong(self):
		them_dong_xep(KHO, VAT_TU, LO, self.chua_xep, O_B, 10)
		p = them_dong_xep(KHO, VAT_TU, LO, self.chua_xep, O_B, 4)
		self.assertEqual(len(p["dong"]), 1)
		self.assertEqual(float(p["dong"][0]["so_luong"]), 14.0)

	def test_con_xep_duoc_tru_dong_da_len_phieu_nhap(self):
		them_dong_xep(KHO, VAT_TU, LO, self.chua_xep, O_B, 25)
		nguon = {d["o"]: d for d in quet_de_xep(KHO, LO)["nguon"]}
		self.assertEqual(float(nguon[self.chua_xep]["con_xep_duoc"]), 5.0)

	def test_xep_qua_so_con_lai_bi_chan_ngay_luc_them(self):
		them_dong_xep(KHO, VAT_TU, LO, self.chua_xep, O_B, 25)
		with self.assertRaisesRegex(frappe.ValidationError, "chỉ còn"):
			them_dong_xep(KHO, VAT_TU, LO, self.chua_xep, O_C, 6)
		# Dòng bị chặn không được lọt vào phiếu.
		self.assertEqual(len(phieu_xep_dang_lam(KHO)["phieu"]["dong"]), 1)

	def test_phep_kiem_dong_cua_phieu_van_chay(self):
		"""Nút nhóm không chứa hàng — câu báo là của `LocationTransfer._kiem_mot_dong`."""
		with self.assertRaisesRegex(frappe.ValidationError, "nút nhóm"):
			them_dong_xep(KHO, VAT_TU, LO, self.chua_xep, "9P01", 1)
		self.assertIsNone(phieu_xep_dang_lam(KHO)["phieu"])

	def test_phieu_nhap_la_cua_tung_nguoi(self):
		p = them_dong_xep(KHO, VAT_TU, LO, self.chua_xep, O_B, 3)

		if not frappe.db.exists("User", NGUOI_KHAC):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": NGUOI_KHAC,
					"first_name": "Xep",
					"send_welcome_email": 0,
					"roles": [{"role": "Stock User"}],
				}
			).insert(ignore_permissions=True)
		frappe.set_user(NGUOI_KHAC)

		self.assertIsNone(phieu_xep_dang_lam(KHO)["phieu"])
		p_khac = them_dong_xep(KHO, VAT_TU, LO, self.chua_xep, O_C, 2)
		self.assertNotEqual(p_khac["name"], p["name"])

	# --------------------------------------------------------- xoá dòng

	def test_xoa_dong(self):
		them_dong_xep(KHO, VAT_TU, LO, self.chua_xep, O_B, 3)
		p = them_dong_xep(KHO, VAT_TU_KHONG_LO, None, self.chua_xep, O_C, 2)
		con = xoa_dong_xep(p["name"], p["dong"][0]["name"])
		self.assertEqual([d["vat_tu"] for d in con["dong"]], [VAT_TU_KHONG_LO])

	def test_xoa_dong_cuoi_thi_bo_luon_phieu_nhap(self):
		"""Phiếu phải có ít nhất một dòng, và Stock User không có quyền xoá phiếu —
		nên dòng cuối đi thì phiếu nháp rỗng của CHÍNH người đó bị gỡ luôn,
		không để phiếu rác chỉ quản lý mới dọn được."""
		p = them_dong_xep(KHO, VAT_TU, LO, self.chua_xep, O_B, 3)
		self.assertIsNone(xoa_dong_xep(p["name"], p["dong"][0]["name"]))
		self.assertFalse(frappe.db.exists("Location Transfer", p["name"]))

	# ------------------------------------------------------------ duyệt

	def test_duyet_ghi_so_va_doi_ton_theo_o(self):
		them_dong_xep(KHO, VAT_TU, LO, self.chua_xep, O_B, 10)
		p = them_dong_xep(KHO, VAT_TU_KHONG_LO, None, self.chua_xep, O_C, 5)

		kq = duyet_phieu_xep(p["name"])

		self.assertEqual(kq["name"], p["name"])
		self.assertEqual(frappe.db.get_value("Location Transfer", p["name"], "docstatus"), 1)
		self.assertEqual(so.ton_o(self.chua_xep, VAT_TU, LO), 20.0)
		self.assertEqual(so.ton_o(O_B, VAT_TU, LO), 10.0)
		self.assertEqual(so.ton_o(O_C, VAT_TU_KHONG_LO, None), 5.0)
		self.assertIsNone(phieu_xep_dang_lam(KHO)["phieu"], "duyệt xong thì không còn phiếu đang làm")

	def test_duyet_hong_thi_phieu_nhap_con_nguyen(self):
		"""Ô nguồn bị rút bớt SAU khi dòng đã lên phiếu (người khác chuyển đi) —
		duyệt phải báo lỗi và phiếu nháp cùng các dòng còn nguyên để sửa."""
		p = them_dong_xep(KHO, VAT_TU, LO, O_A, O_B, 8)
		_nap(O_A, VAT_TU, LO, -5)

		with self.assertRaisesRegex(frappe.ValidationError, "không đủ hàng"):
			duyet_phieu_xep(p["name"])

		self.assertEqual(frappe.db.get_value("Location Transfer", p["name"], "docstatus"), 0)
		self.assertEqual(len(phieu_xep_dang_lam(KHO)["phieu"]["dong"]), 1)

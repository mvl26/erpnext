"""Luồng nhập kho nối liền: khai lô → duyệt phiếu nhập → xếp lên kệ (23/09/2026).

Hai thứ được khoá ở đây:

- `luong_nhap.tien_do_nhap_kho`: phiếu đang đứng ở bước nào. Thanh tiến trình và
  các nút trên form đọc CHÍNH hàm này, nên một trạng thái sai là thủ kho được
  chỉ sang bước không làm được.
- Tab **Connections** của bốn doctype trong luồng. Connections hỏng theo kiểu
  KHÔNG ném lỗi (tab vẫn dựng, chỉ là trống), đúng lớp lỗi mà `test_giao_dien.py`
  nói tới — nên phải đếm bằng chính `get_open_count` mà giao diện gọi.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import nowdate

from erpnext.warehouse_operations.tests.kho_thu import dam_bao_kho_khong_vi_tri
from erpnext.warehouse_operations.tests.test_hook_nhap import _tao_item
from erpnext.warehouse_operations.tests.test_lay_hang import CTY, KHO, O_GAN, _o, bo_kiem_o_tem
from erpnext.warehouse_operations.tests.test_lo_ncc import _ncc_thu

DIEM_TEST = "test_luong_nhap"
ITEM = "9N-VT-LUONG-NHAP"
LO = "9N-LO-01"
O_NHAN = "9N01010101"


def _phieu_nhap(qty=10, kho=KHO):
	"""Phiếu nhập CÒN NHÁP."""
	pr = frappe.get_doc(
		{
			"doctype": "Purchase Receipt",
			"company": CTY,
			"supplier": _ncc_thu(),
			"items": [{"item_code": ITEM, "qty": qty, "warehouse": kho, "rate": 1000}],
		}
	)
	pr.insert(ignore_permissions=True)
	return pr


def _khai_lo(pr, so_lo=LO, qty=10):
	"""Phiếu nhập lô đã DUYỆT cho dòng đầu của `pr` — bước "Nhập lô & in nhãn"."""
	d = pr.items[0]
	be = frappe.get_doc(
		{
			"doctype": "Batch Entry",
			"phieu_nhap": pr.name,
			"items": [
				{
					"dong_phieu_nhap": d.name,
					"vat_tu": d.item_code,
					"kho": d.warehouse,
					"so_luong": qty,
					"so_lo": so_lo,
					"hsd": "2030-01-31",
				}
			],
		}
	)
	be.insert(ignore_permissions=True)
	be.submit()
	return be


def _xep_len_ke(so_luong, o=O_NHAN, so_lo=LO):
	"""Phiếu xếp từ ô "Chưa xếp vị trí" sang ô thật — bước "Xếp hàng lên kệ"."""
	chua_xep = frappe.db.get_value("Storage Location", {"kho": KHO, "la_o_chua_xep": 1})
	lt = frappe.get_doc(
		{
			"doctype": "Location Transfer",
			"kho": KHO,
			"ngay": nowdate(),
			"items": [
				{"vat_tu": ITEM, "so_lo": so_lo, "tu_o": chua_xep, "den_o": o, "so_luong": so_luong}
			],
		}
	)
	with bo_kiem_o_tem():
		lt.insert(ignore_permissions=True)
		lt.submit()
	return lt


class _Nen(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.savepoint(DIEM_TEST)
		_tao_item(ITEM, co_lo=1)
		_o(O_GAN, thu_tu=1)
		_o(O_NHAN, thu_tu=2)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point=DIEM_TEST)

	def _tien_do(self, pr):
		from erpnext.warehouse_operations.vitri.luong_nhap import tien_do_nhap_kho

		return tien_do_nhap_kho(pr.name)


class TestTienDoNhapKho(_Nen):
	def test_phieu_nhap_chua_khai_lo(self):
		pr = _phieu_nhap()
		t = self._tien_do(pr)
		self.assertEqual(t["trang_thai"], "can_khai_lo")
		self.assertEqual((t["dong_can_khai"], t["kho_quan_ly"]), (1, [KHO]))
		self.assertEqual(t["phieu_nhap_lo"], [])

	def test_khai_lo_xong_thi_cho_duyet(self):
		pr = _phieu_nhap()
		be = _khai_lo(pr)
		t = self._tien_do(pr)
		self.assertEqual(t["trang_thai"], "khai_du_cho_duyet")
		self.assertEqual((t["dong_can_khai"], t["phieu_nhap_lo"]), (0, [be.name]))
		self.assertEqual(t["tong_chua_xep"], 0)

	def test_duyet_xong_thi_cho_xep_dung_so_luong(self):
		pr = _phieu_nhap(10)
		_khai_lo(pr, qty=10)
		pr.reload()
		pr.submit()
		t = self._tien_do(pr)
		self.assertEqual(t["trang_thai"], "cho_xep")
		self.assertEqual(t["tong_chua_xep"], 10)
		self.assertEqual(t["chua_xep_theo_kho"], {KHO: 10})
		self.assertEqual([(d["vat_tu"], d["so_lo"]) for d in t["chua_xep"]], [(ITEM, LO)])

	def test_xep_het_len_ke_thi_xong_luong(self):
		pr = _phieu_nhap(10)
		_khai_lo(pr, qty=10)
		pr.reload()
		pr.submit()
		_xep_len_ke(10)
		t = self._tien_do(pr)
		self.assertEqual(t["trang_thai"], "da_xep")
		self.assertEqual((t["tong_chua_xep"], t["chua_xep"]), (0, []))

	def test_xep_mot_phan_thi_van_cho_xep(self):
		pr = _phieu_nhap(10)
		_khai_lo(pr, qty=10)
		pr.reload()
		pr.submit()
		_xep_len_ke(4)
		self.assertEqual(self._tien_do(pr)["tong_chua_xep"], 6)

	def test_lo_cua_phieu_khac_khong_tinh_vao_phieu_nay(self):
		"""Ô chưa xếp là ô dùng chung; chỉ đếm (kho, mặt hàng, lô) CÓ TRÊN phiếu."""
		pr = _phieu_nhap(10)
		_khai_lo(pr, qty=10)
		pr.reload()
		pr.submit()
		pr2 = _phieu_nhap(7)
		_khai_lo(pr2, so_lo="9N-LO-02", qty=7)
		pr2.reload()
		pr2.submit()
		self.assertEqual(self._tien_do(pr)["tong_chua_xep"], 10)
		self.assertEqual(self._tien_do(pr2)["tong_chua_xep"], 7)

	def test_kho_khong_quan_ly_vi_tri_thi_khong_ap_dung(self):
		kho = dam_bao_kho_khong_vi_tri()
		pr = _phieu_nhap(5, kho=kho)
		t = self._tien_do(pr)
		self.assertEqual(t["trang_thai"], "khong_ap_dung")
		self.assertEqual(t["kho_quan_ly"], [])

	def test_phieu_huy(self):
		pr = _phieu_nhap(10)
		_khai_lo(pr, qty=10)
		pr.reload()
		pr.submit()
		pr.cancel()
		self.assertEqual(self._tien_do(pr)["trang_thai"], "da_huy")

	def test_khong_quyen_doc_bi_chan(self):
		pr = _phieu_nhap()
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			self._tien_do(pr)


class TestConnectionsLuongNhap(_Nen):
	"""Đếm bằng chính `get_open_count` mà tab Connections gọi."""

	def _dem(self, doctype, ten):
		from frappe.desk.notifications import get_open_count

		kq = get_open_count(doctype, ten)["count"]
		dem = {x["doctype"]: x["count"] for x in kq.get("external_links_found", [])}
		dem.update({x["doctype"]: x["count"] for x in kq.get("internal_links_found", [])})
		return dem

	def test_phieu_nhap_thay_phieu_nhap_lo_va_so_vi_tri(self):
		pr = _phieu_nhap(10)
		_khai_lo(pr, qty=10)
		pr.reload()
		pr.submit()
		dem = self._dem("Purchase Receipt", pr.name)
		self.assertEqual(dem.get("Batch Entry"), 1)
		self.assertEqual(dem.get("Location Ledger Entry"), 1)

	def test_phieu_nhap_lo_thay_phieu_nhap_va_lo_da_tao(self):
		pr = _phieu_nhap(10)
		be = _khai_lo(pr, qty=10)
		dem = self._dem("Batch Entry", be.name)
		self.assertEqual(dem.get("Purchase Receipt"), 1)
		self.assertEqual(dem.get("Batch"), 1)

	def test_phieu_xep_thay_so_vi_tri(self):
		pr = _phieu_nhap(10)
		_khai_lo(pr, qty=10)
		pr.reload()
		pr.submit()
		lt = _xep_len_ke(10)
		self.assertEqual(self._dem("Location Transfer", lt.name).get("Location Ledger Entry"), 2)

	def test_lo_thay_so_vi_tri(self):
		pr = _phieu_nhap(10)
		_khai_lo(pr, qty=10)
		pr.reload()
		pr.submit()
		self.assertEqual(self._dem("Batch", LO).get("Location Ledger Entry"), 1)


class TestPhieuNhapLoCuaLo(_Nen):
	"""Đường đi NGƯỢC: từ lô về phiếu khai ra nó (nút trên form lô)."""

	def _tim(self, so_lo):
		from erpnext.warehouse_operations.vitri.luong_nhap import phieu_nhap_lo_cua_lo

		return phieu_nhap_lo_cua_lo(so_lo)

	def test_tra_ve_phieu_da_duyet(self):
		pr = _phieu_nhap(10)
		be = _khai_lo(pr, qty=10)
		self.assertEqual(self._tim(LO), [be.name])

	def test_lo_khong_qua_phieu_nhap_lo_thi_rong(self):
		frappe.get_doc({"doctype": "Batch", "batch_id": "9N-LO-99", "item": ITEM}).insert(
			ignore_permissions=True
		)
		self.assertEqual(self._tim("9N-LO-99"), [])

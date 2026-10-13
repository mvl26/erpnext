"""CRITICAL 3 (review điều phối, sau khi 147/147 bài "xong") — hai loại
chứng từ của chính yêu cầu chủ dự án chưa từng chạy qua hook bằng chứng từ
thật.

Trước bài này: chỉ `Stock Entry` (Material Receipt/Issue) và `Stock
Reconciliation` có test tích hợp bằng chứng từ THẬT (`test_hook_nhap.py`,
`test_huy_chung_tu.py`, `test_doi_soat.py`). ZERO test cho `Delivery Note`
và `Purchase Receipt` — trong khi yêu cầu gốc của chủ dự án ("khi giao hàng
biết lấy từ kho và vị trí nào", spec §6.2) đi qua ĐÚNG `Delivery Note`.

Mỗi doctype: hai đường (ghi sổ và huỷ), khẳng định bất biến §3 bằng NGUỒN
ĐỘC LẬP (`Bin`) sau mỗi thao tác, và với đường huỷ khẳng định hàng về ĐÚNG Ô
CŨ — không phải CHUA-XEP.

Bài học đã ghi hai lần trong repo này (Minor 1 `TestHuyPhieuNhap`, Minor 2
`TestHuyPhieuXuat` ở `test_huy_chung_tu.py`): "hàng về đúng ô cũ" KHÔNG có
sức phân biệt nếu CHUA-XEP là ô DUY NHẤT giữ mặt hàng đó — FEFO/CHUA-XEP
tình cờ trùng "ô cũ" nên bài xanh dù logic hỏng. Cả hai bộ test dưới đây vì
vậy đều seed một Ô THỨ HAI có hàng thật của CÙNG mặt hàng trước khi thao
tác chính, đúng khuôn `_seed_o`/`_o` đã dùng ở `test_huy_chung_tu.py`.

Supplier/Customer/Company dùng trên site `erptest.local` (đã kiểm tồn tại
trước khi viết bài — xem báo cáo): Supplier "hoang nam", Customer "Bệnh
viện DEMO Miyano E2E", Company "Miyano Việt Nam" (khớp company của
`Kho Miyano - MYN`).
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from erpnext.warehouse_operations.tests.test_hook_nhap import _bat_kho_tho, _nhap_kho, _tao_item, _tat_kho_tho
from erpnext.warehouse_operations.tests.test_huy_chung_tu import _o, _seed_o
from erpnext.warehouse_operations.tests.test_lay_hang import bo_bat_buoc_lay_hang
from erpnext.warehouse_operations.vitri import kho as vk
from erpnext.warehouse_operations.vitri import so

KHO = "Kho Miyano - MYN"
COMPANY = "Miyano Việt Nam"
SUPPLIER = "hoang nam"
CUSTOMER = "Bệnh viện DEMO Miyano E2E"


def _nhap_pr(item, qty, kho=KHO, rate=1000):
	pr = frappe.get_doc(
		{
			"doctype": "Purchase Receipt",
			"supplier": SUPPLIER,
			"company": COMPANY,
			"items": [{"item_code": item, "qty": qty, "rate": rate, "warehouse": kho}],
		}
	)
	pr.insert(ignore_permissions=True)
	pr.submit()
	return pr


def _giao_hang(item, qty, kho=KHO, rate=2000):
	dn = frappe.get_doc(
		{
			"doctype": "Delivery Note",
			"customer": CUSTOMER,
			"company": COMPANY,
			"items": [{"item_code": item, "qty": qty, "rate": rate, "warehouse": kho}],
		}
	)
	dn.insert(ignore_permissions=True)
	dn.submit()
	return dn


def _bin_qty(item, kho=KHO):
	return flt(frappe.db.get_value("Bin", {"item_code": item, "warehouse": kho}, "actual_qty"))


class TestPurchaseReceiptTichHop(FrappeTestCase):
	def setUp(self):
		_bat_kho_tho(KHO)
		self.o_khac = _o("9Z24010101", thu_tu=-5)

	def tearDown(self):
		_tat_kho_tho(KHO)

	def test_pr_submit_vao_chua_xep_va_khop_bin(self):
		# Mặt hàng RIÊNG cho bài này — lớp rollback theo LỚP (không theo
		# từng bài), dùng chung item với bài huỷ sẽ cộng dồn/để lại dữ liệu
		# bẩn tuỳ thứ tự chạy alphabet.
		item = _tao_item("_Test WMS PR TH Submit")
		pr = _nhap_pr(item, 10)
		o_cx = vk.o_chua_xep(KHO)

		self.assertEqual(so.ton_o(o_cx, item, None), 10, "PR không khai vị trí phải vào CHUA-XEP")
		dong = frappe.get_all(
			"Location Ledger Entry",
			filters={"chung_tu": pr.name},
			fields=["chung_tu_type", "so_luong"],
		)
		self.assertEqual(len(dong), 1)
		self.assertEqual(dong[0].chung_tu_type, "Purchase Receipt")
		self.assertEqual(dong[0].so_luong, 10)

		self.assertEqual(_bin_qty(item), 10, "tiền đề: nguồn độc lập (Bin) đã ghi 10")
		self.assertEqual(so.tong_ton_vi_tri(KHO, item, None), 10, "bất biến §3 sau khi submit PR")

	def test_pr_cancel_tra_ve_chua_xep_khong_dung_vao_o_khac(self):
		"""Seed một Ô KHÁC có hàng CÙNG mặt hàng từ một chứng từ KHÁC trước —
		nếu huỷ PR không đi qua dao_theo_o_goc (rơi xuống đường thường: huỷ
		nhập => delta âm => FEFO), FEFO sẽ ưu tiên rút từ o_khac (thu_tu nhỏ
		hơn CHUA-XEP mặc định 0) — khoá bằng cách khẳng định o_khac KHÔNG bị
		đụng sau khi huỷ PR."""
		item = _tao_item("_Test WMS PR TH Cancel")
		_nhap_pr(item, 4)
		_seed_o(item, self.o_khac, 4)
		self.assertEqual(so.ton_o(self.o_khac, item, None), 4, "tiền đề: ô khác đã có sẵn hàng")
		o_cx = vk.o_chua_xep(KHO)
		self.assertEqual(so.ton_o(o_cx, item, None), 0, "tiền đề: CHUA-XEP về 0 sau khi seed")

		pr = _nhap_pr(item, 8)
		self.assertEqual(so.ton_o(o_cx, item, None), 8)

		pr.cancel()

		self.assertEqual(so.ton_o(o_cx, item, None), 0, "PR phải quay về đúng ô đã nhập (CHUA-XEP)")
		self.assertEqual(
			so.ton_o(self.o_khac, item, None),
			4,
			"ô khác (thu_tu nhỏ hơn CHUA-XEP) KHÔNG được bị FEFO rút nhầm vào",
		)
		self.assertEqual(_bin_qty(item), 4, "tiền đề: ERPNext đã đưa tồn kho về 4 sau huỷ PR")
		self.assertEqual(so.tong_ton_vi_tri(KHO, item, None), 4, "bất biến §3 sau khi huỷ PR")


class TestDeliveryNoteTichHop(FrappeTestCase):
	"""Yêu cầu gốc của chủ dự án (spec §6.2): "khi giao hàng biết lấy từ kho
	và vị trí nào" — đi qua ĐÚNG Delivery Note."""

	def setUp(self):
		# Bài về đường FEFO tự trừ khi duyệt thẳng — đường mà luật bắt buộc lấy hàng
		# (22/09/2026) đóng lại với nghiệp vụ thật; giữ nó chạy được cho test.
		self.enterContext(bo_bat_buoc_lay_hang())
		_bat_kho_tho(KHO)
		self.o_gan = _o("9Z23010101", thu_tu=1)

	def tearDown(self):
		_tat_kho_tho(KHO)

	def _seed(self, item, qty):
		"""Nhập thật qua Stock Entry (có định giá) rồi chuyển sổ VỊ TRÍ
		(không đụng ERPNext Bin) sang o_gan — cùng khuôn `_seed_o_gan` ở
		`test_huy_chung_tu.py`."""
		_nhap_kho(item, qty)
		_seed_o(item, self.o_gan, qty)

	def test_dn_submit_lay_tu_o_gan_khong_dung_chua_xep_va_khop_bin(self):
		# Mặt hàng RIÊNG cho bài này — lớp rollback theo LỚP, xem lý do ở
		# TestPurchaseReceiptTichHop.
		item = _tao_item("_Test WMS DN TH Submit")
		self._seed(item, 10)
		o_cx = vk.o_chua_xep(KHO)
		self.assertEqual(so.ton_o(self.o_gan, item, None), 10, "tiền đề")
		self.assertEqual(so.ton_o(o_cx, item, None), 0, "tiền đề")

		dn = _giao_hang(item, 4)

		self.assertEqual(so.ton_o(self.o_gan, item, None), 6, "DN không khai vị trí phải tự FEFO chọn o_gan")
		self.assertEqual(so.ton_o(o_cx, item, None), 0, "CHUA-XEP không được bị đụng — không có hàng ở đó")
		dong = frappe.get_all(
			"Location Ledger Entry",
			filters={"chung_tu": dn.name},
			fields=["chung_tu_type", "o", "so_luong"],
		)
		self.assertEqual(len(dong), 1)
		self.assertEqual(dong[0].chung_tu_type, "Delivery Note")
		self.assertEqual(dong[0].o, self.o_gan)
		self.assertEqual(dong[0].so_luong, -4)

		self.assertEqual(_bin_qty(item), 6, "tiền đề: nguồn độc lập (Bin) đã trừ còn 6")
		self.assertEqual(so.tong_ton_vi_tri(KHO, item, None), 6, "bất biến §3 sau khi submit DN")

	def test_dn_cancel_tra_hang_ve_dung_o_gan_khong_roi_xuong_chua_xep(self):
		item = _tao_item("_Test WMS DN TH Cancel")
		self._seed(item, 10)
		dn = _giao_hang(item, 4)
		self.assertEqual(so.ton_o(self.o_gan, item, None), 6)

		dn.cancel()

		self.assertEqual(
			so.ton_o(self.o_gan, item, None),
			10,
			"hàng phải quay về ĐÚNG o_gan (nơi đã lấy), không phải một ô khác",
		)
		self.assertEqual(
			so.ton_o(vk.o_chua_xep(KHO), item, None),
			0,
			"KHÔNG được rơi xuống CHUA-XEP — đó là nơi hàng sẽ tới nếu huỷ DN không đi "
			"qua dao_theo_o_goc (chạy lại FEFO/CHUA-XEP thay vì trả đúng ô gốc)",
		)
		self.assertEqual(_bin_qty(item), 10, "tiền đề: ERPNext đã đưa tồn kho về 10 sau huỷ DN")
		self.assertEqual(so.tong_ton_vi_tri(KHO, item, None), 10, "bất biến §3 sau khi huỷ DN")

"""Xem trước chuyển đổi — bắt buộc trước khi bật.

Xem trước KHÔNG ĐƯỢC GHI GÌ. Đây là điều duy nhất bài test này khoá, và nó
đáng một bài riêng: một hàm "xem trước" lỡ ghi dữ liệu là thứ không ai nghi
ngờ cho tới khi đã muộn.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.vi_tri_kho.tests.test_hook_nhap import _nhap_kho, _tao_item
from erpnext.vi_tri_kho.vitri.bat_kho import xem_truoc
from erpnext.vi_tri_kho.vitri.doi_soat import doi_soat_kho

KHO = "Kho Miyano - MYN"

# Kho RIÊNG của nhóm bài này, tự dựng, chưa chuyển đổi bao giờ.
#
# SỬA 10/09/2026: cả nhóm trước đây mượn `Kho Miyano - MYN` làm "kho chưa
# chuyển đổi" và mượn luôn tồn có sẵn trên site làm dữ liệu. Khi chủ dự án
# bật kho thật, sáu bài đổ cùng lúc — `xem_truoc` ném "kho đã bật rồi".
# Đó không phải hồi quy sản phẩm mà là món nợ đã ghi ở BAN-GIAO mục 3
# ("toàn suite ràng vào dữ liệu của erptest.local") đến hạn. Kho riêng cắt
# hẳn phụ thuộc đó: bài không còn quan tâm site đang ở trạng thái nào.
KHO_THU = "_Test Kho XemTruoc - MYN"


def _kho_thu():
	if not frappe.db.exists("Warehouse", KHO_THU):
		frappe.get_doc(
			{
				"doctype": "Warehouse",
				"warehouse_name": "_Test Kho XemTruoc",
				"company": "Miyano Việt Nam",
				"is_group": 0,
			}
		).insert(ignore_permissions=True)
	return KHO_THU


class TestXemTruoc(FrappeTestCase):
	def setUp(self):
		# Mỗi bài tự dựng điều kiện nó cần. Trước đây `test_canh_bao_hang_khong_lo`
		# xanh nhờ `Kho Miyano` TÌNH CỜ có hàng không lô — cảnh báo nổ vì dữ liệu
		# người khác để lại, không phải vì bài dựng ra nó.
		_kho_thu()

	def test_khong_ghi_gi(self):
		truoc_o = frappe.db.count("Storage Location")
		truoc_so = frappe.db.count("Location Ledger Entry")
		truoc_ton = frappe.db.count("Location Balance")
		co_truoc = frappe.db.get_value("Warehouse", KHO_THU, "custom_quan_ly_vi_tri")

		xem_truoc(KHO_THU)

		self.assertEqual(frappe.db.count("Storage Location"), truoc_o)
		self.assertEqual(frappe.db.count("Location Ledger Entry"), truoc_so)
		self.assertEqual(frappe.db.count("Location Balance"), truoc_ton)
		self.assertEqual(frappe.db.get_value("Warehouse", KHO_THU, "custom_quan_ly_vi_tri"), co_truoc)

	def test_dem_dung_so_mat_hang_va_lo(self):
		_nhap_kho(_tao_item("_Test XemTruoc Dem"), 9, kho=KHO_THU)

		kq = xem_truoc(KHO_THU)
		self.assertGreater(kq["so_dong"], 0, "vừa nhập hàng vào kho thử nên phải có dòng")
		self.assertEqual(kq["so_dong"], len(kq["dong"]))
		self.assertEqual(kq["so_mat_hang"], len({d["vat_tu"] for d in kq["dong"]}))

	def test_kho_tong_bi_chan(self):
		with self.assertRaises(frappe.ValidationError) as ctx:
			xem_truoc("All Warehouses - MYN")
		self.assertIn("kho tổng", str(ctx.exception).lower())

	def test_kho_da_bat_thi_bao(self):
		frappe.db.set_value("Warehouse", "Stores - MYN", "custom_quan_ly_vi_tri", 1)
		try:
			with self.assertRaises(frappe.ValidationError):
				xem_truoc("Stores - MYN")
		finally:
			frappe.db.set_value("Warehouse", "Stores - MYN", "custom_quan_ly_vi_tri", 0)

	def test_so_luong_dong_khop_ton_that_khong_qua_ton_kho_theo_lo(self):
		"""Bài không tự chứng minh mình: vế đối chiếu KHÔNG lấy từ chính
		`xem_truoc`, mà nhập một Stock Entry thật rồi đọc lại qua `Bin`.

		SỬA MINOR (vòng review 1): docstring bản trước nói vế đối chiếu này
		"đường hoàn toàn khác đường mà xem_truoc dùng" — KHÔNG đúng.
		`ton_kho_theo_lo` (Task 10) chính là hàm đọc thẳng `Bin.actual_qty`
		làm tổng có thẩm quyền cấp mặt hàng, nên so lại bằng `Bin` không
		độc lập ở CẤP TỔNG — cả hai cùng một nguồn số liệu gốc. Bài này chỉ
		khoá phần `xem_truoc` KIỂM SOÁT ĐƯỢC: bọc dict→list, lọc ngưỡng
		gần-0, gán `so_lo=None` cho hàng không lô — không khoá "Bin có đúng
		37 hay không" (đó là ERPNext tự tính khi submit Stock Entry, không
		phải logic của task này).

		Dùng mặt hàng riêng (lớp rollback theo LỚP, không theo bài — xem
		ghi chú ở `test_doi_soat.py`).
		"""
		item = _tao_item("_Test XemTruoc SoLuong")
		_nhap_kho(item, 37, kho=KHO_THU)

		kq = xem_truoc(KHO_THU)
		dong_cua_item = [d for d in kq["dong"] if d["vat_tu"] == item]
		self.assertEqual(len(dong_cua_item), 1)
		self.assertEqual(dong_cua_item[0]["so_luong"], 37)
		self.assertIsNone(dong_cua_item[0]["so_lo"], "item không quản lý lô")

		ton_bin = frappe.db.get_value("Bin", {"item_code": item, "warehouse": KHO_THU}, "actual_qty")
		self.assertEqual(ton_bin, 37)

	def test_khop_voi_doi_soat_kho_chua_chuyen_doi(self):
		"""Trước khi bật, Location Balance rỗng nên `doi_soat_kho` coi TOÀN
		BỘ tồn kho là lệch — `so_dong_lech` của nó phải khớp `so_dong` của
		`xem_truoc`, vì cả hai đọc cùng một nguồn (`ton_kho_theo_lo`).

		Đây là điểm khoá chính: nếu `_ton_hien_co` từng chép lại SQL riêng
		(như brief gốc) thay vì dùng lại hàm của Task 10, hai vế này có thể
		lệch nhau mà không bài nào ở trên bắt được — cả hai đều chỉ đọc từ
		`xem_truoc`.
		"""
		_nhap_kho(_tao_item("_Test XemTruoc DoiSoat"), 6, kho=KHO_THU)
		self.assertEqual(
			frappe.db.count("Location Balance", {"kho": KHO_THU}),
			0,
			"kho thử chưa chuyển đổi bao giờ — nếu số này khác 0 thì bài không "
			"còn đúng tiền đề và cần xem lại.",
		)
		kq = xem_truoc(KHO_THU)
		ds = doi_soat_kho(KHO_THU)
		self.assertEqual(kq["so_dong"], ds["so_dong_lech"])

	def test_website_user_bi_chan(self):
		"""VÒNG SỬA 1 (review điều phối, Critical/bảo mật): `xem_truoc` là
		RPC `@frappe.whitelist()` đầu tiên của module `vitri/`, ban đầu
		KHÔNG kiểm quyền — chỉ đòi đăng nhập. DocPerm trên doctype
		`Warehouse Location Setup` không chặn được RPC này. Site
		`erptest.local` có tài khoản `Website User` thật đang hoạt động
		(khách hàng cổng `miyano_portal`, ví dụ `bvminhduc@demo.miyano`) —
		thiếu kiểm quyền nghĩa là một tài khoản bệnh viện đọc được tồn theo
		lô của mọi kho nội bộ Miyano.
		"""
		self.assertTrue(
			frappe.db.exists("User", "bvminhduc@demo.miyano"),
			"Cần tài khoản Website User thật trên site để bài này có ý nghĩa.",
		)
		frappe.set_user("bvminhduc@demo.miyano")
		try:
			with self.assertRaises(frappe.PermissionError):
				xem_truoc(KHO)
		finally:
			frappe.set_user("Administrator")

	def test_canh_bao_hang_khong_lo(self):
		"""VÒNG SỬA 1: khối cảnh báo (`canh_bao`) trước đó không bài nào
		khoá — xoá cả khối trên giấy, không bài nào đỏ.
		"""
		item = _tao_item("_Test XemTruoc CanhBaoKhongLo")
		_nhap_kho(item, 5, kho=KHO_THU)

		kq = xem_truoc(KHO_THU)
		self.assertTrue(kq["canh_bao"], "phải có cảnh báo vì bài vừa nhập hàng KHÔNG lô vào kho thử")
		self.assertTrue(
			any("không quản lý lô" in c and "Chưa xếp vị trí" in c for c in kq["canh_bao"]),
			kq["canh_bao"],
		)

	def test_canh_bao_ton_am(self):
		"""VÒNG SỬA 1: cảnh báo tồn âm cũng không bài nào khoá trước đó.

		Dựng tồn âm bằng cách đặt thẳng `Bin.actual_qty` — KHÔNG qua một
		giao dịch Stock Entry thật, vì ERPNext mặc định chặn giao dịch tạo
		tồn âm (Stock Settings không bật `allow_negative_stock` trên site
		này). Tồn âm trong thực tế thường tới từ hiệu chỉnh dữ liệu quá
		khứ, không phải giao dịch bình thường — đặt thẳng Bin mô phỏng
		đúng lớp tình huống đó cho mặt hàng không lô (phần dư của
		`ton_kho_theo_lo` khi không có `Serial and Batch Entry` nào chia).
		"""
		item = _tao_item("_Test XemTruoc CanhBaoTonAm")
		if not frappe.db.exists("Bin", {"item_code": item, "warehouse": KHO_THU}):
			frappe.get_doc(
				{
					"doctype": "Bin",
					"item_code": item,
					"warehouse": KHO_THU,
					"actual_qty": 0,
				}
			).insert(ignore_permissions=True)
		frappe.db.set_value("Bin", {"item_code": item, "warehouse": KHO_THU}, "actual_qty", -5)

		kq = xem_truoc(KHO_THU)
		dong_cua_item = [d for d in kq["dong"] if d["vat_tu"] == item]
		self.assertEqual(dong_cua_item, [{"vat_tu": item, "so_lo": None, "so_luong": -5.0}])
		self.assertTrue(
			any("ÂM" in c for c in kq["canh_bao"]),
			kq["canh_bao"],
		)

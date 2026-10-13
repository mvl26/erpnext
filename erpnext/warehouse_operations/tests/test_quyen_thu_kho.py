"""Bảy hàm GHI của trang Lấy hàng PDA chạy dưới QUYỀN THỦ KHO THẬT.

VÌ SAO CÓ MODULE NÀY (lỗi thật, 24/09/2026 — chặn việc dùng thật): một thủ kho
có đúng bộ vai trò kho (`Stock User` + `Stock Manager`, đúng tập
`lay_hang.VAI_TRO_DUOC_LAY`) KHÔNG ghi được một lượt lấy nào. Mọi hàm ghi đều
`doc.save()` trên phiếu giao; `Delivery Note.validate` nạp lại thông tin khách
(`SellingController.set_missing_lead_customer_details`), dựng lại chuỗi địa chỉ
qua `render_address` → `Address.check_permission()` → `PermissionError` tiếng
Anh, giữa kho. `Address` chỉ cho vai trò `All` đọc kèm `if_owner = 1`, nên địa
chỉ do nhân viên bán hàng tạo thì thủ kho không đọc được.

VÌ SAO CẢ BỘ TEST KHÔNG BẮT ĐƯỢC — hai lỗ hổng, phải bịt CẢ HAI:

1. Mọi bài của `test_lay_hang*` chạy dưới `Administrator`.
2. Khách hàng thử của chúng (`Bệnh viện DEMO Miyano E2E`) KHÔNG có `Address`
   nào. `render_address(None)` trả về ngay, chưa kịp kiểm quyền — nên dù có
   đổi sang chạy dưới vai trò kho, chúng vẫn XANH mà không kiểm gì.

Vì vậy FIXTURE ĐỊA CHỈ ở đây là thứ chịu lực. Hai điều kiện bắt buộc của nó:

- Địa chỉ phải được tạo khi CÒN LÀ `Administrator`. Tạo sau khi `set_user` thì
  thủ kho thành `owner`, `if_owner = 1` cho đọc, và cả module xanh vô nghĩa.
- Phiếu giao phải TRỎ vào địa chỉ đó (`customer_address` +
  `shipping_address_name`), không chỉ tồn tại một `Address` lơ lửng.

`test_khong_doc_duoc_dia_chi_khach` là bài CANH GÁC cho chính fixture ấy: nếu
một ngày nào đó vai trò kho đọc được `Address`, bài đó đỏ và báo cho người sau
biết sáu bài còn lại đã hết ý nghĩa — chứ không âm thầm xanh.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt, nowdate

from erpnext.warehouse_operations.tests.test_lay_hang import (
	CTY,
	ITEM,
	KHACH,
	KHO,
	LO,
	O_GAN,
	O_XA,
	_chuyen_vao_o,
	_lo,
	_nhap_kho,
	_o,
	_vat_tu,
	bo_bat_buoc_lay_hang,
)
from erpnext.warehouse_operations.tests.test_the_pda import _nguoi

DIEM_TEST = "test_quyen_thu_kho"

# Tài khoản RIÊNG của module này. KHÔNG dùng lại `9p-thukho@miyano.test` của
# `test_the_pda`: module đó CẮT `Stock User`/`Stock Manager` khỏi tài khoản ấy
# trong một bài (test_the_pda.py:320), nên mượn nó là buộc hai module vào nhau
# theo thứ tự chạy — đúng loại phụ thuộc ngầm mà dự án này đã trả giá.
THU_KHO = "9q-thukho-quyen@miyano.test"
VAI_TRO_KHO = ["Stock User", "Stock Manager"]

DIA_CHI = "9Q Địa chỉ giao hàng thử quyền-Shipping"
LO_2 = "9Q-LO-QUYEN-02"


def _dia_chi_khach() -> str:
	"""`Address` của khách, GẮN VÀO phiếu giao — thứ làm bài test đo đúng lỗi.

	Chủ sở hữu là người đang chạy (`Administrator` trong `setUp`), KHÔNG phải
	thủ kho: đó chính là điều kiện làm `if_owner = 1` của DocPerm `All` không
	cứu được thủ kho.
	"""
	if not frappe.db.exists("Address", DIA_CHI):
		frappe.get_doc(
			{
				"doctype": "Address",
				"address_title": "9Q Địa chỉ giao hàng thử quyền",
				"address_type": "Shipping",
				"address_line1": "Số 9 phố Thử Quyền",
				"city": "Hà Nội",
				"country": "Vietnam",
				"links": [{"link_doctype": "Customer", "link_name": KHACH}],
			}
		).insert(ignore_permissions=True)
	return DIA_CHI


def _lo_thu_hai() -> str:
	if not frappe.db.exists("Batch", LO_2):
		frappe.get_doc(
			{"doctype": "Batch", "batch_id": LO_2, "item": ITEM, "expiry_date": "2029-06-30"}
		).insert(ignore_permissions=True)
	return LO_2


def _phieu_giao_co_dia_chi(so_luong: float, dia_chi: str):
	"""Phiếu giao NHÁP CÓ địa chỉ khách — `test_lay_hang._phieu_giao` không đặt
	địa chỉ, và chính chỗ trống đó là lý do 83 bài của nó không bắt được lỗi."""
	dn = frappe.get_doc(
		{
			"doctype": "Delivery Note",
			"company": CTY,
			"customer": KHACH,
			"customer_address": dia_chi,
			"shipping_address_name": dia_chi,
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
	return dn


class TestThuKhoGhiDuocLuotLay(FrappeTestCase):
	def setUp(self):
		# Bài về QUYỀN, không về luật bắt buộc lấy hàng + tem kiện (luật đó có
		# bộ riêng: `test_lay_hang_don_vi.TestChanDuyet`) — `hoan_tat` ở đây
		# phải đi lọt tới `doc.submit()` mới chạm được đường lỗi cần đo.
		self.enterContext(bo_bat_buoc_lay_hang())
		from erpnext.warehouse_operations.vitri.lay_hang import _khoa_chot_thieu

		frappe.set_user("Administrator")

		# TÀI KHOẢN DỰNG TRƯỚC SAVEPOINT — đúng chỗ `test_the_pda` đặt nó, và vì
		# một lý do: `User.insert()` của Frappe v15 tự `commit()` bên trong. Một
		# `commit()` xảy ra SAU `frappe.db.savepoint` sẽ ghi THẲNG xuống CSDL mọi
		# thứ đang nằm trong giao dịch — mặt hàng, lô, ô, phiếu nhập, phiếu xếp,
		# phiếu giao — lên `erptest.local` thật. Đặt trước savepoint thì thiệt hại
		# xấu nhất chỉ là một dòng `User` thừa.
		_nguoi(THU_KHO, VAI_TRO_KHO)
		# Bộ vai trò nằm trong Redis theo từng người dùng; không xoá thì
		# `frappe.get_roles()` có thể trả bộ CŨ và `_kiem_tra_quyen()` chặn vì
		# lý do KHÁC — bài sẽ đỏ đúng chỗ nhưng sai nguyên nhân.
		frappe.clear_cache(user=THU_KHO)

		frappe.db.savepoint(DIEM_TEST)
		_vat_tu()
		_lo()
		_lo_thu_hai()
		_o(O_GAN, thu_tu=1)
		_o(O_XA, thu_tu=2)
		_nhap_kho(30)
		_chuyen_vao_o([(O_GAN, 20), (O_XA, 10)])
		self.dia_chi = _dia_chi_khach()
		self.dn = _phieu_giao_co_dia_chi(12, self.dia_chi)
		self.dong = self.dn.items[0].name
		frappe.cache().delete_value(_khoa_chot_thieu(self.dn.name))

	def tearDown(self):
		from erpnext.warehouse_operations.vitri.lay_hang import _khoa_chot_thieu

		# TRẢ QUYỀN TRƯỚC MỌI THỨ KHÁC: `tearDown` vẫn chạy khi bài ném lỗi, và
		# một phiên còn kẹt ở thủ kho sẽ làm `rollback` cùng mọi bài SAU chạy
		# dưới nhầm người.
		frappe.set_user("Administrator")
		frappe.cache().delete_value(_khoa_chot_thieu(self.dn.name))
		frappe.db.rollback(save_point=DIEM_TEST)

	# --- Bài canh gác cho fixture -------------------------------------------

	def test_khong_doc_duoc_dia_chi_khach(self):
		"""Nếu bài này đỏ thì sáu bài dưới KHÔNG còn kiểm gì nữa — chúng sẽ xanh
		vì thủ kho đọc được `Address`, chứ không vì bản sửa còn đúng."""
		frappe.set_user(THU_KHO)
		self.assertFalse(
			frappe.has_permission("Address", "read", doc=self.dia_chi),
			"vai trò kho KHÔNG được đọc Address — fixture của module này dựa vào điều đó",
		)
		self.assertEqual(
			frappe.db.get_value("Delivery Note", self.dn.name, "customer_address"),
			self.dia_chi,
			"phiếu giao phải TRỎ vào địa chỉ đó, không thì render_address trả None và bỏ qua kiểm quyền",
		)

	# --- Bảy hàm ghi ---------------------------------------------------------

	def test_ghi_da_lay(self):
		from erpnext.warehouse_operations.vitri.lay_hang import ghi_da_lay

		frappe.set_user(THU_KHO)
		p = ghi_da_lay(self.dn.name, self.dong, LO, O_GAN, 5)
		self.assertEqual(p["dong"][0]["da_lay"], 5.0)

	def test_bo_dong_da_lay(self):
		from erpnext.warehouse_operations.vitri.lay_hang import bo_dong_da_lay, ghi_da_lay

		frappe.set_user(THU_KHO)
		p = ghi_da_lay(self.dn.name, self.dong, LO, O_GAN, 5)
		ten = p["dong"][0]["da_lay_o"][0]["name"]
		self.assertEqual(bo_dong_da_lay(self.dn.name, ten)["dong"][0]["da_lay"], 0.0)

	def test_doi_lo(self):
		from erpnext.warehouse_operations.vitri.lay_hang import doi_lo

		frappe.set_user(THU_KHO)
		doi_lo(self.dn.name, self.dong, LO_2)
		self.assertEqual(frappe.db.get_value("Delivery Note Item", self.dong, "batch_no"), LO_2)

	def test_tach_dong_theo_lo(self):
		from erpnext.warehouse_operations.vitri.lay_hang import ghi_da_lay, tach_dong_theo_lo

		frappe.set_user(THU_KHO)
		ghi_da_lay(self.dn.name, self.dong, LO, O_GAN, 5)
		tach_dong_theo_lo(self.dn.name, self.dong, LO_2)
		doc = frappe.get_doc("Delivery Note", self.dn.name)
		self.assertEqual(len(doc.items), 2)
		self.assertEqual([flt(d.qty) for d in doc.items], [5.0, 7.0])

	def test_chot_thieu_va_bo_chot_thieu(self):
		from erpnext.warehouse_operations.vitri.lay_hang import bo_chot_thieu, chot_thieu, ghi_da_lay

		frappe.set_user(THU_KHO)
		ghi_da_lay(self.dn.name, self.dong, LO, O_GAN, 7)
		self.assertTrue(chot_thieu(self.dn.name, self.dong)["dong"][0]["da_chot_thieu"])
		self.assertFalse(bo_chot_thieu(self.dn.name, self.dong)["dong"][0]["da_chot_thieu"])

	def test_hoan_tat(self):
		"""`hoan_tat` đi qua `doc.submit()`, KHÔNG qua `_luu_hoac_bao_xung_dot`
		như sáu hàm kia — đường khác, phải đo riêng."""
		from erpnext.warehouse_operations.vitri import so
		from erpnext.warehouse_operations.vitri.lay_hang import ghi_da_lay, hoan_tat

		frappe.set_user(THU_KHO)
		ghi_da_lay(self.dn.name, self.dong, LO, O_XA, 10)
		ghi_da_lay(self.dn.name, self.dong, LO, O_GAN, 2)
		hoan_tat(self.dn.name)

		frappe.set_user("Administrator")
		self.assertEqual(frappe.db.get_value("Delivery Note", self.dn.name, "docstatus"), 1)
		self.assertEqual(so.ton_o(O_XA, ITEM, LO), 0.0)
		self.assertEqual(so.ton_o(O_GAN, ITEM, LO), 18.0)

	# --- Ca biên của chính bản sửa -------------------------------------------

	def test_chuoi_dia_chi_rong_van_ghi_duoc(self):
		"""Phiếu có `address_display = ""` (chuỗi RỖNG, không phải `None`).

		Đây là ca phân biệt hai cách viết điều kiện trong bản sửa. Nếu bản sửa
		chỉ dùng lại chuỗi khi nó KHÁC RỖNG thì ca này rơi lại vào
		`render_address` và `PermissionError` quay về nguyên vẹn — trong khi
		`Document.update_if_missing` xét `is not None`, nên nó vẫn VỨT kết quả
		đi y như ca chuỗi có nội dung. Điều kiện đúng là "khoá CÓ MẶT".

		Ghi bằng `db.set_value` chứ không `doc.save()`: lưu qua tài liệu sẽ
		chạy lại `validate` và tự điền chuỗi về, mất đúng ca cần dựng.
		"""
		from erpnext.warehouse_operations.vitri.lay_hang import ghi_da_lay

		frappe.db.set_value("Delivery Note", self.dn.name, "address_display", "", update_modified=False)
		frappe.db.set_value("Delivery Note", self.dn.name, "shipping_address", "", update_modified=False)

		frappe.set_user(THU_KHO)
		p = ghi_da_lay(self.dn.name, self.dong, LO, O_GAN, 5)
		self.assertEqual(p["dong"][0]["da_lay"], 5.0)

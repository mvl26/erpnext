# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Hệ số giá bán theo khách hàng và quyền sửa (BA12 R01, R07, D01)."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, getdate, nowdate

from erpnext.selling.kiem_gia.cau_hinh import co_quyen_sua_ty_le_lai, he_so_ap_dung

VAI_TRO = "_KG Giám đốc"


def dam_bao_vai_tro(test, *roles):
	"""Tạo vai trò thử nếu chưa có.

	Administrator có mọi vai trò nhưng danh sách đó nằm trong cache "roles" (Redis, dùng
	chung giữa các tiến trình): vai trò tạo trong giao dịch test không có trong danh sách
	đã cache từ trước, còn sau rollback thì cache lại giữ vai trò đã mất. Xóa cache của
	Administrator lúc tạo và khi test kết thúc.
	"""
	for role in roles:
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(
				ignore_permissions=True
			)
	frappe.cache.hdel("roles", "Administrator")
	test.addCleanup(frappe.cache.hdel, "roles", "Administrator")


class CauHinhCase(FrappeTestCase):
	def setUp(self):
		# Cleanup chạy ngược thứ tự đăng ký: rollback trước, xóa cache sau, để cache
		# không giữ giá trị Selling Settings của test.
		self.addCleanup(frappe.set_user, "Administrator")
		self.addCleanup(frappe.clear_document_cache, "Selling Settings", "Selling Settings")
		frappe.db.savepoint("kiem_gia_cau_hinh")
		self.addCleanup(frappe.db.rollback, save_point="kiem_gia_cau_hinh")
		self.d = getdate(nowdate())
		self.sfx = frappe.generate_hash(length=6)
		dam_bao_vai_tro(self, VAI_TRO)
		self.settings(vai_tro_sua_ty_le_lai=VAI_TRO, bat_kiem_gia_ban=0)
		self.giam_doc = self.user("gd", [VAI_TRO, "Sales Master Manager", "Sales Manager"])
		self.nhan_vien = self.user("nv", ["Sales Master Manager", "Sales Manager"])
		self.item_a = self.item()
		self.item_b = self.item()

	def settings(self, **values):
		doc = frappe.get_single("Selling Settings")
		doc.update(values)
		doc.save(ignore_permissions=True)
		return doc

	def user(self, label, roles):
		return (
			frappe.get_doc(
				{
					"doctype": "User",
					"email": f"_kg_{label}_{self.sfx}@example.com",
					"first_name": f"KG {label}",
					"send_welcome_email": 0,
					"roles": [{"role": r} for r in roles],
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def item(self):
		return (
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": f"_KG-{frappe.generate_hash(length=8)}",
					"item_group": frappe.db.get_value("Item Group", {"is_group": 0}, "name"),
					"stock_uom": frappe.db.get_value("UOM", {}, "name"),
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def he_so(self, he_so=1.01, so_hop_dong="HĐ-01", tu=-365, den=None, item_code=None):
		return {
			"he_so": he_so,
			"so_hop_dong": so_hop_dong,
			"tu_ngay": add_days(self.d, tu),
			"den_ngay": add_days(self.d, den) if den is not None else None,
			"item_code": item_code,
		}

	def customer(self, chung=(), theo_hang=()):
		doc = frappe.get_doc(
			{
				"doctype": "Customer",
				"customer_name": f"_KG Khách {frappe.generate_hash(length=6)}",
				"customer_group": frappe.db.get_value("Customer Group", {"is_group": 0}, "name"),
				"territory": frappe.db.get_value("Territory", {"is_group": 0}, "name"),
				"he_so_gia_ban": list(chung),
				"he_so_theo_mat_hang": list(theo_hang),
			}
		)
		return doc.insert(ignore_permissions=True)

	def ap_dung(self, khach, ngay=None):
		return he_so_ap_dung(khach.name, [self.item_a, self.item_b], ngay or self.d)


class TestHeSoApDung(CauHinhCase):
	def test_r01_customer_coefficient_with_its_contract(self):
		kq = self.ap_dung(self.customer([self.he_so(1.01, "HĐ-HIMEDIC")]))[self.item_a]
		self.assertEqual((kq.he_so, kq.so_hop_dong), (1.01, "HĐ-HIMEDIC"))

	def test_r07_customer_without_coefficient(self):
		self.assertEqual(self.ap_dung(self.customer()), {self.item_a: None, self.item_b: None})

	def test_the_coefficient_in_force_on_the_date_is_used(self):
		khach = self.customer([self.he_so(1.01, tu=-100, den=-1), self.he_so(1.05, "HĐ-02", tu=0)])

		self.assertEqual(self.ap_dung(khach)[self.item_a].he_so, 1.05)
		self.assertEqual(self.ap_dung(khach, add_days(self.d, -5))[self.item_a].he_so, 1.01)
		self.assertIsNone(self.ap_dung(khach, add_days(self.d, -200))[self.item_a])

	def test_item_coefficient_applies_only_without_a_customer_coefficient(self):
		khach = self.customer(theo_hang=[self.he_so(1.05, item_code=self.item_a)])
		kq = self.ap_dung(khach)

		self.assertEqual(kq[self.item_a].he_so, 1.05)
		self.assertIsNone(kq[self.item_b])

	def test_customer_coefficient_disables_the_item_table(self):
		khach = self.customer([self.he_so(1.01)], theo_hang=[self.he_so(1.05, item_code=self.item_a)])
		self.assertEqual(self.ap_dung(khach)[self.item_a].he_so, 1.01)

	def test_an_expired_customer_coefficient_still_disables_the_item_table(self):
		khach = self.customer(
			[self.he_so(1.01, tu=-100, den=-1)], theo_hang=[self.he_so(1.05, item_code=self.item_a)]
		)
		self.assertIsNone(self.ap_dung(khach)[self.item_a])


class TestQuyTacR01(CauHinhCase):
	def test_a_contract_number_is_required(self):
		self.assertRaisesRegex(
			frappe.ValidationError, "số hợp đồng", self.customer, [self.he_so(so_hop_dong="")]
		)

	def test_coefficient_must_be_positive(self):
		self.assertRaises(frappe.ValidationError, self.customer, [self.he_so(0)])

	def test_end_before_start_is_rejected(self):
		self.assertRaises(frappe.ValidationError, self.customer, [self.he_so(tu=0, den=-1)])

	def test_two_coefficients_in_force_on_the_same_day_are_rejected(self):
		self.assertRaisesRegex(
			frappe.ValidationError,
			"cùng hiệu lực",
			self.customer,
			[self.he_so(1.01, tu=-100), self.he_so(1.05, tu=0)],
		)
		self.assertRaises(
			frappe.ValidationError, self.customer, [self.he_so(1.01, tu=-100, den=5), self.he_so(1.05, tu=0)]
		)

	def test_consecutive_coefficients_are_fine(self):
		self.customer([self.he_so(1.01, tu=-100, den=-1), self.he_so(1.05, tu=0)])

	def test_customer_table_rows_have_no_item(self):
		self.assertRaises(frappe.ValidationError, self.customer, [self.he_so(item_code=self.item_a)])

	def test_item_table_rows_need_an_item_and_must_not_overlap_per_item(self):
		self.assertRaises(frappe.ValidationError, self.customer, theo_hang=[self.he_so()])
		self.assertRaises(
			frappe.ValidationError,
			self.customer,
			theo_hang=[self.he_so(item_code=self.item_a), self.he_so(1.05, tu=0, item_code=self.item_a)],
		)
		self.customer(theo_hang=[self.he_so(item_code=self.item_a), self.he_so(1.05, item_code=self.item_b)])


class TestQuyenSuaHeSo(CauHinhCase):
	def test_staff_cannot_create_a_customer_with_a_coefficient(self):
		frappe.set_user(self.nhan_vien)
		self.assertRaises(frappe.PermissionError, self.customer, [self.he_so()])

	def test_staff_cannot_change_a_coefficient(self):
		khach = self.customer([self.he_so()])
		frappe.set_user(self.nhan_vien)
		khach.he_so_gia_ban[0].he_so = 1.5
		self.assertRaises(frappe.PermissionError, khach.save)

	def test_staff_cannot_add_an_item_coefficient(self):
		khach = self.customer()
		frappe.set_user(self.nhan_vien)
		khach.append("he_so_theo_mat_hang", self.he_so(item_code=self.item_a))
		self.assertRaises(frappe.PermissionError, khach.save)

	def test_staff_can_create_customers_and_edit_other_fields(self):
		frappe.set_user(self.nhan_vien)
		khach = self.customer()
		khach.customer_details = "ghi chú"
		khach.save()

	def test_staff_can_edit_other_fields_of_a_customer_with_a_coefficient(self):
		khach = self.customer([self.he_so()])
		frappe.set_user(self.nhan_vien)
		khach.reload()
		khach.customer_details = "ghi chú"
		khach.save()

	def test_director_can_set_coefficients(self):
		frappe.set_user(self.giam_doc)
		khach = self.customer([self.he_so()])
		khach.he_so_gia_ban[0].he_so = 1.05
		khach.save()
		self.assertEqual(self.ap_dung(khach)[self.item_a].he_so, 1.05)

	def test_staff_cannot_change_the_settings(self):
		frappe.set_user(self.nhan_vien)
		self.assertRaises(frappe.PermissionError, self.settings, bat_kiem_gia_ban=1)
		self.assertRaises(frappe.PermissionError, self.settings, vai_tro_sua_ty_le_lai="Sales Manager")

	def test_director_can_change_the_settings(self):
		frappe.set_user(self.giam_doc)
		self.settings(bat_kiem_gia_ban=1)

	def test_staff_can_change_unrelated_settings(self):
		frappe.set_user(self.nhan_vien)
		self.settings(allow_multiple_items=1)

	def test_permission_follows_the_configured_role(self):
		frappe.set_user(self.giam_doc)
		self.assertTrue(co_quyen_sua_ty_le_lai())
		frappe.set_user(self.nhan_vien)
		self.assertFalse(co_quyen_sua_ty_le_lai())

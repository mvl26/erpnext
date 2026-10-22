# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Cấu hình % lãi và quyền sửa (spec mục 6.1.2; tình huống G3, G4, G9, G13)."""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.selling.kiem_gia.cau_hinh import co_quyen_sua_ty_le_lai, ty_le_lai_ap_dung
from erpnext.stock.tests.test_item_code_rule import use_naming_mode

VAI_TRO = "_KG Giám đốc"


class CauHinhCase(FrappeTestCase):
	def setUp(self):
		# Cleanup chạy ngược thứ tự đăng ký: rollback trước, xóa cache sau, để cache
		# không giữ giá trị Selling Settings của test.
		self.addCleanup(frappe.set_user, "Administrator")
		self.addCleanup(frappe.clear_document_cache, "Selling Settings", "Selling Settings")
		frappe.db.savepoint("kiem_gia_cau_hinh")
		self.addCleanup(frappe.db.rollback, save_point="kiem_gia_cau_hinh")
		use_naming_mode(self, "Item Code")
		self.sfx = frappe.generate_hash(length=6)
		if not frappe.db.exists("Role", VAI_TRO):
			frappe.get_doc({"doctype": "Role", "role_name": VAI_TRO, "desk_access": 1}).insert(
				ignore_permissions=True
			)
		self.settings(ty_le_lai_mac_dinh=1, vai_tro_sua_ty_le_lai=VAI_TRO)
		self.giam_doc = self.user("gd", [VAI_TRO, "Sales Master Manager", "Item Manager", "Sales Manager"])
		self.nhan_vien = self.user("nv", ["Sales Master Manager", "Item Manager", "Sales Manager"])

	def settings(self, **values):
		doc = frappe.get_single("Selling Settings")
		doc.update(values)
		doc.save(ignore_permissions=True)
		return doc

	def user(self, label, roles):
		doc = frappe.get_doc(
			{
				"doctype": "User",
				"email": f"_kg_{label}_{self.sfx}@example.com",
				"first_name": f"KG {label}",
				"send_welcome_email": 0,
				"roles": [{"role": r} for r in roles],
			}
		).insert(ignore_permissions=True)
		return doc.name

	def customer(self, **fields):
		doc = frappe.get_doc(
			{
				"doctype": "Customer",
				"customer_name": f"_KG Khách {frappe.generate_hash(length=6)}",
				"customer_group": frappe.db.get_value("Customer Group", {"is_group": 0}, "name"),
				"territory": frappe.db.get_value("Territory", {"is_group": 0}, "name"),
				**fields,
			}
		)
		return doc.insert(ignore_permissions=True)

	def item(self, customer_items=()):
		doc = frappe.new_doc("Item")
		doc.item_code = f"_KG-{frappe.generate_hash(length=8)}"
		doc.item_name = doc.item_code
		doc.item_group = frappe.db.get_value("Item Group", {"is_group": 0}, "name")
		doc.stock_uom = frappe.db.get_value("UOM", {}, "name")
		for row in customer_items:
			doc.append("customer_items", row)
		return doc.insert(ignore_permissions=True)


class TestTyLeLaiApDung(CauHinhCase):
	def test_default_applies_to_every_customer(self):
		kq = ty_le_lai_ap_dung(self.customer().name, None)

		self.assertEqual((kq.kiem, kq.ty_le_lai), (1, 1))

	def test_g3_customer_rate(self):
		khach = self.customer(ty_le_lai_rieng=1, ty_le_lai=2)

		self.assertEqual(ty_le_lai_ap_dung(khach.name, None).ty_le_lai, 2)

	def test_g4_item_customer_rate_wins(self):
		khach = self.customer(ty_le_lai_rieng=1, ty_le_lai=2)
		item = self.item([{"customer_name": khach.name, "ty_le_lai_rieng": 1, "ty_le_lai": 0.5}])

		self.assertEqual(ty_le_lai_ap_dung(khach.name, item.name).ty_le_lai, 0.5)
		self.assertEqual(ty_le_lai_ap_dung(khach.name, self.item().name).ty_le_lai, 2)

	def test_zero_is_a_valid_customer_rate(self):
		khach = self.customer(ty_le_lai_rieng=1, ty_le_lai=0)

		self.assertEqual(ty_le_lai_ap_dung(khach.name, None).ty_le_lai, 0)

	def test_g9_customer_switched_off(self):
		kq = ty_le_lai_ap_dung(self.customer(kiem_gia_ban=0).name, None)

		self.assertEqual(kq.kiem, 0)
		self.assertIsNone(kq.ty_le_lai)

	def test_a_customer_code_row_does_not_set_a_rate(self):
		khach = self.customer()
		item = self.item([{"customer_name": khach.name, "ref_code": "KH-001"}])

		self.assertEqual(ty_le_lai_ap_dung(khach.name, item.name).ty_le_lai, 1)


class TestQuyenSuaTyLeLai(CauHinhCase):
	def test_g13_staff_cannot_change_a_customer_rate(self):
		khach = self.customer()
		frappe.set_user(self.nhan_vien)
		khach.ty_le_lai_rieng = 1
		khach.ty_le_lai = 5

		self.assertRaises(frappe.PermissionError, khach.save, ignore_permissions=True)

	def test_g13_staff_cannot_switch_the_check_off(self):
		khach = self.customer()
		frappe.set_user(self.nhan_vien)
		khach.kiem_gia_ban = 0

		self.assertRaises(frappe.PermissionError, khach.save, ignore_permissions=True)

	def test_staff_can_create_customers_and_edit_other_fields(self):
		frappe.set_user(self.nhan_vien)
		khach = self.customer()
		khach.website = "https://example.com"
		khach.save(ignore_permissions=True)

	def test_staff_cannot_create_a_customer_with_its_own_rate(self):
		frappe.set_user(self.nhan_vien)

		self.assertRaises(frappe.PermissionError, self.customer, ty_le_lai_rieng=1, ty_le_lai=9)

	def test_director_can_change_the_rate(self):
		khach = self.customer()
		frappe.set_user(self.giam_doc)
		khach.ty_le_lai_rieng = 1
		khach.ty_le_lai = 5
		khach.save(ignore_permissions=True)

		self.assertEqual(ty_le_lai_ap_dung(khach.name, None).ty_le_lai, 5)

	def test_g13_staff_cannot_change_an_item_customer_rate(self):
		khach = self.customer()
		item = self.item()
		frappe.set_user(self.nhan_vien)
		item.append("customer_items", {"customer_name": khach.name, "ty_le_lai_rieng": 1, "ty_le_lai": 3})

		self.assertRaises(frappe.PermissionError, item.save, ignore_permissions=True)

	def test_staff_can_still_maintain_customer_item_codes(self):
		khach = self.customer()
		item = self.item()
		frappe.set_user(self.nhan_vien)
		item.append("customer_items", {"customer_name": khach.name, "ref_code": "KH-002"})
		item.save(ignore_permissions=True)

		self.assertEqual(item.customer_code, "KH-002")

	def test_a_row_needs_a_customer_code_or_a_rate(self):
		self.assertRaises(frappe.ValidationError, self.item, [{"customer_name": self.customer().name}])

	def test_rate_only_row_keeps_customer_code_search_clean(self):
		khach = self.customer()
		item = self.item(
			[{"customer_name": khach.name, "ref_code": "KH-003", "ty_le_lai_rieng": 1, "ty_le_lai": 1.5}]
		)

		self.assertEqual(item.customer_code, "KH-003")
		self.assertEqual(ty_le_lai_ap_dung(khach.name, item.name).ty_le_lai, 1.5)

	def test_a_rate_row_next_to_a_code_row_for_the_same_customer_is_rejected(self):
		khach = self.customer()
		self.assertRaisesRegex(
			frappe.ValidationError,
			"mỗi khách một dòng",
			self.item,
			[
				{"customer_name": khach.name, "ref_code": "KH-004"},
				{"customer_name": khach.name, "ty_le_lai_rieng": 1, "ty_le_lai": 1.5},
			],
		)

	def test_g13_staff_cannot_change_the_settings(self):
		frappe.set_user(self.nhan_vien)

		self.assertRaises(frappe.PermissionError, self.settings, ty_le_lai_mac_dinh=5)
		self.assertRaises(frappe.PermissionError, self.settings, vai_tro_sua_ty_le_lai="Sales Manager")

	def test_director_can_change_the_settings(self):
		frappe.set_user(self.giam_doc)
		self.settings(ty_le_lai_mac_dinh=2)

		self.assertEqual(ty_le_lai_ap_dung(self.customer().name, None).ty_le_lai, 2)

	def test_staff_can_change_unrelated_settings(self):
		frappe.set_user(self.nhan_vien)
		self.settings(allow_multiple_items=1)

	def test_permission_follows_the_configured_role(self):
		frappe.set_user(self.giam_doc)
		self.assertTrue(co_quyen_sua_ty_le_lai())
		frappe.set_user(self.nhan_vien)
		self.assertFalse(co_quyen_sua_ty_le_lai())

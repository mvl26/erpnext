from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from gameplan.miyano import hr_sync, permissions, utils

HCNS = "P. HCNS - pháp chế - M"
BLD = "Ban lãnh đạo - M"
KETOAN = "P. Kế toán - M"


class TestGroupCreation(FrappeTestCase):
	def _can_create(self, user, department, roles=()):
		with patch.object(utils, "get_user_department", return_value=department), patch.object(
			utils.frappe, "get_roles", return_value=list(roles)
		):
			return permissions.can_create_group(user)

	def test_admin_can_create(self):
		self.assertTrue(permissions.can_create_group("Administrator"))
		self.assertTrue(self._can_create("a@x.test", KETOAN, roles=["System Manager"]))
		self.assertTrue(self._can_create("a@x.test", KETOAN, roles=["Gameplan Admin"]))

	def test_hcns_and_directors_can_create(self):
		self.assertTrue(self._can_create("hcns@x.test", HCNS, roles=["Gameplan Member"]))
		self.assertTrue(self._can_create("gd@x.test", BLD, roles=["Gameplan Member"]))

	def test_admin_approved_creator_role(self):
		self.assertTrue(self._can_create("k@x.test", KETOAN, roles=["Gameplan Member", "Gameplan Group Creator"]))

	def test_other_members_cannot_create(self):
		self.assertFalse(self._can_create("kt@x.test", KETOAN, roles=["Gameplan Member"]))
		self.assertFalse(self._can_create("kt@x.test", None, roles=["Gameplan Member"]))

	def test_insert_group_blocked_for_non_creator(self):
		with patch.object(permissions, "can_create_group", return_value=False):
			doc = frappe.get_doc(doctype="GP Project", title="Nhóm thử không quyền")
			with self.assertRaises(frappe.PermissionError):
				permissions.validate_new_group(doc)

	def test_insert_group_allowed_for_creator(self):
		with patch.object(permissions, "can_create_group", return_value=True):
			doc = frappe.get_doc(doctype="GP Project", title="Nhóm thử có quyền")
			permissions.validate_new_group(doc)  # không ném lỗi


class TestCompanyScope(FrappeTestCase):
	def test_allowed_companies_from_site_config(self):
		with patch.dict(frappe.conf, {"gameplan_companies": ["Miyano"]}):
			self.assertEqual(utils.get_allowed_companies(), ["Miyano"])

	def test_user_in_other_company_is_not_company_user(self):
		with patch.object(utils, "get_allowed_companies", return_value=["Miyano"]), patch.object(
			utils, "get_user_company", return_value="Cong ty khac"
		):
			self.assertFalse(utils.is_company_user("x@y.test"))

	def test_user_in_company_is_company_user(self):
		with patch.object(utils, "get_allowed_companies", return_value=["Miyano"]), patch.object(
			utils, "get_user_company", return_value="Miyano"
		):
			self.assertTrue(utils.is_company_user("x@y.test"))

	def test_user_without_employee_is_not_company_user(self):
		with patch.object(utils, "get_allowed_companies", return_value=["Miyano"]), patch.object(
			utils, "get_user_company", return_value=None
		):
			self.assertFalse(utils.is_company_user("x@y.test"))

	def test_ensure_member_rejects_other_company(self):
		with patch.object(hr_sync, "is_company_user", return_value=False), patch.object(
			hr_sync, "remove_member", return_value=False
		) as rm:
			self.assertFalse(hr_sync.ensure_member("hcns@miyano.test"))
			rm.assert_called_once()

	def test_invite_outside_company_rejected(self):
		from gameplan.api import invite_by_email

		with patch.object(utils, "is_company_user", return_value=False):
			with self.assertRaises(frappe.PermissionError):
				invite_by_email("nguoi.ngoai@gmail.com", "Gameplan Member")

from unittest.mock import patch

import frappe
from frappe.core.doctype.role.role import Role
from frappe.tests.utils import FrappeTestCase

from erpnext.access.permissions.matrix import load_matrix
from erpnext.access.permissions.profiles import (
	combined_profile_name,
	sync_role_profiles,
	sync_roles,
)
from erpnext.access.tests.helpers import small_matrix


def profile_roles(name):
	return {r.role for r in frappe.get_doc("Role Profile", name).roles}


def modified(name):
	return frappe.db.get_value("Role Profile", name, "modified")


class TestProfiles(FrappeTestCase):
	SHOW_TRANSACTION_COMMIT_WARNINGS = True

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		# A desk_access change re-types every real user holding the role (Role.update_user_type_on_change) and
		# clear_sessions() then COMMITS the test transaction (frappe/sessions.py delete_session) — that is how
		# throwaway Role Profiles leaked onto site miyano. The re-typing is frappe's, not under test here.
		cls._retype = patch.object(Role, "update_user_type_on_change")
		cls._retype.start()
		cls.m = load_matrix()
		sync_roles(cls.m)  # the class-scope rollback removes these

	@classmethod
	def tearDownClass(cls):
		cls._retype.stop()
		super().tearDownClass()
		frappe.clear_cache()

	def test_new_roles_created_custom_with_desk_access(self):
		for role in self.m.roles.values():
			for name in role.names:
				self.assertEqual(frappe.db.get_value("Role", name, "desk_access"), role.desk_access, name)
				if role.is_new:
					self.assertEqual(frappe.db.get_value("Role", name, "is_custom"), 1, name)

	def test_lk_desk_access_zero(self):
		lk = self.m.roles["LK"]
		self.assertEqual(lk.desk_access, 0)
		for name in lk.names:
			self.assertEqual(frappe.db.get_value("Role", name, "desk_access"), 0)

	def test_existing_role_desk_access_corrected_and_enabled_untouched(self):
		frappe.db.set_value("Role", "Customer", "desk_access", 1)
		sync_roles(self.m)
		self.assertEqual(frappe.db.get_value("Role", "Customer", "desk_access"), 0)
		self.assertEqual(sync_roles(self.m), 0)

	def test_roles_outside_matrix_untouched(self):
		name = "Zzz Probe " + frappe.generate_hash(length=6)
		frappe.get_doc({"doctype": "Role", "role_name": name, "desk_access": 1}).insert()
		sync_roles(self.m)
		self.assertEqual(frappe.db.get_value("Role", name, "desk_access"), 1)

	def test_kho_tk_exactly_three_roles(self):
		sync_role_profiles(self.m)
		self.assertEqual(profile_roles("RP-KHO-TK"), {"Employee", "Projects User", "Stock User"})

	def test_every_matrix_profile_matches(self):
		sync_role_profiles(self.m)
		for profile in self.m.role_profiles:
			self.assertEqual(profile_roles(profile), set(self.m.profile_roles(profile)), profile)

	def test_manual_extra_role_removed(self):
		sync_role_profiles(self.m)
		doc = frappe.get_doc("Role Profile", "RP-NV")
		doc.append("roles", {"role": "Sales Manager"})
		doc.save(ignore_permissions=True)
		self.assertIn("Sales Manager", profile_roles("RP-NV"))
		sync_role_profiles(self.m)
		self.assertEqual(profile_roles("RP-NV"), set(self.m.profile_roles("RP-NV")))

	def test_missing_role_added(self):
		sync_role_profiles(self.m)
		doc = frappe.get_doc("Role Profile", "RP-KHO-TK")
		doc.set("roles", [r for r in doc.roles if r.role != "Stock User"])
		doc.save(ignore_permissions=True)
		sync_role_profiles(self.m)
		self.assertIn("Stock User", profile_roles("RP-KHO-TK"))

	def test_second_run_writes_nothing(self):
		sync_role_profiles(self.m)
		before = {p: modified(p) for p in self.m.role_profiles}
		count = frappe.db.count("Role Profile")
		self.assertEqual(sync_roles(self.m), 0)
		self.assertEqual(sync_role_profiles(self.m), [])
		self.assertEqual(frappe.db.count("Role Profile"), count)
		self.assertEqual({p: modified(p) for p in self.m.role_profiles}, before)

	def _assetcore_stand_in(self):
		name = "ZZ-AC-" + frappe.generate_hash(length=6)
		frappe.get_doc(
			{
				"doctype": "Role Profile",
				"role_profile": name,
				"roles": [{"role": "Quality Manager"}, {"role": "Sales User"}],
			}
		).insert(ignore_permissions=True)
		return name

	def test_combined_profile_is_union(self):
		ac = self._assetcore_stand_in()
		m = small_matrix()
		m.role_profiles = {"RP-KHO-TK": ["BASE", "STU"]}
		m.combined_profiles = [{"erp": "RP-KHO-TK", "assetcore": ac}]
		self.assertEqual(sync_role_profiles(m), [])
		name = combined_profile_name("RP-KHO-TK", ac)
		self.assertEqual(name, f"RP-KHO-TK+AC-{ac}")
		self.assertEqual(
			profile_roles(name),
			{"Employee", "Projects User", "Stock User", "Quality Manager", "Sales User"},
		)
		before = modified(name)
		sync_role_profiles(m)
		self.assertEqual(modified(name), before)

	def test_combined_profile_missing_assetcore_warns_and_skips(self):
		m = small_matrix()
		m.role_profiles = {"RP-NV": ["BASE"]}
		m.combined_profiles = [{"erp": "RP-NV", "assetcore": "ZZ-nope-" + frappe.generate_hash(length=6)}]
		warnings = sync_role_profiles(m)
		self.assertEqual(len(warnings), 1)
		self.assertIn("skipped", warnings[0])
		self.assertFalse(
			frappe.db.exists(
				"Role Profile", combined_profile_name("RP-NV", m.combined_profiles[0]["assetcore"])
			)
		)

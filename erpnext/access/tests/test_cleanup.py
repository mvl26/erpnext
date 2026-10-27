"""Role / Role Profile hygiene — ``erpnext.access.permissions.cleanup``.

Every test runs inside its own savepoint and rolls back to it, so nothing it deletes — test rows or the real
leftovers the scan also finds on site miyano — survives the test. The lists of dead names are patched to throwaway
names, ``frappe.clear_cache`` is patched (the Redis caches are shared with production), and the old department
profiles and the test e-mail domains are patched to none so the real ones are not even touched inside the
transaction; the test-user cases use their own domain ``zzt-cleanup.test``.
"""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.access.permissions import cleanup
from erpnext.access.permissions.profiles import combined_profile_name
from erpnext.access.tests.helpers import make_user, small_matrix


def make_role(name):
	frappe.get_doc({"doctype": "Role", "role_name": name, "desk_access": 1}).insert(ignore_permissions=True)
	return name


def make_profile(name, *roles):
	frappe.get_doc(
		{"doctype": "Role Profile", "role_profile": name, "roles": [{"role": r} for r in roles]}
	).insert(ignore_permissions=True)
	return name


def give_profile(user, profile):
	doc = frappe.get_doc("User", user)
	doc.role_profile_name = profile
	doc.save(ignore_permissions=True)


def roles_of(user):
	return set(frappe.get_all("Has Role", filters={"parenttype": "User", "parent": user}, pluck="role"))


class CleanupCase(FrappeTestCase):
	SHOW_TRANSACTION_COMMIT_WARNINGS = True

	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.savepoint("test_cleanup")
		self.addCleanup(frappe.db.rollback, save_point="test_cleanup")
		self.tag = frappe.generate_hash(length=6)
		self.m = small_matrix()
		self.m.role_profiles = {**self.m.role_profiles, f"RP-ZZT-KEEP-{self.tag}": ["BASE"]}
		self.m.combined_profiles = []
		for target, value in (
			("erpnext.access.permissions.cleanup.load_matrix", self.m),
			("erpnext.access.permissions.cleanup.DEAD_WORKFLOWS", ()),
			("erpnext.access.permissions.cleanup.DEAD_ROLES", ()),
			# make_user writes @example.com: keep every test user (and the site's real leftovers) out of scope
			("erpnext.access.permissions.cleanup.TEST_EMAIL_DOMAINS", ()),
			("erpnext.access.permissions.cutover.OLD_ERP_PROFILES", ()),
			("erpnext.regional.vietnam.role_profiles.VN_ROLE_PROFILES", {}),
		):
			patcher = (
				patch(target, return_value=value) if target.endswith("load_matrix") else patch(target, value)
			)
			patcher.start()
			self.addCleanup(patcher.stop)
		patcher = patch.object(frappe, "clear_cache")
		patcher.start()
		self.addCleanup(patcher.stop)

	def run_cleanup(self, dry_run=0):
		with patch("builtins.print"):
			return cleanup.run(dry_run=dry_run)


class TestRoleCleanup(CleanupCase):
	def test_dead_role_held_by_a_user_only_is_deleted(self):
		role = make_role(f"ZZT Dead {self.tag}")
		user = make_user(role, prefix="cleanup")
		with patch.object(cleanup, "DEAD_ROLES", (role,)):
			lines = self.run_cleanup()
		self.assertIn(f"done: xóa Role '{role}'", lines)
		self.assertFalse(frappe.db.exists("Role", role))
		self.assertFalse(frappe.db.exists("Has Role", {"role": role}))
		self.assertNotIn(role, roles_of(user))

	def test_dead_role_still_linked_is_kept_with_its_users(self):
		role = make_role(f"ZZT Linked {self.tag}")
		user = make_user(role, prefix="cleanup")
		make_profile(f"ZZT-HOLDER-{self.tag}", role)
		with patch.object(cleanup, "DEAD_ROLES", (role,)):
			lines = self.run_cleanup()
		self.assertTrue(any(line.startswith(f"skip: Role '{role}'") for line in lines), lines)
		self.assertTrue(frappe.db.exists("Role", role))
		self.assertTrue(frappe.db.exists("Has Role", {"parent": user, "role": role}))

	def test_matrix_role_is_never_a_dead_role(self):
		matrix_role = next(iter(self.m.roles.values())).names[0]
		with patch.object(cleanup, "DEAD_ROLES", (matrix_role,)):
			self.assertEqual(cleanup._dead_roles(dry=False, m=self.m), [])
		self.assertTrue(frappe.db.exists("Role", matrix_role))

	def test_stale_rbac_role_deleted_only_when_unused(self):
		matrix_roles = {r for r in cleanup._matrix_roles(self.m) if frappe.db.exists("Role", r)}
		unused = make_role(f"MVL ZZT Old {self.tag}")
		held = make_role(f"MVL ZZT Held {self.tag}")
		make_user(held, prefix="cleanup")
		lines = self.run_cleanup()
		self.assertIn(f"done: xóa Role '{unused}'", lines)
		self.assertTrue(any(line.startswith(f"skip: Role '{held}'") for line in lines), lines)
		self.assertTrue(frappe.db.exists("Role", held))
		self.assertEqual({r for r in matrix_roles if frappe.db.exists("Role", r)}, matrix_roles)

	def test_stale_rp_profile_deleted_unless_held_and_matrix_profiles_kept(self):
		keep = make_profile(f"RP-ZZT-KEEP-{self.tag}", "Employee")
		stale = make_profile(f"RP-ZZT-OLD-{self.tag}", "Employee")
		held = make_profile(f"RP-ZZT-HELD-{self.tag}", "Employee")
		give_profile(make_user(prefix="cleanup"), held)
		lines = self.run_cleanup()
		self.assertIn(f"done: xóa Role Profile '{stale}'", lines)
		self.assertFalse(frappe.db.exists("Role Profile", stale))
		self.assertTrue(frappe.db.exists("Role Profile", keep))
		self.assertTrue(frappe.db.exists("Role Profile", held))
		self.assertTrue(any(line.startswith(f"skip: Role Profile '{held}'") for line in lines), lines)

	def test_test_stand_in_and_its_combined_profile_are_deleted(self):
		stand_in = make_profile(f"ZZ-AC-{self.tag}", "Quality Manager")
		combined = make_profile(combined_profile_name("RP-KHO-TK", stand_in), "Employee", "Quality Manager")
		lines = self.run_cleanup()
		self.assertLess(
			lines.index(f"done: xóa Role Profile '{combined}'"),
			lines.index(f"done: xóa Role Profile '{stand_in}'"),
		)
		self.assertFalse(frappe.db.exists("Role Profile", stand_in))
		self.assertFalse(frappe.db.exists("Role Profile", combined))

	def test_wanted_combined_profile_is_kept(self):
		self.m.combined_profiles = [{"erp": "RP-KHO-TK", "assetcore": "Kỹ thuật viên"}]
		combined = make_profile(combined_profile_name("RP-KHO-TK", "Kỹ thuật viên"), "Employee")
		self.run_cleanup()
		self.assertTrue(frappe.db.exists("Role Profile", combined))

	def test_old_department_profile_deleted_when_unused(self):
		old = make_profile(f"ZZT Sales {self.tag}", "Sales User")
		with patch("erpnext.access.permissions.cutover.OLD_ERP_PROFILES", (old,)):
			lines = self.run_cleanup()
		self.assertIn(f"done: xóa Role Profile '{old}'", lines)

	def test_dry_run_changes_nothing(self):
		role = make_role(f"ZZT Dead {self.tag}")
		user = make_user(role, prefix="cleanup")
		stale = make_profile(f"RP-ZZT-OLD-{self.tag}", "Employee")
		frappe.clear_cache.reset_mock()  # make_user clears its own user cache
		with patch.object(cleanup, "DEAD_ROLES", (role,)):
			lines = self.run_cleanup(dry_run=1)
		self.assertIn(f"[dry-run] xóa Role '{role}'", lines)
		self.assertIn(f"[dry-run] xóa Role Profile '{stale}'", lines)
		self.assertTrue(frappe.db.exists("Role", role))
		self.assertIn(role, roles_of(user))
		self.assertTrue(frappe.db.exists("Role Profile", stale))
		frappe.clear_cache.assert_not_called()

	def test_missing_dead_workflow_is_ignored(self):
		with patch.object(cleanup, "DEAD_WORKFLOWS", (f"ZZT no such workflow {self.tag}",)):
			self.assertEqual(cleanup._workflows(dry=False, m=self.with_workflows(True)), [])

	def with_workflows(self, on):
		from erpnext.access.permissions.matrix import load_matrix

		m = small_matrix(workflows=load_matrix().workflows)
		m.rules = {**m.rules, "workflows_enabled": on}
		return m

	def test_rbac_workflows_retire_only_when_switched_off(self):
		self.assertEqual(cleanup.retired_rbac_workflows(self.with_workflows(True)), [])
		names = cleanup.retired_rbac_workflows(self.with_workflows(False))
		self.assertIn("WF-PO Purchase Order", names)
		self.assertIn("WF-LA Shift Request", names)
		self.assertNotIn("Cong Tac Approval", names)  # hrms' own version: no G11 condition

	def test_cong_tac_approval_rewritten_by_the_sync_is_retired(self):
		if not frappe.db.exists("Workflow", "Cong Tac Approval"):
			self.skipTest("hrms workflow Cong Tac Approval is absent on this site")
		frappe.get_doc(
			{
				"doctype": "Workflow Transition",
				"parent": "Cong Tac Approval",
				"parenttype": "Workflow",
				"parentfield": "transitions",
				"state": "Chờ COO duyệt",
				"action": "Duyệt",
				"next_state": "COO đã duyệt",
				"allowed": "COO",
				"condition": cleanup.G11_MARKER,
			}
		).db_insert()
		self.assertIn("Cong Tac Approval", cleanup.retired_rbac_workflows(self.with_workflows(False)))

	def test_deleted_workflow_leaves_cache_and_list_column_clean(self):
		doctype = frappe.db.get_value("Workflow", {}, "document_type")
		if not doctype:
			self.skipTest("no Workflow on this site")
		name = frappe.db.get_value("Workflow", {"document_type": doctype}, "name")
		with (
			patch.object(cleanup, "DEAD_WORKFLOWS", (name,)),
			patch.object(cleanup, "_delete", return_value=f"done: xóa Workflow '{name}'") as delete,
			patch.object(cleanup, "_hide_state_column") as hide,
			patch.object(frappe.cache, "hdel") as hdel,
			patch.object(frappe.db, "exists", return_value=False),
		):
			lines = cleanup._workflows(dry=False, m=self.with_workflows(True))
		self.assertEqual(lines, [f"done: xóa Workflow '{name}'"])
		delete.assert_called_once_with(False, "Workflow", name)
		hdel.assert_called_once_with("workflow", doctype)
		hide.assert_called_once_with(doctype)

	def test_real_dead_lists_never_name_a_matrix_role_or_profile(self):
		from erpnext.access.permissions.matrix import load_matrix

		m = load_matrix()
		self.assertFalse(set(cleanup.DEAD_ROLES) & cleanup._matrix_roles(m))
		self.assertFalse({p for p in cleanup.wanted_profiles(m) if p.startswith(cleanup.TEST_PROFILE_PREFIX)})


DOMAIN = "zzt-cleanup.test"


def contact_for(email, user=None, party=None):
	doc = frappe.get_doc(
		{
			"doctype": "Contact",
			"first_name": "ZZT",
			"user": user,
			"email_ids": [{"email_id": email, "is_primary": 1}],
			"links": [{"link_doctype": "Company", "link_name": party}] if party else [],
		}
	).insert(ignore_permissions=True)
	return doc.name


class TestTestUserCleanup(CleanupCase):
	def setUp(self):
		super().setUp()
		patcher = patch.object(cleanup, "TEST_EMAIL_DOMAINS", (DOMAIN,))
		patcher.start()
		self.addCleanup(patcher.stop)

	def make_test_user(self, *roles):
		email = f"u-{frappe.generate_hash(length=8)}@{DOMAIN}"
		frappe.get_doc(
			{"doctype": "User", "email": email, "first_name": "ZZT", "send_welcome_email": 0}
		).insert(ignore_permissions=True).add_roles(*roles)
		return email

	def test_test_user_and_its_own_contact_are_deleted(self):
		user = self.make_test_user("Sales User")
		own = contact_for(user, user=user)
		lines = self.run_cleanup()
		self.assertIn(f"done: xóa User '{user}'", lines)
		self.assertFalse(frappe.db.exists("User", user))
		self.assertFalse(frappe.db.exists("Contact", own))
		self.assertFalse(frappe.db.exists("Has Role", {"parent": user}))

	def test_contact_linked_to_a_party_survives_its_test_user(self):
		user = self.make_test_user()
		kept = contact_for(user, user=user, party="Miyano")
		self.run_cleanup()
		self.assertFalse(frappe.db.exists("User", user))
		self.assertTrue(frappe.db.exists("Contact", kept))
		self.assertFalse(frappe.db.get_value("Contact", kept, "user"))  # User.on_trash unlinks it

	def test_orphan_contacts_of_test_emails(self):
		orphan = contact_for(f"gone-{self.tag}@{DOMAIN}")
		with_party = contact_for(f"party-{self.tag}@{DOMAIN}", party="Miyano")
		real = contact_for(f"real-{self.tag}@miyano.com.vn")
		lines = self.run_cleanup()
		self.assertIn("done: xóa 1 Contact của user test đã xóa", lines)
		self.assertFalse(frappe.db.exists("Contact", orphan))
		self.assertTrue(frappe.db.exists("Contact", with_party))
		self.assertTrue(frappe.db.exists("Contact", real))

	def test_dry_run_keeps_test_users_and_contacts(self):
		user = self.make_test_user()
		own = contact_for(user, user=user)
		orphan = contact_for(f"gone-{self.tag}@{DOMAIN}")
		lines = self.run_cleanup(dry_run=1)
		self.assertIn(f"[dry-run] xóa User '{user}'", lines)
		self.assertTrue(frappe.db.exists("User", user))
		self.assertTrue(frappe.db.exists("Contact", own))
		self.assertTrue(frappe.db.exists("Contact", orphan))


class TestTestEmail(FrappeTestCase):
	def test_only_reserved_test_domains_match(self):
		for email in ("a@example.com", "b@EXAMPLE.invalid", "c@test.local", "d@assetcore.test"):
			self.assertTrue(cleanup.is_test_email(email), email)
		for email in ("anh.dn@miyano.com.vn", "x@gmail.com", "y@example.com.vn", "", None, "Administrator"):
			self.assertFalse(cleanup.is_test_email(email), email)

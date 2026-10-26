import io
from contextlib import redirect_stdout
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.access.permissions import audit, sync
from erpnext.access.permissions.matrix import DocTypeEntry, load_matrix
from erpnext.access.permissions.site import DocTypeInfo, SiteInfo
from erpnext.access.permissions.user_scope import sync_user_permissions, users_without_scope
from erpnext.access.permissions.validate import Problems
from erpnext.access.tests.helpers import small_matrix

DT = "Supplier Scorecard Period"  # rarely used DocType, safe to give a Custom DocPerm in a test
WAREHOUSE_RULE = {
	"roles": ["STU", "PDA"],
	"apply_to_all": 0,
	"applicable_for": ["Stock Entry", "Pick List"],
}
ENABLED = {"mvl_rbac_enabled": 1}


def count(doctype):
	return frappe.db.count(doctype)


def tiny_site():
	return SiteInfo(
		doctypes={
			DT: DocTypeInfo(name=DT, app="erpnext", module="Buying", is_submittable=False, issingle=False)
		}
	)


def tiny_matrix():
	m = small_matrix(doctypes={DT: DocTypeEntry(state="matrix", perms={"PU": "CRW"})})
	m.role_profiles, m.combined_profiles = {}, []  # keep real Role Profiles untouched
	return m


def make_user(*roles):
	email = f"sync-{frappe.generate_hash(length=8)}@example.com"
	user = frappe.get_doc({"doctype": "User", "email": email, "first_name": "Sync", "send_welcome_email": 0})
	user.insert(ignore_permissions=True)
	user.add_roles(*roles)
	return email


def permissions_of(user, allow):
	rows = frappe.get_all(
		"User Permission",
		filters={"user": user, "allow": allow},
		fields=["for_value", "applicable_for", "apply_to_all_doctypes"],
	)
	return sorted((r.for_value, r.applicable_for, r.apply_to_all_doctypes) for r in rows)


class TestSyncOrchestrator(FrappeTestCase):
	SHOW_TRANSACTION_COMMIT_WARNINGS = True

	def setUp(self):
		# after_migrate commits; the real role cleanup must never ride along on site miyano (test_cleanup covers it)
		patcher = patch.object(sync, "_cleanup_roles")
		self.cleanup = patcher.start()
		self.addCleanup(patcher.stop)

	def run_quiet(self, fn):
		out = io.StringIO()
		with redirect_stdout(out):
			fn()
		return out.getvalue()

	def test_disabled_is_noop(self):
		before = count("Custom DocPerm")
		with (
			patch.dict(frappe.conf, {"mvl_rbac_enabled": 0}),
			patch("erpnext.access.permissions.matrix.load_matrix") as load,
		):
			out = self.run_quiet(sync.run)
			out += self.run_quiet(sync.after_migrate)
		load.assert_not_called()
		self.assertIn("RBAC sync tắt", out)
		self.assertEqual(count("Custom DocPerm"), before)
		self.cleanup.assert_called_once_with()  # role cleanup runs on migrate even with the flag off

	def test_validation_error_stops_before_writes(self):
		with (
			patch.dict(frappe.conf, ENABLED),
			patch("erpnext.access.permissions.matrix.load_matrix", return_value=tiny_matrix()),
			patch.object(SiteInfo, "from_db", return_value=tiny_site()),
			patch("erpnext.access.permissions.validate.validate", return_value=Problems(errors=["boom"])),
			patch("erpnext.access.permissions.schema.ensure_schema") as ensure,
		):
			with self.assertRaises(frappe.ValidationError):
				self.run_quiet(sync.run)
		ensure.assert_not_called()

	def test_after_migrate_entry_does_not_raise_on_errors(self):
		before = count("Custom DocPerm")
		with (
			patch.dict(frappe.conf, ENABLED),
			patch("erpnext.access.permissions.matrix.load_matrix", return_value=tiny_matrix()),
			patch.object(SiteInfo, "from_db", return_value=tiny_site()),
			patch.object(frappe.db, "commit"),
			patch("erpnext.access.permissions.validate.validate", return_value=Problems(errors=["boom"])),
			patch("erpnext.access.permissions.schema.ensure_schema") as ensure,
			patch.object(frappe, "log_error") as log_error,
		):
			out = self.run_quiet(sync.after_migrate)
		ensure.assert_not_called()
		self.assertIn("boom", out)
		self.assertIn("RBAC sync bỏ qua, chưa ghi gì", out)
		self.assertEqual(count("Custom DocPerm"), before)
		log_error.assert_called_once()
		self.assertEqual(log_error.call_args.kwargs["title"], "RBAC sync")
		self.assertIn("boom", log_error.call_args.kwargs["message"])

	def test_after_migrate_swallows_write_failure_and_rolls_back(self):
		with (
			patch.dict(frappe.conf, ENABLED),
			patch("erpnext.access.permissions.matrix.load_matrix", return_value=tiny_matrix()),
			patch.object(SiteInfo, "from_db", return_value=tiny_site()),
			patch("erpnext.access.permissions.schema.ensure_schema", side_effect=RuntimeError("ddl")),
			patch.object(frappe.db, "commit"),
			patch.object(frappe.db, "rollback") as rollback,
			patch.object(frappe, "log_error") as log_error,
		):
			calls = MagicMock()
			calls.attach_mock(rollback, "rollback")
			calls.attach_mock(log_error, "log_error")
			out = self.run_quiet(sync.after_migrate)
		rollback.assert_called_once()
		self.assertIn("RuntimeError", out)
		self.assertFalse(frappe.flags.get("in_rbac_sync"))
		self.assertEqual([c[0] for c in calls.mock_calls], ["rollback", "log_error"])  # logged AFTER rollback
		self.assertEqual(log_error.call_args.kwargs["title"], "RBAC sync")
		self.assertIn("RuntimeError: ddl", log_error.call_args.kwargs["message"])

	def test_after_migrate_survives_a_failing_error_log(self):
		with (
			patch.dict(frappe.conf, ENABLED),
			patch("erpnext.access.permissions.matrix.load_matrix", return_value=tiny_matrix()),
			patch.object(SiteInfo, "from_db", return_value=tiny_site()),
			patch("erpnext.access.permissions.schema.ensure_schema", side_effect=RuntimeError("ddl")),
			patch.object(frappe.db, "commit"),
			patch.object(frappe.db, "rollback"),
			patch.object(frappe, "log_error", side_effect=RuntimeError("log down")),
		):
			out = self.run_quiet(sync.after_migrate)  # must not raise (R-20)
		self.assertIn("log down", out)

	def test_full_run_on_tiny_matrix_writes_and_resets_flag(self):
		seen = []
		with (
			patch.dict(frappe.conf, ENABLED),
			patch("erpnext.access.permissions.matrix.load_matrix", return_value=tiny_matrix()),
			patch.object(SiteInfo, "from_db", return_value=tiny_site()),
			patch(
				"erpnext.access.permissions.schema.ensure_schema",
				side_effect=lambda m: seen.append(frappe.flags.in_rbac_sync),
			),
		):
			out = self.run_quiet(sync.run)
		self.assertEqual(seen, [True])
		self.assertFalse(frappe.flags.in_rbac_sync)
		self.assertIn("RBAC sync xong", out)
		self.assertTrue(frappe.db.exists("Custom DocPerm", {"parent": DT, "role": "Purchase User"}))

	def test_after_migrate_commits_before_any_step(self):
		calls = []
		with (
			patch.dict(frappe.conf, ENABLED),
			patch("erpnext.access.permissions.matrix.load_matrix", return_value=tiny_matrix()),
			patch.object(SiteInfo, "from_db", return_value=tiny_site()),
			patch.object(frappe.db, "commit", side_effect=lambda: calls.append("commit")),
			patch.object(frappe.db, "rollback"),
			patch(
				"erpnext.access.permissions.schema.ensure_schema",
				side_effect=lambda m: calls.append("ensure_schema")
				or (_ for _ in ()).throw(RuntimeError("stop")),
			),
			patch.object(frappe, "log_error"),
		):
			self.run_quiet(sync.after_migrate)
		self.assertEqual(calls, ["commit", "ensure_schema"])

	def test_run_does_not_commit(self):
		with (
			patch.dict(frappe.conf, ENABLED),
			patch("erpnext.access.permissions.matrix.load_matrix", return_value=tiny_matrix()),
			patch.object(SiteInfo, "from_db", return_value=tiny_site()),
			patch.object(frappe.db, "commit") as commit,
			patch("erpnext.access.permissions.schema.ensure_schema"),
		):
			self.run_quiet(sync.run)
		commit.assert_not_called()

	def test_after_migrate_has_sync_last(self):
		self.assertEqual(
			frappe.get_hooks("after_migrate", app_name="erpnext")[-1],
			"erpnext.access.permissions.sync.after_migrate",
		)


class TestUserScope(FrappeTestCase):
	SHOW_TRANSACTION_COMMIT_WARNINGS = True

	def matrix(self, scope):
		m = small_matrix()
		m.user_permission_rules = {
			"Warehouse": WAREHOUSE_RULE,
			"Price List": {"roles": ["PU"], "apply_to_all": 1},
			"_remove_allow": ["Employee", "Department", "Company"],
		}
		m.user_scope = scope
		return m

	def test_user_permission_from_scope(self):
		user = make_user("Stock User")
		m = self.matrix({user: {"Warehouse": ["Stores - M"]}})
		result = sync_user_permissions(m)
		self.assertEqual(result["inserted"], 2)
		self.assertEqual(
			permissions_of(user, "Warehouse"),
			[("Stores - M", "Pick List", 0), ("Stores - M", "Stock Entry", 0)],
		)
		self.assertEqual(sync_user_permissions(m)["inserted"], 0)  # idempotent

	def test_scope_change_removes_stale_rows(self):
		user = make_user("Stock User")
		sync_user_permissions(self.matrix({user: {"Warehouse": ["Stores - M"]}}))
		sync_user_permissions(self.matrix({user: {"Warehouse": []}}))
		self.assertEqual(permissions_of(user, "Warehouse"), [])

	def test_user_without_the_role_gets_nothing(self):
		user = make_user("Sales User")
		sync_user_permissions(self.matrix({user: {"Warehouse": ["Stores - M"]}}))
		self.assertEqual(permissions_of(user, "Warehouse"), [])

	def test_apply_to_all_rule(self):
		user = make_user("Purchase User")
		sync_user_permissions(self.matrix({user: {"Price List": ["Standard Buying"]}}))
		rows = permissions_of(user, "Price List")
		self.assertEqual([(r[1], r[2]) for r in rows], [(None, 1)])

	def test_removes_company_user_permissions(self):
		# Company stands in for Employee/Department: same _remove_allow code path, no heavy Employee fixture.
		user = make_user("Stock User")
		frappe.get_doc(
			{"doctype": "User Permission", "user": user, "allow": "Company", "for_value": "Miyano"}
		).insert(ignore_permissions=True)
		self.assertEqual(len(permissions_of(user, "Company")), 1)
		sync_user_permissions(self.matrix({}))
		self.assertEqual(permissions_of(user, "Company"), [])

	def test_missing_scope_value_is_skipped_and_audited(self):
		user = make_user("Stock User")
		ghost = "No Such Warehouse " + frappe.generate_hash(length=6)
		audit_lines = []
		sync_user_permissions(self.matrix({user: {"Warehouse": [ghost, "Stores - M"]}}), audit_lines)
		self.assertEqual({r[0] for r in permissions_of(user, "Warehouse")}, {"Stores - M"})
		self.assertEqual(audit_lines, [f"{user} — Warehouse {ghost} không tồn tại, bỏ qua"])

	def test_fixed_values_rule_applies_to_holder_not_in_scope(self):
		user = make_user("MVL Kho PDA")
		m = self.matrix({})
		m.user_permission_rules = {
			"Stock Entry Type": {
				"roles": ["PDA"],
				"apply_to_all": 0,
				"applicable_for": ["Stock Entry"],
				"values": ["Material Transfer"],
			}
		}
		with patch("erpnext.access.permissions.user_scope._holders", return_value=[user]):
			sync_user_permissions(m)
		self.assertEqual(permissions_of(user, "Stock Entry Type"), [("Material Transfer", "Stock Entry", 0)])

	def test_unlisted_users_are_left_alone_and_reported(self):
		user = make_user("Stock User")
		frappe.get_doc(
			{
				"doctype": "User Permission",
				"user": user,
				"allow": "Warehouse",
				"for_value": "Stores - M",
				"apply_to_all_doctypes": 1,
			}
		).insert(ignore_permissions=True)
		m = self.matrix({})
		sync_user_permissions(m)
		self.assertEqual(len(permissions_of(user, "Warehouse")), 1)
		self.assertIn(user, users_without_scope(m))


class TestAudit(FrappeTestCase):
	SHOW_TRANSACTION_COMMIT_WARNINGS = True

	def test_run_audit_is_read_only_and_returns_lines(self):
		m = load_matrix()
		before = {
			dt: count(dt) for dt in ("User Permission", "Custom DocPerm", "Role Profile", "Custom Role")
		}
		lines = audit.run_audit(m, tiny_site())
		self.assertTrue(all(isinstance(line, str) for line in lines))
		self.assertEqual(before, {dt: count(dt) for dt in before})

	def test_r22_single_root_is_accepted(self):
		one = [frappe._dict(name="E1", reports_to=None), frappe._dict(name="E2", reports_to="E1")]
		self.assertEqual(audit.employees_without_reports_to(one), [])
		self.assertIn(
			"vòng", audit.employees_without_reports_to([frappe._dict(name="E1", reports_to="E2")])[0]
		)
		two = [frappe._dict(name="E1", reports_to=None), frappe._dict(name="E2", reports_to=None)]
		self.assertIn("thiếu reports_to", audit.employees_without_reports_to(two)[0])

	def test_undeclared_permlevel_fields(self):
		site = SiteInfo(
			doctypes={
				DT: DocTypeInfo(
					name=DT,
					app="erpnext",
					module="Buying",
					is_submittable=False,
					issingle=False,
					high_permlevel_fields=frozenset({"a", "b"}),
				)
			}
		)
		m = small_matrix(doctypes={DT: DocTypeEntry(state="matrix", permlevel={1: {"fields": ["a"]}})})
		lines = audit.undeclared_permlevel_fields(m, site)
		self.assertEqual(len(lines), 1)
		self.assertIn(f"{DT}.b", lines[0])
		self.assertNotIn(f"{DT}.a", lines[0])

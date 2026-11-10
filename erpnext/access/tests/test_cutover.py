"""Cutover (spec 12 Bước 4/6). On site miyano the write paths run on throwaway objects only; real-data
writes sit behind ``require_test_site``."""

import re
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.access.permissions import cutover
from erpnext.access.permissions.matrix import load_matrix
from erpnext.access.tests.helpers import require_test_site

WRITE_SQL = re.compile(r"^\s*(update|delete|insert|replace|alter|create|drop)\b", re.I)
SNAPSHOT_SQL = (
	"select count(*) from `tabHas Role`",
	"select count(*) from `tabRole` where disabled = 1",
	"select count(*) from `tabRole Profile`",
	"select count(*) from `tabUser Type`",
	"select ifnull(workflow_state, ''), docstatus, count(*) from `tabSales Order` group by 1, 2",
	"select name, is_active from `tabWorkflow` order by name",
)


def snapshot():
	return [frappe.db.sql(q) for q in SNAPSHOT_SQL]


def plain(lines):
	return [line for line in lines if line.startswith(("done:", "[dry-run]"))]


class TestCutover(FrappeTestCase):
	SHOW_TRANSACTION_COMMIT_WARNINGS = True

	def setUp(self):
		frappe.db.savepoint("cutover_test")  # FrappeTestCase only rolls back per class

	def tearDown(self):
		frappe.db.rollback(save_point="cutover_test")

	def make_role(self):
		name = f"ZZ-cut-{frappe.generate_hash(length=8)}"
		frappe.get_doc({"doctype": "Role", "role_name": name, "desk_access": 1}).insert()
		return name

	def make_user(self, role=None, profile=None):
		email = f"cut-{frappe.generate_hash(length=8)}@example.com"
		user = frappe.get_doc(
			{"doctype": "User", "email": email, "first_name": "Cut", "send_welcome_email": 0}
		)
		if role:
			user.append("roles", {"role": role})
		user.insert(ignore_permissions=True)
		if profile:
			frappe.db.set_value("User", email, "role_profile_name", profile)
		return email

	# -- dry run -----------------------------------------------------------------------------

	def test_dry_run_on_real_data_writes_nothing(self):
		before = snapshot()
		real_sql = frappe.db.sql

		def guarded(query, *args, **kwargs):
			self.assertIsNone(WRITE_SQL.match(str(query)), query)
			return real_sql(query, *args, **kwargs)

		with (
			patch.object(frappe.db, "sql", side_effect=guarded),
			patch.object(frappe.db, "set_value") as set_value,
			patch.object(frappe.db, "delete") as delete,
			patch.object(frappe, "delete_doc") as delete_doc,
		):
			lines = cutover.run(dry_run=1)
		set_value.assert_not_called()
		delete.assert_not_called()
		delete_doc.assert_not_called()
		self.assertEqual(before, snapshot())
		self.assertTrue(lines)
		self.assertFalse([line for line in lines if line.startswith("done:")], lines)
		text = "\n".join(lines)
		self.assertIn("[dry-run] ", text)
		self.assertIn("'COO'", text)  # planned: disabled, never deleted
		self.assertTrue(frappe.db.exists("Role", "COO"))

	def test_run_defaults_to_dry_run(self):
		with patch.object(frappe.db, "set_value") as set_value, patch.object(frappe, "delete_doc") as dd:
			cutover.run()
		set_value.assert_not_called()
		dd.assert_not_called()

	# -- targets -----------------------------------------------------------------------------

	def test_default_targets(self):
		targets = cutover.default_targets(load_matrix())
		self.assertNotIn("Business Trip", targets)
		leave = targets["Leave Application"]
		self.assertEqual(leave["first"], "Đã duyệt")
		self.assertEqual(leave["cancelled"], "Đã hủy")
		self.assertEqual(leave["status_map"], {"Approved": "Đã duyệt", "Rejected": "Từ chối"})
		self.assertEqual(targets["Payment Entry"]["first"], "Đã ghi sổ")
		self.assertNotIn("Bank Account", {d for d, t in targets.items() if t["first"]})

	def test_leave_application_without_column_is_skipped(self):
		if frappe.db.has_column("Leave Application", "workflow_state"):
			self.skipTest("Leave Application đã có cột workflow_state")
		lines = cutover.remap_workflow_states(
			True, None, {"Leave Application": cutover.default_targets()["Leave Application"]}
		)
		self.assertEqual(lines, ["skip: Leave Application chưa có cột workflow_state"])

	# -- workflows (mocked: never touch a real Workflow on miyano) -----------------------------

	def test_retire_workflows(self):
		row = frappe._dict(is_active=1, document_type="Payment Entry")
		with (
			patch.object(
				frappe.db,
				"get_value",
				side_effect=lambda dt, n, f, **kw: row if f != "document_type" else "Sales Order",
			),
			patch.object(frappe.db, "set_value") as set_value,
			patch.object(frappe, "delete_doc") as delete_doc,
			patch.object(frappe.cache, "hdel") as hdel,
		):
			dry = cutover.retire_workflows(True)
			set_value.assert_not_called()
			delete_doc.assert_not_called()
			done = cutover.retire_workflows(False)
		self.assertEqual(len(dry), 2)
		self.assertTrue(all(line.startswith("[dry-run] ") for line in dry))
		self.assertTrue(all(line.startswith("done: ") for line in done))
		set_value.assert_called_once_with("Workflow", "MVL Duyệt thanh toán", "is_active", 0)
		delete_doc.assert_called_once_with("Workflow", "SO Test Workflow", force=1, ignore_permissions=True)
		self.assertEqual(hdel.call_count, 2)

	def test_retire_workflows_nothing_to_do(self):
		with patch.object(frappe.db, "get_value", return_value=None):
			self.assertEqual(cutover.retire_workflows(False), [])

	# -- remap on throwaway Bank Accounts ------------------------------------------------------

	def make_bank_account(self, label):
		bank = f"ZZ-bank-{frappe.generate_hash(length=6)}"
		frappe.get_doc({"doctype": "Bank", "bank_name": bank}).insert()
		doc = frappe.get_doc({"doctype": "Bank Account", "account_name": label, "bank": bank}).insert()
		return doc.name

	def test_remap_write_paths_and_idempotency(self):
		if frappe.db.count("Bank Account"):
			self.skipTest("site có Bank Account thật — test này cần bảng rỗng")
		tag = frappe.generate_hash(length=6)
		approved, rejected, cancelled, submitted, other = (
			self.make_bank_account(f"{tag}-ok"),
			self.make_bank_account(f"{tag}-no"),
			self.make_bank_account(f"{tag}-x"),
			self.make_bank_account(f"{tag}-s"),
			self.make_bank_account(f"{tag}-o"),
		)
		for name, docstatus in ((approved, 1), (rejected, 1), (cancelled, 2), (submitted, 1), (other, 0)):
			frappe.db.set_value("Bank Account", name, "docstatus", docstatus)
		targets = {
			"Bank Account": {
				"first": "Chốt",
				"cancelled": "Đã hủy",
				"status_field": "account_name",
				"status_map": {f"{tag}-ok": "Đã duyệt", f"{tag}-no": "Từ chối"},
			}
		}
		before = {n: frappe.db.get_value("Bank Account", n, "modified") for n in (approved, other)}

		plan = cutover.remap_workflow_states(True, None, targets)
		self.assertEqual(len(plan), 4, plan)
		self.assertIsNone(frappe.db.get_value("Bank Account", approved, "workflow_state"))

		done = cutover.remap_workflow_states(False, None, targets)
		self.assertEqual(len(plain(done)), 4, done)
		state = lambda n: frappe.db.get_value("Bank Account", n, "workflow_state")  # noqa: E731
		self.assertEqual(state(approved), "Đã duyệt")
		self.assertEqual(state(rejected), "Từ chối")
		self.assertEqual(state(cancelled), "Đã hủy")
		self.assertEqual(state(submitted), "Chốt")
		self.assertNotIn(state(other), ("Chốt", "Đã hủy"))  # docstatus 0 untouched
		for name, modified in before.items():  # remap never bumps `modified`
			self.assertEqual(frappe.db.get_value("Bank Account", name, "modified"), modified)

		self.assertEqual(plain(cutover.remap_workflow_states(False, None, targets)), [])

	def test_approved_bank_accounts(self):
		if frappe.db.count("Bank Account"):
			self.skipTest("site có Bank Account thật")
		name = self.make_bank_account(f"ok-{frappe.generate_hash(length=6)}")
		lines = cutover.remap_workflow_states(True, [name, "không-có"], {})
		self.assertEqual(len(lines), 2)
		self.assertTrue(lines[1].startswith("skip: "))
		self.assertNotEqual(frappe.db.get_value("Bank Account", name, "workflow_state"), "Đã duyệt")
		cutover.remap_workflow_states(False, [name], {})
		self.assertEqual(frappe.db.get_value("Bank Account", name, "workflow_state"), "Đã duyệt")
		self.assertEqual(plain(cutover.remap_workflow_states(False, [name], {})), [])

	# -- retire on throwaway roles / profiles --------------------------------------------------

	def test_retire_role_write_path(self):
		role = self.make_role()
		email = self.make_user(role=role)
		kwargs = {"roles": [role], "profiles": [], "user_type": None}

		dry = cutover.retire_legacy(True, **kwargs)
		self.assertEqual(len(dry), 2)
		self.assertTrue(frappe.db.exists("Has Role", {"parent": email, "role": role}))
		self.assertEqual(frappe.db.get_value("Role", role, "disabled"), 0)

		done = cutover.retire_legacy(False, **kwargs)
		self.assertEqual(len(plain(done)), 2, done)
		self.assertFalse(frappe.db.exists("Has Role", {"parent": email, "role": role}))
		self.assertEqual(frappe.db.get_value("Role", role, "disabled"), 1)
		self.assertTrue(frappe.db.exists("Role", role))  # disabled, never deleted

		self.assertEqual(cutover.retire_legacy(False, **kwargs), [])

	def test_missing_role_is_silent(self):
		self.assertEqual(cutover.retire_legacy(False, roles=["ZZ-không-có"], profiles=[], user_type=None), [])

	def test_profile_with_users_is_kept(self):
		role = self.make_role()
		held, free = (f"ZZ-prof-{frappe.generate_hash(length=6)}" for _ in range(2))
		for name in (held, free):
			frappe.get_doc(
				{"doctype": "Role Profile", "role_profile": name, "roles": [{"role": role}]}
			).insert()
		self.make_user(profile=held)
		kwargs = {"roles": [], "profiles": [held, free, "ZZ-vắng"], "user_type": None}

		dry = cutover.retire_legacy(True, **kwargs)
		self.assertEqual(
			sorted(dry), sorted([f"skip: {held} còn user", f"[dry-run] xóa Role Profile '{free}'"])
		)
		self.assertTrue(frappe.db.exists("Role Profile", free))

		done = cutover.retire_legacy(False, **kwargs)
		self.assertIn(f"skip: {held} còn user", done)
		self.assertIn(f"done: xóa Role Profile '{free}'", done)
		self.assertTrue(frappe.db.exists("Role Profile", held))
		self.assertFalse(frappe.db.exists("Role Profile", free))

	def test_user_type_dropped_only_when_unused(self):
		with (
			patch.object(frappe.db, "exists", return_value=True),
			patch.object(frappe.db, "count", return_value=0),
			patch.object(frappe, "delete_doc") as delete_doc,
		):
			self.assertEqual(len(cutover._drop_user_type(True, "X")), 1)
			delete_doc.assert_not_called()
			self.assertTrue(cutover._drop_user_type(False, "X")[0].startswith("done: "))
			delete_doc.assert_called_once_with("User Type", "X", force=1, ignore_permissions=True)
		with (
			patch.object(frappe.db, "exists", return_value=True),
			patch.object(frappe.db, "count", return_value=2),
			patch.object(frappe, "delete_doc") as delete_doc,
		):
			self.assertEqual(cutover._drop_user_type(False, "X"), ["skip: User Type X còn 2 user"])
			delete_doc.assert_not_called()

	def test_default_lists_cover_spec(self):
		m = load_matrix()
		self.assertIn("COO", m.rules["retired_roles"])
		self.assertIn("Employee Self Service", m.rules["retired_roles"])
		self.assertEqual(len(cutover.OLD_ERP_PROFILES), 6)

	# -- real data (test site only) --------------------------------------------------------------

	def test_real_cutover_t35(self):
		require_test_site(self)
		lines = cutover.run(dry_run=0)
		self.assertTrue(lines)
		self.assertEqual(frappe.db.get_value("Role", "COO", "disabled"), 1)
		self.assertTrue(frappe.db.exists("Role", "COO"))
		self.assertFalse(frappe.db.exists("User Type", "Employee Self Service"))
		self.assertEqual(cutover.run(dry_run=0), ["Không có việc cần làm."])

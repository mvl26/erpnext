import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.access.permissions.docperm_sync import (
	PTYPES,
	desired_rows,
	managed_roles,
	sync_docperms,
)
from erpnext.access.permissions.expand import PermRow
from erpnext.access.permissions.matrix import DocTypeEntry
from erpnext.access.permissions.site import DocTypeInfo, SiteInfo
from erpnext.access.tests.helpers import small_matrix

# Only rarely used DocTypes are written to — the Redis meta cache is shared with the live web workers.
PERIOD = "Supplier Scorecard Period"
STANDING = "Supplier Scorecard Standing"
TOUCHED = (PERIOD, STANDING)
FOREIGN = "AssetCore Auditor"


def info(name, app="erpnext"):
	return DocTypeInfo(name=name, app=app, module="X", is_submittable=False, issingle=False)


def site_for(*names, app="erpnext"):
	return SiteInfo(doctypes={n: info(n, app) for n in names})


def row(role, level, ptypes, if_owner=False):
	return PermRow(role, level, frozenset(ptypes.split()), if_owner)


def custom_rows(doctype):
	"""Custom DocPerm rows of a DocType as a sorted list of PermRow (duplicates kept)."""
	fields = ["role", "permlevel", "if_owner", *PTYPES]
	cdp = frappe.qb.DocType("Custom DocPerm")
	data = (
		frappe.qb.from_(cdp).select(*[cdp[f] for f in fields]).where(cdp.parent == doctype).run(as_dict=True)
	)
	return sorted(
		(PermRow(d.role, d.permlevel, frozenset(p for p in PTYPES if d[p]), bool(d.if_owner)) for d in data),
		key=lambda r: (r.role, r.permlevel, r.if_owner, sorted(r.ptypes)),
	)


def add_custom_row(doctype, role, ptypes, permlevel=0, if_owner=0):
	doc = {"doctype": "Custom DocPerm", "parent": doctype, "role": role, "permlevel": permlevel}
	doc["if_owner"] = if_owner
	doc.update({p: int(p in ptypes.split()) for p in PTYPES})
	frappe.get_doc(doc).insert(ignore_permissions=True)


class TestDocPermSync(FrappeTestCase):
	SHOW_TRANSACTION_COMMIT_WARNINGS = True

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		# New roles (3.1) are created by an earlier sync step; the class-scope rollback removes these.
		for name in managed_roles(small_matrix()) | {FOREIGN}:
			if not frappe.db.exists("Role", name):
				frappe.get_doc({"doctype": "Role", "role_name": name}).insert(ignore_permissions=True)

	@classmethod
	def tearDownClass(cls):
		super().tearDownClass()  # class-scope rollback first, then drop any cached meta built from test rows
		for dt in TOUCHED:
			frappe.clear_cache(doctype=dt)

	def setUp(self):
		# Per-test isolation: every test starts from the site's real Custom DocPerm state.
		frappe.db.savepoint("docperm_sync")
		for dt in TOUCHED:
			self.addCleanup(frappe.clear_cache, doctype=dt)
		self.addCleanup(frappe.db.rollback, save_point="docperm_sync")
		self.assertFalse(custom_rows(PERIOD), "site already has Custom DocPerm on the test DocType")

	def matrix(self, entry=None, rules=None):
		m = small_matrix(doctypes={PERIOD: entry or DocTypeEntry(state="matrix", perms={"PU": "R"})})
		if rules:
			m.rules = {**m.rules, **rules}
		return m

	def test_managed_roles(self):
		roles = managed_roles(small_matrix())
		self.assertTrue({"Purchase User", "MVL Viewer", "All", "Desk User", "COO", "Thủ kho"} <= roles)
		self.assertFalse({"Administrator", "Guest", FOREIGN} & roles)

	def test_writes_expanded_rows(self):
		m = self.matrix()
		c = sync_docperms(m, site_for(PERIOD))
		expected = sorted(desired_rows(m, PERIOD, info(PERIOD)), key=lambda r: (r.role, r.permlevel))
		self.assertEqual(custom_rows(PERIOD), expected)
		self.assertIn(row("Purchase User", 0, "read report"), expected)
		# the standard System Manager CRWD row was cut down to the G1 read
		self.assertIn(row("System Manager", 0, "read report"), expected)
		self.assertGreater(c["inserted"], 0)

	def test_keeps_external_role_row(self):
		add_custom_row(PERIOD, FOREIGN, "read write")
		add_custom_row(PERIOD, "All", "read")  # G10 — erpnext DocType, managed, goes
		add_custom_row(PERIOD, "Auditor", "read")  # retired role (3.3), managed, goes
		sync_docperms(self.matrix(), site_for(PERIOD))
		rows = custom_rows(PERIOD)
		self.assertIn(row(FOREIGN, 0, "read write"), rows)
		roles = {r.role for r in rows}
		self.assertNotIn("All", roles)
		self.assertNotIn("Auditor", roles)

	def test_second_run_changes_nothing(self):
		add_custom_row(PERIOD, FOREIGN, "read")
		add_custom_row(PERIOD, "Purchase User", "read write")  # wrong ptypes, updated
		add_custom_row(PERIOD, "MVL Viewer", "read print report")  # duplicate key, one is dropped
		add_custom_row(PERIOD, "MVL Viewer", "read print report")
		m, site = self.matrix(), site_for(PERIOD)
		first = sync_docperms(m, site)
		self.assertGreater(first["deleted"], 0)
		after_first = custom_rows(PERIOD)
		c = sync_docperms(m, site)
		self.assertEqual((c["inserted"], c["deleted"]), (0, 0))
		self.assertEqual(custom_rows(PERIOD), after_first)
		self.assertEqual(len([r for r in after_first if r.role == "MVL Viewer"]), 1)

	def test_second_run_from_standard_changes_nothing(self):
		m, site = self.matrix(), site_for(PERIOD)
		sync_docperms(m, site)
		c = sync_docperms(m, site)
		self.assertEqual((c["inserted"], c["deleted"]), (0, 0))

	def test_empty_desired_stays_locked(self):
		# A g1 exception with no cells wants no row at all; an empty Custom DocPerm set would fall back
		# to the standard DocPerm, so the DocType must stay locked and the next run must be a no-op.
		m = self.matrix(DocTypeEntry(state="matrix"), rules={"g1_exceptions": [PERIOD]})
		site = site_for(PERIOD)
		self.assertEqual(desired_rows(m, PERIOD, info(PERIOD)), [])
		sync_docperms(m, site)
		self.assertTrue(custom_rows(PERIOD))
		self.assertFalse([r for r in custom_rows(PERIOD) if r.ptypes])
		c = sync_docperms(m, site)
		self.assertEqual((c["inserted"], c["deleted"]), (0, 0))

	def test_keep_standard_without_custom_rows_does_nothing(self):
		m = small_matrix(doctypes={STANDING: DocTypeEntry(state="keep_standard")})
		self.assertFalse(custom_rows(STANDING))
		c = sync_docperms(m, site_for(STANDING))
		self.assertEqual((c["inserted"], c["deleted"]), (0, 0))
		self.assertFalse(custom_rows(STANDING))

	def test_keep_standard_restores_standard_rows(self):
		add_custom_row(STANDING, "System Manager", "read")  # edited standard row, put back
		add_custom_row(STANDING, "Purchase User", "read")  # managed, not in standard, goes
		add_custom_row(STANDING, FOREIGN, "read")  # foreign, stays
		m = small_matrix(doctypes={STANDING: DocTypeEntry(state="keep_standard")})
		sync_docperms(m, site_for(STANDING))
		rows = custom_rows(STANDING)
		sm = [r for r in rows if r.role == "System Manager"]
		self.assertEqual(len(sm), 1)
		self.assertTrue({"read", "write", "create", "delete"} <= sm[0].ptypes)
		self.assertNotIn("Purchase User", {r.role for r in rows})
		self.assertIn(row(FOREIGN, 0, "read"), rows)
		c = sync_docperms(m, site_for(STANDING))
		self.assertEqual((c["inserted"], c["deleted"]), (0, 0))

	def test_keep_standard_rows_copies_named_role(self):
		m = small_matrix(
			doctypes={PERIOD: DocTypeEntry(state="matrix", keep_standard_rows=["System Manager"])}
		)
		rows = desired_rows(m, PERIOD, info(PERIOD))
		sm = [r for r in rows if r.role == "System Manager"]
		self.assertEqual(len(sm), 1)
		self.assertTrue({"read", "write", "create", "delete"} <= sm[0].ptypes)

	def test_contact_gets_no_all_row(self):
		# Pure — writing perms on Contact would leak into the live site's shared meta cache.
		m = small_matrix(doctypes={"Contact": DocTypeEntry(state="matrix", perms={"SU": "CRW"})})
		rows = desired_rows(m, "Contact", info("Contact", app="frappe"))
		self.assertNotIn("All", {r.role for r in rows})
		self.assertIn(row("Sales User", 0, "create read write report"), rows)

	def test_user_keeps_desk_user_select(self):
		m = small_matrix(doctypes={"User": DocTypeEntry(state="matrix", perms={"SYS": "CRW W1"})})
		rows = desired_rows(m, "User", info("User", app="frappe"))
		self.assertIn(row("Desk User", 0, "select"), rows)
		self.assertIn(row("System Manager", 1, "read write"), rows)

	def test_erpnext_doctype_gets_no_auto_role_rows(self):
		m = small_matrix(doctypes={"User": DocTypeEntry(state="matrix", perms={"SYS": "CRW W1"})})
		rows = desired_rows(m, "User", info("User", app="erpnext"))
		self.assertFalse({"All", "Desk User"} & {r.role for r in rows})

	def test_permission_effective(self):
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": f"rbac-sync-{frappe.generate_hash(length=8)}@example.com",
				"first_name": "RBAC Sync",
				"send_welcome_email": 0,
				"roles": [{"role": "Purchase User"}],
			}
		).insert(ignore_permissions=True)
		sync_docperms(self.matrix(), site_for(PERIOD))
		frappe.clear_cache(doctype=PERIOD)
		frappe.local.role_permissions = {}
		self.assertTrue(frappe.has_permission(PERIOD, "read", user=user.name))
		self.assertFalse(frappe.has_permission(PERIOD, "create", user=user.name))

from frappe.tests.utils import FrappeTestCase

from erpnext.access.permissions.expand import PermRow, data_import_rows, expand_doctype
from erpnext.access.permissions.matrix import DocTypeEntry
from erpnext.access.permissions.site import DocTypeInfo
from erpnext.access.tests.helpers import small_matrix


def info(name, submittable=0, single=0):
	return DocTypeInfo(
		name=name, app="erpnext", module="X", is_submittable=bool(submittable), issingle=bool(single)
	)


def row(role, level, ptypes, if_owner=False):
	return PermRow(role, level, frozenset(ptypes.split()), if_owner)


class TestExpand(FrappeTestCase):
	SHOW_TRANSACTION_COMMIT_WARNINGS = True

	def setUp(self):
		self.m = small_matrix()

	def expand(self, name, **kw):
		return expand_doctype(self.m, name, info(name, **kw))

	def test_po_gets_g1_g2(self):
		rows = self.expand("Purchase Order", submittable=1)
		self.assertIn(row("MVL Approver", 0, "read write submit report"), rows)
		self.assertIn(row("System Manager", 0, "read report"), rows)
		self.assertIn(row("MVL Viewer", 0, "read print report"), rows)
		self.assertFalse([r for r in rows if r.permlevel == 1])

	def test_grievance_has_no_sys_vw(self):
		rows = self.expand("Employee Grievance")
		roles = {r.role for r in rows}
		self.assertNotIn("System Manager", roles)
		self.assertNotIn("MVL Viewer", roles)
		self.assertIn(row("HR Manager", 0, "create read write report"), rows)

	def test_ref_master_gives_emp_and_pda_read(self):
		rows = self.expand("Company")
		self.assertIn(row("Employee", 0, "read report"), rows)
		self.assertIn(row("MVL Kho PDA", 0, "read report"), rows)
		self.assertIn(row("Accounts Manager", 0, "read write report"), rows)

	def test_salary_slip_vw_reads_level1(self):
		rows = self.expand("Salary Slip", submittable=1)
		self.assertIn(row("MVL Viewer", 1, "read"), rows)
		self.assertIn(row("HR Manager", 1, "read write"), rows)
		self.assertIn(row("Employee", 1, "read"), rows)

	def test_g2_salary_doctype_gets_level1_for_ap(self):
		self.m.doctypes["Salary Structure Assignment"] = DocTypeEntry(state="matrix", perms={"HM": "CRWS"})
		rows = self.expand("Salary Structure Assignment", submittable=1)
		self.assertIn(row("MVL Approver", 0, "read write submit report"), rows)
		self.assertIn(row("MVL Approver", 1, "read"), rows)

	def test_g2_merges_with_explicit_ap_cell(self):
		self.m.doctypes["Payment Entry"] = DocTypeEntry(state="matrix", perms={"AP": "RP"})
		rows = self.expand("Payment Entry", submittable=1)
		aps = [r for r in rows if r.role == "MVL Approver" and r.permlevel == 0]
		self.assertEqual(aps, [row("MVL Approver", 0, "read write submit print report")])

	def test_g2_skipped_for_g1_only(self):
		self.m.doctypes["Job Offer"] = DocTypeEntry(state="g1_only")
		rows = self.expand("Job Offer", submittable=1)
		self.assertNotIn("MVL Approver", {r.role for r in rows})

	def test_g1_only_gets_just_g1(self):
		rows = self.expand("BOM", submittable=1)
		self.assertEqual({r.role for r in rows}, {"System Manager", "MVL Viewer"})

	def test_keep_standard_returns_nothing(self):
		self.assertEqual(self.expand("ToDo"), [])

	def test_report_only_at_level_zero(self):
		rows = self.expand("Salary Slip", submittable=1)
		for r in rows:
			if r.permlevel > 0:
				self.assertNotIn("report", r.ptypes)

	def test_vw_r1_extra(self):
		self.m.doctypes["Bin"] = DocTypeEntry(state="g1_only")
		self.assertIn(row("MVL Viewer", 1, "read"), self.expand("Bin"))

	def test_owner_scope_becomes_if_owner(self):
		rows = self.expand("Interview Feedback", submittable=1)
		self.assertIn(row("Employee", 0, "create read write submit report", True), rows)
		self.assertFalse([r for r in rows if r.role == "Employee" and not r.if_owner])

	def test_other_scope_does_not_change_rows(self):
		rows = self.expand("Salary Slip", submittable=1)
		self.assertTrue(all(not r.if_owner for r in rows))

	def test_data_import_rows_for_importers(self):
		rows = data_import_rows(self.m)
		for name in ("Purchase Manager", "Purchase Master Manager"):
			self.assertIn(row(name, 0, "create read write report", True), rows)
		self.assertNotIn("Purchase User", {r.role for r in rows})

	def test_expand_data_import_includes_importers(self):
		self.m.doctypes["Data Import"] = DocTypeEntry(state="matrix", perms={"SYS": "CRWD"})
		rows = self.expand("Data Import")
		self.assertIn(row("Purchase Manager", 0, "create read write report", True), rows)
		self.assertIn(row("System Manager", 0, "create read write delete report"), rows)

	def test_expand_data_import_without_entry(self):
		del self.m.doctypes["Supplier"]
		self.m.doctypes["Supplier"] = DocTypeEntry(state="matrix", perms={"PM": "I"})
		rows = self.expand("Data Import")
		self.assertIn(row("Purchase Manager", 0, "create read write report", True), rows)

	def test_manager_code_expands_to_both_roles(self):
		rows = self.expand("Purchase Order", submittable=1)
		pm = {r.role for r in rows if "submit" in r.ptypes and r.role.startswith("Purchase")}
		self.assertEqual(pm, {"Purchase Manager", "Purchase Master Manager"})

	def test_rows_are_deduplicated(self):
		rows = self.expand("Purchase Order", submittable=1)
		keys = [(r.role, r.permlevel, r.if_owner) for r in rows]
		self.assertEqual(len(keys), len(set(keys)))

import json
import tempfile
from pathlib import Path

from frappe.tests.utils import FrappeTestCase

from erpnext.access.permissions.cells import MatrixError
from erpnext.access.permissions.matrix import load_matrix
from erpnext.access.permissions.site import SiteInfo


class TestMatrix(FrappeTestCase):
	SHOW_TRANSACTION_COMMIT_WARNINGS = True

	def _dir(self, files: dict) -> Path:
		tmp = tempfile.TemporaryDirectory()
		self.addCleanup(tmp.cleanup)
		for name, data in files.items():
			(Path(tmp.name) / name).write_text(json.dumps(data))
		return Path(tmp.name)

	def test_duplicate_doctype_across_fragments_raises(self):
		d = self._dir(
			{
				"a.json": {"doctypes": {"Lead": {"state": "matrix"}}},
				"b.json": {"doctypes": {"Lead": {"state": "matrix"}}},
			}
		)
		with self.assertRaises(MatrixError) as ctx:
			load_matrix(d)
		self.assertIn("a.json", str(ctx.exception))
		self.assertIn("b.json", str(ctx.exception))

	def test_unknown_top_level_key_raises(self):
		self.assertRaises(MatrixError, load_matrix, self._dir({"a.json": {"bogus": {}}}))

	def test_partial_fragments_and_defaults(self):
		d = self._dir(
			{
				"a.json": {"doctypes": {"Lead": {"state": "matrix", "permlevel": {"1": {"fields": ["x"]}}}}},
				"b.json": {"reports": {"R1": ["PU"]}, "rules": {"k": 1}},
			}
		)
		m = load_matrix(d)
		e = m.doctypes["Lead"]
		self.assertEqual(
			(e.perms, e.scope, e.workflow, e.keep_standard_rows, e.pda), ({}, {}, None, [], False)
		)
		self.assertEqual(e.permlevel, {1: {"fields": ["x"]}})
		self.assertEqual(m.reports, {"R1": ["PU"]})
		self.assertEqual(m.roles, {})

	def test_duplicate_rules_key_raises(self):
		d = self._dir({"a.json": {"rules": {"k": 1}}, "b.json": {"rules": {"k": 2}}})
		self.assertRaises(MatrixError, load_matrix, d)

	def test_profiles_expand_packs(self):
		m = load_matrix()
		self.assertEqual(set(m.profile_roles("RP-KHO-TK")), {"Employee", "Projects User", "Stock User"})
		self.assertIn("Purchase Master Manager", m.profile_roles("RP-MH-TP"))
		self.assertEqual(m.profile_roles("RP-KHO-PDA"), ["MVL Kho PDA"])
		self.assertEqual(m.roles["LK"].desk_access, 0)
		self.assertTrue(m.roles["IC"].is_new)
		self.assertFalse(m.roles["PU"].is_new)
		self.assertEqual(m.role_names("SM"), ("Sales Manager", "Sales Master Manager"))
		self.assertEqual(len(m.role_profiles), 20)
		self.assertEqual(m.combined_profiles, [])


class TestSiteInfo(FrappeTestCase):
	SHOW_TRANSACTION_COMMIT_WARNINGS = True

	def test_from_db(self):
		s = SiteInfo.from_db()
		self.assertTrue(s.doctypes["Purchase Order"].is_submittable)
		self.assertNotIn("Asset Repair", s.doctypes)
		self.assertTrue(s.reports)

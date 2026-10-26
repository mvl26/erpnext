"""Coverage gate — the real matrix fragments must validate with zero errors against the real site."""

from frappe.tests.utils import FrappeTestCase

from erpnext.access.permissions.cells import parse_cell
from erpnext.access.permissions.matrix import load_matrix
from erpnext.access.permissions.site import SiteInfo
from erpnext.access.permissions.validate import validate

# DocTypes hooked by another access hook (not H8): H1 scopes Contract by party_type, not by [e]/[d].
OTHER_HOOK_OWNERS = {"Contract"}


class TestMatrixData(FrappeTestCase):
	SHOW_TRANSACTION_COMMIT_WARNINGS = True

	def test_real_matrix_has_no_errors(self):
		p = validate(load_matrix(), SiteInfo.from_db())
		self.assertEqual(p.errors, [], "\n".join(p.errors))

	def test_data_import_log_roles_match_importers(self):
		m = load_matrix()
		importers = {
			code
			for entry in m.doctypes.values()
			for code, cell in entry.perms.items()
			if any("import" in ptypes for ptypes in parse_cell(cell).values())
		}
		log_roles = set(m.doctypes["Data Import Log"].perms) - {"SYS"}
		self.assertEqual(log_roles, importers)

	def test_every_scoped_doctype_is_hooked(self):
		"""hooks.py lists H8 by hand (it must not import erpnext.access) — keep it equal to the matrix."""
		from erpnext import hooks
		from erpnext.access.scope import ref_fields

		fields = ref_fields()
		unresolved = sorted(dt for dt, field in fields.items() if field is None)
		self.assertEqual(unresolved, [], "DocType có [e]/[d] nhưng không có trường Employee/Department")
		scoped = set(fields)
		for name, method in (
			("has_permission", "erpnext.access.scope.has_permission"),
			("permission_query_conditions", "erpnext.access.scope.query_conditions"),
		):
			hooked = {dt for dt, value in getattr(hooks, name).items() if value == method}
			# DocTypes owned by another access hook, listed on purpose: H1 scopes Contract by party_type
			self.assertEqual(
				{dt for dt, value in getattr(hooks, name).items() if value != method} - OTHER_HOOK_OWNERS,
				set(),
				f"{name}: hook lạ ngoài danh sách",
			)
			self.assertEqual(sorted(scoped - hooked), [], f"{name}: thiếu DocType")
			self.assertEqual(sorted(hooked - scoped), [], f"{name}: thừa DocType")

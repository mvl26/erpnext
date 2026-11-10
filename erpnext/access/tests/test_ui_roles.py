import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.access.permissions.cells import MatrixError
from erpnext.access.permissions.matrix import load_matrix
from erpnext.access.permissions.profiles import sync_roles
from erpnext.access.permissions.site import SiteInfo
from erpnext.access.permissions.ui_roles import (
	sync_page_roles,
	sync_report_roles,
	sync_workspace_roles,
)
from erpnext.access.tests.helpers import small_matrix

REPORTS = {
	"BOM Explorer": "BOM",
	"Accounts Receivable": "Sales Invoice",
	"Stock Balance": "Stock Ledger Entry",
}


def custom_roles(field, name):
	rows = frappe.get_all("Custom Role", filters={field: name}, pluck="name")
	if not rows:
		return []
	return sorted(r.role for r in frappe.get_doc("Custom Role", rows[0]).roles)


def make_user(*roles):
	email = f"ui-roles-{frappe.generate_hash(length=8)}@example.com"
	user = frappe.get_doc(
		{"doctype": "User", "email": email, "first_name": "UI", "send_welcome_email": 0}
	).insert()
	user.add_roles(*roles)
	frappe.clear_cache(user=email)
	return email


def workspace_roles(name):
	return sorted(
		frappe.get_all("Has Role", filters={"parenttype": "Workspace", "parent": name}, pluck="role")
	)


class TestUiRoles(FrappeTestCase):
	SHOW_TRANSACTION_COMMIT_WARNINGS = True

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		sync_roles(load_matrix())
		cls.site = SiteInfo(reports=dict(REPORTS))
		cls.m = small_matrix()
		cls.m.reports = {"Accounts Receivable": ["SU"], "Stock Balance": ["AM", "PRU"]}
		cls.m.pages = {"lay-hang-pda": ["STU", "STM", "PDA"], "no-such-page-zz": ["EMP"]}
		cls.m.workspaces = {"Home": ["EMP"], "Doi Chieu Cong No": ["AU"], "No Such Workspace ZZ": ["EMP"]}
		cls.locked = sync_report_roles(cls.m, cls.site)

	@classmethod
	def tearDownClass(cls):
		super().tearDownClass()
		frappe.clear_cache()

	def setUp(self):
		super().setUp()
		sync_report_roles(self.m, self.site)  # tests share state; start each from the class matrix

	def test_unlisted_report_locked(self):
		self.assertEqual(custom_roles("report", "BOM Explorer"), ["MVL Khóa sửa"])
		self.assertEqual(self.locked, ["BOM Explorer"])

	def test_listed_report_opens_for_roles(self):
		self.assertEqual(custom_roles("report", "Accounts Receivable"), ["Sales User"])
		self.assertEqual(
			custom_roles("report", "Stock Balance"), ["Accounts Manager", "Prepared Report User"]
		)
		sales = make_user("Sales User")
		stock = make_user("Stock User")
		ar = frappe.get_doc("Report", "Accounts Receivable")
		sb = frappe.get_doc("Report", "Stock Balance")
		bom = frappe.get_doc("Report", "BOM Explorer")
		with self.set_user(sales):
			self.assertTrue(ar.is_permitted())
			self.assertFalse(bom.is_permitted())
		with self.set_user(stock):
			self.assertFalse(sb.is_permitted())

	def test_second_run_no_writes(self):
		sync_report_roles(self.m, self.site)  # tests share state; settle first
		before = frappe.db.sql("select name, modified from `tabCustom Role` order by name")
		self.assertEqual(sync_report_roles(self.m, self.site), self.locked)
		self.assertEqual(frappe.db.sql("select name, modified from `tabCustom Role` order by name"), before)

	def test_role_change_is_applied(self):
		m = small_matrix()
		m.reports = {"Accounts Receivable": ["SU", "SM"]}
		sync_report_roles(m, self.site)
		self.assertEqual(
			custom_roles("report", "Accounts Receivable"),
			["Sales Manager", "Sales Master Manager", "Sales User"],
		)
		sync_report_roles(self.m, self.site)
		self.assertEqual(custom_roles("report", "Accounts Receivable"), ["Sales User"])

	def test_page_roles(self):
		warnings = sync_page_roles(self.m)
		self.assertEqual(custom_roles("page", "lay-hang-pda"), ["MVL Kho PDA", "Stock Manager", "Stock User"])
		self.assertEqual(len(warnings), 2)
		self.assertTrue(any("no-such-page-zz" in w for w in warnings))
		self.assertTrue(any(w.startswith("lay-hang-pda — 11.8: role chuẩn System Manager") for w in warnings))
		self.assertEqual(sync_page_roles(self.m), warnings)
		with self.set_user(make_user("MVL Kho PDA")):
			self.assertTrue(frappe.get_doc("Page", "lay-hang-pda").is_permitted())

	def test_empty_role_list_refused(self):
		m = small_matrix()
		m.reports = {"Accounts Receivable": []}
		with self.assertRaises(MatrixError):
			sync_report_roles(m, self.site)
		self.assertEqual(custom_roles("report", "Accounts Receivable"), ["Sales User"])

	def test_listed_report_missing_on_site_warns(self):
		m = small_matrix()
		m.reports = {"No Such Report ZZ": ["SU"]}
		warnings = []
		sync_report_roles(m, self.site, warnings)
		self.assertEqual(len(warnings), 1)
		self.assertIn("No Such Report ZZ", warnings[0])

	def test_duplicate_custom_roles_collapsed(self):
		frappe.get_doc(
			{"doctype": "Custom Role", "report": "BOM Explorer", "roles": [{"role": "Sales User"}]}
		).insert()
		sync_report_roles(self.m, self.site)
		self.assertEqual(frappe.db.count("Custom Role", {"report": "BOM Explorer"}), 1)
		self.assertEqual(custom_roles("report", "BOM Explorer"), ["MVL Khóa sửa"])

	def test_duplicate_workspace_role_rows_collapsed(self):
		sync_workspace_roles(self.m)
		frappe.get_doc(
			{
				"doctype": "Has Role",
				"parenttype": "Workspace",
				"parentfield": "roles",
				"parent": "Home",
				"role": "Employee",
			}
		).db_insert()
		self.assertEqual(len(workspace_roles("Home")), 2)
		sync_workspace_roles(self.m)
		self.assertEqual(workspace_roles("Home"), ["Employee"])

	def test_unlisted_page_untouched(self):
		sync_page_roles(self.m)
		self.assertEqual(custom_roles("page", "team-updates"), [])

	def test_workspace_roles(self):
		warnings = sync_workspace_roles(self.m)
		self.assertEqual(workspace_roles("Home"), ["Employee"])
		self.assertEqual(workspace_roles("Doi Chieu Cong No"), ["Accounts User"])
		self.assertEqual(len(warnings), 1)
		self.assertIn("No Such Workspace ZZ", warnings[0])

	def test_workspace_second_run_no_writes(self):
		sync_workspace_roles(self.m)
		before = frappe.db.sql(
			"select name, idx from `tabHas Role` where parenttype='Workspace' order by name"
		)
		sync_workspace_roles(self.m)
		self.assertEqual(
			frappe.db.sql("select name, idx from `tabHas Role` where parenttype='Workspace' order by name"),
			before,
		)

	def test_unlisted_workspace_untouched(self):
		before = workspace_roles("Expense Claims")
		sync_workspace_roles(self.m)
		self.assertEqual(workspace_roles("Expense Claims"), before)

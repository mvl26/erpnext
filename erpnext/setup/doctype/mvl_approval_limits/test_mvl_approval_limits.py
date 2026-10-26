import frappe
from frappe.tests.utils import FrappeTestCase


class TestMVLApprovalLimits(FrappeTestCase):
	SHOW_TRANSACTION_COMMIT_WARNINGS = True

	def test_limits_are_currency_singles(self):
		meta = frappe.get_meta("MVL Approval Limits")
		self.assertTrue(meta.issingle)
		for name in ("h1", "h2", "h3"):
			self.assertEqual(meta.get_field(name).fieldtype, "Currency")
			self.assertTrue(meta.get_field(name).description)

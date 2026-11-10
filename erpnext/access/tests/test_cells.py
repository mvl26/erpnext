from frappe.tests.utils import FrappeTestCase

from erpnext.access.permissions.cells import PTYPE_BY_LETTER, MatrixError, parse_cell


class TestCells(FrappeTestCase):
	SHOW_TRANSACTION_COMMIT_WARNINGS = True

	def test_letters_and_levels(self):
		self.assertEqual(
			parse_cell("CRWS PE"),
			{0: frozenset({"create", "read", "write", "submit", "print", "email"})},
		)
		self.assertEqual(parse_cell("R R1"), {0: frozenset({"read"}), 1: frozenset({"read"})})
		self.assertEqual(parse_cell("CRW W1")[1], frozenset({"read", "write"}))

	def test_commas_and_blank(self):
		self.assertEqual(parse_cell("R, W"), {0: frozenset({"read", "write"})})
		self.assertEqual(parse_cell(""), {})
		self.assertEqual(parse_cell("R2"), {2: frozenset({"read"})})

	def test_unknown_letter_raises(self):
		self.assertRaises(MatrixError, parse_cell, "CRQ")
		self.assertRaises(MatrixError, parse_cell, "R3")

	def test_all_letters(self):
		self.assertEqual(len(PTYPE_BY_LETTER), 14)
		self.assertEqual(PTYPE_BY_LETTER["L"], "select")

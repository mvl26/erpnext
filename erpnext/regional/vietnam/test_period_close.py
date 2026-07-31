# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Tests for Vietnam kết chuyển 911 period close (khóa sổ cuối kỳ)."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from erpnext.regional.vietnam.setup import _acct
from erpnext.regional.vietnam.test_setup import make_vn_company


def _post_je(company, lines, posting_date):
	"""Submit a Journal Entry; P&L rows carry the company's default cost center."""
	cost_center = frappe.db.get_value("Company", company, "cost_center")
	je = frappe.new_doc("Journal Entry")
	je.company = company
	je.posting_date = posting_date
	for number, dr, cr in lines:
		je.append(
			"accounts",
			{
				"account": _acct(company, number),
				"debit_in_account_currency": dr,
				"credit_in_account_currency": cr,
				"cost_center": cost_center,
			},
		)
	je.flags.ignore_permissions = True
	je.insert()
	je.submit()
	return je


def _lines_by_number(entry):
	return {line["account_number"]: line for line in entry["lines"]}


class TestVietnamPeriodClosePreview(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = make_vn_company("_Test VN KC911", "TVKC")
		# July 2026: 1,000,000 revenue (511), 600,000 COGS (632) → profit 400,000.
		_post_je(cls.company, [("111", 1_000_000, 0), ("511", 0, 1_000_000)], "2026-07-05")
		_post_je(cls.company, [("632", 600_000, 0), ("111", 0, 600_000)], "2026-07-10")

	def test_preview_lists_closing_entries_and_result(self):
		from erpnext.regional.vietnam.period_close import ket_chuyen_911

		result = ket_chuyen_911(self.company, "2026-07", preview=1)
		self.assertTrue(result["ok"])
		self.assertEqual(flt(result["result"]), 400_000)

		income, expense, transfer = result["entries"]
		income_lines = _lines_by_number(income)
		self.assertEqual(flt(income_lines["511"]["debit"]), 1_000_000)
		self.assertEqual(flt(income_lines["911"]["credit"]), 1_000_000)
		expense_lines = _lines_by_number(expense)
		self.assertEqual(flt(expense_lines["632"]["credit"]), 600_000)
		self.assertEqual(flt(expense_lines["911"]["debit"]), 600_000)
		transfer_lines = _lines_by_number(transfer)
		self.assertEqual(flt(transfer_lines["911"]["debit"]), 400_000)
		self.assertEqual(flt(transfer_lines["4212"]["credit"]), 400_000)

	def test_preview_makes_no_writes(self):
		from erpnext.regional.vietnam.period_close import ket_chuyen_911

		before = frappe.db.count("Journal Entry", {"company": self.company})
		ket_chuyen_911(self.company, "2026-07", preview=1)
		self.assertEqual(frappe.db.count("Journal Entry", {"company": self.company}), before)

	def test_empty_period_previews_empty(self):
		from erpnext.regional.vietnam.period_close import ket_chuyen_911

		result = ket_chuyen_911(self.company, "2026-05", preview=1)
		self.assertTrue(result["ok"])
		self.assertEqual(result["entries"], [])
		self.assertEqual(flt(result["result"]), 0)

	def test_non_vn_company_is_guarded(self):
		from erpnext.regional.vietnam.period_close import ket_chuyen_911

		result = ket_chuyen_911("_Test Company", "2026-07", preview=1)
		self.assertFalse(result["ok"])


class TestVietnamPeriodCloseExecute(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = make_vn_company("_Test VN KC Exec", "TVKE")
		_post_je(cls.company, [("111", 1_000_000, 0), ("511", 0, 1_000_000)], "2026-07-05")
		_post_je(cls.company, [("632", 600_000, 0), ("111", 0, 600_000)], "2026-07-10")

	def test_execute_zeroes_911_locks_period_and_blocks_rerun(self):
		from erpnext.regional.vietnam.period_close import ket_chuyen_911
		from erpnext.regional.vietnam.utils import get_account_balances, sum_closing_by_prefix

		result = ket_chuyen_911(self.company, "2026-07", preview=0)
		self.assertTrue(result["ok"], result)
		self.assertEqual(len(result["journal_entries"]), 3)

		# 5xx–8xx and 911 all zero as of period end; result sits in 4212 (credit).
		balances = get_account_balances(self.company, "1900-01-01", "2026-07-31")
		self.assertEqual(flt(sum_closing_by_prefix(balances, ("5", "6", "7", "8", "9"))), 0)
		self.assertEqual(flt(sum_closing_by_prefix(balances, ("4212",))), -400_000)

		# The month is locked: posting into it is now blocked...
		self.assertRaises(
			frappe.ValidationError,
			_post_je,
			self.company,
			[("111", 1, 0), ("4211", 0, 1)],
			"2026-07-20",
		)
		# ...and a re-run is a structured no-op with no duplicate JEs.
		je_count = frappe.db.count("Journal Entry", {"company": self.company})
		rerun = ket_chuyen_911(self.company, "2026-07", preview=0)
		self.assertFalse(rerun["ok"])
		self.assertTrue(rerun["already_closed"])
		self.assertEqual(frappe.db.count("Journal Entry", {"company": self.company}), je_count)

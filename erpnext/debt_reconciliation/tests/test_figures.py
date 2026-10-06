# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Hàm tính số dùng chung — bảng 3.4 TKKT (T2, T12, T15, T22)."""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.debt_reconciliation import figures
from erpnext.debt_reconciliation.constants import DIR_CREDIT, DIR_DEBIT, DIR_ZERO
from erpnext.debt_reconciliation.tests.utils import account, get_company, make_party, post


def calc(party_type, d0, c0, d, c, l_open=0, l_period=0):
	return figures.compute(party_type, figures.signed_opening(party_type, d0, c0), d, c, l_open, l_period)


class TestFormula(FrappeTestCase):
	"""Thuần — không đụng DB."""

	def test_a_supplier_owed_with_interest(self):
		r = calc("Supplier", 30, 100, 40, 50, 0, 5)
		self.assertEqual((r.opening_principal, r.opening_direction), (70, DIR_CREDIT))
		self.assertEqual((r.closing_balance, r.balance_direction), (85, DIR_CREDIT))
		self.assertEqual(r.credit_in_period + 5, 55)  # PS Có in = C + L_ps
		self.assertFalse(r.interest_errors)

	def test_b_supplier_prepaid_blocks_interest(self):
		r = calc("Supplier", 60, 10, 0, 20)
		self.assertEqual((r.opening_principal, r.opening_direction), (50, DIR_DEBIT))
		self.assertEqual((r.closing_balance, r.balance_direction), (30, DIR_DEBIT))
		self.assertTrue(calc("Supplier", 60, 10, 0, 20, 0, 1).interest_errors)

	def test_c_customer_owed_with_interest(self):
		r = calc("Customer", 200, 50, 100, 80, 0, 10)
		self.assertEqual((r.opening_principal, r.opening_direction), (150, DIR_DEBIT))
		self.assertEqual(r.debit_in_period + 10, 110)  # PS Nợ in = D + L_ps
		self.assertEqual((r.closing_balance, r.balance_direction), (180, DIR_DEBIT))
		self.assertFalse(r.interest_errors)

	def test_d_customer_prepaid_blocks_opening_interest(self):
		r = calc("Customer", 0, 40, 10, 0)
		self.assertEqual((r.opening_principal, r.opening_direction), (40, DIR_CREDIT))
		self.assertEqual((r.closing_balance, r.balance_direction), (30, DIR_CREDIT))
		self.assertTrue(calc("Customer", 0, 40, 10, 0, 1, 0).interest_errors)

	def test_e_no_movement(self):
		r = calc("Customer", 0, 0, 0, 0)
		self.assertEqual((r.closing_balance, r.balance_direction), (0, DIR_ZERO))
		self.assertFalse(r.meets_d1)
		self.assertEqual(r.amount_in_words, "Không đồng")

	def test_opening_interest_adds_on_owed_side(self):
		r = calc("Supplier", 0, 100, 0, 0, 7, 0)
		self.assertEqual((r.closing_balance, r.balance_direction), (107, DIR_CREDIT))

	def test_negative_interest_rejected(self):
		self.assertTrue(calc("Customer", 100, 0, 0, 0, -1, 0).interest_errors)

	def test_never_negative(self):
		for pt in ("Supplier", "Customer"):
			for args in ((0, 500, 900, 0), (500, 0, 0, 900), (1, 2, 3, 4)):
				r = calc(pt, *args)
				for f in ("opening_principal", "debit_in_period", "credit_in_period", "closing_balance"):
					self.assertGreaterEqual(r[f], 0)
				self.assertNotIn("âm", r.amount_in_words)

	def test_amount_in_words_large(self):
		self.assertEqual(
			calc("Supplier", 0, 56_001_171_083, 0, 0).amount_in_words,
			"Năm mươi sáu tỷ không trăm lẻ một triệu một trăm bảy mươi mốt nghìn không trăm tám mươi ba đồng",
		)

	def test_to_signed_roundtrip(self):
		for pt in ("Supplier", "Customer"):
			for v in (-30, 0, 45):
				self.assertEqual(figures.to_signed(pt, abs(v), figures.direction_of(pt, v)), v)


class TestGLTotals(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = get_company("_Test DR Figures", "TDRF")
		cls.from_date, cls.to_date = "2026-03-01", "2026-03-31"

	def test_matches_gl_and_ignores_cancelled(self):
		supplier = make_party("Supplier")
		post(self.company, "Supplier", supplier, 0, 1_000_000, "2026-02-10")  # mua chịu kỳ trước
		post(self.company, "Supplier", supplier, 300_000, 0, "2026-03-05")  # trả tiền
		post(self.company, "Supplier", supplier, 0, 500_000, "2026-03-20")  # mua thêm
		post(self.company, "Supplier", supplier, 0, 999, "2026-04-02")  # sau kỳ
		cancelled = post(self.company, "Supplier", supplier, 0, 77_777, "2026-03-25")
		cancelled.cancel()

		r = figures.get_figures(self.company, "Supplier", supplier, self.from_date, self.to_date)
		self.assertEqual((r.opening_principal, r.opening_direction), (1_000_000, DIR_CREDIT))
		self.assertEqual((r.debit_in_period, r.credit_in_period), (300_000, 500_000))
		self.assertEqual((r.closing_balance, r.balance_direction), (1_200_000, DIR_CREDIT))

	def test_bulk_query_equals_single(self):
		c1, c2 = make_party("Customer"), make_party("Customer")
		post(self.company, "Customer", c1, 700_000, 0, "2026-02-15")
		post(self.company, "Customer", c1, 0, 300_000, "2026-03-20")
		post(self.company, "Customer", c2, 200_000, 0, "2026-03-12")
		bulk = figures.get_gl_totals(self.company, "Customer", self.from_date, self.to_date)
		for party in (c1, c2):
			single = figures.get_gl_totals(
				self.company, "Customer", self.from_date, self.to_date, party=party
			)
			self.assertEqual(bulk[party], single[party])
		self.assertEqual(
			figures.compute_from_totals("Customer", bulk[c1]).closing_balance,
			400_000,
		)


class TestChildAccounts(FrappeTestCase):
	"""T15: phát sinh trên TK con của 331 được cộng vào (D7)."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = get_company("_Test DR Child Acc", "TDRC")
		root = account(cls.company, "331")
		if not frappe.db.get_value("Account", root, "is_group"):
			frappe.db.set_value("Account", root, "is_group", 1)
		cls.children = []
		for number in ("3311", "3312"):
			existing = account(cls.company, number)
			if not existing:
				existing = (
					frappe.get_doc(
						{
							"doctype": "Account",
							"company": cls.company,
							"account_name": f"Phải trả NCC {number}",
							"account_number": number,
							"parent_account": root,
							"account_type": "Payable",
							"root_type": "Liability",
						}
					)
					.insert(ignore_permissions=True)
					.name
				)
			cls.children.append(existing)

	def test_group_account_expands_to_leaves(self):
		accounts = figures.get_party_accounts(self.company, "Supplier")
		self.assertEqual(sorted(accounts), sorted(self.children))

		supplier = make_party("Supplier")
		post(self.company, "Supplier", supplier, 0, 400_000, "2026-03-03", account_name=self.children[0])
		post(self.company, "Supplier", supplier, 0, 100_000, "2026-03-04", account_name=self.children[1])
		r = figures.get_figures(self.company, "Supplier", supplier, "2026-03-01", "2026-03-31")
		self.assertEqual(r.credit_in_period, 500_000)
		self.assertEqual((r.closing_balance, r.balance_direction), (500_000, DIR_CREDIT))


class TestSiblingChildAccounts(FrappeTestCase):
	"""Bố cục tài khoản trên production: 3311/3312 nằm dưới nhóm "Tài khoản phải trả",
	ngang hàng với 331 (lá) chứ không nằm dưới 331 — vẫn phải được quét theo số hiệu (D7).
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = get_company("_Test DR Figures", "TDRF")
		cls.root = account(cls.company, "331")
		parent = frappe.db.get_value("Account", cls.root, "parent_account")
		cls.siblings = []
		for number, name in (("3311", "Phải trả người bán ngắn hạn"), ("3312", "Trả trước cho người bán")):
			existing = account(cls.company, number)
			if not existing:
				existing = (
					frappe.get_doc(
						{
							"doctype": "Account",
							"company": cls.company,
							"account_name": name,
							"account_number": number,
							"parent_account": parent,
							"account_type": "Payable",
							"root_type": "Liability",
						}
					)
					.insert(ignore_permissions=True)
					.name
				)
			cls.siblings.append(existing)

	def test_sibling_accounts_found_by_number(self):
		self.assertEqual(
			sorted(figures.get_party_accounts(self.company, "Supplier")), sorted([self.root, *self.siblings])
		)

	def test_ledger_report_and_statement_agree(self):
		from erpnext.regional.report.so_chi_tiet_cong_no.so_chi_tiet_cong_no import execute

		supplier = make_party("Supplier")
		# mọi phát sinh nằm trên 3311/3312, 331 trống — đúng tình huống lỗi "toàn 0" trên production
		post(self.company, "Supplier", supplier, 0, 97_216_000, "2026-08-20", account_name=self.siblings[0])
		post(self.company, "Supplier", supplier, 1_894_000, 0, "2026-09-09", account_name=self.siblings[0])
		post(self.company, "Supplier", supplier, 0, 8_844_832, "2026-09-17", account_name=self.siblings[0])
		post(self.company, "Supplier", supplier, 5_000_000, 0, "2026-09-20", account_name=self.siblings[1])

		r = figures.get_figures(self.company, "Supplier", supplier, "2026-09-01", "2026-09-30")
		self.assertEqual((r.opening_principal, r.opening_direction), (97_216_000, DIR_CREDIT))
		self.assertEqual((r.debit_in_period, r.credit_in_period), (6_894_000, 8_844_832))
		self.assertEqual((r.closing_balance, r.balance_direction), (99_166_832, DIR_CREDIT))

		_, rows = execute(
			frappe._dict(
				company=self.company,
				from_date="2026-09-01",
				to_date="2026-09-30",
				party_type="Supplier",
				party=supplier,
			)
		)
		closing = next(row for row in rows if row.get("is_closing"))
		# sổ theo quy ước Nợ - Có của ERPNext: dư Có hiện âm
		self.assertEqual(-closing["balance"], r.closing_balance)

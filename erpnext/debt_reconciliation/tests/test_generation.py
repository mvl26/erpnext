# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Sinh biên bản: job, hộp thoại, lập tay (T1, T8, T19, T20, T23, R-b, R-d)."""

from datetime import date

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.debt_reconciliation import constants as C
from erpnext.debt_reconciliation import generation
from erpnext.debt_reconciliation.tests.utils import get_company, make_party, post

FROM, TO = "2026-03-01", "2026-03-31"
FIGURE_FIELDS = (
	"opening_principal",
	"opening_direction",
	"debit_in_period",
	"credit_in_period",
	"closing_balance",
	"balance_direction",
	"amount_in_words",
)


class TestGeneration(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = get_company("_Test DR Gen", "TDRG")

	def names_for(self, result, key, parties):
		return {r["party"] for r in result[key] if r["party"] in parties}

	def test_auto_generation_filters_d1_exclusion_and_is_idempotent(self):
		active = make_party("Supplier", reconciliation_email="ncc@example.com")
		settled = make_party("Supplier")  # có GL trước kỳ nhưng dư 0, không phát sinh trong kỳ
		excluded = make_party("Supplier", exclude_reconciliation=1)
		disabled = make_party("Supplier")
		post(self.company, "Supplier", active, 0, 500_000, "2026-03-10")
		post(self.company, "Supplier", settled, 0, 100_000, "2026-01-10")
		post(self.company, "Supplier", settled, 100_000, 0, "2026-02-10")
		post(self.company, "Supplier", excluded, 0, 200_000, "2026-03-11")
		post(self.company, "Supplier", disabled, 0, 300_000, "2026-02-11")
		frappe.db.set_value("Supplier", disabled, "disabled", 1)
		ours = {active, settled, excluded, disabled}

		first = generation.generate_for_period(self.company, FROM, TO, party_type="Supplier")
		self.assertEqual(self.names_for(first, "created", ours), {active})
		self.assertFalse(self.names_for(first, "failed", ours))

		doc = frappe.get_doc(C.DOCTYPE, next(r["name"] for r in first["created"] if r["party"] == active))
		self.assertEqual(doc.creation_source, C.SOURCE_AUTO)
		self.assertEqual(doc.status, C.STATUS_DRAFT)
		self.assertEqual((doc.closing_balance, doc.balance_direction), (500_000, C.DIR_CREDIT))
		self.assertEqual(doc.reconciliation_email, "ncc@example.com")
		self.assertEqual(str(doc.response_deadline), "2026-04-06")
		self.assertTrue(doc.figures_fetched_on)

		again = generation.generate_for_period(self.company, FROM, TO, party_type="Supplier")
		self.assertFalse(self.names_for(again, "created", ours))
		self.assertEqual(self.names_for(again, "existing", ours), {active})

	def test_manual_statement_matches_generated_figures(self):
		customer = make_party("Customer")
		post(self.company, "Customer", customer, 900_000, 0, "2026-02-05")
		post(self.company, "Customer", customer, 250_000, 0, "2026-03-05")
		post(self.company, "Customer", customer, 0, 400_000, "2026-03-25")

		manual = frappe.new_doc(C.DOCTYPE)
		manual.update(
			{
				"company": self.company,
				"party_type": "Customer",
				"party": customer,
				"from_date": FROM,
				"to_date": TO,
			}
		)
		manual.fetch_figures()
		manual.insert()
		self.assertEqual(manual.creation_source, C.SOURCE_MANUAL)
		manual_figures = {f: manual.get(f) for f in FIGURE_FIELDS}
		self.assertEqual((manual.closing_balance, manual.balance_direction), (750_000, C.DIR_DEBIT))

		# lập lại cùng kỳ → trả bản đang có, không tạo bản thứ hai (R-b)
		name, created = generation.build_statement(
			self.company, "Customer", customer, FROM, TO, C.SOURCE_AUTO
		)
		self.assertEqual((name, created), (manual.name, False))
		dup = frappe.new_doc(C.DOCTYPE)
		dup.update(
			{
				"company": self.company,
				"party_type": "Customer",
				"party": customer,
				"from_date": FROM,
				"to_date": TO,
			}
		)
		dup.fetch_figures()
		self.assertRaises(frappe.ValidationError, dup.insert)

		frappe.delete_doc(C.DOCTYPE, manual.name)
		name, created = generation.build_statement(
			self.company, "Customer", customer, FROM, TO, C.SOURCE_AUTO
		)
		self.assertTrue(created)
		auto = frappe.get_doc(C.DOCTYPE, name)
		self.assertEqual({f: auto.get(f) for f in FIGURE_FIELDS}, manual_figures)

	def test_dialog_generates_exactly_the_selected_parties(self):
		a, b = make_party("Customer"), make_party("Customer")
		idle = make_party("Customer")  # không đạt D1 nhưng người dùng chọn → vẫn tạo, có cảnh báo (R-d)
		post(self.company, "Customer", a, 100_000, 0, "2026-03-02")
		post(self.company, "Customer", b, 200_000, 0, "2026-03-03")

		result = generation.generate_statements(
			FROM, TO, "Customer", parties=[a, b, idle], company=self.company
		)
		self.assertFalse(result["queued"])
		self.assertEqual({r["party"] for r in result["created"]}, {a, b, idle})
		idle_doc = frappe.get_doc(C.DOCTYPE, next(r["name"] for r in result["created"] if r["party"] == idle))
		self.assertEqual(idle_doc.creation_source, C.SOURCE_MANUAL)
		self.assertIn("không có số dư", idle_doc.missing_party_warning)

		auto = generation.generate_for_period(self.company, FROM, TO, party_type="Customer")
		self.assertFalse(self.names_for(auto, "created", {a, b, idle}))
		self.assertEqual(self.names_for(auto, "existing", {a, b}), {a, b})

	def test_one_failing_party_does_not_block_others(self):
		good = make_party("Supplier")
		post(self.company, "Supplier", good, 0, 10_000, "2026-03-04")
		result = generation.generate_for_period(
			self.company, FROM, TO, party_type="Supplier", parties=[good, "_Test DR khong ton tai"]
		)
		self.assertEqual([r["party"] for r in result["created"]], [good])
		self.assertEqual([r["party"] for r in result["failed"]], ["_Test DR khong ton tai"])

	def test_statement_no_is_shared_within_month(self):
		s1, s2 = make_party("Supplier"), make_party("Supplier")
		n1, _ = generation.build_statement(
			self.company, "Supplier", s1, "2026-09-01", "2026-09-30", C.SOURCE_MANUAL
		)
		n2, _ = generation.build_statement(
			self.company, "Supplier", s2, "2026-09-01", "2026-09-30", C.SOURCE_MANUAL
		)
		self.assertNotEqual(n1, n2)
		numbers = {frappe.db.get_value(C.DOCTYPE, n, "statement_no") for n in (n1, n2)}
		self.assertEqual(numbers, {"09.SL MVL-…./2026"})

	def test_period_must_be_whole_month(self):
		supplier = make_party("Supplier")
		doc = frappe.new_doc(C.DOCTYPE)
		doc.update(
			{
				"company": self.company,
				"party_type": "Supplier",
				"party": supplier,
				"from_date": "2026-03-01",
				"to_date": "2026-03-15",
			}
		)
		self.assertRaises(frappe.ValidationError, doc.insert)

	def test_job_targets_previous_month(self):
		self.assertEqual(generation.previous_month("2026-10-01"), (date(2026, 9, 1), date(2026, 9, 30)))
		self.assertEqual(generation.previous_month("2026-01-01"), (date(2025, 12, 1), date(2025, 12, 31)))

		supplier = make_party("Supplier")
		post(self.company, "Supplier", supplier, 0, 50_000, "2026-03-15")
		result = generation.auto_generate(today="2026-04-01")
		self.assertIn(supplier, {r["party"] for r in result["created"]})


class TestReports(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = get_company("_Test DR Gen", "TDRG")

	def test_total_reconciliation_ties_to_account_balance(self):
		from erpnext.debt_reconciliation.report.doi_chieu_tong_cong_no.doi_chieu_tong_cong_no import execute

		owed, prepaid = make_party("Supplier"), make_party("Supplier")
		post(self.company, "Supplier", owed, 0, 700_000, "2026-02-01")
		post(self.company, "Supplier", owed, 200_000, 0, "2026-03-05")
		post(self.company, "Supplier", prepaid, 90_000, 0, "2026-03-06")
		generation.generate_for_period(self.company, FROM, TO, party_type="Supplier")

		filters = {"company": self.company, "to_date": TO, "party_type": "Supplier"}
		rows = execute(filters)[1]
		total = rows[-1]
		self.assertEqual(total["difference"], 0)
		by_party = {r["party"]: r for r in rows}
		self.assertEqual(by_party[owed]["statement_balance"], 500_000)
		self.assertEqual(by_party[prepaid]["statement_balance"], -90_000)

		# đối tác có số dư nhưng chưa có biên bản → chênh lệch lộ ra
		late = make_party("Supplier")
		post(self.company, "Supplier", late, 0, 33_000, "2026-03-07")
		rows = execute(filters)[1]
		self.assertEqual(rows[-1]["difference"], 33_000)

	def test_status_report_counts(self):
		from erpnext.debt_reconciliation.report.tinh_trang_doi_chieu_cong_no.tinh_trang_doi_chieu_cong_no import (
			execute,
		)

		customer = make_party("Customer")
		post(self.company, "Customer", customer, 10_000, 0, "2026-03-07")
		generation.build_statement(self.company, "Customer", customer, FROM, TO, C.SOURCE_MANUAL)
		columns, data, _msg, _chart, summary = execute(
			{"company": self.company, "from_date": FROM, "to_date": TO, "party_type": "Customer"}
		)
		self.assertIn(customer, {r.party for r in data})
		self.assertEqual(summary[0]["value"], len(data))

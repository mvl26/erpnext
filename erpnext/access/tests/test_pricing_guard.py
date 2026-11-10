"""H2 — line prices must match the expected price unless the user is SM / PM (spec 11.3 H2, D4; plan R-21).

Documents under test are built in memory and handed to ``pricing_guard.validate`` directly, so no Sales Order /
Invoice is ever saved (WF-SO and the Payment Entry workflow on site miyano stay untouched). The price sources the
guard reads are real rows: Item Price is inserted (validated), while source document rows and Blanket Orders are
written with ``db_insert`` because the site has no Customer-ready fixtures. Every test runs inside its own
savepoint, so rows never cross from one test to the next, and the class transaction is rolled back at the end.
"""

import json
import unittest
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, nowdate

from erpnext.access import pricing_guard
from erpnext.access.tests.helpers import make_user
from erpnext.controllers.accounts_controller import update_child_qty_rate

ENABLED = "erpnext.access.pricing_guard.is_enabled"
TODAY = nowdate()


def fake_name(prefix):
	return f"PG-{prefix}-{frappe.generate_hash(length=8)}"


def insert_parent(doctype, **fields):
	"""A bare parent row (no validation, no children) — enough for the guard's join on party and docstatus."""
	doc = frappe.get_doc({"doctype": doctype, "name": fake_name(doctype[:3].upper()), **fields})
	doc.db_insert()
	return doc.name


def insert_child(child_doctype, parent_doctype, parent, **fields):
	row = frappe.get_doc(
		{
			"doctype": child_doctype,
			"name": fake_name("ROW"),
			"parent": parent,
			"parenttype": parent_doctype,
			"parentfield": "items",
			"idx": 1,
			**fields,
		}
	)
	row.db_insert()
	return row.name


def blanket_order(item, rate, *, company, kind="Selling", docstatus=1, customer=None, supplier=None):
	"""A bare Blanket Order with one item row; returns its name. Party and company are the caller's."""
	name = insert_parent(
		"Blanket Order",
		blanket_order_type=kind,
		customer=customer,
		supplier=supplier,
		company=company,
		from_date=add_days(TODAY, -30),
		to_date=add_days(TODAY, 30),
		docstatus=docstatus,
	)
	insert_child("Blanket Order Item", "Blanket Order", name, item_code=item, qty=100, rate=rate)
	return name


def selling_row(item, stock_uom, **fields):
	return {
		"item_code": item,
		"qty": 1,
		"uom": stock_uom,
		"stock_uom": stock_uom,
		"conversion_factor": 1,
		**fields,
	}


def selling_doc(doctype, customer, *rows, company, currency, price_list=None, **fields):
	"""An in-memory Quotation / Sales Order / Sales Invoice for ``customer`` with ``rows``."""
	base = {
		"doctype": doctype,
		"company": company,
		"currency": currency,
		"conversion_rate": 1,
		"plc_conversion_rate": 1,
		"items": list(rows),
	}
	if price_list:
		base["selling_price_list"] = price_list
	if doctype == "Quotation":
		base.update(quotation_to="Customer", party_name=customer, transaction_date=TODAY)
	elif doctype == "Sales Invoice":
		base.update(customer=customer, posting_date=TODAY)
	else:
		base.update(customer=customer, transaction_date=TODAY)
	base.update(fields)
	return frappe.get_doc(base)


class PricingFixtures(FrappeTestCase):
	"""Users, savepoint per test and document builders shared by both suites (no tests of its own)."""

	SHOW_TRANSACTION_COMMIT_WARNINGS = True

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		item = frappe.db.get_value(
			"Item", {"has_variants": 0, "disabled": 0}, ["name", "stock_uom"], as_dict=True
		)
		customer = frappe.db.get_value("Customer", {}, "name")
		if not item or not customer:
			raise unittest.SkipTest("site needs at least one Item and one Customer")
		cls.item, cls.stock_uom = item.name, item.stock_uom
		cls.other_uom = "Box" if cls.stock_uom != "Box" else "Unit"
		cls.customer = customer
		cls.supplier = "PG Supplier"
		cls.su = make_user("Sales User")
		cls.sm = make_user("Sales User", "Sales Manager")
		cls.smm = make_user("Sales User", "Sales Master Manager")
		cls.au = make_user("Accounts User")
		cls.pu = make_user("Purchase User")
		cls.pm = make_user("Purchase User", "Purchase Master Manager")
		cls.item_name = frappe.db.get_value("Item", cls.item, "item_name")

	def setUp(self):
		patcher = patch(ENABLED, return_value=True)
		patcher.start()
		self.addCleanup(patcher.stop)
		self.addCleanup(frappe.set_user, "Administrator")
		savepoint = f"pg_{frappe.generate_hash(length=8)}"
		frappe.db.savepoint(savepoint)
		self.addCleanup(frappe.db.rollback, save_point=savepoint)

	# -- builders ------------------------------------------------------------------------------

	def item_price(self, rate, price_list="Standard Selling", **fields):
		frappe.get_doc(
			{
				"doctype": "Item Price",
				"item_code": self.item,
				"price_list": price_list,
				"uom": self.stock_uom,
				"price_list_rate": rate,
				**fields,
			}
		).insert(ignore_permissions=True)

	def blanket_order(self, rate, docstatus=1, customer=None, supplier=None, kind="Selling"):
		return blanket_order(
			self.item,
			rate,
			company="Miyano",
			kind=kind,
			docstatus=docstatus,
			customer=customer if customer is not None else (self.customer if kind == "Selling" else None),
			supplier=supplier if supplier is not None else (self.supplier if kind == "Purchasing" else None),
		)

	def row(self, **fields):
		return selling_row(self.item, self.stock_uom, **fields)

	def selling_doc(self, doctype, *rows, **fields):
		args = {"company": "Miyano", "currency": "VND", "price_list": "Standard Selling", **fields}
		customer = args.pop("customer", self.customer)
		return selling_doc(doctype, customer, *rows, **args)

	def buying_doc(self, doctype, *rows, **fields):
		base = {
			"doctype": doctype,
			"company": "Miyano",
			"supplier": self.supplier,
			"currency": "VND",
			"conversion_rate": 1,
			"plc_conversion_rate": 1,
			"buying_price_list": "Standard Buying",
			"items": list(rows),
		}
		base["posting_date" if doctype == "Purchase Invoice" else "transaction_date"] = TODAY
		base.update(fields)
		return frappe.get_doc(base)

	def run_as(self, user, doc):
		frappe.set_user(user)
		try:
			pricing_guard.validate(doc)
		finally:
			frappe.set_user("Administrator")

	def assert_blocked(self, user, doc, *fragments):
		with self.assertRaises(frappe.ValidationError) as ctx:
			self.run_as(user, doc)
		for fragment in fragments:
			self.assertIn(fragment, str(ctx.exception))


class TestPricingGuard(PricingFixtures):
	# -- T21, SM bypass, no Item Price ---------------------------------------------------------

	def test_t21_su_changing_so_rate_against_blanket_order_is_blocked(self):
		bo = self.blanket_order(100)
		doc = self.selling_doc("Sales Order", self.row(rate=90, blanket_order=bo))
		self.assert_blocked(self.su, doc, "Dòng 1", self.item)

	def test_sm_may_change_the_rate(self):
		bo = self.blanket_order(100)
		for user in (self.sm, self.smm):
			doc = self.selling_doc("Sales Order", self.row(rate=90, blanket_order=bo))
			self.run_as(user, doc)  # no error
			self.assertEqual(doc.mvl_dung_gia_hd, 0)  # still computed for SM

	def test_row_without_any_price_is_not_checked(self):
		doc = self.selling_doc("Sales Order", self.row(rate=12345))
		self.run_as(self.su, doc)
		self.assertIsNone(pricing_guard.expected_rate(doc, doc.items[0]))

	def test_item_price_is_enforced_for_su(self):
		self.item_price(100)
		self.run_as(self.su, self.selling_doc("Quotation", self.row(rate=100)))
		self.assert_blocked(self.su, self.selling_doc("Quotation", self.row(rate=120)), "Dòng 1", "120")
		self.assert_blocked(self.su, self.selling_doc("Sales Invoice", self.row(rate=80)), "Dòng 1")

	def test_several_bad_rows_are_listed_in_one_error(self):
		self.item_price(100)
		doc = self.selling_doc(
			"Sales Order", self.row(rate=100), self.row(rate=70, idx=2), self.row(rate=60, idx=3)
		)
		self.assert_blocked(self.su, doc, "Dòng 2", "Dòng 3")

	def test_item_price_converts_from_stock_uom(self):
		self.item_price(100)
		row = self.row(rate=1000, uom=self.other_uom, conversion_factor=10)
		doc = self.selling_doc("Sales Order", row)
		self.assertEqual(pricing_guard.expected_rate(doc, doc.items[0]), 1000)
		self.run_as(self.su, doc)

	def test_item_price_in_the_row_uom_wins(self):
		self.item_price(100)
		self.item_price(950, uom=self.other_uom)
		doc = self.selling_doc("Sales Order", self.row(rate=950, uom=self.other_uom, conversion_factor=10))
		self.assertEqual(pricing_guard.expected_rate(doc, doc.items[0]), 950)

	def test_customer_specific_item_price_is_preferred(self):
		self.item_price(100)
		self.item_price(80, customer=self.customer)
		doc = self.selling_doc("Sales Order", self.row(rate=80))
		self.assertEqual(pricing_guard.expected_rate(doc, doc.items[0]), 80)
		self.run_as(self.su, doc)

	def test_item_price_outside_its_validity_is_ignored(self):
		self.item_price(100, valid_from=add_days(TODAY, 5))
		doc = self.selling_doc("Sales Order", self.row(rate=1))
		self.assertIsNone(pricing_guard.expected_rate(doc, doc.items[0]))

	def test_price_list_currency_is_converted(self):
		self.item_price(100)
		doc = self.selling_doc(
			"Sales Order", self.row(rate=4), conversion_rate=25000, plc_conversion_rate=1000
		)
		self.assertEqual(pricing_guard.expected_rate(doc, doc.items[0]), 4)

	# -- R-21: source rows first ---------------------------------------------------------------

	def test_si_from_so_at_contract_price_passes_and_editing_it_is_blocked(self):
		self.item_price(100)
		so = insert_parent("Sales Order", customer=self.customer, docstatus=1)
		so_item = insert_child(
			"Sales Order Item", "Sales Order", so, item_code=self.item, rate=150, conversion_factor=1
		)
		doc = self.selling_doc("Sales Invoice", self.row(rate=150, so_detail=so_item))
		self.assertEqual(pricing_guard.expected_rate(doc, doc.items[0]), 150)
		self.run_as(self.au, doc)  # AU, contract price ≠ price list: passes
		edited = self.selling_doc("Sales Invoice", self.row(rate=140, so_detail=so_item))
		self.assert_blocked(self.au, edited, "Dòng 1", "150")

	def test_si_from_delivery_note_uses_the_dn_row(self):
		dn = insert_parent("Delivery Note", customer=self.customer, docstatus=1)
		dn_item = insert_child(
			"Delivery Note Item", "Delivery Note", dn, item_code=self.item, rate=55, conversion_factor=1
		)
		doc = self.selling_doc("Sales Invoice", self.row(rate=55, dn_detail=dn_item))
		self.run_as(self.au, doc)
		self.assert_blocked(self.au, self.selling_doc("Sales Invoice", self.row(rate=50, dn_detail=dn_item)))

	def test_so_from_quotation_uses_the_quotation_row(self):
		self.item_price(100)
		qtn = insert_parent("Quotation", quotation_to="Customer", party_name=self.customer, docstatus=1)
		q_item = insert_child(
			"Quotation Item", "Quotation", qtn, item_code=self.item, rate=85, conversion_factor=1
		)
		self.run_as(self.su, self.selling_doc("Sales Order", self.row(rate=85, quotation_item=q_item)))

	def test_po_from_supplier_quotation_passes(self):
		self.item_price(100, price_list="Standard Buying")
		sq = insert_parent("Supplier Quotation", supplier=self.supplier, docstatus=1)
		sq_item = insert_child(
			"Supplier Quotation Item",
			"Supplier Quotation",
			sq,
			item_code=self.item,
			rate=70,
			conversion_factor=1,
		)
		self.run_as(
			self.pu, self.buying_doc("Purchase Order", self.row(rate=70, supplier_quotation_item=sq_item))
		)
		self.assert_blocked(
			self.pu,
			self.buying_doc("Purchase Order", self.row(rate=60, supplier_quotation_item=sq_item)),
			"70",
		)

	def test_pi_from_po_and_pr(self):
		po = insert_parent("Purchase Order", supplier=self.supplier, docstatus=1)
		po_item = insert_child(
			"Purchase Order Item", "Purchase Order", po, item_code=self.item, rate=40, conversion_factor=1
		)
		pr = insert_parent("Purchase Receipt", supplier=self.supplier, docstatus=1)
		pr_item = insert_child(
			"Purchase Receipt Item", "Purchase Receipt", pr, item_code=self.item, rate=41, conversion_factor=1
		)
		self.run_as(self.au, self.buying_doc("Purchase Invoice", self.row(rate=40, po_detail=po_item)))
		self.run_as(self.au, self.buying_doc("Purchase Invoice", self.row(rate=41, pr_detail=pr_item)))
		self.assert_blocked(
			self.au, self.buying_doc("Purchase Invoice", self.row(rate=39, po_detail=po_item))
		)

	def test_source_row_discount_is_compared(self):
		so = insert_parent("Sales Order", customer=self.customer, docstatus=1)
		so_item = insert_child(
			"Sales Order Item",
			"Sales Order",
			so,
			item_code=self.item,
			rate=90,
			discount_percentage=10,
			conversion_factor=1,
		)
		ok = self.selling_doc("Sales Invoice", self.row(rate=90, discount_percentage=10, so_detail=so_item))
		self.run_as(self.au, ok)
		bad = self.selling_doc("Sales Invoice", self.row(rate=90, discount_percentage=5, so_detail=so_item))
		self.assert_blocked(self.au, bad, "Dòng 1", "chiết khấu")

	def test_source_row_rate_follows_the_uom(self):
		so = insert_parent("Sales Order", customer=self.customer, docstatus=1)
		so_item = insert_child(
			"Sales Order Item", "Sales Order", so, item_code=self.item, rate=20, conversion_factor=1
		)
		doc = self.selling_doc(
			"Sales Invoice", self.row(rate=200, uom=self.other_uom, conversion_factor=10, so_detail=so_item)
		)
		self.assertEqual(pricing_guard.expected_rate(doc, doc.items[0]), 200)

	def test_forged_source_links_fall_back_to_the_price_list(self):
		self.item_price(100)
		draft = insert_parent("Sales Order", customer=self.customer, docstatus=0)
		other = insert_parent("Sales Order", customer="PG Someone Else", docstatus=1)
		for so in (draft, other):
			so_item = insert_child(
				"Sales Order Item", "Sales Order", so, item_code=self.item, rate=10, conversion_factor=1
			)
			doc = self.selling_doc("Sales Invoice", self.row(rate=10, so_detail=so_item))
			self.assertEqual(pricing_guard.expected_rate(doc, doc.items[0]), 100)
			self.assert_blocked(self.au, doc, "100")

	# -- roles per side ------------------------------------------------------------------------

	def test_pm_bypasses_buying_but_sm_does_not(self):
		self.item_price(100, price_list="Standard Buying")
		self.run_as(self.pm, self.buying_doc("Purchase Order", self.row(rate=60)))
		self.assert_blocked(self.sm, self.buying_doc("Purchase Order", self.row(rate=60)))
		self.item_price(100)
		self.assert_blocked(self.pm, self.selling_doc("Sales Order", self.row(rate=60)))

	def test_administrator_and_ignore_permissions_skip_the_check(self):
		self.item_price(100)
		pricing_guard.validate(self.selling_doc("Sales Order", self.row(rate=1)))  # Administrator
		doc = self.selling_doc("Sales Order", self.row(rate=1))
		doc.flags.ignore_permissions = True
		self.run_as(self.su, doc)

	def test_gate_off_is_a_no_op(self):
		self.item_price(100)
		doc = self.selling_doc("Sales Order", self.row(rate=1), mvl_dung_gia_hd=1)
		with patch(ENABLED, return_value=False):
			self.run_as(self.su, doc)
		self.assertEqual(doc.mvl_dung_gia_hd, 1)  # untouched

	# -- pricing rules: rule price only when ERPNext would apply the very same rules now ------------

	def pricing_rule(self, **fields):
		"""A throwaway selling Pricing Rule on the test item (rolled back with the test savepoint)."""
		return frappe.get_doc(
			{
				"doctype": "Pricing Rule",
				"title": fake_name("PR"),
				"apply_on": "Item Code",
				"items": [{"item_code": self.item}],
				"selling": 1,
				"company": "Miyano",
				"currency": "VND",
				"price_or_product_discount": "Price",
				"rate_or_discount": "Discount Percentage",
				"discount_percentage": 10,
				**fields,
			}
		).insert(ignore_permissions=True)

	def rule_row(self, *rules, **fields):
		return self.row(pricing_rules=json.dumps(list(rules)), **fields)

	def test_applicable_rule_row_is_checked_against_the_rule_price(self):
		self.item_price(100)
		rule = self.pricing_rule()
		row = self.rule_row(rule.name, rate=90, price_list_rate=100, discount_percentage=10)
		doc = self.selling_doc("Sales Order", row)
		self.assertEqual(pricing_guard._fresh_rules(doc, doc.items[0]), {rule.name})
		self.run_as(self.su, doc)
		deeper = self.rule_row(rule.name, rate=50, price_list_rate=100, discount_percentage=50)
		self.assert_blocked(self.su, self.selling_doc("Sales Order", deeper), "Dòng 1", "quy tắc giá", "90")

	def test_rule_row_with_a_forged_price_list_rate_is_blocked(self):
		# ERPNext keeps the client's price_list_rate and takes the rule's 10 % off it: 60 → 54
		self.item_price(100)
		rule = self.pricing_rule()
		row = self.rule_row(rule.name, rate=54, price_list_rate=60, discount_percentage=10)
		self.assert_blocked(self.su, self.selling_doc("Sales Order", row), "Dòng 1", "90")

	def test_rate_rule_sets_the_price(self):
		self.item_price(100)
		rule = self.pricing_rule(rate_or_discount="Rate", rate=80, discount_percentage=0)
		self.run_as(self.su, self.selling_doc("Sales Order", self.rule_row(rule.name, rate=80)))
		cheaper = self.rule_row(rule.name, rate=70, price_list_rate=70)
		self.assert_blocked(self.su, self.selling_doc("Sales Order", cheaper), "Dòng 1", "80")

	def test_rule_margin_is_applied_before_the_discount(self):
		self.item_price(100)
		rule = self.pricing_rule(margin_type="Percentage", margin_rate_or_amount=20)
		self.run_as(self.su, self.selling_doc("Sales Order", self.rule_row(rule.name, rate=108)))
		self.assert_blocked(
			self.su, self.selling_doc("Sales Order", self.rule_row(rule.name, rate=90)), "Dòng 1", "108"
		)

	def test_discount_rule_without_item_price_is_not_checked(self):
		rule = self.pricing_rule()
		row = self.rule_row(rule.name, rate=1, price_list_rate=1, discount_percentage=10)
		self.run_as(self.su, self.selling_doc("Sales Order", row))

	def test_forged_rule_name_on_unrelated_row_is_checked(self):
		self.item_price(100)
		unrelated = self.pricing_rule(min_qty=1000)  # real rule, but a 1-unit row does not qualify
		for rules in ([unrelated.name], ["PRLE-FORGED-0001"]):
			doc = self.selling_doc("Sales Order", self.rule_row(*rules, rate=50))
			self.assert_blocked(self.su, doc, "Dòng 1", "100")

	def test_row_must_carry_exactly_the_applicable_rules(self):
		self.item_price(100)
		rule = self.pricing_rule()
		extra = self.pricing_rule(min_qty=1000)
		doc = self.selling_doc("Sales Order", self.rule_row(rule.name, extra.name, rate=50))
		self.assert_blocked(self.su, doc, "Dòng 1")

	def test_rule_rows_are_checked_when_rules_are_ignored(self):
		self.item_price(100)
		rule = self.pricing_rule()
		ignored = self.selling_doc("Sales Order", self.rule_row(rule.name, rate=50), ignore_pricing_rule=1)
		self.assert_blocked(self.su, ignored, "Dòng 1")

	def test_free_item_backed_by_an_applied_product_rule_is_skipped(self):
		self.item_price(100)
		rule = self.pricing_rule(
			price_or_product_discount="Product", rate_or_discount=None, same_item=1, free_qty=1
		)
		paid = self.rule_row(rule.name, rate=100)
		free = self.rule_row(rule.name, rate=0, is_free_item=1, idx=2)
		doc = self.selling_doc("Sales Order", paid, free)
		self.assertEqual(pricing_guard._fresh_rules(doc, doc.items[0]), {rule.name})
		self.assertEqual(len(pricing_guard._rule_priced_rows(doc)), 2)
		self.run_as(self.su, doc)

	def test_free_item_with_a_forged_rule_is_checked(self):
		self.item_price(100)
		price_rule = self.pricing_rule()
		paid = self.rule_row(price_rule.name, rate=90, price_list_rate=100, discount_percentage=10)
		free = self.rule_row(
			price_rule.name, rate=0, is_free_item=1, idx=2
		)  # a Price rule gives nothing away
		self.assert_blocked(self.su, self.selling_doc("Sales Order", paid, free), "Dòng 2")
		alone = self.rule_row("PRLE-FORGED-0001", rate=0, is_free_item=1)
		self.assert_blocked(self.su, self.selling_doc("Sales Order", alone), "Dòng 1")

	def test_free_item_without_a_pricing_rule_is_checked(self):
		self.item_price(100)
		self.assert_blocked(
			self.su, self.selling_doc("Sales Order", self.row(rate=0, is_free_item=1)), "Dòng 1"
		)

	# -- T37: mvl_dung_gia_hd ------------------------------------------------------------------

	def test_t37_flag_set_when_every_row_is_at_blanket_price(self):
		bo = self.blanket_order(100)
		doc = self.selling_doc(
			"Sales Order", self.row(rate=100, blanket_order=bo), self.row(rate=100, blanket_order=bo, idx=2)
		)
		self.run_as(self.su, doc)
		self.assertEqual(doc.mvl_dung_gia_hd, 1)

	def test_t37_flag_cleared_otherwise(self):
		bo = self.blanket_order(100)
		cases = {
			"row without blanket order": (self.row(rate=100, blanket_order=bo), self.row(rate=5, idx=2)),
			"rate off the blanket price": (self.row(rate=99, blanket_order=bo),),
			"no rows": (),
		}
		for label, rows in cases.items():
			with self.subTest(label):
				doc = self.selling_doc("Sales Order", *rows, mvl_dung_gia_hd=1)
				self.run_as(self.sm, doc)
				self.assertEqual(doc.mvl_dung_gia_hd, 0)

	def test_t37_flag_needs_a_submitted_blanket_order_of_the_same_customer(self):
		draft = self.blanket_order(100, docstatus=0)
		foreign = self.blanket_order(100, customer="PG Someone Else")
		for bo in (draft, foreign):
			doc = self.selling_doc("Sales Order", self.row(rate=100, blanket_order=bo), mvl_dung_gia_hd=1)
			self.run_as(self.sm, doc)
			self.assertEqual(doc.mvl_dung_gia_hd, 0)

	def test_blanket_rate_is_not_scaled_by_the_uom(self):
		# Blanket Order Item has no UOM; ERPNext copies blanket_order_rate straight into the row rate
		bo = self.blanket_order(100)
		at_bo = self.selling_doc(
			"Sales Order", self.row(rate=100, uom=self.other_uom, conversion_factor=10, blanket_order=bo)
		)
		self.assertEqual(pricing_guard.expected_rate(at_bo, at_bo.items[0]), 100)
		self.run_as(self.su, at_bo)
		self.assertEqual(at_bo.mvl_dung_gia_hd, 1)
		scaled = self.selling_doc(
			"Sales Order", self.row(rate=1000, uom=self.other_uom, conversion_factor=10, blanket_order=bo)
		)
		self.assert_blocked(self.su, scaled, "Dòng 1")

	def test_blanket_order_of_another_company_is_ignored(self):
		bo = self.blanket_order(100)
		doc = self.selling_doc("Sales Order", self.row(rate=100, blanket_order=bo), company="PG Other Co")
		self.assertIsNone(pricing_guard.expected_rate(doc, doc.items[0]))

	def test_po_blanket_order_rate_is_enforced(self):
		bo = self.blanket_order(50, kind="Purchasing")
		self.run_as(self.pu, self.buying_doc("Purchase Order", self.row(rate=50, blanket_order=bo)))
		self.assert_blocked(self.pu, self.buying_doc("Purchase Order", self.row(rate=55, blanket_order=bo)))

	# -- registration --------------------------------------------------------------------------

	def test_hooks_are_registered(self):
		from erpnext import hooks

		def handlers(doctype, event):
			found = hooks.doc_events.get(doctype, {}).get(event, [])
			return [found] if isinstance(found, str) else found

		for doctype in ("Quotation", "Sales Order", "Sales Invoice", "Purchase Order", "Purchase Invoice"):
			self.assertIn("erpnext.access.pricing_guard.validate", handlers(doctype, "validate"), doctype)
			# Update Items is guarded inside update_child_qty_rate, not by a doc event (it would be dead code)
			self.assertEqual(handlers(doctype, "before_update_after_submit"), [], doctype)

	# -- fix round 1: Lead/Prospect quotations, nearest source, Update Items, ERPNext Item Price ---------

	def converted_customer(self, **fields):
		name = fake_name("CUST")
		frappe.get_doc({"doctype": "Customer", "name": name, "customer_name": name, **fields}).db_insert()
		return name

	def test_so_from_lead_or_prospect_quotation_uses_the_quotation_row(self):
		self.item_price(100)
		for quotation_to, field in (("Lead", "lead_name"), ("Prospect", "prospect_name")):
			with self.subTest(quotation_to):
				party = fake_name(quotation_to.upper())
				customer = self.converted_customer(**{field: party})
				stranger = self.converted_customer(**{field: fake_name("OTHER")})
				qtn = insert_parent("Quotation", quotation_to=quotation_to, party_name=party, docstatus=1)
				q_item = insert_child(
					"Quotation Item", "Quotation", qtn, item_code=self.item, rate=85, conversion_factor=1
				)
				doc = self.selling_doc(
					"Sales Order", self.row(rate=85, quotation_item=q_item), customer=customer
				)
				self.assertEqual(pricing_guard.expected_rate(doc, doc.items[0]), 85)
				self.run_as(self.su, doc)
				forged = self.selling_doc(
					"Sales Order", self.row(rate=85, quotation_item=q_item), customer=stranger
				)
				# another customer's quotation row is ignored: back to the price list
				self.assertEqual(pricing_guard.expected_rate(forged, forged.items[0]), 100)

	def test_si_uses_the_dn_row_before_the_so_row(self):
		so = insert_parent("Sales Order", customer=self.customer, docstatus=1)
		so_item = insert_child(
			"Sales Order Item", "Sales Order", so, item_code=self.item, rate=150, conversion_factor=1
		)
		dn = insert_parent("Delivery Note", customer=self.customer, docstatus=1)
		dn_item = insert_child(
			"Delivery Note Item", "Delivery Note", dn, item_code=self.item, rate=160, conversion_factor=1
		)
		doc = self.selling_doc("Sales Invoice", self.row(rate=160, so_detail=so_item, dn_detail=dn_item))
		self.assertEqual(pricing_guard.expected_rate(doc, doc.items[0]), 160)
		self.run_as(self.au, doc)
		at_so = self.selling_doc("Sales Invoice", self.row(rate=150, so_detail=so_item, dn_detail=dn_item))
		self.assert_blocked(self.au, at_so, "160")

	def test_pi_uses_the_pr_row_before_the_po_row(self):
		po = insert_parent("Purchase Order", supplier=self.supplier, docstatus=1)
		po_item = insert_child(
			"Purchase Order Item", "Purchase Order", po, item_code=self.item, rate=40, conversion_factor=1
		)
		pr = insert_parent("Purchase Receipt", supplier=self.supplier, docstatus=1)
		pr_item = insert_child(
			"Purchase Receipt Item", "Purchase Receipt", pr, item_code=self.item, rate=45, conversion_factor=1
		)
		doc = self.buying_doc("Purchase Invoice", self.row(rate=45, po_detail=po_item, pr_detail=pr_item))
		self.run_as(self.au, doc)
		at_po = self.buying_doc("Purchase Invoice", self.row(rate=40, po_detail=po_item, pr_detail=pr_item))
		self.assert_blocked(self.au, at_po, "45")

	def test_price_list_uom_dependence_is_read_like_erpnext(self):
		self.item_price(100)
		doc = self.selling_doc("Sales Order", self.row(rate=100, uom=self.other_uom, conversion_factor=10))
		with patch(
			"erpnext.stock.doctype.price_list.price_list.get_price_list_details",
			return_value={"price_list_uom_dependant": 1},
		):
			self.assertEqual(pricing_guard.expected_rate(doc, doc.items[0]), 100)
		self.assertEqual(pricing_guard.expected_rate(doc, doc.items[0]), 1000)

	def test_customer_price_outside_its_packing_unit_is_not_used(self):
		self.item_price(80, customer=self.customer, packing_unit=5)
		doc = self.selling_doc("Sales Order", self.row(rate=1, qty=3))
		self.assertIsNone(pricing_guard.expected_rate(doc, doc.items[0]))  # ERPNext fills no price either
		doc = self.selling_doc("Sales Order", self.row(rate=80, qty=10))
		self.assertEqual(pricing_guard.expected_rate(doc, doc.items[0]), 80)


class _Reached(Exception):
	"""Raised by the spy after the real guard passed, so update_child_qty_rate stops before writing the row."""


class TestUpdateItemsPricing(PricingFixtures):
	"""H2 on "Update Items": the REAL ``update_child_qty_rate`` against a submitted order written with db_insert.

	A spy wraps ``pricing_guard.check_update_item``: it records the arguments, runs the real guard, then raises
	``_Reached`` so the loop never writes a row nor reaches ``parent.save()`` — a passing guard is proven without
	saving a submitted Sales / Purchase Order on site miyano.
	"""

	def order(self, doctype, **row_fields):
		selling = doctype == "Sales Order"
		date_field = "delivery_date" if selling else "schedule_date"
		parent_fields = {
			"company": "Miyano",
			"currency": "VND",
			"price_list_currency": "VND",
			"conversion_rate": 1,
			"plc_conversion_rate": 1,
			"transaction_date": TODAY,
			date_field: TODAY,
			"set_warehouse": "Stores - M",
			"docstatus": 1,
		}
		if selling:
			parent_fields.update(customer=self.customer, selling_price_list="Standard Selling")
		else:
			parent_fields.update(supplier=self.supplier, buying_price_list="Standard Buying")
		name = insert_parent(doctype, **parent_fields)
		row = insert_child(
			doctype + " Item",
			doctype,
			name,
			**{
				"item_code": self.item,
				"item_name": self.item_name,
				"qty": 2,
				"rate": 100,
				"price_list_rate": 100,
				"uom": self.stock_uom,
				"stock_uom": self.stock_uom,
				"conversion_factor": 1,
				"warehouse": "Stores - M",
				date_field: TODAY,
				"docstatus": 1,
				**row_fields,
			},
		)
		return name, row

	def trans(self, doctype, docname=None, **fields):
		date_field = "delivery_date" if doctype == "Sales Order" else "schedule_date"
		return {
			"docname": docname,
			"item_code": self.item,
			"qty": 2,
			"rate": 100,
			"uom": self.stock_uom,
			"conversion_factor": 1,
			date_field: TODAY,
			**fields,
		}

	def update_items(self, user, doctype, name, *trans_items):
		"""Run the real Update Items as ``user``; return the spy's calls. Raises what the real guard raises."""
		calls = []
		real = pricing_guard.check_update_item

		def spy(parent, child_item, old=None):
			calls.append((parent.name, child_item.as_dict(), old))
			real(parent, child_item, old)
			raise _Reached

		frappe.set_user(user)
		try:
			with patch.object(pricing_guard, "check_update_item", side_effect=spy):
				update_child_qty_rate(doctype, json.dumps(list(trans_items)), name)
		except _Reached:
			pass
		finally:
			frappe.set_user("Administrator")
		self.assertTrue(calls, "the loop never reached check_update_item")
		return calls

	def test_guard_runs_inside_the_loop_with_the_old_values(self):
		self.item_price(100)
		so, row = self.order("Sales Order")
		calls = self.update_items(self.su, "Sales Order", so, self.trans("Sales Order", row, qty=3))
		parent_name, child, old = calls[0]
		self.assertEqual(parent_name, so)
		self.assertEqual((child["name"], child["qty"], child["rate"]), (row, 3, 100))
		self.assertEqual((old.rate, old.uom, old.conversion_factor), (100, self.stock_uom, 1))
		# the row was not written: the spy stopped the loop before child_item.save()
		self.assertEqual(frappe.db.get_value("Sales Order Item", row, "qty"), 2)

	def assert_update_blocked(self, user, doctype, name, *trans_items):
		with self.assertRaises(frappe.ValidationError) as ctx:
			self.update_items(user, doctype, name, *trans_items)
		self.assertIn("Dòng", str(ctx.exception))

	def test_su_lowering_a_rate_is_blocked(self):
		self.item_price(100)
		so, row = self.order("Sales Order")
		self.assert_update_blocked(self.su, "Sales Order", so, self.trans("Sales Order", row, rate=90))

	def test_pu_lowering_a_po_rate_is_blocked_pm_passes(self):
		self.item_price(100, price_list="Standard Buying")
		po, row = self.order("Purchase Order")
		self.assert_update_blocked(self.pu, "Purchase Order", po, self.trans("Purchase Order", row, rate=90))
		self.update_items(self.pm, "Purchase Order", po, self.trans("Purchase Order", row, rate=90))

	def test_su_changing_uom_at_the_same_rate_is_blocked(self):
		self.item_price(100)
		so, row = self.order("Sales Order")
		changed = self.trans("Sales Order", row, uom=self.other_uom, conversion_factor=10)
		self.assert_update_blocked(self.su, "Sales Order", so, changed)

	def test_sm_may_reprice(self):
		self.item_price(100)
		so, row = self.order("Sales Order")
		for user in (self.sm, self.smm):
			self.update_items(user, "Sales Order", so, self.trans("Sales Order", row, rate=90))

	def test_pricing_rule_row_repriced_is_blocked(self):
		self.item_price(100)
		so, row = self.order("Sales Order", pricing_rules='["PRLE-0001"]')
		self.assert_update_blocked(self.su, "Sales Order", so, self.trans("Sales Order", row, rate=90))

	def test_new_row_at_a_wrong_price_is_blocked(self):
		self.item_price(100)
		so, row = self.order("Sales Order")
		self.assert_update_blocked(
			self.su,
			"Sales Order",
			so,
			self.trans("Sales Order", row),  # unchanged: the loop skips it
			self.trans("Sales Order", None, rate=50),
		)

	def test_qty_only_change_passes_even_off_price(self):
		self.item_price(120)  # price list moved since the order was submitted at 100
		so, row = self.order("Sales Order")
		calls = self.update_items(self.su, "Sales Order", so, self.trans("Sales Order", row, qty=5))
		self.assertEqual(calls[0][1]["qty"], 5)

	def test_qty_only_change_on_a_discount_amount_rule_row_passes(self):
		# the loop re-derives discount_percentage 0 → 7 from rate / price_list_rate: not a reprice
		self.item_price(100)
		so, row = self.order(
			"Sales Order",
			rate=93,
			price_list_rate=100,
			discount_percentage=0,
			discount_amount=7,
			pricing_rules='["PRLE-0001"]',
		)
		calls = self.update_items(self.su, "Sales Order", so, self.trans("Sales Order", row, rate=93, qty=5))
		self.assertEqual((calls[0][1]["discount_percentage"], calls[0][2].rate), (7, 93))
		self.assert_update_blocked(self.su, "Sales Order", so, self.trans("Sales Order", row, rate=90, qty=5))

	def test_gate_off_is_a_no_op(self):
		self.item_price(100)
		so, row = self.order("Sales Order")
		with patch(ENABLED, return_value=False):
			self.update_items(self.su, "Sales Order", so, self.trans("Sales Order", row, rate=1))

	def test_check_update_item_unit(self):
		self.item_price(100)
		doc = self.selling_doc("Sales Order", self.row(rate=90, discount_percentage=10))
		row = doc.items[0]
		old = frappe._dict(rate=90, uom=self.stock_uom, conversion_factor=1)
		frappe.set_user(self.su)
		try:
			pricing_guard.check_update_item(doc, row, old)  # unchanged: not checked
			self.assertRaises(
				frappe.ValidationError, pricing_guard.check_update_item, doc, row, None
			)  # new row
			row.rate = 100
			pricing_guard.check_update_item(doc, row, None)  # at the price list rate
		finally:
			frappe.set_user("Administrator")

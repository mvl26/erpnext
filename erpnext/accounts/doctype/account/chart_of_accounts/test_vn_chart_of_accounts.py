# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

"""Tests for the Vietnam (Thông tư 99/2025/TT-BTC) chart of accounts template.

The template lives in ``verified/vn_chart_of_accounts.json`` and must both parse
cleanly and expose the ``account_type`` tags that ERPNext relies on to wire a
company's default accounts (see ``Company.set_default_accounts``).
"""

import json
import os
import unittest

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.accounts.doctype.account.chart_of_accounts import chart_of_accounts

RESERVED_KEYS = {
	"account_name",
	"account_number",
	"account_type",
	"root_type",
	"is_group",
	"tax_rate",
	"account_currency",
}

CHART_NAME = "Vietnam - Chart of Accounts (Thông tư 99/2025/TT-BTC)"

# account_number -> expected account_type. These are the accounts ERPNext maps
# to company default-account fields, so they must be tagged correctly.
EXPECTED_ACCOUNT_TYPES = {
	"111": "Cash",  # Tiền mặt -> default_cash_account
	"112": "Bank",  # Tiền gửi không kỳ hạn -> default_bank_account
	"131": "Receivable",  # Phải thu của khách hàng -> default_receivable_account
	"331": "Payable",  # Phải trả cho người bán -> default_payable_account
	"632": "Cost of Goods Sold",  # Giá vốn hàng bán -> default_expense_account
	"156": "Stock",  # Hàng hóa -> default_inventory_account
	"211": "Fixed Asset",  # TSCĐ hữu hình
	"2141": "Accumulated Depreciation",  # Hao mòn TSCĐ hữu hình
	"6424": "Depreciation",  # Chi phí khấu hao TSCĐ (QLDN) -> depreciation_expense_account
	"2411": "Capital Work in Progress",  # Mua sắm TSCĐ
	"511": "Income Account",  # Doanh thu bán hàng và cung cấp dịch vụ
	"1331": "Tax",  # Thuế GTGT được khấu trừ của hàng hóa, dịch vụ
	"33311": "Tax",  # Thuế GTGT đầu ra
}

# account_number -> expected root_type (inherited from the root).
EXPECTED_ROOT_TYPES = {
	"111": "Asset",
	"331": "Liability",
	"411": "Equity",
	"511": "Income",
	"711": "Income",
	"632": "Expense",
	"642": "Expense",
}

# TT99 has no dedicated accounts for these ERPNext operational needs, so the chart
# adds them (unnumbered) and ERPNext wires them to company defaults by account_type.
OPERATIONAL_ACCOUNT_TYPES = {
	"Hàng mua chưa có hóa đơn": "Stock Received But Not Billed",
	"Tài sản mua chưa có hóa đơn": "Asset Received But Not Billed",
	"Chênh lệch làm tròn": "Round Off",
	"Chi phí điều chỉnh hàng tồn kho": "Stock Adjustment",
	"Chi phí thu mua tính vào giá trị hàng tồn kho": "Expenses Included In Valuation",
	"Chi phí tính vào nguyên giá tài sản": "Expenses Included In Asset Valuation",
}

# These three are wired by ERPNext via translated account NAME, not account_type,
# so the account name must match the canonical string exactly.
OPERATIONAL_NAMED_ACCOUNTS = ("Write Off", "Exchange Gain/Loss", "Gain/Loss on Asset Disposal")

# Company fields that must be populated after creating a company on the VN chart.
COMPANY_OPERATIONAL_DEFAULT_FIELDS = (
	"round_off_account",
	"write_off_account",
	"exchange_gain_loss_account",
	"disposal_account",
	"asset_received_but_not_billed",
	"expenses_included_in_asset_valuation",
	"stock_received_but_not_billed",
	"stock_adjustment_account",
	"expenses_included_in_valuation",
)


def _chart_path():
	return os.path.join(
		os.path.dirname(chart_of_accounts.__file__), "verified", "vn_chart_of_accounts.json"
	)


def _flatten(tree, root_type=None, by_number=None):
	"""Return {account_number: {"node": node, "root_type": root_type}}."""
	if by_number is None:
		by_number = {}
	for name, node in tree.items():
		if name in RESERVED_KEYS or not isinstance(node, dict):
			continue
		this_root_type = node.get("root_type", root_type)
		number = str(node.get("account_number") or "").strip()
		if number:
			by_number[number] = {"node": node, "root_type": this_root_type}
		_flatten(node, this_root_type, by_number)
	return by_number


def _flatten_by_name(tree, by_name=None):
	"""Return {account_name: node} for every account in the tree."""
	if by_name is None:
		by_name = {}
	for name, node in tree.items():
		if name in RESERVED_KEYS or not isinstance(node, dict):
			continue
		by_name[name] = node
		_flatten_by_name(node, by_name)
	return by_name


class TestVietnamChartOfAccounts(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		with open(_chart_path(), encoding="utf-8") as f:
			cls.chart = json.load(f)
		cls.by_number = _flatten(cls.chart["tree"])
		cls.by_name = _flatten_by_name(cls.chart["tree"])

	def test_metadata(self):
		self.assertEqual(self.chart["country_code"], "vn")
		self.assertEqual(self.chart["name"], CHART_NAME)
		self.assertIn("tree", self.chart)

	def test_five_roots_cover_all_root_types(self):
		roots = self.chart["tree"]
		root_types = {node["root_type"] for node in roots.values()}
		self.assertEqual(root_types, {"Asset", "Liability", "Equity", "Income", "Expense"})

	def test_discoverable_for_vietnam(self):
		charts = chart_of_accounts.get_charts_for_country("Vietnam")
		self.assertIn(CHART_NAME, charts)

	def test_key_account_types(self):
		for number, expected_type in EXPECTED_ACCOUNT_TYPES.items():
			self.assertIn(number, self.by_number, f"account {number} missing from chart")
			self.assertEqual(
				self.by_number[number]["node"].get("account_type"),
				expected_type,
				f"account {number} should be account_type {expected_type!r}",
			)

	def test_key_root_types(self):
		for number, expected_root in EXPECTED_ROOT_TYPES.items():
			self.assertIn(number, self.by_number, f"account {number} missing from chart")
			self.assertEqual(
				self.by_number[number]["root_type"],
				expected_root,
				f"account {number} should live under a {expected_root!r} root",
			)

	def test_single_default_candidates(self):
		# Company default-account detection (`_set_default_account`, create_default_accounts,
		# set_default_accounts) picks the first match with NO ORDER BY, so every
		# account_type that feeds a single company-default field must be tagged on
		# exactly one leaf — otherwise the chosen default is non-deterministic.
		single_default_types = (
			"Cash",  # default_cash_account
			"Bank",  # default_bank_account
			"Receivable",  # default_receivable_account
			"Payable",  # default_payable_account
			"Cost of Goods Sold",  # default_expense_account
			"Stock",  # default_inventory_account
			"Income Account",  # default_income_account
			"Accumulated Depreciation",  # accumulated_depreciation_account
			"Depreciation",  # depreciation_expense_account
			"Capital Work in Progress",  # capital_work_in_progress_account
		)
		for account_type in single_default_types:
			tagged = [
				n
				for n, info in self.by_number.items()
				if info["node"].get("account_type") == account_type
			]
			self.assertEqual(
				len(tagged), 1, f"expected exactly one {account_type} account, got {tagged}"
			)

	def test_parses_via_build_tree(self):
		accounts = chart_of_accounts.build_tree_from_json(CHART_NAME)
		# TT99 lists 71 Cấp-1 accounts plus their Cấp 2-4 children; expect a full tree.
		self.assertGreaterEqual(len(accounts), 130)

	def test_account_numbers_unique(self):
		# _flatten would silently overwrite duplicates; assert none were lost by
		# counting raw account_number occurrences in the file.
		with open(_chart_path(), encoding="utf-8") as f:
			raw = f.read()
		numbers = [
			line.split(":", 1)[1].strip().strip(',').strip('"')
			for line in raw.splitlines()
			if '"account_number"' in line
		]
		self.assertEqual(len(numbers), len(set(numbers)), "duplicate account_number in chart")

	def test_operational_accounts_present(self):
		# Type-based operational accounts must exist with the right account_type so
		# ERPNext auto-wires the stock/asset default fields.
		for name, expected_type in OPERATIONAL_ACCOUNT_TYPES.items():
			self.assertIn(name, self.by_name, f"operational account {name!r} missing")
			self.assertEqual(
				self.by_name[name].get("account_type"),
				expected_type,
				f"{name!r} should be account_type {expected_type!r}",
			)

	def test_operational_named_accounts_present(self):
		# Write Off / Exchange Gain/Loss / Gain-Loss on Asset Disposal are matched by
		# name, so the canonical English name must be present verbatim.
		for name in OPERATIONAL_NAMED_ACCOUNTS:
			self.assertIn(name, self.by_name, f"named operational account {name!r} missing")

	def test_operational_types_are_single(self):
		by_number_and_name = list(self.by_number.values()) + [
			{"node": n} for n in self.by_name.values()
		]
		for account_type in OPERATIONAL_ACCOUNT_TYPES.values():
			tagged = [i for i in by_number_and_name if i["node"].get("account_type") == account_type]
			self.assertEqual(
				len(tagged), 1, f"expected exactly one {account_type} account, got {len(tagged)}"
			)


class TestVietnamCompanyDefaults(FrappeTestCase):
	"""End-to-end: a company created on the VN chart must fill every operational
	default-account field ERPNext needs for stock and asset accounting."""

	def test_company_wires_operational_defaults(self):
		company = frappe.get_doc(
			{
				"doctype": "Company",
				"company_name": "_Test VN TT99 Defaults",
				"abbr": "TVND",
				"default_currency": "VND",
				"country": "Vietnam",
				"chart_of_accounts": CHART_NAME,
				"enable_perpetual_inventory": 1,
			}
		)
		company.flags.ignore_permissions = True
		company.insert()

		for field in COMPANY_OPERATIONAL_DEFAULT_FIELDS:
			self.assertTrue(
				company.get(field),
				f"company default field {field!r} was not populated by the VN chart",
			)


if __name__ == "__main__":
	unittest.main()

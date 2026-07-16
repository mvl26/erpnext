# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

"""Tests for Vietnam statutory books (sổ sách) and voucher print formats (chứng từ in)."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from erpnext.regional.vietnam.setup import _acct
from erpnext.regional.vietnam.test_setup import make_vn_company

VN_PRINT_FORMATS = (
	("phieu_thu_01_tt", "Phiếu thu (01-TT)"),
	("phieu_chi_02_tt", "Phiếu chi (02-TT)"),
	("phieu_nhap_kho_01_vt", "Phiếu nhập kho (01-VT)"),
	("phieu_xuat_kho_02_vt", "Phiếu xuất kho (02-VT)"),
)


def _reload_vn_print_formats():
	for folder, _name in VN_PRINT_FORMATS:
		frappe.reload_doc("regional", "print_format", folder)


def _make_party(doctype, name):
	if doctype == "Customer":
		doc = {
			"doctype": "Customer",
			"customer_name": name,
			"customer_group": "All Customer Groups",
			"territory": "All Territories",
		}
	else:
		doc = {"doctype": "Supplier", "supplier_name": name, "supplier_group": "All Supplier Groups"}
	return frappe.get_doc(doc).insert(ignore_permissions=True, ignore_if_duplicate=True)


def _make_payment_entry(company, payment_type, amount):
	"""Submit a Receive (thu, 131→111) or Pay (chi, 111→331) Payment Entry."""
	receive = payment_type == "Receive"
	party_type = "Customer" if receive else "Supplier"
	party = _make_party(party_type, f"_Test VN PE {party_type}")
	pe = frappe.new_doc("Payment Entry")
	pe.update(
		{
			"company": company,
			"payment_type": payment_type,
			"posting_date": frappe.utils.nowdate(),
			"party_type": party_type,
			"party": party.name,
			"paid_from": _acct(company, "131" if receive else "111"),
			"paid_to": _acct(company, "111" if receive else "331"),
			"paid_amount": amount,
			"received_amount": amount,
			"source_exchange_rate": 1,
			"target_exchange_rate": 1,
			"reference_no": "-",
			"reference_date": frappe.utils.nowdate(),
		}
	)
	pe.flags.ignore_permissions = True
	pe.insert()
	pe.submit()
	return pe


class TestVietnamVoucherPrintFormats(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_reload_vn_print_formats()
		cls.company = make_vn_company("_Test VN Vouchers", "TVVC")

	def test_print_formats_exist(self):
		for _folder, name in VN_PRINT_FORMATS:
			self.assertTrue(frappe.db.exists("Print Format", name), f"missing Print Format {name}")

	def test_phieu_thu_renders_with_amount_in_words(self):
		pe = _make_payment_entry(self.company, "Receive", 1_000_000)
		html = frappe.get_print("Payment Entry", pe.name, print_format="Phiếu thu (01-TT)")
		self.assertIn("PHIẾU THU", html)
		self.assertIn("Một triệu đồng", html)
		self.assertIn(pe.party_name or pe.party, html)

	def test_phieu_chi_renders_with_amount_in_words(self):
		pe = _make_payment_entry(self.company, "Pay", 2_500_000)
		html = frappe.get_print("Payment Entry", pe.name, print_format="Phiếu chi (02-TT)")
		self.assertIn("PHIẾU CHI", html)
		self.assertIn("Hai triệu năm trăm nghìn đồng", html)


def _make_item(name="_Test VN Item Kho"):
	if not frappe.db.exists("Item", name):
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": name,
				"item_name": name,
				"item_group": "All Item Groups",
				"stock_uom": "Nos",
				"is_stock_item": 1,
			}
		).insert(ignore_permissions=True)
	return name


def _leaf_warehouse(company):
	return frappe.db.get_value("Warehouse", {"company": company, "is_group": 0}, "name")


class TestVietnamStockVoucherPrintFormats(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_reload_vn_print_formats()
		cls.company = make_vn_company("_Test VN Kho Vouchers", "TVKV")

	def test_phieu_nhap_kho_renders_with_amount_in_words(self):
		supplier = _make_party("Supplier", "_Test VN Kho Supplier")
		pr = frappe.get_doc(
			{
				"doctype": "Purchase Receipt",
				"company": self.company,
				"supplier": supplier.name,
				"posting_date": frappe.utils.nowdate(),
				"items": [
					{
						"item_code": _make_item(),
						"qty": 10,
						"rate": 100_000,
						"warehouse": _leaf_warehouse(self.company),
					}
				],
			}
		)
		pr.flags.ignore_permissions = True
		pr.insert()
		pr.submit()
		html = frappe.get_print("Purchase Receipt", pr.name, print_format="Phiếu nhập kho (01-VT)")
		self.assertIn("PHIẾU NHẬP KHO", html)
		self.assertIn("_Test VN Item Kho", html)
		self.assertIn("Một triệu đồng", html)

	def test_phieu_xuat_kho_renders_with_amount_in_words(self):
		customer = _make_party("Customer", "_Test VN Kho Customer")
		dn = frappe.get_doc(
			{
				"doctype": "Delivery Note",
				"company": self.company,
				"customer": customer.name,
				"posting_date": frappe.utils.nowdate(),
				"items": [
					{
						"item_code": _make_item(),
						"qty": 2,
						"rate": 1_250_000,
						"warehouse": _leaf_warehouse(self.company),
					}
				],
			}
		)
		dn.flags.ignore_permissions = True
		dn.insert()  # draft render smoke — no stock needed for the print format
		html = frappe.get_print("Delivery Note", dn.name, print_format="Phiếu xuất kho (02-VT)")
		self.assertIn("PHIẾU XUẤT KHO", html)
		self.assertIn("Hai triệu năm trăm nghìn đồng", html)


def _post_je(company, lines, posting_date):
	"""Submit a plain (non-opening) Journal Entry from TT99-number lines."""
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
			},
		)
	je.flags.ignore_permissions = True
	je.insert()
	je.submit()
	return je


class TestVietnamCashBankBooks(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = make_vn_company("_Test VN So Quy", "TVSQ")
		cls.from_date, cls.to_date = "2026-02-01", "2026-02-28"
		# Before the period (opening), then one thu and one chi inside it.
		_post_je(cls.company, [("111", 500_000, 0), ("4211", 0, 500_000)], "2026-01-15")
		_post_je(cls.company, [("111", 1_000_000, 0), ("4211", 0, 1_000_000)], "2026-02-10")
		_post_je(cls.company, [("4211", 300_000, 0), ("111", 0, 300_000)], "2026-02-20")

	def test_so_quy_running_balance_ties_to_gl(self):
		from erpnext.regional.report.so_quy_tien_mat.so_quy_tien_mat import execute

		_cols, rows = execute(
			{"company": self.company, "from_date": self.from_date, "to_date": self.to_date}
		)
		self.assertEqual(flt(rows[0]["balance"]), 500_000)  # số dư đầu kỳ
		self.assertEqual(flt(rows[-1]["balance"]), 1_200_000)  # tồn quỹ cuối kỳ
		total = next(r for r in rows if r.get("is_total"))
		self.assertEqual((flt(total["thu"]), flt(total["chi"])), (1_000_000, 300_000))

	def test_so_quy_requires_filters(self):
		from erpnext.regional.report.so_quy_tien_mat.so_quy_tien_mat import execute

		_cols, rows = execute({"company": self.company})
		self.assertEqual(rows, [])

	def test_so_tien_gui_running_balance_ties_to_gl(self):
		from erpnext.regional.report.so_tien_gui_ngan_hang.so_tien_gui_ngan_hang import execute

		_post_je(self.company, [("112", 2_000_000, 0), ("4211", 0, 2_000_000)], "2026-02-05")
		_post_je(self.company, [("4211", 450_000, 0), ("112", 0, 450_000)], "2026-02-25")
		_cols, rows = execute(
			{"company": self.company, "from_date": self.from_date, "to_date": self.to_date}
		)
		self.assertEqual(flt(rows[0]["balance"]), 0)  # no bank opening before the period
		self.assertEqual(flt(rows[-1]["balance"]), 1_550_000)
		total = next(r for r in rows if r.get("is_total"))
		self.assertEqual((flt(total["thu"]), flt(total["chi"])), (2_000_000, 450_000))
		# The cash book (111*) is unaffected by bank movements.
		from erpnext.regional.report.so_quy_tien_mat.so_quy_tien_mat import execute as cash_execute

		_c, cash_rows = cash_execute(
			{"company": self.company, "from_date": self.from_date, "to_date": self.to_date}
		)
		self.assertEqual(flt(cash_rows[-1]["balance"]), 1_200_000)


def _post_party_je(company, number, party_type, party, dr, cr, posting_date):
	"""Submit a JE moving a receivable/payable account against equity 4211."""
	je = frappe.new_doc("Journal Entry")
	je.company = company
	je.posting_date = posting_date
	je.append(
		"accounts",
		{
			"account": _acct(company, number),
			"party_type": party_type,
			"party": party,
			"debit_in_account_currency": dr,
			"credit_in_account_currency": cr,
		},
	)
	je.append(
		"accounts",
		{"account": _acct(company, "4211"), "debit_in_account_currency": cr, "credit_in_account_currency": dr},
	)
	je.flags.ignore_permissions = True
	je.insert()
	je.submit()
	return je


class TestVietnamPartyLedger(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = make_vn_company("_Test VN Cong No", "TVCN")
		cls.from_date, cls.to_date = "2026-03-01", "2026-03-31"
		cls.c1 = _make_party("Customer", "_Test VN CN Cust 1").name
		cls.c2 = _make_party("Customer", "_Test VN CN Cust 2").name
		# C1: opening 700k, +1,000k in period, -300k thu nợ. C2: +200k in period.
		_post_party_je(cls.company, "131", "Customer", cls.c1, 700_000, 0, "2026-02-15")
		_post_party_je(cls.company, "131", "Customer", cls.c1, 1_000_000, 0, "2026-03-10")
		_post_party_je(cls.company, "131", "Customer", cls.c1, 0, 300_000, "2026-03-20")
		_post_party_je(cls.company, "131", "Customer", cls.c2, 200_000, 0, "2026-03-12")

	def _rows(self, **extra):
		from erpnext.regional.report.so_chi_tiet_cong_no.so_chi_tiet_cong_no import execute

		filters = {"company": self.company, "from_date": self.from_date, "to_date": self.to_date}
		filters.update(extra)
		return execute(filters)[1]

	def test_per_party_closing_ties_to_gl(self):
		rows = self._rows(party_type="Customer")
		closing = {r["party"]: flt(r["balance"]) for r in rows if r.get("is_closing")}
		self.assertEqual(closing.get(self.c1), 1_400_000)
		self.assertEqual(closing.get(self.c2), 200_000)

	def test_party_filter_narrows_to_one_party(self):
		rows = self._rows(party_type="Customer", party=self.c1)
		parties = {r.get("party") for r in rows if r.get("party")}
		self.assertEqual(parties, {self.c1})
		closing = next(r for r in rows if r.get("is_closing"))
		self.assertEqual(flt(closing["balance"]), 1_400_000)

	def test_so_nguyen_te_ledger_ties_both_currencies(self):
		from erpnext.regional.report.so_chi_tiet_nguyen_te.so_chi_tiet_nguyen_te import execute

		company = make_vn_company("_Test VN Ngoai Te", "TVNT")
		frappe.db.set_value("Currency", "USD", "enabled", 1)
		parent = frappe.db.get_value(
			"Account", {"company": company, "is_group": 1, "root_type": "Asset"}, "name"
		)
		usd_account = (
			frappe.get_doc(
				{
					"doctype": "Account",
					"account_name": "Tiền gửi ngân hàng USD",
					"account_number": "1122",
					"company": company,
					"parent_account": parent,
					"root_type": "Asset",
					"account_currency": "USD",
					"is_group": 0,
				}
			)
			.insert(ignore_permissions=True)
			.name
		)
		je = frappe.new_doc("Journal Entry")
		je.company = company
		je.posting_date = "2026-04-10"
		je.multi_currency = 1
		je.append(
			"accounts",
			{"account": usd_account, "exchange_rate": 25_000, "debit_in_account_currency": 1_000},
		)
		je.append(
			"accounts", {"account": _acct(company, "4211"), "credit_in_account_currency": 25_000_000}
		)
		je.flags.ignore_permissions = True
		je.insert()
		je.submit()

		_cols, rows = execute({"company": company, "from_date": "2026-04-01", "to_date": "2026-04-30"})
		entry = next(r for r in rows if r.get("voucher_no"))
		self.assertEqual(entry["currency"], "USD")
		self.assertEqual(flt(entry["debit_nt"]), 1_000)
		self.assertEqual(flt(entry["debit_vnd"]), 25_000_000)
		closing = next(r for r in rows if r.get("is_closing"))
		self.assertEqual(flt(closing["balance_nt"]), 1_000)
		self.assertEqual(flt(closing["balance_vnd"]), 25_000_000)

	def test_partyless_rows_are_surfaced(self):
		# Simulate a legacy/imported 131 row that slipped in without a party.
		gle = frappe.new_doc("GL Entry")
		gle.update(
			{
				"name": frappe.generate_hash(length=10),
				"company": self.company,
				"account": _acct(self.company, "131"),
				"posting_date": "2026-03-15",
				"debit": 50_000,
				"credit": 0,
				"voucher_type": "Journal Entry",
				"voucher_no": "_TEST-MANUAL",
				"is_cancelled": 0,
			}
		)
		gle.db_insert()
		rows = self._rows(party_type="Customer")
		bucket = [r for r in rows if r.get("is_closing") and not r.get("party_link")]
		self.assertTrue(any("không có đối tượng" in (r.get("party") or "") for r in bucket))

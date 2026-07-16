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

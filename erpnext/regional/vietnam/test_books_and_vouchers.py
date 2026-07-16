# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

"""Tests for Vietnam statutory books (sổ sách) and voucher print formats (chứng từ in)."""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.regional.vietnam.setup import _acct
from erpnext.regional.vietnam.test_setup import make_vn_company

VN_PRINT_FORMATS = (
	("phieu_thu_01_tt", "Phiếu thu (01-TT)"),
	("phieu_chi_02_tt", "Phiếu chi (02-TT)"),
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

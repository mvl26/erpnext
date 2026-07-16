# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

"""Tests for Tờ khai thuế GTGT (mẫu 01/GTGT)."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import nowdate

from erpnext.regional.report.to_khai_thue_gtgt_01.to_khai_thue_gtgt_01 import execute

CHART_NAME = "Vietnam - Chart of Accounts (Thông tư 99/2025/TT-BTC)"


class TestToKhaiThueGTGT(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		company = frappe.get_doc(
			{
				"doctype": "Company",
				"company_name": "_Test VN GTGT Return",
				"abbr": "TVGR",
				"default_currency": "VND",
				"country": "Vietnam",
				"chart_of_accounts": CHART_NAME,
			}
		)
		company.flags.ignore_permissions = True
		company.insert()
		cls.company = company.name
		cc = frappe.db.get_value("Company", cls.company, "cost_center")

		def acc(number):
			return frappe.db.get_value(
				"Account", {"company": cls.company, "account_number": number, "is_group": 0}, "name"
			)

		# Bán hàng có thuế GTGT đầu ra 10%
		sale = frappe.get_doc(
			{
				"doctype": "Journal Entry",
				"company": cls.company,
				"posting_date": nowdate(),
				"accounts": [
					{"account": acc("111"), "debit_in_account_currency": 11_000_000},
					{"account": acc("511"), "credit_in_account_currency": 10_000_000, "cost_center": cc},
					{"account": acc("33311"), "credit_in_account_currency": 1_000_000},
				],
			}
		)
		sale.flags.ignore_permissions = True
		sale.insert()
		sale.submit()

		# Mua hàng có thuế GTGT đầu vào được khấu trừ
		purchase = frappe.get_doc(
			{
				"doctype": "Journal Entry",
				"company": cls.company,
				"posting_date": nowdate(),
				"accounts": [
					{"account": acc("152"), "debit_in_account_currency": 5_000_000},
					{"account": acc("1331"), "debit_in_account_currency": 500_000},
					{"account": acc("3388"), "credit_in_account_currency": 5_500_000},
				],
			}
		)
		purchase.flags.ignore_permissions = True
		purchase.insert()
		purchase.submit()

	def _run(self):
		result = execute(
			frappe._dict(company=self.company, from_date="1900-01-01", to_date=nowdate())
		)
		return {r["chi_tieu_code"]: r["so_tien"] for r in result[1] if r.get("chi_tieu_code")}

	def test_vat_return_totals(self):
		v = self._run()
		self.assertEqual(v["33"], 1_000_000)  # thuế GTGT đầu ra
		self.assertEqual(v["25"], 500_000)  # thuế GTGT được khấu trừ kỳ này
		self.assertEqual(v["40"], 500_000)  # thuế GTGT phải nộp = đầu ra - khấu trừ
		self.assertEqual(v["41"], 0)  # chưa khấu trừ hết


class TestBangKeGTGT(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		from erpnext.regional.vietnam.setup import _acct
		from erpnext.regional.vietnam.test_setup import make_vn_company

		cls.company = make_vn_company("_Test VN Bang Ke", "TVBK")
		cls.to_date = nowdate()

		customer = frappe.get_doc(
			{
				"doctype": "Customer",
				"customer_name": "_Test VN BK Customer",
				"customer_group": "All Customer Groups",
				"territory": "All Territories",
				"tax_id": "0312345678",
			}
		).insert(ignore_permissions=True)
		supplier = frappe.get_doc(
			{
				"doctype": "Supplier",
				"supplier_name": "_Test VN BK Supplier",
				"supplier_group": "All Supplier Groups",
				"tax_id": "0398765432",
			}
		).insert(ignore_permissions=True)
		if not frappe.db.exists("Item", "_Test VN BK Service"):
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": "_Test VN BK Service",
					"item_name": "_Test VN BK Service",
					"item_group": "All Item Groups",
					"stock_uom": "Nos",
					"is_stock_item": 0,
				}
			).insert(ignore_permissions=True)

		si = frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"company": cls.company,
				"customer": customer.name,
				"posting_date": cls.to_date,
				"items": [{"item_code": "_Test VN BK Service", "qty": 1, "rate": 10_000_000}],
				"taxes": [
					{
						"charge_type": "On Net Total",
						"account_head": _acct(cls.company, "33311"),
						"rate": 10,
						"description": "Thuế GTGT đầu ra 10%",
					}
				],
			}
		)
		si.flags.ignore_permissions = True
		si.insert()
		si.submit()
		cls.si = si

		pi = frappe.get_doc(
			{
				"doctype": "Purchase Invoice",
				"company": cls.company,
				"supplier": supplier.name,
				"posting_date": cls.to_date,
				"items": [{"item_code": "_Test VN BK Service", "qty": 1, "rate": 5_000_000}],
				"taxes": [
					{
						"charge_type": "On Net Total",
						"account_head": _acct(cls.company, "1331"),
						"rate": 10,
						"description": "Thuế GTGT đầu vào 10%",
						"category": "Total",
						"add_deduct_tax": "Add",
					}
				],
			}
		)
		pi.flags.ignore_permissions = True
		pi.insert()
		pi.submit()
		cls.pi = pi

	def test_bang_ke_ban_ra_ties_to_declaration(self):
		from erpnext.regional.report.to_khai_thue_gtgt_01.to_khai_thue_gtgt_01 import bang_ke_ban_ra

		rows = bang_ke_ban_ra(self.company, "1900-01-01", self.to_date)
		self.assertEqual(len(rows), 1)
		row = rows[0]
		self.assertEqual(row["so_hoa_don"], self.si.name)  # no HĐĐT issued → ERP number
		self.assertEqual(row["mst"], "0312345678")
		self.assertEqual(row["doanh_so"], 10_000_000)
		self.assertEqual(row["thue_suat"], 10)
		self.assertEqual(row["tien_thue"], 1_000_000)

		decl = execute(
			frappe._dict(company=self.company, from_date="1900-01-01", to_date=self.to_date)
		)[1]
		output_vat = next(r["so_tien"] for r in decl if r.get("chi_tieu_code") == "33")
		self.assertEqual(sum(r["tien_thue"] for r in rows), output_vat)

	def test_bang_ke_mua_vao_ties_to_declaration(self):
		from erpnext.regional.report.to_khai_thue_gtgt_01.to_khai_thue_gtgt_01 import bang_ke_mua_vao

		rows = bang_ke_mua_vao(self.company, "1900-01-01", self.to_date)
		self.assertEqual(len(rows), 1)
		row = rows[0]
		self.assertEqual(row["mst"], "0398765432")
		self.assertEqual(row["doanh_so"], 5_000_000)
		self.assertEqual(row["tien_thue"], 500_000)

		decl = execute(
			frappe._dict(company=self.company, from_date="1900-01-01", to_date=self.to_date)
		)[1]
		input_vat = next(r["so_tien"] for r in decl if r.get("chi_tieu_code") == "25")
		self.assertEqual(sum(r["tien_thue"] for r in rows), input_vat)

	def test_export_bang_ke_csv(self):
		from erpnext.regional.report.to_khai_thue_gtgt_01.to_khai_thue_gtgt_01 import export_bang_ke

		csv_out = export_bang_ke(self.company, "1900-01-01", self.to_date, kind="ban_ra")
		self.assertIn("Số hóa đơn", csv_out)
		self.assertIn("_Test VN BK Customer", csv_out)
		self.assertIn("0312345678", csv_out)

	def test_export_xml_indicators(self):
		import xml.etree.ElementTree as ET

		from erpnext.regional.report.to_khai_thue_gtgt_01.to_khai_thue_gtgt_01 import export_to_khai_xml

		frappe.db.set_value("Company", self.company, "tax_id", "0301234567")
		xml_out = export_to_khai_xml(self.company, "1900-01-01", self.to_date, ky_khai="3/2026")
		root = ET.fromstring(xml_out)
		self.assertEqual(root.findtext(".//maTKhai"), "842")
		self.assertEqual(root.findtext(".//mst"), "0301234567")
		self.assertEqual(root.findtext(".//tenNNT"), self.company)
		self.assertEqual(root.findtext(".//kyKKhai"), "3/2026")
		self.assertEqual(root.findtext(".//ct33"), "1000000")
		self.assertEqual(root.findtext(".//ct25"), "500000")
		self.assertEqual(root.findtext(".//ct40"), "500000")
		self.assertEqual(root.findtext(".//ct41"), "0")

	def test_export_xml_matches_golden(self):
		from pathlib import Path

		from erpnext.regional.report.to_khai_thue_gtgt_01.to_khai_thue_gtgt_01 import export_to_khai_xml

		frappe.db.set_value("Company", self.company, "tax_id", "0301234567")
		xml_out = export_to_khai_xml(self.company, "1900-01-01", self.to_date, ky_khai="3/2026")
		golden = (Path(__file__).parent / "golden_01_gtgt.xml").read_text(encoding="utf-8")
		self.assertEqual(xml_out.strip(), golden.strip())

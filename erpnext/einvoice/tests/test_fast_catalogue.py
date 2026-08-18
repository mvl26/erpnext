# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Tra danh mục hàng hóa cho dòng hóa đơn — `einvoice.catalogue`.

Nguyên tắc xuyên suốt: **chỉ trả về khóa nào tra được**. Trả về ô rỗng rồi để
giao diện ghi đè là xóa mất số kế toán vừa gõ, và với hóa đơn thì đó là làm sai
chứng từ chứ không phải tiện lợi.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.einvoice.catalogue import item_defaults
from erpnext.einvoice.tests.test_fixtures import ITEM_CODE, ITEM_NAME, ensure_item, ensure_uom

PRICE_LIST = "_Test HĐĐT Bảng giá bán"


def _insert(doc):
	doc.flags.ignore_permissions = True
	doc.flags.ignore_mandatory = True
	doc.insert(ignore_if_duplicate=True)
	return doc


def ensure_price_list():
	if not frappe.db.exists("Price List", PRICE_LIST):
		_insert(
			frappe.get_doc(
				{
					"doctype": "Price List",
					"price_list_name": PRICE_LIST,
					"selling": 1,
					"enabled": 1,
					"currency": "VND",
				}
			)
		)
	frappe.db.set_single_value("Selling Settings", "selling_price_list", PRICE_LIST)
	return PRICE_LIST


class CatalogueBase(FrappeTestCase):
	def setUp(self):
		frappe.db.rollback()
		ensure_item()
		ensure_price_list()

	def tearDown(self):
		frappe.db.rollback()


class TestNameAndUom(CatalogueBase):
	def test_an_unknown_item_yields_nothing(self):
		self.assertEqual(item_defaults("_TEST-KHONG-CO-MA-NAY"), {})

	def test_item_name_always_comes_back(self):
		self.assertEqual(item_defaults(ITEM_CODE)["item_name"], ITEM_NAME)

	def test_stock_uom_is_used_when_there_is_no_sales_uom(self):
		self.assertEqual(item_defaults(ITEM_CODE)["uom"], "Cái")

	def test_sales_uom_wins_over_stock_uom(self):
		"""Đơn vị bán mới là đơn vị ghi trên hóa đơn."""
		ensure_uom("Hộp")
		frappe.db.set_value("Item", ITEM_CODE, "sales_uom", "Hộp")

		self.assertEqual(item_defaults(ITEM_CODE)["uom"], "Hộp")


class TestPrice(CatalogueBase):
	def _set_price(self, rate):
		_insert(
			frappe.get_doc(
				{
					"doctype": "Item Price",
					"item_code": ITEM_CODE,
					"price_list": PRICE_LIST,
					"selling": 1,
					"price_list_rate": rate,
				}
			)
		)

	def test_no_price_in_the_list_leaves_the_field_alone(self):
		"""Chưa khai giá thì không được trả về 0 — số 0 sẽ xóa đơn giá đã gõ."""
		self.assertNotIn("price", item_defaults(ITEM_CODE, currency="VND"))

	def test_a_declared_price_is_returned(self):
		self._set_price(123456)
		self.assertEqual(item_defaults(ITEM_CODE, currency="VND")["price"], 123456)

	def test_a_price_in_another_currency_is_ignored(self):
		"""Hóa đơn ngoại tệ không được lấy giá của bảng giá VND.

		ERPNext ép ``Item Price.currency`` theo bảng giá, nên ca này dựng bằng
		cách hỏi giá cho hóa đơn USD trong khi bảng giá mặc định là VND.
		"""
		self._set_price(123456)
		self.assertNotIn("price", item_defaults(ITEM_CODE, currency="USD"))

	def test_a_zero_price_is_treated_as_not_declared(self):
		self._set_price(0)
		self.assertNotIn("price", item_defaults(ITEM_CODE, currency="VND"))


class TestTaxRate(CatalogueBase):
	def _set_template(self, *rates):
		"""Khai một nhóm thuế cho item. ``Item Tax Template`` tự sinh tên kèm mã
		công ty (``… - M``) nên phải link theo ``name`` thật, không theo ``title``."""
		# Mỗi dòng một tài khoản khác nhau — ERPNext chặn trùng tài khoản trong nhóm.
		accounts = frappe.get_all(
			"Account",
			filters={"company": "Miyano", "is_group": 0, "account_type": "Tax"},
			pluck="name",
			limit=len(rates),
			order_by="name",
		)
		template = _insert(
			frappe.get_doc(
				{
					"doctype": "Item Tax Template",
					"title": f"_Test HĐĐT Thuế {'-'.join(str(r) for r in rates)}",
					"company": "Miyano",
					"taxes": [
						{"tax_type": account, "tax_rate": rate}
						for account, rate in zip(accounts, rates, strict=True)
					],
				}
			)
		)

		item = frappe.get_doc("Item", ITEM_CODE)
		item.set("taxes", [{"item_tax_template": template.name}])
		item.flags.ignore_permissions = True
		item.flags.ignore_mandatory = True
		item.save()

	def test_an_item_without_a_tax_template_leaves_the_rate_alone(self):
		self.assertNotIn("tax_rate", item_defaults(ITEM_CODE))

	def test_a_single_rate_maps_to_the_fast_code(self):
		self._set_template(10)
		self.assertEqual(item_defaults(ITEM_CODE)["tax_rate"], "10")

	def test_five_percent_maps_too(self):
		self._set_template(5)
		self.assertEqual(item_defaults(ITEM_CODE)["tax_rate"], "5")

	def test_a_rate_fast_has_no_code_for_is_skipped(self):
		"""Fast chỉ có mã cho 0/5/8/10 — thuế suất khác thì để kế toán tự chọn."""
		self._set_template(7)
		self.assertNotIn("tax_rate", item_defaults(ITEM_CODE))

	def test_a_template_with_several_rates_is_skipped(self):
		"""Nhóm thuế nhiều dòng không quy về một mã Fast nào."""
		self._set_template(10, 5)
		self.assertNotIn("tax_rate", item_defaults(ITEM_CODE))

import frappe
from frappe.tests.utils import FrappeTestCase

# Ten thiet bi y te tieng Viet thuong vuot 140 ky tu, nen item_name duoc noi len 500.
ITEM_NAME_LENGTH = 500

# Thuoc app assetcore, khong sua trong repo nay.
EXTERNAL_ITEM_NAME_TABLES = {"tabSpare Parts Used"}


class TestItemNameLength(FrappeTestCase):
	def setUp(self):
		super().setUp()
		self.long_name = ("Máy thở xâm nhập đa chế độ kèm bộ dây bệnh nhân và cảm biến lưu lượng " * 20)[
			:ITEM_NAME_LENGTH
		]
		self.assertEqual(len(self.long_name), ITEM_NAME_LENGTH)

	def test_item_stores_full_500_character_name(self):
		item = frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": "_Test Item Ten Dai 500",
				"item_name": self.long_name,
				"item_group": frappe.db.get_value("Item Group", {"is_group": 0}, "name"),
				"stock_uom": frappe.db.get_value("UOM", {}, "name"),
				"is_stock_item": 1,
			}
		).insert()

		stored = frappe.db.get_value("Item", item.name, "item_name")
		self.assertEqual(len(stored), ITEM_NAME_LENGTH)
		self.assertEqual(stored, self.long_name)

	def test_every_erpnext_item_name_column_is_widened(self):
		"""Mot cot item_name con varchar(140) se lam insert loi 'Data too long' o STRICT mode.

		Day la bat bien that su: item_name duoc fetch tu Item xuong moi bang giao dich,
		nen chi can sot mot cot la tao chung tu cho item ten dai se chet.
		"""
		narrow = frappe.db.sql(
			"""
			select TABLE_NAME
			from information_schema.COLUMNS
			where TABLE_SCHEMA = %s and COLUMN_NAME = 'item_name'
				and CHARACTER_MAXIMUM_LENGTH < %s
			""",
			(frappe.conf.db_name, ITEM_NAME_LENGTH),
			pluck=True,
		)
		unexpected = sorted(set(narrow) - EXTERNAL_ITEM_NAME_TABLES)
		self.assertEqual(unexpected, [], f"Cot item_name chua noi len {ITEM_NAME_LENGTH}: {unexpected}")

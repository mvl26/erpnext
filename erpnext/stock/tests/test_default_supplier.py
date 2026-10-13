# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""NCC mặc định của vật tư nằm ở dòng tích mặc định của bảng Supplier Items.

Cột `default_supplier` của Item Defaults không còn dùng cho vật tư. Các test ở đây chạy
ở chế độ đặt tên "Item Code" trừ khi ghi khác: việc chuyển NCC mặc định không phụ thuộc
quy tắc mã vật tư.
"""

from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.stock.doctype.item.item import get_item_defaults
from erpnext.stock.doctype.item_supplier.item_supplier import (
	get_default_supplier,
	get_default_suppliers,
	get_items_with_default_supplier,
	migrate_default_suppliers,
	set_default_supplier,
)
from erpnext.stock.tests.test_item_code_rule import (
	RULE,
	make_brand,
	make_group,
	make_supplier,
	new_item,
	next_group_code,
	use_naming_mode,
)


class DefaultSupplierCase(FrappeTestCase):
	def setUp(self):
		frappe.db.savepoint("default_supplier_test")
		self.addCleanup(frappe.db.rollback, save_point="default_supplier_test")
		self.sfx = frappe.generate_hash(length=6)
		self.company = frappe.db.get_value("Company", {}, "name")
		self.group = make_group(next_group_code())
		self.first = make_supplier(f"{self.sfx}-1")
		self.second = make_supplier(f"{self.sfx}-2")
		use_naming_mode(self, "Item Code")

	def item(self, suppliers=(), typed=None, label="A"):
		"""Vật tư mang mã đặt tay. `typed` là NCC ghi vào ô Default Supplier của Item Defaults."""
		fields = {"item_code": f"_TEST-NCC-{self.sfx}-{label}"}
		if typed:
			fields["item_defaults"] = [{"company": self.company, "default_supplier": typed}]
		return new_item(self.group, None, suppliers, **fields).insert()

	def old_values(self, item_code):
		"""Những gì còn nằm ở cột Default Supplier của Item Defaults."""
		return set(
			frappe.get_all(
				"Item Default", filters={"parent": item_code, "parenttype": "Item"}, pluck="default_supplier"
			)
		)

	def plant_old_value(self, item_code, supplier):
		"""Ghi thẳng vào cột cũ, như dữ liệu có từ trước khi NCC mặc định chuyển sang Supplier Items."""
		frappe.db.set_value(
			"Item Default", {"parent": item_code, "parenttype": "Item"}, "default_supplier", supplier
		)
		frappe.clear_document_cache("Item", item_code)

	def ticked(self, item_code):
		return frappe.get_all(
			"Item Supplier",
			filters={"parent": item_code, "parenttype": "Item", "is_default": 1},
			pluck="supplier",
		)


class TestWhoIsTheDefaultSupplier(DefaultSupplierCase):
	def test_it_is_the_supplier_of_the_ticked_row(self):
		item = self.item([(self.first, "A1"), (self.second, "B2", 1)])

		self.assertEqual(get_default_supplier(item.name), self.second)

	def test_an_item_with_no_ticked_row_has_none(self):
		item = self.item([(self.first, "A1"), (self.second, "B2")])

		self.assertIsNone(get_default_supplier(item.name))

	def test_the_old_column_no_longer_counts(self):
		ticked = self.item([(self.first, "A1", 1)], label="A")
		unticked = self.item([(self.first, "A1"), (self.second, "B2")], label="B")
		self.plant_old_value(ticked.name, self.second)
		self.plant_old_value(unticked.name, self.second)

		self.assertEqual(get_default_supplier(ticked.name), self.first)
		self.assertIsNone(get_default_supplier(unticked.name))
		self.assertEqual(get_items_with_default_supplier(self.first), [ticked.name])
		self.assertEqual(get_items_with_default_supplier(self.second), [])

	def test_several_items_are_answered_at_once(self):
		ticked = self.item([(self.first, "A1", 1)], label="A")
		none = self.item([(self.first, "A1"), (self.second, "B2")], label="B")

		self.assertEqual(get_default_suppliers([ticked.name, none.name, None]), {ticked.name: self.first})


class TestSavingAnItem(DefaultSupplierCase):
	def test_ticking_another_row_moves_the_default(self):
		item = self.item([(self.first, "A1", 1), (self.second, "B2")])
		item.supplier_items[0].is_default = 0
		item.supplier_items[1].is_default = 1

		item.save()

		self.assertEqual(get_default_supplier(item.name), self.second)

	def test_unticking_leaves_the_item_without_a_default_supplier(self):
		item = self.item([(self.first, "A1", 1), (self.second, "B2")])
		item.supplier_items[0].is_default = 0

		item.save()

		self.assertIsNone(get_default_supplier(item.name))

	def test_deleting_every_supplier_row_leaves_no_default_supplier(self):
		item = self.item([(self.first, "A1", 1)])
		item.set("supplier_items", [])

		item.save()

		self.assertIsNone(get_default_supplier(item.name))
		self.assertEqual(item.supplier_items, [])

	def test_only_one_row_is_not_ticked_for_the_user_outside_rule_mode(self):
		item = self.item([(self.first, "A1")])

		self.assertEqual(item.supplier_items[0].is_default, 0)
		self.assertIsNone(get_default_supplier(item.name))

	def test_nothing_is_written_to_the_old_column(self):
		item = self.item([(self.first, "A1", 1)])

		self.assertEqual(self.old_values(item.name), {None})

	# --- NCC mặc định vẫn tới qua ô cũ: Data Import, API, kế thừa từ Nhóm hàng ---

	def test_a_supplier_written_to_the_old_column_becomes_the_ticked_row(self):
		item = self.item(typed=self.first)

		self.assertEqual([(row.supplier, row.is_default) for row in item.supplier_items], [(self.first, 1)])
		self.assertEqual(self.old_values(item.name), {None})

	def test_it_ticks_the_row_the_item_already_lists(self):
		item = self.item([(self.first, "A1"), (self.second, "B2")], typed=self.second)

		self.assertEqual([row.is_default for row in item.supplier_items], [0, 1])
		self.assertEqual(len(item.supplier_items), 2)

	def test_a_row_ticked_by_the_user_is_not_overruled(self):
		item = self.item([(self.first, "A1", 1), (self.second, "B2")], typed=self.second)

		self.assertEqual(get_default_supplier(item.name), self.first)
		self.assertEqual(self.old_values(item.name), {None})

	def test_an_item_from_before_the_move_is_moved_when_it_is_saved(self):
		item = self.item()
		self.plant_old_value(item.name, self.first)
		item.reload()
		item.description = "Sửa một ô khác"

		item.save()

		self.assertEqual(get_default_supplier(item.name), self.first)
		self.assertEqual(self.old_values(item.name), {None})

	def test_a_new_item_inherits_the_default_supplier_of_its_group(self):
		group = frappe.get_doc("Item Group", self.group)
		group.append("item_group_defaults", {"company": self.company, "default_supplier": self.second})
		group.save()

		item = self.item()

		self.assertEqual(get_default_supplier(item.name), self.second)
		# Nhóm hàng vẫn khai NCC mặc định ở bảng defaults của nó.
		self.assertEqual(
			frappe.db.get_value(
				"Item Default", {"parent": self.group, "parenttype": "Item Group"}, "default_supplier"
			),
			self.second,
		)


class TestFlowsReadTheTickedRow(DefaultSupplierCase):
	"""Mỗi luồng từng đọc `Item Default.default_supplier`, nay phải theo dòng tích mặc định."""

	def setUp(self):
		super().setUp()
		self.stock_item = self.item([(self.first, "A1"), (self.second, "B2", 1)])
		# Cột cũ bị gài một NCC khác: luồng nào còn đọc nó sẽ ra `first`.
		self.plant_old_value(self.stock_item.name, self.first)

	def test_item_defaults_used_by_transactions(self):
		defaults = get_item_defaults(self.stock_item.name, self.company)

		self.assertEqual(defaults.default_supplier, self.second)

	def test_item_defaults_of_an_item_without_a_default_supplier(self):
		none = self.item([(self.first, "A1"), (self.second, "B2")], label="B")
		self.plant_old_value(none.name, self.first)

		self.assertIsNone(get_item_defaults(none.name, self.company).default_supplier)

	def test_item_details_fall_back_to_the_group_and_the_brand(self):
		from erpnext.stock.get_item_details import get_default_supplier as for_transaction

		item_defaults = get_item_defaults(self.stock_item.name, self.company)
		none = self.item([(self.first, "A1"), (self.second, "B2")], label="B")
		none_defaults = get_item_defaults(none.name, self.company)

		self.assertEqual(for_transaction({}, item_defaults, {"default_supplier": "GROUP"}, {}), self.second)
		self.assertEqual(for_transaction({}, none_defaults, {"default_supplier": "GROUP"}, {}), "GROUP")
		self.assertEqual(for_transaction({}, none_defaults, {}, {"default_supplier": "BRAND"}), "BRAND")

	def test_purchase_document_takes_the_supplier_of_its_first_item(self):
		order = frappe.new_doc("Purchase Order")
		order.company = self.company
		order.append("items", {"item_code": self.stock_item.name})

		order.set_supplier_from_item_default()

		self.assertEqual(order.supplier, self.second)

	def test_material_request_lists_the_items_of_a_supplier(self):
		from erpnext.stock.doctype.material_request.material_request import (
			get_items_based_on_default_supplier,
		)

		self.assertIn(self.stock_item.name, get_items_based_on_default_supplier(self.second))
		self.assertNotIn(self.stock_item.name, get_items_based_on_default_supplier(self.first))

	def test_material_request_offers_the_default_suppliers_of_its_items(self):
		from erpnext.stock.doctype.material_request import material_request

		request = SimpleNamespace(
			company=self.company, items=[SimpleNamespace(item_code=self.stock_item.name)]
		)
		with patch.object(material_request.frappe, "get_doc", return_value=request):
			found = material_request.get_default_supplier_query(
				"Supplier", "", "name", 0, 20, {"doc": "MAT-MR-TEST"}
			)

		self.assertEqual([row[0] for row in found], [self.second])

	def test_material_request_offers_nothing_when_no_item_has_a_default_supplier(self):
		from erpnext.stock.doctype.material_request import material_request

		none = self.item([(self.first, "A1"), (self.second, "B2")], label="B")
		request = SimpleNamespace(company=self.company, items=[SimpleNamespace(item_code=none.name)])
		with patch.object(material_request.frappe, "get_doc", return_value=request):
			found = material_request.get_default_supplier_query(
				"Supplier", "", "name", 0, 20, {"doc": "MAT-MR-TEST"}
			)

		self.assertEqual(found, [])

	def test_production_plan_fills_the_subcontractor(self):
		plan = frappe.new_doc("Production Plan")
		plan.append(
			"sub_assembly_items",
			{"production_item": self.stock_item.name, "type_of_manufacturing": "Subcontract"},
		)

		plan.set_default_supplier_for_subcontracting_order()

		self.assertEqual(plan.sub_assembly_items[0].supplier, self.second)


class TestSettingTheDefaultSupplier(DefaultSupplierCase):
	def test_an_existing_row_is_ticked_and_the_others_unticked(self):
		item = self.item([(self.first, "A1", 1), (self.second, "B2")])

		set_default_supplier(item.name, self.second)

		self.assertEqual(self.ticked(item.name), [self.second])

	def test_a_supplier_the_item_does_not_list_yet_is_added(self):
		item = self.item([(self.first, "A1", 1)])

		set_default_supplier(item.name, self.second)

		self.assertEqual(self.ticked(item.name), [self.second])
		self.assertEqual(frappe.db.count("Item Supplier", {"parent": item.name, "parenttype": "Item"}), 2)

	def test_the_quotation_comparison_report_sets_it_on_the_item(self):
		from erpnext.buying.report.supplier_quotation_comparison import supplier_quotation_comparison

		item = self.item([(self.first, "A1", 1)])

		supplier_quotation_comparison.set_default_supplier(item.name, self.second, self.company)

		self.assertEqual(get_default_supplier(item.name), self.second)

	def test_a_user_without_write_access_to_the_item_cannot_set_it(self):
		item = self.item([(self.first, "A1", 1)])
		user = frappe.new_doc("User")
		user.email = f"_test_ncc_{self.sfx}@example.com"
		user.first_name = "NCC"
		user.send_welcome_email = 0
		user.append("roles", {"role": "Purchase User"})
		user.insert(ignore_permissions=True)
		frappe.set_user(user.name)
		self.addCleanup(frappe.set_user, "Administrator")

		self.assertRaises(frappe.PermissionError, set_default_supplier, item.name, self.second)

	def test_under_the_code_rule_the_item_code_follows_the_new_default_supplier(self):
		use_naming_mode(self, RULE)
		tok = self.sfx.upper()
		brand = make_brand(f"B{self.sfx[:5]}")
		item = new_item(self.group, brand, [(self.first, f"N{tok}", 1), (self.second, f"Q{tok}")]).insert()

		new_name = set_default_supplier(item.name, self.second)

		self.assertTrue(new_name.endswith(f"-Q{tok}"))
		self.assertEqual(get_default_supplier(new_name), self.second)


class TestMovingOldData(DefaultSupplierCase):
	"""`migrate_default_suppliers`: dữ liệu có từ trước khi NCC mặc định chuyển sang Supplier Items."""

	def test_an_old_value_without_any_row_becomes_a_ticked_row(self):
		item = self.item()
		self.plant_old_value(item.name, self.first)

		migrate_default_suppliers()

		self.assertEqual(self.ticked(item.name), [self.first])
		self.assertEqual(self.old_values(item.name), {None})

	def test_the_row_of_that_supplier_is_ticked(self):
		item = self.item([(self.first, "A1"), (self.second, "B2")])
		self.plant_old_value(item.name, self.second)

		migrate_default_suppliers()

		self.assertEqual(self.ticked(item.name), [self.second])
		self.assertEqual(frappe.db.count("Item Supplier", {"parent": item.name, "parenttype": "Item"}), 2)

	def test_the_old_value_wins_over_a_ticked_row_on_a_handmade_code(self):
		item = self.item([(self.first, "A1", 1)])
		self.plant_old_value(item.name, self.second)

		migrate_default_suppliers()

		self.assertEqual(self.ticked(item.name), [self.second])

	def test_the_ticked_row_wins_on_a_code_made_by_the_rule(self):
		item = self.item([(self.first, "A1", 1)])
		frappe.db.set_value("Item", item.name, "item_code_by_rule", 1)
		self.plant_old_value(item.name, self.second)

		migrate_default_suppliers()

		self.assertEqual(self.ticked(item.name), [self.first])
		self.assertEqual(self.old_values(item.name), {None})

	def test_when_companies_disagree_the_first_wins_and_the_rest_is_noted_on_the_item(self):
		item = self.item()
		self.plant_old_value(item.name, self.first)
		frappe.get_doc(
			{
				"doctype": "Item Default",
				"parent": item.name,
				"parenttype": "Item",
				"parentfield": "item_defaults",
				"idx": 2,
				"company": f"_Test NCC Company {self.sfx}",
				"default_supplier": self.second,
			}
		).db_insert()

		disagreeing = migrate_default_suppliers()

		self.assertIn(item.name, disagreeing)
		self.assertEqual(self.ticked(item.name), [self.first])
		note = frappe.db.get_value(
			"Comment",
			{"reference_doctype": "Item", "reference_name": item.name, "comment_type": "Info"},
			"content",
		)
		self.assertIn(self.second, note)

	def test_the_defaults_of_item_groups_and_brands_are_not_touched(self):
		group = frappe.get_doc("Item Group", self.group)
		group.append("item_group_defaults", {"company": self.company, "default_supplier": self.second})
		group.save()

		migrate_default_suppliers()

		self.assertEqual(
			frappe.db.get_value(
				"Item Default", {"parent": self.group, "parenttype": "Item Group"}, "default_supplier"
			),
			self.second,
		)

	def test_running_it_twice_changes_nothing_more(self):
		item = self.item()
		self.plant_old_value(item.name, self.first)
		migrate_default_suppliers()

		self.assertEqual(migrate_default_suppliers(), [])
		self.assertEqual(frappe.db.count("Item Supplier", {"parent": item.name, "parenttype": "Item"}), 1)

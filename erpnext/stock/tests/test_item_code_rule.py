# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Quy tắc sinh mã vật tư — docs/ke-hoach-build-sinh-ma-vat-tu.md.

FrappeTestCase chỉ rollback ở cấp class, mà phát hiện trùng thì nhìn toàn bộ vật
tư đang có: để nguyên như vậy thì vật tư mang mã hàng `N12345` của test này sẽ
thành "có thể trùng" trong test sau. `ItemCodeRuleCase` vì thế rollback về
savepoint sau từng test.
"""

import itertools
import string
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase, change_settings

from erpnext.stock import item_code_rule
from erpnext.stock.item_code_rule import DuplicateItemError, ItemCodeRuleError

RULE = item_code_rule.RULE_MODE


def use_naming_mode(test, mode):
	"""Coi như Stock Settings đang ở `mode` cho đến hết test.

	Không ghi thật vào `item_naming_by`: giá trị đó nằm trong cache Redis dùng
	chung với web server và worker đang chạy. Ghi trong một transaction chưa
	commit thì tiến trình khác vừa nạp lại cache bằng giá trị cũ (test lúc được
	lúc không), vừa có lúc thấy chế độ của test. Đường đọc thật do
	`TestStockSettings` kiểm.
	"""
	patcher = patch.object(item_code_rule, "is_rule_mode", return_value=mode == RULE)
	patcher.start()
	test.addCleanup(patcher.stop)


_group_numbers = itertools.count()


def next_group_code():
	"""Mã nhóm 3 ký tự, không lặp lại trong một lần chạy test."""
	digits = string.digits + string.ascii_uppercase
	number = next(_group_numbers)
	return "G" + digits[number // 36 % 36] + digits[number % 36]


def make_group(code, name=None):
	"""Nhóm hàng với mã nhóm `code`. `code=None`: nhóm có từ trước quy tắc, chưa có mã."""
	doc = frappe.new_doc("Item Group")
	doc.item_group_name = name or f"_Test ICR Group {code or frappe.generate_hash(length=6)}"
	doc.parent_item_group = "All Item Groups"
	doc.item_group_code = code
	return _insert_master(doc)


def make_brand(code, name=None):
	"""Thương hiệu với mã thương hiệu `code`. `code=None`: có từ trước quy tắc, chưa có mã."""
	doc = frappe.new_doc("Brand")
	doc.brand = name or f"_Test ICR Brand {code or frappe.generate_hash(length=6)}"
	doc.brand_code = code
	return _insert_master(doc)


def _insert_master(doc):
	if doc.get("item_group_code") or doc.get("brand_code"):
		doc.insert(ignore_permissions=True)
	else:
		# Ở chế độ quy tắc, danh mục mới bắt buộc có mã; bản ghi không mã chỉ có từ trước đó.
		with patch.object(item_code_rule, "is_rule_mode", return_value=False):
			doc.insert(ignore_permissions=True)
	return doc.name


def make_supplier(label):
	doc = frappe.new_doc("Supplier")
	doc.supplier_name = f"_Test ICR Supplier {label}"
	doc.supplier_group = "_Test Supplier Group"
	doc.insert(ignore_permissions=True)
	return doc.name


def new_item(item_group, brand=None, suppliers=(), **fields):
	"""Vật tư chưa lưu. `suppliers` là các bộ (NCC, mã hàng NCC[, is_default])."""
	doc = frappe.new_doc("Item")
	doc.item_name = fields.pop("item_name", f"_Test ICR Item {frappe.generate_hash(length=8)}")
	doc.item_group = item_group
	doc.brand = brand
	doc.stock_uom = "Nos"
	doc.is_stock_item = 1
	for row in suppliers:
		doc.append(
			"supplier_items",
			{
				"supplier": row[0],
				"supplier_part_no": row[1],
				"is_default": row[2] if len(row) > 2 else 0,
			},
		)
	doc.update(fields)
	return doc


def messages():
	return " | ".join(str(m.get("message")) for m in frappe.get_message_log())


class ItemCodeRuleCase(FrappeTestCase):
	def setUp(self):
		frappe.db.savepoint("item_code_rule_test")
		self.addCleanup(frappe.db.rollback, save_point="item_code_rule_test")
		self.sfx = frappe.generate_hash(length=6)
		# Mã hàng NCC riêng cho từng test: so trùng nhìn cả vật tư có thật trên site,
		# nên một mã cố định kiểu "N12345" sẽ đụng dữ liệu thử đang nằm ở đó.
		self.tok = self.sfx.upper()
		self.pn = f"N{self.tok}"
		self.pn_dashed = f"N-{self.tok}"
		self.pn_spaced = f"N {self.tok}"
		# Mã nhóm tối đa 3 ký tự, mã thương hiệu tối đa 6.
		self.group_code = next_group_code()
		self.group_code2 = next_group_code()
		self.brand_code = f"B{self.sfx[:5]}"
		self.brand_code2 = f"C{self.sfx[:5]}"
		# Mã hàng NCC dài hơn 11 ký tự; `long_pn_twin` giống nó ở đúng 11 ký tự đầu.
		self.long_pn = f"L{self.tok}-ABCD-EFGH"
		self.long_pn_twin = f"L{self.tok}-ABCD-ZZZZ"
		self.long_part = f"L{self.tok}ABCD"
		self.group = make_group(self.group_code)
		self.brand = make_brand(self.brand_code)
		self.supplier = make_supplier(self.sfx)
		use_naming_mode(self, RULE)

	def code(self, part):
		return f"{self.group_code}-{self.brand_code}-{part}"

	def make_item_manager(self):
		user = frappe.new_doc("User")
		user.email = f"_test_icr_{self.sfx}@example.com"
		user.first_name = "ICR"
		user.send_welcome_email = 0
		user.append("roles", {"role": "Item Manager"})
		user.insert(ignore_permissions=True)
		return user.name

	def as_user(self, user):
		frappe.set_user(user)
		self.addCleanup(frappe.set_user, "Administrator")

	def as_item_manager(self):
		self.as_user(self.make_item_manager())

	def rule_item(self, part_no=None, **fields):
		return new_item(self.group, self.brand, [(self.supplier, part_no or self.pn)], **fields).insert()

	def legacy_item(self, brand=None, item_code=None):
		"""Vật tư mang mã đặt tay, có từ trước khi bật quy tắc."""
		with patch.object(item_code_rule, "is_rule_mode", return_value=False):
			return new_item(self.group, brand, item_code=item_code or f"_TEST-ICR-OLD-{self.sfx}-1").insert()


class TestNormalization(FrappeTestCase):
	def test_code_part_drops_separators_and_keeps_case(self):
		self.assertEqual(item_code_rule.code_part("N-12345"), "N12345")
		self.assertEqual(item_code_rule.code_part(" N 12345 "), "N12345")
		self.assertEqual(item_code_rule.code_part("n12345"), "n12345")
		self.assertEqual(item_code_rule.code_part("12.5/AB#3"), "125AB3")

	def test_code_part_keeps_the_first_11_characters(self):
		self.assertEqual(item_code_rule.code_part("ABCDE-FGHIJ-KLMNO"), "ABCDEFGHIJK")
		self.assertEqual(item_code_rule.code_part("ABCDE-FGHIJ-K"), "ABCDEFGHIJK")

	def test_match_key_is_not_cut(self):
		self.assertEqual(item_code_rule.match_key("abcde-fghij-klmno"), "ABCDEFGHIJKLMNO")

	def test_code_part_strips_vietnamese_accents(self):
		self.assertEqual(item_code_rule.code_part("Ống-Đ 1"), "OngD1")

	def test_code_part_of_nothing_is_empty(self):
		self.assertEqual(item_code_rule.code_part(None), "")
		self.assertEqual(item_code_rule.code_part(" -/. "), "")

	def test_match_key_ignores_case_and_separators(self):
		self.assertEqual(item_code_rule.match_key("n-12 345"), item_code_rule.match_key("N12345"))
		self.assertNotEqual(item_code_rule.match_key("N12345"), item_code_rule.match_key("N12346"))

	def test_scope_is_stock_items_that_are_not_assets_or_variants(self):
		in_scope = item_code_rule.in_scope
		self.assertTrue(in_scope(frappe._dict(is_stock_item=1)))
		self.assertFalse(in_scope(frappe._dict(is_stock_item=0)))
		self.assertFalse(in_scope(frappe._dict(is_stock_item=1, is_fixed_asset=1)))
		self.assertFalse(in_scope(frappe._dict(is_stock_item=1, has_variants=1)))
		self.assertFalse(in_scope(frappe._dict(is_stock_item=1, variant_of="_Test Template")))


class TestCodeGeneration(ItemCodeRuleCase):
	def test_code_is_group_brand_and_supplier_part_no(self):
		item = new_item(self.group, self.brand, [(self.supplier, self.pn)]).insert()

		self.assertEqual(item.name, self.code(self.pn))
		self.assertEqual(item.item_code, item.name)

	def test_the_only_supplier_row_becomes_the_default(self):
		item = new_item(self.group, self.brand, [(self.supplier, self.pn)]).insert()

		self.assertEqual(item.supplier_items[0].is_default, 1)

	def test_code_keeps_the_case_it_was_entered_in(self):
		group_code = next_group_code().swapcase()[:2] + "H"
		brand_code = f"Vi{self.sfx[:3]}H"

		item = new_item(
			make_group(group_code), make_brand(brand_code), [(self.supplier, self.pn.lower())]
		).insert()

		self.assertEqual(item.name, f"{group_code}-{brand_code}-{self.pn.lower()}")

	def test_separators_leave_the_code_but_stay_in_the_supplier_part_no(self):
		item = new_item(
			self.group, self.brand, [(self.supplier, f"N {self.tok[:3]}-{self.tok[3:]}/6")]
		).insert()

		self.assertEqual(item.name, self.code(f"N{self.tok}6"))
		self.assertEqual(item.supplier_items[0].supplier_part_no, f"N {self.tok[:3]}-{self.tok[3:]}/6")

	def test_a_typed_item_code_is_ignored(self):
		item = new_item(self.group, self.brand, [(self.supplier, self.pn)], item_code="TU-GO-TAY").insert()

		self.assertEqual(item.name, self.code(self.pn))

	def test_code_comes_from_the_row_marked_default(self):
		other = make_supplier(f"{self.sfx}-2")

		item = new_item(self.group, self.brand, [(self.supplier, "AAA1"), (other, "BBB2", 1)]).insert()

		self.assertEqual(item.name, self.code("BBB2"))

	def test_several_suppliers_without_a_default_are_rejected(self):
		other = make_supplier(f"{self.sfx}-2")
		item = new_item(self.group, self.brand, [(self.supplier, "AAA1"), (other, "BBB2")])

		self.assertRaisesRegex(ItemCodeRuleError, "NCC mặc định", item.insert)

	def test_two_default_suppliers_are_rejected(self):
		other = make_supplier(f"{self.sfx}-2")
		item = new_item(self.group, self.brand, [(self.supplier, "AAA1", 1), (other, "BBB2", 1)])

		self.assertRaisesRegex(ItemCodeRuleError, "NCC mặc định", item.insert)

	def test_the_same_supplier_twice_is_rejected(self):
		item = new_item(self.group, self.brand, [(self.supplier, "AAA1", 1), (self.supplier, "BBB2")])

		self.assertRaisesRegex(ItemCodeRuleError, "hai dòng", item.insert)

	def test_missing_brand_is_rejected(self):
		item = new_item(self.group, None, [(self.supplier, self.pn)])

		self.assertRaisesRegex(ItemCodeRuleError, r"Thương hiệu \(Brand\)", item.insert)

	def test_missing_supplier_is_rejected(self):
		item = new_item(self.group, self.brand)

		self.assertRaisesRegex(ItemCodeRuleError, "nhà cung cấp", item.insert)

	def test_group_without_a_code_is_rejected(self):
		item = new_item(make_group(None), self.brand, [(self.supplier, self.pn)])

		self.assertRaisesRegex(ItemCodeRuleError, "Mã nhóm", item.insert)

	def test_brand_without_a_code_is_rejected(self):
		item = new_item(self.group, make_brand(None), [(self.supplier, self.pn)])

		self.assertRaisesRegex(ItemCodeRuleError, r"Mã thương hiệu \(Brand Code\)", item.insert)

	def test_code_uses_the_brand_code_not_the_brand_name(self):
		brand = make_brand(self.brand_code2, f"_Test ICR Tên thương hiệu {self.sfx}")

		item = new_item(self.group, brand, [(self.supplier, self.pn)]).insert()

		self.assertEqual(item.name, f"{self.group_code}-{self.brand_code2}-{self.pn}")
		self.assertEqual(item.brand, brand)

	def test_brand_typed_in_another_case_is_stored_as_its_id(self):
		# DB so khớp không phân biệt hoa/thường; so trùng theo thương hiệu thì so chuỗi.
		item = new_item(self.group, self.brand.swapcase(), [(self.supplier, self.pn)]).insert()

		self.assertEqual(item.name, self.code(self.pn))
		self.assertEqual(item.brand, self.brand)

	def test_every_missing_part_is_reported_at_once(self):
		item = new_item(make_group(None), None)

		with self.assertRaises(ItemCodeRuleError) as caught:
			item.insert()

		for part in ("Mã nhóm", "Thương hiệu (Brand)", "nhà cung cấp"):
			self.assertIn(part, str(caught.exception))

	def test_long_supplier_part_no_gives_its_first_11_characters(self):
		item = new_item(self.group, self.brand, [(self.supplier, self.long_pn)]).insert()

		self.assertEqual(item.name, self.code(self.long_part))
		self.assertEqual(len(self.long_part), 11)
		self.assertIn("11 ký tự đầu", messages())

	def test_long_supplier_part_no_is_stored_in_full(self):
		item = new_item(self.group, self.brand, [(self.supplier, self.long_pn)]).insert()

		self.assertEqual(item.supplier_items[0].supplier_part_no, self.long_pn)

	def test_separators_do_not_count_towards_the_11_characters(self):
		frappe.clear_messages()

		item = new_item(self.group, self.brand, [(self.supplier, f"N-{self.tok}-12/34")]).insert()

		self.assertEqual(item.name, self.code(f"N{self.tok}1234"))
		self.assertNotIn("11 ký tự đầu", messages())

	def test_code_is_never_longer_than_22_characters(self):
		item = new_item(self.group, self.brand, [(self.supplier, "N" * 40 + self.tok)]).insert()

		self.assertLessEqual(len(item.name), 3 + 1 + 6 + 1 + 11)

	def test_long_part_nos_alike_in_their_first_11_characters_collide(self):
		first = new_item(self.group, self.brand, [(self.supplier, self.long_pn)]).insert()
		item = new_item(self.group, self.brand, [(self.supplier, self.long_pn_twin)])

		with self.assertRaises(ItemCodeRuleError) as caught:
			item.insert()

		self.assertNotIsInstance(caught.exception, DuplicateItemError)
		self.assertIn(first.name, str(caught.exception))
		self.assertIn("11 ký tự đầu", str(caught.exception))

	def test_group_code_longer_than_3_characters_is_rejected(self):
		# Chỉ có được khi mã nhóm đã nằm trong dữ liệu từ trước khi có giới hạn.
		frappe.db.set_value("Item Group", self.group, "item_group_code", f"{self.group_code}X")
		item = new_item(self.group, self.brand, [(self.supplier, self.pn)])

		self.assertRaisesRegex(ItemCodeRuleError, "dài hơn 3 ký tự", item.insert)

	def test_brand_code_longer_than_6_characters_is_rejected(self):
		frappe.db.set_value("Brand", self.brand, "brand_code", f"{self.brand_code}X")
		item = new_item(self.group, self.brand, [(self.supplier, self.pn)])

		self.assertRaisesRegex(ItemCodeRuleError, "dài hơn 6 ký tự", item.insert)

	def test_supplier_without_a_part_no_gets_a_sequence(self):
		first = new_item(self.group, self.brand, [(self.supplier, None)]).insert()
		second = new_item(self.group, self.brand, [(self.supplier, "")]).insert()

		self.assertEqual(first.name, self.code("X0001"))
		self.assertEqual(second.name, self.code("X0002"))

	def test_sequence_skips_a_code_already_taken(self):
		new_item(self.group, self.brand, [(self.supplier, "X0001")]).insert()

		item = new_item(self.group, self.brand, [(self.supplier, None)]).insert()

		self.assertEqual(item.name, self.code("X0002"))

	def test_default_supplier_follows_the_default_row(self):
		item = new_item(self.group, self.brand, [(self.supplier, self.pn)]).insert()

		self.assertTrue(item.item_defaults)
		self.assertEqual({d.default_supplier for d in item.item_defaults}, {self.supplier})


class TestScope(ItemCodeRuleCase):
	def test_non_stock_item_keeps_its_typed_code(self):
		code = f"_TEST-ICR-DV-{self.sfx}"

		item = new_item(self.group, None, is_stock_item=0, item_code=code).insert()

		self.assertEqual(item.name, code)

	def test_nothing_is_enforced_outside_rule_mode(self):
		use_naming_mode(self, "Item Code")
		code = f"_TEST-ICR-OLD-{self.sfx}"

		item = new_item(self.group, None, item_code=code).insert()

		self.assertEqual(item.name, code)


class TestDuplicateDetection(ItemCodeRuleCase):
	def test_same_brand_and_part_no_written_differently_is_blocked(self):
		existing = new_item(self.group, self.brand, [(self.supplier, self.pn_dashed)]).insert()
		other_group = make_group(self.group_code2)

		item = new_item(other_group, self.brand, [(self.supplier, self.pn_spaced.lower())])

		with self.assertRaises(DuplicateItemError) as caught:
			item.insert()
		self.assertIn(existing.name, str(caught.exception))

	def test_long_part_nos_alike_in_their_first_11_characters_are_not_duplicates(self):
		new_item(self.group, self.brand, [(self.supplier, self.long_pn)]).insert()
		frappe.clear_messages()

		# Khác nhóm nên mã không đụng nhau; khóa so trùng thì không cắt nên không coi là trùng.
		item = new_item(make_group(self.group_code2), self.brand, [(self.supplier, self.long_pn_twin)])
		item.insert()

		self.assertEqual(item.name, f"{self.group_code2}-{self.brand_code}-{self.long_part}")
		self.assertNotIn("trùng vật tư", messages())

	def test_long_part_no_is_matched_in_full(self):
		existing = new_item(self.group, self.brand, [(self.supplier, self.long_pn)]).insert()

		item = new_item(make_group(self.group_code2), self.brand, [(self.supplier, self.long_pn.lower())])

		with self.assertRaises(DuplicateItemError) as caught:
			item.insert()
		self.assertIn(existing.name, str(caught.exception))

	def test_part_nos_differing_only_by_separator_are_blocked(self):
		new_item(self.group, self.brand, [(self.supplier, "12.5")]).insert()

		item = new_item(make_group(self.group_code2), self.brand, [(self.supplier, "125")])

		self.assertRaises(DuplicateItemError, item.insert)

	def test_same_part_no_under_another_brand_only_warns(self):
		existing = new_item(self.group, self.brand, [(self.supplier, self.pn)]).insert()
		other_brand = make_brand(self.brand_code2)
		frappe.clear_messages()

		item = new_item(self.group, other_brand, [(self.supplier, self.pn_dashed.lower())]).insert()

		self.assertEqual(item.name, f"{self.group_code}-{self.brand_code2}-{self.pn.lower()}")
		self.assertIn(existing.name, messages())

	def test_a_new_part_no_does_not_warn(self):
		new_item(self.group, self.brand, [(self.supplier, self.pn)]).insert()
		frappe.clear_messages()

		new_item(self.group, make_brand(self.brand_code2), [(self.supplier, f"Z{self.tok}")]).insert()

		self.assertNotIn("Có thể trùng", str(frappe.get_message_log()))

	def test_items_without_a_part_no_never_count_as_duplicates(self):
		new_item(self.group, self.brand, [(self.supplier, None)]).insert()

		second = new_item(self.group, self.brand, [(self.supplier, None)]).insert()

		self.assertTrue(second.name)

	def test_match_key_is_stored_on_every_supplier_row(self):
		use_naming_mode(self, "Item Code")

		item = new_item(self.group, None, [(self.supplier, "n-12 345")], item_code=f"_TEST-ICR-K-{self.sfx}")
		item.insert()

		self.assertEqual(item.supplier_items[0].supplier_part_no_key, "N12345")


class TestAfterCreation(ItemCodeRuleCase):
	def test_item_defaults_follow_the_default_supplier(self):
		other = make_supplier(f"{self.sfx}-2")
		item = new_item(self.group, self.brand, [(self.supplier, "AAA1", 1), (other, "BBB2")]).insert()

		item.supplier_items[0].is_default = 0
		item.supplier_items[1].is_default = 1
		item.save()

		self.assertEqual({d.default_supplier for d in item.item_defaults}, {other})

	def test_existing_item_missing_brand_and_supplier_still_saves(self):
		use_naming_mode(self, "Item Code")
		code = f"_TEST-ICR-OLD-{self.sfx}"
		item = new_item(self.group, None, item_code=code).insert()
		use_naming_mode(self, RULE)

		item.description = "Sửa sau khi bật quy tắc"
		item.save()

		self.assertEqual(item.name, code)

	def test_existing_default_supplier_survives_when_no_supplier_rows(self):
		use_naming_mode(self, "Item Code")
		item = new_item(self.group, None, item_code=f"_TEST-ICR-OLD-{self.sfx}").insert()
		self.assertTrue(item.item_defaults)
		item.item_defaults[0].default_supplier = self.supplier
		item.save()
		use_naming_mode(self, RULE)

		item.description = "Sửa sau khi bật quy tắc"
		item.save()

		self.assertEqual(item.item_defaults[0].default_supplier, self.supplier)

	def test_existing_item_with_several_suppliers_must_pick_a_default(self):
		use_naming_mode(self, "Item Code")
		other = make_supplier(f"{self.sfx}-2")
		item = new_item(
			self.group,
			None,
			[(self.supplier, "AAA1"), (other, "BBB2")],
			item_code=f"_TEST-ICR-OLD-{self.sfx}",
		).insert()
		use_naming_mode(self, RULE)

		item.description = "Sửa sau khi bật quy tắc"

		self.assertRaisesRegex(ItemCodeRuleError, "NCC mặc định", item.save)


class TestRenameGuard(ItemCodeRuleCase):
	def test_item_manager_cannot_rename_a_rule_item(self):
		item = new_item(self.group, self.brand, [(self.supplier, self.pn)]).insert()
		self.as_user(self.make_item_manager())

		self.assertRaisesRegex(
			ItemCodeRuleError, "đổi mã", frappe.rename_doc, "Item", item.name, f"_TEST-ICR-NEW-{self.sfx}"
		)

	def test_item_manager_cannot_merge_rule_items(self):
		first = new_item(self.group, self.brand, [(self.supplier, "AAA1")]).insert()
		second = new_item(self.group, self.brand, [(self.supplier, "BBB2")]).insert()
		self.as_user(self.make_item_manager())

		self.assertRaisesRegex(
			ItemCodeRuleError, "đổi mã", frappe.rename_doc, "Item", first.name, second.name, merge=True
		)

	def test_designated_role_may_rename(self):
		item = new_item(self.group, self.brand, [(self.supplier, self.pn)]).insert()
		frappe.db.set_single_value("Stock Settings", "item_rename_role", "Item Manager")
		# Giá trị single còn nằm trong cache của kết nối, thứ rollback không xóa.
		self.addCleanup(frappe.db.set_single_value, "Stock Settings", "item_rename_role", None)
		self.as_user(self.make_item_manager())
		new_name = f"_TEST-ICR-NEW-{self.sfx}"

		frappe.rename_doc("Item", item.name, new_name)

		self.assertTrue(frappe.db.exists("Item", new_name))

	def test_system_manager_may_rename(self):
		item = new_item(self.group, self.brand, [(self.supplier, self.pn)]).insert()
		new_name = f"_TEST-ICR-NEW-{self.sfx}"

		frappe.rename_doc("Item", item.name, new_name)

		self.assertTrue(frappe.db.exists("Item", new_name))

	def test_rename_is_not_guarded_outside_rule_mode(self):
		use_naming_mode(self, "Item Code")
		item = new_item(self.group, None, item_code=f"_TEST-ICR-OLD-{self.sfx}").insert()
		self.as_user(self.make_item_manager())
		new_name = f"_TEST-ICR-NEW-{self.sfx}"

		frappe.rename_doc("Item", item.name, new_name)

		self.assertTrue(frappe.db.exists("Item", new_name))


class TestMasterCodes(FrappeTestCase):
	def setUp(self):
		frappe.db.savepoint("item_code_rule_master")
		self.addCleanup(frappe.db.rollback, save_point="item_code_rule_master")
		self.sfx = frappe.generate_hash(length=6)
		self.brand_code = f"Q{self.sfx[:5]}"
		use_naming_mode(self, RULE)

	def group_code_of(self, group):
		return frappe.db.get_value("Item Group", group, "item_group_code")

	def brand_code_of(self, brand):
		return frappe.db.get_value("Brand", brand, "brand_code")

	def test_brand_keeps_a_free_name_beside_its_code(self):
		brand = make_brand(self.brand_code, f"_Test ICR Hãng có dấu - {self.sfx}")

		self.assertEqual(brand, f"_Test ICR Hãng có dấu - {self.sfx}")
		self.assertEqual(self.brand_code_of(brand), self.brand_code)

	def test_brand_code_rejects_separators_and_accents(self):
		for bad in (f"V-{self.sfx[:3]}", f"V {self.sfx[:3]}", f"Hã{self.sfx[:3]}"):
			with self.subTest(code=bad):
				self.assertRaisesRegex(frappe.ValidationError, "Mã thương hiệu", make_brand, bad)

	def test_item_group_code_rejects_separators(self):
		self.assertRaisesRegex(
			frappe.ValidationError, "Mã nhóm", make_group, "H/C", f"_Test ICR G {self.sfx}"
		)

	def test_brand_codes_differing_only_by_case_collide(self):
		make_brand(f"Vi{self.sfx[:4]}", f"_Test ICR Brand a {self.sfx}")

		self.assertRaises(
			frappe.UniqueValidationError, make_brand, f"VI{self.sfx[:4]}", f"_Test ICR Brand b {self.sfx}"
		)

	def test_brand_code_is_trimmed(self):
		self.assertEqual(self.brand_code_of(make_brand(f"  {self.brand_code} ")), self.brand_code)

	# --- Bắt buộc khi tạo ---

	def test_new_group_must_have_a_code(self):
		group = frappe.new_doc("Item Group")
		group.item_group_name = f"_Test ICR Group no code {self.sfx}"
		group.parent_item_group = "All Item Groups"

		self.assertRaisesRegex(ItemCodeRuleError, "Mã nhóm.*bắt buộc", group.insert)

	def test_new_brand_must_have_a_code(self):
		brand = frappe.new_doc("Brand")
		brand.brand = f"_Test ICR Brand no code {self.sfx}"

		self.assertRaisesRegex(ItemCodeRuleError, "Mã thương hiệu.*bắt buộc", brand.insert)

	def test_a_code_of_spaces_does_not_count(self):
		brand = frappe.new_doc("Brand")
		brand.brand = f"_Test ICR Brand blank {self.sfx}"
		brand.brand_code = "   "

		self.assertRaisesRegex(ItemCodeRuleError, "bắt buộc", brand.insert)

	def test_codes_are_optional_outside_rule_mode(self):
		use_naming_mode(self, "Item Code")
		group = frappe.new_doc("Item Group")
		group.item_group_name = f"_Test ICR Group free {self.sfx}"
		group.parent_item_group = "All Item Groups"
		brand = frappe.new_doc("Brand")
		brand.brand = f"_Test ICR Brand free {self.sfx}"

		group.insert()
		brand.insert()

		self.assertIsNone(self.group_code_of(group.name))
		self.assertIsNone(self.brand_code_of(brand.name))

	def test_masters_from_before_the_rule_need_a_code_to_be_saved_again(self):
		group = frappe.get_doc("Item Group", make_group(None))
		brand = frappe.get_doc("Brand", make_brand(None))
		brand.description = "Chưa có mã"

		self.assertRaisesRegex(ItemCodeRuleError, "Mã nhóm.*bắt buộc", group.save)
		self.assertRaisesRegex(ItemCodeRuleError, "Mã thương hiệu.*bắt buộc", brand.save)

		# Lần lưu hỏng đã đổi dấu thời gian trong bộ nhớ; nạp lại như người dùng mở lại form.
		group.reload()
		brand.reload()
		group.item_group_code = next_group_code()
		brand.brand_code = self.brand_code
		group.save()
		brand.save()

	def test_masters_without_a_code_still_save_outside_rule_mode(self):
		group = frappe.get_doc("Item Group", make_group(None))
		brand = frappe.get_doc("Brand", make_brand(None))
		use_naming_mode(self, "Item Code")

		group.save()
		brand.save()

	def test_scaffolding_code_may_create_a_group_without_a_code(self):
		group = frappe.new_doc("Item Group")
		group.item_group_name = f"_Test ICR Group seeded {self.sfx}"
		group.parent_item_group = "All Item Groups"
		group.flags.ignore_mandatory = True

		group.insert()

		self.assertIsNone(self.group_code_of(group.name))

	# --- Giới hạn độ dài: nhập dài hơn thì lấy các ký tự đầu ---

	def test_group_code_keeps_its_first_3_characters(self):
		code = next_group_code()
		frappe.clear_messages()

		group = make_group(f"{code}XY")

		self.assertEqual(self.group_code_of(group), code)
		self.assertIn("3 ký tự đầu", messages())

	def test_group_code_of_3_characters_is_kept_as_is(self):
		code = next_group_code()
		frappe.clear_messages()

		group = make_group(code)

		self.assertEqual(self.group_code_of(group), code)
		self.assertNotIn("ký tự đầu", messages())

	def test_group_code_is_cut_when_edited_too(self):
		group = frappe.get_doc("Item Group", make_group(None))
		code = next_group_code()
		group.item_group_code = f"{code}99"

		group.save()

		self.assertEqual(self.group_code_of(group.name), code)

	def test_group_code_cut_down_to_one_already_taken_is_rejected(self):
		code = next_group_code()
		make_group(code)

		self.assertRaises(frappe.UniqueValidationError, make_group, f"{code}Z")

	def test_brand_code_keeps_its_first_6_characters(self):
		frappe.clear_messages()

		brand = make_brand(f"{self.brand_code}1000")

		self.assertEqual(self.brand_code_of(brand), self.brand_code)
		self.assertIn("6 ký tự đầu", messages())

	def test_brand_code_of_6_characters_is_kept_as_is(self):
		frappe.clear_messages()

		self.assertEqual(self.brand_code_of(make_brand(self.brand_code)), self.brand_code)
		self.assertNotIn("ký tự đầu", messages())

	def test_brand_code_cut_down_to_one_already_taken_is_rejected(self):
		make_brand(self.brand_code)

		self.assertRaises(frappe.UniqueValidationError, make_brand, f"{self.brand_code}2000")

	def test_brand_name_is_never_cut(self):
		name = f"_Test ICR Brand with a long name {self.sfx}"

		self.assertEqual(make_brand(self.brand_code, name), name)


class TestComponentLock(ItemCodeRuleCase):
	"""Mã nhóm, mã thương hiệu đã lưu thì khóa; người được đổi mã vật tư sửa thì vật tư đổi mã theo."""

	def set_group_code(self, code):
		group = frappe.get_doc("Item Group", self.group)
		group.item_group_code = code
		group.save()

	# --- Mã nhóm ---

	def test_group_code_in_use_cannot_be_changed(self):
		self.rule_item()
		self.as_item_manager()

		self.assertRaisesRegex(
			ItemCodeRuleError, "1 vật tư đang mang mã", self.set_group_code, self.group_code2
		)

	def test_group_code_in_use_cannot_be_cleared(self):
		self.rule_item()
		self.as_item_manager()

		self.assertRaises(ItemCodeRuleError, self.set_group_code, None)

	def test_group_code_changing_only_in_case_is_still_a_change(self):
		self.rule_item()
		self.as_item_manager()

		self.assertRaises(ItemCodeRuleError, self.set_group_code, self.group_code.swapcase())

	def test_saved_group_code_is_locked_even_before_any_item_carries_it(self):
		self.as_item_manager()

		self.assertRaisesRegex(
			ItemCodeRuleError, "không sửa được sau khi đã lưu", self.set_group_code, self.group_code2
		)

	def test_privileged_user_fixes_a_group_code_nothing_carries_without_a_warning(self):
		frappe.clear_messages()

		self.set_group_code(self.group_code2)

		self.assertEqual(frappe.db.get_value("Item Group", self.group, "item_group_code"), self.group_code2)
		self.assertNotIn("Đã đổi mã", messages())

	def test_nobody_may_clear_a_group_code(self):
		self.assertRaisesRegex(ItemCodeRuleError, "bắt buộc", self.set_group_code, None)

	def test_only_privileged_users_are_offered_the_unlock(self):
		self.assertTrue(item_code_rule.may_change_codes())

		self.as_item_manager()

		self.assertFalse(item_code_rule.may_change_codes())

	def test_group_without_a_code_can_be_given_one(self):
		group = frappe.get_doc("Item Group", make_group(None))
		self.as_item_manager()

		group.item_group_code = self.group_code2
		group.save()

	def test_group_in_use_still_saves_when_its_code_is_untouched(self):
		self.rule_item()
		self.as_item_manager()

		frappe.get_doc("Item Group", self.group).save()

	def test_privileged_user_changing_a_group_code_renames_its_items(self):
		item = self.rule_item()
		handmade = self.legacy_item()
		frappe.clear_messages()

		self.set_group_code(self.group_code2)

		renamed = f"{self.group_code2}-{self.brand_code}-{self.pn}"
		self.assertFalse(frappe.db.exists("Item", item.name))
		self.assertEqual(frappe.db.get_value("Item", renamed, "item_code"), renamed)
		self.assertTrue(frappe.db.exists("Item", handmade.name))
		self.assertIn("Đã đổi mã 1 vật tư", messages())

	def test_group_code_change_is_refused_when_a_new_code_is_already_taken(self):
		self.rule_item()
		taken = self.legacy_item(item_code=f"{self.group_code2}-{self.brand_code}-{self.pn}")

		with self.assertRaises(ItemCodeRuleError) as caught:
			self.set_group_code(self.group_code2)

		self.assertIn("sẽ trùng", str(caught.exception))
		self.assertIn(taken.name, str(caught.exception))

	def test_privileged_merge_moves_items_to_the_code_of_the_surviving_group(self):
		item = self.rule_item()
		target = make_group(self.group_code2)

		frappe.rename_doc("Item Group", self.group, target, merge=True)

		renamed = f"{self.group_code2}-{self.brand_code}-{self.pn}"
		self.assertFalse(frappe.db.exists("Item", item.name))
		self.assertEqual(frappe.db.get_value("Item", renamed, "item_group"), target)

	def test_merged_items_without_a_part_no_get_the_next_free_number(self):
		target = make_group(self.group_code2)
		moving = new_item(self.group, self.brand, [(self.supplier, None)]).insert()
		staying = new_item(target, self.brand, [(self.supplier, None)]).insert()
		self.assertEqual(staying.name, f"{self.group_code2}-{self.brand_code}-X0001")

		frappe.rename_doc("Item Group", self.group, target, merge=True)

		self.assertFalse(frappe.db.exists("Item", moving.name))
		self.assertTrue(frappe.db.exists("Item", f"{self.group_code2}-{self.brand_code}-X0002"))
		self.assertTrue(frappe.db.exists("Item", staying.name))

	def test_merging_into_a_group_without_a_code_is_refused(self):
		self.rule_item()
		target = make_group(None)

		self.assertRaisesRegex(
			ItemCodeRuleError, "chưa có mã", frappe.rename_doc, "Item Group", self.group, target, merge=True
		)

	def test_many_items_are_renamed_in_the_background(self):
		item = self.rule_item()

		with (
			patch.object(item_code_rule, "INLINE_RENAME_LIMIT", 0),
			patch.object(item_code_rule.frappe, "enqueue") as enqueue,
		):
			self.set_group_code(self.group_code2)

		self.assertTrue(frappe.db.exists("Item", item.name))
		self.assertEqual(enqueue.call_args.args[0], "erpnext.stock.item_code_rule.rename_items")
		self.assertEqual(
			enqueue.call_args.kwargs["plan"], {item.name: f"{self.group_code2}-{self.brand_code}-{self.pn}"}
		)
		self.assertIn("chế độ nền", messages())

	def test_background_renaming_skips_and_reports_an_item_that_fails(self):
		good = self.rule_item()
		plan = {
			"_TEST-ICR-KHONG-CO": "_TEST-ICR-X",
			good.name: f"{self.group_code2}-{self.brand_code}-{self.pn}",
		}

		# Tiến trình nền chốt từng vật tư; trong test thì không được chốt gì vào site.
		with (
			patch.object(frappe.db, "commit"),
			patch.object(frappe.db, "rollback"),
			patch.object(item_code_rule.frappe, "log_error"),
			patch.object(item_code_rule.frappe, "publish_realtime") as notify,
		):
			failed = item_code_rule.rename_items(plan, in_background=True)

		self.assertEqual(failed, ["_TEST-ICR-KHONG-CO"])
		self.assertTrue(frappe.db.exists("Item", plan[good.name]))
		self.assertIn("1 vật tư chưa đổi được", notify.call_args.args[1])

	def test_group_code_is_not_locked_outside_rule_mode(self):
		self.rule_item()
		use_naming_mode(self, "Item Code")
		self.as_item_manager()

		self.set_group_code(self.group_code2)

	def test_renaming_a_group_is_allowed_because_its_code_stays(self):
		self.rule_item()
		self.as_item_manager()
		new_name = f"_Test ICR Group renamed {self.sfx}"

		frappe.rename_doc("Item Group", self.group, new_name)

		self.assertEqual(frappe.db.get_value("Item Group", new_name, "item_group_code"), self.group_code)

	def test_merging_a_group_in_use_into_one_with_another_code_is_blocked(self):
		self.rule_item()
		target = make_group(self.group_code2)
		self.as_item_manager()

		self.assertRaisesRegex(
			ItemCodeRuleError, "gộp", frappe.rename_doc, "Item Group", self.group, target, merge=True
		)

	# --- Mã thương hiệu ---

	def set_brand_code(self, code):
		brand = frappe.get_doc("Brand", self.brand)
		brand.brand_code = code
		brand.save()

	def test_brand_code_in_use_cannot_be_changed(self):
		self.rule_item()
		self.as_item_manager()

		self.assertRaisesRegex(
			ItemCodeRuleError, "1 vật tư đang mang mã", self.set_brand_code, self.brand_code2
		)

	def test_brand_code_in_use_cannot_be_cleared(self):
		self.rule_item()
		self.as_item_manager()

		self.assertRaises(ItemCodeRuleError, self.set_brand_code, None)

	def test_saved_brand_code_is_locked_even_before_any_item_carries_it(self):
		self.as_item_manager()

		self.assertRaisesRegex(
			ItemCodeRuleError, "không sửa được sau khi đã lưu", self.set_brand_code, self.brand_code2
		)

	def test_privileged_user_fixes_a_brand_code_nothing_carries_without_a_warning(self):
		frappe.clear_messages()

		self.set_brand_code(self.brand_code2)

		self.assertEqual(frappe.db.get_value("Brand", self.brand, "brand_code"), self.brand_code2)
		self.assertNotIn("Đã đổi mã", messages())

	def test_other_brand_fields_stay_editable(self):
		self.rule_item()
		self.as_item_manager()
		brand = frappe.get_doc("Brand", self.brand)
		brand.description = "Sửa mô tả, không đụng tới mã"

		brand.save()

	def test_brand_without_a_code_can_be_given_one(self):
		brand = frappe.get_doc("Brand", make_brand(None))
		self.as_item_manager()

		brand.brand_code = self.brand_code2
		brand.save()

	def test_privileged_user_changing_a_brand_code_renames_its_items(self):
		item = self.rule_item()
		frappe.clear_messages()

		self.set_brand_code(self.brand_code2)

		renamed = f"{self.group_code}-{self.brand_code2}-{self.pn}"
		self.assertFalse(frappe.db.exists("Item", item.name))
		self.assertEqual(frappe.db.get_value("Item", renamed, "brand"), self.brand)
		self.assertIn("Đã đổi mã 1 vật tư", messages())

	def test_privileged_merge_moves_items_to_the_code_of_the_surviving_brand(self):
		item = self.rule_item()
		target = make_brand(self.brand_code2)

		frappe.rename_doc("Brand", self.brand, target, merge=True)

		renamed = f"{self.group_code}-{self.brand_code2}-{self.pn}"
		self.assertFalse(frappe.db.exists("Item", item.name))
		self.assertEqual(frappe.db.get_value("Item", renamed, "brand"), target)

	def test_brand_code_is_not_locked_outside_rule_mode(self):
		self.rule_item()
		use_naming_mode(self, "Item Code")
		self.as_item_manager()

		self.set_brand_code(self.brand_code2)

	def test_renaming_a_brand_is_allowed_because_its_code_stays(self):
		item = self.rule_item()
		self.as_item_manager()
		new_name = f"_Test ICR Brand renamed {self.sfx}"

		frappe.rename_doc("Brand", self.brand, new_name)

		self.assertEqual(frappe.db.get_value("Brand", new_name, "brand_code"), self.brand_code)
		self.assertEqual(frappe.db.get_value("Item", item.name, "brand"), new_name)

	def test_merging_a_brand_in_use_into_one_with_another_code_is_blocked(self):
		self.rule_item()
		target = make_brand(self.brand_code2)
		self.as_item_manager()

		self.assertRaisesRegex(
			ItemCodeRuleError, "gộp", frappe.rename_doc, "Brand", self.brand, target, merge=True
		)


class TestCodeFollowsItem(ItemCodeRuleCase):
	"""Đổi nhóm hàng, thương hiệu, NCC mặc định hay mã hàng NCC thì vật tư đổi mã ngay lần lưu đó."""

	def assert_renamed(self, item, old, new):
		self.assertEqual((item.name, item.item_code), (new, new))
		self.assertFalse(frappe.db.exists("Item", old))
		self.assertEqual(frappe.db.get_value("Item", new, "item_code"), new)
		# Dòng con và mọi liên kết đi theo mã mới.
		self.assertTrue(frappe.db.exists("Item Supplier", {"parent": new, "parenttype": "Item"}))
		self.assertFalse(frappe.db.exists("Item Supplier", {"parent": old, "parenttype": "Item"}))

	def test_moving_to_another_group_changes_the_first_part(self):
		item = self.rule_item()
		old = item.name
		frappe.clear_messages()
		item.item_group = make_group(self.group_code2)

		item.save()

		self.assert_renamed(item, old, f"{self.group_code2}-{self.brand_code}-{self.pn}")
		self.assertIn("Mã vật tư đã đổi từ", messages())

	def test_changing_the_brand_changes_the_second_part(self):
		item = self.rule_item()
		old = item.name
		item.brand = make_brand(self.brand_code2)

		item.save()

		self.assert_renamed(item, old, f"{self.group_code}-{self.brand_code2}-{self.pn}")

	def test_changing_the_supplier_part_no_changes_the_third_part(self):
		item = self.rule_item()
		old = item.name
		item.supplier_items[0].supplier_part_no = f"Q-{self.tok}"

		item.save()

		self.assert_renamed(item, old, self.code(f"Q{self.tok}"))

	def test_switching_the_default_supplier_takes_the_new_part_no(self):
		other = make_supplier(f"{self.sfx}-2")
		item = new_item(
			self.group, self.brand, [(self.supplier, self.pn, 1), (other, f"Q{self.tok}")]
		).insert()
		old = item.name
		item.supplier_items[0].is_default = 0
		item.supplier_items[1].is_default = 1

		item.save()

		self.assert_renamed(item, old, self.code(f"Q{self.tok}"))
		self.assertEqual({d.default_supplier for d in item.item_defaults}, {other})

	def test_part_no_written_differently_keeps_the_code(self):
		item = self.rule_item(self.pn_dashed)
		frappe.clear_messages()
		item.supplier_items[0].supplier_part_no = self.pn_spaced

		item.save()

		self.assertEqual(item.name, self.code(self.pn))
		self.assertNotIn("Mã vật tư đã đổi", messages())

	def test_changing_only_the_case_of_the_part_no_renames(self):
		item = self.rule_item()
		item.supplier_items[0].supplier_part_no = self.pn.lower()

		item.save()

		self.assertEqual(item.name, self.code(self.pn.lower()))
		self.assertEqual(frappe.db.get_value("Item", item.name, "name"), self.code(self.pn.lower()))

	def test_saving_something_else_keeps_the_code(self):
		item = self.rule_item()
		frappe.clear_messages()
		item.description = "Mô tả mới"

		item.save()

		self.assertEqual(item.name, self.code(self.pn))
		self.assertNotIn("Mã vật tư đã đổi", messages())
		self.assertFalse(hasattr(item, "localname"))

	def test_the_form_is_told_the_old_name_so_it_can_follow(self):
		item = self.rule_item()
		old = item.name
		item.brand = make_brand(self.brand_code2)

		item.save()

		self.assertEqual(item.localname, old)

	def test_an_item_manager_needs_no_rename_right(self):
		item = self.rule_item()
		other = make_group(self.group_code2)
		self.as_item_manager()
		item.item_group = other

		item.save()

		self.assertEqual(item.name, f"{self.group_code2}-{self.brand_code}-{self.pn}")

	def test_dropping_the_part_no_gives_a_sequence_number(self):
		item = self.rule_item()
		item.supplier_items[0].supplier_part_no = None

		item.save()

		self.assertEqual(item.name, self.code("X0001"))

	def test_a_sequence_number_stays_while_group_and_brand_stay(self):
		item = new_item(self.group, self.brand, [(self.supplier, None)]).insert()
		new_item(self.group, self.brand, [(self.supplier, None)]).insert()
		item.description = "Mô tả mới"
		item.append("supplier_items", {"supplier": make_supplier(f"{self.sfx}-2"), "supplier_part_no": "ZZ1"})

		item.save()

		self.assertEqual(item.name, self.code("X0001"))

	def test_a_sequence_item_moving_group_gets_a_number_of_the_new_pair(self):
		other = make_group(self.group_code2)
		new_item(other, self.brand, [(self.supplier, None)]).insert()
		item = new_item(self.group, self.brand, [(self.supplier, None)]).insert()
		item.item_group = other

		item.save()

		self.assertEqual(item.name, f"{self.group_code2}-{self.brand_code}-X0002")

	def test_a_sequence_item_given_a_part_no_takes_it(self):
		item = new_item(self.group, self.brand, [(self.supplier, None)]).insert()
		item.supplier_items[0].supplier_part_no = self.pn

		item.save()

		self.assertEqual(item.name, self.code(self.pn))

	def test_a_long_part_no_is_cut_when_the_code_follows_too(self):
		item = self.rule_item()
		frappe.clear_messages()
		item.supplier_items[0].supplier_part_no = self.long_pn

		item.save()

		self.assertEqual(item.name, self.code(self.long_part))
		self.assertIn("11 ký tự đầu", messages())

	def test_changing_into_another_items_brand_and_part_no_is_blocked(self):
		existing = self.rule_item()
		item = self.rule_item(f"Q{self.tok}")
		item.supplier_items[0].supplier_part_no = self.pn_dashed

		with self.assertRaises(DuplicateItemError) as caught:
			item.save()

		self.assertIn(existing.name, str(caught.exception))
		self.assertTrue(frappe.db.exists("Item", self.code(f"Q{self.tok}")))

	def test_changing_into_a_part_no_of_another_brand_only_warns(self):
		other_brand = make_brand(self.brand_code2)
		new_item(self.group, other_brand, [(self.supplier, self.pn)]).insert()
		item = self.rule_item(f"Q{self.tok}")
		frappe.clear_messages()
		item.supplier_items[0].supplier_part_no = self.pn

		item.save()

		self.assertEqual(item.name, self.code(self.pn))
		self.assertIn("thương hiệu (Brand) khác", messages())

	def test_an_item_never_counts_as_its_own_duplicate(self):
		item = self.rule_item()
		frappe.clear_messages()
		item.item_group = make_group(self.group_code2)

		item.save()

		self.assertNotIn("trùng vật tư", messages())

	def test_a_code_cut_down_to_one_already_taken_is_blocked(self):
		first = self.rule_item(self.long_pn)
		item = self.rule_item(f"Q{self.tok}")
		item.supplier_items[0].supplier_part_no = self.long_pn_twin

		with self.assertRaises(ItemCodeRuleError) as caught:
			item.save()

		self.assertIn(first.name, str(caught.exception))

	def test_a_rule_item_cannot_lose_what_its_code_is_built_from(self):
		item = self.rule_item()
		item.brand = None

		self.assertRaisesRegex(ItemCodeRuleError, "Chưa đủ thông tin", item.save)

	def test_an_item_out_of_step_with_its_group_is_put_right_on_the_next_save(self):
		item = self.rule_item()
		# Mã nhóm bị sửa thẳng trong dữ liệu, không qua form.
		frappe.db.set_value("Item Group", self.group, "item_group_code", self.group_code2)
		item.reload()
		item.description = "Mô tả mới"

		item.save()

		self.assertEqual(item.name, f"{self.group_code2}-{self.brand_code}-{self.pn}")

	def test_a_handmade_code_is_left_alone(self):
		item = self.legacy_item()
		other = make_group(self.group_code2)
		self.as_item_manager()
		item.reload()
		frappe.clear_messages()
		item.item_group = other
		item.brand = self.brand
		item.append("supplier_items", {"supplier": self.supplier, "supplier_part_no": self.pn})

		item.save()

		self.assertEqual(item.name, f"_TEST-ICR-OLD-{self.sfx}-1")
		self.assertEqual(item.item_group, other)
		self.assertIn("mã đặt tay", messages())

	def test_a_handmade_code_shaped_like_a_rule_code_is_left_alone_too(self):
		item = self.legacy_item(self.brand, item_code=f"TB-001-{self.tok}")
		item.reload()
		item.item_group = make_group(self.group_code2)
		item.append("supplier_items", {"supplier": self.supplier, "supplier_part_no": self.pn})

		item.save()

		self.assertEqual(item.name, f"TB-001-{self.tok}")

	def test_only_the_rule_marks_a_code_as_its_own(self):
		rule_item = self.rule_item()
		handmade = self.legacy_item()
		self.assertEqual((rule_item.item_code_by_rule, handmade.item_code_by_rule), (1, 0))

		handmade.reload()
		handmade.item_code_by_rule = 1
		handmade.save()
		rule_item.item_code_by_rule = 0
		rule_item.save()

		self.assertEqual(frappe.db.get_value("Item", handmade.name, "item_code_by_rule"), 0)
		self.assertEqual(frappe.db.get_value("Item", rule_item.name, "item_code_by_rule"), 1)

	def test_a_code_renamed_by_hand_stops_following(self):
		item = self.rule_item()
		manual = f"_TEST-ICR-TAY-{self.sfx}"

		frappe.rename_doc("Item", item.name, manual)
		renamed = frappe.get_doc("Item", manual)
		renamed.item_group = make_group(self.group_code2)
		renamed.save()

		self.assertEqual(renamed.name, manual)
		self.assertEqual(renamed.item_code_by_rule, 0)

	def test_nothing_is_renamed_outside_rule_mode(self):
		item = self.rule_item()
		other = make_group(self.group_code2)
		use_naming_mode(self, "Item Code")
		item.item_group = other

		item.save()

		self.assertEqual(item.name, self.code(self.pn))


class TestStockSettings(FrappeTestCase):
	def test_rule_mode_makes_item_code_optional_but_visible(self):
		with change_settings("Stock Settings", item_naming_by=RULE):
			field = frappe.get_meta("Item").get_field("item_code")

			self.assertEqual(frappe.db.get_default("item_naming_by"), RULE)
			self.assertEqual((field.reqd, field.hidden), (0, 0))

	def test_item_code_mode_keeps_item_code_mandatory(self):
		with change_settings("Stock Settings", item_naming_by="Item Code"):
			field = frappe.get_meta("Item").get_field("item_code")

			self.assertEqual((field.reqd, field.hidden), (1, 0))

	def test_rule_is_switched_by_the_naming_mode(self):
		with change_settings("Stock Settings", item_naming_by=RULE):
			self.assertTrue(item_code_rule.is_rule_mode())
		with change_settings("Stock Settings", item_naming_by="Item Code"):
			self.assertFalse(item_code_rule.is_rule_mode())


class TestBackfill(ItemCodeRuleCase):
	def old_item(self, suppliers, default_supplier=None):
		use_naming_mode(self, "Item Code")
		item = new_item(
			self.group, None, suppliers, item_code=f"_TEST-ICR-OLD-{frappe.generate_hash(length=6)}"
		).insert()
		if default_supplier:
			item.item_defaults[0].default_supplier = default_supplier
			item.save()
		return item

	def default_flags(self, item):
		return [
			row.is_default
			for row in frappe.get_all(
				"Item Supplier", filters={"parent": item.name}, fields=["is_default"], order_by="idx"
			)
		]

	def test_row_matching_default_supplier_is_marked(self):
		other = make_supplier(f"{self.sfx}-2")
		item = self.old_item([(self.supplier, "AAA1"), (other, "BBB2")], default_supplier=other)

		item_code_rule.backfill_default_supplier_rows()

		self.assertEqual(self.default_flags(item), [0, 1])

	def test_single_row_is_marked(self):
		item = self.old_item([(self.supplier, "AAA1")])

		item_code_rule.backfill_default_supplier_rows()

		self.assertEqual(self.default_flags(item), [1])

	def test_undecidable_item_is_left_alone_and_reported(self):
		other = make_supplier(f"{self.sfx}-2")
		item = self.old_item([(self.supplier, "AAA1"), (other, "BBB2")])

		unresolved = item_code_rule.backfill_default_supplier_rows()

		self.assertEqual(self.default_flags(item), [0, 0])
		self.assertIn(item.name, unresolved)

	def test_missing_match_keys_are_filled(self):
		item = self.old_item([(self.supplier, "n-12 345")])
		frappe.db.set_value("Item Supplier", item.supplier_items[0].name, "supplier_part_no_key", None)

		item_code_rule.backfill_default_supplier_rows()

		self.assertEqual(
			frappe.db.get_value("Item Supplier", item.supplier_items[0].name, "supplier_part_no_key"),
			"N12345",
		)


class TestPreview(ItemCodeRuleCase):
	def test_preview_shows_the_code_before_saving(self):
		preview = item_code_rule.preview_item_code(self.group, self.brand, self.pn_dashed)

		self.assertEqual(preview["code"], self.code(self.pn))
		self.assertEqual(preview["missing"], [])

	def test_preview_names_what_is_missing(self):
		preview = item_code_rule.preview_item_code(make_group(None), None, self.pn)

		self.assertFalse(preview["code"])
		self.assertEqual(len(preview["missing"]), 2)

	def test_preview_without_part_no_shows_the_next_sequence_without_using_it(self):
		preview = item_code_rule.preview_item_code(self.group, self.brand, None)
		item = new_item(self.group, self.brand, [(self.supplier, None)]).insert()

		self.assertEqual(preview["code"], self.code("X0001"))
		self.assertEqual(item.name, self.code("X0001"))

	def test_preview_lists_items_sharing_the_supplier_part_no(self):
		same_brand = new_item(self.group, self.brand, [(self.supplier, self.pn_dashed)]).insert()
		other_brand = make_brand(self.brand_code2)

		preview = item_code_rule.preview_item_code(make_group(self.group_code2), other_brand, self.pn.lower())
		blocked = item_code_rule.preview_item_code(make_group(next_group_code()), self.brand, self.pn.lower())

		self.assertEqual(
			[(row["item_code"], row["same_brand"]) for row in preview["similar"]], [(same_brand.name, False)]
		)
		self.assertEqual(
			[(row["item_code"], row["same_brand"]) for row in blocked["similar"]], [(same_brand.name, True)]
		)

	def test_preview_says_when_the_part_no_is_cut(self):
		preview = item_code_rule.preview_item_code(self.group, self.brand, self.long_pn)

		self.assertEqual(preview["code"], self.code(self.long_part))
		self.assertEqual((preview["truncated"], preview["part_length"], preview["taken"]), (True, 11, False))

	def test_preview_of_a_short_part_no_is_not_marked_as_cut(self):
		preview = item_code_rule.preview_item_code(self.group, self.brand, self.pn)

		self.assertFalse(preview["truncated"])

	def test_preview_says_when_the_cut_code_is_already_taken(self):
		new_item(self.group, self.brand, [(self.supplier, self.long_pn)]).insert()

		preview = item_code_rule.preview_item_code(self.group, self.brand, self.long_pn_twin)

		self.assertTrue(preview["taken"])
		self.assertEqual(preview["similar"], [])

	def test_preview_for_a_saved_item_shows_the_code_it_would_change_to(self):
		item = new_item(self.group, self.brand, [(self.supplier, self.pn)]).insert()
		other = make_group(self.group_code2)

		same = item_code_rule.preview_item_code(self.group, self.brand, self.pn, item_code=item.name)
		moved = item_code_rule.preview_item_code(other, self.brand, self.pn_dashed, item_code=item.name)

		self.assertEqual((same["code"], same["taken"], same["similar"]), (item.name, False, []))
		self.assertEqual(moved["code"], f"{self.group_code2}-{self.brand_code}-{self.pn}")

	def test_preview_for_a_saved_sequence_item_keeps_its_number(self):
		item = new_item(self.group, self.brand, [(self.supplier, None)]).insert()
		new_item(self.group, self.brand, [(self.supplier, None)]).insert()

		preview = item_code_rule.preview_item_code(self.group, self.brand, None, item_code=item.name)

		self.assertEqual(preview["code"], item.name)

	def test_preview_of_a_new_part_no_lists_nothing(self):
		new_item(self.group, self.brand, [(self.supplier, self.pn)]).insert()

		preview = item_code_rule.preview_item_code(self.group, self.brand, f"Z{self.tok}")

		self.assertEqual(preview["similar"], [])

	def test_preview_still_lists_similar_items_when_the_code_cannot_be_built(self):
		existing = new_item(self.group, self.brand, [(self.supplier, self.pn)]).insert()

		preview = item_code_rule.preview_item_code(None, None, self.pn)

		self.assertFalse(preview["code"])
		self.assertEqual([row["item_code"] for row in preview["similar"]], [existing.name])


class TestManufacturerPartNo(ItemCodeRuleCase):
	def add_manufacturer_part(self, item, maker, part_no):
		return frappe.get_doc(
			{
				"doctype": "Item Manufacturer",
				"item_code": item.name,
				"manufacturer": maker,
				"manufacturer_part_no": part_no,
			}
		).insert()

	def test_reusing_a_manufacturer_part_no_on_another_item_warns(self):
		first = new_item(self.group, self.brand, [(self.supplier, "AAA1")]).insert()
		second = new_item(self.group, self.brand, [(self.supplier, "BBB2")]).insert()
		maker = frappe.get_doc({"doctype": "Manufacturer", "short_name": f"_Test ICR M {self.sfx}"}).insert()
		self.add_manufacturer_part(first, maker.name, f"MP-{self.sfx}")
		frappe.clear_messages()

		self.add_manufacturer_part(second, maker.name, f"mp {self.sfx}")

		self.assertIn(first.name, messages())

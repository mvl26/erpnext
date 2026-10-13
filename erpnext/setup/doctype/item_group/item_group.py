import copy

import frappe
from frappe import _
from frappe.utils.nestedset import NestedSet


class ItemGroup(NestedSet):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from erpnext.stock.doctype.item_default.item_default import ItemDefault
		from erpnext.stock.doctype.item_tax.item_tax import ItemTax

		image: DF.AttachImage | None
		is_group: DF.Check
		item_group_code: DF.Data | None
		item_group_defaults: DF.Table[ItemDefault]
		item_group_name: DF.Data
		lft: DF.Int
		old_parent: DF.Link | None
		parent_item_group: DF.Link | None
		rgt: DF.Int
		taxes: DF.Table[ItemTax]
	# end: auto-generated types

	def validate(self):
		if not self.parent_item_group and not frappe.flags.in_test:
			if frappe.db.exists("Item Group", _("All Item Groups")):
				self.parent_item_group = _("All Item Groups")
		self.validate_item_group_defaults()
		self.check_item_tax()
		self.validate_item_group_code()

	def validate_item_group_code(self):
		from erpnext.stock.item_code_rule import (
			GROUP_CODE_LENGTH,
			guard_item_group_code,
			require_component_code,
			validate_component_code,
		)

		label = _("Mã nhóm (Item Group Code)")
		validate_component_code(self, "item_group_code", label, GROUP_CODE_LENGTH)
		require_component_code(self, "item_group_code", label)
		guard_item_group_code(self)

	def before_rename(self, olddn, newdn, merge=False, group_fname="is_group"):
		from erpnext.stock.item_code_rule import guard_item_group_merge

		super().before_rename(olddn, newdn, merge, group_fname)
		guard_item_group_merge(olddn, newdn, merge)

	def after_rename(self, olddn, newdn, merge=False):
		from erpnext.stock.item_code_rule import apply_merge_cascade

		super().after_rename(olddn, newdn, merge)
		apply_merge_cascade(merge)

	def check_item_tax(self):
		"""Check whether Tax Rate is not entered twice for same Tax Type"""
		check_list = []
		for d in self.get("taxes"):
			if d.item_tax_template:
				if (d.item_tax_template, d.tax_category) in check_list:
					frappe.throw(
						_("{0} entered twice {1} in Item Taxes").format(
							frappe.bold(d.item_tax_template),
							f"for tax category {frappe.bold(d.tax_category)}" if d.tax_category else "",
						)
					)
				else:
					check_list.append((d.item_tax_template, d.tax_category))

	def on_update(self):
		from erpnext.stock.item_code_rule import apply_cascade

		NestedSet.on_update(self)
		self.validate_one_root()
		self.delete_child_item_groups_key()
		apply_cascade(self)

	def on_trash(self):
		NestedSet.on_trash(self, allow_root_deletion=True)
		self.delete_child_item_groups_key()

	def delete_child_item_groups_key(self):
		frappe.cache().hdel("child_item_groups", self.name)

	def validate_item_group_defaults(self):
		from erpnext.stock.doctype.item.item import validate_item_default_company_links

		validate_item_default_company_links(self.item_group_defaults)


def get_child_item_groups(item_group_name):
	item_group = frappe.get_cached_value("Item Group", item_group_name, ["lft", "rgt"], as_dict=1)

	child_item_groups = [
		d.name
		for d in frappe.get_all(
			"Item Group", filters={"lft": (">=", item_group.lft), "rgt": ("<=", item_group.rgt)}
		)
	]

	return child_item_groups or {}


def get_item_group_defaults(item, company):
	item = frappe.get_cached_doc("Item", item)
	item_group = frappe.get_cached_doc("Item Group", item.item_group)

	for d in item_group.item_group_defaults or []:
		if d.company == company:
			row = d.as_dict(no_private_properties=True)
			row.pop("name")
			return row

	return frappe._dict()

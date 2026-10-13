import copy

import frappe
from frappe import _
from frappe.model.document import Document


class Brand(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from erpnext.stock.doctype.item_default.item_default import ItemDefault

		brand: DF.Data
		brand_code: DF.Data | None
		brand_defaults: DF.Table[ItemDefault]
		description: DF.Text | None
		image: DF.AttachImage | None
	# end: auto-generated types

	def validate(self):
		from erpnext.stock.item_code_rule import (
			BRAND_CODE_LENGTH,
			guard_brand_code,
			require_component_code,
			validate_component_code,
		)

		label = _("Mã thương hiệu (Brand Code)")
		validate_component_code(self, "brand_code", label, BRAND_CODE_LENGTH)
		require_component_code(self, "brand_code", label)
		guard_brand_code(self)

	def on_update(self):
		from erpnext.stock.item_code_rule import apply_cascade

		apply_cascade(self)

	def before_rename(self, old, new, merge=False):
		from erpnext.stock.item_code_rule import guard_brand_merge

		guard_brand_merge(old, new, merge)

	def after_rename(self, old, new, merge=False):
		from erpnext.stock.item_code_rule import apply_merge_cascade

		apply_merge_cascade(merge)


def get_brand_defaults(item, company):
	item = frappe.get_cached_doc("Item", item)
	if item.brand:
		brand = frappe.get_cached_doc("Brand", item.brand)

		for d in brand.brand_defaults or []:
			if d.company == company:
				row = d.as_dict(no_private_properties=True)
				row.pop("name")
				return row

	return frappe._dict()

from frappe.model.document import Document


class ItemSupplier(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		is_default: DF.Check
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		supplier: DF.Link
		supplier_part_no: DF.Data | None
		supplier_part_no_key: DF.Data | None
	# end: auto-generated types

	pass

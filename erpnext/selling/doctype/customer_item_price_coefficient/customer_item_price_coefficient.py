# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

from frappe.model.document import Document


class CustomerItemPriceCoefficient(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		den_ngay: DF.Date | None
		he_so: DF.Float
		item_code: DF.Link
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		so_hop_dong: DF.Data | None
		tu_ngay: DF.Date
	# end: auto-generated types

	pass

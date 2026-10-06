# import frappe
from frappe.model.document import Document


class PeggedCurrencies(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from erpnext.accounts.doctype.pegged_currencies.pegged_currencies import PeggedCurrencies

		pegged_currency_item: DF.Table[PeggedCurrencies]
	# end: auto-generated types

	pass

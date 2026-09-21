# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class FSSubsidiaryEntityItem(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		address: DF.Data | None
		benefit_percent: DF.Percent
		entity_name: DF.Data
		entity_type: DF.Literal["C\u00f4ng ty con", "C\u00f4ng ty li\u00ean doanh, li\u00ean k\u1ebft", "\u0110\u01a1n v\u1ecb tr\u1ef1c thu\u1ed9c"]
		ownership_percent: DF.Percent
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		voting_percent: DF.Percent
	# end: auto-generated types
	pass

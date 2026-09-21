# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint


class DebtReconciliationSettings(Document):
	def validate(self):
		for fieldname, low, high in (
			("generation_day", 1, 28),
			("generation_hour", 0, 23),
			("response_deadline_day", 1, 28),
		):
			value = cint(self.get(fieldname))
			if not low <= value <= high:
				frappe.throw(
					_("{0} phải nằm trong khoảng {1}–{2}.").format(self.meta.get_label(fieldname), low, high)
				)

# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

import frappe
from frappe.model.document import Document
from frappe.query_builder import Interval
from frappe.query_builder.functions import Now


class SupplyNotificationDispatchLog(Document):
	@staticmethod
	def clear_old_logs(days=180):
		table = frappe.qb.DocType("Supply Notification Dispatch Log")
		frappe.db.delete(table, filters=(table.creation < (Now() - Interval(days=days))))

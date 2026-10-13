import frappe
from frappe import _
from frappe.model.document import Document


class LocationLedgerEntry(Document):
	def on_trash(self):
		frappe.throw(_("Không xoá được dòng sổ vị trí. Sổ chỉ ghi thêm; huỷ chứng từ sẽ ghi bút toán đảo."))

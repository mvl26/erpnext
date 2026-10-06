import frappe


def execute():
	frappe.reload_doc("stock", "doctype", "pick_list")
	frappe.db.sql(
		"""UPDATE `tabPick List` set purpose = 'Delivery'
        WHERE docstatus = 1  and purpose = 'Delivery against Sales Order' """
	)

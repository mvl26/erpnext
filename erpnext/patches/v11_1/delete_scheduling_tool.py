import frappe


def execute():
	if frappe.db.exists("DocType", "Scheduling Tool"):
		frappe.delete_doc("DocType", "Scheduling Tool", ignore_permissions=True)

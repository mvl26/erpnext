import frappe


def execute():
	frappe.delete_doc("Page", "modules_setup")

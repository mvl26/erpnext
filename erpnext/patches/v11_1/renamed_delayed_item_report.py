import frappe


def execute():
	for report in ["Delayed Order Item Summary", "Delayed Order Summary"]:
		if frappe.db.exists("Report", report):
			frappe.delete_doc("Report", report)

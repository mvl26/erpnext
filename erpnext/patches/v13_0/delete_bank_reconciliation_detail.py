import frappe


def execute():
	if frappe.db.exists("DocType", "Bank Reconciliation Detail") and frappe.db.exists(
		"DocType", "Bank Clearance Detail"
	):
		frappe.delete_doc("DocType", "Bank Reconciliation Detail", force=1)

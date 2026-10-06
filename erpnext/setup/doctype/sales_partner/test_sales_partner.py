import frappe

test_records = frappe.get_test_records("Sales Partner")

test_ignore = ["Item Group"]

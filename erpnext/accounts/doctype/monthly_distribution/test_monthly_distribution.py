import unittest

import frappe

test_records = frappe.get_test_records("Monthly Distribution")


class TestMonthlyDistribution(unittest.TestCase):
	pass

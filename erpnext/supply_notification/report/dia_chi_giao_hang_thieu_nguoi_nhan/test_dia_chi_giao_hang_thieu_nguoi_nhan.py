# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.supply_notification.report.dia_chi_giao_hang_thieu_nguoi_nhan.dia_chi_giao_hang_thieu_nguoi_nhan import (
	execute,
)
from erpnext.supply_notification.tests import fixtures


class TestDiaChiGiaoHangThieuNguoiNhan(FrappeTestCase):
	def test_address_without_a_contact_is_listed(self):
		address = fixtures.ensure_address(title=f"Kho thieu {frappe.generate_hash(length=5)}", phone="")

		rows = {row["address"]: row for row in execute()[1]}

		self.assertIn(address, rows)
		self.assertIn("người nhận", rows[address]["missing"])
		self.assertIn("điện thoại", rows[address]["missing"])

	def test_address_with_contact_and_phone_is_not_listed(self):
		address = fixtures.ensure_address(
			title=f"Kho du {frappe.generate_hash(length=5)}", phone="0901 234 567", contact_name="Anh Kho"
		)

		self.assertNotIn(address, [row["address"] for row in execute()[1]])

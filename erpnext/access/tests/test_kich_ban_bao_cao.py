"""Bộ kịch bản bắt buộc, nhóm C — báo cáo và perm level, T39-T41, T56, T57 (đặc tả mục 13, plan Task 26).

Chạy trên site TEST đã đồng bộ ma trận thật (Custom Role của report do `ui_roles.sync_report_roles` ghi); trên
site miyano mọi test bỏ qua (`require_test_site`). Một report không có trên site thì test bỏ qua đúng report đó.

T-number -> test                                       -> dùng lại
T39 test_t39_stu_bi_chan_bao_cao_gia_von               -> scenarios.report_opens (Report.is_permitted + quyền 'report')
T40 test_t40_bao_cao_duoc_mo_theo_g7_va_custom_role    -> scenarios.report_opens
T41 test_t41_stu_khong_thay_cot_gia_tri_kho            -> scenarios.fields_with_access (permlevel 1 của Stock Ledger Entry)
T56 test_t56_bao_cao_muc_11_2_bi_chan                  -> scenarios.report_opens
T57 test_t57_report_ngoai_bang_11_2_bi_khoa            -> matrix.reports (R1: khóa bằng role LK)
"""

import frappe

from erpnext.access.permissions.matrix import load_matrix
from erpnext.access.tests.helpers import require_test_site
from erpnext.access.tests.scenarios import ScenarioCase, fields_with_access, report_opens


class TestKichBanBaoCao(ScenarioCase):
	SHOW_TRANSACTION_COMMIT_WARNINGS = True

	def setUp(self):
		require_test_site(self)
		self.prepare()

	def opens(self, code: str, report: str) -> bool:
		if not frappe.db.exists("Report", report):
			self.skipTest(f"site không có report {report}")
		return report_opens(self.user(code), report)

	def test_t39_stu_bi_chan_bao_cao_gia_von(self):
		for report in ("Stock Balance", "Stock Ledger", "Gross Profit"):
			with self.subTest(report):
				self.assertFalse(self.opens("STU", report))

	def test_t40_bao_cao_duoc_mo_theo_g7_va_custom_role(self):
		for code, report in (
			("SU", "Accounts Receivable"),
			("STU", "Stock Projected Qty"),
			("HM", "Salary Register"),
		):
			with self.subTest(code=code, report=report):
				self.assertTrue(self.opens(code, report))

	def test_t41_stu_khong_thay_cot_gia_tri_kho(self):
		stu = fields_with_access(self.user("STU"), "Stock Ledger Entry")
		self.assertIn("actual_qty", stu)  # control: level 0 is readable
		for column in ("valuation_rate", "stock_value"):
			self.assertNotIn(column, stu)
		self.assertIn("valuation_rate", fields_with_access(self.user("AM"), "Stock Ledger Entry"))

	def test_t56_bao_cao_muc_11_2_bi_chan(self):
		for code, report in (
			("SYS", "MVL Salary Register"),
			("STU", "Item Prices"),
			("STU", "Warehouse Wise Stock Balance"),
			("STU", "Stock Analytics"),
			("DH", "Unpaid Expense Claim"),
		):
			with self.subTest(code=code, report=report):
				self.assertFalse(self.opens(code, report))

	def test_t57_report_ngoai_bang_11_2_bi_khoa(self):
		listed = set(load_matrix().reports)
		unlisted = [
			r
			for r in frappe.get_all("Report", filters={"disabled": 0}, pluck="name", order_by="name")
			if r not in listed
		]
		if not unlisted:
			self.skipTest("site không có report nào ngoài bảng 11.2")
		sample = ["BOM Explorer"] if "BOM Explorer" in unlisted else []
		sample += [r for r in unlisted if r not in sample][:10]
		for code in ("GDVH", "AM", "SYS"):
			for report in sample:
				with self.subTest(code=code, report=report):
					self.assertFalse(report_opens(self.user(code), report))

"""Bộ kịch bản bắt buộc, nhóm A — quyền và phạm vi dữ liệu, T01-T15 (đặc tả mục 13, plan Task 26).

Chạy trên site TEST đã đồng bộ ma trận thật (`require_test_site`); trên site miyano mọi test bỏ qua.
Người dùng là user tạm mang đúng Role Profile `RP-*` (xem `scenarios.PROFILES`); chứng từ chỉ dựng trong bộ nhớ.

T-number -> test                                  -> dùng lại
T01  test_t01_dh_khong_doc_phieu_luong            -> test_scope.make_department (cùng fixture phòng ban H8)
T02  test_t02_hu_bi_chan_luong                    -> scenarios.fields_with_access (permlevel của Custom DocPerm)
T03  test_t03_cus_khong_doc_don_cua_khach_khac    -> User Permission trên Customer (phạm vi `c`)
T04  test_t04_khong_ai_xoa_chung_tu_da_huy        -> frappe.has_permission, không ma trận nào cấp D
T05  test_t05_sys_khong_tao_pe_si                 -> frappe.has_permission
T06  test_t06_vw_khong_tao_si                     -> frappe.has_permission
T07  test_t07_su_mk_khong_xoa_lead                -> frappe.has_permission
T08  test_t08_workspace_pda                       -> UAT (giao diện workspace) — Task 27
T08b test_t08b_ngoai_le_g10_contact_address       -> frappe.has_permission (ngoại lệ G10)
T09  test_t09_su_khong_thay_contract_nhan_vien    -> contract_scope.has_permission (H1, test_contract_scope)
T10  test_t10_ktnv_khong_tao_cho_nguoi_khac       -> scope H8 (test_scope T10) qua frappe.has_permission
T11  test_t11_nsnv_khong_doc_expense_claim_khac   -> scope H8 (test_scope T11) qua frappe.has_permission
T12  test_t12_su_thay_du_khach_khi_strict_0       -> frappe.get_list + System Settings.apply_strict_user_permissions
T13  test_t13_rp_nv_doc_duoc_danh_muc_g8          -> frappe.has_permission (test_scope T13 chỉ kiểm hook)
T14  test_t14_nhan_vien_khong_sua_gio_checkin     -> scenarios.fields_with_access
T15  test_t15_au_phieu_luong_va_make_bank_entry   -> frappe.has_permission (Make Bank Entry kiểm `write` Payroll Entry)
"""

import frappe

from erpnext.access import contract_scope
from erpnext.access.tests.helpers import require_test_site
from erpnext.access.tests.scenarios import (
	ScenarioCase,
	can,
	employee_of,
	ensure_customer,
	fields_with_access,
	memdoc,
	new_employee,
)
from erpnext.access.tests.test_scope import make_department
from erpnext.access.tests.test_workflow_guard import _ensure


def allow_for(user: str, allow: str, value: str) -> None:
	"""A User Permission row (all doctypes) — the per-user scope of the matrix."""
	frappe.get_doc(
		{
			"doctype": "User Permission",
			"user": user,
			"allow": allow,
			"for_value": value,
			"apply_to_all_doctypes": 1,
		}
	).insert(ignore_permissions=True)
	frappe.clear_cache(user=user)


class TestKichBanQuyen(ScenarioCase):
	SHOW_TRANSACTION_COMMIT_WARNINGS = True

	def setUp(self):
		require_test_site(self)
		self.prepare()

	def test_t01_dh_khong_doc_phieu_luong(self):
		dh = self.user("DH")
		slip = memdoc("Salary Slip", employee=new_employee(make_department("T01", approver=dh)))
		self.assertFalse(can(dh, "Salary Slip", "read", slip))

	def test_t02_hu_bi_chan_luong(self):
		hu = self.user("HU")
		self.assertFalse(can(hu, "Salary Structure Assignment", "read"))
		salary_fields = {"ctc", "salary_currency", "salary_mode", "bank_name", "bank_ac_no", "iban"}
		self.assertFalse(salary_fields & fields_with_access(hu, "Employee"))

	def test_t03_cus_khong_doc_don_cua_khach_khac(self):
		cus = self.user("CUS")
		mine, other = ensure_customer(), ensure_customer()
		allow_for(cus, "Customer", mine)
		self.assertTrue(can(cus, "Sales Order", "read", memdoc("Sales Order", customer=mine)))
		self.assertFalse(can(cus, "Sales Order", "read", memdoc("Sales Order", customer=other)))
		for customer in (mine, other):  # CUS holds no cell at all on Quotation
			quotation = memdoc("Quotation", quotation_to="Customer", party_name=customer)
			self.assertFalse(can(cus, "Quotation", "read", quotation))

	def test_t04_khong_ai_xoa_chung_tu_da_huy(self):
		doctypes = ("Sales Order", "Purchase Order", "Sales Invoice", "Payment Entry", "Journal Entry")
		for code in ("GDVH", "AM", "PM", "HM", "SYS"):
			for doctype in doctypes:
				cancelled = memdoc(doctype, docstatus=2)
				with self.subTest(code=code, doctype=doctype):
					self.assertFalse(can(self.user(code), doctype, "delete", cancelled))

	def test_t05_sys_khong_tao_pe_si(self):
		for doctype in ("Payment Entry", "Sales Invoice"):
			self.assertFalse(can(self.user("SYS"), doctype, "create"), doctype)

	def test_t06_vw_khong_tao_si(self):
		self.assertFalse(can(self.user("VW"), "Sales Invoice", "create"))

	def test_t07_su_mk_khong_xoa_lead(self):
		for code in ("SU", "MK"):
			with self.subTest(code):
				self.assertTrue(can(self.user(code), "Lead", "create"))  # the cell exists, only D is missing
				self.assertFalse(can(self.user(code), "Lead", "delete"))
				self.assertFalse(
					can(self.user(code), "Lead", "delete", memdoc("Lead", owner=self.user(code)))
				)

	def test_t08_workspace_pda(self):
		self.skipTest(
			"UAT: giao diện workspace/đường dẫn /app của user PDA — chuyển sang checklist UAT Task 27"
		)

	def test_t08b_ngoai_le_g10_contact_address(self):
		for code in ("PDA", "CUS", "SUP"):
			for doctype in ("Contact", "Address"):
				with self.subTest(code=code, doctype=doctype):
					self.assertFalse(can(self.user(code), doctype, "create"))
		su = self.user("SU")
		for doctype in ("Contact", "Address"):
			with self.subTest(doctype=doctype):
				self.assertFalse(can(su, doctype, "delete", memdoc(doctype, owner=su)))

	def test_t09_su_khong_thay_contract_nhan_vien(self):
		su = self.user("SU")
		contract = memdoc("Contract", party_type="Employee")
		self.assertIs(contract_scope.has_permission(contract, "read", su), False)
		self.assertFalse(can(su, "Contract", "read", contract))
		self.assertIsNone(
			contract_scope.has_permission(memdoc("Contract", party_type="Customer"), "read", su)
		)

	def test_t10_ktnv_khong_tao_cho_nguoi_khac(self):
		au = self.user("AU")  # KT-NV: AU + EMP
		other = new_employee()
		for doctype in ("Expense Claim", "Leave Application"):
			with self.subTest(doctype):
				self.assertFalse(can(au, doctype, "create", memdoc(doctype, employee=other)))
				self.assertTrue(can(au, doctype, "create", memdoc(doctype, employee=employee_of(au))))

	def test_t11_nsnv_khong_doc_expense_claim_khac(self):
		hu = self.user("HU")  # NS-NV: HU + EMP
		self.assertFalse(can(hu, "Expense Claim", "read", memdoc("Expense Claim", employee=new_employee())))
		self.assertTrue(can(hu, "Expense Claim", "read", memdoc("Expense Claim", employee=employee_of(hu))))

	def test_t12_su_thay_du_khach_khi_strict_0(self):
		su = self.user("SU")
		self.assertEqual(
			int(frappe.db.get_single_value("System Settings", "apply_strict_user_permissions") or 0), 0
		)
		currency = frappe.db.get_value("Currency", {"enabled": 1}, "name")
		price_list = _ensure(
			"Price List",
			{"price_list_name": "_Test KB PL"},
			{"price_list_name": "_Test KB PL", "currency": currency, "selling": 1, "enabled": 1},
		)
		allow_for(su, "Price List", price_list)
		customer = ensure_customer()
		frappe.db.set_value("Customer", customer, "default_price_list", None)
		visible = frappe.get_list("Customer", filters={"name": customer}, pluck="name", user=su)
		self.assertEqual(visible, [customer])

	def test_t13_rp_nv_doc_duoc_danh_muc_g8(self):
		nv = self.user("NV")  # RP-NV: only the BASE pack (Employee + Projects User)
		for doctype in ("Company", "Warehouse", "Currency", "Cost Center"):
			with self.subTest(doctype):
				self.assertTrue(can(nv, doctype, "read"))
				name = frappe.db.get_value(doctype, {}, "name")
				if name:
					self.assertTrue(can(nv, doctype, "read", frappe.get_doc(doctype, name)))

	def test_t14_nhan_vien_khong_sua_gio_checkin(self):
		nv = self.user("NV")
		self.assertTrue(can(nv, "Employee Checkin", "create"))
		checkin = memdoc("Employee Checkin", employee=employee_of(nv))
		self.assertFalse(can(nv, "Employee Checkin", "write", checkin))
		self.assertNotIn("time", fields_with_access(nv, "Employee Checkin", "write"))

	def test_t15_au_phieu_luong_va_make_bank_entry(self):
		au = self.user("AU")
		slip = memdoc("Salary Slip", employee=new_employee())
		self.assertFalse(can(au, "Salary Slip", "read", slip))
		self.assertTrue(
			can(au, "Payroll Entry", "write")
		)  # PayrollEntry.make_bank_entry: check_permission("write")

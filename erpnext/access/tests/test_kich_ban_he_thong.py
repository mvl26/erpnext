"""Bộ kịch bản bắt buộc, nhóm D — hệ thống, sync, code, T42-T55 (đặc tả mục 13, plan Task 26).

Chạy trên site TEST đã đồng bộ ma trận thật; trên site miyano mọi test bỏ qua (`require_test_site`).
`test_t45_migrate_hai_lan` chạy `sync` hai lần và các hook after_migrate của erpnext — việc đó COMMIT (DDL của
Custom Field, ghi Custom DocPerm), nên chỉ được chạy trên site test; `require_test_site` chặn nó trên miyano.

T-number -> test                                        -> dùng lại
T42  test_t42_doi_phan_quyen_gdvh_nhan_email            -> test_audit_mail.Mailbox + audit_mail.on_change (H4)
T43  test_t43_profile_tam_het_han_ve_profile_goc        -> test_temp_profiles.make_profile/make_user + temp_profiles.expire (H7)
T44  test_t44_chi_ktt_phat_hanh_hdon                    -> einvoice.issue.issue_invoice gọi bằng 3 profile thật (test_einvoice_roles T44)
T45  test_t45_migrate_hai_lan                           -> sync._run_unguarded x2 + mọi hook after_migrate của erpnext xen giữa
T45b test_t45b_hrms_after_migrate                       -> SKIP: cần hrms C5/C6
T46  test_t46_pda_di_qua_ba_trang_it_qt_bi_chan         -> test_vai_tro_pda.GUARDS bằng role thật + phạm vi Warehouse (User Permission)
T46b test_t46b_pda_sua_don_gia_dn                       -> UAT: giá trên trang PDA — Task 27
T47  test_t47_profile_ghep_it_qt_assetcore              -> SKIP: cần hrms C5/C6
T48  test_t48_kho_tk_nhap_pr_serial_lo_kho_tp_huy       -> frappe.has_permission (S/X trên SBB) + phạm vi Warehouse; chưa dựng PR serial/lô thật
T49  test_t49_o_chon_user_tren_ui                       -> UAT: ô chọn user trên UI — Task 27
T50  test_t50_it_qt_gan_role_profile_cho_user_moi       -> User.insert()/save() thật bằng IT-QT
T51  test_t51_au_brt_thu_tien_chi_va_je                 -> workflow_guard H11 qua scenarios.run_guards (test_workflow_guard T51)
T52  test_t52_gdvh_duyet_thay_stock_reconciliation_h10  -> workflow_guard H10 (regex 'đã duyệt một bước') + bare_row (test_workflow_guard R-18)
T53  test_t53_attendance_request_custom_approver        -> SKIP: cần hrms C5/C6
T54  test_t54_ap_khong_phai_coo_khong_duyet_bt          -> scenarios.transitions (WF-BT thật)
T55  test_t55_am_khong_sua_truc_tiep_bank_account       -> workflow_guard.before_validate (H5) + transitions
"""

from unittest.mock import patch

import frappe
from frappe.utils import add_days, getdate

from erpnext.access import audit_mail, temp_profiles, workflow_guard
from erpnext.access.permissions import sync
from erpnext.access.permissions.workflows import _differs, build_workflow, workflow_name
from erpnext.access.tests.helpers import require_test_site
from erpnext.access.tests.scenarios import (
	H3,
	LIMITS,
	ScenarioCase,
	as_user,
	can,
	memdoc,
	run_guards,
	transitions,
	warehouse_pair,
)
from erpnext.access.tests.test_audit_mail import Mailbox
from erpnext.access.tests.test_temp_profiles import make_profile, make_user, stamp
from erpnext.access.tests.test_workflow_guard import bare_row, make_doc, saving
from erpnext.einvoice import issue
from erpnext.warehouse_operations.tests.test_vai_tro_pda import GUARDS


class TestKichBanHeThong(ScenarioCase):
	SHOW_TRANSACTION_COMMIT_WARNINGS = True

	def setUp(self):
		require_test_site(self)
		self.prepare()

	def assert_warehouse_scope(self, user, doctype, ptype, field):
		"""True for a document in the user's assigned Warehouse, False for one in another Warehouse."""
		assigned, other = warehouse_pair(user)
		self.assertTrue(
			can(user, doctype, ptype, memdoc(doctype, **{field: assigned})), (doctype, "assigned")
		)
		self.assertFalse(can(user, doctype, ptype, memdoc(doctype, **{field: other})), (doctype, "other"))

	# -- T42-T45 ---------------------------------------------------------------------------------

	def test_t42_doi_phan_quyen_gdvh_nhan_email(self):
		gdvh = self.user("GDVH")
		box = Mailbox()

		def mailed(change):
			before = len(box.sent)
			change()
			sent = box.sent[before:]
			self.assertTrue(sent, "không có email nào được gửi")
			for mail in sent:
				self.assertIn(gdvh, mail["recipients"])

		def role_profile():
			frappe.get_doc(
				{
					"doctype": "Role Profile",
					"role_profile": f"RP-KB-{frappe.generate_hash(length=6)}",
					"roles": [{"role": "Newsletter Manager"}],
				}
			).insert(ignore_permissions=True)

		def user_permission():
			frappe.get_doc(
				{
					"doctype": "User Permission",
					"user": self.user("NV"),
					"allow": "User",
					"for_value": "Administrator",
				}
			).insert(ignore_permissions=True)

		def approval_limits():
			limits = frappe.get_doc(LIMITS)
			limits.h1 = limits.h1 + 1
			limits.save(ignore_permissions=True)

		def in_memory(doctype, **fields):  # written by sync/UI in bulk: judge the hook, don't touch the table
			return lambda: audit_mail.on_change(frappe.get_doc({"doctype": doctype, **fields}), "on_update")

		events = frappe.get_hooks("doc_events")
		handler = "erpnext.access.audit_mail.on_change"

		def registered(doctype, event):
			value = events.get(doctype, {}).get(event, [])
			return handler in ([value] if isinstance(value, str) else value)

		for doctype in (
			"Has Role",
			"Role Profile",
			"Custom DocPerm",
			"Custom Role",
			"User Permission",
			"Workflow",
			"MVL Approval Limits",
		):
			for event in ("on_update", "on_trash"):
				self.assertTrue(registered(doctype, event), (doctype, event))
		self.assertTrue(registered("User", "on_update"))

		with patch.object(frappe, "sendmail", box):
			mailed(role_profile)
			mailed(user_permission)
			mailed(approval_limits)
			mailed(in_memory("Custom DocPerm", parent="ToDo", role="Newsletter Manager"))
			mailed(in_memory("Custom Role", report="General Ledger"))

	def test_t43_profile_tam_het_han_ve_profile_goc(self):
		base = "RP-KT-NV"
		temporary = f"{base}+TMP-{stamp(add_days(getdate(), -1))}"
		make_profile(temporary, "Newsletter Manager")
		user = make_user(temporary)
		with patch.object(frappe, "log_error"):  # log_error writes a real Error Log row for orphan profiles
			moved = temp_profiles.expire()
		self.assertIn(user, moved)
		self.assertEqual(frappe.db.get_value("User", user, "role_profile_name"), base)
		roles = set(frappe.get_all("Has Role", filters={"parent": user}, pluck="role"))
		self.assertLessEqual({r.role for r in frappe.get_doc("Role Profile", base).roles}, roles)
		self.assertNotIn("Newsletter Manager", roles)

	def test_t44_chi_ktt_phat_hanh_hdon(self):
		with patch.object(issue, "check_enabled"):
			for code in ("AU", "SYS"):  # KT-NV, IT-QT
				with self.subTest(code), as_user(self.user(code)), self.assertRaises(frappe.PermissionError):
					issue.issue_invoice("KB-NOT-A-REAL-FEI")
			with as_user(self.user("AM")), self.assertRaises(frappe.DoesNotExistError):
				issue.issue_invoice(
					"KB-NOT-A-REAL-FEI"
				)  # KT-KTT passes the role gate, then finds no document

	def test_t45_migrate_hai_lan(self):
		"""Chạy sync hai lần (có hook after_migrate của erpnext xen giữa) — COMMIT, chỉ site test."""
		m, site, problems = sync._prepare()
		self.assertEqual(problems.errors, [])
		sync._run_unguarded(m, site)
		for dotted in frappe.get_hooks("after_migrate", app_name="erpnext"):
			if (
				dotted != "erpnext.access.permissions.sync.after_migrate"
			):  # the sync itself is run above/below
				frappe.get_attr(
					dotted
				)()  # einvoice / supply_notification must not grant permissions of their own
		m, site, _problems = sync._prepare()
		counters = sync._run_unguarded(m, site)["counters"]
		for key in ("inserted", "deleted", "updated"):
			self.assertEqual(counters.get(key, 0), 0, key)
		for code, wf in m.workflows.items():
			for doctype in wf["doctypes"]:
				if not frappe.db.exists("DocType", doctype):
					continue
				with self.subTest(code=code, doctype=doctype):
					self.assertFalse(_differs(build_workflow(m, code, doctype)))
					active = frappe.db.get_value("Workflow", {"document_type": doctype, "is_active": 1})
					self.assertEqual(active, workflow_name(code, doctype))  # no legacy workflow came back

	def test_t45b_hrms_after_migrate(self):
		self.skipTest("Cần hrms C5/C6 — xem docs/rbac/BanGiao_C5_C6_hrms.md")

	# -- T46-T49 ---------------------------------------------------------------------------------

	def test_t46_pda_di_qua_ba_trang_it_qt_bi_chan(self):
		pda, sys = self.user("PDA"), self.user("SYS")
		for name, guard in GUARDS.items():
			with self.subTest(name):
				with as_user(pda):
					guard()
				with as_user(sys), self.assertRaises(frappe.PermissionError):
					guard()
		for doctype, ptype in (
			("Delivery Note", "submit"),
			("Delivery Note", "write"),
			("Purchase Receipt", "read"),
			("Location Transfer", "create"),
		):
			self.assertTrue(can(pda, doctype, ptype), (doctype, ptype))
		self.assertFalse(can(sys, "Delivery Note", "submit"))
		self.assert_warehouse_scope(pda, "Delivery Note", "write", "set_warehouse")
		self.assert_warehouse_scope(pda, "Purchase Receipt", "read", "set_warehouse")

	def test_t46b_pda_sua_don_gia_dn(self):
		self.skipTest(
			"UAT: đơn giá trên trang PDA (Maintain Same Rate = Stop) — chuyển sang checklist UAT Task 27"
		)

	def test_t47_profile_ghep_it_qt_assetcore(self):
		self.skipTest("Cần hrms C5/C6 — xem docs/rbac/BanGiao_C5_C6_hrms.md")

	def test_t48_kho_tk_nhap_pr_serial_lo_kho_tp_huy(self):
		stu, stm = self.user("STU"), self.user("STM")
		self.assertTrue(can(stu, "Purchase Receipt", "submit"))
		self.assertTrue(can(stu, "Serial and Batch Bundle", "submit"))
		self.assertTrue(can(stm, "Purchase Receipt", "cancel"))
		self.assertTrue(can(stm, "Serial and Batch Bundle", "cancel"))
		# narrowed: no real serial/batch receipt is built; the Warehouse scope of KHO-TK is judged on documents
		self.assert_warehouse_scope(stu, "Purchase Receipt", "submit", "set_warehouse")

	def test_t49_o_chon_user_tren_ui(self):
		self.skipTest("UAT: ô chọn người duyệt/người giao trên form — chuyển sang checklist UAT Task 27")

	# -- T50-T52 ---------------------------------------------------------------------------------

	def test_t50_it_qt_gan_role_profile_cho_user_moi(self):
		email = f"kb-t50-{frappe.generate_hash(length=8)}@example.com"
		with as_user(self.user("SYS")):
			user = frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": "KB",
					"send_welcome_email": 0,
					"role_profile_name": "RP-NV",
				}
			)
			user.insert()
			user.role_profile_name = "RP-KT-NV"
			user.save()
		self.assertIn("Accounts User", frappe.get_all("Has Role", filters={"parent": email}, pluck="role"))

	def test_t51_au_brt_thu_tien_chi_va_je(self):
		au = self.user("AU")
		receive = make_doc("Payment Entry", "Nháp", au, payment_type="Receive", base_paid_amount=H3 * 10)
		with as_user(au):
			run_guards(saving(receive, docstatus=1))  # Bank Reconciliation Tool: receipt posts directly
		pay = make_doc("Payment Entry", "Nháp", au, payment_type="Pay", base_paid_amount=H3 + 1)
		journal = make_doc("Journal Entry", "Nháp", au)
		for label, draft in (("Payment Entry chi > H3", pay), ("Journal Entry", journal)):
			with self.subTest(label), as_user(au), self.assertRaises(frappe.PermissionError):
				run_guards(saving(draft, docstatus=1))

	def test_t52_gdvh_duyet_thay_stock_reconciliation_h10(self):
		self.require_workflow("Stock Reconciliation")
		gdvh, am, stu = self.user("GDVH"), self.user("AM"), self.user("STU")
		fields = {"name": bare_row("Stock Reconciliation"), "difference_amount": 100}
		with as_user(gdvh):
			step1 = saving(make_doc("Stock Reconciliation", "Chờ trưởng kho", stu, **fields), state="Chờ KTT")
			run_guards(step1)
			workflow_guard.on_change(step1)
			step2 = saving(
				make_doc("Stock Reconciliation", "Chờ KTT", stu, **fields), state="Đã ghi sổ", docstatus=1
			)
			with self.assertRaisesRegex(frappe.PermissionError, "đã duyệt một bước"):  # H10, not R-16
				run_guards(step2)
		with as_user(am):  # a different approver finishes the chain
			run_guards(
				saving(
					make_doc("Stock Reconciliation", "Chờ KTT", stu, **fields), state="Đã ghi sổ", docstatus=1
				)
			)

	# -- T53-T55 ---------------------------------------------------------------------------------

	def test_t53_attendance_request_custom_approver(self):
		self.skipTest("Cần hrms C5/C6 — xem docs/rbac/BanGiao_C5_C6_hrms.md")

	def test_t54_ap_khong_phai_coo_khong_duyet_bt(self):
		self.require_workflow("Business Trip")
		ap, coo = self.user("VW"), self.user("GDVH")  # both hold AP
		self.assertEqual(
			transitions(ap, "Business Trip", "Chờ COO duyệt", owner=coo, approver_coo=coo), set()
		)
		approved = transitions(coo, "Business Trip", "Chờ COO duyệt", owner=ap, approver_coo=coo)
		self.assertIn(("Duyệt", "COO đã duyệt"), approved)

	def test_t55_am_khong_sua_truc_tiep_bank_account(self):
		self.require_workflow("Bank Account")
		am = self.user("AM")
		approved = make_doc("Bank Account", "Đã duyệt", am, bank_account_no="111")
		with as_user(am), self.assertRaises(frappe.ValidationError):
			workflow_guard.before_validate(saving(approved, bank_account_no="222"))
		self.assertIn(("Sửa", "Nháp"), transitions(am, "Bank Account", "Đã duyệt", owner=am))
		draft = make_doc("Bank Account", "Nháp", am, bank_account_no="111")
		with as_user(am):  # after "Sửa" the draft is editable again
			workflow_guard.before_validate(saving(draft, bank_account_no="222"))

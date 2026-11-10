"""Bộ kịch bản bắt buộc, nhóm B — workflow và luồng duyệt, T16-T38 (đặc tả mục 13, plan Task 26).

Chạy trên site TEST đã đồng bộ ma trận thật; workflow là workflow thật do sync dựng (không tạo Workflow nào ở
đây). Trên site miyano mọi test bỏ qua (`require_test_site`). Hạn mức H1/H2/H3 đặt trong `prepare` (chỉ site test).
Bước chuyển được hỏi thẳng `frappe.model.workflow.get_transitions` trên chứng từ trong bộ nhớ (vai trò, hạn mức,
G11, cờ `mvl_dung_gia_hd` đều do workflow thật tính); chứng từ thật chỉ dựng cho PO/JE bằng builder của
`TestWorkflowGuardOnTestSite` (`scenarios.workflow_fixtures`).

T-number -> test                                     -> dùng lại
T16 test_t16_nv_khong_tu_submit_don_cua_minh         -> frappe.has_permission (EMP không có S)
T17 test_t17_au_submit_je_chi_sang_cho_ktt           -> scenarios.transitions (WF-JE thật)
T18 test_t18_pu_khong_duyet_po_vuot_h1               -> scenarios.transitions (WF-PO thật)
T19 test_t19_api_submit_bi_chan_h11                  -> workflow_fixtures().purchase_order/journal_entry (test_workflow_guard T19)
T20 test_t20_dh_api_submit_expense_claim_cho_tbp     -> workflow_guard.before_submit qua scenarios.run_guards (H11)
T21 test_t21_su_sua_rate_khac_gia_hd                 -> test_pricing_guard.insert_parent/insert_child + pricing_guard.validate (H2)
T22 test_t22_au_dung_bank_account_chua_duyet         -> test_bank_account_guard.bank_account/payment_entry + validate (H3)
T23 test_t23_stu_ghi_so_stock_entry_cho_truong_kho   -> scenarios.transitions (WF-SE thật)
T24 test_t24_je_he_thong_ghi_so_duoc                 -> workflow_fixtures().journal_entry (test_workflow_guard T24)
T25 test_t25_khong_tu_duyet_don_nghi_cua_minh        -> scenarios.transitions (G11 trong điều kiện workflow)
T26 test_t26_sua_noi_dung_khi_dang_cho_duyet         -> workflow_fixtures().purchase_order (test_workflow_guard T26) + H5 Payroll Entry
T27 test_t27_dh_roi_hm_duyet_leave_application       -> Leave Application thật qua apply_workflow (scenarios.insert_leave_application)
T28 test_t28_am_duyet_buoc_cuoi_expense_claim        -> Expense Claim thật qua apply_workflow (scenarios.insert_expense_claim)
T29 test_t29_mh_tp_khong_duyet_po_do_minh_lap        -> scenarios.transitions (G11)
T30 test_t30_gdvh_duyet_thay_roi_bi_h10              -> workflow_fixtures().purchase_order (test_workflow_guard T30)
T31 test_t31_kt_ktt_khong_duyet_pe_do_minh_lap       -> scenarios.transitions (G11)
T32 test_t32_su_vuot_han_muc_tin_dung_sm_duoc        -> customer.check_credit_limit (Accounts Settings.credit_controller)
T33 test_t33_chi_bao_list_giu_status                 -> Workflow.override_status + cột workflow_state
T34 test_t34_huy_roi_amend_po                        -> workflow_fixtures().purchase_order (test_workflow_guard T34)
T34 test_t34b_huy_roi_amend_business_trip            -> SKIP: cần hrms C6
T35 test_t35_workflow_state_khop_status_don_nghi     -> cutover.default_targets()['Leave Application'] (STATUS_MAP) trên từng đơn đã submit
T36 test_t36_workflow_khong_ghi_de_status_expense    -> Expense Claim thật: status Unpaid do hrms; T36b thanh toán -> Paid (hrms get_payment_entry_for_employee)
T37 test_t37_so_dung_gia_hd_tu_duyet                 -> pricing_guard.validate đặt cờ (test_pricing_guard T37) + transitions WF-SO
T38 test_t38_pe_thu_tien_ghi_so_thang                -> transitions + workflow_guard.before_submit (test_workflow_guard T51)
"""

import frappe
import frappe.client
from frappe.model.workflow import apply_workflow, get_workflow

from erpnext.access import bank_account_guard, pricing_guard, workflow_guard
from erpnext.access.permissions import cutover
from erpnext.access.tests.helpers import require_test_site
from erpnext.access.tests.scenarios import (
	H1,
	H2,
	H3,
	ScenarioCase,
	as_user,
	can,
	employee_of,
	ensure_customer,
	insert_expense_claim,
	insert_leave_application,
	memdoc,
	new_employee,
	place_in_department,
	run_guards,
	transitions,
	workflow_fixtures,
)
from erpnext.access.tests.test_bank_account_guard import bank_account, payment_entry
from erpnext.access.tests.test_pricing_guard import blanket_order, selling_doc, selling_row
from erpnext.access.tests.test_workflow_guard import _company, make_doc, saving
from erpnext.selling.doctype.customer.customer import check_credit_limit


def actions(result) -> set[str]:
	return {action for action, _state in result}


class TestKichBanWorkflow(ScenarioCase):
	SHOW_TRANSACTION_COMMIT_WARNINGS = True

	def setUp(self):
		require_test_site(self)
		self.prepare()

	# -- T16-T20 ---------------------------------------------------------------------------------

	def test_t16_nv_khong_tu_submit_don_cua_minh(self):
		nv = self.user("NV")
		own = employee_of(nv)
		for doctype in ("Leave Application", "Attendance Request", "Compensatory Leave Request"):
			with self.subTest(doctype):
				self.assertFalse(can(nv, doctype, "submit", memdoc(doctype, employee=own)))

	def test_t17_au_submit_je_chi_sang_cho_ktt(self):
		self.require_workflow("Journal Entry")
		au = self.user("AU")
		self.assertEqual(transitions(au, "Journal Entry", "Nháp", owner=au), {("Gửi duyệt", "Chờ KTT")})

	def test_t18_pu_khong_duyet_po_vuot_h1(self):
		self.require_workflow("Purchase Order")
		pu = self.user("PU")
		result = transitions(pu, "Purchase Order", "Nháp", owner=pu, base_grand_total=H1 + 1)
		self.assertEqual(result, {("Gửi duyệt", "Chờ TP")})
		self.assertNotIn("Duyệt", actions(result))

	def test_t19_api_submit_bi_chan_h11(self):
		self.require_workflow("Purchase Order")
		self.require_workflow("Journal Entry")
		fx = workflow_fixtures()
		po = fx.purchase_order(H1 + 1, self.user("PU"))
		with self.assertRaises(frappe.PermissionError):
			frappe.client.submit(po.as_dict())
		self.assertEqual(fx.state(po), (0, "Nháp"))

		je = fx.journal_entry(self.user("AU"))
		with self.assertRaises(frappe.PermissionError):
			frappe.client.submit(je.as_dict())
		self.assertEqual(fx.state(je), (0, "Nháp"))

		# Data Import "Submit After Import" calls doc.submit() as the importing user: same hook, no import flag
		importing = fx.journal_entry(self.user("AU"))
		with self.assertRaises(frappe.PermissionError):
			importing.submit()
		self.assertEqual(fx.state(importing), (0, "Nháp"))

	def test_t20_dh_api_submit_expense_claim_cho_tbp(self):
		self.require_workflow("Expense Claim")
		dh = self.user("DH")
		before = make_doc("Expense Claim", "Chờ TBP", "Administrator", employee=new_employee())
		with as_user(dh), self.assertRaises(frappe.PermissionError):
			run_guards(saving(before, docstatus=1))

	# -- T21-T24 ---------------------------------------------------------------------------------

	def sales_order(self, customer, *rows):
		company = _company()
		currency = frappe.get_cached_value("Company", company, "default_currency")
		return selling_doc("Sales Order", customer, *rows, company=company, currency=currency)

	def row(self, item, rate, **fields):
		return selling_row(item, frappe.db.get_value("Item", item, "stock_uom"), rate=rate, **fields)

	def test_t21_su_sua_rate_khac_gia_hd(self):
		item, customer = workflow_fixtures().item(), ensure_customer()
		bo = blanket_order(item, 100, company=_company(), customer=customer)
		doc = self.sales_order(customer, self.row(item, 90, blanket_order=bo))
		with as_user(self.user("SU")), self.assertRaises(frappe.ValidationError):
			pricing_guard.validate(doc)

	def test_t22_au_dung_bank_account_chua_duyet(self):
		bank = frappe.get_doc({"doctype": "Bank", "bank_name": f"KB Bank {frappe.generate_hash(length=8)}"})
		bank.insert(ignore_permissions=True)
		approved = bank_account(bank.name, bank_account_guard.APPROVED)
		pending = bank_account(bank.name, "Chờ KTT")
		with as_user(self.user("AU")):
			bank_account_guard.validate(payment_entry(bank_account=approved))
			with self.assertRaises(frappe.ValidationError):
				bank_account_guard.validate(payment_entry(bank_account=pending))

	def test_t23_stu_ghi_so_stock_entry_cho_truong_kho(self):
		self.require_workflow("Stock Entry")
		stu = self.user("STU")
		for entry_type in ("Material Receipt", "Material Issue"):
			with self.subTest(entry_type):
				result = transitions(stu, "Stock Entry", "Nháp", owner=stu, stock_entry_type=entry_type)
				self.assertEqual(result, {("Gửi duyệt", "Chờ trưởng kho")})
		transfer = transitions(stu, "Stock Entry", "Nháp", owner=stu, stock_entry_type="Material Transfer")
		self.assertEqual(transfer, {("Ghi sổ", "Đã ghi sổ")})  # control: only a pure transfer posts directly

	def test_t24_je_he_thong_ghi_so_duoc(self):
		self.require_workflow("Journal Entry")
		fx = workflow_fixtures()
		je = fx.journal_entry(self.user("AU"), ignore_permissions=True)  # depreciation, FX reval, payroll JEs
		je.submit()
		self.assertEqual(fx.state(je), (1, "Đã ghi sổ"))

	# -- T25-T28 ---------------------------------------------------------------------------------

	def test_t25_khong_tu_duyet_don_nghi_cua_minh(self):
		self.require_workflow("Leave Application")
		dh, hm, nv = self.user("DH"), self.user("HM"), self.user("NV")
		own_dh = transitions(
			dh, "Leave Application", "Chờ TBP", owner=dh, employee=employee_of(dh), leave_approver=dh
		)
		self.assertEqual(own_dh, set())
		others = transitions(
			dh, "Leave Application", "Chờ TBP", owner=nv, employee=employee_of(nv), leave_approver=dh
		)
		self.assertEqual(actions(others), {"Duyệt", "Từ chối"})  # control: the same approver on a colleague

		own_hm = transitions(hm, "Leave Application", "Chờ HCNS", owner=nv, employee=employee_of(hm))
		self.assertEqual(own_hm, set())
		self.assertEqual(
			actions(transitions(hm, "Leave Application", "Chờ HCNS", owner=nv, employee=employee_of(nv))),
			{"Duyệt", "Từ chối"},
		)

	def test_t26_sua_noi_dung_khi_dang_cho_duyet(self):
		self.require_workflow("Purchase Order")
		self.require_workflow("Payroll Entry")
		fx = workflow_fixtures()
		po = fx.purchase_order(H1 + 1, self.user("PU"))
		apply_workflow(po.as_dict(), "Gửi duyệt")
		content = frappe.get_doc("Purchase Order", po.name).as_dict()
		content["items"][0]["qty"] = 2
		with self.assertRaisesRegex(frappe.ValidationError, "không được sửa nội dung"):  # creator too (LK)
			frappe.client.save(content)

		au, hm = self.user("AU"), self.user("HM")
		for state in ("Nháp", "Chờ BGĐ"):
			before = make_doc("Payroll Entry", state, hm, start_date="2026-01-01")
			with (
				self.subTest(state),
				as_user(au),
				self.assertRaisesRegex(frappe.ValidationError, "không được sửa nội dung"),
			):
				workflow_guard.before_validate(saving(before, start_date="2026-02-01"))
		draft = make_doc("Payroll Entry", "Nháp", hm, start_date="2026-01-01")
		with as_user(hm):  # control: HM owns the allow_edit of the draft state
			workflow_guard.before_validate(saving(draft, start_date="2026-02-01"))

	def approve(self, doctype, name, user, action="Duyệt"):
		frappe.set_user(user)
		apply_workflow(frappe.get_doc(doctype, name).as_dict(), action)

	def test_t27_dh_roi_hm_duyet_leave_application(self):
		self.require_workflow("Leave Application")
		dh, hm, nv = self.user("DH"), self.user("HM"), self.user("NV")
		employee = place_in_department(nv, dh)
		leave = insert_leave_application(nv, employee, dh)
		self.approve("Leave Application", leave.name, nv, "Gửi duyệt")
		self.approve("Leave Application", leave.name, dh)
		self.approve("Leave Application", leave.name, hm)
		row = frappe.db.get_value(
			"Leave Application", leave.name, ["docstatus", "workflow_state", "status"], as_dict=True
		)
		self.assertEqual((row.docstatus, row.workflow_state, row.status), (1, "Đã duyệt", "Approved"))

	def test_t28_am_duyet_buoc_cuoi_expense_claim(self):
		self.require_workflow("Expense Claim")
		dh, am, vw, nv = self.user("DH"), self.user("AM"), self.user("VW"), self.user("NV")
		employee = place_in_department(nv, dh)

		def submitted(claim_amount, *approvers):
			claim = insert_expense_claim(nv, employee, claim_amount)
			self.approve("Expense Claim", claim.name, nv, "Gửi duyệt")
			self.approve("Expense Claim", claim.name, dh)
			for approver in approvers:
				self.approve("Expense Claim", claim.name, approver)
			return frappe.db.get_value(
				"Expense Claim",
				claim.name,
				["docstatus", "workflow_state", "approval_status"],
				as_dict=True,
			)

		small = submitted(100, am)  # <= H3: KTT is the last step
		self.assertEqual((small.docstatus, small.workflow_state), (1, "Đã duyệt"))
		self.assertEqual(small.approval_status, "Approved")
		large = submitted(H3 + 1, am, vw)  # > H3: BGĐ closes
		self.assertEqual((large.docstatus, large.workflow_state), (1, "Đã duyệt"))
		self.assertEqual(large.approval_status, "Approved")

	# -- T29-T32 ---------------------------------------------------------------------------------

	def test_t29_mh_tp_khong_duyet_po_do_minh_lap(self):
		self.require_workflow("Purchase Order")
		pm, gdvh = self.user("PM"), self.user("GDVH")
		self.assertEqual(
			transitions(pm, "Purchase Order", "Chờ TP", owner=pm, base_grand_total=H1 + 1), set()
		)
		self.assertIn(
			("Duyệt", "Đã duyệt"),
			transitions(gdvh, "Purchase Order", "Chờ TP", owner=pm, base_grand_total=H1 + 1),
		)

	def test_t30_gdvh_duyet_thay_roi_bi_h10(self):
		self.require_workflow("Purchase Order")
		fx = workflow_fixtures()
		gdvh, vw = self.user("GDVH"), self.user("VW")
		po = fx.purchase_order(H2 + 1, self.user("PU"))
		apply_workflow(po.as_dict(), "Gửi duyệt")
		frappe.set_user(gdvh)
		apply_workflow(frappe.get_doc("Purchase Order", po.name).as_dict(), "Duyệt")
		self.assertEqual(fx.state(po), (0, "Chờ BGĐ"))
		with self.assertRaises(frappe.PermissionError):
			apply_workflow(frappe.get_doc("Purchase Order", po.name).as_dict(), "Duyệt")
		frappe.set_user(vw)
		apply_workflow(frappe.get_doc("Purchase Order", po.name).as_dict(), "Duyệt")
		self.assertEqual(fx.state(po), (1, "Đã duyệt"))

	def test_t31_kt_ktt_khong_duyet_pe_do_minh_lap(self):
		self.require_workflow("Payment Entry")
		am, gdvh = self.user("AM"), self.user("GDVH")
		values = {"payment_type": "Pay", "base_paid_amount": H3 + 1}
		self.assertEqual(transitions(am, "Payment Entry", "Chờ KTT", owner=am, **values), set())
		self.assertIn(("Duyệt", "Chờ BGĐ"), transitions(gdvh, "Payment Entry", "Chờ KTT", owner=am, **values))

	def test_t32_su_vuot_han_muc_tin_dung_sm_duoc(self):
		company = _company()
		customer = frappe.get_doc("Customer", ensure_customer())
		customer.append("credit_limits", {"company": company, "credit_limit": 100})
		customer.save(ignore_permissions=True)
		with as_user(self.user("SU")), self.assertRaises(frappe.ValidationError):
			check_credit_limit(customer.name, company, extra_amount=1000)
		with as_user(self.user("SM")):  # Accounts Settings.credit_controller = Sales Manager
			check_credit_limit(customer.name, company, extra_amount=1000)

	# -- T33-T38 ---------------------------------------------------------------------------------

	def test_t33_chi_bao_list_giu_status(self):
		for doctype in ("Sales Order", "Sales Invoice", "Payment Entry"):
			self.require_workflow(doctype)
			with self.subTest(doctype):
				workflow = get_workflow(doctype)
				self.assertEqual(int(workflow.override_status), 1)  # "Don't Override Status"
				self.assertEqual(workflow.workflow_state_field, "workflow_state")
				state_column = frappe.get_meta(doctype).get_field("workflow_state")
				self.assertEqual(int(state_column.in_list_view), 1)

	def test_t34_huy_roi_amend_po(self):
		self.require_workflow("Purchase Order")
		fx = workflow_fixtures()
		pu, pm = self.user("PU"), self.user("PM")
		po = fx.purchase_order(1000, pu)
		frappe.client.submit(po.as_dict())
		self.assertEqual(fx.state(po), (1, "Đã duyệt"))
		frappe.set_user(pm)
		frappe.client.cancel("Purchase Order", po.name)
		self.assertEqual(fx.state(po), (2, "Đã hủy"))
		frappe.set_user(pu)
		amended = frappe.copy_doc(frappe.get_doc("Purchase Order", po.name))
		amended.amended_from = po.name
		amended.docstatus = 0
		amended.insert()
		self.assertEqual(fx.state(amended), (0, "Nháp"))

	def test_t34b_huy_roi_amend_business_trip(self):
		self.skipTest("Cần hrms C5/C6 — xem docs/rbac/BanGiao_C5_C6_hrms.md")

	def test_t35_workflow_state_khop_status_don_nghi(self):
		self.require_workflow("Leave Application")
		rows = frappe.get_all(
			"Leave Application", filters={"docstatus": 1}, fields=["name", "status", "workflow_state"]
		)
		if not rows:
			self.skipTest("cần chạy cutover trên site test: chưa có Leave Application đã submit để đối chiếu")
		status_map = cutover.default_targets()["Leave Application"]["status_map"]
		first = cutover.default_targets()["Leave Application"]["first"]
		for row in rows:
			with self.subTest(row.name):
				self.assertEqual(row.workflow_state, status_map.get(row.status, first))

	def test_t36_workflow_khong_ghi_de_status_expense(self):
		self.require_workflow("Expense Claim")
		dh, am, nv = self.user("DH"), self.user("AM"), self.user("NV")
		self.assertNotIn("status", {s.update_field for s in get_workflow("Expense Claim").states})
		employee = place_in_department(nv, dh)
		claim = insert_expense_claim(nv, employee, 100)
		self.approve("Expense Claim", claim.name, nv, "Gửi duyệt")
		self.approve("Expense Claim", claim.name, dh)
		self.approve("Expense Claim", claim.name, am)
		row = frappe.db.get_value(
			"Expense Claim", claim.name, ["docstatus", "workflow_state", "status"], as_dict=True
		)
		self.assertEqual((row.docstatus, row.workflow_state), (1, "Đã duyệt"))
		self.assertEqual(row.status, "Unpaid")  # computed by hrms, not by the workflow

	def test_t36b_thanh_toan_expense_claim(self):
		self.require_workflow("Expense Claim")
		from hrms.overrides.employee_payment_entry import get_payment_entry_for_employee

		dh, am, nv = self.user("DH"), self.user("AM"), self.user("NV")
		claim = insert_expense_claim(nv, place_in_department(nv, dh), 100)
		self.approve("Expense Claim", claim.name, nv, "Gửi duyệt")
		self.approve("Expense Claim", claim.name, dh)
		self.approve("Expense Claim", claim.name, am)
		frappe.set_user(am)
		payment = get_payment_entry_for_employee("Expense Claim", claim.name)
		payment.insert()
		payment.submit()
		row = frappe.db.get_value("Expense Claim", claim.name, ["workflow_state", "status"], as_dict=True)
		self.assertEqual((row.workflow_state, row.status), ("Đã duyệt", "Paid"))

	def test_t37_so_dung_gia_hd_tu_duyet(self):
		self.require_workflow("Sales Order")
		su = self.user("SU")
		item, customer = workflow_fixtures().item(), ensure_customer()
		bo = blanket_order(item, 100, company=_company(), customer=customer)
		at_contract = self.sales_order(customer, self.row(item, 100, blanket_order=bo))
		off_contract = self.sales_order(customer, self.row(item, 5))
		with as_user(su):
			pricing_guard.validate(at_contract)
			pricing_guard.validate(off_contract)
		self.assertEqual((at_contract.mvl_dung_gia_hd, off_contract.mvl_dung_gia_hd), (1, 0))
		self.assertEqual(
			transitions(su, "Sales Order", "Nháp", owner=su, mvl_dung_gia_hd=1), {("Duyệt", "Đã duyệt")}
		)
		self.assertEqual(
			transitions(su, "Sales Order", "Nháp", owner=su, mvl_dung_gia_hd=0), {("Gửi duyệt", "Chờ KD-TP")}
		)

	def test_t38_pe_thu_tien_ghi_so_thang(self):
		self.require_workflow("Payment Entry")
		au = self.user("AU")
		values = {"payment_type": "Receive", "base_paid_amount": H3 * 10}
		self.assertEqual(
			transitions(au, "Payment Entry", "Nháp", owner=au, **values), {("Ghi sổ", "Đã ghi sổ")}
		)
		draft = make_doc("Payment Entry", "Nháp", au, **values)
		with as_user(au):
			run_guards(saving(draft, docstatus=1))  # H11 lets the self-approval transition through

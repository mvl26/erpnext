# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Nút nào hiện ở trạng thái nào — bảng B2, tính ở server (mục T21).

Đặt logic ở server thay vì trong JS vì hai lý do: giao diện và chốt chặn phía
server không thể lệch nhau, và bảng B2 mới kiểm chứng được bằng test.
"""

import inspect
import re
from pathlib import Path

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.einvoice.builder import create_from_delivery_note
from erpnext.einvoice.constants import (
	STATUS_ADJUSTED,
	STATUS_AWAITING_CUSTOMER,
	STATUS_CANCELLED,
	STATUS_COLOURS,
	STATUS_CUSTOMER_APPROVED,
	STATUS_DRAFT,
	STATUS_DRAFT_VIEWED,
	STATUS_ERROR,
	STATUS_ISSUED,
	STATUS_ISSUING,
	STATUS_NEEDS_RECONCILE,
	STATUS_SENT,
	STATUS_TAX_ACCEPTED,
	STATUS_TAX_REJECTED,
	STATUSES,
	TAX_STATUS_ACCEPTED,
	TAX_STATUS_PENDING,
)
from erpnext.einvoice.form_state import BUTTONS, get_form_state
from erpnext.einvoice.tests.test_fast_client import configure
from erpnext.einvoice.tests.test_fixtures import make_delivery_note

FEI = "Fast EInvoice Document"


class TestButtonMethodsMatchWhatTheFormSends(FrappeTestCase):
	"""Chữ ký của phương thức phải khớp với đối số giao diện gửi lên.

	``call_action`` trong fast_einvoice_document.js gọi **mọi** nút bằng
	``args: {fei: frm.doc.name, ...}``. Frappe lọc kwargs theo chữ ký hàm trước
	khi gọi, nên phương thức nào đặt tên tham số định danh khác ``fei`` thì nút
	đó chết ngay với TypeError — trong khi test gọi trực tiếp bằng tham số vị
	trí vẫn xanh. Đó là lý do lỗi này lọt tới tận giao diện.
	"""

	def test_every_button_method_takes_fei_as_its_first_argument(self):
		for name, _label, method, *_rest in BUTTONS:
			with self.subTest(button=name):
				parameters = list(inspect.signature(frappe.get_attr(method)).parameters)
				self.assertEqual(
					parameters[0],
					"fei",
					f"Nút {name!r} gọi {method} với tham số đầu {parameters[0]!r} — giao diện gửi 'fei'.",
				)


class TestStatusColours(FrappeTestCase):
	"""Bảng màu trong JS phải khớp bảng màu ở server.

	Danh sách buộc phải có bản sao trong JS vì ``get_indicator`` chạy phía client
	cho từng dòng. Test này là chốt duy nhất giữ hai bảng khớp nhau — thiếu nó thì
	thêm một trạng thái mới là danh sách lặng lẽ tô xám.
	"""

	LIST_JS = (
		Path(frappe.get_app_path("erpnext"))
		/ "einvoice"
		/ "doctype"
		/ "fast_einvoice_document"
		/ "fast_einvoice_document_list.js"
	)

	def test_every_status_has_a_colour(self):
		for status in STATUSES:
			with self.subTest(status=status):
				self.assertIn(status, STATUS_COLOURS)

	def test_the_list_view_map_matches_the_server_map(self):
		source = self.LIST_JS.read_text(encoding="utf-8")
		block = re.search(r"const STATUS_COLOURS = \{(.*?)\};", source, re.S)
		self.assertIsNotNone(block, "Không tìm thấy bảng STATUS_COLOURS trong list view JS.")

		in_js = dict(re.findall(r'"([^"]+)":\s*"([^"]+)"', block.group(1)))
		self.assertEqual(in_js, STATUS_COLOURS)


class FormStateBase(FrappeTestCase):
	def setUp(self):
		frappe.db.rollback()
		configure()
		self.dn = make_delivery_note()
		self.fei = create_from_delivery_note(self.dn.name)

	def tearDown(self):
		frappe.db.rollback()

	def buttons_at(self, status, tax_status=""):
		frappe.db.set_value(FEI, self.fei, {"status": status, "tax_status": tax_status})
		return {b["name"] for b in get_form_state(self.fei)["buttons"]}

	def state_at(self, status):
		frappe.db.set_value(FEI, self.fei, "status", status)
		return get_form_state(self.fei)


class TestStatusIndicatorReachesTheForm(FormStateBase):
	def test_state_carries_the_colour_of_the_current_status(self):
		self.assertEqual(self.state_at(STATUS_TAX_ACCEPTED)["status_colour"], "green")
		self.assertEqual(self.state_at(STATUS_ERROR)["status_colour"], "red")
		self.assertEqual(self.state_at(STATUS_DRAFT)["status_colour"], "grey")


class TestTestModeFlag(FormStateBase):
	"""Giao diện chỉ cần biết có đang chạy thử hay không — không cần banner."""

	def test_state_reports_test_mode_when_the_box_is_ticked(self):
		configure(is_test_mode=1)
		self.assertTrue(self.state_at(STATUS_DRAFT)["is_test_mode"])

	def test_state_reports_no_test_mode_when_the_box_is_clear(self):
		"""Hệ thống thật là trạng thái bình thường — không dán nhãn gì."""
		configure(is_test_mode=0)
		self.assertFalse(self.state_at(STATUS_DRAFT)["is_test_mode"])

	def test_there_is_no_environment_banner_left(self):
		"""Nhãn đỏ ở mọi chứng từ thì vài hôm là không ai đọc nữa."""
		self.assertNotIn("banner", self.state_at(STATUS_DRAFT))


class TestButtonsFollowTheStateTable(FormStateBase):
	def test_draft_can_be_resynced_and_previewed(self):
		buttons = self.buttons_at(STATUS_DRAFT)
		self.assertIn("resync", buttons)
		self.assertIn("preview_draft", buttons)

	def test_draft_cannot_send_to_customer_before_a_preview_exists(self):
		self.assertNotIn("send_draft", self.buttons_at(STATUS_DRAFT))

	def test_previewed_draft_can_go_to_the_customer(self):
		self.assertIn("send_draft", self.buttons_at(STATUS_DRAFT_VIEWED))

	def test_awaiting_customer_offers_feedback_and_approval(self):
		buttons = self.buttons_at(STATUS_AWAITING_CUSTOMER)
		self.assertIn("record_feedback", buttons)
		self.assertIn("mark_approved", buttons)

	def test_approved_invoice_offers_the_issue_button(self):
		self.assertIn("issue", self.buttons_at(STATUS_CUSTOMER_APPROVED))

	def test_issuing_state_is_completely_locked(self):
		"""Trạng thái 05 khóa toàn bộ — chống bấm đúp."""
		self.assertEqual(self.buttons_at(STATUS_ISSUING), set())

	def test_issued_invoice_offers_pdf_email_and_tax_check(self):
		buttons = self.buttons_at(STATUS_ISSUED)
		self.assertIn("download_pdf", buttons)
		self.assertIn("download_converted_pdf", buttons)
		self.assertIn("send_invoice", buttons)
		self.assertIn("check_tax", buttons)
		self.assertIn("reconcile", buttons)

	def test_issued_invoice_can_no_longer_be_issued_or_resynced(self):
		buttons = self.buttons_at(STATUS_ISSUED)
		self.assertNotIn("issue", buttons)
		self.assertNotIn("resync", buttons)

	def test_tax_accepted_invoice_unlocks_adjustment_and_replacement(self):
		buttons = self.buttons_at(STATUS_TAX_ACCEPTED, TAX_STATUS_ACCEPTED)
		self.assertIn("create_adjustment", buttons)
		self.assertIn("create_replacement", buttons)

	def test_an_invoice_already_sent_to_the_customer_can_still_be_amended(self):
		"""Gửi khách rồi vẫn phải điều chỉnh/thay thế được.

		``status`` là ô tuyến tính gánh hai sự thật độc lập — CQT xử lý tới đâu và
		đã giao khách chưa. Gửi hóa đơn đẩy 08 → 07, mà chính hóa đơn đã giao
		khách mới là loại pháp luật bắt buộc phải điều chỉnh khi có sai sót. Nên
		điều kiện gác phải đọc ``tax_status``, không đọc ``status``.
		"""
		buttons = self.buttons_at(STATUS_SENT, TAX_STATUS_ACCEPTED)
		self.assertIn("create_adjustment", buttons)
		self.assertIn("create_replacement", buttons)

	def test_adjustment_is_not_offered_before_the_tax_office_accepts(self):
		self.assertNotIn("create_adjustment", self.buttons_at(STATUS_ISSUED))
		self.assertNotIn("create_adjustment", self.buttons_at(STATUS_SENT))
		self.assertNotIn("create_adjustment", self.buttons_at(STATUS_ISSUED, TAX_STATUS_PENDING))

	def test_rejected_invoice_offers_the_cancel_button(self):
		self.assertIn("cancel", self.buttons_at(STATUS_TAX_REJECTED))

	def test_cancel_is_offered_nowhere_else(self):
		for status in (STATUS_ISSUED, STATUS_SENT, STATUS_TAX_ACCEPTED, STATUS_DRAFT):
			self.assertNotIn("cancel", self.buttons_at(status), status)

	def test_needs_reconcile_pushes_the_query_button(self):
		state = self.state_at(STATUS_NEEDS_RECONCILE)
		names = {b["name"] for b in state["buttons"]}
		self.assertIn("reconcile", names)
		self.assertNotIn("issue", names)

	def test_error_state_can_be_fixed_and_retried(self):
		buttons = self.buttons_at(STATUS_ERROR)
		self.assertIn("resync", buttons)
		self.assertIn("reconcile", buttons)

	def test_superseded_invoices_are_read_only(self):
		for status in (STATUS_ADJUSTED, STATUS_CANCELLED):
			buttons = self.buttons_at(status)
			self.assertNotIn("issue", buttons, status)
			self.assertNotIn("resync", buttons, status)


class TestConfirmationLevels(FormStateBase):
	def test_issuing_is_a_level_three_action(self):
		"""Cấp 3 = gõ đúng chữ mới bật được nút."""
		issue = self._button(STATUS_CUSTOMER_APPROVED, "issue")
		self.assertEqual(issue["level"], 3)
		self.assertEqual(issue["confirm_word"], "PHAT HANH")

	def test_cancelling_is_a_level_three_action(self):
		cancel = self._button(STATUS_TAX_REJECTED, "cancel")
		self.assertEqual(cancel["level"], 3)
		self.assertEqual(cancel["confirm_word"], "HUY")

	def test_previewing_is_only_a_simple_confirmation(self):
		self.assertEqual(self._button(STATUS_DRAFT, "preview_draft")["level"], 1)

	def test_sending_a_draft_asks_for_details(self):
		self.assertEqual(self._button(STATUS_DRAFT_VIEWED, "send_draft")["level"], 2)

	def _button(self, status, name):
		frappe.db.set_value(FEI, self.fei, "status", status)
		return next(b for b in get_form_state(self.fei)["buttons"] if b["name"] == name)


class TestApprovalPolicyAffectsButtons(FormStateBase):
	def test_issue_is_hidden_before_approval_when_required(self):
		configure(require_customer_approval=1)
		self.assertNotIn("issue", self.buttons_at(STATUS_DRAFT_VIEWED))

	def test_issue_is_available_from_draft_when_approval_is_optional(self):
		configure(require_customer_approval=0)
		self.assertIn("issue", self.buttons_at(STATUS_DRAFT_VIEWED))


class TestPermissionGate(FormStateBase):
	def test_staff_do_not_see_the_issue_button(self):
		from erpnext.einvoice.setup import ROLE_STAFF
		from erpnext.einvoice.tests.test_einvoice_setup import _as, _ensure_user

		staff = _ensure_user("fei-staff-form@example.com", ROLE_STAFF)
		frappe.db.set_value(FEI, self.fei, "status", STATUS_CUSTOMER_APPROVED)

		with _as(staff):
			names = {b["name"] for b in get_form_state(self.fei)["buttons"]}
		self.assertNotIn("issue", names)

	def test_staff_still_see_the_preparation_buttons(self):
		from erpnext.einvoice.setup import ROLE_STAFF
		from erpnext.einvoice.tests.test_einvoice_setup import _as, _ensure_user

		staff = _ensure_user("fei-staff-form2@example.com", ROLE_STAFF)
		frappe.db.set_value(FEI, self.fei, "status", STATUS_DRAFT)

		with _as(staff):
			names = {b["name"] for b in get_form_state(self.fei)["buttons"]}
		self.assertIn("preview_draft", names)


class TestValidationSummary(FormStateBase):
	def test_a_clean_invoice_reports_no_blocking_issues(self):
		self.assertTrue(self.state_at(STATUS_DRAFT)["validation"]["ok"])

	def test_problems_are_reported_with_their_field(self):
		frappe.db.set_value(FEI, self.fei, "amount_in_words", "")
		validation = self.state_at(STATUS_DRAFT)["validation"]

		self.assertFalse(validation["ok"])
		self.assertTrue(any(i["field"] == "amount_in_words" for i in validation["issues"]))

	def test_locked_invoices_skip_the_validation_pass(self):
		"""Hóa đơn đã phát hành thì không còn gì để sửa — chạy validate chỉ gây nhiễu."""
		self.assertEqual(self.state_at(STATUS_TAX_ACCEPTED)["validation"]["issues"], [])


class TestDeliveryNoteState(FormStateBase):
	"""Nút "Tạo hóa đơn điện tử" trên phiếu giao (mục E1)."""

	def setUp(self):
		frappe.db.rollback()
		configure()

	def test_a_fresh_submitted_note_can_raise_an_invoice(self):
		from erpnext.einvoice.form_state import get_delivery_note_state

		dn = make_delivery_note()
		state = get_delivery_note_state(dn.name)
		self.assertTrue(state["can_create"])
		self.assertEqual(state["grand_total"], dn.grand_total)

	def test_a_draft_note_cannot(self):
		from erpnext.einvoice.form_state import get_delivery_note_state

		dn = make_delivery_note(submit=False)
		state = get_delivery_note_state(dn.name)
		self.assertFalse(state["can_create"])
		self.assertIn("submit", state["reason"])

	def test_a_return_note_cannot(self):
		from erpnext.einvoice.form_state import get_delivery_note_state

		dn = make_delivery_note(is_return=True)
		self.assertFalse(get_delivery_note_state(dn.name)["can_create"])

	def test_a_note_that_already_has_a_live_invoice_cannot(self):
		from erpnext.einvoice.form_state import get_delivery_note_state

		dn = make_delivery_note()
		fei = create_from_delivery_note(dn.name)

		state = get_delivery_note_state(dn.name)
		self.assertFalse(state["can_create"])
		self.assertEqual(state["existing"]["name"], fei)

	def test_a_cancelled_invoice_frees_the_note_again(self):
		from erpnext.einvoice.form_state import get_delivery_note_state

		dn = make_delivery_note()
		fei = create_from_delivery_note(dn.name)
		frappe.db.set_value(FEI, fei, "status", STATUS_CANCELLED)

		self.assertTrue(get_delivery_note_state(dn.name)["can_create"])

	def test_a_disabled_integration_hides_the_button(self):
		from erpnext.einvoice.form_state import get_delivery_note_state

		dn = make_delivery_note()
		configure(enabled=0)
		self.assertFalse(get_delivery_note_state(dn.name)["can_create"])

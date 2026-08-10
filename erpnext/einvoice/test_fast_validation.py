# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""16 quy tắc kiểm tra dữ liệu trước khi gửi — Phần F của đặc tả.

Mỗi quy tắc chặn được ở ERP là một lời gọi hỏng tiết kiệm được với Fast, và với
lệnh phát hành thì còn là một số hóa đơn không bị tiêu oan.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.einvoice.constants import STATUS_ISSUED
from erpnext.einvoice.test_fast_document import make_fei
from erpnext.einvoice.validation import validate_before_send


def check(fei, **kwargs):
	kwargs.setdefault("check_source", False)
	return validate_before_send(fei, **kwargs)


def rules_hit(result, level=None):
	return {i.rule for i in result.issues if level is None or i.level == level}


class TestValidationRules(FrappeTestCase):
	def setUp(self):
		frappe.db.rollback()

	def tearDown(self):
		frappe.db.rollback()

	def test_a_clean_invoice_passes(self):
		result = check(make_fei())
		self.assertTrue(result.ok, f"Hóa đơn sạch mà vẫn bị chặn: {[i.message for i in result.issues]}")

	# --- Quy tắc 1: Key ---------------------------------------------------

	def test_key_longer_than_32_chars_is_blocked(self):
		self.assertIn(1, rules_hit(check(make_fei(fast_key="X" * 33)), "block"))

	def test_key_with_vietnamese_diacritics_is_blocked(self):
		self.assertIn(1, rules_hit(check(make_fei(fast_key="ĐƠNHÀNG01")), "block"))

	def test_key_already_used_by_an_issued_invoice_is_blocked(self):
		"""Quy tắc 1 — đây chính là lá chắn cho lỗi 809/835."""
		issued = make_fei()
		issued.insert()
		frappe.db.set_value("Fast EInvoice Document", issued.name, "status", STATUS_ISSUED)

		duplicate = make_fei()
		self.assertIn(1, rules_hit(check(duplicate), "block"))

	# --- Quy tắc 2 & 3: người mua ----------------------------------------

	def test_tax_code_without_name_or_address_is_blocked(self):
		self.assertIn(2, rules_hit(check(make_fei(customer_name="", address="")), "block"))

	def test_company_buyer_needs_a_ten_or_thirteen_digit_tax_code(self):
		self.assertIn(3, rules_hit(check(make_fei(customer_type="1", customer_tax_code="123")), "block"))

	def test_thirteen_digit_tax_code_is_accepted(self):
		self.assertNotIn(
			3, rules_hit(check(make_fei(customer_type="1", customer_tax_code="0101234567891")), "block")
		)

	def test_branch_tax_code_with_separators_is_accepted(self):
		"""MST chi nhánh 13 số kèm dấu gạch / khoảng trắng / chấm — đều hợp lệ."""
		for code in ("0101234567-001", "0101234567 001", "0101234567.001"):
			self.assertNotIn(
				3,
				rules_hit(check(make_fei(customer_type="1", customer_tax_code=code)), "block"),
				code,
			)

	def test_eleven_or_twelve_digit_codes_are_still_rejected(self):
		"""Không nới lỏng quá tay: 11—12 số vẫn sai (chi nhánh phải đúng 3 số)."""
		for code in ("01012345672", "0101234567-01"):
			self.assertIn(
				3,
				rules_hit(check(make_fei(customer_type="1", customer_tax_code=code)), "block"),
				code,
			)

	def test_a_real_tax_code_raises_no_check_digit_warning(self):
		"""MST thật (số kiểm tra đúng) không bị cảnh báo."""
		for code in ("0101248141", "0300588569", "0100109106"):
			result = check(make_fei(customer_type="1", customer_tax_code=code))
			self.assertNotIn(3, rules_hit(result, "warn"), code)

	def test_wrong_check_digit_warns_but_does_not_block(self):
		"""MST sai số kiểm tra: cảnh báo (Fast nhiều khả năng trả 78013), không chặn."""
		result = check(make_fei(customer_type="1", customer_tax_code="0101234567"))
		self.assertIn(3, rules_hit(result, "warn"))
		self.assertNotIn(3, rules_hit(result, "block"))

	def test_check_digit_covers_the_parent_of_a_branch_code(self):
		"""MST chi nhánh 13 số: số kiểm tra tính trên 10 số MST mẹ."""
		self.assertIn(
			3, rules_hit(check(make_fei(customer_type="1", customer_tax_code="0101234567001")), "warn")
		)
		self.assertNotIn(
			3, rules_hit(check(make_fei(customer_type="1", customer_tax_code="0101248141001")), "warn")
		)

	def test_individual_buyer_needs_no_tax_code(self):
		fei = make_fei(customer_type="0", customer_tax_code="")
		self.assertNotIn(3, rules_hit(check(fei), "block"))

	# --- Quy tắc 4: CCCD --------------------------------------------------

	def test_id_card_must_be_nine_or_twelve_digits(self):
		self.assertIn(4, rules_hit(check(make_fei(id_card_no="12345")), "block"))

	def test_twelve_digit_id_card_is_accepted(self):
		self.assertNotIn(4, rules_hit(check(make_fei(id_card_no="012345678901")), "block"))

	# --- Quy tắc 5: đọc tiền bằng chữ ------------------------------------

	def test_words_missing_the_currency_keyword_are_blocked(self):
		"""Lá chắn cho lỗi 152."""
		fei = make_fei(currency="VND", amount_in_words="Mười một triệu")
		self.assertIn(5, rules_hit(check(fei), "block"))

	def test_usd_invoice_needs_the_usd_keyword(self):
		fei = make_fei(currency="USD", amount_in_words="Một nghìn đồng")
		self.assertIn(5, rules_hit(check(fei), "block"))

	# --- Quy tắc 6 & 7: độ dài và xuống dòng ------------------------------

	def test_newline_in_any_text_field_is_blocked(self):
		self.assertIn(6, rules_hit(check(make_fei(customer_name="Bệnh viện\nĐa khoa")), "block"))

	def test_newline_in_a_line_item_name_is_blocked(self):
		fei = make_fei()
		fei.lines[0].item_name = "Bơm kim\ntiêm"
		self.assertIn(6, rules_hit(check(fei), "block"))

	def test_buyer_longer_than_100_chars_is_blocked(self):
		self.assertIn(7, rules_hit(check(make_fei(buyer="N" * 101)), "block"))

	def test_item_name_longer_than_500_chars_is_blocked(self):
		fei = make_fei()
		fei.lines[0].item_name = "B" * 501
		self.assertIn(7, rules_hit(check(fei), "block"))

	def test_human_name_longer_than_128_chars_is_blocked(self):
		self.assertIn(7, rules_hit(check(make_fei(human_name="H" * 129)), "block"))

	# --- Quy tắc 8 & 12: dòng hàng ---------------------------------------

	def test_line_without_process_type_is_blocked(self):
		fei = make_fei()
		fei.lines[0].process_type = ""
		self.assertIn(8, rules_hit(check(fei), "block"))

	def test_line_with_an_unknown_tax_rate_is_blocked(self):
		fei = make_fei()
		fei.lines[0].tax_rate = "7"
		self.assertIn(12, rules_hit(check(fei), "block"))

	# --- Quy tắc 9: số liệu phải khớp ------------------------------------

	def test_line_total_must_match_the_master_amount(self):
		self.assertIn(9, rules_hit(check(make_fei(amount=9_000_000)), "block"))

	def test_rounding_difference_of_one_dong_is_tolerated(self):
		self.assertNotIn(9, rules_hit(check(make_fei(amount=9_999_999, total_amount=10_999_999)), "block"))

	def test_line_tax_must_match_the_master_tax(self):
		self.assertIn(9, rules_hit(check(make_fei(tax_amount=999)), "block"))

	def test_total_must_equal_amount_plus_tax_less_deductions(self):
		self.assertIn(9, rules_hit(check(make_fei(total_amount=12_000_000)), "block"))

	def test_deductions_are_taken_off_the_total(self):
		fei = make_fei(deduction_amount=1_000_000, total_amount=10_000_000)
		self.assertNotIn(9, rules_hit(check(fei), "block"))

	# --- Quy tắc 10: số dòng ---------------------------------------------

	def test_more_than_300_lines_is_blocked(self):
		fei = make_fei()
		template = fei.lines[0].as_dict()
		fei.set("lines", [])
		for _ in range(301):
			fei.append("lines", dict(template, name=None))
		self.assertIn(10, rules_hit(check(fei), "block"))

	# --- Quy tắc 11: ngày hóa đơn ----------------------------------------

	def test_invoice_date_before_the_last_issued_one_is_blocked(self):
		"""Lá chắn cho lỗi 819."""
		issued = make_fei(fast_key="TRUOCDO")
		issued.insert()
		frappe.db.set_value(
			"Fast EInvoice Document",
			issued.name,
			{"status": STATUS_ISSUED, "invoice_date": "2026-08-07"},
		)

		backdated = make_fei(fast_key="SAUDO", invoice_date="2026-08-01")
		self.assertIn(11, rules_hit(check(backdated), "block"))

	# --- Quy tắc 13 & 14: cảnh báo ---------------------------------------

	def test_xml_special_characters_only_warn(self):
		"""Ký tự & < > escape được, nên cảnh báo chứ không chặn."""
		result = check(make_fei(customer_name="Bệnh viện A & B"))
		self.assertIn(13, rules_hit(result, "warn"))
		self.assertTrue(result.ok)

	def test_malformed_email_only_warns(self):
		result = check(make_fei(email_deliver="khong-phai-email"))
		self.assertIn(14, rules_hit(result, "warn"))
		self.assertTrue(result.ok)

	def test_multiple_emails_separated_by_commas_are_accepted(self):
		fei = make_fei(email_deliver="a@x.vn,b@y.vn")
		self.assertNotIn(14, rules_hit(check(fei), "warn"))

	# --- Quy tắc 16 + khoảng trống 8% ------------------------------------

	def test_tax_group_buckets_must_add_up_to_the_master_tax(self):
		fei = make_fei(tax_amount_10=0)
		self.assertIn(16, rules_hit(check(fei), "block"))

	def test_eight_percent_lines_warn_about_the_missing_bucket(self):
		"""Bốn thẻ nhóm của Phần I không có ô cho 8% — kế toán phải biết."""
		fei = make_fei(tax_rate="8", tax_amount=800_000, total_amount=10_800_000, tax_amount_10=0)
		fei.lines[0].tax_rate = "8"
		fei.lines[0].tax_amount = 800_000
		self.assertIn(17, rules_hit(check(fei), "warn"))


class TestSourceDeliveryNoteRule(FrappeTestCase):
	"""Quy tắc 15 — kiểm tra chứng từ nguồn."""

	def setUp(self):
		frappe.db.rollback()

	def tearDown(self):
		frappe.db.rollback()

	def test_submitted_delivery_note_passes(self):
		from erpnext.einvoice.test_fixtures import make_delivery_note

		dn = make_delivery_note()
		fei = make_fei(delivery_note=dn.name)
		self.assertNotIn(15, rules_hit(validate_before_send(fei), "block"))

	def test_draft_delivery_note_is_blocked(self):
		from erpnext.einvoice.test_fixtures import make_delivery_note

		dn = make_delivery_note(submit=False)
		fei = make_fei(delivery_note=dn.name)
		self.assertIn(15, rules_hit(validate_before_send(fei), "block"))

	def test_return_delivery_note_is_blocked(self):
		from erpnext.einvoice.test_fixtures import make_delivery_note

		dn = make_delivery_note(is_return=True)
		fei = make_fei(delivery_note=dn.name)
		self.assertIn(15, rules_hit(validate_before_send(fei), "block"))

	def test_delivery_note_already_carrying_a_live_invoice_is_blocked(self):
		from erpnext.einvoice.test_fixtures import make_delivery_note

		dn = make_delivery_note()
		existing = make_fei(delivery_note=dn.name)
		existing.insert()

		second = make_fei(delivery_note=dn.name, fast_key="KHACNUA")
		self.assertIn(15, rules_hit(validate_before_send(second), "block"))

	def test_missing_delivery_note_is_blocked(self):
		fei = make_fei(delivery_note="KHONG-CO-THAT")
		self.assertIn(15, rules_hit(validate_before_send(fei), "block"))

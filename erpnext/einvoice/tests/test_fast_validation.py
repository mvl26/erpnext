# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Các quy tắc kiểm tra dữ liệu trước khi gửi — Phần F của đặc tả.

Mỗi quy tắc chặn được ở ERP là một lời gọi hỏng tiết kiệm được với Fast, và với
lệnh phát hành thì còn là một số hóa đơn không bị tiêu oan.
"""

import re
from typing import ClassVar

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, add_months, getdate, nowdate

from erpnext.einvoice.builder import create_from_sales_invoice
from erpnext.einvoice.constants import (
	PROCESS_TYPE_DISCOUNT,
	PROCESS_TYPE_GOODS,
	PROCESS_TYPE_NOTE,
	PROCESS_TYPE_SPECIAL,
	SOURCE_DELIVERY_NOTE_V2,
	STATUS_ISSUED,
)
from erpnext.einvoice.tests.test_fast_client import configure
from erpnext.einvoice.tests.test_fast_document import make_fei
from erpnext.einvoice.tests.test_fixtures import (
	make_delivery_note,
	make_legacy_fei,
	make_sales_invoice,
	make_sales_invoice_from_delivery_note,
)
from erpnext.einvoice.validation import validate_before_send

FEI = "Fast EInvoice Document"


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

	# --- Quy tắc 8: dòng hàng ---------------------------------------------

	def test_a_goods_line_without_an_item_code_is_blocked(self):
		fei = make_fei()
		fei.lines[0].process_type = PROCESS_TYPE_GOODS
		fei.lines[0].item_code = ""
		self.assertIn(8, rules_hit(check(fei), "block"))

	def test_a_special_goods_line_without_an_item_code_is_blocked(self):
		fei = make_fei()
		fei.lines[0].process_type = PROCESS_TYPE_SPECIAL
		fei.lines[0].item_code = ""
		self.assertIn(8, rules_hit(check(fei), "block"))

	def test_a_note_line_needs_no_item_code(self):
		"""Dòng ghi chú không trỏ tới hàng nào — nội dung nằm ở tên hàng."""
		fei = make_fei()
		fei.lines[0].process_type = PROCESS_TYPE_NOTE
		fei.lines[0].item_code = ""
		fei.lines[0].tax_rate = "-9"
		self.assertNotIn(8, rules_hit(check(fei), "block"))

	def test_a_discount_line_needs_no_item_code(self):
		fei = make_fei()
		fei.lines[0].process_type = PROCESS_TYPE_DISCOUNT
		fei.lines[0].item_code = ""
		self.assertNotIn(8, rules_hit(check(fei), "block"))

	# --- Quy tắc 1: Key ---------------------------------------------------

	def test_key_longer_than_32_chars_is_blocked(self):
		self.assertIn(1, rules_hit(check(make_fei(fast_key="X" * 33)), "block"))

	def test_key_with_vietnamese_diacritics_only_warns(self):
		"""Tài liệu Fast không cấm dấu ở thẻ Key — không có mã lỗi thì không chặn.

		`fast_key_for()` vốn đã bỏ dấu khi sinh Key, nên đây chỉ là lưới cho Key
		gõ tay. Key còn dùng làm khóa tra cứu nên vẫn đáng nhắc.
		"""
		result = check(make_fei(fast_key="ĐƠNHÀNG01"))

		self.assertIn(1, rules_hit(result, "warn"))
		self.assertNotIn(1, rules_hit(result, "block"))

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

	# --- Quy tắc 7: độ dài ----------------------------------------------

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

	# --- Ngày hóa đơn, xuống dòng, ký tự & — không còn là việc của kiểm tra ---

	def test_an_old_invoice_date_raises_nothing(self):
		"""Ngày hóa đơn do hệ thống đặt về hôm nay lúc lưu / xem nháp / phát hành.

		Ngày cũ không phải việc để kế toán quyết, nên không chặn cũng không cảnh báo.
		"""
		issued = make_fei(fast_key="TRUOCDO")
		issued.insert()
		frappe.db.set_value("Fast EInvoice Document", issued.name, "status", STATUS_ISSUED)

		result = check(make_fei(fast_key="SAUDO", invoice_date="2026-08-01"))
		self.assertEqual(result.issues, [])

	def test_ampersand_in_names_raises_nothing(self):
		"""Dữ liệu gửi Fast là JSON mã hóa base64 — & < > không có gì phải lo."""
		fei = make_fei(customer_name="Công ty A & B", buyer="Nguyễn <Văn> A")
		fei.lines[0].item_name = "Bơm & kim tiêm"
		self.assertEqual(check(fei).issues, [])

	def test_malformed_email_only_warns(self):
		result = check(make_fei(email_deliver="khong-phai-email"))
		self.assertIn(14, rules_hit(result, "warn"))
		self.assertTrue(result.ok)

	def test_multiple_emails_separated_by_commas_are_accepted(self):
		fei = make_fei(email_deliver="a@x.vn,b@y.vn")
		self.assertNotIn(14, rules_hit(check(fei), "warn"))

	# --- Quy tắc 16 + khoảng trống 8% ------------------------------------

	def test_tax_group_buckets_that_do_not_match_only_warn(self):
		"""Bốn ô nhóm lệch thì nói ra, nhưng không khóa việc phát hành.

		Fast không dùng bốn ô này để dựng tờ khai — đã đối chứng trên môi trường
		thử: hóa đơn có bốn ô cộng thiếu 100.000 vẫn được Fast nhận và Cơ quan
		Thuế chấp nhận. Chặn ở đây là ERP từ chối gửi thứ Fast sẵn sàng nhận.
		"""
		result = check(make_fei(tax_amount_10=0))

		self.assertIn(16, rules_hit(result, "warn"))
		self.assertNotIn(16, rules_hit(result, "block"))
		self.assertTrue(result.ok)

	def test_the_grand_total_still_blocks_because_it_is_printed(self):
		"""Trái với quy tắc 16: Tổng thanh toán sai thì hóa đơn tự mâu thuẫn."""
		self.assertIn(9, rules_hit(check(make_fei(total_amount=123)), "block"))

	def test_an_eight_percent_invoice_raises_nothing_at_all(self):
		"""Hóa đơn 8% là hóa đơn bình thường — không lỗi, không cả cảnh báo.

		Bốn ô nhóm của Fast không có ô cho 8% nên chúng cộng thiếu đúng phần đó,
		nhưng Fast không dùng bốn ô ấy để kê khai (đã đối chứng trên môi trường
		thử). Từng có một cảnh báo nói chuyện này; đã bỏ vì nó nổ ở gần như mọi
		hóa đơn mà lại kết thúc bằng "không cần xử lý gì", tức là chỉ dạy người
		dùng bỏ qua bảng cảnh báo.
		"""
		fei = make_fei(tax_rate="8", tax_amount=800_000, total_amount=10_800_000, tax_amount_10=0)
		fei.lines[0].tax_rate = "8"
		fei.lines[0].tax_amount = 800_000

		result = check(fei)

		self.assertTrue(result.ok)
		self.assertEqual(result.blocking, [])
		self.assertEqual(result.warnings, [])


class TestSourceRule(FrappeTestCase):
	"""Quy tắc 15 — kiểm tra chứng từ nguồn (hóa đơn bán; bản ghi bản 2.0 giữ luật phiếu giao)."""

	def setUp(self):
		frappe.db.rollback()
		configure()

	def tearDown(self):
		frappe.db.rollback()

	def _legacy(self, **values):
		return make_fei(source_doctype=SOURCE_DELIVERY_NOTE_V2, sales_invoice=None, **values)

	def test_submitted_sales_invoice_passes(self):
		si = make_sales_invoice()
		fei = make_fei(sales_invoice=si.name)
		self.assertNotIn(15, rules_hit(validate_before_send(fei), "block"))

	def test_draft_sales_invoice_is_blocked(self):
		si = make_sales_invoice(submit=False)
		fei = make_fei(sales_invoice=si.name)
		self.assertIn(15, rules_hit(validate_before_send(fei), "block"))

	def test_opening_sales_invoice_is_blocked(self):
		si = make_sales_invoice()
		frappe.db.set_value("Sales Invoice", si.name, "is_opening", "Yes")
		fei = make_fei(sales_invoice=si.name)
		self.assertIn(15, rules_hit(validate_before_send(fei), "block"))

	def test_sales_invoice_already_carrying_a_live_invoice_is_blocked(self):
		si = make_sales_invoice()
		create_from_sales_invoice(si.name)

		second = make_fei(sales_invoice=si.name, fast_key="KHACNUA")
		self.assertIn(15, rules_hit(validate_before_send(second), "block"))

	def test_missing_sales_invoice_is_blocked(self):
		fei = make_fei(sales_invoice="KHONG-CO-THAT")
		self.assertIn(15, rules_hit(validate_before_send(fei), "block"))

	def test_a_delivery_note_invoiced_under_v2_is_blocked(self):
		dn = make_delivery_note()
		make_legacy_fei(dn.name)
		si = make_sales_invoice_from_delivery_note(dn.name)

		fei = make_fei(sales_invoice=si.name)
		self.assertIn(15, rules_hit(validate_before_send(fei), "block"))

	def test_a_v2_record_keeps_the_delivery_note_rules(self):
		dn = make_delivery_note(submit=False)
		self.assertIn(15, rules_hit(validate_before_send(self._legacy(delivery_note=dn.name)), "block"))

		dn = make_delivery_note()
		self.assertNotIn(15, rules_hit(validate_before_send(self._legacy(delivery_note=dn.name)), "block"))


class TestMatchTheSalesInvoice(FrappeTestCase):
	"""Quy tắc 18 (tổng tiền) và 19 (kỳ kê khai) — cảnh báo, không bao giờ chặn."""

	def setUp(self):
		frappe.db.rollback()
		configure()
		self.si = make_sales_invoice()
		self.fei = frappe.get_doc(FEI, create_from_sales_invoice(self.si.name))

	def tearDown(self):
		frappe.db.rollback()

	def test_a_fresh_invoice_matches_its_sales_invoice(self):
		issues = validate_before_send(self.fei).issues
		self.assertNotIn(18, [i.rule for i in issues])
		self.assertNotIn(19, [i.rule for i in issues])

	def test_an_edited_line_is_a_warning_not_a_block(self):
		self.fei.lines[0].qty = 50
		self.fei.flags.ignore_links = True
		self.fei.save(ignore_permissions=True)

		result = validate_before_send(self.fei)
		self.assertIn(18, rules_hit(result, "warn"))
		self.assertNotIn(18, rules_hit(result, "block"))

	def test_rounding_pennies_are_not_reported(self):
		frappe.db.set_value("Sales Invoice", self.si.name, "grand_total", self.si.grand_total + 0.6)
		self.assertNotIn(18, rules_hit(validate_before_send(self.fei), "warn"))

	def test_a_few_days_inside_the_same_period_is_not_reported(self):
		"""Ngày hóa đơn luôn là ngày phát hành — lệch vài ngày trong cùng kỳ là chuyện thường."""
		frappe.db.set_value("Sales Invoice", self.si.name, "posting_date", _same_period_earlier())
		self.assertNotIn(19, rules_hit(validate_before_send(self.fei), "warn"))

	def test_a_different_declaration_period_is_a_warning(self):
		frappe.db.set_value("Sales Invoice", self.si.name, "posting_date", add_months(nowdate(), -3))
		result = validate_before_send(self.fei)
		self.assertIn(19, rules_hit(result, "warn"))
		self.assertNotIn(19, rules_hit(result, "block"))


def _same_period_earlier():
	"""Một ngày trước hôm nay mà vẫn cùng quý — hoặc chính hôm nay nếu đang là ngày đầu quý."""
	today = getdate(nowdate())
	first_of_quarter = today.replace(month=(today.month - 1) // 3 * 3 + 1, day=1)
	return max(first_of_quarter, getdate(add_days(today, -2)))


class TestNothingBlocksMoreThanFastDoes(FrappeTestCase):
	"""Fast mới là bên quyết. ERP chặn thứ Fast sẵn sàng nhận là chặn sai.

	Chặn thừa không phải lỗi vô hại: nó dừng một hóa đơn hoàn toàn hợp lệ, và kế
	toán thì không có đường nào đi tiếp ngoài việc gọi người viết phần mềm. Cả
	một buổi làm việc đã mất vì đúng chuyện này.

	Nên mỗi điểm chặn phải trả lời được câu "Fast từ chối cái này ở đâu?" — hoặc
	bằng một mã lỗi có thật trong tài liệu của họ, hoặc bằng việc nằm trong danh
	sách luật nghiệp vụ Miyano ghi ngay dưới đây. Thêm một điểm chặn mới mà không
	làm một trong hai việc đó thì test này hỏng.
	"""

	# Quy tắc chặn vì **luật nghiệp vụ của Miyano**, không phải vì Fast từ chối.
	# Mỗi mục phải nói được vì sao nó đáng chặn dù Fast vẫn nhận.
	ERP_BUSINESS_RULES: ClassVar[dict[int, str]] = {
		15: "Chứng từ nguồn: hóa đơn bán phải có thật, đã submit, không phải trả hàng / ghi nợ / "
		"số dư đầu kỳ / gộp POS, chưa có hóa đơn khác, và không phiếu giao nào trong nó đã có "
		"hóa đơn bản 2.0. Fast không biết hóa đơn bán của ERP là gì nên không có mã lỗi nào "
		"tương ứng — đây là luật kế toán của Miyano, không phải luật của Fast.",
	}

	def _blocking_points(self):
		"""Mọi lời gọi result.add(..., BLOCK, ...) trong module, kèm nội dung."""
		import inspect

		from erpnext.einvoice import validation

		source = inspect.getsource(validation)
		calls = list(re.finditer(r"result\.add\(\s*(\d+),\s*(BLOCK|WARN|level)\b", source))
		found = []
		for n, match in enumerate(calls):
			if match.group(2) == "WARN":
				continue
			# Cửa sổ đọc phải dừng ở lời gọi kế tiếp **và** ở đầu hàm kế tiếp.
			# Quét rộng hơn thì docstring hay thông báo của quy tắc sau lọt vào,
			# và một quy tắc không nêu căn cứ sẽ mượn được mã lỗi của hàng xóm —
			# tức là test này tự mù.
			stop = calls[n + 1].start() if n + 1 < len(calls) else len(source)
			nxt_def = source.find("\ndef ", match.end())
			if 0 < nxt_def < stop:
				stop = nxt_def
			found.append((int(match.group(1)), source[match.end() : stop]))
		return found

	def test_every_blocking_rule_names_a_real_fast_error_or_a_business_reason(self):
		for rule, text in self._blocking_points():
			with self.subTest(rule=rule):
				cites_fast = bool(re.search(r"lỗi \d{3,5}", text))
				self.assertTrue(
					cites_fast or rule in self.ERP_BUSINESS_RULES,
					f"Quy tắc {rule} chặn mà không nói Fast từ chối ở đâu. Hoặc dẫn mã lỗi Fast "
					f"vào thông báo, hoặc hạ xuống WARN, hoặc ghi lý do nghiệp vụ vào "
					f"ERP_BUSINESS_RULES.",
				)

	def test_the_business_rule_list_stays_honest(self):
		"""Danh sách miễn trừ chỉ được chứa quy tắc thật sự còn chặn."""
		blocking_rules = {rule for rule, _text in self._blocking_points()}
		for rule in self.ERP_BUSINESS_RULES:
			with self.subTest(rule=rule):
				self.assertIn(
					rule,
					blocking_rules,
					f"Quy tắc {rule} không còn chặn nữa — bỏ nó khỏi ERP_BUSINESS_RULES.",
				)

	def test_a_plain_eight_percent_invoice_sails_through(self):
		"""Không quy tắc nào được đụng tới một hóa đơn 8% bình thường."""
		fei = make_fei(tax_rate="8", tax_amount=800_000, total_amount=10_800_000, tax_amount_10=0)
		fei.lines[0].tax_rate = "8"
		fei.lines[0].tax_amount = 800_000

		result = check(fei)

		self.assertEqual(result.blocking, [])
		self.assertEqual(result.warnings, [])

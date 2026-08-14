# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""DocType `Fast EInvoice Document` — mục C2 và bảng trạng thái B2."""

import json

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.einvoice.constants import (
	INVOICE_TYPE_ADJUSTMENT,
	INVOICE_TYPE_ORIGINAL,
	INVOICE_TYPES,
	STATUS_CUSTOMER_APPROVED,
	STATUS_DRAFT,
	STATUS_ERROR,
	STATUS_ISSUED,
	STATUS_ISSUING,
	STATUS_TAX_ACCEPTED,
	STATUSES,
	TAX_RATE_CODES,
)

FEI = "Fast EInvoice Document"

# Thứ tự cột `structure.master` — Phần I của đặc tả.
MASTER_FIELDS = (
	"fast_key",
	"invoice_date",
	"customer_code",
	"buyer",
	"customer_name",
	"customer_tax_code",
	"customer_type",
	"address",
	"phone_number",
	"fax_number",
	"email_deliver",
	"bank_account",
	"bank_name",
	"payment_method",
	"currency",
	"exchange_rate",
	"amount",
	"total_amount",
	"tax_rate",
	"tax_amount",
	"tax_amount_free",
	"tax_amount_0",
	"tax_amount_5",
	"tax_amount_10",
	"discount_amount",
	"promotion_amount",
	"amount_in_words",
	"human_name",
)


def _as_browser_sends(doc):
	"""Chứng từ đúng như giao diện gửi lên: đi qua JSON nên Date thành chuỗi."""
	return json.loads(frappe.as_json(doc.as_dict()))


def make_fei(**values):
	"""Bản ghi FEI tối thiểu. Bỏ qua kiểm tra link để test không cần dựng cả DN."""
	doc = frappe.new_doc(FEI)
	doc.update(
		{
			"delivery_note": "MAT-DN-TEST-0001",
			"customer": "_Test Customer FEI",
			"status": STATUS_DRAFT,
			"invoice_type": INVOICE_TYPE_ORIGINAL,
			"fast_key": "MATDNTEST0001",
			# Ngày hôm nay: hóa đơn test không được "cũ hơn" một hóa đơn thật phát
			# hành cùng ngày (quy tắc 11 truy vấn toàn bộ chứng từ đã phát hành).
			"invoice_date": frappe.utils.nowdate(),
			"customer_code": "KH0001",
			"customer_name": "Bệnh viện Đa khoa X",
			"customer_type": "1",
			"customer_tax_code": "0101234565",
			"address": "Số 1 Phố Y, Hà Nội",
			"email_deliver": "kt@bvx.vn",
			"payment_method": "CK",
			"currency": "VND",
			"exchange_rate": 1.0,
			"amount": 10000000,
			"tax_rate": "10",
			"tax_amount": 1000000,
			"tax_amount_10": 1000000,
			"total_amount": 11000000,
			"amount_in_words": "Mười một triệu đồng chẵn",
			"human_name": "Chu Văn Hiếu",
		}
	)
	doc.update(values)
	doc.append(
		"lines",
		{
			"process_type": "1",
			"item_code": "VT001",
			"item_name": "Bơm kim tiêm 5ml",
			"uom": "Cái",
			"qty": 100,
			"price": 100000,
			"amount": 10000000,
			"tax_rate": "10",
			"tax_amount": 1000000,
		},
	)
	doc.flags.ignore_links = True
	doc.flags.ignore_permissions = True
	return doc


class TestFastEInvoiceDocument(FrappeTestCase):
	def setUp(self):
		frappe.db.rollback()

	def tearDown(self):
		frappe.db.rollback()

	# --- Hình dạng schema ------------------------------------------------

	def test_document_is_not_submittable(self):
		"""Vòng đời 14 trạng thái không khớp Draft/Submitted/Cancelled của Frappe."""
		self.assertFalse(frappe.get_meta(FEI).is_submittable)

	def test_naming_follows_the_spec_series(self):
		self.assertEqual(frappe.get_meta(FEI).autoname, "FEI-.YYYY.-.#####")

	def test_status_offers_every_lifecycle_state_in_order(self):
		options = frappe.get_meta(FEI).get_field("status").options.split("\n")
		self.assertEqual(options, list(STATUSES))

	def test_master_columns_appear_in_the_order_fast_expects(self):
		meta = frappe.get_meta(FEI)
		ordered = [f.fieldname for f in meta.fields if f.fieldname in MASTER_FIELDS]
		self.assertEqual(ordered, list(MASTER_FIELDS))

	def test_lines_point_at_the_line_child_table(self):
		field = frappe.get_meta(FEI).get_field("lines")
		self.assertEqual(field.fieldtype, "Table")
		self.assertEqual(field.options, "Fast EInvoice Line")

	def test_invoice_type_offers_the_three_spec_types(self):
		options = frappe.get_meta(FEI).get_field("invoice_type").options.split("\n")
		self.assertEqual(options, list(INVOICE_TYPES))

	def test_master_tax_rate_uses_the_same_code_set_as_lines(self):
		options = frappe.get_meta(FEI).get_field("tax_rate").options.split("\n")
		self.assertEqual(options, list(TAX_RATE_CODES))

	def test_result_fields_from_fast_are_read_only(self):
		"""Nhóm C2.4 do Fast trả về — người dùng không được gõ tay."""
		meta = frappe.get_meta(FEI)
		for fieldname in (
			"fast_key_search",
			"fast_invoice_no",
			"fast_pattern",
			"fast_serial",
			"fast_signed_date",
			"tax_status",
			"tax_verification_code",
			"error_code",
		):
			self.assertEqual(meta.get_field(fieldname).read_only, 1, fieldname)

	def test_release_type_defaults_to_detailed_columns(self):
		self.assertEqual(frappe.get_meta(FEI).get_field("release_type").default, "1")

	# --- Khóa sửa theo trạng thái (bảng B2) ------------------------------

	def test_draft_record_is_editable(self):
		doc = make_fei()
		doc.insert()
		self.assertEqual(doc.is_edit_locked, 0)
		doc.buyer = "Nguyễn Văn A"
		doc.save()
		self.assertEqual(doc.buyer, "Nguyễn Văn A")

	def test_issued_record_is_flagged_locked(self):
		doc = make_fei()
		doc.insert()
		doc.status = STATUS_ISSUED
		doc.flags.ignore_status_lock = True
		doc.save()
		self.assertEqual(doc.is_edit_locked, 1)

	def test_editing_master_data_after_issuance_is_refused(self):
		"""Trạng thái 06 đã tiêu số hóa đơn thật — sửa dữ liệu là sai lệch chứng từ."""
		doc = make_fei()
		doc.insert()
		doc.status = STATUS_ISSUED
		doc.flags.ignore_status_lock = True
		doc.save()

		reloaded = frappe.get_doc(FEI, doc.name)
		reloaded.customer_name = "Tên khác"
		reloaded.flags.ignore_links = True
		with self.assertRaises(frappe.ValidationError):
			reloaded.save()

	def test_editing_lines_after_issuance_is_refused(self):
		doc = make_fei()
		doc.insert()
		doc.status = STATUS_ISSUED
		doc.flags.ignore_status_lock = True
		doc.save()

		reloaded = frappe.get_doc(FEI, doc.name)
		reloaded.lines[0].qty = 999
		reloaded.flags.ignore_links = True
		with self.assertRaises(frappe.ValidationError):
			reloaded.save()

	def _locked_document(self):
		doc = make_fei()
		doc.insert()
		doc.status = STATUS_TAX_ACCEPTED
		doc.flags.ignore_status_lock = True
		doc.save()
		return frappe.get_doc(FEI, doc.name)

	def test_resaving_a_locked_record_untouched_is_allowed(self):
		"""Form đi qua JSON nên Date về dạng chuỗi — không được coi là đã sửa.

		So thẳng ``"2026-08-12"`` với ``datetime.date(2026, 8, 12)`` luôn ra
		"khác", nên mọi lần lưu chứng từ đã khóa từ giao diện đều bị chặn và
		thông báo đổ oan cho ``invoice_date``. Các test khác không bắt được vì
		chúng nạp bằng ``get_doc`` nên nhận thẳng kiểu ngày của CSDL.
		"""
		resent = frappe.get_doc(_as_browser_sends(self._locked_document()))
		resent.flags.ignore_links = True
		resent.save()

	def test_a_locked_record_still_accepts_fields_outside_the_frozen_set(self):
		"""Số biên bản ghi bổ sung sau khi hóa đơn đã khóa — không phải dữ liệu Fast."""
		payload = _as_browser_sends(self._locked_document())
		payload["minute_no"] = "BB-2026-001"

		resent = frappe.get_doc(payload)
		resent.flags.ignore_links = True
		resent.save()
		self.assertEqual(frappe.db.get_value(FEI, resent.name, "minute_no"), "BB-2026-001")

	def test_editing_master_data_from_the_form_is_still_refused(self):
		payload = _as_browser_sends(self._locked_document())
		payload["customer_name"] = "Tên khác"

		resent = frappe.get_doc(payload)
		resent.flags.ignore_links = True
		with self.assertRaises(frappe.ValidationError) as caught:
			resent.save()

		message = str(caught.exception)
		self.assertIn("customer_name", message)
		self.assertNotIn("invoice_date", message)

	def test_error_state_stays_editable_so_it_can_be_fixed(self):
		doc = make_fei()
		doc.insert()
		doc.status = STATUS_ERROR
		doc.save()
		self.assertEqual(doc.is_edit_locked, 0)

		doc.customer_name = "Tên đã sửa"
		doc.save()
		self.assertEqual(doc.customer_name, "Tên đã sửa")

	def test_customer_approved_state_is_still_editable(self):
		doc = make_fei(status=STATUS_CUSTOMER_APPROVED)
		doc.insert()
		self.assertEqual(doc.is_edit_locked, 0)

	def test_issuing_state_is_locked(self):
		doc = make_fei()
		doc.insert()
		doc.status = STATUS_ISSUING
		doc.flags.ignore_status_lock = True
		doc.save()
		self.assertEqual(doc.is_edit_locked, 1)

	# --- fast_key bất biến ------------------------------------------------

	def test_fast_key_cannot_change_once_the_record_exists(self):
		"""Đặc tả A4: Key sinh một lần và không đổi — đổi Key là nguy cơ lỗi 809/835."""
		doc = make_fei()
		doc.insert()
		doc.fast_key = "KHACHOANTOAN"
		doc.flags.ignore_links = True
		with self.assertRaises(frappe.ValidationError):
			doc.save()

	# --- Bắt buộc có điều kiện (C2.1 #6, #7, #8) --------------------------

	def test_adjustment_requires_original_document_and_reason(self):
		doc = make_fei(invoice_type=INVOICE_TYPE_ADJUSTMENT)
		with self.assertRaises(frappe.ValidationError):
			doc.insert()

	def test_original_invoice_needs_no_adjustment_fields(self):
		doc = make_fei(invoice_type=INVOICE_TYPE_ORIGINAL)
		doc.insert()
		self.assertTrue(doc.name.startswith("FEI-"))

	def test_adjustment_with_full_lineage_is_accepted(self):
		original = make_fei()
		original.insert()
		frappe.db.set_value(FEI, original.name, "status", STATUS_TAX_ACCEPTED)

		adjustment = make_fei(
			invoice_type=INVOICE_TYPE_ADJUSTMENT,
			original_document=original.name,
			adjustment_type="1 - Điều chỉnh giảm",
			adjustment_reason="Trả lại 10 hộp do sai quy cách",
			fast_key="MATDNTEST0001DC",
		)
		adjustment.insert()
		self.assertEqual(adjustment.original_document, original.name)


class TestComputeTotals(FrappeTestCase):
	"""Chứng từ tự tính dòng hàng và tổng hợp — không chỉ giữ data copy."""

	def setUp(self):
		frappe.db.rollback()

	def tearDown(self):
		frappe.db.rollback()

	def _doc(self, lines, **master):
		doc = make_fei(**master)
		doc.set("lines", [])
		for line in lines:
			base = {
				"process_type": "1",
				"item_code": "X",
				"item_name": "Hàng X",
				"uom": "Cái",
				"tax_rate": "10",
			}
			base.update(line)
			doc.append("lines", base)
		doc.insert()
		doc.reload()
		return doc

	def test_line_amount_is_qty_times_price(self):
		doc = self._doc([{"qty": 3, "price": 100000}])
		self.assertEqual(doc.lines[0].amount, 300000)

	def test_line_tax_is_amount_times_rate(self):
		doc = self._doc([{"qty": 3, "price": 100000, "tax_rate": "10"}])
		self.assertEqual(doc.lines[0].tax_amount, 30000)

	def test_five_percent_rate_computes_correctly(self):
		doc = self._doc([{"qty": 2, "price": 100000, "tax_rate": "5"}])
		self.assertEqual(doc.lines[0].tax_amount, 10000)

	def test_non_taxable_rate_has_zero_tax(self):
		"""KCT (-1), không kê khai (-2), không ghi (-9) → không có tiền thuế."""
		for rate in ("-1", "-2", "-9"):
			doc = self._doc([{"qty": 5, "price": 100000, "tax_rate": rate}])
			self.assertEqual(doc.lines[0].tax_amount, 0, rate)

	def test_discount_rate_reduces_the_line_amount(self):
		doc = self._doc([{"qty": 10, "price": 100000, "discount_rate": 10, "tax_rate": "10"}])
		self.assertEqual(doc.lines[0].discount_amount, 100000)
		self.assertEqual(doc.lines[0].amount, 900000)
		self.assertEqual(doc.lines[0].tax_amount, 90000)

	def test_master_totals_sum_the_lines(self):
		doc = self._doc(
			[{"qty": 100, "price": 100000, "tax_rate": "10"}, {"qty": 50, "price": 250000, "tax_rate": "10"}]
		)
		self.assertEqual(doc.amount, 22_500_000)
		self.assertEqual(doc.tax_amount, 2_250_000)
		self.assertEqual(doc.total_amount, 24_750_000)

	def test_tax_groups_are_filled_from_the_lines(self):
		doc = self._doc(
			[
				{"qty": 1, "price": 1_000_000, "tax_rate": "10"},
				{"qty": 1, "price": 1_000_000, "tax_rate": "5"},
			]
		)
		self.assertEqual(doc.tax_amount_10, 100_000)
		self.assertEqual(doc.tax_amount_5, 50_000)

	def test_total_takes_deductions_off(self):
		doc = self._doc([{"qty": 100, "price": 100000, "tax_rate": "10"}], deduction_amount=1_000_000)
		# 10,000,000 + 1,000,000 thuế - 1,000,000 giảm trừ
		self.assertEqual(doc.total_amount, 10_000_000)

	def test_amount_in_words_follows_the_computed_total(self):
		doc = self._doc([{"qty": 100, "price": 100000, "tax_rate": "10"}])
		self.assertIn("đồng", doc.amount_in_words)
		self.assertIn("Mười một triệu", doc.amount_in_words)

	def test_editing_a_line_recomputes_on_save(self):
		doc = self._doc([{"qty": 100, "price": 100000, "tax_rate": "10"}])
		doc.lines[0].qty = 200
		doc.flags.ignore_links = True
		doc.save()
		doc.reload()
		self.assertEqual(doc.lines[0].amount, 20_000_000)
		self.assertEqual(doc.amount, 20_000_000)
		self.assertEqual(doc.total_amount, 22_000_000)

	def test_issued_invoice_values_are_frozen_not_recomputed(self):
		"""Hóa đơn đã phát hành: số liệu là chứng từ pháp lý, tuyệt đối không tính lại."""
		doc = self._doc([{"qty": 100, "price": 100000, "tax_rate": "10"}])
		frappe.db.set_value(FEI, doc.name, {"status": STATUS_ISSUED, "amount": 999}, update_modified=False)
		doc.reload()
		# Lưu lại (ví dụ cập nhật trạng thái CQT) không được đụng vào số tiền.
		doc.flags.ignore_status_lock = True
		doc.flags.ignore_links = True
		doc.save()
		doc.reload()
		self.assertEqual(doc.amount, 999)

	# --- Chứng từ tự tính, không phụ thuộc phiếu giao --------------------

	def test_adding_a_line_moves_every_total(self):
		"""Yêu cầu gốc: thêm một dòng thì mọi số liệu khác đổi theo."""
		doc = self._doc([{"qty": 100, "price": 100000, "tax_rate": "10"}])
		before = (doc.amount, doc.tax_amount, doc.tax_amount_10, doc.total_amount, doc.amount_in_words)

		doc.append(
			"lines",
			{
				"process_type": "1",
				"item_code": "VT002",
				"item_name": "Găng tay",
				"uom": "Đôi",
				"qty": 10,
				"price": 50000,
				"tax_rate": "5",
			},
		)
		doc.flags.ignore_links = True
		doc.save()
		doc.reload()

		self.assertEqual(doc.lines[1].amount, 500_000)
		self.assertEqual(doc.lines[1].tax_amount, 25_000)
		self.assertEqual(doc.amount, 10_500_000)
		self.assertEqual(doc.tax_amount, 1_025_000)
		self.assertEqual(doc.tax_amount_5, 25_000)
		self.assertEqual(doc.total_amount, 11_525_000)
		after = (doc.amount, doc.tax_amount, doc.tax_amount_10, doc.total_amount, doc.amount_in_words)
		self.assertNotEqual(before, after)

	def test_promotion_line_does_not_inflate_the_amount_due(self):
		doc = self._doc(
			[
				{"qty": 1, "price": 1_000_000, "tax_rate": "10"},
				{"process_type": "2", "qty": 2, "price": 100_000, "tax_rate": "10"},
			]
		)
		self.assertEqual(doc.amount, 1_000_000)
		self.assertEqual(doc.promotion_amount, 200_000)
		self.assertEqual(doc.total_amount, 1_100_000)

	def test_discount_line_fills_the_master_discount_box(self):
		doc = self._doc(
			[
				{"qty": 1, "price": 1_000_000, "tax_rate": "10"},
				{"process_type": "3", "qty": 1, "price": -100_000, "tax_rate": "10"},
			]
		)
		self.assertEqual(doc.amount, 900_000)
		self.assertEqual(doc.discount_amount, 100_000)
		self.assertEqual(doc.total_amount, 990_000)

	def test_the_form_preview_agrees_with_what_saving_computes(self):
		"""Số form hiện ra khi chưa lưu phải trùng số server ghi lúc Lưu.

		Nếu hai bên lệch thì kế toán thấy một con số rồi chứng từ lưu một con số
		khác — đúng cái làm mất niềm tin vào toàn bộ phần tính toán.
		"""
		from erpnext.einvoice.totals import preview_totals

		doc = self._doc(
			[
				{"qty": 7, "price": 142_857, "tax_rate": "10"},
				{"process_type": "2", "qty": 3, "price": 33_333, "tax_rate": "10"},
				{"process_type": "3", "qty": 1, "price": -77_777, "tax_rate": "10"},
				{"qty": 13, "price": 76_923, "discount_rate": 3.33, "tax_rate": "5"},
			],
			deduction_amount=1000,
		)
		preview = preview_totals(_as_browser_sends(doc))

		for fieldname, value in preview["master"].items():
			self.assertEqual(value, doc.get(fieldname), fieldname)
		for values in preview["lines"]:
			row = doc.lines[values["idx"] - 1]
			for fieldname, value in values.items():
				if fieldname != "idx":
					self.assertEqual(value, row.get(fieldname), f"dòng {values['idx']} · {fieldname}")

	def test_the_form_preview_works_before_the_first_save(self):
		"""Chứng từ chưa lưu lần nào cũng phải hiện số — đó chính là lúc đang nhập."""
		from erpnext.einvoice.totals import preview_totals

		doc = make_fei()
		doc.lines[0].qty = 20
		doc.lines[0].price = 50_000
		payload = _as_browser_sends(doc)
		payload["__islocal"] = 1
		payload["__unsaved"] = 1

		preview = preview_totals(payload)

		self.assertEqual(preview["lines"][0]["amount"], 1_000_000)
		self.assertEqual(preview["lines"][0]["tax_amount"], 100_000)
		self.assertEqual(preview["master"]["amount"], 1_000_000)
		self.assertEqual(preview["master"]["total_amount"], 1_100_000)
		self.assertIn("Một triệu một trăm nghìn", preview["master"]["amount_in_words"])

	def test_the_form_preview_never_writes_to_the_database(self):
		"""Chỉ là số để xem: lúc Lưu server vẫn tính lại, nên đây không được ghi gì."""
		from erpnext.einvoice.totals import preview_totals

		doc = self._doc([{"qty": 100, "price": 100000, "tax_rate": "10"}])
		payload = _as_browser_sends(doc)
		payload["amount"] = 1
		payload["lines"][0]["qty"] = 1

		preview_totals(payload)

		self.assertEqual(frappe.db.get_value(FEI, doc.name, "amount"), 10_000_000)


class TestManualOverride(FrappeTestCase):
	"""Ghi đè số tổng hợp — cửa thoát có kiểm soát khi số máy tính không dùng được."""

	def setUp(self):
		frappe.db.rollback()

	def tearDown(self):
		frappe.db.rollback()

	def _overridden(self, **values):
		doc = make_fei(totals_manual_override=1, override_reason="Chốt số theo biên bản với Fast", **values)
		doc.insert()
		return doc

	def test_override_keeps_hand_entered_numbers(self):
		doc = self._overridden(amount=12_345, tax_amount=678, total_amount=13_023)
		doc.reload()
		self.assertEqual(doc.amount, 12_345)
		self.assertEqual(doc.tax_amount, 678)
		self.assertEqual(doc.total_amount, 13_023)

	def test_override_needs_a_reason(self):
		doc = make_fei(totals_manual_override=1)
		self.assertRaises(frappe.ValidationError, doc.insert)

	def test_clearing_the_override_recomputes_from_the_lines(self):
		doc = self._overridden(amount=12_345, tax_amount=678, total_amount=13_023)
		doc.totals_manual_override = 0
		doc.override_reason = None
		doc.flags.ignore_links = True
		doc.save()
		doc.reload()
		self.assertEqual(doc.amount, 10_000_000)
		self.assertEqual(doc.total_amount, 11_000_000)

	def test_computed_fields_open_up_only_while_overriding(self):
		meta = frappe.get_meta(FEI)
		for fieldname in (
			"amount",
			"total_amount",
			"tax_amount",
			"tax_rate",
			"tax_amount_free",
			"tax_amount_0",
			"tax_amount_5",
			"tax_amount_10",
			"discount_amount",
			"promotion_amount",
			"amount_in_words",
		):
			self.assertEqual(
				meta.get_field(fieldname).read_only_depends_on,
				"eval:doc.is_edit_locked || !doc.totals_manual_override",
				fieldname,
			)

	def test_reason_is_mandatory_in_the_form_too(self):
		field = frappe.get_meta(FEI).get_field("override_reason")
		self.assertEqual(field.mandatory_depends_on, "eval:doc.totals_manual_override")


class TestProcessTypeLegend(FrappeTestCase):
	"""Mã Tính chất 1..5 phải đọc được ngay trên form, không phải tra tài liệu."""

	def test_the_lines_table_spells_out_every_process_type(self):
		from erpnext.einvoice.constants import PROCESS_TYPE_CODES, PROCESS_TYPE_LABELS

		description = frappe.get_meta(FEI).get_field("lines").description or ""
		for code in PROCESS_TYPE_CODES:
			self.assertIn(code, description, code)
			self.assertIn(PROCESS_TYPE_LABELS[code], description, code)

	def test_the_line_field_carries_the_same_legend(self):
		from erpnext.einvoice.constants import PROCESS_TYPE_LABELS

		description = frappe.get_meta("Fast EInvoice Line").get_field("process_type").description or ""
		for code, label in PROCESS_TYPE_LABELS.items():
			self.assertIn(f"{code} = {label}", description, code)

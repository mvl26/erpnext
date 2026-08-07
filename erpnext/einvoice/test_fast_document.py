# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""DocType `Fast EInvoice Document` — mục C2 và bảng trạng thái B2."""

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
			"invoice_date": "2026-08-07",
			"customer_code": "KH0001",
			"customer_name": "Bệnh viện Đa khoa X",
			"customer_type": "1",
			"customer_tax_code": "0101234567",
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

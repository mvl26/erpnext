# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Nút 1 (tạo chứng từ HĐĐT từ phiếu giao) và Nút 2 (đồng bộ lại) — mục E1."""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.einvoice.builder import (
	create_from_delivery_note,
	fast_key_for,
	resync_from_delivery_note,
)
from erpnext.einvoice.constants import STATUS_DRAFT, STATUS_ISSUED, STATUS_TAX_ACCEPTED
from erpnext.einvoice.test_fast_client import configure
from erpnext.einvoice.test_fixtures import CUSTOMER, make_delivery_note

FEI = "Fast EInvoice Document"


class TestFastKey(FrappeTestCase):
	def test_key_strips_vietnamese_diacritics(self):
		self.assertEqual(fast_key_for("ĐƠN-HÀNG-01"), "DON-HANG-01")

	def test_key_is_capped_at_32_characters(self):
		self.assertEqual(len(fast_key_for("X" * 60)), 32)

	def test_ordinary_delivery_note_name_passes_through(self):
		self.assertEqual(fast_key_for("MAT-DN-2026-00001"), "MAT-DN-2026-00001")


class TestCreateFromDeliveryNote(FrappeTestCase):
	def setUp(self):
		frappe.db.rollback()
		configure()
		self.dn = make_delivery_note()

	def tearDown(self):
		frappe.db.rollback()

	def _create(self):
		return frappe.get_doc(FEI, create_from_delivery_note(self.dn.name))

	def test_new_record_starts_as_a_draft(self):
		fei = self._create()
		self.assertEqual(fei.status, STATUS_DRAFT)
		self.assertEqual(fei.invoice_type, "Hóa đơn gốc")

	def test_key_comes_from_the_delivery_note_name(self):
		self.assertEqual(self._create().fast_key, fast_key_for(self.dn.name))

	def test_totals_are_copied_from_the_delivery_note(self):
		fei = self._create()
		self.assertEqual(fei.amount, self.dn.net_total)
		self.assertEqual(fei.total_amount, self.dn.grand_total)
		self.assertEqual(fei.tax_amount, self.dn.total_taxes_and_charges)

	def test_lines_are_copied_with_fast_defaults(self):
		fei = self._create()
		self.assertEqual(len(fei.lines), len(self.dn.items))
		line = fei.lines[0]
		self.assertEqual(line.item_code, self.dn.items[0].item_code)
		self.assertEqual(line.qty, self.dn.items[0].qty)
		self.assertEqual(line.price, self.dn.items[0].rate)
		self.assertEqual(line.amount, self.dn.items[0].net_amount)
		self.assertEqual(line.process_type, "1")

	def test_line_tax_matches_the_delivery_note_rate(self):
		fei = self._create()
		self.assertEqual(fei.lines[0].tax_rate, "10")
		self.assertAlmostEqual(fei.lines[0].tax_amount, self.dn.total_taxes_and_charges, places=2)

	def test_tax_group_buckets_are_filled(self):
		fei = self._create()
		self.assertAlmostEqual(fei.tax_amount_10, self.dn.total_taxes_and_charges, places=2)

	def test_amount_in_words_is_generated_with_the_currency_keyword(self):
		fei = self._create()
		self.assertTrue(fei.amount_in_words)
		self.assertIn("đồng", fei.amount_in_words)

	def test_buyer_address_is_the_billing_address_not_the_shipping_one(self):
		"""Đặc tả C2.3 #27 gạch chân điều này: KHÔNG lấy địa chỉ giao hàng."""
		fei = self._create()
		self.assertIn("Số 1 Phố Y", fei.address)

	def test_address_is_only_the_address(self):
		"""Fast có thẻ riêng cho điện thoại và email — nhét vào Address là sai chứng từ."""
		address = self._create().address
		self.assertNotIn("Phone:", address)
		self.assertNotIn("Email:", address)
		self.assertIn("Hà Nội", address)

	def test_address_carries_no_html_or_newlines(self):
		"""Địa chỉ dựng từ HTML của Frappe — thẻ sót lại là lỗi 63505/825."""
		address = self._create().address
		self.assertNotIn("<", address)
		self.assertNotIn("\n", address)
		self.assertTrue(address)

	def test_customer_details_are_pulled_across(self):
		fei = self._create()
		self.assertEqual(fei.customer, CUSTOMER)
		self.assertEqual(fei.customer_tax_code, "0101234565")
		self.assertEqual(fei.customer_type, "1")

	def test_issuer_name_defaults_to_the_person_pressing_the_button(self):
		self.assertTrue(self._create().human_name)

	def test_delivery_note_is_stamped_back(self):
		"""Kế toán phải thấy ngay trên phiếu giao là đã có chứng từ HĐĐT."""
		fei = self._create()
		self.dn.reload()
		self.assertEqual(self.dn.fast_einvoice, fei.name)
		self.assertEqual(self.dn.fast_einvoice_status, STATUS_DRAFT)

	def test_the_new_record_passes_validation(self):
		from erpnext.einvoice.validation import validate_before_send

		result = validate_before_send(self._create())
		self.assertTrue(result.ok, [i.message for i in result.blocking])

	# --- Tiền điều kiện của mục E1 ---------------------------------------

	def test_draft_delivery_note_is_refused(self):
		draft = make_delivery_note(submit=False)
		with self.assertRaises(frappe.ValidationError):
			create_from_delivery_note(draft.name)

	def test_return_delivery_note_is_refused(self):
		returned = make_delivery_note(is_return=True)
		with self.assertRaises(frappe.ValidationError):
			create_from_delivery_note(returned.name)

	def test_second_invoice_for_the_same_delivery_note_is_refused(self):
		"""Một phiếu giao chỉ được một hóa đơn đang sống."""
		self._create()
		with self.assertRaises(frappe.ValidationError):
			create_from_delivery_note(self.dn.name)

	def test_a_cancelled_invoice_frees_the_delivery_note_again(self):
		fei = self._create()
		frappe.db.set_value(FEI, fei.name, "status", "12 - Đã hủy nội bộ")

		replacement = frappe.get_doc(FEI, create_from_delivery_note(self.dn.name))
		self.assertEqual(replacement.status, STATUS_DRAFT)

	def test_disabled_integration_refuses(self):
		configure(enabled=0)
		with self.assertRaises(frappe.ValidationError):
			create_from_delivery_note(self.dn.name)


class TestResync(FrappeTestCase):
	def setUp(self):
		frappe.db.rollback()
		configure()
		self.dn = make_delivery_note()
		self.fei = frappe.get_doc(FEI, create_from_delivery_note(self.dn.name))

	def tearDown(self):
		frappe.db.rollback()

	def test_resync_restores_edited_master_data(self):
		self.fei.customer_name = "Tên gõ nhầm"
		self.fei.flags.ignore_links = True
		self.fei.save()

		resync_from_delivery_note(self.fei.name)
		self.fei.reload()
		self.assertEqual(self.fei.customer_name, self.dn.customer_name)

	def test_resync_rebuilds_the_lines(self):
		self.fei.lines[0].qty = 1
		self.fei.flags.ignore_links = True
		self.fei.save()

		resync_from_delivery_note(self.fei.name)
		self.fei.reload()
		self.assertEqual(self.fei.lines[0].qty, self.dn.items[0].qty)

	def test_resync_from_a_customer_facing_state_counts_as_a_revision(self):
		"""Đặc tả C2.2 #19: đếm số lần quay về Nháp **từ 02/03/04**."""
		frappe.db.set_value(FEI, self.fei.name, "status", "03 - Chờ khách duyệt")

		resync_from_delivery_note(self.fei.name)
		self.fei.reload()
		self.assertEqual(self.fei.revision_count, 1)
		self.assertEqual(self.fei.status, STATUS_DRAFT)

	def test_resync_of_a_draft_is_not_a_revision(self):
		"""Đang là Nháp mà nạp lại dữ liệu thì chưa có vòng qua lại nào với khách."""
		before = self.fei.revision_count
		resync_from_delivery_note(self.fei.name)
		self.fei.reload()
		self.assertEqual(self.fei.revision_count, before)

	def test_resync_never_changes_the_key(self):
		"""Đặc tả A4: Key sinh một lần và không đổi."""
		key = self.fei.fast_key
		resync_from_delivery_note(self.fei.name)
		self.fei.reload()
		self.assertEqual(self.fei.fast_key, key)

	def test_resync_returns_an_approved_invoice_to_draft(self):
		frappe.db.set_value(FEI, self.fei.name, "status", "04 - Khách đã duyệt")
		resync_from_delivery_note(self.fei.name)
		self.fei.reload()
		self.assertEqual(self.fei.status, STATUS_DRAFT)

	def test_resync_is_refused_once_the_invoice_is_issued(self):
		frappe.db.set_value(FEI, self.fei.name, "status", STATUS_ISSUED)
		with self.assertRaises(frappe.ValidationError):
			resync_from_delivery_note(self.fei.name)

	def test_resync_is_refused_after_the_tax_office_accepted(self):
		frappe.db.set_value(FEI, self.fei.name, "status", STATUS_TAX_ACCEPTED)
		with self.assertRaises(frappe.ValidationError):
			resync_from_delivery_note(self.fei.name)

# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Đóng gói payload gửi Fast — Phần I của đặc tả."""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.einvoice.payload import (
	DETAIL_BASE_TAGS,
	MASTER_BASE_TAGS,
	amount_in_words_for,
	build_payload,
	compute_tax_groups,
)
from erpnext.einvoice.test_fast_client import configure
from erpnext.einvoice.test_fast_document import make_fei


class TestAmountInWords(FrappeTestCase):
	def test_vnd_reads_as_dong(self):
		self.assertIn("đồng", amount_in_words_for(11_000_000, "VND"))

	def test_usd_reads_as_do_la_my(self):
		"""Đặc tả F#5: sai từ khóa loại tiền là lỗi 152."""
		self.assertIn("đô la Mỹ", amount_in_words_for(1_500, "USD"))

	def test_eur_reads_as_euro(self):
		self.assertIn("Euro", amount_in_words_for(1_500, "EUR"))

	def test_unknown_currency_falls_back_to_the_iso_code(self):
		self.assertIn("AUD", amount_in_words_for(100, "AUD"))


class TestTaxGroups(FrappeTestCase):
	def test_groups_sum_per_rate(self):
		groups = compute_tax_groups(
			[
				frappe._dict(tax_rate="10", tax_amount=1000),
				frappe._dict(tax_rate="10", tax_amount=500),
				frappe._dict(tax_rate="5", tax_amount=250),
				frappe._dict(tax_rate="0", tax_amount=0),
				frappe._dict(tax_rate="-1", tax_amount=0),
			]
		)
		self.assertEqual(groups["tax_amount_10"], 1500)
		self.assertEqual(groups["tax_amount_5"], 250)
		self.assertEqual(groups["tax_amount_0"], 0)

	def test_non_taxable_rates_land_in_the_free_bucket(self):
		groups = compute_tax_groups(
			[frappe._dict(tax_rate="-1", tax_amount=0), frappe._dict(tax_rate="-2", tax_amount=0)]
		)
		self.assertEqual(groups["tax_amount_free"], 0)

	def test_eight_percent_has_no_bucket_and_is_reported_separately(self):
		"""Bốn thẻ nhóm của Phần I không có ô cho thuế suất 8%."""
		groups = compute_tax_groups([frappe._dict(tax_rate="8", tax_amount=800)])
		self.assertEqual(groups["unbucketed"], 800)


class TestPayloadShape(FrappeTestCase):
	def setUp(self):
		frappe.db.rollback()
		configure()
		self.fei = make_fei()
		self.fei.insert()

	def tearDown(self):
		frappe.db.rollback()

	def test_voucher_book_comes_from_settings(self):
		self.assertEqual(build_payload(self.fei)["voucherBook"], "1C26TAA")

	def test_structure_and_values_line_up_one_to_one(self):
		"""Lệch một ô là dữ liệu chạy sang cột khác mà Fast vẫn nhận."""
		payload = build_payload(self.fei)
		structure = payload["data"]["structure"]
		invoice = payload["data"]["invoices"][0]

		self.assertEqual(len(structure["master"]), len(invoice["master"]))
		for row in invoice["detail"]:
			self.assertEqual(len(structure["detail"]), len(row))

	def test_base_master_tags_are_all_present_in_spec_order(self):
		structure = build_payload(self.fei)["data"]["structure"]
		present = [tag for tag in structure["master"] if tag in MASTER_BASE_TAGS]
		self.assertEqual(present, list(MASTER_BASE_TAGS))

	def test_release_type_is_always_sent_to_pin_the_discount_semantics(self):
		"""ReleaseType=1 nói với Fast rằng cột Amount đã trừ chiết khấu.

		Không nằm trong danh sách tham chiếu Phần I, nhưng dòng hàng của ta lấy
		`net_amount` (đã trừ chiết khấu) nên bỏ thẻ này là để Fast tự đoán.
		"""
		structure = build_payload(self.fei)["data"]["structure"]
		self.assertIn("ReleaseType", structure["master"])

	def test_base_detail_tags_match_the_spec_reference(self):
		structure = build_payload(self.fei)["data"]["structure"]
		self.assertEqual(structure["detail"], list(DETAIL_BASE_TAGS))

	def test_unused_optional_tags_are_left_out_entirely(self):
		"""Phần I: trường không dùng thì bỏ hẳn khỏi structure, không gửi thẻ rỗng."""
		structure = build_payload(self.fei)["data"]["structure"]
		for tag in ("IDCardNo", "PassportNo", "BuyerUnit", "External1", "DeductionAmount"):
			self.assertNotIn(tag, structure["master"])

	def test_optional_tag_appears_once_it_carries_a_value(self):
		self.fei.buyer_unit = "1234567"
		self.fei.flags.ignore_links = True
		self.fei.save()

		payload = build_payload(self.fei)
		structure = payload["data"]["structure"]
		self.assertIn("BuyerUnit", structure["master"])
		self.assertEqual(
			payload["data"]["invoices"][0]["master"][structure["master"].index("BuyerUnit")], "1234567"
		)

	def test_invoice_date_is_serialised_day_first(self):
		payload = build_payload(self.fei)
		structure = payload["data"]["structure"]
		value = payload["data"]["invoices"][0]["master"][structure["master"].index("InvoiceDate")]
		self.assertEqual(value, "07/08/2026")

	def test_money_and_rates_are_sent_as_numbers(self):
		payload = build_payload(self.fei)
		structure = payload["data"]["structure"]
		master = payload["data"]["invoices"][0]["master"]

		for tag in ("Amount", "TotalAmount", "TaxAmount", "ExchangeRate", "TaxRate"):
			value = master[structure["master"].index(tag)]
			self.assertIsInstance(value, (int, float), f"{tag} phải là số, đang là {type(value)}")

	def test_customer_type_and_process_type_stay_strings(self):
		"""Phần I gửi CustomerType là "1" (chuỗi) nhưng TaxRate là 10 (số)."""
		payload = build_payload(self.fei)
		structure = payload["data"]["structure"]
		master = payload["data"]["invoices"][0]["master"]

		self.assertIsInstance(master[structure["master"].index("CustomerType")], str)
		self.assertIsInstance(payload["data"]["invoices"][0]["detail"][0][0], str)

	def test_line_values_follow_the_detail_order(self):
		payload = build_payload(self.fei)
		structure = payload["data"]["structure"]
		row = payload["data"]["invoices"][0]["detail"][0]

		self.assertEqual(row[structure["detail"].index("ItemCode")], "VT001")
		self.assertEqual(row[structure["detail"].index("ItemName")], "Bơm kim tiêm 5ml")
		self.assertEqual(row[structure["detail"].index("Quantity")], 100)

	def test_tax_code_is_sent_digits_only(self):
		"""Fast muốn MST toàn số (78013) — dấu phân cách phải được bỏ khi gửi."""
		self.fei.customer_tax_code = "0101234567-001"
		self.fei.flags.ignore_links = True
		self.fei.save()

		payload = build_payload(self.fei)
		structure = payload["data"]["structure"]
		value = payload["data"]["invoices"][0]["master"][structure["master"].index("CustomerTaxCode")]
		self.assertEqual(value, "0101234567001")


class TestAdjustmentPayload(FrappeTestCase):
	def setUp(self):
		frappe.db.rollback()
		configure()
		self.original = make_fei()
		self.original.insert()
		frappe.db.set_value("Fast EInvoice Document", self.original.name, "fast_key_search", "KEYSEARCH-ORIG")

	def tearDown(self):
		frappe.db.rollback()

	def _child(self, invoice_type, **values):
		child = make_fei(
			invoice_type=invoice_type,
			original_document=self.original.name,
			adjustment_reason="Sai số lượng",
			fast_key="MATDNTEST0001X",
			**values,
		)
		child.insert()
		return child

	def test_original_invoice_sends_no_lineage_keys(self):
		payload = build_payload(make_fei())
		self.assertNotIn("originalInvoice", payload)
		self.assertNotIn("adjustmentType", payload)

	def test_adjustment_points_at_the_original_key_search(self):
		child = self._child("Hóa đơn điều chỉnh", adjustment_type="1 - Điều chỉnh giảm")
		payload = build_payload(child)

		self.assertEqual(payload["originalInvoice"], "KEYSEARCH-ORIG")
		self.assertEqual(payload["adjustmentType"], "1")

	def test_replacement_is_always_adjustment_type_four(self):
		"""Đặc tả C2.1 #7: thay thế → hệ thống tự gán 4."""
		child = self._child("Hóa đơn thay thế")
		self.assertEqual(build_payload(child)["adjustmentType"], "4")

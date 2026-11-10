# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Nút 1 (tạo chứng từ HĐĐT từ hóa đơn bán), Nút 2 (đồng bộ lại), hủy hóa đơn bán — mục E1, E1.1.

Đặc tả bản 3.0: hóa đơn gốc chỉ lập từ Sales Invoice đã submit. Phiếu giao chỉ
còn là nguồn của bản ghi bản 2.0 — các test cuối file giữ lối ra cho chúng.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, flt, getdate, nowdate

from erpnext.einvoice.builder import (
	create_from_delivery_note,
	create_from_sales_invoice,
	fast_key_for,
	link_sales_invoice,
	resync_from_source,
)
from erpnext.einvoice.constants import (
	SOURCE_DELIVERY_NOTE_V2,
	SOURCE_SALES_INVOICE,
	STATUS_CANCELLED,
	STATUS_DRAFT,
	STATUS_ISSUED,
	STATUS_NEEDS_RECONCILE,
	STATUS_TAX_ACCEPTED,
)
from erpnext.einvoice.tests.test_fast_client import configure
from erpnext.einvoice.tests.test_fixtures import (
	COMPANY,
	CUSTOMER,
	ITEM_NAME,
	ensure_item,
	make_delivery_note,
	make_legacy_fei,
	make_sales_invoice,
	make_sales_invoice_from_delivery_note,
	output_vat_account,
)

FEI = "Fast EInvoice Document"


def _item_tax_template(rate):
	template = frappe.get_doc(
		{
			"doctype": "Item Tax Template",
			"title": f"GTGT {rate}pc test {frappe.generate_hash(length=6)}",
			"company": COMPANY,
			"taxes": [{"tax_type": output_vat_account(), "tax_rate": rate}],
		}
	)
	template.flags.ignore_permissions = True
	template.insert()
	return template.name


class TestFastKey(FrappeTestCase):
	def test_key_strips_vietnamese_diacritics(self):
		self.assertEqual(fast_key_for("ĐƠN-HÀNG-01"), "DON-HANG-01")

	def test_key_is_capped_at_32_characters(self):
		self.assertEqual(len(fast_key_for("X" * 60)), 32)

	def test_ordinary_sales_invoice_name_passes_through(self):
		self.assertEqual(fast_key_for("ACC-SINV-2026-00011"), "ACC-SINV-2026-00011")


class TestCreateFromSalesInvoice(FrappeTestCase):
	def setUp(self):
		frappe.db.rollback()
		configure()
		self.si = make_sales_invoice()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def _create(self, si=None):
		return frappe.get_doc(FEI, create_from_sales_invoice((si or self.si).name))

	def test_new_record_starts_as_a_draft(self):
		fei = self._create()
		self.assertEqual(fei.status, STATUS_DRAFT)
		self.assertEqual(fei.invoice_type, "Hóa đơn gốc")

	def test_the_sales_invoice_is_the_declared_source(self):
		fei = self._create()
		self.assertEqual(fei.source_doctype, SOURCE_SALES_INVOICE)
		self.assertEqual(fei.sales_invoice, self.si.name)
		self.assertFalse(fei.delivery_note)

	def test_invoice_date_is_not_the_posting_date(self):
		"""Kịch bản K6 #13: hóa đơn bán ghi sổ hôm trước, chứng từ HĐĐT vẫn ra ngày hôm nay."""
		frappe.db.set_value("Sales Invoice", self.si.name, "posting_date", add_days(nowdate(), -1))
		self.assertEqual(getdate(self._create().invoice_date), getdate(nowdate()))

	def test_key_comes_from_the_sales_invoice_name(self):
		self.assertEqual(self._create().fast_key, fast_key_for(self.si.name))

	def test_totals_match_the_sales_invoice(self):
		fei = self._create()
		self.assertEqual(fei.amount, self.si.net_total)
		self.assertEqual(fei.total_amount, self.si.grand_total)
		self.assertEqual(fei.tax_amount, self.si.total_taxes_and_charges)

	def test_totals_are_computed_not_copied(self):
		"""Chỉ `totals.py` tính tiền: tổng sai trên hóa đơn bán không được bê sang."""
		frappe.db.set_value("Sales Invoice", self.si.name, {"net_total": 1, "grand_total": 1})
		fei = self._create()
		self.assertEqual(fei.amount, 10_000_000)
		self.assertEqual(fei.total_amount, 11_000_000)

	def test_lines_are_copied_with_fast_defaults(self):
		fei = self._create()
		self.assertEqual(len(fei.lines), len(self.si.items))
		line = fei.lines[0]
		self.assertEqual(line.item_code, self.si.items[0].item_code)
		self.assertEqual(line.qty, self.si.items[0].qty)
		self.assertEqual(line.price, self.si.items[0].rate)
		self.assertEqual(line.amount, self.si.items[0].net_amount)
		self.assertEqual(line.process_type, "1")

	def test_line_tax_matches_the_sales_invoice_rate(self):
		fei = self._create()
		self.assertEqual(fei.lines[0].tax_rate, "10")
		self.assertAlmostEqual(fei.lines[0].tax_amount, self.si.total_taxes_and_charges, places=2)

	def test_an_eight_percent_sales_invoice_becomes_an_invoice(self):
		"""Thuế suất 8% (giảm thuế theo nghị quyết) phải tạo được chứng từ HĐĐT."""
		si = make_sales_invoice(vat_rate=8)

		fei = self._create(si)

		self.assertEqual(fei.lines[0].tax_rate, "8")
		self.assertAlmostEqual(fei.lines[0].tax_amount, si.total_taxes_and_charges, places=2)
		self.assertAlmostEqual(fei.tax_amount, si.total_taxes_and_charges, places=2)

	def test_eight_percent_leaves_the_four_group_boxes_empty(self):
		"""Fast chưa có ô nhóm cho 8% — phần thuế đó nằm ngoài bốn ô, không nhét vào ô 10%."""
		si = make_sales_invoice(vat_rate=8)

		fei = self._create(si)

		self.assertEqual(fei.tax_amount_10, 0)
		self.assertEqual(fei.tax_amount_5, 0)
		self.assertEqual(fei.tax_amount_free, 0)
		self.assertAlmostEqual(fei.tax_amount, si.total_taxes_and_charges, places=2)

	def test_eight_percent_from_an_item_tax_template(self):
		"""8% khai trên Item Tax Template — đường cấu hình một lần cho mặt hàng."""
		si = make_sales_invoice(
			vat_rate=10,
			items=[
				{
					"item_code": ensure_item(),
					"item_name": ITEM_NAME,
					"qty": 100,
					"rate": 100000,
					"item_tax_template": _item_tax_template(8),
				}
			],
		)

		fei = self._create(si)

		self.assertEqual(fei.lines[0].tax_rate, "8")
		self.assertEqual(fei.tax_rate, "8")

	def test_five_and_eight_percent_lines_match_the_sales_invoice(self):
		"""Kịch bản K6 #14: nhiều dòng 5% + 8% — tổng khớp hóa đơn bán, bốn ô nhóm thuế đúng."""
		from erpnext.einvoice.validation import validate_before_send

		item = ensure_item()
		si = make_sales_invoice(
			vat_rate=10,
			items=[
				{
					"item_code": item,
					"item_name": ITEM_NAME,
					"qty": 3,
					"rate": 333_333,
					"item_tax_template": _item_tax_template(5),
				},
				{
					"item_code": item,
					"item_name": ITEM_NAME,
					"qty": 7,
					"rate": 142_857,
					"item_tax_template": _item_tax_template(8),
				},
			],
		)

		fei = self._create(si)

		self.assertEqual([line.tax_rate for line in fei.lines], ["5", "8"])
		self.assertAlmostEqual(fei.tax_amount_5, flt(fei.lines[0].tax_amount), places=2)
		self.assertEqual(fei.tax_amount_10, 0)
		tolerance = len(fei.lines)
		self.assertLessEqual(abs(fei.amount - si.net_total), tolerance)
		self.assertLessEqual(abs(fei.tax_amount - si.total_taxes_and_charges), tolerance)
		self.assertLessEqual(abs(fei.total_amount - si.grand_total), tolerance)
		self.assertNotIn(18, [issue.rule for issue in validate_before_send(fei).issues])

	def test_only_the_output_vat_row_sets_the_rate(self):
		"""Hóa đơn bán có dòng phí đứng trước dòng thuế GTGT: thuế suất không được lấy nhầm từ dòng phí."""
		fee_account = frappe.db.get_value(
			"Account", {"company": COMPANY, "is_group": 0, "account_type": "Chargeable"}, "name"
		) or frappe.db.get_value(
			"Account", {"company": COMPANY, "is_group": 0, "root_type": "Income"}, "name"
		)
		si = make_sales_invoice(
			vat_rate=None,
			taxes=[
				{
					"charge_type": "On Net Total",
					"account_head": fee_account,
					"rate": 2,
					"description": "Phí vận chuyển",
				},
				{
					"charge_type": "On Net Total",
					"account_head": output_vat_account(),
					"rate": 8,
					"description": "Thuế GTGT 8%",
				},
			],
		)

		fei = self._create(si)
		self.assertEqual(fei.tax_rate, "8")
		self.assertEqual(fei.lines[0].tax_rate, "8")

	def test_tax_group_buckets_are_filled(self):
		fei = self._create()
		self.assertAlmostEqual(fei.tax_amount_10, self.si.total_taxes_and_charges, places=2)

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

	def test_sales_invoice_is_stamped_back(self):
		"""Kế toán phải thấy ngay trên hóa đơn bán là đã có chứng từ HĐĐT."""
		self._create()
		self.si.reload()
		self.assertEqual(self.si.fast_einvoice_status, STATUS_DRAFT)

	def test_the_sales_invoice_has_no_link_back(self):
		"""Hai Link trỏ vòng từng làm không xóa được nháp, không hủy được chứng từ nguồn (mục C5)."""
		self.assertFalse(frappe.get_meta("Sales Invoice").has_field("fast_einvoice"))

	def test_the_new_record_passes_validation(self):
		from erpnext.einvoice.validation import validate_before_send

		result = validate_before_send(self._create())
		self.assertTrue(result.ok, [i.message for i in result.blocking])

	# --- Tiền điều kiện của mục E1 ---------------------------------------

	def test_draft_sales_invoice_is_refused(self):
		draft = make_sales_invoice(submit=False)
		with self.assertRaises(frappe.ValidationError):
			create_from_sales_invoice(draft.name)

	def test_return_sales_invoice_is_refused(self):
		"""Kịch bản K6 #17: hóa đơn trả hàng lập điều chỉnh giảm từ hóa đơn gốc, không lập hóa đơn mới."""
		from erpnext.controllers.sales_and_purchase_return import make_return_doc

		returned = make_return_doc("Sales Invoice", self.si.name)
		returned.flags.ignore_permissions = True
		returned.insert()
		returned.submit()
		with self.assertRaisesRegex(frappe.ValidationError, "trả hàng"):
			create_from_sales_invoice(returned.name)

	def test_debit_opening_and_pos_consolidated_invoices_are_refused(self):
		"""Kịch bản K6 #17: số dư đầu kỳ đã có hóa đơn ở hệ thống cũ — xuất lại là trùng."""
		for field, value, words in (
			("is_debit_note", 1, "ghi nợ"),
			("is_opening", "Yes", "số dư đầu kỳ"),
			("is_consolidated", 1, "POS"),
		):
			with self.subTest(field=field):
				si = make_sales_invoice()
				frappe.db.set_value("Sales Invoice", si.name, field, value)
				with self.assertRaisesRegex(frappe.ValidationError, words):
					create_from_sales_invoice(si.name)
				self.assertFalse(frappe.db.exists(FEI, {"sales_invoice": si.name}))

	def test_second_invoice_for_the_same_sales_invoice_is_refused(self):
		"""Kịch bản K6 #20: một hóa đơn bán chỉ được một hóa đơn đang sống."""
		self._create()
		with self.assertRaises(frappe.ValidationError):
			create_from_sales_invoice(self.si.name)

	def test_the_controller_refuses_a_second_record_too(self):
		"""Chốt chống trùng viết theo `sales_invoice` — chốt cũ `if self.delivery_note` tự bỏ qua."""
		first = self._create()
		copy = frappe.copy_doc(first)
		copy.sales_invoice = self.si.name
		copy.fast_key = f"{first.fast_key}-X"
		with self.assertRaises(frappe.DuplicateEntryError):
			copy.insert(ignore_permissions=True)

	def test_a_cancelled_invoice_frees_the_sales_invoice_again(self):
		fei = self._create()
		frappe.db.set_value(FEI, fei.name, "status", STATUS_CANCELLED)

		again = self._create()
		self.assertEqual(again.status, STATUS_DRAFT)

	def test_a_re_raised_invoice_gets_its_own_key(self):
		"""Key cũ đã thuộc hóa đơn bị hủy trên Fast — dùng lại là 370 chặn phát hành."""
		fei = self._create()
		frappe.db.set_value(FEI, fei.name, "status", STATUS_CANCELLED)

		self.assertEqual(self._create().fast_key, f"{fei.fast_key}-L2")

	def test_disabled_integration_refuses(self):
		configure(enabled=0)
		with self.assertRaises(frappe.ValidationError):
			create_from_sales_invoice(self.si.name)

	def test_a_user_who_cannot_read_the_sales_invoice_is_refused(self):
		"""Bản ghi được ghi bỏ qua phân quyền, nên phải kiểm tra quyền đọc chứng từ nguồn."""
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			create_from_sales_invoice(self.si.name)
		frappe.set_user("Administrator")
		self.assertFalse(frappe.db.exists(FEI, {"sales_invoice": self.si.name}))

	def test_source_fields_cannot_be_edited_afterwards(self):
		fei = self._create()
		fei.sales_invoice = make_sales_invoice().name
		with self.assertRaisesRegex(frappe.ValidationError, "chứng từ nguồn"):
			fei.save(ignore_permissions=True)


class TestOneSaleOneInvoiceNumber(FrappeTestCase):
	"""Chốt K5 #1: Key đổi từ tên phiếu giao sang tên hóa đơn bán, nên Fast không nhận ra trùng."""

	def setUp(self):
		frappe.db.rollback()
		configure()
		self.dn = make_delivery_note()
		self.legacy = make_legacy_fei(self.dn.name)
		self.si = make_sales_invoice_from_delivery_note(self.dn.name)

	def tearDown(self):
		frappe.db.rollback()

	def test_a_delivery_note_already_invoiced_under_v2_is_refused(self):
		"""Kịch bản K6 #16: từ chối, nêu tên chứng từ cũ."""
		with self.assertRaisesRegex(frappe.ValidationError, self.legacy):
			create_from_sales_invoice(self.si.name)
		self.assertFalse(frappe.db.exists(FEI, {"sales_invoice": self.si.name}))

	def test_the_sales_invoice_can_be_linked_to_the_old_record(self):
		link_sales_invoice(self.legacy, self.si.name)

		legacy = frappe.get_doc(FEI, self.legacy)
		self.assertEqual(legacy.sales_invoice, self.si.name)
		self.assertEqual(legacy.source_doctype, SOURCE_DELIVERY_NOTE_V2)
		self.assertEqual(legacy.fast_key, fast_key_for(self.dn.name))

	def test_an_issued_old_record_can_still_be_linked(self):
		"""Chính sáu hóa đơn đã phát hành theo bản 2.0 cần hóa đơn bán để bảng kê lấy đúng số."""
		frappe.db.set_value(FEI, self.legacy, {"status": STATUS_TAX_ACCEPTED, "fast_invoice_no": "2"})
		link_sales_invoice(self.legacy, self.si.name)
		self.assertEqual(frappe.db.get_value(FEI, self.legacy, "sales_invoice"), self.si.name)

	def test_a_sales_invoice_from_another_delivery_note_cannot_be_linked(self):
		other = make_sales_invoice()
		with self.assertRaises(frappe.ValidationError):
			link_sales_invoice(self.legacy, other.name)

	def test_the_old_entry_point_answers_with_a_clear_refusal(self):
		"""Kịch bản K6 #21: trình duyệt còn form script cũ vẫn gọi được hàm này."""
		dn = make_delivery_note()
		with self.assertRaisesRegex(frappe.ValidationError, "hóa đơn bán"):
			create_from_delivery_note(dn.name)
		self.assertFalse(frappe.db.exists(FEI, {"delivery_note": dn.name}))


class TestResync(FrappeTestCase):
	def setUp(self):
		frappe.db.rollback()
		configure()
		self.si = make_sales_invoice()
		self.fei = frappe.get_doc(FEI, create_from_sales_invoice(self.si.name))

	def tearDown(self):
		frappe.db.rollback()

	def test_resync_restores_edited_master_data(self):
		self.fei.customer_name = "Tên gõ nhầm"
		self.fei.flags.ignore_links = True
		self.fei.save()

		resync_from_source(self.fei.name)
		self.fei.reload()
		self.assertEqual(self.fei.customer_name, self.si.customer_name)

	def test_resync_rebuilds_the_lines(self):
		self.fei.lines[0].qty = 1
		self.fei.flags.ignore_links = True
		self.fei.save()

		resync_from_source(self.fei.name)
		self.fei.reload()
		self.assertEqual(self.fei.lines[0].qty, self.si.items[0].qty)

	def test_resync_from_a_customer_facing_state_counts_as_a_revision(self):
		"""Đặc tả C2.2 #19: đếm số lần quay về Nháp **từ 02/03/04**."""
		frappe.db.set_value(
			FEI, self.fei.name, {"status": "03 - Chờ khách duyệt", "customer_name": "Tên gõ nhầm"}
		)

		resync_from_source(self.fei.name)
		self.fei.reload()
		self.assertEqual(self.fei.revision_count, 1)
		self.assertEqual(self.fei.status, STATUS_DRAFT)

	def test_resync_of_a_draft_is_not_a_revision(self):
		"""Đang là Nháp mà nạp lại dữ liệu thì chưa có vòng qua lại nào với khách."""
		before = self.fei.revision_count
		resync_from_source(self.fei.name)
		self.fei.reload()
		self.assertEqual(self.fei.revision_count, before)

	def test_resync_never_changes_the_key(self):
		"""Đặc tả A4: Key sinh một lần và không đổi."""
		key = self.fei.fast_key
		resync_from_source(self.fei.name)
		self.fei.reload()
		self.assertEqual(self.fei.fast_key, key)

	def test_resync_returns_an_approved_invoice_to_draft(self):
		frappe.db.set_value(
			FEI, self.fei.name, {"status": "04 - Khách đã duyệt", "customer_name": "Tên gõ nhầm"}
		)
		resync_from_source(self.fei.name)
		self.fei.reload()
		self.assertEqual(self.fei.status, STATUS_DRAFT)

	def test_resync_is_refused_once_the_invoice_is_issued(self):
		frappe.db.set_value(FEI, self.fei.name, "status", STATUS_ISSUED)
		with self.assertRaises(frappe.ValidationError):
			resync_from_source(self.fei.name)

	def test_resync_is_refused_after_the_tax_office_accepted(self):
		frappe.db.set_value(FEI, self.fei.name, "status", STATUS_TAX_ACCEPTED)
		with self.assertRaises(frappe.ValidationError):
			resync_from_source(self.fei.name)

	def test_resync_without_changes_keeps_status(self):
		"""Q7-2: không có gì đổi thì không đưa về Nháp — khách không phải duyệt lại vô cớ."""
		frappe.db.set_value(FEI, self.fei.name, "status", "03 - Chờ khách duyệt")

		result = resync_from_source(self.fei.name)

		self.fei.reload()
		self.assertEqual(result["changed"], [])
		self.assertIn("đã khớp", result["message"])
		self.assertEqual(self.fei.status, "03 - Chờ khách duyệt")
		self.assertEqual(self.fei.revision_count, 0)

	def test_resync_reports_the_changed_email(self):
		frappe.db.set_value(FEI, self.fei.name, "email_deliver", "nham@bvx.vn")

		result = resync_from_source(self.fei.name)

		self.assertEqual(len(result["changed"]), 1)
		self.assertIn("Email nhận hóa đơn", result["changed"][0])
		self.assertIn("nham@bvx.vn", result["changed"][0])
		self.assertIn("Email nhận hóa đơn", result["message"])

	def test_resync_reports_changed_lines(self):
		frappe.db.set_value("Fast EInvoice Line", self.fei.lines[0].name, "qty", 1)

		result = resync_from_source(self.fei.name)

		self.assertTrue(any(change.startswith("Dòng hàng") for change in result["changed"]))

	def test_resync_ignores_the_invoice_date(self):
		"""Ngày hóa đơn luôn về hôm nay — đưa vào danh sách chỉ gây nhiễu."""
		frappe.db.set_value(FEI, self.fei.name, "invoice_date", "2026-01-01")
		self.assertEqual(resync_from_source(self.fei.name)["changed"], [])

	def test_resync_saves_even_when_the_source_lost_the_address(self):
		"""Q7: thiếu trường bắt buộc không chặn đồng bộ — lỗi hiện ở bảng kiểm tra dữ liệu."""
		from unittest.mock import patch

		with patch("erpnext.einvoice.builder._billing_address", return_value=""):
			result = resync_from_source(self.fei.name)

		self.fei.reload()
		self.assertTrue(result["ok"])
		self.assertEqual(self.fei.address or "", "")

	def test_resync_is_refused_while_reconciling(self):
		"""Q7-1: ở 98 chưa biết Fast đã ra số chưa — phải truy vấn 370 trước."""
		frappe.db.set_value(FEI, self.fei.name, "status", STATUS_NEEDS_RECONCILE)
		with self.assertRaises(frappe.ValidationError):
			resync_from_source(self.fei.name)

	def test_a_v2_draft_still_resyncs_from_its_delivery_note(self):
		legacy = make_legacy_fei()
		frappe.db.set_value(FEI, legacy, "customer_name", "Tên gõ nhầm")

		resync_from_source(legacy)
		self.assertNotEqual(frappe.db.get_value(FEI, legacy, "customer_name"), "Tên gõ nhầm")


class TestCancellingTheSalesInvoice(FrappeTestCase):
	"""Mục E1.1 / kịch bản K6 #18 — hai hook hủy của Sales Invoice.

	Bộ test `sales_invoice` của lõi không chạy được trên site này, nên đây là lưới
	duy nhất bắt lỗi do hai hook này gây ra.
	"""

	def setUp(self):
		frappe.db.rollback()
		configure()
		self.si = make_sales_invoice()
		self.fei = create_from_sales_invoice(self.si.name)

	def tearDown(self):
		frappe.db.rollback()

	def _cancel(self):
		si = frappe.get_doc("Sales Invoice", self.si.name)
		si.flags.ignore_permissions = True
		si.cancel()
		return si

	def test_an_invoice_accepted_by_the_tax_office_blocks_the_cancel(self):
		frappe.db.set_value(FEI, self.fei, {"status": STATUS_TAX_ACCEPTED, "fast_invoice_no": "2"})
		with self.assertRaisesRegex(frappe.ValidationError, "điều chỉnh hoặc thay thế"):
			self._cancel()
		self.assertEqual(frappe.db.get_value("Sales Invoice", self.si.name, "docstatus"), 1)

	def test_an_invoice_whose_fate_is_unknown_blocks_the_cancel(self):
		"""05 / 98: chưa rõ đã tiêu số hay chưa — hủy chứng từ ghi doanh thu lúc này là đánh cược."""
		frappe.db.set_value(FEI, self.fei, "status", "98 - Cần đối soát")
		with self.assertRaises(frappe.ValidationError):
			self._cancel()

	def test_a_draft_does_not_block_the_cancel(self):
		si = self._cancel()
		self.assertEqual(si.docstatus, 2)
		self.assertTrue(frappe.db.exists(FEI, self.fei))
		self.assertFalse(frappe.db.get_value("Sales Invoice", self.si.name, "fast_einvoice_status"))

	def test_an_internally_cancelled_invoice_does_not_lock_the_sales_invoice(self):
		"""Hóa đơn CQT từ chối rồi hủy nội bộ: phải cho hủy và sửa lại hóa đơn bán."""
		frappe.db.set_value(FEI, self.fei, {"status": STATUS_CANCELLED, "fast_invoice_no": "2"})
		self.assertEqual(self._cancel().docstatus, 2)

	def test_the_sales_invoice_check_is_rule_15_once_cancelled(self):
		from erpnext.einvoice.validation import validate_before_send

		self._cancel()
		blocked = [i.rule for i in validate_before_send(frappe.get_doc(FEI, self.fei)).blocking]
		self.assertIn(15, blocked)


class TestNoInvoiceNumberIsCopiedAcross(FrappeTestCase):
	"""Kịch bản K6 #19: lõi chép mọi trường trùng tên — custom field phải `no_copy`."""

	def setUp(self):
		frappe.db.rollback()
		configure()

	def tearDown(self):
		frappe.db.rollback()

	def _stamp(self, doctype, name):
		frappe.db.set_value(
			doctype,
			name,
			{"fast_invoice_no": "2", "fast_einvoice_status": STATUS_ISSUED, "fast_key_search": "KS"},
		)

	def test_a_sales_invoice_made_from_a_delivery_note(self):
		dn = make_delivery_note()
		self._stamp("Delivery Note", dn.name)
		si = make_sales_invoice_from_delivery_note(dn.name, submit=False)
		self.assertFalse(si.get("fast_invoice_no"))
		self.assertFalse(si.get("fast_einvoice_status"))

	def test_a_return_against_the_sales_invoice(self):
		from erpnext.controllers.sales_and_purchase_return import make_return_doc

		si = make_sales_invoice()
		self._stamp("Sales Invoice", si.name)
		returned = make_return_doc("Sales Invoice", si.name)
		self.assertFalse(returned.get("fast_invoice_no"))
		self.assertFalse(returned.get("fast_key_search"))

	def test_an_amended_sales_invoice(self):
		si = make_sales_invoice()
		self._stamp("Sales Invoice", si.name)
		# Nút Amend tôn trọng no_copy — `frappe.copy_doc` mặc định thì không.
		amended = frappe.copy_doc(frappe.get_doc("Sales Invoice", si.name), ignore_no_copy=False)
		self.assertFalse(amended.get("fast_invoice_no"))
		self.assertFalse(amended.get("fast_einvoice_status"))

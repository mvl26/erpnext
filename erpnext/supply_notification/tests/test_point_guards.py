# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Điều kiện khoá của các điểm hạt giống — một chứng từ có nhiều nghĩa nghiệp vụ.

Nền của bộ test này: `Purchase Receipt` cũng là phiếu **trả hàng**, `Delivery Note`
cũng là phiếu **nhận lại hàng trả**, `Payment Entry` là cửa chung của mọi dòng
tiền. Điểm chỉ lọc theo loại chứng từ sẽ bắn sai ngữ cảnh — và với NTF-07 thì bắn
sai nghĩa là **gửi thư cho khách**.

Tham chiếu: docs/BA_ThongBao_PaymentEntry_20261006.md
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.supply_notification import conditions, constants

#: Điều kiện bắt buộc phải có trên từng điểm hạt giống, sau patch
#: `v15_0.khoa_dieu_kien_diem_thong_bao`.
REQUIRED_GUARDS = {
	"NTF-04": {("is_return", "=", "0")},
	"NTF-05": {("is_return", "=", "0")},
	"NTF-06": {("outstanding_amount", ">", "0"), ("on_hold", "=", "0")},
	"NTF-07": {("is_return", "=", "0")},
	"NTF-10": {("payment_type", "=", "Pay"), ("references.reference_doctype", "=", "Purchase Invoice")},
	"NTF-12": {("payment_type", "=", "Receive"), ("references.reference_doctype", "=", "Sales Invoice")},
}


def doc_of(doctype, children=(), **values):
	doc = frappe.new_doc(doctype)
	doc.update(values)
	for fieldname, row in children:
		doc.append(fieldname, row)
	return doc


class TestSeedGuards(FrappeTestCase):
	def test_every_guarded_point_carries_its_conditions_on_site(self):
		for code, required in REQUIRED_GUARDS.items():
			point = frappe.get_doc("Supply Notification Point", code)
			have = {(row.fieldname, row.operator, row.value) for row in point.conditions}
			self.assertTrue(
				required <= have,
				f"{code} thiếu điều kiện khoá: {required - have}",
			)

	def test_seed_data_matches_what_the_site_has(self):
		"""Site mới gieo từ hạt giống phải ra đúng bộ điều kiện như site đang chạy."""
		for code, required in REQUIRED_GUARDS.items():
			spec = constants.SEED_POINTS_BY_CODE[code]
			self.assertTrue(
				required <= set(spec["conditions"]),
				f"hạt giống {code} thiếu: {required - set(spec['conditions'])}",
			)


class TestReturnDocumentsAreExcluded(FrappeTestCase):
	def test_purchase_return_does_not_fire_the_receipt_point(self):
		point = frappe.get_doc("Supply Notification Point", "NTF-04")

		self.assertTrue(conditions.match(point, doc_of("Purchase Receipt", is_return=0)))
		self.assertFalse(conditions.match(point, doc_of("Purchase Receipt", is_return=1)))

	def test_debit_note_does_not_fire_the_purchase_invoice_point(self):
		point = frappe.get_doc("Supply Notification Point", "NTF-05")

		self.assertTrue(conditions.match(point, doc_of("Purchase Invoice", is_return=0)))
		self.assertFalse(conditions.match(point, doc_of("Purchase Invoice", is_return=1)))

	def test_sales_return_does_not_mail_the_customer(self):
		"""NTF-07 gửi thư ra ngoài — bắn sai ở đây là khách nhận thư sai."""
		point = frappe.get_doc("Supply Notification Point", "NTF-07")

		self.assertTrue(conditions.match(point, doc_of("Delivery Note", is_return=0)))
		self.assertFalse(conditions.match(point, doc_of("Delivery Note", is_return=1)))

	def test_an_untouched_checkbox_still_counts_as_zero(self):
		"""Ô tích chưa bao giờ chạm có thể là NULL — vẫn phải khớp `= 0`."""
		point = frappe.get_doc("Supply Notification Point", "NTF-04")
		receipt = doc_of("Purchase Receipt")
		receipt.is_return = None

		self.assertTrue(conditions.match(point, receipt))


class TestInvoiceOnHold(FrappeTestCase):
	def test_invoice_on_hold_is_not_chased_for_payment(self):
		point = frappe.get_doc("Supply Notification Point", "NTF-06")
		base = {"outstanding_amount": 1000}

		self.assertTrue(conditions.match(point, doc_of("Purchase Invoice", on_hold=0, **base)))
		self.assertFalse(conditions.match(point, doc_of("Purchase Invoice", on_hold=1, **base)))


class TestPaymentEntryGuards(FrappeTestCase):
	"""Quyết định PO 06/10/2026: khoá bằng chứng từ nguồn độc quyền."""

	def payment(self, payment_type, party_type=None, refs=()):
		return doc_of(
			"Payment Entry",
			children=[("references", {"reference_doctype": dt, "reference_name": "X-01"}) for dt in refs],
			payment_type=payment_type,
			party_type=party_type,
		)

	def test_supplier_payment_point_fires_only_for_purchase_invoices(self):
		point = frappe.get_doc("Supply Notification Point", "NTF-10")

		self.assertTrue(conditions.match(point, self.payment("Pay", "Supplier", ["Purchase Invoice"])))
		self.assertFalse(conditions.match(point, self.payment("Pay", "Employee", ["Expense Claim"])))
		self.assertFalse(conditions.match(point, self.payment("Pay", "Shareholder", ["Journal Entry"])))
		self.assertFalse(conditions.match(point, self.payment("Internal Transfer")))

	def test_customer_receipt_point_fires_only_for_sales_invoices(self):
		point = frappe.get_doc("Supply Notification Point", "NTF-12")

		self.assertTrue(conditions.match(point, self.payment("Receive", "Customer", ["Sales Invoice"])))
		self.assertFalse(conditions.match(point, self.payment("Receive", "Employee", ["Employee Advance"])))
		self.assertFalse(conditions.match(point, self.payment("Receive", "Customer", [])))

	def test_a_payment_mixing_invoice_and_journal_entry_still_fires(self):
		"""Phiếu chi gộp hoá đơn + bút toán vẫn là chi NCC."""
		point = frappe.get_doc("Supply Notification Point", "NTF-10")

		self.assertTrue(
			conditions.match(point, self.payment("Pay", "Supplier", ["Purchase Invoice", "Journal Entry"]))
		)

	def test_the_guard_value_is_not_an_impossible_one(self):
		"""Gõ nhầm 'Sales Invoice' vào điểm chi NCC làm điểm im lặng vĩnh viễn."""
		for code, impossible in (
			("NTF-10", {"Sales Invoice", "Sales Order", "Dunning"}),
			("NTF-12", {"Purchase Invoice", "Purchase Order"}),
		):
			point = frappe.get_doc("Supply Notification Point", code)
			values = {
				row.value for row in point.conditions if row.fieldname == "references.reference_doctype"
			}
			self.assertFalse(
				values & impossible,
				f"{code} đang lọc theo chứng từ không bao giờ xuất hiện: {values & impossible}",
			)

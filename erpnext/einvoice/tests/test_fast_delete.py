# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Xóa chứng từ HĐĐT và hủy phiếu giao — gỡ vòng tham chiếu.

`Fast EInvoice Document.delivery_note` và custom field `Delivery Note.fast_einvoice`
là hai Link trỏ vòng vào nhau, còn `Fast EInvoice Log.fei_document` là mắt xích
thứ ba. Mặc định Frappe từ chối xóa **cả ba** đầu, không lối ra nào ngoài `force`.

Ranh giới đúng không nằm ở "có ai trỏ tới không" mà ở **hóa đơn đã tiêu số thật
hay chưa**: chưa phát hành thì xóa/hủy thoải mái, đã phát hành thì chặn kèm lời
giải thích và lối đi đúng.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.einvoice.builder import create_from_delivery_note
from erpnext.einvoice.constants import STATUS_DRAFT, STATUS_ISSUED, STATUS_TAX_ACCEPTED
from erpnext.einvoice.tests.test_fast_client import configure
from erpnext.einvoice.tests.test_fast_log import make_log
from erpnext.einvoice.tests.test_fixtures import make_delivery_note

FEI = "Fast EInvoice Document"
LOG = "Fast EInvoice Log"
DN = "Delivery Note"


class DeleteBase(FrappeTestCase):
	def setUp(self):
		frappe.db.rollback()
		configure()
		self.dn = make_delivery_note()
		self.fei = create_from_delivery_note(self.dn.name)

	def tearDown(self):
		frappe.db.rollback()

	def issue_it(self, status=STATUS_ISSUED, invoice_no="7"):
		frappe.db.set_value(FEI, self.fei, {"status": status, "fast_invoice_no": invoice_no})

	def cancel_delivery_note(self):
		doc = frappe.get_doc(DN, self.dn.name)
		doc.flags.ignore_permissions = True
		doc.cancel()


class TestDeletingAnInvoiceDocument(DeleteBase):
	def test_a_draft_deletes_even_though_the_delivery_note_points_back(self):
		"""Vòng Link hai chiều không được biến bản nháp thành thứ không xóa nổi."""
		self.assertEqual(frappe.db.get_value(DN, self.dn.name, "fast_einvoice"), self.fei)

		frappe.delete_doc(FEI, self.fei)

		self.assertFalse(frappe.db.exists(FEI, self.fei))

	def test_a_draft_deletes_even_though_log_rows_point_at_it(self):
		"""Nhật ký là vết kiểm toán, không phải quan hệ khóa được chứng từ."""
		make_log(fei_document=self.fei)

		frappe.delete_doc(FEI, self.fei)

		self.assertFalse(frappe.db.exists(FEI, self.fei))

	def test_deleting_clears_the_stamp_on_the_delivery_note(self):
		frappe.delete_doc(FEI, self.fei)

		stamp = frappe.db.get_value(
			DN, self.dn.name, ["fast_einvoice", "fast_einvoice_status", "fast_invoice_no"], as_dict=True
		)
		self.assertFalse(stamp.fast_einvoice)
		self.assertFalse(stamp.fast_einvoice_status)
		self.assertFalse(stamp.fast_invoice_no)

	def test_deleting_takes_its_own_log_rows_with_it(self):
		"""Không để lại hàng mồ côi trỏ tới một bản ghi không còn tồn tại."""
		make_log(fei_document=self.fei)
		other = make_log(fei_document=None)

		frappe.delete_doc(FEI, self.fei)

		self.assertEqual(frappe.get_all(LOG, filters={"fei_document": self.fei}), [])
		self.assertTrue(frappe.db.exists(LOG, other.name), "log của chứng từ khác không được đụng tới")

	def test_it_leaves_alone_a_delivery_note_pointing_at_another_document(self):
		"""Phiếu giao đang trỏ chứng từ khác thì xóa cái này không được xóa dấu của cái kia."""
		frappe.db.set_value(DN, self.dn.name, "fast_einvoice", "FEI-KHAC", update_modified=False)

		frappe.delete_doc(FEI, self.fei)

		self.assertEqual(frappe.db.get_value(DN, self.dn.name, "fast_einvoice"), "FEI-KHAC")

	def test_an_issued_invoice_cannot_be_deleted(self):
		"""Hóa đơn đã tiêu số là chứng từ pháp lý — xóa bản ghi chỉ làm mất dấu vết."""
		self.issue_it()

		with self.assertRaises(frappe.PermissionError):
			frappe.delete_doc(FEI, self.fei)

		self.assertTrue(frappe.db.exists(FEI, self.fei))

	def test_the_refusal_names_the_way_out(self):
		self.issue_it()

		with self.assertRaises(frappe.PermissionError) as caught:
			frappe.delete_doc(FEI, self.fei)

		self.assertIn("điều chỉnh", str(caught.exception))


class TestCancellingTheDeliveryNote(DeleteBase):
	def test_a_draft_invoice_does_not_block_cancelling(self):
		"""Hủy phiếu giao là việc bình thường của kho — một bản nháp không được chặn."""
		self.cancel_delivery_note()

		self.assertEqual(frappe.db.get_value(DN, self.dn.name, "docstatus"), 2)

	def test_cancelling_clears_the_stamp(self):
		self.cancel_delivery_note()

		self.assertFalse(frappe.db.get_value(DN, self.dn.name, "fast_einvoice"))

	def test_an_issued_invoice_blocks_cancelling(self):
		self.issue_it(status=STATUS_TAX_ACCEPTED, invoice_no="9")

		with self.assertRaises(frappe.ValidationError):
			self.cancel_delivery_note()

		self.assertEqual(frappe.db.get_value(DN, self.dn.name, "docstatus"), 1)

	# Thông báo phải nói rõ hóa đơn nào và lối đi đúng, chứ không phải
	# LinkExistsError trần trụi của Frappe.
	def test_the_refusal_names_the_invoice_and_the_way_out(self):
		self.issue_it(status=STATUS_TAX_ACCEPTED, invoice_no="9")

		with self.assertRaises(frappe.ValidationError) as caught:
			self.cancel_delivery_note()

		message = str(caught.exception)
		self.assertIn(self.fei, message)
		self.assertIn("điều chỉnh", message)

	def test_a_deleted_draft_leaves_nothing_blocking_the_cancel(self):
		"""Đường đi trọn vẹn: xóa bản nháp rồi hủy phiếu giao."""
		frappe.delete_doc(FEI, self.fei)

		self.cancel_delivery_note()

		self.assertEqual(frappe.db.get_value(DN, self.dn.name, "docstatus"), 2)
		self.assertEqual(frappe.db.get_value(FEI, self.fei, "status"), None)
		# Bản nháp biến mất, phiếu giao hủy được, không còn gì trỏ tới nhau.
		self.assertEqual(frappe.db.get_value(DN, self.dn.name, "status"), "Cancelled")


class TestDraftStatusIsWhatMakesItDeletable(DeleteBase):
	def test_an_error_document_is_still_deletable(self):
		"""Chứng từ lỗi chưa tiêu số nào — phải dọn được."""
		frappe.db.set_value(FEI, self.fei, {"status": "99 - Lỗi", "error_code": "836"})

		frappe.delete_doc(FEI, self.fei)

		self.assertFalse(frappe.db.exists(FEI, self.fei))

	def test_an_invoice_number_alone_is_enough_to_refuse(self):
		"""Trạng thái có thể bị sửa tay; số hóa đơn thì không nói dối được."""
		frappe.db.set_value(FEI, self.fei, {"status": STATUS_DRAFT, "fast_invoice_no": "12"})

		with self.assertRaises(frappe.PermissionError):
			frappe.delete_doc(FEI, self.fei)

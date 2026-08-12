# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Chứng từ hóa đơn điện tử Fast — vòng đời 14 trạng thái của bảng B2.

`is_submittable = 0`: vòng đời hóa đơn không khớp mô hình Draft/Submitted/
Cancelled của Frappe, nên trạng thái do trường ``status`` tự quản lý và việc
khóa sửa dựa trên trạng thái chứ không dựa trên docstatus.
"""

import frappe
from frappe import _
from frappe.model.document import Document

from erpnext.einvoice.constants import (
	EDITABLE_STATUSES,
	INVOICE_TYPE_ADJUSTMENT,
	INVOICE_TYPE_ORIGINAL,
	INVOICE_TYPE_REPLACEMENT,
	STATUS_DRAFT,
)

# Dữ liệu sẽ gửi lên Fast (nhóm C2.3). Khi hóa đơn đã tiêu số thật thì đây là nội
# dung của một chứng từ pháp lý — sửa được nghĩa là chứng từ trên ERP lệch với
# chứng từ Cơ quan Thuế đang giữ.
PROTECTED_MASTER_FIELDS = (
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
	"id_card_no",
	"passport_no",
	"buyer_unit",
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
	"deduction_amount",
	"deduction_amount_other",
	"amount_in_words",
	"human_name",
	"release_type",
	"delivery_note",
	"invoice_type",
)

PROTECTED_LINE_FIELDS = (
	"process_type",
	"item_code",
	"item_name",
	"uom",
	"is_promotion",
	"qty",
	"price",
	"amount",
	"discount_rate",
	"discount_amount",
	"tax_rate",
	"tax_amount",
	"note",
)


# Loại tiền lấy 0 chữ số thập phân (đồng nguyên) — VND/JPY; còn lại 2 chữ số.
_ZERO_DECIMAL_CURRENCIES = frozenset({"VND", "JPY"})


def _amount_precision(currency):
	return 0 if (currency or "VND").upper() in _ZERO_DECIMAL_CURRENCIES else 2


def _dominant_tax_rate(lines):
	"""Thuế suất ghi ở master = thuế suất của phần lớn tiền hàng."""
	from frappe.utils import flt

	totals = {}
	for line in lines or []:
		totals[line.tax_rate] = totals.get(line.tax_rate, 0) + flt(line.amount)
	return max(totals, key=totals.get) if totals else "0"


class FastEInvoiceDocument(Document):
	def validate(self):
		if not self.status:
			self.status = STATUS_DRAFT
		self.is_edit_locked = 0 if self.status in EDITABLE_STATUSES else 1

		# Chỉ tính lại khi còn sửa được. Hóa đơn đã phát hành là chứng từ pháp lý —
		# số liệu đóng băng, tính lại là làm sai lệch bản đã lên Cơ quan Thuế.
		if not self.is_edit_locked:
			self._compute_totals()

		self._validate_fast_key_is_immutable()
		self._validate_lineage()
		self._guard_locked_data()

	def _compute_totals(self):
		"""Tính lại dòng hàng và tổng hợp từ số lượng / đơn giá / thuế suất.

		Chứng từ tự tính như hóa đơn thật, không chỉ giữ số copy: sửa một dòng thì
		thành tiền, tiền thuế, các nhóm thuế, tổng thanh toán và số tiền bằng chữ
		đều cập nhật theo, và luôn khớp nhau (không còn dựa vào việc nhập tay đúng).
		"""
		from frappe.utils import flt

		from erpnext.einvoice.constants import NUMERIC_TAX_RATES
		from erpnext.einvoice.payload import amount_in_words_for, compute_tax_groups

		precision = _amount_precision(self.currency)

		amount = 0.0
		tax = 0.0
		for line in self.lines or []:
			gross = flt(line.qty) * flt(line.price)
			if flt(line.discount_rate):
				line.discount_amount = flt(gross * flt(line.discount_rate) / 100.0, precision)
			line.amount = flt(gross - flt(line.discount_amount), precision)

			rate = NUMERIC_TAX_RATES.get((line.tax_rate or "").strip())
			line.tax_amount = flt(line.amount * rate / 100.0, precision) if rate else 0.0

			amount += line.amount
			tax += line.tax_amount

		self.amount = flt(amount, precision)
		self.tax_amount = flt(tax, precision)

		groups = compute_tax_groups(self.lines or [])
		self.tax_amount_free = flt(groups["tax_amount_free"], precision)
		self.tax_amount_0 = flt(groups["tax_amount_0"], precision)
		self.tax_amount_5 = flt(groups["tax_amount_5"], precision)
		self.tax_amount_10 = flt(groups["tax_amount_10"], precision)

		deductions = flt(self.deduction_amount) + flt(self.deduction_amount_other)
		self.total_amount = flt(self.amount + self.tax_amount - deductions, precision)

		self.tax_rate = _dominant_tax_rate(self.lines)
		if self.total_amount and self.currency:
			self.amount_in_words = amount_in_words_for(self.total_amount, self.currency)

	def _validate_fast_key_is_immutable(self):
		"""Đặc tả A4: Key sinh một lần và không đổi.

		Đổi Key trên bản ghi đã gửi đi làm mất khả năng truy vấn 370 để biết hóa
		đơn đã phát hành hay chưa — đúng cái sinh ra lỗi 809/835 phát hành trùng.
		"""
		if self.is_new():
			return
		before = self.get_doc_before_save()
		if before and before.fast_key and before.fast_key != self.fast_key:
			frappe.throw(
				_(
					"Không được đổi Key ({0}) sau khi bản ghi đã tồn tại — đây là mã chống phát hành trùng."
				).format(before.fast_key)
			)

	def _validate_lineage(self):
		"""Hóa đơn điều chỉnh / thay thế phải chỉ rõ hóa đơn gốc và lý do (C2.1)."""
		if self.invoice_type == INVOICE_TYPE_ORIGINAL:
			return

		missing = []
		if not self.original_document:
			missing.append(_("Hóa đơn gốc"))
		if not self.adjustment_reason:
			missing.append(_("Lý do điều chỉnh / thay thế"))
		if self.invoice_type == INVOICE_TYPE_ADJUSTMENT and not self.adjustment_type:
			missing.append(_("Loại điều chỉnh"))
		if missing:
			frappe.throw(
				_("{0} cần có: {1}").format(self.invoice_type, ", ".join(missing)),
				frappe.MandatoryError,
			)

		if self.original_document == self.name:
			frappe.throw(_("Hóa đơn không thể điều chỉnh hoặc thay thế chính nó."))

	def _guard_locked_data(self):
		"""Chặn sửa dữ liệu khi hóa đơn đã rời khỏi vùng còn sửa được (bảng B2).

		``read_only_depends_on`` chỉ khóa ở giao diện. Đây là chốt phía server để
		sửa qua API, script hay import cũng không lọt. Các hàm chuyển trạng thái
		của luồng nghiệp vụ đặt cờ ``ignore_status_lock`` để đi qua.
		"""
		if self.is_new() or self.flags.get("ignore_status_lock"):
			return
		before = self.get_doc_before_save()
		if not before or before.status in EDITABLE_STATUSES:
			return

		changed = [f for f in PROTECTED_MASTER_FIELDS if self.get(f) != before.get(f)]
		if self._lines_changed(before):
			changed.append(_("dòng hàng"))
		if changed:
			frappe.throw(
				_(
					"Hóa đơn đang ở trạng thái <b>{0}</b> nên không sửa được dữ liệu ({1}). "
					"Muốn thay đổi phải lập hóa đơn điều chỉnh hoặc thay thế."
				).format(before.status, ", ".join(changed))
			)

	def _lines_changed(self, before):
		def snapshot(doc):
			return [
				tuple(row.get(fieldname) for fieldname in PROTECTED_LINE_FIELDS) for row in (doc.lines or [])
			]

		return snapshot(self) != snapshot(before)

	@property
	def is_replacement(self):
		return self.invoice_type == INVOICE_TYPE_REPLACEMENT

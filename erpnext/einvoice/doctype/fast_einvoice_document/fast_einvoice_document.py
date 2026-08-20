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

# Không gửi lên Fast, nhưng đổi hai trường này là đổi cách số tiền hình thành —
# nên chứng từ đã khóa cũng phải chặn y như chặn số tiền.
PROTECTED_CONTROL_FIELDS = ("totals_manual_override", "override_reason")


def _frozen_values(doc):
	"""Giá trị các trường đóng băng, quy về cùng một dạng để so sánh được.

	Chứng từ do giao diện gửi lên đi qua JSON nên Date là chuỗi ``"2026-08-12"``,
	còn bản nạp từ cơ sở dữ liệu là ``datetime.date``. So thẳng thì trường ngày
	luôn "khác" kể cả khi không ai đụng tới — chứng từ đã khóa sẽ không lưu nổi
	dù chỉ ghi thêm số biên bản, và thông báo lỗi đổ oan cho ``invoice_date``.
	"""
	master = doc.get_valid_dict(convert_dates_to_str=True)
	lines = [row.get_valid_dict(convert_dates_to_str=True) for row in (doc.lines or [])]
	return (
		{field: master.get(field) for field in (*PROTECTED_MASTER_FIELDS, *PROTECTED_CONTROL_FIELDS)},
		[tuple(row.get(field) for field in PROTECTED_LINE_FIELDS) for row in lines],
	)


class FastEInvoiceDocument(Document):
	def validate(self):
		if not self.status:
			self.status = STATUS_DRAFT
		self.is_edit_locked = 0 if self.status in EDITABLE_STATUSES else 1

		self._validate_manual_override()
		self._compute_totals()
		self._validate_fast_key_is_immutable()
		self._validate_lineage()
		self._guard_locked_data()

	def _compute_totals(self):
		"""Tính lại dòng hàng và tổng hợp — công thức nằm ở `einvoice.totals`.

		Chứng từ tự tính như hóa đơn thật, không chỉ giữ số copy của phiếu giao:
		sửa hay thêm một dòng thì thành tiền, tiền thuế, các ô nhóm thuế, chiết
		khấu, khuyến mại, tổng thanh toán và số tiền bằng chữ đều đổi theo và luôn
		khớp nhau. Phiếu giao đã submit không sửa được, nên đây là chỗ duy nhất
		sửa được nội dung hóa đơn trước lúc phát hành.

		Hai trường hợp **không** tính:

		- hóa đơn đã rời vùng còn sửa được: số liệu là chứng từ pháp lý đã lên Cơ
		  quan Thuế, tính lại là làm nó lệch với bản Thuế đang giữ;
		- kế toán đang ghi đè số tổng hợp bằng tay.
		"""
		if self.is_edit_locked or self.totals_manual_override:
			return

		from erpnext.einvoice.totals import compute_document_totals

		compute_document_totals(self)

	def _validate_manual_override(self):
		"""Ghi đè số tổng hợp phải nói rõ vì sao.

		Đây là con đường duy nhất để số trên chứng từ khác số công thức tính ra.
		Không có lý do ghi lại thì ba tháng sau không ai giải thích được với cơ
		quan thuế vì sao hóa đơn này không khớp dòng hàng của chính nó.
		"""
		if not self.totals_manual_override:
			self.override_reason = None
			return

		if not (self.override_reason or "").strip():
			frappe.throw(
				_("Ghi đè số tổng hợp bằng tay thì phải ghi lý do."),
				frappe.MandatoryError,
			)

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

		mine_master, mine_lines = _frozen_values(self)
		their_master, their_lines = _frozen_values(before)

		changed = [f for f in PROTECTED_MASTER_FIELDS if mine_master.get(f) != their_master.get(f)]
		if mine_lines != their_lines:
			changed.append(_("dòng hàng"))
		if changed:
			frappe.throw(
				_(
					"Hóa đơn đang ở trạng thái <b>{0}</b> nên không sửa được dữ liệu ({1}). "
					"Muốn thay đổi phải lập hóa đơn điều chỉnh hoặc thay thế."
				).format(before.status, ", ".join(changed))
			)

	@property
	def is_replacement(self):
		return self.invoice_type == INVOICE_TYPE_REPLACEMENT

# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Kiểm tra dữ liệu trước khi gửi Fast — 16 quy tắc Phần F.

Chạy ở ba thời điểm (mục F): khi tạo bản ghi (chỉ cảnh báo), khi xem bản nháp,
và **bắt buộc lại phía server ngay trước khi phát hành** — không tin dữ liệu do
client gửi lên.

Mỗi quy tắc chặn được ở đây là một lời gọi hỏng tiết kiệm được với Fast; với
lệnh phát hành thì còn là một số hóa đơn không bị tiêu oan.
"""

import re
import unicodedata
from dataclasses import dataclass, field

import frappe
from frappe import _
from frappe.utils import flt, getdate

from erpnext.einvoice.constants import (
	INVOICE_TYPE_ORIGINAL,
	ISSUED_STATUSES,
	LIVE_STATUSES,
	MAX_LEN,
	MAX_LINES_PER_INVOICE,
	TAX_RATE_CODES,
)
from erpnext.einvoice.payload import (
	CURRENCY_WORDS,
	compute_tax_groups,
	mst_check_digit_ok,
	normalize_tax_code,
)

BLOCK = "block"
WARN = "warn"

# Sai lệch nhỏ hơn mức này coi như bằng nhau (làm tròn tiền tệ).
AMOUNT_TOLERANCE = 1.0

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Trường text sẽ nằm trong XML envelope — xuống dòng là lỗi 825.
_MASTER_TEXT_FIELDS = (
	"buyer",
	"customer_name",
	"address",
	"phone_number",
	"fax_number",
	"email_deliver",
	"bank_account",
	"bank_name",
	"amount_in_words",
	"human_name",
	"external_1",
	"external_2",
	"external_3",
)


@dataclass
class Issue:
	rule: int
	level: str
	field: str
	message: str


@dataclass
class ValidationResult:
	issues: list = field(default_factory=list)

	def add(self, rule, level, field_name, message):
		self.issues.append(Issue(rule=rule, level=level, field=field_name, message=message))

	@property
	def blocking(self):
		return [i for i in self.issues if i.level == BLOCK]

	@property
	def warnings(self):
		return [i for i in self.issues if i.level == WARN]

	@property
	def ok(self):
		"""Chỉ lỗi mức chặn mới ngăn gửi đi; cảnh báo thì cho qua."""
		return not self.blocking

	def as_dict(self):
		return {
			"ok": self.ok,
			"issues": [
				{"rule": i.rule, "level": i.level, "field": i.field, "message": i.message}
				for i in self.issues
			],
		}

	def throw_if_blocking(self):
		if self.ok:
			return
		lines = "".join(f"<li>{frappe.utils.escape_html(i.message)}</li>" for i in self.blocking)
		frappe.throw(
			_("Dữ liệu hóa đơn chưa hợp lệ, không gửi sang Fast:<ul>{0}</ul>").format(lines),
			title=_("Kiểm tra dữ liệu"),
		)


def validate_before_send(fei, check_source=True):
	"""Chạy toàn bộ Phần F. Thuần túy đọc — không sửa gì trên chứng từ."""
	result = ValidationResult()

	_rule_1_key(fei, result)
	_rule_2_buyer_identity(fei, result)
	_rule_3_tax_code(fei, result)
	_rule_4_id_card(fei, result)
	_rule_5_amount_in_words(fei, result)
	_rule_6_newlines(fei, result)
	_rule_7_lengths(fei, result)
	_rule_8_process_type(fei, result)
	_rule_9_totals(fei, result)
	_rule_10_line_count(fei, result)
	_rule_11_invoice_date(fei, result)
	_rule_12_tax_rates(fei, result)
	_rule_13_xml_specials(fei, result)
	_rule_14_email(fei, result)
	if check_source:
		_rule_15_source_delivery_note(fei, result)
	_rule_16_tax_groups(fei, result)

	return result


# --- 1. Key -----------------------------------------------------------------


def _has_diacritics(value):
	return any(unicodedata.combining(c) for c in unicodedata.normalize("NFD", value or "")) or any(
		ord(c) > 127 for c in value or ""
	)


def _rule_1_key(fei, result):
	key = (fei.fast_key or "").strip()
	if not key:
		result.add(1, BLOCK, "fast_key", _("Chưa có Key chống trùng."))
		return
	if len(key) > MAX_LEN["fast_key"]:
		result.add(
			1, BLOCK, "fast_key", _("Key dài {0} ký tự, tối đa {1}.").format(len(key), MAX_LEN["fast_key"])
		)
	if _has_diacritics(key):
		result.add(1, BLOCK, "fast_key", _("Key không được có dấu tiếng Việt hoặc ký tự đặc biệt."))

	clash = frappe.get_all(
		"Fast EInvoice Document",
		filters={
			"fast_key": key,
			"status": ("in", list(ISSUED_STATUSES)),
			"name": ("!=", fei.name or ""),
		},
		pluck="name",
		limit=1,
	)
	if clash:
		result.add(
			1,
			BLOCK,
			"fast_key",
			_("Key {0} đã dùng cho hóa đơn đã phát hành {1} — phát hành nữa sẽ bị lỗi 809/835.").format(
				key, clash[0]
			),
		)


# --- 2, 3, 4. Người mua ------------------------------------------------------


def _rule_2_buyer_identity(fei, result):
	if not (fei.customer_tax_code or "").strip():
		return
	if not (fei.customer_name or "").strip():
		result.add(2, BLOCK, "customer_name", _("Có mã số thuế thì bắt buộc có tên đơn vị mua."))
	if not (fei.address or "").strip():
		result.add(2, BLOCK, "address", _("Có mã số thuế thì bắt buộc có địa chỉ."))


def _rule_3_tax_code(fei, result):
	if str(fei.customer_type) != "1":
		return
	# Bỏ mọi ký tự không phải số (dấu gạch, khoảng trắng, chấm) — MST chi nhánh 13
	# số thường được gõ kèm dấu phân tách. Kiểm tra đúng cái sẽ gửi cho Fast.
	code = normalize_tax_code(fei.customer_tax_code)
	if len(code) not in (10, 13):
		result.add(
			3,
			BLOCK,
			"customer_tax_code",
			_("Khách là doanh nghiệp thì mã số thuế phải đúng 10 hoặc 13 chữ số (đang là {0}).").format(
				fei.customer_tax_code or _("trống")
			),
		)
		return

	# Đúng độ dài nhưng sai số kiểm tra: cảnh báo, không chặn. MST sai số kiểm tra
	# gần như chắc chắn là gõ nhầm hoặc số giả — Fast sẽ trả lỗi 78013. Để cảnh
	# báo (không chặn) phòng khi có mã đặc biệt hợp lệ mà thuật toán chưa phủ.
	if not mst_check_digit_ok(code):
		result.add(
			3,
			WARN,
			"customer_tax_code",
			_(
				"Mã số thuế {0} sai số kiểm tra — nhiều khả năng gõ nhầm. "
				"Fast/Cơ quan Thuế sẽ từ chối (lỗi 78013) nếu MST không có thật."
			).format(fei.customer_tax_code),
		)


def _rule_4_id_card(fei, result):
	code = (fei.id_card_no or "").strip()
	if not code:
		return
	if not code.isdigit() or len(code) not in (9, 12):
		result.add(4, BLOCK, "id_card_no", _("Số CCCD phải đúng 9 hoặc 12 chữ số."))


# --- 5. Đọc tiền bằng chữ ----------------------------------------------------


def _rule_5_amount_in_words(fei, result):
	words = (fei.amount_in_words or "").lower()
	if not words:
		result.add(5, BLOCK, "amount_in_words", _("Chưa có số tiền bằng chữ."))
		return
	keyword = CURRENCY_WORDS.get((fei.currency or "").upper(), fei.currency or "")
	if keyword and keyword.lower() not in words:
		result.add(
			5,
			BLOCK,
			"amount_in_words",
			_("Số tiền bằng chữ phải chứa từ khóa loại tiền “{0}” (lỗi 152).").format(keyword),
		)


# --- 6, 7. Xuống dòng và độ dài ---------------------------------------------


def _rule_6_newlines(fei, result):
	for fieldname in _MASTER_TEXT_FIELDS:
		value = fei.get(fieldname) or ""
		if "\n" in value or "\r" in value:
			result.add(
				6, BLOCK, fieldname, _("Trường “{0}” có ký tự xuống dòng (lỗi 825).").format(fieldname)
			)

	for line in fei.lines or []:
		for fieldname in ("item_name", "item_code", "uom", "note"):
			value = line.get(fieldname) or ""
			if "\n" in value or "\r" in value:
				result.add(
					6,
					BLOCK,
					"lines",
					_("Dòng {0}: “{1}” có ký tự xuống dòng (lỗi 825).").format(line.idx, fieldname),
				)


def _rule_7_lengths(fei, result):
	for fieldname, limit in (("buyer", MAX_LEN["buyer"]), ("human_name", MAX_LEN["human_name"])):
		value = fei.get(fieldname) or ""
		if len(value) > limit:
			result.add(
				7,
				BLOCK,
				fieldname,
				_("“{0}” dài {1} ký tự, tối đa {2}.").format(fieldname, len(value), limit),
			)

	for line in fei.lines or []:
		if len(line.item_name or "") > MAX_LEN["item_name"]:
			result.add(
				7,
				BLOCK,
				"lines",
				_("Dòng {0}: tên hàng dài {1} ký tự, tối đa {2} (lỗi 812).").format(
					line.idx, len(line.item_name), MAX_LEN["item_name"]
				),
			)
		if len(line.item_code or "") > MAX_LEN["item_code"]:
			result.add(
				7,
				BLOCK,
				"lines",
				_("Dòng {0}: mã hàng dài quá {1} ký tự.").format(line.idx, MAX_LEN["item_code"]),
			)


# --- 8, 12. Dòng hàng --------------------------------------------------------


def _rule_8_process_type(fei, result):
	for line in fei.lines or []:
		if not (line.process_type or "").strip():
			result.add(
				8, BLOCK, "lines", _("Dòng {0}: chưa chọn tính chất hàng hóa (lỗi 836).").format(line.idx)
			)


def _rule_12_tax_rates(fei, result):
	for line in fei.lines or []:
		if (line.tax_rate or "").strip() not in TAX_RATE_CODES:
			result.add(
				12,
				BLOCK,
				"lines",
				_("Dòng {0}: thuế suất “{1}” không thuộc bộ mã hợp lệ (lỗi 78025).").format(
					line.idx, line.tax_rate
				),
			)


# --- 9, 10. Số liệu ----------------------------------------------------------


def _rule_9_totals(fei, result):
	lines = fei.lines or []
	line_amount = sum(flt(line.amount) for line in lines)
	line_tax = sum(flt(line.tax_amount) for line in lines)

	if abs(line_amount - flt(fei.amount)) > AMOUNT_TOLERANCE:
		result.add(
			9,
			BLOCK,
			"amount",
			_("Tiền hàng {0} không khớp tổng các dòng {1}.").format(flt(fei.amount), line_amount),
		)
	if abs(line_tax - flt(fei.tax_amount)) > AMOUNT_TOLERANCE:
		result.add(
			9,
			BLOCK,
			"tax_amount",
			_("Tiền thuế {0} không khớp tổng thuế các dòng {1}.").format(flt(fei.tax_amount), line_tax),
		)

	deductions = flt(fei.deduction_amount) + flt(fei.deduction_amount_other)
	expected = flt(fei.amount) + flt(fei.tax_amount) - deductions
	if abs(expected - flt(fei.total_amount)) > AMOUNT_TOLERANCE:
		result.add(
			9,
			BLOCK,
			"total_amount",
			_("Tổng thanh toán {0} phải bằng tiền hàng + thuế − giảm trừ = {1}.").format(
				flt(fei.total_amount), expected
			),
		)


def _rule_10_line_count(fei, result):
	count = len(fei.lines or [])
	if count > MAX_LINES_PER_INVOICE:
		result.add(
			10,
			BLOCK,
			"lines",
			_("Hóa đơn có {0} dòng, tối đa {1} (lỗi 3000). Cần tách hóa đơn.").format(
				count, MAX_LINES_PER_INVOICE
			),
		)


# --- 11. Ngày hóa đơn --------------------------------------------------------


def _rule_11_invoice_date(fei, result):
	if not fei.invoice_date:
		result.add(11, BLOCK, "invoice_date", _("Chưa có ngày hóa đơn."))
		return

	latest = frappe.db.get_value(
		"Fast EInvoice Document",
		{"status": ("in", list(ISSUED_STATUSES)), "name": ("!=", fei.name or "")},
		"invoice_date",
		order_by="invoice_date desc",
	)
	if latest and getdate(fei.invoice_date) < getdate(latest):
		result.add(
			11,
			BLOCK,
			"invoice_date",
			_("Ngày hóa đơn {0} nhỏ hơn hóa đơn đã phát hành gần nhất ({1}) — lỗi 819.").format(
				getdate(fei.invoice_date).strftime("%d/%m/%Y"), getdate(latest).strftime("%d/%m/%Y")
			),
		)


# --- 13, 14. Cảnh báo --------------------------------------------------------


def _rule_13_xml_specials(fei, result):
	def flag(where, value):
		if any(ch in (value or "") for ch in "&<>"):
			result.add(
				13,
				WARN,
				where,
				_(
					"“{0}” có ký tự & < > — hệ thống sẽ escape, nhưng Fast từng lỗi 63505 với ký tự này."
				).format(value),
			)

	flag("customer_name", fei.customer_name)
	flag("buyer", fei.buyer)
	for line in fei.lines or []:
		flag("lines", line.item_name)


def _rule_14_email(fei, result):
	raw = (fei.email_deliver or "").strip()
	if not raw:
		return
	if len(raw) > MAX_LEN["email_deliver"]:
		result.add(14, WARN, "email_deliver", _("Danh sách email dài quá 256 ký tự."))
	for address in raw.split(","):
		address = address.strip()
		if address and not EMAIL_PATTERN.match(address):
			result.add(14, WARN, "email_deliver", _("“{0}” không đúng định dạng email.").format(address))


# --- 15. Chứng từ nguồn ------------------------------------------------------


def _rule_15_source_delivery_note(fei, result):
	if not fei.delivery_note:
		result.add(15, BLOCK, "delivery_note", _("Chưa gắn phiếu giao hàng."))
		return

	source = frappe.db.get_value("Delivery Note", fei.delivery_note, ["docstatus", "is_return"], as_dict=True)
	if not source:
		result.add(
			15, BLOCK, "delivery_note", _("Phiếu giao hàng {0} không tồn tại.").format(fei.delivery_note)
		)
		return
	if source.docstatus != 1:
		result.add(15, BLOCK, "delivery_note", _("Phiếu giao hàng chưa được submit."))
	if source.is_return:
		result.add(
			15,
			BLOCK,
			"delivery_note",
			_("Phiếu trả hàng không lập hóa đơn trực tiếp — dùng hóa đơn điều chỉnh giảm."),
		)

	# Hóa đơn điều chỉnh / thay thế **cố ý** dùng chung phiếu giao với hóa đơn gốc.
	if fei.invoice_type and fei.invoice_type != INVOICE_TYPE_ORIGINAL:
		return

	sibling = frappe.get_all(
		"Fast EInvoice Document",
		filters={
			"delivery_note": fei.delivery_note,
			"status": ("in", list(LIVE_STATUSES)),
			"name": ("!=", fei.name or ""),
		},
		pluck="name",
		limit=1,
	)
	if sibling:
		result.add(
			15,
			BLOCK,
			"delivery_note",
			_("Phiếu giao hàng này đã có chứng từ HĐĐT đang sống: {0}.").format(sibling[0]),
		)


# --- 16. Nhóm thuế -----------------------------------------------------------


def _rule_16_tax_groups(fei, result):
	groups = compute_tax_groups(fei.lines or [])
	bucketed = sum(
		groups[key] for key in ("tax_amount_free", "tax_amount_0", "tax_amount_5", "tax_amount_10")
	)

	stored = flt(fei.tax_amount_free) + flt(fei.tax_amount_0) + flt(fei.tax_amount_5) + flt(fei.tax_amount_10)
	if abs(stored - bucketed) > AMOUNT_TOLERANCE:
		result.add(
			16,
			BLOCK,
			"tax_amount_10",
			_("Tiền thuế theo nhóm ({0}) chưa khớp tổng thuế của các dòng ({1}).").format(stored, bucketed),
		)

	if flt(groups["unbucketed"]) > AMOUNT_TOLERANCE:
		result.add(
			17,
			WARN,
			"tax_amount_10",
			_(
				"Có {0} tiền thuế ở thuế suất không có ô nhóm nào nhận (thường là 8%). "
				"Bốn thẻ TaxAmountFree/0/5/10 của Fast không có ô cho 8% — cần xác nhận với Fast "
				"trước khi phát hành, số liệu kê khai theo nhóm sẽ thiếu khoản này."
			).format(flt(groups["unbucketed"])),
		)

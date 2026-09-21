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
	PROCESS_TYPE_GOODS,
	PROCESS_TYPE_LABELS,
	PROCESS_TYPE_SPECIAL,
	TAX_RATE_CODES,
)
from erpnext.einvoice.payload import (
	CURRENCY_WORDS,
	compute_tax_groups,
	mst_check_digit_ok,
	normalize_tax_code,
)
from erpnext.einvoice.totals import amount_precision, is_billable, summarise

BLOCK = "block"
WARN = "warn"

# Sai lệch nhỏ hơn mức này coi như bằng nhau (làm tròn tiền tệ).
AMOUNT_TOLERANCE = 1.0

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Chỉ dòng thực sự bán hàng mới phải trỏ tới danh mục. Dòng ghi chú (4), khuyến
# mại (2) và chiết khấu (3) không có mặt hàng nào tương ứng.
ITEM_CODE_REQUIRED_PROCESS_TYPES = frozenset({PROCESS_TYPE_GOODS, PROCESS_TYPE_SPECIAL})

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
	_rule_8_line_basics(fei, result)
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
		result.add(1, BLOCK, "fast_key", _("Chưa có Key chống trùng (lỗi 813)."))
		return
	if len(key) > MAX_LEN["fast_key"]:
		result.add(
			1,
			BLOCK,
			"fast_key",
			_("Key dài {0} ký tự, tối đa {1} (lỗi 812).").format(len(key), MAX_LEN["fast_key"]),
		)
	if _has_diacritics(key):
		result.add(
			1,
			WARN,
			"fast_key",
			_(
				"Key có dấu tiếng Việt hoặc ký tự đặc biệt. Tài liệu Fast không cấm điều này ở "
				"thẻ Key nên không chặn, nhưng Key còn là khóa tra cứu hóa đơn — để ASCII cho chắc."
			),
		)

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
		result.add(
			2,
			BLOCK,
			"customer_name",
			_("Có mã số thuế thì bắt buộc có tên đơn vị mua — Fast từ chối, lỗi 836."),
		)
	if not (fei.address or "").strip():
		result.add(
			2,
			BLOCK,
			"address",
			_("Có mã số thuế thì bắt buộc có địa chỉ — Fast từ chối, lỗi 836."),
		)


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
		result.add(4, BLOCK, "id_card_no", _("Số CCCD phải đúng 9 hoặc 12 chữ số (lỗi 836)."))


# --- 5. Đọc tiền bằng chữ ----------------------------------------------------


def _rule_5_amount_in_words(fei, result):
	words = (fei.amount_in_words or "").lower()
	if not words:
		result.add(5, BLOCK, "amount_in_words", _("Chưa có số tiền bằng chữ (lỗi 813)."))
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
				_("“{0}” dài {1} ký tự, tối đa {2} (lỗi 812).").format(fieldname, len(value), limit),
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
				_("Dòng {0}: mã hàng dài quá {1} ký tự (lỗi 812).").format(line.idx, MAX_LEN["item_code"]),
			)


# --- 8, 12. Dòng hàng --------------------------------------------------------


def _rule_8_line_basics(fei, result):
	"""Tính chất dòng, và mã hàng cho những dòng thực sự bán hàng.

	Mã hàng bắt buộc gác ở đây thay vì bằng ``reqd`` của DocType: dòng ghi chú
	(tính chất 4), khuyến mại (2) và chiết khấu (3) không trỏ tới hàng nào trong
	danh mục — nội dung của chúng nằm ở tên hàng. Chỉ dòng hàng hóa (1) và hàng
	đặc trưng (5) mới phải có mã.
	"""
	for line in fei.lines or []:
		process_type = (line.process_type or "").strip()
		if not process_type:
			result.add(
				8, BLOCK, "lines", _("Dòng {0}: chưa chọn tính chất hàng hóa (lỗi 836).").format(line.idx)
			)
			continue

		if process_type in ITEM_CODE_REQUIRED_PROCESS_TYPES and not (line.item_code or "").strip():
			result.add(
				8,
				BLOCK,
				"lines",
				_(
					"Dòng {0}: chưa chọn mã hàng — dòng {1} phải trỏ tới một mặt hàng trong "
					"danh mục. Gửi ItemCode rỗng thì Fast từ chối, lỗi 813."
				).format(line.idx, PROCESS_TYPE_LABELS.get(process_type, process_type)),
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


# Số master phải khớp dòng hàng. Bốn ô nhóm thuế thuộc quy tắc 16, không kiểm ở đây.
_TOTAL_LABELS = {
	"amount": "Tiền hàng (chưa thuế)",
	"tax_amount": "Tiền thuế GTGT",
	"discount_amount": "Tiền chiết khấu",
	"promotion_amount": "Tiền khuyến mại",
	"total_amount": "Tổng thanh toán",
}

_TAX_GROUP_LABELS = {
	"tax_amount_free": "không chịu thuế",
	"tax_amount_0": "0%",
	"tax_amount_5": "5%",
	"tax_amount_10": "10%",
}


def _rule_9_totals(fei, result):
	"""Số tổng hợp phải đúng bằng cái công thức tính ra từ dòng hàng.

	Đối chiếu bằng **chính** hàm mà chứng từ dùng để tính (`einvoice.totals`), nên
	"số đúng" và "số được kiểm" không thể là hai định nghĩa khác nhau — trước đây
	quy tắc này có công thức riêng và không biết Tính chất dòng, nên hóa đơn có
	dòng khuyến mại luôn bị báo lệch.

	Đang ghi đè số bằng tay thì hạ xuống **cảnh báo**: chặn ở đây thì ghi đè trở
	nên vô nghĩa (không phát hành được), nhưng vẫn phải nói ra là số đã lệch.
	"""
	level = WARN if fei.get("totals_manual_override") else BLOCK

	if level == WARN:
		result.add(
			9,
			WARN,
			"totals_manual_override",
			_("Số tổng hợp đang do người dùng ghi đè bằng tay, không do công thức tính: {0}").format(
				fei.get("override_reason") or _("(chưa ghi lý do)")
			),
		)

	expected = summarise(
		fei.lines,
		fei.currency,
		fei.deduction_amount,
		fei.deduction_amount_other,
	)
	for fieldname, label in _TOTAL_LABELS.items():
		if abs(flt(expected[fieldname]) - flt(fei.get(fieldname))) > AMOUNT_TOLERANCE:
			result.add(
				9,
				level,
				fieldname,
				_("{0} đang là {1}, nhưng dòng hàng cho ra {2} (lỗi 836 — lỗi về số liệu).").format(
					label, flt(fei.get(fieldname)), flt(expected[fieldname])
				),
			)

	_warn_about_lines_left_out_of_the_totals(fei, result)


def _warn_about_lines_left_out_of_the_totals(fei, result):
	"""Nói rõ khi hóa đơn có dòng không cộng vào Tiền hàng.

	Khuyến mại và ghi chú **cố ý** đứng ngoài Tiền hàng và Tiền thuế. Nhưng nếu
	Fast đối chiếu tổng của phần chi tiết với phần master ở đầu họ, chênh lệch này
	là thứ đầu tiên cần nhìn — nên ghi ra trước, đừng để đi tìm lúc bị từ chối.
	"""
	excluded = [line for line in (fei.lines or []) if not is_billable(line)]
	if not excluded:
		return
	result.add(
		9,
		WARN,
		"lines",
		_(
			"{0} dòng (khuyến mại / ghi chú) không cộng vào Tiền hàng và Tiền thuế: dòng {1}. "
			"Tổng phần chi tiết vì thế lớn hơn số ở phần tổng hợp."
		).format(len(excluded), ", ".join(str(line.idx) for line in excluded)),
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
	"""Ngày hóa đơn: thiếu thì chặn, ra trước hóa đơn khác thì chỉ cảnh báo.

	Fast bắt buộc có ``InvoiceDate`` nên thiếu là chắc chắn hỏng — chặn.

	Nhưng thứ tự ngày thì **Fast mới là bên biết**, không phải mình. Câu truy vấn
	dưới đây chỉ nhìn thấy những hóa đơn đi qua ERP này; nó không thấy hóa đơn
	phát hành thẳng trên portal, hóa đơn của sổ khác, hay hóa đơn từ hệ thống cũ.
	Chặn dựa trên một cái nhìn thiếu như vậy là chặn nhầm người đang làm đúng, mà
	cái giá phải trả là kế toán ngồi im không thao tác được gì. Fast có kiểm
	(lỗi 819) và câu trả lời của họ mới là câu trả lời thật — nên nói ra để biết
	mà lường trước, rồi để Fast quyết. Cùng cách xử lý với số kiểm tra MST ở
	quy tắc 3.
	"""
	if not fei.invoice_date:
		result.add(11, BLOCK, "invoice_date", _("Chưa có ngày hóa đơn (lỗi 813)."))
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
			WARN,
			"invoice_date",
			_(
				"Ngày hóa đơn {0} nhỏ hơn hóa đơn đã phát hành gần nhất trong ERP ({1}). "
				"Fast không cho phát hành lùi ngày (lỗi 819) — nhiều khả năng sẽ bị từ chối, "
				"nhưng Fast mới là bên biết chắc nên vẫn gửi được."
			).format(getdate(fei.invoice_date).strftime("%d/%m/%Y"), getdate(latest).strftime("%d/%m/%Y")),
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
	"""Bốn ô nhóm thuế của Phần I phải khớp dòng hàng — **từng ô một**.

	Kiểm riêng từng ô chứ không chỉ kiểm tổng: hai ô 5% và 10% đổi chỗ nhau thì
	tổng vẫn đúng, mà tờ khai thì sai.

	Quy tắc này là **cảnh báo**, không chặn phát hành.

	Trước đây còn một quy tắc 17 đi kèm, cảnh báo mỗi khi có tiền thuế 8% nằm
	ngoài bốn ô nhóm. Đã bỏ hẳn: 8% là thuế suất phổ thông của giai đoạn giảm
	thuế, nên nó nổ ở gần như mọi hóa đơn, mà nội dung lại kết thúc bằng "không
	cần xử lý gì". Một cảnh báo luôn hiện và luôn bảo đừng làm gì thì chỉ dạy
	người dùng bỏ qua cả bảng cảnh báo — kéo theo cả những cảnh báo thật sự cần
	đọc (ngày hóa đơn lùi, MST sai số kiểm tra). Điều nó muốn nói đã nằm ở đây
	và ở `compute_tax_groups`, là chỗ đúng của một quyết định thiết kế.

	Đã đối chứng trên môi trường thử ngày 2026-09-08: hóa đơn một dòng 5% và một
	dòng 8% — tiền thuế 150.000 mà bốn ô chỉ cộng được 50.000, lệch 100.000 — vẫn
	phát hành trót lọt: Fast cấp số 4 ký hiệu C26TAA, rồi Cơ quan Thuế chấp nhận.
	Fast **không** dùng bốn ô này để dựng tờ khai; họ dựng từ thuế suất của từng
	dòng hàng, đúng như tài liệu của họ nói về giá trị -9 ("xml thẻ thuế suất bỏ
	trống"). Bốn ô chỉ là số tổng hợp phụ.

	Nên chặn ở đây là ERP từ chối gửi thứ mà Fast sẵn sàng nhận — chặn thừa, và
	cái giá là kế toán không phát hành được một hóa đơn hoàn toàn hợp lệ. Khác với
	quy tắc 9: ở đó là Tổng thanh toán, con số in trên chứng từ pháp lý và khách
	hàng phải trả, sai là hóa đơn tự mâu thuẫn — nên quy tắc 9 vẫn chặn.

	Ngoài ra hai ô này gần như không bao giờ lệch được: `compute_document_totals`
	tính lại chúng ở **mỗi lần Lưu**, bằng đúng hàm mà quy tắc này đem ra đối
	chiếu. Lệch chỉ xảy ra khi đang ghi đè tay, hoặc khi bản ghi còn giữ số cũ từ
	trước một lần đổi công thức — cả hai đều là chuyện cần nói ra, không phải
	chuyện cần khóa tay người dùng.
	"""
	groups = compute_tax_groups(fei.lines or [])
	precision = amount_precision(fei.currency)

	for fieldname, label in _TAX_GROUP_LABELS.items():
		expected = flt(groups[fieldname], precision)
		if abs(expected - flt(fei.get(fieldname))) > AMOUNT_TOLERANCE:
			result.add(
				16,
				WARN,
				fieldname,
				_(
					"Ô tiền thuế {0} đang là {1}, nhưng dòng hàng cho ra {2}. "
					"Fast không dùng bốn ô này để kê khai nên vẫn phát hành được; "
					"bấm Lưu là số tự tính lại cho khớp."
				).format(label, flt(fei.get(fieldname)), expected),
			)

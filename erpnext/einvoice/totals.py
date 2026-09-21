# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Công thức tiền của chứng từ HĐĐT — **một bản duy nhất** cho cả hệ thống.

Trước đây phép tính này nằm ở bốn chỗ: controller của chứng từ, `builder` khi
tạo từ phiếu giao, `validation` khi kiểm tra trước lúc gửi, và `payload` khi cộng
nhóm thuế. Bốn bản thì sớm muộn cũng lệch nhau — và đã lệch: `builder` không tính
gì cả, nó bê `net_total`/`grand_total` của phiếu giao sang, nên chứng từ chỉ là
bản chụp. Sửa một dòng hàng là số liệu sai, mà không chỗ nào phát hiện ra.

Chứng từ HĐĐT phải tự tính, độc lập với phiếu giao: phiếu giao đã submit thì
không sửa được nữa, nên mọi chỉnh sửa hóa đơn trước lúc phát hành chỉ có thể xảy
ra ở đây. Module này là nơi duy nhất biết cách tính, và ai cần tính thì gọi vào.

Thuần túy — không đọc ghi cơ sở dữ liệu, không gọi mạng — trừ `preview_totals`
là cửa cho giao diện gọi vào để hiện số ngay khi đang gõ.
"""

import frappe
from frappe.utils import flt

from erpnext.einvoice.constants import (
	BILLABLE_PROCESS_TYPES,
	NUMERIC_TAX_RATES,
	PROCESS_TYPE_DISCOUNT,
	PROCESS_TYPE_GOODS,
	PROCESS_TYPE_PROMOTION,
)
from erpnext.einvoice.payload import amount_in_words_for, compute_tax_groups

FEI = "Fast EInvoice Document"

# Loại tiền không có đơn vị lẻ trong thanh toán — Tổng thanh toán phải là số nguyên.
_ZERO_DECIMAL_CURRENCIES = frozenset({"VND", "JPY"})

# Các khoản thành phần (tiền hàng, tiền thuế, chiết khấu, khuyến mại) luôn giữ
# hai số lẻ, kể cả VND.
COMPONENT_PRECISION = 2

# Bốn ô nhóm thuế của Phần I.
TAX_GROUP_FIELDS = ("tax_amount_free", "tax_amount_0", "tax_amount_5", "tax_amount_10")

# Trường master do công thức làm chủ. Người dùng không gõ tay vào đây, và
# `validation` đối chiếu đúng bộ này để biết chứng từ có tự nhất quán hay không.
COMPUTED_MASTER_FIELDS = (
	"amount",
	"tax_amount",
	*TAX_GROUP_FIELDS,
	"discount_amount",
	"promotion_amount",
	"total_amount",
	"tax_rate",
	"amount_in_words",
)

# Trường dòng hàng do công thức làm chủ.
#
# `line_number` **không** nằm đây: đó là thẻ tùy chọn của Fast, chỉ đưa vào payload
# khi có dòng dùng tới (xem `_used_detail_tags`). Tự đánh số mọi dòng sẽ khiến thẻ
# LineNumber luôn được gửi — đổi cách giao tiếp với Fast để lấy một con số mà lưới
# đã có sẵn ở cột `idx`.
COMPUTED_LINE_FIELDS = ("discount_amount", "amount", "tax_amount")


def amount_precision(currency=None):
	"""Số chữ số thập phân của các khoản **thành phần** — luôn là hai.

	Tiền hàng chưa thuế và Tiền thuế GTGT không được làm tròn về đồng nguyên:
	làm tròn ở đây là làm tròn hai lần (một lần ở thành phần, một lần ở tổng),
	và mỗi lần lại đẩy sai số vào số tiền phải thu. Chỉ Tổng thanh toán mới lấy
	số nguyên — xem `total_precision`.

	Giữ tham số ``currency`` để nơi gọi không phải nhớ khoản nào theo loại tiền
	và khoản nào không; nếu sau này có loại tiền cần khác hai số lẻ thì đây là
	chỗ duy nhất phải sửa.
	"""
	return COMPONENT_PRECISION


def total_precision(currency):
	"""Số chữ số thập phân của **Tổng thanh toán**.

	VND và JPY không có đơn vị nhỏ hơn đồng/yên trong thanh toán, nên số tiền
	cuối cùng phải tròn. Ngoại tệ có xu thì giữ nguyên hai số lẻ.
	"""
	return 0 if (currency or "VND").upper() in _ZERO_DECIMAL_CURRENCIES else COMPONENT_PRECISION


def process_type_of(line):
	"""Tính chất của dòng; bản nháp chưa chọn thì coi như hàng hóa."""
	return (line.get("process_type") or PROCESS_TYPE_GOODS).strip() or PROCESS_TYPE_GOODS


def is_billable(line):
	"""Dòng này có chảy vào Tiền hàng và Tiền thuế của hóa đơn không."""
	return process_type_of(line) in BILLABLE_PROCESS_TYPES


def compute_lines(lines, precision):
	"""Tính lại từng dòng hàng từ Số lượng, Đơn giá, Chiết khấu, Thuế suất.

	Nhập **tỷ lệ** chiết khấu thì tỷ lệ thắng số tiền gõ tay: để hai con số cùng
	sống là để chứng từ tự nói hai điều khác nhau. Không nhập tỷ lệ thì số tiền
	gõ tay được giữ — đó là cách nhập chiết khấu tuyệt đối.

	Làm tròn **ngay ở từng dòng**, để phần tổng hợp chỉ việc cộng các số đã tròn.
	Cộng số thô rồi mới làm tròn thì tổng lệch với chính các dòng in trên hóa đơn.
	"""
	for line in lines or []:
		gross = flt(line.qty) * flt(line.price)
		if flt(line.discount_rate):
			line.discount_amount = flt(gross * flt(line.discount_rate) / 100.0, precision)
		line.amount = flt(gross - flt(line.discount_amount), precision)

		rate = NUMERIC_TAX_RATES.get((line.tax_rate or "").strip())
		line.tax_amount = flt(line.amount * rate / 100.0, precision) if rate else 0.0


def dominant_tax_rate(lines):
	"""Thuế suất ghi ở master = thuế suất của phần lớn tiền hàng."""
	totals = {}
	for line in lines or []:
		if not is_billable(line):
			continue
		totals[line.tax_rate] = totals.get(line.tax_rate, 0) + flt(line.amount)
	return max(totals, key=totals.get) if totals else "0"


def summarise(lines, currency, deduction_amount=0, deduction_amount_other=0):
	"""Tổng hợp phần master từ các dòng **đã tính**. Chỉ đọc, không sửa dòng nào.

	`validation` dùng chính hàm này để biết số master có khớp dòng hàng không —
	nên "số đúng" và "số được kiểm" không thể là hai định nghĩa khác nhau.

	Nhận loại tiền chứ không nhận sẵn độ chính xác, vì các khoản thành phần và
	Tổng thanh toán làm tròn khác nhau: chỉ nơi này mới biết cả hai.
	"""
	lines = lines or []
	precision = amount_precision(currency)
	billable = [line for line in lines if is_billable(line)]

	amount = flt(sum(flt(line.amount) for line in billable), precision)
	tax_amount = flt(sum(flt(line.tax_amount) for line in billable), precision)

	groups = compute_tax_groups(lines)

	promotion = flt(
		sum(flt(line.amount) for line in lines if process_type_of(line) == PROCESS_TYPE_PROMOTION),
		precision,
	)
	# Chiết khấu của hóa đơn gồm cả chiết khấu ghi trên từng dòng và dòng chiết
	# khấu riêng (nhập số âm, nên đảo dấu để ra số tiền đã giảm).
	discount = flt(
		sum(flt(line.discount_amount) for line in lines)
		+ sum(-flt(line.amount) for line in lines if process_type_of(line) == PROCESS_TYPE_DISCOUNT),
		precision,
	)

	deductions = flt(deduction_amount) + flt(deduction_amount_other)

	return {
		"amount": amount,
		"tax_amount": tax_amount,
		**{field: flt(groups[field], precision) for field in TAX_GROUP_FIELDS},
		"discount_amount": discount,
		"promotion_amount": promotion,
		# Làm tròn **một lần duy nhất**, ở đây, trên số đã cộng đủ — nên chênh lệch
		# làm tròn không bao giờ vượt quá nửa đơn vị tiền tệ.
		"total_amount": flt(amount + tax_amount - deductions, total_precision(currency)),
		"tax_rate": dominant_tax_rate(lines),
		"unbucketed": flt(groups["unbucketed"], precision),
	}


def compute_document_totals(fei):
	"""Tính lại toàn bộ chứng từ — dòng hàng trước, rồi tổng hợp. Sửa thẳng trên `fei`.

	Trả về bản tổng hợp để nơi gọi dùng tiếp (ví dụ phần thuế 8% không có ô nhóm).
	"""
	precision = amount_precision(fei.currency)
	compute_lines(fei.lines, precision)

	totals = summarise(fei.lines, fei.currency, fei.deduction_amount, fei.deduction_amount_other)
	for fieldname in COMPUTED_MASTER_FIELDS:
		if fieldname in totals:
			fei.set(fieldname, totals[fieldname])

	# Hóa đơn 0 đồng thì giữ nguyên chữ đang có: `amount_in_words` là trường bắt
	# buộc, ghi rỗng vào đó chỉ đổi một lỗi thành một lỗi khác.
	if fei.total_amount and fei.currency:
		fei.amount_in_words = amount_in_words_for(fei.total_amount, fei.currency)

	return totals


@frappe.whitelist()
def preview_totals(doc):
	"""Tính thử cho form khi chứng từ **chưa lưu** — cùng công thức với lúc Lưu.

	Không ghi gì vào cơ sở dữ liệu và không quyết định số cuối cùng: lúc Lưu,
	`validate` vẫn tính lại từ đầu. Nên đây thuần túy là để kế toán thấy số đổi
	ngay khi thêm hay sửa một dòng, chứ không phải một đường vòng để nhập số.

	Nhân bản công thức sang JavaScript sẽ nhanh hơn một nhịp mạng, nhưng đổi lại
	là hai công thức — và cái giá của việc form hiện một số rồi chứng từ lưu một
	số khác thì đắt hơn nhiều.
	"""
	if not frappe.has_permission(FEI, "read"):
		frappe.throw(frappe._("Không có quyền đọc chứng từ hóa đơn điện tử."), frappe.PermissionError)

	fei = frappe.get_doc(frappe.parse_json(doc))
	totals = compute_document_totals(fei)

	return {
		"master": {field: fei.get(field) for field in COMPUTED_MASTER_FIELDS},
		"lines": [
			{"idx": line.idx, **{field: line.get(field) for field in COMPUTED_LINE_FIELDS}}
			for line in fei.lines or []
		],
		"unbucketed": totals["unbucketed"],
	}

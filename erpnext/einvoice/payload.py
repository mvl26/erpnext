# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Đóng gói chứng từ HĐĐT thành payload Fast — Phần I của đặc tả.

Hai luật của Phần I quyết định toàn bộ module này:

- **Thứ tự ``structure`` quyết định ý nghĩa từng ô ``master``/``detail``.**
  Lệch một ô thì dữ liệu chạy sang cột khác mà Fast vẫn nhận — hỏng âm thầm.
  Vì vậy structure và values luôn dựng từ **cùng một danh sách thẻ**.
- **Trường không dùng thì bỏ hẳn khỏi structure**, không gửi thẻ rỗng. Thẻ nào
  luôn gửi và thẻ nào chỉ gửi khi có giá trị được đánh dấu ngay trong bảng thẻ.
"""

import frappe
from frappe.utils import flt, getdate

from erpnext.einvoice.constants import (
	ADJUSTMENT_TYPE_REPLACEMENT,
	INVOICE_TYPE_ORIGINAL,
	INVOICE_TYPE_REPLACEMENT,
)
from erpnext.einvoice.fast_settings import get_settings
from erpnext.regional.vietnam.utils import so_thanh_chu

# Đọc tiền bằng chữ phải chứa đúng từ khóa loại tiền, sai là lỗi 152 (mục F#5).
CURRENCY_WORDS = {
	"VND": "đồng",
	"USD": "đô la Mỹ",
	"EUR": "Euro",
	"JPY": "yên Nhật",
}

# Bốn ô nhóm thuế của Phần I. Thuế suất 8% không có ô nào trong bốn thẻ này —
# xem ghi chú ở `compute_tax_groups`.
_TAX_BUCKETS = {
	"0": "tax_amount_0",
	"5": "tax_amount_5",
	"10": "tax_amount_10",
	"-1": "tax_amount_free",
	"-2": "tax_amount_free",
	"-8": "tax_amount_free",
	"-9": "tax_amount_free",
}


def _text(value):
	return "" if value is None else str(value)


def _number(value):
	number = flt(value)
	return int(number) if number == int(number) else number


def _date(value):
	"""InvoiceDate serialize dd/MM/yyyy (mục C2.3 #21)."""
	return getdate(value).strftime("%d/%m/%Y") if value else ""


# (thẻ Fast, fieldname trên DocType, hàm chuyển kiểu, luôn gửi?)
# Thứ tự đúng theo mục C2.3; cột "luôn gửi" theo danh sách tham chiếu Phần I.
MASTER_TAGS = (
	("Key", "fast_key", _text, True),
	("InvoiceDate", "invoice_date", _date, True),
	("CustomerCode", "customer_code", _text, True),
	("Buyer", "buyer", _text, True),
	("CustomerName", "customer_name", _text, True),
	("CustomerTaxCode", "customer_tax_code", _text, True),
	("CustomerType", "customer_type", _text, True),
	("Address", "address", _text, True),
	("PhoneNumber", "phone_number", _text, True),
	("FaxNumber", "fax_number", _text, True),
	("IDCardNo", "id_card_no", _text, False),
	("PassportNo", "passport_no", _text, False),
	("BuyerUnit", "buyer_unit", _text, False),
	("EmailDeliver", "email_deliver", _text, True),
	("BankAccount", "bank_account", _text, True),
	("BankName", "bank_name", _text, True),
	("PaymentMethod", "payment_method", _text, True),
	("Currency", "currency", _text, True),
	("ExchangeRate", "exchange_rate", _number, True),
	("Amount", "amount", _number, True),
	("TotalAmount", "total_amount", _number, True),
	("TaxRate", "tax_rate", _number, True),
	("TaxAmount", "tax_amount", _number, True),
	("TaxAmountFree", "tax_amount_free", _number, True),
	("TaxAmount0", "tax_amount_0", _number, True),
	("TaxAmount5", "tax_amount_5", _number, True),
	("TaxAmount10", "tax_amount_10", _number, True),
	("DiscountAmount", "discount_amount", _number, True),
	("PromotionAmount", "promotion_amount", _number, True),
	("DeductionAmount", "deduction_amount", _number, False),
	("DeductionAmountOther", "deduction_amount_other", _number, False),
	("AmountInWords", "amount_in_words", _text, True),
	("HumanName", "human_name", _text, True),
	("ReleaseType", "release_type", _text, False),
	("External1", "external_1", _text, False),
	("External2", "external_2", _text, False),
	("External3", "external_3", _text, False),
	("NumberExternal1", "number_external_1", _number, False),
	("NumberExternal2", "number_external_2", _number, False),
	("NumberExternal3", "number_external_3", _number, False),
)

DETAIL_TAGS = (
	("ProcessType", "process_type", _text, True),
	("ItemCode", "item_code", _text, True),
	("ItemName", "item_name", _text, True),
	("UOM", "uom", _text, True),
	("IsPromotion", "is_promotion", _number, True),
	("Quantity", "qty", _number, True),
	("Price", "price", _number, True),
	("Amount", "amount", _number, True),
	("DiscountRate", "discount_rate", _number, True),
	("DiscountAmount", "discount_amount", _number, True),
	("TaxRate", "tax_rate", _number, True),
	("TaxAmount", "tax_amount", _number, True),
	("Note", "note", _text, False),
	("LineNumber", "line_number", _number, False),
)

MASTER_BASE_TAGS = tuple(tag for tag, _f, _c, always in MASTER_TAGS if always)
DETAIL_BASE_TAGS = tuple(tag for tag, _f, _c, always in DETAIL_TAGS if always)


def amount_in_words_for(amount, currency):
	"""Đọc tiền bằng chữ kèm đúng từ khóa loại tiền."""
	return so_thanh_chu(amount, CURRENCY_WORDS.get((currency or "").upper(), currency or ""))


def compute_tax_groups(lines):
	"""Cộng tiền thuế theo bốn ô nhóm của Phần I.

	Trả thêm ``unbucketed``: tiền thuế của những thuế suất không có ô nào nhận —
	trong thực tế là **thuế suất 8%** (giảm thuế theo nghị quyết). Bảng thẻ của
	đặc tả chỉ có Free/0/5/10, chưa có TaxAmount8. Không tự nhét 8% vào ô 10%:
	số liệu kê khai sai còn tệ hơn số liệu thiếu. Tầng kiểm tra dữ liệu sẽ cảnh
	báo khi ``unbucketed`` khác 0 để kế toán xác nhận thẻ đúng với Fast.
	"""
	groups = {"tax_amount_free": 0.0, "tax_amount_0": 0.0, "tax_amount_5": 0.0, "tax_amount_10": 0.0}
	unbucketed = 0.0
	for line in lines or []:
		amount = flt(line.get("tax_amount"))
		bucket = _TAX_BUCKETS.get((line.get("tax_rate") or "").strip())
		if bucket:
			groups[bucket] += amount
		else:
			unbucketed += amount
	groups["unbucketed"] = unbucketed
	return groups


def build_payload(fei, settings=None):
	"""Payload hoàn chỉnh cho một chứng từ HĐĐT. Thuần túy — không gọi mạng."""
	settings = settings or get_settings()

	master_tags, master_values = _serialise(fei, MASTER_TAGS)
	detail_tags = _used_detail_tags(fei)
	detail_rows = [_serialise_row(line, detail_tags) for line in (fei.lines or [])]

	payload = {
		"voucherBook": settings.voucher_book,
		"data": {
			"structure": {
				"master": master_tags,
				"detail": [tag for tag, _f, _c, _a in detail_tags],
			},
			"invoices": [{"master": master_values, "detail": detail_rows}],
		},
	}
	payload.update(_lineage(fei))
	return payload


def _serialise(fei, tags):
	"""Dựng danh sách thẻ và danh sách giá trị từ **cùng một** bảng thẻ."""
	used_tags, values = [], []
	for tag, fieldname, convert, always in tags:
		value = fei.get(fieldname)
		if not always and not value:
			continue
		used_tags.append(tag)
		values.append(convert(value))
	return used_tags, values


def _used_detail_tags(fei):
	"""Thẻ tùy chọn của dòng hàng chỉ đưa vào khi **có dòng nào đó** dùng tới."""
	lines = fei.lines or []
	return tuple(entry for entry in DETAIL_TAGS if entry[3] or any(line.get(entry[1]) for line in lines))


def _serialise_row(line, tags):
	return [convert(line.get(fieldname)) for _tag, fieldname, convert, _always in tags]


def _lineage(fei):
	"""``originalInvoice`` + ``adjustmentType`` — chỉ khi điều chỉnh / thay thế."""
	if not fei.invoice_type or fei.invoice_type == INVOICE_TYPE_ORIGINAL:
		return {}

	original_key = ""
	if fei.original_document:
		original_key = (
			frappe.db.get_value("Fast EInvoice Document", fei.original_document, "fast_key_search") or ""
		)

	if fei.invoice_type == INVOICE_TYPE_REPLACEMENT:
		adjustment_type = ADJUSTMENT_TYPE_REPLACEMENT
	else:
		adjustment_type = (fei.adjustment_type or "").split(" - ", 1)[0].strip()

	return {"originalInvoice": original_key, "adjustmentType": adjustment_type}

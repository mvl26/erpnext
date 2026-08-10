# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Dựng chứng từ HĐĐT từ Delivery Note — Nút 1 và Nút 2 của mục E1.

Không gọi Fast ở bước này: chỉ sao dữ liệu sang chứng từ HĐĐT để kế toán rà
soát. Cột "Nguồn DN" của mục C2.3 là bản đồ ánh xạ.
"""

import re
import unicodedata

import frappe
from frappe import _
from frappe.utils import flt, get_fullname

from erpnext.einvoice.constants import (
	EDITABLE_STATUSES,
	INVOICE_TYPE_ORIGINAL,
	LIVE_STATUSES,
	MAX_LEN,
	STATUS_DRAFT,
)
from erpnext.einvoice.fast_settings import check_enabled, get_settings
from erpnext.einvoice.payload import amount_in_words_for, compute_tax_groups

FEI = "Fast EInvoice Document"

# Hình thức thanh toán mặc định — chuyển khoản, đúng thực tế bán buôn thiết bị y tế.
DEFAULT_PAYMENT_METHOD = "CK"


def fast_key_for(delivery_note_name):
	"""Key chống trùng: tên phiếu giao, bỏ dấu, ≤32 ký tự (mục E1)."""
	stripped = "".join(
		c for c in unicodedata.normalize("NFD", delivery_note_name or "") if not unicodedata.combining(c)
	)
	stripped = stripped.replace("Đ", "D").replace("đ", "d")
	safe = "".join(c for c in stripped if c.isalnum() or c in "-_")
	return safe[: MAX_LEN["fast_key"]]


@frappe.whitelist()
def create_from_delivery_note(delivery_note):
	"""Nút 1 — tạo chứng từ HĐĐT từ một phiếu giao đã submit. Trả tên bản ghi."""
	settings = check_enabled()
	source = _load_delivery_note(delivery_note)
	_assert_no_live_invoice(delivery_note)

	fei = frappe.new_doc(FEI)
	fei.delivery_note = source.name
	fei.invoice_type = INVOICE_TYPE_ORIGINAL
	fei.status = STATUS_DRAFT
	# Key sinh đúng một lần, ngay lúc tạo bản ghi (nguyên tắc A4).
	fei.fast_key = fast_key_for(source.name)
	_copy_from_delivery_note(fei, source, settings)

	fei.flags.ignore_permissions = True
	fei.insert()

	_stamp_delivery_note(fei)
	return fei.name


@frappe.whitelist()
def resync_from_delivery_note(fei):
	"""Nút 2 — nạp lại dữ liệu từ phiếu giao, ghi đè master và dòng hàng."""
	settings = check_enabled()
	doc = frappe.get_doc(FEI, fei)

	if doc.status not in EDITABLE_STATUSES:
		frappe.throw(
			_("Hóa đơn đang ở trạng thái {0} nên không đồng bộ lại được từ phiếu giao.").format(doc.status)
		)

	source = _load_delivery_note(doc.delivery_note)
	_copy_from_delivery_note(doc, source, settings)

	# Dữ liệu vừa đổi nên mọi xác nhận trước đó của khách không còn giá trị.
	# `revision_count` đếm số lần **quay về Nháp từ 02/03/04** (mục C2.2 #19), nên
	# đồng bộ lại một bản ghi đang là Nháp thì không tính thêm một vòng sửa —
	# nếu không, ghi nhận ý kiến khách rồi đồng bộ sẽ đếm thành hai.
	if doc.status != STATUS_DRAFT:
		doc.revision_count = (doc.revision_count or 0) + 1
	doc.status = STATUS_DRAFT
	doc.flags.ignore_permissions = True
	doc.save()

	_stamp_delivery_note(doc)
	return doc.name


# --- Ánh xạ dữ liệu ----------------------------------------------------------


def _load_delivery_note(name):
	"""Tiền điều kiện của mục E1: đã submit và không phải phiếu trả hàng."""
	if not name or not frappe.db.exists("Delivery Note", name):
		frappe.throw(_("Không tìm thấy phiếu giao hàng {0}.").format(name))

	source = frappe.get_doc("Delivery Note", name)
	if source.docstatus != 1:
		frappe.throw(_("Phiếu giao hàng {0} chưa được submit.").format(name))
	if source.is_return:
		frappe.throw(
			_("Phiếu trả hàng không lập hóa đơn trực tiếp — dùng hóa đơn điều chỉnh giảm từ hóa đơn gốc.")
		)
	return source


def _assert_no_live_invoice(delivery_note):
	existing = frappe.get_all(
		FEI,
		filters={"delivery_note": delivery_note, "status": ("in", list(LIVE_STATUSES))},
		fields=["name", "status"],
		limit=1,
	)
	if existing:
		frappe.throw(
			_("Phiếu giao {0} đã có chứng từ HĐĐT {1} ({2}).").format(
				delivery_note, existing[0].name, existing[0].status
			)
		)


def _copy_from_delivery_note(fei, source, settings):
	customer = frappe.get_doc("Customer", source.customer)

	fei.customer = source.customer
	fei.invoice_date = source.posting_date
	fei.customer_code = fast_key_for(source.customer)
	fei.customer_name = source.customer_name or source.customer
	fei.customer_tax_code = (customer.get("tax_id") or "").strip()
	fei.customer_type = "1" if (customer.get("customer_type") or "") == "Company" else "0"
	fei.address = _billing_address(source, customer)
	fei.buyer = _contact_name(source)
	fei.phone_number = _contact_value(source, customer, "phone")
	fei.email_deliver = _contact_value(source, customer, "email")
	fei.payment_method = fei.payment_method or DEFAULT_PAYMENT_METHOD
	fei.currency = source.currency
	fei.exchange_rate = flt(source.conversion_rate) or 1.0
	fei.human_name = fei.human_name or _issuer_name(settings)

	fei.amount = flt(source.net_total)
	fei.total_amount = flt(source.grand_total)
	fei.tax_amount = flt(source.get("total_taxes_and_charges"))
	fei.discount_amount = flt(source.get("discount_amount"))

	_copy_lines(fei, source)

	groups = compute_tax_groups(fei.lines)
	fei.tax_amount_free = groups["tax_amount_free"]
	fei.tax_amount_0 = groups["tax_amount_0"]
	fei.tax_amount_5 = groups["tax_amount_5"]
	fei.tax_amount_10 = groups["tax_amount_10"]

	fei.tax_rate = _dominant_tax_rate(fei.lines)
	fei.amount_in_words = amount_in_words_for(fei.total_amount, fei.currency)


def _copy_lines(fei, source):
	default_rate = _delivery_note_tax_rate(source)
	fei.set("lines", [])
	for item in source.items:
		rate = _line_tax_rate(item, default_rate)
		net_amount = flt(item.net_amount)
		fei.append(
			"lines",
			{
				"process_type": "1",
				"item_code": item.item_code,
				"item_name": item.item_name,
				"uom": item.uom or item.get("stock_uom") or "",
				"is_promotion": 0,
				"qty": flt(item.qty),
				"price": flt(item.rate),
				"amount": net_amount,
				"discount_rate": flt(item.get("discount_percentage")),
				"discount_amount": flt(item.get("discount_amount")) * flt(item.qty),
				"tax_rate": rate,
				"tax_amount": net_amount * (flt(rate) / 100.0) if flt(rate) > 0 else 0.0,
				"line_number": item.idx,
			},
		)


def _delivery_note_tax_rate(source):
	"""Thuế suất chung của phiếu giao, lấy từ bảng thuế (thẻ "On Net Total")."""
	for tax in source.get("taxes") or []:
		if flt(tax.rate):
			return _closest_tax_code(flt(tax.rate))
	return "0"


def _line_tax_rate(item, default_rate):
	"""Thuế suất từng dòng: ưu tiên Item Tax Template, không có thì lấy của phiếu."""
	template = item.get("item_tax_template")
	if not template:
		return default_rate
	rates = frappe.get_all(
		"Item Tax Template Detail", filters={"parent": template}, pluck="tax_rate", limit=1
	)
	return _closest_tax_code(flt(rates[0])) if rates else default_rate


def _closest_tax_code(rate):
	"""Ép về đúng bộ mã của Fast; thuế suất lạ giữ nguyên để quy tắc 12 bắt được."""
	from erpnext.einvoice.constants import NUMERIC_TAX_RATES

	for code, value in NUMERIC_TAX_RATES.items():
		if abs(value - rate) < 0.01:
			return code
	return str(int(rate)) if rate == int(rate) else str(rate)


def _dominant_tax_rate(lines):
	"""Thuế suất ghi ở master: thuế suất của phần lớn tiền hàng."""
	totals = {}
	for line in lines or []:
		totals[line.tax_rate] = totals.get(line.tax_rate, 0) + flt(line.amount)
	return max(totals, key=totals.get) if totals else "0"


def _billing_address(source, customer):
	"""⚠️ Địa chỉ trên hóa đơn là địa chỉ **xuất hóa đơn**, không phải địa chỉ giao hàng."""
	address = customer.get("customer_primary_address") or _primary_billing_address(customer.name)
	if address:
		return _one_line(_render_address(address))
	# Chốt cuối: địa chỉ hóa đơn ghi trên phiếu giao. Tuyệt đối không dùng
	# `shipping_address` — hàng giao tới kho, hóa đơn xuất về trụ sở.
	return _one_line(source.get("address_display"))


# Chỉ các phần thực sự là địa chỉ. `get_address_display` của Frappe nối thêm cả
# "Phone:" và "Email:" — trên hóa đơn thì điện thoại và email có thẻ riêng
# (PhoneNumber, EmailDeliver), nhét vào Address là ghi sai chứng từ.
_ADDRESS_PARTS = ("address_line1", "address_line2", "city", "county", "state", "country")


def _render_address(name):
	address = frappe.db.get_value("Address", name, _ADDRESS_PARTS, as_dict=True)
	if not address:
		return ""
	seen, parts = set(), []
	for fieldname in _ADDRESS_PARTS:
		value = (address.get(fieldname) or "").strip()
		if value and value.lower() not in seen:
			seen.add(value.lower())
			parts.append(value)
	return ", ".join(parts)


def _one_line(value):
	"""Địa chỉ một dòng, không thẻ HTML.

	``get_address_display`` trả về HTML có ``<br>``. Xuống dòng là lỗi 825, còn
	ký tự ``<`` ``>`` sót lại thì Fast từng lỗi 63505 — phải dọn cả hai.
	"""
	text = re.sub(r"<[^>]+>", "\n", value or "")
	return re.sub(r"[\s,]*[\r\n]+[\s,]*", ", ", text).strip().strip(",").strip()


def _primary_billing_address(customer):
	rows = frappe.get_all(
		"Dynamic Link",
		filters={"link_doctype": "Customer", "link_name": customer, "parenttype": "Address"},
		pluck="parent",
	)
	if not rows:
		return None
	billing = frappe.get_all(
		"Address",
		filters={"name": ("in", rows), "address_type": "Billing"},
		pluck="name",
		order_by="is_primary_address desc",
		limit=1,
	)
	return billing[0] if billing else rows[0]


def _contact_name(source):
	if source.get("contact_display"):
		return source.contact_display
	return ""


def _contact_value(source, customer, kind):
	field = "contact_email" if kind == "email" else "contact_mobile"
	if value := source.get(field):
		return value
	if kind == "email":
		return customer.get("email_id") or _address_field(customer.name, "email_id")
	return customer.get("mobile_no") or _address_field(customer.name, "phone")


def _address_field(customer, fieldname):
	address = _primary_billing_address(customer)
	return (frappe.db.get_value("Address", address, fieldname) or "") if address else ""


def _issuer_name(settings):
	"""HumanName — người bấm nút, hoặc người phát hành mặc định trong cấu hình."""
	return (get_fullname(frappe.session.user) or settings.default_human_name or "")[: MAX_LEN["human_name"]]


def _stamp_delivery_note(fei):
	"""Ghi ngược sang phiếu giao để kế toán thấy trạng thái ngay ở đó (mục C5)."""
	frappe.db.set_value(
		"Delivery Note",
		fei.delivery_note,
		{
			"fast_einvoice": fei.name,
			"fast_einvoice_status": fei.status,
			"fast_invoice_no": fei.fast_invoice_no or "",
			"fast_key_search": fei.fast_key_search or "",
		},
		update_modified=False,
	)

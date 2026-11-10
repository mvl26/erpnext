# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Dựng chứng từ HĐĐT từ Sales Invoice — Nút 1 và Nút 2 của mục E1 (đặc tả bản 3.0).

Không gọi Fast ở bước này: chỉ sao dữ liệu sang chứng từ HĐĐT để kế toán rà
soát. Cột "Nguồn SI" của mục C2.3 là bản đồ ánh xạ.

Hóa đơn bán là chứng từ nguồn **duy nhất** của hóa đơn gốc: doanh thu, thuế GTGT
đầu ra và công nợ đều sinh từ nó, nên hóa đơn điện tử phải khớp một — một với nó.
Phiếu giao chỉ còn là nguồn của các bản ghi lập theo bản 2.0 — Đồng bộ lại vẫn
đọc được phiếu giao cho những bản ghi đó, nhưng không lập mới từ phiếu giao nữa.
"""

import re
import unicodedata

import frappe
from frappe import _
from frappe.utils import flt, get_fullname, nowdate

from erpnext.einvoice.constants import (
	CANCEL_BLOCKING_STATUSES,
	INVOICE_TYPE_ORIGINAL,
	LIVE_STATUSES,
	MAX_LEN,
	PROCESS_TYPE_GOODS,
	RESYNC_STATUSES,
	SOURCE_DELIVERY_NOTE_V2,
	SOURCE_SALES_INVOICE,
	STATUS_CANCELLED,
	STATUS_DRAFT,
)
from erpnext.einvoice.fast_settings import check_enabled
from erpnext.einvoice.totals import amount_precision, compute_document_totals

FEI = "Fast EInvoice Document"

# Hình thức thanh toán mặc định — chuyển khoản, đúng thực tế bán buôn thiết bị y tế.
DEFAULT_PAYMENT_METHOD = "CK"

# Tài khoản thuế GTGT đầu ra (TT99: 3331x). Thuế suất chung chỉ đọc từ dòng thuế
# thuộc các tài khoản này: hóa đơn bán hay có thêm dòng phí hay thuế khác, và lấy
# dòng có tỷ lệ **đầu tiên** là lấy nhầm.
OUTPUT_VAT_ACCOUNT_PREFIX = "3331"


def fast_key_for(source_name):
	"""Key chống trùng: tên chứng từ nguồn, bỏ dấu, ≤32 ký tự (mục E1)."""
	stripped = "".join(
		c for c in unicodedata.normalize("NFD", source_name or "") if not unicodedata.combining(c)
	)
	stripped = stripped.replace("Đ", "D").replace("đ", "d")
	safe = "".join(c for c in stripped if c.isalnum() or c in "-_")
	return safe[: MAX_LEN["fast_key"]]


def _unused_key(base):
	"""Key chưa bản ghi nào dùng — thường chính là tên hóa đơn bán.

	Hóa đơn bán có hóa đơn cũ đã Hủy nội bộ (CQT từ chối) thì Key tên hóa đơn bán
	đã thuộc về hóa đơn đó trên Fast. Dùng lại thì truy vấn 370 trước phát hành
	thấy hóa đơn cũ và không cho phát hành — nên hóa đơn lập lại mang hậu tố -L2, -L3…
	"""
	candidate, index = base, 1
	while frappe.db.exists(FEI, {"fast_key": candidate}):
		index += 1
		suffix = f"-L{index}"
		candidate = base[: MAX_LEN["fast_key"] - len(suffix)] + suffix
	return candidate


@frappe.whitelist()
def create_from_sales_invoice(sales_invoice):
	"""Nút 1 — tạo chứng từ HĐĐT từ một hóa đơn bán đã submit. Trả tên bản ghi."""
	settings = check_enabled()
	source = _load_sales_invoice(sales_invoice)
	# Bản ghi được ghi bỏ qua phân quyền (kế toán HĐĐT không cần quyền sửa hóa đơn
	# bán), nên ít nhất người bấm phải **đọc** được chứng từ mình đang xuất hóa đơn.
	if not frappe.has_permission("Sales Invoice", "read", source):
		frappe.throw(_("Bạn không có quyền xem hóa đơn bán {0}.").format(source.name), frappe.PermissionError)
	_assert_no_live_invoice(source.name)
	_assert_delivery_notes_not_invoiced(source)

	fei = frappe.new_doc(FEI)
	fei.source_doctype = SOURCE_SALES_INVOICE
	fei.sales_invoice = source.name
	fei.invoice_type = INVOICE_TYPE_ORIGINAL
	fei.status = STATUS_DRAFT
	# Key sinh đúng một lần, ngay lúc tạo bản ghi (nguyên tắc A4).
	fei.fast_key = _unused_key(fast_key_for(source.name))
	_copy_from_source(fei, source, settings)

	# H6: đã kiểm quyền đọc hóa đơn bán ở trên (lý do ghi bỏ qua phân quyền: xem chú thích đó).
	fei.flags.ignore_permissions = True
	fei.insert()

	stamp_source_documents(fei.name)
	return fei.name


@frappe.whitelist()
def create_from_delivery_note(delivery_note=None):
	"""Đường phát hành của bản 2.0 — đã đóng.

	Giữ lại tên hàm vì trình duyệt còn form script cũ trong localStorage vẫn có
	thể gọi tới. Trả lời từ chối rõ ràng thay vì để lộ lỗi "method not found":
	hai đường phát hành cùng sống là nguy cơ một lần bán ra hai số hóa đơn.
	"""
	frappe.throw(
		_(
			"Từ bản 3.0, hóa đơn điện tử chỉ lập từ hóa đơn bán (Sales Invoice), không lập từ phiếu "
			"giao {0}. Lập hóa đơn bán cho phiếu giao này rồi bấm Tạo hóa đơn điện tử trên hóa đơn "
			"bán. Nếu vẫn thấy nút này trên phiếu giao, bấm Reload trong menu tài khoản."
		).format(delivery_note or ""),
		title=_("Đổi chứng từ nguồn"),
	)


@frappe.whitelist()
def resync_from_source(fei):
	"""Nút 2 — nạp lại dữ liệu từ chứng từ nguồn, ghi đè master và dòng hàng (Q7).

	Bấm là chạy, không hỏi lại. Trả ``{"ok", "changed", "message"}``: ``changed`` là
	danh sách "Trường: cũ → mới" để kế toán biết vừa đổi gì — chỉ để biết, không chặn.
	Không có gì đổi thì không lưu và **giữ nguyên trạng thái**: khách không phải
	duyệt lại một bản nháp y hệt bản đã gửi.
	"""
	settings = check_enabled()
	doc = frappe.get_doc(FEI, fei)
	# H6: bản ghi lưu bằng ignore_permissions bên dưới, nên quyền ghi phải kiểm ở đây.
	doc.check_permission("write")

	if doc.status not in RESYNC_STATUSES:
		frappe.throw(
			_("Hóa đơn đang ở trạng thái {0} nên không đồng bộ lại được từ chứng từ nguồn.").format(
				doc.status
			)
		)

	if doc.source_doctype == SOURCE_DELIVERY_NOTE_V2:
		source = _load_delivery_note(doc.delivery_note)
	else:
		source = _load_sales_invoice(doc.sales_invoice)
	before = _resync_snapshot(doc)
	_copy_from_source(doc, source, settings)
	changed = _describe_changes(doc, before, _resync_snapshot(doc))
	if not changed:
		return {
			"ok": True,
			"changed": [],
			"message": _("Dữ liệu đã khớp với chứng từ nguồn — không có gì thay đổi."),
		}

	was_draft = doc.status == STATUS_DRAFT
	# Dữ liệu vừa đổi nên mọi xác nhận trước đó của khách không còn giá trị.
	# `revision_count` đếm số lần **quay về Nháp từ 02/03/04** (mục C2.2 #19), nên
	# đồng bộ lại một bản ghi đang là Nháp thì không tính thêm một vòng sửa —
	# nếu không, ghi nhận ý kiến khách rồi đồng bộ sẽ đếm thành hai.
	if doc.status != STATUS_DRAFT:
		doc.revision_count = (doc.revision_count or 0) + 1
	doc.status = STATUS_DRAFT
	doc.flags.ignore_permissions = True
	# Nguồn thiếu địa chỉ/email vẫn phải lấy về được: lỗi hiện ở bảng kiểm tra dữ
	# liệu trên form, và chốt chặn thật nằm ở nút phát hành (`validate_before_send`).
	doc.flags.ignore_mandatory = True
	doc.save()

	stamp_source_documents(doc.name)
	message = (
		_("Đã đồng bộ lại từ chứng từ nguồn. Các trường thay đổi:")
		+ "<br>"
		+ "<br>".join(frappe.utils.escape_html(change) for change in changed)
	)
	if not was_draft:
		message += "<br><br>" + _("Hóa đơn đã về Nháp — gửi lại bản nháp cho khách nếu cần khách duyệt.")
	return {"ok": True, "changed": changed, "message": message}


# Trường master mà `_copy_from_source` ghi — đúng những gì Đồng bộ lại có thể đổi.
# Không có `invoice_date`: ngày hóa đơn luôn đặt về hôm nay, báo ra chỉ gây nhiễu.
_RESYNC_FIELDS = (
	"customer",
	"customer_code",
	"customer_name",
	"customer_tax_code",
	"customer_type",
	"address",
	"buyer",
	"phone_number",
	"email_deliver",
	"payment_method",
	"currency",
	"exchange_rate",
	"human_name",
	"totals_manual_override",
	"amount",
	"tax_amount",
	"total_amount",
)


def _resync_snapshot(doc):
	"""Giá trị so sánh được của master và dòng hàng — số làm tròn để 1.0 và 1 không "khác"."""
	master = {}
	for fieldname in _RESYNC_FIELDS:
		value = doc.get(fieldname)
		master[fieldname] = flt(value, 6) if isinstance(value, int | float) else (value or "")
	lines = [
		(
			line.item_code or "",
			line.item_name or "",
			line.uom or "",
			flt(line.qty, 6),
			flt(line.price, 6),
			flt(line.discount_amount, 6),
			str(line.tax_rate or ""),
		)
		for line in doc.lines or []
	]
	return master, lines


def _describe_changes(doc, before, after):
	"""Danh sách "Nhãn: cũ → mới" — chỉ để kế toán biết, không phải hộp xác nhận."""
	meta = frappe.get_meta(FEI)
	(old_master, old_lines), (new_master, new_lines) = before, after
	changes = [
		f"{_(meta.get_label(fieldname))}: {old_master[fieldname] or '—'} → {new_master[fieldname] or '—'}"
		for fieldname in _RESYNC_FIELDS
		if old_master[fieldname] != new_master[fieldname]
	]
	if old_lines != new_lines:
		changes.append(
			_("Dòng hàng: {0} dòng → {1} dòng (có thay đổi)").format(len(old_lines), len(new_lines))
		)
	return changes


@frappe.whitelist()
def link_sales_invoice(fei, sales_invoice):
	"""Gắn hóa đơn bán vào chứng từ HĐĐT lập theo bản 2.0 (nguồn phiếu giao).

	Đây là lối ra khi tạo từ hóa đơn bán bị từ chối vì phiếu giao đã có hóa đơn:
	hóa đơn bán được nối vào chứng từ cũ, để bảng kê lấy đúng số qua
	`sales_invoice`. Không đổi Key, không đổi `source_doctype` — Key đã nằm trên
	Fast, và bản ghi vẫn là bản ghi nguồn phiếu giao.
	"""
	doc = frappe.get_doc(FEI, fei)
	doc.check_permission("write")

	if doc.source_doctype != SOURCE_DELIVERY_NOTE_V2 or doc.invoice_type != INVOICE_TYPE_ORIGINAL:
		frappe.throw(_("Chỉ gắn hóa đơn bán vào hóa đơn gốc lập theo bản 2.0 (nguồn phiếu giao)."))
	if doc.sales_invoice:
		frappe.throw(_("Chứng từ {0} đã gắn hóa đơn bán {1}.").format(doc.name, doc.sales_invoice))

	source = _load_sales_invoice(sales_invoice)
	if not frappe.has_permission("Sales Invoice", "read", source):
		frappe.throw(_("Bạn không có quyền xem hóa đơn bán {0}.").format(source.name), frappe.PermissionError)
	if doc.delivery_note not in {item.delivery_note for item in source.items}:
		frappe.throw(
			_("Hóa đơn bán {0} không lập từ phiếu giao {1} nên không gắn vào chứng từ này được.").format(
				source.name, doc.delivery_note
			)
		)
	if existing := live_invoice_for(source.name, exclude=doc.name):
		frappe.throw(
			_("Hóa đơn bán {0} đã có chứng từ HĐĐT {1} ({2}).").format(
				source.name, existing.name, existing.status
			)
		)

	doc.sales_invoice = source.name
	doc.flags.allow_sales_invoice_link = True
	doc.flags.ignore_status_lock = True
	# H6: đã `check_permission("write")` trên chứng từ HĐĐT và kiểm đọc hóa đơn bán ở trên.
	doc.flags.ignore_permissions = True
	doc.save()

	stamp_source_documents(doc.name)
	doc.add_comment("Comment", _("Đã gắn hóa đơn bán {0}.").format(source.name))
	return {"ok": True, "message": _("Đã gắn hóa đơn bán {0}.").format(source.name)}


# --- Ánh xạ dữ liệu ----------------------------------------------------------


def _load_sales_invoice(name):
	"""Tiền điều kiện của mục E1: hóa đơn bán đã submit và là doanh thu cần xuất hóa đơn."""
	if not name or not frappe.db.exists("Sales Invoice", name):
		frappe.throw(_("Không tìm thấy hóa đơn bán {0}.").format(name or ""))

	source = frappe.get_doc("Sales Invoice", name)
	if reason := sales_invoice_refusal(source):
		frappe.throw(reason)
	return source


def sales_invoice_refusal(source):
	"""Vì sao hóa đơn bán này **không** lập hóa đơn điện tử được — rỗng là lập được.

	Dùng chung cho nút tạo, form và quy tắc 15, để ba nơi không bao giờ nói ba
	điều khác nhau về cùng một chứng từ.
	"""
	if source.docstatus != 1:
		return _("Hóa đơn bán {0} chưa được submit.").format(source.name)
	if source.get("is_return"):
		return _(
			"Hóa đơn bán trả hàng không lập hóa đơn điện tử trực tiếp — lập hóa đơn điều chỉnh giảm "
			"từ hóa đơn gốc."
		)
	if source.get("is_debit_note"):
		return _("Hóa đơn ghi nợ không lập hóa đơn gốc mới — lập hóa đơn điều chỉnh tăng từ hóa đơn gốc.")
	if source.get("is_opening") == "Yes":
		return _("Hóa đơn bán số dư đầu kỳ đã có hóa đơn ở hệ thống cũ — xuất lại là trùng hóa đơn.")
	if source.get("is_consolidated"):
		return _("Hóa đơn gộp từ POS không lập hóa đơn điện tử từ đây.")
	return ""


def _assert_no_live_invoice(sales_invoice):
	existing = live_invoice_for(sales_invoice)
	if existing:
		frappe.throw(
			_("Hóa đơn bán {0} đã có chứng từ HĐĐT {1} ({2}).").format(
				sales_invoice, existing.name, existing.status
			)
		)


def live_invoice_for(sales_invoice, exclude=None):
	"""Chứng từ HĐĐT gốc đang sống của một hóa đơn bán, nếu có.

	Chỉ tính hóa đơn **gốc**: hóa đơn điều chỉnh / thay thế cố ý mang theo hóa
	đơn bán của hóa đơn gốc để bảng kê còn lần ra được.
	"""
	filters = {
		"sales_invoice": sales_invoice,
		"invoice_type": INVOICE_TYPE_ORIGINAL,
		"status": ("in", list(LIVE_STATUSES)),
	}
	if exclude:
		filters["name"] = ("!=", exclude)
	rows = frappe.get_all(FEI, filters=filters, fields=["name", "status"], limit=1)
	return rows[0] if rows else None


def legacy_invoices_for_delivery_notes(sales_invoice):
	"""Chứng từ HĐĐT bản 2.0 (nguồn phiếu giao) đang sống của các phiếu giao trong hóa đơn bán.

	Đây là chốt chống **một lần bán, hai số hóa đơn** (mục E1, K5 #1): Key của bản
	2.0 là tên phiếu giao, Key của bản 3.0 là tên hóa đơn bán, nên truy vấn 370 của
	Fast không nhận ra hai hóa đơn cho cùng một lần giao hàng.
	"""
	notes = {
		row.delivery_note
		for row in frappe.get_all(
			"Sales Invoice Item",
			filters={"parent": sales_invoice, "parenttype": "Sales Invoice", "delivery_note": ("is", "set")},
			fields=["delivery_note"],
		)
		if row.delivery_note
	}
	if not notes:
		return []
	return frappe.get_all(
		FEI,
		filters={
			"delivery_note": ("in", sorted(notes)),
			"source_doctype": SOURCE_DELIVERY_NOTE_V2,
			"invoice_type": INVOICE_TYPE_ORIGINAL,
			"status": ("in", list(LIVE_STATUSES)),
		},
		fields=["name", "status", "delivery_note", "fast_invoice_no", "sales_invoice"],
		order_by="name asc",
	)


def _assert_delivery_notes_not_invoiced(source):
	legacy = legacy_invoices_for_delivery_notes(source.name)
	if legacy:
		frappe.throw(legacy_refusal(legacy))


def legacy_refusal(legacy):
	found = legacy[0]
	return _(
		"Phiếu giao {0} trong hóa đơn bán này đã có chứng từ HĐĐT {1} ({2}{3}) lập theo bản 2.0. "
		"Lập thêm từ hóa đơn bán là ra hai số hóa đơn cho cùng một lần bán. Mở chứng từ {1} và "
		"bấm Gắn hóa đơn bán để nối hóa đơn bán vào chứng từ đó."
	).format(
		found.delivery_note,
		found.name,
		found.status,
		_(", số {0}").format(found.fast_invoice_no) if found.fast_invoice_no else "",
	)


def _load_delivery_note(name):
	"""Nguồn của bản ghi lập theo bản 2.0 — chỉ còn dùng để Đồng bộ lại bản nháp cũ."""
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


def _copy_from_source(fei, source, settings):
	"""Sao master và dòng hàng. ``source`` là Sales Invoice, hoặc phiếu giao của bản ghi bản 2.0.

	Hai DocType cùng tên trường cho mọi thứ đọc ở đây (khách hàng, liên hệ, địa
	chỉ, tiền tệ, dòng hàng, bảng thuế), nên một hàm phục vụ cả hai.
	"""
	customer = frappe.get_doc("Customer", source.customer)

	fei.customer = source.customer
	# Không lấy `posting_date` của chứng từ nguồn: ngày hóa đơn luôn bằng ngày
	# phát hành, và lúc bấm phát hành `actions.refresh_before_send` đặt lại lần
	# nữa. Hóa đơn bán ghi sổ hôm qua, phát hành hôm nay thì hóa đơn mang ngày hôm
	# nay — `posting_date` chỉ dùng cho quy tắc 19 (cảnh báo khác kỳ kê khai).
	fei.invoice_date = nowdate()
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

	# Chứng từ nguồn chỉ là **nguồn dòng hàng**. Số tổng hợp do chứng từ tự tính
	# từ chính các dòng đó (`totals.py` là chỗ duy nhất tính tiền), không bê
	# `net_total`/`grand_total` sang: bê sang thì sửa một dòng ở đây là chứng từ
	# sai mà không chỗ nào phát hiện. Tổng của hóa đơn bán chỉ dùng để **đối
	# chiếu** — quy tắc 18.
	fei.totals_manual_override = 0
	fei.override_reason = None
	_copy_lines(fei, source)
	compute_document_totals(fei)


def _copy_lines(fei, source):
	"""Sao dòng hàng sang, đặt sao cho `SL * Đơn giá - Chiết khấu` **đúng bằng** tiền của chứng từ nguồn.

	Đơn giá lấy giá gốc (`price_list_rate`) và toàn bộ phần giảm dồn vào Tiền chiết
	khấu, nên hóa đơn vẫn nói rõ đã giảm bao nhiêu mà công thức tính lại vẫn ra
	đúng `net_amount` của chứng từ nguồn. Cố ý **không** sao `discount_percentage`:
	tỷ lệ thắng số tiền khi tính lại, mà tỷ lệ dòng không chứa phần chiết khấu toàn
	chứng từ đã phân bổ — dùng nó là mất tiền giảm đó khỏi hóa đơn.
	"""
	vat_accounts = output_vat_accounts(source.get("company"))
	default_rate = _source_tax_rate(source, vat_accounts)
	precision = amount_precision(fei.currency)
	fei.set("lines", [])
	for item in source.items:
		price, discount = _price_and_discount(item, precision)
		fei.append(
			"lines",
			{
				"process_type": PROCESS_TYPE_GOODS,
				"item_code": item.item_code,
				"item_name": item.item_name,
				"uom": item.uom or item.get("stock_uom") or "",
				"is_promotion": 0,
				"qty": flt(item.qty),
				"price": price,
				"discount_rate": 0,
				"discount_amount": discount,
				"tax_rate": _line_tax_rate(item, default_rate, vat_accounts),
				"line_number": item.idx,
			},
		)


def _price_and_discount(item, precision):
	"""Đơn giá và tiền chiết khấu của một dòng, sao cho thành tiền khớp `net_amount`."""
	qty = flt(item.qty)
	net_amount = flt(item.net_amount, precision)
	list_rate = flt(item.get("price_list_rate")) or flt(item.rate)

	discount = flt(flt(qty * list_rate, precision) - net_amount, precision)
	if discount >= 0:
		return list_rate, discount

	# Giá gốc thấp hơn tiền thực thu (phiếu có phụ phí trên dòng, hoặc giá nhập
	# tay cao hơn bảng giá): quay về đơn giá thực để thành tiền vẫn đúng.
	return (flt(net_amount / qty) if qty else 0.0), 0.0


def output_vat_accounts(company):
	"""Tài khoản thuế GTGT đầu ra (3331x) của công ty."""
	filters = {"is_group": 0, "account_number": ("like", f"{OUTPUT_VAT_ACCOUNT_PREFIX}%")}
	if company:
		filters["company"] = company
	return set(frappe.get_all("Account", filters=filters, pluck="name"))


def _source_tax_rate(source, vat_accounts):
	"""Thuế suất chung của chứng từ nguồn — chỉ đọc dòng thuộc tài khoản thuế GTGT đầu ra."""
	for tax in source.get("taxes") or []:
		if tax.account_head in vat_accounts and flt(tax.rate):
			return _closest_tax_code(flt(tax.rate))
	return "0"


def _line_tax_rate(item, default_rate, vat_accounts):
	"""Thuế suất từng dòng: ưu tiên Item Tax Template, không có thì lấy của chứng từ.

	Mẫu thuế của mặt hàng có thể khai nhiều tài khoản; chỉ dòng thuộc tài khoản
	thuế GTGT đầu ra mới là thuế suất in trên hóa đơn.
	"""
	template = item.get("item_tax_template")
	if not template:
		return default_rate
	rows = frappe.get_all(
		"Item Tax Template Detail",
		filters={"parent": template},
		fields=["tax_type", "tax_rate"],
		order_by="idx asc",
	)
	vat_rows = [row for row in rows if row.tax_type in vat_accounts] or rows
	return _closest_tax_code(flt(vat_rows[0].tax_rate)) if vat_rows else default_rate


def _closest_tax_code(rate):
	"""Ép về đúng bộ mã của Fast; thuế suất lạ giữ nguyên để quy tắc 12 bắt được."""
	from erpnext.einvoice.constants import NUMERIC_TAX_RATES

	for code, value in NUMERIC_TAX_RATES.items():
		if abs(value - rate) < 0.01:
			return code
	return str(int(rate)) if rate == int(rate) else str(rate)


def _billing_address(source, customer):
	"""⚠️ Địa chỉ trên hóa đơn là địa chỉ **xuất hóa đơn**, không phải địa chỉ giao hàng."""
	address = customer.get("customer_primary_address") or _primary_billing_address(customer.name)
	if address:
		return _one_line(_render_address(address))
	# Chốt cuối: địa chỉ hóa đơn ghi trên chứng từ nguồn. Tuyệt đối không dùng
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


def stamp_source_documents(fei_name, values=None):
	"""Ghi bản sao số hóa đơn / trạng thái lên chứng từ nguồn (mục C5) — chỉ để hiển thị.

	Chứng từ HĐĐT là nguồn sự thật duy nhất (nguyên tắc A4 thứ sáu): bản sao có
	thể trôi, nên không báo cáo nào được đọc nó. ``values`` chỉ ghi đúng các trường
	được nêu; bỏ trống thì chép lại cả bộ từ chứng từ HĐĐT.

	- Bản ghi nguồn hóa đơn bán: ghi lên Sales Invoice.
	- Bản ghi bản 2.0 (nguồn phiếu giao): vẫn ghi lên phiếu giao như trước — các
	  trường đó còn trên site (đã ẩn) chính là để sáu hóa đơn cũ không mất dấu.
	"""
	fei = frappe.db.get_value(
		FEI,
		fei_name,
		[
			"name",
			"source_doctype",
			"sales_invoice",
			"delivery_note",
			"invoice_type",
			"status",
			"fast_invoice_no",
			"fast_key_search",
			"public_pdf_url",
		],
		as_dict=True,
	)
	if not fei:
		return
	if values is None:
		values = {
			"fast_einvoice_status": fei.status,
			"fast_invoice_no": (fei.fast_invoice_no or "").strip(),
			"fast_key_search": fei.fast_key_search or "",
			"fast_einvoice_pdf_url": fei.public_pdf_url or "",
		}
		# Hủy nội bộ mở khóa chứng từ nguồn để lập lại hóa đơn: số hóa đơn đã hủy
		# không được trôi theo bản sao vào bất cứ đâu (mục E10).
		if fei.status == STATUS_CANCELLED:
			values.update({"fast_invoice_no": "", "fast_key_search": "", "fast_einvoice_pdf_url": ""})

	# Hóa đơn điều chỉnh / thay thế mang theo hóa đơn bán của hóa đơn gốc chỉ để
	# bảng kê lần ra — bản sao trên hóa đơn bán vẫn là của hóa đơn gốc.
	if fei.sales_invoice and fei.invoice_type == INVOICE_TYPE_ORIGINAL:
		_write_stamp("Sales Invoice", fei.sales_invoice, values)
	if fei.source_doctype == SOURCE_DELIVERY_NOTE_V2 and fei.delivery_note:
		_write_stamp("Delivery Note", fei.delivery_note, {"fast_einvoice": fei.name, **values})


def _write_stamp(doctype, name, values):
	"""Chỉ ghi những trường đang có trên DocType.

	Các trường là Custom Field do `einvoice.setup` dựng lúc `after_migrate`. Trên
	site chưa chạy setup (hoặc đang giữa chừng một lần cài) chúng chưa tồn tại, và
	ghi vào cột không có sẽ ném lỗi SQL — tức là làm hỏng cả hành động đang chạy.
	"""
	if not frappe.db.exists(doctype, name):
		return
	meta = frappe.get_meta(doctype)
	present = {field: value for field, value in values.items() if meta.has_field(field)}
	if present:
		frappe.db.set_value(doctype, name, present, update_modified=False)


def clear_source_stamp(doctype, name, keep_key_search=True):
	"""Xóa bản sao HĐĐT trên chứng từ nguồn — giữ `fast_key_search` làm bản sao dự phòng."""
	values = {"fast_einvoice_status": "", "fast_invoice_no": "", "fast_einvoice_pdf_url": ""}
	if doctype == "Delivery Note":
		values["fast_einvoice"] = ""
	if not keep_key_search:
		values["fast_key_search"] = ""
	_write_stamp(doctype, name, values)


# --- Hủy chứng từ nguồn (mục E1.1) -------------------------------------------


def _refuse_cancel_if_invoiced(doc, filters, label):
	"""Chặn hủy chứng từ nguồn khi hóa đơn điện tử của nó đã (hoặc có thể đã) tiêu số thật.

	Đặt ở `before_cancel` chứ không phải `on_cancel`: `before_cancel` chạy
	**trước** khi `docstatus` được ghi xuống (frappe/model/document.py:1151, còn
	`on_cancel` mãi tới 1186), nên từ chối ở đây là chưa có chữ nào rơi vào cơ sở
	dữ liệu.

	Hóa đơn đã lên Cơ quan Thuế mà chứng từ ghi doanh thu bị hủy thì sổ sách không
	còn giải thích được. Lối đi đúng là hóa đơn điều chỉnh hoặc thay thế.
	"""
	issued = frappe.get_all(
		FEI,
		filters={**filters, "status": ("in", list(CANCEL_BLOCKING_STATUSES))},
		fields=["name", "fast_invoice_no", "status"],
		order_by="creation asc",
		limit=1,
	)
	if not issued:
		return

	found = issued[0]
	frappe.throw(
		_(
			"{0} {1} đã có hóa đơn điện tử {2} (số {3}) nên không hủy được. "
			"Cần sửa thì lập hóa đơn điều chỉnh hoặc thay thế từ chứng từ đó."
		).format(label, doc.name, found.name, found.fast_invoice_no or found.status)
	)


def _allow_cancel_past_drafts(doc):
	"""Chứng từ HĐĐT chưa phát hành không được khóa việc hủy chứng từ nguồn.

	`Fast EInvoice Document` trỏ tới chứng từ nguồn bằng một Link, nên mặc định
	Frappe từ chối hủy khi còn bất kỳ chứng từ HĐĐT nào trỏ tới — kể cả một bản
	nháp chưa gửi đi đâu cả, và `LinkExistsError` không nói được vì sao. Trường
	hợp thật sự phải chặn đã do `before_cancel` lo, kèm lời giải thích.

	Chạy **sau** `on_cancel` của controller (`compose` gọi method của controller
	trước, rồi tới hook), nên chỉ **nối thêm** vào `ignore_linked_doctypes` chứ
	không gán đè cái lõi vừa đặt.
	"""
	doc.ignore_linked_doctypes = (*(doc.get("ignore_linked_doctypes") or ()), FEI)


def before_sales_invoice_cancel(doc, method=None):
	_refuse_cancel_if_invoiced(
		doc, {"sales_invoice": doc.name, "invoice_type": INVOICE_TYPE_ORIGINAL}, _("Hóa đơn bán")
	)


def on_sales_invoice_cancel(doc, method=None):
	"""Nhả các bản nháp chưa phát hành và xóa bản sao trên hóa đơn bán.

	Bản nháp vẫn còn đó, trỏ vào một hóa đơn bán đã hủy: quy tắc 15 chặn phát
	hành nó, kế toán xóa đi khi cần. Hóa đơn bán sửa lại (amend) mang tên mới,
	tức Key mới — lập chứng từ HĐĐT mới từ bản sửa lại.
	"""
	_allow_cancel_past_drafts(doc)
	clear_source_stamp("Sales Invoice", doc.name)


def before_delivery_note_cancel(doc, method=None):
	"""Chỉ còn cho bản ghi bản 2.0: phiếu giao của sáu hóa đơn cũ vẫn phải được giữ."""
	_refuse_cancel_if_invoiced(
		doc,
		{
			"delivery_note": doc.name,
			"source_doctype": SOURCE_DELIVERY_NOTE_V2,
			"invoice_type": INVOICE_TYPE_ORIGINAL,
		},
		_("Phiếu giao"),
	)


def on_delivery_note_cancel(doc, method=None):
	_allow_cancel_past_drafts(doc)
	clear_source_stamp("Delivery Note", doc.name)

# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Bảy khối nội dung dựng sẵn (BA F13).

Đây là ranh giới cố ý giữa cấu hình và mã nguồn: **nghiệp vụ chọn và sắp khối,
code dựng khối**. Người dùng chèn `{{ bang_mat_hang() }}` vào thân email và chọn
cột trong bảng cấu hình của điểm; cách dựng bảng, định dạng tiền/ngày và giới
hạn số dòng do file này lo.

Khối `nut_mo_chung_tu` và `link_bao_cao` **chỉ nội bộ** — chúng không được nạp
vào ngữ cảnh của email gửi NCC/khách (BR5), nên dù mẫu có gọi cũng không ra
đường dẫn nội bộ.

Tham chiếu: docs/superpowers/specs/2026-09-23-thong-bao-tu-thiet-lap-design.md muc 4.5.
"""

import frappe
from frappe import _
from frappe.utils import cint, get_url, get_url_to_form
from markupsafe import Markup, escape

from erpnext.supply_notification import constants
from erpnext.supply_notification.doctype.supply_notification_settings.supply_notification_settings import (
	get_settings,
)

#: Cột số thứ tự của bảng mặt hàng — không phải trường của chứng từ.
SERIAL_COLUMN = "stt"

#: Trường bảng con mặc định khi điểm chưa chọn.
DEFAULT_ITEM_TABLE = "items"

TABLE_OPEN = '<table border="1" cellpadding="6" cellspacing="0" style="border-collapse: collapse;">'


def functions(point, doc, scope: str, context: dict, triggered_by: str | None = None) -> dict:
	"""Các khối dùng được ở ngữ cảnh này."""
	# Nhận cả tham số vị trí lẫn tham số tên: người dùng gõ khoi_phan_hoi("...")
	# cũng như khoi_phan_hoi(cau="...") đều phải chạy.
	available = {
		"bang_mat_hang": lambda *args, **kwargs: item_table(point, doc, *args, **kwargs),
		"khoi_so_lieu": lambda *args, **kwargs: fact_table(point, doc, context, *args, **kwargs),
		"dia_chi_giao_hang": lambda *args, **kwargs: delivery_address(point, doc, *args, **kwargs),
		"chu_ky": lambda *args, **kwargs: signature(point, doc, *args, triggered_by=triggered_by, **kwargs),
		"khoi_phan_hoi": lambda *args, **kwargs: feedback_block(*args, **kwargs),
		"nut_mo_chung_tu": lambda *args, **kwargs: open_document(doc, *args, **kwargs),
		"link_bao_cao": lambda *args, **kwargs: report_link(*args, **kwargs),
	}

	from erpnext.supply_notification.context import INTERNAL_ONLY_BLOCKS, SCOPE_EXTERNAL

	if scope == SCOPE_EXTERNAL:
		for name in INTERNAL_ONLY_BLOCKS:
			available.pop(name, None)

	return available


# --- Bảng mặt hàng --------------------------------------------------------


def item_columns(point) -> list[tuple[str, str]]:
	rows = [(row.fieldname, row.label or row.fieldname) for row in (point.get("item_columns") or [])]
	return rows or list(constants.DEFAULT_ITEM_COLUMNS)


def item_table(point, doc, bang: str | None = None) -> Markup:
	"""Bảng dòng hàng, cột do người dùng chọn, trần dòng theo Cài đặt."""
	from erpnext.supply_notification import context as ctx

	fieldname = bang or point.get("item_table_field") or DEFAULT_ITEM_TABLE
	rows = doc.get(fieldname) or []
	if not rows:
		return Markup("")

	meta = frappe.get_meta(doc.get("doctype"))
	df = meta.get_field(fieldname)
	child_meta = frappe.get_meta(df.options) if df and df.options else None

	limit = cint(get_settings().max_item_rows) or len(rows)
	shown = rows[:limit]
	hidden = max(len(rows) - len(shown), 0)

	columns = item_columns(point)
	head = "".join(f"<th>{escape(label)}</th>" for _fieldname, label in columns)

	body = []
	for index, row in enumerate(shown, start=1):
		cells = []
		for column, _label in columns:
			if column == SERIAL_COLUMN:
				cells.append(f"<td>{index}</td>")
				continue
			value = ctx.format_value(frappe._dict(row), column, meta=child_meta)
			cells.append(f"<td>{escape(value)}</td>")
		body.append("<tr>" + "".join(cells) + "</tr>")

	note = ""
	if hidden:
		hint = escape(_("... và {0} dòng nữa, xem đầy đủ trên chứng từ.").format(hidden))
		note = f"<p><em>{hint}</em></p>"

	return Markup(f"{TABLE_OPEN}<thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>{note}")


# --- Khối số liệu ---------------------------------------------------------


def fact_rows(point) -> list[tuple[str, str, int]]:
	rows = [
		(row.fieldname, row.label or row.fieldname, cint(row.only_if_previous_empty))
		for row in (point.get("fact_rows") or [])
	]
	return rows or list(constants.default_fact_rows())


def _fact_value(point, doc, context: dict, fieldname: str) -> str:
	"""Giá trị một dòng số liệu: biến dựng sẵn trước, rồi mới tới trường chứng từ."""
	from erpnext.supply_notification import context as ctx

	if fieldname in context and not callable(context[fieldname]):
		value = context[fieldname]
		if fieldname in ("so_ngay_con_lai", "days_left"):
			return _days_left_text(value)
		return str(value or "")

	return ctx.format_value(doc, fieldname)


def _days_left_text(value) -> str:
	if value in ("", None):
		return ""
	days = cint(value)
	if days < 0:
		return _("quá hạn {0} ngày").format(abs(days))
	return _("{0} ngày").format(days)


def fact_table(point, doc, context: dict) -> Markup:
	"""Bảng nhãn — giá trị. Dòng không có giá trị tự bị bỏ."""
	body = []
	previous_filled = False

	for fieldname, label, only_if_previous_empty in fact_rows(point):
		if only_if_previous_empty and previous_filled:
			continue

		value = _fact_value(point, doc, context, fieldname)
		if not value:
			continue

		previous_filled = True
		body.append(f"<tr><td><strong>{escape(label)}</strong></td><td>{escape(value)}</td></tr>")

	if not body:
		return Markup("")

	return Markup(f"{TABLE_OPEN}<tbody>{''.join(body)}</tbody></table>")


# --- Địa chỉ giao hàng ----------------------------------------------------


def _contact_of_address(doc, point, address: str) -> frappe._dict | None:
	"""Liên hệ gắn với chứng từ, nếu không có thì liên hệ gắn thẳng với địa chỉ."""
	fieldname = point.get("contact_field")
	if fieldname and doc.get(fieldname):
		return frappe.db.get_value(
			"Contact",
			doc.get(fieldname),
			["name", "first_name", "last_name", "phone", "mobile_no"],
			as_dict=True,
		)

	rows = frappe.get_all(
		"Contact",
		filters={"address": address},
		fields=["name", "first_name", "last_name", "phone", "mobile_no"],
		order_by="is_primary_contact desc, modified desc",
		limit=1,
	)
	return rows[0] if rows else None


def _contact_name(contact: frappe._dict | None) -> str:
	if not contact:
		return ""
	return " ".join(part for part in (contact.get("first_name"), contact.get("last_name")) if part).strip()


def delivery_address(point, doc, truong: str | None = None) -> Markup:
	"""Địa chỉ giao + người nhận + điện thoại, lấy từ Address chứng từ đang trỏ tới.

	Quyết định 23/09/2026 (thay cho D21 của BA): không thêm trường mới vào
	`Address`. Chứng từ đã trỏ tới địa chỉ rồi, khối đọc thẳng từ đó; thiếu người
	nhận hay điện thoại thì **bỏ dòng đó**, không in nhãn trống. Hộp xác nhận của
	nút Thủ công và báo cáo dữ liệu thiếu lo phần nhắc nghiệp vụ bổ sung.
	"""
	fieldname = truong or point.get("address_field")
	address = doc.get(fieldname) if fieldname else None
	if not address or not frappe.db.exists("Address", address):
		return Markup("")

	lines = [f"<strong>{escape(_('Địa chỉ giao hàng:'))}</strong> {escape(address_text(address))}"]

	contact = _contact_of_address(doc, point, address)
	# Tên người nhận chỉ lấy từ Liên hệ. KHÔNG lấy `address_title`: đó là nhãn của
	# địa chỉ ("Kho Miyano"), không phải một con người — lấy nhầm thì email ghi
	# "Người nhận: Kho Miyano" và cảnh báo thiếu dữ liệu không bao giờ bật.
	person = _contact_name(contact)
	phone = frappe.get_cached_value("Address", address, "phone") or (
		contact.get("mobile_no") or contact.get("phone") if contact else ""
	)

	if person:
		receiver = " – ".join(part for part in (person, phone) if part)
		lines.append(f"<strong>{escape(_('Người nhận:'))}</strong> {escape(receiver)}")
	elif phone:
		lines.append(f"<strong>{escape(_('Điện thoại:'))}</strong> {escape(phone)}")

	return Markup("<p>" + "<br>".join(lines) + "</p>")


def address_text(address: str) -> str:
	"""Địa chỉ một dòng, không kèm thẻ HTML của Frappe."""
	from frappe.contacts.doctype.address.address import get_address_display

	try:
		display = get_address_display(address)
	except Exception:
		return address

	return frappe.utils.strip_html(display or "").replace("\n", ", ").strip(", ").strip()


# --- Chữ ký, phản hồi, liên kết -------------------------------------------


def signature(point, doc, triggered_by: str | None = None) -> Markup:
	"""Họ tên — công ty / điện thoại / email của người tạo hoặc người bấm gửi."""
	source = point.get("signature_person") or "Người tạo"
	user = triggered_by if source == "Người bấm gửi" and triggered_by else doc.get("owner")
	if not user or not frappe.db.exists("User", user):
		return Markup("")

	row = frappe.db.get_value("User", user, ["full_name", "mobile_no", "phone", "email"], as_dict=True)
	company = doc.get("company") or ""

	name_line = " – ".join(part for part in (row.full_name, company) if part)
	contact_line = " | ".join(
		part
		for part in (
			_("Điện thoại: {0}").format(row.mobile_no or row.phone) if (row.mobile_no or row.phone) else "",
			_("Email: {0}").format(row.email) if row.email else "",
		)
		if part
	)

	lines = [escape(name_line)]
	if contact_line:
		lines.append(escape(contact_line))

	return Markup("<p>" + "<br>".join(str(line) for line in lines) + "</p>")


def feedback_block(cau: str | None = None) -> Markup:
	"""Vị trí phản hồi của đối tác. CR_02 sẽ thay câu chữ này bằng hai nút."""
	text = cau or _("Quý đối tác vui lòng trả lời email này để xác nhận.")
	return Markup(f"<p><em>{escape(text)}</em></p>")


def open_document(doc, nhan: str | None = None) -> Markup:
	label = nhan or _("Mở {0} {1}").format(_(doc.get("doctype")), doc.get("name"))
	url = get_url_to_form(doc.get("doctype"), doc.get("name"))
	return Markup(f'<a href="{escape(url)}">{escape(label)}</a>')


def report_link(ten: str, nhan: str | None = None) -> Markup:
	label = nhan or _("Mở báo cáo {0}").format(_(ten))
	url = get_url(f"/app/query-report/{frappe.utils.quoted(ten)}")
	return Markup(f'<a href="{escape(url)}">{escape(label)}</a>')

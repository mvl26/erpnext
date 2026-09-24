# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Ngữ cảnh mẫu **chỉ đọc** và bộ render Jinja hộp cát.

Đây là ranh giới an toàn của cả tính năng (yêu cầu NF2). Từ khi nghiệp vụ tự sửa
được thân email, mẫu trở thành dữ liệu do người dùng nhập, nên:

* Môi trường là `ImmutableSandboxedEnvironment` — không gọi được hàm hệ thống,
  không sửa được dict/list nhận vào.
* `doc` trao cho mẫu là **bản sao dict** (`doc.as_dict()`), không phải `Document`.
  Bản build 05c truyền thẳng `Document`, nên mẫu gọi được `doc.db_set(...)` và
  đổi dữ liệu thật — lỗ hổng đó đóng tại đây.
* Biến lạ render thành chuỗi rỗng khi gửi thật (không chặn nghiệp vụ), nhưng bị
  bắt ngay lúc lưu điểm (kiểm V2) và lúc xem trước.

Tham chiếu: docs/superpowers/specs/2026-09-23-thong-bao-tu-thiet-lap-design.md muc 4.4.
"""

import html
import re

import frappe
from frappe import _
from frappe.utils import cint, flt, fmt_money, formatdate, strip_html
from jinja2 import TemplateSyntaxError, Undefined
from jinja2 import meta as jinja_meta
from jinja2.sandbox import ImmutableSandboxedEnvironment
from markupsafe import Markup

SCOPE_INTERNAL = "internal"
SCOPE_EXTERNAL = "external"

#: Trường hạn thanh toán và cặp trường dẫn chiếu — ngữ nghĩa của biến dựng sẵn
#: `han_thanh_toan` (quyết định D9 của 05c: chứng từ đề nghị thanh toán không có
#: hạn riêng, hạn nằm ở hoá đơn mà nó dẫn chiếu tới).
DUE_FIELD = "due_date"
REFERENCE_DOCTYPE_FIELD = "reference_doctype"
REFERENCE_NAME_FIELD = "reference_name"

#: Tên biến của bản build 05c, giữ lại để mẫu đã sửa trên site không gãy.
ALIASES = {
	"prefix": "tien_to",
	"party_name": "ten_doi_tac",
	"owner_name": "ten_nguoi_tao",
	"amount": "so_tien",
	"date": "ngay",
	"due": "han_thanh_toan",
	"days_left": "so_ngay_con_lai",
}

#: Biến dựng sẵn (BA F12). Dùng cho kiểm V2 và cho bảng "Có thể chèn" trên form.
BUILTIN_VARIABLES = (
	"doc",
	"tien_to",
	"ten_doi_tac",
	"ten_nguoi_tao",
	"nguoi_bam_gui",
	"so_tien",
	"ngay",
	"han_thanh_toan",
	"so_ngay_con_lai",
	"trang_thai",
	"ten_cong_ty",
	*ALIASES.keys(),
)

#: Hàm dùng được trong mẫu; khối nội bộ bị loại khỏi ngữ cảnh gửi ra ngoài (BR5).
INTERNAL_ONLY_BLOCKS = ("nut_mo_chung_tu", "link_bao_cao")
BLOCK_FUNCTIONS = (
	"bang_mat_hang",
	"khoi_so_lieu",
	"dia_chi_giao_hang",
	"chu_ky",
	"khoi_phan_hoi",
	*INTERNAL_ONLY_BLOCKS,
)
TEMPLATE_FUNCTIONS = ("truong", "mau", *BLOCK_FUNCTIONS)


class QuietUndefined(Undefined):
	"""Biến lạ ra chuỗi rỗng thay vì ném lỗi giữa lúc gửi."""

	def __str__(self):
		return ""


_HTML_ENV = ImmutableSandboxedEnvironment(autoescape=True, undefined=QuietUndefined)
_TEXT_ENV = ImmutableSandboxedEnvironment(autoescape=False, undefined=QuietUndefined)

_JINJA_TAG = re.compile(r"\{\{.*?\}\}|\{%.*?%\}", re.DOTALL)


def unescape_jinja(template: str) -> str:
	"""Trả lại `<`, `>`, `&` bên trong các cặp `{{ }}` / `{% %}`.

	Ô thân email là Text Editor (Quill). Quill escape ký tự đặc biệt trong text
	node, nên `{% if so_tien > 0 %}` được lưu thành `{% if so_tien &gt; 0 %}` và
	Jinja không hiểu. Chỉ gỡ escape **bên trong** thẻ Jinja — phần HTML còn lại
	của thư giữ nguyên.
	"""
	if not template:
		return ""
	return _JINJA_TAG.sub(lambda m: html.unescape(m.group(0)), template)


def render(template: str, context: dict, *, as_html: bool = True) -> str:
	"""Render một ô mẫu. Lỗi chỉ ghi nhật ký, không bao giờ chặn nghiệp vụ (BR1)."""
	if not template:
		return ""

	env = _HTML_ENV if as_html else _TEXT_ENV
	try:
		return env.from_string(unescape_jinja(template)).render(**context).strip()
	except Exception:
		frappe.log_error(
			title="Supply Notification: mẫu nội dung lỗi",
			message=f"{template[:500]}\n\n{frappe.get_traceback()}",
		)
		return ""


def render_text(template: str, context: dict) -> str:
	"""Render cho tiêu đề: văn bản thuần, bỏ mọi thẻ HTML lẫn trong dữ liệu."""
	return strip_html(render(template, context, as_html=False)).strip()


def validate_syntax(template: str, label: str):
	"""Kiểm V1 — cú pháp Jinja, báo lỗi tiếng Việt có vị trí."""
	if not template:
		return

	try:
		_HTML_ENV.parse(unescape_jinja(template))
	except TemplateSyntaxError as exc:
		frappe.throw(
			_("{0} lỗi cú pháp ở dòng {1}: {2}").format(label, exc.lineno, exc.message),
			title=_("Mẫu nội dung chưa hợp lệ"),
		)


def variables_used(template: str) -> set[str]:
	"""Tên biến mà mẫu tham chiếu tới — dùng cho kiểm V2."""
	if not template:
		return set()
	try:
		return jinja_meta.find_undeclared_variables(_HTML_ENV.parse(unescape_jinja(template)))
	except TemplateSyntaxError:
		return set()


def methods_called(template: str) -> set[str]:
	"""Lời gọi hàm trên chứng từ: `doc.db_set(...)`, `doc.delete()`…

	Hộp cát đã chặn ở lúc chạy (NF2); bắt thêm ở lúc lưu để người cấu hình biết
	ngay vì sao mẫu của mình không hợp lệ, thay vì thấy thư rỗng.
	"""
	if not template:
		return set()
	return set(re.findall(r"\bdoc\.([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", unescape_jinja(template)))


def fields_used(template: str) -> set[str]:
	"""Trường chứng từ mà mẫu đọc: `doc.abc` và `truong("abc")`."""
	if not template:
		return set()

	template = unescape_jinja(template)
	names = set(re.findall(r"\bdoc\.([a-zA-Z_][a-zA-Z0-9_]*)", template))
	names |= set(re.findall(r"""\btruong\(\s*['"]([^'"]+)['"]""", template))
	return names - methods_called(template)


# --- Giá trị -------------------------------------------------------------


def _meta(doc):
	return frappe.get_meta(doc.get("doctype"))


def currency_of(doc) -> str | None:
	if doc.get("currency"):
		return doc.get("currency")
	if doc.get("company"):
		return frappe.get_cached_value("Company", doc.get("company"), "default_currency")
	return None


def _link_title(options: str, value: str) -> str:
	"""Tên hiển thị của bản ghi được dẫn chiếu, khi DocType đó muốn hiện tên.

	Tín hiệu dùng ở đây là `show_title_field_in_link` — chính cờ mà Frappe dùng để
	quyết định hiện tên thay vì mã trong ô Link. Nhờ vậy `item_code` vẫn ra **mã
	vật tư** (Item đặt tên theo mã), còn DocType đặt tên bằng chuỗi băm mới hiện
	tiêu đề. Bỏ cờ này ra thì cột "Mã vật tư" trong email hoá ra tên hàng.
	"""
	if not options or not value or not frappe.db.exists("DocType", options):
		return str(value)

	meta = frappe.get_meta(options)
	title_field = meta.get_title_field()
	if not title_field or title_field == "name" or not meta.show_title_field_in_link:
		return str(value)

	title = frappe.get_cached_value(options, value, title_field)
	return str(title or value)


def format_value(doc, fieldname: str, value=None, meta=None) -> str:
	"""Giá trị đã định dạng theo kiểu trường (F11): tiền, ngày, Link, có/không."""
	meta = meta or _meta(doc)
	df = meta.get_field(fieldname) if meta else None
	if value is None:
		value = doc.get(fieldname)
	if value in (None, ""):
		return ""

	fieldtype = df.fieldtype if df else None

	if fieldtype == "Currency":
		return fmt_money(flt(value), currency=currency_of(doc))
	if fieldtype in ("Date", "Datetime"):
		return formatdate(value)
	if fieldtype == "Link":
		return strip_html(_link_title(df.options, value))
	if fieldtype == "Check":
		return _("Có") if cint(value) else _("Không")
	if fieldtype in ("Float", "Int", "Percent"):
		number = flt(value)
		return str(cint(number)) if number == cint(number) else str(number)

	return strip_html(str(value))


def _party_name(doc, point) -> str:
	"""Tên đối tác: trường do người dùng chọn, nếu trống thì dò Link Khách/NCC."""
	meta = _meta(doc)

	fieldname = point.get("party_field")
	if fieldname and doc.get(fieldname):
		return format_value(doc, fieldname, meta=meta)

	for df in meta.get_link_fields():
		if df.options in ("Customer", "Supplier") and doc.get(df.fieldname):
			return strip_html(_link_title(df.options, doc.get(df.fieldname)))

	return ""


def _user_name(user: str | None) -> str:
	if not user:
		return ""
	return frappe.get_cached_value("User", user, "full_name") or user


def _due_value(doc) -> str:
	"""Hạn thanh toán của chứng từ, tra sang chứng từ gốc khi cần (D9)."""
	meta = _meta(doc)
	if meta.has_field(DUE_FIELD) and doc.get(DUE_FIELD):
		return formatdate(doc.get(DUE_FIELD))

	ref_doctype = doc.get(REFERENCE_DOCTYPE_FIELD)
	ref_name = doc.get(REFERENCE_NAME_FIELD)
	if not ref_doctype or not ref_name or not frappe.db.exists("DocType", ref_doctype):
		return ""

	if not frappe.get_meta(ref_doctype).has_field(DUE_FIELD):
		return ""

	due = frappe.db.get_value(ref_doctype, ref_name, DUE_FIELD)
	return formatdate(due) if due else ""


def days_left_from(milestone: str | None) -> str:
	"""Số ngày còn lại suy từ mốc nhắc: `d3` là còn 3 ngày, `q1` là quá hạn 1 ngày."""
	if not milestone:
		return ""
	if milestone.startswith("d") and milestone[1:].isdigit():
		return cint(milestone[1:])
	if milestone.startswith("q") and milestone[1:].isdigit():
		return -cint(milestone[1:])
	return ""


def readonly_doc(doc) -> frappe._dict:
	"""Bản sao dict của chứng từ — mẫu không chạm được vào `Document` thật."""
	if isinstance(doc, dict):
		return frappe._dict(doc)
	return frappe._dict(doc.as_dict(no_nulls=False))


def build(point, doc, *, scope: str = SCOPE_INTERNAL, milestone=None, triggered_by=None) -> dict:
	"""Ngữ cảnh đầy đủ trao cho Jinja hộp cát."""
	from erpnext.supply_notification import blocks

	data = readonly_doc(doc)
	meta = frappe.get_meta(data.get("doctype"))

	context = {
		"doc": data,
		"tien_to": point.get("subject_prefix") or "",
		"ten_doi_tac": _party_name(data, point),
		"ten_nguoi_tao": strip_html(_user_name(data.get("owner"))),
		"nguoi_bam_gui": strip_html(_user_name(triggered_by)),
		"so_tien": format_value(data, point.get("amount_field"), meta=meta)
		if point.get("amount_field")
		else "",
		"ngay": format_value(data, point.get("main_date_field"), meta=meta)
		if point.get("main_date_field")
		else "",
		"han_thanh_toan": _due_value(data),
		"so_ngay_con_lai": days_left_from(milestone),
		"trang_thai": format_value(data, "status", meta=meta) if meta.has_field("status") else "",
		"ten_cong_ty": data.get("company") or "",
	}

	for old, new in ALIASES.items():
		context[old] = context[new]

	context["truong"] = lambda fieldname: format_value(data, fieldname, meta=meta)
	context["mau"] = lambda name: snippet(name, scope)
	context.update(blocks.functions(point, data, scope, context, triggered_by=triggered_by))

	return context


def snippet(name: str, scope: str) -> Markup:
	"""Nội dung của một Mẫu dùng chung, tôn trọng phạm vi Nội bộ / Ngoài (F14)."""
	if not name or not frappe.db.exists("Supply Notification Snippet", name):
		return Markup("")

	doc = frappe.get_cached_doc("Supply Notification Snippet", name)
	if not doc.usable_in(scope):
		return Markup("")

	return Markup(doc.content or "")


def sample_document(doctype: str) -> str | None:
	"""Chứng từ mới nhất của một DocType, để xem trước khi người dùng chưa chọn."""
	rows = frappe.get_all(doctype, pluck="name", order_by="modified desc", limit=1)
	return rows[0] if rows else None

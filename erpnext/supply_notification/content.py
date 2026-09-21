# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Dựng chủ đề và thân bài email từ chứng từ.

Ranh giới cố ý (quyết định D7): sáu trường chữ trong cấu hình do nghiệp vụ sửa và
được render bằng Jinja **hộp cát** — không đụng được `frappe` hay hàm tuỳ ý. Bảng
mặt hàng, khối số liệu, định dạng tiền/ngày và bố cục HTML do mã nguồn dựng.

Tham chiếu: docs/05c_Spec_KyThuat_Plan_Thong_Bao.md muc 8.
"""

import frappe
from frappe import _
from frappe.utils import cint, flt, fmt_money, formatdate, get_url, get_url_to_form, strip_html
from jinja2.sandbox import SandboxedEnvironment

from erpnext.supply_notification.constants import POINTS_BY_CODE, PREFIX

#: Số dòng mặt hàng tối đa liệt kê trong email, tránh thư dài vô hạn.
MAX_ITEM_ROWS = 50

STOCK_REPORT_PATH = "/app/query-report/Stock Balance"

_JINJA = SandboxedEnvironment(autoescape=False)


def _render(template: str, context: dict, fallback: str = "") -> str:
	"""Render một mẩu chữ của cấu hình; hỏng thì lùi về bản mặc định, không chặn gửi."""
	for candidate in (template, fallback):
		if not candidate:
			continue
		try:
			return _JINJA.from_string(candidate).render(**context).strip()
		except Exception:
			frappe.log_error(
				title="Supply Notification: mẫu câu chữ lỗi",
				message=f"{candidate}\n\n{frappe.get_traceback()}",
			)
	return ""


def _clean(value) -> str:
	"""Bỏ thẻ HTML lẫn trong dữ liệu chủ, giữ nguyên HTML do mẫu tự viết."""
	if value is None:
		return ""
	return strip_html(str(value)).strip()


def _currency_of(doc) -> str | None:
	if doc.meta.has_field("currency") and doc.get("currency"):
		return doc.get("currency")
	if doc.get("company"):
		return frappe.get_cached_value("Company", doc.get("company"), "default_currency")
	return None


def _money(doc, value) -> str:
	if value is None:
		return ""
	return fmt_money(flt(value), currency=_currency_of(doc))


def _owner_name(doc) -> str:
	if not doc.owner:
		return ""
	return frappe.db.get_value("User", doc.owner, "full_name") or doc.owner


def _party_name(doc, spec: dict) -> str:
	for fieldname in (spec.get("party_field"), "party_name", "customer_name", "supplier_name"):
		if fieldname and doc.meta.has_field(fieldname) and doc.get(fieldname):
			return _clean(doc.get(fieldname))
	return ""


def _due_date(doc) -> str:
	"""Hạn thanh toán của chứng từ, tra sang chứng từ gốc khi cần (quyết định D9).

	`Payment Request` không có trường hạn — hạn nằm ở hoá đơn mà nó dẫn chiếu.
	"""
	if doc.meta.has_field("due_date") and doc.get("due_date"):
		return formatdate(doc.get("due_date"))

	reference_doctype = doc.get("reference_doctype")
	reference_name = doc.get("reference_name")
	if not reference_doctype or not reference_name:
		return ""

	if not frappe.get_meta(reference_doctype).has_field("due_date"):
		return ""

	due = frappe.db.get_value(reference_doctype, reference_name, "due_date")
	return formatdate(due) if due else ""


def spec_of(point) -> dict:
	return POINTS_BY_CODE.get(point.code, {})


def build_context(point, doc, milestone: str | None = None) -> dict:
	"""Ngữ cảnh hạn chế trao cho Jinja hộp cát."""
	spec = spec_of(point)

	amount_field = spec.get("amount_field")
	date_field = spec.get("date_field")

	amount = None
	if amount_field and doc.meta.has_field(amount_field):
		amount = doc.get(amount_field)

	date_value = None
	if date_field and doc.meta.has_field(date_field):
		date_value = doc.get(date_field)

	outstanding = None
	if doc.meta.has_field("outstanding_amount"):
		outstanding = doc.get("outstanding_amount")

	return {
		"prefix": PREFIX,
		"doc": doc,
		"party_name": _party_name(doc, spec),
		"owner_name": _clean(_owner_name(doc)),
		"amount": _money(doc, amount),
		"outstanding": _money(doc, outstanding),
		"date": formatdate(date_value) if date_value else "",
		"due": _due_date(doc),
		"days_left": cint(milestone[1:]) if milestone and milestone.startswith("d") else "",
	}


def _fallback(point, key: str) -> str:
	return spec_of(point).get(key, "")


def subject(point, context: dict) -> str:
	return _render(point.subject_template, context, _fallback(point, "subject_template"))


def external_subject(point, context: dict) -> str:
	rendered = _render(
		point.external_subject_template, context, _fallback(point, "external_subject_template")
	)
	return rendered or subject(point, context)


def _item_rows(doc) -> list[dict]:
	if not doc.meta.has_field("items"):
		return []

	rows = []
	for item in (doc.get("items") or [])[:MAX_ITEM_ROWS]:
		rows.append(
			{
				"item_code": _clean(item.get("item_code")),
				"item_name": _clean(item.get("item_name")),
				"qty": flt(item.get("qty")),
				"uom": _clean(item.get("uom") or item.get("stock_uom")),
			}
		)
	return rows


def _facts(point, doc, context: dict) -> list[dict]:
	"""Khối số liệu thay cho bảng mặt hàng ở chứng từ tiền."""
	spec = spec_of(point)
	facts = []

	if context["amount"]:
		label = _("Số còn nợ") if spec.get("amount_field") == "outstanding_amount" else _("Giá trị")
		facts.append({"label": label, "value": context["amount"]})

	if context["due"]:
		facts.append({"label": _("Hạn thanh toán"), "value": context["due"]})
	elif context["date"]:
		facts.append({"label": _("Ngày"), "value": context["date"]})

	if context["days_left"] != "":
		facts.append({"label": _("Còn lại"), "value": _("{0} ngày").format(context["days_left"])})

	return facts


def internal_body(point, doc, context: dict) -> str:
	items = _item_rows(doc)
	return frappe.render_template(
		"erpnext/supply_notification/templates/internal_email.html",
		{
			"intro": _render(point.intro_template, context, _fallback(point, "intro_template")),
			"action": _render(point.action_template, context, _fallback(point, "action_template")),
			"items": items,
			"hidden_items": max(len(doc.get("items") or []) - len(items), 0),
			"facts": _facts(point, doc, context),
			"doc_url": get_url_to_form(doc.doctype, doc.name),
			"doc_label": f"{_(doc.doctype)} {doc.name}",
			"stock_url": get_url(STOCK_REPORT_PATH) if spec_of(point).get("show_stock_report") else None,
		},
	)


def external_body(point, doc, context: dict) -> str:
	intro = _render(point.external_intro_template, context, _fallback(point, "external_intro_template"))
	return frappe.render_template(
		"erpnext/supply_notification/templates/external_email.html",
		{
			"intro": intro,
			"facts": _facts(point, doc, context),
			"closing": point.external_closing or "",
		},
	)

# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Dựng tiêu đề, thân email và câu thông báo trong hệ thống.

Toàn bộ bố cục thư nay nằm trong **cấu hình**: thân email là một ô do nghiệp vụ
soạn, trong đó chèn biến, khối và mẫu dùng chung. File này chỉ còn là chỗ ghép
các mảnh lại và gắn chân thư mặc định của Cài đặt.

`compose_body` là khuôn ghép ba ô câu chữ của bản build 05c (mở đầu · bảng ·
việc cần làm) thành một thân email — dùng chung cho hạt giống site mới và cho
patch chuyển đổi, nhờ vậy hai đường cho ra cùng một kết quả.

Tham chiếu: docs/superpowers/specs/2026-09-23-thong-bao-tu-thiet-lap-design.md muc 4.6.
"""

import frappe

from erpnext.supply_notification import context as ctx
from erpnext.supply_notification.doctype.supply_notification_settings.supply_notification_settings import (
	get_settings,
)

STOCK_REPORT = "Stock Balance"


def compose_body(intro: str, action: str = "", *, show_stock_report: int = 0, external: bool = False) -> str:
	"""Ghép câu chữ + khối thành thân email, đúng bố cục mà 05c dựng bằng template."""
	parts = []
	if intro:
		parts.append(f"<p>{intro}</p>")

	parts.append("{{ khoi_so_lieu() }}")

	if external:
		if action:
			parts.append(f"<p>{action}</p>")
		return "\n".join(parts)

	parts.append("{{ bang_mat_hang() }}")

	links = ["{{ nut_mo_chung_tu() }}"]
	if show_stock_report:
		links.append('{{ link_bao_cao("' + STOCK_REPORT + '") }}')
	parts.append("<p>" + " &nbsp;·&nbsp; ".join(links) + "</p>")

	if action:
		parts.append(f"<p>{action}</p>")

	return "\n".join(parts)


def _footer(scope: str) -> str:
	settings = get_settings()
	name = (
		settings.external_footer_snippet if scope == ctx.SCOPE_EXTERNAL else settings.internal_footer_snippet
	)
	return str(ctx.snippet(name, scope)) if name else ""


def build(point, doc, *, scope=ctx.SCOPE_INTERNAL, milestone=None, triggered_by=None) -> frappe._dict:
	"""Tiêu đề, thân và câu in-app của một lần gửi."""
	context = ctx.build(point, doc, scope=scope, milestone=milestone, triggered_by=triggered_by)

	if scope == ctx.SCOPE_EXTERNAL:
		subject_template = point.external_subject_template or point.subject_template
		body_template = point.external_body_template
	else:
		subject_template = point.subject_template
		body_template = point.body_template

	subject = ctx.render_text(subject_template, context)
	prefix = (point.subject_prefix or "").strip()
	if prefix and not subject.startswith(prefix):
		subject = f"{prefix} {subject}".strip()

	body = ctx.render(body_template, context)
	footer = _footer(scope)
	if footer:
		body = f"{body}\n{footer}" if body else footer

	inapp = ctx.render_text(point.inapp_template, context) if point.inapp_template else subject

	return frappe._dict(subject=subject, body=body, inapp=inapp)

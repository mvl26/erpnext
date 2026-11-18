# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Nút logo ERP trên thanh bên trái của Raven toàn trang (`/raven/...`) để quay lại ERP.

Raven là app React riêng (không phải app của Miyano): trang của nó không nạp JS của
Desk, kể cả `raven_widget.js`. Để không phải sửa và tự build lại Raven, ERP chèn nút
vào HTML trang Raven qua hook `after_request`; nút là `public/js/raven_back_to_erp.js`,
chèn inline, kèm `data-logo` là logo Miyano ERP (`branding.get_erp_logo`). Trang ERP
vừa rời do `raven_widget.js` ghi vào localStorage.
"""

from functools import cache
from html import escape
from pathlib import Path

import frappe

from erpnext.utilities.branding import get_erp_logo

SCRIPT_FILE = Path(__file__).resolve().parent.parent / "public" / "js" / "raven_back_to_erp.js"
SCRIPT_MARKER = 'id="mvl-back-to-erp-script"'


def add_back_to_erp_button(response, request):
	"""Hook `after_request`: chèn nút "Về ERP" vào trang HTML của Raven.

	Chỉ cho user vào được Desk (System User) — Website User bấm nút cũng không vào được ERP.
	"""
	if not _is_raven_page(request, response) or not _can_use_desk():
		return

	html = response.get_data(as_text=True)
	end = html.rfind("</body>")
	if end == -1 or SCRIPT_MARKER in html:
		return
	response.set_data(html[:end] + _script_tag() + html[end:])


def _is_raven_page(request, response) -> bool:
	if response is None or request.method != "GET":
		return False
	if request.path != "/raven" and not request.path.startswith("/raven/"):
		return False
	# `is_sequence`: thân trả về đã nằm sẵn trong bộ nhớ; response stream/file thì không đụng.
	return response.status_code == 200 and response.mimetype == "text/html" and response.is_sequence


def _can_use_desk() -> bool:
	user = frappe.session.user
	return user != "Guest" and frappe.get_cached_value("User", user, "user_type") == "System User"


def _script_tag() -> str:
	logo = escape(get_erp_logo() or "", quote=True)
	return f'<script {SCRIPT_MARKER} data-logo="{logo}">{_script_source()}</script>'


@cache
def _script_source() -> str:
	return SCRIPT_FILE.read_text(encoding="utf-8")

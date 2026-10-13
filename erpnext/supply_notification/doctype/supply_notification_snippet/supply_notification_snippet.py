# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Mẫu nội dung dùng chung, chèn vào điểm bằng `{{ mau("Tên mẫu") }}` (BA mục 5.4).

Chân email, chữ ký, đoạn quy định giao nhận… viết một lần ở đây; sửa mẫu thì mọi
điểm dùng mẫu đổi theo ở lần gửi kế tiếp.
"""

import re

import frappe
from frappe import _
from frappe.model.document import Document

SCOPE_BOTH = "Cả hai"
SCOPE_INTERNAL = "Nội bộ"
SCOPE_EXTERNAL = "Ngoài"


class SupplyNotificationSnippet(Document):
	def validate(self):
		from erpnext.supply_notification import context

		context.validate_syntax(self.content, _("Nội dung mẫu"))

	def on_update(self):
		from erpnext.supply_notification import registry

		registry.clear_cache()

	def on_trash(self):
		from erpnext.supply_notification import registry

		used_by = points_using(self.name)
		if used_by:
			frappe.throw(
				_("Mẫu đang được dùng ở các điểm: {0}. Hãy gỡ khỏi các điểm đó trước khi xoá.").format(
					", ".join(used_by)
				)
			)
		registry.clear_cache()

	def usable_in(self, scope: str) -> bool:
		"""Mẫu có dùng được ở ngữ cảnh này không (`internal` hoặc `external`)."""
		if self.scope == SCOPE_BOTH or not self.scope:
			return True
		if scope == "external":
			return self.scope == SCOPE_EXTERNAL
		return self.scope == SCOPE_INTERNAL


def snippet_names_in(template: str) -> list[str]:
	"""Tên các mẫu được gọi bằng `mau("...")` trong một đoạn mẫu."""
	if not template:
		return []
	return re.findall(r"""mau\(\s*['"](.+?)['"]\s*\)""", template)


def points_using(snippet: str) -> list[str]:
	"""Mã các điểm có chèn mẫu này ở bất kỳ ô nội dung nào."""
	fields = ("body_template", "external_body_template", "subject_template", "external_subject_template")
	rows = frappe.get_all(
		"Supply Notification Point",
		fields=["name", *fields],
	)

	used = []
	for row in rows:
		for fieldname in fields:
			if snippet in snippet_names_in(row.get(fieldname) or ""):
				used.append(row.name)
				break
	return sorted(used)


@frappe.whitelist()
def usage(snippet: str) -> list[str]:
	frappe.has_permission("Supply Notification Snippet", "read", throw=True)
	return points_using(snippet)

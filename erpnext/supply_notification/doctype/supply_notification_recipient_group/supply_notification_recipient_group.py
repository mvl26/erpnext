# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Nhóm người nhận đặt tên, dùng lại ở nhiều điểm thông báo (BA mục 5.3).

Sửa một nhóm thì mọi điểm dùng nhóm đổi theo ở lần gửi kế tiếp — thay cho việc
sửa tay người nhận ở 13 chỗ.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import split_emails, validate_email_address


class SupplyNotificationRecipientGroup(Document):
	def validate(self):
		self._validate_emails()
		self._validate_not_empty()

	def on_update(self):
		from erpnext.supply_notification import registry

		registry.clear_cache()

	def on_trash(self):
		from erpnext.supply_notification import registry

		used_by = points_using(self.name)
		if used_by:
			frappe.throw(
				_("Nhóm đang được dùng ở các điểm: {0}. Hãy gỡ khỏi các điểm đó trước khi xoá.").format(
					", ".join(used_by)
				)
			)
		registry.clear_cache()

	def _validate_emails(self):
		for email in split_emails(self.fixed_emails or ""):
			validate_email_address(email, throw=True)

	def _validate_not_empty(self):
		if self.departments or self.users or (self.fixed_emails or "").strip():
			return
		frappe.throw(_("Nhóm phải có ít nhất một phòng ban, một người hoặc một email cố định."))


def points_using(group: str) -> list[str]:
	"""Mã các điểm đang trỏ tới nhóm này, ở cả người nhận nội bộ lẫn ngoài."""
	rows = frappe.get_all(
		"Supply Notification Group Link",
		filters={"group": group, "parenttype": "Supply Notification Point"},
		pluck="parent",
	)
	return sorted(set(rows))


@frappe.whitelist()
def members(group: str) -> dict:
	"""Thành viên thực tế của nhóm, để nút *Xem thành viên thực tế* trên form."""
	from erpnext.supply_notification import resolver

	doc = frappe.get_doc("Supply Notification Recipient Group", group)
	doc.check_permission("read")

	return resolver.describe_group(doc)

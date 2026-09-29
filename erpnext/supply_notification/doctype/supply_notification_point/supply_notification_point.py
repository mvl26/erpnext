# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Một điểm thông báo — toàn bộ nghiệp vụ của một loại thư nằm trong bản ghi này.

Vì nghiệp vụ tự cấu hình nên phần lớn giá trị của file này nằm ở **kiểm tra khi
lưu** (V1-V8 của BA mục 6.4): bắt lỗi ngay trên form, bằng tiếng Việt, có gợi ý —
thay vì để sai sót âm thầm biến thành thư gửi nhầm hay thư không bao giờ gửi.

Tham chiếu: docs/superpowers/specs/2026-09-23-thong-bao-tu-thiet-lap-design.md muc 3.2, 5.
"""

import difflib

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

from erpnext.supply_notification import conditions, constants, context, registry

CONTENT_FIELDS = (
	("subject_template", "Tiêu đề"),
	("body_template", "Thân email"),
	("inapp_template", "Câu thông báo trong hệ thống"),
	("external_subject_template", "Tiêu đề (ngoài)"),
	("external_body_template", "Thân email (ngoài)"),
)

EXTERNAL_CONTENT_FIELDS = ("external_subject_template", "external_body_template")

#: Dấu vết của đường dẫn nội bộ trong nội dung gửi ra ngoài (kiểm V4).
INTERNAL_URL_MARKERS = ("/app/", "/desk#", "get_url_to_form")


class SupplyNotificationPoint(Document):
	def validate(self):
		self._set_defaults()
		self._validate_reference_doctype()  # V8
		self._validate_trigger_parameters()  # V7
		self._validate_conditions()  # V3
		self._validate_templates()  # V1, V2
		self._validate_external_content()  # V4
		self._validate_print_format()  # V6
		self._validate_channels()  # V5
		self._warn()

	def on_update(self):
		registry.clear_cache()

	def after_delete(self):
		registry.clear_cache()

	def on_trash(self):
		if self.is_seed:
			frappe.throw(
				_("{0} là điểm mặc định của hệ thống. Hãy tắt điểm thay vì xoá để giữ lịch sử.").format(
					self.name
				)
			)

		if frappe.db.exists("Supply Notification Dispatch Log", {"point": self.name}):
			frappe.throw(
				_("Điểm {0} đã có lịch sử gửi. Hãy tắt điểm thay vì xoá để giữ vết đối chiếu.").format(
					self.name
				)
			)

	# --- chuẩn hoá -------------------------------------------------------

	def _set_defaults(self):
		if self.is_new() and not self.subject_prefix:
			from erpnext.supply_notification.doctype.supply_notification_settings.supply_notification_settings import (
				get_settings,
			)

			self.subject_prefix = get_settings().default_subject_prefix or constants.DEFAULT_PREFIX

		if self.trigger_event != constants.DATE_REMINDER:
			# Ô mốc nhắc có giá trị mặc định trên form; điểm không phải loại nhắc
			# theo ngày mà giữ lại giá trị đó chỉ làm người đọc cấu hình hiểu nhầm.
			self.reminder_offsets = ""
			self.date_field = None

	def reminder_offset_list(self) -> list[int]:
		"""Mốc nhắc đã chuẩn hoá: `-7, -3, -1` → [-7, -3, -1]."""
		offsets = []
		for part in (self.reminder_offsets or "").replace(";", ",").split(","):
			part = part.strip()
			if not part:
				continue
			try:
				offsets.append(int(part))
			except ValueError:
				frappe.throw(
					_("Mốc nhắc '{0}' không phải số. Ví dụ đúng: -7, -3, -1 hoặc +1, +7.").format(part)
				)
		return offsets

	# --- V8 ---------------------------------------------------------------

	def _validate_reference_doctype(self):
		if not self.reference_doctype:
			return

		if self.reference_doctype in constants.BLOCKED_DOCTYPES:
			frappe.throw(
				_("Không đặt thông báo trên {0} — đây là chứng từ hệ thống hoặc nhật ký.").format(
					_(self.reference_doctype)
				)
			)

		meta = frappe.get_meta(self.reference_doctype)
		if meta.istable:
			frappe.throw(
				_("{0} là bảng con, không đặt thông báo trực tiếp được.").format(_(self.reference_doctype))
			)
		if meta.issingle:
			frappe.throw(
				_("{0} là bản ghi cài đặt, không đặt thông báo được.").format(_(self.reference_doctype))
			)

	# --- V7 ---------------------------------------------------------------

	def _validate_trigger_parameters(self):
		if not self.reference_doctype:
			return

		meta = frappe.get_meta(self.reference_doctype)

		if self.trigger_event == constants.VALUE_CHANGE:
			self._require_field(meta, "watch_field", _("Chọn trường cần theo dõi thay đổi."))

		elif self.trigger_event == constants.WORKFLOW_TRANSITION:
			if not self.workflow_state:
				frappe.throw(_("Chọn trạng thái duyệt đích."))
			if not frappe.db.exists("Workflow", {"document_type": self.reference_doctype, "is_active": 1}):
				frappe.throw(
					_(
						"{0} chưa có quy trình duyệt (Workflow) đang bật, nên không có trạng thái để bắn."
					).format(_(self.reference_doctype))
				)

		elif self.trigger_event == constants.DATE_REMINDER:
			self._require_field(meta, "date_field", _("Chọn trường ngày để nhắc."))
			if not self.reminder_offset_list():
				frappe.throw(_("Điền ít nhất một mốc nhắc, ví dụ -7, -3, -1."))

		elif self.trigger_event == constants.MANUAL and not self.button_label:
			frappe.throw(_('Đặt nhãn cho nút trên chứng từ, ví dụ "Gửi cho NCC".'))

		if self.trigger_event in (constants.SUBMIT, constants.CANCEL) and not meta.is_submittable:
			frappe.throw(
				_("{0} không phải chứng từ ghi sổ được, nên không có thời điểm Ghi sổ / Huỷ.").format(
					_(self.reference_doctype)
				)
			)

	def _require_field(self, meta, fieldname: str, message: str):
		value = self.get(fieldname)
		if not value:
			frappe.throw(message)
		self._assert_field_exists(meta, value, self.meta.get_label(fieldname))

	def _assert_field_exists(self, meta, fieldname: str, label: str):
		if meta.has_field(fieldname):
			return
		frappe.throw(
			_("{0}: trường {1} không có trên {2}.{3}").format(
				label, fieldname, _(self.reference_doctype), _suggestion(meta, fieldname)
			)
		)

	# --- V3 ---------------------------------------------------------------

	def _validate_conditions(self):
		if not self.reference_doctype:
			return

		meta = frappe.get_meta(self.reference_doctype)

		for row in self.conditions or []:
			table, fieldname = conditions.split_fieldname(row.fieldname)
			target_meta = meta

			if table:
				parent_df = meta.get_field(table)
				if not parent_df or parent_df.fieldtype not in ("Table", "Table MultiSelect"):
					frappe.throw(
						_("Điều kiện dòng {0}: {1} không phải bảng con của {2}.").format(
							row.idx, table, _(self.reference_doctype)
						)
					)
				target_meta = frappe.get_meta(parent_df.options)

			if not target_meta.has_field(fieldname):
				frappe.throw(
					_("Điều kiện dòng {0}: trường {1} không có trên {2}.{3}").format(
						row.idx, fieldname, _(target_meta.name), _suggestion(target_meta, fieldname)
					)
				)

			if row.operator not in conditions.OPERATORS:
				frappe.throw(_("Điều kiện dòng {0}: toán tử không hợp lệ.").format(row.idx))

			if row.operator in conditions.VALUELESS_OPERATORS:
				row.value = ""
			elif not (row.value or "").strip():
				frappe.throw(_("Điều kiện dòng {0}: chưa điền giá trị so sánh.").format(row.idx))
			else:
				self._validate_condition_value(target_meta, row)

	def _validate_condition_value(self, meta, row):
		df = meta.get_field(conditions.split_fieldname(row.fieldname)[1])
		if not df or df.fieldtype != "Select" or not df.options:
			return

		allowed = [option.strip() for option in df.options.split("\n") if option.strip()]
		values = (
			conditions.split_values(row.value)
			if row.operator in (conditions.IN, conditions.NOT_IN)
			else [row.value.strip()]
		)

		for value in values:
			if value not in allowed:
				frappe.throw(
					_("{0} không có giá trị '{1}'. Chọn một trong: {2}").format(
						_(df.label or df.fieldname), value, ", ".join(allowed)
					)
				)

	# --- V1, V2 -----------------------------------------------------------

	def _validate_templates(self):
		if not self.reference_doctype:
			return

		meta = frappe.get_meta(self.reference_doctype)
		known = set(context.BUILTIN_VARIABLES) | set(context.TEMPLATE_FUNCTIONS)

		for fieldname, label in CONTENT_FIELDS:
			template = self.get(fieldname)
			if not template:
				continue

			context.validate_syntax(template, _(label))

			for method in context.methods_called(template):
				frappe.throw(
					_("{0}: mẫu chỉ được đọc dữ liệu chứng từ, không gọi được hàm {1}().").format(
						_(label), method
					)
				)

			for name in context.variables_used(template) - known:
				frappe.throw(
					_("{0}: không có biến {1}. Dùng nút Chèn trường để chèn đúng tên.").format(_(label), name)
				)

			for name in context.fields_used(template):
				if meta.has_field(name) or name in ("name", "owner", "doctype", "creation", "modified"):
					continue
				frappe.throw(
					_("{0}: trường {1} không có trên {2}.{3}").format(
						_(label), name, _(self.reference_doctype), _suggestion(meta, name)
					)
				)

	# --- V4 ---------------------------------------------------------------

	def _validate_external_content(self):
		for fieldname in EXTERNAL_CONTENT_FIELDS:
			template = self.get(fieldname) or ""
			if not template:
				continue

			for marker in INTERNAL_URL_MARKERS:
				if marker in template:
					frappe.throw(
						_("Email gửi NCC/khách không được chứa đường dẫn nội bộ ({0}).").format(marker)
					)

			for block in context.INTERNAL_ONLY_BLOCKS:
				if block in context.variables_used(template) or f"{block}(" in template:
					frappe.throw(
						_("Khối {0} chỉ dùng cho email nội bộ, không đặt vào nội dung gửi ra ngoài.").format(
							block
						)
					)

			self._validate_external_snippets(template)

	def _validate_external_snippets(self, template: str):
		from erpnext.supply_notification.doctype.supply_notification_snippet.supply_notification_snippet import (
			snippet_names_in,
		)

		for name in snippet_names_in(template):
			if not frappe.db.exists("Supply Notification Snippet", name):
				frappe.throw(_("Không có mẫu dùng chung tên '{0}'.").format(name))

			scope = frappe.db.get_value("Supply Notification Snippet", name, "scope")
			if scope == "Nội bộ":
				frappe.throw(
					_("Mẫu '{0}' chỉ dùng cho nội bộ, không chèn được vào email gửi ra ngoài.").format(name)
				)

	# --- V6, V5 -----------------------------------------------------------

	def _validate_print_format(self):
		if not self.attach_pdf:
			self.print_format = None
			self.require_pdf = 0
			return

		if not self.print_format:
			frappe.throw(_("Đã bật đính PDF thì phải chọn mẫu in."))

		doc_type = frappe.db.get_value("Print Format", self.print_format, "doc_type")
		if doc_type != self.reference_doctype:
			frappe.throw(
				_("Mẫu in {0} dành cho {1}, không dùng được cho {2}.").format(
					self.print_format, doc_type, _(self.reference_doctype)
				)
			)

	def has_internal_recipients(self) -> bool:
		return bool(
			self.departments
			or self.users
			or self.recipient_groups
			or self.user_fields
			or self.notify_owner
			or self.notify_triggering_user
		)

	def has_external_recipients(self) -> bool:
		return bool(
			self.external_party_contact
			or self.external_email_fields
			or (self.external_fixed_emails or "").strip()
			or self.external_groups
		)

	def _validate_channels(self):
		if not self.enabled:
			return

		if not (self.send_email or self.send_inapp or self.notify_external):
			frappe.throw(_("Điểm đang bật thì phải mở ít nhất một kênh gửi."))

		if (self.send_email or self.send_inapp) and not self.has_internal_recipients():
			frappe.throw(_("Đã bật kênh nội bộ nhưng chưa chọn người nhận."))

		if self.notify_external and not self.has_external_recipients():
			frappe.throw(_("Đã bật email ra ngoài nhưng chưa chọn nguồn người nhận ngoài."))

		if self.notify_external and not (self.external_subject_template or self.subject_template):
			frappe.throw(_("Email ra ngoài chưa có tiêu đề."))

	# --- cảnh báo không chặn ---------------------------------------------

	def _warn(self):
		from erpnext.supply_notification.doctype.supply_notification_settings.supply_notification_settings import (
			get_settings,
		)

		messages = []
		settings = get_settings()

		if settings.test_mode:
			messages.append(_("Đang bật <b>Chế độ thử</b>: mọi thư sẽ về {0}.").format(settings.test_email))

		if not settings.enabled:
			messages.append(_("Tính năng thông báo đang <b>tắt toàn cục</b> trong Cài đặt thông báo."))

		if self.enabled and self.has_value_changed("enabled") and self.trigger_event != constants.MANUAL:
			messages.append(_("Điểm vừa bật sẽ gửi ngay ở lần chứng từ kế tiếp thoả điều kiện."))

		if self.trigger_event == constants.DATE_REMINDER and not cint(
			frappe.db.get_single_value("System Settings", "enable_scheduler")
		):
			messages.append(_("Scheduler đang tắt nên nhắc theo ngày sẽ không chạy."))

		messages.extend(self._department_warnings())

		if messages:
			frappe.msgprint("<br>".join(messages), title=_("Lưu ý"), indicator="orange", alert=False)

	def _department_warnings(self) -> list[str]:
		from erpnext.supply_notification import resolver

		names = [row.department for row in (self.departments or []) if row.department]
		if not names:
			return []

		missing = resolver.employees_without_user(names)
		if not missing:
			return []

		return [
			_("{0} nhân viên thuộc phòng ban đã chọn chưa gắn tài khoản nên không nhận được: {1}").format(
				len(missing), ", ".join(sorted(missing)[:10])
			)
		]


def _suggestion(meta, fieldname: str) -> str:
	"""Gợi ý tên trường gần đúng — phần "Có phải ý bạn là..." của V2/V3."""
	candidates = [df.fieldname for df in meta.fields if df.fieldname]
	close = difflib.get_close_matches(fieldname, candidates, n=1, cutoff=0.6)
	if not close:
		return ""
	return " " + _("Có phải ý bạn là {0}?").format(close[0])

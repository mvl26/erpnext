# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Danh mục 23 loại chứng từ TBYT và mức áp dụng của chúng theo phân loại."""

import frappe
from frappe import _
from frappe.model.document import Document

from erpnext.tbyt.constants import LEVEL_BB_STAR


class TBYTDocumentType(Document):
	def validate(self):
		self._validate_one_rule_per_device_class()
		self._validate_condition_belongs_to_bb_star()

	def _validate_one_rule_per_device_class(self):
		"""Hai dòng cùng phân loại làm mức áp dụng thành nhập nhằng."""
		seen = set()
		for row in self.rules:
			if row.device_class in seen:
				frappe.throw(_("Phân loại {0} bị khai hai lần trong bảng quy tắc.").format(row.device_class))
			seen.add(row.device_class)

	def _validate_condition_belongs_to_bb_star(self):
		"""Điều kiện chỉ có nghĩa với BB*; gắn vào mức khác là nhập nhầm."""
		for row in self.rules:
			if row.condition and row.level != LEVEL_BB_STAR:
				frappe.throw(
					_("Dòng phân loại {0}: điều kiện chỉ dùng cho mức {1}, không dùng cho mức {2}.").format(
						row.device_class, LEVEL_BB_STAR, row.level
					)
				)

	def level_for(self, device_class: str) -> tuple[str | None, str | None]:
		"""Trả về (mức, điều kiện) của một phân loại, hoặc (None, None) nếu không khai."""
		for row in self.rules:
			if row.device_class == device_class:
				return row.level, row.condition
		return None, None

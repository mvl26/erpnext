# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Sổ đăng ký chứng từ pháp lý — một bản ghi là một tờ giấy có thật.

Chứng từ KHÔNG gắn vào Item. Nó gắn vào chủ thể mà nó nói về (công ty, chủ sở
hữu, số lưu hành, lô), và Item phân giải ngược chuỗi để dựng bộ hồ sơ của mình.
Nhờ vậy gia hạn một tờ CFS là sửa một bản ghi, không phải sửa 300 dòng.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, getdate

from erpnext.tbyt.constants import SCOPE_DOCTYPE
from erpnext.tbyt.expiry import compute_document_status
from erpnext.tbyt.folders import place_file
from erpnext.tbyt.refresh import refresh_for_document


class TBYTRegulatoryDocument(Document):
	def validate(self):
		self._fill_scope_doctype()
		self._validate_expiry_is_declared()
		self._validate_scope_count()
		self._validate_scope_rows_are_distinct()
		self._validate_single_owner()
		self._validate_no_duplicate_scope()
		self._validate_expiry_is_unambiguous()
		self._validate_date_order()
		self._set_status()

	def on_update(self):
		self._supersede_previous()
		place_file(self)
		refresh_for_document(self)

	def on_trash(self):
		refresh_for_document(self)

	def _validate_links(self):
		"""Frappe tự kiểm tra Dynamic Link ngay trong `insert()`/`_save()`, TRƯỚC khi
		gọi `validate()` — sớm hơn cả `before_insert`. Nếu chỉ điền `scope_doctype`
		trong `validate()` như bình thường thì bước kiểm tra sẵn có của khung sườn
		chạy trước, thấy `scope_doctype` còn trống ứng với `scope_name` đã có giá
		trị, và chặn lại với lỗi chung chung. Đón đầu ở đây để điền trước khi khung
		sườn tự kiểm tra.
		"""
		self._fill_scope_doctype()
		super()._validate_links()

	def _fill_scope_doctype(self):
		"""Người dùng chỉ chọn đối tượng; cấp phạm vi suy từ loại chứng từ."""
		scope_level = frappe.db.get_value("TBYT Document Type", self.document_type, "scope_level")
		expected = SCOPE_DOCTYPE.get(scope_level)
		if not expected:
			frappe.throw(
				_("Loại chứng từ {0} ở cấp {1} không gắn được vào bản ghi nào.").format(
					self.document_type, scope_level
				)
			)
		for row in self.pham_vi:
			row.scope_doctype = expected

	def _validate_expiry_is_declared(self):
		"""Nửa server của tri-state. `mandatory_depends_on` chỉ chặn ở trình duyệt.

		Không có hàm này thì tổ hợp "chưa tích Vô thời hạn mà bỏ trống ngày" vẫn lưu
		được qua import, API hay test — và đúng khoảng mờ mà tri-state sinh ra để xoá
		sẽ mở lại.
		"""
		if not cint(self.khong_thoi_han) and not self.ngay_het_han:
			frappe.throw(
				_("Chưa tích Vô thời hạn thì bắt buộc phải điền Ngày hết hạn."),
				frappe.MandatoryError,
			)

	def _validate_expiry_is_unambiguous(self):
		if cint(self.khong_thoi_han) and self.ngay_het_han:
			frappe.throw(_("Đã tích Vô thời hạn thì không được điền Ngày hết hạn. Bỏ một trong hai."))

	def _validate_date_order(self):
		if self.ngay_cap and self.ngay_het_han and getdate(self.ngay_het_han) < getdate(self.ngay_cap):
			frappe.throw(_("Ngày hết hạn không được trước Ngày cấp."))

	def _set_status(self):
		self.trang_thai = compute_document_status(
			is_active=self.is_active,
			khong_thoi_han=self.khong_thoi_han,
			ngay_het_han=self.ngay_het_han,
		)

	def _validate_scope_count(self):
		"""Loại không cho nhiều phạm vi thì đúng một dòng — nhiều hơn là nhập nhầm."""
		allows_many = frappe.db.get_value("TBYT Document Type", self.document_type, "cho_phep_nhieu_pham_vi")
		if not cint(allows_many) and len(self.pham_vi) > 1:
			frappe.throw(
				_("Loại chứng từ {0} chỉ nhận một phạm vi, đang khai {1}.").format(
					self.document_type, len(self.pham_vi)
				)
			)

	def _validate_scope_rows_are_distinct(self):
		seen = set()
		for row in self.pham_vi:
			if row.scope_name in seen:
				frappe.throw(_("Đối tượng {0} bị khai hai lần trong bảng phạm vi.").format(row.scope_name))
			seen.add(row.scope_name)

	def _validate_single_owner(self):
		"""Chứng từ đa phạm vi phải nằm gọn trong một chủ sở hữu.

		Một file chỉ nằm được ở một thư mục (§7 đặc tả), và cả bốn loại đa phạm
		vi đều do chủ sở hữu cấp — trải hai hãng là dấu hiệu khai nhầm.
		"""
		if len(self.pham_vi) < 2:
			return
		if self.pham_vi[0].scope_doctype != "TBYT Marketing Authorization":
			return
		owners = {
			frappe.db.get_value("TBYT Marketing Authorization", row.scope_name, "chu_so_huu")
			for row in self.pham_vi
		}
		if len(owners) > 1:
			frappe.throw(
				_("Các số lưu hành trong bảng phạm vi thuộc {0} chủ sở hữu khác nhau.").format(len(owners))
			)

	def _validate_no_duplicate_scope(self):
		"""Không cho hai bản ghi còn hiệu lực cùng loại phủ cùng một đối tượng.

		Đây là ràng buộc bảo đảm resolver tất định: mỗi (loại, đối tượng) có
		nhiều nhất một bản ghi đang hiệu lực.

		Loại trừ bản ghi được khai ở `thay_the_cho`: `on_update` (chạy sau
		`validate`) mới tắt `is_active` của nó, nên tại thời điểm này bản cũ
		vẫn còn hiệu lực trong DB — không loại trừ thì không bao giờ gia hạn
		được qua trường Thay thế cho.
		"""
		if not cint(self.is_active):
			return
		for row in self.pham_vi:
			clash = frappe.db.sql(
				"""
				select rd.name
				from `tabTBYT Regulatory Document` rd
				inner join `tabTBYT Document Scope` sc on sc.parent = rd.name
				where rd.document_type = %(document_type)s
					and rd.is_active = 1
					and rd.name != %(name)s
					and rd.name != %(thay_the_cho)s
					and sc.parenttype = 'TBYT Regulatory Document'
					and sc.scope_doctype = %(scope_doctype)s
					and sc.scope_name = %(scope_name)s
				limit 1
				""",
				{
					"document_type": self.document_type,
					"name": self.name or "",
					"thay_the_cho": self.thay_the_cho or "",
					"scope_doctype": row.scope_doctype,
					"scope_name": row.scope_name,
				},
			)
			if clash:
				frappe.throw(
					_(
						"{0} của {1} đã có bản ghi còn hiệu lực: {2}. "
						"Nếu đây là bản gia hạn, hãy khai nó ở trường Thay thế cho."
					).format(self.document_type, row.scope_name, clash[0][0])
				)

	def _supersede_previous(self):
		"""Khai Thay thế cho là đủ — bản cũ tự rút lui, không cần thao tác hai bước."""
		if not self.thay_the_cho:
			return
		previous = frappe.get_doc("TBYT Regulatory Document", self.thay_the_cho)
		if not cint(previous.is_active):
			return
		previous.is_active = 0
		previous.flags.ignore_permissions = True
		previous.save()

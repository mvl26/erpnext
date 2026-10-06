"""Thẻ PDA của một người dùng. Luật nghiệp vụ nằm ở `vitri/the_pda.py`;
ở đây chỉ là phép kiểm KHÔNG ĐƯỢC PHÉP VƯỢT dù ghi bằng đường nào."""

import frappe
from frappe import _
from frappe.model.document import Document

from erpnext.warehouse_operations.vitri.the_pda import VAI_TRO_DUOC_DUNG_THE


class PDABadge(Document):
	def validate(self):
		#: Chỉ kiểm yêu cầu tài khoản lúc CẤP THẺ. Người đã nghỉ việc (bị khoá tài khoản)
		#: hoặc đã bị rút vai trò kho vẫn phải THU HỒI ĐƯỢC thẻ, nên validate() không được
		#: chặn tại save() khi gọi từ thu_hoi(). Kiểm theo con_hieu_luc: chỉ áp dụng khi
		#: thẻ còn hiệu lực (lúc cấp). Thẻ bị tắt (lúc thu hồi) cho phép lưu.
		if self.con_hieu_luc:
			if not frappe.db.get_value("User", self.nguoi_dung, "enabled"):
				frappe.throw(_("Tài khoản {0} đang bị khoá — không cấp thẻ PDA được.").format(self.nguoi_dung))
			if not (VAI_TRO_DUOC_DUNG_THE & set(frappe.get_roles(self.nguoi_dung))):
				frappe.throw(
					_(
						"{0} không có vai trò kho nào nên thẻ PDA sẽ không mở được màn hình nào. "
						"Cấp vai trò Stock User trước, rồi cấp thẻ."
					).format(self.nguoi_dung)
				)
		self.ho_ten = frappe.db.get_value("User", self.nguoi_dung, "full_name")

"""Bài smoke: module đăng ký được và móc hook thật sự nối vào.

VIẾT LẠI 11/09/2026 khi chuyển từ app riêng `miyano_wms` vào thẳng cây
ERPNext. Bản cũ khoá "app `miyano_wms` có trong installed_apps" — câu đó nay
vô nghĩa, và hai trong ba bài của nó trở thành bản sao của nhau
(`assertIn("erpnext", ...)` hai lần).

Thứ đáng khoá ở chỗ ở mới khác hẳn: toàn bộ tầng vị trí treo trên ĐÚNG MỘT
móc `Stock Ledger Entry.on_submit` khai trong `erpnext/hooks.py`. Đó là dòng
duy nhất phải chèn vào file của upstream, nên nó cũng là dòng dễ mất nhất
trong mọi lần merge ERPNext bản mới: xung đột ở `hooks.py` mà giải sai thì
hook biến mất, hệ vẫn chạy, chứng từ vẫn ghi được, chỉ là **không ô nào được
ghi sổ nữa** — im lặng hoàn toàn cho tới lần đối soát kế tiếp.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

HANDLER = "erpnext.vi_tri_kho.vitri.hook_sle.ghi_so_vi_tri"


class TestModuleKhoiDong(FrappeTestCase):
	def test_module_thuoc_app_erpnext(self):
		self.assertEqual(
			frappe.db.get_value("Module Def", "Vi Tri Kho", "app_name"),
			"erpnext",
			"Module 'Vi Tri Kho' phải thuộc app erpnext — kiểm erpnext/modules.txt",
		)

	def test_hook_sle_duoc_dang_ky(self):
		"""Chặn đúng kiểu hỏng của một lần merge upstream giải sai."""
		tay_cam = frappe.get_hooks("doc_events").get("Stock Ledger Entry", {}).get("on_submit") or []
		if isinstance(tay_cam, str):
			tay_cam = [tay_cam]
		self.assertIn(
			HANDLER,
			tay_cam,
			f"Móc {HANDLER} không còn trong doc_events. Không có nó thì mọi chứng từ "
			"kho vẫn chạy bình thường nhưng KHÔNG dòng sổ vị trí nào được ghi — "
			"hỏng trong im lặng. Kiểm doc_events trong erpnext/hooks.py.",
		)

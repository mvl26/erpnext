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

HANDLER = "erpnext.warehouse_operations.vitri.hook_sle.ghi_so_vi_tri"


class TestModuleKhoiDong(FrappeTestCase):
	def test_module_thuoc_app_erpnext(self):
		self.assertEqual(
			frappe.db.get_value("Module Def", "Warehouse Operations", "app_name"),
			"erpnext",
			"Module 'Warehouse Operations' phải thuộc app erpnext — kiểm erpnext/modules.txt",
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

	def test_dam_bao_cay_da_dung_duoc_dang_ky_trong_after_migrate(self):
		"""Vòng sửa 2/5 (Task 8): `dam_bao_cay_da_dung` PHẢI có trong
		`after_migrate` — đây là cơ chế HỘI TỤ, không phải patch một lần. Mất
		dòng này ở một lần merge upstream giải sai: patch
		`v15_0.dung_lai_cay_vi_tri` (chạy một lần, bị `Patch Log` khoá) vẫn
		còn, nhưng nếu nó từng gặp `disabled=1` và bỏ qua, cây sẽ KHÔNG BAO
		GIỜ được dựng lại nữa — hai tính năng "thừa kế disabled" và "lấy hàng
		theo phạm vi" nằm im vĩnh viễn, không ai biết, không có gì báo lỗi."""
		HAM = "erpnext.warehouse_operations.vitri.cay.dam_bao_cay_da_dung"
		danh_sach = frappe.get_hooks("after_migrate") or []
		self.assertIn(
			HAM,
			danh_sach,
			f"Hàm {HAM} không còn trong after_migrate. Đây là cơ chế HỘI TỤ LẠI ở "
			"mọi lần bench migrate — mất nó thì một khi patch dung_lai_cay_vi_tri "
			"từng bỏ qua vì gặp disabled=1, cây vĩnh viễn không được dựng lại. "
			"Kiểm after_migrate trong erpnext/hooks.py.",
		)

	def test_hook_doi_ten_mat_hang_duoc_dang_ky(self):
		"""Móc thứ hai của module trong `hooks.py`, và cũng dễ mất y như móc
		SLE. Mất nó thì đổi mã một mặt hàng làm bản ghi gán của nó âm thầm trỏ
		về mã cũ ở lần lưu kế tiếp — không lỗi, không dấu vết."""
		HAM = "erpnext.warehouse_operations.vitri.gan.doi_ten_theo_mat_hang"
		tay_cam = frappe.get_hooks("doc_events").get("Item", {}).get("after_rename") or []
		if isinstance(tay_cam, str):
			tay_cam = [tay_cam]
		self.assertIn(
			HAM,
			tay_cam,
			f"Móc {HAM} không còn trong doc_events['Item']['after_rename']. "
			"Mất nó thì đổi mã mặt hàng làm gán vị trí revert về mã cũ trong "
			"im lặng. Kiểm doc_events trong erpnext/hooks.py.",
		)

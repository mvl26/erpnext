"""`Warehouse Location Setup` — validate() cấp doctype.

VÒNG SỬA 1 (review điều phối): `_kiem_tra_kho` (RPC, `bat_kho.py`) và
`WarehouseLocationSetup.validate()` cùng chặn kho tổng nhưng trước đó dùng
hai chuỗi thông báo khác nhau — lệch đúng loại mà triết lý "một nguồn sự
thật duy nhất" của task này chống, chỉ là ở tầng validate thay vì tầng tồn
kho. Đã gộp qua `bat_kho.kiem_tra_khong_phai_kho_tong` dùng chung. Trước
vòng sửa này KHÔNG bài nào chạm `validate()` — RPC test không đi qua
Document.validate(), chỉ đi qua `_kiem_tra_kho`.
"""

import frappe
from frappe.tests.utils import FrappeTestCase


class TestValidateChanKhoTong(FrappeTestCase):
	def test_validate_chan_kho_tong(self):
		doc = frappe.get_doc({
			"doctype": "Warehouse Location Setup",
			"kho": "All Warehouses - MYN",
		})
		with self.assertRaises(frappe.ValidationError) as ctx:
			doc.insert(ignore_permissions=True)
		self.assertIn("kho tổng", str(ctx.exception).lower())
		self.assertFalse(
			frappe.db.exists("Warehouse Location Setup", "All Warehouses - MYN"),
			"validate() throw phải chặn insert, không được để lọt bản ghi.",
		)

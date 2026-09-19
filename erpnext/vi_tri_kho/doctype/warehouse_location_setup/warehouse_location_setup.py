from frappe.model.document import Document

from erpnext.vi_tri_kho.vitri.bat_kho import kiem_tra_khong_phai_kho_tong


class WarehouseLocationSetup(Document):
	def validate(self):
		# Dùng chung với `bat_kho._kiem_tra_kho` — một nguồn thông báo duy
		# nhất (vòng sửa 1, review điều phối): trước đây hai nơi chặn cùng
		# điều kiện "kho tổng" bằng hai chuỗi thông báo khác nhau.
		kiem_tra_khong_phai_kho_tong(self.kho)

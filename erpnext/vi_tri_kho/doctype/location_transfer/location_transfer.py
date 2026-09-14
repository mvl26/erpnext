"""Phiếu xếp / chuyển vị trí — spec 2026-09-14.

Phiếu KHÔNG sinh Stock Ledger Entry và không gọi bất cứ hàm nào của
`erpnext/stock/`. Chuyển giữa hai ô trong cùng kho không làm đổi
`Bin.actual_qty` (Bin theo KHO, không theo ô), nên sinh SLE sẽ vừa đẻ hai
dòng sổ kho triệt tiêu nhau, vừa KÍCH LẠI hook `Stock Ledger Entry.on_submit`
→ `ghi_so_vi_tri` dồn hàng vào `ZZZ-CHUA-XEP` một lần nữa, đúng thứ phiếu
này vừa gỡ ra. Xem spec §4.

Ràng buộc "cùng kho" (K2) không phải quy tắc nghiệp vụ tuỳ chọn: nó là
ĐIỀU KIỆN để bất biến §3 ("tổng tồn các ô = Bin.actual_qty") tự giữ. Mỗi
dòng ghi -n ở ô nguồn và +n ở ô đích trong cùng một kho nên tổng của kho
không đổi, kể cả khi mọi logic khác ở đây sai. Bỏ ràng buộc đó ra là phải
tự giữ bất biến bằng tay — và loại lệch ấy thì đối soát theo tổng không
bắt được.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from erpnext.vi_tri_kho.vitri.kho import kho_co_quan_ly_vi_tri


class LocationTransfer(Document):
	def validate(self):
		self.kiem_tra_kho()
		self.kiem_tra_cac_dong()

	def kiem_tra_kho(self):
		"""K1 — không bật quản lý vị trí thì không có sổ vị trí để ghi."""
		if not kho_co_quan_ly_vi_tri(self.kho):
			frappe.throw(
				_(
					"Kho {0} chưa bật quản lý vị trí nên không có sổ vị trí để ghi. "
					"Bật ở màn hình Warehouse Location Setup trước."
				).format(self.kho)
			)

	def kiem_tra_cac_dong(self):
		if not self.items:
			frappe.throw(_("Phiếu phải có ít nhất một dòng."))
		for d in self.items:
			self._kiem_mot_dong(d)

	def _kiem_mot_dong(self, d):
		vi_tri = _("Dòng {0}").format(d.idx)

		# K7. `so_luong` cố ý KHÔNG đặt `reqd = 1` trong JSON: để `reqd` thì
		# Frappe ném MandatoryError cho giá trị 0 TRƯỚC khi tới đây, và phép
		# kiểm này không còn sở hữu ca đó — một đột biến đổi `<= 0` thành
		# `< 0` sẽ lọt mà bài test vẫn xanh.
		if flt(d.so_luong) <= 0:
			frappe.throw(_("{0}: Số lượng phải lớn hơn 0.").format(vi_tri))

		if d.tu_o == d.den_o:
			frappe.throw(_("{0}: Từ ô và Đến ô đang trùng nhau.").format(vi_tri))

		for truong, o in ((_("Từ ô"), d.tu_o), (_("Đến ô"), d.den_o)):
			thong_tin = frappe.db.get_value("Storage Location", o, ["kho", "is_group"], as_dict=True)
			if not thong_tin:
				frappe.throw(_("{0}: Vị trí {1} không tồn tại.").format(vi_tri, o))
			# K2 — xem docstring đầu file: đây là điều kiện giữ bất biến §3.
			if thong_tin.kho != self.kho:
				frappe.throw(
					_(
						"{0}: {1} {2} thuộc kho {3}, không phải {4}. Phiếu này chỉ chuyển "
						"giữa các ô TRONG một kho — đổi kho là việc của phiếu chuyển kho "
						"ERPNext."
					).format(vi_tri, truong, o, thong_tin.kho, self.kho)
				)

		# K3 — nút nhóm không chứa hàng. `ghi_dong_so` cũng chặn, nhưng báo ở
		# đây thì người dùng sửa được lúc phiếu còn là nháp.
		if frappe.db.get_value("Storage Location", d.den_o, "is_group"):
			frappe.throw(
				_("{0}: {1} là nút nhóm (cấp Khu/Dãy/Khoang/Tầng), không chứa hàng được.").format(
					vi_tri, d.den_o
				)
			)

		self._kiem_lo(d, vi_tri)

	def _kiem_lo(self, d, vi_tri):
		"""K9 + K10 — sai CẢ HAI chiều đều làm lệch tồn theo ô mà tổng vẫn
		đúng, nên đối soát không bắt được. Xem spec §6.2."""
		co_lo = frappe.db.get_value("Item", d.vat_tu, "has_batch_no")
		if co_lo and not d.so_lo:
			frappe.throw(
				_(
					"{0}: Mặt hàng {1} có quản lý lô nên bắt buộc chọn số lô. Bỏ trống sẽ "
					"ghi một dòng sổ không khớp lô nào — lô nguồn không giảm, còn ô đích "
					"mọc một dòng tồn ma."
				).format(vi_tri, d.vat_tu)
			)
		if not co_lo and d.so_lo:
			frappe.throw(
				_("{0}: Mặt hàng {1} không quản lý lô, phải bỏ trống Số lô.").format(vi_tri, d.vat_tu)
			)
		if d.so_lo:
			chu = frappe.db.get_value("Batch", d.so_lo, "item")
			if chu != d.vat_tu:
				frappe.throw(
					_("{0}: Lô {1} là lô của mặt hàng {2}, không phải {3}.").format(
						vi_tri, d.so_lo, chu, d.vat_tu
					)
				)

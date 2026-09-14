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
from frappe.utils import flt, now, nowdate

from erpnext.vi_tri_kho.vitri.kho import kho_co_quan_ly_vi_tri
from erpnext.vi_tri_kho.vitri.so import ghi_dong_so, ton_o


class LocationTransfer(Document):
	def validate(self):
		self.kiem_tra_kho()
		self.kiem_tra_cac_dong()

	def on_submit(self):
		self._ghi(dao=False)

	def _ghi(self, dao: bool):
		"""Ghi hai bút toán mỗi dòng, rồi CHẶN TỒN ÂM sau khi ghi xong cả phiếu.

		`dao = True` là đường huỷ: đảo dấu và cờ `da_huy = 1`.

		VÌ SAO GHI TRƯỚC RỒI MỚI KIỂM (spec §7.2): kiểm trước rồi ghi không
		chặn được hai thủ kho cùng rút một lô — cả hai cùng đọc thấy "còn 60"
		rồi cùng ghi -40, ra -20. Đúng ngữ nghĩa transaction: mỗi bên chỉ thấy
		dữ liệu đã commit của bên kia.

		`so._cong_don_ton` dùng `INSERT ... ON DUPLICATE KEY UPDATE`, MariaDB
		khoá đúng dòng chỉ mục ở tầng InnoDB cho statement đó, nên người ghi
		SAU phải chờ và đọc được kết quả của người ghi TRƯỚC. Đặt phép kiểm
		trước khi ghi thì không có khoá nào để dựa vào.
		"""
		company = frappe.db.get_value("Warehouse", self.kho, "company")
		luc = now()
		dau = -1 if dao else 1
		cham = set()

		# SAVEPOINT, không dựa vào `frappe.throw` để dọn hộ. `throw` chỉ ném
		# ngoại lệ; thứ rollback giao dịch là BỘ XỬ LÝ REQUEST của Frappe. Gọi
		# từ script, từ API, hay từ một bài test thì không có ai dọn, và các
		# dòng sổ đã ghi vẫn nằm nguyên trong giao dịch — đúng ngược với lời
		# hứa "phiếu bị từ chối thì không dòng sổ nào sống sót". Đo được bằng
		# bài `test_rut_qua_ton_bi_tu_choi_va_khong_ghi_gi` (14/09/2026).
		diem = "vi_tri_kho_xep_vi_tri"
		frappe.db.savepoint(diem)
		try:
			for d in self.items:
				sl = flt(d.so_luong) * dau
				for o, luong in ((d.tu_o, -sl), (d.den_o, sl)):
					ghi_dong_so(
						o=o,
						kho=self.kho,
						vat_tu=d.vat_tu,
						so_lo=d.so_lo,
						so_luong=luong,
						chung_tu_type=self.doctype,
						chung_tu=self.name,
						chung_tu_row=d.name,
						sle=None,
						ngay=self.ngay or nowdate(),
						thoi_diem=luc,
						company=company,
						da_huy=1 if dao else 0,
					)
					# Gom CẢ HAI ô, không riêng ô nguồn: ở đường huỷ (Task 3)
					# ô bị GIẢM là ô ĐÍCH, vì hàng đã xếp vào đó có thể đã bị
					# xuất đi mất.
					cham.add((o, d.vat_tu, d.so_lo or ""))

			self._chan_ton_am(cham)
		except Exception:
			frappe.db.rollback(save_point=diem)
			raise

	def _chan_ton_am(self, cham):
		"""Đọc lại KẾT QUẢ RÒNG của mọi (ô, mặt hàng, lô) mà phiếu chạm tới.

		Đọc sau khi ghi xong TOÀN BỘ phiếu, không sau từng dòng: một phiếu hợp
		lệ có thể lấy 10 khỏi ô A ở dòng 1 rồi trả 10 về ô A ở dòng 2. Chỉ kết
		quả ròng mới có ý nghĩa.

		Ô âm là hỏng nặng, không phải lệch thường: `doi_soat` báo `o_am`, và
		"Đồng bộ lại" CỐ Ý ném lỗi thay vì chữa. Nên chặn ngay ở đây — `throw`
		làm cả phiếu rollback, không dòng sổ nào sống sót.
		"""
		for o, vat_tu, so_lo in sorted(cham):
			con = flt(ton_o(o, vat_tu, so_lo or None))
			if con < 0:
				frappe.throw(
					_(
						"Ô {0} không đủ hàng: mặt hàng {1}{2} sẽ còn {3} sau phiếu này. "
						"Kiểm lại số lượng trên các dòng lấy hàng từ ô đó."
					).format(o, vat_tu, _(", lô {0}").format(so_lo) if so_lo else "", con)
				)

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

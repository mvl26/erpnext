"""Gán MỘT mặt hàng vào MỘT nút vị trí. Nút nhóm = cả nhánh dưới nó.

Bất biến trung tâm: **một ô chỉ thuộc về một mặt hàng**. Nó được giữ ở hai
tầng khác nhau, cố ý:

1. "Một mặt hàng một nút" — do `autoname: field:vat_tu`, tức KHOÁ CHÍNH của
   bảng. Data Import, `frappe.db.set_value` và đường REST đều không đi vòng
   được một khoá chính; chúng đi vòng được một dòng trong `validate()`.
2. "Một nút một chủ" — do `kiem_tra_chong_lan()` dưới đây, vì nested set
   không có cách nào biểu diễn "hai nhánh không giao nhau" bằng ràng buộc DB.

Thứ tự phép kiểm trong `validate()` là CỐ Ý: rẻ trước, và mỗi phép kiểm sau
dựa vào tiền đề phép kiểm trước đã lập. Cụ thể `kiem_tra_trong_cay()` phải
chạy TRƯỚC mọi thứ đọc `lft`/`rgt` — xem docstring của nó.
"""

import frappe
from frappe import _
from frappe.model.document import Document

from erpnext.vi_tri_kho.vitri.gan import chu_cua_nhanh
from erpnext.vi_tri_kho.vitri.kho import kho_co_quan_ly_vi_tri
from erpnext.vi_tri_kho.vitri.ma_vi_tri import TEN_CAP, cap_do


class ItemLocationPreference(Document):
	def validate(self):
		self.nut = self._doc_nut()
		self.kiem_tra_trong_cay()
		self.kiem_tra_nut_hop_le()
		self.kiem_tra_chong_lan()
		self.cap_do = TEN_CAP[cap_do(self.vi_tri) - 1]

	def _doc_nut(self):
		nut = frappe.db.get_value(
			"Storage Location",
			self.vi_tri,
			["name", "kho", "lft", "rgt", "disabled", "la_o_chua_xep"],
			as_dict=True,
		)
		if not nut:
			frappe.throw(_("Vị trí {0} không tồn tại.").format(self.vi_tri))
		return nut

	def kiem_tra_trong_cay(self):
		"""Nút phải có toạ độ thật trong cây.

		BẪY ĐÃ TRẢ GIÁ HAI LẦN trong chính module này (`fefo.py::pham_vi`,
		`tem.py::goc`). Bản ghi chưa hội tụ mang `lft = rgt = 0`; cho qua thì
		vị từ giao nhau ở `kiem_tra_chong_lan()` thành `0 … 0` và khớp MỌI bản
		ghi 0/0 khác TRÊN TOÀN HỆ, kể cả của kho khác — gán một Tầng lại báo
		đụng một nút hoàn toàn không liên quan, hoặc tệ hơn, chặn oan cả loạt.

		Chặn ở NGUỒN, không vá bằng vị từ chặt hơn: ở đây so chính toạ độ của
		`vi_tri`, mà toạ độ đó mới là thứ hỏng.
		"""
		if not self.nut.lft or not self.nut.rgt:
			frappe.throw(
				_(
					"Vị trí {0} chưa có toạ độ trong cây vị trí nên chưa gán được. "
					"Mở vị trí đó và lưu lại để cây tính lại toạ độ, hoặc chạy "
					"`bench migrate`, rồi thử lại."
				).format(self.vi_tri)
			)

	def kiem_tra_nut_hop_le(self):
		# VÒNG SỬA (điều phối): so LỆCH KHO trước cờ `kho_co_quan_ly_vi_tri()`
		# — cùng lớp lỗi với `storage_location.py::validate` "VÒNG SỬA 2".
		# Nếu đảo lại (cờ trước, lệch kho sau), một kho CHƯA bật quản lý vị
		# trí sẽ luôn nổ ở phép kiểm cờ TRƯỚC KHI kịp so `self.nut.kho` với
		# `self.kho` — bài `test_chan_nut_thuoc_kho_khac` (lấy một Warehouse
		# bất kỳ KHÁC kho Miyano, mà chỉ kho Miyano bật quản lý vị trí) sẽ
		# luôn nổ ở nhánh cờ, không bao giờ chạm nhánh lệch kho nó khai là
		# đang kiểm: bài vẫn xanh nhưng chứng minh sai thứ, và một người sau
		# này gán nhầm nút của kho A vào bản ghi kho B (khi B cũng đã bật
		# quản lý vị trí) sẽ không bị chặn ở đây nữa vì phép kiểm cờ đã tự
		# tin "qua" rồi mới lo tới lệch kho.
		if self.nut.kho != self.kho:
			frappe.throw(
				_("Vị trí {0} thuộc kho {1}, không phải {2}.").format(
					self.vi_tri, self.nut.kho, self.kho
				)
			)

		if not kho_co_quan_ly_vi_tri(self.kho):
			frappe.throw(_("Kho {0} chưa bật quản lý vị trí.").format(self.kho))

		if self.nut.la_o_chua_xep:
			frappe.throw(
				_(
					"{0} là ô hệ thống (hàng chờ xếp), không phải kệ thật — không gán "
					"mặt hàng vào đó được. Chọn một ô hoặc tầng trên cây vị trí."
				).format(self.vi_tri)
			)

		tat = self._to_tien_tat()
		if tat:
			frappe.throw(
				_(
					"Vị trí {0} đang ngừng dùng (do chính nó hoặc do {1} ở trên nó). "
					"Gợi ý sẽ trỏ vào chỗ không ai được đụng tới. Bật lại rồi gán."
				).format(self.vi_tri, tat)
			)

	def kiem_tra_chong_lan(self):
		"""Nối bất biến trung tâm của cả tính năng vào `validate()`: một ô
		chỉ thuộc về một mặt hàng.

		Bỏ phép kiểm này thì hai mặt hàng cùng được gợi ý vào một ô, thủ kho
		xếp chồng lên nhau — và KHÔNG CÓ GÌ BÁO: đối soát §3 (`doi_soat.py`)
		chỉ so TỔNG tồn theo kho/mặt hàng, nên vẫn khớp tuyệt đối dù vị trí
		gợi ý sai be bét. Đây không phải một tình huống hiếm: mọi lần gán
		thủ công hoặc import hàng loạt đều đi qua đúng một cửa này.

		Không thể thay bằng một ràng buộc CSDL (vd. unique index trên
		`vi_tri`): nested set không có cách biểu diễn "hai nhánh không giao
		nhau" bằng constraint — quan hệ "giao nhau" là phép so sánh giữa hai
		KHOẢNG (`lft`/`rgt`), không phải một khoá đơn mà `UNIQUE` bắt được.
		Phải kiểm bằng truy vấn, ở đây, tại `validate()`.
		"""
		chu = chu_cua_nhanh(self.nut.lft, self.nut.rgt, tru_ten=self.name)
		if not chu:
			return

		if chu.vi_tri == self.vi_tri:
			quan_he = _("đã được gán cho")
		elif chu.lft <= self.nut.lft and chu.rgt >= self.nut.rgt:
			quan_he = _("nằm trong nhánh {0} đã được gán cho").format(chu.vi_tri)
		else:
			quan_he = _("bao trùm {0} đã được gán cho").format(chu.vi_tri)

		frappe.throw(
			_("Vị trí {0} {1} mặt hàng {2}. Mỗi ô chỉ thuộc về một mặt hàng.").format(
				self.vi_tri, quan_he, chu.vat_tu
			)
		)

	def _to_tien_tat(self) -> str | None:
		"""Tên nút `disabled` gần nhất: chính nó, hoặc một tổ tiên.

		Kiểm CẢ TỔ TIÊN chứ không chỉ cờ của chính nút — người vận hành tắt cả
		một Dãy để sửa kệ thì mọi ô dưới đó cũng không dùng được, dù cờ của
		từng ô vẫn bằng 0. Cùng luật với `fefo._TO_TIEN_TAT`.
		"""
		dong = frappe.db.sql(
			"""
			select tt.name
			from `tabStorage Location` tt
			where ifnull(tt.disabled, 0) = 1
			  and (tt.name = %(nut)s or (tt.lft < %(lft)s and tt.rgt > %(rgt)s))
			order by tt.lft asc
			limit 1
			""",
			{"nut": self.vi_tri, "lft": self.nut.lft, "rgt": self.nut.rgt},
		)
		return dong[0][0] if dong else None

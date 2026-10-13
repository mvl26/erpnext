"""Gán một mặt hàng vào MỘT HAY NHIỀU nút vị trí. Nút nhóm = cả nhánh dưới nó.

NHIỀU VỊ TRÍ (22/09/2026 — chủ đầu tư: "1 item có thể gán nhiều vị trí khác nhau…
item này có thể ở ô này và ở tầng bên kia nữa"): bản gán giữ một BẢNG CON
`vi_tri_gan` (`Item Location Preference Row`), mỗi dòng một nút, mang kho của nút
đó. Mọi phép kiểm dưới đây chạy cho TỪNG dòng (`self._dong`/`self.nut` là dòng
đang xét), câu báo mở đầu bằng "Dòng N:". Thêm một luật: hai dòng của cùng bản
gán không được giao nhau (`kiem_tra_tu_long_nhau`).

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

from erpnext.warehouse_operations.vitri.fefo import ten_nut_ngung_dung
from erpnext.warehouse_operations.vitri.gan import (
	chu_cua_nhanh,
	dem_ton_khac_trong_nhanh,
	ton_khac_trong_nhanh,
)
from erpnext.warehouse_operations.vitri.kho import kho_co_quan_ly_vi_tri
from erpnext.warehouse_operations.vitri.ma_vi_tri import TEN_CAP, cap_do


class ItemLocationPreference(Document):
	def validate(self):
		if not self.get("vi_tri_gan"):
			frappe.throw(_("Bản gán phải có ít nhất một vị trí."))
		nut_cua_dong = []
		for d in self.vi_tri_gan:
			# `_dong`/`nut` là dòng đang xét — các phép kiểm con đọc hai thuộc tính
			# này, để thân từng phép kiểm (và lý lẽ ghi ở docstring của nó) giữ
			# nguyên như thời một bản gán chỉ có một nút.
			self._dong = d
			self.nut = self._doc_nut()
			self.kiem_tra_trong_cay()
			self.kiem_tra_nut_hop_le()
			self.kiem_tra_chong_lan()
			self.kiem_tra_ton_mat_hang_khac()
			d.kho = self.nut.kho
			d.cap_do = TEN_CAP[cap_do(d.vi_tri) - 1]
			nut_cua_dong.append((d, self.nut))
		self.kiem_tra_tu_long_nhau(nut_cua_dong)

	def _loi(self, cau: str):
		"""`frappe.throw` kèm tiền tố "Dòng N: " — thủ kho sửa đúng dòng, không đoán."""
		frappe.throw(_("Dòng {0}: ").format(self._dong.idx) + cau)

	def kiem_tra_tu_long_nhau(self, nut_cua_dong):
		"""Hai dòng của CÙNG bản gán không được giao nhau (trùng nút, hoặc nút này
		nằm trong nhánh nút kia).

		Không phải vì hỏng dữ liệu — gợi ý ô vẫn chạy — mà vì một dòng thừa khiến
		"mặt hàng này đang giữ những đâu" nói sai (tầng và một ô trong chính tầng
		đó trông như hai chỗ), và thứ tự dòng dùng để phân định ô trống trở nên
		không đoán được. Cùng vị từ giao nhau với `gan.chu_cua_nhanh`.
		"""
		for i, (a, na) in enumerate(nut_cua_dong):
			for b, nb in nut_cua_dong[i + 1 :]:
				if na.lft <= nb.rgt and na.rgt >= nb.lft:
					frappe.throw(
						_(
							"Dòng {0} ({1}) trùng hoặc lồng với dòng {2} ({3}) — mỗi nhánh chỉ gán "
							"một lần. Bỏ một trong hai dòng."
						).format(b.idx, b.vi_tri, a.idx, a.vi_tri)
					)

	def _doc_nut(self):
		nut = frappe.db.get_value(
			"Storage Location",
			self._dong.vi_tri,
			["name", "kho", "lft", "rgt", "disabled", "la_o_chua_xep"],
			as_dict=True,
		)
		if not nut:
			self._loi(_("Vị trí {0} không tồn tại.").format(self._dong.vi_tri))
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
			self._loi(
				_(
					"Vị trí {0} chưa có toạ độ trong cây vị trí nên chưa gán được. "
					"Mở vị trí đó và lưu lại để cây tính lại toạ độ, hoặc chạy "
					"`bench migrate`, rồi thử lại."
				).format(self._dong.vi_tri)
			)

	def kiem_tra_nut_hop_le(self):
		# 22/09/2026: không còn vế "nút thuộc kho khác kho đã khai" — kho của dòng
		# TỰ theo nút (`validate`), không ai khai tay nên không có gì để lệch. Chỉ còn
		# hỏi kho CỦA NÚT đã bật quản lý vị trí chưa.
		if not kho_co_quan_ly_vi_tri(self.nut.kho):
			self._loi(_("Kho {0} chưa bật quản lý vị trí.").format(self.nut.kho))

		if self.nut.la_o_chua_xep:
			self._loi(
				_(
					"{0} là ô hệ thống (hàng chờ xếp), không phải kệ thật — không gán "
					"mặt hàng vào đó được. Chọn một ô hoặc tầng trên cây vị trí."
				).format(self._dong.vi_tri)
			)

		tat = self._to_tien_tat()
		if tat:
			self._loi(
				_(
					"Vị trí {0} đang ngừng dùng (do chính nó hoặc do {1} ở trên nó). "
					"Gợi ý sẽ trỏ vào chỗ không ai được đụng tới. Bật lại rồi gán."
				).format(self._dong.vi_tri, tat)
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

		if chu.vi_tri == self._dong.vi_tri:
			quan_he = _("đã được gán cho")
		elif chu.lft <= self.nut.lft and chu.rgt >= self.nut.rgt:
			quan_he = _("nằm trong nhánh {0} đã được gán cho").format(chu.vi_tri)
		else:
			quan_he = _("bao trùm {0} đã được gán cho").format(chu.vi_tri)

		self._loi(
			_("Vị trí {0} {1} mặt hàng {2}. Mỗi ô chỉ thuộc về một mặt hàng.").format(
				self._dong.vi_tri, quan_he, chu.vat_tu
			)
		)

	def kiem_tra_ton_mat_hang_khac(self):
		"""Trong nhánh không được có tồn của mặt hàng khác.

		Quyết định của chủ đầu tư 15/09 ("chặn cả hai").

		LƯU Ý CHO NGƯỜI ĐỌC SAU: phép kiểm này chỉ chặn LÚC GÁN. Hàng vẫn vào
		sai ô được sau đó — qua phiếu xếp khai tay, qua đường huỷ chứng từ, qua
		kiểm kê. Thứ soi việc đó là báo cáo `hang_nam_sai_vi_tri`; đối soát §3
		KHÔNG bắt được vì nó chỉ so tổng.
		"""
		GIOI_HAN = 3
		dong = ton_khac_trong_nhanh(self.nut.lft, self.nut.rgt, self.vat_tu, GIOI_HAN)
		if not dong:
			return

		ke = [
			_("{0}: {1} × {2}").format(d.o, d.vat_tu, frappe.format_value(d.so_luong, "Float"))
			for d in dong[:GIOI_HAN]
		]
		# VÒNG SỬA 1 (review điều phối): `len(dong)` bị `limit` của
		# `ton_khac_trong_nhanh()` chặn cứng ở `GIOI_HAN + 1`, nên đếm trên đó
		# luôn ra N = 1 dù nhánh có 50 ô — sai đúng con số thủ kho cần để biết
		# khối lượng phải dọn. Chỉ ĐƯỜNG LỖI này mới cần tổng thật nên chỉ ở
		# đây mới gọi thêm `dem_ton_khac_trong_nhanh()` (một truy vấn COUNT
		# riêng, không `limit`); đường thành công (không chồng) không chạm
		# tới nó nên không tốn thêm round-trip DB nào ở đường nóng.
		tong = dem_ton_khac_trong_nhanh(self.nut.lft, self.nut.rgt, self.vat_tu)
		them = _(" … và {0} ô nữa").format(tong - GIOI_HAN) if tong > GIOI_HAN else ""
		self._loi(
			_(
				"Trong nhánh {0} đang có hàng của mặt hàng khác:\n\n{1}{2}\n\n"
				"Chuyển những ô đó đi bằng phiếu chuyển vị trí rồi gán lại."
			).format(self._dong.vi_tri, "\n".join(ke), them)
		)

	def _to_tien_tat(self) -> str | None:
		"""Tên nút `disabled` gần nhất: chính nó, hoặc một tổ tiên.

		Kiểm CẢ TỔ TIÊN chứ không chỉ cờ của chính nút — người vận hành tắt cả
		một Dãy để sửa kệ thì mọi ô dưới đó cũng không dùng được, dù cờ của
		từng ô vẫn bằng 0.

		VÒNG VÁ (mối lo #2, report review tổng trước): đây từng là một bản
		viết TAY THỨ BA của luật này (chữ ký riêng — trả TÊN nút, so bằng
		`lft`/`rgt` truyền tay — nên không tự nhiên gọi được `fefo.to_tien_tat()`
		như `goi_y._UNG_VIEN`/`gan.cay_chon_vi_tri` vốn dùng, hàm đó trả một vị
		từ SQL, không phải một cái tên). Giờ chỉ còn MỘT định nghĩa
		(`fefo._dieu_kien_ngung_dung()`); hàm này chỉ còn là một cách GỌI khác
		của cùng luật đó, không phải một bản sao — hai bản trôi khỏi nhau thì
		một nửa hệ chặn (chỗ này) còn nửa kia (cây chọn vị trí, gợi ý ô) cho
		qua, và không có gì báo.
		"""
		return ten_nut_ngung_dung(self._dong.vi_tri, self.nut.lft, self.nut.rgt)

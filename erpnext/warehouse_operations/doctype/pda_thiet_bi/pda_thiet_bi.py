"""Một chiếc PDA đang cầm danh tính của một thủ kho.

DOCTYPE NÀY KHÔNG GIỮ CHÌA KHOÁ, CHỈ GIỮ DẤU VẾT. Khoá máy là cặp
`api_key`/`api_secret` của Frappe nằm trên `User` (bí mật được mã hoá trong bảng
`__Auth`); ở đây chỉ lưu "ai đang cầm máy nào, từ lúc nào, còn hiệu lực không" —
thứ mà trước Task 3 không ai trả lời được. Lộ bảng này không dựng lại được khoá.

Luật nghiệp vụ nằm ở `vitri/the_pda.py` (cấp khoá, thu hồi, và hook kiểm mã máy ở
mỗi request). Ở đây chỉ là những phép kiểm KHÔNG ĐƯỢC PHÉP VƯỢT dù ghi bằng đường
nào — kể cả một người sửa tay trong Desk.
"""

import frappe
from frappe import _
from frappe.model.document import Document

from erpnext.warehouse_operations.vitri.the_pda import (
	VAI_TRO_DUOC_DUNG_THE,
	chuan_ma_may,
	dong_cua_khi_het_may,
)


class PDAThietBi(Document):
	def validate(self):
		# `ma_may` vừa là tên bản ghi (`autoname: field:ma_may`) vừa là thứ đem so với
		# header của mỗi lời gọi. Hai nơi chuẩn hoá khác nhau là máy quét được ở lượt
		# cấp khoá mà bị từ chối ở lượt gọi sau — nên ở đây KHÔNG tự sửa giá trị (sửa
		# xong sẽ lệch với tên bản ghi đã đặt trước lúc validate), mà BÁO LỖI để người
		# gõ tay tự sửa. Đường chạy thật (`the_pda.cap_khoa_may`) đã chuẩn hoá trước
		# khi tạo, nên nhánh này chỉ bắt người nhập tay trong Desk.
		if chuan_ma_may(self.ma_may) != (self.ma_may or ""):
			frappe.throw(_("Mã máy không được có khoảng trắng thừa: {0}").format(self.ma_may))
		if not chuan_ma_may(self.ma_may):
			frappe.throw(_("Thiếu mã máy — không biết khoá này thuộc chiếc máy nào."))

		# Chỉ kiểm điều kiện tài khoản khi máy CÒN HIỆU LỰC (lúc cấp). Người đã nghỉ
		# việc hoặc đã bị rút vai trò kho vẫn phải THU HỒI ĐƯỢC máy — giống hệt lý do
		# `PDA Badge.validate` gác theo `con_hieu_luc`. Chặn ở đây là chặn đúng cái nút
		# cứu hoả.
		if self.con_hieu_luc and not (VAI_TRO_DUOC_DUNG_THE & set(frappe.get_roles(self.nguoi_dung))):
			frappe.throw(
				_("{0} không có vai trò kho nào nên khoá máy sẽ không mở được màn hình nào.").format(
					self.nguoi_dung
				)
			)
		self.ho_ten = frappe.db.get_value("User", self.nguoi_dung, "full_name")

	def on_update(self):
		"""Đổi "Người dùng" trong Desk không được làm chủ CŨ thoát khỏi ràng buộc mã máy.

		`kiem_khoa_may` thoát sớm khi một người không còn dòng máy nào. Gán chiếc máy này
		sang người khác mà chủ cũ hết máy là **mở đúng cánh cửa đó** — khoá của chủ cũ
		(kể cả khoá ĐÃ THU HỒI) xác thực lại được, không cần `X-Ma-May`. Đã đo (soát tổng,
		N1). Không chặn thao tác, vì `the_pda._ghi_thiet_bi` cũng đi qua đây khi một chiếc
		máy được trao tay ở quầy; thay vào đó **kéo theo hậu quả**: giết khoá của chủ cũ.

		KHÔNG dùng `set_only_once` cho `nguoi_dung` — đã cân nhắc và loại. `_ghi_thiet_bi`
		CẦN gán lại `nguoi_dung` trên đúng dòng cũ (khoá theo `ma_may`, vì `ma_may` là
		`unique`), nên đóng băng trường đó sẽ chặn chính đường chạy thật: một chiếc máy
		được thủ kho khác quét thẻ lên sẽ ném lỗi trùng ngay giữa lúc nhận máy.
		"""
		truoc = self.get_doc_before_save()
		if truoc and truoc.nguoi_dung and truoc.nguoi_dung != self.nguoi_dung:
			dong_cua_khi_het_may(truoc.nguoi_dung)

	def after_delete(self):
		"""Xoá dòng máy phải kéo theo việc giết khoá — xem `on_update` và
		`the_pda.dong_cua_khi_het_may`.

		`after_delete` chứ không `on_trash`: `on_trash` chạy TRƯỚC khi dòng biến mất nên
		phép đếm "còn bao nhiêu máy" vẫn thấy chính dòng đang bị xoá, và phép kiểm sẽ luôn
		trả "vẫn còn máy" — một cái gác không bao giờ nổ.
		"""
		dong_cua_khi_het_may(self.nguoi_dung)

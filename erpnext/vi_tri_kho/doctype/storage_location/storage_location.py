"""Vị trí kho — một bản ghi là MỘT Ô chứa hàng, hoặc một NÚT NHÓM tổ tiên của nó.

Mô hình theo `SPD_VanHanh_PhanTichMaViTriKho_20260907_v2` §5.5: bảng master
vị trí có mã 10 ký tự cộng 5 trường thành phần. Phân cấp Khu → Dãy → Khoang →
Tầng → Ô nằm NGAY TRONG mã — mỗi cấp là TIỀN TỐ của cấp sau — nên cây nested
set (`is_group`, `parent_storage_location`, `lft/rgt`) không phải một phân
cấp độc lập phải tự tay giữ đồng bộ: nó là HÌNH CHIẾU của mã, `validate()`
tính lại từ mã mỗi lần lưu và ghi đè mọi giá trị `parent` mà nơi khác đặt.

Bản trước (Task ngày 2026-09-09) đã bỏ hẳn `NestedSet` với đúng lý do "hai
nguồn sự thật cho cùng một phân cấp". Lý do đó chỉ đứng vững khi cây được
khai TAY. Task 2 (2026-09-11) dựng lại cây, nhưng suy nó THẲNG TỪ MÃ — không
còn là dữ liệu thứ hai, nên không còn nguy cơ lệch: xem
`erpnext/vi_tri_kho/tests/test_cay_vi_tri.py` để thấy phép thử khoá đúng
điều đó ("không tồn tại thao tác nào đặt được cây lệch khỏi mã").
"""

import frappe
from frappe import _
from frappe.utils.nestedset import NestedSet

from erpnext.vi_tri_kho.vitri.ma_vi_tri import cap_do, dinh_dang_nhan, ma_cha, phan_tich_ma


class StorageLocation(NestedSet):
	nsm_parent_field = "parent_storage_location"

	def validate(self):
		self.kiem_tra_ma_o_khong_doi()
		self.dung_cho_trong_cay()
		self.tach_thanh_phan_ma()
		self.kiem_tra_kho()
		self.kiem_tra_khong_doi_dang_o_chua_xep()
		if not self.barcode:
			self.barcode = self.ma_o

	def dung_cho_trong_cay(self):
		"""Tính `is_group` và `parent` TỪ MÃ, ghi đè mọi giá trị người dùng đặt.

		Ghi đè chứ không phải báo lỗi: `parent` là read_only trên form nên
		người dùng bình thường không đặt được, còn đường API/Data Import thì
		đặt được — và ở đó im lặng sửa về đúng tốt hơn là chặn một thao tác
		nhập liệu hàng loạt.
		"""
		if self.la_o_chua_xep:
			self.is_group = 0
			self.parent_storage_location = None
			return

		cap = cap_do(self.ma_o)
		self.is_group = 1 if cap < 5 else 0
		self.parent_storage_location = self.dam_bao_to_tien()

	def dam_bao_to_tien(self) -> str | None:
		"""Tạo các nút cha còn thiếu, từ gốc xuống. Trả tên cha trực tiếp.

		VÒNG SỬA 1 (review điều phối): `ma_o` bỏ 2 ký tự mã kho (Task 1) nên
		là khoá chính TOÀN HỆ, không phải duy nhất trong một kho. Nếu nút cha
		ĐÃ tồn tại, phải kiểm nó thuộc đúng `self.kho` — không kiểm thì hai
		kho khác nhau cùng đặt trùng ký hiệu khu (ví dụ cả hai đặt Khu `1B`)
		sẽ đụng đúng một bản ghi nút nhóm: nhánh của kho sau âm thầm gắn vào
		cây của kho trước, không có lỗi nào báo. Hôm nay chỉ một kho bật quản
		lý vị trí nên chưa lộ; cái giá lộ ra đúng lúc thêm kho thứ hai — khi
		tem đã dán lên kệ.
		"""
		cha = ma_cha(self.ma_o)
		if not cha:
			return None
		kho_cha = frappe.db.get_value("Storage Location", cha, "kho")
		if kho_cha is None:
			frappe.get_doc({"doctype": "Storage Location", "ma_o": cha, "kho": self.kho}).insert(
				ignore_permissions=True
			)
		elif kho_cha != self.kho:
			frappe.throw(
				_(
					"Không tạo được ô {0}: nút nhóm {1} đã thuộc kho {2}, không phải kho {3}. "
					"Mã ô không còn chứa mã kho (bỏ từ khi đổi chuẩn 10 ký tự) nên phải duy "
					"nhất trên TOÀN HỆ, không riêng từng kho — hai kho không được dùng trùng "
					"ký hiệu khu/dãy/khoang/tầng. Chọn một ký hiệu khu khác cho kho {3}."
				).format(self.ma_o, cha, kho_cha, self.kho)
			)
		return cha

	def tach_thanh_phan_ma(self):
		"""Ô LÁ tách đủ 5 thành phần; nút nhóm chỉ điền phần nó có.

		Ô "Chưa xếp vị trí" được MIỄN: nó là ô lô-gic, không ứng với chỗ nào
		ngoài kho và không bao giờ in lên tem. Ép nó vào chuẩn là bịa ra một
		địa chỉ vật lý không tồn tại.
		"""
		if self.la_o_chua_xep:
			return
		if self.is_group:
			phan = ("khu", "day", "khoang", "tang")[: cap_do(self.ma_o)]
			for i, ten in enumerate(phan):
				setattr(self, ten, self.ma_o[i * 2 : i * 2 + 2])
			self.ma_in_nhan = None
			return
		p = phan_tich_ma(self.ma_o)
		self.khu, self.day = p["khu"], p["day"]
		self.khoang, self.tang, self.o = p["khoang"], p["tang"], p["o"]
		self.ma_in_nhan = dinh_dang_nhan(self.ma_o)

	def kiem_tra_ma_o_khong_doi(self):
		# `ma_o` là field autoname (autoname: field:ma_o) nên `name` chính là
		# mã ô — nhưng Frappe chỉ gán `name` từ `ma_o` lúc insert. Nếu không
		# chặn ở đây, `_sync_autoname_field()` của framework sẽ tự lặng lẽ ghi
		# đè `ma_o` về đúng `name` ngay sau bước validate này (autoname field
		# không bao giờ thắng được `name` khi save), khiến người dùng tưởng
		# đã đổi mã ô nhưng thật ra bị âm thầm phục hồi, không có lỗi nào báo.
		# Nên chặn tường minh ở đây, trước khi `_sync_autoname_field()` chạy.
		if self.is_new():
			return
		if self.ma_o != self.name:
			frappe.throw(
				_(
					"Không sửa được mã ô của {0} (đang đổi thành {1}). Mã ô đã in lên tem "
					"dán kệ nên khoá lại sau khi tạo; cần mã khác thì tạo ô mới rồi ngừng "
					"dùng ô cũ."
				).format(self.name, self.ma_o)
			)

	def kiem_tra_kho(self):
		if not self.kho:
			frappe.throw(_("Ô {0} phải chọn kho.").format(self.ma_o))

		if frappe.db.get_value("Warehouse", self.kho, "is_group"):
			frappe.throw(
				_(
					"{0} là kho tổng, không chứa hàng thật nên không đặt ô kệ vào đó được. "
					"Chọn một kho cụ thể."
				).format(self.kho)
			)

	def kiem_tra_khong_doi_dang_o_chua_xep(self):
		"""CRITICAL 2 (review điều phối, sau khi 147/147 bài "xong"): chặn
		việc vô hiệu hoá ô hệ thống "Chưa xếp vị trí" — field `disabled`
		KHÔNG `read_only` và `Stock Manager`
		có quyền `write` trên doctype này (xem `storage_location.json`), nên
		đây là một tai nạn vận hành có thể xảy ra qua form bình thường,
		không chỉ qua API.

		Hậu quả nếu không chặn (đã đo cơ chế, xem `hook_sle.py` docstring
		module — "một checkbox làm đứng cả kho"): tích `disabled=1` làm hook
		nhập (không lọc `disabled`, trước Critical 2 còn không kiểm gì) vẫn
		ghi vào ô này, trong khi FEFO xuất (`fefo.py`, lọc `disabled=0`)
		loại bỏ nó rồi `frappe.throw` GIỮA `Stock Ledger Entry.on_submit` —
		cuộn ngược MỌI phiếu xuất của MỌI mặt hàng đang ở CHUA-XEP. Tương tự,
		`is_group=1` sẽ làm ô này ngừng là ô LÁ (chứa hàng thật) trong khi sổ
		vị trí vẫn coi nó là nơi chứa tồn.

		Đây là lớp chặn ở TẦNG GHI (validate), bổ sung cho lớp chặn ở TẦNG
		ĐỌC (`kho.py::o_chua_xep` giờ kiểm dạng mỗi lần đọc) — hai lớp bắt
		hai nguồn khác nhau: validate chặn thao tác MỚI qua form/API bình
		thường; `o_chua_xep()` bắt dữ liệu CŨ hoặc ghi tay qua Data Import
		(không qua `validate` của doctype).
		"""
		if not self.la_o_chua_xep:
			return
		if self.disabled:
			frappe.throw(
				_(
					'Không thể vô hiệu hoá ô "Chưa xếp vị trí" {0} của kho {1} — đây là ô hệ '
					"thống, luôn phải hoạt động. Muốn ngừng dùng vị trí cho kho này, dùng chức "
					'năng "Tắt" ở Warehouse Location Setup.'
				).format(self.name, self.kho)
			)

	def on_trash(self):
		"""Spec §5.1: `la_o_chua_xep` "mỗi kho đúng 1 ô, không xoá được".

		CRITICAL 2: trước đây Frappe chỉ chặn GIÁN TIẾP khi đã có dòng sổ
		trỏ tới (Link validation qua `Location Ledger Entry.o`) — ngay sau
		khi bật một kho RỖNG (chưa có dòng sổ nào trỏ tới ô này, ví dụ bật
		xong huỷ ngay hoặc kho chưa từng nhập/xuất gì), ô CHUA-XEP xoá được
		bình thường, để lại kho ở trạng thái "đã bật" (`custom_quan_ly_vi_tri
		=1`) mà KHÔNG có ô gom hàng nào — lần nhập kế tiếp sẽ ném lỗi
		"chưa có ô Chưa xếp vị trí" (xem `hook_sle.py::_bat_buoc_o_chua_xep`)
		giữa `Stock Ledger Entry.on_submit`.

		Task 2 (2026-09-11) — ĐIỀU PHỐI: từ khi `StorageLocation` kế thừa
		`NestedSet`, override này PHẢI gọi `super().on_trash()`. Nó dọn
		`lft/rgt` của toàn cây (đóng lại khoảng mà nút bị xoá chừa ra) và tự
		chặn xoá một nút còn con (`validate_if_child_exists`). Override mà
		không gọi super vẫn "xoá được" ở tầng document — chỉ là để lại một
		khoảng `lft/rgt` mồ côi trong bảng, hỏng lặng lẽ, không ai báo lỗi.
		Gọi SAU khi chặn ô hệ thống: chặn ô CHUA-XEP là điều kiện MẠNH hơn
		điều kiện "không còn con" của `NestedSet` (ô CHUA-XEP không có con
		nên super sẽ không tự chặn nó) — thứ tự này giữ nguyên logic chặn có
		sẵn, chỉ thêm dọn cây cho những nút được phép xoá.
		"""
		if self.la_o_chua_xep:
			frappe.throw(
				_(
					'Không xoá được ô "Chưa xếp vị trí" {0} của kho {1} — mỗi kho đã bật quản '
					"lý vị trí phải luôn có đúng một ô này."
				).format(self.name, self.kho)
			)
		super().on_trash()

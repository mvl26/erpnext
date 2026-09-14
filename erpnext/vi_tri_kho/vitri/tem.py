"""Chọn danh sách ô để in tem cho một nhánh của cây vị trí.

File này CHỈ quyết định **in những ô nào**. Việc vẽ tem (khổ 45×25mm hoặc
50×30mm, mã vạch Code 128, cửa sổ in) nằm ở `public/js/vi_tri_kho/tem_vi_tri.js`.

Vì sao tách đôi: phần chọn ô là chỗ hỏng đắt và im lặng. In THIẾU thì thấy
ngay — kệ trống tem. In THỪA thì ra một xấp tem của nhánh khác, dán lên kệ,
và mọi lần quét sau đó đều trỏ sai chỗ mà không có gì báo lỗi. Nên phần này
ở Python để test khoá được và chạy đột biến được.
"""

import frappe
from frappe import _

# Cùng nguồn với DocPerm đọc của `Storage Location`: thủ kho (`Stock User`)
# PHẢI in lại được tem khi tem rách, bẩn, bong — đó là việc hằng ngày, không
# phải thiết lập. Khác với `bat_kho.py` (sinh ô, bật kho) cố ý chỉ mở cho
# quản lý, vì những thao tác đó GHI dữ liệu; in tem không ghi gì.
VAI_TRO_DUOC_IN_TEM = {"System Manager", "Stock Manager", "Stock User"}

# Trần số tem một lần in. Bấm nhầm vào nốt gốc mà không có trần thì cả cuộn
# tem chạy ra máy in trước khi kịp dừng.
TRAN_SO_TEM = 500


def _kiem_tra_quyen():
	"""Chặn người đã đăng nhập nhưng không có vai trò kho.

	`@frappe.whitelist()` một mình chỉ chặn khách vãng lai. Danh mục ô lộ ra
	toàn bộ cách bố trí kho, nên đăng nhập hợp lệ không phải điều kiện đủ —
	`Website User` (khách hàng cổng) không có vai trò nào ở đây nên bị chặn.
	"""
	if not VAI_TRO_DUOC_IN_TEM & set(frappe.get_roles()):
		frappe.throw(_("Bạn không có quyền in tem vị trí."), frappe.PermissionError)


@frappe.whitelist()
def danh_sach_tem(goc: str, so_ban=1) -> list[dict]:
	"""Các ô lá dưới `goc` (kể cả chính nó nếu nó là ô lá), thứ tự đường đi.

	`so_ban` là số bản in cho MỖI ô — chỉ dùng để kiểm trần, không nhân dòng
	trả về; phía JS mới nhân lên khi dựng trang in.

	Năm thành phần (Khu/Dãy/Khoang/Tầng/Ô) đi kèm mỗi dòng vì tem SPD in mã
	tách làm ba nhóm, không phải một chuỗi liền. Lấy từ CỘT đã lưu chứ không
	gọi `phan_tich_ma()` ở đây: hàm đó `frappe.throw` khi gặp mã lệch chuẩn,
	nên một bản ghi cũ hỏng sẽ giết cả lệnh in của những ô lành bên cạnh nó.
	`substr` chỉ là lưới đỡ cho bản ghi tạo trước khi có 5 cột — với bản ghi
	bình thường thì `StorageLocation.tach_thanh_phan_ma()` đã điền sẵn, và
	hai đường luôn cho cùng kết quả vì mỗi cấp là tiền tố của cấp sau.
	"""
	_kiem_tra_quyen()

	try:
		so_ban = int(so_ban or 1)
	except (TypeError, ValueError):
		frappe.throw(_("Số bản in phải là một số nguyên."))
	if so_ban < 1:
		frappe.throw(_("Số bản in phải từ 1 trở lên."))

	moc = frappe.db.get_value("Storage Location", goc, ["lft", "rgt"], as_dict=True)
	if not moc:
		frappe.throw(_("Vị trí {0} không tồn tại.").format(goc))

	# BẪY F8, đã trả giá một lần ở `fefo.py`. Bản ghi chưa hội tụ mang
	# lft = rgt = 0; cho qua thì mệnh đề dưới thành `lft between 0 and 0`,
	# tức `lft = 0` — khớp MỌI bản ghi 0/0 khác trên toàn hệ, kể cả của kho
	# khác. Bấm in một khoang lại ra tem của những ô không liên quan, dán
	# nhầm lên kệ, không gì báo. Chặn ở nguồn, không vá bằng vị từ chặt hơn:
	# ở đây so CHÍNH toạ độ của `goc`, mà toạ độ đó mới là thứ hỏng.
	if not moc.lft or not moc.rgt:
		frappe.throw(
			_(
				"Vị trí {0} chưa nằm trong cây vị trí (chưa có toạ độ trong cây) nên không "
				"in tem theo nhánh được. Lưu lại vị trí này để cây tính lại toạ độ, hoặc "
				"chạy lại `bench migrate`, rồi thử lại."
			).format(goc)
		)

	dong = frappe.db.sql(
		"""
		select sl.name as ma_o,
		       ifnull(sl.ma_in_nhan, sl.name) as ma_in_nhan,
		       ifnull(sl.ten_o, '') as ten_o,
		       sl.kho as kho,
		       ifnull(nullif(sl.khu, ''),    substr(sl.name, 1, 2)) as khu,
		       ifnull(nullif(sl.`day`, ''),  substr(sl.name, 3, 2)) as `day`,
		       ifnull(nullif(sl.khoang, ''), substr(sl.name, 5, 2)) as khoang,
		       ifnull(nullif(sl.tang, ''),   substr(sl.name, 7, 2)) as tang,
		       ifnull(nullif(sl.o, ''),      substr(sl.name, 9, 2)) as o
		from `tabStorage Location` sl
		where sl.lft between %(lft)s and %(rgt)s
		      and ifnull(sl.is_group, 0) = 0
		      and ifnull(sl.la_o_chua_xep, 0) = 0
		order by ifnull(sl.thu_tu_lay_hang, 0) asc, sl.name asc
		""",
		{"lft": moc.lft, "rgt": moc.rgt},
		as_dict=True,
	)

	tong = len(dong) * so_ban
	if tong > TRAN_SO_TEM:
		# Từ chối hẳn, KHÔNG cắt bớt: in 500 tem đầu rồi dừng im lặng thì
		# người vận hành tưởng đã in đủ cả nhánh.
		frappe.throw(
			_(
				"Lần in này ra {0} tem ({1} ô × {2} bản), vượt trần {3}. Chọn một nhánh "
				"nhỏ hơn, hoặc giảm số bản in."
			).format(tong, len(dong), so_ban, TRAN_SO_TEM)
		)

	return dong

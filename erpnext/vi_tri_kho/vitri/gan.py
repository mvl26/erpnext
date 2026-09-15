"""Truy vấn dùng chung về gán vị trí — "nút này ai đang giữ".

Tách khỏi controller vì BA nơi cần hỏi cùng một câu: `validate()` của
`Item Location Preference`, cây chọn vị trí, và báo cáo `hang_nam_sai_vi_tri`.
Để trong controller thì hai nơi kia phải dựng một `Document` chỉ để gọi một
hàm thuần truy vấn — và cái giá thật không phải hiệu năng mà là bản sao: hai
định nghĩa "giao nhau" trôi khỏi nhau thì một nửa hệ chặn, nửa kia cho qua.
"""

import frappe


def chu_cua_nhanh(lft: int, rgt: int, tru_ten: str | None = None) -> dict | None:
	"""Gán đang GIAO với khoảng `[lft, rgt]`, hoặc None.

	Điều kiện là hai nhánh GIAO NHAU, không phải bằng nhau. Một vị từ bắt cả
	ba ca, và đó chính là lý do không được viết `s.name = ...`:

	    trùng đúng nút   A giữ 1B0104,   B gán 1B0104      → chặn
	    gán vào con cháu A giữ 1B0104,   B gán 1B010402    → chặn
	    gán vào tổ tiên  A giữ 1B010402, B gán 1B01        → chặn
	    nút anh em       A giữ 1B010401, B gán 1B010402    → CHO QUA

	`tru_ten` loại chính bản ghi đang lưu ra khỏi phép so — thiếu nó thì mọi
	lần lưu lại một gán đã tồn tại đều tự báo "đụng chính mình".

	Gọi hàm này với `lft`/`rgt` bằng 0 là LỖI của nơi gọi: `0 <= rgt and
	0 >= lft` đúng với mọi bản ghi, nên nó sẽ trả về một gán tuỳ ý. Nơi gọi
	phải chặn trước (xem `ItemLocationPreference.kiem_tra_trong_cay`).
	"""
	if not lft or not rgt:
		frappe.throw("chu_cua_nhanh() nhận toạ độ rỗng — nơi gọi phải chặn trước.")

	dong = frappe.db.sql(
		"""
		select p.vat_tu as vat_tu, p.vi_tri as vi_tri, s.lft as lft, s.rgt as rgt
		from `tabItem Location Preference` p
		join `tabStorage Location` s on s.name = p.vi_tri
		where p.name != %(tru)s
		  and s.lft <= %(rgt)s
		  and s.rgt >= %(lft)s
		order by s.lft asc
		limit 1
		""",
		{"tru": tru_ten or "", "lft": lft, "rgt": rgt},
		as_dict=True,
	)
	return dong[0] if dong else None


def ton_khac_trong_nhanh(lft: int, rgt: int, vat_tu: str, gioi_han: int = 3) -> list[dict]:
	"""Tồn của mặt hàng KHÁC `vat_tu` đang nằm trong nhánh `[lft, rgt]`.

	`so_luong != 0` chứ không phải "có dòng": một ô từng có hàng rồi hết vẫn
	còn dòng `Location Balance` mang 0. Coi dòng-0 là "đang có hàng" thì mọi ô
	từng dùng qua sẽ vĩnh viễn không gán được cho ai.

	`gioi_han` chỉ để dựng thông báo (nêu vài ô đầu rồi "… và N ô nữa"), nên
	hàm trả thêm một dòng so với `gioi_han` để nơi gọi biết là còn nữa.
	"""
	if not lft or not rgt:
		frappe.throw("ton_khac_trong_nhanh() nhận toạ độ rỗng — nơi gọi phải chặn trước.")

	return frappe.db.sql(
		"""
		select lb.o as o, lb.vat_tu as vat_tu, lb.so_luong as so_luong
		from `tabLocation Balance` lb
		join `tabStorage Location` sl on sl.name = lb.o
		where sl.lft between %(lft)s and %(rgt)s
		  and lb.so_luong != 0
		  and lb.vat_tu != %(vat_tu)s
		order by sl.lft asc
		limit %(gioi_han)s
		""",
		{"lft": lft, "rgt": rgt, "vat_tu": vat_tu, "gioi_han": gioi_han + 1},
		as_dict=True,
	)

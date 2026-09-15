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


# Mệnh đề dùng chung giữa `ton_khac_trong_nhanh()` (lấy MẪU, có `limit`) và
# `dem_ton_khac_trong_nhanh()` (lấy TỔNG THẬT, không `limit`). Hai truy vấn
# trả lời cùng một câu ("ô nào trong nhánh đang có hàng của mặt hàng khác")
# ở hai độ chi tiết khác nhau — chép tay hai bản `where` là đúng kiểu bản sao
# trôi khỏi nhau mà module này đã trả giá (xem docstring đầu file).
_DIEU_KIEN_TON_KHAC = """sl.lft between %(lft)s and %(rgt)s
	  and lb.so_luong != 0
	  and lb.vat_tu != %(vat_tu)s"""


def ton_khac_trong_nhanh(lft: int, rgt: int, vat_tu: str, gioi_han: int = 3) -> list[dict]:
	"""Tồn của mặt hàng KHÁC `vat_tu` đang nằm trong nhánh `[lft, rgt]` — MẪU,
	tối đa `gioi_han + 1` dòng.

	`so_luong != 0` chứ không phải "có dòng": một ô từng có hàng rồi hết vẫn
	còn dòng `Location Balance` mang 0. Coi dòng-0 là "đang có hàng" thì mọi ô
	từng dùng qua sẽ vĩnh viễn không gán được cho ai.

	`gioi_han` chỉ để dựng danh sách MẪU trong thông báo (nêu vài ô đầu rồi
	"… và N ô nữa"), nên hàm trả thêm một dòng so với `gioi_han` để nơi gọi
	biết là còn nữa.

	VÒNG SỬA 1 (review điều phối): kết quả hàm này KHÔNG đủ để tính N. Nó bị
	`limit` chặn ở `gioi_han + 1`, nên `len(...)` trên đó luôn ra đúng
	`gioi_han + 1` bất kể nhánh có 4 ô hay 400 ô — "N" tính từ số đó luôn
	bằng 1. Muốn N thật, gọi `dem_ton_khac_trong_nhanh()` — một truy vấn
	COUNT riêng, không `limit`, dùng chung `_DIEU_KIEN_TON_KHAC` để không
	trôi khỏi định nghĩa "khác" ở đây.
	"""
	if not lft or not rgt:
		frappe.throw("ton_khac_trong_nhanh() nhận toạ độ rỗng — nơi gọi phải chặn trước.")

	return frappe.db.sql(
		f"""
		select lb.o as o, lb.vat_tu as vat_tu, lb.so_luong as so_luong
		from `tabLocation Balance` lb
		join `tabStorage Location` sl on sl.name = lb.o
		where {_DIEU_KIEN_TON_KHAC}
		order by sl.lft asc
		limit %(gioi_han)s
		""",
		{"lft": lft, "rgt": rgt, "vat_tu": vat_tu, "gioi_han": gioi_han + 1},
		as_dict=True,
	)


def dem_ton_khac_trong_nhanh(lft: int, rgt: int, vat_tu: str) -> int:
	"""Tổng THẬT số ô có tồn mặt hàng khác trong nhánh `[lft, rgt]` — không
	`limit`, nên không bị cắt như kết quả của `ton_khac_trong_nhanh()`.

	Chỉ gọi trên ĐƯỜNG LỖI của `kiem_tra_ton_mat_hang_khac()` (tức chỉ khi
	`ton_khac_trong_nhanh()` đã trả về ít nhất một dòng): đây là truy vấn
	THỨ HAI, dùng để tính đúng "N" trong "… và N ô nữa" mà lấy MẪU không cho
	biết. Đường thành công (nhánh không chồng, phần lớn các lần gán) không
	chạm tới hàm này nên không tốn thêm một round-trip DB nào ở đường nóng.
	"""
	if not lft or not rgt:
		frappe.throw("dem_ton_khac_trong_nhanh() nhận toạ độ rỗng — nơi gọi phải chặn trước.")

	dong = frappe.db.sql(
		f"""
		select count(*) as tong
		from `tabLocation Balance` lb
		join `tabStorage Location` sl on sl.name = lb.o
		where {_DIEU_KIEN_TON_KHAC}
		""",
		{"lft": lft, "rgt": rgt, "vat_tu": vat_tu},
		as_dict=True,
	)
	return dong[0].tong if dong else 0


def doi_ten_theo_mat_hang(doc, method=None, old=None, new=None, merge=False):
	"""Đổi mã mặt hàng thì đổi luôn `name` của bản ghi gán.

	`Document.hook` gọi handler với `(doc, method, *args)` mà `rename_doc` đã
	truyền `(old, new, merge)` — nên chữ ký phải nhận đủ, xem
	`frappe/model/document.py:1357` và `rename_doc.py:207`.

	VÌ SAO KHÔNG ĐƠN GIẢN LÀ `db.set_value("...", ten, "vat_tu", new)`: bản ghi
	gán dùng `autoname: field:vat_tu`, nên `name` MỚI là nguồn sự thật.
	`_sync_autoname_field()` (base_document.py:1027) chạy ở mọi lần lưu và ép
	`vat_tu = name`. Sửa trường mà không sửa `name` thì lần lưu kế tiếp trả
	ngược về mã cũ — im lặng, không lỗi nào.

	`merge=True` (gộp hai mặt hàng) KHÔNG được xoá vô điều kiện — mã đích là
	mặt hàng còn sống sau khi gộp, nên nếu nó CHƯA có gán riêng thì rename như
	nhánh thường là an toàn tuyệt đối, và xoá ở ca đó là vứt mất vị trí cố
	định của một mặt hàng vẫn còn tồn tại mà không ai báo. Gộp là thao tác
	hiếm, nên khoản mất đó có thể nằm im rất lâu trước khi ai phát hiện — đúng
	lớp lỗi im lặng mà cả module này đang phòng, không phải ngoại lệ được
	quyền bỏ qua.

	Chỉ khi mã đích ĐÃ có gán riêng thì mới xoá bản ghi của mã cũ: rename vào
	một `name` đã tồn tại sẽ khiến `rename_doc` ném `DuplicateEntryError` giữa
	chừng một thao tác gộp đang dở. Giữ gán của mã ĐÍCH chứ không phải mã cũ
	vì đích mới là mặt hàng còn tồn tại sau khi gộp — gán của mã cũ trỏ vào
	một mặt hàng sắp biến mất, giữ nó lại không có ý nghĩa gì.

	GHI CHÚ (Task 4, vòng sửa 1): ca "mã đích ĐÃ có gán" hiện KHÔNG kiểm được
	bằng một bài gộp Item thật trong môi trường này — `rename_doc()` tự vỡ ở
	bước chung `update_link_field_values()` (trước `after_rename`, tức trước
	khi hàm này chạy) vì `vat_tu` mang `unique: 1` ở cấp DB, độc lập với khoá
	chính `name`. Nhánh code dưới đây vẫn đúng về Ý ĐỊNH và giữ lại phòng khi
	đường gọi đổi khác đi trong tương lai; chi tiết xem task-4-report.md.
	"""
	if not old or not new or old == new:
		return
	if not frappe.db.exists("Item Location Preference", old):
		return

	if merge and frappe.db.exists("Item Location Preference", new):
		frappe.delete_doc("Item Location Preference", old, ignore_permissions=True, force=True)
		return

	frappe.rename_doc("Item Location Preference", old, new, force=True, show_alert=False)

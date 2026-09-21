"""Thêm unique index (o, vat_tu, so_lo) trên Location Balance (spec §5.3).

JSON của Task 4 bỏ sót ràng buộc này. Không có nó, hai lần ghi gần như đồng
thời vào cùng một khoá tồn có thể cùng thấy "chưa có dòng" và cùng insert —
sinh hai dòng `Location Balance` cho một khoá, `ton_o()` đọc một dòng bất
định trong khi `tong_ton_vi_tri()` (SUM) vẫn cộng cả hai — dòng ma mà lớp
Python một mình không chặn nổi khi có ghi đồng thời thật.

Bảng đang rỗng khi viết patch này nên không cần dọn dữ liệu trùng trước khi
thêm ràng buộc. Nếu sau này bảng có dữ liệu trùng khoá thật (không nên xảy
ra), lệnh ALTER TABLE sẽ tự báo lỗi và dừng migrate — đó là hành vi đúng,
không nên nuốt lỗi đó.

Idempotent: `frappe.db.add_unique()` tự kiểm tra information_schema trước
khi ALTER, nhưng vẫn bọc thêm try/except bắt "Duplicate key name" để chạy
lại an toàn qua nhiều lần `bench migrate` kể cả trong tình huống hiếm gặp
(vd constraint đã tồn tại dưới tên khác do can thiệp tay).
"""

import frappe

TEN_RANG_BUOC = "unique_location_balance_o_vat_tu_so_lo"


def execute():
	try:
		frappe.db.add_unique(
			"Location Balance",
			["o", "vat_tu", "so_lo"],
			constraint_name=TEN_RANG_BUOC,
		)
	except Exception as e:
		if "duplicate key name" not in str(e).lower():
			raise

"""Bản gán vị trí cũ (một nút) → bản gán có bảng con `vi_tri_gan` (22/09/2026).

Trước: `Item Location Preference` có ba cột `vi_tri`, `kho`, `cap_do` trên chính
bản gán. Sau: mỗi nút là một dòng `Item Location Preference Row`. Chạy ở
`[post_model_sync]` — lúc đó bảng con đã được tạo, còn ba cột cũ vẫn nằm trong
bảng cha (Frappe không tự xoá cột khi field biến khỏi JSON), nên đọc được.

Chạy lại nhiều lần vẫn an toàn: bản gán đã có dòng thì bỏ qua; xoá cột cũ xong
thì lần sau `has_column` trả sai và patch dừng ngay.
"""

import frappe

BANG = "tabItem Location Preference"


def _co_cot(cot: str) -> bool:
	"""Hỏi THẲNG CSDL, không qua `frappe.db.has_column` — hàm đó đọc danh sách cột
	từ bộ đệm (`table_columns`), có thể cũ so với bảng thật (đo được trong bài test
	của patch này: thêm cột bằng DDL xong, `has_column` vẫn báo không có)."""
	return bool(frappe.db.sql(f"show columns from `{BANG}` like %s", cot))


def execute():
	if not _co_cot("vi_tri"):
		return

	cu = frappe.db.sql(
		f"select name, vi_tri, kho, cap_do from `{BANG}` where ifnull(vi_tri, '') != ''",
		as_dict=True,
	)
	for g in cu:
		if frappe.db.exists(
			"Item Location Preference Row", {"parent": g.name, "parenttype": "Item Location Preference"}
		):
			continue
		dong = frappe.new_doc("Item Location Preference Row")
		dong.update(
			{
				"parent": g.name,
				"parenttype": "Item Location Preference",
				"parentfield": "vi_tri_gan",
				"idx": 1,
				"vi_tri": g.vi_tri,
				"kho": g.kho,
				"cap_do": g.cap_do,
			}
		)
		dong.db_insert()

	# DDL tự commit — đặt SAU khi đã chép xong dữ liệu, để một lần chạy hỏng giữa
	# chừng không bao giờ xoá cột khi dữ liệu chưa kịp sang bảng con.
	for cot in ("vi_tri", "kho", "cap_do"):
		if _co_cot(cot):
			frappe.db.sql_ddl(f"alter table `{BANG}` drop column `{cot}`")
	frappe.cache.hdel("table_columns", BANG)

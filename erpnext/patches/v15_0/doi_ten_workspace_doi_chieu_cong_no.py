"""Đổi tên workspace "Doi Chieu Cong No" → "Đối chiếu công nợ" (23/10/2026).

Frappe tra workspace theo slug của TÊN (`/app/doi-chieu-cong-no`) nhưng thanh bên
dựng link theo slug của TIÊU ĐỀ (`/app/đối-chiếu-công-nợ`). Tên khác tiêu đề nên
bấm vào thanh bên ra "Page not found". Đặt tên trùng tiêu đề như các workspace tiếng
Việt khác ("Quản lý kho", "Bán hàng").

Tên workspace là khoá chính: bước đồng bộ tạo bản ghi mới từ thư mục
`workspace/đối_chiếu_công_nợ/`, patch này xoá bản ghi cũ để thanh bên không hiện
hai mục. Xoá bằng SQL, không qua ORM: `Workspace.on_trash` ở chế độ developer xoá
cả thư mục workspace trên đĩa.
"""

import frappe

CU = "Doi Chieu Cong No"
CON = (
	"Workspace Link",
	"Workspace Shortcut",
	"Workspace Chart",
	"Workspace Number Card",
	"Workspace Quick List",
	"Workspace Custom Block",
)


def execute():
	if not frappe.db.exists("Workspace", CU):
		return
	for con in CON:
		if frappe.db.table_exists(con):
			frappe.db.delete(con, {"parent": CU, "parenttype": "Workspace"})
	frappe.db.delete("Workspace", {"name": CU})

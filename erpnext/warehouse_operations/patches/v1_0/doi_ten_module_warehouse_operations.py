"""Đổi tên module "Vi Tri Kho" → "Warehouse Operations" trên site ĐÃ cài (21/09/2026).

Chủ đầu tư muốn tên module tiếng Anh ("mình sẽ quản lý kho"); workspace hiển thị
đổi "Vị trí kho" → "Quản lý kho". Code đã chuyển thư mục `erpnext/vi_tri_kho/` →
`erpnext/warehouse_operations/`. Site CHƯA từng cài module (vd. `miyano` trước khi
PR #17 lên) thì patch này không có gì để làm và cài thẳng bằng tên mới.

Chạy ở `[pre_model_sync]` — TRƯỚC bước đồng bộ doctype: bước đó đọc doctype từ
thư mục mới với `"module": "Warehouse Operations"`, nên Module Def phải mang tên
mới trước khi nó chạy.

Sửa thẳng bằng SQL, CỐ Ý không gọi `frappe.rename_doc`:
- `Module Def.on_update` / `on_trash` ở chế độ developer ghi/xoá `modules.txt`
  và thư mục module trên đĩa;
- `Workspace.on_update` / `on_trash` ở chế độ developer xuất/xoá thư mục
  workspace trên đĩa.
Đổi tên qua ORM trên máy dev là để hook sửa lại chính mã nguồn vừa chuyển.

Patch Log: 7 patch cũ đã ghi dưới đường dẫn `erpnext.vi_tri_kho.patches…`. Đổi
đường dẫn trong `patches.txt` mà không đổi Patch Log thì migrate coi chúng là
patch MỚI và chạy lại.
"""

import frappe

CU = "Vi Tri Kho"
MOI = "Warehouse Operations"
WORKSPACE_CU = "Vị trí kho"

# Bảng con của Workspace — xoá theo `parent` cùng bản ghi cha.
_CON_CUA_WORKSPACE = (
	"Workspace Link",
	"Workspace Shortcut",
	"Workspace Chart",
	"Workspace Number Card",
	"Workspace Quick List",
	"Workspace Custom Block",
)


def execute():
	_doi_patch_log()
	if not frappe.db.exists("Module Def", CU):
		return
	_doi_moi_truong_link_toi_module_def()
	if frappe.db.exists("Module Def", MOI):
		frappe.db.delete("Module Def", {"name": CU})
	else:
		frappe.db.sql(
			"update `tabModule Def` set name = %s, module_name = %s where name = %s", (MOI, MOI, CU)
		)
	_xoa_workspace_cu()
	frappe.clear_cache()


def _doi_patch_log():
	frappe.db.sql(
		"""
		update `tabPatch Log`
		set patch = replace(patch, 'erpnext.vi_tri_kho.', 'erpnext.warehouse_operations.')
		where patch like 'erpnext.vi\\_tri\\_kho.%%'
		"""
	)


def _doi_moi_truong_link_toi_module_def():
	"""Mọi trường Link trỏ tới Module Def (DocType.module, Page.module, Report.module,
	Workspace.module, Custom Field.module…) — tìm theo metadata, không liệt kê tay:
	liệt kê tay là bỏ sót đúng cái bảng mình không nghĩ tới."""
	truong = frappe.db.sql(
		"""
		select df.parent, df.fieldname
		from `tabDocField` df
		join `tabDocType` dt on dt.name = df.parent
		where df.fieldtype = 'Link' and df.options = 'Module Def'
		  and ifnull(dt.issingle, 0) = 0 and ifnull(dt.is_virtual, 0) = 0
		union
		select cf.dt, cf.fieldname from `tabCustom Field` cf
		where cf.fieldtype = 'Link' and cf.options = 'Module Def'
		""",
		as_dict=True,
	)
	for t in truong:
		if not frappe.db.table_exists(t.parent):
			continue
		if not frappe.db.has_column(t.parent, t.fieldname):
			continue
		frappe.db.sql(
			f"update `tab{t.parent}` set `{t.fieldname}` = %s where `{t.fieldname}` = %s", (MOI, CU)
		)


def _xoa_workspace_cu():
	"""Workspace đổi tên = bản ghi khác (tên workspace là khoá chính). Bước đồng bộ
	sẽ nhập "Quản lý kho" từ thư mục mới; bản "Vị trí kho" còn lại là một mục menu
	thứ hai trỏ vào cùng module — xoá, bằng SQL (xem docstring module)."""
	if not frappe.db.exists("Workspace", WORKSPACE_CU):
		return
	for con in _CON_CUA_WORKSPACE:
		if frappe.db.table_exists(con):
			frappe.db.delete(con, {"parent": WORKSPACE_CU, "parenttype": "Workspace"})
	frappe.db.delete("Workspace", {"name": WORKSPACE_CU})

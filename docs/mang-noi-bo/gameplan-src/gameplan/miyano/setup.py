"""Thiết lập Mạng nội bộ Miyano.

Chạy một lần sau khi cài app:
    bench --site <site> execute gameplan.miyano.setup.setup_miyano
Có thể chạy lại nhiều lần, chỉ tạo phần còn thiếu.
"""

import frappe

from gameplan.miyano.hr_sync import get_default_team, set_default_team, sync_all

TEAM_TITLE = "Miyano Việt Nam"

GROUPS = [
	{
		"title": "Thông báo công ty",
		"icon": "📢",
		"description": "Thông báo chính thức, chính sách, quy định của Công ty.",
		"restrict": 1,
		"departments": ["Ban lãnh đạo - M", "P. HCNS - pháp chế - M"],
		"notify_all": 1,
		"email": 1,
	},
	{
		"title": "Kinh doanh",
		"icon": "🤝",
		"description": "Hoạt động bán hàng, triển khai tại khách hàng, bệnh viện.",
		"restrict": 1,
		"departments": ["P. Kinh doanh- M", "P. Dịch vụ khách hàng - M", "Đấu thầu và phát triển nguồn hàng - M"],
	},
	{
		"title": "Kỹ thuật – Phần mềm",
		"icon": "💻",
		"description": "Cập nhật SupplyCore, AssetCore, ERP; hướng dẫn sử dụng phần mềm.",
		"restrict": 1,
		"departments": ["P. IT - M"],
	},
	{
		"title": "Kho – Cung ứng",
		"icon": "📦",
		"description": "Nhập xuất kho, tình hình hàng hóa, mua hàng và cung ứng.",
		"restrict": 1,
		"departments": ["Kho - M", "P. Kho vận và cung ứng - M"],
	},
	{
		"title": "Đời sống Miyano",
		"icon": "🎉",
		"description": "Sinh nhật, nghỉ lễ, hoạt động nội bộ, ảnh tập thể — ai cũng đăng được.",
		"restrict": 0,
		"departments": [],
	},
]


def after_migrate():
	setup_department_link()


def setup_department_link():
	"""Nếu site có module HR (Department) thì trường Phòng ban thành Link để chọn từ danh sách."""
	if not frappe.db.exists("DocType", "Department"):
		return
	from frappe.custom.doctype.property_setter.property_setter import make_property_setter

	make_property_setter("GP Project Poster", "department", "fieldtype", "Link", "Select", validate_fields_for_doctype=False)
	make_property_setter("GP Project Poster", "department", "options", "Department", "Text", validate_fields_for_doctype=False)


def setup_miyano(team_title=TEAM_TITLE):
	setup_department_link()

	team = get_default_team()
	if not team:
		team = frappe.db.get_value("GP Team", {"title": team_title})
	if not team:
		team_doc = frappe.get_doc(doctype="GP Team", title=team_title, icon="🏢", is_private=0)
		team_doc.insert(ignore_permissions=True)
		team = team_doc.name
	set_default_team(team)

	has_department = bool(frappe.db.exists("DocType", "Department"))
	created = []
	missing_departments = []
	for g in GROUPS:
		if frappe.db.exists("GP Project", {"title": g["title"], "team": team}):
			continue
		project = frappe.get_doc(
			doctype="GP Project",
			title=g["title"],
			team=team,
			icon=g["icon"],
			description=g["description"],
			readme=f"<p>{g['description']}</p>",
			is_private=0,
			miyano_restrict_posting=g["restrict"],
			miyano_notify_all=g.get("notify_all", 0),
			miyano_email_new_post=g.get("email", 0),
		)
		for dept in g["departments"]:
			if has_department and not frappe.db.exists("Department", dept):
				missing_departments.append((g["title"], dept))
				continue
			project.append("miyano_posters", {"poster_type": "Phòng ban", "department": dept})
		project.insert(ignore_permissions=True)
		created.append(g["title"])

	result = sync_all()
	frappe.db.commit()
	print(f"Không gian: {team}")
	print(f"Nhóm mới tạo: {', '.join(created) or '(không có)'}")
	print(f"Đồng bộ nhân sự: {result}")
	for title, dept in missing_departments:
		print(
			f"CẢNH BÁO: nhóm “{title}” chưa gán được phòng ban “{dept}” vì không có trên ERP. "
			"Vào menu nhóm → Quyền đăng bài & thông báo để gán đúng phòng ban."
		)
	return {
		"team": team,
		"created": created,
		"sync": result,
		"missing_departments": missing_departments,
	}

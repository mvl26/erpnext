# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Danh mục phòng ban chuẩn của một công ty Miyano.

Mỗi phòng có một **mã** ổn định (`stock`, `purchase`, …) để code tham chiếu, một
tên chuẩn dùng khi tạo mới và danh sách bí danh để nhận ra phòng đã có dưới tên
khác (`Kế toán - M`, `P. Kế toán tài chính - M`, `Accounts - M` đều là `accounts`).

Code nghiệp vụ không được so khớp tên phòng ban cứng — người dùng đổi tên phòng
thì mọi cấu hình gieo theo tên chính xác sẽ tạo phòng trùng hoặc mất người nhận.
Hãy gọi `find_department(mã, công ty)` / `ensure_departments(công ty, mã…)`.
"""

import re

import frappe
from frappe import _
from unidecode import unidecode

STOCK = "stock"
PURCHASE = "purchase"
SALES = "sales"
ACCOUNTS = "accounts"
MANAGEMENT = "management"
OPERATIONS = "operations"
HR_LEGAL = "hr_legal"
IT = "it"
CUSTOMER_SERVICE = "customer_service"
QUALITY = "quality"
MARKETING = "marketing"
TECHNICAL = "technical"

#: Thứ tự ở đây là thứ tự tạo khi dựng công ty mới. Bí danh gồm cả tên mặc định
#: tiếng Anh của bản gốc để site cũ đã có bộ phòng ban đó không bị tạo trùng.
CATALOG = (
	{"key": MANAGEMENT, "name": "Ban lãnh đạo", "aliases": ("Ban Giám đốc", "Ban điều hành", "Management")},
	{
		"key": ACCOUNTS,
		"name": "P. Kế toán tài chính",
		"aliases": ("Kế toán", "Tài chính kế toán", "Tài chính", "Accounts", "Finance"),
	},
	{"key": SALES, "name": "P. Kinh doanh", "aliases": ("Bán hàng", "Sales")},
	{"key": PURCHASE, "name": "P. Mua hàng", "aliases": ("Cung ứng", "Purchase", "Purchasing")},
	{"key": STOCK, "name": "P. Kho", "aliases": ("Kho vận", "Kho hàng", "Stores", "Warehouse")},
	{"key": OPERATIONS, "name": "P. Quản lý vận hành", "aliases": ("Vận hành", "Operations")},
	{
		"key": CUSTOMER_SERVICE,
		"name": "P. Dịch vụ khách hàng",
		"aliases": ("Chăm sóc khách hàng", "CSKH", "Customer Service"),
	},
	{"key": TECHNICAL, "name": "P. Kỹ thuật", "aliases": ("Kỹ thuật", "Technical")},
	{
		"key": QUALITY,
		"name": "P. Quản lý chất lượng và tuân thủ",
		"aliases": ("Quản lý chất lượng", "Chất lượng", "QA", "Quality Management"),
	},
	{
		"key": HR_LEGAL,
		"name": "P. HCNS - pháp chế",
		"aliases": ("HCNS", "Hành chính - Nhân sự", "Nhân sự", "Pháp chế", "Human Resources", "Legal"),
	},
	{"key": IT, "name": "P. IT", "aliases": ("Công nghệ thông tin", "CNTT")},
	{"key": MARKETING, "name": "P. Marketing", "aliases": ()},
)

CATALOG_BY_KEY = {row["key"]: row for row in CATALOG}

_PREFIX = re.compile(r"^(p|phong)\b\.?\s*")
_NON_WORD = re.compile(r"[^a-z0-9]+")


def normalize(department_name: str, abbr: str | None = None) -> str:
	"""Đưa tên phòng về dạng so khớp: bỏ dấu, hậu tố viết tắt công ty, tiền tố "P."."""
	text = (department_name or "").strip()
	if abbr:
		text = re.sub(rf"\s*-\s*{re.escape(abbr)}$", "", text)

	text = unidecode(text).lower().strip()
	text = _PREFIX.sub("", text)
	return _NON_WORD.sub(" ", text).strip()


def _patterns(key: str) -> set[str]:
	spec = CATALOG_BY_KEY[key]
	return {normalize(n) for n in (spec["name"], *spec["aliases"])}


def match_rank(key: str, department_name: str, abbr: str | None = None) -> int:
	"""0 = trùng hẳn tên chuẩn/bí danh, 1 = bắt đầu bằng một bí danh, -1 = không khớp.

	Khớp tiền tố theo ranh giới từ để `P. Kế toán quản trị` vẫn là kế toán, còn
	`Khoa học` không bị nhận là `Kho`.
	"""
	text = normalize(department_name, abbr)
	patterns = _patterns(key)
	if text in patterns:
		return 0
	if any(text.startswith(p + " ") for p in patterns):
		return 1
	return -1


def find_department(key: str, company: str | None = None) -> str | None:
	"""Tìm phòng ban đang dùng ứng với mã danh mục, không tạo mới.

	Nhiều phòng cùng khớp (ví dụ site vừa có `Mua hàng - M` vừa có `P. Mua hàng - M`)
	thì ưu tiên khớp hẳn, rồi phòng có nhiều nhân viên đang làm việc hơn, rồi phòng
	tạo trước — phòng thật đang có người thường là phòng đúng.
	"""
	candidates = _candidates(key, company)
	if not candidates and company:
		# Site một công ty đôi khi để trống `company` trên phòng ban.
		candidates = _candidates(key, None)
	if not candidates:
		return None

	counts = _active_employee_counts([c.name for c in candidates])
	candidates.sort(key=lambda c: (c.rank, -counts.get(c.name, 0), c.creation))
	return candidates[0].name


def _candidates(key: str, company: str | None) -> list:
	filters = {"disabled": 0}
	if company:
		filters["company"] = company

	rows = frappe.get_all(
		"Department",
		filters=filters,
		fields=["name", "department_name", "company", "creation"],
	)
	abbrs = {}
	matched = []
	for row in rows:
		if row.company and row.company not in abbrs:
			abbrs[row.company] = frappe.get_cached_value("Company", row.company, "abbr")
		row.rank = match_rank(key, row.department_name, abbrs.get(row.company))
		if row.rank >= 0:
			matched.append(row)
	return matched


def _active_employee_counts(departments: list[str]) -> dict[str, int]:
	if len(departments) < 2 or not frappe.db.exists("DocType", "Employee"):
		return {}

	rows = frappe.get_all(
		"Employee",
		filters={"department": ("in", departments), "status": "Active"},
		fields=["department", "count(name) as total"],
		group_by="department",
	)
	return {r.department: r.total for r in rows}


def ensure_departments(company: str, keys=None) -> dict[str, str]:
	"""Trả {mã: tên phòng ban}, tạo phòng còn thiếu theo tên chuẩn.

	Chạy lại nhiều lần an toàn: phòng đã có (kể cả dưới tên khác khớp bí danh) được
	dùng lại, không tạo trùng, không đổi tên. Phòng mới đặt cạnh các phòng đã có
	của công ty để giữ cây phòng ban gọn.
	"""
	keys = list(keys) if keys else [row["key"] for row in CATALOG]
	resolved = {}
	missing = []
	for key in keys:
		name = find_department(key, company)
		if name:
			resolved[key] = name
		else:
			missing.append(key)

	if missing:
		parent = _sibling_parent(company, list(resolved.values())) or _root_department()
		for key in missing:
			doc = frappe.new_doc("Department")
			doc.department_name = CATALOG_BY_KEY[key]["name"]
			doc.company = company
			if parent:
				doc.parent_department = parent
			doc.insert(ignore_permissions=True)
			resolved[key] = doc.name

	return resolved


def _sibling_parent(company: str, known: list[str]) -> str | None:
	if not known:
		known = frappe.get_all("Department", filters={"company": company, "is_group": 0}, pluck="name")
	parents = frappe.get_all(
		"Department",
		filters={"name": ("in", known or [""]), "parent_department": ("is", "set")},
		pluck="parent_department",
		order_by="creation asc",
		limit=1,
	)
	return parents[0] if parents else None


def _root_department() -> str | None:
	roots = frappe.get_all(
		"Department",
		filters={"is_group": 1, "parent_department": ("in", ("", None))},
		pluck="name",
		limit=1,
	)
	return roots[0] if roots else None


def default_department_records(company: str) -> list[dict]:
	"""Bản ghi cho `make_records` khi dựng công ty mới (thay bộ tiếng Anh của bản gốc)."""
	root = _("All Departments")
	records = [
		{
			"doctype": "Department",
			"department_name": root,
			"is_group": 1,
			"parent_department": "",
			"__condition": lambda: not frappe.db.exists("Department", root),
		}
	]
	records.extend(
		{
			"doctype": "Department",
			"department_name": row["name"],
			"parent_department": root,
			"company": company,
		}
		for row in CATALOG
	)
	return records

# Hồ sơ pháp lý TBYT — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mỗi Item TBYT tra được trọn bộ hồ sơ pháp lý của nó — thiếu gì, hết hạn khi nào — mà một tờ giấy chỉ tồn tại đúng một lần trong hệ thống.

**Architecture:** Module mới `erpnext/tbyt/`. Chứng từ **không** gắn vào Item; chúng gắn vào chủ thể pháp lý thật (Công ty / Chủ sở hữu / Số lưu hành / Lô / Item) qua một bảng phạm vi đa giá trị. Item trỏ tới một `TBYT Marketing Authorization` (số lưu hành) và một resolver phân giải ngược chuỗi Item → Số lưu hành → Chủ sở hữu → Công ty để dựng bộ chứng từ đầy đủ, không sao chép dòng nào.

**Tech Stack:** Frappe/ERPNext v15, Python (tab-indent), MariaDB, bench site `miyano`.

**Spec:** `docs/superpowers/specs/2026-08-20-ho-so-phap-ly-tbyt-design.md`

## Global Constraints

- **Chạy mọi lệnh `bench` từ bench root `/home/miyano/frappe-bench`**, luôn kèm `--site miyano`.
- **Python indent bằng TAB, không phải space.** Line length 110, chuỗi dùng nháy kép. Mọi code block trong kế hoạch này đã dùng tab.
- Dùng **em dash `—`**, không dùng en dash `–` (ruff RUF002/RUF003 sẽ báo lỗi).
- Gate lint là `~/.local/bin/pre-commit run --files <...>` — chạy tay, không có git hook tự động.
- `bench run-tests --module A --module B` **chỉ chạy module cuối**, im lặng bỏ qua cái đầu. Luôn một module một lệnh.
- **Không chạy hai tiến trình `bench run-tests` song song** trên site `miyano` — sinh `QueryDeadlockError` giả.
- Site có rất ít dữ liệu: `Manufacturer` **0 bản ghi**, `Item` 2 bản ghi, `Batch` 0. Mọi suite phải tự dựng fixture. Company là `Miyano` (abbr `M`).
- Test kế thừa `frappe.tests.utils.FrappeTestCase`, chạy trong transaction và được rollback.
- **Không tạo Custom Field** cho các trường trên Item / Item Group — sửa thẳng JSON core. Lý do: `create_custom_fields` chạy ALTER TABLE, ngầm COMMIT transaction của FrappeTestCase và làm rác dữ liệu test.
- Sau mỗi lần sửa file `.json` của DocType: `bench --site miyano migrate`.
- **`mandatory_depends_on` CHỈ chạy phía client.** Không một chỗ nào trong `frappe/model/` đọc nó; thực thi nằm ở `public/js/frappe/form/save.js`. Mọi trường dùng nó **phải** được ghép thêm một kiểm tra server viết tay ném `frappe.MandatoryError`. ERPNext core làm đúng thế: `Item.asset_category` có `mandatory_depends_on`, nhưng `item.py` vẫn viết riêng một kiểm tra server. Thiếu nửa sau thì mọi đường ghi không qua form — import, API, test, script — đều lọt.
- 5 mức chứng từ: `BB` (bắt buộc), `BB*` (bắt buộc có điều kiện), `NC` (nên có), `TH` (theo trường hợp), `KHONG_AP_DUNG`.
- 6 cấp phạm vi: `Company`, `Owner`, `Authorization`, `Batch`, `Item`, `Transaction`.
- Ngưỡng cảnh báo sắp hết hạn: **90 ngày**.
- Tổng danh mục: **23 loại chứng từ × 4 phân loại = 92 dòng rule**.

---

### Task 1: Đăng ký module `tbyt` + hằng số

**Files:**
- Create: `erpnext/tbyt/__init__.py`
- Create: `erpnext/tbyt/constants.py`
- Create: `erpnext/tbyt/doctype/__init__.py`
- Create: `erpnext/tbyt/tests/__init__.py`
- Create: `erpnext/tbyt/tests/test_tbyt_module.py`
- Create: `erpnext/patches/v15_0/add_tbyt_module_def.py`
- Modify: `erpnext/modules.txt` (thêm dòng cuối)
- Modify: `erpnext/patches.txt` (thêm dòng cuối)

**Interfaces:**
- Produces: `erpnext.tbyt.constants` — `SCOPE_COMPANY`, `SCOPE_OWNER`, `SCOPE_AUTHORIZATION`, `SCOPE_BATCH`, `SCOPE_ITEM`, `SCOPE_TRANSACTION`, `SCOPE_DOCTYPE: dict[str, str]`, `LEVEL_BB`, `LEVEL_BB_STAR`, `LEVEL_NC`, `LEVEL_TH`, `LEVEL_NA`, `DEVICE_CLASSES: tuple`, `EXPIRY_WARNING_DAYS: int`, `AUTH_STATUS_*`, `DOC_STATUS_*`, `ITEM_STATUS_*`

- [ ] **Step 1: Viết test thất bại**

Tạo `erpnext/tbyt/tests/test_tbyt_module.py`:

```python
# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Module `tbyt` phải được app khai báo và phân giải được đường dẫn.

Nếu hai điều này sai thì `bench migrate` không tìm thấy DocType của module và
mọi task sau đều hỏng theo — nên đây là lưới an toàn đặt trước tất cả.
"""

import os

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.tbyt import constants


class TestTBYTModule(FrappeTestCase):
	def test_module_is_registered_in_the_app(self):
		self.assertIn("TBYT", frappe.get_module_list("erpnext"))

	def test_module_path_resolves_to_a_real_directory(self):
		path = frappe.get_module_path("TBYT")
		self.assertTrue(os.path.isdir(path), f"Không thấy thư mục module: {path}")

	def test_scope_doctype_map_covers_every_resolvable_scope(self):
		"""Bốn cấp mà resolver phân giải ở Item đều phải ánh xạ được sang DocType."""
		for scope in (
			constants.SCOPE_COMPANY,
			constants.SCOPE_OWNER,
			constants.SCOPE_AUTHORIZATION,
			constants.SCOPE_ITEM,
		):
			self.assertIn(scope, constants.SCOPE_DOCTYPE)

	def test_expiry_warning_threshold_is_ninety_days(self):
		self.assertEqual(constants.EXPIRY_WARNING_DAYS, 90)

	def test_module_def_exists_in_the_database(self):
		"""`bench migrate` không tự tạo Module Def cho module mới — phải có patch.

		Hai test đầu đều đọc từ đĩa (`modules.txt` và thư mục), nên chúng vẫn xanh
		khi DB thiếu bản ghi. Test này đóng đúng khe hở đó.
		"""
		self.assertTrue(frappe.db.exists("Module Def", "TBYT"))
```

- [ ] **Step 2: Chạy test để xác nhận nó đỏ**

```bash
cd /home/miyano/frappe-bench && bench --site miyano run-tests --module erpnext.tbyt.tests.test_tbyt_module
```

Kỳ vọng: FAIL — `ModuleNotFoundError: No module named 'erpnext.tbyt'`.

- [ ] **Step 3: Tạo package và hằng số**

```bash
cd /home/miyano/frappe-bench/apps/erpnext
mkdir -p erpnext/tbyt/doctype erpnext/tbyt/tests
touch erpnext/tbyt/__init__.py erpnext/tbyt/doctype/__init__.py erpnext/tbyt/tests/__init__.py
```

Tạo `erpnext/tbyt/constants.py`:

```python
# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Hằng số dùng chung của hồ sơ pháp lý TBYT.

Gom vào một chỗ vì cả resolver, validate, job hết hạn và report đều đọc chúng —
để rải rác thì sửa một chỗ quên chỗ khác.
"""

# --- Cấp phạm vi: tờ giấy nói về chủ thể nào ---
SCOPE_COMPANY = "Company"
SCOPE_OWNER = "Owner"
SCOPE_AUTHORIZATION = "Authorization"
SCOPE_BATCH = "Batch"
SCOPE_ITEM = "Item"
SCOPE_TRANSACTION = "Transaction"

SCOPE_LEVELS = (
	SCOPE_COMPANY,
	SCOPE_OWNER,
	SCOPE_AUTHORIZATION,
	SCOPE_BATCH,
	SCOPE_ITEM,
	SCOPE_TRANSACTION,
)

# Ánh xạ cấp phạm vi sang DocType thật. `Transaction` không có mặt: hồ sơ phân
# phối dùng đính kèm sẵn có của Delivery Note / Sales Invoice, ngoài phạm vi.
SCOPE_DOCTYPE = {
	SCOPE_COMPANY: "Company",
	SCOPE_OWNER: "Manufacturer",
	SCOPE_AUTHORIZATION: "TBYT Marketing Authorization",
	SCOPE_BATCH: "Batch",
	SCOPE_ITEM: "Item",
}

# --- Mức bắt buộc theo ma trận Thông tư ---
LEVEL_BB = "BB"
LEVEL_BB_STAR = "BB*"
LEVEL_NC = "NC"
LEVEL_TH = "TH"
LEVEL_NA = "KHONG_AP_DUNG"

LEVELS = (LEVEL_BB, LEVEL_BB_STAR, LEVEL_NC, LEVEL_TH, LEVEL_NA)

DEVICE_CLASSES = ("A", "B", "C", "D")

# --- Trạng thái số lưu hành ---
AUTH_STATUS_PENDING = "Đang đăng ký"
AUTH_STATUS_VALID = "Còn hiệu lực"
AUTH_STATUS_EXPIRED = "Hết hiệu lực"
AUTH_STATUS_REVOKED = "Bị thu hồi"

AUTH_STATUSES = (
	AUTH_STATUS_PENDING,
	AUTH_STATUS_VALID,
	AUTH_STATUS_EXPIRED,
	AUTH_STATUS_REVOKED,
)

# --- Trạng thái từng chứng từ ---
DOC_STATUS_VALID = "Còn hiệu lực"
DOC_STATUS_EXPIRING = "Sắp hết hạn"
DOC_STATUS_EXPIRED = "Hết hạn"
DOC_STATUS_SUPERSEDED = "Đã thay thế"

DOC_STATUSES = (
	DOC_STATUS_VALID,
	DOC_STATUS_EXPIRING,
	DOC_STATUS_EXPIRED,
	DOC_STATUS_SUPERSEDED,
)

# --- Trạng thái hồ sơ của Item, xếp từ nặng tới nhẹ ---
ITEM_STATUS_AUTH_INVALID = "Số lưu hành hết hiệu lực"
ITEM_STATUS_AUTH_PENDING = "Chưa có số lưu hành"
ITEM_STATUS_EXPIRED = "Có chứng từ hết hạn"
ITEM_STATUS_MISSING = "Thiếu chứng từ bắt buộc"
ITEM_STATUS_EXPIRING = "Sắp hết hạn"
ITEM_STATUS_OK = "Đủ hồ sơ mặt hàng"

# Thứ tự này là hợp đồng: `get_item_status` trả về giá trị đầu tiên khớp.
ITEM_STATUSES = (
	ITEM_STATUS_AUTH_INVALID,
	ITEM_STATUS_AUTH_PENDING,
	ITEM_STATUS_EXPIRED,
	ITEM_STATUS_MISSING,
	ITEM_STATUS_EXPIRING,
	ITEM_STATUS_OK,
)

# Số ngày trước hạn thì bắt đầu cảnh báo.
EXPIRY_WARNING_DAYS = 90

# Thư mục gốc chứa toàn bộ file hồ sơ TBYT.
ROOT_FOLDER = "Home/TBYT"
ARCHIVE_FOLDER_NAME = "_Luu-tru"

# Tiền tố số giữ cây thư mục đúng thứ tự trong giao diện File.
SCOPE_FOLDER_NAME = {
	SCOPE_COMPANY: "01-Cong-ty",
	SCOPE_OWNER: "02-Chu-so-huu",
	SCOPE_AUTHORIZATION: "03-So-luu-hanh",
	SCOPE_BATCH: "04-Lo",
	SCOPE_ITEM: "05-Item",
}
```

- [ ] **Step 4: Khai báo module**

Thêm `TBYT` vào cuối `erpnext/modules.txt` (sau dòng `Einvoice`):

```bash
printf 'TBYT\n' >> erpnext/modules.txt && tail -3 erpnext/modules.txt
```

- [ ] **Step 5: Tạo Module Def bằng patch, rồi migrate**

`bench migrate` **KHÔNG** tạo Module Def cho module mới thêm vào `modules.txt` —
`frappe.installer.add_module_defs` chỉ chạy lúc **cài app**, không có trong
`frappe/migrate.py`. Thiếu bản ghi này thì DocType khai `"module": "TBYT"` ở Task 2
không có gì để trỏ tới. Repo cũng không có tiền lệ tự động: Module Def của `Einvoice`
được tạo tay ngày 2026-08-07.

Tạo `erpnext/patches/v15_0/add_tbyt_module_def.py`:

```python
# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Tạo Module Def cho module TBYT.

`bench migrate` KHÔNG tạo Module Def cho module mới thêm vào `modules.txt` —
`frappe.installer.add_module_defs` chỉ chạy lúc cài app. Thiếu bản ghi này thì
DocType khai `"module": "TBYT"` không có gì để trỏ tới.
"""

import frappe


def execute():
	if frappe.db.exists("Module Def", "TBYT"):
		return

	doc = frappe.new_doc("Module Def")
	doc.module_name = "TBYT"
	doc.app_name = "erpnext"
	doc.insert(ignore_permissions=True)
```

Thêm dòng vào cuối `erpnext/patches.txt`:

```bash
printf 'erpnext.patches.v15_0.add_tbyt_module_def\n' >> erpnext/patches.txt
```

Rồi chạy:

```bash
cd /home/miyano/frappe-bench && bench --site miyano migrate
```

- [ ] **Step 6: Chạy test để xác nhận nó xanh**

```bash
cd /home/miyano/frappe-bench && bench --site miyano run-tests --module erpnext.tbyt.tests.test_tbyt_module
```

Kỳ vọng: PASS, 5 test.

- [ ] **Step 7: Commit**

```bash
cd /home/miyano/frappe-bench/apps/erpnext
~/.local/bin/pre-commit run --files erpnext/tbyt/constants.py erpnext/tbyt/tests/test_tbyt_module.py
git add erpnext/tbyt erpnext/modules.txt
git commit -m "feat(tbyt): dang ky module va hang so ho so phap ly TBYT"
```

---

### Task 2: DocType `TBYT Document Type` + `TBYT Document Rule`

**Files:**
- Create: `erpnext/tbyt/doctype/tbyt_document_rule/__init__.py`
- Create: `erpnext/tbyt/doctype/tbyt_document_rule/tbyt_document_rule.json`
- Create: `erpnext/tbyt/doctype/tbyt_document_rule/tbyt_document_rule.py`
- Create: `erpnext/tbyt/doctype/tbyt_document_type/__init__.py`
- Create: `erpnext/tbyt/doctype/tbyt_document_type/tbyt_document_type.json`
- Create: `erpnext/tbyt/doctype/tbyt_document_type/tbyt_document_type.py`
- Create: `erpnext/tbyt/doctype/tbyt_document_type/test_tbyt_document_type.py`

**Interfaces:**
- Consumes: `erpnext.tbyt.constants` (Task 1) — `SCOPE_LEVELS`, `LEVELS`, `DEVICE_CLASSES`
- Produces: DocType `TBYT Document Type` (autoname `field:document_key`) với trường `document_key`, `short_code`, `document_name`, `scope_level`, `cho_phep_nhieu_pham_vi`, `mac_dinh_co_thoi_han`, `rules`; DocType con `TBYT Document Rule` với `device_class`, `level`, `condition`. Controller `TBYTDocumentType.validate` chặn rule trùng phân loại.

- [ ] **Step 1: Viết test thất bại**

Tạo `erpnext/tbyt/doctype/tbyt_document_type/test_tbyt_document_type.py`:

```python
# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Danh mục loại chứng từ — khuôn của bảng rule 23 x 4.

`mac_dinh_co_thoi_han` cố ý CHỈ là gợi ý: có hạn hay không là thuộc tính của
từng tờ giấy chứ không phải của loại (số lưu hành C/D nay nhiều giấy cấp vô
thời hạn, giấy cùng loại cấp trước đó vẫn có hạn). Quyền quyết định nằm ở
`khong_thoi_han` trên từng bản ghi chứng từ — xem Task 5.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.tbyt import constants

DOCTYPE = "TBYT Document Type"


def make_document_type(document_key, **kwargs):
	"""Get-or-create để suite chạy lại được sau khi seed thật đã có mặt."""
	if frappe.db.exists(DOCTYPE, document_key):
		return frappe.get_doc(DOCTYPE, document_key)
	doc = frappe.new_doc(DOCTYPE)
	doc.document_key = document_key
	doc.short_code = kwargs.get("short_code", "XX")
	doc.document_name = kwargs.get("document_name", "Chứng từ thử")
	doc.scope_level = kwargs.get("scope_level", constants.SCOPE_AUTHORIZATION)
	doc.cho_phep_nhieu_pham_vi = kwargs.get("cho_phep_nhieu_pham_vi", 0)
	doc.mac_dinh_co_thoi_han = kwargs.get("mac_dinh_co_thoi_han", 0)
	for device_class in kwargs.get("levels", {}):
		doc.append(
			"rules",
			{"device_class": device_class, "level": kwargs["levels"][device_class]},
		)
	doc.insert()
	return doc


class TestTBYTDocumentType(FrappeTestCase):
	def test_document_key_becomes_the_document_name(self):
		doc = make_document_type("_test_key_autoname")
		self.assertEqual(doc.name, "_test_key_autoname")

	def test_rules_hold_one_level_per_device_class(self):
		doc = make_document_type(
			"_test_key_rules",
			levels={"A": constants.LEVEL_BB, "B": constants.LEVEL_NC},
		)
		levels = {row.device_class: row.level for row in doc.rules}
		self.assertEqual(levels, {"A": constants.LEVEL_BB, "B": constants.LEVEL_NC})

	def test_duplicate_device_class_in_rules_is_rejected(self):
		"""Hai dòng cùng phân loại làm mức áp dụng thành nhập nhằng — chặn tại chỗ."""
		doc = frappe.new_doc(DOCTYPE)
		doc.document_key = "_test_key_dup_rule"
		doc.short_code = "XX"
		doc.document_name = "Chứng từ thử"
		doc.scope_level = constants.SCOPE_AUTHORIZATION
		doc.append("rules", {"device_class": "A", "level": constants.LEVEL_BB})
		doc.append("rules", {"device_class": "A", "level": constants.LEVEL_NC})
		with self.assertRaises(frappe.ValidationError):
			doc.insert()

	def test_condition_only_makes_sense_for_bb_star(self):
		"""Điều kiện gắn vào mức không phải BB* là dấu hiệu nhập sai — chặn."""
		doc = frappe.new_doc(DOCTYPE)
		doc.document_key = "_test_key_bad_condition"
		doc.short_code = "XX"
		doc.document_name = "Chứng từ thử"
		doc.scope_level = constants.SCOPE_AUTHORIZATION
		doc.append(
			"rules",
			{
				"device_class": "A",
				"level": constants.LEVEL_BB,
				"condition": "not miyano_la_chu_so_huu",
			},
		)
		with self.assertRaises(frappe.ValidationError):
			doc.insert()
```

- [ ] **Step 2: Chạy test để xác nhận nó đỏ**

```bash
cd /home/miyano/frappe-bench && bench --site miyano run-tests --doctype "TBYT Document Type"
```

Kỳ vọng: FAIL — DocType chưa tồn tại.

- [ ] **Step 3: Tạo DocType con `TBYT Document Rule`**

```bash
cd /home/miyano/frappe-bench/apps/erpnext
mkdir -p erpnext/tbyt/doctype/tbyt_document_rule erpnext/tbyt/doctype/tbyt_document_type
touch erpnext/tbyt/doctype/tbyt_document_rule/__init__.py erpnext/tbyt/doctype/tbyt_document_type/__init__.py
```

`erpnext/tbyt/doctype/tbyt_document_rule/tbyt_document_rule.json`:

```json
{
 "actions": [],
 "creation": "2026-08-21 09:00:00.000000",
 "doctype": "DocType",
 "editable_grid": 1,
 "engine": "InnoDB",
 "field_order": [
  "device_class",
  "level",
  "condition"
 ],
 "fields": [
  {
   "columns": 1,
   "fieldname": "device_class",
   "fieldtype": "Select",
   "in_list_view": 1,
   "label": "Phân loại",
   "options": "A\nB\nC\nD",
   "reqd": 1
  },
  {
   "columns": 2,
   "description": "BB = bắt buộc · BB* = bắt buộc có điều kiện · NC = nên có · TH = theo trường hợp · KHONG_AP_DUNG = không áp dụng.",
   "fieldname": "level",
   "fieldtype": "Select",
   "in_list_view": 1,
   "label": "Mức",
   "options": "BB\nBB*\nNC\nTH\nKHONG_AP_DUNG",
   "reqd": 1
  },
  {
   "columns": 6,
   "description": "Chỉ dùng cho mức BB*. Biểu thức Python đánh giá trên bối cảnh số lưu hành, ví dụ: not miyano_la_chu_so_huu and hang_nhap_khau",
   "fieldname": "condition",
   "fieldtype": "Small Text",
   "in_list_view": 1,
   "label": "Điều kiện"
  }
 ],
 "index_web_pages_for_search": 1,
 "istable": 1,
 "links": [],
 "modified": "2026-08-21 09:00:00.000000",
 "modified_by": "Administrator",
 "module": "TBYT",
 "name": "TBYT Document Rule",
 "owner": "Administrator",
 "permissions": [],
 "sort_field": "modified",
 "sort_order": "DESC",
 "states": []
}
```

`erpnext/tbyt/doctype/tbyt_document_rule/tbyt_document_rule.py`:

```python
# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

from frappe.model.document import Document


class TBYTDocumentRule(Document):
	pass
```

- [ ] **Step 4: Tạo DocType `TBYT Document Type`**

`erpnext/tbyt/doctype/tbyt_document_type/tbyt_document_type.json`:

```json
{
 "actions": [],
 "allow_rename": 0,
 "autoname": "field:document_key",
 "creation": "2026-08-21 09:00:00.000000",
 "doctype": "DocType",
 "editable_grid": 1,
 "engine": "InnoDB",
 "field_order": [
  "document_key",
  "short_code",
  "document_name",
  "column_break_dt_1",
  "scope_level",
  "cho_phep_nhieu_pham_vi",
  "mac_dinh_co_thoi_han",
  "section_break_dt_1",
  "rules"
 ],
 "fields": [
  {
   "description": "Mã trường theo ma trận Thông tư, ví dụ: cfs_giay_luu_hanh",
   "fieldname": "document_key",
   "fieldtype": "Data",
   "in_list_view": 1,
   "label": "Mã chứng từ",
   "reqd": 1,
   "unique": 1
  },
  {
   "description": "Tiền tố dùng đặt tên file, ví dụ: CFS, ISO13485, HDSD",
   "fieldname": "short_code",
   "fieldtype": "Data",
   "in_list_view": 1,
   "label": "Mã ngắn",
   "length": 16,
   "reqd": 1
  },
  {
   "fieldname": "document_name",
   "fieldtype": "Data",
   "in_list_view": 1,
   "label": "Tên chứng từ",
   "reqd": 1
  },
  {
   "fieldname": "column_break_dt_1",
   "fieldtype": "Column Break"
  },
  {
   "description": "Tờ giấy này nói về chủ thể nào. Quyết định resolver tìm nó ở đâu.",
   "fieldname": "scope_level",
   "fieldtype": "Select",
   "in_list_view": 1,
   "label": "Cấp phạm vi",
   "options": "Company\nOwner\nAuthorization\nBatch\nItem\nTransaction",
   "reqd": 1
  },
  {
   "default": "0",
   "description": "Một tờ giấy phủ được nhiều đối tượng cùng cấp — ví dụ một CFS liệt kê 5 số lưu hành.",
   "fieldname": "cho_phep_nhieu_pham_vi",
   "fieldtype": "Check",
   "label": "Cho phép nhiều phạm vi"
  },
  {
   "default": "0",
   "description": "CHỈ là giá trị điền sẵn khi tạo chứng từ mới. Quyền quyết định có hạn hay không nằm ở trường Vô thời hạn trên từng bản ghi chứng từ.",
   "fieldname": "mac_dinh_co_thoi_han",
   "fieldtype": "Check",
   "label": "Mặc định có thời hạn"
  },
  {
   "fieldname": "section_break_dt_1",
   "fieldtype": "Section Break",
   "label": "Mức áp dụng theo phân loại"
  },
  {
   "description": "Mỗi phân loại A/B/C/D đúng một dòng. Bộ Y tế sửa thông tư thì sửa ở đây, không phải sửa code.",
   "fieldname": "rules",
   "fieldtype": "Table",
   "label": "Quy tắc",
   "options": "TBYT Document Rule"
  }
 ],
 "index_web_pages_for_search": 1,
 "links": [],
 "modified": "2026-08-21 09:00:00.000000",
 "modified_by": "Administrator",
 "module": "TBYT",
 "name": "TBYT Document Type",
 "owner": "Administrator",
 "permissions": [
  {
   "create": 1,
   "delete": 1,
   "email": 1,
   "export": 1,
   "print": 1,
   "read": 1,
   "report": 1,
   "role": "System Manager",
   "share": 1,
   "write": 1
  },
  {
   "read": 1,
   "report": 1,
   "role": "Item Manager"
  }
 ],
 "show_title_field_in_link": 1,
 "sort_field": "modified",
 "sort_order": "DESC",
 "states": [],
 "title_field": "document_name",
 "track_changes": 1
}
```

`erpnext/tbyt/doctype/tbyt_document_type/tbyt_document_type.py`:

```python
# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Danh mục 23 loại chứng từ TBYT và mức áp dụng của chúng theo phân loại."""

import frappe
from frappe import _
from frappe.model.document import Document

from erpnext.tbyt.constants import LEVEL_BB_STAR


class TBYTDocumentType(Document):
	def validate(self):
		self._validate_one_rule_per_device_class()
		self._validate_condition_belongs_to_bb_star()

	def _validate_one_rule_per_device_class(self):
		"""Hai dòng cùng phân loại làm mức áp dụng thành nhập nhằng."""
		seen = set()
		for row in self.rules:
			if row.device_class in seen:
				frappe.throw(
					_("Phân loại {0} bị khai hai lần trong bảng quy tắc.").format(row.device_class)
				)
			seen.add(row.device_class)

	def _validate_condition_belongs_to_bb_star(self):
		"""Điều kiện chỉ có nghĩa với BB*; gắn vào mức khác là nhập nhầm."""
		for row in self.rules:
			if row.condition and row.level != LEVEL_BB_STAR:
				frappe.throw(
					_("Dòng phân loại {0}: điều kiện chỉ dùng cho mức {1}, không dùng cho mức {2}.").format(
						row.device_class, LEVEL_BB_STAR, row.level
					)
				)

	def level_for(self, device_class: str) -> tuple[str | None, str | None]:
		"""Trả về (mức, điều kiện) của một phân loại, hoặc (None, None) nếu không khai."""
		for row in self.rules:
			if row.device_class == device_class:
				return row.level, row.condition
		return None, None
```

- [ ] **Step 5: Migrate và chạy test**

```bash
cd /home/miyano/frappe-bench && bench --site miyano migrate && bench --site miyano run-tests --doctype "TBYT Document Type"
```

Kỳ vọng: PASS, 4 test.

- [ ] **Step 6: Commit**

```bash
cd /home/miyano/frappe-bench/apps/erpnext
~/.local/bin/pre-commit run --files erpnext/tbyt/doctype/tbyt_document_type/tbyt_document_type.py erpnext/tbyt/doctype/tbyt_document_rule/tbyt_document_rule.py erpnext/tbyt/doctype/tbyt_document_type/test_tbyt_document_type.py
git add erpnext/tbyt/doctype
git commit -m "feat(tbyt): danh muc loai chung tu va bang quy tac theo phan loai"
```

---

### Task 3: Nạp 23 loại chứng từ + 92 dòng quy tắc

**Files:**
- Create: `erpnext/tbyt/setup.py`
- Create: `erpnext/tbyt/tests/test_tbyt_setup.py`
- Create: `erpnext/patches/v15_0/seed_tbyt_document_types.py`
- Modify: `erpnext/patches.txt` (thêm dòng cuối)

**Interfaces:**
- Consumes: DocType `TBYT Document Type` + `TBYT Document Rule` (Task 2), `erpnext.tbyt.constants` (Task 1)
- Produces: `erpnext.tbyt.setup.setup_tbyt_masters() -> None` (idempotent), `erpnext.tbyt.setup.DOCUMENT_TYPES: tuple[dict, ...]`, `erpnext.tbyt.setup.CONDITIONS: dict[str, str]`

- [ ] **Step 1: Viết test thất bại**

Tạo `erpnext/tbyt/tests/test_tbyt_setup.py`:

```python
# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Bộ danh mục 23 loại chứng từ phải khớp ma trận Thông tư, chạy lại không nhân đôi.

`hop_chuan_hop_quy` là bẫy đã được ghi rõ trong đặc tả: NC ở A/B nhưng TH ở C/D.
Copy danh sách A sang C là sai — nên nó có test riêng.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.tbyt import constants
from erpnext.tbyt.setup import CONDITIONS, DOCUMENT_TYPES, setup_tbyt_masters

DOCTYPE = "TBYT Document Type"


class TestTBYTSetup(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		setup_tbyt_masters()

	def test_all_twenty_three_document_types_exist(self):
		self.assertEqual(len(DOCUMENT_TYPES), 23)
		for spec in DOCUMENT_TYPES:
			self.assertTrue(
				frappe.db.exists(DOCTYPE, spec["document_key"]),
				f"Thiếu loại chứng từ: {spec['document_key']}",
			)

	def test_every_type_declares_all_four_device_classes(self):
		"""23 x 4 = 92 dòng quy tắc, không thiếu phân loại nào."""
		total = 0
		for spec in DOCUMENT_TYPES:
			doc = frappe.get_doc(DOCTYPE, spec["document_key"])
			classes = sorted(row.device_class for row in doc.rules)
			self.assertEqual(classes, list(constants.DEVICE_CLASSES), spec["document_key"])
			total += len(doc.rules)
		self.assertEqual(total, 92)

	def test_hop_chuan_hop_quy_flips_level_between_ab_and_cd(self):
		"""Bẫy đã biết: NC ở A/B, TH ở C/D. Copy nhầm danh sách A sang C là sai."""
		doc = frappe.get_doc(DOCTYPE, "hop_chuan_hop_quy")
		levels = {row.device_class: row.level for row in doc.rules}
		self.assertEqual(levels["A"], constants.LEVEL_NC)
		self.assertEqual(levels["B"], constants.LEVEL_NC)
		self.assertEqual(levels["C"], constants.LEVEL_TH)
		self.assertEqual(levels["D"], constants.LEVEL_TH)

	def test_cong_bo_dk_mua_ban_does_not_apply_to_class_a(self):
		doc = frappe.get_doc(DOCTYPE, "cong_bo_dk_mua_ban")
		levels = {row.device_class: row.level for row in doc.rules}
		self.assertEqual(levels["A"], constants.LEVEL_NA)
		self.assertEqual(levels["B"], constants.LEVEL_BB)

	def test_scope_level_distribution_matches_the_spec(self):
		"""1 Công ty + 2 Chủ sở hữu + 14 Số lưu hành + 3 Lô + 2 Item + 1 Giao dịch = 23."""
		counts = {}
		for spec in DOCUMENT_TYPES:
			counts[spec["scope_level"]] = counts.get(spec["scope_level"], 0) + 1
		self.assertEqual(
			counts,
			{
				constants.SCOPE_COMPANY: 1,
				constants.SCOPE_OWNER: 2,
				constants.SCOPE_AUTHORIZATION: 14,
				constants.SCOPE_BATCH: 3,
				constants.SCOPE_ITEM: 2,
				constants.SCOPE_TRANSACTION: 1,
			},
		)

	def test_exactly_four_types_allow_multiple_scopes(self):
		"""Bốn chứng từ do chủ sở hữu cấp nhưng liệt kê theo sản phẩm."""
		multi = {s["document_key"] for s in DOCUMENT_TYPES if s["cho_phep_nhieu_pham_vi"]}
		self.assertEqual(
			multi,
			{
				"cfs_giay_luu_hanh",
				"giay_uy_quyen_csh",
				"giay_xac_nhan_bao_hanh",
				"uy_quyen_nhap_khau",
			},
		)

	def test_conditions_are_attached_only_to_bb_star_rows(self):
		for key in CONDITIONS:
			doc = frappe.get_doc(DOCTYPE, key)
			for row in doc.rules:
				if row.level == constants.LEVEL_BB_STAR:
					self.assertEqual(row.condition, CONDITIONS[key], key)
				else:
					self.assertFalse(row.condition, key)

	def test_running_setup_twice_does_not_duplicate(self):
		setup_tbyt_masters()
		self.assertEqual(frappe.db.count(DOCTYPE), 23)
		self.assertEqual(
			frappe.db.count("TBYT Document Rule", {"parenttype": DOCTYPE}),
			92,
		)
```

- [ ] **Step 2: Chạy test để xác nhận nó đỏ**

```bash
cd /home/miyano/frappe-bench && bench --site miyano run-tests --module erpnext.tbyt.tests.test_tbyt_setup
```

Kỳ vọng: FAIL — `ImportError: cannot import name 'DOCUMENT_TYPES'`.

- [ ] **Step 3: Viết bảng danh mục và hàm nạp**

Tạo `erpnext/tbyt/setup.py`:

```python
# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Nạp danh mục 23 loại chứng từ TBYT và 92 dòng quy tắc theo phân loại.

Bảng dưới đây chép từ ma trận Thông tư trong
`docs/ma-tran-chung-tu-tbyt-theo-phan-loai.md`. Sửa thông tư thì sửa bảng này
rồi chạy lại patch — không phải sửa code xử lý.

Chạy được nhiều lần: gọi lại không nhân đôi loại chứng từ hay dòng quy tắc.
"""

import frappe

from erpnext.tbyt.constants import (
	DEVICE_CLASSES,
	LEVEL_BB,
	LEVEL_BB_STAR,
	LEVEL_NA,
	LEVEL_NC,
	LEVEL_TH,
	SCOPE_AUTHORIZATION,
	SCOPE_BATCH,
	SCOPE_COMPANY,
	SCOPE_ITEM,
	SCOPE_OWNER,
	SCOPE_TRANSACTION,
)

DOCTYPE = "TBYT Document Type"

# Điều kiện của nhóm BB*. Biểu thức đánh giá trên bối cảnh số lưu hành:
# {"miyano_la_chu_so_huu": 0|1, "hang_nhap_khau": 0|1}.
#
# Ba tờ giấy này sinh ra chính vì Miyano đứng tên hộ người khác — nên điều kiện
# là "không phải chủ sở hữu", không phải "hàng nhập khẩu". Riêng CFS thì phải
# đồng thời là hàng nhập khẩu, vì hàng sản xuất trong nước không có CFS.
CONDITIONS = {
	"giay_uy_quyen_csh": "not miyano_la_chu_so_huu",
	"giay_xac_nhan_bao_hanh": "not miyano_la_chu_so_huu",
	"cfs_giay_luu_hanh": "not miyano_la_chu_so_huu and hang_nhap_khau",
}


def _spec(document_key, short_code, document_name, scope_level, levels, multi=0, expiry=0):
	"""`levels` xếp theo đúng thứ tự DEVICE_CLASSES = (A, B, C, D)."""
	return {
		"document_key": document_key,
		"short_code": short_code,
		"document_name": document_name,
		"scope_level": scope_level,
		"cho_phep_nhieu_pham_vi": multi,
		"mac_dinh_co_thoi_han": expiry,
		"levels": levels,
	}


DOCUMENT_TYPES = (
	_spec(
		"ban_ket_qua_phan_loai",
		"PL",
		"Bản kết quả phân loại thiết bị y tế",
		SCOPE_AUTHORIZATION,
		(LEVEL_BB, LEVEL_BB, LEVEL_BB, LEVEL_BB),
	),
	_spec(
		"so_cong_bo_tieu_chuan",
		"CBTC",
		"Phiếu tiếp nhận hồ sơ công bố tiêu chuẩn áp dụng",
		SCOPE_AUTHORIZATION,
		(LEVEL_BB, LEVEL_BB, LEVEL_NA, LEVEL_NA),
	),
	_spec(
		"gcn_dang_ky_luu_hanh",
		"SLH",
		"Giấy chứng nhận đăng ký lưu hành",
		SCOPE_AUTHORIZATION,
		(LEVEL_NA, LEVEL_NA, LEVEL_BB, LEVEL_BB),
		expiry=1,
	),
	_spec(
		"giay_phep_nhap_khau",
		"GPNK",
		"Giấy phép nhập khẩu",
		SCOPE_AUTHORIZATION,
		(LEVEL_NA, LEVEL_NA, LEVEL_TH, LEVEL_TH),
		expiry=1,
	),
	_spec(
		"mau_nhan_hang_hoa",
		"NHAN",
		"Mẫu nhãn hàng hóa lưu hành tại Việt Nam",
		SCOPE_AUTHORIZATION,
		(LEVEL_BB, LEVEL_BB, LEVEL_BB, LEVEL_BB),
	),
	_spec(
		"hdsd_tieng_viet",
		"HDSD",
		"Hướng dẫn sử dụng bằng tiếng Việt",
		SCOPE_AUTHORIZATION,
		(LEVEL_BB, LEVEL_BB, LEVEL_BB, LEVEL_BB),
	),
	_spec(
		"thong_tin_bao_hanh",
		"BH",
		"Thông tin cơ sở bảo hành, điều kiện và thời gian bảo hành",
		SCOPE_OWNER,
		(LEVEL_BB, LEVEL_BB, LEVEL_BB, LEVEL_BB),
	),
	_spec(
		"co_chung_nhan_xuat_xu",
		"CO",
		"Giấy chứng nhận xuất xứ (CO)",
		SCOPE_BATCH,
		(LEVEL_BB, LEVEL_BB, LEVEL_BB, LEVEL_BB),
	),
	_spec(
		"cq_chung_nhan_chat_luong",
		"CQ",
		"Giấy chứng nhận chất lượng (CQ) của từng lô",
		SCOPE_BATCH,
		(LEVEL_BB, LEVEL_BB, LEVEL_BB, LEVEL_BB),
	),
	_spec(
		"ket_qua_kiem_dinh",
		"KD",
		"Kết quả kiểm định an toàn và tính năng kỹ thuật",
		SCOPE_BATCH,
		(LEVEL_TH, LEVEL_TH, LEVEL_TH, LEVEL_TH),
		expiry=1,
	),
	_spec(
		"tai_lieu_ky_thuat_bao_duong",
		"KTBD",
		"Tài liệu kỹ thuật phục vụ sửa chữa, bảo dưỡng",
		SCOPE_AUTHORIZATION,
		(LEVEL_BB, LEVEL_BB, LEVEL_BB, LEVEL_BB),
	),
	_spec(
		"giay_uy_quyen_csh",
		"UQCSH",
		"Giấy ủy quyền của chủ sở hữu TBYT",
		SCOPE_AUTHORIZATION,
		(LEVEL_BB_STAR, LEVEL_BB_STAR, LEVEL_BB_STAR, LEVEL_BB_STAR),
		multi=1,
		expiry=1,
	),
	_spec(
		"giay_xac_nhan_bao_hanh",
		"XNBH",
		"Giấy xác nhận đủ điều kiện bảo hành",
		SCOPE_AUTHORIZATION,
		(LEVEL_BB_STAR, LEVEL_BB_STAR, LEVEL_BB_STAR, LEVEL_BB_STAR),
		multi=1,
		expiry=1,
	),
	_spec(
		"cfs_giay_luu_hanh",
		"CFS",
		"Giấy chứng nhận lưu hành tự do (CFS)",
		SCOPE_AUTHORIZATION,
		(LEVEL_BB_STAR, LEVEL_BB_STAR, LEVEL_BB_STAR, LEVEL_BB_STAR),
		multi=1,
		expiry=1,
	),
	_spec(
		"iso_13485_nha_san_xuat",
		"ISO13485",
		"Giấy chứng nhận ISO 13485 của cơ sở sản xuất",
		SCOPE_OWNER,
		(LEVEL_NC, LEVEL_NC, LEVEL_NC, LEVEL_NC),
		expiry=1,
	),
	_spec(
		"tai_lieu_ky_thuat_csdt",
		"CSDT",
		"Tài liệu mô tả tóm tắt kỹ thuật tiếng Việt / Hồ sơ kỹ thuật chung ASEAN (CSDT)",
		SCOPE_AUTHORIZATION,
		(LEVEL_NC, LEVEL_NC, LEVEL_NC, LEVEL_NC),
	),
	_spec(
		"hop_chuan_hop_quy",
		"HCHQ",
		"Giấy chứng nhận hợp chuẩn / Giấy chứng nhận hợp quy",
		SCOPE_AUTHORIZATION,
		(LEVEL_NC, LEVEL_NC, LEVEL_TH, LEVEL_TH),
		expiry=1,
	),
	_spec(
		"danh_gia_chat_luong_ivd",
		"IVD",
		"IVD: Giấy chứng nhận đánh giá chất lượng",
		SCOPE_AUTHORIZATION,
		(LEVEL_NA, LEVEL_NA, LEVEL_TH, LEVEL_TH),
		expiry=1,
	),
	_spec(
		"niem_yet_gia",
		"NYG",
		"Thông tin niêm yết giá",
		SCOPE_ITEM,
		(LEVEL_BB, LEVEL_BB, LEVEL_BB, LEVEL_BB),
	),
	_spec(
		"ke_khai_gia",
		"KKG",
		"Hồ sơ kê khai giá",
		SCOPE_ITEM,
		(LEVEL_TH, LEVEL_TH, LEVEL_TH, LEVEL_TH),
	),
	_spec(
		"ho_so_phan_phoi",
		"HSPP",
		"Hồ sơ phân phối",
		SCOPE_TRANSACTION,
		(LEVEL_BB, LEVEL_BB, LEVEL_BB, LEVEL_BB),
	),
	_spec(
		"cong_bo_dk_mua_ban",
		"CBMB",
		"Phiếu tiếp nhận công bố đủ điều kiện mua bán TBYT",
		SCOPE_COMPANY,
		(LEVEL_NA, LEVEL_BB, LEVEL_BB, LEVEL_BB),
	),
	_spec(
		"uy_quyen_nhap_khau",
		"UQNK",
		"Giấy ủy quyền nhập khẩu của chủ sở hữu số lưu hành",
		SCOPE_AUTHORIZATION,
		(LEVEL_TH, LEVEL_TH, LEVEL_TH, LEVEL_TH),
		multi=1,
		expiry=1,
	),
)


def setup_tbyt_masters():
	"""Nạp / cập nhật toàn bộ danh mục. Gọi lại nhiều lần vẫn ra đúng 23 x 4."""
	for spec in DOCUMENT_TYPES:
		_upsert_document_type(spec)


def _upsert_document_type(spec):
	key = spec["document_key"]
	if frappe.db.exists(DOCTYPE, key):
		doc = frappe.get_doc(DOCTYPE, key)
	else:
		doc = frappe.new_doc(DOCTYPE)
		doc.document_key = key

	doc.short_code = spec["short_code"]
	doc.document_name = spec["document_name"]
	doc.scope_level = spec["scope_level"]
	doc.cho_phep_nhieu_pham_vi = spec["cho_phep_nhieu_pham_vi"]
	doc.mac_dinh_co_thoi_han = spec["mac_dinh_co_thoi_han"]

	# Dựng lại toàn bộ bảng quy tắc thay vì vá từng dòng: bảng chỉ 4 dòng, và
	# dựng lại là cách duy nhất để sửa thông tư giảm mức cũng có hiệu lực.
	doc.set("rules", [])
	for device_class, level in zip(DEVICE_CLASSES, spec["levels"], strict=True):
		doc.append(
			"rules",
			{
				"device_class": device_class,
				"level": level,
				"condition": CONDITIONS.get(key) if level == LEVEL_BB_STAR else None,
			},
		)

	doc.flags.ignore_permissions = True
	if doc.is_new():
		doc.insert(ignore_permissions=True)
	else:
		doc.save()
```

- [ ] **Step 4: Chạy test để xác nhận nó xanh**

```bash
cd /home/miyano/frappe-bench && bench --site miyano run-tests --module erpnext.tbyt.tests.test_tbyt_setup
```

Kỳ vọng: PASS, 8 test.

- [ ] **Step 5: Viết patch để nạp lên site đang chạy**

Tạo `erpnext/patches/v15_0/seed_tbyt_document_types.py`:

```python
# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Nạp danh mục 23 loại chứng từ TBYT và 92 dòng quy tắc."""

from erpnext.tbyt.setup import setup_tbyt_masters


def execute():
	setup_tbyt_masters()
```

Thêm dòng vào cuối `erpnext/patches.txt`:

```bash
cd /home/miyano/frappe-bench/apps/erpnext
printf 'erpnext.patches.v15_0.seed_tbyt_document_types\n' >> erpnext/patches.txt
tail -3 erpnext/patches.txt
```

- [ ] **Step 6: Chạy patch và kiểm chứng trên site thật**

```bash
cd /home/miyano/frappe-bench && bench --site miyano migrate
bench --site miyano console <<'EOF'
import frappe; print("types:", frappe.db.count("TBYT Document Type"), "| rules:", frappe.db.count("TBYT Document Rule"))
EOF
```

Kỳ vọng: `types: 23 | rules: 92`.

- [ ] **Step 7: Commit**

```bash
cd /home/miyano/frappe-bench/apps/erpnext
~/.local/bin/pre-commit run --files erpnext/tbyt/setup.py erpnext/tbyt/tests/test_tbyt_setup.py erpnext/patches/v15_0/seed_tbyt_document_types.py
git add erpnext/tbyt/setup.py erpnext/tbyt/tests/test_tbyt_setup.py erpnext/patches/v15_0/seed_tbyt_document_types.py erpnext/patches.txt
git commit -m "feat(tbyt): nap 23 loai chung tu va 92 dong quy tac theo phan loai"
```

---

### Task 4: DocType `TBYT Marketing Authorization` — số lưu hành

**Files:**
- Create: `erpnext/tbyt/doctype/tbyt_marketing_authorization/__init__.py`
- Create: `erpnext/tbyt/doctype/tbyt_marketing_authorization/tbyt_marketing_authorization.json`
- Create: `erpnext/tbyt/doctype/tbyt_marketing_authorization/tbyt_marketing_authorization.py`
- Create: `erpnext/tbyt/doctype/tbyt_marketing_authorization/test_tbyt_marketing_authorization.py`

**Interfaces:**
- Consumes: `erpnext.tbyt.constants` (Task 1) — `AUTH_STATUS_*`
- Produces: DocType `TBYT Marketing Authorization`, naming series `TBYT-LH-.YYYY.-.#####`, `title_field = so_luu_hanh`. Trường: `so_luu_hanh`, `loai_hinh`, `phan_loai`, `chu_so_huu`, `miyano_la_chu_so_huu`, `hang_nhap_khau`, `trang_thai`, `khong_thoi_han`, `ngay_cap`, `ngay_het_han`. Hàm `erpnext.tbyt.doctype.tbyt_marketing_authorization.tbyt_marketing_authorization.get_condition_context(auth_name) -> dict`

- [ ] **Step 1: Viết test thất bại**

Tạo `erpnext/tbyt/doctype/tbyt_marketing_authorization/test_tbyt_marketing_authorization.py`:

```python
# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Số lưu hành — thực thể trung tâm, nguồn sự thật cho phân loại A/B/C/D.

Cho phép trạng thái "Đang đăng ký" với số lưu hành để trống: thực tế phải tạo
mã hàng để báo giá hoặc nhập hàng mẫu TRƯỚC khi Cục cấp số. Bắt buộc có số
thật ngay từ đầu sẽ chặn nghiệp vụ có thật.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.tbyt import constants

DOCTYPE = "TBYT Marketing Authorization"


def make_manufacturer(name="_Test TBYT Hang"):
	"""Site có 0 bản ghi Manufacturer nên mọi suite phải tự dựng."""
	if frappe.db.exists("Manufacturer", name):
		return name
	doc = frappe.new_doc("Manufacturer")
	doc.short_name = name
	doc.insert(ignore_permissions=True)
	return doc.name


def make_authorization(**kwargs):
	doc = frappe.new_doc(DOCTYPE)
	doc.so_luu_hanh = kwargs.get("so_luu_hanh", "_TEST-SLH-001")
	doc.loai_hinh = kwargs.get("loai_hinh", "Số công bố tiêu chuẩn")
	doc.phan_loai = kwargs.get("phan_loai", "B")
	doc.chu_so_huu = kwargs.get("chu_so_huu") or make_manufacturer()
	doc.miyano_la_chu_so_huu = kwargs.get("miyano_la_chu_so_huu", 0)
	doc.hang_nhap_khau = kwargs.get("hang_nhap_khau", 1)
	doc.trang_thai = kwargs.get("trang_thai", constants.AUTH_STATUS_VALID)
	doc.khong_thoi_han = kwargs.get("khong_thoi_han", 1)
	doc.ngay_cap = kwargs.get("ngay_cap", "2026-01-01")
	doc.ngay_het_han = kwargs.get("ngay_het_han")
	doc.insert(ignore_permissions=True)
	return doc


class TestTBYTMarketingAuthorization(FrappeTestCase):
	def test_document_name_uses_naming_series_not_the_number(self):
		"""Số lưu hành thật hay chứa dấu `/` sẽ hỏng routing URL nếu làm tên document."""
		doc = make_authorization(so_luu_hanh="220000123/PCBA-HN")
		self.assertTrue(doc.name.startswith("TBYT-LH-"))
		self.assertNotIn("/", doc.name)

	def test_pending_registration_needs_neither_number_nor_dates(self):
		doc = frappe.new_doc(DOCTYPE)
		doc.loai_hinh = "Số đăng ký lưu hành"
		doc.phan_loai = "C"
		doc.chu_so_huu = make_manufacturer()
		doc.trang_thai = constants.AUTH_STATUS_PENDING
		doc.insert(ignore_permissions=True)
		self.assertFalse(doc.so_luu_hanh)
		self.assertFalse(doc.ngay_cap)

	def test_issued_authorization_requires_issue_date(self):
		doc = frappe.new_doc(DOCTYPE)
		doc.so_luu_hanh = "_TEST-SLH-NO-DATE"
		doc.loai_hinh = "Số công bố tiêu chuẩn"
		doc.phan_loai = "A"
		doc.chu_so_huu = make_manufacturer()
		doc.trang_thai = constants.AUTH_STATUS_VALID
		doc.khong_thoi_han = 1
		with self.assertRaises(frappe.MandatoryError):
			doc.insert(ignore_permissions=True)

	def test_dated_authorization_requires_an_expiry_date(self):
		"""Không tích vô thời hạn thì phải có ngày — nếu không, trống mang hai nghĩa."""
		doc = frappe.new_doc(DOCTYPE)
		doc.so_luu_hanh = "_TEST-SLH-DATED"
		doc.loai_hinh = "Số đăng ký lưu hành"
		doc.phan_loai = "D"
		doc.chu_so_huu = make_manufacturer()
		doc.trang_thai = constants.AUTH_STATUS_VALID
		doc.khong_thoi_han = 0
		doc.ngay_cap = "2026-01-01"
		with self.assertRaises(frappe.MandatoryError):
			doc.insert(ignore_permissions=True)

	def test_indefinite_authorization_must_not_carry_an_expiry_date(self):
		doc = frappe.new_doc(DOCTYPE)
		doc.so_luu_hanh = "_TEST-SLH-CONTRADICT"
		doc.loai_hinh = "Số đăng ký lưu hành"
		doc.phan_loai = "C"
		doc.chu_so_huu = make_manufacturer()
		doc.trang_thai = constants.AUTH_STATUS_VALID
		doc.khong_thoi_han = 1
		doc.ngay_cap = "2026-01-01"
		doc.ngay_het_han = "2030-01-01"
		with self.assertRaises(frappe.ValidationError):
			doc.insert(ignore_permissions=True)

	def test_expiry_date_cannot_precede_issue_date(self):
		doc = frappe.new_doc(DOCTYPE)
		doc.so_luu_hanh = "_TEST-SLH-BACKWARDS"
		doc.loai_hinh = "Số công bố tiêu chuẩn"
		doc.phan_loai = "B"
		doc.chu_so_huu = make_manufacturer()
		doc.trang_thai = constants.AUTH_STATUS_VALID
		doc.khong_thoi_han = 0
		doc.ngay_cap = "2026-06-01"
		doc.ngay_het_han = "2026-01-01"
		with self.assertRaises(frappe.ValidationError):
			doc.insert(ignore_permissions=True)

	def test_condition_context_exposes_the_two_bb_star_switches(self):
		from erpnext.tbyt.doctype.tbyt_marketing_authorization.tbyt_marketing_authorization import (
			get_condition_context,
		)

		doc = make_authorization(
			so_luu_hanh="_TEST-SLH-CTX",
			miyano_la_chu_so_huu=0,
			hang_nhap_khau=1,
		)
		self.assertEqual(
			get_condition_context(doc.name),
			{"miyano_la_chu_so_huu": 0, "hang_nhap_khau": 1},
		)
```

- [ ] **Step 2: Chạy test để xác nhận nó đỏ**

```bash
cd /home/miyano/frappe-bench && bench --site miyano run-tests --doctype "TBYT Marketing Authorization"
```

Kỳ vọng: FAIL — DocType chưa tồn tại.

- [ ] **Step 3: Tạo DocType**

```bash
cd /home/miyano/frappe-bench/apps/erpnext
mkdir -p erpnext/tbyt/doctype/tbyt_marketing_authorization
touch erpnext/tbyt/doctype/tbyt_marketing_authorization/__init__.py
```

`erpnext/tbyt/doctype/tbyt_marketing_authorization/tbyt_marketing_authorization.json`:

```json
{
 "actions": [],
 "autoname": "naming_series:",
 "creation": "2026-08-21 09:00:00.000000",
 "doctype": "DocType",
 "editable_grid": 1,
 "engine": "InnoDB",
 "field_order": [
  "naming_series",
  "so_luu_hanh",
  "loai_hinh",
  "phan_loai",
  "column_break_ma_1",
  "chu_so_huu",
  "miyano_la_chu_so_huu",
  "hang_nhap_khau",
  "section_break_ma_1",
  "trang_thai",
  "khong_thoi_han",
  "column_break_ma_2",
  "ngay_cap",
  "ngay_het_han"
 ],
 "fields": [
  {
   "default": "TBYT-LH-.YYYY.-.#####",
   "fieldname": "naming_series",
   "fieldtype": "Select",
   "hidden": 1,
   "label": "Naming Series",
   "options": "TBYT-LH-.YYYY.-.#####"
  },
  {
   "description": "Số thật do Bộ Y tế cấp. Để trống khi đang nộp hồ sơ đăng ký.",
   "fieldname": "so_luu_hanh",
   "fieldtype": "Data",
   "in_list_view": 1,
   "label": "Số lưu hành",
   "unique": 1
  },
  {
   "fieldname": "loai_hinh",
   "fieldtype": "Select",
   "label": "Loại hình",
   "options": "Số công bố tiêu chuẩn\nSố đăng ký lưu hành",
   "reqd": 1
  },
  {
   "description": "Nguồn sự thật cho phân loại của mọi Item trỏ tới số lưu hành này.",
   "fieldname": "phan_loai",
   "fieldtype": "Select",
   "in_list_view": 1,
   "label": "Phân loại",
   "options": "A\nB\nC\nD",
   "reqd": 1
  },
  {
   "fieldname": "column_break_ma_1",
   "fieldtype": "Column Break"
  },
  {
   "fieldname": "chu_so_huu",
   "fieldtype": "Link",
   "in_list_view": 1,
   "label": "Chủ sở hữu",
   "options": "Manufacturer",
   "reqd": 1
  },
  {
   "default": "0",
   "description": "Bỏ tích khi Miyano chỉ đứng tên hộ. Đây là công tắc của nhóm chứng từ BB*.",
   "fieldname": "miyano_la_chu_so_huu",
   "fieldtype": "Check",
   "label": "Miyano là chủ sở hữu số lưu hành"
  },
  {
   "default": "0",
   "fieldname": "hang_nhap_khau",
   "fieldtype": "Check",
   "label": "Hàng nhập khẩu"
  },
  {
   "fieldname": "section_break_ma_1",
   "fieldtype": "Section Break",
   "label": "Hiệu lực"
  },
  {
   "default": "Đang đăng ký",
   "fieldname": "trang_thai",
   "fieldtype": "Select",
   "in_list_view": 1,
   "label": "Trạng thái",
   "options": "Đang đăng ký\nCòn hiệu lực\nHết hiệu lực\nBị thu hồi",
   "reqd": 1
  },
  {
   "default": "0",
   "description": "Số lưu hành cấp vô thời hạn. Tích vào thì không bao giờ bị cảnh báo hết hạn.",
   "fieldname": "khong_thoi_han",
   "fieldtype": "Check",
   "label": "Vô thời hạn"
  },
  {
   "fieldname": "column_break_ma_2",
   "fieldtype": "Column Break"
  },
  {
   "fieldname": "ngay_cap",
   "fieldtype": "Date",
   "label": "Ngày cấp",
   "mandatory_depends_on": "eval:doc.trang_thai !== \"Đang đăng ký\""
  },
  {
   "fieldname": "ngay_het_han",
   "fieldtype": "Date",
   "label": "Ngày hết hạn",
   "mandatory_depends_on": "eval:doc.trang_thai !== \"Đang đăng ký\" && !doc.khong_thoi_han"
  }
 ],
 "index_web_pages_for_search": 1,
 "links": [],
 "modified": "2026-08-21 09:00:00.000000",
 "modified_by": "Administrator",
 "module": "TBYT",
 "name": "TBYT Marketing Authorization",
 "owner": "Administrator",
 "permissions": [
  {
   "create": 1,
   "delete": 1,
   "email": 1,
   "export": 1,
   "print": 1,
   "read": 1,
   "report": 1,
   "role": "System Manager",
   "share": 1,
   "write": 1
  },
  {
   "create": 1,
   "email": 1,
   "export": 1,
   "print": 1,
   "read": 1,
   "report": 1,
   "role": "Item Manager",
   "share": 1,
   "write": 1
  }
 ],
 "show_title_field_in_link": 1,
 "sort_field": "modified",
 "sort_order": "DESC",
 "states": [],
 "title_field": "so_luu_hanh",
 "track_changes": 1
}
```

`erpnext/tbyt/doctype/tbyt_marketing_authorization/tbyt_marketing_authorization.py`:

```python
# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Số lưu hành TBYT — thực thể trung tâm của hồ sơ pháp lý.

Ngành TBYT dán hồ sơ vào *số lưu hành*, không dán vào SKU: bơm tiêm
1ml/3ml/5ml/10ml là 4 Item nhưng chung một số công bố, một bản phân loại, một
HDSD. Mô hình hóa số lưu hành là cách duy nhất để một tờ giấy chỉ tồn tại một
lần mà mọi Item dưới nó vẫn tra được.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, getdate

from erpnext.tbyt.constants import AUTH_STATUS_PENDING


class TBYTMarketingAuthorization(Document):
	def validate(self):
		self._validate_expiry_is_unambiguous()
		self._validate_date_order()

	def _validate_expiry_is_unambiguous(self):
		"""Vô thời hạn và có ngày hết hạn là hai khẳng định trái nhau."""
		if cint(self.khong_thoi_han) and self.ngay_het_han:
			frappe.throw(
				_("Đã tích Vô thời hạn thì không được điền Ngày hết hạn. Bỏ một trong hai.")
			)

	def _validate_date_order(self):
		if self.ngay_cap and self.ngay_het_han and getdate(self.ngay_het_han) < getdate(self.ngay_cap):
			frappe.throw(_("Ngày hết hạn không được trước Ngày cấp."))

	def is_usable(self) -> bool:
		"""Số lưu hành đang cho phép lưu thông hàng hóa hay không."""
		return self.trang_thai not in (AUTH_STATUS_PENDING,) and not self.is_lapsed()

	def is_lapsed(self) -> bool:
		from erpnext.tbyt.constants import AUTH_STATUS_EXPIRED, AUTH_STATUS_REVOKED

		return self.trang_thai in (AUTH_STATUS_EXPIRED, AUTH_STATUS_REVOKED)


def get_condition_context(authorization: str) -> dict:
	"""Bối cảnh để đánh giá điều kiện của nhóm BB*.

	Trả về đúng hai công tắc mà `TBYT Document Rule.condition` được phép đọc —
	giữ hẹp để biểu thức trong dữ liệu không với tới thứ gì khác.
	"""
	row = frappe.db.get_value(
		"TBYT Marketing Authorization",
		authorization,
		["miyano_la_chu_so_huu", "hang_nhap_khau"],
		as_dict=True,
	)
	if not row:
		return {"miyano_la_chu_so_huu": 0, "hang_nhap_khau": 0}
	return {
		"miyano_la_chu_so_huu": cint(row.miyano_la_chu_so_huu),
		"hang_nhap_khau": cint(row.hang_nhap_khau),
	}
```

- [ ] **Step 4: Migrate và chạy test**

```bash
cd /home/miyano/frappe-bench && bench --site miyano migrate && bench --site miyano run-tests --doctype "TBYT Marketing Authorization"
```

Kỳ vọng: PASS, 7 test.

- [ ] **Step 5: Commit**

```bash
cd /home/miyano/frappe-bench/apps/erpnext
~/.local/bin/pre-commit run --files erpnext/tbyt/doctype/tbyt_marketing_authorization/tbyt_marketing_authorization.py erpnext/tbyt/doctype/tbyt_marketing_authorization/test_tbyt_marketing_authorization.py
git add erpnext/tbyt/doctype/tbyt_marketing_authorization
git commit -m "feat(tbyt): doctype so luu hanh voi hieu luc ba trang thai"
```

---

### Task 5: DocType `TBYT Document Scope` + `TBYT Regulatory Document`

**Files:**
- Create: `erpnext/tbyt/doctype/tbyt_document_scope/__init__.py`
- Create: `erpnext/tbyt/doctype/tbyt_document_scope/tbyt_document_scope.json`
- Create: `erpnext/tbyt/doctype/tbyt_document_scope/tbyt_document_scope.py`
- Create: `erpnext/tbyt/doctype/tbyt_regulatory_document/__init__.py`
- Create: `erpnext/tbyt/doctype/tbyt_regulatory_document/tbyt_regulatory_document.json`
- Create: `erpnext/tbyt/doctype/tbyt_regulatory_document/tbyt_regulatory_document.py`
- Create: `erpnext/tbyt/expiry.py`
- Create: `erpnext/tbyt/tests/test_expiry.py`

**Interfaces:**
- Consumes: `TBYT Document Type` (Task 2), `TBYT Marketing Authorization` (Task 4), `erpnext.tbyt.constants` (Task 1)
- Produces: DocType `TBYT Regulatory Document` (naming series `TBYT-CT-.YYYY.-.#####`) và con `TBYT Document Scope` (`scope_doctype`, `scope_name`); `erpnext.tbyt.expiry.compute_document_status(is_active, khong_thoi_han, ngay_het_han, today=None) -> str`

- [ ] **Step 1: Viết test thất bại**

Tạo `erpnext/tbyt/tests/test_expiry.py`:

```python
# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Ba trạng thái hiệu lực phải tách bạch tuyệt đối.

Nếu `ngay_het_han` để trống mang cả hai nghĩa "vô thời hạn" và "chưa nhập" thì
job hết hạn hoặc báo động giả hàng loạt, hoặc im lặng bỏ sót giấy sắp hết hạn.
Cả hai đều phá hỏng mục tiêu chính của cả tính năng.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, getdate, today

from erpnext.tbyt import constants
from erpnext.tbyt.expiry import compute_document_status

DOCTYPE = "TBYT Regulatory Document"


def make_regulatory_document(document_type, scope_doctype, scope_name, **kwargs):
	"""File là Attach nên chỉ cần một chuỗi URL — không phải tạo File thật."""
	doc = frappe.new_doc(DOCTYPE)
	doc.document_type = document_type
	doc.append("pham_vi", {"scope_doctype": scope_doctype, "scope_name": scope_name})
	doc.so_hieu = kwargs.get("so_hieu", "_TEST-SH-001")
	doc.ngay_cap = kwargs.get("ngay_cap", "2026-01-01")
	doc.khong_thoi_han = kwargs.get("khong_thoi_han", 1)
	doc.ngay_het_han = kwargs.get("ngay_het_han")
	doc.file = kwargs.get("file", "/private/files/_test_tbyt.pdf")
	doc.is_active = kwargs.get("is_active", 1)
	doc.insert(ignore_permissions=True)
	return doc


class TestComputeDocumentStatus(FrappeTestCase):
	def test_indefinite_document_is_always_valid(self):
		self.assertEqual(
			compute_document_status(is_active=1, khong_thoi_han=1, ngay_het_han=None),
			constants.DOC_STATUS_VALID,
		)

	def test_document_far_from_expiry_is_valid(self):
		far = add_days(today(), constants.EXPIRY_WARNING_DAYS + 10)
		self.assertEqual(
			compute_document_status(is_active=1, khong_thoi_han=0, ngay_het_han=far),
			constants.DOC_STATUS_VALID,
		)

	def test_document_inside_the_warning_window_is_expiring(self):
		near = add_days(today(), constants.EXPIRY_WARNING_DAYS - 1)
		self.assertEqual(
			compute_document_status(is_active=1, khong_thoi_han=0, ngay_het_han=near),
			constants.DOC_STATUS_EXPIRING,
		)

	def test_document_past_its_date_is_expired(self):
		past = add_days(today(), -1)
		self.assertEqual(
			compute_document_status(is_active=1, khong_thoi_han=0, ngay_het_han=past),
			constants.DOC_STATUS_EXPIRED,
		)

	def test_expiring_on_the_boundary_day_still_counts_as_expiring(self):
		"""Đúng ngày hết hạn thì vẫn còn hiệu lực trong ngày đó, chỉ là sắp hết."""
		boundary = today()
		self.assertEqual(
			compute_document_status(is_active=1, khong_thoi_han=0, ngay_het_han=boundary),
			constants.DOC_STATUS_EXPIRING,
		)

	def test_inactive_document_is_superseded_regardless_of_dates(self):
		self.assertEqual(
			compute_document_status(is_active=0, khong_thoi_han=1, ngay_het_han=None),
			constants.DOC_STATUS_SUPERSEDED,
		)


class TestRegulatoryDocumentExpiry(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		from erpnext.tbyt.setup import setup_tbyt_masters

		setup_tbyt_masters()

	def setUp(self):
		from erpnext.tbyt.doctype.tbyt_marketing_authorization.test_tbyt_marketing_authorization import (
			make_authorization,
		)

		self.auth = make_authorization(so_luu_hanh=f"_TEST-SLH-EXP-{frappe.generate_hash(length=6)}")

	def test_dated_document_without_expiry_date_cannot_be_saved(self):
		"""Đây là ràng buộc gỡ bỏ hoàn toàn khoảng mờ giữa vô hạn và chưa nhập."""
		doc = frappe.new_doc(DOCTYPE)
		doc.document_type = "hdsd_tieng_viet"
		doc.append(
			"pham_vi",
			{"scope_doctype": "TBYT Marketing Authorization", "scope_name": self.auth.name},
		)
		doc.ngay_cap = "2026-01-01"
		doc.khong_thoi_han = 0
		doc.file = "/private/files/_test_tbyt.pdf"
		with self.assertRaises(frappe.MandatoryError):
			doc.insert(ignore_permissions=True)

	def test_indefinite_document_must_not_carry_an_expiry_date(self):
		doc = frappe.new_doc(DOCTYPE)
		doc.document_type = "hdsd_tieng_viet"
		doc.append(
			"pham_vi",
			{"scope_doctype": "TBYT Marketing Authorization", "scope_name": self.auth.name},
		)
		doc.ngay_cap = "2026-01-01"
		doc.khong_thoi_han = 1
		doc.ngay_het_han = "2030-01-01"
		doc.file = "/private/files/_test_tbyt.pdf"
		with self.assertRaises(frappe.ValidationError):
			doc.insert(ignore_permissions=True)

	def test_status_is_computed_on_save(self):
		doc = make_regulatory_document(
			"hdsd_tieng_viet",
			"TBYT Marketing Authorization",
			self.auth.name,
			khong_thoi_han=0,
			ngay_het_han=add_days(today(), -5),
		)
		self.assertEqual(doc.trang_thai, constants.DOC_STATUS_EXPIRED)

	def test_scope_doctype_is_filled_from_the_document_type(self):
		"""Người dùng chỉ chọn đối tượng; cấp phạm vi suy ra từ loại chứng từ."""
		doc = frappe.new_doc(DOCTYPE)
		doc.document_type = "hdsd_tieng_viet"
		doc.append("pham_vi", {"scope_name": self.auth.name})
		doc.ngay_cap = "2026-01-01"
		doc.khong_thoi_han = 1
		doc.file = "/private/files/_test_tbyt.pdf"
		doc.insert(ignore_permissions=True)
		self.assertEqual(doc.pham_vi[0].scope_doctype, "TBYT Marketing Authorization")

	def test_scope_level_is_denormalised_for_filtering(self):
		doc = make_regulatory_document(
			"hdsd_tieng_viet", "TBYT Marketing Authorization", self.auth.name
		)
		self.assertEqual(doc.scope_level, constants.SCOPE_AUTHORIZATION)

	def test_expiry_date_cannot_precede_issue_date(self):
		doc = frappe.new_doc(DOCTYPE)
		doc.document_type = "hdsd_tieng_viet"
		doc.append(
			"pham_vi",
			{"scope_doctype": "TBYT Marketing Authorization", "scope_name": self.auth.name},
		)
		doc.ngay_cap = "2026-06-01"
		doc.khong_thoi_han = 0
		doc.ngay_het_han = "2026-01-01"
		doc.file = "/private/files/_test_tbyt.pdf"
		with self.assertRaises(frappe.ValidationError):
			doc.insert(ignore_permissions=True)
```

- [ ] **Step 2: Chạy test để xác nhận nó đỏ**

```bash
cd /home/miyano/frappe-bench && bench --site miyano run-tests --module erpnext.tbyt.tests.test_expiry
```

Kỳ vọng: FAIL — `ModuleNotFoundError: No module named 'erpnext.tbyt.expiry'`.

- [ ] **Step 3: Viết hàm tính trạng thái**

Tạo `erpnext/tbyt/expiry.py`:

```python
# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Tính trạng thái hiệu lực của một chứng từ.

Hàm thuần, không chạm DB — để test được mọi mốc thời gian mà không phải dựng
bản ghi. Job hằng ngày (Task 12) dùng lại chính hàm này, nên trạng thái lúc lưu
và trạng thái do job đặt không bao giờ lệch nhau.
"""

from frappe.utils import add_days, cint, getdate

from erpnext.tbyt.constants import (
	DOC_STATUS_EXPIRED,
	DOC_STATUS_EXPIRING,
	DOC_STATUS_SUPERSEDED,
	DOC_STATUS_VALID,
	EXPIRY_WARNING_DAYS,
)


def compute_document_status(is_active, khong_thoi_han, ngay_het_han, today=None) -> str:
	"""Trả về một trong bốn giá trị DOC_STATUS_*.

	`today` để test bơm ngày cố định; bỏ trống thì lấy ngày hệ thống.
	"""
	if not cint(is_active):
		return DOC_STATUS_SUPERSEDED

	# Vô thời hạn: thoát sớm, không bao giờ so ngày. Đây là nhánh giữ cho giấy
	# cấp vô thời hạn khỏi bị job réo hằng ngày.
	if cint(khong_thoi_han):
		return DOC_STATUS_VALID

	if not ngay_het_han:
		# Không lưu được trạng thái này qua form, nhưng dữ liệu cũ có thể lọt.
		return DOC_STATUS_VALID

	reference = getdate(today)
	expiry = getdate(ngay_het_han)

	if expiry < reference:
		return DOC_STATUS_EXPIRED
	if expiry <= getdate(add_days(reference, EXPIRY_WARNING_DAYS - 1)):
		return DOC_STATUS_EXPIRING
	return DOC_STATUS_VALID
```

- [ ] **Step 4: Tạo DocType con `TBYT Document Scope`**

```bash
cd /home/miyano/frappe-bench/apps/erpnext
mkdir -p erpnext/tbyt/doctype/tbyt_document_scope erpnext/tbyt/doctype/tbyt_regulatory_document
touch erpnext/tbyt/doctype/tbyt_document_scope/__init__.py erpnext/tbyt/doctype/tbyt_regulatory_document/__init__.py
```

`erpnext/tbyt/doctype/tbyt_document_scope/tbyt_document_scope.json`:

```json
{
 "actions": [],
 "creation": "2026-08-21 09:00:00.000000",
 "doctype": "DocType",
 "editable_grid": 1,
 "engine": "InnoDB",
 "field_order": [
  "scope_doctype",
  "scope_name"
 ],
 "fields": [
  {
   "columns": 3,
   "description": "Suy từ cấp phạm vi của loại chứng từ — không sửa tay.",
   "fieldname": "scope_doctype",
   "fieldtype": "Link",
   "in_list_view": 1,
   "label": "Loại đối tượng",
   "options": "DocType",
   "read_only": 1,
   "reqd": 1
  },
  {
   "columns": 7,
   "fieldname": "scope_name",
   "fieldtype": "Dynamic Link",
   "in_list_view": 1,
   "label": "Đối tượng",
   "options": "scope_doctype",
   "reqd": 1
  }
 ],
 "index_web_pages_for_search": 1,
 "istable": 1,
 "links": [],
 "modified": "2026-08-21 09:00:00.000000",
 "modified_by": "Administrator",
 "module": "TBYT",
 "name": "TBYT Document Scope",
 "owner": "Administrator",
 "permissions": [],
 "sort_field": "modified",
 "sort_order": "DESC",
 "states": []
}
```

`erpnext/tbyt/doctype/tbyt_document_scope/tbyt_document_scope.py`:

```python
# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

from frappe.model.document import Document


class TBYTDocumentScope(Document):
	pass
```

- [ ] **Step 5: Tạo DocType `TBYT Regulatory Document`**

`erpnext/tbyt/doctype/tbyt_regulatory_document/tbyt_regulatory_document.json`:

```json
{
 "actions": [],
 "autoname": "naming_series:",
 "creation": "2026-08-21 09:00:00.000000",
 "doctype": "DocType",
 "editable_grid": 1,
 "engine": "InnoDB",
 "field_order": [
  "naming_series",
  "document_type",
  "scope_level",
  "short_code",
  "column_break_rd_1",
  "so_hieu",
  "ngay_cap",
  "khong_thoi_han",
  "ngay_het_han",
  "section_break_rd_1",
  "pham_vi",
  "section_break_rd_2",
  "file",
  "column_break_rd_2",
  "trang_thai",
  "is_active",
  "thay_the_cho"
 ],
 "fields": [
  {
   "default": "TBYT-CT-.YYYY.-.#####",
   "fieldname": "naming_series",
   "fieldtype": "Select",
   "hidden": 1,
   "label": "Naming Series",
   "options": "TBYT-CT-.YYYY.-.#####"
  },
  {
   "fieldname": "document_type",
   "fieldtype": "Link",
   "in_list_view": 1,
   "in_standard_filter": 1,
   "label": "Loại chứng từ",
   "options": "TBYT Document Type",
   "reqd": 1
  },
  {
   "fetch_from": "document_type.scope_level",
   "fieldname": "scope_level",
   "fieldtype": "Data",
   "in_standard_filter": 1,
   "label": "Cấp phạm vi",
   "read_only": 1
  },
  {
   "fetch_from": "document_type.short_code",
   "fieldname": "short_code",
   "fieldtype": "Data",
   "hidden": 1,
   "label": "Mã ngắn",
   "read_only": 1
  },
  {
   "fieldname": "column_break_rd_1",
   "fieldtype": "Column Break"
  },
  {
   "fieldname": "so_hieu",
   "fieldtype": "Data",
   "in_list_view": 1,
   "label": "Số hiệu"
  },
  {
   "fieldname": "ngay_cap",
   "fieldtype": "Date",
   "label": "Ngày cấp",
   "reqd": 1
  },
  {
   "default": "0",
   "description": "Tờ giấy này cấp vô thời hạn. Tích vào thì không bao giờ bị cảnh báo hết hạn.",
   "fieldname": "khong_thoi_han",
   "fieldtype": "Check",
   "label": "Vô thời hạn"
  },
  {
   "fieldname": "ngay_het_han",
   "fieldtype": "Date",
   "in_list_view": 1,
   "label": "Ngày hết hạn",
   "mandatory_depends_on": "eval:!doc.khong_thoi_han"
  },
  {
   "fieldname": "section_break_rd_1",
   "fieldtype": "Section Break",
   "label": "Phạm vi áp dụng"
  },
  {
   "description": "Những đối tượng mà tờ giấy này thực sự phủ. Một CFS liệt kê 5 số lưu hành thì khai 5 dòng — vẫn là một bản ghi, không nhân bản.",
   "fieldname": "pham_vi",
   "fieldtype": "Table",
   "label": "Phạm vi",
   "options": "TBYT Document Scope",
   "reqd": 1
  },
  {
   "fieldname": "section_break_rd_2",
   "fieldtype": "Section Break",
   "label": "Tệp và hiệu lực"
  },
  {
   "fieldname": "file",
   "fieldtype": "Attach",
   "label": "Tệp",
   "reqd": 1
  },
  {
   "fieldname": "column_break_rd_2",
   "fieldtype": "Column Break"
  },
  {
   "fieldname": "trang_thai",
   "fieldtype": "Select",
   "in_list_view": 1,
   "in_standard_filter": 1,
   "label": "Trạng thái",
   "options": "Còn hiệu lực\nSắp hết hạn\nHết hạn\nĐã thay thế",
   "read_only": 1
  },
  {
   "default": "1",
   "fieldname": "is_active",
   "fieldtype": "Check",
   "label": "Đang hiệu lực"
  },
  {
   "description": "Bản ghi mà tờ giấy này thay thế khi gia hạn. Bản cũ tự chuyển sang Đã thay thế, không bị ghi đè.",
   "fieldname": "thay_the_cho",
   "fieldtype": "Link",
   "label": "Thay thế cho",
   "options": "TBYT Regulatory Document"
  }
 ],
 "index_web_pages_for_search": 1,
 "links": [],
 "modified": "2026-08-21 09:00:00.000000",
 "modified_by": "Administrator",
 "module": "TBYT",
 "name": "TBYT Regulatory Document",
 "owner": "Administrator",
 "permissions": [
  {
   "create": 1,
   "delete": 1,
   "email": 1,
   "export": 1,
   "print": 1,
   "read": 1,
   "report": 1,
   "role": "System Manager",
   "share": 1,
   "write": 1
  },
  {
   "create": 1,
   "email": 1,
   "export": 1,
   "print": 1,
   "read": 1,
   "report": 1,
   "role": "Item Manager",
   "share": 1,
   "write": 1
  }
 ],
 "sort_field": "modified",
 "sort_order": "DESC",
 "states": [],
 "title_field": "so_hieu",
 "track_changes": 1
}
```

`erpnext/tbyt/doctype/tbyt_regulatory_document/tbyt_regulatory_document.py`:

```python
# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Sổ đăng ký chứng từ pháp lý — một bản ghi là một tờ giấy có thật.

Chứng từ KHÔNG gắn vào Item. Nó gắn vào chủ thể mà nó nói về (công ty, chủ sở
hữu, số lưu hành, lô), và Item phân giải ngược chuỗi để dựng bộ hồ sơ của mình.
Nhờ vậy gia hạn một tờ CFS là sửa một bản ghi, không phải sửa 300 dòng.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, getdate

from erpnext.tbyt.constants import SCOPE_DOCTYPE
from erpnext.tbyt.expiry import compute_document_status


class TBYTRegulatoryDocument(Document):
	def validate(self):
		self._fill_scope_doctype()
		self._validate_expiry_is_declared()
		self._validate_expiry_is_unambiguous()
		self._validate_date_order()
		self._set_status()

	def _fill_scope_doctype(self):
		"""Người dùng chỉ chọn đối tượng; cấp phạm vi suy từ loại chứng từ."""
		scope_level = frappe.db.get_value("TBYT Document Type", self.document_type, "scope_level")
		expected = SCOPE_DOCTYPE.get(scope_level)
		if not expected:
			frappe.throw(
				_("Loại chứng từ {0} ở cấp {1} không gắn được vào bản ghi nào.").format(
					self.document_type, scope_level
				)
			)
		for row in self.pham_vi:
			row.scope_doctype = expected

	def _validate_expiry_is_declared(self):
		"""Nửa server của tri-state. `mandatory_depends_on` chỉ chặn ở trình duyệt.

		Không có hàm này thì tổ hợp "chưa tích Vô thời hạn mà bỏ trống ngày" vẫn lưu
		được qua import, API hay test — và đúng khoảng mờ mà tri-state sinh ra để xoá
		sẽ mở lại.
		"""
		if not cint(self.khong_thoi_han) and not self.ngay_het_han:
			frappe.throw(
				_("Chưa tích Vô thời hạn thì bắt buộc phải điền Ngày hết hạn."),
				frappe.MandatoryError,
			)

	def _validate_expiry_is_unambiguous(self):
		if cint(self.khong_thoi_han) and self.ngay_het_han:
			frappe.throw(
				_("Đã tích Vô thời hạn thì không được điền Ngày hết hạn. Bỏ một trong hai.")
			)

	def _validate_date_order(self):
		if self.ngay_cap and self.ngay_het_han and getdate(self.ngay_het_han) < getdate(self.ngay_cap):
			frappe.throw(_("Ngày hết hạn không được trước Ngày cấp."))

	def _set_status(self):
		self.trang_thai = compute_document_status(
			is_active=self.is_active,
			khong_thoi_han=self.khong_thoi_han,
			ngay_het_han=self.ngay_het_han,
		)
```

- [ ] **Step 6: Migrate và chạy test**

```bash
cd /home/miyano/frappe-bench && bench --site miyano migrate && bench --site miyano run-tests --module erpnext.tbyt.tests.test_expiry
```

Kỳ vọng: PASS, 12 test.

- [ ] **Step 7: Commit**

```bash
cd /home/miyano/frappe-bench/apps/erpnext
~/.local/bin/pre-commit run --files erpnext/tbyt/expiry.py erpnext/tbyt/doctype/tbyt_regulatory_document/tbyt_regulatory_document.py erpnext/tbyt/doctype/tbyt_document_scope/tbyt_document_scope.py erpnext/tbyt/tests/test_expiry.py
git add erpnext/tbyt/doctype/tbyt_document_scope erpnext/tbyt/doctype/tbyt_regulatory_document erpnext/tbyt/expiry.py erpnext/tbyt/tests/test_expiry.py
git commit -m "feat(tbyt): so dang ky chung tu voi pham vi da gia tri va hieu luc ba trang thai"
```

---

### Task 6: Chặn trùng và giữ toàn vẹn phạm vi

**Files:**
- Modify: `erpnext/tbyt/doctype/tbyt_regulatory_document/tbyt_regulatory_document.py`
- Create: `erpnext/tbyt/tests/test_duplicate.py`

**Interfaces:**
- Consumes: `TBYT Regulatory Document` (Task 5)
- Produces: `TBYTRegulatoryDocument._validate_no_duplicate_scope()`, `._validate_scope_count()`, `._supersede_previous()`. Sau task này, **không thể** tồn tại hai bản ghi cùng `document_type` cùng `is_active = 1` phủ cùng một đối tượng.

- [ ] **Step 1: Viết test thất bại**

Tạo `erpnext/tbyt/tests/test_duplicate.py`:

```python
# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Một tờ giấy tồn tại đúng một lần — ràng buộc cứng, không phải kỷ luật người dùng.

Không có lớp chặn này thì hai bản ghi CFS cùng hiệu lực cho một chủ sở hữu vẫn
lưu được, và resolver trở thành KHÔNG TẤT ĐỊNH: hai lần mở cùng một Item có thể
ra hai ngày hết hạn khác nhau tùy thứ tự DB trả về.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.tbyt.doctype.tbyt_marketing_authorization.test_tbyt_marketing_authorization import (
	make_authorization,
	make_manufacturer,
)
from erpnext.tbyt.tests.test_expiry import make_regulatory_document

AUTH_DOCTYPE = "TBYT Marketing Authorization"


class TestRegulatoryDocumentDuplicates(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		from erpnext.tbyt.setup import setup_tbyt_masters

		setup_tbyt_masters()

	def setUp(self):
		suffix = frappe.generate_hash(length=6)
		self.auth = make_authorization(so_luu_hanh=f"_TEST-SLH-DUP-{suffix}")
		self.other = make_authorization(so_luu_hanh=f"_TEST-SLH-DUP2-{suffix}")

	def test_second_active_document_for_the_same_scope_is_blocked(self):
		make_regulatory_document("hdsd_tieng_viet", AUTH_DOCTYPE, self.auth.name)
		with self.assertRaises(frappe.ValidationError):
			make_regulatory_document("hdsd_tieng_viet", AUTH_DOCTYPE, self.auth.name)

	def test_same_type_on_a_different_scope_is_fine(self):
		make_regulatory_document("hdsd_tieng_viet", AUTH_DOCTYPE, self.auth.name)
		doc = make_regulatory_document("hdsd_tieng_viet", AUTH_DOCTYPE, self.other.name)
		self.assertTrue(doc.name)

	def test_inactive_predecessor_does_not_block_a_renewal(self):
		old = make_regulatory_document("hdsd_tieng_viet", AUTH_DOCTYPE, self.auth.name)
		old.is_active = 0
		old.save(ignore_permissions=True)
		new = make_regulatory_document("hdsd_tieng_viet", AUTH_DOCTYPE, self.auth.name)
		self.assertTrue(new.name)

	def test_renewal_via_thay_the_cho_deactivates_the_predecessor(self):
		"""Gia hạn không cần thao tác tay hai bước — khai thay thế là đủ."""
		old = make_regulatory_document("hdsd_tieng_viet", AUTH_DOCTYPE, self.auth.name)
		new = frappe.new_doc("TBYT Regulatory Document")
		new.document_type = "hdsd_tieng_viet"
		new.append("pham_vi", {"scope_name": self.auth.name})
		new.so_hieu = "_TEST-SH-RENEWED"
		new.ngay_cap = "2026-06-01"
		new.khong_thoi_han = 1
		new.file = "/private/files/_test_tbyt.pdf"
		new.thay_the_cho = old.name
		new.insert(ignore_permissions=True)

		old.reload()
		self.assertEqual(old.is_active, 0)
		self.assertEqual(old.trang_thai, "Đã thay thế")

	def test_one_document_may_cover_several_authorizations(self):
		"""Một CFS phủ nhiều số lưu hành = MỘT bản ghi, không nhân bản."""
		before = frappe.db.count("TBYT Regulatory Document")
		doc = frappe.new_doc("TBYT Regulatory Document")
		doc.document_type = "cfs_giay_luu_hanh"
		doc.append("pham_vi", {"scope_name": self.auth.name})
		doc.append("pham_vi", {"scope_name": self.other.name})
		doc.so_hieu = "_TEST-CFS-MULTI"
		doc.ngay_cap = "2026-01-01"
		doc.khong_thoi_han = 1
		doc.file = "/private/files/_test_tbyt.pdf"
		doc.insert(ignore_permissions=True)

		self.assertEqual(len(doc.pham_vi), 2)
		self.assertEqual(frappe.db.count("TBYT Regulatory Document"), before + 1)

	def test_single_scope_type_rejects_a_second_scope_row(self):
		doc = frappe.new_doc("TBYT Regulatory Document")
		doc.document_type = "hdsd_tieng_viet"
		doc.append("pham_vi", {"scope_name": self.auth.name})
		doc.append("pham_vi", {"scope_name": self.other.name})
		doc.so_hieu = "_TEST-SH-TOOMANY"
		doc.ngay_cap = "2026-01-01"
		doc.khong_thoi_han = 1
		doc.file = "/private/files/_test_tbyt.pdf"
		with self.assertRaises(frappe.ValidationError):
			doc.insert(ignore_permissions=True)

	def test_the_same_scope_row_twice_is_rejected(self):
		doc = frappe.new_doc("TBYT Regulatory Document")
		doc.document_type = "cfs_giay_luu_hanh"
		doc.append("pham_vi", {"scope_name": self.auth.name})
		doc.append("pham_vi", {"scope_name": self.auth.name})
		doc.so_hieu = "_TEST-CFS-SELFDUP"
		doc.ngay_cap = "2026-01-01"
		doc.khong_thoi_han = 1
		doc.file = "/private/files/_test_tbyt.pdf"
		with self.assertRaises(frappe.ValidationError):
			doc.insert(ignore_permissions=True)

	def test_multi_scope_document_must_stay_within_one_owner(self):
		"""File chỉ nằm được một thư mục, nên phạm vi không được trải hai hãng."""
		foreign_owner = make_manufacturer("_Test TBYT Hang Khac")
		stranger = make_authorization(
			so_luu_hanh=f"_TEST-SLH-OTHEROWNER-{frappe.generate_hash(length=6)}",
			chu_so_huu=foreign_owner,
		)
		doc = frappe.new_doc("TBYT Regulatory Document")
		doc.document_type = "cfs_giay_luu_hanh"
		doc.append("pham_vi", {"scope_name": self.auth.name})
		doc.append("pham_vi", {"scope_name": stranger.name})
		doc.so_hieu = "_TEST-CFS-CROSSOWNER"
		doc.ngay_cap = "2026-01-01"
		doc.khong_thoi_han = 1
		doc.file = "/private/files/_test_tbyt.pdf"
		with self.assertRaises(frappe.ValidationError):
			doc.insert(ignore_permissions=True)
```

- [ ] **Step 2: Chạy test để xác nhận nó đỏ**

```bash
cd /home/miyano/frappe-bench && bench --site miyano run-tests --module erpnext.tbyt.tests.test_duplicate
```

Kỳ vọng: FAIL — bản ghi thứ hai vẫn lưu được, không có `ValidationError`.

- [ ] **Step 3: Thêm các lớp kiểm tra vào controller**

Sửa `erpnext/tbyt/doctype/tbyt_regulatory_document/tbyt_regulatory_document.py` — thay thân `validate` và thêm bốn phương thức:

```python
	def validate(self):
		self._fill_scope_doctype()
		self._validate_expiry_is_declared()
		self._validate_scope_count()
		self._validate_scope_rows_are_distinct()
		self._validate_single_owner()
		self._validate_no_duplicate_scope()
		self._validate_expiry_is_unambiguous()
		self._validate_date_order()
		self._set_status()

	def on_update(self):
		self._supersede_previous()

	def _validate_scope_count(self):
		"""Loại không cho nhiều phạm vi thì đúng một dòng — nhiều hơn là nhập nhầm."""
		allows_many = frappe.db.get_value(
			"TBYT Document Type", self.document_type, "cho_phep_nhieu_pham_vi"
		)
		if not cint(allows_many) and len(self.pham_vi) > 1:
			frappe.throw(
				_("Loại chứng từ {0} chỉ nhận một phạm vi, đang khai {1}.").format(
					self.document_type, len(self.pham_vi)
				)
			)

	def _validate_scope_rows_are_distinct(self):
		seen = set()
		for row in self.pham_vi:
			if row.scope_name in seen:
				frappe.throw(_("Đối tượng {0} bị khai hai lần trong bảng phạm vi.").format(row.scope_name))
			seen.add(row.scope_name)

	def _validate_single_owner(self):
		"""Chứng từ đa phạm vi phải nằm gọn trong một chủ sở hữu.

		Một file chỉ nằm được ở một thư mục (§7 đặc tả), và cả bốn loại đa phạm
		vi đều do chủ sở hữu cấp — trải hai hãng là dấu hiệu khai nhầm.
		"""
		if len(self.pham_vi) < 2:
			return
		if self.pham_vi[0].scope_doctype != "TBYT Marketing Authorization":
			return
		owners = {
			frappe.db.get_value("TBYT Marketing Authorization", row.scope_name, "chu_so_huu")
			for row in self.pham_vi
		}
		if len(owners) > 1:
			frappe.throw(
				_("Các số lưu hành trong bảng phạm vi thuộc {0} chủ sở hữu khác nhau.").format(len(owners))
			)

	def _validate_no_duplicate_scope(self):
		"""Không cho hai bản ghi còn hiệu lực cùng loại phủ cùng một đối tượng.

		Đây là ràng buộc bảo đảm resolver tất định: mỗi (loại, đối tượng) có
		nhiều nhất một bản ghi đang hiệu lực.
		"""
		if not cint(self.is_active):
			return
		for row in self.pham_vi:
			clash = frappe.db.sql(
				"""
				select rd.name
				from `tabTBYT Regulatory Document` rd
				inner join `tabTBYT Document Scope` sc on sc.parent = rd.name
				where rd.document_type = %(document_type)s
					and rd.is_active = 1
					and rd.name != %(name)s
					and sc.parenttype = 'TBYT Regulatory Document'
					and sc.scope_doctype = %(scope_doctype)s
					and sc.scope_name = %(scope_name)s
				limit 1
				""",
				{
					"document_type": self.document_type,
					"name": self.name or "",
					"scope_doctype": row.scope_doctype,
					"scope_name": row.scope_name,
				},
			)
			if clash:
				frappe.throw(
					_(
						"{0} của {1} đã có bản ghi còn hiệu lực: {2}. "
						"Nếu đây là bản gia hạn, hãy khai nó ở trường Thay thế cho."
					).format(self.document_type, row.scope_name, clash[0][0])
				)

	def _supersede_previous(self):
		"""Khai Thay thế cho là đủ — bản cũ tự rút lui, không cần thao tác hai bước."""
		if not self.thay_the_cho:
			return
		previous = frappe.get_doc("TBYT Regulatory Document", self.thay_the_cho)
		if not cint(previous.is_active):
			return
		previous.is_active = 0
		previous.flags.ignore_permissions = True
		previous.save()
```

- [ ] **Step 4: Chạy test để xác nhận nó xanh**

```bash
cd /home/miyano/frappe-bench && bench --site miyano run-tests --module erpnext.tbyt.tests.test_duplicate
```

Kỳ vọng: PASS, 8 test.

- [ ] **Step 5: Chạy lại suite Task 5 để chắc không vỡ**

```bash
cd /home/miyano/frappe-bench && bench --site miyano run-tests --module erpnext.tbyt.tests.test_expiry
```

Kỳ vọng: PASS, 12 test.

- [ ] **Step 6: Commit**

```bash
cd /home/miyano/frappe-bench/apps/erpnext
~/.local/bin/pre-commit run --files erpnext/tbyt/doctype/tbyt_regulatory_document/tbyt_regulatory_document.py erpnext/tbyt/tests/test_duplicate.py
git add erpnext/tbyt/doctype/tbyt_regulatory_document erpnext/tbyt/tests/test_duplicate.py
git commit -m "feat(tbyt): chan trung chung tu va giu toan ven bang pham vi"
```

---

### Task 7: Trường TBYT trên Item và Item Group

**Files:**
- Modify: `erpnext/stock/doctype/item/item.json`
- Modify: `erpnext/setup/doctype/item_group/item_group.json`
- Create: `erpnext/tbyt/item_hooks.py`
- Modify: `erpnext/hooks.py` (mục `doc_events`, dòng 333)
- Create: `erpnext/tbyt/tests/test_item_fields.py`

**Interfaces:**
- Consumes: `TBYT Marketing Authorization` (Task 4)
- Produces: trường Item `la_thiet_bi_y_te`, `so_luu_hanh`, `phan_loai_tbyt`, `tinh_trang_ho_so`, `ho_so_tbyt_html`; trường Item Group `la_tbyt`; `erpnext.tbyt.item_hooks.set_default_medical_flag(doc, method=None)`, `erpnext.tbyt.item_hooks.require_authorization_for_medical_item(doc, method=None)`

**Lưu ý:** sửa thẳng JSON core, **không** dùng Custom Field — `create_custom_fields` chạy ALTER TABLE và ngầm COMMIT transaction của FrappeTestCase, làm rác dữ liệu của mọi suite chạy sau.

- [ ] **Step 1: Viết test thất bại**

Tạo `erpnext/tbyt/tests/test_item_fields.py`:

```python
# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Số lưu hành là ràng buộc CỨNG duy nhất của cả tính năng.

Chứng từ thì thiếu tạm thời được — chúng phụ thuộc nhà cung cấp gửi. Nhưng số
lưu hành là điều kiện pháp lý để hàng được phép lưu thông: không có nó thì mã
hàng không có cơ sở tồn tại. Trường hợp chưa được Cục cấp số thì vẫn khai được
qua bản ghi trạng thái "Đang đăng ký".
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.tbyt.doctype.tbyt_marketing_authorization.test_tbyt_marketing_authorization import (
	make_authorization,
)

MEDICAL_GROUP = "_Test Nhom TBYT"


def make_item_group(name=MEDICAL_GROUP, la_tbyt=1):
	if frappe.db.exists("Item Group", name):
		doc = frappe.get_doc("Item Group", name)
		if doc.la_tbyt != la_tbyt:
			doc.la_tbyt = la_tbyt
			doc.save(ignore_permissions=True)
		return name
	doc = frappe.new_doc("Item Group")
	doc.item_group_name = name
	doc.parent_item_group = "All Item Groups"
	doc.is_group = 0
	doc.la_tbyt = la_tbyt
	doc.insert(ignore_permissions=True)
	return doc.name


def make_item(item_code, **kwargs):
	doc = frappe.new_doc("Item")
	doc.item_code = item_code
	doc.item_name = kwargs.get("item_name", item_code)
	doc.item_group = kwargs.get("item_group", make_item_group())
	doc.stock_uom = kwargs.get("stock_uom", "Nos")
	doc.is_stock_item = 0
	if "la_thiet_bi_y_te" in kwargs:
		doc.la_thiet_bi_y_te = kwargs["la_thiet_bi_y_te"]
	if "so_luu_hanh" in kwargs:
		doc.so_luu_hanh = kwargs["so_luu_hanh"]
	doc.insert(ignore_permissions=True)
	return doc


class TestItemTBYTFields(FrappeTestCase):
	def setUp(self):
		self.suffix = frappe.generate_hash(length=6)
		self.auth = make_authorization(
			so_luu_hanh=f"_TEST-SLH-ITEM-{self.suffix}", phan_loai="C"
		)

	def test_medical_flag_defaults_from_the_item_group(self):
		item = make_item(f"_TEST-TBYT-DEFAULT-{self.suffix}", so_luu_hanh=self.auth.name)
		self.assertEqual(item.la_thiet_bi_y_te, 1)

	def test_non_medical_group_leaves_the_flag_off(self):
		group = make_item_group("_Test Nhom Thuong", la_tbyt=0)
		item = make_item(f"_TEST-TBYT-PLAIN-{self.suffix}", item_group=group)
		self.assertEqual(item.la_thiet_bi_y_te, 0)

	def test_medical_item_without_authorization_cannot_be_saved(self):
		doc = frappe.new_doc("Item")
		doc.item_code = f"_TEST-TBYT-NOAUTH-{self.suffix}"
		doc.item_name = doc.item_code
		doc.item_group = make_item_group()
		doc.stock_uom = "Nos"
		doc.is_stock_item = 0
		with self.assertRaises(frappe.MandatoryError):
			doc.insert(ignore_permissions=True)

	def test_device_class_is_fetched_from_the_authorization(self):
		"""Suy ra, không nhập tay — hai item cùng số lưu hành không thể khai lệch loại."""
		item = make_item(f"_TEST-TBYT-CLASS-{self.suffix}", so_luu_hanh=self.auth.name)
		self.assertEqual(item.phan_loai_tbyt, "C")

	def test_device_class_field_is_read_only(self):
		meta = frappe.get_meta("Item")
		self.assertEqual(meta.get_field("phan_loai_tbyt").read_only, 1)

	def test_authorization_is_only_mandatory_for_medical_items(self):
		group = make_item_group("_Test Nhom Thuong", la_tbyt=0)
		item = make_item(f"_TEST-TBYT-OPTIONAL-{self.suffix}", item_group=group)
		self.assertFalse(item.so_luu_hanh)

	def test_manual_override_of_the_medical_flag_survives_saving(self):
		"""Bỏ tích rồi lưu lại không được bị nhóm hàng ghi đè ngược."""
		group = make_item_group("_Test Nhom Thuong", la_tbyt=0)
		item = make_item(
			f"_TEST-TBYT-OVERRIDE-{self.suffix}",
			item_group=group,
			la_thiet_bi_y_te=1,
			so_luu_hanh=self.auth.name,
		)
		item.reload()
		item.item_name = "Doi ten"
		item.save(ignore_permissions=True)
		self.assertEqual(item.la_thiet_bi_y_te, 1)
```

- [ ] **Step 2: Chạy test để xác nhận nó đỏ**

```bash
cd /home/miyano/frappe-bench && bench --site miyano run-tests --module erpnext.tbyt.tests.test_item_fields
```

Kỳ vọng: FAIL — `Item Group` chưa có trường `la_tbyt`.

- [ ] **Step 3: Thêm trường vào `item_group.json`**

Chạy script sau từ `/home/miyano/frappe-bench/apps/erpnext` (idempotent — chạy lại không nhân đôi):

```python
import json

PATH = "erpnext/setup/doctype/item_group/item_group.json"
FIELD = {
	"default": "0",
	"description": "Mặt hàng thuộc nhóm này mặc định là thiết bị / vật tư y tế và cần hồ sơ pháp lý TBYT.",
	"fieldname": "la_tbyt",
	"fieldtype": "Check",
	"label": "Là nhóm thiết bị y tế",
}

with open(PATH, encoding="utf-8") as fh:
	doc = json.load(fh)

if not any(f["fieldname"] == "la_tbyt" for f in doc["fields"]):
	doc["fields"].append(FIELD)
	doc["field_order"].append("la_tbyt")
	with open(PATH, "w", encoding="utf-8") as fh:
		json.dump(doc, fh, indent=1, ensure_ascii=False, sort_keys=True)
		fh.write("\n")
	print("da them la_tbyt")
else:
	print("da co san")
```

- [ ] **Step 4: Thêm tab Hồ sơ TBYT vào `item.json`**

Chạy script sau từ `/home/miyano/frappe-bench/apps/erpnext` (idempotent):

```python
import json

PATH = "erpnext/stock/doctype/item/item.json"

NEW_FIELDS = [
	{
		"fieldname": "tbyt_tab",
		"fieldtype": "Tab Break",
		"label": "Hồ sơ TBYT",
	},
	{
		"default": "0",
		"description": "Mặc định lấy theo nhóm hàng khi tạo mới; sửa tay được.",
		"fieldname": "la_thiet_bi_y_te",
		"fieldtype": "Check",
		"label": "Là thiết bị / vật tư y tế",
	},
	{
		"depends_on": "la_thiet_bi_y_te",
		"description": "Chưa được Cục cấp số thì vẫn chọn được bản ghi ở trạng thái Đang đăng ký.",
		"fieldname": "so_luu_hanh",
		"fieldtype": "Link",
		"label": "Số lưu hành",
		"mandatory_depends_on": "eval:doc.la_thiet_bi_y_te",
		"options": "TBYT Marketing Authorization",
	},
	{
		"depends_on": "la_thiet_bi_y_te",
		"description": "Suy từ số lưu hành — không nhập tay để hai mặt hàng cùng số không thể khai lệch loại.",
		"fetch_from": "so_luu_hanh.phan_loai",
		"fieldname": "phan_loai_tbyt",
		"fieldtype": "Data",
		"label": "Phân loại TBYT",
		"read_only": 1,
	},
	{
		"fieldname": "column_break_tbyt",
		"fieldtype": "Column Break",
	},
	{
		"depends_on": "la_thiet_bi_y_te",
		"description": "Chỉ xét hồ sơ cấp mặt hàng. Chứng từ theo lô (CQ, CO) xem ở Batch và trong báo cáo.",
		"fieldname": "tinh_trang_ho_so",
		"fieldtype": "Select",
		"label": "Tình trạng hồ sơ",
		"options": "\nSố lưu hành hết hiệu lực\nChưa có số lưu hành\nCó chứng từ hết hạn\nThiếu chứng từ bắt buộc\nSắp hết hạn\nĐủ hồ sơ mặt hàng",
		"read_only": 1,
	},
	{
		"depends_on": "la_thiet_bi_y_te",
		"fieldname": "section_break_tbyt",
		"fieldtype": "Section Break",
		"label": "Bộ chứng từ",
	},
	{
		"depends_on": "la_thiet_bi_y_te",
		"fieldname": "ho_so_tbyt_html",
		"fieldtype": "HTML",
		"label": "Hồ sơ TBYT",
	},
]

with open(PATH, encoding="utf-8") as fh:
	doc = json.load(fh)

existing = {f["fieldname"] for f in doc["fields"]}
if "tbyt_tab" in existing:
	print("da co san")
else:
	doc["fields"].extend(NEW_FIELDS)
	# Đặt ngay trước tab Manufacturing, tức là sau trọn vẹn tab Quality.
	anchor = doc["field_order"].index("manufacturing")
	names = [f["fieldname"] for f in NEW_FIELDS]
	doc["field_order"][anchor:anchor] = names
	with open(PATH, "w", encoding="utf-8") as fh:
		json.dump(doc, fh, indent=1, ensure_ascii=False, sort_keys=True)
		fh.write("\n")
	print("da them tab TBYT:", names)
```

- [ ] **Step 5: Viết hook đặt mặc định cờ TBYT**

Tạo `erpnext/tbyt/item_hooks.py`:

```python
# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Móc nối hồ sơ TBYT vào Item.

Để ở module `tbyt` chứ không nhồi vào `item.py`: logic TBYT thay đổi theo thông
tư, còn `item.py` là controller dùng chung — trộn vào nhau thì mỗi lần Bộ Y tế
sửa quy định lại phải mở một file 1000 dòng của core.
"""

import frappe
from frappe import _
from frappe.utils import cint


def require_authorization_for_medical_item(doc, method=None):
	"""Số lưu hành là ràng buộc CỨNG duy nhất của cả tính năng — chặn thật.

	`mandatory_depends_on` trên trường chỉ chặn ở trình duyệt: không chỗ nào trong
	`frappe/model/` đọc nó. ERPNext core cũng không tin nó — `Item.asset_category`
	có `mandatory_depends_on`, nhưng `item.py` vẫn viết riêng một kiểm tra server.
	Thiếu hàm này thì mọi đường ghi không qua form đều lọt.
	"""
	if not cint(doc.get("la_thiet_bi_y_te")):
		return
	if doc.get("so_luu_hanh"):
		return
	frappe.throw(
		_("Mặt hàng là thiết bị y tế thì bắt buộc phải có Số lưu hành."),
		frappe.MandatoryError,
	)


def set_default_medical_flag(doc, method=None):
	"""Chỉ áp mặc định lúc TẠO MỚI, và chỉ khi người dùng chưa tự khai.

	Cố ý không dùng `fetch_from` + `fetch_if_empty`: với trường Check thì "rỗng"
	chính là 0, nên người dùng bỏ tích sẽ bị nhóm hàng ghi đè lại mỗi lần lưu.
	"""
	if doc.get("la_thiet_bi_y_te"):
		return
	if not doc.item_group:
		return
	doc.la_thiet_bi_y_te = cint(frappe.db.get_value("Item Group", doc.item_group, "la_tbyt"))
```

- [ ] **Step 6: Nối vào `hooks.py`**

Trong `erpnext/hooks.py`, tìm `doc_events = {` (khoảng dòng 333) và thêm khóa `"Item"` vào ngay sau dấu mở ngoặc:

```python
	"Item": {
		"before_insert": "erpnext.tbyt.item_hooks.set_default_medical_flag",
		"validate": "erpnext.tbyt.item_hooks.require_authorization_for_medical_item",
	},
```

- [ ] **Step 7: Migrate và chạy test**

```bash
cd /home/miyano/frappe-bench && bench --site miyano migrate && bench --site miyano run-tests --module erpnext.tbyt.tests.test_item_fields
```

Kỳ vọng: PASS, 7 test.

- [ ] **Step 8: Commit**

```bash
cd /home/miyano/frappe-bench/apps/erpnext
~/.local/bin/pre-commit run --files erpnext/tbyt/item_hooks.py erpnext/tbyt/tests/test_item_fields.py erpnext/hooks.py erpnext/stock/doctype/item/item.json erpnext/setup/doctype/item_group/item_group.json
git add erpnext/stock/doctype/item/item.json erpnext/setup/doctype/item_group/item_group.json erpnext/tbyt/item_hooks.py erpnext/tbyt/tests/test_item_fields.py erpnext/hooks.py
git commit -m "feat(tbyt): tab ho so TBYT tren Item, so luu hanh bat buoc cho hang y te"
```

---

### Task 8: `resolver.py` — phân giải bộ chứng từ của một Item

**Files:**
- Create: `erpnext/tbyt/resolver.py`
- Create: `erpnext/tbyt/tests/test_resolver.py`

**Interfaces:**
- Consumes: Item fields (Task 7), `TBYT Document Type` (Task 2), `TBYT Regulatory Document` (Task 5), `get_condition_context` (Task 4)
- Produces:
  - `erpnext.tbyt.resolver.get_item_documents(item_code: str) -> list[dict]` — mỗi phần tử có khóa: `document_key`, `document_name`, `short_code`, `scope_level`, `level`, `is_required`, `is_supplementary`, `document` (tên bản ghi hoặc `None`), `so_hieu`, `ngay_cap`, `ngay_het_han`, `khong_thoi_han`, `trang_thai`, `file`
  - `erpnext.tbyt.resolver.get_scope_values(item_code) -> dict[str, str | None]`
  - `erpnext.tbyt.resolver.find_items_for_scope(scope_doctype, scope_name) -> list[str]`

- [ ] **Step 1: Viết test thất bại**

Tạo `erpnext/tbyt/tests/test_resolver.py`:

```python
# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Phân giải ngược chuỗi Item → Số lưu hành → Chủ sở hữu → Công ty.

Không sao chép dòng nào: một tờ giấy nằm ở đúng cấp của nó, và mọi Item dưới
cấp đó tự thừa hưởng. Ca then chốt là `test_second_item_inherits_...`: thêm
mặt hàng thứ hai vào cùng số lưu hành thì số bản ghi chứng từ KHÔNG tăng.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.tbyt import constants
from erpnext.tbyt.doctype.tbyt_marketing_authorization.test_tbyt_marketing_authorization import (
	make_authorization,
)
from erpnext.tbyt.resolver import find_items_for_scope, get_item_documents
from erpnext.tbyt.tests.test_expiry import make_regulatory_document
from erpnext.tbyt.tests.test_item_fields import make_item

AUTH_DOCTYPE = "TBYT Marketing Authorization"


def levels_by_key(rows):
	return {row["document_key"]: row["level"] for row in rows}


def required_missing(rows):
	return {row["document_key"] for row in rows if row["is_required"] and not row["document"]}


class TestResolver(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		from erpnext.tbyt.setup import setup_tbyt_masters

		setup_tbyt_masters()

	def setUp(self):
		self.suffix = frappe.generate_hash(length=6)

	def _item_of_class(self, device_class, **auth_kwargs):
		auth = make_authorization(
			so_luu_hanh=f"_TEST-SLH-RES-{device_class}-{self.suffix}",
			phan_loai=device_class,
			**auth_kwargs,
		)
		item = make_item(
			f"_TEST-TBYT-RES-{device_class}-{self.suffix}", so_luu_hanh=auth.name
		)
		return item, auth

	def test_class_a_excludes_registration_certificate(self):
		"""Loại A dùng số công bố, không có giấy đăng ký lưu hành."""
		item, _ = self._item_of_class("A")
		keys = levels_by_key(get_item_documents(item.name))
		self.assertIn("so_cong_bo_tieu_chuan", keys)
		self.assertNotIn("gcn_dang_ky_luu_hanh", keys)

	def test_class_c_excludes_standard_declaration(self):
		item, _ = self._item_of_class("C")
		keys = levels_by_key(get_item_documents(item.name))
		self.assertIn("gcn_dang_ky_luu_hanh", keys)
		self.assertNotIn("so_cong_bo_tieu_chuan", keys)

	def test_class_a_excludes_the_trading_eligibility_notice(self):
		item, _ = self._item_of_class("A")
		self.assertNotIn("cong_bo_dk_mua_ban", levels_by_key(get_item_documents(item.name)))

	def test_class_b_includes_the_trading_eligibility_notice(self):
		item, _ = self._item_of_class("B")
		self.assertIn("cong_bo_dk_mua_ban", levels_by_key(get_item_documents(item.name)))

	def test_hop_chuan_hop_quy_appears_for_ab_but_not_for_cd(self):
		"""Bẫy lật mức: NC ở A/B nên hiện, TH ở C/D nên ẩn khi chưa có bản ghi."""
		item_b, _ = self._item_of_class("B")
		item_d, _ = self._item_of_class("D")
		self.assertIn("hop_chuan_hop_quy", levels_by_key(get_item_documents(item_b.name)))
		self.assertNotIn("hop_chuan_hop_quy", levels_by_key(get_item_documents(item_d.name)))

	def test_batch_level_documents_are_not_resolved_at_item_level(self):
		item, _ = self._item_of_class("B")
		keys = levels_by_key(get_item_documents(item.name))
		for key in ("cq_chung_nhan_chat_luong", "co_chung_nhan_xuat_xu"):
			self.assertNotIn(key, keys)

	def test_transaction_level_documents_are_out_of_scope(self):
		item, _ = self._item_of_class("B")
		self.assertNotIn("ho_so_phan_phoi", levels_by_key(get_item_documents(item.name)))

	def test_bb_star_is_required_when_miyano_is_not_the_owner(self):
		item, _ = self._item_of_class("B", miyano_la_chu_so_huu=0, hang_nhap_khau=1)
		self.assertIn("giay_uy_quyen_csh", required_missing(get_item_documents(item.name)))

	def test_bb_star_is_not_required_when_miyano_owns_the_authorization(self):
		item, _ = self._item_of_class("B", miyano_la_chu_so_huu=1, hang_nhap_khau=0)
		self.assertNotIn("giay_uy_quyen_csh", required_missing(get_item_documents(item.name)))

	def test_cfs_needs_both_switches(self):
		"""Hàng sản xuất trong nước không có CFS, dù Miyano không phải chủ sở hữu."""
		domestic, _ = self._item_of_class("A", miyano_la_chu_so_huu=0, hang_nhap_khau=0)
		self.assertNotIn("cfs_giay_luu_hanh", required_missing(get_item_documents(domestic.name)))

	def test_th_document_is_hidden_when_absent(self):
		item, _ = self._item_of_class("B")
		self.assertNotIn("ke_khai_gia", levels_by_key(get_item_documents(item.name)))

	def test_th_document_shows_up_once_uploaded(self):
		"""Tải lên rồi thì phải thấy và phải theo dõi hạn — không được nuốt mất."""
		item, _ = self._item_of_class("B")
		make_regulatory_document("ke_khai_gia", "Item", item.name)
		rows = {r["document_key"]: r for r in get_item_documents(item.name)}
		self.assertIn("ke_khai_gia", rows)
		self.assertTrue(rows["ke_khai_gia"]["is_supplementary"])
		self.assertFalse(rows["ke_khai_gia"]["is_required"])

	def test_authorization_level_document_is_found(self):
		item, auth = self._item_of_class("B")
		doc = make_regulatory_document("hdsd_tieng_viet", AUTH_DOCTYPE, auth.name)
		rows = {r["document_key"]: r for r in get_item_documents(item.name)}
		self.assertEqual(rows["hdsd_tieng_viet"]["document"], doc.name)

	def test_owner_level_document_is_found(self):
		item, auth = self._item_of_class("B")
		doc = make_regulatory_document("thong_tin_bao_hanh", "Manufacturer", auth.chu_so_huu)
		rows = {r["document_key"]: r for r in get_item_documents(item.name)}
		self.assertEqual(rows["thong_tin_bao_hanh"]["document"], doc.name)

	def test_inactive_document_does_not_count(self):
		item, auth = self._item_of_class("B")
		doc = make_regulatory_document("hdsd_tieng_viet", AUTH_DOCTYPE, auth.name)
		doc.is_active = 0
		doc.save(ignore_permissions=True)
		self.assertIn("hdsd_tieng_viet", required_missing(get_item_documents(item.name)))

	def test_second_item_inherits_without_creating_any_new_record(self):
		"""Ca then chốt của toàn bộ thiết kế: thừa hưởng chứ không nhân bản."""
		item, auth = self._item_of_class("C")
		make_regulatory_document("hdsd_tieng_viet", AUTH_DOCTYPE, auth.name)
		before = frappe.db.count("TBYT Regulatory Document")

		sibling = make_item(f"_TEST-TBYT-SIBLING-{self.suffix}", so_luu_hanh=auth.name)
		rows = {r["document_key"]: r for r in get_item_documents(sibling.name)}

		self.assertTrue(rows["hdsd_tieng_viet"]["document"])
		self.assertEqual(frappe.db.count("TBYT Regulatory Document"), before)

	def test_one_cfs_covers_every_authorization_it_lists(self):
		item_a, auth_a = self._item_of_class("C", miyano_la_chu_so_huu=0, hang_nhap_khau=1)
		auth_b = make_authorization(
			so_luu_hanh=f"_TEST-SLH-RES-COVER-{self.suffix}",
			phan_loai="C",
			chu_so_huu=auth_a.chu_so_huu,
			miyano_la_chu_so_huu=0,
			hang_nhap_khau=1,
		)
		item_b = make_item(f"_TEST-TBYT-COVER-{self.suffix}", so_luu_hanh=auth_b.name)

		cfs = frappe.new_doc("TBYT Regulatory Document")
		cfs.document_type = "cfs_giay_luu_hanh"
		cfs.append("pham_vi", {"scope_name": auth_a.name})
		cfs.append("pham_vi", {"scope_name": auth_b.name})
		cfs.so_hieu = "_TEST-CFS-COVER"
		cfs.ngay_cap = "2026-01-01"
		cfs.khong_thoi_han = 1
		cfs.file = "/private/files/_test_tbyt.pdf"
		cfs.insert(ignore_permissions=True)

		for item in (item_a, item_b):
			rows = {r["document_key"]: r for r in get_item_documents(item.name)}
			self.assertEqual(rows["cfs_giay_luu_hanh"]["document"], cfs.name, item.name)

	def test_non_medical_item_resolves_to_nothing(self):
		from erpnext.tbyt.tests.test_item_fields import make_item_group

		group = make_item_group("_Test Nhom Thuong", la_tbyt=0)
		item = make_item(f"_TEST-TBYT-NONMED-{self.suffix}", item_group=group)
		self.assertEqual(get_item_documents(item.name), [])

	def test_find_items_for_scope_walks_back_from_an_authorization(self):
		item, auth = self._item_of_class("B")
		self.assertIn(item.name, find_items_for_scope(AUTH_DOCTYPE, auth.name))

	def test_find_items_for_scope_walks_back_from_an_owner(self):
		item, auth = self._item_of_class("B")
		self.assertIn(item.name, find_items_for_scope("Manufacturer", auth.chu_so_huu))
```

- [ ] **Step 2: Chạy test để xác nhận nó đỏ**

```bash
cd /home/miyano/frappe-bench && bench --site miyano run-tests --module erpnext.tbyt.tests.test_resolver
```

Kỳ vọng: FAIL — `ModuleNotFoundError: No module named 'erpnext.tbyt.resolver'`.

- [ ] **Step 3: Viết resolver**

Tạo `erpnext/tbyt/resolver.py`:

```python
# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Phân giải bộ chứng từ pháp lý của một Item.

Nguyên tắc: KHÔNG sao chép. Một tờ giấy nằm ở đúng cấp của nó — công ty, chủ sở
hữu, số lưu hành, hay chính mặt hàng — và Item đi ngược chuỗi để nhặt về. Nhờ
vậy gia hạn một tờ CFS là sửa một bản ghi, không phải sửa từng SKU.
"""

import frappe
from frappe.utils import cint

from erpnext.tbyt.constants import (
	LEVEL_BB,
	LEVEL_BB_STAR,
	LEVEL_NA,
	LEVEL_TH,
	SCOPE_AUTHORIZATION,
	SCOPE_COMPANY,
	SCOPE_DOCTYPE,
	SCOPE_ITEM,
	SCOPE_OWNER,
)
from erpnext.tbyt.doctype.tbyt_marketing_authorization.tbyt_marketing_authorization import (
	get_condition_context,
)

# Bốn cấp mà một Item phân giải được. Cấp Lô kiểm ở Batch (item chưa có lô thì
# không có gì để thiếu); cấp Giao dịch dùng đính kèm sẵn có của chứng từ bán hàng.
ITEM_SCOPES = (SCOPE_COMPANY, SCOPE_OWNER, SCOPE_AUTHORIZATION, SCOPE_ITEM)


def get_item_documents(item_code: str) -> list[dict]:
	"""Trả về bộ chứng từ đã phân giải của một Item.

	Danh sách rỗng nếu mặt hàng không phải TBYT hoặc chưa gắn số lưu hành.
	"""
	item = frappe.db.get_value(
		"Item", item_code, ["name", "la_thiet_bi_y_te", "so_luu_hanh"], as_dict=True
	)
	if not item or not cint(item.la_thiet_bi_y_te) or not item.so_luu_hanh:
		return []

	auth = frappe.db.get_value(
		"TBYT Marketing Authorization",
		item.so_luu_hanh,
		["name", "phan_loai", "chu_so_huu"],
		as_dict=True,
	)
	if not auth or not auth.phan_loai:
		return []

	context = get_condition_context(auth.name)
	scope_values = get_scope_values(item_code)

	rows = []
	for doc_type in _document_types():
		if doc_type.scope_level not in ITEM_SCOPES:
			continue

		level, condition = _rule_for(doc_type.name, auth.phan_loai)
		if not level or level == LEVEL_NA:
			continue

		record = _find_document(
			doc_type.name,
			SCOPE_DOCTYPE[doc_type.scope_level],
			scope_values.get(doc_type.scope_level),
		)

		# TH không bao giờ tính là thiếu, nhưng đã tải lên thì phải hiện ra và
		# phải được theo dõi hạn — nếu ẩn đi thì tải lên coi như mất.
		if level == LEVEL_TH and not record:
			continue

		rows.append(
			{
				"document_key": doc_type.name,
				"document_name": doc_type.document_name,
				"short_code": doc_type.short_code,
				"scope_level": doc_type.scope_level,
				"level": level,
				"is_required": _is_required(level, condition, context),
				"is_supplementary": level == LEVEL_TH,
				"document": record.name if record else None,
				"so_hieu": record.so_hieu if record else None,
				"ngay_cap": record.ngay_cap if record else None,
				"ngay_het_han": record.ngay_het_han if record else None,
				"khong_thoi_han": cint(record.khong_thoi_han) if record else 0,
				"trang_thai": record.trang_thai if record else None,
				"file": record.file if record else None,
			}
		)
	return rows


def get_scope_values(item_code: str) -> dict:
	"""Đối tượng cụ thể của Item ở từng cấp phạm vi."""
	import erpnext

	item = frappe.db.get_value("Item", item_code, ["name", "so_luu_hanh"], as_dict=True)
	if not item:
		return {}

	owner = None
	if item.so_luu_hanh:
		owner = frappe.db.get_value("TBYT Marketing Authorization", item.so_luu_hanh, "chu_so_huu")

	return {
		SCOPE_COMPANY: erpnext.get_default_company(),
		SCOPE_OWNER: owner,
		SCOPE_AUTHORIZATION: item.so_luu_hanh,
		SCOPE_ITEM: item.name,
	}


def find_items_for_scope(scope_doctype: str, scope_name: str) -> list[str]:
	"""Những Item bị ảnh hưởng khi một chứng từ ở phạm vi này thay đổi.

	Dùng cho việc làm mới trạng thái (Task 11) — một tờ giấy cấp chủ sở hữu có
	thể chạm rất nhiều mặt hàng.
	"""
	if scope_doctype == "Item":
		return [scope_name]

	if scope_doctype == "TBYT Marketing Authorization":
		return frappe.get_all(
			"Item", filters={"so_luu_hanh": scope_name, "la_thiet_bi_y_te": 1}, pluck="name"
		)

	if scope_doctype == "Manufacturer":
		auths = frappe.get_all(
			"TBYT Marketing Authorization", filters={"chu_so_huu": scope_name}, pluck="name"
		)
		if not auths:
			return []
		return frappe.get_all(
			"Item",
			filters={"so_luu_hanh": ("in", auths), "la_thiet_bi_y_te": 1},
			pluck="name",
		)

	if scope_doctype == "Company":
		return frappe.get_all("Item", filters={"la_thiet_bi_y_te": 1}, pluck="name")

	return []


def _document_types():
	return frappe.get_all(
		"TBYT Document Type",
		fields=["name", "document_name", "short_code", "scope_level"],
		order_by="name",
	)


def _rule_for(document_key: str, device_class: str):
	row = frappe.db.get_value(
		"TBYT Document Rule",
		{
			"parent": document_key,
			"parenttype": "TBYT Document Type",
			"device_class": device_class,
		},
		["level", "condition"],
		as_dict=True,
	)
	if not row:
		return None, None
	return row.level, row.condition


def _is_required(level: str, condition: str | None, context: dict) -> bool:
	if level == LEVEL_BB:
		return True
	if level != LEVEL_BB_STAR:
		return False
	if not condition:
		return True
	return bool(frappe.safe_eval(condition, None, dict(context)))


def _find_document(document_key: str, scope_doctype: str, scope_name: str | None):
	"""Bản ghi còn hiệu lực của loại này phủ đúng đối tượng này.

	Chặn trùng ở Task 6 bảo đảm nhiều nhất một bản ghi khớp, nên `limit 1` là
	tất định chứ không phải chọn bừa.
	"""
	if not scope_name:
		return None

	rows = frappe.db.sql(
		"""
		select rd.name, rd.so_hieu, rd.ngay_cap, rd.ngay_het_han,
			rd.khong_thoi_han, rd.trang_thai, rd.file
		from `tabTBYT Regulatory Document` rd
		inner join `tabTBYT Document Scope` sc on sc.parent = rd.name
		where rd.document_type = %(document_type)s
			and rd.is_active = 1
			and sc.parenttype = 'TBYT Regulatory Document'
			and sc.scope_doctype = %(scope_doctype)s
			and sc.scope_name = %(scope_name)s
		limit 1
		""",
		{
			"document_type": document_key,
			"scope_doctype": scope_doctype,
			"scope_name": scope_name,
		},
		as_dict=True,
	)
	return rows[0] if rows else None
```

- [ ] **Step 4: Chạy test để xác nhận nó xanh**

```bash
cd /home/miyano/frappe-bench && bench --site miyano run-tests --module erpnext.tbyt.tests.test_resolver
```

Kỳ vọng: PASS, 20 test.

- [ ] **Step 5: Commit**

```bash
cd /home/miyano/frappe-bench/apps/erpnext
~/.local/bin/pre-commit run --files erpnext/tbyt/resolver.py erpnext/tbyt/tests/test_resolver.py
git add erpnext/tbyt/resolver.py erpnext/tbyt/tests/test_resolver.py
git commit -m "feat(tbyt): resolver phan giai bo chung tu theo chuoi, khong sao chep"
```

---

### Task 9: Trạng thái hồ sơ và cảnh báo trên Item

**Files:**
- Create: `erpnext/tbyt/status.py`
- Modify: `erpnext/tbyt/resolver.py` — thêm tham số tùy chọn `item` cho `get_item_documents` và `get_scope_values`
- Modify: `erpnext/tbyt/item_hooks.py` — thêm `warn_about_missing_documents`
- Modify: `erpnext/hooks.py` — thêm `validate` vào `doc_events["Item"]`
- Modify: `erpnext/stock/doctype/item/item.js` — dựng bảng hồ sơ
- Create: `erpnext/tbyt/tests/test_status.py`

**Interfaces:**
- Consumes: `get_item_documents` (Task 8), Item fields (Task 7)
- Produces:
  - `erpnext.tbyt.resolver.get_item_documents(item_code, item=None)` — `item` là dict có `name`, `la_thiet_bi_y_te`, `so_luu_hanh`; truyền vào để phân giải được bản ghi CHƯA nằm trong DB
  - `erpnext.tbyt.status.get_item_status(item_code, item=None) -> str | None`
  - `erpnext.tbyt.status.update_item_status(item_code) -> str | None`
  - `erpnext.tbyt.status.get_item_dashboard(item_code) -> dict` (whitelisted)
  - `erpnext.tbyt.item_hooks.warn_about_missing_documents(doc, method=None)`

- [ ] **Step 1: Viết test thất bại**

Tạo `erpnext/tbyt/tests/test_status.py`:

```python
# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Trạng thái hồ sơ của Item — sáu giá trị, xếp từ nặng tới nhẹ.

Nhãn cuối cố ý là "Đủ hồ sơ mặt hàng" chứ KHÔNG phải "Đủ": chứng từ cấp lô
(CQ, CO — đều là BB ở cả bốn phân loại) không tính ở cấp Item, nên nói "Đủ" là
nói dối. Trạng thái cấp lô xem ở Batch và trong báo cáo.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from erpnext.tbyt import constants
from erpnext.tbyt.doctype.tbyt_marketing_authorization.test_tbyt_marketing_authorization import (
	make_authorization,
)
import erpnext
from erpnext.tbyt.status import get_item_status, update_item_status
from erpnext.tbyt.tests.test_expiry import make_regulatory_document
from erpnext.tbyt.tests.test_item_fields import make_item, make_item_group

AUTH_DOCTYPE = "TBYT Marketing Authorization"


class TestItemStatus(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		from erpnext.tbyt.setup import setup_tbyt_masters

		setup_tbyt_masters()

	def setUp(self):
		self.suffix = frappe.generate_hash(length=6)

	def _make(self, device_class="A", **auth_kwargs):
		auth = make_authorization(
			so_luu_hanh=f"_TEST-SLH-ST-{self.suffix}", phan_loai=device_class, **auth_kwargs
		)
		item = make_item(f"_TEST-TBYT-ST-{self.suffix}", so_luu_hanh=auth.name)
		return item, auth

	def _upload_everything_required(self, item, auth):
		from erpnext.tbyt.resolver import get_item_documents

		for row in get_item_documents(item.name):
			if not row["is_required"] or row["document"]:
				continue
			scope_map = {
				constants.SCOPE_COMPANY: ("Company", erpnext.get_default_company()),
				constants.SCOPE_OWNER: ("Manufacturer", auth.chu_so_huu),
				constants.SCOPE_AUTHORIZATION: (AUTH_DOCTYPE, auth.name),
				constants.SCOPE_ITEM: ("Item", item.name),
			}
			scope_doctype, scope_name = scope_map[row["scope_level"]]
			make_regulatory_document(row["document_key"], scope_doctype, scope_name)

	def test_non_medical_item_has_no_status(self):
		group = make_item_group("_Test Nhom Thuong", la_tbyt=0)
		item = make_item(f"_TEST-TBYT-ST-NONMED-{self.suffix}", item_group=group)
		self.assertIsNone(get_item_status(item.name))

	def test_pending_authorization_outranks_missing_documents(self):
		item, _ = self._make()
		frappe.db.set_value(
			AUTH_DOCTYPE, item.so_luu_hanh, "trang_thai", constants.AUTH_STATUS_PENDING
		)
		self.assertEqual(get_item_status(item.name), constants.ITEM_STATUS_AUTH_PENDING)

	def test_lapsed_authorization_outranks_everything(self):
		"""Số lưu hành hết hiệu lực là sự kiện tuân thủ nặng nhất — phải hiện lên trước."""
		item, auth = self._make()
		self._upload_everything_required(item, auth)
		frappe.db.set_value(
			AUTH_DOCTYPE, auth.name, "trang_thai", constants.AUTH_STATUS_REVOKED
		)
		self.assertEqual(get_item_status(item.name), constants.ITEM_STATUS_AUTH_INVALID)

	def test_missing_required_document_is_reported(self):
		item, _ = self._make()
		self.assertEqual(get_item_status(item.name), constants.ITEM_STATUS_MISSING)

	def test_expired_document_outranks_missing(self):
		item, auth = self._make()
		make_regulatory_document(
			"hdsd_tieng_viet",
			AUTH_DOCTYPE,
			auth.name,
			khong_thoi_han=0,
			ngay_het_han=add_days(today(), -1),
		)
		self.assertEqual(get_item_status(item.name), constants.ITEM_STATUS_EXPIRED)

	def test_complete_dossier_reports_item_level_completeness(self):
		item, auth = self._make()
		self._upload_everything_required(item, auth)
		self.assertEqual(get_item_status(item.name), constants.ITEM_STATUS_OK)

	def test_expiring_document_is_reported_once_nothing_is_missing(self):
		item, auth = self._make()
		self._upload_everything_required(item, auth)
		doc_name = frappe.db.get_value(
			"TBYT Regulatory Document", {"document_type": "hdsd_tieng_viet"}, "name"
		)
		doc = frappe.get_doc("TBYT Regulatory Document", doc_name)
		doc.khong_thoi_han = 0
		doc.ngay_het_han = add_days(today(), constants.EXPIRY_WARNING_DAYS - 5)
		doc.save(ignore_permissions=True)
		self.assertEqual(get_item_status(item.name), constants.ITEM_STATUS_EXPIRING)

	def test_update_item_status_persists_without_bumping_modified(self):
		item, _ = self._make()
		before = frappe.db.get_value("Item", item.name, "modified")
		update_item_status(item.name)
		after = frappe.db.get_value("Item", item.name, "modified")
		self.assertEqual(
			frappe.db.get_value("Item", item.name, "tinh_trang_ho_so"),
			constants.ITEM_STATUS_MISSING,
		)
		self.assertEqual(before, after)

	def test_saving_a_medical_item_warns_but_does_not_block(self):
		"""Cảnh báo, không chặn — chứng từ về dần theo tiến độ nhà cung cấp gửi."""
		item, _ = self._make()
		item.item_name = "Doi ten de luu lai"
		item.save(ignore_permissions=True)
		messages = frappe.get_message_log()
		self.assertTrue(
			any("chứng từ" in str(m).lower() for m in messages),
			"Phải có cảnh báo thiếu chứng từ trong message log",
		)
```

- [ ] **Step 2: Chạy test để xác nhận nó đỏ**

```bash
cd /home/miyano/frappe-bench && bench --site miyano run-tests --module erpnext.tbyt.tests.test_status
```

Kỳ vọng: FAIL — `ModuleNotFoundError: No module named 'erpnext.tbyt.status'`.

- [ ] **Step 3: Cho resolver nhận Item chưa có trong DB**

Trong `erpnext/tbyt/resolver.py`, đổi hai chữ ký và dòng đọc DB đầu tiên của mỗi hàm:

```python
def get_item_documents(item_code: str, item: dict | None = None) -> list[dict]:
	"""Trả về bộ chứng từ đã phân giải của một Item.

	`item` cho phép truyền vào bản ghi chưa nằm trong DB — cần khi `validate`
	chạy lúc tạo mới, vì lúc đó chưa có dòng nào để đọc.
	"""
	if item is None:
		item = frappe.db.get_value(
			"Item", item_code, ["name", "la_thiet_bi_y_te", "so_luu_hanh"], as_dict=True
		)
	if not item or not cint(item.get("la_thiet_bi_y_te")) or not item.get("so_luu_hanh"):
		return []

	auth = frappe.db.get_value(
		"TBYT Marketing Authorization",
		item["so_luu_hanh"],
		["name", "phan_loai", "chu_so_huu"],
		as_dict=True,
	)
	if not auth or not auth.phan_loai:
		return []

	context = get_condition_context(auth.name)
	scope_values = get_scope_values(item_code, item=item)
	# ... phần còn lại giữ nguyên
```

```python
def get_scope_values(item_code: str, item: dict | None = None) -> dict:
	"""Đối tượng cụ thể của Item ở từng cấp phạm vi."""
	import erpnext

	if item is None:
		item = frappe.db.get_value("Item", item_code, ["name", "so_luu_hanh"], as_dict=True)
	if not item:
		return {}

	owner = None
	if item.get("so_luu_hanh"):
		owner = frappe.db.get_value(
			"TBYT Marketing Authorization", item["so_luu_hanh"], "chu_so_huu"
		)

	return {
		SCOPE_COMPANY: erpnext.get_default_company(),
		SCOPE_OWNER: owner,
		SCOPE_AUTHORIZATION: item.get("so_luu_hanh"),
		SCOPE_ITEM: item.get("name") or item_code,
	}
```

Trong thân `get_item_documents`, đổi `auth.phan_loai` vẫn giữ nguyên, còn `item.name` ở phần dựng `rows` không dùng tới — không phải sửa gì thêm.

- [ ] **Step 4: Viết module trạng thái**

Tạo `erpnext/tbyt/status.py`:

```python
# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Trạng thái hồ sơ pháp lý của một Item và bảng hiển thị trên form.

Thứ tự ưu tiên là hợp đồng của module này: nặng nhất trước. Số lưu hành hết
hiệu lực đè mọi thứ khác vì đó là sự kiện tuân thủ nặng nhất — hàng không còn
cơ sở pháp lý để lưu thông, dù hồ sơ giấy tờ có đủ tới đâu.
"""

import frappe
from frappe.utils import cint

from erpnext.tbyt.constants import (
	AUTH_STATUS_EXPIRED,
	AUTH_STATUS_PENDING,
	AUTH_STATUS_REVOKED,
	DOC_STATUS_EXPIRED,
	DOC_STATUS_EXPIRING,
	ITEM_STATUS_AUTH_INVALID,
	ITEM_STATUS_AUTH_PENDING,
	ITEM_STATUS_EXPIRED,
	ITEM_STATUS_EXPIRING,
	ITEM_STATUS_MISSING,
	ITEM_STATUS_OK,
)
from erpnext.tbyt.resolver import get_item_documents


def get_item_status(item_code: str, item: dict | None = None) -> str | None:
	"""Trả về một giá trị ITEM_STATUS_*, hoặc None nếu không phải hàng y tế."""
	if item is None:
		item = frappe.db.get_value(
			"Item", item_code, ["name", "la_thiet_bi_y_te", "so_luu_hanh"], as_dict=True
		)
	if not item or not cint(item.get("la_thiet_bi_y_te")):
		return None

	if not item.get("so_luu_hanh"):
		return ITEM_STATUS_AUTH_PENDING

	auth_status = frappe.db.get_value(
		"TBYT Marketing Authorization", item["so_luu_hanh"], "trang_thai"
	)
	if auth_status in (AUTH_STATUS_EXPIRED, AUTH_STATUS_REVOKED):
		return ITEM_STATUS_AUTH_INVALID
	if auth_status == AUTH_STATUS_PENDING:
		return ITEM_STATUS_AUTH_PENDING

	rows = get_item_documents(item_code, item=item)

	# Chỉ chứng từ ĐANG bắt buộc mới quyết định trạng thái. BB* không thỏa điều
	# kiện thì không phải nghĩa vụ của Miyano, hết hạn cũng không đổi kết luận.
	if any(r["trang_thai"] == DOC_STATUS_EXPIRED for r in rows if r["is_required"] and r["document"]):
		return ITEM_STATUS_EXPIRED
	if any(r["is_required"] and not r["document"] for r in rows):
		return ITEM_STATUS_MISSING
	if any(r["trang_thai"] == DOC_STATUS_EXPIRING for r in rows if r["is_required"] and r["document"]):
		return ITEM_STATUS_EXPIRING
	return ITEM_STATUS_OK


def update_item_status(item_code: str) -> str | None:
	"""Ghi trạng thái xuống DB mà không đụng `modified`.

	Không dùng `doc.save()`: trạng thái là giá trị suy ra, không phải người dùng
	sửa — làm bẩn `modified` sẽ phá lịch sử sửa đổi thật của mặt hàng.
	"""
	status = get_item_status(item_code)
	frappe.db.set_value("Item", item_code, "tinh_trang_ho_so", status, update_modified=False)
	return status


@frappe.whitelist()
def get_item_dashboard(item_code: str) -> dict:
	"""Dữ liệu cho bảng hồ sơ trên form Item."""
	frappe.has_permission("Item", doc=item_code, throw=True)
	rows = get_item_documents(item_code)
	return {
		"status": get_item_status(item_code),
		"rows": rows,
		"missing": sum(1 for r in rows if r["is_required"] and not r["document"]),
	}
```

- [ ] **Step 5: Thêm cảnh báo vào `item_hooks.py`**

Nối vào cuối `erpnext/tbyt/item_hooks.py`:

```python
def warn_about_missing_documents(doc, method=None):
	"""Cảnh báo thiếu chứng từ — KHÔNG BAO GIỜ chặn lưu.

	Ràng buộc cứng duy nhất là số lưu hành, và nó đã do
	`mandatory_depends_on` trên chính trường đó lo. Chứng từ thì phụ thuộc nhà
	cung cấp gửi, chặn lưu ở đây sẽ chặn cả việc tạo mã hàng để báo giá.
	"""
	from erpnext.tbyt.constants import (
		AUTH_STATUS_EXPIRED,
		AUTH_STATUS_PENDING,
		AUTH_STATUS_REVOKED,
		DOC_STATUS_EXPIRED,
		LEVEL_BB,
		LEVEL_BB_STAR,
		LEVEL_NC,
	)
	from erpnext.tbyt.resolver import get_item_documents
	from erpnext.tbyt.status import get_item_status

	if not cint(doc.get("la_thiet_bi_y_te")):
		doc.tinh_trang_ho_so = None
		return

	snapshot = {
		"name": doc.name,
		"la_thiet_bi_y_te": doc.la_thiet_bi_y_te,
		"so_luu_hanh": doc.so_luu_hanh,
	}
	doc.tinh_trang_ho_so = get_item_status(doc.name, item=snapshot)

	if not doc.so_luu_hanh:
		return

	auth_status = frappe.db.get_value(
		"TBYT Marketing Authorization", doc.so_luu_hanh, "trang_thai"
	)
	lines = []

	if auth_status in (AUTH_STATUS_EXPIRED, AUTH_STATUS_REVOKED):
		lines.append(
			f"<b style='color:var(--red-600)'>Số lưu hành đang ở trạng thái “{auth_status}”.</b>"
		)
	elif auth_status == AUTH_STATUS_PENDING:
		# Chưa có phân loại chắc chắn thì liệt kê thiếu gì chỉ gây nhiễu.
		frappe.msgprint(
			"Số lưu hành chưa được cấp (đang đăng ký). Hồ sơ chứng từ sẽ kiểm khi có số chính thức.",
			indicator="orange",
			alert=True,
		)
		return

	rows = get_item_documents(doc.name, item=snapshot)
	expired = [r for r in rows if r["is_required"] and r["trang_thai"] == DOC_STATUS_EXPIRED]
	missing_bb = [r for r in rows if not r["document"] and r["level"] == LEVEL_BB]
	missing_star = [
		r for r in rows if not r["document"] and r["level"] == LEVEL_BB_STAR and r["is_required"]
	]
	missing_nc = [r for r in rows if not r["document"] and r["level"] == LEVEL_NC]

	if expired:
		names = ", ".join(r["document_name"] for r in expired)
		lines.append(f"<b style='color:var(--red-600)'>Chứng từ đã hết hạn:</b> {names}")
	if missing_bb:
		names = ", ".join(r["document_name"] for r in missing_bb)
		lines.append(f"<b style='color:var(--red-600)'>Thiếu chứng từ bắt buộc:</b> {names}")
	if missing_star:
		names = ", ".join(r["document_name"] for r in missing_star)
		lines.append(
			f"<b style='color:var(--orange-600)'>Thiếu chứng từ bắt buộc có điều kiện:</b> {names}"
		)
	if missing_nc:
		names = ", ".join(r["document_name"] for r in missing_nc)
		lines.append(f"<span style='color:var(--blue-600)'>Nên bổ sung:</span> {names}")

	# Gộp một hộp thoại duy nhất — bốn msgprint liên tiếp sẽ dội vào mặt người dùng.
	if lines:
		frappe.msgprint(
			"<br>".join(lines),
			title="Hồ sơ pháp lý TBYT chưa đầy đủ",
			indicator="red" if (expired or missing_bb) else "orange",
		)
```

- [ ] **Step 6: Nối `validate` vào `hooks.py`**

Sửa khóa `"Item"` trong `doc_events` (đã thêm ở Task 7) thành:

```python
	"Item": {
		"before_insert": "erpnext.tbyt.item_hooks.set_default_medical_flag",
		"validate": [
			"erpnext.tbyt.item_hooks.require_authorization_for_medical_item",
			"erpnext.tbyt.item_hooks.warn_about_missing_documents",
		],
	},
```

Hai handler, đúng thứ tự đó: ràng buộc cứng chạy trước rồi mới tới cảnh báo. Frappe
chấp nhận danh sách cho một sự kiện `doc_events`.

- [ ] **Step 7: Dựng bảng hồ sơ trên form Item**

Nối vào cuối `erpnext/stock/doctype/item/item.js`, bên trong khối `frappe.ui.form.on("Item", {...})` đã có — thêm hàm `refresh` phụ bằng cách khai một handler riêng ở cuối file:

```javascript
frappe.ui.form.on("Item", {
	refresh(frm) {
		erpnext_render_tbyt_dossier(frm);
	},
	la_thiet_bi_y_te(frm) {
		erpnext_render_tbyt_dossier(frm);
	},
	so_luu_hanh(frm) {
		erpnext_render_tbyt_dossier(frm);
	},
});

function erpnext_render_tbyt_dossier(frm) {
	const wrapper = frm.get_field("ho_so_tbyt_html");
	if (!wrapper) return;
	if (frm.is_new() || !frm.doc.la_thiet_bi_y_te) {
		wrapper.$wrapper.empty();
		return;
	}

	frappe.call({
		method: "erpnext.tbyt.status.get_item_dashboard",
		args: { item_code: frm.doc.name },
		callback(r) {
			if (!r.message) return;
			wrapper.$wrapper.html(erpnext_tbyt_dossier_html(r.message));
		},
	});
}

function erpnext_tbyt_dossier_html(data) {
	if (!data.rows.length) {
		return `<div class="text-muted">${__("Chưa xác định được bộ chứng từ.")}</div>`;
	}

	const level_label = { BB: "Bắt buộc", "BB*": "BB có điều kiện", NC: "Nên có", TH: "Bổ sung" };
	const body = data.rows
		.map((row) => {
			const expiry = row.khong_thoi_han
				? __("Vô thời hạn")
				: row.ngay_het_han
					? frappe.datetime.str_to_user(row.ngay_het_han)
					: "—";
			const state = row.document
				? `<span class="indicator-pill ${row.trang_thai === "Còn hiệu lực" ? "green" : "red"}">${row.trang_thai}</span>`
				: `<span class="indicator-pill ${row.is_required ? "red" : "gray"}">${__("Chưa có")}</span>`;
			const link = row.document
				? `<a href="/app/tbyt-regulatory-document/${encodeURIComponent(row.document)}">${frappe.utils.escape_html(row.so_hieu || row.document)}</a>`
				: "";
			return `<tr>
				<td>${frappe.utils.escape_html(row.document_name)}</td>
				<td>${level_label[row.level] || row.level}</td>
				<td>${row.scope_level}</td>
				<td>${link}</td>
				<td>${expiry}</td>
				<td>${state}</td>
			</tr>`;
		})
		.join("");

	return `
		<div class="mb-2"><b>${__("Tình trạng")}:</b> ${data.status || "—"}
			${data.missing ? `· <span class="text-danger">${__("Thiếu")} ${data.missing}</span>` : ""}</div>
		<table class="table table-bordered table-sm">
			<thead><tr>
				<th>${__("Chứng từ")}</th><th>${__("Mức")}</th><th>${__("Cấp lưu")}</th>
				<th>${__("Số hiệu")}</th><th>${__("Hết hạn")}</th><th>${__("Trạng thái")}</th>
			</tr></thead>
			<tbody>${body}</tbody>
		</table>`;
}
```

- [ ] **Step 8: Build asset, migrate, chạy test**

```bash
cd /home/miyano/frappe-bench && bench build --app erpnext && bench --site miyano migrate
bench --site miyano run-tests --module erpnext.tbyt.tests.test_status
```

Kỳ vọng: PASS, 9 test.

- [ ] **Step 9: Chạy lại suite resolver để chắc chữ ký mới không vỡ gì**

```bash
cd /home/miyano/frappe-bench && bench --site miyano run-tests --module erpnext.tbyt.tests.test_resolver
```

Kỳ vọng: PASS, 20 test.

- [ ] **Step 10: Commit**

```bash
cd /home/miyano/frappe-bench/apps/erpnext
~/.local/bin/pre-commit run --files erpnext/tbyt/status.py erpnext/tbyt/resolver.py erpnext/tbyt/item_hooks.py erpnext/tbyt/tests/test_status.py erpnext/hooks.py erpnext/stock/doctype/item/item.js
git add erpnext/tbyt/status.py erpnext/tbyt/resolver.py erpnext/tbyt/item_hooks.py erpnext/tbyt/tests/test_status.py erpnext/hooks.py erpnext/stock/doctype/item/item.js
git commit -m "feat(tbyt): trang thai ho so va bang chung tu tren form Item"
```

---

### Task 10: `folders.py` — cây thư mục và đặt tên file

**Files:**
- Create: `erpnext/tbyt/folders.py`
- Modify: `erpnext/tbyt/doctype/tbyt_regulatory_document/tbyt_regulatory_document.py` — gọi `place_file` / `archive_file` trong `on_update`
- Create: `erpnext/tbyt/tests/test_folders.py`

**Interfaces:**
- Consumes: `TBYT Regulatory Document` (Task 5, 6), `erpnext.tbyt.constants` (Task 1)
- Produces:
  - `erpnext.tbyt.folders.ensure_folder(scope_level: str, scope_value: str) -> str`
  - `erpnext.tbyt.folders.build_file_name(short_code, so_hieu, ngay_cap, extension) -> str`
  - `erpnext.tbyt.folders.slugify(text: str) -> str`
  - `erpnext.tbyt.folders.place_file(doc) -> None`
  - `erpnext.tbyt.folders.archive_file(doc) -> None`

- [ ] **Step 1: Viết test thất bại**

Tạo `erpnext/tbyt/tests/test_folders.py`:

```python
# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Cây thư mục theo NƠI CẤP GIẤY, phân giải theo NƠI GIẤY PHỦ.

Một file chỉ nằm được ở một thư mục, nên chứng từ đa phạm vi (CFS, ủy quyền…)
về thư mục chủ sở hữu. Thư mục chỉ phục vụ người duyệt tay — việc xác định item
nào có chứng từ nào hoàn toàn do resolver quyết định, không đọc thư mục.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.einvoice.tests.test_fixtures import minimal_pdf_bytes
from erpnext.tbyt import constants
from erpnext.tbyt.doctype.tbyt_marketing_authorization.test_tbyt_marketing_authorization import (
	make_authorization,
)
from erpnext.tbyt.folders import build_file_name, ensure_folder, slugify

AUTH_DOCTYPE = "TBYT Marketing Authorization"


def attach_pdf(file_name="_test_tbyt.pdf"):
	"""Frappe parse PDF để dò JS nhúng, nên byte giả sẽ bị từ chối."""
	doc = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": f"{frappe.generate_hash(length=6)}_{file_name}",
			"content": minimal_pdf_bytes(),
			"is_private": 1,
			"folder": "Home/Attachments",
		}
	)
	doc.insert(ignore_permissions=True)
	return doc


class TestFolderNaming(FrappeTestCase):
	def test_slugify_strips_accents_and_slashes(self):
		self.assertEqual(slugify("220000123/PCBA-HN"), "220000123-PCBA-HN")
		self.assertEqual(slugify("Số hiệu lạ"), "So-hieu-la")

	def test_missing_number_becomes_khong_so(self):
		self.assertEqual(build_file_name("HDSD", None, "2026-02-03", "pdf"), "HDSD__khong-so__2026-02-03.pdf")

	def test_file_name_carries_code_number_and_date(self):
		self.assertEqual(
			build_file_name("CBTC", "220000123/PCBA-HN", "2026-02-03", "pdf"),
			"CBTC__220000123-PCBA-HN__2026-02-03.pdf",
		)


class TestFolderTree(FrappeTestCase):
	def test_root_folder_is_created_once(self):
		first = ensure_folder(constants.SCOPE_OWNER, "_Test TBYT Hang")
		second = ensure_folder(constants.SCOPE_OWNER, "_Test TBYT Hang")
		self.assertEqual(first, second)
		self.assertTrue(first.startswith("Home/TBYT/02-Chu-so-huu/"))

	def test_each_scope_level_has_its_own_numbered_branch(self):
		self.assertTrue(
			ensure_folder(constants.SCOPE_AUTHORIZATION, "_TEST-SLH-FOLDER").startswith(
				"Home/TBYT/03-So-luu-hanh/"
			)
		)
		self.assertTrue(
			ensure_folder(constants.SCOPE_ITEM, "_TEST-ITEM-FOLDER").startswith("Home/TBYT/05-Item/")
		)


class TestFilePlacement(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		from erpnext.tbyt.setup import setup_tbyt_masters

		setup_tbyt_masters()

	def setUp(self):
		self.suffix = frappe.generate_hash(length=6)
		self.auth = make_authorization(so_luu_hanh=f"_TEST-SLH-FLD-{self.suffix}")

	def _make_document(self, document_type, scope_names, **kwargs):
		attachment = attach_pdf()
		doc = frappe.new_doc("TBYT Regulatory Document")
		doc.document_type = document_type
		for scope_name in scope_names:
			doc.append("pham_vi", {"scope_name": scope_name})
		doc.so_hieu = kwargs.get("so_hieu", "SH-001")
		doc.ngay_cap = kwargs.get("ngay_cap", "2026-02-03")
		doc.khong_thoi_han = 1
		doc.file = attachment.file_url
		doc.insert(ignore_permissions=True)
		return doc

	def test_single_scope_file_lands_in_its_own_scope_folder(self):
		doc = self._make_document("hdsd_tieng_viet", [self.auth.name])
		folder = frappe.db.get_value("File", {"file_url": doc.file}, "folder")
		self.assertEqual(folder, f"Home/TBYT/03-So-luu-hanh/{slugify(self.auth.so_luu_hanh)}")

	def test_file_is_renamed_to_the_convention(self):
		doc = self._make_document("hdsd_tieng_viet", [self.auth.name], so_hieu="SH-XYZ")
		name = frappe.db.get_value("File", {"file_url": doc.file}, "file_name")
		self.assertEqual(name, "HDSD__SH-XYZ__2026-02-03.pdf")

	def test_multi_scope_file_lands_in_the_owner_folder(self):
		sibling = make_authorization(
			so_luu_hanh=f"_TEST-SLH-FLD2-{self.suffix}", chu_so_huu=self.auth.chu_so_huu
		)
		doc = self._make_document("cfs_giay_luu_hanh", [self.auth.name, sibling.name])
		folder = frappe.db.get_value("File", {"file_url": doc.file}, "folder")
		self.assertEqual(folder, f"Home/TBYT/02-Chu-so-huu/{slugify(self.auth.chu_so_huu)}")

	def test_superseded_file_moves_to_the_archive_subfolder(self):
		doc = self._make_document("hdsd_tieng_viet", [self.auth.name])
		doc.is_active = 0
		doc.save(ignore_permissions=True)
		folder = frappe.db.get_value("File", {"file_url": doc.file}, "folder")
		self.assertTrue(folder.endswith(f"/{constants.ARCHIVE_FOLDER_NAME}"), folder)

	def test_attachment_is_always_private(self):
		doc = self._make_document("hdsd_tieng_viet", [self.auth.name])
		self.assertEqual(frappe.db.get_value("File", {"file_url": doc.file}, "is_private"), 1)
```

- [ ] **Step 2: Chạy test để xác nhận nó đỏ**

```bash
cd /home/miyano/frappe-bench && bench --site miyano run-tests --module erpnext.tbyt.tests.test_folders
```

Kỳ vọng: FAIL — `ModuleNotFoundError: No module named 'erpnext.tbyt.folders'`.

- [ ] **Step 3: Viết module thư mục**

Tạo `erpnext/tbyt/folders.py`:

```python
# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Xếp file hồ sơ TBYT vào cây thư mục và đặt tên có nghĩa.

Nguyên tắc: **thư mục theo nơi cấp giấy, phân giải theo nơi giấy phủ.** Một file
chỉ nằm được một thư mục, nên chứng từ đa phạm vi về thư mục chủ sở hữu. Thư mục
chỉ để người duyệt tay lần ra; resolver không bao giờ đọc thư mục.
"""

import os
import unicodedata

import frappe
from frappe.core.api.file import create_new_folder
from frappe.utils import cint, getdate

from erpnext.tbyt.constants import (
	ARCHIVE_FOLDER_NAME,
	ROOT_FOLDER,
	SCOPE_AUTHORIZATION,
	SCOPE_FOLDER_NAME,
	SCOPE_OWNER,
)


def slugify(text: str) -> str:
	"""Bỏ dấu tiếng Việt và thay ký tự phá đường dẫn bằng gạch nối."""
	if not text:
		return ""
	text = text.replace("Đ", "D").replace("đ", "d")
	text = unicodedata.normalize("NFKD", text)
	text = "".join(ch for ch in text if not unicodedata.combining(ch))
	out = []
	for ch in text:
		out.append(ch if (ch.isalnum() or ch in "-_.") else "-")
	return "-".join(part for part in "".join(out).split("-") if part)


def build_file_name(short_code: str, so_hieu: str | None, ngay_cap, extension: str) -> str:
	"""`{mã ngắn}__{số hiệu}__{ngày cấp}.{đuôi}` — nhìn tên là biết giấy gì."""
	number = slugify(so_hieu) if so_hieu else "khong-so"
	issued = getdate(ngay_cap).isoformat() if ngay_cap else "khong-ngay"
	return f"{short_code}__{number}__{issued}.{extension}"


def ensure_folder(scope_level: str, scope_value: str) -> str:
	"""Trả đường dẫn thư mục của một đối tượng, tạo nếu chưa có.

	`create_new_folder` của Frappe đã tự idempotent bằng
	`insert(ignore_if_duplicate=True)` nên gọi lại không lỗi.
	"""
	branch = SCOPE_FOLDER_NAME[scope_level]
	create_new_folder("TBYT", "Home")
	create_new_folder(branch, ROOT_FOLDER)
	leaf = slugify(scope_value)
	create_new_folder(leaf, f"{ROOT_FOLDER}/{branch}")
	return f"{ROOT_FOLDER}/{branch}/{leaf}"


def target_folder(doc) -> str:
	"""Thư mục đích của một bản ghi chứng từ.

	Đa phạm vi thì về thư mục chủ sở hữu — cả bốn loại đa phạm vi đều do chủ sở
	hữu cấp, và validate đã bảo đảm chúng không trải quá một hãng.
	"""
	if len(doc.pham_vi) > 1 and doc.pham_vi[0].scope_doctype == "TBYT Marketing Authorization":
		owner = frappe.db.get_value(
			"TBYT Marketing Authorization", doc.pham_vi[0].scope_name, "chu_so_huu"
		)
		return ensure_folder(SCOPE_OWNER, owner)

	row = doc.pham_vi[0]
	scope_level = frappe.db.get_value("TBYT Document Type", doc.document_type, "scope_level")
	label = row.scope_name
	if scope_level == SCOPE_AUTHORIZATION:
		# Ưu tiên số thật cho dễ đọc; chưa có số thì dùng tên bản ghi.
		label = (
			frappe.db.get_value("TBYT Marketing Authorization", row.scope_name, "so_luu_hanh")
			or row.scope_name
		)
	return ensure_folder(scope_level, label)


def place_file(doc) -> None:
	"""Dời file vào đúng thư mục và đổi tên theo quy ước."""
	file_doc = _file_of(doc)
	if not file_doc:
		return

	folder = target_folder(doc)
	if cint(doc.is_active) == 0:
		folder = _archive_of(folder)

	extension = (os.path.splitext(file_doc.file_name)[1] or ".pdf").lstrip(".")
	wanted = build_file_name(doc.short_code, doc.so_hieu, doc.ngay_cap, extension)

	changed = False
	if file_doc.folder != folder:
		file_doc.folder = folder
		changed = True
	if file_doc.file_name != wanted:
		file_doc.file_name = wanted
		changed = True
	if not cint(file_doc.is_private):
		file_doc.is_private = 1
		changed = True

	if changed:
		file_doc.flags.ignore_permissions = True
		file_doc.save()


def archive_file(doc) -> None:
	"""Dời file của bản ghi đã bị thay thế vào `_Luu-tru/`."""
	place_file(doc)


def _archive_of(folder: str) -> str:
	create_new_folder(ARCHIVE_FOLDER_NAME, folder)
	return f"{folder}/{ARCHIVE_FOLDER_NAME}"


def _file_of(doc):
	if not doc.file:
		return None
	name = frappe.db.get_value("File", {"file_url": doc.file}, "name")
	return frappe.get_doc("File", name) if name else None
```

- [ ] **Step 4: Gọi từ controller**

Trong `erpnext/tbyt/doctype/tbyt_regulatory_document/tbyt_regulatory_document.py`, sửa `on_update` thành:

```python
	def on_update(self):
		self._supersede_previous()
		place_file(self)
```

và thêm import ở đầu file:

```python
from erpnext.tbyt.folders import place_file
```

- [ ] **Step 5: Chạy test để xác nhận nó xanh**

```bash
cd /home/miyano/frappe-bench && bench --site miyano run-tests --module erpnext.tbyt.tests.test_folders
```

Kỳ vọng: PASS, 10 test.

- [ ] **Step 6: Commit**

```bash
cd /home/miyano/frappe-bench/apps/erpnext
~/.local/bin/pre-commit run --files erpnext/tbyt/folders.py erpnext/tbyt/tests/test_folders.py erpnext/tbyt/doctype/tbyt_regulatory_document/tbyt_regulatory_document.py
git add erpnext/tbyt/folders.py erpnext/tbyt/tests/test_folders.py erpnext/tbyt/doctype/tbyt_regulatory_document
git commit -m "feat(tbyt): cay thu muc va quy uoc dat ten file ho so"
```

---

### Task 11: Làm mới trạng thái ngay khi chứng từ thay đổi

**Files:**
- Create: `erpnext/tbyt/refresh.py`
- Modify: `erpnext/tbyt/doctype/tbyt_regulatory_document/tbyt_regulatory_document.py` — gọi refresh trong `on_update`, thêm `on_trash`
- Modify: `erpnext/tbyt/doctype/tbyt_marketing_authorization/tbyt_marketing_authorization.py` — thêm `on_update`
- Create: `erpnext/tbyt/tests/test_refresh.py`

**Interfaces:**
- Consumes: `find_items_for_scope` (Task 8), `update_item_status` (Task 9)
- Produces:
  - `erpnext.tbyt.refresh.refresh_items(item_codes: list[str]) -> None`
  - `erpnext.tbyt.refresh.refresh_for_document(doc, method=None) -> None`
  - `erpnext.tbyt.refresh.refresh_for_authorization(doc, method=None) -> None`

**Ruling tiền-thực-thi (bắt buộc giữ):** `refresh.py` **không được** import `resolver` / `status` ở cấp module — phải hoãn vào trong thân hàm. Lý do nằm trong comment của chính file. Đây không phải chỗ để "dọn dẹp import cho gọn": làm vậy là dựng lại vòng lặp import và app sẽ không nạp được.

**Vì sao cần task này:** không có nó thì trạng thái ôi tới 24 tiếng. 9h sáng upload CFS ở cấp chủ sở hữu, toàn bộ item của hãng vẫn hiển thị "Thiếu CFS" cho tới khi job nửa đêm chạy — người dùng vừa làm đúng việc mà hệ thống vẫn báo đỏ.

- [ ] **Step 1: Viết test thất bại**

Tạo `erpnext/tbyt/tests/test_refresh.py`:

```python
# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Chứng từ đổi thì trạng thái Item đổi NGAY, không chờ job nửa đêm."""

import frappe
from frappe.tests.utils import FrappeTestCase

import erpnext
from erpnext.tbyt import constants
from erpnext.tbyt.doctype.tbyt_marketing_authorization.test_tbyt_marketing_authorization import (
	make_authorization,
)
from erpnext.tbyt.tests.test_expiry import make_regulatory_document
from erpnext.tbyt.tests.test_item_fields import make_item

AUTH_DOCTYPE = "TBYT Marketing Authorization"


class TestRefresh(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		from erpnext.tbyt.setup import setup_tbyt_masters

		setup_tbyt_masters()

	def setUp(self):
		self.suffix = frappe.generate_hash(length=6)
		self.auth = make_authorization(
			so_luu_hanh=f"_TEST-SLH-RF-{self.suffix}", phan_loai="A"
		)
		self.item = make_item(f"_TEST-TBYT-RF-{self.suffix}", so_luu_hanh=self.auth.name)

	def _status(self):
		return frappe.db.get_value("Item", self.item.name, "tinh_trang_ho_so")

	def test_owner_level_upload_refreshes_every_item_of_that_owner(self):
		"""Một tờ giấy cấp chủ sở hữu chạm rất nhiều mặt hàng — phải quét hết."""
		sibling_auth = make_authorization(
			so_luu_hanh=f"_TEST-SLH-RF2-{self.suffix}",
			phan_loai="A",
			chu_so_huu=self.auth.chu_so_huu,
		)
		sibling = make_item(f"_TEST-TBYT-RF2-{self.suffix}", so_luu_hanh=sibling_auth.name)

		make_regulatory_document("thong_tin_bao_hanh", "Manufacturer", self.auth.chu_so_huu)

		for name in (self.item.name, sibling.name):
			self.assertIsNotNone(frappe.db.get_value("Item", name, "tinh_trang_ho_so"))

	def test_uploading_the_last_missing_document_flips_the_item_to_complete(self):
		from erpnext.tbyt.resolver import get_item_documents

		scope_map = {
			constants.SCOPE_COMPANY: ("Company", erpnext.get_default_company()),
			constants.SCOPE_OWNER: ("Manufacturer", self.auth.chu_so_huu),
			constants.SCOPE_AUTHORIZATION: (AUTH_DOCTYPE, self.auth.name),
			constants.SCOPE_ITEM: ("Item", self.item.name),
		}
		for row in get_item_documents(self.item.name):
			if row["is_required"] and not row["document"]:
				scope_doctype, scope_name = scope_map[row["scope_level"]]
				make_regulatory_document(row["document_key"], scope_doctype, scope_name)

		self.assertEqual(self._status(), constants.ITEM_STATUS_OK)

	def test_deactivating_a_document_flips_the_item_back_to_missing(self):
		doc = make_regulatory_document("hdsd_tieng_viet", AUTH_DOCTYPE, self.auth.name)
		doc.is_active = 0
		doc.save(ignore_permissions=True)
		self.assertEqual(self._status(), constants.ITEM_STATUS_MISSING)

	def test_revoking_the_authorization_refreshes_its_items(self):
		auth = frappe.get_doc(AUTH_DOCTYPE, self.auth.name)
		auth.trang_thai = constants.AUTH_STATUS_REVOKED
		auth.save(ignore_permissions=True)
		self.assertEqual(self._status(), constants.ITEM_STATUS_AUTH_INVALID)

	def test_deleting_a_document_refreshes_the_items_it_covered(self):
		doc = make_regulatory_document("hdsd_tieng_viet", AUTH_DOCTYPE, self.auth.name)
		frappe.delete_doc("TBYT Regulatory Document", doc.name, force=1, ignore_permissions=True)
		self.assertEqual(self._status(), constants.ITEM_STATUS_MISSING)
```

- [ ] **Step 2: Chạy test để xác nhận nó đỏ**

```bash
cd /home/miyano/frappe-bench && bench --site miyano run-tests --module erpnext.tbyt.tests.test_refresh
```

Kỳ vọng: FAIL — `ModuleNotFoundError: No module named 'erpnext.tbyt.refresh'`.

- [ ] **Step 3: Viết module làm mới**

Tạo `erpnext/tbyt/refresh.py`:

```python
# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Làm mới `tinh_trang_ho_so` của những Item bị một thay đổi chạm tới.

Chạy nền vì một chứng từ cấp chủ sở hữu có thể chạm hàng trăm mặt hàng — để
đồng bộ thì người dùng ngồi chờ mỗi lần bấm Lưu.
"""

import frappe

# CỐ Ý không import `resolver` và `status` ở cấp module. Controller
# `tbyt_marketing_authorization` import file này, mà `resolver` lại import
# `get_condition_context` từ chính controller đó — thành vòng lặp
# `authorization -> refresh -> resolver -> authorization`. Python sẽ nổ
# ImportError ngay khi Frappe nạp controller, và nổ từ cả hai đầu vào. Hoãn
# import vào trong thân hàm cắt vòng tại đúng một điểm.


def refresh_items(item_codes: list[str]) -> None:
	from erpnext.tbyt.status import update_item_status

	for item_code in item_codes:
		update_item_status(item_code)


def refresh_for_document(doc, method=None) -> None:
	"""Chứng từ đổi → làm mới mọi Item mà bảng phạm vi của nó phủ."""
	from erpnext.tbyt.resolver import find_items_for_scope

	affected = []
	for row in doc.pham_vi:
		affected.extend(find_items_for_scope(row.scope_doctype, row.scope_name))
	_enqueue(sorted(set(affected)))


def refresh_for_authorization(doc, method=None) -> None:
	"""Số lưu hành đổi trạng thái → làm mới mọi Item trỏ tới nó."""
	from erpnext.tbyt.resolver import find_items_for_scope

	_enqueue(find_items_for_scope("TBYT Marketing Authorization", doc.name))


def _enqueue(item_codes: list[str]) -> None:
	if not item_codes:
		return
	# `now=in_test` vì enqueue mặc định KHÔNG chạy inline trong test — nó đẩy
	# vào Redis thật và assert ngay sau đó sẽ đọc phải giá trị cũ.
	frappe.enqueue(
		"erpnext.tbyt.refresh.refresh_items",
		queue="short",
		item_codes=item_codes,
		now=bool(frappe.flags.in_test),
	)
```

- [ ] **Step 4: Nối vào hai controller**

Trong `erpnext/tbyt/doctype/tbyt_regulatory_document/tbyt_regulatory_document.py`, thêm import và sửa `on_update`, thêm `on_trash`:

```python
from erpnext.tbyt.refresh import refresh_for_document
```

```python
	def on_update(self):
		self._supersede_previous()
		place_file(self)
		refresh_for_document(self)

	def on_trash(self):
		refresh_for_document(self)
```

Trong `erpnext/tbyt/doctype/tbyt_marketing_authorization/tbyt_marketing_authorization.py`, thêm:

```python
from erpnext.tbyt.refresh import refresh_for_authorization
```

```python
	def on_update(self):
		refresh_for_authorization(self)
```

- [ ] **Step 5: Chạy test để xác nhận nó xanh**

```bash
cd /home/miyano/frappe-bench && bench --site miyano run-tests --module erpnext.tbyt.tests.test_refresh
```

Kỳ vọng: PASS, 5 test.

- [ ] **Step 6: Commit**

```bash
cd /home/miyano/frappe-bench/apps/erpnext
~/.local/bin/pre-commit run --files erpnext/tbyt/refresh.py erpnext/tbyt/tests/test_refresh.py erpnext/tbyt/doctype/tbyt_regulatory_document/tbyt_regulatory_document.py erpnext/tbyt/doctype/tbyt_marketing_authorization/tbyt_marketing_authorization.py
git add erpnext/tbyt/refresh.py erpnext/tbyt/tests/test_refresh.py erpnext/tbyt/doctype
git commit -m "feat(tbyt): lam moi trang thai ngay khi chung tu doi, khong cho job nua dem"
```

---

### Task 12: Job hằng ngày cập nhật hết hạn

**Files:**
- Modify: `erpnext/tbyt/expiry.py` — thêm `update_document_status()` và `get_expiring_documents()`
- Modify: `erpnext/hooks.py` — thêm vào `scheduler_events["daily"]` (khoảng dòng 451)
- Create: `erpnext/tbyt/tests/test_expiry_job.py`

**Interfaces:**
- Consumes: `compute_document_status` (Task 5), `refresh_items` (Task 11)
- Produces:
  - `erpnext.tbyt.expiry.update_document_status() -> dict` — trả `{"documents": int, "authorizations": int, "items": int}`
  - `erpnext.tbyt.expiry.get_expiring_documents(days=None) -> list[dict]`

- [ ] **Step 1: Viết test thất bại**

Tạo `erpnext/tbyt/tests/test_expiry_job.py`:

```python
# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Job hằng ngày — và điều quan trọng nhất là những gì nó KHÔNG đụng tới.

Chứng từ vô thời hạn phải bị loại khỏi truy vấn ngay từ đầu. Nếu không, mỗi sáng
người dùng nhận một danh sách cảnh báo giả và sẽ nhanh chóng thôi đọc nó — lúc
đó giấy thật sắp hết hạn cũng chìm theo.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from erpnext.tbyt import constants
from erpnext.tbyt.doctype.tbyt_marketing_authorization.test_tbyt_marketing_authorization import (
	make_authorization,
)
from erpnext.tbyt.expiry import get_expiring_documents, update_document_status
from erpnext.tbyt.tests.test_expiry import make_regulatory_document
from erpnext.tbyt.tests.test_item_fields import make_item

AUTH_DOCTYPE = "TBYT Marketing Authorization"


class TestExpiryJob(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		from erpnext.tbyt.setup import setup_tbyt_masters

		setup_tbyt_masters()

	def setUp(self):
		self.suffix = frappe.generate_hash(length=6)
		self.auth = make_authorization(so_luu_hanh=f"_TEST-SLH-JOB-{self.suffix}")
		self.item = make_item(f"_TEST-TBYT-JOB-{self.suffix}", so_luu_hanh=self.auth.name)

	def test_job_marks_a_lapsed_document_as_expired(self):
		doc = make_regulatory_document(
			"hdsd_tieng_viet",
			AUTH_DOCTYPE,
			self.auth.name,
			khong_thoi_han=0,
			ngay_het_han=add_days(today(), 5),
		)
		# Đẩy ngày về quá khứ mà không qua validate, mô phỏng thời gian trôi.
		frappe.db.set_value(
			"TBYT Regulatory Document", doc.name, "ngay_het_han", add_days(today(), -1)
		)
		update_document_status()
		self.assertEqual(
			frappe.db.get_value("TBYT Regulatory Document", doc.name, "trang_thai"),
			constants.DOC_STATUS_EXPIRED,
		)

	def test_job_never_touches_an_indefinite_document(self):
		doc = make_regulatory_document("hdsd_tieng_viet", AUTH_DOCTYPE, self.auth.name)
		update_document_status()
		self.assertEqual(
			frappe.db.get_value("TBYT Regulatory Document", doc.name, "trang_thai"),
			constants.DOC_STATUS_VALID,
		)

	def test_indefinite_document_never_appears_in_the_warning_list(self):
		make_regulatory_document("hdsd_tieng_viet", AUTH_DOCTYPE, self.auth.name)
		keys = {row["document_type"] for row in get_expiring_documents()}
		self.assertNotIn("hdsd_tieng_viet", keys)

	def test_document_inside_the_window_appears_in_the_warning_list(self):
		make_regulatory_document(
			"tai_lieu_ky_thuat_bao_duong",
			AUTH_DOCTYPE,
			self.auth.name,
			khong_thoi_han=0,
			ngay_het_han=add_days(today(), 10),
		)
		keys = {row["document_type"] for row in get_expiring_documents()}
		self.assertIn("tai_lieu_ky_thuat_bao_duong", keys)

	def test_job_lapses_an_authorization_whose_date_has_passed(self):
		auth = make_authorization(
			so_luu_hanh=f"_TEST-SLH-JOBEXP-{self.suffix}",
			khong_thoi_han=0,
			ngay_het_han=add_days(today(), 5),
		)
		frappe.db.set_value(AUTH_DOCTYPE, auth.name, "ngay_het_han", add_days(today(), -1))
		update_document_status()
		self.assertEqual(
			frappe.db.get_value(AUTH_DOCTYPE, auth.name, "trang_thai"),
			constants.AUTH_STATUS_EXPIRED,
		)

	def test_job_never_lapses_an_indefinite_authorization(self):
		update_document_status()
		self.assertEqual(
			frappe.db.get_value(AUTH_DOCTYPE, self.auth.name, "trang_thai"),
			constants.AUTH_STATUS_VALID,
		)

	def test_job_refreshes_item_status_as_a_safety_net(self):
		frappe.db.set_value("Item", self.item.name, "tinh_trang_ho_so", None)
		update_document_status()
		self.assertIsNotNone(frappe.db.get_value("Item", self.item.name, "tinh_trang_ho_so"))
```

- [ ] **Step 2: Chạy test để xác nhận nó đỏ**

```bash
cd /home/miyano/frappe-bench && bench --site miyano run-tests --module erpnext.tbyt.tests.test_expiry_job
```

Kỳ vọng: FAIL — `ImportError: cannot import name 'update_document_status'`.

- [ ] **Step 3: Thêm job vào `expiry.py`**

Trước hết thêm `import frappe` vào đầu `erpnext/tbyt/expiry.py` (Task 5 chưa cần
tới nó vì `compute_document_status` là hàm thuần, không chạm DB):

```python
import frappe
from frappe.utils import add_days, cint, getdate
```

Rồi nối vào cuối file:

```python
def update_document_status() -> dict:
	"""Job hằng ngày: đồng bộ trạng thái hiệu lực và trạng thái hồ sơ Item.

	Bản ghi vô thời hạn bị loại khỏi truy vấn NGAY TỪ ĐẦU — không đọc lên rồi
	mới bỏ qua. Đây là lý do cảnh báo hằng ngày giữ được uy tín.
	"""
	from erpnext.tbyt.constants import AUTH_STATUS_EXPIRED, AUTH_STATUS_VALID
	from erpnext.tbyt.refresh import refresh_items

	documents = 0
	for row in frappe.get_all(
		"TBYT Regulatory Document",
		filters={"is_active": 1, "khong_thoi_han": 0, "ngay_het_han": ("is", "set")},
		fields=["name", "is_active", "khong_thoi_han", "ngay_het_han", "trang_thai"],
	):
		wanted = compute_document_status(
			is_active=row.is_active,
			khong_thoi_han=row.khong_thoi_han,
			ngay_het_han=row.ngay_het_han,
		)
		if wanted != row.trang_thai:
			frappe.db.set_value(
				"TBYT Regulatory Document", row.name, "trang_thai", wanted, update_modified=False
			)
			documents += 1

	authorizations = 0
	lapsed = frappe.get_all(
		"TBYT Marketing Authorization",
		filters={
			"trang_thai": AUTH_STATUS_VALID,
			"khong_thoi_han": 0,
			"ngay_het_han": ("<", getdate()),
		},
		pluck="name",
	)
	for name in lapsed:
		frappe.db.set_value(
			"TBYT Marketing Authorization",
			name,
			"trang_thai",
			AUTH_STATUS_EXPIRED,
			update_modified=False,
		)
		authorizations += 1

	# Lưới an toàn cho việc làm mới tức thời (Task 11): nếu một job nền chết
	# giữa chừng thì đêm nay hệ thống tự sửa lại.
	items = frappe.get_all("Item", filters={"la_thiet_bi_y_te": 1}, pluck="name")
	refresh_items(items)

	return {"documents": documents, "authorizations": authorizations, "items": len(items)}


def get_expiring_documents(days=None) -> list[dict]:
	"""Chứng từ sắp hết hạn trong `days` ngày tới. Vô thời hạn không bao giờ lọt vào."""
	window = EXPIRY_WARNING_DAYS if days is None else days
	return frappe.get_all(
		"TBYT Regulatory Document",
		filters={
			"is_active": 1,
			"khong_thoi_han": 0,
			"ngay_het_han": ("between", [getdate(), add_days(getdate(), window)]),
		},
		fields=["name", "document_type", "so_hieu", "ngay_het_han", "trang_thai"],
		order_by="ngay_het_han asc",
	)
```

- [ ] **Step 4: Nối vào lịch chạy**

Trong `erpnext/hooks.py`, thêm một dòng vào danh sách `scheduler_events["daily"]` (khoảng dòng 451):

```python
		"erpnext.tbyt.expiry.update_document_status",
```

- [ ] **Step 5: Chạy test để xác nhận nó xanh**

```bash
cd /home/miyano/frappe-bench && bench --site miyano run-tests --module erpnext.tbyt.tests.test_expiry_job
```

Kỳ vọng: PASS, 7 test.

- [ ] **Step 6: Commit**

```bash
cd /home/miyano/frappe-bench/apps/erpnext
~/.local/bin/pre-commit run --files erpnext/tbyt/expiry.py erpnext/tbyt/tests/test_expiry_job.py erpnext/hooks.py
git add erpnext/tbyt/expiry.py erpnext/tbyt/tests/test_expiry_job.py erpnext/hooks.py
git commit -m "feat(tbyt): job hang ngay dong bo hieu luc, bo qua giay vo thoi han"
```

---

### Task 13: Report "Tinh Trang Ho So TBYT"

**Files:**
- Create: `erpnext/tbyt/report/__init__.py`
- Create: `erpnext/tbyt/report/tinh_trang_ho_so_tbyt/__init__.py`
- Create: `erpnext/tbyt/report/tinh_trang_ho_so_tbyt/tinh_trang_ho_so_tbyt.json`
- Create: `erpnext/tbyt/report/tinh_trang_ho_so_tbyt/tinh_trang_ho_so_tbyt.py`
- Create: `erpnext/tbyt/report/tinh_trang_ho_so_tbyt/tinh_trang_ho_so_tbyt.js`
- Create: `erpnext/tbyt/report/tinh_trang_ho_so_tbyt/test_tinh_trang_ho_so_tbyt.py`

**Interfaces:**
- Consumes: `get_item_documents` (Task 8), `get_item_status` (Task 9), constants (Task 1)
- Produces: `erpnext.tbyt.report.tinh_trang_ho_so_tbyt.tinh_trang_ho_so_tbyt.execute(filters=None) -> tuple[list, list]`

**Vì sao task này không phải phụ kiện:** đã chốt hệ thống **không chặn** nghiệp vụ khi thiếu chứng từ, nên report là cơ chế kiểm soát duy nhất còn lại.

- [ ] **Step 1: Viết test thất bại**

Tạo `erpnext/tbyt/report/tinh_trang_ho_so_tbyt/test_tinh_trang_ho_so_tbyt.py`:

```python
# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Báo cáo tổng hợp — cơ chế kiểm soát chính vì hệ thống không chặn nghiệp vụ.

Cột "Hồ sơ cấp lô" tồn tại để bù cho việc trạng thái Item cố ý bỏ qua CQ và CO:
nếu không có cột này thì hai chứng từ BB ở cả bốn phân loại sẽ không ai theo dõi.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.tbyt import constants
from erpnext.tbyt.doctype.tbyt_marketing_authorization.test_tbyt_marketing_authorization import (
	make_authorization,
)
from erpnext.tbyt.report.tinh_trang_ho_so_tbyt.tinh_trang_ho_so_tbyt import execute
from erpnext.tbyt.tests.test_expiry import make_regulatory_document
from erpnext.tbyt.tests.test_item_fields import make_item

AUTH_DOCTYPE = "TBYT Marketing Authorization"


class TestTinhTrangHoSoTBYT(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		from erpnext.tbyt.setup import setup_tbyt_masters

		setup_tbyt_masters()

	def setUp(self):
		self.suffix = frappe.generate_hash(length=6)
		self.auth = make_authorization(
			so_luu_hanh=f"_TEST-SLH-RPT-{self.suffix}", phan_loai="B"
		)
		self.item = make_item(f"_TEST-TBYT-RPT-{self.suffix}", so_luu_hanh=self.auth.name)

	def _row(self, rows):
		return next((r for r in rows if r["item_code"] == self.item.name), None)

	def test_report_lists_medical_items(self):
		_columns, rows = execute({})
		self.assertIsNotNone(self._row(rows))

	def test_report_counts_missing_required_documents(self):
		_columns, rows = execute({})
		row = self._row(rows)
		self.assertGreater(row["bb_thieu"], 0)

	def test_report_counts_drop_as_documents_arrive(self):
		_columns, before_rows = execute({})
		before = self._row(before_rows)["bb_thieu"]
		make_regulatory_document("hdsd_tieng_viet", AUTH_DOCTYPE, self.auth.name)
		_columns, after_rows = execute({})
		self.assertEqual(self._row(after_rows)["bb_thieu"], before - 1)

	def test_report_reports_batch_level_coverage_separately(self):
		"""CQ và CO là BB ở cả bốn phân loại nhưng không tính vào trạng thái Item."""
		_columns, rows = execute({})
		self.assertIn("ho_so_lo", rows[0])

	def test_filter_only_incomplete_hides_complete_items(self):
		_columns, rows = execute({"chi_hien_thieu": 1})
		self.assertTrue(all(r["tinh_trang_ho_so"] != constants.ITEM_STATUS_OK for r in rows))

	def test_filter_by_device_class(self):
		_columns, rows = execute({"phan_loai": "B"})
		self.assertTrue(all(r["phan_loai_tbyt"] == "B" for r in rows))
		self.assertIsNotNone(self._row(rows))

	def test_columns_expose_the_expiry_horizon(self):
		columns, _rows = execute({})
		fieldnames = {c["fieldname"] for c in columns}
		self.assertIn("ngay_het_han_gan_nhat", fieldnames)
		self.assertIn("chung_tu_het_han", fieldnames)
```

- [ ] **Step 2: Chạy test để xác nhận nó đỏ**

```bash
cd /home/miyano/frappe-bench && bench --site miyano run-tests --module erpnext.tbyt.report.tinh_trang_ho_so_tbyt.test_tinh_trang_ho_so_tbyt
```

Kỳ vọng: FAIL — module report chưa tồn tại.

- [ ] **Step 3: Tạo khung report**

```bash
cd /home/miyano/frappe-bench/apps/erpnext
mkdir -p erpnext/tbyt/report/tinh_trang_ho_so_tbyt
touch erpnext/tbyt/report/__init__.py erpnext/tbyt/report/tinh_trang_ho_so_tbyt/__init__.py
```

`erpnext/tbyt/report/tinh_trang_ho_so_tbyt/tinh_trang_ho_so_tbyt.json`:

```json
{
 "add_total_row": 0,
 "columns": [],
 "creation": "2026-08-21 09:00:00.000000",
 "disabled": 0,
 "docstatus": 0,
 "doctype": "Report",
 "filters": [],
 "idx": 0,
 "is_standard": "Yes",
 "letter_head": "",
 "modified": "2026-08-21 09:00:00.000000",
 "modified_by": "Administrator",
 "module": "TBYT",
 "name": "Tinh Trang Ho So TBYT",
 "owner": "Administrator",
 "prepared_report": 0,
 "ref_doctype": "Item",
 "report_name": "Tinh Trang Ho So TBYT",
 "report_type": "Script Report",
 "roles": [
  {
   "role": "System Manager"
  },
  {
   "role": "Item Manager"
  }
 ]
}
```

`erpnext/tbyt/report/tinh_trang_ho_so_tbyt/tinh_trang_ho_so_tbyt.js`:

```javascript
// Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

frappe.query_reports["Tinh Trang Ho So TBYT"] = {
	filters: [
		{
			fieldname: "phan_loai",
			label: __("Phân loại"),
			fieldtype: "Select",
			options: "\nA\nB\nC\nD",
		},
		{
			fieldname: "chu_so_huu",
			label: __("Chủ sở hữu"),
			fieldtype: "Link",
			options: "Manufacturer",
		},
		{
			fieldname: "item_group",
			label: __("Nhóm hàng"),
			fieldtype: "Link",
			options: "Item Group",
		},
		{
			fieldname: "chi_hien_thieu",
			label: __("Chỉ hiện hồ sơ chưa đủ"),
			fieldtype: "Check",
			default: 1,
		},
	],
};
```

- [ ] **Step 4: Viết logic report**

`erpnext/tbyt/report/tinh_trang_ho_so_tbyt/tinh_trang_ho_so_tbyt.py`:

```python
# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Tình trạng hồ sơ pháp lý TBYT theo từng mặt hàng.

Đã chốt hệ thống KHÔNG chặn nghiệp vụ khi thiếu chứng từ, nên báo cáo này là cơ
chế kiểm soát duy nhất còn lại — nó phải nói đủ, kể cả phần mà trạng thái trên
Item cố ý bỏ qua (chứng từ cấp lô).
"""

import frappe
from frappe import _

from erpnext.tbyt.constants import (
	DOC_STATUS_EXPIRED,
	ITEM_STATUS_OK,
	LEVEL_BB,
	LEVEL_BB_STAR,
	LEVEL_NC,
)
from erpnext.tbyt.resolver import get_item_documents
from erpnext.tbyt.status import get_item_status

BATCH_REQUIRED = ("cq_chung_nhan_chat_luong", "co_chung_nhan_xuat_xu")


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"fieldname": "item_code", "label": _("Mặt hàng"), "fieldtype": "Link", "options": "Item", "width": 180},
		{"fieldname": "item_name", "label": _("Tên hàng"), "fieldtype": "Data", "width": 200},
		{"fieldname": "item_group", "label": _("Nhóm"), "fieldtype": "Link", "options": "Item Group", "width": 140},
		{
			"fieldname": "so_luu_hanh",
			"label": _("Số lưu hành"),
			"fieldtype": "Link",
			"options": "TBYT Marketing Authorization",
			"width": 150,
		},
		{"fieldname": "phan_loai_tbyt", "label": _("Phân loại"), "fieldtype": "Data", "width": 80},
		{"fieldname": "trang_thai_slh", "label": _("Trạng thái SLH"), "fieldtype": "Data", "width": 130},
		{"fieldname": "tinh_trang_ho_so", "label": _("Tình trạng hồ sơ"), "fieldtype": "Data", "width": 170},
		{"fieldname": "bb_thieu", "label": _("BB thiếu"), "fieldtype": "Int", "width": 90},
		{"fieldname": "bb_star_thieu", "label": _("BB* thiếu"), "fieldtype": "Int", "width": 90},
		{"fieldname": "nc_thieu", "label": _("NC thiếu"), "fieldtype": "Int", "width": 90},
		{"fieldname": "chung_tu_het_han", "label": _("Hết hạn"), "fieldtype": "Int", "width": 80},
		{
			"fieldname": "ngay_het_han_gan_nhat",
			"label": _("Hết hạn gần nhất"),
			"fieldtype": "Date",
			"width": 130,
		},
		{"fieldname": "ho_so_lo", "label": _("Hồ sơ cấp lô"), "fieldtype": "Data", "width": 130},
	]


def get_data(filters):
	item_filters = {"la_thiet_bi_y_te": 1}
	if filters.get("item_group"):
		item_filters["item_group"] = filters.item_group
	if filters.get("phan_loai"):
		item_filters["phan_loai_tbyt"] = filters.phan_loai

	items = frappe.get_all(
		"Item",
		filters=item_filters,
		fields=["name", "item_name", "item_group", "so_luu_hanh", "phan_loai_tbyt"],
		order_by="name",
	)

	owner_filter = filters.get("chu_so_huu")
	rows = []
	for item in items:
		auth = (
			frappe.db.get_value(
				"TBYT Marketing Authorization",
				item.so_luu_hanh,
				["chu_so_huu", "trang_thai"],
				as_dict=True,
			)
			if item.so_luu_hanh
			else None
		)
		if owner_filter and (not auth or auth.chu_so_huu != owner_filter):
			continue

		documents = get_item_documents(item.name)
		missing = _count_missing(documents)
		expired = [d for d in documents if d["document"] and d["trang_thai"] == DOC_STATUS_EXPIRED]
		horizon = _nearest_expiry(documents)
		status = get_item_status(item.name)

		if filters.get("chi_hien_thieu") and status == ITEM_STATUS_OK:
			continue

		rows.append(
			{
				"item_code": item.name,
				"item_name": item.item_name,
				"item_group": item.item_group,
				"so_luu_hanh": item.so_luu_hanh,
				"phan_loai_tbyt": item.phan_loai_tbyt,
				"trang_thai_slh": auth.trang_thai if auth else None,
				"tinh_trang_ho_so": status,
				"bb_thieu": missing[LEVEL_BB],
				"bb_star_thieu": missing[LEVEL_BB_STAR],
				"nc_thieu": missing[LEVEL_NC],
				"chung_tu_het_han": len(expired),
				"ngay_het_han_gan_nhat": horizon,
				"ho_so_lo": _batch_coverage(item.name),
			}
		)
	return rows


def _count_missing(documents):
	counts = {LEVEL_BB: 0, LEVEL_BB_STAR: 0, LEVEL_NC: 0}
	for row in documents:
		if row["document"]:
			continue
		if row["level"] == LEVEL_BB_STAR and not row["is_required"]:
			continue
		if row["level"] in counts:
			counts[row["level"]] += 1
	return counts


def _nearest_expiry(documents):
	dates = [
		row["ngay_het_han"]
		for row in documents
		if row["document"] and not row["khong_thoi_han"] and row["ngay_het_han"]
	]
	return min(dates) if dates else None


def _batch_coverage(item_code: str) -> str:
	"""CQ và CO theo từng lô — phần mà trạng thái trên Item cố ý không xét.

	Trả về "3/4 lô" nghĩa là 3 trên 4 lô còn tồn đã đủ cả CQ lẫn CO.
	"""
	batches = frappe.get_all("Batch", filters={"item": item_code, "disabled": 0}, pluck="name")
	if not batches:
		return _("Chưa có lô")

	covered = 0
	for batch in batches:
		found = frappe.db.sql(
			"""
			select count(distinct rd.document_type)
			from `tabTBYT Regulatory Document` rd
			inner join `tabTBYT Document Scope` sc on sc.parent = rd.name
			where rd.is_active = 1
				and rd.document_type in %(types)s
				and sc.parenttype = 'TBYT Regulatory Document'
				and sc.scope_doctype = 'Batch'
				and sc.scope_name = %(batch)s
			""",
			{"types": BATCH_REQUIRED, "batch": batch},
		)[0][0]
		if found == len(BATCH_REQUIRED):
			covered += 1

	return f"{covered}/{len(batches)} " + _("lô")
```

- [ ] **Step 5: Migrate và chạy test**

```bash
cd /home/miyano/frappe-bench && bench --site miyano migrate
bench --site miyano run-tests --module erpnext.tbyt.report.tinh_trang_ho_so_tbyt.test_tinh_trang_ho_so_tbyt
```

Kỳ vọng: PASS, 7 test.

- [ ] **Step 6: Chạy toàn bộ suite của module, mỗi module một lệnh**

`bench run-tests --module A --module B` chỉ chạy module CUỐI và im lặng bỏ qua phần còn lại — nên phải lặp:

```bash
cd /home/miyano/frappe-bench
for m in test_tbyt_module test_tbyt_setup test_expiry test_duplicate test_item_fields \
         test_resolver test_status test_folders test_refresh test_expiry_job; do
	echo "=== $m ==="
	bench --site miyano run-tests --module erpnext.tbyt.tests.$m 2>&1 | tail -4
done
bench --site miyano run-tests --doctype "TBYT Document Type" 2>&1 | tail -4
bench --site miyano run-tests --doctype "TBYT Marketing Authorization" 2>&1 | tail -4
bench --site miyano run-tests --module erpnext.tbyt.report.tinh_trang_ho_so_tbyt.test_tinh_trang_ho_so_tbyt 2>&1 | tail -4
```

Kỳ vọng: mọi suite OK. Tổng 116 test.

- [ ] **Step 7: Commit**

```bash
cd /home/miyano/frappe-bench/apps/erpnext
~/.local/bin/pre-commit run --files erpnext/tbyt/report/tinh_trang_ho_so_tbyt/tinh_trang_ho_so_tbyt.py erpnext/tbyt/report/tinh_trang_ho_so_tbyt/test_tinh_trang_ho_so_tbyt.py
git add erpnext/tbyt/report
git commit -m "feat(tbyt): bao cao tinh trang ho so phap ly theo mat hang"
```

---

## Bản đồ đặc tả → task

Dùng để kiểm sót khi review. Mọi mục của đặc tả đều có task thực thi.

| Mục đặc tả | Task |
|---|---|
| §4.1 `TBYT Document Type` | 2 |
| §4.2 `TBYT Document Rule` | 2 |
| §4.3 `TBYT Marketing Authorization` | 4 |
| §4.4 `TBYT Regulatory Document` + tri-state hết hạn | 5 |
| §4.5 `TBYT Document Scope` — phạm vi đa giá trị | 5, 6 |
| §5 Phân bổ 23 chứng từ | 3 |
| §6 Trường trên Item + 6 giá trị trạng thái | 7, 9 |
| §7 Cây thư mục + quy ước tên file | 10 |
| §8.1 resolver, bảng mức × có-record, TH | 8 |
| §8.2 Chặn trùng (R2) | 6 |
| §8.3 Điều kiện BB\* | 3 (dữ liệu), 8 (đánh giá) |
| §8.4 Cảnh báo trên Item, không chặn | 9 |
| §8.5 `folders.py` | 10 |
| §8.6 Làm mới khi chứng từ đổi | 11 |
| §8.7 Job hằng ngày | 12 |
| §9 Report + cột hồ sơ cấp lô | 13 |
| §10 Seed + patch | 3 |
| §11 Ngoài phạm vi (`ho_so_phan_phoi`) | — cố ý không làm |
| §12 Kiểm thử | rải khắp mọi task |

**Ràng buộc R1–R4 của đặc tả §1:**

| Ràng buộc | Được chứng minh bởi |
|---|---|
| R1 — theo dõi thiếu / hết hạn, có hạn hoặc vô thời hạn | `test_expiry.py` (tri-state), `test_expiry_job.py` (vô thời hạn không lọt cảnh báo) |
| R2 — một tờ giấy tồn tại đúng một lần | `test_duplicate.py`, `test_resolver.py::test_second_item_inherits_without_creating_any_new_record` |
| R3 — phân loại khác nhau, bộ chứng từ khác nhau | `test_tbyt_setup.py`, `test_resolver.py` (4 phân loại + bẫy `hop_chuan_hop_quy`) |
| R4 — thiếu tạm thời được, chỉ số lưu hành bắt buộc | `test_item_fields.py`, `test_status.py::test_saving_a_medical_item_warns_but_does_not_block` |

## Việc cần làm bằng tay sau khi triển khai

1. **Nhập danh mục `Manufacturer`** — site đang có 0 bản ghi, mà `chu_so_huu` là trường bắt buộc của số lưu hành. Không nhập thì không tạo được bản ghi nào.
2. **Tích cờ `la_tbyt`** cho ba nhóm hàng có sẵn: *Vật tư y tế tiêu hao*, *Hóa chất - sinh phẩm*, *Thiết bị y tế và phụ kiện*.
3. **Rà 2 Item hiện có** trên site: nếu là hàng y tế thì gắn số lưu hành.

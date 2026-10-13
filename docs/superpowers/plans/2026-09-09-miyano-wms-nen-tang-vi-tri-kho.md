# miyano_wms — Nền tảng vị trí kho (GĐ 0 + GĐ 1) Implementation Plan

> ## ⚠️ HỒ SƠ LỊCH SỬ — ĐÃ THI CÔNG XONG, ĐỪNG THI CÔNG LẠI
>
> 15 task trong file này đã làm xong 10/09/2026. Giữ lại để tra thứ tự đã làm và lý do từng
> bước, **không phải để chạy tiếp**.
>
> Nội dung mô tả **mô hình cũ**: mã ô tự do, `Storage Location` là cây nested set, ô hệ thống
> tên `CHUA-XEP`. Cả ba đều đã bị thay bởi chuẩn mã 12 ký tự của SPD (10/09/2026).
> **Nguồn sự thật hiện hành là `../specs/2026-09-09-miyano-wms-vi-tri-kho-design.md` §5.1 và
> §5.8**, cùng `docs/BAN-GIAO-nen-tang-vi-tri-kho.md` mục 0.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dựng app `miyano_wms` với cây vị trí, sổ vị trí bám theo chứng từ ERPNext, và chức năng bật quản lý vị trí cho kho chỉ định — để tồn kho biết tới từng ô kệ và tự phát hiện khi lệch.

**Architecture:** Tầng vị trí **không tự quyết số lượng**; nó chia nhỏ con số ERPNext đã chốt ra theo từng ô. Bất biến nền: *tổng tồn các ô của một (mặt hàng, lô) = `Bin.actual_qty`*. Toàn bộ việc ghi sổ đi qua **một hook duy nhất** `Stock Ledger Entry.on_submit` — đã xác minh mọi chứng từ đều tạo SLE qua `make_entry()` → `sle.submit()` (`apps/erpnext/erpnext/stock/stock_ledger.py:221-227`). Ô hệ thống `CHUA-XEP` mỗi kho là van an toàn để bất biến luôn đúng kể cả với chứng từ không khai vị trí.

**Tech Stack:** Frappe v15.113.4, ERPNext v15.83.0 (fork `mvl26/erpnext`), Python 3.12, MariaDB 10.11. Test bằng `FrappeTestCase`.

**Spec:** `apps/miyano_portal/docs/superpowers/specs/2026-09-09-miyano-wms-vi-tri-kho-design.md`

## Global Constraints

- Spec nguồn ở trên. Mọi quyết định trong đó là ràng buộc — đặc biệt mục 2 (quyết định nền tảng), mục 3 (bất biến), mục 4.3 và 4.3b (hai cái bẫy).
- App mới: `apps/miyano_wms`. `app_name = "miyano_wms"`, `required_apps = ["frappe/frappe", "erpnext"]`. Module Frappe: **`Miyano WMS`**.
- Bench: `/home/hoangvietyeuem/frappe-bench-yhct`. Site dev + test: `erptest.local`.
- **Không đụng vào `apps/miyano_portal`** ngoài việc di chuyển hai file tài liệu ở Task 1. Sổ kho khách hàng của app đó là hệ khác, tách bạch hoàn toàn.
- **Không đụng vào `apps/supplycore`** và **không restart gunicorn :8002** (site bệnh viện đang chạy thật). Dev server là `systemctl --user restart erptest-dev.service` (cần `XDG_RUNTIME_DIR=/run/user/1000`).
- **Tên doctype tiếng Anh**, fieldname tiếng Việt **không dấu**, label tiếng Việt. Lý do: Frappe sinh tên thư mục và module Python bằng `frappe.scrub(doctype_name)`; tên có dấu tạo thư mục Unicode, dễ vỡ với git và chuẩn hoá NFC/NFD.
- Mọi thông báo lỗi ra **tiếng Việt**, nêu rõ ô nào / mặt hàng nào / thiếu bao nhiêu. Không lộ tên doctype tiếng Anh, không lộ traceback.
- **Số lô lấy từ `Serial and Batch Bundle`, KHÔNG từ `sle.batch_no`.** Đã đo trên `erptest.local`: 0/56 dòng SLE của hàng có lô mang `batch_no`; 56/56 mang `serial_and_batch_bundle`. Đọc sai chỗ này thì 80/164 mặt hàng mất chiều lô **mà báo cáo đối soát vẫn báo khớp**.
- **`Stock Reconciliation` hàng không lô ghi `actual_qty = 0`** và chỉ đặt `qty_after_transaction` (`stock_reconciliation.py:861,870`). Cộng dồn `actual_qty` là bỏ qua âm thầm mọi lần kiểm kê.
- **Huỷ chứng từ phải đảo đúng ô gốc**, tuyệt đối không chạy lại FEFO — làm vậy trả hàng về ô khác với ô đã lấy, sai tồn hai ô mà tổng vẫn đúng nên đối soát không bắt được.
- `Location Ledger Entry` là sổ **chỉ ghi thêm**. Không sửa, không xoá dòng — kể cả khi huỷ.
- Không doctype nào trong app này được có DocPerm cho vai trò `Customer` hay `Website User`.
- Chạy test: `cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests --app miyano_wms --module miyano_wms.tests.<tên module>`
- Chạy cả bộ: `bench --site erptest.local run-tests --app miyano_wms`
- Áp dụng thay đổi doctype JSON: `bench --site erptest.local migrate`
- **Máy 15Gi RAM chạy 3 bench song song.** `ReadTimeout` ngẫu nhiên khi chạy test thường là cạn RAM, không phải hồi quy — chạy lại đúng bài đó trước khi kết luận.
- Commit sau mỗi task. **Không push.**

## Phạm vi

Plan này phủ **GĐ 0 + GĐ 1** trong bảng §9 của spec. Hai giai đoạn này gộp làm một vì `Warehouse Location Setup` (GĐ 0) khi bật phải ghi sổ vị trí — mà sổ nằm ở GĐ 1.

**Cố ý KHÔNG có trong plan này:**

- **Bảng phân bổ `Location Allocation`** (spec §5.4) và giao diện chọn ô trên chứng từ — đó là GĐ 2. Trong plan này hook **chỉ** có hai nhánh: nhập không khai vị trí → `CHUA-XEP`; xuất không khai vị trí → FEFO. Không viết sẵn nhánh đọc phân bổ.
- Gợi ý lấy hàng trên Delivery Note, cột Vị trí trên phiếu in (GĐ 3).
- `Location Transfer`, `Location Count` (GĐ 4).
- `Item Location Preference` (spec §5.5) — chỉ dùng cho gợi ý đặt hàng ở GĐ 2.
- In tem mã vạch, quét bằng điện thoại (GĐ 5).

Kết thúc plan này, phần mềm chạy được và kiểm chứng được: bật quản lý vị trí cho `Kho Miyano - MYN`, mọi xuất nhập tự ghi sổ theo ô và lô, báo cáo đối soát khẳng định tồn vị trí khớp `Bin` theo từng lô.

## File Structure

**Tạo mới — app `apps/miyano_wms`**

| File | Trách nhiệm |
|---|---|
| `miyano_wms/hooks.py` | Khai báo app, `doc_events` cho `Stock Ledger Entry` |
| `miyano_wms/patches.txt`, `miyano_wms/patches/v1_0/them_co_quan_ly_vi_tri.py` | Custom field `custom_quan_ly_vi_tri` (read-only) trên `Warehouse` |
| `miyano_wms/miyano_wms/doctype/storage_location/` | Cây vị trí (nested set) |
| `miyano_wms/miyano_wms/doctype/location_ledger_entry/` | Sổ vị trí, chỉ ghi thêm |
| `miyano_wms/miyano_wms/doctype/location_balance/` | Bộ đệm tồn theo ô × mặt hàng × lô |
| `miyano_wms/miyano_wms/doctype/warehouse_location_setup/` | Bật/tắt/xem trước/đồng bộ lại theo kho |
| `miyano_wms/miyano_wms/doctype/location_generator/` | Sinh mã ô hàng loạt |
| `miyano_wms/vitri/kho.py` | Hỏi kho có bật không (qua cache), tra ô `CHUA-XEP` |
| `miyano_wms/vitri/lo.py` | `tach_theo_lo()` — lấy lô từ Serial and Batch Bundle |
| `miyano_wms/vitri/delta.py` | `tinh_delta()` — gồm bẫy Stock Reconciliation |
| `miyano_wms/vitri/so.py` | Engine ghi sổ, cập nhật tồn, dựng lại tồn |
| `miyano_wms/vitri/fefo.py` | Chọn ô khi xuất mà không khai vị trí |
| `miyano_wms/vitri/hook_sle.py` | Hook `Stock Ledger Entry.on_submit` — điều phối |
| `miyano_wms/vitri/doi_soat.py` | So tồn vị trí với `Bin` |
| `miyano_wms/vitri/bat_kho.py` | Bốn thao tác của `Warehouse Location Setup` |
| `miyano_wms/vitri/sinh_ma.py` | Logic sinh mã ô |
| `miyano_wms/miyano_wms/report/doi_soat_ton_vi_tri/` | Báo cáo đối soát (spec §8.4) |
| `miyano_wms/miyano_wms/report/ton_kho_theo_vi_tri/` | Báo cáo tồn theo ô (spec §8.1) |
| `miyano_wms/miyano_wms/report/hang_chua_xep_vi_tri/` | Việc cần dọn của thủ kho (spec §8.3) |
| `miyano_wms/tests/test_*.py` | Bộ kiểm thử |

**Vì sao tách `vitri/` khỏi thư mục doctype:** logic ghi sổ được gọi từ hook, từ doctype `Warehouse Location Setup`, và từ báo cáo. Nhét vào controller của một doctype nào đó là buộc ba chỗ phải import chéo qua nhau.

---

### Task 1: Dựng app `miyano_wms` và cài lên `erptest.local`

**Files:**
- Create: `apps/miyano_wms/` (toàn bộ khung app do `bench new-app` sinh)
- Modify: `/home/hoangvietyeuem/frappe-bench-yhct/sites/apps.txt`
- Create: `apps/miyano_wms/miyano_wms/tests/__init__.py`
- Test: `apps/miyano_wms/miyano_wms/tests/test_app_khoi_dong.py`

**Interfaces:**
- Consumes: không có (task đầu tiên)
- Produces: app `miyano_wms` cài được trên `erptest.local`; module Frappe `Miyano WMS`; lệnh `bench --site erptest.local run-tests --app miyano_wms` chạy được

- [ ] **Step 1: Tạo app**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench new-app miyano_wms
```

Lệnh này hỏi tương tác — trả lời:

| Câu hỏi | Trả lời |
|---|---|
| App Title | `Miyano WMS` |
| App Description | `Quản lý vị trí kho (giá kệ, ô kệ) cho Miyano` |
| App Publisher | `Miyano` |
| App Email | `anh.doan@medcons.vn` |
| App License | `mit` |
| Create GitHub Workflow action | `n` |

- [ ] **Step 2: Khai báo phụ thuộc ERPNext**

Sửa `apps/miyano_wms/miyano_wms/hooks.py`, thêm ngay sau dòng `app_license`:

```python
required_apps = ["frappe/frappe", "erpnext"]
```

- [ ] **Step 3: Cài app lên site**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
./env/bin/pip install -e apps/miyano_wms
grep -qx miyano_wms sites/apps.txt || echo miyano_wms >> sites/apps.txt
bench --site erptest.local install-app miyano_wms
```

Sau khi chạy, kiểm tra patch đã chạy thật chứ không phải "hoàn thành giả":

```bash
bench --site erptest.local console <<'EOF'
import frappe
print(frappe.get_installed_apps())
EOF
```

Phải thấy `miyano_wms` trong danh sách.

- [ ] **Step 4: Viết bài test khởi động**

Tạo `apps/miyano_wms/miyano_wms/tests/__init__.py` (file rỗng) và `apps/miyano_wms/miyano_wms/tests/test_app_khoi_dong.py`:

```python
"""Bài smoke: app cài được và module Frappe tồn tại.

Bài này tồn tại để phát hiện sớm hai thứ hay hỏng khi thêm app thủ công vào
bench: app có trong installed_apps nhưng module chưa được đăng ký, và ngược
lại. Cả hai đều làm mọi doctype sau này không migrate được.
"""

import frappe
from frappe.tests.utils import FrappeTestCase


class TestAppKhoiDong(FrappeTestCase):
	def test_app_da_cai(self):
		self.assertIn("miyano_wms", frappe.get_installed_apps())

	def test_module_ton_tai(self):
		self.assertTrue(
			frappe.db.exists("Module Def", "Miyano WMS"),
			"Module 'Miyano WMS' chưa được đăng ký — kiểm tra modules.txt",
		)

	def test_erpnext_co_mat(self):
		# Toàn bộ app dựa trên Stock Ledger Entry của ERPNext.
		self.assertIn("erpnext", frappe.get_installed_apps())
```

- [ ] **Step 5: Chạy test, phải ĐỎ trước**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local run-tests --app miyano_wms --module miyano_wms.tests.test_app_khoi_dong
```

Nếu `test_module_ton_tai` đỏ: mở `apps/miyano_wms/miyano_wms/modules.txt`, sửa nội dung thành đúng một dòng `Miyano WMS`, rồi `bench --site erptest.local migrate`.

- [ ] **Step 6: Chạy lại, phải XANH**

```bash
bench --site erptest.local run-tests --app miyano_wms --module miyano_wms.tests.test_app_khoi_dong
```

Kỳ vọng: 3 bài PASS.

- [ ] **Step 7: Chuyển spec sang repo app mới**

Spec đang tạm nằm ở `miyano_portal`. Chuyển sang repo của chính app này:

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
mkdir -p apps/miyano_wms/docs/superpowers/specs apps/miyano_wms/docs/superpowers/plans
git -C apps/miyano_portal mv docs/superpowers/specs/2026-09-09-miyano-wms-vi-tri-kho-design.md /tmp/spec-wms.md 2>/dev/null || \
  mv apps/miyano_portal/docs/superpowers/specs/2026-09-09-miyano-wms-vi-tri-kho-design.md /tmp/spec-wms.md
mv apps/miyano_portal/docs/superpowers/plans/2026-09-09-miyano-wms-nen-tang-vi-tri-kho.md /tmp/plan-wms.md
mv /tmp/spec-wms.md apps/miyano_wms/docs/superpowers/specs/2026-09-09-miyano-wms-vi-tri-kho-design.md
mv /tmp/plan-wms.md apps/miyano_wms/docs/superpowers/plans/2026-09-09-miyano-wms-nen-tang-vi-tri-kho.md
git -C apps/miyano_portal add -A docs/superpowers
git -C apps/miyano_portal commit -m "docs: chuyển spec và plan vị trí kho sang repo miyano_wms"
```

Sau bước này **đường dẫn spec/plan đổi** — các task sau đọc từ `apps/miyano_wms/docs/superpowers/`.

- [ ] **Step 8: Commit**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_wms
git add -A
git commit -m "feat: dựng app miyano_wms, cài lên erptest.local

App quản lý vị trí kho (giá kệ, ô kệ) cho Miyano. Tách khỏi miyano_portal
vì miyano_portal là cổng khách hàng — mô hình phân quyền của nó dựng trên
việc không có DocPerm cho vai trò Customer, trộn kho nội bộ vào đó là mở
đường cho lỗi phân quyền."
```

---

### Task 2: Doctype `Storage Location` — cây vị trí

**Files:**
- Create: `apps/miyano_wms/miyano_wms/miyano_wms/doctype/storage_location/storage_location.json`
- Create: `apps/miyano_wms/miyano_wms/miyano_wms/doctype/storage_location/storage_location.py`
- Create: `apps/miyano_wms/miyano_wms/miyano_wms/doctype/storage_location/__init__.py`
- Test: `apps/miyano_wms/miyano_wms/tests/test_storage_location.py`

**Interfaces:**
- Consumes: app từ Task 1
- Produces: doctype `Storage Location`, `autoname = field:ma_o` (nên `name` chính là mã ô); các field `ma_o, ten_o, kho, cap_do, is_group, parent_storage_location, lft, rgt, old_parent, barcode, thu_tu_lay_hang, suc_chua, suc_chua_dvt, cho_tron_mat_hang, cho_tron_lo, la_o_tran, la_o_chua_xep, disabled`

- [ ] **Step 1: Viết bài test trước**

Tạo `apps/miyano_wms/miyano_wms/tests/test_storage_location.py`:

```python
"""Cây vị trí — ràng buộc cấu trúc.

`name` của bản ghi CHÍNH LÀ mã ô (autoname field:ma_o). Nhờ vậy mọi Link
field đọc được ngay và quét mã vạch ra thẳng bản ghi, không phải tra bảng
trung gian. Bài test đầu tiên khoá đúng điều đó lại.
"""

import frappe
from frappe.tests.utils import FrappeTestCase


def _tao_o(ma_o, **kw):
	kw.setdefault("kho", "Kho Miyano - MYN")
	kw.setdefault("cap_do", "Ô")
	doc = frappe.get_doc({"doctype": "Storage Location", "ma_o": ma_o, **kw})
	doc.insert(ignore_permissions=True)
	return doc


class TestDatTen(FrappeTestCase):
	def test_name_chinh_la_ma_o(self):
		o = _tao_o("TEST-A-01-01")
		self.assertEqual(o.name, "TEST-A-01-01")

	def test_ma_o_khong_duoc_trung(self):
		_tao_o("TEST-A-01-02")
		with self.assertRaises(frappe.DuplicateEntryError):
			_tao_o("TEST-A-01-02")


class TestRangBuocKho(FrappeTestCase):
	def test_o_la_bat_buoc_co_kho(self):
		doc = frappe.get_doc({"doctype": "Storage Location", "ma_o": "TEST-NO-KHO", "cap_do": "Ô"})
		with self.assertRaises(frappe.ValidationError):
			doc.insert(ignore_permissions=True)

	def test_khong_nhan_warehouse_nhom(self):
		with self.assertRaises(frappe.ValidationError) as ctx:
			_tao_o("TEST-NHOM", kho="All Warehouses - MYN")
		self.assertIn("kho tổng", str(ctx.exception).lower())


class TestCayViTri(FrappeTestCase):
	def test_o_con_thua_ke_duoc_cay(self):
		cha = _tao_o("TEST-KHU-A", cap_do="Khu", is_group=1)
		con = _tao_o("TEST-KHU-A-01", parent_storage_location=cha.name)
		con.reload()
		self.assertEqual(con.parent_storage_location, "TEST-KHU-A")
		cha.reload()
		self.assertLess(cha.lft, con.lft)
		self.assertGreater(cha.rgt, con.rgt)
```

- [ ] **Step 2: Chạy test, phải ĐỎ**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local run-tests --app miyano_wms --module miyano_wms.tests.test_storage_location
```

Kỳ vọng: FAIL — `DoesNotExistError: DocType Storage Location not found`.

- [ ] **Step 3: Tạo doctype JSON**

`apps/miyano_wms/miyano_wms/miyano_wms/doctype/storage_location/storage_location.json`:

```json
{
 "actions": [],
 "allow_rename": 0,
 "autoname": "field:ma_o",
 "creation": "2026-09-09 00:00:00.000000",
 "doctype": "DocType",
 "engine": "InnoDB",
 "is_tree": 1,
 "nsm_parent_field": "parent_storage_location",
 "field_order": [
  "ma_o", "ten_o", "kho", "cap_do", "col_1", "is_group",
  "parent_storage_location", "disabled",
  "sec_lay_hang", "barcode", "thu_tu_lay_hang", "col_2", "la_o_tran", "la_o_chua_xep",
  "sec_suc_chua", "suc_chua", "suc_chua_dvt", "col_3", "cho_tron_mat_hang", "cho_tron_lo",
  "lft", "rgt", "old_parent"
 ],
 "fields": [
  {"fieldname": "ma_o", "fieldtype": "Data", "label": "Mã ô", "reqd": 1, "unique": 1, "in_list_view": 1, "description": "Mã dán lên kệ và dùng để quét, ví dụ A-01-02"},
  {"fieldname": "ten_o", "fieldtype": "Data", "label": "Tên mô tả", "in_list_view": 1},
  {"fieldname": "kho", "fieldtype": "Link", "label": "Kho", "options": "Warehouse", "in_list_view": 1, "search_index": 1},
  {"fieldname": "cap_do", "fieldtype": "Select", "label": "Cấp độ", "options": "Khu\nDãy\nKệ\nTầng\nÔ", "default": "Ô", "reqd": 1},
  {"fieldname": "col_1", "fieldtype": "Column Break"},
  {"fieldname": "is_group", "fieldtype": "Check", "label": "Là nhóm", "default": "0"},
  {"fieldname": "parent_storage_location", "fieldtype": "Link", "label": "Thuộc về", "options": "Storage Location", "search_index": 1},
  {"fieldname": "disabled", "fieldtype": "Check", "label": "Ngừng dùng", "default": "0"},
  {"fieldname": "sec_lay_hang", "fieldtype": "Section Break", "label": "Lấy hàng"},
  {"fieldname": "barcode", "fieldtype": "Data", "label": "Mã vạch", "description": "Để trống thì lấy bằng Mã ô"},
  {"fieldname": "thu_tu_lay_hang", "fieldtype": "Int", "label": "Thứ tự lấy hàng", "default": "0", "description": "Thứ tự đường đi trong kho. Số nhỏ đi trước."},
  {"fieldname": "col_2", "fieldtype": "Column Break"},
  {"fieldname": "la_o_tran", "fieldtype": "Check", "label": "Là ô tràn", "default": "0", "description": "Ô tràn được ưu tiên thấp khi gợi ý đặt hàng"},
  {"fieldname": "la_o_chua_xep", "fieldtype": "Check", "label": "Là ô \"Chưa xếp vị trí\"", "default": "0", "read_only": 1, "description": "Ô hệ thống. Mỗi kho đúng một ô. Do chức năng bật quản lý vị trí tạo ra, không tạo tay."},
  {"fieldname": "sec_suc_chua", "fieldtype": "Section Break", "label": "Sức chứa"},
  {"fieldname": "suc_chua", "fieldtype": "Float", "label": "Sức chứa"},
  {"fieldname": "suc_chua_dvt", "fieldtype": "Link", "label": "Đơn vị sức chứa", "options": "UOM"},
  {"fieldname": "col_3", "fieldtype": "Column Break"},
  {"fieldname": "cho_tron_mat_hang", "fieldtype": "Check", "label": "Cho trộn nhiều mặt hàng", "default": "1"},
  {"fieldname": "cho_tron_lo", "fieldtype": "Check", "label": "Cho trộn nhiều lô", "default": "1"},
  {"fieldname": "lft", "fieldtype": "Int", "label": "lft", "hidden": 1, "read_only": 1, "no_copy": 1},
  {"fieldname": "rgt", "fieldtype": "Int", "label": "rgt", "hidden": 1, "read_only": 1, "no_copy": 1},
  {"fieldname": "old_parent", "fieldtype": "Data", "label": "old_parent", "hidden": 1, "read_only": 1, "no_copy": 1}
 ],
 "index_web_pages_for_search": 0,
 "links": [],
 "modified": "2026-09-09 00:00:00.000000",
 "modified_by": "Administrator",
 "module": "Miyano WMS",
 "name": "Storage Location",
 "owner": "Administrator",
 "permissions": [
  {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "report": 1, "export": 1},
  {"role": "Stock Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "report": 1, "export": 1},
  {"role": "Stock User", "read": 1, "report": 1}
 ],
 "sort_field": "modified",
 "sort_order": "DESC",
 "states": [],
 "track_changes": 1
}
```

- [ ] **Step 4: Viết controller**

`apps/miyano_wms/miyano_wms/miyano_wms/doctype/storage_location/__init__.py` — file rỗng.

`apps/miyano_wms/miyano_wms/miyano_wms/doctype/storage_location/storage_location.py`:

```python
import frappe
from frappe import _
from frappe.utils.nestedset import NestedSet


class StorageLocation(NestedSet):
	nsm_parent_field = "parent_storage_location"

	def validate(self):
		self.kiem_tra_kho()
		if not self.barcode:
			self.barcode = self.ma_o

	def kiem_tra_kho(self):
		if self.is_group:
			# Nút cây (Khu, Dãy) có thể không gắn kho cụ thể.
			return

		if not self.kho:
			frappe.throw(_("Ô {0} phải chọn kho.").format(self.ma_o))

		if frappe.db.get_value("Warehouse", self.kho, "is_group"):
			frappe.throw(
				_("{0} là kho tổng, không chứa hàng thật nên không đặt ô kệ vào đó được. "
				  "Chọn một kho cụ thể.").format(self.kho)
			)
```

- [ ] **Step 5: Migrate rồi chạy lại test**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local migrate
bench --site erptest.local run-tests --app miyano_wms --module miyano_wms.tests.test_storage_location
```

Kỳ vọng: 5 bài PASS.

- [ ] **Step 6: Commit**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_wms
git add -A
git commit -m "feat(vitri): doctype Storage Location — cây vị trí kho

autoname field:ma_o nên name chính là mã ô: Link field đọc được ngay và
quét mã vạch ra thẳng bản ghi. Chặn đặt ô vào kho tổng (is_group) vì kho
tổng không chứa hàng thật."
```

---

### Task 3: Bật/tắt ở cấp Warehouse — custom field và hàm hỏi trạng thái

**Files:**
- Create: `apps/miyano_wms/miyano_wms/patches.txt`
- Create: `apps/miyano_wms/miyano_wms/patches/__init__.py`, `apps/miyano_wms/miyano_wms/patches/v1_0/__init__.py`
- Create: `apps/miyano_wms/miyano_wms/patches/v1_0/them_co_quan_ly_vi_tri.py`
- Create: `apps/miyano_wms/miyano_wms/vitri/__init__.py`
- Create: `apps/miyano_wms/miyano_wms/vitri/kho.py`
- Test: `apps/miyano_wms/miyano_wms/tests/test_co_quan_ly_vi_tri.py`

**Interfaces:**
- Consumes: `Storage Location` (Task 2)
- Produces:
  - `Warehouse.custom_quan_ly_vi_tri` (Check, **read_only**)
  - `miyano_wms.vitri.kho.kho_co_quan_ly_vi_tri(kho: str) -> bool`
  - `miyano_wms.vitri.kho.o_chua_xep(kho: str) -> str | None` — trả `name` của ô `CHUA-XEP`
  - `miyano_wms.vitri.kho.xoa_cache_kho(kho: str) -> None`

- [ ] **Step 1: Viết bài test trước**

`apps/miyano_wms/miyano_wms/tests/test_co_quan_ly_vi_tri.py`:

```python
"""Cờ bật quản lý vị trí ở cấp kho.

Hai điều bài này khoá lại:

1. Cờ là READ-ONLY. Bật quản lý vị trí không phải tích một ô — nó phải tạo
   ô CHUA-XEP, chuyển đổi tồn hiện có tách theo từng lô, rồi đối soát. Ai
   tích tay vào cờ là bỏ qua sạch các bước đó và hệ sai ngay từ giây đầu.
   Chỉ Warehouse Location Setup (Task 11-13) được đặt.

2. Hàm hỏi trạng thái đọc qua CACHE. Hook chạy trên MỌI dòng SLE nên không
   thể truy vấn DB mỗi lần. Hệ quả: bật/tắt phải xoá cache, nếu không thao
   tác bật sẽ không có hiệu lực và người vận hành tưởng chức năng hỏng.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_wms.vitri import kho as vk

KHO = "Kho Miyano - MYN"


class TestCustomField(FrappeTestCase):
	def test_field_ton_tai(self):
		self.assertTrue(frappe.db.exists("Custom Field", {"dt": "Warehouse", "fieldname": "custom_quan_ly_vi_tri"}))

	def test_field_la_read_only(self):
		ro = frappe.db.get_value(
			"Custom Field", {"dt": "Warehouse", "fieldname": "custom_quan_ly_vi_tri"}, "read_only"
		)
		self.assertEqual(ro, 1, "Cờ phải read-only — xem docstring đầu file")


class TestHoiTrangThai(FrappeTestCase):
	def tearDown(self):
		frappe.db.set_value("Warehouse", KHO, "custom_quan_ly_vi_tri", 0)
		vk.xoa_cache_kho(KHO)

	def test_kho_chua_bat_tra_false(self):
		frappe.db.set_value("Warehouse", KHO, "custom_quan_ly_vi_tri", 0)
		vk.xoa_cache_kho(KHO)
		self.assertFalse(vk.kho_co_quan_ly_vi_tri(KHO))

	def test_kho_da_bat_tra_true(self):
		frappe.db.set_value("Warehouse", KHO, "custom_quan_ly_vi_tri", 1)
		vk.xoa_cache_kho(KHO)
		self.assertTrue(vk.kho_co_quan_ly_vi_tri(KHO))

	def test_khong_xoa_cache_thi_doc_ra_gia_tri_cu(self):
		# Bài này KHÔNG kiểm tra một tính năng — nó ghi lại cái bẫy.
		frappe.db.set_value("Warehouse", KHO, "custom_quan_ly_vi_tri", 0)
		vk.xoa_cache_kho(KHO)
		self.assertFalse(vk.kho_co_quan_ly_vi_tri(KHO))
		frappe.db.set_value("Warehouse", KHO, "custom_quan_ly_vi_tri", 1)
		# cố tình KHÔNG xoá cache
		self.assertFalse(vk.kho_co_quan_ly_vi_tri(KHO), "get_cached_value vẫn trả giá trị cũ")
		vk.xoa_cache_kho(KHO)
		self.assertTrue(vk.kho_co_quan_ly_vi_tri(KHO))

	def test_kho_khong_ton_tai_tra_false(self):
		self.assertFalse(vk.kho_co_quan_ly_vi_tri("Kho Không Có Thật - XX"))


class TestOChuaXep(FrappeTestCase):
	def test_kho_chua_co_o_chua_xep_tra_none(self):
		self.assertIsNone(vk.o_chua_xep("Stores - MYN"))
```

- [ ] **Step 2: Chạy test, phải ĐỎ**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local run-tests --app miyano_wms --module miyano_wms.tests.test_co_quan_ly_vi_tri
```

Kỳ vọng: FAIL — `ModuleNotFoundError: No module named 'miyano_wms.vitri'`.

- [ ] **Step 3: Viết patch thêm custom field**

`apps/miyano_wms/miyano_wms/patches.txt`:

```
[post_model_sync]
miyano_wms.patches.v1_0.them_co_quan_ly_vi_tri
```

`apps/miyano_wms/miyano_wms/patches/__init__.py` và `apps/miyano_wms/miyano_wms/patches/v1_0/__init__.py` — file rỗng.

`apps/miyano_wms/miyano_wms/patches/v1_0/them_co_quan_ly_vi_tri.py`:

```python
"""Thêm `Warehouse.custom_quan_ly_vi_tri` (spec §5.9).

READ-ONLY có chủ đích. Bật quản lý vị trí là một quy trình chuyển đổi dữ
liệu (tạo ô CHUA-XEP, đọc tồn hiện có tách theo lô, ghi sổ, đối soát), không
phải một cái công tắc. Để field sửa được là mở đường tắt bỏ qua toàn bộ quy
trình đó — và hệ sẽ sai từ giây đầu tiên mà không ai biết. Chỉ doctype
`Warehouse Location Setup` được đặt giá trị này.
"""

from frappe.custom.doctype.custom_field.custom_field import create_custom_field


def execute():
	create_custom_field("Warehouse", {
		"fieldname": "custom_quan_ly_vi_tri",
		"label": "Quản lý theo vị trí",
		"fieldtype": "Check",
		"default": "0",
		"read_only": 1,
		"search_index": 1,
		"insert_after": "warehouse_type",
		"description": "Chỉ đặt qua 'Warehouse Location Setup'. Không sửa tay.",
	})
```

- [ ] **Step 4: Viết `vitri/kho.py`**

`apps/miyano_wms/miyano_wms/vitri/__init__.py` — file rỗng.

`apps/miyano_wms/miyano_wms/vitri/kho.py`:

```python
"""Hỏi trạng thái quản lý vị trí của một kho.

Hook ghi sổ chạy trên MỌI dòng Stock Ledger Entry của toàn hệ, kể cả các kho
không bật. Nên câu hỏi "kho này có bật không" phải rẻ — đọc cache, không
truy vấn DB. Đổi lại: mọi chỗ đổi cờ đều PHẢI gọi `xoa_cache_kho()`.
"""

import frappe

MA_O_CHUA_XEP = "CHUA-XEP"


def kho_co_quan_ly_vi_tri(kho: str) -> bool:
	"""Kho này có bật quản lý vị trí không. Kho không tồn tại → False."""
	if not kho:
		return False
	try:
		return bool(frappe.get_cached_value("Warehouse", kho, "custom_quan_ly_vi_tri"))
	except frappe.DoesNotExistError:
		return False


def xoa_cache_kho(kho: str) -> None:
	"""Xoá cache Warehouse. Bắt buộc gọi sau mỗi lần đổi cờ."""
	frappe.clear_cache(doctype="Warehouse")
	frappe.clear_document_cache("Warehouse", kho)


def ma_o_chua_xep(kho: str) -> str:
	"""Mã ô CHUA-XEP của một kho. Kèm tên kho để không trùng giữa các kho."""
	return f"{MA_O_CHUA_XEP}-{kho}"


def o_chua_xep(kho: str) -> str | None:
	"""Tên bản ghi ô CHUA-XEP của kho, hoặc None nếu kho chưa bật."""
	ten = ma_o_chua_xep(kho)
	return ten if frappe.db.exists("Storage Location", ten) else None
```

- [ ] **Step 5: Chạy patch rồi chạy lại test**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local migrate
bench --site erptest.local run-tests --app miyano_wms --module miyano_wms.tests.test_co_quan_ly_vi_tri
```

Kỳ vọng: 7 bài PASS.

- [ ] **Step 6: Xác nhận patch chạy thật, không phải hoàn thành giả**

`install-app` có thể đánh dấu patch là xong mà chưa chạy. Kiểm tra bằng dấu vết thời gian:

```bash
bench --site erptest.local console <<'EOF'
import frappe
print(frappe.db.get_value("Patch Log",
    {"patch": ("like", "%them_co_quan_ly_vi_tri%")}, ["patch", "creation"]))
print(frappe.db.get_value("Custom Field",
    {"dt": "Warehouse", "fieldname": "custom_quan_ly_vi_tri"}, ["name", "read_only", "creation"]))
EOF
```

Cả hai phải có giá trị, và `creation` của Custom Field phải gần thời điểm chạy migrate. Nếu Patch Log có mà Custom Field không có → patch bị đánh dấu xong mà chưa chạy; xoá dòng Patch Log rồi migrate lại.

- [ ] **Step 7: Commit**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_wms
git add -A
git commit -m "feat(vitri): cờ quản lý vị trí ở cấp kho, đọc qua cache

custom_quan_ly_vi_tri là READ-ONLY: bật quản lý vị trí là quy trình chuyển
đổi dữ liệu chứ không phải công tắc, để sửa tay được là mở đường tắt bỏ qua
toàn bộ quy trình. Hàm hỏi trạng thái đọc get_cached_value vì hook chạy trên
mọi dòng SLE của toàn hệ — kèm test ghi lại cái bẫy quên xoá cache."
```

---

### Task 4: Sổ vị trí và tồn vị trí — hai doctype cùng engine ghi sổ

**Files:**
- Create: `apps/miyano_wms/miyano_wms/miyano_wms/doctype/location_ledger_entry/{__init__.py,location_ledger_entry.json,location_ledger_entry.py}`
- Create: `apps/miyano_wms/miyano_wms/miyano_wms/doctype/location_balance/{__init__.py,location_balance.json,location_balance.py}`
- Create: `apps/miyano_wms/miyano_wms/vitri/so.py`
- Test: `apps/miyano_wms/miyano_wms/tests/test_so_vi_tri.py`

**Interfaces:**
- Consumes: `Storage Location` (Task 2)
- Produces:
  - `miyano_wms.vitri.so.ghi_dong_so(o, kho, vat_tu, so_lo, so_luong, chung_tu_type, chung_tu, chung_tu_row, sle, ngay, thoi_diem, company, da_huy=0) -> str`
  - `miyano_wms.vitri.so.ton_o(o, vat_tu, so_lo) -> float`
  - `miyano_wms.vitri.so.tong_ton_vi_tri(kho, vat_tu, so_lo) -> float`
  - `miyano_wms.vitri.so.dung_lai_ton_vi_tri(kho=None) -> int` (trả số dòng `Location Balance` đã dựng)

- [ ] **Step 1: Viết bài test trước**

`apps/miyano_wms/miyano_wms/tests/test_so_vi_tri.py`:

```python
"""Engine ghi sổ vị trí.

Sổ CHỈ GHI THÊM. Không sửa dòng, không xoá dòng — kể cả khi huỷ chứng từ
(huỷ ghi bút toán đảo, xem Task 9). `Location Balance` chỉ là bộ đệm, dựng
lại được từ sổ bất cứ lúc nào; đó là đường thoát khi nghi ngờ số liệu, nên
`dung_lai_ton_vi_tri()` phải có test riêng chứ không được coi là hàm phụ.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_wms.vitri import so

KHO = "Kho Miyano - MYN"


def _o(ma_o):
	if not frappe.db.exists("Storage Location", ma_o):
		frappe.get_doc({
			"doctype": "Storage Location", "ma_o": ma_o, "kho": KHO, "cap_do": "Ô",
		}).insert(ignore_permissions=True)
	return ma_o


def _ghi(o, vat_tu, so_lo, so_luong, chung_tu="TEST-CT-1"):
	return so.ghi_dong_so(
		o=o, kho=KHO, vat_tu=vat_tu, so_lo=so_lo, so_luong=so_luong,
		chung_tu_type="Stock Entry", chung_tu=chung_tu, chung_tu_row="row-1",
		sle=None, ngay="2026-09-09", thoi_diem="2026-09-09 08:00:00",
		company="Miyano Việt Nam",
	)


class TestGhiSo(FrappeTestCase):
	def test_ghi_mot_dong_thi_ton_o_tang(self):
		o = _o("TEST-SO-01")
		_ghi(o, "_Test Item VT", "LO-A", 10)
		self.assertEqual(so.ton_o(o, "_Test Item VT", "LO-A"), 10)

	def test_ghi_am_thi_ton_giam(self):
		o = _o("TEST-SO-02")
		_ghi(o, "_Test Item VT", "LO-A", 10)
		_ghi(o, "_Test Item VT", "LO-A", -4)
		self.assertEqual(so.ton_o(o, "_Test Item VT", "LO-A"), 6)

	def test_hai_lo_khac_nhau_khong_gop_lam_mot(self):
		o = _o("TEST-SO-03")
		_ghi(o, "_Test Item VT", "LO-A", 10)
		_ghi(o, "_Test Item VT", "LO-B", 5)
		self.assertEqual(so.ton_o(o, "_Test Item VT", "LO-A"), 10)
		self.assertEqual(so.ton_o(o, "_Test Item VT", "LO-B"), 5)
		self.assertEqual(so.tong_ton_vi_tri(KHO, "_Test Item VT", "LO-A"), 10)

	def test_hang_khong_lo_dung_so_lo_rong(self):
		o = _o("TEST-SO-04")
		_ghi(o, "_Test Item Khong Lo", None, 7)
		self.assertEqual(so.ton_o(o, "_Test Item Khong Lo", None), 7)

	def test_tong_ton_cong_qua_nhieu_o(self):
		a, b = _o("TEST-SO-05A"), _o("TEST-SO-05B")
		_ghi(a, "_Test Item VT2", "LO-C", 3)
		_ghi(b, "_Test Item VT2", "LO-C", 4)
		self.assertEqual(so.tong_ton_vi_tri(KHO, "_Test Item VT2", "LO-C"), 7)


class TestSoChiGhiThem(FrappeTestCase):
	def test_ghi_khong_sua_dong_cu(self):
		o = _o("TEST-SO-06")
		t1 = _ghi(o, "_Test Item VT3", "LO-D", 5)
		_ghi(o, "_Test Item VT3", "LO-D", -2)
		self.assertEqual(frappe.db.get_value("Location Ledger Entry", t1, "so_luong"), 5)
		self.assertEqual(
			frappe.db.count("Location Ledger Entry", {"o": o, "vat_tu": "_Test Item VT3"}), 2
		)


class TestDungLaiTon(FrappeTestCase):
	def test_pha_bo_dem_roi_dung_lai_thi_dung(self):
		o = _o("TEST-SO-07")
		_ghi(o, "_Test Item VT4", "LO-E", 12)
		_ghi(o, "_Test Item VT4", "LO-E", -5)

		# cố tình phá bộ đệm
		frappe.db.set_value(
			"Location Balance",
			{"o": o, "vat_tu": "_Test Item VT4", "so_lo": "LO-E"},
			"so_luong", 999,
		)
		self.assertEqual(so.ton_o(o, "_Test Item VT4", "LO-E"), 999)

		so.dung_lai_ton_vi_tri(KHO)
		self.assertEqual(so.ton_o(o, "_Test Item VT4", "LO-E"), 7)

	def test_dung_lai_khong_de_lai_dong_thua(self):
		o = _o("TEST-SO-08")
		_ghi(o, "_Test Item VT5", "LO-F", 4)
		frappe.get_doc({
			"doctype": "Location Balance", "o": o, "kho": KHO,
			"vat_tu": "_Test Item VT5", "so_lo": "LO-MA", "so_luong": 100,
		}).insert(ignore_permissions=True)

		so.dung_lai_ton_vi_tri(KHO)
		self.assertFalse(
			frappe.db.exists("Location Balance", {"o": o, "so_lo": "LO-MA"}),
			"dòng tồn không có dấu vết trong sổ phải bị xoá khi dựng lại",
		)
```

- [ ] **Step 2: Chạy test, phải ĐỎ**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local run-tests --app miyano_wms --module miyano_wms.tests.test_so_vi_tri
```

Kỳ vọng: FAIL — `ModuleNotFoundError: No module named 'miyano_wms.vitri.so'`.

- [ ] **Step 3: Tạo doctype `Location Ledger Entry`**

`.../doctype/location_ledger_entry/location_ledger_entry.json`:

```json
{
 "actions": [],
 "allow_rename": 0,
 "autoname": "hash",
 "creation": "2026-09-09 00:00:00.000000",
 "doctype": "DocType",
 "engine": "InnoDB",
 "field_order": [
  "ngay", "thoi_diem", "kho", "o", "col_1", "vat_tu", "so_lo", "so_luong",
  "sec_ct", "chung_tu_type", "chung_tu", "chung_tu_row", "col_2", "sle", "da_huy", "company"
 ],
 "fields": [
  {"fieldname": "ngay", "fieldtype": "Date", "label": "Ngày", "reqd": 1, "in_list_view": 1},
  {"fieldname": "thoi_diem", "fieldtype": "Datetime", "label": "Thời điểm", "reqd": 1, "search_index": 1},
  {"fieldname": "kho", "fieldtype": "Link", "label": "Kho", "options": "Warehouse", "reqd": 1, "search_index": 1},
  {"fieldname": "o", "fieldtype": "Link", "label": "Ô", "options": "Storage Location", "reqd": 1, "search_index": 1, "in_list_view": 1},
  {"fieldname": "col_1", "fieldtype": "Column Break"},
  {"fieldname": "vat_tu", "fieldtype": "Link", "label": "Mặt hàng", "options": "Item", "reqd": 1, "search_index": 1, "in_list_view": 1},
  {"fieldname": "so_lo", "fieldtype": "Link", "label": "Số lô", "options": "Batch", "search_index": 1, "in_list_view": 1, "description": "Để trống với hàng không quản lý lô"},
  {"fieldname": "so_luong", "fieldtype": "Float", "label": "Số lượng", "reqd": 1, "in_list_view": 1, "description": "Có dấu: nhập là dương, xuất là âm"},
  {"fieldname": "sec_ct", "fieldtype": "Section Break", "label": "Chứng từ nguồn"},
  {"fieldname": "chung_tu_type", "fieldtype": "Link", "label": "Loại chứng từ", "options": "DocType", "search_index": 1},
  {"fieldname": "chung_tu", "fieldtype": "Dynamic Link", "label": "Chứng từ", "options": "chung_tu_type", "search_index": 1},
  {"fieldname": "chung_tu_row", "fieldtype": "Data", "label": "Dòng chứng từ", "search_index": 1, "description": "voucher_detail_no — khoá để đảo đúng ô gốc khi huỷ"},
  {"fieldname": "col_2", "fieldtype": "Column Break"},
  {"fieldname": "sle", "fieldtype": "Link", "label": "Dòng sổ kho ERPNext", "options": "Stock Ledger Entry", "search_index": 1},
  {"fieldname": "da_huy", "fieldtype": "Check", "label": "Đã đảo", "default": "0"},
  {"fieldname": "company", "fieldtype": "Link", "label": "Công ty", "options": "Company"}
 ],
 "index_web_pages_for_search": 0,
 "links": [],
 "modified": "2026-09-09 00:00:00.000000",
 "modified_by": "Administrator",
 "module": "Miyano WMS",
 "name": "Location Ledger Entry",
 "owner": "Administrator",
 "permissions": [
  {"role": "System Manager", "read": 1, "report": 1, "export": 1},
  {"role": "Stock Manager", "read": 1, "report": 1, "export": 1},
  {"role": "Stock User", "read": 1, "report": 1}
 ],
 "sort_field": "creation",
 "sort_order": "DESC",
 "states": [],
 "track_changes": 0
}
```

Chú ý: **không vai trò nào có `create`, `write`, `delete`.** Chỉ engine ghi qua `ignore_permissions`. Đây là điều giữ cho sổ đáng tin.

`.../location_ledger_entry.py`:

```python
import frappe
from frappe import _
from frappe.model.document import Document


class LocationLedgerEntry(Document):
	def on_trash(self):
		frappe.throw(_("Không xoá được dòng sổ vị trí. Sổ chỉ ghi thêm; huỷ chứng từ sẽ ghi bút toán đảo."))
```

- [ ] **Step 4: Tạo doctype `Location Balance`**

`.../doctype/location_balance/location_balance.json`:

```json
{
 "actions": [],
 "allow_rename": 0,
 "autoname": "hash",
 "creation": "2026-09-09 00:00:00.000000",
 "doctype": "DocType",
 "engine": "InnoDB",
 "field_order": ["o", "kho", "vat_tu", "so_lo", "so_luong", "cap_nhat_luc"],
 "fields": [
  {"fieldname": "o", "fieldtype": "Link", "label": "Ô", "options": "Storage Location", "reqd": 1, "search_index": 1, "in_list_view": 1},
  {"fieldname": "kho", "fieldtype": "Link", "label": "Kho", "options": "Warehouse", "reqd": 1, "search_index": 1},
  {"fieldname": "vat_tu", "fieldtype": "Link", "label": "Mặt hàng", "options": "Item", "reqd": 1, "search_index": 1, "in_list_view": 1},
  {"fieldname": "so_lo", "fieldtype": "Link", "label": "Số lô", "options": "Batch", "search_index": 1, "in_list_view": 1},
  {"fieldname": "so_luong", "fieldtype": "Float", "label": "Số lượng", "in_list_view": 1},
  {"fieldname": "cap_nhat_luc", "fieldtype": "Datetime", "label": "Cập nhật lúc", "read_only": 1}
 ],
 "index_web_pages_for_search": 0,
 "links": [],
 "modified": "2026-09-09 00:00:00.000000",
 "modified_by": "Administrator",
 "module": "Miyano WMS",
 "name": "Location Balance",
 "owner": "Administrator",
 "permissions": [
  {"role": "System Manager", "read": 1, "report": 1, "export": 1},
  {"role": "Stock Manager", "read": 1, "report": 1, "export": 1},
  {"role": "Stock User", "read": 1, "report": 1}
 ],
 "sort_field": "modified",
 "sort_order": "DESC",
 "states": [],
 "track_changes": 0
}
```

`.../location_balance.py`:

```python
from frappe.model.document import Document


class LocationBalance(Document):
	pass
```

- [ ] **Step 5: Viết engine `vitri/so.py`**

```python
"""Engine ghi sổ vị trí.

`Location Ledger Entry` là nguồn sự thật, chỉ ghi thêm. `Location Balance`
là bộ đệm dẫn xuất — mọi con số trong đó phải dựng lại được từ sổ, và
`dung_lai_ton_vi_tri()` là đường thoát khi nghi ngờ số liệu.

Không hàm nào ở đây kiểm tra tồn đủ hay không. Việc chặn nằm ở lớp trên
(hook và validate chứng từ) vì chỉ ở đó mới đủ ngữ cảnh để báo lỗi cho
người dùng đọc được.
"""

import frappe
from frappe.utils import flt, now_datetime


def _khoa_ton(o, vat_tu, so_lo):
	return {"o": o, "vat_tu": vat_tu, "so_lo": so_lo or ""}


def ghi_dong_so(
	o, kho, vat_tu, so_lo, so_luong,
	chung_tu_type, chung_tu, chung_tu_row, sle,
	ngay, thoi_diem, company, da_huy=0,
) -> str:
	"""Ghi một dòng sổ vị trí và cập nhật bộ đệm tồn. Trả tên dòng sổ."""
	dong = frappe.get_doc({
		"doctype": "Location Ledger Entry",
		"ngay": ngay,
		"thoi_diem": thoi_diem,
		"kho": kho,
		"o": o,
		"vat_tu": vat_tu,
		"so_lo": so_lo or None,
		"so_luong": flt(so_luong),
		"chung_tu_type": chung_tu_type,
		"chung_tu": chung_tu,
		"chung_tu_row": chung_tu_row,
		"sle": sle,
		"da_huy": da_huy,
		"company": company,
	})
	dong.insert(ignore_permissions=True)
	_cong_don_ton(o, kho, vat_tu, so_lo, flt(so_luong))
	return dong.name


def _cong_don_ton(o, kho, vat_tu, so_lo, delta):
	ten = frappe.db.get_value("Location Balance", _khoa_ton(o, vat_tu, so_lo), "name")
	if ten:
		cu = flt(frappe.db.get_value("Location Balance", ten, "so_luong"))
		frappe.db.set_value("Location Balance", ten, {
			"so_luong": cu + delta,
			"cap_nhat_luc": now_datetime(),
		}, update_modified=False)
	else:
		frappe.get_doc({
			"doctype": "Location Balance",
			"o": o, "kho": kho, "vat_tu": vat_tu, "so_lo": so_lo or None,
			"so_luong": delta, "cap_nhat_luc": now_datetime(),
		}).insert(ignore_permissions=True)


def ton_o(o, vat_tu, so_lo) -> float:
	"""Tồn của một (ô, mặt hàng, lô). Đọc bộ đệm."""
	return flt(frappe.db.get_value("Location Balance", _khoa_ton(o, vat_tu, so_lo), "so_luong"))


def tong_ton_vi_tri(kho, vat_tu, so_lo) -> float:
	"""Tổng tồn của một (mặt hàng, lô) trên TẤT CẢ các ô của kho.

	Theo bất biến ở spec §3, con số này phải bằng Bin.actual_qty.
	"""
	ket_qua = frappe.db.sql(
		"""select sum(so_luong) from `tabLocation Balance`
		   where kho=%s and vat_tu=%s and ifnull(so_lo,'')=%s""",
		(kho, vat_tu, so_lo or ""),
	)
	return flt(ket_qua[0][0] or 0)


def dung_lai_ton_vi_tri(kho=None) -> int:
	"""Dựng lại toàn bộ Location Balance từ sổ. Trả số dòng đã dựng.

	Xoá sạch bộ đệm cũ của phạm vi rồi cộng lại từ đầu — dòng tồn không có
	dấu vết trong sổ sẽ biến mất, đó là điểm mấu chốt.
	"""
	dk_kho = "where kho=%s" if kho else ""
	tham_so = (kho,) if kho else ()

	frappe.db.sql(f"delete from `tabLocation Balance` {dk_kho}", tham_so)

	dong = frappe.db.sql(
		f"""select o, kho, vat_tu, ifnull(so_lo,'') as so_lo, sum(so_luong) as sl
		    from `tabLocation Ledger Entry` {dk_kho}
		    group by o, kho, vat_tu, ifnull(so_lo,'')""",
		tham_so, as_dict=True,
	)

	luc = now_datetime()
	for d in dong:
		frappe.get_doc({
			"doctype": "Location Balance",
			"o": d.o, "kho": d.kho, "vat_tu": d.vat_tu,
			"so_lo": d.so_lo or None, "so_luong": flt(d.sl), "cap_nhat_luc": luc,
		}).insert(ignore_permissions=True)

	return len(dong)
```

- [ ] **Step 6: Migrate rồi chạy lại test**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local migrate
bench --site erptest.local run-tests --app miyano_wms --module miyano_wms.tests.test_so_vi_tri
```

Kỳ vọng: 9 bài PASS. Nếu đỏ vì thiếu `_Test Item VT`, để `FrappeTestCase` tự tạo bằng cách thêm ở đầu file test:

```python
def _tao_item(ma):
	if not frappe.db.exists("Item", ma):
		frappe.get_doc({
			"doctype": "Item", "item_code": ma, "item_name": ma,
			"item_group": "All Item Groups", "stock_uom": "Nos", "is_stock_item": 1,
		}).insert(ignore_permissions=True)
	return ma
```

rồi gọi `_tao_item(...)` trong `setUp` của từng lớp.

- [ ] **Step 7: Commit**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_wms
git add -A
git commit -m "feat(vitri): sổ vị trí chỉ-ghi-thêm và bộ đệm tồn dựng lại được

Location Ledger Entry là nguồn sự thật, không vai trò nào có quyền
create/write/delete — chỉ engine ghi qua ignore_permissions, và on_trash
chặn xoá. Location Balance là bộ đệm; dung_lai_ton_vi_tri() xoá sạch rồi
cộng lại từ sổ nên dòng tồn không có dấu vết trong sổ sẽ biến mất."
```

---

### Task 5: `tach_theo_lo()` — lấy số lô từ Serial and Batch Bundle

**Files:**
- Create: `apps/miyano_wms/miyano_wms/vitri/lo.py`
- Test: `apps/miyano_wms/miyano_wms/tests/test_tach_theo_lo.py`

**Interfaces:**
- Consumes: không có (hàm thuần, nhận doc SLE)
- Produces: `miyano_wms.vitri.lo.tach_theo_lo(sle, delta: float) -> list[dict]` — mỗi phần tử `{"so_lo": str | None, "so_luong": float}`, tổng `so_luong` bằng `delta`

**Vì sao task riêng:** đây là điểm rủi ro cao nhất của cả app. Đọc sai chỗ này thì 80/164 mặt hàng mất chiều lô, **mà báo cáo đối soát vẫn báo khớp** vì tổng số lượng vẫn đúng — không có lưới nào bắt được ngoài bài test này.

- [ ] **Step 1: Xác minh lại trên dữ liệu thật trước khi viết**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/sites
../env/bin/python -c "
import frappe
frappe.init(site='erptest.local', sites_path='.'); frappe.connect()
print('SLE hàng có lô mang batch_no :', frappe.db.sql('''select count(*) from \`tabStock Ledger Entry\` sle
    join tabItem i on i.name=sle.item_code where i.has_batch_no=1 and ifnull(sle.batch_no,\"\")!=\"\"''')[0][0])
print('SLE hàng có lô mang bundle   :', frappe.db.sql('''select count(*) from \`tabStock Ledger Entry\` sle
    join tabItem i on i.name=sle.item_code where i.has_batch_no=1 and ifnull(sle.serial_and_batch_bundle,\"\")!=\"\"''')[0][0])
"
```

Kỳ vọng: cột `batch_no` bằng **0**, cột bundle **lớn hơn 0**. Nếu kết quả ngược lại thì phiên bản ERPNext đã đổi — **dừng lại và báo**, đừng viết tiếp theo giả định cũ.

- [ ] **Step 2: Viết bài test trước**

`apps/miyano_wms/miyano_wms/tests/test_tach_theo_lo.py`:

```python
"""Lấy số lô từ Serial and Batch Bundle, KHÔNG từ sle.batch_no.

ERPNext v15 không ghi batch_no lên Stock Ledger Entry nữa (field còn đó
nhưng bỏ không); số lô nằm ở các dòng con Serial and Batch Entry. Đo trên
erptest.local: 0/56 dòng SLE của hàng có lô mang batch_no, 56/56 mang
serial_and_batch_bundle.

Đọc sai chỗ này thì 80/164 mặt hàng ghi so_lo = NULL, gộp mọi lô làm một —
và báo cáo đối soát VẪN BÁO KHỚP vì tổng số lượng đúng. Bộ test này là lưới
duy nhất bắt được lớp lỗi đó.

Một dòng SLE có thể mang NHIỀU lô → trả về nhiều phần tử, không phải một.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_wms.vitri.lo import tach_theo_lo


class _SleGia:
	"""Đủ thuộc tính cho tach_theo_lo, không cần chạm DB."""

	def __init__(self, bundle=None, batch_no=None):
		self.serial_and_batch_bundle = bundle
		self.batch_no = batch_no


class TestHangKhongLo(FrappeTestCase):
	def test_khong_bundle_khong_batch_thi_mot_dong_lo_rong(self):
		ket_qua = tach_theo_lo(_SleGia(), delta=7)
		self.assertEqual(ket_qua, [{"so_lo": None, "so_luong": 7}])

	def test_delta_am_giu_nguyen_dau(self):
		ket_qua = tach_theo_lo(_SleGia(), delta=-3)
		self.assertEqual(ket_qua, [{"so_lo": None, "so_luong": -3}])


class TestHangCoLo(FrappeTestCase):
	def setUp(self):
		self.bundle = frappe.get_doc({
			"doctype": "Serial and Batch Bundle",
			"item_code": "_Test Item Lo",
			"warehouse": "Kho Miyano - MYN",
			"type_of_transaction": "Inward",
			"voucher_type": "Stock Entry",
			"entries": [
				{"batch_no": "_T-LO-1", "qty": 6},
				{"batch_no": "_T-LO-2", "qty": 4},
			],
		})

	def test_mot_sle_nhieu_lo_tra_nhieu_dong(self):
		# dùng bundle giả trong DB để không phụ thuộc dữ liệu sẵn có
		ten = _luu_bundle_tho(self.bundle)
		ket_qua = tach_theo_lo(_SleGia(bundle=ten), delta=10)
		self.assertEqual(len(ket_qua), 2)
		self.assertEqual({d["so_lo"] for d in ket_qua}, {"_T-LO-1", "_T-LO-2"})
		self.assertEqual(sum(d["so_luong"] for d in ket_qua), 10)

	def test_khong_bao_gio_doc_sle_batch_no_khi_co_bundle(self):
		ten = _luu_bundle_tho(self.bundle)
		# batch_no cố tình sai — nếu hàm đọc nó thì bài này đỏ
		ket_qua = tach_theo_lo(_SleGia(bundle=ten, batch_no="LO-SAI"), delta=10)
		self.assertNotIn("LO-SAI", {d["so_lo"] for d in ket_qua})


def _luu_bundle_tho(doc):
	"""Ghi thẳng bundle + dòng con, bỏ qua validate của ERPNext.

	Bundle thật cần Item bật lô, kho, và ràng buộc tồn — dựng đủ ngần ấy chỉ
	để test một hàm đọc là quá tốn. Ghi thô giữ bài test nhanh và đúng trọng tâm.
	"""
	ten = frappe.generate_hash(length=20)
	frappe.db.sql(
		"""insert into `tabSerial and Batch Bundle`
		   (name, creation, modified, owner, modified_by, item_code, warehouse, voucher_type, docstatus)
		   values (%s, now(), now(), 'Administrator', 'Administrator', %s, %s, %s, 1)""",
		(ten, doc.item_code, doc.warehouse, doc.voucher_type),
	)
	for i, e in enumerate(doc.entries):
		frappe.db.sql(
			"""insert into `tabSerial and Batch Entry`
			   (name, creation, modified, owner, modified_by, parent, parenttype, parentfield, idx, batch_no, qty)
			   values (%s, now(), now(), 'Administrator', 'Administrator', %s,
			           'Serial and Batch Bundle', 'entries', %s, %s, %s)""",
			(frappe.generate_hash(length=20), ten, i + 1, e["batch_no"], e["qty"]),
		)
	return ten
```

- [ ] **Step 3: Chạy test, phải ĐỎ**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local run-tests --app miyano_wms --module miyano_wms.tests.test_tach_theo_lo
```

Kỳ vọng: FAIL — `ModuleNotFoundError: No module named 'miyano_wms.vitri.lo'`.

- [ ] **Step 4: Viết `vitri/lo.py`**

```python
"""Tách một dòng SLE thành các phần theo số lô.

ERPNext v15 KHÔNG ghi batch_no lên Stock Ledger Entry. Số lô nằm ở các dòng
con `Serial and Batch Entry` dưới `Serial and Batch Bundle`, và dòng con đã
mang dấu sẵn (xuất là số âm) — đã kiểm chứng trên erptest.local: bundle của
một Delivery Note actual_qty = -3 có dòng con qty = -3, total_qty = -3.

Một dòng SLE có thể mang nhiều lô, nên hàm này trả về DANH SÁCH.
"""

import frappe
from frappe.utils import flt


def tach_theo_lo(sle, delta: float) -> list[dict]:
	"""Trả [{"so_lo": str|None, "so_luong": float}], tổng so_luong == delta.

	`delta` là số lượng thật đã tính ở `vitri.delta.tinh_delta()` — dùng làm
	nguồn khi SLE không có bundle (hàng không lô, và Stock Reconciliation
	hàng không lô vốn có actual_qty = 0).
	"""
	bundle = getattr(sle, "serial_and_batch_bundle", None)
	if not bundle:
		return [{"so_lo": getattr(sle, "batch_no", None) or None, "so_luong": flt(delta)}]

	dong = frappe.get_all(
		"Serial and Batch Entry",
		filters={"parent": bundle},
		fields=["batch_no", "qty"],
		order_by="idx",
	)
	if not dong:
		return [{"so_lo": None, "so_luong": flt(delta)}]

	return [{"so_lo": d.batch_no or None, "so_luong": flt(d.qty)} for d in dong]
```

- [ ] **Step 5: Chạy lại test**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local run-tests --app miyano_wms --module miyano_wms.tests.test_tach_theo_lo
```

Kỳ vọng: 4 bài PASS.

- [ ] **Step 6: Commit**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_wms
git add -A
git commit -m "feat(vitri): tach_theo_lo() đọc lô từ Serial and Batch Bundle

ERPNext v15 không ghi batch_no lên SLE nữa (đo trên erptest.local: 0/56
dòng hàng có lô mang batch_no, 56/56 mang bundle). Đọc sai chỗ này thì
80/164 mặt hàng mất chiều lô mà báo cáo đối soát vẫn báo khớp — bộ test
này là lưới duy nhất bắt được. Một SLE có thể mang nhiều lô nên trả list."
```

---

### Task 6: `tinh_delta()` — số lượng thật, gồm bẫy Stock Reconciliation

**Files:**
- Create: `apps/miyano_wms/miyano_wms/vitri/delta.py`
- Test: `apps/miyano_wms/miyano_wms/tests/test_tinh_delta.py`

**Interfaces:**
- Consumes: `miyano_wms.vitri.so.tong_ton_vi_tri` (Task 4)
- Produces: `miyano_wms.vitri.delta.tinh_delta(sle) -> float`

- [ ] **Step 1: Viết bài test trước**

`apps/miyano_wms/miyano_wms/tests/test_tinh_delta.py`:

```python
"""Số lượng thật của một dòng SLE.

Cái bẫy: Stock Reconciliation với hàng KHÔNG LÔ ghi actual_qty = 0 và chỉ
đặt qty_after_transaction = tồn mới (erpnext stock_reconciliation.py:861,870).
Hàng CÓ LÔ thì SR tách thành hai dòng có dấu (dòng 809, 821) nên actual_qty
dùng được bình thường.

Cộng dồn actual_qty mà không xử lý nhánh này = bỏ qua ÂM THẦM mọi lần kiểm
kê hàng không lô. Không lưới nào khác bắt được vì SR là chứng từ hợp lệ và
mọi thứ trông vẫn bình thường.
"""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_wms.vitri.delta import tinh_delta

KHO = "Kho Miyano - MYN"


class _SleGia:
	def __init__(self, voucher_type, actual_qty=0, qty_after_transaction=0,
	             item_code="_Test Item Delta", warehouse=KHO, batch_no=None, bundle=None):
		self.voucher_type = voucher_type
		self.actual_qty = actual_qty
		self.qty_after_transaction = qty_after_transaction
		self.item_code = item_code
		self.warehouse = warehouse
		self.batch_no = batch_no
		self.serial_and_batch_bundle = bundle


class TestChungTuThuong(FrappeTestCase):
	def test_lay_thang_actual_qty(self):
		self.assertEqual(tinh_delta(_SleGia("Delivery Note", actual_qty=-5)), -5)

	def test_nhap_kho(self):
		self.assertEqual(tinh_delta(_SleGia("Purchase Receipt", actual_qty=20)), 20)


class TestKiemKeHangKhongLo(FrappeTestCase):
	def test_actual_qty_bang_0_thi_lay_tu_qty_after_transaction(self):
		sle = _SleGia("Stock Reconciliation", actual_qty=0, qty_after_transaction=30)
		with patch("miyano_wms.vitri.delta.tong_ton_vi_tri", return_value=12):
			self.assertEqual(tinh_delta(sle), 18)

	def test_kiem_ke_lam_giam_ton(self):
		sle = _SleGia("Stock Reconciliation", actual_qty=0, qty_after_transaction=5)
		with patch("miyano_wms.vitri.delta.tong_ton_vi_tri", return_value=12):
			self.assertEqual(tinh_delta(sle), -7)

	def test_kiem_ke_khong_doi_gi_tra_0(self):
		sle = _SleGia("Stock Reconciliation", actual_qty=0, qty_after_transaction=12)
		with patch("miyano_wms.vitri.delta.tong_ton_vi_tri", return_value=12):
			self.assertEqual(tinh_delta(sle), 0)


class TestKiemKeHangCoLo(FrappeTestCase):
	def test_co_actual_qty_thi_dung_luon_khong_tra_ton(self):
		# SR hàng có lô tách thành dòng âm/dương, actual_qty dùng được.
		sle = _SleGia("Stock Reconciliation", actual_qty=-8, qty_after_transaction=4, bundle="BUNDLE-X")
		with patch("miyano_wms.vitri.delta.tong_ton_vi_tri", return_value=999) as m:
			self.assertEqual(tinh_delta(sle), -8)
			m.assert_not_called()
```

- [ ] **Step 2: Chạy test, phải ĐỎ**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local run-tests --app miyano_wms --module miyano_wms.tests.test_tinh_delta
```

Kỳ vọng: FAIL — `ModuleNotFoundError: No module named 'miyano_wms.vitri.delta'`.

- [ ] **Step 3: Viết `vitri/delta.py`**

```python
"""Số lượng thật của một dòng Stock Ledger Entry.

Với hầu hết chứng từ, `actual_qty` là số lượng thật. Ngoại lệ duy nhất —
và là cái bẫy nguy hiểm nhất của cả app:

Stock Reconciliation với hàng KHÔNG LÔ ghi `actual_qty = 0` và chỉ đặt
`qty_after_transaction` = tồn mới (erpnext stock_reconciliation.py:861,870).
Nếu cứ cộng dồn actual_qty thì mọi lần kiểm kê hàng không lô bị bỏ qua âm
thầm, và không có lưới nào khác bắt được.
"""

from frappe.utils import flt

from miyano_wms.vitri.so import tong_ton_vi_tri


def tinh_delta(sle) -> float:
	"""Số lượng thật mà dòng SLE này làm thay đổi tồn kho."""
	delta = flt(getattr(sle, "actual_qty", 0))
	if delta:
		return delta

	if getattr(sle, "voucher_type", None) != "Stock Reconciliation":
		return 0.0

	# Kiểm kê đặt tồn tuyệt đối. Tồn trước đó = tổng tồn các ô; theo bất
	# biến spec §3, con số này luôn bằng Bin.actual_qty trước giao dịch.
	truoc = tong_ton_vi_tri(sle.warehouse, sle.item_code, getattr(sle, "batch_no", None))
	return flt(sle.qty_after_transaction) - flt(truoc)
```

- [ ] **Step 4: Chạy lại test**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local run-tests --app miyano_wms --module miyano_wms.tests.test_tinh_delta
```

Kỳ vọng: 6 bài PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_wms
git add -A
git commit -m "feat(vitri): tinh_delta() xử lý bẫy Stock Reconciliation hàng không lô

SR hàng không lô ghi actual_qty=0 và chỉ đặt qty_after_transaction
(stock_reconciliation.py:861,870). Cộng dồn actual_qty là bỏ qua âm thầm
mọi lần kiểm kê hàng không lô. Hàng có lô thì SR tách hai dòng có dấu nên
dùng actual_qty bình thường — test khẳng định nhánh đó không tra tồn."
```

---

### Task 7: Hook SLE — bỏ qua kho không bật, nhập dồn vào `CHUA-XEP`

**Files:**
- Create: `apps/miyano_wms/miyano_wms/vitri/hook_sle.py`
- Modify: `apps/miyano_wms/miyano_wms/hooks.py`
- Test: `apps/miyano_wms/miyano_wms/tests/test_hook_nhap.py`

**Interfaces:**
- Consumes: `vitri.kho.kho_co_quan_ly_vi_tri`, `vitri.kho.o_chua_xep` (Task 3); `vitri.so.ghi_dong_so` (Task 4); `vitri.lo.tach_theo_lo` (Task 5); `vitri.delta.tinh_delta` (Task 6)
- Produces: `miyano_wms.vitri.hook_sle.ghi_so_vi_tri(doc, method=None) -> None`

**Lưu ý phạm vi:** trong plan này hook **không** có nhánh đọc bảng phân bổ `Location Allocation` — đó là GĐ 2. Đừng viết sẵn.

- [ ] **Step 1: Viết bài test trước**

`apps/miyano_wms/miyano_wms/tests/test_hook_nhap.py`:

```python
"""Hook ghi sổ vị trí — nhánh nhập kho và nhánh bỏ qua.

Hook móc vào Stock Ledger Entry.on_submit. Đã xác minh mọi chứng từ đều tạo
SLE qua make_entry() -> sle.submit() (erpnext stock_ledger.py:221-227), nên
một hook này bắt trọn cả 8 loại chứng từ, kể cả doctype ERPNext thêm về sau.

Hai điều bài này khoá:
1. Kho KHÔNG bật thì hook không ghi gì. Hook chạy trên mọi dòng SLE của
   toàn hệ; ghi nhầm vào kho chưa bật là làm bẩn dữ liệu của kho đó.
2. Nhập mà không khai vị trí thì hàng vào ô CHUA-XEP, KHÔNG phải bị chặn.
   Chặn là làm người dùng không nhập kho được; CHUA-XEP biến việc bỏ sót
   thành hữu hình (có báo cáo nhắc dọn) thay vì thành lỗi.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_wms.vitri import kho as vk
from miyano_wms.vitri import so

KHO = "Kho Miyano - MYN"
KHO_TAT = "Stores - MYN"


def _bat_kho_tho(kho):
	"""Bật cờ + tạo ô CHUA-XEP bằng tay, không qua Warehouse Location Setup.

	Task 11-13 mới dựng chức năng bật thật. Ở đây chỉ cần đủ điều kiện để
	hook chạy.
	"""
	ma = vk.ma_o_chua_xep(kho)
	if not frappe.db.exists("Storage Location", ma):
		frappe.get_doc({
			"doctype": "Storage Location", "ma_o": ma, "ten_o": "Chưa xếp vị trí",
			"kho": kho, "cap_do": "Ô", "la_o_chua_xep": 1,
		}).insert(ignore_permissions=True)
	frappe.db.set_value("Warehouse", kho, "custom_quan_ly_vi_tri", 1)
	vk.xoa_cache_kho(kho)


def _tat_kho_tho(kho):
	frappe.db.set_value("Warehouse", kho, "custom_quan_ly_vi_tri", 0)
	vk.xoa_cache_kho(kho)


def _nhap_kho(item, qty, kho=KHO):
	se = frappe.get_doc({
		"doctype": "Stock Entry",
		"stock_entry_type": "Material Receipt",
		"company": "Miyano Việt Nam",
		"items": [{"item_code": item, "qty": qty, "t_warehouse": kho, "basic_rate": 1000}],
	})
	se.insert(ignore_permissions=True)
	se.submit()
	return se


def _tao_item(ma, co_lo=0):
	if not frappe.db.exists("Item", ma):
		frappe.get_doc({
			"doctype": "Item", "item_code": ma, "item_name": ma,
			"item_group": "All Item Groups", "stock_uom": "Nos",
			"is_stock_item": 1, "has_batch_no": co_lo, "create_new_batch": co_lo,
			"batch_number_series": f"{ma}-.###" if co_lo else None,
		}).insert(ignore_permissions=True)
	return ma


class TestKhoKhongBat(FrappeTestCase):
	def setUp(self):
		_tat_kho_tho(KHO_TAT)
		self.item = _tao_item("_Test WMS Bo Qua")

	def test_khong_ghi_dong_so_nao(self):
		truoc = frappe.db.count("Location Ledger Entry", {"kho": KHO_TAT})
		_nhap_kho(self.item, 5, kho=KHO_TAT)
		self.assertEqual(frappe.db.count("Location Ledger Entry", {"kho": KHO_TAT}), truoc)


class TestNhapKhongKhaiViTri(FrappeTestCase):
	def setUp(self):
		_bat_kho_tho(KHO)
		self.item = _tao_item("_Test WMS Nhap")

	def tearDown(self):
		_tat_kho_tho(KHO)

	def test_hang_vao_o_chua_xep(self):
		_nhap_kho(self.item, 12)
		o = vk.o_chua_xep(KHO)
		self.assertEqual(so.ton_o(o, self.item, None), 12)

	def test_bat_bien_tong_ton_bang_bin(self):
		_nhap_kho(self.item, 12)
		bin_qty = frappe.db.get_value("Bin", {"item_code": self.item, "warehouse": KHO}, "actual_qty")
		self.assertEqual(so.tong_ton_vi_tri(KHO, self.item, None), bin_qty)

	def test_dong_so_tro_ve_dung_chung_tu(self):
		se = _nhap_kho(self.item, 3)
		dong = frappe.get_all(
			"Location Ledger Entry",
			filters={"chung_tu": se.name}, fields=["chung_tu_type", "so_luong", "sle"],
		)
		self.assertEqual(len(dong), 1)
		self.assertEqual(dong[0].chung_tu_type, "Stock Entry")
		self.assertEqual(dong[0].so_luong, 3)
		self.assertTrue(dong[0].sle, "phải trỏ về dòng SLE sinh ra nó, để đối soát 1-1")


class TestNhapHangCoLo(FrappeTestCase):
	def setUp(self):
		_bat_kho_tho(KHO)
		self.item = _tao_item("_Test WMS Nhap Lo", co_lo=1)

	def tearDown(self):
		_tat_kho_tho(KHO)

	def test_so_lo_khong_duoc_rong(self):
		_nhap_kho(self.item, 10)
		dong = frappe.get_all(
			"Location Ledger Entry", filters={"vat_tu": self.item}, fields=["so_lo", "so_luong"]
		)
		self.assertTrue(dong, "phải có dòng sổ")
		self.assertTrue(
			all(d.so_lo for d in dong),
			"so_lo rỗng nghĩa là hook đọc sle.batch_no thay vì Serial and Batch Bundle",
		)
```

- [ ] **Step 2: Chạy test, phải ĐỎ**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local run-tests --app miyano_wms --module miyano_wms.tests.test_hook_nhap
```

Kỳ vọng: FAIL — chưa có `hook_sle`, các bài về `CHUA-XEP` đỏ.

- [ ] **Step 3: Viết `vitri/hook_sle.py`**

```python
"""Hook ghi sổ vị trí, móc vào Stock Ledger Entry.on_submit.

Vì sao chỉ một hook: mọi chứng từ ghi sổ kho của ERPNext — Purchase Receipt,
Purchase Invoice, Delivery Note, Sales Invoice, Stock Entry, Stock
Reconciliation, Subcontracting Receipt, Asset Capitalization — đều tạo SLE
qua make_entry() rồi gọi sle.submit() (erpnext stock_ledger.py:221-227).
Móc ở đây bắt trọn cả tám, kể cả doctype ERPNext thêm về sau. Móc vào từng
doctype thì sót một cái là lệch âm thầm.

Nhánh đọc bảng phân bổ Location Allocation thuộc GĐ 2, chưa có ở đây.
"""

import frappe

from miyano_wms.vitri.delta import tinh_delta
from miyano_wms.vitri.kho import kho_co_quan_ly_vi_tri, o_chua_xep
from miyano_wms.vitri.lo import tach_theo_lo
from miyano_wms.vitri.so import ghi_dong_so


def ghi_so_vi_tri(doc, method=None):
	"""Điểm vào duy nhất. `doc` là một Stock Ledger Entry vừa submit."""
	if not kho_co_quan_ly_vi_tri(doc.warehouse):
		return

	delta = tinh_delta(doc)
	if not delta:
		return

	for phan in tach_theo_lo(doc, delta):
		if not phan["so_luong"]:
			continue
		_ghi_mot_phan(doc, phan["so_lo"], phan["so_luong"])


def _ghi_mot_phan(sle, so_lo, so_luong):
	"""Ghi sổ cho một (lô, số lượng) của một dòng SLE."""
	o = o_chua_xep(sle.warehouse)
	if not o:
		frappe.throw(
			f"Kho {sle.warehouse} bật quản lý vị trí nhưng chưa có ô \"Chưa xếp vị trí\". "
			f"Chạy lại chức năng bật quản lý vị trí cho kho này."
		)

	ghi_dong_so(
		o=o,
		kho=sle.warehouse,
		vat_tu=sle.item_code,
		so_lo=so_lo,
		so_luong=so_luong,
		chung_tu_type=sle.voucher_type,
		chung_tu=sle.voucher_no,
		chung_tu_row=sle.voucher_detail_no,
		sle=sle.name,
		ngay=sle.posting_date,
		thoi_diem=sle.get("posting_datetime") or f"{sle.posting_date} {sle.posting_time}",
		company=sle.company,
	)
```

- [ ] **Step 4: Đăng ký hook**

Sửa `apps/miyano_wms/miyano_wms/hooks.py`, thêm:

```python
doc_events = {
	"Stock Ledger Entry": {
		"on_submit": "miyano_wms.vitri.hook_sle.ghi_so_vi_tri",
	},
}
```

- [ ] **Step 5: Nạp lại hook rồi chạy test**

`hooks.py` được cache; phải xoá cache mới có hiệu lực.

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local clear-cache
bench --site erptest.local run-tests --app miyano_wms --module miyano_wms.tests.test_hook_nhap
```

Kỳ vọng: 6 bài PASS. Nếu tất cả bài `CHUA-XEP` vẫn đỏ mà không thấy lỗi import → hook chưa được nạp; chạy `bench --site erptest.local clear-cache && systemctl --user restart erptest-dev.service` (đặt `XDG_RUNTIME_DIR=/run/user/1000`) rồi chạy lại.

- [ ] **Step 6: Commit**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_wms
git add -A
git commit -m "feat(vitri): hook SLE — bỏ qua kho không bật, nhập dồn vào CHUA-XEP

Một hook duy nhất trên Stock Ledger Entry.on_submit bắt trọn cả 8 loại
chứng từ vì mọi chứng từ đều tạo SLE qua make_entry() -> sle.submit()
(stock_ledger.py:221-227). Nhập không khai vị trí vào CHUA-XEP chứ không
chặn: chặn là làm người dùng không nhập kho được, CHUA-XEP biến việc bỏ
sót thành hữu hình thay vì thành lỗi."
```

---

### Task 8: Xuất không khai vị trí — chọn ô theo FEFO

**Files:**
- Create: `apps/miyano_wms/miyano_wms/vitri/fefo.py`
- Modify: `apps/miyano_wms/miyano_wms/vitri/hook_sle.py`
- Test: `apps/miyano_wms/miyano_wms/tests/test_fefo.py`

**Interfaces:**
- Consumes: `vitri.so.ton_o` (Task 4)
- Produces: `miyano_wms.vitri.fefo.chon_o_xuat(kho, vat_tu, so_lo, so_luong: float) -> list[dict]` — mỗi phần tử `{"o": str, "so_luong": float}` với `so_luong` **dương**; tổng bằng `so_luong` yêu cầu. Không đủ tồn → `frappe.throw`.

- [ ] **Step 1: Viết bài test trước**

`apps/miyano_wms/miyano_wms/tests/test_fefo.py`:

```python
"""Chọn ô khi xuất mà chứng từ không khai vị trí.

Thứ tự: hạn dùng gần nhất trước (FEFO), cùng hạn thì theo thu_tu_lay_hang
(đường đi trong kho). Lô không có hạn dùng xếp SAU CÙNG — không phải trước:
"không biết hạn" khác hẳn "hết hạn hôm nay", và đẩy nó lên đầu là ưu tiên
xuất đúng những lô mình biết ít nhất về chúng.

Ô CHUA-XEP vẫn được chọn — hàng nằm ở đó là hàng thật, chỉ là chưa ai xếp.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_wms.vitri import so
from miyano_wms.vitri.fefo import chon_o_xuat

KHO = "Kho Miyano - MYN"


def _o(ma_o, thu_tu=0):
	if not frappe.db.exists("Storage Location", ma_o):
		frappe.get_doc({
			"doctype": "Storage Location", "ma_o": ma_o, "kho": KHO,
			"cap_do": "Ô", "thu_tu_lay_hang": thu_tu,
		}).insert(ignore_permissions=True)
	return ma_o


def _lo(ma, han=None):
	if not frappe.db.exists("Batch", ma):
		frappe.get_doc({
			"doctype": "Batch", "batch_id": ma, "item": "_Test FEFO Item",
			"expiry_date": han,
		}).insert(ignore_permissions=True)
	return ma


def _dat(o, vat_tu, so_lo, sl):
	so.ghi_dong_so(
		o=o, kho=KHO, vat_tu=vat_tu, so_lo=so_lo, so_luong=sl,
		chung_tu_type="Stock Entry", chung_tu="FEFO-SEED", chung_tu_row="r",
		sle=None, ngay="2026-09-01", thoi_diem="2026-09-01 08:00:00",
		company="Miyano Việt Nam",
	)


class TestChonTheoDuongDi(FrappeTestCase):
	def setUp(self):
		if not frappe.db.exists("Item", "_Test FEFO Item"):
			frappe.get_doc({
				"doctype": "Item", "item_code": "_Test FEFO Item", "item_name": "_Test FEFO Item",
				"item_group": "All Item Groups", "stock_uom": "Nos", "is_stock_item": 1,
			}).insert(ignore_permissions=True)

	def test_cung_lo_thi_theo_thu_tu_lay_hang(self):
		xa, gan = _o("TEST-FEFO-XA", thu_tu=9), _o("TEST-FEFO-GAN", thu_tu=1)
		_dat(xa, "_Test FEFO Item", None, 10)
		_dat(gan, "_Test FEFO Item", None, 10)
		ket_qua = chon_o_xuat(KHO, "_Test FEFO Item", None, 4)
		self.assertEqual(ket_qua, [{"o": gan, "so_luong": 4}])

	def test_khong_du_mot_o_thi_lay_tiep_o_sau(self):
		a, b = _o("TEST-FEFO-A", thu_tu=1), _o("TEST-FEFO-B", thu_tu=2)
		_dat(a, "_Test FEFO Item", None, 3)
		_dat(b, "_Test FEFO Item", None, 10)
		ket_qua = chon_o_xuat(KHO, "_Test FEFO Item", None, 7)
		self.assertEqual(ket_qua, [{"o": a, "so_luong": 3}, {"o": b, "so_luong": 4}])

	def test_bo_qua_o_het_hang(self):
		het, con = _o("TEST-FEFO-HET", thu_tu=1), _o("TEST-FEFO-CON", thu_tu=2)
		_dat(het, "_Test FEFO Item", None, 5)
		_dat(het, "_Test FEFO Item", None, -5)
		_dat(con, "_Test FEFO Item", None, 6)
		ket_qua = chon_o_xuat(KHO, "_Test FEFO Item", None, 2)
		self.assertEqual(ket_qua, [{"o": con, "so_luong": 2}])


class TestChonTheoHanDung(FrappeTestCase):
	def test_han_gan_nhat_di_truoc(self):
		som, muon = _o("TEST-FEFO-SOM", thu_tu=9), _o("TEST-FEFO-MUON", thu_tu=1)
		l_som, l_muon = _lo("_T-FEFO-SOM", "2026-10-01"), _lo("_T-FEFO-MUON", "2027-10-01")
		_dat(som, "_Test FEFO Item", l_som, 5)
		_dat(muon, "_Test FEFO Item", l_muon, 5)
		# gọi không chỉ định lô
		ket_qua = chon_o_xuat(KHO, "_Test FEFO Item", None, 3)
		self.assertEqual(ket_qua[0]["o"], som, "lô hạn gần hơn phải đi trước dù đường đi xa hơn")

	def test_lo_khong_han_xep_sau_cung(self):
		co_han, khong_han = _o("TEST-FEFO-CH", thu_tu=1), _o("TEST-FEFO-KH", thu_tu=1)
		l_han = _lo("_T-FEFO-CO-HAN", "2027-01-01")
		l_khong = _lo("_T-FEFO-KHONG-HAN", None)
		_dat(co_han, "_Test FEFO Item", l_han, 5)
		_dat(khong_han, "_Test FEFO Item", l_khong, 5)
		ket_qua = chon_o_xuat(KHO, "_Test FEFO Item", None, 3)
		self.assertEqual(ket_qua[0]["o"], co_han, "lô không hạn phải xếp sau — xem docstring")


class TestChonDungLoDuocChiDinh(FrappeTestCase):
	def test_chi_dinh_lo_thi_khong_dung_lo_khac(self):
		a, b = _o("TEST-FEFO-L1", thu_tu=1), _o("TEST-FEFO-L2", thu_tu=2)
		l1, l2 = _lo("_T-FEFO-L1", "2026-11-01"), _lo("_T-FEFO-L2", "2026-12-01")
		_dat(a, "_Test FEFO Item", l1, 5)
		_dat(b, "_Test FEFO Item", l2, 5)
		ket_qua = chon_o_xuat(KHO, "_Test FEFO Item", l2, 4)
		self.assertEqual(ket_qua, [{"o": b, "so_luong": 4}])


class TestKhongDuTon(FrappeTestCase):
	def test_bao_loi_tieng_viet_neu_ro_thieu_bao_nhieu(self):
		o = _o("TEST-FEFO-THIEU", thu_tu=1)
		_dat(o, "_Test FEFO Item", None, 2)
		with self.assertRaises(frappe.ValidationError) as ctx:
			chon_o_xuat(KHO, "_Test FEFO Item", None, 10)
		loi = str(ctx.exception)
		self.assertIn("_Test FEFO Item", loi)
		self.assertIn("thiếu", loi.lower())
		self.assertNotIn("Traceback", loi)
```

- [ ] **Step 2: Chạy test, phải ĐỎ**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local run-tests --app miyano_wms --module miyano_wms.tests.test_fefo
```

Kỳ vọng: FAIL — `ModuleNotFoundError: No module named 'miyano_wms.vitri.fefo'`.

- [ ] **Step 3: Viết `vitri/fefo.py`**

```python
"""Chọn ô để xuất khi chứng từ không khai vị trí.

Thứ tự: hạn dùng gần nhất trước (FEFO), cùng hạn thì theo thu_tu_lay_hang.

Lô KHÔNG có hạn dùng xếp SAU CÙNG. `ifnull(han, '9999-12-31')` chứ không
phải `ifnull(han, '1900-01-01')`: "không biết hạn" khác hẳn "sắp hết hạn",
và đẩy nó lên đầu là ưu tiên xuất đúng những lô mình biết ít nhất.
"""

import frappe
from frappe import _
from frappe.utils import flt

HAN_XA = "9999-12-31"


def chon_o_xuat(kho, vat_tu, so_lo, so_luong: float) -> list[dict]:
	"""Chọn các ô để lấy đủ `so_luong` (số dương). Không đủ → throw.

	`so_lo` có giá trị thì chỉ lấy đúng lô đó; None thì lấy mọi lô theo FEFO.
	"""
	can = flt(so_luong)
	if can <= 0:
		return []

	dieu_kien = "and ifnull(lb.so_lo,'') = %(so_lo)s" if so_lo else ""
	ung_vien = frappe.db.sql(
		f"""
		select lb.o, lb.so_lo, lb.so_luong
		from `tabLocation Balance` lb
		left join `tabBatch` b on b.name = lb.so_lo
		join `tabStorage Location` sl on sl.name = lb.o
		where lb.kho = %(kho)s and lb.vat_tu = %(vat_tu)s and lb.so_luong > 0
		      and ifnull(sl.disabled, 0) = 0
		      {dieu_kien}
		order by ifnull(b.expiry_date, %(han_xa)s) asc,
		         ifnull(sl.thu_tu_lay_hang, 0) asc,
		         lb.o asc
		""",
		{"kho": kho, "vat_tu": vat_tu, "so_lo": so_lo or "", "han_xa": HAN_XA},
		as_dict=True,
	)

	ket_qua = []
	for u in ung_vien:
		if can <= 0:
			break
		lay = min(flt(u.so_luong), can)
		ket_qua.append({"o": u.o, "so_luong": lay})
		can -= lay

	if can > 0:
		co = flt(so_luong) - can
		frappe.throw(
			_("Không đủ hàng để xuất. Mặt hàng {0}{1} tại kho {2}: cần {3}, chỉ có {4}, thiếu {5}.").format(
				vat_tu,
				f" (lô {so_lo})" if so_lo else "",
				kho,
				flt(so_luong),
				co,
				can,
			)
		)

	return ket_qua
```

- [ ] **Step 4: Nối FEFO vào hook**

Sửa `_ghi_mot_phan` trong `apps/miyano_wms/miyano_wms/vitri/hook_sle.py` thành:

```python
def _ghi_mot_phan(sle, so_lo, so_luong):
	"""Ghi sổ cho một (lô, số lượng) của một dòng SLE.

	Nhập (số dương) mà không khai vị trí → dồn vào CHUA-XEP.
	Xuất (số âm) mà không khai vị trí → chọn ô theo FEFO.
	"""
	if so_luong > 0:
		phan_bo = [{"o": _bat_buoc_o_chua_xep(sle.warehouse), "so_luong": so_luong}]
	else:
		phan_bo = [
			{"o": p["o"], "so_luong": -p["so_luong"]}
			for p in chon_o_xuat(sle.warehouse, sle.item_code, so_lo, -so_luong)
		]

	for p in phan_bo:
		ghi_dong_so(
			o=p["o"],
			kho=sle.warehouse,
			vat_tu=sle.item_code,
			so_lo=so_lo,
			so_luong=p["so_luong"],
			chung_tu_type=sle.voucher_type,
			chung_tu=sle.voucher_no,
			chung_tu_row=sle.voucher_detail_no,
			sle=sle.name,
			ngay=sle.posting_date,
			thoi_diem=sle.get("posting_datetime") or f"{sle.posting_date} {sle.posting_time}",
			company=sle.company,
		)


def _bat_buoc_o_chua_xep(kho):
	o = o_chua_xep(kho)
	if not o:
		frappe.throw(
			_("Kho {0} bật quản lý vị trí nhưng chưa có ô \"Chưa xếp vị trí\". "
			  "Chạy lại chức năng bật quản lý vị trí cho kho này.").format(kho)
		)
	return o
```

Thêm import ở đầu `hook_sle.py`:

```python
from frappe import _

from miyano_wms.vitri.fefo import chon_o_xuat
```

- [ ] **Step 5: Chạy test FEFO và chạy lại test nhập**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local run-tests --app miyano_wms --module miyano_wms.tests.test_fefo
bench --site erptest.local run-tests --app miyano_wms --module miyano_wms.tests.test_hook_nhap
```

Kỳ vọng: 8 bài FEFO PASS, 6 bài nhập vẫn PASS.

- [ ] **Step 6: Commit**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_wms
git add -A
git commit -m "feat(vitri): xuất không khai vị trí thì chọn ô theo FEFO

Hạn gần nhất trước, cùng hạn thì theo thu_tu_lay_hang. Lô KHÔNG có hạn xếp
sau cùng (ifnull -> 9999-12-31): 'không biết hạn' khác 'sắp hết hạn', đẩy
lên đầu là ưu tiên xuất đúng những lô mình biết ít nhất. Không đủ tồn thì
báo lỗi tiếng Việt nêu rõ cần bao nhiêu, có bao nhiêu, thiếu bao nhiêu."
```

---

### Task 9: Huỷ chứng từ — đảo đúng ô gốc

**Files:**
- Modify: `apps/miyano_wms/miyano_wms/vitri/hook_sle.py`
- Test: `apps/miyano_wms/miyano_wms/tests/test_huy_chung_tu.py`

**Interfaces:**
- Consumes: `vitri.so.ghi_dong_so` (Task 4)
- Produces: `miyano_wms.vitri.hook_sle.dao_theo_o_goc(sle) -> bool` — trả `True` nếu đã đảo được theo dòng gốc

- [ ] **Step 1: Viết bài test trước**

`apps/miyano_wms/miyano_wms/tests/test_huy_chung_tu.py`:

```python
"""Huỷ chứng từ — đảo ĐÚNG ô gốc, không chạy lại FEFO.

Khi huỷ, ERPNext ghi THÊM dòng SLE mới với số lượng đảo dấu rồi mới cờ
is_cancelled lên dòng cũ (erpnext stock_ledger.py:66-90, 212). Dòng mới vẫn
qua make_entry() nên hook vẫn nổ.

Cái bẫy: nếu nhánh huỷ cứ chạy FEFO như một lần xuất/nhập bình thường thì
hàng được trả về Ô KHÁC với ô đã lấy. Tổng tồn vẫn đúng nên báo cáo đối
soát KHÔNG bắt được — chỉ tới lúc kiểm kê thực tế mới lộ, và lúc đó không
còn dấu vết để lần ngược. Bộ test này là lưới duy nhất.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_wms.vitri import kho as vk
from miyano_wms.vitri import so
from miyano_wms.tests.test_hook_nhap import _bat_kho_tho, _tao_item, _tat_kho_tho

KHO = "Kho Miyano - MYN"


def _o(ma_o, thu_tu=0):
	if not frappe.db.exists("Storage Location", ma_o):
		frappe.get_doc({
			"doctype": "Storage Location", "ma_o": ma_o, "kho": KHO,
			"cap_do": "Ô", "thu_tu_lay_hang": thu_tu,
		}).insert(ignore_permissions=True)
	return ma_o


def _xuat_kho(item, qty):
	se = frappe.get_doc({
		"doctype": "Stock Entry",
		"stock_entry_type": "Material Issue",
		"company": "Miyano Việt Nam",
		"items": [{"item_code": item, "qty": qty, "s_warehouse": KHO}],
	})
	se.insert(ignore_permissions=True)
	se.submit()
	return se


def _nhap_kho(item, qty):
	se = frappe.get_doc({
		"doctype": "Stock Entry",
		"stock_entry_type": "Material Receipt",
		"company": "Miyano Việt Nam",
		"items": [{"item_code": item, "qty": qty, "t_warehouse": KHO, "basic_rate": 1000}],
	})
	se.insert(ignore_permissions=True)
	se.submit()
	return se


class TestHuyPhieuXuat(FrappeTestCase):
	def setUp(self):
		_bat_kho_tho(KHO)
		self.item = _tao_item("_Test WMS Huy")
		self.o_xa = _o("TEST-HUY-XA", thu_tu=9)
		self.o_gan = _o("TEST-HUY-GAN", thu_tu=1)
		# đặt hàng ở hai ô, FEFO sẽ lấy từ ô GẦN
		so.ghi_dong_so(
			o=self.o_gan, kho=KHO, vat_tu=self.item, so_lo=None, so_luong=10,
			chung_tu_type="Stock Entry", chung_tu="SEED-HUY", chung_tu_row="r",
			sle=None, ngay="2026-09-01", thoi_diem="2026-09-01 08:00:00",
			company="Miyano Việt Nam",
		)

	def tearDown(self):
		_tat_kho_tho(KHO)

	def test_huy_tra_hang_ve_dung_o_da_lay(self):
		se = _xuat_kho(self.item, 4)
		self.assertEqual(so.ton_o(self.o_gan, self.item, None), 6)

		# đổi đường đi để FEFO nếu chạy lại sẽ chọn ô KHÁC
		frappe.db.set_value("Storage Location", self.o_xa, "thu_tu_lay_hang", 0)
		so.ghi_dong_so(
			o=self.o_xa, kho=KHO, vat_tu=self.item, so_lo=None, so_luong=50,
			chung_tu_type="Stock Entry", chung_tu="SEED-HUY-2", chung_tu_row="r",
			sle=None, ngay="2026-09-01", thoi_diem="2026-09-01 09:00:00",
			company="Miyano Việt Nam",
		)

		se.cancel()

		self.assertEqual(
			so.ton_o(self.o_gan, self.item, None), 10,
			"hàng phải quay về đúng ô đã lấy",
		)
		self.assertEqual(
			so.ton_o(self.o_xa, self.item, None), 50,
			"ô khác không được đụng tới",
		)

	def test_dong_goc_bi_co_da_huy(self):
		se = _xuat_kho(self.item, 2)
		se.cancel()
		goc = frappe.get_all(
			"Location Ledger Entry",
			filters={"chung_tu": se.name, "so_luong": ("<", 0)},
			fields=["name", "da_huy"],
		)
		self.assertTrue(goc)
		self.assertTrue(all(d.da_huy for d in goc), "dòng gốc phải bị cờ đã đảo")

	def test_khong_xoa_dong_nao(self):
		se = _xuat_kho(self.item, 2)
		truoc = frappe.db.count("Location Ledger Entry", {"chung_tu": se.name})
		se.cancel()
		sau = frappe.db.count("Location Ledger Entry", {"chung_tu": se.name})
		self.assertGreater(sau, truoc, "huỷ phải GHI THÊM dòng đảo, không xoá dòng cũ")


class TestHuyPhieuNhap(FrappeTestCase):
	def setUp(self):
		_bat_kho_tho(KHO)
		self.item = _tao_item("_Test WMS Huy Nhap")

	def tearDown(self):
		_tat_kho_tho(KHO)

	def test_huy_nhap_lay_hang_ra_dung_o_da_dat(self):
		se = _nhap_kho(self.item, 8)
		o = vk.o_chua_xep(KHO)
		self.assertEqual(so.ton_o(o, self.item, None), 8)
		se.cancel()
		self.assertEqual(so.ton_o(o, self.item, None), 0)
```

- [ ] **Step 2: Chạy test, phải ĐỎ**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local run-tests --app miyano_wms --module miyano_wms.tests.test_huy_chung_tu
```

Kỳ vọng: `test_huy_tra_hang_ve_dung_o_da_lay` FAIL — hàng quay về ô `TEST-HUY-XA` thay vì `TEST-HUY-GAN`.

- [ ] **Step 3: Thêm nhánh đảo vào hook**

Sửa `ghi_so_vi_tri` trong `apps/miyano_wms/miyano_wms/vitri/hook_sle.py`:

```python
def ghi_so_vi_tri(doc, method=None):
	"""Điểm vào duy nhất. `doc` là một Stock Ledger Entry vừa submit."""
	if not kho_co_quan_ly_vi_tri(doc.warehouse):
		return

	if doc.get("is_cancelled") and dao_theo_o_goc(doc):
		return

	delta = tinh_delta(doc)
	if not delta:
		return

	for phan in tach_theo_lo(doc, delta):
		if not phan["so_luong"]:
			continue
		_ghi_mot_phan(doc, phan["so_lo"], phan["so_luong"])
```

Thêm hàm:

```python
def dao_theo_o_goc(sle) -> bool:
	"""Ghi bút toán đảo theo ĐÚNG các ô mà chứng từ gốc đã dùng.

	Trả False nếu không tìm được dòng gốc — khi đó gọi bên ngoài sẽ đi tiếp
	nhánh thường (FEFO / CHUA-XEP), là hành vi đúng cho chứng từ phát sinh
	sau khi kho mới bật quản lý vị trí.

	KHÔNG chạy lại FEFO ở đây. Chạy lại sẽ trả hàng về ô khác với ô đã lấy;
	tổng tồn vẫn đúng nên báo cáo đối soát không bắt được, và lỗi chỉ lộ ra
	lúc kiểm kê thực tế khi đã mất dấu vết.
	"""
	goc = frappe.get_all(
		"Location Ledger Entry",
		filters={
			"chung_tu_type": sle.voucher_type,
			"chung_tu": sle.voucher_no,
			"chung_tu_row": sle.voucher_detail_no,
			"da_huy": 0,
		},
		fields=["name", "o", "so_lo", "so_luong", "kho"],
	)
	if not goc:
		return False

	for d in goc:
		ghi_dong_so(
			o=d.o,
			kho=d.kho,
			vat_tu=sle.item_code,
			so_lo=d.so_lo,
			so_luong=-d.so_luong,
			chung_tu_type=sle.voucher_type,
			chung_tu=sle.voucher_no,
			chung_tu_row=sle.voucher_detail_no,
			sle=sle.name,
			ngay=sle.posting_date,
			thoi_diem=sle.get("posting_datetime") or f"{sle.posting_date} {sle.posting_time}",
			company=sle.company,
			da_huy=1,
		)
		frappe.db.set_value("Location Ledger Entry", d.name, "da_huy", 1, update_modified=False)

	return True
```

- [ ] **Step 4: Chạy lại test**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local run-tests --app miyano_wms --module miyano_wms.tests.test_huy_chung_tu
```

Kỳ vọng: 4 bài PASS.

- [ ] **Step 5: Chạy cả bộ để chắc không vỡ bài cũ**

```bash
bench --site erptest.local run-tests --app miyano_wms
```

Kỳ vọng: toàn bộ PASS. Nếu gặp `ReadTimeout` ngẫu nhiên — máy 15Gi chạy 3 bench, chạy lại đúng module đó trước khi kết luận là hồi quy.

- [ ] **Step 6: Commit**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_wms
git add -A
git commit -m "feat(vitri): huỷ chứng từ đảo đúng ô gốc, không chạy lại FEFO

Khi huỷ, ERPNext ghi thêm dòng SLE đảo dấu rồi mới cờ is_cancelled dòng cũ
(stock_ledger.py:66-90,212) nên hook vẫn nổ. Nhánh đảo soi lại dòng sổ gốc
theo voucher_detail_no và ghi ngược đúng từng ô đã dùng. Chạy lại FEFO sẽ
trả hàng về ô khác — tổng vẫn đúng nên đối soát không bắt được, chỉ lộ lúc
kiểm kê khi đã mất dấu vết."
```

---

### Task 10: Đối soát tồn vị trí ↔ tồn kho ERPNext

**Files:**
- Create: `apps/miyano_wms/miyano_wms/vitri/doi_soat.py`
- Create: `apps/miyano_wms/miyano_wms/miyano_wms/report/doi_soat_ton_vi_tri/{__init__.py,doi_soat_ton_vi_tri.json,doi_soat_ton_vi_tri.py}`
- Test: `apps/miyano_wms/miyano_wms/tests/test_doi_soat.py`

**Interfaces:**
- Consumes: `Location Balance` (Task 4)
- Produces: `miyano_wms.vitri.doi_soat.doi_soat_kho(kho) -> dict` với khoá `khop: bool`, `so_dong_lech: int`, `dong_lech: list[dict]` (mỗi phần tử có `vat_tu`, `so_lo`, `ton_vi_tri`, `ton_kho`, `lech`)

**Đây là lưới an toàn của toàn hệ.** Không được rút gọn ra khỏi plan này — thiếu nó thì mọi giai đoạn sau xây trên số liệu không ai kiểm chứng được.

- [ ] **Step 1: Viết bài test trước**

`apps/miyano_wms/miyano_wms/tests/test_doi_soat.py`:

```python
"""Đối soát tồn vị trí với tồn kho ERPNext — bất biến của spec §3.

So THEO TỪNG LÔ, không chỉ so tổng. So tổng thôi thì một lỗi gộp lô (mọi lô
ghi so_lo = NULL) vẫn "khớp" — đúng lớp lỗi mà Task 5 sinh ra để phòng.

Tồn kho lấy từ Stock Ledger Entry chứ không từ Bin, vì Bin không có chiều
lô. Với hàng có lô thì tổng SLE theo (item, warehouse, batch) là con số duy
nhất so được.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_wms.vitri import so
from miyano_wms.vitri.doi_soat import doi_soat_kho
from miyano_wms.tests.test_hook_nhap import _bat_kho_tho, _tao_item, _tat_kho_tho

KHO = "Kho Miyano - MYN"


def _nhap(item, qty):
	se = frappe.get_doc({
		"doctype": "Stock Entry", "stock_entry_type": "Material Receipt",
		"company": "Miyano Việt Nam",
		"items": [{"item_code": item, "qty": qty, "t_warehouse": KHO, "basic_rate": 1000}],
	})
	se.insert(ignore_permissions=True)
	se.submit()
	return se


class TestKhopThiBaoKhop(FrappeTestCase):
	def setUp(self):
		_bat_kho_tho(KHO)
		self.item = _tao_item("_Test DS Khop")

	def tearDown(self):
		_tat_kho_tho(KHO)

	def test_sau_khi_nhap_thi_khop(self):
		_nhap(self.item, 15)
		kq = doi_soat_kho(KHO)
		lech_cua_item = [d for d in kq["dong_lech"] if d["vat_tu"] == self.item]
		self.assertEqual(lech_cua_item, [], f"phải khớp, nhưng lệch: {lech_cua_item}")


class TestLechThiBao(FrappeTestCase):
	def setUp(self):
		_bat_kho_tho(KHO)
		self.item = _tao_item("_Test DS Lech")

	def tearDown(self):
		_tat_kho_tho(KHO)

	def test_pha_ton_vi_tri_thi_doi_soat_bat_duoc(self):
		_nhap(self.item, 10)
		ten = frappe.db.get_value("Location Balance", {"kho": KHO, "vat_tu": self.item}, "name")
		frappe.db.set_value("Location Balance", ten, "so_luong", 3)

		kq = doi_soat_kho(KHO)
		self.assertFalse(kq["khop"])
		lech = [d for d in kq["dong_lech"] if d["vat_tu"] == self.item]
		self.assertEqual(len(lech), 1)
		self.assertEqual(lech[0]["ton_vi_tri"], 3)
		self.assertEqual(lech[0]["ton_kho"], 10)
		self.assertEqual(lech[0]["lech"], -7)

	def test_dung_lai_ton_thi_het_lech(self):
		_nhap(self.item, 10)
		ten = frappe.db.get_value("Location Balance", {"kho": KHO, "vat_tu": self.item}, "name")
		frappe.db.set_value("Location Balance", ten, "so_luong", 3)
		self.assertFalse(doi_soat_kho(KHO)["khop"])

		so.dung_lai_ton_vi_tri(KHO)
		lech = [d for d in doi_soat_kho(KHO)["dong_lech"] if d["vat_tu"] == self.item]
		self.assertEqual(lech, [])


class TestSoTheoTungLo(FrappeTestCase):
	def setUp(self):
		_bat_kho_tho(KHO)
		self.item = _tao_item("_Test DS Lo", co_lo=1)

	def tearDown(self):
		_tat_kho_tho(KHO)

	def test_gop_lo_lam_mot_thi_bi_bat(self):
		"""Bài chốt: mô phỏng đúng lỗi Task 5 phòng, đối soát phải bắt được."""
		_nhap(self.item, 10)
		dong = frappe.get_all(
			"Location Balance", filters={"kho": KHO, "vat_tu": self.item}, fields=["name", "so_lo"]
		)
		self.assertTrue(dong)
		self.assertTrue(dong[0].so_lo, "tiền đề: hook phải ghi được lô")

		# cố tình xoá lô để giả lập lỗi gộp lô
		frappe.db.set_value("Location Balance", dong[0].name, "so_lo", None)

		kq = doi_soat_kho(KHO)
		self.assertFalse(kq["khop"], "so theo từng lô phải bắt được lỗi gộp lô")
```

- [ ] **Step 2: Chạy test, phải ĐỎ**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local run-tests --app miyano_wms --module miyano_wms.tests.test_doi_soat
```

Kỳ vọng: FAIL — `ModuleNotFoundError: No module named 'miyano_wms.vitri.doi_soat'`.

- [ ] **Step 3: Viết `vitri/doi_soat.py`**

```python
"""So tồn vị trí với tồn kho ERPNext. Bất biến của spec §3.

So THEO TỪNG (mặt hàng, lô), không chỉ so tổng — so tổng thôi thì một lỗi
gộp lô vẫn "khớp".

Tồn kho lấy từ tổng Stock Ledger Entry chứ không từ Bin, vì Bin không có
chiều lô. Với hàng có lô, số lô nằm ở Serial and Batch Bundle nên phải nối
qua dòng con của bundle.
"""

import frappe
from frappe.utils import flt


def _ton_kho_theo_lo(kho) -> dict:
	"""{(vat_tu, so_lo): so_luong} lấy từ sổ kho ERPNext."""
	dong = frappe.db.sql(
		"""
		select sle.item_code as vat_tu,
		       ifnull(sbe.batch_no, ifnull(sle.batch_no, '')) as so_lo,
		       sum(case when sbe.name is not null then sbe.qty else sle.actual_qty end) as sl
		from `tabStock Ledger Entry` sle
		left join `tabSerial and Batch Entry` sbe on sbe.parent = sle.serial_and_batch_bundle
		where sle.warehouse = %s and sle.is_cancelled = 0
		group by sle.item_code, ifnull(sbe.batch_no, ifnull(sle.batch_no, ''))
		""",
		(kho,),
		as_dict=True,
	)
	return {(d.vat_tu, d.so_lo or ""): flt(d.sl) for d in dong}


def _ton_vi_tri_theo_lo(kho) -> dict:
	dong = frappe.db.sql(
		"""select vat_tu, ifnull(so_lo,'') as so_lo, sum(so_luong) as sl
		   from `tabLocation Balance` where kho = %s
		   group by vat_tu, ifnull(so_lo,'')""",
		(kho,),
		as_dict=True,
	)
	return {(d.vat_tu, d.so_lo or ""): flt(d.sl) for d in dong}


def doi_soat_kho(kho) -> dict:
	"""So tồn vị trí với tồn kho. Trả kết quả kèm danh sách dòng lệch."""
	ton_kho = _ton_kho_theo_lo(kho)
	ton_vt = _ton_vi_tri_theo_lo(kho)

	moi_khoa = set(ton_kho) | set(ton_vt)
	lech = []
	for vat_tu, so_lo in sorted(moi_khoa):
		a = flt(ton_vt.get((vat_tu, so_lo), 0))
		b = flt(ton_kho.get((vat_tu, so_lo), 0))
		if abs(a - b) > 0.0001:
			lech.append({
				"vat_tu": vat_tu,
				"so_lo": so_lo or None,
				"ton_vi_tri": a,
				"ton_kho": b,
				"lech": a - b,
			})

	return {"kho": kho, "khop": not lech, "so_dong_lech": len(lech), "dong_lech": lech}
```

- [ ] **Step 4: Chạy lại test**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local run-tests --app miyano_wms --module miyano_wms.tests.test_doi_soat
```

Kỳ vọng: 4 bài PASS.

- [ ] **Step 5: Bọc thành báo cáo gọi tay được**

Scheduler **đang tắt trên `erptest.local`**, nên đối soát bắt buộc phải gọi tay được, không chỉ dựa vào lịch chạy.

`.../report/doi_soat_ton_vi_tri/__init__.py` — file rỗng.

`.../report/doi_soat_ton_vi_tri/doi_soat_ton_vi_tri.json`:

```json
{
 "add_total_row": 0,
 "creation": "2026-09-09 00:00:00.000000",
 "disabled": 0,
 "doctype": "Report",
 "is_standard": "Yes",
 "modified": "2026-09-09 00:00:00.000000",
 "module": "Miyano WMS",
 "name": "Doi Soat Ton Vi Tri",
 "owner": "Administrator",
 "prepared_report": 0,
 "ref_doctype": "Location Balance",
 "report_name": "Doi Soat Ton Vi Tri",
 "report_type": "Script Report",
 "roles": [
  {"role": "System Manager"},
  {"role": "Stock Manager"},
  {"role": "Stock User"}
 ]
}
```

`.../report/doi_soat_ton_vi_tri/doi_soat_ton_vi_tri.py`:

```python
"""Đối soát tồn vị trí ↔ tồn kho — lưới an toàn của toàn hệ.

Báo cáo rỗng nghĩa là KHỚP. Có dòng nghĩa là sổ vị trí đã lệch khỏi sổ kho
ERPNext và phải xử lý trước khi tin bất kỳ con số nào khác.
"""

from frappe import _

from miyano_wms.vitri.doi_soat import doi_soat_kho


def execute(filters=None):
	filters = filters or {}
	kho = filters.get("kho")
	if not kho:
		return _cot(), []

	kq = doi_soat_kho(kho)
	dong = [
		[d["vat_tu"], d["so_lo"], d["ton_vi_tri"], d["ton_kho"], d["lech"]]
		for d in kq["dong_lech"]
	]
	return _cot(), dong


def _cot():
	return [
		{"label": _("Mặt hàng"), "fieldname": "vat_tu", "fieldtype": "Link", "options": "Item", "width": 220},
		{"label": _("Số lô"), "fieldname": "so_lo", "fieldtype": "Link", "options": "Batch", "width": 180},
		{"label": _("Tồn theo vị trí"), "fieldname": "ton_vi_tri", "fieldtype": "Float", "width": 130},
		{"label": _("Tồn kho ERPNext"), "fieldname": "ton_kho", "fieldtype": "Float", "width": 140},
		{"label": _("Lệch"), "fieldname": "lech", "fieldtype": "Float", "width": 100},
	]
```

`.../report/doi_soat_ton_vi_tri/doi_soat_ton_vi_tri.js`:

```javascript
frappe.query_reports["Doi Soat Ton Vi Tri"] = {
	filters: [
		{
			fieldname: "kho",
			label: "Kho",
			fieldtype: "Link",
			options: "Warehouse",
			reqd: 1,
			get_query: () => ({ filters: { custom_quan_ly_vi_tri: 1 } }),
		},
	],
};
```

- [ ] **Step 6: Migrate và kiểm bằng mắt**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local migrate
bench --site erptest.local run-tests --app miyano_wms --module miyano_wms.tests.test_doi_soat
```

Mở `http://192.168.61.129:8003/app/query-report/Doi Soat Ton Vi Tri`, chọn kho, xác nhận báo cáo chạy được và **rỗng** (chưa bật kho nào thì không có gì để lệch).

- [ ] **Step 7: Commit**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_wms
git add -A
git commit -m "feat(vitri): đối soát tồn vị trí với tồn kho ERPNext

Lưới an toàn của toàn hệ: so THEO TỪNG (mặt hàng, lô), không chỉ so tổng —
so tổng thôi thì lỗi gộp lô vẫn báo khớp. Tồn kho lấy từ tổng SLE nối qua
Serial and Batch Entry chứ không từ Bin, vì Bin không có chiều lô. Bọc
thành Script Report gọi tay được vì scheduler đang tắt trên erptest.local."
```

---

### Task 11: `Warehouse Location Setup` và thao tác Xem trước

**Files:**
- Create: `apps/miyano_wms/miyano_wms/miyano_wms/doctype/warehouse_location_setup/{__init__.py,warehouse_location_setup.json,warehouse_location_setup.py,warehouse_location_setup.js}`
- Create: `apps/miyano_wms/miyano_wms/vitri/bat_kho.py`
- Test: `apps/miyano_wms/miyano_wms/tests/test_bat_kho_xem_truoc.py`

**Interfaces:**
- Consumes: `vitri.doi_soat.doi_soat_kho` (Task 10)
- Produces: `miyano_wms.vitri.bat_kho.xem_truoc(kho) -> dict` với khoá `so_dong: int`, `so_lo: int`, `so_mat_hang: int`, `canh_bao: list[str]`, `dong: list[dict]` (mỗi phần tử `vat_tu`, `so_lo`, `so_luong`)

- [ ] **Step 1: Viết bài test trước**

`apps/miyano_wms/miyano_wms/tests/test_bat_kho_xem_truoc.py`:

```python
"""Xem trước chuyển đổi — bắt buộc trước khi bật.

Xem trước KHÔNG ĐƯỢC GHI GÌ. Đây là điều duy nhất bài test này khoá, và nó
đáng một bài riêng: một hàm "xem trước" lỡ ghi dữ liệu là thứ không ai nghi
ngờ cho tới khi đã muộn.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_wms.vitri.bat_kho import xem_truoc
from miyano_wms.tests.test_hook_nhap import _tao_item

KHO = "Kho Miyano - MYN"


class TestXemTruoc(FrappeTestCase):
	def test_khong_ghi_gi(self):
		truoc_o = frappe.db.count("Storage Location")
		truoc_so = frappe.db.count("Location Ledger Entry")
		truoc_ton = frappe.db.count("Location Balance")
		co_truoc = frappe.db.get_value("Warehouse", KHO, "custom_quan_ly_vi_tri")

		xem_truoc(KHO)

		self.assertEqual(frappe.db.count("Storage Location"), truoc_o)
		self.assertEqual(frappe.db.count("Location Ledger Entry"), truoc_so)
		self.assertEqual(frappe.db.count("Location Balance"), truoc_ton)
		self.assertEqual(frappe.db.get_value("Warehouse", KHO, "custom_quan_ly_vi_tri"), co_truoc)

	def test_dem_dung_so_mat_hang_va_lo(self):
		kq = xem_truoc(KHO)
		self.assertGreater(kq["so_dong"], 0, "Kho Miyano - MYN đang có tồn nên phải có dòng")
		self.assertEqual(kq["so_dong"], len(kq["dong"]))
		self.assertEqual(kq["so_mat_hang"], len({d["vat_tu"] for d in kq["dong"]}))

	def test_kho_tong_bi_chan(self):
		with self.assertRaises(frappe.ValidationError) as ctx:
			xem_truoc("All Warehouses - MYN")
		self.assertIn("kho tổng", str(ctx.exception).lower())

	def test_kho_da_bat_thi_bao(self):
		frappe.db.set_value("Warehouse", "Stores - MYN", "custom_quan_ly_vi_tri", 1)
		try:
			with self.assertRaises(frappe.ValidationError):
				xem_truoc("Stores - MYN")
		finally:
			frappe.db.set_value("Warehouse", "Stores - MYN", "custom_quan_ly_vi_tri", 0)
```

- [ ] **Step 2: Chạy test, phải ĐỎ**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local run-tests --app miyano_wms --module miyano_wms.tests.test_bat_kho_xem_truoc
```

Kỳ vọng: FAIL — `ModuleNotFoundError: No module named 'miyano_wms.vitri.bat_kho'`.

- [ ] **Step 3: Viết `vitri/bat_kho.py` — phần xem trước**

```python
"""Bốn thao tác bật quản lý vị trí cho một kho: xem trước, bật, tắt, đồng bộ lại.

Bật KHÔNG phải là tích một checkbox. Nó là quy trình chuyển đổi dữ liệu:
tạo ô CHUA-XEP, đọc tồn hiện có TÁCH THEO TỪNG LÔ, ghi sổ chuyển đổi, dựng
tồn, rồi đối soát. Vì vậy `Warehouse.custom_quan_ly_vi_tri` để read-only và
chỉ module này được đặt.
"""

import frappe
from frappe import _
from frappe.utils import flt, now_datetime, nowdate

from miyano_wms.vitri.kho import kho_co_quan_ly_vi_tri, ma_o_chua_xep, xoa_cache_kho


def _kiem_tra_kho(kho, cho_phep_da_bat=False):
	if not frappe.db.exists("Warehouse", kho):
		frappe.throw(_("Không tìm thấy kho {0}.").format(kho))

	if frappe.db.get_value("Warehouse", kho, "is_group"):
		frappe.throw(
			_("{0} là kho tổng, không chứa hàng thật nên không bật quản lý vị trí được. "
			  "Chọn một kho cụ thể.").format(kho)
		)

	if not cho_phep_da_bat and kho_co_quan_ly_vi_tri(kho):
		frappe.throw(_("Kho {0} đã bật quản lý vị trí rồi.").format(kho))


def _ton_hien_co(kho) -> list[dict]:
	"""Tồn hiện có của kho, TÁCH THEO TỪNG LÔ.

	Ghi một dòng cho mỗi (mặt hàng, kho) mà không tách lô thì tổng vẫn khớp
	Bin nhưng chiều lô mất trắng và KHÔNG BAO GIỜ dựng lại được từ dữ liệu
	quá khứ — mọi thứ xây sau đó đứng trên số liệu sai.
	"""
	dong = frappe.db.sql(
		"""
		select sle.item_code as vat_tu,
		       ifnull(sbe.batch_no, ifnull(sle.batch_no, '')) as so_lo,
		       sum(case when sbe.name is not null then sbe.qty else sle.actual_qty end) as sl
		from `tabStock Ledger Entry` sle
		left join `tabSerial and Batch Entry` sbe on sbe.parent = sle.serial_and_batch_bundle
		where sle.warehouse = %s and sle.is_cancelled = 0
		group by sle.item_code, ifnull(sbe.batch_no, ifnull(sle.batch_no, ''))
		having abs(sum(case when sbe.name is not null then sbe.qty else sle.actual_qty end)) > 0.0001
		""",
		(kho,),
		as_dict=True,
	)
	return [
		{"vat_tu": d.vat_tu, "so_lo": d.so_lo or None, "so_luong": flt(d.sl)}
		for d in dong
	]


@frappe.whitelist()
def xem_truoc(kho) -> dict:
	"""Liệt kê những gì việc bật SẼ ghi. Không ghi gì cả."""
	_kiem_tra_kho(kho)
	dong = _ton_hien_co(kho)

	canh_bao = []
	khong_lo = [d for d in dong if not d["so_lo"]]
	if khong_lo:
		canh_bao.append(
			_("{0} dòng là hàng không quản lý lô — sẽ vào ô \"Chưa xếp vị trí\" không kèm số lô.")
			.format(len(khong_lo))
		)
	am = [d for d in dong if d["so_luong"] < 0]
	if am:
		canh_bao.append(
			_("{0} dòng đang có tồn ÂM. Xử lý tồn âm trước khi bật, nếu không ô "
			  "\"Chưa xếp vị trí\" sẽ mang số âm ngay từ đầu.").format(len(am))
		)

	return {
		"kho": kho,
		"so_dong": len(dong),
		"so_lo": len({d["so_lo"] for d in dong if d["so_lo"]}),
		"so_mat_hang": len({d["vat_tu"] for d in dong}),
		"canh_bao": canh_bao,
		"dong": dong,
	}
```

- [ ] **Step 4: Chạy lại test**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local run-tests --app miyano_wms --module miyano_wms.tests.test_bat_kho_xem_truoc
```

Kỳ vọng: 4 bài PASS.

- [ ] **Step 5: Tạo doctype `Warehouse Location Setup`**

`.../doctype/warehouse_location_setup/warehouse_location_setup.json`:

```json
{
 "actions": [],
 "allow_rename": 0,
 "autoname": "field:kho",
 "creation": "2026-09-09 00:00:00.000000",
 "doctype": "DocType",
 "engine": "InnoDB",
 "field_order": [
  "kho", "trang_thai", "col_1", "o_chua_xep", "ngay_bat", "ngay_tat",
  "sec_kq", "so_dong_chuyen_doi", "so_lo_chuyen_doi", "col_2",
  "lan_doi_soat_cuoi", "ket_qua_doi_soat"
 ],
 "fields": [
  {"fieldname": "kho", "fieldtype": "Link", "label": "Kho", "options": "Warehouse", "reqd": 1, "unique": 1, "in_list_view": 1},
  {"fieldname": "trang_thai", "fieldtype": "Select", "label": "Trạng thái", "options": "Chưa bật\nĐang bật\nĐã tắt\nCần đồng bộ lại", "default": "Chưa bật", "read_only": 1, "in_list_view": 1},
  {"fieldname": "col_1", "fieldtype": "Column Break"},
  {"fieldname": "o_chua_xep", "fieldtype": "Link", "label": "Ô \"Chưa xếp vị trí\"", "options": "Storage Location", "read_only": 1},
  {"fieldname": "ngay_bat", "fieldtype": "Datetime", "label": "Bật lúc", "read_only": 1},
  {"fieldname": "ngay_tat", "fieldtype": "Datetime", "label": "Tắt lúc", "read_only": 1},
  {"fieldname": "sec_kq", "fieldtype": "Section Break", "label": "Kết quả lần chuyển đổi gần nhất"},
  {"fieldname": "so_dong_chuyen_doi", "fieldtype": "Int", "label": "Số dòng đã ghi", "read_only": 1},
  {"fieldname": "so_lo_chuyen_doi", "fieldtype": "Int", "label": "Số lô", "read_only": 1},
  {"fieldname": "col_2", "fieldtype": "Column Break"},
  {"fieldname": "lan_doi_soat_cuoi", "fieldtype": "Datetime", "label": "Đối soát lần cuối", "read_only": 1},
  {"fieldname": "ket_qua_doi_soat", "fieldtype": "Small Text", "label": "Kết quả đối soát", "read_only": 1}
 ],
 "index_web_pages_for_search": 0,
 "links": [],
 "modified": "2026-09-09 00:00:00.000000",
 "modified_by": "Administrator",
 "module": "Miyano WMS",
 "name": "Warehouse Location Setup",
 "owner": "Administrator",
 "permissions": [
  {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "report": 1, "export": 1},
  {"role": "Stock Manager", "read": 1, "write": 1, "create": 1, "report": 1}
 ],
 "sort_field": "modified",
 "sort_order": "DESC",
 "states": [],
 "track_changes": 1
}
```

`.../warehouse_location_setup.py`:

```python
import frappe
from frappe import _
from frappe.model.document import Document


class WarehouseLocationSetup(Document):
	def validate(self):
		if frappe.db.get_value("Warehouse", self.kho, "is_group"):
			frappe.throw(
				_("{0} là kho tổng, không chứa hàng thật nên không bật quản lý vị trí được.")
				.format(self.kho)
			)
```

`.../warehouse_location_setup.js`:

```javascript
frappe.ui.form.on("Warehouse Location Setup", {
	refresh(frm) {
		if (frm.is_new()) return;

		if (frm.doc.trang_thai === "Chưa bật") {
			frm.add_custom_button("Xem trước chuyển đổi", () => xem_truoc(frm));
		}
		if (frm.doc.trang_thai === "Đang bật") {
			frm.add_custom_button("Tắt quản lý vị trí", () => goi(frm, "tat", "Đã tắt quản lý vị trí."));
			frm.add_custom_button("Đồng bộ lại", () => goi(frm, "dong_bo_lai", "Đã đồng bộ lại."));
		}
		if (["Đã tắt", "Cần đồng bộ lại"].includes(frm.doc.trang_thai)) {
			frm.add_custom_button("Đồng bộ lại", () => goi(frm, "dong_bo_lai", "Đã đồng bộ lại."));
		}
	},
});

function xem_truoc(frm) {
	frappe.call({
		method: "miyano_wms.vitri.bat_kho.xem_truoc",
		args: { kho: frm.doc.kho },
		freeze: true,
		callback: (r) => {
			const k = r.message;
			const canh_bao = (k.canh_bao || []).map((c) => `<li>${frappe.utils.escape_html(c)}</li>`).join("");
			frappe.confirm(
				`<p>Sẽ ghi <b>${k.so_dong}</b> dòng sổ cho <b>${k.so_mat_hang}</b> mặt hàng,
				 <b>${k.so_lo}</b> lô — tất cả vào ô "Chưa xếp vị trí".</p>
				 ${canh_bao ? `<ul>${canh_bao}</ul>` : ""}
				 <p>Bật quản lý vị trí cho kho này?</p>`,
				() => goi(frm, "bat", "Đã bật quản lý vị trí."),
			);
		},
	});
}

function goi(frm, phuong_thuc, thong_bao) {
	frappe.call({
		method: `miyano_wms.vitri.bat_kho.${phuong_thuc}`,
		args: { kho: frm.doc.kho },
		freeze: true,
		callback: () => {
			frappe.show_alert({ message: thong_bao, indicator: "green" });
			frm.reload_doc();
		},
	});
}
```

- [ ] **Step 6: Migrate và chạy lại test**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local migrate
bench --site erptest.local run-tests --app miyano_wms --module miyano_wms.tests.test_bat_kho_xem_truoc
```

Kỳ vọng: 4 bài PASS. (Nút Bật/Tắt/Đồng bộ lại chưa có backend — Task 12, 13.)

- [ ] **Step 7: Commit**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_wms
git add -A
git commit -m "feat(vitri): doctype Warehouse Location Setup và thao tác Xem trước

Xem trước không ghi gì — có test riêng khoá điều đó lại, vì một hàm xem
trước lỡ ghi dữ liệu là thứ không ai nghi ngờ cho tới khi đã muộn. Đọc tồn
hiện có TÁCH THEO LÔ; cảnh báo hàng không lô và tồn âm trước khi bật."
```

---

### Task 12: Thao tác Bật — một giao dịch, được ăn cả ngã về không

**Files:**
- Modify: `apps/miyano_wms/miyano_wms/vitri/bat_kho.py`
- Test: `apps/miyano_wms/miyano_wms/tests/test_bat_kho.py`

**Interfaces:**
- Consumes: `xem_truoc`, `_ton_hien_co`, `_kiem_tra_kho` (Task 11); `vitri.so.ghi_dong_so`, `dung_lai_ton_vi_tri` (Task 4); `vitri.doi_soat.doi_soat_kho` (Task 10)
- Produces: `miyano_wms.vitri.bat_kho.bat(kho) -> dict` với khoá `so_dong`, `so_lo`, `o_chua_xep`, `doi_soat`

- [ ] **Step 1: Viết bài test trước**

`apps/miyano_wms/miyano_wms/tests/test_bat_kho.py`:

```python
"""Bật quản lý vị trí — được ăn cả ngã về không.

Không có trạng thái "bật được một nửa". Một kho bật dở dang thì mọi con số
sau đó vô nghĩa mà vẫn TRÔNG NHƯ đang chạy — đó là lý do bài
test_bat_that_bai_khong_de_lai_dau_vet quan trọng ngang bài đường thuận.
"""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_wms.vitri import kho as vk
from miyano_wms.vitri.bat_kho import bat
from miyano_wms.vitri.doi_soat import doi_soat_kho

KHO = "Kho Miyano - MYN"


def _don_sach(kho):
	frappe.db.sql("delete from `tabLocation Ledger Entry` where kho=%s", (kho,))
	frappe.db.sql("delete from `tabLocation Balance` where kho=%s", (kho,))
	ma = vk.ma_o_chua_xep(kho)
	frappe.db.sql("delete from `tabStorage Location` where name=%s", (ma,))
	frappe.db.set_value("Warehouse", kho, "custom_quan_ly_vi_tri", 0)
	if frappe.db.exists("Warehouse Location Setup", kho):
		frappe.db.sql("delete from `tabWarehouse Location Setup` where name=%s", (kho,))
	vk.xoa_cache_kho(kho)


class TestBatThanhCong(FrappeTestCase):
	def setUp(self):
		_don_sach(KHO)

	def tearDown(self):
		_don_sach(KHO)

	def test_tao_o_chua_xep(self):
		bat(KHO)
		o = vk.o_chua_xep(KHO)
		self.assertIsNotNone(o)
		self.assertTrue(frappe.db.get_value("Storage Location", o, "la_o_chua_xep"))

	def test_dat_co_tren_warehouse(self):
		bat(KHO)
		self.assertTrue(vk.kho_co_quan_ly_vi_tri(KHO))

	def test_doi_soat_khop_theo_tung_lo(self):
		bat(KHO)
		kq = doi_soat_kho(KHO)
		self.assertTrue(kq["khop"], f"phải khớp sau khi bật, lệch: {kq['dong_lech'][:5]}")

	def test_ghi_mot_dong_cho_moi_lo(self):
		kq = bat(KHO)
		dong = frappe.get_all(
			"Location Ledger Entry", filters={"kho": KHO}, fields=["vat_tu", "so_lo"]
		)
		self.assertEqual(len(dong), kq["so_dong"])
		khoa = {(d.vat_tu, d.so_lo or "") for d in dong}
		self.assertEqual(len(khoa), len(dong), "mỗi (mặt hàng, lô) đúng một dòng")

	def test_ghi_nhan_vao_setup(self):
		bat(KHO)
		st = frappe.get_doc("Warehouse Location Setup", KHO)
		self.assertEqual(st.trang_thai, "Đang bật")
		self.assertTrue(st.ngay_bat)
		self.assertEqual(st.o_chua_xep, vk.o_chua_xep(KHO))


class TestBatThatBai(FrappeTestCase):
	def setUp(self):
		_don_sach(KHO)

	def tearDown(self):
		_don_sach(KHO)

	def test_bat_that_bai_khong_de_lai_dau_vet(self):
		"""Đối soát cuối cùng lệch → phải quay về đúng như trước khi bấm."""
		with patch(
			"miyano_wms.vitri.bat_kho.doi_soat_kho",
			return_value={"kho": KHO, "khop": False, "so_dong_lech": 1,
			              "dong_lech": [{"vat_tu": "X", "so_lo": None,
			                             "ton_vi_tri": 1, "ton_kho": 2, "lech": -1}]},
		):
			with self.assertRaises(frappe.ValidationError):
				bat(KHO)

		self.assertIsNone(vk.o_chua_xep(KHO), "ô CHUA-XEP phải biến mất")
		self.assertEqual(frappe.db.count("Location Ledger Entry", {"kho": KHO}), 0)
		self.assertFalse(vk.kho_co_quan_ly_vi_tri(KHO), "cờ phải vẫn tắt")

	def test_bat_lai_kho_da_bat_thi_chan(self):
		bat(KHO)
		with self.assertRaises(frappe.ValidationError):
			bat(KHO)
```

- [ ] **Step 2: Chạy test, phải ĐỎ**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local run-tests --app miyano_wms --module miyano_wms.tests.test_bat_kho
```

Kỳ vọng: FAIL — `ImportError: cannot import name 'bat'`.

- [ ] **Step 3: Viết thao tác `bat()`**

Thêm vào `apps/miyano_wms/miyano_wms/vitri/bat_kho.py`:

```python
from miyano_wms.vitri.doi_soat import doi_soat_kho
from miyano_wms.vitri.so import dung_lai_ton_vi_tri, ghi_dong_so

CHUNG_TU_CHUYEN_DOI = "Warehouse Location Setup"


@frappe.whitelist()
def bat(kho) -> dict:
	"""Bật quản lý vị trí cho một kho.

	Chạy trong MỘT giao dịch: đối soát cuối cùng mà lệch thì huỷ sạch. Không
	có trạng thái bật nửa vời — một kho bật dở dang thì mọi con số sau đó vô
	nghĩa mà vẫn trông như đang chạy.
	"""
	_kiem_tra_kho(kho)
	dong = _ton_hien_co(kho)
	diem_luu = "truoc_khi_bat"
	frappe.db.savepoint(diem_luu)

	try:
		o = _tao_o_chua_xep(kho)
		luc = now_datetime()
		for d in dong:
			ghi_dong_so(
				o=o, kho=kho, vat_tu=d["vat_tu"], so_lo=d["so_lo"], so_luong=d["so_luong"],
				chung_tu_type=CHUNG_TU_CHUYEN_DOI, chung_tu=kho, chung_tu_row="chuyen-doi",
				sle=None, ngay=nowdate(), thoi_diem=luc,
				company=frappe.db.get_value("Warehouse", kho, "company"),
			)

		dung_lai_ton_vi_tri(kho)

		kq = doi_soat_kho(kho)
		if not kq["khop"]:
			frappe.throw(
				_("Bật quản lý vị trí thất bại: tồn theo vị trí không khớp tồn kho ở {0} dòng. "
				  "Kho được giữ nguyên như trước. Dòng lệch đầu tiên: {1}.")
				.format(kq["so_dong_lech"], frappe.as_json(kq["dong_lech"][:3]))
			)

		frappe.db.set_value("Warehouse", kho, "custom_quan_ly_vi_tri", 1)
		xoa_cache_kho(kho)
		_ghi_setup(kho, {
			"trang_thai": "Đang bật",
			"o_chua_xep": o,
			"ngay_bat": luc,
			"ngay_tat": None,
			"so_dong_chuyen_doi": len(dong),
			"so_lo_chuyen_doi": len({d["so_lo"] for d in dong if d["so_lo"]}),
			"lan_doi_soat_cuoi": luc,
			"ket_qua_doi_soat": _("Khớp"),
		})

	except Exception:
		frappe.db.rollback(save_point=diem_luu)
		xoa_cache_kho(kho)
		raise

	return {
		"kho": kho,
		"so_dong": len(dong),
		"so_lo": len({d["so_lo"] for d in dong if d["so_lo"]}),
		"o_chua_xep": o,
		"doi_soat": kq,
	}


def _tao_o_chua_xep(kho) -> str:
	ma = ma_o_chua_xep(kho)
	if frappe.db.exists("Storage Location", ma):
		return ma
	frappe.get_doc({
		"doctype": "Storage Location",
		"ma_o": ma,
		"ten_o": _("Chưa xếp vị trí"),
		"kho": kho,
		"cap_do": "Ô",
		"la_o_chua_xep": 1,
		"thu_tu_lay_hang": 9999,
	}).insert(ignore_permissions=True)
	return ma


def _ghi_setup(kho, gia_tri: dict):
	if frappe.db.exists("Warehouse Location Setup", kho):
		doc = frappe.get_doc("Warehouse Location Setup", kho)
	else:
		doc = frappe.get_doc({"doctype": "Warehouse Location Setup", "kho": kho})
	doc.update(gia_tri)
	doc.save(ignore_permissions=True)
```

- [ ] **Step 4: Chạy lại test**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local run-tests --app miyano_wms --module miyano_wms.tests.test_bat_kho
```

Kỳ vọng: 7 bài PASS. Nếu `test_bat_that_bai_khong_de_lai_dau_vet` đỏ vì ô `CHUA-XEP` vẫn còn: `Storage Location` là nested set, `insert` có thể commit ngầm — kiểm tra bằng cách xoá tường minh trong nhánh `except` trước khi `rollback`.

- [ ] **Step 5: Commit**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_wms
git add -A
git commit -m "feat(vitri): thao tác Bật — một giao dịch, được ăn cả ngã về không

Tạo ô CHUA-XEP, ghi một dòng sổ cho MỖI LÔ, dựng tồn, rồi đối soát. Đối
soát lệch thì rollback về savepoint: không ô, không dòng sổ, cờ vẫn tắt.
Không có trạng thái bật nửa vời — kho bật dở dang thì mọi con số sau đó vô
nghĩa mà vẫn trông như đang chạy."
```

---

### Task 13: Tắt, chặn bật thẳng lại, và Đồng bộ lại

**Files:**
- Modify: `apps/miyano_wms/miyano_wms/vitri/bat_kho.py`
- Test: `apps/miyano_wms/miyano_wms/tests/test_tat_va_dong_bo.py`

**Interfaces:**
- Consumes: `bat()` (Task 12)
- Produces:
  - `miyano_wms.vitri.bat_kho.tat(kho) -> dict`
  - `miyano_wms.vitri.bat_kho.dong_bo_lai(kho) -> dict` với khoá `so_dong_bu`, `doi_soat`

- [ ] **Step 1: Viết bài test trước**

`apps/miyano_wms/miyano_wms/tests/test_tat_va_dong_bo.py`:

```python
"""Tắt và đồng bộ lại.

Cái bẫy chắc chắn có người dẫm vào nếu không chặn bằng máy: tắt quản lý vị
trí, kho vẫn xuất nhập bình thường (hook bỏ qua), rồi bật lại — tồn vị trí
đứng yên trong khi tồn kho đã đi tiếp. Vì vậy KHÔNG cho bật thẳng lại từ
"Đã tắt"; phải qua Đồng bộ lại.

Đồng bộ lại ghi bút toán BÙ vào CHUA-XEP, không sửa và không xoá dòng cũ —
sổ vẫn chỉ ghi thêm.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_wms.vitri import kho as vk
from miyano_wms.vitri import so
from miyano_wms.vitri.bat_kho import bat, dong_bo_lai, tat
from miyano_wms.vitri.doi_soat import doi_soat_kho
from miyano_wms.tests.test_bat_kho import _don_sach
from miyano_wms.tests.test_hook_nhap import _tao_item

KHO = "Kho Miyano - MYN"


def _nhap(item, qty):
	se = frappe.get_doc({
		"doctype": "Stock Entry", "stock_entry_type": "Material Receipt",
		"company": "Miyano Việt Nam",
		"items": [{"item_code": item, "qty": qty, "t_warehouse": KHO, "basic_rate": 1000}],
	})
	se.insert(ignore_permissions=True)
	se.submit()
	return se


class TestTat(FrappeTestCase):
	def setUp(self):
		_don_sach(KHO)
		bat(KHO)

	def tearDown(self):
		_don_sach(KHO)

	def test_tat_thi_hook_ngung_ghi(self):
		tat(KHO)
		item = _tao_item("_Test Tat Hook")
		truoc = frappe.db.count("Location Ledger Entry", {"kho": KHO})
		_nhap(item, 5)
		self.assertEqual(frappe.db.count("Location Ledger Entry", {"kho": KHO}), truoc)

	def test_tat_khong_xoa_so_cu(self):
		truoc = frappe.db.count("Location Ledger Entry", {"kho": KHO})
		self.assertGreater(truoc, 0)
		tat(KHO)
		self.assertEqual(frappe.db.count("Location Ledger Entry", {"kho": KHO}), truoc)

	def test_trang_thai_thanh_da_tat(self):
		tat(KHO)
		self.assertEqual(
			frappe.db.get_value("Warehouse Location Setup", KHO, "trang_thai"), "Đã tắt"
		)


class TestChanBatThangLai(FrappeTestCase):
	def setUp(self):
		_don_sach(KHO)
		bat(KHO)

	def tearDown(self):
		_don_sach(KHO)

	def test_bat_lai_sau_khi_tat_bi_chan(self):
		tat(KHO)
		with self.assertRaises(frappe.ValidationError) as ctx:
			bat(KHO)
		self.assertIn("đồng bộ lại", str(ctx.exception).lower())


class TestDongBoLai(FrappeTestCase):
	def setUp(self):
		_don_sach(KHO)
		bat(KHO)
		self.item = _tao_item("_Test Dong Bo")

	def tearDown(self):
		_don_sach(KHO)

	def test_bu_phan_lech_vao_o_chua_xep(self):
		tat(KHO)
		_nhap(self.item, 9)          # hook bỏ qua vì đã tắt
		self.assertFalse(doi_soat_kho(KHO)["khop"])

		kq = dong_bo_lai(KHO)

		self.assertTrue(kq["doi_soat"]["khop"], "đồng bộ xong phải khớp")
		o = vk.o_chua_xep(KHO)
		self.assertEqual(so.ton_o(o, self.item, None), 9)

	def test_dong_bo_khong_xoa_dong_cu(self):
		tat(KHO)
		_nhap(self.item, 4)
		truoc = frappe.db.count("Location Ledger Entry", {"kho": KHO})
		dong_bo_lai(KHO)
		self.assertGreater(
			frappe.db.count("Location Ledger Entry", {"kho": KHO}), truoc,
			"đồng bộ phải GHI THÊM bút toán bù, không sửa dòng cũ",
		)

	def test_dong_bo_xong_thi_bat_lai_duoc(self):
		tat(KHO)
		_nhap(self.item, 4)
		dong_bo_lai(KHO)
		self.assertEqual(
			frappe.db.get_value("Warehouse Location Setup", KHO, "trang_thai"), "Đang bật"
		)
		self.assertTrue(vk.kho_co_quan_ly_vi_tri(KHO))
```

- [ ] **Step 2: Chạy test, phải ĐỎ**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local run-tests --app miyano_wms --module miyano_wms.tests.test_tat_va_dong_bo
```

Kỳ vọng: FAIL — `ImportError: cannot import name 'tat'`.

- [ ] **Step 3: Sửa `_kiem_tra_kho` để chặn bật thẳng lại**

Trong `apps/miyano_wms/miyano_wms/vitri/bat_kho.py`, thay hàm `_kiem_tra_kho`:

```python
def _kiem_tra_kho(kho, cho_phep_da_bat=False):
	if not frappe.db.exists("Warehouse", kho):
		frappe.throw(_("Không tìm thấy kho {0}.").format(kho))

	if frappe.db.get_value("Warehouse", kho, "is_group"):
		frappe.throw(
			_("{0} là kho tổng, không chứa hàng thật nên không bật quản lý vị trí được. "
			  "Chọn một kho cụ thể.").format(kho)
		)

	if not cho_phep_da_bat and kho_co_quan_ly_vi_tri(kho):
		frappe.throw(_("Kho {0} đã bật quản lý vị trí rồi.").format(kho))

	trang_thai = frappe.db.get_value("Warehouse Location Setup", kho, "trang_thai")
	if not cho_phep_da_bat and trang_thai in ("Đã tắt", "Cần đồng bộ lại"):
		frappe.throw(
			_("Kho {0} từng bật rồi tắt. Trong lúc tắt kho vẫn xuất nhập nên tồn theo vị trí "
			  "đã lệch — phải chạy \"Đồng bộ lại\" trước, không bật thẳng được.").format(kho)
		)
```

- [ ] **Step 4: Viết `tat()` và `dong_bo_lai()`**

Thêm vào cuối `apps/miyano_wms/miyano_wms/vitri/bat_kho.py`:

```python
@frappe.whitelist()
def tat(kho) -> dict:
	"""Ngừng ghi sổ vị trí cho kho. Sổ cũ giữ nguyên, không xoá dòng nào."""
	_kiem_tra_kho(kho, cho_phep_da_bat=True)
	if not kho_co_quan_ly_vi_tri(kho):
		frappe.throw(_("Kho {0} chưa bật quản lý vị trí.").format(kho))

	frappe.db.set_value("Warehouse", kho, "custom_quan_ly_vi_tri", 0)
	xoa_cache_kho(kho)
	_ghi_setup(kho, {"trang_thai": "Đã tắt", "ngay_tat": now_datetime()})
	return {"kho": kho, "trang_thai": "Đã tắt"}


@frappe.whitelist()
def dong_bo_lai(kho) -> dict:
	"""So tồn vị trí với tồn kho, phần chênh ghi bù vào CHUA-XEP.

	Ghi THÊM bút toán bù, không sửa và không xoá dòng cũ — sổ vẫn chỉ ghi
	thêm. Dùng cho hai tình huống: bật lại sau khi tắt, và khi đối soát báo
	lệch mà chưa rõ nguyên nhân.
	"""
	_kiem_tra_kho(kho, cho_phep_da_bat=True)

	o = _tao_o_chua_xep(kho)
	lech = doi_soat_kho(kho)["dong_lech"]
	luc = now_datetime()
	company = frappe.db.get_value("Warehouse", kho, "company")

	for d in lech:
		bu = flt(d["ton_kho"]) - flt(d["ton_vi_tri"])
		if not bu:
			continue
		ghi_dong_so(
			o=o, kho=kho, vat_tu=d["vat_tu"], so_lo=d["so_lo"], so_luong=bu,
			chung_tu_type=CHUNG_TU_CHUYEN_DOI, chung_tu=kho, chung_tu_row="dong-bo-lai",
			sle=None, ngay=nowdate(), thoi_diem=luc, company=company,
		)

	kq = doi_soat_kho(kho)
	if not kq["khop"]:
		frappe.throw(
			_("Đồng bộ lại xong vẫn còn {0} dòng lệch. Dòng đầu tiên: {1}.")
			.format(kq["so_dong_lech"], frappe.as_json(kq["dong_lech"][:3]))
		)

	frappe.db.set_value("Warehouse", kho, "custom_quan_ly_vi_tri", 1)
	xoa_cache_kho(kho)
	_ghi_setup(kho, {
		"trang_thai": "Đang bật",
		"o_chua_xep": o,
		"lan_doi_soat_cuoi": luc,
		"ket_qua_doi_soat": _("Khớp sau khi đồng bộ lại"),
	})

	return {"kho": kho, "so_dong_bu": len(lech), "doi_soat": kq}
```

- [ ] **Step 5: Chạy lại test**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local run-tests --app miyano_wms --module miyano_wms.tests.test_tat_va_dong_bo
```

Kỳ vọng: 8 bài PASS.

- [ ] **Step 6: Chạy cả bộ**

```bash
bench --site erptest.local run-tests --app miyano_wms
```

Kỳ vọng: toàn bộ PASS.

- [ ] **Step 7: Commit**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_wms
git add -A
git commit -m "feat(vitri): tắt quản lý vị trí, chặn bật thẳng lại, đồng bộ lại

Tắt giữ nguyên sổ cũ. Không cho bật thẳng lại từ 'Đã tắt': trong lúc tắt
kho vẫn xuất nhập nên tồn vị trí đứng yên trong khi tồn kho đi tiếp — cái
bẫy chắc chắn có người dẫm nếu không chặn bằng máy. Đồng bộ lại ghi bút
toán BÙ vào CHUA-XEP, không sửa và không xoá dòng cũ."
```

---

### Task 14: `Location Generator` — sinh mã ô hàng loạt

**Files:**
- Create: `apps/miyano_wms/miyano_wms/miyano_wms/doctype/location_generator/{__init__.py,location_generator.json,location_generator.py,location_generator.js}`
- Create: `apps/miyano_wms/miyano_wms/vitri/sinh_ma.py`
- Test: `apps/miyano_wms/miyano_wms/tests/test_sinh_ma.py`

**Interfaces:**
- Consumes: `Storage Location` (Task 2)
- Produces:
  - `miyano_wms.vitri.sinh_ma.xem_truoc_sinh(kho, tien_to_khu, so_day, so_ke_moi_day, so_tang_moi_ke, mau_ma) -> dict` với khoá `so_o`, `ma_mau: list[str]` (tối đa 20 mã đầu), `trung: list[str]`
  - `miyano_wms.vitri.sinh_ma.sinh(...) -> dict` với khoá `so_o_da_tao`

**Vì sao có task này:** quy tắc đặt mã ô là **cấu hình, không phải code** (quyết định #5 của spec). Chủ dự án chưa cung cấp sơ đồ kho thật, nên thiết kế không được phụ thuộc vào con số dãy/kệ/tầng cụ thể. Mã ô sai chuẩn là thứ về sau đổi rất đau vì tem đã in và người đã quen mã.

- [ ] **Step 1: Viết bài test trước**

`apps/miyano_wms/miyano_wms/tests/test_sinh_ma.py`:

```python
"""Sinh mã ô hàng loạt từ mẫu mã.

Xem trước KHÔNG ghi gì — cùng nguyên tắc với Warehouse Location Setup.
Trùng mã phải phát hiện Ở BƯỚC XEM TRƯỚC, không phải nửa chừng khi ghi:
sinh được 40 ô rồi vỡ ở ô 41 để lại kho nửa vời mà không ai biết ô nào có
ô nào chưa.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_wms.vitri.sinh_ma import sinh, xem_truoc_sinh

KHO = "Kho Miyano - MYN"
MAU = "{khu}-{day:02d}-{ke:02d}-{tang}"


class TestXemTruocSinh(FrappeTestCase):
	def test_dem_dung_so_o(self):
		kq = xem_truoc_sinh(KHO, "TESTZ", so_day=2, so_ke_moi_day=3, so_tang_moi_ke=4, mau_ma=MAU)
		self.assertEqual(kq["so_o"], 24)

	def test_ma_dung_dinh_dang(self):
		kq = xem_truoc_sinh(KHO, "TESTZ", so_day=1, so_ke_moi_day=1, so_tang_moi_ke=1, mau_ma=MAU)
		self.assertEqual(kq["ma_mau"][0], "TESTZ-01-01-1")

	def test_khong_ghi_gi(self):
		truoc = frappe.db.count("Storage Location")
		xem_truoc_sinh(KHO, "TESTZ", so_day=2, so_ke_moi_day=2, so_tang_moi_ke=2, mau_ma=MAU)
		self.assertEqual(frappe.db.count("Storage Location"), truoc)

	def test_bao_ma_trung_truoc_khi_ghi(self):
		sinh(KHO, "TESTTRUNG", so_day=1, so_ke_moi_day=1, so_tang_moi_ke=1, mau_ma=MAU)
		kq = xem_truoc_sinh(KHO, "TESTTRUNG", so_day=1, so_ke_moi_day=1, so_tang_moi_ke=1, mau_ma=MAU)
		self.assertEqual(kq["trung"], ["TESTTRUNG-01-01-1"])

	def test_mau_ma_sai_bao_loi_doc_duoc(self):
		with self.assertRaises(frappe.ValidationError) as ctx:
			xem_truoc_sinh(KHO, "TESTZ", so_day=1, so_ke_moi_day=1, so_tang_moi_ke=1,
			               mau_ma="{khong_co_bien}")
		self.assertIn("mẫu mã", str(ctx.exception).lower())


class TestSinh(FrappeTestCase):
	def test_tao_du_so_o(self):
		kq = sinh(KHO, "TESTS", so_day=2, so_ke_moi_day=2, so_tang_moi_ke=2, mau_ma=MAU)
		self.assertEqual(kq["so_o_da_tao"], 8)
		self.assertTrue(frappe.db.exists("Storage Location", "TESTS-01-01-1"))
		self.assertTrue(frappe.db.exists("Storage Location", "TESTS-02-02-2"))

	def test_o_moi_gan_dung_kho(self):
		sinh(KHO, "TESTK", so_day=1, so_ke_moi_day=1, so_tang_moi_ke=1, mau_ma=MAU)
		self.assertEqual(frappe.db.get_value("Storage Location", "TESTK-01-01-1", "kho"), KHO)

	def test_thu_tu_lay_hang_tang_dan(self):
		sinh(KHO, "TESTT", so_day=1, so_ke_moi_day=1, so_tang_moi_ke=3, mau_ma=MAU)
		a = frappe.db.get_value("Storage Location", "TESTT-01-01-1", "thu_tu_lay_hang")
		b = frappe.db.get_value("Storage Location", "TESTT-01-01-3", "thu_tu_lay_hang")
		self.assertLess(a, b, "thứ tự lấy hàng phải tăng theo trình tự sinh")

	def test_co_ma_trung_thi_chan_truoc_khi_ghi(self):
		sinh(KHO, "TESTD", so_day=1, so_ke_moi_day=1, so_tang_moi_ke=1, mau_ma=MAU)
		with self.assertRaises(frappe.ValidationError):
			sinh(KHO, "TESTD", so_day=1, so_ke_moi_day=2, so_tang_moi_ke=1, mau_ma=MAU)
		self.assertFalse(
			frappe.db.exists("Storage Location", "TESTD-01-02-1"),
			"có mã trùng thì không được ghi ô nào cả",
		)
```

- [ ] **Step 2: Chạy test, phải ĐỎ**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local run-tests --app miyano_wms --module miyano_wms.tests.test_sinh_ma
```

Kỳ vọng: FAIL — `ModuleNotFoundError: No module named 'miyano_wms.vitri.sinh_ma'`.

- [ ] **Step 3: Viết `vitri/sinh_ma.py`**

```python
"""Sinh mã ô hàng loạt từ một mẫu mã.

Quy tắc đặt mã là CẤU HÌNH, không phải code (spec quyết định #5): mặt bằng
kho mỗi nơi một khác, và mã ô là thứ đổi về sau rất đau vì tem đã in và
người đã quen mã.

Trùng mã phải chặn Ở BƯỚC XEM TRƯỚC. Sinh được 40 ô rồi vỡ ở ô 41 để lại
kho nửa vời mà không ai biết ô nào đã có, ô nào chưa.
"""

import frappe
from frappe import _

BIEN_HOP_LE = {"khu", "day", "ke", "tang"}


def _sinh_ma_list(tien_to_khu, so_day, so_ke_moi_day, so_tang_moi_ke, mau_ma) -> list[str]:
	ma = []
	for day in range(1, int(so_day) + 1):
		for ke in range(1, int(so_ke_moi_day) + 1):
			for tang in range(1, int(so_tang_moi_ke) + 1):
				try:
					ma.append(mau_ma.format(khu=tien_to_khu, day=day, ke=ke, tang=tang))
				except (KeyError, IndexError, ValueError):
					frappe.throw(
						_("Mẫu mã không hợp lệ: {0}. Chỉ dùng được các biến {1}. "
						  "Ví dụ đúng: {2}").format(
							mau_ma,
							", ".join("{" + b + "}" for b in sorted(BIEN_HOP_LE)),
							"{khu}-{day:02d}-{ke:02d}-{tang}",
						)
					)
	return ma


@frappe.whitelist()
def xem_truoc_sinh(kho, tien_to_khu, so_day, so_ke_moi_day, so_tang_moi_ke, mau_ma) -> dict:
	"""Liệt kê mã sẽ sinh và mã đã trùng. Không ghi gì."""
	ma = _sinh_ma_list(tien_to_khu, so_day, so_ke_moi_day, so_tang_moi_ke, mau_ma)
	da_co = set(frappe.get_all("Storage Location", filters={"name": ("in", ma)}, pluck="name")) if ma else set()
	return {
		"kho": kho,
		"so_o": len(ma),
		"ma_mau": ma[:20],
		"trung": sorted(da_co),
	}


@frappe.whitelist()
def sinh(kho, tien_to_khu, so_day, so_ke_moi_day, so_tang_moi_ke, mau_ma) -> dict:
	"""Tạo các ô. Có bất kỳ mã trùng nào thì không ghi ô nào cả."""
	kq = xem_truoc_sinh(kho, tien_to_khu, so_day, so_ke_moi_day, so_tang_moi_ke, mau_ma)
	if kq["trung"]:
		frappe.throw(
			_("{0} mã ô đã tồn tại nên không sinh gì cả. Ví dụ: {1}. "
			  "Đổi tiền tố khu hoặc mẫu mã rồi thử lại.")
			.format(len(kq["trung"]), ", ".join(kq["trung"][:5]))
		)

	ma = _sinh_ma_list(tien_to_khu, so_day, so_ke_moi_day, so_tang_moi_ke, mau_ma)
	for i, m in enumerate(ma, start=1):
		frappe.get_doc({
			"doctype": "Storage Location",
			"ma_o": m,
			"kho": kho,
			"cap_do": "Ô",
			"thu_tu_lay_hang": i,
		}).insert(ignore_permissions=True)

	return {"kho": kho, "so_o_da_tao": len(ma)}
```

- [ ] **Step 4: Tạo doctype `Location Generator`**

`.../doctype/location_generator/location_generator.json`:

```json
{
 "actions": [],
 "allow_rename": 1,
 "autoname": "Prompt",
 "creation": "2026-09-09 00:00:00.000000",
 "doctype": "DocType",
 "engine": "InnoDB",
 "field_order": [
  "kho", "tien_to_khu", "col_1", "mau_ma",
  "sec_kich_thuoc", "so_day", "so_ke_moi_day", "col_2", "so_tang_moi_ke", "so_o_da_tao"
 ],
 "fields": [
  {"fieldname": "kho", "fieldtype": "Link", "label": "Kho", "options": "Warehouse", "reqd": 1, "in_list_view": 1},
  {"fieldname": "tien_to_khu", "fieldtype": "Data", "label": "Tiền tố khu", "reqd": 1, "default": "A", "in_list_view": 1, "description": "Ví dụ A → sinh ra A-01-01-1"},
  {"fieldname": "col_1", "fieldtype": "Column Break"},
  {"fieldname": "mau_ma", "fieldtype": "Data", "label": "Mẫu mã ô", "reqd": 1, "default": "{khu}-{day:02d}-{ke:02d}-{tang}", "description": "Biến dùng được: {khu} {day} {ke} {tang}"},
  {"fieldname": "sec_kich_thuoc", "fieldtype": "Section Break", "label": "Kích thước khu"},
  {"fieldname": "so_day", "fieldtype": "Int", "label": "Số dãy", "reqd": 1, "default": "1"},
  {"fieldname": "so_ke_moi_day", "fieldtype": "Int", "label": "Số kệ mỗi dãy", "reqd": 1, "default": "1"},
  {"fieldname": "col_2", "fieldtype": "Column Break"},
  {"fieldname": "so_tang_moi_ke", "fieldtype": "Int", "label": "Số tầng mỗi kệ", "reqd": 1, "default": "1"},
  {"fieldname": "so_o_da_tao", "fieldtype": "Int", "label": "Số ô đã tạo", "read_only": 1}
 ],
 "index_web_pages_for_search": 0,
 "links": [],
 "modified": "2026-09-09 00:00:00.000000",
 "modified_by": "Administrator",
 "module": "Miyano WMS",
 "name": "Location Generator",
 "owner": "Administrator",
 "permissions": [
  {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "report": 1},
  {"role": "Stock Manager", "read": 1, "write": 1, "create": 1, "report": 1}
 ],
 "sort_field": "modified",
 "sort_order": "DESC",
 "states": [],
 "track_changes": 1
}
```

`.../location_generator.py`:

```python
from frappe.model.document import Document


class LocationGenerator(Document):
	pass
```

`.../location_generator.js`:

```javascript
frappe.ui.form.on("Location Generator", {
	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button("Xem trước rồi sinh ô", () => xem_truoc(frm));
	},
});

function xem_truoc(frm) {
	const args = {
		kho: frm.doc.kho,
		tien_to_khu: frm.doc.tien_to_khu,
		so_day: frm.doc.so_day,
		so_ke_moi_day: frm.doc.so_ke_moi_day,
		so_tang_moi_ke: frm.doc.so_tang_moi_ke,
		mau_ma: frm.doc.mau_ma,
	};
	frappe.call({
		method: "miyano_wms.vitri.sinh_ma.xem_truoc_sinh",
		args,
		freeze: true,
		callback: (r) => {
			const k = r.message;
			const mau = k.ma_mau.map((m) => frappe.utils.escape_html(m)).join(", ");
			if (k.trung.length) {
				frappe.msgprint({
					title: "Có mã ô đã tồn tại",
					indicator: "red",
					message: `${k.trung.length} mã đã có: ${k.trung.slice(0, 5).join(", ")}.
					          Đổi tiền tố khu hoặc mẫu mã rồi thử lại.`,
				});
				return;
			}
			frappe.confirm(
				`<p>Sẽ tạo <b>${k.so_o}</b> ô.</p><p>Ví dụ: ${mau}${k.so_o > 20 ? " …" : ""}</p>
				 <p>Mã ô về sau đổi rất khó vì tem đã in và người đã quen mã — kiểm kỹ trước khi tạo.</p>`,
				() => {
					frappe.call({
						method: "miyano_wms.vitri.sinh_ma.sinh",
						args,
						freeze: true,
						callback: (r2) => {
							frm.set_value("so_o_da_tao", r2.message.so_o_da_tao);
							frm.save();
							frappe.show_alert({
								message: `Đã tạo ${r2.message.so_o_da_tao} ô.`,
								indicator: "green",
							});
						},
					});
				},
			);
		},
	});
}
```

- [ ] **Step 5: Migrate và chạy lại test**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local migrate
bench --site erptest.local run-tests --app miyano_wms --module miyano_wms.tests.test_sinh_ma
```

Kỳ vọng: 9 bài PASS.

- [ ] **Step 6: Commit**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_wms
git add -A
git commit -m "feat(vitri): Location Generator — sinh mã ô hàng loạt từ mẫu mã

Quy tắc đặt mã là cấu hình chứ không phải code (spec quyết định #5): mặt
bằng kho mỗi nơi một khác, và mã ô đổi về sau rất đau vì tem đã in. Trùng
mã chặn ở bước xem trước — sinh 40 ô rồi vỡ ở ô 41 để lại kho nửa vời mà
không ai biết ô nào đã có."
```

---

### Task 15: Hai báo cáo còn lại và chốt bộ kiểm thử

**Files:**
- Create: `apps/miyano_wms/miyano_wms/miyano_wms/report/ton_kho_theo_vi_tri/{__init__.py,ton_kho_theo_vi_tri.json,ton_kho_theo_vi_tri.py,ton_kho_theo_vi_tri.js}`
- Create: `apps/miyano_wms/miyano_wms/miyano_wms/report/hang_chua_xep_vi_tri/{__init__.py,hang_chua_xep_vi_tri.json,hang_chua_xep_vi_tri.py,hang_chua_xep_vi_tri.js}`
- Test: `apps/miyano_wms/miyano_wms/tests/test_bao_cao.py`
- Test: `apps/miyano_wms/miyano_wms/tests/test_phan_quyen.py`

**Interfaces:**
- Consumes: `Location Balance` (Task 4), `Storage Location` (Task 2)
- Produces: hai Script Report `Ton Kho Theo Vi Tri`, `Hang Chua Xep Vi Tri`

- [ ] **Step 1: Viết bài test trước**

`apps/miyano_wms/miyano_wms/tests/test_bao_cao.py`:

```python
"""Hai báo cáo vận hành.

"Hàng chưa xếp vị trí" là danh sách việc của thủ kho — nó biến việc bỏ sót
khai vị trí thành hữu hình thay vì thành lỗi. Không có báo cáo này thì ô
CHUA-XEP âm thầm phình ra và không ai biết.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_wms.vitri import kho as vk
from miyano_wms.vitri.bat_kho import bat
from miyano_wms.tests.test_bat_kho import _don_sach
from miyano_wms.tests.test_hook_nhap import _tao_item

KHO = "Kho Miyano - MYN"


class TestBaoCaoTonTheoViTri(FrappeTestCase):
	def setUp(self):
		_don_sach(KHO)
		bat(KHO)

	def tearDown(self):
		_don_sach(KHO)

	def test_chay_duoc_va_co_dong(self):
		from miyano_wms.miyano_wms.report.ton_kho_theo_vi_tri.ton_kho_theo_vi_tri import execute
		cot, dong = execute({"kho": KHO})
		self.assertTrue(cot)
		self.assertTrue(dong, "kho vừa bật có tồn nên phải có dòng")

	def test_khong_hien_o_het_hang(self):
		from miyano_wms.miyano_wms.report.ton_kho_theo_vi_tri.ton_kho_theo_vi_tri import execute
		frappe.db.sql("update `tabLocation Balance` set so_luong = 0 where kho=%s", (KHO,))
		_, dong = execute({"kho": KHO})
		self.assertEqual(dong, [])


class TestBaoCaoHangChuaXep(FrappeTestCase):
	def setUp(self):
		_don_sach(KHO)
		bat(KHO)

	def tearDown(self):
		_don_sach(KHO)

	def test_liet_ke_hang_o_chua_xep(self):
		from miyano_wms.miyano_wms.report.hang_chua_xep_vi_tri.hang_chua_xep_vi_tri import execute
		_, dong = execute({"kho": KHO})
		self.assertTrue(dong, "vừa bật xong thì mọi thứ đang ở CHUA-XEP")

	def test_khong_liet_ke_o_khac(self):
		from miyano_wms.miyano_wms.report.hang_chua_xep_vi_tri.hang_chua_xep_vi_tri import execute
		o_thuong = "TEST-BC-THUONG"
		if not frappe.db.exists("Storage Location", o_thuong):
			frappe.get_doc({
				"doctype": "Storage Location", "ma_o": o_thuong, "kho": KHO, "cap_do": "Ô",
			}).insert(ignore_permissions=True)
		frappe.get_doc({
			"doctype": "Location Balance", "o": o_thuong, "kho": KHO,
			"vat_tu": _tao_item("_Test BC Item"), "so_luong": 5,
		}).insert(ignore_permissions=True)

		_, dong = execute({"kho": KHO})
		self.assertNotIn(o_thuong, [d[0] for d in dong])
```

`apps/miyano_wms/miyano_wms/tests/test_phan_quyen.py`:

```python
"""Phân quyền — điều chịu lực là những quyền KHÔNG có.

Sổ vị trí đáng tin được là nhờ không vai trò nào có create/write/delete;
chỉ engine ghi qua ignore_permissions. Và không doctype nào của app này
được có DocPerm cho Customer hay Website User — bài học từ kho khách hàng:
thiếu DocPerm mới là thứ chịu lực, hook phân quyền một mình không đủ.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

DOCTYPE_CUA_APP = [
	"Storage Location",
	"Location Ledger Entry",
	"Location Balance",
	"Warehouse Location Setup",
	"Location Generator",
]


class TestSoKhongAiGhiDuoc(FrappeTestCase):
	def test_khong_vai_tro_nao_duoc_ghi_so(self):
		for dt in ("Location Ledger Entry", "Location Balance"):
			quyen = frappe.get_all(
				"DocPerm", filters={"parent": dt}, fields=["role", "create", "write", "delete"]
			)
			self.assertTrue(quyen, f"{dt} phải có ít nhất quyền đọc")
			for q in quyen:
				self.assertFalse(q.create, f"{dt}: {q.role} không được có quyền tạo")
				self.assertFalse(q.write, f"{dt}: {q.role} không được có quyền sửa")
				self.assertFalse(q.delete, f"{dt}: {q.role} không được có quyền xoá")

	def test_khong_xoa_duoc_dong_so(self):
		dong = frappe.get_all("Location Ledger Entry", limit=1, pluck="name")
		if not dong:
			self.skipTest("chưa có dòng sổ nào")
		with self.assertRaises(frappe.ValidationError):
			frappe.delete_doc("Location Ledger Entry", dong[0], ignore_permissions=True)


class TestKhongLoRaCong(FrappeTestCase):
	def test_khong_doctype_nao_mo_cho_customer(self):
		for dt in DOCTYPE_CUA_APP:
			vai_tro = frappe.get_all("DocPerm", filters={"parent": dt}, pluck="role")
			for cam in ("Customer", "Website User", "All"):
				self.assertNotIn(
					cam, vai_tro,
					f"{dt} không được có DocPerm cho '{cam}' — xem docstring đầu file",
				)
```

- [ ] **Step 2: Chạy test, phải ĐỎ**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local run-tests --app miyano_wms --module miyano_wms.tests.test_bao_cao
bench --site erptest.local run-tests --app miyano_wms --module miyano_wms.tests.test_phan_quyen
```

Kỳ vọng: `test_bao_cao` FAIL vì chưa có report. `test_phan_quyen` nên PASS ngay — nếu đỏ thì sửa JSON doctype tương ứng cho đúng.

- [ ] **Step 3: Viết báo cáo Tồn kho theo vị trí**

`.../report/ton_kho_theo_vi_tri/__init__.py` — rỗng.

`.../report/ton_kho_theo_vi_tri/ton_kho_theo_vi_tri.json`:

```json
{
 "add_total_row": 0,
 "creation": "2026-09-09 00:00:00.000000",
 "disabled": 0,
 "doctype": "Report",
 "is_standard": "Yes",
 "modified": "2026-09-09 00:00:00.000000",
 "module": "Miyano WMS",
 "name": "Ton Kho Theo Vi Tri",
 "owner": "Administrator",
 "prepared_report": 0,
 "ref_doctype": "Location Balance",
 "report_name": "Ton Kho Theo Vi Tri",
 "report_type": "Script Report",
 "roles": [
  {"role": "System Manager"},
  {"role": "Stock Manager"},
  {"role": "Stock User"}
 ]
}
```

`.../report/ton_kho_theo_vi_tri/ton_kho_theo_vi_tri.py`:

```python
"""Tồn theo từng ô, xếp theo đường đi lấy hàng."""

import frappe
from frappe import _


def execute(filters=None):
	filters = filters or {}
	dieu_kien = ["lb.so_luong != 0"]
	tham_so = {}

	if filters.get("kho"):
		dieu_kien.append("lb.kho = %(kho)s")
		tham_so["kho"] = filters["kho"]
	if filters.get("vat_tu"):
		dieu_kien.append("lb.vat_tu = %(vat_tu)s")
		tham_so["vat_tu"] = filters["vat_tu"]

	dong = frappe.db.sql(
		f"""
		select lb.o, sl.ten_o, lb.kho, lb.vat_tu, lb.so_lo, b.expiry_date, lb.so_luong
		from `tabLocation Balance` lb
		join `tabStorage Location` sl on sl.name = lb.o
		left join `tabBatch` b on b.name = lb.so_lo
		where {' and '.join(dieu_kien)}
		order by ifnull(sl.thu_tu_lay_hang, 0) asc, lb.o asc, lb.vat_tu asc
		""",
		tham_so,
	)
	return _cot(), [list(d) for d in dong]


def _cot():
	return [
		{"label": _("Ô"), "fieldname": "o", "fieldtype": "Link", "options": "Storage Location", "width": 160},
		{"label": _("Tên ô"), "fieldname": "ten_o", "fieldtype": "Data", "width": 160},
		{"label": _("Kho"), "fieldname": "kho", "fieldtype": "Link", "options": "Warehouse", "width": 160},
		{"label": _("Mặt hàng"), "fieldname": "vat_tu", "fieldtype": "Link", "options": "Item", "width": 220},
		{"label": _("Số lô"), "fieldname": "so_lo", "fieldtype": "Link", "options": "Batch", "width": 170},
		{"label": _("Hạn dùng"), "fieldname": "expiry_date", "fieldtype": "Date", "width": 110},
		{"label": _("Số lượng"), "fieldname": "so_luong", "fieldtype": "Float", "width": 110},
	]
```

`.../report/ton_kho_theo_vi_tri/ton_kho_theo_vi_tri.js`:

```javascript
frappe.query_reports["Ton Kho Theo Vi Tri"] = {
	filters: [
		{ fieldname: "kho", label: "Kho", fieldtype: "Link", options: "Warehouse" },
		{ fieldname: "vat_tu", label: "Mặt hàng", fieldtype: "Link", options: "Item" },
	],
};
```

- [ ] **Step 4: Viết báo cáo Hàng chưa xếp vị trí**

`.../report/hang_chua_xep_vi_tri/__init__.py` — rỗng.

`.../report/hang_chua_xep_vi_tri/hang_chua_xep_vi_tri.json`:

```json
{
 "add_total_row": 0,
 "creation": "2026-09-09 00:00:00.000000",
 "disabled": 0,
 "doctype": "Report",
 "is_standard": "Yes",
 "modified": "2026-09-09 00:00:00.000000",
 "module": "Miyano WMS",
 "name": "Hang Chua Xep Vi Tri",
 "owner": "Administrator",
 "prepared_report": 0,
 "ref_doctype": "Location Balance",
 "report_name": "Hang Chua Xep Vi Tri",
 "report_type": "Script Report",
 "roles": [
  {"role": "System Manager"},
  {"role": "Stock Manager"},
  {"role": "Stock User"}
 ]
}
```

`.../report/hang_chua_xep_vi_tri/hang_chua_xep_vi_tri.py`:

```python
"""Hàng đang nằm ở ô "Chưa xếp vị trí" — danh sách việc của thủ kho.

Báo cáo này biến việc bỏ sót khai vị trí thành HỮU HÌNH thay vì thành lỗi.
Không có nó thì ô CHUA-XEP âm thầm phình ra và không ai biết.
"""

import frappe
from frappe import _


def execute(filters=None):
	filters = filters or {}
	dieu_kien = ["sl.la_o_chua_xep = 1", "lb.so_luong != 0"]
	tham_so = {}

	if filters.get("kho"):
		dieu_kien.append("lb.kho = %(kho)s")
		tham_so["kho"] = filters["kho"]

	dong = frappe.db.sql(
		f"""
		select lb.o, lb.kho, lb.vat_tu, lb.so_lo, b.expiry_date, lb.so_luong
		from `tabLocation Balance` lb
		join `tabStorage Location` sl on sl.name = lb.o
		left join `tabBatch` b on b.name = lb.so_lo
		where {' and '.join(dieu_kien)}
		order by lb.kho asc, lb.vat_tu asc
		""",
		tham_so,
	)
	return _cot(), [list(d) for d in dong]


def _cot():
	return [
		{"label": _("Ô"), "fieldname": "o", "fieldtype": "Link", "options": "Storage Location", "width": 200},
		{"label": _("Kho"), "fieldname": "kho", "fieldtype": "Link", "options": "Warehouse", "width": 160},
		{"label": _("Mặt hàng"), "fieldname": "vat_tu", "fieldtype": "Link", "options": "Item", "width": 220},
		{"label": _("Số lô"), "fieldname": "so_lo", "fieldtype": "Link", "options": "Batch", "width": 170},
		{"label": _("Hạn dùng"), "fieldname": "expiry_date", "fieldtype": "Date", "width": 110},
		{"label": _("Số lượng"), "fieldname": "so_luong", "fieldtype": "Float", "width": 110},
	]
```

`.../report/hang_chua_xep_vi_tri/hang_chua_xep_vi_tri.js`:

```javascript
frappe.query_reports["Hang Chua Xep Vi Tri"] = {
	filters: [{ fieldname: "kho", label: "Kho", fieldtype: "Link", options: "Warehouse" }],
};
```

- [ ] **Step 5: Migrate và chạy lại test**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local migrate
bench --site erptest.local run-tests --app miyano_wms --module miyano_wms.tests.test_bao_cao
bench --site erptest.local run-tests --app miyano_wms --module miyano_wms.tests.test_phan_quyen
```

Kỳ vọng: 4 bài báo cáo PASS, 3 bài phân quyền PASS.

- [ ] **Step 6: Chạy toàn bộ và kiểm bằng mắt trên trình duyệt**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local run-tests --app miyano_wms
```

Kỳ vọng: toàn bộ PASS. `ReadTimeout` ngẫu nhiên → chạy lại module đó, đừng kết luận hồi quy ngay.

Rồi mở `http://192.168.61.129:8003` và làm đúng luồng người dùng:

1. Tạo `Location Generator`, khu `A`, 2 dãy × 3 kệ × 4 tầng → bấm **Xem trước rồi sinh ô**, xác nhận hộp thoại báo **24 ô** và ví dụ mã đúng dạng `A-01-01-1`.
2. Tạo `Warehouse Location Setup` cho `Kho Miyano - MYN` → **Xem trước chuyển đổi**, xác nhận số dòng/mặt hàng/lô hợp lý → **Bật**.
3. Mở báo cáo **Doi Soat Ton Vi Tri**, chọn kho → phải **rỗng**.
4. Mở báo cáo **Hang Chua Xep Vi Tri** → phải liệt kê toàn bộ tồn (vừa bật nên mọi thứ ở `CHUA-XEP`).
5. Tạo một Stock Entry Material Receipt vào kho đó → mở lại **Doi Soat Ton Vi Tri**, vẫn phải **rỗng**.
6. Huỷ chính Stock Entry đó → **Doi Soat Ton Vi Tri** vẫn phải **rỗng**.

Bước 5 và 6 là bằng chứng cuối cùng rằng bất biến đứng vững qua cả ghi sổ lẫn huỷ.

- [ ] **Step 7: Commit**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_wms
git add -A
git commit -m "feat(vitri): báo cáo tồn theo vị trí, hàng chưa xếp vị trí, và test phân quyền

'Hàng chưa xếp vị trí' biến việc bỏ sót khai vị trí thành hữu hình thay vì
thành lỗi — không có nó thì ô CHUA-XEP âm thầm phình ra. Test phân quyền
khoá lại những quyền KHÔNG có: không vai trò nào được create/write/delete
sổ vị trí, và không doctype nào mở cho Customer/Website User."
```

---

## Đối chiếu plan với spec

| Mục spec | Task phủ |
|---|---|
| §2 quyết định nền tảng | Global Constraints + Task 1 (app riêng), Task 3 (bật theo kho chỉ định) |
| §3 bất biến + van `CHUA-XEP` | Task 7 (tạo nhánh), Task 10 (đo bất biến), Task 12 (đối soát khi bật) |
| §4.1 một chỗ móc duy nhất | Task 7 |
| §4.2 huỷ đảo đúng ô gốc | Task 9 |
| §4.3 bẫy Stock Reconciliation | Task 6 |
| §4.3b lô từ Serial and Batch Bundle | Task 5 |
| §4.4 định giá lại không sinh sổ | Task 9 Step 6 (chạy cả bộ) — rủi ro R1 vẫn treo, xem dưới |
| §4.5 luồng hook | Task 7, 8, 9 |
| §4.6 kiểm tra hai lớp | **Chỉ lớp chặn cuối** ở plan này. Lớp sớm (`validate` chứng từ) đi cùng bảng phân bổ ở GĐ 2 — chưa có gì để kiểm sớm khi chưa có phân bổ |
| §5.1 `Storage Location` | Task 2 |
| §5.2 `Location Ledger Entry` | Task 4 |
| §5.3 `Location Balance` | Task 4 |
| §5.4 `Location Allocation` | **GĐ 2 — cố ý ngoài phạm vi** |
| §5.5 `Item Location Preference` | **GĐ 2 — cố ý ngoài phạm vi** |
| §5.6 `Location Transfer` | **GĐ 4 — cố ý ngoài phạm vi** |
| §5.7 `Location Count` | **GĐ 4 — cố ý ngoài phạm vi** |
| §5.8 `Location Generator` | Task 14 |
| §5.9 `Warehouse Location Setup` | Task 11, 12, 13 |
| §6.1 nhập kho | Task 7 (nhánh `CHUA-XEP`); gợi ý đặt hàng ở GĐ 2 |
| §6.2 giao hàng | Task 8 (FEFO tự động); nút gợi ý + cột Vị trí trên phiếu in ở GĐ 3 |
| §7 phân quyền | Task 15 |
| §8.1 tồn theo vị trí | Task 15 |
| §8.2 ô trống, sức chứa còn lại | **GĐ 2 — chỉ có nghĩa khi có gợi ý đặt hàng** |
| §8.3 hàng chưa xếp vị trí | Task 15 |
| §8.4 đối soát | Task 10 |
| §8.5 truy vết lô theo vị trí | **GĐ 3 — cùng với luồng giao hàng** |
| §10.1 bài kiểm thử 1–11 | 1→Task 7,9,15 · 2→Task 6 · 3→Task 9 · 4→Task 8 · 4b→Task 5 · 5→GĐ 4 · 6→Task 4 · 7→Task 8 · 8→Task 12 · 9→Task 12 · 10→Task 13 · 11→Task 7 |

**Rủi ro R1 (`Landed Cost Voucher`) vẫn treo có chủ đích.** Spec ghi rõ đây là điều phải kiểm chứng, chưa có cách khắc phục định sẵn — `via_landed_cost_voucher` là tham số Python của `make_sl_entries`, không phải field trên SLE, nên hook không đọc được. Sau Task 9, chạy thêm bước kiểm chứng thủ công: tạo một Purchase Receipt vào kho đã bật, tạo `Landed Cost Voucher` cho nó, rồi mở báo cáo **Doi Soat Ton Vi Tri**. Rỗng → LCV chỉ định giá lại, không cần làm gì. Có dòng lệch → dừng lại, báo, và thiết kế cách xử lý trước khi đi tiếp GĐ 2.

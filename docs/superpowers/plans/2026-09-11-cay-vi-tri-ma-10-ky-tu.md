# Cây vị trí kho và mã ô 10 ký tự — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Đổi mã ô từ 12 xuống 10 ký tự và dựng lại `Storage Location` thành cây 5 cấp có cha con suy ra từ mã, để gộp tồn theo cấp, ngừng dùng cả một nhánh, và chỉ định lấy hàng ở cấp trên.

**Architecture:** Mã ô là nguồn sự thật duy nhất; cây chỉ là hình chiếu của mã — `parent_storage_location` để read-only và do `validate()` tự tính từ tiền tố mã, tự tạo nút cha còn thiếu. Chỉ ô lá (10 ký tự) giữ hàng. `disabled` thừa kế xuống nhánh bằng một vị từ `EXISTS` trên tổ tiên-hoặc-chính-nó, dùng ở **cả hai** truy vấn của FEFO theo hai chiều ngược nhau.

**Tech Stack:** Frappe v15.113.4 · ERPNext v15.83.0 (fork `mvl26/erpnext`, nhánh `feat/mo-rong-vi-tri-kho-warehouse`) · Python 3.12 · MariaDB · `frappe.model.document.Document` → `frappe.utils.nestedset.NestedSet`

**Spec:** `docs/superpowers/specs/2026-09-11-cay-vi-tri-ma-10-ky-tu-design.md`

## Global Constraints

- Bench root là `/home/hoangvietyeuem/frappe-bench-yhct`, site là **`erptest.local`** (không phải `miyano` như CLAUDE.md viết — CLAUDE.md tả máy của đội, không phải máy này).
- Chạy test: `bench --site erptest.local run-tests --module erpnext.warehouse_operations.tests.<tên>`. **KHÔNG** dùng `--app erpnext` (kéo theo hàng nghìn bài upstream).
- **Chỉ chạy MỘT bộ test tại một thời điểm.** Mọi site dùng chung một CSDL; hai bộ chạy song song làm test đỏ giả. Dấu hiệu: module đỏ mà không có số bài.
- Style: **thụt đầu dòng bằng TAB**, dòng ≤ 110 ký tự, nháy kép. Kiểm bằng `ruff` (venv tạm `/tmp/.ruffvenv/bin/ruff`, repo không cài sẵn): `ruff check erpnext/warehouse_operations/` và `ruff format erpnext/warehouse_operations/`.
- Trước mỗi commit: `python3 -m scripts.file_structure --audit` phải ra **0 vi phạm**. Nó chạy `git ls-files` nên phải `git add` trước, không thì không thấy file mới.
- Patch mới đặt ở `erpnext/patches/v15_0/<động_từ>_<danh_từ>.py` và thêm một dòng vào `erpnext/patches.txt`.
- Thông báo lỗi bằng **tiếng Việt**, không lộ traceback. Mọi `@frappe.whitelist()` phải kiểm quyền tường minh.
- Trên `erptest.local` **được xoá/sửa dữ liệu thoải mái** (chủ dự án xác nhận 11/09/2026).
- Mã ô lá: `[Khu 2][Dãy 2][Khoang 2][Tầng 2][Ô 2]` = **`1B01040302`**. Miền: Dãy/Khoang/Ô `01`–`99`, Tầng `01`–`09`, Khu = số + chữ.
- Ô hệ thống `ZZZ-CHUA-XEP-<kho>` **miễn mọi kiểm định dạng và đứng ngoài cây**.

---

## Bố cục file

| File | Trách nhiệm | Task |
|---|---|---|
| `erpnext/warehouse_operations/vitri/ma_vi_tri.py` | Nguồn sự thật DUY NHẤT của quy tắc mã: regex theo cấp, tách thành phần, dựng chuỗi in tem, suy ra mã cha | 1, 2 |
| `erpnext/warehouse_operations/doctype/storage_location/storage_location.json` | Schema: cây, các trường thành phần, `loai_vi_tri` | 2, 7 |
| `.../storage_location.py` | Cưỡng chế định dạng theo cấp, suy cha, tự tạo tổ tiên | 2 |
| `erpnext/warehouse_operations/vitri/sinh_ma.py` | Sinh mã hàng loạt; tạo nút nhóm trước, ô lá sau | 1, 2 |
| `erpnext/warehouse_operations/vitri/so.py` | Ghi sổ; chặn ghi vào nút nhóm | 3 |
| `erpnext/warehouse_operations/vitri/fefo.py` | Chọn ô khi xuất; thừa kế `disabled`; phạm vi | 4, 5 |
| `erpnext/warehouse_operations/report/ton_kho_theo_vi_tri/` | Báo cáo tồn dạng cây, gộp theo cấp | 6 |
| `erpnext/patches/v15_0/don_loai_vi_tri_khong_hop_le.py` | Dọn giá trị `loai_vi_tri` không còn hợp lệ | 7 |
| `erpnext/warehouse_operations/tests/test_cay_vi_tri.py` | Bài kiểm cho cây (mới) | 2, 3 |
| `erpnext/warehouse_operations/tests/test_fefo_pham_vi.py` | Bài kiểm thừa kế `disabled` và phạm vi (mới) | 4, 5 |

---

## Task 1: Mã 10 ký tự

Đổi độ dài mã là thay đổi **nguyên khối**: `ma_vi_tri.py`, doctype, bộ sinh và toàn bộ mã trong test phải đổi cùng lúc, không có trạng thái trung gian nào xanh được.

**Files:**
- Modify: `erpnext/warehouse_operations/vitri/ma_vi_tri.py`
- Modify: `erpnext/warehouse_operations/doctype/storage_location/storage_location.json` (bỏ trường `ma_kho`)
- Modify: `erpnext/warehouse_operations/doctype/storage_location/storage_location.py`
- Modify: `erpnext/warehouse_operations/vitri/sinh_ma.py`
- Test: `erpnext/warehouse_operations/tests/test_ma_vi_tri.py` (viết lại)
- Test: quét mã trong 11 file `tests/test_*.py` còn lại

**Interfaces:**
- Consumes: —
- Produces:
  - `MAU_MA: re.Pattern` — khớp ô lá 10 ký tự
  - `MAU_CAP: list[re.Pattern]` — 5 phần tử, chỉ số 0..4 ứng với cấp 1..5
  - `TEN_CAP: tuple[str, ...]` = `("Khu", "Dãy", "Khoang", "Tầng", "Ô")`
  - `VI_DU: str` = `"1B01040302"`
  - `phan_tich_ma(ma: str) -> dict` — khoá: `khu`, `day`, `khoang`, `tang`, `o`
  - `dinh_dang_nhan(ma: str) -> str` — `"1B0104-0302"`
  - `cap_do(ma: str) -> int` — 1..5, mã sai → throw
  - `ma_cha(ma: str) -> str | None` — `"1B0104"` → `"1B01"`; `"1B"` → `None`

- [ ] **Step 1: Viết bài kiểm mới cho `ma_vi_tri`**

Viết lại `erpnext/warehouse_operations/tests/test_ma_vi_tri.py`. Các bài bắt buộc:

```python
	def test_tach_du_nam_thanh_phan(self):
		self.assertEqual(
			phan_tich_ma("1B01040302"),
			{"khu": "1B", "day": "01", "khoang": "04", "tang": "03", "o": "02"},
		)

	def test_dung_10_ky_tu(self):
		# 12 ký tự là chuẩn CŨ — phải bị từ chối, không được "vẫn nhận cho lành"
		with self.assertRaises(frappe.ValidationError):
			phan_tich_ma("K11B01040302")

	def test_chan_so_khong(self):
		for sai in ("1B00040302", "1B01000302", "1B01040002", "1B01040300"):
			with self.assertRaises(frappe.ValidationError):
				phan_tich_ma(sai)

	def test_tang_toi_da_09(self):
		phan_tich_ma("1B01040902")
		with self.assertRaises(frappe.ValidationError):
			phan_tich_ma("1B01041002")

	def test_khu_so_truoc_chu(self):
		phan_tich_ma("1B01040302")
		with self.assertRaises(frappe.ValidationError):
			phan_tich_ma("B101040302")

	def test_in_nhan(self):
		self.assertEqual(dinh_dang_nhan("1B01040302"), "1B0104-0302")

	def test_in_nhan_vua_gioi_han_nhan(self):
		# Trường F8 của đặc tả nhãn 50x30 v2 giới hạn 16 ký tự kể cả tiền tố
		self.assertLessEqual(len("VT " + dinh_dang_nhan("1B01040302")), 16)

	def test_cap_do(self):
		self.assertEqual(cap_do("1B"), 1)
		self.assertEqual(cap_do("1B01"), 2)
		self.assertEqual(cap_do("1B0104"), 3)
		self.assertEqual(cap_do("1B010403"), 4)
		self.assertEqual(cap_do("1B01040302"), 5)

	def test_cap_do_chan_ma_sai(self):
		for sai in ("1B0", "1B0104030222", "XX"):
			with self.assertRaises(frappe.ValidationError):
				cap_do(sai)

	def test_ma_cha(self):
		self.assertEqual(ma_cha("1B01040302"), "1B010403")
		self.assertEqual(ma_cha("1B01"), "1B")
		self.assertIsNone(ma_cha("1B"), "Khu là gốc, không có cha")
```

- [ ] **Step 2: Chạy để thấy đỏ**

Run: `bench --site erptest.local run-tests --module erpnext.warehouse_operations.tests.test_ma_vi_tri`
Expected: FAIL — `ImportError: cannot import name 'cap_do'` và các bài mã 10 ký tự đỏ vì regex còn đòi 12.

- [ ] **Step 3: Viết lại `ma_vi_tri.py`**

```python
_KHU = r"[0-9][A-Z]"
_HAI_SO_1_99 = r"(?:0[1-9]|[1-9][0-9])"
_HAI_SO_1_09 = r"(?:0[1-9])"

TEN_CAP = ("Khu", "Dãy", "Khoang", "Tầng", "Ô")

# Mỗi cấp là tiền tố của cấp sau. Nhờ vậy mã cha luôn là `ma[:-2]`, và
# cây suy ra từ mã không cần bảng tra nào.
_PHAN = (_KHU, _HAI_SO_1_99, _HAI_SO_1_99, _HAI_SO_1_09, _HAI_SO_1_99)
MAU_CAP = [re.compile("^" + "".join(_PHAN[: i + 1]) + "$") for i in range(5)]

MAU_MA = MAU_CAP[4]
VI_DU = "1B01040302"


def cap_do(ma: str) -> int:
	"""Trả cấp 1..5 của mã. Sai định dạng ở mọi cấp → ném lỗi tiếng Việt."""
	ma = ma or ""
	for i, mau in enumerate(MAU_CAP):
		if mau.match(ma):
			return i + 1
	frappe.throw(
		_(
			"Mã vị trí không đúng chuẩn: {0}\n\n"
			"Ô chứa hàng phải đúng 10 ký tự, không dấu gạch, theo thứ tự "
			"[Khu 2][Dãy 2][Khoang 2][Tầng 2][Ô 2] — ví dụ {1} "
			"(khu 1B, dãy 01, khoang 04, tầng 03, ô 02).\n"
			"Nút nhóm là tiền tố của mã đó: 1B / 1B01 / 1B0104 / 1B010403.\n"
			"Dãy, Khoang và Ô nhận 01–99; Tầng nhận 01–09."
		).format(ma or "(trống)", VI_DU)
	)


def phan_tich_ma(ma: str) -> dict:
	"""Tách mã ô LÁ (10 ký tự) thành 5 thành phần."""
	khop = MAU_MA.match(ma or "")
	if not khop:
		cap_do(ma)  # ném lỗi có thông báo đầy đủ
		frappe.throw(_("Mã {0} là nút nhóm, không phải ô chứa hàng.").format(ma))
	return {
		"khu": ma[0:2], "day": ma[2:4], "khoang": ma[4:6],
		"tang": ma[6:8], "o": ma[8:10],
	}


def dinh_dang_nhan(ma: str) -> str:
	"""Dạng IN lên nhãn ô: `1B0104-0302` (một gạch trước Tầng-Ô)."""
	p = phan_tich_ma(ma)
	return f"{p['khu']}{p['day']}{p['khoang']}-{p['tang']}{p['o']}"


def ma_cha(ma: str) -> str | None:
	"""Mã của nút cha = chính mã đó bỏ 2 ký tự cuối. Khu (cấp 1) không có cha."""
	if cap_do(ma) == 1:
		return None
	return ma[:-2]
```

Cập nhật docstring đầu module: mã **10** ký tự, và ghi rõ vì sao bỏ 2 ký tự mã kho (bản ghi đã có trường `kho` trỏ `Warehouse`; lưu hai chỗ thì lệch).

- [ ] **Step 4: Chạy lại — phải xanh**

Run: `bench --site erptest.local run-tests --module erpnext.warehouse_operations.tests.test_ma_vi_tri`
Expected: PASS.

- [ ] **Step 5: Bỏ trường `ma_kho` khỏi doctype và controller**

Trong `storage_location.json`: xoá phần tử `"ma_kho"` khỏi `field_order` và khỏi mảng `fields`.

Trong `storage_location.py`, hàm `tach_thanh_phan_ma()`:

```python
		p = phan_tich_ma(self.ma_o)
		self.khu, self.day = p["khu"], p["day"]
		self.khoang, self.tang, self.o = p["khoang"], p["tang"], p["o"]
		self.ma_in_nhan = dinh_dang_nhan(self.ma_o)
```

- [ ] **Step 6: Bỏ mã kho khỏi bộ sinh**

Trong `sinh_ma.py`: xoá hàm `_ma_kho_cua()` và lời gọi tới nó; công thức mã thành

```python
	ma = [
		f"{khu}{d:02d}{k:02d}{t:02d}{o:02d}"
		for d in range(1, so_day + 1)
		for k in range(1, so_khoang_moi_day + 1)
		for t in range(1, so_tang_moi_khoang + 1)
		for o in range(1, so_o_moi_tang + 1)
	]
```

Ghi vào docstring module: `Warehouse.custom_ma_kho_spd` **không còn được dùng** ở đây (Task 7 gỡ hẳn).

- [ ] **Step 7: Quét mã trong 11 file test còn lại**

Quy tắc đổi: bỏ 2 ký tự đầu của mọi mã ô trong test — `K19Z18010101` → `9Z18010101`. Khu `9Z` tiếp tục dành riêng cho test.

**Bắt buộc giữ nguyên hai thế nghịch đảo đã dựng** (xoá đi là mất khả năng bắt đột biến):
- `test_fefo.py` — hai ô thật có thứ tự tên NGƯỢC thứ tự ưu tiên (`…0101` thu_tu=5 vs `…0102` thu_tu=1). Sau khi bỏ 2 ký tự đầu, quan hệ tên vẫn giữ nguyên thứ tự, nên chỉ cần đổi mã.
- `ZZZ-CHUA-XEP` vẫn phải xếp sau mọi mã hợp lệ theo alphabet — mã mới bắt đầu bằng chữ số, vẫn đứng trước `Z`, nên tính chất này được giữ.

- [ ] **Step 8: Chạy CẢ BỘ, tuần tự**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
for f in apps/erpnext/erpnext/warehouse_operations/tests/test_*.py; do
  m=$(basename $f .py)
  bench --site erptest.local run-tests --module erpnext.warehouse_operations.tests.$m 2>&1 \
    | tr '\r' '\n' | grep -E "^Ran |^OK|^FAILED" | paste -sd' ' - | sed "s|^|  $m  |"
done
```
Expected: mọi module OK.

- [ ] **Step 9: Lint và audit**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/erpnext
/tmp/.ruffvenv/bin/ruff check erpnext/warehouse_operations/ && /tmp/.ruffvenv/bin/ruff format erpnext/warehouse_operations/
git add -A erpnext/warehouse_operations && python3 -m scripts.file_structure --audit
```
Expected: ruff không báo gì; audit ra `0 vi pham`.

- [ ] **Step 10: Commit**

```bash
git commit -m "feat(vi_tri_kho): ma o 10 ky tu, bo 2 ky tu ma kho

Ban ghi da co truong kho tro Warehouse; luu ma kho them lan nua trong
chuoi la hai nguon su that cho cung mot thong tin. Trung khop luon ma
kho SPD Nhat trong tai lieu goc (4B01-04-0302).

Them cap_do() va ma_cha() lam nen cho cay o Task 2."
```

---

## Task 2: Cây suy ra từ mã

**Files:**
- Modify: `erpnext/warehouse_operations/doctype/storage_location/storage_location.json`
- Modify: `erpnext/warehouse_operations/doctype/storage_location/storage_location.py`
- Modify: `erpnext/warehouse_operations/vitri/sinh_ma.py`
- Create: `erpnext/warehouse_operations/tests/test_cay_vi_tri.py`

**Interfaces:**
- Consumes: `cap_do()`, `ma_cha()`, `TEN_CAP` từ Task 1
- Produces:
  - `StorageLocation` kế thừa `frappe.utils.nestedset.NestedSet`
  - Trường mới: `is_group` (Check), `parent_storage_location` (Link, read_only), `lft`/`rgt` (Int, hidden), `old_parent` (Data, hidden)
  - `StorageLocation.dam_bao_to_tien()` — tạo các nút cha còn thiếu, trả tên cha trực tiếp

- [ ] **Step 1: Viết bài kiểm cho cây**

Tạo `erpnext/warehouse_operations/tests/test_cay_vi_tri.py`:

```python
"""Cây vị trí là HÌNH CHIẾU của mã, không phải dữ liệu độc lập.

Mọi bài ở đây khoá đúng một điều: không tồn tại thao tác nào của người dùng
đặt được cây lệch khỏi mã. Đó là lý do spec 2026-09-09 từng bỏ cây đi, và là
điều kiện để dựng lại nó.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

KHO = "Kho Miyano - MYN"


def _o(ma):
	if not frappe.db.exists("Storage Location", ma):
		frappe.get_doc({"doctype": "Storage Location", "ma_o": ma, "kho": KHO}).insert(
			ignore_permissions=True
		)
	return ma


class TestCaySuyTuMa(FrappeTestCase):
	def test_tu_sinh_du_to_tien(self):
		_o("9Z18010101")
		for cha in ("9Z", "9Z18", "9Z1801", "9Z180101"):
			self.assertTrue(frappe.db.exists("Storage Location", cha), f"thiếu nút {cha}")

	def test_cha_dung_theo_ma(self):
		_o("9Z18010101")
		self.assertEqual(
			frappe.db.get_value("Storage Location", "9Z18010101", "parent_storage_location"),
			"9Z180101",
		)

	def test_nut_nhom_la_is_group(self):
		_o("9Z18010101")
		for cha in ("9Z", "9Z18", "9Z1801", "9Z180101"):
			self.assertTrue(frappe.db.get_value("Storage Location", cha, "is_group"), cha)
		self.assertFalse(
			frappe.db.get_value("Storage Location", "9Z18010101", "is_group"),
			"ô lá không được là nút nhóm",
		)

	def test_sua_tay_cha_bi_ghi_de_ve_dung(self):
		"""`parent` là read_only trên form, nhưng API vẫn đặt được — chặn ở validate."""
		_o("9Z18010101")
		_o("9Z18020101")
		d = frappe.get_doc("Storage Location", "9Z18010101")
		d.parent_storage_location = "9Z180201"  # sai: thuộc dãy 02
		d.save(ignore_permissions=True)
		self.assertEqual(
			frappe.db.get_value("Storage Location", "9Z18010101", "parent_storage_location"),
			"9Z180101",
			"cha phải được tính lại từ mã, không nhận giá trị người dùng đặt",
		)

	def test_o_chua_xep_dung_ngoai_cay(self):
		from erpnext.warehouse_operations.vitri.bat_kho import tao_o_chua_xep

		ma = tao_o_chua_xep(KHO)
		self.assertIsNone(
			frappe.db.get_value("Storage Location", ma, "parent_storage_location"),
			"ô hệ thống không thuộc cây — nó không ứng với chỗ nào ngoài kho",
		)

	def test_nut_nhom_khong_bi_ep_dinh_dang_o_la(self):
		"""Nút nhóm có mã 2/4/6/8 ký tự — không được đòi đủ 10."""
		_o("9Z18010101")
		self.assertEqual(frappe.db.get_value("Storage Location", "9Z18", "ma_o"), "9Z18")

	def test_ma_sai_cap_bi_chan(self):
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				{"doctype": "Storage Location", "ma_o": "9Z180", "kho": KHO}
			).insert(ignore_permissions=True)
```

- [ ] **Step 2: Chạy để thấy đỏ**

Run: `bench --site erptest.local run-tests --module erpnext.warehouse_operations.tests.test_cay_vi_tri`
Expected: FAIL — chưa có `parent_storage_location`, các bài tổ tiên đỏ.

- [ ] **Step 3: Thêm các trường cây vào doctype**

Trong `storage_location.json`, thêm vào `field_order` sau `kho`: `"is_group"`, `"parent_storage_location"`; và cuối mảng: `"lft"`, `"rgt"`, `"old_parent"`. Thêm vào `fields`:

```json
  {"fieldname": "is_group", "fieldtype": "Check", "label": "Là nút nhóm", "read_only": 1,
   "description": "Nút nhóm là cấp Khu/Dãy/Khoang/Tầng — không chứa hàng."},
  {"fieldname": "parent_storage_location", "fieldtype": "Link", "label": "Thuộc",
   "options": "Storage Location", "read_only": 1, "search_index": 1,
   "description": "Tự tính từ mã ô. Sửa mã thì sửa luôn chỗ đứng trong cây."},
  {"fieldname": "lft", "fieldtype": "Int", "label": "lft", "hidden": 1, "no_copy": 1, "print_hide": 1},
  {"fieldname": "rgt", "fieldtype": "Int", "label": "rgt", "hidden": 1, "no_copy": 1, "print_hide": 1},
  {"fieldname": "old_parent", "fieldtype": "Data", "label": "old_parent", "hidden": 1, "no_copy": 1, "print_hide": 1}
```

Ở cấp doctype, thêm hai khoá: `"is_tree": 1` và `"nsm_parent_field": "parent_storage_location"`.

- [ ] **Step 4: Cho controller kế thừa NestedSet và tự suy cha**

Trong `storage_location.py`:

```python
from frappe.utils.nestedset import NestedSet

from erpnext.warehouse_operations.vitri.ma_vi_tri import cap_do, dinh_dang_nhan, ma_cha, phan_tich_ma


class StorageLocation(NestedSet):
	nsm_parent_field = "parent_storage_location"

	def validate(self):
		self.kiem_tra_ma_o_khong_doi()
		self.dung_cho_trong_cay()
		self.tach_thanh_phan_ma()
		self.kiem_tra_kho()
		self.kiem_tra_khong_doi_dang_o_chua_xep()
		if not self.barcode:
			self.barcode = self.ma_o

	def dung_cho_trong_cay(self):
		"""Tính `is_group` và `parent` TỪ MÃ, ghi đè mọi giá trị người dùng đặt.

		Ghi đè chứ không phải báo lỗi: `parent` là read_only trên form nên
		người dùng bình thường không đặt được, còn đường API/Data Import thì
		đặt được — và ở đó im lặng sửa về đúng tốt hơn là chặn một thao tác
		nhập liệu hàng loạt.
		"""
		if self.la_o_chua_xep:
			self.is_group = 0
			self.parent_storage_location = None
			return

		cap = cap_do(self.ma_o)
		self.is_group = 1 if cap < 5 else 0
		self.parent_storage_location = self.dam_bao_to_tien()

	def dam_bao_to_tien(self) -> str | None:
		"""Tạo các nút cha còn thiếu, từ gốc xuống. Trả tên cha trực tiếp."""
		cha = ma_cha(self.ma_o)
		if not cha:
			return None
		if not frappe.db.exists("Storage Location", cha):
			frappe.get_doc(
				{"doctype": "Storage Location", "ma_o": cha, "kho": self.kho}
			).insert(ignore_permissions=True)
		return cha

	def tach_thanh_phan_ma(self):
		"""Ô LÁ tách đủ 5 thành phần; nút nhóm chỉ điền phần nó có."""
		if self.la_o_chua_xep:
			return
		if self.is_group:
			phan = ("khu", "day", "khoang", "tang")[: cap_do(self.ma_o)]
			for i, ten in enumerate(phan):
				setattr(self, ten, self.ma_o[i * 2 : i * 2 + 2])
			self.ma_in_nhan = None
			return
		p = phan_tich_ma(self.ma_o)
		self.khu, self.day = p["khu"], p["day"]
		self.khoang, self.tang, self.o = p["khoang"], p["tang"], p["o"]
		self.ma_in_nhan = dinh_dang_nhan(self.ma_o)
```

`dam_bao_to_tien()` đệ quy tự nhiên: nút cha khi được `insert()` cũng chạy `validate()` và tự tạo cha của nó.

- [ ] **Step 5: Bộ sinh tạo nút nhóm trước**

Trong `sinh_ma.py`, hàm `sinh()`: trước vòng tạo ô lá, tạo tất cả nút nhóm theo thứ tự **từ gốc xuống**, để tránh nhiều lần chèn lồng nhau tranh khoá `lft/rgt`:

```python
	nhom = sorted({m[:i] for m in ma for i in (2, 4, 6, 8)}, key=len)
	for n in nhom:
		if not frappe.db.exists("Storage Location", n):
			frappe.get_doc(
				{"doctype": "Storage Location", "ma_o": n, "kho": kho}
			).insert(ignore_permissions=True)
```

- [ ] **Step 6: Migrate rồi chạy bài kiểm cây**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local migrate
bench --site erptest.local run-tests --module erpnext.warehouse_operations.tests.test_cay_vi_tri
```
Expected: PASS.

- [ ] **Step 7: Chạy cả bộ, lint, audit, commit**

Dùng vòng lặp ở Task 1 Step 8. Sửa các bài đỏ do đổi `is_group` nếu có. Rồi:

```bash
git add -A erpnext/warehouse_operations
git commit -m "feat(vi_tri_kho): cay vi tri suy ra tu ma

parent_storage_location read_only, validate() tu tinh tu tien to ma va tu
tao nut cha con thieu. Ma van la nguon su that duy nhat; cay chi la hinh
chieu, khong co thao tac nao dat duoc no lech.

Spec 2026-09-09 bo cay vi 'hai nguon su that' — ly do do chi ap cho cay
khai bang tay."
```

---

## Task 3: Chặn ghi sổ vào nút nhóm

**Files:**
- Modify: `erpnext/warehouse_operations/vitri/so.py`
- Test: `erpnext/warehouse_operations/tests/test_cay_vi_tri.py` (thêm lớp)

**Interfaces:**
- Consumes: `is_group` từ Task 2
- Produces: `ghi_dong_so()` ném `frappe.ValidationError` khi `o` là nút nhóm

- [ ] **Step 1: Viết bài kiểm**

Thêm vào `test_cay_vi_tri.py`:

```python
class TestKhongGhiSoVaoNutNhom(FrappeTestCase):
	def test_ghi_vao_nut_nhom_bi_chan(self):
		"""Nếu lọt, báo cáo gộp theo cấp sẽ đếm HAI LẦN cùng một lượng hàng:
		một lần ở nút nhóm, một lần khi cộng dồn các ô lá bên dưới.
		"""
		from erpnext.warehouse_operations.vitri import so

		_o("9Z18010101")
		with self.assertRaises(frappe.ValidationError) as ctx:
			so.ghi_dong_so(
				o="9Z1801", kho=KHO, vat_tu="_Test Item", so_lo=None, so_luong=5,
				chung_tu_type="Storage Location", chung_tu="9Z1801", chung_tu_row="r",
				sle=None, ngay="2026-09-01", thoi_diem="2026-09-01 08:00:00",
				company="Miyano Việt Nam",
			)
		self.assertIn("nhóm", str(ctx.exception).lower())
```

- [ ] **Step 2: Chạy để thấy đỏ**

Run: `bench --site erptest.local run-tests --module erpnext.warehouse_operations.tests.test_cay_vi_tri`
Expected: FAIL — không có ngoại lệ nào được ném.

- [ ] **Step 3: Thêm kiểm tra vào `ghi_dong_so`**

Ngay đầu hàm, sau khi đã có `o`:

```python
	if frappe.db.get_value("Storage Location", o, "is_group"):
		frappe.throw(
			_(
				"{0} là nút nhóm (cấp Khu/Dãy/Khoang/Tầng), không chứa hàng được. "
				"Chỉ ô lá 10 ký tự mới giữ hàng."
			).format(o)
		)
```

- [ ] **Step 4: Chạy lại — xanh. Rồi chạy cả bộ, lint, audit, commit**

```bash
git commit -m "feat(vi_tri_kho): chan ghi so vao nut nhom

Lot qua thi bao cao gop theo cap dem hai lan cung mot luong hang."
```

---

## Task 4: `disabled` thừa kế xuống nhánh

Đây là task nguy hiểm nhất của cả kế hoạch. Đọc §6.2 của spec trước khi làm.

**Files:**
- Modify: `erpnext/warehouse_operations/vitri/fefo.py`
- Create: `erpnext/warehouse_operations/tests/test_fefo_pham_vi.py`

**Interfaces:**
- Consumes: `lft`/`rgt` từ Task 2
- Produces: hằng `_TO_TIEN_TAT` (chuỗi SQL) dùng chung cho cả hai truy vấn

- [ ] **Step 1: Viết bài kiểm**

Tạo `erpnext/warehouse_operations/tests/test_fefo_pham_vi.py`. Dựng hai ô ở hai dãy khác nhau, cùng mặt hàng, rồi tắt nút **dãy**:

```python
	def test_tat_nut_day_thi_khong_lay_o_trong_day(self):
		# 9Z1801xxxx có hạn dùng GẦN HƠN, lẽ ra được ưu tiên. Tắt cả dãy 01
		# thì phải bỏ qua nó và lấy dãy 02 — dù FEFO muốn ngược lại.
		frappe.db.set_value("Storage Location", "9Z1801", "disabled", 1)
		ket = chon_o_xuat(KHO, self.item, None, 5)
		self.assertTrue(all(not d["o"].startswith("9Z1801") for d in ket), ket)

	def test_tat_nut_khu_thi_bao_ro_hang_dang_ket_o_dau(self):
		"""Khoá nửa thứ hai: thông báo thiếu hàng phải NÊU ĐÍCH DANH ô đang giữ.

		Sửa mỗi truy vấn chọn ứng viên thì hàng dưới nút cha đã tắt biến mất
		khỏi CẢ HAI câu — không được chọn, cũng không được nhắc — và người dùng
		nhận đúng câu "thiếu hàng" vô nghĩa.
		"""
		frappe.db.set_value("Storage Location", "9Z", "disabled", 1)
		with self.assertRaises(frappe.ValidationError) as ctx:
			chon_o_xuat(KHO, self.item, None, 5)
		loi = str(ctx.exception)
		self.assertIn("ngừng dùng", loi.lower())
		self.assertIn("9Z18010101", loi, "phải nêu đích danh ô đang giữ hàng")
```

- [ ] **Step 2: Chạy để thấy đỏ**

Run: `bench --site erptest.local run-tests --module erpnext.warehouse_operations.tests.test_fefo_pham_vi`
Expected: FAIL — FEFO vẫn lấy hàng từ dãy đã tắt (chỉ kiểm `disabled` của chính ô lá).

- [ ] **Step 3: Sửa CẢ HAI truy vấn**

Thêm vào đầu `fefo.py` một vị từ dùng chung:

```python
# Tổ-tiên-HOẶC-CHÍNH-NÓ: điều kiện `lft <= sl.lft and rgt >= sl.rgt` đúng cho
# cả chính nút đó, nên vị từ này thay luôn phép kiểm `sl.disabled` cũ.
#
# Dùng ở HAI chỗ theo HAI CHIỀU ngược nhau. Sửa một chỗ quên chỗ kia thì hàng
# nằm dưới một nút cha bị tắt biến mất khỏi cả hai: không được chọn, mà cũng
# không được nhắc tới trong thông báo thiếu hàng.
_TO_TIEN_TAT = """exists (
    select 1 from `tabStorage Location` tt
    where tt.lft <= sl.lft and tt.rgt >= sl.rgt
      and ifnull(tt.disabled, 0) = 1
)"""
```

Trong truy vấn chọn ứng viên, thay `and ifnull(sl.disabled, 0) = 0` bằng:

```python
		      and not {_TO_TIEN_TAT}
```

Trong truy vấn dựng thông báo, thay `and ifnull(sl.disabled, 0) = 1` bằng:

```python
			      and {_TO_TIEN_TAT}
```

Lưu ý: ô `ZZZ-CHUA-XEP` đứng ngoài cây nên `lft`/`rgt` của nó là một khoảng riêng, không nút nào bao — vị từ trả `false` khi chính nó không `disabled`, đúng như mong muốn.

- [ ] **Step 4: Chạy lại — xanh**

- [ ] **Step 5: ĐỘT BIẾN — bắt buộc, không được bỏ**

Xoá mệnh đề `not {_TO_TIEN_TAT}` khỏi truy vấn thứ nhất (để lại `1=1`), chạy lại `test_fefo_pham_vi`:
Expected: **FAIL** ở `test_tat_nut_day_thi_khong_lay_o_trong_day`.

Rồi khôi phục, và xoá mệnh đề `{_TO_TIEN_TAT}` khỏi truy vấn thứ hai, chạy lại:
Expected: **FAIL** ở `test_tat_nut_khu_thi_bao_ro_hang_dang_ket_o_dau`.

Khôi phục cả hai. Bài nào không đỏ được khi đột biến thì **chưa khoá được gì** — sửa bài cho tới khi đỏ.

- [ ] **Step 6: Chạy cả bộ, lint, audit, commit**

```bash
git commit -m "fix(vi_tri_kho): disabled thua ke xuong ca nhanh

Truoc: FEFO chi kiem disabled cua chinh o la. Tat ca mot day de sua ke thi
he van rut hang tu day do, va KHONG CO GI BAO — doi soat van khop vi tong
khong doi.

Sua CA HAI truy van cua fefo.py bang mot vi tu to-tien-hoac-chinh-no, dung
theo hai chieu nguoc nhau. Da dot bien kiem chung tung chieu."
```

---

## Task 5: Chỉ định lấy hàng theo phạm vi

**Files:**
- Modify: `erpnext/warehouse_operations/vitri/fefo.py`
- Test: `erpnext/warehouse_operations/tests/test_fefo_pham_vi.py`

**Interfaces:**
- Consumes: `_TO_TIEN_TAT` từ Task 4
- Produces: `chon_o_xuat(kho, vat_tu, so_lo, so_luong, pham_vi=None)` — `pham_vi` là tên một `Storage Location` bất kỳ cấp nào; `None` = toàn kho

- [ ] **Step 1: Viết bài kiểm**

```python
	def test_pham_vi_gioi_han_trong_nhanh(self):
		# dãy 02 có hạn dùng XA HƠN, FEFO bình thường sẽ không chọn nó
		ket = chon_o_xuat(KHO, self.item, None, 5, pham_vi="9Z1802")
		self.assertTrue(all(d["o"].startswith("9Z1802") for d in ket), ket)

	def test_pham_vi_rong_giu_nguyen_hanh_vi_cu(self):
		self.assertEqual(
			chon_o_xuat(KHO, self.item, None, 5),
			chon_o_xuat(KHO, self.item, None, 5, pham_vi=None),
		)

	def test_pham_vi_khong_ton_tai_bao_loi_tieng_viet(self):
		with self.assertRaises(frappe.ValidationError) as ctx:
			chon_o_xuat(KHO, self.item, None, 5, pham_vi="9Z9999")
		self.assertIn("không tồn tại", str(ctx.exception).lower())
```

- [ ] **Step 2: Chạy để thấy đỏ**

Expected: FAIL — `chon_o_xuat() got an unexpected keyword argument 'pham_vi'`.

- [ ] **Step 3: Cài đặt**

```python
def chon_o_xuat(kho, vat_tu, so_lo, so_luong: float, pham_vi: str | None = None) -> list[dict]:
	...
	loc_pham_vi = ""
	tham_so = {"kho": kho, "vat_tu": vat_tu, "so_lo": so_lo or "", "han_xa": HAN_XA}
	if pham_vi:
		moc = frappe.db.get_value("Storage Location", pham_vi, ["lft", "rgt"], as_dict=True)
		if not moc:
			frappe.throw(_("Vị trí {0} không tồn tại.").format(pham_vi))
		loc_pham_vi = "and sl.lft between %(pv_lft)s and %(pv_rgt)s"
		tham_so.update({"pv_lft": moc.lft, "pv_rgt": moc.rgt})
```

Chèn `{loc_pham_vi}` vào **cả hai** truy vấn (thông báo thiếu hàng cũng phải giới hạn trong phạm vi, không thì nó đi mách hàng ở nhánh mà người dùng không hỏi tới), và đổi hai lời gọi `frappe.db.sql` sang dùng `tham_so`.

- [ ] **Step 4: Chạy lại — xanh. Rồi cả bộ, lint, audit, commit**

```bash
git commit -m "feat(vi_tri_kho): chon o xuat theo pham vi mot nhanh

pham_vi nhan ten mot nut bat ky cap nao; rong = toan kho, giu nguyen hanh
vi cu (co bai khoa dieu do)."
```

---

## Task 6: Báo cáo tồn theo cấp

**Files:**
- Modify: `erpnext/warehouse_operations/report/ton_kho_theo_vi_tri/ton_kho_theo_vi_tri.py`
- Modify: `erpnext/warehouse_operations/report/ton_kho_theo_vi_tri/ton_kho_theo_vi_tri.js`
- Test: `erpnext/warehouse_operations/tests/test_bao_cao.py`

**Interfaces:**
- Consumes: `lft`/`rgt`, `is_group` từ Task 2
- Produces: báo cáo trả thêm cột `parent_o` và khoá `parent_field` để Frappe dựng cây

- [ ] **Step 1: Viết bài kiểm**

Thêm vào `test_bao_cao.py`:

```python
	def test_gop_theo_khu_bang_tong_cac_o_la(self):
		"""Vế đối chiếu KHÔNG lấy từ chính báo cáo: cộng thẳng Location Balance."""
		cot, dong = ton_kho_theo_vi_tri.execute({"kho": KHO})
		theo_o = {d["o"]: d for d in dong}
		tong_la = sum(
			flt(v["so_luong"]) for k, v in theo_o.items()
			if not frappe.db.get_value("Storage Location", k, "is_group")
			and k.startswith("9Z")
		)
		self.assertAlmostEqual(flt(theo_o["9Z"]["so_luong"]), tong_la, places=4)
```

- [ ] **Step 2: Chạy để thấy đỏ** — Expected: `KeyError: '9Z'` (báo cáo chưa trả dòng nút nhóm).

- [ ] **Step 3: Cài đặt**

Trong `.py`: sau khi lấy các dòng ô lá, cộng dồn lên bằng `lft/rgt` và trả thêm dòng cho từng nút nhóm có hàng, kèm cột `parent_o = parent_storage_location`. Thêm vào dict trả về của `execute`: Frappe query report dựng cây khi report trả `parent_field`, khai trong `.js`:

```js
frappe.query_reports["Ton Kho Theo Vi Tri"] = {
	filters: [ /* giữ nguyên */ ],
	tree: true,
	name_field: "o",
	parent_field: "parent_o",
	initial_depth: 1,
};
```

- [ ] **Step 4: Chạy lại — xanh. Rồi cả bộ, lint, audit, commit**

---

## Task 7: Dọn `loai_vi_tri` và `custom_ma_kho_spd`

**Files:**
- Modify: `erpnext/warehouse_operations/doctype/storage_location/storage_location.json`
- Create: `erpnext/patches/v15_0/don_loai_vi_tri_khong_hop_le.py`
- Modify: `erpnext/patches.txt`
- Test: `erpnext/warehouse_operations/tests/test_storage_location.py`

**Interfaces:**
- Consumes: —
- Produces: `loai_vi_tri` chỉ còn `Lưu trữ`, `Soạn hàng`

- [ ] **Step 1: Viết bài kiểm**

```python
	def test_loai_vi_tri_khong_con_cach_ly(self):
		"""'Cách ly' là nhãn an toàn GIẢ: không chỗ nào trong vitri/ đọc nó, nên
		hàng ở ô 'cách ly' vẫn bị FEFO lấy ra bán. Cách ly thật phải là Warehouse.
		"""
		meta = frappe.get_meta("Storage Location")
		lua_chon = meta.get_field("loai_vi_tri").options.split("\n")
		self.assertNotIn("Cách ly", lua_chon)
		self.assertNotIn("Trả hàng", lua_chon)
		self.assertIn("Lưu trữ", lua_chon)
```

- [ ] **Step 2: Chạy để thấy đỏ**

- [ ] **Step 3: Sửa doctype và viết patch**

`storage_location.json`: đổi `options` của `loai_vi_tri` thành `"\nLưu trữ\nSoạn hàng"`.

`erpnext/patches/v15_0/don_loai_vi_tri_khong_hop_le.py`:

```python
"""Dọn `Storage Location.loai_vi_tri` còn giá trị không hợp lệ.

"Cách ly" và "Trả hàng" bị bỏ khỏi danh sách lựa chọn: không chỗ nào trong
`vi_tri_kho/vitri/` đọc trường này, nên hàng ở một ô đánh dấu "Cách ly" vẫn
bị FEFO chọn ra để xuất bán — đúng nghĩa một nhãn an toàn giả. Cách ly thật
là ranh giới TỒN KHO, nên nó phải là một `Warehouse` (xem spec
2026-09-11 §3). Để giá trị cũ nằm lại là tiếp tục quảng cáo điều không có.
"""

import frappe


def execute():
	frappe.db.sql(
		"""update `tabStorage Location` set loai_vi_tri = null
		   where ifnull(loai_vi_tri, '') not in ('', 'Lưu trữ', 'Soạn hàng')"""
	)
```

Thêm vào cuối `erpnext/patches.txt`:
```
erpnext.patches.v15_0.don_loai_vi_tri_khong_hop_le
```

Gỡ luôn `custom_ma_kho_spd`: không còn ai đọc sau Task 1. Thêm vào cùng patch:

```python
	frappe.db.delete("Custom Field", {"dt": "Warehouse", "fieldname": "custom_ma_kho_spd"})
```

- [ ] **Step 4: Migrate, chạy lại — xanh. Rồi cả bộ, lint, audit, commit**

---

## Task 8: Dựng lại dữ liệu trên site và cập nhật tài liệu

**Files:**
- Modify: `docs/warehouse_operations/BAN-GIAO-nen-tang-vi-tri-kho.md`
- Modify: `docs/warehouse_operations/HDSD-quan-ly-vi-tri-kho.md`

- [ ] **Step 1: Xoá 128 ô mã 12 ký tự và sinh lại**

128 ô hiện tại **rỗng hoàn toàn** (đã đo: cả 103 dòng tồn nằm ở `ZZZ-CHUA-XEP`), nên xoá không đụng sổ. Kiểm lại trước khi xoá:

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/sites && ../env/bin/python -c "
import frappe
frappe.init(site='erptest.local', sites_path='.'); frappe.connect()
n = frappe.db.sql('''select count(distinct o) from \`tabLocation Balance\`
                     where o not like 'ZZZ%' ''')[0][0]
assert n == 0, f'CÓ {n} ô đang giữ hàng — DỪNG LẠI, đọc lại spec §7'
print('an toàn: không ô 12 ký tự nào đang giữ hàng')"
```

Rồi xoá và sinh lại khu `1A`, 4 dãy × 4 khoang × 4 tầng × 2 ô qua `sinh_ma.sinh(kho, "1A", 4, 4, 4, 2)`.

- [ ] **Step 2: Kiểm bất biến sau khi dựng lại**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/sites && ../env/bin/python -c "
import frappe
frappe.init(site='erptest.local', sites_path='.'); frappe.connect()
K='Kho Miyano - MYN'
from erpnext.warehouse_operations.vitri.doi_soat import doi_soat_kho
kq = doi_soat_kho(K)
print('ô:', frappe.db.count('Storage Location', {'kho':K}))
print('đối soát khớp:', kq['khop'], '| lệch:', kq['so_dong_lech'])
assert kq['khop']"
```
Expected: đối soát khớp, 0 dòng lệch. Số ô = 128 lá + 1+4+16+64 nút nhóm + 1 ô hệ thống.

- [ ] **Step 3: Cập nhật tài liệu**

`BAN-GIAO` mục 0: thêm hàng vào bảng "Trước / Nay" cho mã 10 ký tự và cây. Ghi rõ **`loai_vi_tri` bỏ "Cách ly"** kèm lý do, vì đó là thay đổi người vận hành nhìn thấy.

`HDSD` mục 1b: đổi sơ đồ mã sang 10 ký tự; thêm một mục về cây (gấp/mở, ngừng dùng cả dãy); và một đoạn về **cách ly phải là kho riêng, không phải loại vị trí**.

- [ ] **Step 4: Chạy cả bộ lần cuối, lint, audit, commit**

---

## Tự soát

**Phủ spec:** §3 → Task 7 · §4 → Task 1 · §5 → Task 2 · §6.1 → Task 6 · §6.2 → Task 4 · §6.3 → Task 5 · §7 → Task 8 · §8 bài 1,2 → Task 4 · bài 3,4 → Task 2 · bài 5 → Task 3 · bài 6,7 → Task 5 · bài 8 → Task 6 · bài 9 → Task 7 · bài 10 → Task 2.

**Nhất quán kiểu:** `cap_do()` trả `int` 1..5 (Task 1) và được dùng đúng kiểu đó ở Task 2. `ma_cha()` trả `str | None`, Task 2 xử lý nhánh `None` cho cấp Khu. `_TO_TIEN_TAT` là chuỗi SQL định nghĩa ở Task 4, Task 5 dùng lại đúng tên đó. `chon_o_xuat` đổi chữ ký ở Task 5 và có bài khoá hành vi cũ khi `pham_vi=None`.

**Chỗ chưa chốt, cố ý để lại cho người thi công:** ba patch hiện nằm ở `erpnext/warehouse_operations/patches/` thay vì `erpnext/patches/v15_0/` theo quy ước trong skill `code_structure`. Chúng qua được cổng vị trí file và đang chạy đúng, nên **không** gộp vào kế hoạch này — nêu ra để chủ dự án quyết riêng.

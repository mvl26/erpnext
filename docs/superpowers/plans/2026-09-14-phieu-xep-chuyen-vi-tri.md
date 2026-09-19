# Phiếu xếp / chuyển vị trí — kế hoạch thi công

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Một chứng từ duyệt được chuyển hàng giữa hai ô trong cùng một kho, để hàng nhập về thoát khỏi ô `ZZZ-CHUA-XEP` và vào ô thật.

**Architecture:** Doctype submittable `Location Transfer` + child `Location Transfer Item`. Mỗi dòng ghi hai bút toán vào `Location Ledger Entry` (`−n` ô nguồn, `+n` ô đích) qua `so.ghi_dong_so()`. **Không sinh Stock Ledger Entry.** Chặn tồn âm bằng cách ghi trước rồi đọc lại trong cùng giao dịch.

**Tech Stack:** Frappe v15.113.4, ERPNext v15.83.0 (fork Miyano ERP), Python 3.12, MariaDB, `frappe.utils.nestedset`.

**Spec:** `docs/superpowers/specs/2026-09-14-phieu-xep-chuyen-vi-tri-design.md`

## Global Constraints

- Bench root: `/home/hoangvietyeuem/frappe-bench-yhct`. Site: `erptest.local`. Mọi lệnh `bench` chạy từ bench root.
- Python: **thụt bằng TAB**, dòng ≤ 110 cột, chuỗi nháy kép. Không có `ruff` trong env này — kiểm tay bằng `awk 'length>110'` và `grep -c "^    "`.
- **Chỉ chạy MỘT bộ test tại một thời điểm** (chung một CSDL). Chạy song song sẽ cho đỏ giả.
- Test đặt ở `erpnext/vi_tri_kho/tests/test_*.py`. Cổng cấu trúc: `python3 -m scripts.file_structure --audit` phải ra **0 vi phạm**.
- Sau khi sửa JSON doctype: `bench --site erptest.local migrate`.
- **Commit sau mỗi task, KHÔNG push.**
- Không tạo DocPerm cho `Customer` hay `Website User` ở bất kỳ đâu.
- Hàm `@frappe.whitelist()` nào cũng phải có phép kiểm quyền tường minh.
- Kho dùng để test: `Kho Miyano - MYN` (company `Miyano Việt Nam`). Ô hệ thống: `ZZZ-CHUA-XEP-Kho Miyano - MYN`.

## Hàm có sẵn được dùng lại (chữ ký chính xác)

```python
# erpnext/vi_tri_kho/vitri/so.py
ghi_dong_so(o, kho, vat_tu, so_lo, so_luong, chung_tu_type, chung_tu,
            chung_tu_row, sle, ngay, thoi_diem, company, da_huy=0) -> str
ton_o(o, vat_tu, so_lo) -> float
tong_ton_vi_tri(kho, vat_tu, so_lo) -> float

# erpnext/vi_tri_kho/vitri/kho.py
kho_co_quan_ly_vi_tri(kho: str) -> bool
o_chua_xep(kho: str) -> str | None
```

## Cấu trúc file

| File | Trách nhiệm |
|---|---|
| `vi_tri_kho/doctype/location_transfer_item/` | dòng phiếu (istable), chỉ schema |
| `vi_tri_kho/doctype/location_transfer/location_transfer.json` | schema đầu phiếu + DocPerm |
| `vi_tri_kho/doctype/location_transfer/location_transfer.py` | controller: phép kiểm + ghi sổ + huỷ |
| `vi_tri_kho/doctype/location_transfer/location_transfer.js` | nút "Lấy hàng chưa xếp" |
| `vi_tri_kho/vitri/cay.py` | **thêm** `nhanh_bi_tat()` — dùng chung với `fefo.py` |
| `vi_tri_kho/vitri/xep.py` | hàm whitelist lấy hàng chưa xếp |
| `vi_tri_kho/tests/test_phieu_xep_vi_tri.py` | toàn bộ T1–T14 |

---

### Task 1: Doctype + phép kiểm cơ bản

Deliverable: lưu và duyệt được một phiếu hợp lệ; phiếu sai bị chặn với thông báo rõ. **Chưa ghi sổ** — Task 2 làm.

**Files:**
- Create: `erpnext/vi_tri_kho/doctype/location_transfer_item/__init__.py`
- Create: `erpnext/vi_tri_kho/doctype/location_transfer_item/location_transfer_item.json`
- Create: `erpnext/vi_tri_kho/doctype/location_transfer/__init__.py`
- Create: `erpnext/vi_tri_kho/doctype/location_transfer/location_transfer.json`
- Create: `erpnext/vi_tri_kho/doctype/location_transfer/location_transfer.py`
- Test: `erpnext/vi_tri_kho/tests/test_phieu_xep_vi_tri.py`

**Interfaces:**
- Consumes: `kho.kho_co_quan_ly_vi_tri(kho)`
- Produces: doctype `Location Transfer` với `items: [Location Transfer Item]`; controller `LocationTransfer` có `before_submit()`; helper test `_phieu(kho, dong, **kw) -> Document`

- [ ] **Step 1: Viết bài test đỏ trước**

Tạo `erpnext/vi_tri_kho/tests/test_phieu_xep_vi_tri.py`:

```python
"""Phiếu xếp / chuyển vị trí — spec 2026-09-14.

Bài học đắt nhất của module này: một phép kiểm sai làm lệch tồn theo Ô mà
TỔNG vẫn đúng, nên `doi_soat` vẫn báo khớp và không gì bật lên. Vì vậy gần
như mọi bài ở đây có CHỐT ÂM đi kèm — khẳng định cả cái phải đổi lẫn cái
phải còn nguyên.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

KHO = "Kho Miyano - MYN"
CTY = "Miyano Việt Nam"


def _o(ma_o, **kw):
	if not frappe.db.exists("Storage Location", ma_o):
		frappe.get_doc({"doctype": "Storage Location", "ma_o": ma_o, "kho": KHO, **kw}).insert(
			ignore_permissions=True
		)
	return ma_o


def _vat_tu(ma, co_lo=True):
	if not frappe.db.exists("Item", ma):
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": ma,
				"item_name": ma,
				"item_group": "All Item Groups",
				"stock_uom": "Nos",
				"is_stock_item": 1,
				"has_batch_no": 1 if co_lo else 0,
				"create_new_batch": 1 if co_lo else 0,
			}
		).insert(ignore_permissions=True)
	return ma


def _lo(ma, vat_tu):
	if not frappe.db.exists("Batch", ma):
		frappe.get_doc({"doctype": "Batch", "batch_id": ma, "item": vat_tu}).insert(ignore_permissions=True)
	return ma


def _phieu(dong, kho=KHO, **kw):
	"""Dựng phiếu chưa lưu. `dong` là list dict(vat_tu, so_lo, tu_o, den_o, so_luong)."""
	return frappe.get_doc(
		{"doctype": "Location Transfer", "kho": kho, "items": dong, **kw}
	)


class TestPhepKiemCoBan(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.vt = _vat_tu("9X-VT-CO-LO", co_lo=True)
		cls.vt_khong_lo = _vat_tu("9X-VT-KHONG-LO", co_lo=False)
		cls.lo = _lo("9X-LO-01", cls.vt)
		cls.a = _o("9X01010101")
		cls.b = _o("9X01010102")

	def _dong(self, **kw):
		m = {"vat_tu": self.vt, "so_lo": self.lo, "tu_o": self.a, "den_o": self.b, "so_luong": 5}
		m.update(kw)
		return [m]

	def test_phieu_khong_co_dong_bi_tu_choi(self):
		with self.assertRaises(frappe.ValidationError):
			_phieu([]).insert(ignore_permissions=True)

	def test_so_luong_khong_duong_bi_tu_choi(self):
		for sl in (0, -5):
			with self.assertRaises(frappe.ValidationError):
				_phieu(self._dong(so_luong=sl)).insert(ignore_permissions=True)

	def test_tu_o_trung_den_o_bi_tu_choi(self):
		with self.assertRaises(frappe.ValidationError):
			_phieu(self._dong(den_o=self.a)).insert(ignore_permissions=True)

	def test_o_thuoc_kho_khac_bi_tu_choi(self):
		"""Điều kiện để bất biến §3 tự giữ — xem spec §3."""
		khac = "Hàng trả về - MYN"
		if not frappe.db.exists("Storage Location", "9Y01010101"):
			frappe.get_doc(
				{"doctype": "Storage Location", "ma_o": "9Y01010101", "kho": khac}
			).insert(ignore_permissions=True)
		with self.assertRaises(frappe.ValidationError):
			_phieu(self._dong(den_o="9Y01010101")).insert(ignore_permissions=True)

	def test_den_o_la_nut_nhom_bi_tu_choi(self):
		with self.assertRaises(frappe.ValidationError):
			_phieu(self._dong(den_o="9X0101")).insert(ignore_permissions=True)

	def test_hang_co_lo_ma_bo_trong_so_lo_bi_tu_choi(self):
		"""K9 chiều thiếu — dòng sổ `so_lo = ''` không bao giờ khớp lô thật."""
		with self.assertRaises(frappe.ValidationError):
			_phieu(self._dong(so_lo=None)).insert(ignore_permissions=True)

	def test_hang_khong_lo_ma_dien_lo_cung_bi_tu_choi(self):
		"""K9 chiều thừa — CHỐT ÂM của bài trên. Thiếu bài này thì một đột
		biến chỉ kiểm một chiều vẫn xanh."""
		with self.assertRaises(frappe.ValidationError):
			_phieu(self._dong(vat_tu=self.vt_khong_lo)).insert(ignore_permissions=True)

	def test_lo_khong_thuoc_mat_hang_bi_tu_choi(self):
		vt2 = _vat_tu("9X-VT-CO-LO-2", co_lo=True)
		lo2 = _lo("9X-LO-02", vt2)
		with self.assertRaises(frappe.ValidationError):
			_phieu(self._dong(so_lo=lo2)).insert(ignore_permissions=True)

	def test_kho_chua_bat_quan_ly_vi_tri_bi_tu_choi(self):
		with self.assertRaises(frappe.ValidationError):
			_phieu(self._dong(), kho="Hàng trả về - MYN").insert(ignore_permissions=True)

	def test_phieu_hop_le_luu_va_duyet_duoc(self):
		"""Đối chứng: mọi phép kiểm trên CHỈ chặn cái sai."""
		p = _phieu(self._dong())
		p.insert(ignore_permissions=True)
		p.submit()
		self.assertEqual(p.docstatus, 1)
```

- [ ] **Step 2: Chạy để chắc nó đỏ**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local run-tests --module erpnext.vi_tri_kho.tests.test_phieu_xep_vi_tri
```

Expected: đỏ, `DoesNotExistError: DocType Location Transfer not found`.

- [ ] **Step 3: Tạo child doctype**

`erpnext/vi_tri_kho/doctype/location_transfer_item/__init__.py` — file rỗng.

`erpnext/vi_tri_kho/doctype/location_transfer_item/location_transfer_item.json`:

```json
{
 "actions": [],
 "creation": "2026-09-14 00:00:00.000000",
 "doctype": "DocType",
 "editable_grid": 1,
 "engine": "InnoDB",
 "field_order": [
  "vat_tu",
  "so_lo",
  "col_1",
  "tu_o",
  "den_o",
  "so_luong"
 ],
 "fields": [
  {"fieldname": "vat_tu", "fieldtype": "Link", "label": "Mặt hàng", "options": "Item", "reqd": 1, "in_list_view": 1},
  {"fieldname": "so_lo", "fieldtype": "Link", "label": "Số lô", "options": "Batch", "in_list_view": 1},
  {"fieldname": "col_1", "fieldtype": "Column Break"},
  {"fieldname": "tu_o", "fieldtype": "Link", "label": "Từ ô", "options": "Storage Location", "reqd": 1, "in_list_view": 1},
  {"fieldname": "den_o", "fieldtype": "Link", "label": "Đến ô", "options": "Storage Location", "reqd": 1, "in_list_view": 1},
  {"fieldname": "so_luong", "fieldtype": "Float", "label": "Số lượng", "reqd": 1, "in_list_view": 1}
 ],
 "index_web_pages_for_search": 0,
 "istable": 1,
 "links": [],
 "modified": "2026-09-14 00:00:00.000000",
 "modified_by": "Administrator",
 "module": "Vi Tri Kho",
 "name": "Location Transfer Item",
 "owner": "Administrator",
 "permissions": [],
 "sort_field": "modified",
 "sort_order": "DESC",
 "states": []
}
```

- [ ] **Step 4: Tạo doctype đầu phiếu**

`erpnext/vi_tri_kho/doctype/location_transfer/__init__.py` — file rỗng.

`erpnext/vi_tri_kho/doctype/location_transfer/location_transfer.json`:

```json
{
 "actions": [],
 "autoname": "naming_series:",
 "creation": "2026-09-14 00:00:00.000000",
 "doctype": "DocType",
 "engine": "InnoDB",
 "field_order": [
  "naming_series",
  "kho",
  "col_1",
  "ngay",
  "sec_dong",
  "items",
  "sec_ghi_chu",
  "ghi_chu",
  "amended_from"
 ],
 "fields": [
  {"fieldname": "naming_series", "fieldtype": "Select", "label": "Số phiếu", "options": "XVT-.YYYY.-", "reqd": 1, "set_only_once": 1},
  {"fieldname": "kho", "fieldtype": "Link", "label": "Kho", "options": "Warehouse", "reqd": 1, "in_list_view": 1, "description": "Phiếu chỉ chuyển giữa các ô TRONG kho này. Đổi kho là việc của phiếu chuyển kho ERPNext."},
  {"fieldname": "col_1", "fieldtype": "Column Break"},
  {"fieldname": "ngay", "fieldtype": "Date", "label": "Ngày", "reqd": 1, "default": "Today", "in_list_view": 1},
  {"fieldname": "sec_dong", "fieldtype": "Section Break", "label": "Các dòng chuyển"},
  {"fieldname": "items", "fieldtype": "Table", "label": "Dòng", "options": "Location Transfer Item", "reqd": 1},
  {"fieldname": "sec_ghi_chu", "fieldtype": "Section Break"},
  {"fieldname": "ghi_chu", "fieldtype": "Small Text", "label": "Ghi chú"},
  {"fieldname": "amended_from", "fieldtype": "Link", "label": "Amended From", "options": "Location Transfer", "no_copy": 1, "print_hide": 1, "read_only": 1}
 ],
 "index_web_pages_for_search": 0,
 "is_submittable": 1,
 "links": [],
 "modified": "2026-09-14 00:00:00.000000",
 "modified_by": "Administrator",
 "module": "Vi Tri Kho",
 "name": "Location Transfer",
 "owner": "Administrator",
 "permissions": [
  {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "submit": 1, "cancel": 1, "amend": 1, "report": 1, "export": 1},
  {"role": "Stock Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "submit": 1, "cancel": 1, "amend": 1, "report": 1, "export": 1},
  {"role": "Stock User", "read": 1, "write": 1, "create": 1, "submit": 1, "cancel": 1, "amend": 1, "report": 1, "export": 1}
 ],
 "sort_field": "modified",
 "sort_order": "DESC",
 "states": [],
 "title_field": "kho",
 "track_changes": 1
}
```

Ghi chú: `Stock User` **không** có `delete` — xoá một phiếu nháp là mất dấu vết, để quản lý làm.

- [ ] **Step 5: Viết controller**

`erpnext/vi_tri_kho/doctype/location_transfer/location_transfer.py`:

```python
"""Phiếu xếp / chuyển vị trí — spec 2026-09-14.

Phiếu KHÔNG sinh Stock Ledger Entry và không gọi bất cứ hàm nào của
`erpnext/stock/`. Chuyển giữa hai ô trong cùng kho không làm đổi
`Bin.actual_qty` (Bin theo KHO, không theo ô), nên sinh SLE sẽ vừa đẻ hai
dòng sổ kho triệt tiêu nhau, vừa KÍCH LẠI hook `Stock Ledger Entry.on_submit`
→ `ghi_so_vi_tri` dồn hàng vào `ZZZ-CHUA-XEP` một lần nữa, đúng thứ phiếu
này vừa gỡ ra. Xem spec §4.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from erpnext.vi_tri_kho.vitri.kho import kho_co_quan_ly_vi_tri


class LocationTransfer(Document):
	def validate(self):
		self.kiem_tra_kho()
		self.kiem_tra_cac_dong()

	def kiem_tra_kho(self):
		"""K1 — không bật quản lý vị trí thì không có sổ vị trí để ghi."""
		if not kho_co_quan_ly_vi_tri(self.kho):
			frappe.throw(
				_(
					"Kho {0} chưa bật quản lý vị trí nên không có sổ vị trí để ghi. "
					"Bật ở màn hình Warehouse Location Setup trước."
				).format(self.kho)
			)

	def kiem_tra_cac_dong(self):
		if not self.items:
			frappe.throw(_("Phiếu phải có ít nhất một dòng."))
		for d in self.items:
			self._kiem_mot_dong(d)

	def _kiem_mot_dong(self, d):
		vi_tri = _("Dòng {0}").format(d.idx)

		if flt(d.so_luong) <= 0:
			# K7. Số âm là phiếu ngược trá hình — bắt lập phiếu riêng cho rõ
			# ai chuyển cái gì đi đâu.
			frappe.throw(_("{0}: Số lượng phải lớn hơn 0.").format(vi_tri))

		if d.tu_o == d.den_o:
			frappe.throw(_("{0}: Từ ô và Đến ô đang trùng nhau.").format(vi_tri))

		for truong, o in (("Từ ô", d.tu_o), ("Đến ô", d.den_o)):
			thong_tin = frappe.db.get_value(
				"Storage Location", o, ["kho", "is_group"], as_dict=True
			)
			if not thong_tin:
				frappe.throw(_("{0}: Vị trí {1} không tồn tại.").format(vi_tri, o))
			# K2 — điều kiện để bất biến §3 tự giữ, không phải quy tắc tuỳ chọn.
			if thong_tin.kho != self.kho:
				frappe.throw(
					_(
						"{0}: {1} {2} thuộc kho {3}, không phải {4}. Phiếu này chỉ "
						"chuyển giữa các ô TRONG một kho — đổi kho là việc của phiếu "
						"chuyển kho ERPNext."
					).format(vi_tri, truong, o, thong_tin.kho, self.kho)
				)

		# K3 — nút nhóm không chứa hàng. `ghi_dong_so` cũng chặn, nhưng báo ở
		# đây thì người dùng sửa được lúc còn là nháp.
		if frappe.db.get_value("Storage Location", d.den_o, "is_group"):
			frappe.throw(
				_("{0}: {1} là nút nhóm (cấp Khu/Dãy/Khoang/Tầng), không chứa hàng được.").format(
					vi_tri, d.den_o
				)
			)

		self._kiem_lo(d, vi_tri)

	def _kiem_lo(self, d, vi_tri):
		"""K9 + K10 — sai CẢ HAI chiều đều làm lệch tồn theo ô mà tổng vẫn
		đúng, nên đối soát không bắt được. Xem spec §6.2."""
		co_lo = frappe.db.get_value("Item", d.vat_tu, "has_batch_no")
		if co_lo and not d.so_lo:
			frappe.throw(
				_(
					"{0}: Mặt hàng {1} có quản lý lô nên bắt buộc chọn số lô. Bỏ trống "
					"sẽ ghi một dòng sổ không khớp lô nào — lô nguồn không giảm, còn ô "
					"đích mọc một dòng tồn ma."
				).format(vi_tri, d.vat_tu)
			)
		if not co_lo and d.so_lo:
			frappe.throw(
				_("{0}: Mặt hàng {1} không quản lý lô, phải bỏ trống Số lô.").format(vi_tri, d.vat_tu)
			)
		if d.so_lo:
			chu = frappe.db.get_value("Batch", d.so_lo, "item")
			if chu != d.vat_tu:
				frappe.throw(
					_("{0}: Lô {1} là lô của mặt hàng {2}, không phải {3}.").format(
						vi_tri, d.so_lo, chu, d.vat_tu
					)
				)
```

- [ ] **Step 6: Migrate rồi chạy lại test**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local migrate
bench --site erptest.local run-tests --module erpnext.vi_tri_kho.tests.test_phieu_xep_vi_tri
```

Expected: PASS, 10 bài.

- [ ] **Step 7: Chạy đột biến — mỗi cái phải làm test ĐỎ**

Sửa từng chỗ rồi chạy lại test, xong khôi phục:

| Đột biến | Bài phải đỏ |
|---|---|
| bỏ `kiem_tra_kho()` khỏi `validate` | `test_kho_chua_bat_quan_ly_vi_tri_bi_tu_choi` |
| `if thong_tin.kho != self.kho` → `if False` | `test_o_thuoc_kho_khac_bi_tu_choi` |
| bỏ nhánh `if not co_lo and d.so_lo` | `test_hang_khong_lo_ma_dien_lo_cung_bi_tu_choi` |
| `if flt(d.so_luong) <= 0` → `< 0` | `test_so_luong_khong_duong_bi_tu_choi` |

- [ ] **Step 8: Cổng cấu trúc + kiểu dáng + commit**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/erpnext
python3 -m scripts.file_structure --audit        # phải 0 vi phạm
awk 'length>110{print FILENAME": "NR}' erpnext/vi_tri_kho/doctype/location_transfer/location_transfer.py
git add erpnext/vi_tri_kho/
git commit -m "feat(vi_tri_kho): doctype Phiếu xếp / chuyển vị trí + phép kiểm dòng"
```

---

### Task 2: Ghi sổ khi duyệt + chặn tồn âm

**Files:**
- Modify: `erpnext/vi_tri_kho/doctype/location_transfer/location_transfer.py`
- Test: `erpnext/vi_tri_kho/tests/test_phieu_xep_vi_tri.py`

**Interfaces:**
- Consumes: `so.ghi_dong_so(...)`, `so.ton_o(o, vat_tu, so_lo)`, `so.tong_ton_vi_tri(kho, vat_tu, so_lo)`
- Produces: `LocationTransfer.on_submit()`; `LocationTransfer._ghi(dao=False)`; `LocationTransfer._chan_ton_am(cham)`

- [ ] **Step 1: Viết bài test đỏ**

Thêm vào `test_phieu_xep_vi_tri.py`:

```python
from erpnext.vi_tri_kho.vitri import so


def _nap(o, vat_tu, so_lo, sl):
	"""Nạp tồn thẳng vào một ô để dựng tiền đề — KHÔNG phải cách dùng thật."""
	from frappe.utils import now, nowdate

	so.ghi_dong_so(
		o=o, kho=KHO, vat_tu=vat_tu, so_lo=so_lo, so_luong=sl,
		chung_tu_type=None, chung_tu=None, chung_tu_row="NAP-TIEN-DE-TEST",
		sle=None, ngay=nowdate(), thoi_diem=now(), company=CTY,
	)


class TestGhiSo(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.vt = _vat_tu("9X-GS-VT", co_lo=True)
		cls.lo = _lo("9X-GS-LO", cls.vt)
		cls.a = _o("9X02010101")
		cls.b = _o("9X02010102")

	def _dong(self, sl=10, **kw):
		m = {"vat_tu": self.vt, "so_lo": self.lo, "tu_o": self.a, "den_o": self.b, "so_luong": sl}
		m.update(kw)
		return [m]

	def test_duyet_thi_chuyen_dung_hai_o(self):
		_nap(self.a, self.vt, self.lo, 30)
		truoc_a = so.ton_o(self.a, self.vt, self.lo)
		truoc_b = so.ton_o(self.b, self.vt, self.lo)
		tong_truoc = so.tong_ton_vi_tri(KHO, self.vt, self.lo)

		p = _phieu(self._dong(10))
		p.insert(ignore_permissions=True)
		p.submit()

		self.assertEqual(so.ton_o(self.a, self.vt, self.lo), truoc_a - 10)
		self.assertEqual(so.ton_o(self.b, self.vt, self.lo), truoc_b + 10)
		# CHỐT ÂM — bất biến §3: tổng của kho KHÔNG được đổi.
		self.assertEqual(so.tong_ton_vi_tri(KHO, self.vt, self.lo), tong_truoc)

	def test_khong_sinh_stock_ledger_entry_nao(self):
		"""CHỐT ÂM quan trọng nhất. Đếm TOÀN BỘ bảng SLE, không đếm theo
		chứng từ này — đếm theo chứng từ thì luôn ra 0 dù hook có chạy hay
		không, và bài trở thành vô nghĩa."""
		_nap(self.a, self.vt, self.lo, 30)
		truoc = frappe.db.count("Stock Ledger Entry")
		p = _phieu(self._dong(10))
		p.insert(ignore_permissions=True)
		p.submit()
		self.assertEqual(frappe.db.count("Stock Ledger Entry"), truoc)

	def test_rut_qua_ton_bi_tu_choi_va_khong_ghi_gi(self):
		_nap(self.a, self.vt, self.lo, 5)
		truoc_a = so.ton_o(self.a, self.vt, self.lo)
		truoc_dong = frappe.db.count("Location Ledger Entry")

		p = _phieu(self._dong(999))
		p.insert(ignore_permissions=True)
		with self.assertRaises(frappe.ValidationError):
			p.submit()

		# CHỐT ÂM: rollback phải sạch — không dòng sổ nào sống sót.
		self.assertEqual(so.ton_o(self.a, self.vt, self.lo), truoc_a)
		self.assertEqual(frappe.db.count("Location Ledger Entry"), truoc_dong)

	def test_lay_ra_roi_tra_lai_cung_o_van_duyet_duoc(self):
		"""Đối chứng cho spec §7.2: kiểm theo KẾT QUẢ RÒNG sau khi ghi xong
		cả phiếu, không kiểm sau từng dòng. Ô A chỉ có 10; dòng 1 lấy 10 đi,
		dòng 2 trả 10 về. Kiểm từng dòng sẽ từ chối oan phiếu đúng này."""
		_nap(self.a, self.vt, self.lo, 10)
		p = _phieu(
			[
				{"vat_tu": self.vt, "so_lo": self.lo, "tu_o": self.a, "den_o": self.b, "so_luong": 10},
				{"vat_tu": self.vt, "so_lo": self.lo, "tu_o": self.b, "den_o": self.a, "so_luong": 10},
			]
		)
		p.insert(ignore_permissions=True)
		p.submit()
		self.assertEqual(p.docstatus, 1)
```

- [ ] **Step 2: Chạy để chắc nó đỏ**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local run-tests --module erpnext.vi_tri_kho.tests.test_phieu_xep_vi_tri
```

Expected: đỏ — `test_duyet_thi_chuyen_dung_hai_o` thấy tồn không đổi (chưa có `on_submit`).

- [ ] **Step 3: Thêm ghi sổ vào controller**

Thêm import và phương thức vào `location_transfer.py`:

```python
from frappe.utils import flt, now, nowdate

from erpnext.vi_tri_kho.vitri.so import ghi_dong_so, ton_o
```

```python
	def on_submit(self):
		self._ghi(dao=False)

	def _ghi(self, dao: bool):
		"""Ghi hai bút toán mỗi dòng, rồi CHẶN TỒN ÂM sau khi ghi xong cả phiếu.

		`dao = True` là đường huỷ: đảo dấu và cờ `da_huy = 1`.

		Vì sao ghi TRƯỚC rồi mới kiểm, xem spec §7.2: kiểm trước rồi ghi
		không chặn được hai thủ kho cùng rút một lô (cả hai cùng đọc thấy
		"còn 60" rồi cùng ghi -40). `_cong_don_ton` dùng
		`INSERT ... ON DUPLICATE KEY UPDATE` nên InnoDB khoá đúng dòng chỉ
		mục; người ghi sau phải chờ và đọc được kết quả của người trước.
		Đặt phép kiểm TRƯỚC khi ghi thì không có khoá nào để dựa vào.
		"""
		company = frappe.db.get_value("Warehouse", self.kho, "company")
		luc = now()
		dau = -1 if dao else 1
		cham = set()

		for d in self.items:
			sl = flt(d.so_luong) * dau
			for o, luong in ((d.tu_o, -sl), (d.den_o, sl)):
				ghi_dong_so(
					o=o,
					kho=self.kho,
					vat_tu=d.vat_tu,
					so_lo=d.so_lo,
					so_luong=luong,
					chung_tu_type=self.doctype,
					chung_tu=self.name,
					chung_tu_row=d.name,
					sle=None,
					ngay=self.ngay or nowdate(),
					thoi_diem=luc,
					company=company,
					da_huy=1 if dao else 0,
				)
				cham.add((o, d.vat_tu, d.so_lo or ""))

		self._chan_ton_am(cham)

	def _chan_ton_am(self, cham):
		"""Đọc lại KẾT QUẢ RÒNG của mọi (ô, mặt hàng, lô) mà phiếu chạm tới.

		Đọc sau khi ghi xong TOÀN BỘ phiếu, không sau từng dòng: một phiếu
		hợp lệ có thể lấy 10 khỏi ô A ở dòng 1 rồi trả 10 về ô A ở dòng 2.
		Chỉ kết quả ròng mới có ý nghĩa.

		Ô âm là hỏng nặng: `doi_soat` báo `o_am` và "Đồng bộ lại" CỐ Ý ném
		lỗi thay vì chữa. Nên chặn ở đây, `throw` làm cả phiếu rollback.
		"""
		for o, vat_tu, so_lo in sorted(cham):
			con = ton_o(o, vat_tu, so_lo or None)
			if flt(con) < 0:
				frappe.throw(
					_(
						"Ô {0} không đủ hàng: mặt hàng {1}{2} sẽ còn {3} sau phiếu này. "
						"Kiểm lại số lượng trên các dòng lấy hàng từ ô đó."
					).format(o, vat_tu, f", lô {so_lo}" if so_lo else "", con)
				)
```

- [ ] **Step 4: Chạy test**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local run-tests --module erpnext.vi_tri_kho.tests.test_phieu_xep_vi_tri
```

Expected: PASS, 14 bài.

- [ ] **Step 5: Chạy đột biến**

| Đột biến | Bài phải đỏ |
|---|---|
| bỏ lời gọi `self._chan_ton_am(cham)` | `test_rut_qua_ton_bi_tu_choi_va_khong_ghi_gi` |
| `cham.add(...)` chỉ thêm `d.tu_o`, bỏ `d.den_o` | không bài nào — **ghi lại phát hiện này**, nó đúng: ô đích chỉ cộng thêm nên không bao giờ âm ở đường duyệt; nó chỉ cần cho đường huỷ ở Task 3 |
| đổi `(d.tu_o, -sl), (d.den_o, sl)` thành `(d.tu_o, sl), (d.den_o, -sl)` | `test_duyet_thi_chuyen_dung_hai_o` |
| gọi thêm một SLE giả trong `on_submit` | `test_khong_sinh_stock_ledger_entry_nao` |

- [ ] **Step 6: Commit**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/erpnext
git add erpnext/vi_tri_kho/
git commit -m "feat(vi_tri_kho): phiếu xếp vị trí ghi sổ khi duyệt, chặn tồn âm sau khi ghi"
```

---

### Task 3: Huỷ phiếu ghi bút toán đảo

**Files:**
- Modify: `erpnext/vi_tri_kho/doctype/location_transfer/location_transfer.py`
- Test: `erpnext/vi_tri_kho/tests/test_phieu_xep_vi_tri.py`

**Interfaces:**
- Consumes: `LocationTransfer._ghi(dao=True)` (Task 2)
- Produces: `LocationTransfer.on_cancel()`

- [ ] **Step 1: Viết bài test đỏ**

```python
class TestHuyPhieu(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.vt = _vat_tu("9X-HP-VT", co_lo=True)
		cls.lo = _lo("9X-HP-LO", cls.vt)
		cls.a = _o("9X03010101")
		cls.b = _o("9X03010102")

	def _phieu_da_duyet(self, sl=10):
		p = _phieu(
			[{"vat_tu": self.vt, "so_lo": self.lo, "tu_o": self.a, "den_o": self.b, "so_luong": sl}]
		)
		p.insert(ignore_permissions=True)
		p.submit()
		return p

	def test_huy_dao_dung_hai_chieu(self):
		_nap(self.a, self.vt, self.lo, 30)
		truoc_a = so.ton_o(self.a, self.vt, self.lo)
		truoc_b = so.ton_o(self.b, self.vt, self.lo)

		p = self._phieu_da_duyet(10)
		p.cancel()

		self.assertEqual(so.ton_o(self.a, self.vt, self.lo), truoc_a)
		self.assertEqual(so.ton_o(self.b, self.vt, self.lo), truoc_b)

	def test_huy_ghi_them_chu_khong_xoa_dong_cu(self):
		"""Sổ là append-only — `dung_lai_ton_vi_tri` dựa vào điều đó."""
		_nap(self.a, self.vt, self.lo, 30)
		p = self._phieu_da_duyet(10)
		sau_duyet = frappe.db.count("Location Ledger Entry", {"chung_tu": p.name})
		p.cancel()
		sau_huy = frappe.db.count("Location Ledger Entry", {"chung_tu": p.name})
		self.assertEqual(sau_huy, sau_duyet * 2)
		self.assertEqual(frappe.db.count("Location Ledger Entry", {"chung_tu": p.name, "da_huy": 1}), 2)

	def test_huy_khi_o_dich_da_bi_xuat_het_bi_chan(self):
		"""Hàng đã xếp vào ô đích có thể đã bị lấy đi mất; lúc đó huỷ sẽ đẩy
		ô đích xuống âm. Phải chặn, kèm lý do."""
		_nap(self.a, self.vt, self.lo, 30)
		p = self._phieu_da_duyet(10)
		_nap(self.b, self.vt, self.lo, -10)  # ô đích bị xuất sạch phần vừa xếp
		truoc = frappe.db.count("Location Ledger Entry")
		with self.assertRaises(frappe.ValidationError):
			p.cancel()
		self.assertEqual(frappe.db.count("Location Ledger Entry"), truoc)
```

- [ ] **Step 2: Chạy để chắc nó đỏ**

Expected: đỏ — huỷ chưa đảo gì nên `test_huy_dao_dung_hai_chieu` thấy tồn không quay lại.

- [ ] **Step 3: Thêm `on_cancel`**

```python
	def on_cancel(self):
		"""Ghi bút toán ĐẢO, không sửa không xoá dòng cũ.

		Sổ vị trí là append-only — `so.dung_lai_ton_vi_tri()` dựng lại bộ
		đệm bằng cách cộng toàn bộ sổ, nên xoá dòng cũ sẽ làm mất dấu vết
		mà vẫn ra đúng số. Giữ cả hai chiều để đọc lại được lịch sử.

		`_ghi` chạy luôn phép chặn tồn âm: ở đường huỷ, ô bị GIẢM là ô ĐÍCH
		(hàng đã xếp vào đó có thể đã bị xuất đi mất). Đó là lý do `cham`
		gom cả hai ô chứ không riêng ô nguồn.
		"""
		self._ghi(dao=True)
```

- [ ] **Step 4: Chạy test**

Expected: PASS, 17 bài.

- [ ] **Step 5: Chạy đột biến**

| Đột biến | Bài phải đỏ |
|---|---|
| `self._ghi(dao=True)` → `self._ghi(dao=False)` | `test_huy_dao_dung_hai_chieu` |
| bỏ `da_huy=1 if dao else 0`, để luôn 0 | `test_huy_ghi_them_chu_khong_xoa_dong_cu` |
| `cham.add` bỏ ô đích (đột biến của Task 2, giờ mới có bài bắt) | `test_huy_khi_o_dich_da_bi_xuat_het_bi_chan` |

- [ ] **Step 6: Commit**

```bash
git add erpnext/vi_tri_kho/
git commit -m "feat(vi_tri_kho): huỷ phiếu xếp vị trí ghi bút toán đảo"
```

---

### Task 4: Chặn nhánh Ngừng dùng — hai chiều ngược nhau

**Files:**
- Modify: `erpnext/vi_tri_kho/vitri/cay.py` (thêm `nhanh_bi_tat`)
- Modify: `erpnext/vi_tri_kho/doctype/location_transfer/location_transfer.py`
- Test: `erpnext/vi_tri_kho/tests/test_phieu_xep_vi_tri.py`

**Interfaces:**
- Produces: `cay.nhanh_bi_tat(o: str) -> str | None` — trả tên nút đang tắt (chính nó hoặc tổ tiên), `None` nếu không có

- [ ] **Step 1: Viết bài test đỏ**

```python
class TestNhanhNgungDung(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.vt = _vat_tu("9X-ND-VT", co_lo=True)
		cls.lo = _lo("9X-ND-LO", cls.vt)
		cls.a = _o("9X04010101")
		cls.b = _o("9X04020101")  # dãy khác, để tắt cả dãy 9X0402

	def _p(self, tu_o, den_o):
		return _phieu(
			[{"vat_tu": self.vt, "so_lo": self.lo, "tu_o": tu_o, "den_o": den_o, "so_luong": 5}]
		)

	def test_xep_vao_o_dang_tat_bi_chan(self):
		frappe.db.set_value("Storage Location", self.b, "disabled", 1)
		_nap(self.a, self.vt, self.lo, 20)
		with self.assertRaises(frappe.ValidationError):
			self._p(self.a, self.b).insert(ignore_permissions=True)

	def test_xep_vao_o_duoi_nhanh_da_tat_cung_bi_chan(self):
		"""Tắt cả DÃY, ô lá bên dưới tự nó vẫn `disabled = 0`."""
		frappe.db.set_value("Storage Location", "9X0402", "disabled", 1)
		_nap(self.a, self.vt, self.lo, 20)
		with self.assertRaises(frappe.ValidationError):
			self._p(self.a, self.b).insert(ignore_permissions=True)

	def test_lay_RA_khoi_o_dang_tat_van_duoc(self):
		"""CHỐT ÂM, và là cả lý do tính năng này tồn tại: đây là đường DUY
		NHẤT gỡ hàng khỏi một dãy đang tháo kệ. `fefo.py` đã chặn đường
		xuất, nên cấm nốt chiều này là hàng kẹt vĩnh viễn."""
		_nap(self.a, self.vt, self.lo, 20)
		frappe.db.set_value("Storage Location", self.a, "disabled", 1)
		p = self._p(self.a, self.b)
		p.insert(ignore_permissions=True)
		p.submit()
		self.assertEqual(p.docstatus, 1)
```

- [ ] **Step 2: Chạy để chắc nó đỏ**

Expected: đỏ — hai bài đầu, chưa có phép chặn nào.

- [ ] **Step 3: Thêm `nhanh_bi_tat` vào `cay.py`**

```python
def nhanh_bi_tat(o: str) -> str | None:
	"""Tên nút đang Ngừng dùng che phủ ô `o` — chính nó hoặc một tổ tiên.

	Dùng ĐÚNG vị từ tổ tiên của `fefo.py::_TO_TIEN_TAT`: chứa CHẶT
	(`lft <` và `rgt >`) cộng với khớp chính nó bằng TÊN. Không suy tổ tiên
	từ tiền tố mã — bẫy F8 đã trả giá một lần: bản ghi chưa hội tụ mang
	`lft = rgt = 0` nên phép chứa lỏng (`<=`, `>=`) khiến chúng coi nhau là
	tổ tiên của nhau, đo được 128 tổ tiên giả cho một ô.
	"""
	moc = frappe.db.get_value("Storage Location", o, ["lft", "rgt"], as_dict=True)
	if not moc:
		return None
	ket_qua = frappe.db.sql(
		"""select tt.name from `tabStorage Location` tt
		   where ifnull(tt.disabled, 0) = 1
		     and (tt.name = %(o)s or (tt.lft < %(lft)s and tt.rgt > %(rgt)s))
		   order by tt.lft asc limit 1""",
		{"o": o, "lft": moc.lft, "rgt": moc.rgt},
	)
	return ket_qua[0][0] if ket_qua else None
```

- [ ] **Step 4: Gọi trong controller**

Thêm import `from erpnext.vi_tri_kho.vitri.cay import nhanh_bi_tat`, rồi thêm vào cuối `_kiem_mot_dong`:

```python
		# K4 — chỉ chặn chiều VÀO. Vá đúng bất đối xứng đã ghi trong
		# QUYET-DINH-thi-cong-cay-vi-tri.md: `fefo.py` là nơi DUY NHẤT lọc
		# `disabled`, đường nhập không lọc gì, nên hàng vẫn chảy VÀO một dãy
		# đã tắt trong khi không ô nào trong dãy đó xuất RA được — mà đối
		# soát vẫn xanh vì nó chỉ so tổng.
		#
		# K5 — KHÔNG kiểm `d.tu_o`, và đó là chủ ý, không phải bỏ sót. Lấy
		# hàng RA khỏi ô đang tắt là đường duy nhất gỡ hàng khỏi dãy đang
		# tháo kệ; chặn nốt chiều này thì hàng kẹt vĩnh viễn.
		nut_tat = nhanh_bi_tat(d.den_o)
		if nut_tat:
			frappe.throw(
				_(
					"{0}: không xếp hàng vào {1} được vì {2} đang Ngừng dùng. "
					"Bật lại {2}, hoặc chọn ô khác. (Lấy hàng RA khỏi ô đang "
					"Ngừng dùng thì vẫn được.)"
				).format(vi_tri, d.den_o, nut_tat)
			)
```

- [ ] **Step 5: Chạy test**

Expected: PASS, 20 bài.

- [ ] **Step 6: Chạy đột biến**

| Đột biến | Bài phải đỏ |
|---|---|
| `tt.lft < %(lft)s and tt.rgt > %(rgt)s` → `<=` và `>=` | `test_lay_RA_khoi_o_dang_tat_van_duoc` (ô nguồn tự coi mình là tổ tiên… kiểm lại: nếu vẫn xanh thì ghi lại là đột biến này KHÔNG bị bắt và nói rõ vì sao) |
| thêm `nhanh_bi_tat(d.tu_o)` vào cùng phép chặn | `test_lay_RA_khoi_o_dang_tat_van_duoc` |
| bỏ hẳn phép chặn `nut_tat` | `test_xep_vao_o_dang_tat_bi_chan` |

- [ ] **Step 7: Commit**

```bash
git add erpnext/vi_tri_kho/
git commit -m "feat(vi_tri_kho): chặn xếp hàng vào nhánh Ngừng dùng, vẫn cho lấy ra"
```

---

### Task 5: Nút "Lấy hàng chưa xếp"

**Files:**
- Create: `erpnext/vi_tri_kho/vitri/xep.py`
- Create: `erpnext/vi_tri_kho/doctype/location_transfer/location_transfer.js`
- Test: `erpnext/vi_tri_kho/tests/test_phieu_xep_vi_tri.py`

**Interfaces:**
- Produces: `xep.hang_chua_xep(kho: str) -> list[dict]` với khoá `vat_tu`, `so_lo`, `tu_o`, `so_luong`

- [ ] **Step 1: Viết bài test đỏ**

```python
from erpnext.vi_tri_kho.vitri.xep import hang_chua_xep


class TestLayHangChuaXep(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.vt = _vat_tu("9X-LC-VT", co_lo=True)
		cls.lo = _lo("9X-LC-LO", cls.vt)
		cls.zzz = frappe.db.get_value(
			"Storage Location", {"la_o_chua_xep": 1, "kho": KHO}, "name"
		)
		cls.o_that = _o("9X05010101")

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_tra_ve_hang_dang_o_o_chua_xep(self):
		_nap(self.zzz, self.vt, self.lo, 7)
		dong = [d for d in hang_chua_xep(KHO) if d["vat_tu"] == self.vt]
		self.assertEqual(len(dong), 1)
		self.assertEqual(dong[0]["tu_o"], self.zzz)
		self.assertEqual(dong[0]["so_luong"], 7)
		self.assertEqual(dong[0]["so_lo"], self.lo)

	def test_khong_tra_ve_hang_o_o_that(self):
		"""CHỐT ÂM: nút này chỉ kéo hàng CHƯA xếp. Thiếu bài này thì một đột
		biến bỏ điều kiện `la_o_chua_xep` sẽ kéo cả kho vào phiếu."""
		_nap(self.o_that, self.vt, self.lo, 9)
		o = {d["tu_o"] for d in hang_chua_xep(KHO)}
		self.assertNotIn(self.o_that, o)

	def test_website_user_bi_chan(self):
		ten = "xep-khong-quyen@mo-phong.local"
		if not frappe.db.exists("User", ten):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": ten,
					"first_name": "Xep",
					"send_welcome_email": 0,
					"roles": [],
				}
			).insert(ignore_permissions=True)
		frappe.set_user(ten)
		with self.assertRaises(frappe.PermissionError):
			hang_chua_xep(KHO)
```

- [ ] **Step 2: Chạy để chắc nó đỏ**

Expected: `ModuleNotFoundError: erpnext.vi_tri_kho.vitri.xep`.

- [ ] **Step 3: Viết `xep.py`**

```python
"""Lấy danh sách hàng đang nằm ở ô "Chưa xếp vị trí" để đổ vào phiếu xếp.

Cùng nguồn dữ liệu với báo cáo *Hàng chưa xếp vị trí*
(`report/hang_chua_xep_vi_tri/`) để hai chỗ không bao giờ nói khác nhau —
thủ kho nhìn báo cáo rồi mở phiếu, thấy lệch là mất tin ngay.
"""

import frappe
from frappe import _

VAI_TRO_DUOC_XEP = {"System Manager", "Stock Manager", "Stock User"}


def _kiem_tra_quyen():
	if not VAI_TRO_DUOC_XEP & set(frappe.get_roles()):
		frappe.throw(_("Bạn không có quyền xem hàng chưa xếp vị trí."), frappe.PermissionError)


@frappe.whitelist()
def hang_chua_xep(kho: str) -> list[dict]:
	"""Các dòng tồn ở ô "Chưa xếp vị trí" của `kho`, dạng dòng phiếu sẵn."""
	_kiem_tra_quyen()
	return frappe.db.sql(
		"""
		select lb.vat_tu as vat_tu, nullif(lb.so_lo, '') as so_lo,
		       lb.o as tu_o, lb.so_luong as so_luong
		from `tabLocation Balance` lb
		join `tabStorage Location` sl on sl.name = lb.o
		where sl.la_o_chua_xep = 1 and lb.kho = %(kho)s and lb.so_luong != 0
		order by lb.vat_tu asc, lb.so_lo asc
		""",
		{"kho": kho},
		as_dict=True,
	)
```

- [ ] **Step 4: Viết form script**

`erpnext/vi_tri_kho/doctype/location_transfer/location_transfer.js`:

```javascript
// Nút "Lấy hàng chưa xếp": đổ toàn bộ hàng đang ở ô "Chưa xếp vị trí" của
// kho thành các dòng sẵn. Ô ĐÍCH để trống — không có căn cứ nào để gợi ý
// (trường `suc_chua` hiện = 0 trên mọi ô), mà gợi ý sai thì thủ kho tin
// theo rồi xếp nhầm.

frappe.ui.form.on("Location Transfer", {
	refresh(frm) {
		if (frm.doc.docstatus !== 0 || !frm.doc.kho) return;
		frm.add_custom_button(__("Lấy hàng chưa xếp"), () => lay_hang_chua_xep(frm));
	},

	kho(frm) {
		// Ô của kho cũ không dùng được cho kho mới (phép kiểm K2 sẽ chặn) —
		// xoá luôn cho khỏi để người dùng sửa từng dòng.
		if (frm.doc.items && frm.doc.items.length) {
			frm.clear_table("items");
			frm.refresh_field("items");
			frappe.show_alert({ message: __("Đã xoá các dòng vì đổi kho."), indicator: "orange" });
		}
	},
});

function lay_hang_chua_xep(frm) {
	frappe.call({
		method: "erpnext.vi_tri_kho.vitri.xep.hang_chua_xep",
		args: { kho: frm.doc.kho },
		callback(r) {
			const dong = r.message || [];
			if (!dong.length) {
				frappe.msgprint({
					title: __("Không có hàng chưa xếp"),
					message: __("Kho {0} không còn hàng nào ở ô 'Chưa xếp vị trí'.", [frm.doc.kho]),
					indicator: "green",
				});
				return;
			}
			frm.clear_table("items");
			dong.forEach((d) => {
				const r = frm.add_child("items");
				r.vat_tu = d.vat_tu;
				r.so_lo = d.so_lo;
				r.tu_o = d.tu_o;
				r.so_luong = d.so_luong;
				// den_o cố ý để trống — thủ kho phải tự khai.
			});
			frm.refresh_field("items");
			frappe.show_alert({
				message: __("Đã lấy {0} dòng. Điền ô đích cho từng dòng.", [dong.length]),
				indicator: "blue",
			});
		},
	});
}
```

- [ ] **Step 5: Chạy test**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local clear-cache
bench --site erptest.local run-tests --module erpnext.vi_tri_kho.tests.test_phieu_xep_vi_tri
```

Expected: PASS, 23 bài.

- [ ] **Step 6: Chạy đột biến**

| Đột biến | Bài phải đỏ |
|---|---|
| bỏ `and sl.la_o_chua_xep = 1` | `test_khong_tra_ve_hang_o_o_that` |
| bỏ `_kiem_tra_quyen()` | `test_website_user_bi_chan` |
| bỏ `and lb.kho = %(kho)s` | không chắc bắt được — nếu xanh, **thêm một bài** nạp hàng vào ô CHUA-XEP của kho khác rồi khẳng định nó không lọt |

- [ ] **Step 7: Commit**

```bash
git add erpnext/vi_tri_kho/
git commit -m "feat(vi_tri_kho): nút Lấy hàng chưa xếp trên phiếu xếp vị trí"
```

---

### Task 6: Chạy thật đầu-cuối + cập nhật tài liệu

**Files:**
- Modify: `docs/vi_tri_kho/HDSD-quan-ly-vi-tri-kho.md`
- Modify: `docs/vi_tri_kho/BAN-GIAO-nen-tang-vi-tri-kho.md`

- [ ] **Step 1: Chạy TOÀN BỘ bộ test của module**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
for m in $(ls apps/erpnext/erpnext/vi_tri_kho/tests/test_*.py | sed 's|apps/erpnext/||; s|/|.|g; s|\.py$||'); do
  echo "=== $m"
  bench --site erptest.local run-tests --module $m 2>&1 | tr '\r' '\n' | grep -E "^Ran|^OK|^FAILED"
done
```

Expected: tất cả OK. Con số nền trước Task 1 là **241 bài**.

- [ ] **Step 2: Xoá dữ liệu mô phỏng cũ rồi xếp lại bằng phiếu thật**

Sáu dòng sổ mô phỏng ngày 13/09 mang dấu `MO-PHONG-XEP-13092026`. Xoá chúng, rồi làm lại
đúng việc đó bằng phiếu thật:

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/sites && ../env/bin/python - <<'PY'
import frappe
frappe.init(site="erptest.local", sites_path="."); frappe.connect()
ten = frappe.get_all("Location Ledger Entry",
                     filters={"chung_tu_row": "MO-PHONG-XEP-13092026"}, pluck="name")
for n in ten:
	frappe.delete_doc("Location Ledger Entry", n, force=True, ignore_permissions=True)
frappe.db.commit()
from erpnext.vi_tri_kho.vitri.so import dung_lai_ton_vi_tri
print("đã xoá", len(ten), "dòng mô phỏng; dựng lại", dung_lai_ton_vi_tri("Kho Miyano - MYN"), "dòng tồn")
frappe.db.commit()
PY
```

Rồi mở `/app/location-transfer/new`, chọn `Kho Miyano - MYN`, bấm **Lấy hàng chưa xếp**, điền vài
ô đích thật, Duyệt. Ghi lại số phiếu.

- [ ] **Step 3: Kiểm bốn thứ sau khi duyệt**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/sites && ../env/bin/python - <<'PY'
import frappe
frappe.init(site="erptest.local", sites_path="."); frappe.connect(); frappe.set_user("Administrator")
KHO = "Kho Miyano - MYN"
from erpnext.vi_tri_kho.vitri.doi_soat import doi_soat_kho
from erpnext.vi_tri_kho.report.ton_kho_theo_vi_tri.ton_kho_theo_vi_tri import execute
kq = doi_soat_kho(KHO)
print("đối soát khớp:", kq["khop"], "| lệch:", kq["so_dong_lech"], "| ô âm:", len(kq["o_am"]))
cot, dong = execute({"kho": KHO})
print("dòng nhóm (Khu/Dãy) hiện ra:", sum(1 for d in dong if d["is_group"]))
print("dòng tồn còn ở ZZZ:", frappe.db.count("Location Balance",
      {"kho": KHO, "o": ["like", "ZZZ%"], "so_luong": ["!=", 0]}))
PY
```

Expected: đối soát khớp, **dòng nhóm > 0** (đây là bằng chứng việc D tự có), ZZZ vơi đi.

- [ ] **Step 4: Cập nhật HDSD**

Trong `docs/vi_tri_kho/HDSD-quan-ly-vi-tri-kho.md`:

1. Mục 6.1 — bỏ câu "Hiện chưa có màn hình khai ô lúc nhập; thủ kho xem báo cáo rồi xếp ngoài
   thực tế", thay bằng trỏ tới mục mới.
2. **Xoá khối cảnh báo "⚠ Đọc kỹ: hai ví dụ trên CHƯA tự làm lại được"** ở mục 6.2 — nay đã sai.
3. Thêm mục mới **"Xếp hàng vào ô"** ngay sau 6.1: mở phiếu, chọn kho, bấm Lấy hàng chưa xếp,
   điền ô đích, Duyệt; huỷ phiếu thì hàng quay về ô cũ; không xếp được vào ô đang Ngừng dùng
   nhưng lấy ra thì được.
4. Mục 7 — bỏ câu "Ba câu hỏi khác về cấp Khu … chưa có báo cáo" nếu vẫn đúng thì giữ, chỉ sửa
   câu nói tồn theo Khu/Dãy ra rỗng.

Trong `docs/vi_tri_kho/BAN-GIAO-nen-tang-vi-tri-kho.md`: thêm một dòng vào bảng trạng thái ghi
`Location Transfer` là doctype submittable đầu tiên của module.

- [ ] **Step 5: Cập nhật `QUYET-DINH-thi-cong-cay-vi-tri.md`**

Mục "Một bất đối xứng còn tồn tại" nói *"Nó trở thành vấn đề thật khi có màn hình khai vị trí
lúc nhập (giai đoạn sau)"*. Giai đoạn sau đã tới — ghi rõ K4 đã vá chiều VÀO, và K5 cố ý để
ngỏ chiều RA, kèm lý do.

- [ ] **Step 6: Commit**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/erpnext
python3 -m scripts.file_structure --audit
git add docs/ erpnext/vi_tri_kho/
git commit -m "docs(vi_tri_kho): HDSD phần xếp hàng vào ô, và chạy thật đầu-cuối"
```

---

## Rà lại kế hoạch so với spec

| Mục spec | Task phủ |
|---|---|
| §3 bất biến | T1/T2 chốt âm "tổng không đổi", Task 6 Step 3 |
| §4 không sinh SLE | Task 2 `test_khong_sinh_stock_ledger_entry_nao` |
| §5.1, §5.2 mô hình | Task 1 Step 3–4 |
| §6 K1–K10 | Task 1 (K1,K2,K3,K6–K10), Task 4 (K4,K5) |
| §6.1 hai chiều disabled | Task 4 |
| §6.2 lô hai chiều | Task 1 |
| §7.1 hai bút toán | Task 2 |
| §7.2 chặn tồn âm | Task 2 |
| §7.3 huỷ | Task 3 |
| §8 nút lấy hàng chưa xếp | Task 5 |
| §9 phân quyền | Task 1 Step 4 (DocPerm), Task 5 (`_kiem_tra_quyen`) |
| §10 T1–T14 | T1,T2→Task 2; T3→Task 2; T4,T5→Task 1; T6,T6b→Task 4; T7,T8→Task 3; T9→Task 2+3; T10→Task 2; T11→**xem ghi chú dưới**; T12→Task 5; T13,T13b→Task 1; T14→Task 2 |
| §11 không làm | không có task — đúng chủ ý |

**Khoảng trống đã biết, xử lý ở Task 2 Step 5:** T11 (hai phiếu cùng rút một lô) cần hai kết nối
CSDL thật và `commit()`, mà bài test nào `commit()` thì phải tự dọn cả tổ tiên do NestedSet sinh
ra — xem `nested-set-ro-ri-trong-test`. Nếu viết được trong Task 2 thì viết; nếu không, **ghi lại
tường minh rằng ca tương tranh chỉ được suy luận từ cơ chế khoá của InnoDB chứ chưa đo**, đừng
để nó trôi thành "đã kiểm".

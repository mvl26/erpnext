# Lấy hàng trên PDA — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Thủ kho quét tem lô + tem ô để xác nhận lấy hàng cho phiếu giao, và sổ vị trí trừ **đúng ô đã quét** thay vì ô do FEFO tự chọn lúc duyệt.

**Architecture:** Dựng tiếp đúng thiết kế đã có ở spec nền tảng: một bảng con `Location Allocation` gắn vào `Delivery Note` (custom field `custom_phan_bo_vi_tri`), một nhánh mới trong `hook_sle._ghi_mot_phan` đọc bảng đó khi xuất kho, một lớp kiểm sớm ở `Delivery Note.validate`, và một trang Frappe Page `lay-hang-pda` gọi các hàm `@frappe.whitelist()` trong `vitri/lay_hang.py`. Không thêm doctype submittable nào; trạng thái "đang lấy dở" sống trên chính phiếu giao nháp.

**Tech Stack:** Frappe v15 / ERPNext (fork Miyano ERP), Python 3.12 (tabs, dòng ≤ 110 ký tự), JS thuần + jQuery của Frappe, bench `/home/hoangvietyeuem/frappe-bench-yhct`, site `erptest.local`.

**Spec:** `docs/superpowers/specs/2026-09-18-lay-hang-pda-design.md`

## Global Constraints

- **Chạy mọi lệnh bench từ bench root** `/home/hoangvietyeuem/frappe-bench-yhct`, `--site erptest.local`.
- **Python: thụt bằng TAB**, dòng ≤ 110 ký tự, chuỗi nháy kép. Câu báo lỗi **tiếng Việt**, nêu rõ ô nào / mặt hàng nào / thiếu bao nhiêu, không lộ traceback.
- **Không sửa** `erpnext/stock/` và `erpnext/stock/utils.py::scan_barcode`.
- **Không `ignore_permissions`** khi lưu / duyệt `Delivery Note` — quyền duyệt vẫn là của doctype. Bộ vai trò: `{"System Manager", "Stock Manager", "Stock User"}`.
- **Đường cũ không được đổi hành vi**: chứng từ không có phân bổ vẫn chạy FEFO y như hôm nay. Chốt bằng bài test âm ở Task 2.
- **`bench run-tests` trả exit code 0 kể cả khi FAILED** — luôn đọc dòng `OK` / `FAILED` trong output, đừng tin exit code.
- `FrappeTestCase` rollback **theo lớp**: bài nào nạp tồn/chứng từ trong `setUp` phải tự `frappe.db.savepoint()` ở `setUp` và `frappe.db.rollback(save_point=...)` ở `tearDown` (khuôn `tests/test_xep_pda.py`).
- Trang PDA: **không dùng `frappe.confirm`** (Enter của súng quét bấm "Có" — `frappe/public/js/frappe/ui/keyboard.js:251`); dùng `frappe.ui.Dialog` thường, và bọc script trang trong IIFE.
- Sau mỗi task: chạy **cả bộ** `vi_tri_kho` (34 module, 466 bài trước khi bắt đầu) và commit.

---

### Task 1: Bảng phân bổ `Location Allocation` + custom field trên Delivery Note

**Files:**
- Create: `erpnext/vi_tri_kho/doctype/location_allocation/__init__.py`
- Create: `erpnext/vi_tri_kho/doctype/location_allocation/location_allocation.json`
- Create: `erpnext/vi_tri_kho/doctype/location_allocation/location_allocation.py`
- Create: `erpnext/vi_tri_kho/doctype/location_allocation/test_location_allocation.py`
- Create: `erpnext/vi_tri_kho/patches/v1_0/them_phan_bo_vi_tri.py`
- Modify: `erpnext/patches.txt` (thêm một dòng ở cuối)

**Interfaces:**
- Consumes: —
- Produces: doctype con `Location Allocation` với các field `dong_hang` (Data), `vat_tu` (Link Item), `so_lo` (Link Batch), `o` (Link Storage Location), `so_luong` (Float), `nguoi_lay` (Link User), `luc_lay` (Datetime); custom field `Delivery Note.custom_phan_bo_vi_tri` (Table → `Location Allocation`, read-only).

- [ ] **Step 1: Viết bài test đỏ**

Tạo `erpnext/vi_tri_kho/doctype/location_allocation/test_location_allocation.py`:

```python
"""Bảng phân bổ vị trí — nơi ghi "hàng của dòng này lấy ở ô nào".

Hỏng theo kiểu im lặng: thiếu patch thì field không có trên Delivery Note, trang
lấy hàng vẫn mở được, quét vẫn chạy, chỉ là không lưu được gì — và không lỗi nào
báo. Bài này khoá đúng hai điều: doctype có thật, và field đã gắn vào phiếu giao.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

TEN_BANG_PHAN_BO = "custom_phan_bo_vi_tri"


class TestBangPhanBo(FrappeTestCase):
	def test_doctype_ton_tai_va_la_bang_con(self):
		meta = frappe.get_meta("Location Allocation")
		self.assertTrue(meta.istable, "Location Allocation phải là bảng con (istable = 1)")
		co = {f.fieldname for f in meta.fields}
		self.assertTrue(
			{"dong_hang", "vat_tu", "so_lo", "o", "so_luong", "nguoi_lay", "luc_lay"} <= co,
			f"thiếu field: {co}",
		)

	def test_field_da_gan_vao_phieu_giao(self):
		"""Thiếu dòng trong patches.txt thì patch không chạy, field không có."""
		f = frappe.get_meta("Delivery Note").get_field(TEN_BANG_PHAN_BO)
		self.assertIsNotNone(f, "Delivery Note chưa có bảng phân bổ vị trí — kiểm patches.txt")
		self.assertEqual(f.fieldtype, "Table")
		self.assertEqual(f.options, "Location Allocation")
		self.assertTrue(f.read_only, "bảng phân bổ là KẾT QUẢ của việc quét, không khai tay")
```

- [ ] **Step 2: Chạy để thấy đỏ**

Chạy: `bench --site erptest.local run-tests --module erpnext.vi_tri_kho.doctype.location_allocation.test_location_allocation`
Chờ: FAILED — `DoesNotExistError: DocType Location Allocation not found`.

- [ ] **Step 3: Tạo doctype**

`erpnext/vi_tri_kho/doctype/location_allocation/__init__.py`: file rỗng.

`erpnext/vi_tri_kho/doctype/location_allocation/location_allocation.json`:

```json
{
 "actions": [],
 "creation": "2026-09-18 00:00:00.000000",
 "doctype": "DocType",
 "editable_grid": 1,
 "engine": "InnoDB",
 "field_order": ["dong_hang", "vat_tu", "so_lo", "col_1", "o", "so_luong", "nguoi_lay", "luc_lay"],
 "fields": [
  {"fieldname": "dong_hang", "fieldtype": "Data", "in_list_view": 1, "label": "Dòng hàng", "reqd": 1,
   "description": "Tên dòng hàng trên chứng từ (khớp Stock Ledger Entry.voucher_detail_no)"},
  {"fieldname": "vat_tu", "fieldtype": "Link", "options": "Item", "label": "Mặt hàng", "reqd": 1, "in_list_view": 1},
  {"fieldname": "so_lo", "fieldtype": "Link", "options": "Batch", "label": "Số lô", "in_list_view": 1},
  {"fieldname": "col_1", "fieldtype": "Column Break"},
  {"fieldname": "o", "fieldtype": "Link", "options": "Storage Location", "label": "Ô", "reqd": 1, "in_list_view": 1},
  {"fieldname": "so_luong", "fieldtype": "Float", "label": "Số lượng", "reqd": 1, "in_list_view": 1},
  {"fieldname": "nguoi_lay", "fieldtype": "Link", "options": "User", "label": "Người lấy", "read_only": 1},
  {"fieldname": "luc_lay", "fieldtype": "Datetime", "label": "Lúc lấy", "read_only": 1}
 ],
 "index_web_pages_for_search": 0,
 "istable": 1,
 "links": [],
 "modified": "2026-09-18 00:00:00.000000",
 "modified_by": "Administrator",
 "module": "Vi Tri Kho",
 "name": "Location Allocation",
 "owner": "Administrator",
 "permissions": [],
 "sort_field": "modified",
 "sort_order": "DESC",
 "states": []
}
```

`erpnext/vi_tri_kho/doctype/location_allocation/location_allocation.py`:

```python
# Bảng con thuần dữ liệu: mọi phép kiểm nằm ở `vitri/lay_hang.kiem_phan_bo_khi_luu`
# (chạy trên chứng từ CHA, vì phải đối chiếu với dòng hàng và với tồn của ô — hai
# thứ mà một dòng bảng con không tự nhìn thấy).

from frappe.model.document import Document


class LocationAllocation(Document):
	pass
```

- [ ] **Step 4: Viết patch gắn field vào Delivery Note**

`erpnext/vi_tri_kho/patches/v1_0/them_phan_bo_vi_tri.py`:

```python
"""Thêm `Delivery Note.custom_phan_bo_vi_tri` — bảng phân bổ vị trí (spec lấy hàng §3.1).

READ-ONLY có chủ đích, cùng lẽ với `custom_so_goi` / `custom_o_in_tem`: bảng này
là KẾT QUẢ của việc thủ kho quét tem ngoài kệ, không phải chỗ để khai tay. Sửa
tay được nghĩa là sổ vị trí nói một đằng, hàng trên kệ một nẻo — mà tổng tồn vẫn
khớp nên không báo cáo nào bắt được.
"""

from frappe.custom.doctype.custom_field.custom_field import create_custom_field


def execute():
	create_custom_field(
		"Delivery Note",
		{
			"fieldname": "custom_phan_bo_vi_tri",
			"label": "Phân bổ vị trí",
			"fieldtype": "Table",
			"options": "Location Allocation",
			"read_only": 1,
			"insert_after": "items",
			"description": "Ô đã lấy hàng, do trang Lấy hàng (PDA) ghi. Trống = hệ tự chọn ô theo hạn dùng.",
		},
	)
```

Thêm dòng cuối `erpnext/patches.txt`:

```
erpnext.vi_tri_kho.patches.v1_0.them_phan_bo_vi_tri
```

- [ ] **Step 5: Migrate rồi chạy lại test**

Chạy: `bench --site erptest.local migrate` rồi
`bench --site erptest.local run-tests --module erpnext.vi_tri_kho.doctype.location_allocation.test_location_allocation`
Chờ: `OK` (2 bài).

- [ ] **Step 6: Commit**

```bash
git add erpnext/vi_tri_kho/doctype/location_allocation erpnext/vi_tri_kho/patches/v1_0/them_phan_bo_vi_tri.py erpnext/patches.txt
git commit -m "feat(vi_tri_kho): bảng phân bổ vị trí Location Allocation trên phiếu giao"
```

---

### Task 2: Hook ghi sổ đọc bảng phân bổ

**Files:**
- Create: `erpnext/vi_tri_kho/vitri/lay_hang.py`
- Modify: `erpnext/vi_tri_kho/vitri/hook_sle.py` (hàm `_ghi_mot_phan`, khoảng dòng 161-177)
- Create: `erpnext/vi_tri_kho/tests/test_lay_hang.py`

**Interfaces:**
- Consumes: doctype `Location Allocation`, field `Delivery Note.custom_phan_bo_vi_tri` (Task 1).
- Produces:
  - `lay_hang.TEN_BANG_PHAN_BO: str` = `"custom_phan_bo_vi_tri"`
  - `lay_hang.VAI_TRO_DUOC_LAY: set[str]`
  - `lay_hang.phan_bo_cua_dong(chung_tu_type: str, chung_tu: str, dong_hang: str, so_lo: str | None) -> list[dict]` — mỗi dict có `name`, `o`, `so_luong` (số dương).
  - `hook_sle._phan_bo_da_khai(sle, so_lo, can_xuat: float) -> list[dict] | None` — `None` = không có phân bổ (đi tiếp FEFO).

- [ ] **Step 1: Viết bài test đỏ**

Tạo `erpnext/vi_tri_kho/tests/test_lay_hang.py`:

```python
"""Lấy hàng theo phân bổ — sổ vị trí phải trừ ĐÚNG ô thủ kho đã quét.

Bài chịu lực của cả thiết kế là `test_ghi_so_theo_o_da_phan_bo_chu_khong_theo_fefo`:
nó phân bổ vào ô mà FEFO KHÔNG chọn. Thiếu chốt đó thì một cài đặt bỏ qua phân bổ
và cứ chạy FEFO vẫn xanh, vì cả hai đường đều cho ra tổng đúng.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import nowdate

from erpnext.vi_tri_kho.vitri import so

KHO = "Kho Miyano - MYN"
CTY = "Miyano Việt Nam"
KHACH = "Bệnh viện DEMO Miyano E2E"
ITEM = "9L-VT-LAY-HANG"
LO = "9L-LO-LAY-01"
O_GAN = "9L01010101"
O_XA = "9L01010102"
DIEM_TEST = "test_lay_hang"


def _o(ma_o):
	if not frappe.db.exists("Storage Location", ma_o):
		frappe.get_doc({"doctype": "Storage Location", "ma_o": ma_o, "kho": KHO}).insert(
			ignore_permissions=True
		)
	return ma_o


def _vat_tu():
	if not frappe.db.exists("Item", ITEM):
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": ITEM,
				"item_name": "Hàng thử lấy hàng PDA",
				"item_group": "All Item Groups",
				"stock_uom": "Nos",
				"is_stock_item": 1,
				"has_batch_no": 1,
				"create_new_batch": 0,
			}
		).insert(ignore_permissions=True)
	return ITEM


def _lo():
	if not frappe.db.exists("Batch", LO):
		frappe.get_doc(
			{"doctype": "Batch", "batch_id": LO, "item": ITEM, "expiry_date": "2029-01-31"}
		).insert(ignore_permissions=True)
	return LO


def _nhap_kho(so_luong):
	"""Nhập hàng thật vào ERPNext (Bin) — phiếu giao cần tồn kho thật, không chỉ sổ vị trí."""
	se = frappe.get_doc(
		{
			"doctype": "Stock Entry",
			"stock_entry_type": "Material Receipt",
			"company": CTY,
			"items": [
				{
					"item_code": ITEM,
					"qty": so_luong,
					"t_warehouse": KHO,
					"basic_rate": 1000,
					"batch_no": LO,
					"use_serial_batch_fields": 1,
				}
			],
		}
	)
	se.insert(ignore_permissions=True)
	se.submit()
	return se


def _chuyen_vao_o(cap):
	"""Chuyển hàng từ ô Chưa xếp sang các ô thật. `cap` = [(ô, số lượng), ...]."""
	chua_xep = frappe.db.get_value("Storage Location", {"kho": KHO, "la_o_chua_xep": 1})
	pxep = frappe.get_doc(
		{
			"doctype": "Location Transfer",
			"kho": KHO,
			"ngay": nowdate(),
			"items": [
				{"vat_tu": ITEM, "so_lo": LO, "tu_o": chua_xep, "den_o": o, "so_luong": sl}
				for o, sl in cap
			],
		}
	)
	pxep.insert(ignore_permissions=True)
	pxep.submit()
	return pxep


def _phieu_giao(so_luong, phan_bo=None):
	"""Phiếu giao NHÁP cho `so_luong`, kèm phân bổ nếu có. `phan_bo` = [(ô, số lượng), ...]."""
	dn = frappe.get_doc(
		{
			"doctype": "Delivery Note",
			"company": CTY,
			"customer": KHACH,
			"posting_date": nowdate(),
			"items": [
				{
					"item_code": ITEM,
					"qty": so_luong,
					"rate": 5000,
					"warehouse": KHO,
					"batch_no": LO,
					"use_serial_batch_fields": 1,
				}
			],
		}
	)
	dn.insert(ignore_permissions=True)
	if phan_bo:
		for o, sl in phan_bo:
			dn.append(
				"custom_phan_bo_vi_tri",
				{"dong_hang": dn.items[0].name, "vat_tu": ITEM, "so_lo": LO, "o": o, "so_luong": sl},
			)
		dn.save(ignore_permissions=True)
	return dn


class TestGhiSoTheoPhanBo(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.savepoint(DIEM_TEST)
		_vat_tu()
		_lo()
		_o(O_GAN)
		_o(O_XA)
		# Thứ tự lấy hàng: ô GẦN đứng trước ô XA trong cây, nên FEFO chọn ô GẦN.
		_nhap_kho(30)
		_chuyen_vao_o([(O_GAN, 20), (O_XA, 10)])

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point=DIEM_TEST)

	def test_ghi_so_theo_o_da_phan_bo_chu_khong_theo_fefo(self):
		"""Phân bổ vào ô mà FEFO KHÔNG chọn — chốt chịu lực của cả thiết kế."""
		dn = _phieu_giao(10, phan_bo=[(O_XA, 10)])
		dn.submit()

		dong = frappe.get_all(
			"Location Ledger Entry", {"chung_tu": dn.name}, ["o", "so_luong"]
		)
		self.assertEqual([(d.o, d.so_luong) for d in dong], [(O_XA, -10.0)])
		# Chốt âm: ô mà FEFO lẽ ra chọn KHÔNG bị đụng tới.
		self.assertEqual(so.ton_o(O_GAN, ITEM, LO), 20.0)
		self.assertEqual(so.ton_o(O_XA, ITEM, LO), 0.0)

	def test_khong_co_phan_bo_thi_van_chay_fefo_nhu_cu(self):
		"""Chốt âm cho đường CŨ: mọi chứng từ không qua trang lấy hàng phải y như trước."""
		dn = _phieu_giao(10)
		dn.submit()

		self.assertEqual(so.ton_o(O_GAN, ITEM, LO), 10.0, "FEFO phải lấy ở ô đứng trước")
		self.assertEqual(so.ton_o(O_XA, ITEM, LO), 10.0)

	def test_tong_phan_bo_lech_thi_chan_va_khong_ghi_dong_so_nao(self):
		dn = _phieu_giao(10, phan_bo=[(O_XA, 4)])
		with self.assertRaisesRegex(frappe.ValidationError, "phân bổ"):
			dn.submit()

		self.assertEqual(
			frappe.get_all("Location Ledger Entry", {"chung_tu": dn.name}),
			[],
			"chặn rồi thì không dòng sổ nào được sống sót",
		)

	def test_phan_bo_nhieu_o_cho_mot_dong(self):
		dn = _phieu_giao(25, phan_bo=[(O_XA, 10), (O_GAN, 15)])
		dn.submit()

		con = {(d.o): d.so_luong for d in frappe.get_all(
			"Location Balance", {"vat_tu": ITEM, "so_lo": LO}, ["o", "so_luong"]
		)}
		self.assertEqual(con.get(O_XA), 0.0)
		self.assertEqual(con.get(O_GAN), 5.0)

	def test_huy_phieu_giao_tra_hang_ve_dung_o_da_lay(self):
		"""`dao_theo_o_goc` tra theo dòng sổ đã ghi — không được rơi về CHUA-XEP."""
		dn = _phieu_giao(10, phan_bo=[(O_XA, 10)])
		dn.submit()
		dn.reload()
		dn.cancel()

		self.assertEqual(so.ton_o(O_XA, ITEM, LO), 10.0)
		chua_xep = frappe.db.get_value("Storage Location", {"kho": KHO, "la_o_chua_xep": 1})
		self.assertEqual(so.ton_o(chua_xep, ITEM, LO), 0.0)
```

- [ ] **Step 2: Chạy để thấy đỏ**

Chạy: `bench --site erptest.local run-tests --module erpnext.vi_tri_kho.tests.test_lay_hang`
Chờ: FAILED — bài `test_ghi_so_theo_o_da_phan_bo...` đỏ vì sổ ghi vào `O_GAN` (FEFO) chứ không phải `O_XA`.

- [ ] **Step 3: Viết `vitri/lay_hang.py` (phần đọc phân bổ)**

```python
"""Lấy hàng: phân bổ ô cho từng dòng phiếu giao, và trang PDA quét xác nhận.

VÌ SAO CÓ FILE NÀY: trước 18/09/2026, ô lấy hàng do `fefo.chon_o_xuat()` chọn
BÊN TRONG hook, đúng lúc duyệt phiếu giao — thủ kho không có danh sách đi lấy, và
không ai đối chiếu "hệ trừ ô A" với "người thật lấy ở ô B". Hai bên lệch nhau thì
TỔNG tồn kho vẫn đúng nên `doi_soat_kho` vẫn báo khớp; sai lệch chỉ lộ ra lúc
kiểm kê thực tế, khi đã mất dấu vết.

Bảng phân bổ `Location Allocation` là thứ spec nền tảng (§4.5, §5.4) đã dành sẵn
chỗ cho từ giai đoạn 1 — file này dựng tiếp đúng thiết kế đó, không nghĩ lại.
"""

import frappe
from frappe import _
from frappe.utils import flt

TEN_BANG_PHAN_BO = "custom_phan_bo_vi_tri"

# Chỉ phiếu giao có giao diện phân bổ (spec §2). Các chứng từ khác vẫn đi đường
# cũ — hằng số ở đây để nơi đọc không phải đoán, và để mở rộng sau này là sửa
# đúng một chỗ.
CHUNG_TU_CO_PHAN_BO = ("Delivery Note",)

# Cùng bộ vai trò với `xep.py`/`quet.py` — thủ kho phải tự làm được, đây là việc
# hằng ngày.
VAI_TRO_DUOC_LAY = {"System Manager", "Stock Manager", "Stock User"}


def phan_bo_cua_dong(chung_tu_type: str, chung_tu: str, dong_hang: str, so_lo: str | None) -> list[dict]:
	"""Các dòng phân bổ của ĐÚNG (dòng hàng, lô). Không có → danh sách rỗng.

	So `so_lo` TRONG PYTHON, không đưa vào `filters`: hàng không quản lý lô lưu
	`None` ở bảng phân bổ nhưng `''` ở vài chỗ khác trong module, và một bộ lọc SQL
	so thẳng sẽ khớp 0 dòng trong im lặng — đúng kiểu hỏng mà cả module này phải
	tránh (xem `xep.py`, `quet.py`).
	"""
	if chung_tu_type not in CHUNG_TU_CO_PHAN_BO or not dong_hang:
		return []

	dong = frappe.get_all(
		"Location Allocation",
		filters={
			"parenttype": chung_tu_type,
			"parent": chung_tu,
			"parentfield": TEN_BANG_PHAN_BO,
			"dong_hang": dong_hang,
		},
		fields=["name", "o", "so_lo", "so_luong"],
		order_by="idx asc",
	)
	return [d for d in dong if (d.so_lo or None) == (so_lo or None)]


def tong_phan_bo(dong: list[dict]) -> float:
	return flt(sum(flt(d["so_luong"]) for d in dong))
```

- [ ] **Step 4: Mở nhánh trong hook**

Trong `erpnext/vi_tri_kho/vitri/hook_sle.py`, thay thân `_ghi_mot_phan` (dòng 161-177) bằng:

```python
def _ghi_mot_phan(sle, so_lo, so_luong):
	"""Ghi sổ cho một (lô, số lượng) của một dòng SLE.

	Nhập (số dương): trước tiên tra xem chứng từ này (CÙNG chung_tu_row) đã
	từng bị MỘT bút toán đảo khác (`dao_theo_o_goc`) rút hàng ra khỏi ô nào
	chưa — có thì trả hàng về ĐÚNG (các) ô đó, không dồn CHUA-XEP. Không có
	dấu vết đảo nào → dồn vào CHUA-XEP như cũ.

	Xuất (số âm): ưu tiên BẢNG PHÂN BỔ (thủ kho đã quét ngoài kệ, 18/09/2026);
	không có phân bổ thì chọn ô theo FEFO như cũ.
	"""
	if so_luong > 0:
		phan_bo = _tra_lai_o_da_dao(sle, so_lo, so_luong)
	else:
		phan_bo = _phan_bo_da_khai(sle, so_lo, -so_luong)
		if phan_bo is None:
			phan_bo = [
				{"o": p["o"], "so_luong": -p["so_luong"]}
				for p in chon_o_xuat(sle.warehouse, sle.item_code, so_lo, -so_luong)
			]
```

(phần `for p in phan_bo: ghi_dong_so(...)` bên dưới giữ nguyên, không sửa)

Thêm hàm mới ngay dưới `_ghi_mot_phan`:

```python
def _phan_bo_da_khai(sle, so_lo, can_xuat) -> list[dict] | None:
	"""Phân bổ ô mà người lấy hàng đã quét, hoặc `None` nếu chứng từ không có.

	`None` (không phải danh sách rỗng) là tín hiệu "đi tiếp FEFO" — phân biệt rõ
	với "có phân bổ nhưng bằng 0", vốn là dữ liệu hỏng chứ không phải đường cũ.

	Tổng lệch thì CHẶN, không tự chữa: phân bổ dở dang nghĩa là mới quét được một
	phần, và im lặng chạy FEFO cho phần còn lại sẽ trừ những ô chưa ai tới lấy —
	sai lệch mà đối soát theo tổng không bao giờ bắt được (spec lấy hàng §5).
	"""
	dong = phan_bo_cua_dong(sle.voucher_type, sle.voucher_no, sle.voucher_detail_no, so_lo)
	if not dong:
		return None

	tong = tong_phan_bo(dong)
	if abs(tong - flt(can_xuat)) > _SAI_SO_CHO_PHEP:
		frappe.log_error(
			title=cat_tieu_de(f"vi_tri_kho: phan bo lech ({sle.voucher_no})"),
			message=(
				f"sle={sle.name} dong_hang={sle.voucher_detail_no} vat_tu={sle.item_code} "
				f"so_lo={so_lo} phan_bo={tong} can_xuat={can_xuat}"
			),
		)
		frappe.throw(
			_(
				"Phiếu giao {0}: dòng {1}{2} phân bổ {3} nhưng xuất {4}. Mở lại trang Lấy hàng "
				"để quét tiếp, hoặc xoá phân bổ của dòng này để hệ tự chọn ô theo hạn dùng."
			).format(
				sle.voucher_no,
				sle.item_code,
				_(", lô {0}").format(so_lo) if so_lo else "",
				flt(tong, 3),
				flt(can_xuat, 3),
			)
		)

	return [{"o": d["o"], "so_luong": -flt(d["so_luong"])} for d in dong]
```

Thêm import ở đầu `hook_sle.py` (cạnh các import `from erpnext.vi_tri_kho.vitri...` sẵn có):

```python
from erpnext.vi_tri_kho.vitri.lay_hang import phan_bo_cua_dong, tong_phan_bo
from erpnext.vi_tri_kho.vitri.nhat_ky_loi import cat_tieu_de
```

- [ ] **Step 5: Chạy lại bài của task**

Chạy: `bench --site erptest.local run-tests --module erpnext.vi_tri_kho.tests.test_lay_hang`
Chờ: `OK` (5 bài).

- [ ] **Step 6: Chạy CẢ BỘ để chắc đường cũ không đổi**

Chạy từng module một (bench không cho chạy cả thư mục):

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
for f in apps/erpnext/erpnext/vi_tri_kho/tests/test_*.py apps/erpnext/erpnext/vi_tri_kho/doctype/*/test_*.py apps/erpnext/erpnext/vi_tri_kho/report/*/test_*.py; do
  [ -f "$f" ] || continue
  m=$(echo ${f#apps/erpnext/} | sed 's/\.py$//; s#/#.#g')
  out=$(bench --site erptest.local run-tests --module $m 2>&1)
  echo "$out" | grep -qE "^OK" || { echo "FAILED: $m"; echo "$out" | grep -E "^(FAIL|ERROR):"; }
done
```

Chờ: không dòng `FAILED:` nào.

- [ ] **Step 7: Commit**

```bash
git add erpnext/vi_tri_kho/vitri/lay_hang.py erpnext/vi_tri_kho/vitri/hook_sle.py erpnext/vi_tri_kho/tests/test_lay_hang.py
git commit -m "feat(vi_tri_kho): hook ghi sổ theo bảng phân bổ, lệch tổng thì chặn"
```

---

### Task 3: Lớp kiểm sớm trên phiếu giao

**Files:**
- Modify: `erpnext/vi_tri_kho/vitri/lay_hang.py` (thêm `kiem_phan_bo_khi_luu`)
- Modify: `erpnext/hooks.py` (khối `doc_events` → khoá `"Delivery Note"` ĐÃ CÓ, thêm `validate`)
- Modify: `erpnext/vi_tri_kho/tests/test_lay_hang.py` (thêm lớp `TestKiemSom`)

**Interfaces:**
- Consumes: `phan_bo_cua_dong`, `TEN_BANG_PHAN_BO` (Task 2).
- Produces: `lay_hang.kiem_phan_bo_khi_luu(doc, method=None) -> None` — ném `frappe.ValidationError` khi phân bổ sai.

- [ ] **Step 1: Viết bài test đỏ**

Thêm vào cuối `erpnext/vi_tri_kho/tests/test_lay_hang.py`:

```python
class TestKiemSom(FrappeTestCase):
	"""Chặn ngay khi LƯU NHÁP — lớp người dùng thật sự nhìn thấy (spec §5).

	Hook là lưới an toàn cuối, nhưng nó chạy sau khi đã bấm Duyệt: báo ở đó thì
	người dùng chỉ thấy phiếu bật lỗi, không biết sửa dòng nào.
	"""

	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.savepoint(DIEM_TEST)
		_vat_tu()
		_lo()
		_o(O_GAN)
		_o(O_XA)
		_nhap_kho(30)
		_chuyen_vao_o([(O_GAN, 20), (O_XA, 10)])

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point=DIEM_TEST)

	def test_o_thuoc_kho_khac_bi_chan(self):
		o_khac = "9Y09090901"
		if not frappe.db.exists("Storage Location", o_khac):
			frappe.get_doc(
				{"doctype": "Storage Location", "ma_o": o_khac, "kho": "Hàng trả về - MYN"}
			).insert(ignore_permissions=True)
		with self.assertRaisesRegex(frappe.ValidationError, "không thuộc kho"):
			_phieu_giao(5, phan_bo=[(o_khac, 5)])

	def test_o_nhom_bi_chan(self):
		with self.assertRaisesRegex(frappe.ValidationError, "nút nhóm"):
			_phieu_giao(5, phan_bo=[("9L0101", 5)])

	def test_phan_bo_vuot_so_luong_dong_bi_chan(self):
		with self.assertRaisesRegex(frappe.ValidationError, "vượt"):
			_phieu_giao(5, phan_bo=[(O_GAN, 6)])

	def test_o_khong_du_ton_bi_chan(self):
		with self.assertRaisesRegex(frappe.ValidationError, "chỉ còn"):
			_phieu_giao(30, phan_bo=[(O_XA, 30)])

	def test_dong_hang_khong_thuoc_phieu_bi_chan(self):
		dn = _phieu_giao(5)
		dn.append(
			"custom_phan_bo_vi_tri",
			{"dong_hang": "khong-co-that", "vat_tu": ITEM, "so_lo": LO, "o": O_GAN, "so_luong": 5},
		)
		with self.assertRaisesRegex(frappe.ValidationError, "không thuộc phiếu"):
			dn.save(ignore_permissions=True)

	def test_phan_bo_dang_do_van_luu_nhap_duoc(self):
		"""Quét dở vẫn phải lưu được — nếu không thì không ai lấy hàng nhiều lượt được."""
		dn = _phieu_giao(20, phan_bo=[(O_GAN, 5)])
		self.assertEqual(len(dn.custom_phan_bo_vi_tri), 1)
```

- [ ] **Step 2: Chạy để thấy đỏ**

Chạy: `bench --site erptest.local run-tests --module erpnext.vi_tri_kho.tests.test_lay_hang`
Chờ: FAILED — các bài `TestKiemSom` không thấy lỗi nào được ném ra.

- [ ] **Step 3: Viết phép kiểm**

Thêm vào `erpnext/vi_tri_kho/vitri/lay_hang.py`:

```python
def kiem_phan_bo_khi_luu(doc, method=None):
	"""Lớp kiểm SỚM cho phân bổ trên chứng từ (spec §5). Gắn `doc_events` validate.

	Cho phép tổng phân bổ NHỎ HƠN số lượng dòng — đó là trạng thái "đang quét dở",
	và chặn nó ở đây là bắt thủ kho lấy xong cả phiếu trong một hơi. Phép so BẰNG
	nằm ở lúc duyệt (hook, Task 2).
	"""
	bang = doc.get(TEN_BANG_PHAN_BO) or []
	if not bang:
		return

	dong_hang = {d.name: d for d in doc.items}
	da_phan_bo: dict[tuple, float] = {}

	for p in bang:
		dh = dong_hang.get(p.dong_hang)
		if not dh:
			frappe.throw(
				_(
					"Phân bổ vị trí dòng {0}: dòng hàng {1} không thuộc phiếu này (có thể đã bị "
					"xoá). Mở lại trang Lấy hàng để quét lại."
				).format(p.idx, p.dong_hang)
			)
		if p.vat_tu != dh.item_code:
			frappe.throw(
				_("Phân bổ vị trí dòng {0}: mặt hàng {1} khác mặt hàng {2} của dòng hàng.").format(
					p.idx, p.vat_tu, dh.item_code
				)
			)
		if (p.so_lo or None) != (dh.get("batch_no") or None):
			frappe.throw(
				_("Phân bổ vị trí dòng {0}: lô {1} khác lô {2} của dòng hàng.").format(
					p.idx, p.so_lo or "—", dh.get("batch_no") or "—"
				)
			)
		if flt(p.so_luong) <= 0:
			frappe.throw(_("Phân bổ vị trí dòng {0}: số lượng phải lớn hơn 0.").format(p.idx))

		thong_tin = frappe.db.get_value(
			"Storage Location", p.o, ["kho", "is_group"], as_dict=True
		)
		if not thong_tin:
			frappe.throw(_("Phân bổ vị trí dòng {0}: ô {1} không tồn tại.").format(p.idx, p.o))
		if thong_tin.kho != dh.warehouse:
			frappe.throw(
				_("Phân bổ vị trí dòng {0}: ô {1} không thuộc kho {2} của dòng hàng.").format(
					p.idx, p.o, dh.warehouse
				)
			)
		if thong_tin.is_group:
			frappe.throw(
				_(
					"Phân bổ vị trí dòng {0}: {1} là nút nhóm (cấp Khu/Dãy/Khoang/Tầng), không "
					"chứa hàng được."
				).format(p.idx, p.o)
			)

		khoa = (p.dong_hang, p.so_lo or "")
		da_phan_bo[khoa] = da_phan_bo.get(khoa, 0.0) + flt(p.so_luong)

		# Tồn của ô đọc từ bộ đệm — đủ cho lớp sớm; phép chặn tồn âm THẬT vẫn nằm
		# ở đường ghi sổ, nơi có khoá dòng của InnoDB (xem `location_transfer.py`).
		con = flt(ton_o(p.o, p.vat_tu, p.so_lo or None))
		if da_phan_bo[khoa] > con + _SAI_SO:
			frappe.throw(
				_("Phân bổ vị trí dòng {0}: ô {1} chỉ còn {2} của {3}{4}.").format(
					p.idx, p.o, flt(con, 3), p.vat_tu, _(", lô {0}").format(p.so_lo) if p.so_lo else ""
				)
			)

	for (dh_ten, _lo), tong in da_phan_bo.items():
		dh = dong_hang[dh_ten]
		if tong > flt(dh.qty) + _SAI_SO:
			frappe.throw(
				_(
					"Phân bổ vị trí cho {0}: tổng {1} vượt số lượng {2} của dòng hàng. Bỏ bớt dòng "
					"phân bổ hoặc sửa số lượng trên phiếu."
				).format(dh.item_code, flt(tong, 3), flt(dh.qty, 3))
			)
```

Thêm vào đầu file (cạnh các import sẵn có):

```python
from erpnext.vi_tri_kho.vitri.so import ton_o

_SAI_SO = 1e-9
```

- [ ] **Step 4: Nối `doc_events`**

Trong `erpnext/hooks.py`, khối `doc_events` ĐÃ CÓ khoá `"Delivery Note"` (dùng cho HĐĐT) — **thêm vào chính khoá đó**, không tạo khoá thứ hai (khoá sau nuốt khoá trước trong im lặng, dự án đã dính một lần):

```python
	"Delivery Note": {
		"validate": "erpnext.vi_tri_kho.vitri.lay_hang.kiem_phan_bo_khi_luu",
		"before_cancel": "erpnext.einvoice.builder.before_delivery_note_cancel",
		"on_cancel": "erpnext.einvoice.builder.on_delivery_note_cancel",
	},
```

- [ ] **Step 5: Chạy lại bài của task**

Chạy: `bench --site erptest.local clear-cache && bench --site erptest.local run-tests --module erpnext.vi_tri_kho.tests.test_lay_hang`
Chờ: `OK` (11 bài).

- [ ] **Step 6: Commit**

```bash
git add erpnext/vi_tri_kho/vitri/lay_hang.py erpnext/hooks.py erpnext/vi_tri_kho/tests/test_lay_hang.py
git commit -m "feat(vi_tri_kho): kiểm phân bổ vị trí ngay khi lưu phiếu giao nháp"
```

---

### Task 4: Máy chủ cho trang PDA — phần ĐỌC

**Files:**
- Modify: `erpnext/vi_tri_kho/vitri/lay_hang.py`
- Modify: `erpnext/vi_tri_kho/tests/test_lay_hang.py` (thêm lớp `TestDocChoTrang`)

**Interfaces:**
- Consumes: `phan_bo_cua_dong`, `VAI_TRO_DUOC_LAY`.
- Produces:
  - `danh_sach_phieu_giao(kho: str) -> list[dict]` — mỗi dict: `name`, `khach_hang`, `so_dong`, `can_lay`, `da_lay`, `nguoi_dang_lay`.
  - `mo_phieu_giao(phieu: str) -> dict` — `name`, `kho`, `khach_hang`, `dong`: list of `{dong_hang, vat_tu, ten_hang, don_vi, so_lo, hsd, can_lay, da_lay, o_nen_lay: [{o, ma_in_nhan, so_luong}], da_lay_o: [{name, o, so_luong}]}`.
  - `quet_de_lay(phieu: str, ma: str) -> dict` — `loai`: `"lo"` / `"lo_khac"` / `"o"` / `None`.

- [ ] **Step 1: Viết bài test đỏ**

Thêm vào `erpnext/vi_tri_kho/tests/test_lay_hang.py`:

```python
class TestDocChoTrang(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.savepoint(DIEM_TEST)
		for ma in (LO, O_GAN, O_XA):
			frappe.cache().delete_value(f"erpnext:barcode_scan:{ma}")
		_vat_tu()
		_lo()
		_o(O_GAN)
		_o(O_XA)
		_nhap_kho(30)
		_chuyen_vao_o([(O_GAN, 20), (O_XA, 10)])
		self.dn = _phieu_giao(12)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point=DIEM_TEST)

	def test_danh_sach_hien_phieu_nhap_va_tien_do(self):
		from erpnext.vi_tri_kho.vitri.lay_hang import danh_sach_phieu_giao

		ds = {d["name"]: d for d in danh_sach_phieu_giao(KHO)}
		self.assertIn(self.dn.name, ds)
		self.assertEqual(ds[self.dn.name]["can_lay"], 12.0)
		self.assertEqual(ds[self.dn.name]["da_lay"], 0.0)

	def test_mo_phieu_ra_o_nen_lay_theo_fefo(self):
		from erpnext.vi_tri_kho.vitri.lay_hang import mo_phieu_giao

		p = mo_phieu_giao(self.dn.name)
		self.assertEqual(len(p["dong"]), 1)
		d = p["dong"][0]
		self.assertEqual((d["vat_tu"], d["so_lo"], d["can_lay"]), (ITEM, LO, 12.0))
		# 12 lấy hết ô đứng trước (20) → chỉ một ô được gợi ý.
		self.assertEqual([o["o"] for o in d["o_nen_lay"]], [O_GAN])

	def test_quet_lo_cua_phieu_va_quet_o(self):
		from erpnext.vi_tri_kho.vitri.lay_hang import quet_de_lay

		self.assertEqual(quet_de_lay(self.dn.name, LO)["loai"], "lo")
		self.assertEqual(quet_de_lay(self.dn.name, O_GAN)["loai"], "o")
		self.assertEqual(quet_de_lay(self.dn.name, "9L-KHONG-CO-GI")["loai"], None)

	def test_quet_lo_khac_cung_mat_hang_bao_loai_lo_khac_kem_hsd(self):
		from erpnext.vi_tri_kho.vitri.lay_hang import quet_de_lay

		lo_khac = "9L-LO-LAY-02"
		if not frappe.db.exists("Batch", lo_khac):
			frappe.get_doc(
				{"doctype": "Batch", "batch_id": lo_khac, "item": ITEM, "expiry_date": "2030-12-31"}
			).insert(ignore_permissions=True)
		frappe.cache().delete_value(f"erpnext:barcode_scan:{lo_khac}")

		kq = quet_de_lay(self.dn.name, lo_khac)
		self.assertEqual(kq["loai"], "lo_khac")
		self.assertEqual(kq["so_lo"], lo_khac)
		self.assertTrue(kq["han_xa_hon"], "lô 2030 xa hơn lô 2029 của phiếu")

	def test_khong_co_vai_tro_kho_thi_bi_chan(self):
		from erpnext.vi_tri_kho.vitri.lay_hang import danh_sach_phieu_giao

		ten = "lay-hang-khong-quyen@mo-phong.local"
		if not frappe.db.exists("User", ten):
			frappe.get_doc(
				{"doctype": "User", "email": ten, "first_name": "Lay", "send_welcome_email": 0, "roles": []}
			).insert(ignore_permissions=True)
		frappe.set_user(ten)
		with self.assertRaises(frappe.PermissionError):
			danh_sach_phieu_giao(KHO)
```

- [ ] **Step 2: Chạy để thấy đỏ**

Chạy: `bench --site erptest.local run-tests --module erpnext.vi_tri_kho.tests.test_lay_hang`
Chờ: FAILED — `ImportError: cannot import name 'danh_sach_phieu_giao'`.

- [ ] **Step 3: Viết phần đọc**

Thêm vào `erpnext/vi_tri_kho/vitri/lay_hang.py`:

```python
def _kiem_tra_quyen():
	"""`@frappe.whitelist()` một mình chỉ chặn khách vãng lai — xem `xep.py`."""
	if not VAI_TRO_DUOC_LAY & set(frappe.get_roles()):
		frappe.throw(_("Bạn không có quyền lấy hàng theo vị trí."), frappe.PermissionError)


def _da_lay_theo_dong(doc) -> dict:
	"""{(tên dòng hàng): tổng đã phân bổ}."""
	tong: dict[str, float] = {}
	for p in doc.get(TEN_BANG_PHAN_BO) or []:
		tong[p.dong_hang] = tong.get(p.dong_hang, 0.0) + flt(p.so_luong)
	return tong


@frappe.whitelist()
def danh_sach_phieu_giao(kho: str) -> list[dict]:
	"""Phiếu giao NHÁP của `kho`, mới nhất trước, kèm tiến độ lấy."""
	_kiem_tra_quyen()
	ten = frappe.get_all(
		"Delivery Note",
		filters={"docstatus": 0, "set_warehouse": kho},
		pluck="name",
		order_by="modified desc",
		limit=50,
	)
	ket_qua = []
	for t in ten:
		doc = frappe.get_doc("Delivery Note", t)
		dong_kho_nay = [d for d in doc.items if d.warehouse == kho]
		if not dong_kho_nay:
			continue
		da = _da_lay_theo_dong(doc)
		nguoi = {p.nguoi_lay for p in doc.get(TEN_BANG_PHAN_BO) or [] if p.nguoi_lay}
		ket_qua.append(
			{
				"name": doc.name,
				"khach_hang": doc.customer_name or doc.customer,
				"so_dong": len(dong_kho_nay),
				"can_lay": flt(sum(flt(d.qty) for d in dong_kho_nay)),
				"da_lay": flt(sum(da.get(d.name, 0.0) for d in dong_kho_nay)),
				"nguoi_dang_lay": sorted(nguoi - {frappe.session.user}),
			}
		)
	return ket_qua


@frappe.whitelist()
def mo_phieu_giao(phieu: str) -> dict:
	"""Chi tiết một phiếu giao để lấy hàng: từng dòng cần bao nhiêu, nên tới ô nào.

	`o_nen_lay` gọi `fefo.chon_o_xuat` — ĐÚNG hàm mà hook sẽ dùng nếu không ai
	phân bổ, nên danh sách gợi ý và hành vi mặc định không bao giờ nói khác nhau.
	Hết hàng thì `chon_o_xuat` ném lỗi; ở đây nuốt và trả danh sách rỗng, vì màn
	hình phải mở được để thủ kho thấy vì sao (khuôn Ruling N ở `xep.hang_chua_xep`).
	"""
	_kiem_tra_quyen()
	doc = frappe.get_doc("Delivery Note", phieu)
	da = _da_lay_theo_dong(doc)
	dong = []
	for d in doc.items:
		con_can = flt(d.qty) - da.get(d.name, 0.0)
		try:
			goi_y = chon_o_xuat(d.warehouse, d.item_code, d.batch_no or None, max(con_can, 0)) if con_can > 0 else []
		except Exception:
			frappe.log_error(title=cat_tieu_de(f"vi_tri_kho: mo_phieu_giao goi y loi ({phieu})"))
			goi_y = []
		dong.append(
			{
				"dong_hang": d.name,
				"vat_tu": d.item_code,
				"ten_hang": d.item_name,
				"don_vi": d.stock_uom or d.uom,
				"so_lo": d.batch_no or None,
				"hsd": frappe.db.get_value("Batch", d.batch_no, "expiry_date") if d.batch_no else None,
				"can_lay": flt(d.qty),
				"da_lay": da.get(d.name, 0.0),
				"o_nen_lay": [
					{
						"o": g["o"],
						"ma_in_nhan": frappe.db.get_value("Storage Location", g["o"], "ma_in_nhan"),
						"so_luong": flt(g["so_luong"]),
					}
					for g in goi_y
				],
				"da_lay_o": [
					{"name": p.name, "o": p.o, "so_luong": flt(p.so_luong)}
					for p in (doc.get(TEN_BANG_PHAN_BO) or [])
					if p.dong_hang == d.name
				],
			}
		)
	return {
		"name": doc.name,
		"kho": doc.set_warehouse or (doc.items[0].warehouse if doc.items else None),
		"khach_hang": doc.customer_name or doc.customer,
		"dong": dong,
	}


@frappe.whitelist()
def quet_de_lay(phieu: str, ma: str) -> dict:
	"""Nhận diện một mã quét trên trang lấy hàng.

	`loai`: `"lo"` (lô ĐANG có trên phiếu) · `"lo_khac"` (lô khác nhưng cùng một
	mặt hàng của phiếu — kèm `han_xa_hon` để màn hình cảnh báo) · `"o"` · `None`.
	Quét nhầm không bao giờ nổ — cùng lời hứa `quet.py`.
	"""
	from erpnext.stock.utils import scan_barcode
	from erpnext.vi_tri_kho.vitri.quet import _tim_o

	_kiem_tra_quyen()
	ma = (ma or "").strip()
	if not ma:
		return {"loai": None}
	doc = frappe.get_doc("Delivery Note", phieu)
	try:
		kq = scan_barcode(ma) or {}
		so_lo = kq.get("batch_no")
		if so_lo:
			dong = [d for d in doc.items if (d.batch_no or None) == so_lo]
			if dong:
				return {"loai": "lo", "so_lo": so_lo, "dong_hang": dong[0].name, "vat_tu": dong[0].item_code}
			vat_tu = frappe.db.get_value("Batch", so_lo, "item")
			cung_hang = [d for d in doc.items if d.item_code == vat_tu]
			if cung_hang:
				hsd_moi = frappe.db.get_value("Batch", so_lo, "expiry_date")
				hsd_cu = frappe.db.get_value("Batch", cung_hang[0].batch_no, "expiry_date")
				return {
					"loai": "lo_khac",
					"so_lo": so_lo,
					"dong_hang": cung_hang[0].name,
					"vat_tu": vat_tu,
					"hsd": hsd_moi,
					"hsd_dang_chot": hsd_cu,
					"so_lo_dang_chot": cung_hang[0].batch_no,
					"han_xa_hon": bool(hsd_moi and hsd_cu and hsd_moi > hsd_cu),
				}
			return {"loai": None}

		ma_o = _tim_o(ma)
		if ma_o:
			o = frappe.db.get_value(
				"Storage Location", ma_o, ["name", "ma_in_nhan", "kho", "is_group"], as_dict=True
			)
			return {
				"loai": "o",
				"ma_o": o.name,
				"ma_in_nhan": o.ma_in_nhan,
				"kho": o.kho,
				"la_nhom": bool(o.is_group),
			}
	except Exception:
		frappe.log_error(title=cat_tieu_de(f"vi_tri_kho: quet_de_lay loi ({ma})"))
	return {"loai": None}
```

Thêm import ở đầu file:

```python
from erpnext.vi_tri_kho.vitri.fefo import chon_o_xuat
from erpnext.vi_tri_kho.vitri.nhat_ky_loi import cat_tieu_de
```

- [ ] **Step 4: Chạy lại bài của task**

Chạy: `bench --site erptest.local run-tests --module erpnext.vi_tri_kho.tests.test_lay_hang`
Chờ: `OK` (17 bài).

- [ ] **Step 5: Commit**

```bash
git add erpnext/vi_tri_kho/vitri/lay_hang.py erpnext/vi_tri_kho/tests/test_lay_hang.py
git commit -m "feat(vi_tri_kho): API đọc cho trang lấy hàng (danh sách, mở phiếu, quét)"
```

---

### Task 5: Máy chủ cho trang PDA — phần GHI

**Files:**
- Modify: `erpnext/vi_tri_kho/vitri/lay_hang.py`
- Modify: `erpnext/vi_tri_kho/tests/test_lay_hang.py` (thêm lớp `TestGhiChoTrang`)

**Interfaces:**
- Consumes: mọi thứ của Task 4.
- Produces:
  - `ghi_da_lay(phieu, dong_hang, so_lo, o, so_luong) -> dict` (trả `mo_phieu_giao`)
  - `bo_dong_da_lay(phieu, ten_dong) -> dict`
  - `doi_lo(phieu, dong_hang, so_lo_moi) -> dict`
  - `chot_thieu(phieu, dong_hang) -> dict`
  - `hoan_tat(phieu) -> dict` — `{"name", "so_dong", "lay_thieu": [...]}`

- [ ] **Step 1: Viết bài test đỏ**

Thêm vào `erpnext/vi_tri_kho/tests/test_lay_hang.py`:

```python
class TestGhiChoTrang(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.savepoint(DIEM_TEST)
		_vat_tu()
		_lo()
		_o(O_GAN)
		_o(O_XA)
		_nhap_kho(30)
		_chuyen_vao_o([(O_GAN, 20), (O_XA, 10)])
		self.dn = _phieu_giao(12)
		self.dong = self.dn.items[0].name

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point=DIEM_TEST)

	def test_ghi_da_lay_luu_ngay_len_phieu(self):
		from erpnext.vi_tri_kho.vitri.lay_hang import ghi_da_lay

		p = ghi_da_lay(self.dn.name, self.dong, LO, O_GAN, 5)
		self.assertEqual(p["dong"][0]["da_lay"], 5.0)
		doc = frappe.get_doc("Delivery Note", self.dn.name)
		self.assertEqual(len(doc.custom_phan_bo_vi_tri), 1)
		self.assertEqual(doc.custom_phan_bo_vi_tri[0].nguoi_lay, frappe.session.user)

	def test_quet_lai_cung_o_thi_cong_don(self):
		from erpnext.vi_tri_kho.vitri.lay_hang import ghi_da_lay

		ghi_da_lay(self.dn.name, self.dong, LO, O_GAN, 5)
		p = ghi_da_lay(self.dn.name, self.dong, LO, O_GAN, 3)
		self.assertEqual(len(p["dong"][0]["da_lay_o"]), 1)
		self.assertEqual(p["dong"][0]["da_lay"], 8.0)

	def test_bo_dong_da_lay(self):
		from erpnext.vi_tri_kho.vitri.lay_hang import bo_dong_da_lay, ghi_da_lay

		p = ghi_da_lay(self.dn.name, self.dong, LO, O_GAN, 5)
		ten = p["dong"][0]["da_lay_o"][0]["name"]
		p2 = bo_dong_da_lay(self.dn.name, ten)
		self.assertEqual(p2["dong"][0]["da_lay"], 0.0)

	def test_doi_lo_sua_dong_phieu_giao(self):
		from erpnext.vi_tri_kho.vitri.lay_hang import doi_lo

		lo2 = "9L-LO-LAY-03"
		if not frappe.db.exists("Batch", lo2):
			frappe.get_doc(
				{"doctype": "Batch", "batch_id": lo2, "item": ITEM, "expiry_date": "2028-01-31"}
			).insert(ignore_permissions=True)
		doi_lo(self.dn.name, self.dong, lo2)
		self.assertEqual(frappe.db.get_value("Delivery Note Item", self.dong, "batch_no"), lo2)

	def test_hoan_tat_duyet_phieu_va_tru_dung_o(self):
		from erpnext.vi_tri_kho.vitri.lay_hang import ghi_da_lay, hoan_tat

		ghi_da_lay(self.dn.name, self.dong, LO, O_XA, 10)
		ghi_da_lay(self.dn.name, self.dong, LO, O_GAN, 2)
		kq = hoan_tat(self.dn.name)

		self.assertEqual(kq["name"], self.dn.name)
		self.assertEqual(frappe.db.get_value("Delivery Note", self.dn.name, "docstatus"), 1)
		self.assertEqual(so.ton_o(O_XA, ITEM, LO), 0.0)
		self.assertEqual(so.ton_o(O_GAN, ITEM, LO), 18.0)

	def test_chot_thieu_ha_so_luong_dong_va_ghi_chu(self):
		from erpnext.vi_tri_kho.vitri.lay_hang import chot_thieu, ghi_da_lay, hoan_tat

		ghi_da_lay(self.dn.name, self.dong, LO, O_GAN, 7)
		chot_thieu(self.dn.name, self.dong)
		hoan_tat(self.dn.name)

		doc = frappe.get_doc("Delivery Note", self.dn.name)
		self.assertEqual(flt(doc.items[0].qty), 7.0)
		self.assertIn("Lấy thiếu", doc.remarks or "")
		self.assertEqual(so.ton_o(O_GAN, ITEM, LO), 13.0)

	def test_hoan_tat_khi_chua_lay_du_bi_chan(self):
		from erpnext.vi_tri_kho.vitri.lay_hang import ghi_da_lay, hoan_tat

		ghi_da_lay(self.dn.name, self.dong, LO, O_GAN, 5)
		with self.assertRaisesRegex(frappe.ValidationError, "chưa lấy đủ"):
			hoan_tat(self.dn.name)
		self.assertEqual(frappe.db.get_value("Delivery Note", self.dn.name, "docstatus"), 0)

	def test_duyet_hong_thi_phieu_con_nhap(self):
		"""Ai đó chuyển hàng khỏi ô sau khi đã quét — duyệt phải hỏng mà không mất phân bổ."""
		from erpnext.vi_tri_kho.vitri.lay_hang import ghi_da_lay, hoan_tat

		ghi_da_lay(self.dn.name, self.dong, LO, O_GAN, 12)
		_chuyen_vao_o_khac = frappe.get_doc(
			{
				"doctype": "Location Transfer",
				"kho": KHO,
				"ngay": nowdate(),
				"items": [
					{"vat_tu": ITEM, "so_lo": LO, "tu_o": O_GAN, "den_o": O_XA, "so_luong": 20}
				],
			}
		)
		_chuyen_vao_o_khac.insert(ignore_permissions=True)
		_chuyen_vao_o_khac.submit()

		with self.assertRaises(frappe.ValidationError):
			hoan_tat(self.dn.name)
		doc = frappe.get_doc("Delivery Note", self.dn.name)
		self.assertEqual(doc.docstatus, 0)
		self.assertEqual(len(doc.custom_phan_bo_vi_tri), 1)
```

- [ ] **Step 2: Chạy để thấy đỏ**

Chạy: `bench --site erptest.local run-tests --module erpnext.vi_tri_kho.tests.test_lay_hang`
Chờ: FAILED — `ImportError: cannot import name 'ghi_da_lay'`.

- [ ] **Step 3: Viết phần ghi**

Thêm vào `erpnext/vi_tri_kho/vitri/lay_hang.py`:

```python
def _dong_cua(doc, dong_hang):
	d = next((x for x in doc.items if x.name == dong_hang), None)
	if not d:
		frappe.throw(_("Dòng hàng {0} không thuộc phiếu {1}.").format(dong_hang, doc.name))
	return d


@frappe.whitelist()
def ghi_da_lay(phieu: str, dong_hang: str, so_lo: str | None, o: str, so_luong) -> dict:
	"""Ghi một lần quét (lô, ô, số lượng) vào bảng phân bổ và LƯU NGAY.

	Lưu ngay chứ không gom trong trình duyệt: PDA hết pin giữa ca là mất cả chục
	lượt quét mà thủ kho đã đi lấy thật ngoài kệ — cùng lẽ với trang xếp hàng.

	Cùng (dòng hàng, lô, ô) thì CỘNG DỒN vào dòng phân bổ sẵn có, không đẻ dòng mới.
	"""
	_kiem_tra_quyen()
	so_lo = so_lo or None
	so_luong = flt(so_luong)
	if so_luong <= 0:
		frappe.throw(_("Số lượng lấy phải lớn hơn 0."))

	doc = frappe.get_doc("Delivery Note", phieu)
	d = _dong_cua(doc, dong_hang)
	if (d.batch_no or None) != so_lo:
		frappe.throw(
			_("Dòng hàng đang chốt lô {0}, không phải {1}. Đổi lô trước khi ghi.").format(
				d.batch_no or "—", so_lo or "—"
			)
		)

	trung = next(
		(
			p
			for p in doc.get(TEN_BANG_PHAN_BO) or []
			if p.dong_hang == dong_hang and (p.so_lo or None) == so_lo and p.o == o
		),
		None,
	)
	if trung:
		trung.so_luong = flt(trung.so_luong) + so_luong
		trung.nguoi_lay = frappe.session.user
		trung.luc_lay = now()
	else:
		doc.append(
			TEN_BANG_PHAN_BO,
			{
				"dong_hang": dong_hang,
				"vat_tu": d.item_code,
				"so_lo": so_lo,
				"o": o,
				"so_luong": so_luong,
				"nguoi_lay": frappe.session.user,
				"luc_lay": now(),
			},
		)
	doc.save()
	return mo_phieu_giao(phieu)


@frappe.whitelist()
def bo_dong_da_lay(phieu: str, ten_dong: str) -> dict:
	"""Quét nhầm thì gỡ đúng dòng phân bổ đó."""
	_kiem_tra_quyen()
	doc = frappe.get_doc("Delivery Note", phieu)
	doc.set(TEN_BANG_PHAN_BO, [p for p in doc.get(TEN_BANG_PHAN_BO) or [] if p.name != ten_dong])
	doc.save()
	return mo_phieu_giao(phieu)


@frappe.whitelist()
def doi_lo(phieu: str, dong_hang: str, so_lo_moi: str) -> dict:
	"""Đổi lô của một dòng phiếu giao sang lô thủ kho thật sự cầm trên tay.

	Chỉ cho đổi khi dòng CHƯA có phân bổ nào: đã quét lấy ở ô nào đó rồi mà đổi lô
	là để lại một phân bổ trỏ vào lô cũ — sổ vị trí sẽ trừ nhầm lô.
	"""
	_kiem_tra_quyen()
	doc = frappe.get_doc("Delivery Note", phieu)
	d = _dong_cua(doc, dong_hang)
	da_lay = [p for p in doc.get(TEN_BANG_PHAN_BO) or [] if p.dong_hang == dong_hang]
	if da_lay:
		frappe.throw(
			_("Dòng này đã ghi {0} lượt lấy cho lô {1}. Bỏ các lượt đó trước khi đổi lô.").format(
				len(da_lay), d.batch_no
			)
		)
	chu = frappe.db.get_value("Batch", so_lo_moi, "item")
	if chu != d.item_code:
		frappe.throw(_("Lô {0} là lô của mặt hàng {1}, không phải {2}.").format(so_lo_moi, chu, d.item_code))
	d.batch_no = so_lo_moi
	doc.save()
	return mo_phieu_giao(phieu)


@frappe.whitelist()
def chot_thieu(phieu: str, dong_hang: str) -> dict:
	"""Đánh dấu dòng này lấy được bao nhiêu thì tính bấy nhiêu.

	KHÔNG sửa số lượng ngay ở đây — `hoan_tat` mới sửa, vì thủ kho còn có thể
	quét thêm ở ô khác sau khi đã chốt thiếu.

	Cờ nằm ở `frappe.cache()` (Redis), KHÔNG phải trên chứng từ: nó là ý định của
	một lượt làm việc, không phải dữ liệu kế toán. Redis bị xoá thì cờ mất và
	`hoan_tat` báo "chưa lấy đủ" — hỏng về phía AN TOÀN (bắt quét/chốt lại), không
	bao giờ tự hạ số lượng phiếu giao vì một cờ rác.
	"""
	_kiem_tra_quyen()
	doc = frappe.get_doc("Delivery Note", phieu)
	_dong_cua(doc, dong_hang)
	danh_dau = set(frappe.cache().get_value(_KHOA_CHOT_THIEU(phieu)) or [])
	danh_dau.add(dong_hang)
	frappe.cache().set_value(_KHOA_CHOT_THIEU(phieu), list(danh_dau), expires_in_sec=86400)
	return mo_phieu_giao(phieu)


def _KHOA_CHOT_THIEU(phieu: str) -> str:
	return f"vi_tri_kho:lay_hang:chot_thieu:{phieu}"


@frappe.whitelist()
def hoan_tat(phieu: str) -> dict:
	"""Chỉnh số lượng theo số lấy thật (nếu có chốt thiếu) rồi DUYỆT phiếu giao.

	Savepoint riêng quanh `submit()`: `Document.submit` ghi `docstatus = 1` xuống
	CSDL TRƯỚC khi `on_submit` chạy, nên hỏng ở hook mà không ai rollback thì phiếu
	mang docstatus 1 không một dòng sổ nào (cùng bẫy đã vá ở `xep.duyet_phieu_xep`).
	"""
	_kiem_tra_quyen()
	doc = frappe.get_doc("Delivery Note", phieu)
	da = _da_lay_theo_dong(doc)
	thieu = set(frappe.cache().get_value(_KHOA_CHOT_THIEU(phieu)) or [])
	lay_thieu = []

	for d in doc.items:
		lay = flt(da.get(d.name, 0.0))
		if abs(lay - flt(d.qty)) <= _SAI_SO:
			continue
		if d.name not in thieu:
			frappe.throw(
				_(
					"Dòng {0} chưa lấy đủ: cần {1}, đã lấy {2}. Quét tiếp, hoặc bấm 'Chốt thiếu' "
					"cho dòng đó."
				).format(d.item_code, flt(d.qty, 3), flt(lay, 3))
			)
		if lay <= 0:
			frappe.throw(
				_("Dòng {0} chưa lấy được gì — bỏ dòng khỏi phiếu giao thay vì chốt thiếu 0.").format(
					d.item_code
				)
			)
		lay_thieu.append({"vat_tu": d.item_code, "so_lo": d.batch_no, "thieu": flt(d.qty) - lay})
		d.qty = lay

	if lay_thieu:
		ghi_chu = "; ".join(
			_("Lấy thiếu {0} {1}{2} — ô trống sớm hơn sổ, cần kiểm kê.").format(
				flt(x["thieu"], 3), x["vat_tu"], f" lô {x['so_lo']}" if x["so_lo"] else ""
			)
			for x in lay_thieu
		)
		doc.remarks = f"{doc.remarks}\n{ghi_chu}" if doc.remarks else ghi_chu
		doc.save()

	diem = "vi_tri_kho_hoan_tat_lay_hang"
	frappe.db.savepoint(diem)
	try:
		doc.submit()
	except Exception:
		frappe.db.rollback(save_point=diem)
		raise
	frappe.cache().delete_value(_KHOA_CHOT_THIEU(phieu))
	return {"name": doc.name, "so_dong": len(doc.items), "lay_thieu": lay_thieu}
```

Thêm import `now`:

```python
from frappe.utils import flt, now
```

- [ ] **Step 4: Chạy lại bài của task**

Chạy: `bench --site erptest.local run-tests --module erpnext.vi_tri_kho.tests.test_lay_hang`
Chờ: `OK` (25 bài).

- [ ] **Step 5: Đột biến — chứng minh savepoint chịu lực**

Tạm bỏ dòng `frappe.db.rollback(save_point=diem)` trong `hoan_tat`, chạy
`bench --site erptest.local run-tests --module erpnext.vi_tri_kho.tests.test_lay_hang --test test_duyet_hong_thi_phieu_con_nhap`
Chờ: FAILED. Khôi phục lại dòng đó rồi chạy lại: `OK`.

- [ ] **Step 6: Commit**

```bash
git add erpnext/vi_tri_kho/vitri/lay_hang.py erpnext/vi_tri_kho/tests/test_lay_hang.py
git commit -m "feat(vi_tri_kho): API ghi cho trang lấy hàng (quét, đổi lô, chốt thiếu, hoàn tất)"
```

---

### Task 6: Tách dòng phiếu giao khi một dòng lấy từ hai lô

**Files:**
- Modify: `erpnext/vi_tri_kho/vitri/lay_hang.py`
- Modify: `erpnext/vi_tri_kho/tests/test_lay_hang.py` (thêm vào lớp `TestGhiChoTrang`)

**Interfaces:**
- Consumes: `ghi_da_lay`, `doi_lo`, `mo_phieu_giao` (Task 4, 5).
- Produces: `tach_dong_theo_lo(phieu: str, dong_hang: str, so_lo_moi: str) -> dict` — giữ dòng cũ với ĐÚNG số đã lấy của lô cũ, đẻ một dòng mới mang phần còn lại và lô mới; trả `mo_phieu_giao`.

**Vì sao cần:** `Stock Settings.use_serial_batch_fields = 1` trên site này (đo 18/09/2026) nên **một dòng phiếu giao chỉ mang một lô**. Lô đầu hết giữa chừng mà đơn vẫn còn thiếu thì không có chỗ nào ghi lô thứ hai — đây là chỗ spec §8 đánh dấu "dễ sai nhất".

- [ ] **Step 1: Viết bài test đỏ**

Thêm vào lớp `TestGhiChoTrang` trong `erpnext/vi_tri_kho/tests/test_lay_hang.py`:

```python
	def test_tach_dong_khi_lay_tu_hai_lo(self):
		"""Lô cũ chỉ còn 8/12 → tách: dòng cũ 8 lô cũ, dòng mới 4 lô mới."""
		from erpnext.vi_tri_kho.vitri.lay_hang import ghi_da_lay, hoan_tat, tach_dong_theo_lo

		lo2 = "9L-LO-LAY-04"
		if not frappe.db.exists("Batch", lo2):
			frappe.get_doc(
				{"doctype": "Batch", "batch_id": lo2, "item": ITEM, "expiry_date": "2027-07-31"}
			).insert(ignore_permissions=True)
		_nhap_kho_lo(lo2, 10)
		_chuyen_vao_o_lo(lo2, [(O_XA, 10)])

		ghi_da_lay(self.dn.name, self.dong, LO, O_GAN, 8)
		p = tach_dong_theo_lo(self.dn.name, self.dong, lo2)

		self.assertEqual(len(p["dong"]), 2)
		cu = next(d for d in p["dong"] if d["dong_hang"] == self.dong)
		moi = next(d for d in p["dong"] if d["dong_hang"] != self.dong)
		self.assertEqual((cu["so_lo"], cu["can_lay"], cu["da_lay"]), (LO, 8.0, 8.0))
		self.assertEqual((moi["so_lo"], moi["can_lay"], moi["da_lay"]), (lo2, 4.0, 0.0))

		ghi_da_lay(self.dn.name, moi["dong_hang"], lo2, O_XA, 4)
		hoan_tat(self.dn.name)

		self.assertEqual(so.ton_o(O_GAN, ITEM, LO), 12.0)
		self.assertEqual(so.ton_o(O_XA, ITEM, lo2), 6.0)

	def test_tach_dong_khi_chua_lay_gi_thi_bi_chan(self):
		"""Chưa lấy được gì của lô cũ thì đó là ĐỔI LÔ, không phải tách."""
		from erpnext.vi_tri_kho.vitri.lay_hang import tach_dong_theo_lo

		with self.assertRaisesRegex(frappe.ValidationError, "chưa lấy được gì"):
			tach_dong_theo_lo(self.dn.name, self.dong, LO)
```

Thêm hai hàm phụ ở đầu file test (cạnh `_nhap_kho` / `_chuyen_vao_o`), vì hai hàm cũ khoá cứng vào `LO`:

```python
def _nhap_kho_lo(so_lo, so_luong):
	se = frappe.get_doc(
		{
			"doctype": "Stock Entry",
			"stock_entry_type": "Material Receipt",
			"company": CTY,
			"items": [
				{
					"item_code": ITEM,
					"qty": so_luong,
					"t_warehouse": KHO,
					"basic_rate": 1000,
					"batch_no": so_lo,
					"use_serial_batch_fields": 1,
				}
			],
		}
	)
	se.insert(ignore_permissions=True)
	se.submit()
	return se


def _chuyen_vao_o_lo(so_lo, cap):
	chua_xep = frappe.db.get_value("Storage Location", {"kho": KHO, "la_o_chua_xep": 1})
	pxep = frappe.get_doc(
		{
			"doctype": "Location Transfer",
			"kho": KHO,
			"ngay": nowdate(),
			"items": [
				{"vat_tu": ITEM, "so_lo": so_lo, "tu_o": chua_xep, "den_o": o, "so_luong": sl}
				for o, sl in cap
			],
		}
	)
	pxep.insert(ignore_permissions=True)
	pxep.submit()
	return pxep
```

- [ ] **Step 2: Chạy để thấy đỏ**

Chạy: `bench --site erptest.local run-tests --module erpnext.vi_tri_kho.tests.test_lay_hang`
Chờ: FAILED — `ImportError: cannot import name 'tach_dong_theo_lo'`.

- [ ] **Step 3: Viết hàm tách dòng**

Thêm vào `erpnext/vi_tri_kho/vitri/lay_hang.py`:

```python
@frappe.whitelist()
def tach_dong_theo_lo(phieu: str, dong_hang: str, so_lo_moi: str) -> dict:
	"""Lô cũ hết giữa chừng: chốt dòng cũ ở số ĐÃ LẤY, đẻ dòng mới cho phần còn lại.

	`Stock Settings.use_serial_batch_fields = 1` trên site này nên MỘT DÒNG phiếu
	giao chỉ mang MỘT lô (đo 18/09/2026) — không tách thì không có chỗ nào ghi lô
	thứ hai, và duyệt sẽ nổ "Batch No … has negative stock".

	Chỉ tách khi dòng cũ ĐÃ lấy được một phần: chưa lấy gì thì đó là ĐỔI LÔ
	(`doi_lo`), và tách ra một dòng 0 là để lại rác trên chứng từ bán hàng.
	"""
	_kiem_tra_quyen()
	doc = frappe.get_doc("Delivery Note", phieu)
	d = _dong_cua(doc, dong_hang)
	da = _da_lay_theo_dong(doc).get(dong_hang, 0.0)
	con_lai = flt(d.qty) - flt(da)

	if flt(da) <= _SAI_SO:
		frappe.throw(
			_("Dòng {0} chưa lấy được gì của lô {1} — dùng 'Đổi lô' thay vì tách dòng.").format(
				d.item_code, d.batch_no or "—"
			)
		)
	if con_lai <= _SAI_SO:
		frappe.throw(_("Dòng {0} đã lấy đủ, không còn gì để tách.").format(d.item_code))

	chu = frappe.db.get_value("Batch", so_lo_moi, "item")
	if chu != d.item_code:
		frappe.throw(
			_("Lô {0} là lô của mặt hàng {1}, không phải {2}.").format(so_lo_moi, chu, d.item_code)
		)

	moi = {
		k: v
		for k, v in d.as_dict().items()
		if k
		not in (
			"name",
			"idx",
			"creation",
			"modified",
			"owner",
			"modified_by",
			"parent",
			"parentfield",
			"parenttype",
			"doctype",
			"serial_and_batch_bundle",
		)
	}
	moi["qty"] = con_lai
	moi["batch_no"] = so_lo_moi
	d.qty = flt(da)
	doc.append("items", moi)
	doc.save()
	return mo_phieu_giao(phieu)
```

- [ ] **Step 4: Chạy lại bài của task**

Chạy: `bench --site erptest.local run-tests --module erpnext.vi_tri_kho.tests.test_lay_hang`
Chờ: `OK` (27 bài).

- [ ] **Step 5: Commit**

```bash
git add erpnext/vi_tri_kho/vitri/lay_hang.py erpnext/vi_tri_kho/tests/test_lay_hang.py
git commit -m "feat(vi_tri_kho): tách dòng phiếu giao khi một dòng lấy từ hai lô"
```

---

### Task 7: Trang PDA `lay-hang-pda`

**Files:**
- Create: `erpnext/vi_tri_kho/page/lay_hang_pda/__init__.py`
- Create: `erpnext/vi_tri_kho/page/lay_hang_pda/lay_hang_pda.json`
- Create: `erpnext/vi_tri_kho/page/lay_hang_pda/lay_hang_pda.js`
- Create: `erpnext/vi_tri_kho/page/lay_hang_pda/lay_hang_pda.css`
- Modify: `erpnext/vi_tri_kho/workspace/vị_trí_kho/vị_trí_kho.json`
- Modify: `erpnext/vi_tri_kho/tests/test_giao_dien.py`

**Interfaces:**
- Consumes: mọi hàm `@frappe.whitelist()` của Task 4, 5 và 6; `erpnext.vi_tri_kho.OQuet` từ `/assets/erpnext/js/vi_tri_kho/o_quet.js`.
- Produces: Page `lay-hang-pda` (vai trò `System Manager`, `Stock Manager`, `Stock User`).

- [ ] **Step 1: Viết bài test đỏ**

Trong `erpnext/vi_tri_kho/tests/test_giao_dien.py`, thêm ở cuối file (lớp cha `TestTrangQuetMa` đã được tham số hoá sẵn cho việc này):

```python
class TestTrangLayHang(TestTrangQuetMa):
	"""Trang lấy hàng trên PDA (spec 2026-09-18). Cùng bốn kiểu hỏng im lặng với
	hai trang PDA trước: thiếu roles thì Stock User mở ra "Not permitted"; thiếu
	khối trong `content` thì workspace không vẽ ô bấm."""

	TRANG = "lay-hang-pda"
	THU_MUC = "lay_hang_pda"

	def _vai_tro_may_chu(self):
		from erpnext.vi_tri_kho.vitri.lay_hang import VAI_TRO_DUOC_LAY

		return VAI_TRO_DUOC_LAY
```

- [ ] **Step 2: Chạy để thấy đỏ**

Chạy: `bench --site erptest.local run-tests --module erpnext.vi_tri_kho.tests.test_giao_dien`
Chờ: FAILED — `Page lay-hang-pda` chưa có.

- [ ] **Step 3: Tạo Page**

`erpnext/vi_tri_kho/page/lay_hang_pda/__init__.py`: rỗng.

`erpnext/vi_tri_kho/page/lay_hang_pda/lay_hang_pda.json`:

```json
{
 "content": null,
 "creation": "2026-09-18 00:00:00",
 "docstatus": 0,
 "doctype": "Page",
 "icon": "assets",
 "idx": 0,
 "modified": "2026-09-18 00:00:00",
 "modified_by": "Administrator",
 "module": "Vi Tri Kho",
 "name": "lay-hang-pda",
 "owner": "Administrator",
 "page_name": "lay-hang-pda",
 "roles": [
  {"role": "System Manager"},
  {"role": "Stock Manager"},
  {"role": "Stock User"}
 ],
 "script": null,
 "standard": "Yes",
 "style": null,
 "system_page": 0,
 "title": "Lấy hàng"
}
```

- [ ] **Step 4: Viết `lay_hang_pda.js`**

Khuôn lấy nguyên từ `xep_hang_pda.js` (IIFE, `OQuet`, hộp hỏi chỉ nhận chạm tay). Hai màn:

```javascript
// Trang "Lấy hàng" — PDA của thủ kho.
//
// Chủ đầu tư 18/09/2026 chọn bản đầy đủ: quét tem lô + tem ô để XÁC NHẬN đã lấy,
// và sổ vị trí trừ ĐÚNG ô đã quét (qua bảng phân bổ `Location Allocation`), thay
// vì ô do FEFO tự chọn lúc duyệt phiếu giao.
//
// Máy chủ: `vitri/lay_hang.py`. Trang KHÔNG tự kiểm ô/lô — gửi lên và để câu báo
// của máy chủ hiện ra, một chỗ duy nhất giữ luật.
//
// Bọc IIFE và KHÔNG dùng `frappe.confirm` — xem `xep_hang_pda.js` để biết vì sao.
(function () {
	const O_QUET = ["/assets/erpnext/js/vi_tri_kho/o_quet.js", "/assets/erpnext/js/vi_tri_kho/o_quet.css"];
	const API = "erpnext.vi_tri_kho.vitri.lay_hang.";

	frappe.pages["lay-hang-pda"].on_page_load = function (wrapper) {
		const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Lấy hàng"), single_column: true });
		frappe.require(O_QUET, () => {
			wrapper.lay_hang = new LayHangPda(page);
		});
	};

	frappe.pages["lay-hang-pda"].on_page_show = function (wrapper) {
		if (wrapper.lay_hang) wrapper.lay_hang.nap_lai();
	};

	class LayHangPda {
		constructor(page) {
			this.page = page;
			this.kho = null;
			this.phieu = null; // kết quả mo_phieu_giao
			this.cho = null; // lô đang chờ quét ô: {dong_hang, so_lo, so_luong, o_khac}
			this.dung();
			this.nap_lai();
		}
		// ... (các phương thức bên dưới)
	}
})();
```

Các phương thức của lớp `LayHangPda` — viết đúng như dưới đây, phần vẽ (`ve_*`) theo
khuôn `XepHangPda` (cùng lớp CSS, đổi tiền tố `.xh-` → `.lh-`):

```javascript
		dung() {
			this.$goc = $(`
				<div class="lh">
					<div class="lh-dau-trang"></div>
					<div class="lh-cho-o-quet"></div>
					<div class="lh-thong-bao"></div>
					<div class="lh-than"></div>
					<div class="lh-chan-trang"></div>
				</div>
			`).appendTo(this.page.main);

			this.o_quet = new erpnext.vi_tri_kho.OQuet({
				cha: this.$goc.find(".lh-cho-o-quet"),
				vung: this.$goc,
				placeholder: __("Quét tem…"),
				goi_y: "",
				khi_quet: (ma) => this.quet(ma),
			});

			this.$goc.on("click", ".lh-mo-phieu", (ev) => this.mo_phieu($(ev.currentTarget).attr("data-phieu")));
			this.$goc.on("click", ".lh-ve-danh-sach", () => { this.phieu = null; this.cho = null; this.nap_lai(); });
			this.$goc.on("click", ".lh-bo-luot", (ev) => this.bo_luot($(ev.currentTarget).attr("data-luot")));
			this.$goc.on("click", ".lh-chot-thieu", (ev) => this.chot_thieu($(ev.currentTarget).attr("data-dong")));
			this.$goc.on("click", ".lh-hoan-tat", () => this.hoan_tat());
			this.$goc.on("click", ".lh-xac-nhan-lo-khac", () => this.nhan_lo_khac());
		}

		nap_lai() {
			const goi = this.phieu
				? frappe.xcall(API + "mo_phieu_giao", { phieu: this.phieu.name }).then((p) => { this.phieu = p; })
				: frappe.xcall(API + "danh_sach_phieu_giao", { kho: this.kho }).then((ds) => { this.ds = ds; });
			return goi.then(() => { this.ve(); this.o_quet.giu_focus(); });
		}

		mo_phieu(ten) {
			this.cho = null;
			frappe.xcall(API + "mo_phieu_giao", { phieu: ten }).then((p) => {
				this.phieu = p;
				this.bao();
				this.ve();
				this.o_quet.giu_focus();
			});
		}

		quet(ma) {
			if (!this.phieu) {
				this.bao(__("Chọn phiếu giao trước khi quét."), "cam");
				return;
			}
			frappe.xcall(API + "quet_de_lay", { phieu: this.phieu.name, ma: ma }).then((d) => {
				d = d || { loai: null };
				if (d.loai === "lo") return this.nhan_lo(d);
				if (d.loai === "lo_khac") return this.hoi_doi_lo(d);
				if (d.loai === "o") return this.nhan_o(d);
				rung([80, 60, 80]);
				this.bao(__("Không nhận ra mã <b>{0}</b>, hoặc lô này không nằm trong phiếu.", [e(ma)]), "xam");
			});
		}

		nhan_lo(d) {
			const dong = this.phieu.dong.find((x) => x.dong_hang === d.dong_hang);
			const con_can = flt(dong.can_lay) - flt(dong.da_lay);
			if (con_can <= 0) {
				this.bao(__("Dòng này đã lấy đủ."), "xam");
				return;
			}
			rung([40]);
			this.cho = { dong_hang: d.dong_hang, so_lo: d.so_lo, so_luong: con_can, lo_khac: null };
			this.bao();
			this.ve();
		}

		hoi_doi_lo(d) {
			// Quét lại đúng tem đó để xác nhận — KHÔNG hộp thoại (Enter của súng quét).
			if (this.cho && this.cho.lo_khac && this.cho.lo_khac.so_lo === d.so_lo) return this.nhan_lo_khac();
			rung([80]);
			this.cho = { dong_hang: d.dong_hang, so_lo: null, so_luong: 0, lo_khac: d };
			this.ve();
		}

		nhan_lo_khac() {
			const lk = this.cho && this.cho.lo_khac;
			if (!lk) return;
			const dong = this.phieu.dong.find((x) => x.dong_hang === lk.dong_hang);
			// Đã lấy được một phần của lô cũ → TÁCH dòng; chưa lấy gì → ĐỔI lô.
			const ham = flt(dong.da_lay) > 0 ? "tach_dong_theo_lo" : "doi_lo";
			frappe
				.xcall(API + ham, { phieu: this.phieu.name, dong_hang: lk.dong_hang, so_lo_moi: lk.so_lo })
				.then((p) => {
					this.phieu = p;
					this.cho = null;
					this.bao(__("Đã chuyển sang lô <b>{0}</b>. Quét lại tem lô để lấy.", [e(lk.so_lo)]), "xanh");
					this.ve();
				})
				.finally(() => this.o_quet.giu_focus());
		}

		nhan_o(o) {
			if (!this.cho || !this.cho.so_lo) {
				rung([80, 60, 80]);
				this.bao(__("Quét tem LÔ trước, rồi mới quét tem ô."), "cam");
				return;
			}
			const c = this.cho;
			frappe
				.xcall(API + "ghi_da_lay", {
					phieu: this.phieu.name,
					dong_hang: c.dong_hang,
					so_lo: c.so_lo,
					o: o.ma_o,
					so_luong: c.so_luong,
				})
				.then((p) => {
					rung([40, 40, 40]);
					this.phieu = p;
					this.cho = null;
					this.bao(__("Đã lấy <b>{0}</b> {1} ở <b>{2}</b>", [so(c.so_luong), e(c.so_lo), e(o.ma_in_nhan || o.ma_o)]), "xanh");
					this.ve();
				})
				.catch(() => rung([80, 60, 80]))
				.finally(() => this.o_quet.giu_focus());
		}

		bo_luot(ten) {
			frappe
				.xcall(API + "bo_dong_da_lay", { phieu: this.phieu.name, ten_dong: ten })
				.then((p) => { this.phieu = p; this.bao(__("Đã bỏ một lượt lấy."), "xam"); this.ve(); })
				.finally(() => this.o_quet.giu_focus());
		}

		chot_thieu(dong_hang) {
			const d = this.phieu.dong.find((x) => x.dong_hang === dong_hang);
			hoi({
				noi_dung: __("Chốt <b>{0}</b> chỉ lấy được <b>{1}</b>/{2}? Phiếu giao sẽ hạ số lượng xuống.", [
					e(d.ten_hang), so(d.da_lay), so(d.can_lay),
				]),
				nhan: __("Chốt thiếu"),
				khi_dong_y: () =>
					frappe
						.xcall(API + "chot_thieu", { phieu: this.phieu.name, dong_hang: dong_hang })
						.then((p) => { this.phieu = p; this.ve(); })
						.finally(() => this.o_quet.giu_focus()),
				khi_dong: () => this.o_quet.giu_focus(),
			});
		}

		hoan_tat() {
			const ten = this.phieu.name;
			hoi({
				noi_dung: __("Duyệt phiếu giao <b>{0}</b>? Kho sẽ trừ đúng các ô vừa quét.", [e(ten)]),
				nhan: __("Duyệt phiếu"),
				khi_dong_y: () =>
					frappe
						.xcall(API + "hoan_tat", { phieu: ten })
						.then((kq) => {
							rung([40, 40, 40]);
							this.phieu = null;
							this.cho = null;
							const thieu = (kq.lay_thieu || []).length
								? " " + __("Có {0} dòng lấy thiếu — xem ghi chú trên phiếu.", [kq.lay_thieu.length])
								: "";
							this.bao(__("Đã duyệt <a href='{0}'>{1}</a>.", [`/app/delivery-note/${encodeURIComponent(ten)}`, e(ten)]) + thieu, "xanh");
							return this.nap_lai();
						})
						.catch(() => { rung([80, 60, 80]); return this.nap_lai(); })
						.finally(() => this.o_quet.giu_focus()),
				khi_dong: () => this.o_quet.giu_focus(),
			});
		}
```

Phần vẽ: `ve()` gọi `ve_dau_trang()` (kho + tên phiếu + nút "← Danh sách"), rồi **màn danh sách**
(mỗi phiếu một nút `.lh-mo-phieu`: số phiếu, khách hàng, `đã lấy X/Y`, và dòng cam *"{tên} đang
lấy"* nếu `nguoi_dang_lay` không rỗng) **hoặc màn phiếu** (mỗi dòng hàng: tên hàng, lô + HSD,
`da_lay/can_lay`, danh sách `o_nen_lay` — mã in đậm kèm số lượng, các lượt `da_lay_o` kèm nút ✕
`.lh-bo-luot`, nút `.lh-chot-thieu` khi `da_lay > 0 && da_lay < can_lay`), `ve_lo_dang_cho()` (thẻ
cam: lô đang chờ quét ô, ô số lượng sửa được; hoặc khung xác nhận lô khác với nút
`.lh-xac-nhan-lo-khac`), và `ve_chan_trang()` (nút `.lh-hoan-tat` chỉ hiện khi đã lấy được ít
nhất một lượt). Chữ gợi ý ô quét: `① Quét tem LÔ` khi chưa có `this.cho`, `② Quét tem Ô cho lô X`
(kiểu `nhan-manh`) khi có, và `Quét LẠI tem {lô} để đổi lô` khi đang chờ xác nhận lô khác.

Ba hàm tiện ích cuối file (chép nguyên từ `xep_hang_pda.js`): `hoi()` (hộp hỏi **chỉ nhận chạm
tay**, dùng `frappe.ui.Dialog` thường), `so()`, `e()`, `rung()`.

- [ ] **Step 5: Viết `lay_hang_pda.css`**

Chép khuôn `xep_hang_pda.css`, đổi tiền tố `.xh-` → `.lh-`, giữ nguyên: sửa `page-title` cho màn 360px, vùng chạm ≥ 44px, nút `Hoàn tất` dùng `class="btn btn-primary"` (màu tự đúng chế độ tối), phông đều chỉ cho MÃ.

- [ ] **Step 6: Thêm lối vào workspace**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/erpnext
python3 - <<'PY'
import json
p="erpnext/vi_tri_kho/workspace/vị_trí_kho/vị_trí_kho.json"
d=json.load(open(p))
d["shortcuts"].insert(2, {"color":"Pink","doc_view":"","label":"Lấy hàng","link_to":"lay-hang-pda","type":"Page"})
c=json.loads(d["content"])
i=next(k for k,b in enumerate(c) if b.get("id")=="vtk-sc-xep-pda")
c.insert(i+1, {"id":"vtk-sc-lay-pda","type":"shortcut","data":{"shortcut_name":"Lấy hàng","col":3}})
d["content"]=json.dumps(c)
d["links"][0]["link_count"]+=1
d["links"].insert(3, {"hidden":0,"is_query_report":0,"label":"Lấy hàng","link_count":0,
  "link_to":"lay-hang-pda","link_type":"Page","onboard":1,"type":"Link"})
d["modified"]="2026-09-18 23:00:00.000000"
open(p,"w").write(json.dumps(d,indent=1))
PY
truncate -s -1 "erpnext/vi_tri_kho/workspace/vị_trí_kho/vị_trí_kho.json"
```

(JSON phải giữ `ensure_ascii=True` mặc định và **không có newline cuối** — file gốc như vậy, đổi đi thì diff phình ra vô nghĩa.)

- [ ] **Step 7: Migrate và chạy lại bài giao diện**

Chạy: `bench --site erptest.local migrate && bench --site erptest.local run-tests --module erpnext.vi_tri_kho.tests.test_giao_dien`
Chờ: `OK` (31 bài).

- [ ] **Step 8: Commit**

```bash
git add erpnext/vi_tri_kho/page/lay_hang_pda erpnext/vi_tri_kho/workspace erpnext/vi_tri_kho/tests/test_giao_dien.py
git commit -m "feat(vi_tri_kho): trang Lấy hàng cho PDA"
```

---

### Task 8: Kiểm trên trình duyệt thật + tài liệu

**Files:**
- Create: `<scratchpad>/t21/kiem_lay_hang.js` (không vào repo)
- Modify: `docs/vi_tri_kho/HDSD-quan-ly-vi-tri-kho.md` (thêm mục 14)
- Modify: `docs/vi_tri_kho/HDSD-luong-tu-A-den-Z.md` (bước 9)

**Interfaces:**
- Consumes: trang `lay-hang-pda`.
- Produces: —

- [ ] **Step 1: Dựng phiên và Chrome headless**

Theo đúng khuôn đã dùng ở `t18`/`t19`:

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/sites
../env/bin/python - <<'PY'
import frappe, json
from types import SimpleNamespace
frappe.init(site="erptest.local"); frappe.connect()
frappe.local.request_ip="127.0.0.1"
frappe.local.request=SimpleNamespace(cookies={},headers={},path="/")
frappe.local.form_dict=frappe._dict()
from frappe.sessions import Session
s=Session(user="Administrator", resume=False, full_name="Administrator", user_type="System User")
frappe.db.commit()
print(s.sid)
PY
google-chrome --headless=new --remote-debugging-port=9222 --user-data-dir=<scratchpad>/t21/chrome --no-first-run --disable-gpu about:blank &
```

- [ ] **Step 2: Viết kịch bản kiểm**

Chép `t19/kiem_xep.js` làm khuôn (CDP `Input.insertText` từng ký tự + Enter, mô phỏng 360×740 cảm ứng). Các phép phải có:

1. Workspace có ô bấm **Lấy hàng**, bấm vào mở đúng trang.
2. Danh sách hiện phiếu giao nháp vừa dựng, đúng tiến độ `0/N`.
3. Quét tem lô của phiếu → thẻ chờ ô; quét tem ô gợi ý → lượt lấy được ghi, tiến độ tăng.
4. Quét ô **không có lô đó** → câu báo máy chủ, không ghi gì.
5. Tải lại trang → vẫn thấy đúng các lượt đã quét (phân bổ nằm trên phiếu).
6. Quét **lô khác cùng mặt hàng, hạn xa hơn** → khung cam, phải quét lại mới đổi.
7. **Hoàn tất** → hỏi xác nhận; gửi **Enter** khi hộp đang mở → phiếu **vẫn nháp**; bấm nút thật → phiếu `docstatus = 1`.
8. Sổ vị trí trừ **đúng ô đã quét** (`frappe.xcall` đọc `Location Ledger Entry`).
9. Không lỗi JS ngoài `socket.io` (máy dev không chạy socket) và các traceback do bài cố ý gây ra.

Dọn cuối bài: huỷ phiếu giao vừa duyệt và mọi chứng từ dựng cho bài, kiểm `doi_soat_kho` khớp.

- [ ] **Step 3: Chạy và sửa tới khi sạch**

Chạy: `node <scratchpad>/t21/kiem_lay_hang.js`
Chờ: mọi dòng `ĐẠT`. Dừng Chrome bằng `kill <pid cổng 9222>` (không dùng `pkill -f`).

- [ ] **Step 4: Chạy cả bộ `vi_tri_kho`**

Dùng vòng lặp ở Task 2 Step 6. Chờ: 35/35 module xanh (34 cũ + `test_lay_hang`), ≥ 493 bài.

- [ ] **Step 5: Viết tài liệu**

`HDSD-quan-ly-vi-tri-kho.md` — thêm **mục 14 "Lấy hàng (trên PDA)"**: mở từ workspace, chọn phiếu giao, ① quét lô ② quét ô, đổi lô, lấy thiếu, hoàn tất; nói rõ **chưa bấm Hoàn tất thì kho chưa trừ**; và phiếu giao duyệt từ form khi phân bổ dở dang sẽ bị chặn (đường thoát: xoá phân bổ).

`HDSD-luong-tu-A-den-Z.md` — bước 9: **bỏ khung cảnh báo "Chưa có màn hình lấy hàng"**, thay bằng đường mới (quét xác nhận), giữ nguyên phần "một dòng chỉ mang một lô" vì vẫn đúng.

- [ ] **Step 6: Commit**

```bash
git add docs/vi_tri_kho/HDSD-quan-ly-vi-tri-kho.md docs/vi_tri_kho/HDSD-luong-tu-A-den-Z.md
git commit -m "docs(vi_tri_kho): HDSD màn hình lấy hàng PDA"
```

---

## Sau khi xong cả 8 task

Báo cáo lại cho chủ đầu tư: đường mới đã chạy, số bài test, và ba việc vẫn còn treo (không thuộc kế hoạch này):

1. `Stock Settings` → `FIFO` hay `Expiry` khi chọn **lô**.
2. Mở phân bổ cho phiếu nhập (chọn ô ngay lúc nhập, thay cho bước xếp riêng).
3. `Location Count` — kiểm kê theo ô, để đóng vòng "lấy thiếu → kiểm kê → chỉnh sổ".

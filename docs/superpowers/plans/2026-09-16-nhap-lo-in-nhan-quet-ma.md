# Nhập lô · In nhãn lô 50×30 · Quét mã — Kế hoạch thi công

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Thủ kho khai số lô + HSD cho từng dòng phiếu nhập trên một phiếu riêng, hệ tạo
bản ghi `Batch` đầy đủ, in được nhãn 50×30 dán lên hàng, và quét lại nhãn ra toàn bộ
thông tin đã nhập.

**Architecture:** Dùng lại doctype `Batch` của ERPNext (tên bản ghi chính là số lô của
NCC) + 3 custom field. Một doctype submittable mới `Batch Entry` gắn với `Purchase
Receipt` còn nháp: submit thì tạo `Batch` và ghi `batch_no` lên dòng phiếu nhập, để
ERPNext tự dựng `Serial and Batch Bundle` — không đụng nội bộ bundle. Nhãn vẽ bằng JS
theo đúng kỷ luật lưới điểm của `tem_vi_tri.js`, hai bố cục tự chọn theo số module
mã vạch. Quét mã bọc ngoài `scan_barcode` sẵn có, không sửa mã ERPNext gốc.

**Tech Stack:** Frappe v15 · ERPNext (Miyano ERP fork) · MariaDB · JsBarcode qua
`frappe.ui.form.make_control({fieldtype: "Barcode"})` · máy in nhiệt Zebra ZD421 203 dpi.

**Spec:** `docs/superpowers/specs/2026-09-16-nhap-lo-in-nhan-quet-ma-design.md`

## Global Constraints

Mọi task đều chịu các ràng buộc dưới. Đọc hết trước khi làm task đầu tiên.

- **Bench:** chạy mọi lệnh `bench` từ `/home/hoangvietyeuem/frappe-bench-yhct`, site
  `erptest.local`. KHÔNG phải site `miyano` (CLAUDE.md nói `miyano` vì đó là prod; máy
  này là máy chơi).
- **Chạy test:** `bench --site erptest.local run-tests --module erpnext.warehouse_operations.tests.<tên>`,
  **tuần tự, từng module một**. KHÔNG dùng `--app erpnext` (chạy cả ERPNext, mất hàng giờ).
  Trước khi đóng task cuối phải chạy lại **toàn bộ** các module trong `vi_tri_kho/tests/`.
- **Python style:** thụt bằng **TAB**, dài dòng tối đa 110, chuỗi nháy kép. Khớp file
  xung quanh.
- **Chú thích tiếng Việt, giải thích VÌ SAO chứ không phải LÀM GÌ** — đúng giọng các file
  sẵn có trong `erpnext/warehouse_operations/`. Chú thích chép lại tên hàm là chú thích thừa.
- **Bẫy toạ độ rỗng:** không bao giờ viết `lft between %(lft)s and %(rgt)s` mà không chặn
  trước `lft = rgt = 0`. `between 0 and 0` khớp MỌI bản ghi chưa hội tụ toàn hệ. Dự án
  đã trả giá cho bẫy này ba lần.
- **Module mã vạch:** X = **0,25 mm** (2 dot trên đầu in 203 dpi). Không bao giờ thu nhỏ
  hơn để nhét vừa — mã quá nhỏ trên đầu in nhiệt **đọc ra sai ký tự**, không phải đọc hỏng.
- **Tiền tố custom field:** `custom_` (khuôn `patches/v1_0/them_co_quan_ly_vi_tri.py`).
- **TUYỆT ĐỐI KHÔNG sửa:** `erpnext/stock/utils.py` · `erpnext/stock/doctype/batch/batch.py` ·
  `erpnext/controllers/stock_controller.py` · `erpnext/public/js/utils/serial_no_batch_selector.js`.
  Mỗi dòng sửa mã ERPNext gốc là một điểm xung đột mỗi lần merge bản mới, và spec đã chọn
  đường bọc ngoài cho đúng mục đó.
- **Cổng cấu trúc file:** một `PreToolUse` hook chặn file mới đặt sai chỗ và nói đúng chỗ
  phải đặt. Nếu bị chặn, đọc `scripts/file_structure/gate.py` chứ đừng lách.
- **Commit** sau mỗi task, kết thúc thông điệp bằng:
  ```
  Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_015sreA2wVDuoP5Ru9TwKrd5
  ```
- **Nhánh:** `feat/mo-rong-vi-tri-kho-warehouse` (đã có, đang làm dở). Không tạo nhánh mới.
- **ĐÍNH CHÍNH 16/09 (sau khi thi công Task 4):** `goi_y_o` trả **BỘ BA**
  `(ô, lý do, tem_hong)`, không phải bộ đôi. Mọi chỗ trong kế hoạch này viết
  `-> tuple[str | None, str]` đều đã lỗi thời. Lý do: hai câu lý do đều chứa chữ
  "tem" — một nghĩa là tem ĐÚNG, một nghĩa là tem HỎNG — nên bên gọi không phân
  biệt được bằng cách đọc chuỗi; và chuỗi đó đi qua `__()` nên **dịch được**, bản
  tiếng Anh không có chữ "tem" và mọi phép so khớp im lặng khớp 0 dòng. **Chuỗi lý
  do là văn bản cho người đọc, không phải giao thức giữa hai tầng.** Task nào đọc
  kết quả `goi_y_o` thì lấy `[0]`/`[1]`/`[2]`, và dùng `[2]` chứ đừng bao giờ dò
  chữ trong `[1]`.
- **Quy ước `...` trong bài test:** kế hoạch này viết đủ thân cho các bài test của Task 3
  làm BÀI MẪU. Ở các task sau, một số bài chỉ có **tên và docstring**, thân là `...`.
  **Docstring đó là yêu cầu ràng buộc, không phải gợi ý**: nó nói chính xác bài phải
  chứng minh điều gì và vì sao điều đó quan trọng. Người thi công viết thân bài sao cho
  đúng docstring, theo khuôn Task 3. `...` để nguyên là task CHƯA XONG.
  Mỗi bài có chữ "chốt âm" trong docstring phải thoả thêm một điều: **một đột biến bỏ
  hẳn phép kiểm mà bài đang nói tới phải làm bài đó ĐỎ.** Viết xong thì thử bỏ phép kiểm
  ra chạy lại một lần để tự kiểm chứng, rồi khôi phục.

## File Structure

**Tạo mới:**

| File | Trách nhiệm |
|---|---|
| `erpnext/warehouse_operations/patches/v1_0/them_so_goi_va_o_in_tem.py` | 2 custom field trên `Batch` |
| `erpnext/warehouse_operations/patches/v1_0/them_thong_so_tem_cho_item.py` | 1 custom field trên `Item` |
| `erpnext/warehouse_operations/vitri/lo_ncc.py` | Móc `before_insert` điền NCC cho lô sinh từ chứng từ mua |
| `erpnext/warehouse_operations/vitri/ma_vach.py` | Đếm module Code 128 — **một** định nghĩa cho cả `validate` lẫn nhãn |
| `erpnext/warehouse_operations/vitri/nhap_lo.py` | API máy chủ: nạp dòng từ phiếu nhập, dữ liệu vẽ nhãn, đặt ô in tem |
| `erpnext/warehouse_operations/vitri/quet.py` | `tra_cuu(ma)` — bọc ngoài `scan_barcode` |
| `erpnext/warehouse_operations/doctype/batch_entry_item/` | Bảng con |
| `erpnext/warehouse_operations/doctype/batch_entry/` | Phiếu nhập lô (submittable) |
| `erpnext/public/js/warehouse_operations/tem_lo.js` | Vẽ nhãn lô 50×30, hai bố cục |
| `erpnext/public/js/warehouse_operations/batch.js` | Nút "In nhãn" trên form `Batch` |
| `erpnext/warehouse_operations/tests/test_lo_ncc.py` | |
| `erpnext/warehouse_operations/tests/test_ma_vach.py` | |
| `erpnext/warehouse_operations/tests/test_nhap_lo.py` | |
| `erpnext/warehouse_operations/tests/test_quet.py` | |

**Sửa:**

| File | Sửa gì |
|---|---|
| `erpnext/warehouse_operations/vitri/goi_y.py` | `goi_y_o(vat_tu, kho, so_lo=None) -> (ô, lý do, tem_hong)` + nhánh "ô đã in tem" |
| `erpnext/warehouse_operations/vitri/xep.py` | Khoá đệm `(vat_tu, so_lo)`, cảnh báo ô in tem bị chiếm |
| `erpnext/warehouse_operations/tests/test_goi_y_o.py` | Bài cho nhánh mới |
| `erpnext/warehouse_operations/tests/test_phieu_xep_vi_tri.py` | Bài cho đệm theo lô |
| `erpnext/hooks.py` | `doc_events["Batch"]["before_insert"]`, `doctype_js["Batch"]` |
| `erpnext/patches.txt` | 2 dòng |
| `erpnext/warehouse_operations/workspace/vị_trí_kho.json` | Lối vào `Batch Entry` |
| `docs/warehouse_operations/HDSD-quan-ly-vi-tri-kho.md` | Mục mới về nhập lô và in nhãn |

---

### Task 1: Custom field và móc điền nhà cung cấp

**Files:**
- Create: `erpnext/warehouse_operations/patches/v1_0/them_so_goi_va_o_in_tem.py`
- Create: `erpnext/warehouse_operations/patches/v1_0/them_thong_so_tem_cho_item.py`
- Create: `erpnext/warehouse_operations/vitri/lo_ncc.py`
- Create: `erpnext/warehouse_operations/tests/test_lo_ncc.py`
- Modify: `erpnext/patches.txt` (cuối file)
- Modify: `erpnext/hooks.py` (`doc_events`)

**Interfaces:**
- Consumes: không có (task đầu).
- Produces: `Batch.custom_so_goi` (Data) · `Batch.custom_o_in_tem` (Link Storage Location) ·
  `Item.custom_thong_so_tem` (Data 60) · `erpnext.warehouse_operations.vitri.lo_ncc.dien_ncc_tu_chung_tu(doc, method=None)`.

- [ ] **Step 1: Viết bài test trước**

`erpnext/warehouse_operations/tests/test_lo_ncc.py`:

```python
"""Móc điền NCC cho lô sinh từ chứng từ mua (spec khối C §4.3).

Vì sao móc này tồn tại: hộp thoại lô sẵn có của ERPNext trên dòng phiếu nhập
vẫn mở được và vẫn tạo lô KHÔNG có NCC. Spec chọn không chặn đường đó (chặn sẽ
vỡ các luồng kho khác dùng chung `Batch`), nên phải bảo đảm dữ liệu không thiếu
bất kể lô sinh bằng đường nào.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.warehouse_operations.tests.test_hook_nhap import _tao_item

CONG_TY = "Miyano Việt Nam"


def _ncc_thu() -> str:
	ten = "_Test NCC Nhap Lo"
	if not frappe.db.exists("Supplier", ten):
		frappe.get_doc(
			{"doctype": "Supplier", "supplier_name": ten, "supplier_group": "All Supplier Groups"}
		).insert(ignore_permissions=True)
	return ten


def _phieu_nhap_nhap(item: str, kho: str, ncc: str, qty=10):
	"""Phiếu nhập CÒN NHÁP — không submit."""
	pr = frappe.get_doc(
		{
			"doctype": "Purchase Receipt",
			"company": CONG_TY,
			"supplier": ncc,
			"items": [{"item_code": item, "qty": qty, "warehouse": kho, "rate": 1000}],
		}
	)
	pr.insert(ignore_permissions=True)
	return pr


class TestDienNccTuChungTu(FrappeTestCase):
	def setUp(self):
		self.ncc = _ncc_thu()
		self.item = _tao_item("_Test LoNcc Co Lo", co_lo=1)
		self.kho = frappe.db.get_value("Warehouse", {"company": CONG_TY, "is_group": 0}, "name")
		self.pr = _phieu_nhap_nhap(self.item, self.kho, self.ncc)

	def test_lo_tu_phieu_nhap_duoc_dien_ncc(self):
		lo = frappe.get_doc(
			{
				"doctype": "Batch",
				"batch_id": "_TEST-LONCC-001",
				"item": self.item,
				"reference_doctype": "Purchase Receipt",
				"reference_name": self.pr.name,
			}
		).insert(ignore_permissions=True)
		self.assertEqual(lo.supplier, self.ncc)

	def test_khong_ghi_de_ncc_da_co(self):
		"""Móc chỉ ĐIỀN CHỖ TRỐNG. Ghi đè là lặng lẽ sửa dữ liệu người khác đã khai."""
		ncc_khac = self.ncc
		lo = frappe.get_doc(
			{
				"doctype": "Batch",
				"batch_id": "_TEST-LONCC-002",
				"item": self.item,
				"supplier": ncc_khac,
				"reference_doctype": "Purchase Receipt",
				"reference_name": self.pr.name,
			}
		).insert(ignore_permissions=True)
		self.assertEqual(lo.supplier, ncc_khac)

	def test_lo_khong_tu_chung_tu_mua_thi_khong_dong_gi(self):
		"""Chốt âm: một đột biến bỏ hết điều kiện `reference_doctype` phải làm bài này đỏ.

		Không có bài này thì móc có thể đi lấy `supplier` của một Stock Entry
		(không có trường đó → None) hoặc tệ hơn, của một doctype tình cờ CÓ
		trường `supplier` nhưng không liên quan gì.
		"""
		lo = frappe.get_doc(
			{"doctype": "Batch", "batch_id": "_TEST-LONCC-003", "item": self.item}
		).insert(ignore_permissions=True)
		self.assertFalse(lo.supplier)


class TestCustomFieldDaCai(FrappeTestCase):
	"""Patch chạy rồi thì field phải có. Không có bài này thì Task 2-9 hỏng vì
	một lý do (patch chưa chạy) mà thông báo lỗi không hề nhắc tới."""

	def test_ba_field_ton_tai(self):
		for dt, fn in (
			("Batch", "custom_so_goi"),
			("Batch", "custom_o_in_tem"),
			("Item", "custom_thong_so_tem"),
		):
			self.assertTrue(
				frappe.db.exists("Custom Field", {"dt": dt, "fieldname": fn}),
				f"thiếu {dt}.{fn} — chạy `bench --site erptest.local migrate`",
			)
```

- [ ] **Step 2: Chạy để chắc chắn nó ĐỎ**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local run-tests --module erpnext.warehouse_operations.tests.test_lo_ncc
```
Kỳ vọng: FAIL — `custom_so_goi` chưa có, và `lo.supplier` rỗng.

- [ ] **Step 3: Viết hai patch**

`erpnext/warehouse_operations/patches/v1_0/them_so_goi_va_o_in_tem.py`:

```python
"""Thêm `Batch.custom_so_goi` và `Batch.custom_o_in_tem` (spec khối C §4.2).

Cả hai READ-ONLY có chủ đích, cùng lý do như `custom_quan_ly_vi_tri`: chúng là
KẾT QUẢ của một thao tác chứ không phải thứ để khai.

`custom_so_goi` là số người ta đọc cho nhau qua kho ("lấy giúp lô ba tám năm
sáu"). Sửa tay được nghĩa là hai lô có thể mang cùng một số gọi, và khi ấy câu
nói trong kho trỏ vào hai thùng hàng khác nhau.

`custom_o_in_tem` ghi lại MỘT SỰ KIỆN LỊCH SỬ: một tờ giấy đã in ra và đang dán
trên thùng hàng. Sửa nó không làm đổi tờ giấy đó — chỉ làm hệ thống nói khác
với vật thể.
"""

from frappe.custom.doctype.custom_field.custom_field import create_custom_field


def execute():
	create_custom_field(
		"Batch",
		{
			"fieldname": "custom_so_goi",
			"label": "Số gọi",
			"fieldtype": "Data",
			"read_only": 1,
			"insert_after": "reference_name",
			"description": "Số 4 chữ số in to trên nhãn để gọi nhanh. Chỉ 'Batch Entry' đặt.",
		},
	)
	create_custom_field(
		"Batch",
		{
			"fieldname": "custom_o_in_tem",
			"label": "Ô đã in trên tem",
			"fieldtype": "Link",
			"options": "Storage Location",
			"read_only": 1,
			"insert_after": "custom_so_goi",
			"description": "Ô đã in lên nhãn đang dán trên hàng. Gợi ý xếp sẽ ưu tiên ô này.",
		},
	)
```

`erpnext/warehouse_operations/patches/v1_0/them_thong_so_tem_cho_item.py`:

```python
"""Thêm `Item.custom_thong_so_tem` — ô F4 của nhãn lô (spec khối C §4.2).

Đặt trên ITEM chứ không phải Batch, vì thông số phân biệt SKU
("7Fr – Loop 10cm – HD 200cm") là thuộc tính của mặt hàng, không phải của lô.
Đặt trên Batch là bắt thủ kho gõ lại cùng một chuỗi cho từng lô — rồi gõ lệch
nhau giữa các lô, và hai thùng cùng một mặt hàng mang hai nhãn nói khác nhau.

60 ký tự là trần của Ô F4 ở 6,5pt trên vùng in 47mm. Dài hơn thì tràn nhãn, mà
tràn nhãn thì không có lỗi nào báo — chỉ là chữ bị cắt trên giấy.
"""

from frappe.custom.doctype.custom_field.custom_field import create_custom_field


def execute():
	create_custom_field(
		"Item",
		{
			"fieldname": "custom_thong_so_tem",
			"label": "Thông số in trên tem",
			"fieldtype": "Data",
			"length": 60,
			"insert_after": "description",
			"description": "Ô F4 nhãn lô, ví dụ '7Fr – Loop 10cm – HD 200cm'. Tối đa 60 ký tự.",
		},
	)
```

- [ ] **Step 4: Đăng ký patch**

Thêm vào **cuối** `erpnext/patches.txt`:

```
erpnext.warehouse_operations.patches.v1_0.them_so_goi_va_o_in_tem
erpnext.warehouse_operations.patches.v1_0.them_thong_so_tem_cho_item
```

- [ ] **Step 5: Viết móc điền NCC**

`erpnext/warehouse_operations/vitri/lo_ncc.py`:

```python
"""Điền nhà cung cấp cho lô sinh từ chứng từ mua (spec khối C §4.3).

Spec chọn KHÔNG chặn hộp thoại lô sẵn có của ERPNext — chặn sẽ vỡ các luồng kho
khác vốn dùng chung `Batch`. Đổi lại phải bảo đảm dữ liệu không thiếu bất kể lô
sinh bằng đường nào, và đây là chỗ làm việc đó.

`before_insert` chứ không phải `validate`: `validate` chạy lại mỗi lần lưu, nên
một người cố tình xoá NCC đi sẽ bị hệ điền lại ngay — tức là hệ cãi người dùng
mà không nói gì. Điền một lần lúc sinh ra là đủ.
"""

import frappe

# Chỉ hai doctype này. Danh sách mở rộng theo "cái nào có trường supplier" là
# cái bẫy: nhiều doctype có trường tên `supplier` mà không phải nguồn gốc của
# lô hàng (Supplier Quotation, Subscription...). Liệt kê tường minh.
_CHUNG_TU_MUA = ("Purchase Receipt", "Purchase Invoice")


def dien_ncc_tu_chung_tu(doc, method=None):
	if doc.supplier:
		return
	if doc.reference_doctype not in _CHUNG_TU_MUA or not doc.reference_name:
		return

	ncc = frappe.db.get_value(doc.reference_doctype, doc.reference_name, "supplier")
	if ncc:
		doc.supplier = ncc
```

- [ ] **Step 6: Nối móc vào `hooks.py`**

Trước khi sửa, `grep -n '"Batch"' erpnext/hooks.py` để kiểm: nếu `doc_events` **đã có**
khoá `"Batch"` thì **gộp vào khoá đó**, đừng thêm khoá thứ hai (khoá trùng trong dict
Python thì khoá sau NUỐT khoá trước, im lặng — dự án đã dính đúng việc này với khoá
`"Item"` ở khối B). Tính tới 16/09/2026 chưa có khoá `"Batch"` trong `doc_events`.

Thêm vào `doc_events`:

```python
	# Lô sinh từ hộp thoại lô sẵn có của ERPNext không mang NCC. Spec khối C §4.3
	# chọn vá dữ liệu thay vì chặn đường đó, vì `Batch` dùng chung với nhiều luồng
	# kho khác. `vi_tri_kho/tests/test_lo_ncc.py` khoá việc này.
	"Batch": {
		"before_insert": "erpnext.warehouse_operations.vitri.lo_ncc.dien_ncc_tu_chung_tu",
	},
```

- [ ] **Step 7: Migrate và chạy lại test**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local migrate
bench --site erptest.local run-tests --module erpnext.warehouse_operations.tests.test_lo_ncc
```
Kỳ vọng: PASS toàn bộ.

- [ ] **Step 8: Chạy bài khoá khởi động app**

```bash
bench --site erptest.local run-tests --module erpnext.warehouse_operations.tests.test_app_khoi_dong
```
Bài này khoá các móc trong `hooks.py` còn trỏ đúng. Kỳ vọng: PASS.

- [ ] **Step 9: Commit**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/erpnext
git add erpnext/warehouse_operations/patches/v1_0/them_so_goi_va_o_in_tem.py \
        erpnext/warehouse_operations/patches/v1_0/them_thong_so_tem_cho_item.py \
        erpnext/warehouse_operations/vitri/lo_ncc.py \
        erpnext/warehouse_operations/tests/test_lo_ncc.py \
        erpnext/patches.txt erpnext/hooks.py
git commit -m "feat(vi_tri_kho): custom field nhãn lô và móc điền NCC

..."
```

---

### Task 2: Đếm module Code 128

**Files:**
- Create: `erpnext/warehouse_operations/vitri/ma_vach.py`
- Create: `erpnext/warehouse_operations/tests/test_ma_vach.py`

**Interfaces:**
- Consumes: không có.
- Produces:
  - `so_ky_hieu(s: str) -> int`
  - `so_module(s: str) -> int`
  - `MODULE_BO_CUC_A = 112` · `MODULE_BO_CUC_B = 188` · `X_MM = 0.25`
  - `kiem_tra_do_dai(s: str, nhan: str) -> None` — `frappe.throw` nếu vượt `MODULE_BO_CUC_B`

- [ ] **Step 1: Viết bài test trước**

`erpnext/warehouse_operations/tests/test_ma_vach.py`:

```python
"""Đếm module Code 128 (spec khối C §6.4).

Vì sao phải có module riêng cho một phép tính ba dòng: con số này quyết định
CẢ phép kiểm lúc nhập lô LẪN việc nhãn chọn bố cục nào. Hai bản cài đặt thì
một ngày nào đó `validate` cho qua một số lô mà nhãn không vẽ nổi — và phát
hiện ra lúc tem đã in.

Con số đã được xác nhận bằng tay: `25L4125` (7 ký tự có chữ) ra đúng 112 module
= 28,00 mm, khớp bề rộng cột trái của bố cục A.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.warehouse_operations.vitri.ma_vach import (
	MODULE_BO_CUC_A,
	MODULE_BO_CUC_B,
	kiem_tra_do_dai,
	so_ky_hieu,
	so_module,
)


class TestSoModule(FrappeTestCase):
	def test_chuoi_co_chu_moi_ky_tu_mot_ky_hieu(self):
		self.assertEqual(so_ky_hieu("25L4125"), 7)
		self.assertEqual(so_module("25L4125"), 112)

	def test_chu_so_do_dai_chan_hai_chu_so_mot_ky_hieu(self):
		self.assertEqual(so_ky_hieu("026090374561"), 6)
		self.assertEqual(so_module("026090374561"), 101)

	def test_chu_so_do_dai_le_ton_them_hai_ky_hieu(self):
		"""Đây là chỗ bản nháp spec đã tính SAI một lần.

		Code 128 không có cách mã hoá một số lẻ chữ số trong bộ C. Chuỗi lẻ phải
		mã hoá chữ số đầu bằng bộ B rồi chèn một ký hiệu chuyển sang bộ C — tốn
		HAI ký hiệu chứ không phải làm tròn lên một. Bỏ qua chỗ này thì 13 chữ số
		lẻ bị tính là vừa 112 module trong khi thực tế là 134.
		"""
		self.assertEqual(so_ky_hieu("1" * 11), 7)
		self.assertEqual(so_module("1" * 11), 112)
		self.assertEqual(so_ky_hieu("1" * 13), 8)
		self.assertEqual(so_module("1" * 13), 123)

	def test_tran_bo_cuc(self):
		self.assertEqual(MODULE_BO_CUC_A, 112)
		self.assertEqual(MODULE_BO_CUC_B, 188)
		# 47mm / 0,25mm = 188 module. Không phải con số tròn ngẫu nhiên.
		self.assertEqual(MODULE_BO_CUC_B * 0.25, 47.0)

	def test_chuoi_rong_khong_no(self):
		self.assertEqual(so_ky_hieu(""), 0)


class TestKiemTraDoDai(FrappeTestCase):
	def test_vua_bo_cuc_b_thi_qua(self):
		kiem_tra_do_dai("A" * 13, "lô")  # 178 module

	def test_vuot_bo_cuc_b_thi_throw(self):
		with self.assertRaises(frappe.ValidationError):
			kiem_tra_do_dai("A" * 14, "lô")  # 189 module

	def test_cau_bao_noi_ro_gioi_han(self):
		"""Câu báo phải nói ĐANG bao nhiêu và ĐƯỢC bao nhiêu.

		Chốt âm cho lớp lỗi 'màn hình nói sai sự thật' đã dính hai lần trong dự
		án: một câu chung chung kiểu 'số lô quá dài' khiến thủ kho cắt bừa vài ký
		tự rồi thử lại, mà số lô cắt bớt là số lô SAI dán lên hàng.
		"""
		try:
			kiem_tra_do_dai("A" * 20, "lô")
		except frappe.ValidationError as e:
			cau = str(e)
			self.assertIn("255", cau)  # module đang có
			self.assertIn("188", cau)  # trần
		else:
			self.fail("phải throw")
```

- [ ] **Step 2: Chạy để chắc chắn nó ĐỎ**

```bash
bench --site erptest.local run-tests --module erpnext.warehouse_operations.tests.test_ma_vach
```
Kỳ vọng: FAIL — `ModuleNotFoundError: erpnext.warehouse_operations.vitri.ma_vach`.

- [ ] **Step 3: Viết `ma_vach.py`**

```python
"""Đếm module Code 128 — MỘT định nghĩa cho cả phép kiểm lẫn việc vẽ nhãn.

Vì sao không ước lượng theo độ dài chuỗi: Code 128 đổi bộ mã giữa chừng và mỗi
lần đổi tốn một ký hiệu. Một chuỗi TOÀN CHỮ SỐ độ dài LẺ không mã hoá hết được
trong bộ C (bộ C nuốt hai chữ số một lần), nên phải bắt đầu ở bộ B cho chữ số
đầu rồi chèn một ký hiệu chuyển — tốn hai ký hiệu, không phải làm tròn lên một.
Bản nháp spec đã tính sai đúng chỗ này.

Hệ quả nếu tính thiếu: `validate` cho qua một số lô mà nhãn không vẽ nổi trong
khung, JS buộc phải bóp mã vạch xuống dưới 2 dot, và máy quét ĐỌC RA SAI KÝ TỰ
— không phải đọc hỏng. Sai lặng lẽ, trên vật thể đã dán lên hàng.
"""

import frappe
from frappe import _

#: Bề rộng một module, mm. 2 dot trên đầu in nhiệt 203 dpi (1 dot = 1/203 inch
#: = 0,125 mm). 1 dot dưới ngưỡng đọc tin cậy của Code 128; 3 dot làm mã tràn
#: khung. Đây là giá trị DUY NHẤT dùng được trên ZD421 — xem spec §6.2.
X_MM = 0.25

#: Bố cục A (theo mockup SPD): mã vạch nằm ở cột trái, rộng 28,0 mm.
MODULE_BO_CUC_A = int(28.0 / X_MM)  # 112

#: Bố cục B: mã vạch chiếm hết chiều ngang vùng in an toàn, 47,0 mm.
MODULE_BO_CUC_B = int(47.0 / X_MM)  # 188

#: start (11) + checksum (11) + stop (13). Không phụ thuộc dữ liệu.
_MODULE_CO_DINH = 35

#: Mỗi ký hiệu Code 128 rộng đúng 11 module (trừ stop, đã tính ở trên).
_MODULE_MOI_KY_HIEU = 11


def so_ky_hieu(s: str) -> int:
	"""Số ký hiệu Code 128 cần để mã hoá `s`, kể cả ký hiệu chuyển bộ mã."""
	if not s:
		return 0
	if s.isdigit():
		if len(s) % 2 == 0:
			return len(s) // 2
		# Chữ số đầu đi bộ B, rồi một ký hiệu chuyển sang bộ C cho phần còn lại.
		return 2 + (len(s) - 1) // 2
	return len(s)


def so_module(s: str) -> int:
	"""Bề rộng `s` tính bằng module Code 128."""
	if not s:
		return 0
	return _MODULE_CO_DINH + _MODULE_MOI_KY_HIEU * so_ky_hieu(s)


def kiem_tra_do_dai(s: str, nhan: str) -> None:
	"""`throw` nếu `s` không vẽ nổi trong vùng in, kèm CON SỐ cụ thể.

	`nhan` là tên thứ đang kiểm, để câu báo đọc được ("số lô", "mã vật tư").

	Câu báo phải nói đang bao nhiêu / được bao nhiêu / suy ra bao nhiêu ký tự.
	Một câu chung chung khiến người dùng cắt bừa vài ký tự rồi thử lại — và số
	lô cắt bớt là số lô SAI dán lên hàng.
	"""
	m = so_module(s)
	if m <= MODULE_BO_CUC_B:
		return

	frappe.throw(
		_(
			"Số {0} '{1}' dài {2} ký tự, cần {3} module mã vạch nhưng nhãn 50×30 chỉ "
			"chứa được {4} module. Giới hạn thực tế: 26 chữ số (độ dài chẵn), "
			"23 chữ số (độ dài lẻ), hoặc 13 ký tự nếu có chữ. Không thu nhỏ mã vạch "
			"được: dưới 2 dot trên máy in nhiệt thì máy quét đọc ra SAI ký tự."
		).format(nhan, s, len(s), m, MODULE_BO_CUC_B)
	)
```

- [ ] **Step 4: Chạy lại test**

```bash
bench --site erptest.local run-tests --module erpnext.warehouse_operations.tests.test_ma_vach
```
Kỳ vọng: PASS.

- [ ] **Step 5: Commit**

```bash
git add erpnext/warehouse_operations/vitri/ma_vach.py erpnext/warehouse_operations/tests/test_ma_vach.py
git commit -m "feat(vi_tri_kho): đếm module Code 128 cho nhãn lô

..."
```

---

### Task 3: `goi_y_o` ưu tiên ô đã in trên tem

**Files:**
- Modify: `erpnext/warehouse_operations/vitri/goi_y.py`
- Modify: `erpnext/warehouse_operations/tests/test_goi_y_o.py`

**Interfaces:**
- Consumes: `Batch.custom_o_in_tem` (Task 1).
- Produces: `goi_y_o(vat_tu: str, kho: str, so_lo: str | None = None) -> tuple[str | None, str]`
  — chữ ký MỞ RỘNG TƯƠNG THÍCH NGƯỢC; mọi lời gọi cũ hai tham số vẫn chạy y như trước.

- [ ] **Step 1: Viết bài test trước**

Thêm vào cuối `erpnext/warehouse_operations/tests/test_goi_y_o.py` (đọc đầu file để dùng đúng
các helper dựng cây sẵn có — **đừng dựng lại cây bằng tay**):

```python
class TestUuTienOInTem(_NenGoiY):
	"""Spec khối C §8 — tem in ô cụ thể có thể nói dối, và cách xử.

	Nhãn in lúc nhập, hàng xếp sau. Giữa hai thời điểm đó một lượt nhập khác có
	thể chiếm mất ô đã in. Không xử thì tem dán trên thùng hàng nói sai — hạng
	lỗi tệ hơn mọi lỗi màn hình, vì màn hình sai thì làm lại được còn tem sai thì
	đi theo thùng hàng suốt vòng đời.

	Cách xử: ưu tiên ô đã in. Tem TỰ ỨNG NGHIỆM thay vì nói dối.
	"""

	def tearDown(self):
		# Cùng lý do đã ghi ở `TestGoiY.tearDown`: rollback chỉ chạy ở
		# `tearDownClass`, nên mỗi bài phải tự dọn phần của mình.
		frappe.db.delete("Location Balance", {"vat_tu": self.vt_khac})

	def _lo(self, ten, vat_tu, o_tem=None):
		"""Bản ghi `Batch` tối thiểu, mang sẵn `custom_o_in_tem`.

		`db.set_value` cho `custom_o_in_tem` KHÔNG phải vì `read_only` chặn —
		`read_only` là cờ phía trình duyệt, máy chủ ghi thoải mái. Lý do là tránh
		một vòng `Batch.validate` nữa: `set_expiry_date()` (`batch.py:184`) có
		thể `throw` khi mặt hàng bật `has_expiry_date`, và bài này không nói gì
		về hạn dùng.
		"""
		frappe.get_doc({"doctype": "Batch", "batch_id": ten, "item": vat_tu}).insert(
			ignore_permissions=True
		)
		if o_tem:
			frappe.db.set_value("Batch", ten, "custom_o_in_tem", o_tem)
		return ten

	def test_tra_dung_o_da_in_du_khong_phai_o_dau_theo_lft(self):
		"""Chốt then chốt của cả task.

		Ô đã in phải KHÁC ô mà thứ tự `lft` sẽ chọn. Trùng nhau thì bài xanh mà
		không chứng minh được gì — đúng cái bẫy đã ghi ở khối B §10. Nên ở đây
		tầng còn trống hoàn toàn (ô đầu theo `lft` là `...01`) và tem in `...03`.
		"""
		v = _mat_hang("_Test Tem UuTien")
		_gan(v, self.tang)
		lo = self._lo("_TEST-TEM-UUTIEN", v, "6B01020103")

		o, ly_do = goi_y_o(v, KHO, lo)
		self.assertEqual(o, "6B01020103")
		self.assertIn("tem", ly_do)

		# Chốt âm trong cùng một bài: bỏ `so_lo` ra thì câu trả lời phải KHÁC.
		# Không có vế này, một cài đặt bỏ qua hẳn tham số `so_lo` vẫn có thể
		# xanh nếu dữ liệu vô tình trùng.
		self.assertEqual(goi_y_o(v, KHO)[0], "6B01020101")

		frappe.db.delete("Item Location Preference", {"vat_tu": v})

	def test_khong_truyen_so_lo_thi_bo_qua_nhanh_nay(self):
		"""Lúc nạp dòng `Batch Entry`, lô CHƯA tồn tại. Nhánh này phải im lặng
		bỏ qua chứ không nổ."""
		v = _mat_hang("_Test Tem KhongLo")
		_gan(v, self.tang)

		o, ly_do = goi_y_o(v, KHO)
		self.assertEqual(o, "6B01020101")
		self.assertNotIn("tem", ly_do)

		frappe.db.delete("Item Location Preference", {"vat_tu": v})

	def test_o_da_in_bi_mat_hang_khac_chiem_thi_tra_o_khac(self):
		"""Và lý do phải NÊU TÊN ô trên tem cũ.

		Thủ kho đang cầm tờ tem in `6B01020103` trên tay. Một câu chung chung
		("ô trống đầu tiên trong 6B010201") để họ tự đoán xem tem còn đúng không
		— và phần lớn sẽ đi theo tem.
		"""
		v = _mat_hang("_Test Tem BiChiem")
		_gan(v, self.tang)
		_ton("6B01020103", self.vt_khac, 7)
		lo = self._lo("_TEST-TEM-BICHIEM", v, "6B01020103")

		o, ly_do = goi_y_o(v, KHO, lo)
		self.assertEqual(o, "6B01020101")
		self.assertIn("6B01020103", ly_do)

		frappe.db.delete("Item Location Preference", {"vat_tu": v})

	def test_o_da_in_dang_co_hang_cung_mat_hang_thi_van_uu_tien(self):
		"""Dồn vào ô cũ là hành vi ĐÚNG — §3.4 (b) của khối B.

		Chốt âm cho một cài đặt lười: điều kiện "ô còn dùng được" mà viết thành
		"ô phải TRỐNG" sẽ làm bài này đỏ, đúng như mong muốn.
		"""
		v = _mat_hang("_Test Tem DonVaoCu")
		_gan(v, self.tang)
		_ton("6B01020103", v, 4)
		lo = self._lo("_TEST-TEM-DONCU", v, "6B01020103")

		o, _ly_do = goi_y_o(v, KHO, lo)
		self.assertEqual(o, "6B01020103")

		frappe.db.delete("Location Balance", {"vat_tu": v})
		frappe.db.delete("Item Location Preference", {"vat_tu": v})

	def test_o_da_in_nam_ngoai_vung_gan_thi_bo_qua(self):
		"""Ai đó đổi gán vị trí SAU khi đã in tem.

		Tem cũ trỏ ra ngoài vùng mới; đi theo nó là xếp hàng ra ngoài vùng đã
		gán, tức phá đúng cái bất biến mà cả khối B dựng lên.
		"""
		_o("6D01020101")
		v = _mat_hang("_Test Tem NgoaiVung")
		_gan(v, self.tang)
		lo = self._lo("_TEST-TEM-NGOAI", v, "6D01020101")

		o, ly_do = goi_y_o(v, KHO, lo)
		self.assertEqual(o, "6B01020101")
		self.assertIn("6D01020101", ly_do)

		frappe.db.delete("Item Location Preference", {"vat_tu": v})

	def test_o_da_in_dang_ngung_dung_thi_bo_qua(self):
		"""Dãy bị tắt thì không xếp vào, kể cả khi tem đã in.

		`_UNG_VIEN` đã mang sẵn luật "chính nó HOẶC tổ tiên `disabled`"
		(`fefo.to_tien_tat`). Bài này khoá việc nhánh mới DÙNG LẠI `_UNG_VIEN`
		chứ không tự viết một truy vấn riêng bỏ quên điều kiện đó.
		"""
		v = _mat_hang("_Test Tem Tat")
		_gan(v, self.tang)
		lo = self._lo("_TEST-TEM-TAT", v, "6B01020103")
		frappe.db.set_value("Storage Location", "6B01020103", "disabled", 1)
		try:
			o, ly_do = goi_y_o(v, KHO, lo)
			self.assertEqual(o, "6B01020101")
			self.assertIn("6B01020103", ly_do)
		finally:
			frappe.db.set_value("Storage Location", "6B01020103", "disabled", 0)
			frappe.db.delete("Item Location Preference", {"vat_tu": v})
```

Lưu ý cho người thi công: `_NenGoiY` (lớp nền sẵn có trong file) đã dựng ba ô
`6B01020101/02/03` dưới tầng `6B010201` và hai mặt hàng `cls.vt` / `cls.vt_khac`. Dùng
lại, **đừng dựng cây mới**.

- [ ] **Step 2: Chạy để chắc chắn nó ĐỎ**

```bash
bench --site erptest.local run-tests --module erpnext.warehouse_operations.tests.test_goi_y_o
```
Kỳ vọng: FAIL — `goi_y_o() takes 2 positional arguments but 3 were given`.

- [ ] **Step 3: Sửa `goi_y.py`**

Đổi chữ ký và chèn nhánh mới **ngay sau** khối chặn toạ độ rỗng, **trước** truy vấn
`trong`:

```python
def goi_y_o(vat_tu: str, kho: str, so_lo: str | None = None) -> tuple[str | None, str]:
	"""Ô nên xếp `vat_tu` vào, kèm lý do. `(None, lý do)` nếu không gợi ý được.

	`so_lo` TUỲ CHỌN: lúc nạp dòng trên `Batch Entry` thì lô chưa tồn tại, và
	phiếu xếp thì có. Có `so_lo` và lô đó đã in tem → ưu tiên đúng ô đã in
	(spec khối C §8).
	"""
```

... (giữ nguyên phần lấy `gan` và chặn toạ độ rỗng) ...

```python
	tham_so = {"lft": g.lft, "rgt": g.rgt, "vat_tu": vat_tu}

	# Ô ĐÃ IN TEM đi trước mọi thứ khác (spec khối C §8).
	#
	# Vì sao ưu tiên chứ không phải "giữ chỗ": giữ chỗ cần hết hạn, cần dọn khi
	# huỷ, cần thêm một doctype nữa — tất cả để giải một bài mà một trường đã
	# giải xong. Ưu tiên khiến tem TỰ ỨNG NGHIỆM: cái gì in ra thì cái đó thành
	# sự thật, miễn là còn xếp vào được.
	#
	# Bốn điều kiện dưới đều CẦN, mỗi cái khoá một đường tem nói dối khác nhau:
	# nằm trong vùng gán (ai đó đổi gán sau khi in), là ô lá thật, không nằm
	# dưới nhánh ngừng dùng, và chưa bị mặt hàng KHÁC chiếm.
	if so_lo:
		o_tem = frappe.db.get_value("Batch", so_lo, "custom_o_in_tem")
		if o_tem:
			dung_duoc = frappe.db.sql(
				f"""
				select sl.name
				{_UNG_VIEN}
				  and sl.name = %(o_tem)s
				  and not exists (
				        select 1 from `tabLocation Balance` lb
				        where lb.o = sl.name and lb.vat_tu != %(vat_tu)s and lb.so_luong != 0
				      )
				limit 1
				""",
				dict(tham_so, o_tem=o_tem),
			)
			if dung_duoc:
				return o_tem, _("theo ô đã in trên tem của lô {0}").format(so_lo)
			# Không im lặng bỏ qua: thủ kho đang cầm một tờ tem in ô này trên tay.
			# Phải biết tem đó không dùng được nữa, và vì sao.
			ly_do_tem = _("tem của lô {0} in ô {1} nhưng ô đó không xếp được nữa").format(
				so_lo, o_tem
			)
		else:
			ly_do_tem = None
	else:
		ly_do_tem = None
```

Rồi ở **mỗi** nhánh trả về phía sau (`trong`, `cung_hang`, và nhánh "đã đầy"), nếu
`ly_do_tem` có giá trị thì **ghép nó vào trước** lý do gốc:

```python
	def _ly_do(goc: str) -> str:
		return f"{ly_do_tem} — {goc}" if ly_do_tem else goc
```

và dùng `_ly_do(...)` bọc cả ba câu lý do hiện có.

- [ ] **Step 4: Chạy lại test**

```bash
bench --site erptest.local run-tests --module erpnext.warehouse_operations.tests.test_goi_y_o
```
Kỳ vọng: PASS, kể cả các bài CŨ trong file (chữ ký mở rộng tương thích ngược).

- [ ] **Step 5: Chạy bài phiếu xếp để chắc không vỡ gì**

```bash
bench --site erptest.local run-tests --module erpnext.warehouse_operations.tests.test_phieu_xep_vi_tri
```
Kỳ vọng: PASS (Task 4 mới đổi `xep.py`; ở đây chỉ kiểm không vỡ).

- [ ] **Step 6: Commit**

```bash
git add erpnext/warehouse_operations/vitri/goi_y.py erpnext/warehouse_operations/tests/test_goi_y_o.py
git commit -m "feat(vi_tri_kho): gợi ý ưu tiên ô đã in trên tem

..."
```

---

### Task 4: Phiếu xếp gợi ý theo LÔ, không theo mặt hàng

**Files:**
- Modify: `erpnext/warehouse_operations/vitri/xep.py`
- Modify: `erpnext/warehouse_operations/tests/test_phieu_xep_vi_tri.py`
- Modify: `erpnext/warehouse_operations/doctype/location_transfer/location_transfer.js`

**Interfaces:**
- Consumes: `goi_y_o(vat_tu, kho, so_lo=None)` (Task 3).
- Produces: `hang_chua_xep(kho)` trả thêm gợi ý phân biệt theo lô; khoá đệm đổi từ
  `vat_tu` sang `(vat_tu, so_lo)`.

- [ ] **Step 1: Viết bài test trước**

Thêm vào `erpnext/warehouse_operations/tests/test_phieu_xep_vi_tri.py`:

```python
	def test_hai_lo_cung_mat_hang_co_the_ra_hai_o_khac_nhau(self):
		"""Khoá đệm phải là (mặt hàng, lô), không phải mặt hàng.

		Trước khối C, một mặt hàng nhiều lô cho ra MỘT gợi ý chung — đúng khi
		căn cứ duy nhất là vị trí gán. Từ khi tem ghi lại ô đã in (§8), hai lô
		của cùng một mặt hàng có thể có hai ô in tem khác nhau, và đệm theo mặt
		hàng sẽ lấy gợi ý của lô ĐẦU TIÊN gán cho cả hai — tức nửa số tem nói dối.
		"""
		...

	def test_van_chi_goi_goi_y_mot_lan_cho_moi_lo(self):
		"""Không được bỏ đệm đi: một kho có thể có hàng trăm dòng."""
		...
```

- [ ] **Step 2: Chạy để chắc chắn nó ĐỎ**

```bash
bench --site erptest.local run-tests --module erpnext.warehouse_operations.tests.test_phieu_xep_vi_tri
```

- [ ] **Step 3: Sửa `xep.py`**

Trong `hang_chua_xep`, đổi khối đệm:

```python
	# Một lời gọi `goi_y_o` cho mỗi (MẶT HÀNG, LÔ).
	#
	# Trước khối C khoá đệm chỉ là `vat_tu`, vì gợi ý khi ấy chỉ phụ thuộc vị trí
	# gán — thứ chung cho mọi lô của mặt hàng. Từ khối C §8, gợi ý còn phụ thuộc
	# `Batch.custom_o_in_tem`, vốn RIÊNG từng lô. Giữ khoá cũ thì lô thứ hai
	# nhận gợi ý của lô thứ nhất và tem của nó nói dối.
	bo_nho: dict[tuple, tuple] = {}
	for d in dong:
		khoa = (d.vat_tu, d.so_lo)
		if khoa not in bo_nho:
			try:
				bo_nho[khoa] = goi_y_o(d.vat_tu, kho, d.so_lo)
			except Exception:
				frappe.log_error(
					title=f"vi_tri_kho: hang_chua_xep goi_y_o loi ({d.vat_tu}/{d.so_lo})"
				)
				bo_nho[khoa] = (
					None,
					_(
						"không gợi ý được cho {0} — xem Error Log. KHÔNG PHẢI mặt hàng "
						"chưa gán, đừng gán lại"
					).format(d.vat_tu),
				)
		d["den_o"], d["ly_do_goi_y"] = bo_nho[khoa]
	return dong
```

Cập nhật docstring của hàm: nói rõ khoá đệm là cặp và vì sao (Ruling N giữ nguyên).

- [ ] **Step 4: Cho `ly_do_goi_y` hiện cả khi ĐÃ có gợi ý**

`location_transfer.js` hiện chỉ tóm tắt lý do cho các dòng **không** có `den_o`. Từ khối
C, một dòng **có** `den_o` vẫn có thể mang lý do cần đọc ("tem in ô X nhưng ô đó không
xếp được nữa — ô trống đầu tiên trong Y"). Sửa khối tóm tắt:

```javascript
			// Từ khối C §8, một dòng CÓ gợi ý vẫn có thể mang tin cần đọc: tem đã
			// in một ô mà giờ không xếp được nữa. Thủ kho đang cầm tờ tem đó trên
			// tay và phải biết để dán đè tem mới. Lọc cũ chỉ bắt dòng TRỐNG nên
			// bỏ lọt đúng ca này.
			const can_doc = dong.filter((d) => !d.den_o || (d.ly_do_goi_y || "").includes("tem"));
```

và đổi câu tóm tắt cho hai nhóm ("chưa có gợi ý" và "tem cũ không dùng được").

- [ ] **Step 5: Chạy lại test**

```bash
bench --site erptest.local run-tests --module erpnext.warehouse_operations.tests.test_phieu_xep_vi_tri
bench --site erptest.local run-tests --module erpnext.warehouse_operations.tests.test_goi_y_o
```
Kỳ vọng: PASS cả hai.

- [ ] **Step 6: Commit**

```bash
git add erpnext/warehouse_operations/vitri/xep.py erpnext/warehouse_operations/tests/test_phieu_xep_vi_tri.py \
        erpnext/warehouse_operations/doctype/location_transfer/location_transfer.js
git commit -m "feat(vi_tri_kho): phiếu xếp gợi ý theo lô thay vì theo mặt hàng

..."
```

---

### Task 5: DocType `Batch Entry` + `Batch Entry Item` (lược đồ và `validate`)

Task này **chưa** làm submit. Chỉ lược đồ và các phép kiểm — để reviewer từ chối được
phần kiểm mà không phải đọc cả phần ghi dữ liệu.

**Files:**
- Create: `erpnext/warehouse_operations/doctype/batch_entry_item/__init__.py`
- Create: `erpnext/warehouse_operations/doctype/batch_entry_item/batch_entry_item.json`
- Create: `erpnext/warehouse_operations/doctype/batch_entry_item/batch_entry_item.py`
- Create: `erpnext/warehouse_operations/doctype/batch_entry/__init__.py`
- Create: `erpnext/warehouse_operations/doctype/batch_entry/batch_entry.json`
- Create: `erpnext/warehouse_operations/doctype/batch_entry/batch_entry.py`
- Create: `erpnext/warehouse_operations/tests/test_nhap_lo.py`

**Interfaces:**
- Consumes: `ma_vach.kiem_tra_do_dai` (Task 2).
- Produces: doctype `Batch Entry` (submittable) và `Batch Entry Item`; lớp
  `BatchEntry` với `validate()`.

- [ ] **Step 1: Viết bài test trước**

`erpnext/warehouse_operations/tests/test_nhap_lo.py`:

```python
"""Phiếu nhập lô — lược đồ và phép kiểm (spec khối C §5).

Thứ tự các phép kiểm là MỘT PHẦN của spec, không phải chi tiết cài đặt: câu báo
lỗi đầu tiên người dùng thấy phải là câu chỉ đúng chỗ sai. Kiểm độ dài mã vạch
trước khi kiểm trùng số lô thì người gõ nhầm một số lô dài sẽ được bảo là "trùng",
đi sửa sai chỗ.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.warehouse_operations.tests.test_hook_nhap import _tao_item
from erpnext.warehouse_operations.tests.test_lo_ncc import _ncc_thu, _phieu_nhap_nhap

CONG_TY = "Miyano Việt Nam"


def _phieu_nhap_lo(pr, dong: list[dict]):
	"""Dựng `Batch Entry` từ một phiếu nhập, KHÔNG submit."""
	be = frappe.get_doc({"doctype": "Batch Entry", "phieu_nhap": pr.name, "items": dong})
	return be


class TestValidate(FrappeTestCase):
	def setUp(self):
		self.ncc = _ncc_thu()
		self.item = _tao_item("_Test NhapLo Co Lo", co_lo=1)
		self.kho = frappe.db.get_value("Warehouse", {"company": CONG_TY, "is_group": 0}, "name")
		self.pr = _phieu_nhap_nhap(self.item, self.kho, self.ncc)
		self.dong_pr = self.pr.items[0].name

	def _dong(self, **ghi_de):
		d = {
			"dong_phieu_nhap": self.dong_pr,
			"vat_tu": self.item,
			"kho": self.kho,
			"so_luong": 10,
			"so_lo": "LO-TEST-01",
			"hsd": "2030-01-31",
		}
		d.update(ghi_de)
		return d

	def test_phieu_hop_le_thi_luu_duoc(self):
		be = _phieu_nhap_lo(self.pr, [self._dong()])
		be.insert(ignore_permissions=True)
		self.assertEqual(be.nha_cung_cap, self.ncc)

	def test_phieu_nhap_da_submit_thi_chan(self):
		"""Và câu báo phải nói rõ THỨ TỰ đúng, vì đây là lỗi thao tác chứ không
		phải lỗi dữ liệu — người dùng cần biết làm gì tiếp, không phải biết cái
		gì sai."""
		self.pr.submit()
		be = _phieu_nhap_lo(self.pr, [self._dong()])
		with self.assertRaises(frappe.ValidationError) as ngu_canh:
			be.insert(ignore_permissions=True)
		self.assertIn("trước", str(ngu_canh.exception))

	def test_hai_dong_cung_mot_dong_phieu_nhap_thi_chan(self):
		"""Spec §5.4 — một dòng phiếu nhập = một lô."""
		be = _phieu_nhap_lo(
			self.pr, [self._dong(so_lo="LO-A"), self._dong(so_lo="LO-B")]
		)
		with self.assertRaises(frappe.ValidationError):
			be.insert(ignore_permissions=True)

	def test_dong_khong_thuoc_phieu_nhap_dang_chon_thi_chan(self):
		"""Chốt âm: bỏ phép kiểm này ra thì một `dong_phieu_nhap` chép nhầm từ
		phiếu khác sẽ ghi `batch_no` lên một chứng từ KHÔNG liên quan, lúc submit."""
		pr2 = _phieu_nhap_nhap(self.item, self.kho, self.ncc)
		be = _phieu_nhap_lo(self.pr, [self._dong(dong_phieu_nhap=pr2.items[0].name)])
		with self.assertRaises(frappe.ValidationError):
			be.insert(ignore_permissions=True)

	def test_so_lo_chi_co_khoang_trang_thi_chan(self):
		be = _phieu_nhap_lo(self.pr, [self._dong(so_lo="   ")])
		with self.assertRaises(frappe.ValidationError):
			be.insert(ignore_permissions=True)

	def test_so_lo_qua_dai_thi_chan_truoc_moi_phep_kiem_khac(self):
		"""Thứ tự: mã vạch trước, trùng lô sau. Xem docstring đầu file."""
		be = _phieu_nhap_lo(self.pr, [self._dong(so_lo="A" * 30)])
		with self.assertRaises(frappe.ValidationError) as ngu_canh:
			be.insert(ignore_permissions=True)
		self.assertIn("module", str(ngu_canh.exception))

	def test_so_lo_trung_voi_lo_cua_mat_hang_khac_thi_chan(self):
		item2 = _tao_item("_Test NhapLo Co Lo 2", co_lo=1)
		frappe.get_doc(
			{"doctype": "Batch", "batch_id": "LO-DUNG-CHUNG", "item": item2}
		).insert(ignore_permissions=True)
		be = _phieu_nhap_lo(self.pr, [self._dong(so_lo="LO-DUNG-CHUNG")])
		with self.assertRaises(frappe.ValidationError) as ngu_canh:
			be.insert(ignore_permissions=True)
		self.assertIn(item2, str(ngu_canh.exception))

	def test_so_lo_trung_voi_lo_cua_CHINH_mat_hang_nay_thi_cho_qua(self):
		"""Lô thứ hai về cùng một số lô là chuyện thật (NCC giao làm hai đợt).
		Chặn ở đây là chặn một nghiệp vụ hợp lệ. Task 6 sẽ DÙNG LẠI lô đó thay
		vì tạo mới."""
		frappe.get_doc(
			{"doctype": "Batch", "batch_id": "LO-DOT-2", "item": self.item}
		).insert(ignore_permissions=True)
		be = _phieu_nhap_lo(self.pr, [self._dong(so_lo="LO-DOT-2")])
		be.insert(ignore_permissions=True)

	def test_hsd_truoc_ngay_san_xuat_thi_chan(self):
		be = _phieu_nhap_lo(
			self.pr, [self._dong(ngay_san_xuat="2030-02-01", hsd="2030-01-31")]
		)
		with self.assertRaises(frappe.ValidationError):
			be.insert(ignore_permissions=True)
```

- [ ] **Step 2: Chạy để chắc chắn nó ĐỎ**

```bash
bench --site erptest.local run-tests --module erpnext.warehouse_operations.tests.test_nhap_lo
```
Kỳ vọng: FAIL — `DoesNotExistError: DocType Batch Entry not found`.

- [ ] **Step 3: Tạo `Batch Entry Item`**

`erpnext/warehouse_operations/doctype/batch_entry_item/__init__.py`: file rỗng.

`erpnext/warehouse_operations/doctype/batch_entry_item/batch_entry_item.json`:

```json
{
 "actions": [],
 "allow_rename": 1,
 "creation": "2026-09-16 09:00:00.000000",
 "doctype": "DocType",
 "editable_grid": 1,
 "engine": "InnoDB",
 "field_order": [
  "dong_phieu_nhap", "vat_tu", "ten_hang", "kho", "so_luong",
  "col_1", "so_lo", "ngay_san_xuat", "hsd",
  "sec_goi_y", "o_goi_y", "ly_do_goi_y",
  "col_2", "lo_da_tao", "so_goi"
 ],
 "fields": [
  {"fieldname": "dong_phieu_nhap", "fieldtype": "Data", "label": "Dòng phiếu nhập", "hidden": 1, "reqd": 1, "read_only": 1},
  {"fieldname": "vat_tu", "fieldtype": "Link", "label": "Vật tư", "options": "Item", "read_only": 1, "in_list_view": 1, "columns": 2},
  {"fieldname": "ten_hang", "fieldtype": "Data", "label": "Tên hàng", "read_only": 1, "in_list_view": 1, "columns": 2},
  {"fieldname": "kho", "fieldtype": "Link", "label": "Kho", "options": "Warehouse", "read_only": 1},
  {"fieldname": "so_luong", "fieldtype": "Float", "label": "Số lượng", "read_only": 1, "in_list_view": 1, "columns": 1},
  {"fieldname": "col_1", "fieldtype": "Column Break"},
  {"fieldname": "so_lo", "fieldtype": "Data", "label": "Số lô", "reqd": 1, "in_list_view": 1, "columns": 2},
  {"fieldname": "ngay_san_xuat", "fieldtype": "Date", "label": "Ngày sản xuất"},
  {"fieldname": "hsd", "fieldtype": "Date", "label": "Hạn dùng", "in_list_view": 1, "columns": 1},
  {"fieldname": "sec_goi_y", "fieldtype": "Section Break", "label": "Gợi ý vị trí"},
  {"fieldname": "o_goi_y", "fieldtype": "Link", "label": "Ô gợi ý", "options": "Storage Location", "read_only": 1, "in_list_view": 1, "columns": 2},
  {"fieldname": "ly_do_goi_y", "fieldtype": "Small Text", "label": "Lý do gợi ý", "read_only": 1},
  {"fieldname": "col_2", "fieldtype": "Column Break"},
  {"fieldname": "lo_da_tao", "fieldtype": "Link", "label": "Lô đã tạo", "options": "Batch", "read_only": 1, "allow_on_submit": 1},
  {"fieldname": "so_goi", "fieldtype": "Data", "label": "Số gọi", "read_only": 1, "allow_on_submit": 1}
 ],
 "index_web_pages_for_search": 1,
 "istable": 1,
 "links": [],
 "modified": "2026-09-16 09:00:00.000000",
 "modified_by": "Administrator",
 "module": "Warehouse Operations",
 "name": "Batch Entry Item",
 "owner": "Administrator",
 "permissions": [],
 "sort_field": "modified",
 "sort_order": "DESC",
 "states": []
}
```

`batch_entry_item.py`:

```python
"""Một dòng hàng của phiếu nhập lô.

`dong_phieu_nhap` (tên bản ghi `Purchase Receipt Item`) là KHOÁ LIÊN KẾT thật,
không phải `vat_tu`: một phiếu nhập có thể có hai dòng cùng một mặt hàng, về
hai kho hoặc hai đơn giá khác nhau, và mỗi dòng cần số lô riêng.
"""

from frappe.model.document import Document


class BatchEntryItem(Document):
	pass
```

- [ ] **Step 4: Tạo `Batch Entry`**

`erpnext/warehouse_operations/doctype/batch_entry/batch_entry.json`:

```json
{
 "actions": [],
 "autoname": "naming_series:",
 "creation": "2026-09-16 09:00:00.000000",
 "doctype": "DocType",
 "editable_grid": 1,
 "engine": "InnoDB",
 "field_order": [
  "naming_series", "phieu_nhap", "cong_ty",
  "col_1", "ngay", "nha_cung_cap",
  "sec_dong", "items",
  "sec_ghi_chu", "ghi_chu", "amended_from"
 ],
 "fields": [
  {"fieldname": "naming_series", "fieldtype": "Select", "label": "Sê-ri", "options": "PNL-.YYYY.-", "default": "PNL-.YYYY.-", "reqd": 1, "print_hide": 1},
  {"fieldname": "phieu_nhap", "fieldtype": "Link", "label": "Phiếu nhập", "options": "Purchase Receipt", "reqd": 1, "set_only_once": 1, "in_list_view": 1},
  {"fieldname": "cong_ty", "fieldtype": "Link", "label": "Công ty", "options": "Company", "read_only": 1, "fetch_from": "phieu_nhap.company"},
  {"fieldname": "col_1", "fieldtype": "Column Break"},
  {"fieldname": "ngay", "fieldtype": "Date", "label": "Ngày nhập", "read_only": 1, "fetch_from": "phieu_nhap.posting_date"},
  {"fieldname": "nha_cung_cap", "fieldtype": "Link", "label": "Nhà cung cấp", "options": "Supplier", "read_only": 1, "fetch_from": "phieu_nhap.supplier", "in_list_view": 1},
  {"fieldname": "sec_dong", "fieldtype": "Section Break", "label": "Dòng hàng"},
  {"fieldname": "items", "fieldtype": "Table", "label": "Dòng hàng", "options": "Batch Entry Item", "reqd": 1},
  {"fieldname": "sec_ghi_chu", "fieldtype": "Section Break"},
  {"fieldname": "ghi_chu", "fieldtype": "Small Text", "label": "Ghi chú"},
  {"fieldname": "amended_from", "fieldtype": "Link", "label": "Sửa từ", "options": "Batch Entry", "read_only": 1, "no_copy": 1, "print_hide": 1}
 ],
 "index_web_pages_for_search": 1,
 "is_submittable": 1,
 "links": [],
 "modified": "2026-09-16 09:00:00.000000",
 "modified_by": "Administrator",
 "module": "Warehouse Operations",
 "name": "Batch Entry",
 "naming_rule": "By \"Naming Series\" field",
 "owner": "Administrator",
 "permissions": [
  {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "submit": 1, "cancel": 1, "amend": 1, "report": 1, "export": 1, "print": 1, "email": 1, "share": 1},
  {"role": "Stock Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "submit": 1, "cancel": 1, "amend": 1, "report": 1, "export": 1, "print": 1, "email": 1, "share": 1},
  {"role": "Stock User", "read": 1, "write": 1, "create": 1, "submit": 1, "cancel": 1, "amend": 1, "report": 1, "print": 1, "share": 1}
 ],
 "sort_field": "modified",
 "sort_order": "DESC",
 "states": [],
 "title_field": "phieu_nhap",
 "track_changes": 1
}
```

`allow_on_submit: 1` trên `lo_da_tao` và `so_goi` KHÔNG phải trang trí: Task 6 ghi hai
trường này trong `on_submit`, lúc `docstatus` đã bằng 1. Thiếu cờ đó thì `db_set` ném
`UpdateAfterSubmitError` và cả `on_submit` đổ — sau khi `Batch` đã được tạo. Tức là một
phiếu hỏng giữa chừng: lô có thật, phiếu báo lỗi.

Bộ vai trò khớp `VAI_TRO_DUOC_XEP` ở `xep.py:17` — nhập lô cũng là việc hằng ngày của
thủ kho, không phải thao tác thiết lập. `Stock User` không được `delete`, giống khuôn
`Location Transfer`.

- [ ] **Step 5: Viết `validate`**

`erpnext/warehouse_operations/doctype/batch_entry/batch_entry.py`:

```python
"""Phiếu nhập lô — khai số lô và HSD cho từng dòng phiếu nhập (spec khối C §5).

VÌ SAO LÀ PHIẾU RIÊNG chứ không phải sửa hộp thoại lô sẵn có của ERPNext: chủ
đầu tư chốt 16/09/2026. Cái giá đã biết và đã chấp nhận — hộp thoại cũ vẫn mở
được và vẫn tạo được lô không tem; §4.3 vá phần dữ liệu, phần số lô máy sinh thì
là lựa chọn nghiệp vụ.

VÌ SAO GHI `batch_no` LÊN DÒNG PHIẾU NHẬP thay vì tự dựng `Serial and Batch
Bundle`: một trường, không có gì khác. Tự dựng bundle là bám vào nội bộ một hệ
thống đã đổi kiến trúc lô một lần giữa v14 và v15 — và sẽ đổi nữa.

ĐÃ ĐO TRÊN erptest.local (16/09/2026), không phải suy từ mã:

    A. sau frappe.db.set_value  batch_no = 'PROBE-LO-001'
    B. sau reload + save (nháp) batch_no = 'PROBE-LO-001'   <- KHÔNG bị xoá
    C. sau submit phiếu nhập    batch_no = 'PROBE-LO-001'
       số Batch của mặt hàng    1 -> 1                      <- KHÔNG sinh lô máy
       bundle                   docstatus 1, dòng con {batch_no: PROBE-LO-001, qty: 10}
    E. scan_barcode('PROBE-LO-001') -> {batch_no, item_code, has_batch_no}

Điểm B là điểm phải đo: `frappe.db.set_value` đi thẳng xuống CSDL, không qua bản
sao trong bộ nhớ. Nếu ai đó mở phiếu nháp ra lưu lại giữa lúc ta ghi và lúc
submit, một bản sao cũ có thể ghi đè `batch_no` về rỗng — và lô của NCC mất mà
không có lỗi nào báo. Đo cho thấy KHÔNG xảy ra. Nếu một bản ERPNext sau này đổi
điều đó, `test_phieu_nhap_submit_sau_do_khong_sinh_lo_may_nao_nua` sẽ đỏ.

Đáng ghi lại: sau submit `use_serial_batch_fields` vẫn bằng 0, tức bundle được
dựng bằng một nhánh KHÁC nhánh `stock_controller.py:231-234`. Không cần biết
nhánh nào — đừng viết mã dựa trên nó. Thứ ràng buộc là KẾT QUẢ đo được ở trên,
và bài test khoá đúng kết quả đó.
"""

import frappe
from frappe import _
from frappe.model.document import Document

from erpnext.warehouse_operations.vitri.ma_vach import kiem_tra_do_dai


class BatchEntry(Document):
	def validate(self):
		# Thứ tự này là một phần của spec (§5.5), không phải chi tiết cài đặt:
		# câu báo lỗi ĐẦU TIÊN người dùng thấy phải chỉ đúng chỗ sai. Kiểm trùng
		# số lô trước khi kiểm độ dài thì người gõ một số lô quá dài được bảo là
		# "trùng" và đi sửa sai chỗ.
		self.kiem_tra_phieu_nhap_con_nhap()
		self.kiem_tra_dong_thuoc_phieu()
		self.kiem_tra_so_lo()
		self.kiem_tra_ngay()

	def kiem_tra_phieu_nhap_con_nhap(self):
		trang_thai = frappe.db.get_value("Purchase Receipt", self.phieu_nhap, "docstatus")
		if trang_thai != 0:
			frappe.throw(
				_(
					"Phiếu nhập {0} đã duyệt nên không gắn được số lô nữa. Phải nhập lô "
					"TRƯỚC rồi mới duyệt phiếu nhập — duyệt trước thì ERPNext đã tự sinh "
					"số lô máy và số lô của nhà cung cấp mất luôn."
				).format(self.phieu_nhap)
			)

	def kiem_tra_dong_thuoc_phieu(self):
		"""Mỗi dòng phiếu nhập xuất hiện đúng một lần, và phải là dòng của ĐÚNG
		phiếu đang chọn.

		Vế thứ hai không thừa: không có nó thì một `dong_phieu_nhap` chép nhầm từ
		phiếu khác sẽ khiến `on_submit` ghi `batch_no` lên một chứng từ không
		liên quan — sửa dữ liệu của người khác, im lặng.
		"""
		hop_le = set(
			frappe.get_all(
				"Purchase Receipt Item",
				filters={"parent": self.phieu_nhap},
				pluck="name",
			)
		)
		da_thay = set()
		for d in self.items:
			if d.dong_phieu_nhap not in hop_le:
				frappe.throw(
					_("Dòng {0}: dòng hàng không thuộc phiếu nhập {1}.").format(
						d.idx, self.phieu_nhap
					)
				)
			if d.dong_phieu_nhap in da_thay:
				frappe.throw(
					_(
						"Dòng {0}: mỗi dòng phiếu nhập chỉ nhận MỘT số lô. Hàng về hai lô "
						"thì tách dòng trên phiếu nhập — tách rồi số lượng theo từng lô "
						"cũng đúng luôn trên chứng từ."
					).format(d.idx)
				)
			da_thay.add(d.dong_phieu_nhap)

	def kiem_tra_so_lo(self):
		for d in self.items:
			d.so_lo = (d.so_lo or "").strip()
			if not d.so_lo:
				frappe.throw(_("Dòng {0}: chưa có số lô.").format(d.idx))

			kiem_tra_do_dai(d.so_lo, _("lô"))

			chu_lo = frappe.db.get_value("Batch", d.so_lo, "item")
			if chu_lo and chu_lo != d.vat_tu:
				frappe.throw(
					_(
						"Dòng {0}: số lô '{1}' đã thuộc mặt hàng {2}. Số lô là tên bản ghi "
						"trong ERPNext nên duy nhất toàn hệ, hai mặt hàng không dùng chung "
						"được."
					).format(d.idx, d.so_lo, chu_lo)
				)

	def kiem_tra_ngay(self):
		for d in self.items:
			if d.ngay_san_xuat and d.hsd and d.hsd < d.ngay_san_xuat:
				frappe.throw(
					_("Dòng {0}: hạn dùng {1} trước ngày sản xuất {2}.").format(
						d.idx, d.hsd, d.ngay_san_xuat
					)
				)
```

- [ ] **Step 6: Migrate và chạy lại test**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local migrate
bench --site erptest.local run-tests --module erpnext.warehouse_operations.tests.test_nhap_lo
```
Kỳ vọng: PASS toàn bộ 9 bài của `TestValidate`.

- [ ] **Step 7: Commit**

```bash
git add erpnext/warehouse_operations/doctype/batch_entry_item/ erpnext/warehouse_operations/doctype/batch_entry/ \
        erpnext/warehouse_operations/tests/test_nhap_lo.py
git commit -m "feat(vi_tri_kho): doctype Batch Entry và các phép kiểm

..."
```

---

### Task 6: `Batch Entry` submit và cancel

**Files:**
- Modify: `erpnext/warehouse_operations/doctype/batch_entry/batch_entry.py`
- Modify: `erpnext/warehouse_operations/tests/test_nhap_lo.py`

**Interfaces:**
- Consumes: `Batch.custom_so_goi` (Task 1), `BatchEntry.validate` (Task 5).
- Produces: `BatchEntry.on_submit()` · `BatchEntry.on_cancel()`; sau submit mỗi dòng có
  `lo_da_tao` và `so_goi`, mỗi `Purchase Receipt Item` tương ứng có `batch_no`.

- [ ] **Step 1: Viết bài test trước**

Thêm vào `test_nhap_lo.py`:

```python
class TestSubmit(FrappeTestCase):
	def setUp(self):
		... # như TestValidate

	def test_submit_tao_lo_day_du(self):
		be = _phieu_nhap_lo(self.pr, [self._dong(so_lo="LO-SUBMIT-1")])
		be.insert(ignore_permissions=True)
		be.submit()
		lo = frappe.get_doc("Batch", "LO-SUBMIT-1")
		self.assertEqual(lo.item, self.item)
		self.assertEqual(str(lo.expiry_date), "2030-01-31")
		self.assertEqual(lo.supplier, self.ncc)
		self.assertEqual(lo.reference_doctype, "Purchase Receipt")
		self.assertEqual(lo.reference_name, self.pr.name)
		self.assertTrue(lo.custom_so_goi)

	def test_submit_ghi_batch_no_len_dong_phieu_nhap(self):
		be = _phieu_nhap_lo(self.pr, [self._dong(so_lo="LO-SUBMIT-2")])
		be.insert(ignore_permissions=True)
		be.submit()
		self.assertEqual(
			frappe.db.get_value("Purchase Receipt Item", self.dong_pr, "batch_no"),
			"LO-SUBMIT-2",
		)

	def test_phieu_nhap_submit_sau_do_khong_sinh_lo_may_nao_nua(self):
		"""Đây là bài chứng minh cả thiết kế chạy được.

		Nếu `batch_no` không tới được `stock_controller`, ERPNext sẽ tự sinh một
		lô theo `batch_number_series` của mặt hàng và số lô của NCC thành vô dụng
		— đúng thứ cả khối C sinh ra để tránh.
		"""
		be = _phieu_nhap_lo(self.pr, [self._dong(so_lo="LO-SUBMIT-3")])
		be.insert(ignore_permissions=True)
		be.submit()
		truoc = frappe.db.count("Batch", {"item": self.item})
		self.pr.reload()
		self.pr.submit()
		self.assertEqual(frappe.db.count("Batch", {"item": self.item}), truoc)

	def test_so_goi_khac_nhau_giua_hai_lo(self):
		"""Số gọi là thứ người ta ĐỌC CHO NHAU qua kho. Trùng nhau thì câu nói
		trỏ vào hai thùng hàng khác nhau."""
		...

	def test_dung_lai_lo_da_co_cua_chinh_mat_hang_nay(self):
		"""NCC giao làm hai đợt cùng một số lô. Không tạo mới, không nổ khoá
		chính — dùng lại, và điền HSD nếu lô cũ còn trống."""
		...

	def test_huy_khi_phieu_nhap_con_nhap_thi_go_batch_no_va_GIU_lo(self):
		"""Không xoá `Batch`: tem có thể đã in và đang dán trên thùng hàng. Xoá
		bản ghi biến tem thành rác không tra được."""
		...

	def test_huy_khi_phieu_nhap_da_submit_thi_chan(self):
		"""Tồn đã ghi theo lô. Gỡ lô khỏi một chứng từ đã submit là việc của
		`Purchase Receipt.cancel`, không phải của phiếu này."""
		...
```

Viết đủ thân của bảy bài. Ba bài cuối là chốt âm, không được bỏ.

- [ ] **Step 2: Chạy để chắc chắn nó ĐỎ**

```bash
bench --site erptest.local run-tests --module erpnext.warehouse_operations.tests.test_nhap_lo
```

- [ ] **Step 3: Viết `on_submit` / `on_cancel`**

Thêm vào lớp `BatchEntry`:

```python
	def on_submit(self):
		for d in self.items:
			lo = self._dam_bao_lo(d)
			d.db_set("lo_da_tao", lo.name, update_modified=False)
			d.db_set("so_goi", lo.custom_so_goi, update_modified=False)
			# `db_set` trên dòng chứng từ NHÁP: `Purchase Receipt` chưa submit nên
			# sửa hợp lệ, và đi thẳng xuống DB để không kích lại `validate` của cả
			# phiếu nhập (nó sẽ tính lại thuế, tỉ giá, và có thể `throw` vì một lý
			# do không liên quan gì tới việc ta đang làm).
			frappe.db.set_value(
				"Purchase Receipt Item", d.dong_phieu_nhap, "batch_no", lo.name
			)

	def _dam_bao_lo(self, d):
		"""Trả về bản ghi `Batch` cho dòng `d` — dùng lại nếu đã có.

		Dùng lại chứ không tạo mới vì NCC giao làm hai đợt cùng một số lô là
		chuyện thật. `validate` đã chặn ca số lô thuộc mặt hàng KHÁC, nên tới
		đây mà đã tồn tại thì chắc chắn là lô của chính mặt hàng này.
		"""
		if frappe.db.exists("Batch", d.so_lo):
			lo = frappe.get_doc("Batch", d.so_lo)
			# Chỉ ĐIỀN CHỖ TRỐNG, không ghi đè: lô cũ có thể đã in tem với HSD cũ.
			doi = False
			for truong, gia_tri in (("expiry_date", d.hsd), ("manufacturing_date", d.ngay_san_xuat)):
				if gia_tri and not lo.get(truong):
					lo.set(truong, gia_tri)
					doi = True
			if not lo.custom_so_goi:
				lo.custom_so_goi = _sinh_so_goi()
				doi = True
			if doi:
				lo.save(ignore_permissions=True)
			return lo

		return frappe.get_doc(
			{
				"doctype": "Batch",
				"batch_id": d.so_lo,
				"item": d.vat_tu,
				"expiry_date": d.hsd,
				"manufacturing_date": d.ngay_san_xuat,
				"supplier": self.nha_cung_cap,
				"reference_doctype": "Purchase Receipt",
				"reference_name": self.phieu_nhap,
				"custom_so_goi": _sinh_so_goi(),
			}
		).insert(ignore_permissions=True)

	def on_cancel(self):
		trang_thai = frappe.db.get_value("Purchase Receipt", self.phieu_nhap, "docstatus")
		if trang_thai != 0:
			frappe.throw(
				_(
					"Phiếu nhập {0} đã duyệt nên không huỷ phiếu nhập lô được. Tồn đã ghi "
					"theo lô rồi — muốn gỡ thì huỷ chính phiếu nhập."
				).format(self.phieu_nhap)
			)

		for d in self.items:
			# GỠ `batch_no`, GIỮ bản ghi `Batch`. Tem có thể đã in và đang dán trên
			# thùng hàng; xoá bản ghi biến tờ tem đó thành rác không tra được.
			frappe.db.set_value("Purchase Receipt Item", d.dong_phieu_nhap, "batch_no", None)
```

và ở đầu file:

```python
from frappe.model.naming import make_autoname

#: Tiền tố chỉ để `make_autoname` có khoá đếm riêng; nó bị cắt khỏi giá trị lưu.
_SERIES_SO_GOI = "SOGOI-.####"


def _sinh_so_goi() -> str:
	"""Số gọi 4 chữ số, bộ đếm TOÀN CỤC không reset theo năm.

	Không reset vì số gọi là thứ người ta đọc cho nhau qua kho. Trùng lại sau
	một năm là đủ để một câu nói trỏ vào hai thùng hàng khác nhau.

	Vượt 9999 thì số thành 5 chữ số — nhãn phải co cỡ chữ (§6.4), KHÔNG được cắt
	bớt số.
	"""
	return make_autoname(_SERIES_SO_GOI).removeprefix("SOGOI-")
```

- [ ] **Step 4: Chạy lại test**

```bash
bench --site erptest.local run-tests --module erpnext.warehouse_operations.tests.test_nhap_lo
```
Kỳ vọng: PASS.

- [ ] **Step 5: Chạy các bài kho liên quan để chắc không vỡ luồng nhập**

```bash
bench --site erptest.local run-tests --module erpnext.warehouse_operations.tests.test_hook_nhap
bench --site erptest.local run-tests --module erpnext.warehouse_operations.tests.test_pr_dn_tich_hop
bench --site erptest.local run-tests --module erpnext.warehouse_operations.tests.test_huy_chung_tu
```

- [ ] **Step 6: Commit**

---

### Task 7: API máy chủ cho màn hình và nhãn

**Files:**
- Create: `erpnext/warehouse_operations/vitri/nhap_lo.py`
- Modify: `erpnext/warehouse_operations/tests/test_nhap_lo.py`

**Interfaces:**
- Consumes: `goi_y_o(vat_tu, kho, so_lo=None)` (Task 3), `Batch.custom_o_in_tem` (Task 1).
- Produces (đều `@frappe.whitelist()`):
  - `lay_dong_tu_phieu_nhap(phieu_nhap: str) -> list[dict]` — khoá `dong_phieu_nhap`,
    `vat_tu`, `ten_hang`, `kho`, `so_luong`, `o_goi_y`, `ly_do_goi_y`
  - `du_lieu_tem(so_lo: list[str] | str) -> list[dict]` — mỗi lô một dict 11 ô F1–F11
  - `dat_o_in_tem(so_lo: str) -> str | None` — đặt `custom_o_in_tem` nếu còn trống, trả ô

- [ ] **Step 1: Viết bài test trước**

```python
class TestApiMayChu(FrappeTestCase):
	def test_lay_dong_chi_lay_mat_hang_co_lo(self):
		"""Mặt hàng không quản lý lô không có gì để khai. Lấy về là bắt thủ kho
		gõ số lô cho một thứ không có lô."""
		...

	def test_lay_dong_bo_qua_dong_da_co_batch_no(self):
		"""Chạy lại nút 'Lấy dòng' sau khi đã nhập lô một phần không được nhân
		đôi công việc đã làm."""
		...

	def test_lay_dong_dien_san_o_goi_y(self):
		...

	def test_lay_dong_khong_no_khi_mot_mat_hang_hong_du_lieu_gan(self):
		"""Ruling N của khối B, áp lại ở đây: lỗi của MỘT mặt hàng không được làm
		sập danh sách của CẢ phiếu."""
		...

	def test_du_lieu_tem_du_11_o(self):
		...

	def test_du_lieu_tem_F3_theo_so_dong_quy_doi_dvt(self):
		"""0 dòng quy đổi -> chỉ ĐVT. 1 dòng -> 'Cái (1/hộp)'. 2 dòng -> chỉ ĐVT.

		Nhiều hơn một quy cách thì không có quy cách nào ĐÚNG để in; in bừa một
		dòng là nói sai trên vật thể vật lý mà không ai đối chiếu lại."""
		...

	def test_dat_o_in_tem_lan_dau_thi_dat_lan_sau_giu_nguyen(self):
		"""In lại lần hai phải ra ĐÚNG tờ giấy như lần đầu — lần đầu có thể đã
		dán lên hàng."""
		...

	def test_dat_o_in_tem_tra_None_khi_mat_hang_chua_gan(self):
		"""F8 in 'VT —', KHÔNG đoán, và KHÔNG chặn in."""
		...
```

- [ ] **Step 2: Chạy để chắc chắn nó ĐỎ**

- [ ] **Step 3: Viết `nhap_lo.py`**

Yêu cầu bắt buộc với người thi công:

1. **Kiểm quyền** ở mọi hàm whitelist, theo đúng khuôn `xep.py:20-28`
   (`@frappe.whitelist()` một mình chỉ chặn khách vãng lai; các hàm này lộ tồn kho
   theo ô). Dùng lại bộ vai trò `{"System Manager", "Stock Manager", "Stock User"}`.
2. `lay_dong_tu_phieu_nhap` bọc **mỗi** lời gọi `goi_y_o` trong `try/except Exception`
   + `frappe.log_error`, y như `xep.py:74-98` (Ruling N). Chép lý do vào chú thích,
   đừng chỉ chép mã.
3. `du_lieu_tem` trả **dữ liệu đã định dạng sẵn**, không trả bản ghi thô: ngày đã
   `YYYY/MM/DD`, F8 đã qua `ma_vi_tri.dinh_dang_nhan()`, F3 đã ghép theo §6.3. JS chỉ
   còn việc đặt chữ vào ô. Trộn định dạng vào JS là mở đường cho nhãn in và màn hình
   xem trước nói khác nhau.
4. `du_lieu_tem` **không** gọi `dat_o_in_tem`. Hai việc tách nhau: xem trước không được
   ghi dữ liệu.
5. Ô F8 khi `custom_o_in_tem` trống và `goi_y_o` trả `None` → chuỗi `"VT —"`.

- [ ] **Step 4: Chạy lại test.** Kỳ vọng: PASS.

- [ ] **Step 5: Commit**

---

### Task 8: Nhãn lô 50×30 — `tem_lo.js`

**Files:**
- Create: `erpnext/public/js/warehouse_operations/tem_lo.js`
- Modify: `erpnext/public/js/warehouse_operations/tem_vi_tri.js` (thêm `ve_tho()` vào
  `may_ve_ma_vach`, xem Step 2 — **thêm**, không đổi `ve()`)

**Interfaces:**
- Consumes: `erpnext.warehouse_operations.tem.may_ve_ma_vach()` (đã export sẵn ở
  `tem_vi_tri.js:136`, dòng cuối file), `nhap_lo.du_lieu_tem` (Task 7).
- Produces: `erpnext.warehouse_operations.tem_lo` = `{ KHO, X_MM, YEN_TINH_MM, TRAN_VE_DUOC, TRAN_YEN_TINH, so_module, ke_hoach_vach, ve_tem, css, ve_xem_truoc, in_xap }`.
  **ĐÍNH CHÍNH 16/09 (sau thi công Task 8): `chon_bo_cuc` KHÔNG tồn tại** — chủ đầu tư
  đã chốt bỏ hẳn bố cục A, nhãn chỉ còn MỘT bố cục. `css(cho_in)` một tham số,
  `ve_tem(o, hinh_vach)` hai tham số.

- [ ] **Step 1: Đọc `tem_vi_tri.js` từ đầu đến cuối trước khi viết một dòng nào**

File đó mang ba luật CSS mà mỗi luật là một lỗi đã trả giá, có chú thích ngay tại chỗ:
`flex: 0 0 auto` trên khối mã vạch (chặn mã vạch co lại trong im lặng), `min-width: 0`
trên cột chữ (chặn dữ liệu dị dạng ăn mất bề rộng), và cặp
`preserveAspectRatio="none"` + `displayValue: false` (hai thiết lập đi kèm nhau).
Chép lại cả luật lẫn lý do.

- [ ] **Step 2: Chọn bố cục bằng SỐ MODULE ĐO ĐƯỢC, không phải ước lượng**

Đây là điểm kỹ thuật cốt lõi của task. `may_ve_ma_vach().ve(ma, k)` đặt bề rộng SVG
theo `k.vach_rong` **mm** kèm `preserveAspectRatio="none"` — tức nó **kéo giãn** mã vạch
cho vừa bề rộng yêu cầu, bất kể mã dài bao nhiêu. Nhồi một mã 13 ký tự vào 28 mm sẽ ra
mã có module hẹp hơn 2 dot, và **máy quét đọc ra sai ký tự**.

Nên phải đo trước khi vẽ. JsBarcode dựng SVG với `width: 2` px mỗi module và `margin: 0`,
nên số module đọc thẳng ra được từ bề rộng px của SVG:

```javascript
	/** Số module Code 128 của `ma`, ĐO từ SVG do JsBarcode dựng.
	 *
	 * Không tự cài đặt lại phép đếm ở JS: `vitri/ma_vach.py` đã có một bản cho
	 * phía máy chủ, và hai bản cài đặt của cùng một phép tính thì một ngày nào
	 * đó `validate` cho qua một số lô mà nhãn không vẽ nổi — phát hiện ra lúc
	 * tem đã in. Đo từ chính thứ sẽ được in ra là nguồn sự thật duy nhất.
	 *
	 * `width: 2` ở `may_ve_ma_vach` nghĩa là mỗi module rộng 2 px, `margin: 0`
	 * nghĩa là không có lề cộng thêm. Nên module = bề rộng px / 2.
	 */
	function so_module(may, ma) {
		const svg = may.ve_tho(ma); // trả SVG gốc chưa đổi đơn vị
		return Math.round((parseFloat(svg.getAttribute("width")) || 0) / 2);
	}
```

`may_ve_ma_vach()` hiện **không** export SVG thô — nó serialize luôn sang mm. Task này
phải **thêm** một hàm `ve_tho(ma)` vào đối tượng trả về của `may_ve_ma_vach` trong
`tem_vi_tri.js` (thêm, không đổi `ve()`), và khẳng định trong chú thích rằng tem vị trí
không dùng tới nó.

Quy tắc chọn:

| Số module | Bố cục |
|---|---|
| ≤ 112 | A |
| ≤ 188 | B |
| > 188 | không xảy ra — `validate` đã chặn. Nếu vẫn tới đây (in từ một lô cũ tạo trước khối C) thì dùng B và `frappe.msgprint` cảnh báo mã có thể không quét được |

- [ ] **Step 3: Dựng hằng số hai bố cục**

```javascript
	const KHO = {
		rong: 50, cao: 30, le: 1.5,      // vùng in an toàn 47 × 27
		A: {
			hang: [5.0, 4.5, 3.5, 3.5, 3.5, 7.0],   // = 27,0
			cot_trai: 29.4, gap: 0.6, cot_phai: 17.0,
			vach_rong: 28.0, vach_cao: 5.0,
			co: { f1: 11, f2: 9, f3: 6.5, f4: 6.5, f5: 8, f6: 7, f7: 6.5, f8: 7, f9: 22, f11: 5 },
		},
		B: {
			hang: [4.5, 4.0, 3.0, 3.0, 3.0, 3.0, 6.5], // = 27,0
			cot_trai: 29.4, gap: 0.6, cot_phai: 17.0,
			vach_rong: 47.0, vach_cao: 4.8,
			co: { f1: 11, f2: 9, f3: 6.5, f4: 6.5, f5: 8, f6: 7, f7: 6.5, f8: 7, f9: 16, f11: 5 },
		},
	};
```

Mỗi mảng `hang` phải cộng đúng 27,0. Viết một `console.assert` ngay dưới khối này —
nếu ai đó chỉnh một con số mà quên chỉnh con số bù lại, nhãn sẽ tràn ra ngoài giấy và
**không có lỗi nào báo**, chỉ là chữ bị cắt.

- [ ] **Step 4: Viết `ve_tem`, `css`, `ve_xem_truoc`, `in_xap`**

Theo đúng khuôn các hàm cùng tên trong `tem_vi_tri.js`. `in_xap` mở một cửa sổ, mỗi lô
một nhãn.

- [ ] **Step 5: Kiểm trên trình duyệt — bắt buộc, không test Python nào thay được**

Mở `192.168.61.129:8003`, đăng nhập, dùng console:

1. Vẽ nhãn ở **kích thước thật** (không phóng to) cho ba số lô: `25L4125` (bố cục A),
   `LOT-2026-A45` (bố cục B), và một lô 5 chữ số gọi.
2. Đo **từng ô** bằng `Range` chứ không phải `scrollWidth`. `scrollWidth` **mù với tràn
   ở giữa** — đây là lỗi đã mắc một lần khi làm tem vị trí và suýt cho qua một nhãn hỏng.
3. Khẳng định: không ô nào vượt khỏi 47 × 27 mm; bề rộng SVG mã vạch đúng 28,0 mm
   (bố cục A) và 47,0 mm (bố cục B); số gọi 5 chữ số không tràn khung F9.
4. **Mỗi khổ một trang riêng.** Đặt `<style>` của hai bố cục trên cùng một trang thì
   bộ thứ hai đè bộ thứ nhất — cũng là lỗi đã mắc một lần.

Chụp màn hình lưu vào `/tmp/claude-*/scratchpad/`, dẫn đường dẫn trong báo cáo.

- [ ] **Step 6: Commit**

---

### Task 9: Màn hình — `batch_entry.js` và nút in trên form `Batch`

**Files:**
- Create: `erpnext/warehouse_operations/doctype/batch_entry/batch_entry.js`
- Create: `erpnext/public/js/warehouse_operations/batch.js`
- Modify: `erpnext/hooks.py` (`doctype_js`)

**Interfaces:**
- Consumes: `nhap_lo.lay_dong_tu_phieu_nhap` · `nhap_lo.du_lieu_tem` ·
  `nhap_lo.dat_o_in_tem` (Task 7); `erpnext.warehouse_operations.tem_lo` (Task 8);
  `quet.tra_cuu` (Task 10 — nút quét nối ở Task 10, không phải ở đây).
- Produces: nút "Lấy dòng hàng từ phiếu nhập" (khi nháp), "In nhãn cả phiếu" (sau
  submit) trên `Batch Entry`; nút "In nhãn" trên `Batch`.

- [ ] **Step 1: `batch_entry.js`** — theo khuôn `location_transfer.js`:
  - `refresh`: `docstatus === 0` → nút "Lấy dòng hàng từ phiếu nhập";
    `docstatus === 1` → nút "In nhãn cả phiếu".
  - `phieu_nhap` đổi → xoá bảng con kèm `show_alert` giải thích (khuôn `kho(frm)` ở
    `location_transfer.js:19-29`).
  - Tóm tắt các dòng không có `o_goi_y`, **gộp theo `ly_do_goi_y` thật** — Ruling O của
    khối B, chú thích đã ghi đầy đủ lý do ở `location_transfer.js`, chép cả lý do.
  - `frappe.require("/assets/erpnext/js/warehouse_operations/tem_lo.js")` trước khi in
    (tiền lệ `timesheet.js:3`) — **không** thêm vào `app_include_js` trong `hooks.py`:
    nhãn chỉ dùng ở hai màn hình, nạp cho mọi trang là bắt cả hệ trả giá.

- [ ] **Step 2: `batch.js`** — nút "In nhãn" trên form `Batch`, chỉ hiện khi
  `frm.doc.item` có `has_batch_no`. Gọi `dat_o_in_tem` rồi `du_lieu_tem` rồi
  `tem_lo.in_xap`.

- [ ] **Step 3: `hooks.py`** — thêm `"Batch": "public/js/warehouse_operations/batch.js"` vào
  `doctype_js` (tiền lệ `"Warehouse"` ở dòng 44). **Kiểm khoá trùng trước khi thêm.**

- [ ] **Step 4: `bench build --app erpnext` rồi kiểm trên trình duyệt**

Luồng thật, từ đầu tới cuối, trên `192.168.61.129:8003`:
tạo phiếu nhập nháp → tạo `Batch Entry` → "Lấy dòng" → gõ lô + HSD → submit →
"In nhãn cả phiếu" → kiểm cửa sổ in → submit phiếu nhập → mở phiếu xếp, khẳng định
`den_o` bằng đúng ô đã in trên tem.

Đây là bài kiểm **duy nhất** chứng minh cả khối C chạy được. Không bỏ.

- [ ] **Step 5: Commit**

---

### Task 10: Quét mã tra cứu

**Files:**
- Create: `erpnext/warehouse_operations/vitri/quet.py`
- Create: `erpnext/warehouse_operations/tests/test_quet.py`
- Modify: `erpnext/warehouse_operations/doctype/batch_entry/batch_entry.js`

**Interfaces:**
- Consumes: `erpnext.stock.utils.scan_barcode` (KHÔNG sửa), `Item Location Preference`,
  `Location Balance`.
- Produces: `@frappe.whitelist() tra_cuu(ma: str) -> dict`.

- [ ] **Step 1: Viết bài test trước**

```python
class TestTraCuu(FrappeTestCase):
	def test_quet_so_lo_ra_du_thong_tin(self):
		"""11 khoá: ten_hang, hsd, ngay_san_xuat, nha_cung_cap, so_goi, ngay_nhap,
		so_phieu_nhap, vi_tri_co_dinh, o_dang_co_hang, o_in_tem, ton_theo_o."""
		...

	def test_quet_ma_khong_ton_tai_thi_tra_rong_chu_khong_no(self):
		"""Thủ kho quét nhầm một mã bất kỳ trong kho. Nổ ra traceback giữa màn
		hình nhập liệu là cách nhanh nhất để họ thôi dùng chức năng này."""
		...

	def test_quet_ma_vat_tu_thi_tra_ve_mat_hang_khong_gia_vo_la_lo(self):
		"""`scan_barcode` phân giải cả Item Barcode. Trả về phải nói rõ LOẠI, vì
		màn hình hiển thị khác nhau cho lô và cho mặt hàng."""
		...

	def test_khong_co_vai_tro_kho_thi_bi_chan(self):
		"""Hàm này lộ tồn kho theo ô — đăng nhập hợp lệ không phải điều kiện đủ.
		Khuôn `xep._kiem_tra_quyen()`."""
		...
```

- [ ] **Step 2: Chạy để chắc chắn nó ĐỎ**

- [ ] **Step 3: Viết `quet.py`** — bọc ngoài, tuyệt đối không sửa `scan_barcode`.
  Trả về phải có khoá `loai` (`"lo"` / `"vat_tu"` / `"kho"` / `None`) để màn hình biết
  hiển thị gì.

- [ ] **Step 4: Nối ô quét vào `batch_entry.js`** — dùng
  `erpnext.utils.BarcodeScanner` sẵn có; kết quả đổ vào một khung `frm.dashboard`
  dưới bảng con.

- [ ] **Step 5: Chạy lại test + kiểm trên trình duyệt** bằng bàn phím giả lập
  (máy quét mã vạch nhập như bàn phím: gõ nhanh rồi Enter).

- [ ] **Step 6: Commit**

---

### Task 11: Workspace, chạy toàn bộ test, và HDSD

**Files:**
- Modify: `erpnext/warehouse_operations/workspace/vị_trí_kho.json`
- Modify: `docs/warehouse_operations/HDSD-quan-ly-vi-tri-kho.md`

- [ ] **Step 1: Thêm lối vào workspace**

`Batch Entry` phải có mặt trong workspace `Vị trí kho`. Khối B đã mắc đúng lỗi này một
lần: chức năng chạy đúng nhưng **không có đường nào vào** từ giao diện, và chỉ phát hiện
khi mở trình duyệt. `vi_tri_kho/tests/test_giao_dien.py` khoá việc này — đọc nó trước,
và **thêm bài cho `Batch Entry`** vào đó.

- [ ] **Step 2: Chạy TOÀN BỘ test của module, tuần tự**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
for m in $(ls apps/erpnext/erpnext/warehouse_operations/tests/test_*.py | xargs -n1 basename | sed 's/\.py$//'); do
	echo "=== $m ==="
	bench --site erptest.local run-tests --module erpnext.warehouse_operations.tests.$m || echo "ĐỎ: $m"
done
```

Mọi module phải xanh. Một module đỏ là một task chưa xong, không phải một ghi chú.

- [ ] **Step 3: Kiểm dữ liệu không rò ra CSDL thật**

Sau khi chạy xong, khẳng định không còn bản ghi thử nào sót lại:

```bash
bench --site erptest.local console <<'PY'
import frappe
for dt, loc in (("Batch", "_TEST"), ("Batch", "LO-"), ("Batch Entry", None), ("Item", "_Test NhapLo")):
	print(dt, loc, frappe.db.count(dt, {"name": ["like", f"{loc}%"]} if loc else {}))
PY
```

`FrappeTestCase` rollback theo **LỚP**, không theo từng phương thức, và dự án đã có
tiền lệ rò dữ liệu qua `commit()` tường minh và qua DDL tự commit. Nếu có bản ghi sót,
tìm ra bài nào rò **trước khi** dọn — dọn mà không biết nguồn thì lần sau rò tiếp.

- [ ] **Step 4: Viết HDSD**

Thêm một mục mới vào `docs/warehouse_operations/HDSD-quan-ly-vi-tri-kho.md`, viết cho **thủ kho**
chứ không cho lập trình viên:

1. Thứ tự bắt buộc: **nhập lô trước, duyệt phiếu nhập sau**, và điều gì xảy ra nếu làm
   ngược (số lô của NCC mất, ERPNext sinh số lô máy). Đây là rủi ro §12 mà hệ **không
   chặn được** từ phía phiếu nhập — tài liệu là lớp phòng vệ duy nhất.
2. Một mặt hàng về hai lô thì tách dòng trên phiếu nhập.
3. Ý nghĩa 11 ô trên nhãn, kèm ảnh mockup.
4. Khi nào nhãn nói sai vị trí và phải làm gì (dán đè tem mới) — §8.
5. Số lô dài quá thì hệ báo gì và phải làm gì.

- [ ] **Step 5: Commit**

---

## Self-review của kế hoạch

**Phủ spec:**

| Mục spec | Task |
|---|---|
| §4.1 dùng lại `Batch` | 5, 6 |
| §4.2 ba custom field | 1 |
| §4.3 móc điền NCC | 1 |
| §4.4 số gọi | 6 |
| §4.5 HSD do ERPNext chặn | — (không viết mã; bài `test_submit_tao_lo_day_du` xác nhận HSD tới nơi) |
| §5.1–5.2 lược đồ | 5 |
| §5.3 luồng | 6, 9 |
| §5.4 một dòng một lô | 5 |
| §5.5 `validate` | 5 |
| §5.6 huỷ | 6 |
| §6.1–6.3 nhãn | 7 (dữ liệu), 8 (vẽ) |
| §6.4 trần mã vạch, hai bố cục | 2 (đếm), 5 (chặn), 8 (chọn bố cục) |
| §6.5 in | 7, 8, 9 |
| §7 quét mã | 10 |
| §8 ô đã in tem | 3 |
| §8.1 đệm theo lô | 4 |
| §9 thay đổi mã sẵn có | 1, 3, 4, 9, 11 |
| §10 quyền | 5 (doctype), 7 và 10 (hàm whitelist) |
| §11 kiểm thử | mọi task |

Không mục nào của spec thiếu task.

**Nhất quán kiểu:**
- `goi_y_o(vat_tu, kho, so_lo=None)` — Task 3 định nghĩa, Task 4 và 7 gọi. Khớp.
- `so_module` có **hai** bản: `vitri/ma_vach.py` (Python, cho `validate`) và một hàm
  cùng tên trong `tem_lo.js` (JS, **đo** từ SVG chứ không tính lại). Đây là trùng tên
  CÓ CHỦ Ý và Task 8 Step 2 ghi rõ vì sao — bản JS đo từ chính thứ sẽ in ra.
- `du_lieu_tem` trả dữ liệu **đã định dạng**; `tem_lo.js` không định dạng lại gì.

**Thứ tự phụ thuộc:** 1 → 2 → 3 → 4, rồi 5 → 6 → 7 → 8 → 9, rồi 10, rồi 11.
Task 4 không chặn Task 5; chạy tuần tự vì cả bộ dùng chung một CSDL.

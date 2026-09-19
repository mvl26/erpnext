# Gán vị trí cố định theo mặt hàng — kế hoạch thi công

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mỗi mặt hàng có một chỗ cố định trên kệ, và hệ trả lời được "hàng này xếp vào ô nào" mà không cần biết sức chứa.

**Architecture:** Một doctype `Item Location Preference` khoá chính là mã mặt hàng (`autoname: field:vat_tu`), trỏ tới **một** nút `Storage Location` ở bất kỳ cấp nào — gán nút nhóm nghĩa là cả nhánh dưới nó. Ràng buộc "một ô một chủ" cưỡng chế bằng vị từ **giao nhau** trên `lft`/`rgt` của nested set. Hàm `goi_y_o()` duyệt ô lá trong nhánh theo `lft` tăng dần, trả ô trống đầu tiên; hết ô trống thì dồn vào ô đang chứa chính mặt hàng đó.

**Tech Stack:** Frappe v15 · ERPNext fork Miyano · MariaDB · `frappe.ui.Tree` · raw `frappe.db.sql` (theo đúng lối module `vi_tri_kho` đang dùng)

**Spec:** `docs/superpowers/specs/2026-09-15-gan-vi-tri-co-dinh-theo-mat-hang-design.md`

## Global Constraints

- **Python thụt bằng TAB**, dòng ≤ 110 ký tự, chuỗi dùng nháy kép. Khớp file xung quanh.
- **Không có `ruff`/`prettier`/`pre-commit` trên máy này.** Kiểm tay hai điều trên.
- Chạy test: `bench --site erptest.local run-tests --module erpnext.vi_tri_kho.tests.<tên>` từ bench root `/home/hoangvietyeuem/frappe-bench-yhct`. **Không** dùng `--app erpnext`.
- **Chạy TUẦN TỰ.** Ba bench chung một máy; chạy song song cho kết quả giả. `FAILED` mà không có dòng `Ran N tests`, hoặc module thuần hàm cũng đỏ → là `ReadTimeout` do hết RAM, chạy lại từng cái.
- Trước khi commit: `python3 -m scripts.file_structure --audit` phải ra `0 vi pham`.
- Test đặt ở `erpnext/vi_tri_kho/tests/`, **không** đặt trong thư mục doctype (module này theo lối `tests/`).
- Nhánh `feat/mo-rong-vi-tri-kho-warehouse`. Commit thường xuyên, mỗi task một commit.
- Kho thử: `Kho Miyano - MYN`. Mã ô 10 ký tự `[0-9][A-Z]` + 8 chữ số; Tầng chỉ nhận `01`–`09`.
- Sau khi sửa `.json` của doctype: `bench --site erptest.local migrate`.

---

## Bản đồ file

| File | Trách nhiệm |
|---|---|
| `erpnext/vi_tri_kho/doctype/item_location_preference/item_location_preference.json` | lược đồ |
| `…/item_location_preference.py` | 4 phép kiểm khi lưu |
| `…/item_location_preference.js` | nút mở cây chọn vị trí |
| `erpnext/vi_tri_kho/vitri/gan.py` | truy vấn dùng chung về gán (ai giữ nút này, nhánh nào của mặt hàng nào) + móc `after_rename` |
| `erpnext/vi_tri_kho/vitri/goi_y.py` | `goi_y_o()` — thuật toán gợi ý |
| `erpnext/public/js/vi_tri_kho/cay_chon_vi_tri.js` | dialog cây, dùng chung |
| `erpnext/vi_tri_kho/report/hang_nam_sai_vi_tri/` | báo cáo soi hàng nằm sai |
| `erpnext/vi_tri_kho/vitri/xep.py` | **sửa**: điền `den_o` |
| `erpnext/hooks.py` | **sửa**: 1 dòng `doc_events["Item"]["after_rename"]` |
| `erpnext/vi_tri_kho/tests/test_gan_vi_tri.py` | Task 1–4 |
| `erpnext/vi_tri_kho/tests/test_goi_y_o.py` | Task 5–6 |
| `erpnext/vi_tri_kho/tests/test_app_khoi_dong.py` | **sửa**: khoá móc mới |
| `erpnext/vi_tri_kho/tests/test_bao_cao.py` | **sửa**: thêm bài cho báo cáo mới |

**Vì sao `gan.py` tách khỏi controller:** ba nơi cần hỏi "nút này ai đang giữ" — `validate()` của chính doctype, cây chọn (Task 7), và báo cáo (Task 8). Để trong controller thì hai nơi kia phải `frappe.get_doc` một bản ghi chỉ để gọi một hàm thuần truy vấn.

---

## Task 1: DocType + hai phép kiểm rẻ

**Files:**
- Create: `erpnext/vi_tri_kho/doctype/item_location_preference/__init__.py`
- Create: `erpnext/vi_tri_kho/doctype/item_location_preference/item_location_preference.json`
- Create: `erpnext/vi_tri_kho/doctype/item_location_preference/item_location_preference.py`
- Create: `erpnext/vi_tri_kho/tests/test_gan_vi_tri.py`

**Interfaces:**
- Consumes: `erpnext.vi_tri_kho.vitri.ma_vi_tri.cap_do`, `TEN_CAP`; `erpnext.vi_tri_kho.vitri.kho.kho_co_quan_ly_vi_tri`
- Produces: DocType `Item Location Preference` với `name == vat_tu`; class `ItemLocationPreference`

- [ ] **Step 1: Viết bài test đỏ**

Tạo `erpnext/vi_tri_kho/tests/test_gan_vi_tri.py`:

```python
"""Gán vị trí cố định cho mặt hàng: một mặt hàng một nút, một ô một chủ.

Bất biến đắt nhất ở đây KHÔNG phải "lưu được": nó là **một ô chỉ thuộc về
một mặt hàng**. Hỏng bất biến đó thì hai mặt hàng cùng được gợi ý vào một ô,
thủ kho xếp chồng lên nhau, và không có gì báo — đối soát §3 chỉ so TỔNG nên
vẫn khớp tuyệt đối.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

KHO = "Kho Miyano - MYN"


def _o(ma_o, **kw):
	"""Nút vị trí (mọi cấp). Nút cha tự sinh theo tiền tố của mã."""
	if not frappe.db.exists("Storage Location", ma_o):
		frappe.get_doc({"doctype": "Storage Location", "ma_o": ma_o, "kho": KHO, **kw}).insert(
			ignore_permissions=True
		)
	return ma_o


def _mat_hang(ma):
	if not frappe.db.exists("Item", ma):
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": ma,
				"item_name": ma,
				"item_group": "All Item Groups",
				"stock_uom": "Nos",
				"is_stock_item": 1,
			}
		).insert(ignore_permissions=True)
	return ma


def _gan(vat_tu, vi_tri, kho=KHO):
	return frappe.get_doc(
		{"doctype": "Item Location Preference", "vat_tu": vat_tu, "kho": kho, "vi_tri": vi_tri}
	).insert(ignore_permissions=True)


class _Nen(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.o1 = _o("7A01010101")  # tạo luôn cả nhánh cha 7A / 7A01 / 7A0101 / 7A010101
		cls.tang = "7A010101"
		cls.o2 = _o("7A01010102")
		cls.vt_a = _mat_hang("_Test Gan VT A")
		cls.vt_b = _mat_hang("_Test Gan VT B")


class TestLuocDo(_Nen):
	def test_ten_ban_ghi_chinh_la_ma_mat_hang(self):
		"""`autoname: field:vat_tu` là thứ giữ bất biến "một mặt hàng một nút".

		Nếu ai đó đổi sang `hash` hay `naming_series`, phép kiểm trùng lặp tụt
		xuống thành một dòng trong `validate()` — mà Data Import và REST đi
		vòng được. Khoá ở đây để đổi lược đồ là đỏ ngay.
		"""
		d = _gan(self.vt_a, self.o1)
		self.assertEqual(d.name, self.vt_a)

	def test_mot_mat_hang_khong_gan_duoc_hai_lan(self):
		_gan(self.vt_a, self.o1)
		with self.assertRaises(frappe.DuplicateEntryError):
			_gan(self.vt_a, self.o2)

	def test_cap_do_tu_dien_theo_ma(self):
		self.assertEqual(_gan(self.vt_a, self.o1).cap_do, "Ô")
		self.assertEqual(_gan(self.vt_b, "7A010101").cap_do, "Tầng")


class TestChanNutKhongHopLe(_Nen):
	def test_chan_o_chua_xep(self):
		"""`ZZZ-CHUA-XEP` là ô ẢO. Gán vào đó thì gợi ý sẽ trỏ về đúng chỗ mà
		phiếu xếp đang cố đưa hàng RA — vòng tròn không lối thoát."""
		zzz = frappe.db.get_value("Storage Location", {"la_o_chua_xep": 1, "kho": KHO}, "name")
		self.assertIsNotNone(zzz)
		with self.assertRaises(frappe.ValidationError):
			_gan(self.vt_a, zzz)

	def test_chan_nut_thuoc_kho_khac(self):
		kho_khac = frappe.db.get_value("Warehouse", {"name": ("!=", KHO), "is_group": 0}, "name")
		self.assertIsNotNone(kho_khac)
		with self.assertRaises(frappe.ValidationError):
			_gan(self.vt_a, self.o1, kho=kho_khac)

	def test_chan_nut_dang_ngung_dung(self):
		frappe.db.set_value("Storage Location", self.o1, "disabled", 1)
		try:
			with self.assertRaises(frappe.ValidationError):
				_gan(self.vt_a, self.o1)
		finally:
			frappe.db.set_value("Storage Location", self.o1, "disabled", 0)

	def test_chan_nut_co_to_tien_ngung_dung(self):
		"""Tắt cả một Tầng để sửa kệ, rồi gán vào Ô bên dưới nó.

		Chốt âm của bài trên: một bản chỉ kiểm `sl.disabled` của CHÍNH nút vẫn
		làm bài trên xanh, nhưng để lọt ca này — và gợi ý sẽ trỏ vào chỗ không
		ai được đụng tới.
		"""
		frappe.db.set_value("Storage Location", "7A010101", "disabled", 1)
		try:
			with self.assertRaises(frappe.ValidationError):
				_gan(self.vt_a, self.o1)
		finally:
			frappe.db.set_value("Storage Location", "7A010101", "disabled", 0)


class TestBayToaDoRong(_Nen):
	def test_nut_ngoai_cay_bi_tu_choi(self):
		"""Cùng hình dạng bẫy đã trả giá ở `fefo.py` và `tem.py`.

		Bản ghi chưa hội tụ mang `lft = rgt = 0`. Cho qua thì vị từ giao nhau ở
		Task 2 thành `0 … 0` và khớp MỌI bản ghi 0/0 khác toàn hệ — gán tưởng
		của Tầng này lại bị chặn bởi nút của kho khác.
		"""
		frappe.db.set_value("Storage Location", self.o1, {"lft": 0, "rgt": 0}, update_modified=False)
		with self.assertRaises(frappe.ValidationError):
			_gan(self.vt_a, self.o1)
```

- [ ] **Step 2: Chạy để chắc chắn nó ĐỎ**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local run-tests --module erpnext.vi_tri_kho.tests.test_gan_vi_tri
```

Kỳ vọng: đỏ với `DoesNotExistError: DocType Item Location Preference not found`.

- [ ] **Step 3: Tạo `__init__.py` rỗng và lược đồ**

`erpnext/vi_tri_kho/doctype/item_location_preference/__init__.py` — file rỗng.

`item_location_preference.json`:

```json
{
 "actions": [],
 "autoname": "field:vat_tu",
 "creation": "2026-09-15 00:00:00.000000",
 "doctype": "DocType",
 "editable_grid": 0,
 "engine": "InnoDB",
 "field_order": ["vat_tu", "kho", "col_1", "vi_tri", "cap_do", "sec_gc", "ghi_chu"],
 "fields": [
  {"fieldname": "vat_tu", "fieldtype": "Link", "label": "Mặt hàng", "options": "Item",
   "reqd": 1, "unique": 1, "in_list_view": 1, "set_only_once": 1},
  {"fieldname": "kho", "fieldtype": "Link", "label": "Kho", "options": "Warehouse",
   "reqd": 1, "in_list_view": 1},
  {"fieldname": "col_1", "fieldtype": "Column Break"},
  {"fieldname": "vi_tri", "fieldtype": "Link", "label": "Vị trí cố định",
   "options": "Storage Location", "reqd": 1, "in_list_view": 1,
   "description": "Nút bất kỳ cấp nào. Chọn một Tầng nghĩa là cả nhánh dưới nó thuộc mặt hàng này."},
  {"fieldname": "cap_do", "fieldtype": "Data", "label": "Cấp", "read_only": 1,
   "description": "Suy từ mã vị trí. Chỉ để nhìn — không truy vấn nào được lọc theo trường này."},
  {"fieldname": "sec_gc", "fieldtype": "Section Break"},
  {"fieldname": "ghi_chu", "fieldtype": "Small Text", "label": "Ghi chú"}
 ],
 "index_web_pages_for_search": 0,
 "links": [],
 "modified": "2026-09-15 00:00:00.000000",
 "modified_by": "Administrator",
 "module": "Vi Tri Kho",
 "name": "Item Location Preference",
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

`set_only_once: 1` trên `vat_tu`: `name` đã chốt lúc insert, cho sửa trường là mở đường cho `name` và `vat_tu` lệch nhau — đúng bẫy `_sync_autoname_field()` mà Task 4 xử.

- [ ] **Step 4: Viết controller — hai phép kiểm rẻ**

`item_location_preference.py`:

```python
"""Gán MỘT mặt hàng vào MỘT nút vị trí. Nút nhóm = cả nhánh dưới nó.

Bất biến trung tâm: **một ô chỉ thuộc về một mặt hàng**. Nó được giữ ở hai
tầng khác nhau, cố ý:

1. "Một mặt hàng một nút" — do `autoname: field:vat_tu`, tức KHOÁ CHÍNH của
   bảng. Data Import, `frappe.db.set_value` và đường REST đều không đi vòng
   được một khoá chính; chúng đi vòng được một dòng trong `validate()`.
2. "Một nút một chủ" — do `kiem_tra_chong_lan()` dưới đây, vì nested set
   không có cách nào biểu diễn "hai nhánh không giao nhau" bằng ràng buộc DB.

Thứ tự phép kiểm trong `validate()` là CỐ Ý: rẻ trước, và mỗi phép kiểm sau
dựa vào tiền đề phép kiểm trước đã lập. Cụ thể `kiem_tra_trong_cay()` phải
chạy TRƯỚC mọi thứ đọc `lft`/`rgt` — xem docstring của nó.
"""

import frappe
from frappe import _
from frappe.model.document import Document

from erpnext.vi_tri_kho.vitri.kho import kho_co_quan_ly_vi_tri
from erpnext.vi_tri_kho.vitri.ma_vi_tri import TEN_CAP, cap_do


class ItemLocationPreference(Document):
	def validate(self):
		self.nut = self._doc_nut()
		self.kiem_tra_trong_cay()
		self.kiem_tra_nut_hop_le()
		self.cap_do = TEN_CAP[cap_do(self.vi_tri) - 1]

	def _doc_nut(self):
		nut = frappe.db.get_value(
			"Storage Location",
			self.vi_tri,
			["name", "kho", "lft", "rgt", "disabled", "la_o_chua_xep"],
			as_dict=True,
		)
		if not nut:
			frappe.throw(_("Vị trí {0} không tồn tại.").format(self.vi_tri))
		return nut

	def kiem_tra_trong_cay(self):
		"""Nút phải có toạ độ thật trong cây.

		BẪY ĐÃ TRẢ GIÁ HAI LẦN trong chính module này (`fefo.py::pham_vi`,
		`tem.py::goc`). Bản ghi chưa hội tụ mang `lft = rgt = 0`; cho qua thì
		vị từ giao nhau ở `kiem_tra_chong_lan()` thành `0 … 0` và khớp MỌI bản
		ghi 0/0 khác TRÊN TOÀN HỆ, kể cả của kho khác — gán một Tầng lại báo
		đụng một nút hoàn toàn không liên quan, hoặc tệ hơn, chặn oan cả loạt.

		Chặn ở NGUỒN, không vá bằng vị từ chặt hơn: ở đây so chính toạ độ của
		`vi_tri`, mà toạ độ đó mới là thứ hỏng.
		"""
		if not self.nut.lft or not self.nut.rgt:
			frappe.throw(
				_(
					"Vị trí {0} chưa có toạ độ trong cây vị trí nên chưa gán được. "
					"Mở vị trí đó và lưu lại để cây tính lại toạ độ, hoặc chạy "
					"`bench migrate`, rồi thử lại."
				).format(self.vi_tri)
			)

	def kiem_tra_nut_hop_le(self):
		if not kho_co_quan_ly_vi_tri(self.kho):
			frappe.throw(_("Kho {0} chưa bật quản lý vị trí.").format(self.kho))

		if self.nut.kho != self.kho:
			frappe.throw(
				_("Vị trí {0} thuộc kho {1}, không phải {2}.").format(
					self.vi_tri, self.nut.kho, self.kho
				)
			)

		if self.nut.la_o_chua_xep:
			frappe.throw(
				_(
					"{0} là ô hệ thống (hàng chờ xếp), không phải kệ thật — không gán "
					"mặt hàng vào đó được. Chọn một ô hoặc tầng trên cây vị trí."
				).format(self.vi_tri)
			)

		tat = self._to_tien_tat()
		if tat:
			frappe.throw(
				_(
					"Vị trí {0} đang ngừng dùng (do chính nó hoặc do {1} ở trên nó). "
					"Gợi ý sẽ trỏ vào chỗ không ai được đụng tới. Bật lại rồi gán."
				).format(self.vi_tri, tat)
			)

	def _to_tien_tat(self) -> str | None:
		"""Tên nút `disabled` gần nhất: chính nó, hoặc một tổ tiên.

		Kiểm CẢ TỔ TIÊN chứ không chỉ cờ của chính nút — người vận hành tắt cả
		một Dãy để sửa kệ thì mọi ô dưới đó cũng không dùng được, dù cờ của
		từng ô vẫn bằng 0. Cùng luật với `fefo._TO_TIEN_TAT`.
		"""
		dong = frappe.db.sql(
			"""
			select tt.name
			from `tabStorage Location` tt
			where ifnull(tt.disabled, 0) = 1
			  and (tt.name = %(nut)s or (tt.lft < %(lft)s and tt.rgt > %(rgt)s))
			order by tt.lft asc
			limit 1
			""",
			{"nut": self.vi_tri, "lft": self.nut.lft, "rgt": self.nut.rgt},
		)
		return dong[0][0] if dong else None
```

- [ ] **Step 5: Migrate rồi chạy test**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local migrate
bench --site erptest.local run-tests --module erpnext.vi_tri_kho.tests.test_gan_vi_tri
```

Kỳ vọng: `Ran 8 tests … OK`.

- [ ] **Step 6: Commit**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/erpnext
python3 -m scripts.file_structure --audit
git add erpnext/vi_tri_kho/doctype/item_location_preference erpnext/vi_tri_kho/tests/test_gan_vi_tri.py
git commit -m "feat(vi_tri_kho): doctype Item Location Preference, khoá chính là mã mặt hàng"
```

---

## Task 2: Phép kiểm chồng lấn (vị từ giao nhau)

**Files:**
- Create: `erpnext/vi_tri_kho/vitri/gan.py`
- Modify: `erpnext/vi_tri_kho/doctype/item_location_preference/item_location_preference.py`
- Modify: `erpnext/vi_tri_kho/tests/test_gan_vi_tri.py`

**Interfaces:**
- Produces: `gan.chu_cua_nhanh(lft, rgt, tru_ten=None) -> dict | None` trả `{vat_tu, vi_tri, lft, rgt}` của gán đang giao với khoảng `[lft, rgt]`, hoặc `None`.

- [ ] **Step 1: Viết ma trận test đỏ**

Thêm vào `test_gan_vi_tri.py`:

```python
class TestChongLan(_Nen):
	"""Ma trận này phải có CẢ chốt âm.

	Một đột biến đổi vị từ giao nhau thành `s.name = %(vi_tri)s` vẫn làm ca
	"trùng đúng nút" xanh, trong khi để lọt hai ca nguy hiểm hơn (gán vào con
	cháu, gán vào tổ tiên). Ngược lại một vị từ chặt quá tay sẽ chặn oan nút
	anh em — và không bài nào bắt được nếu thiếu chốt âm.
	"""

	def test_trung_dung_nut_bi_chan(self):
		_gan(self.vt_a, "7A010101")
		with self.assertRaises(frappe.ValidationError):
			_gan(self.vt_b, "7A010101")

	def test_gan_vao_con_chau_bi_chan(self):
		"""A giữ Tầng 7A010101; B gán Ô 7A01010102 nằm trong đó."""
		_gan(self.vt_a, "7A010101")
		with self.assertRaises(frappe.ValidationError):
			_gan(self.vt_b, self.o2)

	def test_gan_vao_to_tien_bi_chan(self):
		"""A giữ Ô 7A01010101; B gán Khoang 7A0101 bao trùm nó."""
		_gan(self.vt_a, self.o1)
		with self.assertRaises(frappe.ValidationError):
			_gan(self.vt_b, "7A0101")

	def test_nut_anh_em_van_gan_duoc(self):
		"""CHỐT ÂM. Thiếu bài này thì một vị từ chặt quá tay (ví dụ so theo
		Khoang thay vì theo lft/rgt) vẫn xanh hết các bài trên, trong khi thực
		tế nó chặn oan mọi ô cạnh nhau — tức không ai gán được gì."""
		_gan(self.vt_a, self.o1)
		d = _gan(self.vt_b, self.o2)
		self.assertEqual(d.vi_tri, self.o2)

	def test_nhanh_khu_khac_van_gan_duoc(self):
		"""CHỐT ÂM thứ hai: đột biến bỏ hẳn mệnh đề giao nhau thì bài này vẫn
		xanh, nhưng `test_trung_dung_nut_bi_chan` sẽ đỏ — cặp đôi khoá chặt."""
		_o("8C01010101")
		_gan(self.vt_a, self.o1)
		d = _gan(self.vt_b, "8C01010101")
		self.assertEqual(d.vi_tri, "8C01010101")

	def test_sua_chinh_ban_ghi_cua_minh_van_duoc(self):
		"""Loại trừ `p.name != self.name`. Thiếu nó thì mọi lần lưu lại bản ghi
		đã có đều tự báo 'đụng chính mình' — gán tạo được một lần rồi vĩnh viễn
		không sửa nổi ghi chú."""
		d = _gan(self.vt_a, self.o1)
		d.ghi_chu = "đổi chỗ để kiểm"
		d.save(ignore_permissions=True)
		self.assertEqual(frappe.db.get_value("Item Location Preference", self.vt_a, "vi_tri"), self.o1)

	def test_thong_bao_neu_ten_mat_hang_dang_giu(self):
		"""'Không hợp lệ' trần thì người dùng không biết đi sửa ở đâu."""
		_gan(self.vt_a, "7A010101")
		with self.assertRaises(frappe.ValidationError) as ngoai_le:
			_gan(self.vt_b, self.o2)
		self.assertIn(self.vt_a, str(ngoai_le.exception))
		self.assertIn("7A010101", str(ngoai_le.exception))
```

- [ ] **Step 2: Chạy để chắc chắn ĐỎ**

```bash
bench --site erptest.local run-tests --module erpnext.vi_tri_kho.tests.test_gan_vi_tri
```

Kỳ vọng: 5 bài `TestChongLan` đỏ (các bài "bị chặn" không raise); 2 bài chốt âm xanh sẵn.

- [ ] **Step 3: Viết `gan.py`**

```python
"""Truy vấn dùng chung về gán vị trí — "nút này ai đang giữ".

Tách khỏi controller vì BA nơi cần hỏi cùng một câu: `validate()` của
`Item Location Preference`, cây chọn vị trí, và báo cáo `hang_nam_sai_vi_tri`.
Để trong controller thì hai nơi kia phải dựng một `Document` chỉ để gọi một
hàm thuần truy vấn — và cái giá thật không phải hiệu năng mà là bản sao: hai
định nghĩa "giao nhau" trôi khỏi nhau thì một nửa hệ chặn, nửa kia cho qua.
"""

import frappe


def chu_cua_nhanh(lft: int, rgt: int, tru_ten: str | None = None) -> dict | None:
	"""Gán đang GIAO với khoảng `[lft, rgt]`, hoặc None.

	Điều kiện là hai nhánh GIAO NHAU, không phải bằng nhau. Một vị từ bắt cả
	ba ca, và đó chính là lý do không được viết `s.name = ...`:

	    trùng đúng nút   A giữ 1B0104,   B gán 1B0104      → chặn
	    gán vào con cháu A giữ 1B0104,   B gán 1B010402    → chặn
	    gán vào tổ tiên  A giữ 1B010402, B gán 1B01        → chặn
	    nút anh em       A giữ 1B010401, B gán 1B010402    → CHO QUA

	`tru_ten` loại chính bản ghi đang lưu ra khỏi phép so — thiếu nó thì mọi
	lần lưu lại một gán đã tồn tại đều tự báo "đụng chính mình".

	Gọi hàm này với `lft`/`rgt` bằng 0 là LỖI của nơi gọi: `0 <= rgt and
	0 >= lft` đúng với mọi bản ghi, nên nó sẽ trả về một gán tuỳ ý. Nơi gọi
	phải chặn trước (xem `ItemLocationPreference.kiem_tra_trong_cay`).
	"""
	if not lft or not rgt:
		frappe.throw("chu_cua_nhanh() nhận toạ độ rỗng — nơi gọi phải chặn trước.")

	dong = frappe.db.sql(
		"""
		select p.vat_tu as vat_tu, p.vi_tri as vi_tri, s.lft as lft, s.rgt as rgt
		from `tabItem Location Preference` p
		join `tabStorage Location` s on s.name = p.vi_tri
		where p.name != %(tru)s
		  and s.lft <= %(rgt)s
		  and s.rgt >= %(lft)s
		order by s.lft asc
		limit 1
		""",
		{"tru": tru_ten or "", "lft": lft, "rgt": rgt},
		as_dict=True,
	)
	return dong[0] if dong else None
```

- [ ] **Step 4: Nối vào `validate()`**

Trong `item_location_preference.py`, thêm import và một phép kiểm:

```python
from erpnext.vi_tri_kho.vitri.gan import chu_cua_nhanh
```

Thêm `self.kiem_tra_chong_lan()` vào `validate()`, ngay **sau** `kiem_tra_nut_hop_le()`:

```python
	def kiem_tra_chong_lan(self):
		"""Không nhánh nào được giao với nhánh của một gán khác."""
		chu = chu_cua_nhanh(self.nut.lft, self.nut.rgt, tru_ten=self.name)
		if not chu:
			return

		if chu.vi_tri == self.vi_tri:
			quan_he = _("đã được gán cho")
		elif chu.lft <= self.nut.lft and chu.rgt >= self.nut.rgt:
			quan_he = _("nằm trong nhánh {0} đã được gán cho").format(chu.vi_tri)
		else:
			quan_he = _("bao trùm {0} đã được gán cho").format(chu.vi_tri)

		frappe.throw(
			_("Vị trí {0} {1} mặt hàng {2}. Mỗi ô chỉ thuộc về một mặt hàng.").format(
				self.vi_tri, quan_he, chu.vat_tu
			)
		)
```

- [ ] **Step 5: Chạy test**

```bash
bench --site erptest.local run-tests --module erpnext.vi_tri_kho.tests.test_gan_vi_tri
```

Kỳ vọng: `Ran 15 tests … OK`.

- [ ] **Step 6: Đột biến để chứng minh test có răng**

Đổi tạm trong `gan.py`: `s.lft <= %(rgt)s and s.rgt >= %(lft)s` → `s.name = %(vi_tri)s` (kèm tham số). Chạy lại: **`test_gan_vao_con_chau_bi_chan` và `test_gan_vao_to_tien_bi_chan` phải ĐỎ**. Khôi phục.

Nếu chúng vẫn xanh thì bài test đang không chứng minh gì — sửa bài test trước khi đi tiếp.

- [ ] **Step 7: Commit**

```bash
git add erpnext/vi_tri_kho/vitri/gan.py erpnext/vi_tri_kho/doctype/item_location_preference erpnext/vi_tri_kho/tests/test_gan_vi_tri.py
git commit -m "feat(vi_tri_kho): chặn chồng lấn gán bằng vị từ giao nhau lft/rgt"
```

---

## Task 3: Chặn theo tồn của mặt hàng khác

**Files:**
- Modify: `erpnext/vi_tri_kho/vitri/gan.py`
- Modify: `erpnext/vi_tri_kho/doctype/item_location_preference/item_location_preference.py`
- Modify: `erpnext/vi_tri_kho/tests/test_gan_vi_tri.py`

**Interfaces:**
- Produces: `gan.ton_khac_trong_nhanh(lft, rgt, vat_tu, gioi_han=3) -> list[dict]` — các dòng `{o, vat_tu, so_luong}` của mặt hàng KHÁC trong nhánh.

- [ ] **Step 1: Viết test đỏ**

```python
def _ton(o, vat_tu, so_luong, kho=KHO):
	"""Đặt thẳng tồn vị trí. KHÔNG đi qua sổ — bài này chỉ kiểm phép chặn lúc
	gán, không kiểm bất biến sổ/tồn (đã có `test_doi_soat.py` lo)."""
	ten = frappe.db.get_value("Location Balance", {"o": o, "vat_tu": vat_tu, "so_lo": ""}, "name")
	if ten:
		frappe.db.set_value("Location Balance", ten, "so_luong", so_luong)
		return ten
	return frappe.get_doc(
		{"doctype": "Location Balance", "o": o, "kho": kho, "vat_tu": vat_tu,
		 "so_lo": "", "so_luong": so_luong}
	).insert(ignore_permissions=True).name


class TestChanTheoTon(_Nen):
	def test_chan_khi_trong_nhanh_co_hang_mat_hang_khac(self):
		_ton(self.o1, self.vt_b, 15)
		with self.assertRaises(frappe.ValidationError):
			_gan(self.vt_a, "7A010101")

	def test_thong_bao_neu_ro_o_mat_hang_so_luong(self):
		"""Việc tiếp theo của người dùng là đi dọn ĐÚNG những ô đó bằng phiếu
		chuyển vị trí — thông báo phải đủ để làm việc đó ngay."""
		_ton(self.o1, self.vt_b, 15)
		with self.assertRaises(frappe.ValidationError) as e:
			_gan(self.vt_a, "7A010101")
		self.assertIn(self.o1, str(e.exception))
		self.assertIn(self.vt_b, str(e.exception))
		self.assertIn("15", str(e.exception))

	def test_hang_cua_chinh_no_thi_duoc(self):
		"""CHỐT ÂM. Một đột biến bỏ mệnh đề `vat_tu != ...` sẽ chặn luôn cả
		hàng của chính mặt hàng đang gán — tức không ai gán lại được vị trí cho
		món đã nằm sẵn đúng chỗ."""
		_ton(self.o1, self.vt_a, 15)
		d = _gan(self.vt_a, "7A010101")
		self.assertEqual(d.vi_tri, "7A010101")

	def test_ton_bang_0_khong_chan(self):
		"""Ô từng có hàng rồi hết vẫn còn dòng `so_luong = 0`. Coi đó là 'đang
		có hàng' thì mọi ô từng dùng qua đều vĩnh viễn không gán được."""
		_ton(self.o1, self.vt_b, 0)
		d = _gan(self.vt_a, "7A010101")
		self.assertEqual(d.vi_tri, "7A010101")
```

- [ ] **Step 2: Chạy để chắc chắn ĐỎ**

```bash
bench --site erptest.local run-tests --module erpnext.vi_tri_kho.tests.test_gan_vi_tri
```

Kỳ vọng: 2 bài đầu của `TestChanTheoTon` đỏ.

- [ ] **Step 3: Thêm truy vấn vào `gan.py`**

```python
def ton_khac_trong_nhanh(lft: int, rgt: int, vat_tu: str, gioi_han: int = 3) -> list[dict]:
	"""Tồn của mặt hàng KHÁC `vat_tu` đang nằm trong nhánh `[lft, rgt]`.

	`so_luong != 0` chứ không phải "có dòng": một ô từng có hàng rồi hết vẫn
	còn dòng `Location Balance` mang 0. Coi dòng-0 là "đang có hàng" thì mọi ô
	từng dùng qua sẽ vĩnh viễn không gán được cho ai.

	`gioi_han` chỉ để dựng thông báo (nêu vài ô đầu rồi "… và N ô nữa"), nên
	hàm trả thêm một dòng so với `gioi_han` để nơi gọi biết là còn nữa.
	"""
	if not lft or not rgt:
		frappe.throw("ton_khac_trong_nhanh() nhận toạ độ rỗng — nơi gọi phải chặn trước.")

	return frappe.db.sql(
		"""
		select lb.o as o, lb.vat_tu as vat_tu, lb.so_luong as so_luong
		from `tabLocation Balance` lb
		join `tabStorage Location` sl on sl.name = lb.o
		where sl.lft between %(lft)s and %(rgt)s
		  and lb.so_luong != 0
		  and lb.vat_tu != %(vat_tu)s
		order by sl.lft asc
		limit %(gioi_han)s
		""",
		{"lft": lft, "rgt": rgt, "vat_tu": vat_tu, "gioi_han": gioi_han + 1},
		as_dict=True,
	)
```

- [ ] **Step 4: Nối vào `validate()`**

Thêm `self.kiem_tra_ton_mat_hang_khac()` vào cuối `validate()` (sau `kiem_tra_chong_lan()` — phép kiểm này đắt nhất nên chạy sau cùng):

```python
	def kiem_tra_ton_mat_hang_khac(self):
		"""Trong nhánh không được có tồn của mặt hàng khác.

		Quyết định của chủ đầu tư 15/09 ("chặn cả hai").

		LƯU Ý CHO NGƯỜI ĐỌC SAU: phép kiểm này chỉ chặn LÚC GÁN. Hàng vẫn vào
		sai ô được sau đó — qua phiếu xếp khai tay, qua đường huỷ chứng từ, qua
		kiểm kê. Thứ soi việc đó là báo cáo `hang_nam_sai_vi_tri`; đối soát §3
		KHÔNG bắt được vì nó chỉ so tổng.
		"""
		GIOI_HAN = 3
		dong = ton_khac_trong_nhanh(self.nut.lft, self.nut.rgt, self.vat_tu, GIOI_HAN)
		if not dong:
			return

		ke = [
			_("{0}: {1} × {2}").format(d.o, d.vat_tu, frappe.format_value(d.so_luong, "Float"))
			for d in dong[:GIOI_HAN]
		]
		them = _(" … và {0} ô nữa").format(len(dong) - GIOI_HAN) if len(dong) > GIOI_HAN else ""
		frappe.throw(
			_(
				"Trong nhánh {0} đang có hàng của mặt hàng khác:\n\n{1}{2}\n\n"
				"Chuyển những ô đó đi bằng phiếu chuyển vị trí rồi gán lại."
			).format(self.vi_tri, "\n".join(ke), them)
		)
```

Thêm vào import: `from erpnext.vi_tri_kho.vitri.gan import chu_cua_nhanh, ton_khac_trong_nhanh`

- [ ] **Step 5: Chạy test**

```bash
bench --site erptest.local run-tests --module erpnext.vi_tri_kho.tests.test_gan_vi_tri
```

Kỳ vọng: `Ran 19 tests … OK`.

- [ ] **Step 6: Commit**

```bash
git add erpnext/vi_tri_kho/vitri/gan.py erpnext/vi_tri_kho/doctype/item_location_preference erpnext/vi_tri_kho/tests/test_gan_vi_tri.py
git commit -m "feat(vi_tri_kho): chặn gán khi trong nhánh đang có tồn của mặt hàng khác"
```

---

## Task 4: Móc `Item.after_rename`

**Files:**
- Modify: `erpnext/vi_tri_kho/vitri/gan.py`
- Modify: `erpnext/hooks.py`
- Modify: `erpnext/vi_tri_kho/tests/test_app_khoi_dong.py`
- Modify: `erpnext/vi_tri_kho/tests/test_gan_vi_tri.py`

**Interfaces:**
- Produces: `gan.doi_ten_theo_mat_hang(doc, method=None, old=None, new=None, merge=False)`

- [ ] **Step 1: Viết test đỏ**

Thêm vào `test_gan_vi_tri.py`:

```python
class TestDoiMaMatHang(_Nen):
	"""`autoname: field:vat_tu` mua được một khoá chính, và phải trả bằng đây.

	`_sync_autoname_field()` (frappe/model/base_document.py:1027) ép
	`vat_tu = name` MỖI LẦN LƯU khi hai giá trị lệch nhau — `name` luôn thắng.
	`rename_doc` của Item cập nhật GIÁ TRỊ `vat_tu` bằng SQL nhưng không đụng
	`name` của bản ghi gán. Không có móc, lần lưu kế tiếp kéo `vat_tu` ngược về
	mã CŨ, âm thầm: gán trỏ vào một mặt hàng không còn tồn tại, và gợi ý cho mã
	mới lặng lẽ biến mất.

	Cùng hình dạng bẫy mà `storage_location.py::kiem_tra_ma_o_khong_doi` đã
	phải chặn tường minh cho `ma_o`.
	"""

	def test_doi_ma_mat_hang_keo_theo_ten_ban_ghi_gan(self):
		cu = _mat_hang("_Test Gan VT Doi Ten")
		_gan(cu, self.o1)
		moi = "_Test Gan VT Doi Ten MOI"
		frappe.rename_doc("Item", cu, moi, force=True)

		self.assertFalse(frappe.db.exists("Item Location Preference", cu))
		self.assertTrue(frappe.db.exists("Item Location Preference", moi))

	def test_luu_lai_sau_khi_doi_ten_khong_keo_vat_tu_ve_ma_cu(self):
		"""CHỐT ÂM — bài trên vẫn xanh nếu ai đó chỉ `db.set_value` trường
		`vat_tu` mà không rename. Bài này bắt đúng cú revert im lặng."""
		cu = _mat_hang("_Test Gan VT Revert")
		_gan(cu, self.o2)
		moi = "_Test Gan VT Revert MOI"
		frappe.rename_doc("Item", cu, moi, force=True)

		d = frappe.get_doc("Item Location Preference", moi)
		d.ghi_chu = "lưu lại sau khi đổi mã"
		d.save(ignore_permissions=True)
		self.assertEqual(d.vat_tu, moi)
```

Thêm vào `test_app_khoi_dong.py`:

```python
	def test_hook_doi_ten_mat_hang_duoc_dang_ky(self):
		"""Móc thứ hai của module trong `hooks.py`, và cũng dễ mất y như móc
		SLE. Mất nó thì đổi mã một mặt hàng làm bản ghi gán của nó âm thầm trỏ
		về mã cũ ở lần lưu kế tiếp — không lỗi, không dấu vết."""
		HAM = "erpnext.vi_tri_kho.vitri.gan.doi_ten_theo_mat_hang"
		tay_cam = frappe.get_hooks("doc_events").get("Item", {}).get("after_rename") or []
		if isinstance(tay_cam, str):
			tay_cam = [tay_cam]
		self.assertIn(
			HAM,
			tay_cam,
			f"Móc {HAM} không còn trong doc_events['Item']['after_rename']. "
			"Mất nó thì đổi mã mặt hàng làm gán vị trí revert về mã cũ trong "
			"im lặng. Kiểm doc_events trong erpnext/hooks.py.",
		)
```

- [ ] **Step 2: Chạy để chắc chắn ĐỎ**

```bash
bench --site erptest.local run-tests --module erpnext.vi_tri_kho.tests.test_gan_vi_tri
bench --site erptest.local run-tests --module erpnext.vi_tri_kho.tests.test_app_khoi_dong
```

- [ ] **Step 3: Viết hàm trong `gan.py`**

```python
def doi_ten_theo_mat_hang(doc, method=None, old=None, new=None, merge=False):
	"""Đổi mã mặt hàng thì đổi luôn `name` của bản ghi gán.

	`Document.hook` gọi handler với `(doc, method, *args)` mà `rename_doc` đã
	truyền `(old, new, merge)` — nên chữ ký phải nhận đủ, xem
	`frappe/model/document.py:1357` và `rename_doc.py:207`.

	VÌ SAO KHÔNG ĐƠN GIẢN LÀ `db.set_value("...", ten, "vat_tu", new)`: bản ghi
	gán dùng `autoname: field:vat_tu`, nên `name` MỚI là nguồn sự thật.
	`_sync_autoname_field()` (base_document.py:1027) chạy ở mọi lần lưu và ép
	`vat_tu = name`. Sửa trường mà không sửa `name` thì lần lưu kế tiếp trả
	ngược về mã cũ — im lặng, không lỗi nào.

	`merge=True` (gộp hai mặt hàng): bản ghi gán của mã cũ bị XOÁ chứ không
	rename, vì mã mới có thể đã có gán riêng và `rename_doc` sẽ ném
	`DuplicateEntryError` giữa chừng một thao tác gộp đang dở.
	"""
	if not old or not new or old == new:
		return
	if not frappe.db.exists("Item Location Preference", old):
		return

	if merge:
		frappe.delete_doc("Item Location Preference", old, ignore_permissions=True, force=True)
		return

	frappe.rename_doc("Item Location Preference", old, new, force=True, show_alert=False)
```

- [ ] **Step 4: Khai móc trong `hooks.py`**

Trong `doc_events`, thêm ngay sau khối `"Stock Ledger Entry"` (giữ nó cạnh móc cùng module để một lần merge giải xung đột nhìn thấy cả hai):

```python
	# Đổi mã một Item phải kéo theo `name` của bản ghi gán vị trí, vì doctype
	# đó dùng `autoname: field:vat_tu` — `name` là nguồn sự thật, không phải
	# trường. Mất dòng này thì đổi mã mặt hàng làm gán vị trí ÂM THẦM trỏ về mã
	# cũ ở lần lưu kế tiếp (`_sync_autoname_field`, base_document.py:1027):
	# không lỗi, không dấu vết, chỉ là gợi ý xếp hàng biến mất.
	# `vi_tri_kho/tests/test_app_khoi_dong.py` khoá việc này.
	"Item": {
		"after_rename": "erpnext.vi_tri_kho.vitri.gan.doi_ten_theo_mat_hang",
	},
```

> **Kiểm trước khi gõ:** nếu `doc_events` đã có khoá `"Item"` sẵn, **gộp** vào khoá đó thay vì thêm khoá thứ hai — khai trùng khoá trong một dict Python thì khoá sau nuốt khoá trước, và mọi handler `Item` cũ biến mất trong im lặng. Kiểm bằng `grep -n '"Item":' erpnext/hooks.py`.

- [ ] **Step 5: Chạy test**

```bash
bench --site erptest.local run-tests --module erpnext.vi_tri_kho.tests.test_gan_vi_tri
bench --site erptest.local run-tests --module erpnext.vi_tri_kho.tests.test_app_khoi_dong
```

Kỳ vọng: `Ran 21 tests … OK` và `Ran 4 tests … OK`.

- [ ] **Step 6: Commit**

```bash
git add erpnext/vi_tri_kho/vitri/gan.py erpnext/hooks.py erpnext/vi_tri_kho/tests/
git commit -m "fix(vi_tri_kho): đổi mã mặt hàng kéo theo tên bản ghi gán vị trí"
```

---

## Task 5: Hàm gợi ý ô

**Files:**
- Create: `erpnext/vi_tri_kho/vitri/goi_y.py`
- Create: `erpnext/vi_tri_kho/tests/test_goi_y_o.py`

**Interfaces:**
- Consumes: `gan` (Task 2–3), `fefo._TO_TIEN_TAT`
- Produces: `goi_y.goi_y_o(vat_tu, kho) -> tuple[str | None, str]` — `(mã ô, lý do)`

- [ ] **Step 1: Viết test đỏ**

`erpnext/vi_tri_kho/tests/test_goi_y_o.py`:

```python
"""Gợi ý ô khi xếp hàng: ô trống đầu tiên theo THỨ TỰ CÂY.

Bài quan trọng nhất ở đây là `test_theo_thu_tu_cay_chu_khong_phai_thu_tu_ten`.
Trong dữ liệu mẫu, thứ tự `lft` trùng thứ tự chữ cái của mã, nên một bản sắp
theo `order by name` vẫn xanh mọi bài khác mà không chứng minh được gì. Ca đó
dựng riêng một nhánh mà hai thứ tự KHÁC nhau.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.vi_tri_kho.vitri.goi_y import goi_y_o

KHO = "Kho Miyano - MYN"

# Dùng lại helper của bài gán — cùng cách dựng dữ liệu, một chỗ sửa.
from erpnext.vi_tri_kho.tests.test_gan_vi_tri import _gan, _mat_hang, _o, _ton


class _NenGoiY(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		# Tầng 6B010201 có 3 ô
		for o in ("6B01020101", "6B01020102", "6B01020103"):
			_o(o)
		cls.tang = "6B010201"
		cls.vt = _mat_hang("_Test GoiY VT")
		cls.vt_khac = _mat_hang("_Test GoiY VT Khac")


class TestGoiY(_NenGoiY):
	def test_chua_gan_thi_khong_goi_y_va_KHONG_nem_loi(self):
		"""Phần lớn mặt hàng sẽ chưa gán trong nhiều tháng tới. Ném lỗi ở đây
		là phiếu xếp không mở nổi."""
		o, ly_do = goi_y_o(_mat_hang("_Test GoiY Chua Gan"), KHO)
		self.assertIsNone(o)
		self.assertIn("chưa gán", ly_do)

	def test_o_trong_dau_tien(self):
		_gan(self.vt, self.tang)
		_ton("6B01020101", self.vt, 5)
		o, ly_do = goi_y_o(self.vt, KHO)
		self.assertEqual(o, "6B01020102")
		self.assertIn("trống", ly_do)

	def test_theo_thu_tu_cay_chu_khong_phai_thu_tu_ten(self):
		"""Dựng nhánh mà thứ tự `lft` KHÁC thứ tự chữ cái.

		`Storage Location` là nested set: `lft` do thứ tự chèn quyết định, còn
		mã thì không. Tạo ô `...03` TRƯỚC `...02` rồi kiểm rằng gợi ý vẫn đi
		theo cây. Thiếu ca này, `order by name` và `order by lft` không phân
		biệt được — và bài test không khoá cái nó tưởng là đang khoá.
		"""
		_o("6C01020103")
		_o("6C01020102")
		v = _mat_hang("_Test GoiY ThuTu")
		_gan(v, "6C010201")
		lft = {
			n: frappe.db.get_value("Storage Location", n, "lft")
			for n in ("6C01020102", "6C01020103")
		}
		dau_theo_cay = min(lft, key=lft.get)
		o, _ = goi_y_o(v, KHO)
		self.assertEqual(o, dau_theo_cay)

	def test_het_o_trong_thi_don_vao_o_dang_co_hang_cua_chinh_no(self):
		"""Phương án (b) chủ đầu tư chốt 15/09.

		Không có nhánh này thì gán một mặt hàng vào MỘT Ô lẻ khiến lần nhập thứ
		hai trở đi luôn báo đầy — dù hàng trong ô chính là hàng của nó và kệ
		còn thừa chỗ.
		"""
		v = _mat_hang("_Test GoiY O Le")
		_o("6D01020101")
		_gan(v, "6D01020101")
		_ton("6D01020101", v, 7)
		o, ly_do = goi_y_o(v, KHO)
		self.assertEqual(o, "6D01020101")
		self.assertIn("dồn", ly_do)

	def test_day_thi_bao_day(self):
		v = _mat_hang("_Test GoiY Day")
		for o in ("6E01020101", "6E01020102"):
			_o(o)
			_ton(o, self.vt_khac, 3)
		_gan(v, "6E010201")
		o, ly_do = goi_y_o(v, KHO)
		self.assertIsNone(o)
		self.assertIn("đầy", ly_do)

	def test_o_trong_nhanh_ngung_dung_khong_bao_gio_duoc_goi_y(self):
		"""Tắt cả một Khoang để sửa kệ. Ô bên dưới vẫn `disabled = 0` của
		riêng nó — chỉ tổ tiên bị tắt. Gợi ý trỏ vào đó thì `fefo` lại từ chối
		lấy hàng ra: hai nửa của hệ nói ngược nhau."""
		v = _mat_hang("_Test GoiY Tat")
		for o in ("6F01020101", "6F01020102"):
			_o(o)
		_gan(v, "6F010201")
		frappe.db.set_value("Storage Location", "6F0102", "disabled", 1)
		try:
			o, ly_do = goi_y_o(v, KHO)
			self.assertIsNone(o)
		finally:
			frappe.db.set_value("Storage Location", "6F0102", "disabled", 0)

	def test_o_chua_xep_khong_bao_gio_la_ket_qua(self):
		zzz = frappe.db.get_value("Storage Location", {"la_o_chua_xep": 1, "kho": KHO}, "name")
		_gan(self.vt, self.tang)
		o, _ = goi_y_o(self.vt, KHO)
		self.assertNotEqual(o, zzz)
```

- [ ] **Step 2: Chạy để chắc chắn ĐỎ**

```bash
bench --site erptest.local run-tests --module erpnext.vi_tri_kho.tests.test_goi_y_o
```

Kỳ vọng: `ModuleNotFoundError: erpnext.vi_tri_kho.vitri.goi_y`.

- [ ] **Step 3: Viết `goi_y.py`**

```python
"""Gợi ý ô để xếp hàng, dựa trên gán vị trí cố định của mặt hàng.

Đây là thứ mở khoá một quyết định cũ. `xep.py::hang_chua_xep` từng cố ý để
trống `den_o` với lý do "không có căn cứ nào để gợi ý (suc_chua = 0 trên cả
214 ô), mà gợi ý sai thì thủ kho tin theo rồi xếp nhầm". Lý do đó đúng KHI
CĂN CỨ DUY NHẤT LÀ SỨC CHỨA. Gán cố định là một căn cứ khác: khi ô đã thuộc
đúng một mặt hàng thì "xếp đâu" trả lời được mà không cần biết ô chứa nổi bao
nhiêu.

Hàm trả về CẶP `(ô, lý do)`, không phải mỗi ô. Lý do hiện cạnh gợi ý trên
phiếu xếp, vì thủ kho cần phân biệt "ô này trống" với "ô này đã có hàng cùng
loại, dồn vào" TRƯỚC khi ra mở kệ — hai việc khác nhau ngoài kho.
"""

import frappe
from frappe import _

from erpnext.vi_tri_kho.vitri.fefo import _TO_TIEN_TAT

# Ứng viên: ô LÁ thật trong nhánh, không phải nút nhóm, không phải ô ảo, và
# không nằm dưới một nút đang ngừng dùng.
#
# `_TO_TIEN_TAT` mượn nguyên từ `fefo.py` chứ KHÔNG chép lại. Nó mã hoá luật
# "ô coi như tắt nếu chính nó HOẶC bất kỳ tổ tiên nào tắt". Có hai bản thì một
# ngày nào đó sửa một chỗ quên chỗ kia, và khi ấy gợi ý trỏ vào một dãy đang
# tắt trong khi `fefo` từ chối lấy hàng từ đó — hai nửa của hệ nói ngược nhau,
# không có gì báo. Vị từ dùng alias `sl`, nên truy vấn dưới phải giữ đúng alias.
_UNG_VIEN = f"""
	from `tabStorage Location` sl
	where sl.lft between %(lft)s and %(rgt)s
	  and ifnull(sl.is_group, 0) = 0
	  and ifnull(sl.la_o_chua_xep, 0) = 0
	  and not {_TO_TIEN_TAT}
"""


def goi_y_o(vat_tu: str, kho: str) -> tuple[str | None, str]:
	"""Ô nên xếp `vat_tu` vào, kèm lý do. `(None, lý do)` nếu không gợi ý được."""
	gan = frappe.db.sql(
		"""
		select p.vi_tri as vi_tri, s.lft as lft, s.rgt as rgt
		from `tabItem Location Preference` p
		join `tabStorage Location` s on s.name = p.vi_tri
		where p.name = %(vat_tu)s and p.kho = %(kho)s
		""",
		{"vat_tu": vat_tu, "kho": kho},
		as_dict=True,
	)
	if not gan:
		return None, _("mặt hàng chưa gán vị trí cố định")

	g = gan[0]
	if not g.lft or not g.rgt:
		# Cùng bẫy đã trả giá ở `fefo.py` và `tem.py`: `between 0 and 0` khớp
		# MỌI bản ghi 0/0 toàn hệ, nên sẽ gợi ý một ô của kho khác. Chặn ở
		# nguồn, không trả về im lặng — gợi ý sai thì thủ kho tin theo.
		frappe.throw(
			_(
				"Vị trí {0} gán cho mặt hàng {1} chưa có toạ độ trong cây nên không "
				"gợi ý được. Lưu lại vị trí đó, hoặc chạy `bench migrate`."
			).format(g.vi_tri, vat_tu)
		)

	tham_so = {"lft": g.lft, "rgt": g.rgt, "vat_tu": vat_tu}

	trong = frappe.db.sql(
		f"""
		select sl.name
		{_UNG_VIEN}
		  and ifnull((
		        select sum(lb.so_luong) from `tabLocation Balance` lb where lb.o = sl.name
		      ), 0) = 0
		order by sl.lft asc
		limit 1
		""",
		tham_so,
	)
	if trong:
		return trong[0][0], _("ô trống đầu tiên trong {0}").format(g.vi_tri)

	# Không còn ô trống → dồn vào ô đang chứa CHÍNH mặt hàng này (phương án (b),
	# chủ đầu tư chốt 15/09). Không có nhánh này thì gán vào một Ô lẻ khiến lần
	# nhập thứ hai trở đi luôn báo đầy.
	cung_hang = frappe.db.sql(
		f"""
		select sl.name
		{_UNG_VIEN}
		  and exists (
		        select 1 from `tabLocation Balance` lb
		        where lb.o = sl.name and lb.vat_tu = %(vat_tu)s and lb.so_luong != 0
		      )
		order by sl.lft asc
		limit 1
		""",
		tham_so,
	)
	if cung_hang:
		return cung_hang[0][0], _("dồn vào ô đang có hàng cùng mặt hàng")

	tong = frappe.db.sql(f"select count(*) {_UNG_VIEN}", tham_so)[0][0]
	return None, _("vùng {0} đã đầy: {1}/{1} ô đang chứa hàng khác").format(g.vi_tri, tong)
```

- [ ] **Step 4: Chạy test**

```bash
bench --site erptest.local run-tests --module erpnext.vi_tri_kho.tests.test_goi_y_o
```

Kỳ vọng: `Ran 7 tests … OK`.

- [ ] **Step 5: Đột biến để chứng minh bài thứ tự cây có răng**

Đổi tạm cả ba `order by sl.lft asc` → `order by sl.name asc`. Chạy lại:
**`test_theo_thu_tu_cay_chu_khong_phai_thu_tu_ten` phải ĐỎ**, các bài khác vẫn xanh.
Khôi phục. Nếu nó vẫn xanh thì dữ liệu ca đó chưa làm hai thứ tự khác nhau — sửa
dữ liệu ca thử trước khi đi tiếp.

- [ ] **Step 6: Commit**

```bash
git add erpnext/vi_tri_kho/vitri/goi_y.py erpnext/vi_tri_kho/tests/test_goi_y_o.py
git commit -m "feat(vi_tri_kho): gợi ý ô trống đầu tiên theo thứ tự cây, hết trống thì dồn"
```

---

## Task 6: Điền `den_o` trên phiếu xếp

**Files:**
- Modify: `erpnext/vi_tri_kho/vitri/xep.py`
- Modify: `erpnext/vi_tri_kho/doctype/location_transfer/location_transfer.js:26-40`
- Modify: `erpnext/vi_tri_kho/tests/test_goi_y_o.py`

**Interfaces:**
- Consumes: `goi_y.goi_y_o`
- Produces: mỗi dòng `hang_chua_xep()` có thêm `den_o` và `ly_do_goi_y`

- [ ] **Step 1: Viết test đỏ**

Thêm vào `test_goi_y_o.py`:

```python
class TestPhieuXepDuocDienSan(_NenGoiY):
	def test_mat_hang_da_gan_thi_den_o_duoc_dien(self):
		from erpnext.vi_tri_kho.vitri.xep import hang_chua_xep

		zzz = frappe.db.get_value("Storage Location", {"la_o_chua_xep": 1, "kho": KHO}, "name")
		v = _mat_hang("_Test Xep Da Gan")
		_o("7B01020101")
		_gan(v, "7B010201")
		_ton(zzz, v, 9)

		dong = [d for d in hang_chua_xep(KHO) if d["vat_tu"] == v]
		self.assertEqual(len(dong), 1)
		self.assertEqual(dong[0]["den_o"], "7B01020101")
		self.assertIn("trống", dong[0]["ly_do_goi_y"])

	def test_mat_hang_chua_gan_thi_den_o_van_trong(self):
		"""CHỐT ÂM và là ca thật: phần lớn mặt hàng chưa gán. Một bản điền bừa
		(ví dụ lấy ô trống đầu tiên của cả kho) sẽ làm bài trên xanh mà vẫn dẫn
		thủ kho xếp nhầm."""
		from erpnext.vi_tri_kho.vitri.xep import hang_chua_xep

		zzz = frappe.db.get_value("Storage Location", {"la_o_chua_xep": 1, "kho": KHO}, "name")
		v = _mat_hang("_Test Xep Chua Gan")
		_ton(zzz, v, 4)

		dong = [d for d in hang_chua_xep(KHO) if d["vat_tu"] == v]
		self.assertEqual(len(dong), 1)
		self.assertFalse(dong[0]["den_o"])
		self.assertIn("chưa gán", dong[0]["ly_do_goi_y"])
```

- [ ] **Step 2: Chạy để chắc chắn ĐỎ**

```bash
bench --site erptest.local run-tests --module erpnext.vi_tri_kho.tests.test_goi_y_o
```

Kỳ vọng: `KeyError: 'den_o'`.

- [ ] **Step 3: Sửa `xep.py`**

Đổi docstring của `hang_chua_xep` — **bắt buộc**, không phải trang trí. Nó đang
nói "không có căn cứ nào để gợi ý"; để nguyên thì người đọc sau tin là hệ vẫn
không gợi ý trong khi nó đã gợi ý rồi:

```python
@frappe.whitelist()
def hang_chua_xep(kho: str) -> list[dict]:
	"""Các dòng tồn ở ô "Chưa xếp vị trí" của `kho`, dạng dòng phiếu sẵn.

	`den_o` được ĐIỀN SẴN từ `goi_y.goi_y_o()` kể từ 15/09/2026. Trước đó nó cố
	ý để trống, vì căn cứ duy nhất khi ấy là `suc_chua` (= 0 trên cả 214 ô) và
	gợi ý sai thì thủ kho tin theo rồi xếp nhầm. Căn cứ nay khác hẳn: mặt hàng
	có vị trí cố định, nên "xếp đâu" trả lời được mà không cần sức chứa.

	Mặt hàng CHƯA gán vẫn để `den_o` trống — không đoán. `ly_do_goi_y` luôn có
	giá trị để màn hình nói được vì sao trống.

	Gợi ý KHÔNG chặn và KHÔNG ghi đè: thủ kho đứng trước kệ biết những thứ hệ
	không biết.
	"""
	_kiem_tra_quyen()
	dong = frappe.db.sql(
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

	# Một lời gọi `goi_y_o` cho mỗi MẶT HÀNG, không phải mỗi dòng: một mặt hàng
	# nhiều lô cho ra nhiều dòng nhưng cùng một gợi ý.
	bo_nho: dict[str, tuple] = {}
	for d in dong:
		if d.vat_tu not in bo_nho:
			bo_nho[d.vat_tu] = goi_y_o(d.vat_tu, kho)
		d["den_o"], d["ly_do_goi_y"] = bo_nho[d.vat_tu]
	return dong
```

Thêm import: `from erpnext.vi_tri_kho.vitri.goi_y import goi_y_o`

- [ ] **Step 4: Hiện lý do trên form**

Trong `location_transfer.js`, hàm `lay_hang_chua_xep`, sau khi đổ dòng vào lưới,
thêm một dòng tóm tắt:

```js
			const chua_gan = (r.message || []).filter((d) => !d.den_o).length;
			if (chua_gan) {
				frappe.show_alert({
					message: __("{0} dòng chưa có gợi ý — mặt hàng chưa gán vị trí cố định.", [
						chua_gan,
					]),
					indicator: "orange",
				});
			}
```

- [ ] **Step 5: Chạy test**

```bash
bench --site erptest.local run-tests --module erpnext.vi_tri_kho.tests.test_goi_y_o
bench --site erptest.local run-tests --module erpnext.vi_tri_kho.tests.test_phieu_xep_vi_tri
```

Kỳ vọng: cả hai `OK`. `test_phieu_xep_vi_tri` có bài cũ đọc `hang_chua_xep` —
nếu bài nào đó khẳng định `den_o` trống thì **đó là bài cần cập nhật**, không
phải mã cần sửa; sửa bài và ghi lý do vào docstring của nó.

- [ ] **Step 6: Commit**

```bash
git add erpnext/vi_tri_kho/vitri/xep.py erpnext/vi_tri_kho/doctype/location_transfer/location_transfer.js erpnext/vi_tri_kho/tests/
git commit -m "feat(vi_tri_kho): phiếu xếp điền sẵn ô đích theo vị trí cố định"
```

---

## Task 7: Cây chọn vị trí

**Files:**
- Modify: `erpnext/vi_tri_kho/vitri/gan.py`
- Create: `erpnext/public/js/vi_tri_kho/cay_chon_vi_tri.js`
- Create: `erpnext/vi_tri_kho/doctype/item_location_preference/item_location_preference.js`
- Modify: `erpnext/vi_tri_kho/tests/test_gan_vi_tri.py`

**Interfaces:**
- Produces: `@frappe.whitelist() gan.cay_chon_vi_tri(kho, parent=None) -> list[dict]` với các khoá `value`, `title`, `expandable`, `da_gan_cho`, `co_hang_khac`, `so_o_trong`

- [ ] **Step 1: Viết test đỏ cho phần máy chủ**

```python
class TestCayChonViTri(_Nen):
	"""Chỉ kiểm phần MÁY CHỦ. Việc vẽ cây nằm ở JS và không bài Python nào ở
	đây chứng minh nó vẽ đúng — đừng đọc bộ test này như thể nó chứng minh."""

	def test_tra_ve_khu_khi_khong_co_parent(self):
		from erpnext.vi_tri_kho.vitri.gan import cay_chon_vi_tri

		nut = cay_chon_vi_tri(KHO)
		self.assertTrue(nut)
		self.assertTrue(all(len(n["value"]) == 2 for n in nut), "cấp gốc phải là Khu (2 ký tự)")

	def test_nut_da_co_chu_mang_ten_mat_hang(self):
		from erpnext.vi_tri_kho.vitri.gan import cay_chon_vi_tri

		_gan(self.vt_a, "7A010101")
		nut = {n["value"]: n for n in cay_chon_vi_tri(KHO, parent="7A0101")}
		self.assertEqual(nut["7A010101"]["da_gan_cho"], self.vt_a)

	def test_con_chau_cua_nut_da_co_chu_cung_bao_co_chu(self):
		"""CHỐT ÂM quan trọng nhất của cây. Một bản chỉ tra gán ĐÚNG nút sẽ
		hiện Tầng là 'đã có chủ' nhưng các Ô bên dưới vẫn trông trống — người
		dùng bấm vào Ô đó rồi mới ăn lỗi. 'Không khả dụng' phải NHÌN THẤY
		TRƯỚC KHI BẤM, nếu không thì với 214 ô đây là trò chơi đoán."""
		from erpnext.vi_tri_kho.vitri.gan import cay_chon_vi_tri

		_gan(self.vt_a, "7A010101")
		nut = {n["value"]: n for n in cay_chon_vi_tri(KHO, parent="7A010101")}
		self.assertEqual(nut[self.o1]["da_gan_cho"], self.vt_a)

	def test_o_chua_xep_khong_xuat_hien_trong_cay(self):
		from erpnext.vi_tri_kho.vitri.gan import cay_chon_vi_tri

		zzz = frappe.db.get_value("Storage Location", {"la_o_chua_xep": 1, "kho": KHO}, "name")
		gia_tri = {n["value"] for n in cay_chon_vi_tri(KHO)}
		self.assertNotIn(zzz, gia_tri)
```

- [ ] **Step 2: Chạy để chắc chắn ĐỎ**

```bash
bench --site erptest.local run-tests --module erpnext.vi_tri_kho.tests.test_gan_vi_tri
```

- [ ] **Step 3: Viết `cay_chon_vi_tri` trong `gan.py`**

```python
from frappe import _

VAI_TRO_DUOC_XEM_CAY = {"System Manager", "Stock Manager", "Stock User"}


@frappe.whitelist()
def cay_chon_vi_tri(kho: str, parent: str | None = None) -> list[dict]:
	"""Các nút con để vẽ một cấp của cây chọn vị trí.

	`@frappe.whitelist()` một mình chỉ chặn khách vãng lai; danh mục ô lộ ra
	toàn bộ cách bố trí kho nên đăng nhập hợp lệ không phải điều kiện đủ. Cùng
	bộ vai trò với `tem.py` và `xep.py`.

	`da_gan_cho` tra theo TỔ TIÊN chứ không theo đúng nút: gán ở Tầng thì mọi Ô
	dưới nó cũng đã có chủ. Không làm vậy thì cây hiện Tầng là "đã có chủ" mà
	các Ô bên dưới vẫn trông trống, người dùng bấm vào rồi mới ăn lỗi từ
	`validate()` — với 214 ô đó là trò chơi đoán, không phải giao diện.
	"""
	if not VAI_TRO_DUOC_XEM_CAY & set(frappe.get_roles()):
		frappe.throw(_("Bạn không có quyền xem cây vị trí."), frappe.PermissionError)

	dieu_kien = "sl.parent_storage_location = %(parent)s" if parent else "ifnull(sl.parent_storage_location, '') = ''"
	return frappe.db.sql(
		f"""
		select sl.name as value,
		       ifnull(sl.ma_in_nhan, sl.name) as title,
		       ifnull(sl.is_group, 0) as expandable,
		       (select p.vat_tu
		          from `tabItem Location Preference` p
		          join `tabStorage Location` s2 on s2.name = p.vi_tri
		         where s2.lft <= sl.lft and s2.rgt >= sl.rgt
		         order by s2.lft asc limit 1) as da_gan_cho,
		       (select count(distinct lb.vat_tu)
		          from `tabLocation Balance` lb
		          join `tabStorage Location` s3 on s3.name = lb.o
		         where s3.lft between sl.lft and sl.rgt and lb.so_luong != 0) as so_mat_hang_dang_co,
		       (select count(*)
		          from `tabStorage Location` s4
		         where s4.lft between sl.lft and sl.rgt
		           and ifnull(s4.is_group, 0) = 0
		           and ifnull(s4.la_o_chua_xep, 0) = 0
		           and ifnull((select sum(lb2.so_luong) from `tabLocation Balance` lb2
		                        where lb2.o = s4.name), 0) = 0) as so_o_trong
		from `tabStorage Location` sl
		where {dieu_kien}
		  and sl.kho = %(kho)s
		  and ifnull(sl.la_o_chua_xep, 0) = 0
		  and sl.lft > 0
		order by sl.lft asc
		""",
		{"kho": kho, "parent": parent},
		as_dict=True,
	)
```

- [ ] **Step 4: Chạy test máy chủ**

```bash
bench --site erptest.local run-tests --module erpnext.vi_tri_kho.tests.test_gan_vi_tri
```

Kỳ vọng: `Ran 25 tests … OK`.

- [ ] **Step 5: Viết dialog cây**

`erpnext/public/js/vi_tri_kho/cay_chon_vi_tri.js`:

```js
// Dialog chọn một nút vị trí bằng cây, dùng chung.
//
// Nạp bằng `frappe.require("/assets/erpnext/js/vi_tri_kho/cay_chon_vi_tri.js")`
// — cùng lối với `tem_vi_tri.js`, không thêm dòng nào vào `hooks.py`.
//
// ĐIỀU DUY NHẤT KHÔNG ĐƯỢC BỎ: nút đã có chủ phải hiện MỜ kèm tên mặt hàng
// đang giữ, và bấm không ăn. Cho bấm rồi mới ném lỗi từ `validate()` nghĩa là
// bắt người dùng dò từng nút trong 214 ô để tìm chỗ còn trống.

frappe.provide("erpnext.vi_tri_kho");

erpnext.vi_tri_kho.chon_vi_tri = function (kho, khi_chon) {
	const d = new frappe.ui.Dialog({
		title: __("Chọn vị trí cố định"),
		size: "large",
		fields: [{ fieldname: "cay", fieldtype: "HTML" }],
	});
	d.show();

	new frappe.ui.Tree({
		parent: d.fields_dict.cay.$wrapper,
		label: kho,
		expandable: true,
		method: "erpnext.vi_tri_kho.vitri.gan.cay_chon_vi_tri",
		args: { kho: kho },
		get_label: function (node) {
			const n = node.data || {};
			if (n.da_gan_cho) {
				return `<span class="text-muted">${frappe.utils.escape_html(node.label)}
					— ${__("đã gán")}: ${frappe.utils.escape_html(n.da_gan_cho)}</span>`;
			}
			const trong = n.so_o_trong ? ` · ${n.so_o_trong} ${__("ô trống")}` : "";
			const khac = n.so_mat_hang_dang_co
				? ` · <span class="text-warning">${n.so_mat_hang_dang_co} ${__("mặt hàng đang nằm")}</span>`
				: "";
			return frappe.utils.escape_html(node.label) + `<span class="small">${trong}${khac}</span>`;
		},
		onclick: function (node) {
			const n = node.data || {};
			if (n.da_gan_cho) {
				frappe.show_alert({
					message: __("{0} đã thuộc mặt hàng {1}.", [node.value, n.da_gan_cho]),
					indicator: "orange",
				});
				return;
			}
			khi_chon(node.value);
			d.hide();
		},
	});
};
```

- [ ] **Step 6: Nối nút vào form**

`item_location_preference.js`:

```js
// Nút mở cây chọn vị trí. Trường `vi_tri` vẫn là Link bình thường — gõ tay
// được, vì người quen mã gõ nhanh hơn bấm năm cấp cây.

const DUONG_CAY = "/assets/erpnext/js/vi_tri_kho/cay_chon_vi_tri.js";

frappe.ui.form.on("Item Location Preference", {
	refresh(frm) {
		frm.add_custom_button(__("Chọn trên cây vị trí"), () => {
			if (!frm.doc.kho) {
				frappe.msgprint(__("Chọn Kho trước — cây vị trí là của một kho."));
				return;
			}
			frappe.require(DUONG_CAY, () => {
				erpnext.vi_tri_kho.chon_vi_tri(frm.doc.kho, (o) => frm.set_value("vi_tri", o));
			});
		});
	},
});
```

- [ ] **Step 7: Kiểm bằng mắt trên trình duyệt**

Mở `Item Location Preference` mới → chọn Kho → bấm **Chọn trên cây vị trí**.
Kiểm ba điều: cây mở được từng cấp; nút đã có chủ hiện mờ kèm tên mặt hàng và
bấm không ăn; chọn một nút trống thì `vi_tri` được điền.

**Khai rõ trong báo cáo nếu bước này chưa chạy được** (extension Chrome không
mở được localhost trong phiên trước). Đừng viết "đã kiểm" cho phần chỉ đọc mã.

- [ ] **Step 8: Commit**

```bash
python3 -m scripts.file_structure --audit
git add erpnext/public/js/vi_tri_kho/cay_chon_vi_tri.js erpnext/vi_tri_kho/doctype/item_location_preference erpnext/vi_tri_kho/vitri/gan.py erpnext/vi_tri_kho/tests/test_gan_vi_tri.py
git commit -m "feat(vi_tri_kho): cây chọn vị trí, nút đã có chủ hiện mờ không bấm được"
```

---

## Task 8: Báo cáo `hang_nam_sai_vi_tri`

**Files:**
- Create: `erpnext/vi_tri_kho/report/hang_nam_sai_vi_tri/__init__.py`
- Create: `erpnext/vi_tri_kho/report/hang_nam_sai_vi_tri/hang_nam_sai_vi_tri.json`
- Create: `erpnext/vi_tri_kho/report/hang_nam_sai_vi_tri/hang_nam_sai_vi_tri.py`
- Modify: `erpnext/vi_tri_kho/tests/test_bao_cao.py`

**Interfaces:**
- Produces: `execute(filters=None) -> (columns, data)`

- [ ] **Step 1: Viết test đỏ**

Thêm vào `test_bao_cao.py`:

```python
class TestHangNamSaiViTri(FrappeTestCase):
	"""Bổ khuyết của một phép kiểm chỉ chạy MỘT LẦN.

	`ItemLocationPreference.kiem_tra_ton_mat_hang_khac` chặn lúc GÁN. Sau đó
	hàng vẫn vào sai ô được — phiếu xếp khai tay, huỷ chứng từ, kiểm kê. Đối
	soát §3 (`doi_soat.py`) KHÔNG bắt được: nó chỉ so TỔNG tồn vị trí với tồn
	kho ERPNext, nên một ô chứa nhầm mặt hàng vẫn khớp tuyệt đối.
	"""

	def test_bao_cao_rong_khi_moi_thu_dung_cho(self):
		from erpnext.vi_tri_kho.report.hang_nam_sai_vi_tri.hang_nam_sai_vi_tri import execute
		from erpnext.vi_tri_kho.tests.test_gan_vi_tri import _gan, _mat_hang, _o, _ton

		v = _mat_hang("_Test Sai VT Dung")
		_o("5A01010101")
		_gan(v, "5A010101")
		_ton("5A01010101", v, 5)
		_, dong = execute({"kho": "Kho Miyano - MYN"})
		self.assertFalse([d for d in dong if d[0] == "5A01010101"])

	def test_bat_duoc_hang_lot_vao_o_cua_mat_hang_khac(self):
		from erpnext.vi_tri_kho.report.hang_nam_sai_vi_tri.hang_nam_sai_vi_tri import execute
		from erpnext.vi_tri_kho.tests.test_gan_vi_tri import _gan, _mat_hang, _o, _ton

		chu = _mat_hang("_Test Sai VT Chu")
		lac = _mat_hang("_Test Sai VT Lac")
		_o("5B01010101")
		_gan(chu, "5B010101")
		# Ghi thẳng tồn, mô phỏng hàng lọt vào sau khi đã gán.
		_ton("5B01010101", lac, 3)

		_, dong = execute({"kho": "Kho Miyano - MYN"})
		sai = [d for d in dong if d[0] == "5B01010101"]
		self.assertEqual(len(sai), 1)
		self.assertIn(lac, sai[0])
		self.assertIn(chu, sai[0])
```

- [ ] **Step 2: Chạy để chắc chắn ĐỎ**

```bash
bench --site erptest.local run-tests --module erpnext.vi_tri_kho.tests.test_bao_cao
```

- [ ] **Step 3: Tạo `__init__.py` rỗng và JSON**

`hang_nam_sai_vi_tri.json`:

```json
{
 "add_total_row": 0,
 "creation": "2026-09-15 00:00:00.000000",
 "disabled": 0,
 "doctype": "Report",
 "is_standard": "Yes",
 "modified": "2026-09-15 00:00:00.000000",
 "module": "Vi Tri Kho",
 "name": "Hang Nam Sai Vi Tri",
 "owner": "Administrator",
 "prepared_report": 0,
 "ref_doctype": "Location Balance",
 "report_name": "Hang Nam Sai Vi Tri",
 "report_type": "Script Report",
 "roles": [
  {"role": "System Manager"},
  {"role": "Stock Manager"},
  {"role": "Stock User"}
 ]
}
```

- [ ] **Step 4: Viết `hang_nam_sai_vi_tri.py`**

```python
"""Ô đang chứa hàng KHÁC với mặt hàng đã gán cho nhánh của nó.

Báo cáo RỖNG = trạng thái đúng.

Vì sao phải có: `ItemLocationPreference.kiem_tra_ton_mat_hang_khac` chỉ chặn
LÚC GÁN. Sau đó hàng vẫn vào sai ô được — phiếu xếp khai tay, đường huỷ chứng
từ (`hook_sle.dao_theo_o_goc`), kiểm kê. Một bất biến chỉ kiểm ở một thời điểm
rồi không ai soi lại là bất biến sẽ mục trong im lặng, và đối soát §3
(`doi_soat.py`) KHÔNG thay thế được: nó chỉ so TỔNG tồn vị trí với tồn kho
ERPNext, nên một ô chứa nhầm mặt hàng vẫn khớp tuyệt đối.
"""

import frappe
from frappe import _


def execute(filters=None):
	filters = filters or {}
	dieu_kien = ["lb.so_luong != 0", "p.vat_tu != lb.vat_tu"]
	tham_so = {}
	if filters.get("kho"):
		dieu_kien.append("lb.kho = %(kho)s")
		tham_so["kho"] = filters["kho"]

	dong = frappe.db.sql(
		f"""
		select lb.o, ifnull(sl.ma_in_nhan, sl.name) as ma_in_nhan,
		       lb.vat_tu as vat_tu_dang_co, nullif(lb.so_lo, '') as so_lo,
		       lb.so_luong, p.vat_tu as vat_tu_da_gan, p.vi_tri as nut_gan
		from `tabLocation Balance` lb
		join `tabStorage Location` sl on sl.name = lb.o
		join `tabStorage Location` s2 on s2.lft <= sl.lft and s2.rgt >= sl.rgt
		join `tabItem Location Preference` p on p.vi_tri = s2.name
		where {' and '.join(dieu_kien)}
		  and sl.lft > 0
		order by sl.lft asc, lb.vat_tu asc
		""",
		tham_so,
	)
	return _cot(), [list(d) for d in dong]


def _cot():
	return [
		{"label": _("Ô"), "fieldname": "o", "fieldtype": "Link",
		 "options": "Storage Location", "width": 160},
		{"label": _("Mã trên nhãn"), "fieldname": "ma_in_nhan", "fieldtype": "Data", "width": 130},
		{"label": _("Mặt hàng đang nằm"), "fieldname": "vat_tu_dang_co", "fieldtype": "Link",
		 "options": "Item", "width": 200},
		{"label": _("Số lô"), "fieldname": "so_lo", "fieldtype": "Link",
		 "options": "Batch", "width": 150},
		{"label": _("Số lượng"), "fieldname": "so_luong", "fieldtype": "Float", "width": 100},
		{"label": _("Đã gán cho"), "fieldname": "vat_tu_da_gan", "fieldtype": "Link",
		 "options": "Item", "width": 200},
		{"label": _("Nút gán"), "fieldname": "nut_gan", "fieldtype": "Link",
		 "options": "Storage Location", "width": 130},
	]
```

`sl.lft > 0` loại bản ghi chưa hội tụ — với `lft = 0`, phép nối `s2.lft <= 0 and
s2.rgt >= 0` khớp mọi nút 0/0 khác và đẻ ra dòng báo cáo bịa.

- [ ] **Step 5: Migrate rồi chạy test**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local migrate
bench --site erptest.local run-tests --module erpnext.vi_tri_kho.tests.test_bao_cao
```

- [ ] **Step 6: Chạy CẢ BỘ `vi_tri_kho`, tuần tự**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
for M in $(ls apps/erpnext/erpnext/vi_tri_kho/tests/test_*.py | xargs -n1 basename | sed 's/\.py//'); do
  R=$(timeout 900 bench --site erptest.local run-tests --module erpnext.vi_tri_kho.tests.$M 2>&1 | grep -E "^(OK|FAILED|Ran )" | tr '\n' ' ')
  printf "%-38s %s\n" "$M" "$R"
done
```

Mọi module phải `OK`. Module đỏ **mà không có dòng `Ran N tests`** → hết RAM, chạy lại riêng module đó.

- [ ] **Step 7: Commit**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/erpnext
python3 -m scripts.file_structure --audit
git add erpnext/vi_tri_kho/report/hang_nam_sai_vi_tri erpnext/vi_tri_kho/tests/test_bao_cao.py
git commit -m "feat(vi_tri_kho): báo cáo hàng nằm sai so với vị trí đã gán"
```

---

## Tự soát kế hoạch

**Phủ spec:**

| Mục spec | Task |
|---|---|
| §4.1 doctype | 1 |
| §4.2 đổi mã mặt hàng | 4 |
| §4.3 một kho (chỉ ghi chú, không code) | — có chủ ý |
| §5.1 trong cây | 1 |
| §5.2 kho / ZZZ / disabled | 1 |
| §5.3 chồng lấn | 2 |
| §5.4 tồn mặt hàng khác | 3 |
| §6 cây chọn | 7 |
| §7 gợi ý | 5 |
| §8 điền `den_o` | 6 |
| §9 báo cáo | 8 |
| §10 kiểm thử | rải trong 1–8 |

**Thứ tự phụ thuộc:** 1 → 2 → 3 → (4, 5, 7 song song được về mặt logic nhưng **phải chạy tuần tự** vì chung CSDL) → 6 (cần 5) → 8.

**Ba chỗ dễ làm ẩu, đã cài chốt âm:**
- Task 2 Step 6 — đột biến vị từ giao nhau, phải thấy 2 bài đỏ.
- Task 5 Step 5 — đột biến `order by name`, phải thấy đúng 1 bài đỏ.
- Task 3 `test_hang_cua_chinh_no_thi_duoc` — bỏ mệnh đề `vat_tu !=` là đỏ.

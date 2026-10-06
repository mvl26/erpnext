# Gán nhiều vị trí cố định cho một mặt hàng — Kế hoạch thi công

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cho `Item Location Preference` giữ NHIỀU nút vị trí (bảng con) thay vì một, và cho mọi nơi đọc bản gán hiểu nhiều nhánh.

**Architecture:** Thêm doctype con `Item Location Preference Row`. Bản gán cha giữ `autoname: field:vat_tu`, bỏ `kho`/`vi_tri`/`cap_do`. Mọi truy vấn "nhánh đã gán" chuyển sang join bảng con. `goi_y_o` gom mọi nhánh cùng kho vào một truy vấn mỗi bước. Một patch `[post_model_sync]` chuyển bản gán cũ thành 1 dòng rồi xoá cột cũ.

**Tech Stack:** Frappe v15, ERPNext fork Miyano, MariaDB nested set (`lft`/`rgt`), `frappe.ui.Dialog` / `frappe.ui.Tree`.

**Spec:** `docs/superpowers/specs/2026-09-22-gan-nhieu-vi-tri-design.md`

## Global Constraints

- Chạy mọi lệnh bench từ `/home/hoangvietyeuem/frappe-bench-yhct` với `--site erptest.local`. Test: `bench --site erptest.local run-tests --module erpnext.warehouse_operations.tests.<file>`.
- Python thụt lề bằng **TAB**, dòng tối đa 110 ký tự, chuỗi dùng ngoặc kép.
- Câu báo cho người dùng viết tiếng Việt, đi qua `_()`; câu báo theo dòng mở đầu bằng `"Dòng {idx}: "`.
- **Không commit** (CLAUDE.md: git chỉ khi chủ đầu tư yêu cầu rõ). Bước "Commit" của mỗi task thay bằng "để nguyên trong working tree".
- Một doctype sửa JSON thì nâng `"modified"` để `migrate` nạp lại.
- Bất biến giữ nguyên: một ô chỉ thuộc một mặt hàng; kiểm `lft`/`rgt` khác 0 TRƯỚC mọi vị từ giao nhau.

---

### Task 1: Doctype con + controller đọc nhiều dòng + patch chuyển dữ liệu

**Files:**
- Create: `erpnext/warehouse_operations/doctype/item_location_preference_row/{__init__.py,item_location_preference_row.json,item_location_preference_row.py}`
- Modify: `erpnext/warehouse_operations/doctype/item_location_preference/item_location_preference.json` (bỏ `kho`, `col_1`, `vi_tri`, `cap_do`; thêm `vi_tri_gan` Table reqd)
- Modify: `erpnext/warehouse_operations/doctype/item_location_preference/item_location_preference.py`
- Modify: `erpnext/warehouse_operations/vitri/gan.py::chu_cua_nhanh`
- Create: `erpnext/warehouse_operations/patches/v1_0/gan_nhieu_vi_tri.py` + dòng trong `erpnext/patches.txt` ở `[post_model_sync]`
- Test: `erpnext/warehouse_operations/tests/test_gan_vi_tri.py`; sửa helper `_gan` ở `test_gan_vi_tri.py`, `test_phieu_xep_vi_tri.py`, `test_nhap_lo.py`, `test_quet.py`

**Interfaces:**
- Produces: doctype `Item Location Preference Row` (`vi_tri`, `kho`, `cap_do`, `ghi_chu`); bản gán có `vi_tri_gan: list[Row]`.
- Produces: `gan.chu_cua_nhanh(lft, rgt, tru_ten=None) -> dict | None` với khoá `vat_tu`, `vi_tri`, `lft`, `rgt` (chữ ký không đổi).
- Produces: helper test `_gan(vat_tu, vi_tri, kho=KHO)`; `vi_tri` là str hoặc list[str], `kho` bị bỏ qua.

- [ ] **Step 1: Sửa helper `_gan` ở 4 file test** sang cấu trúc mới:

```python
def _gan(vat_tu, vi_tri, kho=KHO):
	"""`vi_tri` là một nút hoặc danh sách nút; `kho` giữ trong chữ ký cho các bài cũ, kho thật lấy theo nút."""
	ds = [vi_tri] if isinstance(vi_tri, str) else list(vi_tri)
	return frappe.get_doc(
		{"doctype": "Item Location Preference", "vat_tu": vat_tu, "vi_tri_gan": [{"vi_tri": v} for v in ds]}
	).insert(ignore_permissions=True)
```

Chỗ nào đọc `gan.vi_tri` / `gan.kho` / `gan.cap_do` thì đổi thành `gan.vi_tri_gan[0].vi_tri` / `.kho` / `.cap_do`.

- [ ] **Step 2: Viết test mới** (lớp `TestNhieuViTri(_Nen)` trong `test_gan_vi_tri.py`):

```python
def test_gan_hai_nhanh_khac_nhau(self):
	g = _gan(self.vt_a, [self.o1, self.o2_khac_tang])
	self.assertEqual([d.vi_tri for d in g.vi_tri_gan], [self.o1, self.o2_khac_tang])
	self.assertEqual({d.kho for d in g.vi_tri_gan}, {KHO})
	self.assertTrue(all(d.cap_do for d in g.vi_tri_gan))

def test_dong_thu_hai_chong_mat_hang_khac_bi_chan(self):
	_gan(self.vt_b, self.o2_khac_tang)
	with self.assertRaisesRegex(frappe.ValidationError, "Dòng 2: .*" + self.vt_b):
		_gan(self.vt_a, [self.o1, self.o2_khac_tang])

def test_hai_dong_tu_long_nhau_bi_chan(self):
	with self.assertRaisesRegex(frappe.ValidationError, "Dòng 2 .*dòng 1"):
		_gan(self.vt_a, [self.tang, self.o1])  # o1 nằm trong tang

def test_khong_co_dong_nao_bi_chan(self):
	with self.assertRaises(frappe.ValidationError):
		frappe.get_doc({"doctype": "Item Location Preference", "vat_tu": self.vt_a, "vi_tri_gan": []}).insert(
			ignore_permissions=True
		)
```

`o2_khac_tang` là một ô ở tầng KHÁC `self.tang` (tạo trong `setUpClass`, vd `_o("7A01010201")`).

- [ ] **Step 3: Chạy test, thấy đỏ** (`vi_tri_gan` chưa tồn tại).

- [ ] **Step 4: Tạo doctype con.** `item_location_preference_row.json`: `istable: 1`, module `Warehouse Operations`, các trường như spec §3. `vi_tri` là Link Storage Location, reqd, in_list_view, columns 3; `kho` là Link Warehouse, read_only, in_list_view, columns 3; `cap_do` là Data, read_only, in_list_view, columns 2; `ghi_chu` là Data. `.py`: `class ItemLocationPreferenceRow(Document): pass`.

- [ ] **Step 5: Sửa JSON cha:** `field_order = ["vat_tu", "vi_tri_gan", "sec_gc", "ghi_chu"]`; bỏ các field `kho`, `col_1`, `vi_tri`, `cap_do`; thêm `{"fieldname": "vi_tri_gan", "fieldtype": "Table", "label": "Vị trí gán", "options": "Item Location Preference Row", "reqd": 1}`; nâng `modified`.

- [ ] **Step 6: Controller** — `validate()` lặp qua `self.vi_tri_gan`. Mỗi dòng dựng `nut` (đọc `name, kho, lft, rgt, disabled, la_o_chua_xep, is_group`), rồi gọi theo đúng thứ tự:
  - `kiem_tra_trong_cay`;
  - `kiem_tra_nut_hop_le` (bỏ vế so `self.kho`, giữ vế kho đã bật quản lý vị trí, ô Chưa xếp, ngừng dùng);
  - `kiem_tra_chong_lan`;
  - `kiem_tra_ton_mat_hang_khac`;
  - điền `d.kho = nut.kho` và `d.cap_do`.

  Sau vòng lặp chạy `kiem_tra_tu_long_nhau()`: với mọi cặp `i < j`, nếu `a.lft <= b.rgt and a.rgt >= b.lft` thì báo *"Dòng {j} ({vi_tri j}) trùng hoặc lồng với dòng {i} ({vi_tri i}) — mỗi nhánh chỉ gán một lần."* Mọi câu báo cũ thêm tiền tố `_("Dòng {0}: ").format(d.idx)`. Các hàm con nhận `(d, nut)` thay vì đọc `self.vi_tri` / `self.nut`.

- [ ] **Step 7: `gan.chu_cua_nhanh`** đổi SQL:

```sql
select p.vat_tu as vat_tu, r.vi_tri as vi_tri, s.lft as lft, s.rgt as rgt
from `tabItem Location Preference Row` r
join `tabItem Location Preference` p on p.name = r.parent
join `tabStorage Location` s on s.name = r.vi_tri
where r.parenttype = 'Item Location Preference' and r.parentfield = 'vi_tri_gan'
  and p.name != %(tru)s and s.lft <= %(rgt)s and s.rgt >= %(lft)s
order by s.lft asc limit 1
```

- [ ] **Step 8: Patch** `gan_nhieu_vi_tri.py`:

```python
def execute():
	bang = "tabItem Location Preference"
	if not frappe.db.has_column("Item Location Preference", "vi_tri"):
		return
	for g in frappe.db.sql(f"select name, vi_tri, kho, cap_do from `{bang}` where ifnull(vi_tri,'') != ''", as_dict=True):
		if frappe.db.exists("Item Location Preference Row", {"parent": g.name, "parentfield": "vi_tri_gan"}):
			continue
		frappe.get_doc({
			"doctype": "Item Location Preference Row", "parent": g.name, "parenttype": "Item Location Preference",
			"parentfield": "vi_tri_gan", "idx": 1, "vi_tri": g.vi_tri, "kho": g.kho, "cap_do": g.cap_do,
		}).db_insert()
	for cot in ("vi_tri", "kho", "cap_do"):
		if frappe.db.has_column("Item Location Preference", cot):
			frappe.db.sql_ddl(f"alter table `{bang}` drop column `{cot}`")
```

Thêm `erpnext.warehouse_operations.patches.v1_0.gan_nhieu_vi_tri` vào cuối `[post_model_sync]`. Test patch:
- dựng bảng tạm bằng cách `alter table add column vi_tri/kho/cap_do` trong test;
- chèn một bản gán kiểu cũ bằng SQL;
- chạy `execute()` hai lần;
- khẳng định có đúng 1 dòng.

Lưu ý: DDL tự commit, xem memory [[nested-set-ro-ri-trong-test]]. Test phải dọn tay trong `tearDown`.

- [ ] **Step 9:** `bench --site erptest.local migrate`, rồi chạy `test_gan_vi_tri`, `test_phieu_xep_vi_tri`, `test_nhap_lo`, `test_quet`. Kỳ vọng tất cả xanh. Kiểm SQL: 8 bản gán cũ trên erptest thành 8 dòng.

- [ ] **Step 10:** Để nguyên trong working tree (không commit).

---

### Task 2: API cây chọn + đọc/ghi bản gán cho form Mặt hàng

**Files:**
- Modify: `erpnext/warehouse_operations/vitri/gan.py` (`cay_chon_vi_tri`, `vi_tri_cua_mat_hang`, `gan_vi_tri_cho_mat_hang`)
- Test: `erpnext/warehouse_operations/tests/test_gan_vi_tri.py`

**Interfaces:**
- Consumes: bảng con (Task 1).
- Produces: `cay_chon_vi_tri(kho, parent=None, is_root=None, tru_ten=None, dang_co=None) -> list[dict]` có thêm cột `cua_chinh_minh` (0/1).
- Produces: `vi_tri_cua_mat_hang(vat_tu) -> {"name": str, "dong": [{"vi_tri", "kho", "cap_do", "ma_in_nhan"}]} | None`.
- Produces: `gan_vi_tri_cho_mat_hang(vat_tu, vi_tri) -> {"name", "dong": [...]}`; `vi_tri` là list hoặc chuỗi JSON list.

- [ ] **Step 1: Test:**

```python
def test_cay_danh_dau_cua_chinh_minh_theo_danh_sach_dang_co(self):
	from erpnext.warehouse_operations.vitri.gan import cay_chon_vi_tri
	nut = {n.value: n for n in cay_chon_vi_tri(KHO, parent="7A0101", dang_co=frappe.as_json([self.tang]))}
	self.assertTrue(nut[self.tang].cua_chinh_minh)

def test_gan_vi_tri_cho_mat_hang_ghi_de_dung_thu_tu(self):
	from erpnext.warehouse_operations.vitri.gan import gan_vi_tri_cho_mat_hang, vi_tri_cua_mat_hang
	gan_vi_tri_cho_mat_hang(self.vt_a, [self.o2_khac_tang, self.o1])
	self.assertEqual([d["vi_tri"] for d in vi_tri_cua_mat_hang(self.vt_a)["dong"]], [self.o2_khac_tang, self.o1])
	gan_vi_tri_cho_mat_hang(self.vt_a, frappe.as_json([self.o1]))
	self.assertEqual([d["vi_tri"] for d in vi_tri_cua_mat_hang(self.vt_a)["dong"]], [self.o1])
```

Các bài cây cũ (`da_gan_cho`, `co_gan_ben_trong`, `tru_ten`) giữ nguyên kỳ vọng.

- [ ] **Step 2: Chạy, thấy đỏ.**

- [ ] **Step 3: Cài đặt.**
  - Trong `cay_chon_vi_tri`, hai subquery thay `from tabItem Location Preference p join Storage Location s2 on s2.name = p.vi_tri` bằng `from tabItem Location Preference Row r join tabStorage Location s2 on s2.name = r.vi_tri`, với `where r.parenttype='Item Location Preference' and r.parent != %(tru_ten)s …`, và chọn `r.parent as da_gan_cho`.
  - `dang_co`: parse JSON thành list tên nút, đọc `lft`/`rgt` của các nút đó (bỏ nút 0/0), rồi dựng biểu thức `(sl.lft <= %(r0)s and sl.rgt >= %(l0)s) or …`. Rỗng thì `0`. Đưa vào SELECT dạng `({bieu_thuc}) as cua_chinh_minh`.
  - `vi_tri_cua_mat_hang` đọc các dòng theo `idx`, kèm `ma_in_nhan`.
  - `gan_vi_tri_cho_mat_hang`: `frappe.parse_json` nếu là chuỗi; `set("vi_tri_gan", [...])`; `save()` hoặc `insert()` (không `ignore_permissions`).

- [ ] **Step 4: Chạy lại `test_gan_vi_tri`, xanh.**

---

### Task 3: `goi_y_o` gợi ý qua nhiều nhánh

**Files:**
- Modify: `erpnext/warehouse_operations/vitri/goi_y.py::goi_y_o`
- Test: `erpnext/warehouse_operations/tests/test_goi_y_o.py`

**Interfaces:**
- Consumes: bảng con.
- Produces: `goi_y_o(vat_tu, kho, so_lo=None) -> (str | None, str, bool)`, không đổi.

- [ ] **Step 1: Test:**

```python
def test_o_trong_o_nhanh_2_thang_o_don_cua_nhanh_1(self):
	# nhánh 1: 1 ô đang chứa CHÍNH mặt hàng (dồn được, không trống); nhánh 2: 1 ô trống
	_gan(VT, [O_NHANH_1, O_NHANH_2])
	_nap(O_NHANH_1, VT, None, 5)
	o, ly_do, hong = goi_y_o(VT, KHO)
	self.assertEqual(o, O_NHANH_2)
	self.assertIn("ô trống", ly_do)

def test_het_o_trong_moi_don_theo_thu_tu_dong(self): ...  # cả hai nhánh có hàng cùng mặt hàng → trả ô của dòng 1

def test_chi_xet_dong_cung_kho(self): ...  # dòng ở kho khác không được gợi ý

def test_tem_lo_o_nhanh_2_duoc_uu_tien(self): ...  # custom_o_in_tem thuộc nhánh 2 → trả đúng ô đó
```

Mỗi bài viết đủ phần dựng dữ liệu bằng các helper sẵn có của `test_goi_y_o.py` (`_o`, `_nap`, `_gan`).

- [ ] **Step 2: Đỏ.**

- [ ] **Step 3: Cài đặt:**
  - đọc các dòng cùng kho, theo thứ tự `idx`;
  - chặn dòng 0/0 như cũ;
  - dựng `vung = " or ".join("sl.lft between %(l{i})s and %(r{i})s")`;
  - `thu_tu = "case " + " ".join("when sl.lft between %(l{i})s and %(r{i})s then {i}") + " end"`;
  - thay `_UNG_VIEN` (vốn nhận một khoảng) bằng hàm `_ung_vien(vung)` trả chuỗi `from … where ({vung}) and …`;
  - ba truy vấn tem / trống / cùng hàng thêm `order by {thu_tu}, sl.lft`;
  - lý do bước trống: `"ô trống đầu tiên trong {vi_tri của dòng chứa ô}"`;
  - câu đầy: `"các vị trí đã gán ({ds}) đã đầy"`.

- [ ] **Step 4: Chạy `test_goi_y_o`, `test_nhap_lo`, `test_phieu_xep_vi_tri`, `test_o_tem`; xanh.**

---

### Task 4: Báo cáo sai vị trí + Quét mã tra cứu

**Files:**
- Modify: `erpnext/warehouse_operations/report/hang_nam_sai_vi_tri/hang_nam_sai_vi_tri.py`
- Modify: `erpnext/warehouse_operations/vitri/quet.py` (`_vi_tri_co_dinh`, `_tra_cuu_vat_tu`)
- Test: `test_gan_vi_tri.py` (lớp báo cáo sẵn có), `test_quet.py`

- [ ] **Step 1: Test:**
  - báo cáo không liệt kê hàng của mặt hàng A đang nằm ở nhánh 2 của chính A;
  - vẫn liệt kê hàng của B nằm trong nhánh của A;
  - `quet` trả `vi_tri_co_dinh` = `"X; Y"` khi A có 2 dòng.

- [ ] **Step 2: Đỏ.**

- [ ] **Step 3: Cài đặt:**
  - Báo cáo join `tabItem Location Preference Row r on r.vi_tri = s2.name`, `p` là `r.parent`. Điều kiện "sai" giữ `r.parent != lb.vat_tu`, cộng thêm `not exists` (một dòng khác của CHÍNH `lb.vat_tu` bao ô đó) — hàng A nằm ở nhánh A2 mà nhánh đó lồng trong nhánh B là ca không thể xảy ra vì luật chồng lấn đã chặn, nên chỉ cần đổi join. `nut_gan` = `r.vi_tri`.
  - `quet._vi_tri_co_dinh` trả `"; ".join(các vi_tri theo idx)` hoặc `None`. `_tra_cuu_vat_tu` dùng hàm đó, và `kho_co_dinh` = `"; "` các kho khác nhau.

- [ ] **Step 4: Xanh.**

---

### Task 5: Giao diện — form Mặt hàng, cây chọn, form bản gán

**Files:**
- Modify: `erpnext/public/js/warehouse_operations/item.js`
- Modify: `erpnext/public/js/warehouse_operations/cay_chon_vi_tri.js` (tham số `dang_co`, nhãn `cua_chinh_minh`, điều kiện nút chọn)
- Modify: `erpnext/warehouse_operations/doctype/item_location_preference/item_location_preference.js`
- Test: `test_giao_dien.py` (nếu có bài khoá chuỗi nút), chạy thật bằng Playwright

- [ ] **Step 1:** `cay_chon_vi_tri.js`: chữ ký `chon_vi_tri(kho, khi_chon, tru_ten, dang_co)`; `args` thêm `dang_co: JSON.stringify(dang_co || [])`; `get_label` hiện `"— đã có trong danh sách"` khi `n.cua_chinh_minh`; `condition` loại thêm `n.cua_chinh_minh`.

- [ ] **Step 2:** `item.js`:
  - `hien_vi_tri(frm, gan)` liệt kê `gan.dong` dạng `"Vị trí cố định: 1A0101-0101 (Ô, Kho…) · 1A0102 (Tầng, …)"`;
  - nút `"Gán vị trí"` mở hộp thoại có trường HTML vẽ bảng dòng (mã, cấp, kho, nút ↑ ↓ ×) từ mảng `ds` trong bộ nhớ;
  - nút phụ `"Thêm vị trí"` hỏi Kho (Link, lọc kho bật quản lý vị trí) rồi mở `chon_vi_tri(kho, cb, gan && gan.name, ds.map(x => x.vi_tri))`;
  - `cb` đẩy vào `ds` và vẽ lại;
  - nút chính `"Lưu"` gọi `gan_vi_tri_cho_mat_hang({vat_tu, vi_tri: ds.map(x => x.vi_tri)})`; thành công thì `frm.reload_doc()`.
  - Danh sách rỗng thì nút Lưu báo *"Cần ít nhất một vị trí."*

- [ ] **Step 3:** `item_location_preference.js`: nút `"Thêm vị trí từ cây"` hỏi kho rồi `chon_vi_tri(kho, (o) => { frm.add_child("vi_tri_gan", {vi_tri: o}); frm.refresh_field("vi_tri_gan"); }, tru_ten, (frm.doc.vi_tri_gan || []).map(d => d.vi_tri))`.

- [ ] **Step 4:** `node --check` ba file. Chạy thật bằng Playwright trên erptest:
  - form Mặt hàng: gán 2 vị trí, lưu, thấy 2 vị trí;
  - cây: nút trong danh sách bị mờ.

---

### Task 6: Toàn bộ test, tài liệu, chạy thật đầu-cuối

**Files:**
- Modify: `docs/warehouse_operations/HDSD-quan-ly-vi-tri-kho.md` (mục 10 "Gán vị trí cố định cho mặt hàng")

- [ ] **Step 1:** Chạy cả 37 file `erpnext.warehouse_operations.tests.*` tuần tự, ở chế độ nền. Kỳ vọng tất cả xanh.
- [ ] **Step 2:** Chạy thật trên erptest:
  - gán 2 vị trí cho một mặt hàng;
  - nhập kho một lô mới, in tem: ô trên tem rơi vào ô trống của vị trí 2 khi vị trí 1 hết ô trống;
  - xếp hàng PDA vào ô đó;
  - báo cáo "Hàng nằm sai vị trí" rỗng.

  Hoàn nguyên dữ liệu thử, kiểm đối soát khớp.
- [ ] **Step 3:** Cập nhật HDSD mục 10:
  - nhiều vị trí;
  - thứ tự gợi ý: ô trống trước bất kể vị trí, rồi dồn;
  - nhiều kho;
  - luật không chồng chính mình.
- [ ] **Step 4:** Báo cáo chủ đầu tư, hỏi commit / PR.

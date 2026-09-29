# Lấy hàng theo phiếu giao — lô FEFO, chuyển đổi đơn vị, tem kiện — Kế hoạch thi công

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lấy hàng cho phiếu giao, trên PDA và trên máy tính: gợi ý lô theo hạn dùng; lấy theo bất kỳ đơn vị nào đã khai quy đổi trên mặt hàng; ghi số kiện, in tem kiện; chặn duyệt khi chưa lấy đủ hoặc chưa in đủ tem.

**Architecture:** Mọi luật nằm ở `vitri/lay_hang.py`, và toàn bộ phép so số lượng chuyển sang ĐƠN VỊ TỒN (`stock_qty`). `Location Allocation` thêm các cột đơn vị lấy / hệ số / số kiện / số kiện đã in. Tem kiện có hàm dữ liệu riêng (`vitri/tem_kien.py`) và bố cục JS riêng. Hộp thoại lấy hàng trên máy tính và trang PDA gọi CHUNG các hàm máy chủ.

**Tech Stack:** Frappe v15, ERPNext fork Miyano, MariaDB, `frappe.ui.Dialog`, `erpnext.warehouse_operations.OQuet`, JsBarcode qua `frappe.ui.form.ControlBarcode` (khuôn `tem_lo.js`).

**Spec:** `docs/superpowers/specs/2026-09-22-lay-hang-don-vi-tem-kien-design.md`

## Global Constraints

- Bench: `/home/hoangvietyeuem/frappe-bench-yhct`, site `erptest.local`. Test: `bench --site erptest.local run-tests --module erpnext.warehouse_operations.tests.<file>`.
- Python thụt lề TAB, dòng ≤ 110 ký tự, ngoặc kép; câu báo tiếng Việt qua `_()`.
- **Không commit** khi chưa được chủ đầu tư yêu cầu (CLAUDE.md).
- Không dùng `frappe.confirm` trên màn hình có súng quét (phím Enter bấm "Có").
- Số lượng trong `Location Allocation.so_luong` luôn là **đơn vị tồn**; sổ vị trí và hook chỉ đọc cột đó.
- Doctype sửa JSON thì nâng `modified`.

---

### Task 1: Lô theo hạn dùng (Expiry) + "Lô nên lấy"

**Files:**
- Create: `erpnext/warehouse_operations/patches/v1_0/chon_lo_theo_han_dung.py`; thêm dòng vào `erpnext/patches.txt` (`[post_model_sync]`)
- Modify: `erpnext/warehouse_operations/vitri/lay_hang.py::mo_phieu_giao` (thêm `lo_nen_lay`, `lo_nen_lay_hsd`, `lo_tren_phieu_muon_hon`)
- Test: `erpnext/warehouse_operations/tests/test_lay_hang_don_vi.py` (file mới)

**Interfaces:**
- Produces: mỗi phần tử `mo_phieu_giao(...)["dong"]` có thêm `lo_nen_lay: str | None`, `lo_nen_lay_hsd: date | None`, `lo_tren_phieu_muon_hon: bool`.

- [ ] **Step 1: Test.** Tạo `test_lay_hang_don_vi.py`, dùng lại helper `test_lay_hang` (`_vat_tu`, `_o`, `_nhap_kho_lo`, `_chuyen_vao_o_lo`, `_phieu_giao`). Dựng hai lô: `LO_SOM` (HSD 2027-01-31) và `LO_MUON` (HSD 2029-12-31), cả hai có tồn trong ô. Phiếu giao chốt `LO_MUON`. Khẳng định `dong[0]["lo_nen_lay"] == LO_SOM` và `lo_tren_phieu_muon_hon is True`. Bài patch: chạy `execute()` rồi `frappe.db.get_single_value("Stock Settings", "pick_serial_and_batch_based_on") == "Expiry"`.
- [ ] **Step 2: Chạy, thấy đỏ.**
- [ ] **Step 3: Patch:**

```python
import frappe

def execute():
	frappe.db.set_single_value("Stock Settings", "pick_serial_and_batch_based_on", "Expiry")
```

- [ ] **Step 4: Cài đặt "lô nên lấy".** Trong `mo_phieu_giao`, với dòng quét được có mặt hàng quản lý lô, dùng helper `_lo_nen_lay(kho, vat_tu)`:

```sql
select lb.so_lo, b.expiry_date from `tabLocation Balance` lb join `tabBatch` b on b.name = lb.so_lo
where lb.kho=%(kho)s and lb.vat_tu=%(vt)s and lb.so_luong > 0
  and (b.expiry_date is null or b.expiry_date >= curdate())
group by lb.so_lo, b.expiry_date order by b.expiry_date is null, b.expiry_date asc limit 1
```

`lo_tren_phieu_muon_hon = bool(d.batch_no and lo_nen_lay and lo_nen_lay != d.batch_no and _han_xa_hon(hsd_cua(d.batch_no), hsd_nen_lay))`.

- [ ] **Step 5: Chạy test mới + `test_lay_hang`; xanh.** `bench migrate` để patch chạy trên erptest.

---

### Task 2: Chuyển đổi đơn vị (đường lấy hàng đo bằng đơn vị tồn)

**Files:**
- Modify: `erpnext/warehouse_operations/doctype/location_allocation/location_allocation.json` (thêm `don_vi_lay`, `so_luong_lay`, `he_so`, `so_kien`, `so_kien_da_in`)
- Modify: `erpnext/warehouse_operations/vitri/lay_hang.py`: `_ly_do_khong_quet_dong` (bỏ chặn đa đơn vị), `kiem_phan_bo_khi_luu` (so `stock_qty`), `danh_sach_phieu_giao`, `mo_phieu_giao`, `_chon_dong_ung_vien`, `ghi_da_lay`, `tach_dong_theo_lo`, `hoan_tat`, `tien_do_lay_hang`
- Test: `test_lay_hang_don_vi.py`; sửa `test_lay_hang.py::TestDongDaDonVi` (hành vi cũ "chặn" thành "lấy được")

**Interfaces:**
- Produces: `_can_ton(d) -> float` = `flt(d.stock_qty) or flt(d.qty) * (flt(d.conversion_factor) or 1)`.
- Produces: `_he_so_don_vi(vat_tu, don_vi) -> float` (đơn vị tồn = 1; không khai thì `throw`).
- Produces: `ghi_da_lay(phieu, dong_hang, so_lo, o, so_luong, lay_toi_da_theo_o=0, don_vi=None, so_kien=None) -> dict`. `so_luong` tính theo `don_vi` (mặc định đơn vị của dòng).
- Produces: phần tử `mo_phieu_giao["dong"]` có thêm `don_vi_dong`, `he_so_dong`, `can_lay_ton`, `da_lay_ton`, `don_vi_ton`, `don_vi_chon: [{"uom", "he_so"}]`. `can_lay` / `da_lay` giữ nghĩa theo **đơn vị của dòng**: `can_lay = d.qty`, `da_lay = da_lay_ton / he_so_dong`.

- [ ] **Step 1: Test** (lớp `TestDonVi`). Mặt hàng `9L-VT-DV` có `stock_uom = "Nos"`, khai thêm `9L-Hop` = 100 và `9L-Thung` = 2000, có lô; 3000 Nos nằm ở ô `O_GAN`. Các bài:
  - `test_lay_5_hop_tru_500_don_vi_ton`: phiếu giao 5 Hộp (cf 100), `ghi_da_lay(..., so_luong=5, don_vi="9L-Hop")` → phân bổ `so_luong == 500`, `so_luong_lay == 5`, `he_so == 100`, `so_kien == 5`; `mo_phieu_giao` cho `da_lay == 5`, `da_lay_ton == 500`.
  - `test_lay_bang_don_vi_ton_cho_dong_ban_theo_hop`: dòng 5 Hộp, lấy 500 Nos → đủ; `hoan_tat` duyệt được; sổ trừ 500.
  - `test_don_vi_khong_khai_bi_chan`: `don_vi="Kg"` → ValidationError "không khai đơn vị".
  - `test_vuot_ton_o_theo_don_vi_ton_bi_chan`: lấy 2 Thùng (4000) khi ô còn 3000 → chặn "chỉ còn".
  - `test_cong_don_chi_khi_cung_don_vi`: 2 Hộp + 1 Hộp cùng ô → 1 dòng phân bổ (`so_luong_lay` 3); thêm 50 Nos → dòng thứ hai.
  - `test_so_kien_mac_dinh_va_sua_duoc`: 5 Hộp → 5; 300 Nos → 1; `so_kien=3` truyền vào → 3.
  - `test_chot_thieu_dong_hop_khong_tron_bi_chan`: `9L-Hop` có `must_be_whole_number=1`; dòng 5 Hộp lấy 350 Nos, chốt thiếu, `hoan_tat` → chặn "phải tròn".
  - `test_chot_thieu_dong_hop_tron_ha_qty`: lấy 300 Nos, chốt thiếu → `qty == 3`, sổ trừ 300.
- [ ] **Step 2: Đỏ.**
- [ ] **Step 3: JSON `Location Allocation`:** thêm các trường sau `so_luong`:

```json
{"fieldname": "don_vi_lay", "fieldtype": "Link", "options": "UOM", "label": "Đơn vị lấy", "read_only": 1},
{"fieldname": "so_luong_lay", "fieldtype": "Float", "label": "SL theo đơn vị lấy", "read_only": 1},
{"fieldname": "he_so", "fieldtype": "Float", "label": "Hệ số", "read_only": 1},
{"fieldname": "so_kien", "fieldtype": "Int", "label": "Số kiện", "read_only": 1},
{"fieldname": "so_kien_da_in", "fieldtype": "Int", "label": "Kiện đã in tem", "read_only": 1, "allow_on_submit": 1}
```

- [ ] **Step 4: Cài đặt.**
  - `_can_ton(d)` như trên; thay MỌI `flt(d.qty)` / `flt(dh.qty)` dùng để so với phân bổ (dòng 396, 604, 724, 830, 923, 1381, 1610, 1639, 1726, 1751 của bản hiện tại) bằng `_can_ton(d)`.
  - `mo_phieu_giao` trả hai hệ đơn vị như ở Interfaces.
  - `_ly_do_khong_quet_dong`: xoá vế `conversion_factor not in (0, 1)`.
  - `_he_so_don_vi(vat_tu, don_vi)`: `don_vi == stock_uom` thì trả 1; không thì tra `UOM Conversion Detail` (parent=vat_tu, uom=don_vi), không có thì `throw(_("Mặt hàng {0} không khai đơn vị {1} — khai quy đổi trên mặt hàng trước.")`.
  - `ghi_da_lay`:
    - `don_vi = don_vi or d.uom or d.stock_uom`; `he_so = _he_so_don_vi(...)`;
    - `so_luong_ton = flt(so_luong) * he_so`;
    - cắt theo ô (`lay_toi_da_theo_o`) bằng đơn vị tồn, rồi quy ngược `so_luong_lay = so_luong_ton / he_so`;
    - cộng dồn khi cùng (dòng, lô, ô, `don_vi_lay`);
    - mặc định `so_kien = cint(round(so_luong_lay)) if he_so != 1 else 1`, tối thiểu 1; khi cộng dồn thì cộng cả `so_kien`;
    - `so_kien_da_in` giữ nguyên (0 cho dòng mới).
  - `hoan_tat`:
    - so `lay` (tồn) với `_can_ton(d)`;
    - chốt thiếu thì `qty_moi = lay / (flt(d.conversion_factor) or 1)`;
    - nếu `frappe.get_cached_value("UOM", d.uom, "must_be_whole_number")` và `abs(qty_moi - round(qty_moi)) > _SAI_SO` thì throw *"Dòng {0} bán theo {1}: số lấy thực phải tròn {1} (đang {2}). Lấy thêm hoặc bỏ bớt cho tròn."*;
    - `d.qty = qty_moi`.
  - `tach_dong_theo_lo`: thay `d.qty = da` (đang bỏ qua cf) bằng `d.qty = da / conv`, và dòng mới lấy phần còn lại cũng quy theo `conv`.
- [ ] **Step 5: Sửa `TestDongDaDonVi`** cho đúng hành vi mới (dòng bán theo Hộp quét được).
- [ ] **Step 6:** `bench migrate`; chạy `test_lay_hang_don_vi`, `test_lay_hang`, `test_lien_ket_phieu_giao`; xanh.

---

### Task 3: Tem kiện — dữ liệu, đánh dấu đã in, bố cục, nút In

**Files:**
- Create: `erpnext/warehouse_operations/vitri/tem_kien.py`
- Create: `erpnext/public/js/warehouse_operations/tem_kien.js` (bố cục tem 50×30)
- Modify: `erpnext/public/js/warehouse_operations/delivery_note.js` (nút "In tem kiện")
- Test: `test_lay_hang_don_vi.py` (lớp `TestTemKien`)

**Interfaces:**
- Produces: `tem_kien.du_lieu_tem_kien(phieu: str, chi_chua_in: int = 1) -> list[dict]`. Mỗi phần tử có các khoá:

  | Khoá | Nội dung |
  |---|---|
  | `dong_phan_bo` | tên dòng phân bổ |
  | `ma_hang`, `ten_hang` | mã, tên mặt hàng |
  | `so_lo`, `hsd` | lô, HSD (chuỗi `YYYY/MM/DD`) |
  | `so_luong_kien` | số lượng trong kiện kèm đơn vị, ví dụ "100 Hộp" |
  | `so_phieu` | số phiếu giao |
  | `khach` | tên khách |
  | `kien_thu`, `tong_kien` | thứ tự kiện, tổng số kiện |
  | `ma_vach` | chuỗi mã vạch (= số lô) |

- Produces: `tem_kien.danh_dau_da_in(phieu: str, dong_phan_bo: str | list | None = None) -> dict` với khoá `{"so_kien_da_in", "tong_kien"}`.
- Produces: `tem_kien.dem_kien(doc) -> tuple[int, int]` (đã in, tổng) — dùng ở Task 4 và `tien_do_lay_hang`.
- Produces (JS): `erpnext.warehouse_operations.tem_kien.in_cho_phieu(phieu, chi_chua_in)`.

- [ ] **Step 1: Test:**
  - 5 Hộp → 5 tem, `kien_thu` 1..5, `tong_kien` 5, `so_luong_kien == "1 9L-Hop"`;
  - 300 Nos chia `so_kien = 3` → 3 tem × "100 Nos";
  - hai lượt cùng (mặt hàng, lô) thì đánh số nối tiếp trên toàn phiếu (1..N);
  - `chi_chua_in=1` sau `danh_dau_da_in` → rỗng;
  - `danh_dau_da_in` trên phiếu đã duyệt vẫn chạy (`allow_on_submit`).
- [ ] **Step 2: Đỏ.**
- [ ] **Step 3: Cài đặt `tem_kien.py`.**
  - Quyền: như `lay_hang._kiem_tra_quyen` và `doc.check_permission("read")`.
  - Mỗi dòng phân bổ sinh `so_kien` tem; tem thứ k mang `so_luong_lay / so_kien` (định dạng `flt(..., 3)` bỏ `.0`) kèm `don_vi_lay`.
  - Đánh số `kien_thu` / `tong_kien` gom theo (`vat_tu`, `so_lo`) trên toàn phiếu.
  - `chi_chua_in` bỏ các tem có thứ tự trong dòng ≤ `so_kien_da_in`.
  - `danh_dau_da_in` ghi `db_set("so_kien_da_in", so_kien)` từng dòng phân bổ (qua `frappe.db.set_value` trên `Location Allocation`), không `save()` phiếu, để không đụng timestamp khi người khác đang quét.
- [ ] **Step 4: `tem_kien.js`** theo khuôn `tem_lo.js`: vẽ lưới 50×30, ô mã vạch Code 128 (chặn khi quá 188 module như tem lô), in qua `in_nhan_lo.js` (cửa sổ in nhiệt). Xong gọi `danh_dau_da_in`.
- [ ] **Step 5:** `delivery_note.js`: nút "In tem kiện" hiện khi phiếu có phân bổ; bấm thì `in_cho_phieu(frm.doc.name, 1)`. Khối tiến độ thêm "x/y kiện đã in tem".
- [ ] **Step 6: Chạy test; xanh.**

---

### Task 4: Chặn duyệt khi chưa lấy / chưa in tem

**Files:**
- Modify: `erpnext/warehouse_operations/vitri/lay_hang.py` (hàm mới `chan_duyet_chua_lay`)
- Modify: `erpnext/hooks.py` (`"Delivery Note": {"before_submit": ...}`)
- Modify: các test đang duyệt thẳng phiếu giao ở kho quản lý vị trí (`test_lay_hang.py`, `test_lien_ket_phieu_giao.py`, …): bật cờ `vi_tri_kho_bo_bat_buoc_lay_hang` qua contextmanager `bo_bat_buoc_lay_hang()` đặt trong `test_lay_hang.py`
- Test: `test_lay_hang_don_vi.py` (lớp `TestChanDuyet`)

**Interfaces:**
- Produces: `lay_hang.CO_BO_BAT_BUOC = "vi_tri_kho_bo_bat_buoc_lay_hang"`; `lay_hang.chan_duyet_chua_lay(doc, method=None)`.

- [ ] **Step 1: Test:**
  - duyệt thẳng phiếu chưa quét → chặn "chưa lấy hàng";
  - lấy đủ nhưng chưa in tem → chặn "chưa in tem";
  - in đủ → duyệt được;
  - phiếu trả hàng → không chặn;
  - phiếu chỉ có dòng dịch vụ → không chặn;
  - chốt thiếu (đã in tem phần đã lấy) → duyệt được.
- [ ] **Step 2: Đỏ.**
- [ ] **Step 3: Cài đặt:**

```python
CO_BO_BAT_BUOC = "vi_tri_kho_bo_bat_buoc_lay_hang"

def chan_duyet_chua_lay(doc, method=None):
	if doc.is_return or frappe.flags.get(CO_BO_BAT_BUOC):
		return
	from erpnext.warehouse_operations.vitri.tem_kien import dem_kien
	da = _da_lay_theo_dong(doc)
	thieu = _doc_chot_thieu(doc.name)
	for d in doc.items:
		if not _can_quet_dong(d):
			continue
		lay = flt(da.get(d.name, 0.0))
		if lay <= _SAI_SO:
			frappe.throw(_("Dòng {0} ({1}) chưa lấy hàng — bấm Lấy hàng (quét lô và ô) trước khi duyệt.").format(d.idx, d.item_code))
		if abs(lay - _can_ton(d)) > _SAI_SO and d.name not in thieu:
			frappe.throw(_("Dòng {0} ({1}) chưa lấy đủ — quét tiếp hoặc Chốt thiếu.").format(d.idx, d.item_code))
	da_in, tong = dem_kien(doc)
	if da_in < tong:
		frappe.throw(_("Còn {0} kiện chưa in tem — bấm In tem kiện trước khi duyệt.").format(tong - da_in))
```

  `hoan_tat` hạ `qty` cho dòng chốt thiếu TRƯỚC `submit()`. Vì vậy ở `before_submit` phép so `abs(lay - _can_ton(d))` đã bằng 0; vế `d.name not in thieu` chỉ còn giữ cho đường duyệt trên form.
- [ ] **Step 4:** Thêm contextmanager `bo_bat_buoc_lay_hang()` vào `test_lay_hang.py` và bọc mọi `dn.submit()` trực tiếp ở các test FEFO / cột vị trí. Chạy toàn bộ `erpnext.warehouse_operations.tests` để tìm các chỗ còn sót.
- [ ] **Step 5:** Xanh toàn bộ.

---

### Task 5: Hộp thoại lấy hàng trên máy tính + bổ sung PDA

**Files:**
- Create: `erpnext/public/js/warehouse_operations/lay_hang_dialog.js`
- Modify: `erpnext/public/js/warehouse_operations/delivery_note.js` (nút "Lấy hàng" mở hộp thoại)
- Modify: `erpnext/warehouse_operations/page/lay_hang_pda/lay_hang_pda.js` (+ `.css`): chọn đơn vị, số kiện, lô nên lấy, trạng thái tem
- Test: `test_giao_dien.py` (nếu khoá tên nút); Playwright trên erptest

**Interfaces:**
- Consumes: `quet_de_lay`, `ghi_da_lay(..., don_vi, so_kien)`, `bo_dong_da_lay`, `doi_lo`, `tach_dong_theo_lo`, `chot_thieu`, `hoan_tat`, `mo_phieu_giao` (các khoá mới ở Task 1–2), `tem_kien.in_cho_phieu`.

- [ ] **Step 1: `lay_hang_dialog.js`.**
  - `frappe.ui.Dialog({size: "extra-large"})`, gồm:
    - HTML bảng dòng: mặt hàng, lô trên phiếu / lô nên lấy, cần / đã lấy (đơn vị của dòng và đơn vị tồn), ô nên lấy;
    - ô quét `OQuet`;
    - khu "đang lấy": lô, ô, chọn đơn vị (`don_vi_chon`), số lượng, số kiện, nút **Ghi**;
    - danh sách lượt đã lấy có nút ×.
  - Luồng quét giống PDA:
    - quét lô → chọn dòng;
    - `loai = lo_khac` → yêu cầu quét lại để đổi / tách lô;
    - quét ô → điền ô;
    - bấm Ghi → `ghi_da_lay`.
  - Nút phụ: **Chốt thiếu** (theo dòng), **In tem kiện**, **Hoàn tất (duyệt)**. Nút Hoàn tất hỏi xác nhận bằng `frappe.ui.Dialog` thường, không dùng `frappe.confirm`.
- [ ] **Step 2: `delivery_note.js`:** nút "Lấy hàng" (phiếu nháp, `lay_duoc`) → `frappe.require(lay_hang_dialog.js)`, mở hộp thoại; đóng hộp thì `frm.reload_doc()`.
- [ ] **Step 3: PDA:**
  - sau khi quét lô, hiện hàng nút đơn vị (`don_vi_chon`) và ô số kiện (−/+), gửi kèm `don_vi` và `so_kien` khi quét ô;
  - dòng hiện "Lô nên lấy" kèm cảnh báo khi lô trên phiếu hết hạn muộn hơn;
  - chân trang hiện "x/y kiện đã in tem".
- [ ] **Step 4:** `node --check`. Chạy thật bằng Playwright trên erptest với mặt hàng khai 1 Thùng = 2000, 1 Hộp = 100:
  - tạo phiếu giao từ đơn bán: lô tự điền theo HSD;
  - trên máy tính lấy 5 Hộp và 20 Cái; trên PDA lấy phần còn lại;
  - In tem kiện: nội dung tem đúng;
  - duyệt bị chặn khi chưa in, qua khi đủ.

  Hoàn nguyên dữ liệu thử, kiểm đối soát khớp.

---

### Task 6: Toàn bộ test + tài liệu

- [ ] Chạy cả `erpnext.warehouse_operations` (mọi `test_*.py`, gồm cả trong thư mục doctype), tuần tự, ở chế độ nền.
- [ ] Cập nhật `docs/warehouse_operations/HDSD-quan-ly-vi-tri-kho.md` mục 14 (Lấy hàng) và `HDSD-luong-tu-A-den-Z.md` bước 9: lô theo HSD, chọn đơn vị, số kiện, In tem kiện, bắt buộc lấy hàng trước khi duyệt.
- [ ] Báo cáo chủ đầu tư; hỏi commit / PR.

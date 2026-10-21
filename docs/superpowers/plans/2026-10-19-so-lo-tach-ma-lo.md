# Tách số lô khỏi mã lô — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `Batch` có mã lô tự sinh `L26-000123` (khoá, mã vạch) và trường số lô NCC (`custom_so_lo`, được trùng) hiện ở mọi chỗ người dùng đọc.

**Architecture:** Thêm `Batch.custom_so_lo` + title field. `Batch Entry` sinh tên lô bằng naming series và nhận diện lô theo (item, số lô, hạn dùng). Máy vẫn nối bằng mã lô ở mọi bảng; chỉ lớp hiển thị đổi sang số lô, qua một module helper chung `vitri/so_lo.py`. Riêng sổ kho khách trên portal đổi khoá sang (kho, vật tư, số lô, hạn dùng) và lưu số lô.

**Tech Stack:** Frappe/ERPNext v15 (fork `mvl26/erpnext`), app `miyano_pda`, app `miyano_portal` (Vue frontend). Test: `FrappeTestCase`, chạy `bench --site erptest.local run-tests --module <module>`.

**Spec:** `docs/superpowers/specs/2026-10-19-so-lo-tach-khoi-ma-lo-design.md`. Đọc trước khi làm bất kỳ task nào. Các mã Q1–Q7, E1–E3 dưới đây trỏ vào đó.

## Global Constraints

- Mẫu mã lô: naming series **`L.YY.-.######`**, cho ra `L26-000123` (Q1). Hằng `_SERIES_MA_LO` trong `batch_entry.py`.
- Mã vạch (F10) = mã lô. Chữ dưới vạch (F11) = mã lô. Dòng "Lô …" (F6) = **số lô** (Q2, Q3, Q6).
- Nhận diện lô = (item, số lô, hạn dùng). Hạn dùng rỗng được coi như một giá trị. Khác NCC vẫn là một lô (Q4, Q5).
- Không đổi tên `Batch` cũ. Tem cũ quét phải ra đúng lô.
- Khoá JSON hiện có tên `so_lo` trong mọi payload Python→JS **giữ nghĩa mã lô** (JS gửi nó ngược lên làm khoá). Giá trị hiển thị thêm vào bằng khoá mới **`so_lo_hien_thi`**. JS luôn hiện `x.so_lo_hien_thi || x.so_lo`.
- Đặt tên tiếng Việt không dấu, comment tiếng Việt, đúng lối module `warehouse_operations`.
- Ba repo, ba nhánh, đều tách từ nhánh tích hợp mới nhất: `erpnext` `feat/so-lo-tach-ma-lo` (từ `develop`), `miyano_pda` `feat/so-lo-tach-ma-lo` (từ `main`), `miyano_portal` `feat/so-lo-tach-ma-lo` (từ `origin/develop`).
- Test chạy **tuần tự** trên `erptest.local`, vì CSDL dùng chung. `test_luong_nhap` và `test_gan_vi_tri` đang lỗi sẵn trên develop vì môi trường. So với baseline, đừng tính là hồi quy.
- Test cũ khẳng định hành vi cũ (tên lô = số lô; chặn số lô trùng giữa hai mặt hàng) **sửa theo spec**, không xoá và không làm yếu. Ghi rõ từng bài đã sửa trong commit message.

## Review Focus

1. **Lô cũ không hạn dùng, nhập lại có hạn dùng** phải dùng lại lô cũ và điền hạn dùng (E1), không đẻ lô thứ hai. → test ở Task 2.
2. **Hai dòng cùng (item, số lô, hạn dùng) trong một phiếu nhập lô** phải ra một lô. → test ở Task 2.
3. **Tem cũ** (mã vạch = tên lô cũ) quét sau migrate vẫn ra đúng lô, và `so_lo_hien_thi` = tên cũ. → test ở Task 4.
4. **Gõ tay một số lô vừa là tên lô cũ (mặt hàng X) vừa là số lô của lô mới (mặt hàng Y)** phải trả cả hai cho chọn (E3). → test ở Task 4.
5. **Portal: phiếu xuất của bệnh viện gõ số lô bao bì** phải trừ đúng dòng tồn do phiếu giao ERPNext tạo. → test ở Task 7.

---

### Task 1: Trường số lô trên `Batch` + vá dữ liệu cũ

**Files:**
- Create: `erpnext/warehouse_operations/patches/v1_0/them_so_lo_ncc.py`
- Modify: `erpnext/patches.txt` (thêm dòng sau `...v1_0.so_goi_theo_phieu_nhap`)
- Modify: `erpnext/warehouse_operations/vitri/lo_ncc.py` (thêm hàm), `erpnext/hooks.py:421-427` (`Batch.before_insert` thành list)
- Test: `erpnext/warehouse_operations/tests/test_so_lo.py` (mới)

**Interfaces:**
- Produces: field `Batch.custom_so_lo` (Data, length 140, `read_only` 1, `bold`, `in_list_view`, `in_standard_filter`, `search_index` 1, `insert_after` `batch_id`, label "Số lô", description "Số lô in trên bao bì nhà cung cấp. Có thể trùng giữa các mặt hàng — mã lô (tên bản ghi) mới là khoá."). Property Setter trên `Batch`: `title_field`=`custom_so_lo`, `show_title_field_in_link`=1, `search_fields`=`custom_so_lo,item,expiry_date`.
- Produces: `lo_ncc.dien_so_lo_neu_trong(doc, method=None) -> None`, gán `doc.custom_so_lo = doc.batch_id or doc.name` khi rỗng (E2).

- [x] **Step 1: Viết test hỏng** trong `test_so_lo.py`, class `TestTruongSoLo`:
  - `test_lo_tao_tay_tu_dien_so_lo_bang_ma`: insert `Batch` (`batch_id="SOLO-TAY-1"`, item có lô) thì `custom_so_lo == "SOLO-TAY-1"`.
  - `test_title_field_la_so_lo`: `frappe.get_meta("Batch").title_field == "custom_so_lo"` và `show_title_field_in_link == 1`.
  - `test_patch_dien_lo_cu`: tạo `Batch` rồi `frappe.db.set_value(... "custom_so_lo", None)`, chạy `them_so_lo_ncc.execute()` thì `custom_so_lo == name`. Chạy lại lần hai không lỗi, giá trị không đổi.
- [x] **Step 2:** `bench --site erptest.local run-tests --module erpnext.warehouse_operations.tests.test_so_lo`. Kỳ vọng: FAIL (thiếu field).
- [x] **Step 3: Viết patch `execute()`**:
  - `create_custom_field` theo Interfaces;
  - 3 `make_property_setter` (`for_doctype=True`);
  - `UPDATE tabBatch SET custom_so_lo = name WHERE IFNULL(custom_so_lo,'') = ''`.

  Viết docstring giải thích lý do giống `them_so_goi_va_o_in_tem.py`. Thêm hàm hook vào `lo_ncc.py`. `hooks.py`: `"before_insert": [<hàm cũ>, "erpnext.warehouse_operations.vitri.lo_ncc.dien_so_lo_neu_trong"]`, giữ nguyên comment "đúng dict con".
- [x] **Step 4:** `bench --site erptest.local migrate`, rồi chạy lại test ở Step 2. Kỳ vọng: PASS. Chạy thêm `test_lo_ncc`, kỳ vọng PASS.
- [x] **Step 5: Commit** `feat(warehouse_operations): them so lo NCC tren Batch, lo cu so lo = ma`.

### Task 2: `Batch Entry` sinh mã lô và nhận diện lô theo (item, số lô, HSD)

**Files:**
- Modify: `erpnext/warehouse_operations/doctype/batch_entry/batch_entry.py` (`kiem_tra_so_lo` :162-183, `_dam_bao_lo` :207-252, thêm `_SERIES_MA_LO`, `_tim_lo_co_san`)
- Modify: `erpnext/warehouse_operations/doctype/batch_entry_item/batch_entry_item.json` (`so_lo`: length 140, sửa description, bỏ ý "giới hạn mã vạch")
- Test: `erpnext/warehouse_operations/tests/test_nhap_lo.py`

**Interfaces:**
- Consumes: `Batch.custom_so_lo` (Task 1).
- Produces: `BatchEntry._tim_lo_co_san(self, d) -> str | None` trả tên `Batch`. Lô mới mang `batch_id = make_autoname(_SERIES_MA_LO)` và `custom_so_lo = d.so_lo`. `lo_da_tao` = mã lô (như cũ).

Thuật toán `_tim_lo_co_san`:
1. Lọc `{"item": d.vat_tu, "custom_so_lo": d.so_lo, "expiry_date": d.hsd or ("is", "not set")}`. Một kết quả thì trả nó. Nhiều hơn một thì `frappe.throw`, nêu các mã lô.
2. Không có kết quả và `d.hsd` có giá trị: lọc lại với `expiry_date` `("is","not set")`. Đúng một kết quả thì trả nó (E1, nhánh điền chỗ trống sẵn có sẽ điền HSD). Nhiều hơn một thì throw.
3. Còn lại: `None`, tức tạo lô mới.

- [x] **Step 1: Viết test hỏng** (class đang chứa `test_huy_ca_pr_lan_be_khong_khoa_chet_nhau`, dùng lại `_phieu_nhap_lo`/`self._dong`):
  - `test_hai_mat_hang_chung_so_lo_duoc_nhap`: phiếu lô cho mặt hàng A số lô `"TRUNG-1"`, rồi mặt hàng B cũng `"TRUNG-1"`. Cả hai submit được. Hai `lo_da_tao` khác nhau, cả hai khớp `^L\d{2}-\d{6}$`, và `custom_so_lo` đều `"TRUNG-1"`.
  - `test_cung_hang_so_lo_hsd_thi_dung_lai_lo`: hai phiếu cùng (A, `"LAI-1"`, `2027-01-31`) thì cùng `lo_da_tao`.
  - `test_khac_hsd_thi_tach_lo_moi`: (A, `"LAI-2"`, `2027-01-31`) và (A, `"LAI-2"`, `2027-06-30`) thì khác `lo_da_tao`.
  - `test_lo_cu_khong_hsd_duoc_dung_lai_va_dien_hsd` (E1): tạo trước `Batch` của A, `custom_so_lo` `"CU-1"`, không HSD. Phiếu (A, `"CU-1"`, `2027-01-31`) thì `lo_da_tao` = lô đó, và `expiry_date` của lô = `2027-01-31`.
  - `test_hai_dong_cung_khoa_trong_mot_phieu_ra_mot_lo`: PR hai dòng cùng mặt hàng; BE hai dòng (A, `"DOI-1"`, cùng HSD) thì hai `lo_da_tao` bằng nhau.
- [x] **Step 2:** chạy `test_nhap_lo`. Kỳ vọng: 5 bài mới FAIL. Ghi lại các bài cũ đỏ do đổi hành vi.
- [x] **Step 3: Sửa code.**
  - `kiem_tra_so_lo`: giữ strip và kiểm rỗng. Bỏ `kiem_tra_ky_tu`/`kiem_tra_do_dai` và bỏ kiểm "đã thuộc mặt hàng"; nếu import không còn dùng thì gỡ.
  - `_dam_bao_lo`: dùng `_tim_lo_co_san`. Nhánh dùng lại giữ nguyên vòng "chỉ điền chỗ trống". Nhánh tạo mới thêm `batch_id` sinh và `custom_so_lo`.
  - Cập nhật docstring đầu file và comment `validate` cho khớp (bỏ lý lẽ "kiểm trùng trước độ dài").
- [x] **Step 4: Sửa các bài cũ** đang giả định tên lô = số lô:
  - `frappe.db.exists("Batch", "<số lô>")` / `get_doc("Batch", "<số lô>")` sau một BE thì đổi sang đọc `lo_da_tao`;
  - bài chặn trùng giữa hai mặt hàng thì đổi thành khẳng định **cho phép**;
  - các bài kiểm độ dài/ký tự số lô ở BE thì xoá chỉ khi spec đã bỏ đúng luật đó, và ghi tên bài trong commit.

  Tìm thêm trong cả thư mục tests: `grep -rn "Batch Entry\|_phieu_nhap_lo" erpnext/warehouse_operations/tests`.
- [x] **Step 5:** chạy `test_nhap_lo`, `test_loi_vao_nhap_lo`, `test_luong_nhap`, `test_pr_dn_tich_hop`, `test_lo_ncc`. Kỳ vọng: PASS (riêng `test_luong_nhap` so với baseline).
- [x] **Step 6: Commit** `feat(warehouse_operations): Batch Entry sinh ma lo L.YY.-######, nhan dien lo theo (hang, so lo, HSD)`.

### Task 3: Helper hiển thị `vitri/so_lo.py`

**Files:**
- Create: `erpnext/warehouse_operations/vitri/so_lo.py`
- Test: `erpnext/warehouse_operations/tests/test_so_lo.py` (thêm class `TestHelperSoLo`)

**Interfaces:**
- Produces:
  - `so_lo_cua(ma_lo: str | None) -> str` trả `custom_so_lo`. Rỗng hoặc lô không tồn tại thì trả chính `ma_lo or ""`.
  - `so_lo_theo_ma(ds_ma: Iterable[str]) -> dict[str, str]`: một truy vấn `get_all` duy nhất, thiếu thì rơi về mã.
  - `gan_so_lo_hien_thi(dong: list[dict], khoa: str = "so_lo") -> list[dict]`: thêm `so_lo_hien_thi` cho từng dict, sửa tại chỗ và trả lại.
  - `tim_lo(ma_go: str) -> list[dict]`: mọi `Batch` có `name == ma_go` **hoặc** `custom_so_lo == ma_go`, mỗi phần tử `{ma_lo, so_lo_hien_thi, vat_tu, ten_hang, hsd}`, sắp theo `vat_tu`, `hsd` (E3).

- [ ] **Step 1: Test hỏng:**
  - `test_so_lo_theo_ma_mot_truy_van`: dùng `self.assertQueryCount(1)` nếu FrappeTestCase của bench có; không có thì kiểm kết quả đúng cho 3 mã, trong đó 1 mã không tồn tại thì trả lại chính nó.
  - `test_tim_lo_tra_ca_ten_cu_lan_so_lo_moi`: lô X tên `"ABC"`, và lô Y mã `L..` có `custom_so_lo="ABC"`. `tim_lo("ABC")` trả 2 phần tử.
- [ ] **Step 2:** chạy `test_so_lo`. Kỳ vọng: FAIL (import).
- [ ] **Step 3:** cài đặt `so_lo.py`.
- [ ] **Step 4:** chạy lại. Kỳ vọng: PASS.
- [ ] **Step 5: Commit** `feat(warehouse_operations): helper hien thi so lo`.

### Task 4: Tem và tra cứu quét

**Files:**
- Modify: `erpnext/warehouse_operations/vitri/nhap_lo.py:212-235` (`_du_lieu_mot_lo`), `vitri/tem_kien.py:92-111`, `public/js/warehouse_operations/tem_lo.js` (ô F6 xuống dòng hoặc co chữ, không cắt)
- Modify: `erpnext/warehouse_operations/vitri/quet.py` (`_tra_cuu_lo` :106-128, `_tra_cuu_khong_kiem_quyen` :298-342, `_ton_theo_o` và các bảng trả về khác trong file có `so_lo`)
- Modify: trang `erpnext/warehouse_operations/page/quet_ma_tra_cuu/*.js` (hiện danh sách chọn khi `loai == "chon_lo"`)
- Test: các file test đang khẳng định F6/F10/F11 (`grep -rln "\"F6\"\|'F6'\|F10" erpnext/warehouse_operations/tests`), `tests/test_quet.py`

**Interfaces:**
- Consumes: `so_lo_cua`, `gan_so_lo_hien_thi`, `tim_lo` (Task 3).
- Produces: `_du_lieu_mot_lo`: `F6 = f"Lô {so_lo_cua(lo.name)}"`, `F10 = F11 = lo.name`. `tem_kien`: `F6` dùng số lô; `F10`/`F11`/`ma_vach` giữ `p.so_lo or p.vat_tu`, tức mã lô. `_tra_cuu_lo` thêm `"so_lo_hien_thi"`. Gõ tay không khớp đường nào mà `tim_lo` ra ≥2 kết quả thì trả `{"loai": "chon_lo", "ds": tim_lo(ma)}`, ra 1 kết quả thì `_tra_cuu_lo(ds[0]["ma_lo"])`. Với E3 (mã vừa là tên lô vừa là số lô lô khác), kiểm `tim_lo` **trước** khi tin nhánh `batch_no` của `scan_barcode`: `len(tim_lo(ma)) >= 2` thì trả `chon_lo`.

- [ ] **Step 1: Test hỏng:**
  - tem lô từ BE số lô `"TEM-SOLO-1"` có `F6 == "Lô TEM-SOLO-1"`, `F10 == F11 == lo_da_tao`, và `F10 != "TEM-SOLO-1"`;
  - `test_tem_cu_quet_van_ra_lo` (Review Focus 3): `Batch` tên `"CU-QUET-1"` qua patch Task 1 thì `tra_cuu("CU-QUET-1")["loai"] == "lo"`, và `so_lo_hien_thi == "CU-QUET-1"`;
  - `test_go_tay_so_lo_trung_cho_chon` (Review Focus 4): lô cũ `"ABC"` (X) và lô mới số lô `"ABC"` (Y) thì `tra_cuu("ABC")["loai"] == "chon_lo"`, `len(ds) == 2`;
  - `test_go_tay_so_lo_duy_nhat_vao_thang`: một lô `L..` số lô `"DUY-1"` thì `tra_cuu("DUY-1")["loai"] == "lo"`.
- [ ] **Step 2:** chạy `test_quet` và các test tem. Kỳ vọng: FAIL.
- [ ] **Step 3:** sửa Python theo Interfaces. Sửa comment F10/F11 ("mã hoá mã lô, chữ dưới vạch là mã lô để gõ tay khi vạch mờ — anh chốt 19/10/2026"). `tem_lo.js`: ô F6 cho số lô dài tới 40 ký tự hiển thị đủ (xuống 2 dòng hoặc co cỡ chữ), theo tiền lệ co chữ đã có trong file.
- [ ] **Step 4:** chạy lại. Kỳ vọng: PASS. Chạy `test_giao_dien`, kỳ vọng PASS.
- [ ] **Step 5:** in thử một tem trên erptest (desk, nút in tem trên Batch Entry) với số lô 30 ký tự. Chụp màn hình đính vào PR. Không có trình duyệt thì ghi rõ trong PR là chưa in thử.
- [ ] **Step 6: Commit** `feat(warehouse_operations): tem in so lo, ma vach va tra cuu theo ma lo`.

### Task 5: Hiển thị số lô ở báo cáo và dữ liệu màn kho (erpnext)

**Files:**
- Modify: báo cáo `erpnext/warehouse_operations/report/{ton_kho_theo_vi_tri,doi_soat_ton_vi_tri,hang_nam_sai_vi_tri,hang_chua_xep_vi_tri}/*.py`
- Modify: `vitri/fefo.py` (:194-206), `vitri/lay_hang.py` (:115-137, :411-471), `vitri/o_tem.py` (:78-292), cùng mọi endpoint whitelisted trả danh sách có `so_lo` lên các trang `page/lay_hang_pda`, `xep_hang_pda`, `dat_o_hang_loat`
- Modify: JS các trang trên, `public/js/warehouse_operations/lay_hang_dialog.js`, `delivery_note.js`
- Test: `test_bao_cao.py`, `test_lay_hang.py`, `test_fefo.py`, `test_o_tem.py`

**Interfaces:**
- Consumes: `gan_so_lo_hien_thi`, `so_lo_theo_ma` (Task 3).
- Produces: mỗi dòng dữ liệu có `so_lo` (mã lô) thì có thêm `so_lo_hien_thi`. Báo cáo: cột Link `so_lo` thêm `"hidden": 1`, thêm cột Data `so_lo_hien_thi` nhãn "Số lô" đặt đúng vị trí cũ. JS hiện `so_lo_hien_thi || so_lo` mọi chỗ đang in số lô ra màn. **Không** đổi giá trị gửi ngược lên máy chủ.

- [ ] **Step 1: Test hỏng:**
  - mỗi báo cáo trong 4 báo cáo: một lô `L..` có `custom_so_lo="BC-1"` thì dòng ra có `so_lo_hien_thi == "BC-1"` và cột `so_lo_hien_thi` nhãn "Số lô" có trong `columns`;
  - `test_lay_hang`: endpoint gợi ý lô trả `so_lo_hien_thi`.
- [ ] **Step 2:** chạy các module test trên. Kỳ vọng: FAIL.
- [ ] **Step 3:** sửa Python. Rà JS bằng `grep -n "so_lo" <file>` và đổi **chỉ** những chỗ render ra màn.
- [ ] **Step 4:** chạy lại 4 module test, rồi `test_giao_dien`, `test_fefo_pham_vi`, `test_lay_hang_don_vi`. Kỳ vọng: PASS.
- [ ] **Step 5:** mở thử trên desk erptest một báo cáo và hộp lấy hàng trên Delivery Note. Xác nhận hiện số lô, kể cả ô Link Batch trên lưới Purchase Receipt/Delivery Note (title field Task 1). Ô nào vẫn hiện mã thì ghi vào PR.
- [ ] **Step 6: Commit** `feat(warehouse_operations): man kho va bao cao hien so lo`.

### Task 6: PDA (`miyano_pda`)

**Files:**
- Modify: `miyano_pda/miyano_pda/public/js/kho_pda/man_tra_cuu.js` (:153,188,226), `man_lay_hang.js` (:193-199,269,342), `man_xep_hang.js`, `man_dat_o.js`

**Interfaces:**
- Consumes: payload có `so_lo_hien_thi` (Task 4, 5) và `{"loai":"chon_lo","ds":[{ma_lo,so_lo_hien_thi,vat_tu,ten_hang,hsd}]}` (Task 4).

- [ ] **Step 1:** đổi mọi chỗ render số lô thành `x.so_lo_hien_thi || x.so_lo`. `man_tra_cuu.js`: xử lý `loai == "chon_lo"` bằng danh sách bấm chọn, mỗi dòng có số lô, mã hàng, tên hàng, HSD. Bấm vào thì gọi lại tra cứu với `ma_lo`.
- [ ] **Step 2:** `bench build --app miyano_pda`. Kỳ vọng: không lỗi.
- [ ] **Step 3:** mở `/kho` trên erptest (hoặc chạy test JS nếu repo có), tra cứu một số lô trùng thì thấy danh sách chọn. Không có trình duyệt thì ghi rõ trong PR.
- [ ] **Step 4: Commit** (repo `miyano_pda`) `feat(kho_pda): hien so lo, chon lo khi so lo trung`.

### Task 7: Portal — sổ kho khách khoá theo (vật tư, số lô, HSD)

**Files:**
- Modify: `miyano_portal/kho/ledger.py` (`_lot_balance_name`, `_current_qty`, `_ensure_non_negative`, `_apply_to_balance`, `post_lines`, `get_lot_balance`, `rebuild_lot_balance`)
- Modify: `miyano_portal/miyano_portal/doctype/customer_stock_lot_balance/customer_stock_lot_balance.py` (`autoname`)
- Modify: `miyano_portal/kho/delivery_hook.py` (`_lo_cua_dong` :~620-660, `_han_su_dung`)
- Modify (nếu có gọi các hàm trên): `kho/dong_phieu.py`, `kho/import_ton_dau.py`, `kho/voucher.py`, `kho/reports.py`
- Test: `miyano_portal/tests/test_kho_ledger.py`, `test_kho_delivery_hook.py`, `test_kho_issue.py`

**Interfaces:**
- Produces: `_lot_balance_name(kho, vat_tu, so_lo, han_su_dung) -> str | None`:
  - khớp đúng HSD (rỗng khớp rỗng);
  - không thấy mà `han_su_dung` có giá trị thì khớp dòng HSD rỗng (cùng quy ước E1). Nhánh "điền HSD nếu trống" sẵn có ở `_apply_to_balance` (:122) sẽ điền.

  `_current_qty`/`get_lot_balance` nhận thêm `han_su_dung`. `autoname` băm `kho::vat_tu::so_lo::han_su_dung`; bản ghi cũ giữ tên cũ. `_lo_cua_dong` trả `(so_lo_ncc, hsd, qty)` với `so_lo_ncc = Batch.custom_so_lo` (fallback mã lô), và gộp theo **(số lô, HSD)**. `LOT_KHONG_CO` giữ nguyên.

- [ ] **Step 1: Test hỏng:**
  - `test_phieu_giao_ghi_so_lo_khong_ghi_ma`: DN xuất lô `L..` có `custom_so_lo="PG-1"` thì phiếu nhập kho khách có dòng `so_lo == "PG-1"`;
  - `test_xuat_go_so_lo_tru_dung_ton_phieu_giao` (Review Focus 5): sau phiếu giao trên, phiếu xuất bệnh viện gõ `so_lo="PG-1"` cùng HSD thì trừ được và tồn giảm đúng;
  - `test_cung_so_lo_khac_hsd_hai_dong_ton`: nhập (A, `"X"`, `2027-01-31`) và (A, `"X"`, `2027-06-30`) thì 2 bản ghi `Customer Stock Lot Balance`;
  - `test_ton_cu_khong_hsd_khop_va_dien_hsd`: dòng tồn (A, `"Y"`, HSD rỗng), nhập thêm (A, `"Y"`, `2027-01-31`) thì vẫn 1 bản ghi, HSD được điền.
- [ ] **Step 2:** `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_kho_ledger` (và 2 module kia). Kỳ vọng: FAIL.
- [ ] **Step 3:** sửa theo Interfaces. Mọi nơi gọi `_current_qty`/`get_lot_balance` truyền HSD của dòng. Tìm bằng `grep -rn "_current_qty\|get_lot_balance\|_lot_balance_name" miyano_portal`.
- [ ] **Step 4:** chạy cả nhóm `test_kho_*`. Kỳ vọng: PASS.
- [ ] **Step 5:** kiểm dữ liệu erptest: `SELECT kho, vat_tu, so_lo, COUNT(*) FROM tabCustomer Stock Lot Balance GROUP BY 1,2,3 HAVING COUNT(*)>1`. Kỳ vọng 0 dòng. Có dòng thì dừng, báo lại.
- [ ] **Step 6:** màn Vue (`Kho.vue`, `PhieuXuatDetail.vue`, `PhieuNhapDetail.vue`, `BaoCaoNXT.vue`) đã hiện `so_lo`, và giờ trường đó chứa số lô, nên không cần đổi. Chỉ kiểm chỗ nào số lô trùng trong cùng một vật tư mà chưa hiện HSD kèm theo thì thêm HSD.
- [ ] **Step 7: Commit** (repo `miyano_portal`) `feat(kho): so kho khach khoa lo theo (vat tu, so lo, HSD), phieu giao ghi so lo`.

### Task 8: `miyano_wms`, dọn và tích hợp

**Files:** tuỳ kết quả Step 1.

- [ ] **Step 1:** xác định `miyano_wms` còn dùng không: báo cáo/trang của nó có trong workspace đang hiện không; `hooks.py` của nó còn `doc_events` không; module Warehouse Operations đã thay chưa. Còn dùng thì áp Task 5 cho các báo cáo trùng tên. Không dùng thì ghi lý do vào PR erpnext, không sửa.
- [ ] **Step 2:** chạy toàn bộ `erpnext.warehouse_operations.tests.*` từng module, tuần tự. So với baseline develop chạy cùng ngày. Liệt kê module đỏ kèm lý do (môi trường hay hồi quy).
- [ ] **Step 3:** cập nhật seed `miyano_portal/setup/seed_100_vat_tu.py` chỉ nếu nó gãy (nó truyền `batch_id`, hook Task 1 tự điền số lô).
- [ ] **Step 4:** ghi vào PR portal: `han_dung_khach.py` và `doi_sanh_ton.py` (nhánh `feat/hsd-toi-thieu`, `feat/doi-sanh-ton-kho-so`, chưa vào develop) có câu báo in `batch_no`. Khi các nhánh đó merge thì phải đổi sang `so_lo_cua`.
- [ ] **Step 5:** push 3 nhánh, mở 3 PR. PR erpnext ghi thứ tự deploy: **erpnext trước** (migrate chạy patch Task 1), rồi `miyano_portal`, rồi `miyano_pda`. Sau đó `bench build` cả ba và `bench restart`.

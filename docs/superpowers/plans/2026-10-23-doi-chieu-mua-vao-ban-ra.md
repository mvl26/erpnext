# Đối chiếu mua vào – bán ra: kế hoạch thực hiện

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dựng Script Report "Doi Chieu Mua Vao Ban Ra" trong module Accounts. Báo cáo đặt từng dòng hàng bán cho một khách cạnh dòng mua tương ứng của NCC (ghép SO → PO → PI), kèm nút xuất Excel theo mẫu `Công nợ T10_Himedic`.

**Architecture:** Logic chia tiền thuế và ghép/tách theo số lượng nằm trong một module Python thuần (`phan_bo.py`), nhận và trả dict, không gọi `frappe`, test nhanh. File report đọc CSDL, dựng các dict đó, gọi `phan_bo`, rồi trả về cột và dòng. `xuat_excel.py` gọi lại `execute()` và vẽ ra xlsx bằng `openpyxl`.

**Tech Stack:** Frappe v15 Script Report, Python (thụt lề tab), `openpyxl` (có sẵn trong env), test `FrappeTestCase` trên `erptest.local`.

**Spec:** `docs/superpowers/specs/2026-10-23-doi-chieu-mua-vao-ban-ra-design.md`

## Global Constraints

- Chỉ đọc chứng từ `docstatus = 1`. Không ghi gì vào CSDL.
- Quyền: chỉ **Accounts User** và **Accounts Manager**, khai ở `roles` của report. Nút xuất cũng kiểm cùng quyền qua `Report.is_permitted()`.
- Số HĐ đầu ra lấy qua `erpnext.einvoice.lookup.invoice_numbers_for([...])[si]["number"]`. Không có thì dùng tên SI. **Không đọc** `Sales Invoice.fast_invoice_no`.
- Số HĐ đầu vào là `bill_no`, nếu trống thì dùng tên PI. Ngày là `bill_date`, nếu trống thì dùng `posting_date`.
- Tên: KH lấy `customer_name`, NCC lấy `supplier_name`. Tên hàng lấy `item_name`.
- Kỳ lọc theo `posting_date` của SI. PI không bị lọc theo kỳ.
- Tiền là VND, làm tròn đến đồng bằng `flt(x, 0)`.
- Thuế từng dòng = `flt(net_amount * rate / 100, 0)`. Phần chênh so với tổng VAT của hoá đơn dồn vào dòng có `idx` lớn nhất của hoá đơn đó.
- Tài khoản VAT: đầu ra có `account_number` bắt đầu bằng `3331`, đầu vào bắt đầu bằng `1331`, cùng công ty.
- Dòng bán không ghép được thì vẫn hiện, bên NCC để trống. Khi lọc NCC thì dòng đó bị ẩn.
- Hoá đơn trả hàng (`is_return = 1`) hiện thành dòng âm bên bán, bên NCC để trống. Đây là thu hẹp quyết định §8 của spec cho bản này; spec đã sửa theo.
- File code đặt theo `scripts/file_structure/gate.py`. Test của report đặt cùng tên thư mục. Test thuần đặt ở `erpnext/accounts/test/`.
- Không commit, không tạo nhánh, trừ khi anh yêu cầu (theo CLAUDE.md). Bước "Commit" trong kế hoạch này thay bằng "để nguyên trong working tree".

## Review Focus

1. **Một dòng SO được xuất hoá đơn qua nhiều kỳ.** Hoá đơn bán của tháng trước đã "dùng" một phần dòng PI. Tháng này phải ghép từ phần PI còn lại, không ghép lại từ đầu. Test: `test_ghep_tru_phan_da_ban_ky_truoc`.
2. **Hai dòng cùng mã hàng trên một hoá đơn.** Tổng thuế vẫn phải khớp hoá đơn. Test: `test_tong_khop_hai_dong_cung_ma`.
3. **Một dòng PI chia cho hai dòng bán.** Tổng thành tiền mua của các mảnh phải bằng đúng dòng PI, không lệch 1 đồng. Test: `test_mot_dong_mua_chia_hai_dong_ban`.
4. **Khách không có hoá đơn nào trong kỳ.** Báo cáo ra 0 dòng (không có dòng TỔNG CỘNG rỗng), và Excel vẫn xuất được. Test: `test_ky_trong`.
5. **Người không có quyền gọi thẳng URL xuất Excel.** Phải bị `PermissionError`. Test: `test_xuat_excel_chan_nguoi_khong_quyen`.

---

### Task 1: Logic thuần chia thuế và ghép dòng

**Files:**
- Create: `erpnext/accounts/report/doi_chieu_mua_vao_ban_ra/__init__.py` (rỗng)
- Create: `erpnext/accounts/report/doi_chieu_mua_vao_ban_ra/phan_bo.py`
- Test: `erpnext/accounts/test/test_doi_chieu_phan_bo.py` (dùng `unittest.TestCase`, không cần CSDL)

**Interfaces:**
- Produces:
  - `chia_thue(dong: list[dict], tong_thue: float) -> None`. Mỗi dict có `idx`, `thanh_tien`, `thue_suat` (phần trăm, ví dụ `5`). Hàm gán `tien_thue` tại chỗ. Phần chênh `flt(tong_thue, 0) - Σ` dồn vào dòng có `idx` lớn nhất. Danh sách rỗng thì không làm gì.
  - `ghep(ban: list[dict], mua: dict[str, list[dict]]) -> list[dict]`.
    - `ban` đã sắp theo thứ tự thời gian. Mỗi dict có `so_detail`, `sl`, `thanh_tien`, `tien_thue`, cờ `trong_ky: bool`, và các trường hiển thị (giữ nguyên).
    - `mua` là `{so_detail: [dòng PI đã sắp theo thời gian]}`. Mỗi dòng PI có `sl`, `thanh_tien`, `tien_thue` cùng các trường hiển thị.
    - Kết quả chỉ chứa các mảnh của dòng `trong_ky`. Mỗi mảnh là `{"ban": {...}, "mua": {...} | None}`; trong `ban` và `mua`, `sl`, `thanh_tien`, `tien_thue` đã chia theo mảnh.
- Thuật toán ghép (con trỏ theo từng `so_detail`, đi lần lượt qua `ban`):
  - Mảnh SL = `min(sl bán còn lại, sl còn lại của dòng PI hiện tại)`.
  - Tiền của mảnh = tiền còn lại × mảnh / SL còn lại, làm tròn đến đồng. Mảnh cuối của một dòng (bán hoặc PI) lấy **đúng phần tiền còn lại**, nên tổng các mảnh luôn bằng dòng gốc.
  - Dòng bán ngoài kỳ (`trong_ky = False`) vẫn tiêu con trỏ nhưng không xuất ra.
  - Dòng bán có `sl <= 0`, không có `so_detail`, hoặc đã hết dòng PI: phần còn lại thành một mảnh với `mua = None`.

- [x] **Step 1: Viết test thất bại** trong `test_doi_chieu_phan_bo.py`:
  - `test_chia_thue_don_le_du_vao_dong_cuoi`: dòng `[{idx:1, thanh_tien:1611943, thue_suat:5}, {idx:2, thanh_tien:555905, thue_suat:5}]`, `tong_thue=108393`. Kỳ vọng: `[80597, 27796]`. 80597 + 27795 = 108392, phần dư 1 dồn vào idx 2.
  - `test_chia_thue_rong`: `chia_thue([], 0)` không lỗi.
  - `test_ghep_mot_mot`: bán SL 10, thành tiền 1010000, thuế 50500. Mua SL 10, thành tiền 1000000, thuế 50000. Kỳ vọng 1 mảnh, `mua.thanh_tien == 1000000`.
  - `test_mot_dong_ban_hai_dong_mua`: bán SL 10, 1000003 / thuế 50000. Mua `[SL 6, 600000 / 30000]`, `[SL 4, 400000 / 20000]`. Kỳ vọng 2 mảnh, SL `[6, 4]`, Σ thành tiền bán == 1000003, Σ thuế bán == 50000.
  - `test_mot_dong_mua_chia_hai_dong_ban`: hai dòng bán cùng `so_detail`, SL 1 và 2. Mua 1 dòng SL 3, thành tiền 100000. Kỳ vọng thành tiền mua `[33333, 66667]`.
  - `test_ghep_tru_phan_da_ban_ky_truoc`: bán ngoài kỳ SL 4, rồi bán trong kỳ SL 6. Mua `[SL 4 hoá đơn "A"]`, `[SL 6 hoá đơn "B"]`. Kỳ vọng 1 mảnh, hoá đơn mua là "B".
  - `test_ban_vuot_mua_phan_con_lai_de_trong`: bán SL 10, mua SL 6. Kỳ vọng 2 mảnh, mảnh 2 có SL 4 và `mua is None`.
  - `test_khong_co_so_detail`: `so_detail = None`. Kỳ vọng 1 mảnh, `mua is None`.
  - `test_dong_tra_hang_am`: SL -2. Kỳ vọng 1 mảnh, `mua is None`, SL -2.
- [x] **Step 2: Chạy, kỳ vọng FAIL (ImportError)**
  `cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests --module erpnext.accounts.test.test_doi_chieu_phan_bo`
- [x] **Step 3: Viết `phan_bo.py`** theo Interfaces. Chỉ import `copy` và `frappe.utils.flt`.
- [x] **Step 4: Chạy lại, kỳ vọng 9 test OK.**

### Task 2: Report (đọc CSDL, cột, bộ lọc)

**Files:**
- Create: `erpnext/accounts/report/doi_chieu_mua_vao_ban_ra/doi_chieu_mua_vao_ban_ra.json`
  - `report_type: "Script Report"`, `module: "Accounts"`, `ref_doctype: "Sales Invoice"`.
  - `name` và `report_name`: "Doi Chieu Mua Vao Ban Ra".
  - `roles`: Accounts Manager, Accounts User. `add_total_row: 0`.
- Create: `erpnext/accounts/report/doi_chieu_mua_vao_ban_ra/doi_chieu_mua_vao_ban_ra.py`
- Create: `erpnext/accounts/report/doi_chieu_mua_vao_ban_ra/doi_chieu_mua_vao_ban_ra.js`
- Test: `erpnext/accounts/report/doi_chieu_mua_vao_ban_ra/test_doi_chieu_mua_vao_ban_ra.py`
- Modify: `docs/superpowers/specs/2026-10-23-doi-chieu-mua-vao-ban-ra-design.md` §8, dòng trả hàng (theo Global Constraints).

**Interfaces:**
- Consumes: `phan_bo.chia_thue`, `phan_bo.ghep`.
- Produces:
  - `execute(filters) -> (columns, data)`.
    - Mỗi dòng của `data` có các key: `stt`, `kh`, `so_hd_ban`, `ngay_hd_ban`, `ten_hang_ban`, `dvt_ban`, `sl_ban`, `don_gia_ban`, `thanh_tien_ban`, `thue_suat_ban`, `tien_thue_ban`, `tong_ban`, `ncc`, `so_hd_mua`, `ngay_hd_mua`, `ten_hang_mua`, `dvt_mua`, `sl_mua`, `don_gia_mua`, `thanh_tien_mua`, `thue_suat_mua`, `tien_thue_mua`, `tong_mua`, `sales_invoice`, `purchase_invoice`.
    - Dòng cuối là `{"ten_hang_ban": "TỔNG CỘNG", "la_tong": 1, …}`, chỉ có tổng của thành tiền, thuế, tổng sau thuế hai bên. Không có dòng dữ liệu thì không có dòng tổng.
  - `khoang_ky(filters) -> tuple[date, date, str]`, nhãn dạng `"THÁNG 10.2026"` hoặc `"TỪ 01/10/2026 ĐẾN 20/10/2026"`.
  - Bộ lọc: `company` (bắt buộc, mặc định công ty của người dùng), `customer` (bắt buộc), `thang` (Data dạng `MM-YYYY`, mặc định tháng hiện tại), `from_date`/`to_date` (có đủ cả hai thì ghi đè `thang`), `supplier` (không bắt buộc).
  - Cột: hiển thị theo thứ tự mẫu, nhãn đúng như spec §6. Tiền dùng kiểu `Currency`, SL dùng `Float`, thuế suất dùng `Percent`. `sales_invoice` / `purchase_invoice` là `Link` đặt ở cuối.
- Đọc dữ liệu, mỗi bước một truy vấn gom:
  1. Dòng SI trong kỳ của khách/công ty, cùng **mọi dòng** của các SI đó (để chia thuế).
  2. Dòng SI ngoài kỳ (`posting_date < from_date`, không phải trả hàng) có `so_detail` thuộc tập ở bước 1, để tiêu con trỏ.
  3. Dòng PO có `sales_order_item` thuộc tập đó.
  4. Dòng PI có `po_detail` thuộc tập dòng PO, PI không phải trả hàng, cùng mọi dòng của các PI đó.
- Thuế suất của dòng: `item_tax_rate` (JSON `{tài khoản: thuế suất}`), lấy tài khoản VAT đầu tiên. Không có thì lấy `rate` của dòng thuế `On Net Total` thuộc tài khoản VAT của hoá đơn.
- Tổng VAT của hoá đơn = Σ `base_tax_amount_after_discount_amount` của các dòng thuế thuộc tài khoản VAT.
- Sắp xếp đầu ra theo (`posting_date`, `so_hd_ban`, `idx`). STT đánh từ 1.

- [x] **Step 1: Viết test thất bại** (`FrappeTestCase`, công ty `Miyano`, kho `Stores - M`).
  - Dữ liệu dùng chung:
    - Khách và NCC có hậu tố `frappe.generate_hash(length=6)`. Mặt hàng lấy từ `erpnext.einvoice.tests.test_fixtures.ensure_item()`.
    - Hàm trợ giúp `_chuoi(qty_so, rate_ban, rate_mua, pi_specs, ngay_si)`: tạo SO (có dòng VAT 5% vào TK `3331x`), rồi PO qua `sales_order.make_purchase_order(so, [{"item_code": …}])`, đặt supplier và VAT 5% vào TK `1331x`. Mỗi spec `(qty, bill_no, bill_date)` tạo một PI qua `purchase_order.make_purchase_invoice`. SI tạo qua `sales_order.make_sales_invoice`, `update_stock = 0`.
  - `test_ghep_mot_dong`: SO SL 10, giá 101000, PO giá 100000, PI `bill_no "00011069"`. Kỳ vọng 1 dòng dữ liệu cùng dòng tổng:
    - `so_hd_ban == si.name`, `thanh_tien_ban == 1010000`, `tien_thue_ban == 50500`;
    - `ncc == supplier_name`, `so_hd_mua == "00011069"`, `thanh_tien_mua == 1000000`, `tien_thue_mua == 50000`;
    - `thue_suat_ban == 5`.
  - `test_khong_ghep_van_hien`: SI lập thẳng, không qua SO. Kỳ vọng `ncc` rỗng và `thanh_tien_mua` là `None`.
  - `test_mot_dong_ban_hai_hd_mua`: hai PI SL 6 và 4. Kỳ vọng 2 dòng, `so_hd_mua` lần lượt là `["A", "B"]`.
  - `test_loc_ncc`: có một dòng ghép được và một dòng không ghép. Lọc `supplier` thì chỉ còn dòng ghép được.
  - `test_tong_khop_hai_dong_cung_ma`: SI lập thẳng có 2 dòng cùng mã, giá 1611943 và 555905, VAT 5%. Kỳ vọng dòng tổng: `thanh_tien_ban == si.net_total`, `tien_thue_ban == si.total_taxes_and_charges`.
  - `test_ky_loc_theo_ngay_ban`: PI ngày tháng trước vẫn hiện. SI tháng trước không có trong báo cáo tháng này.
  - `test_ky_trong`: khách mới, không có hoá đơn. Kỳ vọng `data == []`.
  - `test_khoang_ky`: `{"thang": "10-2026"}` cho `(2026-10-01, 2026-10-31, "THÁNG 10.2026")`. Có `from_date`/`to_date` thì nhãn là `"TỪ 01/10/2026 ĐẾN 20/10/2026"`.
- [x] **Step 2: Chạy, kỳ vọng FAIL.**
  `bench --site erptest.local run-tests --module erpnext.accounts.report.doi_chieu_mua_vao_ban_ra.test_doi_chieu_mua_vao_ban_ra`
- [x] **Step 3: Viết `.json`, `.py`, `.js`.**
  - `.js` khai `frappe.query_reports["Doi Chieu Mua Vao Ban Ra"]` với bộ lọc như trên.
  - `formatter` in đậm dòng `la_tong`.
  - `onload` thêm nút "Xuất Excel theo mẫu" (gọi Task 3).
- [x] **Step 4: Chạy lại, kỳ vọng OK.** Chạy thêm test của Task 1.
- [x] **Step 5:** `bench --site erptest.local migrate`. Mở `/app/query-report/Doi Chieu Mua Vao Ban Ra` trên erptest để xem bộ lọc và cột hiện đúng.

### Task 3: Xuất Excel theo mẫu

**Files:**
- Create: `erpnext/accounts/report/doi_chieu_mua_vao_ban_ra/xuat_excel.py`
- Modify: `doi_chieu_mua_vao_ban_ra.js` (nút gọi URL)
- Test: thêm vào `test_doi_chieu_mua_vao_ban_ra.py`

**Interfaces:**
- Consumes: `execute`, `khoang_ky` (Task 2).
- Produces:
  - `dung_workbook(filters) -> bytes` (thuần, để test đọc lại).
  - `@frappe.whitelist() xuat(filters: str)`: kiểm `frappe.get_doc("Report", "Doi Chieu Mua Vao Ban Ra").is_permitted()`, sai thì `frappe.throw(..., frappe.PermissionError)`. Đặt `frappe.response.filename / filecontent / type = "binary"`.
- Bố cục file:
  - A1:W1 gộp ô, nội dung `f"TỔNG HỢP ĐẦU VÀO - RA CỦA KHÁCH HÀNG {customer_name.upper()} {nhãn kỳ}"`.
  - B3:L3 gộp ô ghi "KHÁCH HÀNG …", M3:W3 gộp ô ghi "NHÀ CUNG CẤP".
  - Dòng 4 là tiêu đề cột y như mẫu ("STT", "KH", "Số HĐ đầu ra", … "Tổng sau thuế").
  - Dữ liệu bắt đầu từ dòng 5. Dòng tổng ghi "TỔNG CỘNG" ở cột E.
  - Định dạng: tiền `#,##0`, đơn giá `#,##0.##`, thuế suất `0%` (ghi giá trị dạng phân số, ví dụ 0.05), ngày `dd/mm/yyyy`.
  - Tên file `Doi chieu mua ban_{customer}_{thang hoặc from_to}.xlsx`.

- [x] **Step 1: Viết test thất bại.**
  - `test_xuat_excel_bo_cuc`: dùng dữ liệu `test_ghep_mot_dong`. `openpyxl.load_workbook(BytesIO(dung_workbook(f)))`, rồi kiểm:
    - `"THÁNG" in A1`, `B3.startswith("KHÁCH HÀNG")`, `M3 == "NHÀ CUNG CẤP"`;
    - `C4 == "Số HĐ đầu ra"`, `N4 == "Số HĐ đầu vào"`;
    - `I5 == 1010000`, `T5 == 1000000`;
    - `E6 == "TỔNG CỘNG"`;
    - `J5.number_format == "0%"` và `J5.value == 0.05`.
  - `test_xuat_excel_ky_trong`: không có dữ liệu thì vẫn ra file có tiêu đề.
  - `test_xuat_excel_chan_nguoi_khong_quyen`: tạo user chỉ có role "Kế toán HĐĐT" (nếu role đó không có thì dùng "Sales User"), `frappe.set_user(...)`. Gọi `xuat(json.dumps(f))` thì phải ra `frappe.PermissionError`. Gọi `frappe.set_user("Administrator")` ở `tearDown`.
- [x] **Step 2: Chạy, kỳ vọng FAIL.**
- [x] **Step 3: Viết `xuat_excel.py` và nút JS.** Nút mở `/api/method/erpnext.accounts.report.doi_chieu_mua_vao_ban_ra.xuat_excel.xuat?filters=<JSON>`.
- [x] **Step 4: Chạy toàn bộ test của Task 1 đến Task 3, kỳ vọng OK.** Chạy `ruff check` và `ruff format --check` trên thư mục report và file test.
- [x] **Step 5:** `bench build --app erpnext` không cần, vì JS của report nạp động. Bấm nút trên erptest rồi mở file xlsx để so với mẫu.

# TKKT_10 — Thiết kế kỹ thuật & kế hoạch build: Biên bản đối chiếu công nợ (NCC 331 / KH 131)

| Mục | Nội dung |
|---|---|
| Căn cứ nghiệp vụ | `BA_BienBanDoiChieuCongNo.md` **V7 (bản chốt)** · `SRS_10_BienBanDoiChieuCongNo_20260917_V0.2.md` **V1.1** (baseline build 21/09/2026) · mẫu `BB đối chiếu công nợ.xlsx` |
| Người đọc | Dev / AI coding thực hiện build |
| Repo | app `erpnext` (Miyano ERP), bench `/home/miyano/frappe-bench`, site `miyano` |
| Ngày | 21/09/2026 |

> **Nguồn chân lý.** BA/SRS quyết định *làm gì*; tài liệu này quyết định *làm thế nào* trong repo. Khi hai bên lệch nhau: SRS V1.0 thắng về nghiệp vụ — dừng lại và báo, không tự chọn. Mã quyết định `Dxx`, `FR-xx`, `Txx` trỏ về SRS/BA.

---

## 0. Việc phải xử lý trước khi build (đã kiểm tra trên site `miyano` ngày 21/09)

| # | Hiện trạng thật | Ảnh hưởng | Cần làm | Chặn |
|---|---|---|---|---|
| E1 | **Scheduler của site đang TẮT** (`is_scheduler_disabled() = True`) | Job ngày 01 và nhắc hạn ngày 06 không chạy; email nằm trong hàng đợi không được đẩy đi (Email Queue chỉ được đẩy bởi job `frappe.email.queue.flush`) — việc email có tới được hay không nằm ngoài phạm vi đợt này (D21), nhưng job ngày 01 vẫn cần scheduler | Kiểm tra trên **production**; bật bằng `bench --site <site> enable-scheduler`. Lưu ý: tiến trình `frappe schedule` vẫn chạy dù site tắt scheduler — `ps` không chứng minh được gì | Có — cho go-live |
| E2 | Hộp thư gửi đi mặc định của hệ thống là **`AssetCore Notifications` <snonamevx@gmail.com>**; mẫu giấy in `mvl.invoices2024@gmail.com` | Nếu "dùng hộp thư hệ thống hiện có" như BA ghi, biên bản gửi đối tác sẽ đi từ địa chỉ của AssetCore | ⚠️ **Chốt địa chỉ gửi.** Thiết kế thêm field `sender_email_account` trong Settings; để trống = hộp thư mặc định | Có — cho go-live |
| E3 | Company `Miyano` **chưa có MST** (`tax_id` rỗng); chưa có Letter Head | Bản in thiếu MST/địa chỉ bên Miyano | Nhập MST `0109529507`, địa chỉ trụ sở, SĐT vào Company/Address; print format lấy từ đó (không hard-code) | Có — cho UAT bản in |
| E4 | TK `331 - Phải trả cho người bán - M`, `131 - Phải thu của khách hàng - M`: tài khoản lá, VND. Site có 9 NCC, 4 KH, 22 GL Entry | Đủ để test | Không | Không |
| E5 | Time zone site = `Asia/Ho_Chi_Minh`, date format `dd-mm-yyyy` | NFR-07 đạt sẵn | Không | Không |
| E6 | Chưa có field nào trùng tên với 6 Custom Field sẽ thêm trên Supplier/Customer (chỉ có `irs_1099`, `exempt_from_sales_tax`) | Không xung đột | Không | Không |

---

## 1. Cấu trúc module (D19)

Module mới **`Debt Reconciliation`**, thư mục `erpnext/debt_reconciliation/`.

```
erpnext/
├── modules.txt                                   # + dòng "Debt Reconciliation" (xem 1.1)
├── hooks.py                                      # + scheduler_events (mục 6, 8, 9)
├── patches.txt                                   # + 1 patch [post_model_sync] (mục 11)
├── patches/v15_0/setup_debt_reconciliation.py    # gọi setup.run()
├── regional/report/so_chi_tiet_cong_no/
│   └── so_chi_tiet_cong_no.js                    # MỚI — bộ lọc còn thiếu (R4 BA)
└── debt_reconciliation/
    ├── __init__.py
    ├── constants.py            # giá trị status, chiều dư, nguồn tạo
    ├── figures.py              # HÀM TÍNH SỐ DÙNG CHUNG (mục 3) — thuần, không ghi DB
    ├── generation.py           # sinh biên bản: job + hộp thoại + lập 1 đối tác (mục 4)
    ├── publishing.py           # render PDF, gửi email, đồng bộ trạng thái email (mục 6)
    ├── reminders.py            # nhắc hạn ngày 06 (mục 8)
    ├── setup.py                # custom field, email template, giá trị mặc định (mục 11)
    ├── tasks.py                # các hàm scheduler gọi vào
    ├── doctype/
    │   ├── debt_reconciliation_statement/   # .json .py .js _list.js test_*.py
    │   └── debt_reconciliation_settings/    # Single
    ├── print_format/
    │   ├── bb_dccn_ncc_331/                  # Jinja
    │   └── bb_dccn_kh_131/                   # Jinja — khác bố cục khối [ii] (D18)
    ├── report/
    │   ├── tinh_trang_doi_chieu_cong_no/     # FR-15a
    │   └── doi_chieu_tong_cong_no/           # FR-15b: Σ biên bản vs số dư TK
    ├── number_card/  workspace/              # FR-15 dashboard
    └── tests/
        ├── test_figures.py
        └── test_generation.py
```

### 1.1 Đăng ký module
- `erpnext/modules.txt` **không có ký tự xuống dòng ở cuối** (dòng cuối là `EDI`). Thêm bằng cách nối `\nDebt Reconciliation` — nếu nối thẳng sẽ thành `EDIDebt Reconciliation`.
- `bench --site miyano migrate` tự tạo `Module Def`.
- Mọi DocType/Report/Print Format/Number Card trong module khai báo `"module": "Debt Reconciliation"`.

---

## 2. Mô hình dữ liệu

### 2.1 DocType `Debt Reconciliation Statement` (Biên bản đối chiếu công nợ)

Thuộc tính: `is_submittable = 1`, `track_changes = 1`, `autoname = "DCCN-.YYYY.-.#####"` (**ID bản ghi do hệ thống tự sinh, không có field `naming_series` cho người dùng chọn** — D8), `title_field = "party_name"`, `sort_field = "from_date"`.

`AOS` = `allow_on_submit` (sửa được sau khi Duyệt).

| Section | fieldname | Label (VI) | fieldtype / options | Bắt buộc | RO | AOS | Ghi chú |
|---|---|---|---|---|---|---|---|
| Chung | company | Công ty | Link Company | ✔ | | | default `frappe.defaults.get_user_default("Company")` |
| | party_type | Loại đối tác | Select `Supplier\nCustomer` | ✔ | | | |
| | party | Đối tác | Dynamic Link → `party_type` | ✔ | | | |
| | party_name | Tên đối tác | Data | | ✔ | | fetch khi chọn party |
| | from_date / to_date | Kỳ từ ngày / đến ngày | Date | ✔ | | | validate tròn tháng (R-c) |
| | posting_date | Ngày lập | Date | ✔ | | | default hôm nay |
| | statement_no | Số biên bản | Data | ✔ | ✔ | | `{MM}.SL MVL-…./{YYYY}` theo `to_date` (D17) — **không unique** |
| | creation_source | Nguồn tạo | Select `Tự động\nThủ công` | ✔ | ✔ | | R-g |
| | status | Trạng thái | Select (mục 5) | ✔ | ✔ | ✔ | chỉ code đổi |
| | response_deadline | Hạn phản hồi & nhận bản ký | Date | ✔ | ✔ | | ngày `response_deadline_day` tháng sau `to_date` (D10) |
| | amended_from | Sửa đổi từ | Link self | | ✔ | | chuẩn Frappe |
| Đối tác & căn cứ | party_tax_id | MST đối tác | Data | | ✔ | | Supplier/Customer.`tax_id` |
| | party_address | Địa chỉ đối tác | Small Text | | ✔ | | địa chỉ mặc định (mục 4.3) |
| | party_representative / _title | Đại diện / Chức vụ đối tác | Data | | | | từ custom field (FR-02) |
| | framework_contract_no / _date | Số / Ngày HĐ nguyên tắc | Data / Date | | | | in "…" nếu trống |
| | reconciliation_email | Email gửi đối chiếu | Data (Email) | | | | sửa được khi Nháp |
| | company_representative / _title | Đại diện / Chức vụ Miyano | Data | ✔ | | | default từ Settings |
| Số liệu | opening_principal | Dư đầu kỳ — gốc | Currency | ✔ | ✔ | | \|G_đ\| |
| | opening_interest | Dư đầu kỳ — lãi quá hạn | Currency | | | | nhập tay, ≥ 0 (D12) |
| | opening_direction | Chiều dư đầu kỳ | Select `Dư Nợ\nDư Có\nBằng 0` | ✔ | ✔ | | |
| | debit_in_period | Phát sinh Nợ — gốc | Currency | ✔ | ✔ | | D |
| | credit_in_period | Phát sinh Có — gốc | Currency | ✔ | ✔ | | C |
| | interest_in_period | Lãi quá hạn phát sinh | Currency | | | | nhập tay, ≥ 0; NCC cộng vào Có, KH cộng vào Nợ (D18) |
| | closing_balance | Dư cuối kỳ | Currency | ✔ | ✔ | | \|Cuối\| |
| | balance_direction | Chiều dư cuối kỳ | Select `Dư Nợ\nDư Có\nBằng 0` | ✔ | ✔ | | |
| | amount_in_words | Số tiền bằng chữ | Small Text | ✔ | ✔ | | mục 7.3 |
| | figures_fetched_on | Thời điểm lấy số liệu | Datetime | ✔ | ✔ | | bằng chứng "khớp GL tại thời điểm lấy" (NFR-03) |
| | missing_party_warning | Cảnh báo | Small Text | | ✔ | | thiếu email / thiếu HĐ / đối tác không đạt D1 |
| Gửi | sent_on | Thời điểm gửi | Datetime | | ✔ | ✔ | |
| | sent_pdf | PDF đã gửi | Attach | | ✔ | ✔ | |
| | email_queue | Email Queue | Link Email Queue (hidden) | | ✔ | ✔ | mục 6.2 |
| | send_error | Lỗi gửi | Small Text | | ✔ | ✔ | |
| Xác nhận | partner_response | Phản hồi đối soát | Select `Chưa phản hồi\nKhớp\nChưa khớp` | ✔ | ✔ | ✔ | default `Chưa phản hồi` |
| | responded_on | Ngày phản hồi | Date | | ✔ | ✔ | |
| | confirmation_method | Cách xác nhận | Select `\nC1 – Bản cứng\nC2 – Ký điện tử` | | | ✔ | bắt buộc khi Đã xác nhận |
| | signed_copy | Bản xác nhận có ký | Attach | | | ✔ | bắt buộc khi Đã xác nhận |
| | confirmed_on | Ngày xác nhận | Date | | ✔ | ✔ | |
| | confirmed_via | Kênh xác nhận | Select `Thủ công\nPortal` | | ✔ | ✔ | default Thủ công (FR-18) |
| Chênh lệch | dispute_amount | Số theo đối tác | Currency | | | ✔ | bắt buộc khi Chênh lệch |
| | dispute_note | Diễn giải chênh lệch | Small Text | | | ✔ | bắt buộc khi Chênh lệch |
| | dispute_resolution | Kết quả xử lý | Small Text | | | ✔ | |

Index DB: thêm `search_index = 1` cho `party`, `from_date`, `status` (truy vấn chống trùng và danh sách theo kỳ).

**Không đặt unique index** trên `statement_no` (D17) hay trên cặp (party, kỳ) — vì bản đã Hủy (`docstatus = 2`) phải được phép trùng kỳ với bản Amend. Chống trùng làm trong code (mục 4.4).

### 2.2 DocType `Debt Reconciliation Settings` (Single — FR-03)

| fieldname | Label | Kiểu | Default |
|---|---|---|---|
| auto_generate | Tự động sinh đầu tháng | Check | 1 |
| generation_day | Ngày sinh | Int (1–28) | 1 |
| generation_hour | Giờ sinh | Int (0–23) | 10 |
| response_deadline_day | Ngày hạn phản hồi & nhận bản ký | Int (1–28) | 6 |
| payable_account_number | Số TK phải trả | Data | `331` |
| receivable_account_number | Số TK phải thu | Data | `131` |
| company_representative / _title | Đại diện / Chức vụ Miyano | Data | `Bà Đoàn Ngọc Anh` / `Giám đốc vận hành` |
| contact_line | Dòng liên hệ | Data | `Ms Hà 0949.723.444` |
| hard_copy_address | Địa chỉ nhận bản cứng | Small Text | VPGD LK21. N03… |
| sender_email_account | Hộp thư gửi | Link Email Account | trống = mặc định (⚠️ E2) |
| cc_emails | Email CC nội bộ | Small Text | |
| email_template | Mẫu email | Link Email Template | tạo sẵn bởi setup |
| reminder_recipients | Người nhận nhắc hạn | Small Text (email, mỗi dòng 1) | |

Lưu số tài khoản (`account_number`) thay vì Link Account: tài khoản là theo công ty, còn số hiệu là chung (D7).

### 2.3 Custom Field trên Supplier và Customer (FR-02)

Tạo bằng `create_custom_fields(..., update=True)` trong `debt_reconciliation/setup.py`, có `"module": "Debt Reconciliation"` để xuất/nhận theo module. Cùng một bộ cho cả hai DocType:

| fieldname | Label | Kiểu |
|---|---|---|
| dr_section | Đối chiếu công nợ | Section Break (collapsible), `insert_after: "tax_id"` |
| framework_contract_no | Số HĐ nguyên tắc | Data |
| framework_contract_date | Ngày HĐ nguyên tắc | Date |
| representative_name | Người đại diện | Data |
| representative_title | Chức vụ | Data |
| reconciliation_email | Email nhận đối chiếu | Data (options Email) |
| exclude_reconciliation | Loại trừ đối chiếu | Check |

Fallback email khi `reconciliation_email` trống: field `email_id` sẵn có của Supplier/Customer.

---

## 3. Hàm tính số dùng chung — `debt_reconciliation/figures.py` (FR-05, D7, D9, D11, D12, D18)

Một hàm thuần, **không ghi DB**, được gọi bởi cả job (FR-04), nút "Lấy số liệu từ sổ" và hộp thoại (FR-20). Đây là trái tim của tính năng — viết và test trước mọi thứ khác.

### 3.1 Tập tài khoản (sửa 21/09 — xem ghi chú)

```python
def get_party_accounts(company, party_type, throw=True) -> list[str]:
    number = "331" / "131" theo Settings
    # 1. mọi TK lá có số hiệu bắt đầu bằng number — bất kể vị trí trên cây
    accounts = {Account lá của company có account_number LIKE f"{number}%"}
    # 2. cộng TK lá dưới node number trên cây (phòng TK con chưa đặt số hiệu)
    for root in Account nhóm có account_number == number: accounts |= lá trong get_descendants_of(root)
    if not accounts and throw: frappe.throw(...)            # UC-01 E3
    return sorted(accounts)
```

**Ghi chú lỗi đã gặp (21/09):** bản đầu chỉ lấy theo cây (331 + con cháu của 331). Trên production, `3311 - Phải trả người bán ngắn hạn` và `3312 - Trả trước cho người bán` nằm dưới nhóm `Tài khoản phải trả`, **ngang hàng** với 331 → bị bỏ sót, biên bản ra toàn 0 trong khi Sổ chi tiết công nợ (lấy theo tiền tố) vẫn có số. Nay báo cáo `so_chi_tiet_cong_no` gọi chung hàm này. Test: `TestSiblingChildAccounts` trong `tests/test_figures.py`.

### 3.2 Truy vấn GL (một câu cho cả đầu kỳ và trong kỳ)

```sql
SELECT
  SUM(CASE WHEN posting_date <  %(from)s THEN debit  ELSE 0 END) AS d0,
  SUM(CASE WHEN posting_date <  %(from)s THEN credit ELSE 0 END) AS c0,
  SUM(CASE WHEN posting_date >= %(from)s THEN debit  ELSE 0 END) AS d,
  SUM(CASE WHEN posting_date >= %(from)s THEN credit ELSE 0 END) AS c
FROM `tabGL Entry`
WHERE company = %(company)s AND is_cancelled = 0
  AND party_type = %(party_type)s AND party = %(party)s
  AND account IN %(accounts)s
  AND posting_date <= %(to)s
```

Bản hàng loạt (job/hộp thoại) dùng cùng câu, bỏ điều kiện `party` và thêm `GROUP BY party` — một truy vấn cho cả kỳ, không N+1 (NFR-01).

### 3.3 Công thức (bản sao nguyên văn SRS 12.6 — D18)

| | NCC 331 | KH 131 |
|---|---|---|
| `G_đ` | `c0 − d0` ⟵ **đổi dấu** so với quy ước `Nợ − Có` của ERPNext | `d0 − c0` |
| `Đầu` | `G_đ + L_đ` | `G_đ + L_đ` |
| Phát sinh Có (in) | `c + L_ps` | `c` |
| Phát sinh Nợ (in) | `d` | `d + L_ps` |
| `Cuối` | `Đầu + c + L_ps − d` | `Đầu + d + L_ps − c` |
| Dương → / Âm → | Dư Có / Dư Nợ | Dư Nợ / Dư Có |

Kiểm tra lãi (ném lỗi khi lưu, không tự sửa): `L_đ > 0` chỉ khi `G_đ > 0`; `L_ps > 0` chỉ khi `Cuối` tính với `L_ps = 0` là `> 0`; `L_đ, L_ps ≥ 0`.

Làm tròn: VND không lẻ — `flt(x, 0)` trước khi so sánh dấu, để số dư kiểu `-0.0000001` không thành "Dư Nợ 0".

Kết quả trả về (dict): `opening_principal=|G_đ|, opening_direction, debit_in_period=d, credit_in_period=c, closing_balance=|Cuối|, balance_direction, meets_d1=(Cuối ≠ 0 or d ≠ 0 or c ≠ 0)`.

### 3.4 Bộ số kiểm thử bắt buộc (T12, T22)

| Ca | Loại | d0 | c0 | d | c | L_đ | L_ps | Kết quả mong đợi |
|---|---|---|---|---|---|---|---|---|
| A | NCC còn nợ | 30 | 100 | 40 | 50 | 0 | 5 | Đầu = Dư Có 70; Cuối = **Dư Có 85**; PS Có in 55 |
| B | NCC trả trước | 60 | 10 | 0 | 20 | 0 | 0 | Đầu = Dư Nợ 50; Cuối = **Dư Nợ 30**; nhập L_ps = 1 → **bị chặn** |
| C | KH còn nợ | 200 | 50 | 100 | 80 | 0 | 10 | Đầu = Dư Nợ 150; PS Nợ in 110; Cuối = **Dư Nợ 180** |
| D | KH trả trước | 0 | 40 | 10 | 0 | 0 | 0 | Đầu = Dư Có 40; Cuối = **Dư Có 30**; nhập L_đ = 1 → **bị chặn** |
| E | Không phát sinh | 0 | 0 | 0 | 0 | 0 | 0 | Bằng 0; `meets_d1 = False` |
| F | Tài khoản con (T15) | — | — | — | — | — | — | Phát sinh trên TK con của 331 được cộng vào |
| G | Bút toán đã hủy | — | — | — | — | — | — | `is_cancelled = 1` không được tính |

---

## 4. Sinh biên bản — `debt_reconciliation/generation.py` (FR-04, FR-20, D16)

### 4.1 Một hàm tạo duy nhất

```python
def build_statement(company, party_type, party, from_date, to_date, source) -> Document:
    # 1. kiểm tra trùng (4.4) → nếu có: trả về bản đang có, không tạo
    # 2. figures.compute(...) → gán số liệu + figures_fetched_on = now()
    # 3. điền thông tin đối tác (4.3) + Settings (đại diện Miyano, hạn phản hồi)
    # 4. statement_no = f"{to_date:%m}.SL MVL-…./{to_date:%Y}"   (D17 — ký tự "…" U+2026 + ".")
    # 5. creation_source = source; status = "Nháp"; insert()
```

Ba lối vào đều gọi `build_statement`:

| Lối vào | Hàm | Cách chạy |
|---|---|---|
| Job ngày 01 (FR-04) | `tasks.hourly()` → nếu `auto_generate` và `now.day == generation_day` và `now.hour == generation_hour` → `generate_for_period(prev_month, parties=None, source="Tự động")` | `frappe.enqueue(..., queue="long", enqueue_after_commit=True, now=frappe.flags.in_test)` |
| Hộp thoại "Sinh biên bản kỳ" (FR-20b) | `@frappe.whitelist() generate_statements(from_date, to_date, party_type, parties=None)` — kiểm role Accounts Manager/User | ≤ 20 đối tác: chạy ngay, trả kết quả; > 20: enqueue + realtime/notification khi xong |
| Form tạo mới (FR-20a) | method trên document `@frappe.whitelist() def fetch_figures(self)` — gọi bằng `frm.call("fetch_figures")` | đồng bộ; chỉ cho khi `docstatus == 0` (R-e) |

`generate_for_period`: lấy danh sách đối tác từ truy vấn GROUP BY (3.2) + Supplier/Customer `disabled = 0` và `exclude_reconciliation = 0`; với `parties=None` chỉ giữ đối tác đạt D1; với `parties` do người dùng chọn thì **giữ cả đối tác không đạt D1** nhưng gắn cảnh báo (R-d). Mỗi đối tác bọc `savepoint` riêng — lỗi một đối tác không rollback cả lô (UC-01 E2). Trả về `{created: [], existing: [], failed: [{party, error}]}` và ghi 1 `Notification Log` tóm tắt cho người chạy / `reminder_recipients`; lỗi chi tiết vào `Error Log`.

Chạy giờ: scheduler `hourly` của Frappe chạy trong khung giờ, không đúng phút `:00` — tức "10:00" nghĩa là trong khoảng 10:00–10:59. Idempotent nên chạy lặp không gây trùng.

### 4.2 Hộp thoại (list view — `debt_reconciliation_statement_list.js`)
Nút **"Sinh biên bản kỳ"** → `frappe.ui.Dialog` với: Từ ngày, Đến ngày (mặc định tháng trước), Loại đối tác, **Đối tác** (`MultiSelectList` có `get_data` lọc theo loại). Kết quả hiện bảng từng đối tác: *Đã tạo* (link) / *Đã có sẵn* (link) / *Lỗi* (thông báo).

### 4.3 Thông tin đối tác
- Địa chỉ: `get_default_address(party_type, party)` + `get_address_display(...)` (`frappe.contacts.doctype.address.address`).
- MST: `tax_id`; tên: `supplier_name` / `customer_name`.
- Email: `reconciliation_email` → fallback `email_id`.
- Thiếu email / thiếu HĐ nguyên tắc → vẫn tạo, ghi vào `missing_party_warning` (UC-01 E1, US-10).

### 4.4 Chống trùng (R-b, D14)
Trong `validate()` (và trước khi tạo ở 4.1):
```python
frappe.db.exists("Debt Reconciliation Statement", {
    "party_type": ..., "party": ..., "from_date": ..., "to_date": ...,
    "docstatus": ["<", 2], "name": ["!=", self.name]})
```
Bản Amend hợp lệ vì bản gốc đã `docstatus = 2`. Để tránh race giữa job và người dùng cùng lúc, bọc tạo mới trong khoá Redis theo khoá `dr:{party_type}:{party}:{from_date}` (`frappe.cache().set(key, 1, nx=True, ex=60)` rồi xoá bằng lệnh raw tương ứng — **không** trộn với `frappe.cache().delete_value()`, hàm này thêm tiền tố site và sẽ không xoá được khoá).

### 4.5 Các validate khác trong controller
- `from_date` là ngày 01 và `to_date` là ngày cuối cùng tháng (R-c; ⚠️ nếu sau này cho kỳ lẻ thì chỉ bỏ validate này).
- Quy tắc lãi (3.3); mọi Currency ≥ 0.
- `before_submit`: số liệu phải đã lấy (`figures_fetched_on` có giá trị); không có cảnh báo chặn nào khác.

---

## 5. Trạng thái (FR-06)

### 5.1 Trạng thái điều khiển bằng code, không dùng DocType `Workflow` — ĐÃ CHỐT (D20)
Lý do (đã được đồng ý 21/09; SRS V1.1 FR-06 đã sửa theo):
1. Hai chuyển trạng thái do **hệ thống** thực hiện bất đồng bộ (Đã duyệt → Đã gửi / Lỗi gửi, sau khi Email Queue xử lý) — Frappe Workflow gắn chuyển trạng thái với hành động của người dùng có role.
2. Mỗi chuyển trạng thái nghiệp vụ kèm dữ liệu bắt buộc (cách xác nhận + bản ký; số theo đối tác + diễn giải) — cần hộp thoại riêng, Workflow không cung cấp.
3. ERPNext tự dùng cách này cho `status` của hầu hết chứng từ.

### 5.2 Bảng trạng thái

| Trạng thái | docstatus | Vào bằng | Ai | Điều kiện / dữ liệu bắt buộc |
|---|---|---|---|---|
| Nháp | 0 | tạo mới | Hệ thống, Acc. Manager, Acc. User | |
| Đã duyệt | 1 | **Submit** (nút chuẩn — đổi nhãn thành "Duyệt" bằng `frm.page.set_primary_action` trong JS) | Acc. Manager | `figures_fetched_on` có giá trị |
| Đã gửi | 1 | ngay sau khi email vào hàng đợi (6.1, D21) | Hệ thống | ghi `sent_on` = thời điểm đưa vào hàng đợi |
| Lỗi gửi | 1 | precheck: thiếu email / sai định dạng (D21) | Hệ thống | ghi `send_error`, Notification Log |
| (Lỗi gửi →) Đã duyệt | 1 | nút **Gửi lại** | Acc. Manager | chạy lại 6.1 |
| Đã đối soát khớp | 1 | nút **Phản hồi: Khớp** | Acc. Manager | từ Đã gửi; ghi `partner_response`, `responded_on` |
| Chênh lệch | 1 | nút **Phản hồi: Chưa khớp** | Acc. Manager | từ Đã gửi **hoặc Đã đối soát khớp**; hộp thoại bắt `dispute_amount`, `dispute_note` |
| Đã xác nhận | 1 | nút **Xác nhận** | Acc. Manager | từ Đã gửi / Đã đối soát khớp / Chênh lệch; hộp thoại bắt `confirmation_method` + `signed_copy`; ghi `confirmed_on`. Từ Đã gửi (chưa từng phản hồi) → tự ghi `partner_response = Khớp` (UC-04 E2) |
| Đã hủy | 2 | Cancel chuẩn | Acc. Manager | sau đó Amend (D14) |

Cài đặt: một method `@frappe.whitelist() def apply_action(self, action, **data)` với bảng `ALLOWED = {action: (from_states, to_state, required_fields)}`; kiểm role bằng `frappe.only_for("Accounts Manager")`; ghi bằng `self.db_set(...)` để timeline có vết (FR-17). Các field AOS ở mục 2.1 cho phép đổi sau Submit.

Cờ **Quá hạn** không phải trạng thái (FR-06): `get_indicator` trong `_list.js` — `response_deadline < today` và `partner_response == "Chưa phản hồi"` → chỉ báo đỏ "Quá hạn".

### 5.3 Duyệt & gửi hàng loạt (FR-11 — mức S)
List view bulk action **"Duyệt & gửi"** → `@frappe.whitelist() bulk_approve(names)`: lặp từng bản Nháp, `savepoint` + `doc.submit()`, trả `{ok: [], failed: [{name, error}]}`; bản lỗi không chặn bản khác (US-03).

---

## 6. Phát hành: PDF + email — `debt_reconciliation/publishing.py` (FR-09, FR-10)

### 6.1 Khi Duyệt (`on_submit`)
`frappe.enqueue("…publishing.send_statement", name=..., enqueue_after_commit=True, now=frappe.flags.in_test)`, rồi `send_statement`:
1. **Precheck:** thiếu email hoặc sai định dạng (`frappe.utils.validate_email_address`) → Lỗi gửi ngay (T6).
2. Print format theo `party_type`: `BB DCCN – NCC 331` / `BB DCCN – KH 131`.
3. `pdf = frappe.attach_print(doctype, name, print_format=pf, print_letterhead=False)` → `{fname, fcontent}`.
4. Lưu PDF làm file riêng tư gắn vào biên bản (`save_file(..., is_private=1)`), ghi `sent_pdf`.
5. `q = frappe.sendmail(recipients=[email], cc=cc_emails, sender=<email của sender_email_account>, subject/message = render Email Template với doc, attachments=[pdf], reference_doctype, reference_name, now=False)` → lưu `email_queue = q.name` (chỉ để tra cứu). `frappe.sendmail` trả về đối tượng Email Queue.
6. **Chuyển Đã gửi ngay**, `sent_on = now()` (D21).

### 6.2 Kết quả gửi email — NGOÀI PHẠM VI đợt này (D21)
Hệ thống **không** theo dõi email có tới được đối tác hay không: không có job đồng bộ trạng thái `Email Queue`, không xử lý bounce. Field `email_queue` chỉ lưu để tra cứu khi cần. Nếu sau này cần: làm job cron đọc `Email Queue.status` (`Sent`/`Error`) — lưu ý Email Queue cập nhật trạng thái bằng `frappe.db.set_value`, **không** bắn `doc_events`, nên không làm bằng hook được.

### 6.3 Email Template mặc định (tạo bởi setup)
Tên `Biên bản đối chiếu công nợ`; biến Jinja: `doc.party_name`, `doc.from_date`, `doc.to_date`, `doc.response_deadline`; nội dung nêu hạn **trước ngày 06** cho cả phản hồi đối soát và gửi bản ký, và 2 cách xác nhận C1/C2 (bản cứng về `hard_copy_address`, hoặc PDF ký điện tử gửi lại email).

---

## 7. Print Format (FR-09, D15, D17, D18)

JSON Jinja theo đúng mẫu đã có của repo, ví dụ `erpnext/regional/print_format/phieu_thu_01_tt/phieu_thu_01_tt.json` (`print_format_type: "Jinja"`, `custom_format: 1`). A4 dọc; font trình duyệt mặc định (Unicode đầy đủ — NFR-05).

### 7.1 Ánh xạ ô Excel → biến Jinja

| Ô mẫu | NCC 331 | KH 131 |
|---|---|---|
| E1–E5 (thông tin Miyano) | Company + Address (⚠️ E3) | như NCC |
| L6 "Số:" | `doc.statement_no` | như NCC |
| L7 "Ngày" | `doc.posting_date` dd/mm/yyyy | như NCC |
| A11–A12 căn cứ HĐ | `doc.framework_contract_no or "…"`, `doc.framework_contract_date or "…"` | như NCC |
| Bên A | **Đối tác** (tên, MST, địa chỉ, đại diện) | **Miyano** |
| Bên B | **Miyano** | **Đối tác** — ⚠️ mẫu Excel in nhầm MST Miyano ở ô K23, **không** chép |
| "2. Đại diện Ông (bà)" | in dòng trống theo mẫu (D15) | như NCC |
| A30 kỳ | `doc.from_date` → `doc.to_date` | như NCC |
| F33 Dư đầu kỳ | `abs(opening_principal + opening_interest)` + `opening_direction` | như NCC |
| F35 / F36 | `opening_principal` / `opening_interest` | như NCC |
| F38 "1. Phát sinh có" | `credit_in_period + interest_in_period` | **`credit_in_period` — một dòng, không tách** |
| F39 / F40 (dưới PS Có) | `credit_in_period` / `interest_in_period` | **bỏ** |
| F41 "2. Phát sinh nợ" | `debit_in_period` — một dòng | `debit_in_period + interest_in_period` |
| (mới, dưới PS Nợ) | bỏ | **(1) gốc `debit_in_period` / (2) lãi `interest_in_period`** (D18) |
| F43 / F48 | `closing_balance` + `balance_direction` | như NCC |
| A46 câu kết luận | theo 12.6 SRS: còn nợ / đã thanh toán trước / không còn công nợ | câu phía KH |
| F49 bằng chữ | `so_thanh_chu(doc.closing_balance)` + `" ./."` | như NCC |
| A51 hạn gửi về | "trước ngày `response_deadline`" (**không** còn "ngày 10" — D10) | như NCC |
| A53–A55 | `hard_copy_address`, `contact_line` từ Settings | như NCC |
| A59–A60 khối ký | **luôn in cả 2 bên**, "(Ký, đóng dấu và ghi rõ họ tên)" (D15) | như NCC |

### 7.2 Định dạng số
`frappe.format_value(x, {"fieldtype": "Currency"}, currency="VND")` hoặc `"{:,.0f}".format(x).replace(",", ".")`; không bao giờ in dấu âm (D9) — các field đã lưu `abs()`.

### 7.3 Số tiền bằng chữ
Dùng `so_thanh_chu` có sẵn (`erpnext/regional/vietnam/utils.py:58`, đã đăng ký jinja method tại `erpnext/hooks.py:102`). Hai lưu ý: hàm in chữ "âm …" khi nhận số âm → **luôn truyền giá trị đã `abs()`**; hàm không có đuôi `./.` → cộng chuỗi ở print format, **không sửa hàm** (đang được Phiếu thu/chi/nhập/xuất và HĐĐT dùng). Field `amount_in_words` lưu cùng giá trị để hiện trên form.

---

## 8. Nhắc hạn (FR-14 — mức S)
Cron hằng ngày `0 8 * * *` → `reminders.send_due_reminders()`: các biên bản có `response_deadline == today` và (`partner_response == "Chưa phản hồi"` **hoặc** (`status == "Đã đối soát khớp"` và chưa có `signed_copy`)) → 1 email nội bộ + Notification Log gửi `reminder_recipients`, liệt kê 2 nhóm kèm link. Idempotent theo ngày (kiểm `frappe.cache` key `dr:reminded:{date}`).

---

## 9. Báo cáo (FR-15 — mức S) và bộ lọc Sổ chi tiết công nợ (R4 BA)

| Báo cáo | Loại | Bộ lọc | Nội dung |
|---|---|---|---|
| Tình trạng đối chiếu công nợ theo kỳ | Script Report | Công ty, Từ/Đến ngày, Loại đối tác | Đếm theo trạng thái, tỷ lệ xác nhận, danh sách quá hạn / chênh lệch |
| Đối chiếu tổng biên bản vs số dư TK | Script Report | Công ty, Kỳ, Loại đối tác | Σ dư cuối (có hướng) các biên bản chưa Hủy vs số dư TK 331/131 **cùng tập tài khoản 3.1** tại `to_date`; chênh lệch phải = 0 khi mọi đối tác có biên bản (T11) |
| Number Card ×5 | Number Card | — | Tổng BB kỳ · Đã gửi · Đã xác nhận · Chênh lệch · Quá hạn |
| **Sổ chi tiết công nợ** (đã có) | bổ sung `so_chi_tiet_cong_no.js` | Công ty (mặc định), Từ ngày, Đến ngày, Loại đối tác (`Supplier`/`Customer`), Đối tác (Dynamic Link) | Lấy tài khoản bằng **chung hàm `get_party_accounts`** với biên bản (3.1); hiện báo cáo **không có file bộ lọc** nên trên giao diện luôn trống |

Nút **"Xem sổ công nợ đối tác"** trên form biên bản → `frappe.set_route("query-report", "Sổ chi tiết công nợ", {company, from_date, to_date, party_type, party})`.

---

## 10. Phân quyền (FR-16, NFR-04)

| Role | Statement | Settings | Report |
|---|---|---|---|
| Accounts Manager | read, write, create, delete (Nháp), submit, cancel, amend, print, email, export, report | read, write | ✔ |
| Accounts User | read, write, create, print, report (**không** submit) | read | ✔ |
| System Manager | toàn quyền | toàn quyền | ✔ |
| Website User / portal | **không có dòng quyền nào** | — | — |

Kiểm tra NFR-04: đăng nhập bằng user chỉ có role Accounts User, gọi `frappe.client.submit` cho một biên bản Nháp → phải bị từ chối; user không có role kế toán gọi `GET /api/resource/Debt Reconciliation Statement` → phải bị từ chối.

---

## 11. Setup, patch, migrate

`debt_reconciliation/setup.py::run()` — **idempotent**, chạy lại nhiều lần không lỗi:
1. `create_custom_fields(CUSTOM_FIELDS, update=True)` (mục 2.3).
2. Tạo Email Template mặc định nếu chưa có (6.3).
3. Ghi giá trị mặc định cho Settings nếu còn trống (không ghi đè giá trị người dùng đã sửa).

Patch `erpnext/patches/v15_0/setup_debt_reconciliation.py` (`execute()` → `setup.run()`), thêm vào **cuối khối `[post_model_sync]`** của `erpnext/patches.txt`.

`hooks.py` — thêm vào `scheduler_events` sẵn có:
```python
"hourly": [..., "erpnext.debt_reconciliation.tasks.hourly"],          # job ngày 01
"cron": {..., "0 8 * * *": [..., "erpnext.debt_reconciliation.tasks.send_due_reminders"]},
```

Lệnh (chạy từ bench root):
```bash
bench --site miyano migrate
bench build --app erpnext
bench --site miyano clear-cache
```
Sau khi sửa file `.js` của DocType: `migrate` sẽ cập nhật `modified` của DocType — nếu không, trình duyệt vẫn chạy script cũ từ localStorage (Ctrl+Shift+R **không** xoá được; người dùng dùng mục **Reload** trong menu avatar).

---

## 12. Kiểm thử

Chạy: `bench --site miyano run-tests --module erpnext.debt_reconciliation.tests.test_figures` (mỗi lần **một** `--module`; chạy nhiều `--module` cùng lệnh thì chỉ module cuối được chạy). Không chạy 2 lệnh test song song trên site `miyano` (deadlock).

Lưu ý môi trường:
- Site **không có** bộ dữ liệu `_Test Company`; test tự tạo Supplier/Customer (tên có `frappe.generate_hash()`) và bút toán JE có `party_type`/`party` trên 331/131 — mẫu hàm `_post_party_je` trong `erpnext/regional/vietnam/test_books_and_vouchers.py`.
- `FrappeTestCase` rollback **theo class**, không theo từng test → mỗi test dùng đối tác riêng.
- Tạo Custom Field trong test (DDL) sẽ **commit** giao dịch test → dùng helper get-or-create, gọi `setup.run()` một lần ở `setUpClass`.
- Trong test, email không gửi thật; chỉ kiểm tra Email Queue được tạo với đúng người nhận và file đính kèm.
- Cổng lint: `pre-commit run --files <file…>`; ruff bắt lỗi dấu gạch `–` (en dash) trong comment tiếng Việt → dùng `—`.

| File test | Phủ ca UAT |
|---|---|
| `tests/test_figures.py` | T2 (số khớp GL), T12, T15, T22 — bảng 3.4 |
| `tests/test_generation.py` | T1, T8, T19, T20; chống trùng, R-d, savepoint lỗi 1 đối tác |
| `doctype/…/test_debt_reconciliation_statement.py` | T7, T9, T14, T18, T23; validate tròn tháng, quy tắc lãi, `apply_action` sai trạng thái/sai role |
| `tests/test_publishing.py` | T5, T6 — precheck email thiếu/sai → Lỗi gửi; email hợp lệ → Đã gửi ngay, có `sent_pdf`, có `email_queue` |
| `tests/test_reminders.py` | T10 (giả lập ngày bằng `frappe.utils.data.getdate` patch / `freeze_time`) |
| Kiểm tra tay trên staging | T3, T4, T11, T16, T17, T21 (bản in — chị Hà duyệt) |

---

## 13. Kế hoạch task (thứ tự làm, phụ thuộc, ước lượng)

| # | Task | Phụ thuộc | FR / T | Ước lượng (ngày dev) | Mức |
|---|---|---|---|---|---|
| 0 | Xử lý E1–E3 (scheduler, hộp thư gửi, MST/địa chỉ Company) | — | — | 0.5 (vận hành) | M |
| 1 | Khung module, `modules.txt`, Settings, custom fields, setup + patch | — | FR-01..03 | 0.5 | M |
| 2 | `figures.py` + `test_figures.py` (bảng 3.4) | 1 | FR-05 · T2, T12, T15, T22 | 1 | M |
| 3 | DocType Statement: JSON, controller validate (trùng, tròn tháng, lãi), `statement_no` | 1, 2 | FR-01, FR-07 · T23 | 1 | M |
| 4 | `generation.py`: `build_statement`, `generate_for_period`, nút "Lấy số liệu từ sổ", hộp thoại, job hourly, khoá Redis | 2, 3 | FR-04, FR-20 · T1, T8, T19, T20 | 1 | M |
| 5 | 2 Print Format + định dạng số + bằng chữ | 3 | FR-08, FR-09 · T3, T4, T16, T21 | 1 | M |
| 6 | Trạng thái: `apply_action`, nút + hộp thoại JS, list indicator | 3 | FR-06, FR-12, FR-13 · T7, T9, T14, T18 | 1 | M |
| 7 | `publishing.py`: precheck email, PDF, email, Email Template, Gửi lại | 5, 6 | FR-10 · T5, T6 | 0.5 | M |
| 8 | Bộ lọc `so_chi_tiet_cong_no.js` + nút "Xem sổ công nợ đối tác" | — | R4 BA | 0.25 | M* |
| 9 | Duyệt & gửi hàng loạt | 6, 7 | FR-11 · T5 | 0.5 | S |
| 10 | Nhắc hạn ngày 06 | 6 | FR-14 · T10 | 0.5 | S |
| 11 | 2 báo cáo + Number Card + Workspace | 3 | FR-15 · T11 | 1 | S |
| 12 | Kiểm tra quyền + UAT staging số liệu tháng 8 | tất cả | FR-16 · T1–T23 | 0.5 | M |

\* không có FR riêng trong SRS nhưng BA R-c phụ thuộc vào nó.

**Tổng:** phần M ≈ **7,25 ngày dev** (gồm task 0 và 8); cộng phần S ≈ **9,25 ngày**. So với mốc release tối 29/09 (còn 8 ngày kể từ 21/09): **chỉ vừa đủ cho phần M**; phần S (FR-11, FR-14, FR-15) theo SRS 12.1 được phép lùi, không chặn release — nên xếp sau cùng. Kỳ gửi đầu 01/10 vẫn cần chị Hà đối chiếu tay 100% (R3 BA).

---

## 14. Điểm cần người có thẩm quyền chốt (⚠️)

| # | Điểm | Đề xuất | Ai |
|---|---|---|---|
| K1 | Hộp thư gửi biên bản (E2) | Tạo/chọn Email Account riêng của kế toán, gán vào `sender_email_account` | Xuân + chị Hà |
| ~~K2~~ | Trạng thái bằng code thay vì Frappe Workflow | ✅ **Đã chốt 21/09 (D20)** | — |
| ~~K3~~ | Theo dõi kết quả gửi email / bounce | ✅ **Đã chốt 21/09 (D21): không làm ở đợt này** | — |
| K4–K6 | 3 điểm ⚠️ nghiệp vụ còn mở ở BA | ✅ **Build theo mặc định** (BA mục 11): lãi đối xứng, 1 đại diện/bên, kỳ tròn tháng | Chị Hà xác nhận sau, không chặn |

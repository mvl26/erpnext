# Runbook Go-Live — Miyano (ERP thương mại TT99)

> Hướng dẫn triển khai vận hành site `miyano` trên bộ ERP thương mại đầy đủ (Kế
> toán + Kho + Bán hàng + Mua hàng + TSCĐ), **khởi tạo mới (greenfield)**, số dư đầu
> kỳ tại **đầu năm tài chính**. Xem `SPEC.md` và `tasks/plan.md` cho bối cảnh.

**Nguyên tắc an toàn:** mọi bước ghi dữ liệu vào công ty **Miyano thật** chỉ thực
hiện **sau khi đã sao lưu + xác minh** và **được người phụ trách xác nhận**. Chạy
thử trên công ty nháp trước khi áp dụng thật. Mọi lệnh chạy từ **bench root**
(`/home/miyano/frappe-bench`).

Ký hiệu: `<CTY>` = tên công ty (ví dụ `Miyano`), `<NĂM>` = năm tài chính go-live
(ví dụ `2027`).

---

## Bước 0 — Sao lưu & xác minh (BẮT BUỘC trước mọi thao tác ghi)

```bash
# Sao lưu toàn bộ (kèm file) trước khi chạm vào công ty thật
bench --site miyano backup --with-files
# Kiểm tra file .sql.gz vừa tạo trong sites/miyano/private/backups/ và thử giải nén thử
```

Sau khi đã có bản sao lưu **và xác minh** khôi phục được, đánh dấu:

```bash
bench --site miyano execute erpnext.regional.vietnam.go_live.mark_backup_verified \
  --kwargs "{'company':'<CTY>'}"
```

> Chỉ đánh dấu khi bản sao lưu đã được kiểm chứng — đây là "chốt chặn" của bước
> kiểm tra sẵn sàng ở Bước 6.

---

## Bước 1 — Cấu hình hệ thống (`configure_go_live`)

Tạo Năm tài chính, bật kế toán kho liên tục + phương pháp tính giá, thêm số hiệu
chứng từ VN (HDB/HDM/PKT/TT/PXK/PK), đặt tiền tệ VND. **Idempotent** — chạy lại vô
hại.

```bash
bench --site miyano execute erpnext.regional.vietnam.go_live.configure_go_live \
  --kwargs "{'company':'<CTY>','fiscal_year':<NĂM>}"
```

Kiểm tra nhanh: Accounting → Fiscal Year có `<NĂM>`; Stock Settings có phương pháp
tính giá; số hiệu chứng từ VN xuất hiện trong tuỳ chọn naming series của Hóa đơn
bán/mua…

---

## Bước 2 — Phân quyền (`ensure_vn_role_profiles` + tạo người dùng)

Tạo 6 nhóm quyền: **Kế toán, Kế toán trưởng, Thủ kho, Bán hàng, Mua hàng, Quản lý**.

```bash
bench --site miyano execute erpnext.regional.vietnam.role_profiles.ensure_vn_role_profiles
```

Sau đó **tạo người dùng thật** (thủ công, cần xác nhận — không tự động hoá):
User → New → nhập email nhân sự → gán **Role Profile** tương ứng. Kiểm tra lại phạm
vi quyền trước khi gửi lời mời đăng nhập.

---

## Bước 3 — Dữ liệu master (greenfield)

### 3.1 Seed khung dữ liệu

Tạo cây Nhóm hàng (thiết bị & vật tư y tế), đơn vị tính VN, nhóm thuế, bảng giá,
kho mặc định. Idempotent.

```bash
bench --site miyano execute erpnext.regional.vietnam.master_data.seed_master_data \
  --kwargs "{'company':'<CTY>'}"
```

### 3.2 Nhập danh mục thật (Data Import)

Dùng mẫu CSV trong `docs/import_templates/`:

- `customers.csv` — Khách hàng (bắt buộc **MST/Tax ID**)
- `suppliers.csv` — Nhà cung cấp (bắt buộc **MST/Tax ID**)
- `items.csv` — Hàng hóa/thiết bị (Nhóm hàng, ĐVT)

Vào **Data Import** → chọn DocType → tải mẫu → điền → import. Không có hệ thống cũ
để di trú (greenfield); nhập tay hoặc từ Excel của phòng ban.

### 3.3 Kiểm tra tính đầy đủ

```bash
bench --site miyano execute erpnext.regional.vietnam.master_data.master_data_completeness \
  --kwargs "{'company':'<CTY>'}"
```

Báo cáo liệt kê khách/NCC thiếu **MST**, hàng thiếu **ĐVT/nhóm hàng**. Bổ sung cho
đến khi `ok = true`.

---

## Bước 4 — Số dư đầu kỳ (tại đầu năm tài chính)

Ngày hạch toán số dư đầu kỳ = ngày đầu năm tài chính (ví dụ `<NĂM>-01-01`). Đối ứng
số dư bằng các tài khoản vốn chủ sở hữu thật (411x/421x), **không** để lệch.

1. **Số dư sổ cái (GL) chung** — Bút toán mở sổ (Opening Entry). Có thể dùng công
   cụ hỗ trợ theo bảng `{số hiệu TT99: (Nợ, Có)}`:

   ```bash
   bench --site miyano execute erpnext.regional.vietnam.go_live.post_opening_journal_entry \
     --kwargs "{'company':'<CTY>','posting_date':'<NĂM>-01-01','lines':[['111',500000000,0],['156',300000000,0],['4211',0,800000000]]}"
   ```

   (Hoặc nhập tay: Journal Entry → Voucher Type **Opening Entry**, `Is Opening = Yes`.)

2. **Công nợ phải thu (131) / phải trả (331)** — dùng **Opening Invoice Creation
   Tool** (Accounting → Opening Invoice Creation Tool), tạo hoá đơn mở cho từng
   khách hàng/NCC (mỗi dòng gắn **đối tượng**). Đây là cách để 131/331 khớp sổ chi
   tiết công nợ.

3. **Tồn kho đầu kỳ (156)** — **Stock Reconciliation** tại ngày đầu kỳ: nhập số
   lượng + giá trị cho từng mặt hàng/kho. Với kế toán kho liên tục, bút toán sẽ vào
   tài khoản kho 156.

4. **Tài sản cố định (211/2141)** — tạo bản ghi **Asset** với nguyên giá + hao mòn
   luỹ kế (Available for use), theo các Asset Category đã cấu hình (211/2141/6424/
   2411).

---

## Bước 4B — Cutover GIỮA NĂM (số dư tại ngày chốt, ví dụ 30/06)

Dùng khi go-live không rơi vào đầu năm tài chính. Mặc định của phương án này
(kế toán trưởng xác nhận trước khi nhập thật):

- **Ngày chốt** (`as_of`): mặc định **30/06/2026** — số dư lấy theo bảng cân đối
  tại cuối ngày chốt; nghiệp vụ từ 01/07 nhập trực tiếp vào ERPNext (kể cả nhập
  bù các ngày đã qua).
- **Chỉ tài khoản Bảng cân đối (loại 1–4).** KHÔNG đưa số dư/lũy kế các tài khoản
  loại 5–9 vào bút toán mở sổ (hệ thống cũng chặn tài khoản P&L trong Opening
  Entry). **Kết quả kinh doanh lũy kế nửa đầu năm đưa vào 4212** (LNST chưa phân
  phối năm nay).
- **Mọi bút toán mở sổ hạch toán đúng ngày chốt** (`posting_date = as_of`) — kể cả
  Opening Invoice, Stock Reconciliation, Asset.
- **Hệ quả cần biết:** B02/B03 in từ ERPNext cho năm cutover chỉ phủ từ sau ngày
  chốt; BCTC **cả năm** phải cộng thủ công số liệu nửa đầu năm từ hệ thống/sổ cũ.
  Kế toán trưởng ghi nhận điểm này khi lập BCTC năm.

Các bước nhập giống Bước 4 (GL / Opening Invoice / Stock Reconciliation / Asset)
nhưng thay ngày đầu năm bằng ngày chốt:

```bash
bench --site miyano execute erpnext.regional.vietnam.go_live.post_opening_journal_entry \
  --kwargs "{'company':'<CTY>','posting_date':'2026-06-30','lines':[['111',500000000,0],['156',300000000,0],['4212',0,800000000]]}"
```

---

## Bước 5 — Kiểm tra số dư đầu kỳ (`validate_opening_balances`)

```bash
# Đầu năm tài chính (Bước 4)
bench --site miyano execute erpnext.regional.vietnam.go_live.validate_opening_balances \
  --kwargs "{'company':'<CTY>'}"

# Cutover giữa năm (Bước 4B) — truyền ngày chốt
bench --site miyano execute erpnext.regional.vietnam.go_live.validate_opening_balances \
  --kwargs "{'company':'<CTY>','as_of':'2026-06-30'}"
```

Yêu cầu **tất cả** đạt (`ok = true`):

- `balanced` — tổng Nợ = tổng Có (bảng cân đối thử nghiệm về 0).
- `all_tt99` — mọi bút toán mở sổ dùng tài khoản có **số hiệu TT99**.
- `ar_ap_has_party` — các bút toán 131/331 đều có **đối tượng** (khớp sổ chi tiết).

Riêng chế độ giữa năm (`as_of`) thêm hai điều kiện:

- `bs_only` — không có tài khoản **số hiệu loại 5–9** trong số dư đầu kỳ (kết quả
  H1 nằm ở 4212).
- `on_cutover_date` — mọi bút toán mở sổ hạch toán **đúng ngày chốt**.

Báo cáo cũng trả các control total 131/331/15x để đối chiếu với sổ chi tiết công
nợ và bảng kê tồn kho.

---

## Bước 6 — Kiểm tra sẵn sàng go-live (`go_live_readiness`)

```bash
bench --site miyano execute erpnext.regional.vietnam.go_live.print_go_live_readiness \
  --kwargs "{'company':'<CTY>'}"
```

Kết quả in ra danh sách kiểm tra. **Chỉ go-live khi tất cả ✓** (SẴN SÀNG GO-LIVE):
on TT99 · năm tài chính mở · defaults 131/331/156/632/511 · số hiệu chứng từ VN ·
kế toán kho liên tục · có kho · đủ nhóm quyền · không còn tài khoản lạ chưa có số
hiệu · số dư đầu kỳ hợp lệ · đã đánh dấu sao lưu.

Nếu còn ✗, xử lý đúng mục đó rồi chạy lại (mỗi lần chạy là read-only, an toàn).

---

## Bước 7 — Chốt go-live & kiểm thử ngày 1

1. Chốt **ngày go-live**; thông báo ngừng nhập liệu ở hệ thống/Excel cũ (nếu có).
2. **Smoke test ngày 1** trên dữ liệu thật:
   - Lập 1 **Hóa đơn bán** (Sales Invoice) → kiểm tra GL vào 131/511/33311.
   - Lập 1 **Hóa đơn mua** (Purchase Invoice) → kiểm tra GL vào 632|156/1331/331.
   - Lập 1 **Payment Entry** thu/chi → kiểm tra 111/112.
   - Lập 1 **phiếu nhập/xuất kho** → kiểm tra tồn kho & 156.
   - Mở báo cáo **B01/B02** và **Sổ Cái** kiểm tra số liệu.
3. Theo dõi sát ngày đầu; giữ bản sao lưu Bước 0 cho tới khi ổn định.

---

## Khóa sổ cuối tháng — kết chuyển 911 (vận hành định kỳ)

Cuối mỗi tháng, sau khi toàn bộ chứng từ của tháng đã nhập đủ (bán, mua, kho,
thu/chi, lương):

1. **Xem trước** bộ bút toán kết chuyển (read-only, an toàn):

   ```bash
   bench --site miyano execute erpnext.regional.vietnam.period_close.ket_chuyen_911 \
     --kwargs "{'company':'<CTY>','period':'2026-07','preview':1}"
   ```

   Kết quả liệt kê: kết chuyển doanh thu/thu nhập (5xx/7xx) → 911, 911 → chi phí
   (6xx/8xx), và kết quả (lãi/lỗ) → 4212. **Kế toán trưởng soát xét** danh sách
   này trước khi thực hiện.

2. **Thực hiện** (ghi sổ + khóa kỳ — cần sao lưu trước trên công ty thật):

   ```bash
   bench --site miyano execute erpnext.regional.vietnam.period_close.ket_chuyen_911 \
     --kwargs "{'company':'<CTY>','period':'2026-07','preview':0}"
   ```

   Lệnh này: ghi các Journal Entry kết chuyển vào ngày cuối tháng → tự kiểm tra
   toàn bộ tài khoản loại 5–9 về **0** → tạo **Accounting Period** khóa tháng
   (chặn ghi lùi chứng từ vào tháng đã đóng). Chạy lại cho tháng đã đóng sẽ trả
   `already_closed` — không tạo bút toán trùng.

3. **Kiểm tra sau khóa sổ**: Sổ Cái TK 911 = 0; Bảng CĐSPS cân; chạy B01/B02,
   sổ quỹ (S07-DN), sổ tiền gửi (S08-DN), sổ công nợ cho tháng vừa đóng.

4. **Mở lại kỳ** (chỉ khi kế toán trưởng phê duyệt — thao tác nhạy cảm): xóa
   Accounting Period "Kết chuyển <kỳ>" rồi hủy (cancel) các JE kết chuyển của
   tháng đó, sửa chứng từ, và chạy lại từ bước 1.

---

## Rollback (nếu phải quay lại)

Số dư/dữ liệu đầu kỳ nhập sai và không thể sửa gọn:

```bash
# Khôi phục về bản sao lưu ở Bước 0 (GHI ĐÈ dữ liệu hiện tại — cân nhắc kỹ)
bench --site miyano restore sites/miyano/private/backups/<FILE>.sql.gz --with-files
bench --site miyano migrate
```

> Restore ghi đè toàn bộ site. Chỉ thực hiện khi đã chắc chắn và có xác nhận.

---

## Checklist một trang

```
[ ] 0. Đã bench backup --with-files + xác minh khôi phục  → mark_backup_verified
[ ] 1. configure_go_live (Fiscal Year <NĂM>, kho liên tục, naming series, VND)
[ ] 2. ensure_vn_role_profiles + tạo user + gán Role Profile
[ ] 3. seed_master_data → import CSV khách/NCC/hàng → master_data_completeness = ok
[ ] 4. Số dư đầu kỳ: GL (Opening Entry) · 131/331 (Opening Invoice Tool) ·
       tồn kho (Stock Reconciliation) · TSCĐ (Asset)
       — giữa năm (4B): chỉ TK loại 1–4, KQKD H1 vào 4212, đúng ngày chốt
[ ] 5. validate_opening_balances = ok (balanced · all_tt99 · ar_ap_has_party;
       giữa năm thêm as_of: bs_only · on_cutover_date)
[ ] 6. print_go_live_readiness = ✅ SẴN SÀNG (mọi mục ✓)
[ ] 7. Chốt ngày go-live · smoke test SI/PI/Payment/Kho · kiểm tra B01/B02/Sổ Cái
[ ] (định kỳ) Cuối tháng: ket_chuyen_911 preview → KTT duyệt → execute → 911 = 0
[ ] (dự phòng) Quy trình rollback bằng bench restore đã sẵn sàng
```

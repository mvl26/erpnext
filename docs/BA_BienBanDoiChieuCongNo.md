# TÀI LIỆU PHÂN TÍCH NGHIỆP VỤ (BA)
## Tính năng: Đối chiếu & xác nhận công nợ theo kỳ (NCC 331 / KH 131) trên ERPNext

**Công ty:** TNHH Miyano Việt Nam
**Hệ thống:** ERPNext — erp.miyano.com.vn, thuộc **SupplyCore** — code nằm trong **module mới `Debt Reconciliation`** của app `erpnext` (D19)
**Tài liệu tham chiếu:** mẫu `BB đối chiếu công nợ.xlsx` (2 sheet: NCC 331, KH 131) · **SRS_10_BienBanDoiChieuCongNo V1.1** (baseline build 21/09/2026) · **TKKT_10** (thiết kế kỹ thuật)
**Phiên bản BA:** **V7 — BẢN CHỐT ĐỂ BUILD (21/09/2026)**: trạng thái điều khiển bằng code (D20) · không theo dõi kết quả gửi email (D21) · V6 — công thức đầy đủ có lãi quá hạn, sheet KH 131 chuyển phần tách lãi sang **Phát sinh Nợ** (D18) · module mới `Debt Reconciliation` (D19) · rà soát cuối · V5: số biên bản **để trống phần mã NCC/KH**: `{Tháng}.SL MVL-…./{Năm}` (D17) · bổ sung **lập biên bản chủ động** cho 1 hoặc nhiều đối tác (D16, FR-20, UC-07) ngày 21/09 · V4: chốt trọn bộ D7–D15 ngày 18/09 (tài khoản con · số biên bản tách khỏi ID · mọi số đều dương · một mốc ngày 06 · số liệu 100% từ GL · lãi quá hạn theo chiều còn nợ · chưa làm ký số · Amend giữ số cũ · khối ký 2 bên)
**Ngày cập nhật:** 21/09/2026

> Tài liệu này là bản tóm tắt ở mức nghiệp vụ (BA), dùng để trao đổi nhanh với các bên không cần đọc toàn bộ 12 mục kỹ thuật của SRS_10. Với chi tiết field/API/test case, tham chiếu thẳng SRS_10.

---

## 1. Mục tiêu & bối cảnh

Hiện tại kế toán lập "Biên bản đối chiếu & xác nhận công nợ" (BBĐCCN) bằng cách điền tay từng file Excel cho từng NCC/KH mỗi tháng — số liệu chép tay từ sổ, số biên bản đánh tay, gửi email và theo dõi xác nhận thủ công. Mục tiêu: tự động hoá toàn bộ vòng đời này trên ERPNext — từ sinh số liệu, duyệt, gửi email, đến ghi nhận xác nhận/chênh lệch của đối tác — với **kỳ gửi chính thức đầu tiên là 01/10/2026** (công nợ tháng 9). Chữ ký số phía Miyano trên PDF (FR-19) được tách thành hạng mục phát triển sau, không nằm trong scope build đợt này.

---

## 2. Phạm vi

**Trong phạm vi:** toàn bộ FR mức Must trong SRS_10, **trừ FR-19**; áp dụng cho mọi Supplier/Customer active có số dư ≠ 0 hoặc có phát sinh trong kỳ. Email gửi đi dùng hộp thư hệ thống hiện có (không cần cấu hình hộp thư riêng cho tính năng này).

**Ngoài phạm vi (giai đoạn này):**
- Xác nhận online qua Supplier/Client Portal (Giai đoạn 2, sau 30/10)
- Tính lãi quá hạn tự động (nhập tay, mặc định 0)
- Bù trừ công nợ 2 chiều cho đối tác vừa là NCC vừa là KH — đã chốt: **gửi 2 biên bản riêng, không bù trừ**, vì giá trị công nợ phải trả (331) và phải thu (131) là 2 khoản hoàn toàn khác nhau về bản chất
- Đối chiếu chi tiết theo từng hoá đơn (biên bản chỉ chốt 4 số tổng; nếu đối tác cần bảng kê chi tiết, gửi kèm General Ledger xuất riêng)
- **Ký số PDF phía Miyano (FR-19)** — đã chốt: **chưa làm ở đợt này, phát triển sau**. Giai đoạn này PDF gửi đi là PDF thường, không ký số

---

## 3. Hiện trạng (As-Is) & vấn đề

| Hoạt động | Cách làm hiện nay | Vấn đề |
|---|---|---|
| Tổng hợp số dư/phát sinh | Tra sổ ERP rồi chép tay sang Excel | Mất công, dễ sai, không gắn thời điểm chốt |
| Lập biên bản | Điền tay từng file cho từng đối tác | Tốn nhiều giờ công mỗi kỳ, lỗi copy-paste |
| Số biên bản | Đánh tay | Không có sổ đăng ký tập trung — To-Be: sổ đăng ký tập trung là **ID bản ghi do hệ thống tự sinh**; số biên bản in trên giấy chỉ để quản lý giấy tờ (D17) |
| Số tiền bằng chữ | Gõ tay | Dễ sai với số lớn |
| Gửi & theo dõi xác nhận | Email tay + theo dõi bằng Excel/trí nhớ | Không thấy toàn cảnh ai chưa xác nhận; không nhắc hạn |
| Xử lý chênh lệch | Trao đổi email/điện thoại, không lưu vết | Mất lịch sử, lặp lại tranh luận kỳ sau |

### Phân tích file mẫu gốc (mức ô/cell — bổ sung chi tiết cho FR-09)

| Ô | Nhãn trong mẫu | Sheet NCC 331 | Sheet KH 131 |
|---|---|---|---|
| F33 | Dư nợ/có đầu kỳ | \|Đầu\| = \|G_đ + L_đ\|, tính khi in | như NCC |
| F35 / F36 | (1) Giá trị gốc / (2) Lãi quá hạn — đầu kỳ | \|G_đ\| từ GL / L_đ nhập tay | như NCC |
| F38 | 1. Phát sinh Có trong kỳ | C + L_ps (tổng) | **C — một dòng, không tách** |
| F39 / F40 | tách (1) gốc / (2) lãi | **dưới Phát sinh Có**: C / L_ps | **không có ở vị trí này** |
| F41 | 2. Phát sinh Nợ trong kỳ | **D — một dòng, không tách** | D + L_ps (tổng) |
| (mới) | tách (1) gốc / (2) lãi | không có | **dưới Phát sinh Nợ**: D / L_ps (D18) |
| F43 / F48 | Dư cuối kỳ / Tổng số tiền kết luận | \|Cuối\| — công thức mục 5 | như NCC |
| F49 / F50 | Số tiền bằng chữ | Đổi \|Cuối\| sang chữ tiếng Việt (FR-08) | như NCC |

**Khác biệt so với file Excel gốc (D18):** trong file mẫu, cả 2 sheet đều đặt phần tách gốc/lãi dưới dòng *Phát sinh Có*. Với sheet KH điều này sai chiều — Phát sinh Có làm *giảm* nợ phải thu, còn lãi tính cho khách làm *tăng* nợ phải thu. Vì vậy Print Format KH 131 chuyển phần tách gốc/lãi xuống dưới dòng **Phát sinh Nợ**; sheet NCC giữ nguyên bố cục mẫu.

**Nguyên tắc nguồn số liệu (D11):** mọi số tiền lấy từ GL Entry có lọc theo khoảng ngày của kỳ — không có field nhập tay cho bất kỳ số gốc nào; ngoại lệ duy nhất là lãi quá hạn. Các dòng tổng của mẫu (F33, F38) là số tính tại thời điểm in.

Chỉ 2 ô (F43, F48) có formula sẵn trong file gốc; toàn bộ số liệu đầu vào hiện đang nhập tay — xác nhận lại rằng quy trình hiện tại **chưa hề tự động ngay cả ở mức Excel**.

---

## 4. Giải pháp đã chọn (To-Be) & lý do

**Đã chốt với PO:** xây **1 Doctype mới `Debt Reconciliation Statement`** (non-GL, non-stock — chỉ đọc `GL Entry`, không sinh bút toán), kết hợp Scheduled Job + Workflow + Print Format + Email chuẩn của Frappe. Đây là mức phát triển mới **nhỏ nhất có thể** — mọi phần còn lại (naming, print, email, permission, dashboard) tái dùng cơ chế có sẵn.

**Vị trí code (D19):** toàn bộ tính năng nằm trong **một module mới `Debt Reconciliation`** của app `erpnext` (thư mục `erpnext/debt_reconciliation/`) — DocType, hàm tính số, job, workflow, print format, báo cáo. Không tạo app riêng, không đặt trong app khác.

**Vì sao không dùng được giải pháp thấp hơn:** report chuẩn "Accounts Receivable/Payable" (PSOA-style) chỉ xuất *sổ chi tiết công nợ*, không phải *chứng từ xác nhận 2 bên có số hiệu, vòng đời trạng thái, bản ký lưu trữ*. Không có Doctype chuẩn nào của ERPNext đóng được vai trò này.

**To-Be tóm tắt:** Ngày 01 hàng tháng, hệ thống tự sinh Draft cho mọi đối tác đạt điều kiện → Chị Hà rà & duyệt (hàng loạt) → hệ thống gửi email kèm PDF từ hộp thư hệ thống → đối tác phản hồi đối soát (trước ngày 06) → gửi bản ký (bản cứng hoặc ký điện tử) → Chị Hà cập nhật Đã xác nhận/Chênh lệch → dashboard theo dõi tỷ lệ xác nhận. (Bước ký số PDF phía Miyano — FR-19 — chưa nằm trong luồng này, sẽ bổ sung sau.)

**Hai đường tạo biên bản (D16):** ngoài job tự động ngày 01, kế toán **chủ động lập biên bản** cho một hoặc vài đối tác bất kỳ lúc nào — ví dụ khi đối tác xin biên bản, khi cần chốt lại sau khi sửa sổ, hoặc khi có đối tác mới. Cả hai đường cho ra **cùng một loại biên bản Nháp**, dùng **chung một hàm tính số**, rồi đi tiếp cùng một luồng duyệt → gửi → xác nhận.

```
Đường 1 — Tự động (lưới an toàn)            Đường 2 — Chủ động (D16)
10:00 ngày 01                               Kế toán chọn đối tác + kỳ
   │ quét TẤT CẢ NCC/KH đạt điều kiện          │ 2a. Tạo mới trên form  (1 đối tác)
   │ BỎ QUA đối tác đã có biên bản kỳ đó       │ 2b. Hộp thoại "Sinh biên bản kỳ"
   ▼                                          │     có ô Đối tác chọn nhiều
   └──────────────► Biên bản NHÁP ◄───────────┘
                         │  (chung hàm tính số từ GL Entry)
                         ▼
          Duyệt → Gửi email → Phản hồi trước ngày 06 → Xác nhận / Chênh lệch
```

### 4.1 Lập biên bản chủ động (D16 — FR-20, UC-07)

**Lối vào 2a — Tạo mới trên form (cho 1 đối tác):**

| Bước | Người dùng | Hệ thống |
|---|---|---|
| 1 | Mở "Biên bản đối chiếu công nợ" → **Thêm mới** | Mở form trống, mặc định Công ty = Miyano |
| 2 | Chọn **Loại đối tác** (NCC / KH) → **Đối tác** → **Kỳ đối chiếu** | Kỳ mặc định = tháng liền trước; tự điền MST, địa chỉ, HĐ nguyên tắc, đại diện, email đối chiếu từ hồ sơ đối tác |
| 3 | Bấm **"Lấy số liệu từ sổ"** | Tính dư đầu kỳ, phát sinh nợ, phát sinh có, dư cuối kỳ, chiều dư, số tiền bằng chữ — cùng công thức với job tự động; hiện cảnh báo nếu thiếu email / thiếu HĐ nguyên tắc |
| 4 | Xem số liệu, nhập lãi quá hạn nếu có (chỉ ở chiều còn nợ — D12) | Cập nhật tổng và số tiền bằng chữ |
| 5 | **Lưu** | Sinh `statement_no`, biên bản ở trạng thái **Nháp** → đi tiếp luồng duyệt/gửi như biên bản tự động |

**Lối vào 2b — Hộp thoại "Sinh biên bản kỳ" (cho nhiều đối tác):** bổ sung ô **Đối tác (chọn nhiều)** bên cạnh Từ/Đến ngày và Loại đối tác. Để trống ô Đối tác = sinh cho tất cả đối tác đạt điều kiện (như cũ); chọn cụ thể = chỉ sinh cho các đối tác đã chọn. Kết thúc hiển thị kết quả từng đối tác: đã tạo / đã có sẵn / lỗi.

**Quy tắc nghiệp vụ của lập chủ động:**

| # | Quy tắc |
|---|---|
| R-a | **Chung một hàm tính số** với job tự động (cùng GL Entry, cùng tài khoản 331/131 và tài khoản con, cùng quy ước số dương) — lập tay hay tự động ra số giống hệt nhau |
| R-b | **Mỗi đối tác, mỗi kỳ chỉ 1 biên bản chưa Hủy.** Nếu đã có → không tạo mới mà báo và mở biên bản đang có. Job ngày 01 cũng bỏ qua đối tác đã được lập tay trong kỳ đó |
| R-c | **Kỳ đối chiếu mặc định là tròn tháng** (từ ngày 01 đến ngày cuối tháng), khớp chu kỳ đối chiếu hàng tháng. Từ D17 số biên bản không chứa mã đối tác nên kỳ lẻ **không còn gây trùng số**; nhu cầu xem số theo kỳ lẻ (ví dụ 01–15) tạm thời dùng báo cáo *Sổ chi tiết công nợ* — **lưu ý: báo cáo này hiện chưa có bộ lọc trên giao diện** (xem R4, mục 9). ⚠️ Có cho lập biên bản chính thức theo kỳ lẻ không — nay chỉ còn là câu hỏi nghiệp vụ, không vướng kỹ thuật |
| R-d | Cho phép lập cho đối tác **không đạt điều kiện D1** (dư 0 và không phát sinh) vì người dùng đã chủ động chọn — hệ thống chỉ hiện cảnh báo, không chặn |
| R-e | Nút **"Lấy số liệu từ sổ"** bấm lại được bao nhiêu lần tùy ý **khi còn Nháp** (để cập nhật sau khi sửa sổ); từ lúc Duyệt trở đi số liệu đóng băng, muốn đổi phải Hủy → Sửa đổi (D14) |
| R-f | Quyền: **Accounts Manager** và **Accounts User** đều lập được biên bản Nháp; chỉ Accounts Manager được duyệt (FR-16 giữ nguyên) |
| R-g | Mọi lần lập (tay hay tự động) ghi vết người tạo, thời điểm, nguồn tạo (`Tự động` / `Thủ công`) để phân biệt trên danh sách |

---

## 5. Quy ước tính số liệu & hiển thị số dư (đã chốt — D5, D9)

**Mọi số tiền trên biên bản đều là số dương** — dư đầu kỳ, phát sinh nợ, phát sinh có, lãi quá hạn, dư cuối kỳ, tổng số tiền kết luận — bất kể là số dư Nợ hay dư Có (D9, mở rộng D5). Chiều dư thể hiện bằng chữ qua `opening_direction` (đầu kỳ) và `balance_direction` (cuối kỳ) cùng câu kết luận. Hệ thống không bao giờ ghi số âm xuống field Currency; giá trị có hướng chỉ tồn tại trong bộ nhớ khi tính toán:

**Ký hiệu:** `D`, `C` = tổng Nợ, tổng Có của GL Entry (không bị hủy) của đối tác trên TK 331/131 và tài khoản con, **trong kỳ**; `D₀`, `C₀` = như trên nhưng **trước ngày đầu kỳ**; `L_đ`, `L_ps` = lãi quá hạn đầu kỳ và phát sinh (nhập tay, ≥ 0).

| Đại lượng (giá trị có hướng, dương = còn nợ) | NCC 331 | KH 131 |
|---|---|---|
| Dư đầu gốc `G_đ` | `C₀ − D₀` | `D₀ − C₀` |
| Dư đầu kỳ `Đầu` | `G_đ + L_đ` | `G_đ + L_đ` |
| Phát sinh Có | `C + L_ps` | `C` |
| Phát sinh Nợ | `D` | `D + L_ps` |
| **Dư cuối `Cuối`** | `Đầu + (C + L_ps) − D` | `Đầu + (D + L_ps) − C` |
| Chiều dư khi dương / âm | Dư Có / Dư Nợ | Dư Nợ / Dư Có |

Cuối > 0 → còn nợ; Cuối < 0 → đã trả trước; = 0 → hết công nợ. Sau khi tính xong, hệ thống lưu `abs()` kèm chiều dư — bản in không có dấu âm ở bất kỳ ô nào. Lưu ý đổi dấu: ERPNext lưu số dư theo quy ước `Nợ − Có`, nên với NCC `G_đ` là **số đối** của số dư ERPNext.

Công thức này thay thế hoàn toàn công thức gốc trong file Excel `F43 = F33 − F38 + F41`, vốn không đúng chiều dấu chuẩn kế toán.

**Lãi quá hạn (D12):** chỉ tính ở **chiều còn nợ** — KH 131 khi dư Nợ (khách còn nợ Miyano), NCC 331 khi dư Có (Miyano còn nợ NCC). Ở chiều đã thanh toán trước thì lãi quá hạn = 0 và không cộng vào tổng; nhập ≠ 0 ở chiều đó sẽ bị chặn. ⚠️ Nhờ chị Hà xác nhận lại giúp quy tắc này áp dụng **đối xứng** cho sheet NCC (ở đó "còn nợ" là dư Có, không phải dư Nợ). Cụ thể điều kiện: `L_đ` chỉ được > 0 khi `G_đ > 0`; `L_ps` chỉ được > 0 khi dư cuối tính **chưa có lãi phát sinh** là > 0 — tức xét theo chiều dư cuối kỳ.

---

## 6. Use case chính (tóm tắt từ SRS_10 mục 9)

| UC | Tên | Actor | Kết quả |
|---|---|---|---|
| UC-01 | Sinh biên bản kỳ tự động (toàn bộ đối tác) | Hệ thống | Bộ biên bản Nháp cho mọi party đạt điều kiện, bỏ qua party đã có biên bản kỳ đó |
| UC-07 | **Lập biên bản chủ động** cho 1 hoặc nhiều đối tác (D16) | Chị Hà / Accounts User | Biên bản Nháp cho đúng đối tác + kỳ đã chọn, số liệu lấy từ sổ, không trùng — xem mục 4.1 |
| UC-02 | Rà soát & duyệt biên bản | Chị Hà | Biên bản chuyển Đã duyệt |
| UC-03 | Gửi email biên bản (kèm PDF) | Hệ thống | Email đã gửi từ hộp thư hệ thống, PDF lưu vết, trạng thái Đã gửi |
| UC-04 | Ghi nhận xác nhận / chênh lệch | Chị Hà | Đã xác nhận (kèm bản ký) hoặc Chênh lệch (kèm ghi chú) |
| UC-05 | Nhắc hạn xác nhận (ngày 06) | Hệ thống | Danh sách đôn đốc cho Chị Hà |
| UC-06 | Theo dõi & báo cáo tình trạng kỳ | Chị Hà, Xuân | Dashboard KPI tỷ lệ xác nhận |

---

## 7. Yêu cầu chức năng chính (rút gọn từ SRS_10 mục 6 — 20 FR)

| Nhóm | FR liên quan | Tóm tắt |
|---|---|---|
| Nền tảng dữ liệu | FR-01, FR-02, FR-03 | Doctype `Debt Reconciliation Statement`; Custom Field trên Supplier/Customer (HĐ nguyên tắc, email đối chiếu...); màn hình Settings |
| Sinh số liệu | FR-04, FR-05, **FR-20** | Job tự động đầu tháng (idempotent); **lập biên bản chủ động** cho 1 hoặc nhiều đối tác — form tạo mới có nút "Lấy số liệu từ sổ" + hộp thoại có ô Đối tác chọn nhiều (FR-20, mục 4.1); số liệu tính từ GL Entry bằng một hàm dùng chung, đóng băng khi duyệt |
| Trình bày & phát hành | FR-07, FR-08, FR-09 | Số biên bản `statement_no` in theo mẫu giấy (field, không phải naming series — xem dưới); số tiền bằng chữ; 2 Print Format theo party_type (KH 131 tách lãi dưới Phát sinh Nợ — D18) |
| Gửi & theo dõi | FR-06, FR-10, FR-11 | Workflow trạng thái; gửi email tự động sau duyệt (từ hộp thư hệ thống); duyệt & gửi hàng loạt |
| Xác nhận & chênh lệch | FR-12, FR-13 | Ghi nhận phản hồi đối soát + xác nhận (C1/C2); ghi nhận & theo dõi chênh lệch |
| Vận hành & giám sát | FR-14, FR-15, FR-16, FR-17, FR-18 | Nhắc hạn; dashboard/report; phân quyền; log/truy vết; sẵn sàng cho portal GĐ2 |
| Backlog (phát triển sau) | FR-19 | Ký số PDF phía Miyano — chưa làm ở đợt này |

**Phân biệt ID bản ghi và số biên bản (đã chốt 21/09):**

| | ID bản ghi (`name`) | Số biên bản (`statement_no`) |
|---|---|---|
| Ai sinh | **Hệ thống tự sinh**, duy nhất, người dùng không nhập/sửa | Hệ thống điền theo mẫu `{Tháng}.SL MVL-…./{Năm}` |
| Dùng để | Định danh, liên kết, tra cứu, chống trùng trên hệ thống | **Chỉ để quản lý giấy tờ** — in ở ô "Số:" trên bản giấy |
| Có duy nhất không | Có | Không — các biên bản cùng tháng cùng số |
| Xuất hiện trên bản in | Không | Có |

**Số biên bản (FR-07 — đã chốt D8, điều chỉnh D17 ngày 21/09):** giữ đúng định dạng mẫu giấy `{Tháng}.SL MVL-…./{Năm}` — ví dụ `09.SL MVL-…./2026`. Tháng và năm lấy theo `to_date` của kỳ đối chiếu; **phần sau `MVL-` để trống (in nguyên dấu `….`), không điền mã NCC/KH.** Hệ quả: mọi biên bản cùng tháng mang cùng một số in — số biên bản chỉ là nhãn hiển thị trên bản giấy, **không dùng để phân biệt biên bản**. Việc phân biệt và chống trùng dựa vào cặp (đối tác, kỳ đối chiếu) — mỗi đối tác mỗi kỳ chỉ 1 biên bản chưa Hủy.

**Số biên bản KHÔNG phải ID bản ghi.** Nó là một field riêng (`statement_no`: Data, read-only, sinh tự động khi tạo, **không kiểm tra trùng** — D17) và là con số duy nhất in ra ô "Số:" trên bản giấy. `name` của document dùng một series kỹ thuật nội bộ (`DCCN-.YYYY.-.####.`), phục vụ hệ thống và không xuất hiện trên bản in. Cách tách này giúp đổi quy ước đánh số sau này mà không phải đụng tới khoá bản ghi hay các liên kết. **Bản Sửa đổi (Amend) — đã chốt D14:** bản Amend là một bản ghi dữ liệu mới nhưng **mang đúng số biên bản của bản gốc** — với D17 điều này tự nhiên đúng vì số chỉ phụ thuộc tháng/năm của kỳ. Kiểm tra chống trùng đặt trên cặp (đối tác, kỳ) trong `validate()`, chỉ xét các bản chưa Hủy.

**Tài khoản công nợ (FR-02/FR-05 — đã chốt D7):** số liệu quét trên **TK 331 và toàn bộ tài khoản con của nó** (với NCC), **TK 131 và toàn bộ tài khoản con** (với KH) — không chỉ một tài khoản đơn lẻ. Cách lấy: mọi tài khoản lá có **số hiệu bắt đầu bằng 331 / 131** (331, 3311, 3312…) của công ty — theo cách đánh số của kế toán VN, **bất kể vị trí trên cây tài khoản ERPNext** — cộng thêm tài khoản lá nằm dưới node 331/131 trên cây (phòng TK con chưa đặt số hiệu); GL Entry lọc theo `account IN (tập đó)` + `party`. **Sửa 21/09 sau lỗi trên production: 3311 và 3312 nằm dưới nhóm "Tài khoản phải trả", **ngang hàng** với 331 chứ không nằm dưới 331 — cách lấy theo cây cũ bỏ sót cả hai nên biên bản ra toàn 0.** Tài khoản `3312 - Trả trước cho người bán` cũng thuộc tập này, nên biên bản ra đúng công nợ ròng (còn nợ trừ đã ứng trước). Không cần tra account mặc định theo từng Supplier/Customer, và **không hard-code tên tài khoản** (tên thật trên site `miyano` là `331 - Phải trả cho người bán - M`). Report đối chiếu tổng (FR-15) và báo cáo Sổ chi tiết công nợ dùng **chung một hàm** lấy tài khoản với biên bản — sổ và biên bản không bao giờ lệch nhau.

---

## 8. Trạng thái biên bản (tóm tắt — điều khiển bằng code, D20)

```
Nháp → Đã duyệt → Đã gửi → Đã đối soát khớp → Đã xác nhận
                     ↘ Lỗi gửi (chỉ khi thiếu/sai email → bổ sung → Gửi lại)
                                            ↘ Chênh lệch → Đã xác nhận
                                   Đã đối soát khớp ↘ Chênh lệch  (đối tác báo Khớp rồi phát hiện lệch)
(Bất kỳ trạng thái đã Submit) → Hủy → Sửa đổi (Amend), giữ liên kết bản gốc
```
Chỉ **Accounts Manager** (Chị Hà) được duyệt/chuyển trạng thái nghiệp vụ; **Accounts User** chỉ tạo/sửa bản Nháp. Trạng thái do code điều khiển (nút trên form + kiểm tra phía server), không dùng DocType Workflow của Frappe (D20).

**Gửi email (D21):** duyệt xong, hệ thống tạo PDF và đưa email vào hàng đợi rồi chuyển **Đã gửi** ngay. Đợt này hệ thống **không theo dõi email có tới được đối tác hay không**; chỉ chặn trước trường hợp thiếu email hoặc email sai định dạng (→ Lỗi gửi).

---

## 9. Rủi ro & điều kiện tiên quyết

| # | Rủi ro | Ảnh hưởng | Cần làm trước khi build |
|---|---|---|---|
| R1 | Journal Entry nhập tay thiếu `party_type`/`party` trên tài khoản 331/131 dùng chung | Sót phát sinh khi lọc theo đối tượng, số dư từng party bị sai | Chạy thử query cảnh báo thiếu party trên dữ liệu thật (đã đưa vào FR-05 dạng kiểm tra) |
| R2 | Chưa có tài khoản/cost center riêng cho lãi quá hạn | Không tách được breakdown giá trị gốc/lãi phạt tự động | Chấp nhận Phase 1: nhập tay, mặc định 0 (đã chốt D3) |
| R4 | Báo cáo *Sổ chi tiết công nợ* (`erpnext/regional/report/so_chi_tiet_cong_no/`) có logic đúng nhưng **thiếu file `.js` khai báo bộ lọc** → trên giao diện không chọn được công ty/kỳ/đối tác, báo cáo trống | Người dùng không tự xem được công nợ từng NCC/KH theo kỳ lẻ (R-c dựa vào báo cáo này) | Bổ sung file bộ lọc (Công ty, Từ/Đến ngày, Loại đối tác, Đối tác) — việc nhỏ, làm kèm đợt build này |
| R3 | Số liệu 331/131 kỳ đầu (tháng 9) mới đưa lên ERP, độ tin cậy chưa rõ | Sai số kỳ gửi đầu tiên 01/10 | Đã chốt: Chị Hà đối chiếu tay 100% trước khi gửi ở kỳ đầu, làm lớp kiểm tra an toàn song song với số hệ thống sinh ra |

---

## 10. Tiêu chí nghiệm thu (tóm tắt UAT — chi tiết T1–T23 xem SRS_10 mục 12.8; T13 ký số đã chuyển backlog)

- Số liệu trên biên bản khớp 100% với GL Entry tại thời điểm sinh (sai số 0 đồng)
- Report đối chiếu tổng: Σ dư cuối các biên bản NCC = số dư TK 331 (tương tự 131)
- Số tiền bằng chữ đúng với các giá trị biên (0, lẻ trăm, hàng chục tỷ)
- Gửi email + đính kèm PDF đúng mẫu, đúng party; biên bản thiếu email / email sai định dạng hiện rõ trạng thái Lỗi gửi, không im lặng bỏ qua (không kiểm tra việc email tới được đối tác — D21)
- Chuyển "Đã xác nhận" bắt buộc có `confirmation_method` + bản ký đính kèm
- Chạy job sinh trùng kỳ không tạo bản trùng (idempotent)
- **Công thức (D18):** unit test đủ 4 ca chiều dư × có/không lãi quá hạn; bản in KH 131 tách gốc/lãi dưới **Phát sinh Nợ** và lãi làm tăng dư cuối; bản in NCC tách dưới Phát sinh Có
- **Số biên bản (D17):** 2 biên bản cùng tháng của 2 đối tác khác nhau cùng in `09.SL MVL-…./2026`, lưu bình thường, ID bản ghi khác nhau
- **Lập chủ động (D16):** lập tay cho 1 đối tác ra số liệu **giống hệt** biên bản job tự động sinh cho cùng đối tác + kỳ; lập lại cho đối tác đã có biên bản kỳ đó → hệ thống mở bản đang có, không tạo bản thứ hai; job ngày 01 bỏ qua đối tác đã lập tay; hộp thoại chọn 3 đối tác → chỉ sinh đúng 3 biên bản, báo kết quả từng đối tác

---

## 11. Câu hỏi mở & quyết định — **ĐÃ CHỐT ĐỂ BUILD (21/09/2026)**

Toàn bộ câu hỏi mở của SRS_10 (Q1–Q7) đã được giải quyết:

- **Số biên bản (tách khỏi ID bản ghi — D8; để trống phần mã NCC/KH, dạng `09.SL MVL-…./2026` — D17), cấu trúc tài khoản 331/131 (quét cả tài khoản con — D7), quy ước số dương toàn bộ (D9), đối tác vừa NCC vừa KH, kỳ đầu đối chiếu tay song song** — đã chốt, đưa vào thân tài liệu (mục 2, 5, 7, 9)
- **Email gửi đi** — dùng hộp thư hệ thống hiện có, không cần cấu hình riêng (mục 2)
- **Ký số PDF phía Miyano (FR-19)** — đã chốt: gác lại, phát triển ở giai đoạn sau; đợt build này gửi PDF thường (mục 2, 7)
- **Phân công nhân sự thực hiện** — loại khỏi tài liệu vì ngoài phạm vi phân tích nghiệp vụ/tính năng

5 điểm mở cuối cùng đã được chốt ngày 18/09:

| # | Điểm | Quyết định |
|---|---|---|
| O1 | Mốc thời hạn | **Một mốc duy nhất: trước ngày 06 hàng tháng** — cho cả phản hồi đối soát lẫn gửi bản ký. Bỏ mốc ngày 10; câu "gửi về … trước ngày 10" in cứng trong mẫu Excel thay bằng biến ngày 06 (D10). Cần cập nhật QĐ 17 của QL_01 |
| O2 | Số liệu & lãi quá hạn | Mọi số tiền lấy từ GL Entry có lọc ngày, không có field nhập tay cho số gốc; dòng tổng của mẫu tính khi in (D11). Lãi quá hạn chỉ tính ở **chiều còn nợ** (D12) |
| O3 | Khối ký | Bản in **bắt buộc có khối ký của cả 2 bên** (D15). Giữ 1 đại diện chính mỗi bên trong dữ liệu; dòng "2. Đại diện" của mẫu in để trống — ⚠️ nếu cần 2 đại diện có tên mỗi bên thì bổ sung 2 field tùy chọn |
| O4 | Ký số (FR-19) | **Chưa làm ở đợt này và không chặn gì cả** — PDF gửi đi là PDF thường; FR-19 xuống backlog, đã gỡ khỏi mọi mệnh đề Must trong SRS (D13) |
| O5 | Số của bản Amend | Bản Amend là bản ghi mới nhưng **giữ nguyên số biên bản của bản gốc** (D14) |

**Bổ sung 21/09 — D16:** thêm **lập biên bản chủ động** cho 1 hoặc nhiều đối tác, song song với job tự động (chi tiết mục 4.1, FR-20, UC-07). Kỳ lập chủ động tạm chốt là tròn tháng (R-c).

**Bổ sung 21/09 — D17:** số biên bản **để trống phần mã NCC/KH**, chỉ ghi `{Tháng}.SL MVL-…./{Năm}` (ví dụ `09.SL MVL-…./2026`). Số không còn duy nhất theo đối tác — biên bản được phân biệt và chống trùng bằng cặp (đối tác, kỳ).

**Bổ sung 21/09 — D18:** công thức đầy đủ có lãi quá hạn (mục 5); sheet KH 131 chuyển phần tách gốc/lãi sang dưới **Phát sinh Nợ** (mục 3).

**Bổ sung 21/09 — D19:** code nằm trong **module mới `Debt Reconciliation`** của app `erpnext`.

**Bổ sung 21/09 — D20:** trạng thái biên bản do code điều khiển, không dùng Frappe Workflow.

**Bổ sung 21/09 — D21:** đợt này không theo dõi email có gửi tới được hay không.

**Kết luận: BA đã chốt, bắt đầu build.** Còn 3 điểm nhỏ ⚠️ chưa có xác nhận của chị Hà — **build theo giá trị mặc định dưới đây**, nếu chị Hà trả lời khác thì sửa nhỏ, không đổi thiết kế: (1) lãi quá hạn áp dụng **đối xứng** — NCC tính khi dư Có (D12); (2) **1 đại diện** mỗi bên, dòng thứ 2 in trống (D15); (3) chỉ lập biên bản **kỳ tròn tháng** (R-c). Ngoài ra BA V6 + SRS_10 V1.0 đã đồng bộ; thiết kế kỹ thuật chi tiết để build nằm ở **TKKT_10** (`docs/TKKT_10_BienBanDoiChieuCongNo.md`).

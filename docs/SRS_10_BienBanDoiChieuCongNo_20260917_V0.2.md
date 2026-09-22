# SRS_10 — Biên bản đối chiếu & xác nhận công nợ theo kỳ (NCC – TK 331 / KH – TK 131)

| Mã tài liệu | SRS_10_BienBanDoiChieuCongNo |
|---|---|
| Phiên bản | **V1.1 (baseline build 21/09/2026)** — mọi thay đổi sau bản này đi qua CR. Còn 3 điểm ⚠️ nhỏ, build theo giá trị mặc định (xem 12.7) |
| Ngày | 21/09/2026 (V1.0; tên file giữ nguyên hậu tố V0.2) |
| Người lập | Xuân (PM/BA) — Claude hỗ trợ phân tích |
| Người thẩm định nghiệp vụ | Chị Hà (Kế toán) |
| Người phát triển | Hiếu bé (Dev) ⚠️ *QL_01 V1.1 đang ghi Việt phụ trách bước 9b/11b — cần cập nhật QL_01 hoặc xác nhận lại phân công tại sprint planning* |
| Tham chiếu | QL_01_KeHoachTrienKhai_ERP_SCM V1.1 (bước 9b, 11b, 14; Quyết định 17) · Mẫu `BB đối chiếu công nợ.xlsx` (2 sheet: NCC 331, KH 131) · SRS_09 (delta kế toán, sẽ viết) |
| Thành phần hệ thống | **SupplyCore** — code nằm trong **module mới `Debt Reconciliation`** của app `erpnext` (thư mục `erpnext/debt_reconciliation/`) trên ERP-MVL (erp.miyano.com.vn) — D19 |
| Giai đoạn SPD | Không thuộc luồng hàng hóa — nghiệp vụ kế toán hỗ trợ cả Supply (công nợ NCC 331) và Distribution (công nợ KH 131) |
| Ảnh hưởng tồn kho / giá vốn | **Không** — chỉ đọc GL Entry, không sinh bút toán, không chạm Stock Ledger |

## Lịch sử thay đổi

| Phiên bản | Ngày | Nội dung | Người sửa |
|---|---|---|---|
| V0.1 | 17/09/2026 | Bản phân tích nghiệp vụ đầy đủ 12 mục để chốt với Kế toán và Dev trước khi phát triển | Xuân |
| V1.2 | 21/09/2026 | Sửa D7 / FR-05 / R2: tài khoản con xác định theo **số hiệu tiền tố** (331x, 131x), không theo cây — trên production 3311/3312 nằm ngang hàng 331 nên cách cũ bỏ sót, biên bản ra toàn 0. Báo cáo Sổ chi tiết công nợ và biên bản dùng chung một hàm lấy tài khoản | Xuân |
| V1.1 | 21/09/2026 | Chốt để build: (D20) trạng thái điều khiển bằng code, không dùng Frappe Workflow; (D21) không theo dõi kết quả gửi email — Duyệt xong chuyển Đã gửi ngay, Lỗi gửi chỉ còn cho trường hợp thiếu/sai email. Sửa FR-06, FR-10, NFR-06, US-04, UC-03, 12.4, T5, T6 | Xuân |
| V1.0 | 21/09/2026 | Baseline, đồng bộ theo BA V6: (D16) **lập biên bản chủ động** cho 1 hoặc nhiều đối tác — FR-20, UC-07, US-13; (D17) số biên bản **để trống phần mã NCC/KH**: `{Tháng}.SL MVL-…./{Năm}`, chỉ để quản lý giấy tờ, không kiểm tra trùng — chống trùng bằng cặp (đối tác, kỳ); (D18) **công thức đầy đủ có lãi quá hạn** cho từng sheet, sheet KH 131 chuyển phần tách gốc/lãi sang dưới **Phát sinh Nợ**; (D19) code đặt trong **module mới `Debt Reconciliation`** của app `erpnext`; thống nhất option chiều dư `Dư Nợ / Dư Có / Bằng 0`; thêm field `creation_source`; thêm nhánh Đã đối soát khớp → Chênh lệch; thêm T19–T23 | Xuân |
| V0.4 | 18/09/2026 | Chốt nốt 5 điểm mở: (D10) **một mốc duy nhất — trước ngày 06 hàng tháng** cho cả phản hồi đối soát lẫn nhận bản ký, bỏ mốc ngày 10; (D11) mọi số tiền lấy 100% từ GL Entry có lọc ngày, không có field nhập tay cho số gốc; (D12) lãi quá hạn chỉ tính ở **chiều còn nợ**; (D13) **không làm ký số đợt này** — FR-19 xuống backlog, gỡ khỏi mọi mệnh đề Must; (D14) bản Amend là bản ghi mới nhưng **giữ nguyên số biên bản** của bản gốc; (D15) bản in bắt buộc có khối ký **cả 2 bên**. Đóng Q5, Q7; thêm T17–T18 | Xuân |
| V0.3 | 18/09/2026 | Chốt thêm với PO: (D7) số liệu quét TK 331/131 **và toàn bộ tài khoản con**; (D8) **số biên bản là field riêng `statement_no`**, giữ định dạng gốc `09.SL MVL-…/2026`, không dùng làm ID bản ghi; (D9) **mọi số tiền in trên biên bản đều dương** dù dư Nợ hay dư Có → thêm field `opening_direction`. Đóng Q1, Q2; cập nhật FR-05, FR-07, 12.3, 12.6, R2, bổ sung T15–T16 | Xuân |
| V0.2 | 17/09/2026 | Theo ý kiến PO: sinh Draft 10:00 ngày 01; mốc phản hồi đối soát trước ngày 06; chốt quy ước mọi số dư hiển thị dương + công thức dư cuối kỳ (D5); bỏ mục nêu lỗi file mẫu, thay bằng đặc tả đúng; thêm chữ ký số phía Miyano (FR-19); 2 cách xác nhận của đối tác (C1 bản cứng / C2 ký điện tử); bỏ bước khóa sổ khỏi SOP | Xuân |

---

## 1. Thu thập thông tin & đề xuất giải pháp

### 1.1 Nguồn thông tin đã thu thập

| # | Nguồn | Nội dung rút ra |
|---|---|---|
| 1 | Mẫu `BB đối chiếu công nợ.xlsx` | Cấu trúc biên bản 2 chiều: sheet **NCC 331** (Miyano là Bên mua/Bên B) và sheet **KH 131** (Miyano là Bên bán/Bên A); các khối [i] dư đầu kỳ, [ii] phát sinh trong kỳ, [iii] dư cuối kỳ, [iv] kết luận + số tiền bằng chữ; chữ ký 2 bên |
| 2 | QL_01 V1.1 — Quyết định 17, bước 9b/11b | Chu kỳ tháng; gửi đầu tháng; đối tác ký xác nhận trước ngày 10 tháng sau (⚠️ **đã chốt lại thành trước ngày 06** — D10, cần cập nhật QĐ 17 của QL_01); kỳ gửi đầu tiên **01/10/2026** cho công nợ tháng 9; chức năng hoàn thành tuần 21–25/9 (được phép lùi đến 30/9 nếu xung đột với bước 10 — Lưu ý điều hành QL_01) |
| 3 | Phỏng vấn PO (17/9) | 4 quyết định đã chốt — xem 1.3 |
| 4 | Hiện trạng ERP-MVL | ERPNext v15 chạy thật Buying / Stock / Selling / Accounts; HĐĐT FAST qua API; TK 331 = Creditors (Phải trả NCC), TK 131 = Debtors (Phải thu KH) trên Chart of Accounts |
| 5 | Cần thu thập bổ sung (chị Hà) | Danh sách email nhận đối chiếu của từng NCC/KH; số + ngày Hợp đồng nguyên tắc từng đối tác; thời điểm khóa sổ tháng thực tế |

### 1.2 Phân tích mẫu biên bản — mapping từng trường

| Trường trên mẫu | Sheet | Nguồn dữ liệu / cách sinh | Ghi chú |
|---|---|---|---|
| Logo + thông tin Miyano (tên, trụ sở, VPGD, Tel, MST, Email) | Cả 2 | Company + Letter Head chuẩn | Cố định trong Print Format |
| Số biên bản `Số: 01.SL MVL-…./2026` | Cả 2 | Field `statement_no` = `{Tháng}.SL MVL-…./{Năm}` theo `to_date` — phần sau `MVL-` in nguyên `….` | Chỉ để quản lý giấy tờ, **không phải ID bản ghi**, không duy nhất (D8, D17) |
| Ngày lập | Cả 2 | Ngày sinh biên bản (mặc định ngày 01 tháng sau kỳ) | |
| Căn cứ HĐ nguyên tắc (số …, ngày …) | Cả 2 | **Custom Field mới** trên Supplier / Customer | Bước 9b QL_01 đã yêu cầu field này |
| Bên A / Bên B (tên, MST, địa chỉ, Tel) | Cả 2 | Supplier / Customer + Address, Tax ID; phía Miyano lấy từ Company | Sheet NCC: Bên A = NCC, Bên B = Miyano. Sheet KH: Bên A = Miyano, Bên B = KH |
| Đại diện + chức vụ mỗi bên | Cả 2 | Phía Miyano: cấu hình Settings (mặc định bà Đoàn Ngọc Anh — Giám đốc vận hành). Phía đối tác: Custom Field / Contact | |
| Kỳ đối chiếu (từ ngày … đến ngày …) | Cả 2 | `from_date` / `to_date` của biên bản | Mặc định tháng liền trước |
| [i] Dư nợ/có đầu kỳ — (1) Giá trị gốc | Cả 2 | Số dư GL của party trên TK 331/131 và tài khoản con đến hết `from_date − 1`, đổi dấu theo sheet — công thức đầy đủ tại 12.6 (D18) | Truy vấn GL Entry |
| [i]/[ii] (2) Lãi quá hạn | Cả 2 | **Nhập tay, mặc định 0**, chỉ nhập được ở chiều còn nợ (D3, D12). Sheet NCC: phần tách gốc/lãi của kỳ nằm dưới **Phát sinh Có**; sheet KH: nằm dưới **Phát sinh Nợ** (D18 — khác file Excel gốc) | Không build logic tính lãi ở phase này |
| [ii] 1. Phát sinh có trong kỳ | Cả 2 | `SUM(credit)` GL Entry của party, TK 331/131, trong kỳ | NCC: hàng mua vào (tăng phải trả). KH: thu tiền/giảm phải thu |
| [ii] 2. Phát sinh nợ trong kỳ | Cả 2 | `SUM(debit)` GL Entry của party, TK 331/131, trong kỳ | NCC: thanh toán. KH: bán hàng (tăng phải thu) |
| [iii] Dư nợ/có cuối kỳ | Cả 2 | Tính theo công thức đầy đủ tại 12.6 (D18) — hiển thị **số dương** kèm chiều dư (`balance_direction`) | Đã chốt D5, D9 |
| [iv] Kết luận (đã thanh toán trước cho / còn nợ) | Cả 2 | Sinh câu tự động theo **dấu** của dư cuối kỳ | Logic: dư có 331 → "còn nợ"; dư nợ 331 → "đã thanh toán trước"; ngược lại cho 131 |
| Tổng số tiền bằng chữ | Cả 2 | **Hàm đổi số → chữ tiếng Việt** (utility trong app) | Bắt buộc — bước 11b QL_01 |
| Hạn phản hồi đối soát **và hạn nhận bản ký** (trước ngày 06 tháng sau) | Cả 2 | **Tính động** = ngày 06 tháng sau `to_date` (field `response_deadline`) | Đã chốt D6 + D10 — một mốc duy nhất, thay cho câu "trước ngày 10" in trong mẫu gốc |
| Địa chỉ nhận bản cứng + Liên hệ Ms Hà 0949.723.444 | Cả 2 | Settings (cấu hình 1 lần) | |
| Khối chữ ký 2 bên | Cả 2 | Print Format | Giữ dòng "(Ký, đóng dấu và ghi rõ họ tên)" theo đúng mẫu này (mẫu đối ngoại — khác quy ước văn bản nội bộ Miyano) |
| ~~Chữ ký số của Miyano trên file PDF~~ | Cả 2 | **Backlog — không làm đợt này (D13)**; PDF gửi đi là PDF thường | Đối tác vẫn ký điện tử được bằng chứng thư của họ (Cách C2) |

### 1.3 Các quyết định đã chốt với PO (17/09/2026)

| # | Câu hỏi | Quyết định | Hệ quả thiết kế |
|---|---|---|---|
| D1 | Phạm vi gửi mỗi kỳ | **Đối tác có số dư cuối kỳ ≠ 0 HOẶC có phát sinh trong kỳ** (thống nhất lại giữa Quyết định 17 và bước 11b của QL_01) | Job sinh biên bản lọc theo điều kiện này; có checkbox loại trừ thủ công từng đối tác |
| D2 | Luồng gửi | **10:00 ngày 01: hệ thống tự sinh Draft → chị Hà rà và duyệt (được duyệt cả lô) → hệ thống render PDF rồi gửi email** (bước ký số đã bỏ khỏi luồng — D13) | Workflow trạng thái + duyệt hàng loạt + gửi email sau duyệt |
| D3 | Lãi quá hạn | **Nhập tay, mặc định 0**; không build logic tính lãi | Field editable ở trạng thái Nháp; nếu ≠ 0 thì cộng vào tổng dư |
| D4 | Cách đối tác xác nhận | **Trước ngày 06: đối tác gửi email phản hồi đã đối soát Khớp / Chưa khớp. Sau đó xác nhận bằng 1 trong 2 cách: (C1) in, ký đóng dấu, gửi bản cứng về VP Miyano — người nhận: chị Hà; (C2) ký chữ ký điện tử vào PDF biên bản và gửi lại qua email cho chị Hà. Chị Hà cập nhật trạng thái + đính kèm bản ký.** Định hướng GĐ2 (sau 30/10): NCC xác nhận trên Supplier Portal, KH trên Client Portal | Phase này KHÔNG làm màn hình portal; DocType sẵn field (`partner_response`, `confirmation_method`, `confirmed_via`) để portal cập nhật sau |
| D5 | Quy ước hiển thị số dư | **Mọi số Dư nợ/có đầu kỳ và cuối kỳ trên biên bản đều là số dương (giá trị tuyệt đối), không có số âm; chiều dư thể hiện bằng chữ (Dư nợ/Dư có) và câu kết luận** | Công thức tính theo bản chất từng tài khoản — đặc tả tại 12.6; bỏ câu hỏi mở về quy ước dấu |
| D6 | Lịch trình kỳ đối chiếu | **Sinh Draft 10:00 ngày 01 → duyệt & gửi trong ngày 01–02 → đối tác phản hồi đối soát trước ngày 06 → đối tác gửi bản ký (C1/C2) sau khi phản hồi Khớp** | Đã chốt D10: **một mốc duy nhất là trước ngày 06** cho cả phản hồi đối soát lẫn nhận bản ký — không còn mốc ngày 10; cập nhật QĐ 17 của QL_01 theo mốc này |
| D7 | Phạm vi tài khoản lấy số liệu | **Quét TK 331 / 131 và toàn bộ tài khoản con của chúng**, không chỉ một account cố định | Tập tài khoản = mọi tài khoản lá có **số hiệu bắt đầu bằng 331 / 131** (331, 3311, 3312…) của công ty — theo cách đánh số của kế toán VN, **bất kể vị trí trên cây tài khoản ERPNext** — cộng thêm tài khoản lá nằm dưới node 331/131 trên cây (phòng TK con chưa đặt số hiệu). Sửa 21/09 sau lỗi trên production: 3311 và 3312 nằm dưới nhóm "Tài khoản phải trả", **ngang hàng** với 331 chứ không nằm dưới 331 — cách lấy theo cây cũ bỏ sót cả hai nên biên bản ra toàn 0. FR-05 lọc `account IN (cây 331)` cho Supplier / `IN (cây 131)` cho Customer; report đối chiếu tổng (FR-15) cộng theo cùng tập tài khoản. **Không hard-code tên account** — tên thật có hậu tố abbr công ty (site `miyano`: `331 - Phải trả cho người bán - M`) |
| D8 | Số biên bản | **Số biên bản KHÔNG phải ID bản ghi.** ID bản ghi (`name`) do hệ thống tự sinh; số biên bản chỉ để quản lý giấy tờ | Field riêng `statement_no`, sinh khi tạo, read-only, in ở ô "Số:"; định dạng điều chỉnh theo D17 |
| D10 | Mốc thời hạn | **Một mốc duy nhất: trước ngày 06 hàng tháng** — áp dụng cho cả phản hồi đối soát lẫn gửi bản ký về Miyano; bỏ mốc ngày 10 của QĐ 17 | Chỉ 1 field `response_deadline`; câu "gửi về … trước ngày 10" in cứng trong mẫu Excel được thay bằng biến ngày 06; nhắc hạn (FR-14) và cờ Quá hạn đều theo mốc này; cần cập nhật QL_01 |
| D11 | Nguồn số liệu | **Toàn bộ số tiền lấy từ GL Entry, có lọc theo khoảng ngày của kỳ** — không có field nhập tay cho bất kỳ số gốc nào | Các dòng tổng của mẫu (F33 = gốc + lãi, F38 = gốc + lãi) là số **tính tại thời điểm in**, không sinh thêm field lưu trữ; ngoại lệ duy nhất được nhập tay là lãi quá hạn (D3, D12) |
| D12 | Lãi quá hạn | **Chỉ tính ở chiều còn nợ**: bên nào còn nợ thì mới có lãi quá hạn; chiều đã thanh toán trước → lãi = 0, không cộng | KH 131: áp dụng khi dư Nợ (KH còn nợ Miyano). NCC 331: áp dụng khi Miyano còn nợ NCC (dư Có). Validate: chiều "đã thanh toán trước" mà nhập lãi ≠ 0 → chặn. ⚠️ Chị Hà xác nhận lại giúp quy tắc này áp dụng **đối xứng** cho sheet NCC |
| D13 | Chữ ký số (FR-19) | **Không làm ở đợt này và không chặn gì cả** — PDF gửi đi là PDF thường | FR-19 xuống ưu tiên C (backlog); gỡ khỏi D2, FR-03, FR-09, FR-10, UC-03, NFR-02, NFR-13, US-04, US-12, T5, T13, R7, Q7 |
| D14 | Bản Sửa đổi (Amend) | Bản Amend **coi như một bản ghi dữ liệu mới**, mang **đúng số biên bản của bản gốc** | Với D17 điều này tự nhiên đúng (số chỉ phụ thuộc tháng/năm). Chống trùng đặt trên cặp (đối tác, kỳ) trong `validate()`, chỉ xét bản chưa Hủy |
| D15 | Khối chữ ký trên bản in | **Bắt buộc in khối ký của cả 2 bên** (Bên A và Bên B), kèm dòng "(Ký, đóng dấu và ghi rõ họ tên)" đúng mẫu | Print Format luôn render đủ 2 khối. Schema giữ 1 đại diện chính mỗi bên; dòng "2. Đại diện Ông (bà)" của mẫu in để trống, chỉ hiện khi có dữ liệu — ⚠️ nếu chị Hà cần 2 đại diện có tên mỗi bên thì bổ sung 2 field tùy chọn |
| D9 | Dấu của số tiền | **Mọi số tiền in trên biên bản đều là số dương** — dư đầu kỳ, phát sinh nợ, phát sinh có, dư cuối kỳ — bất kể dư Nợ hay dư Có; chiều nợ/có chỉ thể hiện bằng chữ và câu kết luận | Mở rộng D5 sang cả dư đầu kỳ → thêm field `opening_direction`. Giá trị có hướng chỉ tồn tại trong bộ nhớ khi tính toán; field Currency luôn lưu `abs()` |
| D16 | Lập biên bản chủ động | Ngoài job ngày 01, kế toán **chủ động lập biên bản** cho 1 hoặc nhiều đối tác bất kỳ lúc nào | Form tạo mới có nút "Lấy số liệu từ sổ"; hộp thoại "Sinh biên bản kỳ" thêm ô Đối tác (chọn nhiều); dùng chung hàm tính số với job; job bỏ qua đối tác đã lập tay — FR-20, UC-07, US-13 |
| D17 | Định dạng số biên bản | **Để trống phần mã NCC/KH**: `{Tháng}.SL MVL-…./{Năm}`, ví dụ `09.SL MVL-…./2026` | Mọi biên bản cùng tháng cùng số; **không kiểm tra trùng số**; biên bản phân biệt bằng ID bản ghi + cặp (đối tác, kỳ) |
| D18 | Công thức có lãi quá hạn + vị trí lãi trên sheet KH | Công thức đầy đủ tách gốc/lãi cho từng sheet (12.6). Sheet **KH 131**: phần tách (1) gốc / (2) lãi của kỳ nằm dưới **Phát sinh Nợ** (lãi làm tăng nợ phải thu), không nằm dưới Phát sinh Có như file Excel gốc | Print Format KH khác bố cục mẫu Excel ở khối [ii]; sheet NCC giữ nguyên |
| D19 | Vị trí code | Code nằm trong **module mới `Debt Reconciliation`** của app `erpnext` (`erpnext/debt_reconciliation/`) — không tạo app riêng, không đặt trong app SupplyCore | Thay NFR-08 cũ; DocType, report, print format, workflow, job đều thuộc module này |
| D20 | Cách quản lý trạng thái | **Trạng thái do code điều khiển**, không dùng DocType `Workflow` của Frappe (đã đồng ý 21/09) | Nút + hộp thoại trên form gọi 1 method phía server kiểm tra trạng thái nguồn, role và dữ liệu bắt buộc; FR-06 chuyển loại giải pháp từ CH sang PT |
| D21 | Kết quả gửi email | **Đợt này hệ thống KHÔNG theo dõi email có gửi tới được đối tác hay không** (đã chốt 21/09) | Duyệt → tạo PDF + đưa email vào hàng đợi → chuyển **Đã gửi** ngay, `sent_on` = thời điểm đưa vào hàng đợi. Chỉ kiểm tra trước khi gửi: thiếu email hoặc email sai định dạng → **Lỗi gửi** để bổ sung rồi bấm Gửi lại. Không đồng bộ trạng thái Email Queue, không xử lý bounce |

### 1.4 So sánh phương án giải pháp (theo thứ tự ưu tiên mục 6.1 hồ sơ dự án)

| Tiêu chí | **PA-A: Cấu hình chuẩn thuần** — Process Statement of Accounts (PSOA) + Print Format | **PA-B (khuyến nghị): PSOA-style job + DocType mới "Biên bản đối chiếu công nợ"** | PA-C: Excel tay như hiện nay + ERP chỉ xuất số |
|---|---|---|---|
| Loại giải pháp | Cấu hình chuẩn (mức 1) | Phát triển mới có kiểm soát (mức 3) — DocType mới + scheduled job; print/email/naming dùng cơ chế chuẩn | Thủ công |
| Sinh & gửi email định kỳ | ✔ PSOA có sẵn lịch gửi tự động | ✔ Scheduled job đầu tháng | ✘ |
| Đúng mẫu biên bản pháp lý (2 chiều A/B, kết luận, bằng chữ, chữ ký) | ✘ PSOA chỉ in sổ chi tiết/AR-AP statement, không phải "biên bản 2 bên"; không có số biên bản, không có số tiền bằng chữ | ✔ Print Format riêng cho NCC 331 / KH 131 trên cùng DocType | ✔ nhưng điền tay |
| Số biên bản (naming series) | ✘ PSOA không sinh chứng từ per-đối-tác để đánh số | ✔ ID bản ghi do hệ thống tự sinh + số biên bản in theo mẫu giấy (D8, D17) | Đánh tay, dễ trùng |
| Lưu bản đã gửi + trạng thái Đã gửi / Đã xác nhận / Chênh lệch + đính kèm scan | ✘ PSOA không lưu record theo dõi từng đối tác từng kỳ | ✔ Mỗi biên bản là 1 document có workflow, attach, timeline | ✘ theo dõi bằng Excel/trí nhớ |
| Duyệt trước khi gửi (D2) | ✘ PSOA gửi thẳng | ✔ Workflow Nháp → Đã duyệt → Đã gửi | — |
| Lãi quá hạn nhập tay (D3) | ✘ | ✔ | ✔ |
| ~~Ký số PDF phía Miyano~~ (backlog — D13, ngoài đợt này) | ✘ | ✔ khi bổ sung sau, không phải sửa thiết kế | ✘ |
| Sẵn sàng cho portal xác nhận GĐ2 (D4) | ✘ | ✔ portal chỉ cần đổi trạng thái trên document có sẵn | ✘ |
| Kết luận | **Không đạt** — thiếu 5/7 yêu cầu lõi | **Chọn** | Là As-Is, chính là cái cần thay |

**Lý do không dùng được mức thấp hơn (bắt buộc ghi theo mục 6.1):** yêu cầu lõi của nghiệp vụ là *chứng từ đối chiếu có số, có vòng đời trạng thái, lưu vết từng đối tác từng kỳ* — ERPNext chuẩn không có DocType nào mang vai trò này (PSOA là công cụ gửi sổ chi tiết, không phải biên bản xác nhận 2 bên; Journal Entry/Payment Reconciliation là bút toán, sai bản chất). Customize không xâm lấn (mức 2) không tạo được DocType lưu trạng thái. Do đó phải tạo **1 DocType mới không ghi sổ (non-GL, non-stock)** — mức phát triển mới nhỏ nhất có thể; toàn bộ phần còn lại (naming, workflow, print, email, permission, dashboard) dùng cơ chế chuẩn của Frappe. Có thể tham khảo/tái dùng code lấy số dư của PSOA (`frappe.utils get_balance_on`, query GL Entry) thay vì viết lại.

---

## 2. Đánh giá thực trạng — As-Is / To-Be / Gap

### 2.1 As-Is (hiện trạng — cần chị Hà xác nhận lại các dòng đánh dấu ⚠️)

| # | Hoạt động | Cách làm hiện nay | Vấn đề |
|---|---|---|---|
| A1 | Tổng hợp số dư/phát sinh 331, 131 từng đối tác | Chị Hà tra sổ trên ERP-MVL (AR/AP report, GL) rồi chép tay sang Excel ⚠️ | Mất công, dễ sai khi chép; số không gắn thời điểm chốt |
| A2 | Lập biên bản | Điền tay từng file Excel theo mẫu `BB đối chiếu công nợ.xlsx` cho từng đối tác ⚠️ | Với hàng chục NCC/KH mỗi kỳ → nhiều giờ công; lỗi copy-paste khó tránh |
| A3 | Số biên bản | Đánh tay `01.SL MVL-…/2026` ⚠️ | Không có sổ đăng ký tập trung, rủi ro trùng/nhảy số |
| A4 | Số tiền bằng chữ | Gõ tay ⚠️ | Dễ sai chính tả số lớn, dễ sót chưa điền trước khi gửi |
| A5 | Gửi cho đối tác | Email tay từng đối tác từ hộp thư kế toán ⚠️ | Không có log gửi tập trung; dễ sót đối tác |
| A6 | Theo dõi xác nhận (ký gửi lại trước ngày 06 — D10) | Theo dõi tay/Excel ⚠️ | Không ai nhìn được toàn cảnh "kỳ này còn ai chưa xác nhận"; không có nhắc hạn |
| A7 | Xử lý chênh lệch | Trao đổi email/điện thoại, không ghi vết trên hệ thống ⚠️ | Mất lịch sử; kỳ sau lặp lại tranh luận cũ |

### 2.2 To-Be (mục tiêu sau bước 11b, release ≤ 30/9, kỳ gửi đầu 01/10)

| # | Hoạt động | Cách làm mới |
|---|---|---|
| T1 | Ngày 01 hàng tháng, hệ thống **tự sinh** toàn bộ biên bản (Nháp) cho NCC/KH có số dư hoặc phát sinh kỳ trước; số liệu lấy thẳng từ GL Entry | Hết chép tay; số khớp sổ 100% tại thời điểm sinh |
| T2 | Chị Hà mở danh sách, đối soát nhanh, sửa lãi quá hạn nếu có, **duyệt** (cả lô hoặc từng cái) | Một màn hình làm việc duy nhất |
| T3 | Hệ thống **gửi email** kèm PDF đúng mẫu (bản NCC hoặc bản KH) tới email đối chiếu của đối tác, lưu PDF đã gửi vào biên bản | Log gửi tập trung, không sót, có bằng chứng gửi |
| T4 | Trước ngày 06 đối tác email phản hồi **Khớp / Chưa khớp**; sau đó gửi bản ký theo **C1** (bản cứng về VP Miyano — chị Hà nhận) hoặc **C2** (PDF ký điện tử gửi lại email); chị Hà ghi nhận phản hồi, đổi trạng thái **Đã xác nhận** + đính bản ký; Chưa khớp → **Chênh lệch** + ghi chú | Vòng đời chứng từ đầy đủ, tra cứu lại được |
| T5 | Ngày 06, hệ thống nhắc danh sách chưa phản hồi đối soát; tiếp tục theo dõi biên bản đã Khớp nhưng chưa nhận bản ký; dashboard tỷ lệ xác nhận theo kỳ | Đo được KPI chốt công nợ |
| T6 | (GĐ2 — ngoài phạm vi WP này) đối tác tự xác nhận trên Supplier/Client Portal | DocType đã sẵn field, portal chỉ đổi trạng thái |

### 2.3 Gap và cách lấp

| Gap | As-Is → To-Be | Lấp bằng (FR) |
|---|---|---|
| G1 | Chưa có chứng từ đối chiếu trên ERP | DocType mới `Debt Reconciliation Statement` — FR-01 |
| G2 | Thiếu field HĐ nguyên tắc, email đối chiếu, đại diện trên Supplier/Customer | Custom Field — FR-02 |
| G3 | Chưa có sinh tự động định kỳ | Scheduled job đầu tháng — FR-04 |
| G4 | Số liệu chép tay | Query GL Entry tự động — FR-05 |
| G5 | Chưa có sổ đăng ký biên bản tập trung | ID bản ghi hệ thống tự sinh (sổ đăng ký tập trung) + `statement_no` in theo mẫu giấy — FR-07 |
| G6 | Chưa có số tiền bằng chữ tự động | Utility đổi số → chữ VI — FR-08 |
| G7 | Chưa có bản in đúng mẫu trên ERP | 2 Print Format — FR-09 |
| G8 | Gửi email tay, không log | Email tự động sau duyệt + lưu PDF — FR-10, FR-11 |
| G9 | Không theo dõi được trạng thái | Workflow + dashboard + nhắc hạn — FR-06, FR-12..FR-15 |
| G10 | Quy ước hiển thị số dư chưa thành văn | Đã chốt D5 — đặc tả công thức tại 12.6 |
| ~~G11~~ | Biên bản gửi đi chưa có chữ ký số | **Backlog (D13)** — FR-19, không xử lý ở đợt này |

---

## 3. Bảng các bên liên quan (Stakeholders)

| Vai trò | Người | Trách nhiệm trong tính năng này | Quyền quyết định | Tham gia giai đoạn |
|---|---|---|---|---|
| PM / BA / PO | **Xuân** | Viết & bảo trì SRS_10; điều phối chốt yêu cầu; quản lý backlog WP; nghiệm thu cuối; quyết định release cùng Hiếu (dev) | Chốt phạm vi, ưu tiên, chấp nhận CR | Toàn bộ |
| SME Kế toán / Người dùng chính / Approver nghiệp vụ | **Chị Hà** | Xác nhận công thức & cách hiển thị số dư (12.6); cung cấp danh sách email & HĐ nguyên tắc đối tác, thời điểm khóa sổ; thẩm định số liệu bản thử; là người duyệt & gửi biên bản hàng kỳ; cập nhật xác nhận/chênh lệch; UAT | Chốt tính đúng nghiệp vụ kế toán (mục 12.6); ký nghiệm thu UAT | Yêu cầu → UAT → Vận hành |
| Dev | **Hiếu bé** | Ước lượng WP; phát triển DocType, job, print format, email, dashboard trên staging; viết test; chạy thử số liệu tháng 8; release theo checklist bước 8 QL_01 | Chốt giải pháp kỹ thuật trong khuôn khổ SRS; báo sớm nếu vượt effort 2–5 ngày/WP | Thiết kế → Build → Release |

Ghi chú: các bên liên quan **thứ cấp** (không tham gia chốt tài liệu này nhưng chịu ảnh hưởng): NCC/KH (người nhận & ký biên bản — đại diện bởi chị Hà trong giai đoạn này), bà Đoàn Ngọc Anh (người đại diện ký phía Miyano), anh Hiếu nghiệp vụ (mua/bán hàng — liên quan khi xử lý chênh lệch do hóa đơn/giao hàng). ⚠️ Nhắc lại: QL_01 V1.1 phân công **Việt** làm bước 11b; tài liệu này ghi theo yêu cầu mới của PO là **Hiếu bé** — cần chốt tại sprint planning và cập nhật QL_01 (đi qua CR nếu QL_01 đã baseline).

---

## 4. Danh sách quy trình nghiệp vụ

| Mã | Tên quy trình | Tần suất | Người thực hiện chính | Trigger | Kết quả |
|---|---|---|---|---|---|
| QT-01 | Chuẩn bị dữ liệu nền đối tác (HĐ nguyên tắc, email đối chiếu, đại diện, cờ loại trừ) | 1 lần đầu + khi có đối tác mới | Chị Hà (kế toán) | Trước kỳ gửi đầu tiên / có NCC-KH mới | Master data đủ để sinh biên bản |
| QT-02 | Sinh biên bản hàng loạt | Tháng (ngày 01) | Hệ thống (job) / chị Hà chạy tay được | 10:00 ngày 01 hàng tháng (GMT+7) hoặc bấm "Sinh biên bản kỳ" | Bộ biên bản Nháp cho mọi đối tác đạt điều kiện D1 |
| QT-03 | Rà soát & duyệt biên bản | Tháng | Chị Hà | Có biên bản Nháp | Biên bản Đã duyệt (đã sửa lãi quá hạn nếu có) |
| QT-04 | Gửi biên bản cho đối tác | Tháng | Hệ thống | Biên bản chuyển Đã duyệt | Email đã gửi kèm PDF, trạng thái Đã gửi, PDF lưu kèm |
| QT-05 | Ghi nhận phản hồi đối soát & xác nhận | Tháng (phản hồi trước ngày 06; bản ký sau đó) | Chị Hà | Email phản hồi Khớp/Chưa khớp của đối tác; bản ký C1 (bản cứng) / C2 (PDF ký điện tử) | Trạng thái Đã đối soát khớp → Đã xác nhận + bản ký đính kèm |
| QT-06 | Xử lý chênh lệch | Phát sinh | Chị Hà (+ anh Hiếu nghiệp vụ khi liên quan hóa đơn/giao hàng) | Đối tác phản hồi số không khớp | Trạng thái Chênh lệch → truy nguyên → biên bản điều chỉnh (Amend) hoặc ghi nhận kỳ sau |
| QT-07 | Nhắc hạn & báo cáo tình trạng kỳ | Tháng (ngày 06) + xem bất kỳ lúc nào | Hệ thống / Xuân, chị Hà xem | Đến hạn phản hồi đối soát (ngày 06) | Notification danh sách chưa phản hồi / Khớp nhưng chưa có bản ký; dashboard tỷ lệ xác nhận |

Sơ đồ chuỗi: `QT-01 (nền) → QT-02 → QT-03 → QT-04 → QT-05 → [QT-06 nếu lệch] → QT-07`.

---

## 5. Đặc tả chi tiết quy trình nghiệp vụ (SOP)

### SOP-DCCN-01 — Đối chiếu & xác nhận công nợ NCC/KH theo kỳ

| Mục | Nội dung |
|---|---|
| Mục đích | Chốt số công nợ TK 331 (NCC) và TK 131 (KH) với 100% đối tác có số dư hoặc phát sinh: đối tác phản hồi đối soát trước ngày 06 và gửi bản xác nhận có ký (C1 bản cứng / C2 ký điện tử) trong kỳ |
| Phạm vi | Toàn bộ Supplier/Customer active trên ERP-MVL, Company = Miyano Việt Nam |
| Tài liệu liên quan | SRS_10 (tài liệu này), mẫu in NCC 331 / KH 131, QL_01 bước 11b |
| Tần suất / SLA | Tháng; sinh Draft 10:00 ngày 01, duyệt & gửi trong ngày 01–02; đối tác phản hồi đối soát trước ngày 06, sau đó gửi bản ký (C1 bản cứng / C2 ký điện tử) |
| KPI | 100% biên bản gửi trong ngày 01–02; ≥ 90% đối tác phản hồi đối soát trước ngày 06; 100% biên bản có bản ký (C1/C2) trong kỳ; 0 biên bản sai số liệu so với GL tại thời điểm sinh |

| Bước | Người / Hệ thống | Hành động | Đầu vào | Đầu ra | Điểm kiểm soát (⚑) |
|---|---|---|---|---|---|
| 1 | Hệ thống (10:00 ngày 01) | Quét Supplier rồi Customer: tính dư đầu, phát sinh nợ/có, dư cuối kỳ trước trên TK 331/131 theo công thức 12.6; bỏ qua đối tác có cờ loại trừ; tạo biên bản **Nháp**, mỗi đối tác 1 bản | GL Entry; master data QT-01 | Bộ biên bản Nháp + log job (số lượng tạo/bỏ qua/lỗi) | ⚑ Đối tác thiếu email đối chiếu → vẫn tạo biên bản, gắn cảnh báo "thiếu email". ⚑ Số liệu kỳ còn thay đổi sau khi sinh → sinh lại qua bước 7 |
| 2 | Chị Hà | Mở List View lọc kỳ hiện tại; đối soát chọn mẫu với sổ AR/AP; nhập tay Lãi quá hạn nếu có (mặc định 0) | Biên bản Nháp | Biên bản đã rà | ⚑ Tổng dư cuối toàn bộ biên bản NCC = số dư TK 331; tương tự 131 (report đối chiếu tổng) |
| 3 | Chị Hà | **Duyệt** — từng biên bản hoặc chọn nhiều → Duyệt hàng loạt | Biên bản đã rà | Trạng thái Đã duyệt | ⚑ Chỉ role Kế toán (Accounts Manager) duyệt được |
| 4 | Hệ thống | Render PDF theo Print Format đúng loại (NCC 331 / KH 131), đính PDF vào biên bản, gửi email theo template tới email đối chiếu (CC hộp kế toán); đổi trạng thái **Đã gửi**, ghi `sent_on` | Biên bản Đã duyệt | Email + PDF đã gửi, lưu vết | ⚑ Thiếu email / email sai định dạng → trạng thái Lỗi gửi + notification cho chị Hà, KHÔNG âm thầm bỏ qua; không theo dõi email có tới được đối tác (D21) |
| 5 | Đối tác → Chị Hà | Trước ngày 06: đối tác gửi email phản hồi **đã đối soát Khớp / Chưa khớp**; chị Hà ghi nhận vào biên bản (Khớp → trạng thái Đã đối soát khớp; Chưa khớp → bước 6b) | PDF biên bản đã gửi | Phản hồi đối soát được ghi nhận (`partner_response`, `responded_on`) | ⚑ Ngày 06 hệ thống nhắc danh sách chưa phản hồi (bước 8) |
| 6a | Đối tác → Chị Hà | Đối tác xác nhận bằng 1 trong 2 cách: **(C1)** in, ký đóng dấu, gửi bản cứng về VP Miyano (người nhận: chị Hà) — chị Hà scan và đính kèm; **(C2)** ký chữ ký điện tử vào PDF biên bản và gửi lại email cho chị Hà — chị Hà đính file PDF đã ký. Chuyển trạng thái **Đã xác nhận**, ghi `confirmed_on`, chọn `confirmation_method` | Bản ký C1/C2 | Biên bản hoàn tất | ⚑ Bắt buộc đính bản ký + chọn cách xác nhận khi chuyển Đã xác nhận |
| 6b | Chị Hà | Phản hồi Chưa khớp → trạng thái **Chênh lệch**, ghi số của đối tác + diễn giải; truy nguyên (hóa đơn về chậm, khác kỳ ghi nhận, thiếu chứng từ…); phối hợp anh Hiếu nghiệp vụ nếu do giao nhận | Phản hồi đối tác | Ghi chú chênh lệch + hướng xử lý | ⚑ Chênh lệch phải đóng trước kỳ sau hoặc chuyển tiếp có ghi chú |
| 7 | Chị Hà (khi cần) | Số liệu nguồn thay đổi sau khi sinh → **Hủy (Cancel) → Sửa đổi (Amend)** biên bản, sinh lại số liệu, quay lại bước 2 | Biên bản sai | Bản Amend giữ liên kết bản gốc | ⚑ Không sửa đè số liệu trên bản Đã gửi — luôn đi qua Cancel/Amend để giữ vết |
| 8 | Hệ thống (ngày 06) | Notification + email nội bộ: danh sách chưa phản hồi đối soát; kèm danh sách đã Khớp nhưng chưa nhận bản ký | Trạng thái các biên bản | Danh sách nhắc | |
| 9 | Xuân / chị Hà | Xem dashboard tỷ lệ xác nhận, xử lý tồn đọng | Dashboard | Báo cáo kỳ | |

**Ngoại lệ:** (E1) Đối tác vừa có vai NCC vừa là KH → sinh 2 biên bản độc lập (331 và 131 riêng), không bù trừ — trừ khi có thỏa thuận bù trừ công nợ bằng văn bản (ngoài phạm vi phase này, ghi nhận backlog). (E2) Đối tác mới phát sinh giữa kỳ → tự động nằm trong lưới quét kỳ đó. (E3) Kỳ đầu tiên (tháng 9/2026): dư đầu kỳ 01/09 phải khớp số dư khai báo khi đưa số lên ERP — chị Hà xác nhận riêng trước khi gửi (liên quan area "đưa kế toán lên ERPNext").

---

## 6. Bảng yêu cầu chức năng (Functional Requirements)

Quy ước: Ưu tiên **M** = Must (bắt buộc cho kỳ gửi 01/10), **S** = Should (nên có trong WP này nếu kịp), **C** = Could (backlog GĐ2/3). Loại giải pháp: **CH** = cấu hình chuẩn, **CZ** = customize không xâm lấn, **PT** = phát triển mới.

| Mã | Yêu cầu | Mô tả / quy tắc nghiệp vụ | Ưu tiên | Loại | Quy trình |
|---|---|---|---|---|---|
| FR-01 | DocType "Biên bản đối chiếu công nợ" (`Debt Reconciliation Statement`) | Submittable (Draft → Submit → Cancel/Amend); non-GL, non-stock; field spec tại mục 12.3; mỗi bản gắn 1 party (Supplier hoặc Customer) + 1 kỳ; không trùng theo (party_type, party, from_date, to_date) giữa các bản chưa Hủy — bản Amend hợp lệ vì bản gốc đã Hủy | M | PT | Tất cả |
| FR-02 | Custom Field trên Supplier & Customer | `framework_contract_no` (Số HĐ nguyên tắc), `framework_contract_date` (Ngày HĐ), `representative_name` (Người đại diện), `representative_title` (Chức vụ), `reconciliation_email` (Email nhận đối chiếu — fallback: email Contact chính), `exclude_reconciliation` (Loại trừ đối chiếu, checkbox) | M | CZ (fixtures) | QT-01 |
| FR-03 | Màn hình cấu hình "Cài đặt đối chiếu công nợ" (Single DocType `Debt Reconciliation Settings`) | Ngày sinh tự động (mặc định 01), giờ chạy (mặc định 10:00); bật/tắt tự động; TK 331/131 mapping (Account link); người đại diện + chức vụ phía Miyano; người liên hệ + SĐT (Ms Hà); địa chỉ VP Miyano nhận bản cứng (người nhận: chị Hà); Email Template; email CC nội bộ; hạn phản hồi đối soát **và nhận bản ký** (mặc định ngày 06 — D10) | M | PT (settings đơn giản) | QT-02..07 |
| FR-04 | Sinh biên bản tự động đầu tháng | Scheduled job 10:00 ngày 01 (ngày/giờ cấu hình theo FR-03, múi giờ GMT+7) quét toàn bộ Supplier/Customer active của Company; điều kiện tạo: (dư cuối kỳ ≠ 0 HOẶC có phát sinh trong kỳ) VÀ không bật `exclude_reconciliation` (D1); mỗi lần chạy ghi log: tạo/bỏ qua/lỗi; chạy lại không tạo trùng (idempotent — bỏ qua party đã có biên bản kỳ đó chưa Cancel, **kể cả bản lập tay theo FR-20**); `creation_source` = Tự động | M | PT | QT-02 |
| FR-20 | Lập biên bản chủ động (D16) | **(a) Form tạo mới:** chọn Loại đối tác → Đối tác → Kỳ (mặc định tháng liền trước, tròn tháng) → nút **"Lấy số liệu từ sổ"** điền dư đầu, PS nợ, PS có, dư cuối, chiều dư, bằng chữ, thông tin đối tác — cùng hàm tính với FR-04/FR-05; bấm lại được khi còn Nháp, đóng băng từ lúc Duyệt. **(b) Hộp thoại "Sinh biên bản kỳ":** Từ/Đến ngày, Loại đối tác, **Đối tác (chọn nhiều — trống = tất cả đối tác đạt D1)**; báo kết quả từng đối tác: đã tạo / đã có sẵn / lỗi. Quy tắc: mỗi đối tác mỗi kỳ 1 biên bản chưa Hủy — nếu đã có thì mở bản đang có; cho lập cả đối tác không đạt D1 (chỉ cảnh báo); `creation_source` = Thủ công; Accounts Manager + Accounts User được lập | M | PT | QT-02 |
| FR-05 | Tính số liệu từ GL | **Tập tài khoản** = TK 331 (Supplier) / 131 (Customer) **và toàn bộ tài khoản con**, gồm mọi tài khoản lá có số hiệu bắt đầu bằng 331/131, bất kể vị trí trên cây (D7). Dư đầu kỳ = số dư party trên tập tài khoản đó đến hết `from_date − 1`; Phát sinh có = SUM(credit), Phát sinh nợ = SUM(debit) GL Entry (bỏ entry `is_cancelled`) của party trên cùng tập tài khoản trong kỳ; Dư cuối = công thức tại 12.6 (D5 + D9 — lưu và in đều là số dương, chiều dư ghi bằng chữ); số liệu đóng băng tại thời điểm sinh (lưu vào field, không tính lại động). **Không có field nhập tay cho số gốc — mọi số đều từ GL Entry lọc theo ngày (D11)**; riêng lãi quá hạn nhập tay và chỉ áp dụng ở chiều còn nợ (D12) | M | PT (tái dùng util chuẩn `get_balance_on`) | QT-02 |
| FR-06 | Quản lý trạng thái (D20) | Nháp → Đã duyệt → Đã gửi → Đã đối soát khớp → Đã xác nhận; nhánh Chênh lệch khi đối tác phản hồi Chưa khớp (từ Đã gửi hoặc Đã đối soát khớp); nhánh **Lỗi gửi chỉ khi thiếu/sai email** (D21); Quá hạn là **cờ hiển thị** (không phải trạng thái) khi quá `response_deadline` mà chưa có phản hồi đối soát; ai được chuyển trạng thái nào — xem 12.4. **Điều khiển bằng code** (nút + method server), không dùng DocType Workflow | M | PT | QT-03..06 |
| FR-07 | Số biên bản `statement_no` — **chỉ để quản lý giấy tờ** (D8, D17) | Định dạng `{Tháng}.SL MVL-…./{Năm}` — ví dụ `09.SL MVL-…./2026`; tháng/năm theo `to_date`; phần sau `MVL-` in nguyên `….`. Sinh tự động khi tạo, read-only, in ở ô "Số:". **Không duy nhất, không kiểm tra trùng.** ID bản ghi (`name`) do hệ thống tự sinh theo series kỹ thuật `DCCN-.YYYY.-.####.`, không in ra. Bản Amend mang đúng số của bản gốc (D14) | M | PT (sinh `statement_no` khi tạo) | QT-02 |
| FR-08 | Số tiền bằng chữ tiếng Việt | Utility đổi VND → chữ (không lẻ xu), viết hoa chữ cái đầu, kết thúc "đồng ./."; xử lý số âm theo câu kết luận (không in "âm") | M | PT (util nhỏ, viết test kỹ) | QT-04 |
| FR-09 | 2 Print Format theo đúng mẫu | `BB DCCN – NCC 331` (Miyano = Bên B/Bên mua) và `BB DCCN – KH 131` (Miyano = Bên A/Bên bán); chọn tự động theo `party_type`; A4 dọc, tiếng Việt, letter head Miyano; MST/địa chỉ đối tác lấy từ master data (Tax ID, Address); hạn phản hồi và kỳ đối chiếu là biến động; số liệu in **số dương kèm chiều dư** theo 12.6; câu kết luận sinh theo `balance_direction`; **bắt buộc in khối ký của cả 2 bên** kèm dòng "(Ký, đóng dấu và ghi rõ họ tên)" đúng mẫu (D15); câu "gửi về … trước ngày …" in theo `response_deadline` (ngày 06 — D10) | M | CH (Print Format/Jinja) | QT-04 |
| FR-10 | Gửi email kèm PDF sau duyệt | Khi Duyệt → kiểm tra email (thiếu/sai định dạng → Lỗi gửi + notification) → render PDF, đính kèm vào document (lưu bản đã gửi — bước 11b QL_01) → đưa email vào hàng đợi tới `reconciliation_email`, CC hộp kế toán (FR-03); nội dung theo Email Template có biến (tên đối tác, kỳ, hạn ngày 06 cho cả phản hồi đối soát lẫn gửi bản ký, hướng dẫn 2 cách xác nhận C1/C2) → **chuyển Đã gửi ngay**, ghi `sent_on`. **Không theo dõi email có đến được đối tác hay không (D21)** | M | PT (Email Template + hàm gửi) | QT-04 |
| FR-11 | Duyệt & gửi hàng loạt | Từ List View chọn nhiều biên bản Nháp → "Duyệt & gửi" một lần; báo kết quả từng bản (thành công/lỗi) | S | CZ (bulk action client script) | QT-03/04 |
| FR-12 | Ghi nhận phản hồi đối soát & xác nhận | Ghi nhận phản hồi của đối tác trước ngày 06 (`partner_response` Khớp/Chưa khớp, `responded_on`); chuyển Đã xác nhận bắt buộc chọn cách xác nhận (`confirmation_method`: C1 bản cứng / C2 PDF ký điện tử) và đính kèm bản ký (scan bản cứng hoặc PDF đối tác đã ký điện tử); ghi `confirmed_on`; cho phép ghi chú | M | CH (Workflow + validate) | QT-05 |
| FR-13 | Ghi nhận & theo dõi chênh lệch | Chuyển Chênh lệch bắt buộc nhập `dispute_note` (số phía đối tác, diễn giải); field `dispute_resolution` khi đóng; liên kết bản Amend nếu phát hành lại | M | CH/CZ | QT-06 |
| FR-14 | Nhắc hạn ngày 06 | Ngày 06 (theo `response_deadline`): notification + email nội bộ cho chị Hà (và Xuân) danh sách chưa phản hồi đối soát, kèm danh sách đã Khớp nhưng chưa nhận bản ký | S | CH (Notification/Auto Repeat job) | QT-07 |
| FR-15 | Báo cáo & dashboard tình trạng kỳ | Report "Tình trạng đối chiếu công nợ theo kỳ": đếm theo trạng thái, tỷ lệ xác nhận, danh sách quá hạn; Number Card + Dashboard Chart; report đối chiếu tổng: Σ dư cuối biên bản NCC vs số dư TK 331 (tương tự 131) — điểm kiểm soát bước 2 SOP | S | CH (Report Builder/Query Report + Dashboard) | QT-07 |
| FR-16 | Phân quyền | Accounts Manager (chị Hà): full trên biên bản + Settings; Accounts User: tạo/đọc/sửa Nháp, không duyệt; System Manager: quản trị; các role khác: read (Giám đốc); KHÔNG cấp quyền Website User/portal ở phase này (D4) | M | CH (Role Permission) | Tất cả |
| FR-17 | Log & truy vết | Toàn bộ đổi trạng thái, gửi email, sửa lãi quá hạn hiện trong timeline/version của document; log job sinh hàng loạt xem lại được | M | CH (Frappe có sẵn — chỉ cần không tắt track changes) | Tất cả |
| FR-18 | Sẵn sàng portal GĐ2 | Không build UI portal; nhưng DocType có sẵn `confirmed_via` (Thủ công/Portal), `partner_response`, `confirmation_method`; API endpoint đổi trạng thái viết sau không phải sửa schema | C | — | GĐ2 |
| FR-19 | Chữ ký số phía Miyano trên PDF biên bản — **BACKLOG, không làm đợt này (D13)** | Đợt build này **không ký số**: PDF gửi đi là PDF thường và điều này không chặn bất kỳ FR nào khác. Khi nào làm: ký PDF bằng chứng thư số của Công ty TNHH Miyano Việt Nam (chuẩn PAdES) trong bước phát hành, bật/tắt trong Settings, mỗi lần ký ghi log. Thiết kế hiện tại không cần đổi khi bổ sung sau | C | PT (giai đoạn sau) | QT-04 |

## 7. Bảng yêu cầu phi chức năng (Non-Functional Requirements)

| Mã | Nhóm | Yêu cầu | Tiêu chí đo |
|---|---|---|---|
| NFR-01 | Hiệu năng | Sinh hàng loạt cho ≤ 500 đối tác hoàn thành trong ≤ 10 phút, chạy nền (background job), không khóa người dùng khác | Đo trên staging với dữ liệu tháng 8 (bước 11b: chạy thử 2 NCC + 2 KH, sau đó chạy full) |
| NFR-02 | Hiệu năng | Render 1 PDF ≤ 10 giây; mở form biên bản ≤ 2 giây | Test staging |
| NFR-03 | Đúng đắn dữ liệu | Số trên biên bản = số GL tại thời điểm sinh, sai số 0 đồng; report đối chiếu tổng (FR-15) lệch 0 khi mọi party đều có biên bản | Unit test + đối chiếu tay kỳ tháng 8 |
| NFR-04 | Bảo mật | Dữ liệu công nợ chỉ role kế toán/quản trị đọc được; portal user không truy cập được DocType (kiểm tra cả API `/api/resource`) | Test permission bằng user thử từng role |
| NFR-05 | Trình bày | PDF A4 dọc, font Unicode tiếng Việt hiển thị đúng trên bản in và bản đối tác mở bằng máy họ; đúng mẫu đã duyệt | Chị Hà duyệt bản in thử |
| NFR-06 | Tin cậy gửi | Biên bản thiếu email hoặc email sai định dạng phải hiện rõ (trạng thái Lỗi gửi + notification), không im lặng bỏ qua; gửi lại được từng bản. Việc email có tới được đối tác hay không **ngoài phạm vi đợt này** (D21) | Test với email trống / sai định dạng |
| NFR-07 | Múi giờ & lịch | Job chạy theo giờ VN (GMT+7); ngày trên biên bản định dạng dd/mm/yyyy | Kiểm tra cấu hình site |
| NFR-08 | Quy ước code | Fieldname EN + label VI toàn bộ; code đặt trong **module `Debt Reconciliation` của app `erpnext`** (D19), version hóa qua git; theo git flow + checklist release bước 8 QL_01 | Code review |
| NFR-09 | Khả năng bảo trì | Mẫu biên bản đổi chữ nghĩa → chỉ sửa Print Format/Email Template, không sửa code | Review thiết kế |
| NFR-10 | Không hồi quy | Không ảnh hưởng HĐĐT FAST, rename Item (biên bản không chứa mã item — đã ghi trong QL_01), hiệu năng GL | Smoke test sau release |
| NFR-11 | Khả dụng | Chị Hà thao tác được toàn bộ QT-03→05 trên desktop; xem được trạng thái trên mobile web | UAT |
| NFR-12 | Đào tạo | Hướng dẫn sử dụng 1 trang cho kế toán, kèm vào tài liệu HDSD bước 34 QL_01 | Có tài liệu trước release |
| ~~NFR-13~~ (theo FR-19 — backlog, D13) | Bảo mật chữ ký số | Khóa/chứng thư số lưu an toàn trên server (không nằm trong git, không tải được qua UI); chỉ tiến trình ký của hệ thống sử dụng; mỗi lần ký có log (biên bản nào, thời điểm nào) | Review cấu hình + kiểm tra log ký |

---

## 8. Bảng User Stories

Định dạng: *Là [vai trò], tôi muốn [điều gì] để [giá trị]* — kèm Acceptance Criteria (AC) kiểm được.

| Mã | User Story | Acceptance Criteria (Given/When/Then) | FR | Ưu tiên |
|---|---|---|---|---|
| US-01 | Là **chị Hà**, tôi muốn hệ thống tự sinh toàn bộ biên bản đối chiếu kỳ trước vào ngày 01 hàng tháng, để không phải lập tay từng file Excel | (1) Given 10:00 ngày 01/10, When job chạy, Then mọi NCC/KH có dư ≠ 0 hoặc phát sinh trong 01–30/09 đều có đúng 1 biên bản Nháp; (2) đối tác bật cờ loại trừ → không tạo; (3) chạy job lần 2 → không tạo trùng; (4) có log số lượng tạo/bỏ qua/lỗi | FR-04, FR-05 | M |
| US-02 | Là **chị Hà**, tôi muốn số dư đầu/cuối kỳ và phát sinh nợ/có lấy thẳng từ sổ ERP, để biên bản luôn khớp sổ | (1) Số trên biên bản = số trên General Ledger lọc theo party + TK + kỳ, lệch 0; (2) report đối chiếu tổng NCC = dư TK 331, KH = dư TK 131; (3) chứng từ hủy (cancelled) không được tính | FR-05, FR-15 | M |
| US-03 | Là **chị Hà**, tôi muốn rà và duyệt nhiều biên bản một lúc, để xử lý cả kỳ trong một buổi sáng | (1) List View lọc theo kỳ + trạng thái; (2) chọn n bản Nháp → "Duyệt & gửi" → từng bản chuyển trạng thái và có kết quả riêng; (3) bản lỗi không chặn bản khác | FR-06, FR-11 | S |
| US-04 | Là **chị Hà**, tôi muốn sau khi duyệt hệ thống tự gửi email kèm PDF đúng mẫu tới từng đối tác và lưu lại bản đã gửi, để có bằng chứng gửi | (1) Email tới đúng `reconciliation_email`, CC hộp kế toán; (2) PDF đính kèm khớp Print Format theo party_type; (3) PDF được lưu vào biên bản; (4) `sent_on` ghi thời điểm đưa email vào hàng đợi; (5) thiếu email / email sai định dạng → trạng thái Lỗi gửi + notification (không theo dõi bounce — D21) | FR-09, FR-10 | M |
| US-05 | Là **chị Hà**, tôi muốn nhập tay lãi quá hạn (mặc định 0) trước khi duyệt, để xử lý các trường hợp có tính lãi | (1) Field mặc định 0, chỉ sửa được ở Nháp; (2) nếu ≠ 0 thì tổng dư và số bằng chữ cập nhật theo; (3) sửa sau khi duyệt → phải Cancel/Amend | FR-01, FR-08 | M |
| US-06 | Là **chị Hà**, tôi muốn ghi nhận phản hồi đối soát (Khớp/Chưa khớp) trước ngày 06 và cập nhật Đã xác nhận theo đúng cách đối tác dùng (C1 bản cứng / C2 PDF ký điện tử) kèm bản ký, để lưu hồ sơ pháp lý tập trung | (1) Ghi được phản hồi Khớp/Chưa khớp với `responded_on`; (2) chuyển Đã xác nhận mà chưa chọn cách xác nhận hoặc chưa đính bản ký → hệ thống chặn và báo; (3) `confirmed_on` tự ghi; (4) bản ký mở lại được từ biên bản | FR-12 | M |
| US-07 | Là **chị Hà**, tôi muốn ghi nhận biên bản Chênh lệch với số của đối tác và diễn giải, để theo dõi đến khi đóng | (1) Chuyển Chênh lệch bắt buộc nhập ghi chú; (2) danh sách chênh lệch đang mở lọc được; (3) phát hành lại qua Cancel/Amend giữ liên kết bản gốc | FR-13 | M |
| US-08 | Là **chị Hà**, tôi muốn ngày 06 hệ thống nhắc danh sách đối tác chưa phản hồi đối soát và danh sách đã Khớp nhưng chưa gửi bản ký, để đôn đốc kịp | (1) Đúng `response_deadline` (ngày 06), notification + email nội bộ liệt kê biên bản chưa có phản hồi và biên bản Khớp chưa có bản ký; (2) biên bản quá hạn phản hồi hiện cờ Quá hạn trên list | FR-14 | S |
| US-09 | Là **Xuân (PM)**, tôi muốn xem dashboard tỷ lệ xác nhận theo kỳ, để đo KPI chốt công nợ và báo cáo BGĐ | (1) Number card: tổng biên bản, đã gửi, đã xác nhận, chênh lệch, quá hạn của kỳ chọn; (2) drill-down ra danh sách | FR-15 | S |
| US-10 | Là **chị Hà**, tôi muốn khai báo 1 lần thông tin HĐ nguyên tắc, đại diện, email đối chiếu cho từng đối tác, để biên bản tự điền phần căn cứ | (1) Field trên Supplier/Customer; (2) biên bản sinh ra kéo đúng giá trị; (3) đối tác thiếu HĐ nguyên tắc → phần căn cứ in "…" và biên bản có cảnh báo nhưng vẫn tạo được | FR-02 | M |
| US-11 | Là **chị Hà**, tôi muốn chạy lại việc sinh biên bản cho một kỳ tùy chọn, để xử lý kỳ đầu tiên (tháng 9) và các trường hợp sinh lại sau khi sửa sổ | (1) Hộp thoại "Sinh biên bản kỳ" cho chọn from/to + loại đối tác + đối tác (chọn nhiều, trống = tất cả); (2) chỉ role kế toán chạy được; (3) idempotent như US-01 | FR-04, FR-20 | M |
| US-12 | Là **chị Hà**, tôi muốn PDF biên bản gửi đi được ký số bằng chứng thư số của Miyano, để biên bản có giá trị pháp lý cao hơn và đối tác ký điện tử tiếp được (C2) | (1) Mở PDF đã gửi bằng phần mềm đọc PDF phổ biến → chữ ký số Miyano hợp lệ; (2) tắt ký số trong Settings → gửi PDF thường, không lỗi; (3) ký lỗi → biên bản sang Lỗi gửi + notification | FR-19 | **C — backlog (D13)** |
| US-13 | Là **chị Hà**, tôi muốn tự lập biên bản cho đúng một đối tác khi họ yêu cầu, xem số liệu trước khi lưu, để không phải chờ đến ngày 01 | (1) Form tạo mới chọn đối tác + kỳ → "Lấy số liệu từ sổ" ra số giống hệt biên bản job sinh cho cùng đối tác + kỳ; (2) đối tác đã có biên bản kỳ đó → hệ thống mở bản đang có, không tạo bản thứ hai; (3) job ngày 01 bỏ qua đối tác đã lập tay; (4) đối tác dư 0 không phát sinh → vẫn lập được, có cảnh báo | FR-20 | M |

---

## 9. Bảng đặc tả Use case

**Sơ đồ tổng quát (actor → use case):** Chị Hà: UC-01..UC-07; Accounts User: UC-07; Hệ thống (scheduler): UC-01, UC-03, UC-05; Xuân: UC-06; Đối tác (ngoài hệ thống phase này): nhận email, phản hồi đối soát và gửi bản ký trước ngày 06, ký bản cứng (C1) hoặc ký điện tử (C2).

| Mã | UC-01 — Sinh biên bản kỳ (tự động / thủ công) |
|---|---|
| Actor | Scheduler (chính) / Chị Hà (thủ công) |
| Trigger | 10:00 ngày 01 hàng tháng, hoặc bấm "Sinh biên bản kỳ" |
| Precondition | Settings đã cấu hình TK 331/131; kỳ trước có dữ liệu GL |
| Luồng chính | 1. Xác định kỳ (mặc định tháng liền trước) → 2. Lấy danh sách Supplier active → với mỗi NCC: tính dư đầu, PS nợ/có, dư cuối trên TK 331 → 3. Nếu đạt điều kiện D1 và chưa có biên bản kỳ này → tạo biên bản Nháp, đánh số, điền căn cứ HĐ + đại diện + hạn phản hồi đối soát (= ngày 06 tháng sau to_date) → 4. Lặp lại cho Customer trên TK 131 → 5. Ghi log tổng kết, gửi notification "đã sinh xong kỳ …" cho chị Hà |
| Luồng thay thế | A1. Chạy thủ công qua hộp thoại, có thể giới hạn theo đối tác (UC-07 / FR-20). A2. Party đã có biên bản kỳ này (chưa Cancel, kể cả bản lập tay) → bỏ qua, đếm vào log |
| Ngoại lệ | E1. Thiếu email đối chiếu → vẫn tạo, gắn cảnh báo. E2. Lỗi 1 party → ghi log lỗi, tiếp tục party khác (không rollback cả lô). E3. Settings thiếu TK → job dừng, notification lỗi cấu hình |
| Postcondition | Bộ biên bản Nháp + log; không có bản trùng |

| Mã | UC-07 — Lập biên bản chủ động (D16) |
|---|---|
| Actor | Chị Hà (Accounts Manager), Accounts User |
| Trigger | Đối tác yêu cầu biên bản; cần chốt lại sau khi sửa sổ; đối tác mới |
| Precondition | Settings đã cấu hình; đối tác tồn tại trên hệ thống |
| Luồng chính (1 đối tác) | 1. Thêm mới biên bản → 2. Chọn Loại đối tác, Đối tác, Kỳ (mặc định tháng liền trước) → hệ thống điền thông tin đối tác → 3. Bấm "Lấy số liệu từ sổ" → hệ thống tính theo 12.6 → 4. Xem số, nhập lãi quá hạn nếu có (chiều còn nợ) → 5. Lưu → Nháp, `creation_source` = Thủ công, sinh `statement_no` → chuyển UC-02 |
| Luồng thay thế | A1. Nhiều đối tác: hộp thoại "Sinh biên bản kỳ" chọn nhiều đối tác → sinh hàng loạt cho đúng danh sách, báo kết quả từng đối tác. A2. Số liệu sổ đổi khi còn Nháp → bấm lại "Lấy số liệu từ sổ" |
| Ngoại lệ | E1. Đối tác đã có biên bản chưa Hủy cho kỳ đó → không tạo, mở bản đang có. E2. Đối tác dư 0 và không phát sinh → cảnh báo, vẫn cho lưu. E3. Kỳ không tròn tháng → chặn (R-c, ⚠️ chờ chốt) |
| Postcondition | 1 biên bản Nháp cho đúng đối tác + kỳ, số liệu khớp GL tại thời điểm lấy |

| Mã | UC-02 — Rà soát & duyệt biên bản |
|---|---|
| Actor | Chị Hà (Accounts Manager) |
| Precondition | Có biên bản Nháp của kỳ |
| Luồng chính | 1. Mở List View lọc kỳ + Nháp → 2. Mở từng bản cần xem, đối soát; sửa Lãi quá hạn nếu có (số bằng chữ tự cập nhật) → 3. Duyệt từng bản, hoặc chọn nhiều → "Duyệt & gửi" → 4. Trạng thái → Đã duyệt, chuyển tiếp UC-03 |
| Luồng thay thế | A1. Phát hiện số sai do sổ chưa khóa → không duyệt, sửa chứng từ nguồn, chạy lại UC-01 cho party đó (Cancel bản cũ → sinh lại) |
| Ngoại lệ | E1. User không có quyền duyệt → hệ thống chặn |
| Postcondition | Biên bản Đã duyệt, sẵn sàng gửi |

| Mã | UC-03 — Gửi email biên bản |
|---|---|
| Actor | Hệ thống |
| Trigger | Biên bản chuyển sang Đã duyệt |
| Luồng chính | 1. Render PDF theo Print Format đúng party_type → 2. Đính PDF vào document → 3. Gửi email theo template (nêu hạn ngày 06 cho cả phản hồi đối soát lẫn gửi bản ký + hướng dẫn 2 cách xác nhận) tới `reconciliation_email`, CC nội bộ → 4. Ghi `sent_on`, trạng thái → Đã gửi |
| Ngoại lệ | E1. Thiếu email / email sai định dạng → trạng thái Lỗi gửi + notification; chị Hà bổ sung email trên Supplier/Customer rồi bấm "Gửi lại". E2. Lỗi ở máy chủ thư sau khi đã đưa vào hàng đợi → **không xử lý ở đợt này** (D21); Frappe tự retry theo cơ chế chuẩn |
| Postcondition | Đối tác nhận email; hệ thống lưu bằng chứng gửi |

| Mã | UC-04 — Ghi nhận xác nhận / chênh lệch |
|---|---|
| Actor | Chị Hà |
| Trigger | Email phản hồi đối soát của đối tác (trước ngày 06), hoặc bản ký gửi về |
| Luồng chính (xác nhận) | 1. Nhận email phản hồi → ghi nhận vào biên bản: Khớp → trạng thái Đã đối soát khớp (`responded_on` tự ghi); Chưa khớp → luồng chênh lệch → 2. Nhận bản ký: **C1** bản cứng về VP Miyano (chị Hà scan) hoặc **C2** PDF đối tác đã ký điện tử qua email → 3. Đính bản ký, chọn `confirmation_method` → 4. Chuyển Đã xác nhận → `confirmed_on` tự ghi |
| Luồng thay thế (chênh lệch) | B1. Chuyển Chênh lệch, nhập số đối tác + diễn giải → B2. Truy nguyên (mở GL từ biên bản, xem chứng từ) → B3a. Miyano sai → sửa chứng từ nguồn, Cancel/Amend biên bản, gửi lại (UC-03) → B3b. Đối tác sai/khác kỳ ghi nhận → ghi `dispute_resolution`, thống nhất qua email, chuyển Đã xác nhận khi có bản ký mới |
| Ngoại lệ | E1. Chuyển Đã xác nhận thiếu bản ký hoặc thiếu cách xác nhận → chặn. E2. Đối tác gửi bản ký nhưng chưa từng phản hồi đối soát → ghi nhận Khớp + xác nhận trong một lần cập nhật |
| Postcondition | Biên bản đóng vòng đời với đầy đủ hồ sơ |

| Mã | UC-05 — Nhắc hạn xác nhận |
|---|---|
| Actor | Hệ thống |
| Trigger | Ngày = `response_deadline` (mặc định ngày 06) |
| Luồng chính | 1. Quét biên bản kỳ chưa có phản hồi đối soát + biên bản đã Khớp nhưng chưa có bản ký → 2. Notification + email nội bộ danh sách kèm link → 3. Gắn cờ Quá hạn trên list sau deadline |
| Postcondition | Chị Hà có danh sách đôn đốc |

| Mã | UC-06 — Theo dõi & báo cáo tình trạng kỳ |
|---|---|
| Actor | Chị Hà, Xuân |
| Luồng chính | 1. Mở dashboard/report → 2. Chọn kỳ → 3. Xem số lượng theo trạng thái, tỷ lệ xác nhận, danh sách chênh lệch/quá hạn → 4. Drill-down từng biên bản; xem report đối chiếu tổng vs TK 331/131 |
| Postcondition | Số liệu KPI phục vụ điều hành |

---

## 10. Sitemap giao diện

Toàn bộ nằm trong Desk của ERP-MVL (không có màn hình portal ở phase này — D4). Người dùng chính: chị Hà.

```
ERP-MVL (Desk) — Workspace "Kế toán / Accounting"
│
├── 1. Biên bản đối chiếu công nợ (Debt Reconciliation Statement)
│   ├── 1.1 List View  — lọc: Kỳ (from/to), Loại đối tác (NCC/KH), Trạng thái, cờ Quá hạn,
│   │        cờ Thiếu email; cột: Số BB, Đối tác, Kỳ, Dư cuối, Trạng thái, Phản hồi đối soát, Hạn phản hồi
│   │        └── Bulk action: "Duyệt & gửi" (FR-11)
│   ├── 1.2 Form View — khối: Đối tác & căn cứ | Kỳ & số liệu [i][ii][iii] | Kết luận + bằng chữ
│   │        | Gửi & xác nhận (sent_on, PDF đã gửi, phản hồi đối soát, cách xác nhận C1/C2, bản ký, confirmed_on) | Chênh lệch
│   │        └── Nút: Duyệt · Gửi lại · Ghi phản hồi đối soát · Đã xác nhận · Chênh lệch · Xem sổ GL của đối tác
│   ├── 1.3 Print Preview — "BB DCCN – NCC 331" / "BB DCCN – KH 131" (tự chọn theo party_type)
│   ├── 1.4 Hộp thoại "Sinh biên bản kỳ" (from/to, loại đối tác, **đối tác chọn nhiều**) (US-11, FR-20)
│   └── 1.5 Thêm mới biên bản → nút "Lấy số liệu từ sổ" (lập chủ động 1 đối tác — US-13, FR-20)
│
├── 2. Cài đặt đối chiếu công nợ (Debt Reconciliation Settings — Single)
│   └── Lịch tự động (10:00 ngày 01) · TK 331/131 · Đại diện Miyano · Liên hệ & địa chỉ VP nhận bản cứng
│       · Email Template + CC · Hạn phản hồi & nhận bản ký (ngày 06)
│
├── 3. Báo cáo
│   ├── 3.1 Tình trạng đối chiếu công nợ theo kỳ (Query Report — FR-15)
│   └── 3.2 Đối chiếu tổng biên bản vs số dư TK 331/131 (điểm kiểm soát SOP bước 2)
│
├── 4. Dashboard "Đối chiếu công nợ"
│   └── Number Cards: Tổng BB kỳ · Đã gửi · Đã xác nhận · Chênh lệch · Quá hạn
│       + Chart: tỷ lệ xác nhận 6 kỳ gần nhất
│
└── 5. Master data liên quan (form có sẵn, thêm section "Đối chiếu công nợ")
    ├── Supplier — HĐ nguyên tắc, đại diện, email đối chiếu, cờ loại trừ (FR-02)
    └── Customer — như trên
```

(GĐ2 — ngoài phạm vi: mục "Công nợ & đối chiếu" trên Supplier Portal / Client Portal trong `miyano_portal`, chỉ đọc + nút xác nhận, map về đúng document này.)

---

## 11. Ma trận truy vết yêu cầu (RTM)

Yêu cầu nghiệp vụ gốc (BR):

| Mã | Yêu cầu nghiệp vụ | Nguồn |
|---|---|---|
| BR-01 | Chốt số công nợ theo kỳ tháng với mọi NCC (331) / KH (131) có số dư hoặc phát sinh | QĐ 17 QL_01 + D1 |
| BR-02 | Biên bản đúng mẫu pháp lý 2 bên của Miyano, có số, có số tiền bằng chữ | Mẫu xlsx + bước 9b |
| BR-03 | Tự sinh 10:00 ngày 01, kế toán duyệt, hệ thống gửi email; đối tác phản hồi đối soát **và gửi bản ký trước ngày 06**, bằng bản cứng (C1) hoặc ký điện tử (C2) | Bước 9b/11b + D2, D4, D6, D10 |
| BR-04 | Theo dõi tập trung: đã gửi / đã xác nhận / chênh lệch / quá hạn, lưu bản đã gửi & bản ký | Bước 11b |
| BR-05 | Số liệu duy nhất từ sổ ERP (ERPNext là sổ chính), không nhập tay số dư | Nguyên tắc kiến trúc dự án |

| BR | FR | US | UC | SOP bước | Màn hình (Sitemap) | Kiểm thử (UAT case — mục 12.8) |
|---|---|---|---|---|---|---|
| BR-01 | FR-04, FR-05, FR-02, FR-20 | US-01, US-10, US-11, US-13 | UC-01, UC-07 | 1 | 1.1, 1.4, 1.5, 5 | T1, T2, T8, T19, T20 |
| BR-02 | FR-07, FR-08, FR-09 | US-04, US-05 | UC-03 | 4 | 1.3 | T3, T4 |
| BR-03 | FR-03, FR-06, FR-10, FR-11 | US-03, US-04 | UC-02, UC-03 | 3–6a | 1.1, 1.2, 2 | T5, T6 |
| BR-04 | FR-06, FR-12, FR-13, FR-14, FR-15, FR-17 | US-06, US-07, US-08, US-09 | UC-04, UC-05, UC-06 | 5–9 | 1.2, 3, 4 | T7, T9, T10, T14 |
| BR-05 | FR-05, FR-15, NFR-03 | US-02 | UC-01, UC-06 | 1–2 | 3.2 | T2, T11 |

Kiểm tra phủ: mọi FR M/S đều truy về ≥ 1 BR; FR-01 (DocType nền) phục vụ mọi BR; FR-16..17 là yêu cầu nền phủ ngang (bảo mật/truy vết); FR-18 (C) truy về D4 định hướng GĐ2; FR-19 đã chuyển backlog (D13) nên không còn trong lưới truy vết của đợt build này — không có yêu cầu mồ côi.

---

## 12. Tài liệu SRS tổng hợp

### 12.1 Phạm vi

**Trong phạm vi WP này (hạn 25/9, được lùi ≤ 30/9; kỳ gửi đầu 01/10):** toàn bộ FR ưu tiên M; FR S làm nếu còn thời gian, không chặn release. **Ngoài phạm vi:** xác nhận online qua portal (GĐ2, sau 30/10 — theo SRS_08); tính lãi quá hạn tự động; bù trừ công nợ 2 chiều cho đối tác vừa là NCC vừa là KH; đối chiếu chi tiết theo từng hóa đơn (biên bản hiện chỉ chốt 4 số tổng — nếu đối tác đòi bảng kê chi tiết, kế toán gửi kèm General Ledger xuất từ ERP, cân nhắc thành FR ở CR sau). **Cập nhật V0.4 (D13):** chữ ký số phía Miyano (FR-19) **ra khỏi phạm vi đợt này** — PDF gửi đi là PDF thường, và việc này không chặn FR nào khác. Việc đối tác ký điện tử (C2) dùng công cụ và chứng thư của chính đối tác — ngoài hệ thống, Miyano chỉ nhận file PDF kết quả.

### 12.2 Giả định & ràng buộc

| # | Nội dung | Loại |
|---|---|---|
| R1 | Số liệu 331/131 trên ERP-MVL đầy đủ và đúng từ kỳ tháng 9/2026 (phụ thuộc tiến độ đưa kế toán lên ERPNext); dư đầu kỳ 01/09 khớp số khai báo ban đầu | Ràng buộc — điều kiện tiên quyết kỳ gửi 01/10 |
| R2 | Công nợ party nằm trên TK 331/131 **và các tài khoản con** của chúng; tập tài khoản = mọi TK lá có số hiệu bắt đầu bằng 331/131, bất kể vị trí trên cây (đã chốt D7 — thay cho giả định "1 account cố định"); GL Entry luôn có `party_type`/`party` trên các tài khoản này (kiểm tra bằng rà soát orphan party trước kỳ đầu) | Đã chốt V0.3 |
| R3 | Email server của site đã cấu hình và gửi được ra ngoài (đang dùng cho HĐĐT/notification) | Giả định |
| R4 | Khối lượng hiện tại ~vài chục NCC/KH hoạt động; thiết kế chịu tới 500 (NFR-01) | Giả định |
| R5 | Release theo checklist bước 8 QL_01 (staging trước, backup, cửa sổ cuối tuần/tối) | Ràng buộc |
| R6 | Biên bản không chứa mã Item → độc lập với rename Item 2/10; không cần regression riêng, chỉ smoke test | Ràng buộc đã ghi QL_01 |
| ~~R7~~ | Chứng thư số doanh nghiệp — **không còn là giả định của đợt này** (D13: không làm ký số) | Đã gỡ |

### 12.3 Đặc tả dữ liệu — DocType `Debt Reconciliation Statement` (Biên bản đối chiếu công nợ)

Submittable; naming series FR-07; track changes bật.

| Fieldname (EN) | Label (VI) | Kiểu | Bắt buộc | Nguồn/validate |
|---|---|---|---|---|
| naming_series | (ID kỹ thuật — không in ra) | Select/Series | ✔ | `DCCN-.YYYY.-.####.`; chỉ làm `name` của bản ghi, **không phải số biên bản** (D8) |
| statement_no | Số biên bản | Data (read-only) | ✔ | `{Tháng}.SL MVL-…./{Năm}` theo `to_date` (D17) — chỉ để quản lý giấy tờ, in ở ô "Số:"; **không duy nhất, không kiểm tra trùng**; bản Amend mang đúng số bản gốc (D14) |
| creation_source | Nguồn tạo | Select (Tự động / Thủ công) | ✔ | Tự động = job FR-04; Thủ công = FR-20; read-only |
| company | Công ty | Link Company | ✔ | Mặc định Miyano VN |
| party_type | Loại đối tác | Select (Supplier/Customer) | ✔ | Quy định Print Format + TK |
| party | Đối tác | Dynamic Link | ✔ | |
| party_name | Tên đối tác | Data (fetch) | ✔ | Read-only |
| party_tax_id | MST đối tác | Data (fetch) | | Từ Tax ID của Supplier/Customer |
| party_address | Địa chỉ đối tác | Small Text (fetch) | | Address chính |
| framework_contract_no | Số HĐ nguyên tắc | Data (fetch từ party) | | In "…" nếu trống + cảnh báo |
| framework_contract_date | Ngày HĐ nguyên tắc | Date (fetch) | | |
| party_representative | Đại diện đối tác | Data (fetch) | | |
| party_representative_title | Chức vụ | Data (fetch) | | |
| company_representative | Đại diện Miyano | Data | ✔ | Default từ Settings |
| company_representative_title | Chức vụ | Data | ✔ | Default từ Settings |
| account | Tài khoản công nợ | Link Account | ✔ | 331 (Supplier) / 131 (Customer) từ Settings |
| from_date / to_date | Kỳ từ ngày / đến ngày | Date | ✔ | to ≥ from; tròn tháng (R-c); mỗi (party_type, party, from_date, to_date) chỉ 1 bản chưa Hủy |
| posting_date | Ngày lập | Date | ✔ | Mặc định ngày sinh |
| opening_principal | Dư đầu kỳ — giá trị gốc | Currency | ✔ | \|G_đ\| theo 12.6, đóng băng khi Duyệt |
| opening_interest | Dư đầu kỳ — lãi quá hạn | Currency | | Nhập tay, mặc định 0 (D3); chỉ nhập được ở chiều còn nợ (D12) |
| opening_direction | Chiều dư đầu kỳ | Select (Dư Nợ / Dư Có / Bằng 0) | ✔ | Tự tính theo 12.6 — dư đầu kỳ in số dương kèm chiều dư (D9) |
| credit_in_period | Phát sinh có trong kỳ — gốc | Currency | ✔ | C = Σ credit GL trong kỳ (FR-05) |
| debit_in_period | Phát sinh nợ trong kỳ — gốc | Currency | ✔ | D = Σ debit GL trong kỳ (FR-05) |
| interest_in_period | Lãi quá hạn phát sinh | Currency | | Nhập tay, mặc định 0; chỉ nhập được ở chiều còn nợ (D12). NCC: cộng vào Phát sinh Có; KH: cộng vào Phát sinh Nợ (D18) |
| closing_balance | Dư cuối kỳ | Currency | ✔ | \|Cuối\| theo 12.6, read-only |
| balance_direction | Chiều dư cuối kỳ | Select (Dư Nợ / Dư Có / Bằng 0) | ✔ | Tự tính theo 12.6; cùng bộ option với `opening_direction`; câu kết luận [iv] sinh từ `party_type` + chiều dư |
| amount_in_words | Số tiền bằng chữ | Data (auto) | ✔ | FR-08, read-only |
| response_deadline | Hạn phản hồi & nhận bản ký | Date | ✔ | = ngày 06 tháng sau `to_date` (cấu hình FR-03); **một mốc duy nhất cho cả hai việc (D10)** |
| reconciliation_email | Email gửi đối chiếu | Data (fetch, sửa được ở Nháp) | | Cảnh báo nếu trống |
| status | Trạng thái | Select (workflow) | ✔ | 12.4 |
| sent_on | Thời điểm gửi | Datetime | | Auto UC-03 |
| sent_pdf | Bản PDF đã gửi | Attach | | Auto UC-03 (lưu bản đã gửi); đợt này là PDF thường, không ký số (D13) |
| partner_response | Phản hồi đối soát | Select (Chưa phản hồi/Khớp/Chưa khớp) | ✔ | Mặc định Chưa phản hồi (D4, D6) |
| responded_on | Ngày phản hồi đối soát | Date | | Ghi khi có phản hồi |
| confirmation_method | Cách xác nhận | Select (C1 – Bản cứng/C2 – Ký điện tử) | ✔ khi Confirmed | FR-12 |
| confirmed_on | Ngày xác nhận | Date | | Auto khi Confirmed |
| signed_copy | Bản xác nhận có ký (scan bản cứng C1 / PDF đối tác ký điện tử C2) | Attach | ✔ khi Confirmed | Validate FR-12 |
| confirmed_via | Kênh xác nhận | Select (Thủ công/Portal) | | Mặc định Thủ công (FR-18) |
| dispute_amount | Số theo đối tác | Currency | ✔ khi Disputed | |
| dispute_note | Diễn giải chênh lệch | Small Text | ✔ khi Disputed | |
| dispute_resolution | Kết quả xử lý | Small Text | | |
| amended_from | Sửa đổi từ | Link (chuẩn Frappe) | | Cancel/Amend |

**Quy ước lưu trữ (D9):** mọi field Currency ở trên lưu **giá trị tuyệt đối** (≥ 0). Giá trị có hướng chỉ dùng trong bộ nhớ khi tính dư cuối kỳ theo 12.6; kết quả ghi xuống field là `abs()` kèm `opening_direction` / `balance_direction`. Không field nào được phép mang số âm.

Custom Field trên **Supplier/Customer** (FR-02) và **Settings** (FR-03): như đã liệt kê tại FR — khai báo trong **module `Debt Reconciliation` của app `erpnext`** (D19); chi tiết kỹ thuật tại TKKT_10.

### 12.4 Workflow & phân quyền

| Chuyển trạng thái | Ai được làm | Điều kiện |
|---|---|---|
| (job / lập chủ động) → Nháp | Hệ thống / Accounts Manager, Accounts User | FR-04, FR-20 |
| Nháp → Đã duyệt | **Accounts Manager** (chị Hà) | Số liệu đã đóng băng; email nên có |
| Đã duyệt → Đã gửi | Hệ thống (ngay sau duyệt) | Email hợp lệ, PDF đã tạo, email đã vào hàng đợi (D21) |
| Đã duyệt → Lỗi gửi | Hệ thống | Chỉ khi thiếu email / email sai định dạng (D21); nút "Gửi lại" quay về luồng |
| Đã gửi → Đã đối soát khớp | Accounts Manager | Có email phản hồi Khớp của đối tác (`responded_on` tự ghi) |
| Đã gửi / Đã đối soát khớp → Đã xác nhận | Accounts Manager | Bắt buộc `confirmation_method` (C1/C2) + đính `signed_copy` |
| Đã gửi → Chênh lệch | Accounts Manager | Đối tác phản hồi Chưa khớp; bắt buộc `dispute_amount` + `dispute_note` |
| Đã đối soát khớp → Chênh lệch | Accounts Manager | Đối tác báo Khớp rồi sau đó phát hiện lệch; bắt buộc `dispute_amount` + `dispute_note` |
| Chênh lệch → Đã xác nhận | Accounts Manager | Sau khi thống nhất, có bản ký |
| Bất kỳ (đã submit) → Hủy → Sửa đổi | Accounts Manager | Cancel/Amend chuẩn, giữ vết |

Role matrix: Accounts Manager = CRUD + duyệt + Settings; Accounts User = tạo/đọc/sửa Nháp; System Manager = quản trị kỹ thuật; role khác được cấp Read theo nhu cầu (BGĐ). Không có quyền cho Website User (phase này).

### 12.5 Ảnh hưởng hệ thống

| Hạng mục | Đánh giá |
|---|---|
| Stock Ledger / giá vốn | Không chạm |
| GL | Chỉ đọc GL Entry; không sinh bút toán |
| HĐĐT FAST | Không liên quan (không gọi API FAST); smoke test sau release chung |
| Rename Item 2/10 | Không ảnh hưởng (không chứa item) — theo Lưu ý điều hành QL_01 |
| Portal | Phase này: không. GĐ2: thêm view + action xác nhận trên `miyano_portal`, phụ thuộc một chiều portal → lõi, portal chỉ đổi trạng thái qua API được phép — đúng nguyên tắc kiến trúc dự án |
| Hiệu năng site | Job nền đầu tháng; giờ chạy 10:00 cấu hình được nếu trùng giờ cao điểm |
| Chữ ký số | **Không áp dụng ở đợt này (D13)** — không cần chứng thư số, không có bước ký trên server |

### 12.6 Quy ước hiển thị & công thức số dư (ĐÃ CHỐT — D5)

Đã chốt với PO ngày 17/09: **mọi số liệu Dư nợ/có đầu kỳ và cuối kỳ in trên biên bản đều là số dương (giá trị tuyệt đối), không có số âm.** Chiều của số dư thể hiện bằng trường `balance_direction` (Dư nợ / Dư có) và câu kết luận [iv].

Cách tính: hệ thống lưu **giá trị có hướng** nội bộ để cộng trừ; khi in lấy **trị tuyệt đối** kèm chiều dư.

| Sheet | Quy ước giá trị có hướng (nội bộ) | Công thức dư cuối kỳ (giá trị có hướng) | Hiển thị & câu kết luận |
|---|---|---|---|
| NCC 331 | Dương = Miyano còn nợ NCC → **Dư Có**; âm → **Dư Nợ** | `Cuối = Đầu + PS Có − PS Nợ` (chi tiết có lãi bên dưới) | In \|Cuối\| (số dương); Cuối > 0 → "Miyano còn nợ tiền mua hàng của NCC"; Cuối < 0 → "Miyano đã thanh toán trước cho NCC"; = 0 → "hai bên không còn công nợ" |
| KH 131 | Dương = KH còn nợ Miyano → **Dư Nợ**; âm → **Dư Có** | `Cuối = Đầu + PS Nợ − PS Có` (chi tiết có lãi bên dưới) | In \|Cuối\| (số dương); Cuối > 0 → "KH còn nợ tiền mua hàng của Miyano"; Cuối < 0 → "KH đã thanh toán trước cho Miyano"; = 0 → "hai bên không còn công nợ" |

**Công thức đầy đủ có lãi quá hạn (D18 — nguồn duy nhất cho hàm tính số dùng chung của FR-04 và FR-20):**

Ký hiệu: `D` = Σ debit, `C` = Σ credit của GL Entry (không bị hủy) của party trên tập tài khoản D7, trong kỳ `[from_date, to_date]`; `D₀`, `C₀` = như trên nhưng `posting_date < from_date`; `L_đ` = lãi quá hạn đầu kỳ, `L_ps` = lãi quá hạn phát sinh (nhập tay, ≥ 0).

| Đại lượng | NCC 331 | KH 131 | Ô trên mẫu |
|---|---|---|---|
| Dư đầu gốc có hướng `G_đ` | `C₀ − D₀` | `D₀ − C₀` | F35 = \|G_đ\| |
| Dư đầu kỳ `Đầu` | `G_đ + L_đ` | `G_đ + L_đ` | F33 = \|Đầu\|, F36 = L_đ |
| Phát sinh Có | `C + L_ps` (F39 = C, F40 = L_ps) | `C` (một dòng, không tách) | F38 |
| Phát sinh Nợ | `D` (một dòng, không tách) | `D + L_ps` (**gốc = D, lãi = L_ps — tách dưới dòng Phát sinh Nợ**) | F41 |
| Dư cuối `Cuối` | `Đầu + (C + L_ps) − D` | `Đầu + (D + L_ps) − C` | F43 = F48 = \|Cuối\| |

Điều kiện lãi (D12): `L_đ` chỉ được > 0 khi `G_đ > 0`; `L_ps` chỉ được > 0 khi `Cuối` tính với `L_ps = 0` là > 0. Vi phạm → chặn khi lưu. Chiều dư: `opening_direction` theo dấu của `Đầu`, `balance_direction` theo dấu của `Cuối`, ánh xạ Dư Nợ/Dư Có theo cột "quy ước" ở bảng trên. Lưu ý đổi dấu: ERPNext lưu số dư theo quy ước `debit − credit`, nên với sheet NCC `G_đ` là **số đối** của số dư ERPNext.

Quy tắc bổ sung: (a) Dư đầu kỳ hiển thị cùng cách — số dương + ghi rõ Dư nợ/Dư có; (b) Phát sinh nợ/có luôn ≥ 0 (là tổng debit/credit của GL Entry trong kỳ, không bù trừ); (c) Lãi quá hạn nhập tay (D3) cộng cùng chiều với giá trị gốc; (d) câu kết luận [iv] và số tiền bằng chữ sinh từ `balance_direction` + \|Cuối\|, tuyệt đối không in dấu âm. (e-bis) **D12 — lãi quá hạn theo chiều dư:** chỉ tính lãi ở chiều còn nợ — KH 131 khi dư Nợ (KH còn nợ Miyano), NCC 331 khi dư Có (Miyano còn nợ NCC); chiều "đã thanh toán trước" thì lãi = 0 và không cộng vào tổng; hệ thống chặn nếu nhập lãi ≠ 0 ở chiều trả trước. (e) **D9 — mở rộng phạm vi quy ước:** không chỉ dư đầu/cuối kỳ mà **toàn bộ số tiền** trên biên bản (kể cả phát sinh nợ, phát sinh có, lãi quá hạn, tổng số tiền kết luận) đều in số dương; dư đầu kỳ dùng `opening_direction`, dư cuối kỳ dùng `balance_direction`; hệ thống không bao giờ ghi số âm xuống field Currency. Hiếu bé viết unit test 4 ca: NCC dư có, NCC trả trước (dư nợ), KH dư nợ, KH trả trước (dư có) — kiểm cả giá trị in và câu kết luận (T12).

### 12.7 Câu hỏi mở còn lại (chốt tại buổi làm việc Xuân – chị Hà – Hiếu bé)

| # | Câu hỏi | Người trả lời | Chặn gì |
|---|---|---|---|
| ~~Q1~~ | ✅ **ĐÃ CHỐT (V1.0 — D8, D17):** `statement_no` = `{Tháng}.SL MVL-…./{Năm}`, để trống phần mã NCC/KH, chỉ để quản lý giấy tờ; ID bản ghi do hệ thống tự sinh | Chị Hà | — |
| ~~Q2~~ | ✅ **ĐÃ CHỐT (V0.3 — D7):** quét TK 331/131 **và toàn bộ tài khoản con**. Lưu ý kỹ thuật: nếu sau này mở tài khoản con ngoại tệ, GL Entry vẫn quy ra VND — biên bản in VND theo mẫu | Chị Hà | — |
| Q3 | Email gửi đi dùng địa chỉ nào (hộp kế toán riêng hay mvl.invoices2024@gmail.com), và chữ ký email? | Chị Hà | FR-10 cấu hình Email Account |
| Q4 | Kỳ đầu 01/10: dữ liệu 331/131 tháng 9 trên ERP đã đủ tin cậy chưa, hay kỳ đầu chạy song song (hệ thống sinh + chị Hà đối chiếu tay 100% trước khi gửi)? | Chị Hà + Xuân | Kế hoạch release bước 14 |
| ~~Q5~~ | ✅ **ĐÃ CHỐT (V0.4 — D10):** một mốc duy nhất **trước ngày 06** cho cả phản hồi đối soát lẫn nhận bản ký; bỏ mốc ngày 10 → cập nhật QĐ 17 của QL_01. Phần phân công nhân sự (a) nằm ngoài phạm vi tài liệu này | Xuân + chị Hà | — |
| Q6 | Đối tác vừa là NCC vừa là KH: xác nhận không bù trừ, gửi 2 biên bản riêng? | Chị Hà | SOP ngoại lệ E1 |
| ~~Q7~~ | ✅ **ĐÃ CHỐT (V0.4 — D13):** chưa làm ký số ở đợt này, gửi PDF thường, **không chặn gì cả**. Khi nào quyết định làm sẽ mở CR riêng | Xuân + Hiếu bé | — |

### 12.8 Kế hoạch kiểm thử chấp nhận (UAT — chạy trên staging với số liệu tháng 8, theo bước 11b)

| Mã | Ca kiểm thử | Kết quả mong đợi | Người |
|---|---|---|---|
| T1 | Chạy job sinh kỳ 01–31/08 | Đủ biên bản cho mọi party đạt D1; log đúng; chạy lại không trùng | Hiếu bé + chị Hà |
| T2 | Đối chiếu 2 NCC + 2 KH với sổ GL (theo 11b) | Lệch 0 đồng cả 4 số [i][ii][iii] | Chị Hà |
| T3 | In thử 2 Print Format | Đúng mẫu đã duyệt, đúng bên A/B, MST/địa chỉ đối tác lấy đúng từ master data, số liệu in số dương kèm chiều dư, tiếng Việt chuẩn | Chị Hà |
| T4 | Số tiền bằng chữ | Đúng với ≥ 10 giá trị biên (0; lẻ trăm; tỷ; hàng chục tỷ như 56.001.171.083) | Hiếu bé (unit test) + chị Hà |
| T5 | Duyệt & gửi hàng loạt tới 2 NCC + 2 KH (email test) | Email + PDF đính kèm đúng; sent_on, PDF lưu trên document | Chị Hà |
| T6 | Party thiếu email / email sai định dạng | Trạng thái Lỗi gửi + notification; Gửi lại được sau khi bổ sung. (Không kiểm thử trường hợp máy chủ thư từ chối — D21) | Hiếu bé |
| T7 | Xác nhận C1 (scan bản cứng) và C2 (PDF ký điện tử); chênh lệch thiếu ghi chú | 2 ca xác nhận thành công với đúng `confirmation_method`; ca thiếu ghi chú/thiếu bản ký bị chặn đúng validate | Chị Hà |
| T8 | Party bật cờ loại trừ; party dư 0 không phát sinh | Không sinh biên bản | Hiếu bé |
| T9 | Cancel/Amend sau khi đã gửi | Bản mới giữ liên kết, số biên bản mới theo quy ước Amend, vết đầy đủ | Hiếu bé |
| T10 | Nhắc hạn ngày 06 (giả lập ngày) | Notification đúng danh sách chưa phản hồi đối soát + danh sách Khớp nhưng chưa có bản ký | Hiếu bé |
| T11 | Report đối chiếu tổng | Σ biên bản NCC = dư TK 331; Σ KH = dư TK 131 | Chị Hà |
| T12 | Test 4 ca chiều số dư (12.6) | Số in luôn dương, đúng chiều dư và câu kết luận cả 4 ca | Hiếu bé (unit test) |
| ~~T13~~ (backlog — D13, không chạy ở đợt này) | Ký số PDF (FR-19) | Chữ ký số Miyano hợp lệ khi mở PDF bằng phần mềm đọc phổ biến; tắt ký số → gửi bình thường; ký lỗi → Lỗi gửi + notification | Hiếu bé + chị Hà |
| T14 | Ghi nhận phản hồi đối soát | Khớp → Đã đối soát khớp, `responded_on` đúng; Chưa khớp → Chênh lệch | Chị Hà |
| T15 | Tài khoản con (D7): mở 1 TK con của 331 (ví dụ 3311), post phát sinh của 1 NCC lên TK con | Biên bản của NCC đó gộp đủ phát sinh trên cả 331 và 3311; report đối chiếu tổng vẫn lệch 0 | Hiếu bé |
| T16 | Dấu hiển thị (D9) | Không có ô nào trên bản in mang dấu âm ở cả 4 ca chiều dư; `opening_direction` / `balance_direction` đúng chiều | Hiếu bé + chị Hà |
| T17 | Lãi quá hạn theo chiều dư (D12) | Chiều còn nợ: nhập lãi → cộng đúng vào tổng và vào số tiền bằng chữ. Chiều đã trả trước: nhập lãi ≠ 0 → hệ thống chặn; lãi giữ 0 | Hiếu bé + chị Hà |
| T18 | Amend giữ số biên bản (D14) | Hủy 1 biên bản rồi Amend → bản mới có **đúng `statement_no` cũ**, `amended_from` trỏ về bản gốc, không báo trùng; bản gốc vẫn tra cứu được | Hiếu bé |
| T19 | Lập chủ động 1 đối tác (FR-20a) | Số liệu **giống hệt** biên bản job sinh cho cùng đối tác + kỳ; `creation_source` = Thủ công; lập lần 2 cùng kỳ → mở bản đang có | Hiếu bé + chị Hà |
| T20 | Hộp thoại chọn 3 đối tác (FR-20b) + chạy job ngày 01 sau đó | Chỉ sinh đúng 3 biên bản, báo kết quả từng đối tác; job ngày 01 bỏ qua 3 đối tác này | Hiếu bé |
| T21 | Lãi quá hạn sheet KH (D18) | Bản in KH: phần tách (1) gốc / (2) lãi nằm dưới **Phát sinh Nợ**; lãi làm **tăng** dư cuối KH còn nợ; bản in NCC giữ tách dưới Phát sinh Có | Chị Hà |
| T22 | Công thức đầy đủ (12.6) — unit test | Đúng cả 4 ca chiều dư × có/không lãi; đổi dấu `C₀ − D₀` cho NCC đúng | Hiếu bé |
| T23 | Số biên bản (D17) | 2 biên bản cùng tháng của 2 đối tác khác nhau cùng in `09.SL MVL-…./2026`, lưu bình thường; ID bản ghi khác nhau | Hiếu bé |

### 12.9 DoR / DoD của Work Package (đưa vào Task trên Project ERP_SCM)

**DoR — WP chỉ được kéo vào sprint khi:** SRS_10 đạt V1.0 (đã đạt 21/09 — còn 3 điểm ⚠️ không chặn: lãi quá hạn đối xứng sheet NCC (D12), số đại diện ký mỗi bên (D15), có cho lập biên bản theo kỳ lẻ không (R-c)); mẫu in được chị Hà duyệt trên giấy; staging đồng bộ production (bước 8 QL_01); danh sách email + HĐ nguyên tắc của ít nhất các đối tác kỳ tháng 9 đã nhập.

**DoD — WP được coi là xong khi:** toàn bộ FR mức M pass UAT T1–T23 trên staging (trừ T13 — ký số đã chuyển backlog theo D13); unit test tính số + bằng chữ + 4 ca dấu pass trong CI; fixtures/code merge theo git flow; tài liệu HDSD 1 trang cho kế toán; release lên production theo checklist bước 8 và gộp vào release MVP (bước 14, tối 29/9); kỳ gửi đầu 01/10 chạy có giám sát (Q5); QL_01 cập nhật phân công và mốc phản hồi đối soát ngày 06 tại QĐ 17 (Q5).

### 12.10 Kế hoạch phiên bản tài liệu

| Bước | Nội dung | Hạn đề xuất |
|---|---|---|
| V0.4 → V1.0 | Đã đồng bộ theo BA V6 (D16–D19) — baseline 21/09; từ đây mọi thay đổi đi qua CR. Thiết kế kỹ thuật chi tiết: TKKT_10 | 21/9 |
| V0.3 | Cập nhật theo kết luận họp | 20/9 |
| **V1.0 (baseline)** | Chốt trước sprint planning 21/9 — sau đó mọi thay đổi đi qua CR | 21/9 |

---

*Hết tài liệu SRS_10 V0.2 — 17/09/2026. Tài liệu lập theo cấu trúc 12 mục do PO yêu cầu, đồng thời bám cấu trúc đề xuất tính năng mục 6.3 của hồ sơ dự án (định vị, loại giải pháp, DocType, field, workflow, phân quyền, báo cáo, ảnh hưởng tồn kho/GL, rủi ro, portal, DoR/DoD).*

# TK_01 – Phân quyền ERP Miyano – Hỗ trợ, Chất lượng

> Trích nguyên văn từ `../TK_01_PhanQuyen_ERP_V2.1_AI.md` (V2.1, 23/10/2026). Không sửa nội dung; tài liệu gốc là nguồn sự thật. Khi cần thay đổi, sửa tài liệu gốc rồi tách lại.
> Ký hiệu, quy tắc G1–G11, hook H1–H11 và hướng dẫn triển khai: xem `TK_01_00_Nen_tang_chung.md`.

## Mục 3.1 – Danh mục role dùng trong ma trận (trích các dòng liên quan)

| Mã | Role | Loại | Desk | Ghi chú |
|---|---|---|---|---|
| QM | Quality Manager | chuẩn | 1 | |
| ST | Support Team | chuẩn | 1 | |

## Mục 6.10 – Hỗ trợ, Chất lượng

| DocType | Quyền |
|---|---|
| Issue | ST CRW (lọc theo Issue Type, mục 10); EMP CRW·o (gửi yêu cầu); CUS CRW·o |
| Issue Type, Issue Priority (G8), Service Level Agreement | SYS CRW |
| Support Settings (Single) | SYS RW |
| Non Conformance | STU CRW; QM CRWD; PU CRW (lỗi NCC); SU R |
| Quality Goal, Quality Procedure, Quality Review, Quality Action, Quality Meeting, Quality Feedback, Quality Feedback Template | QM CRW; STU R; PU R |

CUS dùng `·o` thay cho `[c]`, vì trường `customer` của Issue có thể trống và lọc bằng User Permission sẽ lộ Issue không gắn khách.

## Mục 10 – User Permission (trích các dòng liên quan)

| Đối tượng | Áp cho | Cấu hình |
|---|---|---|
| Issue Type | ST: KD → Khách hàng; IT-QT → IT nội bộ; NS-NV → Hành chính | Applicable For: Issue; `Issue.issue_type` bắt buộc (11.7) |

## Mục 11.2 – Custom Role trên Report (trích các dòng liên quan)

| Nhóm | Report | ref_doctype | Roles |
|---|---|---|---|
| Hỗ trợ | Issue Analytics, Issue Summary, First Response Time for Issues, Support Hour Distribution | Issue | ST, VW |
| Chất lượng | Quality Inspection Summary | Quality Inspection | QM, STM, VW |
| Chất lượng | Review | Quality Action | QM, VW |

## Mục 11.6 – Workspace (trích các dòng liên quan)

| Workspace (tên trên site) | Roles |
|---|---|
| Quality | QM, STU, STM, PU, PM, VW |
| Support | ST, EMP |

## Mục 11.7 – Custom Field và Property Setter (trích các dòng liên quan)

| DocType | Trường | Thiết lập | Lý do |
|---|---|---|---|
| Issue | `issue_type` | `reqd = 1` | User Permission Issue Type của ST không lọc được Issue có trường này trống |

## Phụ lục B – DocType không dùng (`g1_only`), ghi đúng tên (trích các dòng liên quan)

Các DocType dưới đây chỉ có dòng G1 (SYS `R B`, VW `R P B`). DocType của frappe giữ thêm dòng chuẩn của `All` / `Desk User` (G10).

| App / module | DocType |
|---|---|
| erpnext / Support | Warranty Claim |

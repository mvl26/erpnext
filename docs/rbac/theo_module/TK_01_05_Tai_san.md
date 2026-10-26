# TK_01 – Phân quyền ERP Miyano – Tài sản

> Trích nguyên văn từ `../TK_01_PhanQuyen_ERP_V2.1_AI.md` (V2.1, 23/10/2026). Không sửa nội dung; tài liệu gốc là nguồn sự thật. Khi cần thay đổi, sửa tài liệu gốc rồi tách lại.
> Ký hiệu, quy tắc G1–G11, hook H1–H11 và hướng dẫn triển khai: xem `TK_01_00_Nen_tang_chung.md`.

## Mục 3.1 – Danh mục role dùng trong ma trận (trích các dòng liên quan)

| Mã | Role | Loại | Desk | Ghi chú |
|---|---|---|---|---|
| AU | Accounts User | chuẩn | 1 | |
| AM | Accounts Manager | chuẩn | 1 | |
| AO | MVL Asset Operator | **mới** | 1 | IT-QT (tài sản CNTT), NS-TP (CCDC hành chính) |

## Mục 4 – Chân dung → Role Profile (trích các dòng liên quan)

| Chân dung | Role Profile | Roles |
|---|---|---|
| NS-TP | RP-NS-TP | BASE, TBP, HU, HM, AO |
| IT-QT | RP-IT-QT | BASE, SYS, WM, WSM, ST, AO, SNA |

## Mục 6.7 – Tài sản

| DocType | AU | AM | AO | Khác |
|---|---|---|---|---|
| Asset | CRW | CRWSXA PE O | R | STM R; HM R |
| Asset Category (G8) | R | CRW | | |
| Asset Movement | CRW | CRWSXA | CRW | |
| Asset Maintenance, Asset Maintenance Team | CRW | CRWD | CRW | |
| Asset Maintenance Log | CRW | CRWSXA | CRWS | |
| Asset Depreciation Schedule | R | CRWSXA | | |
| Asset Capitalization, Asset Value Adjustment | CRW | CRWSXA | | |
| Asset Activity (hệ thống sinh) | R | R | R | |
| Location (G8) | | CRW | CRW | |

Ghi chú:
- Asset Repair thuộc assetcore (module AssetCore, workflow IMM-09), ngoài phạm vi.
- Asset Shift Allocation, Asset Shift Factor: không dùng.
- Thanh lý tài sản bằng nút Scrap/Sell trên Asset (AM). Nhân viên báo hỏng tài sản bằng Issue (6.10).

## Mục 11.2 – Custom Role trên Report (trích các dòng liên quan)

| Nhóm | Report | ref_doctype | Roles |
|---|---|---|---|
| Tài sản | Fixed Asset Register, Asset Depreciation Ledger, Asset Depreciations and Balances | Asset | AU, AM, VW |
| Tài sản | Asset Activity | Asset Activity | AU, AM, AO, VW |
| Tài sản | Asset Maintenance | Asset Maintenance | AU, AM, AO |

## Mục 11.6 – Workspace (trích các dòng liên quan)

| Workspace (tên trên site) | Roles |
|---|---|
| Assets | AU, AM, AO, VW |

## Phụ lục B – DocType không dùng (`g1_only`), ghi đúng tên (trích các dòng liên quan)

Các DocType dưới đây chỉ có dòng G1 (SYS `R B`, VW `R P B`). DocType của frappe giữ thêm dòng chuẩn của `All` / `Desk User` (G10).

| App / module | DocType |
|---|---|
| erpnext / Assets | Asset Shift Allocation, Asset Shift Factor |

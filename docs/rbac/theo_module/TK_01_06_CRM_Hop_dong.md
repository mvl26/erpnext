# TK_01 – Phân quyền ERP Miyano – CRM, Hợp đồng

> Trích nguyên văn từ `../TK_01_PhanQuyen_ERP_V2.1_AI.md` (V2.1, 23/10/2026). Không sửa nội dung; tài liệu gốc là nguồn sự thật. Khi cần thay đổi, sửa tài liệu gốc rồi tách lại.
> Ký hiệu, quy tắc G1–G11, hook H1–H11 và hướng dẫn triển khai: xem `TK_01_00_Nen_tang_chung.md`.

## Mục 3.1 – Danh mục role dùng trong ma trận (trích các dòng liên quan)

| Mã | Role | Loại | Desk | Ghi chú |
|---|---|---|---|---|
| SU | Sales User | chuẩn | 1 | |
| SM | Sales Manager + Sales Master Manager | chuẩn | 1 | luôn gán cùng nhau |
| MK | MVL Marketing | **mới** | 1 | thay Sales User cho MKT-NV |
| NL | Newsletter Manager | chuẩn | 1 | |

## Mục 4 – Chân dung → Role Profile (trích các dòng liên quan)

| Chân dung | Role Profile | Roles |
|---|---|---|
| KD-NV | RP-KD-NV | BASE, SU, ST |
| KD-TP | RP-KD-TP | BASE, TBP, SU, SM, ST |
| MKT-NV | RP-MKT-NV | BASE, MK, NL |

## Mục 6.8 – CRM, Hợp đồng

| DocType | SU | SM | MK | PU / PM | Khác |
|---|---|---|---|---|---|
| Lead | CRW | CRW O I H | CRW | | |
| Opportunity, Prospect | CRW | CRW O | R | | |
| Lead Source, Sales Stage, Opportunity Type, Opportunity Lost Reason, Market Segment, Industry Type, Competitor (G8) | | CRWD | Lead Source: CRW | | |
| Campaign, Email Campaign | R | R | CRW | | NL CRW |
| Appointment | CRW | CRW | | | |
| Contact, Address | CRW | CRW O I | CRW | CRW / CRW O I | AU R; STU R; STM R; CUS, SUP RW·o |
| Contract | CRW (Customer) | CRWSXA (Customer) | | CRW / CRWSXA (Supplier) | HU CRW, HM CRWSXA (Employee) {D3}; AM R (mọi loại) |
| Contract Template | | CRW | | – / CRW | HM CRW |
| CRM Settings, Appointment Booking Settings (Single) | | RW | | | |

Ghi chú:
- Contract là DocType submittable (submit = hợp đồng đã ký). `Contract Fulfilment Checklist` là bảng con, theo quyền Contract.
- Tách Contract theo `party_type` (trường Select) không làm được bằng User Permission; dùng H1.
- Không ai có D trên Lead, Contact. Lead không dùng thì đổi status.

## Mục 11.2 – Custom Role trên Report (trích các dòng liên quan)

| Nhóm | Report | ref_doctype | Roles |
|---|---|---|---|
| CRM | Lead Details, Lead Owner Efficiency, Campaign Efficiency, Prospects Engaged But Not Converted | Lead | SU, SM, MK, VW |
| CRM | First Response Time for Opportunity, Lost Opportunity, Opportunity Summary by Sales Stage, Sales Pipeline Analytics, Territory-wise Sales | Opportunity | SU, SM, MK, VW |
| Danh bạ | Address And Contacts, Addresses And Contacts, Dia Chi Giao Hang Thieu Nguoi Nhan | Address | SU, SM, PU, PM |

## Mục 11.3 – Hook (phân hệ `access` {D17}) (trích các dòng liên quan)

| Mã | Gắn vào | Nội dung | Bắt buộc |
|---|---|---|---|
| H1 | Contract: `permission_query_conditions` + `has_permission` | Lọc theo `party_type`: SU/SM → Customer; PU/PM → Supplier; HU/HM → Employee; AM, VW, AP, SYS → tất cả | ✓ |

## Mục 11.6 – Workspace (trích các dòng liên quan)

| Workspace (tên trên site) | Roles |
|---|---|
| CRM | SU, SM, MK, VW |

## Mục 13 – Bộ kiểm thử bắt buộc (trích các dòng liên quan)

**A. Quyền và phạm vi dữ liệu**

| # | Kịch bản | Kết quả đúng |
|---|---|---|
| T07 | KD-NV và MK xóa Lead | Bị chặn |
| T08b | PDA, CUS, SUP tạo Contact hoặc Address mới; SU xóa Contact do mình tạo | Bị chặn (ngoại lệ G10) |
| T09 | SU mở Contract có `party_type = Employee` | Không thấy (H1) |

## Mục 14 – Điểm cần chốt (đã điền phương án mặc định) (trích các dòng liên quan)

| Mã | Nội dung | Mặc định |
|---|---|---|
| D3 | HĐLĐ, phụ lục | Contract với `party_type = Employee`; không tạo DocType riêng |

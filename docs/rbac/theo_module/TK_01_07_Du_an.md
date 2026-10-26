# TK_01 – Phân quyền ERP Miyano – Dự án

> Trích nguyên văn từ `../TK_01_PhanQuyen_ERP_V2.1_AI.md` (V2.1, 23/10/2026). Không sửa nội dung; tài liệu gốc là nguồn sự thật. Khi cần thay đổi, sửa tài liệu gốc rồi tách lại.
> Ký hiệu, quy tắc G1–G11, hook H1–H11 và hướng dẫn triển khai: xem `TK_01_00_Nen_tang_chung.md`.

## Mục 3.1 – Danh mục role dùng trong ma trận (trích các dòng liên quan)

| Mã | Role | Loại | Desk | Ghi chú |
|---|---|---|---|---|
| PJU | Projects User | chuẩn | 1 | mọi user nội bộ |
| PJM | Projects Manager | chuẩn | 1 | |

## Mục 4 – Chân dung → Role Profile (trích các dòng liên quan)

| Chân dung | Role Profile | Roles |
|---|---|---|
| DA-PM | RP-DA-PM | BASE, PJM |

## Mục 6.9 – Dự án

| DocType | PJU | PJM | Khác |
|---|---|---|---|
| Project | R | CRW O | AM R |
| Task | (không có DocPerm – chỉ truy cập qua `[g]`) | CRWD | |
| Timesheet | CRWS·o | CRWSXA W1 | DH R[d]; AM R R1 |
| Activity Type, Project Type, Task Type (G8); Project Template | | CRW | |
| Activity Cost | | CRW | AM R |
| Project Update | R | CRWSXA | |
| Projects Settings (Single) | | RW | |

PJU **không được có** dòng DocPerm nào trên Task; nếu có, Frappe cho đọc mọi Task và `[g]` mất tác dụng. KPI thưởng tính theo Task có trọng số (% Complete Method = Task Weight), do PJM quản trị.

## Mục 11.1 – Trường perm level (trích các dòng liên quan)

**Trường đã ở perm level 1 sẵn – erpnext, hrms** (phải cấp lại vì Custom DocPerm thay thế dòng level 1 chuẩn, kể cả `All` R1):

| DocType | Trường | Đọc | Ghi | Lý do |
|---|---|---|---|---|
| Timesheet; bảng Timesheet Detail (`costing_rate`, `costing_amount`, `billing_rate`, `billing_amount`, `billing_hours`) | `billing_details` và các trường tiền | AM | PJM | Giá vốn nhân công |

## Mục 11.2 – Custom Role trên Report (trích các dòng liên quan)

| Nhóm | Report | ref_doctype | Roles |
|---|---|---|---|
| Dự án | Project Summary, Project wise Stock Tracking | Project | PJM, AM, VW |
| Dự án | Delayed Tasks Summary, Today task | Task | PJM |
| Dự án | Daily Timesheet Summary, Employee Hours Utilization Based On Timesheet, Employee Billing Summary, Project Billing Summary, Project Profitability | Timesheet | PJM, AM, VW |

## Mục 11.3 – Hook (phân hệ `access` {D17}) (trích các dòng liên quan)

| Mã | Gắn vào | Nội dung | Bắt buộc |
|---|---|---|---|
| H8 | `permission_query_conditions` + `has_permission` cho DocType có `[e]`/`[d]` (6.9, mục 7) | Với user U, DocType X, ptype p: (a) U có role nào **khác EMP và DH** được p trên X mà không ghi phạm vi → không giới hạn; (b) nếu không, và U có DH được p → chỉ hồ sơ có `employee` thuộc một trong các nhóm: nhân viên thuộc Department mà U nằm trong bảng Department Approver (gồm Department con); nhân viên có `leave_approver`, `expense_approver` hoặc user của `reports_to` là U; chính U; (c) còn lại → chỉ hồ sơ có `employee` = Employee của U (với Employee: `name`). Không áp cho DocType chỉ có `·o` | ✓ |
| H9 | `after_insert` / `on_trash` của ToDo (Assign To) | Khi giao Task, Job Applicant, Interview, Training Program, Training Event: share bản ghi cho người được giao (Task share **Ghi**, còn lại share Đọc); gỡ share khi hủy giao. Assign To chuẩn của frappe chỉ share Đọc | ✓ |

## Mục 11.6 – Workspace (trích các dòng liên quan)

| Workspace (tên trên site) | Roles |
|---|---|
| Projects | PJU, PJM |

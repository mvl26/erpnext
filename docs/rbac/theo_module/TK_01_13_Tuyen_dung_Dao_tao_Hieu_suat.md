# TK_01 – Phân quyền ERP Miyano – Tuyển dụng, đào tạo, hiệu suất

> Trích nguyên văn từ `../TK_01_PhanQuyen_ERP_V2.1_AI.md` (V2.1, 23/10/2026). Không sửa nội dung; tài liệu gốc là nguồn sự thật. Khi cần thay đổi, sửa tài liệu gốc rồi tách lại.
> Ký hiệu, quy tắc G1–G11, hook H1–H11 và hướng dẫn triển khai: xem `TK_01_00_Nen_tang_chung.md`.

## Mục 3.1 – Danh mục role dùng trong ma trận (trích các dòng liên quan)

| Mã | Role | Loại | Desk | Ghi chú |
|---|---|---|---|---|
| HU | HR User | chuẩn | 1 | |
| HM | HR Manager | chuẩn | 1 | |
| DH | MVL Department Head | **mới** | 1 | **mang toàn bộ quyền duyệt của trưởng bộ phận**; luôn đi cùng LA, EA (gói TBP) |
| EMP | Employee | chuẩn | 1 | mọi user nội bộ |
| PJM | Projects Manager | chuẩn | 1 | |
| AP | MVL Approver | **mới** | 1 | bước duyệt Ban Giám đốc trong workflow; thay role COO |

## Mục 7 – HRMS (câu mở đầu)

Mọi ô `[e]`, `[d]` trong mục này được thực thi bằng hook H8.

## Mục 7.4 – Tuyển dụng, đào tạo, hiệu suất

| DocType | EMP | DH | HU | HM | Khác |
|---|---|---|---|---|---|
| Job Requisition | | CRW[d] | R | CRWD | AP RW (duyệt mở vị trí) |
| Staffing Plan | | R[d] | R | CRWSXA | AP R |
| Job Opening | | R | CRW | CRWD | |
| Job Applicant | | R[g] | CRW | CRWD | |
| Job Applicant Source (G8) | | | CRW | CRWD | |
| Interview | | R[g] | CRWS | CRWSXA | |
| Interview Round, Interview Type | | | CRW | CRWD | |
| Interview Feedback | CRWS·o | CRWS·o | R | CRWSXA | |
| Job Offer | | | CRW | CRW, SXA WF | AP (G2) |
| Appointment Letter | | | CRW | CRWD | |
| Job Offer Term Template, Offer Term, Appointment Letter Template | | | CRW | CRWD | |
| Training Program | R[g] | R | CRW | CRWD | |
| Training Event | R[g] | R | CRWS | CRWSXA | |
| Training Result | | R | CRWS | CRWSXA | |
| Training Feedback | CRWS·o | | R | CRWSXA | |
| Appraisal Cycle, Appraisal Template, KRA, Employee Feedback Criteria | | R | CRW | CRWD | |
| Appraisal | RW[e] (tự đánh giá) | RW[d] | CRW | CRWSXA | |
| Employee Performance Feedback | R[e] | CRWS[d] | R | CRWSXA | PJM CRWS·o |
| Goal | CRW[e] | CRW[d] | R | CRWD | |

Người phỏng vấn được giao Interview qua `[g]`; không dùng role Interviewer.

## Mục 9.3 – Đặc tả workflow (trích các dòng liên quan)

Quy ước:
- `(0)` `(1)` `(2)` là `doc_status`.
- Thứ tự state trong mỗi workflow đúng như liệt kê.
- Mọi transition từ "Chờ …" ngầm có điều kiện G11.
- Mọi workflow có transition **Mở lại**: Từ chối → Nháp, do role người lập thực hiện (nếu Từ chối có `doc_status 0`).
- Hạn mức `H1/H2/H3` viết tắt cho `frappe.db.get_value("MVL Approval Limits", None, "h1")`…

| Mã | DocType | States (theo thứ tự) | Lập | Sau submit |
|---|---|---|---|---|
| WF-HR | Salary Structure Assignment, Employee Promotion, Employee Transfer, Job Offer | Nháp(0), Chờ BGĐ(0), Đã duyệt(1), Từ chối(0), Đã hủy(2) | HM | HM |

**Transition:**

| Workflow | Từ | Hành động | Đến | Role | Điều kiện (ngoài G11) |
|---|---|---|---|---|---|
| WF-HR | Nháp | Gửi duyệt | Chờ BGĐ | HM | |
| | Chờ BGĐ | Duyệt / Từ chối | Đã duyệt / Từ chối | AP | |

## Mục 11.2 – Custom Role trên Report (trích các dòng liên quan)

| Nhóm | Report | ref_doctype | Roles |
|---|---|---|---|
| Nhân sự | Appraisal Overview | Appraisal | HU, HM, VW |
| Nhân sự | Recruitment Analytics | Staffing Plan | HU, HM, VW |

## Mục 11.3 – Hook (phân hệ `access` {D17}) (trích các dòng liên quan)

| Mã | Gắn vào | Nội dung | Bắt buộc |
|---|---|---|---|
| H8 | `permission_query_conditions` + `has_permission` cho DocType có `[e]`/`[d]` (6.9, mục 7) | Với user U, DocType X, ptype p: (a) U có role nào **khác EMP và DH** được p trên X mà không ghi phạm vi → không giới hạn; (b) nếu không, và U có DH được p → chỉ hồ sơ có `employee` thuộc một trong các nhóm: nhân viên thuộc Department mà U nằm trong bảng Department Approver (gồm Department con); nhân viên có `leave_approver`, `expense_approver` hoặc user của `reports_to` là U; chính U; (c) còn lại → chỉ hồ sơ có `employee` = Employee của U (với Employee: `name`). Không áp cho DocType chỉ có `·o` | ✓ |
| H9 | `after_insert` / `on_trash` của ToDo (Assign To) | Khi giao Task, Job Applicant, Interview, Training Program, Training Event: share bản ghi cho người được giao (Task share **Ghi**, còn lại share Đọc); gỡ share khi hủy giao. Assign To chuẩn của frappe chỉ share Đọc | ✓ |

## Mục 11.6 – Workspace (trích các dòng liên quan)

| Workspace (tên trên site) | Roles |
|---|---|
| HR, Employee Lifecycle, Recruitment | HU, HM, VW (Recruitment thêm DH) |
| Shift & Attendance, Leaves, Performance, Expense Claims, Tax & Benefits | EMP, HU, HM, DH, VW |

# TK_01 – Phân quyền ERP Miyano – Lương, thuế, phúc lợi

> Trích nguyên văn từ `../TK_01_PhanQuyen_ERP_V2.1_AI.md` (V2.1, 23/10/2026). Không sửa nội dung; tài liệu gốc là nguồn sự thật. Khi cần thay đổi, sửa tài liệu gốc rồi tách lại.
> Ký hiệu, quy tắc G1–G11, hook H1–H11 và hướng dẫn triển khai: xem `TK_01_00_Nen_tang_chung.md`.

## Mục 3.1 – Danh mục role dùng trong ma trận (trích các dòng liên quan)

| Mã | Role | Loại | Desk | Ghi chú |
|---|---|---|---|---|
| AU | Accounts User | chuẩn | 1 | |
| AM | Accounts Manager | chuẩn | 1 | |
| HM | HR Manager | chuẩn | 1 | |
| EMP | Employee | chuẩn | 1 | mọi user nội bộ |
| VW | MVL Viewer | **mới** | 1 | chỉ đọc |
| AP | MVL Approver | **mới** | 1 | bước duyệt Ban Giám đốc trong workflow; thay role COO |

## Mục 7 – HRMS (câu mở đầu)

Mọi ô `[e]`, `[d]` trong mục này được thực thi bằng hook H8.

## Mục 7.5 – Lương, thuế, phúc lợi

Trường tiền của các DocType lương ở perm level 1 theo 11.1.

| DocType | EMP | HM | AM | AU | Khác |
|---|---|---|---|---|---|
| Salary Component | | CRW W1 | R R1 | | |
| Salary Structure | | CRWSXA W1 | R R1 | | |
| Salary Structure Assignment | | CRW W1, SXA WF | R R1 | | AP (G2) |
| Bulk Salary Structure Assignment (Single) | | RW | | | |
| Additional Salary, Employee Incentive, Retention Bonus, Gratuity | | CRWSXA W1 | R R1 | | AP R R1 |
| Gratuity Rule | | CRW | R | | |
| Employee Other Income (fork) | CRW[e] | CRWSXA | R | | |
| Salary Withholding | | CRWSXA | R | | |
| Payroll Period (G8) | | CRW | R | | |
| Income Tax Slab | | CRWSXA | R | | |
| Payroll Entry | | CRW, SXA WF | R | RW (ghi chú 2) | AP (G2) |
| Salary Slip | R R1 [e] | CRWSXA W1 PE | R R1 | | AP R R1 |
| Employee Tax Exemption Category / Sub Category (G8) | | CRW | R | | |
| Employee Tax Exemption Declaration, Employee Tax Exemption Proof Submission | CRW[e] | CRWSXA | R | | HU RWS |
| Employee Benefit Application, Employee Benefit Claim | CRW[e] | CRWSXA | R | | |
| Payroll Settings, MVL Payroll Settings (Single) | | RW | R | | |

Ghi chú:
1. **HU (NS-NV) và DH không xem được lương**, kể cả perm level 1. Bảng lương do HM lập. Nhân viên nhận phiếu lương qua email có mật khẩu và xem phiếu của mình theo `[e]`.
2. **"Make Bank Entry" kiểm tra quyền `write` trên Payroll Entry** (`hrms/payroll/doctype/payroll_entry/payroll_entry.py:880`), nên AU cần `RW`. AU không sửa được nội dung Payroll Entry vì `allow_edit` của WF-PAY và H5. AU cần thêm C trên Journal Entry (đã có ở 6.6).
3. Bút toán dồn tích lương khi submit Salary Slip được tạo với `ignore_permissions` (`payroll_entry.py:633`), nên HM không cần quyền Journal Entry. Bút toán này vào thẳng trạng thái Đã ghi sổ của WF-JE (9.2, quy tắc 5; T24).
4. Tắt hạch toán lương theo từng nhân viên (11.5) để JE không lộ lương từng người.

## Mục 9.3 – Đặc tả workflow (trích các dòng liên quan)

Quy ước:
- `(0)` `(1)` `(2)` là `doc_status`.
- Thứ tự state trong mỗi workflow đúng như liệt kê.
- Mọi transition từ "Chờ …" ngầm có điều kiện G11.
- Mọi workflow có transition **Mở lại**: Từ chối → Nháp, do role người lập thực hiện (nếu Từ chối có `doc_status 0`).
- Hạn mức `H1/H2/H3` viết tắt cho `frappe.db.get_value("MVL Approval Limits", None, "h1")`…

| Mã | DocType | States (theo thứ tự) | Lập | Sau submit |
|---|---|---|---|---|
| WF-PAY | Payroll Entry | Nháp(0), Chờ BGĐ(0), Đã duyệt(1), Từ chối(0), Đã hủy(2) | HM | HM |
| WF-HR | Salary Structure Assignment, Employee Promotion, Employee Transfer, Job Offer | Nháp(0), Chờ BGĐ(0), Đã duyệt(1), Từ chối(0), Đã hủy(2) | HM | HM |

**Transition:**

| Workflow | Từ | Hành động | Đến | Role | Điều kiện (ngoài G11) |
|---|---|---|---|---|---|
| WF-PAY | Nháp | Gửi duyệt | Chờ BGĐ | HM | |
| | Chờ BGĐ | Duyệt / Từ chối | Đã duyệt / Từ chối | AP | |
| WF-HR | Nháp | Gửi duyệt | Chờ BGĐ | HM | |
| | Chờ BGĐ | Duyệt / Từ chối | Đã duyệt / Từ chối | AP | |

Ghi chú:
4. **WF-PAY:** sau Đã duyệt, HM bấm Submit Salary Slip; AU bấm Make Bank Entry.

## Mục 11.1 – Trường perm level (trích các dòng liên quan)

**Trường Miyano đặt thêm** (Property Setter):

| DocType | Trường | Level | Đọc | Ghi |
|---|---|---|---|---|
| Employee | `ctc`, `salary_currency`, `salary_mode`, `bank_name`, `bank_ac_no`, `iban` | 1 | HM, AM | HM |
| Salary Component, Salary Structure, Salary Structure Assignment, Salary Slip, Additional Salary, Employee Incentive, Retention Bonus, Gratuity, Full and Final Statement, Employee Promotion (`revised_ctc`) | mọi trường tiền và bảng earnings/deductions | 1 | HM, AM, VW, AP; EMP (Salary Slip của mình) | HM |

## Mục 11.2 – Custom Role trên Report (trích các dòng liên quan)

| Nhóm | Report | ref_doctype | Roles |
|---|---|---|---|
| Lương, thuế TNCN | Salary Register, MVL Salary Register, Income Tax Deductions, Income Tax Computation, Salary Payments Based On Payment Mode, Salary Payments via ECS, Provident Fund Deductions, Professional Tax Deductions | Salary Slip | HM, AM, VW |
| Lương, thuế TNCN | Bank Remittance | Payroll Entry | HM, AM, VW |
| Lương, thuế TNCN | Quyet Toan TNCN | GL Entry | AM, VW |

## Mục 11.5 – Settings (trích các dòng liên quan)

| Settings | Trường | Giá trị | Hiện tại (23/10) | Ai ghi |
|---|---|---|---|---|
| Payroll Settings | Process Payroll Accounting Entry based on Employee | 0 | 0 | HM |
| Payroll Settings | Encrypt Salary Slips in Emails | 1 – trước khi bật, kiểm tra Password Policy của nhân viên | 0 | HM |

## Mục 11.6 – Workspace (trích các dòng liên quan)

| Workspace (tên trên site) | Roles |
|---|---|
| Shift & Attendance, Leaves, Performance, Expense Claims, Tax & Benefits | EMP, HU, HM, DH, VW |
| Payroll, Salary Payout | HM, AM, VW |

## Mục 13 – Bộ kiểm thử bắt buộc (trích các dòng liên quan)

**A. Quyền và phạm vi dữ liệu**

| # | Kịch bản | Kết quả đúng |
|---|---|---|
| T01 | DH mở Salary Slip của nhân viên trong bộ phận | Không thấy, hoặc không thấy trường tiền |
| T02 | HU (NS-NV) mở Salary Structure Assignment, trường lương trên Employee | Bị chặn hoặc ẩn |
| T15 | AU mở chi tiết Salary Slip; AU bấm Make Bank Entry | Chặn xem chi tiết; Make Bank Entry chạy được |

**B. Workflow và luồng duyệt**

| # | Kịch bản | Kết quả đúng |
|---|---|---|
| T24 | JE khấu hao, đánh giá tỷ giá, bút toán lương do hệ thống sinh khi WF-JE bật | Ghi sổ được, state Đã ghi sổ |
| T26 | Sửa nội dung phiếu đang Chờ … qua API (kể cả người lập); AU sửa Payroll Entry | Bị chặn (H5, `allow_edit` = LK) |

**D. Hệ thống, sync, code**

| # | Kịch bản | Kết quả đúng |
|---|---|---|
| T56 | IT-QT mở MVL Salary Register; STU mở Item Prices, Warehouse Wise Stock Balance, Stock Analytics; DH mở Unpaid Expense Claim | Đều bị chặn (11.2) |

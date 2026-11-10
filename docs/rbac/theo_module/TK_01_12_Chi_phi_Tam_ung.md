# TK_01 – Phân quyền ERP Miyano – Chi phí, tạm ứng

> Trích nguyên văn từ `../TK_01_PhanQuyen_ERP_V2.1_AI.md` (V2.1, 23/10/2026). Không sửa nội dung; tài liệu gốc là nguồn sự thật. Khi cần thay đổi, sửa tài liệu gốc rồi tách lại.
> Ký hiệu, quy tắc G1–G11, hook H1–H11 và hướng dẫn triển khai: xem `TK_01_00_Nen_tang_chung.md`.

## Mục 3.1 – Danh mục role dùng trong ma trận (trích các dòng liên quan)

| Mã | Role | Loại | Desk | Ghi chú |
|---|---|---|---|---|
| AU | Accounts User | chuẩn | 1 | |
| AM | Accounts Manager | chuẩn | 1 | |
| DH | MVL Department Head | **mới** | 1 | **mang toàn bộ quyền duyệt của trưởng bộ phận**; luôn đi cùng LA, EA (gói TBP) |
| LA, EA | Leave Approver, Expense Approver | chuẩn hrms | 1 | **Role đánh dấu, không có dòng Custom DocPerm nào.** Giữ trong gói TBP vì hrms tự gán cho người duyệt (3.2); nếu thiếu trong profile, frappe gỡ khi lưu User |
| EMP | Employee | chuẩn | 1 | mọi user nội bộ |
| AP | MVL Approver | **mới** | 1 | bước duyệt Ban Giám đốc trong workflow; thay role COO |

## Mục 3.2 – Ràng buộc từ mã nguồn (trích các dòng liên quan)

**Code tự gán role.** Role Profile ghi đè toàn bộ role mỗi lần lưu User (mục 4), nên các role dưới đây phải nằm sẵn trong profile:

| Nơi | Hành vi | Hệ quả |
|---|---|---|
| `hrms/overrides/employee_master.py:85` | Gán Leave Approver / Expense Approver cho người được ghi ở `leave_approver` / `expense_approver` | Người duyệt phải có profile chứa TBP; sync kiểm tra |

## Mục 7 – HRMS (câu mở đầu)

Mọi ô `[e]`, `[d]` trong mục này được thực thi bằng hook H8.

## Mục 7.3 – Chi phí, tạm ứng

| DocType | EMP | DH | AU | AM | Khác |
|---|---|---|---|---|---|
| Expense Claim | CRW R1 [e] | RW R1 [d] WF | R R1 | RWSXA W1 WF | HM R R1; AP W1 (G2) |
| Employee Advance | CRW[e] | RW[d] WF | R | RWSXA WF | AP (G2) |
| Expense Invoice (fork – hóa đơn đính kèm Expense Claim) | CRW·o | | RW | CRW | HM R |
| Expense Claim Type (G8) | | | R | CRW | HM CRW |

Sau khi chứng từ được duyệt, AU chi tiền bằng Payment Entry (6.6). "Đề nghị thanh toán" của nhân viên được thực hiện bằng Expense Claim và Employee Advance {D8}. Expense Invoice không có trường Employee nên EMP dùng `·o`.

## Mục 9.3 – Đặc tả workflow (trích các dòng liên quan)

Quy ước:
- `(0)` `(1)` `(2)` là `doc_status`.
- Thứ tự state trong mỗi workflow đúng như liệt kê.
- Mọi transition từ "Chờ …" ngầm có điều kiện G11.
- Mọi workflow có transition **Mở lại**: Từ chối → Nháp, do role người lập thực hiện (nếu Từ chối có `doc_status 0`).
- Hạn mức `H1/H2/H3` viết tắt cho `frappe.db.get_value("MVL Approval Limits", None, "h1")`…

| Mã | DocType | States (theo thứ tự) | Lập | Sau submit |
|---|---|---|---|---|
| WF-EC | Expense Claim, Employee Advance | Nháp(0), Chờ TBP(0), Chờ KTT(0), Chờ BGĐ(0), Đã duyệt(1), Từ chối(0), Đã hủy(2) | EMP | AM |

**Transition:**

| Workflow | Từ | Hành động | Đến | Role | Điều kiện (ngoài G11) |
|---|---|---|---|---|---|
| WF-EC | Nháp | Gửi duyệt | Chờ TBP | EMP | |
| | Chờ TBP | Duyệt / Từ chối | Chờ KTT / Từ chối | DH | Expense Claim: `doc.expense_approver == frappe.session.user`; Employee Advance: `frappe.db.get_value("Employee", doc.employee, "expense_approver") == frappe.session.user` |
| | Chờ KTT | Duyệt | Đã duyệt | AM | Expense Claim: `doc.grand_total <= H3`; Employee Advance: `doc.advance_amount <= H3` |
| | Chờ KTT | Duyệt | Chờ BGĐ | AM | vượt H3 {D2} |
| | Chờ BGĐ | Duyệt | Đã duyệt | AP | |
| | Chờ KTT / Chờ BGĐ | Từ chối | Từ chối | AM / AP | |

Ghi chú:
1. **Expense Claim:** state Đã duyệt có Update Field `approval_status = Approved`; Employee Advance không có trường này. `status` của cả hai do hrms tự tính (Unpaid → Paid…), không đặt bằng workflow.

## Mục 11.1 – Trường perm level (trích các dòng liên quan)

**Trường đã ở perm level 1 sẵn – erpnext, hrms** (phải cấp lại vì Custom DocPerm thay thế dòng level 1 chuẩn, kể cả `All` R1):

| DocType | Trường | Đọc | Ghi | Lý do |
|---|---|---|---|---|
| Expense Claim | `approval_status` | EMP, DH, AU, HM, VW | AM, AP | WF-EC đặt `approval_status = Approved` ở bước cuối |

## Mục 11.2 – Custom Role trên Report (trích các dòng liên quan)

| Nhóm | Report | ref_doctype | Roles |
|---|---|---|---|
| Chi phí | Unpaid Expense Claim | Expense Claim | AU, AM, HM, VW (bỏ Expense Approver hiện có) |
| Chi phí | Employee Advance Summary | Employee Advance | AU, AM, VW |

Ghi chú:
- DH không được cấp report nhân sự hay chi phí: Script Report không qua H8 nên sẽ hiện toàn công ty. DH xem Attendance, Leave Application, Expense Claim của bộ phận bằng list/Report view, nơi H8 có hiệu lực.

## Mục 11.6 – Workspace (trích các dòng liên quan)

| Workspace (tên trên site) | Roles |
|---|---|
| Shift & Attendance, Leaves, Performance, Expense Claims, Tax & Benefits | EMP, HU, HM, DH, VW |

## Mục 13 – Bộ kiểm thử bắt buộc (trích các dòng liên quan)

**A. Quyền và phạm vi dữ liệu**

| # | Kịch bản | Kết quả đúng |
|---|---|---|
| T10 | KT-NV (AU + EMP) tạo Expense Claim, Leave Application cho nhân viên khác | Bị chặn (H8) |
| T11 | NS-NV (HU + EMP) đọc Expense Claim của nhân viên khác | Bị chặn (H8) |
| T13 | User chỉ có RP-NV mở form Sales Order, Expense Claim | Không lỗi "No permission" trên Company, Warehouse, Currency, Cost Center (G8) |

**B. Workflow và luồng duyệt**

| # | Kịch bản | Kết quả đúng |
|---|---|---|
| T20 | DH gọi API submit Expense Claim đang Chờ TBP | Bị chặn (H11) |
| T28 | AM duyệt bước cuối Expense Claim | `approval_status = Approved` được giữ |
| T36 | Submit Expense Claim qua workflow, sau đó thanh toán | `status` do hrms tính (Unpaid → Paid), không bị workflow ghi đè |

**D. Hệ thống, sync, code**

| # | Kịch bản | Kết quả đúng |
|---|---|---|
| T56 | IT-QT mở MVL Salary Register; STU mở Item Prices, Warehouse Wise Stock Balance, Stock Analytics; DH mở Unpaid Expense Claim | Đều bị chặn (11.2) |

## Mục 14 – Điểm cần chốt (đã điền phương án mặc định) (trích các dòng liên quan)

| Mã | Nội dung | Mặc định |
|---|---|---|
| D2 | Luồng duyệt Expense Claim / Employee Advance | TBP → KT-KTT (→ BGĐ nếu > H3). NS-TP không duyệt chi phí |
| D8 | "Các đề nghị thanh toán" | Expense Claim / Employee Advance; không dùng Payment Request |

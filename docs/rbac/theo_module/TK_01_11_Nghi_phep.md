# TK_01 – Phân quyền ERP Miyano – Nghỉ phép

> Trích nguyên văn từ `../TK_01_PhanQuyen_ERP_V2.1_AI.md` (V2.1, 23/10/2026). Không sửa nội dung; tài liệu gốc là nguồn sự thật. Khi cần thay đổi, sửa tài liệu gốc rồi tách lại.
> Ký hiệu, quy tắc G1–G11, hook H1–H11 và hướng dẫn triển khai: xem `TK_01_00_Nen_tang_chung.md`.

## Mục 3.1 – Danh mục role dùng trong ma trận (trích các dòng liên quan)

| Mã | Role | Loại | Desk | Ghi chú |
|---|---|---|---|---|
| HU | HR User | chuẩn | 1 | |
| HM | HR Manager | chuẩn | 1 | |
| DH | MVL Department Head | **mới** | 1 | **mang toàn bộ quyền duyệt của trưởng bộ phận**; luôn đi cùng LA, EA (gói TBP) |
| LA, EA | Leave Approver, Expense Approver | chuẩn hrms | 1 | **Role đánh dấu, không có dòng Custom DocPerm nào.** Giữ trong gói TBP vì hrms tự gán cho người duyệt (3.2); nếu thiếu trong profile, frappe gỡ khi lưu User |
| EMP | Employee | chuẩn | 1 | mọi user nội bộ |

## Mục 3.2 – Ràng buộc từ mã nguồn (trích các dòng liên quan)

**Code tự gán role.** Role Profile ghi đè toàn bộ role mỗi lần lưu User (mục 4), nên các role dưới đây phải nằm sẵn trong profile:

| Nơi | Hành vi | Hệ quả |
|---|---|---|
| `hrms/overrides/employee_master.py:85` | Gán Leave Approver / Expense Approver cho người được ghi ở `leave_approver` / `expense_approver` | Người duyệt phải có profile chứa TBP; sync kiểm tra |

## Mục 7 – HRMS (câu mở đầu)

Mọi ô `[e]`, `[d]` trong mục này được thực thi bằng hook H8.

## Mục 7.2 – Chấm công, ca, nghỉ phép (trích các dòng liên quan)

| DocType | EMP | DH | HU | HM |
|---|---|---|---|---|
| Holiday List, Leave Type, Leave Period, Leave Block List (G8) | | | CRW | CRWD |
| Leave Policy | R | | CRW | CRWSXA |
| Leave Policy Assignment | R[e] | | CRWS | CRWSXA |
| Leave Allocation | R[e] | R[d] | CRW | CRWSXA |
| Leave Application | CRW R1 [e] | RWS W1 [d] WF | CRW R1 (nhập hộ, D6) | RWSXA W1 P WF |
| Compensatory Leave Request | CRW[e] | RW[d] WF | R | RWSXA WF |
| Leave Encashment | R[e] | | CRW | CRWSXA |
| Leave Ledger Entry (hệ thống sinh) | R[e] | R[d] | R | R |
| Shift Assignment Tool, Employee Attendance Tool, Upload Attendance, Leave Control Panel (Single – công cụ tạo hàng loạt) | | | RW | RW |

- **EMP không có S** trên Leave Application, Attendance Request, Compensatory Leave Request, Shift Request:
  - HRMS chỉ cho submit Leave Application và Shift Request khi đơn đã Approved/Rejected;
  - submit Attendance Request tạo chấm công ngay;
  - submit Compensatory Leave Request tự cấp thêm ngày phép.

  Cho EMP quyền S nghĩa là cho nhân viên tự duyệt.
- **DH có S trên Leave Application và Shift Request** chỉ để thực hiện transition Từ chối (submit với `status = Rejected`, WF-LA). HRMS còn tự share quyền Submit cho người duyệt ghi trên đơn (`hrms/hr/utils.py:694`), nên workflow và H11 là chốt chặn thực sự.

## Mục 9.3 – Đặc tả workflow (trích các dòng liên quan)

Quy ước:
- `(0)` `(1)` `(2)` là `doc_status`.
- Thứ tự state trong mỗi workflow đúng như liệt kê.
- Mọi transition từ "Chờ …" ngầm có điều kiện G11.
- Mọi workflow có transition **Mở lại**: Từ chối → Nháp, do role người lập thực hiện (nếu Từ chối có `doc_status 0`).
- Hạn mức `H1/H2/H3` viết tắt cho `frappe.db.get_value("MVL Approval Limits", None, "h1")`…

| Mã | DocType | States (theo thứ tự) | Lập | Sau submit |
|---|---|---|---|---|
| WF-LA | Leave Application, Shift Request | Nháp(0), Chờ TBP(0), Chờ HCNS(0), Đã duyệt(1), Từ chối(1), Đã hủy(2) | EMP, HU | HM |
| WF-AR | Attendance Request, Compensatory Leave Request | Nháp(0), Chờ TBP(0), Chờ HCNS(0), Đã duyệt(1), Từ chối(0), Đã hủy(2) | EMP | HM |

**Transition:**

| Workflow | Từ | Hành động | Đến | Role | Điều kiện (ngoài G11) |
|---|---|---|---|---|---|
| WF-LA | Nháp | Gửi duyệt | Chờ TBP | EMP; HU | |
| | Chờ TBP | Duyệt | Chờ HCNS | DH | `doc.leave_approver == frappe.session.user` (Shift Request: `doc.approver`) |
| | Chờ TBP | Từ chối | Từ chối – Update `status = Rejected` | DH | như trên |
| | Chờ HCNS | Duyệt | Đã duyệt – Update `status = Approved` | HM | |
| | Chờ HCNS | Từ chối | Từ chối – Update `status = Rejected` | HM | |
| WF-AR | Nháp | Gửi duyệt | Chờ TBP | EMP | |
| | Chờ TBP | Duyệt / Từ chối | Chờ HCNS / Từ chối | DH | Attendance Request: `doc.custom_approver == frappe.session.user` (khớp `guard_submit` và Assign To của fork); Compensatory Leave Request: `frappe.db.get_value("Employee", doc.employee, "leave_approver") == frappe.session.user` |
| | Chờ HCNS | Duyệt / Từ chối | Đã duyệt / Từ chối | HM | |

Ghi chú:
2. **Leave Application, Shift Request:** Từ chối là `doc_status 1` (hrms chỉ cho submit đơn ở trạng thái Approved/Rejected), nên DH và HM cần S, thêm W1 trên Leave Application. Ở các DocType HR còn lại, Từ chối là `doc_status 0`.

## Mục 11.1 – Trường perm level (trích các dòng liên quan)

**Trường đã ở perm level 1 sẵn – erpnext, hrms** (phải cấp lại vì Custom DocPerm thay thế dòng level 1 chuẩn, kể cả `All` R1):

| DocType | Trường | Đọc | Ghi | Lý do |
|---|---|---|---|---|
| Leave Application | `status` | EMP, HU, VW | DH, HM | WF-LA đặt `status`. Thiếu W1 thì frappe trả về Open và submit báo lỗi |

## Mục 11.2 – Custom Role trên Report (trích các dòng liên quan)

| Nhóm | Report | ref_doctype | Roles |
|---|---|---|---|
| Nhân sự | Employee Leave Balance, Employee Leave Balance Summary, Employee Analytics, Employee Information, Employee Birthday | Employee | HU, HM, VW |
| Nhân sự | Leave Ledger | Leave Ledger Entry | HU, HM, VW |

Ghi chú:
- DH không được cấp report nhân sự hay chi phí: Script Report không qua H8 nên sẽ hiện toàn công ty. DH xem Attendance, Leave Application, Expense Claim của bộ phận bằng list/Report view, nơi H8 có hiệu lực.

## Mục 11.5 – Settings (trích các dòng liên quan)

| Settings | Trường | Giá trị | Hiện tại (23/10) | Ai ghi |
|---|---|---|---|---|
| HR Settings | Prevent Self Leave Approval, Prevent Self Expense Approval | 1 (dự phòng; không hiệu lực khi có workflow – 9.1) | 0 | HM |
| HR Settings | Leave Approver Mandatory, Expense Approver Mandatory | 1 | 1 | HM |
| HR Settings | Restrict Backdated Leave Application; Role Allowed to Create Backdated Leave Application | 1; HM | 0; trống | HM |
| HR Settings | Leave/Expense Approval Notification Template | trống (9.1) | trống | HM |

## Mục 11.6 – Workspace (trích các dòng liên quan)

| Workspace (tên trên site) | Roles |
|---|---|
| Shift & Attendance, Leaves, Performance, Expense Claims, Tax & Benefits | EMP, HU, HM, DH, VW |

## Mục 11.7 – Custom Field và Property Setter (trích các dòng liên quan)

| DocType | Trường | Thiết lập | Lý do |
|---|---|---|---|
| Employee | `leave_approver`, `expense_approver`, `reports_to` | `reqd = 1` | Điều kiện của WF-LA, WF-AR, WF-EC; `reports_to` là nguồn của `custom_approver` trên Attendance Request |

## Mục 13 – Bộ kiểm thử bắt buộc (trích các dòng liên quan)

**A. Quyền và phạm vi dữ liệu**

| # | Kịch bản | Kết quả đúng |
|---|---|---|
| T10 | KT-NV (AU + EMP) tạo Expense Claim, Leave Application cho nhân viên khác | Bị chặn (H8) |

**B. Workflow và luồng duyệt**

| # | Kịch bản | Kết quả đúng |
|---|---|---|
| T16 | NV submit Leave Application, Attendance Request, Compensatory Leave Request của chính mình | Bị chặn |
| T25 | DH duyệt đơn nghỉ của chính mình; HM duyệt đơn nghỉ của chính mình | Bị chặn (G11) |
| T27 | DH duyệt rồi HM duyệt Leave Application | `status = Approved` được giữ; submit thành công |
| T35 | Sau bước 4, mở 25 đơn nghỉ đã submit trước đó | `workflow_state` khớp `status` |

**D. Hệ thống, sync, code**

| # | Kịch bản | Kết quả đúng |
|---|---|---|
| T49 | NV mở form Leave Application, chọn người duyệt; HU giao Task cho đồng nghiệp | Danh sách user hiện ra (dòng `Desk User` select trên User được giữ) |

## Mục 14 – Điểm cần chốt (đã điền phương án mặc định) (trích các dòng liên quan)

| Mã | Nội dung | Mặc định |
|---|---|---|
| D6 | KHO-PDA | Giao diện PDA hiện là các desk Page (`erpnext/warehouse_operations/page/`), không phải portal, nên PDA phải là **System User** (desk = 1) bị khóa bằng Module Profile "MVL PDA" và Custom Role của Page (11.8). Nghỉ phép do NS-NV nhập hộ (HU có C trên Leave Application); cần tự phục vụ thì chuyển sang RP-KHO-TK. Phương án khác: làm giao diện portal cho PDA rồi mới chuyển PDA thành Website User |

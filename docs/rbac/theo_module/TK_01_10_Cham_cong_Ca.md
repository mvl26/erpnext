# TK_01 – Phân quyền ERP Miyano – Chấm công, ca làm việc

> Trích nguyên văn từ `../TK_01_PhanQuyen_ERP_V2.1_AI.md` (V2.1, 23/10/2026). Không sửa nội dung; tài liệu gốc là nguồn sự thật. Khi cần thay đổi, sửa tài liệu gốc rồi tách lại.
> Ký hiệu, quy tắc G1–G11, hook H1–H11 và hướng dẫn triển khai: xem `TK_01_00_Nen_tang_chung.md`.

## Mục 3.1 – Danh mục role dùng trong ma trận (trích các dòng liên quan)

| Mã | Role | Loại | Desk | Ghi chú |
|---|---|---|---|---|
| HU | HR User | chuẩn | 1 | |
| HM | HR Manager | chuẩn | 1 | |
| DH | MVL Department Head | **mới** | 1 | **mang toàn bộ quyền duyệt của trưởng bộ phận**; luôn đi cùng LA, EA (gói TBP) |
| EMP | Employee | chuẩn | 1 | mọi user nội bộ |

## Mục 3.2 – Ràng buộc từ mã nguồn (trích các dòng liên quan)

**Role được code kiểm tra theo tên** (đổi tên hoặc bỏ khỏi profile thì chức năng ngừng chạy):

| Role | Nơi kiểm tra | Chức năng |
|---|---|---|
| HR Manager, HR User, System Manager | `hrms/hr/doctype/attendance_request/attendance_request_miyano.py:41` (`APPROVER_BYPASS_ROLES`, dùng trong `guard_submit`, nối ở `hrms/hooks.py:109-116`) | submit Attendance Request thay cho người duyệt `custom_approver` – sửa theo C5 |

**Code cho System Manager vượt quyền nghiệp vụ:**

| Nơi | Hành vi | Xử lý |
|---|---|---|
| `hrms/hr/attendance_exempt.py:381, 391` | `only_for(HR Manager, System Manager)` – miễn chấm công | Sửa C5 |
| `hrms/hr/doctype/attendance_request/attendance_request_miyano.py:41` | System Manager (và HR User) submit được mọi Attendance Request | Sửa C5 |

**Code tự gán role.** Role Profile ghi đè toàn bộ role mỗi lần lưu User (mục 4), nên các role dưới đây phải nằm sẵn trong profile:

| Nơi | Hành vi | Hệ quả |
|---|---|---|
| `hrms/hr/doctype/attendance_request/attendance_request_miyano.py:45, 57` | Điền `custom_approver` = user của `reports_to`, rồi Assign To cho người này | Người duyệt Attendance Request là quản lý trực tiếp, không phải `leave_approver` (WF-AR). User của `reports_to` phải có TBP |

## Mục 7 – HRMS (câu mở đầu)

Mọi ô `[e]`, `[d]` trong mục này được thực thi bằng hook H8.

## Mục 7.1 – Hồ sơ, tổ chức, vòng đời (trích các dòng liên quan)

| DocType | EMP | DH | HU | HM | Khác |
|---|---|---|---|---|---|
| Employee Checkin | CR R1 [e] | R R1 [d] | CRW W1 | CRW W1 | SYS R |

Ghi chú:
- Employee Checkin là dữ liệu chấm công gốc nên HM cũng không có D. Trường `time` ở level 1: nhân viên không sửa được giờ chấm.

## Mục 7.2 – Chấm công, ca, nghỉ phép (trích các dòng liên quan)

| DocType | EMP | DH | HU | HM |
|---|---|---|---|---|
| Attendance | R[e] | R[d] | CRWS | CRWSXA |
| Attendance Code (fork; G8) | | | CRW | CRWD |
| Attendance Correction Log (fork – nhật ký sửa công) | | | CR | CR |
| Monthly Attendance Sheet (fork – bảng công tháng) | | R[d] | CRW | CRWSXA |
| Attendance Request | CRW[e] | RW[d] WF | R | RWSXA WF |
| Shift Type, Shift Location (G8) | | | CRW | CRWD |
| Shift Assignment | R[e] | R[d] | CRWS | CRWSXA |
| Shift Schedule | R | | CRW | CRWSXA |
| Shift Schedule Assignment | R[e] | R[d] | CRW | CRWD |
| Shift Request | CRW[e] | RWS[d] WF | R | RWSXA WF |
| Holiday List, Leave Type, Leave Period, Leave Block List (G8) | | | CRW | CRWD |
| Shift Assignment Tool, Employee Attendance Tool, Upload Attendance, Leave Control Panel (Single – công cụ tạo hàng loạt) | | | RW | RW |
| Work Calendar Settings (Single, fork) | | | R | RW |

- **EMP không có S** trên Leave Application, Attendance Request, Compensatory Leave Request, Shift Request:
  - HRMS chỉ cho submit Leave Application và Shift Request khi đơn đã Approved/Rejected;
  - submit Attendance Request tạo chấm công ngay;
  - submit Compensatory Leave Request tự cấp thêm ngày phép.

  Cho EMP quyền S nghĩa là cho nhân viên tự duyệt.
- **DH có S trên Leave Application và Shift Request** chỉ để thực hiện transition Từ chối (submit với `status = Rejected`, WF-LA). HRMS còn tự share quyền Submit cho người duyệt ghi trên đơn (`hrms/hr/utils.py:694`), nên workflow và H11 là chốt chặn thực sự.
- Bảng công tháng do HU lập, HM chốt (submit). DH chỉ xem; muốn sửa thì đề nghị qua Attendance Request.

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
3. **Attendance Request:** `guard_submit` của fork chỉ cho `custom_approver` hoặc role bypass submit. Bước cuối của WF-AR do HM thực hiện, nên HM phải nằm trong `APPROVER_BYPASS_ROLES` sau khi sửa C5 (chỉ còn HR Manager).

## Mục 11.1 – Trường perm level (trích các dòng liên quan)

**Trường đã ở perm level 1 sẵn – erpnext, hrms** (phải cấp lại vì Custom DocPerm thay thế dòng level 1 chuẩn, kể cả `All` R1):

| DocType | Trường | Đọc | Ghi | Lý do |
|---|---|---|---|---|
| Employee Checkin | `time` | EMP, DH | HU, HM | Nhân viên không sửa giờ chấm |

## Mục 11.2 – Custom Role trên Report (trích các dòng liên quan)

| Nhóm | Report | ref_doctype | Roles |
|---|---|---|---|
| Nhân sự | Monthly Attendance Sheet, Monthly Attendance Report, Shift Attendance, Employee Working Hours, Employees working on a holiday | Attendance | HU, HM, VW |

Ghi chú:
- DH không được cấp report nhân sự hay chi phí: Script Report không qua H8 nên sẽ hiện toàn công ty. DH xem Attendance, Leave Application, Expense Claim của bộ phận bằng list/Report view, nơi H8 có hiệu lực.

## Mục 11.4 – Thay đổi code (trích các dòng liên quan)

**Trong fork mvl26/hrms (repo riêng, cần người phụ trách repo đó):**

| Mã | File | Thay đổi |
|---|---|---|
| C5 | `hrms/hr/attendance_exempt.py:381, 391`; `hrms/hr/doctype/attendance_request/attendance_request_miyano.py:41` | Bỏ System Manager khỏi `only_for`. `APPROVER_BYPASS_ROLES` chỉ còn HR Manager (bỏ HR User, System Manager), vì bước cuối của WF-AR do HM thực hiện |

## Mục 11.6 – Workspace (trích các dòng liên quan)

| Workspace (tên trên site) | Roles |
|---|---|
| Shift & Attendance, Leaves, Performance, Expense Claims, Tax & Benefits | EMP, HU, HM, DH, VW |

## Mục 11.8 – Page (trích các dòng liên quan)

Roles của Page ghi bằng Custom Role (sync). Page không có trong bảng thì giữ Roles chuẩn của frappe.

| Page | Roles mới | Roles hiện có trên site |
|---|---|---|
| attendance-review | HU, HM | HR User, HR Manager |

## Mục 13 – Bộ kiểm thử bắt buộc (trích các dòng liên quan)

**A. Quyền và phạm vi dữ liệu**

| # | Kịch bản | Kết quả đúng |
|---|---|---|
| T14 | Nhân viên tạo Employee Checkin rồi sửa `time` | Không sửa được |

**B. Workflow và luồng duyệt**

| # | Kịch bản | Kết quả đúng |
|---|---|---|
| T16 | NV submit Leave Application, Attendance Request, Compensatory Leave Request của chính mình | Bị chặn |

**D. Hệ thống, sync, code**

| # | Kịch bản | Kết quả đúng |
|---|---|---|
| T53 | Attendance Request: người được Assign To (`custom_approver`) duyệt; một trưởng bộ phận khác duyệt | Người được giao duyệt được; người khác bị chặn |

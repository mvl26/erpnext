# TK_01 – Phân quyền ERP Miyano – Nhân sự – hồ sơ, tổ chức, vòng đời, công tác

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
| AP | MVL Approver | **mới** | 1 | bước duyệt Ban Giám đốc trong workflow; thay role COO |

## Mục 3.2 – Ràng buộc từ mã nguồn (trích các dòng liên quan)

**Code tự gán role.** Role Profile ghi đè toàn bộ role mỗi lần lưu User (mục 4), nên các role dưới đây phải nằm sẵn trong profile:

| Nơi | Hành vi | Hệ quả |
|---|---|---|
| `erpnext/setup/doctype/employee/employee.py:108` | Gán `Employee` cho user liên kết với nhân viên | Có sẵn trong BASE. KHO-PDA không có BASE nên profile gỡ lại |
| `hrms/overrides/employee_master.py:85` | Gán Leave Approver / Expense Approver cho người được ghi ở `leave_approver` / `expense_approver` | Người duyệt phải có profile chứa TBP; sync kiểm tra |
| `hrms/setup_vn_defaults.py` (after_migrate) | Tạo lại role COO và workflow Cong Tac Approval nếu không còn | COO chỉ tắt, không xóa; workflow sửa tại chỗ, không xóa (9.4) |

## Mục 4 – Chân dung → Role Profile (trích các dòng liên quan)

Hai gói dùng chung:
- `BASE` = EMP, PJU (mọi user nội bộ).
- `TBP` = DH, LA, EA (người duyệt đơn của nhân viên).

| Chân dung | Role Profile | Roles |
|---|---|---|
| NS-NV | RP-NS-NV | BASE, HU, ST |
| NS-TP | RP-NS-TP | BASE, TBP, HU, HM, AO |
| NV | RP-NV | BASE |

## Mục 7 – HRMS (câu mở đầu)

Mọi ô `[e]`, `[d]` trong mục này được thực thi bằng hook H8.

## Mục 7.1 – Hồ sơ, tổ chức, vòng đời

| DocType | EMP | DH | HU | HM | Khác |
|---|---|---|---|---|---|
| Employee | R[e] | R[d] | CRW | CRW W1 O I | AU R; AM R R1 |
| Department, Designation, Branch, Employee Grade, Employment Type, Employee Group (G8) | | | CRW | CRWD | |
| Employee Onboarding, Employee Separation | R[e] | R[d] | CRW | CRWSXA | |
| Employee Onboarding Template, Employee Separation Template | | | CRW | CRWD | |
| Employee Promotion, Employee Transfer | R[e] | R[d] | CRW | CRW W1, SXA WF | AP (G2) |
| Exit Interview | RW[e] | | CRW | CRWSXA | |
| Full and Final Statement | | | CRW | CRWSXA W1 | AM R R1 |
| Employee Grievance | CRW·o | | | CRWSXA | ngoại lệ G1; HU không đọc |
| Grievance Type (G8) | | | | CRWD | |
| Employee Referral | CRWS·o R1 | | RW W1 | CRWSXA W1 | |
| Business Trip (fork – quyết định cử đi công tác) {D13} | | R[d] | CRW | CRWSXA | AP (G2) |
| Purpose of Travel (G8) | | | | CRW | |
| Employee Checkin | CR R1 [e] | R R1 [d] | CRW W1 | CRW W1 | SYS R |
| Employee Health Insurance, Identification Document Type (G8), Skill (G8), Interest | | | CRW | CRWD | |
| Employee Skill Map | R[e] | R[d] | CRW | CRWD | |

Ghi chú:
- Các bước bàn giao trong Onboarding và Separation sinh ra Task. Người thực hiện (IT-QT: tài khoản, thiết bị; STM: tài sản kho; AM: tạm ứng, công nợ) truy cập Task qua `[g]`.
- Nhân viên nghỉ việc thì đặt status = Left; không xóa Employee.
- Employee Checkin là dữ liệu chấm công gốc nên HM cũng không có D. Trường `time` ở level 1: nhân viên không sửa được giờ chấm.

## Mục 7.6 – HRMS không dùng

Travel Request (dùng Business Trip thay, D13), Daily Work Summary, Daily Work Summary Group, Vehicle Log, Vehicle Service Item: `g1_only`.

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
| WF-BT | Business Trip | Nháp(0), Chờ COO duyệt(0), COO đã duyệt(1), Đã ra QĐ(1), Hoàn tất(1), Từ chối(0) – **giữ đúng tên state hiện có** (ghi chú 5) | HU | HM |

**Transition:**

| Workflow | Từ | Hành động | Đến | Role | Điều kiện (ngoài G11) |
|---|---|---|---|---|---|
| WF-HR | Nháp | Gửi duyệt | Chờ BGĐ | HM | |
| | Chờ BGĐ | Duyệt / Từ chối | Đã duyệt / Từ chối | AP | |
| WF-BT | Nháp | Gửi duyệt | Chờ COO duyệt | HU | |
| | Chờ COO duyệt | Duyệt / Từ chối | COO đã duyệt / Từ chối | AP | `doc.approver_coo == frappe.session.user` |
| | COO đã duyệt | Ra QĐ | Đã ra QĐ | HM | |
| | Đã ra QĐ | Hoàn tất | Hoàn tất | HM | |

Ghi chú:
5. **WF-BT – Business Trip:**
   - `workflow_state` là trường Select với danh sách tên state cố định trong JSON của fork hrms, và đã có 4 bản ghi ở COO đã duyệt / Đã ra QĐ. Đổi tên state sẽ làm lưu phiếu báo lỗi Select.
   - Chưa có state Đã hủy vì danh sách Select chưa có giá trị này. Thêm "Đã hủy" và đặt `no_copy = 1` là việc của C6.
   - Chỉ đổi role: COO → AP; bỏ System Manager và AssetCore Super Admin khỏi mọi transition.

## Mục 9.4 – Workflow đang có trên site (trích các dòng liên quan)

Frappe chỉ chạy một workflow đang bật cho mỗi DocType.

| Workflow hiện có | DocType | Xử lý |
|---|---|---|
| Cong Tac Approval | Business Trip | **Sửa tại chỗ thành WF-BT, không xóa.** `hrms.setup_vn_defaults.ensure_defaults` (gọi `hrms/patches/v15_0/setup_cong_tac_workflow.py` mỗi lần migrate) tạo lại bản cũ nếu workflow hoặc role COO không còn. Sửa code fork hrms theo C6 |

## Mục 10 – User Permission (trích các dòng liên quan)

| Đối tượng | Áp cho | Cấu hình |
|---|---|---|
| Employee, Department | Không dùng – thay bằng H8 | |

Ghi chú:
- Mọi Employee có `create_user_permission = 0` (11.7). Sync xóa User Permission Employee/Department/Company còn sót do HRMS tự tạo.

## Mục 11.1 – Trường perm level (trích các dòng liên quan)

**Trường Miyano đặt thêm** (Property Setter):

| DocType | Trường | Level | Đọc | Ghi |
|---|---|---|---|---|
| Employee | `ctc`, `salary_currency`, `salary_mode`, `bank_name`, `bank_ac_no`, `iban` | 1 | HM, AM | HM |
| Salary Component, Salary Structure, Salary Structure Assignment, Salary Slip, Additional Salary, Employee Incentive, Retention Bonus, Gratuity, Full and Final Statement, Employee Promotion (`revised_ctc`) | mọi trường tiền và bảng earnings/deductions | 1 | HM, AM, VW, AP; EMP (Salary Slip của mình) | HM |

**Trường đã ở perm level 1 sẵn – erpnext, hrms** (phải cấp lại vì Custom DocPerm thay thế dòng level 1 chuẩn, kể cả `All` R1):

| DocType | Trường | Đọc | Ghi | Lý do |
|---|---|---|---|---|
| Employee Referral | `status` | EMP | HU, HM | |
| Employee Checkin | `time` | EMP, DH | HU, HM | Nhân viên không sửa giờ chấm |

## Mục 11.2 – Custom Role trên Report (trích các dòng liên quan)

| Nhóm | Report | ref_doctype | Roles |
|---|---|---|---|
| Nhân sự | Employee Leave Balance, Employee Leave Balance Summary, Employee Analytics, Employee Information, Employee Birthday | Employee | HU, HM, VW |
| Nhân sự | Employee Exits | Exit Interview | HU, HM, VW |

## Mục 11.3 – Hook (phân hệ `access` {D17}) (trích các dòng liên quan)

| Mã | Gắn vào | Nội dung | Bắt buộc |
|---|---|---|---|
| H8 | `permission_query_conditions` + `has_permission` cho DocType có `[e]`/`[d]` (6.9, mục 7) | Với user U, DocType X, ptype p: (a) U có role nào **khác EMP và DH** được p trên X mà không ghi phạm vi → không giới hạn; (b) nếu không, và U có DH được p → chỉ hồ sơ có `employee` thuộc một trong các nhóm: nhân viên thuộc Department mà U nằm trong bảng Department Approver (gồm Department con); nhân viên có `leave_approver`, `expense_approver` hoặc user của `reports_to` là U; chính U; (c) còn lại → chỉ hồ sơ có `employee` = Employee của U (với Employee: `name`). Không áp cho DocType chỉ có `·o` | ✓ |
| H9 | `after_insert` / `on_trash` của ToDo (Assign To) | Khi giao Task, Job Applicant, Interview, Training Program, Training Event: share bản ghi cho người được giao (Task share **Ghi**, còn lại share Đọc); gỡ share khi hủy giao. Assign To chuẩn của frappe chỉ share Đọc | ✓ |

## Mục 11.4 – Thay đổi code (trích các dòng liên quan)

**Trong fork mvl26/hrms (repo riêng, cần người phụ trách repo đó):**

| Mã | File | Thay đổi |
|---|---|---|
| C6 | `hrms/patches/v15_0/setup_cong_tac_workflow.py`, `hrms/hr/doctype/business_trip/business_trip.json` | (a) Bản tự phục hồi dùng role và transition của WF-BT (AP thay COO, không có System Manager/AssetCore Super Admin). (b) Thêm "Đã hủy" vào Select `workflow_state`. (c) Đặt `no_copy = 1` cho `workflow_state`: hiện thiếu, nên khi Amend, phiếu mới chép state cũ và frappe báo "Workflow State transition not allowed" |

## Mục 11.6 – Workspace (trích các dòng liên quan)

| Workspace (tên trên site) | Roles |
|---|---|
| HR, Employee Lifecycle, Recruitment | HU, HM, VW (Recruitment thêm DH) |

## Mục 11.7 – Custom Field và Property Setter (trích các dòng liên quan)

| DocType | Trường | Thiết lập | Lý do |
|---|---|---|---|
| Employee | `create_user_permission` | `default = 0` | Không để HRMS tự tạo User Permission |
| Employee | `leave_approver`, `expense_approver`, `reports_to` | `reqd = 1` | Điều kiện của WF-LA, WF-AR, WF-EC; `reports_to` là nguồn của `custom_approver` trên Attendance Request |
| Business Trip | `approver_coo` | `reqd = 1` | Điều kiện của WF-BT; người được chọn phải có AP |

## Mục 11.8 – Page (trích các dòng liên quan)

Roles của Page ghi bằng Custom Role (sync). Page không có trong bảng thì giữ Roles chuẩn của frappe.

| Page | Roles mới | Roles hiện có trên site |
|---|---|---|
| organizational-chart | HU, HM | HR User, HR Manager |

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
| T34 | Hủy rồi Amend một PO, một Business Trip đã duyệt | Phiếu hủy ở Đã hủy; phiếu Amend bắt đầu từ Nháp, lưu không lỗi (Business Trip: sau C6) |

**D. Hệ thống, sync, code**

| # | Kịch bản | Kết quả đúng |
|---|---|---|
| T49 | NV mở form Leave Application, chọn người duyệt; HU giao Task cho đồng nghiệp | Danh sách user hiện ra (dòng `Desk User` select trên User được giữ) |
| T54 | User có AP nhưng không phải `approver_coo` duyệt Business Trip | Bị chặn |

## Mục 14 – Điểm cần chốt (đã điền phương án mặc định) (trích các dòng liên quan)

| Mã | Nội dung | Mặc định |
|---|---|---|
| D11 | Strict User Permissions, phạm vi hồ sơ nhân sự | Strict = 0; `[e]`/`[d]` bằng H8 |
| D13 | Công tác | Business Trip (fork) với WF-BT; không dùng Travel Request; AP thay COO |

## Phụ lục B – DocType không dùng (`g1_only`), ghi đúng tên (trích các dòng liên quan)

Các DocType dưới đây chỉ có dòng G1 (SYS `R B`, VW `R P B`). DocType của frappe giữ thêm dòng chuẩn của `All` / `Desk User` (G10).

| App / module | DocType |
|---|---|
| hrms / HR | Travel Request, Daily Work Summary, Daily Work Summary Group, Vehicle Log, Vehicle Service Item |

# TK_01 – Đặc tả phân quyền ERP Miyano (bản cho AI triển khai) – V2.1

| Thuộc tính | Nội dung |
|---|---|
| Mã | TK_01_ThietKePhanQuyen_ERP – dự án ERP-SCM (PROJ-0087) |
| Phiên bản | V2.1 – bản hợp nhất 23/10/2026 (đã qua rà soát lần 2), thay thế V2.0 (22/10/2026). Thay đổi: mục 15 |
| Hệ thống | erp.miyano.com.vn – Frappe v15, site `miyano` |
| App đang cài trên site | frappe, erpnext, hrms (fork mvl26/hrms), assetcore |
| Phạm vi | Mọi DocType của **frappe, erpnext, hrms**, gồm cả các module riêng của Miyano nằm trong app erpnext (Einvoice, TBYT, Warehouse Operations, Debt Reconciliation, Supply Notification, EDI) và các DocType bổ sung trong fork hrms |
| Ngoài phạm vi | assetcore (gồm **Asset Repair**, các DocType IMM-\*, 30 role và 8 Role Profile của assetcore); các app chưa cài trên site (supplycore, miyano_portal, miyano_pda, antmed_crm, normcore_dmktkt, norm_himedic, workflowcore); workspace tùy chỉnh |
| Trạng thái | Dự thảo – các tham số `{Dx}` chờ chốt ở mục 14; đã điền phương án mặc định |
| Hiện trạng site | Số liệu đo ngày 23/10/2026: Phụ lục A |

---

## 0. Cách dùng tài liệu

- Tài liệu là **nguồn sự thật** để AI/IT dựng cấu hình quyền. Mục 3–11 chuyển nguyên trạng thành file `erpnext/access/permissions/matrix.json` (mục 12).
- Mỗi DocType ghi quyền theo **Role** (thứ Frappe cấu hình được), không theo chân dung. Chân dung → Role Profile ở mục 4.
- **Ô trống = không có quyền.**
- **Mọi DocType (không phải bảng con) của 3 app phải có mặt trong file ma trận** ở một trong bốn trạng thái. Lệnh sync dừng và báo lỗi nếu còn DocType chưa được xếp loại.

| Trạng thái | Ý nghĩa | Nơi ghi |
|---|---|---|
| `matrix` | Quyền theo bảng | Mục 6–8 |
| `ref_master` | Danh mục tham chiếu, áp G8 | Mục 5 (G8) và bảng của từng mục |
| `g1_only` | Chỉ có dòng G1 (SYS, VW) – DocType không dùng | Mục 6.12, 7.6, 8 |
| `keep_standard` | Giữ DocPerm chuẩn của frappe (quyền theo owner, người được giao hoặc tài liệu gốc) | Mục 8 |

## 1. Nguyên tắc bắt buộc

1. **Tối thiểu cần thiết.** Chỉ cấp đúng quyền ghi trong ma trận.
2. **Tách nhiệm.** Người lập ≠ người duyệt, kể cả khi một người giữ cả role lập và role duyệt (G11). Kho không ghi hóa đơn mua. Bán hàng không sửa giá vốn. IT không tự cấp quyền nghiệp vụ và không thao tác nghiệp vụ kho, kế toán.
3. **Không ai có quyền Xóa (D) trên DocType submittable**, kể cả Manager. Danh mục gốc (Customer, Supplier, Item, Serial No, Employee, Account, Warehouse, User) cũng không xóa, mà dùng Disabled / Left / Enabled = 0.
4. **Một user nội bộ = một Role Profile.** Không gán Role lẻ. Role mà code kiểm tra cứng (mục 3.2) phải nằm trong Role Profile tương ứng.
5. **Ẩn workspace không phải là bảo mật.** Module Profile cũng chỉ ẩn desktop và workspace, không chặn truy cập DocType. Bảo mật được dựng từ Custom DocPerm, perm level, User Permission, Custom Role của Report, workflow và hook.
6. **Thay đổi quyền trên production chỉ qua deploy file ma trận** (mục 12). Không sửa tay trong Role Permission Manager.
7. **Rà soát định kỳ.** Rà soát quyền mỗi quý. Nhân sự nghỉ việc thì khóa tài khoản trong ngày.

## 2. Ký hiệu

**Quyền (ptype Frappe):**

| Ký hiệu | Quyền | Ký hiệu | Quyền |
|---|---|---|---|
| R | read | P | print |
| W | write | E | email |
| C | create | B | report (tự cấp theo G7) |
| D | delete | O | export |
| S | submit | I | import |
| X | cancel | H | share |
| A | amend | L | select (chỉ chọn trong ô Link) |

**Perm level:** `R1` / `W1` = đọc / ghi perm level 1; `R2` / `W2` = đọc / ghi perm level 2. Danh sách trường ở mục 11.1. `W1` bao gồm `R1`.

**Phạm vi dữ liệu:**

| Ký hiệu | Cơ chế |
|---|---|
| `·o` | If Owner – bản ghi do chính user tạo |
| `[e]` | Chỉ hồ sơ của chính nhân viên – hook H8 |
| `[d]` | Hồ sơ nhân viên thuộc bộ phận do user làm trưởng – hook H8 |
| `[w]` | User Permission Warehouse = kho được giao (mục 10) |
| `[pl]` | User Permission Price List (mục 10) |
| `[c]` / `[s]` | User Permission Customer / Supplier = chính đơn vị đó |
| `[g]` | Được giao: Assign To kèm share (hook H9) |
| `WF` | S/X/chuyển trạng thái chỉ qua transition của workflow ở mục 9 (role vẫn phải có S trong DocPerm) |
| `(G8)` | Quyền R đến từ quy tắc danh mục tham chiếu G8, không ghi lặp trong ô |

---

## 3. Role

### 3.1 Danh mục role dùng trong ma trận

| Mã | Role | Loại | Desk | Ghi chú |
|---|---|---|---|---|
| PU | Purchase User | chuẩn | 1 | |
| PM | Purchase Manager + Purchase Master Manager | chuẩn | 1 | luôn gán cùng nhau |
| IM | Item Manager | chuẩn | 1 | chủ dữ liệu Item {D7} |
| IC | MVL Item Creator | **mới** | 1 | thay Item Manager cho MH-NV (không có D) |
| SU | Sales User | chuẩn | 1 | |
| SM | Sales Manager + Sales Master Manager | chuẩn | 1 | luôn gán cùng nhau |
| MK | MVL Marketing | **mới** | 1 | thay Sales User cho MKT-NV |
| NL | Newsletter Manager | chuẩn | 1 | |
| STU | Stock User | chuẩn | 1 | gánh luôn phần Delivery User |
| STM | Stock Manager | chuẩn | 1 | gánh luôn phần Delivery Manager |
| QM | Quality Manager | chuẩn | 1 | |
| PDA | MVL Kho PDA | **mới** | 1 | chỉ thấy workspace "Quản lý kho" và 3 trang PDA (11.8) {D6} |
| AU | Accounts User | chuẩn | 1 | |
| AM | Accounts Manager | chuẩn | 1 | |
| EI | Kế toán HĐĐT | có sẵn | 1 | lập nháp HĐĐT; code kiểm tra theo tên (3.2) {D22} |
| EIC | Kế toán trưởng HĐĐT | có sẵn | 1 | phát hành, hủy HĐĐT; code kiểm tra theo tên (3.2) {D22} |
| AO | MVL Asset Operator | **mới** | 1 | IT-QT (tài sản CNTT), NS-TP (CCDC hành chính) |
| HU | HR User | chuẩn | 1 | |
| HM | HR Manager | chuẩn | 1 | |
| DH | MVL Department Head | **mới** | 1 | **mang toàn bộ quyền duyệt của trưởng bộ phận**; luôn đi cùng LA, EA (gói TBP) |
| LA, EA | Leave Approver, Expense Approver | chuẩn hrms | 1 | **Role đánh dấu, không có dòng Custom DocPerm nào.** Giữ trong gói TBP vì hrms tự gán cho người duyệt (3.2); nếu thiếu trong profile, frappe gỡ khi lưu User |
| EMP | Employee | chuẩn | 1 | mọi user nội bộ |
| PJU | Projects User | chuẩn | 1 | mọi user nội bộ |
| PJM | Projects Manager | chuẩn | 1 | |
| ST | Support Team | chuẩn | 1 | |
| VW | MVL Viewer | **mới** | 1 | chỉ đọc |
| AP | MVL Approver | **mới** | 1 | bước duyệt Ban Giám đốc trong workflow; thay role COO |
| LK | MVL Khóa sửa | **mới** | 0 | **Không gán cho user nào, không có DocPerm.** Chỉ dùng làm `allow_edit` của trạng thái chờ duyệt để không ai sửa được nội dung (9.2) |
| PRU | Prepared Report User | chuẩn | 1 | xem kết quả báo cáo chạy nền (Stock Balance) |
| SNA | Quản trị thông báo | có sẵn | 1 | quản trị Supply Notification (3.2) |
| SYS | System Manager | chuẩn | 1 | |
| WM | Website Manager | chuẩn | 1 | |
| WSM | Workspace Manager | chuẩn | 1 | |
| DEV | MVL IT Dev | **mới** | 1 | production chỉ đọc log |
| CUS | Customer | chuẩn | **0** | |
| SUP | Supplier | chuẩn | **0** | |

### 3.2 Ràng buộc từ mã nguồn

**Role được code kiểm tra theo tên** (đổi tên hoặc bỏ khỏi profile thì chức năng ngừng chạy):

| Role | Nơi kiểm tra | Chức năng |
|---|---|---|
| Kế toán HĐĐT | `erpnext/einvoice/setup.py:23` | lập nháp, gửi khách, xem PDF hóa đơn điện tử |
| Kế toán trưởng HĐĐT | `erpnext/einvoice/issue.py:156`, `erpnext/einvoice/cancel.py:34` | phát hành, hủy hóa đơn điện tử |
| Quản trị thông báo | `erpnext/supply_notification/dispatch.py:419` | quản trị và gửi thông báo cung ứng |
| Accounts Manager, Accounts User | `erpnext/debt_reconciliation/constants.py:42` | đối chiếu công nợ |
| System Manager, Stock Manager, Stock User | `erpnext/warehouse_operations/vitri/*.py` (hằng `VAI_TRO_*`) | quét, xếp, lấy hàng, in tem vị trí kho – sửa theo C1 |
| HR Manager, HR User, System Manager | `hrms/hr/doctype/attendance_request/attendance_request_miyano.py:41` (`APPROVER_BYPASS_ROLES`, dùng trong `guard_submit`, nối ở `hrms/hooks.py:109-116`) | submit Attendance Request thay cho người duyệt `custom_approver` – sửa theo C5 |

**Code cho System Manager vượt quyền nghiệp vụ:**

| Nơi | Hành vi | Xử lý |
|---|---|---|
| `erpnext/einvoice/setup.py:405` `is_chief_accountant` | System Manager phát hành, hủy HĐĐT như Kế toán trưởng HĐĐT | Sửa C4 |
| `erpnext/warehouse_operations/vitri/*.py` | System Manager thao tác kho | Sửa C1 |
| `hrms/hr/attendance_exempt.py:381, 391` | `only_for(HR Manager, System Manager)` – miễn chấm công | Sửa C5 |
| `hrms/hr/doctype/attendance_request/attendance_request_miyano.py:41` | System Manager (và HR User) submit được mọi Attendance Request | Sửa C5 |
| `erpnext/stock/item_code_rule.py:490` `_may_rename` | System Manager luôn được đổi mã vật tư | Chấp nhận: khớp quy định đổi mã chỉ do IT-QT; để `Stock Settings.item_rename_role` trống |
| `erpnext/setup/doctype/transaction_deletion_record/transaction_deletion_record.py:61` | System Manager được chạy xóa toàn bộ giao dịch | Chặn bằng DocPerm: SYS chỉ có R (6.12) |

**Code tự gán role.** Role Profile ghi đè toàn bộ role mỗi lần lưu User (mục 4), nên các role dưới đây phải nằm sẵn trong profile:

| Nơi | Hành vi | Hệ quả |
|---|---|---|
| `erpnext/setup/doctype/employee/employee.py:108` | Gán `Employee` cho user liên kết với nhân viên | Có sẵn trong BASE. KHO-PDA không có BASE nên profile gỡ lại |
| `hrms/hr/doctype/attendance_request/attendance_request_miyano.py:45, 57` | Điền `custom_approver` = user của `reports_to`, rồi Assign To cho người này | Người duyệt Attendance Request là quản lý trực tiếp, không phải `leave_approver` (WF-AR). User của `reports_to` phải có TBP |
| `hrms/overrides/employee_master.py:85` | Gán Leave Approver / Expense Approver cho người được ghi ở `leave_approver` / `expense_approver` | Người duyệt phải có profile chứa TBP; sync kiểm tra |
| `assetcore/services/shared/role_hooks.py:30` `sync_umbrella` | Gán AssetCore Super Admin thì tự thêm System Manager; gỡ thì gỡ kèm | Ai có Super Admin cũng thành SYS của ERP. Chỉ cấp Super Admin cho IT-QT {D19} |
| `hrms/setup_vn_defaults.py` (after_migrate) | Tạo lại role COO và workflow Cong Tac Approval nếu không còn | COO chỉ tắt, không xóa; workflow sửa tại chỗ, không xóa (9.4) |

### 3.3 Role không dùng

Sau khi chuyển user sang Role Profile mới (mục 12, bước 6), các role dưới đây được gỡ khỏi mọi user và đặt `disabled = 1`:

- **Role chuẩn:** Report Manager, Delivery User, Delivery Manager, Manufacturing User/Manager, Maintenance User/Manager, Blogger, Academics User, Agriculture User/Manager, Healthcare Administrator, Laboratory User, Fulfillment User, Auditor, Internal Auditor, Analytics, Script Manager, Dashboard Manager, Inbox User, Knowledge Base Contributor/Editor, Translator, Fleet Manager, Interviewer, Employee Self Service, COO (thay bằng AP).
- **Role tiếng Việt cũ, không có DocPerm:** Kế toán công nợ - ngân hàng, Kế toán kho - ký gửi, Kế toán tổng hợp, Kế toán trưởng, Thủ kho, Thủ quỹ, NV kinh doanh, Nhân viên mua hàng, Quản lý, Quản lý xem báo cáo.
- **Role thử nghiệm và role của app chưa cài:** Test Approver, Test Junior Approver, Norm Manager, Norm User.
- **Administrator:** không dùng cho người.
- **Role tự động `All`, `Desk User`, `Guest`:** không tắt được. Không cấp quyền nghiệp vụ qua các role này (G10).
- **Role của assetcore:** không đụng tới.

---

## 4. Chân dung → Role Profile

Hai gói dùng chung:
- `BASE` = EMP, PJU (mọi user nội bộ).
- `TBP` = DH, LA, EA (người duyệt đơn của nhân viên).

| Chân dung | Role Profile | Roles |
|---|---|---|
| BGD-GDVH – Giám đốc Vận hành | RP-BGD-GDVH | BASE, TBP, SYS, PM, IM, SM, STM, QM, AM, HM, PJM, AP, PRU {D5} |
| BGD-GD – Giám đốc điều hành | RP-BGD-GD | BASE, TBP, VW, AP, PRU |
| MH-NV | RP-MH-NV | BASE, PU, IC |
| MH-TP | RP-MH-TP | BASE, TBP, PU, PM, IM |
| KD-NV | RP-KD-NV | BASE, SU, ST |
| KD-TP | RP-KD-TP | BASE, TBP, SU, SM, ST |
| MKT-NV | RP-MKT-NV | BASE, MK, NL |
| KHO-TK | RP-KHO-TK | BASE, STU |
| KHO-PDA | RP-KHO-PDA | PDA (không có BASE); Module Profile chỉ mở Stock, Warehouse Operations {D6} |
| KHO-TP | RP-KHO-TP | BASE, TBP, STU, STM, QM |
| KT-NV | RP-KT-NV | BASE, AU, EI {D12} |
| KT-KTT | RP-KT-KTT | BASE, TBP, AU, AM, EI, EIC, PRU {D12} |
| NS-NV | RP-NS-NV | BASE, HU, ST |
| NS-TP | RP-NS-TP | BASE, TBP, HU, HM, AO |
| IT-QT | RP-IT-QT | BASE, SYS, WM, WSM, ST, AO, SNA |
| IT-DEV | RP-IT-DEV | BASE, DEV (site dev/test: SYS) |
| DA-PM | RP-DA-PM | BASE, PJM |
| NV | RP-NV | BASE |
| NG-KH | RP-NG-KH | CUS |
| NG-NCC | RP-NG-NCC | SUP |

**Vai trò của hai giám đốc trong luồng duyệt:**
- **GĐVH là cấp duyệt thay** khi trưởng bộ phận hoặc KTT là người lập chứng từ (GĐVH giữ mọi role Manager). Hai cấp duyệt liên tiếp không được do cùng một người (H10). Vì vậy khi GĐVH đã duyệt thay ở cấp trưởng bộ phận, bước BGĐ sau đó do BGD-GD duyệt.
- BGD-GD có TBP để duyệt đơn nghỉ, chi phí của các trưởng bộ phận.
- GĐVH vắng mặt thì ủy quyền bằng Role Profile tạm (bên dưới), không gán role duyệt cố định cho người khác.

**Một user chỉ có một Role Profile, và profile ghi đè toàn bộ role.** Frappe v15 chỉ có trường `role_profile_name`. Mỗi lần lưu User, `populate_role_profile_roles` (`frappe/core/doctype/user/user.py:208`) xóa hết role rồi gán lại đúng role của profile. Do đó:
- Người dùng cả ERP và assetcore có **profile ghép** `RP-<chân dung>+AC-<profile assetcore>`, chứa hợp role của hai profile. Sync sinh các profile này từ cặp (chân dung, profile assetcore) khai báo trong file ma trận {D19}. Không sửa 8 profile gốc của assetcore.
- Người được ghi là `leave_approver` / `expense_approver` trên Employee phải có profile chứa TBP.
- Role do code tự gán (3.2) mà không nằm trong profile sẽ bị gỡ.

**Role Profile cũ:** 6 profile ERP đang có (Inventory, Manufacturing, Accounts, Sales, Purchase, HR) và các profile do `erpnext/regional/vietnam/role_profiles.py` tạo được thay bằng profile `RP-*` (C3). Không gỡ profile của assetcore.

**Quyền ngoài chân dung:** cấp bằng Role Profile biến thể có hạn, tên `RP-<gốc>+TMP-<yyyymmdd>`, chứa role của profile gốc cộng role được cấp thêm. GĐVH duyệt, tối đa 3 tháng. Job H7 trả user về profile gốc khi hết hạn.

---

## 5. Quy tắc chung áp cho mọi bảng

- **G1. Bộ Custom DocPerm đầy đủ.** Mỗi DocType ở trạng thái `matrix`, `ref_master` hoặc `g1_only` phải có bộ Custom DocPerm đầy đủ, vì Custom DocPerm thay thế hoàn toàn DocPerm chuẩn (kể cả các dòng level 1 và dòng `All`). Ngoài các ô trong bảng, mỗi DocType tự có thêm:
  - SYS: `R B`
  - VW: `R P B`, cộng `R1` với DocType lương và Stock Ledger Entry, Bin

  Ngoại lệ: Employee Grievance không có dòng SYS và VW (hồ sơ khiếu nại bảo mật).
- **G2. Role duyệt BGĐ.** AP chỉ có quyền trên DocType có bước BGĐ: Purchase Order, Payment Entry, Expense Claim, Employee Advance, Payroll Entry, Salary Structure Assignment, Employee Promotion, Employee Transfer, Job Offer, Business Trip. Quyền gồm `R W S`, cộng `R1` với DocType lương. Ô `AP R`/`AP RW` ghi riêng trong bảng là quyền xem thêm.
- **G3. Xóa.** Không ai có D trên DocType submittable. Với danh mục phụ (UOM, Item Group, Leave Type…), role Manager được D; frappe tự chặn xóa khi bản ghi đã được liên kết.
- **G4. Share, export, import.** `H` và `O` chỉ cấp ở ô ghi rõ. Role có `I` thì được thêm `CRW·o` trên Data Import.
- **G5. Không dùng L đơn lẻ cho danh mục mà form cần đọc.** `frappe.db.get_value` phía client đòi quyền `read` (`frappe/client.py:125`), và form ERPNext gọi hàm này lên Warehouse, Company, Item Group, Cost Center, Price List, UOM, Currency, Stock Entry Type. Chỉ cấp L khi ghi rõ.
- **G6. Chứng từ của nhân viên.** Quyền của EMP trên chứng từ HR luôn đi kèm `[e]` (H8).
- **G7. R kéo theo B.** Role có R trên DocType thì tự có B. Frappe chỉ mở Query/Script Report khi user có quyền `report` trên `ref_doctype` (`frappe/desk/query_report.py:47`). Report view tôn trọng perm level và phạm vi dữ liệu; Script Report thì không, nên phải giới hạn bằng Custom Role (11.2).
- **G8. Danh mục tham chiếu.** EMP có `R` trên các DocType sau; PDA cũng có `R` trên DocType đánh dấu `†`. Quyền ghi nằm ở bảng của từng mục.
  - **Settings đọc chung (Single):** Accounts Settings, Stock Settings†, Buying Settings, Selling Settings. Form ERPNext gọi `frappe.db.get_single_value` phía client lên các Single này, và hàm đó đòi quyền read (`frappe/client.py:167`).
  - **ERPNext:** Party Type, Company†, Currency†, UOM†, UOM Category†, UOM Conversion Factor†, Item Group†, Brand†, Item Attribute†, Warehouse†, Warehouse Type†, Stock Entry Type†, Manufacturer, Customs Tariff Number, Quality Inspection Parameter, Quality Inspection Parameter Group, Price List, Cost Center, Fiscal Year, Finance Book, Mode of Payment, Payment Terms Template, Payment Term, Tax Category, Territory, Customer Group, Supplier Group, Sales Person, Sales Partner, Sales Partner Type, Incoterm, Print Heading, Quotation Lost Reason, Lead Source, Sales Stage, Opportunity Type, Opportunity Lost Reason, Market Segment, Industry Type, Competitor, Issue Type, Issue Priority, Activity Type, Project Type, Task Type, Location, Asset Category, Driver, Vehicle, TBYT Document Type.
  - **HRMS:** Department, Designation, Branch, Employee Grade, Employment Type, Employee Group, Holiday List, Leave Type, Leave Period, Leave Block List, Shift Type, Shift Location, Attendance Code, Expense Claim Type, Purpose of Travel, Grievance Type, Identification Document Type, Skill, Job Applicant Source, Payroll Period, Employee Tax Exemption Category, Employee Tax Exemption Sub Category.
  - **Frappe:** Country, Salutation, Gender, Address Template, Letter Head.
- **G9. Perm level.** Mục 11.1 là nguồn duy nhất cho quyền perm level, gồm cả các trường mà frappe/erpnext/hrms **đã đặt sẵn** ở level 1. Khi user không có quyền ghi ở level của trường, frappe trả trường về giá trị cũ lúc lưu, kể cả giá trị do workflow đặt (`frappe/model/document.py:783`). Sync dừng nếu:
  - ô `R1/W1/R2/W2` ở mục 6–8 lệch với 11.1;
  - DocType trong file ma trận có trường level > 0 (`meta.get_high_permlevel_fields()`) chưa khai báo ở 11.1. Khai báo "không ai" cũng hợp lệ.

  G9 **không áp dụng** cho DocType `keep_standard`. Các DocType này giữ nguyên dòng chuẩn ở mọi level, ví dụ Communication (`email_inbox` level 1, `timeline_links` level 2) và Note (6 trường level 1).
- **G10. Role tự động.** Không cấp quyền nghiệp vụ cho `All`, `Desk User`, `Guest`.
  - Với DocType của **erpnext, hrms** (mục 6–7): sync xóa dòng của các role này.
  - Với DocType của **frappe** (mục 8): sync **chép lại nguyên các dòng chuẩn** của `All` / `Desk User` vào bộ Custom DocPerm. **Ngoại lệ: Contact và Address** theo đúng bảng 6.8, không chép dòng chuẩn. Dòng chuẩn là `All` R W C (Contact có thêm D), áp khi là chủ bản ghi; nếu chép, mọi user kể cả PDA, CUS, SUP tạo được Contact/Address và xóa được Contact của mình, trái 6.8. Giao diện cần các dòng này, ví dụ `Desk User` select trên User (ô chọn người trong Assign To, `leave_approver`, `approver_coo` dùng `user_query` → `frappe.get_list`, `frappe/core/doctype/user/user.py:1099`), select trên Module Def, read trên Form Tour, Dashboard, Language.
- **G11. Người lập ≠ người duyệt.** Profile trưởng bộ phận gộp role lập và role duyệt (MH-TP: PU+PM, KD-TP: SU+SM, KHO-TP: STU+STM, KT-KTT: AU+AM, NS-TP: HU+HM); GĐVH gộp mọi role Manager và AP. Vì vậy mọi transition **xuất phát từ trạng thái "Chờ …"** có điều kiện:
  - `doc.owner != frappe.session.user`;
  - với chứng từ HR, thêm `frappe.db.get_value("Employee", doc.employee, "user_id") != frappe.session.user`.

  Ngoài ra H10 chặn một user thực hiện hai transition từ trạng thái "Chờ" trên cùng chứng từ. Transition xuất phát từ Nháp đi thẳng tới trạng thái đã duyệt là **tự duyệt trong hạn mức** (PO ≤ H1, Payment Entry ≤ H3 hoặc thu tiền, hóa đơn không phải hàng trả, Stock Entry chuyển kho, Sales Order đủ điều kiện {D4}); các transition này không áp G11.

---

## 6. ERPNext

### 6.1 Mua hàng

| DocType | PU | PM | STU | STM | AU | AM | Khác |
|---|---|---|---|---|---|---|---|
| Supplier | CRW | CRW O I H R2 | R | R | R W2 | R W2 | IC R; SU R; SUP R[s] |
| Supplier Group (G8) | | CRWD | | | | | |
| Request for Quotation | CRWS PE | CRWSXA PE O | | | R | R | SUP: không có DocPerm (ghi chú 1) |
| Supplier Quotation | CRWS PE | CRWSXA PE O W1 | | | R | R | SUP CRW[s] |
| Material Request | CRWS PE | CRWSXA PE | CRWS [w] | CRWSXA | R | R | SU CRWS; SM CRWSXA (ghi chú 3) |
| Purchase Order | CRW PE, S WF | CRW PE O H W1, SXA WF | R | R | R | R | AP (G2); SU R; SUP R[s] |
| Purchase Receipt | R | R | CRWS PE [w] | CRWSXA PE | R | R | PDA R [w] (trang quét tra cứu đọc phiếu nhập) |
| Purchase Invoice | R | R | | | CRWS PE, WF | CRWSXA PE O, WF | SUP R[s] |
| Purchase Taxes and Charges Template | R | R | | | R | CRW | |
| Blanket Order | R | CRWSXA | | | R | R | SU R; SM CRWSXA |
| Supplier Scorecard, Supplier Scorecard Criteria, Supplier Scorecard Standing, Supplier Scorecard Variable | R | CRW | | | | | |
| Supplier Scorecard Period | R | CRWSXA | | | | | |

Ghi chú:
1. RFQ chỉ có một trường Link Supplier ở đầu phiếu (`vendor`, thường để trống); danh sách NCC nằm ở bảng con. User Permission Supplier không lọc được RFQ qua API, nên NCC chỉ xem RFQ qua portal.
2. PO và PR có hiện giá mua cho Kho; giữ như V1.1.
3. `material_request_type` là trường Select nên không tách quyền theo loại được; SU tạo được mọi loại (rủi ro chấp nhận).
4. Blanket Order thuộc module **Manufacturing** nhưng được dùng cho mua và bán. Không xử lý theo module khi khóa Manufacturing.
5. Purchase Invoice do Kế toán lập.

### 6.2 Bán hàng

| DocType | SU | SM | STU | STM | AU | AM | Khác |
|---|---|---|---|---|---|---|---|
| Customer | CRW | CRW O I H R1 R2 | R | R | R R1 W2 | R W1 W2 | PU R; CUS R[c] |
| Customer Group, Territory, Sales Person, Sales Partner, Sales Partner Type (G8) | | CRWD | | | | | |
| Quotation | CRWS PE {D9} | CRWSXA PE O H W1 | | | R | R | CUS: không có DocPerm (ghi chú 1) |
| Sales Order | CRW PE, S WF | CRWSXA PE O H W1 | R | R | R | R | PU R; CUS R[c] |
| Delivery Note | R P | R P | CRWS PE [w] | CRWSXA PE | R | R | PDA RWS [w] (trang lấy hàng sửa số lượng rồi submit); CUS R[c] |
| Sales Invoice | R | R | | | CRWS PE, WF | CRWSXA PE O, WF | CUS R[c] |
| Price List (G8) | | CRW | | | | | PM CRW |
| Item Price | R[pl] | CRWD O I | | | R | R | PU CRW[pl]; PM CRWD O I |
| Pricing Rule, Promotional Scheme | R | CRWD | | | R | R | PU R; PM CRWD |
| Product Bundle | R | CRW | R | R | R | R | |
| Party Specific Item | R | CRWD | | | | | |
| Sales Taxes and Charges Template | R | R | | | R | CRW | |
| Terms and Conditions | R | CRW | | | R | CRW | PU R; PM CRW |
| Installation Note {D18} | CRWS | CRWSXA | R | R | | | |

Ghi chú:
1. Quotation (và Opportunity) gắn khách bằng `party_name` – trường Dynamic Link mà User Permission không lọc được. Cấp R cho CUS sẽ làm lộ báo giá của mọi khách qua API; khách xem báo giá qua portal.
2. Item Price tách mua/bán bằng User Permission Price List (mục 10).
3. Không khóa đơn giá trên dòng chứng từ bằng perm level. Kiểm soát giá bằng H2.
4. Giá cost-plus theo HĐ nguyên tắc (1,01 × giá mua) chỉ SM được sửa, sau khi PM cập nhật giá mua.

### 6.3 Kho

| DocType | STU | STM | PDA | Mua (PU / PM / IC / IM) | Bán (SU / SM) | AU | AM |
|---|---|---|---|---|---|---|---|
| Item | R | R | R | PU, PM R; IC CRW; IM CRW O I | R | R R2 | R W1 W2 |
| Item Group, Brand, UOM, UOM Category, UOM Conversion Factor, Item Attribute, Warehouse Type, Manufacturer, Customs Tariff Number (G8) | | | | IM CRWD | | | |
| Item Manufacturer, Item Alternative | R | R | | PU, PM R; IC CRW; IM CRWD | R | | |
| Warehouse (G8) | | CRW | | | | R R2 | R W2 |
| Stock Entry | CRW PE [w], S WF | CRWSXA PE, WF | CRW·o [w], S WF | PU, PM R | | R | R |
| Stock Entry Type (G8) | | CRW | | | | | |
| Stock Reconciliation | CRW [w] | CRWSXA PE, WF | CRW·o [w] | | | R | R SXA WF |
| Batch | CRW | CRW | CRW | R | R | R | R |
| Serial No | CRW | CRW | CRW | R | R | R | R |
| Serial and Batch Bundle | CRWS | CRWSX | CRWS | R | R | R (CRWS nếu dùng Update Stock trên hóa đơn) | R (CRWSX nếu dùng Update Stock) |
| Quick Stock Balance (Single – có giá trị tồn) | | | | | | | RW |
| Pick List | CRWS P [w] | CRWSXA | | | R | | |
| Packing Slip, Delivery Trip | CRWS P | CRWSXA | | | R | | |
| Driver, Vehicle (G8) | | CRW | | | | | |
| Shipment, Shipment Parcel Template | CRWS (Template: CRW) | CRWSXA (Template: CRWD) | | | R | | |
| Quality Inspection | CRWS | CRWSXA (QM giống STM) | | R | R | | |
| Quality Inspection Template, Quality Inspection Parameter, Quality Inspection Parameter Group | | CRW (QM giống STM) | | | | | |
| Stock Reservation Entry | R | CRWSXA | | | R | | |
| Putaway Rule | R | CRWD | R | | | | |
| Landed Cost Voucher | | R | | | | CRW | CRWSXA |
| Repost Item Valuation | | R | | | | | CRWSXA |
| Closing Stock Balance | | | | | | | CRWSXA |
| Stock Ledger Entry, Bin (hệ thống sinh) | R [w] | R | | R | R | R | R R1 |
| Inventory Dimension | | R | | | | | |

Ghi chú:
- **Serial and Batch Bundle bắt buộc trong v15** với hàng quản lý lô/serial. Khi submit Purchase Receipt, Delivery Note, Stock Entry…, bundle được submit **bằng quyền của user**: `erpnext/stock/serial_batch_bundle.py:387` gọi `doc.submit()` không kèm `ignore_permissions`. Nhánh `ignore_permissions` ở `erpnext/controllers/stock_controller.py:1882` chỉ dùng khi hệ thống tự tạo bundle. Vì vậy role nào submit chứng từ kho thì cần CRWS trên bundle; role nào hủy chứng từ kho thì cần thêm X. Schema chuẩn của erpnext cũng cấp S/X cho Stock User.
- **Serial No** là danh mục gốc của thiết bị y tế quản lý theo số serial; không ai có D.
- Repost Item Valuation do hệ thống tạo với `ignore_permissions` (`stock_controller.py:1805`); quyền trong bảng chỉ để xem và chạy lại thủ công.
- **Giá trị tồn {D10}:** trường giá trị của Stock Ledger Entry và Bin ở perm level 1 (11.1). Kho, Mua, Bán đọc được số lượng, không thấy giá trị, kể cả qua Report view.
- Stock Reservation Entry chỉ STM tạo; nút "Reserve" trên Sales Order do STM thực hiện.
- Đổi tên Item hàng loạt chỉ do IT-QT thực hiện bằng Rename Tool theo kế hoạch, ngoài khung khóa giao dịch 15:00–18:00.

### 6.4 Vị trí kho (module Warehouse Operations – Miyano)

| DocType | STU | STM | PDA |
|---|---|---|---|
| Storage Location | R | CRWD | R |
| Warehouse Location Setup, Location Generator | | CRW | |
| Item Location Preference | R | CRWD | |
| Batch Entry | CRWS [w] | CRWSXA | CRW·o [w] |
| Location Transfer | CRWS [w] | CRWSXA | CRWS·o [w] |
| Location Balance, Location Ledger Entry (hệ thống sinh) | R [w] | R | R [w] |

Các API quét, xếp, lấy hàng, in tem trong `erpnext/warehouse_operations/vitri/` kiểm tra role theo tên (3.2). Đến khi làm xong C1, SYS vẫn thao tác được còn PDA bị chặn.

Ngoài kiểm tra role, các API này còn kiểm tra quyền DocPerm trên chứng từ chúng thao tác. Quyền PDA cần, đã ghi trong các bảng:

| Trang PDA | Chứng từ, quyền cần | Nguồn |
|---|---|---|
| lay-hang-pda (Lấy hàng) | Delivery Note: W và S – `hoan_tat` kiểm `check_permission("write")`, lưu số lượng rồi `doc.submit()`; Serial and Batch Bundle: S | `vitri/lay_hang.py:1383, 2031` |
| quet-ma-tra-cuu (Quét tra cứu) | Purchase Receipt: R – `chan_doan_phieu_nhap` kiểm `has_permission("read")` | `vitri/phieu_nhap.py:88` |
| xep-hang-pda (Xếp hàng) | Location Transfer: C, W, S | `vitri/xep.py:178, 444, 486` |
| (in tem kiện) | Delivery Note: R | `vitri/tem_kien.py:64, 133` |

Các trang PDA không dùng Pick List, nên PDA không có quyền trên Pick List. PDA sửa được Delivery Note nhưng không đổi được đơn giá, vì Selling Settings "Maintain Same Rate Throughout Sales Cycle" = 1, Action = Stop (11.5) buộc giá trên Delivery Note bằng giá Sales Order.

### 6.5 Hồ sơ pháp lý thiết bị y tế (module TBYT – Miyano)

| DocType | IC | IM | Khác |
|---|---|---|---|
| TBYT Document Type (G8) | | CRW | |
| TBYT Marketing Authorization, TBYT Regulatory Document | CRW | CRW | PU, PM, SU, SM, STM, QM R |

### 6.6 Kế toán

| DocType | AU | AM | Khác |
|---|---|---|---|
| Journal Entry | CRW PE, S WF | CRWSXA PE O, WF | |
| Journal Entry Template | R | CRW | |
| Payment Entry | CRW PE, S WF | CRWSXA PE O, WF | AP (G2) |
| Payment Request | | R | không dùng cho đề nghị thanh toán nội bộ {D8} |
| Account | R | CRW O I | |
| Cost Center (G8), Accounting Dimension, Accounting Dimension Filter, Finance Book (G8), Monthly Distribution | R | CRW | PJM R |
| Cost Center Allocation | R | CRWSXA | |
| Budget | R | CRWSXA | |
| Fiscal Year (G8), Accounting Period | R | CRW | chỉ AM khóa kỳ |
| Period Closing Voucher | R | CRWSXA | |
| Company (G8) | R | RW | |
| Currency (G8), Currency Exchange | CRW | CRW | |
| Currency Exchange Settings (Single) | R | RW | |
| Mode of Payment, Payment Terms Template, Payment Term, Tax Category (G8); Item Tax Template, Tax Withholding Category, Tax Rule, Shipping Rule | R | CRW | |
| Bank, Bank Account Type, Bank Account Subtype | R | CRW | |
| Bank Account | CRW, WF | CRW, WF | PU, SU: không có quyền; H3 |
| Bank Guarantee | CRWS | CRWSXA | SM R; PM R (bảo lãnh dự thầu, thực hiện HĐ) |
| Bank Transaction | CRWS | CRWSXA | |
| Bank Statement Import | CRW | CRW | |
| Bank Reconciliation Tool, Bank Clearance, Payment Reconciliation (Single) | RW | RW | |
| Process Payment Reconciliation | CRWS | CRWSXA | |
| Process Payment Reconciliation Log (hệ thống sinh) | R | R | |
| Unreconcile Payment | | CRWSX | |
| Exchange Rate Revaluation | R | CRWSXA | |
| Process Statement Of Accounts | CRW | CRW | |
| Cheque Print Template | R | CRW | |
| Party Link | R | CRWD | |
| Repost Accounting Ledger, Repost Payment Ledger | | CRWSXA | |
| Ledger Merge; Chart of Accounts Importer, Opening Invoice Creation Tool (Single) | | CRW (Single: RW) | chỉ dùng khi go-live, theo phiếu |
| Repost Accounting Ledger Settings (Single) | | RW | |
| FS Note Qualitative Info | R | CRW | |
| GL Entry, Payment Ledger Entry, Advance Payment Ledger Entry, Account Closing Balance (hệ thống sinh) | R | R | |
| Debt Reconciliation Statement (đối chiếu công nợ 131/331) | CRW | CRWSXA | |
| Debt Reconciliation Settings (Single) | R | RW | |
| Fast EInvoice Document | EI CRW | EIC CRWD | phát hành, hủy do code kiểm tra role EIC |
| Fast EInvoice Log | EI R | EIC R | |
| Fast EInvoice Settings (Single) | EI R | EIC R | SYS RW |

Ghi chú:
- Đối chiếu công nợ 131/331 đầu mỗi tháng do AU lập trên Debt Reconciliation Statement, AM xác nhận (submit).
- Bán hàng và Mua hàng xem công nợ qua Accounts Receivable/Payable (Custom Role, 11.2), không cấp Read trên Payment Entry.
- **Bank Reconciliation Tool** có nút tạo Journal Entry và Payment Entry ngay trong công cụ. Các nút này submit chứng từ bằng quyền user, không đi qua workflow (`erpnext/accounts/doctype/bank_reconciliation_tool/bank_reconciliation_tool.py:271, 350`). Với H11 (11.3):
  - Payment Entry thu tiền hoặc chi ≤ H3 vẫn tạo được, vì khớp transition tự duyệt của AU;
  - Payment Entry chi > H3 và mọi Journal Entry bị chặn. Phải lập chứng từ thường, duyệt qua workflow, rồi đối soát với chứng từ đã ghi sổ {D23}.
- Quyền Fast EInvoice\* hiện do `erpnext/einvoice/setup.py` (`_grant_permissions`) tự cấp lại sau mỗi lần migrate. Bảng trên chép đúng quyền đó; xử lý xung đột theo C2.
- DocType kế toán không dùng: xem danh sách đầy đủ ở Phụ lục B.

### 6.7 Tài sản

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

### 6.8 CRM, Hợp đồng

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

### 6.9 Dự án

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

### 6.10 Hỗ trợ, Chất lượng

| DocType | Quyền |
|---|---|
| Issue | ST CRW (lọc theo Issue Type, mục 10); EMP CRW·o (gửi yêu cầu); CUS CRW·o |
| Issue Type, Issue Priority (G8), Service Level Agreement | SYS CRW |
| Support Settings (Single) | SYS RW |
| Non Conformance | STU CRW; QM CRWD; PU CRW (lỗi NCC); SU R |
| Quality Goal, Quality Procedure, Quality Review, Quality Action, Quality Meeting, Quality Feedback, Quality Feedback Template | QM CRW; STU R; PU R |

CUS dùng `·o` thay cho `[c]`, vì trường `customer` của Issue có thể trống và lọc bằng User Permission sẽ lộ Issue không gắn khách.

### 6.11 Thông báo cung ứng (module Supply Notification – Miyano)

| DocType | Quyền |
|---|---|
| Supply Notification Point, Supply Notification Recipient Group, Supply Notification Snippet | SNA CRWD; EMP R (thay dòng `All` R hiện có) |
| Supply Notification Opt Out | SNA CRWD |
| Supply Notification Settings (Single) | SNA RW; EMP R |
| Supply Notification Dispatch Log | SNA R |

`erpnext/supply_notification/setup.py` chạy sau mỗi lần migrate; xử lý theo C2 để không cấp lại quyền cho `All`.

### 6.12 Thiết lập, công cụ và module không dùng

| DocType | Quyền |
|---|---|
| MVL Approval Limits (Single, mới – hạn mức H1, H2, H3) {D17} | SYS RW (nhập theo văn bản BGĐ, H4 báo GĐVH); AM, VW R |
| Global Defaults, Domain Settings (Single) | SYS RW |
| Item Variant Settings (Single) | IM RW |
| Delivery Settings, Stock Reposting Settings (Single) | STM R; AM RW |
| Authorization Rule, Authorization Control | `g1_only`. Hạn mức duyệt chỉ đặt ở MVL Approval Limits; sync báo lỗi nếu có bản ghi Authorization Rule |
| Transaction Deletion Record | `g1_only` (SYS chỉ R). Công cụ xóa toàn bộ giao dịch, chỉ Administrator dùng trên site test |
| Rename Tool (Single) | SYS RW, theo kế hoạch |
| Email Digest | SYS CRW |
| Code List, Common Code (EDI) | SYS CRW |
| Settings của module đang dùng (Accounts, Stock, Selling, Buying, CRM, Projects, Support, HR, Payroll…) | Quyền RW theo cột "Ai ghi" ở 11.5; R cho EMP với 4 Single ở G8 |
| DocType không dùng | `g1_only`, danh sách đầy đủ ở **Phụ lục B**. Blanket Order nằm trong module Manufacturing nhưng **được dùng** (6.1). Ẩn workspace của các module không dùng |

---

## 7. HRMS

Mọi ô `[e]`, `[d]` trong mục này được thực thi bằng hook H8.

### 7.1 Hồ sơ, tổ chức, vòng đời

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

### 7.2 Chấm công, ca, nghỉ phép

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
| Leave Policy | R | | CRW | CRWSXA |
| Leave Policy Assignment | R[e] | | CRWS | CRWSXA |
| Leave Allocation | R[e] | R[d] | CRW | CRWSXA |
| Leave Application | CRW R1 [e] | RWS W1 [d] WF | CRW R1 (nhập hộ, D6) | RWSXA W1 P WF |
| Compensatory Leave Request | CRW[e] | RW[d] WF | R | RWSXA WF |
| Leave Encashment | R[e] | | CRW | CRWSXA |
| Leave Ledger Entry (hệ thống sinh) | R[e] | R[d] | R | R |
| Shift Assignment Tool, Employee Attendance Tool, Upload Attendance, Leave Control Panel (Single – công cụ tạo hàng loạt) | | | RW | RW |
| Work Calendar Settings (Single, fork) | | | R | RW |

- **EMP không có S** trên Leave Application, Attendance Request, Compensatory Leave Request, Shift Request:
  - HRMS chỉ cho submit Leave Application và Shift Request khi đơn đã Approved/Rejected;
  - submit Attendance Request tạo chấm công ngay;
  - submit Compensatory Leave Request tự cấp thêm ngày phép.

  Cho EMP quyền S nghĩa là cho nhân viên tự duyệt.
- **DH có S trên Leave Application và Shift Request** chỉ để thực hiện transition Từ chối (submit với `status = Rejected`, WF-LA). HRMS còn tự share quyền Submit cho người duyệt ghi trên đơn (`hrms/hr/utils.py:694`), nên workflow và H11 là chốt chặn thực sự.
- Bảng công tháng do HU lập, HM chốt (submit). DH chỉ xem; muốn sửa thì đề nghị qua Attendance Request.

### 7.3 Chi phí, tạm ứng

| DocType | EMP | DH | AU | AM | Khác |
|---|---|---|---|---|---|
| Expense Claim | CRW R1 [e] | RW R1 [d] WF | R R1 | RWSXA W1 WF | HM R R1; AP W1 (G2) |
| Employee Advance | CRW[e] | RW[d] WF | R | RWSXA WF | AP (G2) |
| Expense Invoice (fork – hóa đơn đính kèm Expense Claim) | CRW·o | | RW | CRW | HM R |
| Expense Claim Type (G8) | | | R | CRW | HM CRW |

Sau khi chứng từ được duyệt, AU chi tiền bằng Payment Entry (6.6). "Đề nghị thanh toán" của nhân viên được thực hiện bằng Expense Claim và Employee Advance {D8}. Expense Invoice không có trường Employee nên EMP dùng `·o`.

### 7.4 Tuyển dụng, đào tạo, hiệu suất

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

### 7.5 Lương, thuế, phúc lợi

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

### 7.6 HRMS không dùng

Travel Request (dùng Business Trip thay, D13), Daily Work Summary, Daily Work Summary Group, Vehicle Log, Vehicle Service Item: `g1_only`.

---

## 8. Frappe – hệ thống

| DocType | Quyền |
|---|---|
| User | SYS CRW **W1** (không D; nghỉ việc = Enabled 0); `Desk User` L (dòng chuẩn, G10). Mỗi user tự sửa hồ sơ của mình theo mặc định frappe. 18 trường level 1 của User (`roles`, `role_profile_name`, `block_modules`, `api_key`…) chỉ SYS ghi (11.1) |
| Role Profile | SYS CRWD **W1** (`roles` ở level 1), chỉ thay đổi qua lệnh sync |
| Role, Module Profile, Custom DocPerm, User Permission, Custom Role, Role Permission for Page and Report | SYS CRWD, chỉ thay đổi qua lệnh sync (mục 12). Không role nào khác có quyền Set User Permissions |
| DocType, Customize Form, Custom Field, Property Setter, Client Script, Server Script, Print Format, Print Format Field Template, Print Style, Workflow, Workflow State, Workflow Action Master, Notification, Assignment Rule, Auto Email Report, Webhook, Email Account, Email Domain, Email Rule, System Settings, Security Settings, Print Settings, Network Printer Settings, Document Naming Settings, Document Naming Rule, Scheduled Job Type, Scheduler Event, Log Settings, OAuth Client, OAuth Provider Settings, Connected App, Social Login Key, LDAP Settings, Translation, User Group, User Type, Navbar Settings, Session Default Settings, Global Search Settings | SYS. Trên production chỉ thay đổi qua app và deploy. DEV R |
| Letter Head (G8), Email Template | SYS CRW; AM, HM, SM, PM R |
| Report (Report Builder lưu dùng chung) | SYS CRW |
| Prepared Report | SYS CRWD; PRU R |
| Auto Repeat | AM CRW; SYS R (Auto Repeat tự sinh hóa đơn, bút toán) |
| Data Import, Data Import Log | Role có `I` ở mục 6–7: CRW·o; SYS CRWD. "Submit After Import" bị H11 chặn với DocType có workflow |
| Data Export, Bulk Update (Single) | SYS |
| Deleted Document | SYS R; chỉ SYS khôi phục, theo phiếu |
| Version, Access Log, Activity Log, View Log, Audit Trail | SYS R; VW R |
| Permission Inspector (Single) | SYS |
| Error Log, Scheduled Job Log, RQ Job, RQ Worker, Submission Queue, Integration Request, Webhook Request Log, Email Queue, Unhandled Email | SYS R; DEV R |
| DocShare, Document Share Key | SYS R |
| Dashboard, Dashboard Chart, Dashboard Chart Source, Number Card, Custom HTML Block | SYS và WSM CRW; người dùng R theo Roles của từng bản ghi; giữ dòng chuẩn `Desk User` (G10) |
| Workspace | SYS và WSM CRW; giữ dòng chuẩn `Desk User` CRWD (G10). Frappe chỉ cho Workspace Manager sửa workspace công khai, nên người dùng chỉ tạo, sửa, xóa được workspace riêng tư của mình |
| Page | Roles của từng Page ghi bằng Custom Role theo bảng 11.8 |
| Web Page View | SYS R; WM R (báo cáo Website Analytics) |
| Web Page, Blog Post, Blog Category, Web Form, Help Article, Help Category, Web Template, Website Slideshow | MK CRW (trường `published` ở level 1, chỉ WM ghi); WM CRWD W1 |
| Website Settings, Portal Settings, Website Theme, Website Script, About Us Settings, Contact Us Settings, Blog Settings, Website Sidebar, Website Route Meta, Color | WM CRW |
| Email Group, Email Group Member, Newsletter | NL CRW (gửi); MK CRW (Newsletter: R); SM R |
| Country, Salutation, Gender, Address Template (G8) | SYS CRW |
| **`keep_standard`:** ToDo, Note, Event, File, Comment, Communication, Kanban Board, Workflow Action, Notification Log, Notification Settings, Document Follow, Tag, Tag Link, Reminder, Route History, List Filter, List View Settings, Calendar View, PWA Notification (hrms), Dynamic Link | Quyền theo owner, người được giao hoặc tài liệu gốc. Sync không thêm quyền nghiệp vụ; xử lý dòng Custom DocPerm đang có theo mục 12, bước 3.2 |
| Các DocType còn lại của frappe | `g1_only` cộng dòng chuẩn của `All` / `Desk User` (G10); danh sách đầy đủ ở Phụ lục B |

---

## 9. Workflow

### 9.1 Nguyên tắc duyệt

1. **Tách nhiệm (G11).** Transition xuất phát từ trạng thái "Chờ …" luôn có điều kiện người duyệt ≠ người lập (và ≠ chính nhân viên với chứng từ HR). H10 chặn một người duyệt hai bước trên cùng chứng từ. HRMS **bỏ qua** thiết lập Prevent Self Leave/Expense Approval khi DocType có workflow (`leave_application.py`, `expense_claim.py`: điều kiện `not get_workflow_name(...)`), nên điều kiện workflow là chốt chặn duy nhất.
2. **Cấp duyệt thay.** Trưởng bộ phận hoặc KTT tự lập chứng từ thì chứng từ vẫn đi đúng luồng; ở bước của chính họ, GĐVH duyệt thay (có mọi role Manager). Khi GĐVH đã duyệt một bước, bước BGĐ kế tiếp do BGD-GD duyệt (H10). Không có luồng riêng cho chứng từ tự lập {D20}.
3. **Hạn mức** H1, H2, H3 đọc từ Single `MVL Approval Limits` (trường `h1`, `h2`, `h3`) bằng `frappe.db.get_value("MVL Approval Limits", None, "h1")` {D1}. Không dùng Authorization Rule để tránh hai cơ chế hạn mức.
4. **Người duyệt HR** lấy từ trường trên đơn, theo đúng logic có sẵn của hrms và fork để người được Assign To cũng là người bấm duyệt:
   - Leave Application: `leave_approver`;
   - Expense Claim: `expense_approver`;
   - Shift Request: `approver`;
   - Attendance Request: `custom_approver` (fork tự điền = user của `reports_to` và Assign To cho người này);
   - Business Trip: `approver_coo`;
   - Compensatory Leave Request, Employee Advance (không có trường người duyệt): `leave_approver` / `expense_approver` của Employee.

   Các trường `leave_approver`, `expense_approver`, `reports_to` trên Employee bắt buộc (11.7). Người duyệt của trưởng bộ phận là BGD-GD hoặc GĐVH (cả hai có TBP). Đơn của HM ở bước HCNS và đơn của AM ở bước KTT do GĐVH duyệt.
5. **Thông báo.** Mọi workflow đặt `send_email_alert = 1`. Để trống `leave_approval_notification_template` và `expense_approval_notification_template` trong HR Settings, để không gửi trùng email; có thể giữ `leave_status_notification_template` để báo kết quả cho nhân viên.
6. **Cancel và Amend** do role có X/A theo ma trận thực hiện bằng nút chuẩn, không qua transition. Frappe tự chuyển state sang Đã hủy (9.2, quy tắc 4).
7. Điều kiện workflow chỉ dùng được `doc`, `frappe.session.user`, `frappe.db.get_value`, `frappe.db.get_list` và vài hàm ngày giờ (`frappe/model/workflow.py`, `get_workflow_safe_globals`).

### 9.2 Quy tắc kỹ thuật – không đè `status` có sẵn, không bị vòng qua

Đã kiểm chứng trên frappe v15 ngày 23/10/2026. Sync kiểm tra quy tắc 1–4 và dừng nếu vi phạm.

1. **Trường trạng thái.** `workflow_state_field` luôn là `workflow_state`. Frappe tự tạo Custom Field kiểu Link, ẩn, `allow_on_submit = 1`, `no_copy = 1` (`frappe/workflow/doctype/workflow/workflow.py:52`). **Không dùng `status`.** Sales Order và Payment Entry đã có sẵn field này; dùng lại.
2. **Update Field** chỉ dùng cho 3 trường người duyệt được phép đặt: Leave Application `status`, Shift Request `status`, Expense Claim `approval_status`. Leave Application `status` và Expense Claim `approval_status` ở perm level 1, nên role thực hiện transition phải có W1 (11.1). Shift Request `status` ở level 0. **Cấm** Update Field vào `status` do controller tự tính: Sales Order, Purchase Order, Sales/Purchase Invoice, Payment Entry, Payroll Entry, Expense Claim `status`, Employee Advance `status`, Material Request. Không động vào Job Offer `status` (phản hồi của ứng viên).
3. **Hiển thị.** Đặt `override_status = 1` ("Don't Override Status") cho mọi workflow, và thêm cột `workflow_state` vào list view. Nếu để 0 như hai workflow hiện có, list view và form hiện `workflow_state` thay cho chỉ báo của controller (To Deliver and Bill, Overdue, Paid…) (`frappe/public/js/frappe/model/indicator.js:35`).
4. **Thứ tự và loại state.** Frappe dùng **state đầu tiên** có `doc_status` tương ứng khi điền trạng thái cho chứng từ cũ (`update_default_workflow_status`) và khi chứng từ được submit/cancel không qua transition (`set_workflow_state_on_action`, `frappe/model/workflow.py:362`). Vì vậy trong mỗi workflow:
   - state đầu tiên có `doc_status 0` là **Nháp**;
   - state đầu tiên có `doc_status 1` là trạng thái **duyệt/ghi sổ bình thường**, không được là Từ chối;
   - có state **Đã hủy** (`doc_status 2`) và không transition nào dẫn vào nó. Khi đó nút Cancel chuẩn vẫn hiện (`can_cancel_document`) và frappe tự gán Đã hủy khi hủy.
5. **Submit vòng qua workflow.** Giao diện ẩn nút Submit/Cancel và thao tác hàng loạt khi có workflow, nhưng **server không chặn**. `frappe.client.submit`, `set_value` với `docstatus = 1`, Data Import "Submit After Import" và code `doc.submit()` đều qua được `validate_workflow` (state không đổi thì không kiểm tra transition), sau đó frappe gán state `doc_status 1` đầu tiên. **H11 bắt buộc.** Submit thẳng chỉ được cho qua trong hai trường hợp:
   - user có một transition tự duyệt (từ Nháp tới state `doc_status 1`) mà điều kiện đúng với chứng từ – ví dụ AU submit Payment Entry ≤ H3 qua API hoặc qua Bank Reconciliation Tool;
   - chứng từ hệ thống sinh với `ignore_permissions` (bút toán lương, khấu hao, đánh giá tỷ giá – T24).

   Mọi trường hợp khác bị chặn.
6. **`allow_edit` theo loại state:**

   | Loại state | `allow_edit` |
   |---|---|
   | Nháp, Từ chối | role người lập (cột "Lập" ở 9.3) |
   | Chờ … | **LK** (MVL Khóa sửa – không ai có). Nội dung bị khóa khi chờ duyệt; muốn sửa thì người duyệt trả về bằng Từ chối |
   | Đã duyệt / Đã ghi sổ (`doc_status 1`) | role quản lý chứng từ (cột "Sau submit" ở 9.3) – chỉ sửa được trường cho phép sau submit |
   | Đã hủy | LK |

   Frappe chỉ khóa form phía client theo `allow_edit`; **H5 bắt buộc** để chặn ở server. Transition không cần `allow_edit`: người duyệt chỉ cần role của transition và W/S trong DocPerm.
7. **App PWA của HRMS** (`/hrms`) tự dùng nút của workflow khi DocType có workflow (`hrms/frontend/src/components/RequestActionSheet.vue:77`); không cần cấu hình thêm.

### 9.3 Đặc tả workflow

Quy ước:
- `(0)` `(1)` `(2)` là `doc_status`.
- Thứ tự state trong mỗi workflow đúng như liệt kê.
- Mọi transition từ "Chờ …" ngầm có điều kiện G11.
- Mọi workflow có transition **Mở lại**: Từ chối → Nháp, do role người lập thực hiện (nếu Từ chối có `doc_status 0`).
- Hạn mức `H1/H2/H3` viết tắt cho `frappe.db.get_value("MVL Approval Limits", None, "h1")`…

| Mã | DocType | States (theo thứ tự) | Lập | Sau submit |
|---|---|---|---|---|
| WF-PO | Purchase Order | Nháp(0), Chờ TP(0), Chờ BGĐ(0), Đã duyệt(1), Từ chối(0), Đã hủy(2) | PU | PM |
| WF-SO | Sales Order | Nháp(0), Chờ KD-TP(0), Đã duyệt(1), Từ chối(0), Đã hủy(2) | SU | SM |
| WF-SI | Sales Invoice | Nháp(0), Chờ KTT(0), Đã ghi sổ(1), Từ chối(0), Đã hủy(2) | AU | AM |
| WF-PI | Purchase Invoice | như WF-SI | AU | AM |
| WF-PE | Payment Entry | Nháp(0), Chờ KTT(0), Chờ BGĐ(0), Đã ghi sổ(1), Từ chối(0), Đã hủy(2) | AU | AM |
| WF-JE | Journal Entry | Nháp(0), Chờ KTT(0), Đã ghi sổ(1), Từ chối(0), Đã hủy(2) | AU | AM |
| WF-SE | Stock Entry | Nháp(0), Chờ trưởng kho(0), Đã ghi sổ(1), Từ chối(0), Đã hủy(2) | STU, PDA | STM |
| WF-SR | Stock Reconciliation | Nháp(0), Chờ trưởng kho(0), Chờ KTT(0), Đã ghi sổ(1), Từ chối(0), Đã hủy(2) | STU, PDA | STM |
| WF-BA | Bank Account (không submittable) | Nháp(0), Chờ KTT(0), Đã duyệt(0), Từ chối(0) | AU | – (Đã duyệt: `allow_edit` = LK) |
| WF-LA | Leave Application, Shift Request | Nháp(0), Chờ TBP(0), Chờ HCNS(0), Đã duyệt(1), Từ chối(1), Đã hủy(2) | EMP, HU | HM |
| WF-AR | Attendance Request, Compensatory Leave Request | Nháp(0), Chờ TBP(0), Chờ HCNS(0), Đã duyệt(1), Từ chối(0), Đã hủy(2) | EMP | HM |
| WF-EC | Expense Claim, Employee Advance | Nháp(0), Chờ TBP(0), Chờ KTT(0), Chờ BGĐ(0), Đã duyệt(1), Từ chối(0), Đã hủy(2) | EMP | AM |
| WF-PAY | Payroll Entry | Nháp(0), Chờ BGĐ(0), Đã duyệt(1), Từ chối(0), Đã hủy(2) | HM | HM |
| WF-HR | Salary Structure Assignment, Employee Promotion, Employee Transfer, Job Offer | Nháp(0), Chờ BGĐ(0), Đã duyệt(1), Từ chối(0), Đã hủy(2) | HM | HM |
| WF-BT | Business Trip | Nháp(0), Chờ COO duyệt(0), COO đã duyệt(1), Đã ra QĐ(1), Hoàn tất(1), Từ chối(0) – **giữ đúng tên state hiện có** (ghi chú 5) | HU | HM |

**Transition:**

| Workflow | Từ | Hành động | Đến | Role | Điều kiện (ngoài G11) |
|---|---|---|---|---|---|
| WF-PO | Nháp | Duyệt | Đã duyệt | PU | `doc.base_grand_total <= H1` (tự duyệt trong hạn mức) |
| | Nháp | Gửi duyệt | Chờ TP | PU | `doc.base_grand_total > H1` |
| | Chờ TP | Duyệt | Đã duyệt | PM | `doc.base_grand_total <= H2` |
| | Chờ TP | Duyệt | Chờ BGĐ | PM | `doc.base_grand_total > H2` |
| | Chờ BGĐ | Duyệt | Đã duyệt | AP | |
| | Chờ TP / Chờ BGĐ | Từ chối | Từ chối | PM / AP | |
| WF-SO | Nháp | Duyệt | Đã duyệt | SU | `doc.mvl_dung_gia_hd == 1` – cờ do H2 tính {D4} |
| | Nháp | Gửi duyệt | Chờ KD-TP | SU | `doc.mvl_dung_gia_hd != 1` |
| | Chờ KD-TP | Duyệt / Từ chối | Đã duyệt / Từ chối | SM | |
| WF-SI, WF-PI | Nháp | Ghi sổ | Đã ghi sổ | AU | `doc.is_return == 0` |
| | Nháp | Gửi duyệt | Chờ KTT | AU | `doc.is_return == 1` |
| | Chờ KTT | Duyệt / Từ chối | Đã ghi sổ / Từ chối | AM | |
| WF-PE | Nháp | Ghi sổ | Đã ghi sổ | AU | `doc.payment_type == "Receive" or doc.base_paid_amount <= H3` |
| | Nháp | Gửi duyệt | Chờ KTT | AU | `doc.payment_type != "Receive" and doc.base_paid_amount > H3` |
| | Chờ KTT | Duyệt | Chờ BGĐ | AM | |
| | Chờ BGĐ | Duyệt | Đã ghi sổ | AP | |
| | Chờ KTT / Chờ BGĐ | Từ chối | Từ chối | AM / AP | |
| WF-JE | Nháp | Gửi duyệt | Chờ KTT | AU | |
| | Chờ KTT | Duyệt / Từ chối | Đã ghi sổ / Từ chối | AM | |
| WF-SE | Nháp | Ghi sổ | Đã ghi sổ | STU; PDA | `doc.stock_entry_type == "Material Transfer"` |
| | Nháp | Gửi duyệt | Chờ trưởng kho | STU; PDA | `doc.stock_entry_type != "Material Transfer"` |
| | Chờ trưởng kho | Duyệt / Từ chối | Đã ghi sổ / Từ chối | STM | |
| WF-SR | Nháp | Gửi duyệt | Chờ trưởng kho | STU; PDA | |
| | Chờ trưởng kho | Duyệt | Đã ghi sổ | STM | `doc.difference_amount == 0` |
| | Chờ trưởng kho | Duyệt | Chờ KTT | STM | `doc.difference_amount != 0` |
| | Chờ KTT | Duyệt | Đã ghi sổ | AM | |
| | Chờ trưởng kho / Chờ KTT | Từ chối | Từ chối | STM / AM | |
| WF-BA | Nháp | Gửi duyệt | Chờ KTT | AU | |
| | Chờ KTT | Duyệt / Từ chối | Đã duyệt / Từ chối | AM | |
| | Đã duyệt | Sửa | Nháp | AU; AM | Muốn đổi số tài khoản, IBAN, đối tượng thì phải đưa về Nháp và duyệt lại; trong lúc đó H3 chặn dùng tài khoản |
| WF-LA | Nháp | Gửi duyệt | Chờ TBP | EMP; HU | |
| | Chờ TBP | Duyệt | Chờ HCNS | DH | `doc.leave_approver == frappe.session.user` (Shift Request: `doc.approver`) |
| | Chờ TBP | Từ chối | Từ chối – Update `status = Rejected` | DH | như trên |
| | Chờ HCNS | Duyệt | Đã duyệt – Update `status = Approved` | HM | |
| | Chờ HCNS | Từ chối | Từ chối – Update `status = Rejected` | HM | |
| WF-AR | Nháp | Gửi duyệt | Chờ TBP | EMP | |
| | Chờ TBP | Duyệt / Từ chối | Chờ HCNS / Từ chối | DH | Attendance Request: `doc.custom_approver == frappe.session.user` (khớp `guard_submit` và Assign To của fork); Compensatory Leave Request: `frappe.db.get_value("Employee", doc.employee, "leave_approver") == frappe.session.user` |
| | Chờ HCNS | Duyệt / Từ chối | Đã duyệt / Từ chối | HM | |
| WF-EC | Nháp | Gửi duyệt | Chờ TBP | EMP | |
| | Chờ TBP | Duyệt / Từ chối | Chờ KTT / Từ chối | DH | Expense Claim: `doc.expense_approver == frappe.session.user`; Employee Advance: `frappe.db.get_value("Employee", doc.employee, "expense_approver") == frappe.session.user` |
| | Chờ KTT | Duyệt | Đã duyệt | AM | Expense Claim: `doc.grand_total <= H3`; Employee Advance: `doc.advance_amount <= H3` |
| | Chờ KTT | Duyệt | Chờ BGĐ | AM | vượt H3 {D2} |
| | Chờ BGĐ | Duyệt | Đã duyệt | AP | |
| | Chờ KTT / Chờ BGĐ | Từ chối | Từ chối | AM / AP | |
| WF-PAY | Nháp | Gửi duyệt | Chờ BGĐ | HM | |
| | Chờ BGĐ | Duyệt / Từ chối | Đã duyệt / Từ chối | AP | |
| WF-HR | Nháp | Gửi duyệt | Chờ BGĐ | HM | |
| | Chờ BGĐ | Duyệt / Từ chối | Đã duyệt / Từ chối | AP | |
| WF-BT | Nháp | Gửi duyệt | Chờ COO duyệt | HU | |
| | Chờ COO duyệt | Duyệt / Từ chối | COO đã duyệt / Từ chối | AP | `doc.approver_coo == frappe.session.user` |
| | COO đã duyệt | Ra QĐ | Đã ra QĐ | HM | |
| | Đã ra QĐ | Hoàn tất | Hoàn tất | HM | |

Ghi chú:
1. **Expense Claim:** state Đã duyệt có Update Field `approval_status = Approved`; Employee Advance không có trường này. `status` của cả hai do hrms tự tính (Unpaid → Paid…), không đặt bằng workflow.
2. **Leave Application, Shift Request:** Từ chối là `doc_status 1` (hrms chỉ cho submit đơn ở trạng thái Approved/Rejected), nên DH và HM cần S, thêm W1 trên Leave Application. Ở các DocType HR còn lại, Từ chối là `doc_status 0`.
3. **Attendance Request:** `guard_submit` của fork chỉ cho `custom_approver` hoặc role bypass submit. Bước cuối của WF-AR do HM thực hiện, nên HM phải nằm trong `APPROVER_BYPASS_ROLES` sau khi sửa C5 (chỉ còn HR Manager).
4. **WF-PAY:** sau Đã duyệt, HM bấm Submit Salary Slip; AU bấm Make Bank Entry.
5. **WF-BT – Business Trip:**
   - `workflow_state` là trường Select với danh sách tên state cố định trong JSON của fork hrms, và đã có 4 bản ghi ở COO đã duyệt / Đã ra QĐ. Đổi tên state sẽ làm lưu phiếu báo lỗi Select.
   - Chưa có state Đã hủy vì danh sách Select chưa có giá trị này. Thêm "Đã hủy" và đặt `no_copy = 1` là việc của C6.
   - Chỉ đổi role: COO → AP; bỏ System Manager và AssetCore Super Admin khỏi mọi transition.
6. **WF-JE:** JE do hệ thống sinh không đi qua transition. H11 cho qua khi có `ignore_permissions`, và frappe gán Đã ghi sổ. Nếu nguồn sinh JE nào không đặt `ignore_permissions` (kiểm bằng T24), thêm điều kiện loại trừ theo `voucher_type` vào H11, không nới lỏng workflow.

### 9.4 Workflow đang có trên site

Frappe chỉ chạy một workflow đang bật cho mỗi DocType.

| Workflow hiện có | DocType | Xử lý |
|---|---|---|
| MVL Duyệt thanh toán (role Kế toán tổng hợp, Kế toán trưởng) | Payment Entry | Tắt và thay bằng WF-PE |
| SO Test Workflow (role Test Approver, All) | Sales Order | Xóa; thay bằng WF-SO |
| Cong Tac Approval | Business Trip | **Sửa tại chỗ thành WF-BT, không xóa.** `hrms.setup_vn_defaults.ensure_defaults` (gọi `hrms/patches/v15_0/setup_cong_tac_workflow.py` mỗi lần migrate) tạo lại bản cũ nếu workflow hoặc role COO không còn. Sửa code fork hrms theo C6 |
| 22 workflow IMM-\* và AC Asset Lifecycle | DocType assetcore | Không đụng tới |

---

## 10. User Permission

**Không dùng User Permission để giới hạn hồ sơ nhân sự theo nhân viên hoặc bộ phận.** User Permission áp cho **user**, không cho role. Một user có cả EMP và AU/HU/AM thì hoặc bị khóa luôn phần dữ liệu nghiệp vụ, hoặc (nếu được loại trừ) quyền CRW của EMP mở ra cho mọi nhân viên. Phạm vi `[e]`, `[d]` do H8 thực thi theo từng role.

| Đối tượng | Áp cho | Cấu hình |
|---|---|---|
| Warehouse | STU, PDA | Kho được giao. Apply To All = 0; Applicable For: Stock Entry, Stock Reconciliation, Purchase Receipt, Delivery Note, Pick List, Material Request, Stock Ledger Entry, Bin, Batch Entry, Location Transfer, Location Balance, Location Ledger Entry |
| Stock Entry Type | PDA | Material Transfer (và loại cấp phát khác nếu cần); Applicable For: Stock Entry |
| Price List | PU: bảng giá mua; SU: bảng giá bán | Applicable For: Item Price (không Apply To All) |
| Customer | CUS bắt buộc (= chính khách hàng); SU tùy chọn khi KD-TP yêu cầu phân vùng | Apply To All = 1. Với SU: không lọc được Quotation, Opportunity (Dynamic Link) |
| Supplier | SUP bắt buộc (= chính NCC) | Apply To All = 1 |
| Issue Type | ST: KD → Khách hàng; IT-QT → IT nội bộ; NS-NV → Hành chính | Applicable For: Issue; `Issue.issue_type` bắt buộc (11.7) |
| Employee, Department | Không dùng – thay bằng H8 | |
| Company | Không dùng (Miyano có 1 Company) | |

Ghi chú:
- **Apply Strict User Permissions = 0** {D11}. Frappe ghép điều kiện của mọi trường Link cùng loại bằng AND (`frappe/model/db_query.py:1087`), và khi bật Strict, bản ghi có trường Link trống bị ẩn. Ví dụ SU mất mọi Customer chưa đặt `default_price_list`; STU mất Stock Entry Material Receipt (`from_warehouse` trống). Với Strict = 0, mọi DocType mà CUS/SUP có quyền đều có trường Customer/Supplier bắt buộc, nên không lộ dữ liệu; Issue dùng `·o`.
- User Permission Warehouse chỉ lọc danh sách theo trường kho ở đầu phiếu; khi mở phiếu, frappe kiểm tra cả trường kho trên các dòng. Phiếu chuyển giữa kho của STU và kho khác do người được giao cả hai kho hoặc STM lập.
- Mọi Employee có `create_user_permission = 0` (11.7). Sync xóa User Permission Employee/Department/Company còn sót do HRMS tự tạo.

---

## 11. Cấu hình bổ trợ

### 11.1 Trường perm level

**Trường Miyano đặt thêm** (Property Setter):

| DocType | Trường | Level | Đọc | Ghi |
|---|---|---|---|---|
| Item | `valuation_rate` | 1 | AM | AM |
| Item (bảng Item Default) | `expense_account`, `income_account`, `buying_cost_center`, `selling_cost_center` | 2 | AU, AM | AM |
| Customer | `credit_limits` | 1 | SM, AU, AM | AM |
| Customer, Supplier | `accounts`, `tax_category`, `tax_withholding_category` | 2 | AU, AM, SM (Customer), PM (Supplier) | AU, AM |
| Warehouse | `account` | 2 | AU, AM | AM |
| Stock Ledger Entry | `incoming_rate`, `outgoing_rate`, `valuation_rate`, `stock_value`, `stock_value_difference` | 1 | AM, VW | – |
| Bin | `valuation_rate`, `stock_value` | 1 | AM, VW | – |
| Employee | `ctc`, `salary_currency`, `salary_mode`, `bank_name`, `bank_ac_no`, `iban` | 1 | HM, AM | HM |
| Salary Component, Salary Structure, Salary Structure Assignment, Salary Slip, Additional Salary, Employee Incentive, Retention Bonus, Gratuity, Full and Final Statement, Employee Promotion (`revised_ctc`) | mọi trường tiền và bảng earnings/deductions | 1 | HM, AM, VW, AP; EMP (Salary Slip của mình) | HM |
| Web Page, Blog Post | `published` | 1 | MK, WM | WM |

**Trường đã ở perm level 1 sẵn – frappe** (giữ nguyên level, chỉ khai báo quyền):

| DocType | Trường | Đọc | Ghi |
|---|---|---|---|
| User | 18 trường: `roles`, `role_profile_name`, `block_modules`, `sb_allow_modules`, `modules_html`, `user_type`, `api_key`, `api_secret`, `generate_keys`, `restrict_ip`, `login_after`, `login_before`, `third_party_authentication`, `user_emails`, `reset_password_key`, `last_reset_password_key_generated_on`, `sb1`, `sb2` | SYS | SYS |
| Role Profile | `roles` | SYS | SYS |

**Trường đã ở perm level 1 sẵn – erpnext, hrms** (phải cấp lại vì Custom DocPerm thay thế dòng level 1 chuẩn, kể cả `All` R1):

| DocType | Trường | Đọc | Ghi | Lý do |
|---|---|---|---|---|
| Leave Application | `status` | EMP, HU, VW | DH, HM | WF-LA đặt `status`. Thiếu W1 thì frappe trả về Open và submit báo lỗi |
| Expense Claim | `approval_status` | EMP, DH, AU, HM, VW | AM, AP | WF-EC đặt `approval_status = Approved` ở bước cuối |
| Employee Referral | `status` | EMP | HU, HM | |
| Employee Checkin | `time` | EMP, DH | HU, HM | Nhân viên không sửa giờ chấm |
| Quotation, Sales Order | `ignore_pricing_rule` | – | SM | Bỏ qua quy tắc giá – cùng tinh thần H2 |
| Supplier Quotation, Purchase Order | `ignore_pricing_rule` | – | PM | |
| Delivery Note, Purchase Receipt, Purchase Invoice | `ignore_pricing_rule` | không ai | không ai | Lấy theo chứng từ gốc |
| Timesheet; bảng Timesheet Detail (`costing_rate`, `costing_amount`, `billing_rate`, `billing_amount`, `billing_hours`) | `billing_details` và các trường tiền | AM | PJM | Giá vốn nhân công |
| POS Invoice, Voice Call Settings | `ignore_pricing_rule`, `user` | không ai | không ai | Không dùng |

Ghi chú:
- Không đặt perm level cho `rate` / `discount` trên dòng chứng từ. Với bản ghi mới, Frappe reset trường người dùng không có quyền ghi về giá trị mặc định, nên đơn giá bị xóa. Kiểm soát giá bằng H2. Stock Ledger Entry và Bin chỉ do hệ thống ghi nên đặt perm level an toàn.
- Không đặt perm level cho trường tiền mà chính nhân viên phải nhập (Employee Benefit Application/Claim, Employee Other Income, Employee Tax Exemption Declaration/Proof Submission). HU và DH vốn không có quyền trên các DocType này.
- Perm level trên trường của bảng con được cấp qua DocPerm level 1/2 của DocType cha.

### 11.2 Custom Role trên Report

Query Report và Script Report **bỏ qua perm level và H8**, và nhiều report chuẩn đang mở cho role rộng hơn ma trận. Ví dụ đo trên site: MVL Salary Register mở cho HR User và System Manager; Item Prices và Warehouse Wise Stock Balance mở cho Stock User; Unpaid Expense Claim mở cho Expense Approver.

Vì vậy áp **danh sách cho phép**:
- **R1.** Mọi Report của 3 app mặc định nhận Custom Role = **LK** (không ai mở được, trừ Administrator). Report mới phát sinh sau này cũng mặc định khóa; sync liệt kê các report đang khóa để rà.
- **R2.** Chỉ report trong bảng dưới được mở cho các role ghi kèm. Ghi bằng **Custom Role** (Role Permission for Page and Report), vì bảng Roles của Report chuẩn bị ghi đè khi migrate.
- **R3.** Theo G7, mọi role trong cột Roles phải có R trên `ref_doctype`; sync kiểm tra và dừng nếu thiếu.

| Nhóm | Report | ref_doctype | Roles |
|---|---|---|---|
| Lương, thuế TNCN | Salary Register, MVL Salary Register, Income Tax Deductions, Income Tax Computation, Salary Payments Based On Payment Mode, Salary Payments via ECS, Provident Fund Deductions, Professional Tax Deductions | Salary Slip | HM, AM, VW |
| Lương, thuế TNCN | Bank Remittance | Payroll Entry | HM, AM, VW |
| Lương, thuế TNCN | Quyet Toan TNCN | GL Entry | AM, VW |
| Giá vốn, giá trị tồn {D10} | Stock Balance (prepared report – thêm PRU), Stock Ledger, Stock and Account Value Comparison, Warehouse wise Item Balance Age and Value, Warehouse Wise Stock Balance, Item Prices, Supplier-Wise Sales Analytics, Incorrect Stock Value Report, Incorrect Serial No Valuation, Incorrect Balance Qty After Transaction, FIFO Queue vs Qty After Transaction Comparison, Stock Ledger Invariant Check, Stock Ledger Variance | Stock Ledger Entry | AM, VW |
| Giá vốn, giá trị tồn {D10} | Stock Ageing, Item Price Stock | Item | AM, VW (Item Price Stock thêm SM, PM) |
| Giá vốn, giá trị tồn {D10} | Stock Analytics | Stock Entry | AM, VW |
| Giá vốn, lợi nhuận | Gross Profit | Sales Invoice | AM, VW |
| Giá vốn, lợi nhuận | COGS By Item Group, Gross and Net Profit Report, Profitability Analysis | GL Entry | AM, VW |
| Tồn kho số lượng | Stock Projected Qty, Itemwise Recommended Reorder Level, Stock Qty vs Serial No Count, Item Variant Details | Item | STU, STM, PU, PM, SU, SM, AU, AM, VW |
| Tồn kho số lượng | Batch-Wise Balance History, Batch Item Expiry Status, Available Batch Report, Available Serial No, Serial No Ledger, Product Bundle Balance | Stock Ledger Entry | STU, STM, PU, PM, SU, SM, AU, AM, VW |
| Tồn kho số lượng | Item Balance (Simple), Item Shortage Report | Bin | STU, STM, PU, PM, SU, SM, AU, AM, VW |
| Tồn kho số lượng | Serial No Status, Serial No Warranty Expiry, Serial No Service Contract Expiry | Serial No | STU, STM, PU, PM, SU, SM, AU, AM, VW |
| Tồn kho số lượng | Serial and Batch Summary, Incorrect Serial and Batch Bundle | Serial and Batch Bundle | STU, STM, AM, VW |
| Tồn kho số lượng | Total Stock Summary, Requested Items To Be Transferred | Stock Entry | STU, STM, PU, PM, AU, AM, VW |
| Tồn kho số lượng | Reserved Stock | Stock Reservation Entry | STU, STM, SU, VW |
| Tồn kho số lượng | Available Stock for Packing Items | Product Bundle | STU, STM, SU, SM, VW |
| Vị trí kho | Ton Kho Theo Vi Tri, Doi Soat Ton Vi Tri, Hang Chua Xep Vi Tri, Hang Nam Sai Vi Tri | Location Balance | STU, STM, VW |
| Tài chính, sổ sách VN | General Ledger, Trial Balance, Trial Balance (Simple), Trial Balance for Party, Balance Sheet, Profit and Loss Statement, Cash Flow, Bang Can Doi So Phat Sinh, Bao Cao Tinh Hinh Tai Chinh B01, Bao Cao KQHDKD B02, Bao Cao Luu Chuyen Tien Te B03, Thuyet Minh BCTC B09, So Cai, So Nhat Ky Chung, So Chi Tiet Tai Khoan, So Chi Tiet Cong No, So Chi Tiet Nguyen Te, So Quy Tien Mat, So Tien Gui Ngan Hang, To Khai Thue GTGT 01, Quyet Toan TNDN, Voucher-wise Balance, Dimension-wise Accounts Balance Report, Deferred Revenue and Expense, General and Payment Ledger Comparison, Invalid Ledger Entries | GL Entry | AU, AM, VW |
| Tài chính | Consolidated Financial Statement, Financial Ratios | Account | AU, AM, VW |
| Tài chính | Payment Ledger | Payment Ledger Entry | AU, AM, VW |
| Tài chính | Bank Clearance Summary, Bank Reconciliation Statement, Payment Period Based On Invoice Date | Journal Entry | AU, AM, VW |
| Tài chính | Cheques and Deposits Incorrectly cleared | Payment Entry | AU, AM, VW |
| Tài chính | Account Balance | Bank Account | AU, AM, VW |
| Tài chính | Budget Variance Report | Cost Center | AU, AM, VW |
| Tài chính | Doi Chieu Tong Cong No, Tinh Trang Doi Chieu Cong No | Debt Reconciliation Statement | AU, AM, VW |
| Công nợ phải thu | Accounts Receivable, Accounts Receivable Summary, Customer Ledger Summary, Sales Payment Summary | Sales Invoice | AU, AM, VW, SU, SM |
| Công nợ phải thu | Customer Credit Balance | Customer | SM, AU, AM, VW |
| Công nợ phải trả | Accounts Payable, Accounts Payable Summary, Supplier Ledger Summary | Purchase Invoice | AU, AM, VW, PU, PM |
| Bán hàng | Sales Register, Item-wise Sales Register, Sales Invoice Trends, Delivered Items To Be Billed, Inactive Sales Items, Customers Without Any Sales Transactions | Sales Invoice | SU, SM, AU, AM, VW |
| Bán hàng | Sales Analytics, Sales Order Analysis, Sales Order Trends, Item-wise Sales History, Payment Terms Status for Sales Order, Inactive Customers, Exponential Smoothing Forecasting, Sales Person-wise Transaction Summary, Sales Person Target Variance Based On Item Group, Territory Target Variance Based On Item Group | Sales Order | SU, SM, AU, AM, VW |
| Bán hàng | Pending SO Items For Purchase Request | Sales Order | SU, SM, PU |
| Bán hàng (hoa hồng) | Sales Partner Commission Summary, Sales Partner Target Variance based on Item Group, Sales Partner Transaction Summary, Sales Person Commission Summary | Sales Order | SM, AM, VW |
| Bán hàng (hoa hồng) | Sales Partners Commission | Sales Invoice | SM, AM, VW |
| Bán hàng | Quotation Trends, Lost Quotations | Quotation | SU, SM, VW |
| Bán hàng | Delivery Note Trends, Delayed Item Report, Delayed Order Report | Delivery Note | SU, SM, STU, STM, VW |
| Bán hàng | Customer Acquisition and Loyalty, Customer-wise Item Price | Customer | SU, SM, AM, VW |
| Bán hàng | Item-wise Price List Rate (Report Builder, lọc theo `[pl]`) | Item Price | SU, SM, PU, PM, AU, AM |
| CRM | Lead Details, Lead Owner Efficiency, Campaign Efficiency, Prospects Engaged But Not Converted | Lead | SU, SM, MK, VW |
| CRM | First Response Time for Opportunity, Lost Opportunity, Opportunity Summary by Sales Stage, Sales Pipeline Analytics, Territory-wise Sales | Opportunity | SU, SM, MK, VW |
| Danh bạ | Address And Contacts, Addresses And Contacts, Dia Chi Giao Hang Thieu Nguoi Nhan | Address | SU, SM, PU, PM |
| Danh bạ | Doi Tac Thieu Email Lien He | Supplier | PU, PM, SU |
| Mua hàng | Purchase Analytics, Purchase Order Analysis, Purchase Order Trends, Item-wise Purchase History, Procurement Tracker | Purchase Order | PU, PM, AU, AM, VW (bỏ role Supplier hiện có) |
| Mua hàng | Purchase Register, Item-wise Purchase Register, Purchase Invoice Trends, Billed Items To Be Received, Received Items To Be Billed | Purchase Invoice | PU, PM, AU, AM, VW |
| Mua hàng | Purchase Receipt Trends | Purchase Receipt | PU, PM, STU, STM, VW |
| Mua hàng | Supplier Quotation Comparison | Supplier Quotation | PU, PM, VW |
| Mua hàng | Material Requests for which Supplier Quotations are not created, Requested Items to Order and Receive, Items To Be Requested | Material Request | PU, PM, STU, STM, VW |
| Mua hàng | Vat Tu Chua Co NCC Mac Dinh | Item | PU, PM, IM |
| TBYT | Tinh Trang Ho So TBYT | Item | IC, IM, PU, PM, SU, SM, STM, VW |
| Tài sản | Fixed Asset Register, Asset Depreciation Ledger, Asset Depreciations and Balances | Asset | AU, AM, VW |
| Tài sản | Asset Activity | Asset Activity | AU, AM, AO, VW |
| Tài sản | Asset Maintenance | Asset Maintenance | AU, AM, AO |
| Chi phí | Unpaid Expense Claim | Expense Claim | AU, AM, HM, VW (bỏ Expense Approver hiện có) |
| Chi phí | Employee Advance Summary | Employee Advance | AU, AM, VW |
| Nhân sự | Monthly Attendance Sheet, Monthly Attendance Report, Shift Attendance, Employee Working Hours, Employees working on a holiday | Attendance | HU, HM, VW |
| Nhân sự | Employee Leave Balance, Employee Leave Balance Summary, Employee Analytics, Employee Information, Employee Birthday | Employee | HU, HM, VW |
| Nhân sự | Leave Ledger | Leave Ledger Entry | HU, HM, VW |
| Nhân sự | Employee Exits | Exit Interview | HU, HM, VW |
| Nhân sự | Appraisal Overview | Appraisal | HU, HM, VW |
| Nhân sự | Recruitment Analytics | Staffing Plan | HU, HM, VW |
| Dự án | Project Summary, Project wise Stock Tracking | Project | PJM, AM, VW |
| Dự án | Delayed Tasks Summary, Today task | Task | PJM |
| Dự án | Daily Timesheet Summary, Employee Hours Utilization Based On Timesheet, Employee Billing Summary, Project Billing Summary, Project Profitability | Timesheet | PJM, AM, VW |
| Hỗ trợ | Issue Analytics, Issue Summary, First Response Time for Issues, Support Hour Distribution | Issue | ST, VW |
| Chất lượng | Quality Inspection Summary | Quality Inspection | QM, STM, VW |
| Chất lượng | Review | Quality Action | QM, VW |
| Hóa đơn điện tử | Doi Soat Hoa Don Dien Tu | Fast EInvoice Document | EI, EIC, VW |
| Hệ thống | Permitted Documents For User, Document Share Report, Database Storage Usage By Tables, Transaction Log Report, Audit System Hooks, Prepared Report Analytics, Calculated Discount Mismatch | (nhiều) | SYS |
| Hệ thống | Website Analytics | Web Page View | WM, SYS |
| Hệ thống | ToDo | ToDo | mọi user nội bộ (EMP) |

Report không có trong bảng thì giữ khóa theo R1. Hiện gồm: báo cáo sản xuất, gia công, bảo trì, POS, cổ đông; báo cáo thuế nước ngoài (UAE VAT 201, VAT Audit Report, Tax Withholding Details, TDS Computation Summary, IRS 1099); Vehicle Expenses, Daily Work Summary Replies, YouTube Interactions; Lead Conversion Time (ref Communication – `keep_standard`; quyền đọc chỉ có qua dòng `All` khi là chủ bản ghi, nên không bảo đảm được R3); `_Test Report 1` (dữ liệu thử, xóa).

Ghi chú:
- DH không được cấp report nhân sự hay chi phí: Script Report không qua H8 nên sẽ hiện toàn công ty. DH xem Attendance, Leave Application, Expense Claim của bộ phận bằng list/Report view, nơi H8 có hiệu lực.
- Sync ghi đè cấu hình report hiện có trên site (Phụ lục A).

### 11.3 Hook (phân hệ `access` {D17})

| Mã | Gắn vào | Nội dung | Bắt buộc |
|---|---|---|---|
| H1 | Contract: `permission_query_conditions` + `has_permission` | Lọc theo `party_type`: SU/SM → Customer; PU/PM → Supplier; HU/HM → Employee; AM, VW, AP, SYS → tất cả | ✓ |
| H2 | `validate` của Quotation, Sales Order, Sales Invoice, Purchase Order, Purchase Invoice | `rate`, `discount` từng dòng phải khớp Price List hoặc Blanket Order, trừ khi user có SM (bán) hoặc PM (mua). Trên Sales Order, đặt cờ `mvl_dung_gia_hd = 1` khi mọi dòng gắn Blanket Order và đúng giá HĐ (điều kiện WF-SO, D4) | ✓ |
| H3 | `validate` của Payment Entry | Chỉ cho dùng Bank Account ở trạng thái Đã duyệt (WF-BA) | ✓ |
| H4 | `on_update`/`after_insert` của User, Has Role, Role Profile, Custom DocPerm, Custom Role, User Permission, Workflow, MVL Approval Limits | Gửi email kiểm toán cho GĐVH (với User: khi đổi roles, role_profile_name, enabled) | ✓ |
| H5 | `validate` chung (doc_events `*`) cho DocType có workflow | Chặn thay đổi trường người dùng nhập được nếu user không có role `allow_edit` của state hiện tại; bỏ qua `workflow_state` và Update Field của transition | ✓ |
| H6 | Rà code | Mọi API whitelisted đọc/ghi DocType trong tài liệu dùng `frappe.get_list` / `frappe.has_permission`. Cấm `frappe.get_all` hoặc `ignore_permissions=True` với dữ liệu người dùng cuối | ✓ |
| H7 | Scheduler hằng ngày | Trả user có Role Profile tạm hết hạn về profile gốc (mục 4) | ✓ |
| H8 | `permission_query_conditions` + `has_permission` cho DocType có `[e]`/`[d]` (6.9, mục 7) | Với user U, DocType X, ptype p: (a) U có role nào **khác EMP và DH** được p trên X mà không ghi phạm vi → không giới hạn; (b) nếu không, và U có DH được p → chỉ hồ sơ có `employee` thuộc một trong các nhóm: nhân viên thuộc Department mà U nằm trong bảng Department Approver (gồm Department con); nhân viên có `leave_approver`, `expense_approver` hoặc user của `reports_to` là U; chính U; (c) còn lại → chỉ hồ sơ có `employee` = Employee của U (với Employee: `name`). Không áp cho DocType chỉ có `·o` | ✓ |
| H9 | `after_insert` / `on_trash` của ToDo (Assign To) | Khi giao Task, Job Applicant, Interview, Training Program, Training Event: share bản ghi cho người được giao (Task share **Ghi**, còn lại share Đọc); gỡ share khi hủy giao. Assign To chuẩn của frappe chỉ share Đọc | ✓ |
| H10 | `validate` chung cho DocType có workflow (cùng chỗ với H5) | Khi `workflow_state` chuyển đi từ một state "Chờ …": chặn nếu user là `doc.owner` (và với chứng từ HR, là chính nhân viên), hoặc đã duyệt một bước trước trên chứng từ này. "Đã duyệt một bước" = có Comment `comment_type = "Workflow"` do user tạo trên chứng từ, với nội dung là state đích của một transition xuất phát từ state "Chờ". Frappe luôn ghi Comment này khi chuyển trạng thái (`frappe/model/workflow.py:148`). Không dựa vào Version, vì Leave Application, Stock Reconciliation, Payroll Entry, Job Offer đang tắt `track_changes` | ✓ |
| H11 | `before_submit` chung cho DocType có workflow | Chặn `docstatus` 0→1 nếu không đi qua transition hợp lệ (state trước khi lưu và `workflow_state` mới không tạo thành transition của user). Cho qua trong hai trường hợp: (a) user có transition tự duyệt từ state hiện tại tới một state `doc_status 1` mà điều kiện đúng với chứng từ – khi đó gán `workflow_state` theo transition đó; (b) `doc.flags.ignore_permissions` (chứng từ hệ thống sinh – T24) | ✓ |

### 11.4 Thay đổi code

**Trong repo này (app erpnext):**

| Mã | File | Thay đổi |
|---|---|---|
| C1 | `erpnext/warehouse_operations/vitri/*.py` (hằng `VAI_TRO_*`) | Bỏ System Manager, thêm MVL Kho PDA vào các nhóm thao tác kho {D14}. Roles của các trang PDA ghi bằng Custom Role (11.8), không sửa JSON của Page |
| C2 | `erpnext/einvoice/setup.py` (`_grant_permissions`), `erpnext/supply_notification/setup.py` | Hai hàm chạy sau mỗi lần migrate và tự cấp quyền. Bỏ phần cấp quyền để sync là nguồn duy nhất |
| C3 | `erpnext/regional/vietnam/role_profiles.py` | Bỏ `ensure_vn_role_profiles` (profile cũ); sync tạo profile `RP-*` |
| C4 | `erpnext/einvoice/setup.py` (`is_chief_accountant`) | Bỏ `"System Manager" in roles`; chỉ Kế toán trưởng HĐĐT phát hành, hủy HĐĐT |

**Trong fork mvl26/hrms (repo riêng, cần người phụ trách repo đó):**

| Mã | File | Thay đổi |
|---|---|---|
| C5 | `hrms/hr/attendance_exempt.py:381, 391`; `hrms/hr/doctype/attendance_request/attendance_request_miyano.py:41` | Bỏ System Manager khỏi `only_for`. `APPROVER_BYPASS_ROLES` chỉ còn HR Manager (bỏ HR User, System Manager), vì bước cuối của WF-AR do HM thực hiện |
| C6 | `hrms/patches/v15_0/setup_cong_tac_workflow.py`, `hrms/hr/doctype/business_trip/business_trip.json` | (a) Bản tự phục hồi dùng role và transition của WF-BT (AP thay COO, không có System Manager/AssetCore Super Admin). (b) Thêm "Đã hủy" vào Select `workflow_state`. (c) Đặt `no_copy = 1` cho `workflow_state`: hiện thiếu, nên khi Amend, phiếu mới chép state cũ và frappe báo "Workflow State transition not allowed" |

### 11.5 Settings

| Settings | Trường | Giá trị | Hiện tại (23/10) | Ai ghi |
|---|---|---|---|---|
| System Settings | Apply Strict User Permissions | 0 {D11} | 0 | SYS |
| System Settings | 2FA | bật cho user có SYS, AM, HM | | SYS |
| HR Settings | Prevent Self Leave Approval, Prevent Self Expense Approval | 1 (dự phòng; không hiệu lực khi có workflow – 9.1) | 0 | HM |
| HR Settings | Leave Approver Mandatory, Expense Approver Mandatory | 1 | 1 | HM |
| HR Settings | Restrict Backdated Leave Application; Role Allowed to Create Backdated Leave Application | 1; HM | 0; trống | HM |
| HR Settings | Leave/Expense Approval Notification Template | trống (9.1) | trống | HM |
| Payroll Settings | Process Payroll Accounting Entry based on Employee | 0 | 0 | HM |
| Payroll Settings | Encrypt Salary Slips in Emails | 1 – trước khi bật, kiểm tra Password Policy của nhân viên | 0 | HM |
| Accounts Settings | Delete Accounting and Stock Ledger Entries on deletion of Transaction | 0 | | AM |
| Accounts Settings | Role Allowed to Over Bill; Role Allowed to Set Frozen Accounts; Role Allowed to Override Stop Action | AM; AM; AM | trống | AM |
| Accounts Settings | Role allowed to bypass Credit Limit (`credit_controller`) | SM {D21}. Đang trống thì **không ai** submit được SO vượt hạn mức (`erpnext/selling/doctype/customer/customer.py:538`) | trống | AM |
| Accounts Settings | Check Supplier Invoice Number Uniqueness | 1 | | AM |
| Stock Settings | Allow Negative Stock | 0 – trước khi tắt, xử lý Bin có `actual_qty < 0` | 1 | AM |
| Stock Settings | Role Allowed to Over Deliver/Receive; Role Allowed to Create/Edit Back-dated Transactions | STM; STM (trường Link, chỉ nhận một role) {D15} | trống | AM |
| Stock Settings | Role Allowed to Edit Frozen Stock | AM | trống | AM |
| Stock Settings | Item Rename Role (Miyano) | trống (chỉ System Manager, theo code – 3.2) | trống | AM |
| Stock Reposting Settings | Notify Reposting Error to Role | AM | trống | AM |
| Selling Settings | Maintain Same Rate Throughout Sales Cycle | 1 – trước khi bật, rà đơn đang mở có hóa đơn khác giá SO | 0 | SM |
| Selling Settings | Role Allowed to Override Stop Action | SM | trống | SM |
| Buying Settings | Maintain Same Rate; Action | 1; Warn (chênh giá PO–PR–PI có thật) | 1; Stop | PM |
| Buying Settings | Role Allowed to Override Stop Action | PM | trống | PM |
| Company (Miyano) | Exception Budget Approver Role | AM | trống | AM |
| Portal Settings, LDAP Settings | Default Role | trống | trống | SYS |
| Website Settings | Disable Signup | 1 | 1 | SYS |
| Role | Desk Access | 0 cho CUS, SUP, LK | | SYS |
| Module Profile | "MVL PDA" | chặn mọi module trừ Stock, Warehouse Operations; gán cho user KHO-PDA | | SYS |

### 11.6 Workspace

Workspace chỉ ảnh hưởng giao diện. Roles của Workspace chuẩn bị ghi đè khi migrate, nên sync ghi lại sau mỗi lần migrate. Module Profile chỉ dùng để ẩn module không dùng.

| Workspace (tên trên site) | Roles |
|---|---|
| Home, Tools | mọi user nội bộ |
| Accounting, Financial Reports, Payables, Receivables | AU, AM, VW |
| Doi Chieu Cong No | AU, AM |
| Buying | PU, PM, AU, AM, VW |
| Selling, Bán hàng | SU, SM, AU, AM, VW |
| Stock | STU, STM, PU, PM, SU, SM, AU, AM, VW |
| Quản lý kho | STU, STM, PDA (workspace mặc định của PDA) |
| Assets | AU, AM, AO, VW |
| CRM | SU, SM, MK, VW |
| Projects | PJU, PJM |
| Quality | QM, STU, STM, PU, PM, VW |
| Support | ST, EMP |
| HR, Employee Lifecycle, Recruitment | HU, HM, VW (Recruitment thêm DH) |
| Shift & Attendance, Leaves, Performance, Expense Claims, Tax & Benefits | EMP, HU, HM, DH, VW |
| Payroll, Salary Payout | HM, AM, VW |
| Thong Bao | SNA |
| Website | WM, MK |
| Integrations, Manufacturing, Build, Users, Welcome Workspace | SYS |
| IMM Operations | assetcore – ngoài phạm vi |

Workspace tùy chỉnh (Chi phí Miyano, Các đề nghị thanh toán, Trình quản lý công việc, Quản lý hợp đồng, Lịch) gán Roles theo DocType nguồn, ngoài phạm vi tài liệu này.

### 11.7 Custom Field và Property Setter

| DocType | Trường | Thiết lập | Lý do |
|---|---|---|---|
| Sales Order | `mvl_dung_gia_hd` (Check, mới) | `read_only = 1`, `no_copy = 1`, ẩn; H2 tính | Điều kiện WF-SO {D4} |
| Issue | `issue_type` | `reqd = 1` | User Permission Issue Type của ST không lọc được Issue có trường này trống |
| Employee | `create_user_permission` | `default = 0` | Không để HRMS tự tạo User Permission |
| Employee | `leave_approver`, `expense_approver`, `reports_to` | `reqd = 1` | Điều kiện của WF-LA, WF-AR, WF-EC; `reports_to` là nguồn của `custom_approver` trên Attendance Request |
| Business Trip | `approver_coo` | `reqd = 1` | Điều kiện của WF-BT; người được chọn phải có AP |
| (trường ở 11.1, phần Miyano đặt thêm) | | `permlevel` | G9 |

### 11.8 Page

Roles của Page ghi bằng Custom Role (sync). Page không có trong bảng thì giữ Roles chuẩn của frappe.

| Page | Roles mới | Roles hiện có trên site |
|---|---|---|
| lay-hang-pda, xep-hang-pda, quet-ma-tra-cuu | STU, STM, PDA | Stock User, Stock Manager, System Manager |
| dat-o-hang-loat | STU, STM | Stock User, Stock Manager, System Manager |
| attendance-review | HU, HM | HR User, HR Manager |
| organizational-chart | HU, HM | HR User, HR Manager |
| team-updates | không dùng (LK) | System Manager, Employee |
| huong_dan_thong_bao, thong_bao_cua_toi | mọi user nội bộ (EMP) | không giới hạn |

---

## 12. Hướng dẫn triển khai cho AI

**Bước 0 – Chuẩn bị:**
- Xuất bảng Custom DocPerm, Custom Role, Role Profile, Has Role, User Permission, Workflow, User Type ra file sao lưu.
- Làm C1–C4; gửi C5, C6 cho người phụ trách fork hrms.
- Dọn 2 Company test (Phụ lục A). Xử lý Bin âm trước khi tắt Allow Negative Stock.

**Bước 1 – Kiểm tra phủ DocType:**

```sql
SELECT dt.name, dt.module, dt.issingle, dt.is_submittable
FROM `tabDocType` dt
JOIN `tabModule Def` m ON m.name = dt.module
WHERE m.app_name IN ('frappe', 'erpnext', 'hrms')
  AND dt.istable = 0;
```

- Mọi DocType trả về phải có trong file ma trận ở một trong bốn trạng thái (mục 0); thiếu thì sync dừng.
- DocType có trong file ma trận nhưng không có trên site thì ghi log, không tạo. DocType có `module` thuộc app khác (ví dụ Asset Repair → assetcore) không được xử lý.
- **Các trường hợp là lỗi:**
  - S/X/A trên DocType `is_submittable = 0`;
  - D trên DocType `is_submittable = 1`;
  - DocType submittable ở trạng thái `matrix` mà không role nào có S;
  - Single có quyền khác R, W.

**Bước 2 – Chuyển tài liệu thành `erpnext/access/permissions/matrix.json`.** Dùng JSON: gate cấu trúc file của repo (`scripts/file_structure/gate.py`) không nhận đuôi `.yaml`. Tên DocType trong file phải viết đầy đủ, không dùng ký tự đại diện như `POS*`.

```json
{
  "roles": {
    "MVL Kho PDA": {"desk_access": 1},
    "MVL Khóa sửa": {"desk_access": 0}
  },
  "role_profiles": {
    "RP-KHO-TK": ["Employee", "Projects User", "Stock User"],
    "RP-KT-KTT": ["Employee", "Projects User", "MVL Department Head", "Leave Approver", "Expense Approver",
                  "Accounts User", "Accounts Manager", "Kế toán HĐĐT", "Kế toán trưởng HĐĐT", "Prepared Report User"]
  },
  "combined_profiles": [{"erp": "RP-IT-QT", "assetcore": "Quản trị viên IT"}],
  "doctypes": {
    "Purchase Order": {
      "state": "matrix",
      "perms": {"Purchase User": "CRWPE S", "Purchase Manager": "CRWSXAPEOH W1",
                "Stock User": "R", "MVL Approver": "RWS"},
      "workflow": "WF-PO"
    },
    "Payroll Entry": {
      "state": "matrix",
      "perms": {"HR Manager": "CRWSXA", "Accounts Manager": "R", "Accounts User": "RW", "MVL Approver": "RWS"},
      "workflow": "WF-PAY"
    },
    "Salary Slip": {
      "state": "matrix",
      "perms": {"Employee": "R R1", "HR Manager": "CRWSXAPE W1", "Accounts Manager": "R R1"},
      "scope": {"Employee": "e"},
      "permlevel_fields": {"1": ["gross_pay", "net_pay", "earnings", "deductions"]}
    },
    "User": {"state": "matrix", "perms": {"System Manager": "CRW W1"}, "keep_standard_rows": ["Desk User"]},
    "Company": {"state": "ref_master", "perms": {"Accounts Manager": "RW"}},
    "ToDo": {"state": "keep_standard"},
    "BOM": {"state": "g1_only"}
  },
  "reports": {
    "_default": ["MVL Khóa sửa"],
    "Accounts Receivable": ["Accounts User", "Accounts Manager", "MVL Viewer", "Sales User", "Sales Manager", "Sales Master Manager"]
  },
  "workflows": {
    "WF-PO": {
      "document_type": "Purchase Order",
      "override_status": 1,
      "send_email_alert": 1,
      "states": [
        {"state": "Nháp", "doc_status": 0, "allow_edit": "Purchase User"},
        {"state": "Chờ TP", "doc_status": 0, "allow_edit": "MVL Khóa sửa"},
        {"state": "Chờ BGĐ", "doc_status": 0, "allow_edit": "MVL Khóa sửa"},
        {"state": "Đã duyệt", "doc_status": 1, "allow_edit": "Purchase Manager"},
        {"state": "Từ chối", "doc_status": 0, "allow_edit": "Purchase User"},
        {"state": "Đã hủy", "doc_status": 2, "allow_edit": "MVL Khóa sửa"}
      ],
      "transitions": [
        {"from": "Nháp", "action": "Duyệt", "to": "Đã duyệt", "role": "Purchase User",
         "condition": "doc.base_grand_total <= frappe.db.get_value('MVL Approval Limits', None, 'h1')"},
        {"from": "Chờ TP", "action": "Duyệt", "to": "Chờ BGĐ", "role": "Purchase Manager",
         "condition": "doc.owner != frappe.session.user and doc.base_grand_total > frappe.db.get_value('MVL Approval Limits', None, 'h2')"}
      ]
    }
  }
}
```

Mẫu trên chỉ minh họa cấu trúc; file thật phải có đủ mọi DocType, report, workflow và transition ở mục 3–11.

**Bước 3 – Lệnh sync** `bench --site <site> execute erpnext.access.permissions.sync.run`. Lệnh idempotent, đăng ký **cuối cùng** trong `after_migrate` của app erpnext. `after_migrate` của hrms chạy sau erpnext, nên C6 là điều kiện để hai bên không ghi đè nhau (T45). Các bước:
1. Tạo role mới (3.1), Role Profile `RP-*` và profile ghép `RP-*+AC-*` (mục 4).
2. Custom DocPerm cho mỗi DocType trong file ma trận:
   - **Role được quản lý** = role ở mục 3.1, 3.3 và `All`, `Desk User`; các role khác (assetcore) là role ngoài.
   - `matrix`, `ref_master`, `g1_only`: xóa mọi dòng của role được quản lý, tạo lại đủ dòng theo bảng cùng G1, G2, G7, G8; giữ nguyên dòng của role ngoài.
   - `keep_standard`: nếu DocType không có dòng Custom DocPerm nào thì không làm gì. Nếu có, chép DocPerm chuẩn sang Custom DocPerm, xóa dòng của role được quản lý không có trong DocPerm chuẩn, giữ dòng của role ngoài.
3. Property Setter và Custom Field theo 11.1, 11.7.
4. Custom Role cho mọi Report của 3 app: mặc định LK, mở theo bảng 11.2. Custom Role cho Page (11.8). Roles cho Workspace (11.6).
5. Workflow theo 9.3, kiểm tra quy tắc 1–4 ở 9.2; Single `MVL Approval Limits`.
6. User Permission theo mục 10 dựa trên Role Profile của từng user; xóa User Permission Employee/Department/Company còn sót.
7. Settings theo 11.5.
8. **Báo cáo kiểm tra (chỉ in danh sách, không tự sửa):**
   - Employee thiếu `user_id`, `leave_approver`, `expense_approver`;
   - người duyệt không có profile chứa TBP (gồm cả user của `reports_to` và người duyệt ca); `approver_coo` của Business Trip không có AP; Department chưa có approver;
   - nhân viên chưa có người duyệt ca: hrms chỉ nhận Shift Request khi `approver` nằm trong bảng Department Approver `shift_request_approver` của bộ phận, hoặc là `Employee.shift_request_approver` (`hrms/hr/doctype/shift_request/shift_request.py:78`);
   - report đang bị khóa theo R1 (để rà xem có cần mở không);
   - bản ghi Authorization Rule;
   - user có AssetCore Super Admin ngoài IT-QT;
   - user nội bộ chưa có Role Profile;
   - trường perm level > 0 chưa khai báo ở 11.1.

**Bước 4 – Chuyển đổi workflow (chạy một lần, bằng patch):**
1. Tắt "MVL Duyệt thanh toán", xóa "SO Test Workflow", sửa tại chỗ "Cong Tac Approval" (9.4).
2. Tạo các workflow mới. Khi lưu, frappe điền state đầu tiên theo `doc_status` cho chứng từ cũ có `workflow_state` trống.
3. Gán lại `workflow_state` theo dữ liệu thật:
   - Leave Application theo `status` (Approved → Đã duyệt, Rejected → Từ chối);
   - chứng từ đã hủy → Đã hủy;
   - Bank Account đang dùng → Đã duyệt, sau khi AM rà (nếu không, H3 chặn mọi Payment Entry);
   - Business Trip giữ nguyên.

**Bước 5 – Kiểm thử:**
- Một user test cho mỗi Role Profile.
- Duyệt toàn bộ ô trong file ma trận, assert `frappe.has_permission(doctype, ptype, user=...)` đúng, kể cả phạm vi H8.
- Chạy bộ test ở mục 13.

**Bước 6 – Go-live (một lần):**
1. Chạy trên erptest → UAT với đại diện từng bộ phận.
2. Gán Role Profile cho toàn bộ user production. Thu hẹp 2 tài khoản quản trị về RP-IT-QT hoặc RP-BGD-GDVH.
3. Gỡ role lẻ cũ; tắt role ở 3.3 (COO chỉ tắt, không xóa); gỡ 6 Role Profile ERP cũ.
4. Xóa User Type `Employee Self Service` sau khi gỡ role ESS khỏi mọi user, vì mỗi lần lưu User Type này frappe sinh lại dòng Custom DocPerm cho ESS.
5. Khóa tài khoản không còn dùng.

---

## 13. Bộ kiểm thử bắt buộc

**A. Quyền và phạm vi dữ liệu**

| # | Kịch bản | Kết quả đúng |
|---|---|---|
| T01 | DH mở Salary Slip của nhân viên trong bộ phận | Không thấy, hoặc không thấy trường tiền |
| T02 | HU (NS-NV) mở Salary Structure Assignment, trường lương trên Employee | Bị chặn hoặc ẩn |
| T03 | CUS đọc Sales Order, Quotation của khách khác qua API | Bị chặn |
| T04 | Bất kỳ ai (trừ Administrator) xóa chứng từ đã Cancel | Bị chặn |
| T05 | SYS (IT-QT) tạo Payment Entry, Sales Invoice | Bị chặn |
| T06 | VW (BGD-GD) tạo Sales Invoice | Bị chặn |
| T07 | KD-NV và MK xóa Lead | Bị chặn |
| T08 | PDA đăng nhập; mở `/app/sales-invoice`, `/app/stock-balance` | Chỉ thấy workspace Quản lý kho và 3 trang PDA; hai đường dẫn kia bị chặn |
| T08b | PDA, CUS, SUP tạo Contact hoặc Address mới; SU xóa Contact do mình tạo | Bị chặn (ngoại lệ G10) |
| T09 | SU mở Contract có `party_type = Employee` | Không thấy (H1) |
| T10 | KT-NV (AU + EMP) tạo Expense Claim, Leave Application cho nhân viên khác | Bị chặn (H8) |
| T11 | NS-NV (HU + EMP) đọc Expense Claim của nhân viên khác | Bị chặn (H8) |
| T12 | SU mở danh sách Customer, có khách chưa đặt `default_price_list` | Thấy đủ khách (Strict = 0) |
| T13 | User chỉ có RP-NV mở form Sales Order, Expense Claim | Không lỗi "No permission" trên Company, Warehouse, Currency, Cost Center (G8) |
| T14 | Nhân viên tạo Employee Checkin rồi sửa `time` | Không sửa được |
| T15 | AU mở chi tiết Salary Slip; AU bấm Make Bank Entry | Chặn xem chi tiết; Make Bank Entry chạy được |

**B. Workflow và luồng duyệt**

| # | Kịch bản | Kết quả đúng |
|---|---|---|
| T16 | NV submit Leave Application, Attendance Request, Compensatory Leave Request của chính mình | Bị chặn |
| T17 | AU submit Journal Entry | Chỉ chuyển sang Chờ KTT |
| T18 | PU duyệt PO > H1 trên form | Không có hành động Duyệt; chỉ Gửi duyệt sang Chờ TP |
| T19 | PU gọi `frappe.client.submit` cho PO > H1; AU gọi API submit JE; Data Import có "Submit After Import" | Bị chặn (H11) |
| T20 | DH gọi API submit Expense Claim đang Chờ TBP | Bị chặn (H11) |
| T21 | SU sửa `rate` trên SO khác giá HĐ | H2 báo lỗi |
| T22 | AU tạo Payment Entry dùng Bank Account chưa duyệt | H3 báo lỗi |
| T23 | STU ghi sổ Stock Entry Material Receipt / Material Issue | Chỉ chuyển sang Chờ trưởng kho |
| T24 | JE khấu hao, đánh giá tỷ giá, bút toán lương do hệ thống sinh khi WF-JE bật | Ghi sổ được, state Đã ghi sổ |
| T25 | DH duyệt đơn nghỉ của chính mình; HM duyệt đơn nghỉ của chính mình | Bị chặn (G11) |
| T26 | Sửa nội dung phiếu đang Chờ … qua API (kể cả người lập); AU sửa Payroll Entry | Bị chặn (H5, `allow_edit` = LK) |
| T27 | DH duyệt rồi HM duyệt Leave Application | `status = Approved` được giữ; submit thành công |
| T28 | AM duyệt bước cuối Expense Claim | `approval_status = Approved` được giữ |
| T29 | MH-TP lập PO > H1, duyệt ở Chờ TP | MH-TP bị chặn; GĐVH duyệt được |
| T30 | GĐVH duyệt thay ở Chờ TP rồi duyệt tiếp Chờ BGĐ trên cùng PO | Bước BGĐ bị H10 chặn; BGD-GD duyệt được |
| T31 | KT-KTT lập Payment Entry > H3 rồi duyệt ở Chờ KTT | Bị chặn (G11) |
| T32 | SU submit SO vượt hạn mức tín dụng; SM submit cùng SO | SU bị chặn; SM chạy được |
| T33 | Mở list Sales Order, Sales Invoice, Payment Entry sau khi bật workflow | Chỉ báo vẫn là `status` của controller; `workflow_state` ở cột riêng |
| T34 | Hủy rồi Amend một PO, một Business Trip đã duyệt | Phiếu hủy ở Đã hủy; phiếu Amend bắt đầu từ Nháp, lưu không lỗi (Business Trip: sau C6) |
| T35 | Sau bước 4, mở 25 đơn nghỉ đã submit trước đó | `workflow_state` khớp `status` |
| T36 | Submit Expense Claim qua workflow, sau đó thanh toán | `status` do hrms tính (Unpaid → Paid), không bị workflow ghi đè |
| T37 | SO có cờ `mvl_dung_gia_hd = 1` và SO không có cờ | SU tự duyệt được SO thứ nhất; SO thứ hai chỉ Gửi duyệt sang Chờ KD-TP |
| T38 | Payment Entry thu tiền khách (Receive) giá trị lớn | AU ghi sổ thẳng, không qua Chờ KTT |

**C. Báo cáo và perm level**

| # | Kịch bản | Kết quả đúng |
|---|---|---|
| T39 | STU mở Stock Balance, Stock Ledger, Gross Profit | Bị chặn |
| T40 | SU mở Accounts Receivable; STU mở Stock Projected Qty; HM mở Salary Register | Chạy được (G7 + Custom Role) |
| T41 | STU xem cột `valuation_rate`, `stock_value` của Stock Ledger Entry qua Report view | Cột bị ẩn |

**D. Hệ thống, sync, code**

| # | Kịch bản | Kết quả đúng |
|---|---|---|
| T42 | Đổi Role Profile, Custom DocPerm, Custom Role, User Permission, MVL Approval Limits | GĐVH nhận email (H4) |
| T43 | User có Role Profile tạm hết hạn | H7 đã trả về profile gốc |
| T44 | KT-KTT, KT-NV, IT-QT bấm phát hành HĐĐT | KT-KTT chạy được; KT-NV và IT-QT bị chặn (sau C4) |
| T45 | Chạy `bench migrate` hai lần liên tiếp | Custom DocPerm và workflow vẫn khớp file ma trận; einvoice, supply_notification, hrms không cấp lại quyền hay khôi phục workflow cũ |
| T46 | PDA (kho được giao) hoàn tất lấy hàng một Delivery Note có hàng serial/lô; quét tra cứu một Purchase Receipt; xếp hàng bằng Location Transfer. IT-QT gọi cùng API | PDA chạy được cả ba, Delivery Note được submit; IT-QT bị chặn (sau C1) |
| T46b | PDA sửa đơn giá trên Delivery Note khi lấy hàng | Bị chặn (Maintain Same Rate = Stop) |
| T47 | Gán profile ghép RP-IT-QT+AC-Quản trị viên IT, lưu User hai lần | Role assetcore và System Manager vẫn còn; không có role ngoài profile |
| T48 | KHO-TK nhập Purchase Receipt có hàng quản lý serial/lô rồi submit; KHO-TP hủy phiếu đó | Cả hai chạy được (S/X trên Serial and Batch Bundle) |
| T49 | NV mở form Leave Application, chọn người duyệt; HU giao Task cho đồng nghiệp | Danh sách user hiện ra (dòng `Desk User` select trên User được giữ) |
| T50 | IT-QT gán Role Profile cho user mới | Lưu được (SYS có W1 trên User) |
| T51 | AU dùng Bank Reconciliation Tool tạo Payment Entry thu tiền; tạo Payment Entry chi > H3; tạo Journal Entry | Cái đầu chạy được; hai cái sau bị H11 chặn |
| T52 | GĐVH duyệt Stock Reconciliation chênh lệch ≠ 0 ở bước Chờ trưởng kho, rồi duyệt tiếp Chờ KTT | Bước KTT bị H10 chặn |
| T53 | Attendance Request: người được Assign To (`custom_approver`) duyệt; một trưởng bộ phận khác duyệt | Người được giao duyệt được; người khác bị chặn |
| T54 | User có AP nhưng không phải `approver_coo` duyệt Business Trip | Bị chặn |
| T55 | AM sửa số tài khoản của Bank Account đã duyệt | Không sửa trực tiếp được; phải Sửa → Nháp → duyệt lại |
| T56 | IT-QT mở MVL Salary Register; STU mở Item Prices, Warehouse Wise Stock Balance, Stock Analytics; DH mở Unpaid Expense Claim | Đều bị chặn (11.2) |
| T57 | Mở một report không có trong bảng 11.2 (ví dụ BOM Explorer) bằng user không phải Administrator | Bị chặn (R1) |

## 14. Điểm cần chốt (đã điền phương án mặc định)

| Mã | Nội dung | Mặc định |
|---|---|---|
| D1 | Giá trị hạn mức H1 (PO MH-NV tự duyệt), H2 (PO MH-TP duyệt), H3 (chi tiền, chi phí KT duyệt) | **Chưa có – bắt buộc chốt**, BGĐ ban hành bằng văn bản |
| D2 | Luồng duyệt Expense Claim / Employee Advance | TBP → KT-KTT (→ BGĐ nếu > H3). NS-TP không duyệt chi phí |
| D3 | HĐLĐ, phụ lục | Contract với `party_type = Employee`; không tạo DocType riêng |
| D4 | Khi nào KD-NV tự submit SO | Mọi dòng gắn Blanket Order và đúng giá HĐ (cờ `mvl_dung_gia_hd` do H2 tính); còn lại do KD-TP |
| D5 | GĐVH giữ System Manager | Giữ; rủi ro chấp nhận, bù bằng H4 |
| D6 | KHO-PDA | Giao diện PDA hiện là các desk Page (`erpnext/warehouse_operations/page/`), không phải portal, nên PDA phải là **System User** (desk = 1) bị khóa bằng Module Profile "MVL PDA" và Custom Role của Page (11.8). Nghỉ phép do NS-NV nhập hộ (HU có C trên Leave Application); cần tự phục vụ thì chuyển sang RP-KHO-TK. Phương án khác: làm giao diện portal cho PDA rồi mới chuyển PDA thành Website User |
| D7 | Chủ dữ liệu Item | MH-TP (Item Manager). MH-NV tạo, KHO-TP chỉ đọc |
| D8 | "Các đề nghị thanh toán" | Expense Claim / Employee Advance; không dùng Payment Request |
| D9 | Quotation | KD-NV submit trực tiếp, không qua duyệt |
| D10 | Giá trị tồn kho | Chỉ KT-KTT và BGĐ xem (Report + perm level trên SLE/Bin); Kho dùng báo cáo số lượng |
| D11 | Strict User Permissions, phạm vi hồ sơ nhân sự | Strict = 0; `[e]`/`[d]` bằng H8 |
| D12 | Hóa đơn điện tử | KT-NV có Kế toán HĐĐT (lập nháp); chỉ KT-KTT có Kế toán trưởng HĐĐT (phát hành, hủy) |
| D13 | Công tác | Business Trip (fork) với WF-BT; không dùng Travel Request; AP thay COO |
| D14 | Thao tác vị trí kho | Sửa code C1 |
| D15 | Giao dịch kho lùi ngày | Chỉ STM (trường chỉ nhận một role); AM điều chỉnh lùi ngày bằng Journal Entry |
| D16 | Role và Role Profile cũ | Tắt role ở 3.3; gỡ profile cũ sau khi gán xong `RP-*` |
| D17 | Nơi đặt code sync, H1–H11 và Single `MVL Approval Limits` | Trong app erpnext (package `erpnext/access/`, DocType thuộc module Setup), theo CLAUDE.md (hành vi lõi ERP sửa tại app này). Phương án khác: app riêng `miyano_access` |
| D18 | Installation Note | Dùng, quyền theo 6.2. Nếu nghiệm thu lắp đặt làm ở assetcore thì chuyển sang `g1_only` |
| D19 | Người dùng cả ERP và assetcore | Profile ghép do sync sinh; AssetCore Super Admin chỉ cấp cho IT-QT |
| D20 | Cấp duyệt khi trưởng bộ phận hoặc KTT tự lập chứng từ | GĐVH duyệt thay; bước BGĐ kế tiếp do BGD-GD. Phương án khác: cho trưởng bộ phận tự duyệt chứng từ của mình trong hạn mức |
| D21 | SO vượt hạn mức tín dụng | `credit_controller = SM` (KD-TP quyết định). Phương án khác: AM, khi đó WF-SO cần bước KTT và AM cần S trên Sales Order |
| D22 | Role HĐĐT trùng AU/AM | Giữ EI/EIC vì code einvoice kiểm tra theo tên. Phương án gọn hơn: sửa code dùng Accounts User/Accounts Manager và bỏ hai role |
| D23 | Tạo chứng từ ngay trong Bank Reconciliation Tool | Chỉ cho Payment Entry thu tiền hoặc chi ≤ H3 (khớp transition tự duyệt, H11). Payment Entry chi > H3 và Journal Entry phải lập thường, duyệt qua workflow, rồi đối soát. Phương án khác: cho qua toàn bộ, chấp nhận chi > H3 không qua duyệt |

## 15. Thay đổi so với V2.0

**Lỗi làm hỏng triển khai đã sửa:**
- Thiếu quyền B (G7). Báo cáo có `ref_doctype` không mở được.
- Quyền L không đủ để form đọc danh mục (G5, G8).
- User Permission theo user làm lộ hoặc khóa nhầm hồ sơ nhân sự. Bỏ User Permission Employee/Department, thay bằng H8; Strict = 0.
- AU không chạy được Make Bank Entry. Cấp RW trên Payroll Entry.
- Thiếu W1 cho các trường đã ở perm level 1 sẵn (Leave Application `status`, Expense Claim `approval_status`…), làm workflow duyệt không lưu được trạng thái (11.1, G9).
- Ô quyền sai so với cờ submittable (D trên DocType submittable, S trên DocType không submittable, DocType submittable không ai submit được).

**Luồng duyệt:**
- Thêm G11, H10: người lập ≠ người duyệt, kể cả khi profile gộp role lập và role duyệt. GĐVH là cấp duyệt thay (D20).
- Thêm H5 (bắt buộc), H11: frappe không kiểm tra `allow_edit` và không chặn submit vòng qua workflow ở server.
- Thêm role LK để khóa sửa ở trạng thái chờ duyệt.
- Đặc tả đầy đủ từng workflow: thứ tự state, Đã hủy, `override_status`, Update Field (9.2, 9.3).
- Tách WF-AR khỏi WF-LA. WF-PE cho phép thu tiền ghi sổ thẳng. WF-SO dùng cờ `mvl_dung_gia_hd`.
- Business Trip giữ tên state hiện có.
- Xử lý 3 workflow đang chạy trên site.

**Đồng bộ với site và code:**
- Thêm role EI, EIC, SNA, PRU, LK; làm rõ DH với LA/EA.
- Liệt kê code kiểm tra role theo tên, code cho System Manager vượt quyền, code tự gán role (3.2).
- Thêm thay đổi code C1–C6.
- Thêm profile ghép với assetcore.
- Cấu hình các thiết lập role có sẵn (credit limit, stop action, frozen stock, budget, backdated leave).
- Ghi đè Custom Role của report đang cấp lương cho Employee/HR User.
- Xóa User Type ESS.
- Workspace theo tên thực tế.

**Phạm vi:**
- Bổ sung khoảng 150 DocType: các module Miyano (Einvoice, TBYT, Warehouse Operations, Debt Reconciliation, Supply Notification, EDI), DocType của fork hrms, Serial No, Bank Guarantee, Installation Note, Tax Withholding Category, danh mục CRM, Prepared Report, DocType hệ thống của frappe.
- Bỏ Asset Repair (assetcore) và Contract Fulfilment Checklist (bảng con); sửa tên `Process Statement Of Accounts`.
- Bỏ CUS trên Quotation, SUP trên RFQ; CUS trên Issue dùng `·o`.
- Thêm perm level cho giá trị tồn trên Stock Ledger Entry, Bin.

**Rà soát lần 2 (23/10/2026):**
- Serial and Batch Bundle cần S/X: bundle được submit bằng quyền user (`erpnext/stock/serial_batch_bundle.py:387`).
- User và Role Profile: SYS có W1; giữ dòng chuẩn `All` / `Desk User` trên DocType frappe (G10), để ô chọn user hoạt động.
- H10 tra Comment "Workflow" thay cho Version. 4 DocType có workflow đang tắt `track_changes`.
- H11 cho qua submit thẳng khi khớp transition tự duyệt. Bank Reconciliation Tool chạy được trong hạn mức (D23).
- Report chuyển sang danh sách cho phép, mặc định khóa; đã xếp nhóm toàn bộ report của 3 app. Đóng các report đang lộ lương và giá trị tồn (MVL Salary Register, Item Prices, Warehouse Wise Stock Balance, Stock Analytics, Unpaid Expense Claim…).
- PDA thành System User bị khóa bằng Module Profile và Custom Role của Page, vì giao diện PDA là desk Page (D6). Thêm bảng Page (11.8).
- WF-AR dùng `custom_approver` của fork; C5 sửa thêm `APPROVER_BYPASS_ROLES`. WF-BT kiểm tra `approver_coo`. WF-BA có bước Sửa → Nháp; không sửa trực tiếp sau khi duyệt.
- Xếp loại đủ mọi DocType, ghi đúng tên, không dùng ký tự đại diện (Phụ lục B). Thêm Party Type và 4 Single Settings vào G8.
- File ma trận đổi sang `erpnext/access/permissions/matrix.json`.

**Rà soát lần 3 (23/10/2026):**
- PDA có quyền trên đúng các chứng từ mà code PDA thao tác: Delivery Note RWS [w], Purchase Receipt R [w]; bỏ quyền trên Pick List vì code không dùng (bảng ở 6.4).
- Contact, Address là ngoại lệ của G10: không chép dòng `All` chuẩn.
- G9 không áp dụng cho DocType `keep_standard`.
- Khóa report Lead Conversion Time.
- Sửa câu chữ về Workspace cho khớp hành vi của frappe.
- Báo cáo kiểm tra bổ sung người duyệt ca của Shift Request.

---

## Phụ lục A – Hiện trạng site `miyano` (đo ngày 22–23/10/2026)

**App:** frappe, erpnext, hrms, assetcore (các app khác trên bench chưa cài vào site).

**Role (113):**

| Nhóm | Số | Role | Theo tài liệu |
|---|---|---|---|
| Frappe chuẩn | 18 | System Manager, Website Manager, Workspace Manager, Newsletter Manager, Prepared Report User, Report Manager, Dashboard Manager, Script Manager, Inbox User, Blogger, Translator, Knowledge Base\*, Desk User, All, Guest, Administrator… | Dùng SYS, WM, WSM, NL, PRU |
| ERPNext chuẩn | 29 | Accounts/Sales/Purchase/Stock/Projects… User/Manager, Item Manager, Quality Manager, Support Team, Customer, Supplier, Delivery\*, Manufacturing\*, Maintenance\*, Agriculture\*, Auditor, Fulfillment User… | Theo 3.1, 3.3 |
| HRMS chuẩn/fork | 7 | Employee, Leave Approver, Expense Approver, Interviewer, Fleet Manager, Employee Self Service, COO | Dùng EMP, LA, EA |
| Miyano trong erpnext | 3 | Kế toán HĐĐT, Kế toán trưởng HĐĐT, Quản trị thông báo | Dùng |
| Tiếng Việt cũ, không có DocPerm | 10 | Kế toán công nợ - ngân hàng, Kế toán kho - ký gửi, Kế toán tổng hợp, Kế toán trưởng, Thủ kho, Thủ quỹ, NV kinh doanh, Nhân viên mua hàng, Quản lý, Quản lý xem báo cáo | Tắt. Kế toán tổng hợp/Kế toán trưởng đang nằm trong workflow "MVL Duyệt thanh toán"; "Quản lý" đang gán cho 2 user |
| assetcore | 30 | AssetCore\*, Calibration\*, Commissioning\*, Compliance\*, Corrective\*, Data\*, Document\*, Inventory\*, Needs\*, PM\*, Procurement\*, Repair\*, Spec\*, Training\*, Vendor Engineer | Ngoài phạm vi |
| Khác | 8 | Analytics, Healthcare Administrator, Internal Auditor, Laboratory User, Norm Manager, Norm User, Test Approver, Test Junior Approver | Tắt |

**User:**
- 27 System User và 15 Website User.
- Trong 27 System User:
  - 10 user chỉ có Sales User/Sales Manager;
  - khoảng 11 user chỉ có role assetcore;
  - 2 tài khoản quản trị giữ 82–96 role;
  - chưa user nào có role HR, Kế toán, Kho hay Employee.
- Chưa user nào được gán Role Profile.

**Role Profile (14):** 6 profile ERP (Inventory, Manufacturing, Accounts, Sales, Purchase, HR); 8 profile assetcore (Quản trị viên IT, Trưởng phòng VT-TTBYT, Trưởng xưởng kỹ thuật, Kỹ thuật viên, Cán bộ QA / Kiểm toán, Cán bộ hồ sơ, Thủ kho phụ tùng, Trưởng khoa lâm sàng).

**Quyền:**
- **Custom DocPerm:** 1.326 dòng trên 104 DocType. Nhiều dòng cấp cho Employee Self Service (sinh từ User Type ESS), All, Desk User, và các role assetcore trên DocType frappe (Address, Contact, File, Comment, Report, User…).
- **User Permission:** 2 bản ghi.
- **Authorization Rule:** không có.
- **Custom Role / Roles của report:**
  - Provident Fund Deductions, Income Tax Deductions, Professional Tax Deductions đang cấp cho Employee và HR User.
  - 6 report có Employee Self Service: Today task, Shift Attendance, Project Profitability, Appraisal Overview, Income Tax Computation, Income Tax Deductions.
  - Purchase Order Analysis có role Supplier.
  - Doi Soat Hoa Don Dien Tu cấp cho Kế toán HĐĐT, Kế toán trưởng HĐĐT.

**Workflow:**
- **Đang bật (25):** 3 trong phạm vi và 22 của assetcore.

  | Workflow | DocType | `override_status` | `send_email_alert` | Ghi chú |
  |---|---|---|---|---|
  | MVL Duyệt thanh toán | Payment Entry | 0 | 0 | Chờ duyệt → Đã duyệt (Kế toán trưởng) |
  | SO Test Workflow | Sales Order | 0 | 0 | Pending (All) → Approved (Test Approver) |
  | Cong Tac Approval | Business Trip | 0 | 0 | transition có thêm System Manager, AssetCore Super Admin |
- **Trường `workflow_state` hiện có:**
  - Custom Field (Link, `no_copy = 1`) trên Payment Entry, Sales Order, Asset Repair.
  - Trường Select trong JSON của Business Trip (không có `no_copy`).

**Dữ liệu chứng từ liên quan workflow:**
- Leave Application: 25 đã submit, 1 đã hủy.
- Sales Invoice: 4 đã submit, 1 đã hủy.
- Journal Entry: 11 đã submit. Stock Entry: 3. Attendance Request: 5. Purchase Order: 2. Payroll Entry: 1.
- Sales Order: 1 nháp. Payment Entry: 0.
- Business Trip: 1 ở COO đã duyệt, 3 ở Đã ra QĐ.

**Khác:**
- User Type Employee Self Service đang tồn tại.
- Ngoài Company Miyano còn 2 Company test (`_Test DR Child Acc`, `_Test DR Figures`) – dữ liệu thử còn sót.
- Giá trị Settings hiện tại: cột "Hiện tại" ở 11.5.

---

## Phụ lục B – DocType không dùng (`g1_only`), ghi đúng tên

Các DocType dưới đây chỉ có dòng G1 (SYS `R B`, VW `R P B`). DocType của frappe giữ thêm dòng chuẩn của `All` / `Desk User` (G10).

| App / module | DocType |
|---|---|
| erpnext / Accounts | Bisect Accounting Statements, Bisect Nodes, Cashier Closing, Coupon Code, Dunning, Dunning Type, Invoice Discounting, Ledger Health, Ledger Health Monitor, Loyalty Point Entry, Loyalty Program, Payment Gateway Account, Payment Order, Pegged Currencies, POS Closing Entry, POS Invoice, POS Invoice Merge Log, POS Opening Entry, POS Profile, POS Settings, Process Deferred Accounting, Process Subscription, Share Transfer, Share Type, Shareholder, Subscription, Subscription Plan, Subscription Settings |
| erpnext / Assets | Asset Shift Allocation, Asset Shift Factor |
| erpnext / Manufacturing (trừ Blanket Order) | BOM, BOM Creator, BOM Update Log, BOM Update Tool, Downtime Entry, Job Card, Manufacturing Settings, Operation, Plant Floor, Production Plan, Routing, Work Order, Workstation, Workstation Type |
| erpnext / Subcontracting | Subcontracting BOM, Subcontracting Order, Subcontracting Receipt |
| erpnext / Maintenance | Maintenance Schedule, Maintenance Visit |
| erpnext / Support | Warranty Claim |
| erpnext / Setup | Authorization Control, Authorization Rule, Transaction Deletion Record |
| erpnext / Selling, Utilities, Telephony, Communication | SMS Center, SMS Log, Video, Video Settings, Telephony Call Type, Call Log, Incoming Call Settings, Voice Call Settings, Communication Medium |
| erpnext / Portal, ERPNext Integrations, Bulk Transaction | Homepage, Homepage Section, Plaid Settings, Bulk Transaction Log, Bulk Transaction Log Detail |
| erpnext / Regional (nước ngoài) | Import Supplier Invoice, Lower Deduction Certificate, South Africa VAT Settings, UAE VAT Settings |
| hrms / HR | Travel Request, Daily Work Summary, Daily Work Summary Group, Vehicle Log, Vehicle Service Item |
| frappe / Core | Package, Package Import, Package Release, Patch Log, Module Def, Changelog Feed, Console Log, Recorder, Installed Applications, Language, Domain, Success Action, Transaction Log, User Invitation |
| frappe / Desk | Module Onboarding, Onboarding Step, Form Tour, System Console, System Health Report, Desktop Icon, Dashboard Settings |
| frappe / Custom, Email | DocType Layout, Email Flag Queue, Email Unsubscribe |
| frappe / Integrations | Google Calendar, Google Contacts, Google Drive, Google Settings, Dropbox Settings, S3 Backup Settings, Push Notification Settings, OAuth Authorization Code, OAuth Bearer Token, Token Cache, Slack Webhook URL, SMS Settings |
| frappe / Website | Blogger, Discussion Reply, Discussion Topic, Marketing Campaign, Personal Data Deletion Request, Personal Data Download Request |
| frappe / Automation, Social | Milestone, Milestone Tracker, Energy Point Log, Energy Point Rule, Energy Point Settings |

# TK_01 – Phân quyền ERP Miyano – Nền tảng chung (áp cho mọi module)

> Trích nguyên văn từ `../TK_01_PhanQuyen_ERP_V2.1_AI.md` (V2.1, 23/10/2026). Không sửa nội dung; tài liệu gốc là nguồn sự thật. Khi cần thay đổi, sửa tài liệu gốc rồi tách lại.

## Thông tin tài liệu gốc

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

## Mục 0 – Cách dùng tài liệu

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

## Mục 1 – Nguyên tắc bắt buộc

1. **Tối thiểu cần thiết.** Chỉ cấp đúng quyền ghi trong ma trận.
2. **Tách nhiệm.** Người lập ≠ người duyệt, kể cả khi một người giữ cả role lập và role duyệt (G11). Kho không ghi hóa đơn mua. Bán hàng không sửa giá vốn. IT không tự cấp quyền nghiệp vụ và không thao tác nghiệp vụ kho, kế toán.
3. **Không ai có quyền Xóa (D) trên DocType submittable**, kể cả Manager. Danh mục gốc (Customer, Supplier, Item, Serial No, Employee, Account, Warehouse, User) cũng không xóa, mà dùng Disabled / Left / Enabled = 0.
4. **Một user nội bộ = một Role Profile.** Không gán Role lẻ. Role mà code kiểm tra cứng (mục 3.2) phải nằm trong Role Profile tương ứng.
5. **Ẩn workspace không phải là bảo mật.** Module Profile cũng chỉ ẩn desktop và workspace, không chặn truy cập DocType. Bảo mật được dựng từ Custom DocPerm, perm level, User Permission, Custom Role của Report, workflow và hook.
6. **Thay đổi quyền trên production chỉ qua deploy file ma trận** (mục 12). Không sửa tay trong Role Permission Manager.
7. **Rà soát định kỳ.** Rà soát quyền mỗi quý. Nhân sự nghỉ việc thì khóa tài khoản trong ngày.

## Mục 2 – Ký hiệu

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

## Mục 3.1 – Danh mục role dùng trong ma trận

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

## Mục 3.2 – Ràng buộc từ mã nguồn

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

## Mục 3.3 – Role không dùng

Sau khi chuyển user sang Role Profile mới (mục 12, bước 6), các role dưới đây được gỡ khỏi mọi user và đặt `disabled = 1`:

- **Role chuẩn:** Report Manager, Delivery User, Delivery Manager, Manufacturing User/Manager, Maintenance User/Manager, Blogger, Academics User, Agriculture User/Manager, Healthcare Administrator, Laboratory User, Fulfillment User, Auditor, Internal Auditor, Analytics, Script Manager, Dashboard Manager, Inbox User, Knowledge Base Contributor/Editor, Translator, Fleet Manager, Interviewer, Employee Self Service, COO (thay bằng AP).
- **Role tiếng Việt cũ, không có DocPerm:** Kế toán công nợ - ngân hàng, Kế toán kho - ký gửi, Kế toán tổng hợp, Kế toán trưởng, Thủ kho, Thủ quỹ, NV kinh doanh, Nhân viên mua hàng, Quản lý, Quản lý xem báo cáo.
- **Role thử nghiệm và role của app chưa cài:** Test Approver, Test Junior Approver, Norm Manager, Norm User.
- **Administrator:** không dùng cho người.
- **Role tự động `All`, `Desk User`, `Guest`:** không tắt được. Không cấp quyền nghiệp vụ qua các role này (G10).
- **Role của assetcore:** không đụng tới.

## Mục 4 – Chân dung → Role Profile

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

## Mục 5 – Quy tắc chung áp cho mọi bảng

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

## Mục 9.1 – Nguyên tắc duyệt

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

## Mục 9.2 – Quy tắc kỹ thuật – không đè `status` có sẵn, không bị vòng qua

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

## Mục 9.3 – Đặc tả workflow (quy ước chung)

Quy ước:
- `(0)` `(1)` `(2)` là `doc_status`.
- Thứ tự state trong mỗi workflow đúng như liệt kê.
- Mọi transition từ "Chờ …" ngầm có điều kiện G11.
- Mọi workflow có transition **Mở lại**: Từ chối → Nháp, do role người lập thực hiện (nếu Từ chối có `doc_status 0`).
- Hạn mức `H1/H2/H3` viết tắt cho `frappe.db.get_value("MVL Approval Limits", None, "h1")`…

## Mục 9.4 – Workflow đang có trên site

Frappe chỉ chạy một workflow đang bật cho mỗi DocType.

| Workflow hiện có | DocType | Xử lý |
|---|---|---|
| MVL Duyệt thanh toán (role Kế toán tổng hợp, Kế toán trưởng) | Payment Entry | Tắt và thay bằng WF-PE |
| SO Test Workflow (role Test Approver, All) | Sales Order | Xóa; thay bằng WF-SO |
| Cong Tac Approval | Business Trip | **Sửa tại chỗ thành WF-BT, không xóa.** `hrms.setup_vn_defaults.ensure_defaults` (gọi `hrms/patches/v15_0/setup_cong_tac_workflow.py` mỗi lần migrate) tạo lại bản cũ nếu workflow hoặc role COO không còn. Sửa code fork hrms theo C6 |
| 22 workflow IMM-\* và AC Asset Lifecycle | DocType assetcore | Không đụng tới |

## Mục 10 – User Permission

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

## Mục 11.1 – Trường perm level (ghi chú chung)

Ghi chú:
- Không đặt perm level cho `rate` / `discount` trên dòng chứng từ. Với bản ghi mới, Frappe reset trường người dùng không có quyền ghi về giá trị mặc định, nên đơn giá bị xóa. Kiểm soát giá bằng H2. Stock Ledger Entry và Bin chỉ do hệ thống ghi nên đặt perm level an toàn.
- Không đặt perm level cho trường tiền mà chính nhân viên phải nhập (Employee Benefit Application/Claim, Employee Other Income, Employee Tax Exemption Declaration/Proof Submission). HU và DH vốn không có quyền trên các DocType này.
- Perm level trên trường của bảng con được cấp qua DocPerm level 1/2 của DocType cha.

## Mục 11.2 – Custom Role trên Report (nguyên tắc chung)

Query Report và Script Report **bỏ qua perm level và H8**, và nhiều report chuẩn đang mở cho role rộng hơn ma trận. Ví dụ đo trên site: MVL Salary Register mở cho HR User và System Manager; Item Prices và Warehouse Wise Stock Balance mở cho Stock User; Unpaid Expense Claim mở cho Expense Approver.

Vì vậy áp **danh sách cho phép**:
- **R1.** Mọi Report của 3 app mặc định nhận Custom Role = **LK** (không ai mở được, trừ Administrator). Report mới phát sinh sau này cũng mặc định khóa; sync liệt kê các report đang khóa để rà.
- **R2.** Chỉ report trong bảng dưới được mở cho các role ghi kèm. Ghi bằng **Custom Role** (Role Permission for Page and Report), vì bảng Roles của Report chuẩn bị ghi đè khi migrate.
- **R3.** Theo G7, mọi role trong cột Roles phải có R trên `ref_doctype`; sync kiểm tra và dừng nếu thiếu.

Report không có trong bảng thì giữ khóa theo R1. Hiện gồm: báo cáo sản xuất, gia công, bảo trì, POS, cổ đông; báo cáo thuế nước ngoài (UAE VAT 201, VAT Audit Report, Tax Withholding Details, TDS Computation Summary, IRS 1099); Vehicle Expenses, Daily Work Summary Replies, YouTube Interactions; Lead Conversion Time (ref Communication – `keep_standard`; quyền đọc chỉ có qua dòng `All` khi là chủ bản ghi, nên không bảo đảm được R3); `_Test Report 1` (dữ liệu thử, xóa).

Ghi chú:
- DH không được cấp report nhân sự hay chi phí: Script Report không qua H8 nên sẽ hiện toàn công ty. DH xem Attendance, Leave Application, Expense Claim của bộ phận bằng list/Report view, nơi H8 có hiệu lực.
- Sync ghi đè cấu hình report hiện có trên site (Phụ lục A).

## Mục 11.3 – Hook (phân hệ `access` {D17})

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

## Mục 11.4 – Thay đổi code

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

## Mục 11.6 – Workspace (nguyên tắc chung)

Workspace chỉ ảnh hưởng giao diện. Roles của Workspace chuẩn bị ghi đè khi migrate, nên sync ghi lại sau mỗi lần migrate. Module Profile chỉ dùng để ẩn module không dùng.

Workspace tùy chỉnh (Chi phí Miyano, Các đề nghị thanh toán, Trình quản lý công việc, Quản lý hợp đồng, Lịch) gán Roles theo DocType nguồn, ngoài phạm vi tài liệu này.

## Mục 11.7 – Custom Field và Property Setter (dòng chung)

| DocType | Trường | Thiết lập | Lý do |
|---|---|---|---|
| (trường ở 11.1, phần Miyano đặt thêm) | | `permlevel` | G9 |

## Mục 11.8 – Page (nguyên tắc chung)

Roles của Page ghi bằng Custom Role (sync). Page không có trong bảng thì giữ Roles chuẩn của frappe.

## Mục 12 – Hướng dẫn triển khai cho AI

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

## Mục 14 – Điểm cần chốt (đã điền phương án mặc định)

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

## Mục 15 – Thay đổi so với V2.0

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

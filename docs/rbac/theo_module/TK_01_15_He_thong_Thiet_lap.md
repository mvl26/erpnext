# TK_01 – Phân quyền ERP Miyano – Hệ thống, thiết lập, thông báo cung ứng

> Trích nguyên văn từ `../TK_01_PhanQuyen_ERP_V2.1_AI.md` (V2.1, 23/10/2026). Không sửa nội dung; tài liệu gốc là nguồn sự thật. Khi cần thay đổi, sửa tài liệu gốc rồi tách lại.
> Ký hiệu, quy tắc G1–G11, hook H1–H11 và hướng dẫn triển khai: xem `TK_01_00_Nen_tang_chung.md`.

## Mục 3.1 – Danh mục role dùng trong ma trận (trích các dòng liên quan)

| Mã | Role | Loại | Desk | Ghi chú |
|---|---|---|---|---|
| VW | MVL Viewer | **mới** | 1 | chỉ đọc |
| LK | MVL Khóa sửa | **mới** | 0 | **Không gán cho user nào, không có DocPerm.** Chỉ dùng làm `allow_edit` của trạng thái chờ duyệt để không ai sửa được nội dung (9.2) |
| PRU | Prepared Report User | chuẩn | 1 | xem kết quả báo cáo chạy nền (Stock Balance) |
| SNA | Quản trị thông báo | có sẵn | 1 | quản trị Supply Notification (3.2) |
| SYS | System Manager | chuẩn | 1 | |
| WM | Website Manager | chuẩn | 1 | |
| WSM | Workspace Manager | chuẩn | 1 | |
| DEV | MVL IT Dev | **mới** | 1 | production chỉ đọc log |

## Mục 3.2 – Ràng buộc từ mã nguồn (trích các dòng liên quan)

**Role được code kiểm tra theo tên** (đổi tên hoặc bỏ khỏi profile thì chức năng ngừng chạy):

| Role | Nơi kiểm tra | Chức năng |
|---|---|---|
| Quản trị thông báo | `erpnext/supply_notification/dispatch.py:419` | quản trị và gửi thông báo cung ứng |

**Code cho System Manager vượt quyền nghiệp vụ:**

| Nơi | Hành vi | Xử lý |
|---|---|---|
| `erpnext/setup/doctype/transaction_deletion_record/transaction_deletion_record.py:61` | System Manager được chạy xóa toàn bộ giao dịch | Chặn bằng DocPerm: SYS chỉ có R (6.12) |

**Code tự gán role.** Role Profile ghi đè toàn bộ role mỗi lần lưu User (mục 4), nên các role dưới đây phải nằm sẵn trong profile:

| Nơi | Hành vi | Hệ quả |
|---|---|---|
| `assetcore/services/shared/role_hooks.py:30` `sync_umbrella` | Gán AssetCore Super Admin thì tự thêm System Manager; gỡ thì gỡ kèm | Ai có Super Admin cũng thành SYS của ERP. Chỉ cấp Super Admin cho IT-QT {D19} |

## Mục 4 – Chân dung → Role Profile (trích các dòng liên quan)

| Chân dung | Role Profile | Roles |
|---|---|---|
| BGD-GDVH – Giám đốc Vận hành | RP-BGD-GDVH | BASE, TBP, SYS, PM, IM, SM, STM, QM, AM, HM, PJM, AP, PRU {D5} |
| BGD-GD – Giám đốc điều hành | RP-BGD-GD | BASE, TBP, VW, AP, PRU |
| IT-QT | RP-IT-QT | BASE, SYS, WM, WSM, ST, AO, SNA |
| IT-DEV | RP-IT-DEV | BASE, DEV (site dev/test: SYS) |

## Mục 6.11 – Thông báo cung ứng (module Supply Notification – Miyano)

| DocType | Quyền |
|---|---|
| Supply Notification Point, Supply Notification Recipient Group, Supply Notification Snippet | SNA CRWD; EMP R (thay dòng `All` R hiện có) |
| Supply Notification Opt Out | SNA CRWD |
| Supply Notification Settings (Single) | SNA RW; EMP R |
| Supply Notification Dispatch Log | SNA R |

`erpnext/supply_notification/setup.py` chạy sau mỗi lần migrate; xử lý theo C2 để không cấp lại quyền cho `All`.

## Mục 6.12 – Thiết lập, công cụ và module không dùng

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

## Mục 8 – Frappe – hệ thống

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

## Mục 11.1 – Trường perm level (trích các dòng liên quan)

**Trường Miyano đặt thêm** (Property Setter):

| DocType | Trường | Level | Đọc | Ghi |
|---|---|---|---|---|
| Web Page, Blog Post | `published` | 1 | MK, WM | WM |

**Trường đã ở perm level 1 sẵn – frappe** (giữ nguyên level, chỉ khai báo quyền):

| DocType | Trường | Đọc | Ghi |
|---|---|---|---|
| User | 18 trường: `roles`, `role_profile_name`, `block_modules`, `sb_allow_modules`, `modules_html`, `user_type`, `api_key`, `api_secret`, `generate_keys`, `restrict_ip`, `login_after`, `login_before`, `third_party_authentication`, `user_emails`, `reset_password_key`, `last_reset_password_key_generated_on`, `sb1`, `sb2` | SYS | SYS |
| Role Profile | `roles` | SYS | SYS |

**Trường đã ở perm level 1 sẵn – erpnext, hrms** (phải cấp lại vì Custom DocPerm thay thế dòng level 1 chuẩn, kể cả `All` R1):

| DocType | Trường | Đọc | Ghi | Lý do |
|---|---|---|---|---|
| POS Invoice, Voice Call Settings | `ignore_pricing_rule`, `user` | không ai | không ai | Không dùng |

## Mục 11.2 – Custom Role trên Report (trích các dòng liên quan)

| Nhóm | Report | ref_doctype | Roles |
|---|---|---|---|
| Hệ thống | Permitted Documents For User, Document Share Report, Database Storage Usage By Tables, Transaction Log Report, Audit System Hooks, Prepared Report Analytics, Calculated Discount Mismatch | (nhiều) | SYS |
| Hệ thống | Website Analytics | Web Page View | WM, SYS |
| Hệ thống | ToDo | ToDo | mọi user nội bộ (EMP) |

## Mục 11.3 – Hook (phân hệ `access` {D17}) (trích các dòng liên quan)

| Mã | Gắn vào | Nội dung | Bắt buộc |
|---|---|---|---|
| H4 | `on_update`/`after_insert` của User, Has Role, Role Profile, Custom DocPerm, Custom Role, User Permission, Workflow, MVL Approval Limits | Gửi email kiểm toán cho GĐVH (với User: khi đổi roles, role_profile_name, enabled) | ✓ |
| H7 | Scheduler hằng ngày | Trả user có Role Profile tạm hết hạn về profile gốc (mục 4) | ✓ |

## Mục 11.4 – Thay đổi code (trích các dòng liên quan)

**Trong repo này (app erpnext):**

| Mã | File | Thay đổi |
|---|---|---|
| C2 | `erpnext/einvoice/setup.py` (`_grant_permissions`), `erpnext/supply_notification/setup.py` | Hai hàm chạy sau mỗi lần migrate và tự cấp quyền. Bỏ phần cấp quyền để sync là nguồn duy nhất |
| C3 | `erpnext/regional/vietnam/role_profiles.py` | Bỏ `ensure_vn_role_profiles` (profile cũ); sync tạo profile `RP-*` |

## Mục 11.5 – Settings (trích các dòng liên quan)

| Settings | Trường | Giá trị | Hiện tại (23/10) | Ai ghi |
|---|---|---|---|---|
| System Settings | Apply Strict User Permissions | 0 {D11} | 0 | SYS |
| System Settings | 2FA | bật cho user có SYS, AM, HM | | SYS |
| Portal Settings, LDAP Settings | Default Role | trống | trống | SYS |
| Website Settings | Disable Signup | 1 | 1 | SYS |
| Role | Desk Access | 0 cho CUS, SUP, LK | | SYS |
| Module Profile | "MVL PDA" | chặn mọi module trừ Stock, Warehouse Operations; gán cho user KHO-PDA | | SYS |

## Mục 11.6 – Workspace (trích các dòng liên quan)

| Workspace (tên trên site) | Roles |
|---|---|
| Home, Tools | mọi user nội bộ |
| Thong Bao | SNA |
| Website | WM, MK |
| Integrations, Manufacturing, Build, Users, Welcome Workspace | SYS |
| IMM Operations | assetcore – ngoài phạm vi |

Workspace tùy chỉnh (Chi phí Miyano, Các đề nghị thanh toán, Trình quản lý công việc, Quản lý hợp đồng, Lịch) gán Roles theo DocType nguồn, ngoài phạm vi tài liệu này.

## Mục 11.8 – Page (trích các dòng liên quan)

Roles của Page ghi bằng Custom Role (sync). Page không có trong bảng thì giữ Roles chuẩn của frappe.

| Page | Roles mới | Roles hiện có trên site |
|---|---|---|
| team-updates | không dùng (LK) | System Manager, Employee |
| huong_dan_thong_bao, thong_bao_cua_toi | mọi user nội bộ (EMP) | không giới hạn |

## Mục 13 – Bộ kiểm thử bắt buộc (trích các dòng liên quan)

**A. Quyền và phạm vi dữ liệu**

| # | Kịch bản | Kết quả đúng |
|---|---|---|
| T04 | Bất kỳ ai (trừ Administrator) xóa chứng từ đã Cancel | Bị chặn |
| T05 | SYS (IT-QT) tạo Payment Entry, Sales Invoice | Bị chặn |

**D. Hệ thống, sync, code**

| # | Kịch bản | Kết quả đúng |
|---|---|---|
| T42 | Đổi Role Profile, Custom DocPerm, Custom Role, User Permission, MVL Approval Limits | GĐVH nhận email (H4) |
| T43 | User có Role Profile tạm hết hạn | H7 đã trả về profile gốc |
| T45 | Chạy `bench migrate` hai lần liên tiếp | Custom DocPerm và workflow vẫn khớp file ma trận; einvoice, supply_notification, hrms không cấp lại quyền hay khôi phục workflow cũ |
| T47 | Gán profile ghép RP-IT-QT+AC-Quản trị viên IT, lưu User hai lần | Role assetcore và System Manager vẫn còn; không có role ngoài profile |
| T50 | IT-QT gán Role Profile cho user mới | Lưu được (SYS có W1 trên User) |
| T57 | Mở một report không có trong bảng 11.2 (ví dụ BOM Explorer) bằng user không phải Administrator | Bị chặn (R1) |

## Mục 14 – Điểm cần chốt (đã điền phương án mặc định) (trích các dòng liên quan)

| Mã | Nội dung | Mặc định |
|---|---|---|
| D5 | GĐVH giữ System Manager | Giữ; rủi ro chấp nhận, bù bằng H4 |
| D16 | Role và Role Profile cũ | Tắt role ở 3.3; gỡ profile cũ sau khi gán xong `RP-*` |
| D17 | Nơi đặt code sync, H1–H11 và Single `MVL Approval Limits` | Trong app erpnext (package `erpnext/access/`, DocType thuộc module Setup), theo CLAUDE.md (hành vi lõi ERP sửa tại app này). Phương án khác: app riêng `miyano_access` |
| D19 | Người dùng cả ERP và assetcore | Profile ghép do sync sinh; AssetCore Super Admin chỉ cấp cho IT-QT |

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

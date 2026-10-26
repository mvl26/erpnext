# Phân quyền ERP Miyano (RBAC) — Kế hoạch thi công

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dựng toàn bộ cấu hình quyền của TK_01 V2.1 thành một file ma trận trong repo. Một lệnh sync idempotent áp ma trận lên site: Custom DocPerm, Role Profile, Report/Page/Workspace, workflow, User Permission, Settings. Kèm các hook H1–H11 mà Frappe không tự làm.

**Architecture:** Package mới `erpnext/access/`. `permissions/` chứa bộ đọc ma trận, bộ mở rộng quy tắc G1–G10, bộ kiểm tra tĩnh và các bước ghi. Các bước này được `permissions/sync.run` gọi theo thứ tự cố định, ở cuối `after_migrate`. Ma trận là các file JSON trong `permissions/matrix/`. Hook nghiệp vụ là các module ngang hàng trong `erpnext/access/`, đăng ký trong `erpnext/hooks.py`. Single `MVL Approval Limits` thuộc module Setup (D17).

**Tech Stack:** Frappe v15.112 / Miyano ERP (app erpnext), Custom DocPerm, Workflow, `permission_query_conditions` / `has_permission` hooks, `FrappeTestCase`.

**Spec:** `docs/rbac/TK_01_PhanQuyen_ERP_V2.1_AI.md` (V2.1, 23/10/2026). Khi spec và mục "Kết quả review" dưới đây khác nhau, làm theo mục review. Các điểm Q1–Q8 cần chủ đầu tư xác nhận trước khi thi công.

---

## Kết quả review TK_01 V2.1

Các điểm dưới đây đã được kiểm chứng trên code (frappe 15.112.0, erpnext, hrms, assetcore) và trên site `miyano` ngày 23/10/2026.

### Lỗi chặn — làm sai theo spec thì hỏng khi chạy

| # | Vấn đề | Bằng chứng | Plan xử lý |
|---|---|---|---|
| R-1 | **Mọi điều kiện hạn mức so sánh số với chuỗi.** `frappe.db.get_value("MVL Approval Limits", None, "h1")` đọc thẳng cột `value` của `tabSingles` mà không ép kiểu, nên trả `"50000000"` (str). `doc.base_grand_total <= "50000000"` ném `TypeError` ở mọi transition của WF-PO, WF-PE, WF-EC, kể cả mẫu JSON ở mục 12. | `frappe/database/database.py:699-716`; `safe_eval` chỉ cho `int`, `float`, `round` (`frappe/utils/safe_exec.py:884`) | Trong JSON viết `{H1}`, `{H2}`, `{H3}`. Builder thay bằng `float(frappe.db.get_value('MVL Approval Limits', None, 'h1') or 0)`. Nếu chưa nhập hạn mức thì giá trị là 0, mọi chứng từ đều phải qua duyệt (an toàn). Task 16 |
| R-2 | **Hook `has_permission` trả `True` sẽ che hook của app khác.** Frappe duyệt hook theo thứ tự đảo và **dừng ở kết quả khác `None` đầu tiên**. Nếu H1, H8 trả `True` khi cho phép thì hook của hrms/assetcore trên cùng DocType bị bỏ qua. | `frappe/permissions.py:450-457` | H1, H8 chỉ trả `False` hoặc `None`, không bao giờ trả `True`. Có test khóa |
| R-15 | **H5 gắn ở `validate` sẽ chặn mọi bước duyệt SI, PI, SE, SR.** Hook `validate` của `doc_events` chạy **sau** `validate` của controller. Controller của 4 DocType này gọi `validate_posting_time`, đặt lại `posting_date`/`posting_time` theo giờ hiện tại khi `set_posting_time = 0`. Người duyệt ở state "Chờ" không có LK, nên H5 thấy hai trường "đổi" và chặn. | `erpnext/utilities/transaction_base.py:19-22`; thứ tự gọi ở `frappe/model/document.py:1139-1150` | H5 gắn vào `before_validate`, chạy trước controller nên chỉ thấy thay đổi do người dùng gửi lên. `_doc_before_save` đã có từ `check_if_latest` (`document.py:859`). **Còn sót:** hook của `doc_events` chạy **sau** method `before_validate` của chính controller. Stock Entry có method này và áp lại putaway rule (`stock_entry.py:183-189`) khi `apply_putaway_rule = 1`, nên có thể tách hoặc đổi kho trên dòng `items`. Vì vậy `rules.json["h5_skip_tables"] = {"Stock Entry": {"flag": "apply_putaway_rule", "tables": ["items"]}}`. Với PO, SO thì method này chỉ đặt `has_unit_price_items`, mà trường đó ẩn nên H5 đã bỏ qua. Không app nào khác gắn `before_validate` cho `"*"`. Task 2, 17 |
| R-16 | **Sửa nội dung và chuyển state trong cùng một lần gọi API sẽ lách được hạn mức.** `validate_workflow` đánh giá điều kiện trên `doc._doc_before_save`, tức là giá trị đã lưu. Ví dụ PU lưu PO nháp 1 đồng, sau đó gọi `frappe.client.submit` với dòng hàng mới (1 tỷ) và `workflow_state = "Đã duyệt"`. Điều kiện `<= H1` được tính trên bản 1 đồng nên qua. H11 không chạy vì state có đổi. H5 không chặn vì PU có `allow_edit` ở Nháp. | `frappe/model/workflow.py:200-214` | Khi state đổi, `workflow_guard.validate` (chạy sau controller, lúc tổng tiền đã được tính lại) yêu cầu có một transition của user từ state cũ sang state mới mà điều kiện **cũng đúng trên bản đang lưu**. Task 17 |
| R-17 | **H11 tự gán `workflow_state` sẽ làm hỏng submit hợp lệ.** `before_submit` chạy trước `_validate` → `validate_workflow`. Nếu H11 đổi state thì frappe coi đó là một transition: chứng từ mới (chưa có `_doc_before_save`) bị ném "transition not allowed", còn chứng từ cũ thì bị kiểm lại điều kiện trên bản đã lưu. | `frappe/model/workflow.py:196-206`, `document.py:687-695` | H11 chỉ kiểm, **không gán**. Frappe tự gán state `doc_status 1` đầu tiên (`set_workflow_state_on_action`). Validate (Task 3) thêm luật: mọi transition tự duyệt (Nháp → `doc_status 1`) phải đi tới state `doc_status 1` đầu tiên. Chứng từ chưa có `_doc_before_save` thì coi state trước là state đầu tiên. Task 3, 17 |
| R-18 | **H10 không thấy bước duyệt đi bằng API.** Comment `Workflow` chỉ được `apply_workflow` ghi (`frappe/model/workflow.py:148`). Transition qua `frappe.client.save`/`submit` (hợp lệ sau R-16) không để lại comment, nên bước sau không biết người này đã duyệt bước trước. Ngoài ra nội dung comment là `_(state)`, có thể bị dịch. | `frappe/model/workflow.py:148` | Guard tự ghi dấu cho **mọi** transition rời state "Chờ", bất kể đi đường nào: Comment `comment_type = "Info"`, nội dung `"MVL-DUYET: <state cũ> → <state mới>"`. H10 đọc dấu này. Task 17 |
| R-19 | **Hai nguồn cùng ghi quyền Fast EInvoice.** `setup_einvoice` (đứng đầu `after_migrate`) gọi `_grant_permissions` ở mỗi lần migrate. *Đã kiểm lại: nhận định "migrate hai lần không bao giờ ra 0/0 và H4 bắn email từng dòng" chỉ đúng khi ô 6.6 lệch với `_grant_permissions`.* `add_permission` bỏ qua dòng đã có (`frappe/permissions.py:659-668`), còn `update_permission_property` ghi bằng `qb.update` nên không chạy doc event, tức không có H4 (`permissions.py:633-637`). Hiện hai bên khớp nhau, nên lần migrate thứ hai vẫn ra 0/0. Rủi ro thật là sau này ai đó sửa ô 6.6: hai bên sẽ âm thầm ghi đè nhau ở mọi lần migrate. | `erpnext/einvoice/setup.py:110, 383-403` | Vẫn làm C2 sớm ở **Task 9b** để sync là nguồn duy nhất, vì việc này rẻ. Task 15 kiểm idempotent bằng **hai lần `bench migrate`**. Phần C2 về `supply_notification/setup.py` của spec là sai, vì hàm đó không cấp quyền nào |
| R-20 | **`frappe.throw` trong `after_migrate` làm hỏng cả lần migrate.** Hook `after_migrate` của hrms và assetcore chạy **sau** erpnext (`frappe/migrate.py:155-157`), nên sẽ bị bỏ qua. Lệnh migrate trả mã lỗi. Chỉ cần thêm một DocType mới (từ nhánh khác, hoặc khi cập nhật hrms) mà quên khai trong ma trận là deploy hỏng. | `frappe/migrate.py:153-157` | Tách hai lối vào. `sync.after_migrate()` (đăng ký trong hooks): có lỗi validate thì in lỗi, **không ghi gì**, không throw. `sync.run()` (chạy tay): throw. Task 9 |
| R-21 | **H2 sẽ chặn AU lập SI/PI từ SO/PO.** Sales Invoice Item và Purchase Invoice Item **không có** trường `blanket_order`. SI lập từ SO giá HĐ, hoặc PI lập từ PO giá thương lượng, sẽ bị đem so với Price List, lệch giá, và AU (không có SM/PM) bị chặn. | `grep '"blanket_order"'` trên JSON: chỉ có ở Quotation/SO/PO Item | Dòng có liên kết chứng từ nguồn thì giá chuẩn là giá của dòng nguồn: SI `so_detail`/`dn_detail`, PI `po_detail`/`pr_detail`, SO `quotation_item`, PO `supplier_quotation_item`. Cùng loại lỗi: PU lập PO từ báo giá NCC đã thương lượng cũng sẽ bị chặn. Chỉ dòng không có nguồn mới tra Blanket Order hoặc Price List. Task 21 |
| R-23 | **Submit kèm state "Chờ" sẽ được frappe tự nâng lên "Đã duyệt".** Ví dụ PU gọi `frappe.client.submit` cho PO > H1, kèm `workflow_state = "Chờ TP"`. Transition Nháp → Chờ TP hợp lệ với PU, nên qua `validate_workflow` và qua cả kiểm R-16. H11 không chạy vì state có đổi. Sau đó `set_workflow_state_on_action` thấy `Chờ TP` có `doc_status 0` khác `docstatus 1`, liền đổi sang state `doc_status 1` đầu tiên là `Đã duyệt`. Kết quả: PO vượt hạn mức được ghi sổ mà không ai duyệt. Theo chiều ngược lại, lưu nháp vào thẳng state `doc_status 1` sẽ làm phiếu kẹt (H11 chặn submit, không còn transition nào đi tiếp). | `frappe/model/document.py:691-695`, `frappe/model/workflow.py:362-376` (thứ tự gọi: hook `validate` → `validate_workflow` → `set_workflow_state_on_action`) | Khi state đổi, guard `validate` buộc `doc_status` của state đích **bằng** `doc.docstatus`. Lúc gọi `validate` cho hành động submit, `docstatus` đã là 1 (`set_docstatus` trong `_save`). Task 17 |
| R-22 | **`Employee.reports_to` bắt buộc là điều không làm được.** Employee là NestedSet theo `reports_to` (`employee.py:24-25`) và không được tự báo cáo cho mình (`employee.py:214`). Nhân viên gốc (BGD-GD) vì vậy không bao giờ lưu được. | `erpnext/setup/doctype/employee/employee.py:24-25, 214` | **Không** đặt `reqd` cho `reports_to`. Audit liệt kê nhân viên thiếu `reports_to`, trừ đúng một nút gốc (Q9). `leave_approver`, `expense_approver` vẫn bắt buộc. Task 6, 9 |

### Rủi ro triển khai cao

| # | Vấn đề | Plan xử lý |
|---|---|---|
| R-3 | Sync gắn vào `after_migrate`. Như vậy lần `bench migrate` đầu tiên sau khi merge sẽ thay toàn bộ quyền và bật 15 workflow ngay, trong khi theo Phụ lục A chưa user nào có Role Profile và chưa ai có role HR/Kế toán/Kho/Employee. | Cờ `mvl_rbac_enabled` trong `site_config.json`. Chưa bật thì `sync.run` không làm gì, chỉ in một dòng (Q1) |
| R-4 | Bước 4 "bằng patch": patch chạy **trước** `after_migrate`, lúc workflow mới chưa tồn tại, và chạy ngay khi deploy, tức là trước UAT. | Thay bằng lệnh chạy tay, idempotent, có `dry_run`: `erpnext.access.permissions.cutover.run`. Chạy ở Bước 6 (Q2). Task 18 |
| R-5 | Tạo Custom Field (`mvl_dung_gia_hd`, `workflow_state` mà Workflow tự tạo) là DDL, nên **commit ngầm** transaction của test. Cache meta và quyền nằm trong Redis dùng chung với gunicorn. | `sync.run` làm **mọi DDL trước** (`ensure_schema`), phần còn lại chỉ là DML nên test rollback được. Test gọi `frappe.clear_cache()` khi dọn class. Bộ nghiệm thu nên chạy trên site test riêng (Q8) |
| R-6 | H9 gắn `on_trash` của ToDo. Nhưng gỡ giao việc trên giao diện là `set_status(..., "Cancelled")`, tức là **lưu** ToDo chứ không xóa, nên `on_trash` không bao giờ chạy. | Gắn thêm `on_update` khi `status` chuyển sang `Cancelled` (`frappe/desk/form/assign_to.py:181-186`). Task 20 |
| R-7 | Sync xóa rồi tạo lại Custom DocPerm. Mỗi lần migrate như vậy sẽ bắn hàng trăm email H4 cho GĐVH. | Ghi theo **diff** (chỉ thêm/xóa dòng lệch). Trong sync đặt `frappe.flags.in_rbac_sync`, H4 im lặng, cuối sync gửi **một** email tóm tắt nếu có thay đổi. Task 4, 22 |

### Thiếu sót của spec

| # | Vấn đề | Plan xử lý |
|---|---|---|
| R-8 | Mục 10 cần "kho được giao", bảng giá mua/bán, Issue Type, khách/NCC của **từng user**, nhưng spec không nói dữ liệu này lấy ở đâu. Nguyên tắc 6 lại cấm sửa tay. | File `matrix/user_scope.json`, khóa theo email user (Q4). Task 9, 14 |
| R-9 | C3 bỏ `ensure_vn_role_profiles`, nhưng `erpnext/regional/vietnam/go_live.py:285` `_check_role_profiles` và `regional/vietnam/tests/test_go_live.py` (5 chỗ) còn dùng. Bỏ hàm thì kiểm tra go-live báo đỏ và test hỏng. | C3 đổi kiểm tra sang danh sách profile `RP-*` của ma trận. Task 23 |
| R-10 | 3.2 thiếu `erpnext/supply_notification/dispatch.py:419` `only_for((ADMIN_ROLE, "System Manager"))`. SYS (gồm cả GĐVH) gửi lại được thông báo cung ứng. | Bỏ `"System Manager"`, giống C4. IT-QT đã có SNA nên không mất chức năng (Q6). Task 23 |
| R-11 | Nhiều job hệ thống chạy dưới user `Administrator` mà không đặt `ignore_permissions` (scheduler, Auto Repeat). H11 sẽ chặn những job này. | H5, H10, H11 bỏ qua `Administrator`. Theo 3.3, không người nào dùng tài khoản này (Q5) |
| R-12 | `after_migrate` của assetcore chạy **sau** erpnext: `_apply_core_permissions` (`assetcore/setup/install.py:464`) upsert Custom DocPerm cho role assetcore trên 36 DocType frappe, rồi `_seed_role_profiles` sinh lại 8 profile. Việc này không đụng dòng của role được quản lý, nhưng profile ghép `RP-*+AC-*` được dựng từ profile assetcore của lần migrate **trước**, nên chậm một nhịp. | Sync đọc profile assetcore hiện có. Audit (Task 9) liệt kê profile ghép lệch so với hợp role hiện tại |
| R-13 | `get_transitions` đánh giá điều kiện trên `doc._doc_before_save`, tức là giá trị **đã lưu** (`frappe/model/workflow.py:208`). | Giữ nguyên kiểm tra của frappe. Guard đánh giá thêm trên **bản đang lưu**, cả khi state đổi (R-16) lẫn với H11(a), vì đó là giá trị sẽ được ghi sổ. Task 17 |
| R-14 | Repo `apps/hrms` đang có thay đổi chưa commit (`hooks.py`, `fixtures/custom_field.json`…). C5, C6 là việc của repo đó. | Plan **không sửa** hrms. Task 24 chỉ viết tài liệu bàn giao |

Mọi tham chiếu dòng code còn lại trong mục 3.2 đã khớp với code hiện tại: `einvoice/setup.py:23, 405`, `issue.py:156`, `cancel.py:34`, `debt_reconciliation/constants.py:42`, 9 hằng `VAI_TRO_*`, `item_code_rule.py:490`, `user.py:208`, `workflow.py:148`, `attendance_request_miyano.py:41`, `attendance_exempt.py:381, 391`. Site có 575 DocType không phải bảng con (erpnext 293, frappe 176, hrms 106) và 244 Report thuộc 3 app.

## Quyết định chờ chủ đầu tư xác nhận

- **Q1.** Sync chỉ chạy khi `site_config.json` có `"mvl_rbac_enabled": 1`. Bật trên site test trước, production bật ở Bước 6.
- **Q2.** Bước 4 (chuyển đổi workflow) và các việc một lần ở Bước 6 (tắt role 3.3, gỡ profile cũ, xóa User Type ESS) là lệnh `cutover.run(dry_run=1)`, không phải patch.
- **Q3.** Ma trận tách thành nhiều file `erpnext/access/permissions/matrix/*.json`, không gom một `matrix.json`. Lý do: khoảng 575 DocType, 244 report và 15 workflow; tách file thì chép được song song, rà được theo mục. Trùng khóa giữa các file là lỗi. Ô quyền ghi bằng **mã role của 3.1** (PU, PM, AP…). Mã PM, SM mở ra cả hai role (Manager + Master Manager).
- **Q4.** `matrix/user_scope.json` giữ phạm vi dữ liệu của từng user (kho, bảng giá, Issue Type, khách hàng, NCC), khóa theo email.
- **Q5.** H5, H10, H11 bỏ qua `Administrator`.
- **Q6.** Bỏ `System Manager` khỏi `supply_notification/dispatch.py:419`.
- **Q7 (D1).** Chưa có H1–H3. Trong lúc chờ, hạn mức = 0, nghĩa là mọi PO, mọi Payment Entry chi, mọi Expense Claim đều phải qua duyệt.
- **Q8.** Bench chỉ có một site là `miyano`. Đề xuất tạo site `erptest` (restore backup của `miyano`) để chạy bộ nghiệm thu Task 25–26 và để UAT. Lý do thêm: khi cờ bật, Property Setter `reqd` trên Employee làm hỏng mọi bộ test dựng Employee mà không điền người duyệt.
- **Q9 (11.7, R-22).** Bỏ `reqd = 1` của `Employee.reports_to`, thay bằng dòng audit. Cần chỉ định nhân viên gốc của cây (đề xuất: BGD-GD).

## Những điểm plan tự quyết

- Tên Workflow: `"<mã> <DocType>"`, ví dụ `"WF-PO Purchase Order"`, `"WF-LA Shift Request"`. Riêng WF-BT giữ tên `"Cong Tac Approval"` (9.4).
- JSON workflow chỉ ghi "Điều kiện (ngoài G11)". Builder **tự nối** G11 vào mọi transition xuất phát từ state bắt đầu bằng `"Chờ"`: `doc.owner != frappe.session.user`. Với DocType có trường `employee`, nối thêm `frappe.db.get_value('Employee', doc.employee, 'user_id') != frappe.session.user`. Các transition này cũng đặt `allow_self_approval = 0`, để `apply_workflow` tự từ chối owner (`has_approval_access`, `frappe/model/workflow.py:221`). Đây là lớp chặn thứ hai.
- `rules.json["retired_roles"]` chỉ gồm các role tắt được ở 3.3. **Không** đưa `Administrator`, `All`, `Desk User`, `Guest` vào danh sách này.
- Trước khi ghi Custom DocPerm cho một DocType chưa có dòng custom, gọi `frappe.permissions.setup_custom_perms(dt)` để chép DocPerm chuẩn. Nhờ vậy dòng chuẩn của role ngoài (assetcore) vẫn còn, rồi mới xóa dòng của role được quản lý.
- Danh sách DocType gắn H8 được ghi cứng trong `hooks.py`, vì `hooks.py` không được import `erpnext.access`. Có test so danh sách này với các DocType có phạm vi `e`/`d` trong ma trận.
- Thêm PDA vào hằng `VAI_TRO_*` nào (C1): chỉ những hằng chặn API mà 3 trang `lay-hang-pda`, `xep-hang-pda`, `quet-ma-tra-cuu` gọi tới (kể cả in tem kiện).
- Bật 2FA (11.5) bằng `Role.two_factor_auth = 1` trên SYS, AM, HM, cộng `System Settings.enable_two_factor_auth = 1`.
- Settings có điều kiện tiên quyết (Allow Negative Stock = 0, Maintain Same Rate = 1, Encrypt Salary Slips = 1) **không tự áp**. Sync kiểm điều kiện, và nếu chưa đạt thì in dòng audit.

## Global Constraints

- Chạy lệnh bench từ `/home/miyano/frappe-bench`, `--site miyano`. Test chạy **từng module một, tuần tự**: `--module A --module B` chỉ chạy B, và hai lệnh `run-tests` song song sẽ deadlock. Subagent chạy song song chỉ được viết file; lệnh `run-tests` do controller chạy lần lượt.
- Python thụt lề bằng **TAB**, dòng tối đa 110 ký tự, chuỗi dùng ngoặc kép. Comment dùng gạch dài `—`, không dùng `–` (RUF002/003). Kiểm bằng `pre-commit run --files <file>`.
- **Không commit, không tạo/đổi nhánh** (CLAUDE.md). Bước cuối của mọi task là "để nguyên trong working tree".
- **Không sửa** `apps/hrms`, `apps/assetcore`, `apps/mvl_accounting`.
- Không kiểm chứng bằng `bench console` gọi hàm có ghi dữ liệu. Mọi kiểm chứng phải nằm trong test.
- Chỉ `sync.run` được ghi Custom DocPerm, Custom Role, Role Profile, Workflow, User Permission. Không ghi tay.
- Tên role mới viết đúng như sau: `MVL Item Creator`, `MVL Marketing`, `MVL Kho PDA`, `MVL Asset Operator`, `MVL Department Head`, `MVL Viewer`, `MVL Approver`, `MVL Khóa sửa`, `MVL IT Dev`. Tên Role Profile: `RP-<chân dung>` (mục 4), profile ghép `RP-<x>+AC-<profile assetcore>`, profile tạm `RP-<gốc>+TMP-<yyyymmdd>`.
- Không cấp quyền nghiệp vụ cho `All`, `Desk User`, `Guest` (G10). Không ai có D trên DocType submittable (G3).
- Điều kiện workflow chỉ được dùng `doc`, `frappe.session.user`, `frappe.db.get_value`, `frappe.db.get_list`, `int`, `float`, `round` và các hàm ngày giờ có trong safe globals.
- Hook `has_permission` chỉ trả `False` hoặc `None` (R-2).
- Sửa JSON của DocType nào thì nâng `"modified"` của DocType đó.
- Gunicorn chạy dưới supervisor với `--preload`. Code Python mới chỉ có hiệu lực sau khi **người dùng** chạy `sudo supervisorctl restart frappe-bench-web: frappe-bench-workers:`.
- Site không có Item/Customer/Delivery Note. Test cần chứng từ phải tự dựng fixture, đặt tên có hậu tố `frappe.generate_hash()`. Rollback của `FrappeTestCase` tính theo **class**, không theo từng test.

## Review Focus

1. **Dòng Custom DocPerm của role ngoài (assetcore) trên DocType trong ma trận:** sync không được xóa. Chạy sync hai lần thì lần hai 0 thêm, 0 xóa (T45). → test ở Task 4.
2. **User có cả EMP và role nghiệp vụ** (KT-NV = AU + EMP): AU có R trên Expense Claim nên đọc được mọi đơn, nhưng C chỉ đến từ EMP `[e]`. Vì vậy tạo đơn cho người khác bị chặn (T10), còn đọc thì không (H8 tính theo từng ptype). → test ở Task 19.
3. **Chứng từ submit trước khi bật workflow** (25 Leave Application, 11 JE…): sau cutover, Cancel bằng nút chuẩn vẫn chạy, H11 không chặn nhầm, `workflow_state` khớp `status` (T35). → test ở Task 18.
4. **Chưa nhập hạn mức** (`h1` trống): điều kiện không ném lỗi, PO đi Gửi duyệt. → test ở Task 16.
5. **Chứng từ hệ thống sinh khi workflow đang bật** (JE khấu hao, đánh giá tỷ giá, bút toán lương; job chạy bằng Administrator): submit được, state = Đã ghi sổ (T24). Amend phiếu đã hủy bắt đầu lại từ Nháp (T34). → test ở Task 17.

---

## Thứ tự thi công và song song hóa

```
Đợt 1 (tuần tự):   T1 → T2 → T3 → T4
Đợt 2 (song song): T5 T6 T7 T8 T9b  |  T10 T11 T12 T13 T13b T14 (chép ma trận)
                   → T9 → T15 (cổng phủ, tuần tự)
Đợt 3:             T16 → T17 → T18      song song với  T19 T20 T21 T22
Đợt 4:             T23, T24 → T25 → T26 → T27
```

Chỗ ghi dùng chung `erpnext/hooks.py` (after_migrate, doc_events `"*"`, `permission_query_conditions`, `has_permission`, scheduler) **không chia cho subagent song song**. Bước "đăng ký hook" của mỗi task do controller làm tuần tự sau khi task đó qua review.

---

## Đợt 1 — Nền tảng ma trận

### Task 1: Bộ đọc ma trận, mã quyền, danh mục role và profile

**Files:**
- Create: `erpnext/access/__init__.py`, `erpnext/access/permissions/__init__.py`
- Create: `erpnext/access/permissions/cells.py`, `erpnext/access/permissions/matrix.py`, `erpnext/access/permissions/site.py`
- Create: `erpnext/access/permissions/matrix/roles.json` (đủ mục 3.1 và mục 4)
- Test: `erpnext/access/tests/__init__.py`, `erpnext/access/tests/test_cells.py`, `erpnext/access/tests/test_matrix.py`

**Interfaces:**
- Produces:
  - `cells.MatrixError(Exception)`
  - `cells.PTYPE_BY_LETTER: dict[str, str]`: R read, W write, C create, D delete, S submit, X cancel, A amend, P print, E email, B report, O export, I import, H share, L select
  - `cells.parse_cell(cell: str) -> dict[int, frozenset[str]]`. Chữ cái rời → level 0. Token `R1`/`W1`/`R2`/`W2` → level 1/2, `W` kéo theo `read` cùng level. Khoảng trắng và dấu phẩy bỏ qua. Ký tự lạ → `MatrixError`.
  - `matrix.MATRIX_DIR: Path`, `matrix.load_matrix(directory: Path = MATRIX_DIR) -> Matrix`. Hàm gộp mọi `*.json` trong thư mục; khóa (DocType, report, workflow, profile…) trùng giữa hai file → `MatrixError` nêu tên cả hai file.
  - `@dataclass Matrix`: `roles: dict[str, RoleDef]`, `packs: dict[str, list[str]]`, `role_profiles: dict[str, list[str]]`, `combined_profiles: list[dict]`, `doctypes: dict[str, DocTypeEntry]`, `rules: dict`, `reports: dict[str, list[str]]`, `pages: dict[str, list[str]]`, `workspaces: dict[str, list[str]]`, `workflows: dict[str, dict]`, `settings: dict`, `custom_fields: dict`, `user_permission_rules: dict`, `user_scope: dict`, `module_profiles: dict`
  - `@dataclass RoleDef(code: str, names: tuple[str, ...], desk_access: int, is_new: bool)`
  - `@dataclass DocTypeEntry(state: str, perms: dict[str, str], scope: dict[str, str], workflow: str | None, permlevel: dict[int, dict], keep_standard_rows: list[str], pda: bool)`. `state` ∈ `matrix | ref_master | g1_only | keep_standard`. `scope` có giá trị là các token cách nhau bằng khoảng trắng, thuộc `o e d w pl c s g`. `permlevel[1] = {"fields": [...], "read": [codes], "write": [codes]}`.
  - `Matrix.role_names(code: str) -> tuple[str, ...]`, `Matrix.profile_roles(profile: str) -> list[str]` (đã mở `BASE`, `TBP` và mã role thành tên)
  - `site.py` (đặt ở Task 1 để Task 2 và Task 3 không phụ thuộc vòng): `@dataclass DocTypeInfo(name: str, app: str, module: str, is_submittable: bool, issingle: bool, high_permlevel_fields: frozenset[str])`, `@dataclass SiteInfo(doctypes: dict[str, DocTypeInfo], reports: dict[str, str])` (report → `ref_doctype`), `SiteInfo.from_db() -> SiteInfo`. DocType lấy theo truy vấn Bước 1 của spec. Report lấy theo `Module Def.app_name` thuộc 3 app. `high_permlevel_fields` lấy từ `frappe.get_meta(dt).get_high_permlevel_fields()`.

- [ ] **Step 1: Viết test hỏng**

```python
def test_letters_and_levels(self):
	self.assertEqual(parse_cell("CRWS PE"), {0: frozenset({"create", "read", "write", "submit", "print", "email"})})
	self.assertEqual(parse_cell("R R1"), {0: frozenset({"read"}), 1: frozenset({"read"})})
	self.assertEqual(parse_cell("CRW W1")[1], frozenset({"read", "write"}))

def test_unknown_letter_raises(self):
	self.assertRaises(MatrixError, parse_cell, "CRQ")

def test_duplicate_doctype_across_fragments_raises(self):  # 2 file tạm cùng khai "Lead"
def test_profiles_expand_packs(self):
	m = load_matrix()
	self.assertEqual(set(m.profile_roles("RP-KHO-TK")), {"Employee", "Projects User", "Stock User"})
	self.assertIn("Purchase Master Manager", m.profile_roles("RP-MH-TP"))
	self.assertEqual(m.roles["LK"].desk_access, 0)
	self.assertEqual(len(m.role_profiles), 20)
```

- [ ] **Step 2: Chạy, thấy hỏng** — `bench --site miyano run-tests --module erpnext.access.tests.test_cells` (rồi `test_matrix`). Kỳ vọng: `ModuleNotFoundError`.
- [ ] **Step 3: Viết `cells.py`, `matrix.py`, `roles.json`.** Trong `roles.json`, `"roles"` khóa theo mã của 3.1 (`"PM": {"names": ["Purchase Manager", "Purchase Master Manager"], "desk_access": 1}`). `"packs"`: `BASE`, `TBP`. `"role_profiles"`: đủ 20 profile của mục 4. `"combined_profiles"`: để `[]` (D19 chờ danh sách user).
- [ ] **Step 4: Chạy lại, thấy qua.**
- [ ] **Step 5: `pre-commit run --files <các file trên>`, để nguyên trong working tree.**

### Task 2: Mở rộng quy tắc G1, G2, G4, G7, G8

**Files:**
- Create: `erpnext/access/permissions/expand.py`, `erpnext/access/permissions/matrix/rules.json`
- Test: `erpnext/access/tests/test_expand.py`

**Interfaces:**
- Consumes: `Matrix`, `parse_cell`, `DocTypeInfo` (Task 1; test dựng trực tiếp `DocTypeInfo(...)`)
- Produces:
  - `PermRow = NamedTuple(role: str, permlevel: int, ptypes: frozenset[str], if_owner: bool)`
  - `expand_doctype(m: Matrix, doctype: str, info: DocTypeInfo) -> list[PermRow]`. Gộp các dòng trùng (role, level, if_owner). Scope `o` → `if_owner=True`. Scope `e d w pl c s g` không đổi DocPerm.
  - `rules.json`: `"g2_doctypes"` (10 DocType của G2), `"salary_doctypes"` (hàng lương ở 11.1), `"vw_r1_extra": ["Stock Ledger Entry", "Bin"]`, `"g1_exceptions": ["Employee Grievance"]`, `"g10_exceptions": ["Contact", "Address"]`, `"h5_skip_tables": {"Stock Entry": {"flag": "apply_putaway_rule", "tables": ["items"]}}` (R-15; Task 17 đọc)
- Quy tắc:
  - G1: với `matrix`, `ref_master`, `g1_only`, thêm SYS `read report` và VW `read print report`. VW thêm R1 nếu DocType nằm trong `salary_doctypes` hoặc `vw_r1_extra`.
  - G2: AP `read write submit` trên `g2_doctypes`, cộng R1 nếu là DocType lương. Gộp với ô AP ghi riêng trong bảng.
  - G7: dòng có `read` thì thêm `report`.
  - G8: `ref_master` → EMP `read`; `pda: true` → thêm PDA `read`.
  - G4: tập role có `import` trên bất kỳ DocType nào trở thành nguồn của dòng `create read write` + `if_owner` trên `Data Import`.

- [ ] **Step 1: Viết test hỏng**

```python
def test_po_gets_g1_g2(self):
	rows = expand_doctype(m, "Purchase Order", info("Purchase Order", submittable=1))
	self.assertIn(PermRow("MVL Approver", 0, frozenset({"read", "write", "submit", "report"}), False), rows)
	self.assertIn(PermRow("System Manager", 0, frozenset({"read", "report"}), False), rows)

def test_grievance_has_no_sys_vw(self):
def test_ref_master_gives_emp_and_pda_read(self):     # "Company"
def test_salary_slip_vw_reads_level1(self):
def test_owner_scope_becomes_if_owner(self):          # "Interview Feedback" EMP CRWS·o
def test_data_import_rows_for_importers(self):        # PM có I trên Supplier
def test_manager_code_expands_to_both_roles(self):    # PM → Purchase Manager + Purchase Master Manager
```

Test dùng một `Matrix` nhỏ dựng trong test (fixture `small_matrix()` trong `erpnext/access/tests/helpers.py`), không phụ thuộc ma trận thật.

- [ ] **Step 2: Chạy, thấy hỏng.**
- [ ] **Step 3: Viết `expand.py` và `rules.json`.**
- [ ] **Step 4: Chạy, thấy qua.**
- [ ] **Step 5: pre-commit, để nguyên trong working tree.**

### Task 3: Thông tin site và kiểm tra tĩnh

**Files:**
- Create: `erpnext/access/permissions/validate.py`
- Test: `erpnext/access/tests/test_validate.py`

**Interfaces:**
- Consumes: `DocTypeInfo`, `SiteInfo` (Task 1), `expand_doctype` (Task 2)
- Produces:
  - `@dataclass Problems(errors: list[str], warnings: list[str])`, `validate(m: Matrix, site: SiteInfo) -> Problems`
- Lỗi (`errors`), mỗi dòng nêu DocType/report và luật bị vi phạm:
  1. DocType trên site chưa có trong ma trận.
  2. S/X/A trên DocType không submittable; D trên DocType submittable; DocType submittable ở trạng thái `matrix` mà không role nào có S; Single có quyền khác R, W.
  3. G9: `high_permlevel_fields` chưa khai trong `permlevel` (bỏ qua `keep_standard`); ô `R1/W1/R2/W2` lệch với `permlevel[n].read/write`.
  4. R3: role của một report không có `read` trên `ref_doctype` (tính sau khi mở rộng).
  5. Mã role không có trong `roles`; report trong `reports` mà không có trên site.
  6. Workflow (luật 9.2.1–4): `workflow_state_field` khác `workflow_state`; state `doc_status 0` đầu tiên khác `Nháp`; state `doc_status 1` đầu tiên là `Từ chối`; thiếu `Đã hủy` (2) hoặc có transition dẫn vào `Đã hủy`; `update_field` ngoài ba cặp được phép (Leave Application `status`, Shift Request `status`, Expense Claim `approval_status`); transition tự duyệt (từ state đầu tiên tới state `doc_status 1`) mà đích khác state `doc_status 1` đầu tiên (R-17). Riêng WF-BT được miễn kiểm "thiếu Đã hủy" cho đến khi có C6, và chỉ ghi `warnings`.
- Cảnh báo (`warnings`): DocType có trong ma trận nhưng không có trên site; DocType có module thuộc app khác (Asset Repair).

- [ ] **Step 1: Viết test hỏng**: mỗi luật một test, dùng `SiteInfo` giả dựng tay. Ví dụ:

```python
def test_delete_on_submittable_is_error(self):
	p = validate(matrix_with({"Journal Entry": {"state": "matrix", "perms": {"AM": "CRWSXAD"}}}), site_with("Journal Entry", submittable=1))
	self.assertTrue(any("Journal Entry" in e and "D" in e for e in p.errors))

def test_unclassified_doctype_is_error(self):
def test_undeclared_high_permlevel_field_is_error(self):
def test_report_role_without_read_on_ref_doctype_is_error(self):
def test_first_submitted_state_must_not_be_rejected(self):
def test_update_field_on_controller_status_is_error(self):   # Sales Order.status
def test_self_approve_must_target_first_submitted_state(self):  # R-17
def test_foreign_app_doctype_is_warning_only(self):
```

- [ ] **Step 2: Chạy, thấy hỏng.**
- [ ] **Step 3: Viết `site.py`, `validate.py`.**
- [ ] **Step 4: Chạy, thấy qua.**
- [ ] **Step 5: pre-commit, để nguyên trong working tree.**

### Task 4: Ghi Custom DocPerm theo diff

**Files:**
- Create: `erpnext/access/permissions/docperm_sync.py`
- Test: `erpnext/access/tests/test_docperm_sync.py`

**Interfaces:**
- Consumes: `expand_doctype`, `SiteInfo`, `Matrix`
- Produces:
  - `managed_roles(m: Matrix) -> frozenset[str]`: mọi tên role trong `m.roles`, role ở 3.3 (`m.rules["retired_roles"]`, thêm vào `rules.json`), cộng `All` và `Desk User`.
  - `desired_rows(m: Matrix, doctype: str, info: DocTypeInfo) -> list[PermRow]`: kết quả `expand_doctype`, cộng các dòng chuẩn `All`/`Desk User` khi `info.app == "frappe"` và DocType không thuộc `g10_exceptions`, cộng `keep_standard_rows`.
  - `sync_docperms(m: Matrix, site: SiteInfo) -> collections.Counter` với khóa `"inserted"`, `"deleted"`.
- Hành vi:
  - Với `matrix`, `ref_master`, `g1_only`: gọi `setup_custom_perms(dt)`. Xóa những dòng của role được quản lý không có trong `desired_rows`; thêm những dòng còn thiếu. **Không bao giờ** đụng dòng của role ngoài.
  - Với `keep_standard`: không có dòng custom thì bỏ qua. Có dòng custom thì đưa về đúng DocPerm chuẩn cho các role được quản lý.
  - Cuối hàm gọi `frappe.clear_cache(doctype=dt)` một lần cho mỗi DocType có thay đổi.

- [ ] **Step 1: Viết test hỏng.** Test dùng ma trận nhỏ trên DocType thật ít dùng (`Supplier Scorecard Period`, `Contact`, `User`). `tearDownClass` gọi `frappe.clear_cache()`.

```python
def test_writes_expanded_rows(self):
def test_keeps_external_role_row(self):     # chèn trước 1 dòng "AssetCore Auditor"; sau sync vẫn còn
def test_second_run_changes_nothing(self):
	sync_docperms(m, site); c = sync_docperms(m, site)
	self.assertEqual((c["inserted"], c["deleted"]), (0, 0))
def test_contact_gets_no_all_row(self):     # ngoại lệ G10
def test_user_keeps_desk_user_select(self):
def test_permission_effective(self):        # frappe.has_permission("Supplier Scorecard Period", "create", user=<user chỉ có Purchase User>) is False
```

- [ ] **Step 2: Chạy, thấy hỏng.**
- [ ] **Step 3: Viết `docperm_sync.py`.**
- [ ] **Step 4: Chạy, thấy qua.**
- [ ] **Step 5: pre-commit, để nguyên trong working tree.**

---

## Đợt 2 — Các bước ghi còn lại (song song) và dữ liệu ma trận

### Task 5: Role, Role Profile, profile ghép

**Files:**
- Create: `erpnext/access/permissions/profiles.py`
- Test: `erpnext/access/tests/test_profiles.py`

**Interfaces:**
- Produces:
  - `sync_roles(m: Matrix) -> None`: tạo role mới (`is_custom = 1`, đặt `desk_access`); cập nhật `desk_access` của CUS, SUP, LK về 0. **Không** tắt role ở 3.3: việc đó thuộc cutover.
  - `sync_role_profiles(m: Matrix) -> None`: tạo hoặc sửa profile `RP-*` sao cho có đúng `profile_roles`.
  - `combined_profile_name(erp: str, assetcore: str) -> str` → `f"{erp}+AC-{assetcore}"`. Profile ghép = hợp role của profile ERP và profile assetcore hiện có trên site.

- [ ] **Step 1: Viết test hỏng**: RP-KHO-TK đúng 3 role; sửa tay thêm role vào RP-NV rồi sync thì role đó bị gỡ; profile ghép chứa role assetcore; LK `desk_access == 0`; chạy hai lần không sinh bản ghi mới.
- [ ] **Step 2–4: Chạy hỏng → viết → chạy qua.**
- [ ] **Step 5: pre-commit, để nguyên trong working tree.**

### Task 6: Schema — trường perm level, Custom Field, Property Setter

**Files:**
- Create: `erpnext/access/permissions/schema.py`
- Test: `erpnext/access/tests/test_schema.py`

**Interfaces:**
- Produces: `ensure_schema(m: Matrix) -> None`. Đây là **bước DDL duy nhất** và chạy đầu tiên trong sync (R-5). Nội dung:
  - Property Setter `permlevel` cho các trường "Miyano đặt thêm" ở 11.1. Trường bảng con đặt trên DocType con, ví dụ `Item Default`.
  - Custom Field `Sales Order.mvl_dung_gia_hd` (Check, `read_only`, `hidden`, `no_copy`).
  - Property Setter `reqd = 1` cho `Issue.issue_type`, `Employee.leave_approver`, `Employee.expense_approver`, `Business Trip.approver_coo`; `Employee.create_user_permission` có `default = 0` (11.7). **Không** đặt `reqd` cho `Employee.reports_to` (R-22, Q9).
  - Với mỗi DocType có trong `m.workflows`: tạo trước Custom Field `workflow_state` (Link → Workflow State, `hidden`, `allow_on_submit`, `no_copy`) nếu chưa có. Làm vậy để việc tạo Workflow ở Task 16 không sinh DDL nữa.
- Dữ liệu: `m.custom_fields` lấy từ `matrix/config.json` (Task 14). Test dùng ma trận nhỏ.

- [ ] **Step 1: Viết test hỏng**: Property Setter permlevel tồn tại với đúng giá trị; chạy hai lần không sinh bản ghi mới; `frappe.get_meta("Sales Order").get_field("mvl_dung_gia_hd").read_only == 1`. Test này commit DDL vì đó là trường thật. Đây là chủ ý: trường ẩn và vô hại.
- [ ] **Step 2–4: Chạy hỏng → viết → chạy qua.**
- [ ] **Step 5: pre-commit, để nguyên trong working tree.**

### Task 7: Report, Page, Workspace

**Files:**
- Create: `erpnext/access/permissions/ui_roles.py`
- Test: `erpnext/access/tests/test_ui_roles.py`

**Interfaces:**
- Produces:
  - `sync_report_roles(m: Matrix, site: SiteInfo) -> list[str]`: với mọi report trong `site.reports`, ghi Custom Role (`Role Permission for Page and Report`). Mặc định chỉ `MVL Khóa sửa`. Report có trong `m.reports` thì nhận đúng role ở đó, kèm `Prepared Report User` cho Stock Balance. Hàm trả về danh sách report đang khóa, dùng cho audit.
  - `sync_page_roles(m: Matrix) -> None`: theo 11.8 (`m.pages`).
  - `sync_workspace_roles(m: Matrix) -> None`: theo 11.6 (`m.workspaces`, khóa theo tên workspace trên site). Workspace không có trên site thì in cảnh báo.

- [ ] **Step 1: Viết test hỏng**:

```python
def test_unlisted_report_locked(self):   # "BOM Explorer"
	self.assertEqual(custom_roles("BOM Explorer"), ["MVL Khóa sửa"])
def test_listed_report_opens_for_roles(self):
	self.assertTrue(frappe.get_doc("Report", "Accounts Receivable").is_permitted(user_with("Sales User")))
	self.assertFalse(frappe.get_doc("Report", "Stock Balance").is_permitted(user_with("Stock User")))
def test_page_roles(self):               # lay-hang-pda → Stock User, Stock Manager, MVL Kho PDA
```

- [ ] **Step 2–4: Chạy hỏng → viết → chạy qua.**
- [ ] **Step 5: pre-commit, để nguyên trong working tree.**

### Task 8: Single `MVL Approval Limits`, Settings, Module Profile

**Files:**
- Create: `erpnext/setup/doctype/mvl_approval_limits/{__init__.py, mvl_approval_limits.json, mvl_approval_limits.py, test_mvl_approval_limits.py}`
- Create: `erpnext/access/permissions/settings.py`
- Test: `erpnext/access/tests/test_settings.py`

**Interfaces:**
- Produces:
  - DocType `MVL Approval Limits`: Single, module `Setup`, trường `h1`, `h2`, `h3` kiểu Currency, mỗi trường có mô tả theo D1. DocPerm trong JSON chỉ có `System Manager`; sync sẽ ghi đè theo 6.12.
  - `sync_settings(m: Matrix) -> list[str]`: áp `m.settings` (11.5). Mục nằm trong `m.settings["guarded"]` chỉ được áp khi hàm kiểm tra tương ứng trả `True`; nếu không, hàm trả về dòng audit. Các hàm kiểm tra: `no_negative_bins()`, `no_open_orders_with_rate_mismatch()`, `password_policy_ok()`. Bật 2FA theo mục "tự quyết".
  - `sync_module_profiles(m: Matrix) -> None`: Module Profile `MVL PDA` chặn mọi module trừ `Stock` và `Warehouse Operations`.

- [ ] **Step 1: Viết test hỏng**: `Accounts Settings.credit_controller == "Sales Manager"` sau khi sync; khi `no_negative_bins` bị patch trả `False` thì `allow_negative_stock` giữ nguyên và có dòng audit; Module Profile `MVL PDA` có `block_modules` gồm `Accounts` nhưng không có `Stock`.
- [ ] **Step 2–4: Chạy hỏng → viết → `bench --site miyano migrate` → chạy qua.**
- [ ] **Step 5: pre-commit, để nguyên trong working tree.**

### Task 9: User Permission, audit, `sync.run`, cờ bật

**Files:**
- Create: `erpnext/access/permissions/user_scope.py`, `erpnext/access/permissions/audit.py`, `erpnext/access/permissions/sync.py`
- Modify: `erpnext/hooks.py` (thêm `"erpnext.access.permissions.sync.after_migrate"` vào **cuối** `after_migrate`; do controller làm)
- Test: `erpnext/access/tests/test_sync.py`

**Interfaces:**
- Consumes: mọi hàm `sync_*`, `ensure_schema`, `validate`, `SiteInfo.from_db`, `sync_workflows` (Task 16; trước khi có Task 16 thì bước này là no-op)
- Produces:
  - `sync_user_permissions(m: Matrix) -> None`: dựng User Permission từ `m.user_scope` (`{"<email>": {"Warehouse": [...], "Price List": [...], "Issue Type": [...], "Customer": [...], "Supplier": [...]}}`) cộng `m.user_permission_rules` (Applicable For, Apply To All lấy theo mục 10). Xóa mọi User Permission có `allow` thuộc Employee, Department, Company.
  - `run_audit(m: Matrix, site: SiteInfo) -> list[str]`: 8 nhóm kiểm tra của Bước 3.8, thêm R-12 (profile ghép lệch) và R-22 (Employee đang làm việc thiếu `reports_to`, trừ một nút gốc).
  - `sync.is_enabled() -> bool` → `bool(frappe.conf.get("mvl_rbac_enabled"))`
  - `sync.run() -> None`. Thứ tự: `is_enabled` (sai thì in dòng "RBAC sync tắt" rồi thoát) → `load_matrix` → `SiteInfo.from_db` → `validate` (có lỗi thì `frappe.throw` liệt kê lỗi, **chưa ghi gì**) → `ensure_schema` → `sync_roles` → `sync_role_profiles` → `sync_docperms` → `sync_report_roles`/`sync_page_roles`/`sync_workspace_roles` → `sync_workflows` → `sync_settings` → `sync_module_profiles` → `sync_user_permissions` → in audit. Bọc toàn bộ trong `frappe.flags.in_rbac_sync = True`; cuối hàm gọi `audit_mail.send_sync_summary(counter)` (Task 22; trước đó là no-op).
  - `sync.after_migrate() -> None` (R-20): cũng là `run()`, nhưng khi validate có lỗi thì in danh sách lỗi kèm dòng "RBAC sync bỏ qua, chưa ghi gì" rồi **return**, không throw. Nhờ vậy hook `after_migrate` của hrms và assetcore vẫn chạy.

- [ ] **Step 1: Viết test hỏng**:

```python
def test_disabled_is_noop(self):         # patch frappe.conf; không có Custom DocPerm mới
def test_validation_error_stops_before_writes(self):
def test_after_migrate_entry_does_not_raise_on_errors(self):  # R-20: không ghi, không throw
def test_user_permission_from_scope(self):  # user STU → UP Warehouse "Stores - M", applicable_for "Stock Entry"
def test_removes_employee_user_permissions(self):
def test_after_migrate_has_sync_last(self):
	self.assertEqual(
		frappe.get_hooks("after_migrate", app_name="erpnext")[-1], "erpnext.access.permissions.sync.after_migrate"
	)
```

- [ ] **Step 2–4: Chạy hỏng → viết → chạy qua.**
- [ ] **Step 5: pre-commit, để nguyên trong working tree.**

### Task 9b: C2 — bỏ việc tự cấp quyền trong `after_migrate` (R-19)

Làm trước Task 15. Đây là điều kiện để migrate hai lần cho kết quả 0/0.

**Files:**
- Modify: `erpnext/einvoice/setup.py` (bỏ lời gọi `_grant_permissions()` ở dòng 110 và xóa hàm `_grant_permissions`)
- **Không sửa** `erpnext/supply_notification/setup.py`. Spec C2 nói sai: `setup_supply_notification` (dòng 29-39) không cấp quyền nào. Dòng `All` mà spec nhắc là DocPerm chuẩn trong JSON của 4 DocType supply notification, và Custom DocPerm của sync sẽ thay chúng (G10).
- Test: `erpnext/einvoice/tests/test_einvoice_roles.py`

- [ ] **Step 1: Viết test hỏng**: xóa một dòng Custom DocPerm của `Kế toán HĐĐT` trên `Fast EInvoice Document`, gọi `setup_einvoice()`, rồi assert dòng đó **không** được tạo lại.
- [ ] **Step 2–4: Chạy hỏng → sửa → chạy qua**, rồi chạy lại `erpnext.einvoice.tests.*`, mỗi lệnh một module.
- [ ] **Step 5: pre-commit, để nguyên trong working tree.** Các dòng quyền đang có trên site vẫn còn. Từ Task 15 trở đi, sync là nơi duy nhất ghi quyền.

### Task 10–14: Chép spec vào ma trận (5 subagent song song)

Mỗi task chỉ tạo **một** file JSON, theo đúng lược đồ của Task 1. Không viết code. Mọi task dùng chung các quy ước sau:

- Mỗi ô của bảng spec → `perms[<mã role>]`, bỏ phần phạm vi. Phạm vi `·o [e] [d] [w] [pl] [c] [s] [g]` → `scope[<mã>]`. `WF` không ghi (đã có S). `(G8)` → `"state": "ref_master"`, có `†` thì `"pda": true`. Ô `AP (G2)` không ghi.
- Mã viết tắt ở cột "Khác" (ví dụ `IC R; SU R; SUP R[s]`) tách thành từng role.
- Trường perm level: lấy ở 11.1 ghi vào `permlevel`, và **cũng** ghi `R1/W1` vào ô tương ứng. Validate sẽ đối chiếu hai chỗ.
- DocType `g1_only` ghi `{"state": "g1_only"}`.
- Tên DocType viết đúng như trên site, xem `dts.tsv` mà controller dựng bằng truy vấn Bước 1 vào scratchpad của **phiên đang thi công**, rồi đưa đường dẫn tuyệt đối vào prompt của từng subagent.
- Kiểm: subagent **không** chạy bench. Controller chạy Task 15 sau khi các file về đủ.

| Task | File | Nguồn trong spec |
|---|---|---|
| 10 | `matrix/doctypes_erpnext_scm.json` | 6.1–6.5, ghi chú 11.1 phần Item/Customer/Supplier/Warehouse/SLE/Bin, `ignore_pricing_rule` |
| 11 | `matrix/doctypes_erpnext_finance.json` | 6.6–6.11, 11.1 phần Timesheet |
| 12 | `matrix/doctypes_erpnext_setup.json` | 6.12, Phụ lục B (erpnext), Settings của module đang dùng theo cột "Ai ghi" ở 11.5 |
| 13 | `matrix/doctypes_hrms.json` | Mục 7, 11.1 phần HR, Phụ lục B (hrms) |
| 13b | `matrix/doctypes_frappe.json` | Mục 8, 11.1 phần User/Role Profile, Phụ lục B (frappe), danh sách `keep_standard` |
| 14 | `matrix/reports_ui.json` (`reports`, `pages`, `workspaces`) và `matrix/config.json` (`settings` + `guarded`, `custom_fields`, `user_permission_rules`, `module_profiles`) và `matrix/user_scope.json` (để `{}`, chờ Q4) | 11.2, 11.5–11.8, mục 10 |

- [ ] **Bước chung cho mỗi task:** chép xong, tự đếm số DocType/report đã ghi so với số dòng trong bảng nguồn, rồi báo con số đó cho controller.

### Task 15: Cổng phủ — ma trận thật sạch lỗi

**Files:**
- Test: `erpnext/access/tests/test_matrix_data.py`

- [ ] **Step 1: Viết test**

```python
def test_real_matrix_has_no_errors(self):
	p = validate(load_matrix(), SiteInfo.from_db())
	self.assertEqual(p.errors, [], "\n".join(p.errors))

def test_every_scoped_doctype_is_hooked(self):  # bổ sung ở Task 19
```

- [ ] **Step 2: Chạy.** Mỗi lỗi được trả về subagent của file tương ứng để sửa (sửa dữ liệu, không sửa luật). Lặp đến khi `errors == []`.
- [ ] **Step 3: Chạy thử sync** trên site test (Q8) với `mvl_rbac_enabled = 1`: chạy `bench --site <site> migrate` **hai lần** (đây chính là T45, cần Task 9b). Lần hai phải in `inserted 0, deleted 0` và không sinh email H4 nào.
- [ ] **Step 4: Để nguyên trong working tree.**

---

## Đợt 3 — Workflow, chốt chặn và hook

### Task 16: Builder workflow

**Files:**
- Create: `erpnext/access/permissions/workflows.py`, `erpnext/access/permissions/matrix/workflows.json` (đủ 15 workflow của 9.3)
- Test: `erpnext/access/tests/test_workflows.py`

**Interfaces:**
- Produces:
  - `LIMIT_EXPR = "float(frappe.db.get_value('MVL Approval Limits', None, '{f}') or 0)"`, `render_condition(raw: str) -> str` thay `{H1}`, `{H2}`, `{H3}` (R-1)
  - `g11_condition(doctype: str) -> str` (xem mục "tự quyết")
  - `build_workflow(m: Matrix, code: str, doctype: str) -> dict` (dict của doc Workflow). `override_status = 1`, `send_email_alert = 1`, `workflow_state_field = "workflow_state"`, `is_active = 1`. Transition **Mở lại** (Từ chối → Nháp, role người lập) tự sinh khi Từ chối có `doc_status 0`.
  - `workflow_name(code: str, doctype: str) -> str`
  - `sync_workflows(m: Matrix) -> None`: tạo Workflow State và Workflow Action Master còn thiếu; tạo hoặc cập nhật từng Workflow; thêm `workflow_state` vào list view (`in_list_view` qua Property Setter).
- Định dạng `workflows.json`: `{"WF-PO": {"doctypes": ["Purchase Order"], "states": [{"state", "doc_status", "allow_edit": <mã>, "update_field"?, "update_value"?}], "transitions": [{"from", "action", "to", "roles": [<mã>], "condition"?, "per_doctype_condition"?: {dt: cond}}]}}`. Thứ tự state đúng như 9.3.

- [ ] **Step 1: Viết test hỏng**:

```python
def test_limits_unset_does_not_raise(self):   # Review Focus 4
	frappe.db.set_single_value("MVL Approval Limits", "h1", None)
	po = make_po(total=1)                        # fixture tự dựng, nháp
	self.assertEqual([t.action for t in get_transitions(po)], ["Gửi duyệt"])  # user PU
def test_condition_compares_numbers(self):     # h1=100: PO 50 → "Duyệt", PO 150 → "Gửi duyệt"
def test_g11_appended_on_pending_states(self):
def test_hr_g11_checks_employee_user(self):    # Leave Application có thêm user_id
def test_first_states_obey_rules(self):        # validate(...) không còn lỗi workflow
def test_list_indicator_not_overridden(self):  # override_status == 1
```

- [ ] **Step 2–4: Chạy hỏng → viết → chạy qua.**
- [ ] **Step 5: pre-commit, để nguyên trong working tree.**

### Task 17: H5, H10, H11 — chốt chặn workflow phía server

**Files:**
- Create: `erpnext/access/workflow_guard.py`
- Modify: `erpnext/hooks.py`: thêm vào `doc_events["*"]` sẵn có `"before_validate": ["erpnext.access.workflow_guard.before_validate"]`, nối `"erpnext.access.workflow_guard.validate"` vào cuối list `"validate"` đang có, thêm `"before_submit": ["erpnext.access.workflow_guard.before_submit"]`, và đổi `"on_change"` thành list gồm hook supply notification đang có cộng `"erpnext.access.workflow_guard.on_change"`. Giữ nguyên các hook đang có. Do controller làm.
- Test: `erpnext/access/tests/test_workflow_guard.py`

**Interfaces:**
- Produces (mọi hàm thoát ngay nếu DocType không có workflow đang bật — dùng `frappe.model.workflow.get_workflow_name`, có cache — nếu user là `Administrator`, hoặc nếu có `doc.flags.ignore_permissions`. "State trước" là `doc._doc_before_save.workflow_state`. Chứng từ chưa có `_doc_before_save` thì state trước là state đầu tiên của workflow):
  - `before_validate(doc, method=None) -> None` (**H5**, R-15): chạy **trước** controller. Nếu user không có role `allow_edit` của state trước thì so mọi trường người dùng nhập được (bỏ `workflow_state`, trường `update_field` của state đích, trường `read_only`/`hidden`/`set_only_once`, gồm cả dòng bảng con). Bảng con trong `rules.json["h5_skip_tables"]` không so khi cờ tương ứng đang bật. Có trường thay đổi → `frappe.throw(_("Phiếu đang ở trạng thái {0}, không được sửa nội dung."))`. Ghi chú: `before_validate`/`validate` không chạy với `update_after_submit`. Ở các state `doc_status 1`, frappe tự giới hạn sửa vào trường `allow_on_submit`.
  - `validate(doc, method=None) -> None`: chạy **sau** controller, lúc tổng tiền đã được tính lại. Chỉ chạy khi state đổi:
    - **R-23** (kiểm trước): `doc_status` của state đích phải bằng `doc.docstatus`. Nếu không → `frappe.throw(..., frappe.PermissionError)`.
    - **R-16**: phải có ít nhất một transition từ state trước sang state mới, có `allowed` thuộc role của user, và `is_transition_condition_satisfied(t, doc)` đúng trên **bản đang lưu**. Không có → `frappe.throw(..., frappe.PermissionError)`.
    - **H10**: nếu state trước bắt đầu bằng `"Chờ"`: chặn khi user là owner (hoặc là user của `employee`). Chặn cả khi đã có Comment `comment_type = "Info"`, `owner = user`, nội dung bắt đầu bằng `"MVL-DUYET: Chờ"` trên chứng từ này (R-18). Khi cho qua, đặt `doc.flags.mvl_wf_step = (state trước, state mới)`.
  - `on_change(doc, method=None) -> None`: có `doc.flags.mvl_wf_step` thì `doc.add_comment("Info", f"MVL-DUYET: {cu} → {moi}")`. Chuỗi không dịch.
  - `before_submit(doc, method=None) -> None` (**H11**): chỉ áp khi `docstatus` 0→1 và state không đổi so với state trước. Cho qua nếu user có transition tự duyệt từ state trước tới một state `doc_status 1` mà điều kiện đúng **trên doc đang submit** (R-13). **Không gán `workflow_state`** (R-17): frappe tự gán state `doc_status 1` đầu tiên. Còn lại → `frappe.throw(_("Phải duyệt qua quy trình…"), frappe.PermissionError)`.

- [ ] **Step 1: Viết test hỏng** (khóa T19, T20, T24, T26, T30, T34, T51, T52):

```python
def test_api_submit_po_over_limit_blocked(self):           # T19
def test_api_submit_po_within_limit_passes_and_sets_state(self)  # state = "Đã duyệt" do frappe gán
def test_insert_then_submit_receive_payment_entry_passes(self)   # T51, đường của Bank Reconciliation Tool (R-17)
def test_api_edit_and_approve_in_one_call_rechecks_limit(self):  # R-16: PO nháp 1 đ → gửi 1 tỷ + "Đã duyệt" → chặn
def test_submit_with_pending_state_blocked(self):           # R-23: PO > H1, client.submit + "Chờ TP" → chặn, docstatus vẫn 0
def test_draft_save_into_submitted_state_blocked(self):     # R-23: lưu nháp với "Đã duyệt" → chặn
def test_approver_passes_when_controller_resets_posting_time(self):  # R-15: SI set_posting_time=0, AM duyệt Chờ KTT
def test_approver_passes_on_putaway_stock_entry(self):      # R-15 còn sót: SE Material Receipt apply_putaway_rule=1, STM duyệt
def test_edit_while_pending_blocked_even_for_owner(self):   # T26
def test_same_user_cannot_approve_two_steps(self):         # T30
def test_api_approval_leaves_marker_for_h10(self):         # R-18: bước 1 qua frappe.client.save, bước 2 qua apply_workflow → chặn
def test_system_generated_je_passes(self):                 # T24: doc.flags.ignore_permissions
def test_administrator_job_passes(self):                   # Review Focus 5
def test_amend_starts_from_draft(self):                    # T34
def test_cancel_of_pre_workflow_doc_allowed(self):         # Review Focus 3
```

- [ ] **Step 2–4: Chạy hỏng → viết → chạy qua.**
- [ ] **Step 5: pre-commit, để nguyên trong working tree.**

### Task 18: Cutover một lần (Bước 4, phần một lần của Bước 6, xử lý 9.4)

**Files:**
- Create: `erpnext/access/permissions/cutover.py`
- Test: `erpnext/access/tests/test_cutover.py`

**Interfaces:**
- Produces: `run(dry_run: int = 1, approved_bank_accounts: list[str] | None = None) -> list[str]`. Hàm trả danh sách việc đã làm (hoặc sẽ làm nếu `dry_run`). Các bước:
  1. Tắt `MVL Duyệt thanh toán`; xóa `SO Test Workflow` (9.4).
  2. `remap_workflow_states()`: Leave Application theo `status`; chứng từ `docstatus 2` → `Đã hủy`; chứng từ `docstatus 1` mà state trống → state `doc_status 1` đầu tiên; Bank Account trong `approved_bank_accounts` → `Đã duyệt`; Business Trip giữ nguyên.
  3. `retire_legacy()`: gỡ role 3.3 khỏi mọi user; đặt `disabled = 1` (COO chỉ tắt, không xóa); xóa User Type `Employee Self Service` sau khi gỡ role ESS; xóa 6 Role Profile ERP cũ cùng các profile của `regional/vietnam/role_profiles.py`.
- Gọi bằng `bench --site <site> execute erpnext.access.permissions.cutover.run --kwargs "{'dry_run': 0}"`.

- [ ] **Step 1: Viết test hỏng**: Leave Application `Approved` sau remap có `Đã duyệt`; chạy lần hai không đổi gì; `dry_run=1` không ghi gì; COO `disabled == 1` và vẫn tồn tại.
- [ ] **Step 2–4: Chạy hỏng → viết → chạy qua.**
- [ ] **Step 5: pre-commit, để nguyên trong working tree.**

### Task 19: H8 — phạm vi hồ sơ nhân viên `[e]`, `[d]`

**Files:**
- Create: `erpnext/access/scope.py`
- Modify: `erpnext/hooks.py`: thêm `permission_query_conditions` và `has_permission`, ghi cứng một dòng cho mỗi DocType có scope `e`/`d` (do controller làm)
- Test: `erpnext/access/tests/test_scope.py`; thêm `test_every_scoped_doctype_is_hooked` vào `test_matrix_data.py`

**Interfaces:**
- Produces:
  - `unscoped_roles(doctype: str, ptype: str) -> frozenset[str]`: tập role có `ptype` trên DocType mà không ghi scope `e`/`d`. Tính từ ma trận, cache trong tiến trình.
  - `visible_employees(user: str) -> tuple[str, ...] | None`: `None` nghĩa là không giới hạn. Luật (a), (b), (c) theo H8: Department Approver có xét Department con (`lft`/`rgt`); `leave_approver`, `expense_approver`, user của `reports_to` là `user`; luôn gồm chính nhân viên của user.
  - `has_permission(doc, ptype: str, user: str, debug: bool = False) -> bool | None` → `False` hoặc `None` (R-2)
  - `query_conditions(user: str, doctype: str) -> str` → `""` hoặc `` `tab{dt}`.`employee` in (...) ``; với DocType `Employee` thì dùng cột `name`.

- [ ] **Step 1: Viết test hỏng** (T01, T10, T11, T13, Review Focus 2). Fixture: 3 Employee (A thuộc bộ phận do DH làm trưởng, B thuộc bộ phận khác, C là chính user):

```python
def test_emp_sees_only_self(self):
def test_dh_sees_department_and_reportees(self):
def test_ktnv_reads_all_expense_claims_but_creates_only_own(self):   # T10 + RF2
def test_hu_cannot_read_others_expense_claim(self):                  # T11
def test_hook_never_returns_true(self):                              # R-2
	self.assertIsNone(has_permission(own_doc, "read", user))
```

- [ ] **Step 2–4: Chạy hỏng → viết → chạy qua.**
- [ ] **Step 5: pre-commit, để nguyên trong working tree.**

### Task 20: H1 (Contract theo `party_type`) và H9 (share khi giao việc)

**Files:**
- Create: `erpnext/access/contract_scope.py`, `erpnext/access/assign_share.py`
- Modify: `erpnext/hooks.py` (Contract: `permission_query_conditions`, `has_permission`; ToDo: `after_insert`, `on_update`, `on_trash`; do controller làm)
- Test: `erpnext/access/tests/test_contract_scope.py`, `erpnext/access/tests/test_assign_share.py`

**Interfaces:**
- Produces:
  - `contract_scope.allowed_party_types(user: str) -> tuple[str, ...] | None`: SU/SM → Customer; PU/PM → Supplier; HU/HM → Employee; AM, VW, AP, SYS → `None`. Có nhiều role thì lấy hợp.
  - `contract_scope.has_permission(doc, ptype, user, debug=False) -> bool | None`, `contract_scope.query_conditions(user, doctype) -> str`
  - `assign_share.SHARE_WRITE = {"Task"}`, `assign_share.SHARE_READ = {"Job Applicant", "Interview", "Training Program", "Training Event"}`
  - `assign_share.on_todo_change(doc, method=None) -> None`: ToDo đang Open thì share; chuyển `Cancelled` hoặc bị xóa thì gỡ share, trừ khi user còn một ToDo Open khác trên cùng chứng từ (R-6). `on_trash` chạy **trước** khi xóa dòng, nên truy vấn "còn ToDo Open khác" phải loại `name != doc.name`.

- [ ] **Step 1: Viết test hỏng**: T09; user PJU được giao Task thì ghi được Task đó và không đọc được Task khác; gỡ giao (`assign_to.remove`) thì mất quyền.
- [ ] **Step 2–4: Chạy hỏng → viết → chạy qua.**
- [ ] **Step 5: pre-commit, để nguyên trong working tree.**

### Task 21: H2 (giá theo Price List/Blanket Order, cờ `mvl_dung_gia_hd`) và H3 (Bank Account đã duyệt)

**Files:**
- Create: `erpnext/access/pricing_guard.py`, `erpnext/access/bank_account_guard.py`
- Modify: `erpnext/hooks.py`: `validate` của Quotation, Sales Order, Sales Invoice, Purchase Order, Purchase Invoice → `pricing_guard.validate`; `validate` của Payment Entry → `bank_account_guard.validate` (do controller làm)
- Test: `erpnext/access/tests/test_pricing_guard.py`, `erpnext/access/tests/test_bank_account_guard.py`

**Interfaces:**
- Produces:
  - `pricing_guard.expected_rate(doc, row) -> float | None`. Tra theo thứ tự (R-21):
    1. Dòng có chứng từ nguồn thì lấy `rate` của dòng nguồn: SI `so_detail` → Sales Order Item, `dn_detail` → Delivery Note Item; PI `po_detail` → Purchase Order Item, `pr_detail` → Purchase Receipt Item; SO `quotation_item` → Quotation Item; PO `supplier_quotation_item` → Supplier Quotation Item.
    2. Dòng có `blanket_order` thì lấy giá của Blanket Order Item.
    3. Còn lại lấy Item Price theo `price_list` của chứng từ, `uom`, `transaction_date`.
    Không tìm được giá thì `None`, tức là không kiểm.
  - `pricing_guard.validate(doc, method=None) -> None`: phía bán, bỏ qua nếu user có `Sales Manager`; phía mua, bỏ qua nếu có `Purchase Manager`. So `rate` và `discount_percentage` với giá chuẩn bằng `flt(..., precision)`. Lệch → `frappe.throw` nêu dòng. Trên Sales Order: `mvl_dung_gia_hd = 1` khi và chỉ khi mọi dòng có `blanket_order` và đúng giá HĐ.
  - `bank_account_guard.validate(doc, method=None) -> None`: `bank_account`/`party_bank_account` có `workflow_state != "Đã duyệt"` → chặn.

- [ ] **Step 1: Viết test hỏng**: T21, T22, T37; SM sửa giá thì qua; dòng không có Item Price thì không chặn; AU lập SI từ SO giá HĐ (khác Price List) thì qua, còn sửa `rate` trên SI đó thì bị chặn (R-21); PU lập PO từ Supplier Quotation có giá khác Price List thì qua.
- [ ] **Step 2–4: Chạy hỏng → viết → chạy qua.**
- [ ] **Step 5: pre-commit, để nguyên trong working tree.**

### Task 22: H4 (email kiểm toán) và H7 (Role Profile tạm)

**Files:**
- Create: `erpnext/access/audit_mail.py`, `erpnext/access/temp_profiles.py`
- Modify: `erpnext/hooks.py`: `doc_events` của User, Has Role, Role Profile, Custom DocPerm, Custom Role, User Permission, Workflow, MVL Approval Limits → `audit_mail.on_change`; `scheduler_events["daily"]` → `temp_profiles.expire` (do controller làm)
- Test: `erpnext/access/tests/test_audit_mail.py`, `erpnext/access/tests/test_temp_profiles.py`

**Interfaces:**
- Produces:
  - `audit_mail.recipients() -> list[str]`: user đang bật có Role Profile `RP-BGD-GDVH`.
  - `audit_mail.on_change(doc, method=None) -> None`: im lặng khi `frappe.flags.in_rbac_sync` (R-7). Với User: chỉ gửi khi đổi `roles`, `role_profile_name` hoặc `enabled`. Gửi bằng `frappe.sendmail(..., now=False)`.
  - `audit_mail.send_sync_summary(counter: Counter) -> None`: gửi một email khi `inserted + deleted > 0`.
  - `temp_profiles.parse_expiry(profile: str) -> datetime.date | None` (`RP-X+TMP-20261231` → `2026-12-31`), `temp_profiles.base_profile(profile: str) -> str`, `temp_profiles.expire() -> list[str]` (trả về danh sách user đã được đưa về profile gốc).

- [ ] **Step 1: Viết test hỏng**: T42 (dùng `Mailbox` theo mẫu `einvoice/tests/test_fast_approval.py`), T43; sync không sinh email lẻ.
- [ ] **Step 2–4: Chạy hỏng → viết → chạy qua.**
- [ ] **Step 5: pre-commit, để nguyên trong working tree.**

---

## Đợt 4 — Sửa code, bàn giao, nghiệm thu

### Task 23: C1, C3, C4 và R-9, R-10 (C2 đã làm ở Task 9b)

**Files:**
- Modify: `erpnext/warehouse_operations/vitri/{quet,xep,lay_hang,tem,…}.py` (hằng `VAI_TRO_*`, C1)
- Modify: `erpnext/einvoice/setup.py` (`is_chief_accountant` bỏ `System Manager`, C4)
- Modify: `erpnext/supply_notification/dispatch.py:419` (R-10)
- Modify: `erpnext/regional/vietnam/role_profiles.py`, `erpnext/regional/vietnam/go_live.py:285`, `erpnext/regional/vietnam/tests/test_go_live.py` (C3, R-9)
- Test: `erpnext/einvoice/tests/test_einvoice_roles.py` (**Modify**: file do Task 9b tạo, thêm test T44), `erpnext/warehouse_operations/tests/test_vai_tro_pda.py` (Create)

**Interfaces:**
- Produces: `go_live._check_role_profiles(company)` kiểm mọi profile trong `load_matrix().role_profiles` đều có trên site.

- [ ] **Step 1: Viết test hỏng**: T44 (`is_chief_accountant` của user chỉ có SYS là `False`); T46 phần quyền: user chỉ có `MVL Kho PDA` qua được kiểm tra role của `lay_hang`, `xep`, `quet`, còn user chỉ có SYS thì bị chặn.
- [ ] **Step 2: Chạy hỏng.**
- [ ] **Step 3: Sửa code.** Chạy lại các bộ test liên quan, mỗi lệnh một module: `erpnext.einvoice.tests.*` (bỏ qua 3 test đã hỏng từ trước, không phải do thay đổi này: `test_fast_folders.test_the_uploaded_xml_is_filed_with_the_invoice`, `test_fast_lookup.test_the_declared_number_comes_from_the_einvoice`, `test_fast_pdf.test_it_downloads_once_fast_has_had_a_minute`), `erpnext.warehouse_operations.tests.test_giao_dien`, `test_app_khoi_dong`, `erpnext.regional.vietnam.tests.test_go_live`, `erpnext.supply_notification.tests.*`.
- [ ] **Step 4 (H6): rà API whitelisted.** Chạy `grep -rn "@frappe.whitelist" -A 30 erpnext/{einvoice,supply_notification,debt_reconciliation,warehouse_operations,tbyt,regional/vietnam}` và tìm `frappe.get_all(` hoặc `ignore_permissions=True` trên dữ liệu người dùng cuối. Mỗi chỗ tìm được: đổi sang `frappe.get_list`/`check_permission`, hoặc ghi một dòng comment nêu lý do được miễn (dữ liệu hệ thống, đã kiểm quyền ở trên). Danh sách gửi kèm báo cáo task.
- [ ] **Step 5: pre-commit, để nguyên trong working tree.**

### Task 24: Bàn giao C5, C6 cho người phụ trách fork hrms

**Files:**
- Create: `docs/rbac/BanGiao_C5_C6_hrms.md`

- [ ] **Step 1:** Viết tài liệu bàn giao. Nội dung:
  - Từng thay đổi kèm file:dòng hiện tại: `APPROVER_BYPASS_ROLES = {"HR Manager"}`; `only_for(("HR Manager",))` ở `attendance_exempt.py:381, 391`; `setup_cong_tac_workflow.py` dùng role/transition WF-BT; `business_trip.json` thêm `Đã hủy` vào options và đặt `no_copy = 1`.
  - Test họ cần chạy: T34 (Business Trip), T45, T53.
  - Cảnh báo R-14: repo hrms đang có thay đổi chưa commit.
- [ ] **Step 2: Để nguyên trong working tree.**

### Task 25: Fixture user theo profile và quét toàn ma trận

**Files:**
- Create: `erpnext/access/tests/fixtures.py`, `erpnext/access/tests/test_matrix_sweep.py`

**Interfaces:**
- Produces: `make_profile_user(profile: str) -> str` (email `rbac-<profile>-<hash>@example.com`, có Employee liên kết nếu profile có EMP), `make_employee_for(user: str, department: str | None = None) -> str`

- [ ] **Step 1: Viết test**: với mỗi profile, với mỗi DocType ở trạng thái `matrix`/`ref_master`, với mỗi ptype trong `read write create delete submit cancel`, assert `frappe.has_permission(dt, ptype, user=u)` bằng đúng giá trị tính từ `expand_doctype` cộng role của profile. Ô có scope `e`/`d`/`o` chỉ kiểm mức DocType. Gom mọi chỗ lệch rồi in **một** lần.
- [ ] **Step 2: Chạy trên site test (Q8)** sau khi sync. Kỳ vọng 0 lệch.
- [ ] **Step 3: Để nguyên trong working tree.**

### Task 26: Bộ kịch bản bắt buộc T01–T57

**Files:**
- Create: `erpnext/access/tests/test_kich_ban_quyen.py` (T01–T15), `test_kich_ban_workflow.py` (T16–T38), `test_kich_ban_bao_cao.py` (T39–T41, T56, T57), `test_kich_ban_he_thong.py` (T42–T55)

- [ ] **Step 1:** Mỗi kịch bản là một test tên `test_tNN_<mô tả ngắn>`, assertion lấy đúng cột "Kết quả đúng". Kịch bản đã khóa ở task trước thì chỉ viết lại test gọi chung fixture; không lặp logic.
- [ ] **Step 2:** Những kịch bản không tự động được ghi `self.skipTest("UAT: …")` kèm lý do: T08 (giao diện workspace), T46b (giá trên trang PDA), T49 (ô chọn user trên UI). Ba kịch bản này chuyển sang checklist UAT ở Task 27.
- [ ] **Step 3: Chạy từng module trên site test.** Kỳ vọng: không có fail; các skip đúng như Step 2. T45 (T47 cần hrms C6) chạy sau khi hrms có C5, C6.
- [ ] **Step 4: Để nguyên trong working tree.**

### Task 27: Runbook go-live (Bước 0, 6)

**Files:**
- Create: `docs/rbac/RUNBOOK_GoLive_PhanQuyen.md`

- [ ] **Step 1:** Viết runbook theo thứ tự:
  1. Sao lưu (Bước 0).
  2. Dọn 2 Company test và Bin âm.
  3. Nhập `user_scope.json` và H1–H3.
  4. Bật `mvl_rbac_enabled`, migrate, xem audit.
  5. `cutover.run(dry_run=1)`, đọc kết quả, rồi chạy với `dry_run=0`.
  6. Gán Role Profile cho từng user (bảng user → profile do chủ đầu tư điền).
  7. Người dùng chạy `sudo supervisorctl restart frappe-bench-web: frappe-bench-workers:`.
  8. Checklist UAT (T08, T46b, T49 và một kịch bản cho mỗi bộ phận).
  9. Rollback: tắt cờ, khôi phục bảng đã sao lưu ở Bước 0.
- [ ] **Step 2: Để nguyên trong working tree.**

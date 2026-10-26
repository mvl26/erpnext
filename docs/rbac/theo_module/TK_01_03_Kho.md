# TK_01 – Phân quyền ERP Miyano – Kho, vị trí kho, PDA

> Trích nguyên văn từ `../TK_01_PhanQuyen_ERP_V2.1_AI.md` (V2.1, 23/10/2026). Không sửa nội dung; tài liệu gốc là nguồn sự thật. Khi cần thay đổi, sửa tài liệu gốc rồi tách lại.
> Ký hiệu, quy tắc G1–G11, hook H1–H11 và hướng dẫn triển khai: xem `TK_01_00_Nen_tang_chung.md`.

## Mục 3.1 – Danh mục role dùng trong ma trận (trích các dòng liên quan)

| Mã | Role | Loại | Desk | Ghi chú |
|---|---|---|---|---|
| STU | Stock User | chuẩn | 1 | gánh luôn phần Delivery User |
| STM | Stock Manager | chuẩn | 1 | gánh luôn phần Delivery Manager |
| QM | Quality Manager | chuẩn | 1 | |
| PDA | MVL Kho PDA | **mới** | 1 | chỉ thấy workspace "Quản lý kho" và 3 trang PDA (11.8) {D6} |
| PRU | Prepared Report User | chuẩn | 1 | xem kết quả báo cáo chạy nền (Stock Balance) |

## Mục 3.2 – Ràng buộc từ mã nguồn (trích các dòng liên quan)

**Role được code kiểm tra theo tên** (đổi tên hoặc bỏ khỏi profile thì chức năng ngừng chạy):

| Role | Nơi kiểm tra | Chức năng |
|---|---|---|
| System Manager, Stock Manager, Stock User | `erpnext/warehouse_operations/vitri/*.py` (hằng `VAI_TRO_*`) | quét, xếp, lấy hàng, in tem vị trí kho – sửa theo C1 |

**Code cho System Manager vượt quyền nghiệp vụ:**

| Nơi | Hành vi | Xử lý |
|---|---|---|
| `erpnext/warehouse_operations/vitri/*.py` | System Manager thao tác kho | Sửa C1 |
| `erpnext/stock/item_code_rule.py:490` `_may_rename` | System Manager luôn được đổi mã vật tư | Chấp nhận: khớp quy định đổi mã chỉ do IT-QT; để `Stock Settings.item_rename_role` trống |

**Code tự gán role.** Role Profile ghi đè toàn bộ role mỗi lần lưu User (mục 4), nên các role dưới đây phải nằm sẵn trong profile:

| Nơi | Hành vi | Hệ quả |
|---|---|---|
| `erpnext/setup/doctype/employee/employee.py:108` | Gán `Employee` cho user liên kết với nhân viên | Có sẵn trong BASE. KHO-PDA không có BASE nên profile gỡ lại |

## Mục 4 – Chân dung → Role Profile (trích các dòng liên quan)

| Chân dung | Role Profile | Roles |
|---|---|---|
| KHO-TK | RP-KHO-TK | BASE, STU |
| KHO-PDA | RP-KHO-PDA | PDA (không có BASE); Module Profile chỉ mở Stock, Warehouse Operations {D6} |
| KHO-TP | RP-KHO-TP | BASE, TBP, STU, STM, QM |

## Mục 6.3 – Kho

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

## Mục 6.4 – Vị trí kho (module Warehouse Operations – Miyano)

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

## Mục 9.3 – Đặc tả workflow (trích các dòng liên quan)

Quy ước:
- `(0)` `(1)` `(2)` là `doc_status`.
- Thứ tự state trong mỗi workflow đúng như liệt kê.
- Mọi transition từ "Chờ …" ngầm có điều kiện G11.
- Mọi workflow có transition **Mở lại**: Từ chối → Nháp, do role người lập thực hiện (nếu Từ chối có `doc_status 0`).
- Hạn mức `H1/H2/H3` viết tắt cho `frappe.db.get_value("MVL Approval Limits", None, "h1")`…

| Mã | DocType | States (theo thứ tự) | Lập | Sau submit |
|---|---|---|---|---|
| WF-SE | Stock Entry | Nháp(0), Chờ trưởng kho(0), Đã ghi sổ(1), Từ chối(0), Đã hủy(2) | STU, PDA | STM |
| WF-SR | Stock Reconciliation | Nháp(0), Chờ trưởng kho(0), Chờ KTT(0), Đã ghi sổ(1), Từ chối(0), Đã hủy(2) | STU, PDA | STM |

**Transition:**

| Workflow | Từ | Hành động | Đến | Role | Điều kiện (ngoài G11) |
|---|---|---|---|---|---|
| WF-SE | Nháp | Ghi sổ | Đã ghi sổ | STU; PDA | `doc.stock_entry_type == "Material Transfer"` |
| | Nháp | Gửi duyệt | Chờ trưởng kho | STU; PDA | `doc.stock_entry_type != "Material Transfer"` |
| | Chờ trưởng kho | Duyệt / Từ chối | Đã ghi sổ / Từ chối | STM | |
| WF-SR | Nháp | Gửi duyệt | Chờ trưởng kho | STU; PDA | |
| | Chờ trưởng kho | Duyệt | Đã ghi sổ | STM | `doc.difference_amount == 0` |
| | Chờ trưởng kho | Duyệt | Chờ KTT | STM | `doc.difference_amount != 0` |
| | Chờ KTT | Duyệt | Đã ghi sổ | AM | |
| | Chờ trưởng kho / Chờ KTT | Từ chối | Từ chối | STM / AM | |

## Mục 10 – User Permission (trích các dòng liên quan)

| Đối tượng | Áp cho | Cấu hình |
|---|---|---|
| Warehouse | STU, PDA | Kho được giao. Apply To All = 0; Applicable For: Stock Entry, Stock Reconciliation, Purchase Receipt, Delivery Note, Pick List, Material Request, Stock Ledger Entry, Bin, Batch Entry, Location Transfer, Location Balance, Location Ledger Entry |
| Stock Entry Type | PDA | Material Transfer (và loại cấp phát khác nếu cần); Applicable For: Stock Entry |

Ghi chú:
- User Permission Warehouse chỉ lọc danh sách theo trường kho ở đầu phiếu; khi mở phiếu, frappe kiểm tra cả trường kho trên các dòng. Phiếu chuyển giữa kho của STU và kho khác do người được giao cả hai kho hoặc STM lập.

## Mục 11.1 – Trường perm level (trích các dòng liên quan)

**Trường Miyano đặt thêm** (Property Setter):

| DocType | Trường | Level | Đọc | Ghi |
|---|---|---|---|---|
| Item | `valuation_rate` | 1 | AM | AM |
| Item (bảng Item Default) | `expense_account`, `income_account`, `buying_cost_center`, `selling_cost_center` | 2 | AU, AM | AM |
| Warehouse | `account` | 2 | AU, AM | AM |
| Stock Ledger Entry | `incoming_rate`, `outgoing_rate`, `valuation_rate`, `stock_value`, `stock_value_difference` | 1 | AM, VW | – |
| Bin | `valuation_rate`, `stock_value` | 1 | AM, VW | – |

**Trường đã ở perm level 1 sẵn – erpnext, hrms** (phải cấp lại vì Custom DocPerm thay thế dòng level 1 chuẩn, kể cả `All` R1):

| DocType | Trường | Đọc | Ghi | Lý do |
|---|---|---|---|---|
| Delivery Note, Purchase Receipt, Purchase Invoice | `ignore_pricing_rule` | không ai | không ai | Lấy theo chứng từ gốc |

Ghi chú:
- Không đặt perm level cho `rate` / `discount` trên dòng chứng từ. Với bản ghi mới, Frappe reset trường người dùng không có quyền ghi về giá trị mặc định, nên đơn giá bị xóa. Kiểm soát giá bằng H2. Stock Ledger Entry và Bin chỉ do hệ thống ghi nên đặt perm level an toàn.

## Mục 11.2 – Custom Role trên Report (trích các dòng liên quan)

| Nhóm | Report | ref_doctype | Roles |
|---|---|---|---|
| Giá vốn, giá trị tồn {D10} | Stock Balance (prepared report – thêm PRU), Stock Ledger, Stock and Account Value Comparison, Warehouse wise Item Balance Age and Value, Warehouse Wise Stock Balance, Item Prices, Supplier-Wise Sales Analytics, Incorrect Stock Value Report, Incorrect Serial No Valuation, Incorrect Balance Qty After Transaction, FIFO Queue vs Qty After Transaction Comparison, Stock Ledger Invariant Check, Stock Ledger Variance | Stock Ledger Entry | AM, VW |
| Giá vốn, giá trị tồn {D10} | Stock Ageing, Item Price Stock | Item | AM, VW (Item Price Stock thêm SM, PM) |
| Giá vốn, giá trị tồn {D10} | Stock Analytics | Stock Entry | AM, VW |
| Tồn kho số lượng | Stock Projected Qty, Itemwise Recommended Reorder Level, Stock Qty vs Serial No Count, Item Variant Details | Item | STU, STM, PU, PM, SU, SM, AU, AM, VW |
| Tồn kho số lượng | Batch-Wise Balance History, Batch Item Expiry Status, Available Batch Report, Available Serial No, Serial No Ledger, Product Bundle Balance | Stock Ledger Entry | STU, STM, PU, PM, SU, SM, AU, AM, VW |
| Tồn kho số lượng | Item Balance (Simple), Item Shortage Report | Bin | STU, STM, PU, PM, SU, SM, AU, AM, VW |
| Tồn kho số lượng | Serial No Status, Serial No Warranty Expiry, Serial No Service Contract Expiry | Serial No | STU, STM, PU, PM, SU, SM, AU, AM, VW |
| Tồn kho số lượng | Serial and Batch Summary, Incorrect Serial and Batch Bundle | Serial and Batch Bundle | STU, STM, AM, VW |
| Tồn kho số lượng | Total Stock Summary, Requested Items To Be Transferred | Stock Entry | STU, STM, PU, PM, AU, AM, VW |
| Tồn kho số lượng | Reserved Stock | Stock Reservation Entry | STU, STM, SU, VW |
| Tồn kho số lượng | Available Stock for Packing Items | Product Bundle | STU, STM, SU, SM, VW |
| Vị trí kho | Ton Kho Theo Vi Tri, Doi Soat Ton Vi Tri, Hang Chua Xep Vi Tri, Hang Nam Sai Vi Tri | Location Balance | STU, STM, VW |
| Bán hàng | Delivery Note Trends, Delayed Item Report, Delayed Order Report | Delivery Note | SU, SM, STU, STM, VW |
| Mua hàng | Purchase Receipt Trends | Purchase Receipt | PU, PM, STU, STM, VW |
| Mua hàng | Material Requests for which Supplier Quotations are not created, Requested Items to Order and Receive, Items To Be Requested | Material Request | PU, PM, STU, STM, VW |
| Chất lượng | Quality Inspection Summary | Quality Inspection | QM, STM, VW |
| Chất lượng | Review | Quality Action | QM, VW |

## Mục 11.4 – Thay đổi code (trích các dòng liên quan)

**Trong repo này (app erpnext):**

| Mã | File | Thay đổi |
|---|---|---|
| C1 | `erpnext/warehouse_operations/vitri/*.py` (hằng `VAI_TRO_*`) | Bỏ System Manager, thêm MVL Kho PDA vào các nhóm thao tác kho {D14}. Roles của các trang PDA ghi bằng Custom Role (11.8), không sửa JSON của Page |

## Mục 11.5 – Settings (trích các dòng liên quan)

| Settings | Trường | Giá trị | Hiện tại (23/10) | Ai ghi |
|---|---|---|---|---|
| Stock Settings | Allow Negative Stock | 0 – trước khi tắt, xử lý Bin có `actual_qty < 0` | 1 | AM |
| Stock Settings | Role Allowed to Over Deliver/Receive; Role Allowed to Create/Edit Back-dated Transactions | STM; STM (trường Link, chỉ nhận một role) {D15} | trống | AM |
| Stock Settings | Role Allowed to Edit Frozen Stock | AM | trống | AM |
| Stock Settings | Item Rename Role (Miyano) | trống (chỉ System Manager, theo code – 3.2) | trống | AM |
| Stock Reposting Settings | Notify Reposting Error to Role | AM | trống | AM |
| Module Profile | "MVL PDA" | chặn mọi module trừ Stock, Warehouse Operations; gán cho user KHO-PDA | | SYS |

## Mục 11.6 – Workspace (trích các dòng liên quan)

| Workspace (tên trên site) | Roles |
|---|---|
| Stock | STU, STM, PU, PM, SU, SM, AU, AM, VW |
| Quản lý kho | STU, STM, PDA (workspace mặc định của PDA) |
| Quality | QM, STU, STM, PU, PM, VW |

## Mục 11.8 – Page (trích các dòng liên quan)

Roles của Page ghi bằng Custom Role (sync). Page không có trong bảng thì giữ Roles chuẩn của frappe.

| Page | Roles mới | Roles hiện có trên site |
|---|---|---|
| lay-hang-pda, xep-hang-pda, quet-ma-tra-cuu | STU, STM, PDA | Stock User, Stock Manager, System Manager |
| dat-o-hang-loat | STU, STM | Stock User, Stock Manager, System Manager |

## Mục 13 – Bộ kiểm thử bắt buộc (trích các dòng liên quan)

**A. Quyền và phạm vi dữ liệu**

| # | Kịch bản | Kết quả đúng |
|---|---|---|
| T08 | PDA đăng nhập; mở `/app/sales-invoice`, `/app/stock-balance` | Chỉ thấy workspace Quản lý kho và 3 trang PDA; hai đường dẫn kia bị chặn |

**B. Workflow và luồng duyệt**

| # | Kịch bản | Kết quả đúng |
|---|---|---|
| T23 | STU ghi sổ Stock Entry Material Receipt / Material Issue | Chỉ chuyển sang Chờ trưởng kho |

**C. Báo cáo và perm level**

| # | Kịch bản | Kết quả đúng |
|---|---|---|
| T39 | STU mở Stock Balance, Stock Ledger, Gross Profit | Bị chặn |
| T40 | SU mở Accounts Receivable; STU mở Stock Projected Qty; HM mở Salary Register | Chạy được (G7 + Custom Role) |
| T41 | STU xem cột `valuation_rate`, `stock_value` của Stock Ledger Entry qua Report view | Cột bị ẩn |

**D. Hệ thống, sync, code**

| # | Kịch bản | Kết quả đúng |
|---|---|---|
| T46 | PDA (kho được giao) hoàn tất lấy hàng một Delivery Note có hàng serial/lô; quét tra cứu một Purchase Receipt; xếp hàng bằng Location Transfer. IT-QT gọi cùng API | PDA chạy được cả ba, Delivery Note được submit; IT-QT bị chặn (sau C1) |
| T46b | PDA sửa đơn giá trên Delivery Note khi lấy hàng | Bị chặn (Maintain Same Rate = Stop) |
| T48 | KHO-TK nhập Purchase Receipt có hàng quản lý serial/lô rồi submit; KHO-TP hủy phiếu đó | Cả hai chạy được (S/X trên Serial and Batch Bundle) |
| T52 | GĐVH duyệt Stock Reconciliation chênh lệch ≠ 0 ở bước Chờ trưởng kho, rồi duyệt tiếp Chờ KTT | Bước KTT bị H10 chặn |
| T56 | IT-QT mở MVL Salary Register; STU mở Item Prices, Warehouse Wise Stock Balance, Stock Analytics; DH mở Unpaid Expense Claim | Đều bị chặn (11.2) |

## Mục 14 – Điểm cần chốt (đã điền phương án mặc định) (trích các dòng liên quan)

| Mã | Nội dung | Mặc định |
|---|---|---|
| D6 | KHO-PDA | Giao diện PDA hiện là các desk Page (`erpnext/warehouse_operations/page/`), không phải portal, nên PDA phải là **System User** (desk = 1) bị khóa bằng Module Profile "MVL PDA" và Custom Role của Page (11.8). Nghỉ phép do NS-NV nhập hộ (HU có C trên Leave Application); cần tự phục vụ thì chuyển sang RP-KHO-TK. Phương án khác: làm giao diện portal cho PDA rồi mới chuyển PDA thành Website User |
| D10 | Giá trị tồn kho | Chỉ KT-KTT và BGĐ xem (Report + perm level trên SLE/Bin); Kho dùng báo cáo số lượng |
| D14 | Thao tác vị trí kho | Sửa code C1 |
| D15 | Giao dịch kho lùi ngày | Chỉ STM (trường chỉ nhận một role); AM điều chỉnh lùi ngày bằng Journal Entry |

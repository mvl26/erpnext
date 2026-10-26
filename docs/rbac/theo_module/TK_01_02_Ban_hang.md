# TK_01 – Phân quyền ERP Miyano – Bán hàng

> Trích nguyên văn từ `../TK_01_PhanQuyen_ERP_V2.1_AI.md` (V2.1, 23/10/2026). Không sửa nội dung; tài liệu gốc là nguồn sự thật. Khi cần thay đổi, sửa tài liệu gốc rồi tách lại.
> Ký hiệu, quy tắc G1–G11, hook H1–H11 và hướng dẫn triển khai: xem `TK_01_00_Nen_tang_chung.md`.

## Mục 3.1 – Danh mục role dùng trong ma trận (trích các dòng liên quan)

| Mã | Role | Loại | Desk | Ghi chú |
|---|---|---|---|---|
| SU | Sales User | chuẩn | 1 | |
| SM | Sales Manager + Sales Master Manager | chuẩn | 1 | luôn gán cùng nhau |
| CUS | Customer | chuẩn | **0** | |

## Mục 4 – Chân dung → Role Profile (trích các dòng liên quan)

| Chân dung | Role Profile | Roles |
|---|---|---|
| KD-NV | RP-KD-NV | BASE, SU, ST |
| KD-TP | RP-KD-TP | BASE, TBP, SU, SM, ST |
| NG-KH | RP-NG-KH | CUS |

## Mục 6.2 – Bán hàng

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

## Mục 9.3 – Đặc tả workflow (trích các dòng liên quan)

Quy ước:
- `(0)` `(1)` `(2)` là `doc_status`.
- Thứ tự state trong mỗi workflow đúng như liệt kê.
- Mọi transition từ "Chờ …" ngầm có điều kiện G11.
- Mọi workflow có transition **Mở lại**: Từ chối → Nháp, do role người lập thực hiện (nếu Từ chối có `doc_status 0`).
- Hạn mức `H1/H2/H3` viết tắt cho `frappe.db.get_value("MVL Approval Limits", None, "h1")`…

| Mã | DocType | States (theo thứ tự) | Lập | Sau submit |
|---|---|---|---|---|
| WF-SO | Sales Order | Nháp(0), Chờ KD-TP(0), Đã duyệt(1), Từ chối(0), Đã hủy(2) | SU | SM |

**Transition:**

| Workflow | Từ | Hành động | Đến | Role | Điều kiện (ngoài G11) |
|---|---|---|---|---|---|
| WF-SO | Nháp | Duyệt | Đã duyệt | SU | `doc.mvl_dung_gia_hd == 1` – cờ do H2 tính {D4} |
| | Nháp | Gửi duyệt | Chờ KD-TP | SU | `doc.mvl_dung_gia_hd != 1` |
| | Chờ KD-TP | Duyệt / Từ chối | Đã duyệt / Từ chối | SM | |

## Mục 9.4 – Workflow đang có trên site (trích các dòng liên quan)

Frappe chỉ chạy một workflow đang bật cho mỗi DocType.

| Workflow hiện có | DocType | Xử lý |
|---|---|---|
| SO Test Workflow (role Test Approver, All) | Sales Order | Xóa; thay bằng WF-SO |

## Mục 10 – User Permission (trích các dòng liên quan)

| Đối tượng | Áp cho | Cấu hình |
|---|---|---|
| Price List | PU: bảng giá mua; SU: bảng giá bán | Applicable For: Item Price (không Apply To All) |
| Customer | CUS bắt buộc (= chính khách hàng); SU tùy chọn khi KD-TP yêu cầu phân vùng | Apply To All = 1. Với SU: không lọc được Quotation, Opportunity (Dynamic Link) |

## Mục 11.1 – Trường perm level (trích các dòng liên quan)

**Trường Miyano đặt thêm** (Property Setter):

| DocType | Trường | Level | Đọc | Ghi |
|---|---|---|---|---|
| Customer | `credit_limits` | 1 | SM, AU, AM | AM |
| Customer, Supplier | `accounts`, `tax_category`, `tax_withholding_category` | 2 | AU, AM, SM (Customer), PM (Supplier) | AU, AM |

**Trường đã ở perm level 1 sẵn – erpnext, hrms** (phải cấp lại vì Custom DocPerm thay thế dòng level 1 chuẩn, kể cả `All` R1):

| DocType | Trường | Đọc | Ghi | Lý do |
|---|---|---|---|---|
| Quotation, Sales Order | `ignore_pricing_rule` | – | SM | Bỏ qua quy tắc giá – cùng tinh thần H2 |
| Delivery Note, Purchase Receipt, Purchase Invoice | `ignore_pricing_rule` | không ai | không ai | Lấy theo chứng từ gốc |

## Mục 11.2 – Custom Role trên Report (trích các dòng liên quan)

| Nhóm | Report | ref_doctype | Roles |
|---|---|---|---|
| Công nợ phải thu | Accounts Receivable, Accounts Receivable Summary, Customer Ledger Summary, Sales Payment Summary | Sales Invoice | AU, AM, VW, SU, SM |
| Công nợ phải thu | Customer Credit Balance | Customer | SM, AU, AM, VW |
| Bán hàng | Sales Register, Item-wise Sales Register, Sales Invoice Trends, Delivered Items To Be Billed, Inactive Sales Items, Customers Without Any Sales Transactions | Sales Invoice | SU, SM, AU, AM, VW |
| Bán hàng | Sales Analytics, Sales Order Analysis, Sales Order Trends, Item-wise Sales History, Payment Terms Status for Sales Order, Inactive Customers, Exponential Smoothing Forecasting, Sales Person-wise Transaction Summary, Sales Person Target Variance Based On Item Group, Territory Target Variance Based On Item Group | Sales Order | SU, SM, AU, AM, VW |
| Bán hàng | Pending SO Items For Purchase Request | Sales Order | SU, SM, PU |
| Bán hàng (hoa hồng) | Sales Partner Commission Summary, Sales Partner Target Variance based on Item Group, Sales Partner Transaction Summary, Sales Person Commission Summary | Sales Order | SM, AM, VW |
| Bán hàng (hoa hồng) | Sales Partners Commission | Sales Invoice | SM, AM, VW |
| Bán hàng | Quotation Trends, Lost Quotations | Quotation | SU, SM, VW |
| Bán hàng | Delivery Note Trends, Delayed Item Report, Delayed Order Report | Delivery Note | SU, SM, STU, STM, VW |
| Bán hàng | Customer Acquisition and Loyalty, Customer-wise Item Price | Customer | SU, SM, AM, VW |
| Bán hàng | Item-wise Price List Rate (Report Builder, lọc theo `[pl]`) | Item Price | SU, SM, PU, PM, AU, AM |
| Danh bạ | Address And Contacts, Addresses And Contacts, Dia Chi Giao Hang Thieu Nguoi Nhan | Address | SU, SM, PU, PM |
| Danh bạ | Doi Tac Thieu Email Lien He | Supplier | PU, PM, SU |

## Mục 11.3 – Hook (phân hệ `access` {D17}) (trích các dòng liên quan)

| Mã | Gắn vào | Nội dung | Bắt buộc |
|---|---|---|---|
| H2 | `validate` của Quotation, Sales Order, Sales Invoice, Purchase Order, Purchase Invoice | `rate`, `discount` từng dòng phải khớp Price List hoặc Blanket Order, trừ khi user có SM (bán) hoặc PM (mua). Trên Sales Order, đặt cờ `mvl_dung_gia_hd = 1` khi mọi dòng gắn Blanket Order và đúng giá HĐ (điều kiện WF-SO, D4) | ✓ |

## Mục 11.5 – Settings (trích các dòng liên quan)

| Settings | Trường | Giá trị | Hiện tại (23/10) | Ai ghi |
|---|---|---|---|---|
| Accounts Settings | Role allowed to bypass Credit Limit (`credit_controller`) | SM {D21}. Đang trống thì **không ai** submit được SO vượt hạn mức (`erpnext/selling/doctype/customer/customer.py:538`) | trống | AM |
| Selling Settings | Maintain Same Rate Throughout Sales Cycle | 1 – trước khi bật, rà đơn đang mở có hóa đơn khác giá SO | 0 | SM |
| Selling Settings | Role Allowed to Override Stop Action | SM | trống | SM |

## Mục 11.6 – Workspace (trích các dòng liên quan)

| Workspace (tên trên site) | Roles |
|---|---|
| Selling, Bán hàng | SU, SM, AU, AM, VW |

## Mục 11.7 – Custom Field và Property Setter (trích các dòng liên quan)

| DocType | Trường | Thiết lập | Lý do |
|---|---|---|---|
| Sales Order | `mvl_dung_gia_hd` (Check, mới) | `read_only = 1`, `no_copy = 1`, ẩn; H2 tính | Điều kiện WF-SO {D4} |

## Mục 13 – Bộ kiểm thử bắt buộc (trích các dòng liên quan)

**A. Quyền và phạm vi dữ liệu**

| # | Kịch bản | Kết quả đúng |
|---|---|---|
| T03 | CUS đọc Sales Order, Quotation của khách khác qua API | Bị chặn |
| T12 | SU mở danh sách Customer, có khách chưa đặt `default_price_list` | Thấy đủ khách (Strict = 0) |

**B. Workflow và luồng duyệt**

| # | Kịch bản | Kết quả đúng |
|---|---|---|
| T21 | SU sửa `rate` trên SO khác giá HĐ | H2 báo lỗi |
| T32 | SU submit SO vượt hạn mức tín dụng; SM submit cùng SO | SU bị chặn; SM chạy được |
| T33 | Mở list Sales Order, Sales Invoice, Payment Entry sau khi bật workflow | Chỉ báo vẫn là `status` của controller; `workflow_state` ở cột riêng |
| T37 | SO có cờ `mvl_dung_gia_hd = 1` và SO không có cờ | SU tự duyệt được SO thứ nhất; SO thứ hai chỉ Gửi duyệt sang Chờ KD-TP |

## Mục 14 – Điểm cần chốt (đã điền phương án mặc định) (trích các dòng liên quan)

| Mã | Nội dung | Mặc định |
|---|---|---|
| D4 | Khi nào KD-NV tự submit SO | Mọi dòng gắn Blanket Order và đúng giá HĐ (cờ `mvl_dung_gia_hd` do H2 tính); còn lại do KD-TP |
| D9 | Quotation | KD-NV submit trực tiếp, không qua duyệt |
| D18 | Installation Note | Dùng, quyền theo 6.2. Nếu nghiệm thu lắp đặt làm ở assetcore thì chuyển sang `g1_only` |
| D21 | SO vượt hạn mức tín dụng | `credit_controller = SM` (KD-TP quyết định). Phương án khác: AM, khi đó WF-SO cần bước KTT và AM cần S trên Sales Order |

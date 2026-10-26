# TK_01 – Phân quyền ERP Miyano – Mua hàng (gồm hồ sơ pháp lý TBYT)

> Trích nguyên văn từ `../TK_01_PhanQuyen_ERP_V2.1_AI.md` (V2.1, 23/10/2026). Không sửa nội dung; tài liệu gốc là nguồn sự thật. Khi cần thay đổi, sửa tài liệu gốc rồi tách lại.
> Ký hiệu, quy tắc G1–G11, hook H1–H11 và hướng dẫn triển khai: xem `TK_01_00_Nen_tang_chung.md`.

## Mục 3.1 – Danh mục role dùng trong ma trận (trích các dòng liên quan)

| Mã | Role | Loại | Desk | Ghi chú |
|---|---|---|---|---|
| PU | Purchase User | chuẩn | 1 | |
| PM | Purchase Manager + Purchase Master Manager | chuẩn | 1 | luôn gán cùng nhau |
| IM | Item Manager | chuẩn | 1 | chủ dữ liệu Item {D7} |
| IC | MVL Item Creator | **mới** | 1 | thay Item Manager cho MH-NV (không có D) |
| AP | MVL Approver | **mới** | 1 | bước duyệt Ban Giám đốc trong workflow; thay role COO |
| SUP | Supplier | chuẩn | **0** | |

## Mục 4 – Chân dung → Role Profile (trích các dòng liên quan)

| Chân dung | Role Profile | Roles |
|---|---|---|
| MH-NV | RP-MH-NV | BASE, PU, IC |
| MH-TP | RP-MH-TP | BASE, TBP, PU, PM, IM |
| NG-NCC | RP-NG-NCC | SUP |

## Mục 6.1 – Mua hàng

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

## Mục 6.5 – Hồ sơ pháp lý thiết bị y tế (module TBYT – Miyano)

| DocType | IC | IM | Khác |
|---|---|---|---|
| TBYT Document Type (G8) | | CRW | |
| TBYT Marketing Authorization, TBYT Regulatory Document | CRW | CRW | PU, PM, SU, SM, STM, QM R |

## Mục 9.3 – Đặc tả workflow (trích các dòng liên quan)

Quy ước:
- `(0)` `(1)` `(2)` là `doc_status`.
- Thứ tự state trong mỗi workflow đúng như liệt kê.
- Mọi transition từ "Chờ …" ngầm có điều kiện G11.
- Mọi workflow có transition **Mở lại**: Từ chối → Nháp, do role người lập thực hiện (nếu Từ chối có `doc_status 0`).
- Hạn mức `H1/H2/H3` viết tắt cho `frappe.db.get_value("MVL Approval Limits", None, "h1")`…

| Mã | DocType | States (theo thứ tự) | Lập | Sau submit |
|---|---|---|---|---|
| WF-PO | Purchase Order | Nháp(0), Chờ TP(0), Chờ BGĐ(0), Đã duyệt(1), Từ chối(0), Đã hủy(2) | PU | PM |

**Transition:**

| Workflow | Từ | Hành động | Đến | Role | Điều kiện (ngoài G11) |
|---|---|---|---|---|---|
| WF-PO | Nháp | Duyệt | Đã duyệt | PU | `doc.base_grand_total <= H1` (tự duyệt trong hạn mức) |
| | Nháp | Gửi duyệt | Chờ TP | PU | `doc.base_grand_total > H1` |
| | Chờ TP | Duyệt | Đã duyệt | PM | `doc.base_grand_total <= H2` |
| | Chờ TP | Duyệt | Chờ BGĐ | PM | `doc.base_grand_total > H2` |
| | Chờ BGĐ | Duyệt | Đã duyệt | AP | |
| | Chờ TP / Chờ BGĐ | Từ chối | Từ chối | PM / AP | |

## Mục 10 – User Permission (trích các dòng liên quan)

| Đối tượng | Áp cho | Cấu hình |
|---|---|---|
| Price List | PU: bảng giá mua; SU: bảng giá bán | Applicable For: Item Price (không Apply To All) |
| Supplier | SUP bắt buộc (= chính NCC) | Apply To All = 1 |

## Mục 11.1 – Trường perm level (trích các dòng liên quan)

**Trường Miyano đặt thêm** (Property Setter):

| DocType | Trường | Level | Đọc | Ghi |
|---|---|---|---|---|
| Customer, Supplier | `accounts`, `tax_category`, `tax_withholding_category` | 2 | AU, AM, SM (Customer), PM (Supplier) | AU, AM |

**Trường đã ở perm level 1 sẵn – erpnext, hrms** (phải cấp lại vì Custom DocPerm thay thế dòng level 1 chuẩn, kể cả `All` R1):

| DocType | Trường | Đọc | Ghi | Lý do |
|---|---|---|---|---|
| Supplier Quotation, Purchase Order | `ignore_pricing_rule` | – | PM | |
| Delivery Note, Purchase Receipt, Purchase Invoice | `ignore_pricing_rule` | không ai | không ai | Lấy theo chứng từ gốc |

## Mục 11.2 – Custom Role trên Report (trích các dòng liên quan)

| Nhóm | Report | ref_doctype | Roles |
|---|---|---|---|
| Công nợ phải trả | Accounts Payable, Accounts Payable Summary, Supplier Ledger Summary | Purchase Invoice | AU, AM, VW, PU, PM |
| Bán hàng | Pending SO Items For Purchase Request | Sales Order | SU, SM, PU |
| Bán hàng | Item-wise Price List Rate (Report Builder, lọc theo `[pl]`) | Item Price | SU, SM, PU, PM, AU, AM |
| Danh bạ | Address And Contacts, Addresses And Contacts, Dia Chi Giao Hang Thieu Nguoi Nhan | Address | SU, SM, PU, PM |
| Danh bạ | Doi Tac Thieu Email Lien He | Supplier | PU, PM, SU |
| Mua hàng | Purchase Analytics, Purchase Order Analysis, Purchase Order Trends, Item-wise Purchase History, Procurement Tracker | Purchase Order | PU, PM, AU, AM, VW (bỏ role Supplier hiện có) |
| Mua hàng | Purchase Register, Item-wise Purchase Register, Purchase Invoice Trends, Billed Items To Be Received, Received Items To Be Billed | Purchase Invoice | PU, PM, AU, AM, VW |
| Mua hàng | Purchase Receipt Trends | Purchase Receipt | PU, PM, STU, STM, VW |
| Mua hàng | Supplier Quotation Comparison | Supplier Quotation | PU, PM, VW |
| Mua hàng | Material Requests for which Supplier Quotations are not created, Requested Items to Order and Receive, Items To Be Requested | Material Request | PU, PM, STU, STM, VW |
| Mua hàng | Vat Tu Chua Co NCC Mac Dinh | Item | PU, PM, IM |
| TBYT | Tinh Trang Ho So TBYT | Item | IC, IM, PU, PM, SU, SM, STM, VW |

## Mục 11.3 – Hook (phân hệ `access` {D17}) (trích các dòng liên quan)

| Mã | Gắn vào | Nội dung | Bắt buộc |
|---|---|---|---|
| H2 | `validate` của Quotation, Sales Order, Sales Invoice, Purchase Order, Purchase Invoice | `rate`, `discount` từng dòng phải khớp Price List hoặc Blanket Order, trừ khi user có SM (bán) hoặc PM (mua). Trên Sales Order, đặt cờ `mvl_dung_gia_hd = 1` khi mọi dòng gắn Blanket Order và đúng giá HĐ (điều kiện WF-SO, D4) | ✓ |

## Mục 11.5 – Settings (trích các dòng liên quan)

| Settings | Trường | Giá trị | Hiện tại (23/10) | Ai ghi |
|---|---|---|---|---|
| Buying Settings | Maintain Same Rate; Action | 1; Warn (chênh giá PO–PR–PI có thật) | 1; Stop | PM |
| Buying Settings | Role Allowed to Override Stop Action | PM | trống | PM |

## Mục 11.6 – Workspace (trích các dòng liên quan)

| Workspace (tên trên site) | Roles |
|---|---|
| Buying | PU, PM, AU, AM, VW |

## Mục 13 – Bộ kiểm thử bắt buộc (trích các dòng liên quan)

**B. Workflow và luồng duyệt**

| # | Kịch bản | Kết quả đúng |
|---|---|---|
| T18 | PU duyệt PO > H1 trên form | Không có hành động Duyệt; chỉ Gửi duyệt sang Chờ TP |
| T19 | PU gọi `frappe.client.submit` cho PO > H1; AU gọi API submit JE; Data Import có "Submit After Import" | Bị chặn (H11) |
| T29 | MH-TP lập PO > H1, duyệt ở Chờ TP | MH-TP bị chặn; GĐVH duyệt được |
| T30 | GĐVH duyệt thay ở Chờ TP rồi duyệt tiếp Chờ BGĐ trên cùng PO | Bước BGĐ bị H10 chặn; BGD-GD duyệt được |
| T34 | Hủy rồi Amend một PO, một Business Trip đã duyệt | Phiếu hủy ở Đã hủy; phiếu Amend bắt đầu từ Nháp, lưu không lỗi (Business Trip: sau C6) |

## Mục 14 – Điểm cần chốt (đã điền phương án mặc định) (trích các dòng liên quan)

| Mã | Nội dung | Mặc định |
|---|---|---|
| D1 | Giá trị hạn mức H1 (PO MH-NV tự duyệt), H2 (PO MH-TP duyệt), H3 (chi tiền, chi phí KT duyệt) | **Chưa có – bắt buộc chốt**, BGĐ ban hành bằng văn bản |
| D7 | Chủ dữ liệu Item | MH-TP (Item Manager). MH-NV tạo, KHO-TP chỉ đọc |

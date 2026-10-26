# TK_01 – Phân quyền ERP Miyano – Kế toán (gồm HĐĐT, đối chiếu công nợ)

> Trích nguyên văn từ `../TK_01_PhanQuyen_ERP_V2.1_AI.md` (V2.1, 23/10/2026). Không sửa nội dung; tài liệu gốc là nguồn sự thật. Khi cần thay đổi, sửa tài liệu gốc rồi tách lại.
> Ký hiệu, quy tắc G1–G11, hook H1–H11 và hướng dẫn triển khai: xem `TK_01_00_Nen_tang_chung.md`.

## Mục 3.1 – Danh mục role dùng trong ma trận (trích các dòng liên quan)

| Mã | Role | Loại | Desk | Ghi chú |
|---|---|---|---|---|
| AU | Accounts User | chuẩn | 1 | |
| AM | Accounts Manager | chuẩn | 1 | |
| EI | Kế toán HĐĐT | có sẵn | 1 | lập nháp HĐĐT; code kiểm tra theo tên (3.2) {D22} |
| EIC | Kế toán trưởng HĐĐT | có sẵn | 1 | phát hành, hủy HĐĐT; code kiểm tra theo tên (3.2) {D22} |
| AP | MVL Approver | **mới** | 1 | bước duyệt Ban Giám đốc trong workflow; thay role COO |

## Mục 3.2 – Ràng buộc từ mã nguồn (trích các dòng liên quan)

**Role được code kiểm tra theo tên** (đổi tên hoặc bỏ khỏi profile thì chức năng ngừng chạy):

| Role | Nơi kiểm tra | Chức năng |
|---|---|---|
| Kế toán HĐĐT | `erpnext/einvoice/setup.py:23` | lập nháp, gửi khách, xem PDF hóa đơn điện tử |
| Kế toán trưởng HĐĐT | `erpnext/einvoice/issue.py:156`, `erpnext/einvoice/cancel.py:34` | phát hành, hủy hóa đơn điện tử |
| Accounts Manager, Accounts User | `erpnext/debt_reconciliation/constants.py:42` | đối chiếu công nợ |

**Code cho System Manager vượt quyền nghiệp vụ:**

| Nơi | Hành vi | Xử lý |
|---|---|---|
| `erpnext/einvoice/setup.py:405` `is_chief_accountant` | System Manager phát hành, hủy HĐĐT như Kế toán trưởng HĐĐT | Sửa C4 |

## Mục 4 – Chân dung → Role Profile (trích các dòng liên quan)

| Chân dung | Role Profile | Roles |
|---|---|---|
| KT-NV | RP-KT-NV | BASE, AU, EI {D12} |
| KT-KTT | RP-KT-KTT | BASE, TBP, AU, AM, EI, EIC, PRU {D12} |

## Mục 6.6 – Kế toán

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

## Mục 9.3 – Đặc tả workflow (trích các dòng liên quan)

Quy ước:
- `(0)` `(1)` `(2)` là `doc_status`.
- Thứ tự state trong mỗi workflow đúng như liệt kê.
- Mọi transition từ "Chờ …" ngầm có điều kiện G11.
- Mọi workflow có transition **Mở lại**: Từ chối → Nháp, do role người lập thực hiện (nếu Từ chối có `doc_status 0`).
- Hạn mức `H1/H2/H3` viết tắt cho `frappe.db.get_value("MVL Approval Limits", None, "h1")`…

| Mã | DocType | States (theo thứ tự) | Lập | Sau submit |
|---|---|---|---|---|
| WF-SI | Sales Invoice | Nháp(0), Chờ KTT(0), Đã ghi sổ(1), Từ chối(0), Đã hủy(2) | AU | AM |
| WF-PI | Purchase Invoice | như WF-SI | AU | AM |
| WF-PE | Payment Entry | Nháp(0), Chờ KTT(0), Chờ BGĐ(0), Đã ghi sổ(1), Từ chối(0), Đã hủy(2) | AU | AM |
| WF-JE | Journal Entry | Nháp(0), Chờ KTT(0), Đã ghi sổ(1), Từ chối(0), Đã hủy(2) | AU | AM |
| WF-BA | Bank Account (không submittable) | Nháp(0), Chờ KTT(0), Đã duyệt(0), Từ chối(0) | AU | – (Đã duyệt: `allow_edit` = LK) |

**Transition:**

| Workflow | Từ | Hành động | Đến | Role | Điều kiện (ngoài G11) |
|---|---|---|---|---|---|
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
| WF-BA | Nháp | Gửi duyệt | Chờ KTT | AU | |
| | Chờ KTT | Duyệt / Từ chối | Đã duyệt / Từ chối | AM | |
| | Đã duyệt | Sửa | Nháp | AU; AM | Muốn đổi số tài khoản, IBAN, đối tượng thì phải đưa về Nháp và duyệt lại; trong lúc đó H3 chặn dùng tài khoản |

Ghi chú:
6. **WF-JE:** JE do hệ thống sinh không đi qua transition. H11 cho qua khi có `ignore_permissions`, và frappe gán Đã ghi sổ. Nếu nguồn sinh JE nào không đặt `ignore_permissions` (kiểm bằng T24), thêm điều kiện loại trừ theo `voucher_type` vào H11, không nới lỏng workflow.

## Mục 9.4 – Workflow đang có trên site (trích các dòng liên quan)

Frappe chỉ chạy một workflow đang bật cho mỗi DocType.

| Workflow hiện có | DocType | Xử lý |
|---|---|---|
| MVL Duyệt thanh toán (role Kế toán tổng hợp, Kế toán trưởng) | Payment Entry | Tắt và thay bằng WF-PE |

## Mục 11.1 – Trường perm level (trích các dòng liên quan)

**Trường Miyano đặt thêm** (Property Setter):

| DocType | Trường | Level | Đọc | Ghi |
|---|---|---|---|---|
| Item (bảng Item Default) | `expense_account`, `income_account`, `buying_cost_center`, `selling_cost_center` | 2 | AU, AM | AM |
| Customer | `credit_limits` | 1 | SM, AU, AM | AM |
| Customer, Supplier | `accounts`, `tax_category`, `tax_withholding_category` | 2 | AU, AM, SM (Customer), PM (Supplier) | AU, AM |
| Warehouse | `account` | 2 | AU, AM | AM |

## Mục 11.2 – Custom Role trên Report (trích các dòng liên quan)

| Nhóm | Report | ref_doctype | Roles |
|---|---|---|---|
| Lương, thuế TNCN | Quyet Toan TNCN | GL Entry | AM, VW |
| Giá vốn, lợi nhuận | Gross Profit | Sales Invoice | AM, VW |
| Giá vốn, lợi nhuận | COGS By Item Group, Gross and Net Profit Report, Profitability Analysis | GL Entry | AM, VW |
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
| Hóa đơn điện tử | Doi Soat Hoa Don Dien Tu | Fast EInvoice Document | EI, EIC, VW |

## Mục 11.3 – Hook (phân hệ `access` {D17}) (trích các dòng liên quan)

| Mã | Gắn vào | Nội dung | Bắt buộc |
|---|---|---|---|
| H3 | `validate` của Payment Entry | Chỉ cho dùng Bank Account ở trạng thái Đã duyệt (WF-BA) | ✓ |
| H11 | `before_submit` chung cho DocType có workflow | Chặn `docstatus` 0→1 nếu không đi qua transition hợp lệ (state trước khi lưu và `workflow_state` mới không tạo thành transition của user). Cho qua trong hai trường hợp: (a) user có transition tự duyệt từ state hiện tại tới một state `doc_status 1` mà điều kiện đúng với chứng từ – khi đó gán `workflow_state` theo transition đó; (b) `doc.flags.ignore_permissions` (chứng từ hệ thống sinh – T24) | ✓ |

## Mục 11.4 – Thay đổi code (trích các dòng liên quan)

**Trong repo này (app erpnext):**

| Mã | File | Thay đổi |
|---|---|---|
| C2 | `erpnext/einvoice/setup.py` (`_grant_permissions`), `erpnext/supply_notification/setup.py` | Hai hàm chạy sau mỗi lần migrate và tự cấp quyền. Bỏ phần cấp quyền để sync là nguồn duy nhất |
| C4 | `erpnext/einvoice/setup.py` (`is_chief_accountant`) | Bỏ `"System Manager" in roles`; chỉ Kế toán trưởng HĐĐT phát hành, hủy HĐĐT |

## Mục 11.5 – Settings (trích các dòng liên quan)

| Settings | Trường | Giá trị | Hiện tại (23/10) | Ai ghi |
|---|---|---|---|---|
| Accounts Settings | Delete Accounting and Stock Ledger Entries on deletion of Transaction | 0 | | AM |
| Accounts Settings | Role Allowed to Over Bill; Role Allowed to Set Frozen Accounts; Role Allowed to Override Stop Action | AM; AM; AM | trống | AM |
| Accounts Settings | Role allowed to bypass Credit Limit (`credit_controller`) | SM {D21}. Đang trống thì **không ai** submit được SO vượt hạn mức (`erpnext/selling/doctype/customer/customer.py:538`) | trống | AM |
| Accounts Settings | Check Supplier Invoice Number Uniqueness | 1 | | AM |
| Company (Miyano) | Exception Budget Approver Role | AM | trống | AM |

## Mục 11.6 – Workspace (trích các dòng liên quan)

| Workspace (tên trên site) | Roles |
|---|---|
| Accounting, Financial Reports, Payables, Receivables | AU, AM, VW |
| Doi Chieu Cong No | AU, AM |

## Mục 13 – Bộ kiểm thử bắt buộc (trích các dòng liên quan)

**A. Quyền và phạm vi dữ liệu**

| # | Kịch bản | Kết quả đúng |
|---|---|---|
| T05 | SYS (IT-QT) tạo Payment Entry, Sales Invoice | Bị chặn |
| T06 | VW (BGD-GD) tạo Sales Invoice | Bị chặn |

**B. Workflow và luồng duyệt**

| # | Kịch bản | Kết quả đúng |
|---|---|---|
| T17 | AU submit Journal Entry | Chỉ chuyển sang Chờ KTT |
| T19 | PU gọi `frappe.client.submit` cho PO > H1; AU gọi API submit JE; Data Import có "Submit After Import" | Bị chặn (H11) |
| T22 | AU tạo Payment Entry dùng Bank Account chưa duyệt | H3 báo lỗi |
| T24 | JE khấu hao, đánh giá tỷ giá, bút toán lương do hệ thống sinh khi WF-JE bật | Ghi sổ được, state Đã ghi sổ |
| T31 | KT-KTT lập Payment Entry > H3 rồi duyệt ở Chờ KTT | Bị chặn (G11) |
| T33 | Mở list Sales Order, Sales Invoice, Payment Entry sau khi bật workflow | Chỉ báo vẫn là `status` của controller; `workflow_state` ở cột riêng |
| T38 | Payment Entry thu tiền khách (Receive) giá trị lớn | AU ghi sổ thẳng, không qua Chờ KTT |

**D. Hệ thống, sync, code**

| # | Kịch bản | Kết quả đúng |
|---|---|---|
| T44 | KT-KTT, KT-NV, IT-QT bấm phát hành HĐĐT | KT-KTT chạy được; KT-NV và IT-QT bị chặn (sau C4) |
| T51 | AU dùng Bank Reconciliation Tool tạo Payment Entry thu tiền; tạo Payment Entry chi > H3; tạo Journal Entry | Cái đầu chạy được; hai cái sau bị H11 chặn |
| T55 | AM sửa số tài khoản của Bank Account đã duyệt | Không sửa trực tiếp được; phải Sửa → Nháp → duyệt lại |

## Mục 14 – Điểm cần chốt (đã điền phương án mặc định) (trích các dòng liên quan)

| Mã | Nội dung | Mặc định |
|---|---|---|
| D1 | Giá trị hạn mức H1 (PO MH-NV tự duyệt), H2 (PO MH-TP duyệt), H3 (chi tiền, chi phí KT duyệt) | **Chưa có – bắt buộc chốt**, BGĐ ban hành bằng văn bản |
| D8 | "Các đề nghị thanh toán" | Expense Claim / Employee Advance; không dùng Payment Request |
| D12 | Hóa đơn điện tử | KT-NV có Kế toán HĐĐT (lập nháp); chỉ KT-KTT có Kế toán trưởng HĐĐT (phát hành, hủy) |
| D22 | Role HĐĐT trùng AU/AM | Giữ EI/EIC vì code einvoice kiểm tra theo tên. Phương án gọn hơn: sửa code dùng Accounts User/Accounts Manager và bỏ hai role |
| D23 | Tạo chứng từ ngay trong Bank Reconciliation Tool | Chỉ cho Payment Entry thu tiền hoặc chi ≤ H3 (khớp transition tự duyệt, H11). Payment Entry chi > H3 và Journal Entry phải lập thường, duyệt qua workflow, rồi đối soát. Phương án khác: cho qua toàn bộ, chấp nhận chi > H3 không qua duyệt |

# Thiết kế: Kiểm giá bán theo % lãi · Báo trước 7 ngày khi đổi giá · Đối soát PR ↔ PI → ĐNTT

| Mục | Nội dung |
|---|---|
| Hệ thống | Miyano ERP (fork ERPNext v15.83.0), erp.miyano.com.vn, site `miyano` |
| Nhánh | `feat/auto-check-selling-price-poc` (tách từ `feat/auto-check-selling-price`) |
| Ngày | 21/10/2026 |
| Trạng thái | **Thiết kế đã chỉnh theo số liệu production (đợt kiểm 1–4) — chưa triển khai.** Chưa có dòng code nào được viết. Còn mở: ánh xạ vai trò (không chặn code). P8: giả định giá trong bảng giá chưa gồm VAT |
| Tài liệu liên quan | `docs/FRD_Doi_soat_hoa_don_NCC_v1.0.docx` (FRD-MAP-01) · `docs/BA_ThongBao_TuThietLap_CR01_20260922.md` (Supply Notification) · `docs/BA_BienBanDoiChieuCongNo.md` |

---

## 1. Bối cảnh và vấn đề

Miyano mua vật tư y tế của khoảng 15 NCC và bán cho khách hàng (Himedic, Minh Tâm…). Luồng thực tế:

- **Bán:** NCC báo giá (Supplier Quotation) → Miyano báo giá cho khách (Quotation) → Sales Order → kiểm tồn → đủ hàng thì Delivery Note; thiếu hàng thì Purchase Order cho NCC.
- **Giao cho Himedic:** NCC giao thẳng, nhưng trên ERP vẫn làm **Purchase Receipt vào `Kho Himedic - M` rồi Delivery Note ra** (không dùng drop-ship chuẩn của ERPNext).
- **Mua:** PO → Purchase Receipt (PR) + hàng → Purchase Invoice (PI) → Payment Request (ĐNTT) → Payment Entry.

Ba vấn đề cần giải quyết:

| Mã | Vấn đề | Hiện trạng |
|---|---|---|
| **YC3** | Giá bán phải bằng giá nhập từ NCC × (1 + % lãi). Himedic lãi 1%; khách khác có thể 0,5%, 2%, hoặc khác theo từng mặt hàng | Kiểm bằng tay |
| **YC4** | Đổi giá bán cho Himedic phải báo trước 7 ngày | Không có kiểm soát; sửa giá có hiệu lực ngay |
| **YC5** | Đối soát PR với PI; khớp thì tạo ĐNTT, lệch thì báo bên sửa | Kế toán dò tay |

Cộng thêm một yêu cầu phát sinh trong quá trình phân tích:

| Mã | Vấn đề |
|---|---|
| **YC6** | Báo giá NCC gửi qua email, Zalo và đang phải nhập tay vào ERP. Cần cách tự động mà vẫn chính xác |

---

## 2. Nguyên tắc thiết kế

1. **Code đặt trong fork `apps/erpnext`**, sửa thẳng module liên quan theo `CLAUDE.md` của fork (phương án A đã chốt). Không tạo app riêng.
2. **Tận dụng tối đa cái đã có.** Không tạo trường, DocType hay module trùng chức năng. Chỉ thêm khi đã kiểm kê và xác nhận chưa có.
3. **Kiểm soát nằm ở server.** Client Script chỉ dùng để hiển thị trước cho người nhập; nó bị bỏ qua khi gọi API hoặc import dữ liệu.
4. **Hệ thống chỉ tạo chứng từ nháp.** Không tự Submit, không tự thanh toán. Mọi bước ghi sổ đều có người duyệt.
5. **Mọi ngoại lệ đều có dấu vết:** lý do, người duyệt, thời điểm.
6. **Chống trùng và chạy đồng thời** dựa vào khóa dòng trong cơ sở dữ liệu, không dựa vào việc nút bấm bị vô hiệu trên giao diện.

---

## 3. Những gì đã có trong hệ thống (kết quả kiểm kê code)

### 3.1 Cơ chế chuẩn ERPNext được dùng lại

| Cơ chế | Vị trí trong code | Dùng cho |
|---|---|---|
| Supplier Quotation → Quotation: nút tạo Quotation ghi `Quotation.supplier_quotation` | `erpnext/buying/doctype/supplier_quotation/supplier_quotation.py:311` | YC3: tìm giá gốc |
| Quotation → Sales Order: `prevdoc_docname`, `quotation_item` trên từng dòng SO | `erpnext/selling/doctype/quotation/quotation.py:448` | YC3: tìm giá gốc |
| `maintain_same_rate` (Buying, action Stop): chặn PO lệch SQ, PR lệch PO, PI lệch PO/PR (dung sai 0,01) | `erpnext/utilities/transaction_base.py:80-120` | YC3, YC5: giữ giá NCC xuyên suốt SQ → PI |
| `maintain_same_sales_rate` (Selling): chặn SO lệch Quotation | cùng chỗ trên | YC3 (có thể bật) |
| Item Price có `valid_from`/`valid_upto`; hệ thống chọn giá có `valid_from` mới nhất theo **ngày của chứng từ** | `erpnext/stock/get_item_details.py:1036-1067` | YC4: giá theo ngày SO là hành vi sẵn có |
| Item Price đã bật lịch sử thay đổi (`track_changes`) | `erpnext/stock/doctype/item_price/item_price.json:267` | YC4 |
| Thuế "đã gồm trong đơn giá" (`included_in_print_rate`); ERPNext tự tính `net_rate` | `erpnext/controllers/taxes_and_totals.py` | YC3: so trước thuế |
| Bảng Item Customer Detail (`customer_items`) trên Item: mỗi dòng là một cặp (khách, item) | `erpnext/stock/doctype/item_customer_detail/` | YC3: % lãi theo (khách, item) |
| PR item mang `purchase_order_item`; PI item mang `po_detail`/`pr_detail` | `purchase_receipt_item.json`, `purchase_invoice_item.json` | YC5: ghép dòng |
| Chặn hủy PR khi đã có PI Submit | `erpnext/stock/doctype/purchase_receipt/purchase_receipt.py:396-408` | YC5: nhánh sửa PR |
| `frappe.desk.form.assign_to.add` (tạo ToDo, tự bỏ qua ToDo trùng) | `frappe/desk/form/assign_to.py:42-93` | YC5: giao việc duyệt ĐNTT |
| `get_value(..., for_update=True)` / `get_doc(..., for_update=True)` (khóa dòng) | `frappe/database/database.py:476-523` | YC5: chống trùng |
| Cổng NCC: NCC tự nhập báo giá từ RFQ, hệ thống tạo Supplier Quotation | `erpnext/buying/doctype/request_for_quotation/request_for_quotation.py:431` | YC6 |

### 3.2 Tùy biến sẵn có của fork Miyano được dùng lại

| Thành phần | Vị trí | Dùng cho |
|---|---|---|
| **Supply Notification**: điểm thông báo cấu hình trên giao diện (New, Submit, Cancel, Value Change, Workflow Transition, Date Reminder, Manual); gửi được cho nội bộ và email liên hệ của khách/NCC; chống gửi trùng bằng nhật ký | `erpnext/supply_notification/` | YC4, YC5: mọi thông báo và nhắc việc |
| **Làm tròn VND**: thành tiền và tiền thuế làm tròn đồng nguyên theo từng dòng; Commercial Rounding; `round_row_wise_tax` | commit `4a31050`, patch `erpnext/patches/v15_0/set_vnd_rounding_settings.py` | YC5: đối soát 0 đồng không báo lệch giả |
| **Độ chính xác đơn giá**: theo cài đặt hệ thống (4 chữ số thập phân) | System Settings | YC3: làm tròn giá chuẩn |
| **Lô gắn NCC** (`lo_ncc.dien_ncc_tu_chung_tu`) | `erpnext/warehouse_operations/vitri/lo_ncc.py` | Không cần cho thiết kế cuối (xem 4.1.6) |
| **FRD-MAP-01**: Phiếu tiếp nhận hóa đơn, đọc file, khớp mặt hàng 4 tầng, tạo PI nháp | `docs/FRD_Doi_soat_hoa_don_NCC_v1.0.docx` (chờ phê duyệt, **chưa có code**) | YC5, YC6: nối tiếp, không làm bộ thứ hai |
| **Debt Reconciliation**: biên bản đối chiếu công nợ tổng theo kỳ | `erpnext/debt_reconciliation/` | Không trùng YC5 (không đối chiếu từng hóa đơn) |

### 3.3 Cái chưa có (phải thêm)

- Cấu hình % lãi theo khách và theo (khách, item). Không có trường nào tương tự.
- Bộ tính giá chuẩn, so giá, phân loại trạng thái, duyệt giá lệch.
- Quy tắc báo trước 7 ngày; khóa việc sửa đè giá đang hiệu lực.
- Kiểm chồng lấn khoảng ngày của Item Price (ERPNext chỉ chặn khi trùng y hệt cả hai ngày, `item_price.py:78-135`).
- Kiểm số lượng PI so với PR (ERPNext chỉ chặn **vượt tiền**, không kiểm số lượng).
- Chống tạo ĐNTT vượt hóa đơn ở **mọi bước**: ERPNext chỉ chặn vượt tổng **khi Submit** và chỉ cộng các bản **đã Submit**; **không chặn ở bản nháp, không có ràng buộc unique, không khóa dòng** (`payment_request.py:103-141`, `:762-786`; kiểm chứng V4 ở 3.4).

### 3.4 Phát hiện cần lưu ý — đã làm rõ và kiểm chứng

Kiểm chứng thực tế ngày 21/10/2026 trên site test `erpnext.localhost` (code fork, nhánh `feat/auto-check-selling-price-poc`). Script chạy trong một transaction và **rollback toàn bộ**; sau khi chạy, đếm lại còn 0 bản ghi thử và các cài đặt trở về giá trị cũ. Phát hiện #5 không chạy thử được vì tạo Workflow sinh DDL (thêm cột `workflow_state`), MariaDB tự commit nên không hoàn tác được; kết luận #5 dựa trên đọc code.

| # | Phát hiện | Bằng chứng | Kết quả kiểm chứng | Ảnh hưởng tới dự án | Việc phải làm trước / khi code |
|---|---|---|---|---|---|
| 1 | Quy tắc dự án ghi "mapper `make_payment_request` tự Submit" | `payment_request.py:654-662`; `public/js/controllers/transaction.js:393-414` | **Sai.** V4: gọi hàm không truyền `submit_doc` → ĐNTT **nháp** (`docstatus 0`, `status Draft`). Gọi lần hai → **dùng lại** bản nháp cũ, không tạo bản mới. (Khi `create_pr_in_draft_status = 0` thì hàm không lưu gì, chỉ trả bản chưa lưu) | Quy tắc thao tác ERP của dự án đang **cấm một công cụ an toàn** vì lý do không đúng; quy trình tạo ĐNTT tay đang tốn công hơn cần thiết | Sửa quy tắc số 6 trong bộ quy tắc dự án (`00. SKILL_RULES`) thành: "Nút/mapper tạo ĐNTT tạo **nháp** khi `create_pr_in_draft_status = 1`; kiểm lại trạng thái sau khi tạo". Thiết kế YC5 **vẫn tự tạo** ĐNTT bằng `new_doc` để không phụ thuộc cài đặt này |
| 2 | Payment Request chuẩn không có trường hạn thanh toán | `payment_request.json`; tài liệu `docs/05c_Spec_KyThuat_Plan_Thong_Bao.md` (D9) của nhóm cũng ghi "Payment Request **không có** trường hạn thanh toán" | Xác nhận theo code và theo tài liệu 05c | Thông báo ĐNTT (NTF-09) và YC5 phải tra hạn từ chứng từ gốc. Người dùng cho biết production **có** Custom Field trên Payment Request, nhưng tài liệu 05c (22–23/09) không thấy trường hạn | **Không thêm trường hạn** cho tới khi có danh sách Custom Field production (mục 10). Mặc định: lấy `due_date` của PI qua `reference_name`, giống cách NTF-09/NTF-11 đang làm |
| 3 | Payment Request: chống vượt tổng | `payment_request.py:103-141`, `:567-597`, `:762-786` | V4: tạo thêm một bản nháp bằng tay → **2 bản nháp, tổng 20.000 cho PO 10.000, không bị chặn**. Submit lần lượt: bản đầu OK, bản thứ hai **bị chặn** ("Total Payment Request amount cannot be greater than…"). Hai lần Submit **đồng thời**: chưa kiểm | Rủi ro thấp hơn đánh giá ban đầu: vượt tổng **bị chặn ở bước Submit nếu làm lần lượt**. Còn lại: nháp vượt tổng gây nhầm cho người duyệt; Submit đồng thời có thể lọt | Giữ thiết kế 6.3.8 (kiểm ở `validate`, tính cả nháp, khóa dòng PI). Bắt buộc có script kiểm đồng thời (S15) |
| 4 | Code gọi `.submit()` trực tiếp bỏ qua quyền duyệt của Workflow | `frappe/model/workflow.py:362-377` (`set_workflow_state_on_action` chỉ gán trạng thái docstatus 1 đầu tiên, không kiểm vai trò) | Chưa chạy thử (lý do ở trên); kết luận theo code | **Production đang có Workflow trên Sales Order và Payment Entry** (`docs/BA_ThongBao_TuThietLap_CR01_20260922.md`, D12). Mọi code của dự án — kể cả bulk action, script dữ liệu — gọi `.submit()` trên SO/PE sẽ đi vòng qua bước duyệt | Quy tắc code: **không gọi `.submit()`** trên chứng từ có Workflow; dùng `apply_workflow`. Bước duyệt giá lệch trên SO (YC3) phải **ghép vào Workflow SO hiện có** (điều kiện chuyển trạng thái hoặc kiểm `before_submit`), không dựng Workflow thứ hai. Cần định nghĩa Workflow SO trên production (mục 10) |
| 5 | Ô "Price Not UOM Dependent" trên Price List không có tác dụng ở server | `price_list.py:76` trả `price_not_uom_dependent`; `get_item_details.py:1455` đọc `price_list_uom_dependant` | **Xác nhận.** V1: giá 100/ĐVT kho, bán theo Box hệ số 10 → **1.000** cả khi ô tắt lẫn khi ô bật | Hành vi thực tế luôn là: giá nhập theo ĐVT kho × hệ số. Đây là hành vi đúng cho cách Miyano nhập giá. Rủi ro chỉ xảy ra nếu ai đó **bật ô này và tin rằng giá không bị nhân** | Không sửa lõi trong dự án này. Quy ước: **nhập Item Price theo ĐVT kho**, không bật ô này. Bộ kiểm giá YC3 tự quy đổi bằng `conversion_factor`, không dựa vào ô này. Có test G11 khóa hành vi |
| 6 | Giá riêng của khách có `packing_unit` trả về **0** khi số lượng = 0 hoặc không đúng bội số, không lùi về giá chung | `get_item_details.py:1113-1116` | **Xác nhận.** V2: giá chung 100, giá riêng 90 (`packing_unit` 5): số lượng 5 → 90; số lượng 3 → **0**; số lượng 0 → **0** | SO cho Himedic có thể ra **đơn giá 0** mà không báo lỗi. Nếu bộ kiểm giá bỏ qua dòng giá 0, lỗi này **lọt hoàn toàn** | Sửa thiết kế YC3: **chỉ bỏ qua hàng tặng (`is_free_item`)**; dòng có đơn giá 0 mà không phải hàng tặng → trạng thái **"Lệch"** (thêm case G16). Quy ước: không đặt `packing_unit` trên bảng giá Himedic trừ khi thật sự bán theo bội số |
| 7 | `validate_selling_price` chặn cứng | `selling_controller.py:281-368` | **Xác nhận.** V3: bán 99 khi giá mua gần nhất 100 → `ValidationError`, **kể cả Administrator** | Xung đột với 6.2.7 (bán giá cũ trong thời hạn báo giá khi giá NCC tăng); so với giá mua của **mọi NCC** nên có thể chặn sai | Giữ quyết định: **tắt khi lên Đợt 1**. Trước đó phải biết giá trị trên production (mục 10) |

### 3.5 Hiện trạng production (kết quả SQL chỉ-đọc, người dùng chạy ngày 21/10/2026)

| Thông tin | Giá trị production | Khác với giả định trước | Ảnh hưởng |
|---|---|---|---|
| Workflow đang bật | **Quotation** ("Quotation - Client Portal"), Lead, Business Trip. **Không có** trên Sales Order, Payment Entry (Sales Order chỉ còn trường `workflow_state` từ workflow cũ) | Có: tài liệu CR01 (22/09) ghi SO và PE có Workflow, nay không còn | Duyệt giá lệch ở SO làm bằng kiểm `before_submit`, không phụ thuộc Workflow. Quotation có Workflow: đã báo giá → "Gửi khách duyệt" (Sales User) → "Khách đã đồng ý" (docstatus 1). **Điểm cảnh báo sớm hợp lý nhất là bước "Gửi khách duyệt"** |
| Trạng thái trong Workflow Quotation | Transition trỏ tới "Miyano từ chối", "Báo giá hết hạn", "Đã báo hết", "Đã huỷ phần còn lại" nhưng bảng trạng thái chỉ liệt kê 4 trạng thái | — | Cần kiểm lại cấu hình Workflow (có thể kết quả bị cắt). Không chặn dự án |
| Hộp thư gửi đi mặc định | **sales@miyano.com.vn** (mặc định); info@miyano.com.vn | Có: không còn là hộp thư AssetCore | Email gửi Himedic và NCC đi từ sales@ — hợp lý |
| `packing_unit` trên Item Price | **0 dòng** | — | Rủi ro 3.4 #6 hiện chưa xảy ra; vẫn giữ quy tắc G16 để phòng |
| `validate_selling_price` | **0 (đã tắt)** | — | Không xung đột với YC4; không cần làm gì |
| `maintain_same_sales_rate` | 1 | — | Không có tác dụng thực tế vì **không SO nào đi từ Quotation** (xem dưới) |
| `maintain_same_rate` (Buying) | 1, nhưng action = **Warn** | **Có**: thiết kế đang giả định **Stop** | **SQ → PO → PR → PI chỉ cảnh báo khi lệch giá, không chặn.** Thiết kế YC3 ("giá NCC được giữ nguyên tới PI") và YC5 (đơn giá PI = PR) không được dựa vào cài đặt này |
| `pr_required` | **Yes** | Có: trước đoán No | Mọi PI hàng tồn kho **bắt buộc có PR** → YC5 (E7) phủ được gần như toàn bộ PI hàng hóa |
| `create_pr_in_draft_status` | 1 | — | Nút/mapper tạo ĐNTT tạo **nháp** trên production → xác nhận 3.4 #1: quy tắc dự án cần sửa |
| `check_supplier_invoice_uniqueness` | 0 | — | Nên bật (cấu hình, không code) |
| `round_row_wise_tax` | 1 | — | Đối soát 0 đồng không bị lệch giả do làm tròn thuế |
| `rounding_method` | Commercial Rounding | — | Đúng như thiết kế |
| `currency_precision` | **2**; `float_precision` trống (mặc định 3) | **Có**: người dùng mô tả đơn giá làm tròn 4 chữ số thập phân | **Đã làm rõ (đợt 2):** Property Setter đặt **4 chữ số** cho mọi trường đơn giá (`rate`, `net_rate`, `price_list_rate`…) trên Item Price, Supplier Quotation Item, Quotation Item, Sales Order Item, Purchase Receipt Item, Purchase Invoice Item. Thành tiền theo `currency_precision` = 2. Đúng mô tả của người dùng |
| Custom Field Payment Request | **`custom_thoi_han_thanh_toan`** (Thời hạn thanh toán, Date), `custom_nguoi_yeu_cau` (Link User), `custom_ten_nguoi_yeu_cau` | Có: đã có trường hạn | YC5 **dùng lại** `custom_thoi_han_thanh_toan` = `due_date` của PI và `custom_nguoi_yeu_cau`. **Không thêm trường mới** trên Payment Request |
| Custom Field Quotation / Quotation Item | `custom_nguon_gia` (Select: Bảng giá / Báo giá) trên dòng; `custom_nguon_don` (Nội bộ / Client Portal), `custom_de_xuat` (Portal De Xuat Mua), `custom_khoa_phong`, `custom_ngay_gui_khach_duyet`… trên phiếu | Có: đã có khái niệm "nguồn giá" | **Không tạo trường `nguon_gia_goc` trùng nghĩa** khi chưa hiểu `custom_nguon_gia`. Các trường này thuộc **cổng khách hàng (Client Portal)** — một app **không có trong repo này** |
| Custom Field Sales Order | `custom_request_id` (chống trùng đơn), `custom_yeu_cau_goc` (Portal Item Request), `custom_so_po_khach`, `custom_ten_don_hang`… | — | SO được sinh từ **yêu cầu trên cổng khách hàng** |
| Custom Field Customer | Chỉ các trường đối chiếu công nợ và `custom_ma_ngan` | — | Không trùng `kiem_gia_ban`, `ty_le_lai` |
| Vai trò | **"Duyệt giá Himedic"** (đã có), "Kế toán trưởng HĐĐT". **Không có** "Giám đốc", "Ban Điều hành", "Kế toán trưởng" thuần. Workflow Business Trip dùng vai trò **"COO"** | Có | **Không tạo vai trò "Duyệt giá bán" khi chưa biết "Duyệt giá Himedic" đang được dùng ở đâu.** Cần ánh xạ: Giám đốc = COO?; Kế toán trưởng = Accounts Manager hay "Kế toán trưởng HĐĐT"?; Ban Điều hành = ? |
| Dòng SO đã Submit đi từ Quotation | **0 / 321 dòng** (37 SO) | **Có — nghiêm trọng** | Thiết kế YC3 tìm giá gốc qua `SO → quotation_item → Quotation → supplier_quotation`. Với dữ liệu hiện tại, **100% dòng SO sẽ rơi vào "Chưa xác định giá gốc"**. Phải thiết kế lại cách nối SO với giá gốc (mục 3.6) |
| Scheduler | Job gần nhất 21/10/2026 15:24 | — | **Đang chạy** — nhắc việc YC4 dùng được |

### 3.6 Điểm thiết kế phải chốt lại sau khi có số liệu production

Cập nhật sau đợt kiểm thứ hai (21/10/2026).

| # | Điểm | Số liệu đợt 2 | Kết luận / khuyến nghị | Trạng thái |
|---|---|---|---|---|
| P1 | **Nối dòng SO với giá gốc** | Đợt 2: 0 SO đi từ Quotation; SQ chỉ 1 bản nháp. Đợt 3: **195/195 mặt hàng đã bán có giá trong bảng giá mua**; bảng giá mua gồm "Bảng giá mua" chung (244 dòng) và bảng riêng từng NCC "Mua - <NCC>" (có `supplier`); mọi dòng có `valid_from`. PO: 109/276 dòng đi từ SO, 2 dòng đi từ SQ. Người dùng: giá NCC gửi qua Zalo/email, nhập tay vào Supplier Quotation → PO | Giá gốc = Item Price bảng giá mua có hiệu lực tại ngày SO (ưu tiên NCC mặc định của mặt hàng); SQ Submit tạo dòng Item Price mới trong bảng giá mua của NCC; kiểm lại khi lập PO. Chi tiết 6.1.3 | **Đã chốt hướng** |
| P2 | `maintain_same_rate` = Warn | Code `transaction_base.py:80-120`: chỉ so khi chứng từ **được tạo từ chứng từ trước** (SQ→PO, PO→PR, PO/PR→PI), ngưỡng 0,01; Stop chặn ngay ở **Lưu** (cả bản nháp). Production: chỉ 2/276 dòng PO đi từ SQ | **Giữ Warn.** YC5 chặn PI lệch ở Submit (có lý do, người duyệt, nhật ký); kiểm giá PO so với giá gốc do YC3 (6.1.3 bước 5) | **Đã chốt** (người dùng 21/10/2026) |
| P3 | Vai trò duyệt | "Duyệt giá Himedic": không có trong Custom DocPerm, Server/Client Script, Workflow Transition, Workflow Document State; gán cho 4 user, trong đó **tiendj28@gmail.com là tài khoản ngoài công ty** | Nếu dùng ở đâu thì chỉ có thể trong code `miyano_portal`. **Không ghi cứng tên vai trò:** thêm ô "Vai trò duyệt giá lệch" trong Selling Settings, mặc định trỏ "Duyệt giá Himedic". Cần người dùng ánh xạ Giám đốc / Kế toán trưởng / Ban Điều hành (COO, Accounts Manager có sẵn) | Chờ người dùng |
| P4 | `custom_nguon_gia` | 7 dòng Quotation Item: 6 trống, 1 "Báo giá". Trường có cả trên Sales Order Item. Custom Field **không gắn module** | Hầu như không dùng → **không dựa vào** trường này để tìm giá gốc; không tạo trường trùng nghĩa | Đã chốt |
| P5 | Độ chính xác đơn giá | Property Setter = 4 trên mọi trường đơn giá liên quan | Giá chuẩn làm tròn 4 chữ số theo độ chính xác của trường (đọc bằng `get_precision`, không ghi cứng) | Đã chốt |
| P6 | Cổng khách hàng | App `miyano_portal` (module "Miyano Portal", workspace "Kho khách hàng"); có thêm app `miyano_pda` | "Client Portal" = `miyano_portal`, không có trên máy phát triển. Chỉ đọc trường của app này, không sửa | Đã chốt; cần biết nơi lưu mã nguồn |
| P8 | Giá trong bảng giá mua gồm hay chưa gồm VAT | Item Price và Price List không có trường cho biết giá gồm VAT | **Giả định mọi bảng giá (mua và "Bảng giá Himedic") nhập giá CHƯA gồm VAT.** Không thêm trường `gia_gom_thue` lúc này. Giá gốc từ Item Price = giá trước thuế; so với `net_rate` của dòng Quotation/SO khi dòng có thuế gồm trong đơn giá, với `rate` khi không. Nếu sau này có bảng giá gồm VAT → thêm ô `gia_gom_thue` trên Price List (6.1.4 đã chừa chỗ) | **Đã chốt** (người dùng 21/10/2026) |
| P7 | Tự cập nhật Item Price từ chứng từ | `auto_insert_price_list_rate_if_missing` = 0, `update_existing_price_list_rate` = 0; không có Client/Server Script trên Item Price, Price List | Hiện **không có rủi ro ghi đè**. Thêm vào danh sách kiểm khi triển khai: hai cài đặt này phải giữ 0 (nếu bật, `get_item_details.py:950-1015` ghi đè giá cũ, phá YC4) | Đã chốt |

**Hệ quả cho YC4 (từ số liệu đợt 3):** giá riêng của Himedic nằm ở **bảng giá riêng "Bảng giá Himedic"** (472 dòng, không dòng nào dùng trường `customer`). Vì vậy quy tắc báo trước 7 ngày gắn vào **Price List** (cài đặt trên bảng giá: bật báo trước, số ngày, khách nhận thông báo), không gắn vào `Item Price.customer`. Mốc tạo nháp đổi giá chính là **lúc thêm dòng Item Price mới vào "Bảng giá Himedic"**; mốc Submit SQ (E5) vẫn giữ nhưng chỉ đề xuất giá mới (giá mua × (1 + % lãi)) vào bảng giá chờ.

---

## 4. Quyết định nghiệp vụ đã chốt

| Mã | Quyết định |
|---|---|
| D1 | Giá bán = giá gốc × (1 + % lãi). Giá gốc = giá NCC báo cho Miyano. Himedic: 1% |
| D2 | Quy tắc giá áp theo **khách hàng** |
| D3 / C6 | Mặc định 1% cho **mọi khách**; mỗi khách có công tắc tắt kiểm và ô % lãi riêng; có thể đặt % riêng theo (khách, mặt hàng) |
| E1 / E1b | Có 2 loại báo giá: **Supplier Quotation** (NCC báo cho Miyano) và **Quotation** (Miyano báo cho khách như Himedic). Kiểm ở Quotation để cảnh báo sớm, **chốt ở Sales Order**. **Giá gốc lấy từ bảng giá mua** (Item Price `buying = 1`) có hiệu lực tại ngày SO; Supplier Quotation khi Submit ghi giá vào bảng giá mua (P1) |
| E2 (BA) | Giá đầu ra phải **cùng cách tính VAT** với giá đầu vào: NCC báo gồm VAT thì báo khách cũng gồm VAT. Hệ số × (1 + % lãi) áp trên **giá trước thuế** |
| C2 | Giá chuẩn làm tròn theo **độ chính xác đơn giá của hệ thống** (4 chữ số thập phân), Commercial Rounding; chênh 0 là khớp |
| C3 | Giá lệch: bắt buộc nhập lý do; Submit cần **vai trò duyệt giá lệch** (ô cài đặt trong Selling Settings, mặc định "Duyệt giá Himedic" — không tạo vai trò mới); lưu người duyệt và thời điểm. Người có quyền sửa % lãi được phép duyệt |
| C3 (bổ sung) | **Chỉ Giám đốc** (quyền cao nhất) được sửa % lãi. Không có luồng Kế toán đề xuất. Vai trò "Giám đốc" là ô cài đặt trong Selling Settings; người dùng chọn vai trò thật khi triển khai |
| E3 | Không có `valid_from` cho % lãi: % mới có hiệu lực khi được duyệt. Lịch sử nằm ở Version; mỗi dòng SO lưu lại % đã dùng |
| D4 | Quy tắc báo trước 7 ngày **chỉ áp cho Miyano → Himedic**, tính theo ngày lịch |
| D4-1 | Mốc tính là **ngày gửi thông báo từ ERP** |
| D4-2 | Báo dưới 7 ngày: xử lý **mức vừa phải** — cảnh báo, đánh dấu "Báo gấp", nhắc kế toán xin xác nhận của Himedic, theo dõi bằng báo cáo. **Không chặn, không tự lùi ngày hiệu lực, không cần duyệt**, vì Miyano còn phụ thuộc vào thời điểm NCC báo giá |
| D4-3 | **Mọi thay đổi giá**, kể cả giảm giá, đều phải báo trước |
| D4-4 | Himedic chịu giá tại **ngày SO** |
| D4-5 | Kênh xác nhận: **chỉ email** |
| Sửa giá | Giá được sửa trong **Price List / Item Price**. Mỗi lần đổi giá là **một dòng Item Price mới với `valid_from` khác**; **giá cũ giữ nguyên, không xóa**. Hệ thống tự chọn giá theo `valid_from` / `valid_upto` và ngày của chứng từ |
| E4 | Giá chưa gửi thông báo nằm ở **bảng giá chờ** riêng |
| E5 | Nháp đổi giá được tạo khi **Supplier Quotation Submit** (đề xuất vào bảng giá chờ). Mốc chính của quy tắc báo trước: **thêm dòng giá mới vào bảng giá có cài đặt báo trước** ("Bảng giá Himedic") |
| Nhắc việc | Theo bảng ở mục 6.2.5 |
| D5 | Luồng Himedic: PR vào `Kho Himedic - M` rồi DN; đối soát dùng luồng PR chuẩn |
| D6 | ĐNTT tự tạo **nháp** và giao việc cho người duyệt; không tự Submit |
| D7 | Dung sai đối soát PR ↔ PI = **0 đồng**, áp cho cả từng dòng và tổng |
| E7 | **Mọi PI có PR** đều phải đối soát và bị chặn Submit khi lệch, kể cả PI nhập tay |
| E8 | Ngoại lệ Submit PI khi còn lệch: **Kế toán trưởng hoặc Ban Điều hành** duyệt (vai trò là ô cài đặt trong Buying Settings) |
| E9 | Mặc định mỗi PI một ĐNTT thanh toán đủ; **cho phép chia đợt**, với điều kiện tổng các đợt ≤ hóa đơn |
| E10 | Thuế suất PI khác PR là **lệch, chặn Submit** |
| E6 | Nhập báo giá NCC: cổng RFQ cho NCC lớn + hộp thư báo giá dùng chung bộ tiếp nhận FRD-MAP-01 + chuyển tiếp từ Zalo. Chỉ tạo nháp, có người duyệt |
| Lộ trình | YC5 gộp vào lộ trình FRD-MAP-01: đối soát hóa đơn ↔ PO/HĐ khung trước, PR ↔ PI → ĐNTT sau |
| Cài đặt | `validate_selling_price` **giữ tắt** (production đã 0). `round_row_wise_tax`, `create_pr_in_draft_status` giữ bật (production đã 1); **bật** `check_supplier_invoice_uniqueness`. `maintain_same_rate` **giữ Warn** (P2). `auto_insert_price_list_rate_if_missing`, `update_existing_price_list_rate` **giữ tắt** (P7) |
| P1 | Giá gốc = Item Price của bảng giá mua có hiệu lực tại ngày SO, ưu tiên bảng giá của NCC mặc định của mặt hàng; khi lập PO có giá cao hơn giá gốc → cảnh báo |
| P2 | Giữ `maintain_same_rate` = Warn |

---

## 5. Lịch sử thay đổi thiết kế trong quá trình phân tích

Ghi lại để người đọc hiểu vì sao thiết kế cuối khác bản đầu.

| Bản trước | Bản cuối | Lý do |
|---|---|---|
| Giá gốc lấy từ hóa đơn NCC (PI), kiểm chốt ở Sales Invoice | Giá gốc lấy từ **Supplier Quotation**, kiểm chốt ở **Sales Order** | Người dùng yêu cầu so ở khâu báo giá. SQ → PO → PI đã được `maintain_same_rate` giữ đúng giá |
| Truy giá gốc theo lô khi PO tạo tay (C5) | **Bỏ** | Chuỗi SQ → Quotation → SO nằm trước PO, nên việc PO tạo tay không còn ảnh hưởng |
| Làm tròn giá chuẩn về đồng nguyên | Theo **độ chính xác đơn giá của hệ thống** (4 chữ số thập phân) | Hệ thống đã có cấu hình làm tròn; không đặt quy tắc riêng |
| So giá NET (trước thuế) | So **cùng kiểu thuế**, hệ số áp trên giá trước thuế | Xác nhận của BA (E2) |
| DocType riêng "Quy tắc lãi bán" có `valid_from` | Trường trên Customer + cột trên Item Customer Detail + mặc định ở Selling Settings; không `valid_from` | Nguyên tắc không tạo trùng; E3 |
| DocType riêng "Thông báo thay đổi giá" | **Dùng chính dòng Item Price** + bảng giá chờ | Giá được sửa trong Price List/Item Price; nguyên tắc không tạo trùng |
| Nháp đổi giá tạo khi PI Submit | Tạo khi **Supplier Quotation Submit** | E5, vì giá gốc nay lấy từ SQ |
| Bảng chênh lệch PR–PI đặt trên Phiếu tiếp nhận (DT-07) | Đặt **trên Purchase Invoice** | E7: PI nhập tay cũng phải đối soát; không phải chờ FRD-MAP-01 làm xong DT-07 |
| Unique index: mỗi PI một ĐNTT | **Khóa dòng + kiểm tổng ≤ hóa đơn**, tính cả ĐNTT nháp | E9: cho phép chia đợt |
| Báo dưới 7 ngày: tự lùi ngày hiệu lực + ngoại lệ có duyệt + báo cáo vi phạm kèm nháp điều chỉnh | **Chỉ cảnh báo, đánh dấu "Báo gấp", nhắc xin xác nhận, theo dõi bằng báo cáo** | Người dùng: không làm quá chặt vì Miyano còn phụ thuộc thời điểm NCC báo giá |
| Giám đốc sửa % lãi, hoặc Kế toán đề xuất và Giám đốc duyệt | **Chỉ Giám đốc** sửa % lãi | Người dùng chốt lại |
| Giá gốc tìm qua chuỗi SO → Quotation → Supplier Quotation | **Giá gốc = Item Price bảng giá mua tại ngày SO**; SQ Submit ghi vào bảng giá mua | Production: 0/321 dòng SO đi từ Quotation, chỉ 1 SQ nháp; 195/195 mặt hàng đã bán có giá mua (P1) |
| `maintain_same_rate` = Stop giữ giá NCC tới PI | **Giữ Warn**; YC5 và kiểm PO (YC3) tự kiểm | Production đang Warn; Stop chặn cả lưu nháp (P2) |
| Quy tắc báo trước gắn theo khách (`Item Price.customer`) | Gắn theo **Price List** | Giá Himedic nằm ở bảng giá riêng, không dòng nào dùng `customer` |
| Tạo vai trò "Duyệt giá bán", "Giám đốc" | **Ô cài đặt chọn vai trò**, không tạo vai trò mới | Production chưa có các vai trò này; chưa rõ ánh xạ tổ chức |

---

## 6. Thiết kế chi tiết

### 6.1 YC3: Kiểm giá bán theo % lãi

#### 6.1.1 Luồng

```
NCC gửi giá qua Zalo / email
        │  nhập tay (hoặc YC6 nhập tự động) vào Supplier Quotation → Submit
        ▼
Bảng giá mua "Mua - <NCC>"  ← dòng Item Price MỚI (valid_from = ngày hiệu lực), không ghi đè   = GIÁ GỐC
        │
        │  (cổng khách hàng miyano_portal / nhập tay)
        ▼
Quotation (Miyano → khách)    ← KIỂM SỚM: chỉ cảnh báo
Sales Order                   ← KIỂM CHỐT: so với giá gốc tại ngày SO; lệch thì phải có lý do + người duyệt
        │  "có SO rồi mới có PO"
        ▼
Purchase Order                ← KIỂM LẠI: giá PO > giá gốc đã dùng ở SO → cảnh báo "biên lãi bị phá"
        ▼
PR → PI                       ← YC5 đối soát (maintain_same_rate giữ Warn)
```

#### 6.1.2 Cấu hình % lãi

| Nơi lưu | Trường | Ghi chú |
|---|---|---|
| Selling Settings | `ty_le_lai_mac_dinh` = 1; công tắc bật/tắt toàn bộ tính năng; `vai_tro_sua_ty_le_lai` (Link Role, "Giám đốc"); `vai_tro_duyet_gia_lech` (Link Role, mặc định "Duyệt giá Himedic") | Chọn vai trò có sẵn, không tạo vai trò mới |
| Price List | (không thêm) | P8: giả định giá chưa gồm VAT. Chỉ thêm `gia_gom_thue` khi phát sinh bảng giá gồm VAT |
| Customer | `kiem_gia_ban` (mặc định bật); `ty_le_lai_rieng` (Check) + `ty_le_lai` — cần ô Check vì trường số không phân biệt "trống" với 0% | **Chỉ vai trò được chọn ở ô `vai_tro_sua_ty_le_lai` (Selling Settings) được sửa**; server kiểm khi lưu (chặn cả API, import), form hiển thị chỉ đọc với người khác |
| Item → bảng Item Customer Detail | Cột `ty_le_lai_rieng` + `ty_le_lai`; `ref_code` thôi bắt buộc (dòng chỉ khai % lãi không có mã hàng của khách; mỗi dòng phải có một trong hai) | Ghi đè % cho một cặp (khách, item). Cũng chỉ vai trò ở `vai_tro_sua_ty_le_lai` được sửa |

- **Thứ tự ưu tiên:** (khách, item) → khách → mặc định.
- **Lịch sử:** bật `track_changes` trên Customer và Item.
- **Ràng buộc:** % không âm; % quá lớn (ngưỡng cấu hình) thì cảnh báo.

#### 6.1.3 Tìm giá gốc cho một dòng SO (hoặc Quotation)

Theo P1 (đã chốt hướng 21/10/2026): **giá gốc = giá mua trong Item Price của bảng giá mua, có hiệu lực tại ngày SO.** Số liệu production: 195/195 mặt hàng đã bán đều có giá trong bảng giá mua; mọi dòng Item Price đều có `valid_from`.

1. Nếu dòng có liên kết Supplier Quotation (SO → `quotation_item` → Quotation → `supplier_quotation`, hoặc Quotation → `supplier_quotation`) → lấy đơn giá của dòng cùng mặt hàng trong SQ đó (quy đổi ĐVT bằng `conversion_factor`).
2. Nếu không: tìm Item Price có `buying = 1`, cùng mặt hàng, `valid_from` ≤ ngày SO và (`valid_upto` trống hoặc ≥ ngày SO), theo thứ tự ưu tiên:
   1. giá của **NCC mặc định** của mặt hàng (khớp `Item Price.supplier`). NCC mặc định lấy bằng hàm có sẵn của fork `erpnext.stock.doctype.item_supplier.item_supplier.get_default_supplier` (dòng `is_default` trong bảng Supplier Items, commit 50bab31) — **không** đọc `Item Default.default_supplier` (fork luôn để trống ô này);
   2. nếu không có NCC mặc định, hoặc NCC mặc định không có giá hiệu lực: dòng có `valid_from` **mới nhất** trong mọi bảng giá mua (kể cả "Bảng giá mua" chung).
   Quy đổi ĐVT như tra giá chuẩn (giá theo ĐVT kho × `conversion_factor`).
3. Không tìm được, hoặc có từ hai dòng cùng `valid_from` mới nhất với giá khác nhau → **"Chưa xác định giá gốc"**; người lập chọn giá tham chiếu bằng tay hoặc gửi duyệt.
4. Lưu lại trên dòng **nguồn giá gốc đã dùng** (tên Item Price hoặc SQ) để kiểm toán và để bước PO so lại.
5. **Kiểm thêm khi lập PO** (109/276 dòng PO đi từ SO): đơn giá PO (quy về ĐVT kho) > giá gốc đã dùng ở dòng SO tương ứng → cảnh báo "biên lãi bị phá", không chặn.

**Supplier Quotation → bảng giá mua:** quy trình đúng là NCC gửi giá qua Zalo/email → nhập Supplier Quotation → PO. Khi SQ Submit, tạo **dòng Item Price mới** trong bảng giá mua của NCC đó (`Mua - <NCC>`, `supplier` = NCC, `valid_from` = ngày hiệu lực của SQ); không ghi đè dòng cũ. Như vậy SQ nhập tay hay nhập tự động (YC6) đều đổ về cùng một nơi mà bộ kiểm giá đọc.

#### 6.1.4 Tính giá chuẩn và so sánh (theo E2, C2)

```
p   = độ chính xác của trường rate trên CHÍNH dòng đang kiểm (d.precision("rate")), Commercial Rounding
      (production 4; site test 2 — lượt kiểm cuối cho thấy ghi cứng 4 sẽ báo lệch giả 0,003 ở dòng ĐVT Hộp)
So trên ĐVT của dòng: giá chuẩn = round(NET_GOC(ĐVT kho) × conversion_factor × (1 + m), p)
m   = % lãi áp dụng
NET_GOC = giá gốc trước thuế, đã quy đổi ĐVT:
         - từ SQ: net_rate của dòng SQ
         - từ Item Price: price_list_rate; nếu Price List.gia_gom_thue = 1 thì chia (1 + thuế suất mua của mặt hàng) (P8)

Bước 1 — Cùng kiểu thuế:
  Trạng thái "đã gồm thuế" của nguồn giá gốc (SQ, hoặc Price List.gia_gom_thue) phải giống của Quotation/SO.
  Khác nhau → trạng thái "Lệch kiểu thuế".

Bước 2 — So giá, trên đúng con số người dùng nhập:
  Chưa gồm thuế: giá chuẩn = round(NET_GOC × (1 + m), p);              so với SO.rate
  Đã gồm thuế:   giá chuẩn = round(NET_GOC × (1 + m) × (1 + t), p);    so với SO.rate (t = thuế suất đầu ra)
  chênh lệch = SO.rate − giá chuẩn;  bằng 0 thì "Khớp"
```

#### 6.1.5 Trạng thái trên từng dòng

| Trạng thái | Ý nghĩa | Ở Quotation | Ở SO |
|---|---|---|---|
| Khớp | Chênh lệch 0 | — | Submit bình thường |
| Lệch | Chênh lệch khác 0 | Cảnh báo | Bắt buộc lý do + vai trò duyệt giá lệch |
| Lệch kiểu thuế | Nguồn giá gốc và SO khác cách tính VAT | Cảnh báo | Như "Lệch" |
| Đang trong thời hạn báo giá | Bán theo giá hiện hành của bảng giá Himedic trong khi có thông báo chờ hiệu lực (YC4) | Không cảnh báo | Submit bình thường; ghi chênh lệch để báo cáo |
| Chưa xác định giá gốc | Không có giá mua hiệu lực tại ngày SO, hoặc nhiều giá mơ hồ (6.1.3 bước 3) | Cảnh báo | Như "Lệch" |
| Bỏ qua | Khách tắt kiểm, **hàng tặng (`is_free_item`)**, phiếu trả hàng, khách nội bộ. **Dòng đơn giá 0 mà không phải hàng tặng KHÔNG được bỏ qua** (xem 3.4 #6) — xếp vào "Lệch" | — | — |

#### 6.1.6 Dữ liệu được lưu lại trên dòng (chỉ đọc, do server ghi)

`gia_goc`, `nguon_gia_goc` (Dynamic Link: tên Item Price hoặc dòng SQ), `ty_le_lai_ap_dung`, `gia_chuan`, `chenh_lech`, `trang_thai_gia`.

Ở cấp chứng từ: `ly_do_lech_gia`, `nguoi_duyet_gia`, `thoi_diem_duyet_gia`.

#### 6.1.7 Thời điểm chạy

- `validate` của Quotation và Sales Order: tính và lưu kết quả.
- `before_submit` của Sales Order: **tính lại** để không lọt trường hợp % lãi hoặc giá mua bị đổi trong lúc chứng từ đang mở; chặn nếu còn dòng lệch mà chưa được duyệt.
- `validate` của Purchase Order (BuyingController): với dòng có `sales_order_item`, so đơn giá PO (quy về ĐVT kho, cùng kiểu thuế) với `gia_goc` đã lưu ở dòng SO → cảnh báo, không chặn.
- `on_submit` của Supplier Quotation: tạo dòng Item Price mới trong bảng giá mua của NCC (`Mua - <NCC>`; chưa có thì dùng bảng giá mua trên SQ). Cùng `valid_from` mà khác giá → cập nhật dòng chưa từng được SO nào dùng, ngược lại tạo dòng mới.
- Đặt ở `SellingController`, theo hướng dẫn của fork: logic dùng chung cho nhiều chứng từ bán đặt ở controller chung.
- Client Script chỉ gọi một API chỉ-đọc để tô màu dòng ngay khi nhập.

### 6.2 YC4: Đổi giá bán cho Himedic và quy tắc báo trước 7 ngày

#### 6.2.1 Nguyên tắc

- Mỗi lần đổi giá = **tạo dòng Item Price mới** với `valid_from` khác. ERPNext cho một item có nhiều giá, miễn khác nhau ở ít nhất một trường.
- **Giá cũ giữ nguyên, không xóa.** Hệ thống tự nhận diện giá áp dụng theo `valid_from` / `valid_upto` và ngày của chứng từ: dòng có `valid_from` mới nhất mà ≤ ngày SO sẽ được chọn (`get_item_details.py:1045`). Vì vậy không bắt buộc đặt `valid_upto` cho dòng cũ.
- **Không cho sửa đè** `price_list_rate` của dòng đã có hiệu lực, vì sửa đè sẽ làm sai giá của các SO cũ.
- Áp cho các Price List được đánh dấu **`can_bao_truoc`** (Bảng giá Himedic).

#### 6.2.2 Bảng giá chờ (E4)

- Price List "Bảng giá Himedic – Chờ báo" (chỉ là dữ liệu, không thêm cấu trúc) chứa các giá **chưa gửi thông báo**. Vì vậy giá chưa báo **không bao giờ được áp nhầm**.
- Lý do: ERPNext áp mọi dòng Item Price nằm trong khoảng ngày; dòng để trống `valid_from` được hiểu là 2000-01-01 và áp ngay.

#### 6.2.3 Trường thêm trên Item Price

`trang_thai_thong_bao` (Chờ gửi / Đã gửi / Đã xác nhận), `ngay_gui_thong_bao` (hệ thống tự ghi, không sửa được), `ngay_xac_nhan`, `bang_chung_xac_nhan` (file đính kèm), `so_ngay_bao_truoc` (hệ thống tự tính = `valid_from` − ngày gửi), `bao_gap` (hệ thống tự đánh dấu khi số ngày báo trước < 7), `ly_do_bao_gap` (không bắt buộc).

#### 6.2.4 Luồng đổi giá

```
(1) Supplier Quotation Submit với giá làm thay đổi giá chuẩn Himedic   (E5)
      → hệ thống tự tạo dòng Item Price "Chờ gửi" trong bảng giá CHỜ
    hoặc Kế toán tự thêm dòng vào bảng giá chờ
(2) Kế toán bấm "Gửi thông báo đổi giá"
      → gom mọi dòng "Chờ gửi" của Himedic vào MỘT email (Supply Notification)
      → ghi ngay_gui_thong_bao = hôm nay, tính so_ngay_bao_truoc
      → nếu valid_from < ngày gửi + 7: CẢNH BÁO "báo trước X ngày, thiếu Y ngày", đánh dấu bao_gap
        (KHÔNG chặn, KHÔNG đổi valid_from người nhập)
      → chuyển các dòng sang Bảng giá Himedic chính thức, trạng thái "Đã gửi"
(3) Himedic xác nhận qua email → Kế toán ghi ngay_xac_nhan, đính bằng chứng → "Đã xác nhận"
    (xác nhận là bằng chứng bổ sung, KHÔNG phải điều kiện để giá có hiệu lực)
(4) Đến valid_from → ERPNext tự áp giá mới cho các SO có ngày ≥ valid_from.
    Dòng giá cũ vẫn nằm nguyên; các SO có ngày trước valid_from vẫn lấy giá cũ
```

#### 6.2.5 Nhắc việc (cấu hình Supply Notification)

| Điểm thông báo | Kích hoạt | Người nhận |
|---|---|---|
| Gửi thông báo đổi giá | Khi gửi (bước 2) | Email liên hệ Himedic, CC kế toán |
| Nhắc xác nhận | Ngày gửi + 2, chưa có xác nhận | Kế toán phụ trách |
| Báo gấp (dưới 7 ngày) | Khi gửi thông báo có dòng `bao_gap` | Kế toán phụ trách: nhắc xin Himedic xác nhận đồng ý áp giá sớm |
| Giá mới sắp hiệu lực | Ngày hiệu lực − 1 | Bán hàng và kế toán |
| Có báo giá NCC làm thay đổi giá chuẩn Himedic | Khi Supplier Quotation Submit (nháp vừa được tạo) | Kế toán |

#### 6.2.6 Báo dưới 7 ngày: xử lý mức vừa phải (D4-2)

Miyano còn phụ thuộc vào thời điểm NCC báo giá, nên hệ thống **nhắc nhở, không ép buộc**:

| Mức | Cách làm |
|---|---|
| Cảnh báo | Khi lưu dòng giá và khi gửi thông báo, hiện cảnh báo màu cam: "Giá áp dụng từ dd/mm, chỉ báo trước X ngày (thiếu Y ngày so với 7 ngày)". Người dùng vẫn lưu và gửi được |
| Đánh dấu | Hệ thống tự ghi `so_ngay_bao_truoc` và đánh dấu `bao_gap`. `ly_do_bao_gap` để người dùng ghi nếu muốn, không bắt buộc |
| Nhắc việc | Supply Notification nhắc kế toán xin Himedic xác nhận đồng ý áp giá sớm (mục 6.2.5) |
| Theo dõi | Báo cáo "Thông báo đổi giá báo gấp": liệt kê các dòng `bao_gap`, số ngày thiếu, đã có xác nhận của Himedic hay chưa, số SO đã dùng giá đó |

**Không áp dụng:** chặn lưu, tự lùi ngày hiệu lực, bắt buộc duyệt, tự tạo nháp điều chỉnh cho Himedic.

#### 6.2.7 Xung đột giữa giá × 1,01 và thời hạn 7 ngày

Khi giá NCC tăng, giá chuẩn Himedic tăng ngay, nhưng giá bán chỉ được đổi sau 7 ngày. Xử lý:

1. Nháp đổi giá được tạo tự động ngay khi Supplier Quotation Submit, để rút ngắn thời gian chờ.
2. Dòng SO bán theo giá hiện hành khi đang có thông báo chờ hiệu lực nhận trạng thái **"Đang trong thời hạn báo giá"**. Trạng thái này không cần duyệt, nhưng phần chênh được ghi để báo cáo lỗ do thời hạn báo giá.
3. **Giữ tắt `validate_selling_price`** (production đã tắt). Nếu bật, bước 2 sẽ bị chặn cứng khi giá bán cũ thấp hơn giá mua mới.

#### 6.2.8 Các kiểm tra bổ sung trên Item Price

- Chặn sửa đè giá đang có hiệu lực của bảng giá `can_bao_truoc`.
- Chặn thêm giá thẳng vào bảng giá chính thức mà không qua bảng giá chờ (chặn ở server, nên chặn được cả import và API).
- Kiểm chồng lấn khoảng ngày cho bảng giá `can_bao_truoc`.
- Không cho xóa dòng giá đã từng có hiệu lực.

### 6.3 YC5: Đối soát PR ↔ PI → ĐNTT (Giai đoạn B, nối tiếp FRD-MAP-01)

#### 6.3.1 Luồng sau khi gộp

```
FRD-MAP-01 (Giai đoạn A)                         Yêu cầu 5 (Giai đoạn B)
Hóa đơn → Phiếu tiếp nhận → đọc dữ liệu           PI nháp (từ Phiếu tiếp nhận HOẶC nhập tay — E7)
→ khớp 4 tầng → PI nháp ───────────────────────►     │
                                                     ▼
                                          Đối soát PR ↔ PI (0 đồng, từng dòng + tổng)
                                             ├─ Khớp ─► Kế toán Submit PI
                                             │             └─► (cùng transaction) tạo ĐNTT NHÁP + giao việc
                                             └─ Lệch ─► ghi bảng chênh lệch → nhánh (a)/(b1)/(b2)
                                                         → sửa → tự đối soát lại
```

#### 6.3.2 Ghép dòng

- Dòng PI có `po_detail`. Bộ đối soát tìm dòng PR có `purchase_order_item` = `po_detail` và **gắn `pr_detail`**.
- Một dòng PO nhận qua nhiều PR: phân bổ theo số lượng chưa lập hóa đơn.
- Có từ hai cách ghép trở lên: chuyển xử lý tay (giống BR-10 của FRD).
- PI tạo bằng nút từ PR thì đã có sẵn `pr_detail`.

#### 6.3.3 Tiêu chí so

| Tiêu chí | Quy tắc | Ghi chú |
|---|---|---|
| Mặt hàng, ĐVT | Trùng (sau quy đổi sang ĐVT kho) | Phải thêm |
| Số lượng | Số lượng PI = số lượng PR thực nhận chưa lập hóa đơn | **ERPNext không kiểm**, phải thêm |
| Đơn giá | Chênh 0, cùng kiểu thuế | `maintain_same_rate` = Stop đã chặn; bộ đối soát ghi nhận |
| Thuế suất | Trùng; khác là lệch, chặn Submit | E10 |
| Thành tiền, tiền thuế (từng dòng) | Chênh 0 đồng | Fork đã làm tròn theo dòng |
| Tổng tiền hàng, tổng thuế, tổng thanh toán | Chênh 0 đồng | |

#### 6.3.4 Nơi lưu kết quả (E7)

- **Purchase Invoice:** trường `trang_thai_doi_soat_pr` (Chưa đối soát / Khớp / Lệch / Ngoại lệ đã duyệt); **bảng con chênh lệch** (dòng, tiêu chí, giá trị PR, giá trị PI, mức lệch, nhánh xử lý, trạng thái); trường duyệt ngoại lệ (lý do, người duyệt, thời điểm).
- **Phiếu tiếp nhận (DT-07):** khi FRD-MAP-01 làm xong, chỉ cần trỏ sang PI và thêm trạng thái ST-05a "Lệch PR–PI".
- Nhật ký đối soát không xóa được (BR-12 của FRD).

#### 6.3.5 Thời điểm chạy và chặn

- Chạy khi: PI nháp được lưu; PR liên quan được Submit hoặc sửa lại; người dùng bấm "Đối soát lại". Mỗi lần chạy tính lại từ đầu, cho cùng kết quả.
- `before_submit` của PI: chặn nếu trạng thái không phải "Khớp" và không có ngoại lệ được duyệt.
- Ngoại lệ do **Kế toán trưởng hoặc Ban Điều hành** duyệt (E8).
- Áp cho **mọi PI có dòng liên kết PR** (E7). PI dịch vụ không có PR thì không áp.

#### 6.3.6 Xử lý khi lệch

| Nhánh | Khi nào | Ai làm | Cách sửa |
|---|---|---|---|
| (a) PI sai | Nhập hoặc đọc PI sai so với hóa đơn gốc | Mua hàng | Sửa PI nháp; lưu xong tự đối soát lại |
| (b1) PR nhập sai | Kho nhập sai số lượng hoặc mặt hàng so với thực nhận | Kho | Hủy rồi tạo bản sửa của PR (làm được vì PI còn nháp). Hệ thống tự đảo bút toán kho, sổ cái và tính lại giá trị tồn kho |
| (b2) Hóa đơn NCC sai | Hàng thực nhận đúng PR nhưng hóa đơn ghi khác | NCC (nhận email kèm bảng chênh lệch) | NCC phát hành hóa đơn điều chỉnh hoặc thay thế; hóa đơn mới đi lại từ đầu. Lệch giá so với HĐ khung thì áp BR-05 của FRD |

- **Phân loại nhánh do người quyết**, hệ thống chỉ gợi ý: lệch số lượng thì nghi PR hoặc hàng thực nhận; lệch giá thì nghi hóa đơn NCC; lệch so với file gốc thì nghi PI.
- Lưu ý: PR là chứng từ của Miyano, NCC không sửa PR được; NCC chỉ sửa chứng từ của họ.

#### 6.3.7 Tạo ĐNTT

| Bước | Thiết kế |
|---|---|
| Kích hoạt | `on_submit` của PI, khi trạng thái là "Khớp" hoặc "Ngoại lệ đã duyệt" |
| Tạo | `new_doc` + `insert`; Outward; `party_type=Supplier`; số tiền = `outstanding_amount` của PI. **Không gọi `submit`. Không dùng mapper chuẩn** |
| Hạn thanh toán | `due_date` của PI (đã tính từ `bill_date` + kỳ hạn NCC). Dùng trường hạn sẵn có trên production nếu có |
| Giao việc | `assign_to.add` cho người duyệt + Supply Notification |
| Đính kèm | Gắn file hóa đơn gốc |
| Transaction | Cùng transaction với Submit PI: tạo ĐNTT lỗi thì PI không Submit |

#### 6.3.8 Chống trùng và chạy đồng thời (E9)

Kiểm trong `validate` của **Payment Request**, nên áp cho **mọi đường tạo** (tự động, nút chuẩn, API, tạo tay):

1. Khóa dòng PI tham chiếu bằng `SELECT … FOR UPDATE`. Hai yêu cầu đồng thời phải xếp hàng.
2. Tính tổng `grand_total` của mọi ĐNTT **chưa hủy, tính cả nháp**, cho PI đó (không tính chính bản đang lưu).
3. Tổng + bản đang lưu > số tiền hóa đơn thì **chặn**.

| Tình huống | Kết quả |
|---|---|
| Bấm Submit PI hai lần | PI đã Submit thì không Submit lại được; khóa dòng chặn hai yêu cầu song song |
| Tạo ĐNTT thứ hai làm tổng vượt hóa đơn | Bị chặn |
| Chia đợt 60% + 40% | Được phép |
| Hủy ĐNTT | Không còn tính vào tổng; tạo lại được |
| Hủy PI | ERPNext chặn nếu đã có thanh toán; ĐNTT nháp thì hủy theo |
| Hết thời gian chờ sau khi đã ghi | Một transaction: hoặc đủ cả hai, hoặc không có gì |

#### 6.3.9 Thông báo (Supply Notification)

| Điểm thông báo | Kích hoạt | Người nhận |
|---|---|---|
| PI lệch PR, nhánh (a) | Trạng thái đối soát chuyển sang "Lệch" | Mua hàng |
| Lệch nhánh (b1) | Người xử lý chọn (b1) | Kho |
| Lệch nhánh (b2) | Người xử lý chọn (b2), bấm "Gửi NCC" | Email liên hệ NCC, CC Mua hàng |
| ĐNTT nháp đã tạo | ĐNTT được tạo | Người duyệt được giao |
| Lệch tồn quá N ngày | Nhắc theo ngày | Kế toán trưởng |

### 6.4 YC6: Nhập báo giá NCC tự động (Giai đoạn C, gộp lộ trình FRD-MAP-01)

| Kênh | Cách làm | Độ chính xác | Áp dụng |
|---|---|---|---|
| Cổng RFQ (đã có sẵn) | Miyano gửi RFQ; NCC đăng nhập cổng và điền giá; hệ thống tạo Supplier Quotation | Cao nhất: dữ liệu có cấu trúc | NCC lớn |
| Hộp thư báo giá | Một địa chỉ riêng (ví dụ `baogia@`) được ERP đọc tự động. File PDF/ảnh/Excel đi qua **bộ tiếp nhận dùng chung với FRD-MAP-01** (thêm loại chứng từ "Báo giá"); khớp mặt hàng bằng Bảng ánh xạ tên và thuật toán 4 tầng | Cao, nhờ luôn có người kiểm: chỉ tạo **nháp** Supplier Quotation; trường độ tin cậy thấp được tô màu; AI chỉ đọc file, không quyết mã hàng | NCC còn lại |
| Zalo | Nhân viên chuyển tiếp file từ Zalo sang hộp thư báo giá (một thao tác). Zalo Official Account để sau, **khả năng nhận file qua API chưa được kiểm chứng** | Như hộp thư | Mọi NCC dùng Zalo |

---

## 7. Danh mục tình huống (case) nghiệp vụ

### 7.1 YC3: Giá bán

| # | Tình huống | Kết quả mong đợi |
|---|---|---|
| G1 | Giá mua chưa gồm VAT 100.000 (Item Price bảng giá mua) → SO 101.000, Himedic | Khớp |
| G2 | Như G1 nhưng SO 101.500 | Lệch; SO cần lý do và người duyệt |
| G3 | Khách có % riêng 2% | Giá chuẩn 102.000 |
| G4 | (Khách, item) có % riêng 0,5%, khách có % 2% | Áp 0,5% |
| G5 | Bảng giá mua gồm VAT (`gia_gom_thue`), SO chưa gồm VAT | Quy giá mua về trước thuế rồi so; nếu không xác định được thuế suất → Lệch kiểu thuế |
| G6 | Cả hai gồm VAT 8%, giá chuẩn có số lẻ ở chữ số thập phân thứ 4 | Khớp sau làm tròn, không báo lệch giả |
| G7 | SO lập tay hoặc từ cổng khách hàng, không từ Quotation | Lấy giá gốc từ bảng giá mua tại ngày SO; kiểm bình thường |
| G8 | SQ có 2 dòng cùng mặt hàng | Chưa xác định giá gốc |
| G9 | Khách tắt kiểm | Bỏ qua |
| G10 | Hàng tặng (`is_free_item`); phiếu trả hàng | Bỏ qua |
| G16 | Dòng đơn giá 0 không phải hàng tặng (ví dụ giá riêng Himedic có `packing_unit` mà số lượng không đúng bội số) | Lệch; SO cần lý do và người duyệt |
| G11 | ĐVT bán khác ĐVT của giá mua | Quy đổi bằng `conversion_factor` trước khi so |
| G12 | Giám đốc đổi % sau khi SO đã Submit | SO cũ giữ nguyên % đã lưu |
| G13 | Người không có vai trò `vai_tro_sua_ty_le_lai` (kể cả Kế toán) sửa % lãi, qua form, import hoặc API | Bị từ chối; trường chỉ đọc với họ |
| G14 | SO đang mở, % lãi hoặc giá mua bị đổi | `before_submit` tính lại theo dữ liệu mới |
| G15 | Khách là Lead, chưa có Customer | Quotation áp mặc định 1%; SO kiểm theo Customer được tạo khi chuyển đổi |
| G17 | Mặt hàng có giá ở "Mua - Vietmed" và "Bảng giá mua"; NCC mặc định là Vietmed | Lấy giá "Mua - Vietmed" |
| G18 | Không có NCC mặc định; giá ở 2 bảng giá mua với `valid_from` khác nhau | Lấy dòng `valid_from` mới nhất |
| G19 | 2 dòng giá mua cùng `valid_from` mới nhất, giá khác nhau | Chưa xác định giá gốc |
| G20 | Không có giá mua nào hiệu lực tại ngày SO | Chưa xác định giá gốc |
| G21 | Giá mua có `valid_from` sau ngày SO | Không dùng giá đó; dùng giá trước đó |
| G22 | PO tạo từ SO, giá PO cao hơn giá gốc đã dùng ở SO | Cảnh báo "biên lãi bị phá"; vẫn lưu được |
| G23 | Supplier Quotation Submit | Tạo dòng Item Price mới trong "Mua - <NCC>"; dòng cũ giữ nguyên |
| G24 | Ghi nguồn giá gốc | Dòng SO lưu tên Item Price / dòng SQ đã dùng |

### 7.2 YC4: Đổi giá Himedic

| # | Tình huống | Kết quả mong đợi |
|---|---|---|
| T1 | Gửi thông báo ngày D, giá muốn áp từ D+3 | Lưu và gửi được; cảnh báo "thiếu 4 ngày"; dòng được đánh dấu `bao_gap`; nhắc kế toán xin xác nhận; giá áp từ D+3 |
| T1b | Đổi giá: thêm dòng mới `valid_from` = D+7, không sửa dòng cũ | Dòng cũ giữ nguyên; SO ngày D+6 lấy giá cũ, SO ngày D+7 lấy giá mới |
| T2 | Sửa đè `price_list_rate` của dòng đang hiệu lực | Bị chặn |
| T3 | Thêm thẳng giá vào bảng giá chính thức (form, import, API) | Bị chặn; phải qua bảng giá chờ |
| T4 | Giá nằm ở bảng giá chờ | SO không lấy giá này |
| T5 | SO ngày D+6, SI ngày D+8 | Giá cũ (giá theo ngày SO) |
| T6 | Giảm giá | Vẫn phải báo trước |
| T7 | Báo gấp, sau đó Himedic gửi email đồng ý | Kế toán ghi `ngay_xac_nhan` và đính bằng chứng; báo cáo báo gấp hiện "Đã xác nhận" |
| T8 | SQ Submit với giá mới | Tự tạo dòng "Chờ gửi" + thông báo cho kế toán |
| T9 | Giá NCC tăng, SO trong thời hạn chờ bán giá cũ | "Đang trong thời hạn báo giá"; không cần duyệt; ghi chênh |
| T10 | Hai khoảng ngày chồng nhau trong bảng giá Himedic | Bị chặn |
| T11 | Ngày gửi + 2 chưa có xác nhận | Nhắc kế toán |
| T12 | Có dòng báo gấp | Xuất hiện trong báo cáo báo gấp, kèm số ngày thiếu, trạng thái xác nhận và số SO đã dùng giá đó |

### 7.3 YC5: Đối soát và ĐNTT

| # | Tình huống | Kết quả mong đợi |
|---|---|---|
| S1 | PI khớp PR | Submit được; 1 ĐNTT nháp, số tiền = hóa đơn, hạn = `due_date`, có ToDo giao việc |
| S2 | PI lệch số lượng | Lệch; chặn Submit |
| S3 | PI lệch ĐVT | Lệch; chặn Submit |
| S4 | PI lệch thuế suất | Lệch; chặn Submit (E10) |
| S5 | Tổng lệch 1 đồng | Lệch; chặn Submit |
| S6 | PI nhập tay không qua Phiếu tiếp nhận | Vẫn đối soát (E7) |
| S7 | Một dòng PO nhận qua 2 PR | Ghép và phân bổ đúng |
| S8 | Ghép mơ hồ (≥ 2 khả năng) | Chuyển xử lý tay |
| S9 | Ngoại lệ do Kế toán trưởng hoặc Ban Điều hành duyệt | Submit được; lưu dấu vết |
| S10 | Kho sửa PR (hủy, tạo bản sửa) khi PI còn nháp | Đối soát tự chạy lại |
| S11 | NCC phát hành hóa đơn điều chỉnh | Hóa đơn mới đi lại từ đầu |
| S12 | Tạo ĐNTT thứ hai làm tổng vượt hóa đơn (nút chuẩn hoặc API) | Bị chặn; tính cả bản nháp |
| S13 | Chia 2 đợt 60% + 40% | Được phép; đợt thứ ba bị chặn |
| S14 | Tạo ĐNTT gặp lỗi | PI không Submit |
| S15 | Hai tiến trình đồng thời tạo ĐNTT cho một PI | Chỉ một bản thành công |
| S16 | Luồng Himedic: PR vào `Kho Himedic - M` | Đối soát như luồng chuẩn |
| S17 | PI dịch vụ không có PR | Không áp đối soát PR |

---

## 8. Các bước triển khai

| Đợt | Nội dung | Phụ thuộc | Mức rủi ro | Giảm rủi ro |
|---|---|---|---|---|
| **0** | Kiểm production (mục 10 — **đã xong đợt 1–4**). Rà "Bảng giá Himedic": 37/87 mặt hàng thấp hơn giá mua × 1,01, 33 cao hơn (đợt 5); chốt P8; bật `check_supplier_invoice_uniqueness`; xử lý tài khoản ngoài tiendj28@gmail.com có vai trò "Duyệt giá Himedic" | — | Thấp | Chỉ đọc trước, chỉnh sau; người dùng quyết từng giá |
| **1** | YC3: cấu hình % lãi + ô vai trò, tìm giá gốc từ bảng giá mua, bộ kiểm giá Quotation/SO, duyệt giá lệch, SQ Submit → Item Price mua, cảnh báo ở PO, báo cáo đối chiếu giá Himedic ↔ giá mua | Đợt 0 | Trung bình | Công tắc chung; ban đầu chỉ cảnh báo cả ở SO (chế độ "chỉ ghi nhận") đến khi bảng giá sạch, sau đó bật chặn với Himedic |
| **2** | YC4: bảng giá chờ, kiểm tra trên Item Price, nút gửi thông báo, cảnh báo báo gấp, kích hoạt từ SQ, nhắc việc, báo cáo báo gấp | Đợt 1 | Thấp–Trung bình (báo gấp chỉ cảnh báo, không chặn) | Chỉ áp cho bảng giá `can_bao_truoc` |
| **3** | YC5 (Giai đoạn B): đối soát, chặn Submit PI, ĐNTT nháp, chống vượt tổng | Đợt 0 | **Cao** (chặn ghi công nợ) | Công tắc trong Buying Settings; bật thử 1–2 NCC trước |
| **4** | YC6 + FRD-MAP-01: bộ tiếp nhận dùng chung cho hóa đơn và báo giá | FRD-MAP-01 được phê duyệt | Trung bình | Phối hợp với nhóm phụ trách FRD (Xuân, Hiếu bé) |

Mỗi đợt: viết test → triển khai → chạy test và đọc kết quả thật → báo cáo file đã sửa, lệnh đã chạy, kết quả test, rủi ro còn lại. Chỉ commit khi người dùng yêu cầu.

### 8.1 File dự kiến (theo `scripts/file_structure/gate.py`)

| Loại | Đường dẫn |
|---|---|
| Sửa DocType JSON | `customer`, `item_customer_detail`, `selling_settings`, `quotation(_item)`, `sales_order(_item)`, `item_price`, `price_list`, `purchase_invoice` (+ bảng con chênh lệch mới), `buying_settings`. **Không** thêm trường trên `payment_request` (dùng `custom_thoi_han_thanh_toan`, `custom_nguoi_yeu_cau` có sẵn) |
| Code giá gốc / SQ → Item Price / kiểm PO | `erpnext/selling/kiem_gia/gia_goc.py`; gọi từ `supplier_quotation.py` (`on_submit`) và `buying_controller.py` (`validate` của PO) |
| Code kiểm giá | `erpnext/selling/kiem_gia/` (gọi từ `erpnext/controllers/selling_controller.py`) |
| Code đổi giá | `erpnext/selling/kiem_gia/thong_bao_gia.py` |
| Code đối soát | `erpnext/accounts/doi_soat_pr_pi/` |
| Đăng ký sự kiện | `erpnext/hooks.py` (`doc_events`) |
| Patch | `erpnext/patches/v15_0/<động_từ>_<danh_từ>.py` + dòng trong `erpnext/patches.txt`: giá trị mặc định cho ô vai trò, bảng giá chờ, điểm Supply Notification. **Không tạo vai trò mới** |
| Test | `erpnext/selling/tests/`, `erpnext/accounts/test/` |
| Script demo, script kiểm đồng thời | `scripts/` |

---

## 9. Kiểm thử

- Chạy: `bench --site <site test> run-tests --module <module test>`. **Không chạy trên site `miyano`.**
- Mỗi tình huống ở mục 7 có ít nhất một test. Test kiểm **trạng thái lưu trong cơ sở dữ liệu**, không chỉ kiểm việc chạy không lỗi.
- S15 (đồng thời) không chứng minh được bằng test tuần tự. Dùng script trong `scripts/` mở 2 kết nối DB song song, kèm hướng dẫn chạy lại.
- **Dữ liệu demo:** script `scripts/demo_gia_ban_doi_soat.py`; mọi bản ghi có tiền tố `DEMO-`; chạy lại nhiều lần an toàn; **từ chối chạy trên site `miyano`**. Gồm 10 kịch bản:

| # | Kịch bản demo |
|---|---|
| 1 | Himedic 1%, giá mua ở "Mua - <NCC mặc định>", giá khớp |
| 2 | Himedic, giá lệch, chờ duyệt |
| 3 | Khách DEMO-B có % riêng 2% |
| 4 | Bảng giá mua gồm VAT, SO không gồm VAT |
| 5 | Đang trong thời hạn 7 ngày, SO bán giá cũ |
| 6 | Giảm giá báo dưới 7 ngày: cảnh báo, đánh dấu báo gấp, nhắc xin xác nhận |
| 7 | PI khớp PR, ĐNTT nháp đã tạo |
| 8 | PI lệch 1 đồng, chặn Submit |
| 9 | PI lệch thuế suất, chờ hóa đơn điều chỉnh |
| 10 | ĐNTT chia 2 đợt, đợt thứ ba bị chặn |

---

### 9.1 Lượt kiểm cuối trên site test (21/10/2026)

Script `/tmp/.../scratchpad/demo_gia_ban.py` (sẽ chuyển vào `scripts/demo_gia_ban_doi_soat.py` ở Đợt 1). Phần dữ liệu demo được **giữ lại** trên `erpnext.localhost`; phần kiểm chạy trong transaction và **rollback**, với cài đặt giống production (Warn, tắt tự cập nhật giá, Commercial Rounding).

Dữ liệu demo xem được trên trình duyệt: NCC `DEMO-Vietmed`, `DEMO-Hùng Minh`; khách `DEMO-Himedic`, `DEMO-KH B`; mặt hàng `DEMO-VT-01`…`05`; bảng giá `DEMO Mua - Vietmed`, `DEMO Mua - Hùng Minh`, `DEMO Bảng giá mua`, `DEMO Bảng giá Himedic`, `DEMO Bảng giá Himedic - Chờ báo`; SO nháp `SAL-ORD-2026-00001`; Supplier Quotation nháp `PUR-SQTN-2026-00001`.

| Kiểm | Tình huống | Kết quả |
|---|---|---|
| T1 | T1b, T5, D4-4: thêm giá Himedic mới `valid_from` D+7, giá cũ giữ | ĐẠT: SO ngày D và D+6 → 101.000; D+7 → 110.000; 2 dòng giá cùng tồn tại |
| T2 | T4: giá ở bảng chờ không bị áp | ĐẠT |
| T3 | Trùng mặt hàng + bảng giá + ĐVT + `valid_from` | ĐẠT: bị chặn `ItemPriceDuplicateItem` (chuẩn ERPNext); khác `valid_from` thì được |
| T3b | Item Price trên bảng giá mua tự có `buying = 1` | ĐẠT (truy vấn giá gốc dựa vào cờ này) |
| T4 | G17–G21: thuật toán giá gốc | ĐẠT sau khi sửa: lần đầu **KHÔNG ĐẠT** vì đọc `Item Default.default_supplier` (fork để trống) → chuyển sang `get_default_supplier` |
| T5 | G1, G6, G11, G18–G20 trên SO demo | ĐẠT sau khi sửa: lần đầu dòng ĐVT Hộp báo lệch giả 0,003 do ghi cứng 4 chữ số → dùng độ chính xác của trường |
| T5b/c | G3 (2%), G6 (làm tròn) | ĐẠT |
| T6 | G22: PO lập từ SO mang `sales_order_item` | ĐẠT: PO 103.000 > giá gốc 100.000 → cảnh báo được |
| T7 | P2: `maintain_same_rate` | ĐẠT: Warn → lưu được + cảnh báo; Stop → `ValidationError` khi Lưu |
| T8 | SQ Submit có tự tạo Item Price không | Không → phải code (6.1.7) |
| T9 | P7: bật `update_existing_price_list_rate` | Ghi nhận: gõ 25.000 trên SO → giá Himedic 20.500 bị **ghi đè** thành 25.000 → hai cài đặt phải giữ tắt |

Phải kiểm thêm trên production (chỉ đọc): bản erpnext trên production (`595f67e`) **không có** trong repo local, nên chưa biết đã có commit 50bab31 (NCC mặc định ở Supplier Items) chưa:

```sql
SELECT (SELECT COUNT(*) FROM `tabItem Supplier` WHERE parenttype='Item' AND is_default=1) ncc_mac_dinh_supplier_items,
       (SELECT COUNT(*) FROM `tabItem Default` WHERE parenttype='Item' AND IFNULL(default_supplier,'')<>'') ncc_mac_dinh_item_defaults;
```

## 10. Danh sách phải kiểm trên production trước khi triển khai (chỉ đọc)

| # | Cần biết | Vì sao |
|---|---|---|
| 1 | `validate_selling_price` | **Đã kiểm: 0** — giữ tắt |
| 2 | `round_row_wise_tax`, `create_pr_in_draft_status`, `check_supplier_invoice_uniqueness` | **Đã kiểm: 1, 1, 0** — bật cái cuối |
| 3 | `maintain_same_rate` và `maintain_same_rate_action` | **Đã kiểm: 1, Warn** — giữ Warn (P2) |
| 4 | Độ chính xác và cách làm tròn | **Đã kiểm:** đơn giá 4, thành tiền 2, Commercial Rounding |
| 5 | Custom Field trên Payment Request và các DocType liên quan | **Đã kiểm** (3.5) |
| 6 | Vai trò duyệt / Giám đốc / Kế toán trưởng / Ban Điều hành | **Đã kiểm:** chỉ có "Duyệt giá Himedic", COO, Accounts Manager, Sales Manager, "Kế toán trưởng HĐĐT" → dùng ô cài đặt chọn vai trò; ánh xạ chờ người dùng (đợt 5) |
| 7 | Tỷ lệ dòng SO đi từ Quotation | **Đã kiểm: 0/321** → đổi nguồn giá gốc sang bảng giá mua (P1) |
| 8 | Workflow đang bật | **Đã kiểm:** chỉ Quotation, Lead, Business Trip; không có trên SO, PI, Payment Request, Payment Entry |
| 9 | Scheduler | **Đã kiểm:** đang chạy |
| 10 | Hộp thư gửi đi mặc định | **Đã kiểm:** sales@miyano.com.vn |
| 11 | `packing_unit` trên Item Price | **Đã kiểm:** 0 dòng |

**Đợt kiểm thứ hai (sau kết quả 21/10, chỉ đọc)** — trả lời P1–P6 ở mục 3.6:

```sql
-- P1: SO được sinh từ đâu
SELECT COUNT(*) total,
       SUM(IFNULL(custom_yeu_cau_goc,'') <> '') tu_yeu_cau_cong_khach,
       SUM(IFNULL(custom_request_id,'') <> '') co_request_id
  FROM `tabSales Order` WHERE docstatus = 1;
SELECT COUNT(*) FROM `tabSales Order Item` WHERE docstatus = 1 AND IFNULL(prevdoc_docname,'') <> '';
SELECT docstatus, workflow_state, COUNT(*), SUM(IFNULL(supplier_quotation,'') <> '') co_sq
  FROM tabQuotation GROUP BY docstatus, workflow_state;
SELECT docstatus, COUNT(*) FROM `tabSupplier Quotation` GROUP BY docstatus;
SELECT custom_nguon_gia, COUNT(*) FROM `tabQuotation Item` GROUP BY custom_nguon_gia;
-- P4, P6: trường thuộc app nào; app nào đang cài
SELECT dt, fieldname, module FROM `tabCustom Field` WHERE fieldname IN ('custom_nguon_gia','custom_nguon_don','custom_yeu_cau_goc','custom_thoi_han_thanh_toan');
SELECT app_name, app_version FROM `tabInstalled Application`;
-- P3: vai trò "Duyệt giá Himedic" đang dùng ở đâu; vai trò cấp cao
SELECT parent, permlevel, `read`, `write`, submit FROM `tabCustom DocPerm` WHERE role = 'Duyệt giá Himedic';
SELECT parent FROM `tabHas Role` WHERE role = 'Duyệt giá Himedic' AND parenttype = 'User';
SELECT name, reference_doctype FROM `tabServer Script` WHERE script LIKE '%Duyệt giá Himedic%';
SELECT name, dt FROM `tabClient Script` WHERE script LIKE '%Duyệt giá Himedic%';
SELECT name FROM tabRole WHERE name IN ('COO','CEO','Accounts Manager','Sales Manager') OR name LIKE '%Director%';
-- P5: độ chính xác đặt riêng cho trường đơn giá
SELECT doc_type, field_name, value FROM `tabProperty Setter` WHERE property = 'precision'
   AND doc_type IN ('Quotation Item','Sales Order Item','Supplier Quotation Item','Purchase Invoice Item','Purchase Receipt Item','Item Price');
-- Scheduler: lần chạy job gần nhất
SELECT MAX(creation) FROM `tabScheduled Job Log`;
```

**Đợt kiểm thứ ba (sau kết quả đợt 2, chỉ đọc)** — trả lời P1, P3, P7:

```sql
-- P7: tự cập nhật Item Price từ chứng từ
SELECT field, value FROM tabSingles WHERE doctype = 'Stock Settings'
   AND field IN ('auto_insert_price_list_rate_if_missing','update_existing_price_list_rate','update_price_list_based_on');
SELECT name, dt, enabled FROM `tabClient Script` WHERE dt IN ('Item Price','Price List');
SELECT name, reference_doctype, disabled FROM `tabServer Script` WHERE reference_doctype IN ('Item Price','Price List');
-- P1: giá mua đang lưu ở đâu
SELECT pl.name, pl.buying, pl.selling, COUNT(ip.name) so_dong,
       SUM(IFNULL(ip.supplier,'') <> '') co_ncc, SUM(IFNULL(ip.customer,'') <> '') co_khach,
       SUM(ip.valid_from IS NOT NULL) co_valid_from
  FROM `tabPrice List` pl LEFT JOIN `tabItem Price` ip ON ip.price_list = pl.name GROUP BY pl.name;
SELECT COUNT(*) po, SUM(IFNULL(i.sales_order,'') <> '') dong_tu_so, SUM(IFNULL(i.supplier_quotation,'') <> '') dong_tu_sq
  FROM `tabPurchase Order Item` i WHERE i.docstatus = 1;
-- Mặt hàng đã bán (SO đã Submit) có giá trong bảng giá mua không
SELECT COUNT(DISTINCT soi.item_code) mat_hang,
       COUNT(DISTINCT CASE WHEN ip.name IS NOT NULL THEN soi.item_code END) co_gia_mua
  FROM `tabSales Order Item` soi
  LEFT JOIN `tabItem Price` ip ON ip.item_code = soi.item_code AND ip.buying = 1
 WHERE soi.docstatus = 1;
-- P3: "Duyệt giá Himedic" có trong Workflow không
SELECT parent, state, action, next_state FROM `tabWorkflow Transition` WHERE allowed = 'Duyệt giá Himedic';
SELECT parent, state FROM `tabWorkflow Document State` WHERE allow_edit = 'Duyệt giá Himedic';
-- P6: cổng khách hàng
SELECT name, module, public FROM tabWorkspace WHERE name LIKE '%khách%' OR module LIKE '%portal%';
SELECT name, app_name FROM `tabModule Def` WHERE app_name IN ('miyano_portal','miyano_pda');
```

**Đợt kiểm thứ tư (tùy chọn, chỉ đọc)** — số mặt hàng trong "Bảng giá Himedic" hiện đang đúng giá mua × 1,01 (mốc so sánh trước khi bật kiểm giá; chưa xét VAT):

```sql
WITH b AS (
  SELECT item_code, uom, price_list_rate p,
         ROW_NUMBER() OVER (PARTITION BY item_code, uom ORDER BY valid_from DESC, modified DESC) rn
    FROM `tabItem Price` WHERE buying = 1 AND valid_from <= CURDATE()
     AND (valid_upto IS NULL OR valid_upto >= CURDATE())),
h AS (
  SELECT item_code, uom, price_list_rate p,
         ROW_NUMBER() OVER (PARTITION BY item_code, uom ORDER BY valid_from DESC, modified DESC) rn
    FROM `tabItem Price` WHERE price_list = 'Bảng giá Himedic' AND valid_from <= CURDATE()
     AND (valid_upto IS NULL OR valid_upto >= CURDATE()))
SELECT COUNT(*) co_ca_hai_gia,
       SUM(h.p = ROUND(b.p * 1.01, 4)) dung_1pct,
       SUM(h.p < ROUND(b.p * 1.01, 4)) thap_hon,
       SUM(h.p > ROUND(b.p * 1.01, 4)) cao_hon
  FROM h JOIN b ON b.item_code = h.item_code AND b.uom = h.uom AND b.rn = 1
 WHERE h.rn = 1;
```

Kết quả đợt 4 (21/10/2026): 87 mặt hàng có cả giá Himedic và giá mua (cùng ĐVT, đang hiệu lực): **17 đúng ×1,01, 37 thấp hơn, 33 cao hơn**. Nếu bật kiểm ngay, khoảng 80% mặt hàng sẽ báo lệch → trước khi bật phải rà bảng giá (đợt 5) và chạy báo cáo đối chiếu một lần để làm sạch.

**Đợt kiểm thứ năm (chỉ đọc)** — chi tiết 37 mặt hàng thấp hơn (có bán dưới giá mua không) và người đang giữ các vai trò cấp cao:

```sql
WITH b AS (
  SELECT item_code, uom, price_list, price_list_rate p,
         ROW_NUMBER() OVER (PARTITION BY item_code, uom ORDER BY valid_from DESC, modified DESC) rn
    FROM `tabItem Price` WHERE buying = 1 AND valid_from <= CURDATE()
     AND (valid_upto IS NULL OR valid_upto >= CURDATE())),
h AS (
  SELECT item_code, uom, valid_from, price_list_rate p,
         ROW_NUMBER() OVER (PARTITION BY item_code, uom ORDER BY valid_from DESC, modified DESC) rn
    FROM `tabItem Price` WHERE price_list = 'Bảng giá Himedic' AND valid_from <= CURDATE()
     AND (valid_upto IS NULL OR valid_upto >= CURDATE()))
SELECT h.item_code, h.uom, b.price_list, b.p gia_mua, h.p gia_himedic,
       ROUND(b.p * 1.01, 4) gia_chuan, ROUND((h.p / b.p - 1) * 100, 2) pct_lai, h.valid_from
  FROM h JOIN b ON b.item_code = h.item_code AND b.uom = h.uom AND b.rn = 1
 WHERE h.rn = 1 AND h.p < ROUND(b.p * 1.01, 4)
 ORDER BY pct_lai;

SELECT r.role, GROUP_CONCAT(u.name ORDER BY u.name SEPARATOR ', ') users
  FROM `tabHas Role` r JOIN tabUser u ON u.name = r.parent
 WHERE r.parenttype = 'User' AND u.enabled = 1
   AND r.role IN ('COO','Accounts Manager','Kế toán trưởng HĐĐT','Sales Manager','Purchase Manager','Duyệt giá Himedic')
 GROUP BY r.role;
SELECT employee_name, designation, department, user_id FROM tabEmployee
 WHERE status = 'Active' AND (designation LIKE '%Giám đốc%' OR designation LIKE '%trưởng%'
       OR designation LIKE '%Director%' OR designation LIKE '%Manager%');
```

Trên máy chủ production (chỉ đọc) để biết mã nguồn cổng khách hàng ở đâu:

```bash
git -C ~/frappe-bench/apps/miyano_portal remote -v
git -C ~/frappe-bench/apps/miyano_portal log -1 --format='%h %an %ad'
```

Chạy thêm trên production (chỉ đọc), ngoài các câu SQL bên dưới:

```bash
bench --site miyano scheduler status
```

```sql
SELECT w.name, w.document_type, w.is_active, s.state, s.doc_status, s.allow_edit
  FROM tabWorkflow w JOIN `tabWorkflow Document State` s ON s.parent = w.name
 WHERE w.is_active = 1 ORDER BY w.document_type, s.idx;
SELECT t.parent, t.state, t.action, t.next_state, t.allowed, t.`condition`
  FROM `tabWorkflow Transition` t JOIN tabWorkflow w ON w.name = t.parent WHERE w.is_active = 1;
SELECT name, email_id, default_outgoing, enable_outgoing FROM `tabEmail Account` WHERE enable_outgoing = 1;
SELECT price_list, COUNT(*) FROM `tabItem Price` WHERE IFNULL(packing_unit,0) > 0 GROUP BY price_list;
```

```sql
SELECT doctype, field, value FROM tabSingles WHERE
 (doctype='Selling Settings'  AND field IN ('validate_selling_price','maintain_same_sales_rate'))
 OR (doctype='Buying Settings'   AND field IN ('maintain_same_rate','maintain_same_rate_action','pr_required'))
 OR (doctype='Accounts Settings' AND field IN ('round_row_wise_tax','create_pr_in_draft_status','check_supplier_invoice_uniqueness'))
 OR (doctype='System Settings'   AND field IN ('currency_precision','float_precision','rounding_method'));

SELECT dt, fieldname, label, fieldtype, options FROM `tabCustom Field`
 WHERE dt IN ('Payment Request','Purchase Invoice','Quotation','Quotation Item','Sales Order',
              'Sales Order Item','Customer','Item Price','Price List','Supplier Quotation');

SELECT name FROM tabRole
 WHERE name LIKE '%Duyệt%' OR name LIKE '%Giám đốc%' OR name LIKE '%Kế toán trưởng%' OR name LIKE '%Điều hành%';

SELECT COUNT(*) AS total,
       SUM(quotation_item IS NOT NULL AND quotation_item <> '') AS from_quotation
  FROM `tabSales Order Item` WHERE docstatus = 1;
```

---

## 11. Rủi ro còn lại

| Rủi ro | Mức | Cách xử lý |
|---|---|---|
| Không có dữ liệu production để kiểm chứng luồng và hiệu năng | Trung bình | Kiểm production ở Đợt 0; bật dần theo công tắc |
| Chặn Submit PI làm chậm việc ghi công nợ | Cao | Bật thử theo NCC; có đường ngoại lệ do Kế toán trưởng hoặc Ban Điều hành duyệt |
| Bảng giá Himedic hiện lệch nhiều so với giá mua × 1,01 (70/87 mặt hàng, đợt 4) — bật kiểm là báo lệch hàng loạt | Cao | Đợt 0 rà bảng giá; Đợt 1 chạy chế độ "chỉ ghi nhận" trước khi chặn |
| Bảng giá mua cũ / thiếu (giá gốc sai khi NCC đã đổi giá mà chưa nhập SQ) | Trung bình | Kiểm lại ở PO (G22); nhắc nhập SQ; YC6 nhập tự động |
| Giả định P8 sai với một số bảng giá (thực tế nhập gồm VAT) | Trung bình | Báo cáo 1.2 sẽ lộ ra (% lãi thực ≈ VAT); khi đó thêm ô `gia_gom_thue` trên Price List |
| Mẫu thuế khai sai "đã gồm trong đơn giá" làm so sai | Trung bình | Bước kiểm cùng kiểu thuế; hướng dẫn nhập liệu |
| Người có quyền sửa % lãi tự duyệt giá lệch (không có kiểm soát hai người) | Thấp–Trung bình | Đã được chấp nhận; bù bằng dấu vết sửa và duyệt |
| Đợt 4 phụ thuộc FRD-MAP-01 (chờ phê duyệt, nhóm phụ trách riêng) | Trung bình | Giai đoạn B không phụ thuộc DT-07 |
| Khả năng nhận file qua API của Zalo OA chưa được kiểm chứng | Thấp | Trước mắt chuyển tiếp sang hộp thư |
| Ô "Price Not UOM Dependent" không có tác dụng ở server (đã kiểm chứng, 3.4 #5) | Thấp | Quy ước nhập giá theo ĐVT kho, không bật ô này; test G11 |
| Giá riêng của khách có `packing_unit` ra 0 (đã kiểm chứng, 3.4 #6) | Trung bình | Dòng giá 0 không phải hàng tặng xếp vào "Lệch" (G16); kiểm `packing_unit` trên production |
| Code gọi `.submit()` đi vòng qua Workflow | Thấp | Production không có Workflow trên SO/PI/Payment Request; vẫn giữ quy tắc không gọi `.submit()` trên chứng từ có Workflow (Quotation) |
| Tài khoản ngoài công ty (tiendj28@gmail.com) có vai trò "Duyệt giá Himedic" — sẽ là người duyệt giá lệch nếu dùng lại vai trò | Trung bình | Người dùng xác nhận hoặc gỡ vai trò trước Đợt 1 |

---

## 12. Điều kiện để bắt đầu triển khai

1. ~~Có kết quả các câu lệnh kiểm production ở mục 10~~ — đã có (đợt 1–4, 21/10/2026). Đợt 5 không chặn code.
2. ~~P8~~ — đã chốt: giả định chưa gồm VAT.
3. Người dùng xác nhận cho phép bắt đầu **Đợt 1** trên nhánh `feat/auto-check-selling-price-poc`.

Ánh xạ vai trò Giám đốc / Kế toán trưởng / Ban Điều hành **không chặn** việc code (ô cài đặt chọn vai trò); chỉ cần trước khi bật trên production.

---

## 13. Đường lối triển khai cuối cùng

Nguyên tắc: làm phần **chỉ đọc** trước để có giá trị ngay và làm sạch dữ liệu; phần **chặn** bật sau cùng, bằng công tắc.

### Đợt 1 — YC3, theo thứ tự

| Bước | Việc | Nơi sửa | Test |
|---|---|---|---|
| 1.1 | Module tính giá gốc + giá chuẩn: `tim_gia_goc(item, ngày)` (dùng `get_default_supplier`, cờ `buying`, `valid_from`/`valid_upto`), `tinh_gia_chuan(dòng, %)` (độ chính xác của trường, ĐVT của dòng, VAT theo P8) | `erpnext/selling/kiem_gia/gia_goc.py` | G1–G11, G17–G21 |
| 1.2 | **Báo cáo "Đối chiếu giá bán ↔ giá mua"** (Script Report, chỉ đọc): mỗi bảng giá bán × mặt hàng → giá gốc, nguồn, giá chuẩn, chênh, % lãi thực | `erpnext/selling/report/doi_chieu_gia_ban_gia_mua/` | Dùng ngay để rà 70/87 mặt hàng lệch (Đợt 0) |
| 1.3 | Cài đặt: Selling Settings (`bat_kiem_gia_ban`, `che_do_kiem` = Chỉ ghi nhận / Chặn, `ty_le_lai_mac_dinh` = 1, `vai_tro_sua_ty_le_lai`, `vai_tro_duyet_gia_lech`); Customer (`kiem_gia_ban`, `ty_le_lai`); Item Customer Detail (`ty_le_lai`); Price List: không thêm (P8) | DocType JSON + kiểm quyền ở `validate` | G12, G13 |
| 1.4 | Kiểm trên Quotation và SO: ghi `gia_goc`, `nguon_gia_goc`, `ty_le_lai_ap_dung`, `gia_chuan`, `chenh_lech`, `trang_thai_gia` (chỉ đọc) | `SellingController.validate` | G1–G24 |
| 1.5 | Chặn ở `before_submit` của SO khi `che_do_kiem` = Chặn: dòng lệch cần `ly_do_lech_gia` + người có `vai_tro_duyet_gia_lech` | `sales_order.py` | G2, G14, G16 |
| 1.6 | SQ Submit → dòng Item Price mới trong bảng giá mua của NCC | `supplier_quotation.py` `on_submit` | G23, T8 |
| 1.7 | Cảnh báo ở PO lập từ SO khi giá PO > giá gốc | `BuyingController.validate` | G22 |
| 1.8 | Script demo vào repo; chạy toàn bộ test trên `erpnext.localhost` | `scripts/demo_gia_ban_doi_soat.py`, `erpnext/selling/tests/` | 10 kịch bản mục 9 |

Lên production: bật ở chế độ **Chỉ ghi nhận** cho Himedic → dùng báo cáo 1.2 làm sạch bảng giá → khi tỷ lệ lệch còn thấp, chuyển **Chặn**.

### Đợt 2 — YC4 (bảng giá chờ, báo trước 7 ngày gắn Price List, cảnh báo báo gấp, nhắc việc, báo cáo báo gấp)
### Đợt 3 — YC5 (đối soát PR ↔ PI 0 đồng, chặn Submit PI, ĐNTT nháp, chống vượt tổng; ô vai trò ngoại lệ ở Buying Settings)
### Đợt 4 — YC6 + FRD-MAP-01

Không đổi so với mục 6.2–6.4 và 8.

### Việc của người dùng trước / trong Đợt 1 (không chặn bước 1.1–1.2)

1. ~~P8~~ — đã chốt: giả định chưa gồm VAT.
2. SQL kiểm NCC mặc định ở mục 9.1 (cần trước khi lên production).
3. Ánh xạ vai trò; xử lý tài khoản tiendj28@gmail.com (cần trước khi bật Chặn).

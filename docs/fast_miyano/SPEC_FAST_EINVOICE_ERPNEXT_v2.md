# ĐẶC TẢ & HƯỚNG DẪN XÂY DỰNG TÍCH HỢP HÓA ĐƠN ĐIỆN TỬ FAST ↔ ERPNEXT

**Phiên bản 2.0 — 07/08/2026** — thay thế toàn bộ bản 1.0

| Hạng mục            | Nội dung                                                                                                                          |
| --------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| Doanh nghiệp         | CÔNG TY TNHH MIYANO VIỆT NAM                                                                                                     |
| Hệ thống đích     | ERPNext / Frappe — erp.miyano.com.vn                                                                                              |
| Nhà cung cấp HĐĐT | 0Fast e-Invoice — API portal service v2.5 (06/06/2025), chế độ**không mã hóa RSA**                                    |
| Thông số kết nối  | clientCode`008254` · proxyCode `006384` · unitCode `CTY` · voucherBook `1C26TAA` · ký hiệu `1C26TMY`               |
| Hình thức ký số   | **HSM** — Fast tự ký, `action = 0`, một lời gọi là xong                                                             |
| Chứng từ nguồn     | **Delivery Note** (nút phát hành đặt trên DN)                                                                          |
| Phạm vi v2.0         | Toàn bộ vòng đời: nháp → gửi khách → sửa → duyệt → phát hành → email → điều chỉnh / thay thế / hủy nội bộ |

---

## PHẦN A — NGUYÊN TẮC THIẾT KẾ BẮT BUỘC

Ba nguyên tắc dưới đây áp dụng cho **mọi** chức năng trong tài liệu này. Dev không được bỏ qua bất kỳ nguyên tắc nào, kể cả với hành động "chỉ đọc".

### A1. Mọi hành động đều LƯU VÀO DOCTYPE trước và sau khi gọi API

Không có lời gọi API nào được thực hiện "bay" mà không để lại dấu vết trong cơ sở dữ liệu. Chuẩn thực hiện cho mọi nút bấm:

```
① Ghi bản ghi Fast EInvoice Log (status = "Đang gửi", lưu request đã che mật khẩu)
② Cập nhật Fast EInvoice Document.status = trạng thái "đang xử lý" tương ứng
③ frappe.db.commit()  ← BẮT BUỘC commit trước khi gọi API
④ Gọi API Fast
⑤ Ghi response đầy đủ vào Log (kể cả khi lỗi, kể cả khi timeout)
⑥ Cập nhật các trường kết quả + status trên Fast EInvoice Document
⑦ frappe.db.commit()
```

Lý do bước ③ bắt buộc: nếu server sập hoặc timeout giữa chừng, hệ thống vẫn còn bằng chứng "đã gửi đi rồi" để lần sau biết phải truy vấn (method 370) thay vì phát hành lại — tránh hóa đơn trùng.

### A2. Mọi hành động đều PHẢI CÓ XÁC NHẬN CỦA NGƯỜI DÙNG

Không hành động nào tự chạy ngầm không hỏi. Ba cấp xác nhận:

| Cấp                                         | Áp dụng cho                                        | Hình thức                                                                                                                                                                                 |
| -------------------------------------------- | ---------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Cấp 1 — Xác nhận đơn giản**   | Xem nháp, tải PDF, truy vấn, kiểm tra CQT        | `frappe.confirm()` — hộp thoại Có/Không                                                                                                                                              |
| **Cấp 2 — Xác nhận có dữ liệu** | Gửi email, tạo điều chỉnh, tạo thay thế       | `frappe.prompt()` — dialog nhập/sửa thông tin rồi mới chạy                                                                                                                         |
| **Cấp 3 — Xác nhận nghiêm ngặt** | **Phát hành thật**, **Hủy nội bộ** | Dialog toàn màn hình hiển thị bảng tóm tắt hóa đơn + người dùng phải**gõ đúng chữ `PHAT HANH`** (hoặc `HUY`) vào ô trống mới bật được nút xác nhận |

Cấp 3 là bắt buộc vì hai hành động đó **không thể hoàn tác**: đã phát hành là tiêu 1 số hóa đơn và dữ liệu đã lên Cơ quan Thuế.

### A3. Mọi request/response đều được GHI LOG

DocType `Fast EInvoice Log` lưu: thời điểm, người thao tác, action, method, chứng từ liên quan, JSON gửi đi (dạng đọc được, **không** phải base64), response thô, mã lỗi, thời gian phản hồi. Log là căn cứ duy nhất khi đối chiếu tranh chấp với Fast hoặc CQT — không được tắt.

### A4. Quy tắc an toàn khi lập trình

Bốn quy tắc rút ra từ sự cố thực tế trong quá trình thử nghiệm:

Thứ nhất, **luôn truy vấn (370) trước khi phát hành lại** bất kỳ hóa đơn nào đã từng gửi đi mà không rõ kết quả. Lỗi 835 "hóa đơn đã tồn tại" xảy ra do phát hành lặp.

Thứ hai, **Key phải sinh một lần và không đổi**, lưu ngay vào DocType khi tạo bản ghi. Không sinh lại Key ở thời điểm bấm nút.

Thứ ba, **môi trường test và thật phải tách bằng cấu hình**, có cờ `is_test_mode` hiển thị banner đỏ trên giao diện khi đang trỏ vào hệ thống thật.

Thứ tư, **khóa chống bấm đúp**: khi một Fast EInvoice Document đang ở trạng thái "Đang phát hành", mọi nút phát hành bị vô hiệu hóa (dùng `frappe.db.get_value` với `for_update=True` hoặc Redis lock theo `name` của document).

---

## PHẦN B — VÒNG ĐỜI NGHIỆP VỤ (STATE MACHINE)

### B1. Sơ đồ trạng thái đầy đủ

```
                    [Delivery Note đã submit]
                              │ bấm "Tạo hóa đơn điện tử"  (xác nhận cấp 1)
                              ▼
                    ┌──────────────────┐
              ┌────►│  01. NHÁP        │  Dữ liệu đã copy từ DN, chưa gửi Fast
              │     └────────┬─────────┘
              │              │ "Xem bản nháp PDF"  (action=600)
              │              ▼
              │     ┌──────────────────┐
              │     │ 02. ĐÃ XEM NHÁP  │  PDF nháp đã đính kèm vào DocType
              │     └────────┬─────────┘
              │              │ "Gửi bản nháp cho khách"  (xác nhận cấp 2 — nhập email)
              │              ▼
              │     ┌──────────────────────┐
              │     │ 03. CHỜ KHÁCH DUYỆT  │
              │     └───┬──────────────┬───┘
              │         │              │
    "Sửa lại"│◄─────────┘              │ "Khách đã duyệt"  (xác nhận cấp 2 — ghi người/ngày duyệt)
    (khách yêu cầu sửa)                ▼
              │              ┌──────────────────┐
              │              │ 04. KHÁCH DUYỆT  │  ✅ Sẵn sàng phát hành
              │              └────────┬─────────┘
              │                       │ "PHÁT HÀNH HÓA ĐƠN"  (XÁC NHẬN CẤP 3 — gõ PHAT HANH)
              │                       ▼
              │              ┌──────────────────┐
              │              │ 05. ĐANG PHÁT HÀNH│ ← khóa, chống bấm đúp
              │              └────┬────────┬────┘
              │        thất bại   │        │ thành công
              └───────────────────┘        ▼
                    (ghi lỗi,     ┌────────────────────┐
                     về Nháp)     │ 06. ĐÃ PHÁT HÀNH   │  Có invoiceNo + keySearch
                                  └─────────┬──────────┘
                                            │ tự động: tải PDF (380) + đính kèm
                                            │ "Gửi email hóa đơn"  (xác nhận cấp 2)
                                            ▼
                                  ┌────────────────────┐
                                  │ 07. ĐÃ GỬI KHÁCH   │
                                  └─────────┬──────────┘
                                            │ job nền: poll CQT (8200)
                              ┌─────────────┴──────────────┐
                              ▼                            ▼
                  ┌────────────────────┐      ┌────────────────────┐
                  │ 08. CQT CHẤP NHẬN  │      │ 09. CQT TỪ CHỐI    │
                  │      (hoàn tất)    │      └─────────┬──────────┘
                  └─────────┬──────────┘                │ "Hủy nội bộ" (CẤP 3)
                            │                           ▼
        ┌───────────────────┼──────────────┐  ┌────────────────────┐
        ▼                   ▼              │  │ 12. ĐÃ HỦY NỘI BỘ  │
┌──────────────┐   ┌──────────────┐        │  └─────────┬──────────┘
│10. ĐÃ ĐIỀU   │   │ 11. ĐÃ THAY  │        │            │ phát hành lại
│    CHỈNH     │   │     THẾ      │        │            └──► về 01. NHÁP (bản ghi mới)
└──────────────┘   └──────────────┘        │
   (tạo bản ghi mới loại 320/350, trỏ về bản gốc qua keySearch)
```

### B2. Bảng trạng thái — điều kiện chuyển và nút khả dụng

| Mã | Trạng thái       | Nút được phép bấm                                                                                      | Có thể sửa dữ liệu?    |
| --- | ------------------ | ------------------------------------------------------------------------------------------------------------ | --------------------------- |
| 01  | Nháp              | Đồng bộ lại từ DN · Xem nháp PDF · Phát hành (nếu bỏ qua bước duyệt khách) · Xóa           | ✅ Có                      |
| 02  | Đã xem nháp     | Sửa (→01) · Gửi nháp cho khách · Xem lại nháp · Phát hành                                        | ✅ Có (chuyển về 01)     |
| 03  | Chờ khách duyệt | Sửa (→01) · Khách đã duyệt · Gửi lại nháp · Ghi nhận ý kiến khách                            | ✅ Có (chuyển về 01)     |
| 04  | Khách đã duyệt | **Phát hành** · Sửa (→01, cảnh báo mất trạng thái duyệt) · Xem nháp                       | ⚠️ Có, nhưng cảnh báo |
| 05  | Đang phát hành  | *(khóa toàn bộ)*                                                                                        | ❌ Không                   |
| 06  | Đã phát hành   | Tải PDF · Tải PDF chuyển đổi · Gửi email · Kiểm tra CQT · Truy vấn (370)                         | ❌ Không                   |
| 07  | Đã gửi khách   | Tải PDF · Gửi lại email · Kiểm tra CQT                                                                 | ❌ Không                   |
| 08  | CQT chấp nhận    | Tải PDF · Gửi lại email ·**Tạo hóa đơn điều chỉnh** · **Tạo hóa đơn thay thế** | ❌ Không                   |
| 09  | CQT từ chối      | Xem lý do ·**Hủy nội bộ** · Truy vấn (370)                                                      | ❌ Không                   |
| 10  | Đã điều chỉnh | Chỉ xem · mở bản ghi điều chỉnh liên quan                                                            | ❌ Không                   |
| 11  | Đã thay thế     | Chỉ xem · mở bản ghi thay thế liên quan                                                                | ❌ Không                   |
| 12  | Đã hủy nội bộ | Tạo hóa đơn mới từ DN gốc                                                                             | ❌ Không                   |
| 99  | Lỗi               | Xem log lỗi · Truy vấn (370) · Sửa (→01) · Thử lại                                                  | ✅ Có                      |

**Lưu ý pháp lý quan trọng:** bản PDF ở trạng thái 01–04 là **BẢN NHÁP, KHÔNG CÓ GIÁ TRỊ PHÁP LÝ** — chưa có số hóa đơn, chưa ký số, chưa lên CQT. Khi gửi cho khách bắt buộc ghi rõ điều này trong nội dung email (xem mẫu email mục E2). Chỉ từ trạng thái 06 trở đi hóa đơn mới có giá trị.

---

## PHẦN C — THIẾT KẾ DỮ LIỆU (4 DOCTYPE)

```
┌─────────────────────────┐        ┌────────────────────────────────┐
│ Fast eInvoice Settings  │◄───────┤  Fast EInvoice Document        │
│ (Single — cấu hình)     │        │  (cha — is_submittable = 0)    │
└─────────────────────────┘        │  ├─ Fast EInvoice Line (child) │
                                   │  └─ trường kết quả từ Fast     │
┌─────────────────────────┐        └───────────┬────────────────────┘
│ Delivery Note (+3 field)│───────────────────►│
└─────────────────────────┘                    │
                                   ┌───────────▼────────────────────┐
                                   │  Fast EInvoice Log             │
                                   │  (1 bản ghi / 1 lời gọi API)   │
                                   └────────────────────────────────┘
```

Ghi chú thiết kế: đặt `is_submittable = 0` cho Fast EInvoice Document và dùng trường `status` tự quản lý vòng đời, vì vòng đời 12 trạng thái của hóa đơn không khớp mô hình Draft/Submitted/Cancelled của Frappe. Khóa chỉnh sửa bằng `read_only_depends_on` theo `status` thay vì bằng docstatus.

---

### C1. DocType `Fast eInvoice Settings` (Single)

| #  | Fieldname                     | Label                                            | Fieldtype                 | BB | Ghi chú                                                                                                                                 |
| -- | ----------------------------- | ------------------------------------------------ | ------------------------- | -- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| 1  | `enabled`                   | Kích hoạt tích hợp                           | Check                     |    | Tắt = mọi nút ẩn đi                                                                                                                 |
| 2  | `is_test_mode`              | Chế độ TEST                                   | Check                     |    | Bật → banner vàng "MÔI TRƯỜNG TEST"; tắt → banner đỏ "HỆ THỐNG THẬT"                                                        |
| 3  | `api_url`                   | URL dịch vụ                                    | Data                      | ✔ | Thật:`https://tportal.fast.com.vn/AppService/FastEInvoice.PortalService.asmx` · Test: thêm `:9000`                                |
| 4  | `client_code`               | Mã doanh nghiệp                                | Data                      | ✔ | `008254` — trim khoảng trắng khi gửi                                                                                               |
| 5  | `proxy_code`                | Mã nhóm dịch vụ                              | Data                      | ✔ | `006384`                                                                                                                               |
| 6  | `unit_code`                 | Mã đơn vị                                    | Data                      | ✔ | `CTY` — trim khi gửi                                                                                                                 |
| 7  | `voucher_book`              | Quyển hóa đơn                                | Data                      | ✔ | `1C26TAA`                                                                                                                              |
| 8  | `api_user`                  | User API                                         | Data                      | ✔ | **Nên xin Fast user riêng cho ERP** — mỗi user chỉ có 1 token sống, dùng chung với người đăng nhập web sẽ đá nhau |
| 9  | `api_password`              | Mật khẩu                                       | Password                  | ✔ |                                                                                                                                          |
| 10 | `token`                     | Token phiên                                     | Data (hidden, read only)  |    | Hệ thống tự quản lý, hiệu lực 24h                                                                                                 |
| 11 | `token_time`                | Thời điểm lấy token                          | Datetime (hidden)         |    |                                                                                                                                          |
| 12 | `default_human_name`        | Người phát hành mặc định                  | Data                      |    | Điền vào`HumanName` nếu không lấy được từ user                                                                               |
| 13 | `auto_download_pdf`         | Tự tải PDF sau phát hành                     | Check                     |    | Mặc định bật                                                                                                                         |
| 14 | `auto_poll_tax_status`      | Tự kiểm tra trạng thái CQT                   | Check                     |    | Mặc định bật — job 20 phút/lần                                                                                                    |
| 15 | `require_customer_approval` | Bắt buộc khách duyệt trước khi phát hành | Check                     |    | **Bật** = trạng thái phải là 04 mới cho phát hành. Khuyến nghị bật cho khách bệnh viện, tắt cho khách lẻ          |
| 16 | `draft_email_template`      | Mẫu email gửi bản nháp                       | Link → Email Template    |    |                                                                                                                                          |
| 17 | `issued_email_template`     | Mẫu email gửi hóa đơn chính thức          | Link → Email Template    |    |                                                                                                                                          |
| 18 | `notify_on_error`           | Người nhận cảnh báo lỗi                    | Table MultiSelect → User |    | Gửi thông báo khi phát hành lỗi hoặc CQT từ chối                                                                                |

---

### C2. DocType `Fast EInvoice Document` (cha)

Naming: `FEI-.YYYY.-.#####` (ví dụ `FEI-2026-00001`).

#### C2.1 — Nhóm liên kết & điều khiển (không gửi Fast)

| #  | Fieldname                       | Label                          | Fieldtype                                  | BB  | Ghi chú                                                                                                                         |
| -- | ------------------------------- | ------------------------------ | ------------------------------------------ | --- | -------------------------------------------------------------------------------------------------------------------------------- |
| 1  | `delivery_note`               | Phiếu giao hàng              | Link → Delivery Note                      | ✔  | Nguồn dữ liệu. Không cho trùng với bản ghi khác đang ở trạng thái 01–08                                             |
| 2  | `sales_invoice`               | Hóa đơn bán (ERP)          | Link → Sales Invoice                      |     | Điền sau nếu kế toán tạo SINV từ DN                                                                                       |
| 3  | `customer`                    | Khách hàng                   | Link → Customer                           | ✔  | Fetch từ DN                                                                                                                     |
| 4  | `status`                      | Trạng thái                   | Select                                     | ✔  | 12 trạng thái mục B2 +`Lỗi`                                                                                                |
| 5  | `invoice_type`                | Loại chứng từ               | Select                                     | ✔  | `Hóa đơn gốc` / `Hóa đơn điều chỉnh` / `Hóa đơn thay thế`                                                    |
| 6  | `original_document`           | Hóa đơn gốc                | Link → Fast EInvoice Document             | ĐK | Bắt buộc khi loại ≠ gốc. Khi gửi lấy`fast_key_search` của bản ghi này                                                |
| 7  | `adjustment_type`             | Loại điều chỉnh            | Select                                     | ĐK | `1 - Điều chỉnh giảm` / `2 - Điều chỉnh tăng` / `3 - Điều chỉnh thông tin`. Thay thế → hệ thống tự gán 4 |
| 8  | `adjustment_reason`           | Lý do điều chỉnh/thay thế | Small Text                                 | ĐK | Bắt buộc khi loại ≠ gốc — phục vụ biên bản và giải trình                                                            |
| 9  | `minute_no` / `minute_date` | Số / ngày biên bản         | Data / Date                                |     | Biên bản thỏa thuận giữa hai bên (nếu có)                                                                                |
| 10 | `amended_from_fei`            | Bản ghi thay thế bởi        | Link → Fast EInvoice Document (read only) |     | Chiều ngược của#6 — để mở nhanh bản ghi con                                                                             |

#### C2.2 — Nhóm quy trình duyệt khách hàng (điểm mới của v2.0)

| #  | Fieldname                  | Label                            | Fieldtype            | Ghi chú                                                |
| -- | -------------------------- | -------------------------------- | -------------------- | ------------------------------------------------------- |
| 11 | `draft_pdf`              | File PDF nháp                   | Attach (read only)   | Kết quả action=600, ghi đè mỗi lần xem lại nháp |
| 12 | `draft_pdf_time`         | Thời điểm tạo nháp          | Datetime (read only) |                                                         |
| 13 | `draft_sent_to`          | Đã gửi nháp tới email       | Data (read only)     |                                                         |
| 14 | `draft_sent_time`        | Thời điểm gửi nháp          | Datetime (read only) |                                                         |
| 15 | `draft_send_count`       | Số lần gửi nháp              | Int (read only)      | Tăng mỗi lần gửi — theo dõi số vòng sửa        |
| 16 | `customer_feedback`      | Ý kiến khách hàng            | Text                 | Kế toán nhập lại nội dung khách yêu cầu sửa    |
| 17 | `customer_approved_by`   | Người xác nhận khách duyệt | Data                 | Tên người bên khách hoặc nhân viên ghi nhận    |
| 18 | `customer_approved_time` | Thời điểm khách duyệt       | Datetime (read only) |                                                         |
| 19 | `revision_count`         | Số lần sửa                    | Int (read only)      | Tăng mỗi lần quay về trạng thái 01 từ 02/03/04   |

#### C2.3 — Nhóm dữ liệu MASTER gửi Fast

Thứ tự dưới đây **chính là thứ tự cột** trong `structure.master`. Cột "Nguồn DN" = giá trị lấy tự động khi tạo bản ghi từ Delivery Note. **ĐK** = bắt buộc có điều kiện.

| #      | Thẻ Fast                                             | Fieldname                                                                  | Fieldtype                     | BB  | Nguồn DN                               | Quy tắc validate                                                                                                 |
| ------ | ----------------------------------------------------- | -------------------------------------------------------------------------- | ----------------------------- | --- | --------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| 20     | Key                                                   | `fast_key`                                                               | Data (read only sau khi tạo) | ✔  | `name` của DN                        | ≤32 ký tự, không dấu,**duy nhất tuyệt đối**. Sinh 1 lần khi tạo bản ghi. Trùng → lỗi 809/835 |
| 21     | InvoiceDate                                           | `invoice_date`                                                           | Date                          | ✔  | `posting_date`                        | Serialize`dd/MM/yyyy`. Không nhỏ hơn ngày HĐ đã phát hành gần nhất (819)                             |
| 22     | CustomerCode                                          | `customer_code`                                                          | Data                          | ✔  | `customer`                            | Không dấu                                                                                                       |
| 23     | Buyer                                                 | `buyer`                                                                  | Data                          |     | Contact của DN                         | Tên**người** đi mua. ≤100 ký tự (836)                                                                |
| 24     | CustomerName                                          | `customer_name`                                                          | Data                          | ✔  | `customer_name`                       | Bắt buộc khi có MST (836). Không xuống dòng (825)                                                           |
| 25     | CustomerTaxCode                                       | `customer_tax_code`                                                      | Data                          | ĐK | `tax_id` của Customer                | Bắt buộc nếu CustomerType=1. MST 10 hoặc 13 số (78013)                                                       |
| 26     | CustomerType                                          | `customer_type`                                                          | Select`1`/`0`             | ✔  | Customer Group                          | 1 = Doanh nghiệp · 0 = Cá nhân                                                                                |
| 27     | Address                                               | `address`                                                                | Data                          | ✔  | **Billing address** của Customer | ⚠️ KHÔNG lấy shipping address của DN                                                                         |
| 28     | PhoneNumber                                           | `phone_number`                                                           | Data                          |     | Contact                                 |                                                                                                                   |
| 29     | FaxNumber                                             | `fax_number`                                                             | Data                          |     |                                         | Thường rỗng                                                                                                    |
| 30     | IDCardNo                                              | `id_card_no`                                                             | Data                          | ĐK | custom field Customer                   | CCCD: đúng 9 hoặc 12**chữ số** hoặc rỗng                                                             |
| 31     | PassportNo                                            | `passport_no`                                                            | Data                          |     | custom field Customer                   | ≤20 — thẻ mới NĐ 70/2025                                                                                     |
| 32     | BuyerUnit                                             | `buyer_unit`                                                             | Data                          |     | custom field Customer                   | Mã ĐVQHNS ≤7 — dùng cho bệnh viện công                                                                    |
| 33     | EmailDeliver                                          | `email_deliver`                                                          | Data                          | ✔  | Contact/Customer                        | ≤256, nhiều email cách nhau`,`. Portal tự gửi mail khi phát hành                                         |
| 34     | BankAccount                                           | `bank_account`                                                           | Data                          |     | Customer                                |                                                                                                                   |
| 35     | BankName                                              | `bank_name`                                                              | Data                          |     | Customer                                |                                                                                                                   |
| 36     | PaymentMethod                                         | `payment_method`                                                         | Select                        | ✔  | mặc định                             | `TM` / `CK` / `TM/CK`                                                                                       |
| 37     | Currency                                              | `currency`                                                               | Data                          | ✔  | `currency`                            | ISO 3 ký tự. Hỗ trợ sẵn VND/USD/JPY/EUR (152)                                                                |
| 38     | ExchangeRate                                          | `exchange_rate`                                                          | Float                         | ✔  | `conversion_rate`                     | VND = 1.0                                                                                                         |
| 39     | Amount                                                | `amount`                                                                 | Currency                      | ✔  | `net_total`                           | = Σ Amount các dòng. **Giữ 2 số lẻ, không làm tròn về đồng nguyên**                                                                                            |
| 40     | TotalAmount                                           | `total_amount`                                                           | Currency                      | ✔  | `grand_total`                         | = Amount + TaxAmount − giảm trừ, **làm tròn thành số nguyên** (VND/JPY). Chênh lệch làm tròn ≤ 0,5                                                                                |
| 41     | TaxRate                                               | `tax_rate`                                                               | Select                        | ✔  | bảng thuế DN                          | `0` `5` `8` `10` `-1`KCT `-2`KKNT `-8`KHAC `-9`rỗng                                              |
| 42     | TaxAmount                                             | `tax_amount`                                                             | Currency                      | ✔  | `total_taxes_and_charges`             | = Σ TaxAmount các dòng. **Giữ 2 số lẻ, không làm tròn về đồng nguyên**                                                                                         |
| 43–46 | TaxAmountFree / TaxAmount0 / TaxAmount5 / TaxAmount10 | `tax_amount_free`, `tax_amount_0`, `tax_amount_5`, `tax_amount_10` | Currency                      |     | tính                                   | **Bắt buộc điền đủ khi hóa đơn nhiều thuế suất.** Không có ô cho 8% — phần 8% để ngoài. Đối chứng TEST 2026-09-08: Fast nhận, CQT chấp nhận                                                |
| 47     | DiscountAmount                                        | `discount_amount`                                                        | Currency                      |     | `discount_amount`                     |                                                                                                                   |
| 48     | PromotionAmount                                       | `promotion_amount`                                                       | Currency                      |     |                                         |                                                                                                                   |
| 49     | DeductionAmount                                       | `deduction_amount`                                                       | Currency                      |     |                                         | Giảm trừ không chịu thuế                                                                                     |
| 50     | DeductionAmountOther                                  | `deduction_amount_other`                                                 | Currency                      |     |                                         |                                                                                                                   |
| 51     | AmountInWords                                         | `amount_in_words`                                                        | Data                          | ✔  | **ERP tự sinh**                  | Hàm đọc số tiếng Việt. VND→"đồng", USD→"đô la Mỹ", EUR→"Euro" (sai → 152)                          |
| 52     | HumanName                                             | `human_name`                                                             | Data                          | ✔  | user bấm nút                          | ≤128                                                                                                             |
| 53     | ReleaseType                                           | `release_type`                                                           | Select                        |     | `1`                                   | `1` = cột tiền chi tiết đã trừ chiết khấu                                                               |
| 54–56 | External1–3                                          | `external_1..3`                                                          | Data                          |     | tùy chọn                              | ≤500. Ví dụ: số hợp đồng, số PO bệnh viện.**Chỉ đưa vào structure khi có dùng**             |
| 57–59 | NumberExternal1–3                                    | `number_external_1..3`                                                   | Float                         |     | tùy chọn                              | Chỉ đưa vào structure khi có dùng                                                                           |

#### C2.4 — Nhóm KẾT QUẢ từ Fast (read only toàn bộ)

| #  | Fieldname                                                            | Label                               | Fieldtype             | Nguồn              | Ghi chú                                                                                                      |
| -- | -------------------------------------------------------------------- | ----------------------------------- | --------------------- | ------------------- | ------------------------------------------------------------------------------------------------------------- |
| 60 | `fast_key_search`                                                  | Mã tra cứu (keySearch)            | Data                  | response 310        | ⭐**Quan trọng nhất** — chìa khóa cho tải PDF / điều chỉnh / thay thế / hủy / gửi lại mail |
| 61 | `fast_invoice_no`                                                  | Số hóa đơn                      | Data                  | response            | Ví dụ`2`                                                                                                  |
| 62 | `fast_pattern`                                                     | Mẫu số                            | Data                  | response            | Ví dụ`1/001`                                                                                              |
| 63 | `fast_serial`                                                      | Ký hiệu                           | Data                  | response            | Ví dụ`1C26TMY`                                                                                            |
| 64 | `fast_signed_date`                                                 | Ngày phát hành                   | Date                  | response (yyyyMMdd) |                                                                                                               |
| 65 | `issued_by` / `issued_time`                                      | Người / thời điểm phát hành  | Link User / Datetime  | hệ thống          | Ai bấm nút phát hành                                                                                      |
| 66 | `official_pdf`                                                     | File PDF chính thức               | Attach                | method 380          |                                                                                                               |
| 67 | `converted_pdf`                                                    | File PDF chuyển đổi              | Attach                | method 385          | Bản in giấy hợp lệ, có tên người chuyển đổi                                                        |
| 68 | `invoice_sent_to` / `invoice_sent_time` / `invoice_send_count` | Email hóa đơn chính thức       | Data / Datetime / Int |                     |                                                                                                               |
| 69 | `tax_status`                                                       | Trạng thái CQT                    | Select                | method 8200         | `Chờ CQT` / `3 - Chấp nhận` / `4 - Từ chối`                                                        |
| 70 | `tax_verification_code`                                            | Mã CQT cấp                        | Data                  | method 8200         |                                                                                                               |
| 71 | `tax_feedback`                                                     | Phản hồi CQT                      | Small Text            | method 8200         | Lý do từ chối                                                                                              |
| 72 | `tax_checked_time`                                                 | Lần kiểm tra CQT gần nhất       | Datetime              |                     |                                                                                                               |
| 73 | `error_code` / `error_message`                                   | Mã lỗi / thông báo              | Data / Small Text     | response            | Ánh xạ sang tiếng Việt theo mục G                                                                        |
| 74 | `cancel_reason` / `cancelled_time`                               | Lý do & thời điểm hủy nội bộ | Small Text / Datetime |                     |                                                                                                               |

---

### C3. Child table `Fast EInvoice Line`

Thứ tự = thứ tự cột `structure.detail`. Nguồn: bảng `items` của Delivery Note.

| #  | Thẻ Fast      | Fieldname           | Fieldtype | BB | Nguồn DN Item               | Validate                                                                                                                                            |
| -- | -------------- | ------------------- | --------- | -- | ---------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1  | ProcessType    | `process_type`    | Select    | ✔ | mặc định`1`             | `1` Hàng hóa/DV · `2` Khuyến mại · `3` Chiết khấu · `4` Ghi chú · `5` Hàng đặc trưng. **Không được rỗng** (836) |
| 2  | ItemCode       | `item_code`       | Data      | ✔ | `item_code`                | ≤32, không dấu                                                                                                                                   |
| 3  | ItemName       | `item_name`       | Data      | ✔ | `item_name`                | ≤500 (812), không xuống dòng (825), tránh`&` `<` `>` (63505)                                                                             |
| 4  | UOM            | `uom`             | Data      | ✔ | `uom` → tên tiếng Việt | ≤16                                                                                                                                                |
| 5  | IsPromotion    | `is_promotion`    | Check     | ✔ | 0                            |                                                                                                                                                     |
| 6  | Quantity       | `qty`             | Float     | ✔ | `qty`                      | > 0                                                                                                                                                 |
| 7  | Price          | `price`           | Currency  | ✔ | `rate`                     |                                                                                                                                                     |
| 8  | Amount         | `amount`          | Currency  | ✔ | `net_amount`               | = Qty × Price − Chiết khấu (khi ReleaseType=1)                                                                                                  |
| 9  | DiscountRate   | `discount_rate`   | Float     |    |                              |                                                                                                                                                     |
| 10 | DiscountAmount | `discount_amount` | Currency  |    |                              |                                                                                                                                                     |
| 11 | TaxRate        | `tax_rate`        | Select    | ✔ | Item Tax Template            | Cùng bộ mã master.`-9` chỉ cho dòng ghi chú / HĐ điều chỉnh (78025)                                                                     |
| 12 | TaxAmount      | `tax_amount`      | Currency  | ✔ | tính                        |                                                                                                                                                     |
| 13 | Note           | `note`            | Data      |    |                              |                                                                                                                                                     |
| — | LineNumber     | `line_number`     | Int       |    | `idx`                      | Tùy chọn —**không dùng thì không đưa thẻ vào structure**                                                                           |

Giới hạn: **≤300 dòng/hóa đơn** (lỗi 3000). Với hóa đơn điều chỉnh: dòng giảm truyền **số âm**, dòng tăng truyền số dương.

---

### C4. DocType `Fast EInvoice Log`

| #  | Fieldname                          | Fieldtype                      | Ghi chú                                                                                |
| -- | ---------------------------------- | ------------------------------ | --------------------------------------------------------------------------------------- |
| 1  | `fei_document`                   | Link → Fast EInvoice Document | Có thể rỗng với lời gọi CheckKey/GetKey                                           |
| 2  | `operation`                      | Select                         | `CheckKey` / `GetKey` / `ExcuteCommand`                                           |
| 3  | `action` / `method`            | Int / Int                      | Ví dụ 0 / 310                                                                         |
| 4  | `purpose`                        | Data                           | Mô tả tiếng Việt: "Phát hành hóa đơn", "Xem PDF nháp"…                       |
| 5  | `request_json`                   | Long Text                      | JSON**dạng đọc được** (không base64), che password/token                   |
| 6  | `response_raw`                   | Long Text                      | Response thô. Nếu Message là base64 PDF → chỉ ghi độ dài, không ghi cả chuỗi |
| 7  | `success`                        | Check                          |                                                                                         |
| 8  | `error_code` / `error_message` | Data / Small Text              |                                                                                         |
| 9  | `duration_ms`                    | Int                            | Thời gian phản hồi                                                                   |
| 10 | `user` / `timestamp`           | Link User / Datetime           |                                                                                         |

Chính sách lưu trữ: giữ tối thiểu 12 tháng (đối chiếu với CQT); tự dọn bản ghi cũ hơn 24 tháng bằng scheduled job.

---

### C5. Custom field bổ sung trên `Delivery Note`

| Fieldname                | Label               | Fieldtype                                 | Ghi chú                              |
| ------------------------ | ------------------- | ----------------------------------------- | ------------------------------------- |
| `fast_einvoice`        | Chứng từ HĐĐT   | Link → Fast EInvoice Document, read only |                                       |
| `fast_invoice_no`      | Số HĐĐT          | Data, read only                           | Hiện trên list view để lọc nhanh |
| `fast_einvoice_status` | Trạng thái HĐĐT | Select, read only                         | Đồng bộ từ Fast Document          |
| `fast_key_search`      | Mã tra cứu        | Data, read only, hidden                   | Bản sao dự phòng                   |

---

## PHẦN D — DANH MỤC HÀNH ĐỘNG (13 NÚT)

Bảng tổng hợp. Chi tiết từng nút ở Phần E.

| #   | Nút                                   | Vị trí      | API                   | Trạng thái hiện nút                       | Cấp xác nhận                      | Ghi vào DocType                                            |
| --- | -------------------------------------- | ------------- | --------------------- | --------------------------------------------- | ------------------------------------ | ----------------------------------------------------------- |
| 1   | Tạo hóa đơn điện tử             | Delivery Note | —                    | DN submitted, chưa có FEI                   | 1                                    | Tạo bản ghi FEI, status=01                                |
| 2   | Đồng bộ lại từ DN                 | FEI           | —                    | 01, 02, 03, 04, 99                            | 1                                    | Ghi đè master+lines, revision_count+1                     |
| 3   | Xem bản nháp PDF                     | FEI           | action=600 / m=310    | 01→04, 99 (**không chặn theo validate**)     | 1                                    | `draft_pdf`, `draft_pdf_time`, status→02               |
| 4   | Gửi bản nháp cho khách             | FEI           | — (email ERP)        | 02, 03, 04                                    | 2                                    | `draft_sent_*`, `draft_send_count`+1, status→03        |
| 5   | Ghi nhận ý kiến khách              | FEI           | —                    | 03                                            | 2                                    | `customer_feedback`, status→01                           |
| 6   | Khách đã duyệt                     | FEI           | —                    | 03                                            | 2                                    | `customer_approved_*`, status→04                         |
| 7   | **PHÁT HÀNH HÓA ĐƠN**       | FEI           | action=0 / m=310      | 04 (hoặc 01–02 nếu tắt bắt buộc duyệt) | **3**                          | Toàn bộ nhóm C2.4, status→06                            |
| 8   | Tải PDF chính thức                  | FEI           | action=0 / m=380      | 06, 07, 08                                    | 1                                    | `official_pdf`                                            |
| 9   | Tải PDF chuyển đổi                 | FEI           | action=0 / m=385      | 06, 07, 08                                    | 2 (nhập tên người chuyển đổi) | `converted_pdf`                                           |
| 10  | Gửi hóa đơn cho khách             | FEI           | m=700 hoặc email ERP | 06, 07, 08                                    | 2                                    | `invoice_sent_*`, status→07                              |
| 11  | Kiểm tra trạng thái CQT             | FEI           | action=0 / m=8200     | 06, 07                                        | 1                                    | `tax_status`, `tax_verification_code`, `tax_feedback` |
| 12  | Truy vấn hóa đơn (đối soát)     | FEI           | action=0 / m=370      | mọi trạng thái ≥05 và 99                 | 1                                    | Ghi log; cập nhật kết quả nếu phát hiện lệch        |
| 13a | Tạo hóa đơn**điều chỉnh** | FEI           | action=0 / m=320      | 08                                            | 2                                    | Tạo FEI mới loại điều chỉnh, gốc→status 10          |
| 13b | Tạo hóa đơn**thay thế**     | FEI           | action=0 / m=350      | 08                                            | 2                                    | Tạo FEI mới loại thay thế, gốc→status 11              |
| 13c | **Hủy nội bộ**                | FEI           | action=0 / m=330      | 09 (CQT từ chối)                            | **3**                          | `cancel_reason`, `cancelled_time`, status→12           |

---

## PHẦN E — ĐẶC TẢ CHI TIẾT TỪNG HÀNH ĐỘNG

Mỗi hành động mô tả theo 6 mục: **Tiền điều kiện → Dialog xác nhận → Validate → Gọi API → Lưu DocType → Xử lý lỗi**.

### E1. Nút 1 — Tạo hóa đơn điện tử (trên Delivery Note)

**Tiền điều kiện:** `docstatus == 1` · `is_return == 0` · chưa có FEI nào trỏ tới DN này với status ∈ 01–08 · Settings.enabled = 1.

**Dialog (cấp 1):**

> Tạo chứng từ hóa đơn điện tử từ phiếu giao **MAT-DN-2026-00001**?
> Khách hàng: Bệnh viện X · Tổng tiền: 11.000.000 đ
> Hệ thống sẽ sao chép dữ liệu sang chứng từ HĐĐT để rà soát trước khi phát hành. *(Chưa gửi gì cho Fast ở bước này.)*
> **[Hủy] [Tạo chứng từ]**

**Validate ngay khi tạo** (chạy toàn bộ Phần F, nhưng chỉ **cảnh báo** chứ không chặn — để kế toán còn sửa): hiển thị bảng lỗi/cảnh báo ngay đầu form.

**Lưu DocType:** tạo bản ghi FEI mới, sinh `fast_key` = `name` của DN (bỏ dấu, ≤32 ký tự), copy toàn bộ master + lines, tính `amount_in_words`, `status = 01 Nháp`, ghi ngược `delivery_note.fast_einvoice`.

---

### E2. Nút 3 — Xem bản nháp PDF

**Tiền điều kiện:** status ∈ 01, 02, 03, 04, 99 · đã qua validate không còn lỗi chặn.

**Dialog (cấp 1):**

> Lấy bản nháp PDF từ Fast để xem trước?
> ⚠️ Đây là **bản nháp** — không có số hóa đơn, không ký số, **không gửi Cơ quan Thuế**, không tiêu số hóa đơn.
> **[Hủy] [Lấy bản nháp]**

**Gọi API:** `ExcuteCommand(action=600, method=310, data=base64(payload), checkSum=token)`.

**Lưu DocType:** decode base64 → lưu file `Nhap_{name}_{lần}.pdf` vào `draft_pdf`, ghi `draft_pdf_time`, `status = 02`, ghi Log. Mở PDF ngay trong tab mới cho người dùng xem.

**Xử lý lỗi:** hiện thông báo tiếng Việt theo bảng mã lỗi, ghi `error_code`/`error_message`, **giữ nguyên status** (không chuyển 02).

---

### E3. Nút 4 — Gửi bản nháp cho khách hàng

**Tiền điều kiện:** status ∈ 02, 03, 04 · đã có `draft_pdf`.

**Dialog (cấp 2 — `frappe.prompt`):**

> **Gửi bản nháp hóa đơn cho khách hàng**
> • Người nhận (sửa được): `ketoan@benhvienx.vn` *(mặc định lấy từ `email_deliver`)*
> • CC: `[trống]`
> • Tiêu đề: `[Bản nháp hóa đơn] MAT-DN-2026-00001 — Miyano Việt Nam`
> • Nội dung: *(lấy từ Email Template, sửa được)*
> • ☑ Đính kèm bản nháp PDF
> **[Hủy] [Gửi email]**

**Nội dung email mẫu — bắt buộc có dòng cảnh báo:**

> Kính gửi Quý khách,
> Công ty TNHH Miyano Việt Nam xin gửi **BẢN NHÁP** hóa đơn cho đơn hàng ... để Quý khách kiểm tra thông tin (tên đơn vị, mã số thuế, địa chỉ, tên hàng, số lượng, đơn giá, thuế suất).
> **Lưu ý: đây là bản nháp, chưa có số hóa đơn và CHƯA CÓ GIÁ TRỊ PHÁP LÝ.** Sau khi Quý khách xác nhận thông tin chính xác, chúng tôi sẽ phát hành hóa đơn điện tử chính thức và gửi lại.
> Mọi điều chỉnh xin phản hồi lại email này trước ...

**Lưu DocType:** `draft_sent_to`, `draft_sent_time = now()`, `draft_send_count += 1`, `status = 03`, ghi Comment vào timeline của document, ghi Log (operation = "Email nháp").

---

### E4. Nút 5 & 6 — Ghi nhận ý kiến khách / Khách đã duyệt

**Nút 5 — Khách yêu cầu sửa (cấp 2):** dialog nhập `customer_feedback` (bắt buộc, ≥10 ký tự). Lưu: ghi feedback kèm timestamp và người nhập (nối thêm vào trường, không ghi đè lịch sử), `status = 01`, `revision_count += 1`. Sau đó kế toán sửa dữ liệu hoặc bấm "Đồng bộ lại từ DN" rồi lặp lại vòng nháp.

**Nút 6 — Khách đã duyệt (cấp 2):** dialog nhập `customer_approved_by` (tên người bên khách đã xác nhận — bắt buộc) và chọn hình thức xác nhận (Email / Điện thoại / Văn bản / Trực tiếp). Lưu: `customer_approved_by`, `customer_approved_time = now()`, `status = 04`, ghi Comment "Khách hàng đã duyệt bản nháp — xác nhận bởi ... qua ...".

> Đây là bằng chứng nội bộ khi có tranh chấp về nội dung hóa đơn. Bắt buộc ghi DocType, không chỉ nói miệng.

---

### E5. Nút 7 — PHÁT HÀNH HÓA ĐƠN ⚠️ (hành động không thể hoàn tác)

**Tiền điều kiện:** `status == 04` (nếu `require_customer_approval` bật) hoặc status ∈ 01, 02, 04 (nếu tắt) · validate Phần F **không còn lỗi nào** · không có bản ghi FEI khác cùng `fast_key` đã phát hành · Redis lock chưa bị chiếm.

**Dialog xác nhận cấp 3 — toàn màn hình:**

```
╔═══════════════════════════════════════════════════════════════╗
║  ⚠️  PHÁT HÀNH HÓA ĐƠN ĐIỆN TỬ CHÍNH THỨC                     ║
║  [Banner đỏ nếu is_test_mode = 0: "HỆ THỐNG THẬT"]            ║
╠═══════════════════════════════════════════════════════════════╣
║  Khách hàng    : BỆNH VIỆN ĐA KHOA X                          ║
║  Mã số thuế    : 0101234567                                   ║
║  Địa chỉ       : Số 1 Phố Y, Hà Nội                           ║
║  Ngày hóa đơn  : 07/08/2026                                   ║
║  Số dòng hàng  : 12 dòng                                      ║
║  Tiền hàng     : 10.000.000 đ                                 ║
║  Thuế GTGT 10% :  1.000.000 đ                                 ║
║  TỔNG THANH TOÁN: 11.000.000 đ                                ║
║  Bằng chữ      : Mười một triệu đồng chẵn                     ║
║  Quyển/Ký hiệu : 1C26TAA / 1C26TMY                            ║
║  Khách duyệt   : Chị Lan (BV X) — 07/08/2026 09:15            ║
╠═══════════════════════════════════════════════════════════════╣
║  Sau khi phát hành: hóa đơn được ký số HSM, cấp số chính thức ║
║  và gửi lên Cơ quan Thuế. KHÔNG THỂ XÓA hoặc sửa. Muốn thay   ║
║  đổi phải lập hóa đơn điều chỉnh hoặc thay thế.               ║
║                                                               ║
║  Gõ chính xác  PHAT HANH  để xác nhận:  [_______________]     ║
║                                                               ║
║              [ Hủy bỏ ]        [ PHÁT HÀNH ]  (mờ đến khi gõ đúng)
╚═══════════════════════════════════════════════════════════════╝
```

**Trình tự xử lý phía server (bắt buộc đúng thứ tự):**

```python
1. Chiếm lock theo tên document (nếu đã bị chiếm → báo "Đang xử lý, vui lòng đợi")
2. Chạy lại toàn bộ validate — không tin dữ liệu từ client
3. Gọi truy vấn 370 với fast_key → nếu ĐÃ TỒN TẠI:
      → dừng lại, cập nhật kết quả vào DocType, báo "Hóa đơn này đã được
        phát hành trước đó (số ...). Không phát hành lại."      [chống lỗi 835]
4. Ghi Log (status="Đang gửi") + đặt status = 05 Đang phát hành + COMMIT
5. Lấy token (CheckKey → GetKey nếu cần)
6. Gọi ExcuteCommand(action=0, method=310, data, token)   ← lời gọi quyết định
7a. Success=1 → parse Message → lưu invoiceNo, keySearch, pattern, serial,
       signedDate, issued_by, issued_time; status = 06; tax_status = "Chờ CQT"
       → ghi ngược sang Delivery Note (số HĐ, keySearch, trạng thái)
       → COMMIT
       → enqueue job nền: tải PDF (380) sau 6 giây
7b. Success=0 → ghi error_code/message, status = 99 Lỗi, COMMIT,
       gửi thông báo cho nhóm notify_on_error
7c. TIMEOUT hoặc ngoại lệ mạng → status = "Cần đối soát" (biến thể của 99),
       ghi rõ "Đã gửi nhưng chưa nhận được kết quả — BẮT BUỘC truy vấn 370
       trước khi thao tác tiếp", KHÔNG tự động phát hành lại
8. Nhả lock
```

**Kết quả hiển thị:** thông báo xanh "Phát hành thành công — Hóa đơn số **2**, ký hiệu **1C26TMY**, mã tra cứu `...`" kèm nút "Tải PDF" và "Gửi cho khách".

---

### E6. Nút 8 & 9 — Tải PDF chính thức / PDF chuyển đổi

**Nút 8 (cấp 1):** dialog "Tải bản PDF chính thức của hóa đơn số 2 từ Fast?" → gọi `action=0, method=380`, `data = {"key": fast_key_search}` → decode → lưu vào `official_pdf` (đặt tên `HD_{serial}_{invoice_no}.pdf`) → đồng thời đính kèm sang Delivery Note.

**Nút 9 (cấp 2):** dialog nhập **tên người chuyển đổi** (mặc định = họ tên user đang đăng nhập, sửa được) → gọi `method=385`, `data = {"key": ..., "convertName": "..."}` → lưu `converted_pdf`. Dùng khi cần bản in giấy hợp lệ kẹp theo hàng.

**Ràng buộc kỹ thuật:** giữa 2 lần gọi 380/385 phải cách **tối thiểu 5 giây** — hệ thống tự chặn và báo "Vui lòng đợi N giây".

---

### E7. Nút 10 — Gửi hóa đơn chính thức cho khách hàng

Hai phương án, chọn theo cấu hình:

**Phương án A (khuyến nghị) — ERP tự gửi:** dùng email của ERPNext, đính kèm `official_pdf`, nội dung có số hóa đơn, ký hiệu, **mã tra cứu** và hướng dẫn tra cứu trên trang của Fast/CQT. Ưu điểm: kiểm soát nội dung, lưu vào Communication của ERP, tra lại được.

**Phương án B — nhờ Fast gửi:** gọi `action=0, method=700`, `data = {"key": keySearch, "email": "..."}`. Dùng khi cần gửi lại đúng mẫu email của portal Fast.

**Dialog (cấp 2):** cho sửa người nhận, CC, tiêu đề, nội dung; hiển thị rõ "Đính kèm: HD_1C26TMY_2.pdf".

**Lưu DocType:** `invoice_sent_to`, `invoice_sent_time`, `invoice_send_count += 1`, `status = 07`, ghi Log.

---

### E8. Nút 11 & 12 — Kiểm tra CQT / Truy vấn đối soát

**Nút 11 — Kiểm tra trạng thái CQT (cấp 1):** gọi `method=8200` với khoảng ngày = ngày hóa đơn. Cập nhật `tax_status`, `tax_verification_code`, `tax_feedback`, `tax_checked_time`; nếu `taxStatus=3` → status 08; nếu `=4` → status 09 + gửi cảnh báo cho `notify_on_error`. **Không có trong kết quả** = CQT chưa xử lý xong, giữ nguyên "Chờ CQT".

**Job nền tự động:** mỗi 20 phút, quét các FEI có `tax_status = "Chờ CQT"` và `fast_signed_date` trong 7 ngày gần nhất, gọi 8200 theo lô (gộp theo khoảng ngày để giảm số lời gọi). Đây là **hành động đọc**, không đổi dữ liệu nghiệp vụ nên không cần xác nhận người dùng, nhưng vẫn ghi Log.

**Nút 12 — Truy vấn đối soát (cấp 1):** gọi `method=370` với `{"key": fast_key, "period": yyyyMM}`. Dùng khi: nghi phát hành trùng, sau timeout, hoặc muốn dọn "hóa đơn treo". Nếu kết quả lệch với dữ liệu đang lưu → hiển thị bảng so sánh và hỏi người dùng có muốn cập nhật theo Fast không (**xác nhận cấp 2** trước khi ghi đè).

---

### E9. Nút 13a/13b — Hóa đơn điều chỉnh / thay thế

**Khi nào dùng cái nào:**

| Tình huống                                                                            | Nghiệp vụ đúng                                              |
| --------------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| Sai số lượng, đơn giá, thành tiền, thuế suất → cần tăng/giảm giá trị    | **Điều chỉnh** (320), `adjustment_type` 1 hoặc 2    |
| Sai thông tin không ảnh hưởng số tiền (tên hàng, địa chỉ, tên đơn vị…) | **Điều chỉnh thông tin** (320), `adjustment_type` 3 |
| Sai nhiều/sai nghiêm trọng, cần một hóa đơn mới thay hẳn hóa đơn cũ       | **Thay thế** (350)                                       |
| Hàng trả lại toàn bộ hoặc một phần                                              | **Điều chỉnh giảm** (320, type 1) — số âm          |

**Tiền điều kiện:** hóa đơn gốc ở status 08 (CQT đã chấp nhận) và chưa từng bị điều chỉnh/thay thế (nếu rồi → Fast trả lỗi 901).

**Dialog (cấp 2 — nhiều bước):**

1. Chọn loại: Điều chỉnh giảm / Điều chỉnh tăng / Điều chỉnh thông tin / Thay thế.
2. Nhập **lý do** (bắt buộc), số & ngày biên bản thỏa thuận (nếu có).
3. Hệ thống tạo bản ghi FEI mới **sao chép từ bản gốc**, mở ra cho kế toán sửa dòng hàng.
4. Nhắc rõ trên form: *"Hóa đơn điều chỉnh giảm: nhập số **âm** ở các dòng cần giảm. Hóa đơn thay thế: nhập lại **toàn bộ** nội dung đúng."*

Từ đây bản ghi mới đi lại **đúng vòng đời từ trạng thái 01** (xem nháp → gửi khách → duyệt → phát hành cấp 3). Khi phát hành thành công: payload thêm `"originalInvoice": <keySearch bản gốc>` và `"adjustmentType"`; bản gốc chuyển status 10 hoặc 11, ghi `amended_from_fei` hai chiều.

---

### E10. Nút 13c — Hủy nội bộ ⚠️

**Bối cảnh pháp lý:** NĐ 70/2025 đã **bãi bỏ** thủ tục hủy hóa đơn thông thường. Hàm 330 chỉ còn dùng cho tình huống **hóa đơn bị CQT từ chối** — hủy trên hệ thống Fast để dữ liệu không lọt vào bảng kê bán ra.

**Tiền điều kiện:** `status == 09 (CQT từ chối)`. Không cho hủy hóa đơn đã được CQT chấp nhận (Fast cũng chặn: 78016, 900, 901).

**Dialog xác nhận cấp 3:** hiển thị lý do CQT từ chối (`tax_feedback`), yêu cầu nhập **lý do hủy** (bắt buộc), số & ngày biên bản (tùy chọn), và gõ chữ `HUY` để bật nút.

**Gọi API:** `action=0, method=330`, `data = {"key": keySearch, "reason": ..., "minuteNo": ..., "minuteDate": yyyyMMdd}`.

**Lưu DocType:** `cancel_reason`, `cancelled_time`, `status = 12`, mở khóa Delivery Note để cho phép tạo hóa đơn mới (xóa `fast_invoice_no` trên DN nhưng **giữ** liên kết lịch sử tới FEI đã hủy).

---

## PHẦN F — QUY TẮC VALIDATE TRƯỚC KHI GỬI

Hàm `validate_before_send()` chạy ở **3 thời điểm**: khi tạo bản ghi, khi mở form (bảng kết quả hiện ngay trên chứng từ), và **bắt buộc lại** ngay trước khi phát hành phía server.

**Chỉ nút PHÁT HÀNH bị chặn.** Xem bản nháp PDF chạy được kể cả khi chứng từ đang có lỗi mức Chặn: bản nháp không tiêu số hóa đơn, và nó chính là cách kế toán nhìn ra mình sai ở đâu — chặn nó lại là khóa đúng cái cửa dẫn tới chỗ sửa. Dữ liệu sai thì Fast trả lỗi, và mã lỗi của Fast nói đúng chỗ hơn phỏng đoán của ERP. Đồng bộ lại từ phiếu giao cũng không bao giờ bị chặn, vì đó là đường sửa dữ liệu.

| #  | Quy tắc                                                                                                                         | Mức       | Mã lỗi Fast tránh được |
| -- | -------------------------------------------------------------------------------------------------------------------------------- | ---------- | ---------------------------- |
| 1  | `fast_key` ≤32 ký tự, không dấu, không trùng bản ghi đã phát hành                                                  | Chặn      | 809, 835                     |
| 2  | Có MST →`customer_name` và `address` không được trống                                                                | Chặn      | 836                          |
| 3  | `customer_type=1` → MST đúng 10 hoặc 13 chữ số                                                                           | Chặn      | 78013                        |
| 4  | `id_card_no` nếu có → đúng 9 hoặc 12 chữ số                                                                            | Chặn      | 836                          |
| 5  | `amount_in_words` chứa đúng từ khóa loại tiền ("đồng"/"đô la Mỹ"/"Euro")                                           | Chặn      | 152                          |
| 6  | Không trường text nào chứa ký tự xuống dòng                                                                             | Chặn      | 825                          |
| 7  | `buyer` ≤100 · `item_name` ≤500 · `human_name` ≤128                                                                   | Chặn      | 812, 836                     |
| 8  | Mọi dòng có`process_type` khác rỗng                                                                                       | Chặn      | 836                          |
| 9  | Σ Amount dòng == master`amount`; Σ TaxAmount dòng == master `tax_amount`; `total_amount` == amount + tax − giảm trừ | Chặn      | lỗi số liệu               |
| 10 | Số dòng ≤ 300                                                                                                                 | Chặn      | 3000                         |
| 11 | `invoice_date` có mặt (chặn) · không nhỏ hơn ngày hóa đơn đã phát hành gần nhất (**cảnh báo** — Fast mới là bên phán quyết) | Chặn / Cảnh báo | 819 |
| 12 | Mọi dòng có`tax_rate` thuộc bộ mã hợp lệ                                                                               | Chặn      | 78025                        |
| 13 | Tên hàng/tên KH không chứa`&`, `<`, `>` (hoặc phải escape đúng)                                                   | Cảnh báo | 63505                        |
| 14 | `email_deliver` đúng định dạng, ≤256 ký tự                                                                             | Cảnh báo | 836                          |
| 15 | DN nguồn: đã submit, không phải trả hàng, chưa có FEI khác đang sống                                                 | Chặn      | —                           |
| 16 | Hóa đơn nhiều thuế suất → đã điền đủ TaxAmount0/5/10/Free                                                           | **Cảnh báo** — Fast không dùng bốn ô này để kê khai (đối chứng TEST 2026-09-08) | — |
| ~~17~~ | ~~Thuế 8% không có ô nhóm nào nhận~~ — **đã bỏ**: nổ ở gần như mọi hóa đơn mà không đòi hành động nào, chỉ làm người dùng bỏ qua bảng cảnh báo. Fast không dùng bốn ô này để kê khai (đối chứng TEST 2026-09-08) | — | — |

Kết quả validate hiển thị dạng bảng ngay trên form (đỏ = chặn, vàng = cảnh báo), kèm nút nhảy tới trường bị lỗi.

---

## PHẦN G — BẢNG MÃ LỖI → THÔNG BÁO TIẾNG VIỆT

| Code                   | Fast trả về                                            | Hiển thị cho kế toán                                                       | Hành động gợi ý tự động                            |
| ---------------------- | -------------------------------------------------------- | ------------------------------------------------------------------------------ | ---------------------------------------------------------- |
| 152                    | Đọc tiền bằng chữ không hợp lệ                   | "Số tiền bằng chữ chưa đúng với loại tiền tệ"                       | Tự sinh lại`amount_in_words`                           |
| 460                    | Tồn tại hóa đơn treo                                | "Có hóa đơn treo trên hệ thống Fast"                                    | Nút "Dọn hóa đơn treo" → gọi 370                    |
| 500/501/502            | Chứng thư số chưa có / chưa hiệu lực / hết hạn | "Chứng thư số HSM chưa sẵn sàng — liên hệ Fast"                       | Chặn phát hành toàn hệ thống, cảnh báo admin       |
| 601/808                | Hết số hóa đơn                                      | "Quyển hóa đơn 1C26TAA đã hết số"                                      | Cảnh báo kế toán trưởng đăng ký thêm             |
| 800/801                | Sai cấu trúc / data rỗng                              | "Lỗi kỹ thuật khi đóng gói dữ liệu"                                    | Ghi log chi tiết, báo dev                                |
| 802                    | Không có quyền                                        | "Tài khoản API không có quyền thực hiện"                                | Báo admin kiểm tra phân quyền portal                   |
| 809/835                | Trùng Key / hóa đơn đã tồn tại                   | "Hóa đơn này đã được phát hành trước đó"                        | Tự gọi 370 và hiển thị thông tin hóa đơn đã có |
| 812/825                | Vượt độ dài / có ký tự xuống dòng              | "Tên hàng hoặc thông tin khách hàng quá dài / có xuống dòng"        | Chỉ ra đúng dòng bị lỗi                              |
| 819/730/731            | Ngày hóa đơn không hợp lệ                         | "Ngày hóa đơn không hợp lệ hoặc nhỏ hơn hóa đơn đã phát hành" | Gợi ý ngày hợp lệ                                     |
| 836                    | Lỗi số liệu tổng hợp                                | "Thiếu thông tin bắt buộc của người mua hoặc tính chất hàng hóa"   | Chạy lại validate và chỉ rõ trường thiếu           |
| 888                    | (370) Không tìm thấy                                  | "Hóa đơn chưa tồn tại trên hệ thống Fast"                             | Cho phép phát hành                                      |
| 900/901                | Không tồn tại / đã bị điều chỉnh, thay thế     | "Hóa đơn gốc không hợp lệ để điều chỉnh/thay thế"                 | Kiểm tra lại chuỗi điều chỉnh                        |
| 1002                   | Trùng số do phát hành đồng thời                   | "Số hóa đơn bị trùng do nhiều người phát hành cùng lúc"           | Tự thử lại 1 lần sau 5 giây                           |
| 3000                   | Vượt số dòng                                         | "Hóa đơn vượt quá 300 dòng"                                             | Gợi ý tách hóa đơn                                   |
| 78011/78012            | Chứng thư/hình thức chưa đăng ký                 | "Khai báo trên portal Fast chưa đúng"                                     | Báo admin                                                 |
| 78013                  | MST người mua không hợp lệ                          | "Mã số thuế khách hàng không hợp lệ"                                   | Mở form Customer để sửa                                |
| 63505/63503/8031/10000 | Lỗi hệ thống ký số HSM                              | "Hệ thống ký số đang gặp sự cố — thử lại sau"                       | Cho retry; kiểm tra ký tự đặc biệt trong tên hàng  |

---

## PHẦN G2 — BẢNG MÃ LỖI ĐẦY ĐỦ CỦA FAST (tra cứu tại chỗ)

Chép nguyên từ mục 18 "Danh sách mã lỗi" của `HDDT Fast - HĐ Cấp mã CQT- Không mã hóa RSA.pdf`
(trang 40–47). Để ở đây để không phải mở lại file PDF mỗi lần tra.

**Luật của Phần F:** mọi quy tắc mức **Chặn** phải trỏ được về một mã trong bảng này. ERP
không tự đặt thêm điều kiện chặn của riêng mình — Fast mới là bên quyết định hóa đơn có phát
hành được hay không. Cột cuối cho biết quy tắc nào đang gác mã nào; `TestNothingBlocksMoreThanFastDoes`
trong `test_fast_validation.py` bắt lỗi ngay nếu có ai thêm một điểm chặn không nêu được căn cứ.

**Ngoại lệ duy nhất — quy tắc 15 (chứng từ nguồn):** phiếu giao phải có thật, đã submit, không
phải phiếu trả hàng, và chưa có hóa đơn nào khác đang sống. Fast không biết phiếu giao là gì
nên không có mã lỗi tương ứng. Đây là luật kế toán của Miyano, được ghi thành ngoại lệ có tên
trong test chứ không lẫn vào các quy tắc khác.

| Mã | Nghiệp vụ | Fast mô tả | Ghi chú của Fast | Quy tắc ERP |
| --- | --- | --- | --- | --- |
| `101` | Phát hành token | Không tìm thấy thông tin hóa đơn gốc. | | — |
| `131` | Phát hành HSM | Không lấy được thông tin chữ ký số. | | — |
| `132` | Phát hành HSM | Không lấy được thông tin thanh toán của tài khoản ký số hoặc thông tin thanh toán không hợp lệ. | | — |
| `133` | Phát hành HSM | Chưa có thông tin thanh toán của tài khoản ký số. | | — |
| `134` | Phát hành HSM | Thông tin thanh toán của tài khoản ký số không hợp lệ. | | — |
| `135` | Phát hành HSM | Hệ thống không phản hồi kết quả ký số. | | — |
| `136` | Phát hành HSM | Hệ thống không phản hồi thông tin thanh toán của tài khoản ký số. | | — |
| `152` | Phát hành token | Tồn tại hóa đơn đọc tiền bằng chữ không hợp lệ. | Kiểm tra chữ “đồng” với VND, “đô la Mỹ” với USD, “Euro” với EUR. Chỉ hỗ trợ 4 mã: VND, USD, JPY, EUR. | QT5 |
| `435` | Phát hành token | Chứng thư số không hợp lệ. | | — |
| `460` | Phát hành token | Tồn tại hóa đơn (treo) trên hệ thống. | | — |
| `500` | Phát hành token | Thông tin chứng thư chưa có trên hệ thống. | | — |
| `501` | Phát hành token | Chứng thư chưa đến thời điểm sử dụng. | | — |
| `502` | Phát hành token | Chứng thư đã hết hạn. | | — |
| `601` | Phát hành token | Hóa đơn đã sử dụng hết hoặc có lỗi chưa xác định, chương trình không thể phát hành tiếp được. | | — |
| `602` | Phát hành token | Thiết lập hình thức ký số chưa đúng. | | — |
| `604` | Phát hành token | Thông tin chứng thư số hệ thống (HSM) không hợp lệ. | | — |
| `611` | Phát hành token | Thông tin hóa đơn điều chỉnh không đúng. | | — |
| `701` | Phát hành token | Chưa khai báo sử dụng quyển cho đơn vị. | | — |
| `702` | Phát hành token | Ngày hóa đơn không thuộc giới hạn trong phân loại hóa đơn. | | — |
| `703` | Phát hành token | Chưa khai báo quyển ngầm định cho cho đơn vị. | | — |
| `705` | Phát hành token | Số lượng hóa đơn truyền vào lớn hơn số lượng cho phép. | | — |
| `711` | Phát hành token | Loại hóa đơn không đúng. Vui lòng kiểm tra lại. | | — |
| `730` | Phát hành token | Ngày hóa đơn vượt quá số ngày được phép phát hành sau ngày hiện tại. | | — |
| `731` | Phát hành token | Ngày hóa đơn không hợp lệ. | | — |
| `800` | Phát hành token | Hệ thống không nhận dạng được tệp đầu vào. | | — |
| `801` | Phát hành token | Hệ thống không nhận dạng được tệp đầu vào. | | — |
| `802` | Hủy | Tài khoản không đúng hoặc không có quyền thực hiện chức năng này. | | — |
| `803` | Phát hành token | Thông tin đơn vị không đúng hoặc không còn sử dụng. | | — |
| `804` | Phát hành token | Thông tin loại hóa đơn không được trống. | | — |
| `807` | Phát hành token | Mẫu số và ký hiệu không phù hợp. | | — |
| `808` | Phát hành token | Dãy số hóa đơn cũ đã hết. | | — |
| `809` | Phát hành token | Có hóa đơn trùng khóa trong chuỗi dữ liệu. | | QT1 |
| `810` | Phát hành token | Lỗi chưa xác định khi xử lý dữ liệu. | | — |
| `812` | Phát hành token | Lỗi dữ liệu đầu vào vượt quá giới hạn cho phép. | Ví dụ tên mặt hàng > 500 ký tự, tên người mua > 128 ký tự. | QT1 · QT7 |
| `813` | Phát hành token | Lỗi dữ liệu đầu vào không được rỗng. | | QT1 · QT5 · QT8 · QT11 |
| `814` | Phát hành token | Chuỗi kiểm tra không đúng với dữ liệu. | | — |
| `815` | Phát hành token | Lỗi khi tạo xml cho hóa đơn. | | — |
| `816` | Phát hành token | Lỗi khi tạo khóa tra cứu cho hóa đơn. | | — |
| `817` | Phát hành token | Ngày hóa đơn không hợp lệ. | | — |
| `818` | Phát hành token | Ngày hóa đơn không thuộc giới hạn phát hành cho phép. | Giới hạn số ngày được phép phát hành so với ngày hiện tại. | — |
| `819` | Phát hành token | Tồn tại hóa đơn có ngày nhỏ hơn hóa đơn đã có. | | QT11 (cảnh báo) |
| `825` | Phát hành token | Tên hàng hóa hoặc tên khách hàng, địa chỉ chứa ký tự xuống dòng. | | QT6 |
| `835` | Phát hành token | Hóa đơn này đã tồn tại. Vui lòng kiểm tra lại. | | — |
| `836` | Phát hành HSM | Không phát hành được hóa đơn do lỗi về số liệu — hệ thống chặn không cho xuất. | Fast liệt kê các nguyên nhân: tính chất hàng hóa rỗng · email người mua có ký tự ẩn hoặc vượt giới hạn · có MST người mua nhưng thiếu tên đơn vị mua và địa chỉ · họ tên người mua > 100 ký tự. | QT2 · QT4 · QT8 · QT9 |
| `900` | Phát hành token | Không tồn tại hóa đơn cần điều chỉnh/thay thế/hủy. | | — |
| `901` | Phát hành token | Hóa đơn đã bị điều chỉnh hoặc thay thế. | | — |
| `902` | Hủy | Tồn tại hóa đơn điều chỉnh cho hóa đơn này chưa được hủy. | | — |
| `1002` | Phát hành token | Lỗi số hóa đơn đã được cấp. Bị trùng số. | | — |
| `1011` | Phát hành token | Không được phát hành hóa đơn điều chỉnh cho loại hóa đơn này. | | — |
| `3000` | Phát hành token | Tồn tại hóa đơn có số lượng dòng vượt quá số lượng cho phép. | Mỗi XML hóa đơn truyền sang cơ quan thuế tối đa 1MB. | QT10 |
| `8031` | Phát hành HSM | access_token null. | | — |
| `10000` | Phát hành HSM | Lỗi không xác định khi dùng chữ ký số HSM của SmartSign Vina. | | — |
| `63503` | Phát hành HSM | xml invalid. | | — |
| `63505` | Phát hành HSM | signature invalid. | | QT13 (cảnh báo) |
| `78001` | Phát hành token | Chưa khai báo doanh nghiệp truyền nhận dữ liệu cơ quan thuế. | | — |
| `78010` | Phát hành token | Mã số thuế trong chứng thư số không khớp với thông tin đơn vị. | | — |
| `78011` | Phát hành token | Thông tin chứng thư số chưa đăng ký trên tờ khai sử dụng hóa đơn điện tử. | | — |
| `78012` | Phát hành token | Hình thức hóa đơn của khai báo phân loại không phù hợp. | | — |
| `78013` | Phát hành token | Mã số thuế người mua không hợp lệ. | | QT3 |
| `78014` | Phát hành token | Thông tin đơn vị bán hàng có dữ liệu vượt quá giới hạn cho phép. | | — |
| `78015` | Phát hành token | Thông tin đơn vị bán hàng có dữ liệu không hợp lệ. | | — |
| `78016` | Phát hành token | Không được hủy hóa đơn điều chỉnh. | | — |
| `78017` | Hủy | Không được hủy hóa đơn thay thế. | | — |
| `78025` | Phát hành token | Thuế suất cần cập nhật giá trị khi tính chất khác ghi chú/diễn giải. | | QT12 |

---

## PHẦN H — LỘ TRÌNH XÂY DỰNG TỪ ĐẦU

### Giai đoạn 0 — Chuẩn bị với Fast (1–2 ngày, không code)

Checklist bắt buộc hoàn thành trước khi viết dòng code đầu tiên:

- [ ] Fast xác nhận **đã bật chế độ không mã hóa RSA** cho DN 008254
- [ ] Fast xác nhận **chứng thư số HSM** đã khai báo và tờ khai HĐĐT đã được CQT chấp nhận
- [ ] Xin **user API riêng** cho ERP (khác `hieu.cv2@...` mà người dùng đang đăng nhập web)
- [ ] Xin **tài khoản môi trường TEST** (`https://tportal.fast.com.vn:9000/...`)
- [ ] Xác nhận quyển `1C26TAA` / ký hiệu `1C26TMY` còn số, xem hạn mức
- [ ] Hỏi Fast: method 360 (xác nhận thanh toán) Miyano có cần không; API hóa đơn máy tính tiền có tài liệu riêng không
- [ ] **Xử lý hóa đơn test `TESTPM260807A` đã lỡ phát hành thật** — kế toán trưởng quyết phương án (thay thế hoặc điều chỉnh) và ghi biên bản

### Giai đoạn 1 — Rà soát dữ liệu ERP (1–2 ngày)

- [ ] Kiểm tra Delivery Note có gắn **Sales Taxes and Charges Template** không; nếu chưa → bổ sung (đây là điều kiện tiên quyết, thuế là con số pháp lý không được đoán)
- [ ] Kiểm tra Item có **Item Tax Template** để lấy thuế suất từng dòng
- [ ] Rà `tax_id`, billing address, email trên toàn bộ Customer đang hoạt động → làm sạch dữ liệu (đây là nguồn của lỗi 836)
- [ ] Chuẩn hóa bảng UOM sang tên tiếng Việt (Cái, Chiếc, Bộ, Hộp, Kg…)
- [ ] Thống nhất quy tắc `customer_type` (dựa trên Customer Group hay custom field)

### Giai đoạn 2 — Khung custom app (2–3 ngày)

- [ ] `bench new-app miyano_einvoice` · cài lên site
- [ ] Tạo 4 DocType theo Phần C (dùng fixtures để version-control)
- [ ] Tạo 4 custom field trên Delivery Note
- [ ] Tạo 2 Role: **Kế toán HĐĐT** (tạo nháp, gửi khách, xem PDF) và **Kế toán trưởng HĐĐT** (thêm quyền phát hành, điều chỉnh, thay thế, hủy). Nút cấp 3 chỉ hiện với role thứ hai
- [ ] Đưa module `fast_client.py` vào app (đã có sẵn: SOAP, hash, token, encode/decode, đọc số thành chữ)

### Giai đoạn 3 — Luồng nháp & duyệt khách (3–4 ngày)

- [ ] Nút 1, 2, 3, 4, 5, 6 (E1–E4)
- [ ] Toàn bộ validate Phần F + bảng hiển thị lỗi
- [ ] 2 Email Template (nháp / chính thức)
- [ ] Test end-to-end trên **môi trường test**, chỉ dùng `action=600`

- ✅ **Mốc kiểm chứng:** kế toán tạo được nháp, gửi khách, ghi nhận sửa, đánh dấu duyệt — chưa hề chạm tới phát hành thật

### Giai đoạn 4 — Phát hành & sau phát hành (3–4 ngày)

- [ ] Nút 7 với dialog cấp 3 + Redis lock + tiền kiểm 370 (E5)
- [ ] Nút 8, 9, 10 (PDF & email)
- [ ] Nút 11, 12 + scheduled job poll CQT
- [ ] Xử lý đủ 3 nhánh 7a/7b/7c, đặc biệt nhánh timeout

- ✅ **Mốc kiểm chứng:** phát hành thành công trên môi trường test, PDF về đúng, trạng thái CQT cập nhật

### Giai đoạn 5 — Điều chỉnh / thay thế / hủy (2–3 ngày)

- [ ] Nút 13a, 13b, 13c (E9, E10)
- [ ] Sơ đồ liên kết hai chiều giữa hóa đơn gốc và hóa đơn con
- [ ] Report "Đối soát hóa đơn điện tử": danh sách DN chưa xuất hóa đơn, hóa đơn chờ CQT quá 24h, hóa đơn lỗi

### Giai đoạn 6 — Kiểm thử & go-live (3–5 ngày)

Kịch bản test bắt buộc trên môi trường test:

| #  | Kịch bản                                                       | Kỳ vọng                                                                         |
| -- | ---------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| 1  | Khách doanh nghiệp có MST, 1 dòng hàng, VAT 10%             | Phát hành thành công                                                          |
| 2  | Khách cá nhân không MST, có CCCD                            | Thành công                                                                      |
| 3  | Có MST nhưng xóa địa chỉ                                   | Xem nháp **vẫn được** (để thấy chỗ sai); phát hành bị chặn tại ERP, **không** gọi API |
| 4  | Hóa đơn nhiều thuế suất (0% + 5% + 10%)                    | Tổng theo nhóm đúng                                                           |
| 4b | Hóa đơn 5% + 8%                                            | Fast nhận, CQT chấp nhận; bốn ô nhóm cộng thiếu phần 8% là bình thường          |
| 5  | Hóa đơn 250 dòng                                             | Thành công, không timeout                                                      |
| 6  | Bấm nút phát hành 2 lần liên tiếp                         | Lần 2 bị lock chặn, chỉ 1 hóa đơn ra đời                                 |
| 7  | Ngắt mạng giữa lúc phát hành                               | Trạng thái "Cần đối soát", 370 xác định đúng, không phát hành đúp |
| 8  | Token hết hạn giữa chừng                                     | Tự CheckKey→GetKey→retry, người dùng không thấy lỗi                      |
| 9  | Vòng nháp: gửi khách → sửa 2 lần → duyệt → phát hành | `revision_count = 2`, lịch sử đầy đủ trong DocType                        |
| 10 | Điều chỉnh giảm sau khi CQT chấp nhận                      | Số âm đúng, liên kết 2 chiều đúng                                        |
| 11 | Thay thế hóa đơn                                             | Bản gốc chuyển trạng thái 11                                                 |
| 12 | Sai đọc tiền bằng chữ (cố ý)                              | Validate chặn trước, nếu vượt qua thì bắt được lỗi 152                |

Điều kiện go-live: 12/12 kịch bản đạt · đã đào tạo kế toán · đã có quy trình xử lý sự cố bằng văn bản · **1 tuần đầu chạy song song** (đối chiếu thủ công ERP với portal Fast mỗi cuối ngày).

---

## PHẦN I — CẤU TRÚC JSON GỬI ĐI (tham chiếu nhanh)

```json
{
  "voucherBook": "1C26TAA",
  "originalInvoice": "<keySearch hóa đơn gốc — CHỈ khi điều chỉnh/thay thế>",
  "adjustmentType": "1",
  "data": {
    "structure": {
      "master": ["Key","InvoiceDate","CustomerCode","Buyer","CustomerName",
                 "CustomerTaxCode","CustomerType","Address","PhoneNumber","FaxNumber",
                 "EmailDeliver","BankAccount","BankName","PaymentMethod","Currency",
                 "ExchangeRate","Amount","TotalAmount","TaxRate","TaxAmount",
                 "TaxAmountFree","TaxAmount0","TaxAmount5","TaxAmount10",
                 "DiscountAmount","PromotionAmount","AmountInWords","HumanName"],
      "detail": ["ProcessType","ItemCode","ItemName","UOM","IsPromotion","Quantity",
                 "Price","Amount","DiscountRate","DiscountAmount","TaxRate","TaxAmount"]
    },
    "invoices": [{
      "master": ["MAT-DN-2026-00001","07/08/2026","KH0001","Nguyễn Văn A",
                 "Bệnh viện Đa khoa X","0101234567","1","Số 1 Phố Y, Hà Nội",
                 "0912345678","","kt@bvx.vn","","","CK","VND",1.0,
                 10000000,11000000,10,1000000,0,0,0,1000000,0,0,
                 "Mười một triệu đồng chẵn","Chu Văn Hiếu"],
      "detail": [["1","VT001","Bơm kim tiêm 5ml","Cái",0,100,100000,10000000,0,0,10,1000000]]
    }]
  }
}
```

Quy tắc đóng gói: JSON → UTF-8 → **Base64** → tham số `data`. Tên thẻ đúng hoa/thường tuyệt đối. Trường không dùng thì **bỏ hẳn khỏi structure** (không gửi thẻ rỗng). Số gửi dạng number, không phải chuỗi. Escape `&` `<` `>` trước khi nhúng vào XML envelope.

**Bảng action/method dùng trong dự án:**

| Nghiệp vụ                  | action | method |
| ---------------------------- | ------ | ------ |
| Xem PDF nháp                | 600    | 310    |
| Phát hành hóa đơn (HSM) | 0      | 310    |
| Điều chỉnh                | 0      | 320    |
| Thay thế                    | 0      | 350    |
| Hủy nội bộ                | 0      | 330    |
| Truy vấn hóa đơn         | 0      | 370    |
| Tải PDF chính thức        | 0      | 380    |
| Tải PDF chuyển đổi       | 0      | 385    |
| Gửi lại email (Fast gửi)  | 0      | 700    |
| Trạng thái CQT             | 0      | 8200   |

---

## PHẦN J — CÂU HỎI CÒN MỞ CẦN CHỐT

1. `require_customer_approval` bật hay tắt mặc định? (Khuyến nghị: **bật** — mọi hóa đơn phải qua bản nháp được khách duyệt, vì sửa hóa đơn đã phát hành rất tốn công.)
2. Gửi email hóa đơn chính thức: ERP tự gửi hay để Fast gửi (method 700)? (Khuyến nghị: **ERP tự gửi**, method 700 làm dự phòng.)
3. Có cần gộp nhiều Delivery Note của cùng khách thành 1 hóa đơn không? (Nếu có, DocType cần đổi `delivery_note` thành child table nhiều dòng — nên chốt **trước** khi code.)
4. Miyano có phát sinh Phiếu xuất kho kiêm vận chuyển nội bộ không (method 319/328/358/338)?
5. Ai được cấp role "Kế toán trưởng HĐĐT" (quyền phát hành)?

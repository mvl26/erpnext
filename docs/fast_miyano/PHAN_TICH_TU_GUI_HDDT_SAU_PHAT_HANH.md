# PHÂN TÍCH: GỬI HÓA ĐƠN ĐIỆN TỬ CHO KHÁCH — TỰ GỬI, TRA CỨU QUA LINK, ĐỒNG BỘ LẠI CHỨNG TỪ NGUỒN

**Bản 2.2 — ngày 21/10/2026** (đã chốt toàn bộ mục 11) — nhánh `feat/vn-hddt-provider` — liên quan: `SPEC_FAST_EINVOICE_ERPNEXT_v2.md` (mục E3, E5–E8), `RUNBOOK_HDDT_FAST.md`, `Mau_Email_Gui_Hoa_Don_Miyano.md`

> **Bản 2.1 (21/10):** đã chốt hai điểm.
> (1) Mã tra cứu lấy từ PDF: giải mã base64 của method 380 rồi đọc chữ, lưu vào trường mới `fast_lookup_code` (mục 4.3).
> (2) XML không bắt buộc ở mọi luồng: lấy được thì đính kèm, không được thì thôi. Q2 coi như đã chốt; mục 4.4 mới mô tả nguồn lấy XML.
>
> Đã triển khai ngày 21/10/2026 theo `docs/superpowers/plans/2026-10-21-hddt-email-tra-cuu-tu-gui.md` (mục 11 là quyết định đã làm, kể cả hai đề xuất Q7).
> Bản 2 thay cho bản ngày 19/10. Bản này bổ sung: dữ liệu Fast trả về để gửi dạng tra cứu, mẫu email theo `Mau_Email_Gui_Hoa_Don_Miyano.md`, các trường hợp người nhận bị lệch, và nút Đồng bộ lại.
> Các câu hỏi phải chốt trước khi làm được gom ở **mục 11**.

---

## 1. Tóm tắt

**Ba yêu cầu:**

1. **Tự gửi** hóa đơn cho khách khoảng 1 phút sau phát hành, bật/tắt trong Settings.
2. **Nội dung email dạng tra cứu**: khách bấm link hoặc vào cổng tra cứu của Fast, nhập mã tra cứu. Nội dung theo mẫu Miyano.
3. **Nút Đồng bộ lại** đặt ra ngoài, để lấy lại dữ liệu từ chứng từ nguồn khi nguồn có chỉnh sửa.

**Kết luận chính:**

- **Fast không trả đủ thông tin để gửi dạng tra cứu chỉ qua API.** API chỉ trả `keySearch`, là một chuỗi base64 dài khoảng 70 ký tự (`AQAAAGds…==008254`). Mã khách nhập trên trang tra cứu thì **khác**: đó là mã ngắn in trên PDF (`6D A83 217 253 61N 682`). API cũng không trả địa chỉ trang tra cứu. Cả mã ngắn lẫn địa chỉ trang tra cứu chỉ có trong **file PDF**.
- **Làm được nếu đọc từ PDF.** PDF chính thức vốn đã tự tải về khoảng 1–2 phút sau phát hành. Mình đã thử bằng `pypdf` (có sẵn trong bench) trên PDF thật của FEI-2026-00005 và lấy được cả mã tra cứu lẫn link. Đổi lại, cách này phụ thuộc vào bố cục PDF của Fast, nên cần có đường lùi khi không đọc được (mục 4.3).
- **Mẫu email hiện tại đang hiển thị sai mã tra cứu.** Dòng "Mã tra cứu" in `fast_key_search`, tức chuỗi base64 dài, không phải mã khách cần nhập. Lỗi này nên sửa dù có làm tính năng tự gửi hay không.
- **Link xem PDF trên ERP (`public_pdf_url`) đang hỏng nếu sinh từ job nền.** Site chưa cấu hình `host_name`, nên `get_url()` trả `http://miyano`, địa chỉ này khách bên ngoài không mở được.
- **Mã CQT chưa có ở thời điểm 1–2 phút.** Mẫu email Miyano yêu cầu "chỉ gửi sau khi có mã của cơ quan thuế". Job hỏi CQT chạy 20 phút một lần, nên tự gửi phải tự hỏi CQT (method 8200) cho riêng hóa đơn đó trước khi gửi.
- **Fast có thể đã tự gửi mail theo `EmailDeliver`.** Đây vẫn là câu hỏi số 1, vì nếu đúng thì khách nhận trùng email.
- **Nút Đồng bộ lại** hiện nằm trong menu xổ "Hóa đơn điện tử", và ghi đè toàn bộ dữ liệu mà không cho xem trước. Đề xuất đưa nút ra ngoài, kèm hộp thoại so sánh "đang có → từ nguồn" trước khi ghi đè.
- **Khối lượng:** khoảng 3 ngày công (ước lượng thô), tính sau khi đã chốt mục 11.

---

## 2. Dữ liệu Fast trả về

### 2.1. Theo tài liệu API (đã đối chiếu với `HDDT Fast - HĐ Cấp mã CQT- Không mã hóa RSA.pdf`)

| Method | Trả về | Lưu vào trường | Dùng cho email |
|---|---|---|---|
| 310/320/350 (phát hành) | `key`, `pattern`, `serial`, `invoiceNo`, `keySearch`, `signedDate` | `fast_key`, `fast_pattern`, `fast_serial`, `fast_invoice_no`, `fast_key_search`, `fast_signed_date` | Số, ký hiệu, ngày: **có**. `keySearch`: **không**, đây là khóa kỹ thuật dùng cho API |
| 370 (truy vấn) | Các trường trên, thêm `typeVoucher` | — | Không thêm gì |
| 8200 (trạng thái CQT) | `taxStatus`, `verificationCode`, `feedbackContent` | `tax_status`, `tax_verification_code`, `tax_feedback` | **Mã CQT: có**, nhưng chỉ sau khi đã hỏi |
| 380 / 385 | PDF dạng base64 | `official_pdf` / `converted_pdf` | File đính kèm, đồng thời là nguồn mã tra cứu ngắn và link tra cứu |
| 700 | Fast gửi lại mail thông báo phát hành | — | Kênh gửi thay thế (mục 3, phương án L3) |

API **không có**: địa chỉ trang tra cứu, mã tra cứu ngắn, file XML, link mở thẳng tới một hóa đơn.

### 2.2. Đối chiếu trên dữ liệu thật

| | Giá trị (FEI-2026-00005) |
|---|---|
| `fast_key_search` (API trả về) | `AQAAAGdsR7FQfhxF8IACz4v01/XvwBjhL+ksBSqXgrbB91P2PKS32oMqcH7t4nSJBlxO5w==008254` |
| Mã tra cứu in trên PDF | `6D A83 217 253 61N 682` |
| Link tra cứu in trên PDF | `https://tinvoice.fast.com.vn:8000/` (đây là **môi trường TEST**) |
| MCQT in trên PDF | `TEST0000000020260908T154940190TEST` (khớp với `tax_verification_code`) |
| Ký hiệu | `fast_pattern` = `1`, `fast_serial` = `C26TAA`. PDF in gộp thành `1C26TAA` |

Cả 3 PDF chính thức trên site (FEI-2026-00001, 00003, 00005) đều có cùng bố cục: dòng "Mã tra cứu hóa đơn (Invoice code)" và dòng "Tra cứu tại (Search on)".

### 2.3. Trang tra cứu của Fast

- `https://tinvoice.fast.com.vn:8000/` là một trang ASP.NET, gọi `./AppHandler/EInvoiceQuery.ashx`. Trang có **ảnh captcha**, khách phải tự nhập mã tra cứu và captcha.
- Không có tài liệu nào về link mở thẳng tới một hóa đơn (dạng `?key=…`). Chưa kiểm chứng được trang có nhận chuỗi `keySearch` dài hay không, vì phải vượt captcha.
- Chưa biết địa chỉ trang tra cứu của **production**. Mọi PDF trên site đều sinh từ môi trường TEST.

---

## 3. Phương án gửi "dạng tra cứu"

| # | Phương án | Khách làm gì | Cần gì | Đánh giá |
|---|---|---|---|---|
| **L1** | Email ghi **link trang tra cứu Fast + mã tra cứu ngắn** | Mở link, nhập mã và captcha, xem hoặc tải PDF/XML | Đọc mã và link từ PDF (mục 4.3); địa chỉ production lấy từ PDF hoặc hỏi Fast | **Khuyến nghị.** Giống cách MISA làm trong mẫu Miyano. Khách tự tải được **XML** trên trang tra cứu, nhờ vậy gỡ được vướng mắc thiếu XML |
| L2 | Email ghi **link thẳng tới PDF trên ERP** (`public_pdf_url`) | Bấm là mở PDF | Site phải có **tên miền công khai** và đặt `host_name`; mở file công khai ra internet | Tiện cho khách, nhưng hiện link sinh ra là `http://miyano`, khách không mở được. Chỉ nên bật khi có tên miền. Không có XML |
| L3 | **Nhờ Fast gửi**: `EmailDeliver` lúc phát hành, hoặc method 700 | Theo mẫu mail của Fast | Không cần thêm gì | Không theo được mẫu Miyano, không CC được, ERP không lưu Communication. Có thể đang chạy sẵn (câu hỏi Q1) |
| L4 | **Đính kèm PDF** (đang làm) | Mở file đính kèm | — | Giữ nguyên, dùng song song với L1 |

**Đề xuất:** dùng L1 + L4, tức email theo mẫu Miyano gồm link tra cứu, mã tra cứu ngắn và PDF đính kèm. Dòng link L2 chỉ hiện khi Settings có tên miền công khai. L3 tùy kết quả Q1.

**Đã chốt (21/10): XML không bắt buộc**, áp dụng cho cả tự gửi lẫn gửi tay bằng nút 10. Email luôn kèm PDF; có `official_xml` thì kèm thêm XML, không có thì gửi không kèm XML. Nguồn lấy XML: xem mục 4.4.

---

## 4. Mẫu email mới

### 4.1. Ánh xạ biến của mẫu Miyano sang dữ liệu

| Biến trong `Mau_Email_Gui_Hoa_Don_Miyano.md` | Nguồn | Tình trạng |
|---|---|---|
| `ten_khach_hang` | `customer_name` | Có |
| `nguoi_nhan` | `buyer` (người liên hệ) | Có, thường để trống thì ghi "Quý khách" |
| `so_hd` | `fast_invoice_no` | Có. Fast trả `4`, không có số 0 đứng trước. Cần chốt: in nguyên `4` hay đệm thành `00000004` |
| `ngay_hd` | `fast_signed_date` | Có |
| `ky_hieu` | `fast_pattern` + `fast_serial` = `1C26TAA` | Có, phải ghép hai trường. Mẫu hiện tại in tách "Ký hiệu C26TAA" và "Mẫu số 1" |
| `ma_cqt` | `tax_verification_code` | **Chỉ có sau khi hỏi 8200**. Tự gửi phải hỏi trước (mục 6.2) |
| `link_tra_cuu` | **Mới**: đọc từ PDF, nếu không được thì lấy từ Settings | Cần làm (mục 4.3) |
| `ma_tra_cuu` | **Mới**: đọc từ PDF | Cần làm (mục 4.3) |
| `so_hop_dong_po` | `po_no` trên Sales Invoice | Có trường, nhưng dữ liệu hiện đang trống. Trống thì ẩn dòng |
| `tong_tien` | `total_amount` | Có |
| `han_thanh_toan` | `due_date` trên Sales Invoice | Có |
| `nguoi_gui`, `sdt_nguoi_gui`, `email_nguoi_gui` | **Mới**: lấy từ Settings | Tự gửi không có người bấm nút, nên cần một đầu mối cố định. Gửi tay thì lấy người đang đăng nhập |

### 4.2. Mẫu đề xuất

Thay nội dung *Fast HĐĐT - Hóa đơn chính thức* bằng bản đầy đủ ở mục 6 của mẫu Miyano. Có bốn chỗ chỉnh:

- **Bỏ** cụm "và ký điện tử trên hóa đơn". Đó là tính năng của MISA; chưa xác nhận cổng tra cứu của Fast có cho người mua ký hay không.
- Câu về XML viết theo file đính kèm:
  - email có kèm XML: *"Đính kèm: hóa đơn dạng PDF và file XML (hóa đơn điện tử gốc)."*
  - email không kèm XML: chỉ ghi file PDF. Thêm câu *"Quý khách có thể tải file XML tại trang tra cứu"* **chỉ khi** đã kiểm chứng trang tra cứu của Fast thật sự có nút tải XML.
- Dòng "Xem / tải hóa đơn" (L2) chỉ hiện khi có `public_pdf_url` với tên miền công khai.
- Dòng PO và dòng hạn thanh toán chỉ hiện khi có dữ liệu.

Tiêu đề email: `CÔNG TY TNHH MIYANO VIỆT NAM gửi hóa đơn điện tử số {{ so_hd }} cho {{ ten_khach_hang }}`.

Email đặt `reply_to` là email đầu mối trong Settings, vì mẫu Miyano cho phép khách phản hồi. Email CC tới hộp thư kế toán Miyano (Settings) để lưu vết, theo quy tắc 3 của mẫu.

**Cách cập nhật mẫu:** `setup.py` hiện chỉ tạo mẫu khi chưa có trên site. Mẫu đã có chỉ được vá từng đoạn nhỏ. Vì vậy cần một patch thay nội dung mẫu, nhưng chỉ khi mẫu còn y như bản gốc hệ thống tạo; nếu kế toán đã sửa tay thì giữ nguyên và ghi log.

### 4.3. Lấy mã tra cứu và link tra cứu từ PDF (đã chốt 21/10)

- Method 380 trả PDF dạng base64. `download_official_pdf` vốn đã giải mã chuỗi này (`decode_message`) để lưu file. Ngay tại bước đó, đọc chữ từ chính các byte PDF vừa giải mã bằng `pypdf`, không cần gọi Fast thêm lần nào, rồi tìm theo mẫu, không phân biệt khoảng trắng hay xuống dòng:
  - `Mã tra cứu hóa đơn (Invoice code): <mã>` → trường mới `fast_lookup_code`
  - `Tra cứu tại (Search on): <url>` → trường mới `fast_lookup_url`
- Đã thử trên PDF thật: `pypdf` 6.12.0 tách chữ thành nhiều dòng (`Mã tra cứu hóa đơn\n \n(Invoice code)\n:\n \n6D A83…`). Biểu thức tìm kiếm phải chịu được kiểu tách dòng này.
- **Đường lùi:**
  - Không đọc được link thì dùng `lookup_url` trong Settings.
  - Không đọc được mã thì **không tự gửi**: ghi comment *"Không đọc được mã tra cứu từ PDF, cần gửi tay"* và báo `notify_on_error`.
  - Gửi tay: hai trường mới sửa được trên form, kế toán chép mã từ PDF vào.
- **Hóa đơn đã có PDF từ trước:** một patch đọc lại các file `official_pdf` đang có để điền `fast_lookup_code` / `fast_lookup_url`. Trên site hiện có 3 chứng từ: FEI-2026-00001, 00003, 00005.
- Bấm tải lại PDF chính thức thì đọc lại mã; mã đọc được ghi đè giá trị cũ.
- **Hỏi Fast** (câu hỏi Q5): API có trả mã tra cứu ngắn không, và có link mở thẳng tới hóa đơn không. Nếu có, dùng API thay cho việc đọc PDF.

### 4.4. File XML (không bắt buộc)

Mục đích: lưu XML vào ERP làm bản lưu trữ, và đính kèm email khi có. **Không có XML thì không chặn việc gì.**

| Thứ tự | Nguồn | Tình trạng |
|---|---|---|
| 1 | **Method tải XML của Fast**, nếu Fast cung cấp | Chờ trả lời Q5. Nếu có: tải tự động ngay sau khi tải PDF, cùng job, cùng giới hạn số lần thử, lưu vào `official_xml` |
| 2 | **Kế toán tải trên portal Fast rồi đính tay** vào trường *XML hóa đơn* | Đang có sẵn, giữ nguyên |
| — | Tự động lấy qua trang tra cứu (vượt captcha) | **Không làm.** Captcha là cơ chế Fast dùng để chặn truy cập tự động vào trang của họ. Mục đích lưu trữ hóa đơn của chính Miyano là chính đáng, nhưng muốn tự động hóa thì phải qua kênh Fast cho phép: API, hoặc văn bản đồng ý của Fast. Cách lách captcha cũng hỏng ngay khi Fast đổi trang hay đổi kiểu captcha |

Đổi kèm theo: `_send_invoice_via_erp` bỏ điều kiện bắt buộc `official_xml`, chỉ còn bắt buộc `official_pdf`.

---

## 5. Người nhận email

### 5.1. Hiện trạng

Gửi nháp (nút 4) và gửi chính thức (nút 10) cùng lấy `email_deliver` ("Email nhận hóa đơn") làm người nhận mặc định. Người dùng sửa được người nhận trong dialog, và địa chỉ đã sửa **không ghi ngược** vào trường. Địa chỉ thực gửi lưu ở `draft_sent_to` / `invoice_sent_to`.

`email_deliver` được điền khi tạo chứng từ, theo thứ tự ưu tiên: `contact_email` trên Sales Invoice → `email_id` của Customer → email của địa chỉ thanh toán chính. Bấm Đồng bộ lại thì điền lại theo đúng thứ tự này.

### 5.2. Các trường hợp bản nháp và bản chính thức đi tới hai địa chỉ khác nhau

| # | Trường hợp |
|---|---|
| 1 | Sửa người nhận trong dialog gửi nháp. Dialog gửi chính thức lại điền sẵn `email_deliver` cũ |
| 2 | Sửa người nhận trong dialog gửi chính thức |
| 3 | Sửa `email_deliver` trên form ở trạng thái 03/04. Trường vẫn sửa được, và **không quay về Nháp**, không bắt gửi nháp lại |
| 4 | Fast tự gửi theo `EmailDeliver` tại thời điểm phát hành, không biết dialog đã sửa gì (nếu Q1 = có) |
| 5 | Gửi nháp nhiều lần tới các địa chỉ khác nhau. `draft_sent_to` chỉ giữ lần cuối |
| 6 | Hóa đơn điều chỉnh/thay thế sao `email_deliver` của hóa đơn gốc, không sao địa chỉ thực tế đã gửi |

**Đã xảy ra trên site:** FEI-2026-00003 có `email_deliver` = `ketoan@bvdemo.test`, nhưng cả bản nháp và bản chính thức đều được gửi tới `chuvanhieu357@gmail.com` vì người dùng sửa tay cả hai lần.

Đồng bộ lại **không** gây lệch: nó đưa chứng từ về 01, nên phải gửi nháp lại và khách phải duyệt lại.

### 5.3. Đề xuất (câu hỏi Q3)

- **Tự gửi:** chỉ gửi khi người nhận rõ ràng, tức chưa gửi nháp hoặc `draft_sent_to` trùng `email_deliver` (so theo tập địa chỉ, không phân biệt thứ tự hay hoa/thường). Nếu lệch thì không gửi, ghi comment *"Người nhận bản nháp khác Email nhận hóa đơn, cần gửi tay"*.
- **Sửa tận gốc** (cho trường hợp 1 và 2): khi người nhận trong dialog khác `email_deliver`, hiện thêm ô *"Cập nhật vào Email nhận hóa đơn"*. Chỉ ghi được khi chứng từ còn sửa được (01–04, 98, 99); sau phát hành thì chỉ lưu lần gửi đó.

---

## 6. Tự gửi sau phát hành

### 6.1. Job tải PDF hiện có

`actions.download_pending_official_pdfs` chạy theo cron `* * * * *`. Job **không đếm ngược** cho từng hóa đơn. Mỗi phút nó quét lại và tải PDF cho những hóa đơn thỏa đủ điều kiện sau:

- trạng thái 06–09, chưa có PDF, đã có `fast_key_search`;
- phát hành trong khoảng **từ 24 giờ trước tới 60 giây trước**;
- chưa thử đủ 5 lần, và lần thử trước đã cách ít nhất 120 giây.

Giữa hai hóa đơn job nghỉ 5 giây. Thực tế PDF có sau **khoảng 1–2 phút**. Ví dụ: phát hành lúc 10:00:20 → lượt 10:01 bỏ qua (mới 40 giây) → lượt 10:02 tải.

### 6.2. Luồng đề xuất

Thêm hàm `send_pending_invoices()`, gọi ở **cuối mỗi lượt** của job tải PDF và bọc `try` riêng để lỗi gửi không ảnh hưởng việc tải PDF. Gọi trong cùng lượt nên hóa đơn vừa có PDF được xử lý ngay. Nếu tách thành cron riêng, hai job có thể chạy song song trên hai worker và lệch nhau một phút.

```
Phát hành ──≥60s──► lượt quét: tải PDF + đọc mã tra cứu ──► send_pending_invoices()
                                                               │
                                     chưa có mã CQT? ──► hỏi 8200 cho riêng hóa đơn này
                                       ├─ CQT chấp nhận ──► gửi email ──► 06/08 → 07*, Log, comment
                                       ├─ CQT từ chối  ──► không gửi (đã có cảnh báo từ chối)
                                       └─ còn chờ      ──► lượt sau hỏi lại (tối đa 30 phút)
```

\* Hóa đơn ở 08 vẫn giữ 08, giống quy tắc gửi tay hiện nay.

**Điều kiện chọn hóa đơn:**

- Settings: `enabled`, `auto_send_invoice` đang bật. `suspend_email_queue` tắt. Đang **không** chạy với môi trường TEST (xem mục 10, phát hiện b).
- Trạng thái 06 hoặc 08, đã có `official_pdf` và `fast_lookup_code`.
- `invoice_send_count = 0`: chưa từng gửi, kể cả gửi tay.
- Người nhận rõ ràng (mục 5.3).
- Phát hành trong 24 giờ gần nhất. Bật tính năng lên sẽ không gửi bù hóa đơn cũ.
- Chưa tự gửi lỗi quá 3 lần.

**Thời gian thực tế:** khoảng 1–3 phút sau phát hành nếu CQT cấp mã nhanh. Trên môi trường TEST, CQT cấp mã sau khoảng 6 giây. Quá 30 phút vẫn chưa có mã thì dừng tự gửi và báo `notify_on_error`.

**Chống gửi trùng:** ngay trước khi gửi, đọc lại `invoice_send_count` bằng `SELECT … FOR UPDATE`. Nếu đã khác 0 (vừa có người bấm nút 10) thì bỏ qua.

**Xử lý lỗi:** lỗi dựng hoặc xếp email thì ghi Log trạng thái *Lỗi*. Đến lần thứ 3 thì báo `notify_on_error`, nội dung "bấm Gửi hóa đơn cho khách để gửi tay". Thiếu email người nhận thì chỉ bỏ qua, không tính là lỗi.

**Giới hạn:** `frappe.sendmail` chỉ xếp mail vào hàng đợi. Lỗi giao thực sự (SMTP từ chối, hộp thư đầy) chỉ hiện trong *Email Queue*. Nút 10 hiện cũng vậy, tính năng này không thay đổi điều đó.

---

## 7. Nút Đồng bộ lại từ chứng từ nguồn

### 7.1. Hiện trạng

- Nhãn hiện tại "Đồng bộ lại từ hóa đơn bán", gọi `builder.resync_from_source`. Nút nằm **trong menu xổ "Hóa đơn điện tử"** cùng nhiều nút khác (`button_group` trong `fast_einvoice_document.js`).
- Nút chỉ hiện ở trạng thái 01–04, 98, 99. Bấm xong chỉ có hộp Có/Không, rồi **ghi đè toàn bộ** thông tin chung và dòng hàng. Chứng từ quay về **01 - Nháp** và `revision_count` tăng thêm 1 nếu đang ở 02/03/04.
- Không có cách nào biết trước nguồn đã đổi gì, cũng không biết những gì kế toán sửa tay (email, địa chỉ…) sẽ bị ghi đè.
- Sales Invoice đã submit nên dòng hàng và số tiền ít khi đổi. Thứ hay đổi là **danh mục**: email, địa chỉ, mã số thuế trên Customer, Contact, Address. `_copy_from_source` đọc lại các danh mục này mỗi lần đồng bộ.

### 7.2. Đề xuất

1. **Đưa ra ngoài:** thành một nút riêng trên thanh nút của form, nhãn **"Đồng bộ lại từ chứng từ nguồn"**, không nằm trong menu xổ. Vẫn chỉ hiện ở 01–04, 98, 99. Sau khi phát hành, mọi thay đổi phải đi qua điều chỉnh hoặc thay thế, không đồng bộ được.
2. **Xem trước khi ghi đè:** thêm hàm `preview_resync(fei)`. Hàm dựng dữ liệu từ nguồn trong bộ nhớ, **không lưu**, rồi trả danh sách khác biệt:
   - Thông tin chung: *Trường — Đang có → Từ nguồn* (ví dụ *Email nhận hóa đơn: `chuvanhieu357@gmail.com` → `ketoan@bvdemo.test`*).
   - Dòng hàng: thêm / bớt / đổi số lượng, đơn giá, thuế suất.
   - Bỏ qua `invoice_date`: trường này luôn được đặt về ngày hôm nay, đưa vào chỉ gây nhiễu.
   - Không có khác biệt thì báo *"Dữ liệu đã khớp với chứng từ nguồn"* và không làm gì.
   - Có khác biệt thì hộp thoại ghi rõ *"Đồng bộ sẽ đưa hóa đơn về Nháp, phải gửi nháp lại cho khách"* (khi đang ở 02/03/04), rồi mới cho bấm xác nhận.
3. **Tùy chọn (câu hỏi Q7):**
   - (a) Cho **chọn từng trường** muốn lấy lại, ví dụ chỉ lấy địa chỉ mà giữ email đã sửa tay. Nếu đồng bộ chọn lọc mà chỉ đổi trường liên hệ (email, điện thoại), có thể không cần đưa về Nháp.
   - (b) Khi mở form, nếu nguồn đã khác chứng từ thì hiện dải cảnh báo *"Dữ liệu chứng từ nguồn đã thay đổi — bấm Đồng bộ lại để xem"*.
   - (c) Thêm nút tương tự trên form **Sales Invoice**.

   Đề xuất làm nút ngoài + xem trước + (b). (a) làm sau nếu thực sự cần, vì đồng bộ một phần dễ tạo ra hóa đơn nửa cũ nửa mới.

---

## 8. Cài đặt (Fast EInvoice Settings)

| Trường mới | Kiểu | Nhãn | Mặc định |
|---|---|---|---|
| `auto_send_invoice` | Check | Tự gửi hóa đơn cho khách sau phát hành | 0. Chỉ hiện khi `auto_download_pdf` bật; lưu sẽ báo lỗi nếu bật ô này mà tắt `auto_download_pdf` |
| `lookup_url` | Data | Trang tra cứu hóa đơn (dự phòng) | Trống. Dùng khi không đọc được link trong PDF |
| `invoice_sender_name` | Data | Người phụ trách gửi hóa đơn | Trống |
| `invoice_sender_phone` | Data | Điện thoại đầu mối | Trống |
| `invoice_sender_email` | Data | Email đầu mối (nhận phản hồi) | Trống. Dùng làm `reply_to` |
| `invoice_email_cc` | Data | CC kế toán Miyano | Trống |
| `public_base_url` | Data | Tên miền công khai cho link xem PDF | Trống. Trống thì email không có dòng link L2 |

Trường mới trên **Fast EInvoice Document**: `fast_lookup_code` (Mã tra cứu in trên hóa đơn) và `fast_lookup_url` (Trang tra cứu). Cả hai sửa được khi hệ thống không tự đọc được.

---

## 9. Phạm vi thay đổi

| Tệp | Thay đổi |
|---|---|
| `doctype/fast_einvoice_settings/*.json`, `*.py` | Các trường ở mục 8; kiểm tra ràng buộc khi lưu |
| `doctype/fast_einvoice_document/*.json` | `fast_lookup_code`, `fast_lookup_url` |
| `doctype/fast_einvoice_document/*.js` | Nút Đồng bộ lại ra ngoài và hộp thoại xem trước; ô "Cập nhật vào Email nhận hóa đơn" trong dialog gửi; bump `modified` |
| `actions.py` | `send_pending_invoices()`; đọc mã tra cứu từ PDF đã giải mã ngay khi tải; email dùng biến mới và `reply_to`/CC; bỏ điều kiện bắt buộc XML (có thì đính kèm); `public_pdf_url` dựng từ `public_base_url` |
| patch mới trong `patches.txt` | Điền `fast_lookup_code` / `fast_lookup_url` cho hóa đơn đã có PDF |
| `builder.py` | `preview_resync()` |
| `form_state.py` | Đổi nhãn và nhóm của nút `resync` |
| `tax_status.py` | Tách phần hỏi 8200 một hóa đơn để `send_pending_invoices` gọi lại |
| `setup.py` + patch mới trong `patches.txt` | Mẫu email mới; chỉ thay mẫu khi chưa bị sửa tay |
| `tests/` | Mục 10 |
| `RUNBOOK_HDDT_FAST.md` | Cách bật tự gửi, nhập đầu mối, xử lý khi không đọc được mã |

---

## 10. Kiểm thử, rủi ro và các phát hiện ngoài phạm vi

### 10.1. Kiểm thử

Không gọi mạng; `mailer` và `client` Fast đều là bản giả.

- **Tự gửi:**
  - tắt → không gửi;
  - bật → gửi đúng 1 lần, chạy lại không gửi thêm;
  - 06 → 07; 08 giữ nguyên 08;
  - thiếu PDF / mã tra cứu / email, phát hành quá 24 giờ, đã gửi tay, người nhận lệch, hàng đợi email tạm dừng → không gửi;
  - CQT còn chờ → không gửi, lượt sau hỏi lại; quá 30 phút → cảnh báo;
  - CQT từ chối → không gửi;
  - mailer lỗi 3 lần → cảnh báo, không thử nữa.
- **Đọc PDF:** đọc đúng mã và link từ cả 3 PDF thật (dùng làm fixture); PDF đổi bố cục → trường để trống, có cảnh báo, không tự gửi; patch điền đúng mã cho hóa đơn đã có PDF.
- **XML không bắt buộc:** nút 10 khi chưa có XML → gửi, chỉ kèm PDF; có XML → kèm cả hai file.
- **Mẫu email:** hiện đúng số, ký hiệu `1C26TAA`, mã CQT, mã tra cứu ngắn; ẩn dòng PO và hạn thanh toán khi trống; không còn chuỗi `keySearch` dài.
- **Đồng bộ lại:**
  - nguồn không đổi → báo khớp;
  - đổi email Customer → xem trước thấy đúng một dòng khác biệt;
  - xác nhận → về Nháp; ở 06 → không có nút.
- Chạy lại toàn bộ test của module `erpnext.einvoice`.

### 10.2. Rủi ro

| Rủi ro | Giảm thiểu |
|---|---|
| Khách nhận 2 mail (Fast và ERP) | Chốt Q1 trước khi làm |
| Fast đổi bố cục PDF, không đọc được mã | Không tự gửi, cảnh báo, cho nhập tay; hỏi Fast có API trả mã không (Q5) |
| Trang tra cứu production khác địa chỉ TEST | Đọc từ PDF production, nếu không được thì dùng `lookup_url` trong Settings |
| CQT cấp mã chậm | Hỏi 8200 trước khi gửi; tối đa 30 phút rồi chuyển sang gửi tay |
| Gửi lệch người nhận | Điều kiện người nhận rõ ràng (mục 5.3) |

### 10.3. Phát hiện ngoài phạm vi (cần biết, không sửa trong đợt này trừ khi bạn yêu cầu)

- **a. Link `public_pdf_url` đang hỏng nếu sinh từ job nền.** `get_url()` trả `http://miyano`. Cả 9 chứng từ hiện chưa có giá trị này.
- **b. `is_test_mode = 0` nhưng `api_url` đang trỏ tới portal TEST** (`tportal.fast.com.vn:9000`). Kiểm tra tắt tự gửi theo `is_test_mode` vì thế không bảo vệ được gì. Đề xuất nhận diện môi trường TEST theo `api_url`, hoặc sửa lại `is_test_mode` cho đúng.
- **c. FEI-2026-00006 và FEI-2026-00007 cùng số hóa đơn 6, ký hiệu C26TAA, cùng `issued_time`.** Có thể là dữ liệu thử nghiệm, nhưng cần đối soát với Fast.

---

## 11. Quyết định đã chốt (21/10/2026)

Mục này là kết luận cuối cùng. Chỗ nào ở các mục 1–10 nói khác thì làm theo mục này.

| # | Quyết định | Ảnh hưởng tới thiết kế |
|---|---|---|
| Q1 | **Fast không gửi mail** cho khách khi phát hành | ERP là kênh gửi duy nhất, khách không nhận trùng. Payload giữ nguyên `EmailDeliver` |
| Q2 | **XML để khách tự tra cứu** trên Fast | Email không cần kèm XML. Nút 10 bỏ điều kiện bắt buộc XML, chỉ bắt buộc PDF. Kế toán đã đính `official_xml` thì vẫn kèm theo |
| Q3 | **Người nhận là `email_deliver`**, lấy và đồng bộ từ chứng từ nguồn (Sales Invoice). Hệ thống gửi tới trường này. **CC được nhiều người** | Bỏ điều kiện "người nhận rõ ràng" và ô "Cập nhật vào Email nhận hóa đơn" ở mục 5.3. Tự gửi luôn gửi tới `email_deliver`. Thêm `invoice_email_cc` trong Settings, nhận nhiều địa chỉ cách nhau dấu phẩy, áp dụng cho cả tự gửi và gửi tay. Ô CC trong dialog gửi tay vẫn giữ |
| Q4 | **Bật/tắt tự gửi chỉ bằng ô `auto_send_invoice`** trong Settings | Bỏ hai điều kiện chặn thêm ở mục 6.2: kiểm tra môi trường TEST và kiểm tra hàng đợi email tạm dừng |
| Q5 | **Dùng mã tra cứu đọc từ PDF** | Làm theo mục 4.3: đọc mã và link khi tải PDF, lưu vào `fast_lookup_code` / `fast_lookup_url`. Không cần chờ Fast trả lời |
| Q6 | **Vẫn đính kèm PDF, không gửi link công khai của ERP**. Khách tra cứu trên Fast | Mẫu email bỏ dòng `public_pdf_url`. Bỏ phương án L2 và trường `public_base_url` ở mục 8 |
| Q7 | **Nút Đồng bộ lại chỉ lấy lại dữ liệu, không bị chặn** bởi cảnh báo hay hộp xác nhận. **Chỉ đồng bộ được khi hóa đơn chưa phát hành** | Nút đặt ngoài thanh nút, bấm là chạy, không có hộp xem trước hay xác nhận. Lưu không bị chặn vì thiếu trường bắt buộc; cảnh báo hiện trên form sau khi đồng bộ. Xong thì báo các trường đã thay đổi (chỉ để biết). Nút chỉ hiện ở 01–04 và 99; từ 06 trở đi phải sửa bằng điều chỉnh/thay thế. *Đề xuất, chờ duyệt:* (1) bỏ trạng thái 98 khỏi danh sách được đồng bộ, vì ở 98 chưa biết Fast đã ra số hay chưa — phải bấm Lấy dữ liệu từ Fast (370) trước; (2) chỉ đưa hóa đơn về Nháp khi dữ liệu thực sự thay đổi, không đổi gì thì giữ nguyên trạng thái |
| Q8 | **Đồng ý** thêm trường đầu mối (tên, điện thoại, email) và CC vào Settings | Như mục 8 |
| Q9 | **In nguyên số Fast trả về** (ví dụ `4`) | Không đệm số 0 |

---

## 12. Các bước triển khai

1. Mục 11 đã chốt toàn bộ — bắt đầu Đợt 1. Đợt 2 làm theo Q7 (không có hộp xem trước). Đợt 3 làm theo Q1, Q3, Q4.
2. **Đợt 1 — sửa nội dung email** (dùng được ngay cho gửi tay): đọc mã tra cứu từ PDF, mẫu email mới, trường Settings đầu mối/CC. Khoảng 1 ngày.
3. **Đợt 2 — nút Đồng bộ lại**: đưa ra ngoài, hộp thoại xem trước, dải cảnh báo. Khoảng 0,5–1 ngày.
4. **Đợt 3 — tự gửi**: `send_pending_invoices`, hỏi 8200, chống trùng, cảnh báo. Khoảng 1 ngày.
5. Mỗi đợt: viết test trước, chạy `bench --site miyano migrate`, cập nhật runbook.
6. Bật tự gửi trên production và theo dõi hóa đơn thật đầu tiên: mã tra cứu đọc đúng chưa, link mở được không, khách nhận đúng 1 mail không.

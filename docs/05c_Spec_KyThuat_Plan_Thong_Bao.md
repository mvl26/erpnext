# SPEC KỸ THUẬT & PLAN – TÍNH NĂNG THÔNG BÁO CHUỖI CUNG ỨNG
## Kênh Email + In-app (có tiếng) · Miyano ERP (ERPNext v15) · site `miyano`

*Phiên bản 2 · 08/09/2026 · Đã loại bỏ SMS · Đã khảo sát hệ thống thật · Mọi quyết định D1–D9 đã chốt*

> **Cách dùng tài liệu.** Đây là tài liệu **đủ để build một mạch**: mọi điểm còn treo ở bản trước đã được kiểm chứng trên site `miyano` và chốt lại. Spec ràng buộc *kết quả* (điều kiện bắn, người nhận, nội dung, tiêu chí đạt) và **chốt luôn khung hiện thực** (module, DocType, tên trường, điều kiện lọc) để không phải đoán giữa chừng. Chi tiết viết code (tên hàm, cách tách file nhỏ) do người build quyết.
>
> Tài liệu nguồn: `docs/05_Spec_Thong_Bao_Chuoi_Cung_Ung_V3.docx` (v2.1, 28/08/2026). Đối chiếu đầy đủ + các sai khác có chủ ý: **Phụ lục D**.

---

## 0. Tóm tắt cho người build

| Hạng mục | Chốt |
|---|---|
| Nơi đặt code | Module mới **`Supply Notification`** trong app `erpnext` (folder `erpnext/supply_notification/`), theo tiền lệ module `Einvoice`, `TBYT` |
| Kênh | Email (Email Account mặc định đang chạy) + In-app (Notification Log type `Alert`) có âm báo |
| Điểm thông báo | 12 (10 theo Submit + 2 nhắc hạn hằng ngày) |
| Người nhận nội bộ | Cấu hình theo **Phòng ban** và/hoặc **Người cụ thể** (+ cờ gửi người tạo). **Không dùng Role** |
| Nguồn phòng ban (D1) | **Employee** (`Employee.department` + `Employee.user_id`, `status = Active`) |
| Người nhận ngoài | Email trên chứng từ / liên hệ chính của Supplier–Customer |
| PDF đính kèm (D4) | **Chỉ NTF-07** đính `Phiếu xuất kho (02-VT)`. NTF-03 và NTF-11 gửi email chữ, không kèm file |
| Câu chữ email | Tiêu đề + câu mở đầu + câu "việc cần làm" **sửa được trong cấu hình**; bảng/bố cục/định dạng do code |
| Chặn build | 4 việc ở §3.2 phải làm xong trước khi nghiệm thu (scheduler đang **tắt**, chưa có Contact NCC) |

---

## 1. Mục tiêu & phạm vi

### 1.1. Mục tiêu
Tự động thông báo cho đúng người khi chứng từ chuỗi cung ứng chuyển **Ghi sổ (Submit)**, và nhắc hạn thanh toán/thu tiền. Hai kênh: **email** và **in-app** (chuông desk Frappe, **có âm thanh** + toast). Thông báo là định tuyến thông tin, không thay phê duyệt.

### 1.2. Trong phạm vi
12 điểm thông báo dọc chuỗi (10 theo Submit + 2 nhắc hạn); email nội bộ + email ra NCC/khách; in-app có tiếng cho nội bộ; **cơ chế cấu hình người nhận** do nghiệp vụ tự quản; nhật ký gửi để kiểm chứng và chống gửi trùng.

### 1.3. Ngoài phạm vi
SMS (F-038 của bản V3 — bỏ hẳn khỏi đợt này), Zalo/Telegram, portal in-app cho NCC/khách, workflow phê duyệt, tự động giao việc ToDo (F-035), nhúng bảng tồn kho vào email (F-036), cảnh báo tồn dưới min và lô cận hạn (F-017/F-018).

### 1.4. Tiền đề — **đã kiểm chứng ngày 08/09/2026**
| # | Tiền đề | Thực tế trên site `miyano` | Kết luận |
|---|---|---|---|
| 1 | Email Account gửi đi hoạt động | 1 tài khoản `AssetCore Notifications`, `default_outgoing = 1`, `enable_outgoing = 1` | ✅ Dùng lại, không cấu hình lại |
| 2 | Scheduler đang bật | **Scheduler disabled** (workers online: 2) | ❌ **Phải bật** — xem §3.2-a |
| 3 | Realtime (socket.io) hoạt động | Không kiểm được bằng dòng lệnh | ⚠️ Kiểm bằng tay ở Tuần 1 |
| 4 | Xác định được phòng ban của nhân viên | `hrms` đã cài; 6/6 nhân viên có `department`, **chỉ 1/6 có `user_id`** | ⚠️ Cơ chế chạy được, dữ liệu phải bù — §3.2-b |

---

## 2. Nguyên tắc thiết kế

1. **Người nhận là cấu hình, không phải code.** Ai nhận gì khai báo trong dữ liệu; nghiệp vụ sửa qua giao diện; không sửa mã, không đụng phân quyền.
2. **Tách người nhận khỏi Role.** Không "gửi theo Role" (Role là quyền hệ thống, gán nhiều người/nhiều phòng, dễ sai). Thay bằng chọn **Phòng ban** và/hoặc **Người cụ thể**.
3. **Chỉ bắn khi Submit.** Không thông báo từ Draft. Thông báo ra ngoài chỉ gắn chứng từ đã ghi sổ.
4. **Không chặn nghiệp vụ.** Lỗi gửi thông báo không được làm hỏng/chặn Submit chứng từ — toàn bộ việc gửi chạy **nền, sau commit**.
5. **Gửi một lần.** Mỗi (điểm thông báo × chứng từ × mốc) chỉ gửi một lần, kể cả khi job chạy lại.
6. **Nội dung tiếng Việt, định dạng thân thiện.** Tên người là họ tên; tiền có phân tách + đơn vị; ngày theo định dạng hệ thống.
7. **Nhân rộng được.** Cấu hình đóng gói lại được cho site khác; hàm cài đặt chạy lại nhiều lần không nhân đôi dữ liệu.

---

## 3. Kết quả khảo sát hệ thống & việc phải làm trước

### 3.1. Những gì đã có sẵn (dùng lại, không build)
| Hạ tầng | Chi tiết đã kiểm chứng |
|---|---|
| Gửi mail | `frappe.sendmail(...)` → Email Queue → scheduler đẩy đi |
| In-app | DocType `Notification Log`; tạo bản ghi `type = "Alert"` → tự `publish_realtime("notification", user=…)` cập nhật chuông |
| Không gửi mail trùng | `Notification Log` với `type = "Alert"` **không** tự sinh email (`is_email_notifications_enabled_for_type` trả `False` cho `Alert`) → email của ta là email duy nhất |
| Tắt in-app theo người | `Notification Settings.enabled` — Frappe tự lọc người đã tắt khi tạo Notification Log |
| Tắt tiếng theo người | `User.mute_sounds` (nhãn *Mute Sounds*); `frappe.utils.play_sound()` đã tự tôn trọng cờ này |
| Âm báo sẵn có | `frappe/public/sounds/`: `alert.mp3`, `chime.mp3`, `email.mp3`, … |
| Định dạng VN | Ngôn ngữ `vi`, ngày `dd-mm-yyyy`, số `#.###,##`, tiền tệ `VND`, công ty `Miyano` (viết tắt `M`) |
| Mẫu in TV | Phiếu giao hàng: **`Phiếu xuất kho (02-VT)`** (đang bật) |
| Chỗ nhúng JS | `erpnext/public/js/erpnext.bundle.js` (khai qua `app_include_js` trong `hooks.py`) |

### 3.2. Việc phải làm — chặn nghiệm thu nếu bỏ qua

**a) Bật scheduler — chặn NTF-06/08 và toàn bộ email.**
Không có scheduler thì mail nằm lì trong Email Queue và job nhắc hạn không chạy.
```bash
cd /home/miyano/frappe-bench && bench --site miyano enable-scheduler
bench --site miyano doctor            # phải thấy "Scheduler enabled/active"
```

**b) Gắn `user_id` cho nhân viên (chặn mọi thông báo theo phòng ban).**
Hiện chỉ `HR-EMP-00001` có `user_id`. Nhân viên không gắn tài khoản → **không nhận được gì**, và cơ chế xem trước sẽ cảnh báo. Việc của Miyano (D3).

**c) Chuẩn hoá phòng ban.** Đang có `Kế toán - M`, `Kinh doanh - M`, `Kỹ thuật - M`, `Sản xuất - M`, `Ban Giám đốc - M`, `Hành chính - Nhân sự - M` + bộ mặc định tiếng Anh. **Thiếu `Kho` và `Mua hàng`.**
Hàm cài đặt tạo bù hai phòng này (idempotent); ánh xạ chốt:

| Vai trò nghiệp vụ | Department dùng |
|---|---|
| Phòng Kho | `Kho - M` *(tạo mới)* |
| Phòng Mua hàng | `Mua hàng - M` *(tạo mới)* |
| Phòng Bán hàng | `Kinh doanh - M` *(đã có)* |
| Phòng Kế toán | `Kế toán - M` *(đã có)* |

**d) Bổ sung liên hệ NCC/khách (chặn NTF-03/07/10/11/12 phần gửi ra ngoài).**
Khảo sát: **0 Contact nào đang gắn với Supplier** (9 NCC, 2 khách hàng). Chưa bù thì phần email ra ngoài im lặng bỏ qua (đúng thiết kế, không lỗi chứng từ — TC9), nhưng **không nghiệm thu được**.

---

## 4. Quyết định đã chốt

| Mã | Nội dung | **Chốt** |
|---|---|---|
| D1 | Nguồn "phòng ban của người dùng" | **Phương án A — qua hồ sơ Nhân viên.** `Employee.department` + `Employee.user_id`, lọc `status = "Active"`. Code phải chịu được trường hợp DocType `Employee` không tồn tại (site không cài `hrms`) → trả danh sách rỗng, ghi log, không nổ |
| D2 | Ai được sửa cấu hình người nhận | Role mới **`Quản trị thông báo`**, tách khỏi mọi quyền nghiệp vụ. Chỉ role này (và System Manager) có quyền sửa DocType cấu hình |
| D3 | Danh sách phòng ban chuẩn + ánh xạ nhân sự | Theo bảng §3.2-c. Hàm cài đặt tạo bù `Kho - M`, `Mua hàng - M`; gán nhân viên là việc của Miyano |
| D4 | Mẫu in đính PDF | **Chỉ NTF-07** đính `Phiếu xuất kho (02-VT)`. **NTF-03 và NTF-11 không đính PDF** (chưa có mẫu tiếng Việt cho Đơn mua hàng / Yêu cầu thanh toán); email chữ vẫn nêu đủ số chứng từ, giá trị, ngày |
| D5 | Thông tin liên hệ Miyano trong email ngoài | Một khối chữ ký cố định, khai trong cấu hình từng điểm (trường `external_closing`), mặc định seed để trống → Miyano điền hotline ở Tuần 1 |
| D6 | Âm báo | Dùng âm hệ thống sẵn có, mặc định **`alert`**; đổi được bằng hằng số trong code |
| D7 *(mới)* | Câu chữ email do ai sửa | Tiêu đề + câu mở đầu + câu "việc cần làm" (nội bộ và ngoài) nằm trong bản ghi cấu hình, nghiệp vụ tự sửa. Bảng mặt hàng, định dạng tiền/ngày, bố cục HTML do code dựng |
| D8 *(mới)* | Có thông báo khi Ghi sổ Hoá đơn bán (Sales Invoice) không | **Không.** Bản V3 gộp bước 10 thành "Submit SI và nhắc hạn thu tiền" nhưng bảng cấu hình chỉ định nghĩa NTF-08 là *nhắc hạn*. Giữ nguyên: SI chỉ có nhắc hạn, không bắn khi Submit |
| D9 *(mới)* | "Hạn" trong NTF-11 lấy ở đâu | DocType `Payment Request` **không có** trường hạn thanh toán. Lấy `due_date` của chứng từ gốc (`reference_doctype`/`reference_name` → thường là Sales Invoice); không có thì **bỏ đoạn hạn khỏi tiêu đề và thân bài** |

---

## 5. Mô hình dữ liệu cấu hình

Bốn DocType mới, đặt trong `erpnext/supply_notification/doctype/`.

### 5.1. `Supply Notification Point` — điểm thông báo (bản ghi chính)
Đặt tên theo mã (`NTF-01`…`NTF-12`), `autoname: field:code`.

| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `code` | Data, bắt buộc, duy nhất | `NTF-01`… |
| `title` | Data, bắt buộc | "Đơn bán hàng · Ghi sổ" |
| `enabled` | Check, mặc định 1 | Bật/tắt riêng điểm này |
| `reference_doctype` | Link DocType, chỉ đọc | Chứng từ nguồn |
| `trigger_event` | Select: `Submit` / `Due Reminder`, chỉ đọc | Cách kích hoạt |
| `filter_note` | Small Text, chỉ đọc | Mô tả điều kiện lọc cho người dùng đọc (điều kiện thật nằm trong code, xem §7) |
| `send_email` | Check, mặc định 1 | Bật kênh email nội bộ |
| `send_inapp` | Check, mặc định 1 | Bật kênh in-app |
| `notify_owner` | Check | Gửi thêm cho người tạo chứng từ |
| `notify_external` | Check | Gửi email ra NCC/khách |
| `attach_pdf` | Check | Đính PDF chứng từ vào email ra ngoài |
| `print_format` | Link Print Format, hiện khi `attach_pdf` | Mẫu in dùng để tạo PDF |
| `departments` | Table `Supply Notification Department` | Danh sách phòng ban nhận |
| `users` | Table `Supply Notification User` | Danh sách người nhận đích danh |
| `subject_template` | Data, bắt buộc | Tiêu đề email nội bộ (Jinja, xem §8.4) |
| `intro_template` | Small Text | Câu nêu sự việc (nội bộ) |
| `action_template` | Small Text | Câu "việc cần làm tiếp" (nội bộ) |
| `external_subject_template` | Data | Tiêu đề email ra ngoài |
| `external_intro_template` | Small Text | Câu mở đầu email ra ngoài |
| `external_closing` | Small Text | Chữ ký / thông tin liên hệ Miyano (D5) |
| `notes` | Small Text | Ghi chú nội bộ |

Nút trên form: **"Xem trước người nhận"** → gọi phương thức whitelisted, hiện hộp thoại liệt kê người nhận thực tế cùng cảnh báo (§6.3).

### 5.2. `Supply Notification Department` (child) — `department`: Link Department, bắt buộc
### 5.3. `Supply Notification User` (child) — `user`: Link User, bắt buộc
### 5.4. `Supply Notification Dispatch Log` — nhật ký gửi

Phục vụ hai việc: **chống gửi trùng** và **kiểm chứng khi nghiệm thu**.

| Trường | Kiểu |
|---|---|
| `point` | Link Supply Notification Point |
| `reference_doctype`, `reference_name` | Data / Dynamic Link |
| `milestone` | Data — `submit`, `d7`, `d3`, `d1` |
| `sent_on` | Datetime |
| `channel_email`, `channel_inapp`, `channel_external` | Check |
| `recipients` | Small Text — danh sách email nội bộ đã gửi |
| `external_recipients` | Small Text |
| `status` | Select: `Sent` / `Skipped` / `Failed` |
| `remark` | Small Text — lý do bỏ qua / lỗi |

Khoá chống trùng: bộ ba (`point`, `reference_name`, `milestone`) — kiểm tra trước khi gửi. Chỉ đọc với mọi người trừ System Manager; xoá bản ghi cũ hơn 180 ngày bằng job dọn dẹp hằng ngày.

---

## 6. Cơ chế người nhận

### 6.1. Diễn giải phòng ban → người (D1 = A)
1. Với mỗi Department trong cấu hình: nếu là **nhóm** (`is_group = 1`) thì lấy cả **cây con** (`Department` là DocType dạng cây, duyệt theo `lft`/`rgt`), không chỉ đúng nút đó. Bỏ phòng ban `disabled = 1`.
2. Lấy `Employee` có `department` thuộc tập trên, `status = "Active"`, `user_id` khác rỗng → tập user.
3. Cộng thêm danh sách `users` khai đích danh.
4. Cộng thêm `doc.owner` nếu `notify_owner = 1`.
5. Loại user `enabled = 0`, loại user không có email hợp lệ, loại `Administrator` và `Guest`.
6. **Khử trùng** → danh sách cuối.

Cùng một người là người nhận của nhiều điểm là bình thường; trong **một** lần bắn, một người chỉ nhận **một** email và **một** thông báo in-app.

### 6.2. Người nhận ngoài (NCC/khách)
Một hàm dùng chung, thứ tự ưu tiên:
1. `doc.contact_email` trên chứng từ (PO, DN, PE) hoặc `doc.email_to` (Payment Request);
2. nếu trống → email của **Contact chính** (`Is Primary Contact`) gắn với Supplier/Customer qua `Dynamic Link`;
3. nếu trống → email trên bản ghi Supplier/Customer;
4. vẫn trống → **bỏ qua phần gửi ngoài**, ghi Dispatch Log `status = Skipped`, `remark` nêu rõ; nội bộ vẫn gửi bình thường; chứng từ **không** báo lỗi.

Email ra ngoài gửi **riêng** (không chung `recipients` với nội bộ) để không lộ địa chỉ nội bộ và để dùng nội dung/chữ ký khác.

### 6.3. Xem trước người nhận
Trả về, cho một điểm thông báo:
- danh sách người nhận cuối cùng (họ tên + email + nguồn: *phòng ban X* / *đích danh* / *người tạo*);
- **cảnh báo**: phòng ban được chọn nhưng không có nhân viên nào gắn tài khoản; nhân viên Active thuộc phòng nhưng thiếu `user_id`; user bị khoá hoặc thiếu email; điểm đang tắt; cả hai kênh đều tắt.

---

## 7. 12 điểm thông báo — bảng kỹ thuật đầy đủ

Tên trường dưới đây **đã đối chiếu với DocType JSON của bản v15 trong repo này** (xem Phụ lục B).

| Mã | Chứng từ · Sự kiện | Điều kiện bắn (biểu thức) | Phòng ban mặc định | +Người tạo | Ngoài | PDF |
|---|---|---|---|---|---|---|
| NTF-01 | `Sales Order` · on_submit | mọi đơn | Kho | ✅ | – | – |
| NTF-02 | `Material Request` · on_submit | `material_request_type == "Purchase"` | Mua hàng | – | – | – |
| NTF-03 | `Purchase Order` · on_submit | mọi đơn | Kho | – | NCC | ❌ (D4) |
| NTF-04 | `Purchase Receipt` · on_submit | mọi phiếu | Mua hàng + Kế toán | – | – | – |
| NTF-05 | `Purchase Invoice` · on_submit | mọi hoá đơn | Kế toán | – | – | – |
| NTF-06 | `Purchase Invoice` · job hằng ngày | `docstatus == 1` và `outstanding_amount > 0` và `due_date == today + {7,3,1}` | Kế toán + Mua hàng | – | – | – |
| NTF-07 | `Delivery Note` · on_submit | mọi phiếu | Bán hàng | – | Khách | ✅ `Phiếu xuất kho (02-VT)` |
| NTF-08 | `Sales Invoice` · job hằng ngày | `docstatus == 1` và `outstanding_amount > 0` và `due_date == today + {7,3,1}` | Kế toán | – | – | – |
| NTF-09 | `Payment Request` · on_submit | `payment_request_type == "Outward"` | Kế toán | – | – | – |
| NTF-10 | `Payment Entry` · on_submit | `payment_type == "Pay"` | Mua hàng + Kế toán | – | NCC | – |
| NTF-11 | `Payment Request` · on_submit | `payment_request_type == "Inward"` | Bán hàng + Kế toán | – | Khách | ❌ (D4) |
| NTF-12 | `Payment Entry` · on_submit | `payment_type == "Receive"` | Bán hàng + Kế toán | – | Khách | – |

**Bẫy phải tránh (kiểm bằng kịch bản âm):**
- `Material Request` loại `Material Transfer` / `Material Issue` / `Manufacture` / `Customer Provided` → **không** bắn NTF-02.
- `Payment Entry` loại `Internal Transfer` → **không** bắn NTF-10 lẫn NTF-12.
- Hoá đơn `outstanding_amount = 0` → **không** nhắc hạn.
- Chứng từ do Amend sinh ra: xử lý như chứng từ mới (bắn bình thường) — bản gốc đã Cancel không bắn lại.
- Điểm bị tắt (`enabled = 0`) hoặc cả hai kênh tắt → bỏ qua, ghi Dispatch Log `Skipped`.

**Cách nối vào hệ thống:** một hàm xử lý duy nhất khai trong `hooks.py → doc_events` cho 8 DocType ở cột 2 với sự kiện `on_submit`; hàm này tra bảng ánh xạ (DocType, điều kiện) → mã điểm, rồi `frappe.enqueue(..., enqueue_after_commit=True)`. **Toàn bộ việc dựng nội dung và gửi chạy trong job nền** — Submit không bao giờ chờ, không bao giờ hỏng vì thông báo.

---

## 8. Nội dung & định dạng

### 8.1. Email nội bộ
1. Câu nêu sự việc (`intro_template`);
2. Bảng chi tiết khi có ý nghĩa — mặt hàng (mã / tên / SL / ĐVT) với chứng từ có `items`, hoặc khối số tiền + hạn với chứng từ tiền;
3. Liên kết mở chứng từ; **riêng NTF-01 thêm liên kết** báo cáo tồn kho `/app/query-report/Stock Balance`;
4. Câu chỉ rõ việc cần làm tiếp (`action_template`).

### 8.2. Email ra ngoài (NCC/khách)
Xưng hô trang trọng, giọng đối ngoại; **không** chứa bất kỳ liên kết nội bộ nào; kết bằng `external_closing` (thông tin liên hệ Miyano); đính PDF chỉ ở NTF-07.

### 8.3. In-app
Tiêu đề ngắn, cùng ý với chủ đề email; bấm mở đúng chứng từ (`Notification Log.document_type` + `document_name`).

### 8.4. Định dạng dữ liệu (bắt buộc, đã khớp cấu hình site)
| Loại | Cách dựng |
|---|---|
| Tên người | Họ tên (`User.full_name`), **không bao giờ** hiện email làm tên người |
| Số tiền | `frappe.utils.fmt_money(giá_trị, currency=doc.currency)` → `1.234.567,00 ₫` theo định dạng `#.###,##` |
| Ngày | `frappe.utils.formatdate(giá_trị)` → `dd-mm-yyyy` |
| Chủ đề | Tiền tố `[SupplyCore]` + loại chứng từ + số + đối tác + mốc thời gian/số tiền khi phù hợp |

### 8.5. Ranh giới giữa cấu hình và code (D7)
Chỉ 6 trường chữ trong cấu hình được render bằng Jinja, với **ngữ cảnh hạn chế**: `doc`, `party_name`, `owner_name`, `amount`, `outstanding`, `due`, `doc_url`. Người dùng không truy cập được `frappe`, không gọi được hàm tuỳ ý. Render lỗi → dùng bản mặc định seed, ghi Error Log, **vẫn gửi**.

Mẫu chủ đề & trọng tâm thân bài của 12 điểm: **Phụ lục A** (giá trị seed ban đầu).

---

## 9. Kênh in-app có tiếng

### 9.1. Hành vi
- Thông báo mới → chuông cập nhật ngay + **phát âm báo** + hiện toast góc màn hình; bấm toast mở đúng chứng từ.
- Xuất hiện **không cần tải lại trang**.
- Nhiều thông báo dồn gần như cùng lúc → chỉ phát âm **một lần trong 3 giây** (chống dội); toast vẫn hiện đủ.
- Người dùng tự tắt tiếng qua `User → Mute Sounds`; hệ thống tôn trọng (đã có sẵn trong `frappe.utils.play_sound`).
- Người dùng tắt in-app qua `Notification Settings → enabled`; Frappe tự loại khỏi danh sách.
- Chỉ áp dụng người dùng nội bộ trên desk; không áp dụng tài khoản portal.

### 9.2. Cách hiện thực
Sự kiện realtime sẵn có `"notification"` của Frappe **không mang dữ liệu**, chỉ đủ để cập nhật chuông. Vì vậy, sau khi tạo Notification Log, phát thêm một sự kiện riêng của Miyano kèm `{subject, doctype, docname, url}` tới đúng user; file JS lắng nghe sự kiện đó → `frappe.utils.play_sound("alert")` + `frappe.show_alert({message, indicator}, 10)` có liên kết mở chứng từ.

File JS đặt tại `erpnext/public/js/utils/`, thêm một dòng `import` vào `erpnext/public/js/erpnext.bundle.js`; sau đó `bench build --app erpnext`.

### 9.3. Ràng buộc ghi vào hướng dẫn sử dụng
Trình duyệt chỉ cho phát âm sau khi người dùng đã tương tác với trang ít nhất một lần trong phiên; ngay sau khi mở tab mới mà chưa thao tác, âm có thể bị chặn dù toast vẫn hiện — là giới hạn trình duyệt, không phải lỗi.

---

## 10. Nhắc hạn (NTF-06, NTF-08)

- Chạy bằng scheduler, **cron 08:00 hằng ngày** (khai trong `hooks.py → scheduler_events`).
- Với mỗi mốc `N ∈ {7, 3, 1}`: tìm `Purchase Invoice` (NTF-06) / `Sales Invoice` (NTF-08) có `docstatus = 1`, `outstanding_amount > 0`, `due_date = today + N ngày`.
- Trước khi gửi, kiểm Dispatch Log theo (điểm, chứng từ, `milestone = d{N}`) — đã có thì bỏ qua. Nhờ vậy job chạy lại, hoặc chạy bù sau khi bật scheduler, **không gửi trùng**.
- Hoá đơn đã tất toán giữa chừng (`outstanding_amount` về 0) → mốc sau không nhắc nữa.
- Job phải bọc `try/except` từng hoá đơn: một hoá đơn lỗi không được làm chết cả lượt quét.
- Không chạy bù ngược quá khứ: bật scheduler muộn thì các mốc đã trôi qua coi như bỏ.

---

## 11. Ràng buộc kỹ thuật & xử lý ngoại lệ

| Tình huống | Yêu cầu xử lý |
|---|---|
| Email gửi lỗi | Không chặn Submit; ghi Error Log + Dispatch Log `Failed`; in-app vẫn chạy độc lập |
| NCC/khách thiếu email | Bỏ qua người nhận ngoài, vẫn gửi nội bộ; ghi `Skipped` kèm lý do; không lỗi chứng từ |
| Realtime không hoạt động | Thông báo vẫn ghi nhận vào Notification Log; hiện khi tải lại trang; ưu tiên khắc phục hạ tầng |
| Người nhận trùng | Chỉ nhận **một** email, một thông báo |
| Tắt một điểm thông báo | Ngừng riêng điểm đó, không ảnh hưởng điểm khác |
| Đổi người phụ trách / đổi phòng ban | Thông báo tự chuyển theo dữ liệu nhân sự, không sửa từng điểm |
| Scheduler không chạy | Email đọng trong Email Queue, nhắc hạn không bắn — giám sát scheduler, nêu trong checklist vận hành |
| `hrms` không cài trên site khác | Diễn giải phòng ban trả rỗng + ghi log; cấu hình theo **người đích danh** vẫn chạy |
| Job nền không có worker | Thông báo không gửi được nhưng chứng từ vẫn Submit bình thường |
| Cấu hình `Payment Gateway` cho Payment Request (tương lai) | ERPNext sẽ tự gửi thêm email của nó → khi đó cân nhắc tắt `notify_external` của NTF-11 để tránh khách nhận hai thư |

Kiểm soát: thông báo không thay phê duyệt; chứng từ vẫn theo vòng đời Draft → Submit → Cancel/Amend. Nội dung ra ngoài không chứa thông tin nhạy cảm ngoài số chứng từ, số tiền, ngày.

---

## 12. Thứ tự build (chạy một mạch)

Mỗi bước tự kiểm được; làm đúng thứ tự thì không phải quay lại.

| # | Việc | Đầu ra kiểm được |
|---|---|---|
| 1 | Bật scheduler (§3.2-a) | `bench --site miyano doctor` báo scheduler active |
| 2 | Khai module `Supply Notification` vào `erpnext/modules.txt` + patch tạo `Module Def` (theo mẫu `add_tbyt_module_def.py`) | `bench --site miyano migrate` chạy sạch |
| 3 | Dựng 4 DocType ở §5 (+ quyền cho role `Quản trị thông báo`) | Mở được form, tạo tay được một bản ghi |
| 4 | `resolver.py` — diễn giải phòng ban → người, khử trùng, lọc | Test đơn vị: cây phòng ban, nhân viên thiếu `user_id`, user bị khoá, trùng lặp |
| 5 | Phương thức + nút **Xem trước người nhận** | Bấm ra đúng danh sách + cảnh báo |
| 6 | `setup.py` idempotent: tạo role, tạo `Kho - M`/`Mua hàng - M` nếu thiếu, seed 12 điểm (Phụ lục C) | Chạy hai lần không nhân đôi bản ghi |
| 7 | `content.py` — dựng chủ đề/thân bài, định dạng tiền–ngày–tên, bảng mặt hàng, template nội bộ + ngoài | Test: render đủ 12 điểm không lỗi; số tiền ra `#.###,##`; ngày ra `dd-mm-yyyy` |
| 8 | `dispatch.py` — gửi email, tạo Notification Log `Alert`, phát realtime, ghi Dispatch Log, chống trùng | Test: gọi hai lần chỉ gửi một |
| 9 | `events.py` + khai `doc_events` cho 8 DocType, chạy nền sau commit | Submit thử từng loại chứng từ → đúng điểm bắn, sai loại không bắn |
| 10 | JS toast + âm báo, thêm `import` vào bundle, `bench build --app erpnext` | Submit ở tab khác → chuông kêu + toast, bấm mở đúng chứng từ |
| 11 | `reminders.py` + `scheduler_events` cron 08:00 | Test giả lập ngày: đúng ba mốc 7/3/1, tất toán thì thôi |
| 12 | Patch seed + thêm dòng vào `erpnext/patches.txt` | `bench --site miyano migrate` trên site sạch ra đủ 12 điểm |
| 13 | Bộ test trong `erpnext/supply_notification/tests/` | `bench --site miyano run-tests --module erpnext.supply_notification.tests.…` xanh |
| 14 | Chạy kiểm thử §13 trên staging | Bảng TC đạt |

**Bản đồ file** (đã đối chiếu `scripts/file_structure/gate.py`, mọi đường dẫn đều hợp lệ):
```
erpnext/modules.txt                                       (+1 dòng)
erpnext/hooks.py                                          (doc_events, scheduler_events)
erpnext/patches.txt                                       (+2 dòng)
erpnext/supply_notification/__init__.py
erpnext/supply_notification/constants.py
erpnext/supply_notification/resolver.py
erpnext/supply_notification/content.py
erpnext/supply_notification/dispatch.py
erpnext/supply_notification/events.py
erpnext/supply_notification/reminders.py
erpnext/supply_notification/setup.py
erpnext/supply_notification/doctype/supply_notification_point/…
erpnext/supply_notification/doctype/supply_notification_department/…
erpnext/supply_notification/doctype/supply_notification_user/…
erpnext/supply_notification/doctype/supply_notification_dispatch_log/…
erpnext/supply_notification/templates/internal_email.html
erpnext/supply_notification/templates/external_email.html
erpnext/supply_notification/tests/__init__.py
erpnext/supply_notification/tests/test_resolver.py
erpnext/supply_notification/tests/test_content.py
erpnext/supply_notification/tests/test_dispatch.py
erpnext/supply_notification/tests/test_reminders.py
erpnext/public/js/utils/supply_notification_toast.js
erpnext/public/js/erpnext.bundle.js                       (+1 dòng import)
erpnext/patches/v15_0/add_supply_notification_module_def.py
erpnext/patches/v15_0/seed_supply_notification_points.py
```

**Quy ước code của repo:** Python thụt bằng **TAB**, dài tối đa 110, chuỗi nháy kép; chú thích và nhãn giao diện bằng tiếng Việt (theo tiền lệ `erpnext/einvoice/`, `erpnext/tbyt/`).

### Ước lượng công
Dev ~6–7 ngày, BA ~3 ngày (câu chữ, kiểm thử, hướng dẫn), Admin ~2,5 ngày (phòng ban, `user_id`, liên hệ NCC/khách). Tổng ~12 ngày, trải 4 tuần.

---

## 13. Kiểm thử & tiêu chí nghiệm thu

| TC | Kịch bản | Kết quả mong đợi |
|---|---|---|
| TC1 | Ghi sổ Đơn bán hàng | Người thuộc phòng Kho + người tạo nhận email ~2 phút + chuông kêu + toast; ai trùng chỉ nhận một; email có bảng mặt hàng, link đơn và link báo cáo tồn |
| TC2 | Ghi sổ Yêu cầu vật tư loại Mua hàng / loại khác | Mua hàng → NTF-02; `Material Transfer`, `Material Issue` → không bắn |
| TC3 | Ghi sổ Đơn mua, NCC có email | Nội bộ nhận; NCC nhận email (không đính PDF, theo D4), không vào spam |
| TC4 | Ghi sổ Phiếu nhập / Hoá đơn mua | Đúng người nhận theo cấu hình |
| TC5 | Ghi sổ Yêu cầu thanh toán loại `Outward` / `Inward` | Outward → NTF-09 nội bộ; Inward → NTF-11 nội bộ + khách nhận email |
| TC6 | Ghi sổ phiếu chi / phiếu thu / chuyển nội bộ | `Pay` → NTF-10 + NCC; `Receive` → NTF-12 + khách; `Internal Transfer` → không bắn |
| TC7 | Ghi sổ Phiếu giao hàng | Nội bộ + khách nhận email **kèm PDF `Phiếu xuất kho (02-VT)`** |
| TC8 | Hoá đơn mua/bán đến hạn 7/3/1 ngày (giả lập ngày) | Nhận đúng ba mốc; hoá đơn tất toán không nhắc |
| TC8b | Chạy lại job nhắc hạn trong cùng ngày | **Không** gửi trùng (Dispatch Log chặn) |
| TC-R1 | Thêm một người vào một điểm qua cấu hình | Nhận từ lần Ghi sổ kế tiếp, không sửa mã/phân quyền |
| TC-R2 | Đổi phòng ban của một nhân viên | Tự thôi nhận thông báo phòng cũ, bắt đầu nhận phòng mới |
| TC-R3 | Xem trước người nhận của một điểm | Đúng danh sách thực tế; cảnh báo khi phòng có nhân viên thiếu `user_id` |
| TC-R4 | Tắt một điểm thông báo | Điểm đó ngừng gửi; điểm khác không ảnh hưởng |
| TC-R5 | Người không có role `Quản trị thông báo` mở cấu hình | Không sửa được |
| TC9 | NCC thiếu email liên hệ | Nội bộ vẫn nhận; Dispatch Log ghi `Skipped` + lý do; chứng từ ghi sổ bình thường |
| TC10 | Bật `Mute Sounds` / tắt `Notification Settings.enabled` rồi bật lại | Tắt tiếng: toast hiện, không kêu; tắt in-app: không nhận, bật lại nhận bình thường |
| TC11 | Hệ thống mail tạm lỗi (sai cấu hình SMTP) | Ghi Error Log + Dispatch Log `Failed`; in-app vẫn chạy; chứng từ **không** bị chặn ghi sổ |
| TC12 | Chọn một Department **nhóm** có phòng con | Người ở phòng con cũng nhận |
| TC13 | Sửa `subject_template` trong cấu hình | Lần bắn kế tiếp dùng tiêu đề mới, không cần deploy |

**Tiêu chí nghiệm thu:** toàn bộ TC đạt trên staging; vận hành thử một tuần trên môi trường thật với A Hiếu, Xuân, C. Lan; ≥1 NCC + 1 khách thật xác nhận đã nhận email (khách nhận kèm PDF phiếu giao); nghiệp vụ tự thêm/bớt người nhận qua giao diện không cần dev/admin; scheduler bật liên tục cả tuần.

---

## 14. Kế hoạch triển khai (4 tuần, 09–10/2026)

Vai trò: **Dev**, **BA** (nội dung, kiểm thử, hướng dẫn), **Admin** (phòng ban, `user_id`, liên hệ NCC/khách). Người dùng thử: A Hiếu, Xuân, C. Lan. **Bắt buộc có staging** vì kiểm thử nhắc hạn cần giả lập ngày.

### Tuần 1 — Chuẩn bị dữ liệu & hạ tầng *(song song với build bước 2–6)*
- Bật scheduler; kiểm mail gửi được; kiểm realtime bằng tay trên desk.
- Tạo phòng `Kho`, `Mua hàng`; gán nhân viên vào phòng; **gắn `user_id` cho 5 nhân viên còn thiếu**.
- Rà soát liên hệ NCC/khách (hiện **0 Contact gắn NCC**); lập danh sách còn thiếu.
- Chốt câu chữ 12 thông báo (Phụ lục A) + chữ ký/hotline Miyano (D5); A Hiếu duyệt.
- *Ra được:* dữ liệu nhân sự & liên hệ đủ, mẫu nội dung chốt, hạ tầng xanh.

### Tuần 2 — Cơ chế cấu hình người nhận *(build bước 2–6)*
- 4 DocType, role `Quản trị thông báo`, resolver, xem trước, seed 12 điểm.
- *Ra được:* nghiệp vụ tự cấu hình & xem trước được; đạt TC-R1…R5, TC12.

### Tuần 3 — Bắn khi Ghi sổ + in-app có tiếng *(build bước 7–10)*
- Nội dung email nội bộ & ngoài; đính PDF cho NTF-07; 10 điểm theo Submit; chuông + toast + chống dội.
- *Ra được:* Submit → đúng người nhận email + chuông kêu; email ngoài không vào spam; đạt TC1–TC7, TC10, TC13.

### Tuần 4 — Nhắc hạn + đóng gói + nghiệm thu *(build bước 11–14)*
- Job nhắc hạn 7/3/1 + chống trùng; kiểm bằng giả lập ngày.
- Đóng gói cấu hình để nhân rộng site; đưa lên môi trường thật.
- Kiểm thiết lập thông báo cá nhân 3 người dùng; viết hướng dẫn một trang.
- Vận hành thử một tuần trên chứng từ thật (≥1 NCC + 1 khách thật nhận email); họp nghiệm thu.
- *Ra được:* biên bản nghiệm thu; danh sách điểm cần tắt/gộp sau một tháng.

### Sau go-live (backlog riêng)
Nhúng bảng tồn kho vào thông báo Đơn bán (F-036); tự động giao việc ToDo theo chuỗi (F-035); mẫu in tiếng Việt cho Đơn mua hàng & Yêu cầu thanh toán rồi bật lại `attach_pdf` cho NTF-03/11; SMS/Zalo ZNS; portal NCC/khách.

---

## Phụ lục A — Nội dung mẫu 12 thông báo (giá trị seed)

Phần trong ngoặc ⟨ ⟩ là dữ liệu hệ thống tự điền. Câu chữ sửa được trực tiếp trong cấu hình (D7).

| Mã | Chủ đề email nội bộ | Trọng tâm thân bài |
|---|---|---|
| NTF-01 | `[SupplyCore] Đơn bán hàng ⟨số đơn⟩ của khách ⟨tên khách⟩ vừa ghi sổ – đề nghị kiểm tra tồn kho` | Ai tạo, khi nào; bảng mặt hàng; link đơn + link báo cáo tồn; hướng dẫn đủ hàng → soạn giao, thiếu hàng → tạo Yêu cầu vật tư |
| NTF-02 | `[SupplyCore] Yêu cầu vật tư ⟨số phiếu⟩ đang chờ tạo Đơn mua hàng` | Bảng mặt hàng; link phiếu; đề nghị chọn NCC và tạo đơn mua |
| NTF-03 | `[SupplyCore] Đơn mua hàng ⟨số đơn⟩ – NCC ⟨tên NCC⟩ – dự kiến nhận hàng ⟨ngày⟩` | Giá trị đơn, ngày nhận; *(nội bộ)* chuẩn bị kho; *(NCC)* xác nhận đơn + lịch giao |
| NTF-04 | `[SupplyCore] Đã nhập kho phiếu ⟨số phiếu⟩ từ NCC ⟨tên NCC⟩ – đề nghị đối chiếu và tạo hoá đơn mua` | Bảng mặt hàng; đề nghị đối chiếu đơn–phiếu, tạo hoá đơn |
| NTF-05 | `[SupplyCore] Hoá đơn mua ⟨số hoá đơn⟩ – hạn thanh toán ⟨hạn⟩` | Giá trị, hạn; ghi nhận công nợ, lên lịch chi |
| NTF-06 | `[SupplyCore] Hoá đơn ⟨số hoá đơn⟩ đến hạn thanh toán ⟨hạn⟩ – còn nợ ⟨số tiền⟩` | Số còn nợ, hạn, còn ⟨N⟩ ngày; đề nghị chuẩn bị chi |
| NTF-07 | `[SupplyCore] Phiếu giao hàng ⟨số phiếu⟩ cho khách ⟨tên khách⟩ đã xuất kho, đang giao` | *(nội bộ)* theo dõi giao nhận; *(khách)* chuẩn bị nhận hàng, **kèm PDF** |
| NTF-08 | `[SupplyCore] Hoá đơn bán ⟨số hoá đơn⟩ đến hạn thu tiền ⟨hạn⟩ – khách còn nợ ⟨số tiền⟩` | Số khách còn nợ, hạn, còn ⟨N⟩ ngày; theo dõi thu |
| NTF-09 | `[SupplyCore] Yêu cầu thanh toán ⟨số phiếu⟩ cho NCC ⟨tên NCC⟩ – số tiền ⟨số tiền⟩` | Số tiền; đề nghị kiểm tra và chi |
| NTF-10 | `[SupplyCore] Đã thanh toán ⟨số tiền⟩ cho ⟨tên NCC⟩ theo phiếu ⟨số phiếu⟩` | *(nội bộ)* đối chiếu công nợ; *(NCC)* báo đã chi, đề nghị kiểm tra tài khoản |
| NTF-11 | `[SupplyCore] Đề nghị thanh toán ⟨số phiếu⟩ – khách ⟨tên khách⟩ – số tiền ⟨số tiền⟩⟨ – hạn ⟨hạn⟩⟩` | *(nội bộ)* theo dõi; *(khách)* đề nghị thanh toán. Đoạn "– hạn …" **chỉ hiện khi tra được** `due_date` của chứng từ gốc (D9) |
| NTF-12 | `[SupplyCore] Đã nhận thanh toán ⟨số tiền⟩ từ quý khách ⟨tên khách⟩ theo phiếu ⟨số phiếu⟩ – trân trọng cảm ơn` | *(nội bộ)* ghi nhận thu, đối chiếu; *(khách)* xác nhận đã nhận tiền, cảm ơn |

Mẫu email NTF-01 (khung chuẩn cho các điểm khác):

> Đơn bán hàng ⟨số đơn⟩ – khách hàng ⟨tên khách⟩ vừa được ghi sổ bởi ⟨họ tên người tạo⟩ ngày ⟨ngày⟩.
> Vui lòng kiểm tra tồn kho các mặt hàng sau và phản hồi trong ngày:
> *(bảng: Mã vật tư | Tên hàng | Số lượng | ĐVT)*
> → **Mở đơn hàng** · **Mở báo cáo tồn kho**
> Nếu đủ hàng: soạn hàng và giao (Pick List / Phiếu giao hàng). Nếu thiếu: tạo Yêu cầu vật tư loại Mua hàng ngay từ đơn này để chuyển sang bộ phận mua hàng.

---

## Phụ lục B — Bảng đối chiếu trường (đã kiểm chứng trên DocType JSON v15 của repo)

| Thông tin | Trường | Có ở |
|---|---|---|
| Số chứng từ | `name` | tất cả |
| Tên khách hàng | `customer_name` | Sales Order, Delivery Note, Sales Invoice |
| Tên nhà cung cấp | `supplier_name` | Purchase Order, Purchase Receipt, Purchase Invoice |
| Tên đối tác (chứng từ tiền) | `party_name` / `party_type` / `party` | Payment Request, Payment Entry |
| Họ tên người tạo | `User.full_name` tra từ `doc.owner` | tất cả — **không** dùng thẳng `doc.owner` (là email) |
| Ngày dự kiến nhận hàng | `schedule_date` | Purchase Order, Material Request |
| Hạn thanh toán / thu | `due_date` | Purchase Invoice, Sales Invoice |
| Ngày ghi sổ | `posting_date` | Purchase Receipt, Purchase Invoice, Delivery Note, Sales Invoice, Payment Entry |
| Ngày chứng từ | `transaction_date` | Sales Order, Purchase Order, Material Request, Payment Request |
| Giá trị | `grand_total` | Sales Order, Purchase Order, Purchase Receipt, Purchase Invoice, Delivery Note, Sales Invoice, Payment Request |
| Số tiền đã chi/thu | `paid_amount` | **Payment Entry** — DocType này **không có** `grand_total` |
| Còn nợ | `outstanding_amount` | Purchase Invoice, Sales Invoice, Payment Request |
| Email đối tác trên chứng từ | `contact_email` | Sales Order, Purchase Order, Purchase Receipt, Purchase Invoice, Delivery Note, Sales Invoice, Payment Entry |
| Email đối tác (Payment Request) | `email_to` | Payment Request |
| Bảng mặt hàng | `items` | các chứng từ hàng hoá; **Payment Request / Payment Entry không có** |
| Điều kiện loại Yêu cầu vật tư | `material_request_type` ∈ `Purchase, Material Transfer, Material Issue, Manufacture, Customer Provided` | NTF-02 lấy `Purchase` |
| Điều kiện loại Yêu cầu thanh toán | `payment_request_type` ∈ `Outward, Inward` | NTF-09 / NTF-11 |
| Điều kiện loại Thanh toán | `payment_type` ∈ `Receive, Pay, Internal Transfer` | NTF-10 / NTF-12 |
| Chứng từ gốc của Payment Request | `reference_doctype` + `reference_name` | dùng tra `due_date` cho NTF-11 (D9) |
| Link mở chứng từ | `frappe.utils.get_url_to_form(doctype, name)` | chỉ email nội bộ |
| Link báo cáo tồn | `/app/query-report/Stock Balance` | chỉ NTF-01 |

**Ba khác biệt so với bảng 4.4 của bản V3 — bắt buộc sửa theo bảng này:**
1. `Payment Request` **không có** trường hạn thanh toán → NTF-11 phải tra sang chứng từ gốc (D9).
2. `Payment Entry` **không có** `grand_total` → NTF-10/12 dùng `paid_amount`.
3. `⟨người tạo đơn⟩` không phải `doc.owner` (email) mà là `User.full_name` — nguyên tắc §8.4.

---

## Phụ lục C — Cấu hình mặc định khi seed

12 bản ghi `Supply Notification Point`, tất cả `enabled = 1`, `send_email = 1`, `send_inapp = 1`.

| Mã | `reference_doctype` | `trigger_event` | `departments` | `notify_owner` | `notify_external` | `attach_pdf` / `print_format` |
|---|---|---|---|---|---|---|
| NTF-01 | Sales Order | Submit | Kho - M | ✅ | – | – |
| NTF-02 | Material Request | Submit | Mua hàng - M | – | – | – |
| NTF-03 | Purchase Order | Submit | Kho - M | – | ✅ | – |
| NTF-04 | Purchase Receipt | Submit | Mua hàng - M, Kế toán - M | – | – | – |
| NTF-05 | Purchase Invoice | Submit | Kế toán - M | – | – | – |
| NTF-06 | Purchase Invoice | Due Reminder | Kế toán - M, Mua hàng - M | – | – | – |
| NTF-07 | Delivery Note | Submit | Kinh doanh - M | – | ✅ | ✅ `Phiếu xuất kho (02-VT)` |
| NTF-08 | Sales Invoice | Due Reminder | Kế toán - M | – | – | – |
| NTF-09 | Payment Request | Submit | Kế toán - M | – | – | – |
| NTF-10 | Payment Entry | Submit | Mua hàng - M, Kế toán - M | – | ✅ | – |
| NTF-11 | Payment Request | Submit | Kinh doanh - M, Kế toán - M | – | ✅ | – |
| NTF-12 | Payment Entry | Submit | Kinh doanh - M, Kế toán - M | – | ✅ | – |

Quy tắc seed: chạy lại **không** ghi đè bản ghi đã tồn tại (nghiệp vụ có thể đã chỉnh); chỉ tạo bản ghi còn thiếu. Department không tồn tại → bỏ dòng đó khỏi bảng con và ghi log, không nổ.

---

## Phụ lục D — Đối chiếu với spec gốc V3 và các sai khác có chủ ý

### D.1. Truy vết 12 bước của V3 → điểm thông báo
| Bước V3 | Sự kiện | Mã trong tài liệu này |
|---|---|---|
| 1 | Submit Sales Order | NTF-01 |
| 2 | Submit Material Request (Purchase) | NTF-02 |
| 3 | Submit Purchase Order | NTF-03 |
| 4 | Submit Purchase Receipt | NTF-04 |
| 5 | Submit Purchase Invoice | NTF-05 |
| 6 | Payment Request chi NCC | NTF-09 |
| 7 | Payment Entry loại Pay | NTF-10 |
| 8 | Nhắc hạn thanh toán PI | NTF-06 |
| 9 | Submit Delivery Note | NTF-07 |
| 10 | Nhắc hạn thu tiền SI | NTF-08 *(không bắn khi Submit SI — D8)* |
| 11 | Payment Request thu khách | NTF-11 |
| 12 | Payment Entry loại Receive | NTF-12 |

Đủ 12/12. Backlog F-035, F-036, F-038 và cảnh báo tồn F-017/F-018 giữ nguyên ngoài phạm vi.

### D.2. Sai khác có chủ ý so với V3
| # | V3 nói | Tài liệu này | Vì sao |
|---|---|---|---|
| 1 | Kênh SMS cho NCC/khách (F-038, 5 mẫu SMS, SMS Settings, brandname) | **Bỏ hẳn** | Quyết định phạm vi của Miyano; brandname mất 2–4 tuần và phát sinh phí. Nếu làm lại sau thì lập CR riêng |
| 2 | Người nhận nội bộ **theo Role** (4 role `SC …`, "bắt buộc Receiver By Role") | **Theo Phòng ban + Người đích danh** | Role là quyền hệ thống, một người giữ nhiều role (A Hiếu giữ 3) nên gửi theo role bắn thừa. Khảo sát: **chưa role `SC …` nào tồn tại** trên site → không có gì phải bỏ đi. Mục tiêu gốc *"đổi người phụ trách không phải sửa cấu hình"* vẫn đạt: đổi phòng ban của nhân viên là thông báo tự chuyển |
| 3 | Dùng DocType `Notification` chuẩn (16 bản ghi) | **Module `Supply Notification` riêng** | `Notification` chuẩn không chọn được người nhận theo phòng ban, không xem trước được người nhận, không chống gửi trùng, và không tách được quyền sửa cấu hình khỏi quyền nghiệp vụ |
| 4 | In-app cho NCC/khách nếu có tài khoản portal | **Bỏ** | Không cấp portal trong đợt này |
| 5 | Không yêu cầu âm báo | **In-app có tiếng + toast** | Yêu cầu bổ sung của Miyano |
| 6 | Nhắc hạn = 3 bản ghi Notification "Days Before" mỗi loại | **1 job hằng ngày quét cả 3 mốc + chống gửi trùng** | Ít bản ghi hơn, kiểm chứng được qua Dispatch Log, chạy bù an toàn |
| 7 | Đính PDF cho PO / DN / Payment Request | **Chỉ Delivery Note** | Chưa có mẫu in tiếng Việt cho PO và Payment Request (D4); mở lại sau khi có mẫu |
| 8 | Bảng Jinja 4.4 | **Sửa 3 chỗ sai** | Xem cuối Phụ lục B |

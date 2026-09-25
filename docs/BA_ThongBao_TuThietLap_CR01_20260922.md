# TÀI LIỆU PHÂN TÍCH NGHIỆP VỤ (BA)

## Xây dựng lại tính năng Thông báo – người dùng tự thiết lập toàn bộ trên giao diện

| Thông tin        | Nội dung                                                                                                                                                                                                                                                                          |
| ----------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Mã tài liệu    | BA_NTF_V4 (thay thế phần cấu hình của`05c_Spec_KyThuat_Plan_Thong_Bao.md` v2)                                                                                                                                                                                               |
| Phiên bản | **V1.0 – 22/09/2026 – BẢN CHỐT ĐỂ BUILD** |
| Hệ thống        | Miyano ERP – module`Supply Notification` (`erpnext/supply_notification/`)                                                                                                                                                                                                     |
| Nhánh            | `feat/vn-mua-ban-thong-bao-tu-dong`                                                                                                                                                                                                                                              |
| Đầu vào        | (1) Yêu cầu 22/09/2026:*xây dựng lại cả tính năng thông báo cho hoàn thiện, người dùng tùy chỉnh được nhiều hơn, tránh cố định trong code*; (2) `CR_01_ThongBaoPO_GuiNCC_20260917_V2.1.md` (điều chỉnh điểm NTF-03 – bước 3 Đơn mua hàng) |
| Người yêu cầu | Tạ Trường Xuân (PO)                                                                                                                                                                                                                                                            |
| Dev phụ trách   | Hiếu bé                                                                                                                                                                                                                                                                          |

**Lịch sử thay đổi**

| Phiên bản | Ngày      | Nội dung                                                                                                                                                                                                                                                                                                                                                                               |
| ----------- | ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| V0.1        | 22/09/2026 | Bản đầu: mở rộng cấu hình điểm thông báo +CR_01_ThongBaoPO_GuiNCC_20260917_V2.1.md CR_01 là một mảng riêng                                                                                                                                                                                                                                                               |
| V0.2        | 22/09/2026 | Đổi trọng tâm:**xây dựng lại toàn bộ tính năng** theo nguyên tắc "nghiệp vụ nằm trong cấu hình, không nằm trong code". Thêm *Cài đặt thông báo*, *Nhóm người nhận*, *Mẫu dùng chung*, chế độ thử, tự tắt nhận, gửi lại từ nhật ký, thống kê. CR_01 chỉ còn là **một điều chỉnh cấu hình của NTF-03** (mục 8) |
| V1.1 | 23/09/2026 | **Cập nhật theo bản đã build** (xem mục 14). Sáu điều chỉnh so với bản chốt, đều có lý do kỹ thuật: D21 bỏ Custom Field trên Address; người nhận hàng lấy từ Liên hệ; quy tắc hiển thị trường Link; "trường thay đổi" bỏ qua trống→0; điều kiện ngày hỏng coi là không thoả; quy ước mốc gửi. Phiên bản này là bản khớp với hệ thống đang chạy |
| V1.0 | 22/09/2026 | **Chốt để build.** PO trả lời: không đính PDF khi gửi PO (D23); dùng hộp thư mặc định đã cấu hình, không đổi (D24); bỏ bản tin tổng hợp / ToDo (D25); một role quản trị chung (D26); Q3–Q9 chốt theo đề xuất (D27–D32). Mục 13 chuyển thành *Quyết định đã chốt* |

> **Cách đọc.** Mục 1–3: vấn đề và nguyên tắc. Mục 4 và 13: các quyết định đã chốt. Mục 5–7: yêu cầu chi tiết của tính năng mới. Mục 8: CR_01 dựng trên tính năng mới ra sao. Mục 11: tiêu chí nghiệm thu. Mục 12: giai đoạn và ước lượng. Phụ lục cho Dev ở cuối.

---

## 1. Bối cảnh và vấn đề

### 1.1. Hiện trạng (khảo sát mã nguồn và site `miyano` ngày 22/09/2026)

Bản build theo Spec 05c đã chạy được: 12 điểm NTF-01…NTF-12, email nội bộ, thông báo trong hệ thống có âm báo, email ra NCC/khách, nhắc hạn 7/3/1 ngày, nhật ký gửi, 50 test. Nhưng gần như **toàn bộ logic nghiệp vụ đang nằm trong code**:

| Hạng mục                                                               | Sửa trên giao diện?                                                                                                                                                                                                                                                                                                                                                                                | Đang cố định ở đâu                                            |
| ------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| Bật/tắt điểm, bật/tắt kênh                                        | ✅                                                                                                                                                                                                                                                                                                                                                                                                    | –                                                                   |
| Người nhận nội bộ theo phòng ban / người cụ thể / người tạo | ✅                                                                                                                                                                                                                                                                                                                                                                                                    | –                                                                   |
| Tiêu đề, câu mở đầu, câu "việc cần làm", chữ ký ngoài      | ✅ (4 ô chữ ngắn)                                                                                                                                                                                                                                                                                                                                                                                  | –                                                                   |
| **Tạo điểm thông báo mới**                                   | ❌ role*Quản trị thông báo* không có quyền tạo                                                                                                                                                                                                                                                                                                                                              | Quyền DocType                                                       |
| **Chứng từ nguồn**                                              | ❌ ô chỉ đọc                                                                                                                                                                                                                                                                                                                                                                                      | `constants.py`                                                     |
| **Điều kiện bắn**                                              | ❌ chỉ có dòng mô tả                                                                                                                                                                                                                                                                                                                                                                             | `constants.py`, `events.py`                                      |
| **Thời điểm bắn** (chỉ Ghi sổ, Nhắc hạn)                   | ❌                                                                                                                                                                                                                                                                                                                                                                                                    | `events.py`, `reminders.py`, `hooks.py` (nối cứng 8 DocType) |
| Mốc nhắc 7/3/1 ngày, giờ chạy 08:00                                 | ❌                                                                                                                                                                                                                                                                                                                                                                                                    | `constants.DUE_MILESTONES`, `hooks.py` cron                      |
| Trường lấy tên đối tác / số tiền / ngày                        | ❌                                                                                                                                                                                                                                                                                                                                                                                                    | `constants.py`                                                     |
| Bố cục email, bảng mặt hàng (cột nào, tối đa 50 dòng)          | ❌                                                                                                                                                                                                                                                                                                                                                                                                    | `templates/*.html`, `content.py`                                 |
| Tiền tố tiêu đề`[SupplyCore]`                                     | ❌                                                                                                                                                                                                                                                                                                                                                                                                    | `constants.PREFIX`                                                 |
| Âm báo, thời gian hiện toast, chống dội 3 giây                    | ❌                                                                                                                                                                                                                                                                                                                                                                                                    | `constants.SOUND`, `supply_notification_toast.js`                |
| Người nhận ngoài, CC, trả lời về ai                               | ❌ chỉ lấy email liên hệ đối tácCách đọc. Mục 1–3: vấn đề và nguyên tắc. Mục 4: quyết định cần chốt. Mục 5–7: yêu cầu chi tiết của tính năng mới. Mục 8: CR_01 dựng trên tính năng mới ra sao. Mục 11: tiêu chí nghiệm thu. Mục 12: giai đoạn và ước lượng. Mục 13: câu hỏi mở, phải trả lời trước khi build. Phụ lục cho Dev ở cuối. | `resolver.py`                                                      |
| Thời gian giữ nhật ký (180 ngày)                                    | ❌                                                                                                                                                                                                                                                                                                                                                                                                    | `supply_notification_dispatch_log.py`                              |
| Gửi thủ công bằng nút trên chứng từ                              | ❌ chưa có                                                                                                                                                                                                                                                                                                                                                                                          | –                                                                   |
| Xem trước email, gửi thử, hướng dẫn                               | ❌ chỉ có*Xem trước người nhận*                                                                                                                                                                                                                                                                                                                                                              | –                                                                   |

**Hệ quả:** mọi yêu cầu mới (CR_01 là ví dụ đầu tiên) đều phải sửa code, test lại và deploy.

### 1.2. Mục tiêu

Xây dựng lại tính năng Thông báo để **người có role *Quản trị thông báo* tự làm được mọi việc cấu hình** trên giao diện, có hướng dẫn và công cụ tự kiểm tra ngay trên màn hình:

1. Tạo, sửa, sao chép, tắt điểm thông báo trên **bất kỳ chứng từ nghiệp vụ nào**.
2. Tự chọn **khi nào gửi**, **điều kiện**, **gửi cho ai** (trong và ngoài công ty, CC, trả lời về ai), **qua kênh nào**, **tiêu đề và nội dung**, **đính kèm**.
3. Tự chỉnh các thông số chung đang cố định trong code (âm báo, mốc nhắc, giờ chạy, thời gian giữ nhật ký, tiền tố tiêu đề, chân email).
4. Kiểm tra trước khi bật: xem trước người nhận, xem trước email với chứng từ thật, gửi thử cho chính mình, chế độ thử cho toàn hệ thống.
5. Theo dõi sau khi bật: nhật ký, thống kê, gửi lại thư lỗi.

**Đo thành công**

- Yêu cầu thông báo mới ở mức *đổi câu chữ / đổi người nhận / thêm điểm trên chứng từ có sẵn / thêm điều kiện / đổi mốc nhắc* được nghiệp vụ tự làm **≤ 30 phút, không cần Dev, không cần deploy**.
- CR_01 được đáp ứng **hoàn toàn bằng cấu hình**. Code chỉ thêm các khối dùng chung mà CR_01 cần lần đầu (mục 8).
- Sau chuyển đổi, 12 điểm cũ gửi **đúng như trước**.

---

## 2. Nguyên tắc thiết kế

1. **Nghiệp vụ nằm trong cấu hình, code chỉ là bộ máy.** Code không được chứa tên chứng từ cụ thể, tên trường cụ thể, điều kiện nghiệp vụ, câu chữ hay người nhận. Những thứ đó là dữ liệu cấu hình, do người dùng sửa.
2. **Ranh giới rõ giữa cấu hình và code:** xem bảng ngay dưới.
3. **Không chặn nghiệp vụ.** Lỗi thông báo không bao giờ làm hỏng việc lưu hay ghi sổ chứng từ (giữ nguyên 05c).
4. **An toàn trước, linh hoạt sau.** Mẫu nội dung không gọi được hàm hệ thống, không sửa được dữ liệu. Email ra ngoài không chứa đường dẫn nội bộ.
5. **Tự kiểm được.** Cái gì cấu hình được thì xem trước được và thử được, trước khi gửi thật.
6. **Không mất những gì đang chạy.** Chuyển đổi giữ nguyên hành vi của 12 điểm và câu chữ nghiệp vụ đã sửa trên site.

| Người dùng cấu hình                                     | Code đảm nhiệm                                                            |
| ------------------------------------------------------------ | ---------------------------------------------------------------------------- |
| Chứng từ, thời điểm, điều kiện                       | Bộ máy bắt sự kiện, đánh giá điều kiện, chạy nền, chống trùng |
| Người nhận, nhóm người nhận                           | Diễn giải phòng ban → người, lọc user khoá, khử trùng              |
| Tiêu đề, thân email, câu thông báo, chân email       | Jinja hộp cát, định dạng tiền/ngày/tên                               |
| Chọn khối nội dung và cột của khối                    | Cách dựng từng khối (bảng mặt hàng, địa chỉ giao, chữ ký…)      |
| Âm báo, mốc nhắc, giờ chạy, thời gian lưu | Giới hạn an toàn (danh sách DocType cấm, trần số email) |

---

## 3. Phạm vi

**Trong phạm vi**

- Xây dựng lại bộ cấu hình thông báo: 5 đối tượng ở mục 5.
- Bộ máy chung: 7 loại thời điểm, điều kiện dạng bảng, người nhận mở rộng, nội dung có trường và khối, đính kèm, 3 kênh.
- Giao diện có hướng dẫn: chèn trường, xem trước, gửi thử, kiểm tra khi lưu, workspace, trang hướng dẫn, HDSD.
- Vận hành: chế độ thử, thống kê, gửi lại thư lỗi, người nhận tự tắt nhận.
- Chuyển đổi 12 điểm NTF-01…NTF-12 sang cấu hình mới.
- **CR_01:** điều chỉnh NTF-03 bằng cấu hình (mục 8).

**Ngoài phạm vi**

- Nút Xác nhận / Từ chối PO trong email (**CR_02**). Chỉ chừa vị trí bằng khối `khoi_phan_hoi`.
- SMS, Zalo, Supplier/Customer Portal (05c đã bỏ SMS).
- Đọc thư trả lời của đối tác để tự cập nhật chứng từ.
- Tự giao việc ToDo (F-035) và bản tin tổng hợp định kỳ (D25).
- Đính PDF khi gửi PO cho NCC (D23). Khả năng đính PDF chung vẫn giữ cho điểm khác, ví dụ NTF-07.
- Đổi hộp thư gửi đi: dùng hộp thư mặc định đã cấu hình của site (D24).
- Phân quyền cấu hình theo nhóm chức năng (D26).
- Thay thế DocType *Notification* chuẩn của Frappe. Nó vẫn phục vụ assetcore và hrms, không đụng tới.
- Người dùng tự viết điều kiện hay nội dung bằng mã Python.

---

## 4. Quyết định thiết kế (đã chốt)

| Mã           | Nội dung                                     | Đề xuất                                                                                                                                                                                                                                              | Lý do                                                                                                                                                                                                                                                                               |
| ------------- | --------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **D10** | Nền tảng                                    | Xây lại**trong module `Supply Notification`**, giữ tên DocType *Supply Notification Point* và nhật ký. **Không** chuyển sang *Notification* chuẩn của Frappe                                                               | *Notification* chuẩn không chọn được người nhận theo phòng ban, không xem trước người nhận, không chống gửi trùng, điều kiện phải viết bằng Python (05c Phụ lục D.2 #3). Giữ tên DocType thì giữ được dữ liệu, nhật ký và quyền đang có |
| **D11** | Điều kiện bắn                             | **Bảng điều kiện dạng chọn**: *Trường – Toán tử – Giá trị*, chọn nối **VÀ** hoặc **HOẶC** cho cả bảng. Trường được chọn cả trong bảng con (vd. *mặt hàng thuộc nhóm X*). Không có ô viết mã | Nghiệp vụ tự làm, kiểm được khi lưu. Mọi điều kiện của 12 điểm cũ biểu diễn được                                                                                                                                                                               |
| **D12** | Loại thời điểm                            | **7 loại:** Tạo mới · Ghi sổ · Huỷ · Trường thay đổi giá trị · **Chuyển trạng thái duyệt (Workflow)** · Nhắc theo ngày · **Thủ công (nút trên chứng từ)**. Không có "mỗi lần Lưu"                   | "Mỗi lần Lưu" dễ gây bão thư. Site đang có Workflow trên Payment Entry, Sales Order nên cần báo theo bước duyệt                                                                                                                                                      |
| **D13** | Soạn nội dung                               | Một ô**thân email** có định dạng (chuyển được sang HTML), chèn **trường** và **khối**. Ba ô cũ (mở đầu, việc cần làm, chữ ký) gộp vào thân khi chuyển đổi                                             | Người dùng thấy đúng như email thật; phần bảng biểu do khối dựng                                                                                                                                                                                                        |
| **D14** | Dùng lại cấu hình                         | Thêm**Nhóm người nhận** và **Mẫu nội dung dùng chung** (chân email, chữ ký, đoạn quy định giao hàng…), chèn vào nhiều điểm; sửa một chỗ, mọi điểm đổi theo                                                   | Tránh sửa 13 chỗ khi đổi hotline hay đổi người phụ trách                                                                                                                                                                                                                  |
| **D15** | Thông số chung                              | DocType đơn**Cài đặt thông báo** chứa mọi hằng số đang nằm trong code (mục 5.1)                                                                                                                                                     | Nguyên tắc 1                                                                                                                                                                                                                                                                       |
| **D16** | Chế độ thử                                | Công tắc**Chế độ thử** trong *Cài đặt thông báo*: khi bật, **mọi email** (nội bộ và ngoài) chuyển về một địa chỉ thử, tiêu đề thêm `[THỬ → email gốc]`                                                   | Chặn rủi ro gửi nhầm NCC/khách thật khi chưa bật scheduler hoặc đang nghiệm thu (RK1)                                                                                                                                                                                     |
| **D17** | Gửi lại / chống trùng                     | Loại tự động: mỗi (điểm × chứng từ × mốc) gửi một lần. Loại**Thủ công**: mỗi lần bấm là một lần gửi, có hộp xác nhận. Nhật ký *Failed* có nút **Gửi lại**                                              | Theo CR_01 R2, AC5                                                                                                                                                                                                                                                                   |
| **D18** | Người nhận tự tắt                        | Điểm nội bộ có cờ**"Cho phép người nhận tự tắt"**. Người nhận tắt/bật ở trang *Thông báo của tôi*. Mặc định **không** cho tắt với điểm yêu cầu xử lý (vd. NTF-06 nhắc hạn)                            | Giảm thư thừa mà không mất thư bắt buộc                                                                                                                                                                                                                                     |
| **D19** | Chứng từ được chọn                      | Mọi DocType nghiệp vụ,**trừ** DocType hệ thống và nhật ký (Email Queue, Notification Log, Communication, Comment, Version, Error Log, Activity Log, *Dispatch Log*…)                                                                  | Chống vòng lặp thư sinh thư                                                                                                                                                                                                                                                     |
| **D20** | Xoá điểm                                   | Điểm hạt giống không xoá được, chỉ tắt. Điểm do người dùng tạo: chưa có nhật ký thì xoá được, đã có thì chỉ tắt                                                                                                         | Giữ vết đối chiếu                                                                                                                                                                                                                                                               |
| **D21** ~~(bản V1.0)~~ | Trường người nhận hàng trên địa chỉ | ~~Thêm trường "Người nhận hàng" vào *Address* bằng Custom Field~~ | Thay bằng **D21b** |
| **D21b** (chốt 23/09/2026) | Người nhận hàng lấy ở đâu | **Không thêm trường mới vào `Address`.** PO và SO đã trỏ tới bản ghi địa chỉ rồi (`shipping_address`, `dispatch_address`, `customer_address`…), khối `dia_chi_giao_hang` đọc thẳng từ đó: **địa chỉ** từ Address, **người nhận** từ Liên hệ gắn với địa chỉ (hoặc trường liên hệ chọn trên chứng từ), **điện thoại** từ `Address.phone` rồi tới di động của liên hệ. Thiếu người nhận thì **bỏ dòng đó** khỏi email, đồng thời hộp xác nhận cảnh báo và báo cáo *"Địa chỉ giao hàng thiếu người nhận"* liệt kê để bổ sung | Không đụng DocType dùng chung với `assetcore`/`antmed_crm`/`hrms`. Cố ý **không** lấy `Address.address_title` làm tên người nhận: đó là nhãn của địa chỉ ("Kho Miyano"), lấy nhầm thì email ghi "Người nhận: Kho Miyano" và cảnh báo thiếu dữ liệu không bao giờ bật |
| **D22** | Phân quyền cấu hình                       | *Quản trị thông báo* được tạo/sửa/xoá điểm, nhóm, mẫu, cài đặt. Người khác chỉ xem. Bấm nút Thủ công: theo cấu hình của từng điểm (mặc định: người có quyền sửa chứng từ)                                    | Giữ D2 của 05c                                                                                                                                                                                                                                                                     |

---

## 5. Mô hình cấu hình (mức nghiệp vụ)

Tính năng gồm 5 đối tượng. Tên DocType chính thức do Dev chốt; tên trường là gợi ý.

```
Cài đặt thông báo (1 bản ghi) ─ thông số chung, chế độ thử, chân email mặc định
        │
        ├── Điểm thông báo (nhiều) ── Khi nào · Điều kiện · Gửi ai · Kênh · Nội dung · Đính kèm
        │        ├── dùng ──► Nhóm người nhận (nhiều)
        │        └── chèn ──► Mẫu nội dung dùng chung (nhiều)
        │
        └── Nhật ký gửi (tự sinh) ── mỗi lần gửi một dòng; thống kê; gửi lại
```

### 5.1. Cài đặt thông báo (DocType đơn)

Chuyển mọi hằng số đang nằm trong code thành cài đặt:

| Nhóm      | Cài đặt                                                                                   | Mặc định (= hành vi hiện tại)  |
| ---------- | -------------------------------------------------------------------------------------------- | ------------------------------------ |
| Toàn cục | Bật toàn bộ tính năng                                                                   | Bật                                 |
| Toàn cục | **Chế độ thử** + email nhận thử (D16)                                            | Tắt                                 |
| Email      | Tiền tố tiêu đề mặc định cho điểm mới                                             | `[SupplyCore]`                     |
| Email      | Chân email nội bộ / ngoài mặc định (chọn*Mẫu dùng chung*)                        | Trống                               |
| Email      | Số dòng tối đa của bảng mặt hàng                                                     | 50                                   |
| In-app     | Âm báo (chọn trong danh sách âm có sẵn), thời gian hiện toast, khoảng chống dội  | `alert`, 10 giây, 3 giây         |
| Nhắc hạn | Giờ chạy hằng ngày, dùng chung mọi điểm (D31) | 08:00 |
| An toàn   | Trần số email mỗi điểm mỗi giờ; vượt thì tự tạm dừng điểm và báo quản trị | 200                                  |
| Nhật ký | Số ngày giữ nhật ký loại tự động / loại Thủ công (D30) | 180 / vĩnh viễn |

### 5.2. Điểm thông báo

Form chia 7 thẻ. Mỗi thẻ có **dòng hướng dẫn ngắn** ở đầu, mỗi trường có mô tả.

| Thẻ                                  | Nội dung cấu hình                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            | Hướng dẫn hiển thị (ví dụ)                                                                                        |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| **1. Chung**                    | Mã (tự gợi ý mã kế tiếp), Tên, Đang bật, Nhóm chức năng (Mua hàng / Bán hàng / Kho / Kế toán… để lọc danh sách), Ghi chú                                                                                                                                                                                                                                                                                                                                                                                                                                | "Mỗi điểm là một loại thông báo. Tắt thay vì xoá để giữ lịch sử."                                        |
| **2. Khi nào gửi**            | Chứng từ nguồn · Loại thời điểm (D12), tuỳ loại:*Trường theo dõi* · *Trạng thái duyệt đích* · *Trường ngày + danh sách mốc (vd. `-7, -3, -1` là trước hạn, `+1, +7` là quá hạn)* · *Nhãn nút + màu + ai được bấm + trạng thái chứng từ cho phép bấm* · **Bảng điều kiện** (D11)                                                                                                                                                                                                                            | "Ví dụ: Yêu cầu vật tư · Ghi sổ ·*Loại yêu cầu = Mua hàng*."                                              |
| **3. Gửi cho ai**              | **Nội bộ:** phòng ban, người cụ thể, **nhóm người nhận**, người tạo chứng từ, **người ghi trong một trường của chứng từ** (vd. *Người phụ trách*, *Người duyệt*), người bấm gửi · **Bên ngoài:** đầu mối liên hệ của đối tác (NCC/khách, tự nhận theo chứng từ), email ghi trong trường của chứng từ, email cố định · **CC** và **BCC** · **Trả lời về:** người tạo / người bấm gửi / email cố định · Cờ *Cho phép người nhận tự tắt* (D18) | Nút**Xem trước người nhận** chọn được chứng từ mẫu để thấy cả người nhận ngoài và cảnh báo |
| **4. Kênh**                    | Email nội bộ · Thông báo trong hệ thống (có âm báo) · Email ra ngoài                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                | "Email ra ngoài không bao giờ chứa đường dẫn vào hệ thống."                                                   |
| **5. Nội dung nội bộ**       | Tiêu đề · Thân email · Câu thông báo trong hệ thống (mặc định = tiêu đề)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | Bảng**"Có thể chèn"** + nút **Chèn trường**, **Chèn khối**, **Chèn mẫu dùng chung** |
| **6. Nội dung gửi ra ngoài** | Tiêu đề · Thân email · **Đính kèm (tuỳ chọn):** PDF theo mẫu in, tệp đã đính trên chứng từ (có/không) · Bắt buộc có PDF (không tạo được PDF thì không gửi) | Chỉ liệt kê khối an toàn cho bên ngoài. Hộp thư gửi là hộp thư mặc định của site (D24) |
| **7. Kiểm tra**                | **Xem trước email** (chọn chứng từ thật; hiện tiêu đề, thân, người nhận, CC, tệp; **không gửi**) · **Gửi thử cho tôi** (chỉ tới email người đang thao tác, tiêu đề `[THỬ]`, không ghi nhật ký nghiệp vụ) · Số lần gửi 30 ngày qua, tỉ lệ lỗi                                                                                                                                                                                                                                                                    | "Luôn xem trước với một chứng từ thật trước khi bật điểm."                                                  |

**Thanh công cụ:** Xem trước người nhận · Xem trước email · Gửi thử cho tôi · Sao chép điểm · Mở nhật ký của điểm · Hướng dẫn (?).

**Tạo điểm theo mẫu:** khi bấm *Mới*, cho chọn "Bắt đầu từ": *Trống* / *Báo nội bộ khi ghi sổ* / *Nhắc hạn theo ngày* / *Gửi đối tác bằng nút*. Mỗi mẫu điền sẵn một cấu hình ví dụ đúng, người dùng chỉ sửa.

### 5.3. Nhóm người nhận

Danh sách đặt tên (vd. *"Ban mua hàng"*, *"Kế toán công nợ phải trả"*) gồm phòng ban, người cụ thể và email cố định (email ngoài chỉ dùng cho điểm gửi ra ngoài). Một nhóm dùng cho nhiều điểm. Có nút *Xem thành viên thực tế*.

### 5.4. Mẫu nội dung dùng chung

Đoạn nội dung đặt tên, có phạm vi *Nội bộ* / *Ngoài* / *Cả hai*, chèn vào điểm bằng `{{ mau("Tên mẫu") }}`. Ví dụ: *Chân email Miyano*, *Quy định giao nhận hàng hoá* (4 gạch đầu dòng của CR_01), *Hotline*. Sửa mẫu thì mọi điểm dùng mẫu đổi theo ở lần gửi kế tiếp. Không xoá được mẫu đang được dùng; form hiện danh sách điểm đang dùng.

### 5.5. Nhật ký gửi

Giữ DocType *Supply Notification Dispatch Log*, bổ sung: người bấm gửi, CC/BCC, tiêu đề đã gửi, tệp đính kèm, gửi trong chế độ thử (có/không), lý do bỏ qua/lỗi dễ đọc. Mở được từ form điểm, từ chứng từ nguồn (mục *Liên kết*) và từ Workspace. Dòng *Failed* có nút **Gửi lại** (gửi đúng nội dung theo cấu hình hiện tại, ghi dòng nhật ký mới).

---

## 6. Yêu cầu chức năng chi tiết

### 6.1. Thời điểm và điều kiện

| #  | Yêu cầu                                                                                                                                                                                                                                                                                                                                            |
| -- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| F1 | **Tạo mới / Ghi sổ / Huỷ:** bắn sau khi giao dịch lưu thành công, chạy nền.                                                                                                                                                                                                                                                         |
| F2 | **Trường thay đổi:** chỉ bắn khi trường được chọn **thực sự đổi giá trị** so với lần lưu trước; tuỳ chọn "chỉ khi đổi thành giá trị X".                                                                                                                                                                   |
| F3 | **Chuyển trạng thái duyệt:** chọn Workflow State đích; bắn khi chứng từ vào trạng thái đó. Chỉ hiện khi chứng từ nguồn có Workflow đang bật.                                                                                                                                                                            |
| F4 | **Nhắc theo ngày:** chạy hằng ngày theo giờ trong *Cài đặt*; mốc âm là trước ngày, mốc dương là sau ngày (quá hạn). Mỗi mốc gửi một lần. Không chạy bù mốc đã trôi qua.                                                                                                                                    |
| F5 | **Thủ công:** nút hiện trên form chứng từ nguồn khi thoả *trạng thái cho phép bấm* và *điều kiện*; bấm thì mở hộp xác nhận (người nhận, CC, tệp, số lần đã gửi, xem trước), xác nhận thì gửi. Nhiều điểm Thủ công trên cùng chứng từ thì gom vào nút nhóm **"Gửi thông báo"**. |
| F6 | **Điều kiện:** toán tử `=`, `≠`, `>`, `≥`, `<`, `≤`, *trong danh sách*, *không trong danh sách*, *có giá trị*, *trống*, *chứa*; giá trị gợi ý theo kiểu trường (danh sách chọn, Link, ngày). Trường trong bảng con thoả khi **ít nhất một dòng** thoả.                          |
| F7 | Cấu hình được cache; sửa điểm có hiệu lực ngay ở lần bắn kế tiếp, không cần xoá cache hay deploy.                                                                                                                                                                                                                                 |

### 6.2. Người nhận

| #   | Yêu cầu                                                                                                                                                                                                                                                                                                                                                                    |
| --- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| F8  | Gộp tất cả nguồn người nhận nội bộ (phòng ban gồm cả phòng con, người cụ thể, nhóm, người tạo, trường User trên chứng từ, người bấm gửi), loại user khoá/thiếu email/Administrator/Guest/**người đã tự tắt điểm này**, khử trùng. Mỗi người một email và một thông báo trong hệ thống cho mỗi lần gửi.        |
| F9  | Người nhận ngoài theo thứ tự: trường email được chọn trên chứng từ → email liên hệ trên chứng từ (`contact_email`/`email_to`) → Contact chính của đối tác → email trên hồ sơ đối tác. Không có thì bỏ phần gửi ngoài, ghi *Skipped* có lý do. Riêng loại Thủ công: báo ngay trong hộp xác nhận và khoá nút Gửi. |
| F10 | Email ra ngoài gửi**tách riêng** email nội bộ. Người nhận ngoài không thấy địa chỉ nội bộ, trừ CC và *Trả lời về* đã cấu hình.                                                                                                                                                                                                             |

### 6.3. Nội dung

| #   | Yêu cầu                                                                                                                                                                                                                                                                                                                     |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| F11 | **Chèn trường:** hộp chọn liệt kê trường của chứng từ nguồn (và của bảng con) **bằng nhãn tiếng Việt**, có ô tìm; chèn biến vào vị trí con trỏ. Tiền và ngày tự định dạng (`1.234.567 ₫`, `dd-mm-yyyy`); Link hiện tên hiển thị thay vì mã khi có.                |
| F12 | **Biến dựng sẵn:** `ten_doi_tac`, `ten_nguoi_tao`, `nguoi_bam_gui`, `so_tien`, `ngay`, `han_thanh_toan`, `so_ngay_con_lai`, `trang_thai`, `ten_cong_ty`. Người dùng chọn **trường nào** là "số tiền", "ngày" của điểm (thay cho `amount_field`, `date_field` đang cứng). |
| F13 | **Khối dựng sẵn** (code dựng, người dùng chèn và chọn tuỳ chọn): xem bảng dưới.                                                                                                                                                                                                                          |
| F14 | Chèn**Mẫu dùng chung** (5.4). Mẫu phạm vi *Nội bộ* không chèn được vào nội dung ngoài.                                                                                                                                                                                                                 |
| F15 | Đoạn điều kiện đơn giản trong nội dung:*"chỉ hiện đoạn này khi trường X có giá trị"*, chèn qua nút, không phải gõ cú pháp.                                                                                                                                                                        |

| Khối                 | Hiện gì                                                                                     | Tuỳ chọn người dùng                                          | Phạm vi                |
| --------------------- | --------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- | ----------------------- |
| `bang_mat_hang`     | Bảng dòng hàng                                                                             | **Chọn cột** (trường + nhãn + thứ tự), có cột STT  | Cả hai                 |
| `khoi_so_lieu`      | Bảng nhãn – giá trị                                                                      | **Chọn dòng** (trường + nhãn)                          | Cả hai                 |
| `dia_chi_giao_hang` | Địa chỉ giao + Người nhận – điện thoại, theo địa chỉ giao chọn trên chứng từ | Trường địa chỉ nào (giao hàng / xuất hàng / thanh toán) | Cả hai                 |
| `chu_ky`            | Họ tên – công ty / điện thoại / email                                                  | Của người tạo hay người bấm gửi                           | Cả hai                 |
| `khoi_phan_hoi`     | Vị trí phản hồi của đối tác (đợt này là câu chữ; CR_02 thay bằng 2 nút)       | Câu chữ                                                         | Ngoài                  |
| `nut_mo_chung_tu`   | Liên kết mở chứng từ                                                                     | Nhãn                                                             | **Chỉ nội bộ** |
| `link_bao_cao`      | Liên kết một báo cáo (vd. Tồn kho)                                                      | Chọn báo cáo                                                   | **Chỉ nội bộ** |

Khối **mới** (vd. lịch thanh toán, bảng tuổi nợ) do Dev thêm. Đây là ranh giới cố ý: nghiệp vụ chọn và sắp khối, code dựng khối.

### 6.4. Kiểm tra khi lưu

Chặn lưu, báo lỗi tiếng Việt có gợi ý:

| #  | Kiểm tra                                                                                                   | Thông báo mẫu                                                                                      |
| -- | ----------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| V1 | Sai cú pháp mẫu                                                                                          | "Tiêu đề lỗi ở '{{ doc.name ': thiếu dấu }}"                                                   |
| V2 | Biến trỏ tới trường không có trên chứng từ                                                        | "Trường`supplier_nam` không có trên Đơn mua hàng. Có phải ý bạn là `supplier_name`?" |
| V3 | Điều kiện sai trường, hoặc giá trị không có trong danh sách chọn                                | "Loại yêu cầu không có giá trị 'Mua'. Chọn một trong: Purchase, Material Transfer…"         |
| V4 | Nội dung ngoài có khối nội bộ, mẫu nội bộ hoặc đường dẫn`/app/`                             | "Email gửi NCC/khách không được chứa đường dẫn nội bộ."                                  |
| V5 | Điểm bật mà không có kênh, hoặc bật kênh mà không có nguồn người nhận                      | "Đã bật email nội bộ nhưng chưa chọn người nhận."                                          |
| V6 | Mẫu in không thuộc chứng từ nguồn                                                                     | (đã có)                                                                                            |
| V7 | Thiếu tham số theo loại thời điểm (trường theo dõi, trạng thái, trường ngày/mốc, nhãn nút) | "Chọn trường ngày để nhắc."                                                                    |
| V8 | Chứng từ nguồn thuộc danh sách cấm (D19)                                                              | "Không đặt thông báo trên Email Queue."                                                         |

Cảnh báo **không chặn** (dải vàng): điểm tự động vừa bật sẽ gửi ở lần kế tiếp; phòng ban chưa có nhân viên gắn tài khoản; đang bật *Chế độ thử*.

### 6.5. Hướng dẫn người dùng

1. **Trên form:** dòng hướng dẫn mỗi thẻ, mô tả mỗi trường, bảng *Có thể chèn*, mẫu khởi tạo (5.2).
2. **Trang hướng dẫn một trang** trong hệ thống (nút "?" trên form, liên kết trong Workspace): 5 bước tạo điểm; 4 ví dụ hoàn chỉnh (báo kho khi có đơn bán · nhắc hạn hoá đơn · báo theo bước duyệt · gửi PO cho NCC); lỗi thường gặp (nhân viên chưa gắn `user_id`, NCC thiếu email, scheduler tắt, đang bật chế độ thử).
3. **Workspace "Thông báo":** thẻ số (gửi hôm nay, lỗi 7 ngày, điểm đang bật, đang chế độ thử?), lối tắt tới Điểm / Nhóm / Mẫu / Cài đặt / Nhật ký / thư chưa gửi, liên kết hướng dẫn.
4. **Trang "Thông báo của tôi"** cho mọi người dùng: danh sách điểm mình đang nhận, tự tắt/bật với điểm cho phép (D18).
5. **HDSD** bản Word có ảnh chụp thật, theo tiền lệ HDSD Warehouse Operations.

### 6.6. Chuyển đổi 12 điểm hiện có

- Patch chuyển mọi phần cố định trong `constants.py` (chứng từ, điều kiện, trường tiền/ngày/đối tác, cờ báo cáo tồn, mốc 7/3/1) thành dữ liệu của từng điểm. Ba ô câu chữ gộp vào thân email theo đúng thứ tự đang hiển thị.
- **Không ghi đè** câu chữ và người nhận đã sửa trên site.
- Kiểm chứng tự động: với cùng chứng từ mẫu, email trước và sau chuyển đổi giống nhau về nội dung.
- Sau chuyển đổi, code **không còn** danh sách điểm. `constants.py` chỉ giữ dữ liệu hạt giống cho site mới và danh sách DocType cấm. `hooks.py` không còn nối riêng từng DocType.

---

## 7. Quy tắc nghiệp vụ và yêu cầu phi chức năng

| #   | Quy tắc / Yêu cầu                                                                                                                                                                                                                                                                                                                                   |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| BR1 | Loại tự động chạy nền sau khi lưu; lỗi chỉ ghi nhật ký, không chặn chứng từ. Loại Thủ công báo lỗi thẳng cho người bấm.                                                                                                                                                                                                        |
| BR2 | Chống trùng như D17.                                                                                                                                                                                                                                                                                                                                |
| BR3 | Chỉ*Quản trị thông báo* và System Manager sửa cấu hình. Mọi thay đổi được lưu vết (*Track Changes*).                                                                                                                                                                                                                              |
| BR4 | Mẫu chỉ đọc được dữ liệu chứng từ, biến và khối dựng sẵn; không gọi được hàm hệ thống, không sửa được dữ liệu.                                                                                                                                                                                                          |
| BR5 | Email ra ngoài không có đường dẫn nội bộ, không có khối/mẫu nội bộ.                                                                                                                                                                                                                                                                     |
| NF1 | Kiểm tra "chứng từ có điểm nào không" ≤ 5 ms mỗi lần lưu (cache theo DocType); DocType không có điểm thì không truy vấn thêm.                                                                                                                                                                                                      |
| NF2 | **An toàn mẫu:** Jinja hộp cát nhận **bản sao chỉ đọc** (dict), không nhận Document. **Lỗ hổng hiện tại đã kiểm chứng:** `content.build_context` truyền `doc` là Document, nên mẫu gọi được `doc.db_set(...)`. Phải sửa **trước** khi giao quyền sửa mẫu cho người không phải Dev. |
| NF3 | Trần email mỗi điểm mỗi giờ (5.1); vượt thì tự tạm dừng điểm và báo quản trị.                                                                                                                                                                                                                                                        |
| NF4 | Nhãn, hướng dẫn, thông báo lỗi bằng tiếng Việt có dấu.                                                                                                                                                                                                                                                                                     |
| NF5 | Site không cài`hrms`: người nhận theo phòng ban trả rỗng, không lỗi.                                                                                                                                                                                                                                                                       |
| NF6 | Nhân rộng: hàm cài đặt chạy lại không nhân đôi, không ghi đè; cấu hình xuất/nhập được giữa các site (Data Export/Import chuẩn).                                                                                                                                                                                               |

---

## 8. CR_01 – điều chỉnh NTF-03 bằng cấu hình

CR_01 là yêu cầu thay đổi **bước 3 (NTF-03 – Đơn mua hàng)**. Trên tính năng mới, CR_01 được đáp ứng **bằng cấu hình**, không viết code riêng cho PO:

| Việc                                    | Cấu hình                                                                                                                                                                                                                                                                                     | Đáp ứng           |
| ---------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------- |
| NTF-03 hiện tại (báo kho khi Ghi sổ) | Giữ nguyên,**tắt kênh "Email ra ngoài"**                                                                                                                                                                                                                                            | R2, R8, AC7          |
| Gửi PO cho NCC | Điểm mới **NTF-13 "Đơn mua hàng · Gửi NCC"**: chứng từ *Purchase Order* · thời điểm **Thủ công** · nhãn nút **"Gửi cho NCC"** · trạng thái cho phép: đã Ghi sổ, khác Closed (D29) · ai được bấm: người có quyền sửa PO (D27) | R1, R2, AC1 |
| Người nhận                            | Ngoài: đầu mối liên hệ NCC · CC: người tạo · Trả lời về: người tạo                                                                                                                                                                                                            | R3, AC4, AC6         |
| Tiêu đề                               | `[Miyano] Đơn mua hàng {{ doc.name }} – đề nghị xác nhận đơn và thời gian giao hàng`                                                                                                                                                                                           | §3                  |
| Thân                                    | Lời văn CR_01 mục 3, dùng khối`bang_mat_hang` (cột STT, Mã vật tư, Tên hàng, Số lượng, ĐVT, **Ngày cần hàng**), `dia_chi_giao_hang` (địa chỉ giao hàng), `khoi_phan_hoi`, mẫu dùng chung *"Quy định giao nhận hàng hoá"*, `chu_ky` (người tạo) | R4, R5, R9, AC2, AC3 |
| Chỉnh lời văn CR_01 do bỏ PDF (D23) | "(chi tiết đính kèm và liệt kê dưới đây)" → **"(chi tiết liệt kê dưới đây)"**; "bản Đơn mua hàng (PO) của Miyano (bản in đính kèm email này)" → **"bản Đơn mua hàng (PO) của Miyano (in từ email này)"**. Các câu khác giữ nguyên văn | §3 |
| Đính kèm | **Không đính PDF** (D23). Bảng mặt hàng trong thân email là bản chi tiết đơn | R6: bỏ theo quyết định PO 22/09/2026 |
| Không có link nội bộ                 | Kiểm V4 khi lưu                                                                                                                                                                                                                                                                              | R7                   |
| Lịch sử gửi                           | Nhật ký gửi (mỗi lần bấm một dòng) + mục*Liên kết* trên PO + dòng chỉ báo *"Đã gửi NCC 2 lần – lần cuối 22-09-2026 10:15 bởi … tới …"* + dòng timeline                                                                                                          | AC5                  |

**Phần code mà CR_01 kéo theo** (đều là khả năng dùng chung, không riêng PO): khối `dia_chi_giao_hang` (đọc Address sẵn có — D21b), `chu_ky`, `khoi_phan_hoi`, loại thời điểm Thủ công, CC / Trả lời về, dòng chỉ báo "đã gửi" trên chứng từ nguồn, và hai báo cáo dữ liệu thiếu.

**Dữ liệu phải chuẩn hoá trước** (CR_01 mục 4):

| Dữ liệu                     | Việc cần làm                                                                          | Ai            |
| ----------------------------- | ---------------------------------------------------------------------------------------- | ------------- |
| Địa chỉ "Kho Miyano" | Đủ địa chỉ và `Phone`; **người nhận khai bằng một Liên hệ gắn với địa chỉ đó** (D21b); đặt làm địa chỉ giao mặc định theo cơ chế chuẩn (D28) | Xuân |
| Địa chỉ giao thẳng khách | Người nhận + điện thoại cho từng địa chỉ                                       | Anh Hiếu     |
| Liên hệ NCC                 | Mỗi NCC có Contact chính có email (05c: 0 Contact gắn NCC lúc khảo sát)          | Anh Hiếu     |
| Hồ sơ người tạo PO       | Họ tên, di động trên User                                                           | Từng người |

Hệ thống hỗ trợ: báo cáo *"Địa chỉ giao hàng thiếu người nhận/điện thoại"* và *"Đối tác thiếu email liên hệ"*; hộp xác nhận cảnh báo khi thiếu.

---

## 9. Luồng chính

**Luồng 1 – Quản trị thông báo tạo điểm mới**

```
Workspace Thông báo → [Mới] → chọn "Bắt đầu từ" mẫu
 → Thẻ 2: chứng từ + thời điểm + điều kiện
 → Thẻ 3: người nhận → [Xem trước người nhận]
 → Thẻ 5/6: tiêu đề + thân (Chèn trường / khối / mẫu)
 → [Lưu] (kiểm V1–V8) → [Xem trước email] với chứng từ thật → [Gửi thử cho tôi]
 → Bật "Đang bật" → theo dõi ở Nhật ký
```

**Luồng 2 – Người dùng nghiệp vụ gửi thủ công (vd. CR_01)**

```
PO đã Ghi sổ → [Gửi cho NCC] → Hộp xác nhận (Tới / CC / Tệp / Đã gửi n lần / cảnh báo thiếu dữ liệu / Xem trước)
 → [Gửi] → Email NCC → Nhật ký + dòng chỉ báo trên PO
```

**Luồng 3 – Bắn tự động**

```
Chứng từ lưu / ghi sổ / huỷ / đổi trường / đổi trạng thái duyệt, hoặc job nhắc hạn hằng ngày
 → tra điểm đang bật của DocType (cache) → đánh giá điều kiện → chống trùng
 → job nền: dựng người nhận + nội dung → email nội bộ / in-app / email ngoài → Nhật ký
```

---

## 10. Rủi ro

| #   | Rủi ro                                                                                                          | Ảnh hưởng                                                      | Giảm thiểu                                                                                                    |
| --- | ---------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| RK1 | **Scheduler trên site đang tắt**, Email Queue còn thư tồn (05c Phụ lục E: 2.221 thư `Not Sent`) | Mọi email không đi; bật scheduler là gửi thật cả số tồn | Dọn thư tồn; bật**Chế độ thử** (D16) trước khi bật scheduler. Việc vận hành, cần PO quyết |
| RK3 | Người dùng cấu hình điểm tự động trên chứng từ số lượng lớn                                     | Bão thư                                                         | NF3, cảnh báo khi bật, gửi thử trước                                                                     |
| RK4 | Tính năng linh hoạt thì cấu hình sai dễ hơn                                                              | Gửi nhầm người, nhầm nội dung                               | Kiểm V1–V8, xem trước, chế độ thử, lưu vết thay đổi                                                 |
| RK5 | Chuyển đổi làm đổi thư đang chạy                                                                        | Người nhận thấy thư khác                                    | Test so sánh trước/sau (6.6)                                                                                 |
| RK6 | Khối lượng lớn hơn V0.1 làm CR_01 chậm                                                                    | CR_01 trễ sprint                                                 | Chia giai đoạn (mục 13), CR_01 nằm ở GĐ1                                                                  |
| RK7 | NCC vẫn giao không kèm PO; người tạo chọn sai địa chỉ giao                                             | Kho tra cứu lại; email sai địa chỉ                           | Ngoài hệ thống; địa chỉ mặc định Kho Miyano; hộp xác nhận hiện địa chỉ                          |

---

## 11. Tiêu chí nghiệm thu

### 11.1. Tính năng tự thiết lập

| AC    | Kịch bản                                                                                              | Kết quả mong đợi                                                                                                        |
| ----- | ------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| AC-01 | Tạo điểm:*Purchase Receipt · Ghi sổ · Kho = Kho Miyano · gửi phòng Kế toán*                | Lưu được không cần Dev; khớp điều kiện thì gửi, không khớp thì không                                        |
| AC-02 | Điểm*Trường thay đổi*: Sales Order, `delivery_status`                                         | Chỉ bắn khi trường đó đổi                                                                                           |
| AC-03 | Điểm*Chuyển trạng thái duyệt* trên Payment Entry (Workflow "MVL Duyệt thanh toán")           | Bắn khi vào đúng trạng thái đã chọn                                                                                |
| AC-04 | Điểm*Nhắc theo ngày*: PO, `schedule_date`, mốc `-2, +1`, điều kiện `per_received < 100` | Gửi đúng hai mốc; chạy lại trong ngày không trùng                                                                  |
| AC-05 | Điểm*Thủ công* trên một chứng từ khác PO                                                     | Nút đúng nhãn, chỉ hiện trên chứng từ đó và ở trạng thái cho phép                                           |
| AC-06 | Chèn trường, khối (chọn cột), mẫu dùng chung →*Xem trước email* với chứng từ thật      | Giá trị thật, tiền/ngày định dạng VN, cột đúng thứ tự đã chọn                                               |
| AC-07 | Sửa mẫu dùng chung*Chân email*                                                                    | Mọi điểm dùng mẫu đổi theo ở lần gửi kế tiếp                                                                    |
| AC-08 | Thêm người vào Nhóm người nhận                                                                  | Mọi điểm dùng nhóm gửi thêm người đó                                                                             |
| AC-09 | Gõ sai trường / sai cú pháp / chèn`nut_mo_chung_tu` vào nội dung ngoài                       | Không lưu được, lỗi tiếng Việt có gợi ý (V1–V4)                                                                 |
| AC-10 | Mẫu cố gọi`{{ doc.db_set('status','X') }}` hoặc `{{ frappe }}`                                  | Không thực thi, chứng từ không đổi                                                                                   |
| AC-11 | *Gửi thử cho tôi*                                                                                  | Chỉ người bấm nhận, tiêu đề`[THỬ]`, không có dòng nhật ký nghiệp vụ                                       |
| AC-12 | Bật*Chế độ thử* rồi ghi sổ chứng từ có gửi NCC                                             | Mọi thư về địa chỉ thử, tiêu đề ghi email gốc; NCC không nhận gì                                              |
| AC-13 | Đổi âm báo, giờ nhắc, mốc nhắc, số dòng bảng trong*Cài đặt*                             | Có hiệu lực không cần deploy                                                                                           |
| AC-14 | Người nhận tự tắt một điểm cho phép tắt                                                       | Không nhận điểm đó nữa; điểm không cho tắt vẫn nhận                                                            |
| AC-15 | Nhật ký*Failed* → *Gửi lại*                                                                    | Gửi lại được, có dòng nhật ký mới                                                                                 |
| AC-16 | Một điểm vượt trần email/giờ                                                                     | Tự tạm dừng, quản trị nhận cảnh báo                                                                                 |
| AC-17 | Người không có role*Quản trị thông báo* mở cấu hình                                        | Xem được, không sửa, không tạo                                                                                       |
| AC-18 | Sau chuyển đổi, ghi sổ lại chứng từ mẫu của 12 điểm                                          | Email giống trước (trừ NTF-03 không còn tự gửi NCC)                                                                 |
| AC-19 | Người dùng nghiệp vụ mới chỉ đọc hướng dẫn, tự làm AC-01                                  | Xong ≤ 30 phút, không hỏi Dev (thử với một người thật)                                                            |
| AC-20 | Kiểm code                                                                                              | Không còn tên DocType/trường/điều kiện nghiệp vụ của các điểm trong code chạy (ngoài dữ liệu hạt giống) |

### 11.2. CR_01 (AC1–AC8 của CR_01, cách kiểm)

| AC  | Kiểm thế nào                                                                                                                                                |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| AC1 | PO nháp và PO đã huỷ không có nút; gọi API trực tiếp bị từ chối                                                                                  |
| AC2 | Email tới ≤ 2 phút (scheduler bật); tiêu đề và thân khớp lời văn CR_01 mục 3 (đã chỉnh theo D23); **không có tệp đính kèm**; không có `/app/` hay tên miền nội bộ |
| AC3 | Một PO giao Kho Miyano, một PO giao thẳng khách: người nhận/điện thoại đúng theo địa chỉ; đổi địa chỉ rồi gửi lại thì email đổi theo |
| AC4 | Hai người tạo khác nhau → chữ ký khác nhau; NCC bấm Trả lời → thư về người tạo                                                                |
| AC5 | Gửi hai lần → hai dòng nhật ký, chỉ báo "Đã gửi NCC 2 lần"                                                                                         |
| AC6 | NCC không có email → hộp xác nhận báo rõ, nút Gửi khoá, không có thư trống trong Email Queue                                                    |
| AC7 | Ghi sổ PO → kho nhận NTF-03 như trước; NCC không nhận gì cho tới khi bấm gửi                                                                       |
| AC8 | Chạy thật với ít nhất một NCC (nghiệm thu nghiệp vụ)                                                                                                  |

---

## 12. Giai đoạn và ước lượng sơ bộ

| Giai đoạn                                 | Nội dung                                                                                                                                                                                                       | Dev                         | Ra được                                              |
| ------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------- | ------------------------------------------------------- |
| **GĐ1a – Nền**                     | Cài đặt thông báo; mô hình điểm mới; điều kiện dạng bảng; bộ máy bắt sự kiện chung (Tạo/Ghi sổ/Huỷ/Thủ công/Nhắc theo ngày); ngữ cảnh mẫu an toàn (NF2); chuyển đổi 12 điểm | 4–5 ngày                  | 12 điểm chạy như cũ trên nền mới (AC-18, AC-20) |
| **GĐ1b – Nội dung + CR_01**        | Chèn trường, khối, mẫu dùng chung, nhóm người nhận; CC / Trả lời về; hộp xác nhận Thủ công; khối địa chỉ đọc Address sẵn có; cấu hình NTF-13                                                 | 3–4 ngày                  | CR_01 đạt AC1–AC8                                    |
| **GĐ1c – Tự kiểm + hướng dẫn** | Xem trước email, gửi thử, chế độ thử, kiểm V1–V8, mẫu khởi tạo, workspace, trang hướng dẫn                                                                                                      | 2–3 ngày                  | AC-06…AC-12, AC-19                                     |
| **GĐ2 – Mở rộng**                 | Trường thay đổi, Chuyển trạng thái duyệt, tự tắt nhận, gửi lại từ nhật ký, trần email, thống kê                                                                                              | 3 ngày                     | AC-02, AC-03, AC-14…AC-16                              |
| Test + HDSD                                 | Xuyên suốt; HDSD có ảnh ở cuối                                                                                                                                                                            | 2 ngày                     | –                                                      |
| **Tổng**                             |                                                                                                                                                                                                                 | **~14–17 ngày Dev** | BA ~3 ngày (câu chữ, kịch bản test, HDSD)          |

---

## 13. Quyết định đã chốt (22/09/2026)

| Mã | Câu hỏi | Chốt |
| --- | --- | --- |
| **D23** | Có đính PDF khi gửi PO cho NCC không? | **Không.** PO không có bản PDF gửi NCC. Bỏ R6 của CR_01; lời văn chỉnh như mục 8. Khả năng đính PDF chung vẫn giữ (NTF-07 dùng) |
| **D24** | Hộp thư gửi đi | **Dùng hộp thư mặc định đã cấu hình của site**, không đổi, không thêm cài đặt chọn hộp thư |
| **D25** | Bản tin tổng hợp định kỳ, tự giao việc ToDo | **Bỏ qua**, ngoài phạm vi |
| **D26** | Phân quyền cấu hình theo nhóm chức năng | **Chưa cần.** Một role *Quản trị thông báo* chung |
| **D27** | Ai được bấm "Gửi cho NCC" | Người có quyền sửa PO |
| **D28** | Địa chỉ giao mặc định "Kho Miyano" | Cơ chế chuẩn: địa chỉ công ty có cờ *Is Your Company Address* + *Is Shipping Address* |
| **D29** | PO Closed / Completed | Completed: gửi được; Closed: không |
| **D30** | Giữ nhật ký | Thủ công: vĩnh viễn; tự động: 180 ngày (chỉnh được trong *Cài đặt*) |
| **D31** | Giờ chạy nhắc theo ngày | Một giờ chung cho mọi điểm, mặc định 08:00, chỉnh trong *Cài đặt* |
| **D32** | Thứ tự giao; SMS | Nghiệm thu CR_01 ngay sau GĐ1b; **không làm SMS** |

---

## Phụ lục – Dành cho Dev

### P1. Lệnh

Chạy từ `/home/miyano/frappe-bench`:

```bash
bench --site miyano migrate                       # sau khi sửa DocType JSON / patches.txt
bench build --app erpnext                         # sau khi sửa JS
bench --site miyano clear-cache
bench --site miyano run-tests --module erpnext.supply_notification.tests.test_dispatch
bench --site miyano scheduler status              # KHÔNG dựa vào ps (RK1)
```

### P2. Nơi đặt mã (bám `scripts/file_structure/gate.py`)

```
erpnext/supply_notification/
  constants.py        → chỉ còn dữ liệu hạt giống + danh sách DocType cấm (D19)
  events.py           → bộ máy chung: doc_events["*"], cache điểm theo DocType + loại thời điểm
  conditions.py       → (mới) đánh giá bảng điều kiện, cả bảng con
  blocks.py           → (mới) các khối nội dung dựng sẵn
  context.py          → (mới) ngữ cảnh mẫu chỉ đọc (NF2), biến dựng sẵn
  manual.py           → (mới) API cho nút Thủ công + hộp xác nhận
  preview.py          → (mới) xem trước email, gửi thử
  content.py, dispatch.py, resolver.py, reminders.py, setup.py → sửa theo mô hình mới
  doctype/supply_notification_settings/          → (mới, Single)
  doctype/supply_notification_point/             → dựng lại form 7 thẻ
  doctype/supply_notification_condition/         → (mới, bảng con)
  doctype/supply_notification_block_column/      → (mới, bảng con cột/dòng của khối)
  doctype/supply_notification_recipient_group/   → (mới) + bảng con thành viên
  doctype/supply_notification_snippet/           → (mới) mẫu nội dung dùng chung
  doctype/supply_notification_opt_out/           → (mới, GĐ2) người nhận tự tắt
  workspace/, page/                              → workspace + trang hướng dẫn, "Thông báo của tôi"
  tests/
erpnext/public/js/utils/supply_notification_manual.js   → nút Thủ công trên mọi form
erpnext/patches/v15_0/migrate_supply_notification_v2.py
```

Nối sự kiện: `doc_events["*"]` cho `after_insert` / `on_submit` / `on_cancel` / `on_update` (Trường thay đổi và Chuyển trạng thái duyệt so với `doc.get_doc_before_save()`), thoát sớm khi DocType không có điểm trong cache. Gỡ các dòng `supply_notification` đang nối riêng từng DocType trong `hooks.py`. Cron nhắc hạn chạy hằng giờ và tự so với giờ trong *Cài đặt*, để đổi giờ không cần sửa `hooks.py`.

### P3. Quy ước mã

Python thụt bằng **TAB**, dài tối đa 110, chuỗi nháy kép; chú thích, nhãn và thông báo lỗi bằng tiếng Việt có dấu, theo `erpnext/supply_notification/` hiện có:

```python
def matching_points(doc, event: str) -> list[str]:
	"""Mã các điểm đang bật của DocType này mà chứng từ thoả điều kiện."""
	return [p.code for p in cached_points(doc.doctype, event) if conditions.match(p, doc)]
```

### P4. Chiến lược test

- Đơn vị (`erpnext/supply_notification/tests/`): mỗi toán tử điều kiện (cả bảng con); mỗi khối; V1–V8; hộp cát (AC-10); chế độ thử; chuyển đổi 12 điểm, so sánh email trước/sau (AC-18).
- Tích hợp: ghi sổ, huỷ, đổi trường, đổi trạng thái duyệt trên chứng từ thật; nút Thủ công qua API (AC1, AC5, AC6); nhắc theo ngày với ngày giả lập.
- Kiểm tay trên desk: form 7 thẻ, hộp xác nhận, xem trước, gửi thử, workspace, chỉ báo trên PO.
- Lưu ý môi trường (memory `test-env-quirks`, `verify-without-polluting-the-site`): tạo Custom Field trong test sẽ chốt giao dịch; không thử bằng console có commit trên site thật.

### P5. Ranh giới

- **Luôn:** chạy toàn bộ `erpnext.supply_notification.tests` trước khi báo xong; giữ hành vi 12 điểm; nội dung ngoài qua kiểm V4; test gửi ngoài chạy với chế độ thử.
- **Hỏi trước:** bật scheduler / dọn Email Queue (gửi thư thật); thêm Custom Field vào Address; mọi thao tác git.
- **Không bao giờ:** gửi email thật tới NCC/khách khi test; truyền Document hay `frappe` vào ngữ cảnh mẫu; để lại tên DocType/trường nghiệp vụ của điểm trong code chạy; sửa app `mvl_accounting`; tự tạo nhánh hay commit.

---

## 14. Bản đã build (23/09/2026) — khác biệt so với bản chốt V1.0

Mục này là **nguồn sự thật về hành vi thật của hệ thống**. Chi tiết kỹ thuật xem
`docs/superpowers/specs/2026-09-23-thong-bao-tu-thiet-lap-design.md`.

### 14.1. Đã xây dựng đúng như BA

5 đối tượng cấu hình (Cài đặt · Điểm 7 thẻ · Nhóm người nhận · Mẫu dùng chung · Nhật ký),
7 loại thời điểm, bảng điều kiện 11 toán tử (kể cả bảng con), 7 khối nội dung, 3 kênh,
CC/BCC/Trả lời về, chế độ thử, trần thư mỗi giờ, tự tắt nhận, gửi lại từ nhật ký, xem trước
người nhận / xem trước email / gửi thử, kiểm V1–V8, Workspace, trang hướng dẫn, trang
*Thông báo của tôi*, chuyển đổi 12 điểm cũ, và NTF-13 của CR_01 **hoàn toàn bằng cấu hình**.

Thêm ngoài BA (cần cho việc chuẩn hoá dữ liệu của CR_01 mục 4): hai báo cáo
*Địa chỉ giao hàng thiếu người nhận* và *Đối tác thiếu email liên hệ*.

### 14.2. Sáu điều chỉnh, kèm lý do

| # | Bản chốt V1.0 nói | Bản đã build | Vì sao |
| --- | --- | --- | --- |
| 1 | D21: thêm Custom Field *Người nhận hàng* vào `Address` | **D21b**: đọc Address mà chứng từ đang trỏ tới; người nhận lấy từ Liên hệ | PO chốt 23/09/2026: dữ liệu đã có sẵn, không cần thêm trường vào DocType dùng chung |
| 2 | — | Người nhận **không** lấy từ `Address.address_title` | Đó là nhãn địa chỉ; lấy nhầm thì email ghi "Người nhận: Kho Miyano" và cảnh báo thiếu dữ liệu không bao giờ bật |
| 3 | F11: "Link hiện tên hiển thị thay vì mã khi có" | Chỉ hiện tên khi DocType bật cờ *hiện tiêu đề trong ô Link* | Item đặt tên theo mã, nếu luôn hiện tiêu đề thì cột **Mã vật tư** trong email hoá ra tên hàng |
| 4 | F2: bắn khi trường "thực sự đổi giá trị" | Trống → 0 (và `0` → `0.0`) **không** tính là đổi | Ghi sổ điền 0 vào hàng loạt trường số; so thô sẽ bắn thông báo cho trường chưa ai đụng tới |
| 5 | F6: toán tử so sánh | Điều kiện **ngày** mà dữ liệu không đọc được thì coi là **không thoả** | So chuỗi thay cho ngày: `"chữ" > "2026-01-01"` ra đúng theo thứ tự ký tự — điều kiện hỏng sẽ lặng lẽ bắn nhầm |
| 6 | — | Quy ước mốc gửi (cột *Mốc* trong nhật ký) | Cần để chống gửi trùng và đọc nhật ký |

**Quy ước mốc:** `new` · `submit` · `cancel` · `d7`/`d3`/`d1` (trước hạn, giữ đúng chuỗi của
bản cũ) · `q1`/`q7` (quá hạn) · `change:<trường>:<giá trị mới>` · `wf:<trạng thái duyệt>` ·
`manual` (mỗi lần bấm là một lần gửi, không chống trùng).

### 14.3. Trạng thái vận hành trên site `miyano` (23/09/2026)

| Hạng mục | Trạng thái |
| --- | --- |
| 13 điểm NTF-01…NTF-13 | Đã có, đang bật. **NTF-03 đã tắt kênh gửi NCC** (CR_01 R2/R8/AC7) |
| Scheduler | **Đã bật 23/09/2026** (trước đó tắt từ 22/07), đang chạy đều — in-app và toast hoạt động bình thường |
| Gửi email ra ngoài | **Chưa mở** (quyết định PO 23/09/2026). Site còn công tắc thứ hai `suspend_email_queue = 1`: thư vẫn được xếp vào hàng đợi nhưng chưa ai gửi đi. Mở công tắc này là việc riêng, phải quyết trước khi nghiệm thu CR_01 AC2/AC8 |
| Lưu ý khi mở | Bật scheduler làm job định kỳ của **các app khác** tỉnh dậy theo (đã thấy `[AssetCore] CAPA overdue` gửi tới một Gmail thật). Chế độ thử của tính năng thông báo **không** chặn thư của app khác |
| Chế độ thử | **Tắt**, ô *Email nhận thư thử* để trống — PO điền khi nghiệm thu |
| Vai trò *Quản trị thông báo* | Đã tạo, **chưa gán cho ai** — PO tự gán |
| Kiểm chứng | 199 test tự động xanh; `pre-commit` sạch; kiểm ranh giới code (AC-20) tự động |

### 14.4. Còn lại để nghiệm thu

1. AC-19: một người nghiệp vụ mới đọc trang hướng dẫn rồi tự tạo một điểm ≤ 30 phút.
2. CR_01 AC3 và AC8: chạy thật với ít nhất một NCC; kiểm cả PO giao Kho Miyano và PO giao thẳng khách.
3. Chuẩn hoá dữ liệu bằng hai báo cáo mới (liên hệ NCC có email; địa chỉ giao có người nhận + điện thoại).
4. Điền *Email nhận thư thử* và gán vai trò quản trị.
5. HDSD bản Word có ảnh chụp thật (bản nháp ngắn: `docs/HDSD_ThongBao_TuThietLap_20260923.md`).

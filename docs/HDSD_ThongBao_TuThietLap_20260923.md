# HDSD — Tính năng Thông báo (bản nháp ngắn)

| | |
| --- | --- |
| Hệ thống | Miyano ERP — Workspace **Thông báo** |
| Dành cho | Người có vai trò *Quản trị thông báo* (thiết lập) và mọi người dùng (mục 6) |
| Phiên bản | Nháp 23/09/2026 — chưa có ảnh chụp màn hình |
| Tài liệu gốc | `docs/BA_ThongBao_TuThietLap_CR01_20260922.md` |

> Bản này để anh/chị đọc thử luồng và câu chữ. Bản chính thức (Word, có ảnh chụp thật)
> làm sau khi nghiệm thu giao diện.

---

## 1. Tính năng này làm được gì

Hệ thống tự gửi email và thông báo trong hệ thống khi có việc cần biết: đơn bán vừa ghi sổ,
hoá đơn sắp đến hạn, đơn mua hàng cần gửi nhà cung cấp… **Toàn bộ do người dùng tự thiết lập
trên giao diện** — thêm thông báo mới, đổi người nhận, đổi câu chữ, đổi điều kiện đều không
cần lập trình viên và không cần cài đặt lại hệ thống.

Mỗi loại thông báo là một **Điểm thông báo**. Hệ thống đang có sẵn 13 điểm (NTF-01…NTF-13).

---

## 2. Tạo một thông báo mới — 5 bước

Vào **Thông báo → Điểm thông báo → Mới**.

| Bước | Thẻ | Làm gì |
| --- | --- | --- |
| 1 | **2. Khi nào gửi** | Chọn *Chứng từ nguồn* (ví dụ: Phiếu nhập mua) và *Thời điểm bắn* (ví dụ: Khi ghi sổ) |
| 2 | **2. Khi nào gửi** | Thêm *Điều kiện* nếu chỉ muốn bắn trong một số trường hợp. Ví dụ: `warehouse` `=` `Kho Miyano` |
| 3 | **3. Gửi cho ai** | Chọn phòng ban / người / nhóm. Bấm **Xem trước người nhận** để thấy danh sách thật |
| 4 | **5. Nội dung nội bộ** | Gõ tiêu đề và thân email. Dùng nút **Chèn trường**, **Chèn khối**, **Chèn mẫu dùng chung** |
| 5 | **7. Kiểm tra** | **Lưu → Xem trước email** với một chứng từ thật → **Gửi thử cho tôi**. Xong mới bật **Đang bật** |

**Bảy thời điểm bắn:** Khi tạo mới · Khi ghi sổ · Khi huỷ · Khi một trường đổi giá trị ·
Khi chuyển trạng thái duyệt · Nhắc theo ngày · Khi có người bấm nút.

---

## 3. Soạn nội dung

Thân email soạn như soạn thảo văn bản. Ba thứ chèn được:

| Chèn gì | Ví dụ | Kết quả |
| --- | --- | --- |
| **Trường** của chứng từ | `{{ truong("grand_total") }}` | `12.500.000 ₫` (tự định dạng tiền, ngày `dd-mm-yyyy`) |
| **Khối** dựng sẵn | `{{ bang_mat_hang() }}` | Bảng mặt hàng đầy đủ |
| **Mẫu dùng chung** | `{{ mau("Chân email Miyano") }}` | Đoạn chữ dùng lại ở nhiều điểm |

**Bảy khối:** bảng mặt hàng · khối số liệu · địa chỉ giao hàng · chữ ký · khối phản hồi của
đối tác · liên kết mở chứng từ *(chỉ nội bộ)* · liên kết báo cáo *(chỉ nội bộ)*.

Cột của bảng mặt hàng và dòng của khối số liệu chọn được ở thẻ **5 → Cấu hình khối nội dung**
(ghi `stt` để thêm cột số thứ tự).

**Mẫu dùng chung** (menu *Mẫu nội dung dùng chung*): sửa một chỗ thì mọi điểm dùng mẫu đổi theo
ở lần gửi kế tiếp — ví dụ đổi số hotline, đổi chân email, sửa đoạn quy định giao nhận hàng hoá.

---

## 4. Gửi đơn mua hàng cho nhà cung cấp (CR_01)

1. Mở **Đơn mua hàng đã ghi sổ** → bấm **Gửi cho NCC**.
2. Hộp xác nhận hiện: gửi tới email nào, CC ai, xem trước toàn bộ thư, đã gửi mấy lần trước đó,
   và cảnh báo nếu thiếu dữ liệu (NCC chưa có email, địa chỉ giao chưa có người nhận).
3. Bấm **Gửi**. Mỗi lần bấm là một lần gửi thật và được ghi vào nhật ký.

Lưu ý:
- PO **nháp**, **đã huỷ** hoặc **đã đóng (Closed)** không có nút này.
- NCC **chưa có email liên hệ** thì nút Gửi bị khoá — bổ sung Liên hệ cho NCC trước.
- Người nhận hàng và điện thoại trong thư lấy theo **Địa chỉ giao hàng chọn trên PO**:
  người nhận lấy từ **Liên hệ gắn với địa chỉ đó**, điện thoại lấy từ chính địa chỉ.
  Thiếu thì thư không có dòng người nhận — xem báo cáo ở mục 7.

---

## 5. Theo dõi sau khi bật

- **Nhật ký gửi**: mỗi lần gửi một dòng — gửi cho ai, kênh nào, kết quả, lý do bỏ qua/lỗi.
- Dòng **Failed** có nút **Gửi lại** (dùng sau khi đã sửa dữ liệu).
- Trên form điểm, thẻ **7. Kiểm tra** hiện số lần gửi và tỉ lệ lỗi 30 ngày qua.

---

## 6. Trang *Thông báo của tôi* (cho mọi người dùng)

Xem mình đang nhận những thông báo nào và **tự tắt** những điểm cho phép tắt.
Thông báo bắt buộc xử lý (ví dụ nhắc hạn thanh toán) hiện chữ *bắt buộc* và không tắt được.

---

## 7. Khi thông báo không đến

| Hiện tượng | Nguyên nhân thường gặp | Xử lý |
| --- | --- | --- |
| Chọn phòng ban nhưng không ai nhận | Nhân viên chưa gắn tài khoản người dùng | Bấm *Xem trước người nhận* — hệ thống liệt kê đúng những người bị bỏ |
| NCC/khách không nhận được | Đối tác chưa có email liên hệ | Mở báo cáo **Đối tác thiếu email liên hệ** |
| Thư thiếu dòng người nhận hàng | Địa chỉ giao chưa gắn Liên hệ / chưa có điện thoại | Mở báo cáo **Địa chỉ giao hàng thiếu người nhận** |
| Không thư nào đi | Scheduler tắt, hoặc *Cài đặt thông báo* đang tắt toàn bộ | Báo Dev kiểm tra |
| Thư chỉ về một địa chỉ lạ | Đang bật **Chế độ thử** | Tắt trong *Cài đặt thông báo* khi nghiệm thu xong |
| Một điểm tự tắt | Vượt trần số thư mỗi giờ (mặc định 200) | Xem ô *Lý do tạm dừng* trên điểm, sửa điều kiện rồi bật lại |

---

## 8. Cài đặt chung (*Cài đặt thông báo*)

Bật/tắt toàn bộ tính năng · **Chế độ thử** + email nhận thư thử · tiền tố tiêu đề mặc định ·
chân email nội bộ/ngoài · số dòng tối đa của bảng mặt hàng · âm báo, thời gian hiện thông báo
nổi, khoảng chống dội · **giờ chạy nhắc hằng ngày** · trần số thư mỗi điểm mỗi giờ ·
số ngày giữ nhật ký (tự động 180 ngày, thủ công giữ vĩnh viễn).

Đổi ở đây có hiệu lực ngay, không cần cài đặt lại hệ thống.

---

## 9. Ranh giới — khi nào cần Dev

Tự làm được: thêm điểm trên chứng từ có sẵn, đổi người nhận, đổi câu chữ, thêm/bớt điều kiện,
đổi mốc nhắc, đổi cột bảng mặt hàng, đổi âm báo và giờ nhắc.

Cần Dev: thêm **khối nội dung mới** (ví dụ bảng tuổi nợ, lịch thanh toán), thêm **loại thời điểm
mới**, hoặc nối thông báo sang hệ thống ngoài (SMS, Zalo).

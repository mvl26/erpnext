# Mẫu email gửi hóa đơn điện tử cho khách hàng – Miyano Việt Nam

> Xây dựng dựa trên mẫu email tự động của MISA meInvoice (ví dụ: TCBIO gửi HĐ số 00000439 cho Miyano ngày 28/09/2026).
> Có thể dùng theo 2 cách: (A) dán vào phần **Thiết lập mẫu email** của MISA meInvoice, hoặc (B) gửi thủ công từ Gmail/Outlook.

---

## 1. Mô tả mẫu

| Mục | Nội dung |
|---|---|
| Mục đích | Thông báo cho khách hàng đã phát hành hóa đơn GTGT điện tử và hướng dẫn tra cứu/đối chiếu |
| Bên gửi | CÔNG TY TNHH MIYANO VIỆT NAM |
| Bên nhận | Đầu mối kế toán/mua hàng của khách hàng (bệnh viện, công ty, nhà thuốc…) |
| Thời điểm gửi | Ngay sau khi HĐ được cơ quan thuế cấp mã |
| Ngôn ngữ | Tiếng Việt |
| Đính kèm | File PDF hóa đơn (và XML nếu khách yêu cầu); biên bản bàn giao/đối chiếu công nợ nếu có |
| Phân loại | Email giao dịch – không dùng cho mục đích quảng cáo |

## 2. Các thành phần giữ nguyên từ mẫu gốc

1. Dòng thông báo mở đầu: đơn vị bán thông báo gửi Hóa đơn giá trị gia tăng.
2. Lời chào "Kính gửi".
3. Khối thông tin hóa đơn: **Số – Ngày – Ký hiệu – Mã của cơ quan thuế**.
4. Nút/đường dẫn **Tra cứu** kèm **mã tra cứu**.
5. Câu đề nghị kiểm tra, đối chiếu nội dung hóa đơn.
6. Lời kết "Trân trọng kính chào!" và tên đơn vị.

## 3. Phần Miyano bổ sung so với mẫu gốc

- Câu cảm ơn khách hàng đã hợp tác.
- Khối thông tin giao dịch: số hợp đồng/PO, tổng tiền thanh toán, hạn thanh toán, tài khoản nhận tiền.
- Đầu mối liên hệ (mẫu gốc là email tự động "vui lòng không phản hồi"; mẫu Miyano **cho phép phản hồi**).
- Hướng dẫn xử lý khi có sai sót thông tin trên hóa đơn.

## 4. Biến (placeholder)

| Biến | Ý nghĩa | Ví dụ |
|---|---|---|
| `{{ten_khach_hang}}` | Tên đơn vị mua hàng | Bệnh viện …/Công ty … |
| `{{nguoi_nhan}}` | Người nhận (nếu biết) | Chị/Anh … – Phòng Tài chính kế toán |
| `{{so_hd}}` | Số hóa đơn | 00000xxx |
| `{{ngay_hd}}` | Ngày hóa đơn | dd/mm/yyyy |
| `{{ky_hieu}}` | Ký hiệu hóa đơn | 1C26TTO |
| `{{ma_cqt}}` | Mã của cơ quan thuế | (copy từ MISA) |
| `{{link_tra_cuu}}` | Đường dẫn tra cứu | https://www.meinvoice.vn/tra-cuu |
| `{{ma_tra_cuu}}` | Mã tra cứu | (copy từ MISA) |
| `{{so_hop_dong_po}}` | Số hợp đồng/PO/đơn hàng | HĐ số …/PO số … |
| `{{tong_tien}}` | Tổng tiền thanh toán (đã VAT) | … VNĐ |
| `{{han_thanh_toan}}` | Hạn thanh toán | dd/mm/yyyy |
| `{{nguoi_gui}}` | Người phụ trách gửi | Họ tên – chức danh |
| `{{sdt_nguoi_gui}}` | SĐT đầu mối | … |
| `{{email_nguoi_gui}}` | Email đầu mối | … |

## 5. Tiêu đề email

```
CÔNG TY TNHH MIYANO VIỆT NAM gửi hóa đơn điện tử số {{so_hd}} cho {{ten_khach_hang}}
```

## 6. Nội dung email – Bản đầy đủ (gửi thủ công)

```
Kính gửi: {{nguoi_nhan}} – {{ten_khach_hang}}

CÔNG TY TNHH MIYANO VIỆT NAM xin trân trọng cảm ơn Quý khách hàng đã tin tưởng và hợp tác.

Chúng tôi xin gửi Quý khách Hóa đơn giá trị gia tăng với các thông tin như sau:

  Số:                           {{so_hd}}
  Ngày:                         {{ngay_hd}}
  Ký hiệu:                      {{ky_hieu}}
  Mã của cơ quan thuế:          {{ma_cqt}}
  Theo hợp đồng/đơn hàng:       {{so_hop_dong_po}}
  Tổng tiền thanh toán:         {{tong_tien}}
  Hạn thanh toán:               {{han_thanh_toan}}

Để tra cứu và ký điện tử trên hóa đơn, Quý khách vui lòng nhấn nút [TRA CỨU]
hoặc truy cập đường dẫn {{link_tra_cuu}} và nhập mã số: {{ma_tra_cuu}}

(Hóa đơn dạng PDF được đính kèm email này để Quý khách tiện lưu trữ.)

Quý khách vui lòng kiểm tra, đối chiếu nội dung ghi trên hóa đơn. Nếu có sai sót hoặc cần
điều chỉnh thông tin (tên đơn vị, mã số thuế, địa chỉ…), xin phản hồi lại email này hoặc
liên hệ trực tiếp để chúng tôi xử lý kịp thời.

Trân trọng kính chào!

{{nguoi_gui}}
CÔNG TY TNHH MIYANO VIỆT NAM
ĐT: {{sdt_nguoi_gui}} | Email: {{email_nguoi_gui}}
```

## 7. Nội dung email – Bản ngắn (dán vào mẫu tự động của MISA meInvoice)

```
CÔNG TY TNHH MIYANO VIỆT NAM thông báo gửi Hóa đơn giá trị gia tăng cho Quý khách

Kính gửi: Quý khách

CÔNG TY TNHH MIYANO VIỆT NAM xin gửi cho Quý khách Hóa đơn giá trị gia tăng với các thông tin như sau:
Số: {{so_hd}}
Ngày: {{ngay_hd}}
Ký hiệu: {{ky_hieu}}
Mã của cơ quan thuế: {{ma_cqt}}

Để tra cứu và ký điện tử trên hóa đơn, Quý khách vui lòng nhấn nút: [TRA CỨU]
Hoặc truy cập vào đường dẫn {{link_tra_cuu}} và nhập mã số: {{ma_tra_cuu}}

Quý khách vui lòng kiểm tra, đối chiếu nội dung ghi trên hóa đơn.
Mọi thắc mắc xin liên hệ: {{sdt_nguoi_gui}} – {{email_nguoi_gui}}

Trân trọng kính chào!
CÔNG TY TNHH MIYANO VIỆT NAM
```

> Trong MISA meInvoice, các biến tương ứng là thẻ dữ liệu của hệ thống (số HĐ, ngày, ký hiệu, mã CQT, mã tra cứu…); chỉ cần thay `{{…}}` bằng thẻ tương ứng khi cấu hình.

## 8. Quy tắc sử dụng

1. Chỉ gửi sau khi HĐ đã có **mã của cơ quan thuế** và đã đối chiếu số tiền với hợp đồng/PO/biên bản giao nhận.
2. Kiểm tra tên, MST, địa chỉ khách hàng trước khi gửi; sai thông tin thì xử lý điều chỉnh/thay thế, không gửi tiếp.
3. Gửi đến email nhận hóa đơn đã đăng ký của khách; đồng thời CC kế toán Miyano để lưu vết.
4. Không ghi thông tin nhạy cảm (số tài khoản đầy đủ, mật khẩu…) vào nội dung nếu khách chưa yêu cầu.
5. Lưu email đã gửi và PDF hóa đơn vào thư mục khách hàng theo quy ước đặt tên hiện hành của Miyano.
6. Nếu khách chưa phản hồi sau 3 ngày làm việc, gửi nhắc nhẹ bằng bản dưới đây.

## 9. Mẫu nhắc nhận hóa đơn (tùy chọn)

```
Tiêu đề: [Nhắc] Hóa đơn điện tử số {{so_hd}} của CÔNG TY TNHH MIYANO VIỆT NAM

Kính gửi: {{nguoi_nhan}} – {{ten_khach_hang}}

Miyano Việt Nam đã gửi Quý khách hóa đơn số {{so_hd}} ngày {{ngay_hd}} (ký hiệu {{ky_hieu}}).
Kính nhờ Quý khách xác nhận đã nhận được hóa đơn và đối chiếu nội dung. Nếu chưa nhận được,
xin báo lại để chúng tôi gửi lại ngay.

Trân trọng cảm ơn!
{{nguoi_gui}} – CÔNG TY TNHH MIYANO VIỆT NAM
```

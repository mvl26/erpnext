# Hướng dẫn nhanh cho nhân viên bán hàng — Kiểm giá theo hệ số khách hàng

Áp dụng cho khách có **hệ số giá bán** theo hợp đồng (ví dụ Himedic 1,01; Hoàng Lâm 1,05). Khách không có hệ số: lập đơn như cũ, hệ thống không kiểm.

## Khi lập Sales Order

1. Chọn khách, thêm mặt hàng, bấm **Lưu**.
2. Hệ thống tự tính cho từng dòng. Kết quả của mọi dòng hiện ở bảng **Kiểm giá bán** ngay dưới bảng mặt hàng: giá mua, giá đề xuất, trạng thái giá, chênh lệch. Bấm tên mặt hàng trong bảng để mở dòng xem đủ chi tiết (mục **Kiểm giá bán** của dòng):
   - **NCC dự kiến**: mặc định là NCC mặc định của mặt hàng. Định mua của NCC khác thì đổi ở đây: giá mua và giá đề xuất tính lại ngay, rồi Lưu. Đổi mặt hàng của dòng thì NCC dự kiến tự về NCC mặc định của mặt hàng mới.
   - **Giá mua** và **nguồn**: báo giá đợt của NCC còn hiệu lực; không có thì giá hợp đồng nguyên tắc — dòng giá mua có ô **Nhà cung cấp** đúng là NCC đó (hệ thống nhận theo ô Nhà cung cấp, không theo tên bảng giá).
   - **Giá đề xuất** = giá mua × hệ số, làm tròn đến đồng.
   - **Giá bảng giá KH**: lấy từ **bảng giá mặc định của khách** (trên Khách hàng), không theo ô Bảng giá trên đơn — đổi bảng giá trên đơn không làm mất yêu cầu chấp thuận.
3. Nếu giá trên dòng khác giá đề xuất → cảnh báo màu cam (vẫn lưu được). Muốn dùng đúng giá đề xuất: bấm nút **Áp giá đề xuất** rồi Lưu.

## Trước khi Submit (xác nhận đơn)

| Cảnh báo | Bạn cần làm |
|---|---|
| Giá lệch giá đề xuất, hoặc "Chưa có giá mua để đối soát" | Ghi **Lý do lệch giá** (dưới bảng mặt hàng) |
| "Giá đề xuất khác bảng giá KH" hoặc "Chưa có trong bảng giá KH" trên một dòng (dòng có tích **Chờ khách chấp thuận giá**) | Trên **chính dòng đó**, mục "Khách chấp thuận giá mới": ghi **số văn bản thông báo/đề nghị điều chỉnh giá**, **người đại diện KH đã xác nhận**, **ngày chấp thuận**. Nếu công ty bật "Bắt buộc đính kèm văn bản chấp thuận": đính kèm tệp văn bản ở ô **Tệp văn bản chấp thuận** |

- Chỉ Submit khi đã có văn bản được khách chấp thuận (BA12 D09).
- Hệ thống tự ghi **người nhập** và **thời điểm nhập** trên dòng; kế toán xem lại ở báo cáo đối soát.
- Mặt hàng có giá mới đang trong thời hạn báo trước 7 ngày: bán **đúng giá bảng giá hiện hành** thì không cần lý do, không cần văn bản. Bán giá mới sớm hơn ngày áp dụng → cần văn bản khách chấp thuận; bán giá khác → cần lý do và văn bản.

## Sau khi Submit

- Nếu đơn có giá mới so với bảng giá, hệ thống tự gửi email **Thông báo giá mới** cho người đặt đơn (email liên hệ trên đơn) và khách thấy trên Portal. Xem email ở ô **Thông báo giá mới** hoặc timeline của đơn.
- Đơn chưa có email người đặt → hệ thống nhắc; liên hệ khách để gửi thủ công.
- Đổi giá/thêm dòng bằng **Update Items**:
  - dòng lệch giá đề xuất cần **Lý do lệch giá** (ô này sửa được trên đơn đã Submit; điền rồi bấm **Cập nhật** trước khi Update Items);
  - dòng khác bảng giá **không bị chặn** mà chuyển sang **Chờ khách chấp thuận giá** (đầu đơn có dòng nhắc màu cam). Bấm vào dòng, nhập 3 thông tin rồi bấm **Cập nhật**. Khi đủ, hệ thống tự gửi email thông báo giá mới bổ sung cho khách. **Chưa nhập thì chưa tạo được Phiếu giao hàng / Hóa đơn bán** cho dòng đó (các dòng khác vẫn giao được).
- Trên đơn đã Submit: ô chấp thuận **còn trống** thì điền được; ô **đã điền** chỉ Giám đốc sửa.
- Đổi **NCC dự kiến** trên đơn đã Submit: bấm vào dòng, đổi NCC (bảng Kiểm giá bán tính lại ngay dòng đó) rồi bấm **Cập nhật**. Dòng thành lệch giá đề xuất thì cần **Lý do lệch giá**; không cần khách chấp thuận lại vì giá bán không đổi.

## Không làm được?

- Không sửa được hệ số trên Khách hàng hoặc thông tin chấp thuận đã điền: chỉ Giám đốc được sửa.
- Báo cáo theo dõi: **Doi Soat Gia Mua Gia Ban** (theo từng đơn; lọc "Chỉ dòng chờ khách chấp thuận" để xem đơn còn thiếu văn bản). Menu: **Bán hàng → Kiểm giá bán**.

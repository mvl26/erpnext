# Hướng dẫn nhanh cho nhân viên bán hàng — Kiểm giá theo hệ số khách hàng

Áp dụng cho khách có **hệ số giá bán** theo hợp đồng (ví dụ Himedic 1,01; Hoàng Lâm 1,05). Khách không có hệ số: lập đơn như cũ, hệ thống không kiểm.

## Khi lập Sales Order

1. Chọn khách, thêm mặt hàng, bấm **Lưu**.
2. Hệ thống tự tính cho từng dòng (bấm vào dòng → mục **Kiểm giá bán**):
   - **NCC dự kiến**: mặc định là NCC mặc định của mặt hàng. Định mua của NCC khác thì đổi ở đây rồi Lưu lại.
   - **Giá mua** và **nguồn**: báo giá đợt của NCC còn hiệu lực; không có thì giá hợp đồng nguyên tắc.
   - **Giá đề xuất** = giá mua × hệ số, làm tròn đến đồng.
3. Nếu giá trên dòng khác giá đề xuất → cảnh báo màu cam (vẫn lưu được). Muốn dùng đúng giá đề xuất: bấm nút **Áp giá đề xuất** rồi Lưu.

## Trước khi Submit (xác nhận đơn)

| Cảnh báo | Bạn cần làm |
|---|---|
| Giá lệch giá đề xuất, hoặc "Chưa có giá mua để đối soát" | Ghi **Lý do lệch giá** (dưới bảng mặt hàng) |
| "Giá đề xuất khác bảng giá KH" trên một dòng | Trên **chính dòng đó**, mục "Khách chấp thuận giá mới": ghi **số văn bản thông báo/đề nghị điều chỉnh giá**, **người đại diện KH đã xác nhận**, **ngày chấp thuận** |

Chỉ Submit khi đã có văn bản được khách chấp thuận (BA12 D09).

## Sau khi Submit

- Nếu đơn có giá mới so với bảng giá, hệ thống tự gửi email **Thông báo giá mới** cho người đặt đơn (email liên hệ trên đơn) và khách thấy trên Portal. Xem email ở ô **Thông báo giá mới** hoặc timeline của đơn.
- Đơn chưa có email người đặt → hệ thống nhắc; liên hệ khách để gửi thủ công.
- Đổi giá/thêm dòng bằng **Update Items**: dòng lệch cần Lý do lệch giá; dòng khác bảng giá thì phải Amend đơn để ghi thông tin chấp thuận.

## Không làm được?

- Không sửa được hệ số trên Khách hàng: chỉ Giám đốc được sửa.
- Báo cáo theo dõi: **Doi Soat Gia Mua Gia Ban** (theo từng đơn).

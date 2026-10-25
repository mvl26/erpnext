# Kế hoạch triển khai "Mạng nội bộ Miyano" (Gameplan)

App phụ `gameplan` (nhánh `miyano-v15`, AGPL-3.0) chạy cạnh ERP trên site `miyano`, đường dẫn `/g`.
**Mã nguồn app nằm ở repo riêng `mvl26/gameplan`, nhánh `miyano-v15`, không nằm trong repo erpnext.**
Thư mục này chỉ giữ tài liệu và script cài. Cài lên site bằng `bench get-app` + `install-app`
(xem `miyano_install.sh`), không copy code vào erpnext.

| File | Nội dung |
| --- | --- |
| `README_MIYANO.md` | Các thay đổi của bản Miyano so với Gameplan gốc |
| `miyano_install.sh` | Script IT chạy trên server (tự backup, cài, thiết lập nhóm) |
| `gameplan-miyano-v15-hoan-thien.patch` | Patch lịch sử lên `e33fc3c` (lời chào tiếng Việt, cảnh báo phòng ban thiếu). Đã nằm trong commit `f06479e` của `miyano-v15`, chỉ để tham chiếu |

Các commit mới nhất của `miyano-v15`: `f06479e` (lời chào tiếng Việt, cảnh báo phòng ban),
`a68ae3a` (chỉ HCNS / Ban lãnh đạo / quản trị / người được cấp vai trò *Gameplan Group Creator*
tạo được nhóm; chỉ nhân viên cùng công ty được vào; cấu hình `gameplan_companies` trong `site_config.json`).

## 1. Chuẩn bị

1. Đẩy nhánh `miyano-v15` của repo gameplan lên `mvl26/gameplan` (AGPL-3.0 bắt buộc công khai mã nguồn).
2. Đối chiếu tên Department thật trên ERP với danh sách trong `gameplan/miyano/setup.py` (`GROUPS`).
3. Xác nhận ERP có Email Account gửi mặc định (không có thì bài vẫn đăng, chỉ không có email).

## 2. Cài trên server (IT, user `mvl`, không dùng root)

```bash
bash miyano_install.sh [URL kho hoặc đường dẫn .bundle]
```

Script: backup site kèm tệp → tải app → `install-app` → link giao diện build sẵn → tạo không gian "Miyano Việt Nam" + 5 nhóm + đồng bộ HR → restart.

- Lỗi giữa chừng: `bench --site miyano migrate`, rồi chạy lại `bench --site miyano execute gameplan.miyano.setup.setup_miyano` (chạy lại được nhiều lần).
- Rollback: khôi phục từ backup do bước 1 của script tạo ra.
- Các dòng `CẢNH BÁO` cuối `setup_miyano` là phòng ban chưa gán được: vào menu nhóm → *Quyền đăng bài & thông báo* để gán.

## 3. Nghiệm thu

Thử với tài khoản HCNS, Kế toán và một người phòng Kinh doanh:

- Thấy 5 nhóm, giao diện tiếng Việt.
- HCNS đăng được "Thông báo công ty"; Kế toán không thấy nút "Đăng bài mới" ở nhóm đó.
- Bài mới ở "Thông báo công ty": chuông cho mọi người, email tới hộp thư công ty; @tên nhận email.
- Tệp đính kèm: đồng nghiệp mở được, ẩn danh bị chặn (403).
- Tìm "nghi le" ra "nghỉ lễ"; giờ hiển thị đúng; giao diện điện thoại dùng được.

## 4. Ra mắt và theo dõi

HCNS đăng bài chào mừng, gửi hướng dẫn ngắn cho nhân viên. Theo dõi 1 tuần: lỗi email, nhân viên chưa có `user_id` ở Employee, phản hồi về quyền đăng.

## 5. Rủi ro

| Rủi ro | Giảm thiểu |
| --- | --- |
| Tên phòng ban lệch → nhóm chỉ quản trị đăng được | Cảnh báo của `setup_miyano`, gán tay ở bước 2 |
| Không có email gửi mặc định | Kiểm tra ở bước 1; lỗi chỉ ghi log, không chặn đăng bài |
| Cài hỏng | Backup tự động, có rollback |
| Nâng ERP lên Frappe v16 | Bản này dựa nhánh `main` của Gameplan cho v15, phải làm lại khi nâng |

## 6. Đã kiểm tra trên bench thử (WSL `~/miyano/miyano-dev`, Frappe 15.124)

Đồng bộ HR, chặn đăng theo nhóm, chặn đổi cấu hình quyền, chuông và email xếp hàng, tìm kiếm không dấu, tệp riêng tư, trang `/g`, giao diện điện thoại. **Chưa** kiểm tra trên ERP thật, ảnh dán vào bài, @nhắc tên với người dùng thật.

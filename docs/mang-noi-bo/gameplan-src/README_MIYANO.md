# Mạng nội bộ Miyano — Gameplan bản Miyano (nhánh `miyano-v15`)

Bản sửa đổi của [Frappe Gameplan](https://github.com/frappe/gameplan) (giấy phép **AGPL-3.0**) cho
Công ty TNHH Miyano Việt Nam, chạy trên **Frappe/ERPNext v15** tại erp.miyano.com.vn.

- Gốc: nhánh `main` của frappe/gameplan (commit `30d4f16`, 06/2026) — nhánh duy nhất còn chạy được trên Frappe v15.
  Nhánh `develop` mới nhất của Gameplan chỉ hỗ trợ Frappe v16.
- Đường dẫn ứng dụng: `/g`

## Thay đổi so với bản gốc

### 1. Việt hóa
- Toàn bộ giao diện (~70 tệp .vue/.js), thời gian tương đối ("2 giờ trước") bằng dayjs `vi`.
- Chuỗi bên trong thư viện frappe-ui (thanh công cụ soạn thảo, hộp chèn ảnh/liên kết/video, tìm kiếm) được
  Việt hóa lúc build bằng plugin `frontend/miyanoFrappeUiVi.js` (không sửa node_modules).
- Thông báo lỗi phía máy chủ, email mời, tên ứng dụng "Mạng nội bộ".
- Thuật ngữ: Team = **Không gian**, Project = **Nhóm**, Discussion = **Bài đăng**.

### 2. Quyền đăng bài theo nhóm (`gameplan/miyano/permissions.py`)
- Trường mới trên GP Project: *Chỉ người được chỉ định mới được đăng bài* + bảng *Người / phòng ban được đăng bài*
  (bảng con `GP Project Poster`; trường Phòng ban tự thành Link tới Department nếu site có module HR).
- Mọi người vẫn đọc và bình luận mọi nhóm. Quản trị (System Manager, Gameplan Admin) luôn được đăng.
- Máy chủ chặn đăng bài trái quyền; giao diện ẩn nút "Đăng bài mới" ở nhóm không có quyền.
- Chỉ quản trị viên được đổi cấu hình này (menu nhóm → *Quyền đăng bài & thông báo* mở form trên ERP).

### 3. Đồng bộ nhân sự từ HR (`gameplan/miyano/hr_sync.py`)
- Nhân viên **Active** có `user_id` → tự được vai trò *Gameplan Member*, hồ sơ, và vào không gian mặc định.
- Nhân viên nghỉ việc → gỡ vai trò và khỏi không gian.
- Chạy khi lưu hồ sơ Employee và hằng ngày (scheduler). Chạy tay:
  `bench --site miyano execute gameplan.miyano.hr_sync.sync_all`

### 4. Thông báo bài mới + email (`gameplan/miyano/notifications.py`)
- Loại thông báo mới *New Post*. Nhóm bật *Báo chuông cho toàn công ty* → mọi người nhận; nhóm khác → người đang theo dõi nhóm.
- Email: khi được **nhắc tên** (@tên) và khi có bài mới ở nhóm bật *Gửi email* (mặc định: nhóm Thông báo công ty).
  Email gửi qua hộp thư gửi mặc định của ERP; lỗi email không chặn việc đăng bài.

### 5. Ảnh, tệp đính kèm, tìm kiếm
- Nút **Đính kèm** (PDF, Word, Excel…, tối đa 25 MB) trong soạn bài và bình luận; tệp lưu **riêng tư**,
  chỉ người đăng nhập có quyền đọc bài mới mở được (`gameplan/miyano/files.py`).
- Ảnh dán/chèn vào bài (bản gốc lưu base64 trong database) được tách thành tệp riêng tư và thu nhỏ còn cạnh dài 1920px.
- **Tìm kiếm dự phòng bằng SQL** khi Redis chưa có module RediSearch: không phân biệt hoa thường và dấu
  ("nghi le" tìm ra "nghỉ lễ"), tìm cả trong bình luận (`gameplan/miyano/search.py`). Có RediSearch thì dùng như bản gốc.

### 6. Vận hành trên máy chủ yếu RAM
- Giao diện **đã build sẵn** và commit trong `gameplan/public/frontend` + `gameplan/www/g.html`.
- Script `build` ở package.json gốc đổi tên thành `build:frontend` để `bench build`/`bench update`
  **không** tự build lại giao diện trên máy chủ. Bỏ phụ thuộc cypress.

## Cài đặt trên máy chủ
Xem `miyano_install.sh` (sao lưu → get-app → install-app → liên kết assets → thiết lập nhóm & đồng bộ HR → restart).

## Sửa giao diện về sau (trên máy dev)
```bash
cd apps/gameplan && yarn build:frontend   # cần Node 18+
git add gameplan/public/frontend gameplan/www/g.html && git commit
```

## Giấy phép
AGPL-3.0 (giữ nguyên tệp LICENSE). Vì Mạng nội bộ chạy qua mạng cho người dùng, mã nguồn bản sửa đổi phải
được cung cấp cho họ: menu tài khoản có mục *Mã nguồn (AGPL-3.0)* trỏ tới
`https://github.com/mvl26/gameplan/tree/miyano-v15` — cần đẩy nhánh này lên kho đó.

# Kế hoạch — Hóa đơn điện tử Fast ↔ Miyano

Nguồn: `docs/fast_miyano/SPEC_FAST_EINVOICE_ERPNEXT_v2.md` (v2.0, 07/08/2026).

## Quyết định đã chốt (người dùng, 2026-08-07)

1. **Vị trí code:** dựng thẳng trong `erpnext`, module mới **`einvoice`**
   (`erpnext/einvoice/`), DocType và hàm xử lý nằm trong module đó.
   Ghi đè chỉ dẫn "bench new-app miyano_einvoice" của spec Giai đoạn 2 —
   theo CLAUDE.md, HĐĐT thuộc về erpnext core.
2. **Luồng HĐĐT cũ (Task 40–44, SI-driven, tự phát hành khi submit):** **xóa hẳn.**
   An toàn: kiểm tra site `miyano` ngày 2026-08-07 cho thấy **0 bản ghi**
   `Vietnam E Invoice Log` và **0** Sales Invoice có `vn_einvoice_number` →
   không mất dữ liệu nghiệp vụ.
3. **J-3 gộp nhiều Delivery Note:** **không.** 1 DN = 1 hóa đơn,
   `delivery_note` là Link như bảng C2.1.

Mặc định lấy theo khuyến nghị của spec cho các câu hỏi mở còn lại:
J-1 `require_customer_approval` = **bật**; J-2 gửi email hóa đơn chính thức =
**ERP tự gửi** (method 700 làm dự phòng, vẫn dựng); J-4 phiếu xuất kho kiêm vận
chuyển nội bộ (319/328/358/338) = **ngoài phạm vi v2.0**; J-5 gán role là việc
quản trị, không phải code — dựng đủ 2 role để giao sau.

## Nguyên tắc thi công

- **TDD**: mỗi task viết test đỏ trước. Toàn bộ test dùng **transport giả**
  (monkeypatch lớp gọi HTTP) — **không test nào chạm mạng thật**.
- Mỗi task = 1 commit, chạy được, không làm vỡ suite đang xanh.
- Ba nguyên tắc Phần A (ghi DocType trước+sau khi gọi API · mọi hành động phải
  có xác nhận người dùng · ghi log đủ request/response) áp cho **mọi** task,
  không chỉ task nào nhắc tới.

## Danh sách task

### Giai đoạn 0 — Nền móng dữ liệu

- [x] **T1 — Module `einvoice` + gỡ luồng HĐĐT cũ.**
  Tạo `erpnext/einvoice/` (+ `modules.txt`). Xóa `regional/vietnam/e_invoice.py`,
  `e_invoice_providers/`, `test_e_invoice.py`, DocType `Vietnam E Invoice Log`,
  hook `on_si_submit`, và các custom field `vn_einvoice_*` (Company + Sales
  Invoice) trong `regional/vietnam/setup.py`. Patch dọn DocType + custom field
  trên site đang chạy.
  - Nghiệm thu: `bench migrate` sạch; suite VN còn lại xanh; báo cáo
    `to_khai_thue_gtgt_01` vẫn chạy (đã có guard `meta.has_field`).
  - Files: `erpnext/einvoice/`, `modules.txt`, `regional/vietnam/setup.py`,
    `hooks.py`, `patches.txt`, patch mới. Deps: không.

- [x] **T2 — DocType `Fast eInvoice Settings` (Single).** 18 trường mục C1,
  quản lý token (24h), cờ `is_test_mode`.
  - Nghiệm thu: lưu được cấu hình; thiếu trường bắt buộc → chặn; `api_password`
    là Password (không lộ khi đọc doc). Deps: T1.

- [x] **T3 — DocType `Fast EInvoice Line` (child).** 14 trường mục C3, đúng thứ
  tự cột `structure.detail`. Deps: T1.

- [x] **T4 — DocType `Fast EInvoice Document` (cha).** Nhóm C2.1–C2.4, naming
  `FEI-.YYYY.-.#####`, 12 trạng thái + `Lỗi`, khóa sửa bằng
  `read_only_depends_on` theo `status` (`is_submittable = 0`).
  - Nghiệm thu: tạo được bản ghi ở trạng thái 01; trạng thái ≥05 khóa sửa;
    `fast_key` read-only sau khi tạo. Deps: T2, T3.

- [x] **T5 — DocType `Fast EInvoice Log`.** 10 trường mục C4 + job dọn bản ghi
  cũ hơn 24 tháng. Deps: T1.

- [x] **T6 — Custom field Delivery Note (C5) + 2 Role.**
  `fast_einvoice`, `fast_invoice_no`, `fast_einvoice_status`, `fast_key_search`;
  Role **Kế toán HĐĐT** và **Kế toán trưởng HĐĐT** (nút cấp 3 chỉ hiện với role
  thứ hai). Deps: T4.

### Giai đoạn 1 — Tầng giao tiếp Fast

- [x] **T7 — `fast_client.py`: SOAP + token.** Dựng envelope, escape `&<>`,
  base64 UTF-8, `CheckKey`/`GetKey`, tự lấy lại token khi hết hạn rồi thử lại 1
  lần. Deps: T2.

- [x] **T8 — `ExcuteCommand` + ghi log + ánh xạ lỗi.** Bọc mọi lời gọi theo trình
  tự A1 (ghi log → commit → gọi → ghi response → commit); che password/token
  trong `request_json`; Message là PDF base64 thì chỉ ghi độ dài; ánh xạ ~20 mã
  lỗi Phần G sang thông báo tiếng Việt + hành động gợi ý. Deps: T5, T7.

### Giai đoạn 2 — Đóng gói & kiểm tra dữ liệu

- [x] **T9 — `payload.py`.** Dựng `structure.master`/`structure.detail` đúng
  Phần I; bỏ hẳn thẻ không dùng khỏi structure; số gửi dạng number; đọc tiền
  bằng chữ theo loại tiền (đồng / đô la Mỹ / Euro). Deps: T4.

- [ ] **T10 — `validation.py`: 16 quy tắc Phần F.** Phân mức chặn/cảnh báo, trả
  danh sách lỗi kèm tên trường để giao diện nhảy tới. Deps: T9.

### Giai đoạn 3 — Vòng nháp & duyệt khách

- [ ] **T11 — Nút 1 + Nút 2.** Tạo FEI từ DN (sinh `fast_key` **một lần**, ghi
  ngược `delivery_note.fast_einvoice`); đồng bộ lại từ DN (`revision_count`).
  Deps: T10.
- [ ] **T12 — Nút 3 — xem bản nháp PDF** (`action=600`, `method=310`) → lưu
  `draft_pdf`, `status = 02`; lỗi thì giữ nguyên trạng thái. Deps: T8, T11.
- [ ] **T13 — Nút 4/5/6 + 2 Email Template.** Gửi nháp cho khách, ghi nhận ý
  kiến (nối lịch sử, không ghi đè), khách đã duyệt. Mẫu email **bắt buộc** có
  dòng "bản nháp — CHƯA CÓ GIÁ TRỊ PHÁP LÝ". Deps: T12.

### Giai đoạn 4 — Phát hành & sau phát hành

- [ ] **T14 — Nút 7 PHÁT HÀNH.** Lock chống bấm đúp, validate lại phía server,
  **tiền kiểm 370** trước khi phát hành, commit trước khi gọi API, xử lý đủ 3
  nhánh 7a thành công / 7b lỗi / 7c timeout → "Cần đối soát" (tuyệt đối không tự
  phát hành lại). Deps: T13.
- [ ] **T15 — Nút 8/9 — PDF chính thức (380) / chuyển đổi (385).** Chặn gọi lại
  trong 5 giây. Deps: T14.
- [ ] **T16 — Nút 10 — gửi hóa đơn chính thức.** Phương án A (ERP gửi, mặc định)
  + phương án B (`method=700`). Deps: T15.
- [ ] **T17 — Nút 11/12 + job nền CQT.** `method=8200` cập nhật trạng thái CQT
  (3 → status 08, 4 → status 09 + cảnh báo); `method=370` đối soát, lệch thì hỏi
  trước khi ghi đè; job 20 phút quét các hóa đơn "Chờ CQT". Deps: T14.

### Giai đoạn 5 — Điều chỉnh / thay thế / hủy

- [ ] **T18 — Nút 13a/13b — điều chỉnh (320) / thay thế (350).** Bản ghi mới sao
  từ gốc, đi lại vòng đời từ 01; payload thêm `originalInvoice` +
  `adjustmentType`; gốc chuyển 10/11; liên kết 2 chiều. Deps: T17.
- [ ] **T19 — Nút 13c — hủy nội bộ (330).** Chỉ cho khi status 09; mở khóa DN để
  lập hóa đơn mới nhưng **giữ** liên kết lịch sử. Deps: T18.
- [ ] **T20 — Report "Đối soát hóa đơn điện tử".** DN chưa xuất hóa đơn · hóa
  đơn chờ CQT quá 24h · hóa đơn lỗi. Deps: T17.

### Giai đoạn 6 — Giao diện & hoàn thiện

- [ ] **T21 — Client script `Fast EInvoice Document`.** Banner môi trường
  (vàng TEST / đỏ THẬT), bảng kết quả validate, 13 nút hiện theo trạng thái bảng
  B2, dialog xác nhận cấp 1/2/3 (cấp 3 gõ đúng `PHAT HANH` / `HUY`). Deps: T19.
- [ ] **T22 — Client script `Delivery Note`.** Nút "Tạo hóa đơn điện tử" +
  hiển thị trạng thái HĐĐT. Deps: T21.
- [ ] **T23 — Nối bảng kê bán ra / tờ khai 01/GTGT sang nguồn số mới.** Thay chỗ
  đọc `vn_einvoice_number`/`vn_einvoice_symbol` (đã xóa ở T1) bằng số hóa đơn
  Fast. Deps: T14.
- [ ] **T24 — Tài liệu vận hành + 12 kịch bản test Giai đoạn 6.** Deps: T23.

## Cổng chặn ngoài phạm vi code

Các mục Giai đoạn 0 của spec do người dùng/Fast làm, code không thay được:

- Fast xác nhận đã bật chế độ **không mã hóa RSA** cho DN 008254.
- Fast xác nhận **chứng thư số HSM** + tờ khai HĐĐT đã được CQT chấp nhận.
- Cấp **user API riêng cho ERP** và **tài khoản môi trường TEST** (`:9000`).
  → Chưa có thì T7–T19 vẫn dựng và test được bằng transport giả, nhưng
  **không thể chạy 12 kịch bản end-to-end thật** của Giai đoạn 6.
- Xử lý hóa đơn test `TESTPM260807A` đã lỡ phát hành trên hệ thống thật —
  kế toán trưởng quyết điều chỉnh hay thay thế.
- Gán role "Kế toán trưởng HĐĐT" (ai được quyền phát hành).

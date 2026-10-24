# Hướng dẫn test thủ công — Đợt 2: Báo trước khi đổi giá bán (YC4)

| Mục | Nội dung |
|---|---|
| Phạm vi | YC4 — spec `docs/superpowers/specs/2026-10-21-kiem-gia-ban-bao-gia-doi-soat-design.md`, mục 6.2, 14, 15; phần kiểm giá theo hệ số xem `docs/HDKT_BA12_Kiem_gia_ban.md` |
| Site test | `erpnext.localhost` — `http://127.0.0.1:8000`. **Không test trên `miyano`.** |
| Nhánh | `feat/bao-truoc-doi-gia-himedic` |
| Email | Site test bật `mute_emails`: email thông báo được **lưu** (Communication) nhưng **không gửi** ra ngoài. Email nhận demo: `himedic.demo@example.com` |

Quy tắc để đối chiếu khi test:

- "DEMO Bảng giá Himedic" có **Báo trước khi đổi giá** (7 ngày). Giá mới phải vào **bảng giá chờ** "DEMO Bảng giá Himedic - Chờ báo" trước. Người nhập giá mới vào bảng chờ là người dùng — hệ thống **không** tự tạo nháp từ báo giá NCC (BA12 D09: bảng giá khách hàng cập nhật thủ công).
- Chỉ **Giám đốc** (vai trò ở Selling Settings → "Vai trò được sửa hệ số giá bán", demo: `Sales Manager`, vai trò có sẵn) được **Gửi thông báo đổi giá** và đổi cài đặt báo trước.
- Gửi: một email gom mọi giá chờ; giá chuyển sang bảng giá chính; giá cũ giữ nguyên. Ngày hiệu lực **trước ngày gửi → bị chặn**; **dưới 7 ngày → cảnh báo + đánh dấu Báo gấp**, vẫn gửi được.
- Trên bảng giá chính: không thêm thẳng, không sửa giá/ngày, không xóa.

## 0. Chuẩn bị

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| 0.1 | Bench đang chạy. Ở `sites` chạy:<br>`../env/bin/python ../apps/erpnext/scripts/demo_gia_ban_doi_soat.py --site erpnext.localhost` | Chạy xong không lỗi, in ra 4 SO demo | ☐ |
| 0.2 | Mở Price List **DEMO Bảng giá Himedic** | Mục "Báo trước khi đổi giá": đã tích, 7 ngày, Bảng giá chờ = DEMO Bảng giá Himedic - Chờ báo, email himedic.demo@example.com | ☐ |
| 0.3 | Bấm **Giá chờ gửi** | Danh sách Item Price của bảng giá chờ: 1 dòng DEMO-VT-02 52.000, áp từ D+5, trạng thái Chờ gửi | ☐ |

Giá trên DEMO Bảng giá Himedic: VT-01 120.000, VT-02 50.500, VT-05 10.100 (theo Cái).
Người dùng mẫu (Impersonate): `demo.giamdoc@example.com` (Giám đốc), `demo.nhanvien@example.com` (nhân viên).

Gặp lỗi thiếu tài khoản kho khi Nộp chứng từ kho, hoặc lỗi máy chủ khi lưu hồ sơ Công ty: xem mục **11. Xử lý sự cố thường gặp** trong `docs/HDKT_BA12_Kiem_gia_ban.md`.

## H. Cài đặt bảng giá và chặn sửa

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| H1 | `demo.nhanvien` mở DEMO Bảng giá Himedic → bỏ tích "Báo trước khi đổi giá" → Lưu | Bị chặn: "Chỉ Giám đốc được đổi cài đặt báo trước…" | ☐ |
| H2 | `demo.giamdoc` đổi Số ngày báo trước = 10 → Lưu; đổi lại 7 → Lưu | Lưu được | ☐ |
| H3 | Item Price → New: bảng giá **DEMO Bảng giá Himedic**, DEMO-VT-05, 10.500, Valid From D+7 → Lưu | Bị chặn: "thêm giá mới vào bảng giá chờ … rồi Giám đốc Gửi thông báo đổi giá" (T3) | ☐ |
| H4 | Mở dòng giá DEMO-VT-05 10.100 của DEMO Bảng giá Himedic → sửa giá thành 10.500 → Lưu | Bị chặn: "Không sửa được giá đã có…" (T2). Tương tự khi sửa Valid From / Valid Upto | ☐ |
| H5 | `demo.nhanvien` xóa dòng giá đó | Bị chặn: "Không xóa giá trên bảng giá …" | ☐ |
| H6 | Item Price → New: bảng giá **DEMO Bảng giá Himedic - Chờ báo**, DEMO-VT-05, 10.500, Valid From hôm nay → Lưu | Lưu được; mục "Thông báo đổi giá": trạng thái **Chờ gửi** | ☐ |
| H7 | Sửa giá dòng H6 = 10.600 → Lưu; rồi xóa dòng | Đều được (nháp tự do sửa/xóa) | ☐ |
| H8 | Tạo Sales Order cho DEMO-Himedic, chọn Price List = **DEMO Bảng giá Himedic - Chờ báo** → Lưu | Bị chặn: "… là bảng giá chờ (giá chưa báo cho khách). Dùng bảng giá DEMO Bảng giá Himedic" (T4) | ☐ |
| H9 | Sửa giá dòng của bảng giá **mua** (vd. DEMO Mua - Hùng Minh) | Sửa bình thường — bảng giá mua không bị ảnh hưởng | ☐ |

## K. Trạng thái "Đang trong thời hạn báo giá" trên SO

**Làm trước mục I** (khi nháp VT-02 52.000 còn ở bảng chờ).

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| K1 | Thêm giá HĐ nguyên tắc mới cho VT-02: Item Price bảng **DEMO Mua - Hùng Minh**, Supplier DEMO-Hùng Minh, 51.485, Valid From hôm nay → Lưu | Lưu được | ☐ |
| K2 | Tạo SO nháp DEMO-Himedic chỉ có VT-02 giá 50.500 → Lưu | Dòng VT-02: giá đề xuất 52.000 (51.485 × 1,01), trạng thái **Đang trong thời hạn báo giá**, chênh −1.500, ghi chú "…; giá mới 52000 từ … (chờ gửi thông báo)"; **Đề xuất khác bảng giá** không tích. Không có trong cảnh báo lệch (T9) | ☐ |
| K3 | `demo.nhanvien` Submit SO K2 | Submit được — không cần lý do, không cần 3 thông tin chấp thuận (giá mới đang trong luồng báo trước) | ☐ |
| K4 | SO nháp thứ hai của DEMO-Himedic (VT-01 125.000) | VT-01 vẫn **Cao hơn** — không có giá mới chờ báo nên vẫn là lệch | ☐ |
| K5 | SO nháp DEMO-Himedic VT-02 giá **52.000** (bán giá mới trước ngày áp) → Lưu | **Không** phải "Đang trong thời hạn báo giá": trạng thái Khớp, **Đề xuất khác bảng giá** có tích → Submit cần 3 thông tin chấp thuận (Q7, PO 22/10) | ☐ |
| K6 | SO nháp DEMO-Himedic VT-02 giá **51.000** → Lưu | Trạng thái **Thấp hơn**, ghi chú "… nhưng giá bán khác giá bảng giá hiện hành nên vẫn tính là lệch" → Submit cần lý do và 3 thông tin (Q7) | ☐ |

## I. Gửi thông báo đổi giá

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| I1 | `demo.nhanvien` mở DEMO Bảng giá Himedic | **Không** thấy nút "Gửi thông báo đổi giá" (chỉ thấy "Giá chờ gửi") | ☐ |
| I2 | Thêm nháp vào bảng chờ: DEMO-VT-05 10.200, Valid From = **hôm qua** | Lưu được (nháp) | ☐ |
| I3 | `demo.giamdoc` mở DEMO Bảng giá Himedic → **Gửi thông báo đổi giá** → Xác nhận | Bị chặn: "Sửa ngày hiệu lực (không được trước hôm nay) cho: DEMO-VT-05 …". **Không** dòng nào bị chuyển (VT-02 vẫn ở bảng chờ) (D2-4) | ☐ |
| I4 | Sửa Valid From của nháp VT-05 = **D+7** → Lưu. Gửi lại | Gửi được. Cảnh báo cam "Báo gấp (dưới 7 ngày)": DEMO-VT-02 áp từ D+5, **báo trước 5 ngày, thiếu 2 ngày** (T1). VT-05 không nằm trong danh sách báo gấp | ☐ |
| I5 | Mở dòng VT-02 52.000 (giờ ở **DEMO Bảng giá Himedic**) → mục Thông báo đổi giá | Trạng thái **Đã gửi**, Ngày gửi = hôm nay, Số ngày báo trước = 5, **Báo gấp** tích, Email thông báo có link, Người gửi = demo.giamdoc | ☐ |
| I6 | Bấm link Email thông báo (Communication) | Tiêu đề "Thông báo thay đổi giá - DEMO Bảng giá Himedic"; người nhận himedic.demo@example.com; bảng: mã hàng, giá hiện tại (VT-02: 50.500; VT-05: 10.100), giá mới, ngày áp dụng | ☐ |
| I7 | Mở DEMO Bảng giá Himedic → timeline cuối form | Thấy email vừa gửi | ☐ |
| I8 | Dòng giá cũ VT-02 50.500 | **Vẫn còn**, không đổi (T1b) | ☐ |
| I9 | Bảng chờ sau khi gửi | Trống | ☐ |
| I10 | Sửa giá dòng VT-02 52.000 vừa gửi | Bị chặn (giá đã báo không sửa được) | ☐ |
| I11 | Nhập **Ngày khách xác nhận** (hôm nay) + đính kèm file vào dòng VT-02 → Lưu (`demo.nhanvien` cũng làm được) | Lưu được; trạng thái → **Đã xác nhận** (T7). Xóa ngày xác nhận → về **Đã gửi** | ☐ |
| I12 | Nhập "Lý do báo gấp" cho dòng VT-02 → Lưu | Lưu được | ☐ |
| I13 | Tạo SO DEMO-Himedic ngày **D+4** có VT-02 → xem giá gợi ý | 50.500 (giá cũ). Ngày **D+5** → 52.000 (giá theo ngày SO — D4-4, T5) | ☐ |
| I14 | Gửi khi bảng chờ trống | Báo "Bảng giá chờ … không có giá nào để gửi" | ☐ |
| I15 | Xóa email nhận trên bảng giá (Giám đốc) rồi gửi | Báo "chưa có Email nhận thông báo đổi giá". Điền lại email | ☐ |
| I16 | Thêm nháp VT-02 với **cùng Valid From** với một giá đã có trên bảng giá chính → Gửi | Báo "đã có giá cùng ngày hiệu lực …"; không dòng nào bị chuyển | ☐ |
| I17 | Tạo lại SO nháp như K2 → Lưu | Vẫn "Đang trong thời hạn báo giá", ghi chú "(đã báo)" | ☐ |

## L. Nhắc việc

Hai điểm nhắc trong **Supply Notification Point** (tự tạo khi migrate):

| Mã | Tên | Khi nào |
|---|---|---|
| NTF-14 | Đổi giá bán · Nhắc xin khách xác nhận | Ngày gửi + 2, trạng thái vẫn Đã gửi (chưa xác nhận) |
| NTF-15 | Đổi giá bán · Giá mới sắp áp dụng | Ngày hiệu lực − 1, giá đã gửi / đã xác nhận |

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| L1 | Mở Supply Notification Point NTF-14, NTF-15 | Đang bật; Item Price; ngày `ngay_gui_thong_bao` +2 / `valid_from` −1; người nhận: trường **Người gửi thông báo** (NTF-15 thêm P. Kinh doanh, P. Kế toán) | ☐ |
| L2 | Trên NTF-15 dùng **Xem trước** với một dòng giá đã gửi (vd. VT-02 ở I5) | Thấy nội dung và người nhận là demo.giamdoc | ☐ |
| L3 | (Kiểm tự động — test `TestNhacViec`) ngày gửi + 2 chưa xác nhận → nhắc người gửi; đã xác nhận → không nhắc; nháp chờ gửi → không nhắc | Xem mục Test tự động | ☐ |

Nhắc tự động chạy theo giờ trong Cài đặt thông báo (scheduler hằng giờ) và chỉ khi **Supply Notification Settings** đang bật.

## M. Báo cáo "Thong Bao Doi Gia Bao Gap"

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| M1 | Mở báo cáo (mặc định "Chỉ dòng báo gấp") | VT-02 52.000: báo trước 5, **thiếu 2**, Báo gấp, trạng thái, ngày xác nhận, người gửi, link email (T12) | ☐ |
| M2 | Bỏ tích "Chỉ dòng báo gấp" | Có thêm VT-05 (đủ 7 ngày) | ☐ |
| M3 | Tích "Chỉ dòng khách chưa xác nhận" | Dòng đã nhập Ngày khách xác nhận biến mất | ☐ |
| M4 | Submit một SO DEMO-Himedic ngày ≥ D+5 có VT-02 → chạy lại báo cáo | Cột "Số SO đã bán theo giá" của VT-02 tăng 1 | ☐ |

## Test tự động

`erpnext/selling/tests/test_kiem_gia_bao_truoc.py` — 35 test (cài đặt bảng giá, chặn sửa, gửi thông báo, trạng thái đang trong thời hạn báo giá, nhắc việc, báo cáo). Chạy:

```bash
cd ~/frappe-bench/sites
../env/bin/python ../apps/erpnext/scripts/chay_test.py --site erpnext.localhost erpnext.selling.tests.test_kiem_gia_bao_truoc
```

## Thay đổi so với bản trước (theo BA12)

- **Bỏ mục J** (Submit báo giá NCC tự tạo nháp giá Himedic): BA12 D09 — bảng giá khách hàng cập nhật thủ công; báo giá NCC nay chỉ là nguồn "Báo giá đợt" để tính giá đề xuất (D07), không ghi vào bảng giá nào.
- Dòng "Đang trong thời hạn báo giá" không cần lý do và **không** bị đòi 3 thông tin chấp thuận R05 — **chỉ khi bán đúng giá bảng giá hiện hành** (Q7, PO chốt 22/10/2026). Bán giá mới sớm hoặc một giá khác là lệch bình thường (K5, K6).
- Trường trên Price List / Item Price là Custom Field (BA12 "không sửa core"); vị trí và nhãn trên form không đổi.

# Hướng dẫn test thủ công — Đợt 2: Báo trước khi đổi giá bán (YC4)

| Mục | Nội dung |
|---|---|
| Phạm vi | Đợt 2 (bước 2.1–2.8) — spec `docs/superpowers/specs/2026-10-21-kiem-gia-ban-bao-gia-doi-soat-design.md`, mục 6.2 và 14 |
| Site test | `erpnext.localhost` — `http://127.0.0.1:8000`. **Không test trên `miyano`.** |
| Nhánh | `feat/bao-truoc-doi-gia-himedic` |
| Email | Site test bật `mute_emails`: email thông báo được **lưu** (Communication) nhưng **không gửi** ra ngoài. Email nhận demo: `himedic.demo@example.com` |

Quy tắc để đối chiếu khi test:

- "DEMO Bảng giá Himedic" có **Báo trước khi đổi giá** (7 ngày). Giá mới phải vào **bảng giá chờ** "DEMO Bảng giá Himedic - Chờ báo" trước.
- Chỉ **Giám đốc** (vai trò ở Selling Settings → "Vai trò được sửa % lãi", demo: `DEMO Giám đốc`) được **Gửi thông báo đổi giá** và đổi cài đặt báo trước.
- Gửi: một email gom mọi giá chờ; giá chuyển sang bảng giá chính; giá cũ giữ nguyên. Ngày hiệu lực **trước ngày gửi → bị chặn**; **dưới 7 ngày → cảnh báo + đánh dấu Báo gấp**, vẫn gửi được.
- Trên bảng giá chính: không thêm thẳng, không sửa giá/ngày, không xóa.

## 0. Chuẩn bị

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| 0.1 | Bench đang chạy. Ở `sites` chạy:<br>`../env/bin/python ../apps/erpnext/scripts/demo_gia_ban_doi_soat.py --site erpnext.localhost` | Chạy xong không lỗi | ☐ |
| 0.2 | Mở Price List **DEMO Bảng giá Himedic** | Mục "Báo trước khi đổi giá": đã tích, 7 ngày, Bảng giá chờ = DEMO Bảng giá Himedic - Chờ báo, email himedic.demo@example.com | ☐ |
| 0.3 | Bấm **Giá chờ gửi** | Danh sách Item Price của bảng giá chờ: 1 dòng DEMO-VT-01 106.050, áp từ D+5, trạng thái Chờ gửi | ☐ |

Người dùng mẫu (Impersonate): `demo.giamdoc@example.com` (Giám đốc), `demo.nhanvien@example.com` (nhân viên), `demo.duyet@example.com`.

## H. Cài đặt bảng giá và chặn sửa (bước 2.1–2.3)

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| H1 | `demo.nhanvien` mở DEMO Bảng giá Himedic → bỏ tích "Báo trước khi đổi giá" → Lưu | Bị chặn: "Chỉ Giám đốc được đổi cài đặt báo trước…" | ☐ |
| H2 | `demo.giamdoc` đổi Số ngày báo trước = 10 → Lưu; đổi lại 7 → Lưu | Lưu được | ☐ |
| H3 | Mở Item Price → New: bảng giá **DEMO Bảng giá Himedic**, DEMO-VT-02, 53.000, Valid From D+7 → Lưu | Bị chặn: "thêm giá mới vào bảng giá chờ … rồi Giám đốc Gửi thông báo đổi giá" (T3) | ☐ |
| H4 | Mở dòng giá DEMO-VT-02 52.000 của DEMO Bảng giá Himedic → sửa giá thành 53.000 → Lưu | Bị chặn: "Không sửa được giá đã có…" (T2). Tương tự khi sửa Valid From / Valid Upto | ☐ |
| H5 | `demo.nhanvien` xóa dòng giá đó | Bị chặn: "Không xóa giá trên bảng giá …" | ☐ |
| H6 | Item Price → New: bảng giá **DEMO Bảng giá Himedic - Chờ báo**, DEMO-VT-02, 53.000, Valid From hôm nay → Lưu | Lưu được; mục "Thông báo đổi giá": trạng thái **Chờ gửi** | ☐ |
| H7 | Sửa giá dòng H6 = 53.500 → Lưu; rồi xóa dòng | Đều được (nháp tự do sửa/xóa) | ☐ |
| H8 | Tạo Sales Order cho DEMO-Himedic, chọn Price List = **DEMO Bảng giá Himedic - Chờ báo** → Lưu | Bị chặn: "… là bảng giá chờ (giá chưa báo cho khách). Dùng bảng giá DEMO Bảng giá Himedic" (T4) | ☐ |
| H9 | Sửa giá dòng của bảng giá **mua** (vd. DEMO Mua - Hùng Minh) | Sửa bình thường — bảng giá mua không bị ảnh hưởng | ☐ |

## I. Gửi thông báo đổi giá (bước 2.4)

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| I1 | `demo.nhanvien` mở DEMO Bảng giá Himedic | **Không** thấy nút "Gửi thông báo đổi giá" (chỉ thấy "Giá chờ gửi") | ☐ |
| I2 | Thêm nháp vào bảng chờ: DEMO-VT-02 53.000, Valid From = **hôm qua** | Lưu được (nháp) | ☐ |
| I3 | `demo.giamdoc` mở DEMO Bảng giá Himedic → **Gửi thông báo đổi giá** → Xác nhận | Bị chặn: "Sửa ngày hiệu lực (không được trước hôm nay) cho: DEMO-VT-02 …". **Không** dòng nào bị chuyển (VT-01 vẫn ở bảng chờ) (D2-4) | ☐ |
| I4 | Sửa Valid From của nháp VT-02 = **D+7** → Lưu. Gửi lại | Gửi được. Cảnh báo cam "Báo gấp (dưới 7 ngày)": DEMO-VT-01 áp từ D+5, **báo trước 5 ngày, thiếu 2 ngày** (T1). VT-02 không nằm trong danh sách báo gấp | ☐ |
| I5 | Mở dòng VT-01 106.050 (giờ ở **DEMO Bảng giá Himedic**) → mục Thông báo đổi giá | Trạng thái **Đã gửi**, Ngày gửi = hôm nay, Số ngày báo trước = 5, **Báo gấp** tích, Email thông báo có link, Người gửi = demo.giamdoc | ☐ |
| I6 | Bấm link Email thông báo (Communication) | Tiêu đề "Thông báo thay đổi giá - DEMO Bảng giá Himedic"; người nhận himedic.demo@example.com; bảng: mã hàng, giá hiện tại (VT-01: 101.000; VT-02: 52.000), giá mới, ngày áp dụng | ☐ |
| I7 | Mở DEMO Bảng giá Himedic → timeline cuối form | Thấy email vừa gửi | ☐ |
| I8 | Dòng giá cũ VT-01 101.000 | **Vẫn còn**, không đổi (T1b) | ☐ |
| I9 | Bảng chờ sau khi gửi | Trống | ☐ |
| I10 | Sửa giá dòng VT-01 106.050 vừa gửi | Bị chặn (giá đã báo không sửa được) | ☐ |
| I11 | Nhập **Ngày khách xác nhận** (hôm nay) + đính kèm file vào dòng VT-01 → Lưu (`demo.nhanvien` cũng làm được) | Lưu được; trạng thái → **Đã xác nhận** (T7). Xóa ngày xác nhận → về **Đã gửi** | ☐ |
| I12 | Nhập "Lý do báo gấp" cho dòng VT-01 → Lưu | Lưu được | ☐ |
| I13 | Tạo SO DEMO-Himedic ngày **D+4** có VT-01 → xem giá gợi ý | 101.000 (giá cũ). Ngày **D+5** → 106.050 (giá theo ngày SO — D4-4, T5) | ☐ |
| I14 | Gửi khi bảng chờ trống | Báo "Bảng giá chờ … không có giá nào để gửi" | ☐ |
| I15 | Xóa email nhận trên bảng giá (Giám đốc) rồi gửi | Báo "chưa có Email nhận thông báo đổi giá". Điền lại email | ☐ |
| I16 | Thêm nháp VT-02 với **cùng Valid From** với một giá đã có trên bảng giá chính → Gửi | Báo "đã có giá cùng ngày hiệu lực …"; không dòng nào bị chuyển | ☐ |

## J. Báo giá NCC tạo nháp giá Himedic (bước 2.5)

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| J1 | Mở Supplier Quotation nháp DEMO-Vietmed (VT-01, 107.000) → **Submit** | Ngoài thông báo ghi giá mua (Đợt 1), có thêm thông báo xanh "Báo giá NCC … làm đổi giá bán. Đã tạo nháp…": DEMO Bảng giá Himedic: DEMO-VT-01 (giá hiện tại) → **108.070** (T8) | ☐ |
| J2 | Bảng giá chờ | Có nháp VT-01 108.070, Valid From = **hôm nay** (D2-3), ghi chú "Đề xuất từ báo giá NCC: <số>", trạng thái Chờ gửi | ☐ |
| J3 | Impersonate `demo.giamdoc` → chuông thông báo | Có thông báo "Có nháp đổi giá chờ gửi thông báo (báo giá NCC …)" | ☐ |
| J4 | Tạo báo giá NCC DEMO-Vietmed cho **VT-02** (mặt hàng NCC mặc định khác) giá bất kỳ → Submit | Không tạo nháp nếu giá chuẩn Himedic không đổi | ☐ |
| J5 | Tạo báo giá cho mặt hàng **không có** trên DEMO Bảng giá Himedic → Submit | Không tạo nháp | ☐ |
| J6 | **Cancel** báo giá J1 | Nháp 108.070 trong bảng chờ bị xóa (nếu chưa gửi). Nếu đã gửi rồi thì giữ nguyên trên bảng giá chính | ☐ |

## K. Trạng thái "Đang trong thời hạn báo giá" trên SO (bước 2.6)

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| K1 | Sau J1 (giá mua VT-01 = 107.000, có nháp 108.070 trong bảng chờ): mở SO DEMO-Himedic nháp → Lưu | Dòng VT-01 (giá 101.000): **Đang trong thời hạn báo giá**, chênh lệch −7.070, ghi chú "…; giá mới 108070 từ … (chờ gửi thông báo)". Không nằm trong cảnh báo lệch (T9) | ☐ |
| K2 | Selling Settings → Chế độ = **Chặn** → `demo.nhanvien` Submit SO chỉ có dòng VT-01 | Submit được (không cần lý do / duyệt cho dòng đang trong thời hạn báo giá). Trả Chế độ về Chỉ ghi nhận | ☐ |
| K3 | Gửi thông báo nháp VT-01 với Valid From D+7 → mở lại SO nháp → Lưu | Vẫn "Đang trong thời hạn báo giá", ghi chú "(đã báo)" | ☐ |
| K4 | Mặt hàng lệch giá **không** có nháp / giá mới chờ (vd. VT-02 52.000) | Vẫn "Thấp hơn" như Đợt 1 | ☐ |

## L. Nhắc việc (bước 2.7)

Hai điểm nhắc trong **Supply Notification Point** (tự tạo khi migrate):

| Mã | Tên | Khi nào |
|---|---|---|
| NTF-14 | Đổi giá bán · Nhắc xin khách xác nhận | Ngày gửi + 2, trạng thái vẫn Đã gửi (chưa xác nhận) |
| NTF-15 | Đổi giá bán · Giá mới sắp áp dụng | Ngày hiệu lực − 1, giá đã gửi / đã xác nhận |

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| L1 | Mở Supply Notification Point NTF-14, NTF-15 | Đang bật; Item Price; ngày `ngay_gui_thong_bao` +2 / `valid_from` −1; người nhận: trường **Người gửi thông báo** (NTF-15 thêm P. Kinh doanh, P. Kế toán) | ☐ |
| L2 | Trên NTF-15 dùng **Xem trước** với một dòng giá đã gửi (vd. VT-01 ở I5) | Thấy nội dung và người nhận là demo.giamdoc | ☐ |
| L3 | (Kiểm tự động — test `TestNhacViec`) ngày gửi + 2 chưa xác nhận → nhắc người gửi; đã xác nhận → không nhắc; nháp chờ gửi → không nhắc | Xem mục Test tự động | ☐ |

Nhắc tự động chạy theo giờ trong Cài đặt thông báo (scheduler hằng giờ) và chỉ khi **Supply Notification Settings** đang bật.

## M. Báo cáo "Thong Bao Doi Gia Bao Gap" (bước 2.8)

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| M1 | Mở báo cáo (mặc định "Chỉ dòng báo gấp") | VT-01 106.050: báo trước 5, **thiếu 2**, Báo gấp, trạng thái, ngày xác nhận, người gửi, link email (T12) | ☐ |
| M2 | Bỏ tích "Chỉ dòng báo gấp" | Có thêm VT-02 (đủ 7 ngày) | ☐ |
| M3 | Tích "Chỉ dòng khách chưa xác nhận" | Dòng đã nhập Ngày khách xác nhận biến mất | ☐ |
| M4 | Submit một SO DEMO-Himedic ngày ≥ ngày áp dụng VT-01 (mới) có VT-01 → chạy lại báo cáo | Cột "Số SO đã bán theo giá" của VT-01 tăng 1 | ☐ |

## Test tự động

`erpnext/selling/tests/test_kiem_gia_bao_truoc.py` — 42 test (cài đặt bảng giá, chặn sửa, gửi thông báo, nháp từ báo giá NCC, trạng thái đang trong thời hạn báo giá, nhắc việc, báo cáo). Chạy:

```bash
cd ~/frappe-bench/sites
../env/bin/python ../apps/erpnext/scripts/chay_test.py --site erpnext.localhost erpnext.selling.tests.test_kiem_gia_bao_truoc
```

## Ảnh hưởng tới hướng dẫn Đợt 1

Script demo nay bật báo trước cho "DEMO Bảng giá Himedic". Ở `docs/HDKT_Dot1_Kiem_gia_ban.md`:
- **E4**: sau khi Submit báo giá NCC, dòng VT-01 trên SO là **"Đang trong thời hạn báo giá"** (đã có nháp 108.070 chờ báo), không còn là "Thấp hơn".
- Các bước thêm/sửa giá trực tiếp trên DEMO Bảng giá Himedic (nếu có) sẽ bị chặn — làm qua bảng giá chờ.

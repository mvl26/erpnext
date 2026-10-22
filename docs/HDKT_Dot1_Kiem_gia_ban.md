# Hướng dẫn test thủ công — Đợt 1: Kiểm giá bán theo % lãi

| Mục | Nội dung |
|---|---|
| Phạm vi | YC3 — Đợt 1 (bước 1.1–1.8) của spec `docs/superpowers/specs/2026-10-21-kiem-gia-ban-bao-gia-doi-soat-design.md` |
| Site test | `erpnext.localhost` — mở `http://127.0.0.1:8000`. **Không test trên `miyano`.** |
| Nhánh | `feat/auto-check-selling-price-poc` |
| Cách ghi kết quả | Đánh dấu ☐ → ☑ khi đạt; ghi chú ngắn khi không đạt (số chứng từ, ảnh chụp) |

Quy tắc chung của tính năng, để đối chiếu khi test:

- **Giá chuẩn = giá gốc × (1 + % lãi)**, so trên giá **chưa gồm VAT**, **sau chiết khấu cấp đơn**.
- **Giá gốc** = giá trong bảng giá **mua** có hiệu lực tại ngày chứng từ; ưu tiên giá của **NCC mặc định** của mặt hàng; không có thì lấy giá có ngày hiệu lực mới nhất.
- **% lãi**: (khách, mặt hàng) → % riêng của khách → % mặc định (1%).
- Trạng thái mỗi dòng: **Khớp / Thấp hơn / Cao hơn / Chưa xác định giá gốc / Bỏ qua**.
- Kết quả xem ở **dòng hàng → mục "Kiểm giá bán"** (bấm vào dòng để mở chi tiết).

---

## 0. Chuẩn bị

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| 0.1 | Bật bench: ở thư mục bench chạy `bench start`; đợi web chạy | Mở được `http://127.0.0.1:8000` | ☐ |
| 0.2 | Ở thư mục `sites` chạy:<br>`../env/bin/python ../apps/erpnext/scripts/demo_gia_ban_doi_soat.py --site erpnext.localhost` | In ra 2 SO demo và trạng thái từng dòng (xem bảng 0.4). Chạy lại lần 2 không lỗi, không tạo trùng | ☐ |
| 0.3 | Thử chạy với `--site miyano` | Script từ chối: "Từ chối: không tạo dữ liệu demo trên site production." | ☐ |
| 0.4 | Đăng nhập Administrator | — | ☐ |

Dữ liệu script tạo:

| Loại | Bản ghi |
|---|---|
| NCC | `DEMO-Vietmed` (bảng giá mặc định `DEMO Mua - Vietmed`), `DEMO-Hùng Minh` (`DEMO Mua - Hùng Minh`) |
| Khách | `DEMO-Himedic` (% mặc định 1%), `DEMO-KH B` (% riêng 2%) |
| Mặt hàng | `DEMO-VT-01` Găng tay (NCC mặc định Vietmed) · `DEMO-VT-02` Bơm tiêm · `DEMO-VT-03` Bông gạc · `DEMO-VT-04` Khẩu trang · `DEMO-VT-05` Dung dịch (bán theo Hộp = 10 Cái, NCC mặc định Vietmed) |
| Bảng giá | Mua: `DEMO Mua - Vietmed`, `DEMO Mua - Hùng Minh`, `DEMO Bảng giá mua`. Bán: `DEMO Bảng giá Himedic` |
| Người dùng (không mật khẩu, dùng **Impersonate**) | `demo.nhanvien@example.com` (bán hàng, mua hàng, sửa khách/mặt hàng) · `demo.duyet@example.com` (vai trò **DEMO Duyệt giá**) · `demo.giamdoc@example.com` (vai trò **DEMO Giám đốc**, được sửa % lãi) |
| Cài đặt | Selling Settings: Bật kiểm giá; Chế độ = Chỉ ghi nhận; % mặc định 1; Vai trò sửa % = DEMO Giám đốc; Vai trò duyệt = DEMO Duyệt giá |
| Chứng từ nháp | SO DEMO-Himedic (5 dòng), SO DEMO-KH B (1 dòng), Supplier Quotation DEMO-Vietmed (VT-01 giá 107.000) |

Giá mua demo (D = hôm nay):

| Mặt hàng | Giá mua | Giá Himedic | Kỳ vọng |
|---|---|---|---|
| VT-01 | Vietmed 100.000 (D−60); Vietmed 105.000 (D+5); Bảng giá mua 98.000 (D−10) | 101.000 | Khớp (lấy Vietmed 100.000 vì là NCC mặc định) |
| VT-02 | Hùng Minh 50.000 (D−90); Bảng giá mua 52.000 (D−20) | 52.000 | Thấp hơn 520 (giá chuẩn 52.520) |
| VT-03 | Vietmed 20.000 và Hùng Minh 21.000 cùng D−15 | 20.500 | Chưa xác định (2 giá cùng ngày) |
| VT-04 | (không có) | 3.000 | Chưa xác định (không có giá mua) |
| VT-05 | Vietmed 12.345,67 / Cái (D−30) | 12.469,1267 / Cái | Khớp; bán theo Hộp: 124.691,27 |

**Cách đăng nhập thay người khác (Impersonate):** Administrator mở **User** → chọn người dùng → nút **Impersonate** → nhập lý do → Xác nhận. Muốn quay về: đăng xuất, đăng nhập lại Administrator.

---

## A. Báo cáo "Doi Chieu Gia Ban Gia Mua"

Mở: thanh tìm kiếm → gõ "Doi Chieu Gia Ban Gia Mua".

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| A1 | Bảng giá bán = `DEMO Bảng giá Himedic`, Tại ngày = hôm nay, % lãi **để trống** (theo cấu hình) | 5 dòng: VT-02 "Thấp hơn" (đỏ, −520), VT-03 và VT-04 "Chưa xác định giá gốc" (ghi chú lý do), VT-01 và VT-05 "Khớp" (xanh). Dòng lệch xếp trước | ☐ |
| A2 | Cột "Dòng giá mua", "Bảng giá mua", "NCC" của VT-01 | Trỏ tới dòng giá `DEMO Mua - Vietmed` 100.000, NCC DEMO-Vietmed | ☐ |
| A3 | Tích "Chỉ hiện dòng lệch" | Chỉ còn VT-02, VT-03, VT-04 | ☐ |
| A4 | Đổi % lãi = 2 | VT-01 thành "Thấp hơn" (giá chuẩn 102.000) | ☐ |
| A5 | Đổi Tại ngày = hôm nay + 5 | VT-01 lấy giá mua 105.000 → giá chuẩn 106.050 → "Thấp hơn" | ☐ |
| A6 | Chọn một bảng giá bán bằng USD (nếu có; không có thì bỏ qua) | Báo lỗi "chỉ so được bảng giá bằng tiền tệ công ty" | ☐ |
| A7 | Xóa ô % lãi (để trống); khi `DEMO-Himedic` có % riêng 3 (làm ở B8) mà bảng giá có giá riêng cho khách này | Cột "% lãi áp dụng" lấy theo cấu hình của khách. (Bảng giá demo không có giá riêng theo khách — bước này để kiểm khi có dữ liệu thật) | ☐ |

---

## B. Cấu hình % lãi và quyền sửa

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| B1 | Administrator mở **Selling Settings** → mục "Kiểm giá bán theo % lãi" | Thấy 5 ô: Bật kiểm giá bán, Chế độ, % lãi mặc định, Vai trò được sửa % lãi, Vai trò duyệt giá lệch | ☐ |
| B2 | Impersonate `demo.nhanvien` → mở Selling Settings | 5 ô trên chỉ đọc. (Nếu sửa được bằng cách khác, lưu sẽ báo "Bạn không có quyền sửa…") | ☐ |
| B3 | `demo.nhanvien` sửa một ô khác của Selling Settings (vd. "Allow Multiple Items") → Lưu | Lưu được | ☐ |
| B4 | Impersonate `demo.giamdoc` → Selling Settings → đổi % lãi mặc định = 1,5 → Lưu; rồi đổi lại 1 → Lưu | Lưu được cả hai lần | ☐ |
| B5 | `demo.nhanvien` mở khách `DEMO-Himedic` → tab Settings → mục "Kiểm giá bán theo % lãi" | 3 ô chỉ đọc | ☐ |
| B6 | `demo.nhanvien` tạo khách mới (chỉ nhập tên) → Lưu | Lưu được; "Kiểm giá bán" mặc định tích | ☐ |
| B7 | `demo.nhanvien` **Duplicate** khách `DEMO-KH B` → đổi tên → Lưu | Lưu được; bản sao **không** có % riêng (dùng mặc định) | ☐ |
| B8 | `demo.giamdoc` mở `DEMO-Himedic` → tích "% lãi riêng", % lãi = 3 → Lưu. Mở lại SO DEMO-Himedic → Lưu | Lưu được; trên SO, dòng VT-01 "Thấp hơn" (giá chuẩn 103.000), "% lãi áp dụng" = 3. **Trả lại**: bỏ tích % lãi riêng → Lưu | ☐ |
| B9 | `demo.giamdoc` mở mặt hàng `DEMO-VT-01` → bảng Customer Items → thêm dòng: Khách DEMO-Himedic, tích "% lãi riêng", % lãi = 0,5 → Lưu | Lưu được (không cần mã hàng của khách) | ☐ |
| B10 | Mở SO DEMO-Himedic → Lưu | VT-01: giá chuẩn 100.500 → "Cao hơn" 500; "% lãi áp dụng" 0,5; ghi chú "% lãi: Mặt hàng - khách" | ☐ |
| B11 | `demo.giamdoc` thêm dòng thứ 2 cho cùng khách DEMO-Himedic (vd. chỉ có mã hàng "HM-01") → Lưu | Báo lỗi "Khách DEMO-Himedic có nhiều dòng… mỗi khách một dòng". Muốn có cả mã hàng và % thì nhập mã hàng vào **chính dòng** % lãi. Xóa dòng vừa thêm | ☐ |
| B12 | `demo.nhanvien` mở `DEMO-VT-01` → cột % lãi trong Customer Items | Chỉ đọc | ☐ |
| B13 | `demo.nhanvien` thêm dòng Customer Items: Khách **DEMO-KH B** + Mã hàng của khách "KH-001" → Lưu | Lưu được (vẫn khai mã hàng của khách bình thường) | ☐ |
| B14 | Thêm dòng chỉ có Khách, không mã hàng, không % riêng → Lưu | Báo lỗi "nhập mã hàng của khách hoặc % lãi riêng" | ☐ |
| B15 | `demo.giamdoc` xóa dòng % riêng của VT-01 (B9) và dòng KH-001 (B13) → Lưu | Trả dữ liệu về như ban đầu | ☐ |

---

## C. Kiểm giá trên Quotation và Sales Order (chế độ "Chỉ ghi nhận")

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| C1 | Mở SO DEMO-Himedic (nháp) → bấm từng dòng → mục "Kiểm giá bán" | Đúng bảng giá mua demo ở mục 0: VT-01 Khớp, VT-02 Thấp hơn −520, VT-03/VT-04 Chưa xác định (ghi chú lý do), VT-05 (Hộp) Khớp, giá gốc 123.456,7 | ☐ |
| C2 | Lưu SO | Hộp cảnh báo cam "Kiểm giá bán" liệt kê dòng 2, 3, 4; SO vẫn lưu được | ☐ |
| C3 | Mở SO DEMO-KH B | VT-01 giá 102.000 → Khớp, "% lãi áp dụng" 2, ghi chú "% lãi: Khách" | ☐ |
| C4 | Trên SO DEMO-Himedic đổi giá VT-02 thành 52.520 → Lưu | VT-02 thành Khớp, hết trong cảnh báo | ☐ |
| C5 | Thêm dòng VT-01, tích "Is Free Item", giá 0 → Lưu | Dòng mới "Bỏ qua" (Hàng tặng) | ☐ |
| C6 | Thêm dòng VT-01 giá 0, không tích Is Free Item → Lưu | "Thấp hơn" (dòng giá 0 không phải hàng tặng vẫn bị bắt) | ☐ |
| C7 | Tạo một mặt hàng dịch vụ (bỏ tích "Maintain Stock", vd. "Phí vận chuyển") → thêm vào SO → Lưu | Dòng dịch vụ "Bỏ qua" (Mặt hàng không quản lý kho) | ☐ |
| C8 | Ở SO: tab chiết khấu đơn (Additional Discount) đặt 10% trên Net Total → Lưu | Các dòng đang Khớp chuyển "Thấp hơn" (so sau chiết khấu). Bỏ chiết khấu → Lưu → trở lại Khớp | ☐ |
| C9 | Thêm thuế VAT 10% có tích "Is this Tax included in Basic Rate?" và đổi giá VT-01 = 111.100 → Lưu | VT-01 Khớp (net 101.000). Bỏ thuế, đặt lại giá 101.000 | ☐ |
| C10 | Đổi ngày SO (Transaction Date) = hôm nay + 5 → Lưu | VT-01 lấy giá mua 105.000 → "Thấp hơn" (giá chuẩn 106.050). Đặt lại ngày hôm nay | ☐ |
| C11 | Khách `DEMO-Himedic`: `demo.giamdoc` bỏ tích "Kiểm giá bán" → mở lại SO → Lưu | Mọi dòng "Bỏ qua" (Khách tắt kiểm giá). **Trả lại**: tích lại | ☐ |
| C12 | Tạo **Quotation** cho DEMO-Himedic, bảng giá DEMO Bảng giá Himedic, các dòng VT-01, VT-02 → Lưu | Cùng kết quả như SO (VT-01 Khớp, VT-02 Thấp hơn) + cảnh báo | ☐ |
| C13 | Tạo Quotation cho một **Lead** (Quotation To = Lead), VT-01 giá 101.000 | Khớp, % lãi áp dụng = 1 (mặc định) | ☐ |
| C14 | Từ Quotation C12 → Create → Sales Order | SO mới có kết quả kiểm tính lại (không chép từ Quotation) | ☐ |
| C15 | **Duplicate** SO DEMO-Himedic → Lưu | Bản sao được kiểm lại; không mang người duyệt | ☐ |
| C16 | Selling Settings: bỏ tích "Bật kiểm giá bán" (Administrator) → tạo SO mới VT-01 giá 1 → Lưu | Không có cảnh báo, mục "Kiểm giá bán" trống. **Bật lại** | ☐ |

---

## D. Chế độ "Chặn" — lý do và duyệt giá lệch

Chuẩn bị: Administrator → Selling Settings → Chế độ = **Chặn** → Lưu. Dùng SO DEMO-Himedic (VT-02 Thấp hơn, VT-03/VT-04 Chưa xác định).

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| D1 | `demo.nhanvien` mở SO → **Submit** (chưa nhập lý do) | Bị chặn: "Dòng … lệch giá chuẩn. Nhập Lý do lệch giá trước khi Submit." | ☐ |
| D2 | Nhập "Lý do lệch giá" (mục Kiểm giá bán dưới bảng hàng) → Lưu → Submit | Bị chặn: "… chưa được duyệt. Người có vai trò DEMO Duyệt giá cần bấm Duyệt giá lệch." | ☐ |
| D3 | `demo.nhanvien`: có thấy nút **Duyệt giá lệch** không? | Không thấy | ☐ |
| D4 | Impersonate `demo.duyet` → mở SO | Thấy nút **Duyệt giá lệch** | ☐ |
| D5 | Bấm **Duyệt giá lệch** | Ô "Người duyệt giá lệch" = demo.duyet, có "Thời điểm duyệt"; nút biến mất | ☐ |
| D6 | `demo.nhanvien` mở SO → Submit | Submit được | ☐ |
| D7 | Tạo SO mới (hoặc Duplicate) có dòng lệch + lý do → `demo.duyet` duyệt → `demo.nhanvien` **sửa giá dòng lệch** → Lưu | Cảnh báo "Dòng lệch giá đã thay đổi sau khi duyệt. Cần duyệt lại."; ô Người duyệt bị xóa; Submit bị chặn | ☐ |
| D8 | Như D7 nhưng chỉ sửa **số lượng dòng đang Khớp** | Người duyệt giữ nguyên; Submit được | ☐ |
| D9 | Tạo SO lệch + lý do → `demo.duyet` tự **Submit** (không bấm duyệt) | Submit được; Người duyệt = demo.duyet | ☐ |
| D10 | Như D9 nhưng `demo.giamdoc` Submit | Submit được (người được sửa % lãi cũng được duyệt) | ☐ |
| D11 | `demo.duyet` bấm Duyệt giá lệch khi SO **chưa có lý do** | Báo "Người lập cần nhập và lưu Lý do lệch giá trước khi duyệt" | ☐ |
| D12 | SO **không có dòng lệch** (chỉ VT-01 giá 101.000) → `demo.nhanvien` Submit | Submit được, không cần lý do, không có người duyệt | ☐ |
| D13 | SO đã Submit ở D6 → **Update Items** → `demo.nhanvien` đổi giá VT-01 thành 90.000 → Update | Bị chặn (dòng lệch mới chưa được duyệt) | ☐ |
| D14 | Như D13 nhưng `demo.duyet` làm | Cập nhật được; Người duyệt = demo.duyet; dòng VT-01 "Thấp hơn" | ☐ |
| D15 | SO đã Submit ở D9 → Cancel → **Amend** → Lưu | Bản Amend giữ "Lý do lệch giá" nhưng **không** còn người duyệt; Submit bởi `demo.nhanvien` bị chặn | ☐ |
| D16 | Quotation có dòng lệch → Submit (bất kỳ ai có quyền) | Không bị chặn (Quotation chỉ cảnh báo) | ☐ |
| D17 | Selling Settings → Chế độ = **Chỉ ghi nhận** → SO lệch, không lý do → Submit | Submit được (chỉ cảnh báo) | ☐ |
| D18 | Chế độ Chặn, SO lệch → Administrator **tắt** "Bật kiểm giá bán" → `demo.nhanvien` Submit | Submit được (tắt là gỡ toàn bộ). Bật lại | ☐ |
| D19 | SO lệch + lý do → `demo.duyet` duyệt → người lập thêm **chiết khấu đơn** 10% → Lưu | Người duyệt bị xóa, cảnh báo "Cần duyệt lại"; Submit bị chặn | ☐ |
| D20 | SO đã duyệt → người lập **sửa Lý do lệch giá** → Lưu | Người duyệt bị xóa (người duyệt đã duyệt theo lý do cũ) | ☐ |
| D21 | Tắt kiểm giá → Submit một SO có dòng lệch → bật lại, Chế độ Chặn → `demo.nhanvien` **Update Items**: chỉ đổi **số lượng một dòng đang Khớp** | Cập nhật được (dòng lệch cũ không bị bắt duyệt) | ☐ |
| D22 | Như D21 nhưng đổi **giá** dòng thành lệch | Bị chặn | ☐ |
| D23 | Kết thúc phần D: Chế độ = Chỉ ghi nhận | — | ☐ |

---

## E. Báo giá NCC → bảng giá mua

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| E1 | Mở Supplier Quotation nháp của DEMO-Vietmed (VT-01, 107.000) | Chưa có dòng giá mua 107.000 nào (báo giá nháp không ghi gì) | ☐ |
| E2 | **Submit** báo giá | Thông báo xanh "Đã ghi 1 giá vào bảng giá mua DEMO Mua - Vietmed, hiệu lực từ …" | ☐ |
| E3 | Mở **Item Price**, lọc DEMO-VT-01 | Có dòng mới 107.000, bảng giá DEMO Mua - Vietmed, NCC DEMO-Vietmed, Valid From hôm nay, ghi chú "Báo giá NCC: <số>". Dòng 100.000 cũ vẫn còn | ☐ |
| E4 | Mở SO DEMO-Himedic (nháp, ngày hôm nay) → Lưu | VT-01: giá gốc 107.000, giá chuẩn 108.070 → "Thấp hơn". **Từ Đợt 2** (bảng giá Himedic có báo trước): "Đang trong thời hạn báo giá" vì báo giá NCC đã tạo nháp 108.070 chờ báo — xem `HDKT_Dot2_Bao_truoc_doi_gia.md` mục K | ☐ |
| E5 | Tạo SO ngày **hôm qua** cho VT-01 giá 101.000 → Lưu | Khớp (ngày hôm qua vẫn dùng giá 100.000) | ☐ |
| E6 | Tạo báo giá mới cùng NCC, cùng ngày, VT-01 **107.000** → Submit | Không tạo dòng trùng | ☐ |
| E7 | Tạo báo giá cùng NCC, cùng ngày, VT-01 **106.000** → Submit | Cảnh báo cam "Đã có giá khác của NCC này cùng ngày, giữ nguyên"; dòng 107.000 **không đổi** | ☐ |
| E7b | Cancel báo giá E7 | Dòng 107.000 vẫn còn (không bị xóa nhầm) | ☐ |
| E7c | Cancel báo giá E2 (107.000, nếu chưa SO Submit nào dùng) → Amend → sửa giá 106.000 → Submit | Dòng 107.000 bị xóa; dòng mới 106.000 | ☐ |
| E8 | Submit một SO dùng dòng giá VT-01 hôm nay (Chế độ Chỉ ghi nhận) → Cancel báo giá đã tạo dòng đó | Dòng giá được giữ, thông báo "Giữ lại … dòng giá mua đã dùng cho Sales Order" | ☐ |
| E9 | Báo giá có 2 dòng VT-02 giá khác nhau (50.000 và 51.000) → Submit | Cảnh báo "Bỏ qua (nhiều giá khác nhau…)", không ghi giá VT-02 | ☐ |
| E10 | Báo giá VT-05 theo **Hộp** giá 1.300.000 (hệ số 10) → Submit | Dòng giá mới 130.000 / **Cái** | ☐ |
| E11 | Báo giá có **chiết khấu đơn 10%**, VT-04 giá 2.000 → Submit | Dòng giá VT-04 = 1.800 | ☐ |
| E12 | Lưu một SO **nháp** có VT-04 (dòng VT-04 nhận giá gốc 1.800 của E11) → **Cancel** báo giá E11 | Cancel được (SO nháp không giữ dòng giá); dòng giá VT-04 1.800 bị xóa | ☐ |
| E13 | NCC chưa có bảng giá mặc định, báo giá chọn bảng giá mua `DEMO Bảng giá mua` → Submit | Giá ghi vào `DEMO Bảng giá mua` | ☐ |

---

## F. Cảnh báo giá PO cao hơn giá gốc

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| F1 | SO đã Submit có VT-01 (giá gốc 100.000) → **Create → Purchase Order** → NCC DEMO-Vietmed, giá VT-01 = 103.000 → Lưu | Cảnh báo cam "Kiểm giá mua": dòng VT-01, giá gốc ở SO là 100.000, cao hơn 3.000. PO vẫn lưu được | ☐ |
| F2 | Đổi giá PO = 100.000 (hoặc thấp hơn) → Lưu | Không cảnh báo | ☐ |
| F3 | SO bán VT-05 theo Hộp (giá gốc 123.456,7 / Hộp) → PO mua theo **Hộp** giá 123.456,7 → Lưu; rồi đổi giá PO = 124.000 → Lưu | Lần đầu không cảnh báo; lần sau cảnh báo cao hơn ≈ 543,3 | ☐ |
| F4 | PO giá 105.000 nhưng chiết khấu đơn 10% (net 94.500) → Lưu | Không cảnh báo | ☐ |
| F5 | PO tạo tay (không từ SO) giá rất cao → Lưu | Không cảnh báo (không có giá gốc để so) | ☐ |
| F6 | PO từ dòng SO "Chưa xác định giá gốc" (VT-04) → Lưu | Không cảnh báo | ☐ |

---

## G. Dọn dẹp sau khi test

1. Selling Settings: Chế độ = Chỉ ghi nhận (hoặc tắt "Bật kiểm giá bán" nếu muốn site test về như cũ).
2. Chạy lại script demo (bước 0.2) để có lại chứng từ nháp cho lần test sau. Các chứng từ đã Submit vẫn giữ.

## Test tự động (đối chiếu)

109 test, chạy trên `erpnext.localhost` (mỗi test tự rollback): `erpnext/selling/tests/test_kiem_gia_*.py`.

| File | Nội dung | Mục test thủ công tương ứng |
|---|---|---|
| `test_kiem_gia_goc.py` | Giá gốc, giá chuẩn, báo cáo | A |
| `test_kiem_gia_cau_hinh.py` | % lãi, quyền sửa | B |
| `test_kiem_gia_chung_tu.py` | Kiểm trên Quotation / SO | C |
| `test_kiem_gia_duyet.py` | Chế độ Chặn, duyệt | D |
| `test_kiem_gia_bao_gia_ncc.py` | Báo giá NCC → bảng giá mua | E |
| `test_kiem_gia_po.py` | Cảnh báo PO | F |
| `test_kiem_gia_bien.py` | Trường hợp biên và lỗi review (ngoại tệ, chiết khấu đơn, dịch vụ, khách qua cổng, duyệt giả qua API, Amend, Duplicate, Update Items, mã duyệt theo giá thực bán, báo cáo theo cấu hình) | C7, C8, D13–D22, B7, B11, A7 |

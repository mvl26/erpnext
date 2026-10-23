# Hướng dẫn test thủ công — Đợt 3: Đối soát Phiếu nhập mua ↔ Hóa đơn mua và đề nghị thanh toán (YC5)

| Mục | Nội dung |
|---|---|
| Phạm vi | YC5 — spec `docs/superpowers/specs/2026-10-21-kiem-gia-ban-bao-gia-doi-soat-design.md`, mục 6.3, 7.3, 16. Hướng dẫn sử dụng: `HD_01_HDSD_MuaHang_ERP_20261023_V1.4.docx`, chương 9 |
| Site test | `erpnext.localhost` — `http://127.0.0.1:8000`. **Không test trên `miyano`.** |
| Nhánh | `feat/doi-soat-pr-pi` (đã gộp vào `feat/auto-check-selling-price`) |
| Dữ liệu | `scripts/demo_doi_soat_pr_pi.py`: tạo sẵn Đơn mua hàng và Phiếu nhập mua đã Nộp cho từng kịch bản A–L. Hóa đơn mua do người test tự lập |
| Email | Site test chưa có hộp thư gửi đi: thông báo trong hệ thống (chuông, giao việc) chạy bình thường, email **không** đi ra ngoài. Xem mục K |

Quy tắc để đối chiếu khi test:

- Chỉ áp cho hóa đơn mua của NCC trong phạm vi (thử: NCC có tích **Áp đối soát Phiếu nhập ↔ Hóa đơn**, demo là `DEMO-Vietmed`), có dòng lấy từ Phiếu nhập mua. Hóa đơn trả hàng, hóa đơn tự nhập kho, hóa đơn dịch vụ không có Phiếu nhập: không đối soát.
- So **0 đồng** với phần Phiếu nhập đã nhận mà chưa lập hóa đơn, theo ĐVT kho và giá trước thuế: số lượng, đơn giá, thuế suất, thành tiền từng dòng; rồi tổng tiền hàng, tổng thuế, tổng thanh toán (chỉ so tổng khi mọi dòng đã khớp).
- Trạng thái đối soát (mục **Đối soát với Phiếu nhập mua**, dưới bảng mặt hàng; nhãn màu ở đầu form): **Khớp** xanh lá, **Lệch** đỏ, **Ngoại lệ đã duyệt** cam, **Chưa đối soát** xám.
- Lệch thì **không Nộp được**. Kế toán trưởng / Ban Điều hành có thể **Duyệt ngoại lệ** (bắt buộc lý do). Sửa hóa đơn làm chênh lệch đổi thì phê duyệt mất hiệu lực. Hóa đơn **cao hơn** giá trị Phiếu nhập thì không duyệt ngoại lệ được.
- Nộp hóa đơn Khớp / có ngoại lệ → hệ thống tạo **Yêu cầu thanh toán (ĐNTT) nháp**, đính kèm file hóa đơn, giao việc cho người duyệt. Tổng ĐNTT chưa hủy của một hóa đơn (kể cả bản nháp) không được vượt số tiền hóa đơn.

## 0. Chuẩn bị

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| 0.1 | Bench đang chạy. Ở `sites` chạy:<br>`../env/bin/python ../apps/erpnext/scripts/demo_doi_soat_pr_pi.py --site erpnext.localhost` | In ra các cài đặt vừa đổi và bảng 12 kịch bản A–L (số Đơn mua hàng, số Phiếu nhập). Chạy lại được; mỗi lần tạo một bộ chứng từ mới | ☐ |
| 0.2 | Thử chạy với `--site miyano` | Script từ chối: "Từ chối: không tạo dữ liệu demo trên site production." | ☐ |
| 0.3 | Mở **Buying Settings** → mục **Đối soát Phiếu nhập mua ↔ Hóa đơn mua** | Bật đối soát Phiếu nhập ↔ Hóa đơn mua: tích. Phạm vi áp dụng: Chỉ nhà cung cấp được chọn. Tự tạo đề nghị thanh toán nháp khi Nộp hóa đơn: tích. Vai trò Kế toán trưởng: Accounts Manager. Vai trò Ban Điều hành: trống. Người duyệt đề nghị thanh toán: demo.ketoantruong@example.com. Nhắc Kế toán trưởng khi lệch quá (ngày): 3 | ☐ |
| 0.4 | Mở NCC **DEMO-Vietmed** và **DEMO-Hùng Minh** | DEMO-Vietmed tích **Áp đối soát Phiếu nhập ↔ Hóa đơn**; DEMO-Hùng Minh không tích | ☐ |

Tìm Phiếu nhập của một kịch bản: danh sách **Phiếu nhập mua**, lọc **Phiếu giao hàng nhà cung cấp** = `DEMO-D3-A` (thay A bằng mã kịch bản). Số chứng từ thay đổi mỗi lần chạy script; số tiền dưới đây là cố định.

Người dùng mẫu (Impersonate): `demo.ketoan@example.com` (Kế toán, lập hóa đơn), `demo.ketoantruong@example.com` (Kế toán trưởng: duyệt ngoại lệ, duyệt ĐNTT), `demo.muahang@example.com` (Mua hàng). Thao tác của Kho làm bằng Administrator.

Cách lập hóa đơn trong các bước dưới: mở Phiếu nhập → **Tạo → Hóa đơn mua** → điền **Số hóa đơn nhà cung cấp** (ví dụ `HD-A`) → sửa theo bước → **Lưu**. ERPNext có thể hiện cảnh báo cam "Rate must be same as Purchase Order / Purchase Receipt" khi sửa đơn giá: đó là cảnh báo chuẩn, không chặn.

## A. Cài đặt và quyền

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| A1 | `demo.muahang` mở Buying Settings → bỏ tích **Bật đối soát** → Lưu | Bị chặn: "Chỉ System Manager được sửa cài đặt đối soát Phiếu nhập ↔ Hóa đơn: Bật đối soát Phiếu nhập ↔ Hóa đơn mua." | ☐ |
| A2 | `demo.muahang` mở NCC DEMO-Vietmed → bỏ tích **Áp đối soát Phiếu nhập ↔ Hóa đơn** → Lưu | Bị chặn: "Chỉ người duyệt ngoại lệ đối soát hoặc System Manager được đổi ô Áp đối soát Phiếu nhập ↔ Hóa đơn." | ☐ |

## B. Hóa đơn khớp → Nộp → ĐNTT nháp (kịch bản A)

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| B1 | `demo.ketoan` lập hóa đơn từ Phiếu nhập **DEMO-D3-A** (10 DEMO-VT-01 × 100.000, VAT 10%), không sửa gì → Lưu | Tổng 1.100.000. Mục Đối soát: **Khớp**, có giờ đối soát; không có Bảng chênh lệch. Đầu form: nhãn xanh "Đối soát Phiếu nhập: Khớp" | ☐ |
| B2 | Đính kèm một file PDF bất kỳ vào hóa đơn | Đính kèm được | ☐ |
| B3 | **Nộp** | Nộp được. Thông báo xanh "Đã tạo đề nghị thanh toán nháp ACC-PRQ-…" | ☐ |
| B4 | Mở Yêu cầu thanh toán vừa tạo | **Nháp**; Loại yêu cầu thanh toán Outward; Đối tác DEMO-Vietmed; Số tiền **1.100.000**; tiêu đề "Thanh toán hóa đơn HD-A của DEMO-Vietmed"; nội dung có "Đối soát Phiếu nhập: Khớp"; có file PDF đính kèm; **Giao cho** demo.ketoantruong | ☐ |
| B5 | `demo.ketoantruong` xem chuông / danh sách việc (ToDo) | Có việc "Duyệt đề nghị thanh toán cho hóa đơn HD-A (DEMO-Vietmed), hạn …" | ☐ |
| B6 | `demo.ketoan` vào **Yêu cầu thanh toán → Mới**: Loại yêu cầu thanh toán Outward, Loại đối tác Supplier, Đối tác DEMO-Vietmed, Loại tài liệu tham chiếu Purchase Invoice, Tên tham chiếu = hóa đơn B1, Số tiền **1** → Lưu | Bị chặn "Vượt số tiền hóa đơn": tổng 1.100.001 vượt 1.100.000 (các đề nghị khác chưa hủy, kể cả bản nháp: 1.100.000) | ☐ |
| B7 | Administrator sửa Số tiền ĐNTT B4 = **600.000** → Lưu. Lặp B6 với Số tiền **500.000** → Lưu. Lặp B6 với Số tiền **1** | 600.000 lưu được; 500.000 lưu được (tổng vừa đủ 1.100.000); 1 bị chặn như B6 | ☐ |
| B8 | Trên hóa đơn B1 bấm **Tạo → Yêu cầu thanh toán** | ERPNext **mở lại bản nháp có sẵn**, không tạo bản thứ hai (hành vi chuẩn; số tiền bản nháp có thể bị đặt lại theo số còn phải trả) | ☐ |
| B9 | **Hủy** hóa đơn B1 (đang có 2 ĐNTT nháp 600.000 và 500.000) | Hủy được. Cả hai ĐNTT nháp bị xóa theo; timeline hóa đơn có ghi chú "Đã xóa đề nghị thanh toán nháp … khi hủy hóa đơn." cho từng bản | ☐ |

## C. Lệch số lượng, nhắc Kế toán trưởng, duyệt ngoại lệ (kịch bản B)

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| C1 | `demo.ketoan` lập hóa đơn từ **DEMO-D3-B**, sửa Số lượng **9** → Lưu | Thông báo cam "Hóa đơn lệch Phiếu nhập mua ở 1 điểm (xem Bảng chênh lệch). Chưa Nộp được." Trạng thái **Lệch** (nhãn đỏ, dòng giới thiệu đỏ). **Lệch từ ngày** = hôm nay. Bảng chênh lệch 1 dòng: Dòng 1 · Số lượng · DEMO-VT-01 · Phiếu nhập "10 Cái", Hóa đơn "9 Cái", mức lệch −1, gợi ý "(b1) Phiếu nhập mua sai" | ☐ |
| C2 | **Nộp** | Bị chặn "Lệch Phiếu nhập mua": "Hóa đơn chưa khớp Phiếu nhập mua (Lệch), chưa Nộp được: Dòng 1 · Số lượng · DEMO-VT-01: Phiếu nhập 10 Cái, Hóa đơn 9 Cái …" | ☐ |
| C3 | Menu **Đối soát Phiếu nhập** của `demo.ketoan` | Chỉ có **Đối soát lại**, **không** có Duyệt ngoại lệ | ☐ |
| C4 | Ở `sites` chạy:<br>`../env/bin/python ../apps/erpnext/scripts/demo_doi_soat_pr_pi.py --site erpnext.localhost --nhac-lech <số hóa đơn C1>` | In "Lệch từ ngày lùi về 3 ngày trước", "Đã nhắc Kế toán trưởng 1 hóa đơn" (hoặc nhiều hơn nếu còn hóa đơn lệch khác) | ☐ |
| C5 | `demo.ketoantruong` mở chuông | Thông báo "1 hóa đơn mua lệch Phiếu nhập quá 3 ngày"; nội dung là bảng: số hóa đơn (link), NCC, số HĐ NCC, giá trị, lệch từ (3 ngày), trạng thái, nhánh xử lý "Chưa chọn", người lập | ☐ |
| C6 | `demo.ketoantruong` mở hóa đơn C1 → **Đối soát Phiếu nhập → Duyệt ngoại lệ** → để trống lý do → Duyệt | Không duyệt được (ô lý do bắt buộc) | ☐ |
| C7 | Nhập lý do "NCC giao thiếu 1, đã thỏa thuận" → **Duyệt** | Trạng thái **Ngoại lệ đã duyệt** (nhãn cam). Hiện Lý do ngoại lệ, Người duyệt ngoại lệ = demo.ketoantruong, Thời điểm duyệt. Lệch từ ngày bị xóa. Bảng chênh lệch vẫn giữ | ☐ |
| C8 | `demo.ketoan` sửa Số lượng **8** → Lưu | Thông báo cam "Chênh lệch đã thay đổi sau khi demo.ketoantruong@example.com duyệt ngoại lệ, nên phê duyệt cũ không còn hiệu lực." Trạng thái về **Lệch**; ô duyệt trống; mức lệch −2 | ☐ |
| C9 | Sửa lại **9** → Lưu | Vẫn **Lệch** (phê duyệt cũ không tự quay lại) | ☐ |
| C10 | `demo.ketoantruong` Duyệt ngoại lệ lại. `demo.ketoan` **Nộp** | Nộp được. ĐNTT nháp **990.000**, nội dung "Đối soát Phiếu nhập: Ngoại lệ đã duyệt" | ☐ |

## D. Lệch đơn giá, thuế suất; hóa đơn điều chỉnh (kịch bản C, D)

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| D1 | `demo.ketoan` lập hóa đơn từ **DEMO-D3-C** (20 DEMO-VT-02 × 50.000), sửa Đơn giá **48.000** → Lưu | **Lệch**: Dòng 1 · Đơn giá · Phiếu nhập "50.000 / Cái", Hóa đơn "48.000 / Cái", mức lệch −2.000, gợi ý "(b2) Hóa đơn NCC sai". Không có dòng tổng (tổng chỉ so khi mọi dòng khớp) | ☐ |
| D2 | Chọn **Nhánh xử lý** = "(b2) Hóa đơn NCC sai" → Lưu | Lưu được. Trên thanh công cụ có nút vàng **Gửi NCC bảng chênh lệch** (chỉ hiện khi hóa đơn nháp đang Lệch). Gửi thật: xem mục K | ☐ |
| D3 | NCC gửi hóa đơn điều chỉnh: `demo.ketoantruong` **Xóa** hóa đơn D1 (`demo.ketoan` không có quyền xóa). Lập lại từ DEMO-D3-C, không sửa → Lưu | **Khớp** — hóa đơn mới đối soát lại từ đầu | ☐ |
| D4 | Lập hóa đơn từ **DEMO-D3-D** (5 DEMO-VT-01), đổi **Mẫu thuế và chi phí mua hàng** = "GTGT mua vào 8% - MVL" → Lưu | **Lệch**: Dòng 1 · Thuế suất · Phiếu nhập "10%", Hóa đơn "8%", mức lệch −2, gợi ý (b2). Tổng 540.000 | ☐ |

## E. Hóa đơn cao hơn Phiếu nhập (kịch bản E)

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| E1 | `demo.ketoan` lập hóa đơn từ **DEMO-D3-E** (10 × 100.000), sửa Đơn giá **120.000** → Lưu | **Lưu được** (không bị ERPNext chặn "Cannot overbill"). **Lệch**: Đơn giá "100.000 / Cái" → "120.000 / Cái", mức lệch +20.000, gợi ý (b2) | ☐ |
| E2 | `demo.ketoantruong` → Duyệt ngoại lệ, lý do "thử" | Bị từ chối "Không duyệt ngoại lệ được": "Hóa đơn vượt giá trị hàng đã nhập kho: Dòng 1 (DEMO-VT-01): vượt 20.0% … Nếu giá mới là đúng, sửa Phiếu nhập theo giá mới (nhánh b1); nếu nhà cung cấp tính sai, xin hóa đơn điều chỉnh (nhánh b2)." Trạng thái vẫn Lệch | ☐ |
| E3 | `demo.ketoan` sửa Đơn giá về **100.000** → Lưu | **Khớp** | ☐ |

## F. Phiếu nhập sai — Kho hủy và sửa (kịch bản F, nhánh b1)

Đơn mua 12 cái DEMO-VT-02, Phiếu nhập **DEMO-D3-F** ghi 10; thực tế Kho nhận 11 và NCC xuất hóa đơn 11.

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| F1 | `demo.ketoan` lập hóa đơn từ DEMO-D3-F, sửa Số lượng **11** → Lưu | **Lệch**: Số lượng "10 Cái" → "11 Cái", mức +1, gợi ý "(b1) Phiếu nhập mua sai" | ☐ |
| F2 | Chọn **Nhánh xử lý** = "(b1) Phiếu nhập mua sai" → Lưu | Lưu được; vẫn Lệch | ☐ |
| F3 | Administrator mở Phiếu nhập DEMO-D3-F → **Hủy** | Hủy được. Mở lại hóa đơn F1: trạng thái **Chưa đối soát** (dòng giới thiệu cam "Phiếu nhập liên quan vừa thay đổi. Bấm Đối soát lại."); timeline có "Phiếu nhập mua … vừa thay đổi; hóa đơn sẽ được đối soát lại khi lưu hoặc Nộp." | ☐ |
| F4 | Trên Phiếu nhập đã hủy bấm **Sửa đổi** → Số lượng và Số lượng nhận = **11** → Lưu → **Nộp** | Nộp được bản sửa (số …-1) | ☐ |
| F5 | Mở lại hóa đơn F1 | Tự đối soát lại: **Khớp**, Bảng chênh lệch trống, Lệch từ ngày trống. Cột Phiếu nhập mua trên dòng = bản sửa …-1 | ☐ |

## G. Một dòng Đơn mua nhận qua nhiều Phiếu nhập (kịch bản G, H)

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| G1 | Mở **Đơn mua hàng** của kịch bản G (10 DEMO-VT-01, nhận qua 2 Phiếu nhập 6 + 4) → **Tạo → Hóa đơn mua** → điền số HĐ NCC → Lưu | Thông báo xanh "Ghép dòng với Phiếu nhập mua: Dòng 1: tách theo 2 Phiếu nhập (…, …)". Hóa đơn có 2 dòng: 6 cái trỏ Phiếu nhập thứ nhất, 4 cái trỏ Phiếu nhập thứ hai. **Khớp**, tổng 1.100.000 | ☐ |
| G2 | **Nộp** | Nộp được; ĐNTT nháp 1.100.000 | ☐ |
| G3 | Mở Đơn mua hàng của kịch bản H (10 DEMO-VT-02, nhận 6 + 4) → Tạo → Hóa đơn mua → sửa Số lượng **5** → Lưu | Bị chặn "Không ghép được Phiếu nhập mua": "Dòng 1 (DEMO-VT-02): nhiều Phiếu nhập có thể ghép (…, …). Xóa dòng rồi dùng Lấy mặt hàng từ → Phiếu nhập mua để chọn đúng phiếu." | ☐ |
| G4 | Làm theo hướng dẫn: xóa dòng, **Lấy mặt hàng từ → Phiếu nhập mua**, chọn Phiếu nhập 6 cái → Lưu | **Khớp**, tổng 330.000 | ☐ |

## H. Hóa đơn từng phần và cước cố định (kịch bản I)

Phiếu nhập **DEMO-D3-I**: 10 DEMO-VT-01 × 100.000, VAT 10%, cước vận chuyển cố định 50.000. NCC xuất 2 hóa đơn: 6 cái rồi 4 cái.

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| H1 | `demo.ketoan` lập hóa đơn từ DEMO-D3-I, sửa Số lượng **6**, **không** tích Hóa đơn từng phần → Lưu | **Lệch**: Số lượng "10 Cái" → "6 Cái", mức −4 | ☐ |
| H2 | Tích **Hóa đơn từng phần** → Lưu | **Khớp**. Thông báo xanh "Hóa đơn từng phần. Còn chờ hóa đơn tiếp theo của nhà cung cấp: <Phiếu nhập> · DEMO-VT-01: 4 Cái". Thuế và phí: VAT 60.000, cước 50.000; tổng **710.000** | ☐ |
| H3 | **Nộp** | Nộp được; ĐNTT nháp 710.000 | ☐ |
| H4 | Lập hóa đơn thứ hai từ DEMO-D3-I (ERPNext tự lấy 4 cái và chép cả dòng cước) → Lưu | **Lệch** 2 dòng tổng: Tổng thuế "40.000" → "90.000" và Tổng thanh toán "440.000" → "490.000", mức +50.000 (cước bị lập lần hai) | ☐ |
| H5 | Xóa dòng **Cước vận chuyển** trong bảng Thuế và phí → Lưu | **Khớp**, tổng 440.000. Hóa đơn cuối lấy hết phần còn lại nên không cần tích Hóa đơn từng phần | ☐ |

## I. Ngoài phạm vi, dịch vụ, ĐVT (kịch bản J, K, L)

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| I1 | Lập hóa đơn từ **DEMO-D3-J** (NCC DEMO-Hùng Minh, không tích Áp đối soát), sửa Số lượng **9** → Lưu → Nộp | **Không** có mục Đối soát với Phiếu nhập mua; Nộp được; **không** tạo ĐNTT | ☐ |
| I2 | Mở Đơn mua hàng kịch bản K (dịch vụ DEMO-DV-VC 200.000, không có Phiếu nhập) → Tạo → Hóa đơn mua → Lưu → Nộp | Không có mục đối soát; Nộp được (hàng không quản lý kho không cần Phiếu nhập); không tạo ĐNTT | ☐ |
| I3 | Lập hóa đơn từ **DEMO-D3-L** (10 DEMO-VT-05 theo Cái), đổi ĐVT dòng thành **Hộp**, hệ số 10, Số lượng 1 → Lưu | ERPNext chặn ngay khi lưu: "Incorrect value in row 1:UOM must be equal to 'Cái'" (ĐVT phải trùng Phiếu nhập; không tới bước đối soát) | ☐ |

## J. Tắt công tắc

Làm sau cùng.

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| J1 | Administrator bỏ tích **Bật đối soát** trong Buying Settings → Lưu. Lập hóa đơn từ Phiếu nhập 4 cái còn lại của kịch bản H, sửa Số lượng **3** → Lưu → Nộp | Không có mục đối soát; Nộp được; không tạo ĐNTT. Hóa đơn đã đối soát trước đó giữ nguyên dữ liệu | ☐ |
| J2 | Ở `sites` chạy `../env/bin/python ../apps/erpnext/scripts/demo_doi_soat_pr_pi.py --site erpnext.localhost --tra-lai` | In các cài đặt được trả về như trước lần chạy demo đầu | ☐ |

## K. Xử lý sự cố thường gặp

| Hiện tượng | Nguyên nhân | Cách xử lý |
|---|---|---|
| Bấm **Gửi NCC bảng chênh lệch** báo lỗi hệ thống; nhật ký gửi thông báo (Supply Notification Dispatch Log) của hóa đơn ghi Failed / "Lỗi hệ thống khi gửi" | Site test chưa có **Email Account** gửi đi mặc định | Bỏ qua bước gửi thật trên site test; kiểm trên site có hộp thư gửi đi. Production: script `kiem_truoc_trien_khai_yc5.py` kiểm mục này |
| Nộp hóa đơn báo thiếu tài khoản làm tròn | Công ty chưa có Round Off Account | Script demo đã điền "Chênh lệch làm tròn - MVL"; chạy lại script |
| Sửa đơn giá trên hóa đơn bị chặn hẳn "Rate must be same as Purchase Order" (không phải cảnh báo) | Buying Settings → Maintain Same Rate Action = Stop | Script demo đặt Warn (như production); chạy lại script |
| Lưu hóa đơn báo không liên kết được tới Phiếu nhập đã hủy | Phiếu nhập đã hủy, bản sửa chưa Nộp | Nộp bản sửa (hóa đơn tự đối soát lại), hoặc bấm **Đối soát Phiếu nhập → Đối soát lại** |
| Hóa đơn Khớp nhưng Nộp báo "over limit" | Phiếu nhập giá cao hơn Đơn mua; ERPNext chặn hóa đơn vượt thành tiền Đơn mua | Sửa Đơn mua hàng (Cập nhật mặt hàng) hoặc nhờ duyệt ngoại lệ khi hóa đơn còn lệch |

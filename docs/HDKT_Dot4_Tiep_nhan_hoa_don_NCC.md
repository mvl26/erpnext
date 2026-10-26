# Hướng dẫn test thủ công — Đợt 4: Hợp đồng khung, tiếp nhận hóa đơn NCC và đối soát 4 tầng (FRD-MAP-01, phần 1)

| Mục | Nội dung |
|---|---|
| Phạm vi | FRD-MAP-01 phần 1, spec `docs/superpowers/specs/2026-10-23-tiep-nhan-hoa-don-ncc-design.md` (quyết định D4-1 → D4-19). Hợp đồng nguyên tắc mẫu Greentech chỉ để tham khảo: Đơn khung giữ khung chung, điều khoản riêng của từng NCC ghi theo Mẫu điều khoản. Chưa có ở phần 1: đọc ảnh / PDF hóa đơn, ràng buộc Yêu cầu vật tư → Đơn mua, mẫu in / email đặt hàng có mã dòng hợp đồng |
| Site test | `erpnext.localhost` — `http://127.0.0.1:8000`. **Không test trên `miyano`.** |
| Nhánh | `feat/tiep-nhan-chung-tu-ncc` (đã gộp vào `feat/auto-check-selling-price`). Thư mục chính của bench phải có code Đợt 4, đã `migrate` và `clear-cache` |
| Dữ liệu | `scripts/demo_tiep_nhan_hoa_don.py`: mỗi lần chạy tạo một NCC demo mới (`DEMO-D4 NCC xx`, xx là số thứ tự lần chạy) kèm hai hợp đồng khung đã Nộp (mỗi hợp đồng một Mẫu điều khoản), Đơn mua hàng và Phiếu nhập mua đã Nộp cho từng kịch bản, và tệp XML hóa đơn điện tử. Phiếu tiếp nhận và hóa đơn mua do người test tự lập |
| Liên quan | Đợt 1: giá "HĐ nguyên tắc" khi kiểm giá bán. Đợt 3: đối soát Phiếu nhập ↔ Hóa đơn mua (dung sai 1 đồng cho hợp đồng giá gồm VAT), ĐNTT nháp khi Nộp hóa đơn |

Quy tắc để đối chiếu khi test:

- **Hợp đồng khung** là **Đơn khung** (Blanket Order) có Loại đơn hàng = Purchasing. Ô **Số hợp đồng** (Order No) là số của hợp đồng nguyên tắc; ô **Ngày đặt** (Order Date) là ngày ký.
  - **Khung chung**, hợp đồng nào cũng có: số hợp đồng, ngày ký, hiệu lực (Từ ngày – Đến ngày), các bên ký, tệp hợp đồng đã ký, Đơn giá đã gồm thuế GTGT, Không cam kết số lượng tối thiểu, phụ lục, dòng hàng.
  - **Điều khoản riêng của từng NCC** (thanh toán, giao hàng, phạt…) không phải trường cố định. Chọn ở ô **Điều khoản** một **Mẫu điều khoản** (Terms and Conditions, loại Mua) do người dùng tự tạo; nội dung chép vào **Chi tiết điều khoản và điều kiện** và sửa được trên từng hợp đồng.
  - Mỗi dòng có **Mã dòng hợp đồng** dạng `[NCC]-[Mã hợp đồng]-[Nhóm hàng]-[STT]`, ví dụ `D4Nxx-HDKxx2026-VTTH-001`.
    - Mã tự sinh khi lưu, sửa được trước khi Nộp, không được trùng.
    - [Mã hợp đồng] là ô "Mã hợp đồng trong mã dòng"; để trống thì lấy Số hợp đồng bỏ dấu và ký tự đặc biệt.
  - Khi Lưu, ô trống của **Các bên ký hợp đồng** được điền:
    - trước hết theo thẻ công ty / NCC (MST, địa chỉ mặc định, tài khoản ngân hàng);
    - sau đó theo hợp đồng mua đã Nộp gần nhất của công ty / NCC (đại diện, chức vụ…).
  - Muốn **Nộp** thì luôn phải có Nhà cung cấp, Số hợp đồng, Bảng giá mua, đơn giá > 0, số lượng > 0 (trừ khi tích Không cam kết số lượng tối thiểu), Số phụ lục khi là phụ lục.
  - Các trường bắt buộc khác **chọn ở Cài đặt tiếp nhận hóa đơn NCC** (mục Hợp đồng khung). Mặc định gồm: Ngày đặt, Đại diện và MST hai bên, Số tài khoản và Ngân hàng Bên B, Chi tiết điều khoản; trên dòng: Mã hàng NCC theo hợp đồng, Tên theo hợp đồng, Quy cách, Hãng sản xuất, Nước sản xuất, Số lưu hành / công bố, Thuế suất GTGT.
  - **Không cam kết số lượng tối thiểu** tích thì dòng để Số lượng 0 = không giới hạn: không cảnh báo, không chặn hạn mức.
  - **ĐVT theo hợp đồng** phải là ĐVT kho của mặt hàng.
- **Nộp** hợp đồng khung: giá từng dòng được ghi vào bảng giá mua của NCC. Đây là giá "HĐ nguyên tắc" mà kiểm giá bán dùng.
  - Tích **Đơn giá đã gồm thuế GTGT** thì giá ghi vào bảng giá là giá chưa VAT, làm tròn đến đồng.
  - **Hủy** hợp đồng khung: các giá này bị xóa.
- **Đã Nộp thì không sửa được**, chỉ trừ ô **Đến ngày** (gia hạn).
  - Bổ sung mặt hàng hoặc đổi giá theo phụ lục: lập Đơn khung mới, chọn **Phụ lục của hợp đồng** = hợp đồng gốc.
  - Phụ lục lấy số hợp đồng của gốc; mã dòng đánh số tiếp.
  - Phụ lục đổi giá phải có Từ ngày sau Từ ngày của hợp đồng gốc.
- **Quyền**: giám đốc là người có quyền cao nhất, giữ vai trò **Sales Manager**, làm cả ba việc: Nộp / Hủy / Sửa đổi / gia hạn Đơn khung, duyệt lệch giá / vượt hạn mức, duyệt Bảng ánh xạ tên. Purchase User, Purchase Manager tạo, sửa bản nháp; Accounts User, Accounts Manager, Stock User chỉ xem; System Manager toàn quyền.
- **Đơn mua hàng** tự gắn hợp đồng khung còn hiệu lực (mặt hàng có ở cả hợp đồng gốc và phụ lục thì gắn phụ lục). Sau đơn mà số đã đặt đạt 90% hạn mức thì hệ thống cảnh báo; vượt hạn mức thì ERPNext chặn.
- **Phiếu tiếp nhận hóa đơn NCC**: tải tệp XML lên rồi **Lưu**. Hệ thống làm lần lượt:
  - đọc hóa đơn;
  - nhận NCC theo MST người bán;
  - từ chối nếu MST người mua sai hoặc hóa đơn đã tiếp nhận;
  - kiểm tổng tiền và nghi trùng;
  - đối soát từng dòng qua 4 tầng:
    - **Tầng 1 - Mã**: mã hàng Miyano, mã hàng của NCC (trên thẻ mặt hàng hoặc ghi trong hợp đồng) hoặc mã dòng hợp đồng.
    - **Tầng 2 - Ánh xạ tên**: Bảng ánh xạ tên, chỉ dòng **Đang dùng**.
    - **Tầng 3 - Đơn mua**: dòng Đơn mua cùng ĐVT, cùng đơn giá, còn đủ số lượng, tên đủ giống. Điểm ≥ 0,75 thì Đã khớp; 0,55 – 0,75 thì Chờ xác nhận.
    - **Chọn tay**.
  - Quy cách (các con số, cỡ S / M / L) trong tên khác nhau thì **không bao giờ tự khớp**.
- **Cảnh báo chặn**: đơn giá khác giá hợp đồng khung (hợp đồng giá gồm VAT: so với giá chưa VAT, dung sai 1 đồng trên đơn giá hóa đơn), hoặc vượt hạn mức còn lại của hợp đồng.
  - Chỉ người có vai trò duyệt (giám đốc, **Sales Manager**) mới có nút **Duyệt cảnh báo**, và phải nhập lý do.
  - Thuế suất / ĐVT khác hợp đồng, hoặc hàng ngoài hợp đồng khung: chỉ ghi chú, không chặn.
- Trạng thái phiếu (nhãn màu đầu form):
  - **Mới tiếp nhận**: xám;
  - **Đã trích xuất**: xanh dương;
  - **Đã đối soát**: xanh lá;
  - **Chờ xử lý thủ công**: cam;
  - **Đã tạo nháp hóa đơn mua**: xanh dương;
  - **Lệch PR-PI**: đỏ — hóa đơn mua nháp của phiếu bị đối soát Đợt 3 báo Lệch Phiếu nhập; hết lệch thì phiếu tự về Đã tạo nháp hóa đơn mua. Lọc danh sách phiếu theo trạng thái này để thấy mọi hóa đơn đang kẹt. Báo Mua hàng khi lệch là thông báo NTF-16 / NTF-17 của Đợt 3;
  - **Đã ghi sổ**: xanh lá;
  - **Từ chối**: đỏ. Hệ thống tự từ chối (sai MST người mua, trùng, bị thay thế), hoặc người dùng bấm **Từ chối** kèm lý do (Từ chối tay; bấm **Mở lại** để đối soát lại).
- **Hóa đơn thay thế / điều chỉnh** (ô **Tính chất hóa đơn** trên phiếu, đọc từ XML): hệ thống tìm hóa đơn gốc theo MST người bán + ký hiệu + số.
  - **Thay thế**: phiếu của hóa đơn cũ tự Từ chối. Hóa đơn cũ đã có Hóa đơn mua nháp thì bấm **Bỏ hóa đơn bị thay thế** (xóa bản nháp); đã ghi sổ thì phải hủy Hóa đơn mua đó trước.
  - **Điều chỉnh** (phần tăng ghi dương, phần giảm ghi âm): mỗi dòng gắn với một dòng hóa đơn gốc. Hóa đơn gốc chưa ghi sổ thì gộp vào **một** Hóa đơn mua theo số sau điều chỉnh (nút **Lập / Lập lại Hóa đơn mua nháp (gốc + điều chỉnh)**). Hóa đơn gốc đã ghi sổ thì kế toán lập tay Hóa đơn mua trả hàng / bổ sung, Số hóa đơn NCC = số hóa đơn điều chỉnh; phiếu tự nối vào chứng từ đó.
  - Xóa Hóa đơn mua nháp (Lập lại, Bỏ hóa đơn bị thay thế, Từ chối phiếu có bản nháp) cần quyền sửa phiếu **và** quyền xóa Hóa đơn mua: trong demo là `demo.ketoantruong` (có thêm vai trò Purchase User). Ở production kế toán chỉ xem phiếu, nên làm hai bước: kế toán xóa Hóa đơn mua nháp ngay trên Hóa đơn mua (phiếu tự tính lại), rồi nhân viên mua hàng bấm nút trên phiếu.
- **Quyền trên phiếu tiếp nhận**: Purchase User, Purchase Manager tạo / sửa; Kế toán (Accounts User, Accounts Manager) **chỉ xem** — không có nút Lưu, Tạo Hóa đơn mua nháp, Từ chối. Giám đốc (Sales Manager) xem phiếu và có nút **Duyệt cảnh báo**; sửa được Bảng ánh xạ tên. Giám đốc chỉ cần vai trò Sales Manager, không cần thêm Purchase User. Người dùng demo kế toán có thêm Purchase User (dùng chung cho các đợt) nên vẫn sửa được phiếu.
- **Bảng ánh xạ tên**: dòng đã duyệt (Đang dùng / Ngừng dùng) mà người không có vai trò duyệt sửa NCC, tên hoặc Mặt hàng thì tự về **Chờ duyệt**, tầng 2 thôi dùng tới khi giám đốc duyệt lại.
- Hóa đơn mua tạo từ phiếu luôn là **nháp**; Kế toán kiểm rồi Nộp. Hóa đơn này đi tiếp qua đối soát Phiếu nhập ↔ Hóa đơn (Đợt 3) như hóa đơn nhập tay. Với dòng thuộc hợp đồng giá gồm VAT, đối soát Đợt 3 cho lệch tối đa 1 đồng trên đơn giá hóa đơn, và lúc Nộp không bị ERPNext chặn "over limit" vì phần vượt trong mức đó.

## 0. Chuẩn bị

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| 0.1 | Ở `sites` chạy:<br>`../env/bin/python ../apps/erpnext/scripts/demo_tiep_nhan_hoa_don.py --site erpnext.localhost` | In ra:<ul><li>các cài đặt vừa đổi (lần đầu có thêm dòng lưu cài đặt cũ);</li><li>tên NCC demo (`DEMO-D4 NCC xx`, MST 0109990xxx, mã viết tắt D4Nxx) và hai hợp đồng khung: `HĐK xx/2026`, `HĐNT xx-ELISA/MIYANO`;</li><li>7 mã dòng hợp đồng;</li><li>bảng 21 dòng kịch bản (tệp XML, Đơn mua hàng, Phiếu nhập mua);</li><li>thư mục chứa tệp XML, kèm đường dẫn mở từ Windows: `\\wsl.localhost\Ubuntu-22.04\home\minhbitong\frappe\frappe-bench\sites\erpnext.localhost\private\demo_tiep_nhan_hoa_don\DEMO-D4_NCC_xx`.</li></ul>Chạy lại được: mỗi lần tạo NCC mới và thư mục XML mới. Dùng NCC của **lần chạy mới nhất** | ☐ |
| 0.2 | Thử chạy với `--site miyano` | Script từ chối: "Từ chối: không tạo dữ liệu demo trên site production." | ☐ |
| 0.3 | Mở `/app/supplier-invoice-intake-settings` (**Cài đặt tiếp nhận hóa đơn NCC**) | <ul><li>Bật tiếp nhận hóa đơn: tích; MST người mua: 0109529507; Cảnh báo khi đặt hàng đạt (% hạn mức hợp đồng khung): 90.</li><li>Vai trò duyệt lệch giá, vượt hạn mức: **Sales Manager**; Vai trò duyệt Bảng ánh xạ tên: **Sales Manager**.</li><li>Mục **Hợp đồng khung**, ô "Trường bắt buộc khi Nộp": Đầu hợp đồng: Ngày đặt, Đại diện Bên A (Miyano), MST Bên A, Đại diện Bên B (NCC), MST Bên B, Số tài khoản Bên B, Ngân hàng Bên B (mở tại), Chi tiết điều khoản và điều kiện. Dòng hợp đồng: Mã hàng NCC theo hợp đồng, Tên theo hợp đồng, Quy cách, Hãng sản xuất, Nước sản xuất, Số lưu hành / công bố, Thuế suất GTGT.</li><li>Ngưỡng khớp tự động 0,75; Ngưỡng chờ xác nhận 0,55; Trọng số trùng từ 0,6; Trọng số giống chuỗi 0,4; từ đồng nghĩa 4 dòng; từ bỏ qua "size, cỡ, loại, cái".</li></ul> | ☐ |
| 0.4 | Mở danh sách **Điều khoản và điều kiện** (`/app/terms-and-conditions`) | Có 2 mẫu do script tạo, loại Mua: "DEMO Mẫu điều khoản - vật tư y tế" (giá chưa VAT, giao 5 ngày, thanh toán 45 ngày…) và "DEMO Mẫu điều khoản - hóa chất xét nghiệm" (giá gồm VAT, giá theo số hộp, giao 3 – 5 ngày, thanh toán 30 ngày, tự động gia hạn…). Người dùng tự tạo mẫu cho từng NCC / loại hợp đồng như tạo bản ghi thường | ☐ |
| 0.5 | Mở hợp đồng khung 1 (`HĐK xx/2026`) trong danh sách **Đơn khung** | <ul><li>Đã Nộp; Bảng giá mua "DEMO Mua - Hợp đồng khung"; Đơn giá đã gồm thuế GTGT không tích.</li><li>Mục **Các bên ký hợp đồng** đủ thông tin Bên A (Miyano, MST 0109529507) và Bên B.</li><li>Điều khoản = "DEMO Mẫu điều khoản - vật tư y tế", Chi tiết điều khoản có nội dung mẫu.</li><li>5 dòng, mã dòng D4Nxx-HDKxx2026-VTTH-001 → 005 (VTTH là nhóm hàng của mặt hàng demo trên site này). Mở một dòng: đủ Mã hàng NCC, Tên theo hợp đồng, Quy cách, Hãng, Nước, Số lưu hành, ĐVT Cái, Thuế suất 10%.</li></ul> | ☐ |
| 0.6 | Mở hợp đồng khung 2 (`HĐNT xx-ELISA/MIYANO`) | <ul><li>Tích **Đơn giá đã gồm thuế GTGT** và **Không cam kết số lượng tối thiểu**; Điều khoản = "DEMO Mẫu điều khoản - hóa chất xét nghiệm"; Mã hợp đồng trong mã dòng `NTxx`.</li><li>Dòng 1: DEMO-HDK-08 "Ascaris IgG Elisa Kit", Mã hàng NCC 5002, ĐVT Hộp, Số lượng 0, Đơn giá 3.949.000, Thuế suất 5%, mã dòng D4Nxx-NTxx-VTTH-001, Ghi chú giá "10 - 30 hộp/đơn: 3.812.500 (đã gồm VAT)".</li><li>Dòng 2: DEMO-HDK-10 "Đầu côn vô trùng 200µl", Mã hàng NCC DC200, ĐVT Cái, Số lượng 0, Đơn giá 5.250, Thuế suất 5%.</li></ul> | ☐ |
| 0.7 | Mở danh sách **Giá mặt hàng**, lọc Nhà cung cấp = NCC demo | <ul><li>7 giá trong bảng giá "DEMO Mua - Hợp đồng khung", ô **Hợp đồng khung** (chỉ đọc) trỏ về hợp đồng tương ứng.</li><li>DEMO-HDK-08: **3.760.952** (= 3.949.000 / 1,05, làm tròn đến đồng); DEMO-HDK-10: **5.000**; ghi chú "… (hợp đồng ghi … đã gồm VAT 5%)".</li></ul> | ☐ |

Người dùng mẫu (Impersonate). Chỉ dùng vai trò có sẵn của hệ thống:

| Người dùng | Vai trò trong demo | Dùng ở bước |
|---|---|---|
| `demo.nvmuahang@example.com` | Nhân viên mua hàng (Purchase User) | Nhập hợp đồng khung nháp, lập phiếu tiếp nhận, tạo hóa đơn mua nháp; không Nộp hợp đồng, không duyệt |
| `demo.chuoicungung@example.com` | Trưởng phòng mua hàng (Purchase Manager) | Nhập nháp như nhân viên; không Nộp hợp đồng (B2) |
| `demo.giamdoc@example.com` | Giám đốc (Sales Manager) | Nộp / Hủy / gia hạn hợp đồng khung, duyệt lệch giá / vượt hạn mức, duyệt Bảng ánh xạ tên |
| `demo.ketoan@example.com` | Kế toán | Nộp hóa đơn mua |
| `demo.ketoantruong@example.com` | Kế toán trưởng | Xóa hóa đơn mua nháp; Lập lại hóa đơn theo điều chỉnh, Bỏ hóa đơn bị thay thế (L, M) |
| Administrator | System Manager | Cài đặt, Kho nhập hàng |

**Cách lập phiếu tiếp nhận** trong các bước dưới:
1. Vào `/app/supplier-invoice-intake/new`, đặt Công ty = Miyano.
2. Ở ô **Tệp hóa đơn (XML)** bấm Đính kèm, chọn tệp của kịch bản trong thư mục ở 0.1.
3. Bấm **Lưu**.

Mọi ô thông tin hóa đơn, NCC và Đơn mua hàng đều tự điền. Mỗi hóa đơn mẫu có ghi chú "Theo đơn đặt hàng PUR-ORD-…", nên phiếu chỉ khớp với Đơn mua của kịch bản đó.

Số chứng từ thay đổi mỗi lần chạy. Số hóa đơn (ký hiệu C26TDM, số 00000001 → 00000021) và số tiền dưới đây là cố định.

## A. Cài đặt và quyền

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| A1 | `demo.nvmuahang` mở Cài đặt tiếp nhận hóa đơn NCC | Các ô chỉ đọc, không có nút Lưu. Chỉ System Manager sửa được | ☐ |
| A2 | Administrator mở Cài đặt → bấm **Chọn trường bắt buộc khi Nộp hợp đồng khung** | Hộp tích chọn hai nhóm **Đầu hợp đồng** và **Dòng hợp đồng**, liệt kê các trường của Đơn khung theo nhãn (cả trường quản trị tự thêm bằng Customize Form), đang tích đúng danh sách ở 0.3. Không có các trường hệ thống luôn bắt buộc hoặc tự điền (Nhà cung cấp, Số hợp đồng, Bảng giá mua, Mã dòng…) | ☐ |
| A3 | Bỏ tích **Chi tiết điều khoản và điều kiện**, tích thêm **Tệp hợp đồng đã ký** → Áp dụng → **Lưu** | Ô tóm tắt "Trường bắt buộc khi Nộp" cập nhật theo. Làm xong mục B thì đặt lại như cũ (tích Chi tiết điều khoản, bỏ Tệp hợp đồng đã ký) — hoặc làm A3 sau cùng và kiểm: hợp đồng không có điều khoản Nộp được, không có tệp đã ký thì bị chặn "Tệp hợp đồng đã ký" | ☐ |

## B. Hợp đồng khung: nhập, Nộp, gia hạn, phụ lục

Chọn NCC demo in ở 0.1.

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| B1 | `demo.nvmuahang`: **Đơn khung → Mới**:<ul><li>Loại đơn hàng = Purchasing;</li><li>Nhà cung cấp = NCC demo;</li><li>Số hợp đồng = `HĐK 05/2026`;</li><li>Từ ngày = hôm nay, Đến ngày = sau 1 năm;</li><li>dòng DEMO-HDK-05, Số lượng 100, Đơn giá 20.000.</li></ul>→ **Lưu** | Lưu được.<ul><li>**Bảng giá mua** tự điền "DEMO Mua - Hợp đồng khung" (bảng giá mặc định của NCC).</li><li>**Các bên ký hợp đồng** tự điền theo hợp đồng gần nhất: Đại diện Bên A "DEMO Đại diện Miyano", Giám đốc vận hành, MST 0109529507, tài khoản DEMO-0001…; Bên B: MST của NCC demo, tài khoản DEMO-0002….</li><li>Dòng 1: **Mã dòng hợp đồng** `D4Nxx-HDK052026-VTTH-001`; ĐVT theo hợp đồng = Cái.</li></ul> | ☐ |
| B2 | `demo.nvmuahang` rồi `demo.chuoicungung` mở đơn khung B1, tìm nút **Nộp**. Bấm vào ô Bảng giá mua | Cả hai không có nút Nộp (Purchase User, Purchase Manager chỉ nhập nháp). Ô Bảng giá mua chỉ liệt kê bảng giá mua | ☐ |
| B3 | `demo.giamdoc` mở đơn khung B1 → **Nộp** | Bị chặn "Chưa Nộp được hợp đồng khung". Hợp đồng khung thiếu thông tin (theo danh sách ở Cài đặt):<ul><li>Ngày đặt</li><li>Chi tiết điều khoản và điều kiện</li><li>Dòng 1: Mã hàng NCC theo hợp đồng</li><li>Dòng 1: Tên theo hợp đồng</li><li>Dòng 1: Quy cách</li><li>Dòng 1: Hãng sản xuất</li><li>Dòng 1: Nước sản xuất</li><li>Dòng 1: Số lưu hành / công bố</li><li>Dòng 1: Thuế suất GTGT</li></ul> | ☐ |
| B4 | `demo.nvmuahang` bổ sung:<ul><li>Ngày đặt = hôm nay;</li><li>ô **Điều khoản** (mục Điều khoản và điều kiện) chọn "DEMO Mẫu điều khoản - vật tư y tế";</li><li>dòng 1: Mã hàng NCC "DTD-23G", Tên theo hợp đồng "Dây truyền dịch có kim 23G", Quy cách "Dài 150cm", Hãng "DEMO Hãng F", Nước "Việt Nam", Số lưu hành "DEMO-SLH-05", Thuế suất 5%.</li></ul>→ Lưu. `demo.giamdoc` **Nộp** | Chọn mẫu xong, **Chi tiết điều khoản và điều kiện** tự điền nội dung mẫu, sửa được cho riêng hợp đồng này. Nộp được. Danh sách Giá mặt hàng lọc Mặt hàng = DEMO-HDK-05 có giá mới:<ul><li>bảng giá DEMO Mua - Hợp đồng khung, **20.000**, ĐVT Cái;</li><li>hiệu lực từ hôm nay đến sau 1 năm;</li><li>ô Hợp đồng khung = đơn khung B1;</li><li>ghi chú "Hợp đồng khung HĐK 05/2026, dòng D4Nxx-HDK052026-VTTH-001".</li></ul> | ☐ |
| B5 | `demo.nvmuahang`: Đơn khung mới, Số hợp đồng `HĐK 06/2026`, dòng DEMO-HDK-06 SL 100 giá 1.000. Mở dòng, nhập Mã dòng hợp đồng = mã của B1 → Lưu | Bị chặn: "Mã dòng hợp đồng đã dùng: D4Nxx-HDK052026-VTTH-001 (MFG-BLR-…)" | ☐ |
| B6 | Trên đơn khung B5, xóa Mã dòng, đặt ĐVT theo hợp đồng = **Hộp** → Lưu. Sau đó đóng, không lưu | Bị chặn: "Dòng 1 (DEMO-HDK-06): ĐVT theo hợp đồng Hộp khác ĐVT kho của mặt hàng (Cái). Quy đổi số lượng và đơn giá về Cái, hoặc sửa ĐVT kho của mặt hàng." | ☐ |
| B7 | `demo.nvmuahang`: **Đơn mua hàng → Mới**, NCC demo, DEMO-HDK-05 SL **95** → **Lưu** | Đơn giá tự lấy 20.000 từ bảng giá mua. Dòng tự tích **Theo đơn khung**, Đơn khung = B1, Đơn giá đơn khung 20.000. Hộp cam "Sắp hết hạn mức hợp đồng khung": "Dòng 1 (DEMO-HDK-05): sau đơn này đã đặt 95/100 (95%) hạn mức hợp đồng khung MFG-BLR-…" | ☐ |
| B8 | **Nộp** Đơn mua B7. Mở lại Đơn khung B1 | Nộp được (cảnh báo hiện lại). Dòng 1 của B1: **Số lượng đã đặt** 95 | ☐ |
| B9 | Đơn mua hàng mới: DEMO-HDK-05 SL **10** → Lưu | ERPNext chặn: "Mặt hàng DEMO-HDK-05 không được đặt quá 5.0 theo đơn khung MFG-BLR-…" | ☐ |
| B10 | Gia hạn: `demo.nvmuahang` mở B1, thử sửa **Đến ngày**. Sau đó `demo.giamdoc` sửa Đến ngày = sau 2 năm → **Cập nhật** | `demo.nvmuahang`: ô Đến ngày khóa (chỉ đọc), không có nút Cập nhật. `demo.giamdoc` cập nhật được; timeline ghi thay đổi Đến ngày | ☐ |
| B11 | `demo.giamdoc` thử sửa Đơn giá hoặc dòng của B1 | Mọi ô khác đều khóa sau khi Nộp (chuẩn ERPNext): sửa nội dung hợp đồng phải làm phụ lục (B14) | ☐ |
| B12 | `demo.nvmuahang`: Đơn khung mới `HĐK 07/2026`, dòng DEMO-HDK-06 SL 100 giá 1.000, nhập đủ thông tin dòng, Ngày đặt, chọn một Mẫu điều khoản. `demo.giamdoc` **Nộp**, xem Giá mặt hàng của DEMO-HDK-06, rồi **Hủy** đơn khung này | Sau khi Nộp: có 1 giá 1.000 gắn hợp đồng `HĐK 07/2026`. Sau khi Hủy: giá đó bị xóa | ☐ |
| B13 | `demo.giamdoc` **Hủy** đơn khung B1 | Không hiện hộp "Hủy tất cả chứng từ" của Frappe (hộp này mà bấm nhầm là hủy luôn Đơn mua). Bị chặn: "Không thể xóa hoặc hủy vì Đơn khung MFG-BLR-… được liên kết với Đơn mua hàng PUR-ORD-…" (chuẩn ERPNext) | ☐ |
| B14 | Phụ lục: `demo.nvmuahang` tạo Đơn khung mới:<ul><li>NCC demo, **Phụ lục của hợp đồng** = hợp đồng 1 (`HĐK xx/2026`), để trống Số hợp đồng;</li><li>Từ ngày = hôm nay; Ngày đặt; Chi tiết điều khoản ghi nội dung phụ lục ("Phụ lục 01: đổi giá gạc, thêm khẩu trang");</li><li>dòng DEMO-HDK-02 (gạc) SL 1000 giá **5.200** và dòng DEMO-HDK-06 (khẩu trang) SL 500 giá 1.000, đủ thông tin dòng.</li></ul>→ Lưu | Lưu được. Số hợp đồng tự lấy "HĐK xx/2026" của hợp đồng gốc; mã dòng **D4Nxx-HDKxx2026-VTTH-006** và **-007** (đánh số tiếp hợp đồng gốc) | ☐ |
| B15 | `demo.giamdoc` **Nộp** phụ lục khi chưa có Số phụ lục; rồi nhập Số phụ lục `01` → Lưu → Nộp | Lần đầu bị chặn "Hợp đồng khung thiếu thông tin: Số phụ lục". Lần sau Nộp được | ☐ |
| B16 | `demo.nvmuahang`: Đơn mua hàng mới, DEMO-HDK-02 SL 10 → Lưu. Làm lại một đơn nữa, lần này tự tích **Theo đơn khung** trên dòng trước khi Lưu | Đơn giá **5.200** (giá phụ lục, có Từ ngày mới nhất). Dòng gắn **phụ lục**, không gắn hợp đồng gốc; Đơn giá đơn khung 5.200. Khi tự tích, ERPNext có thể điền hợp đồng gốc và giá 5.000; Lưu xong thì vẫn là phụ lục và 5.200 | ☐ |

## C. Khớp theo Đơn mua (tầng 3) → hóa đơn mua nháp → Nộp (kịch bản A)

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| C1 | `demo.nvmuahang` lập phiếu với **A_tang3_ten_khac.xml** | **Đã đối soát** (xanh lá).<ul><li>Nhà cung cấp = NCC demo (tự nhận theo MST).</li><li>Đơn mua hàng = Đơn mua kịch bản A.</li><li>Ký hiệu C26TDM, Số hóa đơn 00000001.</li><li>Tổng tiền hàng 6.250.000, Tiền thuế 625.000, Tổng thanh toán 6.875.000.</li><li>Tỷ lệ khớp tự động 100%.</li></ul>Dòng 1:<ul><li>Tên trên hóa đơn "Sonde Foley 2 way size 16", không có mã.</li><li>Mặt hàng DEMO-HDK-01.</li><li>Cách khớp **Tầng 3 - Đơn mua**, Điểm khớp 0,8, Trạng thái Đã khớp.</li><li>Hợp đồng khung và Mã dòng D4Nxx-HDKxx2026-VTTH-001.</li></ul> | ☐ |
| C2 | Bấm **Tạo Hóa đơn mua nháp** | Thông báo xanh "Đã tạo Hóa đơn mua nháp ACC-PINV-…". Phiếu → **Đã tạo nháp hóa đơn mua**; có nút **Mở Hóa đơn mua**; bảng dòng và ô tệp bị khóa | ☐ |
| C3 | Mở hóa đơn mua | **Nháp**. Số hóa đơn nhà cung cấp 00000001, ngày hóa đơn = hôm nay; ô **Phiếu tiếp nhận hóa đơn** = phiếu C1.<br>Dòng: DEMO-HDK-01, 500 × 12.500, gắn Đơn mua A và Phiếu nhập A. Mở dòng: Tên trên hóa đơn NCC, Hợp đồng khung, Mã dòng hợp đồng, Cách khớp, Điểm khớp.<br>Mục đối soát Đợt 3: **Khớp**. Tổng 6.875.000; có tệp A_tang3_ten_khac.xml đính kèm | ☐ |
| C4 | Mở `/app/supplier-item-alias` (**Bảng ánh xạ tên hàng NCC**) | Một dòng **Chờ duyệt** (cam):<ul><li>NCC demo, Tên trên hóa đơn "Sonde Foley 2 way size 16";</li><li>Tên chuẩn hóa "ong thong foley 2 nhanh 16";</li><li>Mặt hàng DEMO-HDK-01, Nguồn "Khớp theo Đơn mua";</li><li>Phiếu tiếp nhận đề xuất = phiếu C1.</li></ul> | ☐ |
| C5 | `demo.ketoan` **Nộp** hóa đơn C3 | Nộp được (công tắc ĐNTT của Đợt 3 đang bật nên có thêm "Đã tạo đề nghị thanh toán nháp ACC-PRQ-…"). Phiếu C1 → **Đã ghi sổ**. Hợp đồng 1, dòng 001: **Đã lập hóa đơn (ĐVT kho)** = 500 | ☐ |
| C6 | `demo.nvmuahang` lập phiếu mới, tải **lại đúng tệp A** | **Từ chối** (đỏ): "Từ chối: Hóa đơn C26TDM 00000001 đã được tiếp nhận ở phiếu TNHD-…" (số phiếu C1). Dòng không được đối soát | ☐ |
| C7 | (Tùy chọn) Administrator **Hủy** hóa đơn C3 | Phiếu C1 về **Đã đối soát**, ô Hóa đơn mua trống, dòng thời gian ghi "Hóa đơn mua … đã hủy."; Đã lập hóa đơn của dòng 001 giảm 500 (về 0 nếu làm ngay sau C5; còn 42 nếu đã làm mục L). ĐNTT nháp bị xóa theo Đợt 3 | ☐ |

## D. Khớp theo mã (tầng 1) và nghi trùng (kịch bản B, M, N)

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| D1 | Lập phiếu với **B_tang1_ma_ncc.xml** | **Đã đối soát**. Tổng 2.750.000. Dòng: Mã trên hóa đơn **NCC-FL216** (mã hàng của NCC trên thẻ mặt hàng và trong hợp đồng), tên "Foley catheter 2-way 16Fr" → DEMO-HDK-01, **Tầng 1 - Mã**, Điểm 1, Đã khớp | ☐ |
| D2 | Lập phiếu với **M_nghi_trung.xml** (cùng ngày, cùng tổng tiền với B, khác số hóa đơn) | **Chờ xử lý thủ công** (cam); dòng giới thiệu cam "Còn dòng chưa khớp / chờ xác nhận hoặc cảnh báo chưa xử lý…". Ô **Nghi trùng hóa đơn** tích; Cảnh báo của phiếu: "Nghi trùng: TNHD-… cùng nhà cung cấp, cùng ngày, cùng tổng tiền. Kiểm rồi tích Đã kiểm, không trùng." Dòng vẫn Đã khớp (tầng 1). Không có nút Tạo Hóa đơn mua nháp | ☐ |
| D3 | Tích **Đã kiểm, không trùng** → Lưu | **Đã đối soát**; có nút Tạo Hóa đơn mua nháp | ☐ |
| D4 | Lập phiếu với **N_ngoai_hdk.xml** (Băng dính, mã trên hóa đơn là mã hàng Miyano DEMO-HDK-09) | **Đã đối soát**. Dòng: **Tầng 1 - Mã**, Đã khớp; Hợp đồng khung trống; Cảnh báo "Không thuộc hợp đồng khung còn hiệu lực." (chỉ ghi chú, không chặn) | ☐ |

## E. Bảng ánh xạ tên (kịch bản C1, C2)

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| E1 | Lập phiếu với **C1_anh_xa_lan_1.xml** ("Găng khám Nitrile size M", 100 × 2.000) | **Đã đối soát**, tổng 220.000. Dòng → DEMO-HDK-03, **Tầng 3 - Đơn mua**, Điểm 1. Điểm 1 vì sau chuẩn hóa hai tên giống hệt: "găng khám" = "găng tay khám", bỏ "size" / "cỡ" | ☐ |
| E2 | **Tạo Hóa đơn mua nháp** | Tạo được. Bảng ánh xạ tên có dòng **Chờ duyệt**: "Găng khám Nitrile size M" → DEMO-HDK-03, tên chuẩn hóa "gang tay kham nitrile m" | ☐ |
| E3 | Lập phiếu với **C2_anh_xa_lan_2.xml** (cùng tên, 120 × 2.000) | **Đã đối soát**, tổng 264.000; Cách khớp vẫn **Tầng 3 - Đơn mua** (ánh xạ Chờ duyệt chưa được dùng). Chưa tạo hóa đơn | ☐ |
| E4 | `demo.nvmuahang` mở dòng ánh xạ E2 → bấm **Duyệt** | Bị chặn: "Bạn không có vai trò duyệt Bảng ánh xạ tên." | ☐ |
| E5 | `demo.giamdoc` bấm **Duyệt** (trên form, hoặc tích dòng ở danh sách → Thao tác → Duyệt) | **Đang dùng** (xanh lá); Người duyệt = demo.giamdoc, có Thời điểm duyệt. Nút Duyệt ẩn, còn nút **Ngừng dùng** | ☐ |
| E6 | Mở lại phiếu E3 → **Lưu** | Đối soát lại: Cách khớp **Tầng 2 - Ánh xạ tên**, Điểm 1 | ☐ |
| E7 | **Tạo Hóa đơn mua nháp** từ phiếu E3 | Tạo được. Dòng ánh xạ: Số lần dùng 1, có Lần dùng cuối | ☐ |
| E8 | `demo.nvmuahang` mở dòng ánh xạ E5 (Đang dùng), đổi **Mặt hàng** = DEMO-HDK-02 → Lưu | Thông báo cam "Ánh xạ đã duyệt vừa bị sửa nên chuyển về Chờ duyệt, cần người duyệt ánh xạ duyệt lại." Trạng thái **Chờ duyệt**, ô Người duyệt / Thời điểm duyệt trống; tầng 2 không dùng dòng này tới khi duyệt lại | ☐ |
| E9 | `demo.giamdoc` đổi Mặt hàng về DEMO-HDK-03 → Lưu → **Duyệt** | **Đang dùng**, Người duyệt = demo.giamdoc. (Giám đốc sửa một dòng đang Đang dùng thì dòng giữ Đang dùng: coi như duyệt lại) | ☐ |

## F. Khác quy cách → chọn tay (kịch bản D)

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| F1 | Lập phiếu với **D_khac_quy_cach.xml** ("Gạc phẫu thuật 7,5cm x 7,5cm", 100 × 5.000; Đơn mua D là gạc 10cm x 10cm cùng giá, cùng số lượng) | **Chờ xử lý thủ công**; Tỷ lệ khớp tự động 0%. Dòng **Chưa khớp**, Cảnh báo "Không khớp được ở tầng 1 – 3: chọn mặt hàng (tầng 4)." Gạc 7,5cm không bao giờ tự khớp gạc 10cm | ☐ |
| F2 | Giả sử đã kiểm hàng thật và NCC ghi nhầm quy cách: ở dòng 1 chọn **Mặt hàng** = DEMO-HDK-02 → Lưu | Ô **Chọn tay** tự tích. Dòng **Đã khớp**, Cách khớp **Chọn tay**, Điểm 0,76, gắn Đơn mua D và dòng hợp đồng 002 (Đơn mua D gắn hợp đồng gốc nên giá so là 5.000, không phải giá phụ lục). Phiếu **Đã đối soát**; Tỷ lệ khớp tự động vẫn 0% (chọn tay không tính là tự động) | ☐ |

## G. Cảnh báo chặn theo hợp đồng khung (kịch bản E, F)

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| G1 | Lập phiếu với **E_lech_gia_hdk.xml** (Đơn mua E và hóa đơn giá 13.000; hợp đồng 12.500) | **Chờ xử lý thủ công**, tổng 1.430.000. Dòng: Tầng 1 - Mã, Đã khớp, ô **Cảnh báo chặn** tích, Cảnh báo "Đơn giá 13.000 khác giá hợp đồng khung 12.500 (D4Nxx-HDKxx2026-VTTH-001)." Không có nút Tạo Hóa đơn mua nháp | ☐ |
| G2 | `demo.nvmuahang` xem phiếu G1 | Không có nút **Duyệt cảnh báo** | ☐ |
| G3 | `demo.giamdoc` bấm **Duyệt cảnh báo** → để trống Lý do duyệt → Duyệt | Không duyệt được (ô lý do bắt buộc) | ☐ |
| G4 | Nhập lý do "Ban Điều hành đồng ý giá mới từ 01/11" → **Duyệt** | **Đã đối soát**. Hiện Lý do duyệt cảnh báo, Người duyệt = demo.giamdoc, Thời điểm duyệt. Cảnh báo trên dòng vẫn giữ để lưu vết | ☐ |
| G5 | **Tạo Hóa đơn mua nháp** | Hóa đơn 100 × 13.000, tổng 1.430.000, đối soát Đợt 3: **Khớp** (Phiếu nhập E cũng 13.000) | ☐ |
| G6 | Lập phiếu với **F_vuot_han_muc.xml** (Bơm tiêm: hợp đồng 100, Đơn mua và Phiếu nhập 100, hóa đơn 120; mã trên hóa đơn là **mã dòng hợp đồng** D4Nxx-HDKxx2026-VTTH-004) | **Chờ xử lý thủ công**, tổng 396.000. Dòng: **Tầng 1 - Mã** (khớp theo mã dòng hợp đồng), Cảnh báo chặn: "Vượt hạn mức hợp đồng khung: còn 100, hóa đơn 120 (ĐVT kho)." | ☐ |
| G7 | `demo.giamdoc` Duyệt cảnh báo (lý do bất kỳ) → **Tạo Hóa đơn mua nháp** | Phiếu Đã đối soát rồi tạo được hóa đơn nháp. Hóa đơn hiện thông báo cam "Hóa đơn lệch Phiếu nhập mua ở 1 điểm (xem Bảng chênh lệch). Chưa Nộp được."<br>Đối soát Đợt 3: **Lệch** — Số lượng, Phiếu nhập "100 Cái", Hóa đơn "120 Cái".<br>Duyệt vượt hợp đồng không thay cho đối soát Phiếu nhập. Hóa đơn cao hơn Phiếu nhập thì không duyệt ngoại lệ được (Đợt 3): NCC phải xuất hóa đơn điều chỉnh | ☐ |

## H. Từ chối (kịch bản G)

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| H1 | Lập phiếu với **G_sai_mst_nguoi_mua.xml** | **Từ chối** (đỏ): "Từ chối: MST người mua trên hóa đơn (0100000000) khác MST của công ty (0109529507)." Dòng không được đối soát | ☐ |

Trường hợp hóa đơn đã tiếp nhận: xem C6.

## I. Tổng tiền không khớp (kịch bản I)

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| I1 | Lập phiếu với **I_lech_so_hoc.xml** (50 × 12.500 = 625.000, thuế 62.500, nhưng tổng thanh toán ghi 688.500) | **Chờ xử lý thủ công**. Ô **Tổng tiền không khớp các dòng** tích; Cảnh báo của phiếu "Số học trên hóa đơn không cân đối: tổng thanh toán 688.500 khác tiền hàng + thuế." Dòng vẫn Đã khớp (tầng 3) | ☐ |
| I2 | Kiểm hóa đơn gốc, tích **Đã kiểm tổng tiền** → Lưu | **Đã đối soát** | ☐ |

## J. Chưa có Phiếu nhập, hóa đơn từng phần, nhiều ứng viên (kịch bản J, K, L)

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| J1 | Lập phiếu với **J_chua_phieu_nhap.xml** (Đơn mua J chưa nhập kho) → **Tạo Hóa đơn mua nháp** | Phiếu **Đã đối soát** (khớp Đơn mua J, tổng 412.500). Tạo hóa đơn bị chặn "Chưa tạo được Hóa đơn mua": "Dòng 1 (DEMO-HDK-01): chưa có Phiếu nhập mua cho Đơn mua PUR-ORD-… Chờ Kho nhập hàng." Phiếu vẫn Đã đối soát | ☐ |
| J2 | Administrator (Kho) mở Đơn mua J → **Tạo → Phiếu nhập mua** → Lưu → Nộp. Quay lại phiếu J1 bấm lại **Tạo Hóa đơn mua nháp** | Tạo được; hóa đơn 30 × 12.500, gắn Phiếu nhập vừa nhập, tổng 412.500, **Khớp** | ☐ |
| J3 | Lập phiếu với **K_tung_phan.xml** (hóa đơn 300; Đơn mua và Phiếu nhập K là 500) → **Tạo Hóa đơn mua nháp** | Tạo được. Hóa đơn tích **Hóa đơn từng phần**, đối soát **Khớp**, tổng 4.125.000; thông báo "Hóa đơn từng phần. Còn chờ hóa đơn tiếp theo của nhà cung cấp: MAT-PRE-… · DEMO-HDK-01: 200 Cái" | ☐ |
| J4 | `demo.ketoan` xóa hóa đơn J3. Sau đó `demo.ketoantruong` **Xóa** hóa đơn J3 | `demo.ketoan` không xóa được (không có quyền). `demo.ketoantruong` xóa được. Phiếu J3 về **Đã đối soát**, ô Hóa đơn mua trống, dòng thời gian ghi "Hóa đơn mua nháp ACC-PINV-… đã xóa." Bấm lại Tạo Hóa đơn mua nháp được | ☐ |
| J5 | Lập phiếu với **L_nhieu_ung_vien.xml** (Đơn mua L có 2 dòng: DEMO-HDK-01 và DEMO-HDK-07, cùng tên theo hợp đồng, cùng giá; hóa đơn 250) | **Chờ xử lý thủ công**. Dòng **Chưa khớp**: "Nhiều dòng Đơn mua có thể khớp (PUR-ORD-… · DEMO-HDK-01, PUR-ORD-… · DEMO-HDK-07): chọn tay." Hệ thống không tự chọn | ☐ |
| J6 | Chọn **Mặt hàng** = DEMO-HDK-07 → Lưu | Dòng Đã khớp, **Chọn tay**, gắn dòng hợp đồng 005 (D4Nxx-HDKxx2026-VTTH-005). Phiếu **Đã đối soát** | ☐ |

## K. Hợp đồng giá đã gồm VAT, không cam kết số lượng (kịch bản O, P, Q — hợp đồng 2)

Hợp đồng 2 giống mẫu Greentech:
- Đơn giá 3.949.000 / hộp đã gồm VAT 5%, quy về chưa VAT là 3.760.952.
- Mức giá 10 – 30 hộp/đơn (3.812.500 gồm VAT) chỉ ghi ở Ghi chú giá.
- Không cam kết số lượng.

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| K1 | Mở Đơn mua kịch bản O (7 hộp). Tạo thử Đơn mua mới DEMO-HDK-08 SL 7, tự tích **Theo đơn khung** → Lưu | Đơn mua O: Đơn giá **3.760.952** (chưa VAT); dòng gắn hợp đồng 2, Đơn giá đơn khung 3.760.952; không có cảnh báo hạn mức dù hợp đồng ghi Số lượng 0. Đơn mới: Đơn giá lấy 3.760.952 từ bảng giá mua; khi tích, ERPNext điền Đơn giá đơn khung 3.949.000 (giá gồm VAT trên hợp đồng), Lưu xong thì về 3.760.952 | ☐ |
| K2 | Lập phiếu với **O_gia_gom_vat.xml** (7 hộp × 3.760.952, thuế suất 5%, mã hàng NCC 5002) | **Đã đối soát**. Dòng: **Tầng 1 - Mã** (mã hàng NCC ghi trong hợp đồng), Đã khớp, không cảnh báo, Hợp đồng khung = hợp đồng 2, mã dòng D4Nxx-NTxx-VTTH-001 | ☐ |
| K3 | **Tạo Hóa đơn mua nháp** | Hóa đơn 7 × 3.760.952, mẫu thuế "GTGT mua vào 5%", đối soát Đợt 3: **Khớp** (Đơn mua, Phiếu nhập và hóa đơn cùng giá chẵn đồng) | ☐ |
| K4 | Lập phiếu với **P_gia_bac_2.xml** (12 hộp × 3.630.952 = giá 10 – 30 hộp quy về chưa VAT) | **Chờ xử lý thủ công**. Dòng: Tầng 1 - Mã, **Cảnh báo chặn**: "Đơn giá 3.630.952 khác giá hợp đồng khung 3.760.952 (chưa VAT; hợp đồng ghi 3.949.000 đã gồm VAT 5%) (D4Nxx-NTxx-VTTH-001)." Hệ thống chỉ dùng một đơn giá của dòng; mức giá khác phải được duyệt | ☐ |
| K5 | `demo.giamdoc` **Duyệt cảnh báo**, lý do "Đơn 12 hộp theo giá 10 - 30 hộp của hợp đồng" | **Đã đối soát** | ☐ |
| K6 | Lập phiếu với **Q_dung_sai_1_dong.xml** (Đầu côn DC200: hợp đồng 5.250 gồm VAT = 5.000 chưa VAT; Đơn mua và Phiếu nhập 10 × 5.000; hóa đơn 10 × **5.001**) | **Đã đối soát**, tổng 52.510,5. Dòng Tầng 1 - Mã, không cảnh báo: lệch 1 đồng nằm trong dung sai của hợp đồng giá gồm VAT | ☐ |
| K7 | **Tạo Hóa đơn mua nháp** | Hóa đơn 10 × 5.001, đối soát Đợt 3: **Khớp** (dung sai 1 đồng / đơn vị). Có thể hiện cảnh báo cam chuẩn của ERPNext "Rate must be same as Purchase Order / Purchase Receipt (5001.0 / 5000.0)": chỉ cảnh báo, không chặn | ☐ |
| K8 | `demo.ketoan` **Nộp** hóa đơn K7 | Nộp được, không bị chặn "over limit" dù hóa đơn cao hơn thành tiền Đơn mua 0,02%. Lệch 2 đồng trở lên thì phiếu báo lệch giá và Đợt 3 báo Lệch như thường | ☐ |

## L. Kho nhận thiếu → Lệch PR-PI → hóa đơn điều chỉnh (kịch bản R)

Đơn mua R đặt 44 Ống thông Foley; Kho chỉ nhận **42** (Phiếu nhập R). Hóa đơn R1 (số 00000018) vẫn ghi 44 × 12.500. NCC sau đó xuất hóa đơn điều chỉnh giảm R2 (số 00000019): −2 × 12.500.

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| L1 | `demo.nvmuahang` lập phiếu với **R1_lech_pr_pi.xml** | **Đã đối soát**. Tính chất hóa đơn **Hóa đơn gốc**. Tổng 550.000 / 55.000 / 605.000. Dòng: Tầng 3 - Đơn mua, Đã khớp | ☐ |
| L2 | Bấm **Tạo Hóa đơn mua nháp** | Thông báo cam "Hóa đơn lệch Phiếu nhập mua ở 1 điểm (xem Bảng chênh lệch). Chưa Nộp được." rồi thông báo xanh "Đã tạo Hóa đơn mua nháp ACC-PINV-…". Phiếu → **Lệch PR-PI** (đỏ), dòng giới thiệu đỏ "Hóa đơn mua ACC-PINV-… lệch Phiếu nhập mua. Mở Hóa đơn mua, xem Bảng chênh lệch và xử lý theo nhánh; khớp lại thì phiếu tự về Đã tạo nháp hóa đơn mua." Dòng thời gian: "Hóa đơn mua ACC-PINV-… lệch Phiếu nhập mua: phiếu chuyển Lệch PR-PI." | ☐ |
| L3 | Mở hóa đơn mua L2 | Nháp, 44 × 12.500. **Đối soát Phiếu nhập: Lệch**. Bảng chênh lệch 1 dòng: Dòng 1 · Số lượng · Phiếu nhập "42 Cái", Hóa đơn "44 Cái", mức lệch 2, gợi ý "(b1) Phiếu nhập mua sai". Vài giây sau, **Supply Notification Dispatch Log** có dòng **NTF-16** cho hóa đơn này (người nhận demo.nvmuahang; production thêm phòng Mua hàng) | ☐ |
| L4 | Mở danh sách **Phiếu tiếp nhận hóa đơn NCC**, lọc Trạng thái = **Lệch PR-PI** | Thấy phiếu L1, nhãn đỏ. Đây là danh sách hóa đơn đang kẹt, không phải mở từng hóa đơn mua | ☐ |
| L5 | Giả sử Kho nhận đúng 42 và NCC đồng ý xuất hóa đơn điều chỉnh. `demo.nvmuahang` lập phiếu với **R2_dieu_chinh_giam.xml** | **Đã đối soát**. Tính chất hóa đơn **Điều chỉnh**; mục **Hóa đơn bị thay thế / bị điều chỉnh**: Ký hiệu C26TDM, Số 00000018, Ngày hôm nay, Phiếu tiếp nhận của hóa đơn đó = phiếu L1, Hóa đơn mua của hóa đơn đó = hóa đơn L2. Tổng −25.000 / −2.500 / −27.500. Dòng: Số lượng −2, **Dòng hóa đơn gốc (STT)** 1, **Điều chỉnh theo** Số lượng, Cách khớp "Dòng hóa đơn gốc", Mặt hàng DEMO-HDK-01. Dòng giới thiệu xanh "Hóa đơn điều chỉnh của phiếu TNHD-…". Có nút **Lập lại Hóa đơn mua nháp (gốc + điều chỉnh)** và **Mở phiếu hóa đơn gốc**. Phiếu L1 vẫn Lệch PR-PI | ☐ |
| L6 | `demo.nvmuahang` bấm **Lập lại Hóa đơn mua nháp (gốc + điều chỉnh)** → xác nhận | Hộp xác nhận "Hóa đơn mua nháp hiện có của hóa đơn gốc sẽ bị xóa và lập lại theo số sau điều chỉnh. Tiếp tục?". Bấm Có thì bị chặn: "Bạn không có quyền xóa Hóa đơn mua nháp ACC-PINV-…: nhờ Kế toán xóa rồi làm lại." Không có gì thay đổi | ☐ |
| L7 | `demo.ketoantruong` mở phiếu L5, bấm lại nút đó → xác nhận | "Đã tạo Hóa đơn mua nháp ACC-PINV-…" (số có thể trùng số bản vừa xóa). Phiếu L1 và L5: **Đã tạo nháp hóa đơn mua**, cùng trỏ vào hóa đơn này. Phiếu L1, dòng 1: Số lượng sau điều chỉnh **42**, Đơn giá sau điều chỉnh 12.500, Thành tiền sau điều chỉnh 525.000, Hóa đơn điều chỉnh đã gộp "C26TDM 00000019 (Số lượng): số lượng -2, thành tiền -25.000". Dòng thời gian phiếu L5: "Gộp vào Hóa đơn mua nháp ACC-PINV-… của hóa đơn gốc TNHD-…" | ☐ |
| L8 | Mở hóa đơn mua L7 | Số hóa đơn NCC **00000018** (số hóa đơn gốc); ô **Hóa đơn điều chỉnh đã gộp** "C26TDM 00000019 ngày dd-mm-yyyy (phiếu TNHD-…)". 42 × 12.500, tổng 525.000 / 52.500 / 577.500. **Đối soát Phiếu nhập: Khớp**. Đính kèm hai tệp R1_lech_pr_pi.xml và R2_dieu_chinh_giam.xml | ☐ |
| L9 | `demo.ketoan` **Nộp** hóa đơn L8 | Nộp được, "Đã tạo đề nghị thanh toán nháp ACC-PRQ-…". Phiếu L1 và L5: **Đã ghi sổ**. Hợp đồng 1, dòng 001: Đã lập hóa đơn tăng **42** (số sau điều chỉnh) | ☐ |

Hóa đơn gốc **đã ghi sổ** rồi mới có hóa đơn điều chỉnh (không có trong demo): phiếu điều chỉnh dừng ở Chờ xử lý thủ công, cảnh báo "Hóa đơn gốc … đã ghi sổ ở Hóa đơn mua …. Kế toán lập tay Hóa đơn mua trả hàng (điều chỉnh giảm) hoặc Hóa đơn mua bổ sung (điều chỉnh tăng), Số hóa đơn NCC ghi …; phiếu này tự nối vào chứng từ đó." Kế toán lập chứng từ (ví dụ từ hóa đơn gốc: **Tạo → Trả hàng / Ghi nợ**), ghi Số hóa đơn NCC = số hóa đơn điều chỉnh, Lưu: phiếu tự chuyển Đã tạo nháp hóa đơn mua, Nộp chứng từ đó thì Đã ghi sổ. Hóa đơn điều chỉnh đổi thuế suất, hoặc hóa đơn gốc nhập tay không qua phiếu: phiếu dừng ở Chờ xử lý thủ công, kế toán xử lý tay rồi **Từ chối** phiếu.

## M. Hóa đơn thay thế (kịch bản S)

Hóa đơn S1 (số 00000020, 60 × 12.500) có sai sót; NCC xuất hóa đơn S2 (số 00000021) thay thế S1, cùng ngày, cùng số tiền.

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| M1 | `demo.nvmuahang` lập phiếu với **S1_bi_thay_the.xml** → **Tạo Hóa đơn mua nháp** | Phiếu Đã đối soát rồi Đã tạo nháp hóa đơn mua; hóa đơn mua Khớp | ☐ |
| M2 | Lập phiếu với **S2_thay_the.xml** | **Chờ xử lý thủ công**. Tính chất hóa đơn **Thay thế**, hóa đơn bị thay thế C26TDM 00000020, Phiếu tiếp nhận của hóa đơn đó = phiếu M1. Cảnh báo của phiếu: "Hóa đơn bị thay thế C26TDM 00000020 đang có Hóa đơn mua nháp ACC-PINV-… (phiếu TNHD-…): bấm Bỏ hóa đơn bị thay thế để xóa bản nháp đó; phiếu TNHD-… chuyển Từ chối." Không bị báo nghi trùng dù cùng ngày, cùng tổng tiền với S1. Có nút **Bỏ hóa đơn bị thay thế** | ☐ |
| M3 | `demo.nvmuahang` bấm **Bỏ hóa đơn bị thay thế** → xác nhận. Sau đó `demo.ketoantruong` làm lại | `demo.nvmuahang`: "Bạn không có quyền xóa Hóa đơn mua nháp ACC-PINV-…: nhờ Kế toán xóa rồi làm lại." `demo.ketoantruong`: hóa đơn mua M1 bị xóa; phiếu S2 → **Đã đối soát**; phiếu M1 → **Từ chối**: "Hóa đơn đã bị thay thế bởi hóa đơn C26TDM 00000021 (phiếu TNHD-…)." | ☐ |
| M4 | Mở phiếu M1: không còn nút Tạo Hóa đơn mua nháp. Trên phiếu S2 bấm **Tạo Hóa đơn mua nháp** | Hóa đơn mua Số hóa đơn NCC **00000021**, 60 × 12.500, Khớp | ☐ |
| M5 | (Tùy chọn) `demo.ketoantruong` bấm **Từ chối** trên phiếu S2, lý do "NCC gửi nhầm hóa đơn thay thế" | Hóa đơn mua M4 bị xóa, phiếu S2 Từ chối tay; phiếu M1 tự mở lại về **Đã đối soát** | ☐ |

Hóa đơn bị thay thế **đã ghi sổ**: phiếu thay thế dừng ở Chờ xử lý thủ công, cảnh báo "… đã ghi sổ ở Hóa đơn mua …: hủy hóa đơn mua đó (gỡ thanh toán, Đề nghị thanh toán nếu có) rồi Lưu lại phiếu này." Hủy xong, phiếu thay thế tự đối soát tiếp và phiếu cũ chuyển Từ chối. Hóa đơn bị thay thế chưa từng tiếp nhận: phiếu thay thế đi tiếp, chỉ ghi "Thay thế hóa đơn …; hóa đơn đó chưa có trên hệ thống."

## N. Từ chối tay

Dùng phiếu D4 (**N_ngoai_hdk.xml**, Đã đối soát). Giả sử NCC báo hủy hóa đơn này.

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| N1 | `demo.nvmuahang` mở phiếu D4 → **Từ chối**. Để trống Lý do từ chối → Từ chối; rồi nhập "NCC báo hủy hóa đơn, sẽ xuất lại" → **Từ chối** | Để trống: không gửi được (ô bắt buộc). Có lý do: phiếu **Từ chối** (đỏ), dòng giới thiệu "Từ chối tay bởi … : NCC báo hủy hóa đơn, sẽ xuất lại"; hiện Người từ chối, Thời điểm từ chối. Ô tệp và dòng hàng khóa. Có nút **Mở lại**, không còn nút Từ chối | ☐ |
| N2 | Bấm **Lưu** (hoặc sửa ô khác rồi Lưu) | Vẫn Từ chối: Lưu không tính lại phiếu Từ chối tay | ☐ |
| N3 | Bấm **Mở lại** | **Đã đối soát**; ô lý do, người, thời điểm từ chối trống. Dòng thời gian ghi "Từ chối tay: …" và "Mở lại phiếu đã Từ chối tay." | ☐ |
| N4 | **Tạo Hóa đơn mua nháp** từ phiếu D4. `demo.nvmuahang` bấm **Từ chối** | Hộp thoại có dòng đỏ "Hóa đơn mua nháp ACC-PINV-… của phiếu sẽ bị xóa." Bấm Từ chối: "Bạn không có quyền xóa Hóa đơn mua nháp …: nhờ Kế toán xóa rồi làm lại." | ☐ |
| N5 | `demo.ketoantruong` làm lại N4 | Hóa đơn mua bị xóa, phiếu Từ chối tay (người từ chối demo.ketoantruong) | ☐ |
| N6 | Mở phiếu C1 (Đã ghi sổ ở C5) | Không có nút Từ chối. Muốn từ chối phải hủy hóa đơn mua trước | ☐ |

## O. Tắt công tắc

Làm sau cùng.

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| O1 | Administrator bỏ tích **Bật tiếp nhận hóa đơn** → Lưu. Mở phiếu F1 → Lưu | Bị chặn: "Tiếp nhận hóa đơn đang tắt (Cài đặt tiếp nhận hóa đơn)." Bật lại sau khi thử | ☐ |
| O2 | Ở `sites` chạy `../env/bin/python ../apps/erpnext/scripts/demo_tiep_nhan_hoa_don.py --site erpnext.localhost --tra-lai` | In các cài đặt được trả về như trước lần chạy demo đầu (MST người mua, vai trò duyệt…). Dữ liệu demo giữ nguyên | ☐ |

## P. Xử lý sự cố thường gặp

| Hiện tượng | Nguyên nhân | Cách xử lý |
|---|---|---|
| Mở `/app/supplier-invoice-intake` báo lỗi, hoặc Đơn khung không có mục Các bên ký hợp đồng / Cài đặt không có mục Hợp đồng khung | Thư mục chính của bench chưa có code Đợt 4, hoặc chưa `migrate` | Đưa nhánh Đợt 4 vào thư mục chính, chạy `bench --site erpnext.localhost migrate` rồi `clear-cache` |
| Tên DocType, nhãn "Order No" và câu chặn vượt hạn mức hiện tiếng Anh | Bản dịch nằm trong cache | `bench --site erpnext.localhost clear-cache`, tải lại trang |
| Lưu phiếu báo "Chưa đọc được hóa đơn" | Tệp không phải XML hóa đơn điện tử (không có `HDon/DLHDon`). Ảnh / PDF chưa hỗ trợ ở phần 1 | Tải tệp XML gốc của hóa đơn |
| Phiếu không tự nhận NCC: "Không có nhà cung cấp nào mang MST …" | NCC chưa có MST (Tax ID), hoặc có hai NCC cùng MST | Điền MST cho NCC, hoặc chọn Nhà cung cấp trên phiếu rồi Lưu |
| Đơn mua không tự gắn Đơn khung; hộp cam "Nhiều hợp đồng khung cùng hiệu lực, chưa tự gắn…" | NCC có hai hợp đồng khung cùng hiệu lực chứa mặt hàng (không phải gốc – phụ lục của nhau) | Chọn Đơn khung trên dòng Đơn mua |
| Nộp Đơn khung báo thiếu Bảng giá mua | NCC chưa có bảng giá mặc định là bảng giá mua | Chọn Bảng giá mua trên Đơn khung |
| Không Hủy được Đơn khung | Đã có Đơn mua liên kết (ERPNext chặn) | Giữ hợp đồng; đổi nội dung bằng phụ lục, gia hạn bằng Đến ngày |
| Không thấy nút Nộp / không sửa được Đến ngày | Người dùng không có vai trò Sales Manager | Giám đốc (Sales Manager) Nộp và gia hạn. Quyền tạo ở lần migrate đầu; quản trị đổi trong Role Permission Manager thì migrate sau không ghi đè |
| Nộp Đơn khung báo thiếu một trường mà hợp đồng của NCC này không có | Danh sách trường bắt buộc ở Cài đặt áp cho mọi hợp đồng | System Manager bỏ trường đó khỏi danh sách (Cài đặt tiếp nhận hóa đơn NCC → Chọn trường bắt buộc khi Nộp hợp đồng khung), hoặc ghi "Không có" vào ô |
| Hợp đồng của NCC có điều khoản không có ô riêng | Điều khoản riêng không phải trường cố định | Ghi vào Chi tiết điều khoản và điều kiện; lập Mẫu điều khoản cho NCC đó để dùng lại. Cần lọc / báo cáo theo một điều khoản thì quản trị thêm trường bằng Customize Form và chọn bắt buộc ở Cài đặt nếu cần |
| Phụ lục báo "Phụ lục đổi giá mặt hàng … phải có Từ ngày sau Từ ngày của hợp đồng gốc" | Phụ lục đổi giá cùng ngày bắt đầu với hợp đồng gốc | Đặt Từ ngày của phụ lục là ngày giá mới có hiệu lực |
| Không bấm được Lập lại Hóa đơn mua nháp / Bỏ hóa đơn bị thay thế / Từ chối phiếu có bản nháp: "Bạn không có quyền xóa Hóa đơn mua nháp …" | Các nút này xóa Hóa đơn mua nháp, cần quyền xóa Hóa đơn mua | Người có quyền xóa (demo: `demo.ketoantruong`) bấm; hoặc Kế toán xóa hóa đơn nháp trước, phiếu tự tính lại |
| Phiếu điều chỉnh "Chọn Dòng hóa đơn gốc (STT 1 – n) mà dòng này điều chỉnh." | Không nhận ra dòng gốc theo mã / tên, hóa đơn gốc có nhiều dòng | Nhập STT dòng của hóa đơn gốc vào ô Dòng hóa đơn gốc → Lưu; kiểm ô Điều chỉnh theo (Số lượng / Đơn giá) |
| Hóa đơn của hợp đồng giá gồm VAT bị phiếu và Đợt 3 báo lệch đơn giá | Lệch hơn 1 đồng trên đơn giá hóa đơn (trong 1 đồng thì đã được bỏ qua) | Kiểm hóa đơn với NCC; giám đốc duyệt cảnh báo trên phiếu, Kế toán trưởng duyệt ngoại lệ ở Đợt 3 nếu chấp nhận |

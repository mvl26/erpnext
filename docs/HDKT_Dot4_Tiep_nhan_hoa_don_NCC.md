# Hướng dẫn test thủ công — Đợt 4: Hợp đồng khung, tiếp nhận hóa đơn NCC và đối soát 4 tầng (FRD-MAP-01, phần 1)

| Mục | Nội dung |
|---|---|
| Phạm vi | FRD-MAP-01 phần 1, spec `docs/superpowers/specs/2026-10-23-tiep-nhan-hoa-don-ncc-design.md`. Chưa có ở phần 1: đọc ảnh / PDF hóa đơn, ràng buộc Yêu cầu vật tư → Đơn mua, mẫu in / email đặt hàng có mã dòng hợp đồng |
| Site test | `erpnext.localhost` — `http://127.0.0.1:8000`. **Không test trên `miyano`.** |
| Nhánh | `feat/tiep-nhan-chung-tu-ncc` (đã gộp vào `feat/auto-check-selling-price`). Thư mục chính của bench phải có code Đợt 4, đã `migrate` và `clear-cache` |
| Dữ liệu | `scripts/demo_tiep_nhan_hoa_don.py`: mỗi lần chạy tạo một NCC demo mới kèm hợp đồng khung đã Nộp, Đơn mua hàng và Phiếu nhập mua đã Nộp cho từng kịch bản, và tệp XML hóa đơn điện tử. Phiếu tiếp nhận và hóa đơn mua do người test tự lập |
| Liên quan | Đợt 1: giá "HĐ nguyên tắc" khi kiểm giá bán. Đợt 3: đối soát Phiếu nhập ↔ Hóa đơn mua, ĐNTT nháp khi Nộp hóa đơn |

Quy tắc để đối chiếu khi test:

- **Hợp đồng khung** là **Đơn khung** (Blanket Order) có Loại đơn hàng = Purchasing.
  - Mỗi dòng có **Mã dòng hợp đồng** dạng `[NCC]-[Số hợp đồng]-[Nhóm hàng]-[STT]`, ví dụ `D4N01-HDK012026-VTTH-001`. Mã tự sinh khi lưu, sửa được trước khi Nộp, và không được trùng.
  - Muốn **Nộp** thì phải có Order No (số hợp đồng), Nhà cung cấp, Bảng giá mua.
  - Mỗi dòng phải có Tên theo hợp đồng, Quy cách, Hãng sản xuất, Nước sản xuất, Số lưu hành / công bố, Thuế suất GTGT, đơn giá > 0 và số lượng > 0.
- **Nộp** hợp đồng khung: giá từng dòng được ghi vào bảng giá mua của NCC. Đây là giá "HĐ nguyên tắc" mà kiểm giá bán dùng. **Hủy** hợp đồng khung: các giá này bị xóa.
- **Đơn mua hàng** tự gắn hợp đồng khung còn hiệu lực. Sau đơn mà số đã đặt đạt 90% hạn mức thì hệ thống cảnh báo; vượt hạn mức thì ERPNext chặn.
- **Phiếu tiếp nhận hóa đơn NCC**: tải tệp XML lên rồi **Lưu**. Hệ thống làm lần lượt:
  - đọc hóa đơn;
  - nhận NCC theo MST người bán;
  - từ chối nếu MST người mua sai hoặc hóa đơn đã tiếp nhận;
  - kiểm tổng tiền và nghi trùng;
  - đối soát từng dòng qua 4 tầng:
    - **Tầng 1 - Mã**: mã hàng Miyano, mã hàng của NCC hoặc mã dòng hợp đồng.
    - **Tầng 2 - Ánh xạ tên**: Bảng ánh xạ tên, chỉ dòng **Đang dùng**.
    - **Tầng 3 - Đơn mua**: dòng Đơn mua cùng ĐVT, cùng đơn giá, còn đủ số lượng, tên đủ giống. Điểm ≥ 0,75 thì Đã khớp; 0,55 – 0,75 thì Chờ xác nhận.
    - **Chọn tay**.
  - Quy cách (các con số, cỡ S / M / L) trong tên khác nhau thì **không bao giờ tự khớp**.
- **Cảnh báo chặn**: đơn giá khác giá hợp đồng khung, hoặc vượt hạn mức còn lại của hợp đồng.
  - Chỉ người có vai trò duyệt (demo: **DEMO Giám đốc**) mới có nút **Duyệt cảnh báo**, và phải nhập lý do.
  - Thuế suất / ĐVT khác hợp đồng, hoặc hàng ngoài hợp đồng khung: chỉ ghi chú, không chặn.
- Trạng thái phiếu (nhãn màu đầu form):
  - **Mới tiếp nhận**: xám;
  - **Đã trích xuất**: xanh dương;
  - **Đã đối soát**: xanh lá;
  - **Chờ xử lý thủ công**: cam;
  - **Đã tạo nháp hóa đơn mua**: xanh dương;
  - **Đã ghi sổ**: xanh lá;
  - **Từ chối**: đỏ.
- Hóa đơn mua tạo từ phiếu luôn là **nháp**; Kế toán kiểm rồi Nộp. Hóa đơn này đi tiếp qua đối soát Phiếu nhập ↔ Hóa đơn (Đợt 3) như hóa đơn nhập tay.

## 0. Chuẩn bị

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| 0.1 | Ở `sites` chạy:<br>`../env/bin/python ../apps/erpnext/scripts/demo_tiep_nhan_hoa_don.py --site erpnext.localhost` | In ra:<ul><li>các cài đặt vừa đổi (lần đầu có thêm dòng lưu cài đặt cũ);</li><li>tên NCC demo (lần đầu: **DEMO-D4 NCC 01**, MST 0109990001, mã viết tắt D4N01) và số hợp đồng khung;</li><li>5 mã dòng hợp đồng;</li><li>bảng 14 kịch bản (tệp XML, Đơn mua hàng, Phiếu nhập mua);</li><li>thư mục chứa tệp XML, kèm đường dẫn mở từ Windows: `\\wsl.localhost\Ubuntu-22.04\home\minhbitong\frappe\frappe-bench\sites\erpnext.localhost\private\demo_tiep_nhan_hoa_don\DEMO-D4_NCC_01`.</li></ul>Chạy lại được: mỗi lần tạo NCC mới (`DEMO-D4 NCC 02`…) và thư mục XML mới | ☐ |
| 0.2 | Thử chạy với `--site miyano` | Script từ chối: "Từ chối: không tạo dữ liệu demo trên site production." | ☐ |
| 0.3 | Mở `/app/supplier-invoice-intake-settings` (**Cài đặt tiếp nhận hóa đơn NCC**) | <ul><li>Bật tiếp nhận hóa đơn: tích.</li><li>MST người mua: 0109529507.</li><li>Cảnh báo khi đặt hàng đạt (% hạn mức hợp đồng khung): 90.</li><li>Vai trò duyệt lệch giá, vượt hạn mức: DEMO Giám đốc.</li><li>Vai trò duyệt Bảng ánh xạ tên: Purchase Manager.</li><li>Ngưỡng khớp tự động 0,75; Ngưỡng chờ xác nhận 0,55; Trọng số trùng từ 0,6; Trọng số giống chuỗi 0,4.</li><li>Từ đồng nghĩa có 4 dòng: sonde ↔ ống thông, 2 way ↔ 2 nhánh, dùng 1 lần ↔ dùng một lần, găng khám ↔ găng tay khám.</li><li>Từ bỏ qua: "size, cỡ, loại, cái".</li></ul> | ☐ |
| 0.4 | Mở hợp đồng khung in ở 0.1 (danh sách **Đơn khung**) | <ul><li>Đã Nộp; Order No "HĐK 01/2026"; Bảng giá mua "DEMO Mua - Hợp đồng khung".</li><li>5 dòng, mã dòng D4N01-HDK012026-VTTH-001 → 005 (VTTH là nhóm hàng của mặt hàng demo trên site này).</li><li>Mở một dòng: đủ Tên theo hợp đồng, Quy cách, Hãng, Nước, Số lưu hành, Thuế suất 10%.</li></ul> | ☐ |
| 0.5 | Mở danh sách **Giá mặt hàng**, lọc Nhà cung cấp = NCC demo | <ul><li>5 giá trong bảng giá "DEMO Mua - Hợp đồng khung", hiệu lực từ ngày đầu hợp đồng.</li><li>Ô **Hợp đồng khung** (chỉ đọc) trỏ về hợp đồng 0.4.</li><li>Ghi chú "Hợp đồng khung HĐK 01/2026, dòng D4N01-…".</li></ul> | ☐ |

Người dùng mẫu (Impersonate):

| Người dùng | Vai trò trong demo | Dùng ở bước |
|---|---|---|
| `demo.nvmuahang@example.com` | Nhân viên mua hàng | Lập phiếu tiếp nhận, tạo hóa đơn mua nháp; không duyệt được gì |
| `demo.chuoicungung@example.com` | Chuỗi cung ứng (Purchase Manager) | Duyệt Bảng ánh xạ tên |
| `demo.giamdoc@example.com` | Vai trò DEMO Giám đốc | Duyệt lệch giá / vượt hạn mức |
| `demo.ketoan@example.com` | Kế toán | Nộp hóa đơn mua |
| `demo.ketoantruong@example.com` | Kế toán trưởng | Xóa hóa đơn mua nháp |
| Administrator | System Manager | Hợp đồng khung (mặc định chỉ System Manager tạo / Nộp Đơn khung), Kho |

**Cách lập phiếu tiếp nhận** trong các bước dưới:
1. Vào `/app/supplier-invoice-intake/new`, đặt Công ty = Miyano.
2. Ở ô **Tệp hóa đơn (XML)** bấm Đính kèm, chọn tệp của kịch bản trong thư mục ở 0.1.
3. Bấm **Lưu**.

Mọi ô thông tin hóa đơn, NCC và Đơn mua hàng đều tự điền. Mỗi hóa đơn mẫu có ghi chú "Theo đơn đặt hàng PUR-ORD-…", nên phiếu chỉ khớp với Đơn mua của kịch bản đó.

Số chứng từ thay đổi mỗi lần chạy. Số hóa đơn (ký hiệu C26TDM, số 00000001 → 00000014) và số tiền dưới đây là cố định.

## A. Cài đặt và quyền

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| A1 | `demo.nvmuahang` mở Cài đặt tiếp nhận hóa đơn NCC | Các ô chỉ đọc, không có nút Lưu. Chỉ System Manager sửa được | ☐ |

## B. Hợp đồng khung

Làm bằng Administrator, chọn NCC demo in ở 0.1.

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| B1 | **Đơn khung → Mới**:<ul><li>Loại đơn hàng = Purchasing;</li><li>Nhà cung cấp = NCC demo;</li><li>Order No = `HĐK 05/2026`;</li><li>Từ ngày = hôm nay, Đến ngày = sau 1 năm;</li><li>dòng DEMO-HDK-05, Số lượng 100, Đơn giá 20.000.</li></ul>→ **Lưu** | Lưu được. **Bảng giá mua** tự điền "DEMO Mua - Hợp đồng khung" (bảng giá mặc định của NCC). Mở dòng 1: **Mã dòng hợp đồng** = `D4N01-HDK052026-VTTH-001`, ghép từ:<ul><li>mã viết tắt NCC;</li><li>Order No bỏ dấu và ký tự đặc biệt;</li><li>nhóm hàng;</li><li>STT.</li></ul> | ☐ |
| B2 | Bấm vào ô Bảng giá mua | Danh sách chỉ có bảng giá mua | ☐ |
| B3 | **Nộp** ngay | Bị chặn "Chưa Nộp được hợp đồng khung". Hợp đồng khung thiếu thông tin:<ul><li>Dòng 1: Tên theo hợp đồng</li><li>Dòng 1: Quy cách</li><li>Dòng 1: Hãng sản xuất</li><li>Dòng 1: Nước sản xuất</li><li>Dòng 1: Số lưu hành / công bố</li><li>Dòng 1: Thuế suất GTGT</li></ul> | ☐ |
| B4 | Mở dòng 1, nhập:<ul><li>Tên theo hợp đồng "Dây truyền dịch có kim 23G";</li><li>Quy cách "Dài 150cm";</li><li>Hãng sản xuất "DEMO Hãng F";</li><li>Nước sản xuất "Việt Nam";</li><li>Số lưu hành "DEMO-SLH-05";</li><li>Thuế suất GTGT 5%.</li></ul>→ Lưu → **Nộp** | Nộp được. Danh sách Giá mặt hàng lọc Mặt hàng = DEMO-HDK-05 có giá mới:<ul><li>bảng giá DEMO Mua - Hợp đồng khung, NCC demo, **20.000**, ĐVT Cái;</li><li>hiệu lực từ hôm nay đến sau 1 năm;</li><li>ô Hợp đồng khung = đơn khung B1;</li><li>ghi chú "Hợp đồng khung HĐK 05/2026, dòng D4N01-HDK052026-VTTH-001".</li></ul> | ☐ |
| B5 | Đơn khung mới: NCC demo, Order No `HĐK 06/2026`, dòng DEMO-HDK-06 SL 100 giá 1.000. Mở dòng, nhập Mã dòng hợp đồng = `D4N01-HDK052026-VTTH-001` → Lưu | Bị chặn: "Mã dòng hợp đồng đã dùng: D4N01-HDK052026-VTTH-001 (MFG-BLR-…)". Đóng, không lưu | ☐ |
| B6 | **Đơn mua hàng → Mới**: NCC demo, DEMO-HDK-05 SL **95**, Đơn giá 20.000 → **Lưu** | Dòng tự tích **Theo đơn khung**, Đơn khung = B1, Đơn giá đơn khung 20.000. Hộp cam "Sắp hết hạn mức hợp đồng khung": "Dòng 1 (DEMO-HDK-05): sau đơn này đã đặt 95/100 (95%) hạn mức hợp đồng khung MFG-BLR-…" | ☐ |
| B7 | **Nộp** Đơn mua B6. Mở lại Đơn khung B1 | Nộp được (cảnh báo hiện lại). Dòng 1 của B1: **Số lượng đã đặt** 95 | ☐ |
| B8 | Đơn mua hàng mới: DEMO-HDK-05 SL **10** → Lưu | ERPNext chặn: "Mặt hàng DEMO-HDK-05 không được đặt quá 5.0 theo đơn khung MFG-BLR-…" | ☐ |
| B9 | Đơn khung mới `HĐK 07/2026`, dòng DEMO-HDK-06 SL 100 giá 1.000, nhập đủ thông tin dòng → Nộp. Xem Giá mặt hàng của DEMO-HDK-06. Sau đó **Hủy** đơn khung này | Sau khi Nộp: có 1 giá 1.000 gắn Hợp đồng khung `HĐK 07/2026`. Sau khi Hủy: giá đó bị xóa. (Đơn khung B1 không Hủy được vì đã có Đơn mua B7 liên kết — hành vi chuẩn của ERPNext) | ☐ |

## C. Khớp theo Đơn mua (tầng 3) → hóa đơn mua nháp → Nộp (kịch bản A)

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| C1 | `demo.nvmuahang` lập phiếu với **A_tang3_ten_khac.xml** | **Đã đối soát** (xanh lá).<ul><li>Nhà cung cấp = NCC demo (tự nhận theo MST).</li><li>Đơn mua hàng = Đơn mua kịch bản A.</li><li>Ký hiệu C26TDM, Số hóa đơn 00000001.</li><li>Tổng tiền hàng 6.250.000, Tiền thuế 625.000, Tổng thanh toán 6.875.000.</li><li>Tỷ lệ khớp tự động 100%.</li></ul>Dòng 1:<ul><li>Tên trên hóa đơn "Sonde Foley 2 way size 16", không có mã.</li><li>Mặt hàng DEMO-HDK-01.</li><li>Cách khớp **Tầng 3 - Đơn mua**, Điểm khớp 0,8, Trạng thái Đã khớp.</li><li>Hợp đồng khung và Mã dòng D4N01-HDK012026-VTTH-001.</li></ul> | ☐ |
| C2 | Bấm **Tạo Hóa đơn mua nháp** | Thông báo xanh "Đã tạo Hóa đơn mua nháp ACC-PINV-…". Phiếu → **Đã tạo nháp hóa đơn mua**; có nút **Mở Hóa đơn mua**; bảng dòng và ô tệp bị khóa | ☐ |
| C3 | Mở hóa đơn mua | **Nháp**. Số hóa đơn nhà cung cấp 00000001, ngày hóa đơn = hôm nay; ô **Phiếu tiếp nhận hóa đơn** = phiếu C1.<br>Dòng: DEMO-HDK-01, 500 × 12.500, gắn Đơn mua A và Phiếu nhập A. Mở dòng: Tên trên hóa đơn NCC, Hợp đồng khung, Mã dòng hợp đồng, Cách khớp, Điểm khớp.<br>Mục đối soát Đợt 3: **Khớp**. Tổng 6.875.000; có tệp A_tang3_ten_khac.xml đính kèm | ☐ |
| C4 | Mở `/app/supplier-item-alias` (**Bảng ánh xạ tên hàng NCC**) | Một dòng **Chờ duyệt** (cam):<ul><li>NCC demo, Tên trên hóa đơn "Sonde Foley 2 way size 16";</li><li>Tên chuẩn hóa "ong thong foley 2 nhanh 16";</li><li>Mặt hàng DEMO-HDK-01, Nguồn "Khớp theo Đơn mua";</li><li>Phiếu tiếp nhận đề xuất = phiếu C1.</li></ul> | ☐ |
| C5 | `demo.ketoan` **Nộp** hóa đơn C3 | Nộp được (nếu công tắc ĐNTT của Đợt 3 đang bật: "Đã tạo đề nghị thanh toán nháp ACC-PRQ-…"). Phiếu C1 → **Đã ghi sổ**. Đơn khung của NCC demo, dòng 001: **Đã lập hóa đơn (ĐVT kho)** = 500 | ☐ |
| C6 | `demo.nvmuahang` lập phiếu mới, tải **lại đúng tệp A** | **Từ chối** (đỏ): "Từ chối: Hóa đơn C26TDM 00000001 đã được tiếp nhận ở phiếu TNHD-…" (số phiếu C1). Dòng không được đối soát | ☐ |
| C7 | (Tùy chọn) Administrator **Hủy** hóa đơn C3 | Phiếu C1 về **Đã đối soát**, ô Hóa đơn mua trống, dòng thời gian ghi "Hóa đơn mua … đã hủy."; Đã lập hóa đơn của dòng 001 về 0. ĐNTT nháp (nếu có) bị xóa theo Đợt 3 | ☐ |

## D. Khớp theo mã (tầng 1) và nghi trùng (kịch bản B, M, N)

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| D1 | Lập phiếu với **B_tang1_ma_ncc.xml** | **Đã đối soát**. Tổng 2.750.000. Dòng: Mã trên hóa đơn **NCC-FL216** (mã hàng của NCC trên thẻ mặt hàng DEMO-HDK-01), tên "Foley catheter 2-way 16Fr" → DEMO-HDK-01, **Tầng 1 - Mã**, Điểm 1, Đã khớp | ☐ |
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
| E5 | `demo.chuoicungung` bấm **Duyệt** (trên form, hoặc tích dòng ở danh sách → Thao tác → Duyệt) | **Đang dùng** (xanh lá); Người duyệt = demo.chuoicungung, có Thời điểm duyệt. Nút Duyệt ẩn, còn nút **Ngừng dùng** | ☐ |
| E6 | Mở lại phiếu E3 → **Lưu** | Đối soát lại: Cách khớp **Tầng 2 - Ánh xạ tên**, Điểm 1 | ☐ |
| E7 | **Tạo Hóa đơn mua nháp** từ phiếu E3 | Tạo được. Dòng ánh xạ: Số lần dùng 1, có Lần dùng cuối | ☐ |

## F. Khác quy cách → chọn tay (kịch bản D)

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| F1 | Lập phiếu với **D_khac_quy_cach.xml** ("Gạc phẫu thuật 7,5cm x 7,5cm", 100 × 5.000; Đơn mua D là gạc 10cm x 10cm cùng giá, cùng số lượng) | **Chờ xử lý thủ công**; Tỷ lệ khớp tự động 0%. Dòng **Chưa khớp**, Cảnh báo "Không khớp được ở tầng 1 – 3: chọn mặt hàng (tầng 4)." Gạc 7,5cm không bao giờ tự khớp gạc 10cm | ☐ |
| F2 | Giả sử đã kiểm hàng thật và NCC ghi nhầm quy cách: ở dòng 1 chọn **Mặt hàng** = DEMO-HDK-02 → Lưu | Ô **Chọn tay** tự tích. Dòng **Đã khớp**, Cách khớp **Chọn tay**, Điểm 0,76, gắn Đơn mua D và dòng hợp đồng 002. Phiếu **Đã đối soát**; Tỷ lệ khớp tự động vẫn 0% (chọn tay không tính là tự động) | ☐ |

## G. Cảnh báo chặn theo hợp đồng khung (kịch bản E, F)

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| G1 | Lập phiếu với **E_lech_gia_hdk.xml** (Đơn mua E và hóa đơn giá 13.000; hợp đồng 12.500) | **Chờ xử lý thủ công**, tổng 1.430.000. Dòng: Tầng 1 - Mã, Đã khớp, ô **Cảnh báo chặn** tích, Cảnh báo "Đơn giá 13.000 khác giá hợp đồng khung 12.500 (D4N01-HDK012026-VTTH-001)." Không có nút Tạo Hóa đơn mua nháp | ☐ |
| G2 | `demo.nvmuahang` xem phiếu G1 | Không có nút **Duyệt cảnh báo** | ☐ |
| G3 | `demo.giamdoc` bấm **Duyệt cảnh báo** → để trống Lý do duyệt → Duyệt | Không duyệt được (ô lý do bắt buộc) | ☐ |
| G4 | Nhập lý do "Ban Điều hành đồng ý giá mới từ 01/11" → **Duyệt** | **Đã đối soát**. Hiện Lý do duyệt cảnh báo, Người duyệt = demo.giamdoc, Thời điểm duyệt. Cảnh báo trên dòng vẫn giữ để lưu vết | ☐ |
| G5 | **Tạo Hóa đơn mua nháp** | Hóa đơn 100 × 13.000, tổng 1.430.000, đối soát Đợt 3: **Khớp** (Phiếu nhập E cũng 13.000) | ☐ |
| G6 | Lập phiếu với **F_vuot_han_muc.xml** (Bơm tiêm: hợp đồng 100, Đơn mua và Phiếu nhập 100, hóa đơn 120; mã trên hóa đơn là **mã dòng hợp đồng** D4N01-HDK012026-VTTH-004) | **Chờ xử lý thủ công**, tổng 396.000. Dòng: **Tầng 1 - Mã** (khớp theo mã dòng hợp đồng), Cảnh báo chặn: "Vượt hạn mức hợp đồng khung: còn 100, hóa đơn 120 (ĐVT kho)." | ☐ |
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
| J6 | Chọn **Mặt hàng** = DEMO-HDK-07 → Lưu | Dòng Đã khớp, **Chọn tay**, gắn dòng hợp đồng 005 (D4N01-HDK012026-VTTH-005). Phiếu **Đã đối soát** | ☐ |

## K. Tắt công tắc

Làm sau cùng.

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| K1 | Administrator bỏ tích **Bật tiếp nhận hóa đơn** → Lưu. Mở phiếu D4 → Lưu | Bị chặn: "Tiếp nhận hóa đơn đang tắt (Cài đặt tiếp nhận hóa đơn)." Bật lại sau khi thử | ☐ |
| K2 | Ở `sites` chạy `../env/bin/python ../apps/erpnext/scripts/demo_tiep_nhan_hoa_don.py --site erpnext.localhost --tra-lai` | In các cài đặt được trả về như trước lần chạy demo đầu (MST người mua, vai trò duyệt…). Dữ liệu demo giữ nguyên | ☐ |

## L. Xử lý sự cố thường gặp

| Hiện tượng | Nguyên nhân | Cách xử lý |
|---|---|---|
| Mở `/app/supplier-invoice-intake` báo lỗi hoặc không thấy DocType | Thư mục chính của bench chưa có code Đợt 4, hoặc chưa `migrate` | Đưa nhánh Đợt 4 vào thư mục chính, chạy `bench --site erpnext.localhost migrate` rồi `clear-cache` |
| Tên DocType và câu chặn vượt hạn mức hiện tiếng Anh ("Supplier Invoice Intake", "Item … cannot be ordered more than …") | Bản dịch nằm trong cache | `bench --site erpnext.localhost clear-cache`, tải lại trang |
| Lưu phiếu báo "Chưa đọc được hóa đơn" | Tệp không phải XML hóa đơn điện tử (không có `HDon/DLHDon`). Ảnh / PDF chưa hỗ trợ ở phần 1 | Tải tệp XML gốc của hóa đơn |
| Phiếu không tự nhận NCC: "Không có nhà cung cấp nào mang MST …" | NCC chưa có MST (Tax ID), hoặc có hai NCC cùng MST | Điền MST cho NCC, hoặc chọn Nhà cung cấp trên phiếu rồi Lưu |
| Đơn mua không tự gắn Đơn khung; hộp cam "Nhiều hợp đồng khung cùng hiệu lực, chưa tự gắn…" | NCC có hai hợp đồng khung cùng hiệu lực chứa mặt hàng | Chọn Đơn khung trên dòng Đơn mua |
| Nộp Đơn khung báo thiếu Bảng giá mua | NCC chưa có bảng giá mặc định là bảng giá mua | Chọn Bảng giá mua trên Đơn khung |
| Không Hủy được Đơn khung | Đã có Đơn mua liên kết (ERPNext chặn) | Hủy Đơn mua trước, hoặc giữ hợp đồng và sửa ngày hết hiệu lực (Đến ngày sửa được sau khi Nộp) |
| Nhân viên không tạo được Đơn khung | Mặc định chỉ System Manager có quyền trên Đơn khung | Cấp quyền cho vai trò phụ trách hợp đồng trong Role Permission Manager (cấu hình site) |

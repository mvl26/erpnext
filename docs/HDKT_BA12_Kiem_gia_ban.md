# Hướng dẫn test thủ công — BA12: Đối soát giá mua – giá bán theo hệ số khách hàng

| Mục | Nội dung |
|---|---|
| Phạm vi | BA12 V1.0 (21/10/2026), nghiệm thu A01–A08 và các điểm PO chốt 22/10/2026 (Q1, Q2, Q7, Q10 — mục F); thiết kế kỹ thuật `docs/BA12_TKKT_DoiSoatGiaMuaGiaBan.md` |
| Site test | `erpnext.localhost` — mở `http://127.0.0.1:8000`. **Không test trên `miyano`.** |
| Nhánh | `feat/bao-truoc-doi-gia-himedic` |
| Cách ghi kết quả | Đánh dấu ☐ → ☑ khi đạt; ghi chú ngắn khi không đạt (số chứng từ, ảnh chụp) |

Quy tắc để đối chiếu khi test:

- **Giá đề xuất = giá mua × hệ số**, **làm tròn đến đồng** (R03), so với giá bán **chưa VAT, sau chiết khấu đơn**.
- **Giá mua** (D07) của **NCC dự kiến** trên dòng (D08; trống thì NCC mặc định của mặt hàng): (1) **Báo giá đợt** = Supplier Quotation đã Submit còn hiệu lực, mới nhất; (2) không có thì **HĐ nguyên tắc** = giá trong bảng giá "Mua - <NCC>" (dòng có Supplier) hiệu lực tại ngày SO.
- **Hệ số** (R01) trên Khách hàng: bảng "Hệ số theo khách hàng" (hệ số, số hợp đồng, hiệu lực từ–đến). Khách không có hệ số → **không kiểm, không cảnh báo** (R07).
- Lệch → cảnh báo, vẫn lưu được (D03). **Submit**: còn dòng lệch hoặc chưa có giá mua → bắt buộc **Lý do lệch giá** (R04, R08); dòng **khác bảng giá KH** → bắt buộc **số văn bản, người đại diện KH, ngày chấp thuận** trên dòng đó (R05). Không còn bước duyệt.
- **Bảng giá KH** = bảng giá mặc định của khách (Customer → Default Price List; trống thì của nhóm khách), **không** phải bảng giá chọn trên đơn. "Khác bảng giá" = giá đề xuất khác giá trong bảng giá đó, **hoặc mặt hàng chưa có trong bảng giá đó** (Q2).
- Hệ thống tự ghi **người nhập** và **thời điểm nhập** thông tin chấp thuận trên dòng (Q1). Sau Submit: ô trống vẫn điền được, ô đã điền chỉ Giám đốc sửa.
- Xác nhận (Submit) SO có dòng R05 → email "Thông báo giá mới" cho người đặt đơn (R06). Dòng thêm sau Submit bằng Update Items → **chờ khách chấp thuận**, chưa tạo được Phiếu giao / Hóa đơn bán cho dòng đó; nhập đủ thông tin → email bổ sung (Q10).
- Kết quả xem ở **dòng hàng → mục "Kiểm giá bán (BA12)"** (bấm vào dòng để mở chi tiết).

---

## 0. Chuẩn bị

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| 0.1 | Bench đang chạy (`bench start`) | Mở được `http://127.0.0.1:8000` | ☐ |
| 0.2 | Ở thư mục `sites` chạy:<br>`../env/bin/python ../apps/erpnext/scripts/demo_gia_ban_doi_soat.py --site erpnext.localhost` | In ra 4 SO demo và trạng thái từng dòng. Chạy lại lần 2 không lỗi, kết quả như cũ | ☐ |
| 0.3 | Thử chạy với `--site miyano` | Script từ chối: "Từ chối: không tạo dữ liệu demo trên site production." | ☐ |

Gặp lỗi thiếu tài khoản kho khi Nộp chứng từ kho, hoặc lỗi máy chủ khi lưu hồ sơ Công ty: xem mục **11. Xử lý sự cố thường gặp** cuối tài liệu.

Dữ liệu demo:

| Loại | Bản ghi |
|---|---|
| NCC | `DEMO-Vietmed` (NCC mặc định của VT-01, VT-03, VT-05), `DEMO-Hùng Minh` (của VT-02) |
| Giá HĐ nguyên tắc | `DEMO Mua - Vietmed`: VT-01 123.457, VT-05 10.000/Cái · `DEMO Mua - Hùng Minh`: VT-01 118.000, VT-02 50.000 |
| Báo giá đợt | Supplier Quotation **nháp** DEMO-Vietmed: VT-01 125.000, hiệu lực 30 ngày |
| Khách | `DEMO-Himedic` hệ số 1,01 (HĐNT-HIMEDIC-2026) · `DEMO-Hoàng Lâm` 1,05 (HĐNT-HOANGLAM-2026) · `DEMO-Khách lẻ` không hệ số |
| Bảng giá bán | `DEMO Bảng giá Himedic`: VT-01 120.000, VT-02 50.500, VT-03 30.000, VT-05 10.100/Cái · `DEMO Bảng giá Hoàng Lâm`: VT-02 52.500 (không có VT-01) |
| SO nháp | ① Himedic: VT-01 124.692, VT-02 50.500, VT-05 2 Hộp 101.000, email người đặt đơn `himedic.demo@example.com` · ② Himedic: VT-01 125.000, VT-03 30.000 · ③ Hoàng Lâm: VT-02 52.500, VT-01 129.630 · ④ Khách lẻ: VT-01 150.000 |
| Người dùng (Impersonate) | `demo.nhanvien@example.com` (bán hàng) · `demo.giamdoc@example.com` (vai trò **DEMO Giám đốc**, được sửa hệ số) |

## A. Nghiệm thu BA12

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| A01 | Mở SO ① → dòng VT-01 → mục Kiểm giá bán | NCC dự kiến DEMO-Vietmed; giá mua **123.457**, nguồn **HĐ nguyên tắc**, chứng từ = dòng giá của DEMO Mua - Vietmed; hệ số 1,01; số HĐ HĐNT-HIMEDIC-2026; giá đề xuất **124.692**; trạng thái **Khớp** | ☐ |
| A02 | Mở Supplier Quotation nháp DEMO-Vietmed → **Submit**. Mở lại SO ① → Lưu | VT-01: giá mua **125.000**, nguồn **Báo giá đợt** (số báo giá, ngày), giá đề xuất **126.250**, trạng thái **Thấp hơn**, chênh −1.558 | ☐ |
| A03 | SO ①, dòng VT-01: đổi **NCC dự kiến** = DEMO-Hùng Minh → Lưu | Giá mua **118.000** (HĐ nguyên tắc Hùng Minh), đề xuất **119.180**, trạng thái **Cao hơn** | ☐ |
| A04 | Mở SO ② → Lưu | Cảnh báo cam: VT-01 giá mua 123.457 (HĐ nguyên tắc …), hệ số 1,01, giá đúng 124.692, **chênh +308**. Submit (không lý do) → **bị chặn** "Nhập Lý do lệch giá" | ☐ |
| A05 | SO ② (hoặc ①) dòng VT-01 có **Đề xuất khác bảng giá** (bảng giá 120.000) và **Chờ khách chấp thuận giá** → điền Lý do lệch giá, Submit | Bị chặn: "… Ghi đủ thông tin khách chấp thuận (R05): Dòng 1 – DEMO-VT-01: thiếu Số văn bản…, Người đại diện KH…, Ngày chấp thuận". Điền thiếu 1 trong 3 ô → vẫn bị chặn, báo đúng ô thiếu | ☐ |
| A06 | Làm lại từ 0.2. SO ① dòng VT-01: điền Số văn bản `VB-01/2026`, Người đại diện `Ông A`, Ngày chấp thuận hôm nay → Lưu → **Submit** | Submit được. Ô **Thông báo giá mới (R06)** có link Communication: gửi `himedic.demo@example.com`, tiêu đề "Thông báo giá mới - Đơn hàng …", bảng: VT-01, giá cũ **120.000**, giá mới **124.692**, số văn bản VB-01/2026. Email nằm trên timeline SO | ☐ |
| A07 | Mở SO ④ (DEMO-Khách lẻ) → Lưu → Submit | Không cảnh báo; mục Kiểm giá bán trống; Submit được không cần gì | ☐ |
| A08 | Mở báo cáo **Doi Soat Gia Mua Gia Ban** (Từ ngày–Đến ngày quanh hôm nay) | Có dòng của SO đã Submit ở A06: SO, mặt hàng, NCC, nguồn giá, giá mua, hệ số, số HĐ, giá đề xuất, giá bán, chênh lệch, giá bảng giá, trạng thái, lý do, số văn bản, người đại diện, ngày chấp thuận, **Chấp thuận** (Đủ / Chờ chấp thuận), **Người nhập chấp thuận**, **Thời điểm nhập**. Lọc Khách hàng / NCC / Mặt hàng hoạt động; "Gồm SO nháp" hiện thêm SO nháp; "Chỉ dòng lệch / khác bảng giá" ẩn dòng khớp; "Chỉ dòng chờ khách chấp thuận" chỉ hiện dòng còn chờ | ☐ |

## B. Hệ số khách hàng (R01, R07) và quyền

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| B1 | Mở Khách hàng DEMO-Himedic → mục **Hệ số giá bán (BA12)** | Bảng "Hệ số theo khách hàng": 1,01 / HĐNT-HIMEDIC-2026 / từ ngày; cột Mặt hàng ẩn. Bảng "Hệ số theo mặt hàng" **khóa** (vì đã có hệ số chung) | ☐ |
| B2 | `demo.giamdoc`: thêm dòng hệ số thứ hai 1,02 từ hôm nay, không điền "Hiệu lực đến" cho dòng cũ → Lưu | Bị chặn "… cùng hiệu lực từ … Đặt ngày hiệu lực đến cho dòng 1". Đặt dòng 1 đến hôm qua → Lưu được. SO ① lưu lại → hệ số 1,02. Xóa dòng mới, bỏ ngày đến dòng 1 để trả về như cũ | ☐ |
| B3 | Dòng hệ số không có số hợp đồng / hệ số = 0 / đến trước từ | Bị chặn với thông báo tương ứng | ☐ |
| B4 | `demo.nhanvien` mở DEMO-Himedic | Hai bảng hệ số **chỉ đọc**. Sửa ô khác (vd. ghi chú) → Lưu được. Gửi API đổi hệ số → bị chặn "Chỉ vai trò DEMO Giám đốc được sửa hệ số giá bán" | ☐ |
| B5 | `demo.giamdoc` tạo khách mới không có hệ số chung, thêm **Hệ số theo mặt hàng**: VT-02 1,05 → tạo SO VT-02 52.500 | VT-02 hệ số 1,05, Khớp; mặt hàng khác của khách này không kiểm (R07) | ☐ |
| B6 | Selling Settings → mục **Kiểm giá bán theo hệ số khách hàng (BA12)** | Có ô "Bật kiểm giá bán", "Bắt buộc đính kèm văn bản chấp thuận" và "Vai trò được sửa hệ số giá bán"; **không còn** % lãi mặc định, Chế độ, Vai trò duyệt. `demo.nhanvien` thấy chỉ đọc | ☐ |
| B7 | Bỏ tích "Bật kiểm giá bán" → SO ② Lưu, Submit | Không kiểm, Submit được. Bật lại | ☐ |

## C. Giá mua, làm tròn, ĐVT (R02, R03, R08, D04)

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| C1 | SO ② dòng VT-03 | **Chưa có giá mua**, ghi chú "Chưa có giá mua để đối soát: NCC DEMO-Vietmed không có báo giá đợt còn hiệu lực, cũng không có giá HĐ nguyên tắc…". VT-03 có trong bảng giá Himedic nên không khác bảng giá. Submit không lý do → bị chặn (R08) | ☐ |
| C2 | SO ① dòng VT-05 (2 Hộp, Hộp = 10 Cái) | Giá mua 100.000/Hộp, đề xuất 101.000, Khớp; bảng giá 10.100/Cái → 101.000/Hộp, không khác bảng giá | ☐ |
| C3 | Sửa giá VT-01 thành 124.692,4 → Lưu | Vẫn **Khớp** (làm tròn đến đồng, D04). 124.693 → **Cao hơn**, chênh +1 | ☐ |
| C4 | Supplier Quotation DEMO-Vietmed cho VT-01, **Valid Till = hôm qua**, Submit | SO lưu lại vẫn lấy giá HĐ nguyên tắc (báo giá hết hiệu lực) | ☐ |
| C5 | Supplier Quotation có chiết khấu đơn 10% (giá 130.000) → Submit | Giá mua = 117.000 (sau chiết khấu) | ☐ |
| C6 | Mặt hàng chưa có NCC mặc định, dòng SO không chọn NCC dự kiến | Chưa có giá mua, ghi chú nêu thiếu NCC | ☐ |
| C7 | Dòng SO hàng tặng / mặt hàng không quản lý kho / khách nội bộ | Trạng thái **Bỏ qua** | ☐ |
| C8 | SO ① bấm nút **Áp giá đề xuất** (hiện khi có dòng Thấp hơn/Cao hơn) | Đơn giá các dòng lệch = giá đề xuất; Lưu → Khớp (D06) | ☐ |

## D. Sau khi Submit

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| D1 | SO đã Submit (khớp, không lý do) → **Update Items**: thêm dòng VT-01 giá 130.000 | Bị chặn "Nhập Lý do lệch giá". Điền Lý do lệch giá trên SO (ô sửa được sau Submit) → Update Items lại → được | ☐ |
| D2 | Update Items thêm mặt hàng có giá đề xuất khác bảng giá | **Không bị chặn** — dòng mới ở trạng thái chờ khách chấp thuận (xem mục F, Q10) | ☐ |
| D3 | Update Items chỉ đổi số lượng một dòng khớp của SO cũ có dòng lệch khác | Được; dòng không ai đụng giữ nguyên kết quả cũ (D05) | ☐ |
| D4 | Thêm giá HĐ nguyên tắc mới cho VT-01 (130.000, từ hôm nay) | SO đã Submit **không đổi** giá mua; báo cáo A08 cột **Giá mua hiện tại** 130.000, **Giá mua đổi** +6.543 (D05) | ☐ |
| D5 | Tạo PO từ SO ① với giá VT-01 cao hơn giá mua đã dùng ở SO | Cảnh báo "Giá mua cao hơn giá mua đã dùng để chốt giá bán", vẫn lưu được | ☐ |

## F. Các điểm PO chốt ngày 22/10/2026 (Q1, Q2, Q7, Q10)

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| F1 | **Q1.** `demo.nhanvien` mở SO ① dòng VT-01, điền Số văn bản `VB-01/2026`, Người đại diện `Ông A`, Ngày chấp thuận hôm nay → Lưu | Mục "Khách chấp thuận giá mới (R05)": **Người nhập chấp thuận** = demo.nhanvien, **Thời điểm nhập** = lúc lưu (chỉ đọc); bỏ tích **Chờ khách chấp thuận giá** | ☐ |
| F2 | **Q1.** Submit SO ở F1. `demo.nhanvien` sửa Số văn bản thành `VB-02/2026` → Cập nhật | Bị chặn: "Thông tin khách chấp thuận đã điền chỉ vai trò DEMO Giám đốc được sửa…". `demo.giamdoc` sửa → được; Người nhập đổi thành demo.giamdoc. Lịch sử sửa xem ở timeline (Version) | ☐ |
| F3 | **Q1.** `demo.giamdoc`: Selling Settings bật **Bắt buộc đính kèm văn bản chấp thuận**. SO nháp có dòng khác bảng giá, điền 3 ô, không đính kèm → Submit | Bị chặn, báo thiếu "Tệp văn bản chấp thuận". Đính kèm tệp ở ô đó → Submit được. **Tắt lại** ô cài đặt | ☐ |
| F4 | **Q2.** Mở SO ③ (Hoàng Lâm) dòng VT-01 | Tích **Chưa có trong bảng giá KH** và **Đề xuất khác bảng giá**; giá bảng giá trống; cảnh báo "chưa có trong bảng giá KH DEMO Bảng giá Hoàng Lâm — Submit cần …". Submit không có 3 thông tin → bị chặn. Điền đủ, thêm email liên hệ → Submit → email: giá cũ **"Chưa có trong bảng giá"** | ☐ |
| F5 | **Q2.** SO ① (nháp) đổi ô **Bảng giá** trên đơn sang `DEMO Bảng giá Hoàng Lâm` → Lưu | Dòng VT-01 vẫn so với **DEMO Bảng giá Himedic** (bảng giá mặc định của khách): giá bảng giá 120.000, vẫn khác bảng giá. Đổi bảng giá trên đơn không né được R05 | ☐ |
| F6 | **Q7.** Theo HDKT Đợt 2 mục K (VT-02 có giá mới 52.000 chờ báo, giá đề xuất 52.000). SO nháp Himedic VT-02 giá **52.000** → Lưu | Trạng thái **Khớp** nhưng **khác bảng giá** (bảng giá hiện hành 50.500), chờ khách chấp thuận → Submit cần 3 thông tin (khách chấp thuận áp giá mới sớm) | ☐ |
| F7 | **Q7.** Như F6 nhưng giá **51.000** | Trạng thái **Thấp hơn** (không phải "Đang trong thời hạn báo giá"), ghi chú "… nhưng giá bán khác giá bảng giá hiện hành nên vẫn tính là lệch". Submit cần Lý do lệch giá và 3 thông tin | ☐ |
| F8 | **Q10.** SO đã Submit (vd. SO ở F1) → **Update Items** thêm VT-01 giá đề xuất (khác bảng giá) | Update Items **được**. Đầu form báo cam "Dòng … chờ khách chấp thuận giá (R05) …"; dòng mới tích **Chờ khách chấp thuận giá** | ☐ |
| F9 | **Q10.** Từ SO ở F8 tạo **Phiếu giao hàng** rồi **Hóa đơn bán** → Lưu | Bị chặn: "Khách chưa chấp thuận giá mới của các dòng đơn hàng dưới đây (R05) …" nêu dòng. Xóa dòng đó khỏi phiếu → lưu được | ☐ |
| F10 | **Q10.** Mở dòng chờ trên SO ở F8, nhập 3 thông tin → **Cập nhật** | Hết chờ; timeline có email **"Thông báo giá mới (bổ sung) - Đơn hàng …"** chỉ gồm dòng đó; tạo Phiếu giao hàng cho dòng đó được. Cập nhật lại lần nữa không gửi thêm email | ☐ |

## E. Báo cáo đối chiếu bảng giá

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| E1 | Mở **Doi Chieu Gia Ban Gia Mua**, Bảng giá bán = DEMO Bảng giá Himedic | Mỗi giá trong bảng giá: NCC, nguồn giá mua, giá mua, hệ số (của DEMO-Himedic), giá đề xuất, chênh, trạng thái. VT-01 120.000 → **Thấp hơn** | ☐ |
| E2 | Ô "Hệ số" = 1,05 | Tính theo 1,05 cho mọi dòng | ☐ |
| E3 | Khách = DEMO-Khách lẻ | Trạng thái "Khách không có hệ số" | ☐ |

## Kiểm tra cổng khách hàng (Việt phối hợp)

| # | Bước | Kết quả mong đợi | ☐ |
|---|---|---|---|
| P1 | Khách lưu SO qua cổng | Không thấy cảnh báo giá mua / hệ số | ☐ |
| P2 | Khách cố Submit SO còn lệch qua cổng | Thông báo chung "Đơn hàng cần Miyano kiểm tra giá trước khi xác nhận", không lộ giá | ☐ |
| P3 | Gọi `erpnext.selling.kiem_gia.thong_bao_gia_moi.lay_thong_bao_gia_moi` với SO ở A06 | Trả về dòng VT-01: giá cũ 120.000, giá mới 124.692, số văn bản — cùng nội dung email | ☐ |
| P4 | Gọi API với SO ở F4 và SO ở F8 (trước và sau F10) | F4: `gia_cu` = null (Portal hiển thị "Chưa có trong bảng giá"). F8: dòng chờ chấp thuận **chưa** có; sau F10 có | ☐ |

## 11. Xử lý sự cố thường gặp

### 11.1. Nộp Phiếu nhập mua báo lỗi thiếu tài khoản kho

**Thông báo:** "Vui lòng thiết lập Stock Received But Not Billed mặc định trong công ty Miyano".

**Nguyên nhân:** công ty Miyano bật hạch toán tồn kho thường xuyên nhưng chưa khai báo các tài khoản kế toán kho mặc định. Lỗi này không phải do thao tác của nhân viên mua hàng.

**Cách xử lý** (kế toán trưởng hoặc IT): mở **Công ty Miyano**, điền 3 trường rồi Lưu:

| Trường | Tài khoản cần chọn |
|---|---|
| Stock Received But Not Billed | Hàng mua chưa có hóa đơn - MVL |
| Expenses Included In Valuation | Chi phí thu mua tính vào giá trị hàng tồn kho - MVL |
| Stock Adjustment | Chi phí điều chỉnh hàng tồn kho - MVL |

Lưu Công ty mà gặp lỗi máy chủ → làm mục 11.2 trước.

Site test `erpnext.localhost`: **đã điền** 3 tài khoản này ngày 23/10/2026.

### 11.2. Lỗi máy chủ khi lưu hồ sơ Công ty

**Thông báo:** "Lỗi máy chủ – pymysql.err.OperationalError: (1054, Unknown column default_employee_advance_account)".

**Nguyên nhân:** cấu trúc cơ sở dữ liệu thiếu các trường nhân sự của Công ty. Khi lưu, Công ty tự gán tài khoản mặc định nhân sự theo TT99 (tạm ứng 141, phải trả người lao động 334) vào các trường do app **HRMS** thêm. Thiếu khi: site **chưa cài HRMS**, hoặc đã cài nhưng **chưa chạy lệnh đồng bộ** sau khi cập nhật ERPNext / HRMS. Hệ quả: không lưu được hồ sơ Công ty, nên cũng chưa khắc phục được lỗi ở mục 11.1.

**Cách xử lý** (bộ phận IT, từ thư mục bench trên máy chủ — thư mục chứa `sites/`):

1. Xem site đã cài HRMS chưa: `bench --site <tên site> list-apps`.
2. Chưa có `hrms` → sao lưu rồi cài HRMS (tạo các trường nhân sự trên Công ty và phần quản lý nhân viên):

   ```bash
   bench --site <tên site> backup
   bench --site <tên site> install-app hrms
   ```

3. Đã có `hrms` → chạy lệnh đồng bộ:

   ```bash
   bench --site <tên site> migrate
   ```

4. Làm lại mục 11.1.

Site test `erpnext.localhost`: **đã cài HRMS** (15.50.3) ngày 23/10/2026.

## Test tự động

```bash
cd ~/frappe-bench/sites
../env/bin/python ../apps/erpnext/scripts/chay_test.py --site erpnext.localhost \
	erpnext.selling.tests.test_kiem_gia_chung_tu erpnext.selling.tests.test_kiem_gia_goc \
	erpnext.selling.tests.test_kiem_gia_cau_hinh erpnext.selling.tests.test_kiem_gia_submit \
	erpnext.selling.tests.test_kiem_gia_thong_bao_gia_moi erpnext.selling.tests.test_kiem_gia_bao_cao \
	erpnext.selling.tests.test_kiem_gia_po erpnext.selling.tests.test_kiem_gia_bao_truoc
```

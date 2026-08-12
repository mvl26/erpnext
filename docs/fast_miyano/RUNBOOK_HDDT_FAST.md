# Vận hành hóa đơn điện tử Fast — Miyano ERP

Tài liệu thao tác hằng ngày và xử lý sự cố. Đặc tả gốc:
`SPEC_FAST_EINVOICE_ERPNEXT_v2.md`. Lịch sử thi công nằm trong `git log` của
module `erpnext/einvoice/`.

> **Trạng thái:** phần mềm đã dựng xong và test đầy đủ bằng transport giả.
> **Chưa chạy thật lần nào** — xem mục "Việc phải làm trước khi go-live".

---

## 1. Trước khi go-live — những việc code không làm thay được

| # | Việc | Ai làm | Vì sao chặn |
|---|---|---|---|
| 1 | Fast xác nhận **đã bật chế độ không mã hóa RSA** cho DN 008254 | Fast | Sai chế độ thì mọi lời gọi đều hỏng |
| 2 | Fast xác nhận **chứng thư số HSM** + tờ khai HĐĐT đã được CQT chấp nhận | Fast | Thiếu là lỗi 500/501/502, tắc toàn hệ thống |
| 3 | Xin **user API riêng cho ERP** (khác user đăng nhập web) | Miyano | Mỗi user chỉ có **một token sống**; dùng chung sẽ đá nhau, người đang thao tác web bị đăng xuất |
| 4 | Xin **tài khoản môi trường TEST** (`:9000`) | Miyano | Không có thì không chạy được 12 kịch bản trước khi đụng số thật |
| 5 | **Đối chiếu WSDL thật** với `OPERATIONS` trong `fast_client.py` và bộ đọc kết quả trong `issue.py` / `tax_status.py` | Dev + Fast | Đặc tả không kèm WSDL nên tên tham số và định dạng chuỗi trả về hiện đang là **suy ra** |
| 6 | Xác nhận với Fast **thẻ nào chứa tiền thuế suất 8%** | Kế toán + Fast | Bốn thẻ `TaxAmountFree/0/5/10` không có ô cho 8% |
| 7 | Xử lý hóa đơn test `TESTPM260807A` đã lỡ phát hành thật | Kế toán trưởng | Là số hóa đơn thật đã tiêu, phải điều chỉnh hoặc thay thế |
| 8 | Giao role **Kế toán trưởng HĐĐT** cho đúng người | Kế toán trưởng | Role này mở nút phát hành và nút hủy |

Ngoài ra, hai việc chuẩn hóa dữ liệu (Giai đoạn 1 của đặc tả):

- Delivery Note phải gắn **Sales Taxes and Charges Template** — thuế là con số
  pháp lý, hệ thống không đoán.
- Rà `tax_id`, địa chỉ xuất hóa đơn và email trên toàn bộ Customer đang hoạt
  động. Đây là nguồn của lỗi 836.
- Chuẩn hóa bảng UOM sang tên tiếng Việt (Cái, Chiếc, Bộ, Hộp, Kg…).

---

## 2. Bật tích hợp

Vào **Fast EInvoice Settings** (Single DocType):

1. Điền `api_user` / `api_password` do Fast cấp.
2. **Giữ `Chế độ TEST` bật** và `URL dịch vụ` trỏ vào cổng `:9000` cho tới khi
   chạy xong 12 kịch bản.
3. Bật `Kích hoạt tích hợp`.
4. Chọn hai mẫu email (đã tạo sẵn khi migrate) và điền `Người nhận cảnh báo lỗi`.

Mặc định an toàn: site mới có `Kích hoạt = tắt` và `Chế độ TEST = bật`. Lên
thật là hành động **cố ý lật hai cờ**, không thể vô tình.

> Banner trên đầu mỗi chứng từ HĐĐT: **vàng** = môi trường TEST, **đỏ** = HỆ
> THỐNG THẬT. Nhìn banner trước khi bấm bất cứ nút nào.

---

## 3. Quy trình hằng ngày

```
Delivery Note đã submit
   │  [Tạo hóa đơn điện tử]                     ← xác nhận cấp 1
   ▼
01 Nháp ──[Xem bản nháp PDF]──► 02 Đã xem nháp
   ▲                                │  [Gửi bản nháp cho khách]   ← cấp 2
   │                                ▼
   └──[Ghi nhận ý kiến khách]── 03 Chờ khách duyệt
                                    │  [Khách đã duyệt]           ← cấp 2
                                    ▼
                              04 Khách đã duyệt
                                    │  [PHÁT HÀNH HÓA ĐƠN]        ← CẤP 3
                                    ▼
                              06 Đã phát hành
                                    │  [Tải PDF] → [Gửi hóa đơn]  ← cấp 2
                                    ▼
                              07 Đã gửi khách
                                    │  job nền 20 phút kiểm tra CQT
                          ┌─────────┴─────────┐
                          ▼                   ▼
                 08 CQT chấp nhận      09 CQT từ chối
                 (điều chỉnh/thay thế)  ([Hủy nội bộ] ← CẤP 3)
```

**Xem bản nháp bao nhiêu lần cũng được** — `action=600` không ký số, không cấp
số, không gửi CQT, không tiêu số hóa đơn nào.

**Chỉ từ trạng thái 06 trở đi hóa đơn mới có giá trị pháp lý.** Bản PDF ở trạng
thái 01–04 là bản nháp; mẫu email gửi khách đã ghi sẵn dòng cảnh báo này.

---

## 4. Xử lý sự cố

### 4.1 "Cần đối soát" (trạng thái 98) — ca nguy hiểm nhất

Nghĩa là: **đã gửi lệnh phát hành nhưng không nhận được kết quả** (mạng đứt,
Fast treo). Chưa biết hóa đơn đã ra số hay chưa.

> **TUYỆT ĐỐI KHÔNG bấm phát hành lại.** Phát hành lại khi Fast đã cấp số là
> hai số hóa đơn cho một lần bán.

Cách xử lý: bấm **Truy vấn đối soát (370)**.

- Fast **có** hóa đơn → bấm áp dụng, chứng từ nhận lại số thật, về trạng thái 06.
- Fast **không có** (mã 888) → xác nhận chưa tiêu số nào, chứng từ về Nháp, phát
  hành lại được an toàn.

### 4.2 Fast báo lỗi khi phát hành (trạng thái 99)

Bảng lỗi tiếng Việt hiện ngay trên chứng từ kèm gợi ý hành động. Vài mã hay gặp:

| Mã | Nghĩa | Làm gì |
|---|---|---|
| 152 | Đọc tiền bằng chữ sai loại tiền | Đồng bộ lại từ phiếu giao, hệ thống sinh lại |
| 809 / 835 | Hóa đơn đã phát hành trước đó | Bấm Truy vấn (370). **Không phát hành lại** |
| 812 / 825 | Tên hàng quá dài hoặc có xuống dòng | Sửa tên hàng trên phiếu giao rồi đồng bộ lại |
| 819 | Ngày hóa đơn nhỏ hơn hóa đơn liền trước | Đặt lại ngày hóa đơn |
| 836 | Thiếu thông tin người mua | Bảng kiểm tra dữ liệu trên form chỉ đúng trường thiếu |
| 78013 | Mã số thuế khách không hợp lệ | Sửa `tax_id` trên hồ sơ Customer |
| 500/501/502 | Chứng thư số HSM chưa sẵn sàng | **Liên hệ Fast** — cả hệ thống đang tắc, không phải lỗi chứng từ này |
| 601 / 808 | Hết số hóa đơn | Kế toán trưởng đăng ký thêm số với CQT |

### 4.3 CQT từ chối (trạng thái 09)

Xem lý do ở trường `Phản hồi CQT`. Sửa nguồn sai (thường là MST hoặc tên đơn
vị mua), rồi **Hủy nội bộ** (cấp 3, gõ `HUY`) và lập hóa đơn mới từ phiếu giao.

Hủy xong, phiếu giao được mở khóa để lập hóa đơn mới; liên kết tới chứng từ đã
hủy vẫn giữ để còn lần lại lịch sử.

### 4.4 Sai sót sau khi CQT đã chấp nhận (trạng thái 08)

Không hủy được nữa (NĐ 70/2025 đã bãi bỏ thủ tục hủy thông thường). Chọn:

| Tình huống | Dùng |
|---|---|
| Sai số lượng / đơn giá / thuế suất | **Điều chỉnh** loại 1 (giảm) hoặc 2 (tăng) |
| Sai thông tin không đổi số tiền | **Điều chỉnh thông tin** (loại 3) |
| Sai nhiều, sai nghiêm trọng | **Thay thế** |
| Trả lại hàng | **Điều chỉnh giảm** — nhập số **âm** |

Bản ghi mới đi lại trọn vòng đời từ Nháp. Hóa đơn gốc chỉ bị khóa **khi bản mới
đã thực sự có số**.

### 4.5 Báo cáo đối soát

**Doi Soat Hoa Don Dien Tu** — chạy mỗi cuối ngày, gom ba việc phải dọn:

1. Phiếu giao đã submit mà chưa lập hóa đơn.
2. Hóa đơn chờ CQT quá 24 giờ (bất thường — hỏi Fast).
3. Hóa đơn lỗi hoặc cần đối soát.

---

## 5. 12 kịch bản kiểm thử của Giai đoạn 6

Cột "Tự động" = đã có test chạy trong `bench run-tests`, dùng transport giả.
Cột "Chạy thật" = phải làm tay trên môi trường TEST của Fast khi có tài khoản.

| # | Kịch bản | Tự động | Chạy thật |
|---|---|---|---|
| 1 | Khách doanh nghiệp có MST, VAT 10% | ✅ `test_fast_end_to_end.TestScenario1HappyPath` | Bắt buộc |
| 2 | Khách cá nhân không MST, có CCCD | ⚠️ chỉ có test quy tắc CCCD (`test_fast_validation`) | Bắt buộc |
| 3 | Có MST nhưng xóa địa chỉ → chặn tại ERP | ✅ `TestScenario3ValidationStopsBeforeFast` | Nên |
| 4 | Hóa đơn nhiều thuế suất (0% + 5% + 10%) | ✅ `test_fast_payload.TestTaxGroups` | Bắt buộc |
| 5 | Hóa đơn 250 dòng | ⚠️ chỉ có test ngưỡng 300 dòng | Bắt buộc (đo cả thời gian) |
| 6 | Bấm phát hành 2 lần liên tiếp | ✅ `TestScenario6DoubleClick` | Nên |
| 7 | Ngắt mạng giữa lúc phát hành | ✅ `TestScenario7NetworkCutMidIssue` | Bắt buộc |
| 8 | Token hết hạn giữa chừng | ✅ `test_fast_client` (tự lấy lại rồi thử lại 1 lần) | Nên |
| 9 | Vòng nháp: gửi → sửa 2 lần → duyệt → phát hành | ✅ `TestScenario9DraftRevisionCycle` | Bắt buộc |
| 10 | Điều chỉnh giảm sau khi CQT chấp nhận | ✅ `TestScenario10AdjustmentAfterAcceptance` | Bắt buộc |
| 11 | Thay thế hóa đơn | ✅ `test_fast_lineage` | Bắt buộc |
| 12 | Sai đọc tiền bằng chữ | ✅ `test_fast_validation` (quy tắc 5) | Nên |

Chạy toàn bộ test tự động:

```bash
cd /home/miyano/frappe-bench
for m in test_einvoice_module test_einvoice_setup test_fast_settings test_fast_line \
         test_fast_document test_fast_log test_fast_client test_fast_gateway \
         test_fast_payload test_fast_validation test_fast_builder test_fast_draft \
         test_fast_approval test_fast_issue test_fast_pdf test_fast_send_invoice \
         test_fast_tax_status test_fast_lineage test_fast_cancel test_fast_form_state \
         test_fast_lookup test_fast_end_to_end ; do
  bench --site miyano run-tests --module erpnext.einvoice.$m
done
bench --site miyano run-tests --module erpnext.einvoice.report.doi_soat_hoa_don_dien_tu.test_doi_soat_hoa_don_dien_tu
```

> `bench run-tests --module A --module B` chỉ chạy module **cuối cùng** — phải
> lặp từng module một như trên.

**Điều kiện go-live:** 12/12 kịch bản đạt trên môi trường TEST · đã đào tạo kế
toán · **tuần đầu chạy song song**, cuối mỗi ngày đối chiếu tay giữa ERP và
portal Fast.

---

## 6. Ghi chú kỹ thuật cho dev

- **Mọi lời gọi Fast đi qua `gateway.call_fast`**, nên tự động ghi log trước và
  sau (nguyên tắc A1). Đừng gọi `FastClient` thẳng từ tầng nghiệp vụ.
- **Nhật ký là bằng chứng đối chiếu** với Fast và CQT: read-only, giữ 24 tháng,
  che mật khẩu/token, payload lưu dạng đọc được (không phải base64).
- **Bảng trạng thái B2 nằm ở `form_state.py`**, không nhân bản trong JS. Thêm
  nút mới thì sửa ở đó, giao diện tự có.
- **Không test nào chạm mạng.** Transport được tiêm vào `FastClient`; muốn thêm
  kịch bản chỉ cần dựng thêm `envelope(...)`.
- `setup_einvoice()` chạy sau mỗi lần `bench migrate` và **chạy lại được nhiều
  lần** — thêm custom field hoặc mẫu email mới không cần viết patch.

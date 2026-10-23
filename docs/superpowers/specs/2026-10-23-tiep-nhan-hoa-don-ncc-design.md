# Thiết kế: Đợt 4 — Hợp đồng khung, tiếp nhận hóa đơn NCC và đối soát 4 tầng (FRD-MAP-01, phần 1)

| Mục | Nội dung |
|---|---|
| Hệ thống | Miyano ERP (fork ERPNext v15.83.0), site `miyano` |
| Nhánh | `feat/tiep-nhan-chung-tu-ncc` (cắt từ `feat/auto-check-selling-price` tại `d0da26f`) |
| Ngày | 23/10/2026 |
| Căn cứ | `docs/FRD_Doi_soat_hoa_don_NCC_v1.0.docx` (FRD-MAP-01); spec `2026-10-21-kiem-gia-ban-bao-gia-doi-soat-design.md` mục 6.3, 6.4, 8 (Đợt 4) |
| Liên quan | Đợt 1 (giá mua "HĐ nguyên tắc"), Đợt 3 (đối soát Phiếu nhập ↔ Hóa đơn mua, ĐNTT nháp) |

## 1. Quyết định của người dùng (23/10/2026)

| Mã | Quyết định |
|---|---|
| D4-1 | **Giữ mã hàng hiện tại.** Không sinh item_code mới theo từng dòng hợp đồng. Hợp đồng khung (HĐK) dùng **Blanket Order** loại Purchasing; mã dạng `[NCC]-[Số HĐK]-[Nhóm]-[STT]` là **mã dòng HĐK** để tra cứu và để NCC ghi lên hóa đơn |
| D4-2 | **HĐK là nguồn giá duy nhất.** Nộp HĐK thì hệ thống ghi giá từng dòng vào bảng giá mua của NCC (Item Price có `supplier`), nên kiểm giá Đợt 1 dùng tiếp như giá "HĐ nguyên tắc". Hủy HĐK thì xóa các giá đó |
| D4-3 | **Phần 1 chỉ làm phần không phụ thuộc bên ngoài:** HĐK, Bảng ánh xạ tên, Phiếu tiếp nhận hóa đơn đọc **XML hóa đơn điện tử**, đối soát 4 tầng, tạo Hóa đơn mua nháp, cảnh báo lệch giá / vượt hạn mức. Để đợt sau: đọc ảnh/PDF bằng Claude (FR-14, FR-15 phần ảnh; cần khóa API và Ban Điều hành đồng ý), chặn PO nhập tay và lọc mã trên Yêu cầu vật tư (FR-06 → FR-09), mẫu in / email đặt hàng (FR-12, FR-13) |
| D4-4 | Ba câu hỏi mở của FRD (20.3) thành ô cài đặt: người duyệt lệch giá HĐK = vai trò (mặc định Ban Điều hành của Đợt 3), ngưỡng cảnh báo hạn mức (mặc định 90%), hóa đơn hàng ngoài HĐK **vẫn nhận**, chuyển chọn tay |
| D4-5 | Theo nguyên tắc BA12 / YC5: không sửa JSON DocType chuẩn. Trường thêm là Custom Field; DocType mới đặt ở module Buying; điểm gắn ở `hooks.py` |

## 2. Hợp đồng khung (Blanket Order, Purchasing)

ERPNext đã có: một dòng một mặt hàng, `qty` (hạn mức), `ordered_qty` (đã đặt qua PO), `party_item_code`
(mã hàng NCC, lấy từ Item Supplier), `from_date` / `to_date`, `order_no` (dùng làm số HĐK). PO dòng tích
"Against Blanket Order" thì ERPNext chặn đặt vượt `qty - ordered_qty` (+ Blanket Order Allowance).

Thêm (Custom Field):

| DocType | Trường |
|---|---|
| Blanket Order | `bang_gia_mua` (Price List mua; mặc định bảng giá mặc định của NCC) |
| Blanket Order Item | `ma_dong_hdk` (mã dòng, tự sinh, sửa được trước khi Nộp, duy nhất), `ten_hdk` (tên nguyên văn), `quy_cach`, `chat_lieu`, `hang_sx`, `nuoc_sx`, `so_luu_hanh`, `thue_suat` (%), `da_lap_hoa_don` (số lượng đã lập hóa đơn mua đã Nộp, chỉ đọc) |
| Supplier, Item Group | `ma_viet_tat` (phần [NCC], [Nhóm] của mã dòng; trống thì lấy chữ cái đầu của tên) |
| Item Price | `hop_dong_khung` (Link Blanket Order, chỉ đọc): giá do HĐK ghi |

Quy tắc:
- Nộp HĐK mua: bắt buộc Số HĐK, bảng giá mua, và trên mỗi dòng: tên HĐK, quy cách, hãng, nước sản xuất, số lưu hành, đơn giá > 0, thuế suất, số lượng > 0 (FR-02 áp ở dòng HĐK thay vì thẻ vật tư, D4-1).
- `ma_dong_hdk` trùng với dòng HĐK khác chưa hủy: chặn (BR-01).
- Nộp: ghi / cập nhật Item Price (bảng giá mua, mặt hàng, NCC, `valid_from` = từ ngày, `valid_upto` = đến ngày, ĐVT kho). Đã có giá cùng (bảng giá, mặt hàng, NCC, từ ngày) thì cập nhật giá đó. Hủy: xóa các Item Price có `hop_dong_khung` = HĐK này.
- PO: dòng chưa gắn HĐK mà có đúng một HĐK đã Nộp còn hiệu lực của NCC chứa mặt hàng → tự gắn (`against_blanket_order`, `blanket_order`, `blanket_order_rate`), để ERPNext tính đã đặt và chặn vượt. Sau đơn này đạt ≥ ngưỡng cảnh báo hạn mức thì cảnh báo (FR-11).
- Hóa đơn mua Nộp / hủy: cập nhật `da_lap_hoa_don` của dòng HĐK (FR-23, lũy kế đã mua).

## 3. Bảng ánh xạ tên (`Supplier Item Alias`, DT-06)

Trường: NCC, tên trên hóa đơn, tên chuẩn hóa (tự tính), mặt hàng, nguồn (Khớp theo PO / Người dùng chọn tay),
trạng thái (Chờ duyệt / Đang dùng / Ngừng dùng), số lần dùng, lần cuối. Duy nhất theo (NCC, tên chuẩn hóa)
khi chưa Ngừng dùng (BR-04). Tầng 2 chỉ dùng dòng Đang dùng. Dòng mới sinh từ tầng 3 / tầng 4 ở trạng thái
Chờ duyệt (FR-22); người có vai trò duyệt ánh xạ (cài đặt) bấm Duyệt / Ngừng dùng.

## 4. Phiếu tiếp nhận hóa đơn (`Supplier Invoice Intake`, DT-07)

Đầu phiếu: công ty, tệp XML, trạng thái (ST-01 → ST-07), NCC (tìm theo MST người bán), tên + MST người bán / người
mua, ký hiệu, số, ngày hóa đơn, số PO ghi trên hóa đơn, Đơn mua hàng, tổng tiền hàng / thuế / thanh toán, tỷ lệ khớp,
hóa đơn mua đã tạo, lý do từ chối, dữ liệu trích xuất (JSON), phê duyệt cảnh báo (người, lý do, thời điểm, dấu vân tay).

Dòng: STT, mã hàng / tên / ĐVT / số lượng / đơn giá / thành tiền / thuế suất **theo hóa đơn**; kết quả: mặt hàng,
dòng HĐK, Đơn mua hàng + dòng, cách khớp (Tầng 1 mã / Tầng 2 ánh xạ tên / Tầng 3 Đơn mua / Chọn tay), điểm khớp,
trạng thái dòng (Đã khớp / Chờ xác nhận / Chưa khớp), cảnh báo, ô Chọn tay / Đã xác nhận.

Luồng (mỗi lần Lưu chạy lại; dòng chọn tay giữ nguyên):
1. Tệp mới → đọc XML (`HDon/DLHDon`: TTChung, NBan, NMua, DSHHDVu/HHDVu, TToan). Chỉ dòng hàng hóa (TChat 1); dòng
   khuyến mại / chiết khấu / ghi chú không vào đối soát. Đọc lỗi → ST-01, báo lỗi.
2. MST người mua ≠ MST cài đặt → ST-07 Từ chối (FR-16). Trùng (cùng NCC + ký hiệu + số) với phiếu khác chưa Từ chối
   hoặc Hóa đơn mua có cùng số → ST-07 (BR-08, TC-11). Cùng NCC, cùng tổng, cùng ngày → cảnh báo, phải tích "Đã kiểm
   không trùng" mới tạo hóa đơn (FR-17).
3. Kiểm số học: tổng các dòng = tổng tiền hàng; thuế; tổng thanh toán. Lệch → ST-04 (11.1).
4. Đối soát 4 tầng (mục 5) → mọi dòng Đã khớp và không còn cảnh báo chặn (hoặc đã được duyệt) → ST-03; còn lại ST-04.
5. Nút **Tạo hóa đơn mua nháp** (ST-03) → ST-05. Hóa đơn mua Nộp → ST-06; hủy / xóa → về ST-03.

Cảnh báo theo dòng: lệch đơn giá HĐK (BR-05, chặn), vượt hạn mức HĐK còn lại (BR-06, chặn), ĐVT hoặc thuế suất khác
HĐK (BR-07, chỉ ghi nhận). Cảnh báo chặn được người có vai trò duyệt lệch giá (cài đặt) **Duyệt** kèm lý do; phê duyệt
gắn với dấu vân tay danh sách cảnh báo, cảnh báo đổi thì mất hiệu lực (như ngoại lệ Đợt 3).

## 5. Đối soát 4 tầng (FRD mục 10)

- Chuẩn hóa: chữ thường, bỏ dấu, đ → d; thay từ đồng nghĩa (bảng trong cài đặt); bỏ từ vô nghĩa (cài đặt, mặc định
  `size, cỡ, loại, cái`) và dấu ngoặc.
- Khóa quy cách: tập mọi con số (kể cả thập phân, `7,5` = `7.5`) và cỡ chữ S / M / L / XL / XXL. Hai bên phải bằng
  nhau mới xét tiếp (BR-03).
- Điểm tên = trọng số Jaccard (0,6) × Jaccard tập từ + trọng số chuỗi (0,4) × SequenceMatcher; ≥ 0,75 khớp, 0,55 –
  0,75 chờ xác nhận, < 0,55 chọn tay. Ngưỡng và trọng số ở cài đặt (NFR-08).
- Tầng 1: mã trên hóa đơn = mã hàng Miyano, mã hàng NCC (Item Supplier / dòng HĐK) hoặc mã dòng HĐK. Khóa quy cách
  khác thì cảnh báo.
- Tầng 2: Bảng ánh xạ tên của NCC, tên chuẩn hóa trùng, Đang dùng.
- Tầng 3: dòng Đơn mua hàng của NCC (ưu tiên số PO ghi trên hóa đơn), còn số lượng chưa lập hóa đơn ≥ số lượng hóa
  đơn, cùng ĐVT, cùng đơn giá, cùng khóa quy cách, điểm tên ≥ 0,55 (so với tên HĐK nếu dòng PO gắn HĐK, không thì tên
  mặt hàng). Từ hai ứng viên trở lên: không tự chọn (BR-10) → tầng 4.
- Tầng 4: người dùng chọn mặt hàng (và dòng Đơn mua) trên dòng.
- Khớp ở tầng 3 / tầng 4: đề xuất dòng Bảng ánh xạ tên Chờ duyệt.

## 6. Tạo Hóa đơn mua nháp (FR-19)

Hóa đơn mua nháp (`docstatus` 0, không Nộp — BR-09): NCC, công ty, số HĐ NCC = số hóa đơn, ngày hóa đơn, dòng: mặt
hàng, số lượng / ĐVT / đơn giá theo hóa đơn, `purchase_order` + `po_detail`, Phiếu nhập: phân bổ số lượng vào các
dòng Phiếu nhập còn chưa lập hóa đơn theo thứ tự ngày nhập (tách dòng nếu cần), lấy ít hơn phần còn lại thì tích
**Hóa đơn từng phần** (Đợt 3). Chưa có Phiếu nhập cho dòng hàng kho thì không tạo, báo "chờ Kho nhập hàng". Thuế: mẫu
thuế của Đơn mua hàng. Trường thêm trên dòng: tên trên hóa đơn (BR-11), dòng HĐK, cách khớp, điểm khớp; trên hóa đơn:
phiếu tiếp nhận. Đính kèm tệp XML. Hóa đơn sau đó đi qua đối soát Phiếu nhập ↔ Hóa đơn của Đợt 3 như hóa đơn nhập tay.

## 7. Cài đặt (`Supplier Invoice Intake Settings`, Single)

Bật tiếp nhận; MST người mua (mặc định MST công ty); ngưỡng khớp tự động 0,75, ngưỡng chờ xác nhận 0,55; trọng số
Jaccard 0,6, trọng số chuỗi 0,4; từ đồng nghĩa (bảng: từ ↔ từ, mặc định `sonde ↔ ống thông`, `2 way ↔ 2 nhánh`,
`dùng 1 lần ↔ dùng một lần`, `găng khám ↔ găng tay khám`); từ bỏ qua; ngưỡng cảnh báo hạn mức 90%; vai trò duyệt
lệch giá (trống: Vai trò Ban Điều hành của Buying Settings, trống nữa: System Manager); vai trò duyệt ánh xạ tên
(trống: Purchase Manager). Chỉ System Manager sửa.

## 8. File

| Loại | Đường dẫn |
|---|---|
| DocType mới | `erpnext/buying/doctype/supplier_invoice_intake{,_item}/`, `supplier_item_alias/`, `supplier_invoice_intake_settings/`, `supplier_invoice_synonym/` |
| Logic | `erpnext/buying/tiep_nhan_hoa_don/` (`truong_tuy_bien`, `cau_hinh`, `chuan_hoa`, `doc_xml`, `hop_dong_khung`, `don_mua`, `doi_soat`, `tao_hoa_don`, `anh_xa`) |
| Điểm gắn | `erpnext/hooks.py`: `after_migrate`, `doc_events` (Blanket Order, Purchase Order, Purchase Invoice) |
| Test | `erpnext/buying/tests/test_tiep_nhan_hoa_don*.py` |

## 9. Ngoài phần 1

Đọc ảnh / PDF bằng Claude API; Yêu cầu vật tư chỉ chọn mã HĐK, PO chỉ tạo từ Yêu cầu vật tư, một PO một HĐK, khóa
giá PO; mẫu in PO và email đặt hàng có mã dòng HĐK; màn hình tra cứu mã và báo cáo tỷ lệ khớp (FR-03, FR-24); YC6
(nhập báo giá NCC dùng chung bộ tiếp nhận).

## 10. Kết quả phần 1 (23/10/2026)

| Phần | Test (`erpnext/buying/tests/`) |
|---|---|
| Chuẩn hóa, khóa quy cách, điểm tên (TC-12, TC-13), đọc XML (bọc `TDiep`, namespace, dòng không phải hàng hóa, tệp hỏng, chặn entity ngoài) | `test_tiep_nhan_hoa_don_doc.py` (12, không cần DB) |
| HĐK: Nộp ghi giá HĐ nguyên tắc và kiểm giá Đợt 1 đọc được, Hủy xóa giá; mã dòng tự sinh, không trùng; thiếu thông tin không Nộp được; PO tự gắn HĐK, cảnh báo ≥ 90%, ERPNext chặn vượt | `TestHopDongKhung` |
| Phiếu tiếp nhận: tầng 3 (TC-12) → Hóa đơn mua nháp gắn Phiếu nhập, Đợt 3 báo Khớp, đề xuất ánh xạ Chờ duyệt, Nộp → Đã ghi sổ + lũy kế HĐK, Hủy → mở lại; tầng 1 mã NCC; tầng 2 chỉ ánh xạ Đang dùng; TC-13 → chọn tay; TC-10 sai MST, TC-11 trùng → Từ chối; TC-14 lệch giá HĐK chặn đến khi được duyệt (vai trò); vượt hạn mức; lệch số học; chưa có Phiếu nhập; hóa đơn từng phần; xóa hóa đơn nháp mở lại phiếu; BR-10 nhiều ứng viên | `TestTiepNhanHoaDon` |
| Bảng ánh xạ tên: chỉ người duyệt đổi trạng thái; không trùng tên chuẩn hóa trong một NCC | `TestBangAnhXa` |

Tổng 30 test mới đạt; chạy chung với test Đợt 1 – 3 (kiểm giá, thông báo, đối soát PR ↔ PI): 473 test đạt, 3 bỏ qua.

**Lưu ý chạy test từ worktree:** `frappe.get_hooks` đọc `app_hooks` từ Redis dùng chung (trừ khi `developer_mode`),
và `chay_test.py` nạp `doc_events` một lần cho cả tiến trình. Chạy từ worktree thì dùng
`<worktree>/scripts/chay_test.py --worktree`. Cờ này nạp `erpnext` từ worktree và bật `developer_mode` riêng
trong tiến trình test. Nhờ vậy tiến trình đọc đúng `hooks.py` của nhánh, và không ghi hooks của nhánh vào
cache mà web đang dùng. Script của worktree mà chạy thiếu cờ thì tự từ chối. Kết quả với cờ này: 473 test
đạt, 3 bỏ qua.

### 10.1 Kiểm thử thủ công

- `docs/HDKT_Dot4_Tiep_nhan_hoa_don_NCC.md`: các mục A – K, xử lý sự cố ở mục L.
- `scripts/demo_tiep_nhan_hoa_don.py`: mỗi lần chạy tạo một NCC demo mới (MST riêng), kèm:
  - hợp đồng khung đã Nộp;
  - Đơn mua hàng và Phiếu nhập cho 14 kịch bản;
  - tệp XML hóa đơn có ghi số Đơn mua.

  Script từ chối chạy trên `miyano`; `--tra-lai` trả cài đặt về như cũ.
- Đã chạy thật mọi bước HDKT trên erpnext.localhost (23/10/2026) rồi hoàn tác. Trạng thái, số tiền và câu thông
  báo trong HDKT lấy từ lần chạy đó.
- Sau lần chạy, câu cảnh báo in số theo định dạng hệ thống (95/100 (95%), 13.000), thay cho 95.0 / VND 13.000,00.
- Đã thêm bản dịch tiếng Việt cho tên các DocType mới và câu chặn vượt hạn mức của ERPNext
  (`erpnext/translations/vi.csv`).
- **Quyền trên Đơn khung:** mặc định chỉ System Manager tạo / Nộp. Production cần cấp quyền cho vai trò phụ trách
  hợp đồng (Chuỗi cung ứng). Việc này là cấu hình site, chưa làm trong phần 1.

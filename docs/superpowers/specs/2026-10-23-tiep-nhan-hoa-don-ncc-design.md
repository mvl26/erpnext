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

Bổ sung 24/10/2026, theo hợp đồng nguyên tắc mẫu `001-GREENTECH-MIYANO_HDNT_v2.docx` (người dùng gửi):

| Mã | Quyết định |
|---|---|
| D4-6 | Đơn khung có **khung chung** của hợp đồng nguyên tắc: số hợp đồng, ngày ký, hiệu lực, các bên ký, tệp đã ký, giá gồm VAT, không cam kết số lượng, phụ lục, dòng hàng. Mẫu Greentech chỉ để tham khảo: mỗi NCC có hợp đồng riêng nên **điều khoản không thành trường cố định** (người dùng 25/10, thay bản 24/10 có ~25 trường điều khoản theo mẫu) — ghi ở mục Điều khoản và điều kiện chuẩn của ERPNext, lấy từ Mẫu điều khoản (Terms and Conditions, loại mua) người dùng tự tạo cho từng NCC / loại hợp đồng, sửa được trên từng hợp đồng. **Giá đã gồm VAT** khi tích thì quy về giá chưa VAT theo thuế suất dòng, **làm tròn đến đồng**, để ghi bảng giá mua (kiểm giá bán Đợt 1 dùng giá chưa VAT), ghi Đơn giá đơn khung trên Đơn mua và so với đơn giá hóa đơn. Làm tròn đến đồng để Đơn mua, Phiếu nhập và hóa đơn điện tử cùng một số (lần chạy thật 24/10 với giá 3.760.952,38 đã lệch 0,38 đồng ở đối soát Đợt 3) |
| D4-7 | **Một đơn giá mỗi dòng.** Mẫu có 2 mức giá theo số hộp mỗi đơn (5 – 9 / 10 – 30 hộp): mức khác ghi ở Ghi chú giá. Hóa đơn theo mức khác thì bị cảnh báo lệch giá hợp đồng và cần người duyệt (người dùng chọn 24/10) |
| D4-8 | **Không cam kết số lượng** (Điều 2.2): ô trên hợp đồng. Khi tích, dòng để Số lượng 0 = không giới hạn: không cảnh báo, không chặn hạn mức. ERPNext vốn bỏ qua kiểm vượt khi `qty` = 0. Không tích thì mỗi dòng phải có số lượng |
| D4-9 | **Đã Nộp thì không sửa** (chuẩn ERPNext): chỉ Đến ngày sửa được để gia hạn (Điều 12.1), và Frappe đòi quyền Nộp. Bổ sung mặt hàng / đổi giá theo phụ lục (Điều 2.4, 2.6, 12.2): lập Đơn khung mới có **Phụ lục của hợp đồng** = hợp đồng gốc. Phụ lục lấy số hợp đồng của gốc; mã dòng đánh số tiếp; phụ lục đổi giá phải có Từ ngày sau Từ ngày của gốc. Đơn mua ưu tiên gắn phụ lục; kiểm giá Đợt 1 lấy giá có Từ ngày mới nhất. Dòng Đơn mua đã có đơn khung (người dùng tích Theo đơn khung, ERPNext tự chọn hợp đồng đầu tiên và điền giá hợp đồng nguyên văn) cũng được chuẩn hóa khi Lưu: chuyển sang phụ lục của hợp đồng đã chọn, Đơn giá đơn khung = giá chưa VAT |
| D4-10 | **Quyền trên Đơn khung và người duyệt** (người dùng 25/10, thay bản 24/10 dùng Purchase Manager): giám đốc là người có quyền cao nhất, giữ vai trò **Sales Manager** (như kiểm giá bán Đợt 1 – 2) cho cả ba việc: Nộp / Hủy / Sửa đổi / gia hạn Đơn khung, duyệt lệch giá / vượt hạn mức, duyệt Bảng ánh xạ tên. Purchase User, Purchase Manager tạo, sửa bản nháp; Accounts User, Accounts Manager, Stock User chỉ xem; System Manager giữ quyền chuẩn. Custom DocPerm tạo ở `after_migrate` **một lần**, khi Blanket Order chưa có Custom DocPerm nào; quản trị chỉnh lại trong Role Permission Manager thì migrate sau không ghi đè. Hai ô vai trò duyệt của Cài đặt gieo Sales Manager lần đầu; để trống cũng hiểu là Sales Manager. Để duyệt mà không cần vai trò khác (người dùng 25/10): Sales Manager được xem Phiếu tiếp nhận (duyệt cảnh báo) và sửa Bảng ánh xạ tên (duyệt / ngừng dùng, sửa dòng) |
| D4-11 | **Không tự tạo vai trò**, chỉ dùng vai trò có sẵn. Demo Đợt 1 – 4: giám đốc = `demo.giamdoc` (Sales Manager); nhân viên demo không có vai trò này |
| D4-12 | **Đối soát Đợt 3 cho dung sai 1 đồng với hợp đồng giá gồm VAT** (người dùng 25/10). Chỉ áp cho dòng hóa đơn có `po_detail` thuộc dòng Đơn mua gắn Đơn khung tích Đơn giá đã gồm thuế GTGT: đơn giá lệch ≤ 1 đồng trên đơn giá hóa đơn (1 / hệ số quy đổi theo ĐVT kho); thành tiền dòng ≤ 1 đồng x số lượng hóa đơn; ba tổng cộng dồn dung sai các dòng đó, thêm 1 đồng / dòng cho làm tròn thuế. Lúc Nộp, ERPNext chỉ cho vượt thành tiền dòng Đơn mua 0,01 % (hàng 5.000 đồng + 1 đồng = 0,02 % bị chặn dù Khớp): hóa đơn Khớp được bỏ kiểm đó cho các dòng này khi phần vượt ≤ 1 đồng x số lượng dòng Đơn mua. Phiếu tiếp nhận dùng cùng dung sai. Dòng khác vẫn so 0 đồng. **Triển khai:** đối soát YC5 (`erpnext/accounts/doi_soat_pr_pi`) nay gọi code Đợt 4 (`hop_dong_khung.dong_don_mua_gia_gom_vat`), nên production phải lên Đợt 3 và Đợt 4 cùng nhau theo nhánh tích hợp `feat/auto-check-selling-price`; site chưa có trường Đợt 4 thì `has_column` bỏ qua, đối soát như cũ |
| D4-13 | **Trường bắt buộc khi Nộp hợp đồng khung chọn ở Cài đặt tiếp nhận hóa đơn NCC** (mục Hợp đồng khung, nút Chọn trường bắt buộc khi Nộp hợp đồng khung), không cố định trong code. Hệ thống luôn cần: NCC, Số hợp đồng, Bảng giá mua, đơn giá > 0, số lượng > 0 trừ khi không cam kết, Số phụ lục khi là phụ lục. Gieo một lần (`da_khoi_tao_truong_bat_buoc`): ngày ký, đại diện và MST hai bên, tài khoản và ngân hàng Bên B, Chi tiết điều khoản; dòng: mã hàng NCC, tên theo hợp đồng, quy cách, hãng, nước sản xuất, số lưu hành, thuế suất (FR-02). Trường quản trị tự thêm bằng Customize Form chọn được như trường có sẵn |
| D4-14 | **ST-05a "Lệch PR-PI"** (người dùng 25/10, spec 2026-10-21 mục 6.3.4). Hóa đơn mua nháp tạo từ phiếu bị đối soát Đợt 3 báo Lệch thì phiếu chuyển Lệch PR-PI (đỏ); hết lệch thì về Đã tạo nháp hóa đơn mua. Người theo dõi hóa đơn đầu vào lọc danh sách phiếu theo trạng thái này, không phải mở từng hóa đơn. Cách xử lý lệch giữ nguyên nhánh (a) / (b1) / (b2) của Đợt 3. Báo Mua hàng khi lệch đã có sẵn ở Supply Notification NTF-16 (lệch lúc tạo) và NTF-17 (chuyển sang Lệch), không viết thêm. Tên trạng thái dùng gạch ngang thường cho dễ lọc |
| D4-15 | **Từ chối tay và Mở lại** (người dùng 25/10). Người có quyền sửa phiếu bấm Từ chối, bắt buộc ghi lý do; hệ thống lưu người và thời điểm từ chối. Phiếu đang có Hóa đơn mua nháp thì bản nháp bị xóa (cần quyền xóa Hóa đơn mua); đã ghi sổ thì phải hủy trước. Phiếu Từ chối tay không tính lại khi Lưu; Mở lại thì đối soát lại từ đầu. Các ô Từ chối tay và ô phê duyệt cảnh báo chỉ đổi được qua nút: giá trị gửi từ form, API hay import bị trả về giá trị đang lưu (trước đây ô phê duyệt cảnh báo sửa được qua API) |
| D4-16 | **Hóa đơn thay thế** (người dùng 25/10). Đọc `TTChung/TTHDLQuan` (TCHDon 1), tìm hóa đơn bị thay thế theo MST người bán + ký hiệu + số (0000123 = 123). Hóa đơn cũ chưa có Hóa đơn mua thì phiếu cũ tự Từ chối ("bị thay thế bởi…"); có bản nháp do phiếu lập thì phiếu mới dừng, nút **Bỏ hóa đơn bị thay thế** xóa bản nháp và từ chối phiếu cũ; bản nháp nhập tay thì xóa tay; đã ghi sổ thì phải hủy Hóa đơn mua trước. Hóa đơn cũ chưa vào hệ thống thì chỉ cảnh báo. Phiếu thay thế bị Từ chối / xóa thì phiếu cũ mở lại |
| D4-17 | **Hóa đơn điều chỉnh** (người dùng 25/10, TCHDon 2; phần tăng dương, phần giảm âm — NĐ 123/2020 Điều 19). Mỗi dòng gắn với dòng hóa đơn gốc nó điều chỉnh: theo mã trên hóa đơn, rồi tên chuẩn hóa, rồi hóa đơn gốc chỉ có một dòng; không được thì người dùng chọn STT. Kiểu: **Số lượng** khi đơn giá bằng đơn giá gốc (dấu theo thành tiền), còn lại **Đơn giá** (chỉ đổi tiền). Hóa đơn gốc **chưa ghi sổ**: gộp vào MỘT Hóa đơn mua theo số sau điều chỉnh; Số HĐ NCC là số hóa đơn gốc, ô "Hóa đơn điều chỉnh đã gộp" ghi số hóa đơn điều chỉnh, đính kèm cả hai XML. Hóa đơn gốc đang có bản nháp thì nút **Lập lại Hóa đơn mua nháp (gốc + điều chỉnh)** xóa bản cũ và lập lại, lỗi thì hoàn tác cả lần bấm. Đối soát 4 tầng, kiểm giá / hạn mức HĐK và Đợt 3 chạy trên số sau điều chỉnh. Hóa đơn gốc **đã ghi sổ**: kế toán lập tay Hóa đơn mua trả hàng / bổ sung với Số HĐ NCC = số hóa đơn điều chỉnh, phiếu tự nối vào chứng từ đó và chuyển trạng thái theo nó. Không gộp được, phải xử lý tay rồi Từ chối phiếu: đổi thuế suất, hóa đơn gốc nhập tay, số sau điều chỉnh âm |
| D4-18 | **Sửa ánh xạ đã duyệt phải duyệt lại** (người dùng duyệt danh sách việc còn thiếu, 25/10). Dòng Bảng ánh xạ tên Đang dùng / Ngừng dùng bị người không có vai trò duyệt ánh xạ sửa NCC, tên (sau chuẩn hóa) hoặc Mặt hàng thì về Chờ duyệt, xóa người duyệt; tầng 2 thôi dùng tới khi duyệt lại. Chính người duyệt sửa thì coi như duyệt lại (ghi người, thời điểm). Ô Người duyệt / Thời điểm duyệt chỉ do server ghi |
| D4-19 | **Kế toán chỉ xem Phiếu tiếp nhận** (FRD; người dùng 25/10). Accounts Manager như Accounts User: xem, báo cáo, in (Sales Manager cũng chỉ xem, để duyệt cảnh báo); nút thao tác trên phiếu ẩn khi không có quyền ghi. Các thao tác xóa Hóa đơn mua nháp của phiếu (Lập lại theo điều chỉnh, Bỏ hóa đơn bị thay thế, Từ chối phiếu có bản nháp) cần cả quyền ghi phiếu lẫn quyền xóa Hóa đơn mua; người không đủ hai quyền làm theo hai bước: kế toán xóa bản nháp trên Hóa đơn mua (phiếu tự tính lại), rồi mua hàng bấm nút trên phiếu |

## 2. Hợp đồng khung (Blanket Order, Purchasing)

ERPNext đã có: một dòng một mặt hàng, `qty` (hạn mức), `ordered_qty` (đã đặt qua PO), `party_item_code`
(mã hàng NCC, lấy từ Item Supplier), `from_date` / `to_date`, `order_no` (dùng làm số HĐK). PO dòng tích
"Against Blanket Order" thì ERPNext chặn đặt vượt `qty - ordered_qty` (+ Blanket Order Allowance).

Thêm (Custom Field):

| DocType | Trường |
|---|---|
| Blanket Order | `bang_gia_mua` (Price List mua; mặc định bảng giá mặc định của NCC). Khung hợp đồng (D4-6, chỉ hiện với loại mua): `ma_hop_dong` (phần [Mã hợp đồng] của mã dòng, trống = Số hợp đồng bỏ dấu), `hop_dong_goc` + `so_phu_luc` (phụ lục, D4-9), `tep_hop_dong`, `gia_gom_vat`, `khong_cam_ket_so_luong`. **Các bên ký:** đại diện, chức vụ, MST, địa chỉ, số tài khoản, ngân hàng của Bên A và Bên B, thêm điện thoại và fax của Bên B; MST lấy từ Company / Supplier. Điều khoản: trường chuẩn `tc_name` (Mẫu điều khoản) + `terms`. Nhãn "Order No" dịch là "Số hợp đồng"; "Order Date" (Ngày đặt) là ngày ký |
| Blanket Order Item | `ma_hang_ncc` (mã hàng NCC theo hợp đồng; trống thì lấy mã trên thẻ mặt hàng; tầng 1 khớp mã này), `ma_dong_hdk` (mã dòng, tự sinh, sửa được trước khi Nộp, duy nhất), `ten_hdk` (tên nguyên văn), `quy_cach`, `chat_lieu`, `hang_sx`, `nuoc_sx`, `so_luu_hanh`, `dvt_hdk` (ĐVT theo hợp đồng, phải là ĐVT kho), `thue_suat` (%), `ghi_chu_gia` (D4-7), `da_lap_hoa_don` (số lượng đã lập hóa đơn mua đã Nộp, chỉ đọc) |
| Supplier, Item Group | `ma_viet_tat` (phần [NCC], [Nhóm] của mã dòng; trống thì lấy chữ cái đầu của tên) |
| Item Price | `hop_dong_khung` (Link Blanket Order, chỉ đọc): giá do HĐK ghi |

Quy tắc:
- Lưu: ô trống của các bên được điền từ thẻ công ty / NCC (MST, địa chỉ mặc định, tài khoản ngân hàng), rồi từ hợp đồng mua đã Nộp gần nhất của công ty / NCC (đại diện, chức vụ). Mã hàng NCC theo hợp đồng lấy từ thẻ mặt hàng nếu trống; ĐVT theo hợp đồng mặc định ĐVT kho, khác ĐVT kho thì chặn.
- Nộp HĐK mua: bắt buộc NCC, Số hợp đồng, Bảng giá mua, đơn giá > 0, số lượng > 0 trừ khi không cam kết số lượng, và các trường chọn ở Cài đặt (D4-13; mặc định gồm thông tin dòng theo FR-02, áp ở dòng HĐK thay vì thẻ vật tư, D4-1).
- `ma_dong_hdk` trùng với dòng HĐK khác chưa hủy: chặn (BR-01).
- Nộp: ghi / cập nhật Item Price (bảng giá mua, mặt hàng, NCC, `valid_from` = từ ngày, `valid_upto` = đến ngày, ĐVT kho, giá chưa VAT — D4-6). Đã có giá cùng (bảng giá, mặt hàng, NCC, từ ngày) thì cập nhật giá đó. Hủy: xóa các Item Price có `hop_dong_khung` = HĐK này.
- PO: dòng chưa gắn HĐK mà có đúng một HĐK đã Nộp còn hiệu lực của NCC chứa mặt hàng → tự gắn (`against_blanket_order`, `blanket_order`, `blanket_order_rate`), để ERPNext tính đã đặt và chặn vượt. Sau đơn này đạt ≥ ngưỡng cảnh báo hạn mức thì cảnh báo (FR-11).
- Hóa đơn mua Nộp / hủy: cập nhật `da_lap_hoa_don` của dòng HĐK (FR-23, lũy kế đã mua).

## 3. Bảng ánh xạ tên (`Supplier Item Alias`, DT-06)

Trường: NCC, tên trên hóa đơn, tên chuẩn hóa (tự tính), mặt hàng, nguồn (Khớp theo PO / Người dùng chọn tay),
trạng thái (Chờ duyệt / Đang dùng / Ngừng dùng), số lần dùng, lần cuối. Duy nhất theo (NCC, tên chuẩn hóa)
khi chưa Ngừng dùng (BR-04). Tầng 2 chỉ dùng dòng Đang dùng. Dòng mới sinh từ tầng 3 / tầng 4 ở trạng thái
Chờ duyệt (FR-22); người có vai trò duyệt ánh xạ (cài đặt) bấm Duyệt / Ngừng dùng.

## 4. Phiếu tiếp nhận hóa đơn (`Supplier Invoice Intake`, DT-07)

Đầu phiếu: công ty, tệp XML, trạng thái (ST-01 → ST-07, thêm ST-05a Lệch PR-PI), NCC (tìm theo MST người bán), tên
+ MST người bán / người mua, ký hiệu, số, ngày hóa đơn, số PO ghi trên hóa đơn, tính chất hóa đơn (Hóa đơn gốc / Thay
thế / Điều chỉnh) và hóa đơn liên quan (ký hiệu, số, ngày, phiếu và Hóa đơn mua của nó), Đơn mua hàng, tổng tiền hàng
/ thuế / thanh toán, tỷ lệ khớp, hóa đơn mua đã tạo, lý do từ chối, Từ chối tay (người, thời điểm), dữ liệu trích xuất
(JSON), phê duyệt cảnh báo (người, lý do, thời điểm, dấu vân tay).

Dòng: STT, mã hàng / tên / ĐVT / số lượng / đơn giá / thành tiền / thuế suất **theo hóa đơn**; kết quả: mặt hàng,
dòng HĐK, Đơn mua hàng + dòng, cách khớp (Tầng 1 mã / Tầng 2 ánh xạ tên / Tầng 3 Đơn mua / Chọn tay), điểm khớp,
trạng thái dòng (Đã khớp / Chờ xác nhận / Chưa khớp), cảnh báo, ô Chọn tay / Đã xác nhận. Hóa đơn điều chỉnh: dòng
hóa đơn gốc (STT), điều chỉnh theo (Số lượng / Đơn giá); hóa đơn gốc: số lượng / đơn giá / thành tiền sau điều chỉnh và
các hóa đơn điều chỉnh đã gộp.

Luồng (mỗi lần Lưu chạy lại; dòng chọn tay giữ nguyên):
1. Tệp mới → đọc XML (`HDon/DLHDon`: TTChung, NBan, NMua, DSHHDVu/HHDVu, TToan). Chỉ dòng hàng hóa (TChat 1); dòng
   khuyến mại / chiết khấu / ghi chú không vào đối soát. Đọc lỗi → ST-01, báo lỗi.
2. MST người mua ≠ MST cài đặt → ST-07 Từ chối (FR-16). Trùng (cùng NCC + ký hiệu + số) với phiếu khác chưa Từ chối
   hoặc Hóa đơn mua có cùng số → ST-07 (BR-08, TC-11). Cùng NCC, cùng tổng, cùng ngày → cảnh báo, phải tích "Đã kiểm
   không trùng" mới tạo hóa đơn (FR-17).
3. Kiểm số học: tổng các dòng = tổng tiền hàng; thuế; tổng thanh toán. Lệch → ST-04 (11.1).
4. Đối soát 4 tầng (mục 5) → mọi dòng Đã khớp và không còn cảnh báo chặn (hoặc đã được duyệt) → ST-03; còn lại ST-04.
5. Nút **Tạo hóa đơn mua nháp** (ST-03) → ST-05; đối soát Đợt 3 báo Lệch → ST-05a, hết lệch → ST-05 (D4-14). Hóa đơn
   mua Nộp → ST-06; hủy / xóa → về ST-03.
6. Hóa đơn thay thế / điều chỉnh: D4-16, D4-17 (`hoa_don_lien_quan`). Từ chối tay / Mở lại: D4-15.

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
| Logic | `erpnext/buying/tiep_nhan_hoa_don/` (`truong_tuy_bien`, `cau_hinh`, `chuan_hoa`, `doc_xml`, `hop_dong_khung`, `don_mua`, `doi_soat`, `hoa_don_lien_quan`, `tao_hoa_don`, `anh_xa`) |
| Điểm gắn | `erpnext/hooks.py`: `after_migrate`, `doc_events` (Blanket Order, Purchase Order, Purchase Invoice: `on_update` cho ST-05 / ST-05a và chứng từ lập tay của hóa đơn điều chỉnh, `after_delete` để tính lại phiếu thay thế / điều chỉnh) |
| Test | `erpnext/buying/tests/test_tiep_nhan_hoa_don*.py` |

## 9. Ngoài phần 1

Đọc ảnh / PDF bằng Claude API; Yêu cầu vật tư chỉ chọn mã HĐK, PO chỉ tạo từ Yêu cầu vật tư, một PO một HĐK, khóa
giá PO; mẫu in PO và email đặt hàng có mã dòng HĐK; màn hình tra cứu mã và báo cáo tỷ lệ khớp (FR-03, FR-24); YC6
(nhập báo giá NCC dùng chung bộ tiếp nhận).

## 10. Kết quả phần 1 (23/10/2026)

| Phần | Test (`erpnext/buying/tests/`) |
|---|---|
| Chuẩn hóa, khóa quy cách, điểm tên (TC-12, TC-13), đọc XML (bọc `TDiep`, namespace, dòng không phải hàng hóa, tệp hỏng, chặn entity ngoài, hóa đơn liên quan của hóa đơn điều chỉnh) | `test_tiep_nhan_hoa_don_doc.py` (13, không cần DB) |
| HĐK: Nộp ghi giá HĐ nguyên tắc và kiểm giá Đợt 1 đọc được, Hủy xóa giá; mã dòng tự sinh, không trùng; thiếu thông tin không Nộp được; PO tự gắn HĐK, cảnh báo ≥ 90%, ERPNext chặn vượt | `TestHopDongKhung` |
| Phiếu tiếp nhận: tầng 3 (TC-12) → Hóa đơn mua nháp gắn Phiếu nhập, Đợt 3 báo Khớp, đề xuất ánh xạ Chờ duyệt, Nộp → Đã ghi sổ + lũy kế HĐK, Hủy → mở lại; tầng 1 mã NCC; tầng 2 chỉ ánh xạ Đang dùng; TC-13 → chọn tay; TC-10 sai MST, TC-11 trùng → Từ chối; TC-14 lệch giá HĐK chặn đến khi được duyệt (vai trò); vượt hạn mức; lệch số học; chưa có Phiếu nhập; hóa đơn từng phần; xóa hóa đơn nháp mở lại phiếu; BR-10 nhiều ứng viên | `TestTiepNhanHoaDon` |
| Bảng ánh xạ tên: chỉ người duyệt đổi trạng thái; không trùng tên chuẩn hóa trong một NCC; sửa ánh xạ đã duyệt về Chờ duyệt, người duyệt sửa thì giữ, không tự ghi được người duyệt (D4-18); giám đốc chỉ có Sales Manager duyệt và sửa được | `TestBangAnhXa` |
| Hợp đồng nguyên tắc (24/10, D4-6 → D4-10): thiếu thông tin các bên / điều khoản không Nộp được; điều khoản mặc định theo mẫu; tự điền các bên theo hợp đồng gần nhất; giá gồm VAT quy về chưa VAT chẵn đồng (bảng giá mua, kiểm giá Đợt 1, Đơn giá đơn khung, hóa đơn khớp và Hóa đơn mua khớp Phiếu nhập; giá bậc 2 bị chặn); không cam kết số lượng (không chặn, không cảnh báo); ĐVT theo hợp đồng phải là ĐVT kho; tầng 1 theo mã hàng NCC ghi trong hợp đồng; phụ lục (số hợp đồng của gốc, mã dòng đánh số tiếp, thiếu Số phụ lục không Nộp được, Đơn mua gắn phụ lục kể cả khi người dùng đã chọn hợp đồng gốc, cùng Từ ngày với gốc thì chặn) | `TestHopDongKhung` |
| Quyền Đơn khung: Purchase User lưu nháp nhưng không Nộp được, Purchase Manager Nộp; Accounts User không tạo được | `TestQuyenDonKhung` |
| ST-05a, Từ chối tay, quyền phiếu (25/10, D4-14, D4-15, D4-19): kế toán chỉ xem phiếu, không Từ chối / tạo hóa đơn được; giám đốc chỉ có Sales Manager xem phiếu và duyệt cảnh báo được; Kho nhận thiếu → Hóa đơn mua Lệch → phiếu Lệch PR-PI, sửa hóa đơn hết lệch → về Đã tạo nháp; Từ chối tay bắt buộc lý do, xóa hóa đơn nháp, sửa thẳng ô không bỏ được, Mở lại đối soát lại; phiếu đã ghi sổ không Từ chối được; ô phê duyệt cảnh báo không giả mạo được qua API | `TestTrangThaiVaTuChoi` |
| Hóa đơn thay thế (D4-16): phiếu cũ chưa có Hóa đơn mua tự Từ chối, không báo nghi trùng; phiếu thay thế bị Từ chối thì phiếu cũ mở lại; có bản nháp → Bỏ hóa đơn bị thay thế; đã ghi sổ → phải hủy trước, hủy xong tự đi tiếp; hóa đơn cũ chưa tiếp nhận chỉ cảnh báo | `TestHoaDonThayThe` |
| Hóa đơn điều chỉnh (D4-17): (b2) giảm số lượng khi gốc đang Lệch PR-PI → lập lại một Hóa đơn mua 480, Khớp, ghi số hóa đơn điều chỉnh, đính hai XML, Nộp / Hủy cập nhật cả hai phiếu; giảm giá trước khi lập hóa đơn hết cảnh báo lệch giá HĐK; kế toán xóa bản nháp rồi mua hàng lập lại (hai bước); gốc đã ghi sổ → nối Hóa đơn mua trả hàng kế toán lập (số 602 = 0000602), xóa chứng từ đó thì phiếu về Chờ xử lý; chưa có hóa đơn gốc; đổi thuế suất chặn cả phiếu gốc tới khi Từ chối phiếu điều chỉnh; chọn tay dòng gốc | `TestHoaDonDieuChinh` |

Tổng 41 test Đợt 4 đạt (gồm trường bắt buộc theo Cài đặt, quyền Sales Manager, dung sai 1 đồng: hàng 5.000 đồng hóa đơn cao hơn 1 đồng vẫn Khớp và Nộp được — tắt bản vá thì ERPNext báo "over limit by Amount 10.0"); chạy chung với test Đợt 1 – 3 (kiểm giá, thông báo, đối soát PR ↔ PI, 47 test YC5 vẫn so 0 đồng cho dòng thường): 484 test đạt, 3 bỏ qua (24/10/2026).

Thêm D4-14 → D4-17 (25/10/2026): 56 test Đợt 4 đạt; cả 25 module (Đợt 1 – 4, YC5, Supply Notification) chạy từ worktree với `--worktree`: 499 test đạt, 3 bỏ qua. Thêm D4-18, D4-19: 59 test Đợt 4 đạt, 47 test YC5 vẫn đạt.

**Lưu ý chạy test từ worktree:** `frappe.get_hooks` đọc `app_hooks` từ Redis dùng chung (trừ khi `developer_mode`),
và `chay_test.py` nạp `doc_events` một lần cho cả tiến trình. Chạy từ worktree thì dùng
`<worktree>/scripts/chay_test.py --worktree`. Cờ này nạp `erpnext` từ worktree và bật `developer_mode` riêng
trong tiến trình test. Nhờ vậy tiến trình đọc đúng `hooks.py` của nhánh, và không ghi hooks của nhánh vào
cache mà web đang dùng. Script của worktree mà chạy thiếu cờ thì tự từ chối. Kết quả với cờ này: 473 test
đạt, 3 bỏ qua.

### 10.1 Kiểm thử thủ công

- `docs/HDKT_Dot4_Tiep_nhan_hoa_don_NCC.md`: các mục A – N, tắt công tắc ở mục O, xử lý sự cố ở mục P.
- `scripts/demo_tiep_nhan_hoa_don.py`: mỗi lần chạy tạo một NCC demo mới (MST riêng), kèm:
  - hai hợp đồng khung đã Nộp, mỗi hợp đồng một Mẫu điều khoản;
  - Đơn mua hàng và Phiếu nhập cho 19 kịch bản (thêm R: Kho nhận thiếu → Lệch PR-PI → hóa đơn điều chỉnh giảm; S: hóa đơn thay thế);
  - tệp XML hóa đơn có ghi số Đơn mua.

  Script từ chối chạy trên `miyano`; `--tra-lai` trả cài đặt về như cũ.
- Đã chạy thật mọi bước HDKT trên erpnext.localhost (23/10/2026) rồi hoàn tác. Trạng thái, số tiền và câu thông
  báo trong HDKT lấy từ lần chạy đó. Các mục L – N (kịch bản R, S, Từ chối tay) chạy lại như vậy ngày 25/10/2026
  bằng người dùng demo: nhân viên mua hàng không xóa được Hóa đơn mua nháp nên các nút Lập lại / Bỏ hóa đơn bị
  thay thế / Từ chối phiếu có bản nháp do `demo.ketoantruong` bấm.
- Sau lần chạy, câu cảnh báo in số theo định dạng hệ thống (95/100 (95%), 13.000), thay cho 95.0 / VND 13.000,00.
- Đã thêm bản dịch tiếng Việt cho tên các DocType mới và câu chặn vượt hạn mức của ERPNext
  (`erpnext/translations/vi.csv`).
- **Quyền trên Đơn khung:** mặc định chỉ System Manager tạo / Nộp. Production cần cấp quyền cho vai trò phụ trách
  hợp đồng (Chuỗi cung ứng). Việc này là cấu hình site, chưa làm trong phần 1.

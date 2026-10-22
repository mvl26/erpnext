# BA12-TKKT — Thiết kế kỹ thuật: Đối soát giá mua – giá bán theo hệ số khách hàng

| Mục | Nội dung |
|---|---|
| Căn cứ | BA12 V1.0 (21/10/2026, CHỐT ĐỂ BUILD) + trả lời của PO ngày 22/10/2026 |
| Dev | Minh (MinhBiTong) |
| Nhánh | `feat/bao-truoc-doi-gia-himedic` (tách từ `feat/auto-check-selling-price`) |
| Liên quan | Spec `docs/superpowers/specs/2026-10-21-kiem-gia-ban-bao-gia-doi-soat-design.md` (YC3–YC6; mục 15 ghi phần BA12 thay thế); hướng dẫn test `docs/HDKT_BA12_Kiem_gia_ban.md`, `docs/HDKT_Dot2_Bao_truoc_doi_gia.md`; hướng dẫn nhân viên `docs/HDSD_BA12_Nhan_vien_ban_hang.md` |

## 1. Nguyên tắc

- **Không sửa core ERPNext** (PO 22/10): mọi trường thêm trên DocType chuẩn là **Custom Field**; logic gắn qua **`hooks.py`** (`doc_events`, `doctype_js`). Các file chuẩn (`selling_controller.py`, `accounts_controller.py`, JSON/PY/JS của Customer, Sales Order, Price List…) giữ nguyên như `develop`.
- Logic tính giá và cảnh báo nằm ở lõi ERPNext (app `erpnext`); **Portal (`miyano_portal`, Việt làm) chỉ hiển thị** qua API.
- Mỗi điểm trong code ghi mã Dxx/Rxx/Axx của BA12.

## 2. Chọn mức giải pháp (cấu hình chuẩn → customize → phát triển mới)

| Yêu cầu | Mức | Lý do |
|---|---|---|
| R01 Hệ số theo khách, số HĐ, hiệu lực | **Customize**: bảng con mới `Customer Price Coefficient` gắn vào Customer bằng Custom Field (Table) | Chuẩn không có hệ số theo khách; Pricing Rule tính theo bảng giá bán, không theo giá mua × hệ số |
| R02/D07 Giá mua: báo giá đợt → HĐ nguyên tắc | **Phát triển mới** (`gia_goc.py`) đọc dữ liệu chuẩn: Supplier Quotation, Item Price | Chuẩn không có khái niệm "giá mua còn hiệu lực theo NCC" để so với giá bán |
| D08 NCC dự kiến trên dòng | **Customize**: Custom Field `ncc_du_kien` | Trường `supplier` chuẩn của dòng SO gắn với giao thẳng (drop ship) — dùng lại sẽ đổi nghĩa |
| R03/R04/D04 Giá đề xuất, cảnh báo | **Phát triển mới** (`kiem_chung_tu.py`) qua `doc_events.validate` | Không có cấu hình tương đương |
| R04/R05/R08 Chặn Submit | **Phát triển mới** qua `doc_events.before_submit` | `validate_selling_price` chuẩn chỉ so với giá mua cuối/định giá, không đòi lý do hay văn bản |
| R06 Thông báo giá mới | **Phát triển mới**: Communication (email chuẩn Frappe) + API cho Portal | Notification chuẩn không dựng được bảng giá cũ/mới theo dòng R05 |
| A08 Báo cáo | **Phát triển mới**: Script Report | — |

## 3. Mô hình dữ liệu

### 3.1 DocType mới

`Customer Price Coefficient` (bảng con, module Selling): `item_code`, `he_so` (Float 4 số lẻ), `so_hop_dong`, `tu_ngay`, `den_ngay`.

### 3.2 Custom Field (`erpnext/selling/kiem_gia/truong_tuy_bien.py`, tạo ở `after_migrate`)

| DocType | Trường | Ghi chú |
|---|---|---|
| Selling Settings | `bat_kiem_gia_ban`, `vai_tro_sua_ty_le_lai` | Công tắc chung; vai trò Giám đốc được sửa hệ số |
| Customer | `he_so_gia_ban` (Table), `he_so_theo_mat_hang` (Table) | R01; hệ số theo mặt hàng chỉ áp khi khách KHÔNG có hệ số chung |
| Quotation Item, Sales Order Item | `ncc_du_kien`, `trang_thai_gia`, `gia_mua`, `nguon_gia_mua`, `chung_tu_gia_mua`, `ngay_gia_mua`, `he_so_gia_ban`, `so_hop_dong_he_so`, `gia_de_xuat`, `chenh_lech_gia`, `gia_bang_gia`, `khac_bang_gia`, `ghi_chu_gia` | Server ghi, chỉ đọc |
| Sales Order Item | `so_van_ban_gia`, `nguoi_dai_dien_kh`, `ngay_chap_thuan_gia` (R05, sửa được sau Submit), `gia_da_kiem` (ẩn) | R05 ghi **theo từng dòng** (PO chốt) |
| Sales Order | `ly_do_lech_gia` (R04/R08, sửa được sau Submit), `thong_bao_gia_moi` (Link Communication, R06) | |
| Price List, Item Price | trường báo trước đổi giá (YC4) | Giữ nguyên tên trường của Đợt 2 |

Trạng thái dòng: Khớp / Thấp hơn / Cao hơn / Chưa có giá mua / Đang trong thời hạn báo giá (YC4) / Bỏ qua.

## 4. Luồng và quy tắc

### 4.1 Hệ số (R01, R07)

- Mỗi ngày tối đa **một** hệ số hiệu lực (chặn chồng lấn); hệ số theo khách bắt buộc số hợp đồng.
- Khách có dòng hệ số chung → bảng hệ số theo mặt hàng **bị khóa trên form và không áp** (PO: "nếu ô % lãi theo khách hàng được chọn thì ô % lãi theo item phải disable").
- Không có hệ số hiệu lực tại ngày SO → **không tính, không cảnh báo** (R07). Không còn "1% mặc định cho mọi khách".
- Chỉ vai trò ở `vai_tro_sua_ty_le_lai` (Giám đốc) được sửa hệ số (kiểm ở server).

### 4.2 Giá mua (R02, D07, D08)

NCC = `ncc_du_kien` (trống → NCC mặc định của mặt hàng: dòng `is_default` ở Supplier Items).

1. **Báo giá đợt**: Supplier Quotation `docstatus = 1`, không Stopped, cùng công ty, của NCC, `transaction_date ≤ ngày SO ≤ valid_till` (trống = còn hiệu lực); lấy báo giá mới nhất; giá = `base_net_rate / conversion_factor` (chưa VAT, sau chiết khấu, ĐVT kho).
2. **HĐ nguyên tắc**: Item Price `buying = 1`, `supplier` = NCC (bảng giá "Mua - <NCC>"), bảng giá đang bật, cùng tiền tệ công ty, hiệu lực tại ngày SO, `valid_from` mới nhất; quy về ĐVT kho.
3. Không có → **Chưa có giá mua** (R08).

Mơ hồ (một báo giá có 2 giá khác nhau; 2 giá HĐ cùng ngày khác nhau) → không tự chọn, xếp "Chưa có giá mua" kèm lý do.

**Đề xuất về PR/PI** (PO cho phép đề xuất): **không** dùng Purchase Receipt / Purchase Invoice làm giá HĐ nguyên tắc — đó là giá thực mua từng lần (có thể kèm chiết khấu, khuyến mãi, sai sót), không phải giá cam kết; PO cũng đã chốt "Giá HĐ nguyên tắc lưu ở bảng giá Mua - <NCC>". PR/PI là đầu vào của đối soát PR ↔ PI (YC5), không phải của BA12.

### 4.3 Giá đề xuất và so sánh (R03, R04, D04)

- Giá đề xuất = giá mua (ĐVT dòng, tiền tệ chứng từ) × hệ số, **làm tròn đến đồng, nửa đồng làm tròn lên**, áp cho mọi đơn vị tiền (PO chốt).
- So với `net_rate` (sau chiết khấu đơn, bỏ thuế gồm trong đơn giá) làm tròn đến đồng; khác 0 là lệch (không dung sai).
- D06: nút **Áp giá đề xuất** trên SO nháp chép giá đề xuất vào đơn giá các dòng lệch.

### 4.4 So với bảng giá KH (R05)

- Giá bảng giá = giá trong `selling_price_list` của SO tại ngày SO (giá riêng của khách ưu tiên), quy về ĐVT dòng.
- `khac_bang_gia` = bảng giá **có** giá và khác giá đề xuất (sau làm tròn). Bảng giá không có giá cho mặt hàng → không tính là khác.
- Dòng "Đang trong thời hạn báo giá" (YC4: giá mới đã nằm trong luồng báo trước 7 ngày) → không tính là khác bảng giá.

### 4.5 Submit (R04, R05, R08, D03)

`before_submit` của Sales Order:
1. Còn dòng Thấp hơn / Cao hơn / Chưa có giá mua → bắt buộc `ly_do_lech_gia`.
2. Dòng `khac_bang_gia` → bắt buộc đủ 3 ô R05 trên dòng; báo rõ dòng và ô thiếu.
3. Người dùng cổng (Website User) chỉ nhận thông báo chung, không lộ giá.

Không còn chế độ "Chặn", không còn vai trò/bước duyệt giá lệch (PO 22/10).

"Update Items" sau Submit (`before_update_after_submit`): chỉ kiểm lại dòng vừa thêm/đổi (nhận biết bằng `modified` trong DB mới hơn lần lưu trước của SO); dòng không đụng giữ kết quả cũ (D05). Dòng mới khác bảng giá → bị chặn (hộp thoại Update Items không có ô R05 — dùng Amend).

### 4.6 Thông báo giá mới (R06, D10, D12)

`on_submit` của Sales Order, khi có dòng `khac_bang_gia`:
- Email (Communication, lưu trên timeline SO) tới người đặt đơn: `contact_email` của SO; trống thì email của người tạo nếu là tài khoản cổng. Nội dung: mặt hàng, giá cũ (bảng giá), giá mới (giá trên SO), số văn bản. Gắn vào `thong_bao_gia_moi`.
- Không có email → cảnh báo, SO vẫn xác nhận.
- **API cho Portal** (Việt): `erpnext.selling.kiem_gia.thong_bao_gia_moi.lay_thong_bao_gia_moi(sales_order)` → `{sales_order, customer, ngay, dong: [{item_code, item_name, uom, gia_cu, gia_moi, so_van_ban, ngay_chap_thuan}]}`; kiểm quyền đọc SO (khách chỉ thấy đơn của mình). Cùng nguồn dữ liệu với email (D12).

### 4.7 Báo cáo (A08, D05)

- **Doi Soat Gia Mua Gia Ban** (mới): mỗi dòng SO đã kiểm — SO, ngày, KH, mặt hàng, NCC, nguồn giá, chứng từ giá mua, giá mua, hệ số, số HĐ, giá đề xuất, giá bán, chênh lệch, giá bảng giá, trạng thái, lý do, số văn bản, người đại diện, ngày chấp thuận; thêm **Giá mua hiện tại / Giá mua đổi** (D05: giá mua đổi sau SO chỉ hiện ở báo cáo). Lọc: công ty, kỳ, KH, NCC, mặt hàng, chỉ dòng lệch, gồm SO nháp.
- **Doi Chieu Gia Ban Gia Mua** (có từ trước, đã chuyển sang hệ số): rà một bảng giá bán so với giá mua × hệ số của khách.

## 5. Điểm gắn (hooks.py)

| DocType | Sự kiện | Hàm |
|---|---|---|
| Quotation, Sales Order | validate | `bao_truoc.kiem_chung_tu_ban`, `kiem_chung_tu.kiem_chung_tu` |
| Sales Order | before_submit / on_submit / before_update_after_submit | `kiem_truoc_submit` / `thong_bao_gia_moi.gui_khi_xac_nhan` / `kiem_sau_submit` |
| Sales Invoice, Delivery Note, POS Invoice | validate | `bao_truoc.kiem_chung_tu_ban` (YC4) |
| Purchase Order | validate | `kiem_po.kiem_po` (cảnh báo PO giá cao hơn giá mua đã dùng ở SO) |
| Customer / Selling Settings | validate | `cau_hinh.kiem_khach` / `kiem_selling_settings` |
| Price List / Item Price | validate, on_trash | `bao_truoc.*` (YC4) |
| Customer, Selling Settings, Sales Order, Price List | doctype_js | `public/js/kiem_gia/*.js` |
| — | after_migrate | `truong_tuy_bien.tao_truong_tuy_bien` |

## 6. Thay đổi so với spec YC3 (Đợt 1) đã làm

| Bỏ / đổi | Thay bằng |
|---|---|
| % lãi mặc định 1% cho mọi khách | R07: không hệ số → không kiểm |
| % lãi trên Customer (một số), % theo (khách, mặt hàng) trong Item Customer Detail | Bảng hệ số có số HĐ và hiệu lực trên Customer; hệ số theo mặt hàng trên Customer, bị khóa khi có hệ số chung |
| Giá gốc = bảng giá mua bất kỳ, ưu tiên NCC mặc định | D07: báo giá đợt → HĐ nguyên tắc của NCC dự kiến |
| Submit báo giá NCC ghi giá vào bảng giá mua; Submit báo giá NCC tự tạo nháp giá Himedic | Bỏ — báo giá NCC được đọc trực tiếp (D07); bảng giá KH cập nhật thủ công (D09) |
| Làm tròn theo độ chính xác trường (4 số lẻ) | Làm tròn đến đồng |
| Chế độ "Chỉ ghi nhận / Chặn", vai trò duyệt, nút Duyệt giá lệch | Submit chỉ cần lý do (R04/R08) + 3 thông tin (R05) |
| Sửa thẳng JSON/controller chuẩn | Custom Field + hooks |

## 7. Kiểm thử

- Test tự động: `erpnext/selling/tests/test_kiem_gia_*.py` (chung_tu, goc, cau_hinh, submit, thong_bao_gia_moi, bao_cao, po, bao_truoc) — mỗi tiêu chí A01–A08 có test kiểm dữ liệu lưu trong DB.
- Thủ công: `docs/HDKT_BA12_Kiem_gia_ban.md`. Dữ liệu demo: `scripts/demo_gia_ban_doi_soat.py`.
- **Chưa làm (cần staging):** regression Portal → SO → DN → SI → HĐĐT FAST.

## 8. Triển khai

1. `bench --site miyano migrate` (tạo Custom Field, DocType `Customer Price Coefficient`, báo cáo).
2. Selling Settings: chọn **Vai trò được sửa hệ số giá bán** (Giám đốc).
3. Nhập hệ số + số HĐ + ngày hiệu lực cho khách áp hệ số (DoR: danh sách từ chị Anh/anh Xuân/chị Thư).
4. Kiểm: mọi dòng giá trong các bảng giá "Mua - <NCC>" có điền **Supplier** (production 21/10: "Mua - Avanta" 5/26 dòng chưa có); NCC mặc định của các mặt hàng liên quan.
5. Stock Settings: giữ tắt "Auto Insert Price List Rate If Missing" và "Update Existing Price List Rate".
6. Rà bảng giá bằng báo cáo **Doi Chieu Gia Ban Gia Mua**, rồi bật **Bật kiểm giá bán**.
7. Gỡ: bỏ tích "Bật kiểm giá bán" (dữ liệu đã ghi giữ nguyên).

## 9. Điểm Minh tự diễn giải — cần PO xác nhận

| # | Điểm | Cách đang làm |
|---|---|---|
| Q1 | R05 "Ai được nhập" 3 thông tin? (PO chưa trả lời) | Ai sửa được SO thì nhập được; không giới hạn thêm vai trò |
| Q2 | R05 khi bảng giá KH **không có** giá cho mặt hàng | Không tính là "khác bảng giá" (không có giá cũ để báo) |
| Q3 | R06 "giá mới" | Giá thực bán trên SO (thường bằng giá đề xuất) |
| Q4 | Báo giá đợt không có `valid_till` | Coi là còn hiệu lực |
| Q5 | Hệ số theo mặt hàng có cần số HĐ/hiệu lực? | Có cột như hệ số chung; số HĐ không bắt buộc |
| Q6 | Quotation (báo giá cho khách) | Vẫn tính và cảnh báo như SO (cảnh báo sớm), không chặn |
| Q7 | Dòng "Đang trong thời hạn báo giá" (YC4) | Không cần lý do, không cần 3 thông tin R05 |
| Q8 | Bảng giá "Bảng giá mua" chung (không có Supplier) | Không dùng làm giá HĐ nguyên tắc |
| Q9 | Thông báo trên Portal | Việt hiển thị qua API mục 4.6 |
| Q10 | "Update Items" thêm dòng khác bảng giá | Bị chặn (hộp thoại không có ô R05), phải Amend |

### 9.1 Đề xuất của dev cho Q1, Q2, Q7, Q10 (22/10/2026 — chờ PO chốt, CHƯA code)

**Q1 — Ai nhập 3 thông tin R05.** Nhân viên bán hàng phụ trách đơn (ai sửa được SO) nhập, vì họ là người làm việc với khách và giữ văn bản; không thêm bước duyệt (PO đã bỏ duyệt). Kiểm soát bù: (1) hệ thống tự ghi người nhập và thời điểm trên từng dòng (chỉ đọc), hiện ở báo cáo A08 để kế toán hậu kiểm; (2) sau khi SO đã Submit, ô còn trống vẫn điền được, nhưng giá trị đã điền chỉ Giám đốc sửa; (3) tùy PO: bắt buộc đính kèm file văn bản chấp thuận.

**Q2 — Bảng giá KH chưa có giá cho mặt hàng.** Tính là "khác bảng giá": đòi 3 thông tin R05, email R06 ghi giá cũ "Chưa có trong bảng giá". Lý do: D09 — giá chưa được thỏa thuận trong bảng giá thì phải có văn bản khách chấp thuận; R07 đã giới hạn ở khách có hợp đồng hệ số nên không gây nhiễu cho khách lẻ. Kèm theo: so với **bảng giá mặc định của khách** (Customer → Default Price List) thay vì bảng giá đang chọn trên SO — hiện đổi bảng giá trên SO sang bảng không có mặt hàng là lọt R05.

**Q7 — R05 và quy tắc báo trước 7 ngày.** Giữ miễn R05 nhưng thu hẹp: chỉ miễn khi bán **đúng giá bảng giá hiện hành** trong thời hạn báo trước. Bán giá mới sớm hơn ngày áp dụng → khác bảng giá → cần R05 (khách chấp thuận áp sớm) — hiện đã như vậy. Bán giá khác cả giá cũ lẫn giá mới → lệch bình thường (cần lý do và R05). Hiện đang miễn mọi giá miễn có giá mới chờ báo — lỗ hổng cần đóng.

**Q10 — Update Items thêm dòng khác bảng giá.** Cho Update Items đi qua; dòng đó ở trạng thái chờ chấp thuận; nhân viên điền 3 ô ngay trên SO đã Submit (các ô đã cho sửa sau Submit); **chặn tạo Phiếu giao hàng / Hóa đơn bán** cho dòng còn thiếu; điền đủ thì tự gửi email R06 bổ sung. Không đề xuất giữ cách Amend: không hủy được SO khi đã có Phiếu giao/Hóa đơn, số SO đổi, liên kết Portal bị đứt.

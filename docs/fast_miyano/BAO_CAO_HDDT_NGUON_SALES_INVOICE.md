# BÁO CÁO PHÂN TÍCH: XUẤT HĐĐT TỪ SALES INVOICE THAY CHO DELIVERY NOTE

**Ngày 13/10/2026** — nhánh `feat/vn-hddt-provider` — liên quan: `SPEC_FAST_EINVOICE_ERPNEXT_v2.md`, `RUNBOOK_HDDT_FAST.md`

> Báo cáo này chỉ là phân tích. Chưa có dòng mã nào được sửa trên nhánh.

---

## 1. Tóm tắt

Yêu cầu đúng và nên làm ngay: đổi chứng từ nguồn của HĐĐT từ Delivery Note sang **Sales Invoice đã submit**, một Sales Invoice ứng với một hóa đơn gốc.

- **Lý do cốt lõi.** Doanh thu, thuế GTGT đầu ra, công nợ 131, bảng kê bán ra và tờ khai 01/GTGT đều sinh từ Sales Invoice. Hóa đơn điện tử là chứng từ pháp lý của chính khoản doanh thu đó, nên phải khớp 1–1 với Sales Invoice. Hiện hai bên chỉ nối với nhau bằng một cầu vòng qua phiếu giao, và cầu này sai khi một hóa đơn bán gộp nhiều phiếu giao hoặc một phiếu giao tách nhiều hóa đơn bán.
- **Phạm vi.** Thay đổi nằm ở lớp "chứng từ nguồn": khoảng 15 tệp mã trong `erpnext/einvoice`, 3 dòng `hooks.py`, 1 form script. Phần lõi nói chuyện với Fast (đăng nhập, payload, phát hành, trạng thái CQT, PDF) giữ nguyên.
- **Dữ liệu.** Site `miyano` mới có 8 chứng từ HĐĐT (6 đã có số, 2 nháp) và đúng 1 Sales Invoice. Chuyển đổi lúc này gần như không tốn; để càng lâu càng đắt.
- **Rủi ro chính.** Thời điểm lập hóa đơn. Phiếu giao gắn với lúc giao hàng; hóa đơn bán thì kế toán có thể lập muộn vài ngày. Cần một báo cáo "đã giao, chưa lập hóa đơn bán" để bù lại.
- **Khối lượng.** Khoảng 7 ngày công (ước lượng thô), sau khi chốt 8 câu hỏi ở mục 8.
- **Lỗi cũ.** Mục 10 đối chiếu từng lỗi đã mắc khi làm HĐĐT với cách nó có thể quay lại khi đổi nguồn, kèm chốt chặn và điều kiện hoàn thành.

---

## 2. Hiện trạng: phiếu giao là nguồn duy nhất

Trên nhánh `feat/vn-hddt-provider`, hóa đơn gốc chỉ sinh ra được từ một phiếu giao đã submit. Sales Invoice chỉ là một ô liên kết tùy chọn trên chứng từ HĐĐT, và chưa bản ghi nào điền ô đó (0/8).

Phiếu giao được gắn vào module ở sáu chỗ:

1. **Tạo chứng từ.** Nút "Tạo hóa đơn điện tử" trên form phiếu giao gọi `builder.create_from_delivery_note`. Khách hàng, địa chỉ, người liên hệ, dòng hàng và thuế suất đều sao từ phiếu giao.
2. **Khóa chống trùng.** `fast_key` gửi sang Fast chính là tên phiếu giao (ví dụ `MAT-DN-2026-00008`). Mỗi phiếu giao chỉ được có một chứng từ HĐĐT đang sống.
3. **Schema.** `delivery_note` là trường bắt buộc, chỉ đọc, đồng thời là tiêu đề và ô tìm kiếm của chứng từ. `sales_invoice` không bắt buộc.
4. **Ghi ngược.** Năm custom field trên phiếu giao giữ bản sao: chứng từ HĐĐT, số hóa đơn, trạng thái, mã tra cứu, link PDF. PDF chính thức cũng đính sang phiếu giao.
5. **Hủy.** Hai hook `before_cancel` và `on_cancel` của Delivery Note chặn hủy phiếu giao khi hóa đơn đã có số.
6. **Kiểm tra và báo cáo.** Quy tắc 15 kiểm tra phiếu giao nguồn. Báo cáo Đối soát đếm "chưa xuất hóa đơn" theo phiếu giao.

Phía kế toán đi đường khác. Bảng kê bán ra và tờ khai 01/GTGT dựng từ Sales Invoice, rồi hỏi số hóa đơn qua `lookup.invoice_numbers_for`: trước tìm chứng từ HĐĐT trỏ thẳng vào Sales Invoice, không có thì đi vòng Sales Invoice Item → phiếu giao → chứng từ HĐĐT.

Luồng cũ chạy theo Sales Invoice đã bị gỡ ngày 07/08/2026 (patch `remove_vn_einvoice_si_flow`). Lý do ghi trong patch là luồng đó **tự phát hành khi submit**, trái nguyên tắc A2 "mọi hành động phải có người xác nhận". Đặc tả v2 không ghi lý do nào cho việc chọn phiếu giao làm nguồn. Vì vậy quay lại Sales Invoice không mâu thuẫn với quyết định cũ, miễn là giữ luồng bấm nút có xác nhận.

---

## 3. Yêu cầu mới và căn cứ

Hóa đơn điện tử phải lập từ Sales Invoice vì đó là chứng từ duy nhất ghi doanh thu, thuế GTGT đầu ra và công nợ phải thu. Phiếu giao chỉ ghi xuất kho và giá vốn.

Sáu điểm yếu của việc lấy phiếu giao làm nguồn, đối chiếu với mã hiện tại:

| Điểm yếu | Hệ quả thực tế | Sales Invoice giải quyết |
| --- | --- | --- |
| Hóa đơn và sổ sách không chung nguồn | Tổng tiền HĐĐT tính từ dòng phiếu giao. Không có gì bảo đảm nó bằng số đã ghi 511 / 3331 / 131 nếu kế toán chỉnh giá, chiết khấu hay thuế trên hóa đơn bán | HĐĐT và bút toán cùng đọc một chứng từ; đối chiếu được từng đồng |
| Quan hệ phiếu giao ↔ hóa đơn bán là nhiều–nhiều | `lookup` đi vòng qua phiếu giao: hóa đơn bán gộp 3 phiếu giao chỉ nhận số của phiếu đầu tiên tìm thấy; phiếu giao tách 2 hóa đơn bán thì cả hai dòng bảng kê mang cùng một số | Liên kết trực tiếp, một–một; bỏ đường vòng |
| Bán không qua phiếu giao | Dịch vụ lắp đặt, bảo trì, hiệu chuẩn; hóa đơn bán có `update_stock`; hóa đơn ứng trước. Hiện không lập được HĐĐT. 13/38 mặt hàng đang hoạt động là không tồn kho | Mọi khoản doanh thu đều có Sales Invoice |
| Gộp nhiều lần giao vào một hóa đơn | Câu hỏi mở J3 của đặc tả v2, chưa có lời giải; muốn làm phải đổi `delivery_note` thành bảng con | Có sẵn: Sales Invoice lấy dòng từ nhiều phiếu giao |
| Trả hàng, giảm giá | Phiếu trả hàng chỉ nhập kho lại. Hóa đơn điều chỉnh giảm không gắn với chứng từ ghi giảm doanh thu | Hóa đơn bán trả hàng (credit note) là chứng từ đối ứng tự nhiên |
| Bảo vệ hủy đặt sai chỗ | Hủy phiếu giao bị chặn, nhưng `hooks.py` không có hook HĐĐT nào trên Sales Invoice: hủy được bút toán doanh thu trong khi hóa đơn đã lên Cơ quan Thuế | Chặn hủy đúng chứng từ mang doanh thu |

**Về pháp lý** (ghi theo hiểu biết sẵn có, chưa tra lại văn bản, cần kế toán trưởng xác nhận): Nghị định 123/2020/NĐ-CP, Điều 9 quy định thời điểm lập hóa đơn bán hàng hóa là lúc chuyển giao quyền sở hữu hoặc quyền sử dụng, không phụ thuộc đã thu tiền hay chưa; giao nhiều lần thì mỗi lần giao phải lập hóa đơn. Quy định nói về **thời điểm**, không nói chứng từ nào trong phần mềm làm nguồn. Đổi sang Sales Invoice vì thế hợp lệ, với điều kiện hóa đơn bán được lập đúng ngày giao hàng.

---

## 4. Phân tích khoảng cách

Về dữ liệu thì không có khoảng cách: mọi trường mà `builder` đang đọc từ phiếu giao đều có trên Sales Invoice và Sales Invoice Item (đã đối chiếu với hai tệp JSON của DocType). Khoảng cách nằm ở hành vi.

| Khía cạnh | Hiện tại (phiếu giao) | Khi chuyển sang hóa đơn bán | Việc phải làm |
| --- | --- | --- | --- |
| Khóa chống trùng `fast_key` | Tên phiếu giao | Tên hóa đơn bán, ví dụ `ACC-SINV-2026-00011` (19 ký tự, giới hạn 32) | Đổi nguồn key cho bản ghi mới; key của hóa đơn đã phát hành giữ nguyên |
| Một nguồn, một hóa đơn | 1 phiếu giao = 1 chứng từ HĐĐT đang sống | 1 hóa đơn bán = 1 chứng từ HĐĐT đang sống; hóa đơn bán có thể gồm nhiều phiếu giao | Đổi ba chỗ kiểm tra trùng: `builder`, controller, quy tắc 15 |
| Ngày hóa đơn | Bằng ngày phát hành, không lấy ngày phiếu giao | Vẫn bằng ngày phát hành, nhưng bảng kê lấy `posting_date` của hóa đơn bán | Cảnh báo khi hai ngày khác nhau, nhất là khác kỳ kê khai |
| Tổng tiền | Chứng từ HĐĐT tự tính từ dòng, không có gì để so với sổ | So được với tiền trước thuế, thuế và tổng thanh toán của hóa đơn bán | Thêm quy tắc đối chiếu, mức cảnh báo |
| Trả hàng, ghi nợ | Phiếu trả hàng bị từ chối, hướng sang điều chỉnh giảm | Hóa đơn bán có `is_return` và `is_debit_note` cần quy tắc riêng | Bước đầu từ chối như cũ; gắn credit note vào hóa đơn điều chỉnh là câu hỏi mở |
| Hủy chứng từ nguồn | Chặn hủy phiếu giao khi hóa đơn đã có số | Chặn hủy hóa đơn bán; phiếu giao đã có hóa đơn bán thì lõi tự chặn | Chuyển hai hook sang Sales Invoice |
| Ghi ngược trạng thái | 5 custom field trên phiếu giao | 5 custom field trên hóa đơn bán | Dựng field mới, gỡ field cũ |
| Thời điểm lập | Nút nằm ngay trên phiếu giao, giao xong là thấy | Phụ thuộc kế toán lập hóa đơn bán kịp ngày giao | Báo cáo "đã giao, chưa lập hóa đơn bán" |
| Email gửi khách | Tiêu đề và nội dung nêu số phiếu giao | Nêu số hóa đơn bán | Sửa hai mẫu email |

---

## 5. Phương án đề xuất

Sales Invoice đã submit là nguồn duy nhất của hóa đơn gốc; phiếu giao lùi về vai trò tham chiếu.

```
HIỆN TẠI

  [Phiếu giao hàng] ──── nút "Tạo hóa đơn điện tử" ────► [Chứng từ HĐĐT] ──► [Fast và CQT]
         │                                                      ▲
         │ lập hóa đơn bán                                      ┆ tra số vòng qua phiếu giao
         ▼                                                      ┆
  [Hóa đơn bán] ─────────────────────────────────────► [Sổ cái, bảng kê]
                                                         511 · 3331 · 131

ĐỀ XUẤT

  [Phiếu giao hàng] ──► [HÓA ĐƠN BÁN] ── nút "Tạo hóa đơn điện tử" ──► [Chứng từ HĐĐT] ──► [Fast và CQT]
     lập hóa đơn bán    nguồn duy nhất                                        ┆
                              │ ghi sổ                                        ┆ số hóa đơn nối thẳng,
                              ▼                                               ┆ một–một
                       [Sổ cái, bảng kê] ◄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┘
                        511 · 3331 · 131
```

Hiện tại hóa đơn điện tử và sổ sách đi hai nhánh riêng từ phiếu giao, nối với nhau bằng một phép tra vòng. Sau khi đổi, cả hai cùng đi qua hóa đơn bán, và số hóa đơn nối thẳng về chứng từ ghi doanh thu.

Bảy quy tắc thiết kế:

1. **Điều kiện tạo.** Hóa đơn bán đã submit, không phải trả hàng hay ghi nợ, chưa có chứng từ HĐĐT đang sống. Nút "Tạo hóa đơn điện tử" chuyển sang form Sales Invoice và giữ hộp xác nhận như cũ.
2. **Trường nguồn.** `sales_invoice` thành trường nguồn: bắt buộc với bản ghi mới, chỉ đọc, có index, làm tiêu đề. `delivery_note` hết bắt buộc, giữ lại cho 8 bản ghi cũ và để tham chiếu.
3. **Sao dữ liệu.** Giữ nguyên công thức dòng hàng đang chạy (đơn giá gốc, chiết khấu dồn về số tiền, thuế suất theo Item Tax Template). Chỉ đổi chứng từ được đọc.
4. **Ghi ngược.** Số hóa đơn, trạng thái, mã tra cứu, link PDF và tệp PDF chính thức ghi lên hóa đơn bán, dạng Data chứ không phải Link (tránh hai Link trỏ vòng, xem mục 10.1). Phiếu giao chỉ hiển thị trạng thái suy ra qua hóa đơn bán, không lưu bản sao riêng.
5. **Hủy.** `before_cancel` của Sales Invoice chặn khi hóa đơn đã có số; `on_cancel` nhả các bản nháp chưa phát hành.
6. **Tra số cho bảng kê.** Nối thẳng qua `sales_invoice`. Đường vòng qua phiếu giao chỉ còn phục vụ bản ghi cũ.
7. **Không đổi.** Vòng đời 01–12, xác nhận ba cấp, hóa đơn điều chỉnh và thay thế lập từ hóa đơn gốc, toàn bộ lớp giao tiếp với Fast.

Các phương án khác đã cân nhắc:

| Phương án | Nội dung | Đánh giá |
| --- | --- | --- |
| A (đề xuất) | Chỉ lập từ hóa đơn bán đã submit | Một đường phát hành duy nhất, khớp sổ |
| B | Cho lập từ cả phiếu giao lẫn hóa đơn bán | Loại. Hai đường phát hành cùng sống là nguy cơ một lần bán ra hai số hóa đơn, đúng lý do đã dùng để gỡ luồng cũ |
| C | Lập từ hóa đơn bán nháp, phát hành xong mới submit | Ngày và số khớp tuyệt đối với sổ, nhưng đảo quy trình ghi sổ và khó xử lý khi phát hành lỗi. Để giai đoạn sau nếu cần |
| D | Giữ phiếu giao, chỉ bắt buộc điền `sales_invoice` trước khi phát hành | Sửa ít nhất, nhưng không giải quyết gộp nhiều phiếu giao, bán dịch vụ, và số liệu vẫn sao từ phiếu giao |

---

## 6. Phạm vi thay đổi

Thay đổi gói trong lớp "chứng từ nguồn". Lớp giao tiếp với Fast không đụng tới: `fast_client`, `gateway`, `payload`, `totals`, `tax_status`, `catalogue`, `folders`.

| Tệp | Thay đổi |
| --- | --- |
| `einvoice/builder.py` (414 dòng) | Viết lại quanh Sales Invoice: tạo, đồng bộ lại, sinh key, ghi ngược, hai hook hủy. Phần ánh xạ dòng hàng, địa chỉ, liên hệ dùng lại gần nguyên |
| `einvoice/form_state.py` | `get_delivery_note_state` thành trạng thái nhìn từ hóa đơn bán; đổi nhãn nút "Đồng bộ lại" |
| `einvoice/validation.py` | Quy tắc 15 kiểm tra hóa đơn bán nguồn; thêm quy tắc đối chiếu tổng tiền và ngày |
| `fast_einvoice_document.json` và `.py` | `sales_invoice` thành trường nguồn, tiêu đề, ô tìm kiếm; `delivery_note` hết bắt buộc; kiểm tra trùng theo hóa đơn bán; nhả dấu khi xóa bản nháp |
| `einvoice/issue.py`, `cancel.py`, `actions.py`, `reconcile.py` | Bốn chỗ ghi ngược số hóa đơn, trạng thái, PDF: đổi đích sang hóa đơn bán |
| `einvoice/setup.py` | Dựng custom field trên Sales Invoice, gỡ 7 field trên Delivery Note; sửa hai mẫu email đang nêu số phiếu giao |
| `einvoice/lookup.py` | Đường nối thẳng thành chính; đường vòng chỉ giữ cho bản ghi cũ |
| `einvoice/lineage.py` | Đã sao cả hai trường sang hóa đơn điều chỉnh và thay thế; chỉ rà lại |
| Báo cáo `doi_soat_hoa_don_dien_tu` | "Chưa xuất hóa đơn" đếm theo hóa đơn bán; thêm loại "đã giao, chưa lập hóa đơn bán"; thêm cột hóa đơn bán |
| `hooks.py` | `doctype_js` và hai `doc_events` chuyển từ Delivery Note sang Sales Invoice (3 dòng) |
| `public/js/einvoice/delivery_note.js` | Thay bằng `sales_invoice.js`; phiếu giao chỉ còn phần xem |
| `regional/report/to_khai_thue_gtgt_01` | Chỉ sửa chú thích; hành vi đúng sẵn nhờ `lookup` |
| `patches.txt` và một patch mới | Chuyển custom field, nối bản ghi cũ (mục 7) |
| Kiểm thử | 20 tệp test có 212 dòng nhắc phiếu giao, trong khoảng 580 test của module. Nặng nhất: `test_fast_builder` (41), `test_fast_form_state` (24), test báo cáo đối soát (22), `test_fast_validation` (19). Fixture cần thêm `make_sales_invoice` |
| Tài liệu | `SPEC_FAST_EINVOICE_ERPNEXT_v2.md` (19 chỗ nhắc phiếu giao), `RUNBOOK_HDDT_FAST.md` (8 chỗ) |

---

## 7. Dữ liệu hiện có và chuyển đổi

Dữ liệu phải chuyển rất ít, và trông là dữ liệu thử: site `miyano` đang trỏ vào cổng `:9000` của Fast (môi trường TEST theo runbook), khách hàng trên hầu hết bản ghi là khách demo.

| Hạng mục | Số lượng | Ghi chú |
| --- | --- | --- |
| Chứng từ HĐĐT | 8 | 6 mang số hóa đơn (số 2 đến 6, ký hiệu C26TAA), 2 nháp |
| Chứng từ HĐĐT đã điền `sales_invoice` | 0 | |
| Phiếu giao đã submit | 8 | 7 phiếu chưa có hóa đơn bán |
| Sales Invoice đã submit | 1 | `ACC-SINV-2026-00011`, lập từ `MAT-DN-2026-00010` |
| Sales Order đã submit | 0 | |

Cách xử lý đề xuất, gói trong một patch:

1. **Nối được tự động: 1 bản ghi.** `FEI-2026-00009` (nháp) thuộc phiếu giao `MAT-DN-2026-00010`, phiếu này có đúng một hóa đơn bán. Patch điền `sales_invoice` cho nó.
2. **Sáu bản ghi đã có số: giữ nguyên.** Không đổi `fast_key`, vì key đã nằm trên hệ thống Fast. Chúng thành bản ghi "nguồn phiếu giao" kiểu cũ; yêu cầu bắt buộc có hóa đơn bán chỉ áp cho bản ghi tạo mới.
3. **`FEI-2026-00008` (nháp, phiếu giao chưa có hóa đơn bán):** xóa nháp và lập lại từ hóa đơn bán khi có.
4. **Custom field.** Dựng field trên Sales Invoice. Bảy field trên Delivery Note: ẩn đi, không xóa, vì 6 bản ghi cũ vẫn ghi vào đó.
5. **Field mồ côi của luồng cũ.** Trong DB còn 6 field `vn_einvoice_*` trên Sales Invoice và 4 trên Company, cùng bảng `Vietnam E Invoice Log`, dù patch gỡ luồng cũ đã chạy ngày 07/08/2026 và không còn mã nào đọc chúng. Cần gỡ trong cùng đợt, nếu không form Sales Invoice sẽ có hai mục "Hóa đơn điện tử".

Hai điểm lệch có sẵn trong dữ liệu, nên biết trước khi viết patch:

- `FEI-2026-00006` và `FEI-2026-00007` cùng mang số hóa đơn 6 và cùng key. Bản 00007 là bản chép mà commit gần nhất đã chặn từ gốc, nhưng bản ghi vẫn còn.
- Bản sao trạng thái trên phiếu giao đã trôi: `MAT-DN-2026-00001` ghi "02 - Đã xem nháp" trong khi chứng từ HĐĐT của nó ở "07 - Đã gửi khách". Đây là lý do quy tắc 4 đề xuất không lưu bản sao thứ hai trên phiếu giao.

---

## 8. Rủi ro và câu hỏi mở

Rủi ro lớn nhất không nằm ở mã mà ở quy trình: hóa đơn bán lập muộn thì hóa đơn điện tử cũng muộn so với ngày giao hàng.

| Rủi ro | Mức | Giảm thiểu |
| --- | --- | --- |
| Lập hóa đơn muộn so với ngày giao | Cao | Báo cáo "đã giao, chưa lập hóa đơn bán"; quy định kế toán lập hóa đơn bán trong ngày giao |
| Ngày hóa đơn bán và ngày hóa đơn điện tử rơi vào hai kỳ kê khai | Trung bình | Cảnh báo trước khi phát hành; Fast cũng từ chối ngày quá xa (lỗi 818) hoặc lùi trước hóa đơn gần nhất (lỗi 819) |
| Hai đường phát hành cùng tồn tại trong lúc chuyển | Trung bình | Gỡ nút trên phiếu giao và bật nút trên hóa đơn bán trong cùng một lần triển khai |
| Hóa đơn bán bị hủy hoặc sửa lại khi chứng từ HĐĐT đang nháp | Trung bình | Hook `on_cancel` nhả bản nháp; nút đồng bộ lại từ hóa đơn bán |
| Hồi quy trong khoảng 580 test | Thấp | Đổi fixture trước, rồi mới đổi mã |
| Thủ kho mất nút quen trên phiếu giao | Thấp | Phiếu giao vẫn hiện trạng thái và link tới hóa đơn |

Tám câu cần chốt trước khi viết mã:

- [ ] Chỉ lập từ hóa đơn bán **đã submit** (phương án A)? Khuyến nghị: có.
- [ ] Gỡ hẳn nút trên phiếu giao ngay, hay chạy song song một thời gian? Khuyến nghị: gỡ hẳn.
- [ ] Hóa đơn bán trả hàng: tiếp tục lập điều chỉnh giảm từ hóa đơn gốc rồi gắn credit note vào, hay tạo thẳng từ credit note? Khuyến nghị: bước đầu giữ cách cũ.
- [ ] Lệch ngày giữa hóa đơn bán và hóa đơn điện tử: cảnh báo hay chặn? Khuyến nghị: cảnh báo, và chỉ khi hai ngày rơi vào hai kỳ kê khai khác nhau, đúng nguyên tắc "chỉ chặn cái Fast thật sự từ chối" đang áp dụng.
- [ ] Lệch tổng tiền giữa chứng từ HĐĐT và hóa đơn bán (khi kế toán sửa dòng trên chứng từ HĐĐT): cảnh báo hay chặn? Khuyến nghị (đã đổi sau khi rà lịch sử lỗi, mục 10.1 nhóm C): cảnh báo có dung sai làm tròn. Nếu vẫn muốn chặn thì phải ghi lý do vào `ERP_BUSINESS_RULES` và nhường cửa thoát `totals_manual_override` đang có.
- [ ] Tám bản ghi hiện có đúng là dữ liệu thử? Nếu đúng: giữ làm bản ghi cũ, hay dọn sạch trước khi chạy thật?
- [ ] Gỡ 10 field `vn_einvoice_*` mồ côi và bảng `Vietnam E Invoice Log` trong đợt này?
- [ ] (Mới, từ mục 10.2) Hóa đơn nào chặn hủy hóa đơn bán: khuyến nghị chặn trạng thái 06–11, không chặn "12 - Đã hủy nội bộ".

---

## 9. Các bước triển khai

Khoảng 7 ngày công, chia sáu bước. Con số là ước lượng thô từ số tệp và số test phải sửa, chưa tính thời gian chờ tài khoản TEST của Fast.

| Bước | Nội dung | Ngày công |
| --- | --- | --- |
| 1 | Chốt tám câu hỏi mở; nâng đặc tả lên v3 với chứng từ nguồn là Sales Invoice | 0,5 |
| 2 | Schema chứng từ HĐĐT, custom field trên Sales Invoice, patch chuyển đổi | 1 |
| 3 | `builder`, `form_state`, nút trên form Sales Invoice, hai hook hủy | 1,5 |
| 4 | Ghi ngược, quy tắc 15 và hai quy tắc đối chiếu, `lookup`, báo cáo đối soát | 1,5 |
| 5 | Fixture `make_sales_invoice` và 20 tệp test | 1,5 |
| 6 | Chạy lại các kịch bản trên môi trường TEST của Fast; cập nhật runbook | 1 |

---

## 10. Rủi ro khi chuyển đổi và các lỗi cũ không được lặp lại

Module HĐĐT có 53 commit, trong đó 16 commit là sửa lỗi. Gần như lỗi nào cũng có một cửa để quay lại khi đổi nguồn sang Sales Invoice, vì việc đổi nguồn đụng đúng những chỗ từng sai: ngày, số tiền, khóa chống trùng, hủy chứng từ và form.

Rủi ro nặng nhất là **một lần bán ra hai số hóa đơn** trong giai đoạn chuyển (mục 10.2, dòng đầu). Các rủi ro còn lại đều có chốt chặn bằng test.

### 10.1. Lỗi đã mắc và cách chúng quay lại

#### Nhóm A — ngày và số tiền

| Lỗi đã mắc | Cách nó quay lại khi sang Sales Invoice | Chốt chặn |
| --- | --- | --- |
| Ngày hóa đơn lấy theo ngày chứng từ nguồn. Phát hành trễ một hôm là ngày hóa đơn lệch ngày ký, truy vấn 8200 trả rỗng, hóa đơn số 4 kẹt "Chờ CQT" và job nền gọi Fast vài trăm lần (`338a547`, `a6b7937`, `1157345`) | Sales Invoice có `posting_date` là ngày ghi sổ. Rất dễ "tiện tay" lấy nó làm ngày hóa đơn để khớp sổ | Ngày hóa đơn vẫn luôn bằng ngày phát hành. Test: hóa đơn bán ngày hôm qua, chứng từ HĐĐT vẫn ra ngày hôm nay. `posting_date` chỉ dùng để cảnh báo |
| Bê `net_total` / `grand_total` của nguồn sang thay vì tự tính; bốn chỗ cùng tính tiền rồi lệch nhau (`7465fb1`, `be43000`) | Lý lẽ "Sales Invoice là sổ, cứ lấy tổng của nó" nghe rất hợp lý | Chỉ `totals.py` được tính tiền. Tổng của hóa đơn bán chỉ dùng để **đối chiếu**, không ghi đè |
| Làm tròn hai lần, mỗi lần đẩy sai số vào số phải thu (`18c2673`) | Hóa đơn bán có cách làm tròn riêng (`rounded_total`, thuế tính trên tổng). Quy tắc đối chiếu mới sẽ báo lệch vài đồng ở hóa đơn hoàn toàn đúng | Đối chiếu có dung sai làm tròn. Test với hóa đơn nhiều dòng, 5% + 8% |
| Thuế 8% suýt bị nhét vào ô 10%; bốn ô nhóm thuế không có ô 8% (kiểm chứng 08/09/2026) | Viết lại `builder` mà không mang theo ba test 8% hiện đang dựng từ phiếu giao (`e764761`) | Chuyển nguyên ba test đó sang fixture hóa đơn bán trước khi sửa mã |
| Địa chỉ: phải là địa chỉ xuất hóa đơn chứ không phải nơi giao; HTML `<br>` gây lỗi 825, ký tự `<` `>` gây lỗi 63505 | Hóa đơn bán có cả `customer_address`, `shipping_address` và `address_display` dạng HTML | Dùng lại nguyên `_billing_address` và `_one_line`, không viết mới |

#### Nhóm B — trùng hóa đơn và danh tính chứng từ

| Lỗi đã mắc | Cách nó quay lại khi sang Sales Invoice | Chốt chặn |
| --- | --- | --- |
| Hóa đơn "ma" `FEI-2026-00007`: bản chép bằng nút Duplicate, mang sẵn số hóa đơn 6 (`aae6c65`) | Chốt chống trùng hiện viết là `if self.delivery_note and …`. Bản ghi mới không có phiếu giao nên chốt này **tự bỏ qua mà không báo gì** | Viết lại chốt theo `sales_invoice`. Test: bản ghi thứ hai cho cùng một hóa đơn bán phải bị từ chối |
| Dùng lại Key sau khi hủy nội bộ làm truy vấn 370 vướng hóa đơn cũ; Key con trùng Key gốc là lỗi 809 (`aae6c65`) | Sinh Key mới từ tên hóa đơn bán mà bỏ quên `_unused_key` (hậu tố `-L2`, `-DC1`) | Giữ `_unused_key` trong luồng mới. Test lập lại hóa đơn sau khi hủy nội bộ |
| Trường danh tính sửa tay được: đổi chứng từ nguồn là `fast_key` lệch hẳn với nguồn (`be92ff1`) | `sales_invoice` hiện là ô kế toán tự điền | Thành chỉ đọc. Gắn hóa đơn bán vào bản ghi cũ phải đi qua một hành động có kiểm tra |
| Hai nguồn sự thật cho một câu hỏi: ô "Chế độ TEST" và `api_url` (`720d656`) | Bản ghi có cả `delivery_note` lẫn `sales_invoice`: không biết cái nào là nguồn | Thêm một trường nguồn tường minh, đặt một lần lúc tạo, không sửa được |

#### Nhóm C — khóa, hủy và giao diện

| Lỗi đã mắc | Cách nó quay lại khi sang Sales Invoice | Chốt chặn |
| --- | --- | --- |
| Hai Link trỏ vòng vào nhau: không xóa được nháp, không hủy được phiếu giao, lỗi `LinkExistsError` không nói vì sao (`6fae7d7`) | Dựng lại đúng vòng đó giữa hóa đơn bán và chứng từ HĐĐT | Trên hóa đơn bán chỉ lưu số, trạng thái, link PDF dạng Data; liên kết đi qua mục Connections. Hook `on_cancel` chỉ **nối thêm** vào `ignore_linked_doctypes` mà lõi vừa đặt |
| Chứng từ kẹt ở "05 - Đang phát hành", không nút nào dùng được (`74d3826`); form mất hết nút vì `refresh` không `await` (`1ddb08c`) | Viết `sales_invoice.js` mới từ đầu | Chép khuôn của `delivery_note.js`: `async refresh` có `await`, server quyết định trạng thái, luôn hiện lý do khi không có nút |
| Sửa form script nhưng trình duyệt vẫn chạy bản cũ, vì meta nằm trong localStorage (phát hiện 09/09/2026) | Người dùng vẫn thấy nút cũ trên phiếu giao và bấm vào: đường phát hành thứ hai còn sống | Patch đổi `modified` của Sales Invoice và Delivery Note. Hàm `create_from_delivery_note` giữ lại nhưng trả lời từ chối rõ ràng. Hướng dẫn người dùng bấm Reload |
| Bản sao trạng thái trôi: `MAT-DN-2026-00001` ghi "02" trong khi chứng từ ở "07"; số hóa đơn lưu kèm khoảng trắng | Bản sao trên hóa đơn bán trôi y như vậy, và lần này nó nằm cạnh số liệu kê khai | Mọi báo cáo đọc từ chứng từ HĐĐT. Bản sao trên hóa đơn bán chỉ để hiển thị |
| Chặn thừa làm kẹt hóa đơn hợp lệ; cảnh báo hiện ở mọi hóa đơn nên không ai đọc nữa (`0a8587e`, `18c2673`) | Hai quy tắc đối chiếu mới (ngày, tổng tiền) chính là ứng viên chặn thừa. Test `TestNothingBlocksMoreThanFastDoes` sẽ đỏ nếu chặn mà không nêu căn cứ | Mặc định là cảnh báo. Lệch ngày chỉ báo khi khác **kỳ kê khai**, không báo mỗi lần lệch một ngày |

#### Nhóm D — cách làm việc

| Lỗi đã mắc | Cách nó quay lại khi sang Sales Invoice | Chốt chặn |
| --- | --- | --- |
| Suy ra thay vì đọc tài liệu: bộ đọc 8200 sai ba chỗ (`c0d8044`), bắt tay token sai (`2e2aac5`) | Đoán hành vi của Sales Invoice: thứ tự hook hủy, field nào bị chép khi tạo từ phiếu giao, bảng thuế nhiều dòng | Mỗi giả định về lõi phải có một test chạy thật trên Sales Invoice |
| Bốn commit ngày 16/09 ghi "chưa chạy được trên máy này". Kết quả là test đỏ nằm sẵn trong nhánh | Bắt đầu sửa trên một nền đã đỏ thì không phân biệt được lỗi cũ với lỗi mới | Chốt mốc trước khi sửa (mục 10.3) |
| Kiểm chứng bằng `bench console` để lại dữ liệu rác trên site; tệp PDF giả làm hỏng hai bộ test không liên quan (10/09/2026) | Thử luồng mới phải submit hóa đơn bán, tức ghi sổ cái. Bản ghi đã ghi sổ thì không xóa sạch được | Chỉ kiểm chứng bằng `bench run-tests`. Không gọi phát hành hay tạo hóa đơn bán từ console |
| Dọn dẹp không tới nơi: 10 field `vn_einvoice_*` còn nguyên dù patch gỡ đã chạy; DocType đã xóa nhưng bảng còn | Patch chuyển đổi để lại field cũ trên phiếu giao, form hiện hai nơi cùng nói về hóa đơn | Patch tự kiểm tra kết quả ở cuối. Field trên phiếu giao: ẩn đi, không xóa, vì 6 bản ghi cũ vẫn ghi vào đó |
| Web chạy bằng gunicorn `--preload`: mã Python mới không tới worker cho đến khi restart; hook lại nằm trong Redis dùng chung | Sau `migrate`, worker cũ đọc hook mới trỏ tới hàm chưa có: thao tác hủy hóa đơn bán **có thể lỗi hàng loạt** cho tới khi restart | Triển khai ngoài giờ: `migrate` rồi restart supervisor ngay |
| Email đi tới khách thật: nút gửi bản nháp gửi thẳng cho khách | Tiêu đề mẫu nháp là `{{ doc.delivery_note }}`. Bản ghi mới không có phiếu giao nên tiêu đề ra trống | Sửa mẫu trước khi bật luồng mới. `setup` chỉ ghi đè mẫu còn nguyên bản gốc, nên phải kiểm tra tay mẫu trên site |

### 10.2. Rủi ro mới, riêng của Sales Invoice

| Rủi ro | Vì sao xảy ra | Chốt chặn |
| --- | --- | --- |
| **Một lần bán, hai số hóa đơn** | Key đổi từ tên phiếu giao sang tên hóa đơn bán, nên lớp chống trùng phía Fast (truy vấn 370, lỗi 809/835) không còn nhận ra. Bốn phiếu giao đã có hóa đơn có số theo luồng cũ, và cả bốn chưa có hóa đơn bán. Lập hóa đơn bán cho chúng rồi bấm nút là ra hóa đơn thứ hai | Khi tạo từ hóa đơn bán, dò mọi phiếu giao trong dòng hàng. Phiếu nào đã có chứng từ HĐĐT đang sống thì từ chối, và hướng sang gắn hóa đơn bán vào chứng từ cũ |
| Hóa đơn bán không được phép xuất HĐĐT | Số dư đầu kỳ (`is_opening`) đã có hóa đơn ở hệ thống cũ. Ngoài ra còn trả hàng, ghi nợ, hóa đơn gộp POS | Từ chối ngay ở điều kiện tạo, kèm lý do |
| Hủy rồi sửa lại hóa đơn bán | Bản sửa lại mang tên mới (`…-1`), tức Key mới. Hook chặn hủy hiện dùng tập `ISSUED_STATUSES`, tập này gồm cả "12 - Đã hủy nội bộ": hóa đơn bị CQT từ chối sẽ khóa hóa đơn bán vĩnh viễn | Chốt lại tập trạng thái chặn hủy: chặn 06–11, không chặn 12 |
| Bảng thuế nhiều dòng | Hàm lấy thuế suất chung chọn dòng thuế **đầu tiên** có tỷ lệ. Hóa đơn bán hay có thêm dòng phí hoặc thuế khác | Chỉ lấy dòng thuộc tài khoản thuế GTGT đầu ra (3331) |
| Số hóa đơn bị chép sang chứng từ khác | Tạo hóa đơn bán từ phiếu giao, tạo hóa đơn trả hàng, sửa lại: lõi chép mọi field trùng tên trừ field `no_copy` | Mọi custom field mới trên hóa đơn bán đặt `no_copy`. Test cho cả ba đường chép |
| Thiếu lưới test của lõi | Bộ test `sales_invoice` của lõi không chạy được trên site này (thiếu app `payments`, theo ghi nhận tháng 9/2026), nên không bắt được lỗi do hook mới gây ra | Viết test riêng cho hai hook hủy. Dựng custom field bằng `migrate`, không dựng trong test |
| Bảng kê che mất lỗ hổng | Hóa đơn bán chưa có HĐĐT thì bảng kê lấy luôn tên chứng từ ERP làm số hóa đơn | Sau khi đổi nguồn, dòng như vậy phải hiện là thiếu hóa đơn |
| Quyền tạo chứng từ | `create_from_delivery_note` không kiểm tra quyền đọc chứng từ nguồn và ghi bỏ qua phân quyền. Phát hành và hủy thì đã gác theo vai trò | Bản mới kiểm tra quyền đọc hóa đơn bán trước khi tạo |

### 10.3. Mốc trước khi sửa và điều kiện hoàn thành

Mốc ngày 13/10/2026, chạy trên nhánh hiện tại, chưa sửa gì:

| Bộ test | Kết quả |
| --- | --- |
| `test_einvoice_module` | 1 lỗi / 8: `test_no_vn_einvoice_custom_fields_remain` (field cũ còn trên site) |
| `test_fast_folders` | 1 lỗi / 12: `test_the_uploaded_xml_is_filed_with_the_invoice` (tệp XML vào `Home/Attachments` thay vì thư mục hóa đơn) |
| `test_fast_lookup` | 7 / 7 đạt |
| `test_fast_pdf` | 32 / 32 đạt |

Các bộ còn lại của module chưa chạy trong lần này. Cần chạy đủ và ghi lại trước khi viết dòng mã đầu tiên.

Điều kiện hoàn thành:

- [ ] Hai test đang đỏ được sửa hoặc ghi nhận rõ là lỗi có sẵn
- [ ] Hóa đơn bán ngày hôm qua, chứng từ HĐĐT ra ngày hôm nay
- [ ] Hóa đơn bán 5% + 8% nhiều dòng: tổng khớp trong dung sai, bốn ô nhóm thuế đúng
- [ ] Tạo từ hóa đơn bán có phiếu giao đã xuất hóa đơn theo luồng cũ: bị từ chối
- [ ] Hóa đơn bán số dư đầu kỳ, trả hàng, ghi nợ: bị từ chối kèm lý do
- [ ] Hủy hóa đơn bán: chặn khi hóa đơn còn hiệu lực, nhả khi mới là nháp
- [ ] Hóa đơn bán tạo từ phiếu giao, trả hàng, sửa lại: không mang theo số hóa đơn
- [ ] `TestNothingBlocksMoreThanFastDoes` vẫn xanh; câu chữ quy tắc 15 trong `ERP_BUSINESS_RULES` đã đổi
- [ ] Hàm cũ `create_from_delivery_note` trả lời từ chối rõ ràng
- [ ] Patch đổi `modified` của Sales Invoice và Delivery Note, và tự kiểm tra kết quả
- [ ] Mẫu email trên site đã sửa và xem thử với bản ghi mới
- [ ] Triển khai: `migrate` rồi restart supervisor ngay, ngoài giờ làm việc

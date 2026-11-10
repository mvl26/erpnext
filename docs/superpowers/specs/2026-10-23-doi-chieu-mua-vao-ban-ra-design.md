# Báo cáo Đối chiếu mua vào – bán ra theo khách hàng — thiết kế

Ngày: 23/10/2026 · Người yêu cầu: anh (kế toán Miyano) · Mẫu: `docs/Công nợ T10_Himedic_20.10.xlsx`

## 1. Ý định

Hằng tháng kế toán lập tay một bảng Excel đặt **từng dòng hàng bán cho một khách** (ví dụ Himedic)
cạnh **chính dòng hàng đó mua vào từ NCC**, để đối soát với khách và NCC. Mẫu tháng 10/2026 có
53 dòng, 11 NCC. Giá bán thường cao hơn giá mua khoảng 1%. Mục tiêu là ERP tự dựng bảng này:
xem trên web, lọc được, và xuất Excel có bố cục như mẫu.

Báo cáo này **khác** với Biên bản đối chiếu công nợ (module `Debt Reconciliation`, SRS_10). Module đó
đối chiếu số dư TK 131/331 từ GL. Báo cáo này đi theo dòng hàng trên hoá đơn và không đọc GL.

## 2. Mục tiêu / không làm / phản mục tiêu

**Mục tiêu**
- Có một báo cáo trong module **Accounts** (Kế toán), xem trên desk.
- Có ba bộ lọc: **Khách hàng** (bắt buộc), **Kỳ** (theo tháng, hoặc từ ngày đến ngày), **NCC** (không bắt buộc).
  - Thêm bộ lọc **Công ty**, mặc định là công ty mặc định. Lý do: erptest có 2 công ty dùng VND.
- Có nút **Xuất Excel theo mẫu**, xuất đúng bố cục của file mẫu (mục 6).

**Không làm**
- Không sinh bút toán, không sửa chứng từ, không gửi cho khách hay NCC.
- Không đối chiếu số dư công nợ và thanh toán. Phần đó thuộc `Debt Reconciliation`.
- Không thêm chiều ngược lại, tức hàng đã mua về cho đơn của khách nhưng chưa bán, trong bản này.
- Không thêm ô tên viết tắt cho khách hàng hay NCC, không thêm ô "tên hàng theo HĐ NCC".

**Phản mục tiêu**, tức những điều làm báo cáo thành hỏng dù chạy được:
- Một dòng bán biến mất chỉ vì chưa ghép được bên mua. Anh đã chốt: **vẫn hiện dòng đó, để trống bên NCC**.
- Ghép bừa theo mã hàng khi không có liên kết đơn hàng. Ghép sai thì tệ hơn để trống.
- Tổng bên bán lệch với tổng các hoá đơn bán của khách trong kỳ.
- Lộ biên lãi cho người không phải kế toán (mục 7).

## 3. Nguồn số liệu và cách ghép (anh đã chốt)

- Chỉ lấy chứng từ **đã submit** (`docstatus = 1`).
- **Bên khách hàng** lấy từ `Sales Invoice` / `Sales Invoice Item` của khách và công ty đã lọc. Ngày hoá đơn (`posting_date`) nằm trong kỳ.
  - Số HĐ đầu ra lấy qua `erpnext/einvoice/lookup.py::invoice_numbers_for`. Đây là nguồn chuẩn; `fast_invoice_no` chỉ là bản sao để hiển thị và có thể lệch, nên **không đọc** ô đó.
    - HĐĐT gốc đã bị thay thế thì hiện số của hoá đơn thay thế. Hàm lookup đã xử lý việc này.
    - SI chưa có HĐĐT thì hiện tên chứng từ.
  - KH lấy theo `customer_name`. Anh chốt dùng tên trong ERP.
  - Tên hàng lấy theo `item_name`, hoặc `description` của dòng.
- **Bên NCC** lấy từ `Purchase Invoice` / `Purchase Invoice Item`. Đường ghép đi theo đơn hàng:
  `Sales Invoice Item.so_detail` → `Purchase Order Item.sales_order_item` → `Purchase Invoice Item.po_detail`.
  - Số HĐ đầu vào lấy theo `Purchase Invoice.bill_no`, ngày lấy theo `bill_date`. Nếu trống thì dùng tên chứng từ và `posting_date`.
  - NCC lấy theo `supplier_name`. Tên hàng lấy theo `item_name` / `description` trên PI. Anh chốt: chữ trong ERP là được, không cần đúng nguyên văn chữ NCC in.
  - Hoá đơn mua **không bị lọc theo kỳ**. Trong mẫu, hoá đơn VietMed ngày 30/09 vẫn có trong bảng tháng 10.
- Dòng bán **không ghép được** hoá đơn mua thì vẫn hiện, bên NCC để trống.
- Bộ lọc **NCC** chỉ giữ những dòng mà bên mua thuộc NCC đó. Khi có lọc NCC, dòng không ghép được sẽ bị ẩn.

## 4. Tiền thuế từng dòng (anh chốt: khớp tổng hoá đơn)

**Không dùng** `item_wise_tax_detail` để lấy thuế từng dòng. Bảng đó gộp theo mã hàng (`controllers/taxes_and_totals.py`), nên hai dòng cùng mã trên một hoá đơn sẽ không tách ra được.

Cách tính:
1. Mỗi dòng: tiền thuế = làm tròn đến đồng của (`net_amount` × thuế suất của dòng). Thuế suất lấy từ `item_tax_template` / `item_tax_rate` của dòng, nếu không có thì lấy từ bảng thuế của hoá đơn.
2. Trong mỗi hoá đơn, cộng tiền thuế các dòng rồi so với tổng thuế VAT trên hoá đơn. Phần chênh **dồn vào dòng cuối của hoá đơn đó**, để tổng cột Tiền thuế bằng đúng hoá đơn.
3. Làm giống hệt cho SI và PI.

Khi một dòng bị tách (mục 5), thành tiền và thuế chia theo tỉ lệ SL. Phần lẻ dồn vào mảnh cuối.

Test "tổng khớp" kiểm hai điều:
- Tổng Thành tiền bên bán bằng Σ `net_total` của các SI trong kỳ.
- Tổng Tiền thuế bên bán bằng Σ thuế VAT của các SI đó.

## 5. Quy tắc tách dòng

- Một dòng bán ghép với **nhiều** dòng hoá đơn mua thì tách thành nhiều dòng.
  - Mỗi mảnh lấy theo SL của từng dòng mua, cắt cho vừa SL bán.
  - SL bán còn lại chưa ghép được, ví dụ đơn bán xuất qua nhiều tháng, thành một dòng trống bên NCC.
- Nhiều dòng bán cùng ghép với **một** dòng mua thì mỗi dòng bán hiện riêng. Bên mua chỉ lấy phần SL tương ứng, không lặp lại cả dòng mua.
- Thứ tự sắp xếp: theo ngày HĐ bán, rồi số HĐ bán, rồi thứ tự dòng (`idx`).

## 6. Hiển thị và xuất Excel

Các cột theo đúng thứ tự trong mẫu:
- STT.
- Khối **KHÁCH HÀNG**: KH, Số HĐ đầu ra, Ngày HĐ, Tên hàng hóa, ĐVT, SL, Đơn giá (chưa VAT), Thành tiền (chưa VAT), Thuế suất, Tiền thuế, Tổng sau thuế.
- Khối **NHÀ CUNG CẤP**: NCC, Số HĐ đầu vào, Ngày HĐ, Tên hàng hóa, ĐVT, SL, Đơn giá (chưa VAT), Thành tiền (chưa VAT), Thuế suất, Tiền thuế, Tổng sau thuế.
- Dòng cuối là **TỔNG CỘNG** của Thành tiền, Tiền thuế, Tổng sau thuế, cho cả hai khối.

File xlsx xuất ra gồm:
- Dòng 1 là tiêu đề gộp ô, dạng "TỔNG HỢP ĐẦU VÀO - RA CỦA … <KHÁCH> THÁNG MM.YYYY". Nếu lọc theo khoảng ngày thì ghi "TỪ dd/mm/yyyy ĐẾN dd/mm/yyyy".
- Dòng 3 là hai khối tiêu đề gộp ô.
- Dòng 4 là tiêu đề cột.
- Tiền định dạng VND, có dấu phân cách hàng nghìn. Thuế suất hiện dạng %. Ngày hiện dd/mm/yyyy.
- Tên file: `Doi chieu mua ban_<Khach>_<ky>.xlsx`.

Nút Excel mặc định của ERP vẫn giữ, nhưng không phải là đầu ra chính.

## 7. Ràng buộc

- Code nằm trong app `erpnext`, module Accounts, theo cấu trúc thư mục của repo (skill `code_structure`, hook chặn đặt sai chỗ). Python thụt lề bằng tab.
- **Quyền xem: chỉ Accounts User và Accounts Manager.** Anh chốt điều này vì báo cáo lộ biên lãi từng dòng.
  - Vai trò Kế toán HĐĐT và Kế toán trưởng HĐĐT **không** được xem.
  - Nút xuất Excel phải kiểm cùng quyền này.
- Có test chạy trên `erptest.local`, chạy tuần tự (dùng chung CSDL):
  - một dòng ghép được;
  - một dòng không ghép được;
  - một dòng bán ghép với hai hoá đơn mua;
  - lọc NCC;
  - tổng khớp, kể cả trường hợp hai dòng cùng mã hàng trên một hoá đơn;
  - người không có quyền gọi nút xuất bị chặn.
- Thực tế dữ liệu trên máy thử:
  - Chỉ 4/55 dòng PO có `sales_order_item`.
  - Chưa hoá đơn mua nào có `bill_no`.
  - Chưa SI nào có số HĐĐT.

  Báo cáo vẫn phải chạy đúng khi phần lớn dòng trống bên NCC. Việc nhập liệu PO từ SO là chuyện vận hành, nằm ngoài phạm vi.

## 8. Để người dựng quyết (quyết định của Claude, chưa hỏi anh)

- Loại báo cáo: **Script Report**, vì có sẵn bộ lọc, xem trên desk và in. Nút xuất mẫu là một method whitelist trả file xlsx, dùng `openpyxl`.
- Tên báo cáo: "Đối chiếu mua vào - bán ra".
- Bộ lọc Kỳ: chọn **Tháng** (mặc định tháng hiện tại), hoặc nhập Từ ngày / Đến ngày. Nhập ngày thì ghi đè tháng.
- Hoá đơn trả hàng (`is_return`) trong kỳ hiện thành dòng âm bên bán, bên NCC để trống (bản này chưa ghép hoá đơn trả hàng mua).
- HĐĐT điều chỉnh không thành dòng riêng trong bản này, vì báo cáo đi theo SI.
- Có thể thêm cột ẩn "Chứng từ" link tới SI/PI để bấm mở, nhưng không xuất cột này ra Excel.

## 9. Đợt 2 (23/10/2026): theo bản nhận xét P0/P1

Anh chốt: chỉ **cảnh báo** khi thiếu số HĐ NCC, không bắt buộc `bill_no` khi submit hoá
đơn mua; phần công nợ (đã thu/trả, hạn, quá hạn — P2) để đợt sau.

- **Trạng thái đối chiếu** (`phan_bo.danh_gia`): Khớp / Thiếu đầu vào / Lệch giá / Lệch
  thuế suất / Lệch ĐVT / Trả hàng; một dòng có thể mang nhiều loại lệch. Không có "Lệch
  SL": mảnh đã ghép luôn cùng SL hai bên, phần SL bán vượt mua hiện thành mảnh "Thiếu đầu
  vào". Lọc được theo trạng thái, thêm lựa chọn "Chưa khớp (mọi loại)".
- **Tỷ lệ giá** = ĐG bán / ĐG mua (6 chữ số), chênh lệch %, chênh lệch thành tiền. Lệch
  giá khi |tỷ lệ − tỷ lệ hợp đồng| > 0,0005; tỷ lệ hợp đồng là bộ lọc, mặc định 1,01.
- **Số HĐ là số thật**: bên bán là số HĐĐT, bên mua là `bill_no`. Chưa có số thì để
  trống và ghi chú ("Chưa có số HĐĐT" / "Thiếu số HĐ NCC"); mã chứng từ nằm ở cột riêng
  (Excel) hoặc link dưới số HĐ (trang web).
- **Gom nhóm**: STT đánh theo dòng hàng bán, các mảnh tách từ một dòng bán cùng STT, có
  `manh` "i/n", và gộp ô bên bán (STT, KH, số HĐ, ngày, tên hàng, ĐVT, đơn giá, thuế suất)
  trên trang và Excel. Một dòng HĐ mua chia cho nhiều dòng bán thì ghi chú. Sắp xếp theo
  mã chứng từ bán, không theo số HĐ hiển thị.
- **Trả hàng**: trạng thái riêng, ghi chú "Trả lại HĐ <số>", số âm đỏ trong ngoặc.
- **Kỳ**: chỉ còn Từ ngày / Đến ngày (theo ngày HĐ đầu ra), mặc định tháng hiện tại; trọn
  một tháng thì nhãn vẫn là "THÁNG mm.yyyy". HĐ mua ngày trước kỳ thì ghi chú "ngoài kỳ".
- **Tổng**: TỔNG CỘNG theo đúng các dòng đang lọc; tỷ lệ giá bình quân và chênh lệch chỉ
  tính trên dòng đã ghép. Tóm tắt: doanh thu có / thiếu đầu vào, số HĐ bán / mua, số
  dòng lệch, số dòng theo trạng thái.
- **Excel**: thêm khối "ĐỐI CHIẾU" (X:AD), dòng 2 ghi cơ sở kỳ, cố định tới cột Tên hàng
  (F5), phần TÓM TẮT dưới dòng tổng.

## 10. Đợt 3 (26/10/2026): ghép theo mã hàng khi thiếu liên kết

Trên prod, tháng 10 của Himedic có 29 dòng "Thiếu đầu vào". Nguyên nhân không phải thiếu hoá đơn mua mà là đứt chuỗi SO → PO → PI:

- PO lập tay, hoặc dòng PO thêm tay, nên không có `sales_order_item` (khoảng 23 dòng).
- HĐ bán không đi qua SO, ví dụ lập từ phiếu giao (4 dòng).
- PI lập theo một PO khác với PO của SO (1 dòng).

Anh đã chốt cách xử lý: ghép dự phòng theo mã hàng, trạng thái tính như bình thường, ghi chú để kế toán biết. Công cụ sửa liên kết dữ liệu để đợt sau.

- **Lượt 1** giữ nguyên ghép theo chuỗi. Lượt này chạy hết cho mọi dòng bán trước lượt 2, để dòng ghép theo mã không giành mất PI mà một dòng bán sau với tới được qua chuỗi.
- **Lượt 2** lấy phần SL còn thiếu, ghép với dòng PI cùng `item_code` và cùng công ty mà không thuộc chuỗi nào. Một dòng PI thuộc chuỗi chỉ khi dòng PO của nó lập từ một dòng SO **đã có HĐ bán**, xuất ngày nào cũng được. Lấy mọi ngày để khi mở lại kỳ cũ vẫn ra như trước.
  - Dữ liệu prod cho thấy lý do: các PO hay được lập từ SO `HM-HOASINH-*`, còn HĐ bán lại xuất từ SO `SAL-ORD-*` (SO lập trùng). PI của các SO không bao giờ xuất HĐ vẫn phải dùng được.
  - **SL so theo đơn vị kho** (`conversion_factor`), vì NCC có thể xuất theo hộp còn bán theo test. Mỗi bên cắt theo ĐVT trên hoá đơn của mình.
  - **Chặn tỷ lệ vô lý:** chỉ nhận dòng PI có tỷ lệ giá (theo đơn vị kho) trong khoảng 0,5–2 lần `ty_le_hd`. Hai bên không có chứng từ nào nối với nhau, nên chênh gấp chục lần là sai ĐVT chứ không phải lệch giá.
  - Thứ tự ưu tiên:
    1. HĐ mua ngày trước HĐ bán;
    2. tỷ lệ giá gần `ty_le_hd` nhất;
    3. ngày gần HĐ bán nhất.
  - Ngày được xếp trên giá. Nếu xếp giá trên, trên prod HĐ bán tháng 9 lấy mất PI tháng 10 của mã AH-M53D-DIL.
- **Khác ĐVT nhưng cùng đơn vị kho:** so giá theo đơn vị kho, Ghi chú ghi "Quy đổi 1 hộp = 30 Test". Khác cả đơn vị kho thì vẫn báo "Lệch ĐVT". Áp dụng cho cả dòng ghép theo chuỗi.
- **Hàng 0 đồng** (cả hai bên giá 0) không tính là lệch giá. Ghi chú ghi "Hàng 0 đồng".
- **Chạy thử trên dữ liệu prod (26/10):**
  - Tháng 10 Himedic: code cũ ra 29 dòng thiếu, code mới ra 68 Khớp và 4 thiếu.
  - Cả 4 dòng thiếu thuộc SINV-00028 (Deka). Nguyên nhân là PI-00022 ghi "hộp" với hệ số quy đổi 1, trong khi giá tính theo 10 đĩa. Vì vậy HĐ bán tháng 9 phải lấy PI tháng 10.
  - Giả lập sửa hệ số này thành 10 thì ra 72/72 Khớp, trong đó 29 dòng ghép theo mã.
- **Không ghép trùng.** PI dự phòng không gắn với khách nào, nên mọi dòng SI cùng mã hàng đến hết kỳ (mọi khách, cả các kỳ trước) đều chạy qua hai lượt với `trong_ky=False`. Nhờ vậy một PI không được ghép lại ở tháng sau hay cho khách khác.
- **Hiển thị.**
  - Ghi chú "Ghép theo mã hàng – thiếu liên kết SO→PO", hoặc "– HĐ bán không qua SO".
  - Ô tóm tắt và Excel có thêm số dòng và doanh thu ghép theo mã.
- **Rủi ro đã biết:** nếu cùng mã hàng mua cho nhiều khách mà PO không gắn SO, PI có thể bị ghép cho dòng bán đến trước, không đúng khách. Ghi chú trên dòng là dấu hiệu để kiểm tra lại.

## 11. Đợt 4 (27/10/2026): ba tầng ghép, tách "trong cặp SO→PO" khỏi "theo mã hàng"

Anh đề xuất: cảnh báo "thiếu liên kết" chỉ dành cho dòng thật sự không có chứng từ nối; dòng mà PO vẫn lập từ đúng đơn bán thì nhãn nhẹ hơn.

- **Tầng ① chuỗi** (`so_detail` → PO `sales_order_item` → PI `po_detail`): giữ nguyên.
- **Tầng ② trong cặp SO→PO:** lấy dòng PI trong pool dự phòng (cùng quy tắc pool ở §10), cùng `item_code`, mà **PO của nó có ít nhất một dòng** lập từ đơn bán của dòng bán. Xét cả PO chứ không xét riêng dòng PO, vì trên prod dòng hàng hay được thêm tay vào PO lập từ SO. Ví dụ PO-00078 có 3 dòng từ SAL-ORD-00052 và 6 dòng thêm tay. Các dòng thêm tay không mang `sales_order`, nên nếu xét theo dòng thì tầng ② ra 0 dòng.
  - Ưu tiên: cùng số lượng (theo đơn vị kho) với phần còn thiếu của dòng bán, rồi tỷ lệ giá gần `ty_le_hd` nhất, rồi ngày như tầng ③.
  - **Không chặn theo khoảng tỷ lệ giá:** đã có chứng từ nối, nên ghép rồi để trạng thái báo Lệch giá hoặc Lệch ĐVT, thay vì báo thiếu đầu vào.
  - Ghi chú: "Ghép trong cặp SO→PO (SO → PO)". Cột ẩn `theo_cap=1`, không gắn `theo_ma`.
- **Tầng ③ theo mã hàng toàn kỳ:** như §10, giữ khoảng tỷ lệ 0,5–2. Chỉ tầng này mang ghi chú "thiếu liên kết SO→PO" và được đếm vào "Ghép theo mã hàng (thiếu liên kết)".
- Mỗi tầng chạy hết mọi dòng bán rồi mới sang tầng sau. Dòng SI kỳ trước hoặc của khách khác (`trong_ky=False`) có thêm `sales_order`, nên cũng tiêu tầng ② theo đúng thứ tự thời gian.
- Ô tóm tắt và Excel thêm "Ghép trong cặp SO→PO" (số dòng, doanh thu), không tô cảnh báo.
- **Giới hạn:**
  - SO bị huỷ rồi sửa (amend) thì SI trỏ `SO-x-1` còn PO trỏ SO cũ, nên không thành cặp và rơi xuống tầng ③. Chưa xử lý `amended_from`.
  - SINV-00030 vẫn ở tầng ③: PI-00054 lập từ PO-00071 lập tay, không gắn SO nào.
- **Chạy thử trên dữ liệu prod (27/10), tháng 10 Himedic:**
  - Ghép giống hệt code đang chạy, từng dòng: 72 dòng, 68 Khớp, 4 Thiếu (vẫn SINV-00028, PI-00022 sai hệ số quy đổi). Chỉ nhãn đổi.
  - 25 dòng ghép theo mã tách thành 10 dòng tầng ② (SINV-00043, -00035-1, -00047, -00050) và 15 dòng tầng ③.
  - Phân loại 15 dòng tầng ③:
    - 10 dòng có PO lập tay hoàn toàn: PO-00060, -00059, -00071, -00082.
    - 4 dòng HĐ bán không qua SO, mà lập từ phiếu giao: SINV-00029, -00046.
    - 1 dòng PI không qua PO.
  - Hướng mở rộng chưa làm: lấy SO của dòng bán qua phiếu giao (`against_sales_order`).

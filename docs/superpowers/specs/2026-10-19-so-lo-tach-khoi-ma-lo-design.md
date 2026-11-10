# Tách "số lô" khỏi "mã lô" (Batch ID) — thiết kế

Ngày: 19/10/2026 · Người yêu cầu: anh.dn@miyano.com.vn · App: `erpnext` (module Warehouse Operations), `miyano_pda`, `miyano_portal`

## 1. Vì sao

Hiện tại số lô nhà cung cấp (NCC) do thủ kho gõ trên phiếu nhập lô (`Batch Entry.items[].so_lo`) được dùng
**làm luôn tên bản ghi `Batch`** (`batch_id = so_lo`, `batch.json` có `autoname: field:batch_id`). Tên
`Batch` là khoá chính nên không được trùng. Thực tế **hai mặt hàng khác nhau rất hay có chung số lô** (anh
gặp nhiều lần): mặt hàng nhập sau bị chặn bởi `kiem_tra_so_lo` ("lô đã thuộc mặt hàng khác",
`batch_entry.py:162-183`) và thủ kho không có cách nhập đúng.

Ngoài ra số lô NCC dài còn không nhét vừa mã vạch Code128 trên tem 50×30 (giới hạn ở `vitri/ma_vach.py`),
nên thủ kho đang bị ép gõ số lô ngắn hơn thực tế.

## 2. Mục tiêu

1. Mỗi `Batch` có **mã lô** do hệ thống tự sinh, không trùng, và **số lô** do thủ kho nhập, được phép trùng.
2. **Mọi chỗ người dùng nhìn thấy đều hiện số lô, không hiện mã lô.** Lời anh: "những hiển thị ra sẽ hiển
   thị số lô chứ không hiển thị theo batch id nữa", kể cả tem nhãn.
3. **Mã vạch trên tem mã hoá mã lô tự sinh.** Lời anh: "mã vạch sẽ theo mã hoá tự sinh vì khi quét mới biết
   lô nào sản phẩm gì".

## 3. Không làm / phải tránh

- **Không đổi tên** các `Batch` đã có. Tem cũ đang dán trên thùng phải quét được như trước.
- **Phải tránh:** gộp nhầm hai lô thật sự khác nhau vào một bản ghi (sai tồn, sai FEFO, sai truy vết thu hồi).
- **Phải tránh:** mã lô tự sinh lộ ra như "số lô" ở bất cứ màn nào người dùng đọc.
- Không sửa lõi tồn kho ERPNext (Stock Ledger, Serial and Batch Bundle). Chỉ đổi cách đặt tên và cách hiển thị.

## 4. Quyết định đã chốt với anh

| # | Quyết định | Nguồn |
|---|---|---|
| Q1 | Mã lô tự sinh theo mẫu **`L26-000123`**: chữ `L`, 2 số cuối của năm, `-`, 6 chữ số tăng dần (naming series `L.YY.-.######`) | anh chốt |
| Q2 | Mã vạch Code128 trên tem lô và tem kiện **mã hoá mã lô tự sinh** | anh chốt |
| Q3 | Chữ người đọc trên tem in **số lô** | anh chốt |
| Q4 | Nhận diện lô = **(mặt hàng, số lô, hạn dùng)**. Trùng cả ba thì dùng lại lô cũ; **khác hạn dùng thì tách lô mới**; khác mặt hàng thì luôn là lô riêng | anh chốt |
| Q5 | Cùng mặt hàng + số lô + hạn dùng nhưng **khác NCC** vẫn là **một lô** | **em quyết**, anh chỉ nhắc hạn dùng; đổi được |
| Q6 | Dòng chữ dưới mã vạch (F11) in **mã lô** `L26-000123`, khớp với mã vạch để gõ tay khi vạch mờ. Đây là **ngoại lệ duy nhất** của mục tiêu 2; số lô vẫn in to ở F6 | anh chốt (chọn a) |
| Q7 | Kho khách trên portal nhận diện lô theo **(vật tư, số lô, hạn dùng)**. Phiếu giao từ ERPNext ghi **số lô** (không ghi mã lô) vào sổ kho khách | anh chốt |

## 5. Thiết kế

### 5.1 Dữ liệu `Batch`
- Thêm custom field **`custom_so_lo`** (Data, bắt buộc với lô mới tạo từ `Batch Entry`, `in_list_view`,
  `in_standard_filter`, `bold`), tạo bằng **patch** như `them_so_goi_va_o_in_tem.py` (module này không dùng
  fixtures), đăng ký trong `erpnext/patches.txt`.
- Property Setter trên `Batch`: `title_field = custom_so_lo`, `show_title_field_in_link = 1`, thêm
  `custom_so_lo` vào `search_fields`. Mục đích: ô Link "Batch" ở mọi form ERPNext (Purchase Receipt, Delivery
  Note, Stock Entry…) hiện số lô và gõ số lô vẫn tìm được. Vì số lô có thể trùng, ô chọn phải hiện kèm mặt
  hàng và hạn dùng để phân biệt (cột mô tả của search).
- **Patch dữ liệu cũ:** mọi `Batch` có `custom_so_lo` rỗng được gán `custom_so_lo = name`. Tên giữ nguyên.

### 5.2 Sinh mã lô
- Mã sinh bằng naming series `L.YY.-.######` (Q1). Mã luôn dài 10 ký tự, vừa giới hạn mã vạch hiện có.
- Chỗ gán: khi `Batch Entry` tạo lô (`_dam_bao_lo`, `batch_entry.py:207-252`) truyền `batch_id` đã sinh,
  **hoặc** hook `Batch.before_insert`/`autoname` sinh mã khi `custom_so_lo` có giá trị. Builder chọn, với ràng
  buộc: lô do `Batch Entry` tạo **luôn** mang mã `L..`, không phụ thuộc cấu hình `Item.batch_number_series`
  hay Stock Settings của từng mặt hàng.
- Hook `vitri/ma_vach.kiem_ky_tu_lo` (kiểm ký tự `batch_id`) giữ nguyên, mã tự sinh luôn qua.

### 5.3 Phiếu nhập lô (`Batch Entry`)
- Thủ kho vẫn gõ `so_lo` như bây giờ (`batch_entry_item.so_lo`, Data). `lo_da_tao` (Link → Batch) giữ mã lô.
- `kiem_tra_so_lo`:
  - **bỏ** kiểm "lô đã thuộc mặt hàng khác";
  - **bỏ** giới hạn độ dài/ký tự theo mã vạch, vì số lô không còn vào mã vạch. Giữ các kiểm vệ sinh cơ bản
    (cắt khoảng trắng, không rỗng) và độ dài tối đa của trường;
  - sửa mô tả trường `so_lo` ở `batch_entry_item.json` cho khớp.
- `_dam_bao_lo`: tìm lô có sẵn theo **(item, custom_so_lo, expiry_date)** thay vì theo tên.
  - Hạn dùng rỗng được coi như một giá trị (cùng mặt hàng + cùng số lô + cùng không có hạn dùng thì là cùng lô).
  - Thấy lô thì dùng lại, giữ nguyên cách "chỉ điền trường đang rỗng" hiện có. Không thấy thì tạo lô mới với
    mã tự sinh.
  - Nếu tìm ra **nhiều hơn một** lô khớp (dữ liệu cũ lỗi) thì báo lỗi rõ ràng, không đoán.
- Kiểm trùng trong **cùng một phiếu**: hai dòng cùng (item, số lô, hạn dùng) phải trỏ về một lô.
- `kiem_tra_dong_chua_bi_be_khac_phu`, `on_cancel` và guard huỷ giữ nguyên logic, chỉ so theo `lo_da_tao`
  (mã lô).

### 5.4 Tem (`vitri/nhap_lo.py::du_lieu_tem`, `vitri/tem_kien.py`, `public/js/warehouse_operations/tem_lo.js`, `in_nhan_lo.js`, `batch.js`)
- F6 ("Lô …") in **số lô**.
- F10 (nội dung mã vạch) là **mã lô**.
- F11 (dòng chữ dưới mã vạch) in **mã lô** (Q6).
- Số lô dài phải xuống dòng hoặc thu chữ trong ô F6, không cắt mất ký tự (tiền lệ cắt "…" ở mã hàng 22 ký tự).
- Tem kiện (`tem_kien.py:92-111`) làm tương tự.

### 5.5 Quét mã và tra cứu (`vitri/quet.py`, trang `quet_ma_tra_cuu`, PDA)
- Quét mã vạch: giá trị quét là mã lô, `scan_barcode` của ERPNext tìm `Batch` theo tên như hiện tại. **Không
  đổi đường tìm**; chỉ đổi kết quả trả về (`_tra_cuu_lo`, hiện `so_lo: lo.name`) để có cả `ma_lo` (để máy dùng)
  và `so_lo` (để hiện).
- **Gõ tay số lô** để tra cứu: xem E3.
- Tem cũ (mã vạch = tên cũ = số lô cũ) vẫn quét đúng nhờ patch ở 5.1.

### 5.6 Hiển thị
Nguyên tắc: **máy nối bằng mã lô, người đọc số lô.** Không đổi kiểu hay giá trị các cột liên kết (vd
`Location Balance.so_lo` là Link → Batch, giữ chứa mã lô). Chỉ đổi lớp hiển thị.

| Nơi | Việc |
|---|---|
| Báo cáo `ton_kho_theo_vi_tri`, `doi_soat_ton_vi_tri`, `hang_nam_sai_vi_tri`, `hang_chua_xep_vi_tri` | cột "Số lô" hiện `custom_so_lo`. Có thể giữ Link ẩn hoặc dùng title-link để bấm được |
| `vitri/fefo.py`, `lay_hang.py`, `o_tem.py`, `quet.py` (dữ liệu trả lên màn) | trả kèm `so_lo` hiển thị bên cạnh mã lô |
| Trang `lay_hang_pda`, `xep_hang_pda`, `dat_o_hang_loat`, `quet_ma_tra_cuu` | hiện số lô |
| PDA `miyano_pda/.../kho_pda/man_tra_cuu.js`, `man_lay_hang.js`, `man_xep_hang.js`, `man_dat_o.js`, và bundle `erpnext/pda_app` | hiện số lô |
| `lay_hang_dialog.js`, `delivery_note.js` | hiện số lô |
| Form/list ERPNext có Link Batch | nhờ title field (5.1). Builder kiểm thực tế trên Purchase Receipt, Delivery Note, Stock Entry, và trong lưới con |
| Portal `miyano_portal` | xem 5.7 |

- Chỗ nào số lô có thể trùng trong cùng một danh sách thì **luôn hiện kèm mã hàng/tên hàng** (nhiều màn đã có sẵn).
- `miyano_wms` đang cài nhưng chức năng đã gộp vào module Warehouse Operations. Builder kiểm xem nó còn được
  dùng không. Còn dùng thì làm tương tự, không thì bỏ qua và ghi rõ trong PR.
- `miyano_portal-redesign` không cài, bỏ qua. `miyano_portal/setup/seed_100_vat_tu.py` là dữ liệu mẫu, cập
  nhật nếu rẻ.

### 5.7 Portal khách hàng (`miyano_portal`, Q7)
- Sổ kho khách (`kho/ledger.py`: `_lot_balance_name`, `_current_qty`, `_apply_to_balance`, `get_lot_balance`…)
  đổi khoá lô từ (kho, vật tư, `so_lo`) sang **(kho, vật tư, `so_lo`, `han_su_dung`)**, với `so_lo` = **số lô
  bao bì**. Hạn dùng rỗng được coi như một giá trị (cùng quy ước 5.3).
- `kho/delivery_hook.py` ghi `Batch.custom_so_lo` (và hạn dùng của lô) vào sổ, **không** ghi tên `Batch`.
- Nhập tay, import Excel (`dong_phieu.py`) và tồn đầu (`import_ton_dau.py`) khớp lô theo cùng bộ khoá. Mẫu
  import phải có cột hạn dùng nếu chưa có. Builder kiểm và báo trong PR.
- Các phép nối sang ERPNext (`han_dung_khach.py`, `doi_sanh_ton.py`, hiện nối `so_lo` với tên `Batch`) đổi
  sang nối theo (item, `custom_so_lo`, `expiry_date`).
- Dữ liệu cũ: các dòng sổ hiện có đang chứa tên lô cũ, mà tên lô cũ = số lô (patch 5.1), nên không phải chuyển
  giá trị. Chỉ cần kiểm không có hai dòng trùng (kho, vật tư, số lô) nào bị gộp sai khi thêm hạn dùng vào khoá.
- Màn Vue `Kho.vue`, `PhieuXuatDetail.vue`, `PhieuNhapDetail.vue`, `BaoCaoNXT.vue`, `kho-bao-cao-columns.js`
  hiện số lô kèm hạn dùng.

## 6. Ràng buộc

- Frappe v15 / ERPNext v15 fork của `mvl26`. Làm trên nhánh tách từ `develop`, PR vào `develop`.
- Test chạy trên `erptest.local`. Máy dùng chung với các agent/phiên khác: test chạy tuần tự, và
  `test_luong_nhap`/`test_gan_vi_tri` đang lỗi sẵn vì môi trường.
- Prod `miyano` ở máy khác: các patch phải chạy được qua `bench migrate` và chạy lại nhiều lần không hỏng.
- Không phá tem đã in: mọi mã vạch đang dán vẫn tra ra đúng lô.

## 7. Để builder tự quyết

- Cách gắn naming series (5.2), tên hàm/biến (theo lối đặt tên tiếng Việt không dấu của module).
- Bố cục chữ trên tem cho số lô dài.

## 7b. Các điểm em tự quyết sau vòng rà soát (anh xem lại khi đọc)

- **E1. Lô cũ chưa có hạn dùng.** Tìm theo (item, số lô) ra đúng **một** lô có `expiry_date` rỗng, mà phiếu
  mới có hạn dùng, thì **dùng lại lô đó và điền hạn dùng vào** (giữ hành vi cũ của `_dam_bao_lo`), không tách
  lô mới. Lý do: tránh một lô thật bị tách đôi sau patch, làm sai FEFO, truy vết và kiểm kê. Ngoại lệ duy nhất
  này áp dụng cho lô có hạn dùng rỗng; hạn dùng đã có mà khác thì tách lô mới (Q4).
- **E2. Lô tạo ngoài `Batch Entry`** (hộp lô của ERPNext, `batch_number_series`, Stock Entry, import): không
  chặn. Hook `Batch.before_insert` gán `custom_so_lo = batch_id/name` khi rỗng, để số lô luôn có giá trị và
  title field không bao giờ trống. Các lô này không bắt buộc mang mẫu `L..`.
- **E3. Gõ tay để tra cứu** luôn trả **mọi** lô khớp, theo tên **hoặc** theo `custom_so_lo`. Đúng một kết quả
  thì vào thẳng, nhiều hơn thì cho chọn (số lô, mặt hàng, hạn dùng). Thay cho "tìm theo tên trước" ở 5.5.

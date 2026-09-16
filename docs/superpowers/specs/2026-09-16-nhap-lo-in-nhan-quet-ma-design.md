# Nhập lô khi nhập kho · In nhãn lô 50×30 · Quét mã tra cứu

> Khối C của nền tảng vị trí kho. Nối tiếp
> `2026-09-14-nen-tang-vi-tri-kho-design.md` (khối A) và
> `2026-09-15-gan-vi-tri-co-dinh-theo-mat-hang-design.md` (khối B).
> Spec này trả lời hai câu §12 mà khối B để lại.

## 1. Mục tiêu

Khi hàng về, thủ kho khai **số lô và hạn dùng cho từng mặt hàng trên phiếu nhập**,
hệ thống tạo bản ghi lô đầy đủ (lô · HSD · NCC · phiếu nhập), **in được nhãn 50×30**
dán lên hàng, và **quét lại nhãn đó** ra toàn bộ thông tin đã nhập.

Vị trí không phải khai lại: mặt hàng đã có vị trí cố định từ khối B, hệ tự suy ra ô.

## 2. Phạm vi

**Trong phạm vi**: doctype `Batch Entry` (+ bảng con) · 3 custom field · móc điền NCC ·
nhãn lô `tem_lo.js` · hàm tra cứu khi quét · đổi gợi ý phiếu xếp từ *theo mặt hàng*
sang *theo lô*.

**Ngoài phạm vi**: xem §13.

## 3. Bốn quyết định của chủ đầu tư (16/09/2026)

| Câu | Quyết định |
|---|---|
| Màn hình nhập lô ở đâu | **Màn hình riêng, gắn với phiếu nhập** — không sửa hộp thoại lô sẵn có của ERPNext |
| Nhãn thiếu chỗ cho NCC | **Không bỏ ô nào, bỏ NCC khỏi nhãn.** NCC tra bằng cách quét |
| Mã vạch F10 mã hoá gì | **Số lô** |
| F8 in vùng đã gán hay ô cụ thể | **Ô cụ thể** (`VT 1A0101-0201`) — kéo theo §8 |

Chốt thêm, đã ghi ở khối B §12 và giữ nguyên: **ảnh mockup thắng bảng chữ F1–F11.**
Ảnh: `docs/vi_tri_kho/Screenshot 2026-09-15 142544.png`.

## 4. Dữ liệu

### 4.1 Dùng lại `Batch`, không đẻ doctype lô mới

`Batch` đã mang đủ: `batch_id` · `item` · `item_name` · `expiry_date` ·
`manufacturing_date` · `supplier` · `reference_doctype` / `reference_name` ·
`batch_qty` · `stock_uom` · `batch_bar_code`.

Quan trọng nhất: `autoname` lấy thẳng `batch_id` (`batch.py:115-119`) → **tên bản ghi
chính là số lô của nhà cung cấp**. Quét mã ra là ra đúng bản ghi, không cần bảng tra.

**Vị trí KHÔNG lưu trên `Batch`.** Nó suy từ `Item Location Preference` + `goi_y_o()`.
Lưu thêm một bản sao là tạo nguồn sự thật thứ hai cho cùng một điều. Ngoại lệ duy nhất
là `custom_o_in_tem` ở §4.2 — đó không phải "vị trí của lô", đó là *ghi lại một tờ giấy
đã in ra và đang dán trên thùng hàng*, một sự kiện lịch sử không suy lại được.

### 4.2 Ba custom field

Theo đúng khuôn `patches/v1_0/them_co_quan_ly_vi_tri.py`: dùng
`create_custom_field`, tiền tố `custom_`, mỗi field một patch ghi rõ lý do.

| DocType | Field | Kiểu | Ghi chú |
|---|---|---|---|
| `Batch` | `custom_so_goi` | Data, `read_only: 1`, `insert_after: "reference_name"` | Ô **F9**. Chỉ `Batch Entry` được đặt |
| `Batch` | `custom_o_in_tem` | Link `Storage Location`, `read_only: 1`, `insert_after: "custom_so_goi"` | Ô đã in lên nhãn — §8 |
| `Item` | `custom_thong_so_tem` | Data (60 ký tự), `insert_after: "description"` | Ô **F4** `7Fr – Loop 10cm – HD 200cm` |

`custom_thong_so_tem` đặt trên **Item** chứ không phải Batch, vì thông số phân biệt SKU
là thuộc tính của mặt hàng. Khai một lần, mọi lô dùng chung. Đặt trên Batch là bắt thủ
kho gõ lại cùng một chuỗi cho từng lô — và gõ lệch nhau giữa các lô.

### 4.3 Móc điền NCC — vá đường tạo lô mặc định

`doc_events["Batch"]["before_insert"]` → `vitri.lo_ncc.dien_ncc_tu_chung_tu`:

> Nếu `supplier` trống và `reference_doctype` là `Purchase Receipt` / `Purchase Invoice`
> và `reference_name` có giá trị → lấy `supplier` của chứng từ đó.

Đây là mục đích chính: **hộp thoại lô sẵn có của ERPNext vẫn mở được** và vẫn tạo lô
không có NCC. Móc này khiến mọi lô sinh từ chứng từ mua đều có NCC, bất kể sinh bằng
đường nào. Không chặn đường cũ — chặn sẽ vỡ các luồng kho khác dùng chung `Batch`.

### 4.4 Số gọi (F9)

`custom_so_goi = make_autoname("SOGOI-.####")` rồi cắt bỏ tiền tố `SOGOI-`.

Bộ đếm **toàn cục, không reset theo năm** — số gọi là thứ người ta đọc cho nhau qua
kho; trùng lại sau một năm là đủ để gọi nhầm. Khi bộ đếm vượt 9999 số thành 5 chữ số;
nhãn phải co cỡ chữ F9, **không** được cắt bớt số (§6.4).

### 4.5 HSD đã có chốt sẵn, không viết lại

`batch.py:203` đã `throw` nếu `Item.has_expiry_date = 1` mà lô không có HSD. Spec này
**không** thêm chốt HSD riêng — thêm là hai chỗ cùng nói một luật, rồi lệch nhau.
Điều kiện vận hành: mặt hàng y tế phải bật `has_expiry_date`.

## 5. DocType `Batch Entry`

Submittable, đúng khuôn `Location Transfer` (cùng module, cùng kiểu "phiếu riêng").

### 5.1 Trường phiếu

| Field | Kiểu | Ghi chú |
|---|---|---|
| `naming_series` | Select | `PNL-.YYYY.-` |
| `phieu_nhap` | Link `Purchase Receipt`, `reqd: 1`, `set_only_once: 1` | Chỉ chọn phiếu **nháp** (`docstatus = 0`) |
| `cong_ty` | Link Company, read-only | fetch từ phiếu nhập |
| `ngay` | Date, read-only | fetch `posting_date` |
| `nha_cung_cap` | Link Supplier, read-only | fetch `supplier` |
| `items` | Table `Batch Entry Item` | |
| `ghi_chu` | Small Text | |
| `amended_from` | Link | |

### 5.2 Bảng con `Batch Entry Item`

| Field | Kiểu | Ghi chú |
|---|---|---|
| `dong_phieu_nhap` | Data, hidden, `reqd: 1` | `Purchase Receipt Item.name` — khoá liên kết |
| `vat_tu` | Link Item, read-only | |
| `ten_hang` | Data, read-only | |
| `kho` | Link Warehouse, read-only | `Purchase Receipt Item.warehouse` (mỗi dòng một kho) |
| `so_luong` | Float, read-only | |
| `so_lo` | Data, `reqd: 1` | Thủ kho gõ từ hộp hàng |
| `ngay_san_xuat` | Date | |
| `hsd` | Date | |
| `o_goi_y` | Link `Storage Location`, read-only | `goi_y_o(vat_tu, kho)[0]` |
| `ly_do_goi_y` | Small Text, read-only | `goi_y_o(...)[1]` — để màn hình nói được vì sao trống |
| `lo_da_tao` | Link Batch, read-only | Điền sau khi submit |
| `so_goi` | Data, read-only | Điền sau khi submit |

### 5.3 Luồng

1. Tạo `Batch Entry`, chọn phiếu nhập **còn nháp**.
2. Nút **"Lấy dòng hàng từ phiếu nhập"** — nạp các dòng có `Item.has_batch_no = 1`
   và `batch_no` còn trống. Điền `o_goi_y` / `ly_do_goi_y`.
3. Thủ kho gõ `so_lo`, `hsd` (và `ngay_san_xuat` nếu có).
4. **Submit** làm đúng bốn việc, theo thứ tự:
   1. `validate` — §5.5;
   2. tạo `Batch` cho từng dòng: `batch_id` · `item` · `expiry_date` ·
      `manufacturing_date` · `supplier` · `reference_doctype = "Purchase Receipt"` ·
      `reference_name` · `custom_so_goi`;
   3. ghi `batch_no` lên dòng phiếu nhập tương ứng (`dong_phieu_nhap`);
   4. ghi ngược `lo_da_tao` · `so_goi` vào bảng con.
5. Nút **"In nhãn"** — hiện sau khi submit. §6.
6. Submit **phiếu nhập** như bình thường. ERPNext tự dựng `Serial and Batch Bundle`
   từ `batch_no` — `stock_controller.py:231-234` tự bật `use_serial_batch_fields = 1`
   khi thấy `batch_no` có giá trị. Ta không đụng vào nội bộ bundle.

**Thứ tự bắt buộc là nhập lô TRƯỚC, submit phiếu nhập SAU.** Làm ngược lại thì ERPNext
đã sinh số lô máy theo `batch_number_series`, và số lô của nhà cung cấp mất luôn —
đúng thứ mà nhãn phải in ra.

### 5.4 Một dòng phiếu nhập = một lô

Ràng buộc có chủ đích. Lý do: ghi `batch_no` lên dòng phiếu là đường **ít bám dính
nhất** vào ERPNext — một trường, không có gì khác. Cho nhiều lô trên một dòng thì phải
tự dựng `Serial and Batch Bundle`, tức bám vào nội bộ một hệ thống vốn đã đổi kiến trúc
lô một lần giữa v14 và v15.

Một lô đến hai lô cho cùng mặt hàng → **tách dòng trên phiếu nhập**. ERPNext hỗ trợ sẵn,
và tách dòng còn khiến số lượng theo từng lô đúng ngay trên chứng từ.

### 5.5 `validate`

Theo thứ tự — thứ tự này là một phần của spec, vì câu báo lỗi đầu tiên người dùng thấy
phải là câu chỉ đúng chỗ sai:

1. `phieu_nhap` còn `docstatus = 0`. Đã submit → `throw`, nói rõ phải nhập lô trước.
2. `dong_phieu_nhap` không trùng nhau trong phiếu (§5.4), và mỗi giá trị thuộc đúng
   `phieu_nhap` đang chọn.
3. `so_lo` không rỗng sau khi `strip()`.
4. **Trần độ dài mã vạch** (§6.4). Vượt → `throw` kèm đúng giới hạn và số ký tự đang có.
5. `so_lo` chưa tồn tại như một `Batch` **của mặt hàng khác** — trùng số lô giữa hai
   mặt hàng khác nhau là hợp lệ trong ERPNext (`Batch.name` là duy nhất toàn hệ) nên
   ta chặn ở đây thay vì để lỗi khoá chính bật ra lúc `insert()`.
6. `hsd` > `ngay_san_xuat` khi cả hai có giá trị.

### 5.6 Huỷ

- Phiếu nhập **còn nháp** → gỡ `batch_no` khỏi các dòng phiếu nhập, giữ nguyên các bản
  ghi `Batch`. **Không xoá `Batch`**: tem có thể đã in và đang dán trên thùng hàng; xoá
  bản ghi biến tem thành rác không tra được.
- Phiếu nhập **đã submit** → `throw`, chặn huỷ. Tồn đã ghi theo lô; gỡ lô ra khỏi một
  chứng từ đã submit là việc của `Purchase Receipt.cancel`, không phải của phiếu này.

## 6. Nhãn lô 50×30

File mới `erpnext/public/js/vi_tri_kho/tem_lo.js`, dùng lại **nguyên kỷ luật lưới điểm**
của `tem_vi_tri.js` (đã kiểm chứng trên ZD421): `flex: 0 0 auto` cho khối mã vạch,
`min-width: 0` cho cột chữ, `preserveAspectRatio="none"` đi kèm `displayValue: false`.

### 6.1 Bố cục A (theo mockup) — mặc định

Vùng in an toàn **47 × 27 mm**, lề 1,5 mm, gốc toạ độ góc trên-trái.

```
┌─────────────────────────────────────┬──────────────┐
│ F1  1130-N6214210          F3 Cái (1/hộp)          │  R1  5,0mm
│ F2  Stent Piglet (Piglet Stent)                    │  R2  4,5mm
│ F4  7Fr – Loop 10cm – HD 200cm                     │  R3  3,5mm
├─────────────────────────────────────┼──────────────┤
│ F5  HSD 2029/01/31                  │ F7 NHẬP 2026/09/03 │ R4 3,5mm
│ F6  Lô 25L4125                      │ F8 VT 3B1205-0401  │ R5 3,5mm
│ F10 ▮▮▯▮▯▮▮  F11 25L4125            │ F9   3856          │ R6 7,0mm
└─────────────────────────────────────┴──────────────┘
  cột trái 29,4mm            gap 0,6      cột phải 17,0mm
```

| Ô | Nguồn | Định dạng | Cỡ chữ |
|---|---|---|---|
| F1 | `Item.name` | nguyên văn | 11pt đậm |
| F2 | `Item.item_name` | nguyên văn | 9pt đậm |
| F3 | `Item.stock_uom` + quy cách | §6.3 | 6,5pt |
| F4 | `Item.custom_thong_so_tem` | nguyên văn; trống thì **để trắng**, không dồn hàng dưới lên | 6,5pt |
| F5 | `Batch.expiry_date` | `HSD YYYY/MM/DD` | 8pt đậm |
| F6 | `Batch.batch_id` | `Lô {sl}` | 7pt |
| F7 | `Purchase Receipt.posting_date` | `NHẬP YYYY/MM/DD` | 6,5pt |
| F8 | `Batch.custom_o_in_tem` | `ma_vi_tri.dinh_dang_nhan(o)` → `VT 3B1205-0401` | 7pt đậm |
| F9 | `Batch.custom_so_goi` | nguyên văn | 22pt đậm, co theo §6.4 |
| F10 | `Batch.batch_id` | Code128, X = 0,25mm, cao 5,0mm | — |
| F11 | `Batch.batch_id` | nguyên văn dưới mã vạch | 5pt |

Tổng hàng: 5,0 + 4,5 + 3,5 + 3,5 + 3,5 + 7,0 = **27,0 mm** ✓

Lưới **cố định**: ô trống vẫn chiếm đúng chiều cao của nó. Dồn hàng lên khi thiếu dữ
liệu làm hai nhãn cạnh nhau đặt cùng một thông tin ở hai độ cao khác nhau, và người
đứng trước kệ đọc nhãn bằng vị trí trước khi đọc bằng chữ.

### 6.2 Hình học in — ZD421 203 dpi

1 dot = 1/203 inch = 0,125 mm. Module mã vạch phải là **số nguyên dot**:
2 dot = **0,25 mm**. 1 dot (0,125 mm) dưới ngưỡng đọc tin cậy của Code 128; 3 dot
(0,375 mm) làm mã tràn khung. **X = 0,25 mm là giá trị duy nhất dùng được** — giống
hệt kết luận đã chốt cho tem vị trí.

### 6.3 Ô F3 — ĐVT và quy cách

Mockup in `Cái (1/hộp)`. Quy tắc:

- Nếu `Item.uoms` có **đúng một** dòng `UOM Conversion Detail` với `uom != stock_uom`
  → in `{stock_uom} ({conversion_factor}/{uom})`, ví dụ `Cái (1/hộp)`.
- Không có dòng nào, hoặc có nhiều hơn một → in **chỉ** `{stock_uom}`.

Nhiều hơn một quy cách thì không có "quy cách" nào đúng để in; in bừa một dòng là nói
sai trên vật thể vật lý mà không ai đối chiếu lại.

### 6.4 Trần độ dài mã vạch — và bố cục B

Đây là ràng buộc **mới phát hiện khi làm spec này**, chưa ai trong dự án chạm tới.

Cột trái của bố cục A rộng 29,4 mm → mã vạch được **28,0 mm** → ở X = 0,25 mm là
**112 module**. Code 128 tiêu tốn 35 module cố định (start + checksum + stop), còn lại
77 module cho dữ liệu:

Số module tính chính xác, **không ước lượng theo độ dài chuỗi** — Code 128 đổi bộ mã
giữa chừng và mỗi lần đổi tốn một ký hiệu:

```
ký hiệu(s) = len(s)//2                nếu s toàn chữ số và len chẵn
           = 2 + (len(s)-1)//2        nếu s toàn chữ số và len lẻ   (1 ký tự bộ B + 1 ký hiệu chuyển bộ C)
           = len(s)                   nếu s có chữ                  (bộ B)

module(s)  = 35 + 11 × ký hiệu(s)     (35 = start 11 + checksum 11 + stop 13)
```

Với 112 module → **ký hiệu ≤ 7**:

| Kiểu số lô | Chứa được trong 28,0 mm |
|---|---|
| Chữ số, độ dài chẵn | **≤ 14 chữ số** |
| Chữ số, độ dài lẻ | **≤ 11 chữ số** |
| Có chữ | **≤ 7 ký tự** |

7 ký tự là quá chật cho số lô thật (`25L4125` vừa khít đúng 7; `LOT-2026-A45` thì không).
Vì vậy nhãn có **bố cục B, tự động chuyển sang khi mã không vừa**:

```
┌────────────────────────────────────────────────────┐
│ F1 1130-N6214210                   F3 Cái (1/hộp)  │  R1 4,5
│ F2 Stent Piglet (Piglet Stent)                     │  R2 4,0
│ F4 7Fr – Loop 10cm – HD 200cm                      │  R3 3,0
├─────────────────────────────────┬──────────────────┤
│ F5 HSD 2029/01/31               │                  │  R4 3,0
│ F6 Lô LOT-2026-A45  F7 NHẬP …   │ F9   3856        │  R5 3,0
├─────────────────────────────────┴──────────────────┤
│ F8 VT 3B1205-0401                                  │  R6 3,0
│ F10 ▮▮▯▮▯▮▮▮▮▯▮▮▯▮▯▮▮  F11 LOT-2026-A45            │  R7 6,5
└────────────────────────────────────────────────────┘
```

Bố cục B cho mã vạch **toàn bộ 47 mm** → 188 module → **ký hiệu ≤ 13**, tức
**≤ 26 chữ số chẵn / ≤ 23 chữ số lẻ / ≤ 13 ký tự có chữ**.

Chiều cao hàng phải dựng lại, vì F8 xuống thành một hàng riêng:

| Hàng | Nội dung | Cao |
|---|---|---|
| R1 | F1 · F3 | 4,5 mm |
| R2 | F2 | 4,0 mm |
| R3 | F4 | 3,0 mm |
| R4 | F5 │ F9 (trải R4–R5, 16pt) | 3,0 mm |
| R5 | F6 · F7 │ F9 | 3,0 mm |
| R6 | F8 (hết chiều ngang) | 3,0 mm |
| R7 | F10 mã vạch cao 4,8 mm + F11 | 6,5 mm |

Tổng: 4,5 + 4,0 + 3,0 + 3,0 + 3,0 + 3,0 + 6,5 = **27,0 mm** ✓
F9 cao 6,0 mm × rộng 17,0 mm — 16pt bốn chữ số vừa, vẫn đọc được qua lối đi.

Quy tắc chọn, tính tại thời điểm vẽ nhãn, không phải lúc nhập:

| Số lô | Nhãn dùng |
|---|---|
| vừa 112 module | **A** |
| vừa 188 module | **B** |
| vượt 188 module | `validate` đã chặn từ §5.5 bước 4 |

Trần được phát biểu bằng **số module**, không bằng số ký tự. Số ký tự chỉ là ví dụ suy
ra; phát biểu trần bằng ký tự là chỗ em đã tính sai một lần khi viết bản nháp spec này.

**Không bao giờ được thu module xuống dưới 2 dot để nhét vừa.** Mã vạch quá nhỏ trên
đầu in nhiệt không phải "khó đọc" — nó **đọc ra sai ký tự**, và sai lặng lẽ.

### 6.5 In

Hai nút, cùng đường vẽ:
- Trên `Batch Entry` (sau submit): **In nhãn cả phiếu** — mỗi lô một nhãn, xếp thành xấp
  như `in_xap()` của tem vị trí.
- Trên form `Batch`: **In nhãn** cho một lô.

Mỗi lần in, nếu `custom_o_in_tem` còn trống thì đặt = `goi_y_o(item, kho)[0]` rồi mới vẽ.
`kho` lấy từ `Batch Entry Item.kho` khi in từ phiếu; khi in từ form `Batch` thì đi
`reference_name` → dòng `Purchase Receipt Item` → `warehouse`. Không suy ra được kho
(lô không sinh từ phiếu nhập) → F8 in `VT —`, không đoán.
Đã có giá trị thì **giữ nguyên** — in lại lần hai phải ra đúng tờ giấy như lần đầu, vì
lần đầu có thể đã dán lên hàng. `goi_y_o` trả `None` (mặt hàng chưa gán) → F8 in
`VT —` và màn hình cảnh báo, chứ không chặn in.

## 7. Quét mã tra cứu

Hàm mới `erpnext/vi_tri_kho/vitri/quet.py`:

```
tra_cuu(ma: str) -> dict
```

Gọi `erpnext.stock.utils.scan_barcode(ma)` sẵn có (nó đã phân giải Item Barcode →
Serial No → **Batch** → Warehouse, `stock/utils.py:585`) rồi bồi thêm, khi kết quả là
một lô: `ten_hang` · `hsd` · `ngay_san_xuat` · `nha_cung_cap` · `so_goi` · `ngay_nhap` ·
`so_phieu_nhap` · `vi_tri_co_dinh` (từ `Item Location Preference`) · `o_dang_co_hang`
(từ `Location Balance`) · `o_in_tem` · `ton_theo_o`.

**Không sửa `scan_barcode`.** Mỗi dòng sửa mã ERPNext gốc là một điểm xung đột mỗi lần
merge bản mới; ở đây không cần vì ta bọc ngoài được.

Ô quét đặt trên form `Batch Entry` (dùng `erpnext.utils.BarcodeScanner` sẵn có), kết quả
đổ vào một khung thông tin dưới bảng con.

## 8. Tem có thể nói dối — và cách xử

Chủ đầu tư chọn in **ô cụ thể**. Hệ quả: giữa lúc in nhãn và lúc xếp hàng, một lượt
nhập khác có thể chiếm mất ô đó. Khi ấy tem dán trên thùng hàng **nói sai, trên vật thể
vật lý, và không ai biết** — đây là hạng lỗi tệ hơn mọi lỗi màn hình, vì màn hình sai
thì làm lại được, còn tem sai thì đi theo thùng hàng suốt vòng đời.

Xử bằng thứ rẻ nhất, **không** cần cơ chế giữ chỗ (giữ chỗ cần hết hạn, cần dọn khi
huỷ, cần một doctype nữa — tất cả để giải một bài mà một trường đã giải xong):

1. **In xong ghi lại**: `Batch.custom_o_in_tem` = ô vừa in (§6.5).
2. **Lúc xếp, ưu tiên ô đã in**: `goi_y_o` nhận thêm nhánh đầu tiên — nếu lô này có
   `custom_o_in_tem` và ô đó còn nhận được hàng của mặt hàng này, trả đúng ô đó.
   Không truyền `so_lo` (lúc nạp dòng `Batch Entry`, lô chưa có) → bỏ qua nhánh này.
   Tem **tự ứng nghiệm** thay vì nói dối.
3. **Bị chiếm thì nói thẳng**: phiếu xếp hiện câu
   *"tem in VT 3B1205-0401 nhưng ô đó đã có hàng khác — xếp vào 3B1205-0402, dán đè tem mới"*.

### 8.1 Kéo theo: gợi ý đổi từ *theo mặt hàng* sang *theo lô*

`xep.py:71` hiện đệm `goi_y_o` theo `vat_tu` — một mặt hàng nhiều lô cho ra một gợi ý
chung. Với §8 thì hai lô của cùng một mặt hàng có thể có `custom_o_in_tem` khác nhau,
nên khoá đệm phải là `(vat_tu, so_lo)`.

Ruling N vẫn nguyên: `goi_y_o` ném lỗi cho một lô **không** được làm sập danh sách của
cả kho.

## 9. Thay đổi trên mã sẵn có

| File | Đổi gì |
|---|---|
| `vitri/goi_y.py` | `goi_y_o(vat_tu, kho, so_lo=None)` — tham số **tuỳ chọn**, vì lúc nạp dòng `Batch Entry` lô chưa tồn tại. Thêm nhánh "ô đã in tem" lên đầu, chỉ chạy khi có `so_lo` |
| `vitri/xep.py` | Khoá đệm `(vat_tu, so_lo)`; thêm cảnh báo khi ô in tem bị chiếm |
| `hooks.py` | `doc_events["Batch"]["before_insert"]` — gộp vào key sẵn có nếu đã tồn tại |
| `vi_tri_kho/workspace/` | Thêm `Batch Entry` vào workspace |
| `patches.txt` | 3 dòng patch custom field |

**Không** sửa: `erpnext/stock/utils.py` · `serial_no_batch_selector.js` ·
`stock_controller.py` · `batch.py`.

## 10. Quyền

`Batch Entry`: `System Manager` · `Stock Manager` · `Stock User` (tạo/sửa/submit) —
cùng bộ vai trò với `VAI_TRO_DUOC_XEP` ở `xep.py:17`, vì đây cũng là việc hằng ngày của
thủ kho chứ không phải thao tác thiết lập.

`quet.tra_cuu` whitelist + kiểm vai trò như `xep._kiem_tra_quyen()` — nó lộ ra tồn kho
theo ô, đăng nhập hợp lệ không phải điều kiện đủ.

## 11. Kiểm thử

**Python** (`bench --site erptest.local run-tests --module erpnext.vi_tri_kho.tests.<tên>`,
chạy tuần tự, rồi cả bộ `vi_tri_kho` trước khi đóng):

- Submit `Batch Entry` → `Batch` tạo đúng: lô · HSD · NCC · `reference_name` · số gọi.
- `batch_no` được ghi lên đúng dòng phiếu nhập; submit phiếu nhập sau đó **không** sinh
  lô máy nào nữa.
- Chốt âm §5.4: hai dòng cùng `dong_phieu_nhap` → `throw`.
- Chốt âm §5.5-4: lô 15 chữ số → `throw`; lô 14 chữ số → qua.
- §4.3: lô tạo bằng `frappe.get_doc` với `reference_name` = phiếu nhập, `supplier`
  trống → sau `insert()` có NCC.
- §6.3: mặt hàng 0 / 1 / 2 dòng quy đổi ĐVT → ba chuỗi F3 khác nhau.
- §8: lô có `custom_o_in_tem` còn trống chỗ → `goi_y_o` trả đúng ô đó, **kể cả khi ô
  theo thứ tự `lft` là một ô khác** (dữ liệu phải dựng cho hai ô này **khác** nhau,
  nếu không bài test không chứng minh gì — cùng cái bẫy đã ghi ở khối B §10).
- §8: ô in tem bị mặt hàng khác chiếm → gợi ý trả ô khác **và** `ly_do_goi_y` nói rõ.
- §5.6: huỷ khi phiếu nhập còn nháp → `batch_no` được gỡ, `Batch` còn nguyên;
  huỷ khi phiếu nhập đã submit → `throw`.

**Trình duyệt** (`192.168.61.129:8003`, không có test Python nào thay được):

- Nhãn A và B ở kích thước thật: mọi ô nằm trong 47×27, không ô nào tràn, mã vạch đúng
  28,0 / 47,0 mm. Đo bằng `Range` như harness của tem vị trí — `scrollWidth` mù với
  tràn ở giữa.
- Số gọi 5 chữ số (§4.4) không tràn khung F9.
- Quét một mã lô bằng bàn phím giả lập → khung thông tin đổ đủ 11 trường.

## 12. Rủi ro

| Rủi ro | Xử lý |
|---|---|
| Thủ kho submit phiếu nhập trước khi nhập lô | §5.5-1 chặn từ phía `Batch Entry`, nhưng **không** chặn được từ phía phiếu nhập — ERPNext sẽ sinh lô máy. Chấp nhận: chặn phía kia là sửa `Purchase Receipt`, mở ra vùng rủi ro lớn hơn nhiều. HDSD phải nói rõ thứ tự |
| Hộp thoại lô sẵn có vẫn tạo được lô không tem | Chấp nhận có ý thức (§3, §4.3). Dữ liệu không thiếu (HSD do ERPNext chặn, NCC do móc §4.3); chỉ là số lô máy và không có nhãn |
| Số lô vượt 188 module (≈ 26 chữ số / 13 ký tự có chữ) | §5.5-4 chặn ngay lúc nhập, kèm câu báo nói rõ giới hạn. Nếu NCC thật dùng lô dài hơn → phải quay lại quyết định "mã vạch mã hoá số lô" ở §3 |
| Tem in rồi ô bị chiếm | §8 — ưu tiên ô đã in, và nói thẳng khi không giữ được |
| `custom_o_in_tem` giữ ô lại, không cho xoá | Frappe **chặn xoá** một bản ghi còn bị Link trỏ tới. Nghĩa là một ô từng in tem sẽ không xoá được khi cơ cấu lại kho. Chấp nhận, và đúng: ô đó đang được một tờ giấy dán trên thùng hàng nhắc tên. Muốn xoá thì `disabled` nó, cách khối A đã dùng |
| Bộ đếm số gọi vượt 9999 | §4.4 + §6.4: co chữ, không cắt số. Có bài test trình duyệt |

## 13. Không thuộc spec này

Sửa hộp thoại lô sẵn có của ERPNext · sửa `scan_barcode` · nhiều lô trên một dòng phiếu
nhập · cơ chế giữ chỗ ô · nhãn cho phiếu xuất · in nhãn từ Purchase Invoice ·
`Batch Entry` cho Stock Entry / chuyển kho · NCC trên nhãn (đã bỏ, §3).

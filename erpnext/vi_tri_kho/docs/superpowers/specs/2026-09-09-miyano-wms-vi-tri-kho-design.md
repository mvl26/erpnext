# Thiết kế: Quản lý vị trí kho (giá kệ / ô kệ) cho kho Miyano

Ngày: 2026-09-09 — cập nhật 2026-09-10 theo chuẩn mã 12 ký tự của SPD
Trạng thái: đã duyệt; GĐ0+GĐ1 đã thi công xong
App: **`miyano_wms`** (app mới) — site `erptest.local`
Phạm vi bật: **chỉ `Kho Miyano - MYN`** (công ty `Miyano Việt Nam`)

> Bản gốc từng nằm trong repo `miyano_portal`; đã chuyển hẳn về đây 10/09/2026 để hai hệ
> tách bạch. Nếu còn thấy bản trong `miyano_portal` thì đó là bản cũ, đừng sửa.
>
> **Cập nhật 10/09/2026:** chủ dự án chốt mã ô 12 ký tự theo
> `docs/SPD_VanHanh_PhanTichMaViTriKho_20260907_v2.docx` §5.2. Mục 5.1 và 5.8 đã viết
> lại; quyết định #5 ("quy tắc đặt mã là cấu hình") **không còn đúng** — quy tắc đặt mã
> giờ là chuẩn cứng của khách hàng, xem mục 5.1.

## 1. Bài toán

Hiện tồn kho Miyano chỉ biết tới cấp **kho** (`Kho Miyano - MYN`). Khi giao hàng, phiếu
chỉ nói "lấy từ Kho Miyano", không nói lấy ở **giá kệ nào, ô nào**. Thủ kho phải nhớ
bằng đầu; hàng đặt sai chỗ thì không ai truy được; kiểm kê phải lục cả kho.

Yêu cầu của chủ dự án (09/09/2026): *"khi giao hàng anh cũng muốn biết lấy từ kho và
vị trí nào chứ không phải lấy từ mỗi kho như bây giờ"*.

Quy mô hiện tại trên `erptest.local`: 164 mặt hàng (**80 mặt hàng có lô**, 0 serial),
13 warehouse, 120 dòng `Bin`, 192 dòng `Stock Ledger Entry`. Hệ còn rất nhẹ — đây là
thời điểm rẻ nhất để đưa chiều vị trí vào, làm sau sẽ phải chuyển đổi tồn đang có.

## 2. Quyết định nền tảng

Đã chốt với chủ dự án. Đây là ràng buộc của thiết kế, không phải gợi ý.

| # | Quyết định | Ghi chú |
|---|---|---|
| 1 | Vị trí là **doctype riêng**, không dùng cây Warehouse làm ô kệ | Chủ dự án chọn phương án B sau khi được trình cả A/B/C và được cảnh báo về khối lượng |
| 2 | Code nằm ở **app mới `miyano_wms`**, không nhét vào `miyano_portal` | `miyano_portal` là cổng khách hàng; mô hình phân quyền của nó dựng trên việc **không có** DocPerm cho vai trò Customer. Trộn kho nội bộ vào đó là mở đường cho lỗi phân quyền |
| 3 | Bật quản lý vị trí **theo từng kho chỉ định**, qua một chức năng riêng | Lần đầu bật cho **`Kho Miyano - MYN`**; Stores / WIP / Finished Goods / Hàng trả về / Transit giữ nguyên. **Không hard-code tên kho ở bất kỳ đâu** — thêm kho về sau chỉ là chạy lại chức năng bật. Xem mục 5.9 |
| 4 | Sổ vị trí **bám theo** chứng từ ERPNext, không độc lập | Khác hẳn sổ kho khách hàng (`Customer Stock Ledger Entry`) — sổ đó độc lập vì ERPNext stock bị loại trừ có chủ đích; ở đây thì không |
| 5 | ~~Quy tắc đặt mã ô là **cấu hình**, không phải code~~ → **thay bằng chuẩn mã 12 ký tự của SPD** (10/09/2026) | Lúc chốt spec chủ dự án chưa cung cấp sơ đồ kho, nên thiết kế để mã ô tự do. Sau đó khách hàng đưa `SPD_VanHanh_PhanTichMaViTriKho v2` §5.2 — mã ô là chuẩn cứng, tự nó mang toạ độ. Xem mục 5.1 |
| 6 | Theo dõi vị trí **kèm số lô** | 80/164 mặt hàng đã bật theo lô; nếu vị trí không biết lô thì không gợi ý FEFO được. Lô lấy từ `Serial and Batch Bundle`, **không** từ `SLE.batch_no` — xem mục 4.3b |
| 7 | Không đụng gì tới sổ kho khách hàng của `miyano_portal` | Hai hệ tách bạch hoàn toàn |

### 2.1 Vì sao phương án B đắt hơn — ghi lại để sau này không phải tranh luận lại

Chọn B nghĩa là **vứt bỏ `Putaway Rule` của ERPNext** (nó chỉ phân bổ theo warehouse,
vô dụng khi vị trí không phải warehouse) và **tự viết lại toàn bộ phần lô + hạn dùng
theo vị trí**. Phương án A (ô kệ = warehouse con) làm được đúng chừng đó bằng cấu hình.
Chủ dự án chọn B có ý thức, vì muốn chiều vị trí là một chiều dữ liệu riêng dùng lại
được cho các phần khác về sau, không bị trói vào ngữ nghĩa warehouse của ERPNext.

## 3. Nguyên tắc nền — bất biến của toàn hệ

> Với mọi bộ **(mặt hàng, lô, kho có bật quản lý vị trí)**:
> **tổng tồn ở các ô = `Bin.actual_qty` của ERPNext.**

Tầng vị trí **không tự quyết số lượng**. Nó chỉ chia nhỏ con số ERPNext đã chốt ra theo
từng ô. Đây là điều làm cho phương án B ở đây an toàn hơn hẳn một sổ độc lập: sổ vị trí
**không thể lệch mà không bị phát hiện**, vì có một phép so sánh đối chiếu chạy được
bất cứ lúc nào (mục 8.4).

**Van an toàn bắt buộc — ô `ZZZ-CHUA-XEP`.** Mỗi kho bật quản lý vị trí có đúng một ô hệ
thống "Chưa xếp vị trí". Chứng từ nào không khai vị trí thì hàng rơi vào đó. Nhờ vậy
bất biến **luôn** đúng kể cả với chứng từ hiếm gặp hoặc doctype ERPNext thêm về sau.
Không có van này thì mọi chứng từ ngoài dự kiến đều làm vỡ hệ.

## 4. Cơ chế móc vào ERPNext

### 4.1 Một chỗ móc duy nhất

Đã xác minh trong mã nguồn `apps/erpnext`:

- `erpnext/stock/stock_ledger.py:221-227` — hàm `make_entry()` tạo `Stock Ledger Entry`
  rồi gọi **`sle.submit()`**. Mọi chứng từ ghi sổ kho đều đi qua đây, không có ngoại lệ.
- Các chứng từ ghi sổ kho: `Purchase Receipt`, `Purchase Invoice` (update_stock),
  `Delivery Note`, `Sales Invoice` (update_stock), `Stock Entry` (mọi mục đích),
  `Stock Reconciliation`, `Subcontracting Receipt`, `Asset Capitalization`.

→ **Chỉ cần một hook `Stock Ledger Entry.on_submit`**, không phải móc 8 doctype × 3 đường
(ghi/huỷ/sửa). Doctype nào ERPNext thêm về sau cũng tự động được bắt.

```python
# miyano_wms/hooks.py
doc_events = {
    "Stock Ledger Entry": {"on_submit": "miyano_wms.ledger.tu_sle.ghi_so_vi_tri"},
}
```

### 4.2 Huỷ chứng từ

`stock_ledger.py:66-90` — khi huỷ, ERPNext **ghi thêm dòng SLE mới với số lượng đảo dấu**
rồi mới cờ `is_cancelled=1` lên dòng cũ bằng SQL thô (`set_as_cancel`, dòng 212). Dòng mới
vẫn đi qua `make_entry()` → hook vẫn nổ. Mô hình này trùng đúng với "sổ chỉ ghi thêm, huỷ
bằng bút toán đảo" đã dùng ở kho khách hàng.

**Quy tắc bắt buộc khi huỷ:** bút toán đảo phải **soi lại đúng các dòng sổ vị trí gốc**
của chứng từ đó (cùng `voucher_detail_no`, `da_huy = 0`) và ghi ngược **đúng từng ô đã
dùng**, rồi cờ `da_huy = 1` lên các dòng gốc.
**Tuyệt đối không chạy lại FEFO khi huỷ** — làm vậy sẽ trả hàng về ô khác với ô đã lấy
và làm sai tồn của cả hai ô, dù tổng vẫn đúng nên đối soát không bắt được.

### 4.3 Cái bẫy `Stock Reconciliation` — phải xử lý ngay từ đầu

`erpnext/stock/doctype/stock_reconciliation/stock_reconciliation.py`:

- Hàng **có lô / serial**: tách thành 2 dòng SLE có dấu (dòng 809 `actual_qty: -current_qty`,
  dòng 821 `actual_qty: row.qty`) → cộng dồn `actual_qty` là đúng.
- Hàng **không lô**: ghi **`actual_qty: 0`** và chỉ đặt `qty_after_transaction = tồn mới`
  (dòng 861, 870).

→ Nếu tầng vị trí cứ cộng `actual_qty` thì **mọi lần kiểm kê hàng không lô sẽ bị bỏ qua
âm thầm**. Công thức bắt buộc:

```python
delta = sle.actual_qty
if sle.voucher_type == "Stock Reconciliation" and not delta:
    # tồn trước đó = tổng tồn các ô của bộ (kho, vật tư, lô);
    # theo bất biến mục 3 con số này luôn bằng Bin.actual_qty trước giao dịch
    delta = sle.qty_after_transaction - tong_ton_vi_tri(kho, vat_tu, so_lo)
```

### 4.3b Số lô KHÔNG nằm trên SLE — phải lấy từ Serial and Batch Bundle

Đây là điểm dễ làm hỏng cả thiết kế nhất, đã kiểm chứng trên dữ liệu thật của
`erptest.local`:

| Truy vấn | Kết quả |
|---|---|
| Số dòng SLE của hàng có lô mang `batch_no` | **0** |
| Số dòng SLE của hàng có lô mang `serial_and_batch_bundle` | **56** |

ERPNext v15 **không** ghi `batch_no` lên `Stock Ledger Entry` nữa (field còn đó nhưng bỏ
không). Số lô nằm ở các dòng con `Serial and Batch Entry` dưới `Serial and Batch Bundle`.

Nếu hook đọc `sle.batch_no` thì **toàn bộ 80/164 mặt hàng có lô sẽ ghi `so_lo = NULL`**,
gộp mọi lô của một mặt hàng vào chung một dòng — mà **báo cáo đối soát 8.4 vẫn báo "khớp"**
vì tổng số lượng vẫn đúng. FEFO ở GĐ 3 khi đó không còn gì để sắp theo hạn dùng. Đây đúng
là loại lỗi âm thầm mà thiết kế này lập ra để phòng.

**Quy tắc bắt buộc:** một dòng SLE có thể mang **nhiều lô** → hook ghi **N dòng sổ vị trí
trên mỗi dòng SLE**, không phải một.

```python
if sle.serial_and_batch_bundle:
    # dòng con đã có dấu sẵn: xuất là số âm; tổng qty == sle.actual_qty (đã kiểm chứng)
    dong = frappe.get_all("Serial and Batch Entry",
        filters={"parent": sle.serial_and_batch_bundle},
        fields=["batch_no", "qty"])
else:
    dong = [{"batch_no": sle.batch_no or None, "qty": delta}]
```

Hệ quả lan sang các mục khác:

- Sơ đồ luồng 4.5 chạy **một lần cho mỗi (lô, số lượng)**, không phải một lần cho mỗi SLE.
- `Location Allocation` (5.4) phân bổ theo **(dòng hàng, lô)**, không phải chỉ theo dòng hàng.
- Kiểm tra lớp sớm (4.6) đối chiếu tổng phân bổ **theo từng lô**, không phải tổng dòng hàng.

### 4.4 Định giá lại — không sinh sổ vị trí

`repost_current_voucher()` / `update_entries_after()` / `Repost Item Valuation` chỉ sửa
giá vốn và `qty_after_transaction`, **không tạo dòng SLE mới** → không ảnh hưởng tồn vị trí.
`Landed Cost Voucher` phải có bài kiểm thử riêng ở GĐ 1 để khẳng định không sinh sổ trùng
(xem mục 10, rủi ro R1).

### 4.5 Luồng của hook

```
SLE submit
 └─ kho có bật quản lý vị trí?  ── không ─→ bỏ qua
     └─ có
         ├─ tính delta thật (mục 4.3)
         ├─ chứng từ là bút toán huỷ?  ── có ─→ đảo đúng ô gốc (mục 4.2)
         └─ không
             ├─ chứng từ có bảng phân bổ vị trí, tổng khớp delta
             │      → ghi sổ vị trí theo từng dòng phân bổ
             ├─ delta > 0, không khai vị trí   → dồn vào ô `ZZZ-CHUA-XEP`
             └─ delta < 0, không khai vị trí   → tự chọn ô theo FEFO
                                                 (hạn gần nhất trước, rồi theo thứ tự lấy hàng)
                                                 không đủ → chặn, báo lỗi tiếng Việt
```

### 4.6 Kiểm tra hai lớp — vì sao không chỉ chặn ở hook

Hook chạy ở `on_submit` của SLE, tức là **sau khi người dùng đã bấm Ghi sổ**. Ném lỗi ở
đó thì Frappe cuộn ngược cả giao dịch — đúng về dữ liệu, nhưng người dùng chỉ thấy phiếu
bật lỗi sau khi đã điền xong, không biết sai từ đâu.

Nên kiểm tra **hai lớp**:

1. **Lớp sớm — `validate` của chứng từ.** Kiểm ngay khi lưu nháp: mỗi dòng hàng có phân bổ
   thì tổng số lượng phân bổ phải bằng số lượng dòng hàng (khớp theo từng lô); ô được chọn
   phải thuộc đúng kho; ô xuất phải đủ tồn. Đây là lớp người dùng thực sự nhìn thấy.
2. **Lớp chặn cuối — hook `on_submit` của SLE.** Là lưới an toàn cho các đường không đi qua
   giao diện (nhập liệu qua API, chứng từ không làm giao diện phân bổ, doctype ERPNext thêm
   về sau). Lỗi ở lớp này là lỗi hệ thống, phải ghi log đủ để truy được chứng từ nào gây ra.

Thông báo lỗi ở cả hai lớp đều phải là tiếng Việt đọc được, nêu rõ **ô nào, mặt hàng nào,
thiếu bao nhiêu** — không để lộ traceback.

## 5. Mô hình dữ liệu

App `miyano_wms`, module `Miyano WMS`. Tên doctype tiếng Anh, tên field tiếng Việt không
dấu, nhãn tiếng Việt — theo đúng quy ước đang dùng ở `miyano_portal`.

### 5.1 `Storage Location` — danh mục ô, mã 12 ký tự theo SPD

**Bảng phẳng, không phải cây.** `autoname: field:ma_o` → `name` chính là mã ô, nên link
field đọc được ngay và quét mã vạch ra thẳng bản ghi.

Mã ô theo `SPD_VanHanh_PhanTichMaViTriKho_20260907_v2` §5.2 — 12 ký tự, tự nó mang đủ
toạ độ:

```
[Kho 2][Khu 2][Dãy 2][Khoang 2][Tầng 2][Ô 2]

  K1   1B      01       04      03      02     →  K11B01040302
  kho  khu     dãy      khoang  tầng    ô

  in tem   K11B0104-0302   →  với tiền tố "VT " là đúng 16 ký tự, bằng giới hạn
                              trường F8 của đặc tả nhãn 50×30 v2
```

SPD đôi chỗ viết `K1-1B01-04-0302` cho dễ đọc bằng mắt. Đó chỉ là cách trình bày trong văn
bản, **không** phải một dạng hệ sinh ra — hệ chỉ có mã 12 ký tự liền và chuỗi in tem.

Miền giá trị: dãy / khoang / ô là `01`–`99`, tầng là `01`–`09`. Regex chặn cả miền giá
trị chứ không chỉ hình dạng — `00` hợp hình dạng nhưng vô nghĩa và sẽ lọt xuống tận tem
in. Một chỗ duy nhất định nghĩa quy tắc này: `vitri/ma_vi_tri.py` (`MAU_MA`,
`phan_tich_ma`, `dinh_dang_nhan`).

**Vì sao bỏ cây nested set.** Mã đã mã hoá sẵn cấp bậc, nên quan hệ cha–con chỉ là bản
sao thứ hai của cùng một sự thật — giữ lại chỉ tổ có hai nguồn lệch nhau. Mọi báo cáo gộp
theo Khu/Dãy đều làm được bằng cách gộp trên 6 trường thành phần.

| Field | Kiểu | Ghi chú |
|---|---|---|
| `ma_o` | Data | reqd, unique, 12 ký tự, khoá cứng sau khi tạo. Ví dụ `K11B01040302` |
| `ma_in_nhan` | Data, read_only | chuỗi in tem, ví dụ `K11B0104-0302` |
| `ten_o` | Data | tên mô tả, không bắt buộc |
| `kho` | Link Warehouse | reqd; phải là kho đã bật quản lý vị trí |
| `loai_vi_tri` | Select | `Lưu trữ` / `Soạn hàng` / `Cách ly` / `Trả hàng` |
| `ma_kho` `khu` `day` `khoang` `tang` `o` | Data, read_only | 6 thành phần tách từ mã — để lọc và gộp báo cáo |
| `barcode` | Data | mặc định = `ma_o`; dùng khi in tem và quét |
| `thu_tu_lay_hang` | Int | thứ tự đường đi trong kho — dùng để xếp gợi ý nhặt hàng |
| `suc_chua` / `suc_chua_dvt` | Float / Link UOM | sức chứa, để gợi ý đặt hàng |
| `cho_tron_mat_hang` | Check | default 1 |
| `cho_tron_lo` | Check | default 1 |
| `la_o_tran` | Check | khu tràn — ưu tiên thấp khi đặt hàng |
| `la_o_chua_xep` | Check, read_only | ô hệ thống; **mỗi kho đúng 1 ô**, không xoá được |
| `disabled` | Check | |

### 5.2 `Location Ledger Entry` — sổ vị trí (chỉ ghi thêm)

Nguồn sự thật. Không submittable, không ai tạo tay — chỉ hook sinh ra.

| Field | Kiểu | Ghi chú |
|---|---|---|
| `ngay` / `thoi_diem` | Date / Datetime | bám theo posting date/time của SLE |
| `kho` | Link Warehouse | |
| `o` | Link Storage Location | |
| `vat_tu` | Link Item | |
| `so_lo` | Link Batch | rỗng với hàng không lô |
| `so_luong` | Float | **có dấu** |
| `chung_tu_type` | Link DocType | |
| `chung_tu` | Dynamic Link | |
| `chung_tu_row` | Data | `voucher_detail_no` — khoá để đảo khi huỷ |
| `sle` | Link Stock Ledger Entry | dòng SLE sinh ra nó; dùng đối soát 1-1 |
| `da_huy` | Check | |
| `company` | Link Company | |

Index: `(kho, vat_tu, so_lo, o)`, `(chung_tu_type, chung_tu)`, `(sle)`.

### 5.3 `Location Balance` — bộ đệm tồn, dựng lại được

| Field | Kiểu |
|---|---|
| `o` / `kho` / `vat_tu` / `so_lo` | Link |
| `so_luong` | Float |
| `cap_nhat_luc` | Datetime |

Unique index `(o, vat_tu, so_lo)`. Có hàm `miyano_wms.ledger.dung_lai_ton_vi_tri()` dựng
lại toàn bộ từ sổ — bắt buộc phải có, đây là đường thoát khi nghi ngờ số liệu.

### 5.4 `Location Allocation` — bảng phân bổ (child table)

Gắn vào chứng từ ERPNext ở **cấp chứng từ cha**, không phải trên dòng hàng — vì một dòng
hàng có thể rải nhiều ô.

| Field | Kiểu | Ghi chú |
|---|---|---|
| `dong_hang` | Data | docname dòng hàng trên chứng từ (`voucher_detail_no`) |
| `vat_tu` | Link Item | read-only, để nhìn |
| `so_lo` | Link Batch | |
| `o` | Link Storage Location | reqd |
| `so_luong` | Float | reqd |

Thêm custom field `phan_bo_vi_tri` (Table) qua patch vào: `Purchase Receipt`,
`Purchase Invoice`, `Delivery Note`, `Sales Invoice`, `Stock Entry`,
`Stock Reconciliation`, `Subcontracting Receipt`.
**`Asset Capitalization` không làm giao diện** — để hàng rơi vào `ZZZ-CHUA-XEP`; nghiệp vụ này
hiếm và bất biến vẫn giữ nguyên.

### 5.5 `Item Location Preference` — ô cố định theo mặt hàng

`vat_tu`, `kho`, `o`, `la_o_chinh` (Check), `so_luong_toi_da` (Float).
Dùng cho gợi ý đặt hàng khi nhập kho.

### 5.6 `Location Transfer` — phiếu chuyển ô (submittable)

ERPNext **không nhìn thấy** việc chuyển ô (vẫn cùng một kho, tồn không đổi), nên bắt buộc
phải có chứng từ riêng. Bảng con `Location Transfer Item`: `vat_tu`, `so_lo`, `o_tu`,
`o_den`, `so_luong`. Submit ghi cặp dòng sổ ±. **Huỷ = ghi bút toán đảo, không xoá dòng.**

### 5.7 `Location Count` — kiểm kê theo ô (submittable)

Bảng con: `o`, `vat_tu`, `so_lo`, `so_luong_so_sach`, `so_luong_dem`.

- Lệch **do xếp nhầm** (tổng tồn kho vẫn đúng) → sinh `Location Transfer`.
- Lệch **tổng tồn kho** → **bắt buộc** đi qua `Stock Reconciliation` của ERPNext.
  Không cho sửa thẳng sổ vị trí — đây là chỗ dễ bị lách nhất và cũng là chỗ làm vỡ bất biến.

### 5.8 `Location Generator` — công cụ sinh mã ô hàng loạt

Tham số đúng bằng các chiều của mã SPD, **không còn mẫu mã tự do**: `kho`, `khu`,
`so_day`, `so_khoang_moi_day`, `so_tang_moi_khoang`, `so_o_moi_tang`. Hai ký tự mã kho
không nhập ở đây mà đọc từ `Warehouse.custom_ma_kho_spd`, để mọi ô của cùng một kho chắc
chắn cùng mã kho.

Giới hạn theo miền giá trị của mã: dãy ≤ 99, khoang ≤ 99, tầng ≤ 9, ô ≤ 99.

**Bắt buộc xem trước rồi mới ghi** — hiện bảng mã sẽ sinh, số lượng ô, cảnh báo trùng mã;
người dùng bấm xác nhận mới tạo. Ghi là all-or-nothing: chỉ cần một mã trùng thì không
tạo ô nào. Mã ô sai chuẩn là thứ về sau đổi rất đau vì tem đã in và người đã quen mã.

### 5.9 `Warehouse Location Setup` — bật quản lý vị trí cho kho chỉ định

Bật quản lý vị trí **không phải là tích một checkbox**. Nó là một quy trình chuyển đổi dữ
liệu: tạo ô `ZZZ-CHUA-XEP`, đọc tồn hiện có tách theo từng lô, ghi sổ chuyển đổi, dựng tồn vị
trí, rồi đối soát. Ai tích tay vào checkbox là bỏ qua sạch các bước đó và hệ sai ngay từ
giây đầu tiên.

Nên: **một doctype riêng, mỗi kho một bản ghi.** `autoname: field:kho`.

| Field | Kiểu | Ghi chú |
|---|---|---|
| `kho` | Link Warehouse | reqd, **unique**. Chỉ nhận warehouse **lá** (`is_group = 0`) |
| `trang_thai` | Select, read_only | `Chưa bật` / `Đang bật` / `Đã tắt` / `Cần đồng bộ lại` |
| `o_chua_xep` | Link Storage Location | read_only, do hệ tạo |
| `ngay_bat` / `ngay_tat` | Datetime | read_only |
| `so_dong_chuyen_doi` / `so_lo_chuyen_doi` | Int | read_only, kết quả lần chuyển đổi gần nhất |
| `lan_doi_soat_cuoi` / `ket_qua_doi_soat` | Datetime / Small Text | read_only |

**Custom field `custom_quan_ly_vi_tri` trên `Warehouse` chuyển thành `read_only`** — chỉ
doctype này được đặt. Đây là điểm chịu lực: không có đường tắt để bật.

#### Bốn thao tác

**1. Xem trước chuyển đổi** — liệt kê sẽ ghi bao nhiêu dòng sổ, bao nhiêu lô, cảnh báo
hàng không lô và tồn âm nếu có. **Không ghi gì cả.** Bắt buộc phải xem trước rồi mới bật
được (cùng nguyên tắc với `Location Generator` mục 5.8).

**2. Bật** — chạy trong **một giao dịch, được ăn cả ngã về không**:

```
kiểm tra: kho là lá, chưa bật, có Company
 → tạo ô `ZZZ-CHUA-XEP` cho kho (la_o_chua_xep = 1, không xoá được)
 → đọc tồn hiện có theo (mặt hàng, lô)   ← tách theo lô, xem 4.3b
 → ghi sổ chuyển đổi: MỘT dòng cho MỖI lô, vào ô `ZZZ-CHUA-XEP`
 → dựng Location Balance
 → chạy đối soát 8.4
     ├─ khớp   → đặt custom_quan_ly_vi_tri = 1, trang_thai = "Đang bật", ghi ngay_bat
     └─ lệch   → huỷ toàn bộ, báo rõ lệch ở đâu
```

Không có trạng thái "bật được một nửa". Bật hỏng thì kho quay về đúng như trước khi bấm.

**3. Tắt** — hook ngừng ghi sổ cho kho đó. **Sổ vị trí cũ giữ nguyên, không xoá dòng nào**
(cùng nguyên tắc chỉ-ghi-thêm của mục 3). `trang_thai = "Đã tắt"`.

Nhưng kho vẫn xuất nhập trong lúc tắt, nên tồn vị trí sẽ lệch dần so với `Bin`. Vì vậy:
**không cho bật thẳng lại từ trạng thái `Đã tắt`** — phải qua thao tác Đồng bộ lại. Đây là
cái bẫy chắc chắn sẽ có người dẫm vào nếu không chặn bằng máy.

**4. Đồng bộ lại** — so tồn vị trí với `Bin` theo từng (mặt hàng, lô); phần chênh dồn vào
`ZZZ-CHUA-XEP` bằng bút toán ghi thêm, **không sửa và không xoá dòng cũ**. Dùng cho hai tình
huống: bật lại sau khi tắt, và khi đối soát 8.4 báo lệch mà chưa rõ nguyên nhân.

#### Hook đọc trạng thái từ đâu

Hook (mục 4.5) hỏi `Warehouse.custom_quan_ly_vi_tri` qua `frappe.get_cached_value` — đọc
cache, không truy vấn thêm mỗi dòng SLE. Bật/tắt phải **xoá cache của Warehouse**, nếu
không thao tác bật sẽ không có hiệu lực cho tới lần khởi động lại kế tiếp và người vận
hành sẽ tưởng chức năng hỏng.

## 6. Luồng nghiệp vụ

### 6.1 Nhập kho (Purchase Receipt / Stock Entry Material Receipt)

Nút **"Gợi ý đặt hàng"** → theo thứ tự: ô cố định của mặt hàng (`Item Location Preference`)
→ ô đang chứa cùng mặt hàng và còn chỗ → ô trống → khu tràn. Thủ kho sửa được.
Không bấm gợi ý thì hàng vào `ZZZ-CHUA-XEP`, có báo cáo nhắc dọn.

### 6.2 Giao hàng — luồng chính, đúng yêu cầu chủ dự án

Trên `Delivery Note` (và `Sales Invoice` có update_stock) có nút **"Gợi ý lấy hàng"**:

1. Quét các ô đang có mặt hàng đó trong `Kho Miyano - MYN`
2. Xếp theo **hạn dùng gần nhất trước (FEFO)**, cùng hạn thì theo `thu_tu_lay_hang`
3. Điền sẵn bảng `phan_bo_vi_tri`; thủ kho sửa được nếu thực tế lấy chỗ khác
4. **Mẫu in phiếu giao hàng có thêm cột "Vị trí"** cho từng dòng hàng

Truy ngược được cả hai chiều: lô X đã lấy từ ô nào và giao cho ai; ô Y đã xuất những gì.

### 6.3 Chuyển ô, kiểm kê

Theo mục 5.6 và 5.7.

## 7. Phân quyền

Dùng lại vai trò sẵn có của ERPNext, **không đẻ vai trò mới**:

| Doctype | Stock Manager | Stock User |
|---|---|---|
| `Storage Location`, `Item Location Preference`, `Location Generator` | tạo/sửa/xoá | đọc |
| `Location Ledger Entry`, `Location Balance` | đọc | đọc |
| `Location Transfer`, `Location Count` | tạo/sửa/duyệt/huỷ | tạo/sửa/duyệt |

`Location Ledger Entry` **không có quyền tạo/sửa/xoá cho bất kỳ vai trò nào** — chỉ hook
ghi. Đây là điều giữ cho sổ đáng tin.

**Bắt buộc:** không doctype nào ở đây được có DocPerm cho vai trò `Customer` hay
`Website User`. Bài học từ kho khách hàng: thiếu DocPerm mới là thứ chịu lực, hook phân
quyền một mình không đủ.

## 8. Báo cáo

| Báo cáo | Nội dung |
|---|---|
| 8.1 Tồn kho theo vị trí | Gộp theo 6 thành phần của mã (Khu → Dãy → Khoang → Tầng → Ô), lọc theo mặt hàng/lô |
| 8.2 Ô trống và sức chứa còn lại | Phục vụ gợi ý đặt hàng và quy hoạch kho |
| 8.3 Hàng chưa xếp vị trí | Mọi thứ đang nằm ở `ZZZ-CHUA-XEP` — danh sách việc của thủ kho |
| 8.4 **Đối soát tồn vị trí ↔ tồn kho ERPNext** | So `Location Balance` với `Bin`. **Chạy tự động định kỳ + gọi tay được.** Lệch là báo. Đây là lưới an toàn của toàn hệ |
| 8.5 Truy vết lô theo vị trí | Lô X vào ô nào, ra khi nào, theo chứng từ nào |

Lưu ý vận hành: scheduler **đang tắt trên `erptest.local`**, nên 8.4 phải gọi tay được,
không chỉ dựa vào lịch chạy.

## 9. Chia giai đoạn

| GĐ | Nội dung | Kết quả nhìn thấy được |
|---|---|---|
| 0 | App `miyano_wms` + `Storage Location` + `Location Generator` + `Warehouse Location Setup` (bật/tắt/xem trước/đồng bộ lại) | Có sơ đồ kho trong hệ, bật được cho kho chỉ định |
| 1 | Sổ vị trí + tồn vị trí + hook SLE + báo cáo đối soát 8.4 | **Tồn theo ô đúng và tự bắt lệch** |
| 2 | Bảng phân bổ + giao diện nhập kho + gợi ý đặt hàng | Nhập hàng chỉ định được ô |
| **3** | **FEFO gợi ý lấy hàng trên DN/SI + cột Vị trí trên phiếu giao** | **Đúng yêu cầu của chủ dự án** |
| 4 | `Location Transfer` + `Location Count` | Kho tự vận hành trọn vẹn |
| 5 | In tem mã vạch vị trí + quét bằng điện thoại | Tuỳ chọn, chốt sau |

GĐ 1 là giai đoạn chịu lực. Không được rút gọn báo cáo đối soát 8.4 ra khỏi GĐ 1 — thiếu
nó thì các giai đoạn sau xây trên số liệu không ai kiểm chứng được.

## 10. Kiểm thử và rủi ro

### 10.1 Bộ kiểm thử bắt buộc

1. **Bất biến sau mỗi loại chứng từ** — 8 loại × 3 đường (ghi sổ / huỷ / sửa amend).
   Sau mỗi thao tác: tổng `Location Balance` phải bằng `Bin.actual_qty`.
2. **Kiểm kê hàng không lô** — cái bẫy ở mục 4.3. Đây là bài dễ quên nhất và hỏng âm thầm nhất.
3. **Huỷ phiếu giao trả hàng về đúng ô đã lấy**, không phải ô do FEFO chọn lại (mục 4.2).
4. **FEFO chọn đúng lô và đúng ô**, kể cả khi một mặt hàng nằm rải nhiều ô.
4b. **Số lô ghi đúng từ Serial and Batch Bundle** (mục 4.3b) — gồm bài một dòng SLE mang
   **nhiều lô** phải sinh nhiều dòng sổ vị trí. Bài này phải khẳng định `so_lo` khác NULL
   với hàng có lô; báo cáo đối soát 8.4 **không bắt được lỗi này** nên phải có bài riêng.
5. **Chuyển ô không làm đổi tồn ERPNext** — `Bin` phải y nguyên trước và sau.
6. **`dung_lai_ton_vi_tri()` dựng lại đúng** từ sổ sau khi cố tình phá bộ đệm.
7. **Xuất quá tồn của ô bị chặn**, thông báo tiếng Việt đọc được, không phải traceback.
8. **Bật quản lý vị trí trên kho đã có tồn** (mục 5.9): sau khi bật, đối soát 8.4 phải khớp
   **theo từng lô**, không chỉ khớp tổng.
9. **Bật thất bại thì không để lại dấu vết** — cố tình làm hỏng bước đối soát, kiểm tra kho
   quay về đúng như trước: không còn ô `ZZZ-CHUA-XEP`, không dòng sổ nào, checkbox vẫn tắt.
10. **Tắt rồi xuất nhập rồi bật lại** — phải bị chặn, bắt đi qua Đồng bộ lại; đồng bộ xong
   thì đối soát khớp.
11. **Kho không bật thì hook không ghi gì** — thao tác trên `Stores - MYN` không sinh dòng
   sổ vị trí nào.

### 10.2 Rủi ro đã biết

| # | Rủi ro | Xử lý |
|---|---|---|
| R1 | `Landed Cost Voucher` có thể sinh sổ vị trí trùng | **Chỉ là điều phải kiểm chứng, chưa có cách khắc phục định sẵn.** `via_landed_cost_voucher` là tham số Python của `make_sl_entries`, **không phải field trên SLE** → hook ở `on_submit` không đọc được. Bài kiểm thử ở GĐ 1 phải xác định LCV có sinh dòng SLE mới hay không rồi mới chọn cách xử lý |
| R2 | Chuyển ô ERPNext không thấy → báo cáo ERPNext và báo cáo vị trí kể hai câu chuyện khác nhau | Chấp nhận có chủ đích; báo cáo 8.5 truy vết được, và tổng luôn khớp |
| R3 | Người dùng bỏ qua bước khai vị trí | `ZZZ-CHUA-XEP` + báo cáo 8.3 làm việc bỏ sót thành hữu hình thay vì thành lỗi |
| R4 | Máy chỉ có 15Gi RAM, 3 bench chạy song song | Chạy cả bộ test sau mỗi task; phân biệt ReadTimeout do cạn RAM với hồi quy thật |

## 11. Cố ý KHÔNG làm (YAGNI)

- Không tối ưu đường đi nhặt hàng phức tạp — chỉ sắp theo `thu_tu_lay_hang`
- Không quản lý pallet / thùng / hộp như ba mức lồng nhau trong một ô
- Không chia sóng nhặt hàng (wave picking), không gom đơn
- Không làm app di động riêng ở GĐ 0–4
- Không bật quản lý vị trí cho kho nào khác ngoài `Kho Miyano - MYN` ở giai đoạn này — kiến trúc cho phép thêm kho bất cứ lúc nào bằng mục 5.9, nhưng không làm sẵn và không bật hàng loạt
- Không đụng tới sổ kho khách hàng của `miyano_portal`

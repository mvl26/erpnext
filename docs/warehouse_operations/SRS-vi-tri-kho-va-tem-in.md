# Đặc tả yêu cầu phần mềm (SRS) — Quản lý vị trí kho, nhập lô và tem in

Miyano ERP · module **Warehouse Operations** trong app `erpnext` (fork `mvl26/erpnext`)

| | |
|---|---|
| Mã tài liệu | SRS-VTK-01 |
| Phiên bản | 1.0 |
| Ngày | 18/09/2026 |
| Chuẩn trình bày | ISO/IEC/IEEE 29148:2018, mục 9.5 (nội dung SRS) |
| Mốc mã nguồn được đặc tả | nhánh `feat/mo-rong-vi-tri-kho-warehouse`, commit `8b1ccdea` (18/09/2026) |
| Trạng thái | Đặc tả **hiện trạng đã xây** (as-built), chờ chủ đầu tư duyệt |

> **Cách đọc tài liệu này.** Đây là đặc tả của hệ **đang chạy**, dựng lại từ mã nguồn,
> các bản thiết kế và các quyết định đã chốt. Khi tài liệu cũ nói khác mã, tài liệu này theo
> **mã**, và ghi chỗ khác biệt vào Phụ lục C. Mỗi yêu cầu có mã riêng để truy vết tới mã nguồn
> và bài kiểm thử (Phụ lục A).

---

## 1. Giới thiệu

### 1.1 Mục đích

Tài liệu đặc tả các chức năng đã thêm mới và sửa đổi trong ERPNext để quản lý **vị trí vật lý
của hàng trong kho** (khu, dãy, khoang, tầng, ô), **khai số lô khi nhập kho**, **in tem vị trí
và nhãn lô**, và **quét mã tra cứu / xếp hàng trên PDA**.

Người đọc:

| Người đọc | Dùng tài liệu để |
|---|---|
| Chủ đầu tư, quản lý kho | duyệt phạm vi và các quy tắc nghiệp vụ đã chốt |
| Lập trình viên bảo trì | biết điều gì là bất biến, điều gì không được "sửa cho gọn" |
| Kiểm thử / nghiệm thu | lấy tiêu chí nghiệm thu cho từng yêu cầu |
| Người triển khai lên site thật `miyano` | biết điều kiện triển khai và các rủi ro đã biết |

### 1.2 Phạm vi

**Trong phạm vi tài liệu này:**

1. **Nền tảng vị trí kho** — mã ô 10 ký tự, cây vị trí, sinh ô hàng loạt, bật/tắt/đồng bộ quản
   lý vị trí cho từng kho, sổ vị trí ghi tự động theo chứng từ kho, đối soát, bốn báo cáo.
2. **Nhập lô và xếp hàng** — phiếu nhập lô (khai số lô nhà cung cấp), chặn lô gõ tay khi duyệt
   phiếu nhập, gán vị trí cố định cho mặt hàng, gợi ý ô, phiếu xếp / chuyển vị trí, trang xếp
   hàng trên PDA.
3. **Tem và nhãn in** — tem vị trí dán kệ (45×25 mm và 50×30 mm), nhãn lô 50×30 mm dán lên hàng,
   trang quét mã tra cứu.

**Ngoài phạm vi (đặc tả ở tài liệu riêng):**

- Lấy hàng trên PDA, bảng phân bổ vị trí trên phiếu giao (`Location Allocation`), trang
  `lay-hang-pda`. Tài liệu này chỉ mô tả **giao diện** giữa nền tảng và phần đó (VTK-SO-07).
- Quy tắc chọn ô khi xuất theo hạn dùng (FEFO, `vitri/fefo.py`) — chỉ mô tả ở mức hành vi mà
  nền tảng dựa vào (VTK-SO-06).
- Kiểm kê theo ô (`Location Count`), báo cáo sức chứa ô, lịch đối soát tự động — **chưa làm**.

### 1.3 Tài liệu tham chiếu và thứ tự thẩm quyền

Khi hai nguồn nói khác nhau, nguồn đứng trên thắng:

| # | Nguồn | Vai trò |
|---|---|---|
| 1 | Mã nguồn tại commit `8b1ccdea` | hành vi thật của hệ |
| 2 | Quyết định của chủ đầu tư ghi trong `QUYET-DINH-thi-cong-cay-vi-tri.md`, `QUYET-DINH-thi-cong-khoi-C.md` và docstring mã | lý do của các quy tắc |
| 3 | Thiết kế trong `docs/superpowers/specs/`: `2026-09-09-miyano-wms-vi-tri-kho-design`, `2026-09-11-cay-vi-tri-ma-10-ky-tu-design`, `2026-09-14-phieu-xep-chuyen-vi-tri-design`, `2026-09-15-gan-vi-tri-co-dinh-theo-mat-hang-design`, `2026-09-16-nhap-lo-in-nhan-quet-ma-design` | ý định thiết kế (một số mục đã bị thay thế — xem Phụ lục C) |
| 4 | `SPD_VanHanh_PhanTichMaViTriKho_20260907_v2.docx` §5 | chuẩn mã vị trí của khách hàng |
| 5 | `HDSD-quan-ly-vi-tri-kho.md`, `HDSD-luong-tu-A-den-Z.md`, `BAN-GIAO-nen-tang-vi-tri-kho.md` | hướng dẫn người dùng và bàn giao kỹ thuật |

`SPD_PhanMem_QuyTacMaHoaNhan_20260908_v1` mô tả mã 11 ký tự không có Khoang — **đã lỗi thời**,
không dùng làm căn cứ.

### 1.4 Thuật ngữ và viết tắt

| Thuật ngữ | Nghĩa |
|---|---|
| **Ô** (ô lá) | vị trí thấp nhất trên kệ, nơi duy nhất chứa hàng; mã đủ 10 ký tự |
| **Nút nhóm** | cấp Khu, Dãy, Khoang, Tầng; mã 2/4/6/8 ký tự; không chứa hàng |
| **Nhánh** | một nút cùng mọi nút con cháu của nó trong cây vị trí |
| **Ô "Chưa xếp vị trí"** | ô hệ thống `ZZZ-CHUA-XEP-<tên kho>`, mỗi kho đúng một ô, nhận mọi hàng chưa biết vị trí |
| **Sổ vị trí** | doctype `Location Ledger Entry` — chỉ ghi thêm, là nguồn sự thật |
| **Tồn vị trí** | doctype `Location Balance` — bộ đệm dẫn xuất từ sổ, dựng lại được |
| **Bất biến tồn** | với mọi (mặt hàng, lô, kho có quản lý vị trí): tổng tồn các ô = tồn kho ERPNext |
| **Phiếu nhập lô** | doctype `Batch Entry` — khai số lô nhà cung cấp cho các dòng phiếu nhập |
| **Phiếu xếp** | doctype `Location Transfer` — chuyển hàng giữa hai ô trong cùng kho |
| **Gán vị trí cố định** | doctype `Item Location Preference` — một mặt hàng thuộc một nút |
| **Số gọi** | số 4 chữ số cấp cho từng lô, in to trên nhãn để gọi miệng trong kho |
| **Ô in trên tem** | `Batch.custom_o_in_tem` — ô đã in lên nhãn lô và đang dán trên thùng |
| **SLE** | `Stock Ledger Entry` — dòng sổ kho của ERPNext |
| **Bundle** | `Serial and Batch Bundle` — nơi ERPNext v15 lưu số lô của một dòng SLE |
| **Module (mã vạch)** | đơn vị bề rộng nhỏ nhất của Code 128; ở đây 1 module = 0,25 mm = 2 dot |
| **Vùng yên tĩnh** | khoảng trắng bắt buộc hai đầu mã vạch Code 128, ≥ 10 module |
| **PDA** | máy cầm tay có súng quét, chạy trình duyệt |
| SM / StM / SU | vai trò `System Manager` / `Stock Manager` / `Stock User` |

### 1.5 Quy ước yêu cầu

- Mỗi yêu cầu có mã `VTK-<nhóm>-<số>`. Nhóm: `MA` mã ô, `CAY` cây vị trí, `DM` danh mục ô,
  `KHO` bật kho, `SO` sổ vị trí, `DS` đối soát, `BC` báo cáo, `XEP` phiếu xếp, `GAN` gán vị trí,
  `GY` gợi ý ô, `LO` nhập lô, `TVT` tem vị trí, `TL` nhãn lô, `QUET` quét tra cứu, `PDA` xếp
  hàng trên PDA, `QH` phân quyền, `NF` phi chức năng.
- **PHẢI** = bắt buộc, đã thực hiện. **KHÔNG ĐƯỢC** = cấm, đã chặn bằng mã. **NÊN** = khuyến nghị
  vận hành, phần mềm không cưỡng chế.
- Cột **Kiểm chứng** ghi **phương pháp** kiểm chứng (ISO/IEC/IEEE 29148 §9.6), không phải
  trạng thái đã kiểm:
  - `T` — kiểm thử tự động; tên module là bài test **đã có** trong `erpnext/warehouse_operations/tests/`
    tại commit mốc.
  - `I` — soát mã; người viết tài liệu này đã đọc đoạn mã tương ứng.
  - `D` — trình diễn trên trình duyệt; **phải làm khi nghiệm thu** (NT-06), trừ khi có ghi nguồn
    của một lần chạy thật.
  - `A` — phân tích / đo; số đo nào lấy từ tài liệu khác thì có ghi nguồn.

---

## 2. Mô tả tổng quan

### 2.1 Bối cảnh

Trước khi có module này, tồn kho Miyano chỉ biết tới cấp **kho**. Yêu cầu gốc của chủ đầu tư
(09/09/2026): *"khi giao hàng anh cũng muốn biết lấy từ kho và vị trí nào chứ không phải lấy từ
mỗi kho như bây giờ"*.

Chủ đầu tư chọn **phương án B**: vị trí là một chiều dữ liệu riêng (doctype riêng + sổ riêng),
**không** biến ô kệ thành `Warehouse` con. Phương án này được chọn có ý thức sau hai lần cảnh
báo về khối lượng, vì chiều vị trí sẽ được dùng lại cho các phần khác. Không mở lại quyết định
này.

Module nằm **trong app `erpnext`** (thư mục `erpnext/warehouse_operations/`), không phải app riêng — vì
đây là phần mở rộng của `Warehouse`. Mã upstream chỉ bị chèn ở các điểm liệt kê tại VTK-NF-20.

```
                   Chứng từ kho ERPNext (PR, DN, SE, SR, PI, SI, …)
                                 │  mọi SLE đi qua make_entry() → sle.submit()
                                 ▼
          ┌──────── hook Stock Ledger Entry.on_submit ────────┐
          │  kho có bật vị trí?  không → bỏ qua                │
          │  huỷ?  → đảo đúng ô gốc                            │
          │  nhập  → ô "Chưa xếp vị trí"                       │
          │  xuất  → theo phân bổ đã quét, không có thì FEFO   │
          └──────────────────────┬────────────────────────────┘
                                 ▼
     Location Ledger Entry (sổ, chỉ ghi thêm) ──► Location Balance (bộ đệm)
                                 ▲                         │
     Location Transfer (phiếu xếp, KHÔNG sinh SLE) ────────┤
                                                           ▼
                        đối soát với Bin + Serial and Batch Entry của ERPNext
```

### 2.2 Chức năng chính

| Nhóm | Chức năng |
|---|---|
| Thiết lập | sinh ô hàng loạt · bật / tắt / đồng bộ lại quản lý vị trí cho một kho · gán vị trí cố định cho mặt hàng |
| Vận hành hằng ngày | nhập lô từ phiếu nhập · in nhãn lô · xếp hàng vào ô (máy tính hoặc PDA) · quét mã tra cứu · in lại tem |
| Tự động | ghi sổ vị trí cho mọi chứng từ kho · đảo đúng ô khi huỷ · gợi ý ô khi xếp · chặn duyệt phiếu nhập có lô gõ tay |
| Kiểm soát | đối soát ba phép đo · bốn báo cáo · phân quyền theo vai trò kho |

### 2.3 Người dùng

| Người dùng | Vai trò hệ thống | Việc chính |
|---|---|---|
| Quản trị / quản lý kho | SM, StM | sinh ô, bật kho, gán vị trí cố định, đồng bộ lại, xem đối soát |
| Thủ kho | SU | nhập lô, in nhãn, in lại tem, xếp hàng, quét tra cứu |
| Mua hàng / kế toán kho | theo quyền ERPNext gốc | lập và duyệt phiếu nhập |
| Khách hàng cổng (`Website User`) | — | **không truy cập được bất kỳ phần nào** của module |

### 2.4 Môi trường vận hành

| Thành phần | Giá trị |
|---|---|
| Nền tảng | Frappe 15.113.4, ERPNext 15.83.0 (fork `mvl26/erpnext`), MariaDB/InnoDB |
| Site thử | `erptest.local` (`http://192.168.61.129:8003`) — đã bật `Kho Miyano - MYN` |
| Site thật | `miyano` (máy khác) — **chưa cài** module |
| Máy in tem | Zebra ZD421, 203 dpi (8 dot/mm), cuộn tem 45×25 mm và 50×30 mm |
| PDA / điện thoại | trình duyệt Chrome; súng quét giả lập bàn phím (có hoặc không gửi Enter); camera |
| Ký hiệu mã vạch | Code 128 |

### 2.5 Ràng buộc thiết kế

| Mã | Ràng buộc |
|---|---|
| RB-01 | Không sửa `erpnext/stock/utils.py::scan_barcode`, `batch.py`, `stock_controller.py`, `serial_no_batch_selector.js`. Mở rộng qua `hooks.py` và `doctype_js` |
| RB-02 | Tên doctype tiếng Anh, tên trường tiếng Việt không dấu, nhãn tiếng Việt |
| RB-03 | Mọi thông báo cho người dùng bằng tiếng Việt, nêu đích danh đối tượng lỗi; không lộ traceback |
| RB-04 | Chỉ dùng vai trò có sẵn của ERPNext, không tạo vai trò mới |
| RB-05 | Tài liệu nằm ở `docs/` gốc repo; `.docx`/`.zip` không được nằm dưới `erpnext/` (cổng `scripts/file_structure/gate.py`) |
| RB-06 | Không đưa JS tem vào bundle hay `app_include_js`; nạp bằng `frappe.require` khi cần |

### 2.6 Giả định và phụ thuộc

| Mã | Giả định |
|---|---|
| GD-01 | ERPNext v15 lưu số lô ở `Serial and Batch Bundle`, **không** ở `SLE.batch_no` (đã đo: 0/56 dòng SLE hàng có lô mang `batch_no`) |
| GD-02 | Mọi chứng từ ghi sổ kho đều tạo SLE qua `stock_ledger.make_entry()` → `sle.submit()`, kể cả dòng đảo khi huỷ |
| GD-03 | Mặt hàng có lô đặt **"không tự sinh lô"** (`create_new_batch = 0`). Bật ô này làm ERPNext tự đặt số lô máy khi duyệt phiếu nhập |
| GD-04 | `Stock Settings` → *Pick Serial / Batch Based On* đang là `FIFO`: ERPNext chọn **lô** theo thứ tự nhập; module chỉ chọn **ô** trong lô đó. Đổi sang `Expiry` là quyết định của công ty |
| GD-05 | `Stock Settings` → *Default Warehouse* phải trỏ tới kho đúng công ty. Nếu trỏ vào kho không quản lý vị trí, chứng từ mới sẽ tự điền kho đó và không sinh dòng sổ vị trí nào |
| GD-06 | Scheduler đang tắt trên `erptest.local`; đối soát chỉ chạy khi gọi tay |

---

## 3. Yêu cầu cụ thể

### 3.1 Giao diện ngoài

#### 3.1.1 Màn hình

| Màn hình | Đường dẫn | Loại |
|---|---|---|
| Trang tổng hợp **Vị trí kho** | `/app/vị-trí-kho` | Workspace |
| Quét mã tra cứu | `/app/quet-ma-tra-cuu` | Page (PDA) |
| Xếp hàng vào ô | `/app/xep-hang-pda` | Page (PDA) |
| Danh mục ô (dạng bảng và dạng cây) | `/app/storage-location`, `/app/storage-location/view/tree` | DocType |
| Sinh mã ô | `/app/location-generator` | DocType |
| Bật quản lý vị trí | `/app/warehouse-location-setup` | DocType |
| Gán vị trí cố định | `/app/item-location-preference` | DocType |
| Phiếu nhập lô | `/app/batch-entry` | DocType, duyệt được |
| Phiếu xếp / chuyển vị trí | `/app/location-transfer` | DocType, duyệt được |
| Sổ vị trí, tồn vị trí | `/app/location-ledger-entry`, `/app/location-balance` | DocType, chỉ đọc |
| 4 báo cáo | `/app/query-report/<tên>` | Query Report |

Phần mở rộng gắn vào form ERPNext có sẵn (qua `doctype_js`):

| Form | Thêm gì |
|---|---|
| `Warehouse` | nhóm nút **Vị trí kho**: Bật quản lý vị trí · Ô kệ của kho · 3 báo cáo · Thiết lập vị trí |
| `Item` | dòng thông báo vị trí cố định đầu form · nhóm nút **Vị trí kho → Gán / Đổi vị trí** |
| `Purchase Receipt` | nút **Nhập lô & in nhãn** (phiếu nháp) · nút **Xem phiếu nhập lô** (phiếu đã duyệt) |
| `Batch` | nút **In nhãn** |

#### 3.1.2 Phần cứng

- **Máy in nhiệt 203 dpi**: tem in qua hộp thoại in của trình duyệt, mỗi tem một trang, tỉ lệ
  100%, không "Fit to page".
- **Súng quét**: gõ ký tự vào ô đang focus như bàn phím, có thể kèm hoặc không kèm Enter.
- **Camera**: quét bằng `frappe.ui.Scanner` khi không có súng quét.

#### 3.1.3 Giao diện phần mềm

| Điểm móc | Loại | Hàm |
|---|---|---|
| `Stock Ledger Entry.on_submit` | `doc_events` | `vitri.hook_sle.ghi_so_vi_tri` |
| `Batch.before_insert` | `doc_events` | `vitri.lo_ncc.dien_ncc_tu_chung_tu` |
| `Batch.validate` | `doc_events` | `vitri.ma_vach.kiem_ky_tu_lo` |
| `Purchase Receipt.before_submit` | `doc_events` | `vitri.phieu_nhap.chan_lo_go_tay_khi_duyet` |
| `Item.after_rename` | `doc_events` | `vitri.gan.doi_ten_theo_mat_hang` |
| `after_migrate` | hook | `vitri.cay.dam_bao_cay_da_dung` |
| `PurchaseReceipt.on_cancel` | sửa lõi, 1 dòng | thêm `"Batch Entry"` vào `ignore_linked_doctypes` |

Phần lấy hàng (ngoài phạm vi) có thêm móc riêng trên `Delivery Note`; không liệt kê ở đây.

#### 3.1.4 Giao diện gọi từ xa (whitelist)

Mọi hàm dưới đây **PHẢI** tự kiểm vai trò (VTK-QH-02); đăng nhập hợp lệ không đủ.

| Hàm | Vai trò | Ghi dữ liệu |
|---|---|---|
| `bat_kho.xem_truoc`, `bat`, `tat`, `dong_bo_lai` | SM, StM | `bat`/`tat`/`dong_bo_lai` có |
| `sinh_ma.xem_truoc_sinh`, `sinh` | SM, StM | `sinh` có |
| `tem.danh_sach_tem` | SM, StM, SU | không |
| `xep.hang_chua_xep`, `phieu_xep_dang_lam`, `quet_de_xep` | SM, StM, SU | không |
| `xep.them_dong_xep`, `xoa_dong_xep`, `duyet_phieu_xep` | SM, StM, SU + DocPerm | có |
| `gan.cay_chon_vi_tri` | SM, StM, SU | không |
| `gan.vi_tri_cua_mat_hang` | quyền đọc `Item` | không |
| `gan.gan_vi_tri_cho_mat_hang` | DocPerm `Item Location Preference` | có |
| `nhap_lo.lay_dong_tu_phieu_nhap`, `du_lieu_tem` | SM, StM, SU | không |
| `nhap_lo.dat_o_in_tem` | SM, StM, SU | có (một lần mỗi lô) |
| `phieu_nhap.chan_doan_phieu_nhap` | quyền đọc phiếu nhập | không |
| `quet.tra_cuu` | SM, StM, SU | không |

---

### 3.2 Yêu cầu chức năng

#### 3.2.1 Mã ô — VTK-MA

| Mã | Yêu cầu | Kiểm chứng |
|---|---|---|
| VTK-MA-01 | Mã ô lá **PHẢI** dài đúng 10 ký tự, không dấu gạch, theo thứ tự `[Khu 2][Dãy 2][Khoang 2][Tầng 2][Ô 2]`, ví dụ `1B01040302` | T `test_ma_vi_tri` |
| VTK-MA-02 | Khu **PHẢI** là 1 chữ số rồi 1 chữ cái in hoa (`1B`, `3B`). Dãy, Khoang, Ô nhận `01`–`99`; Tầng nhận `01`–`09` (đếm từ dưới lên). `00` bị chặn | T `test_ma_vi_tri` |
| VTK-MA-03 | Mã nút nhóm **PHẢI** là tiền tố 2/4/6/8 ký tự của mã ô lá; mã cha **PHẢI** bằng mã con bỏ 2 ký tự cuối | T `test_ma_vi_tri` |
| VTK-MA-04 | Mã sai chuẩn **PHẢI** bị từ chối với thông báo nêu mã sai, dạng đúng và ví dụ | T `test_ma_vi_tri` |
| VTK-MA-05 | Hệ **PHẢI** sinh "mã in trên nhãn" dạng `1B0104-0302` (một gạch trước Tầng+Ô) cho ô lá; nút nhóm không có mã in | T `test_ma_vi_tri`, `test_storage_location` |
| VTK-MA-06 | Mã ô **PHẢI** duy nhất trên **toàn hệ**, không riêng từng kho (mã không chứa mã kho). Ký hiệu Khu **NÊN** được cấp phát toàn công ty trước khi sinh ô | T `test_storage_location` |
| VTK-MA-07 | Mã ô **KHÔNG ĐƯỢC** sửa sau khi tạo; đổi mã = tạo ô mới rồi ngừng dùng ô cũ. Mã đã dùng **NÊN** không cấp lại (SPD §5.3) | T `test_storage_location` |
| VTK-MA-08 | Ô "Chưa xếp vị trí" (`ZZZ-CHUA-XEP-<kho>`) **PHẢI** được miễn kiểm định dạng. Tiền tố `ZZZ` để ô này luôn đứng cuối thứ tự chữ cái | T `test_storage_location` |

*Lý do bỏ 2 ký tự mã kho (11/09/2026):* kho đã có ở trường `kho`; lưu cả trong mã là hai nguồn sự
thật. Hệ quả là VTK-MA-06.

#### 3.2.2 Cây vị trí — VTK-CAY

| Mã | Yêu cầu | Kiểm chứng |
|---|---|---|
| VTK-CAY-01 | `Storage Location` **PHẢI** là cây nested set 5 cấp Khu → Dãy → Khoang → Tầng → Ô | T `test_cay_vi_tri` |
| VTK-CAY-02 | Nút cha và cờ `is_group` **PHẢI** được tính lại từ mã ở mỗi lần lưu và ghi đè mọi giá trị đặt tay (qua API, Data Import). Trường "Thuộc" chỉ đọc | T `test_cay_vi_tri` |
| VTK-CAY-03 | Lưu một ô lá khi chưa có nút cha **PHẢI** tự tạo đủ các nút cha còn thiếu, từ gốc xuống | T `test_cay_vi_tri` |
| VTK-CAY-04 | Nếu nút cha đã tồn tại nhưng thuộc kho khác, lưu **PHẢI** bị chặn, báo nút nào thuộc kho nào | T `test_storage_location` |
| VTK-CAY-05 | Chỉ ô lá được giữ hàng. Ghi sổ vào nút nhóm **PHẢI** bị chặn ở tầng ghi sổ | T `test_cay_vi_tri` |
| VTK-CAY-06 | Ô "Chưa xếp vị trí" **PHẢI** đứng ngoài cây (gốc riêng, không cha, không con) | T `test_cay_vi_tri` |
| VTK-CAY-07 | "Ngừng dùng" **PHẢI** thừa kế xuống cả nhánh: một ô coi như ngừng dùng nếu chính nó hoặc bất kỳ tổ tiên nào ngừng dùng. Luật này có đúng một định nghĩa SQL (`fefo._dieu_kien_ngung_dung`), mọi nơi khác gọi lại | T `test_cay_vi_tri`, `test_fefo` |
| VTK-CAY-08 | `thu_tu_lay_hang` **KHÔNG** thừa kế | I |
| VTK-CAY-09 | Mỗi lần `bench migrate`, hệ **PHẢI** dựng lại `lft`/`rgt` nếu còn bản ghi thiếu toạ độ. Nhánh "không có việc" **PHẢI** thoát sau đúng một câu đếm | T `test_storage_location` (`TestDamBaoCayDaDung`), `test_app_khoi_dong` |
| VTK-CAY-10 | Nếu còn ô đang ngừng dùng, việc dựng cây **PHẢI** bị hoãn (không chặn migrate), ghi cảnh báo vào console và Error Log kèm lệnh chạy tay | T `test_storage_location` (`TestDamBaoCayDaDung`) |
| VTK-CAY-11 | Bản ghi có cha không tồn tại **PHẢI** được liệt kê đích danh trong log; lỗi của `rebuild_tree` **KHÔNG ĐƯỢC** làm vỡ `bench migrate`; cờ `auto_commit_on_many_writes` **PHẢI** được trả về 0 dù thành công hay lỗi | T `test_storage_location` (`TestDamBaoCayDaDung`) |
| VTK-CAY-12 | Mọi phép tính theo nhánh (in tem, gán, gợi ý, phạm vi lấy hàng) **PHẢI** từ chối nút có `lft = rgt = 0` với thông báo tường minh, không được lặng lẽ khớp mọi bản ghi 0/0 | T `test_tem`, `test_gan_vi_tri`, `test_goi_y_o`, `test_fefo_pham_vi` |

#### 3.2.3 Danh mục ô và sinh mã hàng loạt — VTK-DM

| Mã | Yêu cầu | Kiểm chứng |
|---|---|---|
| VTK-DM-01 | Mỗi ô **PHẢI** thuộc một kho lá; kho tổng (`is_group`) bị chặn | T `test_storage_location` |
| VTK-DM-02 | Ô lá **PHẢI** tự tách và lưu 5 thành phần chỉ đọc (Khu, Dãy, Khoang, Tầng, Ô); nút nhóm chỉ điền phần nó có | T `test_storage_location` |
| VTK-DM-03 | Trường **Mã vạch** trống thì **PHẢI** lấy bằng mã ô; khác rỗng thì duy nhất | T `test_storage_location` |
| VTK-DM-04 | **Loại vị trí** chỉ có "Lưu trữ" và "Soạn hàng". "Cách ly"/"Trả hàng" đã bị bỏ vì không nơi nào đọc chúng (nhãn an toàn giả). Cách ly thật **NÊN** là một `Warehouse` riêng. Patch `don_loai_vi_tri_khong_hop_le` đặt giá trị cũ về "Lưu trữ" | T `test_storage_location` |
| VTK-DM-05 | Ô "Chưa xếp vị trí" **KHÔNG ĐƯỢC** đặt "Ngừng dùng" và **KHÔNG ĐƯỢC** xoá | T `test_co_quan_ly_vi_tri`, `test_storage_location` |
| VTK-DM-06 | Xoá một nút còn con **PHẢI** bị chặn (NestedSet) | T `test_cay_vi_tri` |
| VTK-DM-07 | **Sinh mã ô** nhận: Kho, Khu, Số dãy (1–99), Số khoang mỗi dãy (1–99), Số tầng mỗi khoang (1–9), Số ô mỗi tầng (1–99). Ngoài khoảng **PHẢI** bị từ chối | T `test_sinh_ma` |
| VTK-DM-08 | Trước khi ghi, người dùng **PHẢI** xem được số ô sẽ tạo và tối đa 20 mã ví dụ. Bước xem trước không ghi gì | T `test_sinh_ma`, D |
| VTK-DM-09 | Có **bất kỳ** mã trùng nào thì **KHÔNG ĐƯỢC** tạo ô nào (tất cả hoặc không), báo số mã trùng và tối đa 5 ví dụ | T `test_sinh_ma` |
| VTK-DM-10 | Bộ sinh **PHẢI** tạo nút nhóm trước (từ gốc xuống), rồi ô lá theo thứ tự dãy → khoang → tầng → ô, đánh `thu_tu_lay_hang` 1, 2, 3… theo thứ tự đó | T `test_sinh_ma` |
| VTK-DM-11 | Không có mẫu mã tự do: bộ sinh chỉ sinh đúng chuẩn 10 ký tự | I |

#### 3.2.4 Bật, tắt, đồng bộ quản lý vị trí cho kho — VTK-KHO

Trạng thái của hồ sơ `Warehouse Location Setup` (mỗi kho một bản ghi, tên = tên kho):

```
 Chưa bật ──[Xem trước → xác nhận = Bật]──► Đang bật ──[Tắt]──► Đã tắt
                                               ▲                    │
                                               └────[Đồng bộ lại]───┘
                           Đang bật ──[Đồng bộ lại]──► Đang bật
```

| Mã | Yêu cầu | Kiểm chứng |
|---|---|---|
| VTK-KHO-01 | Cờ `Warehouse.custom_quan_ly_vi_tri` **PHẢI** chỉ đọc trên form; chỉ các thao tác của module này được đặt | T `test_co_quan_ly_vi_tri` |
| VTK-KHO-02 | Không có nút "Bật" riêng: bật **PHẢI** đi qua **Xem trước chuyển đổi** rồi xác nhận | D |
| VTK-KHO-03 | Xem trước **PHẢI** nêu số dòng sổ sẽ ghi, số mặt hàng, số lô; cảnh báo số dòng hàng không lô và số dòng tồn âm (bật sẽ thất bại). Không ghi gì | T `test_bat_kho_xem_truoc` |
| VTK-KHO-04 | Bật **PHẢI** chạy trong một giao dịch có savepoint: tạo ô "Chưa xếp vị trí" (thứ tự lấy hàng 9999) → ghi **một dòng sổ cho mỗi (mặt hàng, lô)** của tồn hiện có vào ô đó → dựng lại tồn vị trí → đối soát. Đối soát lệch thì huỷ sạch, kho về đúng như trước | T `test_bat_kho` |
| VTK-KHO-05 | Tồn hiện có **PHẢI** đọc theo đúng nguồn của đối soát (`doi_soat.ton_kho_theo_lo`): tổng theo `Bin`, chia lô theo `Serial and Batch Entry`, phần dư vào ngăn không lô | T `test_bat_kho`, `test_doi_soat` |
| VTK-KHO-06 | Bật thành công **PHẢI** đặt cờ kho = 1, xoá cache `Warehouse`, ghi trạng thái "Đang bật", thời điểm bật, số dòng, số lô, kết quả đối soát | T `test_bat_kho` |
| VTK-KHO-07 | Chặn bật khi: kho không tồn tại, kho tổng, kho đã bật, hoặc kho đang "Đã tắt"/"Cần đồng bộ lại" (phải qua Đồng bộ lại) | T `test_bat_kho`, `test_tat_va_dong_bo` |
| VTK-KHO-08 | Tắt **PHẢI** đặt cờ = 0, trạng thái "Đã tắt", giữ nguyên toàn bộ sổ | T `test_tat_va_dong_bo` |
| VTK-KHO-09 | Đồng bộ lại chỉ chạy được khi trạng thái là "Đang bật", "Đã tắt" hoặc "Cần đồng bộ lại" (danh sách cho phép). Nó ghi **bút toán bù** (không sửa, không xoá dòng cũ) vào ô "Chưa xếp vị trí" cho từng (mặt hàng, lô) lệch, rồi đối soát lại | T `test_tat_va_dong_bo` |
| VTK-KHO-10 | Nếu sau khi bù vẫn còn ô âm hoặc lệch bộ đệm, Đồng bộ lại **PHẢI** báo lỗi nêu rõ loại lệch, **KHÔNG ĐƯỢC** báo "khớp". Khi đó dùng `so.dung_lai_ton_vi_tri(kho)` (chạy bằng `bench execute`) | T `test_tat_va_dong_bo` |
| VTK-KHO-11 | Đồng bộ lại thành công **PHẢI** bật lại cờ và cập nhật hồ sơ bằng số liệu của chính lần đồng bộ đó | T `test_tat_va_dong_bo` |
| VTK-KHO-12 | Hook ghi sổ **PHẢI** đọc cờ kho từ cache; mọi thao tác đổi cờ **PHẢI** xoá cache | T `test_co_quan_ly_vi_tri` |
| VTK-KHO-13 | Không hard-code tên kho ở bất kỳ đâu; thêm kho mới = chạy lại quy trình bật | I |

#### 3.2.5 Sổ vị trí và ghi sổ tự động — VTK-SO

| Mã | Yêu cầu | Kiểm chứng |
|---|---|---|
| VTK-SO-01 | Sổ vị trí **PHẢI** chỉ ghi thêm. Không vai trò nào có quyền tạo/sửa/xoá; xoá một dòng sổ **PHẢI** bị chặn tuyệt đối | T `test_so_vi_tri`, `test_phan_quyen` |
| VTK-SO-02 | Mỗi dòng sổ **PHẢI** mang: ngày, thời điểm, kho, ô, mặt hàng, lô (chuỗi rỗng nếu không lô, không bao giờ NULL), số lượng **có dấu**, loại + số chứng từ, dòng chứng từ, SLE gốc, cờ đã đảo, công ty. Mọi liên kết **PHẢI** được kiểm tồn tại | T `test_so_vi_tri` |
| VTK-SO-03 | Mỗi lần ghi sổ **PHẢI** cộng dồn tồn vị trí bằng một câu `INSERT … ON DUPLICATE KEY UPDATE` trên khoá duy nhất (ô, mặt hàng, lô) | T `test_so_vi_tri` |
| VTK-SO-04 | Hook trên `Stock Ledger Entry.on_submit` **PHẢI** bỏ qua kho chưa bật; với kho đã bật, **PHẢI** tính số lượng thay đổi thật **trước** khi ghi bất kỳ dòng sổ nào của chính SLE đó | T `test_hook_nhap`, `test_tinh_delta` |
| VTK-SO-05 | Số lượng thật = `actual_qty`, trừ kiểm kê hàng không lô (không bundle, không `has_batch_no`, không inventory dimension): = `qty_after_transaction` − tồn vị trí hiện có. Điều kiện chọn nhánh **KHÔNG ĐƯỢC** dựa vào `actual_qty = 0` (sai ở đường huỷ kiểm kê) | T `test_tinh_delta`, `test_hook_nhap` |
| VTK-SO-06 | Một dòng SLE **PHẢI** được tách theo lô từ bundle (N lô → N dòng sổ). Tổng thẩm quyền là số lượng thật; bundle chỉ cho tỉ lệ. Lệch thì chia theo tỉ lệ, dồn phần dư vào dòng cuối (6 chữ số thập phân); tổng bundle ≈ 0 thì ghi một dòng không lô và ghi log | T `test_tach_theo_lo` |
| VTK-SO-07 | **Nhập** (số dương): vào ô "Chưa xếp vị trí" của kho. Ngoại lệ: nếu chính dòng chứng từ đó vừa bị đảo khỏi ô thật (Landed Cost Voucher, Repost), trả về đúng các ô đã đảo. **Xuất** (số âm): hook giao cho phần lấy hàng chọn ô — đặc tả ở tài liệu riêng (§1.2). Nền tảng chỉ đòi hai điều: ô được chọn là ô lá của đúng kho, và thiếu hàng thì chặn cả chứng từ với thông báo tiếng Việt | T `test_hook_nhap`, `test_landed_cost_voucher` |
| VTK-SO-08 | **Huỷ chứng từ**: hook **PHẢI** tra lại các dòng sổ gốc (cùng loại + số chứng từ, dòng chứng từ, kho, mặt hàng, chưa đảo), ghi đảo đúng từng ô và lô đã dùng, cờ "đã đảo" lên cả dòng gốc lẫn dòng đảo. **KHÔNG ĐƯỢC** chạy lại quy tắc chọn ô khi huỷ | T `test_huy_chung_tu`, `test_pr_dn_tich_hop` |
| VTK-SO-09 | Nếu không có dòng gốc vì chứng từ lập trước khi bật kho, hook đi đường thường. Nếu không có dòng gốc vì một SLE anh em đã đảo xong, hook **KHÔNG ĐƯỢC** ghi thêm | T `test_huy_chung_tu` |
| VTK-SO-10 | Kho bật mà thiếu ô "Chưa xếp vị trí", hoặc ô đó sai dạng (sai kho, không cờ, là nhóm, ngừng dùng), hook **PHẢI** báo lỗi tiếng Việt thay vì ghi nhầm | T `test_co_quan_ly_vi_tri` |
| VTK-SO-11 | Trường hợp mất chiều lô (huỷ chứng từ lập trước khi bật kho) **PHẢI** được ghi Error Log, không im lặng | T `test_hook_nhap` |
| VTK-SO-12 | `dung_lai_ton_vi_tri(kho)` **PHẢI** xoá bộ đệm của phạm vi và cộng lại toàn bộ từ sổ; chạy lại bao nhiêu lần cũng cho cùng kết quả | T `test_so_vi_tri` |

#### 3.2.6 Đối soát — VTK-DS

| Mã | Yêu cầu | Kiểm chứng |
|---|---|---|
| VTK-DS-01 | Đối soát một kho **PHẢI** chạy ba phép đo, và chỉ báo "khớp" khi cả ba sạch: **(a) lệch tồn** — tổng theo (mặt hàng, lô) so với tồn kho ERPNext; **(b) ô âm** — ô nào mang tồn < −0,0001; **(c) lệch bộ đệm** — bộ đệm so với sổ theo (ô, mặt hàng, lô) | T `test_doi_soat` |
| VTK-DS-02 | Vế tồn kho ERPNext **PHẢI** lấy tổng từ `Bin.actual_qty` và chia lô từ `Serial and Batch Entry` của SLE chưa huỷ; phần dư không chia được vào ngăn không lô. **KHÔNG ĐƯỢC** cộng `SLE.actual_qty` | T `test_doi_soat` |
| VTK-DS-03 | Ngưỡng sai số dùng chung một hằng (`NGUONG_SAI_SO = 0,0001`) cho bật kho và đối soát | I |
| VTK-DS-04 | Đối soát "khớp" **không** chứng minh ô chứa đúng mặt hàng, cũng không chứng minh cấu trúc cây đúng. Hai việc đó thuộc VTK-BC-04 và kiểm tra `lft`/`rgt` trực tiếp | I |

#### 3.2.7 Báo cáo — VTK-BC

Cả bốn báo cáo mở cho SM, StM, SU.

| Mã | Báo cáo | Yêu cầu | Kiểm chứng |
|---|---|---|---|
| VTK-BC-01 | **Tồn kho theo vị trí** | Lọc theo kho, mặt hàng. Hiển thị **dạng cây** Khu → Dãy → Khoang → Tầng → Ô, mỗi nút nhóm mang tổng của mọi ô lá bên dưới; ô "Chưa xếp vị trí" luôn hiện dù đứng ngoài cây. Cột: ô, tên ô, kho, mặt hàng, lô, hạn dùng, số lượng, ô cha | T `test_bao_cao` |
| VTK-BC-02 | **Hàng chưa xếp vị trí** | Mọi dòng tồn ≠ 0 ở ô "Chưa xếp vị trí", lọc theo kho. Cùng điều kiện với nút "Lấy hàng chưa xếp" của phiếu xếp | T `test_bao_cao` |
| VTK-BC-03 | **Đối soát tồn vị trí** | Bắt buộc chọn kho (thiếu kho thì báo lỗi, kể cả khi gọi qua API). Một bảng, cột **Loại lệch** phân biệt "Lệch tồn" / "Ô âm" / "Lệch bộ đệm". **Rỗng = khớp** | T `test_bao_cao`, `test_doi_soat` |
| VTK-BC-04 | **Hàng nằm sai vị trí** | Mọi dòng tồn ≠ 0 nằm trong nhánh đã gán cho mặt hàng khác. Cột: ô, mã trên nhãn, mặt hàng đang nằm, lô, số lượng, mặt hàng đã gán, nút gán. **Rỗng = đúng chỗ** | T `test_bao_cao` |
| VTK-BC-05 | Ghi chú | Số ở nút Khu trong VTK-BC-01 cộng qua nhiều đơn vị tính; người dùng **NÊN** lọc một mặt hàng trước khi đọc số cấp Khu | — |

#### 3.2.8 Phiếu xếp / chuyển vị trí — VTK-XEP

`Location Transfer`, số phiếu `XVT-.YYYY.-`, duyệt được. Mỗi dòng: mặt hàng, lô, từ ô, đến ô,
số lượng.

| Mã | Yêu cầu | Kiểm chứng |
|---|---|---|
| VTK-XEP-01 | Phiếu **KHÔNG ĐƯỢC** sinh Stock Ledger Entry và không gọi hàm nào của `erpnext/stock/`; tồn kho ERPNext, giá vốn, kế toán không đổi | T `test_phieu_xep_vi_tri` (đếm SLE trước/sau) |
| VTK-XEP-02 | K1: kho **PHẢI** đang bật quản lý vị trí | T `test_phieu_xep_vi_tri` |
| VTK-XEP-03 | K2: cả "từ ô" lẫn "đến ô" **PHẢI** thuộc đúng kho của phiếu. Đây là điều kiện để bất biến tồn tự giữ | T `test_phieu_xep_vi_tri` |
| VTK-XEP-04 | K3: "đến ô" **KHÔNG ĐƯỢC** là nút nhóm | T `test_phieu_xep_vi_tri` |
| VTK-XEP-05 | K4: "đến ô" **KHÔNG ĐƯỢC** ngừng dùng hoặc nằm dưới nhánh ngừng dùng; thông báo nêu nút đang tắt ở cấp cao nhất | T `test_phieu_xep_vi_tri` |
| VTK-XEP-06 | K5: "từ ô" **ĐƯỢC PHÉP** đang ngừng dùng — đường duy nhất gỡ hàng khỏi dãy đang tháo kệ | T `test_phieu_xep_vi_tri` (bài đối chứng) |
| VTK-XEP-07 | K6–K8: từ ô ≠ đến ô; số lượng > 0; phiếu có ít nhất một dòng | T `test_phieu_xep_vi_tri` |
| VTK-XEP-08 | K9–K10: mặt hàng có lô thì bắt buộc lô; mặt hàng không lô thì lô phải trống; lô phải là lô của đúng mặt hàng | T `test_phieu_xep_vi_tri` |
| VTK-XEP-09 | Duyệt **PHẢI** ghi hai dòng sổ mỗi dòng phiếu (−n ô nguồn, +n ô đích), rồi đọc lại tồn **ròng** của mọi (ô, mặt hàng, lô) phiếu chạm tới; ô nào âm thì báo lỗi nêu ô, mặt hàng, lô, số sẽ còn, và rollback về savepoint (không dòng sổ nào sống sót) | T `test_phieu_xep_vi_tri` |
| VTK-XEP-10 | Phiếu lấy 10 khỏi ô A ở dòng 1 rồi trả 10 về ô A ở dòng 2 **PHẢI** duyệt được (kiểm theo kết quả ròng) | T `test_phieu_xep_vi_tri` |
| VTK-XEP-11 | Huỷ **PHẢI** ghi bút toán đảo (cờ đã đảo), không sửa, không xoá; bị chặn nếu ô đích sẽ âm (hàng đã bị xuất) | T `test_phieu_xep_vi_tri` |
| VTK-XEP-12 | Nút **Lấy hàng chưa xếp** (phiếu nháp) **PHẢI** đổ mọi dòng tồn ở ô "Chưa xếp vị trí" thành dòng phiếu, điền sẵn "từ ô" và **đến ô gợi ý** theo VTK-GY. Gợi ý không chặn và không ghi đè lựa chọn của thủ kho | T `test_phieu_xep_vi_tri`, `test_goi_y_o` |
| VTK-XEP-13 | Sau khi lấy dòng, màn hình **PHẢI** tóm tắt số dòng chưa có gợi ý, gộp theo đúng lý do máy chủ trả về, và riêng nhóm "tem cũ không dùng được" (theo cờ `tem_hong`, **KHÔNG ĐƯỢC** so khớp chuỗi) | T `test_phieu_xep_vi_tri` (cờ `tem_hong`), D |
| VTK-XEP-14 | Lỗi gợi ý của một (mặt hàng, lô) **KHÔNG ĐƯỢC** làm hỏng cả danh sách: dòng đó để trống ô đích với lý do "không gợi ý được — xem Error Log", lỗi ghi vào Error Log | T `test_phieu_xep_vi_tri` |
| VTK-XEP-15 | Đổi kho trên phiếu nháp **PHẢI** xoá các dòng và báo cho người dùng | D |

#### 3.2.9 Gán vị trí cố định cho mặt hàng — VTK-GAN

`Item Location Preference`, tên bản ghi = mã mặt hàng.

| Mã | Yêu cầu | Kiểm chứng |
|---|---|---|
| VTK-GAN-01 | Một mặt hàng **PHẢI** gán đúng **một** nút ở bất kỳ cấp nào; gán nút nhóm = cả nhánh dưới nó thuộc mặt hàng. Bất biến giữ bằng khoá chính (`autoname: field:vat_tu`) | T `test_gan_vi_tri` |
| VTK-GAN-02 | Hệ quả của VTK-GAN-01: một mặt hàng chỉ gán được ở **một kho** (xem Phụ lục C) | I |
| VTK-GAN-03 | Thứ tự kiểm khi lưu: (1) nút có toạ độ trong cây; (2) nút cùng kho, kho đang bật, không phải ô "Chưa xếp vị trí", không ngừng dùng kể cả qua tổ tiên; (3) không chồng lấn gán khác; (4) nhánh không chứa tồn của mặt hàng khác | T `test_gan_vi_tri` |
| VTK-GAN-04 | Chồng lấn **PHẢI** xét theo **giao nhau** hai nhánh: chặn trùng nút, gán vào con cháu, gán vào tổ tiên; **cho qua** nút anh em và nhánh khác; loại trừ chính bản ghi đang sửa. Thông báo nêu nút vướng, mặt hàng đang giữ và quan hệ (trùng / nằm trong / bao trùm) | T `test_gan_vi_tri` |
| VTK-GAN-05 | Chặn tồn mặt hàng khác **PHẢI** nêu tối đa 3 ô đầu (ô · mặt hàng · số lượng) và "… và N ô nữa" với N đếm thật | T `test_gan_vi_tri` |
| VTK-GAN-06 | Trường **Cấp** (Khu/Dãy/Khoang/Tầng/Ô) **PHẢI** tự tính lại từ mã mỗi lần lưu, chỉ để hiển thị | T `test_gan_vi_tri` |
| VTK-GAN-07 | Đổi mã mặt hàng **PHẢI** kéo theo tên bản ghi gán. Gộp mặt hàng: đích chưa có gán thì đổi tên; đích đã có gán thì giữ gán của đích, xoá gán của mã cũ | T `test_gan_vi_tri`, `test_app_khoi_dong` |
| VTK-GAN-08 | **Cây chọn vị trí** (hộp thoại) **PHẢI** nạp từng cấp của đúng kho, loại ô "Chưa xếp vị trí" và nút chưa có toạ độ; mỗi nốt hiện **số ô trống** và **số mặt hàng đang nằm** trong nhánh | T `test_gan_vi_tri`, D |
| VTK-GAN-09 | Nốt không chọn được **PHẢI** không có nút "Chọn" và hiện lý do riêng: *đã gán: `<mặt hàng>`* (chính nó hoặc tổ tiên đã có chủ) · *có gán bên trong* · *đang ngừng dùng*. Mở cây khi đang sửa một gán **PHẢI** loại trừ chính gán đó | T `test_gan_vi_tri`, D |
| VTK-GAN-10 | Trên form **Item** (mặt hàng lưu kho, đã lưu): đầu form **PHẢI** hiện "Vị trí cố định: `<nút>` · `<kho>` · cấp `<cấp>`" (xanh) hoặc "chưa gán vị trí cố định — tem in ra sẽ trống ô vị trí" (cam) | T `test_giao_dien` (gắn `item.js`), D |
| VTK-GAN-11 | Nút **Vị trí kho → Gán vị trí / Đổi vị trí** chỉ hiện khi người dùng có quyền tạo hoặc sửa gán; chọn kho (chỉ kho đã bật) rồi chọn trên cây; lưu đi qua `validate` đầy đủ, không `ignore_permissions` | T `test_gan_vi_tri`, D |
| VTK-GAN-12 | Người dùng **NÊN** gán ở cấp **Tầng**, không gán một Ô lẻ | — |

#### 3.2.10 Gợi ý ô khi xếp — VTK-GY

`goi_y_o(vat_tu, kho, so_lo=None)` trả bộ ba **(ô, lý do, tem_hong)**.

| Mã | Yêu cầu | Kiểm chứng |
|---|---|---|
| VTK-GY-01 | Mặt hàng chưa gán → `(trống, "mặt hàng chưa gán vị trí cố định")`, không báo lỗi | T `test_goi_y_o` |
| VTK-GY-02 | Nút gán chưa có toạ độ → báo lỗi tường minh | T `test_goi_y_o` |
| VTK-GY-03 | Ứng viên = ô lá trong nhánh gán, không phải ô "Chưa xếp vị trí", không nằm dưới nhánh ngừng dùng; duyệt theo thứ tự cây (`lft` tăng) | T `test_goi_y_o` |
| VTK-GY-04 | Nếu có `so_lo` và lô đó đã in tem (`custom_o_in_tem`): ô trên tem được ưu tiên **trước mọi thứ**, miễn là ô đó vẫn là ứng viên và không chứa mặt hàng khác → lý do "theo ô đã in trên tem của lô …" | T `test_goi_y_o` |
| VTK-GY-05 | Ô trên tem không dùng được nữa → rơi xuống các bước sau, lý do mở đầu bằng "tem của lô … in ô … nhưng ô đó không xếp được nữa", và `tem_hong = True` | T `test_goi_y_o` |
| VTK-GY-06 | Thứ tự còn lại: **ô trống đầu tiên** (tổng tồn = 0, không phải "không có dòng") → **ô đang chứa chính mặt hàng** → không có thì `(trống, "vùng <nút> đã đầy: N/N ô đang chứa hàng khác")` | T `test_goi_y_o` |
| VTK-GY-07 | Gợi ý không dùng sức chứa ô (`suc_chua` chưa được điền) | I |

#### 3.2.11 Nhập lô — VTK-LO

Luồng bắt buộc: **phiếu nhập nháp → Nhập lô & in nhãn → khai lô → duyệt phiếu nhập lô → duyệt
phiếu nhập → in nhãn**.

```
Purchase Receipt (nháp) ──[Nhập lô & in nhãn]──► Batch Entry (nháp, dòng tự nạp)
                                                   │ gõ số lô, HSD, NSX → Lưu → Duyệt
                                                   ▼
                        tạo/dùng lại Batch · cấp số gọi · ghi batch_no lên dòng PR
                                                   │
Purchase Receipt ──[Duyệt: kiểm lô phải đến từ Batch Entry]──► hàng vào ô "Chưa xếp vị trí"
                                                   │
                         Batch Entry ──[In nhãn cả phiếu]──► nhãn 50×30
```

| Mã | Yêu cầu | Kiểm chứng |
|---|---|---|
| VTK-LO-01 | `Batch Entry` (số `PNL-.YYYY.-`, duyệt được) **PHẢI** gắn đúng một phiếu nhập, chọn một lần; công ty, ngày nhập, nhà cung cấp lấy từ phiếu nhập | T `test_nhap_lo` |
| VTK-LO-02 | **Lấy dòng hàng từ phiếu nhập** **PHẢI** nạp các dòng có mặt hàng bật "Có lô" và **chưa có** số lô, kèm kho, số lượng, ô gợi ý và lý do gợi ý (không truyền lô) | T `test_nhap_lo` |
| VTK-LO-03 | Phiếu mới đã mang sẵn phiếu nhập mà chưa có dòng thật **PHẢI** tự nạp dòng. Đổi phiếu nhập khi đã có dòng thật **PHẢI** hỏi xác nhận trước khi xoá | D |
| VTK-LO-04 | Kiểm khi lưu, **đúng thứ tự**: (1) phiếu nhập còn nháp; (2) mỗi dòng thuộc đúng phiếu nhập và không trùng — một dòng phiếu nhập nhận **một** lô, hai lô thì tách dòng trên phiếu nhập; (3) dòng chưa được một phiếu nhập lô khác đã duyệt phủ; (4) số lô sau khi cắt khoảng trắng không rỗng, **ký tự trước, độ dài sau** (VTK-LO-05, 06); lô chưa thuộc mặt hàng khác; (5) hạn dùng không trước ngày sản xuất | T `test_nhap_lo` |
| VTK-LO-05 | Số lô **PHẢI** chỉ gồm ký tự ASCII (Code 128 mã hoá được). Vi phạm → thông báo nêu **ký tự, mã U+, vị trí**, nhắc hai thủ phạm (dấu tiếng Việt, gạch dài `–`) và dặn **không xoá bớt ký tự** | T `test_ma_vach`, `test_nhap_lo` |
| VTK-LO-06 | Số lô **PHẢI** vẽ được trong 188 module (47 mm ở 0,25 mm/module): tối đa 26 chữ số (độ dài chẵn), 23 chữ số (lẻ), 13 ký tự nếu có chữ. Số module tính chính xác: `35 + 11 × số ký hiệu`, trong đó chuỗi toàn số độ dài lẻ tốn thêm một ký hiệu chuyển bộ mã | T `test_ma_vach` |
| VTK-LO-07 | Kiểm ký tự (VTK-LO-05) **PHẢI** áp cho **mọi** đường tạo `Batch` mới (hộp thoại lô ERPNext, form Batch, Data Import) qua `Batch.validate`, chỉ khi tạo mới (lô cũ vẫn lưu lại được) | T `test_lo_ncc` (`TestChanKyTuLo`) |
| VTK-LO-08 | Duyệt phiếu nhập lô **PHẢI**: tạo `Batch` (số lô, mặt hàng, HSD, NSX, NCC, chứng từ gốc = phiếu nhập, số gọi); nếu lô đã tồn tại của cùng mặt hàng thì **dùng lại** và chỉ điền chỗ trống; ghi lô và số gọi về bảng con; ghi `batch_no` lên đúng dòng phiếu nhập | T `test_nhap_lo` |
| VTK-LO-09 | **Số gọi** **PHẢI** là số 4 chữ số từ bộ đếm **toàn cục không reset theo năm**, không bao giờ cấp lại; vượt 9999 thành 5 chữ số, nhãn **KHÔNG ĐƯỢC** cắt bớt. Chỉ phiếu nhập lô cấp số gọi; trường chỉ đọc | T `test_nhap_lo` |
| VTK-LO-10 | Huỷ phiếu nhập lô: **bị chặn** khi phiếu nhập đã duyệt; **cho phép** khi phiếu nhập còn nháp, đã huỷ hoặc đã xoá. Huỷ gỡ `batch_no` khỏi dòng phiếu nhập **chỉ khi** giá trị đó đúng là lô do chính dòng này tạo; bản ghi `Batch` **luôn được giữ** (tem có thể đã dán) | T `test_nhap_lo` |
| VTK-LO-11 | Huỷ phiếu nhập **KHÔNG ĐƯỢC** bị chặn bởi phiếu nhập lô trỏ tới nó (sửa lõi: `Batch Entry` trong `ignore_linked_doctypes`) — tránh khoá chết hai chứng từ | T `test_nhap_lo` |
| VTK-LO-12 | Lô sinh từ phiếu nhập / hoá đơn mua mà thiếu nhà cung cấp **PHẢI** được điền NCC từ chứng từ gốc lúc tạo (`before_insert`), bất kể tạo bằng đường nào | T `test_lo_ncc` |
| VTK-LO-13 | **Chặn duyệt phiếu nhập**: với dòng hàng có lô **vào kho đã bật quản lý vị trí**, số lô **PHẢI** đến từ một phiếu nhập lô đã duyệt, khớp theo cặp (dòng, số lô). Thiếu lô hoặc lô gõ tay → từ chối, liệt kê từng dòng sai và chỉ nút **Nhập lô & in nhãn**. Miễn: phiếu trả hàng, kho chưa bật | T `test_loi_vao_nhap_lo` |
| VTK-LO-14 | Nút **Nhập lô & in nhãn** **PHẢI** hiện trên mọi phiếu nhập nháp; tự lưu phiếu nếu mới hoặc đang sửa; mở lại phiếu nhập lô **nháp** đang có (không tạo phiếu thứ hai); không có dòng để khai thì hiện **câu chẩn đoán**. Nhãn nút khớp từng chữ với câu báo ở VTK-LO-13 | T `test_loi_vao_nhap_lo`, `test_giao_dien` (nhãn nút khớp câu báo) |
| VTK-LO-15 | Câu chẩn đoán **PHẢI** nói đúng một nguyên nhân: phiếu đã duyệt (kèm lô gõ tay nếu có) · phiếu đã huỷ · dòng có lô gõ thẳng trên phiếu · không mặt hàng nào bật "Có lô" · mọi dòng đã khai qua phiếu nhập lô `<số>`. Dữ liệu người dùng trong câu **PHẢI** được escape HTML | T `test_loi_vao_nhap_lo`; escape: I |
| VTK-LO-16 | Phiếu nhập đã duyệt **PHẢI** có nút **Xem phiếu nhập lô** nếu có phiếu nhập lô đã duyệt (một phiếu → mở form; nhiều → danh sách) | D |
| VTK-LO-17 | Mặt hàng có trường **Thông số in trên tem** (`custom_thong_so_tem`, tối đa 60 ký tự) cho ô F4 của nhãn | T `test_nhap_lo` |

#### 3.2.12 Tem vị trí dán kệ — VTK-TVT

| Mã | Yêu cầu | Kiểm chứng |
|---|---|---|
| VTK-TVT-01 | Tem **PHẢI** in mã 10 ký tự tách **ba nhóm**: `KHU DÃY` (4 ký tự) · `KHOANG` (2) · `TẦNG Ô` (4, cỡ chữ lớn nhất, có khung đậm). Đọc liền ba nhóm ra đúng chuỗi máy quét trả về | T `test_tem`, D |
| VTK-TVT-02 | Mã vạch Code 128 mã hoá **trường Mã vạch** của ô (mặc định = mã ô), **không in chữ dưới vạch** | D |
| VTK-TVT-03 | Mũi tên ⇩ in cố định trên mọi tem, **vẽ bằng SVG** (không dùng ký tự Unicode) — nghĩa "ô nằm ngay dưới chỗ dán" | I |
| VTK-TVT-04 | Chân tem: `<kho> · <tên ô>` | D |
| VTK-TVT-05 | Hai khổ, **một bố cục**: 45×25 mm (mặc định, lề 1,25 mm) và 50×30 mm (lề 1,5 mm). Mã vạch rộng **28,0 mm** (112 module × 0,25 mm), cao 7,25 / 9 mm. Cỡ chữ: tiêu đề 5 / 5,5 pt, nhóm 11 / 12 pt, nhóm lớn 20 / 23 pt, chân 4 / 4,5 pt | A |
| VTK-TVT-06 | Mọi mã ô 10 ký tự **PHẢI** ra đúng 112 module, nên bề rộng mã vạch là hằng số, không làm tròn | A |
| VTK-TVT-07 | Form ô **PHẢI** vẽ **đúng con tem sẽ in** (cùng bộ vẽ với trang in). Nút nhóm và ô "Chưa xếp vị trí" hiện câu giải thích thay vì tem. Hình vẽ lại mỗi lần mở form, không lưu vào CSDL | D |
| VTK-TVT-08 | **In tem hàng loạt** từ cây vị trí: bấm **In tem** ở nốt nào thì in mọi ô lá dưới nốt đó (loại nút nhóm, loại ô "Chưa xếp vị trí"), theo thứ tự lấy hàng rồi mã ô | T `test_tem` |
| VTK-TVT-09 | Hộp thoại in **PHẢI** cho biết số ô, 5 mã ví dụ, chọn khổ, số bản mỗi ô (1–200), xem trước ô đầu tiên và nhắc in tỉ lệ 100% | D |
| VTK-TVT-10 | Tổng số tem một lần in (số ô × số bản) **KHÔNG ĐƯỢC** vượt **500**; vượt thì **từ chối hẳn**, không cắt bớt | T `test_tem` |
| VTK-TVT-11 | Trang in **PHẢI** đặt `@page` đúng khổ, lề 0, mỗi tem một trang, không có trang trắng cuối; mã vạch nhúng SVG nội tuyến (không tải ảnh) | A |
| VTK-TVT-12 | Không mã hoá được một mã → **không vẽ mã vạch nào**; **KHÔNG ĐƯỢC** dùng lại mã vạch của lần vẽ trước | I |
| VTK-TVT-13 | Trình duyệt chặn cửa sổ in → báo "Trình duyệt chặn cửa sổ in" | D |
| VTK-TVT-14 | Thủ kho (SU) **PHẢI** in lại được tem; in tem không ghi dữ liệu | T `test_tem` |

#### 3.2.13 Nhãn lô 50×30 — VTK-TL

Một bố cục duy nhất. Vùng in 47 × 27 mm (lề 1,5 mm).

```
┌─────────────────────────────────────────────────┐
│ F1 mã vật tư (11pt đậm)          F3 ĐVT (6,5pt) │ R1 4,32
│ F2 tên hàng (8pt)                               │ R2 3,26
│ F4 thông số (5,5pt)                             │ R3 2,47
├───────────────────────────┬─────────────────────┤
│ F5 HSD YYYY/MM/DD (8pt)   │                     │ R4 3,90
│ F6 Lô <số lô> (7pt)       │  F9 SỐ GỌI (19pt)   │ R5 3,58
├───────────────────────────┴─────────────────────┤
│ F8 VT <ô> (7pt)              F7 NHẬP YYYY/MM/DD │ R6 2,73
│ F10 mã vạch = số lô (cao 4,8, căn giữa)         │ R7 6,74
│ F11 số lô bằng chữ (5pt)                        │
└─────────────────────────────────────────────────┘
  cột trái 27,0 mm · khe 0,6 · cột phải 19,4 mm        tổng hàng = 27,0 mm
```

| Mã | Yêu cầu | Kiểm chứng |
|---|---|---|
| VTK-TL-01 | Dữ liệu 11 ô **PHẢI** do máy chủ định dạng sẵn: F1 mã mặt hàng · F2 tên hàng · F3 ĐVT tồn kho, kèm `(<hệ số>/<đơn vị>)` chỉ khi mặt hàng có **đúng một** quy đổi khác ĐVT tồn · F4 thông số in trên tem (trống thì để trắng, giữ chỗ) · F5 `HSD YYYY/MM/DD` · F6 `Lô <số lô>` · F7 `NHẬP <ngày phiếu nhập>` · F8 `VT <mã in trên nhãn của ô>` hoặc `VT —` · F9 số gọi · F10, F11 số lô nguyên văn | T `test_nhap_lo` |
| VTK-TL-02 | Lưới **cố định**: ô trống vẫn giữ nguyên chiều cao, không dồn hàng dưới lên | A |
| VTK-TL-03 | Mã vạch **PHẢI** mã hoá **đúng số lô**, module 0,25 mm (2 dot); bề rộng = số module × 0,25 mm **đo từ chính SVG sẽ in**; căn giữa khổ 50 mm | A, T `test_ma_vach` |
| VTK-TL-04 | Không mã hoá được (ký tự ngoài ASCII) hoặc > 188 module → **không vẽ mã vạch**, in dòng chữ **"KHÔNG CÓ MÃ VẠCH — GÕ TAY SỐ LÔ"** đúng chỗ mã vạch, và báo đỏ trên màn hình. **KHÔNG ĐƯỢC** thu module dưới 2 dot | I, D |
| VTK-TL-05 | 181–188 module → vẫn vẽ nhưng cảnh báo cam "vùng yên tĩnh bị thiếu" | I |
| VTK-TL-06 | Chiều cao mỗi hàng **PHẢI** ≥ hộp chữ (đỉnh ascender → đáy descender, gồm dấu tiếng Việt) của cỡ lớn nhất trong hàng. Tổng 7 hàng **PHẢI** bằng 27,0 mm (có phép kiểm `console.assert`) | A |
| VTK-TL-07 | Ô chữ tràn **PHẢI** bị cắt trong ô của nó (`min-width: 0`), không đè ô bên cạnh; khối mã vạch không được co (`flex: 0 0 auto`) | A |
| VTK-TL-08 | **Ô in trên tem** (F8) **PHẢI** được chốt đúng **một lần**, lần in đầu tiên (`dat_o_in_tem`): suy kho từ dòng phiếu nhập của lô, lấy ô gợi ý (VTK-GY), ghi `Batch.custom_o_in_tem`. Đã có giá trị thì giữ nguyên: in lại ra đúng tờ tem cũ | T `test_nhap_lo` |
| VTK-TL-09 | Xem trước dữ liệu tem (`du_lieu_tem`) **KHÔNG ĐƯỢC** ghi ô in trên tem. Hàm nhận một lô, danh sách lô, hoặc chuỗi JSON của danh sách, trả đúng thứ tự đầu vào | T `test_nhap_lo` |
| VTK-TL-10 | Không suy được kho, mặt hàng chưa gán, hoặc gợi ý lỗi → F8 in `VT —`, **không chặn in**, và báo cam một lần danh sách lô không có ô | T `test_nhap_lo`, D |
| VTK-TL-11 | Trình tự in **PHẢI** là: chốt ô **tuần tự** từng lô → đọc dữ liệu cả xấp một lần → mở cửa sổ in. Dùng chung cho **In nhãn cả phiếu** (phiếu nhập lô đã duyệt, chỉ khi `docstatus = 1`) và **In nhãn** (form Batch đã lưu, mặt hàng còn bật "Có lô") | T `test_giao_dien` (gắn `batch.js`, `in_nhan_lo.js`), D |
| VTK-TL-12 | Ô in trên tem khác ô thực tế lúc xếp → hệ xếp lại theo VTK-GY-05 và thủ kho **NÊN** in tem mới dán đè | — |

#### 3.2.14 Quét mã tra cứu — VTK-QUET

| Mã | Yêu cầu | Kiểm chứng |
|---|---|---|
| VTK-QUET-01 | Trang `quet-ma-tra-cuu` **PHẢI** nhận diện mã theo thứ tự: mã vạch mặt hàng / serial / **lô** / **kho** (qua `scan_barcode` của ERPNext, không sửa) → **ô** (theo tên, trường mã vạch, hoặc mã in trên nhãn `1A0101-0101`) → **mã vật tư** gõ tay | T `test_quet` |
| VTK-QUET-02 | **Lô**: số lô, mặt hàng, tên, ĐVT, hạn dùng, ngày SX, NCC, số gọi, ngày nhập, số phiếu nhập, vị trí cố định, ô in trên tem, **tồn theo từng ô** | T `test_quet` |
| VTK-QUET-03 | **Ô / nút nhóm**: kho, loại, ngừng dùng, mặt hàng giữ vị trí (gán ở chính nút hoặc tổ tiên gần nhất — **không** lấy gán của con cháu), hàng đang chứa trong cả nhánh (tối đa 50 dòng) và tổng số dòng | T `test_quet` |
| VTK-QUET-04 | **Mặt hàng**: tên, ĐVT, có lô, vị trí cố định, các lô còn tồn theo ô, **hạn gần nhất lên đầu** (không hạn xuống cuối) | T `test_quet` |
| VTK-QUET-05 | **Kho**: có quản lý vị trí không, số ô lá đang dùng, số ô có hàng | T `test_quet` |
| VTK-QUET-06 | Mã không nhận ra hoặc lỗi dữ liệu **KHÔNG ĐƯỢC** gây lỗi màn hình: trả "không nhận ra", ghi Error Log; lỗi phân quyền vẫn báo nguyên | T `test_quet` |
| VTK-QUET-07 | Hạn dùng tô màu: xanh > 90 ngày · cam ≤ 90 ngày · đỏ đã hết hạn. Ngưỡng 90 ngày là **tạm đặt** | D |
| VTK-QUET-08 | Giữ 10 mã quét gần nhất trong phiên (mất khi tải lại trang, không lưu CSDL) | D |

#### 3.2.15 Ô quét dùng chung và xếp hàng trên PDA — VTK-PDA

| Mã | Yêu cầu | Kiểm chứng |
|---|---|---|
| VTK-PDA-01 | Ô quét **PHẢI** luôn giữ focus mà không bật bàn phím ảo (`inputmode="none"`); nút ⌨ chuyển sang gõ tay; nút máy ảnh quét bằng camera | D |
| VTK-PDA-02 | Súng quét không gửi Enter: ngừng nhận ký tự **250 ms** thì coi là quét xong | I |
| VTK-PDA-03 | Trang `xep-hang-pda`: tự chọn kho nếu chỉ có một kho quản lý vị trí; nhiều kho thì lấy kho của phiếu nháp gần nhất của người dùng, không có thì hỏi | T `test_xep_pda` |
| VTK-PDA-04 | Mỗi người dùng có **một phiếu xếp nháp mỗi kho**; mở lại trang gặp lại đúng phiếu đó | T `test_xep_pda` |
| VTK-PDA-05 | Quét **tem lô** → hiện mặt hàng, lô, hạn, các **ô nguồn** còn xếp được (đã trừ phần đã lên phiếu), ô nguồn mặc định (ô "Chưa xếp vị trí" nếu còn hàng; một ô duy nhất; nhiều ô thì để chọn), số lượng điền sẵn toàn bộ, **ô gợi ý** | T `test_xep_pda` |
| VTK-PDA-06 | Quét **mã hàng có lô** → nhắc quét tem lô, không đoán lô. Mã hàng không lô → dùng được như tem lô | T `test_xep_pda` |
| VTK-PDA-07 | Quét **tem ô** đúng ô gợi ý → thêm dòng ngay. Khác ô gợi ý → **chưa ghi**, yêu cầu quét lại đúng tem đó (hoặc chạm nút xác nhận) | D |
| VTK-PDA-08 | Mỗi dòng **PHẢI** lưu ngay lên phiếu nháp (tạo phiếu nếu chưa có), cộng dồn nếu trùng (mặt hàng, lô, từ ô, đến ô). Vượt số còn ở ô nguồn chưa lên phiếu → từ chối | T `test_xep_pda` |
| VTK-PDA-09 | Bỏ dòng chỉ trên phiếu nháp của **chính mình**; bỏ dòng cuối thì xoá luôn phiếu nháp rỗng | T `test_xep_pda` |
| VTK-PDA-10 | **Hoàn tất phiếu** duyệt trong savepoint riêng: lỗi thì phiếu nháp và các dòng còn nguyên | T `test_xep_pda` |
| VTK-PDA-11 | Hộp xác nhận "Ghi phiếu?" / "Bỏ dòng?" **chỉ nhận chạm tay** — phím Enter của súng quét không bấm được | D |
| VTK-PDA-12 | Mọi phép kiểm dòng còn lại do `Location Transfer.validate` đảm nhiệm (VTK-XEP); trang PDA không phải cửa sau quyền | T `test_xep_pda` |

#### 3.2.16 Phân quyền — VTK-QH

| Mã | Yêu cầu | Kiểm chứng |
|---|---|---|
| VTK-QH-01 | DocPerm theo bảng dưới; **không doctype, trang, báo cáo nào** có quyền cho `Customer` hay `Website User` | T `test_phan_quyen` |
| VTK-QH-02 | Mọi hàm whitelist **PHẢI** tự kiểm vai trò ở dòng đầu (bảng 3.1.4) và báo `PermissionError` tiếng Việt nêu đúng thao tác bị chặn | T `test_phan_quyen`, `test_bat_kho`, `test_quet`, `test_tem`, `test_xep_pda` |

| Doctype / trang | SM | StM | SU |
|---|---|---|---|
| Storage Location, Item Location Preference | đọc, tạo, sửa, xoá | đọc, tạo, sửa, xoá | đọc |
| Location Generator | đọc, tạo, sửa, xoá | đọc, tạo, sửa | — |
| Warehouse Location Setup | đọc, tạo, sửa, xoá | đọc, tạo, sửa | — |
| Location Ledger Entry, Location Balance | đọc | đọc | đọc |
| Location Transfer, Batch Entry | toàn quyền | toàn quyền | đọc, tạo, sửa, duyệt, huỷ, sửa đổi (không xoá) |
| 3 trang PDA, 4 báo cáo | ✓ | ✓ | ✓ |

---

### 3.3 Yêu cầu dữ liệu

#### 3.3.1 Doctype mới

| Doctype | Đặt tên | Loại | Trường chính |
|---|---|---|---|
| Storage Location | `field:ma_o` | cây | ma_o, ma_in_nhan, ten_o, kho, is_group, parent_storage_location, loai_vi_tri, disabled, khu, day, khoang, tang, o, barcode, thu_tu_lay_hang, la_o_tran, la_o_chua_xep, suc_chua, suc_chua_dvt, cho_tron_mat_hang, cho_tron_lo |
| Location Generator | Prompt | thường | kho, khu, so_day, so_khoang_moi_day, so_tang_moi_khoang, so_o_moi_tang, so_o_da_tao |
| Warehouse Location Setup | `field:kho` | thường | kho (duy nhất), trang_thai, o_chua_xep, ngay_bat, ngay_tat, so_dong_chuyen_doi, so_lo_chuyen_doi, lan_doi_soat_cuoi, ket_qua_doi_soat |
| Location Ledger Entry | hash | sổ | ngay, thoi_diem, kho, o, vat_tu, so_lo, so_luong, chung_tu_type, chung_tu, chung_tu_row, sle, da_huy, company |
| Location Balance | hash | bộ đệm | o, kho, vat_tu, so_lo, so_luong, cap_nhat_luc — **khoá duy nhất (o, vat_tu, so_lo)** |
| Item Location Preference | `field:vat_tu` | thường | vat_tu, kho, vi_tri, cap_do, ghi_chu |
| Location Transfer | `XVT-.YYYY.-` | duyệt được | kho, ngay, items, ghi_chu |
| Location Transfer Item | — | bảng con | vat_tu, so_lo, tu_o, den_o, so_luong |
| Batch Entry | `PNL-.YYYY.-` | duyệt được | phieu_nhap, cong_ty, ngay, nha_cung_cap, items, ghi_chu |
| Batch Entry Item | — | bảng con | dong_phieu_nhap (ẩn), vat_tu, ten_hang, kho, so_luong, so_lo, ngay_san_xuat, hsd, o_goi_y, ly_do_goi_y, lo_da_tao, so_goi |

`Location Allocation` (bảng con trên phiếu giao) và trường `Delivery Note.custom_phan_bo_vi_tri`
thuộc tài liệu lấy hàng.

#### 3.3.2 Trường tuỳ biến trên doctype ERPNext

| Doctype | Trường | Kiểu | Thuộc tính |
|---|---|---|---|
| Warehouse | `custom_quan_ly_vi_tri` | Check | chỉ đọc, có index |
| Batch | `custom_so_goi` | Data | chỉ đọc |
| Batch | `custom_o_in_tem` | Link Storage Location | chỉ đọc |
| Item | `custom_thong_so_tem` | Data(60) | sửa được |

#### 3.3.3 Quy tắc dữ liệu

| Mã | Quy tắc |
|---|---|
| VTK-DL-01 | Hàng không lô lưu lô là **chuỗi rỗng**, không NULL (để khoá duy nhất có hiệu lực) |
| VTK-DL-02 | Vị trí của một lô **không** lưu trên `Batch`; nó suy từ gán vị trí + gợi ý. Ngoại lệ duy nhất là `custom_o_in_tem` — bản ghi của một sự kiện đã xảy ra (tem đã in) |
| VTK-DL-03 | Bộ đệm tồn luôn dựng lại được từ sổ; không có dữ liệu nào chỉ nằm ở bộ đệm |
| VTK-DL-04 | Một ô từng in tem không xoá được khi còn lô trỏ tới (ràng buộc Link). Muốn bỏ thì đặt "Ngừng dùng" |

---

### 3.4 Yêu cầu phi chức năng

Bảng nào dưới đây không có cột **Kiểm chứng** thì phương pháp là `I` (soát mã).

#### 3.4.1 Toàn vẹn dữ liệu

| Mã | Yêu cầu | Kiểm chứng |
|---|---|---|
| VTK-NF-01 | **Bất biến tồn**: với mọi (mặt hàng, lô, kho đã bật), tổng tồn các ô = tồn kho ERPNext, sau mọi loại chứng từ (ghi, huỷ) | T `test_hook_nhap`, `test_pr_dn_tich_hop`, `test_doi_soat` |
| VTK-NF-02 | Không trạng thái nửa vời: bật kho, sinh ô, phiếu xếp, xếp PDA, ghi theo phân bổ đều là tất cả hoặc không (savepoint riêng, không dựa vào rollback của request) | T `test_bat_kho`, `test_sinh_ma`, `test_phieu_xep_vi_tri`, `test_xep_pda` |
| VTK-NF-03 | Phép chặn tồn âm **PHẢI** đặt **sau** khi ghi (đọc lại trong cùng giao dịch), để hai người cùng rút một ô không vượt qua được | T `test_phieu_xep_vi_tri` |
| VTK-NF-04 | Không có dòng tồn ma khi ghi đồng thời: khoá duy nhất + upsert nguyên tử (VTK-SO-03) | T `test_so_vi_tri` |
| VTK-NF-05 | Mọi thao tác ghi đè / phá huỷ phải có bài kiểm thử với **chốt âm** (khẳng định cả thứ phải còn nguyên) | I |

#### 3.4.2 Độ tin cậy

| Mã | Yêu cầu |
|---|---|
| VTK-NF-06 | Hook ghi sổ không bao giờ tự chặn một giao dịch kho hợp lệ vì lệch làm tròn: mọi so sánh số lượng dùng ngưỡng sai số (1e-6 khi chia lô, 1e-4 khi đối soát, 1e-9 khi kiểm số còn xếp được) |
| VTK-NF-07 | Lỗi của một bản ghi không được làm hỏng cả danh sách (lấy hàng chưa xếp, nạp dòng phiếu nhập lô, xem trước tem, quét). Lỗi ghi Error Log |
| VTK-NF-08 | Tiêu đề Error Log **PHẢI** được cắt về ≤ 140 ký tự kèm đuôi "…(cắt)", để chính việc ghi log không gây lỗi mới |
| VTK-NF-09 | Việc dựng cây ở `after_migrate` không được làm vỡ migrate của bất kỳ site nào |

#### 3.4.3 Bảo mật

| Mã | Yêu cầu |
|---|---|
| VTK-NF-10 | Theo VTK-QH-01, VTK-QH-02. Lý do: site có tài khoản khách hàng cổng (`Website User`) đang hoạt động; `@frappe.whitelist()` mặc định chỉ đòi đăng nhập |
| VTK-NF-11 | Mọi dữ liệu người dùng gõ (số lô, mã hàng) nhúng vào thông báo HTML hoặc trang in **PHẢI** được escape. *Chưa có bài test tự động; kiểm chứng bằng soát mã* |
| VTK-NF-12 | Không hàm nào của trang PDA hay nút trên form được bỏ qua DocPerm của doctype nó ghi (không `ignore_permissions`), trừ xoá phiếu nháp rỗng do chính người gọi tạo |

#### 3.4.4 Hiệu năng

| Mã | Yêu cầu |
|---|---|
| VTK-NF-13 | Hook ghi sổ đọc cờ kho từ cache, không truy vấn thêm cho kho chưa bật |
| VTK-NF-14 | `dam_bao_cay_da_dung` thoát sau đúng một câu đếm khi cây đã đủ toạ độ |
| VTK-NF-15 | Cây chọn vị trí nạp theo từng cấp, không nạp cả cây |
| VTK-NF-16 | Mã vạch của một ô vẽ một lần cho mọi bản in của ô đó; bộ vẽ dựng một lần cho cả xấp |

#### 3.4.5 In ấn (tiêu chí đo được)

| Mã | Yêu cầu | Kiểm chứng |
|---|---|---|
| VTK-NF-17 | Module mã vạch = **0,25 mm = 2 dot** trên 203 dpi, không bao giờ nhỏ hơn. Vùng yên tĩnh ≥ **2,5 mm** mỗi đầu | A |
| VTK-NF-18 | Khổ trang in: tem vị trí 45 × 25 mm và 50 × 30 mm, không có trang trắng thừa cuối xấp | A — số đo trên **bản PDF** (45,13 × 25,06 và 50,12 × 29,97 mm) lấy từ `HDSD-quan-ly-vi-tri-kho.md` mục 3; **chưa** đo trên giấy in từ ZD421 (NT-01) |
| VTK-NF-19 | Chữ trên nhãn lô không bị xén (gồm chữ hoa có dấu chồng tầng, chữ có đuôi g/p/y, số gọi 5 chữ số). Bước làm tròn của Chrome là 0,265 mm nên mọi khoảng hở **NÊN** ≥ một bước | A — đo ảnh chụp ×10 trên Chrome khi sửa lỗi ở commit `ba6b921a` (17/09/2026) |

#### 3.4.6 Khả năng bảo trì

| Mã | Yêu cầu |
|---|---|
| VTK-NF-20 | Mã upstream chỉ bị chạm ở: `hooks.py` (doctype_js × 4: Warehouse, Batch, Purchase Receipt, Item · after_migrate × 1 · doc_events: SLE.on_submit, Batch.before_insert, Batch.validate, Purchase Receipt.before_submit, Item.after_rename; cộng một móc `Delivery Note.validate` của phần lấy hàng), `modules.txt`, `patches.txt`, `purchase_receipt.py` (1 dòng), 2 patch trong `erpnext/patches/v15_0/`. Mọi thứ khác nằm trong `erpnext/warehouse_operations/` và `erpnext/public/js/warehouse_operations/` |
| VTK-NF-21 | Các dòng trong `hooks.py` là **dễ mất nhất** khi merge ERPNext bản mới; mất chúng thì hệ vẫn chạy nhưng không ghi sổ / không có nút, không báo lỗi. `test_app_khoi_dong` và `test_giao_dien` **PHẢI** khoá sự có mặt của chúng |
| VTK-NF-22 | Mỗi luật nghiệp vụ có **một** định nghĩa: định dạng mã (`ma_vi_tri.py`), luật ngừng dùng thừa kế (`fefo._dieu_kien_ngung_dung`), đếm module (`ma_vach.py`), tồn kho theo lô (`doi_soat.ton_kho_theo_lo`), dạng ô "Chưa xếp vị trí" (`kho.kiem_tra_dang_o_chua_xep`), bộ vẽ tem (`tem_vi_tri.js`), trình tự in nhãn (`in_nhan_lo.js`) |
| VTK-NF-23 | Giao thức giữa máy chủ và giao diện dùng **khoá/cờ** (`loai`, `tem_hong`), không so khớp chuỗi hiển thị (chuỗi đi qua `_()` dịch được) |

#### 3.4.7 Khả dụng

| Mã | Yêu cầu |
|---|---|
| VTK-NF-24 | Thông báo tiếng Việt, nêu đích danh ô / mặt hàng / lô / số lượng và việc cần làm tiếp |
| VTK-NF-25 | Lý do khác nhau phải hiện khác nhau (chưa gán / vùng đã đầy / lỗi gợi ý; đã gán / có gán bên trong / đang ngừng dùng); không gộp thành một câu chung |
| VTK-NF-26 | Nốt, nút hay lựa chọn không dùng được phải thấy **trước** khi bấm, không để người dùng bấm rồi mới nhận lỗi |

---

## 4. Kiểm chứng

### 4.1 Phương pháp

| Phương pháp | Áp dụng |
|---|---|
| Kiểm thử tự động | Tại commit `8b1ccdea`: 35 module, 522 bài trong `erpnext/warehouse_operations/tests/`. Trừ 60 bài của `test_lay_hang` (ngoài phạm vi) còn **462 bài** phủ phạm vi tài liệu này; 21 bài `test_fefo*` phủ luật ngừng dùng thừa kế (VTK-CAY-07) và giao diện với phần lấy hàng. Tài liệu này **không** chạy lại bộ test — kết quả chạy phải lấy khi nghiệm thu. Chạy: `bench --site erptest.local run-tests --module erpnext.warehouse_operations.tests.<tên>`, **tuần tự** (chung CSDL). Không chạy `--app erpnext` |
| Kiểm thử đột biến | Bắt buộc với các luật cấm im lặng (ngừng dùng thừa kế, chặn tồn âm, không sinh SLE, chồng lấn gán): tắt luật thì bài phải đỏ |
| Trình diễn | chạy luồng thật trên `erptest.local` (HDSD Phụ lục A, B; `HDSD-luong-tu-A-den-Z.md`) |
| Phân tích / đo | hình học tem đo trên bản in PDF và ảnh chụp ×10 |

### 4.2 Tiêu chí nghiệm thu chưa đạt — phải làm trước khi dùng thật

| # | Việc | Ai làm |
|---|---|---|
| NT-01 | In **một** nhãn lô và **một** tem vị trí trên **Zebra ZD421 thật**, tỉ lệ 100%, quét bằng máy quét của kho; chuỗi quét ra phải giống từng ký tự chuỗi in bằng chữ | chủ đầu tư |
| NT-02 | Thử ô quét trên **PDA thật** của kho (giữ focus, súng quét có/không Enter, rung) | chủ đầu tư |
| NT-03 | Chốt ngưỡng "cận date" (hiện tạm 90 ngày) | kho |
| NT-04 | Chốt `Stock Settings` → *Pick Serial / Batch Based On* (FIFO hay Expiry) | công ty |
| NT-05 | Sửa `Stock Settings` → *Default Warehouse* về kho đúng công ty | quản trị |
| NT-06 | Trình diễn mọi yêu cầu có phương pháp `D` trên `erptest.local`, ghi số chứng từ làm bằng chứng. Đã có bằng chứng chạy thật cho luồng nhập lô → in nhãn → xếp PDA (`HDSD-luong-tu-A-den-Z.md`, 18/09/2026) | kiểm thử |
| NT-07 | Chạy toàn bộ 462 bài trong phạm vi, tuần tự, và lưu kết quả | kỹ thuật |

### 4.3 Điều kiện triển khai lên site miyano

1. Patch `them_unique_location_balance` giả định bảng `Location Balance` **rỗng hoặc không trùng
   khoá**; kiểm trước khi migrate.
2. Thống nhất bảng phân bổ **Khu ↔ Kho** cho toàn công ty trước khi sinh ô (VTK-MA-06).
3. Sau `bench migrate`, kiểm `frappe.db.count("Storage Location", {"lft": 0, "rgt": 0}) == 0`.
4. Làm lại toàn bộ trình tự: sinh ô → bật kho → đối soát (HDSD mục 5).
5. Bộ test hiện ràng vào dữ liệu `erptest.local`, **không chạy được** trên `miyano`.

---

## Phụ lục A. Ma trận truy vết

| Nhóm yêu cầu | Mã nguồn chính | Kiểm thử |
|---|---|---|
| VTK-MA | `vitri/ma_vi_tri.py` | `test_ma_vi_tri` |
| VTK-CAY | `doctype/storage_location/storage_location.py`, `vitri/cay.py`, `vitri/fefo.py` (`_dieu_kien_ngung_dung`) | `test_cay_vi_tri`, `test_storage_location`, `test_fefo_pham_vi` |
| VTK-DM | `storage_location.py`, `vitri/sinh_ma.py`, `location_generator.js`, patch `don_loai_vi_tri_khong_hop_le` | `test_storage_location`, `test_sinh_ma` |
| VTK-KHO | `vitri/bat_kho.py`, `vitri/kho.py`, `warehouse_location_setup.*`, `public/js/warehouse_operations/warehouse.js` | `test_bat_kho`, `test_bat_kho_xem_truoc`, `test_tat_va_dong_bo`, `test_co_quan_ly_vi_tri`, `test_warehouse_location_setup` |
| VTK-SO | `vitri/hook_sle.py`, `vitri/so.py`, `vitri/delta.py`, `vitri/lo.py` | `test_hook_nhap`, `test_so_vi_tri`, `test_tinh_delta`, `test_tach_theo_lo`, `test_huy_chung_tu`, `test_landed_cost_voucher`, `test_pr_dn_tich_hop` |
| VTK-DS | `vitri/doi_soat.py` | `test_doi_soat` |
| VTK-BC | `report/*` | `test_bao_cao` |
| VTK-XEP | `doctype/location_transfer/*`, `vitri/xep.py::hang_chua_xep` | `test_phieu_xep_vi_tri` |
| VTK-GAN | `doctype/item_location_preference/*`, `vitri/gan.py`, `public/js/warehouse_operations/item.js`, `cay_chon_vi_tri.js` | `test_gan_vi_tri` |
| VTK-GY | `vitri/goi_y.py` | `test_goi_y_o` |
| VTK-LO | `doctype/batch_entry/*`, `vitri/nhap_lo.py`, `vitri/phieu_nhap.py`, `vitri/ma_vach.py`, `vitri/lo_ncc.py`, `public/js/warehouse_operations/purchase_receipt.js`, `purchase_receipt.py` | `test_nhap_lo`, `test_loi_vao_nhap_lo`, `test_ma_vach`, `test_lo_ncc` |
| VTK-TVT | `vitri/tem.py`, `public/js/warehouse_operations/tem_vi_tri.js`, `storage_location.js`, `storage_location_tree.js` | `test_tem` |
| VTK-TL | `vitri/nhap_lo.py` (`du_lieu_tem`, `dat_o_in_tem`), `public/js/warehouse_operations/tem_lo.js`, `in_nhan_lo.js`, `batch.js` | `test_nhap_lo` |
| VTK-QUET | `vitri/quet.py`, `page/quet_ma_tra_cuu/*`, `public/js/warehouse_operations/o_quet.js` | `test_quet` |
| VTK-PDA | `vitri/xep.py` (phần PDA), `page/xep_hang_pda/*`, `o_quet.js` | `test_xep_pda` |
| VTK-QH | DocPerm các doctype, `_kiem_tra_quyen` ở từng module | `test_phan_quyen` |
| VTK-NF-08 | `vitri/nhat_ky_loi.py` | `test_nhat_ky_loi` |
| VTK-NF-21 | `erpnext/hooks.py` | `test_app_khoi_dong`, `test_giao_dien` |

## Phụ lục B. Các thông báo chính người dùng sẽ gặp

| Tình huống | Nội dung (rút gọn) | Yêu cầu |
|---|---|---|
| Mã ô sai chuẩn | "Mã vị trí không đúng chuẩn: … phải đúng 10 ký tự … ví dụ 1B01040302" | VTK-MA-04 |
| Khu trùng kho khác | "nút nhóm … đã thuộc kho …, không phải kho …" | VTK-CAY-04 |
| Sinh ô trùng | "N mã ô đã tồn tại nên không sinh ô nào cả" | VTK-DM-09 |
| Bật lại kho đã tắt | "phải chạy Đồng bộ lại trước, không bật thẳng được" | VTK-KHO-07 |
| Xếp vào nhánh tắt | "không xếp hàng vào … được vì … đang Ngừng dùng" | VTK-XEP-05 |
| Ô nguồn không đủ | "Ô … không đủ hàng: mặt hàng …, lô … sẽ còn …" | VTK-XEP-09 |
| Gán chồng lấn | "Vị trí … nằm trong nhánh … đã được gán cho mặt hàng …" | VTK-GAN-04 |
| Số lô có dấu | "Số lô '…' có ký tự '…' (U+…) ở vị trí N … ĐỪNG xoá bớt ký tự" | VTK-LO-05 |
| Số lô quá dài | "… cần N module mã vạch nhưng nhãn 50×30 chỉ chứa được 188 module" | VTK-LO-06 |
| Phiếu nhập đã duyệt | "Phiếu nhập … đã duyệt nên không gắn được số lô nữa" | VTK-LO-04 |
| Duyệt phiếu nhập có lô gõ tay | "Chưa khai lô qua phiếu nhập lô … bấm nút Nhập lô & in nhãn" | VTK-LO-13 |
| In quá nhiều tem | "Lần in này ra N tem …, vượt trần 500" | VTK-TVT-10 |

## Phụ lục C. Vấn đề mở và sai lệch giữa tài liệu cũ và mã

### C.1 Sai lệch phát hiện khi viết tài liệu này

| # | Chỗ | Nói gì | Mã thật | Đề xuất |
|---|---|---|---|---|
| C-01 | Form **Location Generator** | Trường "Mẫu mã sinh ra" mặc định `[Kho][Khu][Dãy][Khoang][Tầng][Ô] — ví dụ K11B01040302`; mô tả trường Khu: "Hai ký tự đầu của mã (mã kho) lấy tự động từ phiếu kho" | Mã 10 ký tự, không có mã kho (từ 11/09/2026) | Sửa hai chuỗi trong `location_generator.json` — màn hình đang nói sai chuẩn mã |
| C-02 | `HDSD-luong-tu-A-den-Z.md` | "số **gói**" | Trường tên "Số **gọi**" (`custom_so_goi`) | Sửa HDSD |
| C-03 | Spec 09/09 §5.1 | `Storage Location.kho` "phải là kho đã bật quản lý vị trí" | Chỉ chặn kho tổng; sinh ô **trước** khi bật kho là trình tự đúng (HDSD mục 5) | Giữ mã, coi spec đã lỗi thời |
| C-04 | Spec 16/09 §6.1, mockup SPD | Nhãn "bố cục A", mã vạch cột trái 28 mm | Bố cục A đã bỏ (thiếu vùng yên tĩnh), chủ đầu tư chốt 16/09/2026 | Đã chấp nhận |
| C-05 | Spec 16/09 §12 | Không chặn ô lô chuẩn trên phiếu nhập | Từ 17/09/2026 chặn duyệt ở kho đã bật (VTK-LO-13) | Mã đúng theo quyết định mới |
| C-06 | Spec 16/09 §7 | Ô quét trên form Batch Entry | Trang riêng `quet-ma-tra-cuu` từ 17/09/2026 | Mã đúng |
| C-07 | Spec 09/09 §5.5 | `la_o_chinh`, `so_luong_toi_da` trên gán vị trí | Cố ý bỏ (spec 15/09 §2) | Mã đúng |

### C.2 Vấn đề mở đã biết

| # | Vấn đề | Mức | Ghi chú |
|---|---|---|---|
| M-01 | Một mặt hàng chỉ gán được ở **một kho** | trung bình, kích hoạt khi bật kho thứ hai | phải đổi `autoname` sang `{vat_tu}-{kho}` kèm patch đổi tên |
| M-02 | Mỗi lần chạy bộ sinh, thứ tự lấy hàng đánh lại từ 1 — khu sinh sau trùng số thứ tự với khu trước | thấp | cần quyết định quy ước đánh số khi có khu thứ hai |
| M-03 | Trạng thái "Cần đồng bộ lại" không nơi nào trong mã đặt; không có đối soát định kỳ (`scheduler_events`) | thấp | làm cùng nhau |
| M-04 | Phép chặn "nút cha thuộc kho khác" chỉ đi chiều con → cha; nút Khu (gốc) đổi được `kho` mà không kiểm con cháu | thấp, kích hoạt khi bật kho thứ hai | |
| M-05 | Purchase Invoice, Sales Invoice, Subcontracting Receipt, Asset Capitalization chưa có kiểm thử tích hợp ghi sổ vị trí; Material Transfer chưa có kiểm thử huỷ thật | trung bình | hook bắt được theo thiết kế, chưa đo |
| M-06 | Repost Item Valuation với `recreate_stock_ledgers = 1` cho chứng từ **xuất** có thể chọn lại ô khác ô đã lấy | hẹp | ERPNext cấm bật cờ đó cho hàng có lô |
| M-07 | Lô tạo trước 16/09/2026 có thể mang ký tự ngoài ASCII (không có mã vạch); lô tạo ngoài phiếu nhập lô không có số gọi | thấp | cần một patch rà `Batch.batch_id` nếu muốn dọn |
| M-08 | Cổng `khop` cho "lệch bộ đệm" chưa có bài kiểm khoá riêng | nợ kiểm thử | |
| M-09 | Tem vị trí dùng line-height 1,05–1,2 với mã ASCII — chưa đo xén chữ như nhãn lô | thấp | |

## Phụ lục D. Lịch sử hình thành

| Ngày | Mốc |
|---|---|
| 09/09/2026 | Bắt đầu, app riêng `miyano_wms`; chủ đầu tư chọn phương án B |
| 10/09/2026 | Bật `Kho Miyano - MYN` trên `erptest.local` (mã 12 ký tự) |
| 11/09/2026 | Mã 10 ký tự, cây suy từ mã, ngừng dùng thừa kế; chuyển vào app `erpnext` |
| 14/09/2026 | Phiếu xếp / chuyển vị trí; tem vị trí bố cục SPD |
| 15–16/09/2026 | Gán vị trí cố định, gợi ý ô, báo cáo hàng nằm sai vị trí |
| 16/09/2026 | Phiếu nhập lô, nhãn lô 50×30 (bỏ bố cục A), quét mã tra cứu |
| 17/09/2026 | Nút Nhập lô & in nhãn, chặn lô gõ tay, gán vị trí trên form Item, trang Quét mã tra cứu và Xếp hàng trên PDA, sửa nhãn lô bị xén chữ |
| 18/09/2026 | HDSD theo luồng A→Z; tài liệu này (mốc `8b1ccdea`) |

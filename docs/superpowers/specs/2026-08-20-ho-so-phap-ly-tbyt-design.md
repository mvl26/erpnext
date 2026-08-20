# Hồ sơ pháp lý TBYT — sổ đăng ký chứng từ theo số lưu hành

> Trạng thái: **DRAFT — chờ duyệt.** Giai đoạn Specify.
> Nguồn: `docs/ma-tran-chung-tu-tbyt-theo-phan-loai.md` (ma trận 23 chứng từ × 4 phân loại).
> Thiết kế này **bác bỏ §5.5 của tài liệu nguồn** và thay bằng mô hình khác — lý do ở §2.

## 1. Mục tiêu

Mỗi mặt hàng TBYT phải tra được trọn bộ hồ sơ pháp lý của nó: đủ hay thiếu, hết hạn khi nào,
file nằm ở đâu. File tải lên phải tự vào đúng thư mục và tự mang tên có nghĩa, không phụ
thuộc người dùng đặt tên đúng.

Ràng buộc bao trùm: **một tờ giấy chỉ được tồn tại đúng một lần trong hệ thống.**

## 2. Vấn đề gốc — vì sao không làm theo §5.5 tài liệu nguồn

§5.5 đề xuất child table `Item Regulatory Document` với trường `Attach` gắn thẳng lên Item.
Mô hình này sinh trùng lặp có hệ thống.

Frappe **đã** chống trùng ở mức file vật lý: `frappe/core/doctype/file/file.py:712-731` băm nội
dung (`content_hash`), trùng thì trỏ chung `file_url`. Upload 1 file CFS lên 300 item → 1 file
trên đĩa, **300 dòng `File`**. Nên vấn đề không phải dung lượng, mà là **300 bản metadata độc
lập**: mỗi bản một `ngay_het_han`, một `so_hieu`, một `status`. CFS gia hạn → phải sửa 300 chỗ,
sót 1 chỗ là báo cáo tuân thủ sai.

### Chỉ 2/23 chứng từ thật sự thuộc về một Item

Xét theo **chủ thể pháp lý được cấp giấy**, không theo chỗ ta muốn hiển thị:

| Chủ thể sở hữu tờ giấy | SL | Hệ số trùng nếu gắn Item |
|---|:--:|---|
| Công ty (Miyano) | 1 | × toàn bộ item B/C/D |
| Chủ sở hữu / nhà sản xuất | 6 | × số item của hãng đó |
| Số lưu hành / số công bố | 10 | × số size, chủng loại dùng chung 1 số |
| Lô hàng | 3 | × số lô |
| Giao dịch | 1 | × số đơn |
| **Item (thật sự 1–1)** | **2** | — |

**Thực thể đang thiếu là "Số lưu hành".** Ngành TBYT dán hồ sơ pháp lý vào *số lưu hành*, không
dán vào SKU. Bơm tiêm 1ml/3ml/5ml/10ml = 4 Item nhưng chung 1 số công bố, 1 bản phân loại,
1 HDSD. ERP không mô hình hóa số lưu hành → mọi chứng từ của nó bị chép xuống từng SKU.
Đó là cỗ máy sinh trùng lặp.

### Cách giải: phân giải theo chuỗi, không sao chép

```
Item ──> Số lưu hành TBYT ──> Chủ sở hữu ──> Công ty
            (A/B/C/D)
   Hồ sơ gắn vào đúng cấp của nó; Item phân giải ngược chuỗi để dựng bộ đầy đủ.
```

Hệ quả đo được:
- Gia hạn CFS → sửa **1** record, mọi item cập nhật ngay.
- Thêm size mới dưới số lưu hành đã có → thừa hưởng **17/23** chứng từ, chỉ nhập 2 chứng từ giá.
- `phan_loai_tbyt` suy từ số lưu hành → hai item cùng số lưu hành **không thể** khai lệch loại.

## 3. Quyết định đã chốt

| # | Quyết định | Ghi chú |
|---|---|---|
| 1 | Hướng **A — sổ đăng ký + DocType Số lưu hành**, không dùng child table Attach trên Item | Người dùng, sau khi nghe phân tích §2 |
| 2 | Thiếu chứng từ → **chỉ cảnh báo, không chặn** ở bất kỳ đâu | Người dùng |
| 3 | `so_luu_hanh` trên Item → **bắt buộc** khi `la_thiet_bi_y_te` | Người dùng |
| 4 | BB\* bắt buộc khi **Miyano không phải chủ sở hữu số lưu hành** | Người dùng |
| 5 | Cho tạo bản ghi số lưu hành trạng thái **"Đang đăng ký"** | Người dùng |
| 6 | Cấp lưu trữ: Item + Chủ sở hữu + Số lưu hành + Công ty + Lô | Suy từ §2 |

**Ranh giới của quyết định 2 và 3:** chặn ở *quan hệ pháp lý* (khai một lần bằng link), cảnh
báo ở *file* (phụ thuộc nhà cung cấp gửi, về dần). Không mâu thuẫn nhau.

## 4. Mô hình dữ liệu

Module mới `erpnext/tbyt/`, thêm `TBYT` vào `erpnext/modules.txt`. Theo tiền lệ module
`Einvoice` — một năng lực lớn, tự chứa, có DocType + report + setup riêng.

### 4.1. `TBYT Document Type` — danh mục 23 loại chứng từ

| Trường | Kiểu | Ghi chú |
|---|---|---|
| `document_key` | Data, unique | `cfs_giay_luu_hanh`, … — khớp mã trường tài liệu nguồn |
| `short_code` | Data | `CFS`, `ISO13485`, `HDSD` — dùng đặt tên file |
| `document_name` | Data | Tên tiếng Việt đầy đủ |
| `scope_level` | Select | `Company` / `Owner` / `Authorization` / `Batch` / `Item` / `Transaction` |
| `has_expiry` | Check | Có theo dõi ngày hết hạn không |
| `rules` | Table → `TBYT Document Rule` | 4 dòng, mỗi phân loại một dòng |

`autoname: field:document_key`.

### 4.2. `TBYT Document Rule` — child table, mức áp dụng theo phân loại

| Trường | Kiểu |
|---|---|
| `device_class` | Select: A / B / C / D |
| `level` | Select: `BB` / `BB*` / `NC` / `TH` / `KHONG_AP_DUNG` |
| `condition` | Small Text — chỉ dùng cho `BB*` |

Đây là câu trả lời cho §5.1 tài liệu nguồn: **không hard-code 4 fieldset.** Bộ Y tế sửa thông
tư → mở record ra sửa dòng rule, không migrate, không đụng code. Tổng 23 × 4 = **92 dòng**.

### 4.3. `TBYT Marketing Authorization` — số lưu hành, thực thể trung tâm

| Trường | Kiểu | Ghi chú |
|---|---|---|
| `so_luu_hanh` | Data, unique | Số thật; **để trống được** khi đang đăng ký |
| `loai_hinh` | Select | `Số công bố tiêu chuẩn` (A, B) / `Số đăng ký lưu hành` (C, D) |
| `phan_loai` | Select: A/B/C/D | **reqd** — nguồn sự thật cho phân loại |
| `chu_so_huu` | Link → Manufacturer | reqd |
| `miyano_la_chu_so_huu` | Check | Điều khiển nhóm BB\* |
| `hang_nhap_khau` | Check | Điều kiện phụ cho CFS |
| `trang_thai` | Select | `Đang đăng ký` / `Còn hiệu lực` / `Hết hiệu lực` / `Bị thu hồi` |
| `ngay_cap`, `ngay_het_han` | Date | Trống khi đang đăng ký |

**Đặt tên: naming series `TBYT-LH-.YYYY.-.#####`, không lấy `so_luu_hanh` làm tên document.**
Lý do kỹ thuật: số lưu hành thật hay chứa dấu `/` (`220000123/PCBA-HN`) sẽ hỏng routing URL của
Frappe. Bù lại đặt `title_field = so_luu_hanh` + `show_title_field_in_link = 1` để giao diện vẫn
hiển thị số thật ở mọi link field.

`ngay_cap` bắt buộc khi `trang_thai != "Đang đăng ký"`, qua `mandatory_depends_on`.

### 4.4. `TBYT Regulatory Document` — sổ đăng ký, 1 record = 1 tờ giấy

| Trường | Kiểu | Ghi chú |
|---|---|---|
| `document_type` | Link → `TBYT Document Type` | reqd |
| `company` | Link → Company | `depends_on` scope_level = Company |
| `chu_so_huu` | Link → Manufacturer | scope_level = Owner |
| `so_luu_hanh` | Link → `TBYT Marketing Authorization` | scope_level = Authorization |
| `batch` | Link → Batch | scope_level = Batch |
| `item` | Link → Item | scope_level = Item |
| `so_hieu` | Data | Số hiệu trên tờ giấy |
| `ngay_cap`, `ngay_het_han` | Date | |
| `file` | Attach | reqd |
| `trang_thai` | Select | `Còn hiệu lực` / `Sắp hết hạn` / `Hết hạn` / `Đã thay thế` — read-only |
| `thay_the_cho` | Link → chính nó | Bản bị thay thế khi gia hạn |
| `is_active` | Check, default 1 | |

Chỉ **một** ô phạm vi được hiện và bắt buộc, suy từ `scope_level` của `document_type` —
`validate` chặn cứng việc điền sai ô hoặc điền nhiều ô.

Trả lời câu 3 §6 tài liệu nguồn: gia hạn = tạo record mới trỏ `thay_the_cho` về bản cũ; bản cũ
chuyển `is_active = 0`, `trang_thai = "Đã thay thế"` — **không ghi đè**, lịch sử vẫn tra được.

## 5. Phân bổ 23 chứng từ về đúng chủ thể

| Cấp | SL | `document_key` |
|---|:--:|---|
| **Công ty** | 1 | `cong_bo_dk_mua_ban` |
| **Chủ sở hữu** | 6 | `thong_tin_bao_hanh`, `giay_uy_quyen_csh`, `giay_xac_nhan_bao_hanh`, `cfs_giay_luu_hanh`, `iso_13485_nha_san_xuat`, `uy_quyen_nhap_khau` |
| **Số lưu hành** | 10 | `ban_ket_qua_phan_loai`, `so_cong_bo_tieu_chuan`, `gcn_dang_ky_luu_hanh`, `giay_phep_nhap_khau`, `mau_nhan_hang_hoa`, `hdsd_tieng_viet`, `tai_lieu_ky_thuat_bao_duong`, `tai_lieu_ky_thuat_csdt`, `hop_chuan_hop_quy`, `danh_gia_chat_luong_ivd` |
| **Lô** | 3 | `cq_chung_nhan_chat_luong`, `co_chung_nhan_xuat_xu`, `ket_qua_kiem_dinh` |
| **Item** | 2 | `niem_yet_gia`, `ke_khai_gia` |
| **Giao dịch** | 1 | `ho_so_phan_phoi` — ngoài phạm vi, xem §11 |

**Hai điểm lệch so với §5.4 tài liệu nguồn, có chủ ý:**

1. `co_chung_nhan_xuat_xu` (CO) chuyển từ cấp Item xuống **cấp Lô** — CO cấp theo chuyến hàng,
   một CO liệt kê nhiều mặt hàng. Gắn Item là sai bản chất và sinh trùng theo số lô.
2. `thong_tin_bao_hanh` lên **cấp Chủ sở hữu** — thông tin cơ sở bảo hành là của hãng, dùng
   chung mọi mặt hàng của hãng đó.

## 6. Thay đổi trên Item

Sửa trực tiếp `erpnext/stock/doctype/item/item.json` (golden rule: bẻ core cho vừa nghiệp vụ).
Thêm tab **"Hồ sơ TBYT"** đặt sau tab `quality_tab`:

| Trường | Kiểu | Ràng buộc |
|---|---|---|
| `la_thiet_bi_y_te` | Check | `fetch_from` cờ `la_tbyt` mới trên Item Group, cho phép sửa tay |
| `so_luu_hanh` | Link → `TBYT Marketing Authorization` | `mandatory_depends_on = "eval:doc.la_thiet_bi_y_te"` |
| `phan_loai_tbyt` | Data, read-only | `fetch_from = so_luu_hanh.phan_loai` |
| `tinh_trang_ho_so` | Data, read-only | `Đủ` / `Thiếu N chứng từ` / `Có N chứng từ hết hạn` |
| `ho_so_tbyt_html` | HTML | Bảng chứng từ đã phân giải |

Khuôn mẫu `mandatory_depends_on` đã có tiền lệ ngay trong `item.json`: `asset_category` bắt buộc
khi `is_fixed_asset` (44 file JSON trong repo dùng cơ chế này).

Thêm cờ `la_tbyt` (Check) trên Item Group. Site đã có sẵn 3 nhóm TBYT: *Vật tư y tế tiêu hao*,
*Hóa chất - sinh phẩm*, *Thiết bị y tế và phụ kiện*.

Bảng HTML liệt kê: tên chứng từ · mức (BB/BB\*/NC) · cấp lưu · số hiệu · ngày hết hạn · trạng
thái · link mở file · nút tải lên nếu thiếu.

## 7. Cây thư mục File

```
Home/TBYT/
├── 01-Cong-ty/<Company>/
├── 02-Chu-so-huu/<Manufacturer>/
├── 03-So-luu-hanh/<so_luu_hanh | tên document nếu chưa có số>/
├── 04-Lo/<Batch ID>/
└── 05-Item/<Item code>/
```

Tiền tố số giữ cây đúng thứ tự trong giao diện File. Mọi file đặt `is_private = 1`.

### Quy ước tên file

```
{short_code}__{so_hieu}__{ngay_cap}.{ext}
```

Ví dụ trong `Home/TBYT/03-So-luu-hanh/BYT-CB-01234-2026/`:

```
PL__PL-2026-0087__2026-01-12.pdf
CBTC__220000123-PCBA-HN__2026-02-03.pdf
HDSD__khong-so__2026-02-03.pdf
_Luu-tru/
└── HDSD__khong-so__2024-05-10.pdf      ← bản đã bị thay thế
```

Nhìn tên file biết ngay chứng từ gì, số nào, cấp ngày nào — không cần mở ERP. `so_hieu` được
slug hóa (bỏ dấu, `/` → `-`); trống thì dùng `khong-so`.

Record chuyển `is_active = 0` → file tự dời vào `_Luu-tru/` cùng thư mục.

## 8. Xử lý

### 8.1. `resolver.py` — phân giải, không sao chép

```
get_item_documents(item_code) -> list[ResolvedDocument]
```

1. Đọc `so_luu_hanh` của Item → lấy `phan_loai`, `chu_so_huu`, `miyano_la_chu_so_huu`, `hang_nhap_khau`.
2. Lấy toàn bộ `TBYT Document Type` kèm rule khớp `device_class = phan_loai`.
3. Bỏ rule mức `TH` và `KHONG_AP_DUNG` (theo quy tắc lọc tài liệu nguồn).
4. Với mỗi loại còn lại, tìm `TBYT Regulatory Document` `is_active = 1` ở đúng cấp:
   Company → `company`; Owner → `chu_so_huu`; Authorization → `so_luu_hanh`; Item → `item`.
5. Trả về mức, record tìm được (hoặc `None`), trạng thái hiệu lực.

**Chứng từ cấp Lô không tính vào trạng thái của Item** — kiểm ở Batch, vì item chưa có lô thì
không có gì để thiếu. Item đánh giá 19 loại (1 + 6 + 10 + 2), trừ những loại `TH`/không áp dụng
theo phân loại.

### 8.2. Điều kiện nhóm BB\*

Bắt buộc khi `miyano_la_chu_so_huu = 0`:
`giay_uy_quyen_csh`, `giay_xac_nhan_bao_hanh`, `cfs_giay_luu_hanh`.
Riêng `cfs_giay_luu_hanh` thêm điều kiện `hang_nhap_khau = 1`.

Lưu trong `TBYT Document Rule.condition` dạng biểu thức đánh giá trên bối cảnh số lưu hành —
sửa được bằng dữ liệu, không phải sửa code.

### 8.3. `validate` trên Item — cảnh báo, không chặn

Hook qua `doc_events` trong `hooks.py` (Item hiện chưa có entry `doc_events` nào — thêm mới).

- Thiếu `BB` → `frappe.msgprint(indicator="red")`, **vẫn lưu**.
- Thiếu `BB*` thỏa điều kiện → `msgprint(indicator="orange")`.
- Thiếu `NC` → gộp một dòng `indicator="blue"`.
- `trang_thai = "Đang đăng ký"` → một dòng riêng "Chưa có số lưu hành", không liệt kê thiếu gì.

Gộp tất cả thành **một** `msgprint` để không dội hộp thoại.

### 8.4. `folders.py` — quản lý cây thư mục

Dùng `frappe.core.api.file.create_new_folder` sẵn có của Frappe — hàm này đã tự idempotent
bằng `insert(ignore_if_duplicate=True)`, không cần bọc try/except. Hàm chính:

- `ensure_folder(scope_level, scope_value) -> str` — trả đường dẫn folder, tạo nếu chưa có.
- `place_file(doc)` — đặt `File.folder`, đổi tên theo §7, gọi khi `TBYT Regulatory Document` lưu.
- `archive_file(doc)` — dời vào `_Luu-tru/` khi `is_active = 0`.

Đổi tên chủ sở hữu / số lưu hành → `on_update` đổi tên folder tương ứng.

### 8.5. Scheduled job hằng ngày

`erpnext.tbyt.expiry.update_document_status` thêm vào `scheduler_events["daily"]`:

1. Cập nhật `trang_thai` mọi `TBYT Regulatory Document` theo `ngay_het_han`
   (ngưỡng "Sắp hết hạn": 90 ngày, để trong `constants.py`).
2. Cập nhật `trang_thai` số lưu hành khi `ngay_het_han` đã qua.
3. Cập nhật `tinh_trang_ho_so` các Item bị ảnh hưởng.
4. Gửi thông báo tổng hợp chứng từ sắp hết hạn.

## 9. Report

**"Tình trạng hồ sơ pháp lý TBYT"** (`erpnext/tbyt/report/`) — Query/Script Report:

Cột: Item · Nhóm · Số lưu hành · Phân loại · Trạng thái SLH · Số chứng từ BB thiếu ·
Số BB\* thiếu · Số NC thiếu · Chứng từ hết hạn · Ngày hết hạn gần nhất.

Lọc theo phân loại, chủ sở hữu, nhóm hàng, chỉ-hiện-thiếu. Vì đã chốt **không chặn**, report
này là cơ chế kiểm soát chính — cần làm kỹ, không phải phụ kiện.

## 10. Seed dữ liệu

`erpnext/tbyt/setup.py` — `setup_tbyt_masters()` tạo 23 `TBYT Document Type` + 92 dòng rule,
idempotent. Gọi từ patch `erpnext/patches/v15_0/seed_tbyt_document_types.py`.

Bảng nguồn chép nguyên từ §2 tài liệu gốc. **`hop_chuan_hop_quy` phải kiểm riêng** (§5.2 tài
liệu nguồn): `NC` ở A/B nhưng `TH` ở C/D — copy nhầm danh sách A sang C là sai.

Site hiện có 2 Item, 0 variant → **không cần patch di trú dữ liệu**.

## 11. Ngoài phạm vi

- `ho_so_phan_phoi` (cấp giao dịch) — dùng đính kèm sẵn có của Delivery Note / Sales Invoice.
  Hợp đồng, hóa đơn, phiếu xuất đã là chứng từ trong ERP, không phải file cần quản hạn.
- Chặn nghiệp vụ khi thiếu chứng từ — đã chốt không làm.
- Vòng đời thiết bị sau bán hàng — thuộc `assetcore`.

## 12. Kiểm thử

`erpnext/tbyt/tests/`:

| File | Nội dung |
|---|---|
| `test_resolver.py` | Phân giải đủ 4 phân loại; ca `hop_chuan_hop_quy` lật mức A/B ↔ C/D; BB\* bật/tắt theo `miyano_la_chu_so_huu`; CFS theo `hang_nhap_khau` |
| `test_folders.py` | Đường dẫn từng cấp; slug số hiệu có dấu `/`; dời `_Luu-tru/`; đổi tên folder khi đổi tên chủ sở hữu |
| `test_item_validate.py` | Cảnh báo chứ không chặn; `so_luu_hanh` bắt buộc khi `la_thiet_bi_y_te`; trạng thái "Đang đăng ký" |
| `test_expiry.py` | Chuyển trạng thái theo ngưỡng 90 ngày; chuỗi thay thế `thay_the_cho` |

Ca then chốt: **thêm item thứ hai vào cùng số lưu hành → 17 chứng từ tự có, số dòng
`TBYT Regulatory Document` không tăng.** Đây là bài kiểm tra trực tiếp cho mục tiêu chống trùng.

## 13. Rủi ro

| Rủi ro | Giảm thiểu |
|---|---|
| Nhập số lưu hành trở thành cửa ải khi tạo item | Cho trạng thái "Đang đăng ký", chỉ cần phân loại + chủ sở hữu |
| `Manufacturer` hiện trống trên site (0 bản ghi) | Nhập chủ sở hữu là việc bắt buộc trước khi dùng; ghi vào runbook |
| Đã chốt không chặn → hồ sơ có thể thiếu lâu dài | Report §9 + thông báo hằng ngày là cơ chế bù |
| Bảng rule seed sai ở `hop_chuan_hop_quy` | Test riêng cho ca này (§12) |

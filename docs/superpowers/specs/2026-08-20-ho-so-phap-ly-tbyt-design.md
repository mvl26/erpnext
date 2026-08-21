# Hồ sơ pháp lý TBYT — sổ đăng ký chứng từ theo số lưu hành

> Trạng thái: **DRAFT — chờ duyệt.** Giai đoạn Specify.
> Nguồn: `docs/ma-tran-chung-tu-tbyt-theo-phan-loai.md` (ma trận 23 chứng từ × 4 phân loại).
> Bản sửa **2026-08-21** — vá 6 lỗi tìm được khi kiểm toán bản đầu, xem §14.
> Thiết kế này **bác bỏ §5.5 của tài liệu nguồn** và thay bằng mô hình khác — lý do ở §2.

## 1. Mục tiêu

Mỗi mặt hàng TBYT phải tra được trọn bộ hồ sơ pháp lý của nó: đủ hay thiếu, hết hạn khi nào,
file nằm ở đâu. File tải lên phải tự vào đúng thư mục và tự mang tên có nghĩa, không phụ
thuộc người dùng đặt tên đúng.

Bốn ràng buộc bao trùm, mọi quyết định dưới đây phục vụ chúng:

| # | Ràng buộc | Cơ chế bảo đảm |
|---|---|---|
| R1 | Theo dõi được **thiếu** và **hết hạn**; chứng từ **có hạn hoặc vô thời hạn** | §4.4 tri-state, §8.5, §8.6 |
| R2 | **Một tờ giấy tồn tại đúng một lần** | §4.5 phủ nhiều phạm vi, §8.2 chặn trùng |
| R3 | Phân loại khác nhau → bộ chứng từ khác nhau | §4.2 bảng rule 23×4 |
| R4 | Chứng từ thiếu tạm thời được; **chỉ số lưu hành bắt buộc** | §6, §8.4 |

## 2. Vấn đề gốc — vì sao không làm theo §5.5 tài liệu nguồn

§5.5 đề xuất child table `Item Regulatory Document` với trường `Attach` gắn thẳng lên Item.
Mô hình này sinh trùng lặp có hệ thống, phá R2.

Frappe **đã** chống trùng ở mức file vật lý: `frappe/core/doctype/file/file.py:712-731` băm nội
dung (`content_hash`), trùng thì trỏ chung `file_url`. Upload 1 file CFS lên 300 item → 1 file
trên đĩa, **300 dòng `File`**. Nên vấn đề không phải dung lượng, mà là **300 bản metadata độc
lập**: mỗi bản một `ngay_het_han`, một `so_hieu`, một `trang_thai`. CFS gia hạn → phải sửa 300
chỗ, sót 1 chỗ là báo cáo tuân thủ sai.

### Chỉ 2/23 chứng từ thật sự thuộc về một Item

Xét theo **chủ thể pháp lý mà tờ giấy nói về**, không theo chỗ ta muốn hiển thị:

| Chủ thể | SL | Hệ số trùng nếu gắn thẳng Item |
|---|:--:|---|
| Công ty (Miyano) | 1 | × toàn bộ item B/C/D |
| Chủ sở hữu / cơ sở sản xuất | 2 | × số item của hãng đó |
| Số lưu hành / số công bố | 14 | × số size, chủng loại dùng chung 1 số |
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
| 1 | Hướng **A — sổ đăng ký + DocType Số lưu hành**, không dùng child table Attach trên Item | Người dùng, sau phân tích §2 |
| 2 | Thiếu chứng từ → **chỉ cảnh báo, không chặn** ở bất kỳ đâu | Người dùng |
| 3 | `so_luu_hanh` trên Item → **bắt buộc** khi `la_thiet_bi_y_te` | Người dùng |
| 4 | BB\* bắt buộc khi **Miyano không phải chủ sở hữu số lưu hành** | Người dùng |
| 5 | Cho tạo bản ghi số lưu hành trạng thái **"Đang đăng ký"** | Người dùng |
| 6 | Một chứng từ **phủ được nhiều phạm vi** | Người dùng, 2026-08-21 — xem §4.5 |

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
| `cho_phep_nhieu_pham_vi` | Check | Một tờ giấy phủ được nhiều đối tượng cùng cấp — xem §4.5 |
| `mac_dinh_co_thoi_han` | Check | **Chỉ là giá trị gợi ý** khi tạo record mới |
| `rules` | Table → `TBYT Document Rule` | 4 dòng, mỗi phân loại một dòng |

`autoname: field:document_key`.

**`mac_dinh_co_thoi_han` không phải quyền quyết định.** Có hạn hay không là thuộc tính của
*từng tờ giấy*, không phải của loại: số lưu hành loại C/D nay nhiều giấy cấp **vô thời hạn**
trong khi giấy cùng loại cấp trước đó vẫn có hạn. Quyền quyết định nằm ở `khong_thoi_han` trên
record (§4.4). Trường này chỉ để form điền sẵn cho đỡ thao tác.

### 4.2. `TBYT Document Rule` — child table, mức áp dụng theo phân loại

| Trường | Kiểu |
|---|---|
| `device_class` | Select: A / B / C / D |
| `level` | Select: `BB` / `BB*` / `NC` / `TH` / `KHONG_AP_DUNG` |
| `condition` | Small Text — chỉ dùng cho `BB*` |

Đây là câu trả lời cho §5.1 tài liệu nguồn và là cơ chế của **R3**: **không hard-code 4
fieldset.** Bộ Y tế sửa thông tư → mở record ra sửa dòng rule, không migrate, không đụng code.
Tổng 23 × 4 = **92 dòng**.

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
| `khong_thoi_han` | Check | Số lưu hành cấp vô thời hạn |
| `ngay_cap` | Date | reqd khi `trang_thai != "Đang đăng ký"` |
| `ngay_het_han` | Date | reqd khi không phải `Đang đăng ký` **và** `khong_thoi_han = 0` |

**Đặt tên: naming series `TBYT-LH-.YYYY.-.#####`, không lấy `so_luu_hanh` làm tên document.**
Lý do kỹ thuật: số lưu hành thật hay chứa dấu `/` (`220000123/PCBA-HN`) sẽ hỏng routing URL của
Frappe. Bù lại đặt `title_field = so_luu_hanh` + `show_title_field_in_link = 1` để giao diện vẫn
hiển thị số thật ở mọi link field.

### 4.4. `TBYT Regulatory Document` — sổ đăng ký, 1 record = 1 tờ giấy

| Trường | Kiểu | Ghi chú |
|---|---|---|
| `document_type` | Link → `TBYT Document Type` | reqd |
| `pham_vi` | Table → `TBYT Document Scope` | reqd, ≥1 dòng — xem §4.5 |
| `so_hieu` | Data | Số hiệu trên tờ giấy |
| `ngay_cap` | Date | reqd |
| `khong_thoi_han` | Check | Tờ giấy này cấp vô thời hạn; mặc định theo `mac_dinh_co_thoi_han` |
| `ngay_het_han` | Date | `mandatory_depends_on = "eval:!doc.khong_thoi_han"` |
| `file` | Attach | reqd |
| `trang_thai` | Select | `Còn hiệu lực` / `Sắp hết hạn` / `Hết hạn` / `Đã thay thế` — read-only |
| `thay_the_cho` | Link → chính nó | Bản bị thay thế khi gia hạn |
| `is_active` | Check, default 1 | |

**Ba trạng thái hiệu lực tách bạch — đây là cơ chế của R1:**

| `khong_thoi_han` | `ngay_het_han` | Nghĩa |
|:--:|:--:|---|
| 1 | trống | **Vô thời hạn** — job bỏ qua, không bao giờ cảnh báo |
| 0 | có ngày | **Có hạn** — job theo dõi theo ngưỡng §8.5 |
| 0 | trống | **Không lưu được** — `mandatory_depends_on` chặn |

Nếu để `ngay_het_han` trống mang cả hai nghĩa "vô thời hạn" và "chưa nhập" thì job hoặc báo động
giả hàng loạt, hoặc im lặng bỏ sót giấy sắp hết hạn. Cả hai đều phá hỏng mục tiêu chính.

Trả lời câu 3 §6 tài liệu nguồn: gia hạn = tạo record mới trỏ `thay_the_cho` về bản cũ; bản cũ
chuyển `is_active = 0`, `trang_thai = "Đã thay thế"` — **không ghi đè**, lịch sử vẫn tra được.

### 4.5. `TBYT Document Scope` — child table phạm vi, cơ chế của R2

| Trường | Kiểu | Ghi chú |
|---|---|---|
| `scope_doctype` | Link → DocType, read-only | Suy từ `scope_level` của loại chứng từ |
| `scope_name` | Dynamic Link, options = `scope_doctype` | reqd |

Ánh xạ `scope_level` → `scope_doctype`: `Company` → Company; `Owner` → Manufacturer;
`Authorization` → TBYT Marketing Authorization; `Batch` → Batch; `Item` → Item.

**Vì sao phải là bảng chứ không phải một Link.** CFS, giấy ủy quyền chủ sở hữu, giấy xác nhận
đủ điều kiện bảo hành và giấy ủy quyền nhập khẩu do chủ sở hữu cấp nhưng **liệt kê theo sản
phẩm**, và một tờ thường phủ nhiều số lưu hành. Mô hình một-phạm-vi-cố-định kẹt hai đầu:

- Xếp lên **cấp Chủ sở hữu** → mọi item của hãng tự nhận "Đủ CFS", kể cả mặt hàng không hề nằm
  trong tờ CFS đó. Đây là **báo "Đủ" sai** — nguy hiểm hơn báo thiếu, vì không ai kiểm tra lại
  cái đang xanh.
- Ép xuống **cấp Số lưu hành, mỗi số một record** → một CFS phủ 5 số phải tạo 5 record.
  **Trùng lặp, phá R2.**

Bảng phạm vi thoát cả hai: **một record, N dòng phạm vi.** Không trùng, và không nhận vơ.

`cho_phep_nhieu_pham_vi = 0` → `validate` bắt buộc đúng 1 dòng (mặc định cho 19/23 loại).
`= 1` → cho nhiều dòng, áp dụng cho 4 loại kể trên.
Mọi dòng phải cùng `scope_doctype`, khớp `scope_level` của loại chứng từ.

## 5. Phân bổ 23 chứng từ về đúng chủ thể

| Cấp | SL | Nhiều phạm vi | `document_key` |
|---|:--:|:--:|---|
| **Công ty** | 1 | — | `cong_bo_dk_mua_ban` |
| **Chủ sở hữu** | 2 | — | `thong_tin_bao_hanh`, `iso_13485_nha_san_xuat` |
| **Số lưu hành** | 14 | 4 loại ✓ | `ban_ket_qua_phan_loai`, `so_cong_bo_tieu_chuan`, `gcn_dang_ky_luu_hanh`, `giay_phep_nhap_khau`, `mau_nhan_hang_hoa`, `hdsd_tieng_viet`, `tai_lieu_ky_thuat_bao_duong`, `tai_lieu_ky_thuat_csdt`, `hop_chuan_hop_quy`, `danh_gia_chat_luong_ivd`, **`cfs_giay_luu_hanh`**, **`giay_uy_quyen_csh`**, **`giay_xac_nhan_bao_hanh`**, **`uy_quyen_nhap_khau`** |
| **Lô** | 3 | — | `cq_chung_nhan_chat_luong`, `co_chung_nhan_xuat_xu`, `ket_qua_kiem_dinh` |
| **Item** | 2 | — | `niem_yet_gia`, `ke_khai_gia` |
| **Giao dịch** | 1 | — | `ho_so_phan_phoi` — ngoài phạm vi, xem §11 |

Bốn `document_key` in đậm là nhóm `cho_phep_nhieu_pham_vi = 1`.

**Ba điểm lệch so với §5.4 tài liệu nguồn, có chủ ý:**

1. `co_chung_nhan_xuat_xu` (CO) chuyển từ cấp Item xuống **cấp Lô** — CO cấp theo chuyến hàng,
   một CO liệt kê nhiều mặt hàng. Gắn Item là sai bản chất và sinh trùng theo số lô.
2. `thong_tin_bao_hanh` lên **cấp Chủ sở hữu** — thông tin cơ sở bảo hành là của hãng, dùng
   chung mọi mặt hàng của hãng đó.
3. Bốn chứng từ do chủ sở hữu cấp nhưng liệt kê theo sản phẩm nằm ở **cấp Số lưu hành**, không
   phải cấp Chủ sở hữu — lý do đầy đủ ở §4.5.

Con số then chốt **không đổi** sau điều chỉnh 3: vẫn 17/23 chứng từ được thừa hưởng khi thêm
size mới (1 + 2 + 14), vẫn 19 loại được đánh giá ở cấp Item (17 + 2).

## 6. Thay đổi trên Item

Sửa trực tiếp `erpnext/stock/doctype/item/item.json` (golden rule: bẻ core cho vừa nghiệp vụ).
Thêm tab **"Hồ sơ TBYT"** đặt sau tab `quality_tab`:

| Trường | Kiểu | Ràng buộc |
|---|---|---|
| `la_thiet_bi_y_te` | Check | `fetch_from` cờ `la_tbyt` mới trên Item Group, cho phép sửa tay |
| `so_luu_hanh` | Link → `TBYT Marketing Authorization` | `mandatory_depends_on = "eval:doc.la_thiet_bi_y_te"` |
| `phan_loai_tbyt` | Data, read-only | `fetch_from = so_luu_hanh.phan_loai` |
| `tinh_trang_ho_so` | Select, read-only | 6 giá trị, xem dưới |
| `ho_so_tbyt_html` | HTML | Bảng chứng từ đã phân giải |

Khuôn mẫu `mandatory_depends_on` đã có tiền lệ ngay trong `item.json`: `asset_category` bắt buộc
khi `is_fixed_asset` (44 file JSON trong repo dùng cơ chế này). Đây là cơ chế của **R4** — ràng
buộc duy nhất cứng trong toàn thiết kế.

Thêm cờ `la_tbyt` (Check) trên Item Group. Site đã có sẵn 3 nhóm TBYT: *Vật tư y tế tiêu hao*,
*Hóa chất - sinh phẩm*, *Thiết bị y tế và phụ kiện*.

### `tinh_trang_ho_so` — thứ tự ưu tiên, nặng nhất trước

| Giá trị | Điều kiện |
|---|---|
| `Số lưu hành hết hiệu lực` | SLH `Hết hiệu lực` hoặc `Bị thu hồi` |
| `Chưa có số lưu hành` | SLH `Đang đăng ký` |
| `Có chứng từ hết hạn` | ≥1 chứng từ BB/BB\* đã quá `ngay_het_han` |
| `Thiếu chứng từ bắt buộc` | ≥1 BB hoặc BB\* thỏa điều kiện chưa có record |
| `Sắp hết hạn` | ≥1 chứng từ vào ngưỡng cảnh báo |
| `Đủ hồ sơ mặt hàng` | Không rơi vào các trường hợp trên |

Nhãn cuối cố ý **không phải "Đủ"**. Chứng từ cấp Lô không tính vào trạng thái Item (§8.1), mà
`cq_chung_nhan_chat_luong` và `co_chung_nhan_xuat_xu` đều là **BB ở cả 4 phân loại** — nói "Đủ"
trong khi chưa có CQ lẫn CO là nói dối. Trạng thái cấp lô hiển thị riêng trên Batch và có cột
riêng trong report §9.

Bảng HTML liệt kê: tên chứng từ · mức (BB/BB\*/NC/TH) · cấp lưu · số hiệu · ngày hết hạn hoặc
nhãn *Vô thời hạn* · trạng thái · link mở file · nút tải lên nếu thiếu.

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

**Chứng từ phủ nhiều phạm vi đặt ở thư mục chủ sở hữu** (`02-Chu-so-huu/<hãng>/`) — vì một file
không thể nằm ở hai thư mục, và cả 4 loại đa phạm vi đều do chủ sở hữu cấp. Nguyên tắc:
**thư mục theo nơi cấp giấy, phân giải theo nơi giấy phủ.** Thư mục chỉ phục vụ người duyệt
tay; việc xác định item nào có chứng từ nào hoàn toàn do §8.1 quyết định, không đọc thư mục.
`validate` kiểm mọi số lưu hành trong bảng phạm vi cùng một `chu_so_huu`.

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
slug hóa (bỏ dấu, `/` → `-`); trống thì dùng `khong-so`. `ngay_cap` là reqd nên luôn có.

Record chuyển `is_active = 0` → file tự dời vào `_Luu-tru/` cùng thư mục.

## 8. Xử lý

### 8.1. `resolver.py` — phân giải, không sao chép

```
get_item_documents(item_code) -> list[ResolvedDocument]
```

1. Đọc `so_luu_hanh` của Item → lấy `phan_loai`, `chu_so_huu`, `miyano_la_chu_so_huu`,
   `hang_nhap_khau`, `trang_thai`.
2. Lấy toàn bộ `TBYT Document Type` kèm rule khớp `device_class = phan_loai`.
3. Với mỗi loại, tìm `TBYT Regulatory Document` `is_active = 1` có **dòng phạm vi trỏ đúng
   đối tượng**: `Company` → company của item; `Owner` → `chu_so_huu`; `Authorization` →
   số lưu hành của item; `Item` → chính item.
4. Ghép mức và record thành kết quả:

| Mức | Có record | Không có record |
|---|---|---|
| `BB`, `BB*` (thỏa điều kiện) | Trả về, theo dõi hạn | **Tính là thiếu** |
| `BB*` (không thỏa điều kiện) | Trả về, theo dõi hạn | Bỏ qua |
| `NC` | Trả về, theo dõi hạn | Cảnh báo nhẹ |
| `TH` | **Trả về, theo dõi hạn**, gắn nhãn *bổ sung* | **Bỏ qua, không tính thiếu** |
| `KHONG_AP_DUNG` | Cảnh báo dữ liệu sai | Bỏ qua |

Dòng `TH` là điểm sửa so với bản đầu. §4 tài liệu nguồn nói rõ chứng từ TH *"vẫn nên giữ trong
danh mục master để đính kèm thủ công khi phát sinh"*. Nếu resolver loại bỏ TH từ đầu thì
`ket_qua_kiem_dinh` hay `ke_khai_gia` tải lên rồi **không hiện trên Item và không được theo dõi
hết hạn** — tải lên coi như mất.

**Chứng từ cấp Lô không tính vào trạng thái của Item** — kiểm ở Batch, vì item chưa có lô thì
không có gì để thiếu. Item đánh giá 19 loại (1 + 2 + 14 + 2), trừ những loại không áp dụng
theo phân loại. Hệ quả về cách gọi tên trạng thái đã xử lý ở §6.

### 8.2. Chặn trùng — cơ chế của R2

`validate` trên `TBYT Regulatory Document`:

1. Với mỗi dòng phạm vi, tìm record khác cùng `document_type`, `is_active = 1`, có dòng phạm vi
   trỏ cùng đối tượng → **`frappe.throw`**, chỉ tên record đang giữ chỗ và nhắc dùng
   `thay_the_cho` nếu đây là bản gia hạn.
2. Trùng `content_hash` với record đang hiệu lực → `msgprint` cảnh báo (không chặn: cùng một
   file quét chung nhiều loại giấy là chuyện có thật).
3. `cho_phep_nhieu_pham_vi = 0` mà có >1 dòng phạm vi → `throw`.
4. Dòng phạm vi sai `scope_doctype` so với `scope_level` của loại → `throw`.

Không có bước 1 thì hai record `cfs_giay_luu_hanh` cùng hiệu lực cho một chủ sở hữu vẫn lưu
được, và §8.1 bước 3 trở thành **không tất định** — hai lần mở cùng một Item có thể ra hai ngày
hết hạn khác nhau tùy thứ tự DB trả về.

### 8.3. Điều kiện nhóm BB\*

Bắt buộc khi `miyano_la_chu_so_huu = 0`:
`giay_uy_quyen_csh`, `giay_xac_nhan_bao_hanh`, `cfs_giay_luu_hanh`.
Riêng `cfs_giay_luu_hanh` thêm điều kiện `hang_nhap_khau = 1`.

Lưu trong `TBYT Document Rule.condition` dạng biểu thức đánh giá trên bối cảnh số lưu hành —
sửa được bằng dữ liệu, không phải sửa code.

### 8.4. `validate` trên Item — cảnh báo, không chặn

Hook qua `doc_events` trong `hooks.py` (Item hiện chưa có entry `doc_events` nào — thêm mới).

- SLH `Hết hiệu lực` / `Bị thu hồi` → `msgprint(indicator="red")`, dòng đầu tiên.
- SLH `Đang đăng ký` → dòng "Chưa có số lưu hành", **không liệt kê thiếu gì** (chưa có phân
  loại chắc chắn thì liệt kê là gây nhiễu).
- Thiếu `BB` → đỏ. Thiếu `BB*` thỏa điều kiện → cam. Thiếu `NC` → gộp một dòng xanh.
- Chứng từ đã hết hạn → đỏ, liệt kê riêng khỏi nhóm thiếu.

Gộp tất cả thành **một** `msgprint`. **Không bao giờ `throw`** — R4.

### 8.5. `folders.py` — quản lý cây thư mục

Dùng `frappe.core.api.file.create_new_folder` sẵn có của Frappe — hàm này đã tự idempotent
bằng `insert(ignore_if_duplicate=True)`, không cần bọc try/except. Hàm chính:

- `ensure_folder(scope_level, scope_value) -> str` — trả đường dẫn folder, tạo nếu chưa có.
- `place_file(doc)` — đặt `File.folder`, đổi tên theo §7; đa phạm vi thì về folder chủ sở hữu.
- `archive_file(doc)` — dời vào `_Luu-tru/` khi `is_active = 0`.

Đổi tên chủ sở hữu / số lưu hành → `on_update` đổi tên folder tương ứng.

### 8.6. Làm mới trạng thái khi chứng từ thay đổi

`doc_events` trên `TBYT Regulatory Document` (`on_update`, `on_trash`) và trên
`TBYT Marketing Authorization` (`on_update`) → `frappe.enqueue` làm mới `tinh_trang_ho_so` của
các Item bị ảnh hưởng, suy ngược từ bảng phạm vi.

Không có bước này thì trạng thái ôi tới 24 tiếng: 9h sáng upload CFS ở cấp chủ sở hữu, toàn bộ
item của hãng vẫn hiển thị "Thiếu CFS" cho tới khi job nửa đêm chạy. Người dùng vừa làm đúng
việc mà hệ thống vẫn báo đỏ — kiểu lỗi khiến người ta thôi tin vào chỉ báo.

Chạy nền vì một chứng từ cấp Chủ sở hữu có thể chạm rất nhiều Item.

### 8.7. Scheduled job hằng ngày

`erpnext.tbyt.expiry.update_document_status` thêm vào `scheduler_events["daily"]`:

1. Cập nhật `trang_thai` các `TBYT Regulatory Document` có `khong_thoi_han = 0` theo
   `ngay_het_han`. Ngưỡng "Sắp hết hạn" 90 ngày, để trong `constants.py`.
   **Record `khong_thoi_han = 1` bị loại khỏi truy vấn ngay từ đầu** — không bao giờ cảnh báo.
2. Cập nhật `trang_thai` số lưu hành khi `ngay_het_han` đã qua và `khong_thoi_han = 0`.
3. Cập nhật `tinh_trang_ho_so` các Item bị ảnh hưởng (lưới an toàn cho §8.6).
4. Gửi thông báo tổng hợp chứng từ sắp hết hạn và số lưu hành sắp hết hiệu lực.

## 9. Report

**"Tình trạng hồ sơ pháp lý TBYT"** (`erpnext/tbyt/report/`) — Query/Script Report:

Cột: Item · Nhóm · Số lưu hành · Phân loại · Trạng thái SLH · BB thiếu · BB\* thiếu · NC thiếu ·
Chứng từ hết hạn · Ngày hết hạn gần nhất · **Hồ sơ cấp lô** (đủ/thiếu CQ, CO theo lô còn tồn).

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
| `test_resolver.py` | Phân giải đủ 4 phân loại; `hop_chuan_hop_quy` lật mức A/B ↔ C/D; BB\* bật/tắt theo `miyano_la_chu_so_huu`; CFS theo `hang_nhap_khau`; **TH có record thì hiện, không record thì không tính thiếu** |
| `test_scope.py` | **Một CFS phủ 3 số lưu hành → cả 3 item đều "có", vẫn đúng 1 record**; chặn dòng phạm vi sai cấp; chặn >1 dòng khi `cho_phep_nhieu_pham_vi = 0` |
| `test_duplicate.py` | **Record thứ hai cùng loại cùng phạm vi bị `throw`**; gia hạn qua `thay_the_cho` thì không bị chặn; cảnh báo trùng `content_hash` |
| `test_expiry.py` | Tri-state: vô thời hạn không bao giờ cảnh báo; có hạn cảnh báo đúng ngưỡng 90 ngày; **`khong_thoi_han = 0` + `ngay_het_han` trống thì không lưu được** |
| `test_status.py` | 6 giá trị `tinh_trang_ho_so` đúng thứ tự ưu tiên; SLH hết hiệu lực đè mọi trạng thái khác |
| `test_refresh.py` | Upload chứng từ cấp Chủ sở hữu → item liên quan đổi trạng thái **ngay**, không chờ job |
| `test_folders.py` | Đường dẫn từng cấp; slug `so_hieu` có dấu `/`; dời `_Luu-tru/`; đa phạm vi về folder chủ sở hữu; đổi tên folder khi đổi tên chủ sở hữu |
| `test_item_validate.py` | Cảnh báo chứ không chặn; `so_luu_hanh` reqd khi `la_thiet_bi_y_te`; trạng thái "Đang đăng ký" không liệt kê thiếu |

Ca then chốt cho R2: **thêm item thứ hai vào cùng số lưu hành → 17 chứng từ tự có, số dòng
`TBYT Regulatory Document` không tăng.**

## 13. Rủi ro

| Rủi ro | Giảm thiểu |
|---|---|
| Nhập số lưu hành trở thành cửa ải khi tạo item | Trạng thái "Đang đăng ký", chỉ cần phân loại + chủ sở hữu |
| `Manufacturer` hiện trống trên site (0 bản ghi) | Nhập chủ sở hữu là việc bắt buộc trước khi dùng; ghi vào runbook |
| Đã chốt không chặn → hồ sơ có thể thiếu lâu dài | Report §9 + thông báo hằng ngày là cơ chế bù |
| Bảng rule seed sai ở `hop_chuan_hop_quy` | Test riêng (§12) |
| Người dùng quên tích `khong_thoi_han`, để trống ngày | Không lưu được — `mandatory_depends_on` chặn tại chỗ |
| Bảng phạm vi bị bỏ sót số lưu hành → item báo thiếu oan | Báo thiếu là lỗi an toàn; report §9 hiện ra để bổ sung |
| Đa phạm vi làm resolver chậm khi nhiều item | Truy vấn theo `scope_name` có index; làm mới chạy nền (§8.6) |

## 14. Nhật ký sửa

**2026-08-21 — vá 6 lỗi từ đợt kiểm toán đối chiếu R1–R4:**

| # | Lỗi | Vá ở |
|---|---|---|
| 1 | Không có gì chặn hai record cùng loại cùng phạm vi; resolver không tất định | §8.2 |
| 2 | Một-phạm-vi-cố-định không diễn tả được chứng từ phủ nhiều số lưu hành | §4.5, §5, §7 |
| 3 | `has_expiry` đặt trên loại thay vì trên tờ giấy; `ngay_het_han` trống nhập nhằng | §4.1, §4.3, §4.4, §8.7 |
| 4 | `tinh_trang_ho_so` ôi tới 24 tiếng vì thiếu hook trên chứng từ | §8.6 |
| 5 | Chứng từ mức TH bị resolver loại bỏ → tải lên rồi mất | §8.1 |
| 6 | Nhãn "Đủ" nói dối vì bỏ qua CQ/CO cấp lô; thiếu trạng thái SLH hết hiệu lực | §6, §9 |

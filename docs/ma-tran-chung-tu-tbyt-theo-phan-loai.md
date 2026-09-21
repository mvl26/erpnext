# Ma trận chứng từ TBYT theo phân loại A / B / C / D

> **Mục đích:** chuẩn hóa danh mục chứng từ pháp lý gắn vào Item (vật tư / thiết bị y tế) trên ERP.
> **Quy tắc lọc áp dụng:** chỉ đưa vào phân loại các mức **BB** và **NC**. Bỏ **TH** và **—**.
> **Quy ước tên trường:** đã bỏ tiền tố `doc_`.

---

## 1. Chú giải mức độ

| Ký hiệu | Ý nghĩa | Đưa vào phân loại? |
|---|---|---|
| `BB` | Bắt buộc | ✅ Có |
| `BB*` | Bắt buộc có điều kiện (thường áp dụng cho hàng nhập khẩu / Miyano không phải chủ sở hữu số lưu hành) | ✅ Có (kèm điều kiện) |
| `NC` | Nên có | ✅ Có |
| `TH` | Theo trường hợp | ❌ Không |
| `—` | Không áp dụng | ❌ Không |

---

## 2. Ma trận gốc đầy đủ (23 chứng từ)

| # | Mã trường | Tên chứng từ | A | B | C | D |
|---|---|---|:--:|:--:|:--:|:--:|
| 1 | `ban_ket_qua_phan_loai` | Bản kết quả phân loại thiết bị y tế (mẫu Phụ lục II TT 05/2022) | BB | BB | BB | BB |
| 2 | `so_cong_bo_tieu_chuan` | Phiếu tiếp nhận hồ sơ công bố tiêu chuẩn áp dụng (Số công bố tiêu chuẩn áp dụng) | BB | BB | — | — |
| 3 | `gcn_dang_ky_luu_hanh` | Giấy chứng nhận đăng ký lưu hành (Số lưu hành TBYT loại C, D) | — | — | BB | BB |
| 4 | `giay_phep_nhap_khau` | Giấy phép nhập khẩu (trường hợp chưa có số lưu hành) | — | — | TH | TH |
| 5 | `mau_nhan_hang_hoa` | Mẫu nhãn hàng hóa lưu hành tại Việt Nam | BB | BB | BB | BB |
| 6 | `hdsd_tieng_viet` | Hướng dẫn sử dụng bằng tiếng Việt | BB | BB | BB | BB |
| 7 | `thong_tin_bao_hanh` | Thông tin cơ sở bảo hành, điều kiện và thời gian bảo hành | BB | BB | BB | BB |
| 8 | `co_chung_nhan_xuat_xu` | Giấy chứng nhận xuất xứ (CO) | BB | BB | BB | BB |
| 9 | `cq_chung_nhan_chat_luong` | Giấy chứng nhận chất lượng (CQ) của từng lô | BB | BB | BB | BB |
| 10 | `ket_qua_kiem_dinh` | Kết quả kiểm định an toàn và tính năng kỹ thuật | TH | TH | TH | TH |
| 11 | `tai_lieu_ky_thuat_bao_duong` | Tài liệu kỹ thuật phục vụ sửa chữa, bảo dưỡng | BB | BB | BB | BB |
| 12 | `giay_uy_quyen_csh` | Giấy ủy quyền của chủ sở hữu TBYT cho tổ chức đứng tên công bố / đăng ký lưu hành | BB* | BB* | BB* | BB* |
| 13 | `giay_xac_nhan_bao_hanh` | Giấy xác nhận đủ điều kiện bảo hành do chủ sở hữu TBYT cấp | BB* | BB* | BB* | BB* |
| 14 | `cfs_giay_luu_hanh` | Giấy chứng nhận lưu hành tự do (CFS) / Giấy lưu hành — hàng nhập khẩu | BB* | BB* | BB* | BB* |
| 15 | `iso_13485_nha_san_xuat` | Giấy chứng nhận ISO 13485 của cơ sở sản xuất (còn hiệu lực) | NC | NC | NC | NC |
| 16 | `tai_lieu_ky_thuat_csdt` | Tài liệu mô tả tóm tắt kỹ thuật tiếng Việt (A, B) / Hồ sơ kỹ thuật chung ASEAN — CSDT (C, D) | NC | NC | NC | NC |
| 17 | `hop_chuan_hop_quy` | Giấy chứng nhận hợp chuẩn / Bản tiêu chuẩn chủ sở hữu công bố (A, B) — Giấy chứng nhận hợp quy (C, D có QCVN) | NC | NC | TH | TH |
| 18 | `danh_gia_chat_luong_ivd` | IVD: Giấy chứng nhận đánh giá chất lượng / giấy chứng nhận chất lượng do cơ quan có thẩm quyền VN cấp | — | — | TH | TH |
| 19 | `niem_yet_gia` | Thông tin niêm yết giá | BB | BB | BB | BB |
| 20 | `ke_khai_gia` | Hồ sơ kê khai giá | TH | TH | TH | TH |
| 21 | `ho_so_phan_phoi` | Hồ sơ phân phối (hợp đồng, hóa đơn, phiếu xuất — theo dõi phân phối) | BB | BB | BB | BB |
| 22 | `cong_bo_dk_mua_ban` | Phiếu tiếp nhận công bố đủ điều kiện mua bán TBYT (loại B, C, D) | — | BB | BB | BB |
| 23 | `uy_quyen_nhap_khau` | Giấy ủy quyền nhập khẩu của chủ sở hữu số lưu hành (nếu Miyano nhập khẩu nhưng không phải chủ sở hữu số lưu hành) | TH | TH | TH | TH |

---

## 3. Danh mục sau khi lọc — theo từng phân loại

### 3.1. Loại A — 16 chứng từ

| # | Mã trường | Tên chứng từ | Mức |
|---|---|---|:--:|
| 1 | `ban_ket_qua_phan_loai` | Bản kết quả phân loại thiết bị y tế | BB |
| 2 | `so_cong_bo_tieu_chuan` | Phiếu tiếp nhận hồ sơ công bố tiêu chuẩn áp dụng | BB |
| 3 | `mau_nhan_hang_hoa` | Mẫu nhãn hàng hóa lưu hành tại Việt Nam | BB |
| 4 | `hdsd_tieng_viet` | Hướng dẫn sử dụng bằng tiếng Việt | BB |
| 5 | `thong_tin_bao_hanh` | Thông tin cơ sở bảo hành, điều kiện và thời gian bảo hành | BB |
| 6 | `co_chung_nhan_xuat_xu` | Giấy chứng nhận xuất xứ (CO) | BB |
| 7 | `cq_chung_nhan_chat_luong` | Giấy chứng nhận chất lượng (CQ) của từng lô | BB |
| 8 | `tai_lieu_ky_thuat_bao_duong` | Tài liệu kỹ thuật phục vụ sửa chữa, bảo dưỡng | BB |
| 9 | `niem_yet_gia` | Thông tin niêm yết giá | BB |
| 10 | `ho_so_phan_phoi` | Hồ sơ phân phối | BB |
| 11 | `giay_uy_quyen_csh` | Giấy ủy quyền của chủ sở hữu TBYT | BB* |
| 12 | `giay_xac_nhan_bao_hanh` | Giấy xác nhận đủ điều kiện bảo hành | BB* |
| 13 | `cfs_giay_luu_hanh` | Giấy chứng nhận lưu hành tự do (CFS) | BB* |
| 14 | `iso_13485_nha_san_xuat` | Giấy chứng nhận ISO 13485 của cơ sở sản xuất | NC |
| 15 | `tai_lieu_ky_thuat_csdt` | Tài liệu mô tả tóm tắt kỹ thuật tiếng Việt | NC |
| 16 | `hop_chuan_hop_quy` | Giấy chứng nhận hợp chuẩn / Bản tiêu chuẩn chủ sở hữu công bố | NC |

**Tổng:** 10 BB + 3 BB\* + 3 NC

---

### 3.2. Loại B — 17 chứng từ

| # | Mã trường | Tên chứng từ | Mức |
|---|---|---|:--:|
| 1 | `ban_ket_qua_phan_loai` | Bản kết quả phân loại thiết bị y tế | BB |
| 2 | `so_cong_bo_tieu_chuan` | Phiếu tiếp nhận hồ sơ công bố tiêu chuẩn áp dụng | BB |
| 3 | `mau_nhan_hang_hoa` | Mẫu nhãn hàng hóa lưu hành tại Việt Nam | BB |
| 4 | `hdsd_tieng_viet` | Hướng dẫn sử dụng bằng tiếng Việt | BB |
| 5 | `thong_tin_bao_hanh` | Thông tin cơ sở bảo hành, điều kiện và thời gian bảo hành | BB |
| 6 | `co_chung_nhan_xuat_xu` | Giấy chứng nhận xuất xứ (CO) | BB |
| 7 | `cq_chung_nhan_chat_luong` | Giấy chứng nhận chất lượng (CQ) của từng lô | BB |
| 8 | `tai_lieu_ky_thuat_bao_duong` | Tài liệu kỹ thuật phục vụ sửa chữa, bảo dưỡng | BB |
| 9 | `niem_yet_gia` | Thông tin niêm yết giá | BB |
| 10 | `ho_so_phan_phoi` | Hồ sơ phân phối | BB |
| 11 | `cong_bo_dk_mua_ban` | Phiếu tiếp nhận công bố đủ điều kiện mua bán TBYT | BB |
| 12 | `giay_uy_quyen_csh` | Giấy ủy quyền của chủ sở hữu TBYT | BB* |
| 13 | `giay_xac_nhan_bao_hanh` | Giấy xác nhận đủ điều kiện bảo hành | BB* |
| 14 | `cfs_giay_luu_hanh` | Giấy chứng nhận lưu hành tự do (CFS) | BB* |
| 15 | `iso_13485_nha_san_xuat` | Giấy chứng nhận ISO 13485 của cơ sở sản xuất | NC |
| 16 | `tai_lieu_ky_thuat_csdt` | Tài liệu mô tả tóm tắt kỹ thuật tiếng Việt | NC |
| 17 | `hop_chuan_hop_quy` | Giấy chứng nhận hợp chuẩn / Bản tiêu chuẩn chủ sở hữu công bố | NC |

**Tổng:** 11 BB + 3 BB\* + 3 NC
**Khác biệt so với loại A:** thêm duy nhất `cong_bo_dk_mua_ban`.

---

### 3.3. Loại C — 16 chứng từ

| # | Mã trường | Tên chứng từ | Mức |
|---|---|---|:--:|
| 1 | `ban_ket_qua_phan_loai` | Bản kết quả phân loại thiết bị y tế | BB |
| 2 | `gcn_dang_ky_luu_hanh` | Giấy chứng nhận đăng ký lưu hành (Số lưu hành) | BB |
| 3 | `mau_nhan_hang_hoa` | Mẫu nhãn hàng hóa lưu hành tại Việt Nam | BB |
| 4 | `hdsd_tieng_viet` | Hướng dẫn sử dụng bằng tiếng Việt | BB |
| 5 | `thong_tin_bao_hanh` | Thông tin cơ sở bảo hành, điều kiện và thời gian bảo hành | BB |
| 6 | `co_chung_nhan_xuat_xu` | Giấy chứng nhận xuất xứ (CO) | BB |
| 7 | `cq_chung_nhan_chat_luong` | Giấy chứng nhận chất lượng (CQ) của từng lô | BB |
| 8 | `tai_lieu_ky_thuat_bao_duong` | Tài liệu kỹ thuật phục vụ sửa chữa, bảo dưỡng | BB |
| 9 | `niem_yet_gia` | Thông tin niêm yết giá | BB |
| 10 | `ho_so_phan_phoi` | Hồ sơ phân phối | BB |
| 11 | `cong_bo_dk_mua_ban` | Phiếu tiếp nhận công bố đủ điều kiện mua bán TBYT | BB |
| 12 | `giay_uy_quyen_csh` | Giấy ủy quyền của chủ sở hữu TBYT | BB* |
| 13 | `giay_xac_nhan_bao_hanh` | Giấy xác nhận đủ điều kiện bảo hành | BB* |
| 14 | `cfs_giay_luu_hanh` | Giấy chứng nhận lưu hành tự do (CFS) | BB* |
| 15 | `iso_13485_nha_san_xuat` | Giấy chứng nhận ISO 13485 của cơ sở sản xuất | NC |
| 16 | `tai_lieu_ky_thuat_csdt` | Hồ sơ kỹ thuật chung ASEAN — CSDT | NC |

**Tổng:** 11 BB + 3 BB\* + 2 NC

---

### 3.4. Loại D — 16 chứng từ

Danh mục **giống hệt loại C**, không khác trường nào.

| # | Mã trường | Tên chứng từ | Mức |
|---|---|---|:--:|
| 1 | `ban_ket_qua_phan_loai` | Bản kết quả phân loại thiết bị y tế | BB |
| 2 | `gcn_dang_ky_luu_hanh` | Giấy chứng nhận đăng ký lưu hành (Số lưu hành) | BB |
| 3 | `mau_nhan_hang_hoa` | Mẫu nhãn hàng hóa lưu hành tại Việt Nam | BB |
| 4 | `hdsd_tieng_viet` | Hướng dẫn sử dụng bằng tiếng Việt | BB |
| 5 | `thong_tin_bao_hanh` | Thông tin cơ sở bảo hành, điều kiện và thời gian bảo hành | BB |
| 6 | `co_chung_nhan_xuat_xu` | Giấy chứng nhận xuất xứ (CO) | BB |
| 7 | `cq_chung_nhan_chat_luong` | Giấy chứng nhận chất lượng (CQ) của từng lô | BB |
| 8 | `tai_lieu_ky_thuat_bao_duong` | Tài liệu kỹ thuật phục vụ sửa chữa, bảo dưỡng | BB |
| 9 | `niem_yet_gia` | Thông tin niêm yết giá | BB |
| 10 | `ho_so_phan_phoi` | Hồ sơ phân phối | BB |
| 11 | `cong_bo_dk_mua_ban` | Phiếu tiếp nhận công bố đủ điều kiện mua bán TBYT | BB |
| 12 | `giay_uy_quyen_csh` | Giấy ủy quyền của chủ sở hữu TBYT | BB* |
| 13 | `giay_xac_nhan_bao_hanh` | Giấy xác nhận đủ điều kiện bảo hành | BB* |
| 14 | `cfs_giay_luu_hanh` | Giấy chứng nhận lưu hành tự do (CFS) | BB* |
| 15 | `iso_13485_nha_san_xuat` | Giấy chứng nhận ISO 13485 của cơ sở sản xuất | NC |
| 16 | `tai_lieu_ky_thuat_csdt` | Hồ sơ kỹ thuật chung ASEAN — CSDT | NC |

**Tổng:** 11 BB + 3 BB\* + 2 NC

---

## 4. Chứng từ bị loại khỏi cả 4 phân loại

Các chứng từ dưới đây mang mức TH hoặc — ở toàn bộ A/B/C/D nên **không đưa vào cấu hình phân loại**, nhưng vẫn nên giữ trong danh mục master để đính kèm thủ công khi phát sinh:

| Mã trường | Tên chứng từ | Lý do loại |
|---|---|---|
| `giay_phep_nhap_khau` | Giấy phép nhập khẩu | — (A, B) / TH (C, D) |
| `ket_qua_kiem_dinh` | Kết quả kiểm định an toàn và tính năng kỹ thuật | TH toàn bộ |
| `danh_gia_chat_luong_ivd` | IVD: Giấy chứng nhận đánh giá chất lượng | — (A, B) / TH (C, D) |
| `ke_khai_gia` | Hồ sơ kê khai giá | TH toàn bộ |
| `uy_quyen_nhap_khau` | Giấy ủy quyền nhập khẩu của chủ sở hữu số lưu hành | TH toàn bộ |

`hop_chuan_hop_quy` là trường hợp đặc biệt: **có mặt ở A, B (NC)** nhưng **bị loại ở C, D (TH)**.

---

## 5. Ghi chú kỹ thuật khi triển khai

### 5.1. Thực chất chỉ có 3 bộ quy tắc

- A và B chỉ lệch đúng 1 dòng: `cong_bo_dk_mua_ban`
- C và D giống nhau 100%

→ Không nên hard-code 4 fieldset. Nên dựng bảng rule `(document_type, device_class, level)` để khi Bộ Y tế sửa thông tư chỉ cần sửa dữ liệu, không phải sửa code và migrate.

### 5.2. Trường dễ sai: `hop_chuan_hop_quy`

Trường này lật mức giữa các phân loại (NC ở A/B → TH ở C/D). Nếu copy danh sách A sang C sẽ sai. Cần kiểm tra riêng khi seed dữ liệu.

### 5.3. Nhóm BB\* không nên đặt `reqd = 1` cứng

Ba trường `giay_uy_quyen_csh`, `giay_xac_nhan_bao_hanh`, `cfs_giay_luu_hanh` chỉ bắt buộc khi hàng nhập khẩu / Miyano không phải chủ sở hữu số lưu hành. Nếu bắt buộc cứng sẽ chặn nhầm hàng sản xuất trong nước.

→ Đề xuất dùng `depends_on` / `mandatory_depends_on`:

```python
mandatory_depends_on = "eval:doc.xuat_xu == 'Nhập khẩu'"
```

### 5.4. Phân biệt cấp lưu trữ: Item / Batch / Transaction

| Chứng từ | Cấp lưu đề xuất | Lý do |
|---|---|---|
| `cq_chung_nhan_chat_luong` | **Batch** | Bản chất là "CQ của **từng lô**" |
| `ho_so_phan_phoi` | **Transaction** | Gắn theo hợp đồng / hóa đơn / phiếu xuất |
| 14 trường còn lại | **Item** | Hồ sơ cấp mặt hàng, dùng chung mọi lô |

### 5.5. Cấu trúc DocType đề xuất (Frappe / ERPNext)

```
DocType: Medical Device Document Type          (master — 23 bản ghi)
  - field_name        Data, unique
  - doc_label         Data
  - attach_level      Select: Item / Batch / Transaction

DocType: Medical Device Doc Rule               (master — 92 bản ghi = 23 × 4)
  - document_type     Link → Medical Device Document Type
  - device_class      Select: A / B / C / D
  - level             Select: BB / BB* / NC / TH / KHONG_AP_DUNG
  - condition         Code (chỉ dùng cho BB* và TH)

DocType: Item Regulatory Document              (child table trên Item)
  - document_type     Link → Medical Device Document Type
  - file              Attach
  - so_hieu           Data
  - ngay_cap          Date
  - ngay_het_han      Date
  - status            Select: Còn hiệu lực / Sắp hết hạn / Hết hạn
```

### 5.6. Logic validate

Hook `validate` trên Item:

1. Đọc `phan_loai_tbyt` của Item (A / B / C / D)
2. Query bảng rule lấy danh sách chứng từ tương ứng
3. **BB** → thiếu thì `frappe.throw()` chặn lưu
4. **BB\*** → chỉ chặn khi thỏa `condition`
5. **NC** → thiếu thì `frappe.msgprint()` cảnh báo, vẫn cho lưu

Nên bổ sung scheduled job kiểm tra `ngay_het_han` để cảnh báo chứng từ sắp hết hiệu lực.

---

## 6. Điểm cần bạn xác nhận trước khi code

1. **Định nghĩa chính xác điều kiện của BB\***: chỉ phụ thuộc "hàng nhập khẩu" hay còn phụ thuộc "Miyano có phải chủ sở hữu số lưu hành không"? Hai điều kiện này khác nhau và ảnh hưởng tới `mandatory_depends_on`.
2. **Có tách `cq_chung_nhan_chat_luong` và `ho_so_phan_phoi` khỏi Item không?** Nếu giữ ở Item thì danh mục mỗi loại giảm còn 14–15 trường.
3. **Có cần lưu lịch sử phiên bản chứng từ không** (ví dụ giấy lưu hành gia hạn)? Nếu có, child table cần thêm cờ `is_active` thay vì ghi đè.
4. **Nguồn dữ liệu phân loại A/B/C/D** lấy từ trường nào trên Item hiện tại, hay cần tạo mới?

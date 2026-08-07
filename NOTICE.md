# NOTICE — Bản quyền & Nguồn gốc

## Tình trạng

**Miyano ERP** — hệ thống ERP nội bộ của Công ty TNHH Miyano Việt Nam, xây dựng trên một bản fork sâu của ERPNext.

**Chỉ dùng nội bộ, không phát hành công khai, không phân phối ra ngoài công ty.** Không áp dụng giấy phép công khai nào cho hệ thống này.

## Bản quyền

### Phần do Miyano tự phát triển

Bản quyền **Công ty TNHH Miyano Việt Nam**. 110 file, mang dòng `Copyright (c) 2026, Công ty TNHH Miyano Việt Nam`, không gắn giấy phép công khai. Xác định khách quan bằng git:

```bash
git log --diff-filter=A --author=hivx --format="" --name-only | sort -u
```

Gồm toàn bộ nghiệp vụ kế toán & tuân thủ Việt Nam:

- `erpnext/regional/vietnam/**`
- 15 báo cáo VN trong `erpnext/regional/report/`: `so_cai`, `so_nhat_ky_chung`, `so_chi_tiet_tai_khoan`, `so_chi_tiet_cong_no`, `so_chi_tiet_nguyen_te`, `so_quy_tien_mat`, `so_tien_gui_ngan_hang`, `bang_can_doi_so_phat_sinh`, `bao_cao_tinh_hinh_tai_chinh_b01`, `bao_cao_kqhdkd_b02`, `bao_cao_luu_chuyen_tien_te_b03`, `thuyet_minh_bctc_b09`, `to_khai_thue_gtgt_01`, `quyet_toan_tncn`, `quyet_toan_tndn`
- Các sửa đổi core do Miyano thực hiện

### Phần kế thừa từ ERPNext

Bản quyền **Frappe Technologies Pvt. Ltd. và các contributor** của dự án ERPNext, cấp cho Miyano theo **GNU General Public License v3** (toàn văn: <https://www.gnu.org/licenses/gpl-3.0.html>).

Theo quyết định của chủ sở hữu ngày 2026-07-31, dòng ghi bản quyền và dòng trỏ giấy phép đã được **gỡ khỏi 1591 file** kế thừa (5433 dòng, diff không thêm dòng nào). Header bị **xoá hẳn**, không thay bằng `© Miyano` — để nếu có kiểm toán thì đó là "không ghi gì", không phải "ghi sai".

**Điều này không làm thay đổi tình trạng pháp lý của phần mã kế thừa.** Giấy phép GPLv3 do các chủ sở hữu bản quyền cấp, không do sự hiện diện của dòng chữ trong file. Phần mã đó vẫn thuộc bản quyền Frappe Technologies và contributor, và vẫn ở GPLv3.

### Bên thứ ba — giữ nguyên ghi nhận

Sáu công ty **không phải Frappe** có đóng góp trong phần kế thừa. Dòng bản quyền của họ được **giữ nguyên có chủ đích**, vì mục tiêu của đợt bóc tách là gỡ thương hiệu ERPNext/Frappe, không phải gỡ ghi nhận của bên vô can:

| Công ty | Số file |
|---|---|
| Wahni Green Technologies Pvt. Ltd. | 7 |
| Epoch Consulting | 1 |
| Velometro Mobility Inc | 1 |
| newmatik.io / ESO Electronic Service Ottenbreit | 1 |
| Tristar Enterprises | 1 |

## Vì sao không có giấy phép công khai

GPLv3 chỉ phát sinh nghĩa vụ khi **phân phối** (convey). Hệ thống chỉ chạy nội bộ Miyano ⇒ **không có nghĩa vụ công bố mã nguồn**, tự do sửa core, giữ kín toàn bộ, không phải đóng góp ngược lên upstream.

**Ngưỡng cần lưu ý:** nếu hệ thống được giao cho công ty con, đối tác, hoặc triển khai/bán cho khách hàng bên ngoài, đó là hành vi phân phối và nghĩa vụ GPLv3 phát sinh — phải kèm mã nguồn và giữ giấy phép. Nếu Miyano cần quyền sở hữu độc quyền không ràng buộc GPL, cần thương lượng giấy phép thương mại với Frappe Technologies và tham vấn luật sư sở hữu trí tuệ.

## Ghi nhận bên thứ ba khác

Tài nguyên (icon, thư viện) được ghi nhận trong [attributions.md](attributions.md).

## Thương hiệu

"ERPNext" và logo ERPNext là nhãn hiệu của Frappe Technologies Pvt. Ltd. Hệ thống này mang thương hiệu **Miyano ERP**; không sử dụng nhãn hiệu ERPNext trong nhận diện sản phẩm.

Khoá cài đặt `app_name = "erpnext"` và đường dẫn package `erpnext/` được giữ nguyên vì là định danh cài đặt và cơ sở dữ liệu trên site `miyano`, không phải nhận diện thương hiệu.

# Lấy hàng theo phiếu giao — lô theo hạn dùng, chuyển đổi đơn vị, tem kiện — thiết kế

Ngày: 22/09/2026 · Module: Warehouse Operations · Nền: trang PDA `lay-hang-pda`, `vitri/lay_hang.py`, bảng `Location Allocation` (spec 2026-09-18-lay-hang-pda)

## 1. Yêu cầu (chủ đầu tư, 22/09/2026)

> "Trong phiếu delivery note chúng ta sẽ làm nút lấy hàng, khi lấy hàng sẽ gợi ý lô theo FEFO, có thể sửa được, lấy hàng yêu cầu lấy lô, lấy đúng vị trí, khi lấy hàng có cơ chế chuyển đổi linh hoạt — 1 thùng 2000 cái nhưng lấy 5 hộp mỗi hộp 100 cái — nút in tem để… dán tem cho từng mặt hàng ngoài đời thực. Lấy hàng theo vị trí (chọn chuyển đổi đơn vị, in tem) → submit."

## 2. Quyết định đã chốt

| Câu hỏi | Chốt |
|---|---|
| Màn hình | **Cả hai**: PDA (đi lấy ở kệ) và hộp thoại trên form phiếu giao (bàn đóng gói, súng quét USB). Một bộ hàm máy chủ chung |
| Đơn vị | **Linh hoạt theo quy đổi khai trên mặt hàng** (`Item.uoms`): lấy theo Cái, Hộp hay Thùng đều được |
| Tem | **Mỗi kiện một tem**, có số phiếu giao và tên khách |
| Lô FEFO | **Đổi `Stock Settings.pick_serial_and_batch_based_on` sang "Expiry" cho toàn hệ** |
| Duyệt khi thiếu tem | **Chặn** |
| Bắt buộc lấy hàng | **Có**: dòng hàng ở kho quản lý vị trí phải được lấy (quét) đủ hoặc chốt thiếu, và in đủ tem kiện, thì mới duyệt được |

## 3. Lô theo hạn dùng

- Patch đặt `Stock Settings.pick_serial_and_batch_based_on = "Expiry"`. ERPNext (`get_item_details.py`, `serial_and_batch_bundle.get_available_batches`) đã sắp theo `expiry_date` và bỏ lô hết hạn. Nhờ vậy phiếu giao tạo từ đơn bán **tự điền lô gần hết hạn nhất**; người dùng vẫn sửa được lô trên phiếu.
- Màn hình lấy hàng giữ gợi ý ô FEFO (`o_nen_lay`) và luật đổi lô / tách dòng / chặn lô hết hạn đã có. Thêm vào mỗi dòng **"Lô nên lấy"**: lô FEFO còn tồn trong kho quản lý vị trí. Nếu lô đang chốt trên dòng KHÁC lô FEFO thì hiện cảnh báo *"Lô trên phiếu hết hạn muộn hơn lô X"*.

## 4. Chuyển đổi đơn vị

**Hiện nay:** `_ly_do_khong_quet_dong` chặn dòng có `conversion_factor ∉ (0,1)` vì trang nói bằng đơn vị giao dịch còn bảng phân bổ đo bằng đơn vị tồn. **Bỏ chặn này.** Toàn bộ đường lấy hàng chuyển sang đo bằng **đơn vị tồn** (`stock_qty`), hiển thị kèm đơn vị của dòng.

**Bảng `Location Allocation` thêm trường:**

| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `don_vi_lay` | Link UOM | đơn vị thủ kho chọn khi lấy |
| `so_luong_lay` | Float | số lượng theo `don_vi_lay` |
| `he_so` | Float | hệ số `don_vi_lay` → đơn vị tồn (từ `Item.uoms`; đơn vị tồn = 1) |
| `so_kien` | Int | số kiện của lượt lấy |
| `so_kien_da_in` | Int, read_only | số kiện đã in tem |

`so_luong` (đơn vị tồn) vẫn là con số duy nhất mà sổ vị trí và hook đọc: `so_luong = so_luong_lay × he_so`.

**`ghi_da_lay`** nhận thêm `don_vi` (mặc định = đơn vị của dòng phiếu giao) và `so_kien`:
- `don_vi` phải nằm trong `Item.uoms` của mặt hàng; sai thì báo *"Mặt hàng X không khai đơn vị Y"*.
- Quy đổi: `so_luong = so_luong_lay × he_so`, rồi kiểm theo đơn vị tồn như hiện nay (tồn của ô, không vượt `stock_qty` còn thiếu của dòng).
- Mặc định `so_kien`: nếu `don_vi` ≠ đơn vị tồn thì `so_kien = so_luong_lay` (5 Hộp → 5 kiện); nếu bằng đơn vị tồn thì 1. Sửa được, ≥ 1.
- Cộng dồn một lượt vào dòng phân bổ cũ chỉ khi cùng ô, cùng lô, cùng `don_vi_lay` **và mỗi kiện chứa cùng số lượng** (`so_luong_lay / so_kien` bằng nhau); còn lại thì thêm dòng mới. *(Sửa khi chạy thật 22/09: 20 Cái + 80 Cái từng gộp thành hai tem "50 Cái".)*

**Tiến độ và hoàn tất** so theo đơn vị tồn: dòng đủ khi Σ`so_luong` = `stock_qty`.

**Chốt thiếu trên dòng bán theo đơn vị khác đơn vị tồn:** số thực lấy (đơn vị tồn) ÷ `conversion_factor` của dòng. Nếu đơn vị của dòng có `UOM.must_be_whole_number` mà kết quả không tròn thì **chặn**, kèm câu *"Dòng N bán theo Hộp: số lấy thực phải tròn Hộp (đang 3,5 Hộp). Lấy thêm hoặc bỏ bớt cho tròn."*

## 5. Kiện và tem kiện

- Mỗi dòng phân bổ có `so_kien`; mỗi kiện mang `so_luong / so_kien` (đơn vị tồn), hiển thị theo `don_vi_lay`: `so_luong_lay / so_kien`.
- `tem_kien.du_lieu_tem_kien(phieu, chi_chua_in=1)` (file riêng `vitri/tem_kien.py`) trả danh sách tem. Mỗi tem gồm:
  - tên hàng, mã hàng;
  - lô, HSD;
  - "100 Cái" (số lượng trong kiện kèm đơn vị);
  - số phiếu giao, tên khách;
  - "Kiện i/N" (đánh số trên TOÀN phiếu cho mỗi mặt hàng + lô);
  - mã vạch lô.
- `tem_kien.danh_dau_da_in(phieu, dong_phan_bo=None)` đặt `so_kien_da_in = so_kien`; gọi sau khi cửa sổ in đã mở.
- Tem 50×30 dùng **lại nguyên bố cục tem lô** (`tem_lo.in_xap`, ô F1…F11; F9 chữ to = "i/N") — không dựng bố cục thứ hai. `tem_kien.js` chỉ nối: đọc dữ liệu → mở cửa sổ in → đánh dấu đã in.
- Nút **"In tem kiện"** trên form phiếu giao và trong hộp thoại lấy hàng trên máy tính. PDA chỉ hiện trạng thái *"x/y kiện đã in tem"*, vì máy in tem nối với máy tính.

## 6. Bắt buộc lấy hàng và in tem trước khi duyệt

`Delivery Note.before_submit` (hook mới `lay_hang.chan_duyet_chua_lay`), bỏ qua phiếu trả hàng (`is_return`):
- Mọi dòng quét được (`_can_quet_dong`: kho quản lý vị trí, hàng tồn kho) phải **lấy đủ theo đơn vị tồn hoặc đã chốt thiếu**. Chưa lấy gì thì báo *"Dòng N (X) chưa lấy hàng — bấm Lấy hàng"*.
- Mọi dòng phân bổ phải có `so_kien_da_in = so_kien`. Chưa in đủ thì báo *"Còn N kiện chưa in tem — bấm In tem kiện"*.
- Đường FEFO tự trừ khi duyệt thẳng **không còn dùng được** cho dòng quản lý vị trí. Nó vẫn còn trong hook cho chứng từ khác (Stock Entry…) và cho dòng không quét được.
- Cờ trong tiến trình `frappe.flags.vi_tri_kho_bo_bat_buoc_lay_hang` chỉ dành cho bộ test dựng dữ liệu (như `CO_BO_KIEM_TEST` của luật ô trên tem); không đặt được qua HTTP.

## 7. Hộp thoại lấy hàng trên máy tính

- Nút **"Lấy hàng"** trên form phiếu giao nháp mở `frappe.ui.Dialog` lớn. Nút "Lấy hàng trên PDA" giữ nguyên.
- Trong hộp thoại:
  - bảng các dòng: cần / đã lấy (theo đơn vị của dòng và đơn vị tồn), lô nên lấy, ô nên lấy;
  - ô quét dùng `OQuet`, giống PDA;
  - các bước: quét lô → quét ô → chọn đơn vị + số lượng + số kiện → **Ghi**;
  - danh sách lượt đã lấy có nút bỏ;
  - nút **In tem kiện** và **Hoàn tất (duyệt)**.
- Gọi chung các hàm máy chủ của trang PDA (`quet_de_lay`, `ghi_da_lay`, `bo_dong_da_lay`, `doi_lo`, `tach_dong_theo_lo`, `chot_thieu`, `hoan_tat`). Không thêm luật nào ở phía màn hình.
- Không dùng `frappe.confirm`, vì súng quét gửi phím Enter.

## 8. PDA

- Sau khi quét lô: thêm chọn **đơn vị** (các nút theo `Item.uoms`, mặc định đơn vị của dòng) và **số kiện** (nút −/+).
- Mỗi dòng hiển thị "cần / đã lấy" theo đơn vị của dòng, kèm đơn vị tồn.
- Hiện "Lô nên lấy" và trạng thái *"x/y kiện đã in tem"*.

## 9. Ngoài phạm vi

- Không đổi luật xếp đúng ô trên tem, không đổi sổ vị trí.
- Không thêm doctype "phiếu lấy hàng" riêng (đã chốt 19/09: lấy hàng nằm trên phiếu giao).
- Không đổi mẫu in 02-VT.
- Không làm hàng Product Bundle.

## 10. Kiểm thử

- **Máy chủ**
  - Quy đổi: 5 Hộp (hệ số 100) trừ 500 ở ô; vượt tồn ô thì chặn; đơn vị không khai thì chặn.
  - Cộng dồn chỉ khi cùng đơn vị.
  - Dòng bán theo Hộp lấy đủ bằng Cái.
  - Chốt thiếu tròn / không tròn đơn vị.
  - Mặc định số kiện.
  - `du_lieu_tem_kien`: đúng số tờ, đúng "Kiện i/N", đúng số lượng mỗi kiện.
  - `danh_dau_da_in_tem_kien`.
  - Chặn duyệt khi chưa lấy / chưa in tem; phiếu trả hàng không bị chặn; dòng dịch vụ không bị chặn.
  - Patch Expiry: phiếu giao mới tự điền lô gần hết hạn.
- **Sửa test cũ:** mọi bài duyệt thẳng phiếu giao ở kho quản lý vị trí bật cờ bỏ bắt buộc, hoặc đi qua lấy hàng.
- Chạy cả bộ `erpnext.warehouse_operations.tests`.
- **Chạy thật trên erptest** với một mặt hàng khai 1 Thùng = 2000 Cái, 1 Hộp = 100 Cái:
  - tạo phiếu giao từ đơn bán: lô tự điền theo HSD;
  - lấy 5 Hộp trên PDA, lấy thêm Cái trên máy tính;
  - in tem kiện;
  - duyệt: bị chặn khi thiếu tem, qua khi đủ.

## 11. Thứ tự thi công

1. Lô theo FEFO (patch cài đặt, "Lô nên lấy").
2. Chuyển đổi đơn vị (trường mới, `ghi_da_lay`, tiến độ, chốt thiếu, bỏ chặn).
3. Kiện và tem kiện (dữ liệu tem, đánh dấu đã in, `tem_kien.js`, nút In tem kiện).
4. Chặn duyệt (bắt buộc lấy hàng + in tem).
5. Hộp thoại lấy hàng trên máy tính; bổ sung PDA.

Mỗi phần chạy đủ test module trước khi sang phần sau.

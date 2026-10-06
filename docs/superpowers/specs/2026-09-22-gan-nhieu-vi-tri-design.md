# Gán nhiều vị trí cố định cho một mặt hàng — thiết kế

Ngày: 22/09/2026 · Module: Warehouse Operations (`erpnext/warehouse_operations/`) · Nhánh: `feat/gan-nhieu-vi-tri`

## 1. Vấn đề

Hiện nay mỗi mặt hàng có **đúng một** bản gán `Item Location Preference`. Tên bản ghi là mã mặt hàng (`autoname: field:vat_tu`), và bản ghi trỏ vào **một** nút cây (`vi_tri`) cùng một kho (`kho`). Chủ đầu tư, ngày 22/09/2026: *"1 item có thể gán nhiều vị trí khác nhau… ví dụ item này có thể ở ô này và ở tầng bên kia nữa"*.

## 2. Quyết định đã chốt với chủ đầu tư

| Câu hỏi | Chốt |
|---|---|
| Mô hình | Một mặt hàng có một bản gán, bản gán có **nhiều dòng vị trí** (bảng con) |
| Thứ tự gợi ý ô | **Ô trống trước, bất kể thuộc vị trí nào**; hết ô trống mới dồn vào ô đang chứa cùng mặt hàng |
| Nhiều kho | **Có** — mỗi dòng mang kho của nút được chọn |

## 3. Dữ liệu

**`Item Location Preference`** (giữ tên doctype, giữ `autoname: field:vat_tu`, tức vẫn một bản ghi cho mỗi mặt hàng):
- Giữ: `vat_tu`, `ghi_chu`.
- **Bỏ:** `kho`, `vi_tri`, `cap_do`. Patch §8 xoá cột sau khi đã chuyển dữ liệu.
- **Thêm:** `vi_tri_gan` (Table → `Item Location Preference Row`, bắt buộc ít nhất 1 dòng).

**`Item Location Preference Row`** (bảng con mới, `istable`):

| Trường | Kiểu | Ghi chú |
|---|---|---|
| `vi_tri` | Link → Storage Location, bắt buộc, in_list_view | nút bất kỳ trong cây: ô, tầng, khoang, dãy… |
| `kho` | Link → Warehouse, read_only, in_list_view | tự điền từ `Storage Location.kho` trong `validate` |
| `cap_do` | Data, read_only, in_list_view | tự tính (`TEN_CAP[cap_do(vi_tri) - 1]`) |
| `ghi_chu` | Data | |

Thứ tự dòng (`idx`) chỉ là **tiêu chí phân định** khi có nhiều ô trống ở nhiều vị trí; không phải "vị trí chính / phụ".

## 4. Luật kiểm (`ItemLocationPreference.validate`)

Chạy cho **từng dòng**, giữ nguyên thứ tự và lý lẽ của các phép kiểm hiện có. Câu báo mở đầu bằng *"Dòng {idx}: …"*.

1. Nút tồn tại và có toạ độ trong cây (`lft`/`rgt` khác 0). Luật `kiem_tra_trong_cay` giữ nguyên, chạy trước mọi thứ đọc `lft`/`rgt`.
2. Nút hợp lệ:
   - kho của nút đã bật quản lý vị trí;
   - không phải ô "Chưa xếp";
   - không nằm dưới một nhánh đang ngừng dùng.

   Không còn kiểm "cùng kho với bản gán", vì `kho` của dòng tự điền theo nút.
3. **Không chồng lên mặt hàng khác:** nhánh của dòng không được giao với nhánh của bất kỳ dòng nào thuộc bản gán **khác**. Dùng `gan.chu_cua_nhanh(lft, rgt, tru_ten=self.name)`, viết lại để đọc bảng con.
4. **Không chồng chính mình (mới):** hai dòng của cùng bản gán không được giao nhau (trùng nút, hoặc lồng nhau). Câu báo nêu rõ cặp dòng.
5. Không gán vào nhánh đang chứa tồn của mặt hàng khác. `kiem_tra_ton_mat_hang_khac` giữ nguyên câu báo và cách đếm N, áp cho từng dòng.
6. Điền `kho` và `cap_do` cho dòng.

Bất biến trung tâm giữ nguyên: **một ô chỉ thuộc về một mặt hàng**.

## 5. Gợi ý ô (`goi_y.goi_y_o(vat_tu, kho, so_lo=None)`)

Chữ ký và kết quả trả về (bộ ba `(ô, lý do, tem_hong)`) **không đổi**. Chỉ xét các dòng có `kho` bằng kho đang làm. Mặt hàng không có dòng nào ở kho này thì trả `(None, "mặt hàng chưa gán vị trí cố định ở kho {kho}", False)`.

Thứ tự:
1. **Ô đã in trên tem lô**, nếu có `so_lo` và lô có `custom_o_in_tem`, với ô đó thoả cả bốn điều kiện:
   - nằm trong **bất kỳ** nhánh nào đã gán ở kho này;
   - là ô lá;
   - không bị ngừng dùng;
   - không bị mặt hàng khác chiếm.

   Tem hỏng thì vẫn đặt `tem_hong = True` và rơi xuống bước 2, như hiện nay.
2. **Ô trống đầu tiên**, xét **mọi dòng**, sắp theo `idx` của dòng rồi `lft` của ô. Lý do: *"ô trống đầu tiên trong {vi_tri của dòng}"*.
3. **Dồn vào ô đang chứa chính mặt hàng này**, xét mọi dòng, cùng thứ tự.
4. Không còn chỗ thì `(None, "các vị trí đã gán ({danh sách}) đã đầy", tem_hong)`.

Cách làm: một truy vấn duy nhất cho mỗi bước, gom các nhánh bằng `or` các khoảng `lft`/`rgt`, kèm `field(...)`/`case` theo `idx` để sắp thứ tự. Không lặp truy vấn theo từng dòng.

## 6. Nơi dùng khác

| Nơi | Đổi |
|---|---|
| `gan.chu_cua_nhanh` | đọc `tabItem Location Preference Row` join `Storage Location`; trả `vat_tu`, `vi_tri`, `lft`, `rgt` |
| `gan.cay_chon_vi_tri` | hai subquery `da_gan_cho` / `co_gan_ben_trong` đọc bảng con; `tru_ten` loại **toàn bộ** các dòng đã lưu của bản gán đang sửa. Tham số mới `dang_co` (JSON, danh sách nút đang nằm trong hộp thoại — kể cả dòng vừa thêm/bỏ chưa lưu) → cột `cua_chinh_minh` = nút GIAO với một nút trong `dang_co` (trùng, tổ tiên hoặc con cháu); cây hiện "đã có trong danh sách" và không cho chọn. Nguồn sự thật của "chính mình" là hộp thoại, không phải CSDL |
| `gan.vi_tri_cua_mat_hang` | trả `{"name", "dong": [{vi_tri, kho, cap_do, ma_in_nhan}]}` hoặc `None` |
| `gan.gan_vi_tri_cho_mat_hang` | nhận `vi_tri` là **danh sách** tên nút (JSON); ghi đè toàn bộ bảng con theo đúng thứ tự; đi qua `save()`/`insert()`, không `ignore_permissions` |
| `quet.py` | hiện danh sách vị trí đã gán (các `vi_tri` nối bằng "; ") thay vì một nút |
| Báo cáo `hang_nam_sai_vi_tri` | giữ định nghĩa cũ "ô chứa hàng KHÁC chủ nhánh", chỉ đổi join sang bảng con. Hàng của A nằm ở nhánh thứ hai của chính A không bị báo (chủ nhánh cũng là A) |
| `gan.doi_ten_theo_mat_hang` | không đổi (tên bản gán vẫn là mã mặt hàng) |
| `nhap_lo.dat_o_in_tem`, `xep.hang_chua_xep`, `o_tem.*` | không đổi — đi qua `goi_y_o` |

## 7. Giao diện

**Form Mặt hàng** (`public/js/warehouse_operations/item.js`): khu "Vị trí kho" liệt kê các vị trí đang gán (mã ô, cấp, kho). Nút **"Gán vị trí"** mở một hộp thoại (`frappe.ui.Dialog`) gồm:
- bảng các dòng hiện có, mỗi dòng có nút bỏ và nút lên/xuống để đổi thứ tự;
- nút **"Thêm vị trí"**, mở cây chọn hiện có (`cay_chon_vi_tri.js`); chọn xong thêm một dòng;
- nút chính **"Lưu"**, gọi `gan_vi_tri_cho_mat_hang` với danh sách. Lỗi của máy chủ (mở đầu bằng "Dòng N:") hiện nguyên văn.

**Cây chọn vị trí:** nút của mặt hàng khác vẫn mờ và không chọn được. Nút đã thuộc chính mặt hàng này hiện nhãn "đã gán" và cũng không chọn lại được.

**Form `Item Location Preference`:** bảng con hiện dạng lưới chuẩn. Nút "Chọn trên cây vị trí" sẵn có đổi thành thêm một dòng.

## 8. Chuyển dữ liệu

Patch `warehouse_operations.patches.v1_0.gan_nhieu_vi_tri` đặt ở `[post_model_sync]`, chạy sau khi bảng con đã được tạo:
- Với mỗi bản gán còn cột `vi_tri` khác rỗng: thêm một dòng bảng con (`vi_tri`, `kho`, `cap_do`, `idx = 1`) bằng SQL.
- Xong thì xoá các cột `vi_tri`, `kho`, `cap_do` của bảng cha (`frappe.db.sql_ddl` … `drop column`, có kiểm `has_column`).
- Chạy lại nhiều lần vẫn an toàn: bản gán nào đã có dòng thì bỏ qua.

Trên erptest có 8 bản gán; sau patch sẽ thành 8 bản gán, mỗi bản 1 dòng.

## 9. Kiểm thử

- Sửa `test_gan_vi_tri.py` (37 bài) và `test_goi_y_o.py` (18 bài) theo cấu trúc mới; hành vi một dòng phải y như cũ.
- Bài mới:
  - gán 2 vị trí khác nhánh cho một mặt hàng;
  - chặn chồng mặt hàng khác ở dòng thứ 2;
  - chặn hai dòng tự lồng nhau;
  - hai dòng ở hai kho, gợi ý chỉ xét kho đang làm;
  - ô trống ở dòng 2 được gợi ý khi dòng 1 hết ô trống (dòng 1 còn ô "dồn" được) — khoá đúng luật "ô trống trước, bất kể vị trí";
  - tem lô ở ô thuộc dòng 2 vẫn được ưu tiên;
  - báo cáo sai vị trí không báo hàng nằm ở dòng 2;
  - cây: `da_gan_cho` / `co_gan_ben_trong` / `cua_chinh_minh`;
  - `gan_vi_tri_cho_mat_hang` ghi đè đúng thứ tự;
  - patch chuyển dữ liệu (một bản gán kiểu cũ thành 1 dòng; chạy lại không nhân đôi).
- Chạy cả bộ `erpnext.warehouse_operations.tests` (37 file).
- Chạy thật trên erptest: gán 2 vị trí cho một mặt hàng trên form Mặt hàng, in tem một lô mới (ô trên tem rơi vào ô trống), xếp hàng qua PDA, xem báo cáo sai vị trí.

## 10. Ngoài phạm vi

- Không đổi luật xếp đúng ô trên tem, không đổi FEFO khi lấy hàng.
- Không thêm sức chứa theo ô.
- Không đồng bộ cách đếm mã vạch (ghi chú ở PR #19).

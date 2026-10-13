# Kế hoạch build: Sinh mã vật tư tự động trên ERPNext

> Trạng thái: **đã code xong Giai đoạn 1, 2, 3 và phần patch của Giai đoạn 5** (12/10/2026). Đã bật trên site dev `miyano` kèm dữ liệu thử; chưa bật trên production. Chi tiết ở mục 14.
> Phạm vi: sửa trực tiếp core trong fork `mvl26/erpnext`
> **Điều chỉnh lần sáu 13/10/2026 (mục 5.4, 14.11):** mã vật tư **không còn bất biến**. Đổi nhóm hàng, thương hiệu, NCC mặc định hay mã hàng NCC thì vật tư **đổi mã theo**; đổi mã nhóm, mã thương hiệu ở danh mục thì **mọi vật tư mang mã cũ đổi theo**. Thay cho nguyên tắc "mã chốt một lần" ở các bản trước.
> **Điều chỉnh lần năm 13/10/2026 (mục 14.10):** mã nhóm, mã thương hiệu **luôn bắt buộc** (không chỉ lúc tạo) và **đã lưu thì khóa**, kể cả khi chưa vật tư nào dùng.
> **Điều chỉnh lần bốn 13/10/2026 (mục 14.9):** Brand và Item Group **giữ ID là tên**; mã dùng để sinh mã vật tư là **trường riêng** (`brand_code`, `item_group_code`), và **bắt buộc khi tạo** Brand, Item Group. Thay cho phần "ID của Brand là mã" ở 14.7.
> **Điều chỉnh lần ba 12/10/2026 (mục 2.4, 14.8):** giới hạn độ dài **3-6-11** cho mã nhóm, mã thương hiệu, mã hàng NCC; nhập dài hơn thì hệ thống **tự cắt, lấy các ký tự đầu**.
> **Điều chỉnh lần hai 12/10/2026 (mục 14.7):** mã thương hiệu là **chính ID của Brand** (bỏ trường `brand_code`); **khóa** mã nhóm, thương hiệu và nhóm hàng khi đã có vật tư mang mã đó.
> **Điều chỉnh sau review 12/10/2026 (mục 14.6):** bỏ màn hình tra cứu trước khi tạo; trùng mã hàng NCC khác thương hiệu chỉ cảnh báo; gọi "hãng" là **Thương hiệu (Brand)**.
> Đã đối chiếu với code của fork (nhánh `feat/vn-tbyt-ho-so-phap-ly`) và site dev `miyano`, kết quả ở mục 13. **Chưa có số liệu production**, đây là phần còn lại của Giai đoạn 0.

## Thay đổi so với bản trước

| Mục | Thay đổi | Lý do |
|---|---|---|
| 1.2 | Thêm: tài liệu này là tài liệu chính, ưu tiên hơn FRD-MAP-01 ở quy tắc mã | Hai tài liệu đang trái nhau ở cấu trúc mã |
| 2.2 | Thêm quy ước hoa/thường: mã **giữ nguyên hoa/thường** như đã khai | Quyết định mới |
| 3.1 | Thêm D9: NCC không có mã hàng thì phần thứ ba lấy gì | Bản trước bắt buộc mã NCC nhưng không có lối ra |
| 3.2 | D4 đổi tiêu chí phạm vi; thêm D10 (trường khóa so khớp) | `is_purchase_item` mặc định bật cho mọi Item |
| 5.1 | Chốt ký tự được giữ trong mã; tách "phần ghép mã" và "khóa so khớp" | Bản trước ghi "thay hoặc bỏ", chưa chốt |
| 5.2 | Tách kiểm tra lúc tạo và lúc sửa | Tránh khóa Item cũ (D6) |
| 5.3, 5.4 | Cách bật quy tắc qua Stock Settings; chặn đổi tên và gộp mã | Sửa JSON không đủ, Item đang cho rename |
| 5.5 | Không xóa `default_supplier` khi Item không có dòng NCC | Item cũ |
| 6.1 | Cảnh báo lớp 2 khi không có giao diện thì thành chặn (đã thay ở 14.6: lớp 2 chỉ cảnh báo) | Data Import, API không có chỗ xác nhận |
| 10 | Sửa ca 9, 13, 15; thêm ca 20–27 | Theo các thay đổi trên |
| 13 | Thêm kết quả khảo sát fork | Đầu ra Giai đoạn 0 |

---

## 1. Mục tiêu

1. Item Code được hệ thống **tự sinh** theo cấu trúc `[Mã nhóm]-[Mã hãng/Model]-[Mã hàng NCC]`, ví dụ `HCH-VinaH-N12345`.
2. **Mã duy nhất** trên toàn hệ thống.
3. **Không tạo trùng vật tư**: khi có báo giá mới, biết được vật tư đã có trong hệ thống hay chưa trước khi tạo Item.
4. Người dùng không nhập tay Item Code.

### 1.1 Hai loại "trùng" cần phân biệt

| Loại | Ý nghĩa | Ai chặn |
|---|---|---|
| Trùng mã | Hai Item cùng Item Code | ERPNext đã chặn sẵn bằng khóa chính, và khóa chính vốn không phân biệt hoa/thường (xem 2.2). Không phải viết thêm |
| Trùng vật tư | Một vật tư thật nhưng có hai mã | **Phải tự xây**: khớp Brand + mã NCC chuẩn hóa, gợi ý theo tên |

### 1.2 Quan hệ với FRD-MAP-01

Tài liệu này là **tài liệu chính** cho quy tắc mã vật tư. Chỗ nào FRD-MAP-01 (Chuẩn hóa mã vật tư và đối soát hóa đơn NCC) viết khác thì theo tài liệu này:

| FRD-MAP-01 | Tài liệu này |
|---|---|
| FR-01: mã `[Mã NCC]-[Số HĐK]-[Nhóm hàng]-[STT]`, cho sửa tay trước khi lưu | Mã `[Mã nhóm]-[Mã hãng/Model]-[Mã hàng NCC]`, không nhập tay |
| FR-04: gia hạn hợp đồng khung thì sinh mã mới | Một mã cho một vật tư, không đổi theo hợp đồng. Mã chỉ đổi khi nhóm hàng, thương hiệu hoặc mã hàng NCC của vật tư đổi (5.4) |
| Mục tiêu 1: từ mã truy ngược về NCC và hợp đồng khung | Mã không mang thông tin hợp đồng. Liên kết vật tư với hợp đồng khung nằm ngoài phạm vi tài liệu này |

Các phần còn lại của FRD (đối soát hóa đơn, Bảng ánh xạ tên, ràng buộc Yêu cầu vật tư và PO) không thuộc tài liệu này.

---

## 2. Quy tắc mã hàng (phiên bản đề xuất sửa so với văn bản gốc)

### 2.1 Cấu trúc

```
{item_group_code}-{brand_code}-{supplier_part_no đã chuẩn hóa}
```

| Thành phần | Nguồn | Tối đa | Ví dụ |
|---|---|---|---|
| Mã nhóm | `Item Group.item_group_code` (trường mới) | 3 ký tự | `HCH` |
| Mã hãng/Model | `Brand.brand_code` (trường mới) | 6 ký tự | `VinaH`, `SYSMEX` |
| Mã hàng NCC | `Item Supplier.supplier_part_no` của **dòng được đánh dấu mặc định** | 11 ký tự | `N12345` |

Mỗi thành phần chỉ gồm chữ không dấu và số (xem 5.1). Dấu `-` chỉ dùng làm dấu phân cách, nên một mã luôn tách lại được thành đúng ba phần.

**Mã hệ thống và mã sinh Item Code là hai thứ tách nhau.** ID của Item Group và Brand vẫn là tên ("Vật tư y tế tiêu hao", "Vinahankook"), dùng để liên kết chứng từ và hiện trên báo cáo. `item_group_code` và `brand_code` chỉ dùng để ghép mã vật tư. Đổi tên danh mục không động tới mã, và ngược lại.

Mã vật tư dài nhất là 3 + 1 + 6 + 1 + 11 = **22 ký tự**.

### 2.2 Hoa/thường

- Mã **giữ nguyên hoa/thường** đúng như đã khai: `item_group_code` và `brand_code` theo danh mục, mã hàng NCC theo cách NCC viết. Hệ thống không tự đổi sang chữ hoa hay chữ thường. Brand khai mã `VinaH` thì mã ra `HCH-VinaH-N12345`.
- **Giới hạn kỹ thuật:** cơ sở dữ liệu so sánh không phân biệt hoa/thường (collation `utf8mb4_unicode_ci` trên cột `name` của Item và trên mọi cột liên kết tới Item). Vì vậy **không thể tồn tại hai mã chỉ khác nhau ở hoa/thường**: `HCH-VinaH-N12345` và `HCH-VINAH-N12345` là một mã. Tìm kiếm, quét mã và liên kết chứng từ cũng không phân biệt. Đổi collation sẽ động tới mọi bảng có liên kết tới Item nên không làm.
- Hệ quả: cách viết hoa/thường được chốt một lần, ở danh mục mã nhóm và mã hãng (nghiệp vụ duyệt ở Giai đoạn 1) và ở lần nhập mã NCC đầu tiên. Phát hiện trùng (mục 6) không phân biệt hoa/thường.

### 2.3 Điểm khác văn bản gốc (cần team đồng ý)

| Văn bản gốc | Đề xuất sửa | Lý do |
|---|---|---|
| "Ưu tiên NCC số 1 hoặc NCC mặc định (Default Supplier trong Tab Accounting)" | "NCC được **đánh dấu mặc định trong Supplier Items**" | `default_supplier` (Item Defaults) là liên kết độc lập với `supplier_items`, có thể chọn NCC không có trong `supplier_items`, và phụ thuộc Company. "Số 1" và "mặc định" có thể cho hai kết quả khác nhau |
| Mã đọc NCC mỗi khi thay đổi (ngầm hiểu) | Mã **chạy theo** nhóm hàng, thương hiệu, mã hàng NCC (5.4, từ 13/10/2026; trước đó là "chốt một lần lúc tạo") | Mã vật tư và danh mục luôn khớp nhau. Cái giá: đổi mã là rename Item, kéo theo toàn bộ chứng từ (xem 5.4 và mục 11) |
| Không nói gì về trường thiếu | Vật tư trong phạm vi (D4) **bắt buộc** đủ nhóm, hãng, NCC cấp mã | `brand`, `supplier_items`, `default_supplier` đều không bắt buộc trong ERPNext |
| Không nói gì khi NCC không có mã hàng | Cần quy định phần thứ ba lấy gì (D9) | Nhiều NCC vật tư tiêu hao không đặt mã hàng |

### 2.4 Giới hạn độ dài 3-6-11

Nhập dài hơn giới hạn thì hệ thống **tự cắt, lấy các ký tự đầu**, không báo lỗi. Người nhập được báo là mã đã bị cắt.

| Thành phần | Tối đa | Cắt ở đâu | Ví dụ |
|---|---|---|---|
| Mã nhóm | 3 | Khi lưu Item Group: giá trị lưu trong `item_group_code` là bản đã cắt | `VTTH` → `VTT` |
| Mã thương hiệu | 6 | Khi lưu Brand: giá trị lưu trong `brand_code` là bản đã cắt. Tên Brand không bị cắt | `SYSMEX1000` → `SYSMEX` |
| Mã hàng NCC | 11 | Lúc ghép mã vật tư, **sau khi** bỏ dấu và ký tự phân cách. `supplier_part_no` vẫn lưu nguyên văn | `CELLPACK-DCL-300A/20L` → `CELLPACKDCL` |

Quy ước đi kèm:

- **Kiểm tra ký tự trước, cắt sau.** Mã nhóm, mã thương hiệu có dấu, khoảng trắng hoặc ký tự đặc biệt vẫn bị từ chối chứ không bị cắt cho vừa.
- **Mã hàng NCC nguyên văn không bị cắt.** Bản đầy đủ cần cho việc đối chiếu hóa đơn NCC (FRD-MAP-01), nên chỉ phần ghép vào mã vật tư mới bị cắt.
- **So trùng dùng mã đầy đủ, không dùng bản đã cắt** (mục 6). Hai mã hàng NCC dài chỉ giống nhau ở 11 ký tự đầu là hai mặt hàng khác nhau, không phải "trùng vật tư".
- **Cắt xong mà đụng mã đã có thì chặn, không tự đổi sang mã khác:**
  - Mã nhóm, mã thương hiệu: báo trùng, người dùng nhập mã khác.
  - Mã vật tư (hai mã hàng NCC dài, cùng nhóm, cùng thương hiệu, giống nhau ở 11 ký tự đầu): chặn và chỉ ra vật tư đang giữ mã. Người quản trị danh mục xử lý tay. Form báo trước tình huống này ở dải "Mã vật tư dự kiến".
- **Số thứ tự D9** (`X0001`) dài 5 ký tự, nằm trong giới hạn 11.
- Mã nhóm dài hơn 3 hoặc mã thương hiệu dài hơn 6 có từ trước khi đặt giới hạn thì không dùng để sinh mã được: bị chặn lúc tạo Item, báo rõ cần sửa mã nào.

---

## 3. Các quyết định

### 3.1 Cần chốt trước khi code (chặn tiến độ)

| # | Câu hỏi | Đề xuất | Người chốt |
|---|---|---|---|
| D1 | Nguồn chuẩn giữa **Item Group** và **"Nhóm vật tư"** (đang trùng thông tin) | Dùng Item Group làm nguồn sinh mã; ẩn hoặc đồng bộ trường còn lại | Trao đổi với anh Việt |
| D2 | Phần thứ ba của mã là **mã NCC** hay **mã hãng sản xuất** | Giữ mã NCC theo văn bản gốc; mã hãng sản xuất nhập vào Item Manufacturer có sẵn (không thêm trường) để đối chiếu và chống trùng | Team |
| D9 | NCC **không có mã hàng** thì phần thứ ba lấy gì | Hệ thống cấp số thứ tự 4 chữ số theo từng cặp nhóm–hãng, có tiền tố `X` để không lẫn với mã NCC thật, ví dụ `HCH-VinaH-X0001` | Team |

> Lưu ý D1: trong fork và site dev, Item **không có** trường "Nhóm vật tư"; chỉ có Item Group, `la_thiet_bi_y_te` và `phan_loai_tbyt`. Cần xác định trường này đang nằm ở production hay ở file Excel.
>
> Lưu ý D2: mã NCC gắn mã vật tư với NCC. Nếu đổi/thêm NCC cho cùng một hàng thì mã cũ vẫn giữ nhưng không còn khớp mã NCC hiện hành. Chấp nhận được nếu mã chỉ dùng để nhận diện và tra cứu. Item Manufacturer là doctype riêng, chỉ tạo được **sau khi** Item đã có, nên mã hãng sản xuất không dùng được làm thành phần mã lúc tạo.
>
> Lưu ý D9: Item mang số thứ tự không có mã hàng NCC để so, nên không được lớp 1 và lớp 2 ở mục 6 bảo vệ.

### 3.2 Có thể chốt trong lúc làm

| # | Câu hỏi | Đề xuất |
|---|---|---|
| D3 | Hãng và model (Vinahancook vs Sysmex 1000) | Tạo **Brand riêng cho từng cặp hãng–model** (ví dụ Brand "Sysmex XN-1000", mã `SYSXN1`), không thêm trường Model. Lưu ý: 6 ký tự khó chứa cả hãng lẫn model, nghiệp vụ cần bảng mã viết tắt riêng (xem mục 11). Brand không thay Manufacturer: hãng theo hồ sơ pháp lý vẫn nằm ở Manufacturer, đang được số lưu hành TBYT dùng (`chu_so_huu`) |
| D4 | Phạm vi áp dụng | Item **có quản lý tồn kho** (`is_stock_item`), không phải tài sản cố định, không phải mẫu/biến thể. Dịch vụ và tài sản vẫn nhập mã tay. Không dùng `is_purchase_item` làm tiêu chí vì trường này mặc định bật cho mọi Item |
| D5 | Hàng không thuộc hãng nào | Brand mặc định "KHAC", mã `OTH` |
| D6 | Item hiện có | **Không đổi mã** các Item có mã đặt tay (có từ trước quy tắc). Chỉ mã do quy tắc sinh mới chạy theo thông tin (5.4) |
| D7 | Item mẫu có biến thể (template/variant) | Loại khỏi phạm vi, xử lý riêng nếu cần |
| D8 | Quy cách đóng gói khác nhau cùng mã (hộp 50 / hộp 100) | Dùng UOM quy đổi của cùng Item, hoặc tách Item nếu là sản phẩm khác; cần team quy định |
| D10 | Có lưu khóa so khớp của mã NCC không | Thêm một trường kỹ thuật ẩn, có index, trên Item Supplier (xem mục 4). Nếu không lưu thì mỗi lần tìm trùng phải đọc và chuẩn hóa lại toàn bộ Item Supplier |

---

## 4. Thiết kế dữ liệu

| Doctype | Trường | Loại | Ghi chú |
|---|---|---|---|
| Item Group | `item_group_code` | Data, unique | **Bắt buộc** ở chế độ quy tắc và **khóa sau khi lưu** (xem dưới). Tối đa 3 ký tự |
| Brand | `brand_code` | Data, unique | **Bắt buộc** ở chế độ quy tắc và **khóa sau khi lưu** (xem dưới). Tối đa 6 ký tự. ID của Brand vẫn là tên thương hiệu |
| Item Supplier | `is_default` | Check | "NCC mặc định / NCC cấp mã". Tự tick nếu là dòng duy nhất |
| Item Supplier | `supplier_part_no_key` | Data, ẩn, chỉ đọc, có index | Khóa so khớp của mã NCC (5.1), hệ thống tự điền khi lưu. Chỉ thêm nếu chốt D10 |
| Item | `item_code_by_rule` | Check, ẩn, chỉ đọc, không sao chép | Dấu "mã do quy tắc sinh". Chỉ Item mang dấu mới đổi mã theo thông tin (5.4). Hệ thống tự đặt; người dùng không bật, tắt được |
| Stock Settings | `item_naming_by` | Thêm lựa chọn thứ ba "Quy tắc mã vật tư" | Công tắc bật quy tắc (5.3). Không phải trường mới |
| Stock Settings | `item_rename_role` | Link Role | "Vai trò được chỉ định" ở 5.4. Để trống thì chỉ System Manager đổi tên, gộp mã vật tư và đổi các thành phần đã khóa được. Thêm lúc triển khai |

Ba trường nghiệp vụ mới là `item_group_code`, `brand_code`, `is_default`. Nhãn trên màn hình: **Mã nhóm (Item Group Code)**, **Mã thương hiệu (Brand Code)**, **NCC mặc định (Default Supplier)**.

Chữ "hãng" trong tài liệu này và "Thương hiệu (Brand)" trên màn hình là một. Chỉ mục `unique` đã không phân biệt hoa/thường nên không cần viết kiểm tra riêng. Mã NCC nguyên bản vẫn nằm trong `supplier_part_no`. Truy vết thay đổi dùng `track_changes` của Item, đang bật sẵn.

**Mã nhóm, mã thương hiệu luôn bắt buộc.** Ở chế độ "Quy tắc mã vật tư", lưu Item Group hoặc Brand mà không có mã thì bị chặn — lúc tạo lẫn lúc sửa, ở mọi đường (form, Quick Entry, cây nhóm hàng, Data Import, API). Cách làm và giới hạn:

- Không đặt `reqd` ở mức trường. Trình cài đặt, dữ liệu mẫu và bộ test core tạo Item Group, Brand không có mã; đặt `reqd` thì gãy cả ba. Thay vào đó: kiểm tra trên server mỗi lần lưu, và `mandatory_depends_on` để form hiện dấu bắt buộc.
- Item Group, Brand có từ trước mà chưa có mã: lần sửa tới phải nhập mã mới lưu được. Chưa ai sửa thì bản ghi vẫn nằm đó, và bị chặn lúc tạo Item (5.2).
- Áp dụng cho mọi nhóm, kể cả nhóm dịch vụ và nhóm cha. Nhóm không dùng để sinh mã vật tư vẫn phải có một mã 3 ký tự.
- Ngoại lệ: code tự tạo cây nhóm khung (`erpnext/regional/vietnam/master_data.py`) được tạo nhóm chưa có mã, bằng cờ `ignore_mandatory`. Nghiệp vụ điền mã sau.
- Ở chế độ "Item Code" hai mã này không bắt buộc.

**Mã đã lưu thì khóa.** Sau lần lưu đầu tiên có mã, ô mã chuyển sang chỉ đọc và server từ chối mọi thay đổi, **kể cả khi chưa vật tư nào mang mã đó**. Người có vai trò được đổi mã vật tư (và System Manager) thấy nút "Đổi mã nhóm" / "Đổi mã thương hiệu" trên form để mở khóa; họ sửa mã thì mọi vật tư mang mã cũ đổi mã theo (5.4). Khóa vẫn cần dù mã đã chạy theo: sửa một mã ở danh mục là đổi mã hàng loạt vật tư. Không ai xóa trắng được mã. Bản ghi chưa có mã thì nhập được một lần, rồi khóa.

**Item Defaults.default_supplier**: không xóa (nhiều luồng core đang dùng, danh sách ở mục 13). Ẩn khỏi form, hệ thống tự đồng bộ theo dòng `is_default` (xem 5.5).

---

## 5. Logic

### 5.1 Chuẩn hóa mã

Từ mã NCC nguyên bản tạo ra hai giá trị:

| Giá trị | Cách tạo | Dùng cho |
|---|---|---|
| Phần ghép mã | Bỏ dấu tiếng Việt; bỏ mọi ký tự không phải chữ hoặc số (khoảng trắng, `-`, `/`, `.`, `#`…); **giữ nguyên hoa/thường**; rồi **lấy tối đa 11 ký tự đầu** (2.4) | Ghép vào Item Code |
| Khóa so khớp | Như trên nhưng **không cắt**, đưa về chữ hoa | So trùng (mục 6) |

- `N-12345`, `N12345`, `N 12345` cho cùng phần ghép mã `N12345`. `n12345` cho phần ghép mã khác (`n12345`) nhưng cùng khóa so khớp.
- `item_group_code` và `brand_code` cũng chỉ được chứa chữ không dấu và số, và bị cắt về 3 và 6 ký tự (2.4); kiểm tra khi lưu danh mục, ở mọi chế độ đặt tên.
- Frappe chỉ cấm `<` và `>` trong tên bản ghi. Các ký tự khác bị bỏ vì làm hỏng đường dẫn, tem nhãn và việc tách mã, không phải vì hệ thống cấm.
- Mã NCC **nguyên bản** giữ nguyên trong `supplier_part_no`.

### 5.2 Validate (server)

Chỉ áp dụng khi Stock Settings đang ở chế độ "Quy tắc mã vật tư" và Item thuộc phạm vi D4.

**Lúc tạo mới** (chặn nếu thiếu):

1. Có `item_group` và nhóm đó có `item_group_code`.
2. Có `brand` và brand đó có `brand_code`.
3. `supplier_items` có ít nhất một dòng.
4. **Đúng một** dòng `is_default`. Nếu chỉ có một dòng thì tự tick. Nhiều dòng mà không dòng nào tick thì báo lỗi.
5. Dòng `is_default` phải có `supplier_part_no`, trừ trường hợp theo D9.
6. Không có hai dòng cùng `supplier`.

**Lúc sửa** (mọi Item trong phạm vi, kể cả Item cũ): chỉ kiểm tra điều 4 và 6, và chỉ khi Item có dòng `supplier_items`. Item cũ thiếu mã nhóm, hãng hay NCC **vẫn lưu được** (D6).

Mọi lỗi báo tiếng Việt, nói rõ thiếu thành phần nào.

### 5.3 Sinh mã (`autoname` của Item)

- **Cách bật:** thêm lựa chọn thứ ba cho `Stock Settings.item_naming_by`. `Item.autoname` vốn đã rẽ nhánh theo giá trị này. Site chạy thật chọn chế độ mới; bộ test core vẫn chạy ở chế độ "Item Code" nên không bị ảnh hưởng.
- Chỉ chạy lúc tạo mới. Lúc này các dòng `supplier_items` đã nằm trong doc.
- Item ngoài phạm vi D4: giữ cách cũ, người dùng nhập Item Code.
- Item trong phạm vi: bỏ qua Item Code nhập vào (form, Data Import, API), ghép `{item_group_code}-{brand_code}-{phần ghép mã}`.
- Kiểm tra: mã chưa tồn tại. Phép kiểm tra tồn tại vốn không phân biệt hoa/thường. Không còn kiểm tra giới hạn 140 ký tự của cột `name`: với giới hạn 3-6-11 mã dài nhất là 22 ký tự.
- Gán kết quả vào `item_code` và `name`.
- Trạng thái "bắt buộc" của `item_code` do Stock Settings ghi thành Property Setter (hiện là bắt buộc). Sửa `item.json` sẽ bị giá trị này đè, nên phải thêm nhánh cho chế độ mới ngay trong `StockSettings.validate`: `item_code` không bắt buộc, không ẩn.
- Tắt Quick Entry của Item (`item.json` đang bật).

### 5.4 Sau khi đã có mã: mã chạy theo thông tin

Mã vật tư **luôn bằng** `{mã nhóm}-{mã thương hiệu}-{phần ghép mã}` tính từ thông tin hiện tại. Thông tin đổi thì mã đổi.

**Hai nguồn làm mã đổi**

| Thay đổi | Ai làm được | Vật tư nào đổi mã | Khi nào đổi |
|---|---|---|---|
| Trên Item: đổi Nhóm hàng, Thương hiệu, dòng NCC mặc định, hoặc mã hàng NCC của dòng mặc định | Ai sửa được Item | Chính Item đó | Ngay trong lần lưu |
| Trên Item Group, Brand: sửa `item_group_code`, `brand_code` | Người có vai trò được đổi mã vật tư, qua nút mở khóa (mục 4) | Mọi Item thuộc nhóm/thương hiệu đó đang mang mã cũ | Tối đa 20 Item: ngay trong lần lưu. Nhiều hơn: tiến trình nền |
| Gộp (Merge) hai Item Group hoặc hai Brand mang mã khác nhau | Như trên | Các Item của bản ghi bị gộp | Như trên |
| Đổi tên Item Group, Brand | Ai sửa được danh mục | Không Item nào: mã không đổi theo tên | |

**Cách đổi.** Đổi mã vật tư là đổi tên bản ghi Item (`rename_doc`): hệ thống cập nhật mọi trường liên kết tới Item — 103 trường ở 86 bảng trên fork này — nên mọi chứng từ, kể cả chứng từ đã ghi sổ, hiện mã mới. Mỗi lần đổi mã để lại một dòng "renamed from … to …" trong lịch sử của vật tư.

**Vật tư nào chạy theo.** Chỉ vật tư mang dấu `item_code_by_rule` (trường ẩn, hệ thống tự đặt lúc sinh mã). Lý do không nhìn hình dạng mã: mã đặt tay kiểu `TB-001-A` cũng có ba phần.

- Mã đặt tay (có từ trước quy tắc, dịch vụ, tài sản): không bao giờ bị đổi (D6).
- Vật tư mang dấu: mã được tính lại ở **mọi lần lưu**, không chỉ khi thông tin vừa đổi, nên vật tư đang lệch tự về đúng mã.
- Vật tư mang dấu phải luôn đủ nhóm có mã, thương hiệu có mã và NCC mặc định; thiếu thì không lưu được.

**Kiểm tra trước khi đổi** (bị từ chối thì không có gì được ghi):

- Trùng lớp 1 (cùng thương hiệu, cùng mã hàng NCC với Item khác): chặn. Lớp 2: cảnh báo. Item không bị coi là trùng với chính nó.
- Mã mới đã có Item khác giữ: chặn.
- Đổi dây chuyền từ danh mục: tính trước mã mới của **tất cả** Item; chỉ cần một mã đụng mã đã có thì từ chối cả lượt, không đổi nửa chừng.

**Số thứ tự (D9).** Item không có mã hàng NCC giữ số đang có khi nhóm và thương hiệu không đổi. Sang cặp nhóm–thương hiệu khác thì lấy số kế tiếp của cặp mới. Trong đổi dây chuyền, số thứ tự đụng nhau thì cấp số kế tiếp thay vì chặn.

**Đổi tay.** Người có vai trò được phép vẫn đổi tên hoặc gộp Item bằng tay (`Item.before_rename` chặn những người khác). Item bị đổi tên tay thì **mất dấu** `item_code_by_rule`, tức thôi chạy theo thông tin. Đây là lối thoát cho ca quy tắc không cho ra mã dùng được, ví dụ hai mã hàng NCC dài trùng nhau ở 11 ký tự đầu.

**Trên form.** Sửa thông tin của Item mang dấu thì dải thông báo đầu form ghi trước "Mã vật tư sẽ đổi từ A thành B khi lưu". Lưu xong, form tự chuyển sang mã mới.

**Cái giá của việc cho mã đổi** — cần nghiệp vụ biết trước khi bật trên production:

| Hệ quả | Mức độ | Giảm thiểu |
|---|---|---|
| Giấy tờ đã phát hành mang mã cũ: báo giá, đơn hàng đã in, tem nhãn, **hóa đơn điện tử đã gửi cơ quan thuế**, bảng mã NCC đang giữ | Cao | Hệ thống không sửa được thứ đã ra ngoài. Tra mã cũ qua lịch sử của vật tư; chưa có ô tìm theo mã cũ (xem 14.11) |
| Dữ liệu lưu mã vật tư ở trường không phải liên kết (ghi chú, file đính kèm, app khác lưu dạng chữ) không được cập nhật | Trung bình | Rà các app dùng chung site (`assetcore`, `antmed_crm`, …) trước khi bật |
| Tốc độ: khoảng 1 giây cho một Item trên site dev gần như trống; mỗi lần đổi còn quét toàn bộ bảng thuế của hóa đơn (`Item.after_rename`) | Cao với đổi dây chuyền | Quá 20 Item thì chạy nền. **Phải đo trên bản sao production** trước khi cho sửa mã nhóm, mã thương hiệu ở đó |
| Đổi dây chuyền chạy nền: trong lúc chạy, một phần Item còn mang mã cũ; Item lỗi bị bỏ qua và ghi vào Error Log | Trung bình | Người sửa nhận thông báo khi xong, kèm danh sách Item chưa đổi; Item đó tự về đúng mã ở lần lưu tới |
| Người khác đang mở form của Item vừa bị đổi mã | Thấp | Họ gặp lỗi "không tìm thấy" và phải mở lại theo mã mới |
| Sửa một ô trên Item là đổi mã trên mọi chứng từ: thao tác nhỏ, hậu quả rộng | Cao | Form báo trước mã sẽ đổi; cân nhắc giới hạn quyền sửa Nhóm hàng, Thương hiệu của Item đã có giao dịch (chưa làm) |

**Đồng bộ NCC mặc định.** Cho phép đổi dòng `is_default` sang NCC khác; hệ thống đồng bộ `default_supplier` trong Item Defaults theo dòng này (5.5), và mã đổi theo mã hàng của NCC mới.

### 5.5 Đồng bộ `default_supplier`

Khi lưu Item: với mỗi dòng trong Item Defaults, đặt `default_supplier` = NCC của dòng `is_default`. Cách này giữ nguyên các luồng core (Material Request → PO, drop ship, đặt hàng lại tự động, `get_item_details`) mà không phải sửa từng luồng.

- Item **không có** dòng `is_default` (Item cũ chưa khai `supplier_items`): giữ nguyên `default_supplier`, không xóa.
- Chạy sau `update_defaults_from_item_group`, vì hàm này điền `default_supplier` từ Item Group khi Item chưa có Item Defaults.

### 5.6 Pseudo-code

```python
def autoname(doc):
    if naming_mode() != "Quy tắc mã vật tư" or not in_scope(doc):   # D4
        return default_autoname(doc)      # giữ cách đặt tên hiện tại

    validate_on_create(doc)               # mục 5.2, gồm tự tick is_default
    row = get_default_supplier_row(doc)   # đúng một dòng is_default

    item_group_code = frappe.db.get_value("Item Group", doc.item_group, "item_group_code")
    brand_code = frappe.db.get_value("Brand", doc.brand, "brand_code")
    part = code_part(row.supplier_part_no) or next_sequence(item_group_code, brand_code)   # D9
    # code_part đã cắt về 11 ký tự đầu; mã nhóm và ID Brand đã được cắt từ lúc lưu danh mục (2.4)

    code = f"{item_group_code}-{brand_code}-{part}"   # giữ nguyên hoa/thường, tối đa 22 ký tự

    if frappe.db.exists("Item", code):    # không phân biệt hoa/thường
        frappe.throw(_("Mã {0} đã tồn tại").format(code))

    check_duplicate_item(doc, match_key(row.supplier_part_no))   # mục 6

    doc.item_code = code
    doc.name = code
```

---

## 6. Phát hiện vật tư đã có trong hệ thống

### 6.1 Hai lớp nhận diện

| Lớp | Cách so khớp | Kết quả |
|---|---|---|
| 1 | Cùng Brand **và** cùng khóa so khớp của mã hàng NCC | **Chặn** tạo mới, chỉ ra Item đang giữ |
| 2 | Cùng khóa so khớp ở Item khác Brand | **Chỉ cảnh báo**, không chặn và không hỏi lại |

- Cảnh báo lớp 2 hiện ngay trên form lúc người dùng điền mã hàng NCC (cùng chỗ với "Mã dự kiến"), và hiện lại sau khi lưu. Form, Data Import và API cho cùng một kết quả: vật tư vẫn được tạo, kèm cảnh báo.
- Trên form, vật tư trùng lớp 1 cũng được chỉ ra ngay lúc điền, trước khi bấm lưu.
- **Đã bỏ (12/10/2026):** gợi ý theo tên hàng (lớp 3 cũ) và so theo mã hãng sản xuất lúc tra cứu. Còn lại một cảnh báo khi lưu Item Manufacturer mà mã của nhà sản xuất đã khai cho vật tư khác.
- Vật tư mang số thứ tự (D9) không có mã hàng NCC để so, nên không có cảnh báo nào.

### 6.2 Điểm vào

Không có màn hình tra cứu riêng (đã bỏ 12/10/2026). Người dùng tạo vật tư bằng form Item như thường lệ; mọi luồng tạo (form, Data Import, API) đều đi qua cùng kiểm tra server ở mục 5 và 6.1. Quick Entry của Item vẫn tắt.

### 6.3 Nhập báo giá theo lô

1. Nhận file báo giá vào bảng tạm (chưa tạo Item).
2. Đối chiếu từng dòng, gắn trạng thái *Đã có / Có thể trùng / Chưa có*.
3. Người phụ trách duyệt các dòng "có thể trùng".
4. Chỉ dòng "Chưa có" mới tạo Item mới; dòng "Đã có" chỉ cập nhật NCC và giá.

Có thể tận dụng logic đối chiếu báo giá với Master đang dùng cho sheet BaoGia.

---

## 7. Giao diện

- Item Code chỉ đọc với Item trong phạm vi; hiển thị **"Mã dự kiến"** cập nhật khi người dùng chọn nhóm, hãng, nhập NCC. Item ngoài phạm vi (dịch vụ, tài sản) vẫn nhập mã tay.
- Bảng `supplier_items` hiển thị cột `is_default`; tự tick khi chỉ có một dòng.
- `brand` và `supplier_items` bắt buộc có điều kiện theo phạm vi D4.
- Cảnh báo khi sửa nhóm/hãng/NCC của Item đã có mã.
- Quyền tạo/sửa Brand và Item Group: trong fork đã chỉ vai trò Item Manager làm được. Việc còn lại là rà xem ai đang giữ vai trò này (tránh sinh Brand trùng như "Sysmex" / "SYSMEX").

---

## 8. Dữ liệu cũ

- Patch: với mỗi Item hiện có, tick `is_default` cho dòng `supplier_items` khớp `default_supplier`; xuất báo cáo các Item không xác định được để xử lý tay. Nếu chốt D10, patch điền luôn `supplier_part_no_key`.
- Không đổi mã Item cũ: chúng không mang dấu `item_code_by_rule` nên không chạy theo thông tin.
- Xuất danh sách Item Group và Brand hiện có để nghiệp vụ điền `item_group_code`, `brand_code`. Bản ghi hiện có không bị bắt buộc có mã; chỉ bản ghi tạo mới sau khi bật quy tắc mới bắt buộc.
- Site dev không có dữ liệu để thử patch (0 dòng Item Supplier, 0 `default_supplier`, 2 Brand test). Phải chạy thử trên bản sao production.

---

## 9. Kế hoạch theo giai đoạn

| GĐ | Nội dung | Đầu ra | Phụ thuộc |
|---|---|---|---|
| 0 | **Khảo sát fork**. Phần code đã xong (mục 13). Còn lại: thống kê production (số Item, số Item có `supplier_items`, có `default_supplier`, số Brand/Item Group chưa có mã) | Số liệu hiện trạng production | — |
| 1 | **Dữ liệu nền**: thêm các trường mục 4; nghiệp vụ điền mã nhóm/hãng và chốt cách viết hoa/thường; rà vai trò Item Manager | Danh mục mã được duyệt | D1; nghiệp vụ duyệt danh mục |
| 2 | **Logic lõi**: chế độ đặt tên mới trong Stock Settings, chuẩn hóa, `autoname`, validate, chống trùng lớp 1–2, đồng bộ `default_supplier`, chặn đổi tên/gộp mã, tắt Quick Entry | Tạo Item mới ra mã đúng, chặn trùng | GĐ 0, 1; D2, D9 |
| 3 | **Giao diện form**: mã dự kiến, cảnh báo trùng mã hàng NCC | Form Item | GĐ 2 |
| 4 | **Nhập báo giá theo lô** (có thể làm sau) | Bảng tạm + đối chiếu + duyệt | GĐ 2, 3 ổn định |
| 5 | **Dữ liệu cũ và kiểm thử**: patch, chạy trên bản sao, UAT với người nhập báo giá | Báo cáo kiểm thử | GĐ 2–3 |
| 6 | **Triển khai**: sao lưu, migrate, patch ngoài giờ; bật chế độ đặt tên mới; hướng dẫn người dùng; ghi lại file core đã sửa | Bản chạy thật | GĐ 5 |

Phần còn lại của Giai đoạn 0 và các quyết định D1, D2, D9 làm song song. Giai đoạn 4 tách riêng được.

---

## 10. Ca kiểm thử

| # | Tình huống | Kỳ vọng |
|---|---|---|
| 1 | Đủ nhóm, hãng, một NCC có mã | Ra đúng `HCH-VinaH-N12345` |
| 2 | Một dòng NCC duy nhất | Tự tick `is_default`, sinh mã đúng |
| 3 | Nhiều dòng NCC, không dòng nào tick | Bị chặn |
| 4 | Tick hai dòng | Bị chặn |
| 5 | Dòng tick thiếu mã NCC | Theo D9 |
| 6 | Hai dòng cùng NCC | Bị chặn |
| 7 | Vật tư trong phạm vi thiếu hãng | Bị chặn |
| 8 | Nhóm hoặc hãng (có từ trước) chưa có mã | Bị chặn lúc tạo Item, báo rõ |
| 9 | Hàng dịch vụ (không quản lý tồn kho) hoặc tài sản cố định | Không bị ràng buộc, nhập mã tay được |
| 10 | Mã NCC có khoảng trắng, `/`, `-` | Phần ghép mã bỏ các ký tự đó, mã NCC gốc giữ nguyên |
| 11 | Cùng Brand + cùng mã NCC (khác cách viết, khác hoa/thường) | Bị chặn, chỉ ra Item đang giữ |
| 12 | Cùng mã NCC, khác Brand (trên form) | Cảnh báo ngay khi điền và sau khi lưu; vẫn lưu được |
| 13 | Đã có `brand_code` `VinaH`, khai thêm Brand mã `VINAH` | Bị chặn: mã hãng không phân biệt hoa/thường |
| 14 | Mã hàng NCC dài hơn 11 ký tự (sau khi bỏ ký tự phân cách) | Mã vật tư lấy 11 ký tự đầu, có thông báo; `supplier_part_no` giữ nguyên văn |
| 15 | Tạo qua Data Import và API | Cùng mã với form; Item Code nhập vào bị bỏ qua |
| 16 | Đổi NCC mặc định sang NCC có mã hàng khác | Mã vật tư đổi phần thứ ba theo mã hàng của NCC mới; `default_supplier` đồng bộ |
| 17 | Sửa Nhóm hàng hoặc Thương hiệu của Item do quy tắc sinh (người dùng thường) | Mã vật tư đổi phần tương ứng; mọi liên kết theo mã mới; form chuyển sang mã mới |
| 18 | Tạo PO từ Material Request | Vẫn lấy đúng NCC mặc định |
| 19 | Item cũ không có `is_default` sau patch | Có trong báo cáo xử lý tay, không làm hỏng Item |
| 20 | Brand mã `VinaH`, mã NCC `n12345` | Mã ra `HCH-VinaH-n12345`, không bị đổi sang chữ hoa |
| 21 | Tra cứu hoặc quét `hch-vinah-n12345` | Ra đúng Item `HCH-VinaH-N12345` |
| 22 | Cùng mã NCC, khác Brand, tạo qua Data Import | Tạo được, kèm cảnh báo liệt kê Item nghi trùng |
| 23 | Sửa và lưu Item cũ thiếu hãng, thiếu NCC | Lưu được, mã không đổi |
| 24 | Item cũ có `default_supplier` nhưng không có dòng `supplier_items` | Lưu xong `default_supplier` vẫn còn |
| 25 | Đổi tên hoặc gộp mã Item trong phạm vi, người dùng không có vai trò được phép | Bị chặn |
| 26 | Stock Settings ở chế độ "Item Code" | Không ràng buộc nào chạy; bộ test core không đổi kết quả |
| 27 | Hai mã NCC chỉ khác dấu phân cách (`12.5` và `125`), cùng Brand | Bị chặn như trùng lớp 1 |
| 28 | Khai mã nhóm hoặc mã thương hiệu có dấu, khoảng trắng, `-` | Bị chặn |
| 29 | Người dùng thường sửa hoặc đổi hoa/thường mã nhóm đã lưu | Bị chặn, có vật tư mang mã hay chưa; nếu có thì nêu số vật tư |
| 30 | Người dùng thường sửa mã thương hiệu đã lưu; hoặc gộp Brand đang có vật tư mang mã | Bị chặn |
| 31 | Sửa mã hàng NCC của dòng mặc định | Mã vật tư đổi phần thứ ba. Chỉ đổi cách viết (dấu phân cách) thì mã giữ nguyên; đổi hoa/thường thì mã đổi hoa/thường |
| 32 | Như 16, 17, 31 nhưng Item mang mã đặt tay (kể cả mã có ba phần như `TB-001-A`) | Mã giữ nguyên, có thông báo |
| 33 | Người có vai trò được phép sửa mã nhóm, mã thương hiệu qua nút mở khóa | Mọi Item mang mã cũ đổi mã theo; Item mang mã đặt tay không đổi |
| 34 | Đổi tên Item Group hoặc Brand (không gộp) | Không khóa: mã không đổi; Item và chứng từ tự cập nhật theo tên mới |
| 35 | Gộp Item Group đang có vật tư mang mã vào nhóm có mã khác | Bị chặn |
| 36 | Brand có tên tự do (có dấu, khoảng trắng, dài) và mã `VinaH` | Mã vật tư dùng `VinaH`; tên Brand không bị kiểm tra ký tự, không bị cắt |
| 37 | Chọn Brand qua API bằng cách viết tên khác hoa/thường | Item lưu đúng ID của Brand; so trùng theo thương hiệu vẫn đúng |
| 38 | Nhập mã nhóm `VTTH` | Lưu thành `VTT`, có thông báo đã cắt |
| 39 | Nhập mã thương hiệu `SYSMEX1000` | Lưu thành `SYSMEX`, có thông báo đã cắt |
| 40 | Nhập mã thương hiệu `SYSMEX2000` khi đã có mã `SYSMEX` | Bị chặn: mã sau khi cắt đã có |
| 41 | Tên Brand dài hơn 6 ký tự | Không bị cắt: giới hạn chỉ áp cho mã |
| 42 | Mã nhóm, Brand đúng 3 và 6 ký tự; mã hàng NCC đúng 11 ký tự | Giữ nguyên, không có thông báo cắt |
| 43 | Mã hàng NCC `N-123456-12/34` (14 ký tự gõ vào, 11 chữ và số) | Không bị cắt: ký tự phân cách không tính vào 11 |
| 44 | Hai mã hàng NCC dài, giống nhau ở 11 ký tự đầu, cùng nhóm, cùng Brand | Cái thứ hai bị chặn vì trùng mã vật tư, không báo là trùng vật tư; form báo trước |
| 45 | Như 44 nhưng khác nhóm | Tạo được cả hai, không cảnh báo trùng |
| 46 | Cùng Brand, cùng mã hàng NCC dài (khác cách viết) | Bị chặn như trùng lớp 1: so theo mã đầy đủ |
| 47 | Mã nhóm dài hơn 3 hoặc mã thương hiệu dài hơn 6 có từ trước khi đặt giới hạn | Bị chặn lúc tạo Item, báo rõ |
| 48 | Tạo Item Group hoặc Brand không nhập mã, ở chế độ quy tắc (form, Quick Entry, cây nhóm hàng, Data Import, API) | Bị chặn: mã bắt buộc khi tạo |
| 49 | Như 48, mã chỉ gồm khoảng trắng | Bị chặn |
| 50 | Như 48, ở chế độ "Item Code" | Tạo được, mã để trống |
| 51 | Sửa và lưu Item Group, Brand có từ trước mà chưa có mã, ở chế độ quy tắc | Bị chặn cho tới khi nhập mã; nhập xong thì lưu được và mã khóa lại |
| 52 | Code tạo cây nhóm khung cho công ty Việt Nam, ở chế độ quy tắc | Tạo được nhóm chưa có mã |
| 53 | Xóa trắng mã nhóm, mã thương hiệu đã lưu | Bị chặn với mọi người dùng: mã bắt buộc |
| 54 | Sửa trường khác của Item Group, Brand đã có mã | Lưu được |
| 55 | Mở Item Group, Brand đã có mã bằng tài khoản thường / tài khoản có vai trò được phép | Ô mã chỉ đọc / ô mã chỉ đọc kèm nút mở khóa |
| 56 | Lưu Item do quy tắc sinh mà không đụng nhóm, thương hiệu, NCC | Mã giữ nguyên, không có thông báo đổi mã |
| 57 | Item do quy tắc sinh: xóa mã hàng NCC / thêm mã hàng NCC cho Item đang mang số thứ tự | Lấy số thứ tự kế tiếp / lấy mã hàng NCC |
| 58 | Item mang số thứ tự: lưu lại không đổi nhóm, thương hiệu / chuyển sang nhóm khác | Giữ số / lấy số kế tiếp của cặp mới |
| 59 | Sửa Item thành cùng thương hiệu, cùng mã hàng NCC với Item khác | Bị chặn như trùng lớp 1; Item giữ mã cũ |
| 60 | Sửa Item do quy tắc sinh: xóa Thương hiệu | Bị chặn: chưa đủ thông tin để sinh mã |
| 61 | Item do quy tắc sinh đang lệch với mã nhóm (mã nhóm bị sửa thẳng trong dữ liệu) | Lần lưu tới tự về đúng mã |
| 62 | Sửa mã nhóm mà một mã vật tư mới sẽ đụng mã đã có | Từ chối cả lượt, không Item nào đổi |
| 63 | Gộp hai nhóm đều có Item mang số thứ tự `X0001` | Item của nhóm bị gộp nhận số kế tiếp |
| 64 | Gộp vào nhóm chưa có mã, khi nhóm bị gộp có Item mang mã | Bị chặn |
| 65 | Sửa mã nhóm của nhóm có hơn 20 Item mang mã | Đổi ở tiến trình nền; người sửa được báo khi xong |
| 66 | Người có vai trò được phép đổi tên Item bằng tay, rồi sửa nhóm của Item đó | Mã đặt tay được giữ; Item mất dấu `item_code_by_rule` |
| 67 | Người dùng tự bật hoặc tắt `item_code_by_rule` qua API | Hệ thống đặt lại theo giá trị cũ |
| 68 | Lưu Item từ form khi mã đổi | Phản hồi mang mã mới và `localname` là mã cũ; form chuyển sang mã mới |

---

## 11. Rủi ro

| Rủi ro | Giảm thiểu |
|---|---|
| Sửa core gây khó nâng cấp ERPNext | Gom thay đổi vào ít file nhất, đánh dấu rõ, ghi danh sách file đã sửa (mục 13) |
| Ràng buộc mới làm gãy bộ test core (91 file test tạo Item không có hãng, NCC) | Bật quy tắc bằng chế độ đặt tên riêng trong Stock Settings; test core chạy ở chế độ cũ |
| `default_supplier` đồng bộ sai làm hỏng luồng mua hàng | Kiểm thử PO, Material Request, drop ship; chọn cách đồng bộ thay vì sửa từng luồng |
| Danh mục mã nhóm/hãng làm trễ tiến độ | Giao nghiệp vụ duyệt sớm (GĐ 1), tách khỏi phần code |
| Người dùng lách (tạo Brand mới, viết mã NCC khác cách) | Phân quyền Brand/Item Group, chuẩn hóa, một điểm vào duy nhất |
| Hàng cùng loại nhưng NCC đặt mã khác nhau, lớp 1–2 không bắt được | Cảnh báo khi khai trùng mã của nhà sản xuất ở Item Manufacturer; người duyệt danh mục tìm theo tên trước khi tạo |
| Hai mã NCC khác nhau thật nhưng trùng sau khi bỏ dấu phân cách (ca 27) | Chấp nhận chặn; xử lý tay qua vai trò quản trị danh mục |
| Cùng một hãng bị viết hai kiểu hoa/thường ở hai Item | `brand_code` lấy từ danh mục, không gõ tay trên Item |
| Sửa mã nhóm, đổi tên Brand, đổi nhóm/thương hiệu của Item làm mã vật tư lệch với danh mục | Khóa ở 5.4; chỉ vai trò được chỉ định mới đổi được, kèm cảnh báo |
| Mã bắt buộc làm khó việc tạo, sửa nhóm dịch vụ, nhóm cha (không dùng để sinh mã) | Chấp nhận: mọi nhóm đều có mã 3 ký tự. Nếu nghiệp vụ thấy vướng thì nới thành "chỉ bắt buộc với nhóm lá" |
| Bật quy tắc trên site đang chạy làm các luồng tự tạo Item Group, Brand (cài đặt, dữ liệu mẫu, test) bị chặn | Chỉ bắt buộc ở chế độ quy tắc; code tạo cây nhóm khung dùng `ignore_mandatory` |
| Đổi mã Item làm lệch giấy tờ đã phát hành, dữ liệu ngoài hệ thống và chạy chậm khi đổi hàng loạt | Bảng "Cái giá của việc cho mã đổi" ở 5.4. Item mang mã đặt tay không bị đổi |
| Giới hạn 6 ký tự làm hai Brand khác nhau cắt ra cùng một mã (`SYSMEX1000`, `SYSMEX2000`) | Chặn khi lưu mã thứ hai; nghiệp vụ lập bảng mã viết tắt (ví dụ `SYSXN1`, `SYSXN2`) trước khi nhập |
| Giới hạn 11 ký tự làm hai mặt hàng khác nhau của cùng nhóm, cùng Brand ra cùng một mã | Chặn và báo trước trên form; người quản trị danh mục xử lý tay. Cần số liệu production về độ dài mã hàng NCC để biết tần suất |
| Mã khóa ngay sau lần lưu đầu nên gõ nhầm là phải nhờ người có quyền sửa | Chấp nhận: đổi lại được sự chắc chắn là mã không đổi sau khi đã công bố. Form ghi rõ "Đã lưu thì không sửa được" |
| Tự cắt làm người dùng không để ý mã đã khác thứ mình gõ | Có thông báo "Mã đã được cắt ngắn" ở cả ba chỗ; mô tả trường ghi rõ giới hạn |

---

## 12. Checklist review cuối

**Quy tắc**
- [ ] Đồng ý sửa văn bản gốc: "NCC số 1 hoặc NCC mặc định" → "NCC đánh dấu mặc định trong Supplier Items"
- [ ] Đồng ý mã vật tư chạy theo nhóm hàng, thương hiệu, mã hàng NCC, kèm các hệ quả ở 5.4 (thay cho "mã bất biến sau khi tạo")
- [ ] Đồng ý bắt buộc đủ nhóm, hãng, NCC cấp mã với vật tư trong phạm vi
- [ ] Đồng ý mã giữ nguyên hoa/thường, và hai mã chỉ khác hoa/thường được coi là một (2.2)
- [ ] Đồng ý tài liệu này ưu tiên hơn FRD-MAP-01 ở quy tắc mã (1.2)

**Quyết định chặn**
- [ ] D1 chốt: nguồn chuẩn Item Group / Nhóm vật tư
- [ ] D2 chốt: mã NCC hay mã hãng sản xuất
- [ ] D9 chốt: NCC không có mã hàng

**Thiết kế**
- [ ] Brand riêng cho từng cặp hãng–model (D3)
- [ ] Phạm vi: Item có quản lý tồn kho, không phải tài sản, không phải mẫu/biến thể (D4)
- [ ] Brand `OTH` cho hàng không có hãng (D5)
- [ ] Không đổi mã Item mang mã đặt tay (D6)
- [ ] Giữ `default_supplier` và đồng bộ, không bỏ hẳn
- [ ] Thêm trường khóa so khớp `supplier_part_no_key` (D10)
- [ ] Bật quy tắc bằng lựa chọn thứ ba của `item_naming_by`

**Thực thi**
- [ ] Giao Hiếu hoàn tất Giai đoạn 0: lấy số liệu production
- [ ] Giao nghiệp vụ lập danh sách mã nhóm và mã hãng, kèm cách viết hoa/thường
- [ ] Chốt giai đoạn 4 (nhập lô) làm cùng hay làm sau
- [ ] Chốt môi trường dev/bản sao dữ liệu để chạy thử

---

## 13. Kết quả khảo sát fork (Giai đoạn 0, phần code)

Khảo sát ngày 09/10/2026, nhánh `feat/vn-tbyt-ho-so-phap-ly`, site dev `miyano`.

### 13.1 Hiện trạng code

| Hạng mục | Hiện trạng |
|---|---|
| Đặt tên Item | `Item.autoname` ở `erpnext/stock/doctype/item/item.py:156`, rẽ nhánh theo `item_naming_by`. Site đang ở "Item Code" (nhập tay) |
| Trường `item_code` | Trạng thái bắt buộc/ẩn do `StockSettings.validate` ghi thành Property Setter (`erpnext/stock/doctype/stock_settings/stock_settings.py:80`, `erpnext/utilities/naming.py`) |
| Item | `allow_rename = 1`, `quick_entry = 1`, `track_changes = 1`. `before_rename` ở `item.py:549` xử lý cả gộp mã |
| `is_purchase_item` | Mặc định 1. Trên site 30/30 Item đều bật, kể cả nhóm dịch vụ |
| `supplier_items` | Core không có kiểm tra nào trên bảng này. Item Supplier chỉ có `supplier`, `supplier_part_no` |
| Item Manufacturer | Doctype riêng (không phải bảng con của Item), liên kết tới Manufacturer, có sẵn `is_default` |
| Hãng trong TBYT | `TBYT Marketing Authorization.chu_so_huu` liên kết tới Manufacturer |
| Brand | Đặt tên theo trường `brand`; `quick_entry = 1`; chỉ Item Manager tạo/sửa |
| Item Group | Đặt tên theo `item_group_name`; có `la_tbyt`; chỉ Item Manager tạo/sửa |
| "Nhóm vật tư" | Không có trường này trên Item |
| Collation | `utf8mb4_unicode_ci` trên Item, Brand, Item Group, Item Supplier. Cột `name` và `item_code` dài 140 ký tự |
| Tên bản ghi | `frappe/model/naming.py` chỉ cấm `<` và `>` |
| Biến thể | Tạo ở `erpnext/controllers/item_variant.py:52` và `:203`, có cách đặt mã riêng (D7) |
| App khác | Không tìm thấy chỗ tạo Item trong `antmed_crm`, `assetcore`, `workflowcore`, `normcore_dmktkt`, `norm_himedic`, `hrms` (tìm theo `new_doc("Item")` và `"doctype": "Item"`) |

### 13.2 Nơi đang dùng `default_supplier`

| File | Dùng để |
|---|---|
| `erpnext/stock/doctype/material_request/material_request.py` | Tách PO theo NCC khi tạo từ Yêu cầu vật tư |
| `erpnext/stock/get_item_details.py` | Điền NCC mặc định lên dòng chứng từ |
| `erpnext/controllers/buying_controller.py` | Điền NCC cho chứng từ mua |
| `erpnext/selling/doctype/sales_order/sales_order.py` | Tạo PO từ Sales Order |
| `erpnext/manufacturing/doctype/production_plan/production_plan.py` | Kế hoạch sản xuất → Yêu cầu vật tư |
| `erpnext/buying/report/supplier_quotation_comparison/supplier_quotation_comparison.py` | Báo cáo so sánh báo giá |
| `erpnext/stock/doctype/item/item.py:733`, `:749` | `update_defaults_from_item_group` lấy NCC mặc định từ Item Group |

### 13.3 Số liệu site dev

30 Item (28 là dữ liệu test), 0 dòng Item Supplier, 0 Item Defaults có `default_supplier`, 2 Brand (đều là test), 12 Item Group. Không đại diện cho production.

### 13.4 File đã sửa và file mới

File core đã sửa:

- `erpnext/stock/doctype/item/item.py` (`autoname`, `validate`, `before_rename`), `item.js`, `item_list.js`, `item.json`
- `erpnext/stock/doctype/item_supplier/item_supplier.json`, `item_supplier.py`
- `erpnext/stock/doctype/item_manufacturer/item_manufacturer.py`
- `erpnext/setup/doctype/item_group/item_group.json`, `item_group.py`
- `erpnext/setup/doctype/brand/brand.json`, `brand.py`
- `erpnext/stock/doctype/stock_settings/stock_settings.json`, `stock_settings.py`
- `erpnext/patches.txt`

File mới:

- `erpnext/stock/item_code_rule.py`: toàn bộ logic (chuẩn hóa, sinh mã, validate, chống trùng, tra cứu, patch dữ liệu cũ)
- `erpnext/stock/tests/test_item_code_rule.py`
- `erpnext/patches/v15_0/mark_default_item_supplier.py`
- `erpnext/stock/report/vat_tu_chua_co_ncc_mac_dinh/`: báo cáo "Vat Tu Chua Co NCC Mac Dinh"

---

## 14. Trạng thái triển khai (12/10/2026)

Nhánh `feat/vn-tbyt-ho-so-phap-ly`, chưa commit. Site dev `miyano` đã migrate và **đã chuyển sang chế độ "Quy tắc mã vật tư"** để chạy thử (mục 14.5). Hướng dẫn cho người dùng: `docs/HDSD_SinhMaVatTu_MiyanoERP_20261013_V1.6.docx`.

### 14.1 Đã làm

| Giai đoạn | Nội dung | Ghi chú |
|---|---|---|
| 1 | Các trường ở mục 4 | Mã nhóm, mã thương hiệu bắt buộc và khóa sau khi lưu, kiểm tra trên server thay cho `reqd` (mục 4) |
| 2 | Chế độ đặt tên mới, chuẩn hóa, sinh mã, validate, chống trùng lớp 1–2, đồng bộ `default_supplier`, chặn đổi tên/gộp mã, khóa các thành phần của mã, giới hạn 3-6-11, mã bắt buộc và khóa sau khi lưu ở danh mục, mã vật tư chạy theo thông tin, tắt Quick Entry | 146 test ở `erpnext/stock/tests/test_item_code_rule.py` |
| 3 | Form Item: mã dự kiến, bắt buộc có điều kiện, cảnh báo ngay khi mã hàng NCC đã có ở vật tư khác | Phần JavaScript **chưa chạy thử trên trình duyệt** |
| 5 | Patch đánh dấu NCC mặc định và báo cáo xử lý tay | Mới chạy trên site dev, nơi không có dòng Item Supplier nào |

Các quyết định D1, D2, D9, D10 chưa ai tick ở mục 12; code đi theo cột "Đề xuất".

### 14.2 Khác tài liệu ở chỗ nào

- Tắt Quick Entry của Item áp dụng cho mọi chế độ đặt tên, vì đây là thuộc tính của DocType, không bật tắt theo Stock Settings được.
- Khóa so khớp `supplier_part_no_key` được điền ở mọi chế độ, để bật quy tắc lúc nào cũng có sẵn dữ liệu so trùng.

### 14.3 Chưa làm

- Giai đoạn 4 (nhập báo giá theo lô).
- Số liệu production (phần còn lại của Giai đoạn 0) và chạy patch trên bản sao production.
- UAT và Giai đoạn 6.
- Ca kiểm thử 18 (tạo PO từ Yêu cầu vật tư) chưa có test tự động: các bộ test core liên quan không chạy được trên site dev vì thiếu dữ liệu mẫu `_Test Company`.

### 14.4 Cách bật

1. Điền `Mã nhóm` (tối đa 3 ký tự) cho Item Group và `Mã thương hiệu` (tối đa 6 ký tự) cho Brand hiện có.
2. Stock Settings → Item Naming By → "Quy tắc mã vật tư"; chọn "Vai trò được đổi mã vật tư" nếu cần.
3. Người dùng bấm Reload trong menu avatar để nhận form mới.

### 14.5 Dữ liệu thử trên site dev

Tạo ngày 12/10/2026 để tập thao tác; mô tả của các Item này có ghi "Dữ liệu thử nghiệm quy tắc mã vật tư".

| Loại | Bản ghi |
|---|---|
| Mã nhóm | Vật tư y tế tiêu hao = `VTT`; Hóa chất-sinh phẩm = `HCS`; Thiết bị y tế và phụ kiện = `TBY`. Trước khi có giới hạn 3 ký tự, ba mã này là `VTTH`, `HCSP`, `TBYT` |
| Brand mới | Vinahankook (mã `VinaH`); Sysmex XN-1000 (mã `SYSMEX`); KHAC (mã `OTH`). ID là tên, mã ở trường riêng |
| Manufacturer mới | Sysmex Corporation |
| Item theo quy tắc | `VTT-VinaH-N12345`, `HCS-SYSMEX-CL50A` (có mã hãng sản xuất `DCL-300A`), `VTT-VinaH-FL216` (hai NCC), `VTT-OTH-X0001` (NCC không có mã hàng). Bốn vật tư này đã được đổi mã từ dạng cũ (`VTTH-…`, `HCSP-SYSMEX1000-…`) |
| Bản ghi người dùng tự tạo khi thử | Item `HCSP-VinaH-132LA`, `HCSP-SYSMEX1000-123LA`, `HCSP-SYSMEX1000-456LA`: đang lệch với mã nhóm `HCS` và mã thương hiệu `SYSMEX`. Đã được đánh dấu là mã do quy tắc sinh, nên **lần lưu tới sẽ tự đổi** thành `HCS-…`. Item Group "Kiểm thử" (chưa có mã) |
| Item kiểu cũ | `DEMO-VT003`: hai NCC, chưa chọn NCC mặc định, để thử báo cáo xử lý tay |

Hai NCC dùng trong dữ liệu thử là bản ghi có sẵn: Công ty TNHH Thiết bị Y tế An Phát, Công ty Cổ phần Vật tư Y tế Hà Nội.

Tắt chạy thử: Stock Settings → Item Naming By → "Item Code".

### 14.6 Điều chỉnh sau review (12/10/2026)

| Thay đổi | Trước | Sau |
|---|---|---|
| Màn hình tra cứu trước khi tạo | Nút tạo mới ở danh sách Item mở hộp tra cứu (thương hiệu, NCC, mã hàng NCC, tên hàng, mã hãng sản xuất) | Bỏ. `item_list.js` trở lại như gốc; bỏ các hàm `lookup_item`, `add_supplier_to_item` và gợi ý theo tên |
| Cùng mã hàng NCC, khác thương hiệu | Chặn cho tới khi người dùng xác nhận trên form; Data Import bị chặn hẳn | Chỉ cảnh báo, ở mọi luồng tạo |
| Cùng thương hiệu, cùng mã hàng NCC | Chặn | Vẫn chặn (hai vật tư này cùng nhóm thì trùng luôn cả mã) |
| Cách gọi | "Hãng", "Mã hãng" | "Thương hiệu (Brand)", "Mã thương hiệu (Brand Code)"; các nhãn mới đều kèm tiếng Anh trong ngoặc đơn |

Lưu ý khi chạy test: lúc site dev ở chế độ "Quy tắc mã vật tư", các bộ test core có tạo vật tư tồn kho không kèm thương hiệu và NCC sẽ lỗi (ví dụ `erpnext.stock.doctype.stock_settings.test_stock_settings`). Chuyển Stock Settings về "Item Code" trước khi chạy các bộ test đó.

### 14.7 Điều chỉnh lần hai (12/10/2026): ID của Brand là mã, khóa thành phần của mã

> Phần "ID của Brand là mã" trong mục này **đã bị thay ở 14.9**. Phần khóa vẫn giữ.

| Thay đổi | Trước | Sau |
|---|---|---|
| Mã thương hiệu | Trường riêng `brand_code` trên Brand; ID của Brand là tên | **ID của Brand là mã.** Bỏ trường `brand_code`; ô ID mang nhãn "Mã thương hiệu (Brand Code)"; tên đầy đủ ở Description (có trong Quick Entry, hiện kèm khi chọn thương hiệu) |
| Brand mới ở chế độ quy tắc | Tên tự do | Phải là mã: chỉ chữ không dấu và số |
| Mã nhóm | Trường `item_group_code`, ID là tên nhóm | **Không đổi.** Item Group được liên kết từ 30 trường ở 29 loại chứng từ, code gốc tham chiếu tên nhóm mặc định ở 26 chỗ, và nhóm dịch vụ không cần mã |
| Sửa mã nhóm, đổi tên/gộp Brand, gộp Item Group | Không chặn | Khóa khi có vật tư mang mã đó (5.4) |
| Đổi Nhóm hàng, Thương hiệu trên Item | Chỉ cảnh báo | Khóa với Item mang mã đó; người có vai trò được phép thì vẫn đổi được, kèm cảnh báo |

Lưu ý khi triển khai:

- Cột `brand_code` còn nằm lại trong bảng `tabBrand` của site dev (hệ thống không tự xóa cột khi bỏ trường). Cột này không còn được dùng. Production chưa từng có cột này.
- Khóa nhận diện "vật tư mang mã" bằng cách tách mã vật tư theo dấu `-`. Mã có từ trước quy tắc mà tình cờ có đúng ba phần và phần đầu trùng mã nhóm cũng bị coi là mang mã.
- Form Item chưa làm mờ ô Nhóm hàng, Thương hiệu với vật tư đã khóa: người dùng sửa được trên màn hình và bị chặn lúc lưu, kèm thông báo.

### 14.8 Điều chỉnh lần ba (12/10/2026): giới hạn độ dài 3-6-11

Quy tắc ở mục 2.4. Phần đã làm:

| Hạng mục | Cách làm |
|---|---|
| Mã nhóm | `validate_component_code` cắt về 3 ký tự khi lưu Item Group, ở mọi chế độ đặt tên |
| Mã thương hiệu | `validate_component_code` cắt `brand_code` về 6 ký tự khi lưu Brand, ở mọi chế độ đặt tên (đã sửa theo 14.9; bản đầu cắt ID của Brand) |
| Mã hàng NCC | `code_part` cắt về 11 ký tự; `match_key` không cắt |
| Form Item | Dải "Mã vật tư dự kiến" ghi rõ khi mã hàng NCC bị cắt, và chuyển đỏ khi mã sau khi cắt đã có vật tư khác dùng |
| Bỏ | Kiểm tra giới hạn 140 ký tự và ca kiểm thử tương ứng: mã dài nhất giờ là 22 ký tự |

Ba con số nằm ở ba hằng số đầu file `erpnext/stock/item_code_rule.py` (`GROUP_CODE_LENGTH`, `BRAND_CODE_LENGTH`, `PART_CODE_LENGTH`), không cấu hình được trên màn hình. Cột trong cơ sở dữ liệu không bị thu hẹp.

### 14.9 Điều chỉnh lần bốn (13/10/2026): tách mã hệ thống và mã sinh Item Code, mã bắt buộc khi tạo

| Thay đổi | Trước (14.7, 14.8) | Sau |
|---|---|---|
| ID của Brand | Là mã thương hiệu; tên đầy đủ ở Description | **Là tên thương hiệu**, như gốc. Ô ID trở lại nhãn "Brand Name" |
| Mã thương hiệu | Không có trường riêng | Trường `brand_code`, nhãn "Mã thương hiệu (Brand Code)", unique, tối đa 6 ký tự; hiện kèm khi chọn thương hiệu |
| Item Group | ID là tên, kèm `item_group_code` | Không đổi cấu trúc; mã nhóm hiện kèm khi chọn nhóm hàng |
| Mã khi tạo Item Group, Brand | Không bắt buộc; thiếu thì chặn lúc tạo Item | **Bắt buộc khi tạo**, ở chế độ quy tắc (mục 4) |
| Khóa thương hiệu | Khóa đổi tên, gộp Brand | Khóa sửa `brand_code` và gộp Brand; đổi tên Brand không khóa nữa |
| Cây nhóm hàng | Hộp thoại thêm nhóm con chỉ có tên | Thêm ô Mã nhóm, bắt buộc ở chế độ quy tắc |

Lưu ý khi triển khai:

- Dấu bắt buộc trên form dùng `mandatory_depends_on`, đọc chế độ đặt tên từ dữ liệu khởi động của trình duyệt. Đổi chế độ trong Stock Settings xong, người dùng phải bấm Reload thì dấu này mới đổi theo; kiểm tra trên server thì có hiệu lực ngay.
- Phần giao diện của lần này (dấu bắt buộc trên form, ô mã trong hộp thoại cây nhóm hàng) **chưa chạy thử trên trình duyệt**.
- Cột `brand_code` trong bảng `tabBrand` của site dev (ghi chú ở 14.7) nay được dùng lại.

### 14.10 Điều chỉnh lần năm (13/10/2026): mã luôn bắt buộc, đã lưu thì khóa

| Thay đổi | Trước (14.9) | Sau |
|---|---|---|
| Bắt buộc | Chỉ khi tạo mới; bản ghi đã lưu thì ô mã không còn dấu bắt buộc và xóa trắng được | Mỗi lần lưu, ở chế độ quy tắc. Bản ghi cũ chưa có mã phải nhập mã ở lần sửa tới |
| Sửa mã đã lưu | Người dùng thường: chỉ bị chặn khi đã có vật tư mang mã. Người có quyền: sửa tự do | Người dùng thường: luôn bị chặn. Người có quyền: phải bấm nút mở khóa trên form |
| Ô mã trên form | Luôn nhập được | Chỉ đọc sau khi đã lưu có mã |

Lưu ý khi triển khai:

- Nút mở khóa và trạng thái chỉ đọc nằm ở `brand.js`, `item_group.js`; quyền mở khóa hỏi qua `item_code_rule.may_change_codes`. Việc chặn thật sự nằm trên server, nên sửa qua API hay Data Import cũng bị chặn như trên form.
- Trên site dev còn 10 Item Group và 2 Brand chưa có mã (các nhóm mặc định, nhóm dịch vụ, "Kiểm thử", `_Test Brand…`). Chúng vẫn dùng được trong chứng từ; ai mở ra sửa thì phải nhập mã.
- Phần giao diện của lần này **chưa chạy thử trên trình duyệt**.

### 14.11 Điều chỉnh lần sáu (13/10/2026): mã vật tư chạy theo thông tin

Thiết kế và phân tích ở mục 5.4. Tóm tắt thay đổi:

| Thay đổi | Trước | Sau |
|---|---|---|
| Sửa Nhóm hàng, Thương hiệu của Item do quy tắc sinh | Người dùng thường bị chặn; người có quyền sửa được, mã giữ nguyên | Ai sửa được Item cũng sửa được; mã đổi theo ngay trong lần lưu |
| Đổi NCC mặc định, sửa mã hàng NCC | Mã giữ nguyên, có cảnh báo | Mã đổi theo |
| Sửa mã nhóm, mã thương hiệu; gộp danh mục | Item giữ mã cũ, có cảnh báo | Mọi Item mang mã cũ đổi theo; quá 20 Item thì chạy nền |
| Nhận diện Item thuộc quy tắc | Theo hình dạng mã (ba phần) | Theo dấu `item_code_by_rule` |
| Đổi tên Item bằng tay (người có quyền) | Được, không hệ quả gì thêm | Được; Item thôi chạy theo thông tin |

Phần đã làm:

- `erpnext/stock/item_code_rule.py`: `plan_code_change` (tính và kiểm lúc validate), `apply_code_change` (đổi ở cuối `Item.on_update`), `_plan_cascade`, `rename_items` (đổi dây chuyền, có nhánh chạy nền), `after_item_rename`.
- `Item.on_update`, `Item.after_rename`; `on_update` và `after_rename` của Item Group, Brand.
- Form Item: báo trước mã sẽ đổi; Nhóm hàng, Thương hiệu, bảng NCC bắt buộc với Item do quy tắc sinh.
- Trường `Item.item_code_by_rule`.

Chưa làm, cần quyết định hoặc cần môi trường khác:

- **Đo tốc độ trên bản sao production.** Con số "1 giây một Item" là trên site dev gần như trống.
- **Tìm theo mã cũ.** Mã cũ chỉ còn trong lịch sử của vật tư; ô tìm kiếm không ra. Hướng đề xuất: lưu mã cũ vào một bảng con của Item và cho tìm theo nó.
- **Hạn chế đổi mã với Item đã có giao dịch**, đặc biệt Item đã lên hóa đơn điện tử. Hiện chưa hạn chế gì.
- **Patch cho production:** không cần. Production chưa có Item nào do quy tắc sinh, nên không Item nào mang dấu; Item cũ giữ mã. Trên site dev, 7 Item đã được đánh dấu bằng script dữ liệu thử.
- Phần giao diện (dải báo trước, form chuyển sang mã mới sau khi lưu) **chưa chạy thử trên trình duyệt**. Đã kiểm ở mức phản hồi của máy chủ: lần lưu trả về mã mới kèm `localname` là mã cũ, đúng cơ chế mà form dùng khi bản ghi mới được cấp tên.
- Việc đổi mã ở tiến trình nền cần worker đang chạy (`bench start` hoặc supervisor).

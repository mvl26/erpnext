# Gán vị trí cố định theo mặt hàng — thiết kế

Nhánh `feat/mo-rong-vi-tri-kho-warehouse`, module `erpnext/warehouse_operations/`.
Chốt ngày 15/09/2026 sau brainstorm với chủ đầu tư.

Đây là **khối A+B** của một việc lớn hơn gồm ba khối:

| | Khối | Trạng thái |
|---|---|---|
| **A** | Gán vị trí cố định cho mặt hàng (danh mục + ràng buộc + cây chọn) | **spec này** |
| **B** | Gợi ý ô khi xếp hàng | **spec này** |
| **C** | Nhãn nhập kho 50×30 (NCC · mặt hàng · lô · HSD · **vị trí** · mã vạch) + màn hình điền và in | spec riêng, ngay sau |

C là thứ chủ đầu tư nhìn thấy, nhưng nó **bắt buộc** đứng sau A+B: ô `{ViTri}` của
nhãn không có giá trị nào để in cho tới khi có A.

---

## 1. Vì sao cần

Spec ngày 14/09 (`2026-09-14-phieu-xep-chuyen-vi-tri-design.md` §2) nêu rõ **"Không tự
gợi ý ô đích"**, với lý do ghi thẳng trong mã (`vitri/xep.py::hang_chua_xep`):

> `den_o` KHÔNG được điền — không có căn cứ nào để gợi ý (trường `suc_chua` hiện = 0 trên
> cả 214 ô), mà gợi ý sai thì thủ kho tin theo rồi xếp nhầm.

Lý do đó đúng **khi căn cứ duy nhất là sức chứa**. Chủ đầu tư nay đưa một căn cứ khác và
mạnh hơn: **mỗi mặt hàng có một chỗ cố định trên kệ**, như kho SPD East Osaka vẫn làm.
Khi ô đã thuộc về đúng một mặt hàng thì câu "hàng này xếp đâu" trả lời được mà **không
cần biết sức chứa** — đó là điều mở khoá cho cả GĐ 2 lẫn nhãn nhập kho.

Đây cũng chính là §5.5 `Item Location Preference` mà spec gốc
(`2026-09-09-miyano-wms-vi-tri-kho-design.md`) đã trù liệu, và là nhánh mà
`vitri/hook_sle.py:9` để ngỏ ("Nhánh đọc bảng phân bổ Location Allocation thuộc GĐ 2").

---

## 2. Phạm vi

**Làm:**

- Danh mục gán **một mặt hàng ↔ một nút vị trí** (nút ở bất kỳ cấp nào: Khu / Dãy /
  Khoang / Tầng / Ô). Gán một nút nhóm nghĩa là **cả nhánh dưới nó** thuộc về mặt hàng đó.
- Ràng buộc **một ô một chủ**: nút đã thuộc mặt hàng A thì mặt hàng B không gán được vào
  chính nút đó, vào con cháu của nó, hay vào tổ tiên của nó.
- **Cây chọn vị trí** trực quan: nút đã có chủ hiện mờ kèm tên chủ, không bấm chọn được.
- Hàm **gợi ý ô** và chỗ nhìn thấy nó: cột "Ô đích" của phiếu xếp vị trí được điền sẵn.
- Một **báo cáo** soi hàng đang nằm sai so với gán.

**Không làm** (nêu ra để khỏi tranh cãi sau):

- **Không đụng `Purchase Receipt`** hay bất kỳ chứng từ kho nào. Quyết định 14/09 "xếp
  sau, bằng phiếu riêng" vẫn đứng.
- **Không làm bảng `Location Allocation` (§5.4).** Nó phục vụ việc khai vị trí ngay trên
  chứng từ — chưa cần, và sẽ là hai nguồn sự thật nếu làm song song với phiếu xếp.
- **Không dùng sức chứa.** `suc_chua` vẫn = 0 trên cả 214 ô; không trường nào trong spec
  này đọc nó. Cố ý **bỏ** `so_luong_toi_da` và `la_o_chinh` mà §5.5 phác — trường trông có
  thẩm quyền mà không ai điền là cái bẫy repo này đã dính nhiều lần.
- **Không làm nhãn.** Khối C.

---

## 3. Quyết định của chủ đầu tư (15/09/2026)

Bốn câu hỏi đã chốt, ghi lại để không mở lại:

1. **Một mặt hàng gán ĐÚNG MỘT nút.** Không phải nhiều nút có một nơi chính như §5.5 phác.
2. **Luật gợi ý: "ô trống đầu tiên theo thứ tự cây"** — duyệt Khu→Dãy→Khoang→Tầng→Ô, lấy ô
   trống đầu tiên. Không phải "dồn sát ô đang có hàng", không phải "đổ đầy ô cũ trước".
3. **Chặn cả hai chiều:** không gán được nếu nhánh đó đã có gán khác, **và cũng không gán
   được nếu trong nhánh đang có tồn của mặt hàng khác.**
4. **Hết ô trống thì dồn vào ô đang chứa chính mặt hàng đó** (phương án (b)), chỉ khi
   không có cả hai mới báo đầy. Lý do chọn (b) thay vì báo đầy ngay: nếu gán một mặt hàng
   vào **một Ô lẻ**, luật thuần "ô trống đầu tiên" khiến lần nhập **thứ hai trở đi luôn báo
   đầy** — dù hàng trong ô chính là hàng của nó và kệ còn thừa chỗ. (b) xử đúng ca đó mà
   vẫn không cần biết sức chứa.

---

## 4. Mô hình dữ liệu

### 4.1 DocType `Item Location Preference`

`erpnext/warehouse_operations/doctype/item_location_preference/`

| Trường | Kiểu | Bắt buộc | Ghi chú |
|---|---|---|---|
| `vat_tu` | Link `Item` | ✓ | |
| `kho` | Link `Warehouse` | ✓ | phải đang bật quản lý vị trí |
| `vi_tri` | Link `Storage Location` | ✓ | nút bất kỳ cấp nào |
| `cap_do` | Data, read-only | | "Khu"/"Dãy"/"Khoang"/"Tầng"/"Ô", suy từ `ma_vi_tri.cap_do()` |
| `ghi_chu` | Small Text | | |

**`autoname: field:vat_tu`.** Đây là quyết định thiết kế chính, không phải chi tiết vặt:
nó biến bất biến *"một mặt hàng một nút"* thành **khoá chính của bảng**. Một phép kiểm
trong `validate()` thì `frappe.db.set_value`, Data Import, và đường REST đi vòng được;
khoá chính thì không.

Cái giá phải trả nằm ở §4.2 và nó KHÔNG tự lo được.

`cap_do` là trường **để nhìn**, không phải nguồn sự thật — nó tính lại từ `vi_tri` mỗi lần
lưu. Không được có bất kỳ truy vấn nào lọc theo nó.

### 4.2 Đổi mã mặt hàng — phải xử tường minh

`autoname: field:vat_tu` kéo theo một bẫy đã đo được trong chính frappe v15
(`frappe/model/base_document.py:1027`) — `_sync_autoname_field()`:

```
if fieldname and self.name and self.name != self.get(fieldname):
    self.set(fieldname, self.name)      # name THẮNG, luôn luôn
```

Khi đổi mã một mặt hàng, `rename_doc` cập nhật **giá trị** `vat_tu` của bản ghi gán sang mã
mới bằng SQL (không qua `save`), nhưng **`name` của bản ghi vẫn là mã cũ**. Lần kế tiếp có
ai lưu bản ghi đó — kể cả chỉ sửa ghi chú — `_sync_autoname_field()` chạy TRƯỚC `validate()`
và **âm thầm kéo `vat_tu` ngược về mã cũ**. Không có lỗi nào báo; gán trỏ về một mặt hàng
không còn tồn tại, và gợi ý cho mặt hàng mới lặng lẽ biến mất.

Đây đúng là hình dạng bẫy mà `storage_location.py::kiem_tra_ma_o_khong_doi` đã phải chặn
tường minh cho `ma_o`. Xử: móc `Item.on_rename` (qua `doc_events` trong `hooks.py`) gọi
`frappe.rename_doc("Item Location Preference", ma_cu, ma_moi)` để `name` đi theo. Phải có
bài test khoá: đổi mã mặt hàng → lưu lại bản ghi gán → `vat_tu` vẫn là mã MỚI.

> **Dòng thêm vào `hooks.py` là dòng dễ mất nhất.** Tài liệu bàn giao của module đã gọi tên
> vấn đề này cho móc `Stock Ledger Entry.on_submit`: mỗi lần merge ERPNext bản mới là một
> cơ hội mất nó. `tests/test_app_khoi_dong.py` đang khoá móc SLE theo cách đó; móc mới này
> phải được khoá cùng kiểu, trong cùng file.

### 4.3 Hệ quả: một mặt hàng chỉ gán được ở MỘT kho

Vì `name` là mã mặt hàng, bảng chỉ chứa **một** dòng cho mỗi mặt hàng — nên trường `kho`
không tạo ra được hai gán ở hai kho khác nhau cho cùng một món.

Hôm nay điều đó vô hại: chỉ `Kho Miyano - MYN` đang bật quản lý vị trí. Nhưng nó sẽ cắn
đúng ngày kho thứ hai được bật, và cách gỡ khi đó **không phải** sửa một dòng: phải đổi
`autoname` sang `format:{vat_tu}-{kho}` kèm patch đổi tên toàn bộ bản ghi cũ. Ghi ra đây để
ngày đó không ai tưởng là lỗi.

### 4.4 Không có bảng nào khác

Không child table, không doctype phụ. Gán là quan hệ 1–1 giữa mặt hàng và một nút; mọi câu
hỏi khác ("nhánh này gồm những ô nào", "ô này còn trống không") trả lời được từ
`Storage Location.lft/rgt` và `Location Balance` đã có.

---

## 5. Bốn phép kiểm khi lưu

Thứ tự là cố ý: rẻ trước, và phép kiểm sau dựa vào tiền đề của phép kiểm trước.

### 5.1 Nút phải nằm trong cây

`Storage Location.lft` và `.rgt` đều khác 0, nếu không thì **ném lỗi tường minh**.

Đây là **bẫy đã trả giá hai lần** trong chính module này (`vitri/fefo.py` với `pham_vi`,
`vitri/tem.py` với `goc`). Bản ghi chưa hội tụ mang `lft = rgt = 0`; mọi mệnh đề dạng
`between`/giao nhau bên dưới sẽ thành `0 … 0` và **khớp MỌI bản ghi 0/0 khác trên toàn hệ**
— tức một gán tưởng là của Tầng `1B0104` lại chặn (hoặc bị chặn bởi) những nút hoàn toàn
không liên quan, có thể của kho khác.

Chặn ở nguồn, **không** vá bằng vị từ chặt hơn: ở đây so **chính toạ độ của `vi_tri`**, mà
toạ độ đó mới là thứ hỏng. Thông báo phải nêu cách sửa (lưu lại vị trí đó, hoặc chạy
`bench migrate` để `cay.dam_bao_cay_da_dung()` dựng lại toạ độ).

### 5.2 Nút phải hợp lệ về mặt kho

- `Storage Location.kho == self.kho`.
- `kho_co_quan_ly_vi_tri(self.kho)` phải đúng (`vitri/kho.py:34`, đọc
  `Warehouse.custom_quan_ly_vi_tri`).
- **Không cho gán vào ô `la_o_chua_xep`.** `ZZZ-CHUA-XEP` là ô ảo, không có kệ thật; gán
  mặt hàng vào đó là bịa ra một địa chỉ vật lý không tồn tại, và sẽ khiến gợi ý trỏ về
  đúng chỗ mà phiếu xếp đang cố đưa hàng RA.
- **Không cho gán vào nút đang `disabled`, hoặc có tổ tiên `disabled`.** Gán vào một dãy
  đang tắt để sửa kệ thì gợi ý trỏ vào chỗ không ai được đụng tới.

### 5.3 Không chồng lấn với gán khác

Điều kiện đúng là hai nhánh **GIAO NHAU**, không phải bằng nhau:

```sql
exists (
  select 1
  from `tabItem Location Preference` p
  join `tabStorage Location` s on s.name = p.vi_tri
  where p.name != %(ten)s
    and s.lft <= %(rgt)s
    and s.rgt >= %(lft)s
)
```

Một vị từ bắt cả **ba** ca, và đó là lý do phải viết dạng giao nhau chứ không phải
`s.name = vi_tri`:

| Ca | Ví dụ | Vì sao phải chặn |
|---|---|---|
| Trùng đúng nút | A giữ `1B0104`, B gán `1B0104` | hiển nhiên |
| Gán vào **con cháu** | A giữ Tầng `1B0104`, B gán Ô `1B010402` | ô đó đã thuộc A |
| Gán vào **tổ tiên** | A giữ Ô `1B010402`, B gán Khoang `1B01` | nuốt luôn ô của A |

Anh em ruột (`1B010401` và `1B010402`) **không** giao nhau → cho qua, đúng ý.

Thông báo lỗi phải nêu: nút nào đang vướng, mặt hàng nào đang giữ, và quan hệ (trùng / nằm
trong / bao trùm) — "không hợp lệ" trần thì người dùng không biết đi sửa ở đâu.

### 5.4 Trong nhánh không được có tồn của mặt hàng khác

Quyết định §3.3 của chủ đầu tư. Truy vấn `Location Balance` join `Storage Location` trong
nhánh `[lft, rgt]`, `so_luong != 0`, `vat_tu != self.vat_tu`.

Thông báo nêu **ô nào · mặt hàng nào · bao nhiêu** (tối đa vài dòng đầu rồi "… và N ô
nữa"), vì việc cần làm tiếp theo là đi dọn đúng những ô đó bằng phiếu chuyển vị trí.

> **Rủi ro đã biết, chấp nhận có ý thức.** Hôm nay 100% tồn nằm ở `ZZZ-CHUA-XEP` (103
> dòng, 24.026 đơn vị; 128 ô thật trống trơn — đo 13/09). Nên phép kiểm này **hôm nay gần
> như không bao giờ chặn ai**. Nó chỉ bắt đầu cắn khi phiếu xếp đã chạy được một thời gian
> và hàng đã vào ô thật. Đó là lúc người ta đã quen gán tự do — nên thông báo phải dạy
> được cách gỡ, không chỉ từ chối.

---

## 6. Cây chọn vị trí

Dialog chứa `frappe.ui.Tree`. Có tiền lệ ngay trong repo:
`erpnext/accounts/doctype/chart_of_accounts_importer/chart_of_accounts_importer.js:189`.

Server method `cay_chon_vi_tri(kho, parent)` trả các nút con kèm ba thông tin **mà cây phải
hiển thị trước khi người dùng bấm**:

| Cờ | Ý nghĩa | Thể hiện |
|---|---|---|
| `da_gan_cho` | mặt hàng đang giữ nút này (hoặc giữ một tổ tiên của nó) | chữ mờ + tên mặt hàng, không bấm được |
| `co_hang_khac` | trong nhánh đang có tồn của mặt hàng khác | biểu tượng cảnh báo + số ô |
| `so_o_trong` | số ô lá còn trống trong nhánh | chữ nhỏ bên phải |

**"Không khả dụng" phải nhìn thấy TRƯỚC khi bấm.** Cho bấm rồi mới ném lỗi là bắt người
dùng dò từng nút để tìm ra chỗ còn trống — với 214 ô thì đó không phải giao diện, đó là
trò chơi đoán.

Nút gốc của cây là các Khu của `kho` đang chọn. Ô `ZZZ-CHUA-XEP` **không xuất hiện** trong
cây này (nó đứng ngoài cây, và §5.2 đã cấm gán vào nó).

---

## 7. Gợi ý ô — `vitri/goi_y.py`

```
goi_y_o(vat_tu, kho) -> (o | None, ly_do)

1. không có bản ghi gán       → (None, "mặt hàng chưa gán vị trí cố định")
2. nút gán lft/rgt = 0        → throw  (§5.1, chặn ở nguồn)
3. ứng viên = ô LÁ trong [lft, rgt]
     - bỏ is_group
     - bỏ la_o_chua_xep
     - bỏ nhánh disabled  → DÙNG LẠI `fefo._TO_TIEN_TAT` (fefo.py:104)
     sắp theo lft tăng dần
4. ô đầu tiên có tổng tồn = 0 → (ô, "ô trống đầu tiên")
5. hết ô trống                → ô lft nhỏ nhất TRONG NHÁNH đang chứa CHÍNH `vat_tu`
                              → (ô, "dồn vào ô đang có hàng")          ← §3.4 (b)
6. không có cả hai            → (None, "vùng <nút> đã đầy: N/N ô đang chứa hàng khác")
```

**Bước 3 dùng lại `_TO_TIEN_TAT` chứ không chép lại.** Vị từ đó mã hoá luật "ô bị coi là
tắt nếu chính nó hoặc bất kỳ tổ tiên nào của nó `disabled`". Chép ra chỗ thứ hai nghĩa là
một ngày nào đó sửa một chỗ quên chỗ kia, và khi đó gợi ý sẽ trỏ vào một dãy đang tắt
trong khi `fefo` từ chối lấy hàng từ đó — hai nửa của hệ nói ngược nhau.

"Tổng tồn = 0" ở bước 4 tính bằng tổng `Location Balance.so_luong` của ô, **không** phải
"không có dòng nào": một ô đã từng có hàng rồi hết vẫn còn dòng `so_luong = 0`.

Hàm trả **cặp (ô, lý do)**, không chỉ trả ô. Lý do được hiển thị cạnh gợi ý — thủ kho cần
phân biệt "ô này trống" với "ô này đã có hàng cùng loại, dồn vào" trước khi mở kệ.

---

## 8. Chỗ nhìn thấy kết quả

`vitri/xep.py::hang_chua_xep(kho)` hiện trả mỗi dòng với `den_o` để trống **có chủ ý**, và
docstring ghi rõ lý do. Sửa: điền `den_o` và thêm `ly_do_goi_y` từ `goi_y_o()`.

**Phải sửa luôn docstring đó.** Nó đang nói "không có căn cứ nào để gợi ý" — để nguyên thì
người đọc sau sẽ tin là hệ vẫn không gợi ý, trong khi nó đã gợi ý rồi.

Gợi ý **không** ghi đè giá trị thủ kho đã tự chọn, và **không** chặn việc chọn khác. Đây là
gợi ý, không phải luật; thủ kho đứng trước kệ biết những thứ hệ không biết.

Đây là mặt duy nhất của khối B mà chủ đầu tư kiểm được bằng mắt trước khi có khối C.

---

## 9. Báo cáo `hang_nam_sai_vi_tri`

`erpnext/warehouse_operations/report/hang_nam_sai_vi_tri/`

Cột: `o` · `ma_in_nhan` · `vat_tu_dang_co` · `so_lo` · `so_luong` · `vat_tu_da_gan` ·
`nut_gan`.

Nội dung: mọi dòng `Location Balance` (`so_luong != 0`) nằm trong nhánh của một gán, mà
`vat_tu` của nó khác mặt hàng được gán cho nhánh đó.

**Vì sao báo cáo này bắt buộc đi kèm, không phải tuỳ chọn.** §5.4 chỉ chặn **lúc gán**.
Sau khi đã gán, hàng vẫn vào sai ô được — qua phiếu xếp khai tay, qua đường huỷ chứng từ
(`hook_sle.dao_theo_o_goc`), qua kiểm kê. Một bất biến chỉ được kiểm ở một thời điểm rồi
không ai soi lại là bất biến sẽ mục trong im lặng: đối soát §3 (`doi_soat.py`) vẫn khớp
tuyệt đối, vì nó chỉ so **tổng**, không phân biệt ô nào chứa gì.

Báo cáo rỗng = trạng thái đúng.

---

## 10. Kiểm thử

`erpnext/warehouse_operations/tests/test_gan_vi_tri.py` và `test_goi_y_o.py`.

**Ma trận chồng lấn (§5.3)** — phải có cả chốt âm, vì một đột biến đổi vị từ giao nhau
thành `s.name = vi_tri` vẫn làm ca "trùng đúng nút" xanh:

| Ca | Kỳ vọng |
|---|---|
| B gán đúng nút A đang giữ | chặn |
| B gán con cháu của nút A | chặn |
| B gán tổ tiên của nút A | chặn |
| B gán nút **anh em** | **cho qua** ← chốt âm |
| B gán nhánh ở Khu khác hẳn | **cho qua** ← chốt âm |
| A sửa chính bản ghi của mình | **cho qua** (loại trừ `p.name != self.name`) |

**Bẫy toạ độ rỗng (§5.1)**: đặt `lft = rgt = 0` cho nút định gán → phải `throw`. Kèm chốt
âm: một đột biến bỏ hẳn phép kiểm phải làm bài khác đỏ, chứ không được lặng lẽ trả về một
gán "thành công" đã chặn nhầm nửa hệ thống.

**Gợi ý (§7)**:

- nhánh nhiều ô, ô đầu có hàng → trả ô thứ hai (khoá đúng thứ tự `lft`, không phải thứ tự
  chữ cái — hai thứ này trùng nhau ở dữ liệu mẫu, nên ca thử phải dựng dữ liệu mà chúng
  **khác** nhau, nếu không bài test không chứng minh gì)
- **ô lẻ đã có hàng của chính nó → dồn vào ô đó** (§3.4 (b))
- mọi ô đều có hàng của mặt hàng KHÁC → `(None, "đã đầy")`
- nhánh có dãy `disabled` → ô trong dãy đó không bao giờ được gợi ý
- mặt hàng chưa gán → `(None, ...)`, **không** throw
- `ZZZ-CHUA-XEP` không bao giờ là kết quả gợi ý

**Phiếu xếp (§8)**: `hang_chua_xep` trả `den_o` đã điền cho mặt hàng đã gán, và **để
trống** cho mặt hàng chưa gán — trong cùng một lời gọi.

Chạy: `bench --site erptest.local run-tests --module erpnext.warehouse_operations.tests.<tên>`,
**tuần tự**, rồi cả bộ `vi_tri_kho` trước khi đóng. Không dùng `--app erpnext`.

---

## 11. Rủi ro

| Rủi ro | Xử lý |
|---|---|
| Gán vào **Ô lẻ** làm gợi ý sớm báo đầy | §3.4 (b) xử; thêm cảnh báo mềm trên form khi `cap_do == "Ô"`, gợi ý gán từ cấp Tầng trở lên |
| Toạ độ cây rỗng (`lft=rgt=0`) | §5.1, chặn ở nguồn, có test + chốt âm |
| Hàng vào sai ô sau khi đã gán | §9 báo cáo; đối soát §3 **không** bắt được vì nó chỉ so tổng |
| Đổi ý sang "nhiều nút mỗi mặt hàng", hoặc bật kho thứ hai | `autoname: field:vat_tu` phải bỏ/đổi — thay đổi lược đồ có patch, không phải sửa một dòng. §4.3 |
| Mã mặt hàng bị đổi | Frappe **không** tự kéo `name` theo — `_sync_autoname_field()` âm thầm revert. §4.2: móc `Item.on_rename`, có test khoá |
| Cây 214 nút vẽ chậm | `frappe.ui.Tree` nạp theo từng cấp (`expandable`), không nạp cả cây |

---

## 12. Việc để lại cho khối C

Hai câu chưa trả lời, sẽ chốt trong spec của nhãn nhập kho:

1. **Nhà cung cấp.** Chủ đầu tư yêu cầu nhãn có NCC, nhưng bảng F1–F11 và ảnh mockup
   (`docs/warehouse_operations/Screenshot 2026-09-15 142544.png`) **không có ô nào cho NCC** — 11 ô
   đã kín vùng in an toàn 47×27mm. `Batch.supplier` có sẵn dữ liệu; chỗ đặt thì chưa có.
2. **Mã vạch F10 mã hoá gì.** Mockup in `026090374561` (12 chữ số) trong khi F9 "số gọi" là
   `3856` — hai số khác nhau, chưa rõ quan hệ.

Một điều đã xác định được và cần ghi lại: **bảng chữ F1–F11 mà chủ đầu tư dán có F8 =
`VT K11B0104-0302`, tức mã 12 ký tự đã bỏ ngày 11/09.** Ảnh mockup thì đúng —
`VT 3B1205-0401`, khớp chính xác `ma_vi_tri.dinh_dang_nhan()` hiện hành. **Ảnh thắng.**
`test_ma_vi_tri.py:65` chỉ khoá độ dài ≤ 16 nên cả hai dạng đều lọt — không có bài test nào
bắt được nếu code theo bảng chữ.

---

## 13. Không thuộc spec này

`Location Allocation` (§5.4 spec gốc) · custom field trên `Purchase Receipt` hay bất kỳ
chứng từ kho nào · sức chứa ô · nhiều nút cho một mặt hàng · nhãn nhập kho · quét mã vạch.

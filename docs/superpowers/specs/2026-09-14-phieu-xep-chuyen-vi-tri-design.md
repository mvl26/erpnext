# Phiếu xếp / chuyển vị trí — thiết kế

Nhánh `feat/mo-rong-vi-tri-kho-warehouse`, module `erpnext/vi_tri_kho/`.
Chốt ngày 14/09/2026 sau brainstorm với chủ đầu tư.

---

## 1. Vì sao cần

Hôm nay mọi hàng nhập về đều rơi vào ô hệ thống `ZZZ-CHUA-XEP` và **ở lại đó vĩnh viễn**:
không có màn hình, không có API, không có phiếu nào đưa hàng từ đó vào ô thật. Đo trên
`erptest.local` ngày 13/09/2026: 103 dòng tồn, 24.026 đơn vị, **100% nằm ở `ZZZ-CHUA-XEP`;
128 ô thật trống hoàn toàn**.

Hệ quả dây chuyền — ba tính năng đã làm xong đang nằm im vì thiếu đúng mắt xích này:

| Đã có | Vì sao chưa dùng được |
|---|---|
| Chọn ô xuất theo hạn dùng (`fefo.py`) | chỉ có **một** ô để chọn |
| Tồn gộp theo Khu/Dãy (`ton_kho_theo_vi_tri`) | `ZZZ` đứng ngoài cây nên **mọi dòng nhóm đều rỗng** |
| Tem mã vạch 50×30mm (việc B) | dán lên kệ rồi **không có chỗ nào để quét** |

---

## 2. Phạm vi

**Làm:** một chứng từ duyệt được, chuyển hàng giữa hai ô **trong cùng một kho** — gồm cả
xếp hàng nhập về (`ZZZ` → ô thật) lẫn dồn/đổi kệ (ô thật → ô thật).

**Không làm** (nêu ra để khỏi tranh cãi sau):

- **Không chuyển sang kho khác.** Đổi kho là đổi tồn kho thật; đó là việc của phiếu chuyển
  kho ERPNext. Xem §4.
- **Không khai vị trí ngay trên phiếu nhập.** Chủ đầu tư đã chốt "xếp sau, bằng phiếu riêng".
- **Không quét mã vạch để điền ô đích.** Đã cân, đã loại ở vòng brainstorm — cần máy quét
  thật để thử, để lại giai đoạn sau.
- **Không tự gợi ý ô đích.** Chưa có dữ liệu sức chứa (`suc_chua` hiện = 0 trên cả 214 ô).

---

## 3. Bất biến phải giữ

Bất biến §3 của spec cây vị trí: **với mọi (mặt hàng, lô, kho có quản lý vị trí), tổng tồn các
ô = `Bin.actual_qty`.**

Phiếu này giữ bất biến đó **bằng cấu trúc, không bằng cố gắng**: mỗi dòng ghi `−n` ở ô nguồn và
`+n` ở ô đích, hai ô cùng một kho, nên tổng của kho **không đổi**. Không có đường nào để phiếu
làm lệch tổng — kể cả khi logic bên trong sai.

Đây là lý do ràng buộc "cùng kho" ở §4 không phải một quy tắc nghiệp vụ tuỳ chọn mà là **điều
kiện để bất biến tự giữ**. Bỏ nó ra là phải tự giữ bất biến bằng tay, và bài học `LandedCostVoucher`
trong `frappe-v15-gotchas` cho thấy loại lệch đó **đối soát theo tổng không bắt được**.

---

## 4. Không sinh Stock Ledger Entry

Phiếu **không tạo SLE**, không gọi bất cứ hàm nào của `erpnext/stock/`.

Lý do: chuyển giữa hai ô trong cùng kho không làm đổi tồn kho ERPNext ở bất kỳ mức nào
(`Bin.actual_qty` theo kho, không theo ô). Sinh SLE sẽ:

- ghi hai dòng sổ kho triệt tiêu nhau — rác thuần tuý trong sổ cái kho;
- **kích lại hook `Stock Ledger Entry.on_submit`**, tức `ghi_so_vi_tri` chạy và dồn hàng vào
  `ZZZ-CHUA-XEP` một lần nữa — đúng thứ phiếu này vừa gỡ ra. Vòng lặp ngược.

Bài test khoá điều này bằng **chốt âm**: đếm SLE trước và sau khi duyệt phiếu, phải bằng nhau.

---

## 5. Mô hình dữ liệu

### 5.1 `Location Transfer` (đầu phiếu, submittable)

Đây là doctype **submittable đầu tiên** của module — bốn doctype hiện có đều không duyệt.

| Trường | Kiểu | Ghi chú |
|---|---|---|
| `naming_series` | Select | `XVT-.YYYY.-` |
| `kho` | Link Warehouse | bắt buộc; phải đang bật quản lý vị trí |
| `ngay` | Date | mặc định hôm nay |
| `ghi_chu` | Small Text | |
| `items` | Table | `Location Transfer Item` |

`autoname: naming_series` — khác bốn doctype hiện có (`hash`, `field:`, `Prompt`), vì đây là
chứng từ người dùng đọc và nhắc tới bằng số.

### 5.2 `Location Transfer Item` (dòng, istable)

| Trường | Kiểu | Ghi chú |
|---|---|---|
| `vat_tu` | Link Item | bắt buộc |
| `so_lo` | Link Batch | để trống nếu mặt hàng không quản lý lô |
| `tu_o` | Link Storage Location | bắt buộc |
| `den_o` | Link Storage Location | bắt buộc |
| `so_luong` | Float | bắt buộc, **> 0** |

Không có trường "tồn hiện có ở ô nguồn": số đó **thay đổi giữa lúc mở phiếu và lúc duyệt**, lưu
lại chỉ tạo ảo giác an toàn. Kiểm tra thật nằm ở §7, chạy lúc duyệt.

---

## 6. Phép kiểm lúc duyệt

Chạy trong `before_submit`, **không** phải `on_submit` — `Document.save()` ghi dòng trước khi
chạy `on_submit`, nên một `throw` ở đó để lại trạng thái hỏng đã ghi (xem `frappe-v15-gotchas`,
mục "Hook timing").

| # | Phép kiểm | Vì sao |
|---|---|---|
| K1 | `kho` đang bật quản lý vị trí | không bật thì không có sổ vị trí để ghi |
| K2 | Mọi `tu_o`, `den_o` thuộc đúng `kho` của phiếu | điều kiện để bất biến §3 tự giữ |
| K3 | `den_o` không phải nút nhóm | nút nhóm không chứa hàng (`ghi_dong_so` cũng chặn, nhưng báo sớm hơn thì sửa dễ hơn) |
| K4 | `den_o` **không** đang Ngừng dùng, và **không** nằm dưới nhánh đã tắt | xem §6.1 |
| K5 | `tu_o` **được phép** đang Ngừng dùng | xem §6.1 — đây là chốt âm, không phải thiếu sót |
| K6 | `tu_o != den_o` | dòng vô nghĩa, gần như luôn là gõ nhầm |
| K7 | `so_luong > 0` | số âm là phiếu ngược trá hình, phải lập phiếu riêng cho rõ |
| K8 | Phiếu có ít nhất một dòng | |
| K9 | Mặt hàng có quản lý lô ⇒ `so_lo` bắt buộc; không quản lý lô ⇒ `so_lo` phải trống | xem §6.2 |
| K10 | `so_lo` (nếu có) phải đúng là lô **của** `vat_tu` | |

### 6.1 Vì sao hai chiều `disabled` ngược nhau

`QUYET-DINH-thi-cong-cay-vi-tri.md` mục "Một bất đối xứng còn tồn tại" đã ghi: `fefo.py` là nơi
**duy nhất** lọc `disabled`; đường **nhập** không lọc gì. Nên hàng vẫn chảy **vào** một dãy đã
tắt trong khi không ô nào trong dãy đó xuất **ra** được — và đối soát vẫn xanh vì nó chỉ so tổng.

Tài liệu đó viết tiếp: *"Nó trở thành vấn đề thật khi có màn hình khai vị trí lúc nhập."* Phiếu
này **chính là** màn hình đó. Nên K4 vá đúng chỗ ấy.

K5 là chiều ngược lại và cũng cố ý: **ô nguồn đang tắt thì phải cho lấy ra**. Đó là đường duy
nhất gỡ hàng khỏi một dãy đang tháo kệ. Cấm cả hai chiều thì hàng kẹt vĩnh viễn — vừa đúng cái
`fefo.py` đã chặn ở đường xuất.

Phép kiểm "nằm dưới nhánh đã tắt" dùng **cùng một vị từ tổ tiên** với `fefo.py::_TO_TIEN_TAT`
(so `lft`/`rgt` bằng phép chứa **chặt**, cộng với khớp chính nó bằng tên). Không viết lại bằng
tiền tố mã — bẫy F8 đã trả giá một lần.

### 6.2 Lô: phải khớp cả hai chiều

K9 chặn **cả hai** chiều sai, không chỉ chiều thiếu. Để trống `so_lo` cho một mặt hàng có quản
lý lô sẽ ghi một dòng sổ mang `so_lo = ''` — dòng đó **không bao giờ khớp** với dòng tồn thật
của lô, nên nó vừa làm lô nguồn không giảm, vừa đẻ một dòng tồn ma ở ô đích. Chiều ngược lại
(điền lô cho hàng không quản lý lô) tách tồn của ô thành hai dòng mà `fefo.py` chỉ nhìn thấy
một. Cả hai đều **không làm lệch tổng**, nên đối soát vẫn xanh.

---

## 7. Ghi sổ, và chặn tồn âm

### 7.1 Hai bút toán mỗi dòng

`on_submit` gọi `so.ghi_dong_so()` **hai lần cho mỗi dòng**: `−so_luong` ở `tu_o`, `+so_luong`
ở `den_o`. Cả hai mang `chung_tu_type = "Location Transfer"`, `chung_tu = name`,
`chung_tu_row = <tên dòng con>`, `sle = None`.

Không gộp thành một dòng sổ mang cả Từ/Đến: `dung_lai_ton_vi_tri()` gom theo `o`
(`group by o, kho, vat_tu, so_lo`), một dòng hai ô sẽ làm nó dựng sai bộ đệm.

### 7.2 Chặn tồn âm — GHI TRƯỚC, ĐỌC LẠI SAU

`ghi_dong_so` **không tự chặn âm**. Ô âm là hỏng nặng: `doi_soat` báo `o_am`, và "Đồng bộ lại"
**cố ý ném lỗi** thay vì chữa.

Kiểm trước rồi ghi là **không đủ**. Hai thủ kho cùng xếp một lô ra khỏi `ZZZ`: cả hai đọc thấy
"còn 60", cả hai ghi `−40`, ra `−20`. Đúng ngữ nghĩa transaction — mỗi bên chỉ thấy dữ liệu đã
commit của bên kia.

Cách làm: **ghi hết các bút toán trước, rồi đọc lại tồn của mọi (ô, mặt hàng, lô) mà lần ghi này
có chạm tới, trong cùng giao dịch**; chỗ nào âm thì `frappe.throw` → cả phiếu rollback, không
dòng sổ nào sống sót.

Phải đọc lại **sau khi ghi xong toàn bộ phiếu**, không phải sau từng dòng. Một phiếu hợp lệ có
thể có dòng 1 lấy 10 từ ô A và dòng 2 trả 10 về ô A; kiểm sau từng dòng sẽ từ chối oan một phiếu
đúng. Kiểm cuối cùng nhìn **kết quả ròng**, là thứ duy nhất có ý nghĩa.

Cùng phép kiểm đó dùng lại cho `on_cancel` (§7.3) — ở đó ô bị giảm là ô **đích**, không phải ô
nguồn. Nên phép kiểm phát biểu theo "mọi chỗ lần ghi này chạm tới", không theo vai trò nguồn/đích.

An toàn được là nhờ `_cong_don_ton` dùng `INSERT … ON DUPLICATE KEY UPDATE`: MariaDB khoá dòng
chỉ mục ở tầng InnoDB cho statement đó, nên người ghi sau **phải chờ** và đọc được kết quả của
người ghi trước. Đây là lý do phép kiểm đặt **sau** khi ghi chứ không phải trước — đặt trước thì
không có khoá nào để dựa vào.

Thông báo lỗi phải nêu **đích danh ô, mặt hàng, lô, tồn thực tế và số đang đòi** — không phải
câu "không đủ hàng" chung chung.

### 7.3 Huỷ phiếu

`on_cancel` ghi **hai bút toán đảo** cho mỗi dòng (`+` ở `tu_o`, `−` ở `den_o`), cờ `da_huy = 1`.
Không sửa, không xoá dòng cũ — sổ là append-only, `dung_lai_ton_vi_tri()` dựng lại đúng.

Huỷ cũng phải qua phép kiểm âm ở §7.2: hàng đã xếp vào ô đích có thể đã bị xuất đi mất, lúc đó
huỷ sẽ đẩy ô đích xuống âm. Ca này phải bị chặn, kèm thông báo nói rõ vì sao không huỷ được.

---

## 8. Nút "Lấy hàng chưa xếp"

Một hàm whitelist trả mọi dòng `Location Balance` có `so_luong != 0` ở ô `la_o_chua_xep = 1` của
kho đang chọn — cùng nguồn với báo cáo *Hàng chưa xếp vị trí* để hai chỗ không nói khác nhau.

Nút điền các dòng với `tu_o` = ô `ZZZ` của kho, `den_o` **để trống** (người dùng phải tự điền —
không có gợi ý nào đủ căn cứ, xem §2).

Kiểm quyền tường minh như mọi hàm whitelist khác của module.

---

## 9. Phân quyền

| Vai trò | Đọc | Tạo | Duyệt | Huỷ |
|---|---|---|---|---|
| `System Manager` | ✓ | ✓ | ✓ | ✓ |
| `Stock Manager` | ✓ | ✓ | ✓ | ✓ |
| `Stock User` | ✓ | ✓ | ✓ | ✓ |

Thủ kho có đủ quyền: xếp hàng là **việc hằng ngày**, và phiếu không đổi tồn kho nên không có
đường làm lệch số liệu công ty. Khác hẳn `bat_kho.py` (sinh ô, bật kho) vốn chỉ mở cho quản lý.

**Không** `Customer`, **không** `Website User` ở bất kỳ tầng nào — DocPerm, hook, hay hàm
whitelist. Bài test quét động theo module đã có sẵn sẽ tự phủ doctype mới này.

---

## 10. Kiểm thử bắt buộc

Mỗi bài dưới đây phải **đỏ khi đột biến** phép chặn tương ứng.

| # | Bài | Chốt âm đi kèm |
|---|---|---|
| T1 | Xếp `ZZZ` → ô thật: tồn hai ô đổi đúng | tổng tồn của kho **không đổi** |
| T2 | Chuyển ô thật → ô thật | tổng không đổi |
| T3 | Rút quá tồn ô nguồn bị từ chối | **không dòng sổ nào được ghi**, tồn ô nguồn nguyên vẹn |
| T4 | Ô khác kho bị từ chối | |
| T5 | Ô đích là nút nhóm bị từ chối | |
| T6 | Ô đích đang tắt (hoặc dưới nhánh tắt) bị từ chối | **T6b: ô nguồn đang tắt vẫn CHO** |
| T7 | Huỷ phiếu đảo đúng hai chiều | tồn về đúng như trước khi duyệt |
| T8 | Huỷ khi ô đích đã bị xuất hết bị từ chối | |
| T9 | Bất biến §3 đúng trước duyệt, sau duyệt, sau huỷ | |
| T10 | **Không SLE nào được sinh** | đếm trước/sau bằng nhau |
| T11 | Hai phiếu cùng rút một lô không làm âm | |
| T12 | `Website User` bị chặn ở hàm whitelist | |
| T13 | Hàng có lô mà bỏ trống `so_lo` bị từ chối (K9) | **T13b: hàng không lô mà điền lô cũng bị từ chối** |
| T14 | Phiếu lấy 10 từ ô A rồi trả 10 về ô A **được duyệt** | đối chứng cho §7.2: kiểm theo ròng, không theo từng dòng |

T3 và T10 là hai bài dễ viết thành vô nghĩa nhất: T3 thiếu chốt âm thì một đột biến làm phạm vi
rộng ra vẫn xanh; T10 mà chỉ đếm SLE *của phiếu này* thì luôn bằng 0 dù hook có chạy hay không.

---

## 11. Cố ý KHÔNG làm

- **Không tự gợi ý ô đích.** `suc_chua` = 0 trên cả 214 ô, không có căn cứ nào để gợi ý.
- **Không đặt trần số dòng một phiếu.** Khác việc in tem (tem hỏng là tốn vật tư thật); phiếu
  nhiều dòng chỉ chậm, và trần đặt bừa sẽ chặn đúng lúc xếp cả một chuyến hàng lớn.
- **Không nhập từ Excel.** Chưa ai xin.
- **Không đụng `Location Ledger Entry`.** Ba trường `chung_tu_type` / `chung_tu` / `chung_tu_row`
  đã sẵn sàng cho đúng việc này.

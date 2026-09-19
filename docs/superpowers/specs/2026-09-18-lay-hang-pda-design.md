# Lấy hàng trên PDA — quét xác nhận, ghi sổ theo đúng ô đã lấy

*Thiết kế — 18/09/2026. Chủ đầu tư duyệt hướng đi cùng ngày.*

## 1. Vì sao có việc này

Hôm nay, ô lấy hàng do `fefo.chon_o_xuat()` chọn **bên trong hook, đúng lúc duyệt phiếu giao**.
Hệ quả:

- Thủ kho **không có danh sách** "đi ô nào, lấy lô nào, bao nhiêu" — phải tự nhớ hoặc tự đoán.
- **Không ai đối chiếu** việc hệ trừ ô A với việc người thật lấy ở ô B. Hai bên lệch nhau thì
  tổng tồn kho vẫn đúng, `doi_soat_kho` vẫn báo khớp, và sai lệch chỉ lộ ra khi kiểm kê thực tế —
  lúc đó đã mất dấu vết.

Yêu cầu chủ đầu tư (18/09): *"em làm phần lấy hàng"* — bản đầy đủ, quét để xác nhận.

Bốn điều chủ đầu tư chốt khi duyệt hướng:

| Câu hỏi | Chốt |
|---|---|
| Mở trang lấy hàng từ đâu | **Từ phiếu giao nháp** (kinh doanh tạo trước) |
| Ai duyệt phiếu giao | **Thủ kho duyệt luôn** khi lấy xong |
| Đến ô mà thiếu hàng | **Cho lấy thiếu**, ghi số thực, sửa số lượng phiếu giao, có cảnh báo |
| Ra kệ thấy lô khác | **Cho đổi lô**, có cảnh báo so hạn dùng |

## 2. Phạm vi

**Làm:**

- `Location Allocation` — bảng phân bổ (child table) gắn vào **Delivery Note**.
- Nhánh **đọc phân bổ** trong hook ghi sổ (nhánh đã dự trù ở spec nền tảng §4.5, chưa ai làm).
- Lớp kiểm sớm trong `validate` của Delivery Note.
- Trang PDA `lay-hang-pda`.
- Bài kiểm server + trình duyệt; chạy lại luồng A→Z.

**Không làm (giai đoạn này):**

- Phân bổ cho `Purchase Receipt` / `Purchase Invoice` / `Sales Invoice` / `Stock Entry` /
  `Stock Reconciliation` / `Subcontracting Receipt`: các chứng từ đó **giữ nguyên** đường cũ
  (nhập → `ZZZ-CHUA-XEP`, xuất → FEFO). Bảng phân bổ thiết kế để dùng lại được, nhưng mở rộng
  là việc sau.
- Giao diện phân bổ trên máy tính (form Delivery Note). Chỉ có đường PDA; ai không dùng PDA thì
  duyệt phiếu giao như hôm nay và hệ vẫn chạy FEFO.
- Đặt trước / giữ chỗ hàng (reservation) cho đơn bán.
- `Location Count` (kiểm kê theo ô) — lệch phát hiện khi lấy hàng chỉ **cảnh báo**, không tự sửa
  sổ. Sửa tồn vẫn phải đi qua `Stock Reconciliation`, đúng như spec nền tảng §5.7.

## 3. Dữ liệu

### 3.1 `Location Allocation` (child table, không submittable riêng)

| Field | Kiểu | Bắt buộc | Ghi chú |
|---|---|---|---|
| `dong_hang` | Data | ✓ | `name` của dòng hàng trên chứng từ cha (khớp `sle.voucher_detail_no`) |
| `vat_tu` | Link Item | ✓ | để đọc và để lọc; phải khớp dòng hàng |
| `so_lo` | Link Batch | | rỗng với hàng không quản lý lô |
| `o` | Link Storage Location | ✓ | ô lá, cùng kho với dòng hàng |
| `so_luong` | Float | ✓ | > 0; đơn vị = đơn vị tồn kho của mặt hàng |
| `nguoi_lay` | Link User | | ai quét dòng này (chỉ để truy vết) |
| `luc_lay` | Datetime | | thời điểm quét |

Gắn vào `Delivery Note` bằng custom field `custom_phan_bo_vi_tri` (Table), tạo bằng patch
`erpnext/vi_tri_kho/patches/v1_0/them_phan_bo_vi_tri.py` (nhớ thêm một dòng vào `erpnext/patches.txt`
— thiếu dòng đó thì patch không chạy và field không có, mà không lỗi nào báo), theo đúng khuôn
`them_so_goi_va_o_in_tem.py`. Field **read-only trên form**: nó là kết quả của việc quét, không
phải chỗ để khai tay — cùng lẽ với `custom_so_goi` / `custom_o_in_tem`.

Vì sao gắn ở **cấp chứng từ cha**, không phải trên dòng hàng: một dòng hàng có thể rải nhiều ô
(lấy 30 ở ô A, 10 ở ô B), và ERPNext không cho child table lồng trong child table.

### 3.2 Không thêm doctype nào khác

Không có "Phiếu lấy hàng" riêng. Trạng thái "đang lấy dở" **sống trên chính phiếu giao nháp**:
các dòng đã quét nằm trong bảng phân bổ, đóng trình duyệt rồi mở lại là thấy lại — cùng cách
trang xếp hàng PDA giữ dòng trên phiếu xếp nháp.

## 4. Ghi sổ

### 4.1 Nhánh mới trong hook

`vitri/hook_sle.py::_ghi_mot_phan()` hôm nay có hai nhánh: nhập → `_tra_lai_o_da_dao` /
`CHUA-XEP`; xuất → `chon_o_xuat` (FEFO). Thêm **một** nhánh, đặt **trước** nhánh FEFO:

```
xuất (so_luong < 0)
 ├─ chứng từ có phân bổ cho ĐÚNG (dong_hang = sle.voucher_detail_no, so_lo)?
 │    ├─ có, tổng phân bổ == |so_luong|  → ghi theo từng dòng phân bổ
 │    └─ có, tổng LỆCH                   → throw, nêu rõ lệch bao nhiêu (§4.3)
 └─ không có                              → FEFO như hôm nay (không đổi)
```

Đối chiếu **theo từng (dòng hàng, lô)**, không theo cả chứng từ: `tach_theo_lo()` đã tách SLE
thành từng phần theo lô trước khi gọi `_ghi_mot_phan`, và spec nền tảng §4.3 nói rõ phân bổ khớp
theo từng lô.

Nhánh nhập **không đọc phân bổ** ở giai đoạn này (không làm giao diện phân bổ cho phiếu nhập),
nhưng `_tra_lai_o_da_dao` đã lường sẵn trường hợp hàng nằm ở ô thật — không phải sửa gì.

### 4.2 Huỷ phiếu giao

Không đụng tới. `dao_theo_o_goc()` tra lại **các dòng sổ vị trí đã ghi** của chính chứng từ đó và
đảo đúng từng ô — nó không quan tâm ô ấy đến từ FEFO hay từ phân bổ. Đây là lý do chọn hướng
"ghi sổ theo phân bổ" thay vì "sửa FEFO": đường huỷ không phải biết gì thêm.

### 4.3 Câu báo khi lệch

> Phiếu giao {tên}: dòng {mã hàng}{, lô X} phân bổ {a} nhưng xuất {b}. Mở lại trang Lấy hàng để
> quét lại, hoặc xoá phân bổ của dòng này để hệ tự chọn ô theo hạn dùng.

Ghi kèm `frappe.log_error` (đây là lỗi hệ thống — giao diện lẽ ra đã chặn từ lớp sớm).

## 5. Kiểm hai lớp

**Lớp sớm — `Delivery Note.validate`** (hook `doc_events`, hàm mới
`vitri/lay_hang.py::kiem_phan_bo_khi_luu`). Chạy khi phiếu còn nháp, người dùng sửa được ngay:

| Kiểm | Câu báo nêu |
|---|---|
| `dong_hang` trỏ đúng một dòng hàng của phiếu | dòng nào lạc |
| `vat_tu` khớp dòng hàng đó | mặt hàng nào lệch |
| `so_lo` khớp lô của dòng hàng (nếu dòng có lô) | lô nào lệch |
| ô tồn tại, **cùng kho** với dòng hàng, **không phải ô nhóm** | ô nào sai |
| tổng phân bổ theo (dòng, lô) **không vượt** số lượng dòng | thừa bao nhiêu |
| ô đủ tồn cho phần phân bổ (đọc `so.ton_o`) | thiếu bao nhiêu, ở ô nào |

Cho phép **tổng nhỏ hơn** số lượng dòng khi phiếu còn nháp (đang quét dở). Bằng nhau là điều kiện
để **duyệt**, và trang PDA chịu trách nhiệm chỉnh số lượng dòng xuống bằng số lấy thật trước khi
duyệt (§6.4).

**Duyệt thẳng từ form với phân bổ dở dang** (không qua PDA) thì hook chặn với câu báo §4.3 — cố ý:
phân bổ dở dang nghĩa là "mới quét được một phần", và im lặng chạy FEFO cho phần còn lại sẽ trừ
những ô chưa ai tới lấy. Muốn để hệ tự chọn ô thì **xoá sạch** phân bổ của phiếu rồi duyệt.

**Lớp chặn cuối — hook.** §4.1. Là lưới an toàn cho đường API và cho chứng từ sửa bằng tay.

## 6. Trang PDA `lay-hang-pda`

Cùng khuôn hai trang PDA đã có: một cột, ô quét dùng chung `public/js/vi_tri_kho/o_quet.js`,
biến màu Frappe, vai trò `System Manager` / `Stock Manager` / `Stock User`.

### 6.1 Màn danh sách

Phiếu giao **nháp** của kho quản lý vị trí, mới nhất trước: số phiếu, khách hàng, số dòng, tổng
số món phải lấy, và **tiến độ** (`đã lấy 20/50`). Chạm để mở.

Phiếu đang có người khác lấy dở (có dòng phân bổ mang `nguoi_lay` khác) thì hiện *"{tên} đang
lấy"* và **hỏi lại** trước khi mở — không khoá cứng, vì ca sau có thể phải lấy tiếp phiếu của ca
trước.

### 6.2 Màn lấy hàng của một phiếu

Mỗi dòng hàng hiện: tên hàng, lô hệ chốt, **ô nên tới lấy** (từ `fefo.chon_o_xuat`, hạn gần nhất
trước; nhiều ô thì liệt kê theo thứ tự đi lấy), số cần lấy, số đã lấy.

Thứ tự thao tác, giống hai trang kia: **① quét tem LÔ → ② quét tem Ô**.

- Quét lô **không thuộc phiếu này** → báo *"lô này không nằm trong phiếu"*, không ghi gì.
- Quét lô **khác lô hệ chốt nhưng cùng mặt hàng**: so hạn dùng.
  - Lô quét có hạn **gần hơn hoặc bằng** → nhận, cảnh báo nhẹ.
  - Lô quét có hạn **xa hơn** → hiện khung cam *"Lô {X} hạn {ngày} — xa hơn lô hệ chọn {Y} hạn
    {ngày}. Quét lại tem {X} để xác nhận"*, đúng cách xác nhận bằng quét lại của trang xếp hàng.
  - Nhận rồi thì **sửa `batch_no` của dòng phiếu giao** sang lô mới (một dòng chỉ mang một lô —
    xem §8).
- Quét ô: ô không có lô đó → báo *"ô {O} không có lô {X}"*; có thì ghi nhận số lượng (mặc định
  bằng min(số còn cần, tồn của ô), sửa được) vào bảng phân bổ và **lưu phiếu ngay** — mất điện
  không mất việc đã quét.

### 6.3 Lấy thiếu

Ô hết hàng sớm hơn sổ: quét ô khác bù. Không còn ô nào mà vẫn thiếu → nút **"Chốt thiếu"** trên
dòng: ghi số thực lấy được, và khi hoàn tất, **sửa số lượng dòng phiếu giao** xuống bằng số đó,
kèm ghi chú tự động vào `Delivery Note.remarks`:

> Lấy thiếu {N} {đơn vị} {mặt hàng} lô {X} — ô trống sớm hơn sổ, cần kiểm kê ô {O}.

Đây là **cảnh báo**, không tự sửa sổ vị trí (§2).

### 6.4 Hoàn tất

1. Kiểm: mọi dòng đã lấy đủ hoặc đã chốt thiếu.
2. Ghi bảng phân bổ (đã ghi dần ở §6.2) + chỉnh số lượng dòng nếu có chốt thiếu.
3. **Duyệt phiếu giao**. Hook đọc phân bổ → sổ vị trí trừ **đúng ô đã quét**.
4. Duyệt hỏng (hết hàng, sai lô, ai đó vừa chuyển ô) → phiếu **còn nháp**, phân bổ còn nguyên,
   hiện câu báo của máy chủ để quét lại. Dùng savepoint như `xep.duyet_phieu_xep`.

Hộp xác nhận **chỉ nhận chạm tay**, không dùng `frappe.confirm` — súng quét gửi Enter sau mỗi lần
quét và `keyboard.js` bắt Enter để bấm "Có" (đã trả giá một lần ngày 17/09, xem
`xep_hang_pda.js`).

## 7. Máy chủ — module mới `vitri/lay_hang.py`

| Hàm | Việc |
|---|---|
| `danh_sach_phieu_giao(kho)` | phiếu giao nháp + tiến độ lấy |
| `mo_phieu_giao(phieu)` | dòng hàng, lô, số cần/đã lấy, **ô nên tới lấy** (gọi `chon_o_xuat`) |
| `quet_de_lay(phieu, ma)` | nhận diện mã: lô của phiếu / lô khác cùng mặt hàng / ô / không rõ |
| `ghi_da_lay(phieu, dong_hang, so_lo, o, so_luong)` | thêm/cộng dòng phân bổ, lưu phiếu |
| `bo_dong_da_lay(phieu, ten_dong_phan_bo)` | quét nhầm thì gỡ |
| `chot_thieu(phieu, dong_hang)` | đánh dấu dòng lấy thiếu |
| `hoan_tat(phieu)` | chỉnh số lượng + submit trong savepoint |
| `kiem_phan_bo_khi_luu(doc, method)` | lớp sớm §5, gắn `doc_events` |

Quyền: cùng bộ `VAI_TRO_DUOC_XEP` (`System Manager`, `Stock Manager`, `Stock User`) và **không**
`ignore_permissions` khi lưu/duyệt phiếu giao — quyền duyệt phiếu giao vẫn là của doctype.

## 8. Chỗ đã biết là vướng

**Một dòng phiếu giao chỉ mang một lô** (`Stock Settings.use_serial_batch_fields = 1` trên site
này — đo 18/09). Nên:

- Đổi lô = ghi đè `batch_no` của dòng đó. Được, vì phiếu còn nháp.
- Lấy một dòng từ **hai lô khác nhau** thì phải **tách dòng phiếu giao**. Trang PDA sẽ tự tách:
  giữ dòng cũ với số lượng đã lấy của lô cũ, thêm dòng mới cho lô mới. Đây là phần **dễ sai
  nhất** của cả việc này — phải có bài kiểm riêng, và nếu site đổi sang bundle (tắt
  `use_serial_batch_fields`) thì phần này phải viết lại.

**Hai người cùng một phiếu**: bảng phân bổ nằm trên phiếu, hai người lưu cùng lúc sẽ đụng
`TimestampMismatchError` của Frappe. Chấp nhận: người sau nhận câu báo "phiếu vừa đổi, mở lại",
màn hình tự nạp lại. Không làm khoá riêng.

**Kho không bật quản lý vị trí**: trang không liệt kê phiếu của kho đó.

## 9. Kiểm thử

**Server (`vi_tri_kho/tests/test_lay_hang.py`):**

1. Có phân bổ → sổ vị trí trừ **đúng ô đã phân bổ**, không phải ô FEFO chọn (dựng hai ô cùng lô,
   phân bổ vào ô FEFO **không** chọn — đây là bài chịu lực của cả thiết kế).
2. Không có phân bổ → vẫn chạy FEFO y như cũ (chốt âm: hành vi cũ không đổi).
3. Tổng phân bổ lệch → hook chặn, phiếu không ghi dòng sổ nào.
4. Lớp sớm: ô khác kho / ô nhóm / vượt số lượng dòng / ô không đủ tồn → `validate` chặn khi lưu
   nháp, mỗi ca một bài, bắt bằng `assertRaisesRegex` (không chỉ loại ngoại lệ).
5. Lấy thiếu → số lượng dòng giảm đúng, sổ vị trí khớp số thực, remarks có ghi chú.
6. Đổi lô → `batch_no` dòng đổi, sổ vị trí ghi đúng lô mới.
7. Tách dòng khi lấy hai lô cho một dòng.
8. Huỷ phiếu giao đã lấy theo phân bổ → hàng về **đúng các ô đã lấy** (chốt âm: không về
   `CHUA-XEP`).
9. Phân bổ cho chứng từ **không phải Delivery Note** (ví dụ Stock Entry) → không ai đọc, không nổ.

**Giao diện (Chrome headless 360×740, khuôn `t18`/`t19`):** mở danh sách → mở phiếu → quét lô →
quét ô → dòng lưu ngay → tải lại trang thấy lại → lấy thiếu → hoàn tất → phiếu giao docstatus 1 →
sổ vị trí đúng ô. Kèm ca "Enter khi hộp xác nhận đang mở → không duyệt".

**Cả bộ `vi_tri_kho` (466 bài) phải xanh** — nhánh hook mới không được đụng đường cũ.

**Luồng A→Z**: chạy lại `docs/vi_tri_kho/HDSD-luong-tu-A-den-Z.md` với bước 9 đi qua trang mới,
rồi cập nhật tài liệu đó (bỏ khung "chưa có màn hình lấy hàng").

## 10. Rủi ro

| Rủi ro | Vì sao đáng sợ | Chặn bằng |
|---|---|---|
| Nhánh hook mới làm hỏng đường cũ | hook là chỗ mọi chứng từ kho đi qua; hỏng thì lệch âm thầm, đối soát theo tổng vẫn khớp | bài 2 và 9 ở §9 + chạy cả bộ 466 bài |
| Phân bổ "mồ côi" (dòng hàng bị xoá, phiếu sửa lại) | ghi sổ theo dữ liệu rác | lớp sớm kiểm `dong_hang` trỏ đúng dòng đang có; xoá dòng hàng thì dọn phân bổ của nó |
| Tách dòng khi hai lô | sửa cấu trúc chứng từ từ một trang PDA | bài 7; và tách **chỉ khi** người dùng thật sự quét lô thứ hai |
| Thủ kho quét cho đủ rồi mới đi lấy | hệ tin số quét | không chặn được bằng phần mềm; tài liệu nói rõ trách nhiệm |

## 11. Việc còn treo, không thuộc phạm vi

1. `Stock Settings` → `FIFO` hay `Expiry` khi chọn **lô** (quyết định của công ty).
2. Mở phân bổ cho phiếu nhập (chọn ô ngay khi nhập, thay cho bước xếp hàng riêng).
3. `Location Count` — kiểm kê theo ô, để đóng vòng "lấy thiếu → kiểm kê → chỉnh sổ".

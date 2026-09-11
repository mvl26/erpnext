# Bàn giao: nền tảng quản lý vị trí kho (GĐ 0 + GĐ 1)

Nay là **module `Vi Tri Kho` trong app `erpnext`** (fork `mvl26/erpnext`), nhánh
`feat/mo-rong-vi-tri-kho-warehouse` · **182/182 test xanh**
Spec: `docs/superpowers/specs/2026-09-09-miyano-wms-vi-tri-kho-design.md`
Mã nguồn: `erpnext/vi_tri_kho/` · Tài liệu: `docs/vi_tri_kho/`

> **Chuyển nhà 11/09/2026 — không còn app riêng `miyano_wms`.**
> Chủ dự án chốt: đây là **mở rộng của `Warehouse`**, nên thuộc về cây ERP chứ không
> phải một app bên cạnh — đúng golden rule của repo này (`CLAUDE.md`: "edit the relevant
> module directly, don't route around core"), và cùng khuôn với module `Einvoice` mà fork
> đã tự thêm trước đó.
>
> Mọi file mới nằm gọn trong `erpnext/vi_tri_kho/`. Chỉ **3 file của upstream bị chèn,
> mỗi file một dòng**: `hooks.py` (móc `Stock Ledger Entry.on_submit`), `modules.txt`,
> `patches.txt`. Trong đó **dòng ở `hooks.py` là dòng dễ mất nhất** ở mỗi lần merge
> ERPNext bản mới — mất nó thì chứng từ vẫn chạy, chỉ là không ô nào được ghi sổ nữa.
> `tests/test_app_khoi_dong.py` khoá đúng việc đó (đã đột biến kiểm chứng).
>
> Đường chạy test đổi theo: `bench --site erptest.local run-tests --module
> erpnext.vi_tri_kho.tests.<tên>`. **Đừng** chạy `--app erpnext` nếu chỉ muốn kiểm phần
> này — nó kéo theo hàng nghìn bài của upstream.
>
> Tài liệu KHÔNG nằm cạnh mã nguồn: repo có cổng cưỡng chế vị trí file
> (`scripts/file_structure/gate.py`), và bản đồ của nó chỉ cho tài liệu ở `docs/` gốc
> repo — `.zip`/`.docx` thì không được phép nằm dưới `erpnext/` ở bất kỳ đâu. Kiểm bằng
> `python3 -m scripts.file_structure --audit` trước khi commit.

> **Cập nhật 10/09/2026 — mã ô đổi sang chuẩn 12 ký tự của SPD.**
> Chủ dự án đưa `docs/SPD_VanHanh_PhanTichMaViTriKho_20260907_v2.docx` và chốt mã ô
> `[Kho 2][Khu 2][Dãy 2][Khoang 2][Tầng 2][Ô 2]`, ví dụ `K11B01040302`. Bản bàn giao gốc
> mô tả mô hình cũ (mã tự do + cây nested set); những chỗ đã thay đổi ghi ở mục 0 ngay dưới.
> Tài liệu superpowers cũng đã chuyển từ repo `miyano_portal` về repo này — bản còn sót bên
> đó là bản lỗi thời, đừng đọc.

---

## 0. Những gì đã đổi sau bản bàn giao gốc

| Trước | Nay |
|---|---|
| `ma_o` chuỗi tự do, người dùng tự đặt | **12 ký tự**, regex chặn cả miền giá trị (dãy/khoang/ô `01`–`99`, tầng `01`–`09`) |
| `Storage Location` là cây nested set (`cap_do`, `is_group`, `lft`/`rgt`) | **bảng phẳng** — mã đã mã hoá sẵn cấp bậc, giữ cây là có hai nguồn sự thật |
| — | thêm `ma_in_nhan` (`K11B0104-0302`, tự sinh khi lưu), `loai_vi_tri`, và 6 trường thành phần chỉ đọc |
| Bộ sinh nhận `tien_to_khu` + `mau_ma` tự do | nhận đúng 6 chiều SPD; mã kho lấy từ **`Warehouse.custom_ma_kho_spd`** |
| Ô hệ thống tên `CHUA-XEP` | **`ZZZ-CHUA-XEP`** |

**Vì sao phải đổi tên ô hệ thống** — không phải thẩm mỹ: mã 12 ký tự toàn số nên thứ tự chữ
cái trùng thứ tự số. Nhiều bài test FEFO dựng thế **thứ tự chữ cái ngược với thứ tự ưu tiên**
để chứng minh code thật sự sắp theo hạn dùng chứ không phải theo tên. Giữ tiền tố `C` thì ô
hệ thống lọt vào giữa, các bài đó vẫn xanh mà không còn chứng minh gì.

Số bài giảm từ 187 xuống 182 là do bỏ các bài đã hết đối tượng (nút nhóm của cây nested set),
không phải bỏ bớt phạm vi kiểm.

---

## 1. Trạng thái bàn giao

**ĐÃ BẬT cho `Kho Miyano - MYN` ngày 10/09/2026** theo quyết định của chủ dự án.

| Đo được sau khi bật | |
|---|---|
| `custom_quan_ly_vi_tri` | 1 |
| Ô kệ | **129** = 128 ô thật (khu `1A`, 4 dãy × 4 khoang × 4 tầng × 2 ô) + 1 ô `ZZZ-CHUA-XEP` |
| Sổ vị trí / tồn vị trí | 103 dòng / 103 dòng |
| `Warehouse Location Setup` | "Đang bật" |
| Đối soát | **khớp** — 0 dòng lệch, 0 ô âm, 0 lệch bộ đệm |

Bất biến §3 đã kiểm **độc lập bằng SQL thô** (không qua `doi_soat_kho`): 103 mặt hàng có
`Bin`, **0 mặt hàng lệch** giữa tổng tồn các ô và `Bin.actual_qty`.

Toàn bộ 103 dòng tồn hiện nằm ở ô `ZZZ-CHUA-XEP` — đúng thiết kế. Việc xếp hàng vào 128 ô
thật là việc ngoài kho cộng với màn hình khai vị trí của **GĐ 2** (chưa có).

Kích thước kệ là **kho mẫu do chủ dự án chọn**, đúng tinh thần §5 của SPD ("cần kiểm
nghiệm tại kho mẫu"). Thêm dãy 05, 06… về sau chỉ là chạy lại bộ sinh; ngược lại thì
không, vì §5.3 cấm cấp lại mã đã dùng.

## 2. Bốn việc phải dặn người vận hành

1. **`dong_bo_lai()` KHÔNG còn là lối thoát vạn năng.** Nó ném lỗi nếu kho có ô âm hoặc bộ
   đệm trôi khỏi sổ. Gặp lỗi đó thì dùng **"Dựng lại tồn vị trí"** (`dung_lai_ton_vi_tri`),
   đừng bấm lại `dong_bo_lai`.
2. **Không tích `Ngừng dùng` lên ô `ZZZ-CHUA-XEP`** — đã bị chặn bằng mã, nhưng cần biết vì
   sao: ô đó là van an toàn của cả kho.
3. **Mã ô không sửa được sau khi tạo** (`ma_o` khoá cứng) và theo §5.3 của SPD thì **mã đã
   dùng không bao giờ cấp lại**. Đổi mã = xoá ô, và mã cũ chết theo. Đối chiếu sơ đồ kho cho
   xong TRƯỚC khi sinh hàng loạt, vì tem đã in và người đã quen mã.
4. **Phải khai `Mã kho SPD (2 ký tự)` trên phiếu Warehouse trước khi sinh ô** — chưa khai thì
   bộ sinh ném lỗi. Đó là 2 ký tự đầu của mọi mã ô trong kho.

## 3. Việc CÒN LẠI, xếp theo mức

### Phải làm trước khi mở rộng ra chứng từ khác
- **`Purchase Invoice`, `Sales Invoice`, `Subcontracting Receipt`, `Asset Capitalization`
  vẫn ZERO test tích hợp.** Hook bắt được chúng theo thiết kế (một chỗ móc duy nhất), nhưng
  chưa loại nào chạy thật một lần. `Delivery Note` và `Purchase Receipt` thì đã có đủ 4 bài
  (ghi + huỷ).

### Lỗ đã biết, mức HẸP, phải ghi sổ
- **Lỗ đối xứng ở đường XUẤT.** Bản vá `_tra_lai_o_da_dao` chỉ chữa chiều NHẬP. Với chứng từ
  XUẤT đi qua `Repost Item Valuation` có `recreate_stock_ledgers = 1`: bước 2 sinh delta âm
  → FEFO **chọn lại**, có thể ra ô khác ô đã lấy. **Cả ba phép đo của đối soát đều mù trước
  ca này.** Hẹp vì: checkbox phải bật tay (mặc định 0), và ERPNext **cấm** bật cho hàng có
  lô/serial — hàng Miyano chủ yếu có lô.

### Nợ ở tầng test (không đổi hành vi sản phẩm)
- **ĐÃ TRẢ 10/09/2026, và nó đắt hơn dự tính.** Món "toàn suite ràng vào dữ liệu của
  `erptest.local`" khi đến hạn không chỉ làm 6 bài đỏ vì đổi tiền đề — nó còn lộ ra **một
  bài khoá NGƯỢC hành vi thật suốt nhiều tháng**: bốn chỗ trong test tự dựng ô "Chưa xếp"
  mà bỏ trống `thu_tu_lay_hang` (nhận 0 = lấy đầu), trong khi production đặt 9999 (lấy
  cuối). Bài FEFO khẳng định đúng chiều ngược lại và vẫn xanh, vì nó tự dựng một thế giới
  production không bao giờ sinh ra. Nay ô hệ thống chỉ được tạo qua
  `bat_kho.tao_o_chua_xep()`. **Bài học chung: một bài test dựng lấy đối tượng mà
  production cũng dựng là đủ để nó khoá nhầm chiều — dùng lại hàm của production, đừng
  chép hình dạng của nó.**
- **Cổng `khop` cho `lech_bo_dem` không có bài nào khoá** — xoá `and not lech_bo_dem` khỏi
  điều kiện thì suite vẫn xanh (đo bằng đột biến lúc suite còn 173 bài; đợt 12 ký tự không
  đụng tới chỗ này nên nợ vẫn nguyên).
- `TestOAm` / `TestLechBoDem` kết thúc bằng `assertFalse(kq["khop"])`. Khi ghi món nợ này,
  `Kho Miyano - MYN` luôn lệch 103 dòng nên khẳng định đó **luôn xanh**, không chứng minh
  gì. Từ 10/09/2026 kho đã bật và đối soát khớp, nên tiền đề đổi — **chưa đo lại**, đừng
  coi là đã trả cũng đừng coi là còn nguyên. Cách đo: đột biến điều kiện `khop` rồi chạy
  `test_doi_soat`.
- Một bài assert vào phần **tĩnh** của thông báo lỗi ("âm" vốn có sẵn trong chuỗi cứng) nên
  xanh kể cả khi hàm mô tả lỗi trả chuỗi rỗng.
- **Toàn suite ràng vào dữ liệu của `erptest.local`** → không chạy được trên site `miyano`.

### Nợ nhỏ
- `hooks.py` chưa có `scheduler_events`, nên đối soát chỉ gọi tay được (spec §8.4 đòi cả
  định kỳ). Kèm theo: trạng thái `"Cần đồng bộ lại"` **không nơi nào trong mã đặt** — field
  đang quảng cáo một cơ chế tự phát hiện lệch chưa tồn tại. Nên làm cùng lúc.
- Spec §5.2 đòi index tổ hợp; cài đặt chỉ có `search_index` từng cột rời. Chưa đau ở quy mô
  hiện tại.

## 4. Cảnh báo triển khai

**Patch thêm unique index cho `Location Balance` giả định bảng đang rỗng.** Đúng trên
`erptest.local`, **không suy ra được** cho site `miyano` (prod, máy khác). Nếu bảng ở đó đã
có dữ liệu trùng khoá thì `bench migrate` **dừng giữa chừng**. Kiểm trước khi deploy.

## 5. Hai cái bẫy ERPNext đã trả giá để tìm ra

Ghi lại vì chúng sẽ cắn lại ở bất kỳ việc nào đụng tới sổ kho:

1. **`Stock Reconciliation` hàng KHÔNG lô ghi `actual_qty = 0`** và chỉ đặt
   `qty_after_transaction` (`stock_reconciliation.py:861,870`). Cộng dồn `actual_qty` là bỏ
   qua âm thầm mọi lần kiểm kê. `actual_qty == 0` chỉ **tình cờ** đúng ở đường ghi thường —
   đừng lấy nó làm dấu hiệu nhận biết.
2. **`Landed Cost Voucher` và `Repost Item Valuation` đặt `docstatus=2` → ghi sổ →
   `docstatus=1` → ghi sổ lần nữa** (`landed_cost_voucher.py:243-250`). Hook nổ **hai lần**.
   Không xử lý thì hàng âm thầm rời ô thật mà tổng vẫn đúng.

Cộng một bẫy Frappe: **`set_only_once` không bao giờ nổ trên field autoname** —
`_sync_autoname_field()` (`document.py:632`) chạy TRƯỚC `validate_set_only_once()` (`:654`)
và ghi đè giá trị về `name`. Muốn khoá thật phải chặn trong `validate()` của controller.

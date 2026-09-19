# Thiết kế: cây vị trí kho và mã ô 10 ký tự

Ngày: 2026-09-11
Trạng thái: chờ chủ dự án duyệt
Phạm vi: module `Vi Tri Kho` trong app `erpnext` (`erpnext/vi_tri_kho/`)
Thay thế: mục §5.1 và §5.8 của `2026-09-09-miyano-wms-vi-tri-kho-design.md`

> Tài liệu này **không** viết lại toàn bộ thiết kế. Nền tảng — một móc
> `Stock Ledger Entry.on_submit`, sổ vị trí chỉ ghi thêm, bất biến "tổng tồn các ô =
> `Bin.actual_qty`", ô `ZZZ-CHUA-XEP` làm van an toàn — **giữ nguyên**. Đọc spec
> 2026-09-09 trước; tài liệu này chỉ đổi ba thứ: lằn ranh Warehouse/vị trí, độ dài mã,
> và việc dựng lại cây.

## 1. Vì sao sửa

Bản đang chạy có ba chỗ hụt, phát hiện khi rà lại cùng chủ dự án ngày 11/09/2026:

**a. Không có cây.** Spec cũ cố ý bỏ cây với lý do "mã đã mã hoá sẵn cấp bậc, giữ cây là
có hai nguồn sự thật phải tự tay đồng bộ". Lý do đó vẫn đúng **với cây khai bằng tay** —
nhưng nó đã khiến ba việc sau không làm được: gộp tồn theo Khu/Dãy, đặt thuộc tính ở cấp
trên (ngừng dùng cả một dãy khi sửa kệ), và chỉ định lấy hàng ở cấp trên. Cả ba đều là
yêu cầu thật của vận hành.

**b. Mã 12 ký tự mang thừa thông tin.** Hai ký tự đầu là mã kho, trong khi bản ghi đã có
trường `kho` trỏ tới `Warehouse`. Cùng một sự thật lưu hai chỗ thì sớm muộn lệch nhau.
Bỏ đi còn **10 ký tự**, trùng khớp luôn mã của kho SPD Nhật trong tài liệu gốc
(`4B01-04-0302`).

**c. `loai_vi_tri` là nhãn an toàn giả.** Trường này có lựa chọn `Cách ly`, nhưng **không
chỗ nào trong `vitri/` đọc nó** (đã đo). Hàng đặt ở ô "Cách ly" vẫn bị FEFO chọn ra để
xuất bán như ô thường. Đây là lỗi đang nằm trong bản chạy, không phải rủi ro tương lai.

## 2. Quyết định nền

Đã chốt với chủ dự án. Đây là ràng buộc của thiết kế, không phải gợi ý.

| # | Quyết định | Ghi chú |
|---|---|---|
| 1 | **Lằn ranh Warehouse / vị trí đi theo Ý NGHĨA TỒN KHO, không theo tầng bậc** | Xem §3. Chủ dự án chọn phương án này sau khi được trình ba phương án |
| 2 | Mã ô **10 ký tự** `[Khu 2][Dãy 2][Khoang 2][Tầng 2][Ô 2]` | Bỏ 2 ký tự mã kho; kho nằm ở trường `kho` |
| 3 | `Storage Location` **là cây nested set trở lại**, 5 cấp | Nhưng cha con **suy ra từ mã**, không ai gõ — xem §5 |
| 4 | Bỏ `Cách ly` và `Trả hàng` khỏi `loai_vi_tri` | Cách ly thật phải là Warehouse (§3) |
| 5 | Chỉ **ô lá** mới giữ hàng | Nút nhóm không bao giờ xuất hiện trong sổ vị trí |
| 6 | `disabled` **thừa kế xuống nhánh**; `thu_tu_lay_hang` **không** | Xem §6 và §9 |

### 2.1 Vì sao không tách mọi Khu thành Warehouse — ghi lại để khỏi tranh luận lại

Phương án "mỗi Khu là một Warehouse" mua được rất nhiều thứ miễn phí: ERPNext tự biết tồn
theo Khu qua `Bin`, chọn Khu khi giao hàng chính là chọn kho, và cây kho có sẵn giao diện.

Nó bị loại vì **cái giá nằm ở chỗ khác**: Warehouse là ranh giới tồn kho, nên mỗi phiếu
nhập/xuất buộc người nhập liệu phải quyết "hàng này thuộc khu nào" **ngay lúc gõ chứng
từ**. Mà đó đúng là thứ ô `ZZZ-CHUA-XEP` được đẻ ra để tránh: quyết định xếp hàng thuộc về
lúc xếp hàng ngoài kho, không phải lúc nhập liệu. Chọn sai kho thì phải làm phiếu điều
chỉnh; chọn sai vị trí thì chỉ là một dòng trong báo cáo "Hàng chưa xếp".

Thêm một ràng buộc cứng của ERPNext: `Warehouse.convert_to_group()` ném lỗi
`Warehouses with existing transaction can not be converted to group`
(`erpnext/stock/doctype/warehouse/warehouse.py:169-171`). `Kho Miyano - MYN` đang có 103
dòng `Bin` và 183 dòng `Stock Ledger Entry`, nên không thể biến thành kho nhóm bằng cách
đổi cờ — sẽ phải chuyển toàn bộ tồn đi bằng phiếu chuyển kho thật.

## 3. Lằn ranh: khi nào là Warehouse, khi nào là vị trí

> Một chỗ trở thành **Warehouse** khi hàng ở đó **phải bị loại khỏi luồng xuất bán bình
> thường**, hoặc **phải định giá riêng**. Còn lại là địa chỉ vật lý, và địa chỉ vật lý
> thuộc về cây vị trí.

| Chỗ | Warehouse | Vị trí |
|---|---|---|
| Cách ly, chờ kiểm nhập, hàng hỏng | ✔ | |
| Hàng trả về | ✔ *(đã có `Hàng trả về - MYN`)* | |
| Kho lạnh — nếu kế toán tách giá trị | ✔ | |
| Khu A / Khu B trong cùng một phòng kho | | ✔ |
| Dãy, khoang, tầng, ô | | ✔ |

**Hôm nay quyết định này không đòi chuyển kho nào.** Cây kho hiện tại đã đúng sẵn:
`Hàng trả về - MYN` chính là một "khu có ý nghĩa tồn kho" đã được tách đúng cách từ trước
khi có module này. `Kho Miyano - MYN` giữ nguyên là kho lá; Khu `1A`/`1B` nằm trong cây vị
trí.

**Hệ quả bắt buộc:** `loai_vi_tri` chỉ còn `Lưu trữ` và `Soạn hàng`. Giữ `Cách ly` là
quảng cáo một sự cách ly không tồn tại — và đó là loại lỗi tệ nhất, vì người dùng tin vào
nhãn rồi mới phát hiện hàng cách ly đã lên phiếu giao.

Không thêm cơ chế "FEFO bỏ qua ô cách ly": làm vậy là viết lại `Warehouse` một cách tồi
hơn, và chỉ chặn được đúng đường FEFO chứ không chặn báo cáo tồn, không chặn kiểm kê,
không chặn kế toán.

## 4. Mã ô 10 ký tự

```
1B  01   04      03    02   →  1B01040302
khu dãy  khoang  tầng  ô

  Hiển thị và lưu :  1B01040302   (10 ký tự liền)
  In tem          :  1B0104-0302  (với tiền tố "VT " là 14 ký tự,
                                   dưới giới hạn 16 của trường F8)
```

| Phần | Dài | Miền giá trị | Cách đánh số |
|---|---|---|---|
| Khu | 2 | số + chữ, ví dụ `1B` | chữ số = tầng nhà (0 nếu nhà một tầng), chữ cái = khu |
| Dãy | 2 | `01`–`99` | tăng dần từ cửa nhập theo lối đi chính |
| Khoang | 2 | `01`–`99` | từ đầu dãy phía lối đi chính |
| Tầng | 2 | `01`–`09` | **đếm từ dưới lên** |
| Ô | 2 | `01`–`99` | trái → phải khi đứng đối diện kệ |

Regex chặn cả miền giá trị chứ không chỉ hình dạng: `00` hợp hình dạng nhưng không có dãy
0 hay tầng 0 nào, và nếu lọt thì lọt xuống tận tem in. Một chỗ duy nhất định nghĩa quy
tắc: `vitri/ma_vi_tri.py`.

SPD đôi chỗ viết `K1-1B01-04-0302` cho dễ đọc bằng mắt. Đó là cách trình bày trong văn
bản, **không** phải một dạng hệ sinh ra.

## 5. Cây suy ra từ mã — điểm cốt lõi của thiết kế

`Storage Location` là nested set trở lại (`is_tree: 1`,
`nsm_parent_field: parent_storage_location`), 5 cấp:

```
1B                    Khu       is_group = 1
└ 1B01                Dãy       is_group = 1
  └ 1B0104            Khoang    is_group = 1
    └ 1B010403        Tầng      is_group = 1
      └ 1B01040302    Ô         is_group = 0   ← chỉ cấp này giữ hàng
```

**Cha con KHÔNG do người dùng khai.** `parent_storage_location` để `read_only`;
`validate()` tự tính cha từ tiền tố mã và **tự tạo các nút cha còn thiếu**. Mã vẫn là
nguồn sự thật duy nhất; cây chỉ là hình chiếu của mã.

Đây chính là chỗ spec cũ thiếu. Phản đối "hai nguồn sự thật" hồi đó là đúng — nhưng nó chỉ
áp cho cây khai tay. Cây suy ra từ mã **không có đường nào để lệch**, vì không có thao tác
nào của người dùng có thể đặt nó lệch.

**Tên nút nhóm chính là tiền tố mã** (`1B`, `1B01`, `1B0104`, `1B010403`). Nên `ma_o` có
độ dài 2/4/6/8 với nút nhóm và đúng 10 với ô lá. `validate()` kiểm theo đúng cấp.

**`ZZZ-CHUA-XEP` đứng ngoài cây** — nút gốc riêng, `is_group = 0`, miễn kiểm định dạng.
Nó là ô lô-gic, không ứng với chỗ nào ngoài kho, nên ép vào cây là bịa ra một địa chỉ vật
lý không tồn tại.

## 6. Ba năng lực mà cây phải mang lại

### 6.1 Gộp tồn theo cấp

Nested set cho sẵn `lft`/`rgt`, nên tồn của cả một nhánh là một điều kiện
`where sl.lft between :lft and :rgt`. Báo cáo `Tồn kho theo vị trí` đổi thành **báo cáo
cây** (Frappe query report hỗ trợ `parent_field`), gấp/mở được theo Khu → Dãy → Khoang →
Tầng → Ô.

### 6.2 Thuộc tính ở cấp trên

**`disabled` thừa kế xuống cả nhánh.** Ngừng dùng nút `1B01` thì toàn bộ ô trong dãy 01
không được lấy hàng.

> **Đây là chỗ nguy hiểm nhất của cả thiết kế.** `fefo.py` hiện chỉ kiểm
> `ifnull(sl.disabled, 0) = 0` **của chính ô lá**. Không sửa thì người dùng tắt cả dãy để
> sửa kệ, hệ vẫn thản nhiên rút hàng từ dãy đó, và **không có gì báo** — đối soát vẫn
> khớp vì tổng không đổi. Đúng loại lỗi im lặng mà dự án này đã trả giá nhiều lần.

Cài đặt: thêm một `EXISTS` kiểm tổ tiên, không denormalize:

```sql
and not exists (
    select 1 from `tabStorage Location` to_tien
    where to_tien.lft <= sl.lft and to_tien.rgt >= sl.rgt
      and ifnull(to_tien.disabled, 0) = 1
)
```

Chọn `EXISTS` thay vì một cờ `disabled_hieu_luc` denormalize: cờ ấy phải được cập nhật lại
mỗi lần tắt/bật một nút cha và mỗi lần thêm ô mới — tức lại đẻ ra đúng loại "bản sao phải
tự tay giữ đồng bộ" mà §5 vừa loại bỏ.

**Phải sửa CẢ HAI truy vấn của `fefo.py`, không chỉ một.** Module này có hai câu dùng
`disabled`, theo hai chiều ngược nhau:

| Dòng | Câu | Chiều |
|---|---|---|
| ~60 | chọn ứng viên | `disabled = 0` — loại ô đã tắt |
| ~88 | dựng thông báo khi thiếu hàng | `disabled = 1` — tìm hàng đang kẹt ở ô đã tắt |

Câu thứ hai tồn tại để thông báo nói được *"còn 40 đang nằm ở ô 1B01040302 đã ngừng
dùng"* thay vì *"thiếu hàng"* chung chung. Nếu chỉ thêm kiểm tổ tiên vào câu thứ nhất,
hàng nằm dưới một **nút cha** bị tắt sẽ biến mất khỏi cả hai câu: không được chọn, mà cũng
không được nhắc tới. Người dùng tắt cả dãy rồi nhận đúng câu "thiếu hàng" vô nghĩa, và
không có manh mối nào dẫn tới dãy mình vừa tắt. Bài test 2 (§8) khoá đúng điểm này.

**`thu_tu_lay_hang` KHÔNG thừa kế** — xem §9.

### 6.3 Chỉ định lấy hàng ở cấp trên

`chon_o_xuat()` nhận thêm tham số `pham_vi` (tên một nút bất kỳ, có thể là nút nhóm).
Ứng viên giới hạn trong nhánh đó (`between lft/rgt`), thứ tự vẫn FEFO như cũ. `pham_vi`
rỗng = toàn kho, giữ nguyên hành vi hiện tại.

## 7. Chuyển đổi dữ liệu

Đã đo trên `erptest.local`: **128 ô hiện có rỗng hoàn toàn**; cả 103 dòng tồn nằm ở
`ZZZ-CHUA-XEP`. Nên chuyển đổi rẻ bất thường:

1. Xoá 128 ô mã 12 ký tự (không ô nào giữ hàng → không đụng sổ, không đụng tồn).
2. Sinh lại bằng mã 10 ký tự, bộ sinh tự tạo các nút nhóm.
3. Sổ vị trí, tồn vị trí, cờ kho, ô `ZZZ-CHUA-XEP`: **không đổi gì**.

Về §5.3 của SPD ("mã đã cấp không tái sử dụng"): các mã `K1…` **chưa từng in tem và chưa
từng giữ hàng**, nên đây là *chưa từng cấp*, không phải *cấp rồi thu hồi*.

Chủ dự án đã xác nhận (11/09/2026): trên site local được xoá/sửa dữ liệu thoải mái, miễn
thành phẩm đúng. Nên **không** làm patch chuyển đổi tại chỗ cho 128 ô — xoá và sinh lại.
Patch chỉ cần cho hai việc có thể đụng site khác: dọn giá trị `loai_vi_tri` không còn hợp
lệ, và dựng `lft/rgt` lần đầu.

## 8. Kiểm thử bắt buộc

Ngoài việc quét lại mã trong 189 bài hiện có (**giữ nguyên các thế nghịch đảo
chữ-cái/ưu-tiên** đã dựng để bắt đột biến khoá sắp xếp):

| # | Bài | Khoá điều gì |
|---|---|---|
| 1 | Tắt nút **dãy** → FEFO không lấy ô nào trong dãy | §6.2 — lỗ im lặng tệ nhất |
| 2 | Tắt nút **khu** → không lấy được ô nào của khu, và thông báo nói rõ ô nào đang giữ hàng | thừa kế qua nhiều cấp |
| 3 | Lưu ô `1B01040302` khi chưa có nút cha nào → tự sinh đủ 4 nút nhóm | §5 |
| 4 | Sửa tay `parent_storage_location` → bị chặn / bị ghi đè về đúng cha theo mã | §5, chống lệch |
| 5 | Ghi sổ vào một **nút nhóm** → bị chặn | quyết định #5 |
| 6 | `pham_vi` = một dãy → chỉ lấy trong dãy đó dù dãy khác có hạn dùng gần hơn | §6.3 |
| 7 | `pham_vi` rỗng → hành vi y hệt trước khi có tham số | chống hồi quy |
| 8 | Gộp tồn theo khu = tổng tồn các ô lá trong khu, đo bằng đường độc lập | §6.1 |
| 9 | `loai_vi_tri` không còn nhận `Cách ly` | §3 |
| 10 | `ZZZ-CHUA-XEP` vẫn nằm ngoài cây và vẫn nhận hàng | van an toàn |

Mỗi bài của nhóm §6.2 phải **đột biến kiểm chứng**: bỏ mệnh đề `EXISTS` khỏi `fefo.py` thì
bài 1 và 2 phải đỏ. Bài xanh mà không đột biến được thì không tính là đã khoá.

## 9. Cố ý KHÔNG làm (YAGNI)

- **`thu_tu_lay_hang` không thừa kế.** Bộ sinh đã đánh số theo đúng thứ tự cây (dãy →
  khoang → tầng → ô), mà thứ tự đó chính là đường đi trong kho. Thêm cơ chế thừa kế nghĩa
  là mỗi lần đọc phải leo ngược lên tổ tiên tìm giá trị gần nhất — đắt, và chưa ai cần.
  Muốn đổi thứ tự cả dãy thì sửa các ô trong dãy, hoặc chờ tới khi có yêu cầu thật.
- **Không tự xoá nút nhóm khi ô con cuối cùng bị xoá.** Nút nhóm rỗng vô hại; xoá tự động
  là thêm một đường ghi dữ liệu ngầm.
- **Không gộp tồn ở cấp `Warehouse` bằng cây vị trí** — `Bin` đã làm việc đó.
- **Không làm giao diện kéo-thả sắp xếp cây.** Cây suy ra từ mã; kéo thả là mời người dùng
  đặt nó lệch.

## 10. Rủi ro đã biết

| # | Rủi ro | Giảm thiểu |
|---|---|---|
| R1 | Quên kiểm tổ tiên `disabled` → hàng bị lấy từ dãy đã tắt, đối soát vẫn khớp | Bài test 1, 2 + đột biến bắt buộc |
| R2 | Sinh hàng loạt 128 ô đụng khoá `lft/rgt` của nested set | Bộ sinh tạo nút nhóm **trước**, theo thứ tự từ gốc xuống, rồi mới tạo ô lá |
| R3 | Ghi sổ nhầm vào nút nhóm → báo cáo gộp đếm hai lần | Chặn ở `so.ghi_dong_so` (bài test 5) |
| R4 | Có site khác đã dùng `loai_vi_tri = Cách ly` | Patch dọn giá trị, và ghi vào tài liệu bàn giao rằng cách ly phải là Warehouse |

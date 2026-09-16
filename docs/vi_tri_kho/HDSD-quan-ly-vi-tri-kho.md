# Hướng dẫn sử dụng kho

Miyano ERP · quản lý kho và vị trí (giá kệ / ô kệ) · dành cho thủ kho và quản lý kho.

> **Tài liệu này mô tả hệ đang chạy trên site thử `erptest.local` (`http://192.168.61.129:8003`).**
> Đây **không phải** site chạy thật. Site thật là `miyano`, nằm trên máy khác và **chưa cài**
> phần quản lý vị trí. Làm quen trên site thử thoải mái — hỏng gì cũng không ảnh hưởng số liệu
> công ty. Khi đưa lên site thật, làm lại toàn bộ mục 5 từ đầu.

---

## 1. Kho nào đang quản lý vị trí

Công ty **Miyano Việt Nam** có các kho sau:

| Kho | Vai trò | Quản lý vị trí |
|---|---|---|
| `Kho Miyano - MYN` | kho vật tư chính | **CÓ** |
| `Hàng trả về - MYN` | hàng khách trả | không |
| `Stores - MYN`, `Work In Progress - MYN`, `Finished Goods - MYN`, `Goods In Transit - MYN` | kho mặc định ERPNext, chưa dùng | không |

Chỉ **`Kho Miyano - MYN`** được chia ô. Các kho khác vẫn chạy bình thường như ERPNext gốc —
có tồn kho, có nhập xuất, chỉ là không biết hàng nằm ở ô nào.

> ### ⚠ Cái bẫy phải sửa trước khi dùng thật
>
> Trong **Stock Settings**, ô **Default Warehouse** đang là **`Stores - M`** — kho của một
> công ty **khác** (`Miyano`, mã `M`), không phải `Miyano Việt Nam` (mã `MYN`). Nghĩa là một
> chứng từ mới mở ra sẽ **tự điền sẵn một kho không quản lý vị trí**. Người lập phiếu không
> để ý, bấm Lưu — hàng vào kho đó, **sổ vị trí không ghi một dòng nào**, và **đối soát vẫn
> báo khớp** (nó chỉ kiểm những kho có bật quản lý vị trí).
>
> Việc cần làm: đổi Default Warehouse sang `Kho Miyano - MYN`, hoặc xoá trống ô đó để người
> lập phiếu buộc phải tự chọn kho. Đây là việc của quản trị hệ thống, làm **một lần**.

### Ai vào được gì

| Việc | Vai trò cần có |
|---|---|
| Sinh ô, bật/tắt quản lý vị trí, đồng bộ lại | `System Manager` **hoặc** `Stock Manager` |
| **Gán vị trí cố định cho mặt hàng** (tạo / sửa / xoá) | `System Manager` **hoặc** `Stock Manager` |
| Xem bốn báo cáo, xem danh mục ô, **xem các gán vị trí** | thêm `Stock User` |
| Nhập/xuất kho như thường lệ | như ERPNext gốc, không đổi |

Sinh ô, bật/tắt kho và **gán vị trí cố định** đều là **thao tác thiết lập**, cố ý không mở cho
`Stock User` — không phải việc hằng ngày. Thủ kho **xem** được mặt hàng nào thuộc ô nào (và phiếu
xếp vẫn tự điền ô đích cho họ), chỉ không tự đổi được chỗ của một mặt hàng.

Khách hàng đăng nhập cổng (`Website User`) **không vào được gì** của phần này.

### Vào ở đâu

Gõ tên màn hình vào ô tìm kiếm (kính lúp trên thanh trên cùng), hoặc vào thẳng đường dẫn:

| Màn hình | Đường dẫn |
|---|---|
| **Vị trí kho** (trang tổng hợp, vào đây trước) | `/app/vị-trí-kho` |
| Storage Location — danh mục ô | `/app/storage-location` |
| Location Generator — sinh mã ô hàng loạt | `/app/location-generator` |
| Warehouse Location Setup — bật/tắt/đồng bộ | `/app/warehouse-location-setup` |
| Báo cáo **Tồn kho theo vị trí** | `/app/query-report/Ton Kho Theo Vi Tri` |
| Báo cáo **Hàng chưa xếp vị trí** | `/app/query-report/Hang Chua Xep Vi Tri` |
| Báo cáo **Đối soát tồn vị trí** | `/app/query-report/Doi Soat Ton Vi Tri` |
| **Item Location Preference** — gán vị trí cố định | `/app/item-location-preference` |
| Báo cáo **Hàng nằm sai vị trí** | `/app/query-report/Hang Nam Sai Vi Tri` |

*(Đường dẫn **có dấu**, giống `/app/bán-hàng` và `/app/kho-khách-hàng`. Trước 14/09/2026 trang
này nằm ở `/app/vi-tri-kho` không dấu — lệch với mọi trang khác của site và gây lỗi "Not found"
cho người gõ theo tiêu đề; đã đổi cho khớp, đường dẫn không dấu nay **không còn dùng được**.)*

---

## 2. Mã ô đọc thế nào

Mã ô **10 ký tự**, nhìn mã biết ngay chỗ đứng, không phải tra bảng:

```
1B   01   04      03    02        →   1B01040302
khu  dãy  khoang  tầng  ô
```

| Phần | Dài | Miền giá trị | Cách đánh số |
|---|---|---|---|
| Khu | 2 | 1 số + 1 chữ, ví dụ `1B` | theo sơ đồ mặt bằng |
| Dãy | 2 | `01`–`99` | |
| Khoang | 2 | `01`–`99` | trái sang phải |
| Tầng | 2 | `01`–`09` | **đếm từ dưới lên** |
| Ô | 2 | `01`–`99` | trái sang phải |

Hệ lưu và hiển thị **đúng 10 ký tự liền** ở ô **Mã ô**. Ô **Mã in trên nhãn** giữ dạng có gạch
nối `1B0104-0302` cho dễ đọc bằng mắt khi in tem.

Mã sai chuẩn bị **chặn cứng** — sai một ký tự là không lưu được, kèm thông báo chỉ rõ dạng
đúng. `00` cũng bị chặn: không có dãy 0 hay tầng 0 nào cả.

> **Mã ô không bao giờ dùng lại.** Dỡ kệ đi thì mã đó chết theo, không cấp cho ô khác — nếu
> không, tem cũ còn sót lại sẽ chỉ vào chỗ sai.

> **Mã ô cũng KHÔNG sửa được sau khi tạo.** Muốn đổi phải xoá ô và tạo lại, mà mã đã dùng thì
> không cấp lại. Đối chiếu sơ đồ kho cho xong **trước khi** bấm sinh ô.

> ### Ký hiệu Khu phải cấp phát TOÀN HỆ, không phải theo từng kho
>
> Mã ô không chứa mã kho, nên `Mã ô` là khoá chính trên **toàn bộ** danh mục — không riêng
> một kho. Hai kho khác nhau **không được** cùng dùng ký hiệu `1B`. Hệ có chặn (báo "nút nhóm
> đã thuộc kho khác"), nhưng phải thống nhất bảng phân bổ **Khu ↔ Kho** *trước khi* sinh ô,
> đừng để phát hiện sau khi tem đã in.

> ### Cách ly là một KHO RIÊNG, không phải một loại vị trí
>
> Trường **Loại vị trí** chỉ có hai lựa chọn: "Lưu trữ" và "Soạn hàng". **Không có "Cách ly"** —
> và đó là cố ý. Trước đây có, nhưng nó chỉ là một cái nhãn: không chỗ nào trong hệ đọc tới,
> nên hàng để ở ô "Cách ly" **vẫn bị chọn ra xuất bán bình thường**. Một nhãn an toàn giả còn
> nguy hơn không có nhãn.
>
> Muốn cách ly hàng thật (chờ QC, hàng lỗi, hàng thu hồi, hàng hết hạn): tạo một **Kho riêng**
> và chuyển hàng sang đó bằng phiếu chuyển kho. Đó mới là ranh giới tồn kho thật.

---

## 3. Tem vị trí

Mở một ô bất kỳ trong **Storage Location**, mục **Tem vị trí** nằm ngay dưới mục đầu — đó là
**đúng con tem sẽ in ra**, không phải một bản xem trước gần giống.

Tem dựng theo mẫu đang dán trong kho: mã 10 ký tự tách làm **ba nhóm**, theo đúng cách người
đứng trước kệ tìm hàng — tới Khu+Dãy, đếm Khoang, rồi nhìn Tầng+Ô.

```
┌──────┬──────┬─────────────────┐
│  ⬇   │      │  TẦNG        Ô  │
├──────┴──────┤  ┌───────────┐  │
│ KHU DÃY│KHOANG│ │   0302    │  │   ← nhóm cuối to nhất: khi đã đứng
│  1B01  │  04  │ └───────────┘  │      đúng khoang thì chỉ còn nó đáng đọc
├─────────────────────────────────┤
│  ▌│▌▌│▌ ▌│▌▌▌ │▌ ▌│▌▌ ▌│▌      │
│  Kho Miyano - MYN · Kệ inox T3  │
└─────────────────────────────────┘
```

Đọc liền ba nhóm ra `1B` `01` `04` `03` `02` = `1B01040302` — **đúng chuỗi máy quét trả về**,
tức đúng khoá chính của bản ghi. Quét tem là ra thẳng ô, không qua bảng tra nào. Ký hiệu dùng
là **Code 128**, mọi máy quét công nghiệp đều đọc được.

> **Tem KHÔNG in chữ dưới mã vạch** — khác thói quen thường thấy, và là chủ ý. Ba nhóm số ở
> khối trên đã làm đúng việc đó và làm tốt hơn: `1B01 · 04 · 0302` dễ đọc bằng mắt hơn một
> chuỗi mười ký tự liền. Nếu in thử mà thấy khó đọc, đây là chỗ xem lại đầu tiên.

> **Mũi tên ⬇ in cố định trên mọi tem**, nghĩa là "ô của tem này nằm ngay **dưới** chỗ dán" —
> tem dán lên thanh xà hoặc mép tầng trên. Nó không đổi chiều theo dữ liệu được.

Vài điều nên biết:

- Tem **không phải dữ liệu mới** — nó vẽ lại từ Mã ô mỗi lần mở form, không lưu vào cơ sở dữ
  liệu. Sửa được Mã vạch ở mục *Lấy hàng* nếu kho cần một chuỗi khác với Mã ô (hiếm); để trống
  thì hệ lấy bằng Mã ô.
- **Nút nhóm cũng có mã vạch** (`1A`, `1A01`, `1A0104`…) để dán tem đầu dãy, đầu khoang.
- **Ô "Chưa xếp vị trí" không có** — nó là ô ảo, không có kệ thật để dán.

### In tem hàng loạt

Mở **Storage Location** ở dạng cây, mỗi nốt có nút **"In tem"**. Bấm ở nốt nào thì in tem cho
**mọi ô lá thuộc nhánh dưới nốt đó** — bấm ở Khu `1A` ra 128 tem, bấm ở một khoang ra 8 tem,
bấm ở đúng một ô ra một tem.

Hộp thoại cho biết **sẽ in bao nhiêu tem** và vài mã ví dụ trước khi in, kèm ô **Số bản in mỗi
ô** (dán hai mặt kệ thì để 2). Kiểm rồi mới bấm In.

Tem có **hai khổ: 45×25mm (mặc định) và 50×30mm** — chọn trong hộp thoại. Mỗi tem một trang,
đúng cuộn tem của máy in nhiệt, không phải khổ A4. Đã đo trên bản in thật: 45,13 × 25,06mm và
50,12 × 29,97mm, không có tem trắng thừa ở cuối xấp.

> **Khi in phải đặt tỉ lệ 100%, KHÔNG dùng "Fit to page".** Lệch 10% trên con tem 45mm là mã
> vạch chạy ra khỏi mép và máy quét đọc chập chờn ngay trên kệ.

| Không in tem cho | Vì sao |
|---|---|
| Nút nhóm (Khu, Dãy, Khoang, Tầng) | không có kệ riêng để dán |
| Ô "Chưa xếp vị trí" | ô ảo, không tồn tại ngoài kho |

**Trần 500 tem một lần in.** Vượt thì hệ **từ chối hẳn** kèm thông báo, không in 500 tem đầu
rồi lặng lẽ dừng — nếu cắt bớt im lặng, người in tưởng đã in đủ cả nhánh. Chọn nhánh nhỏ hơn
rồi in làm nhiều đợt.

**Thủ kho (`Stock User`) tự in lại được** khi tem rách, bẩn, bong — không phải nhờ quản lý. In
tem không ghi gì vào dữ liệu nên không có rủi ro hỏng số liệu.

> **Nếu không thấy cửa sổ in hiện ra:** trình duyệt đang chặn cửa sổ bật lên. Cho phép pop-up
> cho địa chỉ này rồi bấm In lại.

> **Vẫn nên in thử vài con và dán lên kệ trước khi in cả loạt** — rồi quét thử bằng đúng máy
> quét của kho. Khổ giấy và bố cục đã đo trên bản in ra PDF, nhưng chưa ai quét thử một con
> tem in ra từ máy in nhiệt thật.

---

## 4. Cây vị trí: gấp/mở, và ngừng dùng cả một dãy

Ô kệ là một **cây 5 cấp** (Khu → Dãy → Khoang → Tầng → Ô), suy thẳng từ mã: mỗi cấp là **tiền
tố** của cấp sau.

```
1B                  Khu
└─ 1B01             Dãy
   └─ 1B0104        Khoang
      └─ 1B010403   Tầng
         └─ 1B01040302   Ô  ← chỉ cấp này mới thật sự chứa hàng
```

Cây này **không khai tay** — hệ tự tính lại từ mã mỗi lần lưu, nên không bao giờ có chuyện cây
lệch khỏi mã.

**Xem cây:** mở **Storage Location** ở dạng cây (Tree View) thay vì bảng. Mỗi Khu/Dãy/Khoang/
Tầng là một nút gấp được; nút không gấp được là ô lá — nơi chứa hàng.

**Ngừng dùng cả một dãy trong một thao tác:** tích **"Ngừng dùng"** trên **một nút cha bất kỳ**
— Khu, Dãy, Khoang hay Tầng — là ngừng dùng **toàn bộ ô lá bên dưới nó**. Ví dụ tắt cả khoang
`1B0104` (mấy chục ô bên dưới) chỉ cần tích đúng một bản ghi `1B0104`. Bỏ tích để dùng lại.

Hàng nằm trong nhánh đã tắt: vẫn **cộng vào tồn kho** như thường (đối soát vẫn khớp), chỉ là
**không được chọn để xuất**. Nếu hàng chỉ còn ở nhánh đã tắt, phiếu xuất bị chặn kèm thông báo
**nói rõ ô nào đang giữ hàng** — không phải câu "thiếu hàng" chung chung.

---

## 5. Trình tự làm lần đầu

Làm đúng thứ tự này. Trên `erptest.local` các bước này **đã làm xong rồi** (214 bản ghi: 85 nút
nhóm + 128 ô thật + 1 ô hệ thống); mục này để làm lại khi đưa lên site thật.

### Bước 0 — Thống nhất ký hiệu Khu (một lần, cho TẤT CẢ các kho)

Làm **ngoài phần mềm**: lập một bảng "Khu nào thuộc kho nào" (`1A`, `1B`, `2A`…), mỗi ký hiệu
chỉ dùng cho **đúng một kho**. Lý do ở mục 2.

### Bước 1 — Sinh mã ô

**Location Generator** → **New**:

| Ô nhập | Ví dụ |
|---|---|
| Kho | `Kho Miyano - MYN` |
| Khu (2 ký tự) | `1B` |
| Số dãy (tối đa 99) | `4` |
| Số khoang mỗi dãy (tối đa 99) | `4` |
| Số tầng mỗi khoang (tối đa **9**) | `4` |
| Số ô mỗi tầng (tối đa 99) | `2` |

Lưu, rồi bấm **"Xem trước rồi sinh ô"**. Hộp thoại cho biết **sẽ tạo bao nhiêu ô** và **vài mã
ví dụ** — ví dụ trên là `4 × 4 × 4 × 2` = **128 ô**. Kiểm kỹ rồi mới xác nhận.

Nếu có mã trùng, hệ **không tạo ô nào cả** và báo rõ mã nào trùng. Không có chuyện tạo được
một nửa.

**Thứ tự lấy hàng:** bộ sinh tự đánh số 1, 2, 3… theo thứ tự mã. Nếu đường đi thật trong kho
khác thế, mở từng ô trong **Storage Location** và sửa lại — ô gần cửa để số nhỏ.

### Bước 2 — Bật quản lý vị trí cho kho

**Warehouse Location Setup** → **New** → chọn Kho → **Lưu** → bấm **"Xem trước chuyển đổi"**.

Hộp thoại cho biết sẽ ghi bao nhiêu dòng sổ, cho bao nhiêu mặt hàng và lô, kèm **cảnh báo** nếu
có hàng không quản lý lô hoặc có tồn âm. **Bước xem trước không ghi gì cả** — bấm thoải mái.

Xác nhận trên hộp thoại đó chính là **bật**. *(Không có nút "Bật" riêng — cố ý, để không ai bật
mà chưa xem trước.)*

Toàn bộ tồn hiện có chuyển vào ô **"Chưa xếp vị trí"**, tách theo từng lô. Nếu bước kiểm cuối
phát hiện lệch, hệ **huỷ sạch** và kho quay về đúng như trước — không có trạng thái bật nửa vời.

### Bước 3 — Kiểm ngay sau khi bật

1. Mở **Đối soát tồn vị trí**, chọn kho. **Rỗng nghĩa là khớp.**
2. Mở **Hàng chưa xếp vị trí** — lúc này nó liệt kê **toàn bộ tồn**, vì mọi thứ vừa dồn vào ô
   "Chưa xếp vị trí". Đó là danh sách việc: ra kho xếp hàng vào ô thật.

---

## 6. Vận hành hằng ngày

**Không phải thao tác gì thêm.** Cứ nhập/xuất bằng chứng từ ERPNext như cũ — hệ tự ghi sổ vị
trí ở phía sau.

| Việc | Hệ làm gì |
|---|---|
| Nhập kho (Purchase Receipt, Stock Entry) | Hàng vào ô **"Chưa xếp vị trí"** |
| Xuất kho / giao hàng (Delivery Note, Stock Entry) | Hệ **tự chọn ô** — xem mục 6.2 |
| Huỷ phiếu | Hàng về **đúng ô đã lấy**, không phải ô khác |
| Kiểm kê (Stock Reconciliation) | Sổ vị trí điều chỉnh theo |

**Việc hằng ngày của thủ kho:** mở **Hàng chưa xếp vị trí**, ra kho xếp hàng vào ô thật.
**Việc hằng tuần của quản lý:** mở **Đối soát tồn vị trí**. Rỗng là tốt.

### 6.1 Nhập hàng: số lô phải gõ tay

Cả **80 mặt hàng có quản lý lô** của Miyano đều đặt "không tự sinh lô". Nghĩa là khi nhập hàng,
**người lập phiếu phải gõ số lô theo nhãn của nhà sản xuất** — hệ không tự đẻ ra số lô, và
không cho lưu nếu bỏ trống.

Gõ **kèm hạn dùng**. Hạn dùng là thứ hệ dựa vào để chọn hàng xuất trước; bỏ trống là mất tác
dụng đó. Hiện 55/55 lô trên hệ đều đã có hạn dùng — giữ nguyên kỷ luật này.

Hàng nhập về **dồn hết vào ô "Chưa xếp vị trí"** — chưa có ô khai vị trí ngay trên phiếu nhập.
Việc xếp làm sau, bằng **Phiếu xếp / chuyển vị trí** (mục 6.3).

### 6.2 Xuất hàng: hệ chọn LÔ và chọn Ô theo hai quy tắc KHÁC NHAU

Đây là chỗ dễ hiểu nhầm nhất, đọc kỹ:

| Bước | Ai quyết | Theo quy tắc nào |
|---|---|---|
| 1. Chọn **lô** nào để xuất | ERPNext gốc | **thứ tự nhập** (lô tạo trước xuất trước) |
| 2. Trong lô đó, lấy ở **ô** nào | phần vị trí của Miyano | **hạn dùng gần nhất trước**, cùng hạn thì theo thứ tự lấy hàng |

Lô **đã quá hạn** thì ERPNext tự loại, không chọn. Nhưng giữa hai lô **còn hạn**, nó chọn theo
thứ tự nhập chứ **không** theo hạn dùng.

**Điều này đã được chạy thử trên site và đo, không phải suy đoán.** Ngày 13/09/2026, mặt hàng
`MYN-IMP-NEP-8` có ba lô còn hạn trong kho:

| Lô | Hạn dùng | Tạo lúc |
|---|---|---|
| `E2E-LO-GAN-2026` | **28/10/2026** — còn 45 ngày | 13/09, tạo sau |
| `LO-IMP-NEP-8-2026` | 16/07/2028 | 16/08, tạo trước |
| `E2E-LO-XA-2028` | 12/09/2028 | 13/09 |

Lập phiếu giao **`MAT-DN-2026-00053`** xuất 30 Cái, để hệ tự chọn. Kết quả: hệ lấy
`LO-IMP-NEP-8-2026` (20) rồi `E2E-LO-XA-2028` (10) — **cả hai đều hạn 2028**, còn lô sắp hết
hạn sau 45 ngày **không được đụng tới**.

Đây không phải lỗi, đó là FIFO đúng như cấu hình. Nhưng với vật tư y tế thì hệ quả rất thật:
**hàng sắp hết hạn nằm lại trong kho cho tới lúc hỏng**, trong khi hàng còn hai năm được bán đi.

> **Việc cần quyết.** Trong **Stock Settings**, ô **"Pick Serial / Batch Based On"** đang để
> `FIFO`; đổi sang **`Expiry`** thì cả hai bước đều theo hạn dùng gần nhất trước. Đây là
> **quyết định của công ty**, không phải việc kỹ thuật — nó ảnh hưởng mọi kho, mọi chứng từ,
> nên cần người có thẩm quyền chốt.

Ngược lại, **bước 2 chạy đúng như thiết kế.** Phiếu **`MAT-DN-2026-00054`** xuất 40 Cái, chỉ
định thẳng lô `E2E-LO-GAN-2026` đang nằm ở hai ô. Hệ lấy hết ô gần cửa trước rồi mới đi tới ô
cuối kho:

```
1A01010101   -25   (thứ tự lấy hàng 1)     ← lấy cạn ô này trước
1A04040402   -15   (thứ tự lấy hàng 128)   ← rồi mới tới ô xa
```

### 6.3 Xếp hàng vào ô

Đây là bước biến "hàng đã về kho" thành "hàng nằm ở ô nào". Không có nó thì mọi thứ dồn ở ô
"Chưa xếp vị trí" và cả phần vị trí chỉ chạy được một nửa.

**Cách làm:**

1. Mở **Phiếu xếp / chuyển vị trí** (`/app/location-transfer/new`), chọn **Kho**.
2. Bấm **"Lấy hàng chưa xếp"** — hệ đổ toàn bộ hàng đang ở ô "Chưa xếp vị trí" thành các dòng
   sẵn, cột *Từ ô* điền sẵn, và **cột *Đến ô* cũng điền sẵn** cho những mặt hàng đã được gán vị
   trí cố định (xem mục 10).
3. **Soát lại cột *Đến ô*.** Dòng nào hệ chưa điền thì tự chọn ô. Chia một lô ra nhiều ô thì
   tách thành nhiều dòng và sửa số lượng.

   Hệ **không ép** — sửa đè lên ô hệ gợi ý lúc nào cũng được. Thủ kho đứng trước kệ biết những
   thứ hệ không biết.

   Sau khi bấm "Lấy hàng chưa xếp", nếu có dòng chưa được điền thì hệ hiện một dòng nhắc màu cam
   nói **có bao nhiêu dòng và vì sao**, gộp theo từng lý do. Ba lý do có thể gặp:

   | Lý do hiện ra | Nghĩa là | Việc cần làm |
   |---|---|---|
   | *mặt hàng chưa gán vị trí cố định* | chưa ai gán chỗ cho mặt hàng này | gán một lần ở mục 10, lần sau khỏi phải điền |
   | *vùng `<nút>` đã đầy: N/N ô đang chứa hàng khác* | đã gán rồi, nhưng vùng đó hết chỗ trống và cũng không ô nào đang chứa chính mặt hàng này | dọn bớt vùng đó, hoặc gán mặt hàng sang nút rộng hơn |
   | *không gợi ý được cho `<mã>` — xem Error Log* | có trục trặc dữ liệu ở nút đã gán | báo quản trị; **đừng** đi gán lại, gán lại không chữa được |

   > Ba lý do là ba việc khác nhau. Đọc nhầm "đã đầy" thành "chưa gán" rồi đi gán lại một thứ đã
   > gán là mất công mà vùng kho vẫn hết chỗ.
4. **Lưu** rồi **Duyệt**. Duyệt xong sổ vị trí mới ghi.

Phiếu này cũng dùng để **dồn hàng, đổi kệ**: chọn *Từ ô* là một ô thật thay vì ô "Chưa xếp".

**Xếp nhầm thì Huỷ phiếu** — hàng quay về đúng ô cũ. Sổ giữ nguyên dấu vết cả hai chiều, không
ai sửa được lịch sử. Nếu hàng ở ô đích đã bị xuất đi mất thì **không huỷ được**, kèm thông báo
nói rõ vì sao.

| Hệ chặn | Vì sao |
|---|---|
| Chuyển sang **kho khác** | đổi kho là đổi tồn kho thật — việc của phiếu chuyển kho ERPNext |
| Xếp vào **nút nhóm** (Khu/Dãy/Khoang/Tầng) | không phải kệ thật, không chứa hàng |
| Xếp vào ô **đang Ngừng dùng**, hoặc dưới nhánh đã tắt | hàng vào được mà không xuất ra được |
| Rút quá tồn ô nguồn | sinh ô âm, mà "Đồng bộ lại" cố ý từ chối chữa ô âm |
| Bỏ trống số lô cho hàng có lô, hoặc điền lô cho hàng không lô | lệch tồn theo ô mà tổng vẫn đúng — đối soát không bắt được |

> **Lấy hàng RA khỏi ô đang Ngừng dùng thì VẪN ĐƯỢC** — cố ý. Đó là đường duy nhất gỡ hàng khỏi
> một dãy đang tháo kệ. Chỉ chiều xếp *vào* mới bị chặn.

**Phiếu xếp không đụng tới tồn kho ERPNext.** Chuyển giữa hai ô trong cùng kho không làm đổi
`Bin.actual_qty`, nên nó chỉ ghi sổ vị trí. Vì vậy nó không sinh phiếu kho, không đổi giá vốn,
không ảnh hưởng kế toán.

**Thủ kho (`Stock User`) lập, duyệt và huỷ được** — xếp hàng là việc hằng ngày.

---

## 7. Bốn báo cáo

| Báo cáo | Trả lời câu hỏi | Rỗng nghĩa là |
|---|---|---|
| **Tồn kho theo vị trí** | hàng nào đang ở ô nào (hiển thị dạng cây, gộp theo từng cấp) | kho trống |
| **Hàng chưa xếp vị trí** | việc cần dọn của thủ kho | đã xếp hết, tốt |
| **Đối soát tồn vị trí** | hệ có lệch không | **khớp, tốt** |
| **Hàng nằm sai vị trí** | ô nào đang chứa hàng khác với mặt hàng đã gán cho nó | **đúng chỗ hết, tốt** |

**Hai báo cáo cuối là báo cáo *sai lệch*, không phải báo cáo tồn kho.** Rỗng mới là tốt. Muốn
xem tồn thì mở *Tồn kho theo vị trí*.

> ### Vì sao cần *Hàng nằm sai vị trí* khi đã có *Đối soát*
>
> Hai cái soi hai thứ khác hẳn nhau, và cái này **không** thay được cái kia.
>
> *Đối soát* so **tổng** tồn theo ô với tồn kho ERPNext. Một ô chứa nhầm mặt hàng thì tổng vẫn
> đúng y nguyên — **đối soát không bao giờ thấy**. Nó khớp tuyệt đối trong khi kệ đã sai.
>
> Lúc **gán** vị trí, hệ đã chặn nếu vùng đó đang có hàng của mặt hàng khác. Nhưng đó là chặn
> **một lần**, lúc gán. Sau đó hàng vẫn vào sai ô được — qua phiếu xếp khai tay, qua huỷ chứng
> từ, qua kiểm kê. *Hàng nằm sai vị trí* là thứ duy nhất soi việc đó, và nên xem **hằng tuần**.

### Xem tồn theo Khu, theo Dãy

*Tồn kho theo vị trí* hiện **dạng cây và tự cộng dồn lên từng cấp**: mỗi nút Khu/Dãy/Khoang/
Tầng mang tổng của mọi ô lá bên dưới nó. Gấp nhánh lại là thấy số của cả khu.

```
1A                    50        ← cả Khu
   1A02               30           ← Dãy 02
      1A0201          30
         1A020101     30
            1A02010101  30        ← ô thật
   1A04               20           ← Dãy 04
      ...
```

> **Luôn lọc một mặt hàng trước khi đọc số ở cấp Khu.** Kho đang dùng **10 đơn vị tính** khác
> nhau (Hộp, Cái, Gói, Chai, Bộ, Cuộn, Đôi, Miếng, Túi, Lọ). Không lọc thì con số ở nút Khu là
> tổng của hộp cộng chai cộng đôi — **không trả lời được câu hỏi nào**. Lọc một mặt hàng rồi
> thì cùng đơn vị, con số mới có nghĩa.

Ba câu hỏi khác về cấp Khu — *khu nào còn chỗ trống*, *khu nào đang giữ bao nhiêu tiền hàng*,
*khu nào có hàng sắp hết hạn* — **chưa có báo cáo**, đang chờ làm.

### Khi đối soát có dòng

Đọc cột `loai`:

| Loại | Nghĩa | Làm gì |
|---|---|---|
| Lệch tồn | Tổng tồn các ô ≠ tồn kho ERPNext | Warehouse Location Setup → **"Đồng bộ lại"** |
| Ô âm | Có ô mang số lượng âm | **Không** bấm Đồng bộ lại — xem dưới |
| Lệch bộ đệm | Bộ nhớ đệm trôi khỏi sổ | xem dưới |

**"Đồng bộ lại" chỉ chữa được loại thứ nhất.** Với hai loại kia nó **cố ý ném lỗi** thay vì âm
thầm ghi đè — đó là dấu hiệu dữ liệu hỏng, không phải lệch thường. Khi đó gọi kỹ thuật chạy:

```
bench --site erptest.local execute erpnext.vi_tri_kho.vitri.so.dung_lai_ton_vi_tri \
  --kwargs "{'kho': 'Kho Miyano - MYN'}"
```

Hàm này xoá bộ đệm và cộng lại từ đầu từ sổ. Sổ không bao giờ bị sửa hay xoá — nó chỉ ghi thêm
— nên thao tác này an toàn, chạy lại bao nhiêu lần cũng được.

> **Đối soát khớp KHÔNG chứng minh cây vị trí đúng.** Nó chỉ so tổng số lượng với tồn kho; nó
> **không đọc cấu trúc cây**. Một ô gắn nhầm vào nhánh khác vẫn cho đối soát khớp. Muốn kiểm
> cấu trúc thì phải nhờ kỹ thuật kiểm thẳng, không nhìn báo cáo này mà kết luận.

---

## 8. Tắt và bật lại quản lý vị trí

**Tắt** (Warehouse Location Setup → "Tắt quản lý vị trí"): hệ ngừng ghi sổ cho kho đó. **Sổ cũ
giữ nguyên**, không xoá gì.

**Không bật thẳng lại được.** Trong lúc tắt, kho vẫn xuất nhập — nên tồn vị trí đứng yên trong
khi tồn kho đi tiếp. Phải bấm **"Đồng bộ lại"** trước: nó ghi bù phần chênh vào ô "Chưa xếp vị
trí" rồi mới cho bật lại. Đây là chặn cố ý, không phải lỗi.

---

## 9. Sáu điều dễ hiểu nhầm

**1. Ô "Chưa xếp vị trí" được lấy hàng SAU CÙNG, không phải trước.** Nó mang thứ tự lấy hàng
9999. Cùng hạn dùng thì hệ lấy từ ô đã xếp đàng hoàng trước — thủ kho biết đi tới đâu; chỉ khi
các ô thật cạn mới rút tới đống chưa xếp. Hàng ở đó vẫn là hàng thật, vẫn xuất bình thường.

**2. Ô "Chưa xếp vị trí" là ô hệ thống, mỗi kho đúng một ô** (mã `ZZZ-CHUA-XEP`). Không xoá
được, không đặt "Ngừng dùng" được — nó là **van an toàn**: mọi thứ không rõ vị trí rơi vào đó
thay vì làm hỏng số liệu. Đây là ô duy nhất không theo chuẩn 10 ký tự, và nó đứng **riêng**
ngoài cây — nên "Ngừng dùng" một nhánh thật không bao giờ vô tình kéo theo nó.

**3. Ô (hay cả nhánh) "Ngừng dùng" vẫn tính vào tồn, chỉ không được lấy hàng.** Nếu hàng chỉ
còn ở đó, phiếu xuất bị chặn kèm thông báo nói rõ ô nào đang giữ. Chuyển hàng ra, hoặc bật lại.

**4. "Ngừng dùng" một nhánh chỉ có tác dụng khi cây đã dựng xong.** Ngay sau khi cài hoặc phục
hồi trên một site mới, quản trị phải chạy một lần thao tác dựng lại cây (`bench migrate` tự làm
— xem `BAN-GIAO-nen-tang-vi-tri-kho.md`). Chưa chạy thì tích "Ngừng dùng" trên nút cha **không
chặn được gì** ở các ô lá bên dưới, dù giao diện vẫn cho tích bình thường. Trên `erptest.local`
bước này đã xong.

**5. "Đã gán vị trí" KHÔNG có nghĩa là "còn chỗ".** Gán chỉ nói *mặt hàng này thuộc vùng nào*;
nó không giữ chỗ trống nào cả. Một mặt hàng đã gán vẫn có thể không được gợi ý ô nào, vì vùng của
nó đã đầy. Khi đó phiếu xếp nói **"vùng ... đã đầy"** chứ không nói "chưa gán" — hai câu khác
nhau, hai việc khác nhau. Đọc nhầm rồi đi gán lại là mất công mà vùng vẫn hết chỗ.

**6. Ô đích hệ điền sẵn là GỢI Ý, không phải lệnh.** Sửa đè lúc nào cũng được, hệ không chặn.
Thủ kho đứng trước kệ biết những thứ hệ không biết — hàng cồng kềnh, kệ đang hỏng, lô sắp xuất
ngay. Ngược lại: **hệ cũng không tự sửa lại** cái bạn đã chọn.

---

## 10. Gán vị trí cố định cho mặt hàng

Từ 16/09/2026. Đây là thứ làm cho cột *Đến ô* ở mục 6.3 tự điền được.

**Ý tưởng:** mỗi mặt hàng có **một chỗ cố định** trên kệ, như kho SPD bên Nhật vẫn làm. Khi ô đã
thuộc về đúng một mặt hàng thì câu "hàng này xếp đâu" trả lời được ngay, **không cần khai sức
chứa cho ô nào** — đó là lý do trước đây hệ không dám gợi ý.

### 10.1 Gán một mặt hàng

1. Mở **`/app/item-location-preference`** (hoặc bấm **Gán vị trí cố định** trên trang *Vị trí kho*).
2. **Mặt hàng** — chọn một lần, **không sửa được về sau**. Gán nhầm thì xoá bản ghi rồi tạo lại.
3. **Kho** — phải là kho đang quản lý vị trí.
4. **Vị trí cố định** — gõ mã ô, hoặc bấm **"Chọn trên cây vị trí"** để chọn trực quan.

Ô **Cấp** tự hiện ra (Khu / Dãy / Khoang / Tầng / Ô) — chỉ để nhìn cho chắc, không gõ.

### 10.2 Nên gán ở cấp TẦNG, đừng gán một Ô lẻ

Chọn một **Tầng** nghĩa là **cả nhánh dưới nó** thuộc mặt hàng đó — mọi ô trong tầng.

Đây không phải lời khuyên cho đẹp. Luật gợi ý là *"ô trống đầu tiên"*, nên nếu gán vào **một Ô
lẻ**: lần nhập đầu hệ chỉ đúng ô đó; từ **lần nhập thứ hai** ô đã có hàng, không còn ô trống nào
khác trong "vùng" (vùng chỉ có một ô) — hệ sẽ gợi ý dồn tiếp vào chính ô đó cho tới khi kệ thật
sự không còn chỗ, và khi đó không còn đường nào khác để gợi ý.

Gán ở cấp Tầng cho mặt hàng chỗ để lớn lên.

### 10.3 Cây vị trí: vì sao có nút không chọn được

Cây hiện mỗi nốt kèm **số ô trống** và **số mặt hàng đang nằm** trong nhánh đó, để biết chỗ nào
còn rộng mà không phải mở ra đếm.

Nốt **không chọn được thì không có nút "Chọn"** — cố ý. Với 214 ô, bắt người dùng bấm thử rồi
đọc thông báo lỗi không phải là giao diện, đó là trò đoán mò. Ba lý do, ba việc khác nhau:

| Cây báo | Nghĩa là | Việc cần làm |
|---|---|---|
| *đã gán: `<mặt hàng>`* | nốt này, hoặc một nút trên nó, đã thuộc mặt hàng khác | chọn nhánh khác |
| *có gán bên trong* | bên trong nhánh này đã có mặt hàng khác giữ chỗ | gỡ gán con đó trước, hoặc chọn nhánh khác |
| *đang ngừng dùng* | nốt này hoặc một nút trên nó đang tắt | bật lại nhánh, hoặc chờ sửa kệ xong |

> **Một ô chỉ thuộc về một mặt hàng.** Hệ chặn cả ba chiều: gán trùng đúng nút, gán vào **con
> cháu** của nút đã có chủ, và gán vào **nút cha bao trùm** nút đã có chủ. Hai nhánh **cạnh
> nhau** thì không sao.

### 10.4 Hệ gợi ý ô theo luật nào

Khi bấm *"Lấy hàng chưa xếp"*, với mỗi mặt hàng đã gán:

1. Duyệt các ô trong vùng đã gán **theo thứ tự cây** (Khu → Dãy → Khoang → Tầng → Ô), bỏ qua ô
   nằm dưới nhánh đang ngừng dùng.
2. Lấy **ô trống đầu tiên**.
3. Hết ô trống thì lấy **ô đang chứa chính mặt hàng đó** (dồn vào chỗ cũ).
4. Không có cả hai → báo **"vùng `<nút>` đã đầy"**, để trống ô đích.

Gợi ý **không ép**. Sửa đè lúc nào cũng được.

### 10.5 Hai điều cần biết trước

**Không gán được nếu trong nhánh đang có hàng của mặt hàng khác.** Hệ nói rõ ô nào, mặt hàng nào,
bao nhiêu — chuyển những ô đó đi bằng phiếu xếp / chuyển vị trí rồi gán lại. Hôm nay gần như
không bao giờ gặp vì hàng còn nằm ở ô "Chưa xếp"; nó sẽ bắt đầu gặp khi kho đã xếp được một thời
gian.

**Một mặt hàng chỉ gán được ở MỘT kho.** Hôm nay vô hại vì chỉ `Kho Miyano - MYN` quản lý vị trí.
Ngày bật kho thứ hai, đây là chỗ phải sửa lược đồ — xem `BAN-GIAO-nen-tang-vi-tri-kho.md`.

**Đổi mã mặt hàng thì gán tự đi theo**, không phải gán lại.

---

## Phụ lục. Một lần chạy thật, từ mua hàng tới tồn theo ô

Chạy ngày 13/09/2026 trên `erptest.local`, mặt hàng `MYN-IMP-NEP-8` (Nẹp khoá 8 lỗ titan,
đơn vị Cái). Số chứng từ có thật, mở ra xem lại được.

**1. Nhập kho** — phiếu nhập `MAT-PRE-2026-00002`, 100 Cái, hai lô gõ tay kèm hạn dùng.
Không thao tác gì thêm, sổ vị trí tự ghi và **tự tách theo lô**:

```
ZZZ-CHUA-XEP   lô E2E-LO-GAN-2026   +60
ZZZ-CHUA-XEP   lô E2E-LO-XA-2028    +40
```

**2. Xếp vào ô** — hàng được đưa vào ba ô: `1A01010101` (25), `1A04040402` (35),
`1A02010101` (40). *(Lần chạy 13/09 này làm trước khi có Phiếu xếp vị trí nên phải ghi thẳng
vào sổ bằng lệnh. Từ 14/09 dùng phiếu — xem mục 6.3; phiếu thật đầu tiên là `XVT-2026-00001`,
xếp 1.500 đơn vị của 5 mặt hàng từ ô "Chưa xếp vị trí" vào 5 ô thật.)*

**3. Xuất kho** — hai phiếu giao, mỗi phiếu chứng minh một điều:

| Phiếu | Xuất | Điều nó cho thấy |
|---|---|---|
| `MAT-DN-2026-00053` | 30 Cái, để hệ tự chọn | hệ **bỏ qua lô sắp hết hạn**, lấy hai lô hạn 2028 — xem mục 6.2 |
| `MAT-DN-2026-00054` | 40 Cái, chỉ định lô | hệ lấy **ô gần cửa trước** (thứ tự 1), cạn rồi mới tới ô xa (thứ tự 128) |

**4. Kiểm lại** — cả ba phép kiểm đều sạch:

```
Đối soát tồn vị trí:        0 dòng lệch, 0 ô âm, 0 lệch bộ đệm
Bin của ERPNext:            50 Cái
Tổng tồn các ô vị trí:      50 Cái        ← khớp
```

**5. Tồn theo cấp** — báo cáo *Tồn kho theo vị trí*, lọc đúng mặt hàng này:

```
1A                       50    [NHÓM]
   1A02                  30    [NHÓM]
      1A0201             30    [NHÓM]
         1A020101        30    [NHÓM]
            1A02010101   30
   1A04                  20    [NHÓM]
      1A0404             20    [NHÓM]
         1A040404        20    [NHÓM]
            1A04040402   20
```

Tổng nút Khu `1A` = 50 = đúng tổng hai ô lá bên dưới.

---

## Tài liệu liên quan

| File | Cho ai |
|---|---|
| `BAN-GIAO-nen-tang-vi-tri-kho.md` | kỹ thuật — kiến trúc, cách bảo trì, cách merge ERPNext bản mới |
| `../superpowers/specs/2026-09-15-gan-vi-tri-co-dinh-theo-mat-hang-design.md` | kỹ thuật — thiết kế phần gán vị trí cố định (mục 10) và những chỗ cố ý KHÔNG làm |
| `QUYET-DINH-thi-cong-cay-vi-tri.md` | chủ dự án — những chỗ tự chốt trong lúc làm và cái giá nếu chốt sai |

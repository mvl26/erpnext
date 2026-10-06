# Hướng dẫn sử dụng — App PDA kho Miyano

Tài liệu cho **trưởng kho** (cấp/thu hồi thẻ, giao máy, cài app lên máy quét
mới) và **thủ kho** (dùng app hằng ngày). Tài liệu kỹ thuật cho người dựng lại
APK nằm ở `pda_app/README.md`.

App PDA **mang sẵn giao diện trong máy**. Mở app là màn hình hiện ra ngay,
không tải gì từ máy chủ; chỉ dữ liệu (lô, ô, phiếu) mới đi hỏi máy chủ. Vì vậy
app **không còn là một cửa sổ trình duyệt** như bản cũ: không thanh công cụ ERP,
không lạc được sang Desk, và mạng chập một nhịp thì chỉ chậm chứ không trắng màn.

> **Tài liệu này mô tả app ĐỜI MỚI (từ 25/09/2026).** Bản cũ có một màn "khai
> máy chủ" với nút **Kiểm tra & lưu** và nút **Đổi máy chủ**; đời mới **không
> còn hai màn/nút đó** — địa chỉ máy chủ được nướng vào bản cài lúc đóng gói.
> Ai còn cầm bản cũ thì đọc lại mục 3 để cài đè bản mới.

---

## 1. Cấp thẻ

Thẻ PDA là một mã vạch in trên giấy. Cấp thẻ là **hai bước**, không gộp được:

1. Vào **PDA Badge** (danh sách) → **New** → chọn **Người dùng** → **Save**.
   Bước này chỉ tạo bản ghi thẻ, **chưa sinh mã**; nút "Cấp thẻ & in" chỉ hiện
   sau khi bản ghi đã được lưu.
2. Mở lại đúng bản ghi vừa lưu → bấm **Cấp thẻ & in**. Lúc này hệ mới sinh mã
   thật, mở cửa sổ in tem, rồi **quên mã đó ngay** — máy chủ chỉ giữ một bản
   băm có muối, không giữ mã gốc.

Dán tem vừa in vào bao nhựa, giao cho đúng người trên bản ghi.

**Mã chỉ hiện đúng lúc in, không xem lại được.** Nếu cửa sổ in bị chặn, bản ghi
thẻ vẫn đã đổi mã (mã cũ đã chết) mà tem chưa in ra — bấm **Cấp thẻ & in** thêm
lần nữa sau khi cho phép pop-up. Cấp lại là việc bình thường.

Người được cấp thẻ phải có vai trò kho (`Stock User` trở lên) và tài khoản đang
mở, nếu không hệ báo ngay lúc lưu/cấp.

## 2. Mất thẻ

Nghi thẻ bị mất, bị lộ, hoặc người cầm thẻ nghỉ việc: mở đúng bản ghi
**PDA Badge** của người đó → **Thu hồi thẻ** → xác nhận.

Thu hồi làm hai việc cùng lúc:
- Thẻ ngừng quét được ngay, và mọi chiếc máy đứng tên người đó bị hạ khỏi danh
  sách máy còn hiệu lực — từ đó máy chủ **từ chối** mọi lời gọi của chúng.
- Hệ **cố gắng** xoá luôn chiếc khoá API của tài khoản đó.

> **XOÁ KHOÁ KHÔNG PHẢI LÚC NÀO CŨNG XẢY RA — đọc câu hệ báo lại.** Hệ chỉ xoá
> chiếc khoá **do PDA cấp**. Nếu tài khoản đó đang mang một khoá API **không
> phải của PDA** (một tích hợp khác, một script), hệ **giữ nguyên** khoá đó và
> hiện một hộp tên **"Khoá API vẫn còn"** nói rõ lý do. Máy quét vẫn chết (vì
> hàng rào mã máy đã từ chối nó), nhưng **chiếc khoá thì còn sống** — nếu nó
> từng bị lộ, phải vào **User** của người đó và xoá tay.
>
> Thấy hộp "Khoá API vẫn còn" mà không hiểu vì sao thì **đừng bỏ qua** — gọi kỹ
> thuật. Đó là một câu nói đúng sự thật, không phải một lời nhắc thừa.

Thu hồi xong, cấp thẻ mới theo mục 1 nếu người đó còn cần dùng PDA.

## 3. Cài app

Không cần cáp, không cần máy tính: máy quét tự tải bản cài từ chính hệ thống.

**Trưởng kho làm một lần, mỗi khi kỹ thuật dựng bản mới:**

1. Vào **Quản lý kho › Cài app PDA**.
2. Bấm **Đưa bản cài lên**, chọn file APK kỹ thuật gửi. **Giữ nguyên tên file
   dạng `miyano-pda-1.0-release.apk`** — app trong máy đọc con số trong tên này
   để biết mình có phải bản mới nhất không (mục 6). Đổi tên thành "ban cai
   moi.apk" là tắt mất lời nhắc trên mọi máy.
3. File phải để **công khai** — máy quét lúc chưa cài app thì chưa đăng nhập
   được, file riêng tư sẽ không tải nổi.
4. Trang hiện lại tên file, dung lượng, ngày đưa lên — đó là bản đang phát hành.

**Trên từng máy quét:**

1. Mở trình duyệt, gõ địa chỉ kho kèm `/tai-app` (địa chỉ đúng hiện sẵn ở trang
   **Cài app PDA**, khỏi nhớ).
2. Bấm **Tải bản cài**.
3. Bật quyền "Cài từ nguồn không rõ" cho trình duyệt khi máy hỏi, rồi mở file
   vừa tải và bấm Cài đặt.
4. Mở app **Miyano PDA** → ra thẳng màn quét thẻ. **Không phải khai địa chỉ máy
   chủ** — địa chỉ đã nằm sẵn trong bản cài.

> Bản cài để **công khai**: ai trong mạng biết đường dẫn đều tải được, và bên
> trong file APK có địa chỉ máy chủ của kho. Không có mật khẩu hay khoá nào
> trong đó. Đây là cái giá để cài được cho nhiều máy mà không cần cáp — chủ đầu
> tư đã chốt ngày 23/09/2026.

> **Chỉ đưa lên bản đã trỏ đúng máy chủ thật.** Bản dựng để thử trỏ vào máy chủ
> thử; thủ kho cài nhầm bản đó thì mọi thao tác ghi vào dữ liệu thử. Dấu hiệu
> nhìn thấy ngay: **bản thử hiện một dải CAM "BẢN THỬ — KHÔNG phải máy chủ
> thật"** trên màn quét thẻ và màn menu. Thấy dải cam trên máy phát cho kho là
> **dừng lại**, báo kỹ thuật. Bản thật không có dải đó.

## 4. Nhận máy — quét thẻ MỘT LẦN, không phải mỗi ca

Đây là chỗ khác lớn nhất so với bản cũ.

**Lần đầu (trưởng kho giao máy cho một người):**

1. Mở app → màn quét thẻ.
2. Người nhận máy quét thẻ của mình bằng súng quét.
3. App đổi tấm thẻ lấy một **khoá máy** và cất khoá đó **trong máy**. Vào thẳng
   menu bốn việc, có tên người nhận.

**Từ lần sau:** chạm icon là **vào thẳng menu**. Không quét thẻ nữa, không có
mốc "12 tiếng", không bị đá ra giữa ca. Màn quét thẻ chỉ hiện lại khi khoá máy
bị giết — tức là khi trưởng kho thu hồi (mục 2/5), hoặc khi có người bấm
**Đăng xuất**.

**Đổi ca, đổi người cầm máy:** người đang cầm bấm **Đăng xuất** ở màn menu →
máy trả về màn quét thẻ → người ca sau quét thẻ của mình. Không bấm Đăng xuất
thì máy vẫn đứng tên người cũ, và mọi việc ghi trên máy đó mang tên người cũ.

**Một chiếc máy đứng tên đúng một người tại một lúc.** Danh sách máy nào đang
đứng tên ai xem ở **PDA Thiet Bi** trên web.

> **Bản Desk (bốn trang cũ — Xếp hàng, Lấy hàng, Quét mã tra cứu, Đặt ô hàng
> loạt) vẫn còn nguyên trên máy chủ**, không bị xoá và không đổi. Ai dùng **máy
> tính** (bàn phím, màn hình lớn, đăng nhập tài khoản thường qua trình duyệt)
> vẫn mở được y như trước — ví dụ để đặt ô hàng loạt, việc vốn thiết kế cho máy
> tính. Trang `/kho` trên web cũng còn, và vẫn quét thẻ **mỗi ca** như cũ (phiên
> 12 tiếng): đường "quét một lần" chỉ có trong app. App trên máy quét chỉ không
> còn ĐI QUA các trang đó nữa.

## 5. Mất máy thì làm gì

Máy quét thất lạc, bị lấy, hoặc nhân viên nghỉ việc mang máy theo.

**Làm ngay, theo thứ tự:**

1. Vào **PDA Badge**, mở bản ghi thẻ của người đang cầm chiếc máy đó → bấm
   **Thu hồi thẻ**. Đây là đường giết máy; không có nút nào khác làm được việc
   này. **Đọc câu hệ báo lại** — nếu hiện hộp **"Khoá API vẫn còn"** thì chiếc
   khoá API của tài khoản đó **chưa bị xoá** (mục 2 nói rõ vì sao), và phải xử
   lý tiếp bằng tay.
2. Nếu người đó còn cần làm việc: cấp thẻ mới (mục 1) và giao cho họ một máy
   khác.
3. Muốn biết chiếc máy nào đang đứng tên ai trước khi thu hồi: **PDA Thiet Bi**
   trên web (tên máy, mã máy, người đang cầm, lần dùng cuối).

**Sau bao lâu thì chiếc máy đó chết?**

Câu trả lời trung thực: **ngay lần nó gọi máy chủ kế tiếp — không phải sau một
số phút định sẵn.** Không có đồng hồ đếm ngược nào cả.

- Người cầm máy chạm bất cứ việc gì cần dữ liệu (quét một lô, mở danh sách
  phiếu, ghi một thùng): lời gọi đó bị máy chủ từ chối, app **xoá khoá trong
  máy** và quay về màn quét thẻ, kèm câu báo của máy chủ. Từ lúc đó máy là một
  chiếc máy trắng.
- Chiếc máy **để yên trong túi**, hoặc **không có mạng**, thì nó chưa biết gì:
  màn hình cuối cùng vẫn còn đó. Nhưng nó **không làm được việc gì mới** — mọi
  việc đều phải hỏi máy chủ. Nó không ghi được một dòng nào vào kho.
- Máy **không có mạng vĩnh viễn** thì vẫn cứ là máy trắng: dữ liệu nghiệp vụ
  nằm ở máy chủ, trong máy không có gì để đọc.

**Thu hồi rồi thì bản thân chiếc máy có nguy hiểm không?** Trong máy có một
chuỗi khoá, một mã máy, và tên người cầm máy. Không có mật khẩu, không có dữ
liệu kho.

Nói cho đúng: chuỗi khoá đó **thường** đã chết, nhưng **không phải luôn luôn** —
xem hộp "Khoá API vẫn còn" ở mục 2. Và **mã máy nằm cùng chỗ với chuỗi khoá**
trong bộ nhớ của app: ai đọc được một thứ thì đọc được cả hai. Vì vậy hàng rào
"khoá chỉ dùng được từ đúng chiếc máy" chặn ca **chuỗi khoá rò ra ngoài chiếc
máy** (ảnh chụp màn hình, bản sao lưu, nhật ký) — nó **không** chặn ca ai đó có
trong tay nguyên chiếc máy. Ca mất nguyên máy do **Thu hồi thẻ** lo, và đó là lý
do bước 1 phải làm ngay.

## 6. Có bản cài mới

Khi kỹ thuật dựng bản mới và trưởng kho đưa lên hệ thống (mục 3), màn menu của
các máy đang dùng sẽ hiện một **dải xanh** *"Đã có bản cài mới X (máy đang dùng
Y)"* kèm nút **Mở trang tải**.

- App **không tự tải, không tự cài**. Bấm nút thì trình duyệt của máy mở trang
  `/tai-app`; từ đó làm tiếp như mục 3 bước 2–3.
- Cài đè lên bản cũ **không mất khoá máy**: cài xong mở app vẫn vào thẳng menu.
- Không thấy dải nhắc dù kỹ thuật đã đưa bản mới lên: gần như chắc chắn là
  **tên file APK bị đổi** (mục 3 bước 2) — app không đọc ra được con số phiên
  bản thì nó im, cố ý, thay vì nhắc bừa.

## 7. Đổi máy chủ

**Việc của kỹ thuật, không phải việc làm ở kho.** Địa chỉ máy chủ nằm trong
chính bản cài; đổi máy chủ nghĩa là **dựng lại APK và cài lại**. Xem
`pda_app/README.md`.

**Một ngoại lệ, và chỉ một:** nếu đường vào kho là một **đường hầm** (ngrok) và
đường hầm đó rớt, thì **mọi máy quét chết cùng một lúc** — dựng lại APK rồi đi
cài từng chiếc giữa ca là không kịp. Cho đúng ca đó, app có một **lối ẩn**:
**bấm giữ logo MIYANO ở màn quét thẻ trong 3 giây** → hiện ô nhập địa chỉ máy
chủ → gõ địa chỉ mới → **Lưu và mở lại**.

- Lối này **không dành cho thủ kho** và không nằm trong luồng thường. Chỉ dùng
  khi kỹ thuật đọc địa chỉ cho.
- Chỉ nhận địa chỉ **`https://…`** (ví dụ địa chỉ ngrok), hoặc `http://` tới
  đúng hai địa chỉ nội bộ đã khai sẵn lúc dựng APK. Gõ một địa chỉ `http://`
  khác thì app **từ chối ngay kèm lý do** — vì Android chặn nó ở tầng dưới, và
  nếu không từ chối ở đây thì triệu chứng y hệt "máy chủ chết".
- Chỉ nhập tới **tên miền và cổng**, bỏ phần sau dấu `/`.
- Gõ nhầm thì mở lại lối ẩn và bấm **Bỏ địa chỉ gõ tay** để quay về địa chỉ gốc
  của bản cài. Lối ẩn không cần mạng nên luôn mở được.
- Sau khi lưu, đối chiếu dòng **"Máy chủ:"** ở cuối màn quét thẻ — nó in đúng
  địa chỉ mà app đang thật sự gọi.

## 8. Sự thật về bảo mật — đọc kỹ trước khi giao thẻ cho ai

**Một tấm thẻ quét được là một chiếc chìa khoá thật.** Ai chụp được ảnh mã vạch
trên thẻ và in lại được là vào hệ thống với đúng quyền của chủ thẻ.

- Bảo quản thẻ như bảo quản chìa khoá kho — không để hớ hênh, không chụp ảnh
  gửi qua chat, không dán ở chỗ ai cũng chụp được.
- **Nghi thẻ bị mất, bị lộ, hoặc bị chụp lại là thu hồi ngay** (mục 2). Thu hồi
  rồi cấp lại tốn một phút; chờ xác minh mà thẻ đã lộ thật thì có người khác
  vào được hệ thống trong lúc chờ.
- **Khoá máy trong app KHÔNG phải một phiên trình duyệt** (đây là chỗ khác bản
  cũ): nó là một khoá API gắn với một **mã máy**, và máy chủ từ chối mọi lời gọi
  mang khoá ấy mà không kèm đúng mã máy.
  **Nhưng mã máy KHÔNG phải một bí mật, và KHÔNG phải "Android ID".** Nó là một
  chuỗi app tự sinh lần đầu (`pda-…`) và **cất cùng một chỗ với chuỗi khoá**
  trong bộ nhớ của app. Nên câu "chép chuỗi khoá sang máy khác không dùng được"
  chỉ đúng khi chép **riêng** chuỗi khoá — một lượt đọc sạch bộ nhớ app lấy
  **cả hai**, và khi đó chiếc khoá dùng được ở nơi khác.
  Lớp này vì vậy chặn ca **khoá rò ra ngoài chiếc máy** (ảnh chụp màn hình, bản
  sao lưu, nhật ký lỗi) và ca **máy đã thu hồi**; nó **không** chặn ca mất
  nguyên chiếc máy vào tay người biết việc. Ca đó chỉ có **Thu hồi thẻ** chặn
  được — xem mục 5.
- **Nhưng tài khoản đứng sau vẫn là tài khoản đầy đủ quyền.** Ai lấy được
  chính tấm THẺ (không phải chiếc máy) thì vào được `/kho` trên web, và phiên
  web đó là phiên Frappe bình thường. Vì vậy:
  **TUYỆT ĐỐI không cấp thẻ PDA cho tài khoản có vai trò `System Manager`.**
  Chỉ cấp cho tài khoản `Stock User`/`Stock Manager`.

## 9. Sự cố hay gặp

| Sự cố | Cách xử lý |
|---|---|
| Mở app ra màn quét thẻ dù hôm qua vẫn vào thẳng menu | Khoá máy đã bị giết: trưởng kho vừa thu hồi thẻ, hoặc có người bấm **Đăng xuất**. Quét thẻ lại (nếu thẻ còn hiệu lực) hoặc hỏi trưởng kho |
| Quét thẻ báo "Máy chưa được cấp quyền…" hoặc "Thẻ không dùng được" | Hỏi trưởng kho: thẻ còn hiệu lực không, tài khoản có bị khoá không, còn vai trò kho không. Ba lý do đó cho ra câu báo gần giống nhau — phải tra trên web |
| Dải **CAM "BẢN THỬ"** trên màn quét thẻ/menu | Máy đang cầm bản trỏ vào **máy chủ thử**. Dừng dùng, báo kỹ thuật — mọi thao tác đang ghi vào dữ liệu thử |
| Dải **CAM "Giờ máy lệch…"** | Đồng hồ máy sai. Không chặn việc (hạn dùng vẫn tính theo giờ máy chủ), nhưng báo kỹ thuật chỉnh lại giờ |
| Dải **XÁM "Chưa lấy được giờ hệ thống"** | App chưa hỏi được giờ máy chủ; **chip hạn dùng tạm ẩn**. Kiểm wifi; kéo dài thì báo kỹ thuật |
| "Mất kết nối. Kiểm tra wifi rồi thử lại." | Máy không với tới máy chủ: kiểm wifi trước. Wifi tốt mà vẫn vậy thì báo kỹ thuật (có thể đường hầm đã rớt — mục 7) |
| Màn "Đặt ô trên tem" chật, khó thao tác | Việc này vốn thiết kế cho máy tính — mở bằng trình duyệt trên máy tính, đăng nhập tài khoản thường (mục 4) |
| Cửa sổ in tem không mở ra khi cấp thẻ | Trình duyệt đang chặn pop-up — cho phép rồi bấm "Cấp thẻ & in" lại (mục 1) |

---

## Bảng kiểm tay cho chủ đầu tư

Dùng để tự thử APK vừa dựng trên một máy PDA hoặc điện thoại Android thật,
trước khi phát cho kho dùng đại trà.

**Chốt chặn BẮT BUỘC trước dòng #1.** Bản dựng từ kho mã nguồn **luôn** trỏ vào
site thử. Trước khi dựng APK để giao cho kho dùng thật, kỹ thuật phải: (a) sửa
**cả hai** khoá `may_chu` và `may_chu_phat_hanh` trong
`scripts/pda/cau-hinh-may-chu.json` sang địa chỉ máy chủ thật; (b) dựng lại
theo `pda_app/README.md`; (c) chạy `apksigner verify --print-certs` và xác nhận
in ra đúng `CN=Miyano PDA, …`; (d) **mở app lên và xác nhận KHÔNG còn dải cam
"BẢN THỬ"**. Dải cam còn hiện nghĩa là bước (a) làm thiếu một nửa.

| # | Việc | Kỳ vọng |
|---|---|---|
| 1 | Cài APK, mở app | Ra thẳng màn quét thẻ. **Không** hỏi địa chỉ máy chủ. Không dải cam "BẢN THỬ" |
| 2 | Đọc dòng "Máy chủ:" ở cuối màn quét thẻ | Đúng địa chỉ máy chủ THẬT |
| 3 | Quét thẻ của mình | Vào menu bốn nút, hiện đúng tên mình |
| 4 | **Đóng app, mở lại** | Vào **thẳng menu**, không hỏi thẻ nữa |
| 5 | Xếp một thùng | Quét lô, quét ô, ghi xong; mở web thấy ngay phiếu xếp |
| 6 | Lấy một phiếu giao | Quét lô, quét ô, chọn đơn vị, số kiện; web thấy ngay |
| 7 | Tắt wifi rồi thao tác | Câu tiếng Việt "Mất kết nối. Kiểm tra wifi rồi thử lại." — không phải trang lỗi của Chrome, không phải chữ tiếng Anh |
| 8 | Thu hồi thẻ trên web khi PDA đang mở, rồi thao tác tiếp trên PDA | PDA quay về màn quét thẻ kèm câu nói rõ nguyên nhân — **không phải** màn đăng nhập Desk (ô Email/Mật khẩu) |
| 9 | Sau bước 8, đóng app rồi mở lại | Vẫn ở màn quét thẻ (khoá đã chết thật, không sống lại) |
| 10 | Bấm **Đăng xuất** ở menu | Về màn quét thẻ; mở lại app vẫn ở màn quét thẻ |
| 11 | Mở `/app/lay-hang-pda` trên máy tính | Bản Desk vẫn chạy như cũ |

Bảng kiểm dành cho **máy thật** (những thứ chỉ máy thật trả lời được — cookie
sau nâng cấp tại chỗ, HTTPS thật, mất sóng giữa chừng, nút Back cứng, đồng hồ
máy sai, lối ẩn) nằm ở `HDSD-thu-app-pda-tren-may-that.md`.

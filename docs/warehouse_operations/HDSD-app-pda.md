# Hướng dẫn sử dụng — App PDA kho Miyano

Tài liệu cho **trưởng kho** (cấp/thu hồi thẻ, cài app lên máy quét mới) và
**thủ kho** (dùng app hằng ngày). Tài liệu kỹ thuật cho người dựng lại APK nằm
ở `pda_app/README.md`.

App PDA là một vỏ Android rỗng — một cửa sổ WebView chỉ mở được đúng máy chủ
Miyano ERP đã khai. Mọi nghiệp vụ (quét thẻ, xếp hàng, lấy hàng, tra cứu, đặt
ô hàng loạt) chạy trên máy chủ, giống hệt mở bằng trình duyệt; app chỉ đỡ việc
phải gõ địa chỉ và mở trình duyệt mỗi lần.

---

## 1. Cấp thẻ

Thẻ PDA là một mã vạch in trên giấy — thủ kho quét mã đó ở màn `/pda` để vào
hệ thống, không cần gõ tài khoản/mật khẩu trên súng quét.

Cấp thẻ là **hai bước**, không gộp được thành một:

1. Vào **PDA Badge** (danh sách) → **New** → chọn **Người dùng** → **Save**.
   Bước này chỉ tạo bản ghi thẻ, **chưa sinh mã** và nút "Cấp thẻ & in" chưa
   hiện ra (nút chỉ hiện sau khi bản ghi đã được lưu).
2. Mở lại đúng bản ghi vừa lưu → bấm **Cấp thẻ & in**. Lúc này hệ mới sinh mã
   thật, mở cửa sổ in tem, rồi **quên mã đó ngay** — máy chủ chỉ giữ lại một
   bản băm (SHA-256), không giữ mã gốc.

Dán tem vừa in vào bao nhựa, giao cho đúng người trên bản ghi.

**Mã chỉ hiện đúng lúc in, không xem lại được.** Nếu cửa sổ in bị trình duyệt
chặn, bản ghi thẻ vẫn đã đổi mã (mã cũ đã chết) mà tem chưa in ra — bấm
**Cấp thẻ & in** thêm lần nữa sau khi cho phép pop-up; cấp lại vốn là việc
bình thường, không có gì phải lo khi phải cấp lại.

Người được cấp thẻ phải có vai trò kho (`Stock User` trở lên) và tài khoản
đang mở, nếu không hệ báo ngay lúc lưu/cấp, không đợi tới lúc quét thẻ mới báo.

## 2. Mất thẻ

Nghi thẻ bị mất, bị lộ, hoặc người cầm thẻ nghỉ việc: mở đúng bản ghi
**PDA Badge** của người đó → bấm **Thu hồi thẻ** → xác nhận.

Thu hồi làm hai việc cùng lúc:
- Thẻ ngừng quét được ngay (mã băm cũ không còn khớp bản ghi còn hiệu lực).
- **Phiên đang mở trên PDA bị đóng ngay lập tức** — nếu đúng lúc đó có người
  đang cầm máy quét dùng thẻ này, thao tác tiếp theo trên máy đó sẽ bị đòi
  quét thẻ lại.

Thu hồi xong, cấp thẻ mới theo mục 1 nếu người đó còn cần dùng PDA.

## 3. Cài app

1. Chép file `app-release.apk` sang máy PDA (USB, hoặc gửi qua kênh nội bộ —
   không đăng lên Google Play, app chỉ dùng nội bộ).
2. Trên máy PDA, bật quyền "Cài từ nguồn không rõ" (Install unknown apps) cho
   trình duyệt/ứng dụng quản lý file dùng để mở file APK.
3. Mở file APK, bấm Cài đặt.
4. Mở app **Miyano PDA** lần đầu → hiện màn khai máy chủ → gõ hoặc giữ nguyên
   địa chỉ mặc định → bấm **Kiểm tra & lưu**. App tự thử nối máy chủ; nối được
   thì vào thẳng màn quét thẻ (`/pda`).

## 4. Dùng hằng ngày

Mở app → màn quét thẻ hiện ra → quét thẻ của mình bằng súng quét → vào menu
bốn nút (**Xếp hàng vào ô**, **Lấy hàng**, **Quét mã tra cứu**, **Đặt ô trên
tem**) → chọn việc cần làm.
Xong việc bấm **Đăng xuất** để quay về màn quét thẻ cho người ca sau dùng
chung máy.

Phiên đăng nhập sống **12 tiếng** kể từ lúc quét thẻ. Hết 12 tiếng, màn hình
tự đá về `/pda` — quét thẻ lại là vào tiếp, không cần làm gì khác.

**Hạn phiên thật là cái nào tới TRƯỚC**, không phải luôn luôn 12 tiếng: Frappe
còn một hạn phiên riêng của site, ở **System Settings → Session Expiry**
(định dạng `giờ:phút`). Trên `erptest.local` giá trị này đang là `170:00`
(hơn 7 ngày) — lớn hơn 12 tiếng rất nhiều, nên trên site thử, mốc 12 tiếng của
thẻ luôn là cái chặn trước. **Trên máy chủ thật, kiểm lại giá trị này** —
nếu ai đó từng đặt `Session Expiry` ngắn hơn 12 tiếng cho mục đích khác, thủ
kho sẽ bị đòi quét thẻ lại SỚM HƠN 12 tiếng, và mục 4 ở trên sẽ không còn đúng.

## 5. Đổi máy chủ — việc của kỹ thuật, không phải việc tự làm ở kho

**Đừng tự đổi máy chủ sang một địa chỉ mạng nội bộ khác bằng nút "Đổi máy chủ"
trong app.** Đây từng là một cái bẫy: file cấu hình mạng của app
(`network_security_config.xml`) chỉ mở kết nối HTTP (không mã hoá) cho ĐÚNG
hai địa chỉ đã khai sẵn lúc dựng APK — gõ một địa chỉ nội bộ khác, dù đúng
định dạng IP, sẽ bị **hệ điều hành Android chặn ở tầng mạng**, trước khi app
kịp làm gì. App chỉ báo được đúng một câu chung "Không nối được máy chủ. Kiểm
tra wifi..." — không có cách nào phân biệt "gõ sai địa chỉ", "mất wifi", hay
"địa chỉ đúng nhưng chưa được khai trong `network_security_config.xml`" từ màn
hình đó. Kết quả thật đã xảy ra: trưởng kho đi kiểm wifi cả buổi trong khi
nguyên nhân là địa chỉ mới chưa được mở ngoại lệ mạng.

Nút "Đổi máy chủ" trên màn hình chờ kết nối chỉ an toàn dùng để **sửa lại
đúng địa chỉ đã được kỹ thuật khai báo sẵn** (ví dụ gõ nhầm một ký tự) — không
dùng để trỏ sang một máy chủ hoàn toàn mới.

**Đổi sang một máy chủ MỚI (ví dụ từ máy thử sang máy chủ thật) là việc của
kỹ thuật**, gồm ba bước bắt buộc, không làm được từ màn hình app: sửa
`network_security_config.xml` (mở ngoại lệ HTTP cho địa chỉ mới, nếu địa chỉ
đó không chạy HTTPS) + sửa hằng `MAC_DINH` trong `www/index.html`, rồi
**dựng lại APK** và cài lại trên từng máy quét. Chi tiết đầy đủ (kể cả luật
khớp `allowNavigation` hay bị hiểu nhầm) nằm ở `pda_app/README.md`, mục "Đổi
địa chỉ máy chủ mặc định" — đọc đúng tài liệu đó, đừng đoán.

## 6. Sự thật về bảo mật — đọc kỹ trước khi giao thẻ cho ai

**Một tấm thẻ quét được là một chiếc chìa khoá thật, không hơn không kém.**
Ai chụp được ảnh mã vạch trên thẻ (kể cả chụp bằng điện thoại từ xa) và in lại
được là vào hệ thống với đúng quyền của chủ thẻ — hệ thống không có cách nào
phân biệt "thẻ thật" với "ảnh chụp lại của thẻ thật".

Vì vậy:
- Bảo quản thẻ như bảo quản chìa khoá kho — không để thẻ hớ hênh trên bàn,
  không chụp ảnh thẻ gửi qua chat nội bộ, không dán thẻ ở chỗ ai cũng chụp
  được.
- **Nghi thẻ bị mất, bị lộ, hoặc bị chụp lại là thu hồi ngay** (mục 2), đừng
  đợi xác minh chắc chắn mới thu hồi — thu hồi rồi cấp lại tốn một phút, còn
  chờ xác minh mà thẻ đã lộ thật thì có người khác vào được hệ thống trong
  lúc chờ.
- **Quét thẻ tạo ra một phiên đăng nhập Frappe BÌNH THƯỜNG, đầy đủ quyền của
  chủ thẻ — không phải một phiên bị giam trong bốn màn hình kho.** Và khác
  với điều tài liệu này từng viết, **không cần "tự gõ đường dẫn" gì cả**:
  menu sau khi quét thẻ (`/app/pda-home`) VỐN LÀ một trang Desk bình thường
  của Frappe, mang nguyên thanh công cụ trên cùng của Desk — ô "Search or
  type a command", logo (bấm vào là về thẳng `/app`), chuông thông báo, và
  menu avatar góc phải. **Một cú chạm vào bất kỳ thứ nào trong thanh đó là
  vào thẳng Desk đầy đủ, với đúng quyền thật của tài khoản** — không cần gõ
  gì, không có lớp chặn nào ở giữa. Vì vậy:
  **TUYỆT ĐỐI không cấp thẻ PDA cho tài khoản có vai trò `System Manager`.**
  Thẻ của một tài khoản `System Manager` mà rơi vào tay người ngoài thì người
  đó có toàn quyền quản trị hệ thống, không chỉ mấy màn hình kho. Chỉ cấp thẻ
  cho tài khoản `Stock User`/`Stock Manager` dùng đúng việc kho.

## 7. Sự cố hay gặp

| Sự cố | Cách xử lý |
|---|---|
| Không nối được máy chủ (hiện câu báo "Không nối được máy chủ..." kèm ô nhập địa chỉ đã điền sẵn và nút **Kiểm tra & lưu** — **không** có nút "Đổi máy chủ" ở màn này, nút đó chỉ hiện thoáng qua ở màn "đang nối" trước đó; và không phải trang lỗi của Chrome) | Kiểm wifi của máy PDA còn bắt được mạng nội bộ không; kiểm địa chỉ máy chủ gõ đúng chưa (sửa trong ô đang hiện sẵn rồi bấm lại Kiểm tra & lưu — mục 5); nếu wifi và địa chỉ đều đúng mà vẫn không nối được, báo kỹ thuật kiểm máy chủ |
| Quét thẻ báo "Thẻ không dùng được — báo trưởng kho" | Hỏi trưởng kho: thẻ còn hiệu lực không (có bị thu hồi không), tài khoản gắn thẻ có bị khoá không, tài khoản còn giữ vai trò kho không. Thẻ hỏng vì bất kỳ lý do nào trong ba lý do trên đều hiện đúng một câu này — không phân biệt được lý do nào từ màn hình PDA, phải tra trên web |
| Màn "Đặt ô trên tem" (đặt ô hàng loạt) hiện chật, khó thao tác trên máy PDA | Việc này vốn thiết kế để dùng trên máy tính (bàn phím, màn hình lớn) — mở cùng địa chỉ máy chủ bằng trình duyệt trên máy tính, đăng nhập bằng tài khoản thường (không phải quét thẻ) |
| Cửa sổ in tem không mở ra khi cấp thẻ | Trình duyệt đang chặn pop-up cho trang này — cho phép pop-up rồi bấm "Cấp thẻ & in" lại (xem mục 1) |
| Để máy qua 12 tiếng không dùng | Bình thường — mở lại app phải quét thẻ lại, không phải lỗi (mục 4) |

---

## Bảng kiểm tay cho chủ đầu tư

Bảng dưới dùng để tự thử APK vừa dựng trên một máy PDA hoặc điện thoại
Android thật, trước khi phát cho kho dùng đại trà.

**Chốt chặn BẮT BUỘC trước dòng #1 — không có gì tự động ngăn việc phát nhầm
một APK đang trỏ vào site THỬ:** hằng `MAC_DINH` trong `pda_app/www/index.html`
mặc định trỏ `http://192.168.61.129:8003` — đúng địa chỉ site thử
`erptest.local`, KHÔNG phải máy chủ thật. Trước khi dựng APK để giao cho kho
dùng thật: (a) sửa `MAC_DINH` sang địa chỉ máy chủ thật, (b) dựng lại APK theo
`pda_app/README.md`, (c) chạy `apksigner verify --print-certs` trên file vừa
dựng và xác nhận in ra đúng `CN=Miyano PDA, ...` (không phải chữ ký debug tự
động). Bỏ qua bước này là có nguy cơ giao cho kho một app chỉ nói chuyện được
với site thử, không phải site thật.

| # | Việc | Kỳ vọng |
|---|---|---|
| 1 | Cài APK, mở app | Hiện màn khai máy chủ, mặc định đúng địa chỉ |
| 2 | Bấm Kiểm tra & lưu | Vào thẳng màn quét thẻ |
| 3 | Quét thẻ của mình | Vào menu bốn nút, hiện đúng tên mình |
| 4 | Xếp một thùng | Quét lô, quét ô, ghi xong; mở web thấy ngay phiếu xếp |
| 5 | Lấy một phiếu giao | Quét lô, quét ô, chọn đơn vị, số kiện; web thấy ngay |
| 6 | Tắt wifi rồi mở lại app | Hiện câu báo "Không nối được máy chủ..." kèm ô nhập địa chỉ (đã điền sẵn) và nút **Kiểm tra & lưu** — **không** phải nút "Đổi máy chủ" (nút đó chỉ nằm ở màn đang-nối, không hiện khi ping tự động lúc mở app thất bại), và không phải trang lỗi của Chrome |
| 7 | Thu hồi thẻ trên web khi PDA đang mở, rồi thử thao tác tiếp trên PDA | PDA quay về đúng màn quét thẻ (`/pda`) để đòi quét thẻ mới — **không phải** màn đăng nhập Desk thông thường (ô Email/Mật khẩu). Nếu thấy màn Desk là app đang lỗi (mất bẫy chuyển hướng ở tầng Java), phải báo kỹ thuật ngay |
| 8 | Để máy qua 12 tiếng | Mở lại phải quét thẻ |

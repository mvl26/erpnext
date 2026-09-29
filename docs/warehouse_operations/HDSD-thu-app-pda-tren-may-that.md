# Thử app PDA trên máy thật — tờ hướng dẫn cho người thử

Tờ này để **anh/chị cầm máy PDA thật thử app kho**. Không cần biết kỹ thuật.
Dữ liệu trong bài đã được dựng sẵn trên máy chủ thử — thử hỏng cũng không sao,
không đụng gì tới số liệu thật.

Ngày dựng: 24/09/2026.

---

## 1. Vào app

| Việc | Nội dung |
|---|---|
| Địa chỉ trên máy PDA | `http://192.168.61.129:8003/kho` |
| Mã thẻ để đăng nhập | `SGRL79WAQF3W` |
| Tài khoản tương ứng | `thu-pda@miyano.test` (tên hiện trên menu) |

Mở địa chỉ trên bằng trình duyệt của máy PDA. Màn đầu tiên là **Quét thẻ**.

- Có thẻ in sẵn thì **bắn súng quét** vào ô.
- Chưa có thẻ in thì bấm nút **hình bàn phím** ở cuối ô, gõ `SGRL79WAQF3W` rồi bấm Enter.

Vào được sẽ thấy menu bốn nút: **Tra cứu · Xếp hàng · Lấy hàng · Đặt ô**.

> Mã thẻ này chỉ dùng cho máy thử. Một phiên đăng nhập sống 12 tiếng.
> Bấm **Đăng xuất** ở cuối menu khi thử xong.

---

## 2. Những thứ cần quét, và kết quả mong đợi

Có **5 phiếu giao** đã dựng sẵn, mỗi phiếu cho một bài. Phiếu nào cũng ở kho
**THU-Kho Thu PDA - MYN**. Vào **Lấy hàng** → nếu máy hỏi kho thì chọn kho đó →
danh sách 5 phiếu hiện ra, bấm vào phiếu theo bảng dưới.

### Bảng các mã cần quét

| Thứ cần quét | Mã |
|---|---|
| Thẻ đăng nhập | `SGRL79WAQF3W` |
| Lô còn hạn, chia hai ô | `THU-LO-A` |
| Lô còn hạn, hàng nhiều | `THU-LO-B` |
| Lô **đã quá hạn** | `THU-LO-HETHAN` |
| Ô A (chỉ còn 50 Cái) | `3T0101-0101` |
| Ô B (còn 150 Cái) | `3T0101-0102` |
| Ô của lô B (2000 Cái) | `3T0101-0103` |
| Ô của lô quá hạn | `3T0101-0104` |

### Bài 1 — Lô hết hạn phải bị CHẶN

| Bước | Làm gì | Kết quả mong đợi |
|---|---|---|
| 1 | Mở phiếu ghi **THU-PDA-5** (`MAT-DN-2026-00087`) | Màn hiện một dòng hàng, 100 Cái |
| 2 | Quét `THU-LO-HETHAN` | Dải báo **đỏ/cam**: "CHẶN: lô THU-LO-HETHAN đã hết hạn ngày 31-03-2026…" |
| 3 | Nhìn màn | **KHÔNG** hiện thẻ "Đang lấy lô", **không** sang bước chờ quét ô |

Sai nếu: máy cho đi tiếp, hoặc chỉ cảnh báo nhẹ rồi vẫn cho lấy.

### Bài 2 — Quét nhầm sang lô khác, dòng CHƯA lấy gì → ĐỔI LÔ

| Bước | Làm gì | Kết quả mong đợi |
|---|---|---|
| 1 | Mở phiếu **THU-PDA-2** (`MAT-DN-2026-00084`) — dòng đang chốt lô `THU-LO-A` | |
| 2 | Quét `THU-LO-B` | Hiện một thẻ giải thích: lô vừa quét KHÁC lô đang chốt, kèm cảnh báo "lô mới có hạn XA HƠN". Nút: **Đổi sang lô THU-LO-B** |
| 3 | Bấm **Đổi sang lô THU-LO-B** | Dải báo: "Đã chuyển sang lô THU-LO-B. Quét lại tem lô để lấy." Dòng trên phiếu giờ mang lô B |

Sai nếu: máy tự đổi mà không hỏi, hoặc lại **tách** phiếu thành hai dòng.

### Bài 3 — Quét nhầm sang lô khác, dòng ĐÃ lấy một phần → TÁCH DÒNG

| Bước | Làm gì | Kết quả mong đợi |
|---|---|---|
| 1 | Mở phiếu **THU-PDA-3** (`MAT-DN-2026-00085`) — 200 Cái lô `THU-LO-B` | |
| 2 | Quét `THU-LO-B` | Hiện thẻ "Đang lấy lô THU-LO-B", số lượng 200 |
| 3 | Sửa số lượng còn **50** | |
| 4 | Quét ô `3T0101-0103` | "Đã lấy 50 Cái THU-LO-B ở 3T0101-0103" |
| 5 | Quét `THU-LO-A` | Hiện thẻ hỏi, nút ghi **Tách sang lô THU-LO-A** (không phải "Đổi") |
| 6 | Bấm nút đó | Phiếu từ **1 dòng thành 2 dòng**: dòng cũ chốt ở 50, dòng mới 150 cho lô A |

Sai nếu: nút vẫn ghi "Đổi sang lô…", hoặc phiếu vẫn một dòng, hoặc mất 50 đã lấy.

### Bài 4 — Đơn vị Hộp / Cái

| Bước | Làm gì | Kết quả mong đợi |
|---|---|---|
| 1 | Mở phiếu **THU-PDA-1** (`MAT-DN-2026-00083`) | Phiếu có 2 dòng |
| 2 | Quét `THU-LO-B` | Số lượng hiện **650**, đơn vị **Cái** |
| 3 | Bấm nút đơn vị **Hộp** | Số lượng thành **6** (không phải 7 — 650 Cái là 6,5 Hộp, máy chỉ gợi ý phần nguyên) |
| 4 | Bấm lại **Cái** | Số lượng về **650** |

### Bài 5 — Số kiện (số tem sẽ in)

| Bước | Làm gì | Kết quả mong đợi |
|---|---|---|
| 1 | Vẫn ở bài 4, chọn đơn vị **Hộp** (6 Hộp) | Ô "Số kiện (số tem)" hiện **6** — mỗi Hộp một kiện |
| 2 | Bấm **+** ở ô Số kiện | Thành **7** |
| 3 | Bấm **−** ở ô Số lượng (6 → 5) | Số kiện **vẫn là 7** — máy giữ đúng con số anh/chị đã tự đặt |

Lưu ý (đúng thiết kế, không phải lỗi): nếu **đổi đơn vị** (Hộp ↔ Cái) thì số kiện
tính lại từ đầu — vì đó là một lượt lấy khác.

Xong bài 5, bấm **Bỏ lô này** để về bước quét.

### Bài 6 — Một ô chỉ còn một phần (bài quan trọng nhất)

Dòng thứ hai của phiếu **THU-PDA-1** là **1 Hộp = 100 Cái**, nhưng hàng nằm ở
**hai ô**: ô `3T0101-0101` chỉ còn 50 Cái, ô `3T0101-0102` còn phần kia.

| Bước | Làm gì | Kết quả mong đợi |
|---|---|---|
| 1 | Quét `THU-LO-A` | Thẻ "Đang lấy lô THU-LO-A", 1 Hộp |
| 2 | Quét ô `3T0101-0101` | "Ô 3T0101-0101 chỉ còn 0.5 Hộp — đã lấy 0.5, quét ô khác cho phần còn lại." Số lượng còn lại đổi sang **50 Cái** |
| 3 | Quét ô `3T0101-0102` | **Ghi được**: "Đã lấy 50 Cái THU-LO-A ở 3T0101-0102" |

Sai nếu: bước 3 ra câu **"Số lượng phải lớn hơn 0"** và không đi tiếp được.
Đây là ca từng làm tắc giữa kho — nếu thấy lại, báo ngay.

### Bài 7 — Đặt ô: chọn kho

| Bước | Làm gì | Kết quả mong đợi |
|---|---|---|
| 1 | Về menu → **Đặt ô** | Hiện danh sách **3 kho** để chọn |
| 2 | Chọn **THU-Kho Thu PDA - MYN** | Hiện **3 lô chưa có ô**: `THU-LO-CHUAO-1/2/3`, mỗi lô tồn 30 |

### Bài 8 — Đặt ô: hết lô

| Bước | Làm gì | Kết quả mong đợi |
|---|---|---|
| 1 | Bấm **Đổi** (cạnh tên kho) → chọn **THU-Kho Da Dat O - MYN** | Câu: "Mọi lô đang có tồn ở kho THU-Kho Da Dat O - MYN đều đã có ô trên tem." Không có dòng nào, không có nút "Đặt ô" |

### Bài 9 — Bấm "Hoàn tất phiếu" nhiều lần

| Bước | Làm gì | Kết quả mong đợi |
|---|---|---|
| 1 | Mở phiếu **THU-PDA-4** (`MAT-DN-2026-00086`) | 100 Cái lô `THU-LO-B` |
| 2 | Quét `THU-LO-B`, rồi quét ô `3T0101-0103` | "Đã lấy 100 Cái…" |
| 3 | Bấm **Hoàn tất phiếu** **ba lần thật nhanh** | Chỉ hiện **MỘT** hộp xác nhận |
| 4 | Bấm **Đồng ý** | Máy báo *"Còn 1/1 kiện chưa in tem — bấm In tem kiện, dán tem lên hàng rồi duyệt."* Đây là **đúng luật**, không phải lỗi |

Sai nếu: hiện 2–3 hộp xác nhận chồng nhau, hoặc phiếu bị duyệt nhiều lượt.

**Muốn duyệt được phiếu thật** (không bắt buộc cho bài này): máy in tem nối với
MÁY TÍNH, không với PDA. Mở `MAT-DN-2026-00086` trên máy tính (Desk) → bấm
**In tem kiện** → quay lại PDA bấm **Hoàn tất phiếu** → máy báo "Đã duyệt…".
Phép thử "bấm 3 lần ra 1 hộp" quan sát được ở cả hai trường hợp.

---

## 2b. NHẬN MÁY MỘT LẦN — chỉ dành cho bản APP (file `.apk`)

Mục này **không áp dụng** cho cách mở bằng trình duyệt ở mục 1. Nó dành cho **bản app
cài vào máy** (biểu tượng trên màn hình chính). Khác biệt lớn nhất: **quét thẻ một lần
lúc nhận máy**, từ đó chạm biểu tượng là vào thẳng menu, không phải quét mỗi ca.

Xin anh/chị làm đúng bốn bước dưới, theo thứ tự, và ghi lại nếu có bước nào lệch:

| # | Việc làm | Phải thấy gì |
|---|---|---|
| 1 | Mở app lần đầu, quét thẻ của mình | Vào menu bốn nút; dòng tên mình ở cuối menu |
| 2 | **Thoát hẳn app** (bấm nút vuông của Android → gạt app ra khỏi danh sách), rồi chạm biểu tượng mở lại | Vào **THẲNG** menu. **Không** hỏi thẻ nữa |
| 3 | Nhờ trưởng kho bấm **Thu hồi thẻ** trên máy tính, rồi chạm bất kỳ nút nào trên PDA | Máy quay về màn **Quét thẻ**, kèm một dòng chữ nói **báo trưởng kho cấp khoá cho máy này** (không phải "Phiên đã hết") |
| 4 | Trưởng kho cấp thẻ **mới**, quét thẻ mới đó | Vào lại menu bình thường |

**Bốn** việc nữa cũng chỉ máy thật trả lời được, riêng cho bản app (mục 3 bên dưới có
thêm ba việc nữa, chung cho cả hai cách dùng):

- **Nút "Đăng xuất" ở cuối menu.** Từ bản này, đó là cách **trả máy** khi đổi ca: bấm
  xong máy phải về màn Quét thẻ, và người nhận ca quét thẻ **của họ** để nhận máy. Nếu
  bấm Đăng xuất mà mở lại app vẫn vào thẳng menu của người cũ — **xin ghi lại ngay**,
  đó là lỗi.
- **"Xoá dữ liệu ứng dụng"** (Cài đặt → Ứng dụng → app kho → Bộ nhớ → Xoá dữ liệu).
  Sau đó app phải mở ra ở màn **Quét thẻ** và quét lại được bình thường. Tuyệt đối
  **không** được ra màn trắng hay báo lỗi lạ. (Đây là ca duy nhất làm mất khoá đã lưu;
  không mất gì khác, mọi số liệu nằm ở máy chủ.)
- **Máy đời thấp, bộ nhớ gần đầy.** Nếu máy báo hết bộ nhớ, app có thể không nhớ được
  khoá và hỏi thẻ **mỗi lần mở**. Không phải lỗi chức năng, nhưng xin ghi lại **tên
  máy** và **dung lượng trống** để bên kỹ thuật biết ngưỡng thật.
- **Nâng cấp app tại chỗ** (cài bản `.apk` mới lên trên bản cũ, không xoá app). Sau khi
  nâng cấp, xin thử lại **bước 2** ở trên: phải vào thẳng menu, và **không** được xuất
  hiện màn đăng nhập kiểu web hay một trang lỗi. Nếu máy đòi quét thẻ lại sau khi nâng
  cấp thì vẫn dùng được (quét lại là xong), nhưng **xin ghi lại**.
  *(Ca nâng cấp từ bản ĐỜI CŨ — bản còn dùng cookie — là một bài riêng và quan trọng
  hơn hẳn: xem mục **3.1**.)*

---

## 3. 11 thứ CHỈ máy thật mới trả lời được

Mọi cổng nghiệm thu tự động của kho chạy trên **trình duyệt máy tính**. 11
việc dưới đây **không cổng nào chạm tới được** — hoặc vì chúng thuộc về tầng
Android, hoặc vì chúng cần một chiếc máy có sóng, có đồng hồ, và có ngón tay.
Xin anh/chị làm và ghi lại, kể cả khi kết quả **đúng như kỳ vọng**: "đã thử,
đúng" cũng là một câu trả lời mà hôm nay chưa ai có.

Bốn mục đầu là những mục bên kỹ thuật tự khai là **chưa chứng minh được**.

### 3.1. Cookie đời cũ sau khi NÂNG CẤP APK TẠI CHỖ

Đây là mục quan trọng nhất của cả tờ này.

Bản app đời cũ điều hướng thẳng vào trang web của máy chủ, nên nó để lại một
**cookie đăng nhập** trong máy. Bản mới không dùng cookie nữa — nó dùng khoá
máy. App mới có một đoạn xoá sạch cookie mỗi lần mở, nhưng **đoạn đó chưa từng
được chạy trên một chiếc máy thật**.

| Bước | Làm gì | Phải thấy gì |
|---|---|---|
| 1 | Cài bản APK **ĐỜI CŨ** (bản trước 24/09/2026) lên một máy sạch, mở app, **đăng nhập/quét thẻ** để có phiên | Vào được như bản cũ |
| 2 | Cài đè bản APK **MỚI** lên trên (KHÔNG gỡ app, KHÔNG xoá dữ liệu) | Cài xong bình thường |
| 3 | Mở app | **Phải ra màn Quét thẻ** và đòi quét thẻ |

**Sai nếu**: app vào thẳng menu, hoặc làm được việc mà chưa từng quét thẻ trên
bản mới. Nghĩa là cookie cũ còn sống và nó đang **che mất** trạng thái "máy chưa
được cấp quyền" — trạng thái mà toàn bộ việc thu hồi máy dựa vào. **Ghi lại
ngay, đây là lỗi an ninh chứ không phải lỗi giao diện.**

### 3.2. Một lượt đi–về qua HTTPS THẬT, với chứng chỉ THẬT

Máy dựng bản này chỉ thử được với `http://` trong mạng nội bộ. Mọi lời gọi của
app đi qua **một cầu nối ở tầng Java**, không đi bằng trình duyệt — mà tầng Java
có bộ kiểm chứng chỉ riêng.

| Bước | Làm gì | Phải thấy gì |
|---|---|---|
| 1 | Trỏ app vào một địa chỉ `https://` thật (ngrok, hoặc tên miền thật của kho) | |
| 2 | Quét thẻ, rồi quét một lô | Ra dữ liệu bình thường |

**Sai nếu**: ra câu "Mất kết nối. Kiểm tra wifi rồi thử lại." trong khi wifi tốt
và mở cùng địa chỉ đó bằng Chrome trên chính máy ấy thì vào được. Đó là chứng
chỉ bị tầng Java từ chối — ghi lại **tên miền** và **ai cấp chứng chỉ**.

### 3.3. Mất sóng ĐÚNG GIỮA CHỪNG một lời gọi

Không phải "tắt wifi rồi bấm" (cái đó đã thử được trên máy tính), mà là **đang
bấm thì sóng rớt**.

| Bước | Làm gì | Phải thấy gì |
|---|---|---|
| 1 | Đứng ở rìa vùng phủ wifi của kho, hoặc nhờ người tắt wifi đúng lúc | |
| 2 | Bấm **Hoàn tất phiếu** (hoặc ghi một thùng) rồi đi ra khỏi vùng sóng ngay | |
| 3 | Nhìn màn | Câu tiếng Việt, **không** treo, **không** quay vòng mãi |
| 4 | Có sóng lại, mở web trên máy tính xem phiếu đó | Phiếu **hoặc** đã ghi **hoặc** chưa ghi — không được nửa vời |

**Ghi lại**: câu chữ hiện ra, và kết quả bước 4. Nếu màn hình đứng im quay vòng
quá 15 giây mà không có câu nào, đó là lỗi.

### 3.4. Máy đời thấp — chỗ cất khoá có đủ không

App cất khoá máy trong bộ nhớ của trình duyệt hệ thống (`localStorage`). Một số
bản Android gọt sẵn, hoặc máy do công ty quản lý bằng phần mềm MDM, **từ chối**
cho ghi vào đó. Bên kỹ thuật chỉ chứng minh được rằng app **không tự tắt** nó,
chứ không chứng minh được rằng máy **có cấp**.

| Bước | Làm gì | Phải thấy gì |
|---|---|---|
| 1 | Quét thẻ nhận máy | Vào menu |
| 2 | Thoát hẳn app, mở lại | Vào **thẳng** menu |
| 3 | Lặp lại bước 2 ba lần nữa, có một lần **khởi động lại máy** | Lần nào cũng vào thẳng menu |

**Sai nếu**: có lần đòi quét thẻ lại. Ghi lại **tên máy**, **bản Android**,
**dung lượng trống**, và máy có do công ty quản lý bằng MDM không.

### 3.5. Đồng hồ máy SAI — chip hạn dùng có đúng không

App cố ý **không tin đồng hồ của máy**: nó hỏi giờ máy chủ. Máy quét trong kho
thường không có SIM, không đồng bộ giờ, pin yếu là trôi ngày — và một lần trước
đây, chính chỗ này đã làm phán quyết **hết hạn** của một lô vật tư y tế đổi
nghĩa mà không ai biết.

| Bước | Làm gì | Phải thấy gì |
|---|---|---|
| 1 | Cài đặt Android → Ngày giờ → **tắt "Tự động"** → đặt ngày **lệch hẳn 2 ngày về sau** | |
| 2 | Mở app, vào **Tra cứu**, quét một lô có hạn dùng gần (ví dụ `THU-LO-A`) | Chip hạn dùng phải tính theo **ngày THẬT**, không theo ngày vừa đặt |
| 3 | Nhìn đầu màn | Có thể hiện dải **CAM "Giờ máy lệch…"** — đó là đúng, nó chỉ nhắc chứ không chặn |
| 4 | Quét `THU-LO-HETHAN` | Vẫn phải chặn vì hết hạn |
| 5 | Đặt lệch **về quá khứ 2 ngày**, lặp lại bước 2 | Chip vẫn y như bước 2 |
| 6 | **Trả lại giờ tự động** | |

**Sai nếu**: chip đổi theo đồng hồ máy, hoặc chip **biến mất hẳn** mà không có
dải xám "Chưa lấy được giờ hệ thống". Cảnh báo có hiện hay không **không thay
được** việc con số phải đúng — xin để ý cả hai.

### 3.6. Lối ẩn khai địa chỉ máy chủ

Lối này để cứu cả kho khi đường hầm vào máy chủ rớt (xem `HDSD-app-pda.md` mục
7). Nó đã được đo bằng chuột trên máy tính, **chưa được đo bằng ngón tay**.

| Bước | Làm gì | Phải thấy gì |
|---|---|---|
| 1 | Ở màn Quét thẻ, chạm logo **MIYANO** rồi nhả ra ngay | **Không** có gì xảy ra |
| 2 | Bấm giữ logo, đếm đủ **3 giây**, rồi nhả | Hiện hộp "Địa chỉ máy chủ…" với ô đã điền sẵn địa chỉ đang dùng |
| 3 | Trong lúc giữ, nhìn kỹ | **Không** được bật menu "Copy/Chọn chữ" của Android che mất logo |
| 4 | Bấm giữ 3 giây rồi **kéo ngón tay ra khỏi logo** trước khi nhả | **Không** mở hộp |
| 5 | Với hộp đang mở, **bắn súng quét** vào ô địa chỉ | Hộp **không** được tự lưu/tự đóng |
| 6 | Gõ `http://10.9.9.9:8000` → **Lưu và mở lại** | Phải hiện câu từ chối nói rõ Android chặn `http://` tới địa chỉ đó |
| 7 | Bấm **Đóng** | Về màn quét thẻ, địa chỉ cũ giữ nguyên |

**Ghi lại**: bước 2 có cần giữ lâu hơn 3 giây không (cảm giác thật), và bước 3
có bị menu chọn chữ chen vào không.

### 3.7. Nút "Mở trang tải" của dải nhắc bản mới

Đây là mục kỹ thuật **chưa chứng minh được** bằng bất cứ phép đo nào: nút đó
phải mở **trình duyệt của máy**, và app phải **đứng nguyên** phía sau.

| Bước | Làm gì | Phải thấy gì |
|---|---|---|
| 1 | Nhờ trưởng kho đưa lên một bản cài có số hiệu **cao hơn** bản đang cài | |
| 2 | Mở app, vào menu | Hiện dải **XANH** "Đã có bản cài mới …" |
| 3 | Bấm **Mở trang tải** | **Chrome (hoặc trình duyệt mặc định) mở ra** trang tải |
| 4 | Bấm Back để quay lại app | App vẫn ở **đúng màn menu**, không phải màn trắng, không phải trang lỗi |

**Sai nếu**: trang tải mở **bên trong app** (không có thanh địa chỉ của Chrome),
hoặc bấm Back ra màn trắng. Đó là app đã bị kéo ra khỏi giao diện của nó — ghi
lại ngay.

### 3.8. Súng quét, bàn phím ảo

1. **Súng quét có tự gửi mã sau khi bắn không?** Bắn một mã bất kỳ vào ô quét.
   Máy có tự xử lý ngay không, hay phải bấm thêm phím nào? (App có hai đường:
   chờ Enter của súng, và tự gửi sau khi ngừng nhận ký tự 1/4 giây — cần biết
   đường nào đang chạy trên máy của mình.)
2. **Bàn phím ảo có nhảy lên che màn không?** Bình thường ô quét được đặt
   "không gọi bàn phím"; khi bắn súng, bàn phím ảo **không được** bật lên. Chỉ
   khi bấm nút hình bàn phím mới được bật. Nếu bàn phím tự nhảy lên che mất
   nút/ô số lượng — ghi lại màn nào.
3. **Súng quét bắn khi đang có hộp xác nhận mở** (ví dụ hộp "Hoàn tất phiếu?").
   Mã vừa bắn **không được** lọt xuống ô quét phía sau hộp. Đây từng là một sự
   cố thật (duyệt nhầm một phiếu, 17/09/2026) — nếu thấy lại, ghi lại ngay.

### 3.9. Nút Back CỨNG của Android

| Bước | Làm gì | Phải thấy gì |
|---|---|---|
| 1 | Đang ở **menu** bốn nút, bấm Back cứng | **Thoát app** — không nhảy ngược vào màn vừa rời |
| 2 | Vào một màn việc, bấm "‹" về menu, rồi bấm Back cứng | Vẫn **thoát app** |
| 3 | Vào một màn việc rồi bấm **thẳng** Back cứng | Về menu, **đúng một bước** |
| 4 | Ở màn **Quét thẻ** (máy chưa nhận), bấm Back cứng vài lần | Không được lọt vào menu hay màn việc nào |

Bước 4 là bước đáng để ý nhất: nút Back đổi được địa chỉ trang mà app không
phân biệt được nguồn, nên đây là chỗ một máy chưa được cấp quyền có thể lọt vào
trong. Nếu thấy menu hiện ra ở bước 4 — **ghi lại ngay**.

### 3.10. Bốn luật của màn Lấy hàng khi lô có ĐƠN VỊ ĐÓNG GÓI

*(Ghi lại từ đợt trước, 23–24/09/2026 — chuyển từ `HDSD-app-pda.md` sang đây khi
tài liệu đó được viết lại. **Chưa ai kiểm đầu–cuối bằng dữ liệu thật**, ghi ra để
không ai tưởng nhầm là đã kiểm.)*

Bốn luật chỉ chạy được ở nhánh lô **có đơn vị đóng gói** (UOM khác đơn vị gốc):
(a) lô hết hạn thì **chặn** lấy; (b) quét nhầm sang lô khác thì **đổi lô** hoặc
**tách dòng** tuỳ dòng đã lấy gì chưa; (c) đơn vị lấy làm tròn **xuống** phần
nguyên; (d) có ô nhập **số kiện**.

**Vì sao chưa kiểm được:** trên `erptest.local`, tại thời điểm viết, **không còn
phiếu giao (`Delivery Note`) nào có dòng lô kèm đơn vị đóng gói**.

**Trước khi thử:** nhờ kỹ thuật tạo sẵn (hoặc giữ lại) một phiếu giao có ít nhất
một dòng lô mang UOM đóng gói (ví dụ "Thùng" quy đổi từ "Cái"), rồi lặp lại các
bài 4–6 của mục 2 với đúng dòng đó — quan sát **cả bốn** luật, không chỉ luật
"ghi được".

### 3.11. Hai nhánh của màn Đặt ô

*(Cùng nguồn gốc và cùng trạng thái với 3.10: **chưa kiểm bằng dữ liệu thật**.)*

(a) Màn báo "hết lô chưa gán ô" khi không còn lô nào cần đặt; (b) màn hiện **hộp
chọn kho** khi tài khoản quản lý NHIỀU kho có bật quản lý vị trí.

**Vì sao chưa kiểm được:** `erptest.local` chỉ có **một** kho bật quản lý vị trí
(`Kho Miyano - MYN`), và kho đó luôn còn dư lô chưa gán ô (49 lô tại thời điểm
ghi) — nên nhánh "hết lô" chưa từng được kích hoạt, và nhánh "chọn kho" không có
gì để chọn.

**Trước khi thử:** (a) gán ô cho hết số lô còn lại trên site thử (hoặc lọc còn
rất ít) rồi mở lại màn Đặt ô để thấy thông báo hết lô; (b) bật quản lý vị trí
thêm một kho thứ hai rồi đăng nhập một tài khoản có quyền trên cả hai kho để
thấy hộp chọn kho hiện ra.

> *(Bộ dữ liệu `THU-` ở mục 2 có bài 7/8 chạm tới nhánh chọn kho và nhánh hết lô
> trên các kho `THU-…` — nhưng đó là dữ liệu dựng riêng cho bài thử, không phải
> dữ liệu vận hành. Hai mục trên nói về nhánh chạy trên kho THẬT.)*

## 4. Nếu thấy sai thì ghi lại gì

Ghi càng ngắn càng tốt, nhưng **phải đủ bốn thứ**:

1. **Màn nào** — Tra cứu / Xếp hàng / Lấy hàng / Đặt ô / Quét thẻ.
2. **Bấm gì, quét gì** — ghi đúng mã đã quét và đúng nút đã bấm, theo thứ tự.
   Ví dụ: "phiếu THU-PDA-1, quét THU-LO-A, quét 3T0101-0101, rồi quét 3T0101-0102".
3. **Thấy gì** — chép nguyên câu chữ trên dải báo (chụp ảnh màn hình là tốt nhất).
4. **Mong đợi gì** — theo bảng trên thì lẽ ra phải ra gì.

Thêm nếu có: **giờ** xảy ra, **tên phiếu** (`MAT-DN-2026-000xx`), và máy PDA đang
dùng là máy nào.

---

## 5. Dữ liệu này là dữ liệu THỬ

Mọi thứ trong bài đều mang tiền tố `THU-` (kho, mặt hàng, số lô), riêng ô kho
dùng khu `3T` và `3U` vì mã ô bắt buộc đúng 10 ký tự theo chuẩn SPD.

Thử xong, thử lại từ đầu được: dựng lại bộ dữ liệu bằng đúng một lệnh (xem
`.superpowers/sdd/2026-09-23-giao-dien-app-kho-pda/du-lieu-thu-report.md`).
Khi nào không cần nữa, cũng xoá sạch bằng một lệnh, không để lại vết.

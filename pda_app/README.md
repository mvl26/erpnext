# pda_app — Vỏ Android cho PDA kho Miyano

**ĐỔI HƯỚNG 24/09/2026 (spec `2026-09-24-app-pda-giao-dien-trong-may-design.md`):
giao diện nằm TRONG MÁY, không còn tải từ máy chủ.** Trước đó app là một cửa sổ
WebView trỏ vào `<máy chủ>/kho`, nên mở lên phải qua màn khai địa chỉ rồi chờ
tải trang — đúng nhịp của web. Nay `www/` mang sẵn bản dựng của giao diện `/kho`:
chạm icon là vào thẳng màn hình, chỉ dữ liệu mới đi qua mạng.

Máy chủ vẫn giữ toàn bộ nghiệp vụ (quét thẻ, xếp hàng, lấy hàng, tra cứu, đặt ô
hàng loạt...) — app không sao chép bất kỳ luật nghiệp vụ nào, chỉ mang bản dựng
của lớp vẽ.

**MỘT nguồn mã, hai nơi chạy.** Trang `/kho` trên web và app dùng CÙNG MỘT
`kho_pda.bundle.js`; `scripts/pda/dong-goi.sh` CHÉP bản dựng vào `www/`, không
bao giờ chép mã nguồn. Sửa giao diện là sửa ở `erpnext/public/js/kho_pda*` —
web nhận ngay, máy quét phải cài lại (xem "Dựng lại file APK").

## Cấu trúc

- `www/index.html` — vỏ TĨNH: khai `window.KHO_LA_APP`, nạp `cau-hinh.js`,
  jQuery, `shim.js` rồi `kho_pda.bundle.js`. Không còn màn khai địa chỉ máy chủ
  trong luồng thường (Task 6 thêm lối ẩn: bấm giữ logo 3 giây).
- `www/shim.js` — các toàn cục mà bốn màn mượn của Frappe (`__`, `flt`,
  `frappe.provide`, `frappe.utils.escape_html`/`icon`, `frappe.datetime.*`).
  Trong app không có Frappe nên vỏ tự cấp; xem chú thích đầu file để biết vì sao
  không gói cả `frappe-web.bundle.js`.
- `www/vendor/jquery.min.js` — bản jQuery lấy từ `apps/frappe/node_modules`,
  gói thẳng vào APK. Theo dõi trong git (không tải từ internet lúc dựng).
- `www/kho_pda.bundle.js` / `.css` / `cau-hinh.js` — SINH RA bởi
  `scripts/pda/dong-goi.sh`, bị `.gitignore`. Đừng sửa tay: lượt đóng gói sau
  ghi đè.
- `android/` — dự án Android sinh bởi `npx cap add android` (Task 5, bước 4).
- `capacitor.config.json` — cấu hình Capacitor: `appId`, `appName`,
  `androidScheme: https`, `server.errorPath`, và **`plugins.CapacitorHttp.enabled`**.

  **`CapacitorHttp` LÀ THỨ LÀM APP GỌI ĐƯỢC MÁY CHỦ (Task 2B).** Bật nó lên thì
  `native-bridge.js` của Capacitor vá `window.fetch` và `XMLHttpRequest` để lời
  gọi đi qua **tầng native của Android** (`HttpURLConnection` trong
  `com.getcapacitor.plugin.CapacitorHttp`), không qua ngăn xếp mạng của trình
  duyệt — nên **không dính luật cùng-nguồn**, và **không phải mở CORS trên máy
  chủ**. Tắt nó đi là app chết câm: trang nằm ở `file://`, lời gọi mang
  `Content-Type: application/json` nên bắt buộc có preflight, và Frappe không
  trả header CORS (đo được: `OPTIONS` tới `erptest.local` trả `200` nhưng
  **không có** `Access-Control-Allow-Origin`) → mọi lời gọi `net::ERR_FAILED`.

  **ĐỪNG "sửa" bằng `allow_cors` trong `site_config.json`.** Lối đó bắt MỌI máy
  chủ mà APK có thể trỏ tới phải được cấu hình trước; ai quên thì app chết câm ở
  đúng site đó, và với một bench dùng chung ba site thì đó là một thay đổi vượt
  phạm vi app này.

  **ĐÃ BỎ `server.allowNavigation` và `android.allowMixedContent` (Task 2B).**
  Cả hai là di sản của đời app cũ — đời đó WebView ĐIỀU HƯỚNG sang trang web của
  máy chủ, nên cần một hàng rào host và một cờ nội dung hỗn hợp. App đời mới
  **không rời `www/index.html`**: giao diện nằm trong máy, máy chủ chỉ được gọi
  bằng `fetch` qua cầu native. Không còn lượt điều hướng nào để rào, và
  `allowMixedContent` là luật của **trình duyệt** cho nội dung nạp vào TRANG —
  nó không chi phối lời gọi native. Thứ chi phối lời gọi native là
  `android/app/src/main/res/xml/network_security_config.xml` (xem bước 3 ở mục
  "Dựng lại file APK").

## Lệnh

```bash
# BƯỚC ĐÓNG GÓI — chạy TRƯỚC mọi lệnh Capacitor bên dưới. Dựng lại bundle rồi
# chép bản dựng + sinh cau-hinh.js vào www/. Thiếu bước này thì `cap sync` gói
# một thư mục www/ không có giao diện.
../scripts/pda/dong-goi.sh
../scripts/pda/dong-goi.sh --bo-qua-dung   # chỉ chép (bundle đã dựng sẵn)

npm install                 # cài @capacitor/core, @capacitor/cli, @capacitor/android
npm run them-android         # npx cap add android — sinh dự án Android
npm run dong-bo               # npx cap sync android — đồng bộ www/ + cấu hình vào Android
npm run mo-android            # npx cap open android — mở Android Studio (Task 6)
```

Cổng nghiệm thu của bản đóng gói (chạy sau `dong-goi.sh`, cần Playwright):

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/erpnext
node scripts/kiem_giao_dien/kiem_ban_dong_goi.js     # PASS cả bốn màn
```

## Ghi chú

- Máy chủ thử hiện tại: `http://192.168.61.129:8003` (Host `erptest.local`),
  giữ trong `scripts/pda/cau-hinh-may-chu.json`.
- **Địa chỉ máy chủ THẬT không nằm trong kho mã nguồn.** Hệ thống đang mở ra
  internet qua ngrok; người phát hành tự điền địa chỉ public thật vào
  `scripts/pda/cau-hinh-may-chu.json` trước khi chạy `dong-goi.sh` để dựng bản
  cho kho, rồi TRẢ file đó về địa chỉ thử. Giá trị đi vào bản dựng qua
  `www/cau-hinh.js` (bị `.gitignore`), không qua `www/index.html` — `index.html`
  được git theo dõi, thay tại chỗ là ghi địa chỉ thật vào kho.
- **DANH TÍNH MÁY (Task 3) — ba điều người vận hành phải biết trước khi phát máy:**
  1. Mọi lời gọi của app mang `Authorization: token <api_key>:<api_secret>` **phải**
     kèm header `X-Ma-May: <Android ID>`. Thiếu hoặc sai là **401** kèm câu
     *"Máy chưa được cấp quyền — báo trưởng kho cấp khoá cho máy này."* Đây là ràng
     buộc ở **cửa vào** (`auth_hooks`), không phải ở riêng các hàm của kho.
  2. Vì nó ở cửa vào nên nó áp cho **mọi** lời gọi mang khoá của người đó: **ai đã
     nhận máy PDA thì khoá API của người ấy chỉ dùng được từ chiếc máy ấy** — kể cả
     một tích hợp/script ngoài đang chạy bằng chính khoá đó. Kiểm điều này trước khi
     cấp máy cho một tài khoản đang có tích hợp.
  3. Cấp máy cho người đang có **khoá API lạ** bị **TỪ CHỐI** (vòng sửa 2). Lý do:
     `generate_keys` luôn xoay `api_secret`, nên cấp máy giết tích hợp đang dùng khoá
     đó — tức thì, không hoàn nguyên được; và `cap_khoa_may` là `allow_guest`, nên chỉ
     "báo" thì một mã thẻ rò rỉ đủ để giết khoá đó mà không cần đăng nhập. Thủ kho sẽ
     thấy câu *"Chưa cấp được khoá cho máy này: tài khoản … đang có một khoá API dùng
     cho việc khác…"*.
     **Lối thoát:** trưởng kho tick ô **`Cho phép đè khoá API có sẵn`** trên `PDA Badge`
     rồi cho quét lại — cờ **tự tắt** sau lần cấp đó, và **một lần là một lần**: đổi máy
     những lần sau KHÔNG phải tick lại. **Đổi máy cho người đã có máy PDA thì KHÔNG bị
     chặn** (khoá đang có là của chính PDA). Đầy đủ ở spec §7.
  4. **Trước khi bật trên một site đã chạy:** `SELECT COUNT(*) FROM \`tabPDA Thiet Bi\``.
     Bằng **0** → không có việc gì phải làm. Khác 0 → những máy cấp trước bản này chưa có
     dấu vân tay khoá, nên mỗi máy cần tick ô lối thoát **đúng một lần** lúc quét lại.
     Không backfill dấu vân tay: làm được nhưng **không nên** — lý do ở spec §7.
- Vì sao vẫn còn `MainActivity.java` sửa tay: **hai việc**. (1) Ghi đè
  `onReceivedHttpError` để bỏ trống. (2) `xoaSachCookie()` trong `onCreate` — xoá
  sạch kho cookie của WebView mỗi lần mở app, để một `sid` sót lại từ APK đời cũ
  không che mất trạng thái "máy chưa được cấp khoá". Chi tiết vì sao không dùng cờ
  `CapacitorCookies` và vì sao gọi **sau** `super.onCreate`: Javadoc trong
  `MainActivity.java`.
  Về việc thứ nhất: `BridgeWebViewClient` của Capacitor dùng
  chung nhánh `server.errorPath` cho cả lỗi mạng lẫn lỗi HTTP; với lỗi HTTP thì
  máy chủ vẫn ping được, nên nạp lại `errorPath` sinh một vòng lặp vô hạn. Xem
  Javadoc trong `android/app/src/main/java/vn/com/miyano/pda/MainActivity.java`.
- **ĐÃ BỎ mẹo bắt điều hướng `/login` (Task 2B).** Nó sinh ra cho đời app cũ:
  khi WebView rời `www/index.html` để nạp nguồn từ máy chủ thì JS của vỏ app
  không còn sống, nên phải chặn ở tầng Java. App đời mới không rời
  `www/index.html` nữa và không dùng cookie phiên (danh tính đi bằng khoá máy
  trong header `Authorization`), nên không có lượt điều hướng `/login` nào để
  bắt — giữ lại là để lại một đoạn mã **nói dối về cách app chạy**.

## Dựng lại file APK (Task 6)

**CHỐT CHẶN trước khi giao APK cho kho dùng thật:** `scripts/pda/cau-hinh-may-chu.json`
trong kho LUÔN giữ `http://192.168.61.129:8003` — địa chỉ site THỬ
`erptest.local`, không phải máy chủ thật. Không có gì tự động ngăn việc build và
phát ra một APK vẫn còn trỏ vào site thử. Trước khi giao APK cho kho:
1. Sửa **CẢ HAI** khoá `may_chu` và `may_chu_phat_hanh` trong
   `scripts/pda/cau-hinh-may-chu.json` sang địa chỉ máy chủ thật, chạy
   `scripts/pda/dong-goi.sh`, rồi TRẢ file đó về giá trị thử (`may_chu` =
   `http://192.168.61.129:8003`, `may_chu_phat_hanh` = `""`) — xem "Đổi địa chỉ
   máy chủ mặc định" bên dưới, có thêm bước sửa `network_security_config.xml`
   nếu máy chủ thật chạy HTTP.

   **Vì sao hai khoá (Task 2):** `dong-goi.sh` so chúng với nhau. Khác nhau (hoặc
   `may_chu_phat_hanh` bỏ trống) thì nó sinh thêm `window.KHO_BAN_THU = true`
   trong `www/cau-hinh.js`, và màn quét thẻ + màn menu đeo một **dải cam "BẢN
   THỬ"**. Dòng chữ "Máy chủ: …" nhỏ ở chân màn thẻ không đủ — thủ kho không đối
   chiếu một URL họ chưa từng nhớ; một dải cam thì không cần đọc chữ cũng thấy.
   Bản phát hành thật (hai khoá bằng nhau) không sinh biến đó nên dải tự tắt,
   không ai phải nhớ tắt. Bản dựng lỡ tay từ kho mã nguồn **luôn** đeo dải này.
   Dòng cuối của `dong-goi.sh` in ra đang ở chế độ nào — đọc nó trước khi dựng APK.
2. Dựng lại APK bằng đúng bốn lệnh ở dưới.
3. Chạy `apksigner verify --print-certs` trên file vừa dựng, xác nhận in ra
   đúng `CN=Miyano PDA, ...` — KHÔNG chỉ tin "BUILD SUCCESSFUL" (xem lý do ở
   cuối mục này).

**Môi trường cần có** — không cài bằng `sudo`, tất cả nằm ngoài kho mã nguồn:

- Node 18 (đã có sẵn trên máy dựng).
- JDK 17 (tarball Temurin, không phải gói hệ thống):
  ```bash
  mkdir -p ~/opt && cd ~/opt
  curl -L -o jdk17.tar.gz "https://api.adoptium.net/v3/binary/latest/17/ga/linux/x64/jdk/hotspot/normal/eclipse"
  tar xzf jdk17.tar.gz && rm jdk17.tar.gz && mv jdk-17* jdk17
  ```
- Android SDK 34 (chỉ ba gói cần cho việc build máy trần — KHÔNG cài
  `emulator`/`system-images`, mỗi thứ vài GB và không dùng để build APK):
  ```bash
  mkdir -p ~/opt/android-sdk/cmdline-tools && cd ~/opt/android-sdk/cmdline-tools
  curl -L -o tools.zip https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip
  unzip -q tools.zip && rm tools.zip && mv cmdline-tools latest
  export JAVA_HOME=~/opt/jdk17
  export ANDROID_HOME=~/opt/android-sdk
  yes | ~/opt/android-sdk/cmdline-tools/latest/bin/sdkmanager --licenses
  ~/opt/android-sdk/cmdline-tools/latest/bin/sdkmanager "platform-tools" "platforms;android-34" "build-tools;34.0.0"
  ```

**Khoá ký** — bắt buộc, nằm NGOÀI kho mã nguồn ở `~/keys/`:

- `~/keys/miyano-pda.keystore` — khoá RSA 2048, alias `miyano-pda`, hiệu lực
  10.000 ngày. Sinh bằng `keytool -genkeypair` (xem lệnh trong
  `.superpowers/sdd/2026-09-23-app-pda-apk/task-6-brief.md`, Bước 4).
- `~/keys/mat-khau-miyano-pda.txt` — mật khẩu, quyền `600`, một bản duy nhất.
  **Chủ đầu tư phải chép mật khẩu này vào nơi lưu mật khẩu của công ty ngay.**
  **Mất file khoá hoặc mật khẩu này là KHÔNG cập nhật được app đã cài trên máy
  quét thật nữa** — Android từ chối cài APK ký bằng khoá khác lên trên một app
  cùng `appId` đã cài bằng khoá cũ; phải gỡ app cũ thủ công trên từng máy rồi
  cài lại bằng khoá mới. Không có cách khôi phục khoá đã mất.
- `pda_app/android/keystore.properties` (đã có sẵn `.gitignore` chặn — pattern
  `keystore.properties` trong `pda_app/.gitignore` và `pda_app/**/keystore.properties`
  trong `.gitignore` gốc của app; kiểm lại bằng
  `git check-ignore -v pda_app/android/keystore.properties` sau khi tạo file,
  đừng chỉ tin theo brief):
  ```properties
  storeFile=/home/hoangvietyeuem/keys/miyano-pda.keystore
  storePassword=<mật khẩu>
  keyAlias=miyano-pda
  keyPassword=<mật khẩu>
  ```

**Lệnh dựng lại APK** (từ `pda_app/`):

```bash
npm install                    # bắt buộc trên máy sạch: node_modules/ bị gitignore.
                                # Không được bỏ qua bước này rồi chạy thẳng
                                # `npx cap sync android` — nếu chưa từng cài,
                                # npx có thể đi tải một gói TÊN "cap" khác trên
                                # npm registry (không phải @capacitor/cli) thay
                                # vì dùng bản đã khai trong package.json.
export JAVA_HOME=~/opt/jdk17
export ANDROID_HOME=~/opt/android-sdk
npx cap sync android
cd android && ./gradlew assembleRelease
```

`npm install` chỉ cần chạy lại khi `node_modules/` chưa có hoặc `package.json`/
`package-lock.json` đổi — không cần chạy lại mỗi lần build.

APK ra ở `pda_app/android/app/build/outputs/apk/release/miyano-pda-<phiên bản>-release.apk`.

**Phát hành cho kho** (từ 23/09/2026): đừng chép file bằng cáp nữa. Vào **Quản lý kho › Cài app
PDA** trên web, bấm **Đưa bản cài lên** và chọn file APK vừa dựng; máy quét sẽ tải về từ
`<địa chỉ kho>/tai-app`. Tên file **phải mang chữ `pda`** — trang tìm bản cài theo mẫu tên đó
(`vitri/cai_app.py: MAU_TEN`), để một file `.apk` lạ ai đó tải lên cho việc khác không bị nhận
nhầm là bản cài của kho. Gradle đã được cấu hình đặt đúng tên này trong `android/app/build.gradle`.
Kiểm APK đã ký thật (không phải ký debug tự động của Gradle):

```bash
export PATH="$JAVA_HOME/bin:$PATH"
~/opt/android-sdk/build-tools/34.0.0/apksigner verify --print-certs \
  android/app/build/outputs/apk/release/miyano-pda-<phiên bản>-release.apk
```

Phải in ra đúng `CN=Miyano PDA, ...` — nếu in ra một DN khác hoặc báo lỗi
verify, `keystore.properties` không trỏ đúng khoá.

**Nếu THIẾU hẳn `keystore.properties` (chưa từng đặt khoá, hoặc gõ sai đường
dẫn `storeFile`) thì build KHÔNG âm thầm ra file không ký — đã kiểm thật bằng
cách đổi tên file đi rồi chạy `./gradlew assembleRelease`:** Gradle báo
`BUILD FAILED`, thoát mã khác 0, và **không sinh ra file APK nào** trong
`app/build/outputs/apk/release/` — lỗi cụ thể:

```
> Task :app:packageRelease FAILED
FAILURE: Build failed with an exception.
* What went wrong:
Execution failed for task ':app:packageRelease'.
> A failure occurred while executing com.android.build.gradle.tasks.PackageAndroidArtifact$IncrementalSplitterRunnable
   > SigningConfig "release" is missing required property "storeFile".
BUILD FAILED
```

Vậy điểm nguy hiểm thật sự **không phải** "ra APK không ký mà không biết" —
Gradle tự chặn việc đó. Điểm nguy hiểm thật là: nếu ai đó **xoá dòng
`signingConfig signingConfigs.release`** khỏi `build.gradle` (thay vì chỉ
thiếu `keystore.properties`), Gradle sẽ **âm thầm quay về không ký** và
`assembleRelease` có thể chạy "thành công" — trường hợp đó `apksigner verify`
ở trên là cách duy nhất phát hiện ra (DN sẽ không phải `CN=Miyano PDA...`,
hoặc verify báo APK chưa ký). **Luôn chạy `apksigner verify --print-certs`
sau mỗi lần build trước khi phát APK cho kho — đừng chỉ tin "BUILD
SUCCESSFUL".**

**Đổi địa chỉ máy chủ mặc định** (khi kho chuyển sang máy chủ khác, ví dụ từ
`erptest.local` sang máy chủ thật `erp.miyano.com.vn`):

1. Sửa `may_chu` trong `scripts/pda/cau-hinh-may-chu.json` thành địa chỉ mới rồi
   chạy `scripts/pda/dong-goi.sh` (nó sinh lại `www/cau-hinh.js`). ĐỪNG sửa
   `www/index.html`: file đó không còn giữ địa chỉ nào. Nếu đây là bản PHÁT HÀNH
   cho kho thì sửa `may_chu_phat_hanh` sang cùng địa chỉ (bỏ dải "BẢN THỬ"); nếu
   là bản thử thì để nguyên khác nhau.
2. **KHÔNG còn bước `allowNavigation`** (đã bỏ khỏi `capacitor.config.json` ở
   Task 2B — app không điều hướng ra ngoài `www/index.html` nữa). Cũng KHÔNG cần
   khai CORS gì trên máy chủ mới: lời gọi đi qua cầu HTTP native.
3. **Nếu máy chủ mới chạy HTTP thường (không phải HTTPS), phải thêm địa chỉ đó
   vào `android/app/src/main/res/xml/network_security_config.xml`** — file này
   hiện chỉ mở ngoại lệ cleartext cho đúng `192.168.61.129` và `10.0.2.2`, mọi
   host khác bị `<base-config cleartextTrafficPermitted="false" />` chặn.
   **Đây là bước DUY NHẤT còn lại ở tầng Android, và nó QUAN TRỌNG HƠN trước:**
   từ Task 2B mọi lời gọi máy chủ đi bằng `HttpURLConnection` ở tầng Java, mà
   `network_security_config.xml` chính là thứ chi phối tầng đó. Thiếu bước này
   thì hệ điều hành chặn kết nối HTTP trước khi có gói tin nào rời máy — mọi lời
   gọi thất bại và người dùng chỉ thấy "Mất kết nối. Kiểm tra wifi rồi thử lại.",
   không có manh mối gì chỉ ra đúng nguyên nhân. Máy chủ chạy HTTPS thật thì bỏ
   qua bước này.
4. Chạy lại đúng bốn lệnh dựng ở trên, phát hành APK mới cho các máy PDA.

**SỬA GIAO DIỆN GIỜ PHẢI DỰNG LẠI APK** (đổi hẳn so với bản trước 24/09/2026:
khi ấy app chỉ là một WebView trỏ vào máy chủ nên sửa gì trên web cũng có hiệu
lực ngay). Nay giao diện nằm trong máy: sửa bất kỳ file nào trong
`erpnext/public/js/kho_pda*` hay `erpnext/public/scss/kho_pda.bundle.scss` thì
phải `scripts/pda/dong-goi.sh` → dựng lại APK → **cài lại từng máy quét**. Đây
là cái giá đã chốt của hướng "gói vào máy" (spec §3); Task 6 thêm dải nhắc cập
nhật trong app để 10 máy không phải đi từng cái bằng tay.

**Sửa NGHIỆP VỤ trên máy chủ (các hàm `@frappe.whitelist()` trong
`erpnext/warehouse_operations/vitri/`) KHÔNG cần dựng lại APK** — app gọi thẳng
các hàm đó, đổi là có hiệu lực ngay lần gọi kế tiếp.

---

## Phát một bản mới — quy trình, và CHỐT CHẶN trước khi giao APK

### A. Đánh số bản mới

Số hiệu app nằm ở **đúng một chỗ**: `versionName` trong
`pda_app/android/app/build.gradle`. Từ đó nó chảy ra hai nơi, và cả hai đều
quan trọng:

- **tên file APK** (`outputFileName` trong cùng file) →
  `miyano-pda-<versionName>-release.apk`;
- **`window.KHO_BAN_APP`** trong `www/cau-hinh.js`, do `scripts/pda/dong-goi.sh`
  đọc thẳng từ `build.gradle`.

Màn menu so hai thứ đó với nhau: nó lấy số trong **tên file** bản cài mới nhất
trên máy chủ và so với `KHO_BAN_APP` của chính nó. Vì vậy:

- **`versionName` phải là ĐÚNG HAI đoạn số, mỗi đoạn 1–3 chữ số** (`1.0`, `1.10`,
  `2.0`). `dong-goi.sh` **TỪ CHỐI DỰNG** nếu lệch khuôn — `2`, `1.0-beta`,
  `1.2.3`, `1000.0` đều bị chặn. Đây không phải sở thích: phía máy chủ chỉ có
  TÊN FILE để so, mà người phát hành **đã chứng minh họ dán NGÀY vào tên file**
  (bản đang phát hành tên `miyano-pda-1.0-kho-2026-09-24.apk`). Ba đoạn thì
  `24.09.26` (dd.mm.yy) không phân biệt được với một số hiệu ba đoạn, và một
  "số hiệu" đọc nhầm thành 24 sẽ bật dải nhắc **vĩnh viễn** trên mọi máy.
- Tăng `versionName` **trước khi** chạy `dong-goi.sh` (nếu không, bản đóng gói
  vẫn khai số cũ). `bench --site … run-tests --module
  erpnext.warehouse_operations.tests.test_giao_dien` có một bài đối chiếu đúng
  hai giá trị này và sẽ ĐỎ nếu quên.
- Cũng nên tăng `versionCode` (số nguyên) — Android từ chối cài đè một APK có
  `versionCode` thấp hơn hoặc bằng bản đang cài trên máy.
- **Giữ nguyên tên file khi tải lên hệ thống.** Từ vòng sửa cuối, máy chủ
  **TỪ CHỐI** một file `.apk` có chữ "pda" trong tên mà không rút được số hiệu
  (`cai_app.chan_ten_ban_cai_sai`, gắn vào `doc_events["File"]["validate"]`),
  và `ban_cai_moi_nhat` trả thêm `phien_ban` + `ly_do` cho các bản đã nằm sẵn
  trên máy chủ từ trước. App vẫn **im lặng** khi không rút được số hiệu — nhắc
  bừa còn tệ hơn không nhắc — nhưng sự im lặng đó nay có một cái tên ở phía máy
  chủ, thay vì chỉ lộ ra hàng tuần sau ngoài kho.
  Thêm được số hiệu vào phần đuôi thì thoải mái: `miyano-pda-1.1-kho-2026-10-01.apk`
  đọc ra `1.1`. Đừng để NGÀY đứng ở chỗ số hiệu.
- So sánh bằng **số từng đoạn**, không bằng chữ cái: `1.10` mới hơn `1.9`.

### B. Chốt chặn TRƯỚC KHI GIAO APK cho kho

Một bản dựng từ kho mã nguồn **luôn** trỏ vào site thử — đó là mặt an toàn của
mặc định, không phải một thiếu sót. Bốn việc dưới đây là thứ biến nó thành bản
phát hành; làm thiếu một việc là giao cho kho một app ghi vào dữ liệu thử.

1. **Sửa CẢ HAI khoá** trong `scripts/pda/cau-hinh-may-chu.json`:
   ```json
   "may_chu": "https://<máy chủ thật>",
   "may_chu_phat_hanh": "https://<máy chủ thật>"
   ```
   Hai khoá **bằng nhau** là điều kiện duy nhất tắt dải cam "BẢN THỬ". Sửa mỗi
   `may_chu` thì APK trỏ đúng máy chủ thật nhưng **vẫn mang dải cam** — và thủ
   kho được dạy rằng dải cam không có nghĩa gì.
2. **Dựng lại theo đúng thứ tự** (thứ tự này đã từng bị đảo và cho ra một APK
   mang giao diện của hôm trước):
   ```bash
   cd /home/hoangvietyeuem/frappe-bench-yhct/apps/erpnext
   bash scripts/pda/dong-goi.sh            # 1. bench build + chép vào www/
   cd pda_app
   export JAVA_HOME=~/opt/jdk17 ANDROID_HOME=~/opt/android-sdk
   npx cap sync android                    # 2. chép www/ sang android/.../assets/public
   cd android && ./gradlew assembleRelease  # 3. đóng gói + ký
   ```
   `npx cap sync` **chép**, nó không dựng. Chạy nó trước `dong-goi.sh` thì APK
   ra lò vẫn hợp lệ, vẫn ký được, vẫn cài được — và mang bản cũ.

   **Từ vòng sửa cuối, `dong-goi.sh` TỰ chép luôn sang
   `android/app/src/main/assets/public/`** (và dọn file mồ côi của lượt cũ —
   `scripts/pda/don_assets_public.py`), nên bản thứ ba đó không thể cũ hơn
   `www/` nữa. `npx cap sync android` **vẫn phải chạy**: nó còn làm việc khác
   (`capacitor.config.json`, `native-bridge.js`, cập nhật plugin, sinh
   `cordova.js`). Có một bài test đối chiếu hai thư mục từng byte
   (`test_task6_www_va_assets_public_khop_tung_byte`) chạy được ngay sau mỗi
   `dong-goi.sh`, không cần đợi có APK.
3. **Kiểm chữ ký VÀ mở bung APK.** Chữ ký:
   ```bash
   export PATH="$JAVA_HOME/bin:$PATH"
   ~/opt/android-sdk/build-tools/34.0.0/apksigner verify --print-certs \
     app/build/outputs/apk/release/miyano-pda-<phiên bản>-release.apk
   ```
   phải in `CN=Miyano PDA, …`. Nhưng chữ ký **không nói gì về nội dung** — nó
   chỉ nói "file này do ta ký". Phép kiểm nội dung là bài
   `test_task6_apk_mang_dung_ban_dong_goi` (trong
   `erpnext/warehouse_operations/tests/test_giao_dien.py`): nó mở bung APK và đối
   chiếu **md5** của `assets/public/{index.html, kho_pda.bundle.js,
   kho_pda.bundle.css, cau-hinh.js, shim.js}` với `pda_app/www/`, đọc
   `assets/capacitor.config.json` xem `CapacitorHttp` còn bật không, và so
   `assets/native-bridge.js` với bản trong `node_modules`. Chạy nó **sau** mỗi
   lần dựng. (Địa chỉ máy chủ nằm ở `assets/public/cau-hinh.js` chứ **không**
   ở `index.html` — `index.html` được git theo dõi nên nó cố ý không giữ địa
   chỉ nào.)
4. **Mở app lên và nhìn.** Màn quét thẻ phải: (a) **không** có dải cam "BẢN
   THỬ"; (b) dòng "Máy chủ:" ở cuối màn in đúng địa chỉ thật. Đây là hai chốt
   chặn bằng MẮT, và chúng đọc cùng một nguồn với lớp gọi mạng — không thể
   đúng chữ mà sai đường.

### C. Sau khi dựng: đưa lên hệ thống

Vào **Quản lý kho › Cài app PDA** → **Đưa bản cài lên** → chọn file APK, giữ
nguyên tên. Máy quét tải về từ `<địa chỉ kho>/tai-app`. Tên file **phải mang
chữ `pda`** (`vitri/cai_app.py: MAU_TEN`), và nên giữ nguyên khuôn gradle đặt
để dải nhắc trong app đọc được số hiệu (mục A).

### D. Trả file cấu hình về giá trị THỬ

Sau khi dựng xong bản phát hành, **trả `scripts/pda/cau-hinh-may-chu.json` về
địa chỉ thử** (`may_chu` = `http://192.168.61.129:8003`, `may_chu_phat_hanh`
= `""`). File này được git theo dõi; để địa chỉ thật nằm lại trong kho mã nguồn
là đúng thứ ràng buộc "không nhúng địa chỉ máy chủ thật vào kho" cấm — và lượt
dựng tiếp theo của bất kỳ ai sẽ lặng lẽ ra một bản trỏ máy chủ thật, không dải
cam nào cảnh báo. Có một bài test canh việc này
(`test_task6_ban_app_trong_ban_dong_goi_khop_versionName`).

### E. Lối ẩn khai địa chỉ máy chủ — khi nào dùng

Bấm giữ logo **MIYANO** ở màn quét thẻ **3 giây** → ô nhập địa chỉ → **Lưu và
mở lại**. Địa chỉ được cất trong máy và **ghi đè** địa chỉ đóng gói; `KhoApp
.goc()` đọc nó, nên dòng "Máy chủ:" và mọi lời gọi mạng đổi cùng lúc.

Đây **không** phải một thiết lập của thủ kho. Nó tồn tại cho đúng một ca: đường
vào kho là một đường hầm (ngrok) chạy trên một máy, hầm rớt là **mọi máy quét
chết cùng lúc**, và dựng lại APK rồi đi cài từng chiếc giữa ca là không kịp.

Luật kiểm địa chỉ (`vo.js::loi_dia_chi_may_chu`):
- phải là `https://` hoặc `http://`, phân tích được thành URL;
- **không** có đường dẫn/tham số phía sau tên miền — `goc()` được nối thẳng với
  `/api/method/…`;
- `http://` **chỉ** cho các host có trong
  `android/app/src/main/res/xml/network_security_config.xml`. Danh sách ấy được
  nhân bản trong `vo.js::_HOST_HTTP_CHO_PHEP` và **có một bài test đối chiếu hai
  nơi**. Lý do từ chối ở tầng JS chứ không để Android tự chặn: Android chặn
  trước khi mã của app chạy, và triệu chứng khi đó **y hệt "máy chủ chết"** —
  đúng cái tình huống lối ẩn sinh ra để chấm dứt.

Mở lại lối ẩn có nút **Bỏ địa chỉ gõ tay** để quay về địa chỉ đóng gói. Lối ẩn
không cần mạng nên nó luôn với tới được, kể cả khi đã gõ nhầm một địa chỉ chết.

---

## Kiểm giao diện: "cả hai lớp vẽ có đọc câu của lớp luồng không"

Kiến trúc tách lớp của `/kho` đứng vững nhờ MỘT phép thử: bọc `tao()` cho lớp
luồng trả một câu báo GIẢ, rồi kiểm cả hai lớp vẽ (app `/kho` và bốn trang Desk)
có hiện đúng câu đó không. Suốt sáu Task đầu nó là nghi thức làm tay; nay nó là
một kịch bản chạy được:

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench build --app erpnext        # BẮT BUỘC — /kho phục vụ bundle, không phục vụ file nguồn
cd apps/erpnext
node scripts/kiem_giao_dien/kiem_cau_chu.js            # mặc định http://192.168.61.129:8003
node scripts/kiem_giao_dien/kiem_cau_chu.js http://<máy-chủ-khác>
```

In `PASS`/`FAIL` cho 4 màn × 2 lớp vẽ, thoát khác 0 khi có lỗi. Không đăng nhập,
không ghi một dòng nào vào CSDL (lớp luồng giả không gọi máy chủ, và cả
`KhoApp.goi` lẫn `frappe.xcall` đều bị thay bằng hàm ném lỗi). Cần Playwright —
kịch bản tham chiếu thẳng bản đã cài của app `supplycore` cùng bench, cố ý KHÔNG
thêm gói vào `package.json` nào.

Chạy lại kịch bản này sau MỌI lần sửa câu chữ nghiệp vụ hay sửa một lớp vẽ: nó
là thứ duy nhất trong kho chặn được việc một lớp vẽ lặng lẽ tự kết luận lại thay
vì đọc kết luận của lớp luồng.

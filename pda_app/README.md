# pda_app — Vỏ Android cho PDA kho Miyano

Vỏ app Capacitor rỗng: một cửa sổ WebView bị khoá chỉ mở được máy chủ đã khai
(`allowNavigation` trong `capacitor.config.json`), nhớ địa chỉ máy chủ trong
`localStorage["pda_may_chu"]`, và khai ngoại lệ HTTP cho mạng nội bộ qua
`network_security_config.xml`. Toàn bộ nghiệp vụ (quét thẻ, xếp hàng, lấy hàng,
tra cứu, đặt ô hàng loạt...) nằm trên máy chủ Frappe/ERPNext; app không sao
chép bất kỳ logic nghiệp vụ nào.

## Cấu trúc

- `www/index.html` — màn hình duy nhất đóng gói trong app: khai/nhớ địa chỉ
  máy chủ, ping thử `<máy chủ>/api/method/ping`, rồi chuyển hẳn WebView sang
  `<máy chủ>/pda` (trang quét thẻ của Task 3). Cũng chính là màn lỗi mạng của
  app: `capacitor.config.json` khai `server.errorPath: "index.html"`, nên khi
  WebView lỗi mạng ở khung chính (mất wifi, sai địa chỉ...) Capacitor tự nạp
  lại đúng trang này thay vì trang lỗi mặc định của Chrome — có sẵn nút
  "Thử lại" và "Đổi máy chủ".
- `android/` — dự án Android sinh bởi `npx cap add android` (Task 5, bước 4).
- `capacitor.config.json` — cấu hình Capacitor: `appId`, `appName`,
  `allowNavigation` (hàng rào host được phép), `androidScheme: https`.

  **Luật khớp của `allowNavigation` (đọc từ mã Capacitor thật, không đoán —
  `node_modules/@capacitor/android/capacitor/src/main/java/com/getcapacitor/util/HostMask.java`,
  lớp `HostMask.Simple.matches()`):** khi mẫu có NHIỀU HƠN MỘT đoạn (tách bởi
  `.`), Capacitor đòi **số đoạn của mẫu phải bằng đúng số đoạn của host**
  (`if (maskSize > 1 && hostSize != maskSize) return false;`) — mẫu ít đoạn
  hơn host thì KHÔNG khớp, không phải một "tiền tố mở". Vì vậy:
  - `"192.168.*"` (3 đoạn) KHÔNG khớp `192.168.61.129` (4 đoạn) — phải viết
    đủ 4 đoạn: `"192.168.*.*"`.
  - `"10.*"` (2 đoạn) KHÔNG khớp `10.0.2.2` (4 đoạn, IP loopback chuẩn của
    Android Emulator vào máy chủ trên máy host) — phải viết
    `"10.*.*.*"`.
  - Mẫu đúng một đoạn (`"*"` một mình, hoặc một tên miền không có `*`) không
    bị luật này ràng buộc.

  **ĐỪNG rút gọn lại thành `192.168.*` / `10.*`** — trông gọn hơn nhưng sẽ
  không bao giờ khớp bất kỳ IP nội bộ thật nào, và hậu quả im lặng: Capacitor
  không báo lỗi, chỉ lặng lẽ mở host không khớp bằng **trình duyệt hệ thống
  ngoài app** thay vì nạp trong WebView — đúng lúc gõ đúng địa chỉ máy chủ
  thật thì app lại văng người dùng ra ngoài, ngược hẳn mục tiêu "cửa sổ bị
  khoá". Bằng chứng mô phỏng 5 cặp theo đúng thuật toán trên: xem mục
  "Sửa vòng 2" trong `.superpowers/sdd/2026-09-23-app-pda-apk/task-5-report.md`.

## Lệnh

```bash
npm install                 # cài @capacitor/core, @capacitor/cli, @capacitor/android
npm run them-android         # npx cap add android — sinh dự án Android
npm run dong-bo               # npx cap sync android — đồng bộ www/ + cấu hình vào Android
npm run mo-android            # npx cap open android — mở Android Studio (Task 6)
```

## Ghi chú

- Máy chủ thử hiện tại: `http://192.168.61.129:8003` (Host `erptest.local`).
- Đổi máy chủ: bấm nút "Đổi máy chủ" trên màn hình chờ đăng nhập trong app.
- Vì sao có `MainActivity.java` sửa tay: khi WebView đã rời `www/index.html`
  để nạp nguồn từ máy chủ, mọi JS của vỏ app (kể cả file này) không còn sống —
  không có cách nào bắt điều hướng `/login` từ JavaScript nữa. Việc bắt điều
  hướng `/login` → tự chuyển `/pda` (phiên 12 tiếng hết hạn giữa ca) vì vậy
  phải làm ở tầng Java bằng `WebViewClient`, xem
  `android/app/src/main/java/vn/com/miyano/pda/MainActivity.java`.

## Dựng lại file APK (Task 6)

**CHỐT CHẶN trước khi giao APK cho kho dùng thật:** hằng `MAC_DINH` trong
`www/index.html` mặc định trỏ `http://192.168.61.129:8003` — địa chỉ site
THỬ `erptest.local`, không phải máy chủ thật. Không có gì tự động ngăn việc
build và phát ra một APK vẫn còn trỏ vào site thử. Trước khi giao APK cho kho:
1. Sửa `MAC_DINH` sang địa chỉ máy chủ thật (xem "Đổi địa chỉ máy chủ mặc
   định" bên dưới — có thêm bước sửa `network_security_config.xml` nếu máy
   chủ thật chạy HTTP).
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

APK ra ở `pda_app/android/app/build/outputs/apk/release/app-release.apk`.
Kiểm APK đã ký thật (không phải ký debug tự động của Gradle):

```bash
export PATH="$JAVA_HOME/bin:$PATH"
~/opt/android-sdk/build-tools/34.0.0/apksigner verify --print-certs \
  android/app/build/outputs/apk/release/app-release.apk
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

1. Sửa hằng `MAC_DINH` trong `www/index.html` thành địa chỉ mới.
2. Thêm host mới vào mảng `allowNavigation` trong `capacitor.config.json` —
   đọc kỹ phần "Luật khớp của `allowNavigation`" ở trên trước khi gõ. Một tên
   miền đầy đủ như `"erp.miyano.com.vn"` khớp bình thường **không phải vì nó
   "chỉ có 1 đoạn"** — nó có đúng 4 đoạn (`erp`.`miyano`.`com`.`vn`) và host
   thật cũng có đúng 4 đoạn, nên luật "số đoạn mẫu phải bằng số đoạn host" tự
   thoả mãn khi gõ đủ tên miền. Ngược lại, một mẫu viết tắt như `"192.168.*"`
   (3 đoạn) thiếu đoạn so với host thật (4 đoạn) thì KHÔNG khớp. Luật này áp
   dụng như nhau cho cả domain lẫn IP: nếu sau này cần một mẫu wildcard theo
   subdomain (ví dụ `"*.miyano.com.vn"`), phải đếm cho đúng số đoạn của host
   định khớp, không được đoán theo cảm giác "gọn là được".
3. **Nếu máy chủ mới chạy HTTP thường (không phải HTTPS), phải thêm địa chỉ đó
   vào `android/app/src/main/res/xml/network_security_config.xml`** — file này
   hiện chỉ mở ngoại lệ cleartext cho đúng `192.168.61.129` và `10.0.2.2`, mọi
   host khác bị `<base-config cleartextTrafficPermitted="false" />` chặn.
   Thiếu bước này thì `allowNavigation` đã khớp, WebView được phép mở host mới,
   nhưng hệ điều hành vẫn chặn kết nối HTTP ở tầng mạng — cái ping trong
   `www/index.html` thất bại và người dùng chỉ thấy "không nối được máy chủ",
   không có manh mối gì chỉ ra đúng nguyên nhân. Máy chủ chạy HTTPS thật thì bỏ
   qua bước này.
4. Chạy lại đúng bốn lệnh dựng ở trên, phát hành APK mới cho các máy PDA.

**Sửa nghiệp vụ trên web (trang `/pda`, `/app/pda-home`, bốn trang nghiệp vụ)
KHÔNG cần dựng lại APK** — vỏ app chỉ là một WebView trỏ vào máy chủ, mọi thay
đổi trên các trang đó có hiệu lực ngay lần mở app kế tiếp, không cần build,
không cần phát APK mới, không cần cài lại trên từng máy quét.

# App PDA (APK Android) cho nghiệp vụ kho — thiết kế

Ngày: 23/09/2026 · Module: Warehouse Operations · Nền: các trang PDA sẵn có (`xep-hang-pda`, `lay-hang-pda`, `quet-ma-tra-cuu`, `dat-o-hang-loat`)

## 1. Yêu cầu (chủ đầu tư, 23/09/2026)

> "Tạo app cho PDA, app này sẽ sử dụng nghiệp vụ xếp hàng vào kho và lấy hàng, những phần liên quan đến nghiệp vụ quét PDA mình đã làm. Làm nó thành file APK rồi cài đặt, và phải liên kết in time với web."

## 2. Quyết định đã chốt

| Câu hỏi | Chốt |
|---|---|
| Kiểu app | **Bọc các trang PDA sẵn có thành APK** (Capacitor). Một nguồn nghiệp vụ duy nhất trên máy chủ |
| "In time với web" | **Ghi thẳng vào hệ thống như hiện nay** — quét xong web thấy ngay. Không bản sao dưới máy, không đồng bộ sau, không làm việc khi mất mạng |
| Máy chủ | Địa chỉ **khai được trong app**, mặc định `http://192.168.61.129:8003`; đổi sang tên miền HTTPS sau, không phải sửa mã |
| Thiết bị | Android có **súng quét gắn sẵn** (Zebra/Honeywell), kiểu bàn phím + Enter |
| Đăng nhập | **Quét thẻ nhân viên**, không PIN |
| Hạn phiên | **12 tiếng** (một ca), hết thì quét thẻ lại |
| Màn hình trong app | Xếp hàng vào ô · Lấy hàng · Quét mã tra cứu · Đặt ô trên tem hàng loạt |
| Mã nguồn app | Nằm **trong kho `erpnext`** |
| Dựng APK | **Trên máy này** (phải dọn ổ trước) |

## 3. Kiến trúc

App **không sao chép một dòng nghiệp vụ nào**. Mọi luật (đúng ô trên tem, FEFO, chốt thiếu, tem kiện, chặn duyệt) vẫn nằm ở máy chủ; app chỉ là một cửa sổ bị khoá vào đúng bốn trang đó.

```
APK (vỏ Capacitor)
 ├─ Bộ nhớ máy: địa chỉ máy chủ
 └─ WebView  →  https://<máy chủ>/pda          (chưa đăng nhập: quét thẻ)
                https://<máy chủ>/app/pda-home  (menu 4 nút)
                https://<máy chủ>/app/xep-hang-pda …
```

**Vì sao mọi màn hình đều nằm trên MÁY CHỦ, kể cả màn quét thẻ và menu** — không phải trang HTML gói trong app: phiên đăng nhập của Frappe là cookie. Trang gói trong app chạy ở nguồn `capacitor://localhost`, gọi sang máy chủ là **khác nguồn**, cookie không được đặt và không được gửi kèm; muốn chạy phải mở CORS + `SameSite=None` — nới lỏng bảo mật cho cả site chỉ để phục vụ một màn hình. Để tất cả trên máy chủ thì cùng một nguồn, cookie chạy đúng như trên trình duyệt, và sửa menu không phải cài lại APK.

Vỏ app vì thế rất mỏng, chỉ giữ bốn việc không làm được bằng web: chọn máy chủ, khoá điều hướng, nút Back, và ngoại lệ HTTP không mã hoá.

## 4. Vỏ app (Capacitor)

- **Capacitor 6** + `@capacitor/android`. Nhớ địa chỉ máy chủ bằng `localStorage` của
  `www/index.html` (khoá `pda_may_chu`) — **không** cài `@capacitor/preferences`: vỏ
  app chỉ có đúng một trang JS cần nhớ một chuỗi, `localStorage` sẵn có trong mọi
  WebView là đủ, cài thêm một gói Capacitor riêng cho việc này là thừa (sửa lại so
  với bản thiết kế ban đầu ở đây — mã đang chạy là mã đúng, spec viết trước khi
  quyết định bớt gói). Node 18 đã có sẵn trên máy.
- **Màn hình chọn máy chủ** (trang HTML gói trong app, chỉ hiện khi chưa khai hoặc khi bấm "Đổi máy chủ"): ô nhập địa chỉ, nút Kiểm tra (gọi `GET /api/method/ping`), nút Lưu. Lưu xong nạp `<máy chủ>/pda`.
- **Khoá điều hướng**: chỉ cho phép điều hướng cấp trang tới đúng máy chủ đã khai và đúng các đường dẫn `/pda`, `/login`, `/app/pda-home`, `/app/xep-hang-pda`, `/app/lay-hang-pda`, `/app/quet-ma-tra-cuu`, `/app/dat-o-hang-loat`. Địa chỉ khác mở bằng trình duyệt hệ thống. Tài nguyên cùng nguồn (JS, CSS, API) không bị chặn.
- **Rơi về màn quét thẻ**: WebView tới `/login` (phiên hết hạn hoặc bấm Đăng xuất) thì app tự chuyển sang `/pda`.
- **Nút Back**: dùng nguyên hành vi mặc định của Capacitor (lùi trong lịch sử WebView,
  thoát app khi hết lịch sử) — **không** có hộp thoại "Thoát app?" riêng (sửa lại so
  với bản thiết kế ban đầu ở đây). Lý do: sau khi WebView rời `www/index.html` sang
  nguồn máy chủ, JS của vỏ app không còn sống (cùng lý do khiến việc bắt "/login"
  phải chặn ở tầng Java, xem `MainActivity.java`) — không có JS nào của vỏ app còn
  chạy để tự bắt sự kiện Back và hỏi xác nhận; viết thêm việc đó phải chặn ở tầng
  Java, và chủ đầu tư không yêu cầu riêng nên giữ hành vi mặc định.
- **Mất mạng**: trang lỗi riêng của app, có nút Thử lại và nút Đổi máy chủ — không để WebView hiện trang lỗi mặc định của Chrome.
- **HTTP không mã hoá**: `network_security_config.xml` khai ngoại lệ cho dải nội bộ `192.168.0.0/16` (+ `10.0.0.0/8`), phần còn lại bắt buộc HTTPS. Khi có tên miền HTTPS thì ngoại lệ này thành thừa, không cản gì.
- Tên app **Miyano PDA**, biểu tượng riêng, khoá **màn dọc**, không cho phóng to thu nhỏ.

## 5. Đăng nhập bằng thẻ nhân viên

### 5.1 Sự thật phải ghi vào tài liệu vận hành

**Một tấm thẻ quét được là một chiếc chìa khoá.** Ai chụp được thẻ và in lại là vào được hệ thống với quyền của người đó. Thiết kế dưới đây làm cho chìa khoá đó **thu hồi được, có dấu vết, và không mở được gì ngoài kho** — chứ không làm nó hết là chìa khoá.

### 5.2 DocType `PDA Badge` (module Warehouse Operations)

| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `nguoi_dung` | Link User, bắt buộc, duy nhất | chủ thẻ; `autoname: field:nguoi_dung` |
| `ho_ten` | Data, read_only | lấy từ User, để in lên thẻ |
| `ma_bam` | Data, hidden, read_only | **SHA-256 của (muối + mã thẻ)** — không lưu mã gốc |
| `muoi` | Data, hidden, read_only, no_copy | muối ngẫu nhiên riêng của thẻ này (`secrets.token_hex(16)`), trộn vào mã trước khi băm — thêm sau bản thiết kế này, quyết định 23/09/2026 (đợt sửa cuối, mục 8): mỗi thẻ một muối để lộ CSDL không dò được hàng loạt thẻ bằng một bảng tra cứu chung |
| `con_hieu_luc` | Check, mặc định 1 | thu hồi = bỏ tick |
| `cap_luc` | Datetime, read_only | lần cấp gần nhất |
| `lan_dung_cuoi` | Datetime, read_only | lần quét thành công gần nhất |
| `thiet_bi_cuoi` | Data, read_only | `User-Agent` rút gọn của lần quét cuối |
| `ghi_chu` | Small Text | vd. "thẻ thay thế, mất 20/09" |

Quyền: chỉ **trưởng kho** đọc/ghi — tức `{"System Manager", "Stock Manager"}`, đúng tập mà `o_tem.VAI_TRO_DOI_O` đang dùng cho việc "đổi ô trên tem". Thủ kho (`Stock User`) **không** có quyền trên doctype này: người ta chỉ cầm tấm thẻ, không được tự cấp thẻ cho mình hay xem thẻ người khác.

`validate`: chủ thẻ phải `enabled = 1` và mang **vai trò kho** — tức một trong `System Manager`, `Stock Manager`, `Stock User` (đúng tập mà `VAI_TRO_DUOC_XEP`, `VAI_TRO_DUOC_LAY`, `VAI_TRO_DUOC_TRA_CUU` đang dùng; ba hằng số đó hiện giống hệt nhau, nên `the_pda.py` giữ **một** hằng `VAI_TRO_DUOC_DUNG_THE` và ghi rõ nó phải bằng hợp của ba tập kia). Cấp thẻ cho người không có vai trò kho là cấp một chìa khoá không mở được gì — chặn ngay lúc lưu, nói rõ lý do.

### 5.3 Cấp và thu hồi (`vitri/the_pda.py`)

- `cap_the(nguoi_dung)` — whitelist, chỉ trưởng kho (`{"System Manager", "Stock Manager"}`):
  - sinh mã **12 ký tự** từ bảng chữ `ABCDEFGHJKLMNPQRSTUVWXYZ23456789` (bỏ `O/0/I/1/L` để người đọc tay không nhầm) bằng `secrets.choice` → ~60 bit;
  - sinh một `muoi` ngẫu nhiên riêng (`secrets.token_hex(16)`), lưu `ma_bam = sha256(muoi + mã)`, đặt `cap_luc = now`, `con_hieu_luc = 1` (muối thêm sau bản thiết kế này, mục 5.2 ở trên);
  - trả **mã gốc đúng một lần** cho màn hình in. Máy chủ không lưu và không bao giờ trả lại lần thứ hai — mất thì cấp thẻ mới.
  - **đóng luôn phiên đang mở của `nguoi_dung`** (`clear_sessions(user=nguoi_dung, keep_current=True)`) — thêm sau bản thiết kế này: mất thẻ thì phản xạ tự nhiên là cấp lại ngay chứ không phải thu hồi trước, nên chỉ đóng phiên ở `thu_hoi` là chưa đủ.
- `thu_hoi(nguoi_dung)`: `con_hieu_luc = 0`. Thẻ chết ngay lập tức; phiên đang mở bị đóng (`frappe.sessions.clear_sessions(user=..., force=True)` — thiếu `force` thì chỉ dọn phiên quá hạn).
- Cấp lại cho người đã có thẻ = ghi đè `ma_bam`/`muoi` → thẻ cũ tự chết, VÀ phiên PDA đang mở bằng thẻ cũ bị đóng ngay (xem gạch đầu dòng thứ ba ở trên). Không có hai thẻ sống cùng lúc cho một người.

### 5.4 In thẻ

Dùng **đúng máy in tem và đúng khuôn tem 50×30 đang chạy** (`tem_lo.in_xap`, các ô F1…F11 — cùng cách tem kiện đã làm 22/09): mã vạch **Code128**, không dùng QR vì súng quét laser 1D không đọc được mã 2D.

| Ô | Nội dung |
|---|---|
| F1 | họ tên |
| F2 | tên đăng nhập |
| F3 | "THẺ PDA — KHO" |
| F5 | ngày cấp |
| F9 | chữ to: "PDA" |
| F10 / F11 | mã thẻ (mã vạch + chữ dưới mã vạch) |

Nút **Cấp thẻ & in** trên form `PDA Badge`. In xong đóng cửa sổ là mã gốc biến mất khỏi màn hình.

### 5.5 Đăng nhập (`/pda` + endpoint)

- **Trang `/pda`** (`erpnext/www/pda.html` + `pda.py`, cho phép khách): một ô nhập duy nhất, tự giữ focus, `inputmode="none"` (không bật bàn phím ảo) — súng quét bắn mã rồi Enter, đúng khuôn `OQuet` các trang PDA đang dùng. Có nút gõ tay cho lúc thẻ mờ.
- **Endpoint** `the_pda.dang_nhap_bang_the(ma)` — `@frappe.whitelist(allow_guest=True)`:
  1. chặn tần suất: `@frappe.rate_limit(limit=10, seconds=60)` — mặc định `ip_based=True`, tức 10 lần/phút cho mỗi IP, quá thì trả 429;
  2. **duyệt các thẻ `con_hieu_luc = 1`** (không tra thẳng bằng `WHERE ma_bam = sha256(ma)` được nữa, vì mỗi thẻ có muối riêng — thêm sau bản thiết kế này, mục 5.2), so từng thẻ bằng `hmac.compare_digest(sha256(muoi + ma), ma_bam)`; số thẻ cỡ vài chục nên duyệt hết là đủ nhanh; không khớp, thẻ đã thu hồi, hoặc chủ thẻ `disabled` → **một câu báo duy nhất** *"Thẻ không dùng được — báo trưởng kho"* (không phân biệt các ca, để không dò được thẻ nào có thật);
  3. kiểm lại vai trò kho (thẻ cũ của người đã đổi việc);
  4. `frappe.local.login_manager.login_as(user, session_end=<UTC now + 12h>.isoformat())` — đúng đường mà `frappe/www/login.py` dùng cho đăng nhập bằng liên kết email;
  5. ghi `lan_dung_cuoi`, `thiet_bi_cuoi`; Frappe tự ghi `Activity Log` qua `on_login`;
  6. trả `{"ok": 1, "di_toi": "/app/pda-home"}`.
- Quét sai ghi một dòng `Error Log` tiêu đề `vi_tri_kho: the_pda sai ma` kèm IP — để còn biết có ai đang dò.

### 5.6 Hạn phiên

`session_end` là mốc thời gian tuyệt đối trong phiên (`frappe/sessions.py` so với giờ UTC hiện tại). 12 tiếng kể từ lúc quét thẻ, **không gia hạn khi dùng tiếp** — hết ca là hết, ca sau quét thẻ của mình, nên cột "người lấy" trên phiếu luôn đúng người.

## 6. Trang chính trong app (`pda-home`)

Desk page mới, dựng theo khuôn các trang PDA đang có (CSS riêng, nút cao ≥ 44px): bốn nút lớn, tên người đang đăng nhập, và nút **Đăng xuất**. Trang này cũng mở được từ trình duyệt máy tính — không có gì chỉ chạy trong app.

(Sửa lại so với bản thiết kế ban đầu ở đây: mã đang chạy chỉ hiện **tên người**, không
hiện "kho đang làm" — một người dùng có thể thao tác nhiều kho khác nhau trong cùng
một phiên, không có khái niệm "kho đang làm" gắn với phiên đăng nhập.)

> "Đặt ô trên tem hàng loạt" là bảng rộng, trên màn 4 inch sẽ chật. Vẫn đưa vào theo yêu cầu, nhưng nút có chú thích *"nên dùng trên máy tính"*.

## 7. Chỗ đặt mã nguồn

```
pda_app/                      ← vỏ Capacitor (mới, nằm trong kho erpnext)
  package.json  capacitor.config.ts  README.md
  www/index.html              ← màn chọn máy chủ + trang lỗi mất mạng
  android/                    ← dự án Android do Capacitor sinh (có commit)
erpnext/www/pda.{html,py}                            ← trang quét thẻ
erpnext/warehouse_operations/page/pda_home/          ← menu 4 nút
erpnext/warehouse_operations/doctype/pda_badge/      ← thẻ + nút cấp/in
erpnext/warehouse_operations/vitri/the_pda.py        ← cấp, thu hồi, đăng nhập
erpnext/warehouse_operations/tests/test_the_pda.py
```

`pda_app/` là thư mục cấp đỉnh mới nên **phải thêm một dòng vào `RULES` trong `scripts/file_structure/gate.py`** rồi chạy `python3 -m scripts.file_structure --audit` (phải ra 0 vi phạm) — đúng cách tài liệu `code_structure` đã dặn. Không commit `android/build`, `android/.gradle`, `node_modules`, và **không bao giờ commit khoá ký**.

## 8. Dựng APK trên máy này

1. **Dọn ổ** (đang còn 7,5 GB / 92% đã dùng): `yarn cache clean` (4,6 GB), `~/.cache/uv` (933 MB), `~/.cache/pip` (169 MB), cache Chrome (1,1 GB) — tất cả đều tự tải lại được. Giữ `~/.cache/ms-playwright` vì đang dùng để kiểm thử.
2. **JDK 17 dạng tarball** giải nén vào `~/opt/jdk17` — không cần `sudo`.
3. **Android commandline-tools** vào `~/opt/android-sdk`; cài đúng `platform-tools`, `platforms;android-34`, `build-tools;34.0.0`. **Không cài emulator và system image** (mỗi cái vài GB, mà máy cũng không đủ RAM để chạy).
4. `npm install && npx cap add android && npx cap sync android`.
5. Khoá ký `~/keys/miyano-pda.keystore` (ngoài kho mã nguồn), `./gradlew assembleRelease`.
6. Kết quả: `pda_app/android/app/build/outputs/apk/release/app-release.apk` → chép sang PDA cài, hoặc `adb install`.

Cập nhật về sau: sửa nghiệp vụ trên web thì PDA có ngay, **không cài lại**; chỉ khi đổi vỏ app (địa chỉ mặc định, khoá điều hướng, biểu tượng) mới phải dựng và cài lại APK.

## 9. Ngoài phạm vi

- Làm việc khi mất mạng (offline) và đồng bộ sau — trái với "in time" đã chốt.
- Đẩy tin tức tức thời qua socket (màn hình tự tươi khi người khác sửa).
- iOS, Play Store, cập nhật tự động trong app.
- Tích hợp DataWedge kiểu intent (đang dùng kiểu bàn phím, chạy tốt).
- Đổi bất kỳ luật nghiệp vụ nào của xếp hàng / lấy hàng.

## 10. Kiểm thử

**Máy chủ (`test_the_pda.py`)**
- Cấp thẻ: trả mã 12 ký tự, chỉ lưu bản băm, mã gốc không nằm trong cơ sở dữ liệu.
- Quét mã đúng → đăng nhập đúng người, `session_end` cách hiện tại 12 tiếng (sai số vài giây).
- Mã sai / thẻ đã thu hồi / chủ thẻ bị khoá / chủ thẻ mất vai trò kho → cùng một câu báo, không đăng nhập.
- Cấp lại thẻ → mã cũ hết tác dụng ngay, VÀ phiên đang mở bằng mã cũ bị đóng (thêm sau bản
  thiết kế này, mục 4 đợt sửa cuối) — kiểm bằng bảng `Sessions` của chủ thẻ.
- Thu hồi → phiên đang mở bị đóng — kiểm bằng bảng `Sessions`, không chỉ cờ `con_hieu_luc`
  (thêm sau bản thiết kế này, mục 5 đợt sửa cuối).
- Mỗi thẻ một muối riêng (`muoi`) — băm không còn tra được thẳng bằng `ma_bam` trần
  (thêm sau bản thiết kế này, mục 8 đợt sửa cuối).
- Chặn tần suất: quá 10 lần/phút một IP thì bị chặn.
- Cấp thẻ cho người không có vai trò kho → chặn lúc lưu.
- Người không phải quản lý gọi `cap_the` → `PermissionError`.

**Giao diện (`test_giao_dien.py`)** — trang `/pda` và page `pda-home` tồn tại, thuộc đúng module; các đường dẫn app khoá đúng tên trang; nhãn nút trên form thẻ khớp hằng số máy chủ; endpoint `dang_nhap_bang_the` mà `pda.html` gọi có thật và còn `@frappe.whitelist` (thêm sau bản thiết kế này, mục 6 đợt sửa cuối).

**Playwright trên erptest** — mở `/pda`, "bắn" mã như súng quét → vào `/app/pda-home` → mở được trang lấy hàng, đúng tên người đăng nhập; thẻ thu hồi thì bị chặn.

**APK** — máy này không có thiết bị Android và không đủ ổ để dựng máy ảo, nên **phần cầm máy quét thật do chủ đầu tư thử**, theo bảng kiểm: cài đặt, khai máy chủ, quét thẻ, xếp một thùng, lấy một phiếu, rút mạng xem báo lỗi, để quá 12 tiếng xem có bắt quét thẻ lại.

## 11. Rủi ro đã biết

| Rủi ro | Cách giảm |
|---|---|
| Thẻ bị chụp ảnh, in lại | thu hồi được ngay; chỉ mở được phần kho; có nhật ký; phiên 12 tiếng |
| Máy chủ chạy HTTP trong mạng nội bộ | ngoại lệ chỉ cho dải nội bộ; chuyển HTTPS khi có tên miền |
| Ổ đĩa chật | chỉ cài đúng gói SDK cần, không emulator |
| Không kiểm được APK tại chỗ | bảng kiểm tay cho chủ đầu tư; mọi thứ khác đều có test tự động |
| "Đặt ô hàng loạt" chật trên màn PDA | giữ nút nhưng ghi rõ nên dùng trên máy tính |

## 12. Thứ tự thi công

1. Thẻ PDA phía máy chủ: doctype, cấp/thu hồi, in thẻ + test.
2. Trang `/pda` và endpoint đăng nhập, phiên 12 tiếng + test.
3. Trang `pda-home` (menu 4 nút) + test giao diện.
4. Vỏ app Capacitor: chọn máy chủ, khoá điều hướng, trang lỗi, nút Back.
5. Dựng môi trường Android, build APK ký sẵn, bảng kiểm tay.
6. Tài liệu vận hành: cấp thẻ, mất thẻ, cài app, đổi máy chủ.

Mỗi phần chạy đủ test của module trước khi sang phần sau.

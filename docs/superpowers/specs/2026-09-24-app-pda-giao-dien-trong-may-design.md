# App PDA: giao diện nằm trong máy — thiết kế

Ngày: 24/09/2026 · Module: Warehouse Operations + `pda_app/` · Nền: giao diện `/kho` đã xong (spec 2026-09-23-giao-dien-app-kho-pda-design.md)

## 1. Yêu cầu (chủ đầu tư, 24/09/2026)

> "Anh muốn nó là app cho điện thoại chứ em vẫn đang đăng nhập vào web."

Đợt trước dựng giao diện riêng ở `/kho`, nhưng app vẫn là một khung trình duyệt: mở lên thấy **màn khai địa chỉ máy chủ**, rồi **màn đăng nhập**, rồi chờ tải trang. Đúng nhịp của web, không phải nhịp của app.

Chủ đầu tư cũng cho biết hệ thống **đang mở ra internet qua ngrok** (`https://blockishly-unvowed-anglea.ngrok-free.dev`) và chốt: **dùng địa chỉ public, không dùng nội bộ**.

## 2. Quyết định đã chốt

| Câu hỏi | Chốt | Ghi chú |
|---|---|---|
| Giao diện nằm ở đâu | **Trong máy** (gói vào APK) | Đổi lại: sửa giao diện phải cài lại từng máy |
| Quét thẻ khi nào | **Một lần khi nhận máy** | Máy giữ danh tính vĩnh viễn cho tới khi thu hồi |
| Địa chỉ máy chủ | **Một địa chỉ HTTPS public duy nhất**, nhúng cứng | Không dự phòng IP nội bộ |
| Màn khai máy chủ | **Bỏ khỏi luồng thường**, chỉ còn lối ẩn | Bấm giữ logo 3 giây |
| Bản `/kho` trên web | **Giữ** | Để thử nhanh và làm đường lùi khi app hỏng |

## 3. Đính chính một kết luận sai của đợt trước

Spec 23/09 §33 viết: *"giao diện trong máy gọi sang máy chủ là khác nguồn — phải mở CORS cho cả hệ thống và tự quản lý khoá API"*. **Nửa đầu sai.**

Capacitor 6 có `CapacitorHttp` (`@capacitor/core@6`, đã kiểm trong `node_modules`): bật lên thì `fetch`/`XMLHttpRequest` được vá để đi qua **tầng native của Android**, không qua trình duyệt, nên **không dính luật cùng-nguồn** — không phải mở CORS gì hết.

Nửa sau đúng: vẫn phải tự quản lý khoá. Cái giá thật của hướng "gói vào máy" là **cài lại từng máy khi sửa giao diện**, không phải CORS. Quyết định 23/09 được ra dựa trên một cái giá cao hơn thực tế.

## 4. Kiến trúc

```
APK
 ├─ www/                     ← bản dựng của giao diện /kho, CHÉP vào lúc đóng gói
 │   ├─ index.html           ← vỏ tối thiểu (không phải trang Frappe)
 │   ├─ kho_pda.bundle.js    ← chép từ sites/assets/erpnext/dist/js/
 │   ├─ kho_pda.bundle.css   ← chép từ dist/css/
 │   ├─ vendor/jquery.min.js
 │   └─ shim.js              ← các toàn cục Frappe mà màn hình cần (xem §5)
 ├─ CapacitorHttp bật        ← mọi lời gọi đi native, không CORS
 └─ Preferences (native)     ← nơi cất khoá máy
        ↕ HTTPS
   Máy chủ: chỉ còn các hàm `@frappe.whitelist()` sẵn có
```

**Một nguồn mã duy nhất.** Giao diện vẫn được viết và dựng trong `apps/erpnext` như hôm nay (`kho_pda.bundle.js`); bước đóng gói **chép bản đã dựng** vào `pda_app/www/`. Không có bản sao thứ hai của mã nguồn — chép bản build, không chép source.

**Trang `/kho` trên web giữ nguyên**, dùng chung đúng bundle đó. Sửa một lần, hai nơi cùng đổi; chỉ khác là web nhận ngay còn máy quét phải cài lại.

## 5. Những toàn cục mà giao diện đang dựa vào

Đo bằng grep trên mã thật của bốn màn + bốn lớp luồng:

| Toàn cục | Số lần dùng | Trong app lấy từ đâu |
|---|---|---|
| `__()` | 142 | shim: trả nguyên chuỗi (hệ thống dùng tiếng Việt, không có bản dịch thứ hai) |
| `flt()` | 48 | shim |
| `$()` jQuery | 28 | gói jQuery vào APK |
| `frappe.utils.escape_html` | 11 | shim |
| `frappe.datetime.str_to_user` | 5 | shim |
| `frappe.datetime.now_time` / `get_today` / `get_day_diff` | 9 | **xem §8 — lấy từ máy chủ, không lấy từ máy** |
| `frappe.utils.icon` | 1 | shim (trả SVG rỗng hoặc chép hàm gốc) |

Tập này **nhỏ và đếm được**, nên hướng chính là **viết shim (~60 dòng)** thay vì gói cả `frappe-web.bundle.js` — bundle đó còn kéo theo socket.io, `frappe.boot`, cơ chế phiên của web, tức kéo lại đúng cái "web" mà đợt này muốn bỏ.

**Rủi ro phải đo trước khi thi công:** nếu shim bỏ sót một toàn cục thì màn đó chết lúc chạy mà không có bài test nào bắt. Việc đầu tiên của kế hoạch là **dựng shim rồi chạy cổng `scripts/kiem_giao_dien/kiem_cau_chu.js` trên bản đóng gói** — cổng đó đi qua đúng ô quét thật của cả bốn màn.

## 6. Đăng nhập một lần

**Lúc nhận máy:** app mở lần đầu → màn quét thẻ → gọi `the_pda.dang_nhap_bang_the(ma)` → máy chủ trả về **khoá máy** → app cất vào `Preferences` của Android → từ đó chạm icon là vào thẳng menu.

**Khoá máy dùng cơ chế sẵn có của Frappe**, không tự phát minh: `Authorization: token <api_key>:<api_secret>` (`frappe/auth.py:674 validate_auth_via_api_keys`), khoá sinh bằng `frappe.core.doctype.user.user.generate_keys(user)` (`user.py:1332`). Đây là đường Frappe thiết kế sẵn cho client ngoài, không phải mẹo.

**Máy chủ phải thêm:** một hàm whitelist `the_pda.cap_khoa_may(ma_the, ten_may)` — kiểm thẻ như `dang_nhap_bang_the` đang làm, rồi sinh/trả khoá và ghi lại máy nào đang cầm.

**Doctype mới `PDA Thiet Bi`**: `nguoi_dung`, `ten_may`, `ma_may` (Android ID), `cap_luc`, `lan_dung_cuoi`, `con_hieu_luc`, `ghi_chu`. Không lưu khoá thô — để trưởng kho biết **ai đang cầm máy nào**, thứ hiện không ai trả lời được.

**Thu hồi:** nút "Thu hồi thẻ" sẵn có trên `PDA Badge` phải **xoá luôn `api_secret`** của người đó. Máy mất khoá → mọi lời gọi trả 401 → app rơi về màn quét thẻ. Thêm nút "Thu hồi máy" trên `PDA Thiet Bi` cho ca mất đúng một máy.

## 7. Đánh đổi an toàn — nói rõ một lần

Máy giữ danh tính vĩnh viễn **cộng với** ERP mở ra internet qua ngrok:

| | Mạng nội bộ | Có ngrok (đang dùng) |
|---|---|---|
| Mất máy | Kẻ nhặt được phải **vào tận kho** | Dùng được **từ bất cứ đâu** |
| Cho tới khi | Có người thu hồi thẻ | Có người thu hồi thẻ |

`api_secret` cho phép gọi **mọi hàm whitelist dưới tên người đó** — đúng bằng quyền một phiên đăng nhập, chỉ khác là không hết hạn. Vai trò kho đã hẹp (không đọc được Address, xem spec sửa quyền 24/09), nhưng nó **ghi được sổ vị trí và duyệt được phiếu giao**.

**Ba việc bắt buộc đi kèm**, không phải tuỳ chọn:
1. Thu hồi phải **giết được máy ngay**, và trưởng kho phải biết chỗ bấm — tài liệu phải có.
2. Danh sách "máy đang cầm thẻ" để biết mất cái nào.
3. Mã máy (Android ID) gửi kèm mỗi lời gọi; máy chủ từ chối nếu khoá dùng từ máy khác. Chặn được ca chép khoá sang máy khác, không chặn được ca mất nguyên máy.

**Không đưa vào:** mã PIN (chủ đầu tư đã loại 23/09), hết hạn theo ca (đã loại 24/09).

### Chặn được gì / KHÔNG chặn được gì — ba hệ quả phải khai (bổ sung sau khi thi công Task 3)

1. **Ai đã nhận máy PDA thì khoá API của người đó chỉ dùng được TỪ CHIẾC MÁY ĐÓ.** Ràng buộc mã máy nằm ở `auth_hooks` (cửa vào của mọi request), nên nó áp cho **mọi** lời gọi mang `Authorization` của người đó — kể cả một tích hợp hay script ngoài vẫn đang chạy bằng chính khoá ấy. Tích hợp đó sẽ chết bằng **401** kèm câu *"Máy chưa được cấp quyền…"*, và người vận hành không có manh mối nào nếu không đọc dòng này. **Trước khi bật trên site thật: kiểm xem có ai đang dùng `api_key` cho tích hợp mà sắp được cấp máy PDA không.**

2. **Cấp máy PDA cho một người đang có khoá API LẠ bị TỪ CHỐI** (siết ở vòng sửa 2, thay cho việc chỉ ghi log). `generate_keys` (`user.py:1332`) giữ nguyên `api_key` cũ và **luôn xoay `api_secret`**, nên cấp máy sẽ giết tích hợp đang dùng khoá đó — **tức thì và không hoàn nguyên được** (bí mật cũ không lưu ở đâu để trả lại). Mà `cap_khoa_may` là `allow_guest=True` và tự nâng quyền lên Administrator bên trong, nên nếu chỉ "báo" thì **một mã thẻ rò rỉ đủ để giết khoá tích hợp của đúng người đó mà không cần đăng nhập**. Với hành động không đảo ngược được, mặc định là **từ chối**.
   - **Lối thoát, cố ý và một lần:** ô `Cho phép đè khoá API có sẵn` trên `PDA Badge` (chỉ `System Manager`/`Stock Manager` ghi được doctype này). Bật xong, lần cấp kế tiếp đi qua được rồi **cờ tự tắt** — mở sẵn vĩnh viễn thì lệnh chặn thành vô nghĩa.
   - **Không chặn ca ĐỔI MÁY:** nếu chiếc khoá đang có chính là khoá PDA đã cấp thì xoay nó là việc bình thường của cơ chế này. Phép phân biệt là `_khoa_co_phai_do_pda_cap`, ba vế (§dưới).
   - Khi đã đè (có cờ): `PDA Thiet Bi` bật `Khoá API vốn có TỪ TRƯỚC`, ghi một dòng `Error Log`, và thu hồi **không** xoá chiếc khoá đó.

2b. **Thu hồi chỉ xoá chiếc khoá PDA thật sự đã cấp — ba vế.** (a) `User.api_key` khớp `api_key_da_cap` đã ghi; (b) máy đó `khoa_von_co_truoc = 0`; (c) **dấu vân tay của `api_secret` hiện tại khớp cái ghi lúc cấp** (SHA-256 có muối; **không lưu bí mật**). Vế (c) đóng ca *nhận máy trước, xoay khoá ở Desk sau*: định danh `api_key` **bất biến** qua mọi lần xoay nên hai vế đầu vẫn trả "đúng" trong khi chiếc khoá đang sống là chiếc PDA chưa bao giờ cấp. Thiếu dấu vân tay (máy cấp trước vòng sửa 2) thì fail-closed: **không xoá**, và cũng **không cho đè** — quét lại thẻ trên chiếc máy cũ đó sẽ bị chặn cho tới khi trưởng kho tick ô lối thoát đúng một lần.
   - **KHÔNG viết patch backfill dấu vân tay.** Viết thì **được** (bí mật nằm trong `__Auth`, `get_decrypted_password` đọc ra được — chính hàm kiểm đang gọi nó mỗi lần). Nhưng backfill buộc phải **giả định** bí mật đang sống chính là bí mật PDA đã cấp — đúng cái giả định mà dấu vân tay sinh ra để bác bỏ. Backfill = mở lại lỗ hổng "xoay khoá ở Desk sau" cho toàn bộ dòng cũ, **im lặng**. Vì vậy: không nên, chứ không phải không thể.
   - **Trước khi bật trên site thật:** chạy `SELECT COUNT(*) FROM \`tabPDA Thiet Bi\``. Bằng **0** thì vấn đề này **không tồn tại**. Khác 0 thì mỗi máy cũ chỉ cần tick ô lối thoát **đúng một lần** lúc quét lại (từ vòng sửa 3 thì đúng là một lần thật — trước đó là mỗi lần). Ghi chú kỹ thuật: bảng `__Auth` của bản Frappe này **không có cột `modified`** (đo: `SHOW COLUMNS` trả `doctype, name, fieldname, password, encrypted`), nên không thể so mốc thời gian của bí mật — đó là lý do phải dùng dấu vân tay.

3. **`bearer` (OAuth) KHÔNG bị ràng buộc mã máy.** Hôm nay vô hại: `validate_oauth` tra tài liệu `OAuth Bearer Token` chứ không nhận cặp `api_key:api_secret`, nên một khoá PDA rò ra **không thể** phát lại dưới dạng bearer; và site hiện có `OAuth Client` = 0. Nhưng nếu sau này bật OAuth, bearer token của chính thủ kho sẽ đi qua cửa mà không bị hỏi máy nào. Đó là một cửa có sẵn của Frappe, không phải cửa do thiết kế này mở — người bật OAuth phải quay lại chỗ này.

## 8. Ngày giờ — chỗ dễ sai lặp lại

Đợt trước đã vấp một lần: lớp luồng lẳng lặng đổi từ giờ máy chủ sang giờ máy trạm, làm **phán quyết hết hạn của lô vật tư y tế** đổi nghĩa. Đã chữa bằng cách tiêm `gio`/`ngay` từ ngoài.

Trong app, máy Android **không đảm bảo đúng giờ**. Vì vậy: lúc mở app, lấy ngày/giờ máy chủ một lần và tiêm vào `tao({goi, gio, ngay})`; lệch quá một ngưỡng thì hiện cảnh báo. **Không được** để `new Date()` của máy đi vào phán quyết hết hạn.

## 9. Địa chỉ máy chủ

Nhúng cứng **một** địa chỉ HTTPS. Không màn khai địa chỉ trong luồng thường.

**Rủi ro chủ đầu tư đã chấp nhận:** ngrok là đường hầm chạy trên máy; tắt máy hoặc rớt hầm là **mọi máy quét chết cùng lúc**, không đường lùi. Vì vậy vẫn giữ **một lối ẩn**: bấm giữ logo 3 giây ra màn khai địa chỉ. Không phải để dùng hằng ngày — để một người biết việc cứu được máy mà không phải cài lại.

Trước khi phát cho cả tổ: đổi địa chỉ sang máy chủ thật rồi **dựng lại APK**. Bản hiện tại trỏ máy chủ thử — thủ kho cài nhầm thì mọi thao tác ghi vào dữ liệu thử mà không ai biết.

## 10. Cập nhật app

Giao diện nằm trong máy nên sửa là phải cài lại. Để 10 máy không phải đi từng cái bằng tay:

- app mở lên gọi `cai_app.ban_cai_moi_nhat` (đã có), so với phiên bản của chính nó;
- có bản mới thì hiện một dải nhắc kèm nút mở trang tải — **không tự tải, không tự cài**;
- tài liệu ghi rõ quy trình phát bản mới.

## 11. Phạm vi

**Trong phạm vi:** vỏ APK đóng gói giao diện; shim toàn cục; `CapacitorHttp`; cấp/lưu/thu hồi khoá máy; doctype `PDA Thiet Bi`; nhắc cập nhật; tài liệu phát máy và thu hồi.

**Ngoài phạm vi:**
- Làm việc khi mất mạng (app mở được, nhưng mọi việc đều cần máy chủ).
- In tem từ máy quét.
- Đổi bất kỳ luật nghiệp vụ nào — bốn màn giữ nguyên hành vi.
- Quét bằng camera (máy kho có súng quét cứng).
- Bỏ trang `/kho` trên web hoặc bốn trang Desk.
- Dời ngrok sang hạ tầng khác — là việc hạ tầng, đáng bàn riêng.

## 12. Rủi ro đã biết

| Rủi ro | Cách giảm |
|---|---|
| Shim bỏ sót toàn cục → màn chết lúc chạy | Việc đầu tiên: chạy cổng `kiem_cau_chu.js` trên bản đóng gói, cả bốn màn |
| Mất máy = mất danh tính cho tới khi thu hồi | Thu hồi giết khoá ngay; danh sách máy; khoá gắn mã máy |
| Rớt ngrok = chết toàn bộ máy quét | Lối ẩn khai lại địa chỉ (bấm giữ logo) |
| Sửa giao diện = đi cài lại 10 máy | Nhắc cập nhật trong app; phát bản qua `/tai-app` |
| Giờ máy Android sai → phán quyết hết hạn sai | Tiêm ngày/giờ máy chủ, cảnh báo khi lệch |
| Hai bản giao diện (web `/kho` và trong máy) trôi khỏi nhau | Chỉ chép **bản dựng**, không chép source; cùng một `kho_pda.bundle.js` |
| Chưa ai cầm máy PDA thật thử | Bảng kiểm tay đã có (`HDSD-thu-app-pda-tren-may-that.md`); đợt này thêm mục cài–nhận máy–thu hồi |

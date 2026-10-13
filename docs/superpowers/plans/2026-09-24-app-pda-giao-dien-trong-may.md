# App PDA: giao diện nằm trong máy — kế hoạch thi công

> **Cho người thi công:** dùng `superpowers:subagent-driven-development` hoặc `superpowers:executing-plans`, làm từng Task. Mỗi bước có ô `- [ ]`.

**Mục tiêu:** chạm icon là vào thẳng menu bốn việc — không màn khai máy chủ, không màn đăng nhập, không chờ tải trang web.

**Kiến trúc:** APK đóng gói **bản dựng** của giao diện `/kho` (không chép mã nguồn); lời gọi mạng đi qua `CapacitorHttp` (native, không CORS); đăng nhập một lần bằng thẻ rồi máy giữ khoá API của Frappe.

**Tech Stack:** Capacitor 6 (`@capacitor/core` + `@capacitor/android`, đã có), JS thuần, jQuery gói kèm, esbuild sẵn có của bench.

**Spec:** `docs/superpowers/specs/2026-09-24-app-pda-giao-dien-trong-may-design.md`

## Global Constraints

- **KHÔNG tự commit.** CLAUDE.md: thao tác git chỉ làm khi chủ đầu tư yêu cầu đúng lần đó. Mỗi Task kết bằng "báo cáo".
- **MỘT bundle cho cả hai nơi.** Trang `/kho` trên web và app dùng **cùng một** `kho_pda.bundle.js`. Phân biệt môi trường bằng **biến toàn cục do vỏ đặt**, không bằng hai bản mã. Chép **bản dựng**, không bao giờ chép mã nguồn sang `pda_app/`.
- **Không đổi luật nghiệp vụ.** Bốn màn giữ nguyên hành vi. Thấy lỗi nghiệp vụ thì BÁO.
- **Khoá ký APK nằm ngoài kho** (`~/keys/`). Tuyệt đối không chép khoá/mật khẩu vào kho, tài liệu hay báo cáo.
- **Không nhúng địa chỉ máy chủ thật vào mã nguồn kho.** Địa chỉ nằm trong **một file cấu hình của bước đóng gói**; kho chỉ giữ địa chỉ thử.
- JS thụt **tab**, chuỗi nháy kép; Python thụt tab, ≤110 ký tự. Chú thích tiếng Việt nói **VÌ SAO** và **phải mô tả đúng điều mã làm**.
- Bench `/home/hoangvietyeuem/frappe-bench-yhct`, site thử `erptest.local`, máy chủ dev `http://192.168.61.129:8003`, địa chỉ public `https://blockishly-unvowed-anglea.ngrok-free.dev`.
- **Trước mỗi lần chạy test: xoá `Location Transfer` nháp và phiếu giao nháp còn sót.** Bốn người liên tiếp đã vấp bẫy này.
- **Giữ nguyên bộ dữ liệu thử `THU-`/`3T`/`3U` và thẻ `SGRL79WAQF3W`** — chủ đầu tư đang dùng để thử tay.
- `test_gan_vi_tri` **đỏ sẵn từ trước** — không phải hồi quy, đừng sửa.

### Bốn luật đã trả giá ở đợt `/kho`, giữ nguyên

1. Trình nghe uỷ quyền gắn lên phần tử **con** dựng lại mỗi lượt vẽ, không lên `$than`.
2. Lớp vẽ chỉ **đọc** kết luận của lớp luồng. Phép thử: `scripts/kiem_giao_dien/kiem_cau_chu.js`.
3. Chốt chống bấm lại nằm ở `erpnext.kho_pda.hoi()`, một chỗ. **Giữ biến đếm tầng** làm lưới tầng dưới.
4. Ngày/giờ đi vào lớp luồng bằng **tham số tiêm**, không bao giờ bằng `new Date()` của máy.

---

### Task 1: Đóng gói giao diện vào `www/` + shim toàn cục

**Files:**
- Create: `pda_app/www/shim.js`, `pda_app/www/vendor/jquery.min.js`
- Create: `scripts/pda/dong-goi.sh` (script chép bản dựng vào `pda_app/www/`)
- Create: `scripts/pda/cau-hinh-may-chu.json` (địa chỉ máy chủ, **chỉ địa chỉ thử** trong kho)
- Modify: `pda_app/www/index.html` (thành vỏ tĩnh, không còn màn khai máy chủ)
- Modify: `pda_app/.gitignore` (bỏ qua bản dựng chép vào `www/`)
- Create: `scripts/kiem_giao_dien/kiem_ban_dong_goi.js`

**Interfaces:**
- Produces cho Task 2–6: `window.KHO_MAY_CHU` (chuỗi địa chỉ gốc, ví dụ `"https://…ngrok-free.dev"`) — **chỉ có mặt trong app**, không có trên web; `window.KHO_LA_APP === true` trong app.
- Produces: `pda_app/www/kho_pda.bundle.js` + `.css` (bản chép, không theo dõi trong git).

- [ ] **Bước 1: Viết bài kiểm trước** — `scripts/kiem_giao_dien/kiem_ban_dong_goi.js`: mở `pda_app/www/index.html` bằng Playwright qua `file://`, vẽ **cả bốn màn** bằng lớp luồng thật + máy chủ giả, in PASS/FAIL từng màn. Chạy khi chưa có `shim.js` → phải FAIL.

```javascript
// Cổng nghiệm thu cho BẢN ĐÓNG GÓI: chứng minh bốn màn dựng được khi KHÔNG có
// Frappe web bundle — thứ mà bản `/kho` trên web vẫn đang mượn.
//
// VÌ SAO PHẢI CÓ: giao diện dựa vào ~7 toàn cục của Frappe (`__`, `flt`, jQuery,
// `frappe.utils.escape_html`, `frappe.datetime.*`…). Trong app không có Frappe.
// Sót MỘT cái là MỘT màn chết lúc chạy, và không bài test nào của kho bắt được.
const { chromium } = require("/home/hoangvietyeuem/frappe-bench-yhct/apps/supplycore/frontend/node_modules/playwright");
const MAN = ["tra-cuu", "xep-hang", "lay-hang", "dat-o"];
// … mở file://…/pda_app/www/index.html, với mỗi màn: đặt hash, đợi vẽ,
// khẳng định có nội dung và KHÔNG có pageerror. In "PASS <màn>" / "FAIL <màn>".
```

- [ ] **Bước 2: Chạy để thấy ĐỎ**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/erpnext
node scripts/kiem_giao_dien/kiem_ban_dong_goi.js
```
Kỳ vọng: FAIL cả bốn màn (chưa có `www/index.html` kiểu mới, chưa có shim).

- [ ] **Bước 3: Shim các toàn cục** — `pda_app/www/shim.js`. Danh sách **đo bằng grep trên mã thật**, không đoán:

| Cần | Số lần dùng |
|---|---|
| `__()` | 142 |
| `flt()` | 48 |
| `$()` jQuery | 28 |
| `frappe.utils.escape_html` | 11 |
| `frappe.datetime.str_to_user` | 5 |
| `frappe.datetime.now_time` / `get_today` / `get_day_diff` | 9 |
| `frappe.utils.icon`, `frappe.utils.flt`, `format_number` | 4 |

```javascript
// Các toàn cục mà bốn màn mượn của Frappe. Trong app KHÔNG có Frappe, nên vỏ tự
// cấp.
//
// VÌ SAO KHÔNG GÓI CẢ `frappe-web.bundle.js`: nó kéo theo socket.io, `frappe.boot`
// và cơ chế phiên của web — đúng cái "web" mà đợt này sinh ra để bỏ. Tập toàn cục
// thật sự cần đã đếm được bằng grep (bảng trên), nhỏ và đứng yên.
//
// `__()` trả nguyên chuỗi: hệ thống dùng tiếng Việt, không có bản dịch thứ hai
// đang chờ (xem Ruling 23 của đợt /kho).
window.frappe = window.frappe || {};
frappe.provide = function (duong) { /* tạo dần các nhánh không gian tên */ };
window.__ = (s) => s;
// … flt, format_number, frappe.utils.{escape_html, icon, flt},
//     frappe.datetime.{str_to_user, now_time, get_today, get_day_diff}
```

`frappe.datetime.now_time`/`get_today`/`get_day_diff` ở đây **chỉ là chỗ dựa tạm**; Task 5 thay bằng ngày giờ máy chủ. Ghi rõ điều đó trong chú thích ngay tại chỗ.

- [ ] **Bước 4: Vỏ tĩnh** — `pda_app/www/index.html` thay hẳn màn khai máy chủ:

```html
<!doctype html>
<html lang="vi">
<head>
	<meta charset="utf-8" />
	<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
	<title>Miyano PDA</title>
	<link rel="stylesheet" href="kho_pda.bundle.css" />
</head>
<body>
	<div id="kho-app" data-la_khach="1" data-nguoi_dung=""></div>
	<script>
		// Vỏ app khai môi trường TRƯỚC khi bundle chạy. Cùng một bundle phục vụ cả
		// trang /kho trên web lẫn app; nó phân biệt bằng hai biến này chứ KHÔNG bằng
		// hai bản mã — một bản mã là điều kiện để hai nơi không trôi khỏi nhau.
		window.KHO_LA_APP = true;
		window.KHO_MAY_CHU = "__MAY_CHU__"; // dong-goi.sh thay bằng giá trị thật
	</script>
	<script src="vendor/jquery.min.js"></script>
	<script src="shim.js"></script>
	<script src="kho_pda.bundle.js"></script>
</body>
</html>
```

- [ ] **Bước 5: Script đóng gói** — `scripts/pda/dong-goi.sh`: chạy `bench build --app erpnext`, tìm `sites/assets/erpnext/dist/js/kho_pda.bundle.*.js` và `dist/css/kho_pda.bundle.*.css` (tên có băm nội dung, **không hằng số hoá**), chép vào `www/` với tên không băm, thay `__MAY_CHU__` bằng giá trị trong `scripts/pda/cau-hinh-may-chu.json`. Script phải **dừng và báo** nếu tìm thấy 0 hoặc >1 file khớp.

`scripts/pda/cau-hinh-may-chu.json` trong kho chỉ chứa địa chỉ **thử**; ghi một dòng trong `pda_app/README.md` rằng bản phát cho kho phải sửa file này rồi dựng lại.

- [ ] **Bước 6: Chạy lại cổng** — `node scripts/kiem_giao_dien/kiem_ban_dong_goi.js` → PASS cả bốn màn. Nếu màn nào FAIL vì thiếu toàn cục, **thêm vào shim và ghi lại đã sót cái gì** — đó là dữ liệu quý cho Task sau.

- [ ] **Bước 7: Không hồi quy bản web** — `bench build --app erpnext`, `bench --site erptest.local clear-cache`, chạy `scripts/kiem_giao_dien/kiem_cau_chu.js` (8/8 PASS) và mở `/kho` thật ở 360×640 bằng thẻ `SGRL79WAQF3W`. Bản web **không được đổi hành vi**.

- [ ] **Bước 8: Báo cáo.** Không commit.

---

### Task 2: `goi()` chạy được ở hai môi trường

**Files:**
- Modify: `erpnext/public/js/kho_pda/vo.js` (hàm `goi()` và chỗ dựng địa chỉ)
- Modify: `erpnext/warehouse_operations/tests/test_giao_dien.py` (thêm bài tĩnh)

**Interfaces:**
- Consumes: `window.KHO_MAY_CHU`, `window.KHO_LA_APP` (Task 1).
- Produces cho Task 4: `erpnext.kho_pda.KhoApp.dat_khoa(khoa)` / `xoa_khoa()` — đặt và xoá khoá máy; khi có khoá, mọi lời gọi gắn `Authorization`.

- [ ] **Bước 1: Viết bài test trước** — thêm vào `test_giao_dien.py`:

```python
	def test_goi_dung_dia_chi_tuyet_doi_khi_la_app(self):
		"""Trong app, trang nằm ở `file://` hoặc `capacitor://` — đường dẫn tương
		đối `/api/method/...` trỏ vào chính cái vỏ, không tới máy chủ. Hỏng kiểu
		này im lặng: mọi lời gọi trả 404 của WebView, không phải lỗi mạng."""
		ma = self._doc_text("public", "js", "kho_pda", "vo.js")
		self.assertIn("KHO_MAY_CHU", ma)

	def test_goi_gan_khoa_may_khi_co(self):
		"""Khoá máy đi trong `Authorization`; thiếu nó thì máy chủ coi là khách."""
		ma = self._doc_text("public", "js", "kho_pda", "vo.js")
		self.assertIn("Authorization", ma)
```

- [ ] **Bước 2: Chạy để thấy ĐỎ** — `bench --site erptest.local run-tests --module erpnext.warehouse_operations.tests.test_giao_dien`.

- [ ] **Bước 3: Sửa `goi()`** — hiện nó gọi `fetch("/api/method/" + duong_dan)` (vo.js ~dòng 312). Đổi thành:

```javascript
	/** Gốc địa chỉ: trên web là rỗng (đường tương đối, cùng nguồn); trong app là
	 * máy chủ thật do vỏ khai. KHÔNG hằng số hoá địa chỉ vào bundle — cùng một
	 * bundle phục vụ cả hai nơi. */
	_goc() {
		return window.KHO_MAY_CHU || "";
	}
```
và trong `goi()`: `fetch(`${this._goc()}/api/method/${duong_dan}`, {...})`, thêm `credentials: "include"`, và nếu có khoá máy thì `dau["Authorization"] = "token " + khoa;`.

**Giữ nguyên** ba nhánh đã trả giá ở đợt trước: 401/403 → về màn thẻ (trừ khi đang ở màn thẻ), lỗi mạng → câu tiếng Việt, và cơ chế làm mới CSRF. Trong app **không có CSRF** (không dùng cookie phiên) — bỏ qua nhánh đó khi `KHO_LA_APP`, đừng xoá nó khỏi đường web.

- [ ] **Bước 4: Chạy lại test** — xanh.

- [ ] **Bước 5: Chứng minh cả hai môi trường**
  - Web: `/kho` thật, quét thẻ, một lượt tra cứu — số lời gọi và kết quả **y như trước**.
  - App: mở `www/index.html` bằng `file://` với `window.KHO_MAY_CHU` trỏ vào `http://192.168.61.129:8003`, gọi một hàm chỉ-đọc — phải tới được máy chủ. (Lúc này chưa có khoá nên trả 401; cái cần chứng minh là **lời gọi đi đúng địa chỉ**, xem tab Network.)

- [ ] **Bước 6: Báo cáo.** Không commit.

---

### Task 3: Máy chủ — khoá máy và thu hồi

**Files:**
- Create: `erpnext/warehouse_operations/doctype/pda_thiet_bi/` (`__init__.py`, `pda_thiet_bi.json`, `pda_thiet_bi.py`, `pda_thiet_bi.js`, `test_pda_thiet_bi.py`)
- Modify: `erpnext/warehouse_operations/vitri/the_pda.py`
- Create: `erpnext/warehouse_operations/tests/test_khoa_may.py`

**Interfaces:**
- Produces cho Task 4: `the_pda.cap_khoa_may(ma, ten_may, ma_may)` → `{"khoa": "<api_key>:<api_secret>", "nguoi_dung", "ho_ten"}`; `the_pda.thu_hoi(nguoi_dung)` mở rộng: xoá luôn `api_secret`.

- [ ] **Bước 1: Viết bài test trước** — `test_khoa_may.py`, **chạy dưới quyền kho thật** (bài học của bản sửa quyền 24/09: mọi test chạy dưới Administrator, mà `before_tests` còn cấp cho Administrator cả 57 vai trò):

```python
	def test_cap_khoa_roi_goi_duoc_bang_khoa(self):
		"""Quét thẻ một lần → khoá dùng được cho lời gọi sau, không cần phiên."""

	def test_thu_hoi_the_giet_luon_khoa_may(self):
		"""Mất máy: trưởng kho bấm Thu hồi là máy đó chết ngay. Nếu khoá còn sống
		sau khi thu hồi thì nút đó chỉ là trang trí — và app đang mở ra internet."""

	def test_khoa_dung_tu_may_khac_bi_tu_choi(self):
		"""Khoá gắn với mã máy: chép khoá sang máy khác thì không dùng được."""

	def test_the_het_hieu_luc_khong_cap_duoc_khoa(self):
```

- [ ] **Bước 2: Chạy để thấy ĐỎ.**

- [ ] **Bước 3: Doctype `PDA Thiet Bi`** — trường: `nguoi_dung` (Link User), `ten_may`, `ma_may` (Data, unique), `cap_luc` (Datetime), `lan_dung_cuoi` (Datetime), `con_hieu_luc` (Check, mặc định 1), `ghi_chu`. Quyền: `System Manager`, `Stock Manager` (cùng tập `VAI_TRO_QUAN_LY_THE`). **Không lưu khoá thô** — chỉ lưu dấu vết để trưởng kho biết ai đang cầm máy nào.

- [ ] **Bước 4: `cap_khoa_may`** trong `the_pda.py`:

```python
@frappe.whitelist(allow_guest=True)
@rate_limit(limit=10, seconds=60)
def cap_khoa_may(ma: str, ten_may: str, ma_may: str) -> dict:
	"""Quét thẻ MỘT LẦN lúc nhận máy, đổi lấy khoá API dùng lâu dài.

	VÌ SAO DÙNG KHOÁ API CỦA FRAPPE chứ không tự chế: `frappe/auth.py:674
	validate_auth_via_api_keys` đã là đường Frappe thiết kế cho client ngoài, và
	`user.py:1332 generate_keys` sinh khoá. Tự chế một cơ chế phiên thứ hai là tự
	nhận lấy một bề mặt tấn công mà không ai soát.

	ĐÁNH ĐỔI ĐÃ CHỐT (spec §7): khoá KHÔNG hết hạn. Mất máy là mất danh tính cho
	tới khi có người thu hồi — mà hệ thống đang mở ra internet qua ngrok, nên "thu
	hồi" phải giết được khoá thật, không chỉ xoá phiên.
	"""
```
Kiểm thẻ đúng như `dang_nhap_bang_the` đang làm (một câu báo chung, `hmac.compare_digest`), rồi ghi `PDA Thiet Bi` và trả khoá.

- [ ] **Bước 5: `thu_hoi` giết luôn khoá** — thêm vào hàm sẵn có: xoá `api_key`/`api_secret` của người đó và đánh dấu mọi `PDA Thiet Bi` của họ `con_hieu_luc = 0`. Chú thích nói rõ vì sao (mất máy + ngrok).

- [ ] **Bước 6: Chạy test** — bài mới xanh; rồi `test_the_pda`, `test_phan_quyen`, `test_giao_dien`, và **cả 44 module** (dùng `find`, gồm các module trong `doctype/`).

- [ ] **Bước 7: `bench --site erptest.local migrate`** rồi kiểm doctype hiện trong Desk.

- [ ] **Bước 8: Báo cáo.** Không commit.

---

### Task 4: App — nhận máy một lần

**Files:**
- Modify: `erpnext/public/js/kho_pda/man_the.js` (thêm đường "nhận máy")
- Modify: `erpnext/public/js/kho_pda/vo.js` (`dat_khoa`/`xoa_khoa`, nạp khoá lúc khởi động)
- Modify: `erpnext/warehouse_operations/tests/test_giao_dien.py`

**Interfaces:** Consumes Task 2 (`Authorization`), Task 3 (`cap_khoa_may`).

- [ ] **Bước 1: Viết bài test trước** — bài tĩnh: `man_the.js` phải gọi `cap_khoa_may` khi `KHO_LA_APP`, và `vo.js` phải **xoá khoá** khi nhận 401 (nếu không, máy kẹt vĩnh viễn ở màn thẻ mà khoá hỏng vẫn nằm đó).

- [ ] **Bước 2: Chạy để thấy ĐỎ.**

- [ ] **Bước 3: Lưu khoá** — dùng `localStorage` của WebView, **không thêm gói `@capacitor/preferences`**:

```javascript
// Khoá máy cất trong `localStorage` của WebView. Đây là vùng RIÊNG của app
// (sandbox Android), không phải localStorage của trình duyệt nào khác, và sống
// qua các lần mở app.
//
// VÌ SAO KHÔNG THÊM `@capacitor/preferences`: thêm một gói npm là thêm một thứ
// phải cài được lúc dựng, trong khi vùng lưu này đã đủ. Hệ quả phải biết: người
// dùng "Xoá dữ liệu ứng dụng" là mất khoá → quét thẻ lại, không mất gì khác.
```

- [ ] **Bước 4: Màn nhận máy** — trong app, `man_the.js` gọi `cap_khoa_may(ma, ten_may, ma_may)` thay vì `dang_nhap_bang_the`; lấy `ma_may` từ Android (Capacitor `Device` id, hoặc một mã tự sinh cất cùng chỗ nếu không thêm gói — **quyết và ghi lý do**). Thành công thì `KhoApp.dat_khoa(...)` rồi `di("menu")`.

Trên web, đường cũ **giữ nguyên** (quét thẻ mỗi ca). Cùng một file, rẽ nhánh bằng `KHO_LA_APP`.

- [ ] **Bước 5: 401 thì xoá khoá** — trong `goi()`: nhận 401/403 mà đang có khoá → `xoa_khoa()` rồi về màn thẻ. Đây là đường thu hồi thật sự nhìn thấy được ở phía máy.

- [ ] **Bước 6: Chứng minh vòng đời đầy đủ** — bằng Playwright trên bản đóng gói, trỏ vào `erptest.local`:
  1. mở lần đầu → màn thẻ; quét `SGRL79WAQF3W` → vào menu;
  2. đóng/mở lại app → **vào thẳng menu**, không hỏi thẻ;
  3. trưởng kho bấm "Thu hồi thẻ" trên Desk → thao tác tiếp theo trên máy → **rơi về màn thẻ**;
  4. quét lại thẻ mới cấp → vào lại được.
  Dán số đo từng bước. **Cấp lại thẻ `SGRL79WAQF3W` sau khi xong** — mã đó đã in trong tài liệu của chủ đầu tư; nếu buộc phải đổi thì **cập nhật luôn `HDSD-thu-app-pda-tren-may-that.md`** và báo rõ.

- [ ] **Bước 7: Báo cáo.** Không commit.

---

### Task 5: Ngày giờ lấy từ máy chủ

**Files:**
- Modify: `erpnext/public/js/kho_pda/vo.js`, `man_tra_cuu.js`, `man_lay_hang.js`
- Modify: `pda_app/www/shim.js`
- Modify: `erpnext/public/js/warehouse_operations/luong/tra_cuu.test.js`

- [ ] **Bước 1: Viết bài test trước** — `node --test`: tiêm `ngay` giả thì phán quyết hết hạn đổi theo; và khi lệch quá ngưỡng thì trạng thái mang cờ cảnh báo.

- [ ] **Bước 2: Chạy để thấy ĐỎ.**

- [ ] **Bước 3: Lấy giờ máy chủ một lần lúc mở app**, cất vào `KhoApp`, tiêm vào `tao({goi, gio, ngay})`. Máy Android không đảm bảo đúng giờ, mà `ngay` đi thẳng vào **phán quyết hết hạn của lô vật tư y tế** — đợt trước đã đổi nghĩa dữ liệu một lần vì chuyện này.

- [ ] **Bước 4: Cảnh báo lệch** — lệch quá 10 phút thì hiện dải báo cam: *"Giờ máy sai N phút so với hệ thống — báo kỹ thuật."* Không chặn việc, chỉ nói.

- [ ] **Bước 5: `node --test` xanh** (hiện 86 bài + bài mới); chạy `kiem_ban_dong_goi.js` và `kiem_cau_chu.js`.

- [ ] **Bước 6: Báo cáo.** Không commit.

---

### Task 6: Dựng APK, lối ẩn khai địa chỉ, nhắc cập nhật, tài liệu

**Files:**
- Modify: `pda_app/capacitor.config.json`
- Modify: `pda_app/android/app/src/main/java/vn/com/miyano/pda/MainActivity.java`
- Modify: `pda_app/android/app/src/main/res/xml/network_security_config.xml`
- Modify: `erpnext/public/js/kho_pda/man_menu.js` (dải nhắc bản mới)
- Modify: `pda_app/README.md`, `docs/warehouse_operations/HDSD-app-pda.md`, `HDSD-thu-app-pda-tren-may-that.md`

> **Phần `CapacitorHttp` ĐÃ LÀM Ở TASK 2B**, không làm lại. Vòng soát Task 2 chỉ ra thứ tự
> trong kế hoạch này sai: Task 3 và 4 đều cần một lượt đi–về THẬT từ trong app, nên để cầu
> native ở cuối thì hai Task đó được nghiệm thu trên một đường mà APK phát hành **không bao
> giờ đi**. Đã bật `CapacitorHttp`, bỏ `server.allowNavigation` + `allowMixedContent`, dọn
> mẹo bắt `/login` trong `MainActivity`, và thêm xoá cookie tầng native (Task 3). Xem
> `.superpowers/sdd/2026-09-24-app-pda-giao-dien-trong-may/task-2b-report.md`.

- [ ] **Bước 1–3: bỏ qua** (xem ghi chú trên). Chỉ kiểm lại `capacitor.config.json` còn đúng
      trạng thái đó, và bài test tĩnh canh nó vẫn xanh.

- [ ] **Bước 4: Lối ẩn khai địa chỉ** — bấm giữ logo 3 giây ở màn thẻ ra ô nhập địa chỉ, lưu đè `KHO_MAY_CHU`. Không nằm trong luồng thường. **VÌ SAO:** ngrok là đường hầm chạy trên một máy; hầm rớt là mọi máy quét chết cùng lúc, và không có lối này thì phải cài lại từng cái.

- [ ] **Bước 5: Nhắc bản mới** — `man_menu.js` gọi `cai_app.ban_cai_moi_nhat` (đã có), so với phiên bản của chính app; có bản mới thì hiện dải nhắc kèm nút mở trang tải. **Không tự tải, không tự cài.**

- [ ] **Bước 6: Dựng APK và kiểm chữ ký**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/erpnext/pda_app
../scripts/pda/dong-goi.sh
export JAVA_HOME=~/opt/jdk17 ANDROID_HOME=~/opt/android-sdk
npx cap sync android && cd android && ./gradlew assembleRelease
~/opt/android-sdk/build-tools/34.0.0/apksigner verify --print-certs \
  app/build/outputs/apk/release/miyano-pda-1.0-release.apk | head -2
```
Chứng chỉ phải vẫn là `CN=Miyano PDA, …`. Rồi **mở bung APK kiểm bên trong**: `assets/public/kho_pda.bundle.js` phải có mặt và `index.html` phải mang đúng địa chỉ máy chủ — đợt trước đã bắt được một lần APK mang bản cũ bằng đúng phép này.

- [ ] **Bước 7: Tài liệu** — `HDSD-app-pda.md`: viết lại mục "Nhận máy" (quét thẻ một lần) và thêm mục **"Mất máy thì làm gì"** (thu hồi ở đâu, sau bao lâu máy chết). `HDSD-thu-app-pda-tren-may-that.md`: thêm ba dòng kiểm — cài lên máy thật, nhận máy, thu hồi rồi xem máy có chết không.

- [ ] **Bước 8: Chạy cả bộ** — `node --test`; **44 module** (dùng `find`); `kiem_cau_chu.js` 8/8; `kiem_ban_dong_goi.js` 4/4; `file_structure --audit` 0 vi phạm. Hoàn nguyên dữ liệu thử, giữ nguyên bộ `THU-` và thẻ của chủ đầu tư.

- [ ] **Bước 9: Báo cáo** — kèm đường dẫn APK và hỏi có commit không.

---

## Tự soát (đã chạy khi viết kế hoạch)

- **Phủ spec:** §4 kiến trúc → Task 1; §5 shim → Task 1 (có bảng đếm thật); §6 khoá máy → Task 3+4; §7 thu hồi/mã máy → Task 3 (3 bài test) + Task 4 (bước 6); §8 ngày giờ → Task 5; §9 địa chỉ + lối ẩn → Task 1 + Task 6; §10 nhắc cập nhật → Task 6; §3 `CapacitorHttp` → Task 6 bước 3.
- **Tên gọi nhất quán:** `window.KHO_MAY_CHU` / `window.KHO_LA_APP` (Task 1 tạo, Task 2/4/6 dùng); `KhoApp.dat_khoa`/`xoa_khoa` (Task 2 tạo, Task 4 dùng); `the_pda.cap_khoa_may` (Task 3 tạo, Task 4 gọi).
- **Đã kiểm trên máy này, khỏi kiểm lại:** `CapacitorHttp` có trong `@capacitor/core@6`; Frappe nhận `Authorization: token key:secret` (`auth.py:674`) và có `generate_keys` (`user.py:1332`); bản dựng nằm ở `sites/assets/erpnext/dist/js/kho_pda.bundle.<băm>.js`; `goi()` hiện gọi `fetch("/api/method/…")` (đường tương đối) ở `vo.js:312`; `pda_app/node_modules/@capacitor/` chỉ có `android`, `cli`, `core` — **chưa có** `preferences`, nên Task 4 cố ý dùng `localStorage`.
- **Rủi ro lớn nhất:** shim sót một toàn cục → một màn chết lúc chạy mà không bài test nào của kho bắt. Vì thế cổng `kiem_ban_dong_goi.js` là **việc đầu tiên**, viết trước cả shim, và phải thấy nó ĐỎ trước.
- **Rủi ro thứ hai:** Task 4 đụng vòng đời thẻ, mà **thẻ `SGRL79WAQF3W` đã in trong tài liệu chủ đầu tư đang dùng**. Bước 6 của Task 4 bắt cấp lại đúng mã đó hoặc cập nhật tài liệu — đừng để chủ đầu tư cầm máy lên và thấy thẻ chết.

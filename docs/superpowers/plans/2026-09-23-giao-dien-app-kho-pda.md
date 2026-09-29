# Giao diện riêng cho app PDA (`/kho`) — kế hoạch thi công

> **Cho người thi công:** dùng `superpowers:subagent-driven-development` hoặc `superpowers:executing-plans`, làm từng Task. Mỗi bước có ô `- [ ]`.

**Mục tiêu:** app PDA có màn hình của riêng nó tại `/kho` — không còn vỏ Desk — phục vụ bốn việc: lấy hàng, xếp hàng, tra cứu, đặt ô trên tem hàng loạt.

**Kiến trúc:** trang website `/kho` (không phải Desk) nạp một bundle JS thuần; mỗi màn tách làm **lớp luồng** (luật + gọi máy chủ, không đụng DOM, dùng CHUNG với trang Desk cũ) và **lớp vẽ** (riêng của app). Luật nghiệp vụ ở máy chủ không đổi một dòng nào.

**Tech Stack:** JS thuần (không framework), bundle esbuild sẵn có của bench, `frappe.xcall` của web bundle, `node --test` cho lớp luồng, Playwright cho giao diện.

**Spec:** `docs/superpowers/specs/2026-09-23-giao-dien-app-kho-pda-design.md`

## Global Constraints

- **KHÔNG tự commit.** CLAUDE.md: thao tác git chỉ làm khi chủ đầu tư yêu cầu đúng lần đó. Mỗi Task kết thúc bằng "báo cáo".
- Bench `/home/hoangvietyeuem/frappe-bench-yhct`, site thử `erptest.local`, lệnh `bench` chạy từ bench root. Máy chủ dev: `http://192.168.61.129:8003`.
- JS: thụt **tab**, chuỗi nháy kép, chú thích tiếng Việt nói **VÌ SAO**. Python: thụt tab, ≤110 ký tự.
- **Không đổi bất kỳ hàm máy chủ nào.** Đợt này chỉ đổi tầng giao diện. Phát hiện lỗi máy chủ thì BÁO, đừng sửa kèm.
- **Lớp luồng không được đụng DOM** và không gọi API của Desk (`frappe.ui.*`, `frappe.set_route`, `frappe.msgprint`). Nó chỉ nhận dữ liệu vào và trả trạng thái ra.
- **Hộp thoại của app không bao giờ nghe phím Enter** — súng quét gửi Enter sau mỗi lần bắn; đã có một phiếu bị duyệt nhầm vì chuyện này (17/09/2026).
- Mỗi Task chạy **cả bộ test của module** (vòng lặp ở Task 6, bước 6) chứ không chỉ các module liên quan — ba đợt trước đều có lỗi lộ ra ở một module tưởng như không dính. Kèm test của Task và **chạy thật bằng Playwright ở khổ 360×640**.
- `test_gan_vi_tri` **đỏ sẵn từ trước** trên erptest (dữ liệu thật giữ ô fixture `7A01010101`) — không phải hồi quy, không sửa, chỉ ghi lại.
- Các đối tượng dùng chung của app nằm ở `erpnext.kho_pda.{KhoApp, OQuet, hoi}`; lớp luồng nằm ở `erpnext.warehouse_operations.luong.<màn>`.
- Playwright: `/home/hoangvietyeuem/frappe-bench-yhct/apps/supplycore/frontend/node_modules/playwright`. Vào bằng IP `http://192.168.61.129:8003` (không cần ánh xạ tên miền).
- **Dữ liệu thử trên erptest phải hoàn nguyên** sau mỗi Task, kèm bằng chứng đã sạch. **Xoá mọi `Location Transfer` nháp TRƯỚC khi chạy test** — một phiếu nháp sót lại là đủ làm `test_xep_pda` đỏ, và người soát Task 3 đã vấp đúng bẫy này, suýt báo nhầm thành hồi quy. Fixture `Storage Location` để lại cả **nhánh cây**, không chỉ ô lá.

### Bốn luật rút ra từ Task 1–3 (đã trả giá, đừng học lại)

1. **Trình nghe uỷ quyền gắn lên phần tử CON dựng lại mỗi lượt vẽ, không gắn lên `$than`.** Task 3 gắn lên `$than`: đo được `10 → 37` trình nghe sau 3 vòng chuyển màn, và **một cú bấm "Hoàn tất phiếu" bật 4 hộp xác nhận, `duyet()` chạy 4 lần**. `_ve()` nay tự gỡ sạch trình nghe trên `$than`, nhưng đó là lưới an toàn — đừng dựa vào nó.
2. **Lớp vẽ chỉ ĐỌC kết luận của lớp luồng, không tự kết luận.** Phép thử: bọc `tao()` cho lớp luồng trả một câu báo giả; cả hai lớp vẽ phải hiện đúng câu đó. Task 2 từng trượt phép thử này vì một dòng `kq.du_lieu || {loai: null}`.
3. **Tô đậm trong câu báo dùng dấu `**…**`; lớp vẽ escape TRƯỚC rồi mới đổi dấu thành `<b>`.** Không bao giờ để chuỗi máy chủ đi thẳng vào DOM dạng HTML.
4. **Ở màn có GHI (Lấy hàng, Đặt ô), chạm một dòng lịch sử phải HỎI LẠI máy chủ.** Màn Tra cứu hiện ảnh chụp cũ là chấp nhận được; ở màn ghi thì đó là quyết định dựa trên số liệu cũ.

## Cấu trúc file

```
erpnext/www/kho/index.{py,html}                    ← trang vỏ (Task 1)
erpnext/public/js/kho_pda.bundle.js                ← điểm vào bundle của app (Task 1)
erpnext/public/js/kho_pda/                         ← mã của app
	vo.js          ← bộ định tuyến hash + khung màn + dải báo (Task 1)
	o_quet.js      ← ô quét không phụ thuộc Desk (Task 1)
	hop_thoai.js   ← hộp thoại KHÔNG nghe Enter (Task 1)
	man_the.js     ← màn quét thẻ đăng nhập (Task 1)
	man_menu.js    ← menu bốn việc (Task 1)
	man_tra_cuu.js ← (Task 2)
	man_xep_hang.js← (Task 3)
	man_lay_hang.js← (Task 4)
	man_dat_o.js   ← (Task 5)
erpnext/public/scss/kho_pda.bundle.scss            ← giao diện app (Task 1)
erpnext/public/js/warehouse_operations/luong/      ← LỚP LUỒNG dùng chung
	tra_cuu.js + tra_cuu.test.js                   ← (Task 2)
	xep_hang.js + xep_hang.test.js                 ← (Task 3)
	lay_hang.js + lay_hang.test.js                 ← (Task 4)
	dat_o.js + dat_o.test.js                       ← (Task 5)
```

Mỗi file lớp luồng kết thúc bằng đuôi cho phép dùng ở CẢ hai nơi:

```javascript
// Trình duyệt: gắn vào không gian tên; Node (bài test): xuất theo kiểu CommonJS.
// Cùng một file, hai nơi dùng — đó là điều kiện để luật không có hai bản.
if (typeof window !== "undefined") {
	frappe.provide("erpnext.warehouse_operations.luong");
	erpnext.warehouse_operations.luong.tra_cuu = API_CUA_MODULE;
}
if (typeof module !== "undefined" && module.exports) module.exports = API_CUA_MODULE;
```

**Hai `if` RỜI, không `if/else`** — esbuild bọc file bằng `__commonJS` nên `typeof module` đúng cả trong trình duyệt; viết `if/else` là phụ thuộc thứ tự hai nhánh, một thứ không ai nhớ khi sửa sau này. Và phải dùng `typeof frappe` / `typeof module` chứ **không** dùng `window.frappe`: bài test tĩnh của `luong/` cấm mọi chữ `window.` — chính nó là thứ giữ cho lớp luồng chạy được ngoài trình duyệt.

**Thời gian đi vào lớp luồng qua tham số tiêm, như `goi`.** Lớp luồng không được gọi `frappe.datetime.*` (API của Desk), nhưng cũng không được lẳng lặng dùng `new Date()` của máy trạm thay cho giờ site — dấu giờ trong lịch sử sẽ đổi nghĩa khi máy quét lệch múi giờ với máy chủ. `tao({goi, gio})` với `gio()` mặc định là giờ máy trạm; bản Desk truyền hàm lấy giờ site vào.

---

### Task 1: Vỏ app `/kho` — định tuyến, quét thẻ, menu

**Files:**
- Create: `erpnext/www/kho/index.py`, `erpnext/www/kho/index.html`
- Create: `erpnext/public/js/kho_pda.bundle.js`
- Create: `erpnext/public/js/kho_pda/{vo.js,o_quet.js,hop_thoai.js,man_the.js,man_menu.js}`
- Create: `erpnext/public/scss/kho_pda.bundle.scss`
- Modify: `erpnext/warehouse_operations/tests/test_giao_dien.py` (thêm lớp `TestVoAppKho` ở CUỐI file)

**Interfaces:**
- Consumes: `erpnext.warehouse_operations.vitri.the_pda.dang_nhap_bang_the(ma)` → `{"di_toi": "/app/pda-home"}` (đã có; app **bỏ qua** khoá `di_toi` và tự vào menu của mình).
- Produces cho Task 2–5:
  - `KhoApp.dang_ky_man(ten, {tieu_de, ve(khung, tham_so), roi()})` — đăng ký một màn;
  - `KhoApp.di(ten, tham_so)` — chuyển màn; `KhoApp.quay_lai()`;
  - `KhoApp.bao(chu, muc)` với `muc` ∈ `"xam" | "xanh" | "cam" | "do"`;
  - `KhoApp.goi(duong_dan_ham, doi_so)` → Promise; tự đưa về màn thẻ khi máy chủ trả 401/403;
  - `new OQuet({cha, vung, goi_y, khi_quet})` với `giu_focus()`, `dat_goi_y(chu, kieu)`;
  - `hoi({noi_dung, nhan, khi_dong_y, khi_dong})` — hộp thoại KHÔNG nghe Enter.

- [ ] **Bước 1: Viết bài test trước** — thêm vào cuối `erpnext/warehouse_operations/tests/test_giao_dien.py`:

```python
class TestVoAppKho(FrappeTestCase):
	"""Vỏ app PDA tại `/kho`. Hỏng ở đây là máy quét không mở nổi màn nào —
	nhưng hỏng IM LẶNG: route mất thì Frappe trả 404, không ai được báo."""

	def _doc(self, *duong_dan):
		# `frappe.get_app_path("erpnext")` trả `<bench>/apps/erpnext/erpnext` —
		# tức thư mục GÓI, không phải gốc kho. Mọi đường dẫn dưới đây tính từ đó.
		return os.path.join(frappe.get_app_path("erpnext"), *duong_dan)

	def test_hai_file_trang_ton_tai(self):
		for ten in ("index.py", "index.html"):
			duong_dan = self._doc("www", "kho", ten)
			self.assertTrue(os.path.exists(duong_dan), f"thiếu {duong_dan}")

	def test_trang_cho_khach_va_khong_dem(self):
		"""Máy quét chưa đăng nhập phải mở được `/kho` (nó tự hiện màn quét thẻ),
		và trang KHÔNG được đệm: Desk đệm mã trang vào localStorage tới 2 ngày —
		đúng lỗi 'header lúc ẩn lúc hiện' ngày 23/09; trang web phải tránh."""
		with open(self._doc("www", "kho", "index.py"), encoding="utf-8") as f:
			ma = f.read()
		self.assertIn("no_cache = 1", ma)

	def test_bundle_duoc_nhung_bang_include_script(self):
		"""Nhúng thẳng `/assets/...js` là dính đệm trình duyệt. `include_script`
		trả tên file mang băm nội dung nên bản mới tới máy quét ngay."""
		with open(self._doc("www", "kho", "index.html"), encoding="utf-8") as f:
			html = f.read()
		self.assertIn("include_script('kho_pda.bundle.js')", html)
		self.assertIn("include_style('kho_pda.bundle.css')", html)

	def test_vo_khong_dung_api_cua_desk(self):
		"""Vỏ chạy ngoài Desk: gọi `frappe.ui.Dialog`/`frappe.set_route`/`msgprint`
		là lỗi lúc chạy, mà chỉ lộ khi thủ kho bấm đúng nút đó ngoài kho."""
		import re

		thu_muc = self._doc("public", "js", "kho_pda")
		cam = re.compile(r"frappe\.(ui\.Dialog|set_route|msgprint|show_alert)")
		for ten in os.listdir(thu_muc):
			if not ten.endswith(".js"):
				continue
			with open(os.path.join(thu_muc, ten), encoding="utf-8") as f:
				ma = f.read()
			self.assertIsNone(cam.search(ma), f"{ten} còn gọi API của Desk")

	def test_hop_thoai_khong_bat_phim_nao(self):
		"""Súng quét gửi Enter sau mỗi lần bắn. Một hộp thoại bắt Enter từng làm
		DUYỆT NHẦM một phiếu thật (17/09/2026).

		Đo CÁCH GẮN SỰ KIỆN, không đo chữ "Enter" trong file: chú thích giải thích
		vì sao phải tránh Enter đương nhiên có chữ đó, mà chú thích không gây hại —
		thứ gây hại là một trình nghe bàn phím."""
		import re

		with open(self._doc("public", "js", "kho_pda", "hop_thoai.js"), encoding="utf-8") as f:
			ma = f.read()
		nghe_phim = re.compile(r"""(on|addEventListener)\s*\(\s*["']key(down|press|up)""")
		self.assertIsNone(nghe_phim.search(ma), "hộp thoại không được nghe bàn phím")
```

- [ ] **Bước 2: Chạy để thấy ĐỎ**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local run-tests --module erpnext.warehouse_operations.tests.test_giao_dien
```
Kỳ vọng: `test_hai_file_trang_ton_tai` đỏ vì chưa có `www/kho/`.

- [ ] **Bước 3: Trang vỏ**

`erpnext/www/kho/index.py`:

```python
"""Vỏ app PDA — giao diện RIÊNG của máy quét, không phải Desk.

VÌ SAO LÀ TRANG WEBSITE: Desk đệm mã nguồn từng trang vào `localStorage` khoá theo
`window._version_number` (`frappe/public/js/frappe/assets.js`). Sửa một trang Desk
mà số phiên bản app không đổi thì máy đã mở trang đó vẫn chạy bản CŨ tới hai ngày —
đo được 23/09/2026: cùng một bản vá, máy này ăn, máy kia không. Trang website với
`no_cache = 1` và tài nguyên mang băm nội dung thì không có lớp đệm đó.
"""

import frappe

no_cache = 1


def get_context(context):
	context.no_header = 1
	context.no_breadcrumbs = 1
	# Vỏ tự lo phần đăng nhập: khách vào thì nó vẽ màn quét thẻ, không đá sang
	# trang khác — chuyển trang giữa chừng trên máy quét là mất trạng thái đang làm.
	context.la_khach = frappe.session.user == "Guest"
	return context
```

`erpnext/www/kho/index.html`:

```html
{% extends "templates/base.html" %}

{# Bỏ trống navbar/footer: màn PDA cao chừng 4 inch, khuôn web mặc định ăn mất
   phần trên cho thanh điều hướng và phần dưới cho chân trang. #}
{% block navbar %}{% endblock %}
{% block footer %}{% endblock %}

{% block title %}{{ _("Kho — PDA") }}{% endblock %}

{% block content %}
<div id="kho-app" data-la-khach="{{ 1 if la_khach else 0 }}"></div>
{{ include_style('kho_pda.bundle.css') }}
{{ include_script('kho_pda.bundle.js') }}
{% endblock %}
```

- [ ] **Bước 4: Bundle và vỏ JS**

`erpnext/public/js/kho_pda.bundle.js`:

```javascript
// Điểm vào của giao diện app PDA. Gom theo thứ tự phụ thuộc: tiện ích trước,
// màn hình sau. Các màn tự đăng ký vào `KhoApp` nên thêm màn mới chỉ cần thêm
// một dòng import ở đây.
import "./kho_pda/hop_thoai.js";
import "./kho_pda/o_quet.js";
import "./kho_pda/vo.js";
import "./kho_pda/man_the.js";
import "./kho_pda/man_menu.js";
```

`erpnext/public/js/kho_pda/vo.js` — khung app (mã đầy đủ):

```javascript
// Khung của app PDA: định tuyến, khung màn hình, dải báo, và một chỗ DUY NHẤT
// gọi máy chủ.
//
// ĐỊNH TUYẾN BẰNG HASH: nút Back của Android lùi trong lịch sử trình duyệt. Dùng
// hash thì mỗi màn là một mục lịch sử mà KHÔNG tải lại trang — tải lại giữa ca là
// mất trạng thái đang quét dở.
//
// MỌI LỜI GỌI MÁY CHỦ ĐI QUA `goi()`: phiên sống 12 tiếng, hết giữa ca thì máy chủ
// trả 401/403. Gom về một chỗ thì chỉ cần một câu "về màn quét thẻ", thay vì mỗi
// màn tự đoán.

frappe.provide("erpnext.kho_pda");

class _KhoApp {
	constructor() {
		this.man = {};
		this.man_hien_tai = null;
	}

	dang_ky_man(ten, dinh_nghia) {
		this.man[ten] = dinh_nghia;
	}

	khoi_dong(goc) {
		this.$goc = $(goc);
		this.$goc.html(`
			<div class="kho-vo">
				<div class="kho-dau"></div>
				<div class="kho-bao"></div>
				<div class="kho-than"></div>
			</div>
		`);
		this.$dau = this.$goc.find(".kho-dau");
		this.$bao = this.$goc.find(".kho-bao");
		this.$than = this.$goc.find(".kho-than");
		$(window).on("hashchange", () => this._theo_hash());
		this._theo_hash();
	}

	_theo_hash() {
		const phan = (location.hash || "#/menu").replace(/^#\//, "").split("/");
		const ten = phan[0] || "menu";
		this._ve(this.man[ten] ? ten : "menu", phan.slice(1));
	}

	di(ten, tham_so) {
		const duoi = tham_so && tham_so.length ? "/" + tham_so.join("/") : "";
		location.hash = `#/${ten}${duoi}`;
	}

	quay_lai() {
		history.length > 1 ? history.back() : this.di("menu");
	}

	_ve(ten, tham_so) {
		if (this.man_hien_tai && this.man[this.man_hien_tai].roi) {
			this.man[this.man_hien_tai].roi();
		}
		this.man_hien_tai = ten;
		this.bao();
		this.$than.empty();
		const m = this.man[ten];
		this.$dau.html(`
			<button type="button" class="kho-ve" ${ten === "menu" ? 'hidden=""' : ""}>‹</button>
			<span class="kho-tieu-de">${frappe.utils.escape_html(m.tieu_de)}</span>
		`);
		this.$dau.find(".kho-ve").on("click", () => this.di("menu"));
		m.ve(this.$than, tham_so || []);
	}

	bao(chu, muc) {
		if (!chu) return this.$bao.empty();
		this.$bao.html(`<div class="kho-bao-o muc-${muc || "xam"}">${chu}</div>`);
	}

	/** Gọi máy chủ. Phiên hết hạn (401/403) thì đưa về màn quét thẻ thay vì để
	 * người dùng bấm mãi một nút không phản hồi. */
	goi(duong_dan, doi_so) {
		return frappe.xcall(duong_dan, doi_so || {}).catch((loi) => {
			const ma = (loi && (loi.status || loi.httpStatus)) || 0;
			if (ma === 401 || ma === 403) {
				this.bao(__("Phiên đã hết — quét thẻ để làm tiếp."), "cam");
				this.di("the");
			}
			throw loi;
		});
	}
}

erpnext.kho_pda.KhoApp = new _KhoApp();

$(document).ready(() => {
	const goc = document.getElementById("kho-app");
	if (!goc) return;
	erpnext.kho_pda.KhoApp.khoi_dong(goc);
	if (goc.dataset.la_khach === "1") erpnext.kho_pda.KhoApp.di("the");
});
```

- [ ] **Bước 5: Ô quét và hộp thoại**

`erpnext/public/js/kho_pda/o_quet.js` — chép **ba hành vi** đã học từ máy thật trong `erpnext/public/js/warehouse_operations/o_quet.js` (đọc chú thích đầu file đó, dòng 1–30) nhưng bỏ mọi phụ thuộc Desk:
1. luôn giữ focus (sau mỗi lần quét, sau mỗi lần chạm chỗ trống);
2. `inputmode="none"` để không bật bàn phím ảo, kèm nút "⌨" chuyển sang gõ tay;
3. súng không gửi Enter thì tự gửi sau `250ms` ngừng nhận ký tự.
Bỏ nút camera (ngoài phạm vi, xem spec §9).

`erpnext/public/js/kho_pda/hop_thoai.js`:

```javascript
// Hộp hỏi CHỈ nhận thao tác CHẠM.
//
// KHÔNG nghe phím nào hết. Súng quét gửi Enter sau mỗi lần bắn, và một hộp xác
// nhận bắt Enter toàn trang đã DUYỆT NHẦM một phiếu thật ngày 17/09/2026
// (XVT-2026-00007 trên erptest, đã huỷ). Đây là lý do file này tồn tại thay vì
// dùng hộp thoại có sẵn.

frappe.provide("erpnext.kho_pda");

erpnext.kho_pda.hoi = function ({ noi_dung, nhan, khi_dong_y, khi_dong }) {
	const $nen = $(`
		<div class="kho-hop-nen">
			<div class="kho-hop">
				<div class="kho-hop-noi-dung">${noi_dung}</div>
				<button type="button" class="kho-hop-dong-y">${frappe.utils.escape_html(nhan)}</button>
				<button type="button" class="kho-hop-thoi">${__("Không")}</button>
			</div>
		</div>
	`).appendTo(document.body);
	const dong = () => $nen.remove();
	$nen.find(".kho-hop-dong-y").on("click", () => {
		dong();
		khi_dong_y && khi_dong_y();
	});
	$nen.find(".kho-hop-thoi").on("click", () => {
		dong();
		khi_dong && khi_dong();
	});
	return { dong };
};
```

- [ ] **Bước 6: Màn quét thẻ và menu**

`man_the.js`: một ô quét duy nhất; bắn mã → `KhoApp.goi("erpnext.warehouse_operations.vitri.the_pda.dang_nhap_bang_the", {ma})` → thành công thì `KhoApp.di("menu")`; hỏng thì hiện đúng câu máy chủ trả về và xoá ô để quét lại. Hiện địa chỉ máy chủ (`location.origin`) dưới cùng.

`man_menu.js`: bốn nút lớn (cao ≥ 72px) dẫn tới `#/tra-cuu`, `#/xep-hang`, `#/lay-hang`, `#/dat-o` — **các màn này Task 2–5 mới đăng ký**, nên ở Task 1 bấm vào sẽ rơi về menu (vỏ tự lo, xem `_theo_hash`). Thêm tên người đang đăng nhập, địa chỉ máy chủ, và nút **Đăng xuất** (gọi `logout` rồi `location.reload()`).

- [ ] **Bước 7: Dựng bundle và chạy test**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench build --app erpnext 2>&1 | tail -3
bench --site erptest.local clear-cache
bench --site erptest.local run-tests --module erpnext.warehouse_operations.tests.test_giao_dien
```
Kỳ vọng: XANH.

- [ ] **Bước 8: Chạy thật ở khổ máy quét**

Kịch bản Playwright (thư mục tạm của bạn, KHÔNG để lại trong kho): khổ 360×640, vào `http://192.168.61.129:8003/kho` **không đăng nhập** → phải thấy màn quét thẻ, không có thanh Desk, không có chân trang. Rồi cấp một thẻ thử bằng `the_pda.cap_the`, "bắn" mã vào ô (gõ ký tự + Enter) → phải vào menu bốn nút, tiêu đề "Kho — PDA", không lỗi JS. Chụp hai ảnh, ghi đường dẫn vào báo cáo. **Hoàn nguyên**: thu hồi + xoá thẻ, xoá tài khoản thử nếu tạo mới.

- [ ] **Bước 9: Báo cáo.** Không commit.

---

### Task 2: Màn Tra cứu — khuôn mẫu tách lớp

**Files:**
- Create: `erpnext/public/js/warehouse_operations/luong/tra_cuu.js`
- Create: `erpnext/public/js/warehouse_operations/luong/tra_cuu.test.js`
- Create: `erpnext/public/js/kho_pda/man_tra_cuu.js`
- Modify: `erpnext/public/js/kho_pda.bundle.js` (thêm hai dòng import)
- Modify: `erpnext/warehouse_operations/page/quet_ma_tra_cuu/quet_ma_tra_cuu.js` (chuyển sang dùng lớp luồng)

**Interfaces:**
- Consumes: `KhoApp`, `OQuet`, `hoi` (Task 1); hàm máy chủ `erpnext.warehouse_operations.vitri.quet.tra_cuu`.
- Produces: `luong.tra_cuu.tao({goi})` → đối tượng có:
  - `quet(ma)` → Promise<`{loai, du_lieu, bao}`> với `loai` ∈ `"lo" | "o" | "khong_ro"`;
  - `lich_su()` → mảng các lần quét gần nhất (mới trước, tối đa 20);
  - `xoa_lich_su()`.
  `goi` là hàm gọi máy chủ (`KhoApp.goi` ở app, `frappe.xcall` ở Desk) — nhờ tham số này mà lớp luồng chạy được cả trong Node lúc test.

- [ ] **Bước 1: Viết bài test trước** (`luong/tra_cuu.test.js`):

```javascript
const { test } = require("node:test");
const assert = require("node:assert");
const { tao } = require("./tra_cuu.js");

const gia_lap = (ket_qua) => (duong_dan, doi_so) => Promise.resolve(ket_qua(duong_dan, doi_so));

test("quét mã lô trả loại 'lo' và giữ vào lịch sử", async () => {
	const l = tao({ goi: gia_lap(() => ({ loai: "lo", so_lo: "LO-1", ten_hang: "Gạc" })) });
	const kq = await l.quet("LO-1");
	assert.equal(kq.loai, "lo");
	assert.equal(l.lich_su().length, 1);
	assert.equal(l.lich_su()[0].du_lieu.so_lo, "LO-1");
});

test("mã không nhận ra thì báo rõ, VẪN vào lịch sử", async () => {
	// Giữ cả mã lạ: trang Desk vốn đã giữ, và thủ kho cần thấy lại mã vừa bắn
	// hỏng để đọc lại con số trên tem. Bỏ đi là cắt một tính năng đang chạy.
	const l = tao({ goi: gia_lap(() => ({ loai: null })) });
	const kq = await l.quet("XXX");
	assert.equal(kq.loai, "khong_ro");
	assert.match(kq.bao, /Không nhận ra/);
	assert.equal(l.lich_su().length, 1);
});

test("mã rỗng không gọi máy chủ", async () => {
	let so_lan = 0;
	const l = tao({ goi: () => { so_lan += 1; return Promise.resolve({}); } });
	await l.quet("   ");
	assert.equal(so_lan, 0);
});

test("lịch sử giữ tối đa 20 và mới nhất đứng đầu", async () => {
	const l = tao({ goi: gia_lap((_, d) => ({ loai: "o", ma_o: d.ma })) });
	for (let i = 1; i <= 25; i++) await l.quet("O-" + i);
	assert.equal(l.lich_su().length, 20);
	assert.equal(l.lich_su()[0].du_lieu.ma_o, "O-25");
});
```

- [ ] **Bước 2: Chạy để thấy ĐỎ**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/erpnext/erpnext/public/js/warehouse_operations/luong
node --test
```
Kỳ vọng: `Cannot find module './tra_cuu.js'`.

- [ ] **Bước 3: Viết lớp luồng** `luong/tra_cuu.js` — đọc `erpnext/warehouse_operations/page/quet_ma_tra_cuu/quet_ma_tra_cuu.js` và **chuyển sang** phần quyết định (không chép phần vẽ):
  - chuẩn hoá mã (cắt khoảng trắng, mã rỗng thì không gọi máy chủ);
  - gọi `quet.tra_cuu`;
  - ánh xạ kết quả máy chủ sang `loai` và câu báo;
  - giữ lịch sử 20 lần gần nhất, mới trước.
  Kết thúc file bằng đuôi hai môi trường (xem "Cấu trúc file" đầu kế hoạch).

- [ ] **Bước 4: Chạy lại `node --test`** — kỳ vọng 4/4 XANH.

- [ ] **Bước 5: Màn app** `man_tra_cuu.js`: đăng ký `KhoApp.dang_ky_man("tra-cuu", {...})`; một `OQuet` ở đầu màn; kết quả quét vẽ thành thẻ thông tin; dưới là lịch sử các lần quét (chạm vào một dòng thì hiện lại chi tiết). Thêm `import "./kho_pda/man_tra_cuu.js";` vào bundle.

- [ ] **Bước 6: Chuyển trang Desk sang lớp luồng** — sửa `quet_ma_tra_cuu.js`: bỏ phần tự gọi `quet.tra_cuu` và tự ánh xạ kết quả, thay bằng `erpnext.warehouse_operations.luong.tra_cuu.tao({goi: frappe.xcall})`; nạp file luồng bằng `frappe.require("/assets/erpnext/js/warehouse_operations/luong/tra_cuu.js")` trước khi dựng trang. **Giữ nguyên toàn bộ phần vẽ của trang Desk** — mục tiêu là hai bản dùng chung LUẬT, không phải đổi giao diện Desk.

- [ ] **Bước 7: Kiểm không hồi quy** — `bench build --app erpnext`, `bench --site erptest.local clear-cache`, rồi:
  - `node --test` trong thư mục `luong` → xanh;
  - `bench --site erptest.local run-tests --module erpnext.warehouse_operations.tests.test_quet` → xanh;
  - Playwright: mở **trang Desk cũ** `/app/quet-ma-tra-cuu`, quét một mã lô có thật → vẫn ra thông tin như trước; rồi mở **màn app** `/kho#/tra-cuu` ở 360×640, quét cùng mã đó → ra cùng nội dung. Chụp ảnh cả hai.

- [ ] **Bước 8: Báo cáo** — kèm ảnh, kết quả ba lệnh test, và **hoàn nguyên dữ liệu thử**. Không commit.

---

### Task 3: Màn Xếp hàng vào ô

**Files:**
- Create: `erpnext/public/js/warehouse_operations/luong/xep_hang.js` + `xep_hang.test.js`
- Create: `erpnext/public/js/kho_pda/man_xep_hang.js`
- Modify: `erpnext/public/js/kho_pda.bundle.js`
- Modify: `erpnext/warehouse_operations/page/xep_hang_pda/xep_hang_pda.js`

**Interfaces:**
- Consumes: `KhoApp`, `OQuet`, `hoi`; hàm máy chủ `xep.phieu_xep_dang_lam`, `xep.quet_de_xep`, `xep.them_dong_xep`, `xep.xoa_dong_xep`, `xep.duyet_phieu_xep`, `o_tem.doi_o_tren_tem`.
- Produces: `luong.xep_hang.tao({goi})` →
  - `mo(kho)` → Promise<trạng thái>;
  - `quet(ma)` → Promise<`{buoc, bao, can_xac_nhan}`> với `buoc` ∈ `"cho_lo" | "cho_o" | "da_ghi"`;
  - `dat_so_luong(so)`;
  - `xoa_dong(ten_dong)` / `duyet()`;
  - `trang_thai()` → `{kho, phieu, dong, cho, o_tren_tem}`.

- [ ] **Bước 1: Viết bài test trước** (`xep_hang.test.js`) — khoá đúng các luật đã có trên trang Desk:

```javascript
const { test } = require("node:test");
const assert = require("node:assert");
const { tao } = require("./xep_hang.js");

function gia_lap(bang) {
	return (duong_dan, doi_so) => {
		const ten = duong_dan.split(".").pop();
		if (!bang[ten]) throw new Error("gọi hàm không mong đợi: " + ten);
		return Promise.resolve(bang[ten](doi_so));
	};
}

test("quét lô rồi quét ô: hai bước, ghi ở bước hai", async () => {
	let da_them = null;
	const l = tao({ goi: gia_lap({
		phieu_xep_dang_lam: () => ({ kho: "K", phieu: null, dong: [] }),
		quet_de_xep: ({ ma }) => (ma === "LO-1"
			? { loai: "lo", so_lo: "LO-1", vat_tu: "VT", ton_chua_xep: 10, o_tren_tem: "1A01" }
			: { loai: "o", ma_o: ma }),
		them_dong_xep: (d) => { da_them = d; return { phieu: "XVT-1", dong: [{ name: "d1" }] }; },
	}) });
	await l.mo("K");
	assert.equal((await l.quet("LO-1")).buoc, "cho_o");
	const sau = await l.quet("1A01");
	assert.equal(sau.buoc, "da_ghi");
	assert.equal(da_them.den_o, "1A01");
	assert.equal(da_them.so_lo, "LO-1");
});

test("quét ô SAI so với ô in trên tem thì KHÔNG ghi và báo rõ", async () => {
	let so_lan_them = 0;
	const l = tao({ goi: gia_lap({
		phieu_xep_dang_lam: () => ({ kho: "K", phieu: null, dong: [] }),
		quet_de_xep: ({ ma }) => (ma === "LO-1"
			? { loai: "lo", so_lo: "LO-1", vat_tu: "VT", ton_chua_xep: 10, o_tren_tem: "1A01" }
			: { loai: "o", ma_o: ma }),
		them_dong_xep: () => { so_lan_them += 1; return {}; },
	}) });
	await l.mo("K");
	await l.quet("LO-1");
	const kq = await l.quet("9Z99");
	assert.equal(so_lan_them, 0, "ô sai tem mà vẫn ghi là vỡ luật 19/09/2026");
	assert.equal(kq.buoc, "cho_o");
	assert.match(kq.bao, /SAI Ô|tem ghi ô/i);
});

test("quét ô khi chưa quét lô thì nhắc quét lô, không gọi máy chủ ghi", async () => {
	let so_lan_them = 0;
	const l = tao({ goi: gia_lap({
		phieu_xep_dang_lam: () => ({ kho: "K", phieu: null, dong: [] }),
		quet_de_xep: () => ({ loai: "o", ma_o: "1A01" }),
		them_dong_xep: () => { so_lan_them += 1; return {}; },
	}) });
	await l.mo("K");
	const kq = await l.quet("1A01");
	assert.equal(so_lan_them, 0);
	assert.match(kq.bao, /quét tem LÔ|quét lô/i);
});

test("lô chưa có ô trên tem thì đòi đặt ô, không cho xếp", async () => {
	const l = tao({ goi: gia_lap({
		phieu_xep_dang_lam: () => ({ kho: "K", phieu: null, dong: [] }),
		quet_de_xep: () => ({ loai: "lo", so_lo: "LO-2", vat_tu: "VT", ton_chua_xep: 5, o_tren_tem: null }),
	}) });
	await l.mo("K");
	const kq = await l.quet("LO-2");
	assert.equal(kq.can_xac_nhan, "dat_o_tren_tem");
	assert.match(kq.bao, /chưa có ô trên tem/i);
});
```

- [ ] **Bước 2: Chạy `node --test` để thấy ĐỎ.**

- [ ] **Bước 3: Viết `luong/xep_hang.js`** — chuyển phần quyết định từ `xep_hang_pda.js` (đọc cả file; phần trạng thái nằm quanh các hàm `quet`, `nhan_lo`, `nhan_o`, `ghi`): hai bước chờ lô → chờ ô, luật **ô phải khớp ô in trên tem**, số lượng mặc định bằng tồn chưa xếp, lô chưa có ô thì đòi đặt ô. Không chép phần vẽ.

- [ ] **Bước 4: `node --test`** — kỳ vọng 4/4 XANH.

- [ ] **Bước 5: Màn app** `man_xep_hang.js`: ô quét ở đầu; thẻ "đang chờ" hiện lô/ô/số lượng với nút −/+; danh sách dòng đã xếp có nút ×; nút "Hoàn tất phiếu" dùng `hoi(...)` (không nghe Enter). Thêm import vào bundle.

- [ ] **Bước 6: Chuyển trang Desk** `xep_hang_pda.js` sang dùng `luong.xep_hang`, giữ nguyên phần vẽ.

- [ ] **Bước 7: Kiểm không hồi quy** — `node --test`; `bench --site erptest.local run-tests --module erpnext.warehouse_operations.tests.test_xep_pda`; `... test_phieu_xep_vi_tri`; `... test_o_tem`; Playwright cả trang Desk cũ lẫn màn app mới (xếp một lô thật vào đúng ô trên tem, rồi thử quét sai ô để thấy bị chặn). **Hoàn nguyên dữ liệu thử** và chứng minh đã sạch.

- [ ] **Bước 8: Báo cáo.** Không commit.

---

### Task 4: Màn Lấy hàng theo phiếu giao

**Files:**
- Create: `erpnext/public/js/warehouse_operations/luong/lay_hang.js` + `lay_hang.test.js`
- Create: `erpnext/public/js/kho_pda/man_lay_hang.js`
- Modify: `erpnext/public/js/kho_pda.bundle.js`
- Modify: `erpnext/warehouse_operations/page/lay_hang_pda/lay_hang_pda.js`

**Interfaces:**
- Consumes: `KhoApp`, `OQuet`, `hoi`; hàm máy chủ `lay_hang.danh_sach_phieu_giao`, `mo_phieu_giao`, `quet_de_lay`, `ghi_da_lay`, `bo_dong_da_lay`, `doi_lo`, `tach_dong_theo_lo`, `chot_thieu`, `bo_chot_thieu`, `hoan_tat`.
- Produces: `luong.lay_hang.tao({goi})` →
  - `danh_sach(kho)`, `mo(phieu)`, `quet(ma)`, `ghi({o})`, `dat_don_vi(uom)`, `dat_so_luong(so)`, `dat_so_kien(n)`, `bo_luot(ten)`, `chot_thieu(dong)`, `bo_chot_thieu(dong)`, `hoan_tat()`, `trang_thai()`;
  - `xac_nhan_doi_lo()` — người dùng đồng ý sau khi `quet` trả `can_xac_nhan: "doi_lo"`; lớp luồng tự chọn `tach_dong_theo_lo` hay `doi_lo` theo việc dòng ĐÃ lấy được gì chưa (xem bài test thứ ba). Lớp vẽ **không** được tự quyết định gọi hàm nào.
  - `quet` trả `{buoc, bao, can_xac_nhan}` với `buoc` ∈ `"cho_lo" | "cho_o" | "cho_ghi"`, `can_xac_nhan` ∈ `null | "doi_lo" | "tach_dong"`.

- [ ] **Bước 1: Viết bài test trước** (`lay_hang.test.js`) — khoá bốn luật đã trả giá để có:

```javascript
const { test } = require("node:test");
const assert = require("node:assert");
const { tao } = require("./lay_hang.js");

const PHIEU = {
	name: "MAT-DN-1",
	dong: [{
		dong_hang: "d1", vat_tu: "VT", ten_hang: "Gạc", so_lo: "LO-1",
		don_vi_dong: "Hộp", he_so_dong: 100, don_vi_ton: "Cái",
		can_lay: 6, da_lay: 0, can_lay_ton: 600, da_lay_ton: 0, can_quet: true,
		don_vi_chon: [{ uom: "Cái", he_so: 1 }, { uom: "Hộp", he_so: 100 }],
		da_lay_o: [], o_nen_lay: [{ o: "1A01", so_luong: 600 }],
	}],
	so_kien_da_in: 0, tong_kien: 0,
};

function gia_lap(bang) {
	return (duong_dan, doi_so) => {
		const ten = duong_dan.split(".").pop();
		if (!bang[ten]) throw new Error("gọi hàm không mong đợi: " + ten);
		return Promise.resolve(bang[ten](doi_so));
	};
}

test("lô hết hạn bị CHẶN, không chuyển sang chờ ô", async () => {
	const l = tao({ goi: gia_lap({
		mo_phieu_giao: () => PHIEU,
		quet_de_lay: () => ({ loai: "lo", het_han: 1, so_lo: "LO-CU", hsd: "2020-01-01" }),
	}) });
	await l.mo("MAT-DN-1");
	const kq = await l.quet("LO-CU");
	assert.equal(kq.buoc, "cho_lo", "lô hết hạn mà vẫn cho quét ô là vỡ luật 18/09");
	assert.match(kq.bao, /hết hạn/i);
});

test("quét lô KHÁC lô đang chốt thì đòi xác nhận, chưa đổi gì", async () => {
	const l = tao({ goi: gia_lap({
		mo_phieu_giao: () => PHIEU,
		quet_de_lay: () => ({ loai: "lo_khac", dong_hang: "d1", so_lo: "LO-2", so_lo_dang_chot: "LO-1" }),
	}) });
	await l.mo("MAT-DN-1");
	const kq = await l.quet("LO-2");
	assert.equal(kq.can_xac_nhan, "doi_lo");
});

test("đã lấy một phần rồi đổi lô thì TÁCH DÒNG, chưa lấy gì thì ĐỔI LÔ", async () => {
	const goi_da = [];
	const phieu_da_lay = JSON.parse(JSON.stringify(PHIEU));
	phieu_da_lay.dong[0].da_lay_ton = 200;
	const l = tao({ goi: gia_lap({
		mo_phieu_giao: () => phieu_da_lay,
		quet_de_lay: () => ({ loai: "lo_khac", dong_hang: "d1", so_lo: "LO-2", so_lo_dang_chot: "LO-1" }),
		tach_dong_theo_lo: (d) => { goi_da.push("tach"); return phieu_da_lay; },
		doi_lo: () => { goi_da.push("doi"); return phieu_da_lay; },
	}) });
	await l.mo("MAT-DN-1");
	await l.quet("LO-2");
	await l.xac_nhan_doi_lo();
	assert.deepEqual(goi_da, ["tach"]);
});

test("đổi đơn vị thì số lượng mặc định lấy phần NGUYÊN của phần còn thiếu", async () => {
	const l = tao({ goi: gia_lap({ mo_phieu_giao: () => PHIEU, quet_de_lay: () => ({
		loai: "lo", dong_hang: "d1", so_lo: "LO-1", vat_tu: "VT",
	}) }) });
	await l.mo("MAT-DN-1");
	await l.quet("LO-1");
	l.dat_don_vi("Hộp");
	assert.equal(l.trang_thai().cho.so_luong, 6);
	l.dat_don_vi("Cái");
	assert.equal(l.trang_thai().cho.so_luong, 600);
});

test("số kiện mặc định: đơn vị đóng gói thì mỗi đơn vị một kiện, đơn vị tồn thì một kiện", async () => {
	const l = tao({ goi: gia_lap({ mo_phieu_giao: () => PHIEU, quet_de_lay: () => ({
		loai: "lo", dong_hang: "d1", so_lo: "LO-1", vat_tu: "VT",
	}) }) });
	await l.mo("MAT-DN-1");
	await l.quet("LO-1");
	l.dat_don_vi("Hộp");
	l.dat_so_luong(5);
	assert.equal(l.trang_thai().cho.so_kien, 5);
	l.dat_don_vi("Cái");
	l.dat_so_luong(300);
	assert.equal(l.trang_thai().cho.so_kien, 1);
});
```

- [ ] **Bước 2: Chạy `node --test` để thấy ĐỎ.**

- [ ] **Bước 3: Viết `luong/lay_hang.js`** — chuyển phần quyết định từ `lay_hang_pda.js`. Bốn luật bắt buộc giữ đúng, mỗi luật đều đã trả giá:
  1. **lô hết hạn: chặn hẳn**, không phải "quét lại để xác nhận";
  2. **lô khác lô đang chốt**: đòi quét lại/xác nhận; đã lấy một phần → `tach_dong_theo_lo`, chưa lấy gì → `doi_lo`;
  3. **đơn vị**: đổi đơn vị thì số lượng mặc định = phần còn thiếu quy theo đơn vị đó, đơn vị đóng gói lấy **phần nguyên**, còn thiếu dưới một đơn vị thì rơi về đơn vị tồn;
  4. **số kiện** mặc định: đơn vị đóng gói → mỗi đơn vị một kiện; đơn vị tồn → một kiện; người dùng sửa thì giữ nguyên ý họ.
  Không chép phần vẽ.

- [ ] **Bước 4: `node --test`** — kỳ vọng 5/5 XANH.

- [ ] **Bước 5: Màn app** `man_lay_hang.js`: danh sách phiếu → mở phiếu → ô quét → thẻ "đang chờ" (lô, hàng nút đơn vị, số lượng −/+, số kiện −/+) → danh sách lượt đã lấy có nút × → dòng "x/y kiện đã in tem" → nút "Hoàn tất" qua `hoi(...)`. Thêm import vào bundle.

- [ ] **Bước 6: Chuyển trang Desk** `lay_hang_pda.js` sang dùng `luong.lay_hang`, giữ nguyên phần vẽ.

- [ ] **Bước 7: Kiểm không hồi quy** (đây là màn đụng nhiều luật nhất):
  - `node --test`;
  - `bench --site erptest.local run-tests --module erpnext.warehouse_operations.tests.test_lay_hang`;
  - `... test_lay_hang_don_vi`; `... test_lien_ket_phieu_giao`;
  - Playwright: trên **trang Desk cũ** lấy một phiếu thật (quét lô, quét ô, ghi) và trên **màn app** lấy phiếu khác, đối chiếu sổ vị trí trừ đúng ô. **Hoàn nguyên** toàn bộ (huỷ phiếu, xoá dữ liệu thử) và chạy `doi_soat_kho` để chứng minh kho khớp.

- [ ] **Bước 8: Báo cáo.** Không commit.

---

### Task 5: Màn Đặt ô trên tem hàng loạt

**Files:**
- Create: `erpnext/public/js/warehouse_operations/luong/dat_o.js` + `dat_o.test.js`
- Create: `erpnext/public/js/kho_pda/man_dat_o.js`
- Modify: `erpnext/public/js/kho_pda.bundle.js`
- Modify: `erpnext/warehouse_operations/page/dat_o_hang_loat/dat_o_hang_loat.js`

**Interfaces:**
- Consumes: `KhoApp`, `hoi`; hàm máy chủ `o_tem.lo_chua_co_o`, `o_tem.dat_o_hang_loat`.
- Produces: `luong.dat_o.tao({goi})` → `nap(kho)`, `chon(so_lo, co_chon)`, `chon_tat_ca(co_chon)`, `dat_o_cho_dong(so_lo, o)`, `so_dong_chon()`, `dat_duoc()` → bool, `dat()` → Promise<`{da_dat, loi}`>, `trang_thai()`.

- [ ] **Bước 1: Viết bài test trước** (`dat_o.test.js`):

```javascript
const { test } = require("node:test");
const assert = require("node:assert");
const { tao } = require("./dat_o.js");

const DS = [
	{ so_lo: "LO-1", vat_tu: "VT1", ton: 10, o_goi_y: "1A01", ly_do: "" },
	{ so_lo: "LO-2", vat_tu: "VT2", ton: 5, o_goi_y: null, ly_do: "mặt hàng chưa gán vị trí" },
];
const gia_lap = (bang) => (duong_dan, doi_so) => Promise.resolve(bang[duong_dan.split(".").pop()](doi_so));

test("nạp xong thì chỉ dòng CÓ ô gợi ý được chọn sẵn", async () => {
	const l = tao({ goi: gia_lap({ lo_chua_co_o: () => DS }) });
	await l.nap("K");
	assert.equal(l.so_dong_chon(), 1);
});

test("dòng đã chọn mà chưa có ô thì KHÔNG cho đặt", async () => {
	const l = tao({ goi: gia_lap({ lo_chua_co_o: () => DS }) });
	await l.nap("K");
	l.chon("LO-2", true);
	assert.equal(l.dat_duoc(), false, "cho đặt khi thiếu ô là đẩy lỗi xuống máy chủ");
	l.dat_o_cho_dong("LO-2", "1A02");
	assert.equal(l.dat_duoc(), true);
});

test("đặt xong trả về số dòng đã đặt và danh sách lỗi riêng", async () => {
	const l = tao({ goi: gia_lap({
		lo_chua_co_o: () => DS,
		dat_o_hang_loat: () => ({ da_dat: ["LO-1"], loi: [{ so_lo: "LO-2", ly_do: "ô vừa bị mặt hàng khác chiếm" }] }),
	}) });
	await l.nap("K");
	l.chon_tat_ca(true);
	l.dat_o_cho_dong("LO-2", "1A02");
	const kq = await l.dat();
	assert.equal(kq.da_dat.length, 1);
	assert.equal(kq.loi[0].so_lo, "LO-2");
});
```

- [ ] **Bước 2: `node --test` để thấy ĐỎ.**

- [ ] **Bước 3: Viết `luong/dat_o.js`** — chuyển phần quyết định từ `dat_o_hang_loat.js`: dòng có ô gợi ý thì chọn sẵn, dòng thiếu ô thì không cho đặt, gom kết quả đặt thành `{da_dat, loi}`.

- [ ] **Bước 4: `node --test`** — kỳ vọng 3/3 XANH.

- [ ] **Bước 5: Màn app** `man_dat_o.js` — **thiết kế lại cho màn hẹp**: bảng rộng của bản máy tính không bê nguyên được. Mỗi lô là một thẻ dọc (số lô · mặt hàng · tồn · ô trên tem, có nút chọn ô), phía trên là ô lọc và nút "Chọn tất cả dòng có ô", dưới cùng là nút "Đặt ô cho N dòng". Có dòng chữ nhắc *"bảng rộng — nên làm trên máy tính"*.

- [ ] **Bước 6: Chuyển trang Desk** `dat_o_hang_loat.js` sang dùng `luong.dat_o`, giữ nguyên phần vẽ.

- [ ] **Bước 7: Kiểm không hồi quy** — `node --test`; `bench --site erptest.local run-tests --module erpnext.warehouse_operations.tests.test_o_tem`; Playwright cả hai bản. Hoàn nguyên dữ liệu thử.

- [ ] **Bước 8: Báo cáo.** Không commit.

---

### Task 6: Trỏ app vào `/kho`, tài liệu, bảng kiểm

**Files:**
- Modify: `pda_app/www/index.html` (đích sau khi nối máy chủ: `/kho` thay cho `/pda`)
- Modify: `pda_app/android/app/src/main/java/vn/com/miyano/pda/MainActivity.java` (đích khi rơi vào `/login`)
- Modify: `docs/warehouse_operations/HDSD-app-pda.md`
- Modify: `docs/warehouse_operations/HDSD-quan-ly-vi-tri-kho.md` (mục 17)
- Modify: `erpnext/warehouse_operations/tests/test_giao_dien.py`

**Interfaces:** Consumes toàn bộ Task 1–5.

- [ ] **Bước 1: Viết bài test trước** — thêm vào `TestVoAppKho`:

```python
	def test_vo_app_tro_vao_kho(self):
		"""Vỏ APK phải mở `/kho` (giao diện app), không phải `/pda` (màn quét thẻ
		đứng một mình) — nếu không, thủ kho quét thẻ xong rơi vào Desk như cũ."""
		goc = frappe.get_app_path("erpnext").rsplit("/erpnext", 1)[0]
		with open(os.path.join(goc, "pda_app", "www", "index.html"), encoding="utf-8") as f:
			ma = f.read()
		self.assertIn('"/kho"', ma)
		duong_dan = os.path.join(
			goc, "pda_app", "android", "app", "src", "main", "java", "vn", "com",
			"miyano", "pda", "MainActivity.java"
		)
		with open(duong_dan, encoding="utf-8") as f:
			java = f.read()
		self.assertIn("/kho", java)
```

- [ ] **Bước 2: Chạy để thấy ĐỎ** (`bench --site erptest.local run-tests --module erpnext.warehouse_operations.tests.test_giao_dien`).

- [ ] **Bước 3: Sửa vỏ app** — trong `pda_app/www/index.html`, hàm `di(u)` đổi `u + "/pda"` thành `u + "/kho"`. Trong `MainActivity.java`, chỗ bắt `/login` đổi đích nạp lại thành `<máy chủ>/kho`. Giữ nguyên mọi thứ khác.

- [ ] **Bước 4: Dựng lại APK và kiểm chữ ký**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/erpnext/pda_app
export JAVA_HOME=~/opt/jdk17 ANDROID_HOME=~/opt/android-sdk
npx cap sync android && cd android && ./gradlew assembleRelease
~/opt/android-sdk/build-tools/34.0.0/apksigner verify --print-certs \
  app/build/outputs/apk/release/miyano-pda-1.0-release.apk | head -2
```
Kỳ vọng: APK dựng được, chứng chỉ vẫn là `CN=Miyano PDA, …`.

- [ ] **Bước 5: Tài liệu** — `HDSD-app-pda.md`: mục "Dùng hằng ngày" viết lại theo giao diện mới (quét thẻ → menu bốn việc trong app, không còn nói tới màn Desk); thêm một câu nói rõ **bản Desk vẫn còn trên web** cho ai dùng máy tính. Mục 17 của `HDSD-quan-ly-vi-tri-kho.md`: thêm dòng "app dùng giao diện riêng ở `/kho`; bốn trang Desk giữ nguyên cho máy tính".

- [ ] **Bước 6: Chạy CẢ BỘ test module**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
for m in $(ls apps/erpnext/erpnext/warehouse_operations/tests/test_*.py | xargs -n1 basename | sed 's/\.py$//'); do
  echo "$m: $(bench --site erptest.local run-tests --module erpnext.warehouse_operations.tests.$m 2>&1 | grep -E '^(OK|FAILED)' | tr '\n' ' ')"
done
```
Kỳ vọng: mọi module XANH trừ `test_gan_vi_tri` (đỏ sẵn từ trước vì dữ liệu thật trên erptest chiếm ô fixture `7A01010101`).

- [ ] **Bước 7: Bảng kiểm tay** (viết vào cuối `HDSD-app-pda.md`)

| # | Việc trên máy PDA thật | Kỳ vọng |
|---|---|---|
| 1 | Cài APK mới, mở app | Vào thẳng màn quét thẻ của app, không thấy thanh ERP |
| 2 | Quét thẻ | Ra menu bốn việc, có tên mình |
| 3 | Tra cứu một tem lô | Ra đúng thông tin lô |
| 4 | Xếp một thùng vào đúng ô trên tem | Ghi được; quét sai ô thì bị chặn |
| 5 | Lấy một phiếu giao | Chọn đơn vị, số kiện, ghi được; web thấy ngay |
| 6 | Bấm nút Back của máy | Lùi đúng một bước trong app, không thoát ra ngoài |
| 7 | Để quá 12 tiếng rồi mở lại | Đòi quét thẻ |
| 8 | Mở `/app/lay-hang-pda` trên máy tính | Bản Desk vẫn chạy như cũ |

- [ ] **Bước 8: Báo cáo** — kết quả bộ test, đường dẫn APK, và hỏi có commit không.

---

## Tự soát (đã chạy khi viết kế hoạch)

- **Phủ spec:** §3 kiến trúc → Task 1; §4 tách lớp luồng → Task 2–5 (mỗi Task đều có bước chuyển bản Desk); §5 vỏ `/kho` → Task 1; §6 ô quét/hộp thoại/thông báo → Task 1 (bước 5); §7 thứ tự → thứ tự Task; §8 kiểm thử → bước 7 của mỗi Task; §9 ngoài phạm vi → không Task nào chạm tới (camera không có trong kế hoạch, đúng như spec chốt).
- **Không có chỗ trống:** mọi bước có mã thật hoặc lệnh thật. Các bước "chuyển phần quyết định từ trang Desk" nêu rõ **file nguồn, luật phải giữ, và bài test khoá từng luật** — thay cho việc chép lại 2.300 dòng vào kế hoạch.
- **Tên gọi nhất quán:** `KhoApp.dang_ky_man/di/quay_lai/bao/goi`, `OQuet`, `hoi`, `luong.<màn>.tao({goi})` với `trang_thai()`; `goi` là tham số tiêm vào để lớp luồng chạy được trong Node — dùng đúng một cách ở cả năm Task.
- **Đã kiểm trên máy này (23/09/2026), khỏi phải kiểm lại:**
  - `node --version` → **v18.20.8**, có sẵn `node --test` (không phải cài gì thêm, không thêm gói nào vào `package.json`).
  - `frappe/templates/base.html` **có** hai khối `navbar` và `footer` (dòng 67 và 84) — ghi đè bằng khối rỗng là đúng cách; bản thân `base.html` không có thanh điều hướng nào khác.
  - `include_script` là hàm Jinja toàn cục của Frappe (`frappe/utils/jinja_globals.py:98`) — dùng được trong trang website.
  - Mọi đường dẫn file mới trong kế hoạch **lọt cổng cấu trúc** (`scripts/file_structure/gate.py`): `erpnext/public/**` và `erpnext/www/**` rơi vào luật `app-subsystem`, kể cả `*.test.js`. **Không phải sửa `gate.py`.**
  - `test_giao_dien.py` **đã import sẵn** `os` và `frappe` — chỉ thêm lớp, không thêm import.
  - Số dòng bốn màn Desk hiện tại: tra cứu 433 · xếp hàng 629 · lấy hàng 929 · đặt ô 291 (khớp thứ tự đợt trong spec).
  - Tên module test dùng ở các bước kiểm: `test_quet`, `test_xep_pda`, `test_phieu_xep_vi_tri`, `test_o_tem`, `test_lay_hang`, `test_lay_hang_don_vi`, `test_lien_ket_phieu_giao` — **đều tồn tại** trong `erpnext/warehouse_operations/tests/`.
- **Rủi ro lớn nhất** (ghi lại để người thi công biết): Task 4 đụng bốn luật đã trả giá bằng lỗi thật. Nếu bài test ở bước 1 của Task 4 không đỏ trước khi viết mã, tức là đang đo nhầm thứ — dừng lại xem lại, đừng viết tiếp.

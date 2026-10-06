# Miyano ERP — bóc lớp vỏ ERPNext

**Ngày:** 2026-07-31
**Nhánh:** `feat/vn-accounting-tt99`
**Trạng thái:** đã thực thi xong

## 1. Mục tiêu & phạm vi

Chuyển repo từ "bản fork nội bộ của ERPNext" thành **Miyano ERP** — sản phẩm nội bộ mang thương hiệu Miyano, không phát hành công khai.

Phạm vi: **chỉ `erpnext`**. App `hrms` đã hoàn tất ở phiên song song cùng ngày (xem `apps/hrms/docs/superpowers/specs/2026-07-31-miyano-rebrand-delicense-design.md`), không đụng lại. Không đụng `frappe` (runtime), `antmed_crm`, `assetcore`.

## 2. Bối cảnh & quyết định đã chốt

Ba điểm đã nêu với chủ sở hữu trước khi thiết kế, chủ sở hữu đã cân nhắc và quyết định gỡ sạch:

1. **App không phân phối thì GPL không ràng buộc.** GPLv3 chỉ phát sinh nghĩa vụ khi conveying. Miyano dùng nội bộ ⇒ không phải công bố mã nguồn.
2. **Xoá header không đổi giấy phép thực tế** của phần mã thượng nguồn. Vô hại trong hạ tầng nội bộ, thành rủi ro thật nếu app được chia sẻ, kiểm toán hay bán lại.
3. **Không thể gỡ Frappe khỏi kỹ thuật** — app chạy trên Frappe Framework, 1473 file `import frappe`. Gỡ được là gỡ **thương hiệu ERPNext**, không phải nền tảng.

**Điều chỉnh áp dụng:** với file thượng nguồn, header bị **xoá hẳn** thay vì thay bằng `© Miyano`. Đạt cùng mục tiêu (repo sạch chữ GPL/Frappe) nhưng không tự dán tên Miyano lên code Miyano không viết — nếu có kiểm toán thì đó là "không ghi gì", không phải "ghi sai". Quy tắc này kế thừa từ thiết kế `hrms`.

## 3. Phân loại file — quy tắc khách quan

`hivx` là tác giả duy nhất trên fork, nên ranh giới là git chứ không phải phán đoán chủ quan:

```bash
git log --diff-filter=A --author=hivx --format="" --name-only | sort -u
```

Repo có **4587 file tracked**, trong đó **110 file do Miyano thêm**.

| Nhóm | Số file | Xử lý header |
|---|---|---|
| Miyano tự viết | 110 (53 file code có header) | Giữ `© Công ty TNHH Miyano Việt Nam` — đã xong |
| Thượng nguồn Frappe | ~1585 | Xoá hẳn dòng copyright |
| Dòng license (mọi biến thể) | 1373 | Xoá hẳn |
| Bên thứ ba không phải Frappe | ~10 | **Giữ nguyên** — xem mục 4 |

### 3.1 Header có 15 biến thể, không phải một

Đây là rủi ro kỹ thuật lớn nhất của cả đợt. Kế hoạch `hrms` đã hụt 8 file vì bỏ sót một biến thể. Số liệu đo được:

| Biến thể copyright | Số file |
|---|---|
| `Frappe Technologies Pvt. Ltd. and contributors` | 788 |
| `Frappe Technologies Pvt. Ltd. and Contributors` | 670 |
| `Frappe and Contributors` (không có "Technologies") | 69 |
| `... and Contributors and contributors` (lặp) | 29 |
| `... and Contributors and Contributors` (lặp) | 11 |
| `Frappe and contributors` | 10 |
| `Frappe Technologies and contributors` | 6 |
| copyright + license dồn một dòng | 1 |
| `Copyright(c)` dính liền, không dấu cách | 1 |

| Biến thể dòng license | Số file |
|---|---|
| `For license information, please see license.txt` | 861 |
| `License: GNU General Public License v3. See license.txt` | 501 |
| `License: MIT. See LICENSE` | 8 |
| `License: GNU GPL v3. See LICENSE` | 1 |
| 2 biến thể lỗi chính tả (thừa `"`, thiếu dấu cách) | 2 |

Script phải liệt kê biến thể trước khi chạy, khớp theo mẫu neo đầu file, và đối chiếu tổng số khớp với tổng số đã đo ở trên.

## 4. Bên thứ ba không phải Frappe — giữ nguyên

Trong khối thượng nguồn có **4 công ty không phải Frappe**: Wahni Green Technologies (6 file), Velometro Mobility (1), newmatik.io / ESO Electronic Service Ottenbreit (1), Web Notes Technologies (1 — tên cũ của Frappe).

Mục tiêu là gỡ dấu vết **ERPNext/Frappe**. Các công ty này không phải Frappe; giữ tên họ không mâu thuẫn với mục tiêu, còn gỡ là mở rộng phạm vi sang bên thứ ba vô can với lợi ích bằng không. **Quyết định: giữ nguyên dòng copyright của họ.**

8 file ghi `License: MIT` trỏ tới file `LICENSE` **chưa bao giờ tồn tại** trong repo — tham chiếu chết có sẵn từ upstream. **Quyết định: xoá dòng trỏ chết, giữ dòng copyright.**

## 5. Hạng mục thực thi

### 5.1 Bóc header

1585 dòng copyright + 1373 dòng license. Không đụng dòng code thực thi nào. `git diff --stat` phải chỉ có xoá dòng.

### 5.2 Gỡ ba thứ còn sót từ đợt rebrand trước

- `erpnext/utilities/__init__.py:45` — link `frappecloud.com/marketplace` bản Python (bản JS trong `public/js/utils.js` đã sửa đợt trước; không biết có bản song sinh).
- `get_site_info` hook (`hooks.py:496`) + hàm trong `utilities/__init__.py` — gom email, họ tên, lần đăng nhập cuối của **mọi system user** cùng dung lượng DB/backup để nạp vào đường ống báo cáo usage SaaS. Hiện nằm im (trong bench này chỉ một test của frappe gọi tới), nhưng cùng loại với `subscription_utils.py` mà phiên `hrms` đã gỡ.
- `erpnext/setup/demo.py` — 2 lời gọi `frappe.utils.telemetry.capture`.

### 5.3 Logo & ảnh

Đơn giản hơn `hrms` nhiều: **không có PWA manifest, không có splash screen**. Chỉ 5 file ảnh, **4 chỗ tham chiếu, tất cả trong `hooks.py`**.

Nguồn: `logo-miyano.png` 768×768 RGBA. Nguồn là PNG nên **chỉ sinh PNG** — 3 chỗ đang trỏ `.svg` đổi sang `.png`, không dựng SVG giả (quy tắc kế thừa từ `hrms`).

| Đích | Thay cho | Dùng ở |
|---|---|---|
| `miyano-logo.png` | `erpnext-logo.svg` | `app_logo_url`, `splash_image` |
| `miyano-logo-blue.png` | `erpnext-logo-blue.png` | app switcher |
| `miyano-favicon.png` | `erpnext-favicon.svg` | `website_context.favicon` |

- `erpnext-video-placeholder.jpg` — **xoá**, đã xác minh không file nào tham chiếu.
- `email_brand_image` (`hooks.py:484`) trỏ `erpnext-logo.jpg` — **file chưa từng tồn tại**, lỗi có sẵn từ upstream. Sửa thành logo Miyano thật.

### 5.4 Dọn chú thích thừa

Quét comment scaffold chết còn lại, theo cách `hrms` đã làm.

### 5.5 Tài liệu

- `CLAUDE.md` — hiện định nghĩa repo là "ERPNext being hard-forked"; viết lại theo thương hiệu Miyano ERP.
- `NOTICE.md`, `README.md` — cập nhật theo phân loại ở mục 3–4.

## 6. Ngoài phạm vi (cố ý giữ)

- `app_name = "erpnext"`, thư mục `erpnext/`, namespace JS `erpnext.*`, tên doctype, `import frappe` — đổi là phải cài lại app và mất dữ liệu.
- Mọi tham chiếu **Frappe Framework** (`frappe.db`, doctype, `bench`) — mô tả kỹ thuật đúng, xoá đi thành sai.
- **6 module regional nước ngoài** (`australia`, `italy`, `south_africa`, `turkey`, `united_arab_emirates`, `united_states`) — tách sang đợt sau, cần điều tra riêng phụ thuộc patch/fixture/test. Khác với `hrms` (2 patch đã nằm trong Patch Log, đã kiểm chứng), ở đây chưa xác minh gì.
- 2 comment dẫn link PR upstream giải thích *lý do* đoạn code (`pricing_rule.py:576`, `opening_invoice_creation_tool.py:210`) — xoá link là mất ngữ cảnh.
- Viết lại lịch sử git.

## 7. Kiểm chứng

Bài học từ `hrms`: **con số test tuyệt đối vô nghĩa, chỉ so trước/sau cùng harness mới có giá trị.** Site `miyano` là PROD, thiếu `_Test Company`, nên luôn có lượng error nền cố định.

| Cổng | Cách đo |
|---|---|
| Không còn dấu vết | `git grep -i "GNU General Public\|Frappe Technologies"` → chỉ còn tài liệu mô tả + 10 file bên thứ ba |
| Cú pháp | `python3 -m compileall` sạch; toàn bộ JSON parse được |
| Test | Mốc trước **45 test / 0 fail** (5 suite kế toán VN); sau phải giống hệt |
| App nạp được | `bench --site miyano console` → `import erpnext` |
| Build | `bench build --app erpnext` xanh; bundle không còn URL upstream |
| Diff chỉ có xoá | `git diff --stat` khối header: 0 dòng thêm |

## 8. Rủi ro

| Rủi ro | Mức | Giảm thiểu |
|---|---|---|
| Regex header ăn nhầm code | **Cao nhất** — 15 biến thể | Neo đầu file; đối chiếu tổng khớp với tổng đã đo; diff chỉ được có xoá dòng |
| Sót biến thể header | Trung bình | Chạy lại bộ đếm biến thể sau khi xong, phải về 0 |
| Gỡ `get_site_info` vỡ hook | Thấp | Chỉ 1 test của frappe gọi tới; xoá cả khai báo hook lẫn hàm |
| Đổi `.svg`→`.png` vỡ ảnh | Thấp | Chỉ 4 chỗ, đều trong `hooks.py`; kiểm tra sau `bench build` |

## 9. Thứ tự thực thi

Từng bước một commit, `git revert`-được:

1. Bóc header (1585 + 1373 dòng)
2. Gỡ 3 thứ còn sót (frappecloud, `get_site_info`, telemetry)
3. Logo & ảnh
4. Dọn chú thích thừa
5. Tài liệu
6. Kiểm chứng toàn bộ


---

## Kết quả thực thi (2026-07-31)

| Cổng | Kết quả |
|---|---|
| `git grep -i "GNU General Public"` | **1** — chính tài liệu này |
| `git grep "Frappe Technologies"` | **1** — chính tài liệu này |
| `license.txt` trong code | **0** |
| Diff bóc header | 1600 file, **0 dòng thêm**, 5518 dòng xóa |
| `compileall` | sạch |
| JSON | 1105 file, 0 lỗi |
| `bench build --app erpnext` | xanh, bundle không còn URL upstream |
| Test 5 suite kế toán VN | **45 test / 0 fail — giống hệt mốc trước** |

### Khác biệt so với thiết kế

1. **Phải chạy 2 lượt, không phải 1.** Lượt 1 khớp theo chuỗi cố định (`License:`, `For license information`) nên bỏ sót 3 biến thể: `# See license.txt` trần (226 file), `# MIT License. See license.txt` (16), `# GPL v3 License...` (1). Lượt 2 đổi cách tiếp cận — quét cả khối comment đầu file, xoá mọi dòng nói về giấy phép — mới sạch. Đúng loại rủi ro thiết kế đã cảnh báo, chỉ là biến thể còn nhiều hơn con số đo được ban đầu.

2. **Sáu công ty bên thứ ba, không phải bốn.** Dry-run lộ thêm **Epoch Consulting** và **Tristar Enterprises**. Script viết theo hướng "xoá Frappe, giữ mọi tên khác" nên bắt được cả hai; nếu dùng danh sách cố định thì đã xoá nhầm ghi nhận của họ.

3. **`erpnext/startup/__init__.py` phải sửa tay.** Khối GPL 14 dòng dài quá tầm quét, regex bóc dở dang. File này còn chứa `product_name = "ERPNext"` — hằng số tên sản phẩm, đã đổi thành `"Miyano ERP"`.

4. **Ảnh: sinh 2 file thay vì 3.** Không có artwork riêng cho biến thể "blue" nên `miyano-logo.png` (512×512) dùng chung cho app switcher, splash, desk logo và email; `miyano-favicon.png` (96×96) cho favicon.

5. **Phát sinh: 2 import chết** (`cstr`, `get_level`) sau khi gỡ `get_site_info`, đã gỡ theo.

6. **Bước 4 (dọn chú thích thừa) gần như trống.** Khác `hrms` có 24 dòng scaffold bị comment trong `hooks.py`, erpnext không có dòng nào. Chỉ gỡ được comment `## temp utility`.

### Việc cần con người làm

- **`bench --site miyano migrate`** rồi **`clear-cache`**, và khởi động lại app để `hooks.py` mới có hiệu lực.
- **Xác nhận trực quan** sau khi khởi động lại: logo Miyano ở app switcher, favicon, splash.
- **Quyết định cách commit** — cây làm việc đang lẫn phần VN accounting chưa commit từ trước phiên này.

# Giao diện riêng cho app PDA (`/kho`) — thiết kế

Ngày: 23/09/2026 · Module: Warehouse Operations · Nền: bốn trang Desk PDA hiện có + app `pda_app/` (spec 2026-09-23-app-pda-apk-design.md)

## 1. Yêu cầu (chủ đầu tư, 23/09/2026)

> "Anh muốn em làm cho anh giao diện app PDA và phục vụ những chức năng như ở kho-pda như bây giờ, chứ không phải app direct sang web nữa."

App hiện tại là một cửa sổ mở thẳng các trang Desk: thủ kho nhìn thấy thanh ERP, ô tìm kiếm, menu tài khoản — trông như đang dùng web trên một màn hình 4 inch. Yêu cầu: app có **màn hình của riêng nó**.

## 2. Quyết định đã chốt

| Câu hỏi | Chốt |
|---|---|
| Hình dạng | **Giao diện riêng**, không dính Desk |
| Bản Desk cũ | **Giữ song song** (không bỏ) |
| Màn đưa vào app | Lấy hàng · Xếp hàng · Quét mã tra cứu · Đặt ô trên tem hàng loạt |
| Chỗ đặt | **Máy chủ phục vụ**, app mở thẳng — cùng nguồn nên phiên/thẻ chạy như cũ, sửa giao diện không phải cài lại APK |
| Công nghệ | **JS thuần**, cùng kiểu các trang PDA hiện có; không thêm bộ dựng mới |
| Chống trôi hai bản | **Tách lớp luồng dùng chung**, và chuyển luôn bản Desk sang dùng lớp đó |

## 3. Kiến trúc

```
/kho  (trang website, KHÔNG phải Desk)
 ├─ chưa đăng nhập → màn quét thẻ  (gọi `the_pda.dang_nhap_bang_the`, đã có)
 ├─ menu bốn việc
 └─ bốn màn nghiệp vụ, mỗi màn = lớp LUỒNG (dùng chung với Desk) + lớp VẼ (riêng của app)
```

**Vì sao là trang website chứ không phải trang Desk:** Desk đệm mã nguồn của từng trang vào `localStorage`, khoá theo `window._version_number` (`frappe/public/js/frappe/assets.js`). Sửa CSS/JS của một trang Desk mà số phiên bản app không đổi thì máy đã mở trang đó trước kia vẫn chạy bản cũ tới 2 ngày — đo được ngày 23/09/2026 khi ẩn thanh Desk: máy này ẩn, máy kia còn hiện. Trang website thì `no_cache = 1` và tài nguyên đi theo tên file có băm nội dung (`include_script`), nên không có lớp đệm đó.

**Vì sao không đóng gói giao diện vào APK:** giao diện trong máy gọi sang máy chủ là **khác nguồn** — phải mở CORS cho cả hệ thống và tự quản lý khoá API, trong khi phiên bằng cookie đang chạy tốt. Và mỗi lần sửa một dòng giao diện phải dựng APK rồi cài lại từng máy quét. Cùng nguồn thì sửa là có ngay.

## 4. Chống chuyện hai bản giao diện trôi khỏi nhau

Giữ song song hai bản nghĩa là cùng một nghiệp vụ có hai màn hình. Nếu cả luật lẫn cách vẽ đều nằm chung một file (như hiện nay) thì mỗi lần đổi nghiệp vụ phải sửa hai nơi, và hai nơi sẽ lệch nhau — lớp lỗi đắt nhất của dự án này (xem `docs/superpowers/specs/2026-09-22-*`: một luật sửa ở màn này mà quên màn kia).

Mỗi màn vì thế tách làm hai lớp:

| Lớp | Nội dung | Dùng bởi |
|---|---|---|
| **Luồng** (`public/js/warehouse_operations/luong/<màn>.js`) | trạng thái và luật: đang chờ quét gì, quét xong thì gọi hàm máy chủ nào, kết quả trả về thì trạng thái đi đâu; các phép kiểm sớm | **cả hai** bản |
| **Vẽ** | dựng HTML, bắt sự kiện, hộp thoại, thông báo | mỗi bản một bản riêng |

Lớp luồng **không đụng DOM, không gọi API của Desk**, chỉ nhận đầu vào (mã vừa quét, số lượng người dùng gõ) và trả ra trạng thái mới + việc cần vẽ. Nhờ vậy nó **test được bằng Python/Node mà không cần trình duyệt**, và đổi nghiệp vụ chỉ sửa một chỗ.

Chuyển bản Desk sang dùng lớp chung là **một phần bắt buộc của mỗi đợt**, không để lại sau: để lại tức là vẫn có hai bản luật, đúng thứ thiết kế này sinh ra để tránh.

## 5. Vỏ app `/kho`

- `erpnext/www/kho/index.py` + `index.html`: trang website, `no_cache = 1`, kế thừa `templates/base.html` và **bỏ trống** hai khối `navbar`/`footer` (khuôn `web.html` mặc định ăn mất phần trên cho thanh điều hướng và phần dưới cho chân trang — trên màn 4 inch đó là chỗ của một dòng phiếu).
- Tài nguyên: `erpnext/public/js/kho_pda.bundle.js` và `kho_pda.bundle.css`, nhúng bằng `include_script`/`include_style` để tên file mang băm nội dung.
- **Điều hướng trong app**: một bộ định tuyến nhỏ theo `location.hash` (`#/menu`, `#/lay-hang`, `#/lay-hang/<phiếu>`, `#/xep-hang`, `#/tra-cuu`, `#/dat-o`). Dùng hash để nút Back của Android lùi đúng một bước trong app mà không tải lại trang.
- **Đăng nhập**: chưa có phiên thì vẽ màn quét thẻ ngay trong vỏ (không chuyển sang `/pda`), gọi `the_pda.dang_nhap_bang_the`. Phiên hết giữa ca: mọi lời gọi máy chủ trả 401/403 thì vỏ tự đưa về màn quét thẻ. Mẹo bắt `/login` ở tầng Java (`MainActivity`) **giữ nguyên** — nó vẫn là lưới an toàn nếu WebView vì lý do nào đó rơi vào trang đăng nhập của Desk.
- Hiện **địa chỉ máy chủ đang nối** ở màn quét thẻ và menu, để không ai nhầm máy chủ thử với máy chủ thật.

## 6. Những thứ Desk có mà app phải tự làm

| Thứ | Hiện dùng | Trong app |
|---|---|---|
| Gọi máy chủ | `frappe.xcall` (Desk) | `frappe.xcall` của web bundle — **đã có sẵn** (`frappe/website/js/website.js`), không phải viết |
| Định dạng ngày/số, `escape_html` | Desk | web bundle **đã có** |
| Ô quét (giữ focus, tắt bàn phím ảo, tự gửi khi súng không gửi Enter) | `OQuet` (`o_quet.js`) | **viết lại** bản không phụ thuộc Desk; giữ nguyên ba hành vi đã học được từ máy thật (xem chú thích đầu `o_quet.js`) |
| Quét bằng camera | `frappe.ui.Scanner` (chỉ có trong Desk) | **ngoài phạm vi đợt này** — xem §9 |
| Hộp thoại xác nhận | `frappe.ui.Dialog` | **viết lại**. Tuyệt đối không dùng loại bắt phím Enter toàn trang — súng quét gửi Enter sau mỗi lần bắn, và đã có một phiếu bị duyệt nhầm vì chuyện này (17/09/2026) |
| Thông báo | `frappe.show_alert` / `msgprint` | **viết lại** một dải báo gọn trong màn |

## 7. Thứ tự thi công — nhẹ trước, nặng sau

| Đợt | Màn | Dòng hiện tại | Vì sao thứ tự này |
|---|---|---|---|
| 1 | Vỏ + đăng nhập thẻ + menu | — | Dựng nền, chưa đụng nghiệp vụ |
| 2 | **Quét mã tra cứu** | 433 | Nhẹ nhất — kiểm khuôn tách lớp có đứng được không |
| 3 | **Xếp hàng vào ô** | 629 | Luồng hai bước rõ ràng |
| 4 | **Lấy hàng theo phiếu giao** | 929 | Nặng nhất; làm sau khi khuôn đã chắc |
| 5 | **Đặt ô trên tem hàng loạt** | 291 | Bảng rộng, phải thiết kế lại cho màn hẹp |

Mỗi đợt kết thúc bằng: cả bộ test module xanh, **chạy thật ở khổ 360×640**, và bản Desk tương ứng đã chuyển sang lớp luồng chung.

## 8. Kiểm thử

- **Lớp luồng**: test chạy không cần trình duyệt — quét lô rồi quét ô thì trạng thái đi đâu; quét lô khác lô đang chốt thì đòi xác nhận; ô không đủ tồn thì cắt theo tồn; chốt thiếu trên dòng bán theo đơn vị đóng gói phải tròn đơn vị.
- **Giao diện**: Playwright ở 360×640 cho từng màn, đúng kịch bản thủ kho: bắn mã như súng quét (gõ ký tự + Enter), kiểm màn hình đổi đúng bước, và **không có lỗi JS**.
- **Không hồi quy bản Desk**: sau khi chuyển sang lớp chung, chạy lại toàn bộ `warehouse_operations` và chạy lại kịch bản Playwright cũ của trang Desk tương ứng.
- **Dữ liệu thử trên erptest phải hoàn nguyên**, và đối soát kho phải khớp — như mọi đợt trước.

## 9. Ngoài phạm vi

- Làm việc khi mất mạng.
- In tem từ máy quét (máy in nối với máy tính; app chỉ hiện "x/y kiện đã in tem").
- Đổi bất kỳ luật nghiệp vụ nào ở máy chủ — đợt này **chỉ** đổi tầng giao diện.
- **Quét bằng camera trong app.** Máy kho là loại có súng quét cứng (đã chốt 23/09), nên camera là thứ có thì tốt. Chưa đưa vào vì chưa đo được cách nhập `html5-qrcode` vào bundle của erpnext: thư viện nằm trong `node_modules` của **frappe**, các bundle của erpnext hiện không nhập gói ngoài nào, và `sites/assets` không có bản dựng sẵn để nạp động. Quyết sau, khi cần thật. Bản Desk vẫn có nút camera như cũ.
- Bỏ các trang Desk cũ (chủ đầu tư chốt giữ song song).
- Đổi cách đăng nhập (vẫn là thẻ PDA, phiên 12 tiếng).

## 10. Rủi ro đã biết

| Rủi ro | Cách giảm |
|---|---|
| Hai bản giao diện trôi khỏi nhau | lớp luồng dùng chung; chuyển bản Desk ngay trong cùng đợt |
| Viết lại ~2.300 dòng màn hình là cơ hội sinh lỗi mới | làm từng màn, nhẹ trước; mỗi màn chạy thật trước khi sang màn sau |
| Ô quét là phần tinh vi nhất (focus, bàn phím ảo, súng không gửi Enter) | chép nguyên ba hành vi đã học từ máy thật; thử trên máy PDA thật ở đợt 2, trước khi làm hai màn nặng |
| Hộp thoại bắt Enter → duyệt nhầm | luật cứng: hộp thoại của app không bao giờ nghe phím Enter |
| "Đặt ô hàng loạt" là bảng rộng | thiết kế lại thành danh sách từng dòng cho màn hẹp; vẫn khuyên dùng trên máy tính |
| Máy PDA thật chưa ai cầm thử | mỗi đợt có bảng kiểm tay; chủ đầu tư thử đợt 2 trước khi làm tiếp |

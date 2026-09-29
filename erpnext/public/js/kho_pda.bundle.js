// Điểm vào của giao diện app PDA. Gom theo thứ tự phụ thuộc: tiện ích trước,
// màn hình sau. Các màn tự đăng ký vào `KhoApp` nên thêm màn mới chỉ cần thêm
// một dòng import ở đây.
//
// RÀNG BUỘC THẬT, VẪN CÒN BẮT BUỘC (soát xét vòng 1, Task 6, mục 2 — khác hẳn
// ràng buộc luồng/màn đã BỎ được ở dưới): `./kho_pda/vo.js` PHẢI nạp TRƯỚC MỌI
// file `man_*.js` (kể cả `man_the.js`/`man_menu.js`, hai file không dùng lớp
// luồng nên KHÔNG được nhắc tới trong khối chú thích "việc thêm 1" bên dưới).
// Lý do: mọi `man_*.js` gọi `erpnext.kho_pda.KhoApp.dang_ky_man(...)` NGAY LÚC
// MODULE TOP-LEVEL chạy (không đợi `ve()` — đây là hành vi phải giữ, không phải
// lỗi cần dựng lười như `.tao()`, vì đăng ký màn KHÔNG tốn lời gọi máy chủ và
// KHÔNG có gì để mất tính singleton), mà `KhoApp` chỉ tồn tại sau dòng
// `erpnext.kho_pda.KhoApp = new _KhoApp();` ở CUỐI `vo.js`. Đảo `vo.js` xuống
// sau một `man_*.js` bất kỳ thì `dang_ky_man` gọi trên `undefined`, ném lỗi
// ngay lúc tải — CÙNG HẠNG lỗi mà việc thêm 1 vừa sửa, chỉ khác nguồn gốc. Khoá
// bằng `test_giao_dien.py::TestVoAppKho::test_vo_js_nap_truoc_moi_man`.
import "./kho_pda/hop_thoai.js";
import "./kho_pda/o_quet.js";
import "./kho_pda/vo.js";
import "./kho_pda/man_the.js";
import "./kho_pda/man_menu.js";
//
// TASK 6, VIỆC THÊM NGOÀI BRIEF 1 — THỨ TỰ DƯỚI ĐÂY KHÔNG CÒN BẮT BUỘC NỮA: bản cũ
// của chú thích này (đọc lại trong lịch sử file nếu cần đối chiếu) từng đòi mỗi
// file `luong/*.js` phải nạp TRƯỚC file `man_*.js` tương ứng, vì `man_*.js` gọi
// `erpnext.warehouse_operations.luong.<màn>.tao(...)` NGAY lúc module top-level
// chạy (dòng `const _luong = ...`, không đợi tới lúc `ve()`). Đảo nhầm một dòng
// import từng đủ làm một màn chết hẳn ngay lúc tải trang, mà không bài test Python
// nào ở đây bắt được (không bài nào thực thi JS trong trình duyệt) — đúng chỗ hở
// soát xét cuối cùng chỉ ra. Cả bốn file `man_tra_cuu.js`/`man_xep_hang.js`/
// `man_lay_hang.js`/`man_dat_o.js` giờ dựng luồng LƯỜI ở lần `ve()` đầu tiên (hàm
// `_dung_luong()` trong từng file) — tới lúc đó toàn bộ bundle này đã nạp xong
// (import đồng bộ, luôn chạy trước `$(document).ready` cuối `vo.js`), nên namespace
// nào cũng đã có mặt BẤT KỂ thứ tự các dòng `import` bên dưới. Vẫn GIỮ NGUYÊN thứ
// tự cũ ở đây (luồng trước, màn sau) vì đọc dễ hiểu hơn — không phải vì còn bắt
// buộc — không đảo lại để tự chứng minh gì; xem `test_giao_dien.py::TestVoAppKho`
// (lớp khoá "không tao() ở top-level trong man_*.js") để biết bài test tĩnh nào
// giữ bất biến này, và Playwright của Task 6 để biết bằng chứng chạy thật.
import "./warehouse_operations/luong/tra_cuu.js";
import "./kho_pda/man_tra_cuu.js";
import "./warehouse_operations/luong/xep_hang.js";
import "./kho_pda/man_xep_hang.js";
import "./warehouse_operations/luong/lay_hang.js";
import "./kho_pda/man_lay_hang.js";
import "./warehouse_operations/luong/dat_o.js";
import "./kho_pda/man_dat_o.js";

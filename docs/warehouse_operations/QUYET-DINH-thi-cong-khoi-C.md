# Quyết định thi công khối C — nhập lô, in nhãn, quét mã

> Ghi ngày 16/09/2026, khi đóng khối C. Đây là những quyết định **điều phối tự ra
> thay chủ đầu tư** trong lúc thi công, mỗi cái kèm cái giá nếu nó sai. Chủ đầu tư
> đọc danh sách này để lật lại bất cứ cái nào.
>
> Sổ thi công đầy đủ (báo cáo từng task, số đo, output test) nằm ngoài git ở
> `.superpowers/sdd/2026-09-16-nhap-lo-in-nhan-quet-ma/`. Ảnh chụp đo đạc nhãn ở
> thư mục scratchpad của phiên.

## Quyết định của CHỦ ĐẦU TƯ (không phải của điều phối)

- **Bỏ hẳn bố cục nhãn theo ảnh mẫu SPD** (16/09/2026, "ok bỏ bố cục A đi em").
  Nhãn chỉ còn một bố cục, mã vạch chạy hết chiều ngang 47mm. Lý do: Code 128 cần
  vùng yên tĩnh 2,5mm mỗi đầu; cột trái của bố cục mẫu chỉ chừa được 0,7mm ở mã dài
  nhất. Đổi lấy mã vạch quét được, chấp nhận lệch khỏi ảnh mẫu.

## Quyết định của điều phối

- # SDD ledger — plan: docs/superpowers/plans/2026-09-16-nhap-lo-in-nhan-quet-ma.md

Spec: docs/superpowers/specs/2026-09-16-nhap-lo-in-nhan-quet-ma-design.md (đọc được — mọi ruling dưới đều có thẩm quyền để soi vào)
Nhánh: feat/mo-rong-vi-tri-kho-warehouse · BASE khi bắt đầu: e6d3fe4
Lưu ý môi trường: BA bench chung một máy, agent thi công phải TUẦN TỰ (chung một CSDL erptest.local).

## Rà trước khi thi công — cặp task dùng chung file hoặc giao diện

| Cặp | Bên sản xuất | Bên tiêu thụ | Kết quả |
|---|---|---|---|
| T1 → T3 | `Batch.custom_o_in_tem` | nhánh ưu tiên trong `goi_y_o` | tên field khớp |
| T1 → T6 | `Batch.custom_so_goi` | `_dam_bao_lo` ghi | khớp |
| T1 → T7 | cả 3 field | `du_lieu_tem` đọc | khớp |
| T1 ↔ T9 | `hooks.py` `doc_events` | `hooks.py` `doctype_js` | HAI dict khác nhau, không đụng. Cả hai task đều đã có câu dặn kiểm khoá trùng |
| T2 → T5 | `kiem_tra_do_dai` | `BatchEntry.kiem_tra_so_lo` | khớp |
| T2 ↔ T8 | `so_module` (Python, TÍNH) | `so_module` (JS, ĐO) | **trùng tên có chủ ý** — xem Ruling A |
| T3 → T4 | `goi_y_o(vat_tu, kho, so_lo=None)` | gọi 3 tham số | khớp |
| T3 → T7 | cùng chữ ký | gọi 2 tham số (lô chưa tồn tại) | khớp — tham số có mặc định |
| T5 → T6 | lớp `BatchEntry`, JSON bảng con | `on_submit` ghi `lo_da_tao`/`so_goi` | khớp SAU khi thêm `allow_on_submit` (e6d3fe4) |
| T5 → T6 | `validate` cho qua lô trùng của CHÍNH mặt hàng | `_dam_bao_lo` dùng lại lô đó | khớp — hai bên nói cùng một điều |
| T7 → T8 | `du_lieu_tem` trả dữ liệu ĐÃ định dạng | `ve_tem` chỉ đặt chữ | khớp |
| T7 → T9 | 3 hàm whitelist | nút trên màn hình | khớp |
| T8 → T9 | `erpnext.warehouse_operations.tem_lo` | `frappe.require` rồi gọi | khớp |
| T8 → T8 | `ve_tho()` thêm vào `tem_vi_tri.js` | `so_module` của chính T8 | khớp; file đã có trong danh sách Modify (e6d3fe4) |
| T9 → T10 | `batch_entry.js` | T10 thêm ô quét vào chính file đó | khớp, đúng thứ tự |
| T4 ↔ — | `location_transfer.js` | không task nào khác chạm | sạch |
| T11 ↔ — | workspace json, `test_giao_dien.py` | không task nào khác chạm | sạch |

## Rà trước — từng task có tự mâu thuẫn không

| Task | Kiểm | Kết quả |
|---|---|---|
| T1 | test gọi `_ncc_thu`/`_phieu_nhap_nhap` — định nghĩa ngay trong file đó, và T5 import lại | nhất quán |
| T2 | 3 con số trong test so với công thức trong mã: 13 chữ số lẻ → 2+6=8 ký hiệu → 123 module; 11 chữ số lẻ → 7 → 112; `"A"*20` → 255 | **tính lại bằng tay, cả ba đúng** |
| T2 | `int(28.0/0.25)` và `int(47.0/0.25)` — 0,25 là luỹ thừa 2 nên chia đúng tuyệt đối, không có chuyện 111.999 | an toàn |
| T3 | thứ tự chạy theo bảng chữ cái đặt `test_tra_dung_o_da_in...` CUỐI; nó cần `6B01020101` trống, và không bài nào trước đó để tồn ở đó | nhất quán — nhưng xem Ruling B |
| T4 | test đòi hai lô cùng mặt hàng ra hai ô; mã đổi khoá đệm thành cặp | nhất quán |
| T5 | `_dong()` không đặt `ten_hang` — field không `reqd` | nhất quán |
| T5 | `items` là Table có `reqd: 1` — Frappe hỗ trợ | nhất quán |
| T6 | `_` và `make_autoname` — file đã import `_`, plan dặn thêm `make_autoname` | nhất quán |
| T7, T10 | thân test để `...`, docstring là yêu cầu | có chủ ý — xem Ruling C |

## Rulings trước khi thi công

- **Ruling A** — `so_module` tồn tại HAI bản (Python `vitri/ma_vach.py` TÍNH, JS trong `tem_lo.js` ĐO từ SVG mà JsBarcode dựng). Không hợp nhất. Vì sao: bản JS đo chính thứ sắp được in ra, nên nó đúng kể cả khi JsBarcode đổi cách mã hoá; bản Python phải chặn từ lúc nhập, trước khi có SVG nào. Hợp nhất là chọn một trong hai chỗ để sai. Giá nếu sai: reviewer báo trùng lặp và ta mất một vòng tranh luận; không ai mất dữ liệu.

- **Ruling B** — bài `TestUuTienOInTem` dùng chung nền `_NenGoiY` với `TestGoiY`. `FrappeTestCase` rollback theo LỚP nên không rò chéo, nhưng đây đúng là lớp lỗi đã cắn dự án ba lần. Dặn người thi công: chạy `test_goi_y_o` HAI lần liên tiếp, lần hai phải xanh y hệt. Giá nếu sai: một bài chập chờn, tốn một vòng sửa.

- **Ruling C** — 18 thân test để `...` ở T6/T7/T10 là hợp đồng, không phải chỗ trống: docstring nói bài phải chứng minh gì. Giao cho reviewer từng task bắt, rẻ hơn việc điều phối viết sẵn 18 thân bài lúc này. Giá nếu sai: một task bị trả lại vì test rỗng — đúng thứ vòng review sinh ra để bắt.

- **Ruling D** — thi công TUẦN TỰ tuyệt đối, không bao giờ hai agent cùng lúc. Ba bench chung một máy và chung CSDL `erptest.local`; hai agent cùng chạy test là hai transaction đè nhau. Giá nếu sai: test đỏ ngẫu nhiên, và tệ hơn là dữ liệu thử rò ra CSDL thật.

## Tiến độ

- Task 1: **Ruling E** — phát hiện này MÂU THUẪN với văn bản kế hoạch (chính brief viết `ncc_khac = self.ncc`). Phán quyết: phát hiện ĐÚNG, kế hoạch SAI, sửa bài test. Vì sao: một bài test phải chứng minh đúng thứ nó tuyên bố; giữ nguyên là để lại một bài xanh vĩnh viễn ở đúng chỗ dễ hồi quy nhất. Giá nếu sai: một vòng sửa thừa cho một file test.

- Task 2: **Ruling F** — phát hiện "Critical: commit ghi Co-Authored-By: Claude Haiku 4.5 thay vì Opus 5" bị BÁC. Không viết lại lịch sử. Vì sao: agent đó LÀ Haiku, dòng đó đang đúng sự thật; đổi thành Opus 5 là biến một dòng đúng thành sai. Phần truy vết là dòng `Claude-Session`, khớp trên cả ba commit. Lỗi ở dispatch của tôi. **Sửa cách giao việc từ Task 3 trở đi: chỉ bắt buộc dòng `Claude-Session` nguyên văn, dòng `Co-Authored-By` để agent ghi đúng model của nó.** Giá nếu sai: nhánh có tên model lẫn lộn — dễ đọc hơn chứ không khó hơn.

- Task 2: **Ruling G** — Minor "ba con số tĩnh" được NÂNG lên fix round thay vì hoãn. Vì sao: đây là lớp lỗi "màn hình nói sai sự thật" dự án đã dính nhiều lần, và cách chặn chỉ tốn một bài test (khoá 26/23/13 vào chính `so_module`), không phải đổi mã sản phẩm. Giá nếu sai: một bài test thừa.

- Task 3: **Ruling H** — mối lo số 1 của implementer ĐÚNG: bài `test_o_da_in_dang_ngung_dung_thi_bo_qua` (brief tôi viết) tắt `disabled` trên chính Ô LÁ, nên một cài đặt viết tay `sl.disabled = 0` bỏ hẳn luật thừa kế của `to_tien_tat()` vẫn làm bài xanh. Bài không khoá được đúng thứ nó sinh ra để khoá. Phán quyết: sửa test, mở thêm vế TỔ TIÊN, kèm tự kiểm chứng đột biến. Vì sao xử TRƯỚC khi đưa soát: đây là mối lo về tính đúng đắn, không phải quan sát. Giá nếu sai: một vòng sửa thừa cho một file test.

- Task 4: **Ruling I** — mối lo của implementer ĐÚNG và nặng hơn nó đánh giá. Bộ lọc JS `includes("tem")` (brief tôi viết) khớp CẢ câu tem-đúng ("theo ô đã in trên tem của lô X") LẪN câu tem-hỏng, nên màn hình báo "tem cũ không dùng được" cho dòng có tem hoàn toàn đúng — đúng lớp lỗi "màn hình nói sai sự thật". Thêm một lý do implementer chưa nêu: cả hai câu đi qua `__()` nên DỊCH ĐƯỢC; bản tiếng Anh sẽ không có chữ "tem" và bộ lọc im lặng khớp 0 dòng. So khớp chuỗi đã dịch là sai nguyên tắc, không chỉ sai kết quả.
  Phán quyết: bỏ hẳn so khớp chuỗi. `goi_y_o` trả BỘ BA `(o, ly_do, tem_hong)`; `xep.py` gắn `d["tem_hong"]`; JS lọc theo cờ. Chấp nhận mở lại file của Task 3 (đã đóng) vì chuỗi lý do là VĂN BẢN CHO NGƯỜI ĐỌC, không phải giao thức giữa hai tầng. Giá nếu sai: phải sửa lại mọi nơi gọi `goi_y_o` (hiện chỉ `xep.py` + test), và Task 7 phải nhận bộ ba.

- Task 5: **Ruling J** — implementer phát hiện `test_so_lo_chi_co_khoang_trang_thi_chan` xanh kể cả khi xoá hẳn `kiem_tra_so_lo()`, vì `reqd: 1` của Frappe đã chặn trước. Phát hiện ĐÚNG. Nhưng lý do sâu hơn: `(d.so_lo or "").strip()` làm HAI việc — chặn rỗng (thừa với `reqd`) và CHUẨN HOÁ (không thừa, rất quan trọng: `Batch.autoname` lấy `batch_id` làm TÊN bản ghi, nên khoảng trắng thừa đi thẳng vào tên lô, vào mã vạch trên nhãn, và quét ra không khớp). Bài test đang kiểm nhánh vô dụng và bỏ sót nhánh đáng giá. Phán quyết: đổi bài sang khoá CHUẨN HOÁ; giữ nguyên dòng chặn rỗng trong mã (hai lớp cho một thứ rẻ tiền, chỉ đừng giả vờ có test khoá nó). Giá nếu sai: một bài test kiểm nhầm chỗ.

- Task 6: **Ruling K** — Important 1 (KHOÁ CHẾT) là phát hiện thật, điều phối TỰ XÁC MINH trong mã: `purchase_receipt.py:417-422` `ignore_linked_doctypes` chỉ có GL Entry / Stock Ledger Entry / Repost Item Valuation / Serial and Batch Bundle. Duyệt cả BE lẫn PR rồi thì huỷ BE bị guard của ta chặn, huỷ PR bị `LinkExistsError` chặn → cả hai đứng vĩnh viễn ở docstatus 1, phải sửa CSDL tay. Phán quyết: sửa, hai phần — (a) thêm `"Batch Entry"` vào `ignore_linked_doctypes` của PR (file KHÔNG nằm trong danh sách cấm; quy tắc vàng CLAUDE.md nói sửa thẳng mã lõi khi nghiệp vụ đòi); (b) đổi guard `on_cancel` từ `!= 0` sang chỉ chặn khi PR `docstatus == 1`, để PR đã huỷ mở được đường thoát. Giá nếu sai: một điểm xung đột khi merge ERPNext bản mới, trên đúng một dòng tuple.

- Task 6: **Ruling L** — implementer nêu rằng phát hiện (3) không chứng minh được qua vòng đời Document bình thường, vì `nha_cung_cap` có `fetch_from: phieu_nhap.supplier` nên LUÔN bằng NCC của phiếu; hai đường (giá trị tường minh vs móc lo_ncc) không bao giờ khác nhau qua đường thường. Họ dùng test bạch hộp gọi thẳng `_dam_bao_lo`. Điều phối chấp nhận TẠM, giao re-reviewer phán xét lại lập luận. Hệ quả đáng ghi: dòng `"supplier": self.nha_cung_cap` trong `_dam_bao_lo` là THỪA trong sản xuất (móc lo_ncc điền đúng giá trị đó) — giữ lại như lớp phòng vệ, giống ca `.strip()` ở Task 5.

- Task 6: fix round 1/5 re-review — cả 6 phát hiện ĐÃ XỬ. Re-reviewer tự đọc `document.py:1148-1151` xác nhận `validate()` KHÔNG chạy trong flow `cancel()` → guard lớp 1 không sinh khoá chết thứ hai. Cũng tự đọc `base_document.py:820-825` xác nhận `fetch_from` không có `fetch_if_empty` nên fetch lại MỌI lần lưu → lập luận của implementer về test bạch hộp ĐÚNG (Ruling L xác nhận). 10/10 đột biến đều có output.

- Task 8: **Ruling M — LỖI SẢN PHẨM ĐANG CHẠY THẬT, phát hiện giá trị nhất của cả kế hoạch.** Implementer đo được `tem_vi_tri.js::ve()` ghi đè viewBox của JsBarcode bằng `0 0 100 h` → **tem vị trí kho đang in mã vạch CỤT, chỉ 44,6% số vạch**. Điều phối TỰ XÁC MINH: `apps/frappe/frappe/public/js/frappe/form/controls/barcode.js:51` chạy `$(svg).attr("width","100%")` ngay sau `JsBarcode(...)`, nên `parseFloat` ra 100 thay vì bề rộng thật; 112 module × 2px = 224px, giữ 100 → 44,6%, khớp CHÍNH XÁC số đo. Tem vẫn rộng đúng 28mm và vẫn trông như mã vạch bình thường nên KHÔNG phép đo bố cục nào bắt được. Lỗi CÓ TỪ TRƯỚC khối C.
  Phán quyết: **chấp nhận việc implementer đi ngược chỉ thị "thêm, không đổi `ve()`"** — chỉ thị đó tôi viết khi chưa biết điều này. Giá nếu sai: không có; giữ nguyên thì cả tem vị trí lẫn tem lô đều in mã không quét được.

- Task 8: **Ruling N** — bỏ phép kiểm "bề rộng mã vạch đúng 28,0/47,0 mm" trong brief (SAI, vì giữ hằng số + preserveAspectRatio=none là ép module hẹp lại đúng dạng hỏng cd749e16 đã sửa). Thay bằng: **0,25 mm mỗi module, sai số ≤ 0,01 mm**. Bề rộng nay là số module × 0,25, tức một TRẦN chứ không phải hằng.

- Task 8: **Ruling O** — cỡ chữ F7/F8/F9 trong kế hoạch tôi viết KHÔNG VỪA cột 17,0mm (đo: 18,42 / 18,80 / 17,26mm). Không lấy con số ai đoán: bắt implementer ĐO ra cỡ chữ nguyên lớn nhất vừa với biên ≥0,5mm. **Sàn cứng F9 ≥ 18pt** (ô đó tồn tại để đọc từ giữa lối đi; implementer đề xuất 16 là bỏ mục đích). Không vừa ở 18pt thì báo lên — khi ấy là vấn đề cấu trúc cột, tôi quyết.

- Task 8: **Ruling P** — bố cục B nhồi F6+F7 = 38,04mm vào hàng 29,4mm (lỗi CẤU TRÚC trong kế hoạch tôi viết). Sửa: F5+F7 chung hàng R4, F6 một mình R5. Và dựng lại chiều cao hàng theo ràng buộc "mỗi hàng ≥ hộp chữ cao nhất trong nó, đo THẬT" — phải dùng hộp chữ chứ không phải chiều cao chữ hoa, vì dấu tiếng Việt đâm xuống (ạ/ợ/ậ) sẽ chạm dù chữ hoa không chạm.

- Task 8: **Ruling Q** — khung đo headless BẮT BUỘC phải tái hiện `barcode.js:51` (`$(svg).attr("width","100%")`). Chỗ đó chính là nơi con bug sống; khung đo thiếu dòng đó thì mọi số đo về viewBox/số module không chứng minh gì về hành vi thật.

- Task 8: **Ruling R — BỎ HẲN BỐ CỤC A.** Quyết định nằm ở vùng yên tĩnh, không phải cỡ chữ. Code 128 cần ≥10 module = 2,5mm mỗi đầu; mã 112 module cần 28,0 + 5,0 = **33,0mm**, cột trái của A chỉ có **29,4mm** — không đủ với BẤT KỲ cỡ chữ hay cách chia cột nào, vì cột trái không nới được nếu cột phải còn phải chứa F9. Và 112 module chính là NGƯỠNG ĐỊNH NGHĨA của A: implementer đo được ở mã dài nhất mà A nhận, vùng yên tĩnh chỉ còn **0,7mm ≈ 2,8 module**, chưa tới 1/3 chuẩn.
  Cùng hạng lỗi với bug viewBox: nhãn TRÔNG ĐÚNG, đo bố cục KHÔNG bắt được, chỉ máy quét mới biết — lúc ấy tem đã dán lên hàng. Spec §6.4 đã chốt nguyên tắc cho đúng hạng này ("không bao giờ thu module dưới 2 dot để nhét vừa"); vùng yên tĩnh thiếu là cùng một đánh đổi, khác chỗ.
  B cho mã vạch cả 47,0mm → 112 module + 5,0mm yên tĩnh chỉ hết 33,0mm, **dư 14,0mm**. Và B là chỗ DUY NHẤT số gọi 5 chữ số không bị cắt.
  Giá nếu sai: lệch khỏi ảnh mockup chủ đầu tư đã duyệt nhiều hơn một bậc (F9 nhỏ hơn, F7/F8 xuống hàng riêng). **PHẢI báo chủ đầu tư.**

- Task 8: **Ruling S** — BỎ sàn cứng "F9 ≥ 18pt" của Ruling O. Sàn đó đặt khi chưa biết ngân sách chiều cao của B đã cạn (tổng sàn 26,232/27,0mm). Thay bằng: tối đa hoá F9 dưới ràng buộc ưu tiên — vùng yên tĩnh ≥2,5mm KHÔNG đánh đổi > không ô nào cắt kể cả số gọi 5 chữ số > không va chạm > tổng đúng 27,0mm. Mã vạch quét được quan trọng hơn cỡ chữ số gọi.

- **Ruling R được CHỦ ĐẦU TƯ XÁC NHẬN (16/09/2026): "ok bỏ bố cục A đi em".** Không còn là phán quyết của điều phối — là quyết định của chủ đầu tư. Nhãn lô chỉ còn MỘT bố cục, mã vạch hết chiều ngang 47mm. Việc lệch khỏi ảnh mockup SPD đã được chấp nhận có ý thức, đánh đổi lấy mã vạch quét được.

- Task 8: **Ruling T** — F9 dừng ở 19pt, KHÔNG đổi F11 lấy 1pt. 20pt thiếu đúng 0,026mm và chỗ duy nhất còn lấy được chiều cao là F11 — chữ người đọc dưới mã vạch, tức ĐƯỜNG LUI khi máy quét hỏng. Đổi đường lui lấy 1pt cỡ chữ là đánh đổi sai chiều. Giá nếu sai: số gọi nhỏ hơn dự tính 1pt.

- Task 8: **Ruling U** — giữ nhánh cảnh báo "vùng yên tĩnh thiếu" dù implementer chứng minh dải 181–188 module RỖNG (thang Code 128 là 35+11k nên nhảy bậc 11: …167, 178, 189; bậc lớn nhất vẽ được là 178 → 2,75mm yên tĩnh, vẫn trên chuẩn). Giữ làm lưới đỡ cho ngày phép tính module đổi. Giá nếu sai: vài dòng mã không bao giờ chạy.

- Task 8: **Ruling V** — vá BA phần, không vá một: (1) `tem_vi_tri.js` kiểm `data-barcode-value === String(ma)` ở cả `ve()` lẫn `ve_tho()`, thất bại thì trả rỗng chứ không trả SVG lần trước; (2) `tem_lo.js:266` đo hỏng thì KHÔNG in mã nào + msgprint đỏ (vá 1 mà không vá 2 thì lỗi chỉ đổi dạng thành "mã kéo giãn im lặng ra 47mm"); (3) `ma_vach.py` chặn ký tự ngoài ASCII ngay lúc NHẬP, câu báo nêu đích danh ký tự vi phạm và vị trí. Giá nếu sai: chặn nhầm một số lô hợp lệ nào đó — nhưng Code 128 thật sự không mã hoá được ký tự ngoài ASCII nên không có ca hợp lệ nào bị chặn oan.

- Task 8: **Ruling W** — GIỮ NGUYÊN implementer cho vòng 4, không leo thang model như quy trình mặc định. Vì sao: quy tắc "vòng 4-5 đổi người, nâng model" sinh ra cho vòng lặp KHÔNG hội tụ (cùng một lỗi lặp lại). Ở đây mỗi vòng tìm ra lỗi MỚI, KHÁC nhau, đều thật — đó là hội tụ, không phải kẹt. Implementer đã ở opus và đang làm tốt; đổi người là mất ngữ cảnh mà không được gì. Giá nếu sai: một vòng nữa với cùng người.

- Task 8: **Ruling X** — mục 3 của implementer ("không gắn `kiem_tra_ky_tu` vào `Batch` được vì cấm sửa `batch.py`") chỉ đúng một nửa. Gắn được qua `doc_events["Batch"]["validate"]` trong hooks.py — đúng cơ chế `lo_ncc.dien_ncc_tu_chung_tu` đang dùng, không đụng file cấm. Bắt DÙNG LẠI `ma_vach.kiem_tra_ky_tu`, không chép. Đóng luôn đường tạo lô trực tiếp (nhập tay, import).

- Task 8: **Ruling Y** — tem thiếu mã vạch PHẢI nói ra điều đó TRÊN GIẤY. Hàng mã vạch đang trống rỗng; một khoảng trắng không nói gì, người cầm tem không biết đó là lỗi hay thiết kế. Cảnh báo đỏ chỉ sống trên màn hình, con tem thì đi theo thùng hàng suốt vòng đời. Thay chỗ mã vạch bằng dòng chữ trong ĐÚNG hàng đó → không tốn thêm chiều cao, ngân sách 0,503mm không bị đụng.

- Task 8: **Ruling Z** — guard `if not doc.is_new(): return` trên `kiem_ky_tu_lo` là ĐÚNG. `batch_id` là TÊN bản ghi; kiểm cả lúc cập nhật sẽ biến một lô cũ xấu thành bản ghi KHÔNG AI SỬA ĐƯỢC, và mọi lần ERPNext tự cập nhật `batch_qty` / huỷ chứng từ / đối soát đều nổ. Hệ quả (lô cũ mang ký tự xấu vẫn tồn tại) đã được xử ở tầng JS: khi in thì bắt và in dòng chữ thay mã vạch. Quét sạch dữ liệu cũ cần một patch rà `Batch.batch_id` — **ngoài Task 8, ghi sổ cho review tổng cuối**.

- Task 9: **Ruling AA** — gật việc thêm file thứ ba `in_nhan_lo.js`. Lập luận implementer đúng: chép trình tự `dat_o_in_tem → du_lieu_tem → in_xap` làm hai bản là mở cửa "một bản quên bước GHI, tem in VT — im lặng". Cùng nguyên tắc đã áp ở `ma_vach.py`.

- Task 9: **Ruling AB** — phát hiện số 5 của implementer ("truyền mảng vào `du_lieu_tem` hỏng lặng lẽ, thành một tên lô bịa") là **LỖI THẬT phải vá**, không phải quy ước gọi. Implementer đề xuất "gọi từng lô, nhap_lo.py giữ nguyên" — BÁC. Chữ ký là `list[str] | str` tức nó TỰ NHẬN là nhận mảng; qua RPC mảng tới nơi thành chuỗi JSON và `isinstance(str)` cho True nên cả chuỗi `'["A","B"]'` thành MỘT tên lô. Người viết mã sau sẽ truyền mảng và sẽ không đọc báo cáo này. Vá bằng `frappe.parse_json`. Giá nếu sai: một hàm nhận thêm một dạng đối số.

- Task 9: **Ruling AC** — bắt dọn dữ liệu `T9-*` khỏi erptest.local dù implementer muốn giữ làm bằng chứng. Dự án có tiền lệ: một lần chạy bị giết giữa chừng để lại 103 dòng sổ vị trí + hồ sơ chuyển đổi treo, phải dọn tay. Bằng chứng sống trong BÁO CÁO và ảnh chụp, không sống trong CSDL.

- Task 9: **Ruling AD** — chấp nhận việc KHÔNG xoá hết được dữ liệu T9-*. Lý do là một BẤT BIẾN CỐ Ý của chính module: `LocationLedgerEntry.on_trash` chặn tuyệt đối ("Sổ chỉ ghi thêm; huỷ chứng từ sẽ ghi bút toán đảo"), không cờ, không cửa thoát. 6 LLE ghim 6 SLE ghim PR ghim Batch ghim Item. Còn lại: LLE 6 (tổng 0.0), SLE 6 (tổng 0.0), PR 1 (docstatus 2), Batch 3 + Item 3 đã `disabled=1`. Xoá sạch = 0 với Batch Entry / Batch Entry Item / Item Location Preference / Location Balance / Serial and Batch Bundle. **Không một câu SQL thô** — implementer từ chối lách bất biến, đúng. Tổng số lượng đều 0 nên không có tồn ma. Giá nếu sai: vài bản ghi thử vô hiệu hoá nằm lại trên site chơi.

- Task 10: **Ruling AE** — GẬT việc không dùng `erpnext.utils.BarcodeScanner` dù brief bước 4 nói dùng. `scan_api_call()` hard-code đối số `search_value`; `process_scan()`/`update_table()` hard-code tên trường bảng con chuẩn ERPNext (`item_code`, `batch_no`) trong khi bảng con Batch Entry dùng `vat_tu`/`so_lo`. Phương án "đúng brief" đòi thêm trường `scan_barcode` + `allow_on_submit` vào doctype — cái giá là **mọi lần quét ghi xuống một chứng từ ĐÃ DUYỆT chỉ để chứa một ô nhập tạm**. Ghi vào chứng từ đã duyệt để giữ giá trị nhất thời là sai nguyên tắc. Brief sai, không phải implementer. Bắt ghi chú thích VÌ SAO không dùng, kẻo người sau "dọn gọn" bằng cách chuyển sang dùng nó.

- Task 10: **Ruling AF** — GẬT việc đặt khung quét ở đầu form. Hai nửa yêu cầu của tôi ("dùng `frm.dashboard`" + "dưới bảng con") LOẠI TRỪ NHAU vì `frm.dashboard` luôn ở đầu form (hành vi cố định của `form.js`). Implementer chọn đúng nửa; đó cũng là chỗ ERPNext vẫn đặt phản hồi quét nên thủ kho không phải học chỗ mới.

- Task 10: **Ruling AG** — bắt thêm bài test thứ 5 cho `loai == "kho"` dù brief chỉ định 4 bài. `loai` là HỢP ĐỒNG mà phía JS dựa vào để quyết hiển thị gì; một nhánh hợp đồng không có bài khoá là nhánh sẽ âm thầm hỏng, và hỏng ở tầng giao diện nơi không test tự động nào khác phủ. Giá nếu sai: một bài test thừa.

- Task 10: **Ruling AH** — điều phối TỰ GREP và tìm ra lỗi này ở **NĂM chỗ**, không phải một: `quet.py:181`, `nhap_lo.py:102/193/316`, `xep.py:106`. Cả năm đều trong khối `except` có mục đích "đừng để một bản ghi hỏng giết cả lời gọi". `Item.name` dài tới 140 ký tự một mình nên `xep.py` và `nhap_lo.py` CŨNG với tới được. Vá một chỗ bỏ bốn chỗ là để lại con bug ở bốn nơi, trong đó `xep.py` là màn hình thủ kho dùng HẰNG NGÀY. Bắt viết MỘT hàm cắt dùng chung cho cả năm. Giá nếu sai: một hàm tiện ích nhỏ và bốn chỗ gọi nó.

- Task 10: **Ruling AI** — PARK việc thêm bài test cho 2 chỗ còn lại ở `nhap_lo.py`. Re-reviewer phán "lợi ích giảm dần, không phải rủi ro thật": cả ba lời gọi nằm CÙNG một file, nên mọi refactor/revert/find-replace xoá `cat_tieu_de` sẽ đồng thời chạm dòng 204 — nơi ĐÃ có bài khoá — và đỏ ngay. Chỉ một kiểu đột biến né được: sửa tay đúng một dòng mà không đụng dòng 204, không phải hình dạng hồi quy thường gặp. **Ghi lại cho ai sau này muốn thêm: thêm cho `lay_dong_tu_phieu_nhap`, KHÔNG phải `dat_o_in_tem`** — vì đầu vào dài ở đó đến từ `Item.name` (trần 140, tiền tố ~46 → tên vật tư y tế tiếng Việt >94 ký tự là chuyện thật), tức đường chạm THẬT; còn `dat_o_in_tem` phải dựng fixture giả tạo mà chính ứng dụng không bao giờ tạo ra được. Giá nếu sai: một đường lỗi hiếm không có bài khoá.

- Task 11: **Ruling AJ** — implementer sửa 3 chỗ trong tài liệu KHÁC brief vì dữ liệu thật nói khác. Điều phối TỰ XÁC MINH: **84/84 mặt hàng có quản lý lô trên site đều `create_new_batch = 0`, và 0 mặt hàng có `batch_number_series`.** Nên duyệt phiếu nhập trước khi khai lô sẽ khiến `Batch.autoname` ném `Batch ID is mandatory` — tức hệ **BÁO LỖI CHẶN LẠI**, không âm thầm sinh số lô máy như spec §12 giả định. CHẤP NHẬN bản sửa. Nhưng đây là thiết lập THEO TỪNG MẶT HÀNG, không phải bảo đảm cấu trúc: ai bật `create_new_batch` lên là rủi ro quay lại. Mệnh lệnh "nhập lô TRƯỚC" giữ nguyên, chỉ hậu quả nêu đúng. Giá nếu sai: tài liệu mô tả một hậu quả nhẹ hơn thực tế trên site khác.

- **C1 (Critical) — mã quá dài VẪN ĐƯỢC VẼ.** `tem_lo.js:283-296`: `m > TRAN_VE_DUOC` (188) chỉ `msgprint` đỏ rồi vẫn vẽ với `rong = Math.min(m*X_MM, 47.0)` → module bị ép **dưới 2 dot**, đúng thứ spec §6.4 cấm và đúng dạng hỏng cd749e16 đã sửa một lần.
  **Khe giữa hai task:** `kiem_tra_do_dai` CHỈ sống trong `Batch Entry.validate`; móc `doc_events["Batch"]["validate"]` (Ruling X) chỉ nâng `kiem_tra_ky_tu` lên tầng Batch, **bỏ lại `kiem_tra_do_dai`**. Mà `Purchase Receipt Item.batch_no` là **Link tới Batch** nên số lô gõ tay đi được qua form Batch / quick-entry / Data Import — đúng ba đường HDSD tự liệt kê.
  Hỏng ra sao: nhánh `m = 0` in dòng chữ LÊN GIẤY; nhánh này in một mã vạch TRÔNG BÌNH THƯỜNG, quét ra SAI KÝ TỰ. Cảnh báo đỏ chết khi đóng hộp thoại.
  **Ruling AK** — vá ở `tem_lo.js` (cho `m > TRAN_VE_DUOC` đi chung đường với `m = 0`), **KHÔNG** thêm `kiem_tra_do_dai` vào `kiem_ky_tu_lo`: móc đó chạy cho MỌI Batch toàn hệ kể cả lô sản xuất, thêm vào là chặn luồng không liên quan. Trần 188 module là ràng buộc CỦA CON TEM nên thuộc tầng vẽ tem.

- **Ruling AL** — PARK chú thích `in_nhan_lo.js:50` trỏ `tem_lo.js:589` trong khi hàm nay ở dòng 620 (các vòng sửa đẩy số dòng). Implementer đúng khi KHÔNG sửa file của agent khác giữa chu kỳ review của họ. Chỉ là chú thích, không phải tham chiếu chạy thật. Đề xuất cho người sau: bỏ số dòng, chỉ nhắc tên hàm. Giá nếu sai: một chú thích chỉ sai chỗ.

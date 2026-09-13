# Những quyết định tự chốt trong lúc thi công cây vị trí (11–13/09/2026)

Nhánh `feat/mo-rong-vi-tri-kho-warehouse`, thi công theo
`docs/superpowers/plans/2026-09-11-cay-vi-tri-ma-10-ky-tu.md`.

Trong lúc thi công có **17 chỗ** kế hoạch không trả lời được, hoặc trả lời sai. Chúng được
chốt tại chỗ để không dừng cả đợt. Tài liệu này ghi lại **cái gì đã chốt, vì sao, và cái giá
nếu chốt sai** — để chủ dự án lật lại cái nào thấy cần.

Bốn cái quan trọng nhất là **lỗi trong chính kế hoạch**, phát hiện bằng cách **đo trên dữ
liệu thật** chứ không phải đọc code.

---

## Bốn lỗi của kế hoạch, và hậu quả nếu cứ làm theo

| # | Kế hoạch viết | Hậu quả nếu làm đúng y vậy |
|---|---|---|
| F8 | Vị từ tổ tiên dùng `lft <= … AND rgt >= …` | **Đứng cả kho.** Mọi bản ghi cũ đều `lft=rgt=0` nên chúng coi nhau là tổ tiên; ô hệ thống giữ toàn bộ tồn có 128 "tổ tiên" giả. Tắt bất kỳ ô nào — thao tác hợp lệ — là loại luôn ô đó khỏi ứng viên, mọi phiếu xuất ném lỗi giữa `Stock Ledger Entry.on_submit` |
| — | Báo cáo cây chỉ cần khai `parent_field` trong `.js` | **Cây không bao giờ hiện ra.** `frappe-datatable` không đọc khoá đó; nó đọc trường `indent` số học. Báo cáo vẫn chạy, test vẫn xanh |
| F9 | Bài kiểm cho truy vấn dựng thông báo | **Không khoá được gì.** Khi mọi ô có hàng đều nằm dưới nút đã tắt, đột biến `1=1` trả đúng cùng tập ô nên bài vẫn xanh. Phải có ô đối chứng ở nhánh khác |
| F6 | Bỏ 2 ký tự mã kho vì "kho đã nằm ở trường `kho`" | Đúng về lưu trữ, nhưng **quên `ma_o` là khoá chính**. Mã ô nay **duy nhất toàn hệ** — hai kho không thể cùng dùng một ký hiệu Khu |

**Hệ quả vận hành của F6, phải nhớ:** ký hiệu **Khu phải cấp phát toàn hệ**, không theo từng
kho. Đã có phép chặn tường minh khi nút cha thuộc kho khác, nhưng người đặt tên khu cần biết
trước.

---

## Hai quyết định tự đẻ ra lỗi mới

Sửa một lỗi im lặng thường mở ra một bề mặt mới. Hai lần trong đợt này:

**F16 → F18.** Bọc `rebuild_tree()` trong `try/except` để không làm vỡ `bench migrate` là
đúng. Nhưng `rebuild_tree` bật cờ `auto_commit_on_many_writes = 1` trước vòng lặp và chỉ tắt
ở dòng sau — lỗi giữa chừng thì cờ **treo**. Trước đây không sao vì lỗi làm chết cả tiến
trình; sau khi nuốt lỗi, `after_migrate` đi tiếp trong cùng kết nối với cờ treo, và **app
khác trên cùng site** có thể bị tự commit sớm. Đã vá bằng `finally`.

**F15.** Chuyển từ patch sang `after_migrate` (vì "cây đã dựng" là **trạng thái cần hội tụ**,
không phải sự kiện một lần) làm tăng diện lộ của rủi ro trên: từ "một lần lúc patch chạy"
thành "mọi lần migrate, mọi site". Vẫn giữ quyết định — nhưng nó là lý do F18 tồn tại.

---

## Ba cách một bài test xanh mà không chứng minh gì

Gặp đủ ba trong một đợt, ba cơ chế khác nhau, cùng một hệ quả. Cả ba chỉ lộ ra khi **chạy đột
biến** — tắt hẳn tính năng rồi xem bài còn xanh không. Không cách nào phát hiện bằng đọc code.

| Cơ chế thoát rollback | Ca cụ thể |
|---|---|
| `commit()` tường minh | Bài kiểm đua hai kết nối; rác để lại làm bài ở **file khác** đỏ giả |
| DDL tự commit | `.insert()` một `Custom Field` gọi `ALTER TABLE` |
| Bảng không nằm trong transaction | Kiểm log bằng cách tra `Error Log` |

**Quy tắc rút ra:** rollback của `FrappeTestCase` chỉ bảo vệ DML trong một transaction. Khi rà
một bài test, hỏi hai câu: *có `commit()` không?* và *có chạm thứ gì đổi schema hoặc nằm ngoài
transaction không?*

**Quy tắc thứ hai:** bài kiểm một thao tác **phá huỷ hoặc ghi đè** phải có **chốt âm** —
khẳng định cả cái bị đổi **lẫn cái phải còn nguyên**. Thiếu nửa sau thì mọi đột biến làm phạm
vi rộng ra đều lọt. Hai bài patch từng thiếu chốt này: một đột biến đổi `WHERE` thành `1=1` sẽ
bẻ gãy mọi bản ghi vị trí, một đột biến bỏ một khoá lọc sẽ xoá **cả cờ bật quản lý vị trí** —
và cả hai bài vẫn xanh.

---

## Hai thứ đang nằm im, và điều kiện để chúng sống

Cho tới khi cây được dựng lại trên một site, **cả hai tính năng này không có tác dụng**:

- **thừa kế `disabled` xuống nhánh** — không ô nào thừa kế từ ai;
- **lấy hàng theo phạm vi** — bị từ chối thẳng, có thông báo tường minh.

Trên `erptest.local` cây đã dựng (0 bản ghi thiếu toạ độ) nên cả hai đã sống. Trên site khác,
chúng sống sau lần `bench migrate` đầu tiên — qua patch `v15_0.dung_lai_cay_vi_tri`, và nếu
lần đó bị bỏ qua thì hook `after_migrate` sẽ thử lại ở mọi lần sau.

**Cảnh báo:** lần dựng cây đầu tiên **kích hoạt thừa kế `disabled` một lượt**. Nếu lúc đó có ô
đang ở trạng thái Ngừng dùng, cả nhánh dưới nó bật chặn ngay. Vì vậy hàm kiểm trước và **bỏ
qua** nếu còn ô đang tắt, kèm log nêu đích danh.

---

## Một bất đối xứng còn tồn tại

`fefo.py` là nơi **duy nhất** lọc `disabled`. Hook **nhập** không lọc gì. Nên hàng vẫn chảy
**vào** một dãy đã tắt trong khi không ô nào trong dãy đó xuất **ra** được — và đối soát vẫn
xanh, vì nó chỉ so tổng.

Hiện chưa chạm được thực tế: luồng nhập dồn hết vào ô "Chưa xếp vị trí", không nhắm ô cụ thể.
Nó trở thành vấn đề thật khi có màn hình khai vị trí lúc nhập (giai đoạn sau).

---

## Một điều "đối soát khớp" KHÔNG chứng minh

`doi_soat_kho` **không đọc `lft`/`rgt`** — nó chỉ so tồn kho với sổ. Nên câu "đối soát khớp"
**không phải** bằng chứng cho cấu trúc cây đúng. Một lần dựng cây gán nhầm ô hệ thống làm con
của một nhánh, hoặc bỏ nó lại với toạ độ rỗng, vẫn cho đối soát khớp. Muốn khoá cấu trúc thì
phải kiểm thẳng `lft`/`rgt` và `parent`.

---

## Hai điểm cố ý để lại

- Câu chẩn đoán khi cây chưa hội tụ hết chỉ gợi ý nguyên nhân "cha treo", trong khi ở nhánh
  chạy sau một lỗi rebuild thì nguyên nhân khả dĩ nhất là chính lỗi đó. *Giá nếu sai:* người
  vận hành đi tìm cha treo không tồn tại — mất thời gian, không mất dữ liệu.
- Một `assertIn` trong bài kiểm phạm vi không tự đứng được (chuỗi kiểm là tiền tố của thứ đã
  được khẳng định riêng). *Giá nếu sai:* một assertion thừa, không phải bài rỗng — cặp
  assertion còn lại vẫn giết được đột biến mục tiêu.

---

## Khe hở cùng hình dạng với F8, chưa chạm tới

Phép chặn "nút cha thuộc kho khác" chỉ đi chiều con → cha. Nút **gốc** (cấp Khu) không có cha
để đối chiếu, nên trường `kho` của nó sửa được tự do và không có phép kiểm nào duyệt con cháu.
Chưa chạm được thực tế vì mới một kho bật quản lý vị trí; kích hoạt khi bật kho thứ hai.

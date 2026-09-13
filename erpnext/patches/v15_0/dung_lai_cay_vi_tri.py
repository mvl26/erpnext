"""Dựng `lft`/`rgt` lần đầu cho `Storage Location` (spec §7, Task 8, 11/09/2026).

`StorageLocation` kế thừa `NestedSet` từ Task 2 (2026-09-11), nhưng bất kỳ bản
ghi nào được TẠO TRƯỚC thời điểm đó (mã 12 ký tự cũ, hoặc ô hệ thống
`ZZZ-CHUA-XEP-<kho>` tạo qua `bat_kho.tao_o_chua_xep()` trước khi có cây) vẫn
mang `lft = rgt = 0` — không ai gọi lại `on_update()`/`update_nsm()` cho nó kể
từ khi trường tồn tại. Trên `erptest.local`, Task 8 đã xoá 128 ô cũ và sinh
lại + `rebuild_tree()` bằng tay; patch này làm đúng việc đó CHO MỌI SITE
KHÁC (đặc biệt site `miyano`, cài đặt riêng, không tự động thừa hưởng thao
tác tay đã làm trên `erptest.local` — xem `miyano-portal-install-patch-trap`).

Không dựng cây thì HAI tính năng dựa vào `lft`/`rgt` NẰM IM hoàn toàn, âm
thầm, không báo lỗi gì (xem `BAN-GIAO-nen-tang-vi-tri-kho.md`, khối "Cập nhật
11/09/2026"):
- thừa kế `disabled` xuống cả nhánh (`fefo.py::_TO_TIEN_TAT` so `lft`/`rgt`
  — không có toạ độ thật thì không ai là tổ tiên thật của ai);
- lấy hàng theo phạm vi một nhánh (`chon_o_xuat(..., pham_vi=...)` bị
  `frappe.throw` thẳng nếu trỏ vào một bản ghi `lft = rgt = 0`, KHÔNG lặng lẽ
  trả sai — nên với `pham_vi` ít nhất có báo lỗi; với thừa kế `disabled` thì
  không có gì báo cả, đây là ca nguy hiểm hơn).

PHÁN QUYẾT F5+F11, ĐÃ CÓ Ở SCRIPT TASK 8, NAY BẮT BUỘC CHẠY QUA `bench
migrate`: trước khi `rebuild_tree()`, kiểm không còn `Storage Location` nào
`disabled = 1`. Lý do: hôm nay (trước khi cây có toạ độ) không ô nào thừa kế
từ ai, nên tắt một nút không có tác dụng gì — một quyết định vận hành hoàn
toàn vô hại tại thời điểm đặt. `rebuild_tree()` cấp toạ độ thật cho TOÀN BỘ
cây trong MỘT lượt, kích hoạt thừa kế `disabled` ngay lập tức, ÂM THẦM (không
có sự kiện nào để người vận hành biết mà chuẩn bị) — nếu đúng lúc đó có một
nút cha đang tắt mà bên dưới còn hàng, phiếu xuất kế tiếp của cả nhánh đó ném
lỗi giữa `Stock Ledger Entry.on_submit`.

QUYẾT ĐỊNH: KHÔNG `frappe.throw` khi gặp tình huống này — GHI LOG RÕ RÀNG rồi
BỎ QUA phần rebuild, để `bench migrate` đi tiếp. Cân nhắc cả hai giá:
- `frappe.throw` chặn đứng TOÀN BỘ `bench migrate`, kể cả các patch KHÔNG
  liên quan xếp sau trong `patches.txt` — với một pipeline triển khai tự
  động (CI/CD chạy `bench migrate` không người canh), một bản ghi
  `disabled = 1` do vận hành kho chủ động đặt (ví dụ đang sửa kệ) sẽ biến
  thành một lần deploy treo cứng, vì một quyết định nghiệp vụ hợp lệ không
  liên quan gì tới việc migrate schema. Patch dọn dữ liệu không có quyền
  phủ quyết một quyết định vận hành đang có hiệu lực.
- Bỏ qua và chỉ log: patch không tự sửa xong việc của mình (cây vẫn thiếu
  toạ độ), và nếu không ai đọc log thì hai tính năng vẫn nằm im — đúng rủi ro
  mà việc này sinh ra để tránh. Giảm nhẹ bằng `print()` (hiện ngay trên
  console lúc chạy `bench migrate`, ai đang canh sẽ thấy ngay) CỘNG
  `frappe.log_error()` (còn lại trong Error Log cho người xem log sau).

Do KHÔNG throw, patch vẫn được `Patch Log` đánh dấu ĐÃ CHẠY dù bỏ qua phần
việc chính — `bench migrate` lần sau sẽ KHÔNG tự thử lại. Đây là đánh đổi có
ý thức, không phải sơ suất: một khi vận hành xác nhận các ô `disabled = 1`
đó đúng chủ đích, việc dựng cây phải làm TAY một lần
(`bench execute frappe.utils.nestedset.rebuild_tree --kwargs "{'doctype':
'Storage Location', 'parent_field': 'parent_storage_location'}"`) — thông
báo log in rõ lệnh này.

IDEMPOTENT theo đúng nghĩa: hàm `execute()` AN TOÀN khi gọi lại nhiều lần
(qua `bench execute` tay, hay trong test) ở bất kỳ trạng thái dữ liệu nào —
không có gì để làm thì thoát ngay (không rebuild vô điều kiện mỗi lần); có gì
để làm thì làm đúng, không giả định số lượng bản ghi cụ thể (site khác nhau
sẽ có số ô khác nhau khi patch này chạy lần đầu).
"""

import frappe
from frappe.utils.nestedset import rebuild_tree

_LENH_REBUILD_TAY = (
	"bench execute frappe.utils.nestedset.rebuild_tree "
	"--kwargs \"{'doctype': 'Storage Location', 'parent_field': 'parent_storage_location'}\""
)


def execute():
	if not frappe.db.exists("Storage Location", {"lft": 0, "rgt": 0}):
		# Cây đã có toạ độ thật (đã chạy patch này trước đó, hoặc đã dựng
		# tay như trên erptest.local ở Task 8) — không có gì để làm. Không
		# rebuild vô điều kiện: rebuild_tree() ghi lại lft/rgt của TOÀN BỘ
		# doctype dù không cần, tốn khoá + I/O vô ích trên mỗi lần migrate.
		return

	so_dang_tat = frappe.db.count("Storage Location", {"disabled": 1})
	if so_dang_tat:
		canh_bao = (
			f"[vi_tri_kho] BỎ QUA dựng cây Storage Location: còn {so_dang_tat} bản ghi "
			"đang `disabled = 1`. rebuild_tree() sẽ cấp toạ độ lft/rgt thật cho TOÀN BỘ "
			"cây trong một lượt, kích hoạt thừa kế `disabled` xuống cả nhánh NGAY LẬP TỨC "
			"và ÂM THẦM — nếu một trong các bản ghi đang tắt là nút cha của ô còn giữ "
			"hàng, phiếu xuất kế tiếp của nhánh đó sẽ ném lỗi giữa "
			"`Stock Ledger Entry.on_submit`. Việc cần làm: xác nhận lại danh sách ô đang "
			"`Ngừng dùng` (Storage Location, lọc disabled = 1) đúng là chủ đích vận hành, "
			"rồi tự chạy dựng cây bằng tay một lần: " + _LENH_REBUILD_TAY + ". Patch này "
			"đã được đánh dấu HOÀN TẤT (không throw để không chặn `bench migrate`) nên sẽ "
			"KHÔNG tự thử lại ở lần migrate sau — bước dựng cây phải làm tay như trên."
		)
		print(canh_bao)
		frappe.log_error(title="vi_tri_kho: dung_lai_cay_vi_tri bo qua", message=canh_bao)
		return

	rebuild_tree("Storage Location", "parent_storage_location")

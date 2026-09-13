"""Dựng `lft`/`rgt` của `Storage Location` — hàm dùng lại được ở nhiều nơi.

VÒNG SỬA 2/5 (review điều phối, Task 8): bản đầu đặt toàn bộ logic này thẳng
trong `erpnext/patches/v15_0/dung_lai_cay_vi_tri.py`. Vấn đề: "cây đã được
dựng" là một TRẠNG THÁI cần HỘI TỤ TỚI, không phải một SỰ KIỆN chạy một lần.
Một patch chỉ chạy đúng một lần rồi `Patch Log` khoá nó lại vĩnh viễn — patch
đó (vòng sửa 1/5) cố tình KHÔNG `frappe.throw` khi gặp `disabled = 1` (để
không chặn đứng `bench migrate` vì một quyết định vận hành hợp lệ), nhưng hệ
quả là nếu đúng lúc `bench migrate` chạy có sẵn một ô `disabled = 1`, patch
bị đánh dấu ĐÃ CHẠY và KHÔNG BAO GIỜ tự thử lại — cây vĩnh viễn không được
dựng cho tới khi có người đọc log rồi gõ tay. Đúng lớp hỏng "nằm im, âm
thầm, mãi mãi" mà cả kế hoạch 2026-09-11 sinh ra để chống.

Nên hàm này được gọi từ HAI nơi, không phải một:
- `erpnext.patches.v15_0.dung_lai_cay_vi_tri` — vẫn giữ, để site CÀI MỚI chạy
  đúng thứ tự khai báo trong `patches.txt` (trước các patch xếp sau có thể
  giả định cây đã có toạ độ).
- `after_migrate` trong `erpnext/hooks.py` — đây mới là cơ chế HỘI TỤ THẬT:
  chạy lại ở MỌI LẦN `bench migrate`, không bị `Patch Log` khoá. Vận hành bật
  lại ô đang tắt rồi `bench migrate` lần sau, cây tự được dựng — không cần
  ai nhớ gõ lệnh tay.

PHẢI RẺ KHI KHÔNG CÓ VIỆC: hàm này chạy ở MỌI lần migrate của MỌI site có
`erpnext` (không riêng site nào bật quản lý vị trí), nên nhánh "đã có cây
rồi" phải thoát ngay sau đúng MỘT câu đếm, không `rebuild_tree` (ghi lại
`lft`/`rgt` của toàn bộ doctype — tốn khoá + I/O), không log ồn ào.
"""

import frappe
from frappe.utils.nestedset import rebuild_tree

_LENH_REBUILD_TAY = (
	"bench execute frappe.utils.nestedset.rebuild_tree "
	"--kwargs \"{'doctype': 'Storage Location', 'parent_field': 'parent_storage_location'}\""
)


def dam_bao_cay_da_dung() -> None:
	"""Dựng `lft`/`rgt` cho các `Storage Location` còn thiếu toạ độ, nếu an toàn.

	PHÁN QUYẾT F5+F11: trước khi `rebuild_tree()`, kiểm không còn bản ghi nào
	`disabled = 1`. Lý do: trước khi cây có toạ độ, không ô nào thừa kế từ ai,
	nên tắt một nút không có tác dụng gì — một quyết định vận hành hoàn toàn
	vô hại tại thời điểm đặt. `rebuild_tree()` cấp toạ độ thật cho TOÀN BỘ cây
	trong một lượt, kích hoạt thừa kế `disabled` xuống cả nhánh NGAY LẬP TỨC,
	ÂM THẦM — nếu đúng lúc đó có một nút cha đang tắt mà bên dưới còn hàng,
	phiếu xuất kế tiếp của cả nhánh đó ném lỗi giữa
	`Stock Ledger Entry.on_submit`.

	KHÔNG `frappe.throw` khi gặp tình huống này — chỉ log rồi bỏ qua phần
	rebuild, để nơi gọi (patch hoặc `after_migrate`) đi tiếp bình thường. Từ
	khi hàm này được gọi lại ở MỌI lần migrate (không riêng lúc patch chạy lần
	đầu), việc "bỏ qua lần này" không còn là ngõ cụt: lần migrate SAU, nếu ô
	đã được bật lại, hàm sẽ tự dựng cây mà không cần ai gõ tay — đây chính là
	lý do hàm này tách khỏi patch và treo thêm vào `after_migrate`.
	"""
	if not frappe.db.exists("Storage Location", {"lft": 0, "rgt": 0}):
		# Nhánh RẺ: không có gì để làm. Không rebuild vô điều kiện — hàm này
		# chạy ở MỌI lần migrate của MỌI site, không riêng site bật vị trí.
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
			"rồi tự chạy dựng cây bằng tay một lần: " + _LENH_REBUILD_TAY + ". Hàm này chạy "
			"lại ở MỌI lần `bench migrate` (treo qua `after_migrate`), nên một khi các ô "
			"đó được bật lại, cây sẽ TỰ dựng ở lần migrate kế tiếp — không cần gõ tay, "
			"trừ khi cần dựng ngay bây giờ."
		)
		print(canh_bao)
		frappe.log_error(title="vi_tri_kho: dam_bao_cay_da_dung bo qua", message=canh_bao)
		return

	rebuild_tree("Storage Location", "parent_storage_location")

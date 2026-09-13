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

VÒNG SỬA 3/5 (review điều phối): "tự hội tụ" ở trên chỉ ĐÚNG khi dữ liệu
LÀNH. Hai ca KHÔNG hội tụ được, dù hàm chạy lại bao nhiêu lần migrate:

1. **Cha treo** (`parent_storage_location` trỏ tới một `name` không tồn
   tại). `frappe.utils.nestedset.rebuild_node` đệ quy TỪ CÁC BẢN GHI GỐC
   (`parent` rỗng) xuống con — một bản ghi có cha treo không phải gốc (vì
   `parent` không rỗng) cũng không phải con của bản ghi NÀO (vì bản ghi cha
   đó không tồn tại để được duyệt tới), nên `rebuild_node` KHÔNG BAO GIỜ chạm
   tới nó. Nó giữ `lft = rgt = 0` VĨNH VIỄN, gọi lại hàm bao nhiêu lần cũng
   vậy — đây là giới hạn thật của "tự hội tụ", không phải một lỗi có thể vá
   bằng gọi lại. Khả dĩ vì Task 8 bước 1 từng `delete_doc(force=True)` hàng
   loạt bản ghi; site hiện tại sạch (không cha treo), đây là phòng ngừa cho
   site khác/về sau, không phải sự cố đã xảy ra.
2. **`rebuild_tree()` ném lỗi vì lý do khác** (dữ liệu hỏng dạng khác, khoá
   DB, …). Hàm này treo ở `after_migrate` — lỗi văng ra khỏi đây làm VỠ
   `bench migrate` của MỌI site có `erpnext`, kể cả site không hề bật quản
   lý vị trí kho. Diện lộ tăng hẳn so với bản chỉ-patch (một lần lúc patch
   chạy) sang "mọi lần migrate, vĩnh viễn, mọi site".

Cách xử lý cả hai, theo đúng tinh thần đã chọn ở phán quyết F5+F11 (không để
một việc dọn dẹp làm vỡ migrate của người khác):
- Trước khi rebuild: TÌM cha treo, LOG NÊU ĐÍCH DANH (không im lặng) — người
  vận hành biết chính xác bản ghi nào sẽ không bao giờ tự dựng được cho tới
  khi họ sửa `parent_storage_location` hoặc xoá bản ghi mồ côi đó. Vẫn tiếp
  tục rebuild cho phần LÀNH — một bản ghi hỏng không được kéo cả lượt xuống.
- `rebuild_tree()` bọc trong `try/except`: bắt mọi lỗi, log rõ ràng, KHÔNG
  raise lại — `after_migrate` của site đó vẫn đi tiếp bình thường.
- Sau khi rebuild (dù thành công hay bắt được lỗi): ĐẾM LẠI bản ghi còn
  `lft = rgt = 0`. Còn thì log rõ còn bao nhiêu — không để hàm coi như
  "xong" trong khi cây chưa hội tụ thật.
"""

import frappe
from frappe.utils.nestedset import rebuild_tree

_LENH_REBUILD_TAY = (
	"bench execute frappe.utils.nestedset.rebuild_tree "
	"--kwargs \"{'doctype': 'Storage Location', 'parent_field': 'parent_storage_location'}\""
)


def _tim_cha_treo() -> list[dict]:
	"""Bản ghi có `parent_storage_location` trỏ tới một `name` không tồn tại.

	`rebuild_node` (frappe/utils/nestedset.py) đệ quy từ gốc xuống con qua
	đúng một truy vấn `where parent_field == <tên cha ĐANG DUYỆT>` — một bản
	ghi trỏ tới cha không tồn tại không bao giờ được truy vấn đó chạm tới,
	dù chạy `rebuild_tree` bao nhiêu lần.
	"""
	return frappe.db.sql(
		"""
		select sl.name, sl.parent_storage_location as cha
		from `tabStorage Location` sl
		where ifnull(sl.parent_storage_location, '') != ''
		  and not exists (
		      select 1 from `tabStorage Location` p where p.name = sl.parent_storage_location
		  )
		""",
		as_dict=True,
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

	VÒNG SỬA 3/5: "tự hội tụ" ở trên KHÔNG phải lời hứa vô điều kiện — chỉ
	đúng khi dữ liệu lành. Cha treo (`_tim_cha_treo`) không bao giờ hội tụ dù
	gọi lại bao nhiêu lần; `rebuild_tree()` tự nó có thể ném lỗi vì lý do
	khác. Cả hai đều được LOG RÕ, KHÔNG im lặng và KHÔNG làm vỡ `after_migrate`
	của site gọi hàm này — xem ba khối bên dưới.
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

	cha_treo = _tim_cha_treo()
	if cha_treo:
		danh_sach = ", ".join(f"{d.name} -> {d.cha}" for d in cha_treo)
		canh_bao_cha_treo = (
			f"[vi_tri_kho] {len(cha_treo)} bản ghi Storage Location có `parent_storage_"
			f"location` trỏ tới một bản ghi KHÔNG TỒN TẠI: {danh_sach}. Các bản ghi này sẽ "
			"KHÔNG BAO GIỜ được rebuild_tree() dựng toạ độ — dù gọi lại bao nhiêu lần migrate "
			"— vì rebuild_node() chỉ đệ quy từ gốc xuống con thật, không chạm tới bản ghi mồ "
			"côi kiểu này. Việc cần làm: sửa lại parent_storage_location cho đúng một bản ghi "
			"đang tồn tại, hoặc xoá hẳn bản ghi mồ côi nếu nó là rác. Các bản ghi LÀNH khác "
			"vẫn được dựng cây bình thường ở bước tiếp theo."
		)
		print(canh_bao_cha_treo)
		frappe.log_error(title="vi_tri_kho: dam_bao_cay_da_dung cha treo", message=canh_bao_cha_treo)

	try:
		rebuild_tree("Storage Location", "parent_storage_location")
	except Exception:
		# KHÔNG raise lại: hàm này treo ở after_migrate, chạy trên MỌI site
		# có erpnext. Làm vỡ bench migrate của một site không liên quan gì
		# tới module vị trí kho là hậu quả nặng hơn hẳn việc cây chưa được
		# dựng — hook này sẽ tự thử lại ở lần migrate sau.
		frappe.log_error(title="vi_tri_kho: dam_bao_cay_da_dung rebuild_tree loi")
		print(
			"[vi_tri_kho] rebuild_tree('Storage Location', ...) ném lỗi — xem Error Log "
			"'vi_tri_kho: dam_bao_cay_da_dung rebuild_tree loi'. Không chặn bench migrate; "
			"hàm sẽ tự thử lại ở lần migrate sau."
		)
		return

	con_thieu = frappe.db.count("Storage Location", {"lft": 0, "rgt": 0})
	if con_thieu:
		canh_bao_con_thieu = (
			f"[vi_tri_kho] Sau khi rebuild_tree(), vẫn còn {con_thieu} bản ghi Storage "
			"Location mang lft = rgt = 0 — cây CHƯA hội tụ hoàn toàn. Nguyên nhân thường "
			"gặp nhất: bản ghi có parent_storage_location trỏ tới một bản ghi không tồn "
			"tại (xem cảnh báo 'cha treo' phía trên nếu có). Kiểm bằng: frappe.db.count("
			'"Storage Location", {"lft": 0, "rgt": 0}).'
		)
		print(canh_bao_con_thieu)
		frappe.log_error(title="vi_tri_kho: dam_bao_cay_da_dung chua hoi tu het", message=canh_bao_con_thieu)

"""Truy vấn dùng chung về gán vị trí — "nút này ai đang giữ".

Tách khỏi controller vì BA nơi cần hỏi cùng một câu: `validate()` của
`Item Location Preference`, cây chọn vị trí, và báo cáo `hang_nam_sai_vi_tri`.
Để trong controller thì hai nơi kia phải dựng một `Document` chỉ để gọi một
hàm thuần truy vấn — và cái giá thật không phải hiệu năng mà là bản sao: hai
định nghĩa "giao nhau" trôi khỏi nhau thì một nửa hệ chặn, nửa kia cho qua.
"""

import frappe
from frappe import _
from frappe.utils import sbool

from erpnext.vi_tri_kho.vitri.fefo import to_tien_tat


def chu_cua_nhanh(lft: int, rgt: int, tru_ten: str | None = None) -> dict | None:
	"""Gán đang GIAO với khoảng `[lft, rgt]`, hoặc None.

	Điều kiện là hai nhánh GIAO NHAU, không phải bằng nhau. Một vị từ bắt cả
	ba ca, và đó chính là lý do không được viết `s.name = ...`:

	    trùng đúng nút   A giữ 1B0104,   B gán 1B0104      → chặn
	    gán vào con cháu A giữ 1B0104,   B gán 1B010402    → chặn
	    gán vào tổ tiên  A giữ 1B010402, B gán 1B01        → chặn
	    nút anh em       A giữ 1B010401, B gán 1B010402    → CHO QUA

	`tru_ten` loại chính bản ghi đang lưu ra khỏi phép so — thiếu nó thì mọi
	lần lưu lại một gán đã tồn tại đều tự báo "đụng chính mình".

	Gọi hàm này với `lft`/`rgt` bằng 0 là LỖI của nơi gọi: `0 <= rgt and
	0 >= lft` đúng với mọi bản ghi, nên nó sẽ trả về một gán tuỳ ý. Nơi gọi
	phải chặn trước (xem `ItemLocationPreference.kiem_tra_trong_cay`).
	"""
	if not lft or not rgt:
		frappe.throw("chu_cua_nhanh() nhận toạ độ rỗng — nơi gọi phải chặn trước.")

	dong = frappe.db.sql(
		"""
		select p.vat_tu as vat_tu, p.vi_tri as vi_tri, s.lft as lft, s.rgt as rgt
		from `tabItem Location Preference` p
		join `tabStorage Location` s on s.name = p.vi_tri
		where p.name != %(tru)s
		  and s.lft <= %(rgt)s
		  and s.rgt >= %(lft)s
		order by s.lft asc
		limit 1
		""",
		{"tru": tru_ten or "", "lft": lft, "rgt": rgt},
		as_dict=True,
	)
	return dong[0] if dong else None


# Mệnh đề dùng chung giữa `ton_khac_trong_nhanh()` (lấy MẪU, có `limit`) và
# `dem_ton_khac_trong_nhanh()` (lấy TỔNG THẬT, không `limit`). Hai truy vấn
# trả lời cùng một câu ("ô nào trong nhánh đang có hàng của mặt hàng khác")
# ở hai độ chi tiết khác nhau — chép tay hai bản `where` là đúng kiểu bản sao
# trôi khỏi nhau mà module này đã trả giá (xem docstring đầu file).
_DIEU_KIEN_TON_KHAC = """sl.lft between %(lft)s and %(rgt)s
	  and lb.so_luong != 0
	  and lb.vat_tu != %(vat_tu)s"""


def ton_khac_trong_nhanh(lft: int, rgt: int, vat_tu: str, gioi_han: int = 3) -> list[dict]:
	"""Tồn của mặt hàng KHÁC `vat_tu` đang nằm trong nhánh `[lft, rgt]` — MẪU,
	tối đa `gioi_han + 1` dòng.

	`so_luong != 0` chứ không phải "có dòng": một ô từng có hàng rồi hết vẫn
	còn dòng `Location Balance` mang 0. Coi dòng-0 là "đang có hàng" thì mọi ô
	từng dùng qua sẽ vĩnh viễn không gán được cho ai.

	`gioi_han` chỉ để dựng danh sách MẪU trong thông báo (nêu vài ô đầu rồi
	"… và N ô nữa"), nên hàm trả thêm một dòng so với `gioi_han` để nơi gọi
	biết là còn nữa.

	VÒNG SỬA 1 (review điều phối): kết quả hàm này KHÔNG đủ để tính N. Nó bị
	`limit` chặn ở `gioi_han + 1`, nên `len(...)` trên đó luôn ra đúng
	`gioi_han + 1` bất kể nhánh có 4 ô hay 400 ô — "N" tính từ số đó luôn
	bằng 1. Muốn N thật, gọi `dem_ton_khac_trong_nhanh()` — một truy vấn
	COUNT riêng, không `limit`, dùng chung `_DIEU_KIEN_TON_KHAC` để không
	trôi khỏi định nghĩa "khác" ở đây.
	"""
	if not lft or not rgt:
		frappe.throw("ton_khac_trong_nhanh() nhận toạ độ rỗng — nơi gọi phải chặn trước.")

	return frappe.db.sql(
		f"""
		select lb.o as o, lb.vat_tu as vat_tu, lb.so_luong as so_luong
		from `tabLocation Balance` lb
		join `tabStorage Location` sl on sl.name = lb.o
		where {_DIEU_KIEN_TON_KHAC}
		order by sl.lft asc
		limit %(gioi_han)s
		""",
		{"lft": lft, "rgt": rgt, "vat_tu": vat_tu, "gioi_han": gioi_han + 1},
		as_dict=True,
	)


def dem_ton_khac_trong_nhanh(lft: int, rgt: int, vat_tu: str) -> int:
	"""Tổng THẬT số ô có tồn mặt hàng khác trong nhánh `[lft, rgt]` — không
	`limit`, nên không bị cắt như kết quả của `ton_khac_trong_nhanh()`.

	Chỉ gọi trên ĐƯỜNG LỖI của `kiem_tra_ton_mat_hang_khac()` (tức chỉ khi
	`ton_khac_trong_nhanh()` đã trả về ít nhất một dòng): đây là truy vấn
	THỨ HAI, dùng để tính đúng "N" trong "… và N ô nữa" mà lấy MẪU không cho
	biết. Đường thành công (nhánh không chồng, phần lớn các lần gán) không
	chạm tới hàm này nên không tốn thêm một round-trip DB nào ở đường nóng.
	"""
	if not lft or not rgt:
		frappe.throw("dem_ton_khac_trong_nhanh() nhận toạ độ rỗng — nơi gọi phải chặn trước.")

	dong = frappe.db.sql(
		f"""
		select count(*) as tong
		from `tabLocation Balance` lb
		join `tabStorage Location` sl on sl.name = lb.o
		where {_DIEU_KIEN_TON_KHAC}
		""",
		{"lft": lft, "rgt": rgt, "vat_tu": vat_tu},
		as_dict=True,
	)
	return dong[0].tong if dong else 0


def doi_ten_theo_mat_hang(doc, method=None, old=None, new=None, merge=False):
	"""Đổi mã mặt hàng thì đổi luôn `name` của bản ghi gán.

	`Document.hook` gọi handler với `(doc, method, *args)` mà `rename_doc` đã
	truyền `(old, new, merge)` — nên chữ ký phải nhận đủ, xem
	`frappe/model/document.py:1357` và `rename_doc.py:207`.

	VÌ SAO KHÔNG ĐƠN GIẢN LÀ `db.set_value("...", ten, "vat_tu", new)`: bản ghi
	gán dùng `autoname: field:vat_tu`, nên `name` MỚI là nguồn sự thật.
	`_sync_autoname_field()` (base_document.py:1027) chạy ở mọi lần lưu và ép
	`vat_tu = name`. Sửa trường mà không sửa `name` thì lần lưu kế tiếp trả
	ngược về mã cũ — im lặng, không lỗi nào.

	`merge=True` (gộp hai mặt hàng) KHÔNG được xoá vô điều kiện — mã đích là
	mặt hàng còn sống sau khi gộp, nên nếu nó CHƯA có gán riêng thì rename như
	nhánh thường là an toàn tuyệt đối, và xoá ở ca đó là vứt mất vị trí cố
	định của một mặt hàng vẫn còn tồn tại mà không ai báo. Gộp là thao tác
	hiếm, nên khoản mất đó có thể nằm im rất lâu trước khi ai phát hiện — đúng
	lớp lỗi im lặng mà cả module này đang phòng, không phải ngoại lệ được
	quyền bỏ qua.

	Chỉ khi mã đích ĐÃ có gán riêng thì mới xoá bản ghi của mã cũ: rename vào
	một `name` đã tồn tại sẽ khiến `rename_doc` ném `DuplicateEntryError` giữa
	chừng một thao tác gộp đang dở. Giữ gán của mã ĐÍCH chứ không phải mã cũ
	vì đích mới là mặt hàng còn tồn tại sau khi gộp — gán của mã cũ trỏ vào
	một mặt hàng sắp biến mất, giữ nó lại không có ý nghĩa gì.

	GHI CHÚ (Task 4, vòng sửa 2, Ruling M): trường `vat_tu` từng mang thêm một
	UNIQUE INDEX ở cấp DB, tách biệt với khoá chính `name` — chỉ mục đó THỪA,
	vì `autoname: field:vat_tu` khiến `name` CHÍNH LÀ `vat_tu`, nên PRIMARY
	KEY đã tự giữ đủ bất biến "một mặt hàng một gán" rồi. Chỉ mục thừa đó
	không thêm bảo đảm nào — nó chỉ CHẶN bước chung `update_link_field_values()`
	của `rename_doc()` đặt tạm hai dòng cùng `vat_tu` giữa chừng một thao tác
	gộp, khiến ca "mã đích ĐÃ có gán" sập ở tầng MySQL trước khi hàm này kịp
	chạy. Đã bỏ `"unique": 1` khỏi `item_location_preference.json` — ĐỪNG
	thêm lại "cho chặt", nó không siết thêm gì mà chỉ chặn đúng nhánh code
	dưới đây. Cả hai ca merge (đích chưa có gán / đích đã có gán) đã có test
	thật trong `test_gan_vi_tri.py::TestDoiMaMatHang`.
	"""
	if not old or not new or old == new:
		return
	if not frappe.db.exists("Item Location Preference", old):
		return

	if merge and frappe.db.exists("Item Location Preference", new):
		frappe.delete_doc("Item Location Preference", old, ignore_permissions=True, force=True)
		return

	frappe.rename_doc("Item Location Preference", old, new, force=True, show_alert=False)


# Cùng bộ vai trò với `tem.py::VAI_TRO_DUOC_IN_TEM` và `xep.py::VAI_TRO_DUOC_XEP`: thủ kho
# (`Stock User`) phải tự xem được cây để chọn vị trí — đây là việc hằng ngày, không phải thao
# tác thiết lập chỉ dành cho quản lý.
VAI_TRO_DUOC_XEM_CAY = {"System Manager", "Stock Manager", "Stock User"}


@frappe.whitelist()
def cay_chon_vi_tri(
	kho: str, parent: str | None = None, is_root=None, tru_ten: str | None = None
) -> list[dict]:
	"""Các nút con để vẽ một cấp của cây chọn vị trí (Task 7 — bảng dữ liệu cho `frappe.ui.Tree`
	phía JS, xem `public/js/vi_tri_kho/cay_chon_vi_tri.js`).

	`@frappe.whitelist()` một mình chỉ chặn khách vãng lai; danh mục ô lộ ra toàn bộ cách bố trí
	kho nên đăng nhập hợp lệ không phải điều kiện đủ. Cùng bộ vai trò với `tem.py` và `xep.py`.

	`da_gan_cho` tra theo TỔ TIÊN-hoặc-chính-nó (`s2.lft <= sl.lft and s2.rgt >= sl.rgt`), không
	phải khớp đúng nút (`s2.name = sl.name`). Gán ở Tầng thì mọi Ô bên dưới nó cũng đã có chủ —
	không tra theo tổ tiên thì cây hiện Tầng là "đã có chủ" mà các Ô bên dưới vẫn trông trống,
	người dùng bấm vào rồi mới ăn lỗi từ `validate()` của `ItemLocationPreference` — với 214 ô
	đó là trò chơi đoán, không phải giao diện. `order by s2.lft asc limit 1` chọn tổ tiên GẦN
	NHẤT khi lồng nhiều lớp (không thể xảy ra thật vì `kiem_tra_chong_lan()` đã chặn hai gán
	chồng nhánh, nhưng `limit 1` giữ subquery luôn ra đúng MỘT giá trị cho `as_dict`).

	`co_gan_ben_trong` (VÒNG SỬA CUỐI, Mục 1 review tổng): `da_gan_cho` CHỈ tra chiều tổ tiên,
	nên chiều NGƯỢC LẠI — gán nằm ở một NÚT CON của `sl` — rơi vào khe hở. Ví dụ đo được: gán
	một mặt hàng vào Tầng `1A010102`, rồi mở cây tới Khoang cha `1A0101` (bao trùm Tầng đó).
	`s2.lft <= sl.lft` sai (Tầng có `lft` lớn hơn Khoang cha) nên `da_gan_cho` ra NULL — Khoang
	hiện như còn trống, `cay_chon_vi_tri.js::condition()` vẫn dựng nút "Chọn vị trí này", người
	dùng bấm vào rồi mới ăn đúng lỗi "bao trùm ... đã được gán cho" từ `kiem_tra_chong_lan()`.
	Đây là đúng cái spec §6 cấm bằng chữ in đậm, và đúng ca dùng CHÍNH (gán ở cấp Tầng/Khoang —
	spec §3.1), không phải một góc hiếm.

	KHÔNG gộp cột này vào `da_gan_cho`: Khoang đó CHƯA thuộc về ai (nó không phải nút được gán,
	chỉ là TỔ TIÊN của một nút đã gán) — nhãn "đã gán: X" ở đây sẽ nói SAI. Đếm bằng vị từ
	CON-CHÁU-NGHIÊM-NGẶT (`s5.lft > sl.lft and s5.rgt < sl.rgt`, loại trừ CHÍNH `sl` bằng bất
	đẳng thức chặt — một nút không bao giờ là con cháu nghiêm ngặt của chính nó, nên không cần
	`!=` tên tường minh): cùng gia đình vị từ với `kiem_tra_chong_lan()` (giao nhau đủ ba chiều
	dùng trong nested set lành: bằng, tổ tiên, con cháu), chỉ giữ đúng một chiều còn thiếu.
	`cay_chon_vi_tri.js` phải LOẠI nút có cột này > 0 khỏi nút "Chọn vị trí này", dù `da_gan_cho`
	của nó là NULL — nếu không, bấm vào rồi mới ăn lỗi vẫn y nguyên như trước khi vá.

	`nhanh_ngung_dung` (VÒNG VÁ TIẾP THEO — mối lo #1 nêu ở report review tổng trước): ba lý do
	`ItemLocationPreference.kiem_tra_nut_hop_le()` từ chối gán là `da_gan_cho`, `co_gan_ben_trong`
	ở trên, và nút `disabled` HOẶC có tổ tiên `disabled` — cây từng chỉ báo trước HAI trong ba.
	Một Dãy đang tắt để sửa kệ hiện ra như bình thường (`da_gan_cho`/`co_gan_ben_trong` đều falsy
	nếu chưa ai gán ở đó), nút "Chọn vị trí này" vẫn dựng ra, bấm vào mới ăn đúng lỗi "đang ngừng
	dùng (do chính nó hoặc do X ở trên nó)" — đúng cái spec §6 cấm bằng chữ in đậm, cùng LOÀI lỗi
	với `da_gan_cho`/`co_gan_ben_trong` ở trên, chỉ khác lý do.

	Dùng ĐÚNG `to_tien_tat("sl")` (từ `fefo.py`, đã import ở đầu file) — KHÔNG viết lại vị từ:
	đây là chính luật mà `so_o_trong` bên dưới (`to_tien_tat("s4")`) và `item_location_preference.py`
	đang dùng; ba nơi trôi khỏi nhau (như đã từng xảy ra, xem `fefo.py::_dieu_kien_ngung_dung()`)
	thì một nửa hệ chặn còn nửa kia cho qua, và không gì báo. `nhanh_ngung_dung` xét TOẠ ĐỘ của
	CHÍNH `sl` (không phải tổ tiên GẦN NHẤT như `ten_nut_ngung_dung()` — cây chỉ cần biết CÓ chặn
	hay không để ẩn nút, không cần nêu tên tổ tiên nào, nên trả boolean là đủ và rẻ hơn).

	`cay_chon_vi_tri.js::toolbar.chon.condition()` phải loại nốt có cột này khỏi nút "Chọn vị trí
	này", và `get_label()` phải hiện nhãn RIÊNG cho ca này ("đang ngừng dùng") — không gộp chung
	với "đã gán"/"có gán bên trong": ba lý do là ba việc khác nhau của người vận hành (đi tìm chỗ
	khác / gỡ gán con trước / bật lại nhánh), gộp thành một chữ "không chọn được" sẽ không nói cho
	người dùng biết phải LÀM GÌ tiếp theo.

	`tru_ten` (bắt được ở vòng soát lại sau khi vá `co_gan_ben_trong`, TRƯỚC khi bàn giao — không
	phải một mục review riêng, mà là hệ quả trực tiếp của cột trên nếu bỏ sót): nút "Chọn trên cây
	vị trí" ở `item_location_preference.js` gắn vào `refresh`, tức hiện ra CẢ KHI đang SỬA một
	bản ghi đã lưu — người dùng đang giữ gán ở Tầng `self.tang`, mở cây định DỜI LÊN Khoang cha
	của chính nó (một thao tác HỢP LỆ: `kiem_tra_chong_lan()` phía `validate()` loại trừ đúng bản
	ghi đang sửa qua `tru_ten=self.name`, xem `item_location_preference.py`). Không loại trừ tương
	tự ở đây thì `co_gan_ben_trong` của Khoang đó đếm luôn CHÍNH gán đang sửa, báo "có gán bên
	trong" và khoá nút chọn — một thao tác hợp lệ trở nên không làm được qua giao diện, dù qua API
	vẫn lưu được bình thường: đúng kiểu UI và validate() nói ngược nhau mà toàn bộ Mục 1 sinh ra để
	dẹp, chỉ là chiều ngược. Áp `p2.name != %(tru_ten)s` cho `co_gan_ben_trong` VÀ `p.name !=
	%(tru_ten)s` cho `da_gan_cho` (đối xứng — nếu không, mở cây ngay tại ĐÚNG nút mình đang giữ sẽ
	hiện "đã gán: chính-mình", một nhãn đúng nhưng gây khó chịu khi người dùng chỉ định xem lại).
	`tru_ten or ""` (cùng khuôn với `chu_cua_nhanh()`) giữ vị từ vô hại khi không có gì cần loại —
	`p.name != ""` luôn đúng.

	`ZZZ-CHUA-XEP` (ô ảo "chưa xếp vị trí") bị loại — nó không phải kệ thật, và
	`ItemLocationPreference.kiem_tra_nut_hop_le()` chặn gán vào đó ngay từ Python; cho nó lên cây
	chỉ để người dùng bấm rồi ăn lỗi.

	Bản ghi `lft = 0` (chưa hội tụ trong cây — xem `ItemLocationPreference.kiem_tra_trong_cay()`
	ở `item_location_preference.py`) bị loại bằng `sl.lft > 0`. Cùng cái bẫy đã trả giá ở
	`fefo.py` và `tem.py`: một nút `lft = rgt = 0` lọt vào cây thì `da_gan_cho` của nó (và mọi
	nút 0/0 khác trên toàn hệ, kể cả kho khác) sẽ tự nhận nhầm gán của nhau qua vị từ giao nhau.

	VÌ SAO NHẬN `is_root` MÀ THÂN HÀM KHÔNG DÙNG TRỰC TIẾP GIÁ TRỊ ĐÓ ĐỂ TRUY VẤN (vòng sửa 2,
	điều phối tự bấm trên trình duyệt bắt được): `frappe.ui.Tree.get_nodes()`
	(`frappe/public/js/frappe/ui/tree.js:41-56`) LUÔN gửi cả `parent` lẫn `is_root` cho mọi lệnh
	gọi — kể cả ở CẤP GỐC. Widget không gọi hàm này với chữ ký "đẹp" mà ta tưởng tượng lúc viết
	(`cay_chon_vi_tri(kho)` không `parent`); nó gọi `cay_chon_vi_tri(kho=..., parent=root_value,
	is_root=True)`, và `root_value` (constructor dòng 22-24: `if (root_value == null) {
	this.root_value = label; }`) CHÍNH LÀ giá trị `label` mà `cay_chon_vi_tri.js` truyền vào —
	tức TÊN KHO, không phải tên một `Storage Location` nào. Bản trước Task 7 coi
	`if parent: ... else: (gốc)` là đủ — sai, vì ở gốc `parent` KHÔNG rỗng, nó mang tên kho, nên
	nhánh gốc (`parent_storage_location is null`) không bao giờ được chọn: hộp thoại mở ra,
	cây hiện đúng một nốt gốc rỗng, bấm vào không ra gì — chết ngay cửa vào duy nhất của cây.
	Không bài test Python nào ở vòng nộp trước bắt được vì chúng gọi hàm theo chữ ký Python nghĩ
	ra (`cay_chon_vi_tri(KHO)`, không `parent`), không theo cách widget THẬT SỰ gọi — hợp đồng
	thật của hàm `@frappe.whitelist()` là hợp đồng của WIDGET gọi nó, không phải chữ ký ta thấy
	gọn. Coi là cấp gốc khi BẤT KỲ điều nào đúng — ba điều vì ba nơi gọi khác nhau:
	  1. `is_root` là true — widget ở CẤP GỐC (case bắt lỗi ở đây).
	  2. `parent` rỗng — mã gọi trực tiếp/bài test kiểu cũ, hoặc widget gọi qua
	     `get_all_nodes()` (dùng `frappe.desk.treeview.get_all_nodes`, không thuộc phạm vi sửa ở
	     đây nhưng cùng lớp "không truyền parent" nên gộp chung điều kiện cho an toàn).
	  3. `parent == kho` — widget ở NHÁNH nhưng lỡ truyền `root_value` trùng tên kho (không xảy
	     ra ở luồng hiện tại vì nhánh luôn dùng `value` thật của `Storage Location`, nhưng đây là
	     đúng tình huống đã đo được ở gốc — giữ điều kiện này tường minh thay vì chỉ dựa vào
	     `is_root` để không phụ thuộc một mình vào việc widget luôn gửi cờ đó đúng).

	`is_root` tới đây dưới dạng CHUỗI `"true"`/`"false"` khi gọi qua HTTP (`frappe.call` gửi mọi
	tham số dạng chuỗi), KHÔNG phải Python bool — `if is_root:` trần sẽ đúng cho CẢ HAI vì
	`"false"` là một chuỗi khác rỗng. Phải qua `frappe.utils.sbool()` (chuyển `"true"/"1"` →
	`True`, `"false"/"0"` → `False`, giữ nguyên giá trị khác — kể cả khi gọi trực tiếp từ Python
	với `is_root=True`/`None`, `sbool()` bắt `AttributeError` của `.lower()` trên bool/None và trả
	nguyên giá trị đó) rồi mới ép `bool()`.
	"""
	if not VAI_TRO_DUOC_XEM_CAY & set(frappe.get_roles()):
		frappe.throw(_("Bạn không có quyền xem cây vị trí."), frappe.PermissionError)

	la_goc = bool(sbool(is_root)) if is_root is not None else False
	if la_goc or not parent or parent == kho:
		dieu_kien = "ifnull(sl.parent_storage_location, '') = ''"
	else:
		dieu_kien = "sl.parent_storage_location = %(parent)s"
	return frappe.db.sql(
		f"""
		select sl.name as value,
		       ifnull(sl.ma_in_nhan, sl.name) as title,
		       ifnull(sl.is_group, 0) as expandable,
		       (select p.vat_tu
		          from `tabItem Location Preference` p
		          join `tabStorage Location` s2 on s2.name = p.vi_tri
		         where p.name != %(tru_ten)s
		           and s2.lft <= sl.lft and s2.rgt >= sl.rgt
		         order by s2.lft asc limit 1) as da_gan_cho,
		       (select count(*)
		          from `tabItem Location Preference` p2
		          join `tabStorage Location` s5 on s5.name = p2.vi_tri
		         where p2.name != %(tru_ten)s
		           and s5.lft > sl.lft and s5.rgt < sl.rgt) as co_gan_ben_trong,
		       {to_tien_tat("sl")} as nhanh_ngung_dung,
		       (select count(distinct lb.vat_tu)
		          from `tabLocation Balance` lb
		          join `tabStorage Location` s3 on s3.name = lb.o
		         where s3.lft between sl.lft and sl.rgt and lb.so_luong != 0) as so_mat_hang_dang_co,
		       (select count(*)
		          from `tabStorage Location` s4
		         where s4.lft between sl.lft and sl.rgt
		           and ifnull(s4.is_group, 0) = 0
		           and ifnull(s4.la_o_chua_xep, 0) = 0
		           and not {to_tien_tat("s4")}
		           and ifnull((select sum(lb2.so_luong) from `tabLocation Balance` lb2
		                        where lb2.o = s4.name), 0) = 0) as so_o_trong
		from `tabStorage Location` sl
		where {dieu_kien}
		  and sl.kho = %(kho)s
		  and ifnull(sl.la_o_chua_xep, 0) = 0
		  and sl.lft > 0
		order by sl.lft asc
		""",
		{"kho": kho, "parent": parent, "tru_ten": tru_ten or ""},
		as_dict=True,
	)

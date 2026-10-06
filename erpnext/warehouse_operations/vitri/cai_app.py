"""Phát hành bản cài app PDA (.apk) qua chính hệ thống (chủ đầu tư 23/09/2026).

Trước file này, đưa app lên một máy quét mới là cầm cáp USB đi từng máy. Nay:
kỹ thuật dựng APK xong thì TẢI LÊN hệ thống một lần; mỗi máy PDA mở trình duyệt
vào một địa chỉ ngắn rồi bấm tải — không cáp, không máy tính.

FILE ĐỂ CÔNG KHAI — chủ đầu tư chốt 23/09/2026, và đây là đánh đổi có thật:
máy PDA lúc chưa cài app thì CHƯA có phiên đăng nhập nào, nên một file riêng tư
sẽ không tải được (Frappe đòi phiên có quyền đọc). Đổi lại, ai biết đường dẫn
đều tải được bản cài, và bản cài đó lộ ĐỊA CHỈ MÁY CHỦ NỘI BỘ của kho (nó nằm
trong `www/index.html` gói bên trong APK). Không có mật khẩu hay khoá nào trong
APK. Muốn kín thì phải bỏ luôn lối "một nút là xong" — xem `docs/warehouse_
operations/HDSD-app-pda.md`.

BẢN MỚI NHẤT SUY THEO `creation`, KHÔNG theo tên file: tên do người tải lên đặt,
mà thứ tự chữ cái không phải thứ tự thời gian (`v10` đứng trước `v9`). Một cái
tên đặt lệch không được phép biến bản cũ thành bản đang phát hành.
"""

import re

import frappe
from frappe import _
from frappe.utils import flt

#: Chỉ trưởng kho mới được đưa bản cài mới lên — cùng tập vai trò mà
#: `o_tem.VAI_TRO_DOI_O` dùng cho các việc "quyết định thay cả kho".
VAI_TRO_PHAT_HANH = {"System Manager", "Stock Manager"}
#: Lọc theo đuôi .apk VÀ tên có "pda": thư mục File của site chứa đủ thứ, mà
#: một file .apk lạ ai đó tải lên cho việc khác không được phép trở thành "bản
#: cài app PDA" chỉ vì nó mới hơn.
MAU_TEN = "%pda%.apk"

#: Khuôn TÊN FILE mang số hiệu bản cài. HỢP ĐỒNG BA NƠI, và đây là nơi DUY NHẤT có
#: người đang nhìn màn hình lúc sai:
#:
#:   `pda_app/android/app/build.gradle`  sinh tên (`outputFileName`)
#:   `scripts/pda/dong-goi.sh`           từ chối dựng nếu `versionName` lệch khuôn
#:   `vo.js::_ban_tu_ten_tep`            rút số hiệu ở phía MÁY QUÉT, và IM khi không rút được
#:
#: VÌ SAO ĐÚNG HAI ĐOẠN (soát tổng, T6-1): phía máy quét chỉ có TÊN FILE để so, mà
#: người phát hành ĐÃ chứng minh họ dán NGÀY vào tên file (bản đang phát hành trên
#: máy chủ thử tên `miyano-pda-1.0-kho-2026-09-24.apk`). Ba đoạn thì `24.09.26`
#: (dd.mm.yy) không phân biệt được với một số hiệu ba đoạn bằng hình dạng — và một
#: số hiệu đọc nhầm thành "24" sẽ bật dải nhắc VĨNH VIỄN trên mọi máy. Hai đoạn thì
#: mọi cách viết ngày đều rớt.
#:
#: Biểu thức này phải KHỚP TỪNG KÝ TỰ với biểu thức trong `vo.js::_ban_tu_ten_tep`
#: — `test_giao_dien.test_task6_hai_noi_rut_phien_ban_khop_nhau` chạy CẢ HAI trên
#: cùng một bảng tên và đòi kết quả giống hệt.
MAU_PHIEN_BAN = re.compile(r"miyano-pda-(\d{1,3}\.\d{1,3})(?=[-_]|\.apk|$)", re.I)

#: Câu chỉ đúng việc phải làm khi tên file không mang số hiệu đọc được.
CAU_TEN_SAI = (
	"Tên file bản cài phải mang số hiệu dạng <b>miyano-pda-X.Y-…apk</b> "
	"(ví dụ <b>miyano-pda-1.1-release.apk</b>) — đây là tên mà Gradle tự đặt, "
	"đừng sửa khi tải lên.<br><br>"
	"Tên đang dùng: <b>{0}</b><br><br>"
	"VÌ SAO BẮT BUỘC: app trong máy quét đọc số hiệu từ chính tên file này để biết "
	"mình có phải bản mới nhất không. Tên không đọc được số hiệu thì app <b>im lặng</b> "
	"— không máy nào được nhắc nâng cấp, và không ai biết là nó đã hỏng. "
	"Ngày tháng trong tên (2026-09-24, 24.09.26…) KHÔNG phải số hiệu."
)


def _phien_ban_tu_ten(ten: str) -> str:
	"""Số hiệu rút từ TÊN FILE, hoặc chuỗi rỗng khi không rút được.

	Cùng luật với `vo.js::_ban_tu_ten_tep` — xem `MAU_PHIEN_BAN`.
	"""
	khop = MAU_PHIEN_BAN.search(ten or "")
	return khop.group(1) if khop else ""


def chan_ten_ban_cai_sai(doc, method=None) -> None:
	"""`doc_events` của `File`: TỪ CHỐI một bản cài PDA đặt tên không mang số hiệu.

	LỚP 1 của "buộc hợp đồng ngầm lộ ra". Trước đây khuôn tên chỉ là một dòng chữ
	trong tài liệu, và hậu quả của việc phá nó (dải nhắc im lặng trên mọi máy) chỉ
	lộ ra hàng tuần sau, ở ngoài kho, dưới dạng "sao máy em không thấy bản mới".
	Chặn ở đây là chặn đúng lúc người phát hành đang nhìn màn hình và sửa được bằng
	một lần đổi tên.

	PHẠM VI HẸP CÓ CHỦ ĐÍCH: hook này chạy cho MỌI `File` của cả hệ thống, nên nó chỉ
	được phép nói khi thật sự là một bản cài PDA — tức tên khớp đúng tập mà
	`_ban_moi_nhat()` sẽ nhặt (`MAU_TEN`: có "pda" và đuôi `.apk`). Một file `.apk`
	khác, một ảnh, một PDF đều đi qua không một lời nào.

	KHÔNG chặn theo `is_private`: file riêng tư đã có câu nhắc riêng ở
	`cai_app_pda.js`, và chặn hai thứ trong một câu là câu không ai đọc hết.
	"""
	ten = (getattr(doc, "file_name", "") or "").strip()
	if not ten.lower().endswith(".apk") or "pda" not in ten.lower():
		return
	if _phien_ban_tu_ten(ten):
		return
	frappe.throw(_(CAU_TEN_SAI).format(frappe.utils.escape_html(ten)), title=_("Tên bản cài không hợp lệ"))


def _kiem_quyen_phat_hanh() -> None:
	if not VAI_TRO_PHAT_HANH & set(frappe.get_roles()):
		frappe.throw(_("Chỉ trưởng kho mới đưa bản cài app PDA lên."), frappe.PermissionError)


def _ban_moi_nhat() -> dict | None:
	"""Bản cài đang phát hành, hoặc `None` khi chưa ai tải bản nào lên.

	Hàm đọc THẲNG, không kiểm quyền: trang tải công khai (`/tai-app`) gọi nó khi
	người dùng chưa đăng nhập. Nó chỉ trả tên/ngày/dung lượng/đường dẫn của một
	file vốn đã công khai — không lộ thêm gì so với chính đường dẫn đó.
	"""
	ds = frappe.get_all(
		"File",
		filters={"file_name": ("like", MAU_TEN), "is_private": 0},
		fields=["name", "file_name", "file_url", "file_size", "creation"],
		order_by="creation desc",
		limit=1,
	)
	if not ds:
		return None
	f = ds[0]
	# LỚP 2 — MÁY CHỦ TỰ RÚT SỐ HIỆU và nói ra khi không rút được. App cố ý IM khi
	# không đọc được số hiệu (không nhắc bừa còn hơn nhắc sai), nhưng "im" nghĩa là
	# KHÔNG AI BIẾT NÓ HỎNG. Đây là chỗ sự im lặng đó có một cái tên: `ly_do` hiện
	# lên trang quản trị, và `log_error` để lại dấu vết cho người kiểm về sau.
	#
	# Lớp 1 (`chan_ten_ban_cai_sai`) chặn ở cửa vào, nên nhánh này chỉ còn chạy cho
	# các bản cài đã nằm sẵn trên máy chủ TỪ TRƯỚC khi có hàng rào đó — đúng ca của
	# site thật hôm nay.
	phien_ban = _phien_ban_tu_ten(f.file_name)
	ly_do = ""
	if not phien_ban:
		ly_do = _(
			"Tên file không mang số hiệu dạng miyano-pda-X.Y — máy quét sẽ KHÔNG "
			"nhắc nâng cấp cho bản này. Đổi tên file rồi tải lại."
		)
		frappe.log_error(
			title="cai_app: ban cai khong doc duoc so hieu",
			message=(
				f"File: {f.file_name}\n"
				f"Khuon can: {MAU_PHIEN_BAN.pattern}\n"
				"He qua: vo.js::_ban_tu_ten_tep tra chuoi rong, dai nhac ban moi "
				"KHONG hien tren bat ky may quet nao."
			),
		)
	return {
		"ma": f.name,
		"ten": f.file_name,
		"phien_ban": phien_ban,
		"ly_do": ly_do,
		"duong_dan": "/api/method/erpnext.warehouse_operations.vitri.cai_app.tai_ban_cai",
		"duong_dan_file_tinh": f.file_url,
		"dung_luong_mb": round(flt(f.file_size) / 1024 / 1024, 1),
		"tai_len_luc": str(f.creation),
	}


@frappe.whitelist(allow_guest=True)
def ban_cai_moi_nhat() -> dict | None:
	"""Cho trang `/tai-app` (công khai) và trang quản trị `cai-app-pda` dùng chung."""
	return _ban_moi_nhat()


@frappe.whitelist(allow_guest=True)
def tai_ban_cai():
	"""Trả thẳng nội dung bản cài — KHÔNG để máy quét tải qua đường `/files/...`.

	VÌ SAO KHÔNG DÙNG ĐƯỜNG FILE TĨNH (đo được trên bench này 23/09/2026): thư mục
	site `192.168.61.129` là LIÊN KẾT MỀM trỏ sang `erptest.local`. Bộ phục vụ file
	tĩnh của Frappe (`frappe/middlewares.py: StaticDataMiddleware`) `resolve()` đường
	dẫn — tức giải luôn liên kết mềm — rồi so với thư mục gốc CHƯA giải bằng
	`is_relative_to`; hai bên lệch nhau nên nó ném `NotFound`. Hệ quả: vào bằng tên
	miền thì tải được, vào bằng ĐỊA CHỈ IP thì lỗi 500 — mà máy quét trong kho chỉ có
	đường vào bằng IP.

	Đi qua đường này thì nội dung do chính ứng dụng đọc và trả, không phụ thuộc cách
	máy chủ phục vụ file tĩnh, nên chạy giống nhau cho mọi tên miền lẫn IP, cả ở máy
	chủ dev lẫn máy chủ thật.
	"""
	ban = _ban_moi_nhat()
	if not ban:
		frappe.throw(_("Chưa có bản cài nào trên hệ thống."), frappe.DoesNotExistError)

	tep = frappe.get_doc("File", ban["ma"])
	frappe.local.response.filename = ban["ten"]
	frappe.local.response.filecontent = tep.get_content()
	frappe.local.response.type = "download"


@frappe.whitelist()
def danh_sach_ban_cai(gioi_han: int = 10) -> list[dict]:
	"""Các bản cài đã tải lên, mới nhất trước — cho trang quản trị xem lịch sử."""
	_kiem_quyen_phat_hanh()
	return frappe.get_all(
		"File",
		filters={"file_name": ("like", MAU_TEN), "is_private": 0},
		fields=["file_name", "file_url", "file_size", "creation", "owner"],
		order_by="creation desc",
		limit=int(gioi_han),
	)

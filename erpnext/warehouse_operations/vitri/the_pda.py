"""Thẻ PDA: cấp, thu hồi, và đăng nhập bằng thẻ (spec 2026-09-23 §5).

MỘT TẤM THẺ QUÉT ĐƯỢC LÀ MỘT CHIẾC CHÌA KHOÁ. Ai chụp được thẻ và in lại là vào
được hệ thống với quyền của chủ thẻ. File này không làm nó hết là chìa khoá — nó
làm chiếc chìa khoá đó THU HỒI ĐƯỢC, CÓ DẤU VẾT, và KHÔNG MỞ ĐƯỢC GÌ NGOÀI KHO:

- máy chủ chỉ giữ SHA-256 của (muối + mã), không giữ mã gốc (lộ CSDL không dựng lại
  được thẻ) — MỖI THẺ MỘT MUỐI RIÊNG (`secrets.token_hex(16)`), nên lộ CSDL cũng
  không dò được HÀNG LOẠT thẻ cùng lúc bằng một bảng tra cứu chung (rainbow table);
- mã gốc trả về ĐÚNG MỘT LẦN, cho đúng màn hình in;
- cấp lại thẻ VÀ thu hồi thẻ đều đóng luôn phiên đang mở (mất thẻ thì phản xạ tự
  nhiên là bấm "Cấp thẻ & in" ngay, không phải bấm "Thu hồi" trước);
- chỉ tài khoản có vai trò kho mới quét được, kiểm cả lúc cấp lẫn lúc quét;
- quét sai bị chặn tần suất theo IP và có dòng Error Log.
"""

import hashlib
import hmac
import secrets
import time
from datetime import datetime, timedelta, timezone

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.sessions import clear_sessions
from frappe.utils import now_datetime
from frappe.utils.password import get_decrypted_password, remove_encrypted_password

#: Bảng chữ bỏ O/0/I/1/L — thủ kho gõ tay lúc tem mờ không nhầm được.
BANG_CHU = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
DO_DAI_MA = 12
#: Ai DÙNG được thẻ. Phải bằng hợp của `VAI_TRO_DUOC_XEP` (xep.py),
#: `VAI_TRO_DUOC_LAY` (lay_hang.py) và `VAI_TRO_DUOC_TRA_CUU` (quet.py) — ba tập đó
#: hiện giống hệt nhau; nếu một ngày chúng tách ra thì sửa ở đây cho khớp.
VAI_TRO_DUOC_DUNG_THE = {"System Manager", "Stock Manager", "Stock User"}
#: Ai CẤP/THU HỒI thẻ — cùng tập `o_tem.VAI_TRO_DOI_O` đang dùng cho quyền trưởng kho.
VAI_TRO_QUAN_LY_THE = {"System Manager", "Stock Manager"}
GIO_MOT_CA = 12
#: Header mà máy gửi kèm MỌI lời gọi để tự khai mình là chiếc máy nào (Android ID).
#: Tên header là HỢP ĐỒNG với vỏ app (Task 4) — đổi ở đây là mọi máy ngoài kho 401.
DAU_MA_MAY = "X-Ma-May"
#: Hai sơ đồ HTTP mà `validate_auth_via_api_keys` (`frappe/auth.py:674`) nhận cho
#: CÙNG một cặp `api_key:api_secret`: `token <key>:<secret>` và
#: `Basic <base64(key:secret)>`. Gác thiếu một cái là để ngỏ nguyên cánh cửa — ai
#: cầm khoá rò ra ngoài chỉ cần mã hoá lại thành `Basic` là ràng buộc mã máy biến
#: mất (ĐÃ ĐO trên máy chủ thật trước khi vá: `Basic` không kèm mã máy trả 200).
#: CỐ Ý KHÔNG có `bearer`: đó là đường OAuth (`validate_oauth`), một loại chứng chỉ
#: khác hẳn, không phải khoá máy PDA.
SO_DO_KHOA_API = ("token ", "basic ")
#: Câu báo khi khoá máy không dùng được trên chiếc máy đang gọi. Cố ý KHÔNG nói rõ
#: "sai mã máy" hay "máy đã thu hồi": kẻ cầm khoá trộm không cần biết mình thiếu gì.
CAU_KHOA_MAY_HONG = "Máy chưa được cấp quyền — báo trưởng kho cấp khoá cho máy này."
#: Ghi `lan_dung_cuoi` thưa ra: hook chạy ở MỌI request mang khoá, ghi mỗi lần là
#: thêm một lượt ghi CSDL cho mỗi lần quét mã vạch. 5 phút đủ để trưởng kho biết máy
#: nào còn sống mà không biến bảng dấu vết thành nhật ký truy cập.
PHUT_GIUA_HAI_LAN_GHI_DAU_VET = 5
#: Trần chặn tần suất cho ba điểm cuối `allow_guest` của file này, TÍNH THEO IP.
#:
#: ĐO ĐƯỢC, KHÔNG PHẢI SUY (soát tổng V9, đo 25/09 trên `http://192.168.61.129:8003`):
#: `LoginManager.set_request_ip` (`frappe/auth.py:64-75`) lấy **mục ĐẦU TIÊN của header
#: `X-Forwarded-For`** trước mọi nguồn khác, và `rate_limit` khoá bộ đếm theo đúng giá trị
#: đó. Phép đo: 12 lượt `gio_may_chu` cùng `X-Forwarded-For: 203.0.113.7` →
#: `200 x10, 429, 429`; ngay sau đó một lượt với `203.0.113.8` → **200**.
#:
#: HỆ QUẢ VẬN HÀNH: qua ngrok, ngrok đặt `X-Forwarded-For` bằng IP CÔNG CỘNG của client —
#: mà cả kho ra internet qua **một IP NAT**. Nghĩa là MỌI chiếc PDA trong kho dùng CHUNG
#: một bộ đếm. Với trần cũ (10/60), 10 máy mở app đầu ca là chạm trần và máy thứ 11 ăn
#: 429 — một sự cố vận hành trông y như lỗi phần mềm.
#:
#: QUYẾT ĐỊNH: nâng trần lên cỡ MỘT CA KHO thay vì cỡ một người, nhưng giữ nó HỮU HẠN.
#: Không đổi sang khoá theo mã máy: `rate_limit(key=...)` đọc `frappe.form_dict`, mà mã máy
#: đi trong HEADER — và một kẻ tấn công tự đặt header thì tự chọn được bộ đếm của mình,
#: tức hàng rào tự tan. Chặn theo IP vẫn là hàng rào duy nhất đứng vững ở đây.
#: 30 lần/phút vẫn chặn được đúng thứ trần này sinh ra để chặn: mã thẻ là 12 ký tự trên
#: bảng 32 chữ (~1,15e18 tổ hợp), dò ở 30 lần/phút là chuyện của hàng chục triệu tỉ năm.
SO_LAN_MOI_PHUT_CHO_KHACH = 30
#: `gio_may_chu` chỉ trả ngày giờ của site — không bí mật, không tác dụng phụ, và MỌI máy
#: gọi nó lúc khởi động. Nới rộng hơn hẳn hai hàm kia vì nó không có gì để dò.
SO_LAN_MOI_PHUT_GIO_MAY_CHU = 60


def chuan_ma_may(ma_may: str | None) -> str:
	"""Chuẩn hoá mã máy ở ĐÚNG MỘT CHỖ — cùng lý do như `bam()` chuẩn hoá mã thẻ.

	Chỉ cắt khoảng trắng, KHÔNG đổi hoa/thường: Android ID là chuỗi hex chữ thường,
	tự viết hoa nó lên là đổi thứ đang so sánh. Một nơi chuẩn hoá khác nơi kia nghĩa
	là máy cấp khoá được nhưng lời gọi tiếp theo bị từ chối — hỏng kiểu đó im lặng và
	chỉ lộ ra ngoài kho.
	"""
	return (ma_may or "").strip()


def bam(muoi: str, ma: str) -> str:
	"""SHA-256 của (muối + mã thẻ), sau khi chuẩn hoá hoa/thường và khoảng trắng của mã.

	Chuẩn hoá mã ở ĐÚNG MỘT CHỖ này: súng quét có thể gửi kèm khoảng trắng, còn người
	gõ tay hay gõ chữ thường. Hai nơi chuẩn hoá khác nhau là thẻ quét được ở màn
	này mà không quét được ở màn kia.

	`muoi` KHÔNG được chuẩn hoá — nó là chuỗi hex do `secrets.token_hex` sinh ra
	(quyết định 2026-09-23, đợt sửa cuối), không phải thứ người dùng gõ tay, nên
	không có nhầm hoa/thường hay khoảng trắng cần lo.
	"""
	ma_chuan = (ma or "").strip().upper()
	return hashlib.sha256(((muoi or "") + ma_chuan).encode("utf-8")).hexdigest()


def bam_bi_mat(muoi: str, bi_mat: str) -> str:
	"""SHA-256 của (muối + `api_secret`) — DẤU VÂN TAY của chiếc khoá, không phải khoá.

	VÌ SAO CẦN: dấu xuất xứ theo `api_key` KHÔNG phân biệt được ca "nhận máy trước, xoay
	khoá ở Desk sau" — `generate_keys` giữ nguyên `api_key` qua **mọi** lần xoay và chỉ
	đổi `api_secret` (`user.py:1332`). Thứ duy nhất đổi theo mỗi lần xoay là BÍ MẬT, nên
	phải bám vào nó. Bám bằng một hàm băm có muối để **không lưu bí mật**.

	VÌ SAO KHÔNG SO `__Auth.modified` (cách người soát đề nghị): bảng `__Auth` của bản
	Frappe này **không có cột `modified`** — đo được: `SHOW COLUMNS FROM __Auth` trả đúng
	`doctype, name, fieldname, password, encrypted`. Không có mốc thời gian nào để so.

	VÌ SAO KHÔNG SO `User.modified`: bất kỳ lần sửa User nào cũng đẩy nó lên, nên phép so
	sẽ trả "không phải khoá của PDA" cho gần như mọi trường hợp — thu hồi thôi không xoá
	khoá nữa, tức quay lại đúng ca "nút trang trí".

	Băm KHÔNG chuẩn hoá hoa/thường hay khoảng trắng (khác `bam()` của mã thẻ): `api_secret`
	là chuỗi máy sinh, so nguyên văn; chuẩn hoá ở đây chỉ làm hai bí mật khác nhau đụng
	nhau. Muối riêng từng dòng, đúng lý do đã ghi cho `PDA Badge.muoi`.
	"""
	return hashlib.sha256(((muoi or "") + (bi_mat or "")).encode("utf-8")).hexdigest()


def _kiem_quyen_quan_ly() -> None:
	if not VAI_TRO_QUAN_LY_THE & set(frappe.get_roles()):
		frappe.throw(_("Chỉ trưởng kho mới cấp hoặc thu hồi thẻ PDA."), frappe.PermissionError)


@frappe.whitelist()
def cap_the(nguoi_dung: str) -> dict:
	"""Cấp thẻ mới cho `nguoi_dung` (cấp lại thì thẻ cũ chết ngay VÀ phiên cũ bị đóng).

	Trả mã gốc ĐÚNG MỘT LẦN cho màn hình in. Không có đường nào đọc lại mã đó:
	mất thẻ thì cấp thẻ khác, không "xem lại mã cũ".
	"""
	_kiem_quyen_quan_ly()
	ma = "".join(secrets.choice(BANG_CHU) for _ in range(DO_DAI_MA))
	muoi = secrets.token_hex(16)
	if frappe.db.exists("PDA Badge", nguoi_dung):
		the = frappe.get_doc("PDA Badge", nguoi_dung)
	else:
		the = frappe.new_doc("PDA Badge")
		the.nguoi_dung = nguoi_dung
	the.muoi = muoi
	the.ma_bam = bam(muoi, ma)
	the.con_hieu_luc = 1
	the.cap_luc = now_datetime()
	the.lan_dung_cuoi = None
	the.thiet_bi_cuoi = None
	the.save()
	# Cấp lại thẻ giết mã băm cũ, nhưng KHÔNG tự đóng phiên đang mở bằng mã cũ đó —
	# một chiếc PDA đang cầm thẻ cũ trên tay vẫn làm việc bình thường tới hết 12
	# tiếng nếu thiếu dòng này. Mà phản xạ tự nhiên khi MẤT THẺ là bấm "Cấp thẻ & in"
	# NGAY, không phải bấm "Thu hồi" trước — nên chỗ đóng phiên thật sự cần nằm ở
	# đây, không chỉ ở `thu_hoi`. `keep_current=True` để không tự đá phiên WEB đang
	# thao tác của chính người gọi hàm này, trong ca trưởng kho tự cấp thẻ cho chính
	# mình (`nguoi_dung` trùng người đang đăng nhập trên web) — không cần `force`:
	# khi cấp cho NGƯỜI KHÁC (ca thường gặp), `frappe.session.user` (trưởng kho) khác
	# `nguoi_dung`, nên giới hạn "chừa lại N phiên đồng thời" của `clear_sessions`
	# không áp dụng (`get_sessions_to_clear` chỉ tính offset khi
	# `user == frappe.session.user`, xem `frappe/sessions.py`) — toàn bộ phiên PDA
	# cũ của `nguoi_dung` vẫn bị đóng sạch.
	clear_sessions(user=nguoi_dung, keep_current=True)
	return {"the": the.name, "ho_ten": the.ho_ten, "ma": ma, "cap_luc": str(the.cap_luc)}


@frappe.whitelist()
def thu_hoi(nguoi_dung: str) -> dict:
	"""Thu hồi thẻ: quét không vào được nữa, VÀ phiên đang mở bị đóng.

	Thiếu vế thứ hai thì một chiếc PDA đang cầm trên tay kẻ nhặt được thẻ vẫn
	làm việc bình thường tới hết ca — thu hồi mà không đuổi phiên là thu hồi nửa vời.
	`force=True` trong clear_sessions bắt buộc để đóng ngay cả phiên của chính mình —
	không nó sẽ chỉ dọn phiên quá hạn. Khi thu hồi cho người khác, không cần `force`
	phiên vẫn bị dọn, nhưng giữ `force=True` ở đây vô hại và đảm bảo.

	TASK 3 THÊM VẾ THỨ BA: GIẾT KHOÁ MÁY. Từ khi máy giữ danh tính bằng
	`Authorization: token <api_key>:<api_secret>` (spec §6), đóng phiên KHÔNG còn đủ —
	khoá API không phải phiên, `clear_sessions` không đụng tới nó, nên một chiếc PDA
	mất tích vẫn gọi được mọi hàm whitelist dưới tên chủ thẻ. Mà hệ thống ĐANG MỞ RA
	INTERNET QUA NGROK: kẻ nhặt được máy dùng nó từ bất cứ đâu, không cần vào tận kho.
	Nút "Thu hồi thẻ" mà không giết khoá là một nút trang trí.
	"""
	_kiem_quyen_quan_ly()
	if not frappe.db.exists("PDA Badge", nguoi_dung):
		frappe.throw(_("{0} chưa từng được cấp thẻ PDA — không có gì để thu hồi.").format(nguoi_dung))
	the = frappe.get_doc("PDA Badge", nguoi_dung)
	the.con_hieu_luc = 0
	the.save()
	clear_sessions(user=nguoi_dung, force=True)
	# Hỏi xuất xứ TRƯỚC khi hạ cờ máy: `_khoa_co_phai_do_pda_cap` tra theo dòng máy, và
	# nó cố ý KHÔNG lọc `con_hieu_luc` nên thứ tự không đổi kết quả — nhưng giữ đúng thứ
	# tự này để người sửa sau không phải đi kiểm lại điều đó.
	kq_khoa = _thu_hoi_khoa_neu_cua_pda(nguoi_dung)
	so_may = 0
	loc_may = {"nguoi_dung": nguoi_dung, "con_hieu_luc": 1}
	for may in frappe.get_all("PDA Thiet Bi", filters=loc_may, pluck="name"):
		# `save()` chứ KHÔNG `db.set_value` (soát tổng, V4): `db.set_value` đi vòng qua
		# tầng Document nên KHÔNG sinh dòng `tabVersion` — trưởng kho hỏi "chiếc máy này
		# chết lúc nào, ai bấm" thì chỉ thấy `modified` nhảy, không có lịch sử. Đây là
		# đường trưởng kho dùng NHIỀU NHẤT, và nó từng là đường duy nhất còn sai:
		# `thu_hoi_may` đã dùng `save()`, và `_ghi_thiet_bi` cũng vậy.
		doc = frappe.get_doc("PDA Thiet Bi", may)
		doc.con_hieu_luc = 0
		doc.save(ignore_permissions=True)
		so_may += 1
	return {"the": the.name, "con_hieu_luc": 0, "so_may_da_thu_hoi": so_may, **kq_khoa}


CAU_BAO_CHUNG = "Thẻ không dùng được — báo trưởng kho."


def _tim_the_dung_duoc(ma: str) -> frappe._dict:
	"""Tìm thẻ khớp `ma` và kiểm chủ thẻ còn dùng được; hỏng thì ném ĐÚNG MỘT CÂU.

	Tách ra khỏi `dang_nhap_bang_the` ở Task 3 vì `cap_khoa_may` phải kiểm thẻ
	**y hệt**. Chép đoạn này sang hàm kia là dựng lại đúng cái bẫy mà docstring đầu
	file cảnh báo ("hai nơi chuẩn hoá khác nhau là thẻ quét được ở màn này mà không
	quét được ở màn kia") — chỉ khác là lần này cái lệch nằm ở phép KIỂM, nên nó sẽ
	lộ ra dưới dạng "thẻ đã thu hồi vẫn đổi được khoá máy vĩnh viễn".
	"""
	# KHÔNG tra theo `ma_bam` bằng một câu WHERE được nữa: từ khi mỗi thẻ có một
	# MUỐI RIÊNG (đợt sửa cuối, mục 8), không thể suy `ma_bam` từ `ma` gõ vào rồi
	# tra thẳng — phải biết `muoi` của TỪNG thẻ trước mới băm để so được. Số thẻ
	# đang lưu hành cỡ vài chục (một kho không có hàng trăm thủ kho), nên DUYỆT
	# HẾT rồi so từng cái là đủ nhanh, không cần thêm chỉ mục nào. Chỉ duyệt thẻ
	# `con_hieu_luc = 1`: thẻ đã thu hồi không cần so khớp nữa — quét bằng thẻ đã
	# thu hồi sẽ rơi vào nhánh "khong co the nao khop" ở dưới (không còn phân biệt
	# được với "mã sai chưa từng tồn tại" qua Error Log nữa, nhưng NGƯỜI DÙNG vẫn
	# nhận đúng một câu báo chung như cũ — không đổi hành vi bên ngoài).
	# `hmac.compare_digest` thay vì `==`: so hai chuỗi bằng `==` dừng sớm ngay ký tự
	# đầu tiên lệch, lộ ra "gần đúng cỡ nào" qua thời gian xử lý (timing attack) —
	# compare_digest so đủ toàn bộ độ dài bất kể lệch ở đâu.
	the = None
	for ung_vien in frappe.get_all(
		"PDA Badge", filters={"con_hieu_luc": 1}, fields=["name", "nguoi_dung", "ma_bam", "muoi"]
	):
		# Phòng hờ thẻ CŨ từ trước đợt sửa muối (không có `muoi`, `ma_bam` là băm trần
		# `sha256(ma)`) còn sót lại trên một site nào đó: KHÔNG so những thẻ này — coi như
		# không khớp, ép chủ thẻ phải được cấp lại thẻ mới đã có muối. Không làm vậy thì
		# `bam(None, ma)` rơi về đúng công thức băm trần cũ, lặng lẽ giữ nguyên lỗ hổng mà
		# mục 8 đang vá cho những thẻ đó. Trên `erptest.local` lúc sửa (23/09/2026) bảng
		# `PDA Badge` đang rỗng nên nhánh này chưa từng chạy thật — vẫn giữ lại vì đúng ngay
		# cả khi có thẻ cũ, và chi phí thêm gần như bằng không.
		if not ung_vien.muoi:
			continue
		if hmac.compare_digest(bam(ung_vien.muoi, ma), ung_vien.ma_bam):
			the = ung_vien
			break

	ly_do = None
	if not the:
		ly_do = "khong co the nao khop"
	elif not frappe.db.get_value("User", the.nguoi_dung, "enabled"):
		ly_do = f"tai khoan {the.nguoi_dung} bi khoa"
	elif not (VAI_TRO_DUOC_DUNG_THE & set(frappe.get_roles(the.nguoi_dung))):
		ly_do = f"{the.nguoi_dung} khong con vai tro kho"

	if ly_do:
		frappe.log_error(
			title="vi_tri_kho: the_pda sai ma",
			message=f"{ly_do}; ip={frappe.local.request_ip}",
		)
		frappe.throw(_(CAU_BAO_CHUNG), frappe.AuthenticationError)

	return the


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=SO_LAN_MOI_PHUT_CHO_KHACH, seconds=60)
def dang_nhap_bang_the(ma: str) -> dict:
	"""Quét thẻ để vào phiên PDA. Gọi từ trang `/pda` (cùng nguồn với máy chủ).

	MỘT CÂU BÁO CHO MỌI CA HỎNG (không thấy thẻ / thẻ thu hồi / tài khoản khoá /
	mất vai trò kho): phân biệt ra là nói cho người đang dò biết mã nào có thật.
	Chi tiết thật nằm ở Error Log — DocType gốc của Frappe chỉ cho `System Manager` đọc
	(không có `Stock Manager`/trưởng kho), nên đây là chỗ chỉ quản trị hệ thống xem được,
	không phải trưởng kho. Không cấp thêm quyền đọc Error Log ở đây — đó là một thay đổi an
	ninh nằm ngoài phạm vi việc đăng nhập bằng thẻ.

	Brief gốc viết `@frappe.rate_limit(...)`, nhưng bản Frappe này KHÔNG lộ `rate_limit`
	ở cấp module `frappe` (chỉ có `frappe.rate_limiter.rate_limit`) — import thẳng và
	gọi `@rate_limit(...)`, giữ nguyên hành vi mặc định `ip_based=True` → 10 lần/phút
	cho mỗi IP.

	`methods=["POST"]` thêm ở Task 3: trước đó hàm này nhận cả `GET`, tức
	`/api/method/…dang_nhap_bang_the?ma=SGRL79WAQF3W` chạy được — và mã thẻ nằm lại
	trong nhật ký truy cập của máy chủ lẫn của ngrok. Trang `/kho` và vỏ app đều đã
	gọi bằng `POST` nên đây KHÔNG đổi hành vi của đường nào đang chạy.
	"""
	the = _tim_the_dung_duoc(ma)

	het_ca = (datetime.now(timezone.utc) + timedelta(hours=GIO_MOT_CA)).isoformat()
	# Cùng đường mà `frappe/www/login.py::login_via_key` dùng cho đăng nhập bằng
	# liên kết email — cookie phiên được đặt vào phản hồi của chính lời gọi này.
	frappe.local.login_manager.login_as(the.nguoi_dung, session_end=het_ca)

	frappe.db.set_value(
		"PDA Badge",
		the.name,
		{
			"lan_dung_cuoi": now_datetime(),
			"thiet_bi_cuoi": (frappe.get_request_header("User-Agent") or "")[:140],
		},
		update_modified=False,
	)
	return {"di_toi": "/app/pda-home"}


# ---------------------------------------------------------------------------
# KHOÁ MÁY (spec 2026-09-24 §6, §7) — quét thẻ MỘT LẦN lúc nhận máy, rồi máy giữ
# danh tính cho tới khi trưởng kho thu hồi.
# ---------------------------------------------------------------------------


def xoa_khoa_api(nguoi_dung: str) -> None:
	"""Giết khoá máy của `nguoi_dung` ở CẢ HAI CHỖ Frappe cất nó.

	`validate_api_key_secret` (`frappe/auth.py:700`) tra `User` theo `api_key` rồi
	so `api_secret` giải mã từ bảng `__Auth`. Xoá một chỗ là đủ để lời gọi hỏng, xoá
	cả hai là để không còn mảnh bí mật nào nằm lại trên đĩa sau khi thu hồi.

	VÔ ĐIỀU KIỆN — đúng như tên gọi. Người gọi phải tự quyết chiếc khoá này có phải
	của PDA không; `thu_hoi`/`thu_hoi_may` hỏi `_khoa_co_phai_do_pda_cap` trước.
	"""
	if frappe.db.get_value("User", nguoi_dung, "api_key"):
		frappe.db.set_value("User", nguoi_dung, "api_key", None, update_modified=False)
	remove_encrypted_password("User", nguoi_dung, "api_secret")


def _may_khop_bi_mat_dang_song(nguoi_dung: str, loc_them: dict | None = None) -> list:
	"""Những dòng `PDA Thiet Bi` của `nguoi_dung` khớp CHIẾC KHOÁ ĐANG SỐNG của họ.

	Khớp = cùng `api_key` (định danh) VÀ vân tay của `api_secret` hiện tại trùng cái ghi
	lúc cấp. Vì mỗi thời điểm một người chỉ có ĐÚNG MỘT bí mật sống, nhiều nhất một dòng
	khớp được vân tay dù họ có bao nhiêu dòng máy cũ.

	`loc_them` là chỗ hai người gọi tách nhau ra — xem `_bi_mat_hien_do_pda_sinh` và
	`_khoa_co_phai_do_pda_cap`.
	"""
	khoa_hien = frappe.db.get_value("User", nguoi_dung, "api_key")
	if not khoa_hien:
		return []
	loc = {"nguoi_dung": nguoi_dung, "api_key_da_cap": khoa_hien}
	loc.update(loc_them or {})
	ung_vien = frappe.get_all("PDA Thiet Bi", filters=loc, fields=["name", "muoi_khoa", "bi_mat_bam"])
	if not ung_vien:
		return []
	bi_mat = get_decrypted_password("User", nguoi_dung, "api_secret", raise_exception=False)
	if not bi_mat:
		return []
	# Thiếu vân tay (máy cấp từ trước vòng sửa 2) thì KHÔNG khớp — fail-closed ở cả hai
	# người gọi: không xoá một chiếc khoá không chứng minh được là của mình, và không
	# cho đè lên một chiếc khoá không chứng minh được là của mình.
	return [
		m
		for m in ung_vien
		if m.bi_mat_bam
		and m.muoi_khoa
		and hmac.compare_digest(bam_bi_mat(m.muoi_khoa, bi_mat), m.bi_mat_bam)
	]


def dong_cua_khi_het_may(nguoi_dung: str) -> bool:
	"""Người này không còn dòng `PDA Thiet Bi` nào → GIẾT khoá API của họ. Trả True nếu đã giết.

	LỖ HỔNG NÀY LÀ MỘT THAO TÁC BÌNH THƯỜNG, KHÔNG PHẢI MỘT MẸO TẤN CÔNG (soát tổng, N1).
	`kiem_khoa_may` cố ý thoát sớm khi người dùng không có dòng máy nào — đó là cái gác
	giữ cho khoá API của người NGOÀI diện PDA (tích hợp, script) không bị vạ lây, và nó có
	bài canh riêng. Nhưng `Stock Manager` có `delete:1` **và** `write:1` trên chính
	`PDA Thiet Bi`, nên trưởng kho chỉ cần **dọn danh sách máy cũ** hoặc **gán lại một
	chiếc máy cho người khác** là chủ cũ còn 0 dòng → hook thoát sớm → **ràng buộc mã máy
	bốc hơi, và một khoá ĐÃ THU HỒI xác thực lại được mà không cần `X-Ma-May`**. Đã đo.

	VÁ Ở CỬA VÀO, KHÔNG NỚI HOOK: hook giữ việc khác và đã đúng. Chỗ sai là hai đường ghi
	trên doctype không kéo theo hậu quả nào.

	VÌ SAO Ở ĐÂY GIẾT KHOÁ VÔ ĐIỀU KIỆN, KHÁC HẲN `thu_hoi` (vòng sửa 1 cố ý KHÔNG giết
	khoá "vốn có từ trước"): hai ca khác nhau ở chỗ **hook còn cưỡng chế được hay không**.
	`thu_hoi` chỉ hạ cờ, dòng máy VẪN CÒN, nên `kiem_khoa_may` vẫn từ chối mọi lời gọi của
	chiếc khoá đó — tha một chiếc khoá lạ khi ấy là an toàn, và tránh giết tích hợp của
	người khác. Ở đây dòng máy **biến mất**, hook không còn chỗ bám, nên lập luận "hai lớp"
	sụp: tha khoá = để lại một chứng chỉ chứng minh được là đi lọt ràng buộc. Giữa "giết
	nhầm một khoá tích hợp" và "để sống một khoá đã thu hồi mở ra internet qua ngrok",
	chọn cái thứ nhất — và nói ra lựa chọn đó chứ không giấu.

	Cố ý KHÔNG chặn thao tác (không `frappe.throw`): chặn thì `_ghi_thiet_bi` cũng bị chặn
	khi một chiếc máy được trao tay sang thủ kho khác — đúng ca ở quầy nhận máy.
	"""
	if not nguoi_dung:
		return False
	if frappe.db.count("PDA Thiet Bi", {"nguoi_dung": nguoi_dung}):
		return False
	if not frappe.db.get_value("User", nguoi_dung, "api_key"):
		return False
	xoa_khoa_api(nguoi_dung)
	frappe.log_error(
		title="vi_tri_kho: het may PDA nen giet khoa",
		message=(
			f"{nguoi_dung} khong con dong PDA Thiet Bi nao (bi xoa hoac doi chu) nen "
			"kiem_khoa_may se thoat som; da xoa api_key/api_secret de khoa khong di lot "
			"rang buoc ma may."
		),
	)
	return True


def _bi_mat_hien_do_pda_sinh(nguoi_dung: str) -> bool:
	"""BÍ MẬT đang sống có phải do `cap_khoa_may` sinh ra không? — câu hỏi của phép CHẶN.

	HAI CÂU HỎI KHÁC NHAU, VÀ TRỘN CHÚNG LÀ MỘT LỖI CÓ THẬT (vòng sửa 3, N1). Phép CHẶN
	ở `cap_khoa_may` hỏi *"cấp máy bây giờ có giẫm lên việc của ai không"*; phép XOÁ ở
	`thu_hoi` hỏi *"tôi có được phép xoá chiếc khoá này không"*. Chúng khác nhau ở đúng
	vế `khoa_von_co_truoc`:

	- Vế đó PHẢI ở lại phép XOÁ: `xoa_khoa_api` xoá cả `api_key` — tức cả ĐỊNH DANH mà
	  PDA không tạo ra, chỉ mượn lại của một chiếc khoá có sẵn.
	- Vế đó KHÔNG được có ở phép CHẶN: một tài khoản đã đi lối thoát ĐÚNG MỘT LẦN sẽ có
	  máy mang `khoa_von_co_truoc = 1` mãi mãi. Dùng chung hàm thì **mọi lần đổi máy về
	  sau đều bị chặn, đòi tick cờ lại** — trong khi bí mật đang sống lúc đó ĐÃ do PDA
	  sinh ra và đè lên nó chẳng giẫm chân ai. Mô tả ô cờ nói "tự tắt sau lần cấp kế
	  tiếp"; với tài khoản ấy sự thật hoá ra là "mỗi lần", và lối thoát duy nhất là xoá
	  tay `api_key` ở Desk.
	"""
	return bool(_may_khop_bi_mat_dang_song(nguoi_dung))


def _khoa_co_phai_do_pda_cap(nguoi_dung: str) -> bool:
	"""Chiếc khoá API mà `nguoi_dung` đang cầm có phải do `cap_khoa_may` sinh ra không?

	VÌ SAO PHẢI HỎI: thu hồi một chiếc PDA mà xoá khoá VÔ ĐIỀU KIỆN thì có thể giết
	một khoá tích hợp của người khác, im lặng, và không ai được báo. Nên trước khi xoá
	phải biết chiếc khoá đó từ đâu ra.

	BA VẾ, và mỗi vế đóng một ca mà hai vế kia để lọt:

	1. `User.api_key` hiện tại phải TRÙNG một `api_key_da_cap` đã ghi trên máy của
	   người đó — tức đúng chiếc khoá `cap_khoa_may` đã trao đi.
	2. Chiếc máy ấy phải nói `khoa_von_co_truoc = 0`. Lý do: `generate_keys`
	   **giữ nguyên `api_key` cũ nếu đã có** (`if not user_details.api_key:` — chỉ
	   `api_secret` bị ghi đè). Nghĩa là khi một người đã có khoá tích hợp rồi mới nhận
	   máy PDA, vế 1 TỰ ĐỘNG đúng dù chiếc khoá đó không do PDA sinh ra. Thiếu vế 2 thì
	   phép kiểm này chỉ là một câu trả lời "có" cho mọi trường hợp.
	3. **Và dấu vân tay của BÍ MẬT hiện tại phải khớp cái đã ghi lúc cấp.** Vế này
	   đóng ca NGƯỢC CHIỀU THỜI GIAN mà vòng soát thứ hai tìm ra: *nhận máy trước, xoay
	   khoá ở Desk sau*. Khi ấy vế 1 và 2 vẫn đúng (định danh bất biến, cờ vẫn 0) trong
	   khi chiếc khoá đang sống là một chiếc **PDA chưa bao giờ cấp** — thu hồi sẽ xoá
	   sạch nó. Định danh không phân biệt được điều đó vì nó không đổi; **bí mật thì
	   đổi mỗi lần xoay**, nên phép kiểm phải bám vào bí mật (bám bằng băm có muối —
	   xem `bam_bi_mat`, không lưu bí mật ở đâu).

	Thiếu dấu vân tay (máy cấp từ trước vòng sửa 2) thì trả **False**: fail-closed —
	không dám xoá một chiếc khoá mình không chứng minh được là của mình. Máy vẫn chết
	vì `kiem_khoa_may` từ chối mọi máy hết hiệu lực.

	NÓI THẲNG: từ vòng sửa 2, ca "khoá có TRƯỚC" chỉ còn xảy ra khi trưởng kho **cố ý**
	bật cờ `cho_de_khoa_api` trên thẻ — `cap_khoa_may` CHẶN ca đó theo mặc định.
	"""
	return bool(_may_khop_bi_mat_dang_song(nguoi_dung, {"khoa_von_co_truoc": 0}))


def _thu_hoi_khoa_neu_cua_pda(nguoi_dung: str) -> dict:
	"""Xoá khoá nếu nó là của PDA; không thì giữ lại và NÓI RÕ vì sao."""
	if _khoa_co_phai_do_pda_cap(nguoi_dung):
		xoa_khoa_api(nguoi_dung)
		return {"khoa_da_xoa": 1, "ly_do_giu_khoa": ""}
	if not frappe.db.get_value("User", nguoi_dung, "api_key"):
		return {"khoa_da_xoa": 0, "ly_do_giu_khoa": ""}
	return {
		"khoa_da_xoa": 0,
		"ly_do_giu_khoa": _(
			"Khoá API hiện tại của {0} KHÔNG do PDA cấp nên không bị xoá — máy vẫn chết, "
			"nhưng chiếc khoá đó có thể đang chạy một tích hợp khác. Muốn xoá thì vào User "
			"và xoá tay."
		).format(nguoi_dung),
	}


def _ghi_thiet_bi(
	nguoi_dung: str, ten_may: str, ma_may: str, khoa: dict, von_co_truoc: bool
) -> str:
	"""Ghi dấu vết "ai đang cầm máy nào" và giết mọi máy CŨ của cùng người.

	VÌ SAO PHẢI GIẾT MÁY CŨ: `generate_keys` ghi đè `api_secret` của `User` — MỘT
	NGƯỜI CHỈ CÓ MỘT BÍ MẬT. Nên ngay khi người này nhận máy thứ hai, máy thứ nhất đã
	chết ở tầng Frappe dù không ai bấm gì. Không hạ cờ máy cũ xuống thì bảng này nói
	dối đúng cái điều nó sinh ra để trả lời, và trưởng kho đi tìm một chiếc máy mà hệ
	thống bảo là đang chạy.

	Khoá theo `ma_may` (cũng là tên bản ghi) chứ không tạo mù: cùng một chiếc máy được
	người khác quét thẻ lên thì đổi chủ, không sinh bản ghi thứ hai — `ma_may` là
	`unique`, tạo mù sẽ ném lỗi trùng ngay giữa lúc thủ kho nhận máy.

	ĐỔI CHỦ PHẢI GIẾT KHOÁ CỦA CHỦ CŨ (vòng sửa 1 của Task 4, lỗi S1) — và đây là một
	lỗ hổng THẬT, dựng lại được trên site thật:

	    A nhận máy   → khoá A + KHÔNG mã máy → 401        (hàng rào đang làm việc)
	    B quét thẻ trên CÙNG chiếc máy đó → dòng máy đổi chủ sang B (đúng ý trên)
	                 → số dòng `PDA Thiet Bi` của A = 0, mà KHOÁ A VẪN SỐNG
	                 → khoá A + KHÔNG mã máy → 200   ← ràng buộc thiết bị BỐC HƠI
	                 → khoá A + mã máy BỪA   → 200

	Nguyên nhân KHÔNG phải ở `kiem_khoa_may`: hook đó thoát sớm khi người gọi không có
	dòng máy nào (`if not may_cua_nguoi: return`), và phép thoát ấy **phải ở lại** — nó
	đang giữ một việc khác hẳn: không chặn khoá API của người chưa bao giờ dùng PDA
	(tích hợp, script). Sửa ở đó là đánh đổi một lỗ hổng bằng một lỗ hổng.

	Chỗ đúng là ở đây: khi chiếc máy đổi chủ, chủ cũ không còn chiếc máy nào, nên khoá
	của họ không còn cánh cửa nào để mở — giết nó. Dùng đúng `_thu_hoi_khoa_neu_cua_pda`
	mà `thu_hoi`/`thu_hoi_may` đã dùng, nên ngoại lệ "khoá KHÔNG do PDA cấp thì giữ lại"
	được tôn trọng y nguyên, không phải viết lại luật lần thứ ba.

	**PHẢI GỌI TRƯỚC `may.save()` — ràng buộc là LƯỢT GHI, không phải dòng lệnh gán.**
	`_khoa_co_phai_do_pda_cap(chủ_cũ)` đi qua `_may_khop_bi_mat_dang_song`, hàm này truy
	vấn **CSDL** theo `nguoi_dung = chủ_cũ` để lấy dấu vân tay; dòng đang giữ vân tay của
	chủ cũ CHÍNH LÀ dòng ta sắp ghi đè. Sau `save()` thì chủ cũ còn 0 dòng → phép kiểm
	trả `False` (fail-closed) → khoá chủ cũ **không** bị xoá, tức bản vá im lặng không
	làm gì. Đo được: dịch lời gọi xuống sau `may.save()` → bài
	`test_may_DOI_CHU_thi_khoa_chu_cu_phai_chet` ĐỎ. Dịch xuống sau dòng gán
	`may.nguoi_dung = ...` mà vẫn trước `save()` thì **KHÔNG** đỏ — phép gán chỉ đổi đối
	tượng trong bộ nhớ, truy vấn vẫn đọc CSDL. Đặt trước cả hai vì đó là chỗ đọc dễ hiểu
	nhất, không phải vì dòng gán có ý nghĩa gì.

	`chu_cu == nguoi_dung` thì không làm gì, và vế đó là HÀNG RÀO DUY NHẤT chặn một lời
	gọi HỢP LỆ tự giết chiếc khoá đang dùng — canh bởi
	`test_ghi_thiet_bi_goi_THANG_khong_tu_giet_khoa_dang_song`.

	Nó **không** cắn khi đi qua `cap_khoa_may`: ở đó `generate_keys` luôn xoay bí mật
	TRƯỚC khi hàm này chạy, nên vân tay trong dòng máy chắc chắn là vân tay của bí mật
	CŨ, phép kiểm không khớp và fail-closed tự cứu. Nó cắn khi ai đó gọi THẲNG hàm này
	với chiếc khoá ĐANG SỐNG — đúng hình dạng của một hàm "đổi tên máy" / "gán lại máy"
	mà Task sau sẽ viết: không cấp khoá mới nghĩa là không xoay bí mật, nên vân tay KHỚP,
	`_khoa_co_phai_do_pda_cap` trả `True`, và bỏ vế `!=` là xoá đúng chiếc khoá người
	dùng đang cầm. Đo được: bỏ vế đó → `api_key` về `None` và khoá hết xác thực được.

	(Vòng sửa 1 tôi khai vế này "không bài nào làm nó cắn được" và dừng lại ở đó. Câu
	đúng là "chưa ai dựng được bài" — người soát dựng được ngay ở vòng sau. Ghi lại vì
	khoảng cách giữa hai câu đó chính là chỗ một hàng rào thật bị gỡ đi vì tưởng nó
	thừa.)
	"""
	if frappe.db.exists("PDA Thiet Bi", ma_may):
		may = frappe.get_doc("PDA Thiet Bi", ma_may)
	else:
		may = frappe.new_doc("PDA Thiet Bi")
		may.ma_may = ma_may
	chu_cu = may.get("nguoi_dung")
	if chu_cu and chu_cu != nguoi_dung:
		_thu_hoi_khoa_neu_cua_pda(chu_cu)
	may.nguoi_dung = nguoi_dung
	may.ten_may = ((ten_may or "").strip() or ma_may)[:140]
	may.con_hieu_luc = 1
	# XUẤT XỨ KHOÁ — xem `_khoa_co_phai_do_pda_cap`. Ghi ĐỊNH DANH (`api_key`) và DẤU
	# VÂN TAY của bí mật (băm có muối), KHÔNG bao giờ ghi chính `api_secret`: định danh
	# một mình không đăng nhập được (`validate_api_key_secret` vẫn đòi bí mật giải mã từ
	# `__Auth`), và dấu vân tay thì không quay ngược ra bí mật được.
	may.api_key_da_cap = khoa["api_key"]
	may.muoi_khoa = secrets.token_hex(16)
	may.bi_mat_bam = bam_bi_mat(may.muoi_khoa, khoa["api_secret"])
	may.khoa_von_co_truoc = 1 if von_co_truoc else 0
	may.cap_luc = now_datetime()
	may.lan_dung_cuoi = None
	# `ignore_permissions=True` và nói rõ vì sao: hàm này chạy dưới danh tính KHÁCH
	# (thủ kho chưa đăng nhập, chỉ mới chìa tấm thẻ ra). Cố ý KHÔNG đặt lời ghi này
	# vào trong cửa sổ nâng quyền Administrator ở `cap_khoa_may`: nâng quyền càng hẹp
	# càng tốt, và để trong đó thì bài test chạy dưới Guest không còn bắt được ca
	# thiếu quyền ghi nữa — nó bị che bởi chính cái nâng quyền.
	may.save(ignore_permissions=True)

	# HẠ CỜ MÁY CŨ BẰNG `save()`, KHÔNG BẰNG `db.set_value` (vòng sửa 2).
	#
	# `pda_thiet_bi.json` khai `track_changes = 1`, nghĩa là doctype này TỰ NHẬN việc
	# giữ lịch sử thay đổi; `db.set_value` đi thẳng xuống SQL, bỏ qua tầng Document,
	# nên nó **không sinh dòng `tabVersion`** — một đường ghi lặng lẽ phá đúng cái ý
	# định mà schema đã khai. Hệ quả đọc được: dòng đổi chủ (`may.save()` ở trên) có
	# lịch sử `nguoi_dung: A → B` trên timeline trong Desk, còn những chiếc máy CHẾT
	# THEO trong cùng lời gọi thì không có gì — người đi tìm "máy này chết lúc nào, vì
	# sao" chỉ thấy `modified` nhảy mà không biết vì sao nhảy.
	#
	# ĐÃ ĐO TRƯỚC KHI ĐỔI, vì đây là ĐƯỜNG NÓNG (thủ kho đang đứng nhận máy, và
	# `generate_keys` đã xoay bí mật xong ở trên — một ngoại lệ ở đây là người đó kẹt
	# giữa chừng): phép kiểm DUY NHẤT trong `PDAThietBi.validate` có thể ném cho một
	# bản ghi đã tồn tại là phép kiểm vai trò kho, và nó nằm sau `if self.con_hieu_luc`
	# — tức **được bỏ qua đúng ở chiều HẠ CỜ**. Hai phép kiểm `ma_may` không ném được
	# cho bản ghi đã lưu (chính `validate` này đã chặn từ lượt lưu đầu). Vòng lặp thực
	# tế chạy 0–1 dòng (một người chỉ có một máy sống).
	#
	# `ignore_permissions=True` vì hàm chạy dưới danh tính KHÁCH — cùng lý do đã viết ở
	# lời `save()` phía trên.
	for khac in frappe.get_all(
		"PDA Thiet Bi",
		filters={"nguoi_dung": nguoi_dung, "con_hieu_luc": 1, "name": ["!=", may.name]},
		pluck="name",
	):
		may_cu = frappe.get_doc("PDA Thiet Bi", khac)
		may_cu.con_hieu_luc = 0
		may_cu.save(ignore_permissions=True)
	return may.name


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=SO_LAN_MOI_PHUT_CHO_KHACH, seconds=60)
def cap_khoa_may(ma: str, ten_may: str, ma_may: str) -> dict:
	"""Quét thẻ MỘT LẦN lúc nhận máy, đổi lấy khoá API dùng lâu dài.

	VÌ SAO DÙNG KHOÁ API CỦA FRAPPE chứ không tự chế: `frappe/auth.py:674
	validate_auth_via_api_keys` đã là đường Frappe thiết kế sẵn cho client ngoài, và
	`frappe/core/doctype/user/user.py:1332 generate_keys` sinh khoá. Tự chế một cơ chế
	phiên thứ hai là tự nhận lấy một bề mặt tấn công mà không ai soát.

	ĐÁNH ĐỔI ĐÃ CHỐT (spec §7): khoá KHÔNG hết hạn. Mất máy là mất danh tính cho tới
	khi có người thu hồi — mà hệ thống đang mở ra internet qua ngrok, nên "thu hồi"
	phải giết được KHOÁ THẬT, không chỉ xoá phiên. Xem `thu_hoi` và `thu_hoi_may`.

	`methods=["POST"]`, KHÔNG phải một chú thích dặn dò: `GET`/`HEAD`/`OPTIONS` không
	đi qua cầu HTTP native của Capacitor — `native-bridge.js` đẩy chúng sang một URL
	proxy nội bộ `https://localhost/_capacitor_http_interceptor_?u=…` (đo ở Task 2B
	§3.3), một đường chưa ai đo. Khoá ở bộ trang trí là thứ duy nhất chặn được việc đó
	từ phía máy chủ.

	NÂNG QUYỀN HẸP NHẤT CÓ THỂ: `generate_keys` mở đầu bằng
	`frappe.only_for("System Manager")`, mà hàm này chạy dưới danh tính KHÁCH. Cửa sổ
	`Administrator` vì vậy bọc ĐÚNG một lời gọi và không hơn — việc ghi `PDA Thiet Bi`
	nằm ngoài nó. Cẩn trọng thêm: `frappe.only_for` (`frappe/__init__.py:944`) tự thoát
	sớm khi `local.flags.in_test`, nên một bài test thường KHÔNG chứng minh được đoạn
	nâng quyền này là cần — `test_cap_khoa_may_chay_duoc_duoi_quyen_khach_that` tắt cờ
	đó để đo đường thật.
	"""
	from frappe.core.doctype.user.user import generate_keys

	the = _tim_the_dung_duoc(ma)
	ma_may = chuan_ma_may(ma_may)
	if not ma_may:
		# Không có mã máy thì khoá cấp ra sẽ bị chính `kiem_khoa_may` từ chối ở lời gọi
		# kế tiếp — cấp ra một chìa khoá không mở được gì rồi để thủ kho tự đoán là tệ
		# hơn hẳn việc nói thẳng ngay tại đây.
		frappe.throw(_("Máy không gửi mã máy — không cấp khoá được. Báo trưởng kho."))

	# `frappe.set_user` xoá sạch `local.form_dict`, `local.session.data` và ghi đè
	# `session.sid` bằng chính tên tài khoản (`frappe/__init__.py:641-654`). Phần còn
	# lại của request (dựng phản hồi, `@rate_limit`) vẫn đọc những thứ đó, nên chụp lại
	# phiên cũ và trả về nguyên vẹn trong `finally` — kể cả khi `generate_keys` ném.
	# Đọc TRƯỚC khi sinh khoá: `generate_keys` giữ nguyên `api_key` cũ nếu đã có và chỉ
	# ghi đè `api_secret` (`user.py:1332`). Nên sau lời gọi đó không còn cách nào phân
	# biệt "khoá này do PDA sinh" với "khoá tích hợp có sẵn, vừa bị PDA xoay mất bí
	# mật" — phải chụp lại tình trạng trước. Xem `_khoa_co_phai_do_pda_cap`.
	khoa_cu = frappe.db.get_value("User", the.nguoi_dung, "api_key")
	# "Đè lên khoá LẠ" chứ không phải "đã có khoá": nếu chiếc khoá đang có CHÍNH LÀ khoá
	# PDA đã cấp (thủ kho đổi máy, hoặc quét lại thẻ trên cùng chiếc máy) thì xoay nó là
	# việc bình thường của Task này, không phá của ai. Chặn theo "đã có khoá" trần sẽ
	# khoá luôn đường ĐỔI MÁY — ca thường gặp nhất sau ca cấp lần đầu.
	# `_bi_mat_hien_do_pda_sinh` gồm vế dấu vân tay, nên một chiếc khoá do PDA cấp rồi bị
	# XOAY Ở DESK vẫn rơi vào nhánh "khoá lạ" và bị chặn — đúng như phải thế. CỐ Ý dùng
	# hàm này chứ KHÔNG dùng `_khoa_co_phai_do_pda_cap`: hàm kia trả lời câu hỏi của phép
	# XOÁ và mang thêm vế `khoa_von_co_truoc`, dùng nhầm ở đây thì ai đã đè một lần sẽ bị
	# chặn vĩnh viễn ở mọi lần đổi máy sau (vòng sửa 3, N1 — xem docstring hàm chặn).
	de_len_khoa_la = bool(khoa_cu) and not _bi_mat_hien_do_pda_sinh(the.nguoi_dung)
	cho_de = bool(frappe.db.get_value("PDA Badge", the.name, "cho_de_khoa_api"))
	if de_len_khoa_la and not cho_de:
		# CHẶN, KHÔNG PHẢI BÁO (vòng sửa 2, X1). Ba lý do, theo thứ tự quan trọng:
		#
		# 1. Thiệt hại TỨC THÌ VÀ KHÔNG HOÀN NGUYÊN ĐƯỢC: `generate_keys` xoay
		#    `api_secret`, và bí mật cũ không được lưu ở đâu để trả lại. Một dòng
		#    Error Log là thứ người ta đọc SAU KHI tích hợp đã chết.
		# 2. Hàm này là `allow_guest=True`, chỉ có `rate_limit(10/60)`, và tự nâng
		#    quyền lên Administrator bên trong. Nếu chỉ "báo" thì MỘT MÃ THẺ RÒ RỈ đủ
		#    để giết khoá tích hợp của đúng người đó, KHÔNG CẦN ĐĂNG NHẬP. Đó là một
		#    mặt tấn công, không phải một bất tiện vận hành.
		# 3. Với một hành động không đảo ngược được, mặc định phải là TỪ CHỐI.
		#
		# NÓI ĐƯỢC VIỆC PHẢI LÀM, không dùng câu báo chung: người gọi tới được đây là
		# đã chìa ra một tấm thẻ HỢP LỆ (`_tim_the_dung_duoc` đã chạy xong), nên lý do
		# giữ kín ở nhánh quét-sai không còn áp dụng — giấu ở đây chỉ làm thủ kho đứng
		# ở quầy mà không biết phải gọi ai.
		frappe.throw(
			_(
				"Chưa cấp được khoá cho máy này: tài khoản {0} đang có một khoá API dùng "
				"cho việc khác, cấp máy sẽ làm hỏng việc đó. Báo trưởng kho — trưởng kho "
				"tick ô 'Cho phép đè khoá API có sẵn' trên thẻ PDA rồi quét lại."
			).format(the.nguoi_dung),
			frappe.AuthenticationError,
		)

	phien_cu = frappe._dict(frappe.local.session)
	form_cu = frappe.local.form_dict
	try:
		frappe.set_user("Administrator")
		khoa = generate_keys(the.nguoi_dung)
	finally:
		frappe.set_user(phien_cu.user)
		frappe.local.session = phien_cu
		frappe.local.form_dict = form_cu

	if de_len_khoa_la:
		# Tới được đây nghĩa là trưởng kho ĐÃ cố ý bật cờ đè. Vẫn ghi Error Log: cờ chỉ
		# nói "được phép", không nói "đã xảy ra" — và tích hợp nào đang chạy bằng chiếc
		# khoá đó vừa chết thật (bí mật bị xoay). Cờ `khoa_von_co_truoc` hiện ngay trên
		# máy trong Desk; dòng Error Log là chỗ quản trị hệ thống đọc lại được sau.
		frappe.log_error(
			title="vi_tri_kho: khoa may de len khoa API co san",
			message=(
				f"{the.nguoi_dung} da co api_key truoc khi nhan may PDA {ma_may}; truong kho "
				"da bat co cho_de_khoa_api. generate_keys giu nguyen api_key va xoay "
				"api_secret nen tich hop cu dung khoa nay da hong. Thu hoi se KHONG xoa khoa do."
			),
		)
		# TIÊU THỤ CỜ NGAY. Lối thoát phải là một lần, không phải một cánh cửa mở sẵn:
		# để cờ bật vĩnh viễn thì mọi lần cấp sau đó đều đè im lặng, tức chặn thành vô
		# nghĩa. `db.set_value` chứ không `doc.save()` vì hàm này đang chạy dưới Guest.
		frappe.db.set_value("PDA Badge", the.name, "cho_de_khoa_api", 0, update_modified=False)

	_ghi_thiet_bi(the.nguoi_dung, ten_may, ma_may, khoa, de_len_khoa_la)
	frappe.db.set_value(
		"PDA Badge",
		the.name,
		{
			"lan_dung_cuoi": now_datetime(),
			"thiet_bi_cuoi": ((ten_may or "").strip() or ma_may)[:140],
		},
		update_modified=False,
	)
	return {
		# Trả MỘT LẦN, cho đúng chiếc máy vừa quét thẻ. Không đường nào đọc lại được:
		# `api_secret` cất trong `__Auth` dạng mã hoá, và `PDA Thiet Bi` không giữ gì.
		"khoa": f"{khoa['api_key']}:{khoa['api_secret']}",
		"nguoi_dung": the.nguoi_dung,
		"ho_ten": frappe.db.get_value("User", the.nguoi_dung, "full_name"),
		"ma_may": ma_may,
	}


def kiem_khoa_may() -> None:
	"""Hook `auth_hooks`: khoá máy chỉ dùng được TỪ ĐÚNG CHIẾC MÁY đã được cấp.

	Chạy ngay sau `validate_auth_via_api_keys` trong `frappe/auth.py:626
	validate_auth_via_hooks`, tức trước khi request chạm vào bất cứ hàm nghiệp vụ nào.

	BA CÁI GÁC, theo đúng thứ tự, và mỗi cái chặn một ca hỏng khác nhau:

	1. `Authorization` mang một trong `SO_DO_KHOA_API` — KHÔNG đụng vào phiên cookie.
	   Trưởng kho ngồi Desk không gửi header này; thiếu gác này thì cấp một máy PDA
	   cho ai là khoá luôn đường vào Desk của người đó. Phải gác CẢ HAI sơ đồ: chỉ gác
	   `token ` thì `Basic <base64(key:secret)>` đi lọt nguyên (đã đo, xem hằng số).
	2. Người ĐÃ từng nhận máy PDA (có ít nhất một dòng `PDA Thiet Bi`, KHÔNG lọc
	   `con_hieu_luc`). Đây là chỗ dễ viết ngược nhất trong cả Task: lọc
	   `con_hieu_luc = 1` ngay ở câu truy vấn này thì một người vừa bị thu hồi HẾT máy
	   rơi vào nhánh "không thuộc diện PDA" và được cho qua — nút Thu hồi thành đồ
	   trang trí, đúng thứ Task này sinh ra để chặn.
	3. Mã máy gửi kèm phải khớp một máy CÒN HIỆU LỰC. Thiếu header cũng là TỪ CHỐI:
	   một hàng rào chỉ chặn khi kẻ tấn công tự nguyện khai mã máy thì không phải hàng rào.

	NÓI THẲNG GIỚI HẠN: `ma_may` KHÔNG phải bí mật. Ai bê được nguyên chiếc máy thì
	cũng có mã máy của nó — spec §7 đã khai đúng điều đó ("chặn được ca chép khoá sang
	máy khác, không chặn được ca mất nguyên máy"). Giá trị thật của lớp này là ca khoá
	rò ra NGOÀI chiếc máy (bản sao lưu, nhật ký, ảnh chụp màn hình) và ca máy đã thu
	hồi. Ca mất nguyên máy do `thu_hoi`/`thu_hoi_may` lo.
	"""
	if frappe.session.user in ("", "Guest"):
		return
	dau_xac_thuc = (frappe.get_request_header("Authorization") or "").lower()
	if not dau_xac_thuc.startswith(SO_DO_KHOA_API):
		return

	# Site có `erpnext` nhưng CHƯA `migrate` thì bảng này chưa tồn tại, và hook chạy ở
	# CỬA VÀO nên một câu SELECT hỏng ở đây là 500 cho MỌI request mang khoá API, không
	# phải một lỗi cục bộ. Fail-open đúng ở ca này và chỉ ca này: chưa migrate thì chưa
	# có chiếc máy nào được cấp, không có gì để ràng buộc.
	if not frappe.db.table_exists("PDA Thiet Bi"):
		return

	may_cua_nguoi = frappe.get_all(
		"PDA Thiet Bi",
		filters={"nguoi_dung": frappe.session.user},
		fields=["name", "ma_may", "con_hieu_luc", "lan_dung_cuoi"],
	)
	if not may_cua_nguoi:
		return

	ma_may = chuan_ma_may(frappe.get_request_header(DAU_MA_MAY))
	khop = [m for m in may_cua_nguoi if m.con_hieu_luc and ma_may and chuan_ma_may(m.ma_may) == ma_may]
	if not khop:
		frappe.throw(_(CAU_KHOA_MAY_HONG), frappe.AuthenticationError)

	may = khop[0]
	gio = now_datetime()
	cu = may.lan_dung_cuoi
	if not cu or (gio - cu).total_seconds() >= PHUT_GIUA_HAI_LAN_GHI_DAU_VET * 60:
		frappe.db.set_value("PDA Thiet Bi", may.name, "lan_dung_cuoi", gio, update_modified=False)


@frappe.whitelist()
def thu_hoi_may(ma_may: str) -> dict:
	"""Thu hồi ĐÚNG MỘT chiếc máy (nút "Thu hồi máy" trên `PDA Thiet Bi`).

	Ca dùng: mất một chiếc PDA, chủ máy vẫn đi làm bình thường bằng tài khoản của họ.

	GIẾT LUÔN KHOÁ nếu người đó không còn chiếc máy nào còn hiệu lực — mà theo thiết kế
	hiện tại thì đó là MỌI LẦN, vì `_ghi_thiet_bi` chỉ cho mỗi người đúng một máy sống
	(một người = một `api_secret`). Để khoá sống trong ca đó là để lại một chìa khoá
	không còn cánh cửa nào khoá: hàng rào duy nhất còn lại sẽ là `kiem_khoa_may`, tức
	toàn bộ an toàn treo vào một cái hook. Hai lớp, không một lớp.

	NGOẠI LỆ DUY NHẤT: khoá KHÔNG do PDA cấp thì giữ lại và nói rõ vì sao
	(`_thu_hoi_khoa_neu_cua_pda`) — xoá nó là giết tích hợp của người khác mà không ai
	được báo. Ca đó rơi về một lớp (`kiem_khoa_may` vẫn từ chối mọi máy hết hiệu lực),
	và trưởng kho nhận đúng một câu nói thẳng là đang ở ca một lớp.
	"""
	_kiem_quyen_quan_ly()
	ma_may = chuan_ma_may(ma_may)
	if not frappe.db.exists("PDA Thiet Bi", ma_may):
		frappe.throw(_("Không có máy nào mang mã {0}.").format(ma_may))
	may = frappe.get_doc("PDA Thiet Bi", ma_may)
	may.con_hieu_luc = 0
	may.save(ignore_permissions=True)

	con_song = frappe.db.count(
		"PDA Thiet Bi", {"nguoi_dung": may.nguoi_dung, "con_hieu_luc": 1, "name": ["!=", may.name]}
	)
	kq_khoa = {"khoa_da_xoa": 0, "ly_do_giu_khoa": ""}
	if not con_song:
		kq_khoa = _thu_hoi_khoa_neu_cua_pda(may.nguoi_dung)
	return {
		"may": may.name,
		"nguoi_dung": may.nguoi_dung,
		"con_hieu_luc": 0,
		"con_may_khac": con_song,
		**kq_khoa,
	}


# ---------------------------------------------------------------------------
# GIỜ MÁY CHỦ (Task 5, spec §8) — máy Android trong kho không đảm bảo đúng giờ
# (không SIM, không NTP, pin yếu là trôi). Một máy lệch NGÀY âm thầm đổi nghĩa
# phán quyết HẾT HẠN của một lô vật tư y tế — đã xảy ra thật một lần (xem
# `luong/tra_cuu.js`). Vỏ app gọi hàm này MỘT LẦN lúc mở, cất kết quả vào
# `KhoApp`, rồi TIÊM vào lớp luồng qua `tao({ngay, gio})` — lớp luồng không bao
# giờ tự đọc `new Date()` cho một phán quyết.
# ---------------------------------------------------------------------------


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=SO_LAN_MOI_PHUT_GIO_MAY_CHU, seconds=60)
def gio_may_chu() -> dict:
	"""Ngày/giờ CỦA SITE, cho vỏ app đồng bộ đồng hồ thiết bị.

	TRẢ CHUỖI NGÀY/GIỜ ĐÃ QUY RA MÚI GIỜ SITE (`now_datetime()`, giống
	`frappe.datetime.get_today()`/`now_time()` mà Desk vẫn dùng) — KHÔNG bắt vỏ
	app tự suy ngày từ một mốc UTC. Header HTTP `Date` mà MỌI phản hồi web đều
	có sẵn (không cần hàm này) tưởng như đủ để lấy giờ máy chủ, nhưng nó luôn là
	giờ UTC: múi giờ VN lệch UTC+7, nên từ 17:00 đến 24:00 UTC (0h–7h sáng VN,
	đúng ca đêm) NGÀY UTC LÙI LẠI một ngày so với ngày site thật. Tự suy `ngay`
	từ đó ở phía JS là dựng lại ĐÚNG cái bẫy mà `_ngay_may_tram()`
	(`luong/tra_cuu.js`) đã né khi bỏ `toISOString()` — chỉ đổi hướng lệch từ
	"múi giờ máy" sang "múi giờ UTC", và nếu site đổi múi giờ thì phép suy đó ở
	phía JS cũng sai theo mà không ai sửa. Máy chủ tính hộ bằng `now_datetime()`
	(đã tự quy đổi múi giờ site) thì không còn phép quy đổi nào ở JS có thể làm
	sai — `moc_epoch_ms` (mốc UNIX, không múi giờ nào cả) chỉ dùng để đo ĐỘ LỆCH
	tính bằng phút, một phép trừ UTC-với-UTC là công bằng bất kể múi giờ nào.

	`allow_guest=True, methods=["POST"]` (Ruling 16 của đợt /kho — GET không đi
	qua cầu HTTP native của Capacitor): vỏ app gọi hàm này NGAY LÚC MỞ, TRƯỚC khi
	biết có khoá máy hay không (thiết bị mới nhận máy còn đang đứng ở màn quét
	thẻ) — bắt đăng nhập là hỏng đúng ca cần nó nhất. KHÔNG đọc/ghi gì, không
	phân biệt khách với người đã đăng nhập: giờ site là một sự thật CÔNG KHAI,
	không phải dữ liệu riêng của ai — cùng tinh thần `frappe.ping`.

	VÒNG SỬA 1 (soát xét, mục 5): thêm `@rate_limit(limit=10, seconds=60)` cho
	ĐỐI XỨNG với `dang_nhap_bang_the`/`cap_khoa_may` — hai hàm `allow_guest`
	khác của file này đều có, đây từng là hàm DUY NHẤT không có. Không phải vì
	rò dữ liệu (hàm không đọc/ghi CSDL, không nhận tham số nào để mà dò), mà vì
	một điểm cuối không đòi danh tính không nên là chỗ RẺ NHẤT để đập trong một
	hệ thống đang mở ra internet qua ngrok (spec §7 đã khai rủi ro này cho các
	hàm `allow_guest` khác).
	"""
	hien_tai = now_datetime()
	return {
		"ngay": hien_tai.strftime("%Y-%m-%d"),
		"gio": hien_tai.strftime("%H:%M:%S"),
		# Mốc UNIX (mili giây, UTC) — CHỈ dùng để đo độ lệch đồng hồ, KHÔNG dùng
		# để suy ngày/giờ hiển thị (xem lý do ở trên). `time.time()` chứ không
		# `hien_tai.timestamp()`: `now_datetime()` có thể trả một datetime NAIVE
		# tuỳ cấu hình múi giờ site, và `.timestamp()` trên một datetime naive tự
		# suy theo múi giờ HỆ ĐIỀU HÀNH của máy chủ — mơ hồ đúng thứ ta đang né.
		"moc_epoch_ms": int(time.time() * 1000),
	}

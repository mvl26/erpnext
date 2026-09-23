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
from datetime import datetime, timedelta, timezone

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.sessions import clear_sessions
from frappe.utils import now_datetime

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
	"""
	_kiem_quyen_quan_ly()
	if not frappe.db.exists("PDA Badge", nguoi_dung):
		frappe.throw(_("{0} chưa từng được cấp thẻ PDA — không có gì để thu hồi.").format(nguoi_dung))
	the = frappe.get_doc("PDA Badge", nguoi_dung)
	the.con_hieu_luc = 0
	the.save()
	clear_sessions(user=nguoi_dung, force=True)
	return {"the": the.name, "con_hieu_luc": 0}


CAU_BAO_CHUNG = "Thẻ không dùng được — báo trưởng kho."


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=10, seconds=60)
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

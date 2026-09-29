"""Khoá máy PDA: cấp một lần lúc nhận máy, và THU HỒI PHẢI GIẾT ĐƯỢC KHOÁ THẬT.

MỌI BÀI Ở ĐÂY CHẠY DƯỚI QUYỀN KHO THẬT, KHÔNG PHẢI `Administrator` — và đó không
phải chuyện hình thức. `erpnext/setup/utils.py::before_tests` cấp cho
`Administrator` **cả 57 vai trò**, nên một bài chạy dưới `Administrator` không
kiểm được một dòng phân quyền nào: nó tự bịt mắt mình (một lỗi quyền đã lọt qua
sáu vòng soát vì đúng chuyện này). Vì vậy:

- `cap_khoa_may` luôn gọi dưới **Guest** — đúng như súng quét gọi lúc chưa ai đăng nhập;
- `cap_the` / `thu_hoi` / `thu_hoi_may` luôn gọi dưới **Stock Manager** (trưởng kho);
- và có một bài gọi dưới **Stock User** để chứng minh thủ kho thường KHÔNG thu hồi được.

CẠM BẪY THỨ HAI, nặng hơn: `frappe.only_for()` (`frappe/__init__.py:944`) **trả về
sớm khi `local.flags.in_test`**. `generate_keys` của Frappe mở đầu bằng
`frappe.only_for("System Manager")`, nên dưới bộ test nó KHÔNG bao giờ ném lỗi dù
người gọi là Guest — một bài test thường sẽ xanh trong khi đường chạy thật 403.
`test_cap_khoa_may_chay_duoc_duoi_quyen_khach_that` tắt đúng cờ đó trong đúng một
lời gọi để đo đường thật.

Người dùng thử KHÔNG xoá được bằng rollback (`User.insert()` tự `commit()`), nên
dùng chung helper `_nguoi` của `test_the_pda` — dựng tài khoản cố định rồi dùng lại.
KHÔNG đụng `thu-pda@miyano.test`: đó là chủ thẻ `SGRL79WAQF3W` mà chủ đầu tư đang
cầm máy thử, và các bài dưới đây xoá `api_key` của chủ thẻ mình dùng.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils.password import get_decrypted_password

from erpnext.warehouse_operations.tests.test_the_pda import _nguoi

DIEM_TEST = "test_khoa_may"
#: Ba tài khoản RIÊNG của bộ bài này — không dùng lại `9p-thukho@miyano.test` của
#: `test_the_pda`, vì ở đây `thu_hoi` xoá `api_key` và đánh dấu thiết bị, tức có
#: tác dụng phụ lên tài khoản. Tách ra để hai bộ bài không giẫm chân nhau.
NGUOI_MAY = "9p-maykho@miyano.test"
NGUOI_MAY2 = "9p-maykho2@miyano.test"
TRUONG_KHO = "9p-truongkho@miyano.test"

MA_MAY_A = "MAYA0123456789ab"
MA_MAY_B = "MAYBfedcba987654"


def _khung_request(duong_dan: str, dau: dict | None = None) -> None:
	"""Dựng lại khung HTTP mà `frappe.app.init_request` dựng — có `headers`.

	Giống `_gia_lap_request()` của `test_the_pda` nhưng nhận thêm bộ header, vì cả
	hai thứ bài này đo (`Authorization: token …` và mã máy) **chỉ tồn tại ở header**.
	`cmd` đặt theo đúng đường dẫn đang giả lập, không đặt cứng một tên: khoá Redis
	của `@rate_limit` là `f"rl:{frappe.form_dict.cmd}:{ip}"`, đặt cứng một `cmd` cho
	mọi bài là gộp bộ đếm của những lời gọi chẳng liên quan vào nhau rồi dính giới
	hạn oan ở lần chạy lại trong vòng 60 giây.
	"""
	from frappe.auth import CookieManager, LoginManager
	from frappe.utils import set_request

	cmd = duong_dan[len("/api/method/") :] if duong_dan.startswith("/api/method/") else duong_dan
	set_request(method="POST", path=duong_dan, headers=dau or {})
	frappe.local.request_ip = "127.0.0.1"
	frappe.local.cookie_manager = CookieManager()
	frappe.local.login_manager = LoginManager()
	frappe.local.form_dict.cmd = cmd
	# Bộ đếm `@rate_limit` sống trong Redis THẬT, ngoài giao dịch DB — `rollback`
	# không dọn được. Chạy lại module này nhiều lần trong 60 giây sẽ cộng dồn bộ đếm
	# của lần trước và vượt hạn mức dù không bài nào gọi sai. Không bài nào ở đây
	# kiểm CHÍNH hành vi giới hạn tần suất, nên xoá khoá trước mỗi lần giả lập là an
	# toàn: chỉ chặn rò rỉ giữa các lần chạy, không bớt phạm vi kiểm tra nào.
	frappe.cache.delete_value(f"rl:{cmd}:127.0.0.1")


def _xac_thuc_bang_khoa(khoa: str, ma_may: str | None, so_do: str = "token") -> str:
	"""Chạy ĐÚNG `frappe.auth.validate_auth()` — đường mà mọi request thật đi qua.

	KHÔNG tự gọi `validate_api_key_secret` hay tự gọi hàm hook: cả hai đều bỏ qua
	đúng chỗ dễ sai nhất (thứ tự giữa khoá API và hook kiểm mã máy, và nhánh
	`if len(authorization_header) == 2 and session.user in ("", "Guest"): raise` ở
	cuối `validate_auth`). Bài kiểm phải đi cùng một đường với request thật, nếu
	không nó chỉ kiểm chính nó.

	`so_do` là sơ đồ xác thực HTTP. Frappe nhận **hai** sơ đồ cho CÙNG một cặp
	`api_key:api_secret` (`validate_auth_via_api_keys`, `frappe/auth.py:674`):
	`token <key>:<secret>` và `Basic <base64(key:secret)>`. Bài kiểm phải đi được cả
	hai, nếu không nó chỉ canh đúng một nửa cánh cửa.
	"""
	import base64

	from frappe.auth import validate_auth

	from erpnext.warehouse_operations.vitri.the_pda import DAU_MA_MAY

	if so_do == "basic":
		dau = {"Authorization": "Basic " + base64.b64encode(khoa.encode()).decode()}
	else:
		dau = {"Authorization": f"token {khoa}"}
	if ma_may is not None:
		dau[DAU_MA_MAY] = ma_may
	frappe.set_user("Guest")
	_khung_request("/api/method/frappe.ping", dau)
	validate_auth()
	return frappe.session.user


class _NenKhoaMay(FrappeTestCase):
	"""Nền chung: dựng người, dọn sạch, và LUÔN trả `frappe.set_user` về Administrator."""

	def setUp(self):
		frappe.set_user("Administrator")
		self._batdau_test = frappe.utils.now()
		_nguoi(NGUOI_MAY, ["Stock User"])
		_nguoi(NGUOI_MAY2, ["Stock User"])
		_nguoi(TRUONG_KHO, ["Stock Manager"])
		self._don_khoa_va_may()
		frappe.db.savepoint(DIEM_TEST)

	def tearDown(self):
		# `frappe.set_user("Administrator")` phải chạy KỂ CẢ KHI BÀI TEST NÉM LỖI:
		# mọi bài ở đây đổi người dùng hiện tại, và một bài ném lỗi giữa chừng sẽ để
		# lại `frappe.session.user` là thủ kho cho BÀI SAU — bài sau đỏ vì quyền, và
		# người đọc đi tìm hồi quy ở chỗ không có gì. Đặt trong `finally` chứ không
		# đặt cuối hàm, vì chính hai dòng dọn dẹp dưới đây cũng có thể ném.
		try:
			frappe.db.rollback(save_point=DIEM_TEST)
			self._don_khoa_va_may()
		finally:
			frappe.set_user("Administrator")
			# `frappe.log_error` ghi vào `tabError Log` — bảng **MyISAM**, không có giao
			# dịch, nên mọi INSERT vào đó COMMIT NGAY và `rollback` ở trên không dọn được.
			# Lọc theo mốc giờ của `setUp` để chỉ xoá đúng dòng do bộ bài này sinh ra,
			# không đụng Error Log của người khác đang thao tác thật trên cùng site dùng chung.
			#
			# PHẢI LIỆT KÊ ĐỦ MỌI TIÊU ĐỀ mà mã sản phẩm ghi ra. Vòng sửa 1 thêm tiêu đề
			# thứ hai (`cap_khoa_may` cảnh báo đè lên khoá API có sẵn) và quên dòng này —
			# 18 dòng rác đã lọt ra CSDL dùng chung trước khi bị phát hiện lúc kiểm dọn
			# dẹp. Thêm một `frappe.log_error` mới ở `the_pda.py` thì thêm một dòng ở đây.
			for tieu_de in (
				"vi_tri_kho: the_pda sai ma",
				"vi_tri_kho: khoa may de len khoa API co san",
				"vi_tri_kho: het may PDA nen giet khoa",
			):
				frappe.db.delete(
					"Error Log", {"method": tieu_de, "creation": [">=", self._batdau_test]}
				)

	def _don_khoa_va_may(self):
		"""Xoá khoá API + thiết bị của ba tài khoản thử.

		`generate_keys` ghi `User.api_key` và bảng `__Auth`; đo trên `erptest.local`
		(24/09) thì cả hai ĐỀU rollback được, nên đây không phải chỗ cứu rollback —
		nó là chốt chặn cho ca bài test ném lỗi ở giữa và cho lần chạy trước còn sót.
		"""
		from erpnext.warehouse_operations.vitri.the_pda import xoa_khoa_api

		for email in (NGUOI_MAY, NGUOI_MAY2, TRUONG_KHO):
			xoa_khoa_api(email)
		for ten in frappe.get_all(
			"PDA Thiet Bi", filters={"nguoi_dung": ["in", [NGUOI_MAY, NGUOI_MAY2, TRUONG_KHO]]}, pluck="name"
		):
			frappe.delete_doc("PDA Thiet Bi", ten, ignore_permissions=True, force=True)

	def _the(self, nguoi: str = NGUOI_MAY) -> str:
		"""Cấp thẻ DƯỚI QUYỀN TRƯỞNG KHO — không phải Administrator."""
		from erpnext.warehouse_operations.vitri.the_pda import cap_the

		frappe.set_user(TRUONG_KHO)
		try:
			return cap_the(nguoi)["ma"]
		finally:
			frappe.set_user("Administrator")

	def _bat_cho_de(self, nguoi: str = NGUOI_MAY) -> None:
		"""Trưởng kho tick ô "Cho phép đè khoá API có sẵn" — lối thoát MỘT LẦN của X1."""
		frappe.set_user(TRUONG_KHO)
		try:
			the = frappe.get_doc("PDA Badge", nguoi)
			the.cho_de_khoa_api = 1
			the.save()
		finally:
			frappe.set_user("Administrator")

	def _cap_khoa(self, ma: str, ten_may: str, ma_may: str) -> dict:
		"""Quét thẻ DƯỚI QUYỀN KHÁCH — đúng như máy gọi lúc chưa ai đăng nhập."""
		from erpnext.warehouse_operations.vitri.the_pda import cap_khoa_may

		frappe.set_user("Guest")
		_khung_request("/api/method/erpnext.warehouse_operations.vitri.the_pda.cap_khoa_may")
		try:
			return cap_khoa_may(ma=ma, ten_may=ten_may, ma_may=ma_may)
		finally:
			frappe.set_user("Administrator")


class TestCapKhoaMay(_NenKhoaMay):
	def test_cap_khoa_roi_goi_duoc_bang_khoa(self):
		"""Quét thẻ một lần → khoá dùng được cho lời gọi sau, KHÔNG cần phiên."""
		ma = self._the()
		kq = self._cap_khoa(ma, "PDA kho 1", MA_MAY_A)

		self.assertIn(":", kq["khoa"], "khoa phải có dạng <api_key>:<api_secret>")
		self.assertEqual(kq["nguoi_dung"], NGUOI_MAY)
		self.assertEqual(_xac_thuc_bang_khoa(kq["khoa"], MA_MAY_A), NGUOI_MAY)

	def test_cap_khoa_may_bat_buoc_POST(self):
		"""`GET`/`HEAD`/`OPTIONS` KHÔNG đi qua cầu HTTP native của Capacitor (đo ở
		Task 2B §3.3): chúng bị đẩy sang một URL proxy nội bộ — một đường chưa ai đo.
		Khoá phương thức ở chính bộ trang trí, không bằng một dòng chú thích."""
		from erpnext.warehouse_operations.vitri.the_pda import cap_khoa_may, dang_nhap_bang_the

		self.assertEqual(frappe.allowed_http_methods_for_whitelisted_func.get(cap_khoa_may), ["POST"])
		self.assertEqual(
			frappe.allowed_http_methods_for_whitelisted_func.get(dang_nhap_bang_the),
			["POST"],
			"mã thẻ đi trong URL của một GET là mã thẻ nằm lại trong nhật ký máy chủ",
		)

	def test_cap_khoa_may_chay_duoc_duoi_quyen_khach_that(self):
		"""BÀI QUAN TRỌNG NHẤT VỀ QUYỀN — và nó chỉ có nghĩa khi tắt `in_test`.

		`generate_keys` mở đầu bằng `frappe.only_for("System Manager")`, mà
		`frappe.only_for` (`frappe/__init__.py:944`) **trả về sớm khi
		`local.flags.in_test`**. Nghĩa là dưới bộ test, một `cap_khoa_may` QUÊN nâng
		quyền vẫn xanh — rồi 403 ngay lần quét thật đầu tiên ngoài kho. Bài này tắt
		đúng cờ đó quanh đúng một lời gọi, và giữ người gọi là **Guest** (nếu nâng
		quyền trước rồi mới gọi thì `only_for` lại thoát sớm vì `Administrator`, và
		khẳng định thành rỗng).
		"""
		from erpnext.warehouse_operations.vitri.the_pda import cap_khoa_may

		ma = self._the()
		frappe.set_user("Guest")
		_khung_request("/api/method/erpnext.warehouse_operations.vitri.the_pda.cap_khoa_may")
		in_test_cu = frappe.local.flags.in_test
		try:
			frappe.local.flags.in_test = False
			self.assertEqual(frappe.session.user, "Guest", "phải đang là Guest thì bài này mới có nghĩa")
			kq = cap_khoa_may(ma=ma, ten_may="PDA kho 1", ma_may=MA_MAY_A)
		finally:
			frappe.local.flags.in_test = in_test_cu
			frappe.set_user("Administrator")
		self.assertIn(":", kq["khoa"])

	def test_khong_luu_BI_MAT_vao_pda_thiet_bi(self):
		"""Doctype giữ DẤU VẾT và ĐỊNH DANH của khoá, tuyệt đối không giữ BÍ MẬT.

		VÒNG SỬA 1 nới bài này một nửa, và nói rõ nửa nào: `api_key` (nửa trước dấu hai
		chấm) nay ĐƯỢC ghi vào `api_key_da_cap` — đó là điều kiện để thu hồi xoá đúng
		chiếc khoá do PDA cấp thay vì giết khoá tích hợp của người khác. `api_key` một
		mình không đăng nhập được: `validate_api_key_secret` dùng nó để TRA RA người
		dùng rồi vẫn đòi `api_secret` giải mã từ `__Auth`.

		Nửa SAU dấu hai chấm — `api_secret` — vẫn phải không có mặt ở bất kỳ đâu trong
		bản ghi. Đó mới là chìa khoá."""
		ma = self._the()
		kq = self._cap_khoa(ma, "PDA kho 1", MA_MAY_A)
		api_key, api_secret = kq["khoa"].split(":")
		may = frappe.get_doc("PDA Thiet Bi", MA_MAY_A)
		json_may = frappe.as_json(may.as_dict())
		self.assertNotIn(api_secret, json_may, "PDA Thiet Bi KHÔNG được lưu api_secret")
		self.assertEqual(may.api_key_da_cap, api_key, "phải ghi ĐỊNH DANH khoá để thu hồi xoá đúng chiếc")
		self.assertEqual(may.nguoi_dung, NGUOI_MAY)
		self.assertEqual(may.con_hieu_luc, 1)

	def test_khong_cap_duoc_khoa_khi_tai_khoan_DANG_CO_khoa_API(self):
		"""VÒNG SỬA 2 (X1) — CHẶN, không chỉ báo.

		`generate_keys` xoay `api_secret` và **bí mật cũ không được lưu ở đâu để trả
		lại**: thiệt hại tức thì, không hoàn nguyên. Mà `cap_khoa_may` là
		`allow_guest=True`, chỉ có `rate_limit(10/60)`, và tự nâng quyền lên
		Administrator bên trong — nếu chỉ ghi Error Log thì **một mã thẻ rò rỉ đủ để
		giết khoá tích hợp của đúng người đó, không cần đăng nhập**. Với một hành động
		không đảo ngược được, mặc định phải là TỪ CHỐI.

		Bài này cũng canh hai thứ dễ bị bỏ quên khi ai đó "dọn" nhánh chặn:
		- khoá cũ phải còn **nguyên vẹn** sau lượt bị từ chối (cả `api_key` LẪN bí mật —
		  chặn mà vẫn kịp xoay bí mật thì chặn để làm gì);
		- **không** sinh dòng `PDA Thiet Bi` nào.
		"""
		from frappe.core.doctype.user.user import generate_keys
		from frappe.utils.password import get_decrypted_password

		khoa_cu = generate_keys(NGUOI_MAY)
		ma = self._the()
		with self.assertRaisesRegex(frappe.AuthenticationError, "đang có một khoá API dùng cho việc khác"):
			self._cap_khoa(ma, "PDA kho 1", MA_MAY_A)

		self.assertEqual(frappe.db.get_value("User", NGUOI_MAY, "api_key"), khoa_cu["api_key"])
		self.assertEqual(
			get_decrypted_password("User", NGUOI_MAY, "api_secret", raise_exception=False),
			khoa_cu["api_secret"],
			"bị từ chối rồi mà bí mật vẫn bị xoay thì lời từ chối là đồ trang trí",
		)
		self.assertFalse(frappe.db.exists("PDA Thiet Bi", MA_MAY_A))

	def test_co_cho_de_khoa_API_la_loi_thoat_MOT_LAN(self):
		"""VÒNG SỬA 2 (X1) — lối thoát phải có, nhưng phải là một lần.

		Không có lối thoát thì ca hợp lệ (người từng có khoá cũ không ai dùng) kẹt cứng.
		Lối thoát mở sẵn vĩnh viễn thì lệnh chặn thành vô nghĩa — mọi lần cấp sau đó đè
		im lặng. Nên cờ phải TỰ TẮT ngay sau lần cấp dùng nó.
		"""
		from frappe.core.doctype.user.user import generate_keys

		generate_keys(NGUOI_MAY)
		ma = self._the()
		self._bat_cho_de(NGUOI_MAY)
		kq = self._cap_khoa(ma, "PDA kho 1", MA_MAY_A)
		self.assertIn(":", kq["khoa"], "bật cờ rồi thì phải cấp được")
		self.assertEqual(frappe.db.get_value("PDA Thiet Bi", MA_MAY_A, "khoa_von_co_truoc"), 1)
		self.assertEqual(
			frappe.db.get_value("PDA Badge", NGUOI_MAY, "cho_de_khoa_api"),
			0,
			"cờ phải TỰ TẮT — để bật vĩnh viễn là mở sẵn một cánh cửa",
		)
		# Và cờ đã tắt thì một chiếc khoá LẠ MỚI lại bị chặn như cũ. Phải dựng ra một
		# chiếc khoá lạ thật (xoay ở Desk) mới đo được điều đó — KHÔNG được đo bằng cách
		# quét lại ngay, vì bí mật đang sống lúc này do chính PDA sinh nên quét lại là
		# việc hợp lệ, không phải ca bị chặn (vòng sửa 3, N1).
		from frappe.core.doctype.user.user import generate_keys

		generate_keys(NGUOI_MAY)
		ma2 = self._the()
		with self.assertRaises(frappe.AuthenticationError):
			self._cap_khoa(ma2, "PDA kho 2", MA_MAY_B)

	def test_da_de_mot_lan_roi_van_DOI_MAY_duoc_khong_phai_tick_lai(self):
		"""VÒNG SỬA 3 (N1) — "một lần" phải là MỘT LẦN, không phải "mỗi lần".

		Phép CHẶN từng dùng `_khoa_co_phai_do_pda_cap`, hàm trả lời câu hỏi của phép
		XOÁ và mang thêm vế `khoa_von_co_truoc`. Hệ quả đo được: một tài khoản đã đi lối
		thoát đúng một lần sẽ có máy mang `khoa_von_co_truoc = 1` **mãi mãi**, nên mọi
		lần đổi máy về sau đều bị chặn và đòi tick cờ lại — trong khi bí mật đang sống
		lúc đó ĐÃ do PDA sinh ra và đè lên nó chẳng giẫm chân ai. Lối thoát duy nhất khi
		ấy là xoá tay `api_key` ở Desk.

		Bài này khoá đúng ca đó: đè một lần (có cờ), rồi **đổi máy lần nữa KHÔNG cờ**.
		"""
		from frappe.core.doctype.user.user import generate_keys

		generate_keys(NGUOI_MAY)
		ma = self._the()
		self._bat_cho_de(NGUOI_MAY)
		self._cap_khoa(ma, "PDA kho 1", MA_MAY_A)
		self.assertEqual(frappe.db.get_value("PDA Thiet Bi", MA_MAY_A, "khoa_von_co_truoc"), 1)
		self.assertEqual(frappe.db.get_value("PDA Badge", NGUOI_MAY, "cho_de_khoa_api"), 0)

		# Đổi sang máy khác, KHÔNG tick cờ lần nữa — phải đi được.
		ma2 = self._the()
		kq = self._cap_khoa(ma2, "PDA kho 2", MA_MAY_B)
		self.assertIn(":", kq["khoa"])
		self.assertEqual(
			frappe.db.get_value("PDA Thiet Bi", MA_MAY_B, "khoa_von_co_truoc"),
			0,
			"máy mới đè lên khoá do CHÍNH PDA sinh — không phải ca 'khoá vốn có từ trước'",
		)
		self.assertEqual(frappe.db.get_value("PDA Thiet Bi", MA_MAY_A, "con_hieu_luc"), 0)
		self.assertEqual(_xac_thuc_bang_khoa(kq["khoa"], MA_MAY_B), NGUOI_MAY)

	def test_muoi_van_tay_phai_NGAU_NHIEN_va_thuc_su_di_vao_phep_bam(self):
		"""VÒNG SỬA 3 (N2) — hai đảo ngược từng XANH OAN, cùng một lớp.

		Người soát dựng được cả hai mà cả bộ bài vẫn 23/23 OK: (a) `muoi_khoa` là một
		hằng số (`"0"*32`), (b) `bam_bi_mat` bỏ qua muối. Không bài nào canh muối phải
		**ngẫu nhiên** và phải **thật sự đi vào phép băm**.

		Vì sao nó đáng lo dù `bi_mat_bam` không phải bí mật: mất muối thì nó là SHA-256
		TRẦN của một chuỗi 15 ký tự hex — dò ngược được bằng bảng dựng sẵn, và dò được
		HÀNG LOẠT bằng cùng một bảng. Muối riêng từng dòng là thứ chặn đúng chuyện đó,
		đúng lý do đã ghi cho `PDA Badge.muoi` từ 23/09.

		Hai khẳng định, mỗi cái bắt một đảo ngược:
		- hai máy phải có `muoi_khoa` KHÁC nhau  → bắt (a);
		- cùng một bí mật, hai muối khác nhau phải ra hai băm KHÁC nhau → bắt (b).
		"""
		from erpnext.warehouse_operations.vitri.the_pda import bam_bi_mat

		ma = self._the()
		self._cap_khoa(ma, "PDA kho 1", MA_MAY_A)
		ma2 = self._the()
		self._cap_khoa(ma2, "PDA kho 2", MA_MAY_B)

		m1 = frappe.db.get_value("PDA Thiet Bi", MA_MAY_A, "muoi_khoa")
		m2 = frappe.db.get_value("PDA Thiet Bi", MA_MAY_B, "muoi_khoa")
		self.assertTrue(m1 and m2, "thiếu muối thì băm là SHA-256 trần")
		self.assertNotEqual(m1, m2, "mỗi máy phải có MUỐI RIÊNG, không dùng chung một hằng số")
		self.assertNotEqual(
			bam_bi_mat(m1, "bi-mat-giong-het-nhau"),
			bam_bi_mat(m2, "bi-mat-giong-het-nhau"),
			"muối phải THẬT SỰ đi vào phép băm — cùng bí mật, khác muối phải ra khác băm",
		)

	def test_the_het_hieu_luc_khong_cap_duoc_khoa(self):
		from erpnext.warehouse_operations.vitri.the_pda import thu_hoi

		ma = self._the()
		frappe.set_user(TRUONG_KHO)
		thu_hoi(NGUOI_MAY)
		frappe.set_user("Administrator")
		with self.assertRaisesRegex(frappe.AuthenticationError, "Thẻ không dùng được"):
			self._cap_khoa(ma, "PDA kho 1", MA_MAY_A)
		self.assertFalse(frappe.db.exists("PDA Thiet Bi", MA_MAY_A))

	def test_ma_the_sai_khong_cap_duoc_khoa(self):
		self._the()
		with self.assertRaisesRegex(frappe.AuthenticationError, "Thẻ không dùng được"):
			self._cap_khoa("ZZZZZZZZZZZZ", "PDA kho 1", MA_MAY_A)
		self.assertFalse(frappe.db.exists("PDA Thiet Bi", MA_MAY_A))

	def test_cap_khoa_may_moi_giet_may_cu_cua_cung_nguoi(self):
		"""MỘT NGƯỜI = MỘT `api_secret`: `generate_keys` ghi đè bí mật cũ, nên cấp
		khoá cho máy thứ hai đã LÀM CHẾT máy thứ nhất ở tầng Frappe dù không ai nói.
		Doctype phải nói đúng sự thật đó, nếu không nó nói dối chính điều nó sinh ra
		để trả lời: ai đang cầm máy nào."""
		ma = self._the()
		khoa_a = self._cap_khoa(ma, "PDA kho 1", MA_MAY_A)["khoa"]
		ma2 = self._the()
		khoa_b = self._cap_khoa(ma2, "PDA kho 2", MA_MAY_B)["khoa"]

		self.assertEqual(frappe.db.get_value("PDA Thiet Bi", MA_MAY_A, "con_hieu_luc"), 0)
		self.assertEqual(frappe.db.get_value("PDA Thiet Bi", MA_MAY_B, "con_hieu_luc"), 1)
		self.assertEqual(_xac_thuc_bang_khoa(khoa_b, MA_MAY_B), NGUOI_MAY)
		frappe.set_user("Administrator")
		with self.assertRaises(frappe.AuthenticationError):
			_xac_thuc_bang_khoa(khoa_a, MA_MAY_A)


class TestKhoaGanVoiMaMay(_NenKhoaMay):
	def test_khoa_dung_tu_may_khac_bi_tu_choi(self):
		"""Khoá gắn với mã máy: chép khoá sang máy khác thì không dùng được."""
		ma = self._the()
		khoa = self._cap_khoa(ma, "PDA kho 1", MA_MAY_A)["khoa"]
		self.assertEqual(_xac_thuc_bang_khoa(khoa, MA_MAY_A), NGUOI_MAY)
		frappe.set_user("Administrator")
		with self.assertRaises(frappe.AuthenticationError):
			_xac_thuc_bang_khoa(khoa, MA_MAY_B)

	def test_khoa_khong_gui_ma_may_bi_tu_choi(self):
		"""Thiếu header là TỪ CHỐI, không phải bỏ qua: một hàng rào chỉ chặn khi kẻ
		tấn công tự nguyện khai mã máy thì không phải hàng rào."""
		ma = self._the()
		khoa = self._cap_khoa(ma, "PDA kho 1", MA_MAY_A)["khoa"]
		frappe.set_user("Administrator")
		with self.assertRaises(frappe.AuthenticationError):
			_xac_thuc_bang_khoa(khoa, None)

	def test_khoa_gui_bang_Basic_cung_bi_rang_ma_may(self):
		"""LỖ HỔNG THẬT, đã đo trên máy chủ thật TRƯỚC khi vá — không phải ca giả tưởng.

		`validate_auth_via_api_keys` nhận CÙNG một cặp `api_key:api_secret` qua HAI sơ
		đồ: `token <key>:<secret>` VÀ `Basic <base64(key:secret)>`. Hook chỉ gác tiền tố
		`token ` thì ai cầm khoá rò ra ngoài chỉ cần mã hoá lại thành `Basic` là toàn bộ
		ràng buộc mã máy biến mất — mà chính ca "khoá rò ra ngoài chiếc máy" là giá trị
		duy nhất của lớp này (mã máy không phải bí mật: mất nguyên máy thì mất cả hai).

		Đo trên `http://192.168.61.129:8003` trước khi vá:
		`Authorization: Basic <base64>` KHÔNG kèm mã máy → **HTTP 200** + đúng email thủ
		kho, trong khi cùng khoá gửi bằng `token` → 401. Ba bài mã máy bên trên đều xanh
		suốt lúc đó, vì cả ba chỉ gửi `token`.

		`bearer` CỐ Ý không gác: đó là đường OAuth (`validate_oauth`), một loại chứng
		chỉ khác hẳn, không phải khoá máy PDA — gác nó là chặn nhầm một cơ chế không
		liên quan.
		"""
		ma = self._the()
		khoa = self._cap_khoa(ma, "PDA kho 1", MA_MAY_A)["khoa"]
		self.assertEqual(_xac_thuc_bang_khoa(khoa, MA_MAY_A, so_do="basic"), NGUOI_MAY)
		frappe.set_user("Administrator")
		with self.assertRaises(frappe.AuthenticationError):
			_xac_thuc_bang_khoa(khoa, None, so_do="basic")
		frappe.set_user("Administrator")
		with self.assertRaises(frappe.AuthenticationError):
			_xac_thuc_bang_khoa(khoa, MA_MAY_B, so_do="basic")

	def test_nguoi_chua_tung_nhan_may_khong_bi_hook_dung_toi(self):
		"""Khoá API cấp cho việc KHÁC (tích hợp, script) không được vạ lây.

		Hook chỉ xét người ĐÃ có ít nhất một dòng `PDA Thiet Bi`. Đây cũng là chỗ dễ
		viết ngược nhất: nếu lọc `con_hieu_luc = 1` ngay trong câu truy vấn này thì
		một máy ĐÃ THU HỒI rơi vào nhánh "không thuộc diện máy PDA" và được cho qua —
		nút Thu hồi thành đồ trang trí. `test_thu_hoi_*` bên dưới canh chiều ngược lại.
		"""
		from frappe.core.doctype.user.user import generate_keys

		khoa = generate_keys(NGUOI_MAY2)
		chuoi = f"{khoa['api_key']}:{khoa['api_secret']}"
		self.assertEqual(_xac_thuc_bang_khoa(chuoi, None), NGUOI_MAY2)

	def test_ha_co_con_hieu_luc_trong_desk_la_may_chet_ngay(self):
		"""Bỏ dấu "Còn hiệu lực" trên `PDA Thiet Bi` là máy đó CHẾT NGAY, dù khoá còn.

		BÀI NÀY SINH RA TỪ MỘT LƯỢT PHÁ NGƯỢC XANH OAN. Lượt phá "lọc
		`con_hieu_luc = 1` ngay trong câu truy vấn của `kiem_khoa_may`" — chính cái
		đảo ngược biến nút thu hồi thành đồ trang trí — KHÔNG bài nào bắt được, vì mọi
		bài thu hồi khác đều giết luôn khoá API nên `validate_api_key_secret` đã ném
		trước khi hook chạy. Tức là cả bộ bài chỉ đang đo `xoa_khoa_api`, không đo cờ.

		Ca có thật, không phải ca giả tưởng: ô "Còn hiệu lực" là một Check trưởng kho
		bỏ dấu được ngay trong Desk (quyền write đã cấp), và đó là phản xạ tự nhiên khi
		muốn tạm khoá một chiếc máy. Ở đây cố ý KHÔNG đụng tới khoá để đo riêng cái cờ.
		"""
		ma = self._the()
		khoa = self._cap_khoa(ma, "PDA kho 1", MA_MAY_A)["khoa"]
		self.assertEqual(_xac_thuc_bang_khoa(khoa, MA_MAY_A), NGUOI_MAY)

		frappe.set_user(TRUONG_KHO)
		may = frappe.get_doc("PDA Thiet Bi", MA_MAY_A)
		may.con_hieu_luc = 0
		may.save()
		frappe.set_user("Administrator")

		self.assertIsNotNone(
			frappe.db.get_value("User", NGUOI_MAY, "api_key"),
			"bài này phải để khoá SỐNG, nếu không nó lại đo `xoa_khoa_api` một lần nữa",
		)
		with self.assertRaises(frappe.AuthenticationError):
			_xac_thuc_bang_khoa(khoa, MA_MAY_A)

	def test_may_DOI_CHU_thi_khoa_chu_cu_phai_chet(self):
		"""S1 (vòng sửa 1 Task 4) — LỖ HỔNG THẬT, dựng lại được trên site thật.

		Kịch bản: A nhận máy, rồi B quét thẻ trên CHÍNH chiếc máy đó (đổi ca, giao máy
		— ca thường gặp nhất sau ca cấp lần đầu, và Task 4 còn làm nó thường hơn vì máy
		nhớ khoá nên không ai quét lại mỗi ca). Dòng `PDA Thiet Bi` đổi chủ sang B và
		KHÔNG sinh dòng thứ hai (đúng thiết kế `_ghi_thiet_bi`). Hệ quả trước bản vá:

		    số dòng máy của A = 0  →  `kiem_khoa_may` thoát sớm (`if not may_cua_nguoi`)
		    →  khoá A không còn bị ràng buộc THIẾT BỊ NÀO:
		       khoá A + KHÔNG mã máy → nhận
		       khoá A + mã máy BỪA   → nhận

		Đúng cái lớp `X-Ma-May` sinh ra để chặn: chiếc khoá rò ra khỏi chiếc máy. Và
		"Đăng xuất" trên app KHÔNG cứu được — nó chỉ xoá kho lưu tại máy, khoá A ở máy
		chủ vẫn sống.

		BÀI NÀY ĐO THEO CHIỀU "KHOÁ CÒN DÙNG ĐƯỢC KHÔNG", không đo `api_key IS NULL`:
		một bản vá xoá `api_key` mà để `api_secret` lại (hoặc ngược lại) vẫn phải đỏ.
		Ba khẳng định, vì trước bản vá cả ba đều cho qua: đúng mã máy cũ, thiếu mã máy,
		mã máy bừa.

		CỐ Ý KHÔNG sửa `kiem_khoa_may`: phép thoát sớm ở đó đang giữ một việc khác —
		không chặn khoá API của người chưa bao giờ dùng PDA
		(`test_nguoi_chua_tung_nhan_may_khong_bi_hook_dung_toi` canh chiều đó). Đổi nó là
		đánh đổi lỗ hổng này bằng lỗ hổng kia.

		RANH GIỚI BÀI NÀY CANH LÀ `may.save()`, KHÔNG PHẢI DÒNG GÁN. Phép giết khoá chủ
		cũ phải chạy TRƯỚC `may.save()` trong `_ghi_thiet_bi`: phép kiểm dấu vân tay truy
		vấn CSDL theo `nguoi_dung = chủ_cũ`, nên sau `save()` thì chủ cũ còn 0 dòng, phép
		kiểm trả `False` (fail-closed) và khoá **không** bị xoá — bản vá im lặng không làm
		gì. Đo được: dịch lời gọi xuống sau `may.save()` (lượt phá `S1d`) → bài này ĐỎ;
		dịch xuống sau dòng gán `may.nguoi_dung = …` mà vẫn trước `save()` (lượt `S1b`) →
		KHÔNG đỏ, vì phép gán chỉ đổi đối tượng trong bộ nhớ. Ai gộp lời gọi đó xuống
		cạnh vòng hạ cờ `con_hieu_luc` — chỗ đọc như "dọn dẹp chủ cũ", tức chỗ tự nhiên
		nhất để đặt sai — sẽ bị bài này bắt.
		"""
		ma_a = self._the(NGUOI_MAY)
		khoa_a = self._cap_khoa(ma_a, "PDA kho 1", MA_MAY_A)["khoa"]
		self.assertEqual(_xac_thuc_bang_khoa(khoa_a, MA_MAY_A), NGUOI_MAY)
		frappe.set_user("Administrator")

		# B quét thẻ trên CÙNG chiếc máy → đổi chủ.
		ma_b = self._the(NGUOI_MAY2)
		khoa_b = self._cap_khoa(ma_b, "PDA kho 1", MA_MAY_A)["khoa"]
		self.assertEqual(
			frappe.db.get_value("PDA Thiet Bi", MA_MAY_A, "nguoi_dung"),
			NGUOI_MAY2,
			"máy phải ĐỔI CHỦ sang B, không sinh dòng thứ hai",
		)
		self.assertEqual(
			frappe.db.count("PDA Thiet Bi", {"nguoi_dung": NGUOI_MAY}),
			0,
			"A không còn dòng máy nào — đó chính là điều làm hook thoát sớm",
		)
		frappe.set_user("Administrator")

		# KHOÁ CỦA A PHẢI CHẾT, đo bằng ba đường mà kẻ cầm khoá rò ra sẽ thử.
		for ten_ca, ma_may in (
			("đúng mã máy cũ", MA_MAY_A),
			("KHÔNG gửi mã máy", None),
			("mã máy bừa", MA_MAY_B),
		):
			frappe.set_user("Administrator")
			with self.assertRaises(
				frappe.AuthenticationError,
				msg=f"khoá của chủ CŨ vẫn dùng được sau khi máy đổi chủ ({ten_ca})",
			):
				_xac_thuc_bang_khoa(khoa_a, ma_may)

		# ĐỐI CHỨNG DƯƠNG — không có vế này thì "A chết" có thể chỉ là "cả hai đều chết":
		# khoá của B, chủ mới, phải dùng được bình thường.
		frappe.set_user("Administrator")
		self.assertEqual(_xac_thuc_bang_khoa(khoa_b, MA_MAY_A), NGUOI_MAY2)

	def test_quet_lai_the_tren_chinh_may_cua_minh_KHONG_tu_giet_khoa(self):
		"""Mặt sau của S1: `chu_cu == nguoi_dung` thì KHÔNG được xoá gì.

		Nếu bản vá S1 xoá khoá vô điều kiện mỗi lần ghi lại dòng máy thì nó xoá đúng
		chiếc khoá `generate_keys` vừa cấp mấy dòng trước trong `cap_khoa_may` — và ca
		"quét lại thẻ trên chính máy của mình" (thủ kho quét lại vì lỡ đăng xuất, hoặc
		trưởng kho cấp lại thẻ) hỏng HOÀN TOÀN: nhận được khoá rồi mà lời gọi đầu tiên
		đã 401. Bài này khoá đúng vế đó."""
		ma = self._the(NGUOI_MAY)
		self._cap_khoa(ma, "PDA kho 1", MA_MAY_A)
		frappe.set_user("Administrator")

		ma2 = self._the(NGUOI_MAY)
		khoa2 = self._cap_khoa(ma2, "PDA kho 1", MA_MAY_A)["khoa"]
		frappe.set_user("Administrator")
		self.assertIsNotNone(
			frappe.db.get_value("User", NGUOI_MAY, "api_key"),
			"quét lại thẻ trên chính máy mình mà khoá vừa cấp đã bị xoá",
		)
		self.assertEqual(_xac_thuc_bang_khoa(khoa2, MA_MAY_A), NGUOI_MAY)

	def test_ghi_thiet_bi_goi_THANG_khong_tu_giet_khoa_dang_song(self):
		"""R7 (vòng sửa 2) — vế `chu_cu != nguoi_dung` LÀ hàng rào duy nhất, và đây là
		bài làm nó cắn.

		Vòng sửa 1 tôi khai vế đó "không bài nào làm nó cắn được". Người soát chỉ ra
		**"không bài nào" ≠ "không dựng được bài"**, rồi dựng được — và bài đó là bài
		này: gọi **THẲNG `_ghi_thiet_bi`** với chiếc khoá ĐANG SỐNG, không đi qua
		`cap_khoa_may`.

		VÌ SAO HÌNH DẠNG NÀY CÓ THẬT, không phải ca giả tưởng: đó đúng là hình dạng mà
		một Task sau sẽ viết cho "đổi tên máy" hoặc "gán lại máy cho người khác" — ghi
		lại dòng thiết bị mà KHÔNG cấp khoá mới. Khác biệt quyết định: không đi qua
		`cap_khoa_may` nghĩa là **không có lượt `generate_keys` xoay bí mật**, nên dấu
		vân tay trong dòng máy vẫn KHỚP bí mật đang sống → `_khoa_co_phai_do_pda_cap`
		trả `True` → bỏ vế `!=` là hàm tự giết đúng chiếc khoá mà người dùng đang cầm.

		Đo theo chiều "khoá còn dùng được không", không chỉ `api_key is not None`: một
		lượt xoá `api_secret` mà để `api_key` lại vẫn phải đỏ.
		"""
		from frappe.utils.password import get_decrypted_password

		from erpnext.warehouse_operations.vitri.the_pda import _ghi_thiet_bi

		ma = self._the(NGUOI_MAY)
		khoa = self._cap_khoa(ma, "PDA kho 1", MA_MAY_A)["khoa"]
		frappe.set_user("Administrator")
		self.assertEqual(_xac_thuc_bang_khoa(khoa, MA_MAY_A), NGUOI_MAY)
		frappe.set_user("Administrator")

		# Chiếc khoá ĐANG SỐNG, đọc lại từ chính chỗ Frappe cất nó.
		khoa_song = {
			"api_key": frappe.db.get_value("User", NGUOI_MAY, "api_key"),
			"api_secret": get_decrypted_password("User", NGUOI_MAY, "api_secret"),
		}
		# Hình dạng của một hàm "đổi tên máy" tương lai: cùng người, cùng máy, khoá cũ.
		_ghi_thiet_bi(NGUOI_MAY, "PDA kho 1 (đổi tên)", MA_MAY_A, khoa_song, False)

		self.assertIsNotNone(
			frappe.db.get_value("User", NGUOI_MAY, "api_key"),
			"ghi lại dòng thiết bị cho CHÍNH chủ cũ mà tự xoá khoá đang dùng",
		)
		frappe.set_user("Administrator")
		self.assertEqual(
			_xac_thuc_bang_khoa(khoa, MA_MAY_A),
			NGUOI_MAY,
			"khoá đang sống phải dùng được nguyên vẹn sau một lượt ghi lại dòng thiết bị",
		)

	def test_may_cu_bi_ha_co_cung_de_lai_dau_vet_lich_su(self):
		"""Vòng sửa 2 (R6) — máy CHẾT THEO cũng phải có lịch sử, không chỉ máy đổi chủ.

		`pda_thiet_bi.json` khai `track_changes = 1`: doctype này tự nhận việc giữ lịch
		sử. `frappe.db.set_value` (bản trước) đi thẳng xuống SQL, bỏ qua tầng Document
		nên KHÔNG sinh `tabVersion` — người đi tìm "chiếc máy này chết lúc nào, vì sao"
		chỉ thấy `modified` nhảy mà không biết vì sao.

		Bài này đọc `tabVersion` của chiếc máy CŨ và đòi đúng dòng `con_hieu_luc 1 → 0`.
		Đọc nội dung `data`, không chỉ đếm số dòng: đếm thì một lượt sửa bất kỳ nào khác
		cũng làm bài xanh.

		**CÁI BẪY PHẢI TẮT, CÙNG HẠNG VỚI `frappe.only_for` CỦA TASK 3:**
		`Document._save` đặt `self.flags.ignore_version = frappe.flags.in_test`
		(`frappe/model/document.py:397`) — tức **dưới bộ test, Frappe TẮT versioning theo
		mặc định**. Không tắt cờ đó thì `tabVersion` luôn rỗng và bài này đỏ vĩnh viễn dù
		mã sản phẩm hoàn toàn đúng; tệ hơn, nếu ai đó "sửa" bằng cách nới khẳng định
		xuống thành "không ném lỗi" thì bài thành một cái cổng không răng. Tắt quanh
		ĐÚNG MỘT lời gọi — đúng cách `test_cap_khoa_may_chay_duoc_duoi_quyen_khach_that`
		đã làm với `only_for` — và trả lại trong `finally`.
		"""
		import json

		ma = self._the(NGUOI_MAY)
		self._cap_khoa(ma, "PDA kho 1", MA_MAY_A)
		frappe.set_user("Administrator")
		# Cùng người nhận máy THỨ HAI → máy thứ nhất phải chết theo.
		ma2 = self._the(NGUOI_MAY)
		trong_test = frappe.flags.in_test
		try:
			frappe.flags.in_test = False
			self._cap_khoa(ma2, "PDA kho 2", MA_MAY_B)
		finally:
			frappe.flags.in_test = trong_test
			frappe.set_user("Administrator")

		self.assertEqual(frappe.db.get_value("PDA Thiet Bi", MA_MAY_A, "con_hieu_luc"), 0)
		doi = []
		for v in frappe.get_all(
			"Version",
			filters={"ref_doctype": "PDA Thiet Bi", "docname": MA_MAY_A},
			pluck="data",
		):
			doi += json.loads(v).get("changed", [])
		self.assertIn(
			["con_hieu_luc", 1, 0],
			doi,
			f"máy cũ bị hạ cờ mà KHÔNG để lại lịch sử (track_changes=1 bị đường ghi bỏ qua); thấy: {doi}",
		)

	def test_site_chua_migrate_thi_hook_im_lang_cho_qua(self):
		"""VÒNG SỬA 1 — nhánh fail-open cho site có `erpnext` mà CHƯA `migrate`.

		Người soát bỏ hẳn gác `table_exists` mà cả `test_khoa_may` lẫn `test_pda_thiet_bi`
		vẫn xanh: trên `erptest.local` bảng luôn tồn tại nên đoạn đó là **mã chết ở đây**
		— mà nó lại chính là thứ bảo vệ site thật `miyano` trong cửa sổ giữa `install_app`
		và `migrate`. Mất nó thì hook ném `SELECT` vào một bảng chưa có, ngay ở CỬA VÀO,
		tức **500 cho mọi request mang khoá API**, không phải một lỗi cục bộ.

		Ép `table_exists` trả `False` là cách duy nhất dựng lại cửa sổ đó mà không phải
		`DROP TABLE` trên một CSDL dùng chung. Khẳng định: hook **không ném**, và danh
		tính do khoá API dựng vẫn nguyên — đúng nghĩa "cho qua", không phải "nuốt lỗi".
		"""
		from erpnext.warehouse_operations.vitri.the_pda import kiem_khoa_may

		ma = self._the()
		khoa = self._cap_khoa(ma, "PDA kho 1", MA_MAY_A)["khoa"]
		# Đúng bộ header mà một máy BỊ TỪ CHỐI sẽ gửi (CỐ Ý thiếu mã máy) — để nhánh
		# dưới cho qua là vì CHƯA MIGRATE, không phải vì lời gọi vốn đã hợp lệ.
		_khung_request("/api/method/frappe.ping", {"Authorization": f"token {khoa}"})
		frappe.set_user(NGUOI_MAY)
		try:
			that = frappe.db.table_exists
			try:
				frappe.db.table_exists = lambda *a, **k: False
				kiem_khoa_may()
			finally:
				frappe.db.table_exists = that
			self.assertEqual(
				frappe.session.user, NGUOI_MAY, "cho qua nghĩa là giữ nguyên danh tính, không nuốt lỗi"
			)
			# ĐỐI CHỨNG DƯƠNG, không có nó thì khẳng định trên vô nghĩa: cùng bộ header
			# ấy, khi bảng CÓ tồn tại, phải bị từ chối.
			with self.assertRaises(frappe.AuthenticationError):
				kiem_khoa_may()
		finally:
			frappe.set_user("Administrator")

	def test_hook_khong_dung_toi_phien_cookie(self):
		"""Trưởng kho đăng nhập Desk bằng cookie, không có header `Authorization` —
		hook phải im lặng. Thiếu gác này thì cấp một máy PDA cho ai là khoá luôn
		đường vào Desk của người đó."""
		from erpnext.warehouse_operations.vitri.the_pda import kiem_khoa_may

		ma = self._the()
		self._cap_khoa(ma, "PDA kho 1", MA_MAY_A)
		# Dựng request TRƯỚC rồi mới `set_user`: `LoginManager()` tự dựng lại một phiên
		# (`make_session`) và kéo người dùng về `Guest` — đặt ngược thứ tự thì bài này
		# chỉ đang kiểm một phiên khách, không kiểm được phiên cookie của ai cả.
		_khung_request("/api/method/frappe.ping")
		frappe.set_user(NGUOI_MAY)
		kiem_khoa_may()
		self.assertEqual(frappe.session.user, NGUOI_MAY)


class TestThuHoiGietKhoa(_NenKhoaMay):
	def test_thu_hoi_the_giet_luon_khoa_may(self):
		"""Mất máy: trưởng kho bấm Thu hồi là máy đó chết NGAY. Nếu khoá còn sống sau
		khi thu hồi thì nút đó chỉ là trang trí — và app đang mở ra internet qua ngrok,
		nên kẻ nhặt được máy dùng được từ bất cứ đâu."""
		ma = self._the()
		khoa = self._cap_khoa(ma, "PDA kho 1", MA_MAY_A)["khoa"]
		self.assertEqual(_xac_thuc_bang_khoa(khoa, MA_MAY_A), NGUOI_MAY)

		from erpnext.warehouse_operations.vitri.the_pda import thu_hoi

		frappe.set_user(TRUONG_KHO)
		thu_hoi(NGUOI_MAY)
		frappe.set_user("Administrator")

		self.assertIsNone(frappe.db.get_value("User", NGUOI_MAY, "api_key"))
		self.assertIsNone(get_decrypted_password("User", NGUOI_MAY, "api_secret", raise_exception=False))
		self.assertEqual(frappe.db.get_value("PDA Thiet Bi", MA_MAY_A, "con_hieu_luc"), 0)
		with self.assertRaises(frappe.AuthenticationError):
			_xac_thuc_bang_khoa(khoa, MA_MAY_A)

	def test_thu_hoi_may_le_giet_khoa_cua_chu_may(self):
		"""Nút "Thu hồi máy" cho ca mất ĐÚNG MỘT MÁY. Vì một người chỉ có đúng một
		`api_secret`, thu hồi chiếc máy đang hoạt động cuối cùng của người đó thì phải
		giết luôn khoá — để lại khoá sống là để lại một chìa khoá không cửa nào khoá."""
		from erpnext.warehouse_operations.vitri.the_pda import thu_hoi_may

		ma = self._the()
		khoa = self._cap_khoa(ma, "PDA kho 1", MA_MAY_A)["khoa"]
		frappe.set_user(TRUONG_KHO)
		thu_hoi_may(MA_MAY_A)
		frappe.set_user("Administrator")

		self.assertEqual(frappe.db.get_value("PDA Thiet Bi", MA_MAY_A, "con_hieu_luc"), 0)
		self.assertIsNone(frappe.db.get_value("User", NGUOI_MAY, "api_key"))
		with self.assertRaises(frappe.AuthenticationError):
			_xac_thuc_bang_khoa(khoa, MA_MAY_A)

	def test_thu_hoi_may_khong_dung_toi_may_cua_nguoi_khac(self):
		"""Thu hồi một máy không được là một lệnh thu hồi cả kho."""
		from erpnext.warehouse_operations.vitri.the_pda import thu_hoi_may

		ma_a = self._the(NGUOI_MAY)
		khoa_a = self._cap_khoa(ma_a, "PDA kho 1", MA_MAY_A)["khoa"]
		ma_b = self._the(NGUOI_MAY2)
		khoa_b = self._cap_khoa(ma_b, "PDA kho 2", MA_MAY_B)["khoa"]

		frappe.set_user(TRUONG_KHO)
		thu_hoi_may(MA_MAY_A)
		frappe.set_user("Administrator")

		with self.assertRaises(frappe.AuthenticationError):
			_xac_thuc_bang_khoa(khoa_a, MA_MAY_A)
		frappe.set_user("Administrator")
		self.assertEqual(_xac_thuc_bang_khoa(khoa_b, MA_MAY_B), NGUOI_MAY2)

	def test_thu_hoi_khong_giet_khoa_API_khong_phai_cua_PDA(self):
		"""VÒNG SỬA 1 — thu hồi một chiếc PDA KHÔNG được giết khoá tích hợp của người khác.

		Ca thật: một tài khoản đã dùng `api_key` cho một tích hợp/script, rồi mới được
		cấp máy PDA. `generate_keys` **giữ nguyên `api_key` cũ** và chỉ xoay `api_secret`
		(`user.py:1332`), nên nếu chỉ so `api_key` thì phép kiểm xuất xứ luôn trả "của
		PDA" — phải dựa thêm vào cờ `khoa_von_co_truoc` ghi lúc cấp.

		Điều bài này canh: sau thu hồi, **máy vẫn chết** (`con_hieu_luc = 0` và mọi lời
		gọi 401) nhưng **`api_key` vẫn còn**, và người gọi nhận về một câu nói rõ vì sao
		để trưởng kho tự quyết — không phải một hành động im lặng.
		"""
		from frappe.core.doctype.user.user import generate_keys

		from erpnext.warehouse_operations.vitri.the_pda import thu_hoi

		# Khoá có TRƯỚC: đây là chiếc khoá tích hợp, chưa liên quan gì tới PDA.
		khoa_tich_hop = generate_keys(NGUOI_MAY)["api_key"]
		ma = self._the()
		# Từ vòng sửa 2, ca này bị CHẶN theo mặc định — phải bật lối thoát của trưởng kho
		# thì mới dựng lại được trạng thái "máy cấp đè lên khoá có sẵn" mà bài này đo.
		self._bat_cho_de(NGUOI_MAY)
		khoa = self._cap_khoa(ma, "PDA kho 1", MA_MAY_A)["khoa"]
		self.assertEqual(khoa.split(":")[0], khoa_tich_hop, "generate_keys phải GIỮ NGUYÊN api_key cũ")
		self.assertEqual(frappe.db.get_value("PDA Thiet Bi", MA_MAY_A, "khoa_von_co_truoc"), 1)

		frappe.set_user(TRUONG_KHO)
		kq = thu_hoi(NGUOI_MAY)
		frappe.set_user("Administrator")

		self.assertEqual(kq["khoa_da_xoa"], 0, "khoá không do PDA cấp thì KHÔNG được xoá")
		self.assertTrue(kq["ly_do_giu_khoa"], "giữ lại khoá mà im lặng là tệ hơn cả xoá nhầm")
		self.assertEqual(frappe.db.get_value("User", NGUOI_MAY, "api_key"), khoa_tich_hop)
		self.assertEqual(frappe.db.get_value("PDA Thiet Bi", MA_MAY_A, "con_hieu_luc"), 0)
		with self.assertRaises(frappe.AuthenticationError):
			_xac_thuc_bang_khoa(khoa, MA_MAY_A)

	def test_thu_hoi_van_giet_khoa_do_chinh_PDA_cap(self):
		"""Vế còn lại của bài trên: khoá DO PDA sinh ra thì vẫn bị xoá sạch, và hàm nói
		đúng là nó đã xoá. Thiếu bài này thì bản vá "chỉ xoá khi khớp" có thể im lặng
		thành "không bao giờ xoá" mà vẫn xanh."""
		from frappe.utils.password import get_decrypted_password

		from erpnext.warehouse_operations.vitri.the_pda import thu_hoi

		ma = self._the()
		self._cap_khoa(ma, "PDA kho 1", MA_MAY_A)
		self.assertEqual(frappe.db.get_value("PDA Thiet Bi", MA_MAY_A, "khoa_von_co_truoc"), 0)
		self.assertEqual(
			frappe.db.get_value("PDA Thiet Bi", MA_MAY_A, "api_key_da_cap"),
			frappe.db.get_value("User", NGUOI_MAY, "api_key"),
			"phải ghi lại ĐÚNG chiếc khoá vừa cấp, nếu không thu hồi sẽ không dám xoá",
		)

		frappe.set_user(TRUONG_KHO)
		kq = thu_hoi(NGUOI_MAY)
		frappe.set_user("Administrator")

		self.assertEqual(kq["khoa_da_xoa"], 1)
		self.assertEqual(kq["ly_do_giu_khoa"], "")
		self.assertIsNone(frappe.db.get_value("User", NGUOI_MAY, "api_key"))
		self.assertIsNone(
			get_decrypted_password("User", NGUOI_MAY, "api_secret", raise_exception=False),
			"xoá `api_key` mà bỏ sót `api_secret` là để lại một mảnh bí mật mồ côi trên đĩa",
		)

	def test_thu_hoi_khong_giet_khoa_XOAY_SAU_khi_nhan_may(self):
		"""VÒNG SỬA 2 (X2) — ca NGƯỢC CHIỀU THỜI GIAN mà vòng soát thứ hai tìm ra.

		Vòng sửa 1 chỉ phủ ca *khoá có TRƯỚC rồi mới nhận máy*. Ca này đảo thứ tự: nhận
		máy PDA trước (trên tài khoản trắng, nên `khoa_von_co_truoc = 0` và
		`api_key_da_cap` khớp), rồi người dùng bấm **Generate Keys ở Desk** cho một việc
		khác. `generate_keys` **giữ nguyên `api_key`** và chỉ xoay bí mật, nên hai vế cũ
		vẫn trả "đúng, khoá của PDA" trong khi chiếc khoá đang sống là chiếc **PDA chưa
		bao giờ cấp** — thu hồi sẽ xoá sạch nó. Đúng tai nạn bản vá vòng 1 sinh ra để
		tránh, chỉ khác thứ tự thời gian.

		Vế thứ ba (dấu vân tay của BÍ MẬT) là thứ duy nhất phân biệt được, vì định danh
		`api_key` bất biến qua mọi lần xoay.
		"""
		from frappe.core.doctype.user.user import generate_keys
		from frappe.utils.password import get_decrypted_password

		from erpnext.warehouse_operations.vitri.the_pda import thu_hoi

		ma = self._the()
		khoa_pda = self._cap_khoa(ma, "PDA kho 1", MA_MAY_A)["khoa"]
		self.assertEqual(frappe.db.get_value("PDA Thiet Bi", MA_MAY_A, "khoa_von_co_truoc"), 0)

		# Người dùng tự bấm "Generate Keys" ở Desk SAU khi đã nhận máy.
		khoa_moi = generate_keys(NGUOI_MAY)
		self.assertEqual(
			khoa_moi["api_key"],
			khoa_pda.split(":")[0],
			"generate_keys GIỮ NGUYÊN api_key — đó chính là lý do phép kiểm cũ không bắt được",
		)
		self.assertNotEqual(khoa_moi["api_secret"], khoa_pda.split(":")[1])

		frappe.set_user(TRUONG_KHO)
		kq = thu_hoi(NGUOI_MAY)
		frappe.set_user("Administrator")

		self.assertEqual(kq["khoa_da_xoa"], 0, "khoá XOAY SAU không phải của PDA — không được xoá")
		self.assertTrue(kq["ly_do_giu_khoa"])
		self.assertEqual(frappe.db.get_value("User", NGUOI_MAY, "api_key"), khoa_moi["api_key"])
		self.assertEqual(
			get_decrypted_password("User", NGUOI_MAY, "api_secret", raise_exception=False),
			khoa_moi["api_secret"],
		)
		# Nhưng MÁY vẫn phải chết — đó là vế không được đánh đổi.
		self.assertEqual(frappe.db.get_value("PDA Thiet Bi", MA_MAY_A, "con_hieu_luc"), 0)
		with self.assertRaises(frappe.AuthenticationError):
			_xac_thuc_bang_khoa(f"{khoa_moi['api_key']}:{khoa_moi['api_secret']}", MA_MAY_A)

	def test_xoa_dong_thiet_bi_trong_desk_khong_lam_khoa_song_lai(self):
		"""SOÁT TỔNG (N1) — thao tác BÌNH THƯỜNG của trưởng kho không được gỡ ràng buộc mã máy.

		`kiem_khoa_may` cố ý thoát sớm khi một người không còn dòng `PDA Thiet Bi` nào
		(để khoá API của người NGOÀI diện PDA không bị vạ lây — có bài canh riêng). Nhưng
		`Stock Manager` có `delete:1` trên chính doctype đó, nên **dọn danh sách máy cũ**
		là đủ để chủ cũ còn 0 dòng → hook thoát sớm → khoá **ĐÃ THU HỒI** xác thực lại
		được, **không cần `X-Ma-May`**. Người soát đã đo đúng ca này.

		Bài dựng đúng ca xấu nhất: khoá "vốn có từ trước", tức ca mà `thu_hoi_may` tự khai
		là **một lớp** (cố ý không xoá khoá). Khi dòng máy biến mất thì lớp duy nhất còn
		lại cũng biến mất — nên xoá dòng phải KÉO THEO việc giết khoá.
		"""
		from frappe.core.doctype.user.user import generate_keys

		from erpnext.warehouse_operations.vitri.the_pda import thu_hoi_may

		generate_keys(NGUOI_MAY)
		ma = self._the()
		self._bat_cho_de(NGUOI_MAY)
		khoa = self._cap_khoa(ma, "PDA kho 1", MA_MAY_A)["khoa"]
		self.assertEqual(_xac_thuc_bang_khoa(khoa, MA_MAY_A), NGUOI_MAY)

		frappe.set_user(TRUONG_KHO)
		kq = thu_hoi_may(MA_MAY_A)
		frappe.set_user("Administrator")
		self.assertEqual(kq["khoa_da_xoa"], 0, "bài này phải ở ca MỘT LỚP thì mới đo đúng thứ cần đo")
		self.assertIsNotNone(frappe.db.get_value("User", NGUOI_MAY, "api_key"))
		with self.assertRaises(frappe.AuthenticationError):
			_xac_thuc_bang_khoa(khoa, MA_MAY_A)

		# Trưởng kho dọn danh sách máy — ĐÚNG người, ĐÚNG quyền, thao tác bình thường.
		frappe.set_user(TRUONG_KHO)
		frappe.delete_doc("PDA Thiet Bi", MA_MAY_A)
		frappe.set_user("Administrator")

		self.assertIsNone(
			frappe.db.get_value("User", NGUOI_MAY, "api_key"),
			"xoá dòng máy cuối cùng phải kéo theo việc giết khoá — nếu không, hook thoát "
			"sớm và chiếc khoá ĐÃ THU HỒI sống lại",
		)
		with self.assertRaises(frappe.AuthenticationError):
			_xac_thuc_bang_khoa(khoa, MA_MAY_A)

	def test_doi_nguoi_dung_trong_desk_khong_lam_khoa_chu_cu_song_lai(self):
		"""SOÁT TỔNG (N1), cửa thứ hai: gán lại một chiếc máy cho người khác.

		`nguoi_dung` không `set_only_once` (cố ý — `_ghi_thiet_bi` CẦN gán lại khi một
		chiếc máy được trao tay ở quầy), nên trưởng kho đổi ô "Người dùng" trong Desk là
		chủ cũ còn 0 dòng máy: **đúng cánh cửa của bài trên**, chỉ khác đường vào.
		"""
		ma = self._the()
		khoa_cu = self._cap_khoa(ma, "PDA kho 1", MA_MAY_A)["khoa"]
		self.assertEqual(_xac_thuc_bang_khoa(khoa_cu, MA_MAY_A), NGUOI_MAY)

		frappe.set_user(TRUONG_KHO)
		may = frappe.get_doc("PDA Thiet Bi", MA_MAY_A)
		may.nguoi_dung = NGUOI_MAY2
		may.save()
		frappe.set_user("Administrator")

		self.assertEqual(frappe.db.count("PDA Thiet Bi", {"nguoi_dung": NGUOI_MAY}), 0)
		self.assertIsNone(
			frappe.db.get_value("User", NGUOI_MAY, "api_key"),
			"đổi chủ chiếc máy cuối cùng phải giết khoá của CHỦ CŨ",
		)
		with self.assertRaises(frappe.AuthenticationError):
			_xac_thuc_bang_khoa(khoa_cu, MA_MAY_A)

	def test_xoa_mot_may_khi_van_con_may_khac_thi_KHONG_giet_khoa(self):
		"""Vế ngược của hai bài trên — nếu không có nó thì bản vá dễ thành "xoá gì cũng
		giết khoá", và ca đổi máy bình thường ở quầy sẽ mất khoá oan.

		Còn ít nhất một dòng máy thì `kiem_khoa_may` VẪN cưỡng chế được, nên không có lý
		do gì đụng tới chiếc khoá."""
		ma = self._the()
		self._cap_khoa(ma, "PDA kho 1", MA_MAY_A)
		ma2 = self._the()
		khoa = self._cap_khoa(ma2, "PDA kho 2", MA_MAY_B)["khoa"]

		frappe.set_user(TRUONG_KHO)
		frappe.delete_doc("PDA Thiet Bi", MA_MAY_A)  # dọn chiếc máy CŨ, đã hết hiệu lực
		frappe.set_user("Administrator")

		self.assertIsNotNone(frappe.db.get_value("User", NGUOI_MAY, "api_key"))
		self.assertEqual(_xac_thuc_bang_khoa(khoa, MA_MAY_B), NGUOI_MAY)

	def test_thu_hoi_the_de_lai_dau_vet_trong_tabVersion(self):
		"""SOÁT TỔNG (V4) — máy chết phải có LỊCH SỬ, không chỉ `modified` nhảy.

		`thu_hoi` từng hạ `con_hieu_luc` bằng `frappe.db.set_value`, tức đi vòng qua tầng
		Document nên không sinh dòng `tabVersion`. Trưởng kho hỏi "chiếc máy này chết lúc
		nào, ai bấm" thì không có gì để trả lời. `thu_hoi_may` và `_ghi_thiet_bi` đều đã
		dùng `save()` — đường trưởng kho dùng NHIỀU NHẤT lại là đường duy nhất còn sai.

		`frappe.flags.in_test` phải tắt quanh ĐÚNG một lời gọi: `Document._save` đặt
		`ignore_version = frappe.flags.in_test`, nên dưới bộ test Frappe **không bao giờ**
		ghi `tabVersion` và bài này sẽ đỏ oan dù mã đã đúng.
		"""
		from erpnext.warehouse_operations.vitri.the_pda import thu_hoi

		ma = self._the()
		self._cap_khoa(ma, "PDA kho 1", MA_MAY_A)
		truoc = frappe.db.count("Version", {"ref_doctype": "PDA Thiet Bi", "docname": MA_MAY_A})

		in_test_cu = frappe.local.flags.in_test
		frappe.set_user(TRUONG_KHO)
		try:
			frappe.local.flags.in_test = False
			thu_hoi(NGUOI_MAY)
		finally:
			frappe.local.flags.in_test = in_test_cu
			frappe.set_user("Administrator")

		self.assertEqual(frappe.db.get_value("PDA Thiet Bi", MA_MAY_A, "con_hieu_luc"), 0)
		self.assertGreater(
			frappe.db.count("Version", {"ref_doctype": "PDA Thiet Bi", "docname": MA_MAY_A}),
			truoc,
			"thu_hoi phải đi qua tầng Document để để lại dấu vết lịch sử",
		)

	def test_thu_kho_thuong_khong_thu_hoi_duoc_may(self):
		"""Quyền thu hồi là của TRƯỞNG KHO. Bài này là lý do cả module không chạy dưới
		`Administrator`: dưới Administrator (57 vai trò) nó xanh vô nghĩa."""
		from erpnext.warehouse_operations.vitri.the_pda import thu_hoi_may

		ma = self._the()
		self._cap_khoa(ma, "PDA kho 1", MA_MAY_A)
		frappe.set_user(NGUOI_MAY)
		try:
			with self.assertRaises(frappe.PermissionError):
				thu_hoi_may(MA_MAY_A)
		finally:
			frappe.set_user("Administrator")
		self.assertEqual(frappe.db.get_value("PDA Thiet Bi", MA_MAY_A, "con_hieu_luc"), 1)

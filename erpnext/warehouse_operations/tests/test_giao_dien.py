"""Hai lối vào giao diện của module: Workspace và nút trên phiếu Warehouse.

Cả hai đều hỏng theo kiểu KHÔNG ném lỗi — đó là lý do chúng đáng có bài riêng:

- Workspace trỏ tới một doctype/báo cáo sai tên thì Frappe vẫn dựng trang,
  chỉ là ô đó bấm vào ra trang trắng. Không log, không lỗi.
- Nút trên Warehouse gắn qua `doctype_js` trong `erpnext/hooks.py` — cùng file
  upstream với móc `Stock Ledger Entry`, nên cùng chịu rủi ro "merge giải sai
  thì mất lặng lẽ". Mất nút thì thủ kho không còn đường vào từ phiếu kho, mà
  chẳng có gì báo.
"""

import json
import os

import frappe
from frappe.tests.utils import FrappeTestCase

# Tên workspace CÓ DẤU, tên module KHÔNG DẤU — hai thứ khác nhau, cố ý.
#
# Workspace: `name` quyết định đường dẫn (`/app/quản-lý-kho`). Mọi workspace
# khác trên site đều có `name` trùng `title`, nên đặt `name` không dấu trong
# khi `title` có dấu là tự đẻ ra một đường dẫn không ai đoán được — người dùng
# đọc tiêu đề "Quản lý kho" rồi gõ `/app/quản-lý-kho` và nhận trang "Not found"
# (đã xảy ra hai lần, 13-14/09/2026). Đổi lại cho khớp quy ước của site; tiền
# lệ sẵn có trong repo: `erpnext/selling/workspace/bán_hàng/`.
#
# Module: PHẢI giữ ASCII. `frappe.scrub()` biến tên module thành đường dẫn gói
# Python, nên tên module có dấu sẽ sinh thư mục và module Python non-ASCII.
TEN_WORKSPACE = "Quản lý kho"
TEN_MODULE = "Warehouse Operations"
DUONG_DAN_JS = "public/js/warehouse_operations/warehouse.js"
# Hằng RIÊNG cho form lô — không dùng chung `DUONG_DAN_JS`: hai nút gắn vào hai
# doctype khác nhau, gộp một hằng thì một lần đổi đường dẫn sẽ kéo bài kia xanh
# giả theo.
DUONG_DAN_JS_LO = "public/js/warehouse_operations/batch.js"


class TestWorkspace(FrappeTestCase):
	def test_workspace_ton_tai_va_thuoc_module(self):
		self.assertEqual(
			frappe.db.get_value("Workspace", TEN_WORKSPACE, "module"),
			TEN_MODULE,
			f"Workspace {TEN_WORKSPACE!r} phải tồn tại và thuộc module {TEN_MODULE!r}. "
			"Hai tên này KHÁC NHAU và phải khác nhau — xem chú thích ở đầu file.",
		)

	def test_ten_workspace_co_dau_de_duong_dan_doan_duoc(self):
		"""Chặn việc vô tình đặt lại `name` không dấu.

		Đường dẫn workspace suy từ `name`, không phải `title`. Đặt `name`
		không dấu thì trang vẫn chạy bình thường ở `/app/quan-ly-kho` — không
		lỗi, không log — chỉ là người đọc tiêu đề "Quản lý kho" gõ
		`/app/quản-lý-kho` sẽ nhận "Not found". Đúng kiểu hỏng im lặng.
		"""
		name, title = frappe.db.get_value("Workspace", TEN_WORKSPACE, ["name", "title"])
		self.assertEqual(
			name,
			title,
			"`name` và `title` của workspace phải trùng nhau, như mọi workspace "
			f"khác trên site (Bán hàng, Kho khách hàng). Đang lệch: {name!r} vs {title!r}.",
		)

	def test_moi_lien_ket_deu_tro_toi_thu_co_that(self):
		"""Ô trỏ sai tên vẫn hiện ra, bấm vào mới ra trang trắng — bắt ở đây."""
		ws = frappe.get_doc("Workspace", TEN_WORKSPACE)
		hong = []
		for l in ws.links:
			if l.type != "Link":
				continue
			dt = l.link_type if l.link_type in ("Report", "Page") else "DocType"
			if not frappe.db.exists(dt, l.link_to):
				hong.append(f"{l.label} -> {dt} {l.link_to!r}")
		self.assertEqual(hong, [], f"liên kết trỏ vào hư không: {hong}")

	def test_moi_loi_tat_deu_tro_toi_thu_co_that(self):
		ws = frappe.get_doc("Workspace", TEN_WORKSPACE)
		hong = []
		for s in ws.shortcuts:
			dt = s.type if s.type in ("Report", "Page") else "DocType"
			if not frappe.db.exists(dt, s.link_to):
				hong.append(f"{s.label} -> {dt} {s.link_to!r}")
		self.assertEqual(hong, [], f"lối tắt trỏ vào hư không: {hong}")

	def test_co_ca_bao_cao_lan_doctype(self):
		"""Chặn kiểu hỏng 'workspace rỗng vẫn xanh': ba bài trên đều xanh khi
		danh sách liên kết TRỐNG. Bài này đòi workspace thật sự dẫn đi đâu đó.
		"""
		ws = frappe.get_doc("Workspace", TEN_WORKSPACE)
		loai = {l.link_type for l in ws.links if l.type == "Link"}
		self.assertIn("DocType", loai)
		self.assertIn("Report", loai)


class TestNutTrenPhieuKho(FrappeTestCase):
	def test_doctype_js_gan_vao_warehouse(self):
		"""Móc này ở `erpnext/hooks.py` — cùng file, cùng rủi ro merge với móc SLE."""
		gan = frappe.get_hooks("doctype_js").get("Warehouse") or []
		if isinstance(gan, str):
			gan = [gan]
		self.assertIn(
			DUONG_DAN_JS,
			gan,
			"Phiếu Warehouse không còn nạp JS của module. Không có nó thì thủ kho "
			"mất đường vào quản lý vị trí ngay trên phiếu kho, mà không lỗi nào báo. "
			"Kiểm `doctype_js` trong erpnext/hooks.py.",
		)

	def test_file_js_co_that(self):
		"""`doctype_js` trỏ file không tồn tại thì Frappe im lặng bỏ qua."""
		duong_dan = frappe.get_app_path("erpnext", *DUONG_DAN_JS.split("/"))
		self.assertTrue(os.path.exists(duong_dan), f"thiếu file {duong_dan}")

	def test_ma_nut_thuc_su_den_duoc_form(self):
		"""Đi đúng đường trình duyệt đi, thay vì chỉ tin hook + file có mặt.

		Hai bài trên cộng lại vẫn KHÔNG chứng minh nút hiện ra: hook có thể
		đúng, file có thể tồn tại, mà Frappe vẫn không ghép được vào form (sai
		tên app trong đường dẫn, file lỗi cú pháp, v.v.). `FormMeta` là lớp
		thật sự ghép JS gửi xuống — `frappe.get_meta()` thường KHÔNG nạp phần
		này, nên kiểm bằng nó sẽ ra chuỗi rỗng và tưởng là hỏng.
		"""
		from frappe.desk.form.meta import get_meta as form_meta

		frappe.clear_cache(doctype="Warehouse")
		js = form_meta("Warehouse").as_dict().get("__js") or ""
		for dau_hieu in ("Bật quản lý vị trí", "Ô kệ của kho", "Đối soát tồn vị trí"):
			self.assertIn(dau_hieu, js, f"JS gửi xuống form Warehouse thiếu nút {dau_hieu!r}")


class TestNutTrenPhieuLo(FrappeTestCase):
	"""Nút "In nhãn" trên form `Batch` — cùng kiểu hỏng im lặng với nút Warehouse.

	Mất dòng `"Batch": "public/js/warehouse_operations/batch.js"` trong `doctype_js` thì
	form `Batch` vẫn mở bình thường, vẫn lưu được, chỉ là không còn nút In nhãn.
	Thủ kho cầm một con tem rách trong tay và không còn đường in lại — mà không
	lỗi nào báo, không log nào ghi.

	Ba bài, ba tầng khác nhau, KHÔNG bài nào thay được bài nào (đúng khuôn
	`TestNutTrenPhieuKho` ở trên): hook có khai báo → file có thật → JS thật sự
	đến được form.
	"""

	def test_doctype_js_gan_vao_batch(self):
		"""Khoá chính dòng trong `doctype_js`.

		`doctype_js` và `doc_events` trong `erpnext/hooks.py` ĐỀU có một khoá
		`"Batch"`, hai dict khác nhau. Một lần giải merge nhầm hai chỗ đó, hoặc
		một khoá `"Batch"` thứ hai thêm vào cùng dict, sẽ nuốt dòng này trong
		im lặng — `doc_events` vẫn chạy nên không có triệu chứng nào khác.
		"""
		gan = frappe.get_hooks("doctype_js").get("Batch") or []
		if isinstance(gan, str):
			gan = [gan]
		self.assertIn(
			DUONG_DAN_JS_LO,
			gan,
			"Form Batch không còn nạp JS của module. Không có nó thì mất nút 'In nhãn' "
			"— đường DUY NHẤT in lại tem cho một lô khi tem rách hoặc thùng bị tách — "
			"mà không lỗi nào báo. Kiểm `doctype_js` trong erpnext/hooks.py.",
		)

	def test_file_js_lo_co_that(self):
		"""`doctype_js` trỏ file không tồn tại thì Frappe im lặng bỏ qua."""
		duong_dan = frappe.get_app_path("erpnext", *DUONG_DAN_JS_LO.split("/"))
		self.assertTrue(os.path.exists(duong_dan), f"thiếu file {duong_dan}")

	def test_ma_nut_in_nhan_thuc_su_den_duoc_form(self):
		"""Đi đúng đường trình duyệt đi, thay vì chỉ tin hook + file có mặt.

		`FormMeta` là lớp thật sự ghép JS gửi xuống; `frappe.get_meta()` thường
		KHÔNG nạp phần này (sẽ ra chuỗi rỗng và tưởng là hỏng).

		Dấu hiệu tìm là chuỗi TIẾNG VIỆT của `batch.js`. `erpnext/stock/doctype/
		batch/batch.js` của upstream cũng được ghép vào cùng `__js` này nhưng
		toàn tiếng Anh, nên không có đường nào cho một dấu hiệu tiếng Việt lọt
		vào từ file khác và cho bài này xanh giả.
		"""
		from frappe.desk.form.meta import get_meta as form_meta

		frappe.clear_cache(doctype="Batch")
		js = form_meta("Batch").as_dict().get("__js") or ""
		for dau_hieu in ("In nhãn", "in_nhan_lo.js"):
			self.assertIn(dau_hieu, js, f"JS gửi xuống form Batch thiếu {dau_hieu!r}")

	def test_file_in_nhan_lo_co_that(self):
		"""`batch.js` và `batch_entry.js` đều `frappe.require` file này lúc BẤM.

		Nó không nằm trong `doctype_js` nên không bài nào ở trên chạm tới. Mất
		nó thì cả hai nút vẫn hiện ra, bấm vào mới hỏng — và hỏng ở đúng lúc thủ
		kho đang cần tem.
		"""
		duong_dan = frappe.get_app_path("erpnext", "public", "js", "warehouse_operations", "in_nhan_lo.js")
		self.assertTrue(os.path.exists(duong_dan), f"thiếu file {duong_dan}")


#: Danh sách TRẮNG những màn hình BẮT BUỘC phải có lối vào trên workspace.
#:
#: Thêm một màn hình vào module mà quên dòng ở đây là quên có chủ đích — dòng
#: này là chỗ duy nhất nói "thứ cần có thì phải có mặt".
MAN_HINH_BAT_BUOC = (
	"Storage Location",
	"Warehouse Location Setup",
	"Location Generator",
	"Item Location Preference",
	"Location Transfer",
	"Batch Entry",
)

#: Hai màn hình thủ kho mở HẰNG NGÀY — phải có LỐI TẮT, không chỉ nằm trong thẻ.
#:
#: Một liên kết nằm trong thẻ là đủ để "vào được", nhưng không đủ cho việc làm
#: mỗi ngày vài chục lần: thủ kho phải mở thẻ ra tìm. Lối tắt là ô bấm ngay ở
#: đầu trang. Hai mức này khác nhau nên khoá bằng hai bài khác nhau.
LOI_TAT_BAT_BUOC = ("Batch Entry", "Location Transfer")


class TestManHinhBatBuocCoMat(FrappeTestCase):
	"""Khẳng định NGƯỢC LẠI với `TestWorkspace`, và đó là cả lý do lớp này tồn tại.

	`test_moi_lien_ket_deu_tro_toi_thu_co_that` khẳng định: "mọi liên kết ĐANG
	CÓ đều trỏ tới thứ có thật". Nó xanh khi danh sách liên kết THIẾU một màn
	hình — thậm chí xanh khi danh sách rỗng. Đó là hai mệnh đề khác nhau:

	    (a) thứ đang có thì phải trỏ đúng   <- TestWorkspace khoá
	    (b) thứ cần có thì phải có mặt      <- lớp này khoá

	Bằng chứng (b) không tự có: `Location Transfer` — phiếu xếp vị trí, màn hình
	thủ kho dùng hằng ngày — KHÔNG có một lối vào nào trên workspace từ lúc dựng
	module cho tới 16/09/2026. Không shortcut, không link, không trong `content`.
	Vào được chỉ bằng cách gõ tên doctype vào thanh tìm kiếm. Suốt thời gian đó
	`test_giao_dien.py` vẫn xanh — đúng khuôn "bài test không khoá thứ nó tưởng
	là đang khoá".

	VÌ SAO PHẢI ĐỌC `content` chứ không chỉ đọc `links`/`shortcuts`: workspace có
	BA cấu trúc song song và cả ba phải khớp nhau. `content` là chuỗi JSON của
	các khối THẬT SỰ VẼ RA TRANG; `links` và `shortcuts` chỉ là kho dữ liệu cho
	các khối đó tra vào. Thêm một dòng vào `links` mà quên khối `card` tương ứng
	trong `content` thì doctype có mặt trong `links`, một bài chỉ đọc `links` sẽ
	xanh, mà trang vẫn KHÔNG hiện gì — đúng con bug cũ, lùi xuống một lớp.
	"""

	def _khoi_ve_ra(self, ws):
		"""Tên các thẻ và lối tắt THẬT SỰ được vẽ ra, lấy từ `content`."""
		khoi = json.loads(ws.content or "[]")
		the = {b["data"]["card_name"] for b in khoi if b.get("type") == "card"}
		loi_tat = {b["data"]["shortcut_name"] for b in khoi if b.get("type") == "shortcut"}
		return the, loi_tat

	def _doctype_trong_the_ve_ra(self, ws, the_ve_ra):
		"""DocType vào được qua một thẻ có vẽ ra.

		Đi theo ranh giới `Card Break` trong danh sách phẳng `links`, đúng cách
		Frappe nhóm chúng.
		"""
		duoc = set()
		the_hien_tai = None
		for l in ws.links:
			if l.type == "Card Break":
				the_hien_tai = l.label
				continue
			if l.link_type == "DocType" and the_hien_tai in the_ve_ra:
				duoc.add(l.link_to)
		return duoc

	def test_moi_man_hinh_bat_buoc_deu_nam_trong_mot_the_ve_ra(self):
		ws = frappe.get_doc("Workspace", TEN_WORKSPACE)
		the_ve_ra, _loi_tat = self._khoi_ve_ra(ws)
		co = self._doctype_trong_the_ve_ra(ws, the_ve_ra)
		thieu = [dt for dt in MAN_HINH_BAT_BUOC if dt not in co]
		self.assertEqual(
			thieu,
			[],
			f"workspace {TEN_WORKSPACE!r} không còn lối vào cho: {thieu}. Màn hình vẫn "
			"chạy, vẫn mở được bằng cách gõ tên vào thanh tìm kiếm — nên KHÔNG có lỗi "
			"nào báo, và người dùng coi như nó không tồn tại. Thêm lại dòng trong "
			"`links` KÈM khối `card` tương ứng trong `content`.",
		)

	def test_hai_man_hinh_hang_ngay_deu_co_loi_tat_ve_ra(self):
		ws = frappe.get_doc("Workspace", TEN_WORKSPACE)
		_the_ve_ra, loi_tat_ve_ra = self._khoi_ve_ra(ws)
		co = {s.link_to for s in ws.shortcuts if s.type == "DocType" and s.label in loi_tat_ve_ra}
		thieu = [dt for dt in LOI_TAT_BAT_BUOC if dt not in co]
		self.assertEqual(
			thieu,
			[],
			f"thiếu lối tắt cho: {thieu}. Đây là hai màn hình mở mỗi ngày — chôn chúng "
			"trong một thẻ là bắt thủ kho tìm, mỗi lần một ít.",
		)

	def test_link_count_khop_so_dong_link_thuc_te(self):
		"""`link_count` sai thì Frappe cắt nhầm danh sách phẳng — im lặng.

		Frappe nhóm `links` bằng cách LẤY `link_count` dòng kế tiếp sau mỗi
		`Card Break`. Thêm một liên kết mà quên tăng số này thì liên kết thừa
		rơi ra ngoài mọi thẻ: nó vẫn nằm trong dữ liệu (nên hai bài trên vẫn
		xanh nếu chúng đọc theo ranh giới `Card Break`) mà trang không vẽ.
		"""
		ws = frappe.get_doc("Workspace", TEN_WORKSPACE)
		lech = []
		khai_bao = None
		nhan = None
		dem = 0
		for l in list(ws.links) + [None]:
			if l is None or l.type == "Card Break":
				if nhan is not None and dem != khai_bao:
					lech.append(f"{nhan}: khai {khai_bao}, đếm được {dem}")
				if l is None:
					break
				nhan, khai_bao, dem = l.label, l.link_count, 0
				continue
			dem += 1
		self.assertEqual(lech, [], f"`link_count` lệch số dòng thật: {lech}")


DUONG_DAN_JS_PHIEU_NHAP = "public/js/warehouse_operations/purchase_receipt.js"
DUONG_DAN_JS_MAT_HANG = "public/js/warehouse_operations/item.js"


class TestLoiVaoTuPhieuNhapVaMatHang(FrappeTestCase):
	"""Hai lối vào chủ đầu tư đòi sau khi thử luồng thật ngày 17/09/2026.

	Phiếu nhập MAT-PRE-2026-00008 được duyệt với số lô gõ tay `17/09/2026`, vì
	phiếu nhập lô không có lối vào nào từ phiếu nhập; và mặt hàng đó chưa từng
	gán vị trí, vì form Item không có chỗ nào để gán. Cả hai lối vào gắn qua
	`doctype_js` — mất một dòng thì form vẫn mở bình thường, chỉ là mất đường
	vào, không lỗi nào báo. Đúng hạng hỏng im lặng mà cả file này sinh ra để bắt.
	"""

	def _gan(self, doctype):
		gan = frappe.get_hooks("doctype_js").get(doctype) or []
		return [gan] if isinstance(gan, str) else gan

	def test_doctype_js_gan_vao_phieu_nhap(self):
		self.assertIn(
			DUONG_DAN_JS_PHIEU_NHAP,
			self._gan("Purchase Receipt"),
			"Phiếu nhập không còn nạp JS của module — mất nút 'Nhập lô & in nhãn', và thủ "
			"kho quay lại gõ số lô thẳng trên phiếu nhập. Kiểm `doctype_js` trong hooks.py.",
		)

	def test_doctype_js_gan_vao_mat_hang(self):
		self.assertIn(
			DUONG_DAN_JS_MAT_HANG,
			self._gan("Item"),
			"Form Item không còn nạp JS của module — mất chỗ gán vị trí cố định. Kiểm "
			"`doctype_js` trong hooks.py.",
		)

	def test_hai_file_js_co_that(self):
		"""`doctype_js` trỏ file không tồn tại thì Frappe im lặng bỏ qua."""
		for tuong_doi in (DUONG_DAN_JS_PHIEU_NHAP, DUONG_DAN_JS_MAT_HANG):
			duong_dan = frappe.get_app_path("erpnext", *tuong_doi.split("/"))
			self.assertTrue(os.path.exists(duong_dan), f"thiếu file {duong_dan}")

	def test_nhan_nut_tren_phieu_nhap_khop_cau_bao_chan_duyet(self):
		"""Câu báo chặn duyệt (`phieu_nhap.chan_lo_go_tay_khi_duyet`) bảo người dùng
		"bấm nút <tên>". Nhãn nút thật nằm trong một file JS khác. Hai chỗ giữ cùng
		một chuỗi mà không gì nối chúng lại — lệch một chữ là thủ kho đi tìm một nút
		không tồn tại, ngay lúc họ đang bị chặn và cần nút đó nhất."""
		from erpnext.warehouse_operations.vitri.phieu_nhap import NHAN_NUT_NHAP_LO

		duong_dan = frappe.get_app_path("erpnext", *DUONG_DAN_JS_PHIEU_NHAP.split("/"))
		with open(duong_dan, encoding="utf-8") as f:
			ma_js = f.read()
		self.assertIn(f'"{NHAN_NUT_NHAP_LO}"', ma_js)


TEN_TRANG_QUET = "quet-ma-tra-cuu"


class TestTrangQuetMa(FrappeTestCase):
	TRANG = TEN_TRANG_QUET
	THU_MUC = "quet_ma_tra_cuu"

	def _vai_tro_may_chu(self):
		from erpnext.warehouse_operations.vitri.quet import VAI_TRO_DUOC_TRA_CUU

		return VAI_TRO_DUOC_TRA_CUU

	"""Trang quét mã tra cứu cho PDA — chủ đầu tư đòi 17/09/2026 "quét mã tra cứu
	là chức năng riêng và ở trong workspace vị trí kho".

	Trang Frappe hỏng theo đúng kiểu cả file này bắt: thiếu dòng `roles` thì
	Stock User mở ra "Not permitted"; thiếu khối trong `content` thì workspace
	không vẽ ô bấm; cả hai đều không lỗi nào báo ở phía máy chủ.
	"""

	def test_trang_ton_tai_thuoc_module(self):
		self.assertEqual(frappe.db.get_value("Page", self.TRANG, "module"), TEN_MODULE)

	def test_dung_ba_vai_tro_duoc_tra_cuu(self):
		"""Khớp `quet.VAI_TRO_DUOC_TRA_CUU` — trang mở được mà máy chủ chặn thì
		thủ kho thấy một trang quét cứ báo lỗi quyền mỗi lần bóp cò."""
		vai_tro = set(frappe.get_all("Has Role", {"parent": self.TRANG, "parenttype": "Page"}, pluck="role"))
		self.assertEqual(vai_tro, self._vai_tro_may_chu())

	def test_co_loi_tat_ve_ra_va_nam_trong_the_hang_ngay(self):
		ws = frappe.get_doc("Workspace", TEN_WORKSPACE)
		khoi = json.loads(ws.content or "[]")
		loi_tat_ve_ra = {b["data"]["shortcut_name"] for b in khoi if b.get("type") == "shortcut"}
		self.assertIn(
			self.TRANG,
			{s.link_to for s in ws.shortcuts if s.type == "Page" and s.label in loi_tat_ve_ra},
		)

		the = None
		trong_the = set()
		for l in ws.links:
			if l.type == "Card Break":
				the = l.label
			elif l.link_type == "Page":
				trong_the.add((the, l.link_to))
		self.assertIn(("Hằng ngày", self.TRANG), trong_the)

	def test_file_trang_co_that(self):
		"""Trang tiêu chuẩn nạp JS/CSS theo ĐÚNG tên file trong thư mục trang —
		đặt sai tên thì trang mở ra trắng trơn."""
		for duoi in ("js", "css"):
			duong_dan = frappe.get_app_path(
				"erpnext", "warehouse_operations", "page", self.THU_MUC, f"{self.THU_MUC}.{duoi}"
			)
			self.assertTrue(os.path.exists(duong_dan), f"thiếu file {duong_dan}")

class TestTrangXepHangPda(TestTrangQuetMa):
	"""Trang xếp hàng trên PDA — chủ đầu tư 17/09/2026 "giao diện xếp hàng cũng là
	pda". Cùng bốn kiểu hỏng im lặng với trang quét mã, nên chạy lại đúng bốn bài
	của lớp cha trên trang này. Vai trò so với `xep.VAI_TRO_DUOC_XEP` — bộ vai trò
	máy chủ thật sự kiểm cho các hàm trang này gọi."""

	TRANG = "xep-hang-pda"
	THU_MUC = "xep_hang_pda"

	def _vai_tro_may_chu(self):
		from erpnext.warehouse_operations.vitri.xep import VAI_TRO_DUOC_XEP

		return VAI_TRO_DUOC_XEP


class TestTrangLayHang(TestTrangQuetMa):
	"""Trang lấy hàng trên PDA (spec 2026-09-18). Cùng bốn kiểu hỏng im lặng với
	hai trang PDA trước: thiếu roles thì Stock User mở ra "Not permitted"; thiếu
	khối trong `content` thì workspace không vẽ ô bấm."""

	TRANG = "lay-hang-pda"
	THU_MUC = "lay_hang_pda"

	def _vai_tro_may_chu(self):
		from erpnext.warehouse_operations.vitri.lay_hang import VAI_TRO_DUOC_LAY

		return VAI_TRO_DUOC_LAY


DUONG_DAN_JS_PHIEU_XEP = "warehouse_operations/doctype/location_transfer/location_transfer.js"
DUONG_DAN_JS_PHIEU_NHAP_LO = "warehouse_operations/doctype/batch_entry/batch_entry.js"
#: Cờ trong trang nối nút "Xếp hàng lên kệ" (phiếu nhập) với chỗ tự đổ dòng
#: (phiếu xếp). Hai file JS khác nhau giữ CÙNG một chuỗi này.
CO_TU_LAY = "tu_lay_hang_chua_xep"


class TestNoiLuongNhapKho(FrappeTestCase):
	"""Các mối nối của luồng nhập kho (23/09/2026): phiếu nhập → phiếu nhập lô →
	duyệt → xếp lên kệ.

	Mọi thứ ở đây đứt theo kiểu KHÔNG ném lỗi — đúng hạng hỏng mà cả file này sinh
	ra để bắt: đổi tên một hàm máy chủ thì nút vẫn vẽ ra, bấm vào mới im; đổi tên
	cờ ở một file thì file kia vẫn chạy, chỉ là không bao giờ tự đổ dòng nữa.
	"""

	def _ma_js(self, tuong_doi):
		with open(frappe.get_app_path("erpnext", *tuong_doi.split("/")), encoding="utf-8") as f:
			return f.read()

	def test_duong_goi_may_chu_co_that_va_duoc_whitelist(self):
		import re

		ma = self._ma_js(DUONG_DAN_JS_PHIEU_NHAP) + self._ma_js(DUONG_DAN_JS_LO)
		duong = set(re.findall(r"erpnext\.warehouse_operations\.vitri\.luong_nhap\.\w+", ma))
		self.assertTrue(duong, "JS không còn gọi `luong_nhap` — mất thanh tiến trình và nút xếp kệ.")
		for d in duong:
			ham = frappe.get_attr(d)
			self.assertIn(
				ham,
				frappe.whitelisted,
				f"{d} không còn `@frappe.whitelist()` — nút bấm vào sẽ im lặng không làm gì.",
			)

	def test_nhan_nut_xep_hang_len_ke(self):
		self.assertIn('"Xếp hàng lên kệ"', self._ma_js(DUONG_DAN_JS_PHIEU_NHAP))

	def test_nut_ve_phieu_nhap_tren_phieu_nhap_lo(self):
		"""Khai lô xong, bước kế tiếp là duyệt phiếu nhập — mất nút này thì thủ kho
		lại phải gõ tên phiếu trên thanh tìm kiếm, đúng điều chủ đầu tư bỏ đi."""
		ma = self._ma_js(DUONG_DAN_JS_PHIEU_NHAP_LO)
		self.assertIn("Duyệt phiếu nhập kho", ma)
		self.assertIn("Xem phiếu nhập kho", ma)

	def test_co_tu_lay_hang_chua_xep_khop_giua_hai_file(self):
		for tuong_doi in (DUONG_DAN_JS_PHIEU_NHAP, DUONG_DAN_JS_PHIEU_XEP):
			self.assertIn(CO_TU_LAY, self._ma_js(tuong_doi), f"{tuong_doi} mất cờ {CO_TU_LAY}")

	def test_ba_file_js_co_that(self):
		for tuong_doi in (DUONG_DAN_JS_PHIEU_XEP, DUONG_DAN_JS_PHIEU_NHAP_LO, DUONG_DAN_JS_LO):
			duong_dan = frappe.get_app_path("erpnext", *tuong_doi.split("/"))
			self.assertTrue(os.path.exists(duong_dan), f"thiếu file {duong_dan}")


DUONG_DAN_JS_THE_PDA = "warehouse_operations/doctype/pda_badge/pda_badge.js"


class TestNutThePda(FrappeTestCase):
	"""Nút cấp/in thẻ PDA. Hỏng theo kiểu im lặng: đổi tên hàm máy chủ thì nút vẫn
	vẽ ra, bấm mới biết; nên khoá cả đường gọi lẫn việc nó còn `@frappe.whitelist`."""

	def _ma_js(self):
		with open(frappe.get_app_path("erpnext", *DUONG_DAN_JS_THE_PDA.split("/")), encoding="utf-8") as f:
			return f.read()

	def test_file_js_co_that(self):
		duong_dan = frappe.get_app_path("erpnext", *DUONG_DAN_JS_THE_PDA.split("/"))
		self.assertTrue(os.path.exists(duong_dan), f"thiếu file {duong_dan}")

	def test_co_hai_nhan_nut(self):
		ma = self._ma_js()
		self.assertIn("Cấp thẻ & in", ma)
		self.assertIn("Thu hồi thẻ", ma)

	def test_duong_goi_may_chu_co_that_va_duoc_whitelist(self):
		import re

		duong = set(re.findall(r"erpnext\.warehouse_operations\.vitri\.the_pda\.\w+", self._ma_js()))
		self.assertTrue(duong, "JS không còn gọi `the_pda` — mất đường cấp thẻ.")
		for d in duong:
			self.assertIn(frappe.get_attr(d), frappe.whitelisted, f"{d} mất @frappe.whitelist()")


class TestTrangPdaHome(FrappeTestCase):
	"""Menu của app PDA. Trang trỏ sai route thì Frappe vẫn dựng trang, bấm vào ra
	trang trắng — đúng hạng hỏng im lặng cả file này sinh ra để bắt."""

	def test_trang_ton_tai_thuoc_module(self):
		self.assertEqual(frappe.db.get_value("Page", "pda-home", "module"), TEN_MODULE)

	def test_dung_ba_vai_tro_kho(self):
		vai_tro = set(frappe.get_all("Has Role", {"parent": "pda-home", "parenttype": "Page"}, pluck="role"))
		self.assertEqual(vai_tro, {"System Manager", "Stock Manager", "Stock User"})

	def test_bon_route_trong_menu_deu_co_that(self):
		import re

		duong_dan = frappe.get_app_path(
			"erpnext", "warehouse_operations", "page", "pda_home", "pda_home.js"
		)
		with open(duong_dan, encoding="utf-8") as f:
			ma_js = f.read()
		route = set(re.findall(r'route:\s*"([a-z0-9-]+)"', ma_js))
		self.assertEqual(
			route, {"xep-hang-pda", "lay-hang-pda", "quet-ma-tra-cuu", "dat-o-hang-loat"}
		)
		for r in route:
			self.assertTrue(frappe.db.exists("Page", r), f"route {r} không có Page nào")


class TestTrangQuetThePda(FrappeTestCase):
	"""`/pda` — cửa vào DUY NHẤT của toàn bộ app PDA, và là trang WEBSITE mở cho khách
	(chưa đăng nhập). Mất trang này là mất cả app, mà tới đợt sửa cuối (23/09/2026) chưa
	có bài test nào canh nó — đúng lỗ hổng mục 6 của đợt sửa cuối vá.

	Ba kiểu hỏng im lặng bắt ở đây: (1) thiếu file thì `/pda` ra 404, không lỗi máy chủ nào
	khác; (2) `pda.html` gọi sai tên hàm máy chủ thì súng quét bắn mã, JS gọi `fetch` tới một
	đường không tồn tại, không có gì báo ngoài "không nối được"; (3) hàm mất
	`@frappe.whitelist` thì mọi lần quét đều bị Frappe chặn ở tầng permission trước khi chạm
	tới logic nghiệp vụ, lại đúng kiểu lỗi im lặng từ phía súng quét."""

	DUONG_DANG_NHAP = "erpnext.warehouse_operations.vitri.the_pda.dang_nhap_bang_the"

	def test_hai_file_pda_ton_tai(self):
		for ten in ("pda.py", "pda.html"):
			duong_dan = frappe.get_app_path("erpnext", "www", ten)
			self.assertTrue(os.path.exists(duong_dan), f"thiếu file {duong_dan}")

	def test_pda_html_goi_dung_duong_dang_nhap_va_ham_con_whitelist(self):
		duong_dan = frappe.get_app_path("erpnext", "www", "pda.html")
		with open(duong_dan, encoding="utf-8") as f:
			html = f.read()
		self.assertIn(
			self.DUONG_DANG_NHAP,
			html,
			f"pda.html không còn gọi đúng {self.DUONG_DANG_NHAP} — súng quét bắn mã vào hư không",
		)
		ham = frappe.get_attr(self.DUONG_DANG_NHAP)
		self.assertIn(
			ham, frappe.whitelisted, f"{self.DUONG_DANG_NHAP} mất @frappe.whitelist() — mọi lần quét bị chặn"
		)

	def test_pda_py_khong_cache(self):
		import erpnext.www.pda as trang_pda

		self.assertEqual(
			getattr(trang_pda, "no_cache", None),
			1,
			"thiếu `no_cache = 1` thì trang có thể bị cache lại phiên bản cũ/của người khác",
		)

	def test_pda_py_dieu_huong_nguoi_da_dang_nhap_sang_pda_home(self):
		"""Đi đúng đường trình duyệt đi (gọi thẳng `get_context`), không chỉ đọc mã nguồn:
		người ĐÃ đăng nhập mở `/pda` phải bị đá thẳng sang `/app/pda-home`, không phải thấy
		lại màn quét thẻ — quét thẻ hai lần khi đã có phiên là một trải nghiệm vô nghĩa."""
		import erpnext.www.pda as trang_pda

		frappe.set_user("Administrator")
		try:
			with self.assertRaises(frappe.Redirect):
				trang_pda.get_context({})
			self.assertEqual(frappe.local.flags.redirect_location, "/app/pda-home")
		finally:
			frappe.local.flags.redirect_location = None


class TestLoiVaoCaiAppPda(FrappeTestCase):
	"""Lối vào phần cài app PDA trong workspace, và trang tải bản cài.

	Hai thứ ở đây hỏng theo kiểu IM LẶNG, đúng hạng mà cả file này sinh ra để bắt:
	lối tắt trỏ sai tên thì workspace vẫn vẽ ra, bấm vào mới ra trang trắng; còn
	trang tải (`/tai-app`) mà mất thì máy quét mới không có đường nào lấy bản cài —
	lỗi chỉ lộ ra khi đứng giữa kho với một chiếc PDA trắng tay.
	"""

	def test_moi_loi_tat_va_the_deu_nam_trong_BO_CUC(self):
		"""Thêm dòng vào `shortcuts`/`links` là CHƯA ĐỦ — trang vẽ theo trường
		`content` (bố cục). Thiếu khối trong đó thì dữ liệu vẫn nằm trong CSDL mà
		màn hình trống trơn, và mọi bài test chỉ đọc bảng con đều xanh.

		Đã dính đúng bẫy này ngày 23/09/2026: lối tắt Thẻ PDA / Cài app PDA và thẻ
		App PDA có đủ trong bảng con, test xanh, mà workspace không hiện gì. Bài này
		soi CẢ HAI CHIỀU nên không lặp lại được.
		"""
		import json

		ws = frappe.get_doc("Workspace", TEN_WORKSPACE)
		khoi = json.loads(ws.content or "[]")
		bo_cuc_loi_tat = {k["data"]["shortcut_name"] for k in khoi if k.get("type") == "shortcut"}
		bo_cuc_the = {k["data"]["card_name"] for k in khoi if k.get("type") == "card"}
		du_lieu_loi_tat = {s.label for s in ws.shortcuts}
		du_lieu_the = {l.label for l in ws.links if l.type == "Card Break"}

		self.assertEqual(
			du_lieu_loi_tat - bo_cuc_loi_tat,
			set(),
			"lối tắt có trong dữ liệu nhưng KHÔNG có khối trong bố cục -> không hiện ra",
		)
		self.assertEqual(
			bo_cuc_loi_tat - du_lieu_loi_tat,
			set(),
			"bố cục trỏ tới lối tắt không tồn tại -> ô trống trên trang",
		)
		self.assertEqual(
			du_lieu_the - bo_cuc_the, set(), "thẻ có trong dữ liệu nhưng không có khối trong bố cục"
		)
		self.assertEqual(
			bo_cuc_the - du_lieu_the, set(), "bố cục trỏ tới thẻ không tồn tại"
		)

	def test_loi_tat_va_link_app_pda_co_trong_workspace(self):
		ws = frappe.get_doc("Workspace", TEN_WORKSPACE)
		loi_tat = {(s.label, s.type, s.link_to) for s in ws.shortcuts}
		self.assertIn(("Thẻ PDA", "DocType", "PDA Badge"), loi_tat)
		self.assertIn(("Cài app PDA", "Page", "cai-app-pda"), loi_tat)
		link = {(l.label, l.link_type, l.link_to) for l in ws.links if l.type == "Link"}
		self.assertIn(("Cài app PDA", "Page", "cai-app-pda"), link)
		self.assertIn(("Màn hình PDA", "Page", "pda-home"), link)

	def test_trang_cai_app_thuoc_module_va_chi_truong_kho(self):
		self.assertEqual(frappe.db.get_value("Page", "cai-app-pda", "module"), TEN_MODULE)
		vai_tro = set(frappe.get_all("Has Role", filters={"parent": "cai-app-pda"}, pluck="role"))
		self.assertEqual(
			vai_tro,
			{"System Manager", "Stock Manager"},
			"Cài app là việc của trưởng kho; thủ kho chỉ quét thẻ — đừng mở rộng vai trò ở đây.",
		)

	def test_trang_tai_app_ton_tai_va_cho_khach(self):
		"""`/tai-app` PHẢI mở được khi chưa đăng nhập: máy PDA chưa cài app thì chưa
		có phiên nào. Mất `allow_guest` là mất luôn cả đường cài."""
		# `frappe.get_app_path` đi qua đường module Python nên nó biến "tai-app"
		# thành "tai_app" — ghép tay để trỏ đúng thư mục thật.
		goc = frappe.get_app_path("erpnext")
		for ten in ("index.py", "index.html"):
			duong_dan = os.path.join(goc, "www", "tai-app", ten)
			self.assertTrue(os.path.exists(duong_dan), f"thiếu file {duong_dan}")
		from erpnext.warehouse_operations.vitri.cai_app import ban_cai_moi_nhat

		self.assertIn(ban_cai_moi_nhat, frappe.whitelisted)
		self.assertIn(
			ban_cai_moi_nhat,
			frappe.guest_methods,
			"Mất `allow_guest` là máy PDA chưa đăng nhập không xem được bản cài nào.",
		)

	def test_duong_tai_ban_cai_KHONG_di_qua_file_tinh(self):
		"""Máy quét trong kho chỉ vào được bằng ĐỊA CHỈ IP, mà đường `/files/...` hỏng
		đúng ở đường đó trên bench này: thư mục site theo IP là liên kết mềm, còn
		`StaticDataMiddleware` giải liên kết rồi so với thư mục chưa giải nên ném
		NotFound (đo 23/09/2026: vào bằng tên miền tải được, vào bằng IP lỗi 500).

		Nên đường tải PHẢI là một lời gọi của ứng dụng. Bài này khoá đúng điều đó —
		trả `/files/...` về là hỏng cho mọi máy quét trong kho.
		"""
		from erpnext.warehouse_operations.vitri.cai_app import _ban_moi_nhat, tai_ban_cai

		self.assertIn(tai_ban_cai, frappe.whitelisted)
		self.assertIn(
			tai_ban_cai,
			frappe.guest_methods,
			"Máy quét chưa cài app thì chưa đăng nhập được — mất allow_guest là mất đường cài.",
		)
		ban = _ban_moi_nhat()
		if ban:
			self.assertFalse(
				ban["duong_dan"].startswith("/files/"),
				f"đường tải đang trỏ file tĩnh ({ban['duong_dan']}) — máy quét vào bằng IP sẽ hỏng",
			)
			self.assertIn("tai_ban_cai", ban["duong_dan"])

	def test_js_trang_cai_app_goi_dung_ham_may_chu(self):
		import re

		duong_dan = frappe.get_app_path(
			"erpnext", "warehouse_operations", "page", "cai_app_pda", "cai_app_pda.js"
		)
		with open(duong_dan, encoding="utf-8") as f:
			ma_js = f.read()
		duong = set(re.findall(r"erpnext\.warehouse_operations\.vitri\.cai_app\.\w+", ma_js))
		self.assertTrue(duong, "JS không còn gọi `cai_app` — mất phần xem bản đang phát hành.")
		for d in duong:
			self.assertIn(frappe.get_attr(d), frappe.whitelisted, f"{d} mất @frappe.whitelist()")


class TestVoAppKho(FrappeTestCase):
	"""Vỏ app PDA tại `/kho`. Hỏng ở đây là máy quét không mở nổi màn nào —
	nhưng hỏng IM LẶNG: route mất thì Frappe trả 404, không ai được báo."""

	def _doc(self, *duong_dan):
		# `frappe.get_app_path("erpnext")` trả `<bench>/apps/erpnext/erpnext` —
		# tức thư mục GÓI, không phải gốc kho. Mọi đường dẫn dưới đây tính từ đó.
		return os.path.join(frappe.get_app_path("erpnext"), *duong_dan)

	@staticmethod
	def _bo_chu_thich_giu_chuoi(ma):
		"""Chỉ xoá chú thích (`//...`, `/*...*/`), GIỮ NGUYÊN chuỗi — NGƯỢC với
		`_bo_chu_thich_va_chuoi` bên dưới (hàm đó xoá LUÔN chuỗi, dùng để đếm độ
		sâu ngoặc an toàn). Ở đây cần ngược lại: một dòng CHÚ THÍCH nhắc "/kho"
		(rất nhiều trong các file này, kể cả chú thích do chính đợt sửa Task 6
		viết) không được giả làm dòng MÃ THẬT trỏ "/kho" — nhưng chuỗi `"/kho"`
		trong mã thật thì phải giữ, vì đó chính là thứ cần đọc."""
		ra = []
		i, n = 0, len(ma)
		trong_chuoi = None
		while i < n:
			if trong_chuoi:
				ra.append(ma[i])
				if ma[i] == "\\" and i + 1 < n:
					ra.append(ma[i + 1])
					i += 2
					continue
				if ma[i] == trong_chuoi:
					trong_chuoi = None
				i += 1
				continue
			hai = ma[i : i + 2]
			if hai == "//":
				j = ma.find("\n", i)
				j = n if j == -1 else j
				ra.append(" " * (j - i))
				i = j
				continue
			if hai == "/*":
				j = ma.find("*/", i + 2)
				j = n if j == -1 else j + 2
				ra.append(" " * (j - i))
				i = j
				continue
			if ma[i] in "\"'`":
				trong_chuoi = ma[i]
			ra.append(ma[i])
			i += 1
		return "".join(ra)

	def _than_ham(self, ma, chu_ky):
		"""Trích thân một hàm/phương thức (giữa `{`...`}` khớp cặp), tìm bằng
		`chu_ky` (ví dụ `"function di(u)"`). Đếm ngoặc trên bản đã bỏ chú thích
		VÀ chuỗi (an toàn — một dấu `{`/`}` nằm trong chuỗi HTML không làm lệch
		phép đếm), rồi cắt CÙNG khoảng chỉ số đó trên bản chỉ-bỏ-chú-thích (giữ
		chuỗi) để lấy nội dung THẬT — hai bản luôn CÙNG ĐỘ DÀI vì chú thích/chuỗi
		bị thay bằng khoảng trắng cùng số ký tự, không cắt bớt gì."""
		sach_do_sau = self._bo_chu_thich_va_chuoi(ma)
		sach_giu_chuoi = self._bo_chu_thich_giu_chuoi(ma)
		self.assertEqual(len(sach_do_sau), len(sach_giu_chuoi))
		i = sach_do_sau.index(chu_ky)
		mo = sach_do_sau.index("{", i)
		do_sau = 0
		j = mo
		while j < len(sach_do_sau):
			if sach_do_sau[j] == "{":
				do_sau += 1
			elif sach_do_sau[j] == "}":
				do_sau -= 1
				if do_sau == 0:
					return sach_giu_chuoi[mo + 1 : j]
			j += 1
		raise AssertionError(f"không tìm thấy thân hàm khớp cặp cho {chu_ky!r}")

	def test_vo_app_nap_giao_dien_trong_may(self):
		"""`www/index.html` là VỎ TĨNH nạp giao diện ĐÃ ĐÓNG GÓI, không phải một
		trang tự điều hướng WebView sang máy chủ.

		ĐỔI TIỀN ĐỀ 24/09/2026 (spec `app-pda-giao-dien-trong-may`, Task 1): bản
		trước của bài này đọc thân hàm `di(u)` trong `index.html` và đòi nó chạy
		`window.location.href = u + "/kho"`. Hàm đó KHÔNG CÒN — giao diện nằm
		trong máy nên không có cú nhảy sang máy chủ nào để kiểm nữa. Thứ phải khoá
		bây giờ là bốn thẻ `<script>` đúng THỨ TỰ: `cau-hinh.js` (địa chỉ máy chủ)
		→ jQuery → `shim.js` (các toàn cục Frappe) → `kho_pda.bundle.js`. Đảo
		`shim.js` xuống sau bundle là `frappe is not defined` ngay lúc tải, một màn
		trắng không lời giải thích.

		Bài này CỐ Ý không kiểm `kho_pda.bundle.js`/`cau-hinh.js` có mặt trên đĩa:
		cả hai do `scripts/pda/dong-goi.sh` sinh và bị `.gitignore`, nên trên một
		bản checkout sạch chúng vắng mặt một cách hợp lệ. Việc chứng minh bốn màn
		dựng được từ bản đóng gói thật là của cổng
		`scripts/kiem_giao_dien/kiem_ban_dong_goi.js` (chạy trong trình duyệt);
		bài tĩnh này chỉ khoá phần khai báo."""
		goc = frappe.get_app_path("erpnext").rsplit("/erpnext", 1)[0]
		with open(os.path.join(goc, "pda_app", "www", "index.html"), encoding="utf-8") as f:
			ma = f.read()

		self.assertIn(
			"window.KHO_LA_APP = true",
			ma,
			"vỏ app không còn khai KHO_LA_APP — cùng một bundle phục vụ cả /kho trên "
			"web lẫn app, nó phân biệt hai nơi bằng đúng cờ này.",
		)

		thu_tu = ["cau-hinh.js", "vendor/jquery.min.js", "shim.js", "kho_pda.bundle.js"]
		vi_tri = []
		for ten in thu_tu:
			the = f'<script src="{ten}"></script>'
			self.assertIn(the, ma, f"vỏ app thiếu thẻ nạp {ten}")
			vi_tri.append(ma.index(the))
		self.assertEqual(
			vi_tri,
			sorted(vi_tri),
			f"thứ tự thẻ <script> trong www/index.html sai — phải đúng {thu_tu}. "
			"shim.js phải đứng TRƯỚC kho_pda.bundle.js: bundle gọi frappe.provide() "
			"ngay dòng đầu mỗi file.",
		)

		# Không còn màn khai địa chỉ máy chủ trong luồng thường (quyết định §2 của
		# spec). Kiểm bằng dấu vết của bản cũ: hằng `MAC_DINH` và khoá localStorage.
		self.assertNotIn("MAC_DINH", ma)
		self.assertNotIn("pda_may_chu", ma)

	def _ma_main_activity(self):
		goc = frappe.get_app_path("erpnext").rsplit("/erpnext", 1)[0]
		duong_dan = os.path.join(
			goc, "pda_app", "android", "app", "src", "main", "java", "vn", "com",
			"miyano", "pda", "MainActivity.java"
		)
		with open(duong_dan, encoding="utf-8") as f:
			return f.read()

	def _cau_hinh_capacitor(self):
		goc = frappe.get_app_path("erpnext").rsplit("/erpnext", 1)[0]
		with open(os.path.join(goc, "pda_app", "capacitor.config.json"), encoding="utf-8") as f:
			return json.load(f)

	def test_vo_app_khong_con_bat_dieu_huong(self):
		"""TASK 2B — phía Java KHÔNG còn bắt điều hướng nào.

		Đời cũ của app mở trang web của máy chủ trong WebView, nên phải chặn lượt
		Desk đá sang `/login` khi hết phiên. App đời mới không rời
		`file:///android_asset/public/index.html`: giao diện nằm trong máy, lời gọi
		máy chủ đi bằng `fetch` qua cầu native, 401/403 do `vo.js::goi()` xử lý ngay
		trong trang. Một `shouldOverrideUrlLoading` còn sót lại là một đoạn mã NÓI
		DỐI về cách app chạy — người đọc sau sẽ tin app vẫn mở trang của máy chủ.

		ĐỌC BẢN ĐÃ BỎ CHÚ THÍCH (bài cũ `test_vo_app_tro_vao_kho` từng xanh oan vì
		so khớp toàn văn file, mà 5/6 lần xuất hiện `/kho` nằm trong Javadoc): chú
		thích ở file này CỐ Ý còn kể lại chuyện `/login` để giải thích vì sao nó đã
		bị bỏ, nên phép kiểm phải nhìn đúng phần MÃ CHẠY."""
		ma = self._bo_chu_thich_va_chuoi(self._ma_main_activity())
		for dau_vet in ("shouldOverrideUrlLoading", "laDuongDangNhap", "dieuHuongVeQuetThe", "loadUrl"):
			self.assertNotIn(
				dau_vet,
				ma,
				f"MainActivity.java còn `{dau_vet}` trong phần MÃ CHẠY — app đời mới "
				"không điều hướng WebView ra khỏi index.html nữa (Task 2B).",
			)

	def test_vo_app_xoa_sach_cookie_luc_khoi_dong(self):
		"""TASK 3 — vỏ app phải xoá SẠCH kho cookie của WebView mỗi lần mở.

		Nguy hiểm không phải "hai danh tính chọn nhầm" (Frappe chạy `validate_auth()`
		SAU khi phiên cookie đã dựng, nên có khoá thì khoá thắng) mà là ca NGƯỢC LẠI:
		**chưa có khoá mà cookie cũ vẫn đăng nhập được**. Đó là trạng thái của mọi máy
		sau `KhoApp.xoa_khoa()` và của mọi máy nâng cấp tại chỗ từ APK đời cũ — một
		`sid` sống sót sẽ CHE MẤT trạng thái "chưa cấp quyền" mà cả Task 3 dựa vào.

		Đòi đúng ba thứ, và cả ba đều là những chỗ đã đọc mã Capacitor mới biết:
		- `removeAllCookies`, KHÔNG phải `removeSessionCookies`: `sid` của Frappe có
		  `max_age` (`frappe/auth.py:385`) nên là cookie CÓ HẠN, sống sót lời gọi kia —
		  mà `CapacitorCookies.load()` đã tự gọi `removeSessionCookies()` rồi, nên viết
		  lại nó ở đây là viết một dòng không làm gì.
		- `flush()`: không có nó thì bản xoá chỉ nằm trong bộ nhớ, chưa xuống đĩa.
		- gọi SAU `super.onCreate(...)`: `CookieManager.getInstance()` nạp WebView hệ
		  thống nên ném trên máy không có WebView, và ném trước `super.onCreate()` là
		  cướp mất màn `no_webview` mà `BridgeActivity` dựng cho đúng chiếc máy đó.

		Đọc BẢN ĐÃ BỎ CHÚ THÍCH: Javadoc của hàm này cố ý nhắc lại cả `isEnabled` lẫn
		`removeSessionCookies` để kể vì sao chúng bị loại — đếm chuỗi con trên toàn
		file sẽ xanh oan."""
		ma = self._ma_main_activity()
		than = self._than_ham(ma, "public void onCreate(Bundle savedInstanceState)")
		self.assertIn(
			"xoaSachCookie()",
			than,
			"onCreate phải gọi xoaSachCookie() — thiếu nó thì `sid` đời cũ vẫn đăng nhập được.",
		)
		vi_tri_super = than.index("super.onCreate(")
		self.assertGreater(
			than.index("xoaSachCookie()"),
			vi_tri_super,
			"xoaSachCookie() phải đứng SAU super.onCreate(...) — trước nó là cướp mất "
			"màn no_webview trên máy không có WebView hệ thống.",
		)
		than_xoa = self._than_ham(ma, "private void xoaSachCookie()")
		self.assertIn("removeAllCookies", than_xoa)
		self.assertNotIn(
			"removeSessionCookies",
			than_xoa,
			"`sid` của Frappe có max_age nên KHÔNG phải cookie phiên — removeSessionCookies "
			"không xoá được nó, và CapacitorCookies.load() đã gọi sẵn rồi.",
		)
		self.assertIn("flush()", than_xoa, "thiếu flush() thì bản xoá chưa xuống đĩa.")

	def test_vo_app_van_chan_vong_lap_errorPath(self):
		"""Ghi đè `onReceivedHttpError` PHẢI còn, và thân nó PHẢI rỗng.

		`server.errorPath` vẫn được khai trong `capacitor.config.json` (màn lỗi mạng
		có nút "Thử lại"), và `BridgeWebViewClient` dùng CHUNG nhánh errorPath cho cả
		lỗi mạng lẫn lỗi HTTP — với lỗi HTTP thì máy chủ vẫn ping được, nên nạp lại
		errorPath sinh một vòng lặp vô hạn. Bỏ ghi đè này (hoặc gọi `super`) là dựng
		lại đúng vòng lặp đó."""
		ma = self._ma_main_activity()
		than = self._than_ham(
			ma,
			"public void onReceivedHttpError(WebView view, WebResourceRequest request, "
			"WebResourceResponse errorResponse)",
		)
		self.assertEqual(
			than.strip(),
			"",
			"thân onReceivedHttpError phải RỖNG — bất kỳ lệnh nào ở đây (nhất là "
			"super.onReceivedHttpError) dựng lại vòng lặp errorPath vô hạn.",
		)

	def test_cau_hinh_capacitor_bat_cau_http_native(self):
		"""TASK 2B — `CapacitorHttp` BẬT, và hai khoá của đời cũ đã dọn.

		`CapacitorHttp` vá `fetch`/`XMLHttpRequest` để đi qua tầng native của Android
		nên lời gọi KHÔNG dính luật cùng-nguồn của WebView — đó là lý do không phải
		mở `allow_cors` trên máy chủ (spec §3). Tắt nó đi là app chết câm với
		`net::ERR_FAILED` ở mọi lời gọi, và không một bài JS nào trong kho bắt được
		vì cả hai cổng Playwright đều chạy trong một trình duyệt thường.

		`server.allowNavigation` và `android.allowMixedContent` phải KHÔNG còn: cái
		thứ nhất là hàng rào cho một lượt điều hướng không còn xảy ra; cái thứ hai là
		luật của trình duyệt cho nội dung nạp vào TRANG, trong khi lời gọi native đi
		bằng `HttpURLConnection` ở tầng Java — nơi quyết định là
		`res/xml/network_security_config.xml`. Để lại cả hai là để lại hai lời khai
		sai về cách app nối mạng."""
		cau_hinh = self._cau_hinh_capacitor()
		self.assertIs(
			cau_hinh.get("plugins", {}).get("CapacitorHttp", {}).get("enabled"),
			True,
			"capacitor.config.json chưa bật CapacitorHttp — mọi lời gọi máy chủ từ "
			"app sẽ đi qua WebView và bị luật cùng-nguồn chặn.",
		)
		self.assertNotIn("allowNavigation", cau_hinh.get("server", {}))
		self.assertNotIn("allowMixedContent", cau_hinh.get("android", {}))
		self.assertEqual(
			cau_hinh.get("server", {}).get("errorPath"),
			"index.html",
			"bỏ errorPath là bỏ màn lỗi mạng có nút 'Thử lại' (spec §4).",
		)

	def test_cau_loi_html_khong_ra_man_hinh(self):
		"""`_cau_loi_may_chu` phải CHẶN câu HTML, không phải chặn mã 403.

		Frappe nhét nguyên một khối HTML tiếng Anh vào `_server_messages` cho lỗi
		quyền; trong app MỌI lời gọi rơi vào ca đó cho tới khi Task 3 cấp khoá. Bài
		này đọc ĐÚNG thân hàm (bỏ chú thích) và đòi hai thứ: một phép thử dấu vết
		HTML, và một `console.warn` để câu thật vẫn tới tay người gỡ lỗi.

		KIỂU RULING 2 — không đếm chuỗi con trong toàn file: cả ba dấu hiệu đều có
		mặt dày đặc trong chú thích của chính hàm đó."""
		ma = self._ma_kho_pda("vo.js")
		than = self._than_ham(ma, "function _cau_loi_may_chu(than, ma, la_app)")
		self.assertIn(
			"console.warn",
			than,
			"_cau_loi_may_chu nuốt câu lỗi HTML mà không ghi lại — người gỡ lỗi mất "
			"chẩn đoán thật ('Function X is not whitelisted').",
		)
		self.assertRegex(
			than,
			r"/<\[[^]]+\]/\.test\(",
			"_cau_loi_may_chu phải nhận diện câu lỗi bằng DẤU VẾT HTML (một biểu thức "
			"chính quy trên `<`), không bằng mã lỗi — đây là một LỚP lỗi (403, 500 "
			"HTML, câu nghiệp vụ có thẻ), không phải một ca.",
		)
		self.assertIn(
			'"</"',
			than,
			"thiếu phép đo thẻ ĐÓNG — một câu chỉ còn `</p>` vẫn là markup.",
		)
		than_thay = self._than_ham(ma, "function _cau_loi_thay_the(ma, la_app)")
		self.assertIn(
			"la_app",
			than_thay,
			"câu thay thế cho 401/403 phải phân biệt app với web: trên web `/kho` "
			"không có khái niệm 'khoá máy', nói 'báo trưởng kho cấp khoá' là sai "
			"người dùng — và đường web không được đổi một chữ nào.",
		)

	def test_hai_file_trang_ton_tai(self):
		for ten in ("index.py", "index.html"):
			duong_dan = self._doc("www", "kho", ten)
			self.assertTrue(os.path.exists(duong_dan), f"thiếu {duong_dan}")

	def test_trang_cho_khach_va_khong_dem(self):
		"""Máy quét chưa đăng nhập phải mở được `/kho` (nó tự hiện màn quét thẻ),
		và trang KHÔNG được đệm: Desk đệm mã trang vào localStorage tới 2 ngày —
		đúng lỗi 'header lúc ẩn lúc hiện' ngày 23/09; trang web phải tránh."""
		with open(self._doc("www", "kho", "index.py"), encoding="utf-8") as f:
			ma = f.read()
		self.assertIn("no_cache = 1", ma)

		# `no_cache = 1` chỉ khoá lớp đệm trình duyệt — không khoá được kiểu hỏng
		# khác: một `frappe.Redirect` ném trong `get_context` (kiểu `www/pda.py` làm
		# cho người ĐÃ đăng nhập) cũng chặn đúng khách ra khỏi `/kho`, mà không dòng
		# `grep` nào ở trên bắt được (soát xét vòng 1: "docstring hứa kiểm quyền
		# khách nhưng chỉ grep `no_cache = 1`"). Gọi thẳng `get_context` với phiên
		# Khách để khoá luôn cả hai vế lời hứa của docstring.
		import importlib

		trang = importlib.import_module("erpnext.www.kho.index")
		with self.set_user("Guest"):
			context = frappe._dict()
			# Không được ném ngoại lệ nào (đặc biệt `frappe.Redirect`) cho khách.
			trang.get_context(context)
		self.assertTrue(context.la_khach, "context.la_khach phải True khi Khách mở /kho")
		self.assertEqual(context.nguoi_dung, "", "Khách không có tên người dùng để lộ ra HTML")

		with self.set_user("Administrator"):
			context = frappe._dict()
			trang.get_context(context)
		self.assertFalse(context.la_khach, "Administrator không phải khách")
		self.assertEqual(context.nguoi_dung, "Administrator")

	def test_bundle_duoc_nhung_bang_include_script(self):
		"""Nhúng thẳng `/assets/...js` là dính đệm trình duyệt. `include_script`
		trả tên file mang băm nội dung nên bản mới tới máy quét ngay."""
		with open(self._doc("www", "kho", "index.html"), encoding="utf-8") as f:
			html = f.read()
		self.assertIn("include_script('kho_pda.bundle.js')", html)
		self.assertIn("include_style('kho_pda.bundle.css')", html)

		# Hai dòng `assertIn` ở trên chỉ kiểm CHUỖI CON — không phân biệt được
		# `include_script` nằm trong `{% block content %}` hay `{% block script %}`
		# của `templates/base.html`. Khác biệt đó KHÔNG vô hại: `content` đứng
		# TRƯỚC khối nạp `frappe-web.bundle.js` (định nghĩa `frappe.provide`), còn
		# `script` đứng SAU — đặt nhầm khối thì `frappe.provide("erpnext.kho_pda")`
		# ở đầu mỗi file trong bundle ném lỗi ngay khi tải trang (soát xét vòng 1:
		# "quyết định mong manh nhất của Task không có gì khoá lại"). Khoá bằng
		# cách đọc đúng thân từng khối, không chỉ tìm chuỗi con trên cả file.
		def than_khoi(ten_khoi):
			khoi = f"{{% block {ten_khoi} %}}"
			dong = html.index(khoi)
			ket = html.index("{% endblock %}", dong)
			return html[dong:ket]

		self.assertNotIn(
			"include_script(",
			than_khoi("content"),
			"include_script trong block content chạy TRƯỚC frappe-web.bundle.js — vỡ trang",
		)
		self.assertIn("include_script('kho_pda.bundle.js')", than_khoi("script"))

	def test_vo_khong_dung_api_cua_desk(self):
		"""Vỏ chạy ngoài Desk: gọi `frappe.ui.Dialog`/`frappe.ui.Scanner`/
		`frappe.set_route`/`msgprint` là lỗi lúc chạy, mà chỉ lộ khi thủ kho bấm
		đúng nút đó ngoài kho. `frappe.ui.Scanner` (máy ảnh) nằm trong ràng buộc
		toàn cục của Task 1 (spec §9, ngoài phạm vi) nhưng ban đầu KHÔNG có trong
		regex cấm — soát xét vòng 1 bắt được lỗ hổng này."""
		import re

		thu_muc = self._doc("public", "js", "kho_pda")
		cam = re.compile(r"frappe\.(ui\.Dialog|ui\.Scanner|set_route|msgprint|show_alert)")
		for ten in os.listdir(thu_muc):
			if not ten.endswith(".js"):
				continue
			with open(os.path.join(thu_muc, ten), encoding="utf-8") as f:
				ma = f.read()
			self.assertIsNone(cam.search(ma), f"{ten} còn gọi API của Desk")

	def test_hop_thoai_khong_bat_phim_nao(self):
		"""Súng quét gửi Enter sau mỗi lần bắn. Một hộp thoại bắt Enter từng làm
		DUYỆT NHẦM một phiếu thật (17/09/2026).

		Đo CÁCH GẮN SỰ KIỆN, không đo chữ "Enter" trong file: chú thích giải thích
		vì sao phải tránh Enter đương nhiên có chữ đó, mà chú thích không gây hại —
		thứ gây hại là một trình nghe bàn phím."""
		import re

		with open(self._doc("public", "js", "kho_pda", "hop_thoai.js"), encoding="utf-8") as f:
			ma = f.read()
		nghe_phim = re.compile(r"""(on|addEventListener)\s*\(\s*["']key(down|press|up)""")
		self.assertIsNone(nghe_phim.search(ma), "hộp thoại không được nghe bàn phím")

	def test_luong_khong_dung_dom_va_api_cua_desk(self):
		"""Task 2 vòng sửa 1 (soát xét `task-2-soat-xet.md`, P9): `test_vo_khong_dung_api_cua_desk`
		ở trên chỉ quét `public/js/kho_pda/` — KHÔNG quét
		`public/js/warehouse_operations/luong/`, nơi lớp LUỒNG dùng chung của Task
		2–5 sống. Trước bài này, ràng buộc "lớp luồng không đụng DOM, không gọi API
		Desk" (điều kiện để `node --test` chạy được nó — xem docstring
		`luong/tra_cuu.js`) chỉ sống trong đầu người viết cộng một lưới an toàn TÌNH
		CỜ của Node (Node ném `ReferenceError` nếu lỡ đụng `document`/`window`,
		nhưng chỉ nếu đúng NHÁNH đó được `node --test` chạy tới — không phải mọi
		dòng chết đều nằm trên một nhánh có bài test).

		Cấm CẢ DOM (`document.`/`window.`/`$(`/`jQuery`) LẪN API riêng của Desk
		(`frappe.ui.`/`frappe.set_route`/`frappe.msgprint`/`frappe.show_alert`) —
		KHÔNG cấm `frappe.provide`/`typeof frappe`: đó là đuôi hai môi trường CỐ Ý
		của lớp luồng (xem cuối `luong/tra_cuu.js`), không phải API riêng của Desk.
		Bỏ qua `*.test.js` — bài test của lớp luồng chạy trong Node, không phải thứ
		bài này khoá."""
		import re

		thu_muc = self._doc("public", "js", "warehouse_operations", "luong")
		cam = re.compile(r"document\.|window\.|\$\(|jQuery|frappe\.ui\.|frappe\.set_route|frappe\.msgprint|frappe\.show_alert")
		for ten in os.listdir(thu_muc):
			if not ten.endswith(".js") or ten.endswith(".test.js"):
				continue
			with open(os.path.join(thu_muc, ten), encoding="utf-8") as f:
				ma = f.read()
			self.assertIsNone(cam.search(ma), f"{ten} còn DOM/API Desk trong lớp luồng")

	# -------------------------------------- Task 2 (đợt "giao diện trong máy"): lớp gọi mạng
	#
	# MỖI BÀI DƯỚI ĐÂY ĐỌC ĐÚNG THÂN HÀM, KHÔNG GREP TOÀN VĂN FILE. Lý do đã trả
	# giá một lần ngay trong file này: bản đầu của `test_vo_app_tro_vao_kho` chỉ
	# `assertIn('"/kho"', ma)` và vẫn XANH khi người soát đổi đúng dòng điều hướng,
	# vì 5 trong 6 lần chữ `/kho` xuất hiện là trong chú thích. Các bài Task 2 nói
	# về những thứ CHẮC CHẮN được nhắc dày đặc trong chú thích (`KHO_MAY_CHU`,
	# `Authorization`, `location.origin`, `csrf`), nên một phép `assertIn` trên
	# toàn văn ở đây là một cái cổng KHÔNG CÓ RĂNG, không phải một bài test.
	#
	# Bài đo HÀNH VI thật (lời gọi đi tới đâu, mang header gì, ở CẢ HAI môi trường)
	# là `scripts/kiem_giao_dien/kiem_goi_mang.js` — chạy trình duyệt thật với một
	# máy chủ HTTP thật ở 127.0.0.1. Các bài tĩnh dưới đây khoá phần khai báo để
	# một lượt sửa lạc tay đỏ ngay ở `bench run-tests`, không phải chờ ai nhớ chạy
	# cổng Playwright.

	def _ma_kho_pda(self, ten_tep):
		with open(self._doc("public", "js", "kho_pda", ten_tep), encoding="utf-8") as f:
			return f.read()

	@staticmethod
	def _dieu_kien_if(than):
		"""Mọi điều kiện `if (...)` trong `than`, cắt bằng phép KHỚP CẶP NGOẶC.

		Không dùng regex một dòng: prettier có quyền ngắt một điều kiện dài xuống
		nhiều dòng bất cứ lúc nào, và một bài test đỏ vì xuống dòng là một bài test
		sẽ bị ai đó gỡ."""
		ra = []
		i = than.find("if (")
		while i != -1:
			j = than.index("(", i)
			do_sau = 0
			k = j
			while k < len(than):
				if than[k] == "(":
					do_sau += 1
				elif than[k] == ")":
					do_sau -= 1
					if do_sau == 0:
						ra.append(than[j + 1 : k])
						break
				k += 1
			i = than.find("if (", k + 1)
		return ra

	def test_goi_di_toi_dia_chi_tuyet_doi_trong_app(self):
		"""`goi()` phải dựng địa chỉ từ `KhoApp.goc()`, không phải một đường TƯƠNG ĐỐI.

		Trong bản đóng gói trang nằm ở `file://` (APK thật: `https://localhost` —
		Capacitor `androidScheme`), nên `/api/method/...` trỏ vào CHÍNH CÁI VỎ. Hỏng
		kiểu này IM LẶNG: WebView trả 404 của chính nó, không phải lỗi mạng, nên mọi
		màn chỉ báo "Có lỗi, thử lại." mãi mãi và không ai đoán ra vì sao.

		Đo biểu thức địa chỉ THẬT SỰ truyền cho `fetch(`, không phải sự có mặt của
		chữ `KHO_MAY_CHU` đâu đó trong file."""
		import re

		ma = self._ma_kho_pda("vo.js")
		than = self._than_ham(ma, "async goi(duong_dan, doi_so, _da_thu_lam_moi_csrf)")
		khop = re.search(r"fetch\(\s*(`[^`]*`)", than)
		self.assertIsNotNone(khop, "goi() không còn lời gọi fetch() nào nhận địa chỉ dạng template")
		self.assertEqual(
			khop.group(1),
			"`${this.goc()}/api/method/${duong_dan}`",
			"goi() không dựng địa chỉ từ KhoApp.goc() — trong app đường tương đối trỏ "
			"vào chính cái vỏ (file://), không tới máy chủ.",
		)
		than_goc = self._than_ham(ma, "goc() {")
		self.assertIn(
			"window.KHO_MAY_CHU",
			than_goc,
			"goc() không đọc hằng số mà vỏ app khai (www/cau-hinh.js)",
		)

		# Trên web `goc()` phải RỖNG (đường tương đối, cùng nguồn) — tức nó không
		# được rơi về `location.origin`/một địa chỉ viết cứng nào. Đó là điều kiện
		# để bản web KHÔNG ĐỔI HÀNH VI.
		self.assertNotIn("location.origin", than_goc)
		self.assertIn('|| ""', than_goc)

	def test_dong_may_chu_doc_cung_nguon_voi_lop_goi_mang(self):
		"""Dòng "Máy chủ:" trên màn thẻ/menu và `goi()` phải đọc CÙNG MỘT nguồn.

		Đây là chốt chặn bằng MẮT duy nhất chống ca "thủ kho cài nhầm bản trỏ máy
		chủ thử rồi ghi vào dữ liệu thử mà không ai biết". Nếu màn hình in một chỗ
		còn `goi()` lấy địa chỉ ở chỗ khác, hai thứ sẽ trôi khỏi nhau ĐÚNG LÚC cần
		nhất — một chốt chặn bằng mắt mà nói dối thì tệ hơn là không có.

		`location.origin` (bản trước Task 2) hiện `file://` trong bản đóng gói:
		phải KHÔNG CÒN trong thân `ve()`. Đọc thân hàm chứ không toàn văn file —
		chính đợt sửa này viết chú thích có chữ `location.origin` ngay cạnh đó."""
		ma_vo = self._ma_kho_pda("vo.js")
		than_hien = self._than_ham(ma_vo, "dia_chi_may_chu()")
		self.assertIn(
			"this.goc()",
			than_hien,
			"dia_chi_may_chu() không đọc cùng hằng số với goi() — hai nguồn sẽ trôi khỏi nhau",
		)

		for ten in ("man_the.js", "man_menu.js"):
			than_ve = self._than_ham(self._ma_kho_pda(ten), "ve($than)")
			self.assertNotIn(
				"location.origin",
				than_ve,
				f"{ten} vẫn in location.origin — trong bản đóng gói đó là nguồn của chính "
				"cái vỏ (file://), KHÔNG phải máy chủ đang nối.",
			)
			self.assertIn(
				"dia_chi_may_chu()",
				than_ve,
				f"{ten} không đọc địa chỉ máy chủ qua KhoApp.dia_chi_may_chu()",
			)

	def test_goi_gan_khoa_may_vao_authorization(self):
		"""Khoá máy đi trong `Authorization`; thiếu nó thì máy chủ coi là khách.

		Task 3 cấp khoá, Task 4 cất khoá — Task 2 chỉ dựng đường ống, nên ba hàm
		`dat_khoa`/`xoa_khoa`/`khoa` phải nói về CÙNG MỘT ô nhớ (bài này đọc tên ô
		nhớ ra từ hàm đọc rồi đối chiếu với hai hàm ghi, thay vì tin rằng chúng
		khớp). Không có khoá là trạng thái BÌNH THƯỜNG hôm nay."""
		import re

		ma = self._ma_kho_pda("vo.js")
		than = self._than_ham(ma, "async goi(duong_dan, doi_so, _da_thu_lam_moi_csrf)")
		self.assertRegex(
			than,
			r"khoa\s*=\s*this\.khoa\(\)",
			"goi() không đọc khoá máy đã lưu",
		)
		self.assertRegex(
			than,
			r'dau\["Authorization"\]\s*=\s*"token "\s*\+\s*khoa',
			'goi() không gắn khoá máy vào header Authorization dạng `token <khoá>`',
		)

		than_doc = self._than_ham(ma, "\tkhoa() {")
		khop = re.search(r"return this\.(\w+)", than_doc)
		self.assertIsNotNone(khop, "khoa() không đọc một ô nhớ nào của KhoApp")
		o_nho = khop.group(1)
		for ten_ham in ("dat_khoa(khoa)", "xoa_khoa()"):
			self.assertIn(
				f"this.{o_nho} =",
				self._than_ham(ma, ten_ham),
				f"{ten_ham} không ghi vào cùng ô nhớ mà khoa() đọc (this.{o_nho})",
			)

	# -------------------------------------- Task 4: nhận máy một lần
	#
	# BỐN BÀI DƯỚI ĐÂY ĐỀU ĐỌC CẤU TRÚC, KHÔNG ĐỌC TOÀN VĂN — cùng lý do đã ghi ở
	# khối chú thích Task 2 phía trên, và lần này lý do còn nặng hơn: mọi chữ cần
	# kiểm (`localStorage`, `X-Ma-May`, `xoa_khoa`, `cap_khoa_may`) đều được nhắc
	# dày đặc trong chính các chú thích giải thích vì sao chúng ở đó.
	#
	# BẰNG CHỨNG HÀNH VI nằm ở `scripts/kiem_giao_dien/kiem_goi_mang.js` mục 5 (APP):
	# đặt khoá → TẢI LẠI TRANG → phải vào thẳng menu → 401 → khoá chết cả trong kho
	# lưu → mở lại ra màn thẻ. Các bài tĩnh ở đây khoá phần khai báo để một lượt sửa
	# lạc tay đỏ ngay ở `bench run-tests`.

	@staticmethod
	def _khoi_tu(than, tu_vi_tri):
		"""Thân khối `{...}` khớp cặp, tính từ dấu `{` ĐẦU TIÊN ở/ sau `tu_vi_tri`."""
		mo = than.index("{", tu_vi_tri)
		do_sau = 0
		i = mo
		while i < len(than):
			if than[i] == "{":
				do_sau += 1
			elif than[i] == "}":
				do_sau -= 1
				if do_sau == 0:
					return than[mo + 1 : i]
			i += 1
		raise AssertionError("khối { } không khớp cặp")

	def test_man_the_nhan_may_trong_app_va_giu_nguyen_duong_web(self):
		"""Cùng một file, HAI đường — và không được đảo hai đường cho nhau.

		Trong app, quét thẻ đổi lấy một KHOÁ MÁY (`cap_khoa_may`); trên web nó mở một
		PHIÊN COOKIE (`dang_nhap_bang_the`). Gọi nhầm đường là hỏng IM LẶNG theo cả
		hai chiều: đường web trong app quét xong không đăng nhập được gì (cookie khác
		nguồn không bao giờ được gửi lại), còn đường app trên web thì phát một khoá
		API vĩnh viễn cho một người chỉ định làm một ca.

		Vì thế bài này đo CẢ THỨ TỰ của phép rẽ nhánh, không chỉ sự có mặt của hai
		hàm: đảo đúng hai vế của toán tử ba ngôi là một lượt sửa một ký tự."""
		ma = self._ma_kho_pda("man_the.js")

		than_app = self._than_ham(ma, "function _nhan_may(App, ma)")
		self.assertIn("the_pda.cap_khoa_may", than_app, "đường APP không gọi cap_khoa_may")
		self.assertIn("App.dat_khoa(", than_app, "đường APP nhận khoá xong mà không cất")
		self.assertIn("ma_may: App.ma_may()", than_app, "đường APP không khai mã máy khi xin khoá")
		self.assertNotIn("dang_nhap_bang_the", than_app)

		than_web = self._than_ham(ma, "function _dang_nhap_ca(App, ma)")
		self.assertIn("the_pda.dang_nhap_bang_the", than_web, "đường WEB không còn mở phiên bằng thẻ")
		self.assertNotIn("cap_khoa_may", than_web, "đường WEB phát khoá API — web không có khoá máy")
		self.assertNotIn("dat_khoa", than_web)

		than_ve = self._than_ham(ma, "ve($than)")
		self.assertRegex(
			than_ve,
			r"App\._la_app\(\)\s*\?\s*_nhan_may\(App, ma\)\s*:\s*_dang_nhap_ca\(App, ma\)",
			"phép rẽ nhánh app/web trong khi_quet đã mất hoặc bị ĐẢO hai vế",
		)

		# Hàm máy chủ phải có thật và còn whitelist — cùng phép kiểm mà bài của
		# `pda.html` đã dùng cho `dang_nhap_bang_the`.
		duong = "erpnext.warehouse_operations.vitri.the_pda.cap_khoa_may"
		self.assertIn(duong, ma)
		self.assertIn(
			frappe.get_attr(duong),
			frappe.whitelisted,
			f"{duong} mất @frappe.whitelist() — không máy nào nhận được khoá",
		)

	def test_goi_gui_ma_may_cung_khoi_voi_khoa(self):
		"""`Authorization` và `X-Ma-May` phải rời khỏi máy CÙNG NHAU.

		Máy chủ (`the_pda.py::kiem_khoa_may`) trả 401 cho mọi lời gọi mang khoá mà
		thiếu mã máy — fail-closed, cố ý. Nên một nhánh mã gắn khoá ở chỗ này và mã
		máy ở chỗ khác là một quả bom hẹn giờ: đủ điều kiện nào đó không đi qua nhánh
		thứ hai là cả kho 401 mà không ai đoán ra vì sao.

		VÀ TÊN HEADER ĐƯỢC ĐỐI CHIẾU VỚI CHÍNH HẰNG SỐ CỦA MÁY CHỦ, không phải với
		một chuỗi gõ tay trong bài test: gõ tay thì hai vế của hợp đồng có thể cùng
		sai một kiểu mà bài vẫn xanh."""
		import re

		from erpnext.warehouse_operations.vitri.the_pda import DAU_MA_MAY

		ma = self._ma_kho_pda("vo.js")
		than = self._than_ham(ma, "async goi(duong_dan, doi_so, _da_thu_lam_moi_csrf)")
		khoi = self._khoi_tu(than, than.index("if (khoa)"))
		self.assertIn(
			'dau["Authorization"] = "token " + khoa',
			khoi,
			"khối `if (khoa)` không còn gắn Authorization",
		)
		self.assertRegex(
			khoi,
			r"dau\[_DAU_MA_MAY\]\s*=\s*this\.ma_may\(\)",
			"mã máy KHÔNG được gắn trong cùng khối với khoá — hai header sẽ rời nhau",
		)

		sach = self._bo_chu_thich_giu_chuoi(ma)
		khop = re.search(r'const _DAU_MA_MAY = "([^"]*)"', sach)
		self.assertIsNotNone(khop, "vo.js không còn khai hằng số tên header mã máy")
		self.assertEqual(
			khop.group(1),
			DAU_MA_MAY,
			"tên header của app KHÁC hằng số DAU_MA_MAY của máy chủ — mọi máy ngoài kho ăn 401",
		)

	def test_401_giet_khoa_da_cat_khong_phu_thuoc_man_dang_dung(self):
		"""Thu hồi ở Desk phải NHÌN THẤY ĐƯỢC từ phía máy: 401 → xoá khoá đã cất.

		Không xoá thì app kẹt vĩnh viễn — mở lên là nạp lại đúng chiếc khoá đã chết,
		`la_khach = false`, vào thẳng menu, chạm gì cũng 401, và không có đường nào
		tới được màn quét thẻ để nhận máy lại.

		PHÉP XOÁ PHẢI ĐỘC LẬP VỚI MÀN ĐANG ĐỨNG. Nhánh điều hướng cũ mang thêm điều
		kiện `man_hien_tai !== "the"` (đúng cho việc nó làm: không tự đá về màn thẻ
		khi đang ở chính màn thẻ). Gộp phép xoá vào đó thì một khoá vừa bị thu hồi mà
		401 rơi đúng lúc đang ở màn thẻ sẽ SỐNG SÓT trong kho lưu.

		VÒNG SỬA CUỐI (soát tổng, N2) — BÀI NÀY ĐÃ ĐƯỢC SỬA, và sửa vì nó ĐÚNG lúc
		đỏ. Bài cũ tìm hai nhánh `if` có chứa chữ "401" ngay trong điều kiện. Từ vòng
		sửa cuối, điều kiện đó không còn là `res.status === 401 || res.status === 403`
		mà là `la_danh_tinh` — một biến do `_la_loi_danh_tinh()` tính ra, vì 403 trong
		app là lỗi QUYỀN NGHIỆP VỤ chứ không phải "khoá máy hỏng" (đo trên máy chủ
		thật: 401 = `AuthenticationError`, 403 = `PermissionError`).

		Nới bài cho hết đỏ sẽ mất luôn thứ nó canh. Thay vào đó bài đo đúng bất biến
		CŨ trên hình dạng MỚI: vẫn phải có đúng hai nhánh, vẫn phải có một nhánh gác
		theo KHOÁ và ĐỘC LẬP với màn đang đứng — chỉ đổi thứ dùng để nhận ra chúng.
		Vế "403 không giết khoá" là một khẳng định HÀNH VI, nằm ở
		`scripts/kiem_giao_dien/kiem_goi_mang.js` nửa NATIVE, không nằm ở đây."""
		ma = self._ma_kho_pda("vo.js")
		than = self._than_ham(ma, "async goi(duong_dan, doi_so, _da_thu_lam_moi_csrf)")

		dk_401 = [d for d in self._dieu_kien_if(than) if "la_danh_tinh" in d]
		self.assertEqual(
			len(dk_401),
			2,
			f"goi() phải có đúng hai nhánh lỗi danh tính (xoá khoá + điều hướng), đang thấy {len(dk_401)}: {dk_401}",
		)
		# KHÔNG CÒN ĐƯỢC PHÉP so thẳng `res.status` với 401/403 để quyết hai việc
		# này: đó chính là hình dạng của lỗi N2. Phải đi qua `_la_loi_danh_tinh()`,
		# nơi 403 được xét bằng `exc_type` của máy chủ.
		self.assertNotIn(
			"res.status === 403",
			" ".join(dk_401),
			"nhánh xoá khoá/điều hướng lại so thẳng với 403 — một lỗi QUYỀN nghiệp vụ "
			"sẽ giết khoá máy của cả kho (N2)",
		)
		dk_xoa = [d for d in dk_401 if "khoa" in d and "man_hien_tai" not in d]
		self.assertEqual(
			len(dk_xoa),
			1,
			f"không tìm thấy nhánh lỗi danh tính ĐỘC LẬP với màn đang đứng và gác theo khoá: {dk_401}",
		)
		khoi = self._khoi_tu(than, than.index(dk_xoa[0]))
		self.assertIn("this.xoa_khoa()", khoi, "nhánh 401 không giết khoá máy")
		self.assertIn(
			"this.la_khach = true",
			khoi,
			"xoá khoá mà không hạ `la_khach` — bấm Back là vào lại menu với một chiếc khoá đã chết",
		)

	def test_khoi_dong_vao_thang_menu_khi_da_cat_khoa(self):
		"""`data-la_khach="1"` viết cứng trong vỏ app KHÔNG được là câu trả lời cuối.

		Bản đóng gói không có phiên nào để máy chủ tính hộ, nên vỏ khai cứng "khách".
		Giữ nguyên nó thì app LUÔN mở ra ở màn quét thẻ và mục tiêu của cả Task —
		quét thẻ một lần lúc nhận máy, sau đó chạm icon là vào thẳng menu — không bao
		giờ đạt được dù khoá nằm sẵn trong máy.

		Ô nhớ bền được đọc RA TỪ HÀM GHI rồi đối chiếu với hàm nạp và hàm xoá: ba hàm
		phải nói về cùng một ô. So hàm nạp với chính nó thì không canh gì cả."""
		import re

		ma = self._ma_kho_pda("vo.js")

		than_kd = self._than_ham(ma, "khoi_dong(goc)")
		self.assertRegex(
			than_kd,
			r"this\._la_app\(\)\s*&&\s*this\._nap_khoa_da_cat\(\)",
			"khoi_dong() không nạp khoá đã cất (và chỉ trong app) — app luôn mở ở màn thẻ",
		)
		self.assertIn(
			"this.la_khach = false",
			than_kd,
			"nạp được khoá mà không hạ `la_khach` — chốt chặn khách vẫn ép về màn thẻ",
		)

		than_dat = self._than_ham(ma, "dat_khoa(khoa)")
		khop = re.search(r"_ghi_ben\((\w+),", than_dat)
		self.assertIsNotNone(khop, "dat_khoa() không cất khoá xuống máy")
		o_khoa = khop.group(1)
		self.assertIn(
			f"_doc_ben({o_khoa})",
			self._than_ham(ma, "_nap_khoa_da_cat()"),
			f"_nap_khoa_da_cat() không đọc đúng ô mà dat_khoa() ghi ({o_khoa})",
		)
		self.assertIn(
			f"_xoa_ben({o_khoa})",
			self._than_ham(ma, "xoa_khoa()"),
			f"xoa_khoa() không xoá đúng ô mà dat_khoa() ghi ({o_khoa})",
		)

	def test_khoa_cat_trong_localStorage_va_ma_may_song_qua_thu_hoi(self):
		"""Cất bằng `localStorage` của WebView — KHÔNG thêm gói `@capacitor/preferences`.

		Vùng này là kho RIÊNG của app (sandbox Android) và sống qua các lần mở app.
		Hệ quả đã chấp nhận: "Xoá dữ liệu ứng dụng" là mất khoá → quét thẻ lại.

		HAI ĐIỀU BÀI NÀY KHOÁ, mỗi điều một lỗi thật:

		1. Mọi phép đọc/ghi phải bọc `try/catch`. Một WebView chặn kho lưu mà ném lỗi
		   ở `khoi_dong()` là MÀN TRẮNG không lời giải thích.
		2. `xoa_khoa()` KHÔNG được xoá mã máy. `_ghi_thiet_bi` (the_pda.py) upsert
		   theo `ma_may`, nên một mã mới sau mỗi lần thu hồi là bảng `PDA Thiet Bi`
		   mọc thêm một dòng cho CÙNG một chiếc máy — đúng cái điều bảng đó sinh ra
		   để trả lời ("ai đang cầm máy nào")."""
		import re

		ma = self._ma_kho_pda("vo.js")

		for chu_ky in ("function _doc_ben(ten)", "function _ghi_ben(ten, gia_tri)", "function _xoa_ben(ten)"):
			than = self._than_ham(ma, chu_ky)
			self.assertIn("window.localStorage", than, f"{chu_ky} không dùng localStorage của WebView")
			self.assertIn("catch", than, f"{chu_ky} không bọc try/catch — kho lưu bị chặn là màn trắng")

		than_mm = self._than_ham(ma, "\tma_may() {")
		khop = re.search(r"_doc_ben\((\w+)\)", than_mm)
		self.assertIsNotNone(khop, "ma_may() không đọc mã máy đã cất")
		o_ma_may = khop.group(1)
		self.assertIn(f"_ghi_ben({o_ma_may}, ma)", than_mm, "ma_may() sinh mã mà không cất lại")
		self.assertNotIn(
			o_ma_may,
			self._than_ham(ma, "xoa_khoa()"),
			f"xoa_khoa() xoá luôn mã máy ({o_ma_may}) — chiếc máy đó quét thẻ lại sẽ thành một máy khác trong sổ",
		)

		goc_kho = frappe.get_app_path("erpnext").rsplit("/erpnext", 1)[0]
		with open(os.path.join(goc_kho, "pda_app", "package.json"), encoding="utf-8") as f:
			goi = json.load(f)
		phu_thuoc = dict(goi.get("dependencies", {}))
		phu_thuoc.update(goi.get("devDependencies", {}))
		self.assertNotIn(
			"@capacitor/preferences",
			phu_thuoc,
			"đã thêm @capacitor/preferences — localStorage đã đủ, và gói đó không giải được "
			"trong kho_pda.bundle.js (bundle dựng từ apps/erpnext, không phải pda_app)",
		)
		# Trên BẢN ĐÃ BỎ CHÚ THÍCH: chính khối chú thích giải thích "vì sao KHÔNG thêm
		# gói này" có tên gói trong đó — đọc toàn văn là bài test tự đỏ vì lời giải
		# thích của chính nó, đúng hạng lỗi mà khối chú thích Task 2 ở trên đã tả.
		self.assertNotIn("@capacitor/preferences", self._bo_chu_thich_giu_chuoi(ma))

	def test_dai_bao_401_noi_dung_nguyen_nhan_va_web_khong_doi_chu(self):
		"""Vòng sửa 1, mục F — dải báo phải nói ĐÚNG nguyên nhân, mỗi nơi một câu.

		Trên web 401/403 THẬT LÀ phiên hết hạn (12 tiếng). Trong app không có phiên nào
		để hết: nó nghĩa là khoá máy bị thu hồi hoặc chưa cấp. Dùng chung một câu thì
		thủ kho đọc "quét thẻ để làm tiếp" rồi quét lại ĐÚNG TẤM THẺ VỪA BỊ THU HỒI,
		thất bại lần nữa, và không biết phải gọi trưởng kho. Task 4 biến đường này từ
		hiếm thành thường xuyên.

		Câu đúng ĐÃ có trong tay app và đang bị ném đi: `_cau_loi_may_chu(...)` cho ca
		401 trong app trả "Máy chưa được cấp quyền — báo trưởng kho cấp khoá cho máy
		này.". Bài này đòi dải báo dùng ĐÚNG biến đó (không phải một chuỗi thứ hai gõ
		tay — hai chuỗi sẽ trôi khỏi nhau), và đòi vế WEB giữ NGUYÊN VĂN câu cũ."""
		ma = self._ma_kho_pda("vo.js")
		than = self._than_ham(ma, "async goi(duong_dan, doi_so, _da_thu_lam_moi_csrf)")

		# Câu lỗi phải được dựng TRƯỚC khối dải báo, nếu không thì không có gì để dùng.
		vi_tri_cau = than.index("_cau_loi_may_chu(")
		vi_tri_bao = than.index("this.bao(")
		self.assertLess(
			vi_tri_cau,
			vi_tri_bao,
			"câu lỗi máy chủ phải được tính TRƯỚC dải báo — nếu không, dải báo không có "
			"câu đúng để dùng và lại phải gõ tay một chuỗi thứ hai",
		)

		self.assertRegex(
			than,
			r'this\.bao\(\s*this\._la_app\(\)\s*\?\s*cau\s*:\s*__\("Phiên đã hết — quét thẻ để làm tiếp\."\)',
			"dải báo 401 không rẽ hai câu theo _la_app(), hoặc vế web đã ĐỔI CHỮ",
		)

		# Vế WEB phải là ĐÚNG MỘT chuỗi, đúng nguyên văn — đếm trên bản đã bỏ chú thích
		# để một lời giải thích nhắc lại câu đó không làm bài này xanh giả.
		sach = self._bo_chu_thich_giu_chuoi(ma)
		self.assertEqual(
			sach.count('__("Phiên đã hết — quét thẻ để làm tiếp.")'),
			1,
			"câu của đường WEB phải xuất hiện đúng một lần trong mã thật",
		)
		# Và câu của app KHÔNG được gõ tay lần thứ hai ở khối dải báo: nó phải đi qua
		# `_cau_loi_may_chu` (chỗ duy nhất Task 2B dựng câu cho app).
		self.assertEqual(
			than.count("Máy chưa được cấp quyền"),
			0,
			"câu của app bị gõ tay lại trong goi() — phải dùng biến từ _cau_loi_may_chu()",
		)

	def test_xoa_khoa_dat_lai_ca_ten_nguoi_dung(self):
		"""Vòng sửa 1, mục S2 — `xoa_khoa()` phải dọn cả tên trong bộ nhớ.

		Bỏ dòng đó thì sau một lượt 401 `KhoApp.nguoi_dung` còn mang tên người vừa bị
		thu hồi; màn menu vẽ lại (hoặc một màn nào đó đọc tên) sẽ nói sai về ai đang
		cầm máy — cùng hạng lỗi mà dòng "Máy chủ:" đã phải sửa ở Task 2."""
		than = self._than_ham(self._ma_kho_pda("vo.js"), "xoa_khoa()")
		self.assertRegex(
			than,
			r'this\.nguoi_dung\s*=\s*""',
			"xoa_khoa() không đặt lại this.nguoi_dung — tên người cũ sống sót qua lượt thu hồi",
		)

	def test_dang_xuat_trong_app_giet_khoa_may(self):
		"""Trong app, "Đăng xuất" không giết khoá máy là một nút KHÔNG LÀM GÌ.

		`logout` chỉ đóng phiên COOKIE, mà app không đăng nhập bằng cookie. Khoá máy
		trong kho lưu sống tiếp, nên `location.reload()` ngay sau đó nạp lại đúng
		chiếc khoá ấy và vào thẳng menu — người bấm nút tưởng đã trả máy trong khi
		chưa trả gì. Trên web thì ngược lại: ở đó không có khoá máy nào, và bọc
		`_la_app()` là để bản web không đổi hành vi."""
		than_ve = self._than_ham(self._ma_kho_pda("man_menu.js"), "ve($than)")
		self.assertRegex(
			than_ve,
			r"if\s*\(\s*erpnext\.kho_pda\.KhoApp\._la_app\(\)\s*\)\s*erpnext\.kho_pda\.KhoApp\.xoa_khoa\(\)",
			'nút "Đăng xuất" không giết khoá máy trong app (hoặc đã bỏ hàng rào _la_app cho web)',
		)
		self.assertIn(
			'KhoApp.goi("logout")',
			than_ve,
			"đường web đã mất lời gọi logout — bản web không được đổi hành vi",
		)

	def test_goi_bo_qua_csrf_trong_app_nhung_giu_nguyen_duong_web(self):
		"""Trong app không có cookie phiên nên KHÔNG có CSRF — bỏ qua nhánh đó khi
		`KHO_LA_APP`, nhưng ĐỪNG XOÁ nó khỏi đường web.

		`frappe.csrf_token` xuất hiện 4 lần trong `goi()`, nằm trong ĐÚNG HAI khối
		`if`: khối gắn header, và khối bắt `CSRFTokenError` để làm mới token. Bài
		này đọc điều kiện của MỌI `if` trong thân `goi()`, giữ lại những điều kiện
		nói về CSRF, và đòi TẤT CẢ phải mang cờ app — sót một khối là app vẫn đi
		vào nhánh đó. Đếm bằng cách này thay vì đếm số lần xuất hiện của chuỗi
		`frappe.csrf_token` (một phép đếm sẽ đỏ với mọi lần sửa chú thích hợp lệ)."""
		ma = self._ma_kho_pda("vo.js")
		than = self._than_ham(ma, "async goi(duong_dan, doi_so, _da_thu_lam_moi_csrf)")

		dieu_kien_csrf = [d for d in self._dieu_kien_if(than) if "csrf" in d.lower()]
		self.assertEqual(
			len(dieu_kien_csrf),
			2,
			f"goi() phải có đúng hai khối `if` về CSRF (gắn header + làm mới token), "
			f"đang thấy {len(dieu_kien_csrf)}: {dieu_kien_csrf}",
		)
		for d in dieu_kien_csrf:
			self.assertIn(
				"_la_app()",
				d,
				f"một nhánh CSRF không bị chặn khi chạy trong app: `if ({d.strip()})`",
			)

		# Đường WEB phải còn NGUYÊN cả ba phần của cơ chế đã trả giá ở Task 3.
		self.assertIn("X-Frappe-CSRF-Token", than)
		self.assertIn("CSRFTokenError", than)
		self.assertIn("_doc_lai_csrf_tu_trang()", than)

		self.assertIn(
			"window.KHO_LA_APP",
			self._than_ham(ma, "_la_app() {"),
			"_la_app() không đọc cờ mà vỏ app khai trong www/index.html",
		)

	def test_dai_ban_thu_tu_sinh_va_hien_o_hai_man_dung_yen(self):
		"""Dải "BẢN THỬ" — dấu hiệu KHÔNG CẦN ĐỌC CHỮ.

		Thủ kho sẽ không đối chiếu `192.168.61.129:8003` với một URL ngrok họ chưa
		từng nhớ, nên dòng "Máy chủ:" một mình không đủ. `dong-goi.sh` so địa chỉ
		đóng gói với địa chỉ phát hành và sinh `window.KHO_BAN_THU = true` khi hai
		cái khác nhau; hai màn ĐỨNG YÊN (thẻ, menu) hiện một dải màu nổi. Trên web
		không có biến đó → không hiện gì.

		Cả hai màn phải dựng dải qua CÙNG MỘT hàm — hai chỗ tự dựng là hai câu chữ
		sẽ lệch nhau."""
		ma_vo = self._ma_kho_pda("vo.js")
		than_dai = self._than_ham(ma_vo, "ve_dai_ban_thu($noi)")
		self.assertIn("this.ban_thu()", than_dai)
		self.assertIn("kho-ban-thu", than_dai)
		self.assertIn(
			"window.KHO_BAN_THU",
			self._than_ham(ma_vo, "ban_thu() {"),
			"ban_thu() không đọc cờ mà dong-goi.sh sinh ra",
		)
		for ten in ("man_the.js", "man_menu.js"):
			self.assertIn(
				"ve_dai_ban_thu(",
				self._than_ham(self._ma_kho_pda(ten), "ve($than)"),
				f"{ten} không dựng dải BẢN THỬ",
			)

		# Không có luật CSS thì `.kho-ban-thu` chỉ là một dòng chữ thường — tức
		# không còn là "dấu hiệu không cần đọc chữ", đúng thứ bài này bảo vệ.
		with open(self._doc("public", "scss", "kho_pda.bundle.scss"), encoding="utf-8") as f:
			self.assertIn(".kho-ban-thu {", f.read())

		goc = frappe.get_app_path("erpnext").rsplit("/erpnext", 1)[0]
		with open(os.path.join(goc, "scripts", "pda", "dong-goi.sh"), encoding="utf-8") as f:
			kich_ban = f.read()
		self.assertIn("may_chu_phat_hanh", kich_ban)
		self.assertIn("window.KHO_BAN_THU = true;", kich_ban)

		with open(os.path.join(goc, "scripts", "pda", "cau-hinh-may-chu.json"), encoding="utf-8") as f:
			cau_hinh = json.load(f)
		self.assertIn(
			"may_chu_phat_hanh",
			cau_hinh,
			"cau-hinh-may-chu.json thiếu địa chỉ phát hành — dong-goi.sh không có gì để so",
		)
		# Trong KHO MÃ NGUỒN, `may_chu` LUÔN là địa chỉ thử, nên hai khoá phải KHÁC
		# nhau: một bản dựng lỡ tay từ kho phải luôn đeo dải "BẢN THỬ".
		self.assertNotEqual(
			(cau_hinh.get("may_chu") or "").rstrip("/"),
			(cau_hinh.get("may_chu_phat_hanh") or "").rstrip("/"),
			"cau-hinh-may-chu.json trong kho đang khai địa chỉ phát hành TRÙNG địa chỉ "
			"đóng gói — một bản dựng lỡ tay sẽ không còn dải BẢN THỬ nào.",
		)

	# ------------------------------------------------------------- Task 5

	def test_task5_ngay_gio_may_chu_tiem_chi_trong_app_va_web_giu_object_rong(self):
		"""Khoá bằng ĐỌC MÃ phần dây nối mà báo cáo Task 5 (§2.4) đã đo bằng HÀNH
		VI trong một kịch bản TẠM (`/tmp`, không còn trong kho): xoá đúng phần này
		khỏi `man_tra_cuu.js` đổi chip hạn dùng từ "Còn 1 ngày" thành "Hết hạn hôm
		nay" cho MỘT LÔ Y HỆT — dựng lại đúng lỗi cả Task 5 sinh ra để vá (giao
		diện lẳng lặng đổi từ giờ SITE sang giờ MÁY TRẠM). Bài hành vi đó không
		còn sống trong kho; bài TĨNH này là hàng rào Ở LẠI, canh đúng phần dây nối
		mà kịch bản kia đã chứng minh có ý nghĩa.

		HAI VẾ, không vế nào thay được vế kia: APP phải tiêm cả `ngay`/`gio` đọc
		`KhoApp.ngay_may_chu()`/`gio_may_chu()`, gác bằng `_la_app()`; nhánh
		KHÔNG-phải-app của phép rẽ đó phải là object RỖNG (không phải một hàm trả
		`null`) — một hàm trả `null` vẫn chặn cứng lối rơi về mặc định
		`_ngay_may_tram()`/`_gio_may_tram()` của `tao()`, tức web sẽ NGƯNG đọc
		đồng hồ trình duyệt — đúng ràng buộc cứng "bản web không đổi hành vi"."""
		than = self._than_ham(self._ma_kho_pda("man_tra_cuu.js"), "function _dung_luong()")
		self.assertIn("_la_app()", than, "_dung_luong() không còn rẽ nhánh theo _la_app()")
		self.assertIn("ngay_may_chu()", than, "không còn tiêm ngay_may_chu() vào lớp luồng")
		self.assertIn("gio_may_chu()", than, "không còn tiêm gio_may_chu() vào lớp luồng")
		self.assertRegex(
			than,
			r":\s*\{\}\)",
			"nhánh WEB (không phải app) của phép tiêm ngay/gio không còn là object "
			"RỖNG — web có thể đã bị tiêm một hàm (kể cả hàm trả null), chặn mất lối "
			"rơi về đồng hồ trình duyệt mà web đang cần giữ nguyên.",
		)

	def test_task5_dai_lech_gio_tu_sinh_va_hien_o_hai_man_dung_yen(self):
		"""Cùng khuôn `test_dai_ban_thu_tu_sinh_va_hien_o_hai_man_dung_yen` ở trên
		— Task 5 thêm MỘT dải cảnh báo nữa qua đúng khuôn đó: một hàm dựng, hai
		màn ĐỨNG YÊN (thẻ, menu) gọi, một luật CSS để dải đó là một dấu hiệu MÀU
		chứ không phải một dòng chữ thường."""
		ma_vo = self._ma_kho_pda("vo.js")
		than_dai = self._than_ham(ma_vo, "ve_dai_lech_gio($noi)")
		self.assertIn("this.lech_gio_qua_nguong()", than_dai)
		self.assertIn("kho-lech-gio", than_dai)
		self.assertIn(
			"_NGUONG_LECH_GIO_PHUT", ma_vo, "ngưỡng cảnh báo lệch giờ đã biến mất khỏi vo.js"
		)
		for ten in ("man_the.js", "man_menu.js"):
			self.assertIn(
				"ve_dai_lech_gio(",
				self._than_ham(self._ma_kho_pda(ten), "ve($than)"),
				f"{ten} không dựng dải cảnh báo lệch giờ",
			)
		with open(self._doc("public", "scss", "kho_pda.bundle.scss"), encoding="utf-8") as f:
			self.assertIn(".kho-lech-gio {", f.read())

	def test_task5_co_bo_qua_dong_bo_gio_khong_lot_vao_ban_that(self):
		"""`window.KHO_BO_QUA_DONG_BO_GIO` chỉ được HAI CỔNG PLAYWRIGHT tự khai
		cho CHÍNH TRANG GIẢ của chúng (`kiem_ban_dong_goi.js`/`kiem_goi_mang.js`,
		qua `page.addInitScript`, không đụng file nào trong kho). Nếu cờ này lọt
		vào `pda_app/www/index.html` (git theo dõi) hay được
		`scripts/pda/dong-goi.sh` tự sinh (như `cau-hinh.js`), MỌI bản đóng gói
		THẬT sẽ VĨNH VIỄN không đồng bộ giờ — hỏng theo hướng AN TOÀN (ẩn chip
		thay vì đoán sai) nhưng HỎNG HOÀN TOÀN và ÂM THẦM."""
		goc = frappe.get_app_path("erpnext").rsplit("/erpnext", 1)[0]
		with open(os.path.join(goc, "pda_app", "www", "index.html"), encoding="utf-8") as f:
			self.assertNotIn("KHO_BO_QUA_DONG_BO_GIO", f.read())
		with open(os.path.join(goc, "scripts", "pda", "dong-goi.sh"), encoding="utf-8") as f:
			self.assertNotIn("KHO_BO_QUA_DONG_BO_GIO", f.read())

	# ------------------------------------------------------------- Task 6, việc thêm 1

	@staticmethod
	def _bo_chu_thich_va_chuoi(ma):
		"""Thay nội dung mọi chú thích (`//...`, `/*...*/`) và mọi chuỗi/template
		(`"...".'...'`,`` `...` ``) bằng khoảng trắng CÙNG ĐỘ DÀI — giữ nguyên vị trí
		ký tự để không lệch chỉ số, nhưng loại các dấu `{`/`}` NẰM TRONG văn bản đó
		khỏi việc đếm độ sâu ngoặc bên dưới. Không làm việc này thì chính các dòng
		chú thích giải thích `.tao(` (đầy trong bốn file `man_*.js` sau đợt sửa này)
		sẽ tự làm hỏng phép đếm độ sâu."""
		ra = []
		i, n = 0, len(ma)
		while i < n:
			hai = ma[i : i + 2]
			if hai == "//":
				j = ma.find("\n", i)
				j = n if j == -1 else j
				ra.append(" " * (j - i))
				i = j
			elif hai == "/*":
				j = ma.find("*/", i + 2)
				j = n if j == -1 else j + 2
				ra.append(" " * (j - i))
				i = j
			elif ma[i] in "\"'`":
				trich = ma[i]
				j = i + 1
				while j < n and ma[j] != trich:
					j += 2 if ma[j] == "\\" else 1
				j = min(j + 1, n)
				ra.append(" " * (j - i))
				i = j
			else:
				ra.append(ma[i])
				i += 1
		return "".join(ra)

	def _vi_tri_tao_o_top_level(self, ma):
		"""Mọi vị trí chuỗi con `.tao(` xuất hiện NGOÀI mọi hàm (kể cả hàm mũi tên
		không có `{}`) — tức bị gọi ngay lúc module top-level chạy, đúng kiểu hỏng
		mà Task 6 việc thêm 1 phải dứt điểm.

		CỐ Ý không dùng "cột 0 / không thụt đầu dòng" làm dấu hiệu: cách đó lọt qua
		đúng ca

			const _luong =
				_ns().tao({...});

		— dòng chứa `.tao(` KHÔNG ở cột 0 nhưng vẫn chạy ở top-level.

		VÒNG SỬA 1 (soát xét): bản đầu chỉ đếm độ sâu `{`/`}`, coi `.tao(` "an
		toàn" hễ nó nằm trong MỘT CẶP `{}` bất kỳ. Người soát dựng được hai phản
		ví dụ:
		  - BÁO NHẦM ĐỎ (an toàn thật, bài lại kêu hỏng): `const _dung_luong = ()
		    => _ns().tao({});` — hàm mũi tên KHÔNG có `{}` (thân là một BIỂU
		    THỨC) không mở cặp `{}` nào để đếm, nên `do_sau` vẫn ở 0 ngay tại
		    `.tao(` dù lời gọi đó THẬT SỰ hoãn tới lúc `_dung_luong()` được gọi.
		  - BỎ LỌT (hỏng thật, bài lại im): `if (true) { _luong = _ns().tao({});
		    }` ở CẤP MODULE — khối `if` CŨNG mở một cặp `{}`, bài cũ tưởng đó là
		    một hàm nên coi `.tao(` bên trong là an toàn, dù khối `if` chạy NGAY
		    lúc nạp, không đợi gọi gì cả.

		SỬA: đếm theo BA THỨ — `{`/`(`/mũi tên `=>` — và phân biệt "khung nào THẬT
		SỰ hoãn thực thi" (hàm) khỏi "khung chỉ đứng đó" (object literal, tham số,
		mũi tên không `{}` vẫn phải tự mở một khung ẢO vì không có dấu ngoặc nào
		để đếm). Quy tắc nhận diện MỘT `{` LÀ THÂN HÀM: đứng ngay sau `)` (khai báo
		hàm thường/kiểu `function ... () {`, method shorthand `ten(...) {`, hoặc
		mũi tên có khối `(...) => {`) hoặc ngay sau `=>` (mũi tên không tham số).
		Còn lại (đứng sau `(`, `,`, `=`, ký tự khác — tức object literal) THÌ
		KHÔNG.

		GIỚI HẠN CÒN LẠI, GHI RÕ THAY VÌ GIẢ VỜ KÍN (theo đúng góp ý soát xét —
		"một bài test biết giới hạn của mình thì dùng được"): quy tắc trên coi MỌI
		`{` đứng sau `)` là thân hàm, nên `if (...) {`/`for (...) {`/`while (...)
		{` CŨNG bị tính là "hàm" — ca "bỏ lọt" nêu trên (`if (true) { ...tao()...
		}` ở cấp module) VẪN không bị bắt. Đây là đánh đổi CÓ CHỦ Ý: phân biệt
		đúng `if`/`for`/`while` với hàm đòi phân tích cú pháp JS thật (theo dõi từ
		khoá đứng trước dấu `(`), vượt quá phạm vi một bài kiểm tra tĩnh bằng
		Python cho một lớp JS nhỏ. Không có `man_*.js` nào hiện tại dùng `.tao(`
		trong một khối `if`/`for`/`while` ở cấp module — nếu sau này có ai viết
		kiểu đó, bài này sẽ SAI, và đây chính là lý do để lại đoạn chú thích này."""
		sach = self._bo_chu_thich_va_chuoi(ma)
		n = len(sach)
		khung = []  # ngăn xếp (loai, la_ham); loai in {"{", "(", "=>"}
		so_ham_dang_mo = 0
		vi_tri = []

		def dong_mui_ten_tren_dinh():
			nonlocal so_ham_dang_mo
			while khung and khung[-1][0] == "=>":
				_, la_ham = khung.pop()
				if la_ham:
					so_ham_dang_mo -= 1

		i = 0
		while i < n:
			if so_ham_dang_mo == 0 and sach[i : i + 5] == ".tao(":
				vi_tri.append(i)

			if sach[i : i + 2] == "=>":
				# Mũi tên KHÔNG có `{}` (thân là biểu thức) phải tự mở một khung
				# ẢO — không có dấu ngoặc nào để `{`/`}` bên dưới đếm hộ. Mũi tên
				# CÓ `{}` thì để đúng nhánh `c == "{"` bên dưới lo (nhận ra nhờ
				# đứng ngay sau `=>`), không mở khung ảo ở đây kẻo đếm hai lần.
				j = i + 2
				while j < n and sach[j].isspace():
					j += 1
				if j >= n or sach[j] != "{":
					khung.append(("=>", True))
					so_ham_dang_mo += 1
				i += 2
				continue

			c = sach[i]
			if c == "{":
				k = i - 1
				while k >= 0 and sach[k].isspace():
					k -= 1
				la_ham = k >= 0 and sach[k] == ")"
				if not la_ham and k >= 1 and sach[k - 1 : k + 1] == "=>":
					la_ham = True
				khung.append(("{", la_ham))
				if la_ham:
					so_ham_dang_mo += 1
			elif c == "(":
				khung.append(("(", False))
			elif c in "})":
				dong_mui_ten_tren_dinh()
				if khung:
					_, la_ham = khung.pop()
					if la_ham:
						so_ham_dang_mo -= 1
			elif c in ",;":
				dong_mui_ten_tren_dinh()
			i += 1
		return vi_tri

	def test_khong_goi_tao_o_top_level_trong_man(self):
		"""Chỗ hở cuối cùng của Task 2–5 (Task 6, việc thêm ngoài brief 1): bốn file
		`man_*.js` từng dựng luồng bằng `const _luong = <namespace>.tao(...)` ngay
		lúc module top-level chạy — phụ thuộc cứng vào thứ tự các dòng `import`
		trong `kho_pda.bundle.js`. Đảo nhầm một dòng import (namespace nạp SAU file
		màn) khiến `.tao()` gọi trên một namespace còn `undefined`, ném lỗi NGAY LÚC
		TẢI TRANG — một màn chết hẳn, mà KHÔNG bài test Python nào (kể cả các bài
		còn lại trong `TestVoAppKho`) bắt được, vì không bài nào thực thi JS trong
		trình duyệt. Bài này khoá bằng cách đọc mã nguồn tĩnh: quét MỌI file
		`man_*.js` (không chỉ bốn tên đã biết hôm nay — glob theo đúng chữ brief
		dùng, "man_*.js", để một màn thứ năm sau này cũng tự động được khoá), cấm
		`.tao(` xuất hiện ở độ sâu ngoặc nhọn 0.

		ĐÃ PHÁ NGƯỢC ĐỂ CHỨNG MINH BÀI NÀY CẮN (đợt sửa Task 6): tạm khôi phục
		`man_tra_cuu.js` về đúng dạng cũ (`const _luong = _LUONG_NS.tao(...)` ở
		top-level), chạy lại bài này — ĐỎ, báo đúng tên file `man_tra_cuu.js`; phục
		hồi bản sửa — XANH trở lại. Không để lại bản phá trong kho."""
		thu_muc = self._doc("public", "js", "kho_pda")
		hong = []
		for ten in os.listdir(thu_muc):
			if not ten.startswith("man_") or not ten.endswith(".js"):
				continue
			with open(os.path.join(thu_muc, ten), encoding="utf-8") as f:
				ma = f.read()
			if self._vi_tri_tao_o_top_level(ma):
				hong.append(ten)
		self.assertEqual(
			hong,
			[],
			f"{hong}: còn gọi `.tao(` ở cấp module (top-level) — đảo nhầm một dòng "
			"import trong kho_pda.bundle.js là màn này chết hẳn, không lỗi nào báo. "
			"Dựng luồng bên trong hàm (kiểu `_dung_luong()`), gọi lần đầu ở `ve()`.",
		)

	def test_man_dung_luong_co_ham_dung_luong_luoi(self):
		"""Bài kia (`test_khong_goi_tao_o_top_level_trong_man`) khoá THIẾU: một file
		lỡ xoá cả `.tao(` LẪN toàn bộ cơ chế dựng luồng (vô tình xoá nhầm khi sửa
		chỗ khác) sẽ xanh giả — không còn `.tao(` nào ở top-level vì không còn
		`.tao(` nào hết. Bài này khoá NGƯỢC LẠI: mọi `man_*.js` có nhắc tới
		namespace `erpnext.warehouse_operations.luong.` (tức là màn có dùng lớp
		luồng) THÌ PHẢI có cơ chế dựng LƯỜI thật sự — nhận diện bằng hàm
		`_dung_luong(` mà cả bốn file dùng chung một tên sau đợt sửa Task 6. Hai
		bài cùng đọc một tệp nhưng cắn hai lỗi khác nhau, đúng khuôn "không bài
		nào thay được bài nào" mà file này theo suốt (xem `TestNutTrenPhieuLo`)."""
		thu_muc = self._doc("public", "js", "kho_pda")
		thieu = []
		for ten in os.listdir(thu_muc):
			if not ten.startswith("man_") or not ten.endswith(".js"):
				continue
			with open(os.path.join(thu_muc, ten), encoding="utf-8") as f:
				ma = f.read()
			if "erpnext.warehouse_operations.luong." not in ma:
				continue
			if "_dung_luong(" not in ma:
				thieu.append(ten)
		self.assertEqual(
			thieu,
			[],
			f"{thieu}: dùng lớp luồng nhưng không có hàm dựng LƯỜI `_dung_luong()`.",
		)

	def test_vo_js_nap_truoc_moi_man(self):
		"""Ràng buộc thứ tự THẬT còn lại, khác hẳn thứ đã bỏ được (soát xét vòng 1,
		Task 6, mục 2): `vo.js` phải nạp TRƯỚC MỌI file `man_*.js` trong
		`kho_pda.bundle.js` — kể cả `man_the.js`/`man_menu.js`, hai file KHÔNG dùng
		lớp luồng nên không bị `test_khong_goi_tao_o_top_level_trong_man` chạm tới.

		Lý do: mọi `man_*.js` gọi `erpnext.kho_pda.KhoApp.dang_ky_man(...)` NGAY
		LÚC MODULE TOP-LEVEL chạy — đây là hành vi ĐÚNG, không phải lỗi cần dựng
		lười giống `.tao()` (đăng ký một màn không tốn lời gọi máy chủ, không có
		trạng thái nào để mất khi gọi sớm). Nhưng `KhoApp` chỉ tồn tại sau dòng
		`erpnext.kho_pda.KhoApp = new _KhoApp();` ở cuối `vo.js` — đảo `vo.js`
		xuống sau một `man_*.js` bất kỳ thì `dang_ky_man` gọi trên `undefined`,
		ném lỗi ngay lúc tải, cùng hạng hỏng "một màn chết hẳn ngay lúc tải" mà
		việc thêm 1 vừa sửa — chỉ khác NGUỒN GỐC (đây là `KhoApp` chưa có, không
		phải namespace luồng chưa có). Đọc theo SỐ THỨ TỰ DÒNG import trong file
		— không dùng `.index()` tìm chuỗi con (một dòng chú thích nhắc lại đường
		dẫn import, như chính khối chú thích Task 6 phía trên các dòng `import`
		này, có thể lừa `.index()` — đúng bài học vừa trả giá ở mục 1)."""
		import re

		with open(self._doc("public", "js", "kho_pda.bundle.js"), encoding="utf-8") as f:
			dong = f.readlines()

		vi_tri_vo = None
		man_nap_truoc_vo = []
		for i, d in enumerate(dong):
			d = d.strip()
			if not d.startswith("import "):
				continue
			if d == 'import "./kho_pda/vo.js";':
				vi_tri_vo = i
				continue
			m = re.match(r'import "\./kho_pda/(man_[^"]+\.js)";', d)
			if m and vi_tri_vo is None:
				man_nap_truoc_vo.append(m.group(1))

		self.assertIsNotNone(vi_tri_vo, "không tìm thấy dòng import vo.js trong kho_pda.bundle.js")
		self.assertEqual(
			man_nap_truoc_vo,
			[],
			f"{man_nap_truoc_vo}: nạp TRƯỚC vo.js — dang_ky_man() gọi trên "
			"erpnext.kho_pda.KhoApp lúc nó chưa tồn tại, ném lỗi ngay lúc tải trang.",
		)

	# ------------------------------------------------------------- Task 6 (đợt APK)
	#
	# CẢNH BÁO CHO NGƯỜI ĐỌC SAU: bốn bài dưới đây là bài TĨNH, và cả đợt này đã
	# đếm được TÁM lượt "xanh oan" của bài tĩnh — chúng đọc HÌNH DẠNG, không đọc
	# NGHĨA. Hàng rào thật của Task 6 là hai kịch bản HÀNH VI trong
	# `scripts/kiem_giao_dien/kiem_goi_mang.js` (`do_loi_an`, `do_nhac_ban_moi`):
	# ở đó lối ẩn được BẤM GIỮ thật và lời gọi mạng được đo xem nó tới máy chủ
	# NÀO. Bốn bài này chỉ canh những HỢP ĐỒNG mà một cổng trình duyệt không nhìn
	# thấy: một file XML của Android, một tên hàm phía máy chủ Python, và nội
	# dung của chính chiếc APK.

	def _goc_kho(self):
		"""Gốc kho (`apps/erpnext`), không phải thư mục gói (`apps/erpnext/erpnext`)."""
		return frappe.get_app_path("erpnext").rsplit("/erpnext", 1)[0]

	def test_task6_host_http_trong_vo_js_khop_network_security_config(self):
		"""Lối ẩn từ chối `http://` tới host lạ, và danh sách host đó phải là
		ĐÚNG danh sách trong `network_security_config.xml`.

		VÌ SAO PHẢI ĐỐI CHIẾU: hai file này nói về cùng một thứ ở hai tầng khác
		nhau. Android chặn `http://` tới host ngoài file XML TRƯỚC KHI mã của app
		chạy, nên nếu JS cho qua một host mà XML không có, người đi cứu máy gõ
		đúng địa chỉ rồi thấy triệu chứng y hệt "máy chủ chết" — đúng cái tình
		huống lối ẩn sinh ra để chấm dứt, chỉ khác là lần này ta tự gây ra. Chiều
		ngược lại (XML có, JS không) thì một địa chỉ hợp lệ bị từ chối oan.

		Một cổng trình duyệt KHÔNG thể canh điều này: ở đó không có Android."""
		import re

		with open(
			os.path.join(
				self._goc_kho(),
				"pda_app", "android", "app", "src", "main", "res", "xml",
				"network_security_config.xml",
			),
			encoding="utf-8",
		) as f:
			xml = f.read()
		tu_xml = set(re.findall(r"<domain[^>]*>([^<]+)</domain>", xml))

		# Bỏ chú thích trước khi tìm: khối chú thích ngay trên hằng số này NHẮC LẠI
		# tên `_HOST_HTTP_CHO_PHEP` và tên file XML — đúng cái bẫy đã làm một bài
		# test của đợt trước xanh oan (nó grep trúng chính lời giải thích).
		sach = self._bo_chu_thich_giu_chuoi(self._ma_kho_pda("vo.js"))
		khop = re.search(r"_HOST_HTTP_CHO_PHEP\s*=\s*\[([^\]]*)\]", sach)
		self.assertIsNotNone(khop, "vo.js không còn khai _HOST_HTTP_CHO_PHEP")
		tu_js = set(re.findall(r'"([^"]+)"', khop.group(1)))

		self.assertEqual(
			tu_js,
			tu_xml,
			"danh sách host cho phép HTTP trong vo.js lệch khỏi network_security_config.xml "
			f"(js={sorted(tu_js)} xml={sorted(tu_xml)}) — một bên cho, một bên chặn",
		)
		# Và `base-config` vẫn phải CẤM cleartext: nới nó ra là mọi địa chỉ đi được
		# bằng HTTP trần, kể cả lời gọi mang khoá máy — lúc đó bài trên vẫn xanh mà
		# hàng rào thì không còn.
		self.assertIn(
			'<base-config cleartextTrafficPermitted="false" />',
			xml,
			"base-config đã bị nới — HTTP trần đi được tới MỌI địa chỉ",
		)

	def test_task6_duong_hoi_ban_cai_co_that_va_duoc_whitelist(self):
		"""Chuỗi đường dẫn mà `vo.js::hoi_ban_cai_moi()` gọi phải trỏ tới một hàm
		CÓ THẬT và ĐƯỢC whitelist với `allow_guest`.

		Gõ sai một chữ ở đây thì dải nhắc bản mới im lặng vĩnh viễn: `goi()` ăn
		một lỗi, `hoi_ban_cai_moi()` nuốt nó thành `null` (cố ý — xem docstring
		của hàm), và KHÔNG MỘT DẤU HIỆU nào trên màn. `allow_guest` là bắt buộc
		vì máy chưa nhận vẫn vẽ màn menu được sau khi quét thẻ."""
		from erpnext.warehouse_operations.vitri.cai_app import ban_cai_moi_nhat

		than = self._than_ham(self._ma_kho_pda("vo.js"), "hoi_ban_cai_moi()")
		duong = "erpnext.warehouse_operations.vitri.cai_app.ban_cai_moi_nhat"
		self.assertIn(duong, than, "hoi_ban_cai_moi() không gọi đúng đường dẫn máy chủ")
		self.assertIn(ban_cai_moi_nhat, frappe.whitelisted)
		self.assertIn(
			ban_cai_moi_nhat,
			frappe.guest_methods,
			"mất `allow_guest` là màn menu của một máy chưa có khoá ăn 401 ở lời gọi này",
		)

	def test_task6_ban_app_trong_ban_dong_goi_khop_versionName(self):
		"""`window.KHO_BAN_APP` trong BẢN ĐÃ ĐÓNG GÓI phải bằng `versionName`
		trong `build.gradle` — cùng biến sinh ra TÊN FILE APK.

		Đọc BẢN ĐÃ CHÉP (`pda_app/www/cau-hinh.js`), không đọc `dong-goi.sh`:
		việc cần canh là "bản cài trong tay thủ kho khai đúng phiên bản của nó",
		mà `dong-goi.sh` có thể chạy đúng hôm qua rồi hôm nay ai đó sửa
		`versionName` và quên đóng gói lại. Lệch nhau thì dải nhắc so một con số
		với một con số khác: hoặc nhắc vĩnh viễn, hoặc im vĩnh viễn."""
		import re

		goc = self._goc_kho()
		with open(
			os.path.join(goc, "pda_app", "android", "app", "build.gradle"), encoding="utf-8"
		) as f:
			gradle = f.read()
		m = re.search(r'versionName\s+"([^"]+)"', gradle)
		self.assertIsNotNone(m, "build.gradle không còn khai versionName")

		tep_cau_hinh = os.path.join(goc, "pda_app", "www", "cau-hinh.js")
		if not os.path.exists(tep_cau_hinh):
			self.skipTest("chưa chạy scripts/pda/dong-goi.sh — không có bản đóng gói để đối chiếu")
		with open(tep_cau_hinh, encoding="utf-8") as f:
			cau_hinh = f.read()
		m2 = re.search(r'window\.KHO_BAN_APP\s*=\s*"([^"]+)"', cau_hinh)
		self.assertIsNotNone(
			m2,
			"bản đóng gói KHÔNG khai window.KHO_BAN_APP — dải nhắc bản mới sẽ không bao giờ hiện",
		)
		self.assertEqual(
			m2.group(1),
			m.group(1),
			"phiên bản trong bản đóng gói lệch khỏi versionName của build.gradle — "
			"chạy lại scripts/pda/dong-goi.sh",
		)
		# Địa chỉ THẬT không được nằm trong kho mã nguồn: `cau-hinh.js` bị gitignore,
		# nhưng `cau-hinh-may-chu.json` thì KHÔNG — nó chỉ được giữ địa chỉ THỬ.
		with open(
			os.path.join(goc, "scripts", "pda", "cau-hinh-may-chu.json"), encoding="utf-8"
		) as f:
			cau_hinh_json = json.load(f)
		self.assertTrue(
			cau_hinh_json["may_chu"].startswith("http://192.168.")
			or cau_hinh_json["may_chu"].startswith("http://10."),
			"scripts/pda/cau-hinh-may-chu.json đang giữ một địa chỉ KHÔNG phải mạng nội bộ thử — "
			"người phát hành quên trả file này về giá trị thử sau khi dựng APK cho kho",
		)

	def test_task6_apk_mang_dung_ban_dong_goi(self):
		"""MỞ BUNG CHÍNH CHIẾC APK và đối chiếu với `pda_app/www/`.

		VÌ SAO KHÔNG TIN `npx cap sync`: đợt trước đã bắt được MỘT LẦN chiếc APK
		mang bundle của lượt dựng TRƯỚC, đúng bằng phép này. `cap sync` chép
		`www/` sang `android/app/src/main/assets/public/`; chạy nó TRƯỚC
		`dong-goi.sh` (thứ tự rất dễ đảo) thì APK ra lò vẫn hợp lệ, vẫn ký được,
		vẫn cài được — và mang giao diện của hôm qua.

		BỎ QUA khi chưa dựng APK: bài này canh một SẢN PHẨM, không canh mã nguồn,
		nên nó không có gì để nói trên một cây làm việc chưa chạy gradle."""
		import hashlib
		import zipfile

		import re

		goc = self._goc_kho()
		# Tên APK mang `versionName` (`outputFileName` trong build.gradle). Ghi cứng
		# "1.0" thì nâng bản là bài này lặng lẽ BỎ QUA — đúng lúc cần nó nhất.
		with open(os.path.join(goc, "pda_app", "android", "app", "build.gradle"), encoding="utf-8") as f:
			ban = re.search(r'versionName\s+"([^"]+)"', f.read()).group(1)
		apk = os.path.join(
			goc, "pda_app", "android", "app", "build", "outputs", "apk", "release",
			f"miyano-pda-{ban}-release.apk",
		)
		www = os.path.join(goc, "pda_app", "www")
		if not os.path.exists(apk):
			self.skipTest("chưa dựng APK release — không có gì để mở bung")

		def bam(b):
			return hashlib.md5(b).hexdigest()

		def bo_dong_ban_do(b):
			"""Cắt dòng `/*# sourceMappingURL=... */` ở cuối file CSS.

			ĐO ĐƯỢC, KHÔNG PHẢI PHÒNG XA: `bench build` sinh tên file bản đồ
			nguồn mang một mã băm ĐỔI MỖI LƯỢT DỰNG dù nội dung SCSS không đổi
			một byte (thấy: `...NV2GXDN3.css.map` → `...C623R53O.css.map` giữa
			hai lượt liên tiếp). Nếu so nguyên văn thì bài này ĐỎ ở mọi lượt
			chạy `dong-goi.sh` sau khi đã dựng APK — một cổng đỏ vì lý do không
			liên quan sẽ bị người ta tắt đi, và lúc đó mất luôn phép so THẬT.
			Chỉ NỚI đúng một dòng bình luận không ảnh hưởng gì tới lớp vẽ; toàn
			bộ phần còn lại của CSS vẫn so nguyên văn."""
			return b"\n".join(
				d for d in b.split(b"\n") if not d.strip().startswith(b"/*# sourceMappingURL=")
			)

		with zipfile.ZipFile(apk) as z:
			trong_apk = set(z.namelist())
			for ten in ("kho_pda.bundle.js", "kho_pda.bundle.css", "cau-hinh.js", "shim.js", "index.html"):
				duong = "assets/public/" + ten
				self.assertIn(duong, trong_apk, f"APK thiếu {duong}")
				loc = bo_dong_ban_do if ten.endswith(".css") else (lambda b: b)
				with open(os.path.join(www, ten), "rb") as f:
					self.assertEqual(
						bam(loc(z.read(duong))),
						bam(loc(f.read())),
						f"{duong} trong APK KHÁC bản trong pda_app/www — APK mang bản CŨ "
						"(chạy dong-goi.sh TRƯỚC npx cap sync, rồi dựng lại)",
					)
			# `capacitor.config.json` gói bên trong phải còn bật cầu HTTP native:
			# tắt nó là mọi lời gọi của APK rơi về `fetch` thường và chết vì CORS.
			cau_hinh_apk = json.loads(z.read("assets/capacitor.config.json"))
			self.assertTrue(
				cau_hinh_apk.get("plugins", {}).get("CapacitorHttp", {}).get("enabled"),
				"capacitor.config.json TRONG APK không bật CapacitorHttp",
			)
			# `native-bridge.js` là file Capacitor tiêm vào WebView — cổng
			# `kiem_goi_mang.js` nạp bản trong `node_modules` để đo cầu native; hai
			# bản lệch nhau thì cái cổng ấy đang đo một cây cầu khác cây cầu thật.
			bridge_apk = z.read("assets/native-bridge.js")
		bridge_nguon = os.path.join(
			goc, "pda_app", "node_modules", "@capacitor", "android", "capacitor",
			"src", "main", "assets", "native-bridge.js",
		)
		if os.path.exists(bridge_nguon):
			with open(bridge_nguon, "rb") as f:
				self.assertEqual(
					bam(bridge_apk),
					bam(f.read()),
					"native-bridge.js trong APK khác bản trong node_modules — cổng kiem_goi_mang.js "
					"đang đo một cây cầu native KHÔNG phải cây cầu trong APK",
				)

	# --------------------------------------------- Task 6, vòng sửa cuối (soát tổng)

	def test_task6_hai_noi_rut_phien_ban_khop_nhau(self):
		"""Hai nơi rút số hiệu từ tên file — `vo.js` (máy quét) và `cai_app.py`
		(máy chủ) — phải cho CÙNG một kết quả trên cùng một bảng tên.

		VÌ SAO PHẢI ĐỐI CHIẾU CHỨ KHÔNG KIỂM RIÊNG: hai bên dùng kết quả cho hai
		việc trái ngược nhau. Máy chủ TỪ CHỐI tải lên khi không rút được; máy quét
		IM LẶNG khi không rút được. Lệch nhau một ca là ca tệ nhất có thể: máy chủ
		nhận file, còn mọi máy quét thì im — tức "đã phát hành" mà không máy nào
		được nhắc, và không một dấu hiệu nào ở đâu cả.

		Đọc biểu thức THẲNG TỪ `vo.js` chứ không chép lại vào đây: chép lại là dựng
		thêm một nguồn thứ ba, và bài test sẽ xanh trong khi hai file thật đã trôi
		khỏi nhau. Cú pháp regex của đoạn này (`\\d{1,3}`, `(?=…)`, `|`) giống nhau ở
		JS và Python nên dịch được một-một.

		BẢNG TÊN gồm cả ca THẬT đang nằm trên máy chủ thử
		(`miyano-pda-1.0-kho-2026-09-24.apk`, đo bằng curl 25/09/2026) và ba cách
		viết NGÀY bằng dấu chấm mà vòng soát tổng (T6-1) tìm ra."""
		import re

		from erpnext.warehouse_operations.vitri.cai_app import _phien_ban_tu_ten

		sach = self._bo_chu_thich_giu_chuoi(self._ma_kho_pda("vo.js"))
		m = re.search(r"/miyano-pda-\((.+?)\)\(\?=(.+?)\)/i\.exec", sach)
		self.assertIsNotNone(m, "không tìm thấy biểu thức rút phiên bản trong vo.js")
		# `\\.` trong JS literal giữ nguyên nghĩa trong Python; `$` cũng vậy.
		tu_js = re.compile(f"miyano-pda-({m.group(1)})(?={m.group(2)})", re.I)

		BANG = [
			("miyano-pda-1.0-release.apk", "1.0"),
			("miyano-pda-1.10-release.apk", "1.10"),
			("miyano-pda-0.9-release.apk", "0.9"),
			("miyano-pda-9.9-release.apk", "9.9"),
			("miyano-pda-1.0.apk", "1.0"),
			("miyano-pda-1.0_kho.apk", "1.0"),
			("MIYANO-PDA-1.1-RELEASE.APK", "1.1"),
			# Ca THẬT đang nằm trên máy chủ thử: người phát hành dán NGÀY vào đuôi.
			("miyano-pda-1.0-kho-2026-09-24.apk", "1.0"),
			# Ba cách viết NGÀY — cả ba PHẢI rớt (T6-1).
			("miyano-pda-2026-09-24-ban-thang-9.apk", ""),
			("miyano-pda-2026.09.24.apk", ""),
			("miyano-pda-25.09.2026-ban-moi.apk", ""),
			("miyano-pda-24.09.26.apk", ""),
			# Lệch khuôn.
			("miyano-pda-1.2.3-release.apk", ""),
			("miyano-pda-1.apk", ""),
			("miyano-pda-v1.1.apk", ""),
			("ban-cai-thang-chin.apk", ""),
			("", ""),
		]
		for ten, mong_doi in BANG:
			khop = tu_js.search(ten)
			js = khop.group(1) if khop else ""
			py = _phien_ban_tu_ten(ten)
			self.assertEqual(js, mong_doi, f"vo.js rút SAI từ {ten!r}")
			self.assertEqual(py, mong_doi, f"cai_app.py rút SAI từ {ten!r}")
			self.assertEqual(js, py, f"hai nơi rút LỆCH nhau ở {ten!r}: js={js!r} py={py!r}")

	def test_task6_chan_ten_ban_cai_sai_ngay_luc_tai_len(self):
		"""LỚP 1 của "buộc hợp đồng ngầm lộ ra": tên bản cài không mang số hiệu thì
		bị TỪ CHỐI ngay lúc tải lên, lúc còn có người đang nhìn màn hình.

		Trước vòng này, khuôn tên chỉ là một dòng chữ trong `pda_app/README.md`.
		Phá nó thì dải nhắc nâng cấp im lặng trên MỌI máy, và hậu quả lộ ra hàng
		tuần sau, ngoài kho, dưới dạng "sao máy em không thấy bản mới".

		Bài kiểm CẢ HAI nửa, vì nửa nào thiếu cũng làm nửa kia vô nghĩa: hàm có từ
		chối đúng không, VÀ nó có thật sự được `hooks.py` gọi không."""
		from erpnext.warehouse_operations.vitri.cai_app import chan_ten_ban_cai_sai

		moc = frappe.get_hooks("doc_events").get("File", {}).get("validate", [])
		if isinstance(moc, str):
			moc = [moc]
		self.assertIn(
			"erpnext.warehouse_operations.vitri.cai_app.chan_ten_ban_cai_sai",
			moc,
			"hàm chặn KHÔNG được đăng ký trong hooks.py — nó không bao giờ chạy",
		)

		def thu(ten):
			# BẮT `Exception` RỒI KHẲNG ĐỊNH TRÊN NỘI DUNG CÂU, không bắt đích danh
			# `frappe.ValidationError`: `frappe.throw()` không khai `exc` nên hôm nay
			# nó ném đúng lớp đó — nhưng ai thêm `exc=frappe.PermissionError` vào
			# `chan_ten_ban_cai_sai` sẽ làm bài này ERROR (ngoại lệ lọt ra ngoài) thay
			# vì FAIL, và một bài "hỏng" đọc như một bài test sai chứ không như một
			# hành vi đã đổi. Thứ bài này canh là "CÓ chặn hay không", không phải
			# "chặn bằng lớp ngoại lệ nào".
			try:
				chan_ten_ban_cai_sai(frappe._dict(file_name=ten))
				return "cho qua"
			except Exception as e:
				self.assertIn(
					"miyano-pda-",
					frappe.utils.strip_html(str(e)),
					f"chặn {ten!r} nhưng câu từ chối KHÔNG nói khuôn tên đúng — "
					"người phát hành không biết phải sửa thành gì",
				)
				return "chan"

		# PHẢI CHẶN — tên là bản cài PDA nhưng không rút được số hiệu.
		for ten in (
			"miyano-pda-thang-9.apk",
			"miyano-pda-2026.09.24.apk",
			"miyano-pda-24.09.26.apk",
			"ban-cai-pda-moi.apk",
		):
			self.assertEqual(thu(ten), "chan", f"{ten!r} phải bị từ chối lúc tải lên")

		# PHẢI CHO QUA — hoặc là tên đúng khuôn, hoặc KHÔNG PHẢI bản cài PDA.
		# Vế sau quan trọng ngang vế trước: hook này chạy cho MỌI `File` của cả hệ
		# thống, nên một câu nói nhầm ở đây là chặn người ta tải ảnh/PDF lên.
		for ten in (
			"miyano-pda-1.0-release.apk",
			"miyano-pda-1.0-kho-2026-09-24.apk",
			"anh-kho-hang.png",
			"bao-gia-thang-9.pdf",
			"ung-dung-khac.apk",
			"",
		):
			self.assertEqual(thu(ten), "cho qua", f"{ten!r} KHÔNG được bị chặn")

	def test_task6_ban_cai_moi_nhat_noi_ro_khi_khong_doc_duoc_so_hieu(self):
		"""LỚP 2: `ban_cai_moi_nhat` trả thêm `phien_ban` và `ly_do`.

		App cố ý IM khi không đọc được số hiệu (không nhắc bừa còn hơn nhắc sai) —
		nhưng "im" nghĩa là KHÔNG AI BIẾT NÓ HỎNG. Hai ô này là chỗ sự im lặng đó
		có một cái tên, cho các bản cài đã nằm sẵn trên máy chủ TỪ TRƯỚC khi có
		hàng rào lớp 1."""
		from erpnext.warehouse_operations.vitri.cai_app import _phien_ban_tu_ten, ban_cai_moi_nhat

		ban = ban_cai_moi_nhat()
		if not ban:
			self.skipTest("site này chưa có bản cài nào — không có gì để đối chiếu")
		self.assertIn("phien_ban", ban)
		self.assertIn("ly_do", ban)
		self.assertEqual(ban["phien_ban"], _phien_ban_tu_ten(ban["ten"]))
		# Hai ô này là MỘT sự thật nói hai chiều — rỗng/khác rỗng phải ngược nhau.
		self.assertEqual(
			bool(ban["phien_ban"]),
			not bool(ban["ly_do"]),
			f"phien_ban và ly_do nói hai câu khác nhau: {ban}",
		)

	def test_task6_403_nghiep_vu_khong_duoc_coi_la_loi_danh_tinh(self):
		"""N2 — `goi()` chỉ được giết khoá máy khi máy chủ nói ĐÚNG LÀ danh tính.

		Đo trên máy chủ thật (25/09/2026): khoá API sai → 401 `AuthenticationError`;
		lỗi quyền nghiệp vụ → 403 `PermissionError`. `the_pda.kiem_khoa_may` — hàng
		rào mã máy — ném `frappe.AuthenticationError`, tức **401**.

		Bài này canh HAI HỢP ĐỒNG mà một cổng trình duyệt không nhìn thấy:
		1. hằng `_EXC_DANH_TINH` trong `vo.js` đúng bằng tên lớp ngoại lệ mà
		   `the_pda.py` thật sự ném ở chỗ từ chối mã máy;
		2. hai lớp ngoại lệ đó vẫn ánh xạ sang đúng 401/403 trong Frappe — nếu
		   Frappe đổi, phép phân biệt của `goi()` mất nghĩa mà không ai biết.

		Hàng rào HÀNH VI (403 không giết khoá, 401 vẫn giết) nằm ở
		`scripts/kiem_giao_dien/kiem_goi_mang.js`, nửa NATIVE."""
		import re

		self.assertEqual(frappe.AuthenticationError.http_status_code, 401)
		self.assertEqual(frappe.PermissionError.http_status_code, 403)

		sach = self._bo_chu_thich_giu_chuoi(self._ma_kho_pda("vo.js"))
		m = re.search(r'_EXC_DANH_TINH\s*=\s*"([^"]+)"', sach)
		self.assertIsNotNone(m, "vo.js không còn khai _EXC_DANH_TINH")

		goc = frappe.get_app_path("erpnext")
		with open(os.path.join(goc, "warehouse_operations", "vitri", "the_pda.py"), encoding="utf-8") as f:
			ma_may_chu = f.read()
		nem = re.search(
			r"frappe\.throw\(\s*_\(CAU_KHOA_MAY_HONG\)\s*,\s*frappe\.(\w+)\s*,?\s*\)", ma_may_chu
		)
		self.assertIsNotNone(
			nem, "không tìm thấy chỗ the_pda.py từ chối mã máy — vo.js đang phân biệt theo cái gì?"
		)
		self.assertEqual(
			m.group(1),
			nem.group(1),
			f"vo.js coi '{m.group(1)}' là lỗi danh tính, nhưng the_pda.py ném "
			f"'{nem.group(1)}' — một lượt thu hồi sẽ KHÔNG giết được khoá đã cất, "
			"hoặc một lỗi quyền nghiệp vụ sẽ giết nhầm nó.",
		)

	def test_task6_www_va_assets_public_khop_tung_byte(self):
		"""V8 — BẢN THỨ BA. Ba cổng nghiệm thu đọc `pda_app/www/`, nhưng APK đóng
		gói từ `android/app/src/main/assets/public/`.

		Cảnh hỏng: sửa giao diện → `dong-goi.sh` → ba cổng XANH → `assembleRelease`
		mà quên `npx cap sync` → APK mang bản cũ KÈM một chứng nhận xanh đầy đủ.
		Từ vòng sửa cuối, `dong-goi.sh` tự chép sang thư mục đó (và xoá file thừa),
		nên bài này canh rằng phép chép ấy còn ở đó và còn đúng.

		KHÁC `test_task6_apk_mang_dung_ban_dong_goi`: bài kia cần một APK đã dựng
		(và tự bỏ qua khi chưa có), bài này chạy được ngay sau mỗi `dong-goi.sh`."""
		import hashlib

		goc = self._goc_kho()
		www = os.path.join(goc, "pda_app", "www")
		assets = os.path.join(goc, "pda_app", "android", "app", "src", "main", "assets", "public")
		if not os.path.isdir(assets):
			self.skipTest("chưa có dự án android — không có bản thứ ba để đối chiếu")

		def bam_cay(goc_cay):
			ra = {}
			for thu_muc, _, ds in os.walk(goc_cay):
				for t in ds:
					duong = os.path.join(thu_muc, t)
					with open(duong, "rb") as f:
						ra[os.path.relpath(duong, goc_cay)] = hashlib.md5(f.read()).hexdigest()
			return ra

		# `npx cap sync` TỰ SINH mấy file này vào `assets/public/`; chúng không có
		# trong `www/` và không thuộc về `dong-goi.sh`. Bỏ qua ĐÍCH DANH, dùng chung
		# một danh sách với `scripts/pda/don_assets_public.py` — không bỏ qua bằng
		# một luật mơ hồ kiểu "file lạ nào cũng được": bất kỳ file lạ NÀO KHÁC vẫn
		# phải làm bài này đỏ.
		from scripts.pda.don_assets_public import CUA_CAPACITOR

		a, b = bam_cay(www), bam_cay(assets)
		b = {
			t: v
			for t, v in b.items()
			if t.split(os.sep)[0] not in CUA_CAPACITOR
		}
		thieu = sorted(set(a) - set(b))
		thua = sorted(set(b) - set(a))
		lech = sorted(t for t in set(a) & set(b) if a[t] != b[t])
		self.assertEqual(
			(thieu, thua, lech),
			([], [], []),
			f"assets/public/ KHÁC www/ — APK sẽ mang bản cũ. Thiếu: {thieu} · Thừa: {thua} · "
			f"Lệch: {lech}. Chạy lại scripts/pda/dong-goi.sh.",
		)

	def test_logo_loi_an_khoa_cu_chi_cham(self):
		"""Logo là nút của lối ẩn (bấm giữ 3 giây). Thiếu `touch-action: none` thì
		trên máy thật một cú xê dịch ngón tay rất nhỏ bị WebView coi là cử chỉ cuộn
		và phát `pointercancel` — `_gan_loi_an` huỷ hẹn, hộp nhập không bao giờ
		hiện. Cổng Playwright bấm giữ bằng CHUỘT nên không bắt được lỗi này; bài
		này giữ luật CSS đó khỏi bị xoá (29/09/2026: thủ kho giữ logo mà không mở
		được lối ẩn để đổi sang địa chỉ ngrok)."""
		import re

		with open(self._doc("public", "scss", "kho_pda.bundle.scss"), encoding="utf-8") as f:
			scss = f.read()
		khoi = re.search(r"\.man-the-logo\s*\{([^}]*)\}", scss)
		self.assertIsNotNone(khoi, "kho_pda.bundle.scss mất luật .man-the-logo")
		self.assertRegex(khoi.group(1), r"touch-action:\s*none")

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
# Workspace: `name` quyết định đường dẫn (`/app/vị-trí-kho`). Mọi workspace
# khác trên site đều có `name` trùng `title`, nên đặt `name` không dấu trong
# khi `title` có dấu là tự đẻ ra một đường dẫn không ai đoán được — người dùng
# đọc tiêu đề "Vị trí kho" rồi gõ `/app/vị-trí-kho` và nhận trang "Not found"
# (đã xảy ra hai lần, 13-14/09/2026). Đổi lại cho khớp quy ước của site; tiền
# lệ sẵn có trong repo: `erpnext/selling/workspace/bán_hàng/`.
#
# Module: PHẢI giữ ASCII. `frappe.scrub()` biến tên module thành đường dẫn gói
# Python, nên tên module có dấu sẽ sinh thư mục và module Python non-ASCII.
TEN_WORKSPACE = "Vị trí kho"
TEN_MODULE = "Vi Tri Kho"
DUONG_DAN_JS = "public/js/vi_tri_kho/warehouse.js"
# Hằng RIÊNG cho form lô — không dùng chung `DUONG_DAN_JS`: hai nút gắn vào hai
# doctype khác nhau, gộp một hằng thì một lần đổi đường dẫn sẽ kéo bài kia xanh
# giả theo.
DUONG_DAN_JS_LO = "public/js/vi_tri_kho/batch.js"


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
		không dấu thì trang vẫn chạy bình thường ở `/app/vi-tri-kho` — không
		lỗi, không log — chỉ là người đọc tiêu đề "Vị trí kho" gõ
		`/app/vị-trí-kho` sẽ nhận "Not found". Đúng kiểu hỏng im lặng.
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
			dt = "Report" if l.link_type == "Report" else "DocType"
			if not frappe.db.exists(dt, l.link_to):
				hong.append(f"{l.label} -> {dt} {l.link_to!r}")
		self.assertEqual(hong, [], f"liên kết trỏ vào hư không: {hong}")

	def test_moi_loi_tat_deu_tro_toi_thu_co_that(self):
		ws = frappe.get_doc("Workspace", TEN_WORKSPACE)
		hong = []
		for s in ws.shortcuts:
			dt = "Report" if s.type == "Report" else "DocType"
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

	Mất dòng `"Batch": "public/js/vi_tri_kho/batch.js"` trong `doctype_js` thì
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
		duong_dan = frappe.get_app_path("erpnext", "public", "js", "vi_tri_kho", "in_nhan_lo.js")
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


DUONG_DAN_JS_PHIEU_NHAP = "public/js/vi_tri_kho/purchase_receipt.js"
DUONG_DAN_JS_MAT_HANG = "public/js/vi_tri_kho/item.js"


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
		from erpnext.vi_tri_kho.vitri.phieu_nhap import NHAN_NUT_NHAP_LO

		duong_dan = frappe.get_app_path("erpnext", *DUONG_DAN_JS_PHIEU_NHAP.split("/"))
		with open(duong_dan, encoding="utf-8") as f:
			ma_js = f.read()
		self.assertIn(f'"{NHAN_NUT_NHAP_LO}"', ma_js)

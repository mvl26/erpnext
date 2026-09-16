"""Hai lối vào giao diện của module: Workspace và nút trên phiếu Warehouse.

Cả hai đều hỏng theo kiểu KHÔNG ném lỗi — đó là lý do chúng đáng có bài riêng:

- Workspace trỏ tới một doctype/báo cáo sai tên thì Frappe vẫn dựng trang,
  chỉ là ô đó bấm vào ra trang trắng. Không log, không lỗi.
- Nút trên Warehouse gắn qua `doctype_js` trong `erpnext/hooks.py` — cùng file
  upstream với móc `Stock Ledger Entry`, nên cùng chịu rủi ro "merge giải sai
  thì mất lặng lẽ". Mất nút thì thủ kho không còn đường vào từ phiếu kho, mà
  chẳng có gì báo.
"""

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

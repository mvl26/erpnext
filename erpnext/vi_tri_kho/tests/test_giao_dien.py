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

TEN_WORKSPACE = "Vi Tri Kho"
DUONG_DAN_JS = "public/js/vi_tri_kho/warehouse.js"


class TestWorkspace(FrappeTestCase):
	def test_workspace_ton_tai_va_thuoc_module(self):
		self.assertEqual(
			frappe.db.get_value("Workspace", TEN_WORKSPACE, "module"),
			TEN_WORKSPACE,
			"Workspace phải tồn tại và thuộc module Vi Tri Kho",
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

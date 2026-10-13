"""Phân quyền — điều chịu lực là những quyền KHÔNG có.

Sổ vị trí đáng tin được là nhờ không vai trò nào có create/write/delete;
chỉ engine ghi qua ignore_permissions. Và không doctype nào của app này
được có DocPerm cho Customer hay Website User — bài học từ kho khách hàng:
thiếu DocPerm mới là thứ chịu lực, hook phân quyền một mình không đủ.

GHI ĐÈ so với brief gốc (review advisor sau khi chạy bộ đầy đủ):
brief để `test_khong_xoa_duoc_dong_so` tự `skipTest` khi chưa có dòng sổ
nào — trên site sạch (module này chạy đơn lẻ) điều đó luôn đúng, nên bài
khoá yêu cầu bắt buộc #1 ("Location Ledger Entry không xoá được") không
bao giờ thực sự chạy phần assert. Sửa: lớp `TestSoKhongAiGhiDuoc` tự dựng
dữ liệu của mình (`_don_sach` + `bat(KHO)`, cùng cách `test_bao_cao.py`
làm) để luôn có ít nhất một dòng sổ thật mà thử xoá.

Thêm kiểm `Custom DocPerm` (site-level override, doctype RIÊNG với
`DocPerm` chuẩn của app) cho cả hai yêu cầu — một override thêm ở tầng
site có thể mở lại đúng lỗ hổng mà `DocPerm` trong JSON đã khoá, và bài
test chỉ đọc `DocPerm` sẽ không thấy.

VÒNG SỬA 1/5 (review điều phối sau khi Task 15 "xong"):

1. `DOCTYPE_CUA_APP` bản trước là danh sách TĨNH hard-code 5 tên. Người
   review đột biến: thêm DocPerm `Customer` cho một doctype thứ 6 giả
   định của app → không bài nào đỏ, vì danh sách tĩnh không biết doctype
   đó tồn tại. Đây đúng họ lỗi "xanh mà không kiểm gì" đã bắt nhiều lần
   trong dự án này. Sửa: suy danh sách ĐỘNG từ `frappe.get_all("DocType",
   filters={"module": "Warehouse Operations"})` — thêm doctype thứ 6 vào app thì
   danh sách này tự thấy nó, không cần sửa test. Có khẳng định danh sách
   suy ra KHÔNG rỗng (nếu truy vấn hỏng và trả rỗng thì vòng lặp không
   chạy và bài lại xanh vô nghĩa — đúng cái bẫy vừa sửa ở `skipTest`
   của `test_khong_xoa_duoc_dong_so`).

2. Thêm `TestBaoCaoKhongMoChoCustomer`: không bài nào trước đó khoá trực
   tiếp `roles` trong hai file `.json` của report — framework đã chặn
   gián tiếp qua `frappe.desk.query_report.run` (kiểm `doc.is_permitted()`
   và `frappe.has_permission(ref_doctype, "report")`), nên đây là thiếu
   MỘT LỚP phòng thủ, không phải lỗ hổng sống — nhưng rẻ, thêm luôn.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.warehouse_operations.tests.test_bat_kho import _don_sach
from erpnext.warehouse_operations.vitri.bat_kho import bat

KHO = "Kho Miyano - MYN"


def _doctype_cua_app():
	"""Suy ĐỘNG từ module, không hard-code — xem VÒNG SỬA 1 ở docstring đầu file."""
	return frappe.get_all("DocType", filters={"module": "Warehouse Operations"}, pluck="name")


class TestSoKhongAiGhiDuoc(FrappeTestCase):
	def setUp(self):
		_don_sach(KHO)
		bat(KHO)

	def tearDown(self):
		_don_sach(KHO)

	def test_khong_vai_tro_nao_duoc_ghi_so(self):
		for dt in ("Location Ledger Entry", "Location Balance"):
			quyen = frappe.get_all(
				"DocPerm", filters={"parent": dt}, fields=["role", "create", "write", "delete"]
			)
			self.assertTrue(quyen, f"{dt} phải có ít nhất quyền đọc")
			for q in quyen:
				self.assertFalse(q.create, f"{dt}: {q.role} không được có quyền tạo")
				self.assertFalse(q.write, f"{dt}: {q.role} không được có quyền sửa")
				self.assertFalse(q.delete, f"{dt}: {q.role} không được có quyền xoá")

			# Custom DocPerm là bảng override RIÊNG (site-level), Frappe cộng
			# dồn nó với DocPerm chuẩn khi tính quyền thật — kiểm ở trên
			# xong mà bỏ qua bảng này thì một override thêm sau (qua UI Role
			# Permission Manager) có thể mở lại đúng lỗ hổng vừa khoá mà bài
			# test không hề hay biết.
			override = frappe.get_all(
				"Custom DocPerm", filters={"parent": dt}, fields=["role", "create", "write", "delete"]
			)
			for q in override:
				self.assertFalse(q.create, f"{dt}: Custom DocPerm của {q.role} không được có quyền tạo")
				self.assertFalse(q.write, f"{dt}: Custom DocPerm của {q.role} không được có quyền sửa")
				self.assertFalse(q.delete, f"{dt}: Custom DocPerm của {q.role} không được có quyền xoá")

	def test_khong_xoa_duoc_dong_so(self):
		dong = frappe.get_all("Location Ledger Entry", filters={"kho": KHO}, limit=1, pluck="name")
		self.assertTrue(dong, "bat() vừa chạy ở setUp phải để lại ít nhất một dòng sổ")
		with self.assertRaises(frappe.ValidationError):
			frappe.delete_doc("Location Ledger Entry", dong[0], ignore_permissions=True)


class TestKhongLoRaCong(FrappeTestCase):
	def test_khong_doctype_nao_mo_cho_customer(self):
		doctype_cua_app = _doctype_cua_app()
		self.assertTrue(
			doctype_cua_app,
			"truy vấn DocType theo module 'Warehouse Operations' trả rỗng — tự nó là dấu hiệu "
			"truy vấn hỏng, không phải app không có doctype nào (không được để bài "
			"này im lặng bỏ qua vì danh sách rỗng)",
		)
		self.assertGreaterEqual(
			len(doctype_cua_app),
			5,
			f"phải thấy ít nhất 5 doctype đã biết của app, chỉ thấy {doctype_cua_app}",
		)
		for dt in doctype_cua_app:
			vai_tro = frappe.get_all("DocPerm", filters={"parent": dt}, pluck="role")
			vai_tro_override = frappe.get_all("Custom DocPerm", filters={"parent": dt}, pluck="role")
			for cam in ("Customer", "Website User", "All"):
				self.assertNotIn(
					cam,
					vai_tro,
					f"{dt} không được có DocPerm cho '{cam}' — xem docstring đầu file",
				)
				self.assertNotIn(
					cam,
					vai_tro_override,
					f"{dt} không được có Custom DocPerm (override site-level) cho '{cam}'",
				)


class TestPhienKhongDocDuoc(FrappeTestCase):
	"""Việc (D) (review điều phối, sau khi 147/147 bài "xong") — "Hình dạng
	9": `TestKhongLoRaCong` ở trên khẳng định trên BẢNG QUYỀN (`DocPerm`/
	`Custom DocPerm` — dữ liệu cấu hình), không phải trên PHIÊN thật. Hai
	thứ đó thường trùng nhau, nhưng KHÔNG PHẢI LOGIC KÉO THEO: bảng quyền
	đúng không tự động chứng minh `frappe.has_permission()` trả kết quả
	đúng cho một phiên cụ thể (có thể có `permission_query_conditions`,
	`has_permission` hook, hoặc site-level override khác đứng giữa hai thứ
	đó mà một bài chỉ đọc bảng không bao giờ chạm tới). Bài này set phiên
	thành MỘT Website User THẬT (khách cổng `miyano_portal`) rồi hỏi thẳng
	`frappe.has_permission()` — đúng câu hỏi mà framework tự hỏi khi phục vụ
	request thật, cho CẢ NĂM doctype (danh sách ĐỘNG, cùng lý do
	`_doctype_cua_app()`).
	"""

	WEBSITE_USER = "bvminhduc@demo.miyano"

	def test_website_user_khong_doc_duoc_bat_ky_doctype_nao(self):
		self.assertTrue(
			frappe.db.exists("User", self.WEBSITE_USER),
			"Cần tài khoản Website User thật trên site để bài này có ý nghĩa.",
		)
		doctype_cua_app = _doctype_cua_app()
		self.assertGreaterEqual(
			len(doctype_cua_app),
			5,
			f"phải thấy ít nhất 5 doctype đã biết của app, chỉ thấy {doctype_cua_app}",
		)

		frappe.set_user(self.WEBSITE_USER)
		try:
			for dt in doctype_cua_app:
				self.assertFalse(
					frappe.has_permission(dt, "read"),
					f"Phiên Website User KHÔNG được có quyền ĐỌC {dt}",
				)
		finally:
			frappe.set_user("Administrator")


def _report_cua_app():
	"""Suy ĐỘNG từ module, không hard-code — cùng lý do `_doctype_cua_app()`
	ở trên."""
	return frappe.get_all("Report", filters={"module": "Warehouse Operations"}, pluck="name")


class TestBaoCaoKhongMoChoCustomer(FrappeTestCase):
	"""Việc 3 (vòng sửa 1/5): không bài nào trước đó khoá trực tiếp `roles`
	trong hai file `.json` của report — chỉ đối chiếu bằng mắt với DocPerm
	của `Location Balance` trong report báo cáo. Framework đã chặn gián
	tiếp (`frappe.desk.query_report.run`), nên đây là thêm một lớp phòng
	thủ rẻ, không phải vá một lỗ hổng đang sống.

	VÒNG SỬA (review điều phối, Việc C, sau khi 147/147 bài "xong"): danh
	sách report bản trước hard-code ĐÚNG 2 tên ("Ton Kho Theo Vi Tri",
	"Hang Chua Xep Vi Tri") — bỏ SÓT đúng "Doi Soat Ton Vi Tri", báo cáo
	NHẠY CẢM NHẤT của app (đọc trực tiếp `doi_soat_kho`, số liệu tồn theo
	từng ô của toàn kho). Đột biến "thêm role Customer vào report Doi Soat
	Ton Vi Tri" không bài nào ở đây từng bắt được — CÙNG HỌ LỖI "xanh mà
	không kiểm gì" đã sửa ở `_doctype_cua_app()` (VÒNG SỬA 1/5, mục 1 phía
	trên) cho DocPerm. Sửa CÙNG cách: suy danh sách report ĐỘNG từ
	`frappe.get_all("Report", filters={"module": "Warehouse Operations"})` — thêm một
	report thứ tư vào app thì bài này tự thấy nó, không cần sửa test.
	"""

	def test_report_roles_khong_co_customer(self):
		report_cua_app = _report_cua_app()
		self.assertTrue(
			report_cua_app,
			"truy vấn Report theo module 'Warehouse Operations' trả rỗng — tự nó là dấu hiệu truy "
			"vấn hỏng, không phải app không có report nào",
		)
		self.assertGreaterEqual(
			len(report_cua_app),
			3,
			f"phải thấy ít nhất 3 report đã biết của app, chỉ thấy {report_cua_app}",
		)
		for ten_report in report_cua_app:
			doc = frappe.get_doc("Report", ten_report)
			vai_tro = [r.role for r in doc.roles]
			self.assertTrue(vai_tro, f"Report {ten_report} phải có ít nhất một role")
			for cam in ("Customer", "Website User", "All"):
				self.assertNotIn(
					cam,
					vai_tro,
					f"Report {ten_report} không được có role '{cam}'",
				)

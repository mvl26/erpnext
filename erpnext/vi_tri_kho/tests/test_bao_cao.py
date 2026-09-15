"""Hai báo cáo vận hành.

"Hàng chưa xếp vị trí" là danh sách việc của thủ kho — nó biến việc bỏ sót
khai vị trí thành hữu hình thay vì thành lỗi. Không có báo cáo này thì ô
CHUA-XEP âm thầm phình ra và không ai biết.

VÒNG SỬA 1/5 (review điều phối, Việc 2): thêm
`test_thu_tu_theo_thu_tu_lay_hang_khong_theo_alphabet_o`. Đột biến của
người review (xoá/đảo `order by ifnull(sl.thu_tu_lay_hang, 0) asc` trong
`ton_kho_theo_vi_tri.py`) không bị bài nào bắt — đúng khuyết tật đã trả
giá thật ở Task 8 (bảy bài FEFO xanh mà không khoá được cột quyết định vì
tên ô tình cờ trùng thứ tự alphabet). Bài mới đặt tên ô MÂU THUẪN với
`thu_tu_lay_hang` (ô "Z..." phải đứng TRƯỚC ô "A..." vì thu_tu_lay_hang
nhỏ hơn) để không thể xanh nhờ khoá sắp xếp phụ (tên ô, vốn cũng có mặt
trong `order by` làm khoá phá vỡ đồng hạng).

TASK 6 (2026-09-11): báo cáo trả thêm dòng NÚT NHÓM (gộp cộng dồn từ
`parent_storage_location`, xem docstring `ton_kho_theo_vi_tri.py`) và đổi
dạng dòng từ list sang dict (`d["o"]` thay cho `d[0]`) để mang thêm cột
`parent_o`/`is_group`. `test_thu_tu_theo_thu_tu_lay_hang_...` phải lọc
`not d.get("is_group")` trước khi so khớp danh sách CHÍNH XÁC 2 phần tử —
không lọc thì các dòng nút nhóm tự sinh (tổ tiên của hai ô test) chen vào
làm độ dài danh sách lệch, bài đỏ giả vì lý do không liên quan tới thứ tự.

`test_gop_theo_khu_bang_tong_cac_o_la`: GHI ĐÈ so với snippet gốc ở
task-6-brief.md — brief dựng vế "tổng ô lá" bằng cách lọc lại từ chính
`dong` (báo cáo tự so với báo cáo). Theo chuẩn nghiệm thu của kế hoạch
(so cả hai vế từ CÙNG báo cáo là bài rỗng — xanh cả khi báo cáo cộng sai
nếu cả hai vế cùng sai theo nhau), vế đối chiếu ở đây cộng THẲNG từ
`tabLocation Balance` bằng SQL riêng, không đọc lại `dong`. Xem
task-6-report.md, mục "đột biến khoá thêm" cho cặp đột biến chứng minh
bài yếu (dong-vs-dong) xanh giả trong khi bài này đỏ đúng.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from erpnext.vi_tri_kho.tests.test_bat_kho import _don_sach
from erpnext.vi_tri_kho.tests.test_hook_nhap import _nhap_kho as _nhap
from erpnext.vi_tri_kho.tests.test_hook_nhap import _tao_item
from erpnext.vi_tri_kho.vitri import kho as vk
from erpnext.vi_tri_kho.vitri.bat_kho import bat

KHO = "Kho Miyano - MYN"


class TestBaoCaoTonTheoViTri(FrappeTestCase):
	def setUp(self):
		_don_sach(KHO)
		bat(KHO)

	def tearDown(self):
		_don_sach(KHO)

	def test_chay_duoc_va_co_dong(self):
		from erpnext.vi_tri_kho.report.ton_kho_theo_vi_tri.ton_kho_theo_vi_tri import execute

		cot, dong = execute({"kho": KHO})
		self.assertTrue(cot)
		self.assertTrue(dong, "kho vừa bật có tồn nên phải có dòng")

	def test_khong_hien_o_het_hang(self):
		from erpnext.vi_tri_kho.report.ton_kho_theo_vi_tri.ton_kho_theo_vi_tri import execute

		frappe.db.sql("update `tabLocation Balance` set so_luong = 0 where kho=%s", (KHO,))
		_, dong = execute({"kho": KHO})
		self.assertEqual(dong, [])

	def test_thu_tu_theo_thu_tu_lay_hang_khong_theo_alphabet_o(self):
		"""Khoá cột sort THẬT (`thu_tu_lay_hang`), không phải khoá phụ (tên ô
		trùng alphabet với nó) — xem VÒNG SỬA 1 ở docstring đầu file.

		"Z-..." mang thu_tu_lay_hang=1 (phải đứng TRƯỚC), "A-..." mang
		thu_tu_lay_hang=2 (phải đứng SAU) — cố ý MÂU THUẪN với thứ tự
		alphabet của tên ô, nên nếu code lỡ sắp theo `lb.o asc` thay vì
		`thu_tu_lay_hang asc` thì thứ tự trả về sẽ ĐẢO NGƯỢC và bài này bắt
		được ngay, không cần nhìn vào SQL.
		"""
		from erpnext.vi_tri_kho.report.ton_kho_theo_vi_tri.ton_kho_theo_vi_tri import execute

		item = _tao_item("_Test BC Thu Tu Lay Hang")
		o_truoc = "9Z99010101"  # thu_tu_lay_hang=1, alphabet đứng SAU "A-..."
		o_sau = "9Z01010101"  # thu_tu_lay_hang=2, alphabet đứng TRƯỚC "Z-..."

		for ma_o, thu_tu in ((o_truoc, 1), (o_sau, 2)):
			if not frappe.db.exists("Storage Location", ma_o):
				frappe.get_doc(
					{
						"doctype": "Storage Location",
						"ma_o": ma_o,
						"kho": KHO,
						"thu_tu_lay_hang": thu_tu,
					}
				).insert(ignore_permissions=True)

		for ma_o in (o_truoc, o_sau):
			frappe.get_doc(
				{
					"doctype": "Location Balance",
					"o": ma_o,
					"kho": KHO,
					"vat_tu": item,
					"so_luong": 3,
				}
			).insert(ignore_permissions=True)

		_, dong = execute({"kho": KHO, "vat_tu": item})
		# TASK 6: lọc bỏ các dòng NÚT NHÓM tự sinh (tổ tiên của o_truoc/o_sau)
		# trước khi so khớp — chúng cũng lọt vào `dong` từ Task 6 trở đi,
		# không liên quan gì tới điều bài này khoá (thứ tự các Ô LÁ).
		thu_tu_o = [d["o"] for d in dong if not d.get("is_group")]
		self.assertEqual(
			thu_tu_o,
			[o_truoc, o_sau],
			f"phải sắp theo thu_tu_lay_hang (1 rồi 2: {o_truoc} rồi {o_sau}), không "
			f"theo alphabet tên ô (alphabet sẽ cho '{o_sau}' trước '{o_truoc}', "
			f"ngược lại). Thứ tự thấy được: {thu_tu_o}",
		)

	def test_gop_theo_khu_bang_tong_cac_o_la(self):
		"""Vế đối chiếu KHÔNG lấy từ chính báo cáo: cộng thẳng `Location Balance`
		bằng SQL riêng trong bài kiểm — xem lý do ở docstring đầu file (GHI ĐÈ
		so với brief).

		VÒNG SỬA 1/5 (review điều phối): hai vế PHẢI cùng phạm vi. Vế báo cáo
		lọc `vat_tu=item`; vế SQL đối chiếu ban đầu KHÔNG lọc `vat_tu` — hôm
		đó không đỏ giả chỉ vì trong transaction chưa có mặt hàng thứ hai nào
		trùng tiền tố `9Z`, thuần may rủi, không phải do thiết kế đúng. Seed
		thêm `item_khac` (mặt hàng KHÁC, không liên quan tới `item`) vào một
		ô `9Z…` để buộc hai vế phải cùng lọc `vat_tu` mới khớp — xem
		task-6-report.md, "Vòng sửa 1/5" cho cặp đo (SQL không lọc `vat_tu`
		hỏng thật với fixture này, SQL có lọc thì đúng)."""
		from erpnext.vi_tri_kho.report.ton_kho_theo_vi_tri import ton_kho_theo_vi_tri

		item = _tao_item("_Test BC Gop Theo Khu")
		for ma_o, so_luong in (
			("9Z50010101", 5),
			("9Z50010102", 7),
			("9Z51010101", 3),
		):
			if not frappe.db.exists("Storage Location", ma_o):
				frappe.get_doc({"doctype": "Storage Location", "ma_o": ma_o, "kho": KHO}).insert(
					ignore_permissions=True
				)
			frappe.get_doc(
				{
					"doctype": "Location Balance",
					"o": ma_o,
					"kho": KHO,
					"vat_tu": item,
					"so_lo": "",
					"so_luong": so_luong,
				}
			).insert(ignore_permissions=True)

		# Mặt hàng THỨ HAI, không liên quan, cùng chung một ô "9Z…" của
		# `item` — chỉ để buộc lộ ra việc hai vế phải cùng lọc `vat_tu`.
		item_khac = _tao_item("_Test BC Gop Theo Khu Khac")
		frappe.get_doc(
			{
				"doctype": "Location Balance",
				"o": "9Z50010101",
				"kho": KHO,
				"vat_tu": item_khac,
				"so_lo": "",
				"so_luong": 1000,
			}
		).insert(ignore_permissions=True)

		_, dong = ton_kho_theo_vi_tri.execute({"kho": KHO, "vat_tu": item})
		theo_o = {d["o"]: d for d in dong}

		# Vế đối chiếu ĐỘC LẬP: đi thẳng vào tabLocation Balance, không đọc
		# lại `dong`/`theo_o` ở trên — nếu báo cáo cộng sai (ví dụ bỏ sót
		# một dòng thật), vế này vẫn thấy đúng số thật trong CSDL. PHẢI lọc
		# cùng `vat_tu=item` như vế báo cáo — không lọc thì `item_khac` (1000
		# đơn vị, không liên quan) lẫn vào, hai vế lệch phạm vi.
		tong_doc_lap = frappe.db.sql(
			"select sum(so_luong) from `tabLocation Balance` where kho=%s and o like '9Z%%' and vat_tu=%s",
			(KHO, item),
		)[0][0]

		self.assertIn("9Z", theo_o, "báo cáo phải trả dòng nút nhóm Khu '9Z' gộp tồn")
		self.assertAlmostEqual(flt(theo_o["9Z"]["so_luong"]), flt(tong_doc_lap), places=4)

		# VÒNG SỬA (review advisor): khoá đúng "từng cấp", không chỉ cấp Khu —
		# vế đối chiếu ở đây dựng TAY từ chính fixture (hai nhánh biết trước
		# giá trị), không đọc lại `dong`/SQL. Không có hai dòng dưới, một đột
		# biến cộng dồn KHÔNG theo đúng nhánh cha-con (ví dụ cộng vào MỌI nút
		# đã biết thay vì đi theo chuỗi `parent_o` của từng lá) vẫn có thể giữ
		# đúng tổng Khu "9Z" (vì "9Z" là tổ tiên chung của cả hai nhánh) mà sai
		# ở cấp trong — xem task-6-report.md, mục đột biến #2.
		self.assertIn("9Z50", theo_o, "phải có dòng nút nhóm Dãy '9Z50'")
		self.assertIn("9Z51", theo_o, "phải có dòng nút nhóm Dãy '9Z51'")
		self.assertAlmostEqual(
			flt(theo_o["9Z50"]["so_luong"]), 12.0, places=4, msg="9Z50 = 5+7, KHÔNG lẫn 9Z51"
		)
		self.assertAlmostEqual(
			flt(theo_o["9Z51"]["so_luong"]), 3.0, places=4, msg="9Z51 riêng, KHÔNG lẫn 9Z50"
		)

	def test_moi_dong_co_indent_va_xep_cha_truoc_con(self):
		"""KHOÁ đúng thứ Frappe THẬT SỰ dùng để vẽ cây, không phải thứ brief
		nói tới.

		Đọc mã nguồn gói `frappe-datatable` (`datamanager.js`/`rowmanager.js`,
		xem task-6-report.md): thư viện suy `isLeaf`/mối quan hệ cha-con
		HOÀN TOÀN từ (a) trường số `indent` trên MỖI dòng và (b) THỨ TỰ CÁC
		DÒNG TRONG MẢNG (dòng cha phải đứng ngay trước cụm con của nó) —
		KHÔNG hề đọc `parent_field`/`name_field` khai trong `.js` để tự dựng
		cây. `query_report.js` chỉ coi báo cáo là cây
		(`this.tree_report = this.data.some(d => "indent" in d)`) khi có ít
		nhất một dòng mang khoá `indent`. Thiếu `indent` → dù `.js` đã khai
		`tree: true` báo cáo vẫn hiện PHẲNG. Đây là lỗ hổng brief không nói
		tới; không có bài này, việc "trả thêm parent_o" (đúng theo brief) có
		thể xanh hết mà báo cáo thực tế không hiện dạng cây.
		"""
		from erpnext.vi_tri_kho.report.ton_kho_theo_vi_tri import ton_kho_theo_vi_tri

		item = _tao_item("_Test BC Indent Cay")
		for ma_o, so_luong in (("9Z50010101", 5),):
			if not frappe.db.exists("Storage Location", ma_o):
				frappe.get_doc({"doctype": "Storage Location", "ma_o": ma_o, "kho": KHO}).insert(
					ignore_permissions=True
				)
			frappe.get_doc(
				{"doctype": "Location Balance", "o": ma_o, "kho": KHO, "vat_tu": item, "so_luong": so_luong}
			).insert(ignore_permissions=True)

		_, dong = ton_kho_theo_vi_tri.execute({"kho": KHO})
		do_sau = {d["o"]: d.get("indent") for d in dong}
		vi_tri = {d["o"]: i for i, d in enumerate(dong)}

		for ten in ("9Z", "9Z50", "9Z5001", "9Z500101", "9Z50010101"):
			self.assertIn(ten, do_sau, f"thiếu dòng {ten}")

		self.assertEqual(do_sau["9Z"], 0, "Khu là gốc, indent=0")
		self.assertEqual(do_sau["9Z50"], 1)
		self.assertEqual(do_sau["9Z5001"], 2)
		self.assertEqual(do_sau["9Z500101"], 3)
		self.assertEqual(do_sau["9Z50010101"], 4, "ô lá sâu nhất, indent=4")

		# Cha phải đứng NGAY TRƯỚC cụm con của nó trong mảng — đúng thứ tự
		# rowmanager.js dò quét để suy children/isLeaf.
		self.assertLess(vi_tri["9Z"], vi_tri["9Z50"])
		self.assertLess(vi_tri["9Z50"], vi_tri["9Z5001"])
		self.assertLess(vi_tri["9Z5001"], vi_tri["9Z500101"])
		self.assertLess(vi_tri["9Z500101"], vi_tri["9Z50010101"])

	def test_o_chua_xep_ngoai_cay_van_hien_trong_bao_cao(self):
		"""Yêu cầu bắt buộc của kế hoạch: mất `ZZZ-CHUA-XEP` khỏi báo cáo là
		"mất dấu 100% hàng" của kho — chưa bài nào khoá riêng điều này
		(`test_chay_duoc_va_co_dong` chỉ khẳng định `dong` không rỗng, vẫn
		xanh dù toàn bộ dòng CHUA-XEP biến mất, miễn còn dòng khác).

		LƯU Ý ĐO ĐƯỢC khi viết bài này: `bat()` nạp lại TOÀN BỘ tồn có sẵn
		của kho thật vào CHUA-XEP (xem `bat_kho.py::bat`, gọi `_ton_hien_co`)
		— trên `KHO` (kho thật, đã dùng nhiều tháng) ô này giữ RẤT NHIỀU mặt
		hàng khác nhau cùng lúc. Báo cáo trả MỘT DÒNG cho MỖI (o, vật tư, lô)
		— đúng thiết kế từ trước Task 6 — nên so khớp phải lọc theo ĐÚNG mặt
		hàng của bài này (`vat_tu=item`), không so tổng-mọi-mặt-hàng của ô
		với một dòng bất kỳ: `dict theo_o = {d["o"]: d ...}` sẽ ÂM THẦM chỉ
		giữ dòng CUỐI CÙNG trùng "o" nếu không lọc — tự đo được lỗi này khi
		viết bài (300 != 24035, xem task-6-report.md)."""
		from erpnext.vi_tri_kho.report.ton_kho_theo_vi_tri import ton_kho_theo_vi_tri

		item = _tao_item("_Test BC ChuaXep Hien")
		_nhap(item, 9)

		_, dong = ton_kho_theo_vi_tri.execute({"kho": KHO, "vat_tu": item})
		o = vk.o_chua_xep(KHO)
		theo_o = {d["o"]: d for d in dong}

		tong_doc_lap = frappe.db.sql(
			"select sum(so_luong) from `tabLocation Balance` where o=%s and vat_tu=%s", (o, item)
		)[0][0]

		self.assertIn(o, theo_o, "ô ngoài cây (CHUA-XEP) phải còn trong báo cáo")
		self.assertAlmostEqual(flt(theo_o[o]["so_luong"]), flt(tong_doc_lap), places=4)
		self.assertAlmostEqual(
			flt(tong_doc_lap), 9.0, places=4, msg="phải đúng 9 vừa nhập, không lẫn mặt hàng khác"
		)
		self.assertIsNone(theo_o[o].get("parent_o"), "CHUA-XEP đứng ngoài cây, không có cha")
		self.assertEqual(theo_o[o].get("indent"), 0, "đứng ngoài cây thì hiện ở gốc, indent=0")


class TestBaoCaoHangChuaXep(FrappeTestCase):
	def setUp(self):
		_don_sach(KHO)
		bat(KHO)

	def tearDown(self):
		_don_sach(KHO)

	def test_liet_ke_hang_o_chua_xep(self):
		from erpnext.vi_tri_kho.report.hang_chua_xep_vi_tri.hang_chua_xep_vi_tri import execute

		_, dong = execute({"kho": KHO})
		self.assertTrue(dong, "vừa bật xong thì mọi thứ đang ở CHUA-XEP")

	def test_khong_liet_ke_o_khac(self):
		from erpnext.vi_tri_kho.report.hang_chua_xep_vi_tri.hang_chua_xep_vi_tri import execute

		o_thuong = "9Z03010101"
		if not frappe.db.exists("Storage Location", o_thuong):
			frappe.get_doc(
				{
					"doctype": "Storage Location",
					"ma_o": o_thuong,
					"kho": KHO,
				}
			).insert(ignore_permissions=True)
		frappe.get_doc(
			{
				"doctype": "Location Balance",
				"o": o_thuong,
				"kho": KHO,
				"vat_tu": _tao_item("_Test BC Item"),
				"so_luong": 5,
			}
		).insert(ignore_permissions=True)

		_, dong = execute({"kho": KHO})
		# GHI ĐÈ so với brief gốc (review advisor): brief chỉ khẳng định
		# o_thuong VẮNG MẶT — bài đó cũng xanh nếu truy vấn trả rỗng vì
		# một lý do bất kỳ khác (tautology "xanh vì rỗng" đã ghim ở
		# task-10-report.md). Khẳng định thêm dong KHÔNG rỗng: báo cáo
		# phải đang thực sự liệt kê tồn CHUA-XEP tại thời điểm này (đã
		# khoá ở test_liet_ke_hang_o_chua_xep, nhưng khoá lại tại đây để
		# chính bài kiểm-vắng-mặt không tự đứng được nhờ dữ liệu rỗng).
		self.assertTrue(dong, "phải vẫn còn tồn CHUA-XEP thật để bài vắng-mặt có ý nghĩa")
		self.assertNotIn(o_thuong, [d[0] for d in dong])


class TestBaoCaoDoiSoat(FrappeTestCase):
	"""Việc (E) (review điều phối, sau khi 147/147 bài "xong") — lưới an
	toàn của TOÀN HỆ (`doi_soat_kho`) được test rất kỹ, nhưng lớp BỌC REPORT
	(`doi_soat_ton_vi_tri.execute()`, thứ thủ kho THẬT SỰ mở lên) thì chưa
	bài nào gọi. Khoá hai điều: (1) guard `frappe.throw` khi thiếu filter
	`kho` (I4, vòng sửa cũ — có mã nhưng chưa ai gọi qua để đo); (2) phép
	chiếu cột đúng với hình dạng MỚI sau Critical 1b (`loai`/`o`/`vat_tu`/
	`so_lo`/`gia_tri_1`/`gia_tri_2`/`lech` — gộp cả ba loại lệch vào một
	bảng, xem docstring module report).
	"""

	def setUp(self):
		_don_sach(KHO)
		bat(KHO)

	def tearDown(self):
		_don_sach(KHO)

	def test_thieu_filter_kho_bi_chan(self):
		from erpnext.vi_tri_kho.report.doi_soat_ton_vi_tri.doi_soat_ton_vi_tri import execute

		with self.assertRaises(frappe.ValidationError):
			execute({})

	def test_khong_truyen_filters_cung_bi_chan(self):
		from erpnext.vi_tri_kho.report.doi_soat_ton_vi_tri.doi_soat_ton_vi_tri import execute

		with self.assertRaises(frappe.ValidationError):
			execute(None)

	def test_khop_thi_rong_va_dung_cot(self):
		from erpnext.vi_tri_kho.report.doi_soat_ton_vi_tri.doi_soat_ton_vi_tri import execute

		cot, dong = execute({"kho": KHO})
		self.assertTrue(cot)
		fieldnames = {c["fieldname"] for c in cot}
		self.assertEqual(
			fieldnames,
			{"loai", "o", "vat_tu", "so_lo", "gia_tri_1", "gia_tri_2", "lech"},
			"báo cáo phải chiếu đủ cột của cả ba loại lệch (Critical 1b), gộp một bảng",
		)
		self.assertEqual(dong, [], "vừa bật xong (khớp cả ba phép đo) thì báo cáo phải rỗng")

	def test_lech_tong_hien_dung_dong(self):
		from erpnext.vi_tri_kho.report.doi_soat_ton_vi_tri.doi_soat_ton_vi_tri import execute

		item = _tao_item("_Test BC DoiSoat Lech")
		_nhap(item, 10)
		ten = frappe.db.get_value("Location Balance", {"kho": KHO, "vat_tu": item}, "name")
		frappe.db.set_value("Location Balance", ten, "so_luong", 3)

		_, dong = execute({"kho": KHO})
		# Sửa thẳng bộ đệm bằng set_value (không qua so.ghi_dong_so) đồng
		# thời làm nó trôi khỏi sổ — cả "Lệch tồn" LẪN "Lệch bộ đệm" cùng lộ
		# ra cho item này (đúng — hai phép đo bắt hai lớp lỗi khác nhau, xem
		# Critical 1b), nên lọc thêm theo LOẠI để chỉ khoá đúng dòng đang
		# xét, không giả định nó là dòng DUY NHẤT.
		lech_tong = [d for d in dong if d[2] == item and d[0] == "Lệch tồn"]
		self.assertEqual(len(lech_tong), 1, f"phải ra đúng 1 dòng 'Lệch tồn' cho item này: {dong}")
		self.assertEqual(lech_tong[0][4], 3, "gia_tri_1 phải là tồn vị trí (3)")
		self.assertEqual(lech_tong[0][5], 10, "gia_tri_2 phải là tồn kho ERPNext (10)")
		self.assertEqual(lech_tong[0][6], -7, "lech = 3 - 10")

	def test_o_am_hien_dung_dong(self):
		from erpnext.vi_tri_kho.report.doi_soat_ton_vi_tri.doi_soat_ton_vi_tri import execute

		item = _tao_item("_Test BC DoiSoat OAm")
		_nhap(item, 10)
		o_chua_xep = frappe.db.get_value("Location Balance", {"kho": KHO, "vat_tu": item}, "o")
		o_gan = "9Z02010101"
		if not frappe.db.exists("Storage Location", o_gan):
			frappe.get_doc(
				{
					"doctype": "Storage Location",
					"ma_o": o_gan,
					"kho": KHO,
				}
			).insert(ignore_permissions=True)
		frappe.db.sql(
			"update `tabLocation Balance` set so_luong = so_luong - 13 where o=%s and vat_tu=%s",
			(o_chua_xep, item),
		)
		frappe.get_doc(
			{
				"doctype": "Location Balance",
				"o": o_gan,
				"kho": KHO,
				"vat_tu": item,
				"so_lo": "",
				"so_luong": 13,
			}
		).insert(ignore_permissions=True)

		_, dong = execute({"kho": KHO})
		# Kịch bản này cũng làm bộ đệm trôi khỏi sổ (chuyển 13 sang o_gan mà
		# không ghi sổ) nên "Lệch bộ đệm" cũng lộ ra cho item này — lọc theo
		# LOẠI để chỉ khoá đúng dòng "Ô âm" đang xét.
		o_am_cua_item = [d for d in dong if d[2] == item and d[0] == "Ô âm"]
		self.assertEqual(len(o_am_cua_item), 1, f"phải ra đúng 1 dòng 'Ô âm': {dong}")
		self.assertEqual(o_am_cua_item[0][1], o_chua_xep)
		self.assertEqual(o_am_cua_item[0][4], -3)


class TestHangNamSaiViTri(FrappeTestCase):
	"""Bổ khuyết của một phép kiểm chỉ chạy MỘT LẦN.

	`ItemLocationPreference.kiem_tra_ton_mat_hang_khac` chặn lúc GÁN. Sau đó
	hàng vẫn vào sai ô được — phiếu xếp khai tay, huỷ chứng từ, kiểm kê. Đối
	soát §3 (`doi_soat.py`) KHÔNG bắt được: nó chỉ so TỔNG tồn vị trí với tồn
	kho ERPNext, nên một ô chứa nhầm mặt hàng vẫn khớp tuyệt đối.
	"""

	def test_bao_cao_rong_khi_moi_thu_dung_cho(self):
		from erpnext.vi_tri_kho.report.hang_nam_sai_vi_tri.hang_nam_sai_vi_tri import execute
		from erpnext.vi_tri_kho.tests.test_gan_vi_tri import _gan, _mat_hang, _o, _ton

		v = _mat_hang("_Test Sai VT Dung")
		_o("5A01010101")
		_gan(v, "5A010101")
		_ton("5A01010101", v, 5)
		_, dong = execute({"kho": "Kho Miyano - MYN"})
		self.assertFalse([d for d in dong if d[0] == "5A01010101"])

	def test_bat_duoc_hang_lot_vao_o_cua_mat_hang_khac(self):
		from erpnext.vi_tri_kho.report.hang_nam_sai_vi_tri.hang_nam_sai_vi_tri import execute
		from erpnext.vi_tri_kho.tests.test_gan_vi_tri import _gan, _mat_hang, _o, _ton

		chu = _mat_hang("_Test Sai VT Chu")
		lac = _mat_hang("_Test Sai VT Lac")
		_o("5B01010101")
		_gan(chu, "5B010101")
		# Ghi thẳng tồn, mô phỏng hàng lọt vào sau khi đã gán.
		_ton("5B01010101", lac, 3)

		_, dong = execute({"kho": "Kho Miyano - MYN"})
		sai = [d for d in dong if d[0] == "5B01010101"]
		self.assertEqual(len(sai), 1)
		self.assertIn(lac, sai[0])
		self.assertIn(chu, sai[0])

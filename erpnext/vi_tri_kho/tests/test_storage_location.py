"""Cây vị trí — ràng buộc cấu trúc.

`name` của bản ghi CHÍNH LÀ mã ô (autoname field:ma_o). Nhờ vậy mọi Link
field đọc được ngay và quét mã vạch ra thẳng bản ghi, không phải tra bảng
trung gian. Bài test đầu tiên khoá đúng điều đó lại.
"""

from unittest.mock import patch as mock_patch

import frappe
from frappe.tests.utils import FrappeTestCase


def _tao_o(ma_o, **kw):
	kw.setdefault("kho", "Kho Miyano - MYN")
	doc = frappe.get_doc({"doctype": "Storage Location", "ma_o": ma_o, **kw})
	doc.insert(ignore_permissions=True)
	return doc


class _CoTienDeKho(FrappeTestCase):
	"""Lớp nền: khẳng định tường minh dữ liệu kho mà cả file test này dựa vào.

	`_tao_o()` hard-code kho "Kho Miyano - MYN", và một số bài test hard-code
	"All Warehouses - MYN" là kho NHÓM. Nếu hai bản ghi đó thiếu hoặc sai hình
	dạng, bài test phải ĐỎ ngay ở đây với thông báo rõ ràng — không được xanh
	vô cớ nhờ dữ liệu tình cờ có sẵn, cũng không được đỏ khó hiểu ở một chỗ
	khác không liên quan tới cái đang thử.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()

		if not frappe.db.exists("Warehouse", "Kho Miyano - MYN"):
			raise AssertionError(
				"Tiền đề thiếu: Warehouse 'Kho Miyano - MYN' không tồn tại trên site "
				"erptest.local. Bài test cây vị trí cần kho lá này có sẵn để gán vào ô."
			)
		if frappe.db.get_value("Warehouse", "Kho Miyano - MYN", "is_group"):
			raise AssertionError(
				"Tiền đề sai: Warehouse 'Kho Miyano - MYN' đang là kho NHÓM (is_group=1), "
				"nhưng bài test cần một kho lá để gán cho ô."
			)
		if not frappe.db.exists("Warehouse", "All Warehouses - MYN"):
			raise AssertionError(
				"Tiền đề thiếu: Warehouse 'All Warehouses - MYN' không tồn tại trên site "
				"erptest.local. Bài test cần kho NHÓM này để thử ràng buộc chặn ô vào kho tổng."
			)
		if not frappe.db.get_value("Warehouse", "All Warehouses - MYN", "is_group"):
			raise AssertionError(
				"Tiền đề sai: Warehouse 'All Warehouses - MYN' không phải kho NHÓM "
				"(is_group=0), nhưng bài test cần is_group=1 để thử ràng buộc chặn ô vào "
				"kho tổng."
			)


class TestDatTen(_CoTienDeKho):
	def test_name_chinh_la_ma_o(self):
		o = _tao_o("9Z01010101")
		self.assertEqual(o.name, "9Z01010101")

	def test_ma_o_khong_duoc_trung(self):
		_tao_o("9Z01010102")
		with self.assertRaises(frappe.DuplicateEntryError):
			_tao_o("9Z01010102")


class TestRangBuocKho(_CoTienDeKho):
	def test_o_la_bat_buoc_co_kho(self):
		doc = frappe.get_doc({"doctype": "Storage Location", "ma_o": "9Z01010201"})
		with self.assertRaises(frappe.ValidationError):
			doc.insert(ignore_permissions=True)

	def test_khong_nhan_warehouse_nhom(self):
		with self.assertRaises(frappe.ValidationError) as ctx:
			_tao_o("9Z01010202", kho="All Warehouses - MYN")
		self.assertIn("kho tổng", str(ctx.exception).lower())


class TestKhoaMaO(_CoTienDeKho):
	"""Mã ô đã in lên tem dán kệ — không được đổi âm thầm sau khi tạo.

	`autoname: field:ma_o` chỉ gán `name` lúc insert. Nếu không khoá, sửa
	`ma_o` của bản ghi đã tồn tại làm `name` và `ma_o` lệch nhau âm thầm,
	phá bất biến "name CHÍNH LÀ mã ô" mà toàn hệ thống dựa vào.
	"""

	def test_khong_duoc_sua_ma_o_sau_khi_tao(self):
		o = _tao_o("9Z02010101")
		o.ma_o = "9Z02010102"
		with self.assertRaises(frappe.ValidationError):
			o.save(ignore_permissions=True)


class TestBarcode(_CoTienDeKho):
	"""Barcode phải duy nhất.

	Hai bài về "nút nhóm để trống barcode" đã bỏ cùng cây nested set: mọi bản
	ghi giờ đều là ô lá và luôn được tự điền barcode từ mã ô, nên không còn
	tình huống hai bản ghi cùng để trống.
	"""

	def test_barcode_khong_duoc_trung(self):
		_tao_o("9Z03010101")
		with self.assertRaises(frappe.ValidationError):
			_tao_o("9Z03010102", barcode="9Z03010101")


class TestKhoaOChuaXep(_CoTienDeKho):
	"""CRITICAL 2 (review điều phối, sau khi 147/147 bài "xong"): một
	checkbox (`disabled`) trên ô `la_o_chua_xep=1` làm đứng cả kho — nhập
	vẫn ghi vào ô đã ngừng dùng (vì `o_chua_xep()` trước đây chỉ hỏi
	`frappe.db.exists`), trong khi xuất bị FEFO loại bỏ ô `disabled`
	(`fefo.py:60`) rồi `frappe.throw` giữa `Stock Ledger Entry.on_submit` —
	cuộn ngược MỌI phiếu xuất của MỌI mặt hàng đang ở CHUA-XEP. `disabled`
	không read-only và `Stock Manager` có quyền `write` trên `Storage
	Location` (xem `storage_location.json`), nên đây là một tai nạn vận
	hành có thật, không phải giả thuyết.

	Spec §5.1: "`la_o_chua_xep`: ... mỗi kho đúng 1 ô, không xoá được."
	"""

	def test_khong_duoc_vo_hieu_hoa_o_chua_xep(self):
		o = _tao_o("TEST-CX-DISABLE", la_o_chua_xep=1)
		o.disabled = 1
		with self.assertRaises(frappe.ValidationError) as ctx:
			o.save(ignore_permissions=True)
		self.assertIn("chưa xếp vị trí", str(ctx.exception).lower())

	def test_khong_xoa_duoc_o_chua_xep(self):
		o = _tao_o("TEST-CX-TRASH", la_o_chua_xep=1)
		with self.assertRaises(frappe.ValidationError) as ctx:
			frappe.delete_doc("Storage Location", o.name, ignore_permissions=True)
		self.assertIn("chưa xếp vị trí", str(ctx.exception).lower())
		self.assertTrue(frappe.db.exists("Storage Location", o.name), "phải còn nguyên sau khi bị chặn xoá")

	def test_o_thuong_van_vo_hieu_hoa_duoc(self):
		"""Đối chứng: ràng buộc CHỈ áp dụng cho ô la_o_chua_xep=1, không phải
		mọi ô — nếu không sẽ chặn nhầm thao tác vận hành bình thường."""
		o = _tao_o("9Z04010101")
		o.disabled = 1
		o.save(ignore_permissions=True)  # không được ném lỗi
		o.reload()
		self.assertTrue(o.disabled)


# --- Chuẩn mã 10 ký tự SPD (chốt 10/09/2026, rút gọn Task 1 11/09/2026) ----

MA_HOP_LE = "9Z01040302"


class TestCuongCheDinhDangMa(FrappeTestCase):
	"""Mã ô phải đúng chuẩn 10 ký tự — §5.5 đòi phần mềm kiểm định dạng khi tạo.

	Trước đây `ma_o` là ô chữ tự do, gõ gì cũng nhận. Đó là chỗ mà một mã sai
	lọt vào rồi được IN LÊN TEM dán kệ — sửa sau khi dán tem là thứ §5.3 cảnh
	báo riêng.
	"""

	def test_ma_dung_chuan_thi_nhan(self):
		o = _tao_o(MA_HOP_LE)
		self.assertEqual(o.name, MA_HOP_LE)

	def test_ma_tu_che_bi_tu_choi(self):
		with self.assertRaises(frappe.ValidationError):
			_tao_o("TEST-TU-CHE")

	def test_tach_du_nam_thanh_phan_vao_truong_rieng(self):
		# §5.5: bảng master phải có "mã 10 ký tự VÀ 5 trường thành phần"
		o = _tao_o("9Z07120405")
		self.assertEqual(
			(o.khu, o.day, o.khoang, o.tang, o.o),
			("9Z", "07", "12", "04", "05"),
		)

	def test_luu_san_dang_in_tren_nhan(self):
		o = _tao_o("9Z08010203")
		self.assertEqual(o.ma_in_nhan, "9Z0801-0203")


class TestOChuaXepDuocMienKiemDinhDang(FrappeTestCase):
	"""Ô CHUA-XEP là ô LÔ-GIC, không phải vị trí vật lý.

	Nó không bao giờ được in lên tem và không ứng với chỗ nào ngoài kho. Ép nó
	vào chuẩn 10 ký tự là bịa ra một địa chỉ không tồn tại — nên nó được miễn,
	qua chính cờ `la_o_chua_xep`.
	"""

	def test_o_chua_xep_khong_bi_ep_dinh_dang(self):
		# Tên riêng cho bài này, KHÔNG dùng tên thật `CHUA-XEP-<kho>`: tên thật
		# do `bat()` tạo và các file test khác cũng dựng, dễ đụng nhau; mà xoá
		# đi để dọn thì `on_trash` chặn (đúng thiết kế — ô này không xoá được).
		ten = "CHUA-XEP-TEST-MIEN-DINH-DANG"
		o = frappe.get_doc(
			{
				"doctype": "Storage Location",
				"ma_o": ten,
				"kho": "Kho Miyano - MYN",
				"la_o_chua_xep": 1,
			}
		)
		o.insert(ignore_permissions=True)
		self.assertEqual(o.name, ten)
		self.assertIsNone(o.khu)


# --- Dọn nhãn an toàn giả `loai_vi_tri` và trường chết `custom_ma_kho_spd` (Task 7) ---


class TestLoaiViTriKhongConCachLy(FrappeTestCase):
	def test_loai_vi_tri_khong_con_cach_ly(self):
		"""'Cách ly' là nhãn an toàn GIẢ: không chỗ nào trong vitri/ đọc nó, nên
		hàng ở ô 'cách ly' vẫn bị FEFO lấy ra bán. Cách ly thật phải là Warehouse.

		LƯU Ý: `get_meta` đọc `tabDocField` trong CSDL, không đọc file JSON
		trong repo trực tiếp — bài này chỉ đỏ đúng nếu site đã `migrate` sau
		khi sửa JSON. Vế đọc thẳng file nằm ở
		`test_json_doctype_khong_con_cach_ly` bên dưới.
		"""
		meta = frappe.get_meta("Storage Location")
		lua_chon = meta.get_field("loai_vi_tri").options.split("\n")
		self.assertNotIn("Cách ly", lua_chon)
		self.assertNotIn("Trả hàng", lua_chon)
		self.assertIn("Lưu trữ", lua_chon)

	def test_json_doctype_khong_con_cach_ly(self):
		"""Vế đọc THẲNG file JSON — nguồn sự thật của schema trong repo.

		Bài `test_loai_vi_tri_khong_con_cach_ly` ở trên đọc `tabDocField` qua
		`get_meta`, nên nó xanh/đỏ theo việc site erptest.local đã `migrate`
		hay chưa — không theo đúng file đang nằm trong git. Bài này không phụ
		thuộc migrate: sửa JSON là đỏ ngay.
		"""
		import json
		import os

		import erpnext

		duong = os.path.join(
			os.path.dirname(erpnext.__file__),
			"vi_tri_kho",
			"doctype",
			"storage_location",
			"storage_location.json",
		)
		with open(duong, encoding="utf-8") as f:
			dt = json.load(f)
		truong = next(t for t in dt["fields"] if t["fieldname"] == "loai_vi_tri")
		lua_chon = truong["options"].split("\n")
		self.assertNotIn("Cách ly", lua_chon)
		self.assertNotIn("Trả hàng", lua_chon)
		self.assertIn("Lưu trữ", lua_chon)


class TestPatchDonLoaiViTriKhongHopLe(_CoTienDeKho):
	"""Chạy trực tiếp patch dọn dữ liệu — không chỉ kiểm danh sách lựa chọn.

	Site đã sống trước khi options đổi có thể còn bản ghi mang giá trị cũ
	('Cách ly'/'Trả hàng') hoặc còn Custom Field `custom_ma_kho_spd`. Bài
	này dựng đúng tình huống đó rồi khẳng định patch dọn sạch, không suy
	diễn từ chính công thức đang kiểm.
	"""

	def test_patch_don_gia_tri_loai_vi_tri_khong_con_hop_le(self):
		"""Chốt cả hai chiều: dọn đúng dòng SAI, KHÔNG đụng dòng ĐÚNG.

		Chỉ khẳng định "dòng sai đã sạch" là bỏ nửa nguy hiểm của một patch
		phá huỷ — một `WHERE` bị viết rộng (vd. `1=1`) NULL luôn mọi
		`Storage Location` hợp lệ trên site, và `loai_vi_tri` lại `reqd: 1`
		nên hậu quả là gãy toàn bộ doctype. Bài này khoá cả hai vế.
		"""
		from erpnext.patches.v15_0.don_loai_vi_tri_khong_hop_le import execute

		o = _tao_o("9Z97010101")
		# Bỏ qua validate của controller — mô phỏng đúng dữ liệu CŨ ghi từ
		# thời options còn "Cách ly", nay đã không còn hợp lệ với schema mới.
		frappe.db.set_value("Storage Location", o.name, "loai_vi_tri", "Cách ly", update_modified=False)
		self.assertEqual(frappe.db.get_value("Storage Location", o.name, "loai_vi_tri"), "Cách ly")

		# Chốt âm: một ô mang giá trị HỢP LỆ, dựng qua insert() bình thường
		# (không bypass) — patch không được đụng vào dòng này.
		o_hop_le = _tao_o("9Z97010102", loai_vi_tri="Soạn hàng")
		self.assertEqual(frappe.db.get_value("Storage Location", o_hop_le.name, "loai_vi_tri"), "Soạn hàng")

		execute()

		self.assertFalse(frappe.db.get_value("Storage Location", o.name, "loai_vi_tri"))
		self.assertEqual(
			frappe.db.get_value("Storage Location", o_hop_le.name, "loai_vi_tri"),
			"Soạn hàng",
			"Patch dọn quá tay: ô mang giá trị HỢP LỆ bị NULL theo — WHERE lọc sai phạm vi",
		)

	def test_patch_xoa_custom_field_ma_kho_spd(self):
		"""Chốt cả hai chiều: xoá đúng field CHẾT, KHÔNG đụng field khác trên Warehouse.

		Chỉ khẳng định "field chết đã bị xoá" là bỏ nửa nguy hiểm: một bộ lọc
		`frappe.db.delete` bị viết thiếu `fieldname` (chỉ còn `{"dt":
		"Warehouse"}`) xoá SẠCH mọi Custom Field của Warehouse — kể cả
		`custom_quan_ly_vi_tri`, cờ bật quản lý vị trí mà cả module
		`vi_tri_kho` treo lên. Bài này khoá cả hai vế.
		"""
		from erpnext.patches.v15_0.don_loai_vi_tri_khong_hop_le import execute

		ten = "Warehouse-custom_ma_kho_spd"
		# Luôn tạo mới bằng tay, không có nhánh "nếu chưa có" — nhánh điều
		# kiện làm bài phụ thuộc site erptest.local đã `migrate` (xoá field
		# thật) hay chưa, và phụ thuộc thứ tự chạy alphabet với bài kia
		# trong cùng lớp. Dọn trước (nếu sót) rồi tạo lại cho chắc độc lập.
		frappe.db.delete("Custom Field", {"name": ten})
		# `.insert()` bình thường sẽ chạy `CustomField.on_update()` ->
		# `frappe.db.updatedb()` -> ALTER TABLE thật trên `tabWarehouse`. DDL
		# tự COMMIT trong MySQL, xoá luôn rollback-theo-class của
		# FrappeTestCase — rò cả bài NÀY lẫn bài kia cùng lớp ra CSDL thật
		# (thấy tận mắt khi đo lần đầu). Dùng `db_insert()` thẳng: chỉ ghi
		# đúng dòng `tabCustom Field`, không đụng schema, không DDL.
		doc = frappe.get_doc(
			{
				"doctype": "Custom Field",
				"dt": "Warehouse",
				"fieldname": "custom_ma_kho_spd",
				"label": "Mã kho SPD (2 ký tự)",
				"fieldtype": "Data",
			}
		)
		doc.name = ten
		doc.db_insert()
		self.assertTrue(frappe.db.exists("Custom Field", ten))

		# Chốt âm: field ĐANG SỐNG khác trên Warehouse — nạn nhân thật nếu
		# bộ lọc bị viết rộng quá tay. Không dựng giả, dùng đúng field thật
		# đang có trên site (do patch `them_co_quan_ly_vi_tri` tạo).
		con_song = "Warehouse-custom_quan_ly_vi_tri"
		self.assertTrue(
			frappe.db.exists("Custom Field", con_song),
			"Tiền đề thiếu: Custom Field 'custom_quan_ly_vi_tri' trên Warehouse phải có sẵn "
			"trên site erptest.local — bài này dùng nó làm chốt âm.",
		)

		execute()

		self.assertFalse(frappe.db.exists("Custom Field", ten))
		self.assertTrue(
			frappe.db.exists("Custom Field", con_song),
			"Patch xoá quá tay: Custom Field 'custom_quan_ly_vi_tri' (không phải mục tiêu của "
			"patch) đã bị xoá theo",
		)


class TestDamBaoCayDaDung(_CoTienDeKho):
	"""`erpnext.vi_tri_kho.vitri.cay.dam_bao_cay_da_dung` — Task 8, vòng sửa 2/5.

	VÒNG SỬA 2/5 (review điều phối): logic dựng `lft`/`rgt` chuyển từ patch
	(`v15_0.dung_lai_cay_vi_tri`, sự kiện MỘT LẦN, bị `Patch Log` khoá) sang
	một hàm dùng lại được, treo thêm vào `after_migrate` — "cây đã dựng" là
	một TRẠNG THÁI cần hội tụ tới ở MỌI lần migrate, không phải một sự kiện
	chạy một lần. Patch cũ giờ chỉ gọi thẳng hàm này (xem file patch); các
	bài dưới đây kiểm HÀM, không kiểm patch.

	`erptest.local` đã dựng cây xong ở Task 8 (0 bản ghi `lft = rgt = 0`), nên
	các bài này TỰ ép một bản ghi về đúng trạng thái "tạo trước khi có cây"
	bằng `frappe.db.set_value` (bypass hook, không kích `update_nsm()` sớm),
	không trông vào dữ liệu sẵn có trên site.
	"""

	def test_dung_lai_toa_do_cho_ban_ghi_thieu_khong_dung_du_lieu_khac(self):
		"""Chốt CẢ HAI chiều: bản ghi thiếu toạ độ ĐƯỢC dựng lại đúng quan hệ
		cha-con; và một thao tác ghi đè TOÀN CÂY không được đụng tới sổ vị
		trí, tồn vị trí, ô `ZZZ-CHUA-XEP`, hay làm đối soát lệch — nếu chỉ
		khẳng định vế đầu, một đột biến làm `rebuild_tree` vô tình xoá/sửa
		bảng khác (hoặc gọi nhầm doctype) vẫn lọt qua xanh."""
		from erpnext.vi_tri_kho.vitri.cay import dam_bao_cay_da_dung
		from erpnext.vi_tri_kho.vitri.doi_soat import doi_soat_kho

		so_ledger_truoc = frappe.db.count("Location Ledger Entry")
		so_balance_truoc = frappe.db.count("Location Balance")
		zzz = "ZZZ-CHUA-XEP-Kho Miyano - MYN"
		zzz_truoc = frappe.db.get_value(
			"Storage Location", zzz, ["lft", "rgt", "parent_storage_location"], as_dict=True
		)
		self.assertTrue(zzz_truoc, "Tiền đề thiếu: ô hệ thống ZZZ-CHUA-XEP phải có sẵn trên site.")

		o = _tao_o("9Z55010101")
		# `insert()` bình thường đã tự gán toạ độ thật (NestedSet.on_update).
		# Ép thẳng về 0/0 bằng frappe.db.set_value — mô phỏng đúng dữ liệu
		# tạo TRƯỚC khi StorageLocation kế thừa NestedSet, không kích hook.
		frappe.db.set_value("Storage Location", o.name, {"lft": 0, "rgt": 0}, update_modified=False)
		frappe.db.set_value("Storage Location", "9Z55", {"lft": 0, "rgt": 0}, update_modified=False)
		self.assertTrue(frappe.db.exists("Storage Location", {"lft": 0, "rgt": 0}))

		dam_bao_cay_da_dung()

		lft, rgt = frappe.db.get_value("Storage Location", o.name, ["lft", "rgt"])
		self.assertTrue(lft and rgt and lft < rgt, f"chưa dựng lại toạ độ cho {o.name}: ({lft}, {rgt})")
		cha_lft, cha_rgt = frappe.db.get_value("Storage Location", "9Z55", ["lft", "rgt"])
		self.assertTrue(
			cha_lft < lft and rgt < cha_rgt,
			"cây dựng sai quan hệ cha-con: nút lá phải nằm TRONG khoảng lft/rgt của nút cha",
		)

		# Chốt âm: rebuild_tree() ghi đè lft/rgt của TOÀN BỘ doctype — dữ
		# liệu KHÔNG liên quan phải còn nguyên y hệt trước khi chạy hàm.
		self.assertEqual(frappe.db.count("Location Ledger Entry"), so_ledger_truoc)
		self.assertEqual(frappe.db.count("Location Balance"), so_balance_truoc)
		# VÒNG SỬA 3/5: `doi_soat_kho` KHÔNG đọc lft/rgt (chỉ so tồn kho với
		# sổ) nên "đối soát khớp" không khoá được cấu trúc cây — một lần
		# rebuild gán nhầm ZZZ-CHUA-XEP làm CON của một nhánh, hoặc để nó ở
		# lft=rgt=0, vẫn qua được đối soát. Kiểm THẲNG toạ độ + parent của
		# ZZZ, không suy diễn qua đối soát.
		zzz_sau = frappe.db.get_value(
			"Storage Location", zzz, ["lft", "rgt", "parent_storage_location"], as_dict=True
		)
		self.assertTrue(zzz_sau, "ô ZZZ-CHUA-XEP biến mất sau khi dựng cây")
		self.assertTrue(
			zzz_sau.lft and zzz_sau.rgt and zzz_sau.lft != zzz_sau.rgt,
			f"ZZZ-CHUA-XEP vẫn thiếu toạ độ thật sau khi dựng cây: {zzz_sau}",
		)
		self.assertFalse(
			zzz_sau.parent_storage_location,
			f"ZZZ-CHUA-XEP bị gán nhầm làm con của {zzz_sau.parent_storage_location} — "
			"nó phải đứng NGOÀI cây theo thiết kế (gốc riêng, không cha).",
		)
		kq = doi_soat_kho("Kho Miyano - MYN")
		self.assertTrue(kq["khop"], f"đối soát lệch sau khi dựng cây: {kq}")

	def test_bo_qua_khong_rebuild_khi_con_o_dang_tat(self):
		"""Nhánh từ chối F5+F11: còn `disabled = 1` thì KHÔNG gọi `rebuild_tree` —
		bản ghi thiếu toạ độ phải giữ nguyên `lft = rgt = 0` sau khi chạy hàm.

		Dùng mock thay vì chỉ so giá trị trước/sau: `rebuild_tree` chạy trên
		một cây đã đúng cấu trúc là HÀM ĐƠN TRỊ (deterministic theo thứ tự
		tên), nên gọi lại có thể tình cờ cho ra đúng `lft`/`rgt` cũ — so giá
		trị không chắc bắt được đột biến "vẫn rebuild bất kể `disabled`".
		Khẳng định thẳng `rebuild_tree` KHÔNG được gọi mới chặn đúng lớp lỗi
		F5+F11 cảnh báo (thừa kế `disabled` kích hoạt ngay khi rebuild)."""
		import erpnext.vi_tri_kho.vitri.cay as cay_module

		o = _tao_o("9Z56010101")
		# `FrappeTestCase` chỉ rollback ở CUỐI CẢ LỚP (`addClassCleanup`), không
		# phải sau mỗi bài — ép `disabled=1`/`lft=rgt=0` mà không tự dọn sẽ rò
		# sang đúng hai bài kiểm "toàn site sạch" khác trong lớp này. Lưu toạ độ
		# thật trước khi ép, và đăng ký trả lại nguyên trạng NGAY KHI bài này
		# xong (`addCleanup` chạy dù bài pass hay fail).
		lft_that, rgt_that = frappe.db.get_value("Storage Location", o.name, ["lft", "rgt"])
		self.addCleanup(
			frappe.db.set_value,
			"Storage Location",
			o.name,
			{"lft": lft_that, "rgt": rgt_that, "disabled": 0},
			update_modified=False,
		)
		frappe.db.set_value(
			"Storage Location", o.name, {"lft": 0, "rgt": 0, "disabled": 1}, update_modified=False
		)
		self.assertTrue(frappe.db.exists("Storage Location", {"lft": 0, "rgt": 0}))
		self.assertEqual(frappe.db.count("Storage Location", {"disabled": 1}), 1)

		with mock_patch.object(cay_module, "rebuild_tree") as gia:
			cay_module.dam_bao_cay_da_dung()
		gia.assert_not_called()

		lft, rgt = frappe.db.get_value("Storage Location", o.name, ["lft", "rgt"])
		self.assertEqual(
			(lft, rgt),
			(0, 0),
			"còn ô disabled=1 mà toạ độ vẫn bị đổi — đúng rủi ro F5+F11: rebuild sẽ kích "
			"hoạt thừa kế disabled xuống cả nhánh một lượt, âm thầm",
		)

	def test_khong_goi_rebuild_khi_khong_con_ban_ghi_thieu_toa_do(self):
		"""Không có bản ghi `lft=rgt=0` nào thì KHÔNG gọi `rebuild_tree` — hàm
		này chạy ở MỌI lần `bench migrate` (treo qua `after_migrate`), nên
		nhánh "không có gì để làm" PHẢI rẻ: không ghi đè vô ích lên toàn bộ
		doctype ở mọi lần migrate của mọi site."""
		import erpnext.vi_tri_kho.vitri.cay as cay_module

		self.assertFalse(
			frappe.db.exists("Storage Location", {"lft": 0, "rgt": 0}),
			"Tiền đề thiếu: site phải KHÔNG còn bản ghi lft=rgt=0 nào (đã dựng cây ở Task 8) "
			"để bài này đo đúng nhánh 'không có gì để làm'.",
		)

		with mock_patch.object(cay_module, "rebuild_tree") as gia:
			cay_module.dam_bao_cay_da_dung()
		gia.assert_not_called()

	def test_ban_ghi_lanh_van_duoc_dung_khi_co_cha_treo(self):
		"""VÒNG SỬA 3/5: "cha treo" (`parent_storage_location` trỏ tới một
		`name` KHÔNG TỒN TẠI) không bao giờ được `rebuild_node` chạm tới —
		hàm KHÔNG được ném lỗi vì nó, PHẢI ghi log cảnh báo nêu đích danh, và
		CHỐT ÂM quan trọng nhất: một bản ghi LÀNH khác vẫn phải được dựng
		bình thường — một bản ghi hỏng không được kéo cả lượt rebuild xuống."""
		import erpnext.vi_tri_kho.vitri.cay as cay_module

		# Bản ghi LÀNH, thiếu toạ độ — phải được dựng lại bình thường dù có
		# một bản ghi hỏng khác trong cùng lượt gọi.
		o_lanh = _tao_o("9Z59010101")
		frappe.db.set_value("Storage Location", o_lanh.name, {"lft": 0, "rgt": 0}, update_modified=False)

		# Bản ghi CHA TREO: dùng db_insert() thẳng, bỏ qua validate()/
		# dung_cho_trong_cay() — mô phỏng đúng dữ liệu hỏng do thao tác tay/
		# import ngoài luồng bình thường (StorageLocation.validate() không
		# bao giờ tự tạo ra được cha treo, vì dam_bao_to_tien() luôn tự sinh
		# đủ nút cha còn thiếu).
		ten_mo_coi = "9Z60010101"
		cha_khong_ton_tai = "CHA-KHONG-TON-TAI-9Z60"
		mo_coi = frappe.get_doc(
			{
				"doctype": "Storage Location",
				"ma_o": ten_mo_coi,
				"kho": "Kho Miyano - MYN",
				"loai_vi_tri": "Lưu trữ",
				"is_group": 0,
				"parent_storage_location": cha_khong_ton_tai,
				"lft": 0,
				"rgt": 0,
			}
		)
		mo_coi.name = ten_mo_coi
		mo_coi.db_insert()
		self.addCleanup(lambda: frappe.db.delete("Storage Location", {"name": ten_mo_coi}))

		self.assertFalse(
			frappe.db.exists("Storage Location", cha_khong_ton_tai),
			"Tiền đề hỏng: 'cha treo' phải trỏ tới một tên THẬT SỰ không tồn tại trên site.",
		)

		# Không được ném lỗi ra ngoài — after_migrate của một site không
		# liên quan không được vỡ vì một bản ghi hỏng. Mock frappe.log_error
		# thay vì kiểm tồn tại trong bảng Error Log thật: log_error() ghi
		# xong KHÔNG bị rollback theo test (đã đo — Error Log của cả những
		# lần chạy `bench run-tests` TRƯỚC vẫn còn trên site), nên kiểm tồn
		# tại theo `method` sẽ XANH GIẢ dù bỏ hẳn phép kiểm cha treo trong
		# code (đã đột biến xác nhận — xem báo cáo vòng sửa 3/5, mục "gãy
		# lưới an toàn").
		with mock_patch.object(frappe, "log_error") as ghi_log:
			cay_module.dam_bao_cay_da_dung()

		# Chốt 1 (quan trọng nhất): bản ghi LÀNH vẫn được dựng bình thường.
		lft, rgt = frappe.db.get_value("Storage Location", o_lanh.name, ["lft", "rgt"])
		self.assertTrue(
			lft and rgt and lft < rgt,
			f"bản ghi LÀNH {o_lanh.name} không được dựng vì có một bản ghi hỏng khác: ({lft}, {rgt})",
		)

		# Chốt 2: bản ghi cha treo giữ nguyên lft=rgt=0 — đúng như docstring
		# mô tả (rebuild_node không đệ quy tới được nó), không bị "sửa" lặng
		# lẽ thành một giá trị sai khác.
		lft_mc, rgt_mc = frappe.db.get_value("Storage Location", ten_mo_coi, ["lft", "rgt"])
		self.assertEqual(
			(lft_mc, rgt_mc),
			(0, 0),
			"bản ghi cha treo không còn 0/0 — rebuild_node lẽ ra không chạm được tới nó",
		)

		# Chốt 3: có ghi log cảnh báo nêu đích danh — không xử lý im lặng.
		tieu_de_da_ghi = [kw.get("title") for _, kw in ghi_log.call_args_list]
		self.assertIn(
			"vi_tri_kho: dam_bao_cay_da_dung cha treo",
			tieu_de_da_ghi,
			f"Không thấy log_error cảnh báo cha treo — cha treo không được xử lý im lặng. "
			f"Các title đã ghi: {tieu_de_da_ghi}",
		)

	def test_loi_rebuild_tree_khong_lam_vo_after_migrate(self):
		"""VÒNG SỬA 3/5: `rebuild_tree()` có thể ném lỗi vì lý do KHÁC (dữ
		liệu hỏng dạng khác, khoá DB, …) — hàm này treo ở `after_migrate` nên
		lỗi đó KHÔNG được văng ra ngoài, chỉ log rồi thoát êm để site gọi
		hàm (có thể không liên quan gì tới module vị trí kho) đi tiếp."""
		import erpnext.vi_tri_kho.vitri.cay as cay_module

		o = _tao_o("9Z61010101")
		frappe.db.set_value("Storage Location", o.name, {"lft": 0, "rgt": 0}, update_modified=False)

		# Mock frappe.log_error thay vì kiểm tồn tại trong Error Log thật —
		# lý do giống hệt bài `test_ban_ghi_lanh_...`: Error Log không bị
		# rollback theo test, nên kiểm tồn tại theo `method` sẽ XANH GIẢ nếu
		# site đã có sẵn một dòng cùng tiêu đề từ lần chạy suite trước.
		with mock_patch.object(cay_module, "rebuild_tree", side_effect=RuntimeError("giả lập lỗi CSDL")):
			with mock_patch.object(frappe, "log_error") as ghi_log:
				# Không được ném RuntimeError ra ngoài — nếu bài này tự nó
				# ném lỗi, test framework sẽ báo lỗi (không cần assertRaises).
				cay_module.dam_bao_cay_da_dung()

		tieu_de_da_ghi = [kw.get("title") for _, kw in ghi_log.call_args_list]
		self.assertIn(
			"vi_tri_kho: dam_bao_cay_da_dung rebuild_tree loi",
			tieu_de_da_ghi,
			f"rebuild_tree() ném lỗi nhưng không thấy log_error() ghi lại — lỗi có nguy cơ "
			f"văng lên after_migrate của mọi site có erpnext. Các title đã ghi: {tieu_de_da_ghi}",
		)

	def test_co_auto_commit_duoc_tra_ve_0_khi_rebuild_tree_loi(self):
		"""VÒNG SỬA 4/5: `rebuild_tree()` tự đặt
		`frappe.db.auto_commit_on_many_writes = 1` TRƯỚC vòng lặp, chỉ đặt
		lại `0` ở dòng SAU vòng lặp — nếu lỗi giữa chừng (đúng ca `except`
		của `dam_bao_cay_da_dung` bắt), dòng reset đó không bao giờ chạy.
		Cờ treo ở `1` có nguy cơ làm các thao tác ghi KHÁC của cùng site (app
		khác, các bước cuối migrate) tự commit sớm ngoài ý muốn — tác dụng
		phụ TOÀN CỤC, ngoài phạm vi module này.

		`rebuild_tree` bị MOCK hoàn toàn ở bài này (giống bài
		`test_loi_rebuild_tree_khong_lam_vo_after_migrate`) nên KHÔNG chạy
		qua đoạn đặt cờ thật của hàm gốc — bài này phải TỰ đặt cờ lên `1`
		trước khi gọi, không trông vào việc hàm thật đặt hộ."""
		import erpnext.vi_tri_kho.vitri.cay as cay_module

		gia_tri_truoc_bai = frappe.db.auto_commit_on_many_writes
		self.addCleanup(setattr, frappe.db, "auto_commit_on_many_writes", gia_tri_truoc_bai)

		o = _tao_o("9Z62010101")
		frappe.db.set_value("Storage Location", o.name, {"lft": 0, "rgt": 0}, update_modified=False)

		frappe.db.auto_commit_on_many_writes = 1
		with mock_patch.object(cay_module, "rebuild_tree", side_effect=RuntimeError("giả lập lỗi CSDL")):
			cay_module.dam_bao_cay_da_dung()

		self.assertEqual(
			frappe.db.auto_commit_on_many_writes,
			0,
			"cờ auto_commit_on_many_writes vẫn treo ở 1 sau khi rebuild_tree() lỗi — nguy cơ "
			"các thao tác ghi KHÁC của site tự commit sớm ngoài ý muốn (thiếu finally).",
		)

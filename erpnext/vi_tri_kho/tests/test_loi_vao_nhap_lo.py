"""Lối vào nhập lô từ phiếu nhập, chặn lô gõ tay khi duyệt, và gán vị trí từ form Item.

Vì sao có file này (chủ đầu tư thử luồng thật ngày 17/09/2026): phiếu nhập
`MAT-PRE-2026-00008` được DUYỆT với số lô `17/09/2026` — một ngày tháng gõ thẳng
vào ô lô chuẩn của ERPNext trên phiếu nhập. Phiếu nhập lô không có lối vào nào từ
phiếu nhập, nên đường tự nhiên nhất là gõ lô ngay trên phiếu rồi duyệt — BỎ QUA
hoàn toàn phiếu nhập lô: số lô nhà cung cấp mất, không có tem. Và form Item không
có chỗ nào gán vị trí, nên mặt hàng đó cũng chưa từng được gán.

Ba thứ được khoá ở đây:
1. `chan_doan_phieu_nhap` nói ĐÚNG vì sao một phiếu nhập không còn dòng nào để
   khai lô — ba nguyên nhân cần ba việc khác nhau của thủ kho.
2. Kho đã bật quản lý vị trí: dòng hàng quản lý lô mà số lô KHÔNG đến từ một phiếu
   nhập lô đã duyệt thì phiếu nhập không duyệt được. Kho chưa bật vẫn chạy như
   ERPNext gốc, và phiếu TRẢ HÀNG không bị chặn.
3. Gán vị trí từ form Item đi qua ĐÚNG bản ghi `Item Location Preference`, tức
   chạy đủ các phép kiểm chống chồng lấn — không ghi thẳng xuống CSDL.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.vi_tri_kho.tests.kho_thu import dam_bao_kho_khong_vi_tri
from erpnext.vi_tri_kho.tests.test_gan_vi_tri import KHO, _mat_hang, _o
from erpnext.vi_tri_kho.tests.test_hook_nhap import _tao_item
from erpnext.vi_tri_kho.tests.test_lo_ncc import _ncc_thu, _phieu_nhap_nhap
from erpnext.vi_tri_kho.tests.test_nhap_lo import _phieu_nhap_lo
from erpnext.vi_tri_kho.vitri.gan import gan_vi_tri_cho_mat_hang, vi_tri_cua_mat_hang
from erpnext.vi_tri_kho.vitri.phieu_nhap import NHAN_NUT_NHAP_LO, chan_doan_phieu_nhap

CONG_TY = "Miyano Việt Nam"

# Số lô trong file này đều ≤ 13 ký tự: số lô có chữ dài hơn vượt trần 188 module
# mã vạch của nhãn 50×30 và bị `BatchEntry.validate` chặn — đúng như thiết kế.


def _go_lo_tay(pr, so_lo: str):
	"""Đúng việc đã xảy ra với MAT-PRE-2026-00008: gõ số lô vào ô lô chuẩn của
	ERPNext trên dòng phiếu nhập, KHÔNG qua phiếu nhập lô."""
	item = pr.items[0].item_code
	if not frappe.db.exists("Batch", so_lo):
		frappe.get_doc({"doctype": "Batch", "batch_id": so_lo, "item": item}).insert(
			ignore_permissions=True
		)
	pr.items[0].batch_no = so_lo
	pr.save(ignore_permissions=True)
	return pr


def _khai_lo_qua_phieu(pr, so_lo: str):
	be = _phieu_nhap_lo(
		pr,
		[
			{
				"dong_phieu_nhap": pr.items[0].name,
				"vat_tu": pr.items[0].item_code,
				"kho": pr.items[0].warehouse,
				"so_luong": pr.items[0].qty,
				"so_lo": so_lo,
				"hsd": "2030-01-31",
			}
		],
	)
	be.insert(ignore_permissions=True)
	be.submit()
	pr.reload()
	return be


class TestChanDoanPhieuNhap(FrappeTestCase):
	def setUp(self):
		self.ncc = _ncc_thu()
		self.item_lo = _tao_item("_Test LoiVao Co Lo", co_lo=1)
		self.item_khong_lo = _tao_item("_Test LoiVao Khong Lo", co_lo=0)

	def test_dong_can_khai_lo(self):
		pr = _phieu_nhap_nhap(self.item_lo, KHO, self.ncc)
		cd = chan_doan_phieu_nhap(pr.name)
		self.assertEqual(cd["dong_can_khai"], 1)
		self.assertEqual(cd["dong_go_tay"], [])
		self.assertIsNone(cd["phieu_nhap_lo_nhap"])

	def test_lo_go_thang_tren_phieu_nhap_duoc_neu_ten(self):
		"""Đúng ca MAT-PRE-2026-00008. Câu báo phải NÊU số lô đã gõ, vì thủ kho
		cần nhận ra đó chính là thứ mình vừa gõ, không phải một lỗi hệ thống.

		Chốt âm: `dong_can_khai` phải bằng 0 — dòng này KHÔNG còn trống lô. Một
		cài đặt gộp "đã có lô" với "cần khai" sẽ đếm nó sai về một phía."""
		pr = _go_lo_tay(_phieu_nhap_nhap(self.item_lo, KHO, self.ncc), "LV-GT-CD")
		cd = chan_doan_phieu_nhap(pr.name)
		self.assertEqual(cd["dong_can_khai"], 0)
		self.assertEqual([d["batch_no"] for d in cd["dong_go_tay"]], ["LV-GT-CD"])
		self.assertIn("LV-GT-CD", cd["cau_bao"])

	def test_lo_da_qua_phieu_nhap_lo_khong_bi_coi_la_go_tay(self):
		"""Chốt âm cho bài trên: một dòng khai lô ĐÚNG ĐƯỜNG cũng có `batch_no`.
		Không phân biệt được hai ca đó thì mọi phiếu làm đúng đều bị báo sai."""
		pr = _phieu_nhap_nhap(self.item_lo, KHO, self.ncc)
		_khai_lo_qua_phieu(pr, "LV-QP-CD")
		cd = chan_doan_phieu_nhap(pr.name)
		self.assertEqual(cd["dong_go_tay"], [])
		self.assertEqual(cd["dong_can_khai"], 0)

	def test_mat_hang_khong_bat_co_lo(self):
		pr = _phieu_nhap_nhap(self.item_khong_lo, KHO, self.ncc)
		cd = chan_doan_phieu_nhap(pr.name)
		self.assertEqual(cd["dong_khong_lo"], 1)
		self.assertEqual(cd["dong_can_khai"], 0)
		self.assertIn("Có lô", cd["cau_bao"])

	def test_tra_ve_phieu_nhap_lo_nhap_dang_co(self):
		"""Nút trên phiếu nhập phải MỞ LẠI phiếu nháp đang có, không tạo phiếu thứ
		hai cho cùng một phiếu nhập."""
		pr = _phieu_nhap_nhap(self.item_lo, KHO, self.ncc)
		be = _phieu_nhap_lo(
			pr,
			[
				{
					"dong_phieu_nhap": pr.items[0].name,
					"vat_tu": self.item_lo,
					"kho": KHO,
					"so_luong": 10,
					"so_lo": "LV-NH-CD",
				}
			],
		)
		be.insert(ignore_permissions=True)
		cd = chan_doan_phieu_nhap(pr.name)
		self.assertEqual(cd["phieu_nhap_lo_nhap"], be.name)


class TestChanLoGoTayKhiDuyet(FrappeTestCase):
	def setUp(self):
		self.ncc = _ncc_thu()
		self.item = _tao_item("_Test LoiVao Duyet", co_lo=1)

	def test_kho_bat_vi_tri_lo_go_tay_thi_khong_duyet_duoc(self):
		"""Đúng ca MAT-PRE-2026-00008 — lần này phải bị chặn.

		Câu báo phải chỉ ĐÚNG việc cần làm (bấm nút nào), vì thủ kho đứng trước
		màn hình này không biết phiếu nhập lô là gì."""
		pr = _go_lo_tay(_phieu_nhap_nhap(self.item, KHO, self.ncc), "LV-GT-DY")
		with self.assertRaises(frappe.ValidationError) as ngu_canh:
			pr.submit()
		self.assertIn(NHAN_NUT_NHAP_LO, str(ngu_canh.exception))
		self.assertIn("LV-GT-DY", str(ngu_canh.exception))

	def test_kho_bat_vi_tri_chua_co_lo_thi_bao_bam_nut(self):
		"""Mặt hàng thử có `create_new_batch = 1`, nên ERPNext SẼ tự sinh lô máy
		nếu không ai chặn — đúng thứ làm mất số lô NCC. Câu báo phải là của ta
		(nêu tên nút), không phải một lỗi chung của ERPNext."""
		pr = _phieu_nhap_nhap(self.item, KHO, self.ncc)
		with self.assertRaises(frappe.ValidationError) as ngu_canh:
			pr.submit()
		self.assertIn(NHAN_NUT_NHAP_LO, str(ngu_canh.exception))

	def test_khai_lo_qua_phieu_nhap_lo_thi_duyet_duoc(self):
		"""Chốt âm: đường ĐÚNG phải đi qua. Không có bài này thì một cài đặt chặn
		MỌI phiếu nhập hàng có lô vẫn làm hai bài trên xanh."""
		pr = _phieu_nhap_nhap(self.item, KHO, self.ncc)
		_khai_lo_qua_phieu(pr, "LV-DD-01")
		pr.submit()
		self.assertEqual(pr.docstatus, 1)

	def test_khai_lo_dung_duong_roi_sua_tay_so_lo_thi_bi_chan(self):
		"""Khớp theo CẶP (dòng, số lô), không chỉ theo dòng.

		Dòng này CÓ phiếu nhập lô đã duyệt trỏ vào — nên một cài đặt chỉ hỏi "dòng
		này có phiếu nhập lô chưa" sẽ cho qua. Nhưng số lô đang nằm trên dòng đã bị
		sửa tay thành một số khác: tem in theo số lô đã khai, còn tồn kho ghi theo
		số lô gõ tay. Hai thứ nói khác nhau về cùng một thùng hàng."""
		pr = _phieu_nhap_nhap(self.item, KHO, self.ncc)
		_khai_lo_qua_phieu(pr, "LV-SUA-01")
		_go_lo_tay(pr, "LV-SUA-02")
		with self.assertRaises(frappe.ValidationError) as ngu_canh:
			pr.submit()
		self.assertIn("LV-SUA-02", str(ngu_canh.exception))

	def test_kho_chua_bat_vi_tri_van_chay_nhu_erpnext(self):
		"""Kho chưa bật quản lý vị trí không có tem, không có ô — chặn ở đó là
		chặn luồng nhập kho thường của cả công ty mà không được gì."""
		kho = dam_bao_kho_khong_vi_tri()
		pr = _go_lo_tay(_phieu_nhap_nhap(self.item, kho, self.ncc), "LV-KT-01")
		pr.submit()
		self.assertEqual(pr.docstatus, 1)

	def test_phieu_tra_hang_khong_bi_chan(self):
		"""Phiếu trả hàng trả lại một lô ĐÃ CÓ, không khai lô mới — không có
		phiếu nhập lô nào cho nó cả. Chặn ở đây là không trả hàng được."""
		from erpnext.stock.doctype.purchase_receipt.purchase_receipt import make_purchase_return

		pr = _phieu_nhap_nhap(self.item, KHO, self.ncc)
		_khai_lo_qua_phieu(pr, "LV-TH-01")
		pr.submit()

		tra = make_purchase_return(pr.name)
		tra.items[0].qty = -2
		tra.items[0].received_qty = -2
		tra.insert(ignore_permissions=True)
		tra.submit()
		self.assertEqual(tra.docstatus, 1)


def _nguoi_dung(ten: str, vai_tro: list[str]) -> str:
	if not frappe.db.exists("User", ten):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": ten,
				"first_name": ten.split("@")[0],
				"send_welcome_email": 0,
				"roles": [{"role": r} for r in vai_tro],
			}
		).insert(ignore_permissions=True)
	return ten


class TestGanViTriTuItem(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.o1 = _o("4K01010101")
		cls.o2 = _o("4K01010201")
		cls.tang1 = "4K010101"
		cls.tang2 = "4K010102"

	def tearDown(self):
		# `FrappeTestCase` chỉ rollback ở `tearDownClass`, không theo từng bài. Các
		# bài trong lớp này gán lên CÙNG hai tầng, nên không dọn thì bản gán của
		# bài trước chiếm tầng và bài sau nổ vì "đã được gán cho mặt hàng khác" —
		# đỏ vì thứ tự chạy, không vì mã sai.
		frappe.set_user("Administrator")
		frappe.db.delete("Item Location Preference", {"vat_tu": ["like", "_Test LoiVao Item%"]})

	def test_gan_lan_dau_tao_ban_gan(self):
		vt = _mat_hang("_Test LoiVao Item Gan")
		gan_vi_tri_cho_mat_hang(vt, KHO, self.tang1)
		self.assertEqual(frappe.db.get_value("Item Location Preference", vt, "vi_tri"), self.tang1)
		self.assertEqual(vi_tri_cua_mat_hang(vt)["vi_tri"], self.tang1)

	def test_gan_lai_thi_sua_dung_ban_gan_cu(self):
		"""Chốt âm: một cài đặt luôn `insert()` sẽ nổ khoá chính ở lần hai
		(`autoname: field:vat_tu`), còn một cài đặt xoá-rồi-tạo sẽ vượt qua được
		nhưng đổi `creation`. Khẳng định vẫn đúng MỘT bản ghi và vị trí đã đổi."""
		vt = _mat_hang("_Test LoiVao Item DoiGan")
		gan_vi_tri_cho_mat_hang(vt, KHO, self.tang1)
		gan_vi_tri_cho_mat_hang(vt, KHO, self.tang2)
		self.assertEqual(frappe.db.count("Item Location Preference", {"vat_tu": vt}), 1)
		self.assertEqual(vi_tri_cua_mat_hang(vt)["vi_tri"], self.tang2)

	def test_chua_gan_tra_none(self):
		self.assertIsNone(vi_tri_cua_mat_hang(_mat_hang("_Test LoiVao Item ChuaGan")))

	def test_gan_trung_nut_cua_mat_hang_khac_bi_chan(self):
		"""Chứng minh việc gán đi qua `validate()` của bản gán — tức qua đủ phép
		kiểm chống chồng lấn. Một cài đặt ghi thẳng `db.set_value` sẽ để bài này
		xanh sai: hai mặt hàng cùng một tầng, đúng thứ khối B sinh ra để chặn."""
		a = _mat_hang("_Test LoiVao Item ChiemA")
		b = _mat_hang("_Test LoiVao Item ChiemB")
		gan_vi_tri_cho_mat_hang(a, KHO, self.tang1)
		with self.assertRaises(frappe.ValidationError):
			gan_vi_tri_cho_mat_hang(b, KHO, self.tang1)

	def test_stock_user_khong_gan_duoc(self):
		"""`Item Location Preference` chỉ cho System Manager và Stock Manager tạo /
		sửa. Nút trên form Item không được là cửa sau vượt quyền đó."""
		vt = _mat_hang("_Test LoiVao Item Quyen")
		ten = _nguoi_dung("loivao-stockuser@mo-phong.local", ["Stock User"])
		self.assertNotIn("Stock Manager", frappe.get_roles(ten))
		frappe.set_user(ten)
		with self.assertRaises(frappe.PermissionError):
			gan_vi_tri_cho_mat_hang(vt, KHO, self.tang2)

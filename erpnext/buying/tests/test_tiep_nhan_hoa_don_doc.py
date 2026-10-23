# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Chuẩn hóa, khóa quy cách, điểm khớp tên (FRD-MAP-01 mục 10) và đọc XML hóa đơn điện tử."""

import unittest

from erpnext.buying.tests.mau_hoa_don_xml import xml_hoa_don
from erpnext.buying.tiep_nhan_hoa_don.chuan_hoa import BoChuanHoa
from erpnext.buying.tiep_nhan_hoa_don.doc_xml import LoiDocHoaDon, doc_hoa_don_xml, thue_suat


class TestChuanHoa(unittest.TestCase):
	def setUp(self):
		self.b = BoChuanHoa()

	def test_bo_dau_dong_nghia_va_tu_bo_qua(self):
		self.assertEqual(self.b.chuan_hoa("Sonde Foley 2 way size 16"), "ong thong foley 2 nhanh 16")
		self.assertEqual(self.b.chuan_hoa("Găng khám (cỡ L)"), "gang tay kham l")

	def test_tc12_ten_khac_hop_dong_van_khop(self):
		hd, hdk = "Sonde Foley 2 way size 16", "Ống thông tiểu Foley 2 nhánh cỡ 16Fr"
		self.assertEqual(self.b.khoa_quy_cach(hd), self.b.khoa_quy_cach(hdk))
		self.assertGreaterEqual(self.b.diem(hd, hdk), 0.75)

	def test_tc13_khac_quy_cach_thi_khac_khoa(self):
		# Tên giống nhau tới 76% nhưng gạc 7,5cm không được khớp với gạc 10cm (BR-03).
		a, b = "Gạc phẫu thuật 7,5cm x 7,5cm", "Gạc phẫu thuật 10cm x 10cm"
		self.assertNotEqual(self.b.khoa_quy_cach(a), self.b.khoa_quy_cach(b))
		self.assertEqual(self.b.khoa_quy_cach("Gạc 7,50cm"), self.b.khoa_quy_cach("Gạc 7.5 cm"))

	def test_co_chu_la_quy_cach(self):
		self.assertNotEqual(self.b.khoa_quy_cach("Găng tay size M"), self.b.khoa_quy_cach("Găng tay size L"))

	def test_dong_nghia_va_tu_bo_qua_tu_cai_dat(self):
		b = BoChuanHoa(dong_nghia=[("bơm kim tiêm", "bơm tiêm")], tu_bo_qua="hộp")
		self.assertEqual(b.chuan_hoa("Bơm kim tiêm 5ml hộp"), "bom tiem 5 ml")
		self.assertEqual(b.diem("Bơm kim tiêm 5ml", "Bơm tiêm 5 ml"), 1.0)

	def test_trong_so(self):
		self.assertEqual(self.b.diem("a b", "a c", trong_so_jaccard=1, trong_so_chuoi=0), round(1 / 3, 4))


class TestDocXml(unittest.TestCase):
	def test_doc_du_truong(self):
		kq = doc_hoa_don_xml(
			xml_hoa_don(
				[("ABC-FL216", "Sonde Foley 2 way size 16", "Cái", 500, 12500, "5%")],
				ghi_chu="Theo đơn PUR-ORD-2026-00123",
			)
		)
		self.assertEqual((kq["so_hoa_don"], kq["ky_hieu"], kq["ngay"]), ("00001234", "C26TAB", "2026-10-23"))
		self.assertEqual(kq["ncc"]["mst"], "0101234567")
		self.assertEqual(kq["nguoi_mua"]["mst"], "0109529507")
		self.assertEqual(kq["so_po_ghi_tren_hoa_don"], "PUR-ORD-2026-00123")
		d = kq["dong_hang"][0]
		self.assertEqual(
			(
				d["ma_hang"],
				d["ten_hang"],
				d["dvt"],
				d["so_luong"],
				d["don_gia"],
				d["thanh_tien"],
				d["thue_suat"],
			),
			("ABC-FL216", "Sonde Foley 2 way size 16", "Cái", 500, 12500, 6250000, "5%"),
		)
		self.assertEqual(
			(kq["tong_tien_hang"], kq["tien_thue"], kq["tong_thanh_toan"]), (6250000, 312500, 6562500)
		)

	def test_boc_tdiep_va_namespace(self):
		for kw in ({"boc_tdiep": True}, {"namespace": True}):
			kq = doc_hoa_don_xml(xml_hoa_don([("", "Gạc", "Gói", 1, 1000, "8%")], **kw))
			self.assertEqual(kq["dong_hang"][0]["ten_hang"], "Gạc", kw)

	def test_dong_khong_phai_hang_hoa_van_doc_kem_tinh_chat(self):
		kq = doc_hoa_don_xml(
			xml_hoa_don([("", "Gạc", "Gói", 1, 1000, "8%"), ("", "Hàng tặng kèm", "Gói", 1, 0, "8%", 2)])
		)
		self.assertEqual([d["tinh_chat"] for d in kq["dong_hang"]], [1, 2])

	def test_tep_hong_bao_ro(self):
		self.assertRaises(LoiDocHoaDon, doc_hoa_don_xml, b"khong phai xml")
		self.assertRaises(LoiDocHoaDon, doc_hoa_don_xml, b"<?xml version='1.0'?><Khac/>")

	def test_khong_mo_entity_ngoai(self):
		xxe = (
			b'<?xml version="1.0"?><!DOCTYPE HDon [<!ENTITY x SYSTEM "file:///etc/passwd">]>'
			b"<HDon><DLHDon><TTChung><SHDon>&x;</SHDon></TTChung><NDHDon/></DLHDon></HDon>"
		)
		self.assertNotIn("root", doc_hoa_don_xml(xxe)["so_hoa_don"])

	def test_thue_suat(self):
		self.assertEqual(
			[thue_suat(t) for t in ("10%", "8", "5.0%", "kct", "")], ["10%", "8%", "5%", "KCT", ""]
		)

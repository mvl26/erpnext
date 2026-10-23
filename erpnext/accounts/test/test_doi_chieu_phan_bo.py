# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Chia thuế và ghép dòng bán - mua của báo cáo Đối chiếu mua vào - bán ra (logic thuần)."""

import unittest

from erpnext.accounts.report.doi_chieu_mua_vao_ban_ra.phan_bo import (
	CHUA_KHOP,
	KHOP,
	LECH_DVT,
	LECH_GIA,
	LECH_THUE,
	THIEU_DAU_VAO,
	TRA_HANG,
	chia_thue,
	chon_tai_khoan_vat,
	danh_dau_nhom,
	danh_gia,
	ghep,
	hop_trang_thai,
	tong_hop,
)


def _ban(sl, thanh_tien, tien_thue=0, so_detail="SOI-1", trong_ky=True, ten="SI-1"):
	return {
		"so_detail": so_detail,
		"sl": sl,
		"thanh_tien": thanh_tien,
		"tien_thue": tien_thue,
		"trong_ky": trong_ky,
		"hoa_don": ten,
	}


def _mua(sl, thanh_tien, tien_thue=0, ten="PI-1"):
	return {"sl": sl, "thanh_tien": thanh_tien, "tien_thue": tien_thue, "hoa_don": ten}


class TestChiaThue(unittest.TestCase):
	def test_chia_thue_don_le_du_vao_dong_cuoi(self):
		dong = [
			{"idx": 2, "thanh_tien": 555905, "thue_suat": 5},
			{"idx": 1, "thanh_tien": 1611943, "thue_suat": 5},
		]
		chia_thue(dong, 108393)
		self.assertEqual([d["tien_thue"] for d in sorted(dong, key=lambda d: d["idx"])], [80597, 27796])

	def test_chia_thue_rong(self):
		chia_thue([], 0)


class TestGhep(unittest.TestCase):
	def test_ghep_mot_mot(self):
		kq = ghep([_ban(10, 1010000, 50500)], {"SOI-1": [_mua(10, 1000000, 50000)]})
		self.assertEqual(len(kq), 1)
		self.assertEqual(kq[0]["ban"]["thanh_tien"], 1010000)
		self.assertEqual(kq[0]["mua"]["thanh_tien"], 1000000)
		self.assertEqual(kq[0]["mua"]["tien_thue"], 50000)

	def test_mot_dong_ban_hai_dong_mua(self):
		kq = ghep(
			[_ban(10, 1000003, 50000)],
			{"SOI-1": [_mua(6, 600000, 30000, "A"), _mua(4, 400000, 20000, "B")]},
		)
		self.assertEqual([m["ban"]["sl"] for m in kq], [6, 4])
		self.assertEqual([m["mua"]["hoa_don"] for m in kq], ["A", "B"])
		self.assertEqual(sum(m["ban"]["thanh_tien"] for m in kq), 1000003)
		self.assertEqual(sum(m["ban"]["tien_thue"] for m in kq), 50000)
		self.assertEqual([m["mua"]["thanh_tien"] for m in kq], [600000, 400000])

	def test_mot_dong_mua_chia_hai_dong_ban(self):
		kq = ghep(
			[_ban(1, 101000, ten="SI-1"), _ban(2, 202000, ten="SI-2")],
			{"SOI-1": [_mua(3, 100000)]},
		)
		self.assertEqual([m["mua"]["thanh_tien"] for m in kq], [33333, 66667])
		self.assertEqual([m["mua"]["sl"] for m in kq], [1, 2])

	def test_ghep_tru_phan_da_ban_ky_truoc(self):
		kq = ghep(
			[_ban(4, 400000, trong_ky=False), _ban(6, 600000)],
			{"SOI-1": [_mua(4, 390000, ten="A"), _mua(6, 590000, ten="B")]},
		)
		self.assertEqual(len(kq), 1)
		self.assertEqual(kq[0]["mua"]["hoa_don"], "B")
		self.assertEqual(kq[0]["mua"]["thanh_tien"], 590000)

	def test_ban_vuot_mua_phan_con_lai_de_trong(self):
		kq = ghep([_ban(10, 1000000, 50000)], {"SOI-1": [_mua(6, 590000)]})
		self.assertEqual([m["ban"]["sl"] for m in kq], [6, 4])
		self.assertIsNotNone(kq[0]["mua"])
		self.assertIsNone(kq[1]["mua"])
		self.assertEqual(sum(m["ban"]["thanh_tien"] for m in kq), 1000000)

	def test_khong_co_so_detail(self):
		kq = ghep([_ban(5, 500000, so_detail=None)], {})
		self.assertEqual(len(kq), 1)
		self.assertIsNone(kq[0]["mua"])
		self.assertEqual(kq[0]["ban"]["sl"], 5)

	def test_dong_tra_hang_am(self):
		kq = ghep([_ban(-2, -200000)], {"SOI-1": [_mua(10, 1000000)]})
		self.assertEqual(len(kq), 1)
		self.assertIsNone(kq[0]["mua"])
		self.assertEqual(kq[0]["ban"]["sl"], -2)

	def test_khong_sua_dau_vao(self):
		ban = [_ban(10, 1000000)]
		mua = {"SOI-1": [_mua(6, 600000), _mua(4, 400000)]}
		ghep(ban, mua)
		self.assertEqual(ban[0]["sl"], 10)
		self.assertEqual(mua["SOI-1"][0]["sl"], 6)


class TestChonTaiKhoanVat(unittest.TestCase):
	TIEN_TO = ("3331", "1331")

	def test_he_thong_danh_so(self):
		ds = [
			{"name": "33311 - Thuế GTGT đầu ra", "account_number": "33311", "account_type": "Tax"},
			{"name": "1331 - Thuế GTGT được khấu trừ", "account_number": "1331", "account_type": ""},
			{"name": "3335 - Thuế TNCN", "account_number": "3335", "account_type": "Tax"},
			{"name": "131 - Phải thu", "account_number": "131", "account_type": "Receivable"},
		]
		self.assertEqual(
			chon_tai_khoan_vat(ds, self.TIEN_TO),
			{"33311 - Thuế GTGT đầu ra", "1331 - Thuế GTGT được khấu trừ"},
		)

	def test_he_thong_khong_danh_so(self):
		ds = [
			{"name": "VAT - M", "account_number": None, "account_type": "Tax"},
			{"name": "Debtors - M", "account_number": None, "account_type": "Receivable"},
		]
		self.assertEqual(chon_tai_khoan_vat(ds, self.TIEN_TO), {"VAT - M"})

	def test_danh_so_nhung_sot_tk_vat(self):
		ds = [
			{"name": "33311 - Thuế GTGT đầu ra", "account_number": "33311", "account_type": "Tax"},
			{"name": "VAT nhập khẩu", "account_number": "", "account_type": "Tax"},
		]
		self.assertEqual(chon_tai_khoan_vat(ds, self.TIEN_TO), {"33311 - Thuế GTGT đầu ra", "VAT nhập khẩu"})


def _dong(gia_ban=101000, gia_mua=100000, sl=1, ts_ban=5, ts_mua=5, dvt="Hộp", pi="PI-1", **kw):
	r = {
		"don_gia_ban": gia_ban,
		"thanh_tien_ban": gia_ban * sl,
		"thue_suat_ban": ts_ban,
		"dvt_ban": dvt,
		"sales_invoice": "SI-1",
	}
	if pi:
		r.update(
			{
				"purchase_invoice": pi,
				"don_gia_mua": gia_mua,
				"thanh_tien_mua": gia_mua * sl,
				"thue_suat_mua": ts_mua,
				"dvt_mua": dvt,
			}
		)
	return {**r, **kw}


class TestDanhGia(unittest.TestCase):
	def test_khop_ty_le_hop_dong(self):
		r = danh_gia(_dong(sl=10))
		self.assertEqual(r["trang_thai"], KHOP)
		self.assertEqual(r["ty_le_gia"], 1.01)
		self.assertEqual(r["chenh_lech_pt"], 1)
		self.assertEqual(r["chenh_lech_tien"], 10000)

	def test_dung_sai_ty_le(self):
		self.assertEqual(danh_gia(_dong(gia_ban=101050))["trang_thai"], KHOP)
		self.assertEqual(danh_gia(_dong(gia_ban=101060))["trang_thai"], LECH_GIA)
		self.assertEqual(danh_gia(_dong(gia_ban=100940))["trang_thai"], LECH_GIA)

	def test_ty_le_khac_theo_bo_loc(self):
		self.assertEqual(danh_gia(_dong(gia_ban=102000), ty_le=1.02)["trang_thai"], KHOP)

	def test_nhieu_loai_lech_cung_luc(self):
		r = _dong(gia_ban=110000, ts_ban=10, ts_mua=8)
		r["dvt_mua"] = "Thùng"
		self.assertEqual(danh_gia(r)["trang_thai"], f"{LECH_GIA}, {LECH_THUE}, {LECH_DVT}")

	def test_thieu_dau_vao_va_tra_hang(self):
		self.assertEqual(danh_gia(_dong(pi=None))["trang_thai"], THIEU_DAU_VAO)
		self.assertIsNone(danh_gia(_dong(pi=None)).get("ty_le_gia"))
		self.assertEqual(danh_gia(_dong(pi=None, tra_hang=1))["trang_thai"], TRA_HANG)

	def test_gia_mua_bang_khong(self):
		r = danh_gia(_dong(gia_mua=0))
		self.assertIsNone(r["ty_le_gia"])
		self.assertEqual(r["trang_thai"], LECH_GIA)

	def test_loc_trang_thai(self):
		self.assertTrue(hop_trang_thai(KHOP, ""))
		self.assertTrue(hop_trang_thai(f"{LECH_GIA}, {LECH_THUE}", LECH_THUE))
		self.assertFalse(hop_trang_thai(LECH_GIA, LECH_THUE))
		self.assertTrue(hop_trang_thai(TRA_HANG, CHUA_KHOP))
		self.assertFalse(hop_trang_thai(KHOP, CHUA_KHOP))


class TestNhomVaTong(unittest.TestCase):
	def test_danh_dau_manh_va_dong_mua_chia_se(self):
		data = danh_dau_nhom(
			[
				{"_dong_ban": "B1", "_dong_mua": "M1"},
				{"_dong_ban": "B1", "_dong_mua": None},
				{"_dong_ban": "B2", "_dong_mua": "M2"},
				{"_dong_ban": "B3", "_dong_mua": "M2"},
			]
		)
		self.assertEqual([r["manh"] for r in data], ["1/2", "2/2", "", ""])
		self.assertNotIn("_ghi_chu", data[0])
		self.assertEqual(data[2]["_ghi_chu"], ["Dòng HĐ mua chia cho 2 dòng bán"])

	def test_tong_chi_tinh_ty_le_tren_dong_da_ghep(self):
		data = [
			danh_gia(_dong(sl=10)),
			danh_gia(_dong(gia_ban=50000, pi=None)),
			danh_gia({**_dong(gia_ban=-101000, pi=None, tra_hang=1), "sales_invoice": "SI-2"}),
		]
		t = tong_hop(data)
		self.assertEqual(t["thanh_tien_ban"], 1010000 + 50000 - 101000)
		self.assertEqual(t["thanh_tien_mua"], 1000000)
		self.assertEqual(t["ty_le_gia"], 1.01)
		self.assertEqual(t["chenh_lech_tien"], 10000)
		tt = t["tom_tat"]
		self.assertEqual((tt["so_dong"], tt["so_hd_ban"], tt["so_hd_mua"], tt["so_dong_lech"]), (3, 2, 1, 0))
		self.assertEqual(tt["doanh_thu_co_dau_vao"], 1010000)
		self.assertEqual(tt["doanh_thu_thieu_dau_vao"], 50000)
		self.assertEqual((tt["dem"][KHOP], tt["dem"][THIEU_DAU_VAO], tt["dem"][TRA_HANG]), (1, 1, 1))

	def test_tong_khong_co_dong_ghep(self):
		t = tong_hop([danh_gia(_dong(pi=None))])
		self.assertIsNone(t["ty_le_gia"])
		self.assertEqual(t["chenh_lech_tien"], 0)

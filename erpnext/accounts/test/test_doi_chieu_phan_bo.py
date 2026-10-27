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


def _ban_ma(sl, gia, ngay, so_detail=None, trong_ky=True, ten="SI-1", ma="VITD"):
	return {
		**_ban(sl, sl * gia, so_detail=so_detail, trong_ky=trong_ky, ten=ten),
		"item_code": ma,
		"net_rate": gia,
		"posting_date": ngay,
	}


def _mua_ma(sl, gia, ngay, ten="PI-9", ma="VITD"):
	return {
		**_mua(sl, sl * gia, ten=ten),
		"item_code": ma,
		"net_rate": gia,
		"posting_date": ngay,
		"parent": ten,
	}


class TestGhepTheoMa(unittest.TestCase):
	def test_ghep_du_phong_khi_khong_co_so(self):
		kq = ghep([_ban_ma(2, 11711190, "2026-10-10")], {}, [_mua_ma(2, 11595238, "2026-10-05")])
		self.assertEqual(len(kq), 1)
		self.assertTrue(kq[0]["theo_ma"])
		self.assertEqual(kq[0]["mua"]["thanh_tien"], 2 * 11595238)

	def test_khac_ma_khong_ghep(self):
		kq = ghep([_ban_ma(2, 1010, "2026-10-10")], {}, [_mua_ma(2, 1000, "2026-10-05", ma="KHAC")])
		self.assertIsNone(kq[0]["mua"])

	def test_chuoi_uu_tien_truoc_du_phong(self):
		# Dòng bán sau có chuỗi tới PI-C; dòng bán trước không có SO. PI-C không được đem
		# cho dòng trước, dù nó xếp trước theo thời gian.
		ban = [
			_ban_ma(5, 1010, "2026-10-01", ten="SI-1"),
			_ban_ma(5, 1010, "2026-10-02", so_detail="SOI-1", ten="SI-2"),
		]
		kq = ghep(ban, {"SOI-1": [_mua(5, 5000, ten="PI-C")]}, [_mua_ma(5, 1000, "2026-09-30", ten="PI-D")])
		self.assertEqual(
			[(m["ban"]["hoa_don"], m["mua"]["hoa_don"]) for m in kq], [("SI-1", "PI-D"), ("SI-2", "PI-C")]
		)
		self.assertTrue(kq[0]["theo_ma"])
		self.assertNotIn("theo_ma", kq[1])

	def test_ban_ky_truoc_da_tieu_pi_du_phong(self):
		ban = [_ban_ma(3, 1010, "2026-09-20", trong_ky=False, ten="SI-T9"), _ban_ma(3, 1010, "2026-10-05")]
		kq = ghep(ban, {}, [_mua_ma(4, 1000, "2026-09-01")])
		self.assertEqual(len(kq), 2)
		self.assertEqual((kq[0]["ban"]["sl"], kq[0]["mua"]["sl"]), (1, 1))
		self.assertIsNone(kq[1]["mua"])
		self.assertEqual(kq[1]["ban"]["sl"], 2)

	def test_uu_tien_ty_le_hop_dong(self):
		du_phong = [_mua_ma(2, 900, "2026-10-09", ten="PI-RE"), _mua_ma(2, 1000, "2026-09-01", ten="PI-DUNG")]
		kq = ghep([_ban_ma(2, 1010, "2026-10-10")], {}, du_phong)
		self.assertEqual(kq[0]["mua"]["hoa_don"], "PI-DUNG")

	def test_cung_ty_le_uu_tien_pi_gan_nhat_truoc_hd_ban(self):
		du_phong = [
			_mua_ma(2, 1000, "2026-10-20", ten="PI-SAU"),
			_mua_ma(2, 1000, "2026-08-01", ten="PI-XA"),
			_mua_ma(2, 1000, "2026-10-08", ten="PI-GAN"),
		]
		kq = ghep([_ban_ma(2, 1010, "2026-10-10")], {}, du_phong)
		self.assertEqual(kq[0]["mua"]["hoa_don"], "PI-GAN")

	def test_lech_gia_van_ghep(self):
		kq = ghep([_ban_ma(1, 1500, "2026-10-10")], {}, [_mua_ma(1, 1000, "2026-10-01")])
		self.assertEqual(kq[0]["mua"]["hoa_don"], "PI-9")

	def test_tra_hang_khong_ghep_du_phong(self):
		ban = {**_ban_ma(-1, 1010, "2026-10-10"), "is_return": 1}
		kq = ghep([ban], {}, [_mua_ma(1, 1000, "2026-10-01")])
		self.assertIsNone(kq[0]["mua"])

	def test_tong_dem_dong_theo_ma(self):
		t = tong_hop([{**danh_gia(_dong(sl=10)), "theo_ma": 1}, danh_gia(_dong(gia_ban=50000, pi=None))])
		self.assertEqual(t["tom_tat"]["so_dong_theo_ma"], 1)
		self.assertEqual(t["tom_tat"]["doanh_thu_theo_ma"], 1010000)


class TestGhepTheoMaQuyDoi(unittest.TestCase):
	def test_ghep_khac_dvt_theo_don_vi_kho(self):
		# NCC xuất 1 hộp = 30 test; bán 30 test.
		ban = {**_ban_ma(30, 27068, "2026-09-15"), "conversion_factor": 1}
		mua = {**_mua_ma(1, 804000, "2026-08-28"), "conversion_factor": 30}
		kq = ghep([ban], {}, [mua])
		self.assertEqual(len(kq), 1)
		self.assertEqual((kq[0]["ban"]["sl"], kq[0]["mua"]["sl"]), (30, 1))
		self.assertEqual(kq[0]["mua"]["thanh_tien"], 804000)

	def test_tach_mot_phan_hop(self):
		ban = {**_ban_ma(15, 27068, "2026-09-15"), "conversion_factor": 1}
		mua = {**_mua_ma(1, 804000, "2026-08-28"), "conversion_factor": 30}
		kq = ghep([ban], {}, [mua])
		self.assertEqual((kq[0]["ban"]["sl"], kq[0]["mua"]["sl"]), (15, 0.5))
		self.assertEqual(kq[0]["mua"]["thanh_tien"], 402000)

	def test_ty_le_ngoai_khoang_khong_ghep(self):
		# 5 hộp ghi hệ số 1 nhưng giá theo 10 đĩa: sai ĐVT, không ghép.
		kq = ghep([_ban_ma(5, 17776, "2026-09-15")], {}, [_mua_ma(5, 176000, "2026-08-04")])
		self.assertIsNone(kq[0]["mua"])

	def test_pi_truoc_ngay_ban_uu_tien_hon_gia_khop(self):
		du_phong = [
			_mua_ma(4, 1500000, "2026-08-05", ten="PI-T8"),
			_mua_ma(4, 1428571, "2026-10-06", ten="PI-T10"),
		]
		kq = ghep([_ban_ma(4, 1442857, "2026-09-22")], {}, du_phong)
		self.assertEqual(kq[0]["mua"]["hoa_don"], "PI-T8")

	def test_hang_0_dong_khong_lech_gia(self):
		r = danh_gia(_dong(gia_ban=0, gia_mua=0))
		self.assertEqual(r["trang_thai"], KHOP)
		self.assertIn("Hàng 0 đồng", r["_ghi_chu"])

	def test_khac_dvt_cung_don_vi_kho_so_theo_don_vi_kho(self):
		r = {
			**_dong(gia_ban=27068 * 30, gia_mua=804000, sl=30),
			"don_gia_ban": 27068,
			"dvt_ban": "Test",
			"dvt_mua": "hộp",
			"_he_so_ban": 1,
			"_he_so_mua": 30,
			"_dvt_kho_ban": "Test",
			"_dvt_kho_mua": "Test",
		}
		danh_gia(r)
		self.assertEqual(r["trang_thai"], KHOP)
		self.assertIn("Quy đổi 1 hộp = 30 Test", r["_ghi_chu"])

	def test_khac_don_vi_kho_van_lech_dvt(self):
		r = {**_dong(), "dvt_ban": "Test", "dvt_mua": "hộp", "_dvt_kho_ban": "Test", "_dvt_kho_mua": "hộp"}
		self.assertIn(LECH_DVT, danh_gia(r)["trang_thai"])


def _ban_so(sl, gia, ngay, so="SO-1", ten="SI-1", ma="VITD"):
	return {**_ban_ma(sl, gia, ngay, so_detail="SOI-1", ten=ten, ma=ma), "sales_order": so}


def _mua_cap(sl, gia, ngay, so="SO-1", ten="PI-9", ma="VITD"):
	return {**_mua_ma(sl, gia, ngay, ten=ten, ma=ma), "so_cua_po": (so,)}


class TestGhepTrongCapSoPo(unittest.TestCase):
	def test_ghep_trong_cap_khong_gan_theo_ma(self):
		kq = ghep([_ban_so(2, 1010, "2026-10-10")], {}, [_mua_cap(2, 1000, "2026-10-05")])
		self.assertEqual(kq[0]["tang"], 2)
		self.assertNotIn("theo_ma", kq[0])

	def test_cap_uu_tien_hon_theo_ma(self):
		# PI-MA đúng giá, ngày gần hơn, nhưng không cùng đơn bán; PI-CAP của PO lập từ SO-1.
		du_phong = [
			_mua_ma(2, 1000, "2026-10-09", ten="PI-MA"),
			_mua_cap(2, 1000, "2026-09-01", ten="PI-CAP"),
		]
		kq = ghep([_ban_so(2, 1010, "2026-10-10")], {}, du_phong)
		self.assertEqual(kq[0]["mua"]["hoa_don"], "PI-CAP")

	def test_cap_khac_so_roi_xuong_theo_ma(self):
		kq = ghep([_ban_so(2, 1010, "2026-10-10")], {}, [_mua_cap(2, 1000, "2026-10-05", so="SO-2")])
		self.assertEqual((kq[0]["tang"], kq[0]["theo_ma"]), (3, True))

	def test_cung_ma_chon_theo_so_luong_roi_gia(self):
		du_phong = [
			_mua_cap(5, 1000, "2026-10-01", ten="PI-5"),
			_mua_cap(3, 950, "2026-10-02", ten="PI-3-LECH"),
			_mua_cap(3, 1000, "2026-10-03", ten="PI-3"),
		]
		kq = ghep([_ban_so(3, 1010, "2026-10-10")], {}, du_phong)
		self.assertEqual([m["mua"]["hoa_don"] for m in kq], ["PI-3"])

	def test_cap_khong_chan_theo_ty_le_gia(self):
		# Có chứng từ nối: ghép rồi để danh_gia báo lệch, thay vì báo thiếu đầu vào.
		kq = ghep([_ban_so(5, 17776, "2026-09-15")], {}, [_mua_cap(5, 176000, "2026-08-04")])
		self.assertEqual(kq[0]["tang"], 2)

	def test_cap_khong_gianh_pi_cua_dong_sau_qua_chuoi(self):
		# Lượt chuỗi chạy hết trước: PI-C để dành cho SI-2, SI-1 lấy PI-D theo cặp.
		ban = [
			_ban_so(2, 1010, "2026-10-01", ten="SI-1"),
			{**_ban_so(2, 1010, "2026-10-02", ten="SI-2"), "so_detail": "SOI-2"},
		]
		kq = ghep(ban, {"SOI-2": [_mua(2, 2000, ten="PI-C")]}, [_mua_cap(2, 1000, "2026-09-30", ten="PI-D")])
		self.assertEqual(
			[(m["ban"]["hoa_don"], m["mua"]["hoa_don"]) for m in kq], [("SI-1", "PI-D"), ("SI-2", "PI-C")]
		)

	def test_tong_dem_rieng_cap_va_theo_ma(self):
		t = tong_hop([{**danh_gia(_dong(sl=10)), "theo_cap": 1}, {**danh_gia(_dong()), "theo_ma": 1}])
		self.assertEqual((t["tom_tat"]["so_dong_theo_cap"], t["tom_tat"]["so_dong_theo_ma"]), (1, 1))
		self.assertEqual(t["tom_tat"]["doanh_thu_theo_cap"], 1010000)

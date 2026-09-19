"""Cắt an toàn tiêu đề `Error Log` (vòng sửa 2/5, điều phối).

Bài học đắt: `Error Log.method` là `Data(140)`, và một tiêu đề quá dài bên
trong CHÍNH khối `except` dựng lên để "đừng để một bản ghi hỏng làm sập cả
lời gọi" lại tự ném `CharacterLengthExceededError` — lưới an toàn thủng ở
lối thoát hiểm của nó. Xem lý lẽ đầy đủ ở `vitri/nhat_ky_loi.py`. Module này
chỉ khoá đúng HÀM CẮT; bằng chứng "cắt xong thì `tra_cuu`/`hang_chua_xep`
không còn nổ nữa" nằm ở `test_quet.py`/`test_phieu_xep_vi_tri.py`.
"""

from frappe.tests.utils import FrappeTestCase

from erpnext.vi_tri_kho.vitri.nhat_ky_loi import TRAN_DO_DAI_TIEU_DE, cat_tieu_de


class TestCatTieuDe(FrappeTestCase):
	def test_tieu_de_ngan_giu_nguyen(self):
		"""Đa số tiêu đề trong dự án NGẮN hơn 140 nhiều — không được đụng vào
		chúng, đổi một tiêu đề vốn đã hợp lệ là làm Error Log khó tra hơn."""
		ngan = "vi_tri_kho: tra_cuu loi (LO-001)"
		self.assertEqual(cat_tieu_de(ngan), ngan)

	def test_dung_bang_tran_giu_nguyen(self):
		"""Biên CHÍNH XÁC = 140: không được cắt (thừa một ký tự là sai lệch bất
		cần thiết), và cũng không được vượt ở nhánh này."""
		dung_140 = "T" * TRAN_DO_DAI_TIEU_DE
		ket_qua = cat_tieu_de(dung_140)
		self.assertEqual(ket_qua, dung_140)
		self.assertEqual(len(ket_qua), TRAN_DO_DAI_TIEU_DE)

	def test_qua_tran_mot_ky_tu_bi_cat(self):
		"""Biên vượt tối thiểu (141) — đây là ca `_validate_length` sẽ ném lỗi
		nếu không cắt, nên đây là ca QUYẾT ĐỊNH của cả module này."""
		qua_140 = "T" * (TRAN_DO_DAI_TIEU_DE + 1)
		ket_qua = cat_tieu_de(qua_140)
		self.assertLessEqual(len(ket_qua), TRAN_DO_DAI_TIEU_DE)
		self.assertNotEqual(ket_qua, qua_140)

	def test_tieu_de_rat_dai_van_duoi_tran_va_con_nhan_ra_duoc_da_cat(self):
		"""Ca thật gây ra bẫy: một mã quét/số lô GÕ TAY dài hàng trăm ký tự.

		Hai vế: (1) kết quả LUÔN `<= 140` — đây là điều kiện duy nhất
		`_validate_length` thật sự kiểm; (2) kết quả vẫn PHẢI nhận ra được là
		đã bị cắt (không cắt câm lặng) — thiếu vế 2 thì một cài đặt cắt thô
		`tieu_de[:140]` (không dấu hiệu gì) vẫn qua được bài chỉ kiểm vế 1.
		"""
		rat_dai = "vi_tri_kho: tra_cuu loi (" + ("X" * 500) + ")"
		ket_qua = cat_tieu_de(rat_dai)
		self.assertLessEqual(len(ket_qua), TRAN_DO_DAI_TIEU_DE)
		self.assertNotEqual(
			ket_qua, rat_dai[:TRAN_DO_DAI_TIEU_DE], "phải có dấu hiệu ĐÃ CẮT, không phải cắt thô"
		)
		self.assertIn("cắt", ket_qua, "kết quả phải còn NHẬN RA ĐƯỢC là đã bị cắt")

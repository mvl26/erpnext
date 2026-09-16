"""Lấy danh sách hàng đang nằm ở ô "Chưa xếp vị trí" để đổ vào phiếu xếp.

CÙNG NGUỒN DỮ LIỆU với báo cáo *Hàng chưa xếp vị trí*
(`report/hang_chua_xep_vi_tri/`) — cùng điều kiện `la_o_chua_xep = 1` và
`so_luong != 0`. Hai chỗ mà nói khác nhau thì thủ kho nhìn báo cáo rồi mở
phiếu, thấy lệch, và mất tin vào cả hai.
"""

import frappe
from frappe import _

from erpnext.vi_tri_kho.vitri.goi_y import goi_y_o

# Giống `tem.py`: thủ kho phải tự làm được, đây là việc hằng ngày chứ không
# phải thao tác thiết lập. Khác `bat_kho.py` (sinh ô, bật kho) vốn chỉ mở
# cho quản lý.
VAI_TRO_DUOC_XEP = {"System Manager", "Stock Manager", "Stock User"}


def _kiem_tra_quyen():
	"""`@frappe.whitelist()` một mình chỉ chặn khách vãng lai.

	Danh sách này lộ ra toàn bộ hàng tồn đang chờ xếp của kho, nên đăng nhập
	hợp lệ không phải điều kiện đủ. `Website User` (khách hàng cổng) không có
	vai trò nào ở đây nên bị chặn.
	"""
	if not VAI_TRO_DUOC_XEP & set(frappe.get_roles()):
		frappe.throw(_("Bạn không có quyền xem hàng chưa xếp vị trí."), frappe.PermissionError)


@frappe.whitelist()
def hang_chua_xep(kho: str) -> list[dict]:
	"""Các dòng tồn ở ô "Chưa xếp vị trí" của `kho`, dạng dòng phiếu sẵn.

	`den_o` được ĐIỀN SẴN từ `goi_y.goi_y_o()` kể từ 15/09/2026. Trước đó nó cố
	ý để trống, vì căn cứ duy nhất khi ấy là `suc_chua` (= 0 trên cả 214 ô) và
	gợi ý sai thì thủ kho tin theo rồi xếp nhầm. Căn cứ nay khác hẳn: mặt hàng
	có vị trí cố định, nên "xếp đâu" trả lời được mà không cần sức chứa.

	Mặt hàng CHƯA gán vẫn để `den_o` trống — không đoán. `ly_do_goi_y` luôn có
	giá trị để màn hình nói được vì sao trống.

	Gợi ý KHÔNG chặn và KHÔNG ghi đè: thủ kho đứng trước kệ biết những thứ hệ
	không biết.

	Ruling N (vòng sửa 1, review điều phối): một bản gán hỏng toạ độ (`lft`/
	`rgt` = 0, xem `goi_y_o`) khiến `goi_y_o` NÉM LỖI cho ĐÚNG một mặt hàng.
	Nuốt lỗi đó ở đây — không để nó văng ra khỏi cả vòng lặp — vì cái giá
	ngược lại nặng hơn nhiều: một mặt hàng lỗi dữ liệu sẽ làm SẬP RPC này cho
	CẢ kho, nút "Lấy hàng chưa xếp" không mở nổi cho bất cứ ai, trong khi hàng
	của những mặt hàng lành vẫn đang chờ ở `ZZZ-CHUA-XEP`. Đó là hình dạng
	chặn nặng hơn hẳn tinh thần "gợi ý không chặn" ở trên. Lỗi thật không mất
	— xem Error Log tiêu đề `vi_tri_kho: hang_chua_xep goi_y_o loi`.

	Khối C §8 (Task 4): bộ đệm `goi_y_o` giờ khoá theo CẶP (mặt hàng, lô),
	không còn khoá theo riêng mặt hàng. Trước §8, gợi ý chỉ phụ thuộc vị trí
	gán — thứ CHUNG cho mọi lô của một mặt hàng — nên khoá theo mặt hàng vẫn
	đúng. Từ §8, `goi_y_o` còn nhận `so_lo` và ưu tiên đúng ô đã in trên tem
	của LÔ đó (`Batch.custom_o_in_tem`, riêng từng lô). Giữ khoá cũ thì lô
	thứ hai của cùng một mặt hàng nhận lại gợi ý của lô thứ nhất, và tem của
	nó nói dối.
	"""
	_kiem_tra_quyen()
	dong = frappe.db.sql(
		"""
		select lb.vat_tu as vat_tu, nullif(lb.so_lo, '') as so_lo,
		       lb.o as tu_o, lb.so_luong as so_luong
		from `tabLocation Balance` lb
		join `tabStorage Location` sl on sl.name = lb.o
		where sl.la_o_chua_xep = 1 and lb.kho = %(kho)s and lb.so_luong != 0
		order by lb.vat_tu asc, lb.so_lo asc
		""",
		{"kho": kho},
		as_dict=True,
	)

	# Một lời gọi `goi_y_o` cho mỗi (MẶT HÀNG, LÔ).
	#
	# Trước khối C khoá đệm chỉ là `vat_tu`, vì gợi ý khi ấy chỉ phụ thuộc vị trí
	# gán — thứ chung cho mọi lô của mặt hàng. Từ khối C §8, gợi ý còn phụ thuộc
	# `Batch.custom_o_in_tem`, vốn RIÊNG từng lô. Giữ khoá cũ thì lô thứ hai
	# nhận gợi ý của lô thứ nhất và tem của nó nói dối.
	bo_nho: dict[tuple, tuple] = {}
	for d in dong:
		khoa = (d.vat_tu, d.so_lo)
		if khoa not in bo_nho:
			try:
				bo_nho[khoa] = goi_y_o(d.vat_tu, kho, d.so_lo)
			except Exception:
				# Ruling N: KHÔNG để lỗi của MỘT (mặt hàng, lô) làm sập danh sách
				# của CẢ kho — xem lý do đầy đủ ở docstring hàm này. `frappe.log_error`
				# (không truyền `message`) tự chụp traceback hiện tại, giữ dấu vết
				# thật trong Error Log để người vận hành đi sửa dữ liệu gán, thay
				# vì lỗi biến mất lặng lẽ. Tiêu đề mang cả số lô — Task 4 tách
				# khoá theo lô nên một lô lỗi (vd. tem trỏ vào dữ liệu hỏng) không
				# còn định danh đủ chỉ bằng mặt hàng.
				frappe.log_error(
					title=f"vi_tri_kho: hang_chua_xep goi_y_o loi ({d.vat_tu}/{d.so_lo})"
				)
				# Mục 5 (review tổng): câu cũ KHẲNG ĐỊNH đây là "lỗi dữ liệu vị
				# trí" — sai, vì `except Exception` ở trên bắt MỌI ngoại lệ,
				# kể cả một lỗi LẬP TRÌNH trong `goi_y_o` (không chỉ toạ độ
				# 0/0 của §5.1). Khẳng định nhầm nguyên nhân khiến người đọc
				# đi sửa dữ liệu trong khi thứ hỏng là mã. Câu mới chỉ nói
				# "không gợi ý được", không đoán vì sao — nhưng vẫn PHẢI giữ
				# phần phân biệt với "chưa gán" (mặt hàng đã có gán, ai đó
				# đừng tưởng nhầm là chưa gán rồi đi gán lại một gán vốn đã
				# đúng, chỉ là `goi_y_o` đang không tính được cho nó).
				bo_nho[khoa] = (
					None,
					_(
						"không gợi ý được cho {0} — xem Error Log. KHÔNG PHẢI mặt hàng "
						"chưa gán, đừng gán lại"
					).format(d.vat_tu),
				)
		d["den_o"], d["ly_do_goi_y"] = bo_nho[khoa]
	return dong

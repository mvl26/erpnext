"""Gợi ý ô để xếp hàng, dựa trên gán vị trí cố định của mặt hàng.

Đây là thứ mở khoá một quyết định cũ. `xep.py::hang_chua_xep` từng cố ý để
trống `den_o` với lý do "không có căn cứ nào để gợi ý (suc_chua = 0 trên cả
214 ô), mà gợi ý sai thì thủ kho tin theo rồi xếp nhầm". Lý do đó đúng KHI
CĂN CỨ DUY NHẤT LÀ SỨC CHỨA. Gán cố định là một căn cứ khác: khi ô đã thuộc
đúng một mặt hàng thì "xếp đâu" trả lời được mà không cần biết ô chứa nổi bao
nhiêu.

Hàm trả về CẶP `(ô, lý do)`, không phải mỗi ô. Lý do hiện cạnh gợi ý trên
phiếu xếp, vì thủ kho cần phân biệt "ô này trống" với "ô này đã có hàng cùng
loại, dồn vào" TRƯỚC khi ra mở kệ — hai việc khác nhau ngoài kho.
"""

import frappe
from frappe import _

from erpnext.vi_tri_kho.vitri.fefo import _TO_TIEN_TAT

# Ứng viên: ô LÁ thật trong nhánh, không phải nút nhóm, không phải ô ảo, và
# không nằm dưới một nút đang ngừng dùng.
#
# `_TO_TIEN_TAT` mượn nguyên từ `fefo.py` chứ KHÔNG chép lại. Nó mã hoá luật
# "ô coi như tắt nếu chính nó HOẶC bất kỳ tổ tiên nào tắt". Có hai bản thì một
# ngày nào đó sửa một chỗ quên chỗ kia, và khi ấy gợi ý trỏ vào một dãy đang
# tắt trong khi `fefo` từ chối lấy hàng từ đó — hai nửa của hệ nói ngược nhau,
# không có gì báo. Vị từ dùng alias `sl`, nên truy vấn dưới phải giữ đúng alias.
_UNG_VIEN = f"""
	from `tabStorage Location` sl
	where sl.lft between %(lft)s and %(rgt)s
	  and ifnull(sl.is_group, 0) = 0
	  and ifnull(sl.la_o_chua_xep, 0) = 0
	  and not {_TO_TIEN_TAT}
"""


def goi_y_o(vat_tu: str, kho: str) -> tuple[str | None, str]:
	"""Ô nên xếp `vat_tu` vào, kèm lý do. `(None, lý do)` nếu không gợi ý được."""
	gan = frappe.db.sql(
		"""
		select p.vi_tri as vi_tri, s.lft as lft, s.rgt as rgt
		from `tabItem Location Preference` p
		join `tabStorage Location` s on s.name = p.vi_tri
		where p.name = %(vat_tu)s and p.kho = %(kho)s
		""",
		{"vat_tu": vat_tu, "kho": kho},
		as_dict=True,
	)
	if not gan:
		return None, _("mặt hàng chưa gán vị trí cố định")

	g = gan[0]
	if not g.lft or not g.rgt:
		# Cùng bẫy đã trả giá ở `fefo.py` và `tem.py`: `between 0 and 0` khớp
		# MỌI bản ghi 0/0 toàn hệ, nên sẽ gợi ý một ô của kho khác. Chặn ở
		# nguồn, không trả về im lặng — gợi ý sai thì thủ kho tin theo.
		frappe.throw(
			_(
				"Vị trí {0} gán cho mặt hàng {1} chưa có toạ độ trong cây nên không "
				"gợi ý được. Lưu lại vị trí đó, hoặc chạy `bench migrate`."
			).format(g.vi_tri, vat_tu)
		)

	tham_so = {"lft": g.lft, "rgt": g.rgt, "vat_tu": vat_tu}

	trong = frappe.db.sql(
		f"""
		select sl.name
		{_UNG_VIEN}
		  and ifnull((
		        select sum(lb.so_luong) from `tabLocation Balance` lb where lb.o = sl.name
		      ), 0) = 0
		order by sl.lft asc
		limit 1
		""",
		tham_so,
	)
	if trong:
		return trong[0][0], _("ô trống đầu tiên trong {0}").format(g.vi_tri)

	# Không còn ô trống → dồn vào ô đang chứa CHÍNH mặt hàng này (phương án (b),
	# chủ đầu tư chốt 15/09). Không có nhánh này thì gán vào một Ô lẻ khiến lần
	# nhập thứ hai trở đi luôn báo đầy.
	cung_hang = frappe.db.sql(
		f"""
		select sl.name
		{_UNG_VIEN}
		  and exists (
		        select 1 from `tabLocation Balance` lb
		        where lb.o = sl.name and lb.vat_tu = %(vat_tu)s and lb.so_luong != 0
		      )
		order by sl.lft asc
		limit 1
		""",
		tham_so,
	)
	if cung_hang:
		return cung_hang[0][0], _("dồn vào ô đang có hàng cùng mặt hàng")

	tong = frappe.db.sql(f"select count(*) {_UNG_VIEN}", tham_so)[0][0]
	return None, _("vùng {0} đã đầy: {1}/{1} ô đang chứa hàng khác").format(g.vi_tri, tong)

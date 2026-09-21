"""Gợi ý ô để xếp hàng, dựa trên gán vị trí cố định của mặt hàng.

Đây là thứ mở khoá một quyết định cũ. `xep.py::hang_chua_xep` từng cố ý để
trống `den_o` với lý do "không có căn cứ nào để gợi ý (suc_chua = 0 trên cả
214 ô), mà gợi ý sai thì thủ kho tin theo rồi xếp nhầm". Lý do đó đúng KHI
CĂN CỨ DUY NHẤT LÀ SỨC CHỨA. Gán cố định là một căn cứ khác: khi ô đã thuộc
đúng một mặt hàng thì "xếp đâu" trả lời được mà không cần biết ô chứa nổi bao
nhiêu.

Hàm trả về BỘ BA `(ô, lý do, tem_hong)`, không phải mỗi ô. Lý do hiện cạnh gợi
ý trên phiếu xếp, vì thủ kho cần phân biệt "ô này trống" với "ô này đã có hàng
cùng loại, dồn vào" TRƯỚC khi ra mở kệ — hai việc khác nhau ngoài kho.

Vòng sửa 2 (điều phối, sau Task 4): `tem_hong` là một TRƯỜNG RIÊNG, không phải
thứ bên gọi tự suy ra bằng cách so khớp chuỗi trong `lý do`. Hai lẽ:

1. Chuỗi lý do đi qua `_()` — dịch được. Một bản dịch tiếng Anh không còn chữ
   "tem" nào, và bất kỳ bộ lọc nào so khớp chuỗi (`"tem" in ly_do`) sẽ âm thầm
   khớp 0 dòng. Giao thức giữa hai tầng không được phép đi qua văn bản cho
   người đọc.
2. Ngay cả không dịch, chuỗi "theo ô đã in trên tem của lô {0}" (tem ĐÚNG) và
   "tem của lô {0} in ô {1} nhưng ô đó không xếp được nữa" (tem HỎNG) đều chứa
   chữ "tem" — so khớp chuỗi con gộp nhầm cả hai case làm một, đúng lớp lỗi
   "màn hình nói sai sự thật" (xem `location_transfer.js`, nhóm cảnh báo
   "tem cũ không dùng được").

`tem_hong = True` CHỈ khi: có `so_lo`, lô đó CÓ `custom_o_in_tem`, và ô ghi
trên tem đó không còn dùng được (phải rơi lại một nhánh khác). Mọi nhánh khác
— kể cả tem đúng, kể cả không truyền `so_lo` — đều `tem_hong = False`.
"""

import frappe
from frappe import _

from erpnext.warehouse_operations.vitri.fefo import to_tien_tat

# Ứng viên: ô LÁ thật trong nhánh, không phải nút nhóm, không phải ô ảo, và
# không nằm dưới một nút đang ngừng dùng.
#
# `to_tien_tat()` mượn nguyên từ `fefo.py` chứ KHÔNG chép lại. Nó mã hoá luật
# "ô coi như tắt nếu chính nó HOẶC bất kỳ tổ tiên nào tắt". Có hai bản thì một
# ngày nào đó sửa một chỗ quên chỗ kia, và khi ấy gợi ý trỏ vào một dãy đang
# tắt trong khi `fefo` từ chối lấy hàng từ đó — hai nửa của hệ nói ngược nhau,
# không có gì báo. Truy vấn dưới đặt bảng vị trí là `sl`, nên gọi hàm với
# alias đó.
_UNG_VIEN = f"""
	from `tabStorage Location` sl
	where sl.lft between %(lft)s and %(rgt)s
	  and ifnull(sl.is_group, 0) = 0
	  and ifnull(sl.la_o_chua_xep, 0) = 0
	  and not {to_tien_tat("sl")}
"""


def goi_y_o(vat_tu: str, kho: str, so_lo: str | None = None) -> tuple[str | None, str, bool]:
	"""Ô nên xếp `vat_tu` vào, kèm lý do và cờ tem hỏng.

	`(None, lý do, False)` nếu không gợi ý được. `so_lo` TUỲ CHỌN: lúc nạp dòng
	trên `Batch Entry` thì lô chưa tồn tại, và phiếu xếp thì có. Có `so_lo` và
	lô đó đã in tem → ưu tiên đúng ô đã in (spec khối C §8).

	`tem_hong` (phần tử thứ ba): `True` đúng khi lô có tem NHƯNG ô ghi trên tem
	không còn dùng được, nên `goi_y_o` phải trả một ô KHÁC. Bên gọi cần biết
	CA NÀY để báo cho thủ kho — họ đang cầm tờ tem cũ trên tay — nhưng KHÔNG
	được suy ra nó bằng cách so khớp chuỗi `lý do` (xem docstring module).
	"""
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
		return None, _("mặt hàng chưa gán vị trí cố định"), False

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

	# Ô ĐÃ IN TEM đi trước mọi thứ khác (spec khối C §8).
	#
	# Vì sao ưu tiên chứ không phải "giữ chỗ": giữ chỗ cần hết hạn, cần dọn khi
	# huỷ, cần thêm một doctype nữa — tất cả để giải một bài mà một trường đã
	# giải xong. Ưu tiên khiến tem TỰ ỨNG NGHIỆM: cái gì in ra thì cái đó thành
	# sự thật, miễn là còn xếp vào được.
	#
	# Bốn điều kiện dưới đều CẦN, mỗi cái khoá một đường tem nói dối khác nhau:
	# nằm trong vùng gán (ai đó đổi gán sau khi in), là ô lá thật, không nằm
	# dưới nhánh ngừng dùng, và chưa bị mặt hàng KHÁC chiếm.
	ly_do_tem = None
	if so_lo:
		o_tem = frappe.db.get_value("Batch", so_lo, "custom_o_in_tem")
		if o_tem:
			dung_duoc = frappe.db.sql(
				f"""
				select sl.name
				{_UNG_VIEN}
				  and sl.name = %(o_tem)s
				  and not exists (
				        select 1 from `tabLocation Balance` lb
				        where lb.o = sl.name and lb.vat_tu != %(vat_tu)s and lb.so_luong != 0
				      )
				limit 1
				""",
				dict(tham_so, o_tem=o_tem),
			)
			if dung_duoc:
				return o_tem, _("theo ô đã in trên tem của lô {0}").format(so_lo), False
			# Không im lặng bỏ qua: thủ kho đang cầm một tờ tem in ô này trên tay.
			# Phải biết tem đó không dùng được nữa, và vì sao.
			ly_do_tem = _("tem của lô {0} in ô {1} nhưng ô đó không xếp được nữa").format(
				so_lo, o_tem
			)

	# `tem_hong` là CỜ, tách khỏi văn bản `ly_do_tem` — xem docstring module vì
	# sao bên gọi không được suy cờ này từ chuỗi lý do.
	tem_hong = ly_do_tem is not None

	def _ly_do(goc: str) -> str:
		return f"{ly_do_tem} — {goc}" if ly_do_tem else goc

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
		return trong[0][0], _ly_do(_("ô trống đầu tiên trong {0}").format(g.vi_tri)), tem_hong

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
		return cung_hang[0][0], _ly_do(_("dồn vào ô đang có hàng cùng mặt hàng")), tem_hong

	tong = frappe.db.sql(f"select count(*) {_UNG_VIEN}", tham_so)[0][0]
	return (
		None,
		_ly_do(_("vùng {0} đã đầy: {1}/{1} ô đang chứa hàng khác").format(g.vi_tri, tong)),
		tem_hong,
	)

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
def _ung_vien(vung: str) -> str:
	"""Mệnh đề `from … where` của ô ỨNG VIÊN nằm trong `vung` (một vị từ SQL trên
	`sl.lft`, gom MỌI nhánh đã gán — xem `goi_y_o`)."""
	return f"""
	from `tabStorage Location` sl
	where ({vung})
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
	# NHIỀU VỊ TRÍ (22/09/2026): mọi dòng gán của mặt hàng ở ĐÚNG kho này, theo thứ
	# tự dòng. Mỗi bước dưới đây là MỘT truy vấn gom mọi nhánh (`vung`), sắp theo
	# thứ tự dòng rồi thứ tự cây (`thu_tu`) — chủ đầu tư chốt "ô trống trước, bất
	# kể thuộc vị trí nào", nên bước ô trống xét HẾT các nhánh trước khi sang bước
	# dồn, không lấp đầy nhánh 1 rồi mới sang nhánh 2.
	gan = frappe.db.sql(
		"""
		select r.vi_tri as vi_tri, s.lft as lft, s.rgt as rgt
		from `tabItem Location Preference Row` r
		join `tabStorage Location` s on s.name = r.vi_tri
		where r.parent = %(vat_tu)s and r.parenttype = 'Item Location Preference'
		  and r.kho = %(kho)s
		order by r.idx asc
		""",
		{"vat_tu": vat_tu, "kho": kho},
		as_dict=True,
	)
	if not gan:
		return None, _("mặt hàng chưa gán vị trí cố định"), False

	for g in gan:
		_chan_toa_do_rong(g, vat_tu)

	tham_so = {"vat_tu": vat_tu}
	vung, thu_tu = [], []
	for i, g in enumerate(gan):
		tham_so[f"l{i}"], tham_so[f"r{i}"] = g.lft, g.rgt
		vung.append(f"sl.lft between %(l{i})s and %(r{i})s")
		thu_tu.append(f"when sl.lft between %(l{i})s and %(r{i})s then {i}")
	ung_vien = _ung_vien(" or ".join(vung))
	thu_tu_sql = f"case {' '.join(thu_tu)} end, sl.lft asc"

	def _nhanh_chua(o: str) -> str:
		"""Nút gán (dòng) chứa ô `o` — để lý do nói đúng "ô trống đầu tiên trong X"."""
		lft = frappe.db.get_value("Storage Location", o, "lft")
		return next((g.vi_tri for g in gan if g.lft <= lft <= g.rgt), gan[0].vi_tri)

	# Ô ĐÃ IN TEM đi trước mọi thứ khác (spec khối C §8): tem TỰ ỨNG NGHIỆM — cái
	# gì in ra thì thành sự thật, miễn còn xếp vào được. Bốn điều kiện đều CẦN, mỗi
	# cái khoá một đường tem nói dối: nằm trong MỘT nhánh đã gán ở kho này (ai đó
	# đổi gán sau khi in), là ô lá thật, không dưới nhánh ngừng dùng, chưa bị mặt
	# hàng KHÁC chiếm. Tem hỏng thì KHÔNG im lặng bỏ qua: thủ kho đang cầm tờ tem.
	ly_do_tem = None
	if so_lo:
		o_tem = frappe.db.get_value("Batch", so_lo, "custom_o_in_tem")
		if o_tem:
			dung_duoc = frappe.db.sql(
				f"""
				select sl.name
				{ung_vien}
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
			ly_do_tem = _("tem của lô {0} in ô {1} nhưng ô đó không xếp được nữa").format(
				so_lo, o_tem
			)

	return _goi_y_trong_vung(ung_vien, thu_tu_sql, tham_so, ly_do_tem, gan, _nhanh_chua)


def _chan_toa_do_rong(g, vat_tu: str) -> None:
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


def _goi_y_trong_vung(ung_vien, thu_tu_sql, tham_so, ly_do_tem, gan, _nhanh_chua):
	"""Bước 2–4 của `goi_y_o`: ô trống → ô đang chứa chính mặt hàng → đầy."""
	# `tem_hong` là CỜ, tách khỏi văn bản `ly_do_tem` — xem docstring module vì
	# sao bên gọi không được suy cờ này từ chuỗi lý do.
	tem_hong = ly_do_tem is not None

	def _ly_do(goc: str) -> str:
		return f"{ly_do_tem} — {goc}" if ly_do_tem else goc

	trong = frappe.db.sql(
		f"""
		select sl.name
		{ung_vien}
		  and ifnull((
		        select sum(lb.so_luong) from `tabLocation Balance` lb where lb.o = sl.name
		      ), 0) = 0
		order by {thu_tu_sql}
		limit 1
		""",
		tham_so,
	)
	if trong:
		o = trong[0][0]
		return o, _ly_do(_("ô trống đầu tiên trong {0}").format(_nhanh_chua(o))), tem_hong

	# Không còn ô trống ở BẤT KỲ nhánh nào → dồn vào ô đang chứa CHÍNH mặt hàng
	# này (phương án (b), chủ đầu tư chốt 15/09). Không có nhánh này thì gán vào
	# một Ô lẻ khiến lần nhập thứ hai trở đi luôn báo đầy.
	cung_hang = frappe.db.sql(
		f"""
		select sl.name
		{ung_vien}
		  and exists (
		        select 1 from `tabLocation Balance` lb
		        where lb.o = sl.name and lb.vat_tu = %(vat_tu)s and lb.so_luong != 0
		      )
		order by {thu_tu_sql}
		limit 1
		""",
		tham_so,
	)
	if cung_hang:
		return cung_hang[0][0], _ly_do(_("dồn vào ô đang có hàng cùng mặt hàng")), tem_hong

	tong = frappe.db.sql(f"select count(*) {ung_vien}", tham_so)[0][0]
	ten = ", ".join(g.vi_tri for g in gan)
	cau = (
		_("vùng {0} đã đầy: {1}/{1} ô đang chứa hàng khác").format(ten, tong)
		if len(gan) == 1
		else _("các vị trí đã gán ({0}) đã đầy: {1}/{1} ô đang chứa hàng khác").format(ten, tong)
	)
	return None, _ly_do(cau), tem_hong

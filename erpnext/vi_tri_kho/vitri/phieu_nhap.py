"""Phiếu nhập kho ↔ phiếu nhập lô: chẩn đoán, và chặn lô gõ tay lúc duyệt.

VÌ SAO FILE NÀY TỒN TẠI (chủ đầu tư thử luồng thật ngày 17/09/2026): phiếu nhập
`MAT-PRE-2026-00008` được DUYỆT với số lô `17/09/2026` — một ngày tháng gõ thẳng
vào ô lô chuẩn của ERPNext trên dòng phiếu nhập. Phiếu nhập lô không có lối vào
nào từ phiếu nhập, nên đường tự nhiên nhất là gõ lô ngay trên phiếu rồi duyệt —
bỏ qua hoàn toàn phiếu nhập lô: số lô nhà cung cấp mất, không có tem.

Spec khối C §4.3 đã cố ý KHÔNG chặn ô lô chuẩn, với lý do "dữ liệu không thiếu".
Lần thử đầu tiên cho thấy lý do đó sai ở chỗ quan trọng nhất: dữ liệu không
thiếu, nhưng nó SAI — và sai theo kiểu không ai phát hiện. Chủ đầu tư chốt chặn
lúc duyệt, giới hạn trong kho đã bật quản lý vị trí.

MỘT định nghĩa của "dòng này đã khai lô đúng đường" (`_lo_qua_phieu_nhap_lo`),
dùng chung cho cả chẩn đoán lẫn phép chặn. Hai bản là một ngày nào đó màn hình
bảo "phiếu này ổn" trong khi nút Duyệt vẫn từ chối — hoặc ngược lại.
"""

import frappe
from frappe import _
from frappe.utils import escape_html

from erpnext.vi_tri_kho.vitri.kho import kho_co_quan_ly_vi_tri

#: Nhãn nút trên phiếu nhập. Là hằng số chứ không phải chuỗi rải rác, vì câu báo
#: chặn duyệt phải nêu ĐÚNG tên nút người dùng nhìn thấy — lệch một chữ là thủ
#: kho đi tìm một nút không tồn tại.
NHAN_NUT_NHAP_LO = "Nhập lô & in nhãn"


def _lo_qua_phieu_nhap_lo(ten_dong: list[str]) -> dict[str, str]:
	"""`{tên dòng phiếu nhập: số lô}` cho các dòng đã khai lô qua một phiếu nhập
	lô ĐÃ DUYỆT.

	Phải là phiếu đã duyệt: `batch_no` chỉ được ghi lên dòng phiếu nhập ở
	`BatchEntry.on_submit`. Một phiếu nhập lô còn nháp chưa ghi gì cả, nên nó
	không chứng minh được dòng nào.

	Khớp theo CẶP (dòng, số lô), không chỉ theo dòng: nếu ai đó khai lô đúng
	đường rồi sửa tay số lô trên dòng phiếu nhập, dòng vẫn có phiếu nhập lô trỏ
	vào nhưng số lô đang nằm trên dòng thì không phải số lô đã khai.
	"""
	if not ten_dong:
		return {}
	return {
		r.dong_phieu_nhap: r.lo_da_tao
		for r in frappe.db.sql(
			"""
			select bei.dong_phieu_nhap, bei.lo_da_tao
			from `tabBatch Entry Item` bei
			join `tabBatch Entry` be on be.name = bei.parent
			where be.docstatus = 1 and bei.dong_phieu_nhap in %(dong)s
			""",
			{"dong": tuple(ten_dong)},
			as_dict=True,
		)
	}


def _dong_hang_co_lo(phieu_nhap: str) -> list[dict]:
	return frappe.db.sql(
		"""
		select pri.name, pri.idx, pri.item_code, pri.warehouse,
		       ifnull(pri.batch_no, '') as batch_no, it.has_batch_no
		from `tabPurchase Receipt Item` pri
		join `tabItem` it on it.name = pri.item_code
		where pri.parent = %(p)s
		order by pri.idx
		""",
		{"p": phieu_nhap},
		as_dict=True,
	)


@frappe.whitelist()
def chan_doan_phieu_nhap(phieu_nhap: str) -> dict:
	"""Trạng thái khai lô của một phiếu nhập, kèm câu giải thích cho thủ kho.

	Dùng cho hai chỗ: nút trên phiếu nhập (mở phiếu nhập lô nháp đang có, hay tạo
	mới, hay giải thích vì sao không có gì để khai), và câu báo "không có dòng
	nào" trên phiếu nhập lô.

	Câu báo cũ chỉ nói "không còn dòng hàng quản lý lô nào chưa có số lô" — đúng
	về kỹ thuật, nhưng ba nguyên nhân sinh ra nó cần BA việc khác nhau (đã
	duyệt / lô gõ thẳng trên phiếu / mặt hàng chưa bật Có lô), và thủ kho không
	có cách nào biết mình rơi vào ca nào.
	"""
	frappe.has_permission("Purchase Receipt", "read", phieu_nhap, throw=True)
	docstatus = frappe.db.get_value("Purchase Receipt", phieu_nhap, "docstatus")

	dong = _dong_hang_co_lo(phieu_nhap)
	co_lo = [d for d in dong if d.has_batch_no]
	da_qua_phieu = _lo_qua_phieu_nhap_lo([d.name for d in co_lo if d.batch_no])

	dong_go_tay = [
		{"idx": d.idx, "item_code": d.item_code, "batch_no": d.batch_no}
		for d in co_lo
		if d.batch_no and da_qua_phieu.get(d.name) != d.batch_no
	]
	ket_qua = {
		"docstatus": docstatus,
		"dong_can_khai": sum(1 for d in co_lo if not d.batch_no),
		"dong_go_tay": dong_go_tay,
		"dong_khong_lo": len(dong) - len(co_lo),
		"phieu_nhap_lo_nhap": frappe.db.get_value(
			"Batch Entry", {"phieu_nhap": phieu_nhap, "docstatus": 0}, "name"
		),
		"phieu_nhap_lo": frappe.get_all(
			"Batch Entry", {"phieu_nhap": phieu_nhap, "docstatus": 1}, pluck="name"
		),
	}
	ket_qua["cau_bao"] = _cau_bao(phieu_nhap, ket_qua)
	return ket_qua


def _liet_ke_go_tay(dong_go_tay: list[dict]) -> str:
	# `escape_html`: câu này hiện qua `frappe.msgprint`, vốn render HTML. Số lô là
	# chữ NGƯỜI DÙNG GÕ và không bị chặn ký tự `<`/`>` (chúng là ASCII, mã hoá được
	# trên mã vạch) — nhúng nguyên văn là một lỗ XSS lưu trữ nằm ngay trên màn hình
	# của thủ kho khác mở cùng phiếu.
	return ", ".join(
		_("dòng {0} ({1}: '{2}')").format(d["idx"], escape_html(d["item_code"]), escape_html(d["batch_no"]))
		for d in dong_go_tay
	)


def _cau_bao(phieu_nhap: str, cd: dict) -> str:
	"""Câu giải thích khi KHÔNG còn dòng nào để khai lô. Rỗng khi còn dòng.

	Thứ tự nguyên nhân là thứ tự thủ kho cần biết: phiếu đã duyệt thì mọi việc
	khác vô nghĩa; lô gõ tay là việc phải sửa trước khi duyệt; mặt hàng chưa bật
	Có lô là việc thiết lập, làm một lần.
	"""
	if cd["dong_can_khai"]:
		return ""

	if cd["docstatus"] == 1:
		cau = _("Phiếu nhập {0} đã duyệt nên không khai lô được nữa.").format(phieu_nhap)
		if cd["dong_go_tay"]:
			cau += " " + _(
				"Số lô trên phiếu này được gõ thẳng trên phiếu nhập, không qua phiếu nhập lô: {0}. "
				"Vì vậy lô đó không có tem, và số lô có thể không phải số lô của nhà cung cấp."
			).format(_liet_ke_go_tay(cd["dong_go_tay"]))
		return cau

	if cd["docstatus"] == 2:
		return _("Phiếu nhập {0} đã huỷ.").format(phieu_nhap)

	if cd["dong_go_tay"]:
		return _(
			"Các dòng sau đã có số lô gõ thẳng trên phiếu nhập, không qua phiếu nhập lô: {0}. "
			"Xoá số lô trên các dòng đó rồi bấm '{1}' — kho đã bật quản lý vị trí sẽ không cho "
			"duyệt phiếu nhập với số lô gõ tay."
		).format(_liet_ke_go_tay(cd["dong_go_tay"]), NHAN_NUT_NHAP_LO)

	if cd["dong_khong_lo"] and not cd["phieu_nhap_lo"]:
		return _(
			"Không mặt hàng nào trên phiếu nhập {0} bật 'Có lô'. Muốn khai lô cho mặt hàng nào "
			"thì mở form mặt hàng đó, bật 'Có lô' rồi lưu trước."
		).format(phieu_nhap)

	if cd["phieu_nhap_lo"]:
		return _("Mọi dòng có lô của phiếu nhập {0} đã khai lô qua phiếu nhập lô: {1}.").format(
			phieu_nhap, ", ".join(cd["phieu_nhap_lo"])
		)

	return _("Phiếu nhập {0} không có dòng hàng nào.").format(phieu_nhap)


def chan_lo_go_tay_khi_duyet(doc, method=None):
	"""`doc_events["Purchase Receipt"]["before_submit"]`.

	Kho đã bật quản lý vị trí: mỗi dòng hàng quản lý lô phải có số lô ĐẾN TỪ một
	phiếu nhập lô đã duyệt. Không có số lô, hay số lô gõ tay → không duyệt.

	Ba phạm vi cố ý đứng ngoài phép chặn:
	- **Kho chưa bật quản lý vị trí**: không có tem, không có ô — chặn ở đó là
	  chặn luồng nhập kho thường của cả công ty mà không được gì.
	- **Phiếu trả hàng** (`is_return`): trả lại một lô ĐÃ CÓ, không khai lô mới,
	  nên không có phiếu nhập lô nào cho nó. Chặn là không trả hàng được.
	- **Hàng bị loại** (`rejected_qty`): đi qua bundle riêng của ERPNext, không
	  vào kho có vị trí.
	"""
	if doc.get("is_return"):
		return

	dong_kiem = [
		d
		for d in doc.items
		if kho_co_quan_ly_vi_tri(d.warehouse)
		and frappe.get_cached_value("Item", d.item_code, "has_batch_no")
	]
	if not dong_kiem:
		return

	da_qua_phieu = _lo_qua_phieu_nhap_lo([d.name for d in dong_kiem])
	sai = [d for d in dong_kiem if not d.batch_no or da_qua_phieu.get(d.name) != d.batch_no]
	if not sai:
		return

	chi_tiet = "<br>".join(
		# `escape_html`: `frappe.throw` hiện qua hộp thoại render HTML, còn số lô là
		# chữ người dùng gõ — xem `_liet_ke_go_tay`.
		_("Dòng {0} — {1}: chưa có số lô").format(d.idx, escape_html(d.item_code))
		if not d.batch_no
		else _("Dòng {0} — {1}: số lô '{2}' được gõ tay, không qua phiếu nhập lô").format(
			d.idx, escape_html(d.item_code), escape_html(d.batch_no)
		)
		for d in sai
	)
	frappe.throw(
		_(
			"Kho đã bật quản lý vị trí: số lô phải được khai qua phiếu nhập lô để có tem và "
			"giữ đúng số lô của nhà cung cấp.<br><br>{0}<br><br>"
			"Xoá số lô gõ tay (nếu có), lưu phiếu, rồi bấm nút <b>{1}</b> ở đầu phiếu nhập."
		).format(chi_tiet, NHAN_NUT_NHAP_LO),
		title=_("Chưa khai lô qua phiếu nhập lô"),
	)

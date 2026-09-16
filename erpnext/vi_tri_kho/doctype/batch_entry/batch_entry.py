"""Phiếu nhập lô — khai số lô và HSD cho từng dòng phiếu nhập (spec khối C §5).

VÌ SAO LÀ PHIẾU RIÊNG chứ không phải sửa hộp thoại lô sẵn có của ERPNext: chủ
đầu tư chốt 16/09/2026. Cái giá đã biết và đã chấp nhận — hộp thoại cũ vẫn mở
được và vẫn tạo được lô không tem; §4.3 vá phần dữ liệu, phần số lô máy sinh thì
là lựa chọn nghiệp vụ.

VÌ SAO GHI `batch_no` LÊN DÒNG PHIẾU NHẬP thay vì tự dựng `Serial and Batch
Bundle`: một trường, không có gì khác. Tự dựng bundle là bám vào nội bộ một hệ
thống đã đổi kiến trúc lô một lần giữa v14 và v15 — và sẽ đổi nữa.

ĐÃ ĐO TRÊN erptest.local (16/09/2026), không phải suy từ mã:

    A. sau frappe.db.set_value  batch_no = 'PROBE-LO-001'
    B. sau reload + save (nháp) batch_no = 'PROBE-LO-001'   <- KHÔNG bị xoá
    C. sau submit phiếu nhập    batch_no = 'PROBE-LO-001'
       số Batch của mặt hàng    1 -> 1                      <- KHÔNG sinh lô máy
       bundle                   docstatus 1, dòng con {batch_no: PROBE-LO-001, qty: 10}
    E. scan_barcode('PROBE-LO-001') -> {batch_no, item_code, has_batch_no}

Điểm B là điểm phải đo: `frappe.db.set_value` đi thẳng xuống CSDL, không qua bản
sao trong bộ nhớ. Nếu ai đó mở phiếu nháp ra lưu lại giữa lúc ta ghi và lúc
submit, một bản sao cũ có thể ghi đè `batch_no` về rỗng — và lô của NCC mất mà
không có lỗi nào báo. Đo cho thấy KHÔNG xảy ra. Nếu một bản ERPNext sau này đổi
điều đó, `test_phieu_nhap_submit_sau_do_khong_sinh_lo_may_nao_nua` sẽ đỏ.

Đáng ghi lại: sau submit `use_serial_batch_fields` vẫn bằng 0, tức bundle được
dựng bằng một nhánh KHÁC nhánh `stock_controller.py:231-234`. Không cần biết
nhánh nào — đừng viết mã dựa trên nó. Thứ ràng buộc là KẾT QUẢ đo được ở trên,
và bài test khoá đúng kết quả đó.
"""

import frappe
from frappe import _
from frappe.model.document import Document

from erpnext.vi_tri_kho.vitri.ma_vach import kiem_tra_do_dai


class BatchEntry(Document):
	def validate(self):
		# Thứ tự này là một phần của spec (§5.5), không phải chi tiết cài đặt:
		# câu báo lỗi ĐẦU TIÊN người dùng thấy phải chỉ đúng chỗ sai. Kiểm trùng
		# số lô trước khi kiểm độ dài thì người gõ một số lô quá dài được bảo là
		# "trùng" và đi sửa sai chỗ.
		self.kiem_tra_phieu_nhap_con_nhap()
		self.kiem_tra_dong_thuoc_phieu()
		self.kiem_tra_so_lo()
		self.kiem_tra_ngay()

	def kiem_tra_phieu_nhap_con_nhap(self):
		trang_thai = frappe.db.get_value("Purchase Receipt", self.phieu_nhap, "docstatus")
		if trang_thai != 0:
			frappe.throw(
				_(
					"Phiếu nhập {0} đã duyệt nên không gắn được số lô nữa. Phải nhập lô "
					"TRƯỚC rồi mới duyệt phiếu nhập — duyệt trước thì ERPNext đã tự sinh "
					"số lô máy và số lô của nhà cung cấp mất luôn."
				).format(self.phieu_nhap)
			)

	def kiem_tra_dong_thuoc_phieu(self):
		"""Mỗi dòng phiếu nhập xuất hiện đúng một lần, và phải là dòng của ĐÚNG
		phiếu đang chọn.

		Vế thứ hai không thừa: không có nó thì một `dong_phieu_nhap` chép nhầm từ
		phiếu khác sẽ khiến `on_submit` ghi `batch_no` lên một chứng từ không
		liên quan — sửa dữ liệu của người khác, im lặng.
		"""
		hop_le = set(
			frappe.get_all(
				"Purchase Receipt Item",
				filters={"parent": self.phieu_nhap},
				pluck="name",
			)
		)
		da_thay = set()
		for d in self.items:
			if d.dong_phieu_nhap not in hop_le:
				frappe.throw(
					_("Dòng {0}: dòng hàng không thuộc phiếu nhập {1}.").format(
						d.idx, self.phieu_nhap
					)
				)
			if d.dong_phieu_nhap in da_thay:
				frappe.throw(
					_(
						"Dòng {0}: mỗi dòng phiếu nhập chỉ nhận MỘT số lô. Hàng về hai lô "
						"thì tách dòng trên phiếu nhập — tách rồi số lượng theo từng lô "
						"cũng đúng luôn trên chứng từ."
					).format(d.idx)
				)
			da_thay.add(d.dong_phieu_nhap)

	def kiem_tra_so_lo(self):
		for d in self.items:
			d.so_lo = (d.so_lo or "").strip()
			if not d.so_lo:
				frappe.throw(_("Dòng {0}: chưa có số lô.").format(d.idx))

			kiem_tra_do_dai(d.so_lo, _("lô"))

			chu_lo = frappe.db.get_value("Batch", d.so_lo, "item")
			if chu_lo and chu_lo != d.vat_tu:
				frappe.throw(
					_(
						"Dòng {0}: số lô '{1}' đã thuộc mặt hàng {2}. Số lô là tên bản ghi "
						"trong ERPNext nên duy nhất toàn hệ, hai mặt hàng không dùng chung "
						"được."
					).format(d.idx, d.so_lo, chu_lo)
				)

	def kiem_tra_ngay(self):
		for d in self.items:
			if d.ngay_san_xuat and d.hsd and d.hsd < d.ngay_san_xuat:
				frappe.throw(
					_("Dòng {0}: hạn dùng {1} trước ngày sản xuất {2}.").format(
						d.idx, d.hsd, d.ngay_san_xuat
					)
				)

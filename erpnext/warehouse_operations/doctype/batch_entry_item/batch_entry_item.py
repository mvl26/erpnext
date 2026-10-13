"""Một dòng hàng của phiếu nhập lô.

`dong_phieu_nhap` (tên bản ghi `Purchase Receipt Item`) là KHOÁ LIÊN KẾT thật,
không phải `vat_tu`: một phiếu nhập có thể có hai dòng cùng một mặt hàng, về
hai kho hoặc hai đơn giá khác nhau, và mỗi dòng cần số lô riêng.
"""

from frappe.model.document import Document


class BatchEntryItem(Document):
	pass

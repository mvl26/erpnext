"""Dòng của Phiếu xếp / chuyển vị trí.

Không có logic riêng: mọi phép kiểm nằm ở controller cha
(`location_transfer.py`) vì chúng cần biết `kho` của đầu phiếu để so —
K2 ("ô phải thuộc đúng kho của phiếu") không phát biểu được ở tầng dòng.
Lớp này tồn tại vì Frappe nạp module controller cho MỌI doctype, kể cả
`istable`.
"""

from frappe.model.document import Document


class LocationTransferItem(Document):
	pass

# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Cây thư mục lưu file hóa đơn điện tử trong File Manager của ERP.

``Home/Invoices/{năm}/{tháng}/{ngày}/{số hóa đơn}`` — bản nháp PDF, PDF chính
thức (kể cả bản đính trên phiếu giao), PDF chuyển đổi và XML của một hóa đơn
nằm chung một thư mục.

Thư mục **không dựng trước**: chỉ khi có file sắp lưu mới kiểm tra từng cấp, cấp
nào chưa có thì tạo. Cây vì thế không có nhánh rỗng cho những ngày không phát
hành gì.

Ngày là ngày phát hành (ngày ký). Bản nháp chưa có số thì tạm nằm ở thư mục mang
tên chứng từ HĐĐT; hóa đơn có số rồi thì `move_invoice_files` dời tất cả sang thư
mục số hóa đơn và dọn thư mục tạm đã rỗng.
"""

import frappe
from frappe.utils import getdate, nowdate

FEI = "Fast EInvoice Document"
HOME = "Home"
ROOT_NAME = "Invoices"
ROOT = f"{HOME}/{ROOT_NAME}"


def invoice_folder(doc) -> str:
	"""Đường dẫn thư mục của hóa đơn, tạo cấp nào còn thiếu. Chỉ gọi khi sắp lưu file."""
	day = getdate(doc.fast_signed_date or doc.invoice_date or nowdate())
	leaf = _folder_name(doc.fast_invoice_no or doc.name)

	path = HOME
	for part in (ROOT_NAME, f"{day.year:04d}", f"{day.month:02d}", f"{day.day:02d}", leaf):
		path = _ensure_folder(path, part)
	return path


def move_invoice_files(fei_name):
	"""Dời mọi file của chứng từ về thư mục số hóa đơn — gọi khi hóa đơn vừa có số.

	Bản nháp xem trước lúc phát hành đang ở thư mục tạm (tên chứng từ, ngày lập
	nháp); PDF tải từ trước khi có cây thư mục thì nằm ở ``Home/Attachments``. Dời
	hết về một chỗ, rồi xóa thư mục tạm đã rỗng cùng các cấp ngày/tháng/năm rỗng
	theo — không để lại nhánh chết trong cây.
	"""
	doc = frappe.db.get_value(
		FEI, fei_name, ["name", "fast_invoice_no", "fast_signed_date", "invoice_date"], as_dict=True
	)
	if not doc or not doc.fast_invoice_no:
		return

	files = frappe.get_all(
		"File",
		filters={"attached_to_doctype": FEI, "attached_to_name": fei_name, "is_folder": 0},
		fields=["name", "folder"],
	)
	if not files:
		return

	target = invoice_folder(doc)
	emptied = set()
	for row in files:
		if row.folder == target:
			continue
		frappe.db.set_value("File", row.name, "folder", target, update_modified=False)
		if (row.folder or "").startswith(f"{ROOT}/"):
			emptied.add(row.folder)

	for folder in emptied:
		_remove_if_empty(folder)


def place_attached_file(doc, file_url):
	"""Xếp một file người dùng tự đính vào chứng từ (XML hóa đơn) về thư mục hóa đơn."""
	name = frappe.db.get_value(
		"File",
		{"file_url": file_url, "attached_to_doctype": FEI, "attached_to_name": doc.name, "is_folder": 0},
		"name",
	) or frappe.db.get_value(
		"File", {"file_url": file_url, "attached_to_name": ("is", "not set"), "is_folder": 0}, "name"
	)
	if not name:
		return

	target = invoice_folder(doc)
	if frappe.db.get_value("File", name, "folder") != target:
		frappe.db.set_value("File", name, "folder", target, update_modified=False)


def _ensure_folder(parent, name):
	"""Có rồi thì thôi, chưa có thì tạo. Tên bản ghi thư mục của Frappe chính là đường dẫn."""
	path = f"{parent}/{name}"
	if not frappe.db.exists("File", {"name": path, "is_folder": 1}):
		folder = frappe.get_doc({"doctype": "File", "file_name": name, "folder": parent, "is_folder": 1})
		folder.flags.ignore_permissions = True
		folder.insert(ignore_if_duplicate=True)
	return path


def _remove_if_empty(folder):
	"""Xóa thư mục rỗng và đi ngược lên các cấp cha rỗng theo — dừng trước ``Home/Invoices``."""
	while folder.startswith(f"{ROOT}/"):
		if frappe.db.exists("File", {"folder": folder}):
			return
		if frappe.db.exists("File", {"name": folder, "is_folder": 1}):
			frappe.delete_doc("File", folder, ignore_permissions=True)
		folder = folder.rsplit("/", 1)[0]


def _folder_name(value):
	"""Dấu ``/`` trong tên là tách cấp thư mục — thay đi để một hóa đơn đúng một thư mục."""
	return str(value).strip().replace("/", "-")

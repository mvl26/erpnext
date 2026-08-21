# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Xếp file hồ sơ TBYT vào cây thư mục và đặt tên có nghĩa.

Nguyên tắc: **thư mục theo nơi cấp giấy, phân giải theo nơi giấy phủ.** Một file
chỉ nằm được một thư mục, nên chứng từ đa phạm vi về thư mục chủ sở hữu. Thư mục
chỉ để người duyệt tay lần ra; resolver không bao giờ đọc thư mục.
"""

import os
import unicodedata

import frappe
from frappe.core.api.file import create_new_folder
from frappe.utils import cint, getdate

from erpnext.tbyt.constants import (
	ARCHIVE_FOLDER_NAME,
	ROOT_FOLDER,
	SCOPE_AUTHORIZATION,
	SCOPE_FOLDER_NAME,
	SCOPE_OWNER,
)


def slugify(text: str) -> str:
	"""Bỏ dấu tiếng Việt và thay ký tự phá đường dẫn bằng gạch nối."""
	if not text:
		return ""
	text = text.replace("Đ", "D").replace("đ", "d")
	text = unicodedata.normalize("NFKD", text)
	text = "".join(ch for ch in text if not unicodedata.combining(ch))
	out = []
	for ch in text:
		out.append(ch if (ch.isalnum() or ch in "-_.") else "-")
	return "-".join(part for part in "".join(out).split("-") if part)


def build_file_name(short_code: str, so_hieu: str | None, ngay_cap, extension: str) -> str:
	"""`{mã ngắn}__{số hiệu}__{ngày cấp}.{đuôi}` — nhìn tên là biết giấy gì."""
	number = slugify(so_hieu) if so_hieu else "khong-so"
	issued = getdate(ngay_cap).isoformat() if ngay_cap else "khong-ngay"
	return f"{short_code}__{number}__{issued}.{extension}"


def ensure_folder(scope_level: str, scope_value: str) -> str:
	"""Trả đường dẫn thư mục của một đối tượng, tạo nếu chưa có.

	`create_new_folder` của Frappe đã tự idempotent bằng
	`insert(ignore_if_duplicate=True)` nên gọi lại không lỗi.
	"""
	branch = SCOPE_FOLDER_NAME[scope_level]
	create_new_folder("TBYT", "Home")
	create_new_folder(branch, ROOT_FOLDER)
	leaf = slugify(scope_value)
	create_new_folder(leaf, f"{ROOT_FOLDER}/{branch}")
	return f"{ROOT_FOLDER}/{branch}/{leaf}"


def target_folder(doc) -> str:
	"""Thư mục đích của một bản ghi chứng từ.

	Đa phạm vi thì về thư mục chủ sở hữu — cả bốn loại đa phạm vi đều do chủ sở
	hữu cấp, và validate đã bảo đảm chúng không trải quá một hãng.
	"""
	if len(doc.pham_vi) > 1 and doc.pham_vi[0].scope_doctype == "TBYT Marketing Authorization":
		owner = frappe.db.get_value("TBYT Marketing Authorization", doc.pham_vi[0].scope_name, "chu_so_huu")
		return ensure_folder(SCOPE_OWNER, owner)

	row = doc.pham_vi[0]
	scope_level = frappe.db.get_value("TBYT Document Type", doc.document_type, "scope_level")
	label = row.scope_name
	if scope_level == SCOPE_AUTHORIZATION:
		# Ưu tiên số thật cho dễ đọc; chưa có số thì dùng tên bản ghi.
		label = (
			frappe.db.get_value("TBYT Marketing Authorization", row.scope_name, "so_luu_hanh")
			or row.scope_name
		)
	return ensure_folder(scope_level, label)


def place_file(doc) -> None:
	"""Dời file vào đúng thư mục và đổi tên theo quy ước."""
	file_doc = _file_of(doc)
	if not file_doc:
		return

	folder = target_folder(doc)
	if cint(doc.is_active) == 0:
		folder = _archive_of(folder)

	extension = (os.path.splitext(file_doc.file_name)[1] or ".pdf").lstrip(".")
	wanted = build_file_name(doc.short_code, doc.so_hieu, doc.ngay_cap, extension)

	changed = False
	if file_doc.folder != folder:
		file_doc.folder = folder
		changed = True
	if file_doc.file_name != wanted:
		file_doc.file_name = wanted
		changed = True
	if not cint(file_doc.is_private):
		file_doc.is_private = 1
		changed = True
	wanted_attachment = (doc.doctype, doc.name, "file")
	if (
		file_doc.attached_to_doctype,
		file_doc.attached_to_name,
		file_doc.attached_to_field,
	) != wanted_attachment:
		# Chốt luôn chủ sở hữu (doctype + name + field) của file: hook `after_
		# insert` bên app `assetcore` (assetcore/utils/attachments.py, link_
		# uploaded_files) có thể đã nhận trước doctype/name cho file mồ côi này
		# qua frappe.db.set_value nhưng bỏ trống attached_to_field. Trạng thái
		# nửa vời đó khiến hook lõi Frappe cho on_update, attach_files_to_document,
		# không khớp được cả điều kiện "đã gắn đủ" lẫn "chưa gắn" — nó bèn tạo
		# thêm một File thứ hai trỏ cùng file_url. Ghi đủ cả ba trường ở đây để
		# chốt lại, dù file đang chưa gắn (None cả ba) hay mới gắn nửa chừng.
		file_doc.attached_to_doctype = doc.doctype
		file_doc.attached_to_name = doc.name
		file_doc.attached_to_field = "file"
		changed = True

	if changed:
		file_doc.flags.ignore_permissions = True
		file_doc.save()


def archive_file(doc) -> None:
	"""Dời file của bản ghi đã bị thay thế vào `_Luu-tru/`."""
	place_file(doc)


def _archive_of(folder: str) -> str:
	create_new_folder(ARCHIVE_FOLDER_NAME, folder)
	return f"{folder}/{ARCHIVE_FOLDER_NAME}"


def _file_of(doc):
	if not doc.file:
		return None
	name = frappe.db.get_value("File", {"file_url": doc.file}, "name")
	return frappe.get_doc("File", name) if name else None

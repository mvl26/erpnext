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

	_sync_file_url(doc, file_doc)


def _sync_file_url(doc, file_doc) -> None:
	"""Ép `is_private` làm ĐỔI `file_url`, nên phải ghi ngược lại vào bản ghi.

	`File.handle_is_private_changed` (frappe/core/doctype/file/file.py) dời tệp
	sang `/private/files/` rồi gán `file_url` mới cho chính bản ghi File — nhưng
	không ai cập nhật trường `file` của bản ghi chứng từ, nó vẫn giữ `/files/...`.
	Hậu quả dây chuyền, cả ba đều đã kiểm chứng trong mã nguồn Frappe:

	1. Link tải về trên bản ghi trỏ vào đường dẫn không còn tồn tại.
	2. Hook lõi `attach_files_to_document` (frappe/core/doctype/file/utils.py)
	   chạy ở `on_update` SAU hook này, không thấy File nào ở URL cũ, nên CHÈN
	   THÊM một File ma trỏ vào đường dẫn đã chết.
	3. Từ lần lưu sau, `_file_of` vớ đúng cái File ma đó, nên đặt tên lẫn xếp
	   thư mục vĩnh viễn không còn tác dụng với bản ghi này.

	Dùng `db_set` chứ không `doc.save()`: đang đứng trong `on_update`, lưu lại
	là đệ quy. `db_set` cũng cập nhật giá trị trong bộ nhớ, nhờ đó hook lõi chạy
	ngay sau đọc được URL mới và không đẻ thêm File.
	"""
	if file_doc.file_url and file_doc.file_url != doc.file:
		doc.db_set("file", file_doc.file_url, update_modified=False)


def archive_file(doc) -> None:
	"""Dời file của bản ghi đã bị thay thế vào `_Luu-tru/`."""
	place_file(doc)


def _archive_of(folder: str) -> str:
	create_new_folder(ARCHIVE_FOLDER_NAME, folder)
	return f"{folder}/{ARCHIVE_FOLDER_NAME}"


def _file_of(doc):
	"""File của CHÍNH bản ghi này — `doc.file` là lời sau cùng, vì người dùng vừa đặt nó.

	Thứ tự tra cứu, đúng ba nhánh:

	1. File có `file_url == doc.file` VÀ đã gắn đủ vào (doctype, name, "file") của
	   bản ghi này — trạng thái ổn định, không có gì thay đổi.
	2. File có `file_url == doc.file` VÀ chưa thuộc về bản ghi nào khác: hoặc mồ côi
	   (`attached_to_name` trống), hoặc gắn NỬA VỜI vào chính bản ghi này (đúng
	   doctype + name nhưng bỏ trống `attached_to_field` — dấu vết hook `after_insert`
	   của app `assetcore`, xem `assetcore/utils/attachments.py`). Đây là tệp vừa
	   được tải lên; lọc cứng theo cả ba trường sẽ trượt nó và bỏ tệp lại giữa
	   `Home/Attachments`.
	3. Không có hàng nào khớp `doc.file` thì mới nhận bất kỳ File nào đang gắn vào
	   (doctype, name, "file") của bản ghi này, kệ URL. Nhánh này để CHỮA bản ghi cũ
	   có `file` lệch URL từ hồi ép `is_private` — `_sync_file_url` sẽ ghi URL thật
	   ngược lại vào trường `file`.

	Vì sao `doc.file` phải đứng trước: người dùng thay tệp A bằng tệp B rồi lưu thì
	`place_file` chạy TRƯỚC hook lõi `attach_files_to_document`, lúc ấy B còn mồ côi
	trong khi A vẫn khớp đủ ba trường. Ưu tiên hàng đã gắn sẽ vớ đúng A, rồi
	`_sync_file_url` ghi đè URL của A lên `doc.file` — lặng lẽ nuốt mất chỉnh sửa
	người dùng vừa làm, còn B mắc kẹt ở `Home/Attachments`.

	Ràng buộc bất di bất dịch ở mọi nhánh: KHÔNG BAO GIỜ cướp File của bản ghi khác.
	Frappe gộp theo `content_hash`, nên hai bản ghi File khác nhau có thể dùng chung
	một `file_url` (cùng một bản scan đính vào hai tờ giấy là chuyện thường). Hàng
	nào có `attached_to_name` trỏ sang bản ghi khác đều bị loại, kể cả khi
	`attached_to_field` của nó đang trống. `order_by` để hai lần gọi không ra hai
	kết quả khác nhau.
	"""
	if not doc.file:
		return None

	attached = half = orphan = None
	for row in frappe.get_all(
		"File",
		filters={"file_url": doc.file},
		fields=["name", "attached_to_doctype", "attached_to_name", "attached_to_field"],
		order_by="creation asc",
	):
		mine = (row.attached_to_doctype, row.attached_to_name) == (doc.doctype, doc.name)
		if mine and row.attached_to_field == "file":
			attached = attached or row
		elif mine and not row.attached_to_field:
			half = half or row
		elif not row.attached_to_name:
			orphan = orphan or row

	row = attached or half or orphan
	if row:
		return frappe.get_doc("File", row.name)

	name = frappe.db.get_value(
		"File",
		{
			"attached_to_doctype": doc.doctype,
			"attached_to_name": doc.name,
			"attached_to_field": "file",
		},
		"name",
		order_by="creation asc",
	)
	return frappe.get_doc("File", name) if name else None

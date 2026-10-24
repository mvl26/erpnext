"""Gắn tệp riêng tư (đính kèm trong bài đăng / bình luận) vào chứng từ để người đọc bài mở được.

Tệp đính kèm được tải lên ở chế độ riêng tư (/private/files/...). Frappe chỉ cho mở tệp riêng tư
khi người xem có quyền đọc chứng từ mà tệp gắn vào, nên sau khi lưu bài/bình luận ta gắn
File.attached_to_doctype/attached_to_name theo các đường dẫn xuất hiện trong nội dung.
"""

import html
import re
from urllib.parse import unquote

import frappe

PRIVATE_URL = re.compile(r"""(?:href|src)=["'](/private/files/[^"'?#]+)["']""")


def link_files(doc, method=None):
	content = doc.get("content") or ""
	urls = {html.unescape(u) for u in PRIVATE_URL.findall(content)}
	if not urls:
		return
	for url in urls:
		files = frappe.get_all(
			"File",
			filters={"file_url": ("in", list({url, unquote(url)})), "is_private": 1},
			fields=["name", "owner", "attached_to_doctype", "attached_to_name"],
		)
		for f in files:
			if f.attached_to_doctype and f.attached_to_name:
				continue
			# Chỉ gắn tệp do chính người viết bài/bình luận tải lên
			if f.owner != doc.owner:
				continue
			frappe.db.set_value(
				"File",
				f.name,
				{"attached_to_doctype": doc.doctype, "attached_to_name": doc.name},
				update_modified=False,
			)


DATA_URI = re.compile(r"""src=(["'])data:(image/[a-zA-Z0-9.+-]+);base64,([A-Za-z0-9+/=\s]+)\1""")
MAX_SIDE = 1920


def _shrink(data, mimetype):
	"""Thu nhỏ ảnh chụp điện thoại (cạnh dài tối đa 1920px) để bài đăng tải nhanh."""
	try:
		from io import BytesIO

		from PIL import Image, ImageOps

		img = Image.open(BytesIO(data))
		if getattr(img, "is_animated", False):
			return data, mimetype
		img = ImageOps.exif_transpose(img)
		if max(img.size) <= MAX_SIDE and len(data) <= 1_500_000:
			return data, mimetype
		img.thumbnail((MAX_SIDE, MAX_SIDE))
		out = BytesIO()
		if img.mode in ("RGBA", "LA", "P") and mimetype == "image/png":
			img.save(out, format="PNG", optimize=True)
			return out.getvalue(), "image/png"
		img.convert("RGB").save(out, format="JPEG", quality=85, optimize=True)
		return out.getvalue(), "image/jpeg"
	except Exception:
		return data, mimetype


def extract_inline_images(doc, method=None):
	"""Hook validate của GP Discussion / GP Comment: tách ảnh base64 trong nội dung thành File riêng tư."""
	import base64

	content = doc.get("content") or ""
	if "data:image/" not in content:
		return
	if not doc.name:
		doc.set_new_name()

	def repl(m):
		quote, mimetype, b64 = m.group(1), m.group(2), m.group(3)
		try:
			data = base64.b64decode(re.sub(r"\s+", "", b64))
		except Exception:
			return m.group(0)
		data, mimetype = _shrink(data, mimetype)
		ext = {"image/jpeg": "jpg", "image/png": "png", "image/gif": "gif", "image/webp": "webp"}.get(
			mimetype, "png"
		)
		f = frappe.get_doc(
			doctype="File",
			file_name=f"anh-{frappe.generate_hash(length=10)}.{ext}",
			content=data,
			is_private=1,
			attached_to_doctype=doc.doctype,
			attached_to_name=str(doc.name),
		)
		f.flags.ignore_permissions = True
		f.insert()
		return f"src={quote}{f.file_url}{quote}"

	doc.content = DATA_URI.sub(repl, content)

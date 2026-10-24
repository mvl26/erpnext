"""Tìm kiếm dự phòng bằng SQL khi Redis chưa có module RediSearch.

MariaDB dùng collation utf8mb4_unicode_ci nên LIKE không phân biệt hoa/thường và dấu tiếng Việt
("thong bao" khớp "Thông báo").
"""

import re
import time
import unicodedata

import frappe
from frappe.core.utils import html2text
from frappe.utils import cstr, escape_html

PAGE_LENGTH = 50


def _fold(ch):
	if ch in "đĐ":
		return "d"
	base = unicodedata.normalize("NFD", ch)[0]
	return base.lower()


def _fold_text(text):
	return "".join(_fold(c) for c in text)


def highlight(text, terms, width=None):
	"""Bôi <mark> các từ khóa (không phân biệt dấu), trả về HTML an toàn."""
	text = re.sub(r"\s+", " ", cstr(text)).strip()
	folded = _fold_text(text)
	spans = []
	for t in terms:
		ft = _fold_text(t)
		if not ft:
			continue
		start = 0
		while True:
			i = folded.find(ft, start)
			if i < 0:
				break
			spans.append((i, i + len(ft)))
			start = i + len(ft)
	if width and len(text) > width:
		first = min([s for s, _ in spans], default=0)
		begin = max(0, first - width // 3)
		end = min(len(text), begin + width)
		spans = [(s - begin, e - begin) for s, e in spans if s >= begin and e <= end]
		text = text[begin:end]
		prefix, suffix = ("…" if begin > 0 else ""), ("…" if end < len(folded) else "")
	else:
		prefix = suffix = ""
	spans.sort()
	out, pos = [], 0
	for s, e in spans:
		if s < pos:
			continue
		out.append(escape_html(text[pos:s]))
		out.append("<mark>" + escape_html(text[s:e]) + "</mark>")
		pos = e
	out.append(escape_html(text[pos:]))
	return prefix + "".join(out) + suffix


def _like_conditions(field, terms):
	return " and ".join(f"{field} like {frappe.db.escape('%' + t + '%')}" for t in terms)


def sql_search(query, start=0, accessible_projects=None):
	t0 = time.time()
	terms = [t for t in re.split(r"\s+", cstr(query).replace("*", " ").strip()) if t]
	if not terms:
		return {"results": {}, "total": 0, "duration": 0}
	projects = [cstr(p) for p in (accessible_projects or [])]
	if not projects:
		return {"results": {}, "total": 0, "duration": 0}
	project_cond = "project in ({})".format(", ".join(frappe.db.escape(p) for p in projects))
	start = int(start or 0)

	results = {}
	total = 0

	def add(doctype, row, title_html, content_html, via_comment=False, modified=None):
		results.setdefault(doctype, []).append(
			frappe._dict(
				doctype=doctype,
				name=cstr(row.name),
				title=title_html,
				content=content_html,
				project=row.project,
				team=row.team,
				modified=modified or row.modified,
				via_comment=via_comment,
			)
		)

	# Bài đăng
	seen_discussions = set()
	for table, doctype, content_field in (
		("GP Discussion", "GP Discussion", "content"),
		("GP Task", "GP Task", "description"),
		("GP Page", "GP Page", "content"),
	):
		cond = "({}) or ({})".format(
			_like_conditions("title", terms), _like_conditions(f"`{content_field}`", terms)
		)
		rows = frappe.db.sql(
			f"""select name, title, `{content_field}` as content, project, team, modified
			from `tab{table}` where ({cond}) and {project_cond}
			order by modified desc limit {PAGE_LENGTH} offset {start}""",
			as_dict=True,
		)
		for r in rows:
			total += 1
			if doctype == "GP Discussion":
				seen_discussions.add(cstr(r.name))
			add(
				doctype,
				r,
				highlight(r.title, terms),
				highlight(html2text(r.content or ""), terms, width=240),
			)

	# Bình luận -> hiện bài đăng chứa bình luận
	rows = frappe.db.sql(
		f"""select c.name as comment, c.content, c.modified, d.name, d.title, d.project, d.team
		from `tabGP Comment` c
		join `tabGP Discussion` d on d.name = c.reference_name and c.reference_doctype = 'GP Discussion'
		where c.deleted_at is null and ({_like_conditions('c.content', terms)})
		and d.{project_cond}
		order by c.modified desc limit {PAGE_LENGTH}""",
		as_dict=True,
	)
	for r in rows:
		if cstr(r.name) in seen_discussions:
			continue
		seen_discussions.add(cstr(r.name))
		total += 1
		add(
			"GP Discussion",
			r,
			escape_html(r.title),
			highlight(html2text(r.content or ""), terms, width=240),
			via_comment=True,
		)

	return {"results": results, "total": total, "duration": (time.time() - t0) * 1000}


def redisearch_available():
	"""Redis cache có module RediSearch (FT.*) hay không."""
	try:
		modules = frappe.cache().execute_command("MODULE", "LIST") or []
	except Exception:
		return False
	for m in modules:
		items = m if isinstance(m, list | tuple) else []
		values = [cstr(x).lower() for x in items]
		if "search" in values or "ft" in values:
			return True
		if isinstance(m, dict) and cstr(m.get(b"name") or m.get("name")).lower() in ("search", "ft"):
			return True
	return False

"""Lop cong: tra loi dung mot bit — duong dan co hop le khong.

Bang luat suy tu 4.673 file dang tracked (2026-08-17). Sua RULES roi chay
`python3 -m scripts.file_structure --audit` de biet co vo gi khong.
"""

import re

# (ten_loai, regex). THU TU QUAN TRONG: mau hep dung truoc mau rong.
RULES: list[tuple[str, str]] = [
	# --- DocType: hai ngoai le framework dung TRUOC moi mau khac ---
	("doctype-test", r"erpnext/[^/]+/doctype/(?P<dt>[^/]+)/test_(?P=dt)\.py"),
	("doctype-records", r"erpnext/[^/]+/doctype/[^/]+/test_records\.json"),
	("doctype-data", r"erpnext/[^/]+/doctype/[^/]+/[^/]+/.+"),
	("doctype-pkg", r"erpnext/[^/]+/doctype/__init__\.py"),
	# Cho phep file phu tro, NHUNG chan moi thu bat dau bang test_ .
	# Day chinh la luat bat duoc loi da sua hom 2026-08-17.
	(
		"doctype",
		r"erpnext/[^/]+/doctype/(?P<dt>[^/]+)/"
		r"(__init__\.py|README\.md|help\.md|_[a-z0-9_]+\.(js|py)"
		r"|(?P=dt)[a-z0-9_]*\.(py|js|json|css|html)"
		r"|(?!test_)[a-z0-9_]+\.(py|html|csv))",
	),
	# --- Report: cung khuon voi DocType ---
	("report-test", r"erpnext/[^/]+/report/(?P<rp>[^/]+)/test_(?P=rp)\.py"),
	("report-pkg", r"erpnext/[^/]+/report/__init__\.py"),
	(
		"report",
		r"erpnext/[^/]+/report/(?P<rp>[^/]+)/"
		r"(__init__\.py|(?P=rp)[a-z0-9_]*\.(py|js|json|html|md)"
		r"|(?!test_)[a-z0-9_]+\.(py|xml|html|md))",
	),
	("report-shared", r"erpnext/[^/]+/report/(?!test_)[a-z0-9_]+\.(py|html)"),
	# --- Test cua module va sub-package (Accounts dung 'test/') ---
	("module-test", r"erpnext/[^/]+/tests?/(__init__\.py|test_[a-z0-9_]+\.py|[a-z0-9_]+\.(py|json))"),
	(
		"subpkg-test",
		r"erpnext/[^/]+/[^/]+/tests?/(__init__\.py|test_[a-z0-9_]+\.py|[a-z0-9_]+\.(py|json))",
	),
	# --- Patch ---
	("patch", r"erpnext/patches/(__init__\.py|v[0-9_]+/(__init__\.py|[a-zA-Z0-9_]+\.py))"),
	# --- Fixture do Frappe sinh ra (dashboard, workspace, print format...) ---
	(
		"fixture",
		r"erpnext/[^/]+/[a-z0-9_]*"
		r"(dashboard|workspace|onboarding|number_card|form_tour|notification"
		r"|print_format|web_form|role|workflow|custom|chart_source)[a-z0-9_]*/.+",
	),
	("page", r"erpnext/[^/]+/page/(__init__\.py|[^/]+/.+)"),
	("web-template", r"erpnext/[^/]+/web_template/[^/]+/.+"),
	# --- He thong con cua app ---
	(
		"app-subsystem",
		r"erpnext/(public|templates|www|translations|startup|config|domains|commands)/.+",
	),
	("app-pkg", r"erpnext/(tests|controllers|utilities|setup)/.+"),
	# --- Ma nguon cap module va sub-package ---
	("module-code", r"erpnext/[^/]+/(?!test_)([a-z0-9_]+|README)\.(py|json|txt|md)"),
	("subpkg-code", r"erpnext/[^/]+/[^/]+/(?!test_)([a-z0-9_-]+|README)\.(py|json|html|xml|md|csv)"),
	# Lookahead chan mau nay voi tay vao doctype/ va report/ — khong co no,
	# test_<gi_do>.py lac trong folder doctype se lai thanh hop le.
	("subpkg-data", r"erpnext/[^/]+/(?!doctype/|report/)[^/]+/[^/]+/.+"),
	(
		"app-root",
		r"erpnext/(__init__|hooks|exceptions)\.py|erpnext/(modules|patches)\.txt" r"|erpnext/\.stylelintrc",
	),
	# --- Ngoai erpnext/ ---
	("spec", r"docs/superpowers/specs/\d{4}-\d{2}-\d{2}-[a-z0-9-]+-design\.md"),
	("plan", r"docs/superpowers/plans/\d{4}-\d{2}-\d{2}-[a-z0-9-]+\.md"),
	("doc", r"docs/.+"),
	("script", r"scripts/.+"),
	("claude-config", r"\.claude/.+"),
	(
		"repo-root",
		r"(README|CLAUDE|NOTICE)\.md|package\.json|pyproject\.toml|yarn\.lock"
		r"|\.(gitignore|editorconfig|eslintrc|flake8|semgrepignore|pre-commit-config\.yaml"
		r"|git-blame-ignore-revs|stylelintrc)|logo-miyano\.png",
	),
]

_COMPILED: list[tuple[str, re.Pattern]] = []


def _compiled() -> list[tuple[str, re.Pattern]]:
	global _COMPILED
	if len(_COMPILED) != len(RULES):
		_COMPILED = [(kind, re.compile(rx + r"\Z")) for kind, rx in RULES]
	return _COMPILED


def classify(path: str) -> str | None:
	"""Tra ten loai cua duong dan, hoac None neu khong mau nao khop."""
	# removeprefix chu KHONG phai lstrip("./"): lstrip boc moi ky tu '.' va '/'
	# o dau, bien ".claude/settings.json" thanh "claude/settings.json".
	path = path.replace("\\", "/").removeprefix("./")
	for kind, rx in _compiled():
		if rx.match(path):
			return kind
	return None


def is_allowed(path: str) -> bool:
	return classify(path) is not None

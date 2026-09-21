"""Lop day: chi chay SAU KHI lop cong da ket luan 'sai'.

Lop nay chi sinh chu, khong quyet dinh chan. Doan sai loai file thi loi khuyen
chua trung, nhung khong chan nham ai — do la ly do kien truc tach hai lop.
"""

import re

# (dieu kien nhan biet, doan huong dan). Xet theo thu tu.
CARDS: list[tuple[str, str]] = [
	(
		r"erpnext/[^/]+/doctype/[^/]+/test_.+\.py",
		"File test nam lac trong folder doctype.\n"
		"  Chi MOT ten duoc phep o day: test_<ten_doctype>.py (trung ten folder).\n"
		"  Frappe resolve dung duong dan do (frappe/test_runner.py:209).\n"
		"  Test khac -> erpnext/<module>/tests/  (Accounts dung erpnext/accounts/test/)",
	),
	(
		r"erpnext/[^/]+/report/[^/]+/test_.+\.py",
		"File test nam lac trong folder report.\n"
		"  Chi test_<ten_report>.py (trung ten folder) duoc phep o day.\n"
		"  Test khac -> erpnext/<module>/tests/",
	),
	(
		r"erpnext/[^/]+/test_.+\.py",
		"File test khong duoc dat o goc module.\n"
		"  -> erpnext/<module>/tests/test_*.py  (Accounts dung erpnext/accounts/test/)\n"
		"  Folder tests/ phai co __init__.py.",
	),
	(
		r"erpnext/patches/.+",
		"Patch -> erpnext/patches/v15_0/<dong_tu>_<danh_tu>.py\n"
		"  Nho them mot dong tuong ung vao erpnext/patches.txt.",
	),
	(
		r"[^/]+\.md",
		"Tai lieu khong dat o goc repo.\n"
		"  -> docs/<ten>.md\n"
		"  Goc repo chi giu README.md, CLAUDE.md, NOTICE.md.\n"
		"  Spec thiet ke -> docs/superpowers/specs/YYYY-MM-DD-<chu-de>-design.md",
	),
	(
		r".+\.(sh|bash)|scripts?/.+",
		"Script -> scripts/<ten>.py (hoac scripts/<goi>/ neu nhieu file).\n"
		"  Test cua script -> scripts/tests/",
	),
]

_FALLBACK = (
	"Duong dan khong khop mau hop le nao cua repo.\n"
	"  Ma nguon BE   -> erpnext/<module>/...\n"
	"  Test          -> erpnext/<module>/tests/test_*.py\n"
	"  Tai lieu      -> docs/\n"
	"  Script        -> scripts/\n"
	"  Xem day du    -> scripts/file_structure/gate.py (bang RULES)"
)


def teach(path: str) -> str:
	"""Tra doan huong dan cho mot duong dan da bi lop cong tu choi."""
	try:
		p = (path or "").replace("\\", "/").removeprefix("./")
		for rx, msg in CARDS:
			if re.match(rx + r"\Z", p):
				return msg
	except Exception:
		pass
	return _FALLBACK

"""Chạy một module test bằng unittest trên site test, không cần bật `allow_tests`.

Dùng khi `bench run-tests` không chạy được (site chưa bật allow_tests hoặc thiếu dữ liệu
`_Test`). Mỗi test kế thừa FrappeTestCase tự rollback; script rollback thêm ở cuối.

	cd ~/frappe-bench/sites
	../env/bin/python ../apps/erpnext/scripts/chay_test.py --site erpnext.localhost \\
		erpnext.selling.tests.test_kiem_gia_bao_truoc [module khác ...]

Chạy từ git worktree (code của nhánh khác thư mục chính mà bench nạp) thì thêm `--worktree`:

	../env/bin/python /duong/dan/worktree/scripts/chay_test.py --worktree --site erpnext.localhost ...

Cờ này làm hai việc. Thiếu việc nào thì test chạy nhầm code hoặc nhầm hooks mà không báo lỗi.
- Nạp `erpnext` từ worktree chứa script này. Mặc định env của bench nạp từ thư mục chính.
- Bật `developer_mode` riêng trong tiến trình test, để `frappe.get_hooks` đọc thẳng `hooks.py`
  của worktree. Nếu không, nó lấy `app_hooks` trong Redis dùng chung với web của thư mục chính.
  Tiến trình test cũng không ghi hooks của nhánh vào cache đó.
Chạy script của worktree mà quên cờ thì script từ chối chạy.

Site và DB vẫn dùng chung: DocType / trường mới của nhánh phải được migrate vào site trước,
và nên báo phiên đang giữ thư mục chính.

TỪ CHỐI chạy trên site `miyano` (production).
"""

import argparse
import importlib
import importlib.util
import os
import sys
import unittest
from pathlib import Path

import frappe

GOC_REPO = Path(__file__).resolve().parents[1]


def _thu_muc_erpnext():
	"""Thư mục repo mà `import erpnext` sẽ nạp (chưa import)."""
	return Path(importlib.util.find_spec("erpnext").origin).resolve().parents[1]


def main():
	parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	parser.add_argument("--site", required=True)
	parser.add_argument("modules", nargs="+")
	parser.add_argument("-q", "--quiet", action="store_true", help="chỉ in tổng kết")
	parser.add_argument(
		"--worktree",
		action="store_true",
		help="nạp erpnext và hooks.py từ worktree chứa script này (xem docstring)",
	)
	args = parser.parse_args()
	if args.site == "miyano":
		sys.exit("Từ chối: không chạy test trên site production.")

	if args.worktree:
		sys.path.insert(0, str(GOC_REPO))
	if _thu_muc_erpnext() != GOC_REPO:
		sys.exit(
			f"Từ chối: script nằm ở {GOC_REPO} nhưng erpnext sẽ nạp từ {_thu_muc_erpnext()}. "
			"Chạy từ worktree thì thêm --worktree."
		)

	frappe.init(site=args.site, sites_path=os.getcwd())
	if args.worktree:
		frappe.local.conf.developer_mode = 1
		print(f"--worktree: code và hooks.py từ {GOC_REPO}")
	frappe.connect()
	ok = True
	try:
		frappe.flags.in_test = True
		frappe.set_user("Administrator")
		for name in args.modules:
			suite = unittest.defaultTestLoader.loadTestsFromModule(importlib.import_module(name))
			result = unittest.TextTestRunner(verbosity=1 if args.quiet else 2).run(suite)
			ok = ok and result.wasSuccessful()
	finally:
		frappe.db.rollback()
		frappe.destroy()
	sys.exit(0 if ok else 1)


if __name__ == "__main__":
	main()

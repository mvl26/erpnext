"""Chạy một module test bằng unittest trên site test, không cần bật `allow_tests`.

Dùng khi `bench run-tests` không chạy được (site chưa bật allow_tests hoặc thiếu dữ liệu
`_Test`). Mỗi test kế thừa FrappeTestCase tự rollback; script rollback thêm ở cuối.

	cd ~/frappe-bench/sites
	../env/bin/python ../apps/erpnext/scripts/chay_test.py --site erpnext.localhost \\
		erpnext.selling.tests.test_kiem_gia_bao_truoc [module khác ...]

TỪ CHỐI chạy trên site `miyano` (production).
"""

import argparse
import importlib
import os
import sys
import unittest

import frappe


def main():
	parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	parser.add_argument("--site", required=True)
	parser.add_argument("modules", nargs="+")
	parser.add_argument("-q", "--quiet", action="store_true", help="chỉ in tổng kết")
	args = parser.parse_args()
	if args.site == "miyano":
		sys.exit("Từ chối: không chạy test trên site production.")

	frappe.init(site=args.site, sites_path=os.getcwd())
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

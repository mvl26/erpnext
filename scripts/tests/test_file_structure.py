import json
import os
import subprocess
import sys
import unittest

from scripts.file_structure import cards, gate

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestGate(unittest.TestCase):
	def test_hai_ngoai_le_framework_phai_dau(self):
		# Frappe resolve dung hai duong dan nay; nan di la hong run-tests.
		self.assertEqual(
			gate.classify("erpnext/selling/doctype/sales_order/test_sales_order.py"), "doctype-test"
		)
		self.assertEqual(
			gate.classify("erpnext/stock/report/stock_balance/test_stock_balance.py"), "report-test"
		)

	def test_test_lac_trong_folder_doctype_phai_rot(self):
		# Chinh la loi da sua hom 2026-08-17: ten khac ten folder.
		self.assertIsNone(gate.classify("erpnext/accounts/doctype/bank_transaction/test_auto_match_party.py"))
		self.assertIsNone(gate.classify("erpnext/selling/report/sales_analytics/test_analytics.py"))

	def test_vi_tri_dung_sau_khi_don_phai_dau(self):
		for p in (
			"erpnext/accounts/test/test_auto_match_party.py",
			"erpnext/selling/tests/test_analytics.py",
			"erpnext/stock/tests/test_stock_ledger_report.py",
		):
			self.assertTrue(gate.is_allowed(p), p)

	def test_helper_khong_phai_test_van_dau_trong_doctype(self):
		# auto_match_party.py la ma nguon that, phai duoc phep.
		self.assertIsNotNone(gate.classify("erpnext/accounts/doctype/bank_transaction/auto_match_party.py"))

	def test_tai_lieu_o_goc_repo_phai_rot(self):
		self.assertIsNone(gate.classify("SPEC.md"))
		self.assertIsNone(gate.classify("attributions.md"))

	def test_ba_file_goc_repo_duoc_giu_phai_dau(self):
		for p in ("README.md", "CLAUDE.md", "NOTICE.md"):
			self.assertTrue(gate.is_allowed(p), p)


class TestAudit(unittest.TestCase):
	def test_moi_file_dang_tracked_deu_hop_le(self):
		"""Cong kiem chung: luat sai thi sua luat, khong phai sua repo."""
		out = subprocess.run(
			["git", "ls-files", "-z"], cwd=REPO, capture_output=True, text=True, check=True
		).stdout
		paths = [p for p in out.split("\0") if p]
		self.assertGreater(len(paths), 4000, "git ls-files tra ve qua it file")
		bad = [p for p in paths if not gate.is_allowed(p)]
		self.assertEqual(bad, [], f"{len(bad)} file hop le bi bao sai, vi du: {bad[:10]}")


class TestCards(unittest.TestCase):
	def test_day_dung_dich_cho_test_lac_trong_doctype(self):
		msg = cards.teach("erpnext/accounts/doctype/bank_transaction/test_auto_match_party.py")
		self.assertIn("erpnext/accounts/test/", msg)
		self.assertIn("test_<ten_doctype>.py", msg)

	def test_day_dung_dich_cho_tai_lieu_o_goc(self):
		msg = cards.teach("SPEC.md")
		self.assertIn("docs/", msg)

	def test_khong_bao_gio_rong_va_khong_bao_gio_qua_dai(self):
		for p in ("abc.xyz", "", "erpnext/x/y/z/w/v/u.py", "SPEC.md"):
			msg = cards.teach(p)
			self.assertTrue(msg.strip(), f"rong voi {p!r}")
			self.assertLessEqual(len(msg.splitlines()), 12, f"qua dai voi {p!r}")


def _run_hook(payload: dict):
	return subprocess.run(
		[sys.executable, "-m", "scripts.file_structure", "--hook"],
		input=json.dumps(payload),
		cwd=REPO,
		capture_output=True,
		text=True,
	)


class TestHook(unittest.TestCase):
	def test_duong_dan_dung_thi_im_lang_hoan_toan(self):
		r = _run_hook({"tool_input": {"file_path": f"{REPO}/erpnext/selling/tests/test_moi.py"}})
		self.assertEqual(r.returncode, 0)
		self.assertEqual(r.stdout, "")
		self.assertEqual(r.stderr, "")

	def test_duong_dan_sai_thi_chan_va_day(self):
		r = _run_hook({"tool_input": {"file_path": f"{REPO}/erpnext/selling/test_moi.py"}})
		self.assertEqual(r.returncode, 2)
		self.assertIn("erpnext/<module>/tests/", r.stderr)

	def test_file_da_ton_tai_thi_khong_chan(self):
		r = _run_hook({"tool_input": {"file_path": f"{REPO}/erpnext/hooks.py"}})
		self.assertEqual(r.returncode, 0)

	def test_bien_moi_truong_tat_hook(self):
		env = dict(os.environ, MIYANO_SKIP_FILE_STRUCTURE="1")
		r = subprocess.run(
			[sys.executable, "-m", "scripts.file_structure", "--hook"],
			input=json.dumps({"tool_input": {"file_path": f"{REPO}/erpnext/selling/test_moi.py"}}),
			cwd=REPO,
			capture_output=True,
			text=True,
			env=env,
		)
		self.assertEqual(r.returncode, 0)

	def test_bang_luat_hong_cu_phap_van_cho_qua(self):
		"""Hoi quy: gate/cards tung duoc import o cap module, nen SyntaxError trong
		bang luat lam hook thoat khac 0 truoc khi try/except kip chay."""
		src = os.path.join(REPO, "scripts", "file_structure", "gate.py")
		with open(src, encoding="utf-8") as fh:
			goc = fh.read()
		try:
			with open(src, "a", encoding="utf-8") as fh:
				fh.write("\nRULES = [(\n")
			r = _run_hook({"tool_input": {"file_path": f"{REPO}/erpnext/selling/test_moi.py"}})
			self.assertEqual(r.returncode, 0, "fail-open: bang luat hong thi phai cho qua")
		finally:
			with open(src, "w", encoding="utf-8") as fh:
				fh.write(goc)

	def test_stdin_rac_thi_cho_qua_chu_khong_chan(self):
		r = subprocess.run(
			[sys.executable, "-m", "scripts.file_structure", "--hook"],
			input="khong-phai-json",
			cwd=REPO,
			capture_output=True,
			text=True,
		)
		self.assertEqual(r.returncode, 0, "fail-open: stdin hong thi phai cho qua")


if __name__ == "__main__":
	unittest.main()

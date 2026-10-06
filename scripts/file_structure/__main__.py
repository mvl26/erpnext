"""CLI cho lop cong va lop day. Cho duy nhat cham stdin/stdout/exit code."""

import json
import os
import subprocess
import sys

# KHONG import gate/cards o cap module: neu bang luat co loi cu phap thi
# SyntaxError se no TRUOC khi try/except trong _hook() kip chay, va hook se
# thoat khac 0 — vi pham nguyen tac fail-open. Import tre ben trong tung ham.


def _hook() -> int:
	"""Doc payload cua Claude Code tu stdin, chan file MOI dat sai cho.

	Fail-open: bat ky truc trac nao — stdin hong, thieu khoa, loi bang luat —
	cung tra 0. Khong bao gio chan viec cua nguoi dung vi bug cua chinh cong cu.
	"""
	try:
		if os.environ.get("MIYANO_SKIP_FILE_STRUCTURE") == "1":
			return 0
		from scripts.file_structure import cards, gate

		payload = json.loads(sys.stdin.read() or "{}")
		raw = (payload.get("tool_input") or {}).get("file_path") or ""
		if not raw:
			return 0
		root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
		abs_path = raw if os.path.isabs(raw) else os.path.join(root, raw)
		if os.path.exists(abs_path):
			return 0  # Chi chan file MOI; sua file cu khong bao gio bi chan.
		rel = os.path.relpath(abs_path, root)
		if rel.startswith("..") or gate.is_allowed(rel):
			return 0
		message = f"Vi tri file sai quy uoc: {rel}\n\n{cards.teach(rel)}"
	except Exception:
		return 0

	print(message, file=sys.stderr)
	return 2


def _audit() -> int:
	# Audit la cong cu chan doan, khong phai hook: co loi thi phai bao to,
	# nen o day co y KHONG bat exception.
	from scripts.file_structure import gate

	out = subprocess.run(["git", "ls-files", "-z"], capture_output=True, text=True, check=True).stdout
	paths = [p for p in out.split("\0") if p]
	bad = [p for p in paths if not gate.is_allowed(p)]
	for p in bad:
		print(f"VI PHAM  {p}")
	print(f"\n{len(bad)} vi pham / {len(paths)} file")
	return 1 if bad else 0


def main(argv: list[str]) -> int:
	if "--hook" in argv:
		return _hook()
	if "--audit" in argv:
		return _audit()
	print("Dung: python3 -m scripts.file_structure [--audit|--check <path>|--hook]", file=sys.stderr)
	return 64


if __name__ == "__main__":
	sys.exit(main(sys.argv[1:]))

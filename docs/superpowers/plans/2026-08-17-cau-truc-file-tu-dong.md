# Cấu trúc file tự động — Kế hoạch thực thi

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dựng cơ chế chặn khiến mọi file AI tạo ra trong repo này luôn đúng thư mục và đúng quy ước tên, không phụ thuộc vào việc AI có nhớ đọc tài liệu hay không.

**Architecture:** Hai lớp tách bạch. *Lớp cổng* (`gate.py`) là bảng regex suy từ 4.673 file thật, trả lời đúng một bit: đường dẫn hợp lệ hay không — lớp này quyết định chặn nên phải chính xác tuyệt đối. *Lớp dạy* (`cards.py`) chỉ chạy sau khi cổng đã nói "sai", sinh chữ hướng dẫn — đoán sai cũng không chặn nhầm ai. Một CLI (`__main__.py`) gói cả hai thành hook `PreToolUse` của Claude Code.

**Tech Stack:** Python 3 thuần (stdlib, không phụ thuộc ngoài — `ruff` không có trên máy này). Hook `PreToolUse` của Claude Code. Không dùng subagent, không dùng workflow.

**Spec:** [docs/superpowers/specs/2026-08-17-cau-truc-file-tu-dong-design.md](../specs/2026-08-17-cau-truc-file-tu-dong-design.md)

## Global Constraints

Mọi task đều ngầm chịu các ràng buộc sau. Sao chép nguyên văn từ spec.

- **Fail-open tuyệt đối.** Checker tự nó lỗi (exception, file luật hỏng, thiếu Python) thì `exit 0` — cho qua. Không bao giờ chặn việc của người dùng vì bug của công cụ.
- **Chỉ chặn khi tạo file MỚI.** Sửa file đã tồn tại không bao giờ bị chặn. Kiểm bằng `os.path.exists`.
- **Im lặng khi đúng.** Hook hợp lệ thì không in gì ra stdout lẫn stderr, `exit 0`. Đây là ràng buộc token, không phải thẩm mỹ.
- **`git ls-files` phải dùng `-z`.** Không có `-z` thì 2 file PDF tiếng Việt trong `docs/` bị bọc ngoặc kép và báo nhầm.
- **Python style của repo: thụt đầu dòng bằng TAB**, độ dài dòng 110, chuỗi nháy kép. Bám theo file xung quanh.
- **Đường thoát:** biến môi trường `MIYANO_SKIP_FILE_STRUCTURE=1` tắt hook.
- **Hai ngoại lệ framework tuyệt đối không được nắn:** `doctype/<dt>/test_<dt>.py` và `report/<rp>/test_<rp>.py` (`frappe/test_runner.py:209`).
- **Chạy mọi lệnh `bench` từ bench root** `/home/miyano/frappe-bench`, không phải thư mục app.
- **Không commit** trừ khi người dùng yêu cầu. Các bước "Commit" bên dưới chỉ thực hiện sau khi người dùng đồng ý.

---

## File Structure

| File | Trách nhiệm |
|---|---|
| `scripts/__init__.py` | Đánh dấu gói, để `python3 -m scripts.file_structure` chạy được |
| `scripts/file_structure/__init__.py` | Đánh dấu gói |
| `scripts/file_structure/gate.py` | **Chỉ** bảng luật + `classify()` + `is_allowed()`. Không in ra, không đọc stdin |
| `scripts/file_structure/cards.py` | **Chỉ** thẻ khuôn + `teach()`. Không quyết định chặn |
| `scripts/file_structure/__main__.py` | CLI: `--hook`, `--audit`, `--check`. Chỗ duy nhất chạm stdin/stdout/exit code |
| `scripts/tests/__init__.py` | Đánh dấu gói |
| `scripts/tests/test_file_structure.py` | Test cho cả ba module trên |
| `.claude/skills/code_structure/SKILL.md` | Skill, trigger hẹp: tạo DocType/report/patch mới |
| `.claude/settings.json` | *(sửa)* thêm hook `PreToolUse` |
| `CLAUDE.md` | *(sửa)* thay mục dòng 76–84 bằng ~6 dòng trỏ về script |

Tách `gate` / `cards` / `__main__` vì ba thứ này có yêu cầu độ chính xác khác hẳn nhau — trộn chung là mất đúng cái tính chất khiến kiến trúc hai lớp an toàn.

---

## Task 1: Lớp cổng — bộ khung và test đỏ

**Files:**
- Create: `scripts/__init__.py`, `scripts/file_structure/__init__.py`, `scripts/file_structure/gate.py`
- Test: `scripts/tests/__init__.py`, `scripts/tests/test_file_structure.py`

**Interfaces:**
- Produces: `gate.classify(path: str) -> str | None` trả tên loại hoặc `None` nếu không mẫu nào khớp. `gate.is_allowed(path: str) -> bool` là `classify(path) is not None`. `gate.RULES: list[tuple[str, str]]` là danh sách `(tên_loại, regex)` theo thứ tự, mẫu hẹp trước mẫu rộng.

- [ ] **Step 1: Viết test đỏ**

Bộ test bám đúng 5 đường dẫn vừa sửa trong đợt dọn 2026-08-17, cộng hai ngoại lệ framework.

```python
import os
import unittest

from scripts.file_structure import gate

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
		self.assertIsNone(
			gate.classify("erpnext/accounts/doctype/bank_transaction/test_auto_match_party.py")
		)
		self.assertIsNone(
			gate.classify("erpnext/selling/report/sales_analytics/test_analytics.py")
		)

	def test_vi_tri_dung_sau_khi_don_phai_dau(self):
		for p in (
			"erpnext/accounts/test/test_auto_match_party.py",
			"erpnext/selling/tests/test_analytics.py",
			"erpnext/stock/tests/test_stock_ledger_report.py",
		):
			self.assertTrue(gate.is_allowed(p), p)

	def test_helper_khong_phai_test_van_dau_trong_doctype(self):
		# auto_match_party.py la ma nguon that, phai duoc phep.
		self.assertIsNotNone(
			gate.classify("erpnext/accounts/doctype/bank_transaction/auto_match_party.py")
		)

	def test_tai_lieu_o_goc_repo_phai_rot(self):
		self.assertIsNone(gate.classify("SPEC.md"))
		self.assertIsNone(gate.classify("attributions.md"))

	def test_ba_file_goc_repo_duoc_giu_phai_dau(self):
		for p in ("README.md", "CLAUDE.md", "NOTICE.md"):
			self.assertTrue(gate.is_allowed(p), p)


if __name__ == "__main__":
	unittest.main()
```

- [ ] **Step 2: Chạy test, xác nhận ĐỎ**

```bash
cd /home/miyano/frappe-bench/apps/erpnext && python3 -m unittest scripts.tests.test_file_structure -v
```

Kỳ vọng: FAIL với `ModuleNotFoundError: No module named 'scripts'`.

- [ ] **Step 3: Tạo bộ khung tối thiểu**

`scripts/__init__.py`, `scripts/file_structure/__init__.py`, `scripts/tests/__init__.py` — cả ba là file rỗng.

`scripts/file_structure/gate.py`:

```python
"""Lop cong: tra loi dung mot bit — duong dan co hop le khong.

Bang luat suy tu 4.673 file dang tracked (2026-08-17). Sua RULES roi chay
`python3 -m scripts.file_structure --audit` de biet co vo gi khong.
"""

import re

# (ten_loai, regex). THU TU QUAN TRONG: mau hep dung truoc mau rong.
RULES: list[tuple[str, str]] = []

_COMPILED: list[tuple[str, re.Pattern]] = []


def _compiled() -> list[tuple[str, re.Pattern]]:
	global _COMPILED
	if len(_COMPILED) != len(RULES):
		_COMPILED = [(kind, re.compile(rx + r"\Z")) for kind, rx in RULES]
	return _COMPILED


def classify(path: str) -> str | None:
	"""Tra ten loai cua duong dan, hoac None neu khong mau nao khop."""
	path = path.replace("\\", "/").lstrip("./")
	for kind, rx in _compiled():
		if rx.match(path):
			return kind
	return None


def is_allowed(path: str) -> bool:
	return classify(path) is not None
```

- [ ] **Step 4: Chạy lại, xác nhận vẫn đỏ nhưng đã đổi lý do**

```bash
cd /home/miyano/frappe-bench/apps/erpnext && python3 -m unittest scripts.tests.test_file_structure -v
```

Kỳ vọng: FAIL vì `RULES` rỗng nên mọi thứ trả `None` — không còn `ModuleNotFoundError`. Đây là mốc xác nhận bộ khung đã chạy.

---

## Task 2: Bảng luật — đưa `--audit` về 0 vi phạm

**Files:**
- Modify: `scripts/file_structure/gate.py` (điền `RULES`)
- Modify: `scripts/file_structure/__main__.py` (tạo mới ở task này, chỉ phần `--audit`)
- Test: `scripts/tests/test_file_structure.py` (thêm bài audit)

**Interfaces:**
- Consumes: `gate.classify`, `gate.RULES` từ Task 1.
- Produces: `python3 -m scripts.file_structure --audit` in danh sách vi phạm ra stdout và `exit 1` nếu có, `exit 0` nếu sạch.

- [ ] **Step 1: Viết test audit (đỏ)**

Thêm vào `scripts/tests/test_file_structure.py`:

```python
import subprocess


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
```

- [ ] **Step 2: Chạy, xác nhận đỏ và ĐỌC danh sách vi phạm**

```bash
cd /home/miyano/frappe-bench/apps/erpnext && python3 -m unittest scripts.tests.test_file_structure.TestAudit -v
```

Kỳ vọng: FAIL, liệt kê ~4673 file. Đây là danh sách công việc của bước sau.

- [ ] **Step 3: Điền `RULES`**

Đặt vào `gate.py`, thay `RULES: list[tuple[str, str]] = []`. Số ở cuối mỗi dòng là số file thật đã đếm.

```python
RULES: list[tuple[str, str]] = [
	# --- DocType: hai ngoai le framework dung TRUOC moi mau khac ---
	("doctype-test", r"erpnext/[^/]+/doctype/(?P<dt>[^/]+)/test_(?P=dt)\.py"),        # 276
	("doctype-records", r"erpnext/[^/]+/doctype/[^/]+/test_records\.json"),           # 64
	("doctype-data", r"erpnext/[^/]+/doctype/[^/]+/[^/]+/.+"),                        # 108
	("doctype-pkg", r"erpnext/[^/]+/doctype/__init__\.py"),                           # 23
	# Cho phep file phu tro, NHUNG chan moi thu bat dau bang test_ .
	# Day chinh la luat bat duoc loi da sua hom 2026-08-17.
	(
		"doctype",
		r"erpnext/[^/]+/doctype/(?P<dt>[^/]+)/"
		r"(__init__\.py|README\.md|(?P=dt)[a-z0-9_]*\.(py|js|json|css|html)"
		r"|(?!test_)[a-z0-9_]+\.(py|html|csv))",
	),                                                                                # 2439
	# --- Report: cung khuon voi DocType ---
	("report-test", r"erpnext/[^/]+/report/(?P<rp>[^/]+)/test_(?P=rp)\.py"),          # 56
	("report-pkg", r"erpnext/[^/]+/report/__init__\.py"),                             # 13
	(
		"report",
		r"erpnext/[^/]+/report/(?P<rp>[^/]+)/"
		r"(__init__\.py|(?P=rp)[a-z0-9_]*\.(py|js|json|html|md)"
		r"|(?!test_)[a-z0-9_]+\.(py|xml|html|md))",
	),                                                                                # 799
	("report-shared", r"erpnext/[^/]+/report/(?!test_)[a-z0-9_]+\.(py|html)"),        # 5
	# --- Test cua module va sub-package (Accounts dung 'test/') ---
	("module-test", r"erpnext/[^/]+/tests?/(__init__\.py|test_[a-z0-9_]+\.py|[a-z0-9_]+\.(py|json))"),
	("subpkg-test", r"erpnext/[^/]+/[^/]+/tests?/(__init__\.py|test_[a-z0-9_]+\.py|[a-z0-9_]+\.(py|json))"),
	# --- Patch ---
	("patch", r"erpnext/patches/(__init__\.py|v[0-9_]+/(__init__\.py|[a-z0-9_]+\.py))"),  # 375
	# --- Fixture do Frappe sinh ra (dashboard, workspace, print format...) ---
	(
		"fixture",
		r"erpnext/[^/]+/[a-z0-9_]*"
		r"(dashboard|workspace|onboarding|number_card|form_tour|notification"
		r"|print_format|web_form|role|workflow|custom|chart_source)[a-z0-9_]*/.+",
	),                                                                                # 324
	("page", r"erpnext/[^/]+/page/(__init__\.py|[^/]+/.+)"),                          # 31
	("web-template", r"erpnext/[^/]+/web_template/[^/]+/.+"),
	# --- He thong con cua app ---
	("app-subsystem", r"erpnext/(public|templates|www|translations|startup|config|domains|commands)/.+"),  # 282
	("app-pkg", r"erpnext/(tests|controllers|utilities|setup)/.+"),                   # 67
	# --- Ma nguon cap module va sub-package ---
	("module-code", r"erpnext/[^/]+/(?!test_)[a-z0-9_]+\.(py|json|txt|md)"),          # 66
	("subpkg-code", r"erpnext/[^/]+/[^/]+/(?!test_)[a-z0-9_]+\.(py|json|html|xml|md|csv)"),  # 41
	("subpkg-data", r"erpnext/[^/]+/[^/]+/[^/]+/.+"),
	("app-root", r"erpnext/(__init__|hooks|exceptions)\.py|erpnext/(modules|patches)\.txt|erpnext/\.stylelintrc"),
	# --- Ngoai erpnext/ ---
	("spec", r"docs/superpowers/specs/\d{4}-\d{2}-\d{2}-[a-z0-9-]+-design\.md"),
	("plan", r"docs/superpowers/plans/\d{4}-\d{2}-\d{2}-[a-z0-9-]+\.md"),
	("doc", r"docs/.+"),                                                              # 11
	("script", r"scripts/.+"),
	("claude-config", r"\.claude/.+"),
	(
		"repo-root",
		r"(README|CLAUDE|NOTICE)\.md|package\.json|pyproject\.toml|yarn\.lock"
		r"|\.(gitignore|editorconfig|eslintrc|flake8|semgrepignore|pre-commit-config\.yaml"
		r"|git-blame-ignore-revs|stylelintrc)|logo-miyano\.png",
	),                                                                                # 14
]
```

- [ ] **Step 4: Vòng lặp cho tới 0 vi phạm**

```bash
cd /home/miyano/frappe-bench/apps/erpnext && python3 -m unittest scripts.tests.test_file_structure.TestAudit -v
```

Mỗi lần FAIL, đọc danh sách còn sót, thêm hoặc nới một mẫu, chạy lại. Lặp tới khi PASS.

**Quan trọng — đây là nơi dễ làm hỏng cả hệ thống nhất:** khi nới mẫu để hết báo nhầm, tuyệt đối không nới rộng tới mức `test_auto_match_party.py` trong folder `bank_transaction` lại thành hợp lệ. Sau **mỗi** lần sửa `RULES`, chạy cả `TestGate` chứ không chỉ `TestAudit`:

```bash
cd /home/miyano/frappe-bench/apps/erpnext && python3 -m unittest scripts.tests.test_file_structure -v
```

Kỳ vọng cuối: cả `TestGate` lẫn `TestAudit` đều PASS.

- [ ] **Step 5: Viết `--audit` vào CLI**

`scripts/file_structure/__main__.py`:

```python
"""CLI cho lop cong va lop day. Cho duy nhat cham stdin/stdout/exit code."""

import subprocess
import sys

from scripts.file_structure import gate


def _audit() -> int:
	out = subprocess.run(
		["git", "ls-files", "-z"], capture_output=True, text=True, check=True
	).stdout
	paths = [p for p in out.split("\0") if p]
	bad = [p for p in paths if not gate.is_allowed(p)]
	for p in bad:
		print(f"VI PHAM  {p}")
	print(f"\n{len(bad)} vi pham / {len(paths)} file")
	return 1 if bad else 0


def main(argv: list[str]) -> int:
	if "--audit" in argv:
		return _audit()
	print("Dung: python3 -m scripts.file_structure [--audit|--check <path>|--hook]", file=sys.stderr)
	return 64


if __name__ == "__main__":
	sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 6: Chạy `--audit` thật, lưu output làm bằng chứng**

```bash
cd /home/miyano/frappe-bench/apps/erpnext && python3 -m scripts.file_structure --audit; echo "EXIT=$?"
```

Kỳ vọng: `0 vi pham / 4673 file`, `EXIT=0`.

- [ ] **Step 7: Commit** *(chỉ khi người dùng đã đồng ý — xem Global Constraints)*

```bash
git add scripts/ && git commit -m "feat(scripts): lop cong kiem tra vi tri file, audit sach 4673 file"
```

---

## Task 3: Lớp dạy — thẻ khuôn

**Files:**
- Create: `scripts/file_structure/cards.py`
- Test: `scripts/tests/test_file_structure.py` (thêm `TestCards`)

**Interfaces:**
- Consumes: `gate.classify` từ Task 1.
- Produces: `cards.teach(path: str) -> str` trả đoạn hướng dẫn ≤12 dòng cho đường dẫn sai. Không bao giờ raise, không bao giờ trả chuỗi rỗng.

- [ ] **Step 1: Viết test đỏ**

```python
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
```

Nhớ thêm `cards` vào dòng import đầu file: `from scripts.file_structure import cards, gate`.

- [ ] **Step 2: Chạy, xác nhận đỏ**

```bash
cd /home/miyano/frappe-bench/apps/erpnext && python3 -m unittest scripts.tests.test_file_structure.TestCards -v
```

Kỳ vọng: FAIL với `ImportError: cannot import name 'cards'`.

- [ ] **Step 3: Viết `cards.py`**

```python
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
	(
		r"erpnext/patches/.+",
		"Patch -> erpnext/patches/v15_0/<dong_tu>_<danh_tu>.py\n"
		"  Nho them mot dong tuong ung vao erpnext/patches.txt.",
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
		p = (path or "").replace("\\", "/").lstrip("./")
		for rx, msg in CARDS:
			if re.match(rx + r"\Z", p):
				return msg
	except Exception:
		pass
	return _FALLBACK
```

- [ ] **Step 4: Chạy, xác nhận xanh**

```bash
cd /home/miyano/frappe-bench/apps/erpnext && python3 -m unittest scripts.tests.test_file_structure -v
```

Kỳ vọng: toàn bộ PASS.

- [ ] **Step 5: Commit** *(chỉ khi người dùng đã đồng ý)*

```bash
git add scripts/ && git commit -m "feat(scripts): lop day — the khuon huong dan khi dat file sai cho"
```

---

## Task 4: CLI `--hook` và fail-open

**Files:**
- Modify: `scripts/file_structure/__main__.py`
- Test: `scripts/tests/test_file_structure.py` (thêm `TestHook`)

**Interfaces:**
- Consumes: `gate.is_allowed`, `cards.teach`.
- Produces: `python3 -m scripts.file_structure --hook` đọc JSON từ stdin, lấy `.tool_input.file_path`. `exit 0` im lặng nếu hợp lệ / file đã tồn tại / thiếu dữ liệu / gặp lỗi. `exit 2` kèm hướng dẫn ra **stderr** nếu file mới và sai chỗ.

- [ ] **Step 1: Viết test đỏ**

```python
import json


def _run_hook(payload: dict):
	return subprocess.run(
		[sys.executable, "-m", "scripts.file_structure", "--hook"],
		input=json.dumps(payload), cwd=REPO, capture_output=True, text=True,
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
		# CLAUDE.md hop le, nhung quan trong hon: sua file cu khong bao gio bi chan.
		r = _run_hook({"tool_input": {"file_path": f"{REPO}/erpnext/hooks.py"}})
		self.assertEqual(r.returncode, 0)

	def test_bien_moi_truong_tat_hook(self):
		env = dict(os.environ, MIYANO_SKIP_FILE_STRUCTURE="1")
		r = subprocess.run(
			[sys.executable, "-m", "scripts.file_structure", "--hook"],
			input=json.dumps({"tool_input": {"file_path": f"{REPO}/erpnext/selling/test_moi.py"}}),
			cwd=REPO, capture_output=True, text=True, env=env,
		)
		self.assertEqual(r.returncode, 0)

	def test_stdin_rac_thi_cho_qua_chu_khong_chan(self):
		r = subprocess.run(
			[sys.executable, "-m", "scripts.file_structure", "--hook"],
			input="khong-phai-json", cwd=REPO, capture_output=True, text=True,
		)
		self.assertEqual(r.returncode, 0, "fail-open: stdin hong thi phai cho qua")
```

Thêm `import sys` vào đầu file test.

- [ ] **Step 2: Chạy, xác nhận đỏ**

```bash
cd /home/miyano/frappe-bench/apps/erpnext && python3 -m unittest scripts.tests.test_file_structure.TestHook -v
```

Kỳ vọng: FAIL — `--hook` chưa được cài nên CLI trả 64.

- [ ] **Step 3: Cài `--hook`**

Thêm vào `scripts/file_structure/__main__.py`:

```python
import json
import os

from scripts.file_structure import cards


def _hook() -> int:
	# Fail-open: bat ky truc trac nao cung cho qua. Khong bao giu chan viec
	# cua nguoi dung vi bug cua chinh cong cu nay.
	try:
		if os.environ.get("MIYANO_SKIP_FILE_STRUCTURE") == "1":
			return 0
		payload = json.loads(sys.stdin.read() or "{}")
		raw = (payload.get("tool_input") or {}).get("file_path") or ""
		if not raw:
			return 0
		root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
		abs_path = raw if os.path.isabs(raw) else os.path.join(root, raw)
		if os.path.exists(abs_path):
			return 0  # Chi chan file MOI.
		rel = os.path.relpath(abs_path, root)
		if rel.startswith("..") or gate.is_allowed(rel):
			return 0
	except Exception:
		return 0

	print(f"Vi tri file sai quy uoc: {rel}\n\n{cards.teach(rel)}", file=sys.stderr)
	return 2
```

và trong `main()`, ngay trước nhánh `--audit`:

```python
	if "--hook" in argv:
		return _hook()
```

- [ ] **Step 4: Chạy, xác nhận xanh**

```bash
cd /home/miyano/frappe-bench/apps/erpnext && python3 -m unittest scripts.tests.test_file_structure -v
```

Kỳ vọng: toàn bộ PASS.

- [ ] **Step 5: Thử fail-open bằng cách làm hỏng thật**

```bash
cd /home/miyano/frappe-bench/apps/erpnext
cp scripts/file_structure/gate.py /tmp/gate.bak
printf 'RULES = [(\n' >> scripts/file_structure/gate.py   # co y lam hong cu phap
echo '{"tool_input":{"file_path":"'"$PWD"'/erpnext/selling/test_x.py"}}' \
  | python3 -m scripts.file_structure --hook; echo "EXIT=$?"
cp /tmp/gate.bak scripts/file_structure/gate.py
```

Kỳ vọng: `EXIT=0`. File luật hỏng mà vẫn chặn là vi phạm fail-open — phải sửa.

- [ ] **Step 6: Commit** *(chỉ khi người dùng đã đồng ý)*

```bash
git add scripts/ && git commit -m "feat(scripts): CLI --hook chan file moi sai vi tri, fail-open khi loi"
```

---

## Task 5: Gắn hook vào Claude Code và thử chặn thật

**Files:**
- Modify: `.claude/settings.json`

**Interfaces:**
- Consumes: `python3 -m scripts.file_structure --hook` từ Task 4.

- [ ] **Step 1: Đọc settings hiện tại**

```bash
cd /home/miyano/frappe-bench/apps/erpnext && cat .claude/settings.json
```

Hiện chỉ có khoá `enabledPlugins` — phải giữ nguyên, không ghi đè.

- [ ] **Step 2: Thêm hook**

Dùng skill `update-config` để sửa `.claude/settings.json`. Kết quả mong muốn:

```json
{
  "enabledPlugins": {
    "agent-skills@addy-agent-skills": true
  },
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "cd \"$CLAUDE_PROJECT_DIR\" && python3 -m scripts.file_structure --hook"
          }
        ]
      }
    ]
  }
}
```

- [ ] **Step 3: Xác nhận JSON hợp lệ**

```bash
cd /home/miyano/frappe-bench/apps/erpnext && python3 -m json.tool .claude/settings.json
```

Kỳ vọng: in ra JSON, không lỗi.

- [ ] **Step 4: Thử chặn thật — bằng chứng quan trọng nhất của cả kế hoạch**

Trong một phiên Claude Code mới, thử `Write` vào `erpnext/selling/test_hook_thu.py`.

Kỳ vọng: bị chặn, thông báo nêu `erpnext/<module>/tests/`. **Không** được tự viết ra file.

Rồi thử `Write` vào `erpnext/selling/tests/test_hook_thu.py` — kỳ vọng: đi qua im lặng. Xoá file thử sau khi xong.

Nếu hook không kích hoạt: kiểm `matcher` có khớp tên tool không, và `CLAUDE_PROJECT_DIR` có trỏ đúng thư mục app không.

- [ ] **Step 5: Commit** *(chỉ khi người dùng đã đồng ý)*

```bash
git add .claude/settings.json && git commit -m "chore(claude): gan hook PreToolUse kiem tra vi tri file"
```

---

## Task 6: Skill `code_structure`

**Files:**
- Create: `.claude/skills/code_structure/SKILL.md`

**Interfaces:**
- Consumes: bảng `RULES` trong `gate.py` — skill **trỏ về** đó, không chép lại, để tránh trôi lệch.

- [ ] **Step 1: Viết SKILL.md**

Trigger phải hẹp: chỉ cho việc tạo **nhiều file cùng lúc**. Lý do ở spec §4 — sửa một file lẻ thì hook lo, gọi skill là tốn token thừa.

```markdown
---
name: code_structure
description: Use when creating a new DocType, report, or patch in this repo — any task that creates several files at once and must follow the Miyano ERP folder and naming layout. Not needed for editing a single existing file; the PreToolUse hook covers that.
---

# Cấu trúc file — Miyano ERP

Nguồn sự thật là bảng `RULES` trong `scripts/file_structure/gate.py`.
Tài liệu này chỉ tóm tắt các bộ file hay tạo cùng lúc.

## Tạo DocType mới

    erpnext/<module>/doctype/<snake_case>/
        __init__.py
        <snake_case>.json      # schema — nguồn sự thật của mô hình dữ liệu
        <snake_case>.py        # controller
        <snake_case>.js        # form script (nếu cần)
        test_<snake_case>.py   # BẮT BUỘC trùng tên folder

Sau đó chạy `bench --site miyano migrate` từ bench root.

## Tạo report mới

    erpnext/<module>/report/<snake_case>/
        __init__.py
        <snake_case>.json
        <snake_case>.py
        test_<snake_case>.py   # BẮT BUỘC trùng tên folder

## Tạo patch mới

    erpnext/patches/v15_0/<động_từ>_<danh_từ>.py

Rồi thêm một dòng tương ứng vào `erpnext/patches.txt`. Thiếu dòng này thì patch không chạy.

## Test đặt ở đâu

- Mặc định: `erpnext/<module>/tests/test_*.py` (Accounts dùng `erpnext/accounts/test/`)
- Sub-package tự chứa: `erpnext/<module>/<sub>/tests/`, ví dụ `erpnext/einvoice/tests/`
- Mọi folder test phải có `__init__.py`

**Hai ngoại lệ duy nhất** — Frappe resolve theo đúng đường dẫn, đặt chỗ khác là
`bench run-tests --doctype "X"` không tìm thấy:

- `erpnext/<module>/doctype/<dt>/test_<dt>.py`
- `erpnext/<module>/report/<rp>/test_<rp>.py`

Tên khác tên folder thì **không** thuộc ngoại lệ — chuyển vào `tests/` của module.

## Tài liệu và script

- Tài liệu: `docs/`. Gốc repo chỉ giữ `README.md`, `CLAUDE.md`, `NOTICE.md`
- Spec thiết kế: `docs/superpowers/specs/YYYY-MM-DD-<chủ-đề>-design.md`
- Script: `scripts/`, test của script: `scripts/tests/`

## Khi bị hook chặn

Đọc thông báo — nó đã nêu vị trí đúng. Nếu chắc chắn đó là ngoại lệ chính đáng:
sửa bảng `RULES` trong `gate.py` rồi chạy
`python3 -m scripts.file_structure --audit` để xác nhận không vỡ gì.
Cần làm gấp thì đặt `MIYANO_SKIP_FILE_STRUCTURE=1`.
```

- [ ] **Step 2: Xác minh skill load được thật**

Đây là tiêu chí §9.7 của spec, và là chỗ rủi ro đã biết: tên có gạch dưới đi ngược quy ước
(`writing-skills/SKILL.md:98` khuyến nghị chỉ dùng chữ/số/gạch ngang).

Trong một phiên Claude Code mới, kiểm xem `code_structure` có xuất hiện trong danh sách skill
khả dụng không. **Không suy đoán từ việc file tồn tại.**

Nếu **không** load được: đổi sang `code-structure`.

```bash
cd /home/miyano/frappe-bench/apps/erpnext
git mv .claude/skills/code_structure .claude/skills/code-structure
# rồi sửa dòng `name:` trong SKILL.md cho khớp
```

Báo lại cho người dùng biết đã phải đổi và vì sao.

- [ ] **Step 3: Commit** *(chỉ khi người dùng đã đồng ý)*

```bash
git add .claude/skills/ && git commit -m "docs(claude): skill code_structure — bo file hay tao cung luc"
```

---

## Task 7: Cắt ngắn CLAUDE.md và kiểm chứng tổng

**Files:**
- Modify: `CLAUDE.md:76-84`

- [ ] **Step 1: Đo trước khi sửa**

```bash
cd /home/miyano/frappe-bench/apps/erpnext && wc -l -c CLAUDE.md
```

Ghi lại con số. Tiêu chí §9.5: sau khi sửa phải **nhỏ hơn**.

- [ ] **Step 2: Thay mục dòng 76–84**

Xoá cả đoạn `**Where test files go — mandatory:** ...` và `**The two exceptions — framework-mandated, do not move:**` cùng hai gạch đầu dòng của nó, thay bằng:

```markdown
**Where files go — enforced, not advisory:** `scripts/file_structure/gate.py` holds the
authoritative path map; a `PreToolUse` hook blocks any *new* file that lands in the wrong
place and tells you the right one. Run `python3 -m scripts.file_structure --audit` to check
the whole tree. Two framework-mandated exceptions the map allows on purpose:
`<module>/doctype/<dt>/test_<dt>.py` and `<module>/report/<rp>/test_<rp>.py` — Frappe resolves
those by path. Everything else named `test_*.py` belongs in `<module>/tests/`
(Accounts uses `accounts/test/`). See the `code_structure` skill when creating a DocType,
report, or patch.
```

- [ ] **Step 3: Đo lại, xác nhận ngắn hơn**

```bash
cd /home/miyano/frappe-bench/apps/erpnext && wc -l -c CLAUDE.md
```

Kỳ vọng: cả số dòng lẫn số ký tự đều nhỏ hơn Step 1. Nếu không, cắt tiếp — mục này nằm trong context của **mọi** request.

- [ ] **Step 4: Chạy lại toàn bộ tiêu chí kiểm chứng §9 của spec**

```bash
cd /home/miyano/frappe-bench/apps/erpnext
python3 -m scripts.file_structure --audit; echo "AUDIT_EXIT=$?"
python3 -m unittest scripts.tests.test_file_structure -v 2>&1 | tail -5
```

Kỳ vọng: `0 vi pham / 4673 file`, `AUDIT_EXIT=0`, toàn bộ test PASS.

Bốn tiêu chí còn lại đã làm ở các task trước — đối chiếu lại và báo cáo trung thực cái nào
chưa chứng minh được:

| § | Tiêu chí | Làm ở |
|---|---|---|
| 9.1 | `--audit` 0 vi phạm | Task 2 Step 6 |
| 9.2 | Test checker xanh | Task 4 Step 4 |
| 9.3 | Thử chặn thật trong phiên | Task 5 Step 4 |
| 9.4 | Thử fail-open | Task 4 Step 5 |
| 9.5 | CLAUDE.md ngắn hơn | Task 7 Step 3 |
| 9.6 | Hook im lặng khi đúng | Task 4 Step 4 |
| 9.7 | Skill load được thật | Task 6 Step 2 |

- [ ] **Step 5: Commit** *(chỉ khi người dùng đã đồng ý)*

```bash
git add CLAUDE.md && git commit -m "docs(repo): CLAUDE.md tro ve gate.py lam nguon su that ve vi tri file"
```

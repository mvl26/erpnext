# App PDA (APK Android) — kế hoạch thi công

> **Cho người thi công:** dùng `superpowers:subagent-driven-development` hoặc `superpowers:executing-plans` để làm từng Task. Mỗi bước có ô `- [ ]` để đánh dấu.

**Mục tiêu:** một file APK cài lên máy PDA Zebra/Honeywell, mở ra là quét thẻ nhân viên đăng nhập rồi vào thẳng bốn màn hình kho đang chạy trên web; mọi thao tác ghi thẳng vào hệ thống như khi dùng trình duyệt.

**Kiến trúc:** vỏ Capacitor mỏng (chọn máy chủ, khoá điều hướng) + WebView trỏ vào chính máy chủ Frappe. Không một dòng nghiệp vụ nào được sao chép xuống máy. Đăng nhập bằng thẻ mã vạch Code128 in từ máy in tem sẵn có; phiên sống 12 tiếng.

**Tech Stack:** Frappe v15 / ERPNext (Python, JS desk pages), Capacitor 6 + Android SDK 34 + JDK 17, Code128 qua module tem sẵn có (`tem_lo.js`).

**Spec:** `docs/superpowers/specs/2026-09-23-app-pda-apk-design.md`

## Global Constraints

- **KHÔNG tự commit.** CLAUDE.md: mọi thao tác git chỉ làm khi chủ đầu tư yêu cầu đúng lần đó. Mỗi Task kết thúc bằng bước "báo cáo", không phải "commit".
- Bench: `/home/hoangvietyeuem/frappe-bench-yhct`, site thử: `erptest.local`, chạy lệnh từ bench root.
- Python: **thụt bằng TAB**, dòng tối đa 110 ký tự, chuỗi nháy kép.
- Vai trò dùng thẻ: `{"System Manager", "Stock Manager", "Stock User"}`. Vai trò cấp/thu hồi thẻ: `{"System Manager", "Stock Manager"}`.
- Mã thẻ: **12 ký tự**, bảng chữ `ABCDEFGHJKLMNPQRSTUVWXYZ23456789`, máy chủ chỉ lưu `sha256`.
- Phiên PDA: **12 tiếng**, không gia hạn khi dùng tiếp.
- Máy chủ mặc định trong app: `http://192.168.61.129:8003`.
- Bốn màn hình app mở được: `/app/xep-hang-pda`, `/app/lay-hang-pda`, `/app/quet-ma-tra-cuu`, `/app/dat-o-hang-loat` (+ `/pda`, `/app/pda-home`).
- Sau mỗi Task: `bench --site erptest.local run-tests --module <module vừa sửa>` phải xanh trước khi sang Task sau.

---

### Task 1: DocType `PDA Badge` — cấp và thu hồi thẻ

**Files:**
- Create: `erpnext/warehouse_operations/doctype/pda_badge/__init__.py` (rỗng)
- Create: `erpnext/warehouse_operations/doctype/pda_badge/pda_badge.json`
- Create: `erpnext/warehouse_operations/doctype/pda_badge/pda_badge.py`
- Create: `erpnext/warehouse_operations/doctype/pda_badge/test_pda_badge.py` (rỗng có docstring — Frappe đòi file này tồn tại cho mọi doctype; bài thật nằm ở `tests/test_the_pda.py`)
- Create: `erpnext/warehouse_operations/vitri/the_pda.py`
- Create: `erpnext/warehouse_operations/tests/test_the_pda.py`

**Interfaces:**
- Produces: `the_pda.bam(ma: str) -> str`; `the_pda.cap_the(nguoi_dung: str) -> dict` (khoá `the`, `ho_ten`, `ma`, `cap_luc`); `the_pda.thu_hoi(nguoi_dung: str) -> dict`; hằng `VAI_TRO_DUOC_DUNG_THE`, `VAI_TRO_QUAN_LY_THE`, `DO_DAI_MA`, `BANG_CHU`.
- Consumes: không có (Task đầu).

- [ ] **Bước 1: Viết bài test trước**

Tạo `erpnext/warehouse_operations/tests/test_the_pda.py`:

```python
"""Thẻ PDA: cấp, thu hồi, và đăng nhập bằng thẻ (spec 2026-09-23 §5).

NGƯỜI DÙNG THỬ KHÔNG XOÁ ĐƯỢC BẰNG ROLLBACK: `User.insert()` tự `commit()`
bên trong (xem ghi chú Frappe v15 của dự án), nên helper dưới đây dựng MỘT
tài khoản cố định rồi dùng lại — không tạo tài khoản mới mỗi lần chạy.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

DIEM_TEST = "test_the_pda"
NGUOI_KHO = "9p-thukho@miyano.test"
NGUOI_NGOAI = "9p-ngoaikho@miyano.test"


def _nguoi(email: str, vai_tro: list[str]) -> str:
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": email.split("@")[0],
				"send_welcome_email": 0,
				"enabled": 1,
			}
		).insert(ignore_permissions=True)
	u = frappe.get_doc("User", email)
	u.enabled = 1
	co = {r.role for r in u.roles}
	for r in vai_tro:
		if r not in co:
			u.append("roles", {"role": r})
	u.save(ignore_permissions=True)
	return email


class TestCapThe(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.savepoint(DIEM_TEST)
		_nguoi(NGUOI_KHO, ["Stock User"])
		_nguoi(NGUOI_NGOAI, ["Accounts User"])

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point=DIEM_TEST)

	def test_cap_the_tra_ma_12_ky_tu_dung_bang_chu(self):
		from erpnext.warehouse_operations.vitri.the_pda import BANG_CHU, DO_DAI_MA, cap_the

		kq = cap_the(NGUOI_KHO)
		self.assertEqual(len(kq["ma"]), DO_DAI_MA)
		self.assertTrue(set(kq["ma"]) <= set(BANG_CHU), kq["ma"])
		self.assertEqual(kq["the"], NGUOI_KHO)

	def test_chi_luu_ban_bam_khong_luu_ma_goc(self):
		from erpnext.warehouse_operations.vitri.the_pda import bam, cap_the

		ma = cap_the(NGUOI_KHO)["ma"]
		doc = frappe.get_doc("PDA Badge", NGUOI_KHO)
		self.assertEqual(doc.ma_bam, bam(ma))
		self.assertNotIn(ma, frappe.as_json(doc.as_dict()))

	def test_cap_lai_thi_the_cu_chet(self):
		from erpnext.warehouse_operations.vitri.the_pda import bam, cap_the

		ma_cu = cap_the(NGUOI_KHO)["ma"]
		ma_moi = cap_the(NGUOI_KHO)["ma"]
		self.assertNotEqual(ma_cu, ma_moi)
		self.assertEqual(frappe.db.get_value("PDA Badge", NGUOI_KHO, "ma_bam"), bam(ma_moi))

	def test_thu_hoi_tat_hieu_luc(self):
		from erpnext.warehouse_operations.vitri.the_pda import cap_the, thu_hoi

		cap_the(NGUOI_KHO)
		thu_hoi(NGUOI_KHO)
		self.assertEqual(frappe.db.get_value("PDA Badge", NGUOI_KHO, "con_hieu_luc"), 0)

	def test_nguoi_khong_co_vai_tro_kho_bi_chan(self):
		from erpnext.warehouse_operations.vitri.the_pda import cap_the

		with self.assertRaisesRegex(frappe.ValidationError, "vai trò kho"):
			cap_the(NGUOI_NGOAI)

	def test_tai_khoan_bi_khoa_bi_chan(self):
		from erpnext.warehouse_operations.vitri.the_pda import cap_the

		frappe.db.set_value("User", NGUOI_KHO, "enabled", 0)
		with self.assertRaisesRegex(frappe.ValidationError, "đang bị khoá"):
			cap_the(NGUOI_KHO)

	def test_thu_kho_khong_tu_cap_the_cho_minh(self):
		from erpnext.warehouse_operations.vitri.the_pda import cap_the

		frappe.set_user(NGUOI_KHO)
		with self.assertRaises(frappe.PermissionError):
			cap_the(NGUOI_KHO)
```

- [ ] **Bước 2: Chạy để thấy nó ĐỎ**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local run-tests --module erpnext.warehouse_operations.tests.test_the_pda
```
Kỳ vọng: lỗi `ModuleNotFoundError: ... vitri.the_pda`.

- [ ] **Bước 3: Tạo DocType**

`erpnext/warehouse_operations/doctype/pda_badge/__init__.py`: file rỗng.

`erpnext/warehouse_operations/doctype/pda_badge/pda_badge.json`:

```json
{
 "actions": [],
 "autoname": "field:nguoi_dung",
 "creation": "2026-09-23 00:00:00.000000",
 "doctype": "DocType",
 "editable_grid": 0,
 "engine": "InnoDB",
 "field_order": ["nguoi_dung", "ho_ten", "con_hieu_luc", "cb1", "cap_luc", "lan_dung_cuoi", "thiet_bi_cuoi", "sec_kt", "ma_bam", "ghi_chu"],
 "fields": [
  {"fieldname": "nguoi_dung", "fieldtype": "Link", "label": "Người dùng", "options": "User",
   "reqd": 1, "unique": 1, "set_only_once": 1, "in_list_view": 1},
  {"fieldname": "ho_ten", "fieldtype": "Data", "label": "Họ tên", "read_only": 1, "in_list_view": 1},
  {"fieldname": "con_hieu_luc", "fieldtype": "Check", "label": "Còn hiệu lực", "default": "1", "in_list_view": 1},
  {"fieldname": "cb1", "fieldtype": "Column Break"},
  {"fieldname": "cap_luc", "fieldtype": "Datetime", "label": "Cấp lúc", "read_only": 1},
  {"fieldname": "lan_dung_cuoi", "fieldtype": "Datetime", "label": "Lần quét cuối", "read_only": 1},
  {"fieldname": "thiet_bi_cuoi", "fieldtype": "Data", "label": "Thiết bị lần cuối", "read_only": 1},
  {"fieldname": "sec_kt", "fieldtype": "Section Break"},
  {"fieldname": "ma_bam", "fieldtype": "Data", "label": "Mã băm", "read_only": 1, "hidden": 1, "no_copy": 1,
   "description": "SHA-256 của mã thẻ. Máy chủ KHÔNG lưu mã gốc — mất thẻ thì cấp thẻ mới."},
  {"fieldname": "ghi_chu", "fieldtype": "Small Text", "label": "Ghi chú"}
 ],
 "index_web_pages_for_search": 0,
 "links": [],
 "modified": "2026-09-23 00:00:00.000000",
 "modified_by": "Administrator",
 "module": "Warehouse Operations",
 "name": "PDA Badge",
 "owner": "Administrator",
 "permissions": [
  {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "report": 1, "export": 1},
  {"role": "Stock Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "report": 1, "export": 1}
 ],
 "sort_field": "modified",
 "sort_order": "DESC",
 "states": [],
 "track_changes": 1
}
```

`erpnext/warehouse_operations/doctype/pda_badge/pda_badge.py`:

```python
"""Thẻ PDA của một người dùng. Luật nghiệp vụ nằm ở `vitri/the_pda.py`;
ở đây chỉ là phép kiểm KHÔNG ĐƯỢC PHÉP VƯỢT dù ghi bằng đường nào."""

import frappe
from frappe import _
from frappe.model.document import Document

from erpnext.warehouse_operations.vitri.the_pda import VAI_TRO_DUOC_DUNG_THE


class PDABadge(Document):
	def validate(self):
		if not frappe.db.get_value("User", self.nguoi_dung, "enabled"):
			frappe.throw(_("Tài khoản {0} đang bị khoá — không cấp thẻ PDA được.").format(self.nguoi_dung))
		if not (VAI_TRO_DUOC_DUNG_THE & set(frappe.get_roles(self.nguoi_dung))):
			frappe.throw(
				_(
					"{0} không có vai trò kho nào nên thẻ PDA sẽ không mở được màn hình nào. "
					"Cấp vai trò Stock User trước, rồi cấp thẻ."
				).format(self.nguoi_dung)
			)
		self.ho_ten = frappe.db.get_value("User", self.nguoi_dung, "full_name")
```

`erpnext/warehouse_operations/doctype/pda_badge/test_pda_badge.py`:

```python
"""Frappe đòi mỗi doctype có file này (`frappe/test_runner.py` tìm theo đường dẫn).
Bài thật của thẻ PDA nằm ở `warehouse_operations/tests/test_the_pda.py` — cùng chỗ với
các bài khác của module, đúng bảng đường dẫn trong `scripts/file_structure/gate.py`."""
```

- [ ] **Bước 4: Viết `vitri/the_pda.py`**

```python
"""Thẻ PDA: cấp, thu hồi, và đăng nhập bằng thẻ (spec 2026-09-23 §5).

MỘT TẤM THẺ QUÉT ĐƯỢC LÀ MỘT CHIẾC CHÌA KHOÁ. Ai chụp được thẻ và in lại là vào
được hệ thống với quyền của chủ thẻ. File này không làm nó hết là chìa khoá — nó
làm chiếc chìa khoá đó THU HỒI ĐƯỢC, CÓ DẤU VẾT, và KHÔNG MỞ ĐƯỢC GÌ NGOÀI KHO:

- máy chủ chỉ giữ SHA-256 của mã, không giữ mã gốc (lộ CSDL không dựng lại được thẻ);
- mã gốc trả về ĐÚNG MỘT LẦN, cho đúng màn hình in;
- thu hồi là đóng luôn phiên đang mở;
- chỉ tài khoản có vai trò kho mới quét được, kiểm cả lúc cấp lẫn lúc quét;
- quét sai bị chặn tần suất theo IP và có dòng Error Log.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import frappe
from frappe import _
from frappe.sessions import clear_sessions
from frappe.utils import now_datetime

#: Bảng chữ bỏ O/0/I/1/L — thủ kho gõ tay lúc tem mờ không nhầm được.
BANG_CHU = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
DO_DAI_MA = 12
#: Ai DÙNG được thẻ. Phải bằng hợp của `VAI_TRO_DUOC_XEP` (xep.py),
#: `VAI_TRO_DUOC_LAY` (lay_hang.py) và `VAI_TRO_DUOC_TRA_CUU` (quet.py) — ba tập đó
#: hiện giống hệt nhau; nếu một ngày chúng tách ra thì sửa ở đây cho khớp.
VAI_TRO_DUOC_DUNG_THE = {"System Manager", "Stock Manager", "Stock User"}
#: Ai CẤP/THU HỒI thẻ — cùng tập `o_tem.VAI_TRO_DOI_O` đang dùng cho quyền trưởng kho.
VAI_TRO_QUAN_LY_THE = {"System Manager", "Stock Manager"}
GIO_MOT_CA = 12


def bam(ma: str) -> str:
	"""SHA-256 của mã thẻ, sau khi chuẩn hoá hoa/thường và khoảng trắng.

	Chuẩn hoá ở ĐÚNG MỘT CHỖ này: súng quét có thể gửi kèm khoảng trắng, còn người
	gõ tay hay gõ chữ thường. Hai nơi chuẩn hoá khác nhau là thẻ quét được ở màn
	này mà không quét được ở màn kia.
	"""
	return hashlib.sha256((ma or "").strip().upper().encode("utf-8")).hexdigest()


def _kiem_quyen_quan_ly() -> None:
	if not VAI_TRO_QUAN_LY_THE & set(frappe.get_roles()):
		frappe.throw(_("Chỉ trưởng kho mới cấp hoặc thu hồi thẻ PDA."), frappe.PermissionError)


@frappe.whitelist()
def cap_the(nguoi_dung: str) -> dict:
	"""Cấp thẻ mới cho `nguoi_dung` (cấp lại thì thẻ cũ chết ngay).

	Trả mã gốc ĐÚNG MỘT LẦN cho màn hình in. Không có đường nào đọc lại mã đó:
	mất thẻ thì cấp thẻ khác, không "xem lại mã cũ".
	"""
	_kiem_quyen_quan_ly()
	ma = "".join(secrets.choice(BANG_CHU) for _ in range(DO_DAI_MA))
	if frappe.db.exists("PDA Badge", nguoi_dung):
		the = frappe.get_doc("PDA Badge", nguoi_dung)
	else:
		the = frappe.new_doc("PDA Badge")
		the.nguoi_dung = nguoi_dung
	the.ma_bam = bam(ma)
	the.con_hieu_luc = 1
	the.cap_luc = now_datetime()
	the.lan_dung_cuoi = None
	the.thiet_bi_cuoi = None
	the.save()
	return {"the": the.name, "ho_ten": the.ho_ten, "ma": ma, "cap_luc": str(the.cap_luc)}


@frappe.whitelist()
def thu_hoi(nguoi_dung: str) -> dict:
	"""Thu hồi thẻ: quét không vào được nữa, VÀ phiên đang mở bị đóng.

	Thiếu vế thứ hai thì một chiếc PDA đang cầm trên tay kẻ nhặt được thẻ vẫn
	làm việc bình thường tới hết ca — thu hồi mà không đuổi phiên là thu hồi nửa vời.
	`force=True` là bắt buộc: thiếu nó `clear_sessions` chỉ dọn phiên quá hạn.
	"""
	_kiem_quyen_quan_ly()
	the = frappe.get_doc("PDA Badge", nguoi_dung)
	the.con_hieu_luc = 0
	the.save()
	clear_sessions(user=nguoi_dung, force=True)
	return {"the": the.name, "con_hieu_luc": 0}
```

- [ ] **Bước 5: Migrate rồi chạy lại test**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local migrate
bench --site erptest.local run-tests --module erpnext.warehouse_operations.tests.test_the_pda
```
Kỳ vọng: 7 bài XANH.

- [ ] **Bước 6: Báo cáo** — nêu số bài xanh, các file đã tạo. **Không commit.**

---

### Task 2: Nút "Cấp thẻ & in" trên form thẻ

**Files:**
- Create: `erpnext/warehouse_operations/doctype/pda_badge/pda_badge.js`
- Modify: `erpnext/warehouse_operations/tests/test_giao_dien.py` (thêm lớp `TestNutThePda` ở cuối file)

**Interfaces:**
- Consumes: `the_pda.cap_the(nguoi_dung)` → `{the, ho_ten, ma, cap_luc}` (Task 1); `erpnext.warehouse_operations.tem_lo.in_xap(danh_sach, so_ban)` với các ô `F1…F11` (đã có, xem `tem_kien.js`).
- Produces: nhãn nút `"Cấp thẻ & in"` và `"Thu hồi thẻ"`.

- [ ] **Bước 1: Viết bài test trước**

Thêm vào cuối `erpnext/warehouse_operations/tests/test_giao_dien.py`:

```python
DUONG_DAN_JS_THE_PDA = "warehouse_operations/doctype/pda_badge/pda_badge.js"


class TestNutThePda(FrappeTestCase):
	"""Nút cấp/in thẻ PDA. Hỏng theo kiểu im lặng: đổi tên hàm máy chủ thì nút vẫn
	vẽ ra, bấm mới biết; nên khoá cả đường gọi lẫn việc nó còn `@frappe.whitelist`."""

	def _ma_js(self):
		with open(frappe.get_app_path("erpnext", *DUONG_DAN_JS_THE_PDA.split("/")), encoding="utf-8") as f:
			return f.read()

	def test_file_js_co_that(self):
		duong_dan = frappe.get_app_path("erpnext", *DUONG_DAN_JS_THE_PDA.split("/"))
		self.assertTrue(os.path.exists(duong_dan), f"thiếu file {duong_dan}")

	def test_co_hai_nhan_nut(self):
		ma = self._ma_js()
		self.assertIn("Cấp thẻ & in", ma)
		self.assertIn("Thu hồi thẻ", ma)

	def test_duong_goi_may_chu_co_that_va_duoc_whitelist(self):
		import re

		duong = set(re.findall(r"erpnext\.warehouse_operations\.vitri\.the_pda\.\w+", self._ma_js()))
		self.assertTrue(duong, "JS không còn gọi `the_pda` — mất đường cấp thẻ.")
		for d in duong:
			self.assertIn(frappe.get_attr(d), frappe.whitelisted, f"{d} mất @frappe.whitelist()")
```

- [ ] **Bước 2: Chạy để thấy ĐỎ**

```bash
bench --site erptest.local run-tests --module erpnext.warehouse_operations.tests.test_giao_dien
```
Kỳ vọng: `test_file_js_co_that` đỏ ("thiếu file …/pda_badge.js").

- [ ] **Bước 3: Viết `pda_badge.js`**

```javascript
// Cấp và in thẻ PDA.
//
// MÃ THẺ CHỈ TỒN TẠI TRONG MỘT NHỊP: `cap_the` trả mã gốc đúng một lần, màn hình
// này đẩy thẳng sang cửa sổ in rồi quên. Không lưu vào `frm.doc`, không show_alert,
// không console.log — mã nằm lại ở đâu là ở đó thành một bản sao chìa khoá.
//
// Tem in bằng ĐÚNG khuôn tem 50×30 đang chạy (`tem_lo.in_xap`, các ô F1…F11) —
// cùng cách tem kiện đã làm 22/09. Mã vạch Code128, KHÔNG dùng QR: súng quét laser
// 1D của kho không đọc được mã hai chiều.

const DUONG_NAP_TEM = [
	"/assets/erpnext/js/warehouse_operations/tem_vi_tri.js",
	"/assets/erpnext/js/warehouse_operations/tem_lo.js",
];
const API_THE = "erpnext.warehouse_operations.vitri.the_pda.";

frappe.ui.form.on("PDA Badge", {
	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(__("Cấp thẻ & in"), () => cap_va_in(frm));
		if (frm.doc.con_hieu_luc) {
			frm.add_custom_button(__("Thu hồi thẻ"), () => thu_hoi(frm));
		}
	},
});

function cap_va_in(frm) {
	frappe.xcall(API_THE + "cap_the", { nguoi_dung: frm.doc.nguoi_dung }).then((kq) => {
		if (!kq || !kq.ma) return;
		frappe.require(DUONG_NAP_TEM, () => {
			const mo_duoc = erpnext.warehouse_operations.tem_lo.in_xap([
				{
					F1: kq.ho_ten || kq.the,
					F2: kq.the,
					F3: __("THẺ PDA — KHO"),
					F4: "",
					F5: frappe.datetime.str_to_user(kq.cap_luc),
					F6: "",
					F7: "",
					F8: "",
					F9: "PDA",
					F10: kq.ma,
					F11: kq.ma,
				},
			]);
			if (!mo_duoc) {
				// Cửa sổ in bị chặn mà thẻ ĐÃ được cấp: mã cũ đã chết, mã mới thì không in
				// ra được và không đọc lại được. Nói thẳng việc phải làm: cho phép pop-up
				// rồi bấm "Cấp thẻ & in" LẦN NỮA (cấp lại lần nữa là chuyện thường).
				frappe.msgprint({
					title: __("Trình duyệt chặn cửa sổ in"),
					message: __(
						"Thẻ đã được cấp nhưng chưa in ra được, và mã không xem lại được. "
							+ "Cho phép pop-up cho trang này rồi bấm 'Cấp thẻ & in' một lần nữa."
					),
					indicator: "red",
				});
			}
			frm.reload_doc();
		});
	});
}

function thu_hoi(frm) {
	const d = new frappe.ui.Dialog({
		title: __("Thu hồi thẻ của {0}", [frm.doc.ho_ten || frm.doc.nguoi_dung]),
		primary_action_label: __("Thu hồi"),
		primary_action: () => {
			d.hide();
			frappe.xcall(API_THE + "thu_hoi", { nguoi_dung: frm.doc.nguoi_dung }).then(() => {
				frappe.show_alert({ message: __("Đã thu hồi thẻ và đóng phiên đang mở."), indicator: "orange" });
				frm.reload_doc();
			});
		},
		secondary_action_label: __("Không"),
		secondary_action: () => d.hide(),
	});
	d.$body.append(
		`<p>${__("Thẻ hiện tại sẽ ngừng hoạt động ngay và phiên đang mở trên PDA bị đóng.")}</p>`
	);
	d.show();
}
```

- [ ] **Bước 4: Chạy lại test**

```bash
bench --site erptest.local clear-cache
bench --site erptest.local run-tests --module erpnext.warehouse_operations.tests.test_giao_dien
```
Kỳ vọng: XANH, tổng số bài tăng 3.

- [ ] **Bước 5: Báo cáo.** Không commit.

---

### Task 3: Đăng nhập bằng thẻ — endpoint và trang `/pda`

**Files:**
- Modify: `erpnext/warehouse_operations/vitri/the_pda.py` (thêm `dang_nhap_bang_the`)
- Create: `erpnext/www/pda.py`
- Create: `erpnext/www/pda.html`
- Modify: `erpnext/warehouse_operations/tests/test_the_pda.py` (thêm lớp `TestDangNhapBangThe`)

**Interfaces:**
- Consumes: `bam`, `cap_the`, `thu_hoi`, `VAI_TRO_DUOC_DUNG_THE`, `GIO_MOT_CA` (Task 1).
- Produces: `the_pda.dang_nhap_bang_the(ma: str) -> dict` trả `{"di_toi": "/app/pda-home"}`; trang web `/pda`.

- [ ] **Bước 1: Viết bài test trước**

Thêm vào `erpnext/warehouse_operations/tests/test_the_pda.py`:

```python
class TestDangNhapBangThe(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.savepoint(DIEM_TEST)
		_nguoi(NGUOI_KHO, ["Stock User"])

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point=DIEM_TEST)

	def _ma(self):
		from erpnext.warehouse_operations.vitri.the_pda import cap_the

		return cap_the(NGUOI_KHO)["ma"]

	def test_quet_dung_thi_dang_nhap_dung_nguoi(self):
		from erpnext.warehouse_operations.vitri.the_pda import dang_nhap_bang_the

		ma = self._ma()
		frappe.set_user("Guest")
		kq = dang_nhap_bang_the(ma)
		self.assertEqual(kq["di_toi"], "/app/pda-home")
		self.assertEqual(frappe.session.user, NGUOI_KHO)

	def test_phien_het_sau_12_tieng(self):
		from datetime import datetime, timedelta, timezone

		from erpnext.warehouse_operations.vitri.the_pda import GIO_MOT_CA, dang_nhap_bang_the

		ma = self._ma()
		frappe.set_user("Guest")
		dang_nhap_bang_the(ma)
		het = datetime.fromisoformat(frappe.local.session_obj.data.data.get("session_end"))
		cach = het - datetime.now(timezone.utc)
		self.assertAlmostEqual(cach.total_seconds(), GIO_MOT_CA * 3600, delta=120)

	def test_ma_sai_bi_chan_bang_mot_cau_bao(self):
		from erpnext.warehouse_operations.vitri.the_pda import dang_nhap_bang_the

		self._ma()
		frappe.set_user("Guest")
		with self.assertRaisesRegex(frappe.AuthenticationError, "Thẻ không dùng được"):
			dang_nhap_bang_the("ZZZZZZZZZZZZ")
		self.assertEqual(frappe.session.user, "Guest")

	def test_the_da_thu_hoi_bi_chan(self):
		from erpnext.warehouse_operations.vitri.the_pda import dang_nhap_bang_the, thu_hoi

		ma = self._ma()
		thu_hoi(NGUOI_KHO)
		frappe.set_user("Guest")
		with self.assertRaisesRegex(frappe.AuthenticationError, "Thẻ không dùng được"):
			dang_nhap_bang_the(ma)

	def test_chu_the_bi_khoa_thi_bi_chan(self):
		from erpnext.warehouse_operations.vitri.the_pda import dang_nhap_bang_the

		ma = self._ma()
		frappe.db.set_value("User", NGUOI_KHO, "enabled", 0)
		frappe.set_user("Guest")
		with self.assertRaisesRegex(frappe.AuthenticationError, "Thẻ không dùng được"):
			dang_nhap_bang_the(ma)

	def test_mat_vai_tro_kho_thi_the_cu_het_tac_dung(self):
		from erpnext.warehouse_operations.vitri.the_pda import dang_nhap_bang_the

		ma = self._ma()
		u = frappe.get_doc("User", NGUOI_KHO)
		u.roles = [r for r in u.roles if r.role not in ("Stock User", "Stock Manager")]
		u.save(ignore_permissions=True)
		frappe.set_user("Guest")
		with self.assertRaisesRegex(frappe.AuthenticationError, "Thẻ không dùng được"):
			dang_nhap_bang_the(ma)

	def test_ghi_lan_quet_cuoi(self):
		from erpnext.warehouse_operations.vitri.the_pda import dang_nhap_bang_the

		ma = self._ma()
		frappe.set_user("Guest")
		dang_nhap_bang_the(ma)
		frappe.set_user("Administrator")
		self.assertIsNotNone(frappe.db.get_value("PDA Badge", NGUOI_KHO, "lan_dung_cuoi"))
```

- [ ] **Bước 2: Chạy để thấy ĐỎ** — `ImportError: cannot import name 'dang_nhap_bang_the'`.

- [ ] **Bước 3: Viết endpoint** — thêm vào cuối `vitri/the_pda.py`:

```python
CAU_BAO_CHUNG = "Thẻ không dùng được — báo trưởng kho."


@frappe.whitelist(allow_guest=True)
@frappe.rate_limit(limit=10, seconds=60)
def dang_nhap_bang_the(ma: str) -> dict:
	"""Quét thẻ để vào phiên PDA. Gọi từ trang `/pda` (cùng nguồn với máy chủ).

	MỘT CÂU BÁO CHO MỌI CA HỎNG (không thấy thẻ / thẻ thu hồi / tài khoản khoá /
	mất vai trò kho): phân biệt ra là nói cho người đang dò biết mã nào có thật.
	Chi tiết thật nằm ở Error Log, chỗ chỉ trưởng kho đọc.

	`@frappe.rate_limit` mặc định `ip_based=True` → 10 lần/phút cho mỗi IP.
	"""
	the = frappe.db.get_value(
		"PDA Badge", {"ma_bam": bam(ma)}, ["name", "nguoi_dung", "con_hieu_luc"], as_dict=True
	)
	ly_do = None
	if not the:
		ly_do = "khong co the nao khop"
	elif not the.con_hieu_luc:
		ly_do = f"the cua {the.nguoi_dung} da thu hoi"
	elif not frappe.db.get_value("User", the.nguoi_dung, "enabled"):
		ly_do = f"tai khoan {the.nguoi_dung} bi khoa"
	elif not (VAI_TRO_DUOC_DUNG_THE & set(frappe.get_roles(the.nguoi_dung))):
		ly_do = f"{the.nguoi_dung} khong con vai tro kho"

	if ly_do:
		frappe.log_error(
			title="vi_tri_kho: the_pda sai ma",
			message=f"{ly_do}; ip={frappe.local.request_ip}",
		)
		frappe.throw(_(CAU_BAO_CHUNG), frappe.AuthenticationError)

	het_ca = (datetime.now(timezone.utc) + timedelta(hours=GIO_MOT_CA)).isoformat()
	# Cùng đường mà `frappe/www/login.py::login_via_key` dùng cho đăng nhập bằng
	# liên kết email — cookie phiên được đặt vào phản hồi của chính lời gọi này.
	frappe.local.login_manager.login_as(the.nguoi_dung, session_end=het_ca)

	frappe.db.set_value(
		"PDA Badge",
		the.name,
		{
			"lan_dung_cuoi": now_datetime(),
			"thiet_bi_cuoi": (frappe.get_request_header("User-Agent") or "")[:140],
		},
		update_modified=False,
	)
	return {"di_toi": "/app/pda-home"}
```

- [ ] **Bước 4: Chạy lại test** — 7 bài mới phải XANH:

```bash
bench --site erptest.local run-tests --module erpnext.warehouse_operations.tests.test_the_pda
```

- [ ] **Bước 5: Viết trang `/pda`**

`erpnext/www/pda.py`:

```python
"""Trang quét thẻ PDA — màn hình đầu tiên app mở ra.

Là trang WEBSITE chứ không phải Desk page: người chưa đăng nhập không mở được
Desk. Và nó phải nằm TRÊN MÁY CHỦ (không gói trong app) vì phiên Frappe là
cookie: trang gói trong app chạy ở nguồn khác, cookie không đặt và không gửi
kèm được — xem spec §3.
"""

import frappe

no_cache = 1


def get_context(context):
	if frappe.session.user != "Guest":
		frappe.local.flags.redirect_location = "/app/pda-home"
		raise frappe.Redirect
	context.no_header = 1
	context.no_breadcrumbs = 1
	return context
```

`erpnext/www/pda.html`:

```html
{% extends "templates/web.html" %}

{% block title %}{{ _("Quét thẻ PDA") }}{% endblock %}

{% block page_content %}
<div class="pda-the">
	<h1>{{ _("Quét thẻ nhân viên") }}</h1>
	<p class="pda-mo">{{ _("Bắn mã vạch trên thẻ. Thẻ mờ thì bấm Gõ tay.") }}</p>
	<input id="pda-ma" type="text" inputmode="none" autocomplete="off" autocorrect="off"
		autocapitalize="characters" spellcheck="false" />
	<button type="button" id="pda-go-tay" class="btn btn-default">{{ _("Gõ tay") }}</button>
	<div id="pda-bao" class="pda-bao"></div>
</div>

<style>
	.pda-the { max-width: 520px; margin: 12vh auto; padding: 0 16px; text-align: center; }
	.pda-the h1 { font-size: 22px; margin-bottom: 4px; }
	.pda-mo { color: var(--text-muted); }
	#pda-ma { width: 100%; height: 56px; font-size: 22px; text-align: center; letter-spacing: 2px;
		font-family: var(--font-stack-monospace, monospace); margin: 16px 0 8px; }
	.pda-bao { min-height: 48px; padding: 8px; font-weight: 600; }
	.pda-bao.loi { color: #c0392b; }
</style>

<script>
(function () {
	const o = document.getElementById("pda-ma");
	const bao = document.getElementById("pda-bao");
	let dang_gui = false;

	// Giữ focus như các trang PDA khác: súng quét gõ vào ô đang focus rồi gửi Enter.
	// `inputmode="none"` giữ focus mà KHÔNG bật bàn phím ảo che nửa màn hình.
	const giu_focus = () => o.focus({ preventScroll: true });
	giu_focus();
	document.addEventListener("click", (ev) => {
		if (ev.target.id !== "pda-go-tay") giu_focus();
	});
	document.getElementById("pda-go-tay").addEventListener("click", () => {
		o.setAttribute("inputmode", "text");
		giu_focus();
	});

	o.addEventListener("keydown", (ev) => {
		if (ev.key !== "Enter" && ev.key !== "Tab") return;
		ev.preventDefault();
		gui();
	});

	function gui() {
		const ma = (o.value || "").trim();
		if (!ma || dang_gui) return;
		dang_gui = true;
		bao.className = "pda-bao";
		bao.textContent = "Đang kiểm thẻ…";
		// Phiên Frappe là cookie: gọi CÙNG NGUỒN với `credentials: "same-origin"` thì
		// cookie phiên do phản hồi đặt ra được giữ lại đúng như trên trình duyệt.
		fetch("/api/method/erpnext.warehouse_operations.vitri.the_pda.dang_nhap_bang_the", {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			credentials: "same-origin",
			body: JSON.stringify({ ma: ma }),
		})
			.then((r) => r.json().then((j) => ({ ok: r.ok, j: j })))
			.then(({ ok, j }) => {
				if (ok && j.message && j.message.di_toi) {
					window.location.href = j.message.di_toi;
					return;
				}
				hong(loi_tu(j));
			})
			.catch(() => hong("Không nối được máy chủ. Kiểm tra wifi rồi quét lại."));
	}

	function loi_tu(j) {
		try {
			const ds = JSON.parse(j._server_messages || "[]");
			if (ds.length) return JSON.parse(ds[0]).message;
		} catch (e) {
			// Không phân tích được thì dùng câu chung bên dưới.
		}
		return "Thẻ không dùng được — báo trưởng kho.";
	}

	function hong(cau) {
		dang_gui = false;
		o.value = "";
		bao.className = "pda-bao loi";
		bao.textContent = cau;
		giu_focus();
	}
})();
</script>
{% endblock %}
```

- [ ] **Bước 6: Thử bằng Playwright trên erptest**

Dựng dữ liệu: cấp thẻ cho một tài khoản Stock User thật rồi chạy kịch bản: mở `http://192.168.61.129:8003/pda` (Host: erptest.local), gõ mã vào ô rồi Enter, kỳ vọng nhảy sang `/app/pda-home` (Task 4 chưa có thì kỳ vọng URL đích đúng, kể cả trang báo 404), và `frappe.session.user` đúng người. Sau đó thu hồi thẻ, quét lại, kỳ vọng thấy câu "Thẻ không dùng được". Hoàn nguyên: thu hồi + xoá `PDA Badge` vừa tạo.

- [ ] **Bước 7: Báo cáo.** Không commit.

---

### Task 4: Trang `pda-home` — menu bốn nút

**Files:**
- Create: `erpnext/warehouse_operations/page/pda_home/__init__.py` (rỗng)
- Create: `erpnext/warehouse_operations/page/pda_home/pda_home.json`
- Create: `erpnext/warehouse_operations/page/pda_home/pda_home.js`
- Create: `erpnext/warehouse_operations/page/pda_home/pda_home.css`
- Modify: `erpnext/warehouse_operations/tests/test_giao_dien.py` (thêm `TestTrangPdaHome`)

**Interfaces:**
- Consumes: các route Desk sẵn có `xep-hang-pda`, `lay-hang-pda`, `quet-ma-tra-cuu`, `dat-o-hang-loat`.
- Produces: route `pda-home`.

- [ ] **Bước 1: Viết bài test trước** — thêm vào `test_giao_dien.py`:

```python
class TestTrangPdaHome(FrappeTestCase):
	"""Menu của app PDA. Trang trỏ sai route thì Frappe vẫn dựng trang, bấm vào ra
	trang trắng — đúng hạng hỏng im lặng cả file này sinh ra để bắt."""

	def test_trang_ton_tai_thuoc_module(self):
		self.assertEqual(frappe.db.get_value("Page", "pda-home", "module"), TEN_MODULE)

	def test_dung_ba_vai_tro_kho(self):
		vai_tro = set(frappe.get_all("Page Role", filters={"parent": "pda-home"}, pluck="role"))
		self.assertEqual(vai_tro, {"System Manager", "Stock Manager", "Stock User"})

	def test_bon_route_trong_menu_deu_co_that(self):
		import re

		duong_dan = frappe.get_app_path(
			"erpnext", "warehouse_operations", "page", "pda_home", "pda_home.js"
		)
		with open(duong_dan, encoding="utf-8") as f:
			ma_js = f.read()
		route = set(re.findall(r'route:\s*"([a-z0-9-]+)"', ma_js))
		self.assertEqual(
			route, {"xep-hang-pda", "lay-hang-pda", "quet-ma-tra-cuu", "dat-o-hang-loat"}
		)
		for r in route:
			self.assertTrue(frappe.db.exists("Page", r), f"route {r} không có Page nào")
```

- [ ] **Bước 2: Chạy để thấy ĐỎ** — `pda-home` chưa tồn tại.

- [ ] **Bước 3: Tạo trang**

`pda_home.json`:

```json
{
 "content": null,
 "creation": "2026-09-23 00:00:00",
 "docstatus": 0,
 "doctype": "Page",
 "icon": "assets",
 "idx": 0,
 "modified": "2026-09-23 00:00:00.000000",
 "modified_by": "Administrator",
 "module": "Warehouse Operations",
 "name": "pda-home",
 "owner": "Administrator",
 "page_name": "pda-home",
 "roles": [
  {"role": "System Manager"},
  {"role": "Stock Manager"},
  {"role": "Stock User"}
 ],
 "script": null,
 "standard": "Yes",
 "style": null,
 "system_page": 0,
 "title": "Kho — PDA"
}
```

`pda_home.js`:

```javascript
// Menu của app PDA: bốn việc, nút to, không có gì khác trên màn hình.
//
// Nằm trên MÁY CHỦ chứ không gói trong APK (spec §3): sửa menu không phải cài lại
// app, và mở được cả từ trình duyệt máy tính để đối chiếu khi có sự cố.

frappe.pages["pda-home"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Kho — PDA"), single_column: true });
	const viec = [
		{ route: "xep-hang-pda", nhan: __("Xếp hàng vào ô"), mo: __("Quét tem lô, quét tem ô") },
		{ route: "lay-hang-pda", nhan: __("Lấy hàng"), mo: __("Theo phiếu giao: lô, ô, đơn vị, kiện") },
		{ route: "quet-ma-tra-cuu", nhan: __("Quét mã tra cứu"), mo: __("Tem lô hoặc tem ô ra thông tin") },
		{
			route: "dat-o-hang-loat",
			nhan: __("Đặt ô trên tem"),
			mo: __("Bảng rộng — nên làm trên máy tính"),
		},
	];
	const e = frappe.utils.escape_html;
	$(`
		<div class="ph">
			<div class="ph-nguoi">${e(frappe.session.user_fullname || frappe.session.user)}</div>
			<div class="ph-ds">
				${viec
					.map(
						(v) => `
					<button type="button" class="ph-nut" data-route="${e(v.route)}">
						<span class="ph-nhan">${e(v.nhan)}</span>
						<span class="ph-mo">${e(v.mo)}</span>
					</button>`
					)
					.join("")}
			</div>
			<button type="button" class="ph-thoat">${__("Đăng xuất")}</button>
		</div>
	`).appendTo(page.main);

	$(page.main).on("click", ".ph-nut", (ev) => frappe.set_route($(ev.currentTarget).attr("data-route")));
	$(page.main).on("click", ".ph-thoat", () => {
		// `/api/method/logout` xoá phiên rồi đưa về `/login`; vỏ app thấy `/login`
		// thì tự chuyển sang `/pda` để quét thẻ lại (xem `pda_app/www/index.html`).
		window.location.href = "/api/method/logout";
	});
};
```

`pda_home.css`:

```css
/* Trang này chạy trên màn PDA 4 inch: nút cao 72px, chạm bằng ngón cái có găng. */
.ph { max-width: 560px; margin: 0 auto; padding: 8px 12px 24px; }
.ph-nguoi { text-align: center; color: var(--text-muted); margin-bottom: 12px; }
.ph-ds { display: flex; flex-direction: column; gap: 12px; }
.ph-nut {
	min-height: 72px;
	border: 1px solid var(--border-color);
	border-radius: 14px;
	background: var(--control-bg);
	color: var(--text-color);
	text-align: left;
	padding: 10px 16px;
}
.ph-nhan { display: block; font-size: 18px; font-weight: 700; }
.ph-mo { display: block; font-size: 13px; color: var(--text-muted); }
.ph-thoat {
	display: block;
	width: 100%;
	margin-top: 24px;
	min-height: 48px;
	border: 0;
	border-radius: 12px;
	background: var(--control-bg);
	color: var(--text-muted);
}
```

- [ ] **Bước 4: Migrate, chạy lại test**

```bash
bench --site erptest.local migrate
bench --site erptest.local run-tests --module erpnext.warehouse_operations.tests.test_giao_dien
```
Kỳ vọng XANH (3 bài mới).

- [ ] **Bước 5: Thử bằng Playwright** — đăng nhập bằng thẻ ở `/pda` rồi kỳ vọng dừng ở `/app/pda-home`, bấm nút "Lấy hàng" nhảy đúng `/app/lay-hang-pda`. Hoàn nguyên dữ liệu thử.

- [ ] **Bước 6: Báo cáo.** Không commit.

---

### Task 5: Vỏ app Capacitor

**Files:**
- Create: `pda_app/package.json`
- Create: `pda_app/capacitor.config.json`
- Create: `pda_app/www/index.html`
- Create: `pda_app/README.md`
- Create: `pda_app/.gitignore`
- Modify: `scripts/file_structure/gate.py` (thêm một dòng vào `RULES`)
- Modify: `.gitignore` gốc repo (bỏ qua `pda_app/node_modules`, `pda_app/android/build`…)

**Interfaces:**
- Consumes: trang `/pda` (Task 3), `/app/pda-home` (Task 4).
- Produces: thư mục dự án Capacitor dựng được APK ở Task 6; khoá `localStorage["pda_may_chu"]` giữ địa chỉ máy chủ.

- [ ] **Bước 1: Mở đường cho thư mục mới trong cổng cấu trúc file**

Thêm vào `RULES` của `scripts/file_structure/gate.py`, đặt **ngay trước** dòng `("repo-root", …)`:

```python
	# Vỏ app PDA (Capacitor) — spec 2026-09-23. Mã nguồn app nằm trong kho này theo
	# quyết định của chủ đầu tư: một nhánh, một PR, không lạc khỏi nghiệp vụ nó phục vụ.
	("pda-app", r"pda_app/(package\.json|capacitor\.config\.json|README\.md|\.gitignore|www/.+|android/.+)"),
```

Kiểm:

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/erpnext
python3 -m scripts.file_structure --audit
```
Kỳ vọng: **0 vi phạm**.

- [ ] **Bước 2: Dựng dự án Capacitor**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/erpnext/pda_app
npm init -y
npm install @capacitor/core@6 @capacitor/cli@6 @capacitor/android@6
```

`pda_app/package.json` (sửa lại sau khi `npm init`):

```json
{
  "name": "miyano-pda",
  "version": "1.0.0",
  "private": true,
  "description": "Vỏ Android cho các màn hình kho PDA của Miyano ERP",
  "scripts": {
    "them-android": "cap add android",
    "dong-bo": "cap sync android",
    "mo-android": "cap open android"
  },
  "dependencies": {
    "@capacitor/android": "^6.0.0",
    "@capacitor/core": "^6.0.0"
  },
  "devDependencies": {
    "@capacitor/cli": "^6.0.0"
  }
}
```

`pda_app/capacitor.config.json`:

```json
{
  "appId": "vn.com.miyano.pda",
  "appName": "Miyano PDA",
  "webDir": "www",
  "android": {
    "allowMixedContent": true
  },
  "server": {
    "androidScheme": "https",
    "allowNavigation": ["192.168.*", "10.*", "erp.miyano.com.vn"]
  }
}
```

> `allowNavigation` là **hàng rào**: WebView chỉ đi tới được các host này; gõ nhầm địa chỉ lạ thì Capacitor mở bằng trình duyệt hệ thống chứ không nạp trong app. Thêm tên miền thật vào đây khi có.

- [ ] **Bước 3: Viết màn hình chọn máy chủ (`pda_app/www/index.html`)**

```html
<!doctype html>
<html lang="vi">
<head>
	<meta charset="utf-8" />
	<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no" />
	<title>Miyano PDA</title>
	<style>
		body { font-family: system-ui, sans-serif; margin: 0; padding: 24px; background: #111; color: #eee; }
		h1 { font-size: 20px; }
		input { width: 100%; height: 52px; font-size: 18px; padding: 0 12px; box-sizing: border-box; }
		button { width: 100%; height: 52px; font-size: 17px; margin-top: 12px; border: 0; border-radius: 10px; }
		.chinh { background: #2d7ff9; color: #fff; }
		.phu { background: #333; color: #eee; }
		.bao { min-height: 44px; margin-top: 12px; }
		.loi { color: #ff8a80; }
	</style>
</head>
<body>
	<h1>Miyano PDA</h1>
	<div id="dang-noi" hidden>
		<p id="chu-noi"></p>
		<button class="phu" id="doi">Đổi máy chủ</button>
	</div>
	<div id="khai" hidden>
		<p>Địa chỉ máy chủ:</p>
		<input id="dia-chi" type="url" inputmode="url" autocapitalize="none" autocomplete="off"
			placeholder="http://192.168.61.129:8003" />
		<button class="chinh" id="luu">Kiểm tra &amp; lưu</button>
	</div>
	<div class="bao" id="bao"></div>

<script>
// Vỏ app chỉ làm đúng ba việc: nhớ địa chỉ máy chủ, thử xem có nối được không,
// rồi giao màn hình cho máy chủ. Mọi nghiệp vụ nằm trên máy chủ (spec §3).
//
// VÌ SAO PING TRƯỚC KHI CHUYỂN: mất wifi mà chuyển thẳng thì người dùng nhìn
// thấy trang lỗi của Chrome, không có đường nào quay lại màn này để đổi máy chủ.
// Ping trước thì lỗi mạng hiện ở đây, kèm nút Thử lại và nút Đổi máy chủ.
(function () {
	var KHOA = "pda_may_chu";
	var MAC_DINH = "http://192.168.61.129:8003";
	var bao = document.getElementById("bao");

	function chuan_hoa(u) {
		u = (u || "").trim().replace(/\/+$/, "");
		if (!u) return "";
		if (!/^https?:\/\//i.test(u)) u = "http://" + u;
		return u;
	}

	function hien_khai(gia_tri) {
		document.getElementById("dang-noi").hidden = true;
		document.getElementById("khai").hidden = false;
		document.getElementById("dia-chi").value = gia_tri || MAC_DINH;
	}

	function ping(u) {
		return new Promise(function (xong) {
			var bo = new AbortController();
			var hen = setTimeout(function () { bo.abort(); }, 6000);
			fetch(u + "/api/method/ping", { signal: bo.signal, credentials: "omit" })
				.then(function (r) { clearTimeout(hen); xong(r.ok); })
				.catch(function () { clearTimeout(hen); xong(false); });
		});
	}

	function di(u) {
		window.location.href = u + "/pda";
	}

	function thu(u, tu_dong) {
		bao.className = "bao";
		bao.textContent = "Đang nối " + u + " …";
		document.getElementById("dang-noi").hidden = false;
		document.getElementById("chu-noi").textContent = "Máy chủ: " + u;
		ping(u).then(function (duoc) {
			if (duoc) {
				localStorage.setItem(KHOA, u);
				di(u);
				return;
			}
			bao.className = "bao loi";
			bao.textContent = "Không nối được máy chủ. Kiểm tra wifi, rồi bấm Kiểm tra lại.";
			if (tu_dong) hien_khai(u);
		});
	}

	document.getElementById("luu").addEventListener("click", function () {
		var u = chuan_hoa(document.getElementById("dia-chi").value);
		if (!u) { bao.className = "bao loi"; bao.textContent = "Chưa nhập địa chỉ."; return; }
		thu(u, false);
	});
	document.getElementById("doi").addEventListener("click", function () {
		hien_khai(localStorage.getItem(KHOA) || MAC_DINH);
	});

	var da_luu = localStorage.getItem(KHOA);
	if (da_luu) thu(da_luu, true);
	else hien_khai(MAC_DINH);
})();
</script>
</body>
</html>
```

- [ ] **Bước 4: Thêm nền tảng Android và khai ngoại lệ HTTP**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/erpnext/pda_app
npx cap add android
```

Tạo `pda_app/android/app/src/main/res/xml/network_security_config.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<!-- Android 9+ cấm HTTP không mã hoá. Máy chủ hiện chạy trong mạng nội bộ theo IP,
     nên mở ngoại lệ ĐÚNG cho dải nội bộ; mọi địa chỉ khác vẫn bắt buộc HTTPS. -->
<network-security-config>
	<domain-config cleartextTrafficPermitted="true">
		<domain includeSubdomains="false">192.168.61.129</domain>
		<domain includeSubdomains="false">10.0.2.2</domain>
	</domain-config>
	<base-config cleartextTrafficPermitted="false" />
</network-security-config>
```

Trong `pda_app/android/app/src/main/AndroidManifest.xml`, thẻ `<application>` thêm hai thuộc tính (nếu `networkSecurityConfig` đã có thì giữ nguyên):

```xml
android:networkSecurityConfig="@xml/network_security_config"
android:screenOrientation="portrait"
```

và thẻ `<activity>` của `MainActivity` thêm `android:screenOrientation="portrait"`.

- [ ] **Bước 5: `.gitignore` cho thư mục app**

`pda_app/.gitignore`:

```gitignore
node_modules/
android/build/
android/app/build/
android/.gradle/
android/local.properties
android/app/release/
*.apk
*.keystore
```

- [ ] **Bước 6: Kiểm lại cổng cấu trúc file**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/erpnext
python3 -m scripts.file_structure --audit
```
Kỳ vọng 0 vi phạm. Nếu báo vi phạm cho file Android nào đó (vd. `android/gradlew`), mở rộng regex ở Bước 1 cho đúng file đó rồi chạy lại.

- [ ] **Bước 7: Báo cáo.** Không commit.

---

### Task 6: Dựng APK, bảng kiểm tay, tài liệu

**Files:**
- Modify: `pda_app/README.md` (cách dựng lại APK)
- Create: `docs/warehouse_operations/HDSD-app-pda.md`
- Modify: `docs/warehouse_operations/HDSD-quan-ly-vi-tri-kho.md` (thêm mục 17 trỏ sang tài liệu app)

**Interfaces:**
- Consumes: toàn bộ Task 1–5.
- Produces: file `pda_app/android/app/build/outputs/apk/release/app-release.apk`.

- [ ] **Bước 1: Dọn ổ đĩa** (đang 92%, cần ~6 GB cho SDK + Gradle)

```bash
yarn cache clean || true
rm -rf ~/.cache/uv ~/.cache/pip ~/.cache/google-chrome
df -h /home | tail -1
```
Kỳ vọng còn trống ≥ 12 GB. **Giữ nguyên `~/.cache/ms-playwright`** — bộ kiểm thử trình duyệt đang dùng.

- [ ] **Bước 2: Cài JDK 17 (không cần sudo)**

```bash
mkdir -p ~/opt && cd ~/opt
curl -L -o jdk17.tar.gz "https://api.adoptium.net/v3/binary/latest/17/ga/linux/x64/jdk/hotspot/normal/eclipse"
tar xzf jdk17.tar.gz && rm jdk17.tar.gz
mv jdk-17* jdk17
~/opt/jdk17/bin/java -version
```
Kỳ vọng in ra `openjdk version "17…"`.

- [ ] **Bước 3: Cài Android SDK (chỉ đúng gói cần)**

```bash
mkdir -p ~/opt/android-sdk/cmdline-tools && cd ~/opt/android-sdk/cmdline-tools
curl -L -o tools.zip https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip
unzip -q tools.zip && rm tools.zip && mv cmdline-tools latest
export JAVA_HOME=~/opt/jdk17
export ANDROID_HOME=~/opt/android-sdk
yes | ~/opt/android-sdk/cmdline-tools/latest/bin/sdkmanager --licenses
~/opt/android-sdk/cmdline-tools/latest/bin/sdkmanager "platform-tools" "platforms;android-34" "build-tools;34.0.0"
du -sh ~/opt/android-sdk
```
**Không cài `emulator` và `system-images`** — mỗi thứ vài GB và máy cũng không đủ RAM chạy.

- [ ] **Bước 4: Tạo khoá ký (để NGOÀI kho mã nguồn)**

```bash
mkdir -p ~/keys
~/opt/jdk17/bin/keytool -genkeypair -v -keystore ~/keys/miyano-pda.keystore \
  -alias miyano-pda -keyalg RSA -keysize 2048 -validity 10000
```
Ghi mật khẩu vào nơi chủ đầu tư giữ. **Mất khoá này là không cập nhật được app đã cài** (Android từ chối APK ký bằng khoá khác) — phải gỡ rồi cài lại.

Tạo `pda_app/android/keystore.properties` (đã nằm trong `.gitignore` của Task 5 — kiểm lại, nếu chưa có thì thêm dòng `android/keystore.properties`):

```properties
storeFile=/home/hoangvietyeuem/keys/miyano-pda.keystore
storePassword=<mật khẩu>
keyAlias=miyano-pda
keyPassword=<mật khẩu>
```

Trong `pda_app/android/app/build.gradle`, thêm vào trước `android {`:

```gradle
def keystoreProperties = new Properties()
def keystorePropertiesFile = rootProject.file("keystore.properties")
if (keystorePropertiesFile.exists()) {
    keystoreProperties.load(new FileInputStream(keystorePropertiesFile))
}
```

và trong khối `android { … }`:

```gradle
    signingConfigs {
        release {
            if (keystoreProperties['storeFile']) {
                storeFile file(keystoreProperties['storeFile'])
                storePassword keystoreProperties['storePassword']
                keyAlias keystoreProperties['keyAlias']
                keyPassword keystoreProperties['keyPassword']
            }
        }
    }
    buildTypes {
        release {
            signingConfig signingConfigs.release
            minifyEnabled false
        }
    }
```

- [ ] **Bước 5: Dựng APK**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/erpnext/pda_app
export JAVA_HOME=~/opt/jdk17
export ANDROID_HOME=~/opt/android-sdk
npx cap sync android
cd android && ./gradlew assembleRelease
ls -lh app/build/outputs/apk/release/app-release.apk
```
Kỳ vọng: có file APK (~4–6 MB).

- [ ] **Bước 6: Viết `pda_app/README.md`**

Nội dung bắt buộc có: yêu cầu môi trường (JDK 17, Android SDK 34, Node 18); đúng bốn lệnh dựng lại APK; chỗ để khoá ký và lời cảnh báo mất khoá; cách đổi địa chỉ máy chủ mặc định (`www/index.html`, hằng `MAC_DINH`) và cách thêm host vào `allowNavigation`; câu nhắc "sửa nghiệp vụ trên web KHÔNG cần dựng lại APK".

- [ ] **Bước 7: Viết `docs/warehouse_operations/HDSD-app-pda.md`**

Nội dung bắt buộc có:
1. **Cấp thẻ**: mở `PDA Badge` → chọn người dùng → **Cấp thẻ & in** → dán thẻ vào bao nhựa. Mã chỉ hiện lúc in, không xem lại được.
2. **Mất thẻ**: **Thu hồi thẻ** (phiên trên máy đang cầm thẻ bị đóng ngay), rồi cấp thẻ mới.
3. **Cài app**: chép `app-release.apk` sang PDA, bật "cài từ nguồn không rõ", cài, mở, khai địa chỉ máy chủ.
4. **Dùng hằng ngày**: mở app → quét thẻ → chọn việc. Hết 12 tiếng thì quét thẻ lại.
5. **Đổi máy chủ**: mở app, trong lúc đang nối bấm **Đổi máy chủ**.
6. **Sự thật về bảo mật**: thẻ là chìa khoá, ai chụp được là vào được — bảo quản như chìa khoá kho; nghi mất thì thu hồi ngay.
7. Bảng **sự cố hay gặp**: không nối được máy chủ (kiểm wifi/địa chỉ), quét thẻ báo "Thẻ không dùng được" (hỏi trưởng kho xem thẻ còn hiệu lực), màn "Đặt ô trên tem" chật (dùng máy tính).

Thêm mục 17 vào `HDSD-quan-ly-vi-tri-kho.md` trỏ sang tài liệu trên, gồm bảng "ai làm gì với thẻ".

- [ ] **Bước 8: Bảng kiểm tay cho chủ đầu tư** (viết vào cuối `HDSD-app-pda.md`)

| # | Việc | Kỳ vọng |
|---|---|---|
| 1 | Cài APK, mở app | Hiện màn khai máy chủ, mặc định đúng địa chỉ |
| 2 | Bấm Kiểm tra & lưu | Vào thẳng màn quét thẻ |
| 3 | Quét thẻ của mình | Vào menu bốn nút, hiện đúng tên mình |
| 4 | Xếp một thùng | Quét lô, quét ô, ghi xong; mở web thấy ngay phiếu xếp |
| 5 | Lấy một phiếu giao | Quét lô, quét ô, chọn đơn vị, số kiện; web thấy ngay |
| 6 | Tắt wifi rồi mở lại app | Hiện lỗi nối máy chủ + nút Đổi máy chủ, không phải trang lỗi của Chrome |
| 7 | Thu hồi thẻ trên web khi PDA đang mở | Thao tác tiếp trên PDA bị đòi đăng nhập lại |
| 8 | Để máy qua 12 tiếng | Mở lại phải quét thẻ |

- [ ] **Bước 9: Chạy CẢ BỘ test của module**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
for m in $(ls apps/erpnext/erpnext/warehouse_operations/tests/test_*.py | xargs -n1 basename | sed 's/\.py$//'); do
  echo "$m: $(bench --site erptest.local run-tests --module erpnext.warehouse_operations.tests.$m 2>&1 | grep -E '^(OK|FAILED)|^Ran ' | tr '\n' ' ')"
done
```
Kỳ vọng: mọi module XANH, trừ `test_gan_vi_tri` (đang đỏ sẵn vì dữ liệu thật trên erptest giữ ô fixture `7A01010101` — không liên quan việc này).

- [ ] **Bước 10: Báo cáo** — đường dẫn file APK, kết quả bộ test, những gì chủ đầu tư phải tự thử (bảng kiểm), và **hỏi có commit không**.

---

## Tự soát (đã chạy khi viết kế hoạch)

- **Phủ spec:** §4 vỏ app → Task 5; §5.2–5.3 thẻ → Task 1; §5.4 in thẻ → Task 2; §5.5–5.6 đăng nhập + phiên → Task 3; §6 menu → Task 4; §7 chỗ đặt mã + cổng cấu trúc → Task 5 Bước 1; §8 dựng APK → Task 6; §10 kiểm thử → test trong từng Task + Bước 9; §11 rủi ro → tài liệu ở Task 6 Bước 7.
- **Lệch cố ý so với spec §4, đã ghi lý do:** nút Back **không** hỏi "Thoát app?" — sau khi WebView chuyển sang máy chủ thì mã JS của vỏ app không còn chạy, nên hộp hỏi bằng JS không thể tồn tại; dùng hành vi mặc định của Capacitor (Back lùi lịch sử, ở trang đầu thì thoát). Tương tự, **trang lỗi mất mạng** được thay bằng **ping trước khi chuyển** ở `www/index.html` — cùng tác dụng mà không phải viết mã Java.
- **Không có chỗ trống:** mọi bước đều có mã hoặc lệnh thật.
- **Tên hàm nhất quán:** `bam`, `cap_the`, `thu_hoi`, `dang_nhap_bang_the`, `VAI_TRO_DUOC_DUNG_THE`, `VAI_TRO_QUAN_LY_THE`, `GIO_MOT_CA`, khoá `localStorage["pda_may_chu"]` — dùng đúng một cách ở mọi Task.

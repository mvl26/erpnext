"""Static checker — reports every matrix/site inconsistency before the sync writes anything."""

from dataclasses import dataclass, field

from erpnext.access.permissions.cells import MatrixError, parse_cell
from erpnext.access.permissions.expand import expand_doctype
from erpnext.access.permissions.matrix import DocTypeEntry, Matrix
from erpnext.access.permissions.site import APPS, SiteInfo

SCOPE_TOKENS = frozenset({"o", "e", "d", "w", "pl", "c", "s", "g"})
ALLOWED_UPDATE_FIELDS = frozenset(
	{("Leave Application", "status"), ("Shift Request", "status"), ("Expense Claim", "approval_status")}
)
DRAFT = "Nháp"
REJECTED = "Từ chối"
CANCELLED = "Đã hủy"
WF_NO_CANCEL_YET = "WF-BT"
R3_EXEMPT_CODES = frozenset({"PRU"})  # Prepared Report User — companion role, always held with AM or VW


@dataclass
class Problems:
	errors: list[str] = field(default_factory=list)
	warnings: list[str] = field(default_factory=list)


class _Checker:
	def __init__(self, m: Matrix, site: SiteInfo):
		self.m = m
		self.site = site
		self.p = Problems()
		self.cells: dict[tuple[str, str], dict[int, frozenset[str]]] = {}

	def err(self, name: str, rule: str, msg: str):
		self.p.errors.append(f"{name} — {rule}: {msg}")

	def warn(self, name: str, rule: str, msg: str):
		self.p.warnings.append(f"{name} — {rule}: {msg}")

	def guard(self, name: str, fn, *args):
		"""Run one per-object check; a malformed object becomes an error line, never an exception."""
		try:
			fn(*args)
		except Exception as e:
			self.err(name, "internal", f"{type(e).__name__}: {e}")

	def cell(self, name: str, code: str, text) -> dict[int, frozenset[str]]:
		key = (name, code)
		if key not in self.cells:
			if not isinstance(text, str):
				self.err(name, "cell", f"{code}: ô perms phải là chuỗi, đang là {type(text).__name__}")
				self.cells[key] = {}
				return self.cells[key]
			try:
				self.cells[key] = parse_cell(text)
			except MatrixError as e:
				self.err(name, "cell", f"{code}: {e}")
				self.cells[key] = {}
		return self.cells[key]

	def run(self) -> Problems:
		self.guard("matrix", self.check_roles)
		self.guard("matrix", self.check_coverage)
		for name, entry in self.m.doctypes.items():
			self.guard(name, self.check_entry, name, entry)
		self.check_reports()
		self.check_workflows()
		self.check_empty_roles()
		return self.p

	# -- role codes ----------------------------------------------------------------------------

	def check_codes(self, name: str, codes, where: str):
		if not isinstance(codes, list | tuple | set | frozenset | dict):
			self.err(name, "R-CODE", f"{where} phải là danh sách mã role, đang là {type(codes).__name__}")
			return
		for code in codes:
			if not isinstance(code, str) or code not in self.m.roles:
				self.err(name, "R-CODE", f"mã role {code!r} trong {where} không có trong roles")

	def check_roles(self):
		m = self.m
		for pack, codes in m.packs.items():
			self.check_codes(pack, codes, "packs")
		for profile, items in m.role_profiles.items():
			for item in items:
				if item not in m.packs and item not in m.roles:
					self.err(profile, "R-CODE", f"{item!r} trong role_profiles không phải pack hay mã role")
		for section in ("pages", "workspaces"):
			for name, codes in getattr(m, section).items():
				self.check_codes(name, codes, section)

	# -- DocTypes ------------------------------------------------------------------------------

	def check_coverage(self):
		for name, info in self.site.doctypes.items():
			if info.app in APPS and name not in self.m.doctypes:
				self.err(name, "9.3.1", "DocType trên site chưa có trong ma trận")
		for name in self.m.doctypes:
			info = self.site.doctypes.get(name)
			if info is None:
				self.warn(name, "9.3.1", "có trong ma trận nhưng không có trên site, bỏ qua")
			elif info.app not in APPS:
				self.warn(name, "9.3.1", f"module {info.module} thuộc app {info.app}, không xử lý")

	def check_entry(self, name: str, entry: DocTypeEntry):
		info = self.site.doctypes.get(name)
		if info is None or info.app not in APPS:
			return
		if not isinstance(entry.perms, dict) or not isinstance(entry.scope, dict):
			self.err(name, "cell", "perms và scope phải là object")
			return
		self.check_codes(name, entry.perms, "perms")
		if entry.pda and entry.state != "ref_master":
			self.err(name, "G8", f"pda chỉ dùng cho ref_master, state hiện tại là {entry.state}")
		for code, scope in entry.scope.items():
			if code not in entry.perms:
				self.err(name, "scope", f"scope của {code} nhưng {code} không có ô perms")
			if not isinstance(scope, str):
				self.err(name, "scope", f"scope của {code} phải là chuỗi")
				continue
			bad = set(scope.split()) - SCOPE_TOKENS
			if bad:
				self.err(name, "scope", f"token scope không hợp lệ: {' '.join(sorted(bad))}")

		levels_by_code = {c: self.cell(name, c, t) for c, t in entry.perms.items()}
		has_submit = False
		for code, levels in levels_by_code.items():
			for level, ptypes in levels.items():
				if level == 0:
					has_submit = has_submit or "submit" in ptypes
					if not info.is_submittable:
						if ptypes & {"submit", "cancel", "amend"}:
							self.err(name, "9.3.1", f"{code} có S/X/A nhưng DocType không submittable")
					elif "delete" in ptypes:
						self.err(name, "9.3.1", f"{code} có quyền D (delete) nhưng DocType submittable")
				if info.issingle and not ptypes <= {"read", "write"}:
					self.err(name, "9.3.1", f"{code} có quyền ngoài R, W trên DocType Single")
		if (
			entry.state == "matrix"
			and info.is_submittable
			and not has_submit
			and name not in self.m.rules.get("no_submit_ok", ())
		):
			self.err(name, "9.3.1", "DocType submittable ở trạng thái matrix nhưng không role nào có S")

		if entry.state != "keep_standard":
			self.check_permlevel(name, entry, info, levels_by_code)

	def check_permlevel(self, name, entry, info, levels_by_code):
		declared: set[str] = set()
		for level, spec in entry.permlevel.items():
			if not isinstance(spec, dict):
				self.err(name, "G9", f"permlevel {level} phải là object")
				continue
			missing = [k for k in ("fields", "read", "write") if k not in spec]
			if missing:
				self.err(name, "G9", f"permlevel {level} thiếu khóa {', '.join(missing)}")
				continue
			declared.update(spec["fields"])
			self.check_codes(name, list(spec["read"]) + list(spec["write"]), f"permlevel {level}")
		for fieldname in sorted(info.high_permlevel_fields - declared):
			self.err(
				name, "G9", f"trường {fieldname} có permlevel > 0 trên site nhưng chưa khai trong permlevel"
			)

		levels = {lv for lv in entry.permlevel} | {
			lv for cl in levels_by_code.values() for lv in cl if lv > 0
		}
		for level in sorted(levels):
			spec = entry.permlevel.get(level)
			if spec is not None and not isinstance(spec, dict):
				continue
			if spec is None:
				self.err(name, "G9", f"perms có R{level}/W{level} nhưng permlevel {level} chưa khai")
				continue
			if not all(k in spec for k in ("read", "write")):
				continue
			cell_read = {c for c, cl in levels_by_code.items() if "read" in cl.get(level, ())}
			cell_write = {c for c, cl in levels_by_code.items() if "write" in cl.get(level, ())}
			want_write = set(spec["write"])
			want_read = set(spec["read"]) | want_write
			if cell_read != want_read or cell_write != want_write:
				self.err(
					name,
					"G9",
					f"ô R{level}/W{level} lệch permlevel {level}: ô đọc={sorted(cell_read)} "
					f"khai đọc={sorted(want_read)}; ô ghi={sorted(cell_write)} khai ghi={sorted(want_write)}",
				)

	# -- reports -------------------------------------------------------------------------------

	def check_reports(self):
		m = self.m
		for report, codes in m.reports.items():
			self.guard(report, self.check_report, report, codes)

	def check_report(self, report: str, codes):
		m = self.m
		self.check_codes(report, codes, "reports")
		if report not in self.site.reports:
			self.err(report, "R-REPORT", "report có trong ma trận nhưng không có trên site")
			return
		ref = self.site.reports[report]
		if not ref or not isinstance(codes, list | tuple):
			return
		entry, info = m.doctypes.get(ref), self.site.doctypes.get(ref)
		if entry is None or info is None:
			self.warn(report, "R3", f"ref_doctype {ref} không có trong ma trận, bỏ qua")
			return
		if entry.state == "keep_standard":
			self.warn(report, "R3", f"ref_doctype {ref} là keep_standard, không kiểm được")
			return
		try:
			rows = expand_doctype(m, ref, info)
		except Exception as e:  # the bad entry is reported by its own check_entry
			self.warn(report, "R3", f"không mở rộng được {ref} ({type(e).__name__}), bỏ qua")
			return
		for code in codes:
			if not isinstance(code, str) or code not in m.roles or code in R3_EXEMPT_CODES:
				continue
			names = m.role_names(code)
			if not any(r.role in names and r.permlevel == 0 and "read" in r.ptypes for r in rows):
				self.err(report, "R3", f"role {code} không có read trên ref_doctype {ref}")

	def check_empty_roles(self):
		"""11.2.E — the sync fails closed on an empty role list or a role code with no Frappe role name."""
		m = self.m
		for section in ("reports", "pages"):
			for name, codes in getattr(m, section).items():
				if isinstance(codes, list | tuple) and not codes:
					self.err(name, "11.2.E", f"{section} có danh sách role rỗng")
		for code, role in m.roles.items():
			if not role.names:
				self.err(code, "11.2.E", "mã role không có tên role Frappe nào (names rỗng)")

	# -- workflows -----------------------------------------------------------------------------

	def check_workflows(self):
		m = self.m
		for name, entry in m.doctypes.items():
			if entry.workflow and entry.workflow not in m.workflows:
				self.err(name, "9.3", f"workflow {entry.workflow} không có trong workflows")
		for code, wf in m.workflows.items():
			self.guard(code, self.check_workflow, code, wf)

	def check_workflow(self, code: str, wf):
		m = self.m
		if not isinstance(wf, dict):
			self.err(code, "9.2", "workflow phải là object")
			return
		doctypes = wf.get("doctypes")
		if not isinstance(doctypes, list) or not doctypes:
			self.err(code, "9.3", "doctypes trống hoặc không phải danh sách")
			doctypes = []
		for dt in doctypes:
			entry = m.doctypes.get(dt)
			if entry is None or entry.workflow != code:
				self.err(code, "9.3", f"{dt} nằm trong doctypes nhưng entry không khai workflow {code}")

		field_name = wf.get("workflow_state_field")
		if field_name is not None and field_name != "workflow_state":
			self.err(code, "9.2.1", f"workflow_state_field phải là workflow_state, đang là {field_name!r}")

		raw_states = wf.get("states")
		if not isinstance(raw_states, list):
			self.err(code, "9.2", "states phải là danh sách")
			raw_states = []
		states = []
		for i, s in enumerate(raw_states):
			if not isinstance(s, dict) or "state" not in s or "doc_status" not in s:
				self.err(code, "9.2", f"state #{i} thiếu khóa state/doc_status hoặc không phải object")
				continue
			states.append(s)
		by_name = {s["state"]: s for s in states}
		first = {}
		for s in states:
			first.setdefault(s["doc_status"], s["state"])
		if first.get(0) != DRAFT:
			self.err(code, "9.2.4", f"state doc_status 0 đầu tiên phải là {DRAFT}, đang là {first.get(0)!r}")
		if first.get(1) == REJECTED:
			self.err(code, "9.2.4", f"state doc_status 1 đầu tiên không được là {REJECTED}")
		draft_only = all(s["doc_status"] == 0 for s in states) and not any(
			getattr(self.site.doctypes.get(dt), "is_submittable", False) for dt in doctypes
		)
		if not draft_only and not any(s["state"] == CANCELLED and s["doc_status"] == 2 for s in states):
			msg = f"thiếu state {CANCELLED} (doc_status 2)"
			if code == WF_NO_CANCEL_YET:
				self.warn(code, "9.2.4", msg + ", miễn cho đến khi có C6")
			else:
				self.err(code, "9.2.4", msg)

		self.check_codes(code, wf.get("creators", []), "creators")
		if not wf.get("creators") and any(s["state"] == REJECTED and s["doc_status"] == 0 for s in states):
			self.warn(code, "9.3", f"creators trống — không sinh được transition Mở lại từ {REJECTED}")
		for s in states:
			uf = s.get("update_field")
			if uf:
				targets = s.get("update_doctypes") or doctypes
				for dt in sorted(set(targets) - set(doctypes)):
					self.err(code, "9.2.2", f"state {s['state']}: update_doctypes có {dt} ngoài doctypes")
				for dt in targets:
					if (dt, uf) not in ALLOWED_UPDATE_FIELDS:
						self.err(
							code, "9.2.2", f"state {s['state']}: update_field {uf} không được phép trên {dt}"
						)

		raw_transitions = wf.get("transitions", [])
		if not isinstance(raw_transitions, list):
			self.err(code, "9.2", "transitions phải là danh sách")
			raw_transitions = []
		for i, t in enumerate(raw_transitions):
			if not isinstance(t, dict):
				self.err(code, "9.2", f"transition #{i} không phải object")
				continue
			label = f"{t.get('from')} -> {t.get('to')}"
			self.check_codes(code, t.get("roles", []), f"transition {label}")
			for end in ("from", "to"):
				if t.get(end) not in by_name:
					self.err(code, "9.2", f"transition {label}: state {t.get(end)!r} không có trong states")
			dst = by_name.get(t.get("to"))
			self.check_transition_rights(code, label, t, by_name.get(t.get("from")), dst, doctypes)
			for dt in t.get("except_doctypes") or ():
				if dt not in doctypes:
					self.err(code, "9.3.K", f"transition {label}: except_doctypes có {dt!r} ngoài doctypes")
			for key in t.get("per_doctype_condition") or {}:
				if key not in doctypes:
					self.err(
						code,
						"9.3.K",
						f"transition {label}: per_doctype_condition có khóa {key!r} ngoài doctypes",
					)
			if dst is not None and (dst["doc_status"] == 2 or dst["state"] == CANCELLED):
				self.err(code, "9.2.4", f"transition {label} dẫn vào {CANCELLED}")
			if (
				t.get("from") == first.get(0)
				and dst is not None
				and dst["doc_status"] == 1
				and dst["state"] != first.get(1)
			):
				self.err(
					code,
					"R-17",
					f"transition tự duyệt {label} phải tới state doc_status 1 đầu tiên ({first.get(1)})",
				)

	def check_transition_rights(self, code, label, t, src, dst, doctypes):
		"""9.2.T — apply_workflow saves (and submits) the document as the acting user."""
		m = self.m
		needs = ["write"]
		if src is not None and dst is not None and src["doc_status"] == 0 and dst["doc_status"] == 1:
			needs.append("submit")
		roles = [c for c in t.get("roles") or [] if isinstance(c, str) and c in m.roles]
		for dt in doctypes:
			info = self.site.doctypes.get(dt)
			if info is None or dt not in m.doctypes or dt in (t.get("except_doctypes") or ()):
				continue
			try:
				rows = expand_doctype(m, dt, info)
			except Exception:  # the bad entry is reported by its own check_entry
				continue
			if m.doctypes[dt].state == "keep_standard":
				continue
			for role in roles:
				names = m.role_names(role)
				for ptype in needs:
					if not any(r.role in names and r.permlevel == 0 and ptype in r.ptypes for r in rows):
						self.err(code, "9.2.T", f"transition {label}: role {role} không có {ptype} trên {dt}")


def validate(m: Matrix, site: SiteInfo) -> Problems:
	return _Checker(m, site).run()

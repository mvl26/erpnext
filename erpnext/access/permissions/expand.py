"""Rule expansion — turns one DocType's matrix entry into concrete permission rows (G1, G2, G4, G7, G8)."""

from typing import NamedTuple

from erpnext.access.permissions.cells import parse_cell
from erpnext.access.permissions.matrix import DocTypeEntry, Matrix
from erpnext.access.permissions.site import DocTypeInfo

EXPANDED_STATES = ("matrix", "ref_master", "g1_only")


class PermRow(NamedTuple):
	role: str
	permlevel: int
	ptypes: frozenset
	if_owner: bool


class _Rows:
	"""Accumulates ptypes per (role, permlevel, if_owner) so duplicate rows merge."""

	def __init__(self):
		self.data: dict[tuple[str, int, bool], set[str]] = {}

	def add(self, m: Matrix, code: str, levels: dict[int, frozenset[str]], if_owner: bool = False):
		for name in m.role_names(code):
			for level, ptypes in levels.items():
				self.data.setdefault((name, level, if_owner), set()).update(ptypes)

	def finish(self) -> list[PermRow]:
		rows = []
		for (role, level, if_owner), ptypes in self.data.items():
			if level == 0 and "read" in ptypes:
				ptypes.add("report")  # G7 — report is only meaningful at level 0
			rows.append(PermRow(role, level, frozenset(ptypes), if_owner))
		return rows


def _scope_tokens(entry: DocTypeEntry, code: str) -> list[str]:
	return (entry.scope.get(code) or "").split()


def data_import_rows(m: Matrix) -> list[PermRow]:
	"""G4 — every role that can import on any DocType gets ``create read write`` + if_owner on Data Import."""
	rows = _Rows()
	grant = {0: frozenset({"create", "read", "write"})}
	for entry in m.doctypes.values():
		for code, cell in entry.perms.items():
			if "import" in parse_cell(cell).get(0, ()):
				rows.add(m, code, grant, if_owner=True)
	return rows.finish()


def expand_doctype(m: Matrix, doctype: str, info: DocTypeInfo) -> list[PermRow]:
	"""All permission rows one DocType needs. ``keep_standard`` DocTypes are not expanded here."""
	entry = m.doctypes.get(doctype)
	if entry is None and doctype == "Data Import":
		entry = DocTypeEntry(state="matrix")
	if entry is None:
		raise KeyError(f"{doctype!r} is not in the matrix")
	if entry.state not in EXPANDED_STATES:
		return []

	rules = m.rules
	salary = doctype in rules.get("salary_doctypes", ())
	rows = _Rows()

	for code, cell in entry.perms.items():
		rows.add(m, code, parse_cell(cell), if_owner="o" in _scope_tokens(entry, code))

	if doctype not in rules.get("g1_exceptions", ()):
		rows.add(m, "SYS", {0: frozenset({"read"})})
		vw = {0: frozenset({"read", "print"})}
		if salary or doctype in rules.get("vw_r1_extra", ()):
			vw[1] = frozenset({"read"})
		rows.add(m, "VW", vw)

	if entry.state != "g1_only" and doctype in rules.get("g2_doctypes", ()):
		ap = {0: frozenset({"read", "write", "submit"})}
		if salary:
			ap[1] = frozenset({"read"})
		rows.add(m, "AP", ap)

	if entry.state == "ref_master":
		rows.add(m, "EMP", {0: frozenset({"read"})})
	if entry.pda:
		rows.add(m, "PDA", {0: frozenset({"read"})})

	if doctype == "Data Import":
		for r in data_import_rows(m):
			rows.data.setdefault((r.role, r.permlevel, r.if_owner), set()).update(r.ptypes)

	return rows.finish()

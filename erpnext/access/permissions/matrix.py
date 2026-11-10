"""Matrix reader — merges every ``matrix/*.json`` fragment into one validated-in-shape ``Matrix``."""

import json
from dataclasses import dataclass, field
from pathlib import Path

from erpnext.access.permissions.cells import MatrixError

MATRIX_DIR = Path(__file__).parent / "matrix"

DOCTYPE_STATES = ("matrix", "ref_master", "g1_only", "keep_standard")

# Sections that merge by second-level key; a repeated key across files is an error.
DICT_SECTIONS = (
	"roles",
	"packs",
	"role_profiles",
	"doctypes",
	"rules",
	"reports",
	"pages",
	"workspaces",
	"workflows",
	"settings",
	"custom_fields",
	"user_permission_rules",
	"user_scope",
	"module_profiles",
)
LIST_SECTIONS = ("combined_profiles",)


@dataclass
class RoleDef:
	code: str
	names: tuple[str, ...]
	desk_access: int
	is_new: bool


@dataclass
class DocTypeEntry:
	state: str
	perms: dict[str, str] = field(default_factory=dict)
	scope: dict[str, str] = field(default_factory=dict)
	workflow: str | None = None
	permlevel: dict[int, dict] = field(default_factory=dict)
	keep_standard_rows: list[str] = field(default_factory=list)
	pda: bool = False


@dataclass
class Matrix:
	roles: dict[str, RoleDef] = field(default_factory=dict)
	packs: dict[str, list[str]] = field(default_factory=dict)
	role_profiles: dict[str, list[str]] = field(default_factory=dict)
	combined_profiles: list[dict] = field(default_factory=list)
	doctypes: dict[str, DocTypeEntry] = field(default_factory=dict)
	rules: dict = field(default_factory=dict)
	reports: dict[str, list[str]] = field(default_factory=dict)
	pages: dict[str, list[str]] = field(default_factory=dict)
	workspaces: dict[str, list[str]] = field(default_factory=dict)
	workflows: dict[str, dict] = field(default_factory=dict)
	settings: dict = field(default_factory=dict)
	custom_fields: dict = field(default_factory=dict)
	user_permission_rules: dict = field(default_factory=dict)
	user_scope: dict = field(default_factory=dict)
	module_profiles: dict = field(default_factory=dict)

	def role_names(self, code: str) -> tuple[str, ...]:
		if code not in self.roles:
			raise MatrixError(f"Unknown role code {code!r}")
		return self.roles[code].names

	def profile_roles(self, profile: str) -> list[str]:
		"""Frappe role names of a profile, packs and role codes expanded, order kept, no duplicates."""
		if profile not in self.role_profiles:
			raise MatrixError(f"Unknown role profile {profile!r}")
		names: list[str] = []
		for item in self.role_profiles[profile]:
			codes = self.packs[item] if item in self.packs else [item]
			for code in codes:
				for name in self.role_names(code):
					if name not in names:
						names.append(name)
		return names


def _build_doctype(name: str, raw: dict) -> DocTypeEntry:
	state = raw.get("state")
	if state not in DOCTYPE_STATES:
		raise MatrixError(f"DocType {name!r}: invalid state {state!r}")
	return DocTypeEntry(
		state=state,
		perms=dict(raw.get("perms") or {}),
		scope=dict(raw.get("scope") or {}),
		workflow=raw.get("workflow"),
		permlevel={int(level): spec for level, spec in (raw.get("permlevel") or {}).items()},
		keep_standard_rows=list(raw.get("keep_standard_rows") or []),
		pda=bool(raw.get("pda", False)),
	)


def load_matrix(directory: Path = MATRIX_DIR) -> Matrix:
	merged: dict[str, dict] = {section: {} for section in DICT_SECTIONS}
	origin: dict[tuple[str, str], str] = {}
	combined: list[dict] = []

	for path in sorted(Path(directory).glob("*.json")):
		data = json.loads(path.read_text(encoding="utf-8"))
		if not isinstance(data, dict):
			raise MatrixError(f"{path.name}: top level must be an object")
		for section, value in data.items():
			if section in LIST_SECTIONS:
				combined.extend(value)
			elif section in DICT_SECTIONS:
				for key, item in value.items():
					if (section, key) in origin:
						raise MatrixError(
							f"Duplicate {section} key {key!r} in {origin[(section, key)]} and {path.name}"
						)
					origin[(section, key)] = path.name
					merged[section][key] = item
			else:
				raise MatrixError(f"{path.name}: unknown top-level key {section!r}")

	roles = {
		code: RoleDef(
			code=code,
			names=tuple(raw["names"]),
			desk_access=int(raw["desk_access"]),
			is_new=bool(raw.get("is_new", False)),
		)
		for code, raw in merged["roles"].items()
	}
	return Matrix(
		roles=roles,
		packs=merged["packs"],
		role_profiles=merged["role_profiles"],
		combined_profiles=combined,
		doctypes={name: _build_doctype(name, raw) for name, raw in merged["doctypes"].items()},
		rules=merged["rules"],
		reports=merged["reports"],
		pages=merged["pages"],
		workspaces=merged["workspaces"],
		workflows=merged["workflows"],
		settings=merged["settings"],
		custom_fields=merged["custom_fields"],
		user_permission_rules=merged["user_permission_rules"],
		user_scope=merged["user_scope"],
		module_profiles=merged["module_profiles"],
	)

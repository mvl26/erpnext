"""H1 — Contract limited by ``party_type`` per role — spec 11.3 H1.

SU/SM see Customer contracts, PU/PM Supplier, HU/HM Employee; AM, VW, AP and SYS see all. A user with several of
these roles gets the union. A user who holds none of them but still reaches Contract through some other role
sees nothing (fail closed).

R-2: :func:`has_permission` returns only ``False`` or ``None`` — frappe stops at the first non-``None`` hook.
R-GATE: both hooks return at once while ``mvl_rbac_enabled`` is off.
Role codes are resolved to frappe role names through the matrix (cached per process); the user's roles are read
with ``frappe.get_roles`` (cached by frappe).
"""

from functools import lru_cache

import frappe

from erpnext.access.permissions.sync import is_enabled

DOCTYPE = "Contract"
PARTY_TYPE_BY_CODE = {
	"SU": "Customer",
	"SM": "Customer",
	"PU": "Supplier",
	"PM": "Supplier",
	"HU": "Employee",
	"HM": "Employee",
}
ALL_CODES = ("AM", "VW", "AP", "SYS")


@lru_cache(maxsize=1)
def _role_tables() -> tuple[dict[str, str], frozenset[str]]:
	"""(frappe role name → party_type, role names that see every party_type)."""
	from erpnext.access.permissions.matrix import load_matrix

	m = load_matrix()
	by_role = {name: party for code, party in PARTY_TYPE_BY_CODE.items() for name in m.role_names(code)}
	everything = frozenset(name for code in ALL_CODES for name in m.role_names(code))
	return by_role, everything


def allowed_party_types(user: str) -> tuple[str, ...] | None:
	"""``party_type`` values ``user`` may see; ``None`` means all, ``()`` means none.

	No cache of its own: ``frappe.get_roles`` is already cached per user by frappe, and the rest is a set lookup.
	"""
	if user == "Administrator":
		return None
	by_role, everything = _role_tables()
	roles = set(frappe.get_roles(user))
	if roles & everything:
		return None
	return tuple(sorted({by_role[r] for r in roles if r in by_role}))


def has_permission(
	doc, ptype: str | None = None, user: str | None = None, debug: bool = False
) -> bool | None:
	"""``has_permission`` hook: ``False`` when ``doc.party_type`` is outside the user's scope, else ``None`` (R-2)."""
	if not is_enabled():
		return None
	user = user or frappe.session.user
	allowed = allowed_party_types(user)
	if allowed is None:
		return None
	if doc.get("party_type") in allowed:
		return None
	return False


def query_conditions(user: str | None = None, doctype: str | None = None) -> str:
	"""``permission_query_conditions`` hook: ``""`` (no limit) or an SQL condition on ``party_type``."""
	if not is_enabled():
		return ""
	user = user or frappe.session.user
	allowed = allowed_party_types(user)
	if allowed is None:
		return ""
	if not allowed:
		return "1=0"  # no allowed party type matches nothing — "" would mean unlimited
	values = ", ".join(frappe.db.escape(v, percent=False) for v in allowed)
	return f"`tab{DOCTYPE}`.`party_type` in ({values})"

"""H8 — row scope of HR records for matrix cells marked ``[e]`` (own) and ``[d]`` (department) — spec 11.3 H8.

Spec section 10 rules out User Permission here: it binds a *user*, not a role, so a user holding EMP next to a
business role (KT-NV = AU + EMP) would either lose the business data or open EMP's rights to every employee.
H8 therefore decides per DocType *and per ptype*, from the matrix, for user U:

(a) U holds a role with ``ptype`` on the DocType whose cell has no ``e``/``d`` scope and is not ``·o`` → no limit;
(b) else U holds a ``[d]`` role with ``ptype`` → records of :func:`visible_employees`; on a department-mode
    DocType (no Employee link) the Departments U approves, sub-departments included;
(c) else U holds an ``[e]`` role with ``ptype`` → records of U's own Employee (department mode: own Department).

``·o`` cells are frappe's ``if_owner`` rows: a user whose ``ptype`` comes only from them is left to frappe's owner
check, and one who also holds an ``[e]``/``[d]`` role keeps the records they own (Timesheet: PJU ·o + DH [d];
Employee Performance Feedback: PJM ·o + DH [d]).

R-2: :func:`has_permission` returns only ``False`` or ``None`` — frappe stops at the first non-``None`` hook
(frappe/permissions.py:450-457), so ``True`` would silence the hooks of hrms and other apps on the same DocType.
R-GATE: both hooks return at once while ``mvl_rbac_enabled`` is off; they run on every list and form request.
The lookups below use ``frappe.get_all`` / SQL on purpose: a permission hook must not re-enter permission checks.
"""

from functools import cache, lru_cache
from typing import NamedTuple

import frappe

from erpnext.access.permissions.sync import is_enabled

EMPLOYEE = "employee"
DEPARTMENT = "department"
SCOPE_TOKENS = frozenset({"e", "d"})
APPROVER_FIELDS = ("leave_approvers", "expense_approvers", "shift_request_approver")
# DocTypes whose Employee link is not called ``employee``. Each entry is checked against the meta: a missing or
# non-Employee field leaves the DocType unresolved, which test_matrix_data reports.
FIELD_OVERRIDES = {
	"Business Trip": "registered_by"
}  # hrms fork: "Người đăng ký"; travelers sit in a child table


class RefField(NamedTuple):
	fieldname: str
	kind: str  # EMPLOYEE or DEPARTMENT


class Grants(NamedTuple):
	"""Frappe role names that hold one ptype on one DocType at level 0, split by the scope of their cell."""

	unscoped: frozenset[str]
	department: frozenset[str]
	own: frozenset[str]
	owner: frozenset[str]


class Limit(NamedTuple):
	field: RefField | None  # None: DocType unresolved — fail closed
	values: tuple[str, ...]
	owner: str | None  # records this user owns stay visible (·o role)


# Resolved reference field per scoped DocType, filled from the meta at first use (cached per process).
_REF_FIELDS: dict[str, RefField | None] = {}


# -- matrix side (per process) --------------------------------------------------------------------


@lru_cache(maxsize=1)
def _matrix():
	from erpnext.access.permissions.matrix import load_matrix

	return load_matrix()


@lru_cache(maxsize=1)
def scoped_doctypes() -> frozenset[str]:
	"""DocTypes with at least one ``[e]`` or ``[d]`` cell — exactly the ones hooks.py must list."""
	return frozenset(
		name
		for name, entry in _matrix().doctypes.items()
		if any(SCOPE_TOKENS & set((scope or "").split()) for scope in entry.scope.values())
	)


def _info(doctype: str):
	from erpnext.access.permissions.site import DocTypeInfo

	meta = frappe.get_meta(doctype)
	return DocTypeInfo(
		name=doctype,
		app=frappe.db.get_value("Module Def", meta.module, "app_name") or "",
		module=meta.module,
		is_submittable=bool(meta.is_submittable),
		issingle=bool(meta.issingle),
	)


@cache
def _grants(doctype: str, ptype: str) -> Grants:
	from erpnext.access.permissions.expand import expand_doctype

	m = _matrix()
	entry = m.doctypes[doctype]
	tokens: dict[str, set[str]] = {}
	for code, scope in entry.scope.items():
		for name in m.role_names(code):
			tokens.setdefault(name, set()).update((scope or "").split())

	sets: dict[str, set[str]] = {"unscoped": set(), "department": set(), "own": set(), "owner": set()}
	for row in expand_doctype(m, doctype, _info(doctype)):
		if row.permlevel != 0 or ptype not in row.ptypes:
			continue
		role_tokens = tokens.get(row.role, set())
		if row.if_owner:
			sets["owner"].add(row.role)
		elif "d" in role_tokens:
			sets["department"].add(row.role)
		elif "e" in role_tokens:
			sets["own"].add(row.role)
		else:
			sets["unscoped"].add(row.role)
	return Grants(**{key: frozenset(value) for key, value in sets.items()})


def unscoped_roles(doctype: str, ptype: str) -> frozenset[str]:
	"""Roles that hold ``ptype`` on ``doctype`` with no ``[e]``/``[d]`` scope and not only as owner (H8 a)."""
	if doctype not in scoped_doctypes():
		return frozenset()
	return _grants(doctype, ptype).unscoped


# -- reference field (per process, from meta) -----------------------------------------------------


def _is_link(meta, fieldname: str, target: str) -> bool:
	df = meta.get_field(fieldname)
	return bool(df and df.fieldtype == "Link" and df.options == target)


def _resolve(doctype: str) -> RefField | None:
	if doctype == "Employee":
		return RefField("name", EMPLOYEE)
	meta = frappe.get_meta(doctype)
	fieldname = FIELD_OVERRIDES.get(doctype, "employee")
	if _is_link(meta, fieldname, "Employee"):
		return RefField(fieldname, EMPLOYEE)
	if doctype not in FIELD_OVERRIDES and _is_link(meta, "department", "Department"):
		return RefField("department", DEPARTMENT)
	return None


def ref_field(doctype: str) -> RefField | None:
	if doctype not in _REF_FIELDS:
		_REF_FIELDS[doctype] = _resolve(doctype)
	return _REF_FIELDS[doctype]


def ref_fields() -> dict[str, RefField | None]:
	"""The resolved field of every scoped DocType; ``None`` marks one H8 cannot scope."""
	return {doctype: ref_field(doctype) for doctype in sorted(scoped_doctypes())}


# -- user side (per request, in frappe.local — never Redis) ---------------------------------------


def _store() -> dict:
	store = getattr(frappe.local, "mvl_scope_cache", None)
	if store is None:
		store = frappe.local.mvl_scope_cache = {}
	return store


def clear_request_cache() -> None:
	frappe.local.mvl_scope_cache = {}


def _cached(kind: str, user: str, compute):
	store = _store()
	key = (kind, user)
	if key not in store:
		store[key] = compute(user)
	return store[key]


def _own_employees(user: str) -> tuple[str, ...]:
	return _cached("own", user, lambda u: tuple(frappe.get_all("Employee", {"user_id": u}, pluck="name")))


def _own_departments(user: str) -> tuple[str, ...]:
	def compute(u):
		own = _own_employees(u)
		if not own:
			return ()
		rows = frappe.get_all("Employee", {"name": ("in", own)}, pluck="department")
		return tuple(sorted({d for d in rows if d}))

	return _cached("own_departments", user, compute)


def approver_departments(user: str) -> tuple[str, ...]:
	"""Departments where ``user`` sits in a Department Approver table, with every sub-department."""

	def compute(u):
		heads = frappe.get_all(
			"Department Approver",
			filters={"approver": u, "parenttype": "Department", "parentfield": ("in", APPROVER_FIELDS)},
			pluck="parent",
			distinct=True,
		)
		if not heads:
			return ()
		rows = frappe.db.sql(
			"""
			SELECT DISTINCT child.name
			FROM `tabDepartment` child
			JOIN `tabDepartment` head ON child.lft >= head.lft AND child.rgt <= head.rgt
			WHERE head.name IN %(heads)s
			""",
			{"heads": tuple(heads)},
		)
		return tuple(sorted(r[0] for r in rows))

	return _cached("approver_departments", user, compute)


def visible_employees(user: str) -> tuple[str, ...] | None:
	"""Employees a ``[d]`` holder may see (H8 b); ``None`` means no limit (Administrator).

	Employees of the Departments ``user`` approves (sub-departments included); Employees whose
	``leave_approver`` or ``expense_approver`` is ``user`` or who ``reports_to`` the user's Employee; the user's
	own Employee.
	"""
	if user == "Administrator":
		return None

	def compute(u):
		own = _own_employees(u)
		departments = approver_departments(u)
		conditions = ["leave_approver = %(user)s", "expense_approver = %(user)s"]
		if own:
			conditions += ["name IN %(own)s", "reports_to IN %(own)s"]
		if departments:
			conditions.append("department IN %(departments)s")
		rows = frappe.db.sql(
			f"SELECT name FROM `tabEmployee` WHERE {' OR '.join(conditions)}",
			{"user": u, "own": own or ("",), "departments": departments or ("",)},
		)
		return tuple(sorted(r[0] for r in rows))

	return _cached("visible", user, compute)


# -- decision ---------------------------------------------------------------------------------------


def _limit(doctype: str, ptype: str | None, user: str) -> Limit | None:
	"""H8 (a)/(b)/(c) for one DocType and ptype; ``None`` means H8 does not limit this user."""
	if doctype not in scoped_doctypes():
		return None
	grants = _grants(doctype, ptype or "read")  # get_doc_permissions(doc) without ptype — the form load
	roles = set(frappe.get_roles(user))
	if roles & grants.unscoped:
		return None
	department = bool(roles & grants.department)
	if not department and not roles & grants.own:
		return None  # no scoped grant: frappe denies, or only ·o rows (frappe's owner check)
	owner = user if roles & grants.owner else None
	field = ref_field(doctype)
	if field is None:
		return Limit(None, (), owner)
	if field.kind == EMPLOYEE:
		values = visible_employees(user) if department else _own_employees(user)
	else:
		values = approver_departments(user) if department else _own_departments(user)
	return Limit(field, tuple(values or ()), owner)


def has_permission(
	doc, ptype: str | None = None, user: str | None = None, debug: bool = False
) -> bool | None:
	"""``has_permission`` hook: ``False`` when the record is outside the user's scope, otherwise ``None`` (R-2)."""
	if not is_enabled():
		return None
	user = user or frappe.session.user
	if user == "Administrator":
		return None
	limit = _limit(doc.doctype, ptype, user)
	if limit is None:
		return None
	if limit.owner and (doc.get("owner") or "").lower() == limit.owner.lower():
		return None
	if limit.field and doc.get(limit.field.fieldname) in limit.values:
		return None
	return False


def query_conditions(user: str | None = None, doctype: str | None = None) -> str:
	"""``permission_query_conditions`` hook: ``""`` (no limit) or an SQL condition on the reference field."""
	if not is_enabled() or not doctype:
		return ""
	user = user or frappe.session.user
	if user == "Administrator":
		return ""
	limit = _limit(doctype, "read", user)
	if limit is None:
		return ""
	table = f"`tab{doctype}`"
	if limit.field and limit.values:
		values = ", ".join(frappe.db.escape(v, percent=False) for v in limit.values)
		condition = f"{table}.`{limit.field.fieldname}` in ({values})"
	else:
		condition = "1=0"  # an empty scope matches nothing — "" would mean unlimited
	if limit.owner:
		condition = f"({condition} or {table}.`owner` = {frappe.db.escape(limit.owner, percent=False)})"
	return condition

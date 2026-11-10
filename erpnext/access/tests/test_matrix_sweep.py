"""Sweep: frappe.has_permission for every (Role Profile, DocType, ptype) equals the matrix expansion.

The site tests need a test site (Q8) where the RBAC sync has already run; on the production site they skip.
Scoped cells (``e`` / ``d`` / ``o``) are only checked at DocType level — document-level scope is H8.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.access.permissions.docperm_sync import desired_rows
from erpnext.access.permissions.expand import PermRow
from erpnext.access.permissions.matrix import load_matrix
from erpnext.access.permissions.site import SiteInfo
from erpnext.access.tests.fixtures import make_profile_user
from erpnext.access.tests.helpers import require_test_site, small_matrix

SWEEP_PTYPES = ("read", "write", "create", "delete", "submit", "cancel")


def expected_perms(rows: list[PermRow], roles, submittable: bool, ptypes=SWEEP_PTYPES) -> dict[str, bool]:
	"""What frappe.has_permission(dt, ptype, user) (no doc) answers for a user holding ``roles``.

	Mirrors frappe.permissions.get_role_permissions: only permlevel-0 rows of held roles count. When some
	applicable row is ``if_owner`` and no applicable row grants the ptype without it, DocType-level access
	drops to False — except ``read`` (list access, rows are filtered by owner later) and ``create``
	(if_owner never limits create). ``submit`` also needs a submittable DocType.
	"""
	held = set(roles)
	applicable = [r for r in rows if r.role in held and r.permlevel == 0]
	owner_enabled = any(r.if_owner for r in applicable)
	result = {}
	for ptype in ptypes:
		granted = any(ptype in r.ptypes for r in applicable)
		if granted and owner_enabled and ptype not in ("read", "create"):
			granted = any(ptype in r.ptypes and not r.if_owner for r in applicable)
		if ptype == "submit" and not submittable:
			granted = False
		result[ptype] = granted
	return result


def profile_codes(m, profile: str) -> list[str]:
	codes = []
	for item in m.role_profiles[profile]:
		codes.extend(m.packs[item] if item in m.packs else [item])
	return codes


def profile_held_roles(m, profile: str) -> set[str]:
	"""Roles a fixture user on ``profile`` holds, as frappe.get_roles reports them.

	frappe adds All and Guest to everyone, and Desk User only to System Users — a profile with no role code
	of desk_access 1 (customer / supplier portal) gives a Website User.
	"""
	roles = {*m.profile_roles(profile), "All", "Guest"}
	if any(m.roles[code].desk_access for code in profile_codes(m, profile)):
		roles.add("Desk User")
	return roles


class TestExpectedPerms(FrappeTestCase):
	"""Pure — runs anywhere, touches no data."""

	SHOW_TRANSACTION_COMMIT_WARNINGS = True

	def test_expected_perms_on_small_matrix(self):
		m = small_matrix()
		info = frappe._dict(name="Purchase Order", app="erpnext", is_submittable=True)
		po_rows = desired_rows(m, "Purchase Order", info)
		pu = expected_perms(po_rows, m.role_names("PU"), True)
		self.assertTrue(pu["read"] and pu["write"] and pu["create"])
		self.assertFalse(pu["delete"])
		pm = expected_perms(po_rows, m.role_names("PM"), True)
		self.assertTrue(pm["submit"] and pm["cancel"])
		self.assertFalse(expected_perms(po_rows, m.role_names("PM"), False)["submit"])
		stu = expected_perms(po_rows, m.role_names("STU"), True)
		self.assertEqual([p for p, v in stu.items() if v], ["read"])
		self.assertFalse(any(expected_perms(po_rows, ["Nobody"], True).values()))

	def test_if_owner_only_rows_keep_read_and_create_only(self):
		rows = [PermRow("X", 0, frozenset({"read", "write", "create", "delete"}), True)]
		got = expected_perms(rows, ["X"], False)
		self.assertEqual(got, dict.fromkeys(SWEEP_PTYPES, False) | {"read": True, "create": True})

	def test_unrestricted_row_beats_if_owner_row(self):
		rows = [
			PermRow("X", 0, frozenset({"read", "write"}), True),
			PermRow("Y", 0, frozenset({"write"}), False),
		]
		got = expected_perms(rows, ["X", "Y"], False)
		self.assertTrue(got["read"] and got["write"])
		self.assertFalse(expected_perms(rows, ["X"], False)["write"])

	def test_portal_profile_gets_no_desk_user(self):
		m = small_matrix()
		cus = next(c for c, r in m.roles.items() if not r.desk_access and c not in m.packs)
		m.role_profiles["RP-TEST-PORTAL"] = [cus]
		m.role_profiles["RP-TEST-DESK"] = [cus, "PU"]
		portal = profile_held_roles(m, "RP-TEST-PORTAL")
		self.assertNotIn("Desk User", portal)
		self.assertTrue({"All", "Guest"} <= portal)
		self.assertIn("Desk User", profile_held_roles(m, "RP-TEST-DESK"))

	def test_higher_permlevel_rows_are_ignored(self):
		rows = [PermRow("X", 1, frozenset({"read", "write"}), False)]
		self.assertFalse(any(expected_perms(rows, ["X"], False).values()))


class TestMatrixSweep(FrappeTestCase):
	SHOW_TRANSACTION_COMMIT_WARNINGS = True

	def test_every_profile_doctype_ptype(self):
		require_test_site(self)
		m = load_matrix()
		site = SiteInfo.from_db()
		users = {profile: make_profile_user(profile) for profile in m.role_profiles}
		held = {}
		for profile, user in users.items():
			held[profile] = set(frappe.get_roles(user))
			if held[profile] != profile_held_roles(m, profile):
				self.fail(f"{profile}: user roles {sorted(held[profile])} != expected roles")
		mismatches = []
		checked = 0
		for dt, entry in m.doctypes.items():
			info = site.doctypes.get(dt)
			if info is None or entry.state == "keep_standard":
				continue
			rows = desired_rows(m, dt, info)
			for profile, user in users.items():
				want = expected_perms(rows, held[profile], info.is_submittable)
				for ptype in SWEEP_PTYPES:
					checked += 1
					got = bool(frappe.has_permission(dt, ptype, user=user))
					if got != want[ptype]:
						mismatches.append(f"{profile} | {dt} | {ptype}: expected {want[ptype]}, got {got}")
		self.assertGreater(checked, 0)
		if mismatches:
			self.fail("\n".join(mismatches[:500]) + f"\n… {len(mismatches)} mismatches of {checked} checks")


class TestProfileUsers(FrappeTestCase):
	SHOW_TRANSACTION_COMMIT_WARNINGS = True

	def test_user_holds_exactly_the_profile_roles(self):
		require_test_site(self)
		m = load_matrix()
		for profile in m.role_profiles:
			user = make_profile_user(profile)
			roles = set(frappe.get_roles(user)) - {"All", "Guest", "Desk User"}
			missing = set(m.profile_roles(profile)) - roles
			self.assertFalse(missing, f"{profile}: user lacks {sorted(missing)}")

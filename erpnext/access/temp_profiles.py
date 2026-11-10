"""H7 — return users from an expired temporary Role Profile to the base one (spec section 4; plan R-7).

A temporary profile is named ``RP-<base>+TMP-<yyyymmdd>``; it is valid through that date. The daily job moves
every enabled user on an expired one back to ``RP-<base>``; saving the User rewrites the roles from the profile.
R-GATE: returns at once while ``mvl_rbac_enabled`` is off.
"""

import datetime
import re
import traceback

import frappe
from frappe.utils import getdate

from erpnext.access.permissions.sync import is_enabled

TMP = re.compile(r"\+TMP-(\d{8})$")


def parse_expiry(profile: str) -> datetime.date | None:
	match = TMP.search(profile or "")
	if not match:
		return None
	try:
		return datetime.datetime.strptime(match.group(1), "%Y%m%d").date()
	except ValueError:
		return None


def base_profile(profile: str) -> str:
	return TMP.sub("", profile or "")


def expire() -> list[str]:
	"""Daily job: returns the users moved back to their base profile."""
	if not is_enabled():
		return []
	today = getdate()
	moved = []
	users = frappe.get_all(
		"User",
		filters={"enabled": 1, "role_profile_name": ("like", "%+TMP-%")},
		fields=["name", "role_profile_name"],
	)
	for row in users:
		expiry = parse_expiry(row.role_profile_name)
		if not expiry or expiry >= today:
			continue
		base = base_profile(row.role_profile_name)
		if not frappe.db.exists("Role Profile", base):
			frappe.log_error(
				title="RBAC H7 expire",
				message=f"Role Profile tạm hết hạn nhưng không có profile gốc {base}: bỏ qua {row.name}",
			)
			continue
		try:
			user = frappe.get_doc("User", row.name)
			user.role_profile_name = base
			user.save(ignore_permissions=True)
		except Exception:
			frappe.log_error(title="RBAC H7 expire", message=f"{row.name}\n{traceback.format_exc()}")
			continue
		moved.append(row.name)
		frappe.logger("rbac").info(f"H7: {row.name} {row.role_profile_name} -> {base}")
	return moved

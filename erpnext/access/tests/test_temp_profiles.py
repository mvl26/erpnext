"""H7 — temporary Role Profile expiry (spec section 4; plan R-7, T43). Profiles and users are throwaway."""

import datetime
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, getdate

from erpnext.access import audit_mail, temp_profiles

ENABLED = "erpnext.access.temp_profiles.is_enabled"


class Mailbox:
	def __init__(self):
		self.sent = []

	def __call__(self, **kwargs):
		self.sent.append(kwargs)


def make_profile(name: str, role: str) -> str:
	frappe.get_doc({"doctype": "Role Profile", "role_profile": name, "roles": [{"role": role}]}).insert(
		ignore_permissions=True
	)
	return name


def make_user(profile: str) -> str:
	doc = frappe.get_doc(
		{
			"doctype": "User",
			"email": f"tmp-{frappe.generate_hash(length=8)}@example.com",
			"first_name": "Tmp",
			"send_welcome_email": 0,
			"role_profile_name": profile,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def stamp(day) -> str:
	return day.strftime("%Y%m%d")


class TestTempProfiles(FrappeTestCase):
	SHOW_TRANSACTION_COMMIT_WARNINGS = True

	def test_parse_expiry(self):
		self.assertEqual(temp_profiles.parse_expiry("RP-X+TMP-20261231"), datetime.date(2026, 12, 31))
		for bad in ("RP-X", "RP-X+TMP-2026123", "RP-X+TMP-20261331", "RP-X+TMP-20261231x", "", None):
			self.assertIsNone(temp_profiles.parse_expiry(bad), bad)

	def test_base_profile(self):
		self.assertEqual(temp_profiles.base_profile("RP-X+TMP-20261231"), "RP-X")
		self.assertEqual(temp_profiles.base_profile("RP-X"), "RP-X")

	def test_expire(self):
		tag = frappe.generate_hash(length=6)
		base = make_profile(f"RP-T{tag}", "Blogger")
		today = getdate()
		expired = make_profile(f"{base}+TMP-{stamp(add_days(today, -1))}", "Newsletter Manager")
		current = make_profile(f"{base}+TMP-{stamp(today)}", "Newsletter Manager")
		orphan = make_profile(f"RP-N{tag}+TMP-{stamp(add_days(today, -3))}", "Newsletter Manager")
		u_expired, u_current, u_orphan = make_user(expired), make_user(current), make_user(orphan)
		u_off = make_user(expired)
		frappe.db.set_value("User", u_off, "enabled", 0)

		with patch(ENABLED, return_value=False):
			self.assertEqual(temp_profiles.expire(), [])
		self.assertEqual(frappe.db.get_value("User", u_expired, "role_profile_name"), expired)

		box = Mailbox()
		with (
			patch(ENABLED, return_value=True),
			patch("erpnext.access.audit_mail.is_enabled", return_value=True),
			patch.object(audit_mail, "recipients", return_value=["director@example.com"]),
			patch.object(frappe, "sendmail", box),
			patch.object(frappe, "log_error") as log_error,  # log_error writes a real Error Log row
		):
			moved = temp_profiles.expire()
		self.assertEqual(log_error.call_args.kwargs["title"], "RBAC H7 expire")
		self.assertIn(orphan.split("+")[0], log_error.call_args.kwargs["message"])
		# H7 moves are audited by H4: one mail per moved user
		self.assertEqual(len(box.sent), len(moved))
		self.assertTrue(any(u_expired in m["subject"] for m in box.sent))

		self.assertIn(u_expired, moved)
		self.assertNotIn(u_current, moved)
		self.assertNotIn(u_orphan, moved)
		self.assertNotIn(u_off, moved)
		self.assertEqual(frappe.db.get_value("User", u_expired, "role_profile_name"), base)
		roles = frappe.get_all("Has Role", filters={"parent": u_expired}, pluck="role")
		self.assertIn("Blogger", roles)
		self.assertNotIn("Newsletter Manager", roles)
		self.assertEqual(frappe.db.get_value("User", u_current, "role_profile_name"), current)
		self.assertEqual(frappe.db.get_value("User", u_orphan, "role_profile_name"), orphan)
		self.assertEqual(frappe.db.get_value("User", u_off, "role_profile_name"), expired)

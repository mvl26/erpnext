"""H9 — share a record with the user it is assigned to (spec 11.3 H9; plan R-6, T09).

frappe's "remove assignment" sets the ToDo to ``Cancelled`` (it does not delete), so ``on_update`` has to unshare;
``on_trash`` covers a ToDo deleted outright. Records and users are throwaway, created in the class transaction.
"""

from unittest.mock import patch

import frappe
from frappe.desk.form import assign_to
from frappe.share import get_users
from frappe.tests.utils import FrappeTestCase

from erpnext.access import assign_share

ENABLED = "erpnext.access.assign_share.is_enabled"


def make_user(*roles):
	email = f"ashare-{frappe.generate_hash(length=8)}@example.com"
	user = frappe.get_doc(
		{"doctype": "User", "email": email, "first_name": "AShare", "send_welcome_email": 0}
	)
	user.insert(ignore_permissions=True)
	if roles:
		user.add_roles(*roles)
	frappe.clear_cache(user=email)
	return email


def make_task():
	return frappe.get_doc(
		{"doctype": "Task", "subject": f"H9 {frappe.generate_hash(length=6)}", "description": "H9 test"}
	).insert(ignore_permissions=True)


def make_program():
	return frappe.get_doc(
		{
			"doctype": "Training Program",
			"training_program": f"H9 {frappe.generate_hash(length=6)}",
			"company": "Miyano",
			"description": "H9 test",
		}
	).insert(ignore_permissions=True)


def share_row(doctype, name, user):
	return frappe.db.get_value(
		"DocShare",
		{"share_doctype": doctype, "share_name": name, "user": user},
		["read", "write"],
		as_dict=True,
	)


class TestAssignShare(FrappeTestCase):
	SHOW_TRANSACTION_COMMIT_WARNINGS = True

	def setUp(self):
		patcher = patch(ENABLED, return_value=True)
		patcher.start()
		self.addCleanup(patcher.stop)
		frappe.set_user("Administrator")
		self.addCleanup(frappe.set_user, "Administrator")
		self.user = make_user()  # no business role: access to the record comes only from the share
		self.other = make_user()

	def assign(self, doc, user):
		assign_to.add({"assign_to": [user], "doctype": doc.doctype, "name": doc.name, "description": "x"})

	def unassign(self, doc, user):
		assign_to.remove(doc.doctype, doc.name, user)

	def test_constants(self):
		self.assertEqual(assign_share.SHARE_WRITE, {"Task"})
		self.assertEqual(
			assign_share.SHARE_READ, {"Job Applicant", "Interview", "Training Program", "Training Event"}
		)

	def test_task_assignment_shares_write_and_unassign_revokes(self):
		task, other_task = make_task(), make_task()
		self.assign(task, self.user)
		self.assertEqual(share_row("Task", task.name, self.user), {"read": 1, "write": 1})
		self.assertTrue(frappe.has_permission("Task", "write", task.name, user=self.user))
		self.assertFalse(frappe.has_permission("Task", "read", other_task.name, user=self.user))

		self.unassign(task, self.user)
		self.assertEqual(frappe.db.get_value("ToDo", {"reference_name": task.name}, "status"), "Cancelled")
		self.assertIsNone(share_row("Task", task.name, self.user))
		self.assertFalse(frappe.has_permission("Task", "read", task.name, user=self.user))

	def test_read_only_doctype_gets_read_share(self):
		program = make_program()
		self.assign(program, self.user)
		self.assertEqual(share_row("Training Program", program.name, self.user), {"read": 1, "write": 0})
		self.assertTrue(frappe.has_permission("Training Program", "read", program.name, user=self.user))
		self.assertFalse(frappe.has_permission("Training Program", "write", program.name, user=self.user))
		self.unassign(program, self.user)
		self.assertIsNone(share_row("Training Program", program.name, self.user))

	def test_second_open_todo_keeps_share(self):
		task = make_task()
		self.assign(task, self.user)
		second = frappe.get_doc(
			{
				"doctype": "ToDo",
				"allocated_to": self.user,
				"reference_type": "Task",
				"reference_name": task.name,
				"description": "second",
			}
		).insert(ignore_permissions=True)
		first = frappe.get_all(
			"ToDo", {"reference_name": task.name, "name": ("!=", second.name)}, pluck="name"
		)[0]
		frappe.db.set_value("ToDo", first, "status", "Cancelled")
		frappe.get_doc("ToDo", first).save(ignore_permissions=True)
		self.assertIsNotNone(share_row("Task", task.name, self.user), "còn ToDo Open khác thì giữ share")
		second.status = "Cancelled"
		second.save(ignore_permissions=True)
		self.assertIsNone(share_row("Task", task.name, self.user))

	def test_trash_unshares_but_not_with_other_open_todo(self):
		task = make_task()
		self.assign(task, self.user)
		todo = frappe.get_doc("ToDo", {"reference_name": task.name, "allocated_to": self.user})
		frappe.delete_doc("ToDo", todo.name, ignore_permissions=True, force=True)
		self.assertIsNone(share_row("Task", task.name, self.user))

	def test_other_users_share_untouched(self):
		task = make_task()
		self.assign(task, self.user)
		self.assign(task, self.other)
		self.unassign(task, self.user)
		self.assertIsNone(share_row("Task", task.name, self.user))
		self.assertEqual(share_row("Task", task.name, self.other), {"read": 1, "write": 1})

	def test_owner_keeps_nothing_removed(self):
		"""The record's owner is never unshared (the share was not ours)."""
		task = make_task()
		frappe.db.set_value("Task", task.name, "owner", self.user)
		frappe.share.add_docshare(
			"Task", task.name, self.user, read=1, write=1, flags={"ignore_share_permission": True}
		)
		self.assign(task, self.user)
		self.unassign(task, self.user)
		self.assertIsNotNone(share_row("Task", task.name, self.user))

	def test_unrelated_doctype_ignored(self):
		with patch("erpnext.access.assign_share.frappe.share.add_docshare") as add:
			todo = frappe.get_doc(
				{
					"doctype": "ToDo",
					"allocated_to": self.user,
					"reference_type": "User",
					"reference_name": self.user,
					"description": "x",
				}
			)
			todo.insert(ignore_permissions=True)
			add.assert_not_called()

	def test_gate_off_does_not_share(self):
		task = make_task()
		before = frappe.db.count("DocShare")
		with patch(ENABLED, return_value=False):
			todo = frappe.get_doc(
				{
					"doctype": "ToDo",
					"allocated_to": self.user,
					"reference_type": "Task",
					"reference_name": task.name,
					"description": "x",
				}
			).insert(ignore_permissions=True)
			todo.status = "Cancelled"
			todo.save(ignore_permissions=True)
		self.assertEqual(frappe.db.count("DocShare"), before)

	def test_reassign_by_editing_todo_moves_share(self):
		task = make_task()
		self.assign(task, self.user)
		todo = frappe.get_doc("ToDo", {"reference_name": task.name, "allocated_to": self.user})
		todo.allocated_to = self.other
		todo.save(ignore_permissions=True)
		self.assertIsNone(share_row("Task", task.name, self.user))
		self.assertEqual(share_row("Task", task.name, self.other), {"read": 1, "write": 1})

	def test_reopen_reshares_and_closed_unshares(self):
		task = make_task()
		self.assign(task, self.user)
		self.unassign(task, self.user)
		todo = frappe.get_doc("ToDo", {"reference_name": task.name, "allocated_to": self.user})
		todo.status = "Open"
		todo.save(ignore_permissions=True)
		self.assertEqual(share_row("Task", task.name, self.user), {"read": 1, "write": 1})
		todo.status = "Closed"
		todo.save(ignore_permissions=True)
		self.assertIsNone(share_row("Task", task.name, self.user))

	def test_assignee_reopening_cancelled_todo_does_not_regain_share(self):
		task = make_task()
		self.assign(task, self.user)
		self.unassign(task, self.user)
		todo = frappe.get_doc("ToDo", {"reference_name": task.name, "allocated_to": self.user})
		frappe.set_user(self.user)
		todo.status = "Open"
		todo.save(ignore_permissions=True)
		frappe.set_user("Administrator")
		self.assertIsNone(share_row("Task", task.name, self.user))
		self.assertFalse(frappe.has_permission("Task", "write", task.name, user=self.user))

	def _self_todo(self, doc, **extra):
		return frappe.get_doc(
			{
				"doctype": "ToDo",
				"allocated_to": self.user,
				"reference_type": doc.doctype,
				"reference_name": doc.name,
				"description": "self-assigned",
				**extra,
			}
		).insert(ignore_permissions=True)

	def test_self_inserted_todo_without_rights_does_not_share(self):
		"""frappe lets anyone insert a ToDo allocated to themselves — that must not open the record."""
		task, program = make_task(), make_program()
		frappe.set_user(self.user)
		self._self_todo(task)
		self._self_todo(program, assigned_by="Administrator")  # assigned_by is client-settable: ignored
		frappe.set_user("Administrator")
		self.assertIsNone(share_row("Task", task.name, self.user))
		self.assertIsNone(share_row("Training Program", program.name, self.user))
		self.assertFalse(frappe.has_permission("Task", "read", task.name, user=self.user))

	def test_assignee_repointing_todo_does_not_share_other_record(self):
		"""The assignee may edit their ToDo; pointing it at another record must not borrow the assigner's right."""
		task, secret = make_task(), make_task()
		self.assign(task, self.user)
		todo = frappe.get_doc("ToDo", {"reference_name": task.name, "allocated_to": self.user})
		frappe.set_user(self.user)
		todo.reference_name = secret.name
		todo.save(ignore_permissions=True)
		frappe.set_user("Administrator")
		self.assertIsNone(share_row("Task", secret.name, self.user))
		self.assertIsNone(share_row("Task", task.name, self.user), "share cũ vẫn được gỡ")

	def test_assigner_with_rights_shares(self):
		task = make_task()
		assigner = make_user("Projects User")
		self.assertTrue(frappe.has_permission("Task", "write", task.name, user=assigner))
		frappe.set_user(assigner)
		self.assign(task, self.user)
		frappe.set_user("Administrator")
		self.assertEqual(share_row("Task", task.name, self.user), {"read": 1, "write": 1})

	def test_assigner_without_write_does_not_share_task(self):
		task = make_task()
		reader = make_user()
		frappe.share.add_docshare(
			"Task", task.name, reader, read=1, write=0, notify=0, flags={"ignore_share_permission": True}
		)
		frappe.set_user(reader)
		frappe.get_doc(
			{
				"doctype": "ToDo",
				"allocated_to": self.user,
				"reference_type": "Task",
				"reference_name": task.name,
				"description": "x",
			}
		).insert(ignore_permissions=True)
		frappe.set_user("Administrator")
		self.assertIsNone(share_row("Task", task.name, self.user), "chỉ có read thì không cấp write")

"""Orchestrator — ``run()`` (manual, strict) and ``after_migrate()`` (migrate hook, never raises).

Keep this module import-light: every runtime hook of the RBAC package imports ``is_enabled`` from here.
The step modules are imported inside the functions that need them.
"""

import importlib
import sys
import traceback
from collections import Counter

import frappe


def is_enabled() -> bool:
	return bool(frappe.conf.get("mvl_rbac_enabled"))


def _optional(module: str):
	"""Import a step module that a later task adds (Task 16: workflows, Task 22: audit_mail); None if absent."""
	name = module if "." in module else f"erpnext.access.permissions.{module}"
	try:
		return importlib.import_module(name)
	except ModuleNotFoundError as e:
		if e.name != name:
			raise
		return None


def _prepare():
	from erpnext.access.permissions.matrix import load_matrix
	from erpnext.access.permissions.site import SiteInfo
	from erpnext.access.permissions.validate import validate

	m = load_matrix()
	site = SiteInfo.from_db()
	return m, site, validate(m, site)


def _write_steps(m, site) -> dict:
	from erpnext.access.permissions import docperm_sync, profiles, schema, settings, ui_roles, user_scope
	from erpnext.access.permissions.audit import _line, run_audit

	summary: dict = {"counters": Counter(), "warnings": [], "audit": []}
	counters = summary["counters"]
	# DDL before DML is intentional: after a mid-sync failure only hidden Custom Fields remain.
	schema.ensure_schema(m)
	counters["roles"] = profiles.sync_roles(m)
	summary["warnings"] += profiles.sync_role_profiles(m)
	counters.update(docperm_sync.sync_docperms(m, site))
	summary["locked"] = ui_roles.sync_report_roles(m, site, summary["warnings"])
	summary["warnings"] += ui_roles.sync_page_roles(m)
	summary["warnings"] += ui_roles.sync_workspace_roles(m)
	workflows = _optional("workflows")  # Task 16 adds the module; no-op until then
	if workflows and workflows.workflows_enabled(m):
		workflows.sync_workflows(m)
	summary["audit"] += settings.sync_settings(m)
	counters["two_factor_roles"] = settings.sync_two_factor_roles(m)
	settings.sync_module_profiles(m)
	for key, count in user_scope.sync_user_permissions(m, summary["audit"]).items():
		counters[f"user_permission_{key}"] = count
	summary["audit"] += _line("User chưa có phạm vi trong user_scope", user_scope.users_without_scope(m))
	summary["audit"] += run_audit(m, site)
	mail = _optional("erpnext.access.audit_mail")
	if mail:
		mail.send_sync_summary(counters)
	return summary


def _print_summary(summary: dict) -> None:
	print("RBAC sync xong:", dict(summary["counters"]))
	print(f"  report đang khóa: {len(summary.get('locked', []))}")
	for label, key in (("Cảnh báo", "warnings"), ("Audit", "audit")):
		for line in summary[key]:
			print(f"  {label}: {line}")


def _run_unguarded(m, site) -> dict:
	previous = frappe.flags.get("in_rbac_sync")
	frappe.flags.in_rbac_sync = True
	try:
		summary = _write_steps(m, site)
	finally:
		frappe.flags.in_rbac_sync = previous or False
	_print_summary(summary)
	return summary


def run() -> None:
	"""Manual run (``bench execute``): raises on validation errors, lets exceptions propagate."""
	if not is_enabled():
		print("RBAC sync tắt (mvl_rbac_enabled chưa bật)")
		return
	m, site, problems = _prepare()
	if problems.errors:
		frappe.throw("<br>".join(problems.errors), title="RBAC matrix lỗi, chưa ghi gì")
	for warning in problems.warnings:
		print(f"  Validate: {warning}")
	_run_unguarded(m, site)


def _log_failure(message: str) -> None:
	"""Error Log row titled "RBAC sync", so a skipped/failed sync shows in Desk and not only in the migrate output.

	Written after any rollback, so it survives; migrate commits it with the hooks that follow. Never raises.
	"""
	try:
		frappe.log_error(title="RBAC sync", message=message)
	except Exception:
		traceback.print_exc(file=sys.stdout)


def _cleanup_roles() -> None:
	"""Role / Role Profile hygiene (``cleanup.py``) — on every migrate, flag or not; never raises.

	Its own savepoint: a failure undoes only the cleanup, not what earlier migrate hooks wrote.
	"""
	try:
		frappe.db.savepoint("mvl_role_cleanup")
		from erpnext.access.permissions import cleanup

		cleanup.run(dry_run=0)
	except Exception:
		trace = traceback.format_exc()
		print("Dọn role lỗi, đã hoàn tác phần dọn:")
		print(trace, end="")
		frappe.db.rollback(save_point="mvl_role_cleanup")
		frappe.clear_cache()
		_log_failure("Dọn role lỗi, đã hoàn tác phần dọn:\n" + trace)


def after_migrate() -> None:
	"""Migrate hook (R-20): never raises, so the hrms and assetcore hooks that follow still run."""
	_cleanup_roles()
	if not is_enabled():
		print("RBAC sync tắt (mvl_rbac_enabled chưa bật)")
		return
	try:
		# migrate runs every after_migrate hook in one transaction; commit what the earlier hooks did so the
		# rollback below only discards RBAC's own writes.
		frappe.db.commit()
		m, site, problems = _prepare()
		if problems.errors:
			print("RBAC matrix lỗi:")
			for error in problems.errors:
				print(f"  {error}")
			print("RBAC sync bỏ qua, chưa ghi gì")
			_log_failure(
				"RBAC sync bỏ qua vì matrix lỗi, chưa ghi gì:\n" + "\n".join(map(str, problems.errors))
			)
			return
		for warning in problems.warnings:
			print(f"  Validate: {warning}")
		_run_unguarded(m, site)
	except Exception:
		print("RBAC sync lỗi, đã hoàn tác phần chưa commit:")
		trace = traceback.format_exc()
		print(trace, end="")
		frappe.db.rollback()
		frappe.clear_cache()  # caches may have been rebuilt from the rolled-back rows
		_log_failure("RBAC sync lỗi, đã hoàn tác phần chưa commit:\n" + trace)  # after the rollback: kept

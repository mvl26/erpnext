"""Schema step of the sync — the only DDL: Custom Fields, permlevel / reqd / default Property Setters.

Runs first so that later steps (DocPerm, Workflow) never trigger ``ALTER TABLE``. Idempotent: a second run
finds everything in place and writes nothing.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

from erpnext.access.permissions.matrix import Matrix

WORKFLOW_STATE_FIELD = {
	"fieldname": "workflow_state",
	"label": "Workflow State",
	"fieldtype": "Link",
	"options": "Workflow State",
	"hidden": 1,
	"allow_on_submit": 1,
	"no_copy": 1,
}


def _norm(value) -> str:
	return "" if value in (None, "") else str(value)


def _field_differs(existing: dict, wanted: dict) -> bool:
	return any(_norm(existing.get(key)) != _norm(value) for key, value in wanted.items())


def _fields_to_write(custom_fields: dict[str, list[dict]]) -> dict[str, list[dict]]:
	"""Only the Custom Field definitions that are missing or differ from the stored row."""
	todo: dict[str, list[dict]] = {}
	for doctype, defs in custom_fields.items():
		for definition in defs:
			name = frappe.db.get_value("Custom Field", {"dt": doctype, "fieldname": definition["fieldname"]})
			if name and not _field_differs(
				frappe.db.get_value("Custom Field", name, "*", as_dict=True), definition
			):
				continue
			todo.setdefault(doctype, []).append(definition)
	return todo


def _workflow_state_fields(m: Matrix) -> dict[str, list[dict]]:
	"""A ``workflow_state`` Custom Field for each workflow DocType that has no such field in any form."""
	out: dict[str, list[dict]] = {}
	for workflow in m.workflows.values():
		for doctype in workflow.get("doctypes", []):
			if doctype not in out and not frappe.get_meta(doctype).get_field("workflow_state"):
				out[doctype] = [dict(WORKFLOW_STATE_FIELD)]
	return out


def _set_property(doctype: str, fieldname: str, prop: str, value: str, property_type: str) -> None:
	"""Make the effective ``prop`` of a field equal ``value``; touch nothing when it already does."""
	field = frappe.get_meta(doctype).get_field(fieldname)
	if field is None:
		frappe.throw(f"RBAC schema: {doctype}.{fieldname} does not exist")
	if _norm(field.get(prop)) == _norm(value):
		return
	name = frappe.db.get_value(
		"Property Setter", {"doc_type": doctype, "field_name": fieldname, "property": prop}
	)
	if name:
		frappe.db.set_value("Property Setter", name, {"value": value, "property_type": property_type})
		frappe.clear_cache(doctype=doctype)
	else:
		make_property_setter(
			doctype, fieldname, prop, value, property_type, validate_fields_for_doctype=False
		)


def _permlevel_targets(m: Matrix):
	"""Yield (doctype, fieldname, level) for every field the matrix puts on a permlevel above 0."""
	for name, entry in m.doctypes.items():
		for level, spec in entry.permlevel.items():
			for ref in spec.get("fields", []):
				child, _, fieldname = ref.rpartition(".")
				yield (child or name), fieldname, level


def ensure_schema(m: Matrix) -> None:
	# DDL first, Property Setters after.
	fields = {dt: list(defs) for dt, defs in (m.custom_fields.get("fields") or {}).items()}
	for doctype, defs in _workflow_state_fields(m).items():
		fields.setdefault(doctype, []).extend(defs)
	todo = _fields_to_write(fields)
	if todo:
		create_custom_fields(todo, update=True)
		for doctype in todo:
			frappe.clear_cache(doctype=doctype)

	for doctype, fieldname, level in _permlevel_targets(m):
		_set_property(doctype, fieldname, "permlevel", str(level), "Int")
	for ps in m.custom_fields.get("property_setters") or []:
		_set_property(ps["doc_type"], ps["field_name"], ps["property"], ps["value"], ps["property_type"])

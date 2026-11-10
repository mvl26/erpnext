from frappe.model.document import Document


class MVLApprovalLimits(Document):
	"""Workflow approval limits H1, H2, H3 — read with frappe.db.get_value("MVL Approval Limits", None, "h1")."""

	pass

"""H3 — Payment Entry may only use Bank Accounts approved through WF-BA — spec 11.3 H3, test T22.

Both ``bank_account`` (the company's) and ``party_bank_account`` (the payee's — a changed payee account is the
classic payment fraud) must sit in the approved state.

R-GATE: ``validate`` returns at once while ``mvl_rbac_enabled`` is off. Administrator and ``ignore_permissions``
saves (system-made entries) skip the check. A site whose Bank Account table has no ``workflow_state`` column yet
is skipped too: the RBAC sync creates that column (``ensure_schema``) before the flag can matter, and failing
closed without it would block every payment on a site that never ran the sync.
"""

import frappe
from frappe import _

from erpnext.access.permissions.sync import is_enabled

APPROVED = "Đã duyệt"
FIELDS = ("bank_account", "party_bank_account")


def _has_state_column() -> bool:
	return frappe.db.has_column("Bank Account", "workflow_state")


def validate(doc, method=None) -> None:
	"""``validate`` hook of Payment Entry: throw naming every Bank Account that is not approved."""
	if not is_enabled():
		return
	if frappe.session.user == "Administrator" or doc.flags.ignore_permissions:
		return
	names = [doc.get(field) for field in FIELDS if doc.get(field)]
	if not names or not _has_state_column():
		return
	bad = []
	for name in dict.fromkeys(names):
		state = frappe.db.get_value("Bank Account", name, "workflow_state")
		if state != APPROVED:
			bad.append(
				_("Tài khoản ngân hàng {0} chưa được duyệt (trạng thái: {1})").format(
					frappe.bold(name), state or _("chưa gửi duyệt")
				)
			)
	if bad:
		frappe.throw("<br>".join(bad), title=_("Tài khoản ngân hàng chưa duyệt"))

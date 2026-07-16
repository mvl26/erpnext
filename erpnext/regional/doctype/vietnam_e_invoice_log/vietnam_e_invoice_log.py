# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

"""Vietnam E Invoice Log — nhật ký phát hành hóa đơn điện tử (NĐ 70/2025).

One row per issuance attempt against the configured HĐĐT provider: payload
snapshot, provider response, số/ký hiệu/mã CQT, and the điều chỉnh/thay thế
lineage. Business logic lives in ``erpnext.regional.vietnam.e_invoice`` — this
controller only guards the lineage links.
"""

import frappe
from frappe import _
from frappe.model.document import Document


class VietnamEInvoiceLog(Document):
	def validate(self):
		self._validate_lineage()

	def _validate_lineage(self):
		for field in ("adjusts", "replaces"):
			target = self.get(field)
			if not target:
				continue
			if target == self.name:
				frappe.throw(_("Bản ghi HĐĐT không thể {0} chính nó").format(field))

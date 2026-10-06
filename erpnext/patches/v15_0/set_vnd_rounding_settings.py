# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Làm tròn tiền cho khớp với hóa đơn điện tử.

Thành tiền đã về số nguyên nhờ `precision = 0` đặt trên từng trường tiền trong
DocType JSON (đơn giá giữ nguyên số lẻ). Patch này bật hai cấu hình còn lại:

- **Commercial Rounding** (nửa lên, 12,5 → 13) thay cho Banker's Rounding
  (12,5 → 12) — HĐĐT và Excel làm tròn nửa lên, lệch cách là lệch 1 đồng.
- **Làm tròn thuế theo từng dòng hàng** (`round_row_wise_tax`): tiền thuế mỗi
  dòng làm tròn rồi mới cộng, đúng như HĐĐT tính.
"""

import frappe


def execute():
	frappe.db.set_single_value("System Settings", "rounding_method", "Commercial Rounding")
	frappe.db.set_single_value("Accounts Settings", "round_row_wise_tax", 1)

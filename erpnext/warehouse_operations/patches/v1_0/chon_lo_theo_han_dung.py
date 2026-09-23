"""Chọn lô theo HẠN DÙNG thay cho FIFO — toàn hệ (chủ đầu tư chốt 22/09/2026).

`Stock Settings.pick_serial_and_batch_based_on` quyết định lô mà ERPNext TỰ ĐIỀN
khi tạo chứng từ xuất (phiếu giao tạo từ đơn bán, phiếu xuất kho…): "Expiry" sắp
theo `expiry_date` và bỏ lô đã hết hạn (`serial_and_batch_bundle.
get_available_batches`, `get_item_details`). Vật tư y tế có hạn dùng: lô gần hết
hạn phải ra trước — FIFO (lô tạo trước) để lô hạn ngắn nằm lại tới khi hết hạn.
Người dùng vẫn sửa lô được trên phiếu; màn hình lấy hàng còn gợi ý "lô nên lấy".
"""

import frappe


def execute():
	frappe.db.set_single_value("Stock Settings", "pick_serial_and_batch_based_on", "Expiry")

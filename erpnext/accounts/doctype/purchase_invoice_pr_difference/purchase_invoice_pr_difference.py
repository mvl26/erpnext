# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

from frappe.model.document import Document


class PurchaseInvoicePRDifference(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		dong_hoa_don: DF.Data | None
		ghi_chu: DF.SmallText | None
		gia_tri_pi: DF.Data | None
		gia_tri_pr: DF.Data | None
		item_code: DF.Link | None
		muc_lech: DF.Float
		nhanh_goi_y: DF.Literal[
			"", "(a) Hóa đơn mua nhập sai", "(b1) Phiếu nhập mua sai", "(b2) Hóa đơn NCC sai", "Cần ghép tay"
		]
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		purchase_receipt: DF.Data | None
		tieu_chi: DF.Literal[
			"",
			"Ghép dòng",
			"Số lượng",
			"Đơn giá",
			"Thuế suất",
			"Thành tiền",
			"Tổng tiền hàng",
			"Tổng thuế",
			"Tổng thanh toán",
		]
	# end: auto-generated types

	pass

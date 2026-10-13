from frappe.model.document import Document


class LocationBalance(Document):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		# Đây là BỘ ĐỆM DẪN XUẤT, không phải nguồn sự thật (đó là Location
		# Ledger Entry) — nên mặc định bỏ qua kiểm tra Link cho so_lo (Link ->
		# Batch): giá trị chỉ để tra cứu song song với sổ, không ép ràng buộc
		# tồn tại. Đặt ở __init__ (không chỉ ở call-site của engine) vì
		# `dung_lai_ton_vi_tri()` insert lại từ dữ liệu sổ có thể mang số lô
		# không còn là Batch hợp lệ, và test brief tự insert trực tiếp dòng
		# tồn với so_lo giả ("LO-MA") mà không truyền ignore_links.
		self.flags.ignore_links = True

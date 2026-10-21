import frappe

# Vai trò duyệt giá có sẵn trên production (quyết định P3: không tạo vai trò mới).
VAI_TRO_DUYET_CO_SAN = "Duyệt giá Himedic"


def execute():
	"""Giá trị đầu cho mục "Kiểm giá bán theo % lãi" trong Selling Settings.

	Trường mới của DocType Single không tự nhận giá trị mặc định khi migrate, nên đặt ở
	đây. Tính năng để TẮT; người có quyền tự bật sau khi rà bảng giá bằng báo cáo
	"Doi Chieu Gia Ban Gia Mua". Chỉ điền ô còn trống, không ghi đè.
	"""
	values = {"ty_le_lai_mac_dinh": 1, "che_do_kiem_gia": "Chỉ ghi nhận"}
	if frappe.db.exists("Role", VAI_TRO_DUYET_CO_SAN):
		values["vai_tro_duyet_gia_lech"] = VAI_TRO_DUYET_CO_SAN

	for field, value in values.items():
		# Đọc thẳng tabSingles: get_single_value đổi ô chưa có thành 0 với trường số.
		current = frappe.db.sql(
			"select value from tabSingles where doctype = 'Selling Settings' and field = %s", field
		)
		current = current[0][0] if current else None
		if current in (None, ""):
			frappe.db.set_single_value("Selling Settings", field, value)

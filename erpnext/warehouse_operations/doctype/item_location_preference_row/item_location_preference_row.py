# Một dòng vị trí của bản gán `Item Location Preference` (22/09/2026 — chủ đầu tư:
# "1 item có thể gán nhiều vị trí khác nhau").
#
# Bảng con thuần dữ liệu: mọi phép kiểm nằm ở `ItemLocationPreference.validate`
# trên bản gán CHA — vì luật "không chồng chính mình" cần nhìn thấy MỌI dòng cùng
# lúc, thứ một dòng bảng con không tự thấy.

from frappe.model.document import Document


class ItemLocationPreferenceRow(Document):
	pass

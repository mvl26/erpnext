"""Vỏ app PDA — giao diện RIÊNG của máy quét, không phải Desk.

VÌ SAO LÀ TRANG WEBSITE: Desk đệm mã nguồn từng trang vào `localStorage` khoá theo
`window._version_number` (`frappe/public/js/frappe/assets.js`). Sửa một trang Desk
mà số phiên bản app không đổi thì máy đã mở trang đó vẫn chạy bản CŨ tới hai ngày —
đo được 23/09/2026: cùng một bản vá, máy này ăn, máy kia không. Trang website với
`no_cache = 1` và tài nguyên mang băm nội dung thì không có lớp đệm đó.
"""

import frappe

no_cache = 1


def get_context(context):
	context.no_header = 1
	context.no_breadcrumbs = 1
	# Vỏ tự lo phần đăng nhập: khách vào thì nó vẽ màn quét thẻ, không đá sang
	# trang khác — chuyển trang giữa chừng trên máy quét là mất trạng thái đang làm.
	context.la_khach = frappe.session.user == "Guest"
	# `frappe.session` KHÔNG tồn tại trên trang website — chỉ `desk.js` (không nạp
	# ở đây) gán nó; `frappe-web.bundle.js` chỉ có `frappe.provide("frappe.session")`
	# dựng một đối tượng RỖNG (`frappe/public/js/frappe/provide.js`). Client không tự
	# biết ai đang đăng nhập, nên tên người dùng phải do MÁY CHỦ đẩy sẵn vào HTML.
	context.nguoi_dung = "" if context.la_khach else frappe.session.user
	return context

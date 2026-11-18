# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Hook `after_request` chèn nút "Về ERP" vào trang Raven, và chỉ vào trang Raven."""

from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from werkzeug.wrappers import Response

from erpnext.utilities import raven

PAGE = "<!doctype html><html><head></head><body><div id='root'></div></body></html>"


def _request(path="/raven/channel/general", method="GET"):
	return SimpleNamespace(path=path, method=method)


def _response(body=PAGE, status=200, mimetype="text/html"):
	return Response(body, status=status, mimetype=mimetype)


class TestRavenBackToErp(FrappeTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")

	def test_chen_nut_truoc_the_dong_body(self):
		response = _response()
		raven.add_back_to_erp_button(response, _request())

		html = response.get_data(as_text=True)
		self.assertIn(raven.SCRIPT_MARKER, html)
		self.assertIn("mvl-back-to-erp", html)
		self.assertTrue(html.index(raven.SCRIPT_MARKER) < html.index("</body>"))
		self.assertEqual(response.content_length, len(response.get_data()))

	def test_logo_di_kem_the_script(self):
		response = _response()
		with patch.object(raven, "get_erp_logo", return_value="/files/logo-cong-ty.png"):
			raven.add_back_to_erp_button(response, _request())
		self.assertIn('data-logo="/files/logo-cong-ty.png"', response.get_data(as_text=True))

	def test_logo_duoc_escape(self):
		response = _response()
		with patch.object(raven, "get_erp_logo", return_value='x.png"><script>alert(1)</script>'):
			raven.add_back_to_erp_button(response, _request())
		html = response.get_data(as_text=True)
		self.assertNotIn("<script>alert(1)", html)
		self.assertIn("&quot;&gt;&lt;script&gt;", html)

	def test_trang_goc_raven_cung_duoc_chen(self):
		response = _response()
		raven.add_back_to_erp_button(response, _request("/raven"))
		self.assertIn(raven.SCRIPT_MARKER, response.get_data(as_text=True))

	def test_goi_hai_lan_chi_chen_mot_lan(self):
		response = _response()
		raven.add_back_to_erp_button(response, _request())
		raven.add_back_to_erp_button(response, _request())
		self.assertEqual(response.get_data(as_text=True).count(raven.SCRIPT_MARKER), 1)

	def test_khong_dung_trang_khong_phai_raven(self):
		cases = {
			"trang Desk": (_request("/app/home"), _response()),
			"app ten bat dau bang raven": (_request("/ravenous"), _response()),
			"POST": (_request(method="POST"), _response()),
			"khong phai HTML": (_request("/raven/sw.js"), _response("x", mimetype="text/javascript")),
			"trang loi": (_request(), _response(status=404)),
			"khong co body": (_request(), _response("<html>no body</html>")),
		}
		for name, (request, response) in cases.items():
			with self.subTest(name):
				before = response.get_data()
				raven.add_back_to_erp_button(response, request)
				self.assertEqual(response.get_data(), before)

	def test_response_none_khong_loi(self):
		raven.add_back_to_erp_button(None, _request())

	def test_guest_khong_co_nut(self):
		frappe.set_user("Guest")
		response = _response()
		raven.add_back_to_erp_button(response, _request())
		self.assertNotIn(raven.SCRIPT_MARKER, response.get_data(as_text=True))

	def test_website_user_khong_co_nut(self):
		response = _response()
		with patch.object(raven.frappe, "get_cached_value", return_value="Website User"):
			raven.add_back_to_erp_button(response, _request())
		self.assertNotIn(raven.SCRIPT_MARKER, response.get_data(as_text=True))

	def test_hook_duoc_dang_ky(self):
		self.assertIn(
			"erpnext.utilities.raven.add_back_to_erp_button",
			frappe.get_hooks("after_request", app_name="erpnext"),
		)

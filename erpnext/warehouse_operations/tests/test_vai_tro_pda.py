# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""T46 — vai trò `MVL Kho PDA` đi qua các hàm của ba trang PDA; `System Manager` không vận hành kho.

Cờ `mvl_rbac_enabled` bật: bộ vai trò là bộ sau go-live. Cờ tắt: `System Manager` vẫn qua
(hành vi hiện tại) để production không đổi trước go-live.
"""

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.warehouse_operations.vitri import lay_hang, o_tem, quet, xep

PDA = "MVL Kho PDA"
SYS = "System Manager"
CO = "erpnext.warehouse_operations.vitri.vai_tro.is_enabled"

# Mỗi hàm kiểm quyền mà ba trang lay-hang-pda, xep-hang-pda, quet-ma-tra-cuu gọi tới.
GUARDS = {
	"quet": quet._kiem_tra_quyen,
	"xep": xep._kiem_tra_quyen,
	"lay_hang": lay_hang._kiem_tra_quyen,
	"o_tem.dat_o": o_tem._kiem_quyen_dat_o,
}


def _qua_duoc(guard, roles, bat):
	with patch(CO, return_value=bat), patch.object(frappe, "get_roles", return_value=list(roles)):
		try:
			guard()
		except frappe.PermissionError:
			return False
	return True


class TestVaiTroPda(FrappeTestCase):
	SHOW_TRANSACTION_COMMIT_WARNINGS = True

	def test_pda_only_passes_when_enabled(self):
		for ten, guard in GUARDS.items():
			self.assertTrue(_qua_duoc(guard, ["Guest", PDA], True), ten)

	def test_system_manager_only_is_blocked_when_enabled(self):
		for ten, guard in GUARDS.items():
			self.assertFalse(_qua_duoc(guard, ["Guest", SYS], True), ten)

	def test_system_manager_still_passes_while_flag_is_off(self):
		for ten, guard in GUARDS.items():
			self.assertTrue(_qua_duoc(guard, ["Guest", SYS], False), ten)

	def test_constants_are_the_post_go_live_sets(self):
		for const in (
			quet.VAI_TRO_DUOC_TRA_CUU,
			xep.VAI_TRO_DUOC_XEP,
			lay_hang.VAI_TRO_DUOC_LAY,
			o_tem.VAI_TRO_DAT_O,
		):
			self.assertIn(PDA, const)
			self.assertNotIn(SYS, const)
		self.assertNotIn(PDA, o_tem.VAI_TRO_DOI_O)

	def _doi_o_qua_duoc(self, roles, bat):
		"""Chạy `doi_o_tren_tem` tới kiểm vai trò nội tuyến (lô chưa có ô); phần sau chạy trên đối tượng giả."""
		lo = MagicMock()
		lo.get.return_value = None
		with (
			patch(CO, return_value=bat),
			patch.object(frappe, "get_roles", return_value=list(roles)),
			patch.object(frappe, "get_doc", return_value=lo),
		):
			try:
				o_tem.doi_o_tren_tem("LO-X", "O-X")
			except frappe.PermissionError:
				return False
			except Exception:
				return True  # qua kiểm vai trò, hỏng ở phần sau (dữ liệu giả)
		return True

	def test_doi_o_tren_tem_inline_check(self):
		self.assertTrue(self._doi_o_qua_duoc(["Guest", PDA], True))
		self.assertFalse(self._doi_o_qua_duoc(["Guest", SYS], True))
		self.assertTrue(self._doi_o_qua_duoc(["Guest", SYS], False))

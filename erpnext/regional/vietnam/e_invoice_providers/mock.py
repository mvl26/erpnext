# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

"""Deterministic in-process HĐĐT provider for tests and development. No network."""

import zlib


def _number_for(reference):
	"""Stable 8-digit invoice number derived from the ERP reference."""
	return f"{zlib.crc32(reference.encode('utf-8')) % 10**8:08d}"


class MockProvider:
	name = "mock"

	def issue(self, payload):
		reference = payload["invoice"]["erp_reference"]
		number = _number_for(reference)
		symbol = payload.get("symbol") or "1C26MOCK"
		return {
			"ok": True,
			"invoice_number": number,
			"invoice_symbol": symbol,
			"cqt_code": f"M1-{number}",
			"xml": (
				f"<HDon><TTChung><KHHDon>{symbol}</KHHDon><SHDon>{number}</SHDon></TTChung>"
				f"<DLHDon>{reference}</DLHDon></HDon>"
			),
		}

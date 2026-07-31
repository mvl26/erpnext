# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Deterministic in-process HĐĐT provider for tests and development. No network."""

import zlib


def _number_for(reference):
	"""Stable 8-digit invoice number derived from the ERP reference."""
	return f"{zlib.crc32(reference.encode('utf-8')) % 10**8:08d}"


class MockProvider:
	name = "mock"

	def issue(self, payload, kind=""):
		"""``kind``: "" (phát hành), "DC" (điều chỉnh) or "TT" (thay thế)."""
		reference = payload["invoice"]["erp_reference"]
		number = _number_for(f"{reference}:{kind}" if kind else reference)
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

	def adjust(self, payload, original=None):
		"""Hóa đơn điều chỉnh cho một hóa đơn đã phát hành."""
		return self.issue(payload, kind="DC")

	def replace(self, payload, original=None):
		"""Hóa đơn thay thế cho một hóa đơn đã phát hành."""
		return self.issue(payload, kind="TT")

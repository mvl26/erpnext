# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Nạp danh mục 23 loại chứng từ TBYT và 92 dòng quy tắc."""

from erpnext.tbyt.setup import setup_tbyt_masters


def execute():
	setup_tbyt_masters()

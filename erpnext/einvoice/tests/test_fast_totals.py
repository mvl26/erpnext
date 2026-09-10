# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Công thức tiền của chứng từ HĐĐT — `erpnext/einvoice/totals.py`.

Thuần túy, không cần cơ sở dữ liệu: tiền của hóa đơn là một hàm của dòng hàng.

Nửa sau của file kiểm **bất biến số học**. Đó là phần quan trọng nhất: một hóa
đơn mà Tiền hàng không đúng bằng tổng các dòng, hay bốn ô nhóm thuế không cộng
đủ Tiền thuế, là hóa đơn kê khai sai — dù từng con số nhìn riêng đều "hợp lý".
"""

from typing import ClassVar

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from erpnext.einvoice.constants import (
	PROCESS_TYPE_DISCOUNT,
	PROCESS_TYPE_GOODS,
	PROCESS_TYPE_NOTE,
	PROCESS_TYPE_PROMOTION,
	PROCESS_TYPE_SPECIAL,
)
from erpnext.einvoice.totals import (
	amount_precision,
	compute_lines,
	dominant_tax_rate,
	summarise,
	total_precision,
)


def line(**values):
	base = {
		"process_type": PROCESS_TYPE_GOODS,
		"item_name": "Hàng X",
		"qty": 1,
		"price": 0,
		"discount_rate": 0,
		"discount_amount": 0,
		"tax_rate": "10",
	}
	base.update(values)
	return frappe._dict(base)


def totals_of(lines, currency="VND", **deductions):
	"""Tính dòng rồi tổng hợp — đúng thứ tự chứng từ thật chạy."""
	compute_lines(lines, amount_precision(currency))
	return summarise(lines, currency, **deductions)


class TestLineFormula(FrappeTestCase):
	"""Từng dòng hàng: thành tiền, chiết khấu, tiền thuế."""

	def test_amount_is_qty_times_price(self):
		lines = [line(qty=10, price=20000)]
		totals_of(lines)
		self.assertEqual(lines[0].amount, 200000)

	def test_tax_is_amount_times_rate(self):
		lines = [line(qty=10, price=20000, tax_rate="10")]
		totals_of(lines)
		self.assertEqual(lines[0].tax_amount, 20000)

	def test_discount_rate_overrides_a_typed_discount_amount(self):
		"""Nhập tỷ lệ thì tỷ lệ thắng — không để hai con số nói hai điều khác nhau."""
		lines = [line(qty=10, price=100000, discount_rate=10, discount_amount=999)]
		totals_of(lines)
		self.assertEqual(lines[0].discount_amount, 100000)
		self.assertEqual(lines[0].amount, 900000)
		self.assertEqual(lines[0].tax_amount, 90000)

	def test_typed_discount_amount_is_kept_when_no_rate_given(self):
		lines = [line(qty=10, price=100000, discount_amount=250000)]
		totals_of(lines)
		self.assertEqual(lines[0].amount, 750000)

	def test_codes_without_a_numeric_rate_carry_no_tax(self):
		"""KCT (-1), không kê khai (-2), thuế suất khác (-8), không ghi (-9)."""
		for rate in ("-1", "-2", "-8", "-9"):
			lines = [line(qty=5, price=100000, tax_rate=rate)]
			totals_of(lines)
			self.assertEqual(lines[0].tax_amount, 0, rate)

	def test_line_number_is_left_alone(self):
		"""`LineNumber` là thẻ tùy chọn của Fast — công thức không tự điền vào.

		Tự đánh số mọi dòng sẽ khiến thẻ đó luôn xuất hiện trong payload, tức là
		đổi cách giao tiếp với Fast chỉ để lấy con số mà lưới đã có ở cột `idx`.
		"""
		lines = [line(qty=1, price=1000) for _ in range(4)]
		totals_of(lines)
		self.assertEqual([row.get("line_number") for row in lines], [None] * 4)


class TestProcessTypeBuckets(FrappeTestCase):
	"""Tính chất dòng quyết định dòng đó chảy vào ô nào của phần Tổng hợp."""

	def test_goods_and_special_lines_make_up_the_net_amount(self):
		lines = [
			line(process_type=PROCESS_TYPE_GOODS, qty=1, price=100000),
			line(process_type=PROCESS_TYPE_SPECIAL, qty=1, price=50000),
		]
		totals = totals_of(lines)
		self.assertEqual(totals["amount"], 150000)
		self.assertEqual(totals["tax_amount"], 15000)

	def test_promotion_line_goes_to_its_own_box_only(self):
		"""Hàng khuyến mại có giá trị nhưng không thu tiền — không vào Tiền hàng."""
		lines = [
			line(process_type=PROCESS_TYPE_GOODS, qty=1, price=100000),
			line(process_type=PROCESS_TYPE_PROMOTION, qty=5, price=8000),
		]
		totals = totals_of(lines)
		self.assertEqual(totals["amount"], 100000)
		self.assertEqual(totals["tax_amount"], 10000)
		self.assertEqual(totals["promotion_amount"], 40000)

	def test_discount_line_lowers_the_net_amount_and_fills_the_discount_box(self):
		"""Dòng chiết khấu nhập số âm: vừa trừ Tiền hàng, vừa hiện ở ô Tiền chiết khấu."""
		lines = [
			line(process_type=PROCESS_TYPE_GOODS, qty=1, price=100000),
			line(process_type=PROCESS_TYPE_DISCOUNT, qty=1, price=-10000),
		]
		totals = totals_of(lines)
		self.assertEqual(totals["amount"], 90000)
		self.assertEqual(totals["tax_amount"], 9000)
		self.assertEqual(totals["discount_amount"], 10000)

	def test_line_level_discounts_also_reach_the_discount_box(self):
		lines = [line(qty=10, price=100000, discount_rate=10)]
		totals = totals_of(lines)
		self.assertEqual(totals["amount"], 900000)
		self.assertEqual(totals["discount_amount"], 100000)

	def test_note_line_changes_nothing(self):
		lines = [
			line(process_type=PROCESS_TYPE_GOODS, qty=1, price=100000),
			line(process_type=PROCESS_TYPE_NOTE, qty=0, price=0, tax_rate="-9"),
		]
		totals = totals_of(lines)
		self.assertEqual(totals["amount"], 100000)
		self.assertEqual(totals["tax_amount"], 10000)
		self.assertEqual(totals["promotion_amount"], 0)
		self.assertEqual(totals["discount_amount"], 0)

	def test_blank_process_type_is_treated_as_goods(self):
		"""Bản nháp mới nhập dở chưa chọn Tính chất vẫn phải ra tổng đúng."""
		lines = [line(process_type="", qty=1, price=100000)]
		self.assertEqual(totals_of(lines)["amount"], 100000)

	def test_the_worked_example_from_the_design(self):
		"""Ví dụ đã chốt: hàng + khuyến mại + chiết khấu + ghi chú trên cùng hóa đơn."""
		lines = [
			line(process_type=PROCESS_TYPE_GOODS, qty=10, price=20000),
			line(process_type=PROCESS_TYPE_PROMOTION, qty=5, price=8000),
			line(process_type=PROCESS_TYPE_DISCOUNT, qty=1, price=-10000),
			line(process_type=PROCESS_TYPE_NOTE, qty=0, price=0, tax_rate="-9"),
		]
		totals = totals_of(lines)
		self.assertEqual(totals["amount"], 190000)
		self.assertEqual(totals["promotion_amount"], 40000)
		self.assertEqual(totals["discount_amount"], 10000)
		self.assertEqual(totals["tax_amount"], 19000)
		self.assertEqual(totals["tax_amount_10"], 19000)
		self.assertEqual(totals["total_amount"], 209000)


class TestMasterSummary(FrappeTestCase):
	def test_deductions_come_off_the_grand_total(self):
		lines = [line(qty=1, price=10_000_000)]
		totals = totals_of(lines, deduction_amount=1_000_000, deduction_amount_other=500_000)
		# 10.000.000 + 1.000.000 thuế - 1.500.000 giảm trừ
		self.assertEqual(totals["total_amount"], 9_500_000)

	def test_tax_groups_split_by_rate(self):
		lines = [
			line(qty=1, price=1_000_000, tax_rate="10"),
			line(qty=1, price=1_000_000, tax_rate="5"),
			line(qty=1, price=1_000_000, tax_rate="0"),
			line(qty=1, price=1_000_000, tax_rate="-1"),
		]
		totals = totals_of(lines)
		self.assertEqual(totals["tax_amount_10"], 100_000)
		self.assertEqual(totals["tax_amount_5"], 50_000)
		self.assertEqual(totals["tax_amount_0"], 0)
		self.assertEqual(totals["tax_amount_free"], 0)

	def test_eight_percent_tax_has_no_group_box(self):
		"""Bốn thẻ của Fast không có ô cho 8% — phải lộ ra chứ không nhét vào ô 10%."""
		lines = [line(qty=1, price=1_000_000, tax_rate="8")]
		totals = totals_of(lines)
		self.assertEqual(totals["tax_amount"], 80_000)
		self.assertEqual(totals["tax_amount_10"], 0)
		self.assertEqual(totals["unbucketed"], 80_000)

	def test_promotion_tax_stays_out_of_the_group_boxes(self):
		"""Thuế của dòng khuyến mại không vào Tiền thuế thì cũng không vào ô nhóm."""
		lines = [
			line(process_type=PROCESS_TYPE_GOODS, qty=1, price=100000),
			line(process_type=PROCESS_TYPE_PROMOTION, qty=1, price=100000),
		]
		totals = totals_of(lines)
		self.assertEqual(totals["tax_amount"], 10000)
		self.assertEqual(totals["tax_amount_10"], 10000)

	def test_dominant_tax_rate_follows_the_bulk_of_the_money(self):
		lines = [
			line(qty=1, price=1_000_000, tax_rate="5"),
			line(qty=1, price=9_000_000, tax_rate="10"),
		]
		totals_of(lines)
		self.assertEqual(dominant_tax_rate(lines), "10")

	def test_no_lines_gives_zeroes_not_errors(self):
		totals = totals_of([])
		self.assertEqual(totals["amount"], 0)
		self.assertEqual(totals["tax_amount"], 0)
		self.assertEqual(totals["total_amount"], 0)


class TestArithmeticInvariants(FrappeTestCase):
	"""Các đẳng thức phải đúng với mọi hóa đơn — đây là "không lệch số"."""

	CASES: ClassVar[dict] = {
		"chỉ hàng hóa": [line(qty=3, price=333_333, tax_rate="10")],
		"nhiều thuế suất": [
			line(qty=7, price=142_857, tax_rate="10"),
			line(qty=3, price=99_999, tax_rate="5"),
			line(qty=1, price=1_000_001, tax_rate="8"),
			line(qty=2, price=500_000, tax_rate="-1"),
			line(qty=4, price=250_007, tax_rate="0"),
		],
		"có khuyến mại, chiết khấu, ghi chú": [
			line(qty=11, price=90_909, tax_rate="10"),
			line(process_type=PROCESS_TYPE_PROMOTION, qty=3, price=33_333),
			line(process_type=PROCESS_TYPE_DISCOUNT, qty=1, price=-77_777),
			line(process_type=PROCESS_TYPE_NOTE, qty=0, price=0, tax_rate="-9"),
			line(process_type=PROCESS_TYPE_SPECIAL, qty=6, price=16_667, tax_rate="5"),
		],
		"chiết khấu theo tỷ lệ lẻ": [
			line(qty=9, price=111_111, discount_rate=7.5, tax_rate="10"),
			line(qty=13, price=76_923, discount_rate=3.33, tax_rate="5"),
		],
	}

	def _each_case(self):
		for label, template in self.CASES.items():
			lines = [frappe._dict(row) for row in template]
			yield label, lines, totals_of(lines)

	def test_net_amount_equals_the_sum_of_the_billable_lines(self):
		from erpnext.einvoice.totals import is_billable

		for label, lines, totals in self._each_case():
			expected = sum(row.amount for row in lines if is_billable(row))
			self.assertEqual(totals["amount"], flt(expected, 2), label)

	def test_tax_equals_the_sum_of_the_billable_line_tax(self):
		from erpnext.einvoice.totals import is_billable

		for label, lines, totals in self._each_case():
			expected = sum(row.tax_amount for row in lines if is_billable(row))
			self.assertEqual(totals["tax_amount"], flt(expected, 2), label)

	def test_group_boxes_plus_the_unboxed_part_equal_the_tax(self):
		for label, _lines, totals in self._each_case():
			boxed = (
				totals["tax_amount_free"]
				+ totals["tax_amount_0"]
				+ totals["tax_amount_5"]
				+ totals["tax_amount_10"]
			)
			self.assertEqual(flt(boxed + totals["unbucketed"], 2), totals["tax_amount"], label)

	def test_grand_total_is_net_plus_tax_minus_deductions(self):
		for label, template in self.CASES.items():
			lines = [frappe._dict(row) for row in template]
			totals = totals_of(lines, deduction_amount=1234, deduction_amount_other=567)
			self.assertEqual(
				totals["total_amount"],
				flt(totals["amount"] + totals["tax_amount"] - 1234 - 567, total_precision("VND")),
				label,
			)

	def test_only_the_grand_total_is_rounded_to_whole_dong(self):
		"""VND: Tiền hàng và Tiền thuế giữ hai số lẻ, chỉ Tổng thanh toán mới tròn."""
		for label, _lines, totals in self._each_case():
			self.assertEqual(
				totals["total_amount"],
				int(totals["total_amount"]),
				f"{label} · total_amount = {totals['total_amount']}",
			)
			for field, value in totals.items():
				if field in ("tax_rate", "total_amount"):
					continue
				self.assertEqual(value, flt(value, 2), f"{label} · {field} quá hai số lẻ = {value}")

	def test_components_keep_two_decimals_and_the_total_rounds_once(self):
		"""Đơn giá lẻ: thành phần giữ số lẻ, chỉ số phải thu cuối cùng mới làm tròn."""
		lines = [line(qty=1, price=1000.4, tax_rate="10") for _ in range(10)]
		totals = totals_of(lines)
		self.assertEqual([row.amount for row in lines], [1000.4] * 10)
		self.assertEqual([row.tax_amount for row in lines], [100.04] * 10)
		self.assertEqual(totals["amount"], 10_004)
		self.assertEqual(totals["tax_amount"], 1000.4)
		# 10.004 + 1.000,40 = 11.004,40 → số phải thu là 11.004 đồng chẵn.
		self.assertEqual(totals["total_amount"], 11_004)

	def test_grand_total_absorbs_at_most_half_a_dong(self):
		"""Chênh lệch làm tròn không bao giờ vượt nửa đồng — làm tròn đúng một lần."""
		lines = [line(qty=1, price=1234.56, tax_rate="8")]
		totals = totals_of(lines)
		self.assertEqual(totals["amount"], 1234.56)
		self.assertEqual(totals["tax_amount"], 98.76)
		self.assertEqual(totals["total_amount"], 1333)
		self.assertLessEqual(abs(totals["amount"] + totals["tax_amount"] - totals["total_amount"]), 0.5)

	def test_foreign_currency_keeps_two_decimals(self):
		"""Ngoại tệ giữ hai số lẻ — không bị làm tròn về đồng nguyên như VND."""
		lines = [line(qty=3, price=10.34, tax_rate="10")]
		totals = totals_of(lines, currency="USD")
		self.assertEqual(lines[0].amount, 31.02)
		self.assertEqual(totals["amount"], 31.02)
		self.assertEqual(totals["tax_amount"], 3.1)

"""H2 — line prices must match the expected price — spec 11.3 H2, D4 and 11.1 note; plan review row R-21.

``validate`` runs on Quotation, Sales Order, Sales Invoice (selling side, bypassed by SM) and Purchase Order,
Purchase Invoice (buying side, bypassed by PM). "Update Items" on a submitted Sales Order / Purchase Order
(``accounts_controller.update_child_qty_rate``) never runs ``validate`` and writes every child row before the final
``parent.save()``, so no document hook can see the old prices there: the loop calls :func:`check_update_item` for
each row just before it is written (a core edit marked "Miyano RBAC H2").
Price control is a hook rather than a perm level on ``rate``: frappe resets a field the user may not write to its
default on new rows, which would wipe the rate (spec 11.1).

Expected price of a row (:func:`expected_rate`), first hit wins:

1. the source row the line was copied from (R-21), NEAREST first — SI ``sales_invoice_item`` (returns),
   ``dn_detail``, ``so_detail``; PI ``purchase_invoice_item`` (returns), ``pr_detail``, ``po_detail``; SO
   ``quotation_item``; PO ``supplier_quotation_item``. A PI made from a PR carries both ``pr_detail`` and
   ``po_detail``, and the PR rate may legitimately differ from the PO (Buying Settings "Warn"), so the PR row wins.
   A source counts only when its parent is submitted and holds the same item and party — a link forged to someone
   else's cheaper row is ignored. A Quotation to a Lead / Prospect matches the Customer made from it
   (``Customer.lead_name`` / ``prospect_name``, as ``quotation._make_customer`` resolves it);
2. ``blanket_order`` — the raw Blanket Order Item ``rate``: the Blanket Order Item has no UOM and ERPNext copies
   ``blanket_order_rate`` straight into the row (``taxes_and_totals.js`` ``apply_pricing_rule_on_item``), so it
   is not scaled by ``conversion_factor``. Conditions follow ``get_blanket_order_details``: submitted, same
   company, ``to_date`` not before the document date; plus the party must be the document's (or empty);
3. Item Price, through ERPNext's own ``get_price_list_rate_for`` with the args ``get_item_details`` would build
   (party-specific price first, then the general one in the row UOM, then the stock UOM times
   ``conversion_factor``; ``valid_from`` newest first; ``packing_unit`` checked; variant falls back to its
   template), converted to the document currency by ``plc_conversion_rate / conversion_rate``. The
   ``price_list_uom_dependant`` arg is read exactly as ``get_price_list_currency_and_exchange_rate`` reads it, so
   Price List ``price_not_uom_dependent`` is honoured as far as ERPNext honours it when it fills the rate.

No price found means the row is not checked. A row priced by a Pricing Rule — the rules themselves are maintained
by managers — is compared to the rule price instead, but only when the row's ``pricing_rules`` are exactly the rules
ERPNext would apply to it now (:func:`_fresh_pricing`); the client-sent list alone is not trusted, since ERPNext's
own save path takes it at face value. The rule price (:func:`_rule_rate`) is rebuilt from trusted inputs: the
rule's own rate, discount and margin applied to the Item Price above — never to the row's ``price_list_rate``,
which ERPNext keeps as the client sent it (``set_missing_item_details``) and derives ``rate`` from. A rule row with
no Item Price and no rule rate has nothing to anchor it and is not checked, like any row without a price.
A free-item row is skipped only when its product-discount rule applies to another row of the document
and gives away that item; a free item without a backed rule is checked like any row.
A source row also fixes ``discount_percentage``; Blanket Order and Item Price carry no discount, so there the
final ``rate`` alone is compared.

``mvl_dung_gia_hd`` (Sales Order, drives WF-SO self-approval, D4) is 1 iff the order has rows and every row has a
``blanket_order`` whose rate it matches. It is a fact about the prices, so it is computed for every user —
SM, Administrator and ``ignore_permissions`` saves included — before the bypass checks.

The flag is NOT recomputed after submit: it only drives the Nháp self-approval transition of WF-SO, which is over
once the order is submitted.

R-GATE: both entry points return at once while ``mvl_rbac_enabled`` is off. Administrator and ``ignore_permissions``
saves (system-made documents) skip the price check.
"""

from functools import lru_cache

import frappe
from frappe import _
from frappe.utils import flt, fmt_money, getdate, nowdate

from erpnext.access.permissions.sync import is_enabled

SELLING = frozenset(("Quotation", "Sales Order", "Sales Invoice"))
BUYING = frozenset(("Purchase Order", "Purchase Invoice"))
BYPASS_CODE = {"selling": "SM", "buying": "PM"}
FLAG = "mvl_dung_gia_hd"

# nearest source first: row link field → (source child DocType, its parent DocType, party field on that parent)
SOURCE_LINKS = {
	"Sales Invoice": (
		("sales_invoice_item", "Sales Invoice Item", "Sales Invoice", "customer"),
		("dn_detail", "Delivery Note Item", "Delivery Note", "customer"),
		("so_detail", "Sales Order Item", "Sales Order", "customer"),
	),
	"Purchase Invoice": (
		("purchase_invoice_item", "Purchase Invoice Item", "Purchase Invoice", "supplier"),
		("pr_detail", "Purchase Receipt Item", "Purchase Receipt", "supplier"),
		("po_detail", "Purchase Order Item", "Purchase Order", "supplier"),
	),
	"Sales Order": (("quotation_item", "Quotation Item", "Quotation", "party_name"),),
	"Purchase Order": (
		("supplier_quotation_item", "Supplier Quotation Item", "Supplier Quotation", "supplier"),
	),
}
# Quotation.quotation_to → the Customer field that remembers the party it was made from (quotation._make_customer)
CONVERTED_PARTY_FIELD = {"Lead": "lead_name", "Prospect": "prospect_name"}


def _side(doctype: str) -> str | None:
	if doctype in SELLING:
		return "selling"
	if doctype in BUYING:
		return "buying"
	return None


@lru_cache(maxsize=2)
def _bypass_roles(side: str) -> frozenset[str]:
	from erpnext.access.permissions.matrix import load_matrix

	return frozenset(load_matrix().role_names(BYPASS_CODE[side]))


def _party(doc) -> str | None:
	if doc.doctype == "Quotation":
		return doc.get("party_name") if doc.get("quotation_to") == "Customer" else None
	return doc.get("customer") if _side(doc.doctype) == "selling" else doc.get("supplier")


def _doc_date(doc):
	return getdate(doc.get("transaction_date") or doc.get("posting_date") or nowdate())


def _factor(row) -> float:
	return flt(row.get("conversion_factor")) or 1.0


# -- price sources -----------------------------------------------------------------------------------------


def _source_party_matches(doc, parent_doctype: str, src) -> bool:
	party = _party(doc)
	if not party:
		return False
	if src.party == party:
		return True
	converted_field = CONVERTED_PARTY_FIELD.get(src.quotation_to) if parent_doctype == "Quotation" else None
	return bool(converted_field) and frappe.db.get_value("Customer", party, converted_field) == src.party


def _source_price(doc, row) -> tuple[float, float] | None:
	"""(rate, discount_percentage) of the nearest valid source row, rescaled to the row's UOM; None if none."""
	for link_field, child_doctype, parent_doctype, party_field in SOURCE_LINKS.get(doc.doctype, ()):
		name = row.get(link_field)
		if not name:
			continue
		child = frappe.qb.DocType(child_doctype)
		parent = frappe.qb.DocType(parent_doctype)
		columns = [
			child.rate,
			child.discount_percentage,
			child.conversion_factor,
			parent[party_field].as_("party"),
		]
		if parent_doctype == "Quotation":
			columns.append(parent.quotation_to)
		found = (
			frappe.qb.from_(child)
			.join(parent)
			.on(parent.name == child.parent)
			.select(*columns)
			.where(
				(child.name == name)
				& (child.parenttype == parent_doctype)
				& (child.item_code == row.item_code)
				& (parent.docstatus == 1)
			)
			.run(as_dict=True)
		)
		if found and _source_party_matches(doc, parent_doctype, found[0]):
			src = found[0]
			rate = flt(src.rate) / (flt(src.conversion_factor) or 1.0) * _factor(row)
			return rate, flt(src.discount_percentage)
	return None


def _blanket_rate(doc, row) -> float | None:
	"""Raw Blanket Order Item rate (ERPNext copies it into ``rate`` unscaled); None if the order does not apply."""
	if not row.get("blanket_order"):
		return None
	bo = frappe.qb.DocType("Blanket Order")
	boi = frappe.qb.DocType("Blanket Order Item")
	party_field = bo.customer if _side(doc.doctype) == "selling" else bo.supplier
	found = (
		frappe.qb.from_(bo)
		.join(boi)
		.on(boi.parent == bo.name)
		.select(boi.rate)
		.where(
			(bo.name == row.blanket_order)
			& (boi.item_code == row.item_code)
			& (bo.docstatus == 1)
			& (bo.company == doc.get("company"))
			& (bo.to_date.isnull() | (bo.to_date >= _doc_date(doc)))
			& (party_field.isnull() | (party_field == "") | (party_field == (_party(doc) or "")))
		)
		.run(as_dict=True)
	)
	return flt(found[0].rate) if found else None


def _item_price_rate(doc, row) -> float | None:
	"""ERPNext's own Item Price pick for this row, in document currency; None if none applies."""
	from erpnext.stock.doctype.price_list.price_list import get_price_list_details
	from erpnext.stock.get_item_details import get_price_list_rate_for

	side = _side(doc.doctype)
	price_list = doc.get("selling_price_list" if side == "selling" else "buying_price_list")
	if not price_list or not frappe.db.get_value("Price List", price_list, "enabled", cache=True):
		return None
	party = _party(doc)
	args = frappe._dict(
		price_list=price_list,
		customer=party if side == "selling" else None,
		supplier=party if side == "buying" else None,
		uom=row.get("uom"),
		stock_uom=row.get("stock_uom") or frappe.get_cached_value("Item", row.item_code, "stock_uom"),
		conversion_factor=_factor(row),
		qty=row.get("qty"),
		transaction_date=_doc_date(doc),
		batch_no=row.get("batch_no"),
		# same key get_price_list_currency_and_exchange_rate reads (get_item_details.py:1455)
		price_list_uom_dependant=get_price_list_details(price_list).get("price_list_uom_dependant"),
	)
	rate = get_price_list_rate_for(args, row.item_code)
	if rate is None:
		template = frappe.get_cached_value("Item", row.item_code, "variant_of")
		rate = get_price_list_rate_for(args, template) if template else None
	if rate is None:
		return None
	conversion_rate = flt(doc.get("conversion_rate")) or 1.0
	plc_conversion_rate = flt(doc.get("plc_conversion_rate")) or conversion_rate
	return flt(rate) * plc_conversion_rate / conversion_rate


def _expected(doc, row) -> tuple[float, float | None] | None:
	"""(expected rate, expected discount % or None when the source fixes none)."""
	source = _source_price(doc, row)
	if source is not None:
		return source
	blanket = _blanket_rate(doc, row)
	if blanket is not None:
		return blanket, None
	price = _item_price_rate(doc, row)
	if price is not None:
		return price, None
	return None


def expected_rate(doc, row) -> float | None:
	"""Expected ``rate`` of ``row`` in ``doc`` (lookup order in the module docstring); None means not checked."""
	expected = _expected(doc, row)
	return expected[0] if expected else None


# -- hooks --------------------------------------------------------------------------------------------------


def _same(a, b, precision) -> bool:
	return flt(a, precision) == flt(b, precision)


def _set_contract_flag(doc) -> None:
	if not doc.meta.has_field(FLAG):
		return
	rows = doc.get("items") or []
	at_contract_price = bool(rows)
	for row in rows:
		blanket = _blanket_rate(doc, row) if row.get("item_code") else None
		if blanket is None or not _same(row.rate, blanket, row.precision("rate")):
			at_contract_price = False
			break
	doc.set(FLAG, 1 if at_contract_price else 0)


def _row_rules(row) -> set[str]:
	from erpnext.accounts.doctype.pricing_rule.utils import get_applied_pricing_rules

	return {
		name.strip() for name in get_applied_pricing_rules(row.get("pricing_rules")) if name and name.strip()
	}


def _fresh_pricing(doc, row, list_rate: float | None) -> frappe._dict:
	"""What ERPNext's pricing rules give ``row`` now: rule names, rate or discount, margin.

	Args are built the way ``AccountsController.set_missing_item_details`` builds them for ``get_item_details``,
	and ``get_pricing_rule_for_item`` runs WITHOUT ``for_validate``: on save ERPNext passes ``for_validate=True``,
	which takes the row's own ``pricing_rules`` at face value (``get_applied_pricing_rules``) — a list the client
	can forge. The row's list is left out of the args so the lookup neither trusts nor strips it, and
	``price_list_rate`` is the Item Price ``list_rate`` (0 when none), as ``get_item_details`` hands it to the rules
	— a discount amount or an amount threshold computed from the client's value could be steered.
	"""
	from erpnext.accounts.doctype.pricing_rule.pricing_rule import get_pricing_rule_for_item
	from erpnext.stock.get_item_details import process_args

	args = {fieldname: doc.get(fieldname) for fieldname in doc.meta.get_valid_columns()}
	if doc.doctype in ("Quotation", "Sales Order", "Delivery Note", "Sales Invoice"):
		args["document_type"] = f"{doc.doctype} Item"
	if doc.doctype == "Quotation" and doc.get("quotation_to") == "Customer" and doc.get("party_name"):
		args["customer"] = doc.party_name
	args.update(row.as_dict())
	args.update(
		doctype=doc.doctype,
		name=doc.name,
		child_doctype=row.doctype,
		child_docname=row.name,
		ignore_pricing_rule=doc.get("ignore_pricing_rule") or 0,
		pricing_rules=None,
		price_list_rate=flt(list_rate),
	)
	if not args.get("transaction_date"):
		args["transaction_date"] = args.get("posting_date")
	return frappe._dict(get_pricing_rule_for_item(process_args(args), doc=doc) or {})


def _fresh_rules(doc, row) -> set[str]:
	"""Names of the Pricing Rules ERPNext itself would apply to ``row`` now."""
	out = _fresh_pricing(doc, row, _item_price_rate(doc, row))
	return _row_rules(frappe._dict(pricing_rules=out.get("pricing_rules")))


def _rule_rate(out, list_rate: float | None) -> float | None:
	"""The ``rate`` ERPNext ends with on a rule-priced row, from ``out`` (:func:`_fresh_pricing`) and the Item Price.

	Mirrors the save path: ``AccountsController.apply_pricing_rule_on_items`` puts a "Rate" rule's price in
	``price_list_rate``; ``calculate_taxes_and_totals.calculate_item_values`` then takes the discount percentage,
	else the discount amount, off ``price_list_rate`` — or off the rate with margin when the rules carry a margin
	(``calculate_margin`` reads it from the rules, not the row). None when there is no price to start from.
	"""
	if out.get("pricing_rule_for") == "Rate" and flt(out.get("price_list_rate")):
		list_rate = flt(out.price_list_rate)
	if not list_rate:
		return None
	percentage, amount = flt(out.get("discount_percentage")), flt(out.get("discount_amount"))
	if percentage == 100:
		return 0.0
	base = list_rate
	margin = flt(out.get("margin_rate_or_amount"))
	if out.get("margin_type") in ("Percentage", "Amount") and margin:
		with_margin = list_rate + (list_rate * margin / 100 if out.margin_type == "Percentage" else margin)
		if with_margin > 0:
			base = with_margin
	if percentage:
		return base * (1.0 - percentage / 100.0)
	return base - amount


def _free_row_backed(doc, row, applied: set[str]) -> bool:
	"""A free-item row is backed when each of its rules is a product-discount rule ERPNext applies to another
	row of this document now, and gives away this very item (``free_item`` or ``same_item``)."""
	for name in _row_rules(row):
		if name not in applied:
			return False
		rule = frappe.db.get_value(
			"Pricing Rule", name, ["price_or_product_discount", "free_item", "same_item"], as_dict=True
		)
		if not rule or rule.price_or_product_discount != "Product":
			return False
		if rule.free_item != row.item_code and not rule.same_item:
			return False
	return True


def _rule_priced_rows(doc) -> dict[int, float | None]:
	"""``id()`` of the rule-priced rows → their rule price (:func:`_rule_rate`; None = not checked).

	A row counts only when its ``pricing_rules`` equal the rules ERPNext would apply now; a row whose list differs
	(a forged or stale rule name) is price-checked like any other row. A free-item row is not priced by
	``get_pricing_rule_for_item`` (it returns nothing for ``is_free_item``), so it is skipped only when
	:func:`_free_row_backed`.
	"""
	if doc.get("ignore_pricing_rule"):
		return {}
	rows = [row for row in doc.get("items") or [] if row.get("item_code") and row.get("pricing_rules")]
	priced, applied = {}, set()
	for row in rows:
		if row.get("is_free_item"):
			continue
		list_rate = _item_price_rate(doc, row)
		out = _fresh_pricing(doc, row, list_rate)
		fresh = _row_rules(frappe._dict(pricing_rules=out.get("pricing_rules")))
		applied |= fresh
		if fresh and fresh == _row_rules(row):
			priced[id(row)] = _rule_rate(out, list_rate)
	for row in rows:
		if row.get("is_free_item") and _free_row_backed(doc, row, applied):
			priced[id(row)] = None
	return priced


def _money(value, precision) -> str:
	return fmt_money(flt(value, precision), precision=precision)


def _bypassed(doc) -> bool:
	user = frappe.session.user
	if user == "Administrator" or doc.flags.ignore_permissions:
		return True
	return bool(set(frappe.get_roles(user)) & _bypass_roles(_side(doc.doctype)))


def _row_error(doc, row, compare_discount: bool = True) -> str | None:
	"""Message for ``row`` if its rate (or the source row's discount) is off the expected price, else None."""
	expected = _expected(doc, row)
	if expected is None:
		return None
	rate, discount = expected
	precision = row.precision("rate")
	if not _same(row.rate, rate, precision):
		return _("Dòng {0} {1}: giá {2} khác giá chuẩn {3}").format(
			row.idx, row.item_code, _money(row.rate, precision), _money(rate, precision)
		)
	if compare_discount and discount is not None:
		dp = row.precision("discount_percentage")
		if not _same(row.discount_percentage, discount, dp):
			return _("Dòng {0} {1}: chiết khấu {2}% khác chiết khấu chuẩn {3}%").format(
				row.idx, row.item_code, flt(row.discount_percentage, dp), flt(discount, dp)
			)
	return None


def _rule_row_error(row, rate: float | None) -> str | None:
	"""Message for a rule-priced ``row`` whose rate is off its rule price (None = not checked)."""
	if rate is None:
		return None
	precision = row.precision("rate")
	if _same(row.rate, rate, precision):
		return None
	return _("Dòng {0} {1}: giá {2} khác giá theo quy tắc giá {3}").format(
		row.idx, row.item_code, _money(row.rate, precision), _money(rate, precision)
	)


def _throw(errors) -> None:
	frappe.throw("<br>".join(errors), title=_("Giá khác giá chuẩn"))


def validate(doc, method=None) -> None:
	"""``validate`` hook: recompute the SO flag, then throw once listing every row off the expected price."""
	if not is_enabled() or _side(doc.doctype) is None:
		return
	if doc.doctype == "Sales Order":
		_set_contract_flag(doc)
	if _bypassed(doc):
		return
	errors = []
	rule_priced = _rule_priced_rows(doc)
	for row in doc.get("items") or []:
		if not row.get("item_code"):
			continue
		if id(row) in rule_priced:
			error = _rule_row_error(row, rule_priced[id(row)])
		else:
			error = _row_error(doc, row)
		if error:
			errors.append(error)
	if errors:
		_throw(errors)


# `discount_percentage` is left out on purpose: update_child_qty_rate re-derives it from rate / price_list_rate on
# every processed row, so a qty-only update of a "Discount Amount" pricing-rule line (0 → 7 %) would look like a
# reprice; a real price change shows in `rate`. `item_code` cannot change for an existing row in that loop.
REPRICE_FIELDS = ("rate", "uom", "conversion_factor")


def _repriced(row, old) -> bool:
	if old is None:
		return True
	if (row.get("uom") or "") != (old.get("uom") or ""):
		return True
	return any(
		not _same(row.get(field), old.get(field), row.precision(field))
		for field in ("rate", "conversion_factor")
	)


def check_update_item(parent, child_item, old=None) -> None:
	"""Called by ``update_child_qty_rate`` for each Sales/Purchase Order row just before it is written.

	``old`` holds the row's ``REPRICE_FIELDS`` before the loop changed them (None for a new row). Only a new or
	repriced row (``rate``, ``uom`` or ``conversion_factor`` changed) is checked — a qty/date-only change passes even if the price list moved since submit. Pricing-rule
	rows are NOT skipped here: ``update_child_qty_rate`` never re-applies the rules. The discount is not compared
	either: that loop derives ``discount_percentage`` from the new rate and the stored ``price_list_rate``.
	"""
	if not is_enabled() or _side(parent.doctype) is None or _bypassed(parent):
		return
	if not child_item.get("item_code") or not _repriced(child_item, old):
		return
	error = _row_error(parent, child_item, compare_discount=False)
	if error:
		_throw([error])

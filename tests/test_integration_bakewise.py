import pytest
from decimal import Decimal
from models.transaction import Transaction


def test_pos_to_cart_to_total(sample_product, sample_inventory):
    """
    Integration test:
    Product + Inventory + Transaction
    Checks if adding an item connects properly to the cart and total.
    """
    t = Transaction(1, "admin")

    result = t.add_item(sample_product, 2, sample_inventory)

    assert result is True or result is None
    assert len(t.items) == 1
    assert t.items[0]["product"].name == sample_product.name
    assert t.items[0]["quantity"] == 2
    assert t.get_total() == sample_product.price * 2


def test_insufficient_stock_blocks_adding(sample_product, sample_inventory):
    """
    Integration test:
    Inventory + Transaction
    Checks if cart insertion is blocked when stock is insufficient.
    """
    t = Transaction(2, "admin")

    result = t.add_item(sample_product, 9999, sample_inventory)

    assert result is False or len(t.items) == 0
    assert len(t.items) == 0


def test_checkout_cash_flow(sample_product, sample_inventory):
    """
    Integration test:
    Product + Inventory + Transaction + Checkout
    Checks if checkout succeeds when payment is enough.
    """
    t = Transaction(3, "admin")
    t.add_item(sample_product, 2, sample_inventory)

    total = t.get_total()
    amount_paid = total + Decimal("50")

    result = t.checkout("Cash", amount_paid, sample_inventory)

    assert result is True
    assert t.amount_paid == amount_paid
    assert t.payment_method.lower() == "cash"


def test_checkout_rejects_insufficient_cash(sample_product, sample_inventory):
    """
    Integration test:
    Transaction + Checkout validation
    Checks if checkout fails when payment is not enough.
    """
    t = Transaction(4, "admin")
    t.add_item(sample_product, 2, sample_inventory)

    total = t.get_total()
    amount_paid = total - Decimal("1")

    result = t.checkout("Cash", amount_paid, sample_inventory)

    assert result is False


def test_void_transaction_flow(sample_product, sample_inventory):
    """
    Integration test:
    Transaction lifecycle
    Checks if a transaction can be voided properly after item insertion.
    """
    t = Transaction(5, "admin")
    t.add_item(sample_product, 1, sample_inventory)

    result = t.void_transaction()

    assert result is True or t.is_voided is True
    assert t.is_voided is True


def test_change_computation_after_cash_checkout(sample_product, sample_inventory):
    """
    Integration test:
    Checkout + change computation
    Checks if change is computed correctly after successful cash payment.
    """
    t = Transaction(6, "admin")
    t.add_item(sample_product, 3, sample_inventory)

    total = t.get_total()
    amount_paid = total + Decimal("20")

    t.checkout("Cash", amount_paid, sample_inventory)
    change = t.get_change()

    assert change == Decimal("20")


def test_non_cash_exact_payment_has_no_change(sample_product, sample_inventory):
    """
    Integration test:
    Non-cash checkout behavior
    Checks if exact non-cash payments return zero change.
    """
    t = Transaction(7, "admin")
    t.add_item(sample_product, 1, sample_inventory)

    total = t.get_total()
    t.checkout("GCash", total, sample_inventory)

    assert t.get_change() == 0 or t.get_change() == Decimal("0")


def test_non_cash_overpayment_computes_change(sample_product, sample_inventory):
    """
    Integration test:
    Non-cash checkout behavior
    Checks if overpayment still computes change.
    """
    t = Transaction(7, "admin")
    t.add_item(sample_product, 1, sample_inventory)

    total = t.get_total()
    t.checkout("GCash", total + Decimal("20"), sample_inventory)

    assert t.get_change() == Decimal("20")


def test_checkout_rejects_insufficient_non_cash(sample_product, sample_inventory):
    """
    Integration test:
    Transaction + Checkout validation
    Checks if any payment method fails when payment is below total.
    """
    t = Transaction(7, "admin")
    t.add_item(sample_product, 1, sample_inventory)

    result = t.checkout("GCash", t.get_total() - Decimal("1"), sample_inventory)

    assert result is False


def test_empty_cart_checkout_fails(sample_inventory):
    """
    Integration test:
    Transaction validation
    Checks if checkout is rejected when cart is empty.
    """
    t = Transaction(8, "admin")

    result = t.checkout("Cash", Decimal("100"), sample_inventory)

    assert result is False

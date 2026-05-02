import pytest
from decimal import Decimal
from datetime import date, timedelta
from models.transaction import Transaction
from models.product import Product
from models.inventory import Inventory, InventoryBatch

@pytest.fixture
def sample_product():
    return Product(1, "Pandesal", "Bread", 5.00, 2)

@pytest.fixture
def sample_inventory(sample_product):
    inv = Inventory()
    today = date.today()
    inv.add_batch(InventoryBatch(1, sample_product, 100,
                                 today, today + timedelta(days=2)))
    return inv

@pytest.fixture
def empty_transaction():
    return Transaction(1, "admin")

@pytest.fixture
def transaction_with_items(sample_product, sample_inventory):
    t = Transaction(1, "admin")
    t.add_item(sample_product, 5, sample_inventory)
    return t

def test_transaction_creation(empty_transaction):
    assert empty_transaction.transaction_id == 1
    assert empty_transaction.cashier_name == "admin"
    assert empty_transaction.items == []
    assert empty_transaction.is_voided is False

def test_add_item(transaction_with_items):
    assert len(transaction_with_items.items) == 1
    assert transaction_with_items.items[0]["product"].name == "Pandesal"
    assert transaction_with_items.items[0]["quantity"] == 5

def test_checkout_cash(transaction_with_items):
    result = transaction_with_items.checkout("Cash", 100.00)
    assert result is True
    assert transaction_with_items.payment_method == "Cash"

def test_void_transaction(empty_transaction):
    empty_transaction.void()
    assert empty_transaction.is_voided is True

def test_get_total(transaction_with_items):
    assert transaction_with_items.get_total() == Decimal("25.00")  # 5 x ₱5.00

def test_get_total_accepts_string_subtotals(transaction_with_items):
    transaction_with_items.items[0]["subtotal"] = "25.00"
    assert transaction_with_items.get_total() == Decimal("25.00")

def test_get_change(transaction_with_items):
    transaction_with_items.checkout("Cash", 50.00)
    assert transaction_with_items.get_change() == Decimal("25.00")  # 50 - 25

def test_get_change_accepts_formatted_amount_paid(transaction_with_items):
    transaction_with_items.checkout("Cash", "PHP 50.00")
    assert transaction_with_items.get_change() == Decimal("25.00")

def test_checkout_insufficient_cash(transaction_with_items):
    result = transaction_with_items.checkout("Cash", 10.00)
    assert result is False

def test_checkout_insufficient_non_cash(transaction_with_items):
    result = transaction_with_items.checkout("GCash", 10.00)
    assert result is False

def test_get_change_non_cash(transaction_with_items):
    transaction_with_items.checkout("GCash", 25.00)
    assert transaction_with_items.get_change() == Decimal("0.00")

def test_get_change_non_cash_overpayment(transaction_with_items):
    transaction_with_items.checkout("GCash", 50.00)
    assert transaction_with_items.get_change() == Decimal("25.00")

def test_checkout_empty_cart(empty_transaction):
    result = empty_transaction.checkout("Cash", 100.00)
    assert result is False

def test_add_item_insufficient_stock(sample_product, sample_inventory):
    t = Transaction(2, "admin")
    t.add_item(sample_product, 9999, sample_inventory)
    assert len(t.items) == 0

import pytest
from datetime import date, timedelta
from models.inventory import Inventory, InventoryBatch
from models.product import Product

@pytest.fixture
def sample_product():
    return Product(1, "Pandesal", "Bread", 5.00, 2)

@pytest.fixture
def active_batch(sample_product):
    today = date.today()
    return InventoryBatch(1, sample_product, 50,
                          today, today + timedelta(days=2))

@pytest.fixture
def expired_batch(sample_product):
    today = date.today()
    return InventoryBatch(2, sample_product, 20,
                          today - timedelta(days=5), today - timedelta(days=1))

@pytest.fixture
def inventory_with_batches(sample_product):
    inv = Inventory()
    today = date.today()
    inv.add_batch(InventoryBatch(1, sample_product, 50,
                                 today - timedelta(days=2), today + timedelta(days=3)))
    inv.add_batch(InventoryBatch(2, sample_product, 30,
                                 today - timedelta(days=1), today + timedelta(days=2)))
    inv.add_batch(InventoryBatch(3, sample_product, 10,
                                 today - timedelta(days=5), today - timedelta(days=1)))
    return inv

def test_batch_creation(active_batch, sample_product):
    assert active_batch.batch_id == 1
    assert active_batch.product == sample_product
    assert active_batch.quantity == 50

def test_add_batch_to_inventory(active_batch):
    inv = Inventory()
    inv.add_batch(active_batch)
    assert len(inv.batches) == 1

def test_get_active_batches(inventory_with_batches):
    active = inventory_with_batches.get_active_batches()
    assert len(active) == 2  # batch 3 is expired

def test_get_expired_batches(inventory_with_batches):
    expired = inventory_with_batches.get_expired_batches()
    assert len(expired) == 1  # only batch 3

def test_freshness_percent_fresh(sample_product):
    today = date.today()
    batch = InventoryBatch(1, sample_product, 50,
                           today, today + timedelta(days=4))
    assert batch.get_freshness_percent() == 100.0

def test_freshness_label_expired(expired_batch):
    assert expired_batch.get_freshness_label() == "EXPIRED"

def test_fifo_deducts_oldest_first(inventory_with_batches):
    inventory_with_batches.deduct_fifo(1, 30)
    oldest_batch = inventory_with_batches.batches[0]  # batch 1 — oldest
    assert oldest_batch.quantity == 20  # 50 - 30 = 20

def test_deduct_stock_exceeds(active_batch):
    result = active_batch.deduct_stock(100)
    assert result is False
    assert active_batch.quantity == 50  # unchanged

def test_get_expiring_soon(sample_product):
    inv = Inventory()
    today = date.today()
    inv.add_batch(InventoryBatch(1, sample_product, 10,
                                 today - timedelta(days=1), today + timedelta(days=1)))
    inv.add_batch(InventoryBatch(2, sample_product, 10,
                                 today - timedelta(days=1), today + timedelta(days=5)))
    expiring = inv.get_expiring_soon(days=2)
    assert len(expiring) == 1  # only batch 1 expires within 2 days

def test_fifo_insufficient_stock(inventory_with_batches):
    result = inventory_with_batches.deduct_fifo(1, 999)
    assert result is False
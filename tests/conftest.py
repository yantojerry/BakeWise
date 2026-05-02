import pytest
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from decimal import Decimal
from models.product import Product
from models.inventory import Inventory, InventoryBatch


@pytest.fixture
def sample_product():
    return Product(
        id=1,
        name="Pandesal",
        price=Decimal("5"),
        shelf_life_days=2
    )


@pytest.fixture
def sample_inventory(sample_product):
    inventory = Inventory()

    batch = InventoryBatch(
        batch_id=1,
        product_id=sample_product.id,
        product_name=sample_product.name,
        quantity=100,
        production_date=None,
        expiry_date=None
    )

    inventory.add_batch(batch)
    return inventory
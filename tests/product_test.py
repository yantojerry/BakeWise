import pytest
from models.product import Product

@pytest.fixture
def sample_product():
    return Product(1, "Pandesal", "Bread", 5.00, 2)

@pytest.fixture
def product_list():
    return [
        Product(1, "Pandesal",        "Bread",  5.00,  2),
        Product(2, "Ensaymada",       "Pastry", 25.00, 3),
        Product(3, "Chocolate Cake",  "Cake",   350.00, 5),
        Product(4, "Iced Coffee",     "Drinks", 60.00, 1),
    ]

def test_product_creation(sample_product):
    assert sample_product.product_id == 1
    assert sample_product.name == "Pandesal"
    assert sample_product.category == "Bread"
    assert sample_product.price == 5.00
    assert sample_product.shelf_life_days == 2

def test_product_list(product_list):
    assert len(product_list) == 4

def test_find_product_by_id(product_list):
    result = next((p for p in product_list if p.product_id == 2), None)
    assert result is not None
    assert result.name == "Ensaymada"

def test_delete_product(product_list):
    product_to_delete = next((p for p in product_list if p.product_id == 1), None)
    product_list.remove(product_to_delete)
    assert len(product_list) == 3
    assert all(p.product_id != 1 for p in product_list)

def test_product_price_correct(sample_product):
    assert sample_product.price == 5.00

def test_product_shelf_life_correct(sample_product):
    assert sample_product.shelf_life_days == 2

def test_product_edit(sample_product):
    sample_product.name = "Cheese Pandesal"
    sample_product.price = 8.00
    assert sample_product.name == "Cheese Pandesal"
    assert sample_product.price == 8.00

def test_product_str(sample_product):
    assert str(sample_product) == "Pandesal - ₱5.00"

def test_product_zero_price():
    p = Product(5, "Free Sample", "Bread", 0.00, 1)

def test_find_nonexistent_product(product_list):
    result = next((p for p in product_list if p.product_id == 99), None)
    assert result is None
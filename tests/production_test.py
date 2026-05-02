import pytest
from datetime import date, timedelta
from models.production import Production
from models.product import Product
from models.recipe import Recipe
from models.ingredient import Ingredient

@pytest.fixture
def sample_product():
    return Product(1, "Pandesal", "Bread", 5.00, 2)

@pytest.fixture
def sample_ingredients():
    return {
        "flour": Ingredient(1, "Flour", "kg", 50.0, 10.0),
        "sugar": Ingredient(2, "Sugar", "kg", 30.0,  5.0),
    }

@pytest.fixture
def sample_recipe(sample_product, sample_ingredients):
    r = Recipe(product_id=1)
    r.add_ingredient(sample_ingredients["flour"], 0.1)
    r.add_ingredient(sample_ingredients["sugar"], 0.02)
    return r

@pytest.fixture
def sample_production(sample_product, sample_recipe):
    return Production(1, sample_product, 10, sample_recipe)

def test_production_creation(sample_production, sample_product):
    assert sample_production.production_id == 1
    assert sample_production.product == sample_product
    assert sample_production.quantity == 10
    assert sample_production.is_cancelled is False

def test_production_date_defaults_to_today(sample_production):
    assert sample_production.production_date == date.today()

def test_produce_success(sample_production, sample_ingredients):
    result = sample_production.produce()
    assert result is True
    assert sample_ingredients["flour"].quantity == 49.0   # 50 - (0.1 * 10)
    assert sample_ingredients["sugar"].quantity == 29.8   # 30 - (0.02 * 10)

def test_cancel_production(sample_production):
    sample_production.cancel()
    assert sample_production.is_cancelled is True

def test_expiry_date_correct(sample_production):
    expected = date.today() + timedelta(days=2)  # shelf_life_days = 2
    assert sample_production.expiry_date == expected

def test_produce_insufficient_ingredients(sample_product, sample_recipe):
    sample_recipe.ingredients[0]["ingredient"].quantity = 0  # zero out flour
    prod = Production(2, sample_product, 10, sample_recipe)
    result = prod.produce()
    assert result is False

def test_produce_cancelled_batch(sample_production):
    sample_production.cancel()
    result = sample_production.produce()
    assert result is False

def test_expiry_date_custom_production_date(sample_product, sample_recipe):
    custom_date = date(2025, 1, 1)
    prod = Production(3, sample_product, 5, sample_recipe, production_date=custom_date)
    assert prod.expiry_date == date(2025, 1, 3)  # 1 Jan + 2 days shelf life

def test_produce_single_unit(sample_product, sample_ingredients):
    r = Recipe(product_id=1)
    r.add_ingredient(sample_ingredients["flour"], 0.1)
    prod = Production(4, sample_product, 1, r)
    prod.produce()
    assert round(sample_ingredients["flour"].quantity, 2) == 49.9  # 50 - 0.1

def test_cancelled_batch_cannot_produce(sample_production):
    sample_production.cancel()
    result = sample_production.produce()
    assert result is False
    assert sample_production.is_cancelled is True
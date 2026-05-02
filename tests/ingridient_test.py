import pytest
from models.ingredient import Ingredient

@pytest.fixture
def sample_ingredient():
    return Ingredient(1, "Flour", "kg", 50.0, 10.0)

@pytest.fixture
def ingredient_list():
    return [
        Ingredient(1, "Flour",  "kg",  50.0, 10.0),
        Ingredient(2, "Sugar",  "kg",  30.0,  5.0),
        Ingredient(3, "Butter", "kg",  20.0,  3.0),
        Ingredient(4, "Eggs",   "pcs", 100.0, 20.0),
        Ingredient(5, "Yeast",  "kg",   5.0,  1.0),
    ]

def test_ingredient_creation(sample_ingredient):
    assert sample_ingredient.ingredient_id == 1
    assert sample_ingredient.name == "Flour"
    assert sample_ingredient.unit == "kg"
    assert sample_ingredient.quantity == 50.0
    assert sample_ingredient.reorder_level == 10.0

def test_ingredient_list(ingredient_list):
    assert len(ingredient_list) == 5

def test_find_ingredient_by_id(ingredient_list):
    result = next((i for i in ingredient_list if i.ingredient_id == 3), None)
    assert result is not None
    assert result.name == "Butter"

def test_deduct_stock(sample_ingredient):
    result = sample_ingredient.deduct(10.0)
    assert result is True
    assert sample_ingredient.quantity == 40.0

def test_deduct_exceeds_stock(sample_ingredient):
    result = sample_ingredient.deduct(100.0)
    assert result is False
    assert sample_ingredient.quantity == 50.0  # quantity unchanged

def test_low_stock_at_reorder_level():
    i = Ingredient(1, "Flour", "kg", 10.0, 10.0)
    assert i.is_low_stock() is True

def test_low_stock_below_reorder_level():
    i = Ingredient(1, "Flour", "kg", 5.0, 10.0)
    assert i.is_low_stock() is True

def test_not_low_stock(sample_ingredient):
    assert sample_ingredient.is_low_stock() is False

def test_deduct_zero(sample_ingredient):
    result = sample_ingredient.deduct(0)
    assert result is True
    assert sample_ingredient.quantity == 50.0

def test_ingredient_str(sample_ingredient):
    assert str(sample_ingredient) == "Flour: 50.0 kg"
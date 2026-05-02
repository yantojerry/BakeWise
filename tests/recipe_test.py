import pytest
from models.recipe import Recipe
from models.ingredient import Ingredient

@pytest.fixture
def sample_ingredients():
    return {
        "flour":  Ingredient(1, "Flour",  "kg",  50.0, 10.0),
        "sugar":  Ingredient(2, "Sugar",  "kg",  30.0,  5.0),
        "butter": Ingredient(3, "Butter", "kg",  20.0,  3.0),
        "eggs":   Ingredient(4, "Eggs",   "pcs", 100.0, 20.0),
    }

@pytest.fixture
def pandesal_recipe(sample_ingredients):
    r = Recipe(product_id=1)
    r.add_ingredient(sample_ingredients["flour"], 0.1)
    r.add_ingredient(sample_ingredients["sugar"], 0.02)
    return r

def test_recipe_creation():
    r = Recipe(product_id=1)
    assert r.product_id == 1
    assert r.ingredients == []

def test_add_ingredient(sample_ingredients):
    r = Recipe(product_id=1)
    r.add_ingredient(sample_ingredients["flour"], 0.1)
    assert len(r.ingredients) == 1
    assert r.ingredients[0]["ingredient"].name == "Flour"
    assert r.ingredients[0]["amount"] == 0.1

def test_add_multiple_ingredients(pandesal_recipe):
    assert len(pandesal_recipe.ingredients) == 2

def test_can_produce_sufficient(pandesal_recipe):
    assert pandesal_recipe.can_produce(10) is True

def test_can_produce_insufficient(sample_ingredients):
    r = Recipe(product_id=1)
    r.add_ingredient(sample_ingredients["flour"], 10.0)
    assert r.can_produce(10) is False

def test_ingredient_amount_correct(pandesal_recipe):
    flour_item = next(i for i in pandesal_recipe.ingredients
                      if i["ingredient"].name == "Flour")
    assert flour_item["amount"] == 0.1

def test_can_produce_exact_amount(sample_ingredients):
    r = Recipe(product_id=1)
    r.add_ingredient(sample_ingredients["flour"], 5.0)
    assert r.can_produce(10) is True

def test_recipe_linked_to_product(pandesal_recipe):
    assert pandesal_recipe.product_id == 1

def test_can_produce_zero(pandesal_recipe):
    assert pandesal_recipe.can_produce(0) is True

def test_empty_recipe_can_produce():
    r = Recipe(product_id=99)
    assert r.can_produce(10) is True
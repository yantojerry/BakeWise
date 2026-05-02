from locust import User, task, between, events
from datetime import date, timedelta
import random
import time

from database.user_db import UserDB
from database.product_db import ProductDB
from database.ingredient_db import IngredientDB
from database.inventory_db import InventoryDB
from database.recipe_db import RecipeDB
from database.transaction_db import TransactionDB
from models.transaction import Transaction


def fire_success(name: str, start_time: float, response_length: int = 1):
    events.request.fire(
        request_type="DB",
        name=name,
        response_time=(time.time() - start_time) * 1000,
        response_length=response_length,
        exception=None,
    )


def fire_failure(name: str, start_time: float, exc: Exception):
    events.request.fire(
        request_type="DB",
        name=name,
        response_time=(time.time() - start_time) * 1000,
        response_length=0,
        exception=exc,
    )


def tracked_call(name: str, fn):
    start_time = time.time()
    try:
        result = fn()
        fire_success(name, start_time)
        return result
    except Exception as exc:
        fire_failure(name, start_time, exc)
        return None


class BakeWiseUser(User):
    # faster cycle
    wait_time = between(0.2, 0.6)

    @task(1)
    def users_panel(self):
        tracked_call("users_get_all", lambda: UserDB.get_all_users())

    @task(3)
    def products_panel(self):
        products = tracked_call("products_get_all", lambda: ProductDB.get_all_products())
        if products:
            picked = random.choice(products)
            tracked_call("products_get_one", lambda: ProductDB.get_product(picked.product_id))

    @task(2)
    def ingredients_panel(self):
        ingredients = tracked_call("ingredients_get_all", lambda: IngredientDB.get_all_ingredients())
        tracked_call("ingredients_low_stock", lambda: IngredientDB.get_low_stock())
        if ingredients:
            picked = random.choice(ingredients)
            tracked_call("ingredients_get_one", lambda: IngredientDB.get_ingredient(picked.ingredient_id))

    @task(3)
    def inventory_panel_fast(self):
        # use lighter inventory calls only
        tracked_call("inventory_active_count", lambda: InventoryDB.get_active_batch_count())
        tracked_call("inventory_expiring_count", lambda: InventoryDB.get_expiring_batch_count(7))

        products = tracked_call("inventory_products_source", lambda: ProductDB.get_all_products())
        if products:
            picked = random.choice(products)
            tracked_call(
                "inventory_available_qty",
                lambda: InventoryDB.get_available_quantity(picked.product_id),
            )

    @task(1)
    def recipe_panel(self):
        products = tracked_call("recipe_products_source", lambda: ProductDB.get_all_products())
        if products:
            picked = random.choice(products)
            tracked_call("recipe_get_one", lambda: RecipeDB.get_recipe(picked.product_id))

    @task(2)
    def reports_panel_fast(self):
        today = date.today()
        last_3_days = today - timedelta(days=3)

        tracked_call("reports_transaction_count", lambda: TransactionDB.get_transaction_count())
        tracked_call("reports_today_revenue", lambda: TransactionDB.get_today_revenue())
        tracked_call(
            "reports_recent_transactions",
            lambda: TransactionDB.get_recent_transactions(limit=5)
        )
        tracked_call(
            "reports_transactions_range",
            lambda: TransactionDB.get_transactions_by_range(last_3_days, today, limit=10)
        )

    @task(4)
    def pos_simulate_sale_fast(self):
        products = tracked_call("pos_products_source", lambda: ProductDB.get_all_products())
        if not products:
            return

        start_time = time.time()
        try:
            # only 1 item to keep test faster
            product = random.choice(products)
            qty = 1

            transaction = Transaction(None, cashier_name="LoadTest")
            transaction.payment_method = "Cash"
            transaction.add_item(product, qty, float(product.price) * qty)

            TransactionDB.save_transaction(transaction)
            fire_success("pos_simulate_sale", start_time)
        except Exception as exc:
            fire_failure("pos_simulate_sale", start_time, exc)
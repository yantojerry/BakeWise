import importlib
import pytest
from datetime import date, timedelta
from decimal import Decimal
import database.ingredient_db as ingredient_db_module
import database.product_db as product_db_module
import database.production_db as production_db_module
import database.recipe_db as recipe_db_module
import database.user_db as user_db_module
from database.ingredient_db import IngredientDB
from database.inventory_db import InventoryDB
from database.product_db import ProductDB
from database.production_db import ProductionDB
from database.recipe_db import RecipeDB
from database.transaction_db import TransactionDB
from database.user_db import UserDB
from models.ingredient import Ingredient
from models.inventory import Inventory, InventoryBatch
from models.product import Product
from models.production import Production
from models.recipe import Recipe
from models.transaction import Transaction
from models.user import User, UserManager


class _ScriptedCursor:
    def __init__(self, results=None, lastrowid=101, rowcount=1):
        self.results = list(results or [])
        self.lastrowid = lastrowid
        self.rowcount = rowcount
        self.current = []
        self.queries = []
        self.params = []
        self.closed = False

    def execute(self, query, params=None):
        self.queries.append(" ".join(str(query).split()))
        self.params.append(params)
        self.current = self.results.pop(0) if self.results else []

    def fetchone(self):
        if isinstance(self.current, list):
            return self.current[0] if self.current else None
        return self.current

    def fetchall(self):
        if self.current is None:
            return []
        if isinstance(self.current, list):
            return self.current
        return [self.current]

    def close(self):
        self.closed = True


class _ScriptedConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self, *args, **kwargs):
        return self._cursor

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


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


def test_recipe_production_inventory_flow():
    """
    Integration test:
    Product + Ingredients + Recipe + Production + Inventory
    Checks if produced stock deducts ingredients and becomes active inventory.
    """
    product = Product(10, "Cheese Bread", "Bread", Decimal("25.00"), 3)
    flour = Ingredient(1, "Flour", "kg", 10, 2)
    cheese = Ingredient(2, "Cheese", "kg", 5, 1)
    recipe = Recipe(product.product_id)
    recipe.add_ingredient(flour, Decimal("0.20"))
    recipe.add_ingredient(cheese, Decimal("0.10"))

    production = Production(1, product, 10, recipe, production_date=date.today())
    inventory = Inventory()

    assert production.produce() is True
    inventory.add_batch(
        InventoryBatch(
            batch_id=1,
            product=product,
            quantity=production.quantity,
            production_date=production.production_date,
            expiry_date=production.expiry_date,
        )
    )

    assert flour.quantity == Decimal("8.00")
    assert cheese.quantity == Decimal("4.00")
    assert inventory.get_available_quantity(product.product_id) == 10
    assert inventory.get_active_batches()[0].product.name == product.name


def test_production_does_not_deduct_when_recipe_stock_is_short():
    """
    Integration test:
    Ingredients + Recipe + Production
    Checks if production stops safely when a recipe requirement cannot be met.
    """
    product = Product(11, "Chocolate Cake", "Cake", Decimal("450.00"), 4)
    cocoa = Ingredient(3, "Cocoa", "kg", Decimal("0.50"), Decimal("0.25"))
    recipe = Recipe(product.product_id)
    recipe.add_ingredient(cocoa, Decimal("0.20"))

    production = Production(2, product, 5, recipe)

    assert production.produce() is False
    assert cocoa.quantity == Decimal("0.50")


def test_inventory_fifo_sale_flow_after_checkout():
    """
    Integration test:
    Product + Inventory + Transaction
    Checks if checkout and FIFO stock deduction work together for a sale.
    """
    product = Product(12, "Pandesal", "Bread", Decimal("5.00"), 2)
    inventory = Inventory()
    old_batch = InventoryBatch(
        1,
        product=product,
        quantity=3,
        production_date=date.today() - timedelta(days=1),
        expiry_date=date.today() + timedelta(days=1),
    )
    new_batch = InventoryBatch(
        2,
        product=product,
        quantity=5,
        production_date=date.today(),
        expiry_date=date.today() + timedelta(days=2),
    )
    inventory.add_batch(old_batch)
    inventory.add_batch(new_batch)

    transaction = Transaction(9, "cashier")
    assert transaction.add_item(product, 5, inventory) is True
    assert transaction.checkout("Cash", Decimal("25.00"), inventory) is True
    assert inventory.deduct_fifo(product.product_id, 5) is True

    assert old_batch.quantity == 0
    assert new_batch.quantity == 3
    assert inventory.get_available_quantity(product.product_id) == 3


def test_user_login_role_and_pos_flow():
    """
    Integration test:
    User + Product + Inventory + Transaction
    Checks if a cashier account can log in and process a basic POS sale.
    """
    manager = UserManager()
    cashier = User(2, "Cashier Jane", "cashier", "cash123", "cashier")
    manager.add_user(User(1, "Owner", "owner", "owner123", "owner"))
    manager.add_user(cashier)

    logged_in = manager.login("CASHIER", "cash123")
    product = Product(13, "Muffin", "Muffin", Decimal("35.00"), 2)
    inventory = Inventory()
    inventory.add_batch(
        InventoryBatch(
            1,
            product=product,
            quantity=6,
            production_date=date.today(),
            expiry_date=date.today() + timedelta(days=2),
        )
    )

    transaction = Transaction(10, logged_in.username)
    transaction.add_item(product, 2, inventory)

    assert logged_in == cashier
    assert logged_in.has_access("transaction")
    assert not logged_in.has_access("inventory")
    assert transaction.checkout("Cash", Decimal("100.00"), inventory) is True
    assert transaction.get_change() == Decimal("30.00")


def test_online_order_lifecycle_flow():
    """
    Integration test:
    Product + Inventory + Transaction online order state
    Checks if online orders move through accepted, processed, and voided states.
    """
    product = Product(14, "Birthday Cake", "Cake", Decimal("650.00"), 5)
    inventory = Inventory()
    inventory.add_batch(
        InventoryBatch(
            1,
            product=product,
            quantity=2,
            production_date=date.today(),
            expiry_date=date.today() + timedelta(days=5),
        )
    )
    transaction = Transaction(11, "cashier")
    transaction.order_source = "Online Orders"

    transaction.add_item(product, 1, inventory)
    transaction.mark_online_accepted("2026-05-03 09:00:00")
    checkout_result = transaction.checkout("GCash", Decimal("650.00"), inventory)
    transaction.mark_online_processed("2026-05-03 09:10:00")
    transaction.void()

    assert checkout_result is True
    assert transaction.accepted_at == "2026-05-03 09:00:00"
    assert transaction.processed_at == "2026-05-03 09:10:00"
    assert transaction.online_order_status == "voided"
    assert transaction.is_voided is True


def test_application_core_modules_import_and_expose_expected_contracts():
    """
    Integration coverage check:
    Imports the app's core model, database, and GUI modules without opening the app.
    This catches broken module wiring while avoiding real DB and Tk window startup.
    """
    module_names = [
        "models.product",
        "models.ingredient",
        "models.recipe",
        "models.production",
        "models.inventory",
        "models.transaction",
        "models.user",
        "database.db",
        "database.product_db",
        "database.ingredient_db",
        "database.recipe_db",
        "database.production_db",
        "database.inventory_db",
        "database.transaction_db",
        "database.user_db",
        "gui.theme",
        "gui.async_utils",
        "gui.keyboard",
        "gui.side_panel",
        "gui.date_picker",
        "gui.login_screen",
        "gui.main_window",
        "gui.screens.dashboard_screen",
        "gui.screens.products_screen",
        "gui.screens.ingredients_screen",
        "gui.screens.recipes_screen",
        "gui.screens.production_screen",
        "gui.screens.inventory_screen",
        "gui.screens.pos_screen",
        "gui.screens.transactions_screen",
        "gui.screens.reports_screen",
        "gui.screens.users_screen",
        "gui.screens.settings_screen",
        "main",
    ]

    loaded = {name: importlib.import_module(name) for name in module_names}

    assert hasattr(loaded["models.product"], "Product")
    assert hasattr(loaded["models.transaction"], "Transaction")
    assert hasattr(loaded["database.user_db"], "UserDB")
    assert hasattr(loaded["database.transaction_db"], "TransactionDB")
    assert hasattr(loaded["gui.screens.pos_screen"], "POSScreen")
    assert hasattr(loaded["gui.screens.settings_screen"], "SettingsScreen")
    assert hasattr(loaded["main"], "login")


def test_gui_pos_inventory_proxy_connects_to_inventory_db(monkeypatch):
    """
    Integration coverage check:
    POS screen proxy delegates stock checks, FIFO reservations, and restores to InventoryDB.
    """
    from gui.screens.pos_screen import DBInventoryProxy

    calls = []
    monkeypatch.setattr(
        InventoryDB,
        "get_available_quantity",
        staticmethod(lambda product_id: calls.append(("available", product_id)) or 12),
    )
    monkeypatch.setattr(
        InventoryDB,
        "get_available_quantities",
        staticmethod(lambda product_ids=None: calls.append(("available_many", product_ids)) or {1: 12}),
    )
    monkeypatch.setattr(
        InventoryDB,
        "reserve_fifo",
        staticmethod(lambda product_id, quantity: calls.append(("reserve", product_id, quantity)) or [{"batch_id": 1, "quantity": quantity}]),
    )
    monkeypatch.setattr(
        InventoryDB,
        "restore_deductions",
        staticmethod(lambda deductions: calls.append(("restore", deductions)) or True),
    )

    proxy = DBInventoryProxy()

    assert proxy.get_available_quantity(1) == 12
    assert proxy.get_available_quantities([1]) == {1: 12}
    assert proxy.reserve_fifo(1, 2) == [{"batch_id": 1, "quantity": 2}]
    assert proxy.restore_deductions([{"batch_id": 1, "quantity": 2}]) is True
    assert calls == [
        ("available", 1),
        ("available_many", [1]),
        ("reserve", 1, 2),
        ("restore", [{"batch_id": 1, "quantity": 2}]),
    ]


def test_database_product_ingredient_recipe_production_inventory_contracts(monkeypatch):
    """
    Integration coverage check:
    Database adapters map rows into the model layer and use commits for write flows.
    The fake connection prevents tests from changing real MySQL data.
    """
    product_cursor = _ScriptedCursor(
        [[{"id": 20, "name": "Ensaymada", "category": "Pastry", "price": Decimal("45.00"), "shelf_life_days": 3}]]
    )
    product_conn = _ScriptedConnection(product_cursor)
    monkeypatch.setattr(product_db_module, "get_connection", lambda: product_conn)

    products = ProductDB.get_all_products()

    assert len(products) == 1
    assert products[0].product_id == 20
    assert products[0].name == "Ensaymada"
    assert products[0].category == "Pastry"
    assert float(products[0].price) == 45.0
    assert product_conn.closed is True

    ingredient_rows = [
        {"id": 1, "name": "Flour", "unit": "kg", "quantity": 0, "reorder_level": 5},
        {"id": 2, "name": "Butter", "unit": "kg", "quantity": 3, "reorder_level": 5},
        {"id": 3, "name": "Sugar", "unit": "kg", "quantity": 20, "reorder_level": 5},
    ]
    ingredient_cursor = _ScriptedCursor([ingredient_rows])
    ingredient_conn = _ScriptedConnection(ingredient_cursor)
    monkeypatch.setattr(ingredient_db_module, "get_connection", lambda: ingredient_conn)

    low_stock_report = IngredientDB.get_low_stock_history_report(
        date(2026, 5, 1),
        date(2026, 5, 3),
    )

    assert low_stock_report["critical_count"] == 1
    assert low_stock_report["low_count"] == 1
    assert low_stock_report["healthy_count"] == 1
    assert [row["ingredient"].name for row in low_stock_report["rows"]] == ["Flour", "Butter"]

    recipe_cursor = _ScriptedCursor(
        [
            [{"id": 7, "product_id": 20}],
            [
                {
                    "quantity": Decimal("0.20"),
                    "id": 1,
                    "name": "Flour",
                    "unit": "kg",
                    "stock": Decimal("10.00"),
                    "reorder_level": Decimal("2.00"),
                }
            ],
        ]
    )
    recipe_conn = _ScriptedConnection(recipe_cursor)
    monkeypatch.setattr(recipe_db_module, "get_connection", lambda: recipe_conn)

    recipe = RecipeDB.get_recipe(20)

    assert recipe.product_id == 20
    assert recipe.ingredients[0]["ingredient"].name == "Flour"
    assert recipe.ingredients[0]["amount"] == Decimal("0.20")

    production_cursor = _ScriptedCursor(lastrowid=501)
    production_conn = _ScriptedConnection(production_cursor)
    product = Product(20, "Ensaymada", "Pastry", Decimal("45.00"), 3)
    monkeypatch.setattr(production_db_module, "get_connection", lambda: production_conn)

    production_id = ProductionDB.log_production(20, product, 12, production_date=date(2026, 5, 3))

    assert production_id == 501
    assert production_conn.committed is True
    assert production_cursor.params[0] == (20, 12, date(2026, 5, 3), date(2026, 5, 6))

    availability_cursor = _ScriptedCursor([[{"product_id": 20, "quantity": 12}]])
    availability_conn = _ScriptedConnection(availability_cursor)
    monkeypatch.setattr(InventoryDB, "_get_connection", staticmethod(lambda: availability_conn))

    assert InventoryDB.get_available_quantities([20]) == {20: 12}

    batch = InventoryDB._build_batch(
        {
            "batch_id": 30,
            "product_id": 20,
            "name": "Ensaymada",
            "category": "Pastry",
            "price": Decimal("45.00"),
            "shelf_life_days": 3,
            "quantity": 12,
            "production_date": date(2026, 5, 3),
            "expiry_date": date(2026, 5, 6),
        }
    )

    assert batch.batch_id == 30
    assert batch.product.name == "Ensaymada"
    assert batch.quantity == 12


def test_user_db_handles_basic_user_schema_variants(monkeypatch):
    """
    Integration coverage check:
    UserDB supports the practical user fields used by the User page even when
    the database uses user_id/full_name/email instead of id/name/username.
    """
    user_columns = [
        {"COLUMN_NAME": "user_id", "IS_NULLABLE": "NO", "COLUMN_DEFAULT": None, "EXTRA": ""},
        {"COLUMN_NAME": "full_name", "IS_NULLABLE": "YES", "COLUMN_DEFAULT": None, "EXTRA": ""},
        {"COLUMN_NAME": "email", "IS_NULLABLE": "NO", "COLUMN_DEFAULT": None, "EXTRA": ""},
        {"COLUMN_NAME": "password", "IS_NULLABLE": "NO", "COLUMN_DEFAULT": None, "EXTRA": ""},
        {"COLUMN_NAME": "role", "IS_NULLABLE": "NO", "COLUMN_DEFAULT": None, "EXTRA": ""},
        {"COLUMN_NAME": "contact_number", "IS_NULLABLE": "YES", "COLUMN_DEFAULT": None, "EXTRA": ""},
        {"COLUMN_NAME": "is_active", "IS_NULLABLE": "NO", "COLUMN_DEFAULT": "1", "EXTRA": ""},
    ]
    user_cursor = _ScriptedCursor([user_columns, [{"next_id": 6}]], lastrowid=0)
    user_conn = _ScriptedConnection(user_cursor)
    monkeypatch.setattr(user_db_module, "get_connection", lambda: user_conn)

    user_id = UserDB.add_user(
        "cashier@example.com",
        "cash123",
        "cashier",
        name="Cashier Example",
        contact_number="09171234567",
        status="Inactive",
    )

    insert_query = user_cursor.queries[-1]
    insert_params = user_cursor.params[-1]

    assert user_id == 6
    assert "INSERT INTO users" in insert_query
    assert "`user_id`" in insert_query
    assert "`full_name`" in insert_query
    assert "`email`" in insert_query
    assert "`contact_number`" in insert_query
    assert "`is_active`" in insert_query
    assert insert_params == (
        6,
        "Cashier Example",
        "cashier@example.com",
        "cash123",
        "cashier",
        "09171234567",
        0,
    )
    assert user_conn.committed is True


def test_transaction_db_save_and_online_helpers_connect_transaction_model(monkeypatch):
    """
    Integration coverage check:
    TransactionDB receives a Transaction model, saves transaction and item rows,
    assigns receipt/customer fields, and keeps online/helper behavior consistent.
    """
    schema = {
        "transaction_columns": {
            "id",
            "transaction_id",
            "cashier_name",
            "date",
            "payment_method",
            "service_mode",
            "order_source",
            "customer_number",
            "pickup_date_from",
            "pickup_date_to",
            "online_order_status",
            "accepted_at",
            "processed_at",
            "total",
            "amount_paid",
            "is_voided",
        },
        "item_columns": {"transaction_id", "product_id", "product_name", "quantity", "price", "subtotal"},
        "product_columns": {"id", "name", "category", "price", "shelf_life_days"},
        "tx_id_col": "id",
        "tx_date_col": "date",
        "product_pk_col": "id",
        "has_cashier_name": True,
        "item_amount_col": "subtotal",
    }
    transaction_cursor = _ScriptedCursor(lastrowid=9001)
    transaction_conn = _ScriptedConnection(transaction_cursor)
    monkeypatch.setattr(TransactionDB, "_schema_info", schema)
    monkeypatch.setattr(TransactionDB, "_get_connection", staticmethod(lambda: transaction_conn))
    monkeypatch.setattr(
        TransactionDB,
        "peek_next_customer_number",
        staticmethod(lambda service_mode, on_date=None, order_source="Walk-In": "DI-001"),
    )

    product = Product(40, "Ube Cake", "Cake", Decimal("450.00"), 4)
    transaction = Transaction(None, "Cashier Jane")
    transaction.service_mode = "Dine In"
    transaction.date = date(2026, 5, 3)

    assert transaction.add_item(product, 2) is True
    assert transaction.checkout("Cash", Decimal("1000.00")) is True

    transaction_id = TransactionDB.save_transaction(transaction)

    assert transaction_id == 9001
    assert transaction.transaction_id == 9001
    assert transaction.customer_number == "DI-001"
    assert transaction.recorded_total == Decimal("900.00")
    assert transaction.amount_paid == Decimal("1000.00")
    assert transaction_conn.committed is True
    assert any(query.startswith("INSERT INTO transactions") for query in transaction_cursor.queries)
    assert any(query.startswith("INSERT INTO transaction_items") for query in transaction_cursor.queries)
    assert TransactionDB._service_mode_prefix("Take Out") == "TO"
    assert TransactionDB._service_mode_prefix("Dine In") == "DI"
    assert TransactionDB._service_mode_prefix("Take Out", order_source="Online Orders") == "ON"

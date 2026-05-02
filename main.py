from models.product import Product
from models.ingredient import Ingredient
from models.recipe import Recipe
from models.production import Production
from models.inventory import Inventory, InventoryBatch
from models.transaction import Transaction
from models.user import User, UserManager
from database.user_db import UserDB
from database.product_db import ProductDB
from database.ingredient_db import IngredientDB
from database.recipe_db import RecipeDB
from database.production_db import ProductionDB
from database.inventory_db import InventoryDB
from database.transaction_db import TransactionDB

# ── Global ────────────────────────────────────────────────
current_user = None

# ── Helpers ──────────────────────────────────────────────
def pause():
    input("\nPress Enter to continue...")

def clear():
    print("\n" * 3)

# ═══════════════════════════════════════════════════════════
#  LOGIN
# ═══════════════════════════════════════════════════════════
def login():
    global current_user
    clear()
    print("=" * 40)
    print("         BAKEWISE — LOGIN")
    print("=" * 40)
    username = input("Username: ").strip()
    password = input("Password: ").strip()
    user = UserDB.get_user(username)
    if user and user["password"] == password:
        current_user = user
        print(f"Login successful! Welcome, {user['username']}")
        pause()
        return True
    print("Invalid username or password.")
    pause()
    return False

# ═══════════════════════════════════════════════════════════
#  MAIN MENU
# ═══════════════════════════════════════════════════════════
def main_menu():
    while True:
        clear()
        print("=" * 40)
        print(f"  BAKEWISE  |  {current_user['username']} ({current_user['role'].upper()})")
        print("=" * 40)

        if current_user['role'] == "owner":
            print("1. Manage Products")
            print("2. Manage Ingredients")
            print("3. Manage Recipes")
            print("4. Log Production")
            print("5. View Inventory")
            print("6. POS Transaction")
            print("7. Reports")
            print("8. Manage Users")
            print("0. Logout")
        elif current_user['role'] == "cashier":
            print("1. POS Transaction")
            print("2. View Transaction History")
            print("0. Logout")
        elif current_user['role'] == "baker":
            print("1. Log Production")
            print("2. View Inventory")
            print("3. View Ingredients")
            print("0. Logout")

        choice = input("\nEnter choice: ").strip()

        if current_user['role'] == "owner":
            if choice == "1": manage_products()
            elif choice == "2": manage_ingredients()
            elif choice == "3": manage_recipes()
            elif choice == "4": log_production()
            elif choice == "5": view_inventory()
            elif choice == "6": pos_transaction()
            elif choice == "7": reports()
            elif choice == "8": manage_users()
            elif choice == "0": break

        elif current_user['role'] == "cashier":
            if choice == "1": pos_transaction()
            elif choice == "2": view_transactions()
            elif choice == "0": break

        elif current_user['role'] == "baker":
            if choice == "1": log_production()
            elif choice == "2": view_inventory()
            elif choice == "3": view_ingredients()
            elif choice == "0": break

# ═══════════════════════════════════════════════════════════
#  PRODUCTS
# ═══════════════════════════════════════════════════════════
def manage_products():
    while True:
        clear()
        print("=" * 40)
        print("        MANAGE PRODUCTS")
        print("=" * 40)
        print("1. View All Products")
        print("2. Add Product")
        print("3. Edit Product")
        print("4. Delete Product")
        print("0. Back")
        choice = input("\nEnter choice: ").strip()

        if choice == "1": view_products()
        elif choice == "2": add_product()
        elif choice == "3": edit_product()
        elif choice == "4": delete_product()
        elif choice == "0": break

def view_products():
    clear()
    print("=" * 40)
    print("         ALL PRODUCTS")
    print("=" * 40)
    products = ProductDB.get_all_products()
    if not products:
        print("No products yet.")
    for p in products:
        print(f"[{p.product_id}] {p.name} | {p.category} | ₱{p.price:.2f} | Shelf Life: {p.shelf_life_days} days")
    pause()

def add_product():
    clear()
    print("=== ADD PRODUCT ===")
    name = input("Product Name: ").strip()
    category = input("Category (Bread/Pastry/Cake/Drinks): ").strip()
    try:
        price = float(input("Price (₱): ").strip())
        shelf_life = int(input("Shelf Life (days): ").strip())
    except ValueError:
        print("Invalid input.")
        pause()
        return
    ProductDB.add_product(name, category, price, shelf_life)
    print(f"\nProduct '{name}' added successfully!")
    pause()

def edit_product():
    clear()
    print("=" * 40)
    print("         ALL PRODUCTS")
    print("=" * 40)
    products = ProductDB.get_all_products()
    if not products:
        print("No products yet.")
        pause()
        return
    for p in products:
        print(f"[{p.product_id}] {p.name} | {p.category} | ₱{p.price:.2f} | Shelf Life: {p.shelf_life_days} days")
    try:
        pid = int(input("\nEnter Product ID to edit: ").strip())
        p = ProductDB.get_product(pid)
        if not p:
            print("Product not found.")
            pause()
            return
        print(f"Editing: {p.name}")
        name = input(f"New Name [{p.name}]: ").strip()
        category = input(f"New Category [{p.category}]: ").strip()
        price = input(f"New Price [{p.price}]: ").strip()
        shelf_life = input(f"New Shelf Life [{p.shelf_life_days}]: ").strip()

        new_name = name if name else p.name
        new_category = category if category else p.category
        new_price = float(price) if price else p.price
        new_shelf = int(shelf_life) if shelf_life else p.shelf_life_days

        ProductDB.update_product(pid, new_name, new_category, new_price, new_shelf)
        print("Product updated!")
    except ValueError:
        print("Invalid input.")
    pause()

def delete_product():
    clear()
    print("=" * 40)
    print("         ALL PRODUCTS")
    print("=" * 40)
    products = ProductDB.get_all_products()
    if not products:
        print("No products yet.")
        pause()
        return
    for p in products:
        print(f"[{p.product_id}] {p.name} | {p.category} | ₱{p.price:.2f}")
    try:
        pid = int(input("\nEnter Product ID to delete: ").strip())
        p = ProductDB.get_product(pid)
        if not p:
            print("Product not found.")
            pause()
            return
        ProductDB.delete_product(pid)
        print(f"Product '{p.name}' deleted.")
    except ValueError:
        print("Invalid input.")
    pause()

# ═══════════════════════════════════════════════════════════
#  INGREDIENTS
# ═══════════════════════════════════════════════════════════
def manage_ingredients():
    while True:
        clear()
        print("=" * 40)
        print("       MANAGE INGREDIENTS")
        print("=" * 40)
        print("1. View All Ingredients")
        print("2. Add Ingredient")
        print("3. Edit Ingredient")
        print("4. Delete Ingredient")
        print("0. Back")
        choice = input("\nEnter choice: ").strip()

        if choice == "1": view_ingredients()
        elif choice == "2": add_ingredient()
        elif choice == "3": edit_ingredient()
        elif choice == "4": delete_ingredient()
        elif choice == "0": break

def view_ingredients():
    clear()
    print("=" * 40)
    print("        ALL INGREDIENTS")
    print("=" * 40)
    ingredients = IngredientDB.get_all_ingredients()
    if not ingredients:
        print("No ingredients yet.")
    for i in ingredients:
        status = "LOW STOCK" if i.is_low_stock() else "OK"
        print(f"[{i.ingredient_id}] {i.name} | {i.quantity} {i.unit} | Reorder: {i.reorder_level} | {status}")
    pause()

def add_ingredient():
    clear()
    print("=== ADD INGREDIENT ===")
    name = input("Ingredient Name: ").strip()
    unit = input("Unit (kg/pcs/liters): ").strip()
    try:
        quantity = float(input("Current Quantity: ").strip())
        reorder = float(input("Reorder Level: ").strip())
    except ValueError:
        print("Invalid input.")
        pause()
        return
    IngredientDB.add_ingredient(name, unit, quantity, reorder)
    print(f"Ingredient '{name}' added!")
    pause()

def edit_ingredient():
    clear()
    print("=" * 40)
    print("        ALL INGREDIENTS")
    print("=" * 40)
    ingredients = IngredientDB.get_all_ingredients()
    if not ingredients:
        print("No ingredients yet.")
        pause()
        return
    for i in ingredients:
        status = "LOW STOCK" if i.is_low_stock() else "OK"
        print(f"[{i.ingredient_id}] {i.name} | {i.quantity} {i.unit} | Reorder: {i.reorder_level} | {status}")
    try:
        iid = int(input("\nEnter Ingredient ID to edit: ").strip())
        i = IngredientDB.get_ingredient(iid)
        if not i:
            print("Ingredient not found.")
            pause()
            return
        quantity = input(f"New Quantity [{i.quantity}]: ").strip()
        reorder = input(f"New Reorder Level [{i.reorder_level}]: ").strip()
        new_qty = float(quantity) if quantity else i.quantity
        new_reorder = float(reorder) if reorder else i.reorder_level
        IngredientDB.update_ingredient(iid, new_qty, new_reorder)
        print("Ingredient updated!")
    except ValueError:
        print("Invalid input.")
    pause()

def delete_ingredient():
    clear()
    print("=" * 40)
    print("        ALL INGREDIENTS")
    print("=" * 40)
    ingredients = IngredientDB.get_all_ingredients()
    if not ingredients:
        print("No ingredients yet.")
        pause()
        return
    for i in ingredients:
        print(f"[{i.ingredient_id}] {i.name} | {i.quantity} {i.unit}")
    try:
        iid = int(input("\nEnter Ingredient ID to delete: ").strip())
        i = IngredientDB.get_ingredient(iid)
        if not i:
            print("Ingredient not found.")
            pause()
            return
        IngredientDB.delete_ingredient(iid)
        print(f"Ingredient '{i.name}' deleted.")
    except ValueError:
        print("Invalid input.")
    pause()

# ═══════════════════════════════════════════════════════════
#  RECIPES
# ═══════════════════════════════════════════════════════════
def manage_recipes():
    while True:
        clear()
        print("=" * 40)
        print("         MANAGE RECIPES")
        print("=" * 40)
        print("1. View Recipe")
        print("2. Create / Update Recipe")
        print("0. Back")
        choice = input("\nEnter choice: ").strip()
        if choice == "1": view_recipe()
        elif choice == "2": create_recipe()
        elif choice == "0": break

def view_recipe():
    clear()
    products = ProductDB.get_all_products()
    if not products:
        print("No products yet.")
        pause()
        return
    for p in products:
        print(f"[{p.product_id}] {p.name}")
    try:
        pid = int(input("\nEnter Product ID: ").strip())
        recipe = RecipeDB.get_recipe(pid)
        if not recipe:
            print("No recipe found for this product.")
            pause()
            return
        recipe.display()
    except ValueError:
        print("Invalid input.")
    pause()

def create_recipe():
    clear()
    products = ProductDB.get_all_products()
    if not products:
        print("No products yet.")
        pause()
        return
    for p in products:
        print(f"[{p.product_id}] {p.name}")
    try:
        pid = int(input("\nEnter Product ID to set recipe: ").strip())
        p = ProductDB.get_product(pid)
        if not p:
            print("Product not found.")
            pause()
            return
        recipe = Recipe(pid)
        print(f"\nSetting recipe for: {p.name}")
        print("Add ingredients (type 0 to finish):")

        while True:
            ingredients = IngredientDB.get_all_ingredients()
            for i in ingredients:
                print(f"[{i.ingredient_id}] {i.name} | {i.quantity} {i.unit}")
            try:
                iid = int(input("Ingredient ID (0 to finish): ").strip())
                if iid == 0:
                    break
                ing = IngredientDB.get_ingredient(iid)
                if not ing:
                    print("Ingredient not found.")
                    continue
                amount = float(input(f"Amount of {ing.name} per 1 {p.name} ({ing.unit}): ").strip())
                recipe.add_ingredient(ing, amount)
            except ValueError:
                print("Invalid input.")

        RecipeDB.save_recipe(pid, recipe.ingredients)
        print(f"Recipe for '{p.name}' saved!")
    except ValueError:
        print("Invalid input.")
    pause()

# ═══════════════════════════════════════════════════════════
#  PRODUCTION
# ═══════════════════════════════════════════════════════════
def log_production():
    clear()
    print("=" * 40)
    print("         LOG PRODUCTION")
    print("=" * 40)
    products = ProductDB.get_all_products()
    if not products:
        print("No products yet.")
        pause()
        return
    for p in products:
        print(f"[{p.product_id}] {p.name}")
    try:
        pid = int(input("\nSelect Product ID: ").strip())
        p = ProductDB.get_product(pid)
        if not p:
            print("Product not found.")
            pause()
            return

        if not RecipeDB.has_recipe(pid):
            print(f"No recipe set for {p.name}. Ask owner to set a recipe first.")
            pause()
            return

        recipe = RecipeDB.get_recipe(pid)
        quantity = int(input(f"How many {p.name} to produce?: ").strip())

        if not recipe.can_produce(quantity):
            pause()
            return

        # Deduct ingredients from DB
        for item in recipe.ingredients:
            needed = item["amount"] * quantity
            IngredientDB.deduct_ingredient(item["ingredient"].ingredient_id, needed)

        # Log production to DB
        from datetime import date, timedelta
        prod_date = date.today()
        ProductionDB.log_production(pid, p, quantity, prod_date)

        # Compute expiry and add to inventory
        expiry_date = prod_date + timedelta(days=p.shelf_life_days)
        InventoryDB.add_batch(pid, quantity, prod_date, expiry_date)

        print(f"\nSuccessfully produced {quantity} {p.name}!")
        print(f"Production Date: {prod_date}")
        print(f"Expiry Date:     {expiry_date}")

    except ValueError:
        print("Invalid input.")
    pause()

# ═══════════════════════════════════════════════════════════
#  INVENTORY
# ═══════════════════════════════════════════════════════════
def view_inventory():
    clear()
    print("=" * 40)
    print("        STOCK INVENTORY")
    print("=" * 40)
    active = InventoryDB.get_active_batches()
    if not active:
        print("No active stock.")
        pause()
        return
    for b in active:
        label = b.get_freshness_label()
        percent = b.get_freshness_percent()
        print(f"[Batch {b.batch_id}] {b.product.name}")
        print(f"  Qty: {b.quantity} | Produced: {b.production_date} | Expires: {b.expiry_date}")
        print(f"  Freshness: {percent:.1f}% — {label}")
        print()

    expired = InventoryDB.get_expired_batches()
    if expired:
        print("--- EXPIRED BATCHES ---")
        for b in expired:
            print(f"[Batch {b.batch_id}] {b.product.name} — EXPIRED {b.expiry_date}")
    pause()

# ═══════════════════════════════════════════════════════════
#  POS
# ═══════════════════════════════════════════════════════════
def pos_transaction():
    clear()
    print("=" * 40)
    print("            POS")
    print("=" * 40)
    print(f"  Cashier: {current_user['username']}")

    t = Transaction(None, current_user['username'])

    # Proxy so Transaction.add_item() works with InventoryDB
    class DBInventoryProxy:
        def deduct_fifo(self, product_id, quantity):
            return InventoryDB.deduct_fifo(product_id, quantity)

    db_inventory = DBInventoryProxy()

    while True:
        print("\nCurrent Cart:")
        if not t.items:
            print("  (empty)")
        else:
            for item in t.items:
                print(f"  {item['product'].name} x{item['quantity']} — ₱{item['subtotal']:.2f}")
            print(f"  TOTAL: ₱{t.get_total():.2f}")

        print("\n1. Add Item")
        print("2. Checkout")
        print("3. Void Transaction")
        print("0. Cancel")
        choice = input("\nEnter choice: ").strip()

        if choice == "1":
            products = ProductDB.get_all_products()
            for p in products:
                print(f"[{p.product_id}] {p.name} | ₱{p.price:.2f}")
            try:
                pid = int(input("Product ID: ").strip())
                p = ProductDB.get_product(pid)
                if not p:
                    print("Product not found.")
                    continue
                qty = int(input(f"Quantity of {p.name}: ").strip())
                t.add_item(p, qty, db_inventory)
            except ValueError:
                print("Invalid input.")

        elif choice == "2":
            if not t.items:
                print("Cart is empty!")
                continue
            print("\nPayment Method:")
            print("1. Cash")
            print("2. Card")
            print("3. GCash")
            pm_choice = input("Choose: ").strip()
            methods = {"1": "Cash", "2": "Card", "3": "GCash"}
            method = methods.get(pm_choice, "Cash")
            try:
                amount = float(input(f"Amount Paid (₱): ").strip())
                success = t.checkout(method, amount)
                if success:
                    transaction_id = TransactionDB.save_transaction(t)
                    t.transaction_id = transaction_id
                    t.print_receipt()
                    pause()
                    break
            except ValueError:
                print("Invalid amount.")

        elif choice == "3":
            t.void()
            if t.items:
                TransactionDB.save_transaction(t)
            pause()
            break

        elif choice == "0":
            break

def view_transactions():
    clear()
    print("=" * 40)
    print("      TRANSACTION HISTORY")
    print("=" * 40)
    transactions = TransactionDB.get_all_transactions()
    if not transactions:
        print("No transactions yet.")
        pause()
        return
    for t in transactions:
        status = "VOIDED" if t.is_voided else "OK"
        print(f"[#{t.transaction_id}] {t.date} | ₱{t.get_total():.2f} | {t.payment_method} | {status}")
    pause()

# ═══════════════════════════════════════════════════════════
#  REPORTS
# ═══════════════════════════════════════════════════════════
def reports():
    while True:
        clear()
        print("=" * 40)
        print("            REPORTS")
        print("=" * 40)
        print("1. Sales Summary")
        print("2. Best Selling Products")
        print("3. Low Stock Ingredients")
        print("4. Expiring Soon (within 2 days)")
        print("0. Back")
        choice = input("\nEnter choice: ").strip()

        if choice == "1":
            clear()
            print("=== SALES SUMMARY ===")
            print("1. Daily")
            print("2. Weekly")
            print("3. Monthly")
            period = input("Choose period: ").strip()

            from datetime import date, timedelta
            today = date.today()

            if period == "1":
                label = f"Daily — {today}"
                filtered = TransactionDB.get_transactions_by_date(today)

            elif period == "2":
                start_of_week = today - timedelta(days=today.weekday())
                label = f"Weekly — {start_of_week} to {today}"
                filtered = TransactionDB.get_transactions_by_range(start_of_week, today)

            elif period == "3":
                start_of_month = today.replace(day=1)
                label = f"Monthly — {today.strftime('%B %Y')}"
                filtered = TransactionDB.get_transactions_by_range(start_of_month, today)

            else:
                print("Invalid choice.")
                pause()
                continue

            total = sum(t.get_total() for t in filtered)
            print(f"\n{label}")
            print(f"Total Transactions: {len(filtered)}")
            print(f"Total Revenue:      ₱{total:.2f}")
            if filtered:
                print("\nBreakdown:")
                for t in filtered:
                    print(f"  #{t.transaction_id} | {t.date} | ₱{t.get_total():.2f} | {t.payment_method}")
            pause()

        elif choice == "2":
            clear()
            print("=== BEST SELLING PRODUCTS ===")
            transactions = TransactionDB.get_all_transactions()
            sales = {}
            for t in transactions:
                if t.is_voided:
                    continue
                for item in t.items:
                    name = item["product"].name
                    sales[name] = sales.get(name, 0) + item["quantity"]
            if not sales:
                print("No sales data yet.")
            else:
                ranked = sorted(sales.items(), key=lambda x: x[1], reverse=True)
                for rank, (name, qty) in enumerate(ranked, 1):
                    print(f"{rank}. {name} — {qty} pcs sold")
            pause()

        elif choice == "3":
            clear()
            print("=== LOW STOCK INGREDIENTS ===")
            low = IngredientDB.get_low_stock()
            if not low:
                print("All ingredients are sufficiently stocked.")
            for i in low:
                print(f"{i.name}: {i.quantity} {i.unit} (reorder at {i.reorder_level})")
            pause()

        elif choice == "4":
            clear()
            print("=== EXPIRING SOON ===")
            expiring = InventoryDB.get_expiring_soon(days=2)
            if not expiring:
                print("No items expiring within 2 days.")
            for b in expiring:
                print(f"{b.product.name} | Batch {b.batch_id} | Expires: {b.expiry_date} | Qty: {b.quantity}")
            pause()

        elif choice == "0":
            break

# ═══════════════════════════════════════════════════════════
#  MANAGE USERS
# ═══════════════════════════════════════════════════════════
def manage_users():
    while True:
        clear()
        print("=" * 40)
        print("         MANAGE USERS")
        print("=" * 40)
        print("1. View All Users")
        print("2. Add User")
        print("0. Back")
        choice = input("\nEnter choice: ").strip()

        if choice == "1":
            clear()
            users = UserDB.get_all_users()
            if not users:
                print("No users found.")
            for u in users:
                print(f"[{u['id']}] {u['username']} — Role: {u['role']}")
            pause()

        elif choice == "2":
            clear()
            print("=== ADD USER ===")
            username = input("Username: ").strip()
            password = input("Password: ").strip()
            print("Roles: owner / cashier / baker")
            role = input("Role: ").strip().lower()
            if role not in ["owner", "cashier", "baker"]:
                print("Invalid role.")
                pause()
                continue
            UserDB.add_user(username, password, role)
            print(f"User '{username}' added successfully!")
            pause()

        elif choice == "0":
            break
#===========================================
#settings
#===========================================
import customtkinter as ctk
from gui.theme import get_colors, AMBER, AMBER_DARK, SUCCESS, ERROR_RED

class SettingsScreen(ctk.CTkFrame):
    def __init__(self, parent, user, on_theme_change=None):
        self.c = get_colors()
        super().__init__(parent, fg_color=self.c["bg"], corner_radius=0)
        self.user = user
        self.on_theme_change = on_theme_change
        self.pack(fill="both", expand=True)
        self._build_ui()

    def _build_ui(self):
        c = self.c
        is_dark = ctk.get_appearance_mode() == "Dark"

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=32, pady=(28, 0))
        ctk.CTkLabel(header, text="Settings",
                     font=ctk.CTkFont("Georgia", 28, "bold"),
                     text_color=c["text"]).pack(anchor="w")
        ctk.CTkLabel(header, text="Manage your preferences and system settings",
                     font=ctk.CTkFont("Segoe UI", 13),
                     text_color=c["text_muted"]).pack(anchor="w", pady=(4, 0))

        ctk.CTkFrame(self, fg_color=c["border"], height=1).pack(fill="x", padx=32, pady=20)

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=32, pady=(0, 24))

        # ── Appearance ────────────────────────────────────
        self._section(scroll, "🎨  Appearance")

        appear_card = ctk.CTkFrame(scroll, fg_color=c["card"], corner_radius=12,
                                   border_width=1, border_color=c["border"])
        appear_card.pack(fill="x", pady=(0, 16))

        # Theme toggle row
        row = ctk.CTkFrame(appear_card, fg_color="transparent")
        row.pack(fill="x", padx=24, pady=20)
        left = ctk.CTkFrame(row, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(left, text="Color Theme",
                     font=ctk.CTkFont("Segoe UI", 13, "bold"),
                     text_color=c["text"]).pack(anchor="w")
        ctk.CTkLabel(left, text="Switch between dark and light appearance",
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color=c["text_muted"]).pack(anchor="w")

        theme_frame = ctk.CTkFrame(row, fg_color="transparent")
        theme_frame.pack(side="right")
        self.theme_var = ctk.StringVar(value="Dark" if is_dark else "Light")
        for option in ["Dark", "Light"]:
            btn_color = AMBER if self.theme_var.get() == option else c["input"]
            btn_text_color = "#0F0F0F" if self.theme_var.get() == option else c["text_gray"]
            ctk.CTkButton(theme_frame, text=option, width=90, height=36,
                          fg_color=btn_color,
                          hover_color=AMBER_DARK if option == "Dark" else "#D1D5DB",
                          text_color=btn_text_color,
                          corner_radius=8, border_width=1, border_color=c["border"],
                          font=ctk.CTkFont("Segoe UI", 12),
                          command=lambda o=option: self._change_theme(o)
                          ).pack(side="left", padx=4)

        ctk.CTkFrame(appear_card, fg_color=c["border"], height=1).pack(fill="x", padx=24)

        # Font size row
        font_row = ctk.CTkFrame(appear_card, fg_color="transparent")
        font_row.pack(fill="x", padx=24, pady=20)
        fl = ctk.CTkFrame(font_row, fg_color="transparent")
        fl.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(fl, text="Interface Scale",
                     font=ctk.CTkFont("Segoe UI", 13, "bold"),
                     text_color=c["text"]).pack(anchor="w")
        ctk.CTkLabel(fl, text="Adjust the UI scaling for your display",
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color=c["text_muted"]).pack(anchor="w")
        self.scale_var = ctk.StringVar(value="100%")
        ctk.CTkOptionMenu(font_row, values=["80%", "90%", "100%", "110%", "120%"],
                          variable=self.scale_var,
                          fg_color=c["input"], button_color=c["border"],
                          button_hover_color=c["border"],
                          text_color=c["text"], dropdown_fg_color=c["card"],
                          dropdown_text_color=c["text"],
                          font=ctk.CTkFont("Segoe UI", 12), width=110,
                          command=self._change_scale
                          ).pack(side="right")

        # ── POS Settings ──────────────────────────────────
        self._section(scroll, "🛒  Point of Sale")

        pos_card = ctk.CTkFrame(scroll, fg_color=c["card"], corner_radius=12,
                                border_width=1, border_color=c["border"])
        pos_card.pack(fill="x", pady=(0, 16))

        pos_settings = [
            ("Default Payment Method", "Cash", ["Cash", "Card", "GCash"]),
            ("Receipt Auto-Print",     "Yes",  ["Yes", "No"]),
            ("Currency Symbol",        "₱",    ["₱", "$", "€"]),
        ]

        for i, (label, default, options) in enumerate(pos_settings):
            if i > 0:
                ctk.CTkFrame(pos_card, fg_color=c["border"], height=1).pack(fill="x", padx=24)
            r = ctk.CTkFrame(pos_card, fg_color="transparent")
            r.pack(fill="x", padx=24, pady=16)
            ctk.CTkLabel(r, text=label,
                         font=ctk.CTkFont("Segoe UI", 13, "bold"),
                         text_color=c["text"]).pack(side="left")
            ctk.CTkOptionMenu(r, values=options,
                              fg_color=c["input"], button_color=c["border"],
                              button_hover_color=c["border"],
                              text_color=c["text"], dropdown_fg_color=c["card"],
                              dropdown_text_color=c["text"],
                              font=ctk.CTkFont("Segoe UI", 12), width=120
                              ).pack(side="right")

        # ── Inventory Settings ────────────────────────────
        self._section(scroll, "📦  Inventory")

        inv_card = ctk.CTkFrame(scroll, fg_color=c["card"], corner_radius=12,
                                border_width=1, border_color=c["border"])
        inv_card.pack(fill="x", pady=(0, 16))

        inv_settings = [
            ("Low Stock Alert Threshold", "At reorder level",
             ["At reorder level", "10% above", "20% above"]),
            ("Expiry Warning (days)",     "2 days",
             ["1 day", "2 days", "3 days", "5 days", "7 days"]),
            ("FIFO Stock Deduction",      "Enabled",
             ["Enabled", "Disabled"]),
        ]

        for i, (label, default, options) in enumerate(inv_settings):
            if i > 0:
                ctk.CTkFrame(inv_card, fg_color=c["border"], height=1).pack(fill="x", padx=24)
            r = ctk.CTkFrame(inv_card, fg_color="transparent")
            r.pack(fill="x", padx=24, pady=16)
            ctk.CTkLabel(r, text=label,
                         font=ctk.CTkFont("Segoe UI", 13, "bold"),
                         text_color=c["text"]).pack(side="left")
            ctk.CTkOptionMenu(r, values=options,
                              fg_color=c["input"], button_color=c["border"],
                              button_hover_color=c["border"],
                              text_color=c["text"], dropdown_fg_color=c["card"],
                              dropdown_text_color=c["text"],
                              font=ctk.CTkFont("Segoe UI", 12), width=160
                              ).pack(side="right")

        # ── System Info ───────────────────────────────────
        self._section(scroll, "ℹ️  System Information")

        info_card = ctk.CTkFrame(scroll, fg_color=c["card"], corner_radius=12,
                                 border_width=1, border_color=c["border"])
        info_card.pack(fill="x", pady=(0, 16))

        info_items = [
            ("Application",  "BakeWise — Bakery Management System"),
            ("Version",      "v1.1.0"),
            ("Database",     "MySQL via XAMPP (Port 3307)"),
            ("Framework",    "Python 3.14 + CustomTkinter 5.2.2"),
            ("Logged in as", f"{self.user.get('username','').capitalize()} ({self.user.get('role','').upper()})"),
        ]

        for i, (label, value) in enumerate(info_items):
            if i > 0:
                ctk.CTkFrame(info_card, fg_color=c["border"], height=1).pack(fill="x", padx=24)
            r = ctk.CTkFrame(info_card, fg_color="transparent")
            r.pack(fill="x", padx=24, pady=14)
            ctk.CTkLabel(r, text=label,
                         font=ctk.CTkFont("Segoe UI", 12),
                         text_color=c["text_muted"]).pack(side="left")
            ctk.CTkLabel(r, text=value,
                         font=ctk.CTkFont("Segoe UI", 12, "bold"),
                         text_color=c["text"]).pack(side="right")

    def _section(self, parent, title):
        ctk.CTkLabel(parent, text=title,
                     font=ctk.CTkFont("Segoe UI", 13, "bold"),
                     text_color=self.c["text_muted"]).pack(anchor="w", pady=(8, 8))

    def _change_theme(self, mode):
        ctk.set_appearance_mode(mode.lower())
        if self.on_theme_change:
            self.on_theme_change()

    def _change_scale(self, scale):
        value = float(scale.replace("%", "")) / 100
        ctk.set_widget_scaling(value)

# ═══════════════════════════════════════════════════════════
#  RUN APP
# ═══════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("Starting BakeWise...")
    while True:
        if login():
            main_menu()
        again = input("Login again? (y/n): ").strip().lower()
        if again != "y":
            print("Goodbye!")
            break

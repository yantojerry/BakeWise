import customtkinter as ctk
from database.product_db import ProductDB
from database.ingredient_db import IngredientDB
from database.recipe_db import RecipeDB
from gui.async_utils import run_in_thread
from models.recipe import Recipe
from gui.theme import get_colors, AMBER, AMBER_DARK, SUCCESS, ERROR_RED


class RecipesScreen(ctk.CTkFrame):
    def __init__(self, parent, user):
        self.c = get_colors()
        super().__init__(parent, fg_color=self.c["bg"], corner_radius=0)
        self.user = user
        self.recipe_items = []

        self.all_products = []
        self.filtered_products = []
        self.recipe_product_ids = set()
        self.ingredients_cache = []
        self.selected_product = None
        self._products_load_token = None
        self._recipe_load_token = None

        self.pack(fill="both", expand=True)
        self._build_ui()

    def _build_ui(self):
        c = self.c

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=32, pady=(28, 0))

        ctk.CTkLabel(
            header,
            text="Recipes",
            font=ctk.CTkFont("Georgia", 28, "bold"),
            text_color=c["text"]
        ).pack(side="left")

        ctk.CTkFrame(self, fg_color=c["border"], height=1).pack(fill="x", padx=32, pady=20)

        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=32, pady=(0, 24))
        main.grid_columnconfigure(0, weight=1)
        main.grid_columnconfigure(1, weight=1)
        main.grid_rowconfigure(0, weight=1)

        # LEFT PANEL
        left = ctk.CTkFrame(
            main,
            fg_color=c["card"],
            corner_radius=12,
            border_width=1,
            border_color=c["border"]
        )
        left.grid(row=0, column=0, padx=(0, 12), sticky="nsew")

        ctk.CTkLabel(
            left,
            text="Select Product",
            font=ctk.CTkFont("Segoe UI", 14, "bold"),
            text_color=c["text"]
        ).pack(anchor="w", padx=20, pady=(20, 8))

        ctk.CTkFrame(left, fg_color=c["border"], height=1).pack(fill="x", padx=20, pady=(0, 8))

        # FILTER CONTROLS
        filter_frame = ctk.CTkFrame(left, fg_color="transparent")
        filter_frame.pack(fill="x", padx=20, pady=(0, 10))

        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *args: self._apply_filters())

        self.filter_var = ctk.StringVar(value="All Products")

        self.search_entry = ctk.CTkEntry(
            filter_frame,
            textvariable=self.search_var,
            height=36,
            fg_color=c["input"],
            border_color=c["border"],
            text_color=c["text"],
            placeholder_text="Search product name...",
            placeholder_text_color=c["text_muted"],
            corner_radius=8,
            font=ctk.CTkFont("Segoe UI", 11)
        )
        self.search_entry.pack(fill="x", pady=(0, 8))

        self.filter_menu = ctk.CTkOptionMenu(
            filter_frame,
            values=["All Products", "With Recipe", "Without Recipe"],
            variable=self.filter_var,
            command=lambda value: self._apply_filters(),
            fg_color=c["input"],
            button_color=c["border"],
            button_hover_color=c["input"],
            text_color=c["text"],
            dropdown_fg_color=c["card"],
            dropdown_text_color=c["text"],
            font=ctk.CTkFont("Segoe UI", 11)
        )
        self.filter_menu.pack(fill="x")

        self.products_count_label = ctk.CTkLabel(
            left,
            text="",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=c["text_muted"]
        )
        self.products_count_label.pack(anchor="w", padx=20, pady=(8, 6))

        self.products_frame = ctk.CTkScrollableFrame(left, fg_color="transparent")
        self.products_frame.pack(fill="both", expand=True, padx=8, pady=(0, 12))

        self._load_products()

        # RIGHT PANEL
        self.right = ctk.CTkFrame(
            main,
            fg_color=c["card"],
            corner_radius=12,
            border_width=1,
            border_color=c["border"]
        )
        self.right.grid(row=0, column=1, sticky="nsew")

        ctk.CTkLabel(
            self.right,
            text="Select a product to view or edit its recipe",
            font=ctk.CTkFont("Segoe UI", 13),
            text_color=c["text_muted"]
        ).place(relx=0.5, rely=0.5, anchor="center")

    def _load_products(self):
        token = object()
        self._products_load_token = token
        self.products_count_label.configure(text="Loading products...")
        if not self.all_products:
            self._show_products_message("Loading products...")

        run_in_thread(
            self,
            self._fetch_products_data,
            on_success=lambda data: self._apply_loaded_products(token, data),
            on_error=lambda exc: self._handle_products_load_error(token, exc),
            is_current=lambda: self._products_load_token is token,
        )

    def _fetch_products_data(self):
        products = ProductDB.get_all_products() or []
        try:
            recipe_ids = set(RecipeDB.get_product_ids_with_recipes() or [])
        except Exception:
            recipe_ids = set()
        try:
            ingredients = IngredientDB.get_all_ingredients() or []
        except Exception:
            ingredients = []
        return {
            "products": products,
            "recipe_ids": recipe_ids,
            "ingredients": ingredients,
        }

    def _apply_loaded_products(self, token, data):
        if self._products_load_token is not token:
            return

        self.all_products = data.get("products", [])
        self.recipe_product_ids = set(data.get("recipe_ids", set()))
        self.ingredients_cache = data.get("ingredients", [])
        self._apply_filters()

    def _handle_products_load_error(self, token, exc):
        if self._products_load_token is not token:
            return

        self.all_products = []
        self.filtered_products = []
        self.recipe_product_ids = set()
        self.ingredients_cache = []
        self.products_count_label.configure(text="Load failed")
        self._show_products_message(f"Failed to load products: {exc}", color=ERROR_RED)

    def _show_products_message(self, message, color=None):
        c = self.c
        for w in self.products_frame.winfo_children():
            w.destroy()
        ctk.CTkLabel(
            self.products_frame,
            text=message,
            font=ctk.CTkFont("Segoe UI", 12),
            text_color=color or c["text_muted"]
        ).pack(pady=16)

    def _apply_filters(self):
        search_text = self.search_var.get().strip().lower()
        selected_filter = self.filter_var.get()

        filtered = []

        for product in self.all_products:
            product_name = getattr(product, "name", "")
            has_recipe = product.product_id in self.recipe_product_ids

            # Search filter
            if search_text and search_text not in product_name.lower():
                continue

            # Status filter
            if selected_filter == "With Recipe" and not has_recipe:
                continue
            if selected_filter == "Without Recipe" and has_recipe:
                continue

            filtered.append(product)

        self.filtered_products = filtered
        self._render_products()

    def _render_products(self):
        c = self.c

        for w in self.products_frame.winfo_children():
            w.destroy()

        count = len(self.filtered_products)
        self.products_count_label.configure(text=f"{count} product(s) found")

        if not self.filtered_products:
            ctk.CTkLabel(
                self.products_frame,
                text="No matching products found.",
                font=ctk.CTkFont("Segoe UI", 12),
                text_color=c["text_muted"]
            ).pack(pady=16)
            return

        for p in self.filtered_products:
            has_recipe = p.product_id in self.recipe_product_ids

            ctk.CTkButton(
                self.products_frame,
                text=f"  {p.name}  {'✓' if has_recipe else ''}",
                anchor="w",
                height=42,
                corner_radius=8,
                fg_color="transparent",
                hover_color=c["active_bg"],
                text_color=SUCCESS if has_recipe else c["text_gray"],
                font=ctk.CTkFont("Segoe UI", 13),
                command=lambda prod=p: self._select_product(prod)
            ).pack(fill="x", pady=2)

    def _select_product(self, product):
        self.selected_product = product
        self.recipe_items = []
        self._render_recipe_loading(product)

        token = object()
        self._recipe_load_token = token
        run_in_thread(
            self,
            lambda: self._fetch_recipe_items(product.product_id),
            on_success=lambda items: self._apply_recipe_items(token, product, items),
            on_error=lambda exc: self._handle_recipe_load_error(token, product, exc),
            is_current=lambda: self._recipe_load_token is token and self.selected_product == product,
        )

    def _fetch_recipe_items(self, product_id):
        recipe = RecipeDB.get_recipe(product_id)
        items = []
        if recipe:
            for item in recipe.ingredients:
                items.append({
                    "ingredient": item["ingredient"],
                    "amount": item["amount"]
                })
        return items

    def _apply_recipe_items(self, token, product, recipe_items):
        if self._recipe_load_token is not token or self.selected_product != product:
            return

        self.recipe_items = recipe_items
        self._render_recipe_editor(product)

    def _handle_recipe_load_error(self, token, product, exc):
        if self._recipe_load_token is not token or self.selected_product != product:
            return

        self.recipe_items = []
        self._render_recipe_editor(product, error_message=f"Failed to load recipe: {exc}")

    def _render_recipe_loading(self, product):
        c = self.c
        for w in self.right.winfo_children():
            w.destroy()

        ctk.CTkLabel(
            self.right,
            text=f"Recipe — {product.name}",
            font=ctk.CTkFont("Segoe UI", 14, "bold"),
            text_color=c["text"]
        ).pack(anchor="w", padx=20, pady=(20, 4))

        ctk.CTkFrame(self.right, fg_color=c["border"], height=1).pack(fill="x", padx=20, pady=(0, 8))
        ctk.CTkLabel(
            self.right,
            text="Loading recipe...",
            font=ctk.CTkFont("Segoe UI", 12),
            text_color=c["text_muted"]
        ).pack(anchor="w", padx=20, pady=(16, 0))

    def _render_recipe_editor(self, product, error_message=""):
        c = self.c

        for w in self.right.winfo_children():
            w.destroy()

        self.selected_product = product

        ctk.CTkLabel(
            self.right,
            text=f"Recipe — {product.name}",
            font=ctk.CTkFont("Segoe UI", 14, "bold"),
            text_color=c["text"]
        ).pack(anchor="w", padx=20, pady=(20, 4))

        ctk.CTkFrame(self.right, fg_color=c["border"], height=1).pack(fill="x", padx=20, pady=(0, 8))

        self.ing_frame = ctk.CTkScrollableFrame(self.right, fg_color="transparent", height=200)
        self.ing_frame.pack(fill="x", padx=12, pady=(0, 8))

        self._refresh_recipe_list()

        ctk.CTkLabel(
            self.right,
            text="ADD INGREDIENT",
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            text_color=c["text_muted"]
        ).pack(anchor="w", padx=20, pady=(8, 4))

        add_row = ctk.CTkFrame(self.right, fg_color="transparent")
        add_row.pack(fill="x", padx=20)

        ingredients = self.ingredients_cache
        ing_names = [f"{i.ingredient_id} — {i.name}" for i in ingredients]

        self.ing_map = {f"{i.ingredient_id} — {i.name}": i for i in ingredients}
        self.ing_var = ctk.StringVar(value=ing_names[0] if ing_names else "")

        ctk.CTkOptionMenu(
            add_row,
            values=ing_names if ing_names else ["No ingredients available"],
            variable=self.ing_var,
            fg_color=c["input"],
            button_color=c["border"],
            button_hover_color=c["input"],
            text_color=c["text"],
            dropdown_fg_color=c["card"],
            dropdown_text_color=c["text"],
            font=ctk.CTkFont("Segoe UI", 11),
            width=200
        ).pack(side="left", padx=(0, 8))

        self.amount_entry = ctk.CTkEntry(
            add_row,
            width=80,
            height=36,
            fg_color=c["input"],
            border_color=c["border"],
            text_color=c["text"],
            corner_radius=8,
            placeholder_text="Amt",
            placeholder_text_color=c["text_muted"],
            font=ctk.CTkFont("Segoe UI", 11)
        )
        self.amount_entry.pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            add_row,
            text="Add",
            width=60,
            height=36,
            fg_color="#1F3A1F",
            hover_color="#2A4A2A",
            text_color=SUCCESS,
            corner_radius=6,
            font=ctk.CTkFont("Segoe UI", 11),
            command=self._add_ingredient
        ).pack(side="left")

        self.status_label = ctk.CTkLabel(
            self.right,
            text="",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=ERROR_RED
        )
        self.status_label.pack(pady=(4, 0))
        if error_message:
            self.status_label.configure(text=error_message, text_color=ERROR_RED)

        ctk.CTkButton(
            self.right,
            text="Save Recipe",
            height=44,
            fg_color=AMBER,
            hover_color=AMBER_DARK,
            text_color="#0F0F0F",
            corner_radius=8,
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            command=self._save_recipe
        ).pack(fill="x", padx=20, pady=12)

    def _refresh_recipe_list(self):
        c = self.c

        for w in self.ing_frame.winfo_children():
            w.destroy()

        if not self.recipe_items:
            ctk.CTkLabel(
                self.ing_frame,
                text="No ingredients added yet.",
                font=ctk.CTkFont("Segoe UI", 12),
                text_color=c["text_muted"]
            ).pack(pady=12)
            return

        for idx, item in enumerate(self.recipe_items):
            row = ctk.CTkFrame(self.ing_frame, fg_color=c["input"], corner_radius=8)
            row.pack(fill="x", pady=3)

            ctk.CTkLabel(
                row,
                text=item["ingredient"].name,
                font=ctk.CTkFont("Segoe UI", 12, "bold"),
                text_color=c["text"]
            ).pack(side="left", padx=12, pady=8)

            ctk.CTkLabel(
                row,
                text=f"{item['amount']} {item['ingredient'].unit}",
                font=ctk.CTkFont("Segoe UI", 11),
                text_color=AMBER
            ).pack(side="left")

            ctk.CTkButton(
                row,
                text="✕",
                width=30,
                height=26,
                fg_color="transparent",
                hover_color="#3A1A1A",
                text_color=ERROR_RED,
                corner_radius=6,
                command=lambda i=idx: self._remove_ingredient(i)
            ).pack(side="right", padx=8)

    def _add_ingredient(self):
        ingredient = self.ing_map.get(self.ing_var.get())
        if not ingredient:
            self.status_label.configure(text="Please select a valid ingredient.")
            return

        try:
            amount = float(self.amount_entry.get().strip())
            if amount <= 0:
                raise ValueError
        except ValueError:
            self.status_label.configure(text="Enter a valid amount greater than 0.")
            return

        self.recipe_items.append({
            "ingredient": ingredient,
            "amount": amount
        })

        self.amount_entry.delete(0, "end")
        self.status_label.configure(text="")
        self._refresh_recipe_list()

    def _remove_ingredient(self, idx):
        self.recipe_items.pop(idx)
        self._refresh_recipe_list()

    def _save_recipe(self):
        self.status_label.configure(text="", text_color=ERROR_RED)

        if not self.recipe_items:
            self.status_label.configure(text="Add at least one ingredient.")
            return

        try:
            RecipeDB.save_recipe(self.selected_product.product_id, self.recipe_items)
            self.status_label.configure(text="✓ Recipe saved!", text_color=SUCCESS)

            self.recipe_product_ids.add(self.selected_product.product_id)
            self._apply_filters()

        except Exception as e:
            self.status_label.configure(text=f"Error: {e}", text_color=ERROR_RED)

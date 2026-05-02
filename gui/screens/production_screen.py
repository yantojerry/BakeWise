from datetime import date, timedelta
import tkinter as tk
from tkinter import ttk

import customtkinter as ctk
from tkcalendar import Calendar

from database.ingredient_db import IngredientDB
from database.inventory_db import InventoryDB
from database.production_db import ProductionDB
from database.product_db import ProductDB
from database.recipe_db import RecipeDB
from gui.async_utils import run_in_thread
from gui.theme import AMBER, AMBER_DARK, ERROR_RED, SUCCESS, get_colors


class ProductionScreen(ctk.CTkFrame):
    def __init__(self, parent, user):
        self.c = get_colors()
        super().__init__(parent, fg_color=self.c["bg"], corner_radius=0)
        self.user = user
        self.product_map = {}
        self.products = []
        self._setup_token = None
        self._recipe_token = None
        self._history_token = None
        self._history_search_after_id = None
        self._produce_token = None
        self._setup_loaded_once = False
        self._history_loaded_once = False
        self.pack(fill="both", expand=True)
        self._build_ui()

    def on_show(self):
        self._load_setup_async()
        self._load_history()

    def _build_ui(self):
        c = self.c

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=32, pady=(28, 0))

        ctk.CTkLabel(
            header,
            text="Production",
            font=ctk.CTkFont("Georgia", 28, "bold"),
            text_color=c["text"],
        ).pack(side="left")

        ctk.CTkFrame(self, fg_color=c["border"], height=1).pack(fill="x", padx=32, pady=20)

        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=32, pady=(0, 24))
        main.grid_columnconfigure(0, weight=1)
        main.grid_columnconfigure(1, weight=1)

        form_card = ctk.CTkFrame(
            main,
            fg_color=c["card"],
            corner_radius=12,
            border_width=1,
            border_color=c["border"],
        )
        form_card.grid(row=0, column=0, padx=(0, 12), sticky="nsew")

        ctk.CTkLabel(
            form_card,
            text="Log Production",
            font=ctk.CTkFont("Segoe UI", 14, "bold"),
            text_color=c["text"],
        ).pack(anchor="w", padx=24, pady=(20, 4))

        ctk.CTkFrame(form_card, fg_color=c["border"], height=1).pack(fill="x", padx=24, pady=(0, 16))

        ctk.CTkLabel(
            form_card,
            text="SELECT PRODUCT",
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            text_color=c["text_muted"],
        ).pack(anchor="w", padx=24, pady=(0, 6))

        self.product_var = ctk.StringVar(value="Loading products...")
        self.product_menu = ctk.CTkOptionMenu(
            form_card,
            values=["Loading products..."],
            variable=self.product_var,
            fg_color=c["input"],
            button_color=c["border"],
            text_color=c["text"],
            dropdown_fg_color=c["card"],
            font=ctk.CTkFont("Segoe UI", 12),
            command=self._on_product_select,
        )
        self.product_menu.pack(fill="x", padx=24)

        ctk.CTkLabel(
            form_card,
            text="QUANTITY",
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            text_color=c["text_muted"],
        ).pack(anchor="w", padx=24, pady=(16, 6))

        self.qty_entry = ctk.CTkEntry(
            form_card,
            height=42,
            fg_color=c["input"],
            border_color=c["border"],
            text_color=c["text"],
            corner_radius=8,
            font=ctk.CTkFont("Segoe UI", 13),
            placeholder_text="Enter quantity",
        )
        self.qty_entry.pack(fill="x", padx=24)

        ctk.CTkLabel(
            form_card,
            text="RECIPE REQUIREMENTS",
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            text_color=c["text_muted"],
        ).pack(anchor="w", padx=24, pady=(16, 6))

        self.recipe_frame = ctk.CTkScrollableFrame(
            form_card,
            fg_color=c["input"],
            corner_radius=8,
            height=120,
        )
        self.recipe_frame.pack(fill="x", padx=24)

        self.status_label = ctk.CTkLabel(
            form_card,
            text="",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=ERROR_RED,
        )
        self.status_label.pack(pady=(8, 0))

        self.produce_btn = ctk.CTkButton(
            form_card,
            text="PRODUCE",
            height=46,
            fg_color=AMBER,
            hover_color=AMBER_DARK,
            text_color="#0F0F0F",
            command=self._produce,
        )
        self.produce_btn.pack(fill="x", padx=24, pady=16)

        hist_card = ctk.CTkFrame(
            main,
            fg_color=c["card"],
            corner_radius=12,
            border_width=1,
            border_color=c["border"],
        )
        hist_card.grid(row=0, column=1, sticky="nsew")

        ctk.CTkLabel(
            hist_card,
            text="Production History",
            font=ctk.CTkFont("Segoe UI", 14, "bold"),
            text_color=c["text"],
        ).pack(anchor="w", padx=24, pady=(20, 4))

        filter_frame = ctk.CTkFrame(hist_card, fg_color="transparent")
        filter_frame.pack(fill="x", padx=24, pady=(0, 12))

        ctk.CTkLabel(
            filter_frame,
            text="Search by Product:",
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            text_color=c["text_muted"],
        ).pack(anchor="w", pady=(0, 4))

        self.product_search = ctk.CTkEntry(
            filter_frame,
            placeholder_text="Type product name...",
            height=36,
            fg_color=c["input"],
            border_color=c["border"],
            text_color=c["text"],
        )
        self.product_search.pack(fill="x", pady=(0, 12))
        self.product_search.bind("<KeyRelease>", lambda _e: self._schedule_history_load())

        date_frame = ctk.CTkFrame(filter_frame, fg_color="transparent")
        date_frame.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(
            date_frame,
            text="Filter by Date:",
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            text_color=c["text_muted"],
        ).pack(anchor="w", pady=(0, 4))

        date_entry_frame = ctk.CTkFrame(date_frame, fg_color="transparent")
        date_entry_frame.pack(fill="x")

        self.date_var = tk.StringVar(value=str(date.today()))

        self.date_entry = ctk.CTkEntry(
            date_entry_frame,
            textvariable=self.date_var,
            height=36,
            fg_color=c["input"],
            border_color=c["border"],
            text_color=c["text"],
            state="readonly",
        )
        self.date_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.calendar_btn = ctk.CTkButton(
            date_entry_frame,
            text="📅",
            width=50,
            height=36,
            fg_color=c["input"],
            hover_color=c["border"],
            text_color=c["text"],
            font=ctk.CTkFont("Segoe UI", 14),
            command=self._open_calendar_popup,
        )
        self.calendar_btn.pack(side="right", padx=(0, 8))

        self.clear_date_btn = ctk.CTkButton(
            date_entry_frame,
            text="Clear",
            width=60,
            height=36,
            fg_color=c["input"],
            hover_color=c["border"],
            text_color=c["text"],
            command=self._clear_date_filter,
        )
        self.clear_date_btn.pack(side="right")

        ctk.CTkLabel(
            filter_frame,
            text="Filter by Category:",
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            text_color=c["text_muted"],
        ).pack(anchor="w", pady=(0, 4))

        self.category_var = ctk.StringVar(value="All Categories")
        self.category_menu = ctk.CTkOptionMenu(
            filter_frame,
            values=["All Categories"],
            variable=self.category_var,
            fg_color=c["input"],
            button_color=c["border"],
            text_color=c["text"],
            dropdown_fg_color=c["card"],
            command=lambda _value: self._load_history(),
        )
        self.category_menu.pack(fill="x", pady=(0, 12))

        self.filter_btn = ctk.CTkButton(
            filter_frame,
            text="Apply Filters",
            height=36,
            fg_color=AMBER,
            hover_color=AMBER_DARK,
            text_color="#0F0F0F",
            command=self._load_history,
        )
        self.filter_btn.pack(fill="x", pady=(0, 8))

        self.reset_btn = ctk.CTkButton(
            filter_frame,
            text="Reset Filters",
            height=36,
            fg_color=c["input"],
            hover_color=c["border"],
            text_color=c["text"],
            command=self._reset_filters,
        )
        self.reset_btn.pack(fill="x")

        self.hist_frame = ctk.CTkScrollableFrame(hist_card)
        self.hist_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self._show_recipe_message("Loading products with recipes...")
        self._show_history_message("Loading production history...")

    def _load_setup_async(self):
        token = object()
        self._setup_token = token

        if not self._setup_loaded_once:
            self.product_menu.configure(values=["Loading products..."])
            self.product_var.set("Loading products...")
            self.category_menu.configure(values=["All Categories"])
            self.category_var.set("All Categories")
            self._show_recipe_message("Loading products with recipes...")

        run_in_thread(
            self,
            self._fetch_setup_data,
            on_success=self._apply_setup_data,
            on_error=self._handle_setup_error,
            is_current=lambda: self._setup_token is token,
        )

    def _fetch_setup_data(self):
        all_products = ProductDB.get_all_products() or []
        recipe_product_ids = RecipeDB.get_product_ids_with_recipes()
        products = [product for product in all_products if product.product_id in recipe_product_ids]
        categories = sorted({product.category for product in all_products if getattr(product, "category", None)})
        product_names = [f"{product.product_id} — {product.name}" for product in products]
        return {
            "products": products,
            "product_names": product_names,
            "category_values": ["All Categories"] + categories,
        }

    def _apply_setup_data(self, data):
        self.products = data.get("products", [])
        product_names = data.get("product_names") or []
        category_values = data.get("category_values") or ["All Categories"]

        self.product_map = {f"{product.product_id} — {product.name}": product for product in self.products}

        current_product = self.product_var.get()
        if current_product not in self.product_map:
            current_product = product_names[0] if product_names else "No products"

        self.product_menu.configure(values=product_names or ["No products"])
        self.product_var.set(current_product)

        current_category = self.category_var.get()
        self.category_menu.configure(values=category_values)
        self.category_var.set(current_category if current_category in category_values else "All Categories")

        self._setup_loaded_once = True

        if current_product in self.product_map:
            self._on_product_select(current_product)
        else:
            self._show_recipe_message("No products with recipes available.")

    def _handle_setup_error(self, _exc):
        if not self._setup_loaded_once:
            self.product_menu.configure(values=["No products"])
            self.product_var.set("No products")
            self.category_menu.configure(values=["All Categories"])
            self.category_var.set("All Categories")
            self._show_recipe_message("Products could not be loaded.")

    def _open_calendar_popup(self):
        c = self.c

        popup = ctk.CTkToplevel(self)
        popup.title("Select Date")
        popup.geometry("300x300")
        popup.resizable(False, False)
        popup.configure(fg_color=c["card"])
        popup.grab_set()

        popup.update_idletasks()
        x = (popup.winfo_screenwidth() // 2) - 150
        y = (popup.winfo_screenheight() // 2) - 150
        popup.geometry(f"300x300+{x}+{y}")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Dark.TCalendar",
            background=c["card"],
            foreground=c["text"],
            bordercolor=c["border"],
            lightcolor=c["input"],
            darkcolor=c["card"],
            selectbackground=AMBER,
            selectforeground="#0F0F0F",
            fieldbackground=c["input"],
            fieldforeground=c["text"],
        )

        current_date = self.date_var.get().strip()
        try:
            if current_date:
                year, month, day = map(int, current_date.split("-"))
                calendar_date = date(year, month, day)
            else:
                calendar_date = date.today()
        except Exception:
            calendar_date = date.today()

        calendar = Calendar(
            popup,
            selectmode="day",
            year=calendar_date.year,
            month=calendar_date.month,
            day=calendar_date.day,
            date_pattern="yyyy-mm-dd",
            background=c["card"],
            foreground=c["text"],
            bordercolor=c["border"],
            selectbackground=AMBER,
            selectforeground="#0F0F0F",
            normalbackground=c["input"],
            normalforeground=c["text"],
            weekendbackground=c["card"],
            weekendforeground=c["text_muted"],
            othermonthbackground=c["input"],
            othermonthforeground=c["text_muted"],
            headersbackground=c["card"],
            headersforeground=AMBER,
            showweeknumbers=False,
        )
        calendar.pack(padx=10, pady=10, fill="both", expand=True)

        btn_frame = ctk.CTkFrame(popup, fg_color="transparent")
        btn_frame.pack(pady=(0, 10))

        def select_date():
            self.date_var.set(calendar.get_date())
            self._load_history()
            popup.destroy()

        ctk.CTkButton(
            btn_frame,
            text="Select",
            width=100,
            height=32,
            fg_color=AMBER,
            hover_color=AMBER_DARK,
            text_color="#0F0F0F",
            command=select_date,
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame,
            text="Cancel",
            width=100,
            height=32,
            fg_color=c["input"],
            hover_color=c["border"],
            text_color=c["text"],
            command=popup.destroy,
        ).pack(side="left", padx=5)

    def _show_recipe_message(self, message, color=None):
        for widget in self.recipe_frame.winfo_children():
            widget.destroy()

        ctk.CTkLabel(
            self.recipe_frame,
            text=message,
            text_color=color or self.c["text_muted"],
        ).pack(anchor="w", pady=8)

    def _on_product_select(self, selection):
        product = self.product_map.get(selection)
        if not product:
            self._show_recipe_message("No recipe.")
            return

        token = object()
        self._recipe_token = token
        self._show_recipe_message("Loading recipe...")

        run_in_thread(
            self,
            lambda: RecipeDB.get_recipe(product.product_id),
            on_success=self._render_recipe,
            on_error=lambda _exc: self._show_recipe_message("Recipe could not be loaded.", ERROR_RED),
            is_current=lambda: self._recipe_token is token,
        )

    def _render_recipe(self, recipe):
        for widget in self.recipe_frame.winfo_children():
            widget.destroy()

        if not recipe:
            self._show_recipe_message("No recipe.", ERROR_RED)
            return

        for item in recipe.ingredients:
            ctk.CTkLabel(
                self.recipe_frame,
                text=f"{item['ingredient'].name} - {item['amount']} {item['ingredient'].unit}",
            ).pack(anchor="w")

    def _produce(self):
        self.status_label.configure(text="", text_color=ERROR_RED)

        product = self.product_map.get(self.product_var.get())
        if not product:
            self.status_label.configure(text="Select a product.")
            return

        try:
            quantity = int(self.qty_entry.get().strip())
            if quantity <= 0 or quantity > 1000:
                raise ValueError
        except Exception:
            self.status_label.configure(text="Invalid quantity.")
            return

        self.produce_btn.configure(text="PRODUCING...", state="disabled")
        self.status_label.configure(text="Processing production...", text_color=self.c["text_muted"])

        token = object()
        self._produce_token = token
        run_in_thread(
            self,
            lambda: self._produce_worker(product, quantity),
            on_success=self._handle_produce_result,
            on_error=self._handle_produce_error,
            is_current=lambda: self._produce_token is token,
        )

    def _produce_worker(self, product, quantity):
        recipe = RecipeDB.get_recipe(product.product_id)
        if not recipe:
            return {"ok": False, "message": "No recipe found for this product."}

        for item in recipe.ingredients:
            required = item["amount"] * quantity
            available = item["ingredient"].quantity
            if available < required:
                return {
                    "ok": False,
                    "message": f"Not enough {item['ingredient'].name}! Available: {available}",
                }

        for item in recipe.ingredients:
            IngredientDB.deduct_ingredient(
                item["ingredient"].ingredient_id,
                item["amount"] * quantity,
            )

        prod_date = date.today()
        expiry = prod_date + timedelta(days=product.shelf_life_days)
        ProductionDB.log_production(product.product_id, product, quantity, prod_date)
        InventoryDB.add_batch(product.product_id, quantity, prod_date, expiry)

        return {"ok": True, "message": f"Produced {quantity} {product.name}!"}

    def _handle_produce_result(self, result):
        self.produce_btn.configure(text="PRODUCE", state="normal")

        if not result.get("ok"):
            self.status_label.configure(text=result.get("message", "Production failed."), text_color=ERROR_RED)
            return

        self.status_label.configure(text=result["message"], text_color=SUCCESS)
        self.qty_entry.delete(0, "end")
        self._load_history()

    def _handle_produce_error(self, exc):
        self.produce_btn.configure(text="PRODUCE", state="normal")
        self.status_label.configure(text=f"Error: {exc}", text_color=ERROR_RED)

    def _show_history_message(self, message):
        for widget in self.hist_frame.winfo_children():
            widget.destroy()

        ctk.CTkLabel(
            self.hist_frame,
            text=message,
            font=ctk.CTkFont("Segoe UI", 12),
            text_color=self.c["text_muted"],
        ).pack(pady=40)

    def _schedule_history_load(self):
        if self._history_search_after_id is not None:
            try:
                self.after_cancel(self._history_search_after_id)
            except Exception:
                pass

        self._history_search_after_id = self.after(180, self._run_scheduled_history_load)

    def _run_scheduled_history_load(self):
        self._history_search_after_id = None
        self._load_history()

    def _load_history(self):
        if self._history_search_after_id is not None:
            try:
                self.after_cancel(self._history_search_after_id)
            except Exception:
                pass
            self._history_search_after_id = None

        search_text = self.product_search.get().strip() or None
        date_value = self.date_var.get().strip()
        production_date = date_value if date_value and date_value != "None" else None
        category = self.category_var.get().strip()
        selected_category = category if category != "All Categories" else None

        token = object()
        self._history_token = token

        if not self._history_loaded_once:
            self._show_history_message("Loading production history...")

        run_in_thread(
            self,
            lambda: ProductionDB.get_productions(
                product_name=search_text,
                production_date=production_date,
                category=selected_category,
            ),
            on_success=self._render_history,
            on_error=self._handle_history_error,
            is_current=lambda: self._history_token is token,
        )

    def _render_history(self, productions):
        for widget in self.hist_frame.winfo_children():
            widget.destroy()

        if not productions:
            self._show_history_message("No production records found matching the filters.")
            self._history_loaded_once = True
            return

        for production in productions:
            record_card = ctk.CTkFrame(
                self.hist_frame,
                fg_color=self.c["input"],
                corner_radius=8,
            )
            record_card.pack(fill="x", pady=4, padx=4)

            ctk.CTkLabel(
                record_card,
                text=production.product.name,
                font=ctk.CTkFont("Segoe UI", 12, "bold"),
                text_color=self.c["text"],
            ).pack(anchor="w", padx=12, pady=(8, 2))

            details_frame = ctk.CTkFrame(record_card, fg_color="transparent")
            details_frame.pack(fill="x", padx=12, pady=(0, 8))

            ctk.CTkLabel(
                details_frame,
                text=f"Quantity: {production.quantity} pcs",
                font=ctk.CTkFont("Segoe UI", 11),
                text_color=self.c["text_gray"],
            ).pack(side="left", padx=(0, 16))

            ctk.CTkLabel(
                details_frame,
                text=f"Date: {production.production_date}",
                font=ctk.CTkFont("Segoe UI", 11),
                text_color=self.c["text_gray"],
            ).pack(side="left", padx=(0, 16))

            ctk.CTkLabel(
                details_frame,
                text=f"Category: {production.product.category}",
                font=ctk.CTkFont("Segoe UI", 11),
                text_color=AMBER,
            ).pack(side="left")

        self._history_loaded_once = True

    def _handle_history_error(self, _exc):
        if not self._history_loaded_once:
            self._show_history_message("Production history could not be loaded.")

    def _clear_date_filter(self):
        self.date_var.set("")
        self.date_entry.delete(0, "end")
        self._load_history()

    def _reset_filters(self):
        self.product_search.delete(0, "end")
        self.date_var.set("")
        self.date_entry.delete(0, "end")
        self.category_var.set("All Categories")
        self._load_history()

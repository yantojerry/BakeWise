import customtkinter as ctk
from database.product_db import ProductDB
from gui.async_utils import run_in_thread
from gui.theme import get_colors

CATEGORIES = [
    "All",
    "Bread",
    "Pastry",
    "Cake",
    "Cupcake",
    "Cookie",
    "Donut",
    "Muffin",
    "Pie",
    "Drinks",
    "Savory",
    "Seasonal",
    "Other",
]


class ProductsScreen(ctk.CTkFrame):
    def __init__(self, parent, user):
        self.c = get_colors()
        super().__init__(parent, fg_color=self.c["bg"], corner_radius=0)
        self.user = user
        self._all_products = []
        self._products_load_token = None
        self.pack(fill="both", expand=True)
        self._build_ui()

    def _build_ui(self):
        c = self.c

        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=32, pady=(28, 0))

        ctk.CTkLabel(
            header,
            text="Products",
            font=ctk.CTkFont("Georgia", 28, "bold"),
            text_color=c["text"]
        ).pack(side="left")

        right_actions = ctk.CTkFrame(header, fg_color="transparent")
        right_actions.pack(side="right")

        ctk.CTkButton(
            right_actions,
            text="+ Add Product",
            height=38,
            fg_color=c["amber"],
            hover_color=c["amber_dark"],
            text_color="#0F0F0F",
            corner_radius=8,
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            command=self._open_add_modal
        ).pack(side="left", padx=(0, 10))

        self._search_var = ctk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._apply_filter())

        ctk.CTkEntry(
            right_actions,
            textvariable=self._search_var,
            placeholder_text="Search products...",
            width=220,
            height=38,
            fg_color=c["input"],
            border_color=c["border"],
            text_color=c["text"],
            corner_radius=8,
            font=ctk.CTkFont("Segoe UI", 12)
        ).pack(side="left")

        ctk.CTkFrame(self, fg_color=c["border"], height=1).pack(fill="x", padx=32, pady=(16, 0))

        # Filter row
        filter_row = ctk.CTkFrame(self, fg_color="transparent")
        filter_row.pack(fill="x", padx=32, pady=(14, 0))

        self._cat_var = ctk.StringVar(value="All")
        ctk.CTkOptionMenu(
            filter_row,
            variable=self._cat_var,
            values=CATEGORIES,
            width=150,
            height=36,
            fg_color=c["input"],
            button_color=c["border"],
            button_hover_color=c["amber_dark"],
            text_color=c["text"],
            corner_radius=8,
            font=ctk.CTkFont("Segoe UI", 12),
            command=lambda _: self._apply_filter()
        ).pack(side="left")

        # Table card
        table_card = ctk.CTkFrame(
            self,
            fg_color=c["card"],
            corner_radius=12,
            border_width=1,
            border_color=c["border"]
        )
        table_card.pack(fill="both", expand=True, padx=32, pady=(14, 24))

        thead = ctk.CTkFrame(table_card, fg_color=c["thead"], corner_radius=0, height=44)
        thead.pack(fill="x", padx=1, pady=(1, 0))
        thead.pack_propagate(False)

        for col, width in [
            ("ID", 70),
            ("Name", 220),
            ("Category", 140),
            ("Price", 120),
            ("Shelf Life", 120),
            ("Actions", 160),
        ]:
            ctk.CTkLabel(
                thead,
                text=col,
                width=width,
                font=ctk.CTkFont("Segoe UI", 11, "bold"),
                text_color=c["text_muted"],
                anchor="w"
            ).pack(side="left", padx=12)

        self.rows_frame = ctk.CTkScrollableFrame(table_card, fg_color="transparent")
        self.rows_frame.pack(fill="both", expand=True, padx=1)

        self._load_products()

    def _load_products(self):
        token = object()
        self._products_load_token = token
        self._show_rows_message("Loading products...")
        run_in_thread(
            self,
            lambda: ProductDB.get_all_products() or [],
            on_success=lambda products: self._apply_loaded_products(token, products),
            on_error=lambda exc: self._handle_products_load_error(token, exc),
            is_current=lambda: self._products_load_token is token,
        )

    def _apply_loaded_products(self, token, products):
        if self._products_load_token is not token:
            return
        self._all_products = list(products or [])
        self._apply_filter()

    def _handle_products_load_error(self, token, _exc):
        if self._products_load_token is not token:
            return
        self._all_products = []
        self._show_rows_message("Products could not be loaded.")

    def _show_rows_message(self, message):
        for widget in self.rows_frame.winfo_children():
            widget.destroy()
        ctk.CTkLabel(
            self.rows_frame,
            text=message,
            font=ctk.CTkFont("Segoe UI", 13),
            text_color=self.c["text_muted"],
        ).pack(pady=40)

    def _apply_filter(self):
        query = self._search_var.get().lower().strip()
        category = self._cat_var.get()

        filtered = []
        for p in self._all_products:
            if category != "All" and p.category != category:
                continue
            if query and query not in p.name.lower() and query not in p.category.lower():
                continue
            filtered.append(p)

        self._render_rows(filtered)

    def _render_rows(self, products):
        c = self.c

        for w in self.rows_frame.winfo_children():
            w.destroy()

        if not products:
            ctk.CTkLabel(
                self.rows_frame,
                text="No products found.",
                font=ctk.CTkFont("Segoe UI", 13),
                text_color=c["text_muted"]
            ).pack(pady=40)
            return

        for i, p in enumerate(products):
            row_bg = c["card"] if i % 2 == 0 else c["row_alt"]

            row = ctk.CTkFrame(self.rows_frame, fg_color=row_bg, corner_radius=0, height=48)
            row.pack(fill="x")
            row.pack_propagate(False)

            ctk.CTkLabel(
                row, text=str(p.product_id), width=70,
                font=ctk.CTkFont("Segoe UI", 12),
                text_color=c["amber"], anchor="w"
            ).pack(side="left", padx=12)

            ctk.CTkLabel(
                row, text=p.name, width=220,
                font=ctk.CTkFont("Segoe UI", 12, "bold"),
                text_color=c["text"], anchor="w"
            ).pack(side="left", padx=12)

            ctk.CTkLabel(
                row, text=p.category, width=140,
                font=ctk.CTkFont("Segoe UI", 12),
                text_color=c["text_gray"], anchor="w"
            ).pack(side="left", padx=12)

            ctk.CTkLabel(
                row, text=f"₱{p.price:,.2f}", width=120,
                font=ctk.CTkFont("Segoe UI", 12),
                text_color=c["success"], anchor="w"
            ).pack(side="left", padx=12)

            ctk.CTkLabel(
                row, text=f"{p.shelf_life_days} days", width=120,
                font=ctk.CTkFont("Segoe UI", 12),
                text_color=c["text_gray"], anchor="w"
            ).pack(side="left", padx=12)

            actions = ctk.CTkFrame(row, fg_color="transparent", width=160)
            actions.pack(side="left", padx=12)

            ctk.CTkButton(
                actions,
                text="Edit",
                width=60,
                height=28,
                fg_color=c["success_bg"],
                hover_color=c["success_hover"],
                text_color=c["success"],
                corner_radius=6,
                font=ctk.CTkFont("Segoe UI", 11),
                command=lambda pid=p.product_id: self._open_edit_modal(pid)
            ).pack(side="left", padx=(0, 6))

            ctk.CTkButton(
                actions,
                text="Delete",
                width=60,
                height=28,
                fg_color=c["error_bg"],
                hover_color=c["error_hover"],
                text_color=c["error"],
                corner_radius=6,
                font=ctk.CTkFont("Segoe UI", 11),
                command=lambda pid=p.product_id, pname=p.name: self._delete_product(pid, pname)
            ).pack(side="left")

    def _open_add_modal(self):
        self._open_modal("Add Product")

    def _open_edit_modal(self, product_id):
        p = ProductDB.get_product(product_id)
        if p:
            self._open_modal("Edit Product", p)

    def _open_modal(self, title, product=None):
        c = self.c

        modal = ctk.CTkToplevel(self)
        modal.title(title)
        modal.geometry("520x560")
        modal.resizable(False, False)
        modal.configure(fg_color=c["card"])
        modal.grab_set()

        ctk.CTkLabel(
            modal,
            text=title,
            font=ctk.CTkFont("Georgia", 28, "bold"),
            text_color=c["text"]
        ).pack(pady=(26, 24))

        fields = {}

        form_fields = [
            ("Product Name", "name", product.name if product else ""),
            ("Price (₱)", "price", str(product.price) if product else ""),
            ("Shelf Life (days)", "shelf_life", str(product.shelf_life_days) if product else ""),
        ]

        for label, key, default in form_fields:
            ctk.CTkLabel(
                modal,
                text=label,
                font=ctk.CTkFont("Segoe UI", 12),
                text_color=c["text_muted"]
            ).pack(anchor="w", padx=32, pady=(8, 6))

            entry = ctk.CTkEntry(
                modal,
                width=444,
                height=48,
                fg_color=c["input"],
                border_color=c["border"],
                text_color=c["text"],
                corner_radius=10,
                font=ctk.CTkFont("Segoe UI", 13)
            )
            entry.insert(0, default)
            entry.pack(padx=32)
            fields[key] = entry

        ctk.CTkLabel(
            modal,
            text="Category",
            font=ctk.CTkFont("Segoe UI", 12),
            text_color=c["text_muted"]
        ).pack(anchor="w", padx=32, pady=(8, 6))

        cat_var = ctk.StringVar(value=product.category if product else "Bread")
        ctk.CTkOptionMenu(
            modal,
            variable=cat_var,
            values=CATEGORIES[1:],
            width=444,
            height=48,
            fg_color=c["input"],
            button_color=c["border"],
            button_hover_color=c["amber_dark"],
            text_color=c["text"],
            corner_radius=10,
            font=ctk.CTkFont("Segoe UI", 13)
        ).pack(padx=32)

        fields["category"] = cat_var

        error_lbl = ctk.CTkLabel(
            modal,
            text="",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=c["error"]
        )
        error_lbl.pack(pady=(8, 0))

        def save():
            try:
                name = fields["name"].get().strip()
                category = fields["category"].get()
                price = float(fields["price"].get().strip())
                shelf = int(fields["shelf_life"].get().strip())

                if not name:
                    error_lbl.configure(text="Product name is required.")
                    return

                if product:
                    ProductDB.update_product(product.product_id, name, category, price, shelf)
                else:
                    ProductDB.add_product(name, category, price, shelf)

                modal.destroy()
                self._load_products()

            except ValueError:
                error_lbl.configure(text="Invalid price or shelf life value.")

        ctk.CTkButton(
            modal,
            text="Save",
            width=444,
            height=48,
            fg_color=c["amber"],
            hover_color=c["amber_dark"],
            text_color="#0F0F0F",
            corner_radius=10,
            font=ctk.CTkFont("Segoe UI", 13, "bold"),
            command=save
        ).pack(padx=32, pady=22)

    def _delete_product(self, product_id, name):
        c = self.c

        confirm = ctk.CTkToplevel(self)
        confirm.title("Confirm Delete")
        confirm.geometry("360x180")
        confirm.resizable(False, False)
        confirm.configure(fg_color=c["card"])
        confirm.grab_set()

        ctk.CTkLabel(
            confirm,
            text=f"Delete '{name}'?",
            font=ctk.CTkFont("Segoe UI", 14, "bold"),
            text_color=c["text"]
        ).pack(pady=(24, 8))

        ctk.CTkLabel(
            confirm,
            text="This action cannot be undone.",
            font=ctk.CTkFont("Segoe UI", 12),
            text_color=c["text_muted"]
        ).pack()

        btn_row = ctk.CTkFrame(confirm, fg_color="transparent")
        btn_row.pack(pady=20)

        ctk.CTkButton(
            btn_row,
            text="Cancel",
            width=140,
            height=40,
            fg_color=c["input"],
            hover_color=c["border"],
            text_color=c["text_gray"],
            corner_radius=8,
            command=confirm.destroy
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            btn_row,
            text="Delete",
            width=140,
            height=40,
            fg_color=c["error"],
            hover_color="#B91C1C",
            text_color="#FFFFFF",
            corner_radius=8,
            command=lambda: [
                ProductDB.delete_product(product_id),
                confirm.destroy(),
                self._load_products()
            ]
        ).pack(side="left", padx=6)

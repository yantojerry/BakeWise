import customtkinter as ctk
from database.inventory_db import InventoryDB
from gui.async_utils import run_in_thread
from gui.theme import get_colors, AMBER, SUCCESS, ERROR_RED


class InventoryScreen(ctk.CTkFrame):
    def __init__(self, parent, user):
        self.c = get_colors()
        super().__init__(parent, fg_color=self.c["bg"], corner_radius=0)
        self.user = user
        self.filters_expanded = False
        self.all_batches = []
        self._load_token = None
        self._loaded_once = False
        self.pack(fill="both", expand=True)
        self._build_ui()

    def on_show(self):
        self._refresh_inventory_async()

    def _build_ui(self):
        c = self.c

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=32, pady=(28, 0))

        ctk.CTkLabel(
            header,
            text="Inventory",
            font=ctk.CTkFont("Georgia", 28, "bold"),
            text_color=c["text"],
        ).pack(side="left")

        ctk.CTkFrame(self, fg_color=c["border"], height=1).pack(fill="x", padx=32, pady=20)

        self.main = ctk.CTkFrame(self, fg_color="transparent")
        self.main.pack(fill="both", expand=True, padx=32, pady=(0, 24))
        self.main.grid_rowconfigure(0, weight=1)
        self.main.grid_columnconfigure(0, weight=1)

        self.inventory_card = ctk.CTkFrame(
            self.main,
            fg_color=c["card"],
            corner_radius=14,
            border_width=1,
            border_color=c["border"],
        )
        self.inventory_card.grid(row=0, column=0, sticky="nsew")
        self.inventory_card.grid_rowconfigure(3, weight=1)
        self.inventory_card.grid_columnconfigure(0, weight=1)

        self._build_inventory_card()
        self._build_filter_panel()
        self._toggle_filters(force_state=False)
        self._show_inventory_message("Loading inventory...")

    def _build_inventory_card(self):
        c = self.c

        top_bar = ctk.CTkFrame(self.inventory_card, fg_color="transparent")
        top_bar.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 10))
        top_bar.grid_columnconfigure(0, weight=1)

        title_wrap = ctk.CTkFrame(top_bar, fg_color="transparent")
        title_wrap.grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            title_wrap,
            text="Current Inventory",
            font=ctk.CTkFont("Segoe UI", 16, "bold"),
            text_color=c["text"],
        ).pack(anchor="w")

        self.sub_label = ctk.CTkLabel(
            title_wrap,
            text="View and filter your available batches",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=c["text_muted"],
        )
        self.sub_label.pack(anchor="w", pady=(2, 0))

        self.filter_toggle_btn = ctk.CTkButton(
            top_bar,
            text="Filters",
            width=110,
            height=34,
            corner_radius=8,
            fg_color=c["input"],
            hover_color=c["border"],
            text_color=c["text"],
            command=self._toggle_filters,
        )
        self.filter_toggle_btn.grid(row=0, column=1, sticky="e")

        self.filter_panel = ctk.CTkFrame(
            self.inventory_card,
            fg_color=c["input"],
            corner_radius=10,
            border_width=1,
            border_color=c["border"],
        )
        self.filter_panel.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 14))
        self.filter_panel.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)

        self.stats_bar = ctk.CTkFrame(self.inventory_card, fg_color="transparent")
        self.stats_bar.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 14))
        for i in range(3):
            self.stats_bar.grid_columnconfigure(i, weight=1)

        self.total_batches_label = self._create_stat_card(self.stats_bar, 0, "Batches", "0")
        self.total_quantity_label = self._create_stat_card(self.stats_bar, 1, "Quantity", "0")
        self.total_value_label = self._create_stat_card(self.stats_bar, 2, "Active Value", "₱0.00", value_color=SUCCESS)

        table_wrap = ctk.CTkFrame(self.inventory_card, fg_color="transparent")
        table_wrap.grid(row=3, column=0, sticky="nsew", padx=8, pady=(0, 8))
        table_wrap.grid_rowconfigure(1, weight=1)
        table_wrap.grid_columnconfigure(0, weight=1)

        thead = ctk.CTkFrame(table_wrap, fg_color=c["thead"], corner_radius=8, height=42)
        thead.grid(row=0, column=0, sticky="ew", padx=8, pady=(0, 6))
        thead.grid_propagate(False)
        for idx, weight in enumerate((3, 2, 1, 2, 2, 2)):
            thead.grid_columnconfigure(idx, weight=weight)

        headers = ["Product", "Category", "Qty", "Freshness", "Expiry Date", "Status"]
        for idx, col in enumerate(headers):
            ctk.CTkLabel(
                thead,
                text=col,
                font=ctk.CTkFont("Segoe UI", 11, "bold"),
                text_color=c["text_muted"],
                anchor="w",
            ).grid(row=0, column=idx, sticky="ew", padx=(14 if idx == 0 else 8, 8), pady=10)

        self.inventory_frame = ctk.CTkScrollableFrame(table_wrap, fg_color="transparent")
        self.inventory_frame.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self.inventory_frame.grid_columnconfigure(0, weight=1)

    def _create_stat_card(self, parent, column, label, value, value_color=None):
        c = self.c
        card = ctk.CTkFrame(parent, fg_color=c["input"], corner_radius=10, border_width=1, border_color=c["border"])
        card.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 6, 0 if column == 2 else 6))

        ctk.CTkLabel(
            card,
            text=label,
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            text_color=c["text_muted"],
        ).pack(anchor="w", padx=14, pady=(10, 2))

        value_label = ctk.CTkLabel(
            card,
            text=value,
            font=ctk.CTkFont("Segoe UI", 16, "bold"),
            text_color=value_color or c["text"],
        )
        value_label.pack(anchor="w", padx=14, pady=(0, 10))
        return value_label

    def _build_filter_panel(self):
        c = self.c

        self.search_entry = ctk.CTkEntry(
            self.filter_panel,
            placeholder_text="Search product...",
            height=36,
            fg_color=c["card"],
            border_color=c["border"],
            text_color=c["text"],
        )
        self.search_entry.grid(row=0, column=0, sticky="ew", padx=(14, 6), pady=14)
        self.search_entry.bind("<KeyRelease>", lambda e: self._load_inventory())

        self.category_var = ctk.StringVar(value="All Categories")
        self.category_menu = ctk.CTkOptionMenu(
            self.filter_panel,
            values=["All Categories"],
            variable=self.category_var,
            height=36,
            fg_color=c["card"],
            button_color=c["border"],
            text_color=c["text"],
            dropdown_fg_color=c["card"],
            command=lambda _: self._load_inventory(),
        )
        self.category_menu.grid(row=0, column=1, sticky="ew", padx=6, pady=14)

        self.stock_status_var = ctk.StringVar(value="All Stock")
        self.stock_status_menu = ctk.CTkOptionMenu(
            self.filter_panel,
            values=["All Stock", "Active Stock Only", "Expired Stock Only", "Low Stock (≤10)", "Depleted Only"],
            variable=self.stock_status_var,
            height=36,
            fg_color=c["card"],
            button_color=c["border"],
            text_color=c["text"],
            dropdown_fg_color=c["card"],
            command=lambda _: self._load_inventory(),
        )
        self.stock_status_menu.grid(row=0, column=2, sticky="ew", padx=6, pady=14)

        self.freshness_var = ctk.StringVar(value="All")
        self.freshness_menu = ctk.CTkOptionMenu(
            self.filter_panel,
            values=["All", "FRESH", "GOOD", "AGING", "STALE", "EXPIRED"],
            variable=self.freshness_var,
            height=36,
            fg_color=c["card"],
            button_color=c["border"],
            text_color=c["text"],
            dropdown_fg_color=c["card"],
            command=lambda _: self._load_inventory(),
        )
        self.freshness_menu.grid(row=0, column=3, sticky="ew", padx=6, pady=14)

        self.reset_btn = ctk.CTkButton(
            self.filter_panel,
            text="Reset",
            width=90,
            height=36,
            corner_radius=8,
            fg_color=c["card"],
            hover_color=c["border"],
            text_color=c["text"],
            command=self._reset_filters,
        )
        self.reset_btn.grid(row=0, column=4, sticky="e", padx=(6, 14), pady=14)

    def _clean_batches(self, batches):
        cleaned = []
        for batch in batches or []:
            product = getattr(batch, "product", None)
            if product is None or not hasattr(product, "name"):
                continue
            cleaned.append(batch)
        return cleaned

    def _refresh_category_options(self, batches=None):
        batches = self.all_batches if batches is None else batches
        categories = sorted(
            {
                str(getattr(batch.product, "category", "")).strip()
                for batch in batches
                if str(getattr(batch.product, "category", "")).strip()
            },
            key=str.casefold,
        )
        values = ["All Categories"] + categories
        current = self.category_var.get()
        self.category_menu.configure(values=values)
        self.category_var.set(current if current in values else "All Categories")

    def _show_inventory_message(self, title, subtitle=None):
        for widget in self.inventory_frame.winfo_children():
            widget.destroy()

        empty = ctk.CTkFrame(
            self.inventory_frame,
            fg_color=self.c["input"],
            corner_radius=10,
            border_width=1,
            border_color=self.c["border"],
        )
        empty.pack(fill="x", padx=4, pady=6)
        ctk.CTkLabel(
            empty,
            text=title,
            font=ctk.CTkFont("Segoe UI", 13, "bold"),
            text_color=self.c["text"],
        ).pack(pady=(18, 4))
        if subtitle:
            ctk.CTkLabel(
                empty,
                text=subtitle,
                font=ctk.CTkFont("Segoe UI", 11),
                text_color=self.c["text_muted"],
            ).pack(pady=(0, 18))

    def _refresh_inventory_async(self):
        token = object()
        self._load_token = token

        if not self._loaded_once:
            self._show_inventory_message("Loading inventory...")
            self._update_stats([])
        self.sub_label.configure(text="Loading inventory data...")

        run_in_thread(
            self,
            lambda: self._clean_batches(InventoryDB.get_all_batches() or []),
            on_success=self._apply_inventory_batches,
            on_error=self._handle_inventory_error,
            is_current=lambda: self._load_token is token,
        )

    def _apply_inventory_batches(self, batches):
        self.all_batches = batches
        self._loaded_once = True
        self._refresh_category_options(batches)
        self._load_inventory()

    def _handle_inventory_error(self, _exc):
        if not self._loaded_once:
            self.all_batches = []
            self._refresh_category_options([])
            self._show_inventory_message(
                "No inventory items found.",
                "Inventory data could not be loaded.",
            )
            self._update_stats([])
            self.sub_label.configure(text="0 matching batches")
            return

        self.sub_label.configure(text="Showing cached inventory data")

    def _toggle_filters(self, force_state=None):
        if force_state is None:
            self.filters_expanded = not self.filters_expanded
        else:
            self.filters_expanded = force_state

        if self.filters_expanded:
            self.filter_panel.grid()
            self.filter_toggle_btn.configure(text="Hide Filters")
        else:
            self.filter_panel.grid_remove()
            self.filter_toggle_btn.configure(text="Show Filters")

    def _apply_filters(self, batches):
        search_text = self.search_entry.get().strip().casefold()
        selected_category = self.category_var.get().strip().casefold()
        stock_status = self.stock_status_var.get()
        selected_freshness = self.freshness_var.get().strip().upper()

        filtered = []
        for batch in batches:
            product_name = str(getattr(batch.product, "name", "")).strip()
            category = str(getattr(batch.product, "category", "")).strip()
            quantity = float(getattr(batch, "quantity", 0) or 0)
            is_expired = bool(batch.is_expired())
            freshness_label = "EXPIRED" if is_expired else str(batch.get_freshness_label()).strip().upper()

            if search_text and search_text not in product_name.casefold():
                continue
            if selected_category != "all categories" and category.casefold() != selected_category:
                continue
            if stock_status == "Active Stock Only" and (is_expired or quantity <= 0):
                continue
            if stock_status == "Expired Stock Only" and not is_expired:
                continue
            if stock_status == "Low Stock (≤10)" and (is_expired or quantity <= 0 or quantity > 10):
                continue
            if stock_status == "Depleted Only" and quantity > 0:
                continue
            if selected_freshness != "ALL" and freshness_label != selected_freshness:
                continue

            filtered.append(batch)

        return sorted(
            filtered,
            key=lambda b: (
                bool(b.is_expired()),
                str(getattr(b.product, "name", "")).casefold(),
                str(getattr(b, "expiry_date", "")),
            ),
        )

    def _load_inventory(self):
        for w in self.inventory_frame.winfo_children():
            w.destroy()

        self._refresh_category_options(self.all_batches)
        filtered_batches = self._apply_filters(self.all_batches)

        if not filtered_batches:
            self._show_inventory_message(
                "No inventory items found.",
                "Try changing or resetting the filters.",
            )
            self._update_stats([])
            self.sub_label.configure(text="0 matching batches")
            return

        for index, batch in enumerate(filtered_batches):
            self._create_inventory_row(batch, index)

        self._update_stats(filtered_batches)
        self.sub_label.configure(text=f"{len(filtered_batches)} matching batch{'es' if len(filtered_batches) != 1 else ''}")

    def _create_inventory_row(self, batch, index):
        c = self.c
        row_bg = c["input"] if index % 2 == 0 else c["card"]

        row = ctk.CTkFrame(
            self.inventory_frame,
            fg_color=row_bg,
            corner_radius=10,
            border_width=1,
            border_color=c["border"],
            height=56,
        )
        row.pack(fill="x", pady=4, padx=2)
        row.pack_propagate(False)
        for idx, weight in enumerate((3, 2, 1, 2, 2, 2)):
            row.grid_columnconfigure(idx, weight=weight)

        accent_color = SUCCESS
        if batch.is_expired():
            accent_color = ERROR_RED
        elif float(getattr(batch, "quantity", 0) or 0) <= 0:
            accent_color = c["text_muted"]
        elif float(getattr(batch, "quantity", 0) or 0) <= 10:
            accent_color = AMBER

        accent = ctk.CTkFrame(row, fg_color=accent_color, width=4, corner_radius=8)
        accent.place(x=0, y=8, relheight=0.72)

        product_color = c["text_muted"] if batch.is_expired() else c["text"]
        category_text = str(getattr(batch.product, "category", "") or "N/A")
        quantity = float(getattr(batch, "quantity", 0) or 0)

        if quantity <= 0:
            quantity_text = "0"
            quantity_color = c["text_muted"]
        elif quantity <= 10:
            quantity_text = str(int(quantity) if quantity.is_integer() else quantity)
            quantity_color = AMBER
        else:
            quantity_text = str(int(quantity) if quantity.is_integer() else quantity)
            quantity_color = SUCCESS

        if batch.is_expired():
            freshness_text = "Expired"
            freshness_color = ERROR_RED
        else:
            freshness_percent = batch.get_freshness_percent()
            freshness_label = str(batch.get_freshness_label()).title()
            freshness_text = f"{freshness_label} ({freshness_percent:.0f}%)"
            if freshness_percent >= 75:
                freshness_color = SUCCESS
            elif freshness_percent >= 50:
                freshness_color = c["text"]
            elif freshness_percent >= 25:
                freshness_color = AMBER
            else:
                freshness_color = ERROR_RED

        cells = [
            (str(getattr(batch.product, "name", "")), product_color, (12, 8), "normal"),
            (category_text, c["text_muted"], 8, "normal"),
            (quantity_text, quantity_color, 8, "bold"),
            (freshness_text, freshness_color, 8, "normal"),
            (str(getattr(batch, "expiry_date", "")), ERROR_RED if batch.is_expired() else c["text_muted"], 8, "normal"),
        ]

        for col, (text, color, padx, weight) in enumerate(cells):
            ctk.CTkLabel(
                row,
                text=text,
                font=ctk.CTkFont("Segoe UI", 11 if col else 12, weight),
                text_color=color,
                anchor="w",
            ).grid(row=0, column=col, sticky="ew", padx=padx, pady=14)

        badge_text = "In Stock"
        badge_fg = SUCCESS
        badge_text_color = "#0F0F0F"
        if batch.is_expired():
            badge_text = "Expired"
            badge_fg = ERROR_RED
        elif quantity <= 0:
            badge_text = "Depleted"
            badge_fg = c["border"]
            badge_text_color = c["text"]
        elif quantity <= 10:
            badge_text = "Low Stock"
            badge_fg = AMBER

        badge_wrap = ctk.CTkFrame(row, fg_color="transparent")
        badge_wrap.grid(row=0, column=5, sticky="w", padx=8, pady=12)

        badge = ctk.CTkFrame(badge_wrap, fg_color=badge_fg, corner_radius=999)
        badge.pack(anchor="w")

        ctk.CTkLabel(
            badge,
            text=badge_text,
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            text_color=badge_text_color,
        ).pack(padx=12, pady=5)

    def _update_stats(self, batches=None):
        if batches is None:
            batches = self.all_batches

        total_batches = len(batches)
        total_quantity = sum(max(float(getattr(b, "quantity", 0) or 0), 0) for b in batches)
        total_value = sum(
            float(getattr(b, "quantity", 0) or 0) * float(getattr(b.product, "price", 0) or 0)
            for b in batches
            if not b.is_expired() and float(getattr(b, "quantity", 0) or 0) > 0
        )

        qty_text = int(total_quantity) if float(total_quantity).is_integer() else round(total_quantity, 2)
        self.total_batches_label.configure(text=str(total_batches))
        self.total_quantity_label.configure(text=str(qty_text))
        self.total_value_label.configure(text=f"₱{total_value:,.2f}")

    def _reset_filters(self):
        self.search_entry.delete(0, "end")
        self.category_var.set("All Categories")
        self.stock_status_var.set("All Stock")
        self.freshness_var.set("All")
        self._load_inventory()

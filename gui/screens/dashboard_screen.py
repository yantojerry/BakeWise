from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

import customtkinter as ctk

from database.ingredient_db import IngredientDB
from database.inventory_db import InventoryDB
from database.product_db import ProductDB
from database.transaction_db import TransactionDB
from gui.async_utils import run_in_thread
from gui.theme import get_colors


class DashboardScreen(ctk.CTkFrame):
    def __init__(self, parent, user, on_navigate=None):
        self.c = get_colors()
        super().__init__(parent, fg_color=self.c["bg"], corner_radius=0)
        self.user = user
        self.on_navigate = on_navigate
        self._load_token = None
        self._loaded_once = False
        self.stat_labels = {}
        self.pack(fill="both", expand=True)
        self._build_ui()

    def on_show(self):
        self._refresh_dashboard()

    def _build_ui(self):
        c = self.c

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=32, pady=(28, 0))

        ctk.CTkLabel(
            header,
            text="Dashboard",
            font=ctk.CTkFont("Georgia", 28, "bold"),
            text_color=c["text"],
        ).pack(anchor="w")

        self.subtitle_label = ctk.CTkLabel(
            header,
            text=f"Welcome back, {self.user.get('username', '').capitalize()}  —  {date.today().strftime('%B %d, %Y')}",
            font=ctk.CTkFont("Segoe UI", 13),
            text_color=c["text_muted"],
        )
        self.subtitle_label.pack(anchor="w", pady=(4, 0))

        ctk.CTkFrame(self, fg_color=c["border"], height=1).pack(fill="x", padx=32, pady=20)

        stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        stats_frame.pack(fill="x", padx=32)

        cards = [
            ("products", "Products", c["amber"], "🧁", "products"),
            ("ingredients", "Ingredients", c["blue"], "🌾", "ingredients"),
            ("low_stock", "Low Stock", c["error"], "⚠️", "ingredients"),
            ("inventory_stock", "Inventory Stock", c["success"], "📦", "inventory"),
            ("active_batches", "Active Batches", c["warning"], "📋", "production"),
            ("today_revenue", "Today's Revenue", c["amber"], "💰", "reports"),
        ]

        for index, (key, label, color, icon, target_key) in enumerate(cards):
            card = ctk.CTkFrame(
                stats_frame,
                fg_color=c["card"],
                corner_radius=12,
                border_width=1,
                border_color=c["border"],
            )
            card.grid(row=0, column=index, padx=8, pady=4, sticky="ew")
            stats_frame.grid_columnconfigure(index, weight=1)

            icon_label = ctk.CTkLabel(
                card,
                text=icon,
                font=ctk.CTkFont("Segoe UI Emoji", 24),
                fg_color="transparent",
            )
            icon_label.pack(anchor="w", padx=20, pady=(20, 4))

            value_label = ctk.CTkLabel(
                card,
                text="...",
                font=ctk.CTkFont("Georgia", 26, "bold"),
                text_color=color,
            )
            value_label.pack(anchor="w", padx=20)
            self.stat_labels[key] = value_label

            text_label = ctk.CTkLabel(
                card,
                text=label,
                font=ctk.CTkFont("Segoe UI", 11),
                text_color=c["text_muted"],
            )
            text_label.pack(anchor="w", padx=20, pady=(2, 20))
            self._bind_card_navigation(card, [icon_label, value_label, text_label], target_key)

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(fill="both", expand=True, padx=32, pady=24)
        bottom.grid_columnconfigure(0, weight=2)
        bottom.grid_columnconfigure(1, weight=1)

        tx_card = ctk.CTkFrame(
            bottom,
            fg_color=c["card"],
            corner_radius=12,
            border_width=1,
            border_color=c["border"],
        )
        tx_card.grid(row=0, column=0, padx=(0, 12), sticky="nsew")

        ctk.CTkLabel(
            tx_card,
            text="Recent Transactions",
            font=ctk.CTkFont("Segoe UI", 14, "bold"),
            text_color=c["text"],
        ).pack(anchor="w", padx=20, pady=(20, 4))

        ctk.CTkFrame(tx_card, fg_color=c["border"], height=1).pack(fill="x", padx=20, pady=(0, 12))

        self.tx_body = ctk.CTkFrame(tx_card, fg_color="transparent")
        self.tx_body.pack(fill="both", expand=True)

        ls_card = ctk.CTkFrame(
            bottom,
            fg_color=c["card"],
            corner_radius=12,
            border_width=1,
            border_color=c["border"],
        )
        ls_card.grid(row=0, column=1, sticky="nsew")

        ctk.CTkLabel(
            ls_card,
            text="Low Stock Alert",
            font=ctk.CTkFont("Segoe UI", 14, "bold"),
            text_color=c["text"],
        ).pack(anchor="w", padx=20, pady=(20, 4))

        ctk.CTkFrame(ls_card, fg_color=c["border"], height=1).pack(fill="x", padx=20, pady=(0, 12))

        self.low_stock_body = ctk.CTkFrame(ls_card, fg_color="transparent")
        self.low_stock_body.pack(fill="both", expand=True)

        self._render_loading_state()

    def _bind_card_navigation(self, card, children, target_key):
        if not self.on_navigate or not target_key:
            return

        base_color = card.cget("fg_color")
        base_border = card.cget("border_color")

        def navigate(_event=None):
            self.on_navigate(target_key)

        def on_enter(_event=None):
            card.configure(fg_color=self.c["card_hover"], border_color=self.c["focus"])

        def on_leave(_event=None):
            card.configure(fg_color=base_color, border_color=base_border)

        for widget in [card, *children]:
            widget.bind("<Button-1>", navigate, add="+")
            widget.bind("<Enter>", on_enter, add="+")
            widget.bind("<Leave>", on_leave, add="+")
            try:
                widget.configure(cursor="hand2")
            except Exception:
                pass

    def _render_loading_state(self):
        for container in (self.tx_body, self.low_stock_body):
            for widget in container.winfo_children():
                widget.destroy()

        for label in self.stat_labels.values():
            label.configure(text="...")

        ctk.CTkLabel(
            self.tx_body,
            text="Loading recent transactions...",
            font=ctk.CTkFont("Segoe UI", 12),
            text_color=self.c["text_muted"],
        ).pack(pady=20)

        ctk.CTkLabel(
            self.low_stock_body,
            text="Loading stock alerts...",
            font=ctk.CTkFont("Segoe UI", 12),
            text_color=self.c["text_muted"],
        ).pack(pady=20)

    def _refresh_dashboard(self):
        token = object()
        self._load_token = token

        if not self._loaded_once:
            self._render_loading_state()
        self.subtitle_label.configure(text="Loading dashboard data...")

        run_in_thread(
            self,
            self._fetch_dashboard_data,
            on_success=self._apply_dashboard_data,
            on_error=self._handle_load_error,
            is_current=lambda: self._load_token is token,
        )

    def _fetch_dashboard_data(self):
        tasks = {
            "product_count": (ProductDB.get_product_count, 0),
            "ingredient_count": (IngredientDB.get_ingredient_count, 0),
            "low_stock": (lambda: IngredientDB.get_low_stock() or [], []),
            "inventory_summary": (lambda: InventoryDB.get_inventory_summary(expiring_days=2), {}),
            "today_revenue": (lambda: float(TransactionDB.get_today_revenue()), 0.0),
            "recent_transactions": (
                lambda: TransactionDB.get_recent_transactions(limit=8, include_items=False) or [],
                [],
            ),
        }
        results = {key: default for key, (_worker, default) in tasks.items()}

        with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
            failed_keys = set()
            future_map = {
                executor.submit(worker): (key, default)
                for key, (worker, default) in tasks.items()
            }
            for future in as_completed(future_map):
                key, default = future_map[future]
                try:
                    results[key] = future.result()
                except Exception:
                    results[key] = default
                    failed_keys.add(key)

        return {
            "product_count": results["product_count"],
            "ingredient_count": results["ingredient_count"],
            "low_stock": results["low_stock"],
            "inventory_summary": results["inventory_summary"],
            "today_revenue": results["today_revenue"],
            "recent_transactions": results["recent_transactions"],
            "failed_keys": failed_keys,
        }

    def _apply_dashboard_data(self, data):
        inventory_summary = data.get("inventory_summary") or {}
        low_stock = data.get("low_stock") or []
        failed_keys = data.get("failed_keys") or set()

        self.stat_labels["products"].configure(
            text="—" if "product_count" in failed_keys else str(data.get("product_count", 0))
        )
        self.stat_labels["ingredients"].configure(
            text="—" if "ingredient_count" in failed_keys else str(data.get("ingredient_count", 0))
        )
        self.stat_labels["low_stock"].configure(
            text="—" if "low_stock" in failed_keys else str(len(low_stock))
        )
        self.stat_labels["inventory_stock"].configure(
            text="—" if "inventory_summary" in failed_keys else self._format_number(inventory_summary.get("active_quantity", 0))
        )
        self.stat_labels["active_batches"].configure(
            text="—" if "inventory_summary" in failed_keys else str(inventory_summary.get("active_batches", 0) or 0)
        )
        self.stat_labels["today_revenue"].configure(
            text="—" if "today_revenue" in failed_keys else f"₱{float(data.get('today_revenue', 0) or 0):,.2f}"
        )

        self._render_recent_transactions(
            [] if "recent_transactions" in failed_keys else (data.get("recent_transactions") or [])
        )
        self._render_low_stock([] if "low_stock" in failed_keys else low_stock)

        subtitle = f"Welcome back, {self.user.get('username', '').capitalize()}  —  {date.today().strftime('%B %d, %Y')}"
        if failed_keys:
            subtitle = "Dashboard data could not be fully refreshed."
        self.subtitle_label.configure(text=subtitle)
        self._loaded_once = True

    def _handle_load_error(self, _exc):
        if not self._loaded_once:
            self._render_recent_transactions([])
            self._render_low_stock([])
            for label in self.stat_labels.values():
                label.configure(text="0")
            self.stat_labels["today_revenue"].configure(text="₱0.00")

        self.subtitle_label.configure(text="Dashboard data could not be refreshed.")

    def _format_number(self, value):
        number = float(value or 0)
        if number.is_integer():
            return str(int(number))
        return f"{number:,.2f}"

    def _is_voided(self, tx):
        return bool(getattr(tx, "is_voided", 0))

    def _get_transaction_total(self, tx):
        try:
            total = tx.get_total()
            if total is not None:
                return float(total)
        except Exception:
            pass

        for attr in ("amount_paid", "total", "grand_total", "total_amount"):
            try:
                value = getattr(tx, attr, None)
                if value not in (None, ""):
                    return float(value)
            except Exception:
                continue

        return 0.0

    def _render_recent_transactions(self, transactions):
        for widget in self.tx_body.winfo_children():
            widget.destroy()

        if not transactions:
            ctk.CTkLabel(
                self.tx_body,
                text="No transactions yet",
                font=ctk.CTkFont("Segoe UI", 12),
                text_color=self.c["text_muted"],
            ).pack(pady=20)
            return

        for transaction in transactions:
            row = ctk.CTkFrame(self.tx_body, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=3)

            status_color = self.c["error"] if self._is_voided(transaction) else self.c["success"]
            status_text = "VOID" if self._is_voided(transaction) else "OK"

            ctk.CTkLabel(
                row,
                text=f"#{getattr(transaction, 'transaction_id', '-')}",
                font=ctk.CTkFont("Segoe UI", 12, "bold"),
                text_color=self.c["amber"],
                width=40,
            ).pack(side="left")

            ctk.CTkLabel(
                row,
                text=str(getattr(transaction, "date", "")),
                font=ctk.CTkFont("Segoe UI", 11),
                text_color=self.c["text_muted"],
            ).pack(side="left", padx=8)

            ctk.CTkLabel(
                row,
                text=f"₱{self._get_transaction_total(transaction):,.2f}",
                font=ctk.CTkFont("Segoe UI", 12),
                text_color=self.c["text"],
            ).pack(side="left")

            ctk.CTkLabel(
                row,
                text=status_text,
                font=ctk.CTkFont("Segoe UI", 10, "bold"),
                text_color=status_color,
            ).pack(side="right")

    def _render_low_stock(self, rows):
        for widget in self.low_stock_body.winfo_children():
            widget.destroy()

        if not rows:
            ctk.CTkLabel(
                self.low_stock_body,
                text="✓  All stocked",
                font=ctk.CTkFont("Segoe UI", 12),
                text_color=self.c["success"],
            ).pack(pady=20)
            return

        for item in rows:
            row = ctk.CTkFrame(self.low_stock_body, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=3)

            ctk.CTkLabel(
                row,
                text="⚠",
                font=ctk.CTkFont("Segoe UI", 12),
                text_color=self.c["error"],
            ).pack(side="left")

            ctk.CTkLabel(
                row,
                text=getattr(item, "name", ""),
                font=ctk.CTkFont("Segoe UI", 12),
                text_color=self.c["text"],
            ).pack(side="left", padx=8)

            ctk.CTkLabel(
                row,
                text=f"{getattr(item, 'quantity', 0)} {getattr(item, 'unit', '')}",
                font=ctk.CTkFont("Segoe UI", 11),
                text_color=self.c["error"],
            ).pack(side="right")

import csv
import os
import tempfile
import tkinter as tk
from datetime import date, datetime
from decimal import Decimal
from tkinter import filedialog, messagebox

import customtkinter as ctk

from database.inventory_db import InventoryDB
from database.product_db import ProductDB
from database.transaction_db import TransactionDB
from gui.async_utils import run_in_thread
from gui.theme import AMBER, AMBER_DARK, ERROR_RED, SUCCESS, get_colors
from models.transaction import Transaction


class DBInventoryProxy:
    def reserve_fifo(self, product_id, quantity):
        return InventoryDB.reserve_fifo(product_id, quantity)

    def restore_deductions(self, deductions):
        return InventoryDB.restore_deductions(deductions)

    def get_available_quantity(self, product_id):
        return InventoryDB.get_available_quantity(product_id)

    def get_available_quantities(self, product_ids=None):
        return InventoryDB.get_available_quantities(product_ids)


class SearchKeyboardPopup(ctk.CTkToplevel):
    KEY_ROWS = [
        ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"],
        list("QWERTYUIOP"),
        list("ASDFGHJKL"),
        list("ZXCVBNM"),
    ]

    def __init__(self, parent, colors, anchor_widget, on_key, on_backspace, on_clear, on_space, on_search):
        super().__init__(parent)
        self.colors = colors
        self.anchor_widget = anchor_widget
        self.on_key = on_key
        self.on_backspace = on_backspace
        self.on_clear = on_clear
        self.on_space = on_space
        self.on_search = on_search

        self.title("Search Keyboard")
        self.geometry("620x270")
        self.resizable(False, False)
        self.transient(parent)
        self.configure(fg_color=colors["bg"])

        self._build_ui()
        self._position_window(parent)
        self.after(40, self.lift)

    def _build_ui(self):
        c = self.colors
        container = ctk.CTkFrame(
            self,
            fg_color=c["card"],
            corner_radius=18,
            border_width=1,
            border_color=c["border"],
        )
        container.pack(fill="both", expand=True, padx=8, pady=8)

        header = ctk.CTkFrame(container, fg_color="transparent")
        header.pack(fill="x", padx=14, pady=(12, 8))
        ctk.CTkLabel(
            header,
            text="Search Keyboard",
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            text_color=c["text"],
        ).pack(side="left")
        ctk.CTkButton(
            header,
            text="Close",
            width=72,
            height=30,
            fg_color=c["input"],
            hover_color=c["border"],
            text_color=c["text"],
            corner_radius=10,
            font=ctk.CTkFont("Segoe UI", 11),
            command=self.destroy,
        ).pack(side="right")

        body = ctk.CTkFrame(container, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        for row_keys in self.KEY_ROWS:
            row = ctk.CTkFrame(body, fg_color="transparent")
            row.pack(fill="x", pady=4)
            for key in row_keys:
                ctk.CTkButton(
                    row,
                    text=key,
                    width=54,
                    height=38,
                    fg_color=c["input"],
                    hover_color=c["border"],
                    text_color=c["text"],
                    corner_radius=10,
                    font=ctk.CTkFont("Segoe UI", 11, "bold"),
                    command=lambda value=key: self.on_key(value),
                ).pack(side="left", padx=3)

        actions = ctk.CTkFrame(body, fg_color="transparent")
        actions.pack(fill="x", pady=(8, 0))
        ctk.CTkButton(
            actions,
            text="Space",
            width=164,
            height=40,
            fg_color=c["input"],
            hover_color=c["border"],
            text_color=c["text"],
            corner_radius=10,
            font=ctk.CTkFont("Segoe UI", 11),
            command=self.on_space,
        ).pack(side="left", padx=(0, 6))
        ctk.CTkButton(
            actions,
            text="Back",
            width=96,
            height=40,
            fg_color=c["input"],
            hover_color=c["border"],
            text_color=c["text"],
            corner_radius=10,
            font=ctk.CTkFont("Segoe UI", 11),
            command=self.on_backspace,
        ).pack(side="left", padx=6)
        ctk.CTkButton(
            actions,
            text="Clear",
            width=96,
            height=40,
            fg_color=c["input"],
            hover_color=c["border"],
            text_color=c["text"],
            corner_radius=10,
            font=ctk.CTkFont("Segoe UI", 11),
            command=self.on_clear,
        ).pack(side="left", padx=6)
        ctk.CTkButton(
            actions,
            text="Search",
            width=118,
            height=40,
            fg_color=AMBER,
            hover_color=AMBER_DARK,
            text_color="#0F0F0F",
            corner_radius=10,
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            command=self.on_search,
        ).pack(side="right")

    def _position_window(self, parent):
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()

        if self.anchor_widget is not None and self.anchor_widget.winfo_exists():
            x = self.anchor_widget.winfo_rootx()
            y = self.anchor_widget.winfo_rooty() + self.anchor_widget.winfo_height() + 8
        else:
            x = parent.winfo_rootx() + max((parent.winfo_width() - width) // 2, 20)
            y = parent.winfo_rooty() + max((parent.winfo_height() - height) // 2, 20)

        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = min(max(x, 20), max(screen_width - width - 20, 20))
        y = min(max(y, 20), max(screen_height - height - 60, 20))
        self.geometry(f"{width}x{height}+{x}+{y}")


class POSScreen(ctk.CTkFrame):
    def __init__(self, parent, user, workspace_mode="Walk-In", locked_workspace=None, show_source_switcher=True):
        self.c = get_colors()
        super().__init__(parent, fg_color=self.c["bg"], corner_radius=0)
        self.user = user
        self.screen_active = True
        self.show_source_switcher = bool(show_source_switcher)
        self.locked_workspace = self._normalize_workspace_mode(locked_workspace) if locked_workspace else None
        initial_workspace = self.locked_workspace or self._normalize_workspace_mode(workspace_mode)
        self.default_workspace = initial_workspace
        self.transaction = Transaction(None, user.get("username", "cashier"))
        self.inventory_proxy = DBInventoryProxy()
        self.products_cache = []
        self.product_stock_cache = {}
        self.products_loaded = False
        self.walkin_product_card_views = {}
        self.walkin_cart_item_views = {}
        self.walkin_cart_empty_label = None
        self.browse_cart_render_mode = None
        self.online_orders_cache = []
        self.pending_online_orders_snapshot = []
        self.accepted_online_orders_snapshot = []
        self.online_orders_loaded_once = False
        self.online_queue_render_limit = 8
        self.online_queue_render_step = 8
        self.online_queue_search_page_size = 3
        self.online_queue_visible_count = 0
        self.online_queue_page_index = 0
        self.selected_online_order = None
        self.selected_online_order_id = None
        self.online_checkout_source = None
        self.checkout_pickup_start = None
        self.checkout_pickup_end = None
        self.online_wait_labels = {}
        self.online_order_card_views = {}
        self.selected_online_wait_label = None
        self.search_after_id = None
        self.online_orders_accepting = True
        self.pending_online_order_count = 0
        self.accepted_online_order_count = 0
        self.known_pending_online_order_ids = []
        self.known_accepted_online_order_ids = []
        self.online_orders_poll_ready = False
        self.recent_searches = []
        self.search_keyboard_popup = None
        self.recent_dropdown_visible = False
        self.transaction_saved = False
        self.ticket_printed = False
        self.order_notification_cards = []
        self.notification_host = None
        self.search_shell = None
        self.products_grid = None
        self.products_info_label = None
        self.search_var = ctk.StringVar()
        self.amount_var = ctk.StringVar()
        self._sanitizing_amount = False
        self.service_mode_var = ctk.StringVar(value="Take Out")
        self.order_source_var = ctk.StringVar(value=initial_workspace)
        self.online_queue_var = ctk.StringVar(value="Pending")
        self.customer_number_hint_var = ctk.StringVar(value="Receipt No.: TO-001")
        self.finished_preview_dirty = True
        self._product_load_token = None
        self._online_orders_load_token = None
        self._online_order_detail_token = None
        self._online_accepting_token = None
        self._customer_number_hint_token = None
        self._customer_number_hint_key = None
        self._walkin_products_loading = False
        self._online_orders_loading = False
        self._online_order_detail_loading = False
        self._online_orders_poll_inflight = False
        self.pack(fill="both", expand=True)
        self.bind("<Destroy>", self._handle_destroy, add="+")
        self._build_ui()
        self.amount_var.trace_add("write", self._handle_amount_changed)

    def _normalize_workspace_mode(self, value):
        key = str(value or "").strip().lower().replace("_", " ").replace("-", " ")
        return "Online Orders" if key == "online orders" else "Walk-In"

    def _supports_online_queue(self):
        return self.locked_workspace != "Walk-In"

    def _selected_card_bg(self):
        return "#241C08" if ctk.get_appearance_mode() == "Dark" else "#FFF4CC"

    def _selected_button_colors(self):
        if ctk.get_appearance_mode() == "Dark":
            return "#0F0F0F", "#1E1E1E"
        return "#FFF7E0", "#FDE7A2"

    def _success_button_colors(self):
        if ctk.get_appearance_mode() == "Dark":
            return "#1D2712", "#2A3917"
        return "#DCFCE7", "#BBF7D0"

    def _danger_button_colors(self):
        if ctk.get_appearance_mode() == "Dark":
            return "#311818", "#452020"
        return "#FEE2E2", "#FECACA"

    def _status_pill_colors(self, is_accepting):
        if is_accepting:
            if ctk.get_appearance_mode() == "Dark":
                return "#183424", "#B9F5D0", "#20422D", "#2E5A3C", "#D9FFE7"
            return "#DCFCE7", "#166534", "#BBF7D0", "#86EFAC", "#166534"
        if ctk.get_appearance_mode() == "Dark":
            return "#5A1717", "#FFD2D2", "#6A1D1D", "#842525", "#FFE2E2"
        return "#FEE2E2", "#991B1B", "#FECACA", "#FCA5A5", "#991B1B"

    def _build_ui(self):
        c = self.c
        app = self.winfo_toplevel()

        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=22, pady=18)
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(0, weight=1)

        self.browse_view = ctk.CTkFrame(main, fg_color="transparent")
        self.browse_view.grid_columnconfigure(0, weight=8, uniform="browse_main")
        self.browse_view.grid_columnconfigure(1, weight=2, uniform="browse_main")
        self.browse_view.grid_rowconfigure(0, weight=1)
        self._build_products_panel(self.browse_view)
        self._build_browse_cart_panel(self.browse_view)

        self.checkout_view = ctk.CTkScrollableFrame(main, fg_color="transparent")
        self.checkout_view.grid_columnconfigure(0, weight=1)
        self.checkout_view.grid_rowconfigure(0, weight=1)
        self.checkout_view.grid_columnconfigure(0, weight=65, uniform="checkout_main")
        self.checkout_view.grid_columnconfigure(1, weight=35, uniform="checkout_main")
        self.checkout_view.grid_rowconfigure(0, weight=1)
        self._build_checkout_order_panel(self.checkout_view)
        self._build_checkout_payment_panel(self.checkout_view)

        self.finished_view = ctk.CTkFrame(main, fg_color="transparent")
        self.finished_view.grid_columnconfigure(0, weight=60, uniform="finished_main")
        self.finished_view.grid_columnconfigure(1, weight=40, uniform="finished_main")
        self.finished_view.grid_rowconfigure(0, weight=1)
        self._build_finished_preview_panel(self.finished_view)
        self._build_receipt_actions_panel(self.finished_view)

        self._refresh_cart()
        self._show_stage("browse")
        self.after_idle(self._bootstrap_pos_view)
        if self._supports_online_queue():
            self.after(1000, self._tick_online_wait_indicators)
            self.after(2500, self._poll_online_orders)

        if hasattr(app, "register_primary_action"):
            app.register_primary_action(self, on_enter=self._handle_primary_action)
        if hasattr(app, "register_entry"):
            app.register_entry(self.search_entry, "text", on_enter=self._commit_search)
            app.register_entry(
                self.amount_entry,
                "numeric",
                on_enter=self._checkout,
                popup_parent=self,
                popup_mode="pos",
            )

    def _build_products_panel(self, parent):
        c = self.c
        left = ctk.CTkFrame(
            parent,
            fg_color=c["card"],
            corner_radius=16,
            border_width=1,
            border_color=c["border"],
        )
        left.grid(row=0, column=0, padx=(0, 12), sticky="nsew")

        header = ctk.CTkFrame(left, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(18, 8))
        self.products_panel_title_label = ctk.CTkLabel(
            header,
            text="Products",
            font=ctk.CTkFont("Segoe UI", 14, "bold"),
            text_color=c["text"],
        )
        self.products_panel_title_label.pack(side="left")
        self.workspace_badge_label = ctk.CTkLabel(
            header,
            text="",
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            corner_radius=8,
            padx=10,
            pady=4,
        )
        self.workspace_badge_label.pack(side="left", padx=(10, 0))
        header_actions = ctk.CTkFrame(header, fg_color="transparent")
        header_actions.pack(side="right")
        self.refresh_products_button = ctk.CTkButton(
            header_actions,
            text="Refresh",
            width=82,
            height=32,
            fg_color=c["card"],
            hover_color=c["border"],
            text_color=c["text"],
            corner_radius=10,
            border_width=1,
            border_color=c["border"],
            font=ctk.CTkFont("Segoe UI", 10),
            command=self._refresh_products_from_db,
        )
        self.refresh_products_button.pack(side="right")

        source_row = ctk.CTkFrame(left, fg_color="transparent")
        source_row.pack(fill="x", padx=20, pady=(0, 8))
        self.source_row = source_row
        self.order_source_buttons = {}
        for label in ["Walk-In", "Online Orders"]:
            button = ctk.CTkButton(
                source_row,
                text=label,
                height=34,
                fg_color=c["input"],
                hover_color=c["border"],
                text_color=c["text"],
                corner_radius=10,
                font=ctk.CTkFont("Segoe UI", 11, "bold"),
                command=lambda value=label: self._set_order_source_mode(value),
            )
            button.pack(side="left", padx=(0, 8))
            self.order_source_buttons[label] = button
        if not self.show_source_switcher:
            source_row.pack_forget()

        self.online_controls_row = ctk.CTkFrame(left, fg_color="transparent")
        self.online_accepting_status_label = ctk.CTkLabel(
            self.online_controls_row,
            text="",
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            fg_color=c["input"],
            corner_radius=8,
            padx=12,
            pady=6,
            text_color=c["text_muted"],
        )
        self.online_accepting_status_label.pack(side="left")
        self.online_accepting_button = ctk.CTkButton(
            self.online_controls_row,
            text="",
            height=32,
            fg_color=c["input"],
            hover_color=c["border"],
            text_color=c["text"],
            corner_radius=10,
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            command=self._toggle_online_orders_accepting,
        )
        self.online_accepting_button.pack(side="right")

        self.products_info_label = ctk.CTkLabel(
            left,
            text="Live products from the Products list, with available stock shown per item.",
            font=ctk.CTkFont("Segoe UI", 10),
            text_color=c["text_muted"],
        )
        self.products_info_label.pack(anchor="w", padx=20, pady=(0, 10))

        self.online_filters_row = ctk.CTkFrame(left, fg_color="transparent")
        self.online_queue_buttons = {}
        for label in ["Pending", "Accepted"]:
            button = ctk.CTkButton(
                self.online_filters_row,
                text=label,
                height=32,
                fg_color=c["input"],
                hover_color=c["border"],
                text_color=c["text"],
                corner_radius=10,
                font=ctk.CTkFont("Segoe UI", 10, "bold"),
                command=lambda value=label: self._set_online_queue_view(value),
            )
            button.pack(side="left", padx=(0, 8))
            self.online_queue_buttons[label] = button
        self.accept_all_pending_button = ctk.CTkButton(
            self.online_filters_row,
            text="Accept All Pending",
            height=32,
            fg_color=AMBER,
            hover_color=AMBER_DARK,
            text_color="#0F0F0F",
            corner_radius=10,
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            command=self._accept_all_pending_online_orders,
        )
        self.accept_all_pending_button.pack(side="right")

        self.search_var.trace_add("write", lambda *_args: self._schedule_filter_products())

        search_shell = ctk.CTkFrame(
            left,
            fg_color=c["input"],
            corner_radius=12,
            border_width=1,
            border_color=c["border"],
        )
        search_shell.pack(fill="x", padx=20, pady=(0, 8))
        search_shell.pack_propagate(False)
        search_shell.configure(height=50)
        self.search_shell = search_shell

        icon_canvas = tk.Canvas(search_shell, width=28, height=28, bg=c["input"], highlightthickness=0, bd=0)
        icon_canvas.pack(side="left", padx=(12, 4), pady=8)
        icon_canvas.create_oval(4, 4, 16, 16, outline=c["text_muted"], width=2)
        icon_canvas.create_line(15, 15, 23, 23, fill=c["text_muted"], width=2)

        self.search_entry = ctk.CTkEntry(
            search_shell,
            textvariable=self.search_var,
            placeholder_text="Search products",
            placeholder_text_color=c["text_muted"],
            fg_color="transparent",
            border_width=0,
            text_color=c["text"],
            corner_radius=0,
            font=ctk.CTkFont("Segoe UI", 12),
            height=42,
        )
        self.search_entry.pack(side="left", fill="x", expand=True, pady=2)

        ctk.CTkButton(
            search_shell,
            text="Recent",
            width=74,
            height=34,
            fg_color=c["card"],
            hover_color=c["border"],
            text_color=c["text"],
            corner_radius=10,
            font=ctk.CTkFont("Segoe UI", 11),
            command=self._toggle_recent_searches,
        ).pack(side="left", padx=(4, 6), pady=6)

        ctk.CTkButton(
            search_shell,
            text="Keys",
            width=64,
            height=34,
            fg_color=c["card"],
            hover_color=c["border"],
            text_color=c["text"],
            corner_radius=10,
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            command=self._show_search_keyboard,
        ).pack(side="left", padx=(0, 8), pady=6)

        self.recent_dropdown_host = ctk.CTkFrame(left, fg_color="transparent")
        self.products_grid = ctk.CTkScrollableFrame(left, fg_color="transparent")
        self.products_grid.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.products_grid.grid_columnconfigure(0, weight=1, uniform="products_grid")
        self.products_grid.grid_columnconfigure(1, weight=1, uniform="products_grid")
        ctk.CTkLabel(
            self.products_grid,
            text="Loading products...",
            font=ctk.CTkFont("Segoe UI", 12),
            text_color=c["text_muted"],
        ).pack(pady=24)

        self.online_queue_footer = ctk.CTkFrame(left, fg_color="transparent")
        self.online_queue_footer.pack(fill="x", padx=20, pady=(0, 12))
        self.online_queue_footer_label = ctk.CTkLabel(
            self.online_queue_footer,
            text="",
            font=ctk.CTkFont("Segoe UI", 10),
            text_color=c["text_muted"],
            anchor="w",
        )
        self.online_queue_footer_label.pack(side="left", fill="x", expand=True)
        self.online_queue_prev_button = ctk.CTkButton(
            self.online_queue_footer,
            text="Previous",
            width=96,
            height=32,
            fg_color=c["card"],
            hover_color=c["border"],
            text_color=c["text"],
            corner_radius=10,
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            command=self._show_previous_online_orders_page,
        )
        self.online_queue_prev_button.pack(side="right", padx=(0, 8))
        self.online_queue_more_button = ctk.CTkButton(
            self.online_queue_footer,
            text="Next",
            width=96,
            height=32,
            fg_color=c["card"],
            hover_color=c["border"],
            text_color=c["text"],
            corner_radius=10,
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            command=self._load_more_online_orders,
        )
        self.online_queue_more_button.pack(side="right")
        self.online_queue_footer.pack_forget()

    def _build_browse_cart_panel(self, parent):
        c = self.c
        right = ctk.CTkFrame(
            parent,
            fg_color=c["card"],
            corner_radius=16,
            border_width=1,
            border_color=c["border"],
        )
        right.grid(row=0, column=1, sticky="nsew")

        cart_summary = ctk.CTkFrame(
            right,
            fg_color=c["input"],
            corner_radius=12,
            border_width=1,
            border_color=c["border"],
        )
        cart_summary.pack(fill="x", padx=18, pady=(18, 10))
        self.browse_panel_title_label = ctk.CTkLabel(
            cart_summary,
            text="Cart",
            font=ctk.CTkFont("Segoe UI", 14, "bold"),
            text_color=c["text"],
        )
        self.browse_panel_title_label.pack(anchor="w", padx=14, pady=(12, 2))
        self.browse_items_count_label = ctk.CTkLabel(
            cart_summary,
            text="0 items",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=c["text_muted"],
        )
        self.browse_items_count_label.pack(anchor="w", padx=14, pady=(0, 8))
        self.browse_panel_hint_label = ctk.CTkLabel(
            cart_summary,
            text="",
            anchor="w",
            justify="left",
            wraplength=240,
            font=ctk.CTkFont("Segoe UI", 10),
            text_color=c["text_muted"],
        )
        self.browse_panel_hint_label.pack(fill="x", padx=14, pady=(0, 10))

        self.browse_status_label = ctk.CTkLabel(
            right,
            text="",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=ERROR_RED,
        )
        self.browse_status_label.pack(anchor="w", padx=20, pady=(0, 4))

        self.browse_cart_frame = ctk.CTkScrollableFrame(right, fg_color="transparent")
        self.browse_cart_frame.pack(fill="both", expand=True, padx=18, pady=(0, 12))

        footer = ctk.CTkFrame(
            right,
            fg_color=c["input"],
            corner_radius=12,
            border_width=1,
            border_color=c["border"],
        )
        footer.pack(fill="x", padx=18, pady=(0, 18))

        total_row = ctk.CTkFrame(footer, fg_color="transparent")
        total_row.pack(fill="x", padx=14, pady=(12, 8))
        self.browse_total_caption_label = ctk.CTkLabel(
            total_row,
            text="CURRENT TOTAL",
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            text_color=c["text_muted"],
        )
        self.browse_total_caption_label.pack(anchor="w")
        self.browse_total_label = ctk.CTkLabel(
            total_row,
            text="PHP 0.00",
            font=ctk.CTkFont("Georgia", 22, "bold"),
            text_color=AMBER,
        )
        self.browse_total_label.pack(anchor="w", pady=(2, 0))

        self.proceed_button = ctk.CTkButton(
            footer,
            text="Go to Checkout",
            height=48,
            fg_color=AMBER,
            hover_color=AMBER_DARK,
            text_color="#0F0F0F",
            corner_radius=12,
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            command=self._proceed_to_checkout,
        )
        self.proceed_button.pack(fill="x", padx=14, pady=(0, 14))

    def _build_checkout_order_panel(self, parent):
        c = self.c
        top = ctk.CTkFrame(
            parent,
            fg_color=c["card"],
            corner_radius=16,
            border_width=1,
            border_color=c["border"],
        )
        top.grid(row=0, column=1, sticky="nsew")

        header = ctk.CTkFrame(top, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(14, 6))
        left_meta = ctk.CTkFrame(header, fg_color="transparent")
        left_meta.pack(side="left")
        ctk.CTkLabel(
            left_meta,
            text="Added Items",
            font=ctk.CTkFont("Segoe UI", 13, "bold"),
            text_color=c["text"],
        ).pack(anchor="w")
        self.checkout_items_count_label = ctk.CTkLabel(
            left_meta,
            text="0 items",
            font=ctk.CTkFont("Segoe UI", 10),
            text_color=c["text_muted"],
        )
        self.checkout_items_count_label.pack(anchor="w", pady=(2, 0))

        self.back_to_products_button = ctk.CTkButton(
            header,
            text="Back to Products",
            width=138,
            height=34,
            fg_color=c["input"],
            hover_color=c["border"],
            text_color=c["text"],
            corner_radius=10,
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            command=self._return_to_products,
        )
        self.back_to_products_button.pack(side="right")

        self.checkout_details_frame = ctk.CTkFrame(
            top,
            fg_color=c["input"],
            corner_radius=12,
            border_width=1,
            border_color=c["border"],
        )
        self.checkout_details_frame.pack(fill="x", padx=16, pady=(0, 10))
        self.checkout_details_title_label = ctk.CTkLabel(
            self.checkout_details_frame,
            text="Order Details",
            anchor="w",
            justify="left",
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            text_color=c["text_muted"],
        )
        self.checkout_details_title_label.pack(fill="x", padx=12, pady=(10, 2))
        self.checkout_details_primary_label = ctk.CTkLabel(
            self.checkout_details_frame,
            text="",
            anchor="w",
            justify="left",
            wraplength=280,
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            text_color=c["text"],
        )
        self.checkout_details_primary_label.pack(fill="x", padx=12, pady=(0, 2))
        self.checkout_details_meta_label = ctk.CTkLabel(
            self.checkout_details_frame,
            text="",
            anchor="w",
            justify="left",
            wraplength=280,
            font=ctk.CTkFont("Segoe UI", 10),
            text_color=c["text_muted"],
        )
        self.checkout_details_meta_label.pack(fill="x", padx=12, pady=(0, 2))
        self.checkout_details_time_label = ctk.CTkLabel(
            self.checkout_details_frame,
            text="",
            anchor="w",
            justify="left",
            wraplength=280,
            font=ctk.CTkFont("Segoe UI", 10),
            text_color=c["text"],
        )
        self.checkout_details_time_label.pack(fill="x", padx=12, pady=(0, 2))
        self.checkout_details_wait_label = ctk.CTkLabel(
            self.checkout_details_frame,
            text="",
            anchor="w",
            justify="left",
            wraplength=280,
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            text_color=AMBER,
        )
        self.checkout_details_wait_label.pack(fill="x", padx=12, pady=(0, 10))

        self.checkout_cart_frame = ctk.CTkScrollableFrame(top, fg_color="transparent")
        self.checkout_cart_frame.pack(fill="both", expand=True, padx=16, pady=(0, 12))

        footer = ctk.CTkFrame(top, fg_color="transparent")
        footer.pack(fill="x", padx=16, pady=(0, 16))
        summary = ctk.CTkFrame(
            footer,
            fg_color=c["input"],
            corner_radius=12,
            border_width=1,
            border_color=c["border"],
        )
        summary.pack(fill="x", pady=(0, 10))

        self.checkout_context_label = ctk.CTkLabel(
            summary,
            text="Walk-In Order",
            anchor="w",
            justify="left",
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            text_color=c["text_muted"],
        )
        self.checkout_context_label.pack(fill="x", padx=12, pady=(10, 2))
        self.checkout_order_date_label = ctk.CTkLabel(
            summary,
            text="",
            anchor="w",
            justify="left",
            wraplength=280,
            font=ctk.CTkFont("Segoe UI", 10),
            text_color=c["text"],
        )
        self.checkout_order_date_label.pack(fill="x", padx=12, pady=(0, 2))
        self.checkout_order_wait_label = ctk.CTkLabel(
            summary,
            text="",
            anchor="w",
            justify="left",
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            text_color=AMBER,
        )
        self.checkout_order_wait_label.pack(fill="x", padx=12, pady=(0, 8))

        for label_text, value_name in [
            ("TOTAL DUE", "checkout_total_due_value_label"),
            ("CUSTOMER PAYMENT", "checkout_customer_paid_value_label"),
            ("BALANCE", "checkout_delta_value_label"),
        ]:
            row = ctk.CTkFrame(summary, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=2)
            caption_label = ctk.CTkLabel(
                row,
                text=label_text,
                font=ctk.CTkFont("Segoe UI", 10, "bold"),
                text_color=c["text_muted"],
            )
            caption_label.pack(side="left")
            value_label = ctk.CTkLabel(
                row,
                text="PHP 0.00",
                font=ctk.CTkFont("Segoe UI", 13, "bold"),
                text_color=AMBER if label_text == "TOTAL DUE" else c["text"],
            )
            value_label.pack(side="right")
            setattr(self, value_name, value_label)
            if value_name == "checkout_delta_value_label":
                self.checkout_delta_caption_label = caption_label

        self.finish_transaction_button = ctk.CTkButton(
            footer,
            text="Finish Transaction",
            height=48,
            fg_color=AMBER,
            hover_color=AMBER_DARK,
            text_color="#0F0F0F",
            corner_radius=14,
            font=ctk.CTkFont("Segoe UI", 14, "bold"),
            command=self._checkout,
        )
        self.finish_transaction_button.pack(fill="x")

    def _build_checkout_payment_panel(self, parent):
        c = self.c
        keypad_column = ctk.CTkFrame(
            parent,
            fg_color=c["card"],
            corner_radius=16,
            border_width=1,
            border_color=c["border"],
        )
        keypad_column.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        keypad_header = ctk.CTkFrame(keypad_column, fg_color="transparent")
        keypad_header.pack(fill="x", padx=16, pady=(12, 4))
        ctk.CTkLabel(
            keypad_header,
            text="Payment",
            font=ctk.CTkFont("Segoe UI", 13, "bold"),
            text_color=c["text"],
        ).pack(side="left")

        ctk.CTkFrame(keypad_column, fg_color=c["border"], height=1).pack(fill="x", padx=16, pady=(0, 8))

        ctk.CTkLabel(
            keypad_column,
            text="PAYMENT METHOD",
            font=ctk.CTkFont("Segoe UI", 9, "bold"),
            text_color=c["text_muted"],
        ).pack(anchor="w", padx=16, pady=(0, 3))

        self.payment_var = ctk.StringVar(value="Cash")
        payment_row = ctk.CTkFrame(keypad_column, fg_color="transparent")
        payment_row.pack(fill="x", padx=12, pady=(0, 8))
        self.payment_method_controls = []
        for method in ["Cash", "Card", "GCash"]:
            control = ctk.CTkRadioButton(
                payment_row,
                text=method,
                variable=self.payment_var,
                value=method,
                fg_color=AMBER,
                text_color=c["text_gray"],
                font=ctk.CTkFont("Segoe UI", 11),
                command=self._handle_payment_method_changed,
            )
            control.pack(side="left", padx=5)
            self.payment_method_controls.append(control)

        self.service_mode_section = ctk.CTkFrame(keypad_column, fg_color="transparent")
        self.service_mode_section.pack(fill="x")
        self.service_mode_section_label = ctk.CTkLabel(
            self.service_mode_section,
            text="SERVICE MODE",
            font=ctk.CTkFont("Segoe UI", 9, "bold"),
            text_color=c["text_muted"],
        )
        self.service_mode_section_label.pack(anchor="w", padx=16, pady=(0, 3))

        service_row = ctk.CTkFrame(self.service_mode_section, fg_color="transparent")
        service_row.pack(fill="x", padx=12, pady=(0, 8))
        self.service_mode_row = service_row
        self.service_mode_controls = []
        for label in ["Dine In", "Take Out"]:
            control = ctk.CTkRadioButton(
                service_row,
                text=label,
                variable=self.service_mode_var,
                value=label,
                fg_color=AMBER,
                text_color=c["text_gray"],
                font=ctk.CTkFont("Segoe UI", 11),
                command=lambda: [self._update_customer_number_hint(), self._refresh_checkout_summary()],
            )
            control.pack(side="left", padx=5)
            self.service_mode_controls.append(control)

        self.service_mode_note_label = ctk.CTkLabel(
            self.service_mode_section,
            text="Choose dine in or take out for walk-in customers.",
            anchor="w",
            justify="left",
            font=ctk.CTkFont("Segoe UI", 8),
            text_color=c["text_muted"],
        )
        self.service_mode_note_label.pack(fill="x", padx=16, pady=(0, 6))

        self.customer_number_hint_label = ctk.CTkLabel(
            keypad_column,
            textvariable=self.customer_number_hint_var,
            anchor="w",
            justify="left",
            font=ctk.CTkFont("Segoe UI", 9, "bold"),
            text_color=AMBER,
        )
        self.customer_number_hint_label.pack(fill="x", padx=16, pady=(0, 6))

        ctk.CTkLabel(
            keypad_column,
            text="ORDER SOURCE",
            font=ctk.CTkFont("Segoe UI", 9, "bold"),
            text_color=c["text_muted"],
        ).pack(anchor="w", padx=16, pady=(0, 3))

        self.order_source_summary_label = ctk.CTkLabel(
            keypad_column,
            text=self.order_source_var.get(),
            anchor="w",
            justify="left",
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            text_color=c["text"],
        )
        self.order_source_summary_label.pack(fill="x", padx=16, pady=(0, 8))

        ctk.CTkLabel(
            keypad_column,
            text="AMOUNT PAID",
            font=ctk.CTkFont("Segoe UI", 9, "bold"),
            text_color=c["text_muted"],
        ).pack(anchor="w", padx=16, pady=(0, 3))

        self.amount_entry = ctk.CTkEntry(
            keypad_column,
            textvariable=self.amount_var,
            height=40,
            fg_color=c["input"],
            border_color=c["border"],
            text_color=c["text"],
            corner_radius=12,
            font=ctk.CTkFont("Segoe UI", 14, "bold"),
            placeholder_text="0.00",
            placeholder_text_color=c["text_muted"],
            justify="right",
        )
        self.amount_entry.pack(fill="x", padx=16, pady=(0, 6))

        self.error_label = ctk.CTkLabel(
            keypad_column,
            text="",
            font=ctk.CTkFont("Segoe UI", 10),
            text_color=ERROR_RED,
        )
        self.error_label.pack(anchor="w", padx=16, pady=(0, 6))

        keypad_grid = ctk.CTkFrame(keypad_column, fg_color="transparent")
        keypad_grid.pack(fill="both", expand=True, padx=14, pady=(2, 8))
        self._build_numpad(keypad_grid)

        actions = ctk.CTkFrame(keypad_column, fg_color="transparent")
        actions.pack(fill="x", padx=16, pady=(0, 12))
        self.start_new_transaction_button = ctk.CTkButton(
            actions,
            text="Void and New Transaction",
            height=38,
            fg_color=c["input"],
            hover_color="#311818",
            text_color=ERROR_RED,
            corner_radius=12,
            font=ctk.CTkFont("Segoe UI", 11),
            command=self._start_new_transaction,
        )
        self.start_new_transaction_button.pack(fill="x")

    def _build_finished_preview_panel(self, parent):
        c = self.c
        panel = ctk.CTkFrame(
            parent,
            fg_color=c["card"],
            corner_radius=16,
            border_width=1,
            border_color=c["border"],
        )
        panel.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        panel.grid_rowconfigure(2, weight=1)

        header = ctk.CTkFrame(panel, fg_color="transparent")
        header.pack(fill="x", padx=18, pady=(18, 6))
        ctk.CTkLabel(
            header,
            text="Finished Transaction",
            font=ctk.CTkFont("Segoe UI", 15, "bold"),
            text_color=c["text"],
        ).pack(side="left")

        feedback_card = ctk.CTkFrame(
            panel,
            fg_color=c["input"],
            corner_radius=12,
            border_width=1,
            border_color=c["border"],
        )
        feedback_card.pack(fill="x", padx=18, pady=(0, 10))
        self.finished_feedback_label = ctk.CTkLabel(
            feedback_card,
            text="",
            anchor="w",
            justify="left",
            wraplength=500,
            font=ctk.CTkFont("Segoe UI", 10),
            text_color=c["text_muted"],
        )
        self.finished_feedback_label.pack(fill="x", padx=14, pady=12)

        self.preview_frame = ctk.CTkScrollableFrame(
            panel,
            fg_color="transparent",
            scrollbar_button_color=c["card"],
            scrollbar_button_hover_color=c["border"],
        )
        self.preview_frame.pack(fill="both", expand=True, padx=18, pady=(0, 16))

    def _build_receipt_actions_panel(self, parent):
        c = self.c
        panel = ctk.CTkFrame(
            parent,
            fg_color=c["card"],
            corner_radius=16,
            border_width=1,
            border_color=c["border"],
        )
        panel.grid(row=0, column=1, sticky="nsew")
        panel.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(panel, fg_color="transparent")
        header.pack(fill="x", padx=18, pady=(18, 6))
        ctk.CTkLabel(
            header,
            text="Receipt & Actions",
            font=ctk.CTkFont("Segoe UI", 15, "bold"),
            text_color=c["text"],
        ).pack(side="left")

        body = ctk.CTkScrollableFrame(
            panel,
            fg_color="transparent",
            scrollbar_button_color=c["card"],
            scrollbar_button_hover_color=c["border"],
        )
        body.pack(fill="both", expand=True, padx=18, pady=(0, 16))

        status_card = ctk.CTkFrame(
            body,
            fg_color=c["input"],
            corner_radius=12,
            border_width=1,
            border_color=c["border"],
        )
        status_card.pack(fill="x", pady=(0, 12))
        self.receipt_status_label = ctk.CTkLabel(
            status_card,
            text="Finish the transaction to unlock receipt export.",
            anchor="w",
            justify="left",
            wraplength=300,
            font=ctk.CTkFont("Segoe UI", 10),
            text_color=c["text_muted"],
        )
        self.receipt_status_label.pack(fill="x", padx=14, pady=12)

        self.print_ticket_button = ctk.CTkButton(
            body,
            text="Print Ticket",
            height=42,
            fg_color=AMBER,
            hover_color=AMBER_DARK,
            text_color="#0F0F0F",
            corner_radius=12,
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            command=self._print_transaction_ticket,
        )
        self.print_ticket_button.pack(fill="x", pady=(0, 12))

        export_row = ctk.CTkFrame(body, fg_color="transparent")
        export_row.pack(fill="x", pady=(0, 10))
        export_row.grid_columnconfigure(0, weight=1, uniform="receipt_actions")
        export_row.grid_columnconfigure(1, weight=1, uniform="receipt_actions")
        self.export_csv_button = ctk.CTkButton(
            export_row,
            text="Export CSV",
            height=40,
            fg_color=c["input"],
            hover_color=c["border"],
            text_color=c["text"],
            corner_radius=12,
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            command=self._export_receipt_csv,
        )
        self.export_csv_button.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.export_pdf_button = ctk.CTkButton(
            export_row,
            text="Export PDF",
            height=40,
            fg_color=c["input"],
            hover_color=c["border"],
            text_color=c["text"],
            corner_radius=12,
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            command=self._export_receipt_pdf,
        )
        self.export_pdf_button.grid(row=0, column=1, sticky="ew", padx=(6, 0))

        action_row = ctk.CTkFrame(body, fg_color="transparent")
        action_row.pack(fill="x", pady=(0, 6))
        action_row.grid_columnconfigure(0, weight=1, uniform="receipt_actions")
        action_row.grid_columnconfigure(1, weight=1, uniform="receipt_actions")
        self.void_transaction_button = ctk.CTkButton(
            action_row,
            text="Void Transaction",
            height=40,
            fg_color="#311818",
            hover_color="#452020",
            text_color=ERROR_RED,
            corner_radius=12,
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            command=self._void_transaction_action,
        )
        self.void_transaction_button.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.receipt_new_transaction_button = ctk.CTkButton(
            action_row,
            text="Start New",
            height=40,
            fg_color=c["input"],
            hover_color=c["border"],
            text_color=c["text"],
            corner_radius=12,
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            command=self._start_new_transaction,
        )
        self.receipt_new_transaction_button.grid(row=0, column=1, sticky="ew", padx=(6, 0))

    def _show_stage(self, stage):
        self.current_stage = stage
        for view in (self.browse_view, self.checkout_view, self.finished_view):
            if view.winfo_manager() == "grid":
                view.grid_remove()

        if stage == "checkout":
            self._render_checkout_cart()
            self.checkout_view.grid(row=0, column=0, sticky="nsew")
            self._hide_recent_searches()
            if self.search_keyboard_popup is not None and self.search_keyboard_popup.winfo_exists():
                self.search_keyboard_popup.destroy()
            self.after(60, lambda: self.amount_entry.focus_set())
            return

        if stage == "finished":
            self.finished_view.grid(row=0, column=0, sticky="nsew")
            if self.finished_preview_dirty:
                self._render_transaction_preview()
                self.finished_preview_dirty = False
            return

        self._render_browse_cart()
        self.browse_view.grid(row=0, column=0, sticky="nsew")
        self.after(60, lambda: self.search_entry.focus_set())

    def _handle_primary_action(self):
        if self.current_stage == "checkout":
            self._checkout()
        elif self.current_stage == "finished":
            return None
        else:
            self._proceed_to_checkout()

    def _proceed_to_checkout(self):
        self._set_feedback("")
        if self._is_online_mode():
            self._proceed_online_order_to_checkout()
            return
        if not self.transaction.items:
            self._set_feedback("Cart is empty.")
            return
        self._show_stage("checkout")

    def _return_to_products(self):
        if self.transaction_saved:
            self._set_feedback("Start a new transaction to continue selling.")
            return
        self._set_feedback("")
        self.current_stage = "browse"
        self.checkout_view.grid_remove()
        self.finished_view.grid_remove()
        self._render_browse_cart()
        self.browse_view.grid(row=0, column=0, sticky="nsew")
        self._hide_recent_searches()
        if self.search_keyboard_popup is not None and self.search_keyboard_popup.winfo_exists():
            self.search_keyboard_popup.destroy()
        self.after(60, lambda: self.search_entry.focus_set())

    def _set_feedback(self, message):
        self.browse_status_label.configure(text=message)
        self.error_label.configure(text=message)
        self.finished_feedback_label.configure(text=message)

    def _show_products_loading_message(self, message):
        for widget in self.products_grid.winfo_children():
            widget.destroy()

        ctk.CTkLabel(
            self.products_grid,
            text=message,
            font=ctk.CTkFont("Segoe UI", 12),
            text_color=self.c["text_muted"],
            justify="left",
        ).pack(pady=24)

    def _fetch_walkin_product_data(self):
        products = ProductDB.get_all_products() or []
        stock_map = self.inventory_proxy.get_available_quantities(
            [product.product_id for product in products]
        ) if products else {}
        return {
            "products": products,
            "stock_map": stock_map or {},
        }

    def _fetch_online_orders_data(self):
        pending_orders = TransactionDB.get_pending_online_orders(
            limit=60,
            include_items=False,
        )
        accepted_orders = TransactionDB.get_accepted_online_orders(
            limit=60,
            include_items=False,
        )
        return {
            "pending_orders": list(pending_orders or []),
            "accepted_orders": list(accepted_orders or []),
        }

    def _dismiss_order_notification(self, card):
        if card is None:
            return

        dismiss_after_id = getattr(card, "_dismiss_after_id", None)
        if dismiss_after_id is not None:
            try:
                self.after_cancel(dismiss_after_id)
            except Exception:
                pass
            card._dismiss_after_id = None

        if card in self.order_notification_cards:
            self.order_notification_cards.remove(card)

        if card.winfo_exists():
            card.destroy()

    def _show_pending_order_notification(self, title, body):
        return

    def _coerce_datetime(self, value):
        if isinstance(value, datetime):
            return value
        if isinstance(value, date):
            return datetime.combine(value, datetime.min.time())
        if isinstance(value, str) and value.strip():
            cleaned = value.strip().replace("T", " ")
            for pattern, size in [
                ("%Y-%m-%d %H:%M:%S", 19),
                ("%Y-%m-%d %H:%M", 16),
                ("%Y-%m-%d", 10),
            ]:
                try:
                    return datetime.strptime(cleaned[:size], pattern)
                except ValueError:
                    continue
            try:
                return datetime.fromisoformat(cleaned)
            except ValueError:
                return None
        return None

    def _coerce_date(self, value):
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, str) and value.strip():
            try:
                return date.fromisoformat(value[:10])
            except ValueError:
                return None
        return None

    def _is_online_mode(self):
        return self.order_source_var.get() == "Online Orders"

    def _is_preorder_transaction(self, transaction):
        return self._coerce_date(getattr(transaction, "pickup_date_from", None)) is not None

    def _is_accepted_online_order(self, transaction):
        return getattr(transaction, "online_order_status", "") == "accepted"

    def _current_online_queue_name(self):
        return "Accepted" if self.online_queue_var.get() == "Accepted" else "Pending"

    def _current_online_queue_statuses(self):
        return ["accepted"] if self._current_online_queue_name() == "Accepted" else ["pending"]

    def _online_order_status_text(self, transaction):
        status = str(getattr(transaction, "online_order_status", "") or "pending").strip().lower()
        if status == "accepted":
            return "Accepted"
        if status == "processed":
            return "Processed"
        if status == "voided":
            return "Voided"
        return "Pending"

    def _online_order_elapsed_text(self, anchor_value, prefix):
        anchor = self._coerce_datetime(anchor_value)
        if anchor is None:
            return f"{prefix} unavailable"
        elapsed_seconds = max(int((datetime.now() - anchor).total_seconds()), 0)
        hours, remainder = divmod(elapsed_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{prefix} {hours:02d}:{minutes:02d}:{seconds:02d}"

    def _online_order_primary_date_text(self, transaction):
        pickup_date = self._coerce_date(getattr(transaction, "pickup_date_from", None))
        ordered_at = self._coerce_datetime(getattr(transaction, "date", None))
        if pickup_date is not None:
            return f"Pre-Order Date: {pickup_date.isoformat()}"
        if ordered_at is not None:
            return f"Ordered At: {ordered_at.strftime('%b %d, %I:%M %p')}"
        return "Ordered At: -"

    def _online_order_wait_text(self, transaction):
        if self._is_accepted_online_order(transaction) and getattr(transaction, "accepted_at", None):
            return self._online_order_elapsed_text(getattr(transaction, "accepted_at", None), "Accepted wait")

        pickup_date = self._coerce_date(getattr(transaction, "pickup_date_from", None))
        if pickup_date is not None:
            return f"Scheduled for {pickup_date.isoformat()}"

        ordered_at = self._coerce_datetime(getattr(transaction, "date", None))
        if ordered_at is None:
            return "Waiting time unavailable"
        return self._online_order_elapsed_text(
            ordered_at,
            "Pending wait" if self._is_online_mode() or getattr(transaction, "order_source", "") == "Online Orders" else "Waiting",
        )

    def _apply_browse_layout_mode(self):
        left_weight = 6 if self._is_online_mode() else 8
        right_weight = 4 if self._is_online_mode() else 2
        self.browse_view.grid_columnconfigure(0, weight=left_weight, uniform="browse_main")
        self.browse_view.grid_columnconfigure(1, weight=right_weight, uniform="browse_main")

    def _load_online_orders_accepting_state(self):
        token = object()
        self._online_accepting_token = token
        self._update_online_accepting_ui()

        run_in_thread(
            self,
            TransactionDB.get_online_orders_accepting,
            on_success=lambda is_accepting: self._apply_online_orders_accepting_state(token, is_accepting),
            on_error=lambda _exc: self._apply_online_orders_accepting_state(token, True),
            is_current=lambda: self._online_accepting_token is token,
        )

    def _apply_online_orders_accepting_state(self, token, is_accepting):
        if self._online_accepting_token is not token:
            return

        self.online_orders_accepting = bool(is_accepting)
        self._update_online_accepting_ui()

    def _update_online_accepting_ui(self):
        if not hasattr(self, "online_controls_row"):
            return
        is_online = self._is_online_mode()
        if is_online and not self.online_controls_row.winfo_manager():
            self.online_controls_row.pack(fill="x", padx=20, pady=(0, 8))
        if not is_online and self.online_controls_row.winfo_manager():
            self.online_controls_row.pack_forget()

        status_text = "Accepting online orders" if self.online_orders_accepting else "Online orders paused"
        status_fg, status_text_color, button_fg, button_hover, button_text = self._status_pill_colors(
            self.online_orders_accepting
        )
        self.online_accepting_status_label.configure(
            text=status_text,
            fg_color=status_fg,
            text_color=status_text_color,
        )
        self.online_accepting_button.configure(
            text="Pause Orders" if self.online_orders_accepting else "Accept Orders",
            fg_color=button_fg,
            hover_color=button_hover,
            text_color=button_text,
        )

    def _update_online_order_button_label(self):
        if not hasattr(self, "order_source_buttons"):
            return
        button = self.order_source_buttons.get("Online Orders")
        if button is None:
            return
        count = max(int(self.pending_online_order_count or 0), 0) + max(int(self.accepted_online_order_count or 0), 0)
        button.configure(text=f"Online Orders ({count})" if count else "Online Orders")

    def _update_online_queue_ui(self):
        if not hasattr(self, "online_filters_row"):
            return

        is_online = self._is_online_mode()
        if is_online and not self.online_filters_row.winfo_manager():
            self.online_filters_row.pack(fill="x", padx=20, pady=(0, 8), before=self.search_shell)
        if not is_online and self.online_filters_row.winfo_manager():
            self.online_filters_row.pack_forget()

        counts = {
            "Pending": max(int(self.pending_online_order_count or 0), 0),
            "Accepted": max(int(self.accepted_online_order_count or 0), 0),
        }
        for label, button in getattr(self, "online_queue_buttons", {}).items():
            is_active = label == self._current_online_queue_name()
            if label == "Accepted" and is_active:
                fg_color, hover_color = self._success_button_colors()
                text_color = "#166534" if ctk.get_appearance_mode() != "Dark" else SUCCESS
            elif is_active:
                fg_color = AMBER
                hover_color = AMBER_DARK
                text_color = "#0F0F0F"
            else:
                fg_color = self.c["input"]
                hover_color = self.c["border"]
                text_color = self.c["text"]
            count = counts.get(label, 0)
            button.configure(
                text=f"{label} ({count})" if count else label,
                fg_color=fg_color,
                hover_color=hover_color,
                text_color=text_color,
            )

        if hasattr(self, "accept_all_pending_button"):
            show_accept_all = is_online and self._current_online_queue_name() == "Pending"
            pending_count = max(int(self.pending_online_order_count or 0), 0)
            if show_accept_all:
                if not self.accept_all_pending_button.winfo_manager():
                    self.accept_all_pending_button.pack(side="right")
                self.accept_all_pending_button.configure(
                    state="normal" if pending_count > 0 else "disabled",
                    text=f"Accept All ({pending_count})" if pending_count > 0 else "Accept All Pending",
                    fg_color=AMBER if pending_count > 0 else self.c["input"],
                    hover_color=AMBER_DARK if pending_count > 0 else self.c["input"],
                    text_color="#0F0F0F" if pending_count > 0 else self.c["text_muted"],
                )
            elif self.accept_all_pending_button.winfo_manager():
                self.accept_all_pending_button.pack_forget()

    def _accept_all_pending_online_orders(self):
        pending_count = max(int(self.pending_online_order_count or 0), 0)
        if pending_count <= 0:
            self._set_feedback("There are no pending online orders to accept.")
            return
        if self._current_online_queue_name() != "Pending":
            self._set_feedback("Switch to the Pending queue to accept all pending online orders.")
            return

        if not messagebox.askyesno(
            "Accept All Pending Orders",
            f"Accept all {pending_count} pending online orders?\n\nThey will move to the Accepted queue for checkout.",
            parent=self,
        ):
            self._set_feedback("Accept all pending orders cancelled.")
            return

        try:
            accepted_count, _accepted_at = TransactionDB.accept_all_pending_online_orders()
        except Exception as exc:
            self._set_feedback(f"Failed to accept all pending online orders: {exc}")
            return

        self.selected_online_order = None
        self.selected_online_order_id = None
        self._refresh_order_source_ui(force_reload=True)
        if accepted_count <= 0:
            self._set_feedback("There were no pending online orders left to accept.")
            return
        self._set_feedback(
            f"Accepted {accepted_count} pending online order{'s' if accepted_count != 1 else ''}. Open the Accepted queue to process checkout."
        )

    def _set_online_queue_view(self, value):
        normalized = "Accepted" if str(value).strip().lower() == "accepted" else "Pending"
        self.online_queue_var.set(normalized)
        self._reset_online_queue_render_limit()
        self.selected_online_order = None
        self.selected_online_order_id = None
        if self._is_online_mode():
            self._refresh_order_source_ui(force_reload=False)
        else:
            self._update_online_queue_ui()

    def _poll_online_orders(self):
        if not self.winfo_exists():
            return
        if not self._supports_online_queue():
            return
        if not self.screen_active:
            self.after(3000, self._poll_online_orders)
            return
        if self._online_orders_poll_inflight or self._online_orders_loading:
            self.after(3000, self._poll_online_orders)
            return

        self._online_orders_poll_inflight = True
        run_in_thread(
            self,
            self._fetch_online_orders_data,
            on_success=self._handle_online_orders_poll_success,
            on_error=self._handle_online_orders_poll_error,
            is_current=lambda: self.winfo_exists() and self._supports_online_queue(),
        )

    def _handle_online_orders_poll_success(self, data):
        self._online_orders_poll_inflight = False

        pending_orders = list(data.get("pending_orders") or [])
        accepted_orders = list(data.get("accepted_orders") or [])
        previous_ids = list(self.known_pending_online_order_ids)
        previous_accepted_ids = list(self.known_accepted_online_order_ids)
        pending_ids = [row.transaction_id for row in pending_orders if row.transaction_id is not None]
        accepted_ids = [row.transaction_id for row in accepted_orders if row.transaction_id is not None]
        new_ids = [transaction_id for transaction_id in pending_ids if transaction_id not in previous_ids]
        has_baseline = self.online_orders_poll_ready

        self.online_orders_poll_ready = True
        self.online_orders_loaded_once = True
        self.pending_online_orders_snapshot = pending_orders
        self.accepted_online_orders_snapshot = accepted_orders
        self.known_pending_online_order_ids = pending_ids
        self.known_accepted_online_order_ids = accepted_ids
        self.pending_online_order_count = len(pending_ids)
        self.accepted_online_order_count = len(accepted_ids)
        self._update_online_order_button_label()
        self._update_online_queue_ui()

        current_ids = accepted_ids if self._current_online_queue_name() == "Accepted" else pending_ids
        should_reload = self._is_online_mode() and (
            (self._current_online_queue_name() == "Pending" and pending_ids != previous_ids)
            or (self._current_online_queue_name() == "Accepted" and accepted_ids != previous_accepted_ids)
        )
        if self.selected_online_order_id is not None and self.selected_online_order_id not in current_ids:
            should_reload = True

        if should_reload:
            self._load_online_orders(self.search_var.get().strip(), force_reload=False)

        if has_baseline and new_ids:
            newest_order = next(
                (row for row in pending_orders if row.transaction_id == new_ids[0]),
                None,
            )
            if len(new_ids) == 1 and newest_order is not None:
                order_label = newest_order.customer_number or f"Order #{newest_order.transaction_id}"
                order_kind = "pre-order" if self._is_preorder_transaction(newest_order) else "online order"
                self._set_feedback(f"New {order_kind} received in POS: {order_label}.")
            else:
                self._set_feedback(f"{len(new_ids)} new online orders were received in POS.")

        self.after(3000, self._poll_online_orders)

    def _handle_online_orders_poll_error(self, _exc):
        self._online_orders_poll_inflight = False
        self.after(3000, self._poll_online_orders)

    def _toggle_online_orders_accepting(self):
        next_state = not self.online_orders_accepting
        try:
            TransactionDB.set_online_orders_accepting(next_state)
            self.online_orders_accepting = next_state
            self._update_online_accepting_ui()
            self._set_feedback(
                "Online orders are now accepting new requests."
                if next_state
                else "Online orders are now paused for new requests."
            )
        except Exception as exc:
            self._set_feedback(f"Failed to update online order availability: {exc}")

    def _refresh_checkout_summary(self):
        if not hasattr(self, "checkout_total_due_value_label"):
            return

        total = self.transaction.get_total() if getattr(self.transaction, "items", None) is not None else Decimal("0.00")
        amount_paid, amount_error = self._parsed_amount_paid()

        self.checkout_total_due_value_label.configure(text=self._money_text(total))
        self.checkout_customer_paid_value_label.configure(text=self._money_text(amount_paid))

        if amount_paid > total:
            delta_caption = "CHANGE"
            delta_value = amount_paid - total
        elif amount_paid == total:
            delta_caption = "PAID"
            delta_value = Decimal("0.00")
        else:
            delta_caption = "BALANCE"
            delta_value = total - amount_paid
        self.checkout_delta_caption_label.configure(text=delta_caption)
        self.checkout_delta_value_label.configure(text=self._money_text(delta_value))

        if self.online_checkout_source is not None or self._is_online_mode():
            source_transaction = self.online_checkout_source or self.selected_online_order or self.transaction
            self.checkout_context_label.configure(
                text=f"{source_transaction.customer_number or 'Online Order'}  |  {source_transaction.order_source or 'Online Orders'}"
            )
            self.checkout_order_date_label.configure(text=self._online_order_primary_date_text(source_transaction))
            self.checkout_order_wait_label.configure(text=self._online_order_wait_text(source_transaction))
            self.checkout_details_title_label.configure(text="Online Order Details")
            self.checkout_details_primary_label.configure(
                text=f"{source_transaction.customer_number or 'Online Order'}  |  Transaction ID {source_transaction.transaction_id or '-'}"
            )
            self.checkout_details_meta_label.configure(
                text=(
                    f"Source: {source_transaction.order_source or 'Online Orders'}"
                    f"  |  Status: {self._online_order_status_text(source_transaction)}"
                    f"  |  Payment: {source_transaction.payment_method or self.payment_var.get() or '-'}"
                )
            )
            self.checkout_details_time_label.configure(text=self._online_order_primary_date_text(source_transaction))
            self.checkout_details_wait_label.configure(text=self._online_order_wait_text(source_transaction))
        else:
            self.checkout_context_label.configure(
                text=f"{self.order_source_var.get()}  |  {self.service_mode_var.get()}"
            )
            self.checkout_order_date_label.configure(
                text=self.customer_number_hint_var.get()
            )
            self.checkout_order_wait_label.configure(text="")
            self.checkout_details_title_label.configure(text="Checkout Details")
            self.checkout_details_primary_label.configure(text="Walk-In Order")
            self.checkout_details_meta_label.configure(
                text=f"Source: {self.order_source_var.get()}  |  Service: {self.service_mode_var.get()}"
            )
            self.checkout_details_time_label.configure(text=self.customer_number_hint_var.get())
            self.checkout_details_wait_label.configure(text="")

        self._sync_finish_transaction_button_state(amount_error=amount_error)

    def _parsed_amount_paid(self):
        try:
            raw_value = self.amount_var.get().strip()
            if raw_value in {"", "."}:
                return Decimal("0.00"), None
            return Decimal(raw_value), None
        except Exception:
            return Decimal("0.00"), "Enter a valid amount paid."

    def _payment_validation_message(self, amount_error=None):
        if self.transaction_saved:
            return "This sale is already completed."
        if not getattr(self.transaction, "items", None):
            return "Add items before finishing the transaction."
        if amount_error:
            return amount_error

        total = self.transaction.get_total()
        amount_paid, amount_error = self._parsed_amount_paid()
        if amount_error:
            return amount_error

        if amount_paid < total:
            return f"Amount paid must be at least {self._money_text(total)}."
        return ""

    def _sync_finish_transaction_button_state(self, amount_error=None):
        if not hasattr(self, "finish_transaction_button"):
            return
        message = self._payment_validation_message(amount_error=amount_error)
        can_finish = not bool(message)
        self.finish_transaction_button.configure(
            state="normal" if can_finish else "disabled",
            text="Proceed to Finished Order" if self.online_checkout_source is not None else "Finish Transaction",
        )
        if hasattr(self, "error_label") and getattr(self, "current_stage", "browse") == "checkout":
            self.error_label.configure(text=message)

    def _handle_payment_method_changed(self):
        if self.payment_var.get() != "Cash":
            self.amount_var.set(self._amount_text(self.transaction.get_total()))
            self._refresh_checkout_summary()
            return
        self._refresh_checkout_summary()

    def _handle_amount_changed(self, *_args):
        if self._sanitizing_amount:
            return

        raw_value = self.amount_var.get()
        sanitized = self._sanitize_amount_value(raw_value)
        if raw_value != sanitized:
            self._sanitizing_amount = True
            try:
                self.amount_var.set(sanitized)
            finally:
                self._sanitizing_amount = False
            self._refresh_checkout_summary()
            return

        self._refresh_checkout_summary()

    def _sanitize_amount_value(self, value):
        text = str(value or "").strip().replace(",", "")
        if not text:
            return ""

        cleaned = []
        has_decimal = False
        for char in text:
            if char.isdigit():
                cleaned.append(char)
            elif char == "." and not has_decimal:
                cleaned.append(char)
                has_decimal = True

        if not cleaned:
            return ""

        result = "".join(cleaned)
        if result.startswith("."):
            result = f"0{result}"

        if "." in result:
            whole, fraction = result.split(".", 1)
            result = f"{whole or '0'}.{fraction[:2]}"

        return result

    def _tick_online_wait_indicators(self):
        if not self.winfo_exists():
            return
        if not self._supports_online_queue():
            return
        if not self.screen_active:
            self.after(1000, self._tick_online_wait_indicators)
            return

        for transaction_id, label in list(self.online_wait_labels.items()):
            if not label.winfo_exists():
                self.online_wait_labels.pop(transaction_id, None)
                continue
            transaction = next(
                (row for row in self.online_orders_cache if row.transaction_id == transaction_id),
                None,
            )
            if transaction is not None:
                label.configure(text=self._online_order_wait_text(transaction))

        if self.selected_online_wait_label is not None and self.selected_online_wait_label.winfo_exists():
            if self.selected_online_order is not None:
                self.selected_online_wait_label.configure(text=self._online_order_wait_text(self.selected_online_order))

        if self.current_stage == "checkout":
            self._refresh_checkout_summary()

        self.after(1000, self._tick_online_wait_indicators)

    def _clone_transaction_for_checkout(self, source_transaction):
        clone = Transaction(None, source_transaction.cashier_name or self.user.get("username", "cashier"))
        clone.date = source_transaction.date
        clone.payment_method = source_transaction.payment_method
        clone.amount_paid = self._to_money_decimal(source_transaction.amount_paid or source_transaction.get_total())
        clone.recorded_total = source_transaction.recorded_total
        clone.service_mode = source_transaction.service_mode
        clone.order_source = source_transaction.order_source
        clone.customer_number = source_transaction.customer_number
        clone.pickup_date_from = getattr(source_transaction, "pickup_date_from", None)
        clone.pickup_date_to = getattr(source_transaction, "pickup_date_to", None)
        clone.online_order_status = getattr(source_transaction, "online_order_status", None)
        clone.accepted_at = getattr(source_transaction, "accepted_at", None)
        clone.processed_at = getattr(source_transaction, "processed_at", None)
        clone.items = [
            {
                "product": item["product"],
                "quantity": item["quantity"],
                "subtotal": Decimal(str(item["subtotal"])),
                "reservations": [],
            }
            for item in source_transaction.items
        ]
        return clone

    def _proceed_online_order_to_checkout(self):
        if self.selected_online_order is None:
            self._set_feedback("Choose an online order first.")
            return
        if not self._is_accepted_online_order(self.selected_online_order):
            self._set_feedback("Accept the pending online order first so the waiting timer can start.")
            return

        replace_existing = (
            bool(self.transaction.items)
            and not self.transaction_saved
            and (
                self.online_checkout_source is None
                or self.online_checkout_source.transaction_id != self.selected_online_order.transaction_id
            )
        )
        if replace_existing and not messagebox.askyesno(
            "Replace Checkout",
            "Proceeding with this online order will replace the current checkout. Continue?",
            parent=self,
        ):
            self._set_feedback("Stayed on the current checkout.")
            return

        if replace_existing:
            self._restore_pending_inventory()

        self.online_checkout_source = self.selected_online_order
        self.transaction = self._clone_transaction_for_checkout(self.selected_online_order)
        self.transaction_saved = False
        self.ticket_printed = False
        self.order_source_var.set("Online Orders")
        self.payment_var.set(self.transaction.payment_method or "Cash")
        self.amount_var.set(self._amount_text(self.transaction.amount_paid or self.transaction.get_total()))

        self.checkout_pickup_start = getattr(self.selected_online_order, "pickup_date_from", None)
        self.checkout_pickup_end = getattr(self.selected_online_order, "pickup_date_to", None)

        self._set_feedback("")
        self._refresh_order_source_ui(reload_list=False)
        self._show_stage("checkout")
        self._set_feedback(
            f"Online order #{self.selected_online_order.transaction_id} loaded into checkout."
        )

    def _accept_selected_online_order(self):
        if self.selected_online_order is None:
            self._set_feedback("Choose a pending online order first.")
            return
        if self._is_accepted_online_order(self.selected_online_order):
            self._set_feedback("This online order is already accepted.")
            return

        order_id = self.selected_online_order.transaction_id
        order_label = self.selected_online_order.customer_number or f"Order #{order_id}"

        try:
            accepted_at = TransactionDB.accept_online_order(order_id)
        except Exception as exc:
            self._set_feedback(f"Failed to accept online order: {exc}")
            return

        self.selected_online_order = None
        self.selected_online_order_id = None
        self._refresh_order_source_ui(force_reload=True)
        self._set_feedback(
            f"Accepted {order_label}. It is now ready in the Accepted queue for checkout, and the POS will stay on Pending."
        )

    def _update_browse_panel_mode(self):
        if self._is_online_mode():
            queue_name = self._current_online_queue_name()
            self.browse_panel_title_label.configure(text=f"{queue_name} Online Order")
            self.browse_total_caption_label.configure(text="ORDER TOTAL")
            if queue_name == "Pending":
                self.proceed_button.configure(text="Accept Order", command=self._accept_selected_online_order)
            else:
                self.proceed_button.configure(text="Process Checkout", command=self._proceed_to_checkout)
        else:
            self.browse_panel_title_label.configure(text="Walk-In Cart")
            self.browse_total_caption_label.configure(text="ORDER TOTAL")
            self.proceed_button.configure(text="Go to Checkout", command=self._proceed_to_checkout)

    def _transaction_pickup_text(self, transaction):
        pickup_start = getattr(transaction, "pickup_date_from", None)
        pickup_end = getattr(transaction, "pickup_date_to", None) or pickup_start
        if pickup_start and pickup_end and pickup_start != pickup_end:
            return f"Pickup Window: {pickup_start.isoformat()} to {pickup_end.isoformat()}"
        if pickup_start:
            return f"Pickup Date: {pickup_start.isoformat()}"
        if getattr(transaction, "order_source", "") == "Online Orders":
            return f"Pickup Date: {str(transaction.date)[:10]}"
        return ""

    def _to_money_decimal(self, value):
        if value is None or value == "":
            return Decimal("0.00")
        try:
            if isinstance(value, Decimal):
                return value
            text = str(value).strip().upper().replace(",", "").replace("PHP", "").replace("₱", "")
            return Decimal(text or "0")
        except Exception:
            return Decimal("0.00")

    def _money_text(self, value):
        return f"PHP {self._to_money_decimal(value):,.2f}"

    def _amount_text(self, value):
        return f"{self._to_money_decimal(value):.2f}"

    def _transaction_receipt_lines(self, transaction):
        status = "VOIDED" if transaction.is_voided else "COMPLETED"
        lines = [
            "BAKEWISE RECEIPT",
            "",
            f"Receipt No.: {transaction.customer_number or '-'}",
            f"Transaction ID: {transaction.transaction_id}",
            f"Date: {transaction.date}",
            f"Cashier: {transaction.cashier_name}",
            f"Service Mode: {transaction.service_mode}",
            f"Order Source: {transaction.order_source}",
        ]
        pickup_text = self._transaction_pickup_text(transaction)
        if pickup_text:
            lines.append(pickup_text)
        lines.extend(
            [
                f"Status: {status}",
                "",
                "Items",
            ]
        )
        for item in transaction.items:
            lines.append(
                f"{item['product'].name} x{item['quantity']} - {self._money_text(item.get('subtotal'))}"
            )
            lines.append(
                f"  {item['product'].category} | {self._money_text(item['product'].price)} each"
            )

        lines.extend(
            [
                "",
                f"TOTAL: {self._money_text(transaction.get_total())}",
                f"Payment: {transaction.payment_method}",
                f"Amount Paid: {self._money_text(transaction.amount_paid)}",
                f"Change: {self._money_text(transaction.get_change())}",
            ]
        )
        return lines

    def _bootstrap_pos_view(self):
        if not self.winfo_exists():
            return
        if self.locked_workspace is not None:
            self.order_source_var.set(self.locked_workspace)
        if self._supports_online_queue():
            self._load_online_orders_accepting_state()
        self.after(10, lambda: self.winfo_exists() and self._refresh_order_source_ui(force_reload=True))

    def _reset_entry_stage(self):
        current_stage = getattr(self, "current_stage", "browse")
        if current_stage == "finished" and self.transaction_saved:
            self._new_transaction(restore_inventory=False)
            return

        if current_stage != "browse":
            self._show_stage("browse")

        self._set_feedback("")

    def set_screen_active(self, active):
        self.screen_active = bool(active)
        if not self.screen_active:
            self._hide_recent_searches()
            if self.search_keyboard_popup is not None and self.search_keyboard_popup.winfo_exists():
                self.search_keyboard_popup.destroy()
            return

        if self.locked_workspace is not None:
            self.order_source_var.set(self.locked_workspace)
        self._reset_entry_stage()
        self._refresh_order_source_ui(force_reload=False)

    def set_workspace_mode(self, value, force_reload=False):
        normalized = self._normalize_workspace_mode(value)
        if self.locked_workspace is not None:
            normalized = self.locked_workspace
        if not force_reload and normalized == self.order_source_var.get():
            return
        if normalized == "Online Orders":
            self._reset_online_queue_render_limit()
        self.order_source_var.set(normalized)
        if self.winfo_exists():
            self._refresh_order_source_ui(force_reload=force_reload)

    def _set_order_source_mode(self, value):
        self.set_workspace_mode(value)

    def _reset_online_queue_render_limit(self):
        self.online_queue_visible_count = 0
        self.online_queue_page_index = 0
        self.online_queue_render_limit = self._online_queue_page_size()

    def _online_queue_page_size(self, filter_text=""):
        if str(filter_text or "").strip():
            return max(int(self.online_queue_search_page_size or 3), 1)
        return max(int(self.online_queue_render_step or 8), 1)

    def _load_more_online_orders(self):
        total = len(getattr(self, "online_orders_cache", []) or [])
        page_size = self._online_queue_page_size(self.search_var.get().strip())
        max_page_index = max(((total + page_size - 1) // page_size) - 1, 0)
        if self.online_queue_page_index < max_page_index:
            self.online_queue_page_index += 1
        self._load_online_orders(self.search_var.get().strip(), force_reload=False)

    def _show_previous_online_orders_page(self):
        if self.online_queue_page_index > 0:
            self.online_queue_page_index -= 1
        self._load_online_orders(self.search_var.get().strip(), force_reload=False)

    def _update_online_queue_footer(self):
        if not hasattr(self, "online_queue_footer"):
            return

        is_online = self._is_online_mode()
        total = len(getattr(self, "online_orders_cache", []) or [])
        page_size = self._online_queue_page_size(self.search_var.get().strip())
        page_count = max((total + page_size - 1) // page_size, 1)
        self.online_queue_page_index = min(max(int(self.online_queue_page_index or 0), 0), page_count - 1)
        start_index = self.online_queue_page_index * page_size
        visible = min(int(self.online_queue_visible_count or 0), total)
        end_index = min(start_index + visible, total)
        if not is_online or total == 0:
            if self.online_queue_footer.winfo_manager():
                self.online_queue_footer.pack_forget()
            return

        if not self.online_queue_footer.winfo_manager():
            self.online_queue_footer.pack(fill="x", padx=20, pady=(0, 12))

        queue_name = self._current_online_queue_name().lower()
        self.online_queue_footer_label.configure(
            text=(
                f"Showing {start_index + 1}-{end_index} of {total} {queue_name} "
                f"order{'s' if total != 1 else ''}. Page {self.online_queue_page_index + 1} of {page_count}."
            )
        )

        has_previous = self.online_queue_page_index > 0
        has_more = self.online_queue_page_index < (page_count - 1)
        search_active = bool(self.search_var.get().strip())
        next_label = "Next 3" if search_active else "Next"
        prev_label = "Previous 3" if search_active else "Previous"
        self.online_queue_prev_button.configure(
            state="normal" if has_previous else "disabled",
            text=prev_label,
            fg_color=self.c["card"] if has_previous else self.c["input"],
            hover_color=self.c["border"] if has_previous else self.c["input"],
            text_color=self.c["text"] if has_previous else self.c["text_muted"],
        )
        self.online_queue_more_button.configure(
            state="normal" if has_more else "disabled",
            text=next_label if has_more else "Last Page",
            fg_color=self.c["card"] if has_more else self.c["input"],
            hover_color=self.c["border"] if has_more else self.c["input"],
            text_color=self.c["text"] if has_more else self.c["text_muted"],
        )

    def _schedule_filter_products(self):
        if self.search_var.get().strip() and self.recent_dropdown_visible:
            self._hide_recent_searches()
        if self._is_online_mode():
            self._reset_online_queue_render_limit()
        if self.search_after_id is not None:
            try:
                self.after_cancel(self.search_after_id)
            except Exception:
                pass
            self.search_after_id = None
        self.search_after_id = self.after(180, self._run_scheduled_filter_products)

    def _run_scheduled_filter_products(self):
        self.search_after_id = None
        self._filter_products()

    def _refresh_order_source_ui(self, reload_list=True, force_reload=False):
        selected = self.order_source_var.get()
        is_online = selected == "Online Orders"
        self._apply_browse_layout_mode()
        self.products_panel_title_label.configure(text="Online Orders Queue" if is_online else "Walk-In Products")
        if hasattr(self, "workspace_badge_label"):
            self.workspace_badge_label.configure(
                text="ONLINE ORDERS" if is_online else "WALK-IN POS",
                fg_color="#1C3550" if is_online else "#2E240E",
                text_color="#D7ECFF" if is_online else "#FFD889",
            )
        if hasattr(self, "refresh_products_button"):
            self.refresh_products_button.configure(text="Refresh Queue" if is_online else "Refresh")
        if hasattr(self, "order_source_summary_label"):
            summary_text = "Online Order Processing" if is_online else "Walk-In Cashier Checkout"
            self.order_source_summary_label.configure(text=summary_text)

        if self.products_info_label is not None:
            if is_online:
                self.products_info_label.configure(
                    text="Review website orders, accept pending requests, and process accepted orders without leaving the online queue. Newest orders load first for smoother traffic handling."
                )
            else:
                self.products_info_label.configure(
                    text="Fast in-store selling view with live product stock, quick cart updates, and cashier-ready checkout."
                )
        if hasattr(self, "browse_panel_hint_label"):
            if is_online:
                queue_name = self._current_online_queue_name()
                hint = (
                    "Review the selected pending order before accepting it."
                    if queue_name == "Pending"
                    else "Accepted orders are ready to be checked out and released to the customer."
                )
            else:
                hint = "Add bakery items here for the current in-store customer, then move straight to checkout."
            self.browse_panel_hint_label.configure(text=hint)

        if hasattr(self, "service_mode_note_label"):
            if is_online:
                self.service_mode_note_label.configure(
                    text="Dine in and take out are for walk-in customers only. Online orders use the online queue.",
                )
            else:
                self.service_mode_note_label.configure(
                    text="Choose dine in or take out for walk-in customers.",
                )
        if hasattr(self, "service_mode_section"):
            if is_online:
                if self.service_mode_section.winfo_manager():
                    self.service_mode_section.pack_forget()
            elif not self.service_mode_section.winfo_manager():
                self.service_mode_section.pack(fill="x", before=self.customer_number_hint_label)

        if hasattr(self, "search_entry"):
            self.search_entry.configure(
                placeholder_text="Search online orders, customer no., or date"
                if is_online
                else "Search products for walk-in checkout"
            )
        if hasattr(self, "back_to_products_button"):
            self.back_to_products_button.configure(text="Back to Orders" if is_online else "Back to Products")

        self._update_online_accepting_ui()
        self._update_online_order_button_label()
        self._update_online_queue_ui()
        self._update_online_queue_footer()
        self._update_browse_panel_mode()
        for label, button in getattr(self, "order_source_buttons", {}).items():
            is_active = label == selected
            button.configure(
                fg_color=AMBER if is_active else self.c["input"],
                hover_color=AMBER_DARK if is_active else self.c["border"],
                text_color="#0F0F0F" if is_active else self.c["text"],
            )

        self._set_checkout_inputs_enabled(not self.transaction_saved)
        self._update_customer_number_hint()
        self._refresh_checkout_summary()
        skip_final_cart_refresh = False
        if reload_list:
            self._load_products(self.search_var.get().strip(), force_reload=force_reload)
            skip_final_cart_refresh = is_online
        if not skip_final_cart_refresh:
            self._refresh_cart()

    def _update_customer_number_hint(self):
        if self.online_checkout_source is not None and not self.transaction_saved:
            self.customer_number_hint_var.set(
                f"Receipt No.: {self.transaction.customer_number or self.online_checkout_source.customer_number or 'ON-...'}"
            )
            return
        service_mode, order_source = self._selected_transaction_metadata()
        hint_key = (service_mode, order_source)
        if self._customer_number_hint_key == hint_key and "..." not in self.customer_number_hint_var.get():
            return

        if order_source == "Online Orders":
            prefix = "ON"
        else:
            prefix = "DI" if service_mode == "Dine In" else "TO"
        self.customer_number_hint_var.set(f"Receipt No.: {prefix}-...")

        token = object()
        self._customer_number_hint_token = token
        run_in_thread(
            self,
            lambda: TransactionDB.peek_next_customer_number(
                service_mode,
                order_source=order_source,
            ),
            on_success=lambda next_number: self._apply_customer_number_hint(token, hint_key, next_number),
            on_error=lambda _exc: self._apply_customer_number_hint(token, hint_key, None),
            is_current=lambda: self._customer_number_hint_token is token,
        )

    def _apply_customer_number_hint(self, token, hint_key, next_number):
        if self._customer_number_hint_token is not token:
            return

        self._customer_number_hint_key = hint_key
        if next_number:
            self.customer_number_hint_var.set(f"Receipt No.: {next_number}")

    def _selected_transaction_metadata(self):
        order_source = self.order_source_var.get() or "Walk-In"
        if order_source == "Online Orders":
            return "Online Orders", order_source
        return self.service_mode_var.get() or "Take Out", order_source

    def _sync_transaction_metadata(self):
        service_mode, order_source = self._selected_transaction_metadata()
        self.transaction.service_mode = service_mode
        self.transaction.order_source = order_source
        if order_source == "Online Orders" and self._is_preorder_transaction(self.transaction):
            self.transaction.pickup_date_from = self.checkout_pickup_start
            self.transaction.pickup_date_to = self.checkout_pickup_end or self.checkout_pickup_start
        else:
            self.transaction.pickup_date_from = None
            self.transaction.pickup_date_to = None

    def _start_new_transaction(self):
        restore_inventory = not self.transaction_saved and not self.transaction.is_voided
        self._new_transaction(restore_inventory=restore_inventory)
        self.current_stage = "browse"
        self.checkout_view.grid_remove()
        self.finished_view.grid_remove()
        self._render_browse_cart()
        self.browse_view.grid(row=0, column=0, sticky="nsew")
        self._hide_recent_searches()
        if self.search_keyboard_popup is not None and self.search_keyboard_popup.winfo_exists():
            self.search_keyboard_popup.destroy()
        self.after(60, lambda: self.search_entry.focus_set())

    def _set_checkout_inputs_enabled(self, enabled):
        state = "normal" if enabled else "disabled"
        self.amount_entry.configure(state=state)
        for control in self.payment_method_controls:
            control.configure(state=state)
        service_state = state if self.order_source_var.get() == "Walk-In" else "disabled"
        for control in getattr(self, "service_mode_controls", []):
            control.configure(state=service_state)
        for button in getattr(self, "order_source_buttons", {}).values():
            button.configure(state=state)
        for button in getattr(self, "numpad_buttons", []):
            button.configure(state=state)
        self.back_to_products_button.configure(state=state)
        self.finish_transaction_button.configure(state=state)

    def _update_receipt_actions(self):
        has_items = bool(self.transaction.items)
        can_export = self.transaction_saved and self.transaction.transaction_id is not None
        can_void = self.transaction_saved and self.transaction.transaction_id is not None and not self.transaction.is_voided

        if self.transaction_saved and self.transaction.is_voided:
            status_text = (
                f"{self.transaction.customer_number or 'Customer'} was voided under "
                f"transaction #{self.transaction.transaction_id}. "
                "Preview stays available, and you can still export the receipt record."
            )
        elif self.transaction_saved:
            if self.ticket_printed:
                status_text = (
                    f"{self.transaction.customer_number or 'Customer'} was already printed. "
                    "If this was finished by mistake, you can still void it here."
                )
            else:
                status_text = (
                    f"{self.transaction.customer_number or 'Customer'} is ready. "
                    "Preview it here, print it, export it, or void it if needed."
                )
        elif self.online_checkout_source is not None:
            status_text = (
                "Review the selected online order details, confirm the payment, "
                "then finish it to open the printable order panel."
            )
        elif has_items:
            status_text = (
                "Review the cart, confirm the payment, then use Finish Transaction to save this sale."
            )
        else:
            status_text = "Add items, then finish the transaction to unlock receipt export."

        self.receipt_status_label.configure(text=status_text)
        self.print_ticket_button.configure(state="normal" if can_export else "disabled")
        self.export_csv_button.configure(state="normal" if can_export else "disabled")
        self.export_pdf_button.configure(state="normal" if can_export else "disabled")
        self.void_transaction_button.configure(state="normal" if can_void else "disabled")
        next_state = "normal" if has_items or can_export else "disabled"
        self.receipt_new_transaction_button.configure(state=next_state)
        self.start_new_transaction_button.configure(state=next_state)
        self.start_new_transaction_button.configure(
            text="Start New Transaction" if self.transaction_saved else "Void and New Transaction"
        )
        self._set_checkout_inputs_enabled(not self.transaction_saved)
        self._sync_finish_transaction_button_state()
        if not self.transaction_saved:
            self.back_to_products_button.configure(state="normal")

    def _void_transaction_action(self):
        if not self.transaction.items:
            self._set_feedback("No transaction to void.")
            return

        if self.transaction_saved:
            if self.transaction.is_voided:
                self._set_feedback("This transaction is already voided.")
                return

            prompt = (
                f"Void transaction #{self.transaction.transaction_id} for "
                f"{self.transaction.customer_number or 'this customer'}?"
            )
            if self.ticket_printed:
                prompt += "\n\nThe ticket was already printed, but this transaction can still be voided."
            if not messagebox.askyesno("Void Transaction", prompt, parent=self):
                self._set_feedback("Void transaction cancelled.")
                return

            try:
                for item in self.transaction.items:
                    for reservation_group in item.get("reservations", []):
                        self._restore_reservation_group(reservation_group)
                    item["reservations"] = []
                TransactionDB.void_transaction(self.transaction.transaction_id)
                self.transaction.void()
                self._load_products(self.search_var.get().strip(), force_reload=True)
                self._refresh_cart()
                self._set_feedback(
                    f"Transaction #{self.transaction.transaction_id} voided. "
                    "Export the receipt record or start a new transaction."
                )
            except Exception as exc:
                self._set_feedback(f"Failed to void transaction: {exc}")
            return

        if not messagebox.askyesno(
            "Void Pending Transaction",
            "Void this pending transaction and return its reserved stock to inventory?",
            parent=self,
        ):
            self._set_feedback("Pending transaction kept active.")
            return

        self._new_transaction(restore_inventory=True)
        self._set_feedback("Pending transaction voided.")

    def _receipt_file_basename(self):
        tx_id = self.transaction.transaction_id if self.transaction.transaction_id is not None else "draft"
        stamp = str(self.transaction.date).replace(":", "-").replace(" ", "_")
        customer_number = (self.transaction.customer_number or "queue").replace("/", "-")
        return f"bakewise_receipt_{tx_id}_{customer_number}_{stamp}"

    def _receipt_lines(self):
        return self._transaction_receipt_lines(self.transaction)

    def _receipt_csv_rows(self):
        transaction = self.transaction
        rows = [
            ["BakeWise Receipt"],
            ["Receipt Number", transaction.customer_number or "-"],
            ["Transaction ID", transaction.transaction_id],
            ["Date", transaction.date],
            ["Cashier", transaction.cashier_name],
            ["Service Mode", transaction.service_mode],
            ["Order Source", transaction.order_source],
            ["Pickup Window", self._transaction_pickup_text(transaction)],
            ["Status", "VOIDED" if transaction.is_voided else "COMPLETED"],
            [],
            ["Item", "Quantity", "Unit Price", "Subtotal", "Category"],
        ]
        for item in transaction.items:
            rows.append(
                [
                    item["product"].name,
                    item["quantity"],
                    self._amount_text(item["product"].price),
                    self._amount_text(item.get("subtotal")),
                    item["product"].category,
                ]
            )
        rows.extend(
            [
                [],
                ["Total", self._amount_text(transaction.get_total())],
                ["Payment Method", transaction.payment_method],
                ["Amount Paid", self._amount_text(transaction.amount_paid)],
                ["Change", self._amount_text(transaction.get_change())],
            ]
        )
        return rows

    def _wrap_pdf_text(self, text, width=72):
        if len(text) <= width:
            return [text]

        words = text.split()
        if not words:
            return [text[:width]]

        lines = []
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if len(candidate) <= width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
        return lines

    def _escape_pdf_text(self, text):
        safe = str(text).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        return safe.encode("latin-1", "replace").decode("latin-1")

    def _write_receipt_pdf(self, path):
        lines = []
        for line in self._receipt_lines():
            lines.extend(self._wrap_pdf_text(line, width=76))

        line_height = 14
        content_lines = ["BT", "/F1 12 Tf", f"{line_height} TL", "40 770 Td"]
        for index, line in enumerate(lines):
            escaped = self._escape_pdf_text(line)
            if index == 0:
                content_lines.append(f"({escaped}) Tj")
            else:
                content_lines.append("T*")
                content_lines.append(f"({escaped}) Tj")
        content_lines.append("ET")
        stream = "\n".join(content_lines).encode("latin-1", "replace")

        objects = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            f"<< /Length {len(stream)} >>\nstream\n".encode("latin-1") + stream + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        ]

        with open(path, "wb") as handle:
            handle.write(b"%PDF-1.4\n")
            offsets = [0]
            for index, obj in enumerate(objects, start=1):
                offsets.append(handle.tell())
                handle.write(f"{index} 0 obj\n".encode("latin-1"))
                handle.write(obj)
                handle.write(b"\nendobj\n")
            xref_position = handle.tell()
            handle.write(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
            handle.write(b"0000000000 65535 f \n")
            for offset in offsets[1:]:
                handle.write(f"{offset:010d} 00000 n \n".encode("latin-1"))
            handle.write(
                (
                    f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
                    f"startxref\n{xref_position}\n%%EOF"
                ).encode("latin-1")
            )

    def _export_receipt_csv(self):
        if not self.transaction_saved or self.transaction.transaction_id is None:
            self._set_feedback("Complete checkout first to export the receipt.")
            return

        path = filedialog.asksaveasfilename(
            parent=self,
            title="Save Receipt as CSV",
            defaultextension=".csv",
            initialfile=f"{self._receipt_file_basename()}.csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return

        try:
            with open(path, "w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerows(self._receipt_csv_rows())
            self._set_feedback(f"Receipt saved as CSV: {path}")
        except Exception as exc:
            self._set_feedback(f"Failed to save CSV receipt: {exc}")

    def _export_receipt_pdf(self):
        if not self.transaction_saved or self.transaction.transaction_id is None:
            self._set_feedback("Complete checkout first to export the receipt.")
            return

        path = filedialog.asksaveasfilename(
            parent=self,
            title="Save Receipt as PDF",
            defaultextension=".pdf",
            initialfile=f"{self._receipt_file_basename()}.pdf",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
        )
        if not path:
            return

        try:
            self._write_receipt_pdf(path)
            self._set_feedback(f"Receipt saved as PDF: {path}")
        except Exception as exc:
            self._set_feedback(f"Failed to save PDF receipt: {exc}")

    def _print_transaction_ticket(self):
        if not self.transaction_saved or self.transaction.transaction_id is None:
            self._set_feedback("Finish the transaction first before printing.")
            return

        ticket_path = os.path.join(tempfile.gettempdir(), f"{self._receipt_file_basename()}.txt")
        try:
            with open(ticket_path, "w", encoding="utf-8") as handle:
                handle.write("\n".join(self._receipt_lines()))

            if hasattr(os, "startfile"):
                os.startfile(ticket_path, "print")
                self.ticket_printed = True
                self._update_receipt_actions()
                self._set_feedback(
                    "Print command sent to the default printer. "
                    "Make sure Windows has a printer configured. "
                    "If this transaction was finished by mistake, you can still void it."
                )
            else:
                self._set_feedback(f"Printer shortcut is not available here. Ticket saved to {ticket_path}")
        except Exception as exc:
            self._set_feedback(
                f"Printing failed: {exc}. "
                f"Check your printer/driver setup, or export the receipt instead."
            )

    def _build_numpad(self, parent):
        c = self.c
        self.numpad_buttons = []
        for column in range(4):
            parent.grid_columnconfigure(column, weight=1, uniform="numpad")
        for row in range(4):
            parent.grid_rowconfigure(row, weight=1, uniform="numpad")

        buttons = [
            ("7", lambda: self._append_amount_value("7")),
            ("8", lambda: self._append_amount_value("8")),
            ("9", lambda: self._append_amount_value("9")),
            ("Back", self._backspace_amount),
            ("4", lambda: self._append_amount_value("4")),
            ("5", lambda: self._append_amount_value("5")),
            ("6", lambda: self._append_amount_value("6")),
            ("Clear", self._clear_amount),
            ("1", lambda: self._append_amount_value("1")),
            ("2", lambda: self._append_amount_value("2")),
            ("3", lambda: self._append_amount_value("3")),
            ("Exact", self._apply_exact_amount),
            ("0", lambda: self._append_amount_value("0")),
            ("00", lambda: self._append_amount_value("00")),
            (".", lambda: self._append_amount_value(".")),
            ("+100", lambda: self._increase_amount_by(Decimal("100"))),
        ]

        for index, (label, command) in enumerate(buttons):
            row = index // 4
            column = index % 4
            is_primary = label in {"Exact", "+100"}
            is_numeric = label.isdigit() or label in {"00", "."}
            button = ctk.CTkButton(
                parent,
                text=label,
                height=108,
                fg_color=AMBER if is_primary else c["input"],
                hover_color=AMBER_DARK if is_primary else c["border"],
                text_color="#0F0F0F" if is_primary else c["text"],
                corner_radius=16,
                font=ctk.CTkFont(
                    "Segoe UI",
                    32 if is_numeric else 18,
                    "bold" if is_numeric or is_primary else "normal",
                ),
                command=command,
            )
            button.grid(row=row, column=column, sticky="nsew", padx=8, pady=9)
            self.numpad_buttons.append(button)

    def _toggle_recent_searches(self):
        if self.recent_dropdown_visible:
            self._hide_recent_searches()
        else:
            self._show_recent_searches()

    def _show_recent_searches(self):
        if not self.recent_searches:
            return

        self._hide_recent_searches(clear_only=True)
        self.recent_dropdown_visible = True
        self.recent_dropdown_host.pack(fill="x", padx=20, pady=(0, 12))

        card = ctk.CTkFrame(
            self.recent_dropdown_host,
            fg_color=self.c["input"],
            corner_radius=12,
            border_width=1,
            border_color=self.c["border"],
        )
        card.pack(fill="x")
        ctk.CTkLabel(
            card,
            text="Recent Searches",
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            text_color=self.c["text_muted"],
        ).pack(anchor="w", padx=14, pady=(12, 6))

        for term in self.recent_searches:
            ctk.CTkButton(
                card,
                text=term,
                height=34,
                fg_color=self.c["card"],
                hover_color=self.c["border"],
                text_color=self.c["text"],
                corner_radius=10,
                font=ctk.CTkFont("Segoe UI", 11),
                anchor="w",
                command=lambda selected=term: self._apply_recent_search(selected),
            ).pack(fill="x", padx=12, pady=3)

    def _hide_recent_searches(self, clear_only=False):
        for widget in self.recent_dropdown_host.winfo_children():
            widget.destroy()
        if not clear_only and self.recent_dropdown_host.winfo_manager():
            self.recent_dropdown_host.pack_forget()
        self.recent_dropdown_visible = False

    def _apply_recent_search(self, term):
        self.search_var.set(term)
        self._commit_search()
        self._hide_recent_searches()

    def _remember_search(self, term):
        cleaned = term.strip()
        if not cleaned:
            return
        filtered = [item for item in self.recent_searches if item.lower() != cleaned.lower()]
        self.recent_searches = [cleaned] + filtered[:5]

    def _show_search_keyboard(self):
        if self.search_keyboard_popup is not None and self.search_keyboard_popup.winfo_exists():
            self.search_keyboard_popup.lift()
            return

        self.search_keyboard_popup = SearchKeyboardPopup(
            self.winfo_toplevel(),
            self.c,
            self.search_shell,
            on_key=self._append_search_text,
            on_backspace=self._backspace_search_text,
            on_clear=self._clear_search_text,
            on_space=lambda: self._append_search_text(" "),
            on_search=self._commit_search,
        )
        self.search_keyboard_popup.bind(
            "<Destroy>",
            lambda _event: setattr(self, "search_keyboard_popup", None),
            add="+",
        )

    def _append_search_text(self, value):
        current = self.search_var.get()
        self.search_var.set(f"{current}{value}")
        self.search_entry.focus_set()

    def _backspace_search_text(self):
        current = self.search_var.get()
        self.search_var.set(current[:-1] if current else "")
        self.search_entry.focus_set()

    def _clear_search_text(self):
        self.search_var.set("")
        self.search_entry.focus_set()

    def _commit_search(self):
        term = self.search_var.get().strip()
        if self.search_after_id is not None:
            try:
                self.after_cancel(self.search_after_id)
            except Exception:
                pass
            self.search_after_id = None
        self._filter_products()
        if term:
            self._remember_search(term)
        self._hide_recent_searches()
        self.search_entry.focus_set()

    def _refresh_products_from_db(self):
        if self._is_online_mode():
            self._reset_online_queue_render_limit()
        self._load_products(self.search_var.get().strip(), force_reload=True)

    def _start_walkin_products_load(self):
        if self._walkin_products_loading:
            return

        token = object()
        self._product_load_token = token
        self._walkin_products_loading = True
        self._show_products_loading_message("Loading products...")

        run_in_thread(
            self,
            self._fetch_walkin_product_data,
            on_success=lambda data: self._apply_walkin_product_data(token, data),
            on_error=lambda exc: self._handle_walkin_product_load_error(token, exc),
            is_current=lambda: self._product_load_token is token and not self._is_online_mode(),
        )

    def _apply_walkin_product_data(self, token, data):
        if self._product_load_token is not token:
            return

        self._walkin_products_loading = False
        self.products_cache = list(data.get("products") or [])
        self.product_stock_cache = dict(data.get("stock_map") or {})
        self.products_loaded = True
        self._render_walkin_products(self.search_var.get().strip())

    def _handle_walkin_product_load_error(self, token, exc):
        if self._product_load_token is not token:
            return

        self._walkin_products_loading = False
        self._set_feedback(f"Failed to load products: {exc}")
        if not self.products_loaded:
            self.products_cache = []
            self.product_stock_cache = {}
        self._render_walkin_products(self.search_var.get().strip(), load_error=exc)

    def _render_walkin_products(self, filter_text="", load_error=None):
        c = self.c
        self.walkin_product_card_views = {}
        for widget in self.products_grid.winfo_children():
            widget.destroy()

        filtered = self.products_cache
        if filter_text:
            lookup = filter_text.lower()
            filtered = [product for product in self.products_cache if lookup in product.name.lower()]

        if not filtered:
            ctk.CTkLabel(
                self.products_grid,
                text=(
                    "Products are unavailable right now.\nCheck the BakeWise database connection."
                    if load_error is not None
                    else "No products matched your search."
                ),
                font=ctk.CTkFont("Segoe UI", 12),
                text_color=c["text_muted"],
                justify="left",
            ).pack(pady=24)
            return

        for index, product in enumerate(filtered):
            stock_quantity = self._display_stock_quantity(product.product_id)
            stock_color = SUCCESS if stock_quantity > 8 else AMBER if stock_quantity > 0 else ERROR_RED
            card = ctk.CTkFrame(
                self.products_grid,
                fg_color=c["input"],
                corner_radius=12,
                border_width=1,
                border_color=c["border"],
            )
            card.grid(row=index // 2, column=index % 2, sticky="nsew", padx=8, pady=8)

            title_row = ctk.CTkFrame(card, fg_color="transparent")
            title_row.pack(fill="x", padx=14, pady=(12, 2))

            ctk.CTkLabel(
                title_row,
                text=product.name,
                font=ctk.CTkFont("Segoe UI", 12, "bold"),
                text_color=c["text"],
            ).pack(side="left")
            ctk.CTkLabel(
                title_row,
                text=f"#{product.product_id}",
                font=ctk.CTkFont("Segoe UI", 10, "bold"),
                text_color=c["text_muted"],
            ).pack(side="right")

            ctk.CTkLabel(
                card,
                text=self._money_text(product.price),
                font=ctk.CTkFont("Georgia", 14, "bold"),
                text_color=AMBER,
            ).pack(anchor="w", padx=14)
            ctk.CTkLabel(
                card,
                text=product.category,
                font=ctk.CTkFont("Segoe UI", 10),
                text_color=c["text_muted"],
            ).pack(anchor="w", padx=14, pady=(0, 6))
            stock_label = ctk.CTkLabel(
                card,
                text=f"Available stock: {stock_quantity}",
                font=ctk.CTkFont("Segoe UI", 10, "bold"),
                text_color=stock_color,
            )
            stock_label.pack(anchor="w", padx=14, pady=(0, 8))
            add_button = ctk.CTkButton(
                card,
                text="Add to Cart" if stock_quantity > 0 else "Out of Stock",
                height=34,
                fg_color=self._success_button_colors()[0] if stock_quantity > 0 else c["card"],
                hover_color=self._success_button_colors()[1] if stock_quantity > 0 else c["card"],
                text_color=("#166534" if ctk.get_appearance_mode() != "Dark" else SUCCESS) if stock_quantity > 0 else c["text_muted"],
                corner_radius=8,
                font=ctk.CTkFont("Segoe UI", 11, "bold"),
                command=lambda selected=product: self._add_to_cart(selected),
                state="normal" if stock_quantity > 0 else "disabled",
            )
            add_button.pack(fill="x", padx=14, pady=(2, 12))
            self.walkin_product_card_views[product.product_id] = {
                "product": product,
                "stock_label": stock_label,
                "add_button": add_button,
            }

    def _load_products(self, filter_text="", force_reload=False):
        if self._is_online_mode():
            self._load_online_orders(filter_text, force_reload=force_reload)
            return

        if force_reload:
            self.products_loaded = False

        if not self.products_loaded:
            self._start_walkin_products_load()
            return

        if self._walkin_products_loading and not self.products_cache:
            self._show_products_loading_message("Loading products...")
            return

        self._render_walkin_products(filter_text)

    def _refresh_walkin_product_cards(self):
        if self._is_online_mode():
            return

        product_ids = list(getattr(self, "walkin_product_card_views", {}).keys())
        if not product_ids or not self.product_stock_cache:
            return

        success_fg, success_hover = self._success_button_colors()
        success_text = "#166534" if ctk.get_appearance_mode() != "Dark" else SUCCESS
        for product_id, view in list(self.walkin_product_card_views.items()):
            stock_label = view.get("stock_label")
            add_button = view.get("add_button")
            if (
                stock_label is None
                or add_button is None
                or not stock_label.winfo_exists()
                or not add_button.winfo_exists()
            ):
                self.walkin_product_card_views.pop(product_id, None)
                continue

            stock_quantity = self._display_stock_quantity(product_id)
            stock_color = SUCCESS if stock_quantity > 8 else AMBER if stock_quantity > 0 else ERROR_RED
            stock_label.configure(
                text=f"Available stock: {stock_quantity}",
                text_color=stock_color,
            )
            add_button.configure(
                text="Add to Cart" if stock_quantity > 0 else "Out of Stock",
                state="normal" if stock_quantity > 0 else "disabled",
                fg_color=success_fg if stock_quantity > 0 else self.c["card"],
                hover_color=success_hover if stock_quantity > 0 else self.c["card"],
                text_color=success_text if stock_quantity > 0 else self.c["text_muted"],
            )

    def _finish_walkin_product_action(self):
        term = self.search_var.get().strip()
        if self.search_after_id is not None:
            try:
                self.after_cancel(self.search_after_id)
            except Exception:
                pass
            self.search_after_id = None

        if term:
            self._remember_search(term)
        if self.recent_dropdown_visible:
            self._hide_recent_searches()

        self._refresh_cart()
        self._refresh_walkin_product_cards()
        if hasattr(self, "search_entry") and self.search_entry.winfo_exists():
            self.search_entry.focus_set()

    def _update_online_order_snapshots(self, pending_orders, accepted_orders):
        self.online_orders_loaded_once = True
        self.pending_online_orders_snapshot = list(pending_orders or [])
        self.accepted_online_orders_snapshot = list(accepted_orders or [])
        self.pending_online_order_count = len(self.pending_online_orders_snapshot)
        self.accepted_online_order_count = len(self.accepted_online_orders_snapshot)
        self.known_pending_online_order_ids = [
            transaction.transaction_id
            for transaction in self.pending_online_orders_snapshot
            if transaction.transaction_id is not None
        ]
        self.known_accepted_online_order_ids = [
            transaction.transaction_id
            for transaction in self.accepted_online_orders_snapshot
            if transaction.transaction_id is not None
        ]
        self._update_online_order_button_label()
        self._update_online_queue_ui()

    def _start_online_orders_load(self):
        if self._online_orders_loading:
            return

        token = object()
        self._online_orders_load_token = token
        self._online_orders_loading = True
        self._show_products_loading_message("Loading online orders...")

        run_in_thread(
            self,
            self._fetch_online_orders_data,
            on_success=lambda data: self._apply_online_orders_data(token, data),
            on_error=lambda exc: self._handle_online_orders_load_error(token, exc),
            is_current=lambda: self._online_orders_load_token is token and self._is_online_mode(),
        )

    def _apply_online_orders_data(self, token, data):
        if self._online_orders_load_token is not token:
            return

        self._online_orders_loading = False
        self._update_online_order_snapshots(
            data.get("pending_orders") or [],
            data.get("accepted_orders") or [],
        )
        self._render_online_orders(self.search_var.get().strip())

    def _handle_online_orders_load_error(self, token, exc):
        if self._online_orders_load_token is not token:
            return

        self._online_orders_loading = False
        self._set_feedback(f"Failed to load online orders: {exc}")
        self._render_online_orders(self.search_var.get().strip(), load_error=exc)

    def _load_online_orders(self, filter_text="", force_reload=False):
        if force_reload:
            self.online_orders_loaded_once = False

        if not self.online_orders_loaded_once:
            self._start_online_orders_load()
            return

        if self._online_orders_loading and not (self.pending_online_orders_snapshot or self.accepted_online_orders_snapshot):
            self._show_products_loading_message("Loading online orders...")
            return

        self._render_online_orders(filter_text)

    def _render_online_orders(self, filter_text="", load_error=None):
        c = self.c
        for widget in self.products_grid.winfo_children():
            widget.destroy()
        self.online_wait_labels = {}
        self.online_order_card_views = {}
        previous_selected = self.selected_online_order

        queue_name = self._current_online_queue_name()
        show_accepted = queue_name == "Accepted"
        pending_orders = list(self.pending_online_orders_snapshot)
        accepted_orders = list(self.accepted_online_orders_snapshot)
        transactions = accepted_orders if show_accepted else pending_orders

        filtered = transactions
        if filter_text:
            lookup = filter_text.lower()
            filtered = []
            for transaction in transactions:
                searchable = [
                    str(transaction.transaction_id or ""),
                    str(transaction.customer_number or ""),
                    str(transaction.cashier_name or ""),
                    str(transaction.date or ""),
                    str(getattr(transaction, "pickup_date_from", "") or ""),
                    str(getattr(transaction, "pickup_date_to", "") or ""),
                ]
                haystack = " ".join(searchable).lower()
                if lookup in haystack:
                    filtered.append(transaction)

        self.online_orders_cache = filtered
        if self.selected_online_order_id is not None:
            self.selected_online_order = next(
                (row for row in filtered if row.transaction_id == self.selected_online_order_id),
                None,
            )
        if self.selected_online_order is None and filtered:
            self.selected_online_order = filtered[0]
            self.selected_online_order_id = filtered[0].transaction_id
        elif not filtered:
            self.selected_online_order = None
            self.selected_online_order_id = None

        if (
            previous_selected is not None
            and self.selected_online_order is not None
            and previous_selected.transaction_id == self.selected_online_order.transaction_id
            and getattr(previous_selected, "items", None)
        ):
            self.selected_online_order = previous_selected
            for index, transaction in enumerate(self.online_orders_cache):
                if transaction.transaction_id == previous_selected.transaction_id:
                    self.online_orders_cache[index] = previous_selected
                    break

        if not filtered:
            self.online_queue_visible_count = 0
            self._update_online_queue_footer()
            self._load_selected_online_order_details()

            empty_text = (
                (
                    "Online orders are unavailable right now.\nCheck the BakeWise database connection."
                    if load_error is not None
                    else "No accepted online orders matched the current data."
                )
                if show_accepted
                else (
                    "Online orders are unavailable right now.\nCheck the BakeWise database connection."
                    if load_error is not None
                    else "No pending online or pre-orders matched the current data."
                )
            )
            ctk.CTkLabel(
                self.products_grid,
                text=empty_text,
                font=ctk.CTkFont("Segoe UI", 12),
                text_color=c["text_muted"],
                justify="left",
            ).pack(pady=24)
            self._refresh_cart()
            return

        page_size = self._online_queue_page_size(filter_text)
        page_count = max((len(filtered) + page_size - 1) // page_size, 1)
        self.online_queue_page_index = min(max(int(self.online_queue_page_index or 0), 0), page_count - 1)
        start_index = self.online_queue_page_index * page_size
        end_index = min(start_index + page_size, len(filtered))
        visible_transactions = filtered[start_index:end_index]
        visible_ids = {
            row.transaction_id
            for row in visible_transactions
            if row.transaction_id is not None
        }
        if visible_transactions and self.selected_online_order_id not in visible_ids:
            self.selected_online_order = visible_transactions[0]
            self.selected_online_order_id = visible_transactions[0].transaction_id
        self.online_queue_visible_count = len(visible_transactions)
        self._update_online_queue_footer()
        self._load_selected_online_order_details()

        for transaction in visible_transactions:
            is_selected = transaction.transaction_id == self.selected_online_order_id
            select_order = lambda _event=None, tx_id=transaction.transaction_id: self._select_online_order(tx_id)
            card = ctk.CTkFrame(
                self.products_grid,
                fg_color=self._selected_card_bg() if is_selected else c["input"],
                corner_radius=12,
                border_width=1,
                border_color=AMBER if is_selected else c["border"],
                height=164,
            )
            card.pack(fill="x", padx=8, pady=(0, 8))
            card.pack_propagate(False)
            card.bind("<Button-1>", select_order, add="+")

            title_row = ctk.CTkFrame(card, fg_color="transparent")
            title_row.pack(fill="x", padx=14, pady=(14, 4))
            title_row.bind("<Button-1>", select_order, add="+")
            customer_label = ctk.CTkLabel(
                title_row,
                text=transaction.customer_number or f"Order #{transaction.transaction_id}",
                font=ctk.CTkFont("Segoe UI", 16, "bold"),
                text_color=AMBER if is_selected else c["text"],
            )
            customer_label.pack(side="left")
            right_meta = ctk.CTkFrame(title_row, fg_color="transparent")
            right_meta.pack(side="right")
            right_meta.bind("<Button-1>", select_order, add="+")
            status_color = SUCCESS if self._is_accepted_online_order(transaction) else AMBER
            status_label = ctk.CTkLabel(
                right_meta,
                text=self._online_order_status_text(transaction).upper(),
                font=ctk.CTkFont("Segoe UI", 11, "bold"),
                text_color=status_color,
            )
            status_label.pack(side="left", padx=(0, 8))
            id_label = ctk.CTkLabel(
                right_meta,
                text=f"#{transaction.transaction_id}",
                font=ctk.CTkFont("Segoe UI", 12, "bold"),
                text_color=AMBER if is_selected else c["text_muted"],
            )
            id_label.pack(side="left")

            primary_date_label = ctk.CTkLabel(
                card,
                text=self._online_order_primary_date_text(transaction),
                font=ctk.CTkFont("Segoe UI", 12),
                text_color=c["text"] if is_selected else c["text_muted"],
                anchor="w",
                justify="left",
            )
            primary_date_label.pack(fill="x", padx=14, pady=(2, 0))
            wait_label = ctk.CTkLabel(
                card,
                text=self._online_order_wait_text(transaction),
                font=ctk.CTkFont("Segoe UI", 12, "bold"),
                text_color=SUCCESS if self._is_accepted_online_order(transaction) else AMBER,
                anchor="w",
                justify="left",
            )
            wait_label.pack(fill="x", padx=14, pady=(2, 0))
            self.online_wait_labels[transaction.transaction_id] = wait_label
            footer = ctk.CTkFrame(card, fg_color="transparent")
            footer.pack(fill="x", padx=14, pady=(10, 14))
            footer.bind("<Button-1>", select_order, add="+")
            total_label = ctk.CTkLabel(
                footer,
                text=self._money_text(transaction.get_total()),
                font=ctk.CTkFont("Georgia", 18, "bold"),
                text_color=AMBER,
            )
            total_label.pack(side="left")
            view_button = ctk.CTkButton(
                footer,
                text="Viewing" if is_selected else "View Order",
                width=124,
                height=38,
                fg_color=self._selected_button_colors()[0] if is_selected else c["card"],
                hover_color=self._selected_button_colors()[1] if is_selected else c["border"],
                text_color=AMBER if is_selected else c["text"],
                corner_radius=8,
                font=ctk.CTkFont("Segoe UI", 12, "bold"),
                command=lambda tx_id=transaction.transaction_id: self._select_online_order(tx_id),
            )
            view_button.pack(side="right")

            for widget in [
                customer_label,
                status_label,
                id_label,
                primary_date_label,
                wait_label,
                total_label,
            ]:
                widget.bind("<Button-1>", select_order, add="+")

            self.online_order_card_views[transaction.transaction_id] = {
                "card": card,
                "customer_label": customer_label,
                "status_label": status_label,
                "id_label": id_label,
                "primary_date_label": primary_date_label,
                "wait_label": wait_label,
                "view_button": view_button,
            }

        self._refresh_cart()

    def _load_selected_online_order_details(self):
        if self.selected_online_order_id is None:
            self._online_order_detail_loading = False
            return

        selected = self.selected_online_order
        if selected is not None and getattr(selected, "items", None):
            self._online_order_detail_loading = False
            return

        token = object()
        self._online_order_detail_token = token
        self._online_order_detail_loading = True

        run_in_thread(
            self,
            lambda: TransactionDB.get_transaction_by_id(
                self.selected_online_order_id,
                include_items=True,
            ),
            on_success=lambda detailed: self._apply_selected_online_order_details(token, detailed),
            on_error=lambda exc: self._handle_selected_online_order_detail_error(token, exc),
            is_current=lambda: self._online_order_detail_token is token,
        )

    def _apply_selected_online_order_details(self, token, detailed):
        if self._online_order_detail_token is not token:
            return

        self._online_order_detail_loading = False
        if detailed is None:
            self.selected_online_order = None
            self.selected_online_order_id = None
            self._refresh_cart()
            return

        self.selected_online_order = detailed
        for index, transaction in enumerate(self.online_orders_cache):
            if transaction.transaction_id == detailed.transaction_id:
                self.online_orders_cache[index] = detailed
                break

        self._refresh_cart()

    def _handle_selected_online_order_detail_error(self, token, exc):
        if self._online_order_detail_token is not token:
            return

        self._online_order_detail_loading = False
        self._set_feedback(f"Failed to load online order details: {exc}")

    def _apply_online_order_selection_state(self, transaction_id):
        view = self.online_order_card_views.get(transaction_id)
        if not view:
            return

        transaction = next(
            (row for row in self.online_orders_cache if row.transaction_id == transaction_id),
            None,
        )
        if transaction is None:
            return

        is_selected = transaction_id == self.selected_online_order_id
        view["card"].configure(
            fg_color=self._selected_card_bg() if is_selected else self.c["input"],
            border_color=AMBER if is_selected else self.c["border"],
        )
        view["customer_label"].configure(text_color=AMBER if is_selected else self.c["text"])
        view["id_label"].configure(text_color=AMBER if is_selected else self.c["text_muted"])
        view["primary_date_label"].configure(
            text_color=self.c["text"] if is_selected else self.c["text_muted"]
        )
        view["status_label"].configure(
            text_color=SUCCESS if self._is_accepted_online_order(transaction) else AMBER
        )
        view["wait_label"].configure(
            text_color=SUCCESS if self._is_accepted_online_order(transaction) else AMBER
        )
        view["view_button"].configure(
            text="Viewing" if is_selected else "View Order",
            fg_color=self._selected_button_colors()[0] if is_selected else self.c["card"],
            hover_color=self._selected_button_colors()[1] if is_selected else self.c["border"],
            text_color=AMBER if is_selected else self.c["text"],
        )

    def _select_online_order(self, transaction_id):
        if (
            transaction_id == self.selected_online_order_id
            and self.selected_online_order is not None
            and getattr(self.selected_online_order, "items", None)
        ):
            return

        self.selected_online_order_id = transaction_id
        self.selected_online_order = next(
            (row for row in self.online_orders_cache if row.transaction_id == transaction_id),
            None,
        )
        self._load_selected_online_order_details()
        for tx_id in list(self.online_order_card_views.keys()):
            self._apply_online_order_selection_state(tx_id)
        self._refresh_cart()

    def _filter_products(self):
        if self.search_var.get().strip() and self.recent_dropdown_visible:
            self._hide_recent_searches()
        self._load_products(self.search_var.get().strip())

    def _find_cart_item(self, product_id):
        return next(
            (item for item in self.transaction.items if item["product"].product_id == product_id),
            None,
        )

    def _cart_quantity_for_product(self, product_id):
        if self.transaction_saved:
            return 0
        item = self._find_cart_item(product_id)
        if item is None:
            return 0
        try:
            return max(int(item.get("quantity", 0)), 0)
        except Exception:
            return 0

    def _display_stock_quantity(self, product_id):
        try:
            base_stock = int(self.product_stock_cache.get(product_id, 0) or 0)
        except Exception:
            base_stock = 0
        return max(base_stock - self._cart_quantity_for_product(product_id), 0)

    def _reserve_product_unit(self, product):
        # Cart actions should not deduct inventory immediately.
        # Actual inventory reservation happens during checkout.
        return True

    def _restore_reservation_group(self, reservation_group):
        if reservation_group:
            self.inventory_proxy.restore_deductions(reservation_group)

    def _restore_pending_inventory(self):
        for item in list(self.transaction.items):
            for reservation_group in item.get("reservations", []):
                self._restore_reservation_group(reservation_group)
        self.transaction.items = []

    def _release_reserved_groups(self, reserved_groups):
        for item, reservation_group in reversed(reserved_groups):
            if reservation_group in item.get("reservations", []):
                item["reservations"].remove(reservation_group)
            self._restore_reservation_group(reservation_group)

    def _ensure_transaction_inventory_reserved(self):
        reserved_now = []
        for item in self.transaction.items:
            reservations = item.setdefault("reservations", [])
            if reservations:
                continue

            reservation = self.inventory_proxy.reserve_fifo(
                item["product"].product_id,
                item["quantity"],
            )
            if not reservation:
                self._release_reserved_groups(reserved_now)
                return False, item["product"].name, []

            reservations.append(reservation)
            reserved_now.append((item, reservation))

        return True, None, reserved_now

    def _update_cart_item(self, item):
        item["quantity"] = max(int(item.get("quantity", 0)), 0)
        item["subtotal"] = Decimal(str(item["product"].price)) * item["quantity"]

    def _add_to_cart(self, product):
        self._set_feedback("")
        if self._display_stock_quantity(product.product_id) <= 0:
            self._set_feedback(f"No available stock left for {product.name}.")
            self._refresh_walkin_product_cards()
            return

        existing = self._find_cart_item(product.product_id)
        if existing:
            existing["quantity"] = int(existing.get("quantity", 0)) + 1
            existing.setdefault("reservations", [])
            self._update_cart_item(existing)
        else:
            self.transaction.items.append(
                {
                    "product": product,
                    "quantity": 1,
                    "subtotal": Decimal(str(product.price)),
                    "reservations": [],
                }
            )
        self._finish_walkin_product_action()

    def _increase_item(self, product_id):
        item = self._find_cart_item(product_id)
        if item is None:
            return
        self._set_feedback("")
        if self._display_stock_quantity(product_id) <= 0:
            self._set_feedback(f"No available stock left for {item['product'].name}.")
            self._refresh_walkin_product_cards()
            return
        item["quantity"] = int(item.get("quantity", 0)) + 1
        item.setdefault("reservations", [])
        self._update_cart_item(item)
        self._finish_walkin_product_action()

    def _decrease_item(self, product_id):
        item = self._find_cart_item(product_id)
        if item is None:
            return

        current_quantity = int(item.get("quantity", 0))
        if current_quantity > 0:
            item["quantity"] = current_quantity - 1

        self._update_cart_item(item)
        if item["quantity"] <= 0:
            self.transaction.items = [
                row for row in self.transaction.items if row["product"].product_id != product_id
            ]
        self._set_feedback("")
        self._finish_walkin_product_action()

    def _remove_item(self, product_id):
        item = self._find_cart_item(product_id)
        if item is None:
            return
        if self.transaction_saved:
            self._set_feedback("Start a new transaction before changing items.")
            return

        self.transaction.items = [
            row for row in self.transaction.items if row["product"].product_id != product_id
        ]
        self._set_feedback("")
        self._finish_walkin_product_action()
        if self.current_stage == "checkout" and not self.transaction.items:
            self._set_feedback("Cart is empty. Add items before checkout.")

    def _refresh_cart(self):
        c = self.c
        total_items = sum(item["quantity"] for item in self.transaction.items)
        total_label = f"{total_items} item{'s' if total_items != 1 else ''}"
        grand_total = self.transaction.get_total()

        self.checkout_items_count_label.configure(text=total_label)
        self._update_browse_panel_mode()

        if self._is_online_mode():
            selected_total = self.selected_online_order.get_total() if self.selected_online_order is not None else Decimal("0.00")
            online_count = len(self.online_orders_cache)
            queue_name = self._current_online_queue_name().lower()
            self.browse_items_count_label.configure(
                text=f"{online_count} {queue_name} order{'s' if online_count != 1 else ''}"
            )
            self.browse_total_label.configure(text=self._money_text(selected_total))
            has_selection = self.selected_online_order is not None
            self.proceed_button.configure(
                state="normal" if has_selection else "disabled",
                fg_color=AMBER if has_selection else c["input"],
                hover_color=AMBER_DARK if has_selection else c["input"],
                text_color="#0F0F0F" if has_selection else c["text_muted"],
            )
        else:
            self.browse_items_count_label.configure(text=total_label)
            self.browse_total_label.configure(text=self._money_text(grand_total))
            has_items = total_items > 0
            self.proceed_button.configure(
                state="normal" if has_items else "disabled",
                fg_color=AMBER if has_items else c["input"],
                hover_color=AMBER_DARK if has_items else c["input"],
                text_color="#0F0F0F" if has_items else c["text_muted"],
            )

        self._refresh_checkout_summary()
        current_stage = getattr(self, "current_stage", "browse")
        if current_stage == "checkout":
            self._render_checkout_cart()
        else:
            self._render_browse_cart()
        self.finished_preview_dirty = True
        if current_stage == "finished":
            self._render_transaction_preview()
            self.finished_preview_dirty = False
        self._update_receipt_actions()

    def _clear_browse_cart_content(self):
        for widget in self.browse_cart_frame.winfo_children():
            widget.destroy()
        self.walkin_cart_item_views = {}
        self.walkin_cart_empty_label = None
        self.selected_online_wait_label = None

    def _create_walkin_cart_item_view(self, item):
        c = self.c
        product_id = item["product"].product_id
        row = ctk.CTkFrame(self.browse_cart_frame, fg_color="transparent")

        name_label = ctk.CTkLabel(
            row,
            text=item["product"].name,
            anchor="w",
            justify="left",
            wraplength=210,
            font=ctk.CTkFont("Segoe UI", 13, "bold"),
            text_color=c["text"],
        )
        name_label.pack(fill="x")

        meta = ctk.CTkFrame(row, fg_color="transparent")
        meta.pack(fill="x", pady=(4, 0))
        meta_label = ctk.CTkLabel(
            meta,
            text="",
            font=ctk.CTkFont("Segoe UI", 10),
            text_color=c["text_muted"],
        )
        meta_label.pack(side="left")
        subtotal_label = ctk.CTkLabel(
            meta,
            text="",
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            text_color=AMBER,
        )
        subtotal_label.pack(side="right")

        adjust = ctk.CTkFrame(row, fg_color="transparent")
        adjust.pack(anchor="w", pady=(6, 0))
        ctk.CTkButton(
            adjust,
            text="-",
            width=34,
            height=30,
            fg_color=c["input"],
            hover_color=c["border"],
            text_color=c["text"],
            corner_radius=8,
            font=ctk.CTkFont("Segoe UI", 15, "bold"),
            command=lambda selected_product_id=product_id: self._decrease_item(selected_product_id),
        ).pack(side="left")
        ctk.CTkButton(
            adjust,
            text="+",
            width=34,
            height=30,
            fg_color=c["input"],
            hover_color=c["border"],
            text_color=c["text"],
            corner_radius=8,
            font=ctk.CTkFont("Segoe UI", 15, "bold"),
            command=lambda selected_product_id=product_id: self._increase_item(selected_product_id),
        ).pack(side="left", padx=(8, 0))

        separator = ctk.CTkFrame(row, fg_color=c["border"], height=1)
        self.walkin_cart_item_views[product_id] = {
            "row": row,
            "name_label": name_label,
            "meta_label": meta_label,
            "subtotal_label": subtotal_label,
            "separator": separator,
        }
        return self.walkin_cart_item_views[product_id]

    def _render_walkin_browse_cart(self):
        c = self.c
        self.selected_online_wait_label = None
        if self.browse_cart_render_mode != "walkin":
            self._clear_browse_cart_content()
            self.browse_cart_render_mode = "walkin"

        if not self.transaction.items:
            for product_id, view in list(self.walkin_cart_item_views.items()):
                row = view.get("row")
                if row is not None and row.winfo_exists():
                    row.destroy()
                self.walkin_cart_item_views.pop(product_id, None)

            if self.walkin_cart_empty_label is None or not self.walkin_cart_empty_label.winfo_exists():
                self.walkin_cart_empty_label = ctk.CTkLabel(
                    self.browse_cart_frame,
                    text="No items in this walk-in ticket yet.\nChoose products on the left to start the sale.",
                    justify="left",
                    font=ctk.CTkFont("Segoe UI", 13),
                    text_color=c["text_muted"],
                )
                self.walkin_cart_empty_label.pack(anchor="w", pady=24)
            return

        if self.walkin_cart_empty_label is not None and self.walkin_cart_empty_label.winfo_exists():
            self.walkin_cart_empty_label.destroy()
        self.walkin_cart_empty_label = None

        current_ids = {
            item["product"].product_id
            for item in self.transaction.items
        }
        for product_id, view in list(self.walkin_cart_item_views.items()):
            if product_id in current_ids:
                continue
            row = view.get("row")
            if row is not None and row.winfo_exists():
                row.destroy()
            self.walkin_cart_item_views.pop(product_id, None)

        last_index = len(self.transaction.items) - 1
        for index, item in enumerate(self.transaction.items):
            product_id = item["product"].product_id
            view = self.walkin_cart_item_views.get(product_id)
            if view is None or not view["row"].winfo_exists():
                view = self._create_walkin_cart_item_view(item)

            view["name_label"].configure(text=item["product"].name)
            view["meta_label"].configure(
                text=f"Qty {item['quantity']} | {self._money_text(item['product'].price)} each"
            )
            view["subtotal_label"].configure(text=self._money_text(item.get("subtotal")))

            row = view["row"]
            row.pack_forget()
            row.pack(fill="x", pady=(0, 10))

            separator = view["separator"]
            if index < last_index:
                if not separator.winfo_manager():
                    separator.pack(fill="x", pady=(10, 0))
            elif separator.winfo_manager():
                separator.pack_forget()

    def _render_browse_cart(self):
        c = self.c
        if self._is_online_mode():
            self._clear_browse_cart_content()
            self.browse_cart_render_mode = "online"
            if self.selected_online_order is None:
                queue_name = self._current_online_queue_name().lower()
                ctk.CTkLabel(
                    self.browse_cart_frame,
                    text=f"No {queue_name} online order selected yet.\nChoose one from the queue on the left.",
                    justify="left",
                    font=ctk.CTkFont("Segoe UI", 16),
                    text_color=c["text_muted"],
                ).pack(anchor="w", pady=24)
                return

            transaction = self.selected_online_order
            ctk.CTkLabel(
                self.browse_cart_frame,
                text=transaction.customer_number or f"Order #{transaction.transaction_id}",
                anchor="w",
                justify="left",
                font=ctk.CTkFont("Segoe UI", 18, "bold"),
                text_color=c["text"],
            ).pack(fill="x")
            ctk.CTkLabel(
                self.browse_cart_frame,
                text=f"Transaction ID {transaction.transaction_id}",
                anchor="w",
                justify="left",
                wraplength=220,
                font=ctk.CTkFont("Segoe UI", 13),
                text_color=c["text_muted"],
            ).pack(fill="x", pady=(4, 10))
            ctk.CTkLabel(
                self.browse_cart_frame,
                text=f"Status: {self._online_order_status_text(transaction)}",
                anchor="w",
                justify="left",
                font=ctk.CTkFont("Segoe UI", 14, "bold"),
                text_color=SUCCESS if self._is_accepted_online_order(transaction) else AMBER,
            ).pack(fill="x", pady=(0, 6))
            ctk.CTkLabel(
                self.browse_cart_frame,
                text=self._online_order_primary_date_text(transaction),
                anchor="w",
                justify="left",
                wraplength=220,
                font=ctk.CTkFont("Segoe UI", 13),
                text_color=c["text"],
            ).pack(fill="x", pady=(0, 2))
            self.selected_online_wait_label = ctk.CTkLabel(
                self.browse_cart_frame,
                text=self._online_order_wait_text(transaction),
                anchor="w",
                justify="left",
                font=ctk.CTkFont("Segoe UI", 14, "bold"),
                text_color=AMBER,
            )
            self.selected_online_wait_label.pack(fill="x", pady=(0, 10))
            if getattr(transaction, "accepted_at", None):
                ctk.CTkLabel(
                    self.browse_cart_frame,
                    text=f"Accepted At: {str(transaction.accepted_at)[:19]}",
                    anchor="w",
                    justify="left",
                    wraplength=220,
                    font=ctk.CTkFont("Segoe UI", 12),
                    text_color=c["text_muted"],
                ).pack(fill="x", pady=(0, 10))

            if self._online_order_detail_loading and not getattr(transaction, "items", None):
                ctk.CTkLabel(
                    self.browse_cart_frame,
                    text="Loading order details...",
                    anchor="w",
                    justify="left",
                    font=ctk.CTkFont("Segoe UI", 12),
                    text_color=c["text_muted"],
                ).pack(fill="x", pady=(0, 10))
                return

            for index, item in enumerate(transaction.items):
                row = ctk.CTkFrame(self.browse_cart_frame, fg_color="transparent")
                row.pack(fill="x", pady=(0, 14))
                ctk.CTkLabel(
                    row,
                    text=item["product"].name,
                    anchor="w",
                    justify="left",
                    wraplength=210,
                    font=ctk.CTkFont("Segoe UI", 15, "bold"),
                    text_color=c["text"],
                ).pack(fill="x")
                ctk.CTkLabel(
                    row,
                    text=f"Qty {item['quantity']} | {self._money_text(item['product'].price)} each",
                    anchor="w",
                    justify="left",
                    wraplength=220,
                    font=ctk.CTkFont("Segoe UI", 12),
                    text_color=c["text_muted"],
                ).pack(fill="x", pady=(4, 0))
                ctk.CTkLabel(
                    row,
                    text=self._money_text(item.get("subtotal")),
                    font=ctk.CTkFont("Segoe UI", 15, "bold"),
                    text_color=AMBER,
                ).pack(anchor="w", pady=(4, 0))
                if index < len(transaction.items) - 1:
                    ctk.CTkFrame(row, fg_color=c["border"], height=1).pack(fill="x", pady=(12, 0))
            return
        self._render_walkin_browse_cart()

    def _render_checkout_cart(self):
        c = self.c
        for widget in self.checkout_cart_frame.winfo_children():
            widget.destroy()

        if not self.transaction.items:
            ctk.CTkLabel(
                self.checkout_cart_frame,
                text="No items ready for checkout.",
                font=ctk.CTkFont("Segoe UI", 13),
                text_color=c["text_muted"],
            ).pack(anchor="w", pady=24)
            return

        for index, item in enumerate(self.transaction.items):
            row = ctk.CTkFrame(self.checkout_cart_frame, fg_color="transparent")
            row.pack(fill="x", pady=(0, 10))

            header = ctk.CTkFrame(row, fg_color="transparent")
            header.pack(fill="x")
            ctk.CTkLabel(
                header,
                text=item["product"].name,
                anchor="w",
                justify="left",
                wraplength=260,
                font=ctk.CTkFont("Segoe UI", 12, "bold"),
                text_color=c["text"],
            ).pack(side="left")
            ctk.CTkLabel(
                header,
                text=self._money_text(item.get("subtotal")),
                font=ctk.CTkFont("Segoe UI", 12, "bold"),
                text_color=AMBER,
            ).pack(side="right")

            ctk.CTkLabel(
                row,
                text=f"Qty {item['quantity']} | {item['product'].category} | {self._money_text(item['product'].price)} each",
                anchor="w",
                justify="left",
                font=ctk.CTkFont("Segoe UI", 10),
                text_color=c["text_muted"],
            ).pack(fill="x", pady=(4, 0))

            if not self.transaction_saved and self.online_checkout_source is None:
                ctk.CTkButton(
                    row,
                    text="Delete",
                    width=78,
                    height=28,
                    fg_color=self._danger_button_colors()[0],
                    hover_color=self._danger_button_colors()[1],
                    text_color=ERROR_RED,
                    corner_radius=8,
                    font=ctk.CTkFont("Segoe UI", 10, "bold"),
                    command=lambda selected_product_id=item["product"].product_id: self._remove_item(selected_product_id),
                ).pack(anchor="w", pady=(6, 0))

            if index < len(self.transaction.items) - 1:
                ctk.CTkFrame(row, fg_color=c["border"], height=1).pack(fill="x", pady=(10, 0))

    def _render_transaction_preview(self):
        c = self.c
        for widget in self.preview_frame.winfo_children():
            widget.destroy()

        if not self.transaction_saved or self.transaction.transaction_id is None:
            empty = ctk.CTkFrame(self.preview_frame, fg_color="transparent")
            empty.pack(fill="x", pady=8)
            ctk.CTkLabel(
                empty,
                text="No finished transaction yet.",
                anchor="w",
                justify="left",
                wraplength=520,
                font=ctk.CTkFont("Segoe UI", 13, "bold"),
                text_color=c["text"],
            ).pack(fill="x")
            ctk.CTkLabel(
                empty,
                text="After you finish the sale, the receipt preview will appear here.",
                anchor="w",
                justify="left",
                wraplength=520,
                font=ctk.CTkFont("Segoe UI", 11),
                text_color=c["text_muted"],
            ).pack(fill="x", pady=(6, 0))
            return

        status_text = "VOIDED" if self.transaction.is_voided else "COMPLETED"
        status_color = ERROR_RED if self.transaction.is_voided else SUCCESS

        receipt_card = ctk.CTkFrame(
            self.preview_frame,
            fg_color=c["input"],
            corner_radius=12,
            border_width=1,
            border_color=c["border"],
        )
        receipt_card.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(
            receipt_card,
            text="BAKEWISE RECEIPT",
            font=ctk.CTkFont("Georgia", 17, "bold"),
            text_color=AMBER,
        ).pack(anchor="w", padx=14, pady=(12, 2))
        ctk.CTkLabel(
            receipt_card,
            text=f"Receipt No. {self.transaction.customer_number or '-'}",
            font=ctk.CTkFont("Segoe UI", 15, "bold"),
            text_color=c["text"],
        ).pack(anchor="w", padx=14, pady=(0, 4))
        ctk.CTkLabel(
            receipt_card,
            text=status_text,
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            text_color=status_color,
        ).pack(anchor="w", padx=14)
        labels = [
            f"Transaction ID: {self.transaction.transaction_id}",
            f"Date: {self.transaction.date}",
            f"Cashier: {self.transaction.cashier_name}",
            f"Service Mode: {self.transaction.service_mode}",
            f"Order Source: {self.transaction.order_source}",
        ]
        pickup_text = self._transaction_pickup_text(self.transaction)
        if pickup_text:
            labels.append(pickup_text)
        for label in labels:
            ctk.CTkLabel(
                receipt_card,
                text=label,
                anchor="w",
                justify="left",
                wraplength=500,
                font=ctk.CTkFont("Segoe UI", 10),
                text_color=c["text_muted"],
            ).pack(fill="x", padx=14, pady=(2, 0))
        ctk.CTkFrame(receipt_card, fg_color=c["border"], height=1).pack(fill="x", padx=14, pady=10)

        for index, item in enumerate(self.transaction.items):
            item_row = ctk.CTkFrame(receipt_card, fg_color="transparent")
            item_row.pack(fill="x", pady=(0, 8))
            ctk.CTkLabel(
                item_row,
                text=f"{item['product'].name} x{item['quantity']}",
                anchor="w",
                justify="left",
                wraplength=500,
                font=ctk.CTkFont("Segoe UI", 11, "bold"),
                text_color=c["text"],
            ).pack(fill="x", padx=14)
            ctk.CTkLabel(
                item_row,
                text=self._money_text(item.get("subtotal")),
                anchor="w",
                justify="left",
                font=ctk.CTkFont("Segoe UI", 10, "bold"),
                text_color=AMBER,
            ).pack(fill="x", padx=14, pady=(2, 0))
            ctk.CTkLabel(
                item_row,
                text=f"{item['product'].category} | {self._money_text(item['product'].price)} each",
                anchor="w",
                justify="left",
                wraplength=500,
                font=ctk.CTkFont("Segoe UI", 9),
                text_color=c["text_muted"],
            ).pack(fill="x", padx=14, pady=(2, 0))
            if index < len(self.transaction.items) - 1:
                ctk.CTkFrame(item_row, fg_color=c["border"], height=1).pack(fill="x", padx=14, pady=(8, 0))

        totals = ctk.CTkFrame(
            receipt_card,
            fg_color="transparent",
        )
        ctk.CTkFrame(receipt_card, fg_color=c["border"], height=1).pack(fill="x", padx=14, pady=(6, 8))
        totals.pack(fill="x", padx=14, pady=(0, 12))
        for label, value, color in [
            ("TOTAL", self._money_text(self.transaction.get_total()), AMBER),
            ("Payment", self.transaction.payment_method or "-", c["text"]),
            ("Amount Paid", self._money_text(self.transaction.amount_paid), c["text"]),
            ("Change", self._money_text(self.transaction.get_change()), c["text"]),
        ]:
            total_row = ctk.CTkFrame(totals, fg_color="transparent")
            total_row.pack(fill="x", pady=3)
            ctk.CTkLabel(
                total_row,
                text=label,
                font=ctk.CTkFont("Segoe UI", 10, "bold" if label == "TOTAL" else "normal"),
                text_color=c["text_muted"] if label != "TOTAL" else AMBER,
            ).pack(side="left")
            ctk.CTkLabel(
                total_row,
                text=value,
                font=ctk.CTkFont("Segoe UI", 10, "bold" if label == "TOTAL" else "normal"),
                text_color=color,
            ).pack(side="right")

    def _append_amount_value(self, token):
        current = self.amount_var.get().strip()
        if token == "." and "." in current:
            return
        if token == "00" and not current:
            current = "0"
        next_value = f"{current}{token}" if current else token
        self.amount_var.set(next_value)
        self.amount_entry.focus_set()

    def _backspace_amount(self):
        current = self.amount_var.get()
        self.amount_var.set(current[:-1] if current else "")
        self.amount_entry.focus_set()

    def _clear_amount(self):
        self.amount_var.set("")
        self.amount_entry.focus_set()

    def _apply_exact_amount(self):
        self.amount_var.set(self._amount_text(self.transaction.get_total()))
        self.amount_entry.focus_set()

    def _increase_amount_by(self, amount):
        current = self.amount_var.get().strip()
        try:
            base_value = self._to_money_decimal(current) if current else Decimal("0")
        except Exception:
            base_value = Decimal("0")
        self.amount_var.set(self._amount_text(base_value + amount))
        self.amount_entry.focus_set()

    def _checkout(self):
        self._set_feedback("")
        if self.transaction_saved:
            self._set_feedback("This sale is already completed. Start a new transaction.")
            return
        if not self.transaction.items:
            self._set_feedback("Cart is empty.")
            return

        amount, amount_error = self._parsed_amount_paid()
        validation_message = self._payment_validation_message(amount_error=amount_error)
        if validation_message:
            self._set_feedback(validation_message)
            self._sync_finish_transaction_button_state(amount_error=amount_error)
            return

        service_mode, order_source = self._selected_transaction_metadata()
        total = self.transaction.get_total()
        method = self.payment_var.get()

        confirm_message = (
            f"Finish this transaction for {self._money_text(total)}?\n\n"
            f"Payment Method: {method}\n"
            f"Amount Paid: {self._money_text(amount)}\n"
            f"Order Source: {order_source}\n"
            f"Service Mode: {service_mode}\n\n"
            "You can still void the transaction later from the finished transaction panel, even after printing the ticket."
        )
        if not messagebox.askyesno("Confirm Finish Transaction", confirm_message, parent=self):
            self._set_feedback("Finish transaction cancelled.")
            return

        self._sync_transaction_metadata()
        inventory_ready, missing_product, reserved_now = self._ensure_transaction_inventory_reserved()
        if not inventory_ready:
            self._set_feedback(f"Not enough stock available to finish {missing_product}.")
            return

        if not self.transaction.checkout(method, amount):
            self._release_reserved_groups(reserved_now)
            self._set_feedback(f"Unable to finish the transaction. Total is {self._money_text(total)}.")
            return

        if self.online_checkout_source is not None:
            try:
                cashier_name = self.user.get("username", "cashier")
                processed_at = TransactionDB.complete_online_order(
                    self.online_checkout_source.transaction_id,
                    cashier_name,
                    method,
                    amount,
                    self.transaction.pickup_date_from,
                    self.transaction.pickup_date_to,
                )
                self.transaction.transaction_id = self.online_checkout_source.transaction_id
                self.transaction.date = self.online_checkout_source.date
                self.transaction.cashier_name = cashier_name
                self.transaction.customer_number = (
                    self.online_checkout_source.customer_number or self.transaction.customer_number
                )
                self.transaction.mark_online_processed(processed_at)
                self.transaction_saved = True
                self.ticket_printed = False
                self.selected_online_order = None
                self.selected_online_order_id = None
                self.online_checkout_source = None
                self._load_online_orders(self.search_var.get().strip(), force_reload=True)
            except Exception as exc:
                self._release_reserved_groups(reserved_now)
                self._set_feedback(f"Failed to update online order: {exc}")
                return

            self._refresh_cart()
            self._show_stage("finished")
            self._set_feedback(
                f"Online order #{self.transaction.transaction_id} was processed, recorded, and removed from the pending queue. "
                "Print it, export it, or void it if needed."
            )
            return

        try:
            tx_id = TransactionDB.save_transaction(self.transaction)
            self.transaction.transaction_id = tx_id
            self.transaction_saved = True
            self.ticket_printed = False
        except Exception as exc:
            self._release_reserved_groups(reserved_now)
            self._set_feedback(f"Failed to save transaction: {exc}")
            return

        self._refresh_cart()
        self._show_stage("finished")
        self._set_feedback(
            f"{self.transaction.customer_number or 'Customer'} saved under transaction "
            f"#{self.transaction.transaction_id}. Preview it here, then print, export, or void it."
        )

    def _new_transaction(self, restore_inventory=True):
        if restore_inventory:
            self._restore_pending_inventory()

        next_workspace = self.locked_workspace or self._normalize_workspace_mode(self.order_source_var.get())
        self.transaction = Transaction(None, self.user.get("username", "cashier"))
        self.online_checkout_source = None
        self.transaction_saved = False
        self.ticket_printed = False
        self.amount_var.set("")
        self.service_mode_var.set("Take Out")
        self.order_source_var.set(next_workspace)
        if next_workspace == "Online Orders":
            self._reset_online_queue_render_limit()
        self.checkout_pickup_start = None
        self.checkout_pickup_end = None
        self._set_feedback("")
        self.payment_var.set("Cash")
        self._update_customer_number_hint()
        self._refresh_order_source_ui(force_reload=True)
        self._show_stage("browse")

    def _handle_destroy(self, event):
        if event.widget is not self:
            return
        if self.search_after_id is not None:
            try:
                self.after_cancel(self.search_after_id)
            except Exception:
                pass
            self.search_after_id = None
        if self.search_keyboard_popup is not None and self.search_keyboard_popup.winfo_exists():
            self.search_keyboard_popup.destroy()
        for card in list(self.order_notification_cards):
            self._dismiss_order_notification(card)
        if self.notification_host is not None and self.notification_host.winfo_exists():
            self.notification_host.destroy()
        if not self.transaction_saved and getattr(self.transaction, "items", None):
            self._restore_pending_inventory()

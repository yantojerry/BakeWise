from concurrent.futures import ThreadPoolExecutor
import threading
import tkinter as tk
from datetime import date, datetime, timedelta
from decimal import Decimal

import customtkinter as ctk

from database.ingredient_db import IngredientDB
from database.inventory_db import InventoryDB
from database.product_db import ProductDB
from database.transaction_db import TransactionDB
from gui.date_picker import TouchDatePicker
from gui.theme import AMBER, AMBER_DARK, BLUE, ERROR_RED, SUCCESS, WARNING, get_colors

SALES_PAGE_SIZE = 10
CHART_HEIGHT = 220


class ReportsScreen(ctk.CTkFrame):
    def __init__(self, parent, user):
        self.c = get_colors()
        super().__init__(parent, fg_color=self.c["bg"], corner_radius=0)
        self.user = user
        self.active_tab = ctk.StringVar(value="sales")
        self.tab_buttons = {}
        self.category_options = ["All Categories"]
        self.date_preset_var = ctk.StringVar(value="All Time")
        self.start_date_var = ctk.StringVar()
        self.end_date_var = ctk.StringVar()
        self.category_var = ctk.StringVar(value="All Categories")
        self.group_var = ctk.StringVar(value="Auto")
        self.best_metric_var = ctk.StringVar(value="Quantity")
        self.expiry_window_var = ctk.StringVar(value="14 Days")
        self.sales_sort_key = "receipt"
        self.sales_sort_direction = "asc"
        self.date_preset_buttons = {}
        self.date_value_buttons = {}
        self.active_date_picker = None
        self.sales_report_host = None
        self.sales_table_host = None
        self.sales_details_popup = None
        self.product_details_popup = None
        self.sales_page = 0
        self.sales_total_count = 0
        self.bestseller_page = 0
        self.low_stock_page = 0
        self.expiring_page = 0
        self.bestseller_list_host = None
        self.low_stock_list_host = None
        self.expiring_list_host = None
        self.bestseller_data_cache = None
        self.low_stock_data_cache = None
        self.expiring_data_cache = None
        self._load_token = 0
        self._apply_date_preset("All Time")
        self._load_categories()
        self.pack(fill="both", expand=True)
        self._build_ui()
        self._switch_tab("sales")

    def _build_ui(self):
        c = self.c
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=32, pady=(28, 0))
        ctk.CTkLabel(
            header,
            text="Reports",
            font=ctk.CTkFont("Georgia", 28, "bold"),
            text_color=c["text"],
        ).pack(anchor="w")
        ctk.CTkLabel(
            header,
            text="Preset ranges are the quickest option for daily reporting, and custom dates stay available when you need an exact lookup.",
            font=ctk.CTkFont("Segoe UI", 12),
            text_color=c["text_muted"],
        ).pack(anchor="w", pady=(4, 0))
        ctk.CTkFrame(self, fg_color=c["border"], height=1).pack(fill="x", padx=32, pady=20)

        tabs = ctk.CTkFrame(self, fg_color="transparent")
        tabs.pack(fill="x", padx=32, pady=(0, 18))
        for label, key in [
            ("Sales Summary", "sales"),
            ("Best Sellers", "bestsellers"),
            ("Low Stock", "lowstock"),
            ("Expiring Soon", "expiring"),
        ]:
            button = ctk.CTkButton(
                tabs,
                text=label,
                width=150,
                height=38,
                corner_radius=10,
                border_width=1,
                border_color=c["border"],
                font=ctk.CTkFont("Segoe UI", 12, "bold"),
                command=lambda selected=key: self._switch_tab(selected),
            )
            button.pack(side="left", padx=(0, 8))
            self.tab_buttons[key] = button

        self.content = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color=c["card"],
            scrollbar_button_hover_color=c["border"],
        )
        self.content.pack(fill="both", expand=True, padx=32, pady=(0, 24))
        self._refresh_tabs()

    def _refresh_tabs(self):
        c = self.c
        active = self.active_tab.get()
        for key, button in self.tab_buttons.items():
            is_active = key == active
            button.configure(
                fg_color=AMBER if is_active else c["card"],
                hover_color=AMBER_DARK if is_active else c["input"],
                text_color="#0F0F0F" if is_active else c["text_gray"],
            )

    def _switch_tab(self, key):
        self.active_tab.set(key)
        self._refresh_tabs()
        self.date_preset_buttons = {}
        self.date_value_buttons = {}
        self.sales_report_host = None
        self.sales_table_host = None
        self.bestseller_list_host = None
        self.low_stock_list_host = None
        self.expiring_list_host = None
        for widget in self.content.winfo_children():
            widget.destroy()
        if key == "sales":
            self._show_sales()
        elif key == "bestsellers":
            self._show_bestsellers()
        elif key == "lowstock":
            self._show_low_stock()
        elif key == "expiring":
            self._show_expiring()

    def _reload_current_tab(self):
        self._switch_tab(self.active_tab.get())

    def _load_categories(self):
        try:
            categories = ProductDB.get_categories()
        except Exception:
            categories = []
        self.category_options = ["All Categories"] + categories
        if self.category_var.get() not in self.category_options:
            self.category_var.set("All Categories")

    def _build_card(self, parent, title, subtitle=""):
        c = self.c
        card = ctk.CTkFrame(
            parent,
            fg_color=c["card"],
            corner_radius=16,
            border_width=1,
            border_color=c["border"],
        )
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(18, 10))
        ctk.CTkLabel(
            header,
            text=title,
            font=ctk.CTkFont("Segoe UI", 14, "bold"),
            text_color=c["text"],
        ).pack(anchor="w")
        if subtitle:
            ctk.CTkLabel(
                header,
                text=subtitle,
                font=ctk.CTkFont("Segoe UI", 11),
                text_color=c["text_muted"],
            ).pack(anchor="w", pady=(4, 0))
        ctk.CTkFrame(card, fg_color=c["border"], height=1).pack(fill="x", padx=20)
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=(16, 18))
        return card, body

    def _build_metric_card(self, parent, title, value, caption, accent_color):
        c = self.c
        card = ctk.CTkFrame(
            parent,
            fg_color=c["card"],
            corner_radius=14,
            border_width=1,
            border_color=c["border"],
        )
        ctk.CTkFrame(card, fg_color=accent_color, corner_radius=999, height=4).pack(fill="x", padx=16, pady=(14, 12))
        ctk.CTkLabel(
            card,
            text=title,
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            text_color=c["text_muted"],
        ).pack(anchor="w", padx=16)
        ctk.CTkLabel(
            card,
            text=value,
            font=ctk.CTkFont("Georgia", 19, "bold"),
            text_color=accent_color,
            justify="left",
            wraplength=220,
        ).pack(anchor="w", padx=16, pady=(6, 6))
        ctk.CTkLabel(
            card,
            text=caption,
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=c["text_gray"],
            justify="left",
            wraplength=220,
        ).pack(anchor="w", padx=16, pady=(0, 16))
        return card

    def _show_loading(self, container, text="Loading report..."):
        for widget in container.winfo_children():
            widget.destroy()
        ctk.CTkLabel(
            container,
            text=text,
            font=ctk.CTkFont("Segoe UI", 12),
            text_color=self.c["text_muted"],
        ).pack(pady=24)

    def _show_error(self, container, error):
        for widget in container.winfo_children():
            widget.destroy()
        ctk.CTkLabel(
            container,
            text=f"Unable to load this report.\n{error}",
            font=ctk.CTkFont("Segoe UI", 12),
            text_color=ERROR_RED,
            justify="left",
            wraplength=860,
        ).pack(anchor="w", padx=8, pady=18)

    def _run_async(self, tab_key, fetch, on_success, on_error):
        self._load_token += 1
        token = self._load_token

        def worker():
            try:
                data = fetch()
                error = None
            except Exception as exc:
                data = None
                error = str(exc)
            self.after(0, lambda: self._finish_async(tab_key, token, data, error, on_success, on_error))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_async(self, tab_key, token, data, error, on_success, on_error):
        if token != self._load_token or self.active_tab.get() != tab_key or not self.winfo_exists():
            return
        if error:
            on_error(error)
            return
        on_success(data)

    def _fetch_parallel(self, tasks):
        if not tasks:
            return {}
        with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
            future_map = {executor.submit(worker): key for key, worker in tasks.items()}
            return {key: future.result() for future, key in future_map.items()}

    def _apply_date_preset(self, preset):
        today = date.today()
        if preset == "All Time":
            start_date, end_date = TransactionDB.get_transaction_date_bounds()
            if start_date is None or end_date is None:
                start_date = today
                end_date = today
        elif preset == "Today":
            start_date = today
            end_date = today
        elif preset == "Last 7 Days":
            start_date = today - timedelta(days=6)
            end_date = today
        elif preset == "This Year":
            start_date = today.replace(month=1, day=1)
            end_date = today
        else:
            start_date = today.replace(day=1)
            end_date = today
        self.start_date_var.set(start_date.isoformat())
        self.end_date_var.set(end_date.isoformat())

    def _on_preset_selected(self, value):
        if value == "Custom":
            return
        self._apply_date_preset(value)

    def _select_date_preset(self, value):
        self.date_preset_var.set(value)
        if value == "Custom":
            self._refresh_date_preset_buttons()
            self._open_date_picker("start")
            return
        self._apply_date_preset(value)
        self._refresh_date_preset_buttons()
        self._refresh_date_value_buttons()

    def _build_date_preset_chips(self, parent):
        c = self.c
        chips = ctk.CTkFrame(parent, fg_color="transparent")
        chips.pack(fill="x")
        self.date_preset_buttons = {}
        for preset in ["All Time", "Today", "Last 7 Days", "This Month", "This Year", "Custom"]:
            button = ctk.CTkButton(
                chips,
                text=preset,
                height=34,
                corner_radius=999,
                font=ctk.CTkFont("Segoe UI", 11, "bold"),
                command=lambda selected=preset: self._select_date_preset(selected),
            )
            button.pack(side="left", padx=(0, 8))
            self.date_preset_buttons[preset] = button
        self._refresh_date_preset_buttons()
        return chips

    def _refresh_date_preset_buttons(self):
        if not self.date_preset_buttons:
            return
        c = self.c
        active = self.date_preset_var.get()
        for preset, button in self.date_preset_buttons.items():
            is_active = preset == active
            button.configure(
                fg_color=AMBER if is_active else c["input"],
                hover_color=AMBER_DARK if is_active else c["border"],
                text_color="#0F0F0F" if is_active else c["text"],
                border_width=1 if not is_active else 0,
                border_color=c["border"],
            )

    def _date_button_text(self, target):
        raw_value = self.start_date_var.get().strip() if target == "start" else self.end_date_var.get().strip()
        try:
            parsed = datetime.strptime(raw_value, "%Y-%m-%d").date()
            return parsed.strftime("%b %d, %Y")
        except ValueError:
            return "Select Date"

    def _refresh_date_value_buttons(self):
        for target, button in self.date_value_buttons.items():
            if button.winfo_exists():
                button.configure(text=self._date_button_text(target))

    def _default_sales_sort_direction(self, sort_key):
        normalized = str(sort_key).strip().lower()
        return "asc" if normalized in {"receipt", "payment", "status"} else "desc"

    def _set_sales_sort(self, sort_key):
        normalized = str(sort_key).strip().lower()
        if normalized == self.sales_sort_key:
            self.sales_sort_direction = "asc" if self.sales_sort_direction == "desc" else "desc"
        else:
            self.sales_sort_key = normalized
            self.sales_sort_direction = self._default_sales_sort_direction(normalized)
        self.sales_page = 0
        if self.active_tab.get() == "sales" and self.sales_table_host is not None and self.sales_table_host.winfo_exists():
            self._refresh_sales_table_only()
            return
        self._reload_current_tab()

    def _sales_sort_indicator(self, sort_key):
        normalized = str(sort_key).strip().lower()
        if normalized != self.sales_sort_key:
            return ""
        return " \u25B2" if self.sales_sort_direction == "asc" else " \u25BC"

    def _sales_sort_caption(self):
        captions = {
            ("receipt", "asc"): "Sorted by date, then daily receipt number",
            ("receipt", "desc"): "Sorted by latest date, then latest daily receipt",
            ("date", "asc"): "Sorted by date from oldest to newest",
            ("date", "desc"): "Sorted by date from newest to oldest",
            ("payment", "asc"): "Sorted by payment from A to Z",
            ("payment", "desc"): "Sorted by payment from Z to A",
            ("status", "asc"): "Sorted by status with voided receipts first, then newest within each group",
            ("status", "desc"): "Sorted by status with completed receipts first, then newest within each group",
            ("total", "asc"): "Sorted by total from lowest to highest",
            ("total", "desc"): "Sorted by total from highest to lowest",
        }
        return captions.get((self.sales_sort_key, self.sales_sort_direction), "Sorted by date, then daily receipt number")

    def _sales_page_count(self, total_count):
        if total_count <= 0:
            return 1
        return ((total_count - 1) // SALES_PAGE_SIZE) + 1

    def _resolved_sales_page(self, total_count):
        page_count = self._sales_page_count(total_count)
        page = min(max(self.sales_page, 0), page_count - 1)
        return page, page_count

    def _change_sales_page(self, step):
        page_count = self._sales_page_count(self.sales_total_count)
        next_page = min(max(self.sales_page + step, 0), page_count - 1)
        if next_page == self.sales_page:
            return
        self.sales_page = next_page
        if self.active_tab.get() == "sales" and self.sales_table_host is not None and self.sales_table_host.winfo_exists():
            self._refresh_sales_table_only(message="Loading sales page...")
            return
        self._reload_current_tab()

    def _page_count(self, total_count):
        if total_count <= 0:
            return 1
        return ((total_count - 1) // SALES_PAGE_SIZE) + 1

    def _slice_page_rows(self, rows, page):
        total_count = len(rows)
        page_count = self._page_count(total_count)
        page = min(max(page, 0), page_count - 1)
        start = page * SALES_PAGE_SIZE
        end = start + SALES_PAGE_SIZE
        return rows[start:end], page, page_count, total_count

    def _jump_to_page(self, section, raw_value, page_count):
        try:
            requested_page = int(str(raw_value).strip() or "1") - 1
        except ValueError:
            requested_page = 0
        requested_page = min(max(requested_page, 0), page_count - 1)

        rerender = None
        if section == "sales":
            if requested_page == self.sales_page:
                return
            self.sales_page = requested_page
            rerender = lambda: self._refresh_sales_table_only(message="Loading sales page...")
        elif section == "bestsellers":
            if requested_page == self.bestseller_page:
                return
            self.bestseller_page = requested_page
            rerender = self._rerender_bestseller_list
        elif section == "lowstock":
            if requested_page == self.low_stock_page:
                return
            self.low_stock_page = requested_page
            rerender = self._rerender_low_stock_list
        elif section == "expiring":
            if requested_page == self.expiring_page:
                return
            self.expiring_page = requested_page
            rerender = self._rerender_expiring_list

        if rerender is not None:
            rerender()

    def _render_pagination_footer(self, parent, section, page, page_count, total_count, item_count, on_change_page):
        footer = ctk.CTkFrame(parent, fg_color="transparent")
        footer.pack(fill="x", pady=(12, 0))

        if total_count > 0:
            range_start = (page * SALES_PAGE_SIZE) + 1
            range_end = min(total_count, range_start + item_count - 1)
            summary_text = f"Showing {range_start}-{range_end} of {total_count}."
        else:
            summary_text = "Showing 0 results."

        ctk.CTkLabel(
            footer,
            text=f"{summary_text} Page {page + 1} of {page_count}",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=self.c["text_gray"],
        ).pack(side="left")

        pager = ctk.CTkFrame(footer, fg_color="transparent")
        pager.pack(side="right")

        prev_button = ctk.CTkButton(
            pager,
            text="Previous",
            width=92,
            height=34,
            corner_radius=10,
            fg_color=self.c["input"],
            hover_color=self.c["border"],
            text_color=self.c["text"],
            font=ctk.CTkFont("Segoe UI", 11),
            command=lambda: on_change_page(-1),
        )
        prev_button.pack(side="left")

        page_var = ctk.StringVar(value=str(page + 1))
        page_entry = ctk.CTkEntry(
            pager,
            width=56,
            height=34,
            corner_radius=10,
            textvariable=page_var,
            fg_color=self.c["input"],
            border_color=self.c["border"],
            text_color=self.c["text"],
            justify="center",
            font=ctk.CTkFont("Segoe UI", 11),
        )
        page_entry.pack(side="left", padx=(8, 8))
        page_entry.bind("<Return>", lambda _event: self._jump_to_page(section, page_var.get(), page_count))

        go_button = ctk.CTkButton(
            pager,
            text="Go",
            width=58,
            height=34,
            corner_radius=10,
            fg_color=self.c["input"],
            hover_color=self.c["border"],
            text_color=self.c["text"],
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            command=lambda: self._jump_to_page(section, page_var.get(), page_count),
        )
        go_button.pack(side="left")

        next_button = ctk.CTkButton(
            pager,
            text="Next",
            width=92,
            height=34,
            corner_radius=10,
            fg_color=AMBER,
            hover_color=AMBER_DARK,
            text_color="#0F0F0F",
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            command=lambda: on_change_page(1),
        )
        next_button.pack(side="left", padx=(8, 0))

        if page <= 0:
            prev_button.configure(state="disabled", fg_color=self.c["border"], text_color=self.c["text_muted"])
        if page >= page_count - 1 or total_count == 0:
            next_button.configure(state="disabled", fg_color=self.c["border"], text_color=self.c["text_muted"])

    def _open_date_picker(self, target):
        initial_text = self.start_date_var.get().strip() if target == "start" else self.end_date_var.get().strip()
        try:
            initial_date = datetime.strptime(initial_text, "%Y-%m-%d").date()
        except ValueError:
            initial_date = date.today()

        if self.active_date_picker is not None and self.active_date_picker.winfo_exists():
            self.active_date_picker.destroy()

        anchor_widget = self.date_value_buttons.get(target)
        title = "Select Start Date" if target == "start" else "Select End Date"
        self.active_date_picker = TouchDatePicker(
            self.winfo_toplevel(),
            self.c,
            initial_date,
            title,
            lambda chosen_date, selected=target: self._on_date_picked(selected, chosen_date),
            anchor_widget=anchor_widget,
        )

    def _on_date_picked(self, target, chosen_date):
        chosen_text = chosen_date.isoformat()
        self.date_preset_var.set("Custom")
        if target == "start":
            self.start_date_var.set(chosen_text)
            try:
                current_end = datetime.strptime(self.end_date_var.get().strip(), "%Y-%m-%d").date()
            except ValueError:
                current_end = None
            if current_end is None or chosen_date > current_end:
                self.end_date_var.set(chosen_text)
        else:
            self.end_date_var.set(chosen_text)
            try:
                current_start = datetime.strptime(self.start_date_var.get().strip(), "%Y-%m-%d").date()
            except ValueError:
                current_start = None
            if current_start is None or chosen_date < current_start:
                self.start_date_var.set(chosen_text)

        self._refresh_date_preset_buttons()
        self._refresh_date_value_buttons()

    def _build_touch_date_field(self, parent, label_text, target, column, total_columns):
        c = self.c
        parent.grid_columnconfigure(column, weight=1 if column < total_columns - 1 else 0)
        ctk.CTkLabel(
            parent,
            text=label_text,
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            text_color=c["text_muted"],
        ).grid(row=0, column=column, sticky="w", padx=(0, 12), pady=(0, 6))

        button = ctk.CTkButton(
            parent,
            text=self._date_button_text(target),
            height=40,
            corner_radius=10,
            fg_color=c["input"],
            hover_color=c["border"],
            text_color=c["text"],
            anchor="w",
            font=ctk.CTkFont("Segoe UI", 12),
            command=lambda selected=target: self._open_date_picker(selected),
        )
        button.grid(row=1, column=column, sticky="ew", padx=(0, 12))
        self.date_value_buttons[target] = button
        self._refresh_date_value_buttons()

    def _reset_sales_filters(self):
        self.date_preset_var.set("All Time")
        self.group_var.set("Auto")
        self.category_var.set("All Categories")
        self.best_metric_var.set("Quantity")
        self.sales_sort_key = "receipt"
        self.sales_sort_direction = "asc"
        self.sales_page = 0
        self.bestseller_page = 0
        self._apply_date_preset("All Time")
        self._reload_current_tab()

    def _reset_stock_filters(self):
        self.date_preset_var.set("All Time")
        self.group_var.set("Auto")
        self.low_stock_page = 0
        self._apply_date_preset("All Time")
        self._reload_current_tab()

    def _reset_expiry_filters(self):
        self.expiry_window_var.set("14 Days")
        self.expiring_page = 0
        self._reload_current_tab()

    def _apply_sales_filters(self):
        if self.sales_sort_key == "receipt":
            self.sales_sort_direction = "asc"
        self.sales_page = 0
        self.bestseller_page = 0
        self._reload_current_tab()

    def _apply_stock_filters(self):
        self.low_stock_page = 0
        self._reload_current_tab()

    def _apply_expiry_filters(self):
        self.expiring_page = 0
        self._reload_current_tab()

    def _build_filter_field(self, parent, column, label_text, widget, total_columns):
        parent.grid_columnconfigure(column, weight=1 if column < total_columns - 1 else 0)
        ctk.CTkLabel(
            parent,
            text=label_text,
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            text_color=self.c["text_muted"],
        ).grid(row=0, column=column, sticky="w", padx=(0, 12), pady=(0, 6))
        widget.grid(row=1, column=column, sticky="ew", padx=(0, 12))

    def _build_sales_filters(self, parent, include_metric=False):
        c = self.c
        card, body = self._build_card(
            parent,
            "Report Filters",
            "Use the quick date chips for common ranges, or tap Start Date and End Date for a custom touch calendar selection.",
        )
        card.pack(fill="x", pady=(0, 16))

        preset_row = ctk.CTkFrame(body, fg_color="transparent")
        preset_row.pack(fill="x")
        ctk.CTkLabel(
            preset_row,
            text="Quick Range",
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            text_color=c["text_muted"],
        ).pack(anchor="w", pady=(0, 6))
        self._build_date_preset_chips(preset_row)

        form = ctk.CTkFrame(body, fg_color="transparent")
        form.pack(fill="x", pady=(14, 0))
        total_columns = 6 if include_metric else 5

        self._build_touch_date_field(form, "Start Date", "start", 0, total_columns)
        self._build_touch_date_field(form, "End Date", "end", 1, total_columns)

        category = ctk.CTkOptionMenu(
            form,
            values=self.category_options,
            variable=self.category_var,
            fg_color=c["input"],
            button_color=c["border"],
            button_hover_color=c["input"],
            text_color=c["text"],
            dropdown_fg_color=c["card"],
            dropdown_text_color=c["text"],
            width=150,
        )
        self._build_filter_field(form, 2, "Category", category, total_columns)

        group = ctk.CTkOptionMenu(
            form,
            values=["Auto", "Daily", "Weekly", "Monthly"],
            variable=self.group_var,
            fg_color=c["input"],
            button_color=c["border"],
            button_hover_color=c["input"],
            text_color=c["text"],
            dropdown_fg_color=c["card"],
            dropdown_text_color=c["text"],
            width=140,
        )
        self._build_filter_field(form, 3, "Graph Scale", group, total_columns)

        if include_metric:
            metric = ctk.CTkOptionMenu(
                form,
                values=["Quantity", "Revenue"],
                variable=self.best_metric_var,
                fg_color=c["input"],
                button_color=c["border"],
                button_hover_color=c["input"],
                text_color=c["text"],
                dropdown_fg_color=c["card"],
                dropdown_text_color=c["text"],
                width=140,
            )
            self._build_filter_field(form, 4, "Rank By", metric, total_columns)

        action_column = 5 if include_metric else 4
        form.grid_columnconfigure(action_column, weight=0)
        ctk.CTkLabel(
            form,
            text="Actions",
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            text_color=c["text_muted"],
        ).grid(row=0, column=action_column, sticky="w", pady=(0, 6))
        actions = ctk.CTkFrame(form, fg_color="transparent")
        actions.grid(row=1, column=action_column, sticky="w")
        ctk.CTkButton(
            actions,
            text="Search",
            width=86,
            height=36,
            fg_color=AMBER,
            hover_color=AMBER_DARK,
            text_color="#0F0F0F",
            corner_radius=10,
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            command=self._apply_sales_filters,
        ).pack(side="left")
        ctk.CTkButton(
            actions,
            text="Reset",
            width=86,
            height=36,
            fg_color=c["input"],
            hover_color=c["border"],
            text_color=c["text"],
            corner_radius=10,
            font=ctk.CTkFont("Segoe UI", 11),
            command=self._reset_sales_filters,
        ).pack(side="left", padx=(8, 0))

        ctk.CTkLabel(
            body,
            text=f"Current selection: {self._range_preview_text()}  |  {self.category_var.get()}",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=c["text_gray"],
        ).pack(anchor="w", pady=(12, 0))
        ctk.CTkLabel(
            body,
            text="Sales reports only count completed walk-in sales and processed online orders. Pending online orders stay in the POS queue until they are finished.",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=c["text_muted"],
            justify="left",
            wraplength=920,
        ).pack(anchor="w", pady=(8, 0))

    def _build_stock_filters(self, parent):
        c = self.c
        card, body = self._build_card(
            parent,
            "Low Stock Filters",
            "Use the quick chips or tap the dates for a custom range. The queue uses the latest ingredient quantities.",
        )
        card.pack(fill="x", pady=(0, 16))

        preset_row = ctk.CTkFrame(body, fg_color="transparent")
        preset_row.pack(fill="x")
        ctk.CTkLabel(
            preset_row,
            text="Quick Range",
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            text_color=c["text_muted"],
        ).pack(anchor="w", pady=(0, 6))
        self._build_date_preset_chips(preset_row)

        form = ctk.CTkFrame(body, fg_color="transparent")
        form.pack(fill="x", pady=(14, 0))
        total_columns = 4

        self._build_touch_date_field(form, "Start Date", "start", 0, total_columns)
        self._build_touch_date_field(form, "End Date", "end", 1, total_columns)

        group = ctk.CTkOptionMenu(
            form,
            values=["Auto", "Daily", "Weekly", "Monthly"],
            variable=self.group_var,
            fg_color=c["input"],
            button_color=c["border"],
            button_hover_color=c["input"],
            text_color=c["text"],
            dropdown_fg_color=c["card"],
            dropdown_text_color=c["text"],
            width=140,
        )
        self._build_filter_field(form, 2, "Graph Scale", group, total_columns)

        form.grid_columnconfigure(3, weight=0)
        ctk.CTkLabel(
            form,
            text="Actions",
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            text_color=c["text_muted"],
        ).grid(row=0, column=3, sticky="w", pady=(0, 6))
        actions = ctk.CTkFrame(form, fg_color="transparent")
        actions.grid(row=1, column=3, sticky="w")
        ctk.CTkButton(
            actions,
            text="Search",
            width=86,
            height=36,
            fg_color=AMBER,
            hover_color=AMBER_DARK,
            text_color="#0F0F0F",
            corner_radius=10,
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            command=self._apply_stock_filters,
        ).pack(side="left")
        ctk.CTkButton(
            actions,
            text="Reset",
            width=86,
            height=36,
            fg_color=c["input"],
            hover_color=c["border"],
            text_color=c["text"],
            corner_radius=10,
            font=ctk.CTkFont("Segoe UI", 11),
            command=self._reset_stock_filters,
        ).pack(side="left", padx=(8, 0))

        ctk.CTkLabel(
            body,
            text=f"Current range: {self._range_preview_text()}",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=c["text_gray"],
        ).pack(anchor="w", pady=(12, 0))

    def _build_expiry_filters(self, parent):
        c = self.c
        card, body = self._build_card(
            parent,
            "Expiry Window",
            "The graph switches to weekly buckets automatically for wider windows so upcoming expirations stay easy to scan.",
        )
        card.pack(fill="x", pady=(0, 16))

        form = ctk.CTkFrame(body, fg_color="transparent")
        form.pack(fill="x")
        form.grid_columnconfigure(0, weight=1)
        form.grid_columnconfigure(1, weight=0)

        self._build_filter_field(
            form,
            0,
            "Show Items Expiring In",
            ctk.CTkOptionMenu(
                form,
                values=["7 Days", "14 Days", "30 Days"],
                variable=self.expiry_window_var,
                fg_color=c["input"],
                button_color=c["border"],
                button_hover_color=c["input"],
                text_color=c["text"],
                dropdown_fg_color=c["card"],
                dropdown_text_color=c["text"],
                width=180,
            ),
            2,
        )

        ctk.CTkLabel(
            form,
            text="Actions",
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            text_color=c["text_muted"],
        ).grid(row=0, column=1, sticky="w", pady=(0, 6))
        actions = ctk.CTkFrame(form, fg_color="transparent")
        actions.grid(row=1, column=1, sticky="w")
        ctk.CTkButton(
            actions,
            text="Search",
            width=86,
            height=36,
            fg_color=AMBER,
            hover_color=AMBER_DARK,
            text_color="#0F0F0F",
            corner_radius=10,
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            command=self._apply_expiry_filters,
        ).pack(side="left")
        ctk.CTkButton(
            actions,
            text="Reset",
            width=86,
            height=36,
            fg_color=c["input"],
            hover_color=c["border"],
            text_color=c["text"],
            corner_radius=10,
            font=ctk.CTkFont("Segoe UI", 11),
            command=self._reset_expiry_filters,
        ).pack(side="left", padx=(8, 0))

    def _parse_date_value(self, value, field_name):
        try:
            return datetime.strptime(value.strip(), "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValueError(f"{field_name} must use YYYY-MM-DD.") from exc

    def _resolve_selected_range(self):
        start_date = self._parse_date_value(self.start_date_var.get(), "Start date")
        end_date = self._parse_date_value(self.end_date_var.get(), "End date")
        if start_date > end_date:
            raise ValueError("Start date must be earlier than or equal to the end date.")
        return start_date, end_date, self._format_range_label(start_date, end_date)

    def _range_preview_text(self):
        start = self.start_date_var.get().strip() or "YYYY-MM-DD"
        end = self.end_date_var.get().strip() or "YYYY-MM-DD"
        return f"{start} to {end}"

    def _format_range_label(self, start_date, end_date):
        if start_date == end_date:
            return start_date.strftime("%b %d, %Y")
        return f"{start_date.strftime('%b %d, %Y')} to {end_date.strftime('%b %d, %Y')}"

    def _previous_range(self, start_date, end_date):
        days_in_range = (end_date - start_date).days + 1
        previous_end = start_date - timedelta(days=1)
        previous_start = previous_end - timedelta(days=days_in_range - 1)
        return previous_start, previous_end

    def _selected_category(self):
        current = self.category_var.get().strip()
        return None if not current or current == "All Categories" else current

    def _selected_group_key(self):
        return self.group_var.get().strip().lower()

    def _resolve_grouping(self, start_date, end_date):
        selected_group = self._selected_group_key()
        if selected_group != "auto":
            return selected_group, selected_group.capitalize()

        total_days = (end_date - start_date).days + 1
        if total_days <= 45:
            return "daily", "Daily (Auto)"
        if total_days <= 240:
            return "weekly", "Weekly (Auto)"
        return "monthly", "Monthly (Auto)"

    def _selected_metric_key(self):
        return "revenue" if self.best_metric_var.get().strip().lower() == "revenue" else "quantity"

    def _selected_expiry_days(self):
        raw = self.expiry_window_var.get().strip().split()[0]
        return int(raw)

    def _money(self, value):
        return f"PHP {Decimal(str(value)):,.2f}"

    def _receipt_table_label(self, transaction):
        return transaction.customer_number or f"#{transaction.transaction_id}"

    def _compact_value(self, value, money=False):
        number = float(value or 0)
        absolute = abs(number)
        suffix = ""
        if absolute >= 1_000_000:
            number /= 1_000_000
            suffix = "M"
        elif absolute >= 1_000:
            number /= 1_000
            suffix = "K"
        text = f"{number:.1f}{suffix}" if suffix else f"{number:.0f}"
        return f"PHP {text}" if money else text

    def _truncate_label(self, text, limit=14):
        return text if len(text) <= limit else f"{text[:limit - 3]}..."

    def _delta_percent(self, current_value, previous_value):
        current = float(current_value or 0)
        previous = float(previous_value or 0)
        if previous == 0:
            if current == 0:
                return 0.0
            return 100.0
        return ((current - previous) / previous) * 100

    def _delta_style(self, delta):
        if delta > 0.5:
            return "Up", SUCCESS
        if delta < -0.5:
            return "Down", ERROR_RED
        return "Flat", WARNING

    def _trend_caption(self, delta, baseline_text):
        direction, _color = self._delta_style(delta)
        if direction == "Flat":
            return f"Flat vs {baseline_text}"
        return f"{direction} {abs(delta):.1f}% vs {baseline_text}"

    def _bucket_start(self, value, group_by):
        if group_by == "weekly":
            return value - timedelta(days=value.weekday())
        if group_by == "monthly":
            return value.replace(day=1)
        return value

    def _increment_bucket(self, current, group_by):
        if group_by == "weekly":
            return current + timedelta(days=7)
        if group_by == "monthly":
            year = current.year + (1 if current.month == 12 else 0)
            month = 1 if current.month == 12 else current.month + 1
            return current.replace(year=year, month=month, day=1)
        return current + timedelta(days=1)

    def _bucket_label(self, current, group_by):
        if group_by == "weekly":
            return current.strftime("%b %d")
        if group_by == "monthly":
            return current.strftime("%b %Y")
        return current.strftime("%b %d")

    def _fill_trend_points(self, start_date, end_date, group_by, raw_rows):
        point_map = {row["bucket_start"]: row for row in raw_rows}
        cursor = self._bucket_start(start_date, group_by)
        final_bucket = self._bucket_start(end_date, group_by)
        points = []
        while cursor <= final_bucket:
            row = point_map.get(cursor)
            points.append(
                {
                    "label": self._bucket_label(cursor, group_by),
                    "value": float(row["revenue"]) if row else 0.0,
                    "transactions": row["transaction_count"] if row else 0,
                }
            )
            cursor = self._increment_bucket(cursor, group_by)
        return points

    def _draw_line_chart(self, canvas, points, color, money=False, empty_text="No data available."):
        c = self.c
        canvas.delete("all")
        width = max(canvas.winfo_width(), 260)
        height = max(canvas.winfo_height(), CHART_HEIGHT)
        if not points or max(point["value"] for point in points) <= 0:
            canvas.create_text(width / 2, height / 2, text=empty_text, fill=c["text_muted"], font=("Segoe UI", 11))
            return

        left, right, top, bottom = 52, 18, 18, 40
        plot_width = width - left - right
        plot_height = height - top - bottom
        max_value = max(point["value"] for point in points) or 1

        for index in range(4):
            y = top + (plot_height * index / 3)
            value = max_value * (1 - index / 3)
            canvas.create_line(left, y, width - right, y, fill=c["border"], width=1)
            canvas.create_text(
                left - 8,
                y,
                text=self._compact_value(value, money=money),
                fill=c["text_muted"],
                font=("Segoe UI", 9),
                anchor="e",
            )

        x_positions = []
        for index, point in enumerate(points):
            x = left + (plot_width / 2) if len(points) == 1 else left + (plot_width * index / (len(points) - 1))
            y = top + plot_height - ((point["value"] / max_value) * plot_height)
            x_positions.append((x, y, point))

        for index in range(len(x_positions) - 1):
            x1, y1, _point1 = x_positions[index]
            x2, y2, _point2 = x_positions[index + 1]
            canvas.create_line(x1, y1, x2, y2, fill=color, width=3, smooth=True)

        label_step = max(1, len(points) // 6)
        for index, (x, y, point) in enumerate(x_positions):
            canvas.create_oval(x - 4, y - 4, x + 4, y + 4, fill=color, outline=color)
            if index % label_step == 0 or index == len(x_positions) - 1:
                canvas.create_text(
                    x,
                    height - 14,
                    text=self._truncate_label(point["label"], 10),
                    fill=c["text_muted"],
                    font=("Segoe UI", 9),
                )

    def _draw_bar_chart(self, canvas, points, color, money=False, empty_text="No data available."):
        c = self.c
        canvas.delete("all")
        width = max(canvas.winfo_width(), 260)
        height = max(canvas.winfo_height(), CHART_HEIGHT)
        if not points or max(point["value"] for point in points) <= 0:
            canvas.create_text(width / 2, height / 2, text=empty_text, fill=c["text_muted"], font=("Segoe UI", 11))
            return

        left, right, top, bottom = 46, 18, 18, 50
        plot_width = width - left - right
        plot_height = height - top - bottom
        max_value = max(point["value"] for point in points) or 1
        slot_width = plot_width / max(len(points), 1)
        bar_width = min(36, slot_width * 0.62)

        for index in range(4):
            y = top + (plot_height * index / 3)
            value = max_value * (1 - index / 3)
            canvas.create_line(left, y, width - right, y, fill=c["border"], width=1)
            canvas.create_text(
                left - 8,
                y,
                text=self._compact_value(value, money=money),
                fill=c["text_muted"],
                font=("Segoe UI", 9),
                anchor="e",
            )

        for index, point in enumerate(points):
            center_x = left + (slot_width * index) + (slot_width / 2)
            bar_height = (point["value"] / max_value) * plot_height
            x1 = center_x - (bar_width / 2)
            y1 = top + plot_height - bar_height
            x2 = center_x + (bar_width / 2)
            y2 = top + plot_height
            canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline=color, width=0)
            canvas.create_text(
                center_x,
                y1 - 10,
                text=self._compact_value(point["value"], money=money),
                fill=c["text_gray"],
                font=("Segoe UI", 9),
            )
            canvas.create_text(
                center_x,
                height - 18,
                text=self._truncate_label(point["label"], 11),
                fill=c["text_muted"],
                font=("Segoe UI", 9),
            )

    def _schedule_chart_draw(self, canvas, draw_callback):
        pending_job = getattr(canvas, "_chart_redraw_job", None)
        if pending_job:
            canvas.after_cancel(pending_job)
        canvas._chart_redraw_job = canvas.after(24, draw_callback)

    def _mount_line_chart(self, parent, points, color=AMBER, money=False, empty_text="No data available."):
        shell = ctk.CTkFrame(parent, fg_color=self.c["input"], corner_radius=12)
        shell.pack(fill="both", expand=True)
        canvas = tk.Canvas(shell, bg=self.c["input"], highlightthickness=0, bd=0, relief="flat", height=CHART_HEIGHT)
        canvas.pack(fill="both", expand=True, padx=12, pady=12)
        canvas.bind(
            "<Configure>",
            lambda _event: self._schedule_chart_draw(
                canvas,
                lambda: self._draw_line_chart(canvas, points, color=color, money=money, empty_text=empty_text),
            ),
        )
        self._draw_line_chart(canvas, points, color=color, money=money, empty_text=empty_text)

    def _mount_bar_chart(self, parent, points, color=AMBER, money=False, empty_text="No data available."):
        shell = ctk.CTkFrame(parent, fg_color=self.c["input"], corner_radius=12)
        shell.pack(fill="both", expand=True)
        canvas = tk.Canvas(shell, bg=self.c["input"], highlightthickness=0, bd=0, relief="flat", height=CHART_HEIGHT)
        canvas.pack(fill="both", expand=True, padx=12, pady=12)
        canvas.bind(
            "<Configure>",
            lambda _event: self._schedule_chart_draw(
                canvas,
                lambda: self._draw_bar_chart(canvas, points, color=color, money=money, empty_text=empty_text),
            ),
        )
        self._draw_bar_chart(canvas, points, color=color, money=money, empty_text=empty_text)

    def _show_sales(self):
        self._build_sales_filters(self.content)
        report_body = ctk.CTkFrame(self.content, fg_color="transparent")
        report_body.pack(fill="both", expand=True)
        self.sales_report_host = report_body
        self.sales_table_host = None
        self._show_loading(report_body, "Loading sales summary...")
        self._run_async(
            "sales",
            self._fetch_sales_report,
            lambda data: self._render_sales(report_body, data),
            lambda error: self._show_error(report_body, error),
        )

    def _fetch_sales_report(self):
        start_date, end_date, range_label = self._resolve_selected_range()
        category = self._selected_category()
        group_by, group_label = self._resolve_grouping(start_date, end_date)
        previous_start, previous_end = self._previous_range(start_date, end_date)
        requested_page = max(self.sales_page, 0)
        requested_offset = requested_page * SALES_PAGE_SIZE
        tasks = {
            "summary": lambda: TransactionDB.get_sales_summary(start_date, end_date, category=category),
            "previous_summary": lambda: TransactionDB.get_sales_summary(
                previous_start,
                previous_end,
                category=category,
            ),
            "trend_rows": lambda: TransactionDB.get_sales_trend(
                start_date,
                end_date,
                group_by=group_by,
                category=category,
            ),
            "best_sellers": lambda: TransactionDB.get_best_sellers(
                limit=6,
                start_date=start_date,
                end_date=end_date,
                category=category,
                sort_by="quantity",
            ),
            "total_transactions": lambda: TransactionDB.get_report_transaction_count(
                start_date,
                end_date,
                category=category,
            ),
            "transactions": lambda: TransactionDB.get_report_transactions(
                start_date,
                end_date,
                category=category,
                limit=SALES_PAGE_SIZE,
                offset=requested_offset,
                include_items=False,
                sort_key=self.sales_sort_key,
                sort_direction=self.sales_sort_direction,
            ),
        }
        if category is None:
            tasks["category_breakdown"] = lambda: TransactionDB.get_category_sales(start_date, end_date, limit=6)

        fetched = self._fetch_parallel(tasks)
        summary = fetched["summary"]
        previous_summary = fetched["previous_summary"]
        trend_rows = fetched["trend_rows"]
        best_sellers = fetched["best_sellers"]
        category_breakdown = fetched.get("category_breakdown") or []
        total_transactions = fetched["total_transactions"]
        page, page_count = self._resolved_sales_page(total_transactions)
        transactions = fetched["transactions"]
        if page != requested_page:
            transactions = TransactionDB.get_report_transactions(
                start_date,
                end_date,
                category=category,
                limit=SALES_PAGE_SIZE,
                offset=page * SALES_PAGE_SIZE,
                include_items=False,
                sort_key=self.sales_sort_key,
                sort_direction=self.sales_sort_direction,
            )
        average_sale = summary["revenue"] / summary["transaction_count"] if summary["transaction_count"] else Decimal("0")
        revenue_delta = self._delta_percent(summary["revenue"], previous_summary["revenue"])
        transaction_delta = self._delta_percent(summary["transaction_count"], previous_summary["transaction_count"])

        if category_breakdown:
            breakdown_points = [{"label": item["category"], "value": float(item["sales_total"])} for item in category_breakdown]
            breakdown_title = "Sales by Category"
            breakdown_subtitle = "Revenue share for the selected date range."
        else:
            breakdown_points = [{"label": item["product_name"], "value": float(item["sales_total"])} for item in best_sellers]
            breakdown_title = "Top Products"
            breakdown_subtitle = "Highest earning products for the selected filters."

        return {
            "range_label": range_label,
            "category_label": category or "All Categories",
            "group_label": group_label,
            "summary": summary,
            "previous_summary": previous_summary,
            "average_sale": average_sale,
            "revenue_delta": revenue_delta,
            "transaction_delta": transaction_delta,
            "trend_points": self._fill_trend_points(start_date, end_date, group_by, trend_rows),
            "breakdown_title": breakdown_title,
            "breakdown_subtitle": breakdown_subtitle,
            "breakdown_points": breakdown_points,
            "transactions": transactions,
            "sort_caption": self._sales_sort_caption(),
            "transaction_total_count": total_transactions,
            "sales_page": page,
            "sales_page_count": page_count,
        }

    def _render_sales(self, parent, data):
        for widget in parent.winfo_children():
            widget.destroy()
        self.sales_page = data["sales_page"]
        self.sales_total_count = data["transaction_total_count"]

        cards = ctk.CTkFrame(parent, fg_color="transparent")
        cards.pack(fill="x", pady=(0, 16))
        for column in range(4):
            cards.grid_columnconfigure(column, weight=1)

        revenue_direction, revenue_color = self._delta_style(data["revenue_delta"])
        metric_cards = [
            ("Revenue", self._money(data["summary"]["revenue"]), f"{data['range_label']} | {data['category_label']}", SUCCESS),
            ("Transactions", str(data["summary"]["transaction_count"]), self._trend_caption(data["transaction_delta"], "the previous range"), AMBER),
            ("Average Sale", self._money(data["average_sale"]), f"Viewed by {data['group_label']}", BLUE),
            (
                "Sales Direction",
                f"{revenue_direction} {abs(data['revenue_delta']):.1f}%" if revenue_direction != "Flat" else "Flat",
                self._trend_caption(data["revenue_delta"], "the previous range"),
                revenue_color,
            ),
        ]
        for index, (title, value, caption, accent) in enumerate(metric_cards):
            card = self._build_metric_card(cards, title, value, caption, accent)
            card.grid(row=0, column=index, padx=6, sticky="nsew")

        chart_row = ctk.CTkFrame(parent, fg_color="transparent")
        chart_row.pack(fill="x", pady=(0, 16))
        chart_row.grid_columnconfigure(0, weight=3)
        chart_row.grid_columnconfigure(1, weight=2)

        trend_card, trend_body = self._build_card(
            chart_row,
            "Sales Trend",
            f"{data['group_label']} performance across {data['range_label']}.",
        )
        trend_card.grid(row=0, column=0, padx=(0, 8), sticky="nsew")
        self._mount_line_chart(
            trend_body,
            data["trend_points"],
            color=AMBER,
            money=True,
            empty_text="No sales recorded for the selected filters.",
        )

        mix_card, mix_body = self._build_card(chart_row, data["breakdown_title"], data["breakdown_subtitle"])
        mix_card.grid(row=0, column=1, padx=(8, 0), sticky="nsew")
        self._mount_bar_chart(
            mix_body,
            data["breakdown_points"],
            color=BLUE,
            money=True,
            empty_text="No breakdown data is available for this selection.",
        )

        table_host = ctk.CTkFrame(parent, fg_color="transparent")
        table_host.pack(fill="x", pady=(0, 16))
        self.sales_table_host = table_host
        self._render_sales_table_section(table_host, data)

    def _render_sales_table_section(self, host, data):
        for widget in host.winfo_children():
            widget.destroy()
        self.sales_page = data["sales_page"]
        self.sales_total_count = data["transaction_total_count"]

        table_card, table_body = self._build_card(
            host,
            "Sales List",
            f"{data['sort_caption']}. Click a sale row to view the full transaction details. "
            "Voided receipts stay visible here for audit history.",
        )
        table_card.pack(fill="x")
        total_count = data["transaction_total_count"]
        page = data["sales_page"]
        page_count = data["sales_page_count"]
        if total_count > 0:
            range_start = (page * SALES_PAGE_SIZE) + 1
            range_end = min(total_count, range_start + len(data["transactions"]) - 1)
            ctk.CTkLabel(
                table_body,
                text=f"Showing {range_start}-{range_end} of {total_count} matching transactions.",
                font=ctk.CTkFont("Segoe UI", 11),
                text_color=self.c["text_muted"],
            ).pack(anchor="w", pady=(0, 10))
        self._render_transaction_table(table_body, data["transactions"])
        self._render_pagination_footer(
            table_body,
            "sales",
            page,
            page_count,
            total_count,
            len(data["transactions"]),
            self._change_sales_page,
        )

    def _fetch_sales_table_data(self):
        start_date, end_date, _range_label = self._resolve_selected_range()
        category = self._selected_category()
        requested_page = max(self.sales_page, 0)
        requested_offset = requested_page * SALES_PAGE_SIZE
        fetched = self._fetch_parallel(
            {
                "total_transactions": lambda: TransactionDB.get_report_transaction_count(
                    start_date,
                    end_date,
                    category=category,
                ),
                "transactions": lambda: TransactionDB.get_report_transactions(
                    start_date,
                    end_date,
                    category=category,
                    limit=SALES_PAGE_SIZE,
                    offset=requested_offset,
                    include_items=False,
                    sort_key=self.sales_sort_key,
                    sort_direction=self.sales_sort_direction,
                ),
            }
        )
        total_transactions = fetched["total_transactions"]
        page, page_count = self._resolved_sales_page(total_transactions)
        transactions = fetched["transactions"]
        if page != requested_page:
            transactions = TransactionDB.get_report_transactions(
                start_date,
                end_date,
                category=category,
                limit=SALES_PAGE_SIZE,
                offset=page * SALES_PAGE_SIZE,
                include_items=False,
                sort_key=self.sales_sort_key,
                sort_direction=self.sales_sort_direction,
            )
        return {
            "transactions": transactions,
            "sort_caption": self._sales_sort_caption(),
            "transaction_total_count": total_transactions,
            "sales_page": page,
            "sales_page_count": page_count,
        }

    def _refresh_sales_table_only(self, message="Sorting sales list..."):
        if self.sales_table_host is None or not self.sales_table_host.winfo_exists():
            self._reload_current_tab()
            return

        self._show_loading(self.sales_table_host, message)
        self._run_async(
            "sales",
            self._fetch_sales_table_data,
            lambda data, host=self.sales_table_host: self._render_sales_table_section(host, data),
            lambda error, host=self.sales_table_host: self._show_error(host, error),
        )

    def _render_transaction_table(self, parent, transactions):
        c = self.c
        if not transactions:
            ctk.CTkLabel(
                parent,
                text="No sales matched the current filters.",
                font=ctk.CTkFont("Segoe UI", 12),
                text_color=c["text_muted"],
            ).pack(anchor="w", pady=8)
            return

        header = ctk.CTkFrame(parent, fg_color=c["thead"], corner_radius=10)
        header.pack(fill="x", pady=(0, 6))
        columns = [
            ("Receipt", "receipt", 1),
            ("Date", "date", 2),
            ("Payment", "payment", 1),
            ("Status", "status", 1),
            ("Total", "total", 1),
        ]
        for index, (label, sort_key, weight) in enumerate(columns):
            header.grid_columnconfigure(index, weight=weight)
            is_active = sort_key == self.sales_sort_key
            ctk.CTkButton(
                header,
                text=f"{label}{self._sales_sort_indicator(sort_key)}",
                font=ctk.CTkFont("Segoe UI", 11, "bold"),
                fg_color="transparent",
                hover_color=c["input"],
                text_color=AMBER if is_active else c["text_muted"],
                corner_radius=8,
                anchor="w",
                command=lambda selected=sort_key: self._set_sales_sort(selected),
            ).grid(row=0, column=index, sticky="ew", padx=8, pady=8)

        for index, transaction in enumerate(transactions):
            base_color = c["input"] if index % 2 == 0 else c["row_alt"]
            row = ctk.CTkFrame(parent, fg_color=base_color, corner_radius=10)
            row.pack(fill="x", pady=2)
            for column, weight in enumerate([1, 2, 1, 1, 1]):
                row.grid_columnconfigure(column, weight=weight)

            def activate(_event, tx_id=transaction.transaction_id):
                self._open_sales_transaction_details(tx_id)

            def on_enter(_event, target=row):
                target.configure(fg_color=c["border"])

            def on_leave(_event, target=row, color=base_color):
                target.configure(fg_color=color)

            row.bind("<Button-1>", activate)
            row.bind("<Enter>", on_enter)
            row.bind("<Leave>", on_leave)

            status_text = "VOIDED" if transaction.is_voided else "COMPLETED"
            status_color = ERROR_RED if transaction.is_voided else SUCCESS
            receipt_label = self._receipt_table_label(transaction)
            values = [
                (receipt_label, ERROR_RED if transaction.is_voided else AMBER),
                (str(transaction.date)[:19], c["text_gray"]),
                (((transaction.payment_method or "Unspecified").strip() or "Unspecified").title(), c["text_gray"]),
                (status_text, status_color),
                (self._money(transaction.get_total()), c["text"]),
            ]
            for column, (value, text_color) in enumerate(values):
                label = ctk.CTkLabel(
                    row,
                    text=value,
                    font=ctk.CTkFont("Segoe UI", 12, "bold" if column in {0, 3, 4} else "normal"),
                    text_color=text_color,
                    anchor="w",
                )
                label.grid(row=0, column=column, sticky="ew", padx=12, pady=10)
                label.bind("<Button-1>", activate)
                label.bind("<Enter>", on_enter)
                label.bind("<Leave>", on_leave)

    def _open_sales_transaction_details(self, transaction_id):
        transaction = TransactionDB.get_transaction_by_id(transaction_id, include_items=True)
        if transaction is None:
            self._show_sales_details_error(f"Transaction #{transaction_id} was not found.")
            return
        receipt_label = transaction.customer_number or f"#{transaction.transaction_id}"

        if self.sales_details_popup is not None and self.sales_details_popup.winfo_exists():
            self.sales_details_popup.destroy()

        c = self.c
        popup = ctk.CTkToplevel(self)
        popup.title(f"Sale Details {receipt_label}")
        popup.geometry("780x720")
        popup.minsize(680, 560)
        popup.configure(fg_color=c["bg"])
        popup.transient(self.winfo_toplevel())
        popup.grab_set()
        popup.protocol("WM_DELETE_WINDOW", lambda: self._close_sales_details_popup(popup))
        self.sales_details_popup = popup

        shell = ctk.CTkFrame(popup, fg_color="transparent")
        shell.pack(fill="both", expand=True, padx=20, pady=18)

        header = ctk.CTkFrame(shell, fg_color="transparent")
        header.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(
            header,
            text=f"Sale Details {receipt_label}",
            font=ctk.CTkFont("Georgia", 22, "bold"),
            text_color=c["text"],
        ).pack(side="left")
        ctk.CTkButton(
            header,
            text="Close",
            width=88,
            height=36,
            fg_color=c["input"],
            hover_color=c["border"],
            text_color=c["text"],
            corner_radius=10,
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            command=lambda: self._close_sales_details_popup(popup),
        ).pack(side="right")

        content = ctk.CTkScrollableFrame(shell, fg_color="transparent")
        content.pack(fill="both", expand=True)

        summary_card, summary_body = self._build_card(
            content,
            "Transaction Summary",
            "This detail view is loaded from the saved transaction record in the backend.",
        )
        summary_card.pack(fill="x", pady=(0, 12))

        status_text = "VOIDED" if transaction.is_voided else "COMPLETED"
        summary_rows = [
            ("Receipt Number", receipt_label),
            ("Internal Transaction ID", f"#{transaction.transaction_id}"),
            ("Date", str(transaction.date)[:19]),
            ("Cashier", transaction.cashier_name or "-"),
            ("Service Mode", transaction.service_mode or "-"),
            ("Order Source", transaction.order_source or "-"),
            ("Payment Method", transaction.payment_method or "-"),
            ("Total", self._money(transaction.get_total())),
            ("Customer Paid", self._money(transaction.amount_paid)),
            ("Change", self._money(transaction.get_change())),
            ("Status", status_text),
        ]
        pickup_text = ""
        if getattr(transaction, "pickup_date_from", None) or getattr(transaction, "pickup_date_to", None):
            pickup_from = getattr(transaction, "pickup_date_from", None) or "-"
            pickup_to = getattr(transaction, "pickup_date_to", None) or pickup_from
            pickup_text = f"{pickup_from} to {pickup_to}" if pickup_from != pickup_to else str(pickup_from)
        if pickup_text:
            summary_rows.insert(6, ("Pickup", pickup_text))

        for label_text, value in summary_rows:
            row = ctk.CTkFrame(summary_body, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(
                row,
                text=label_text,
                font=ctk.CTkFont("Segoe UI", 11, "bold"),
                text_color=c["text_muted"],
                anchor="w",
            ).pack(side="left")
            ctk.CTkLabel(
                row,
                text=str(value),
                font=ctk.CTkFont("Segoe UI", 11),
                text_color=c["text"],
                anchor="e",
            ).pack(side="right")

        items_card, items_body = self._build_card(
            content,
            "Items",
            "Each row shows the saved sale snapshot for that item. Click an item to view its product details.",
        )
        items_card.pack(fill="x", pady=(0, 12))

        if not transaction.items:
            ctk.CTkLabel(
                items_body,
                text="No items were stored for this transaction.",
                font=ctk.CTkFont("Segoe UI", 12),
                text_color=c["text_muted"],
            ).pack(anchor="w", pady=8)
        else:
            for index, item in enumerate(transaction.items):
                saved_name = item.get("saved_product_name") or item["product"].name
                saved_unit_price = item.get("saved_unit_price", item["product"].price)
                current_name = item["product"].name
                item_row = ctk.CTkFrame(
                    items_body,
                    fg_color=c["input"],
                    corner_radius=10,
                    border_width=1,
                    border_color=c["border"],
                )
                item_row.pack(fill="x", pady=(0, 8))

                def open_product(
                    _event,
                    product_id=item["product"].product_id,
                    product=item["product"],
                    quantity=item["quantity"],
                    subtotal=item["subtotal"],
                    snapshot_name=saved_name,
                    snapshot_price=saved_unit_price,
                ):
                    self._open_product_details_popup(
                        product_id=product_id,
                        fallback_name=product.name,
                        fallback_category=product.category,
                        source_title="Sale Item Details",
                        source_note="This product detail view combines the current product record with the clicked sale item snapshot.",
                        extra_rows=[
                            ("Saved Product Name", snapshot_name),
                            ("Sale Quantity", str(quantity)),
                            ("Saved Unit Price", self._money(snapshot_price)),
                            ("Sale Subtotal", self._money(subtotal)),
                        ],
                    )

                def on_item_enter(_event, target=item_row):
                    target.configure(fg_color=c["border"])

                def on_item_leave(_event, target=item_row):
                    target.configure(fg_color=c["input"])

                item_row.bind("<Button-1>", open_product)
                item_row.bind("<Enter>", on_item_enter)
                item_row.bind("<Leave>", on_item_leave)

                def bind_item_widget(widget):
                    widget.bind("<Button-1>", open_product)
                    widget.bind("<Enter>", on_item_enter)
                    widget.bind("<Leave>", on_item_leave)

                header_row = ctk.CTkFrame(item_row, fg_color="transparent")
                header_row.pack(fill="x", padx=12, pady=(10, 4))
                header_label = ctk.CTkLabel(
                    header_row,
                    text=f"Item {index + 1}: {saved_name}",
                    font=ctk.CTkFont("Segoe UI", 12, "bold"),
                    text_color=c["text"],
                    anchor="w",
                )
                header_label.pack(side="left", fill="x", expand=True)
                total_label = ctk.CTkLabel(
                    header_row,
                    text=self._money(item["subtotal"]),
                    font=ctk.CTkFont("Segoe UI", 11, "bold"),
                    text_color=AMBER,
                    anchor="e",
                )
                total_label.pack(side="right")
                bind_item_widget(header_row)
                bind_item_widget(header_label)
                bind_item_widget(total_label)

                detail_rows = [
                    ("Category", item["product"].category or "-"),
                    ("Quantity", str(item["quantity"])),
                    ("Saved Unit Price", self._money(saved_unit_price)),
                    ("Line Total", self._money(item["subtotal"])),
                ]
                if current_name and current_name != saved_name:
                    detail_rows.insert(1, ("Current Catalog Name", current_name))

                for label_text, value_text in detail_rows:
                    detail_row = ctk.CTkFrame(item_row, fg_color="transparent")
                    detail_row.pack(fill="x", padx=12, pady=1)
                    key_label = ctk.CTkLabel(
                        detail_row,
                        text=label_text,
                        font=ctk.CTkFont("Segoe UI", 10, "bold"),
                        text_color=c["text_muted"],
                        anchor="w",
                    )
                    key_label.pack(side="left")
                    value_label = ctk.CTkLabel(
                        detail_row,
                        text=str(value_text),
                        font=ctk.CTkFont("Segoe UI", 10),
                        text_color=c["text"],
                        anchor="e",
                    )
                    value_label.pack(side="right")
                    bind_item_widget(detail_row)
                    bind_item_widget(key_label)
                    bind_item_widget(value_label)

                click_hint = ctk.CTkLabel(
                    item_row,
                    text="Click to open product details",
                    font=ctk.CTkFont("Segoe UI", 10),
                    text_color=c["text_muted"],
                    anchor="w",
                )
                click_hint.pack(fill="x", padx=12, pady=(6, 10))
                bind_item_widget(click_hint)

        totals_card, totals_body = self._build_card(
            content,
            "Payment Totals",
            "Saved payment values for this transaction.",
        )
        totals_card.pack(fill="x")
        for label_text, value, color in [
            ("Total", self._money(transaction.get_total()), AMBER),
            ("Customer Paid", self._money(transaction.amount_paid), c["text"]),
            ("Change", self._money(transaction.get_change()), c["text"]),
        ]:
            row = ctk.CTkFrame(totals_body, fg_color="transparent")
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(
                row,
                text=label_text,
                font=ctk.CTkFont("Segoe UI", 11, "bold"),
                text_color=AMBER if label_text == "Total" else c["text_muted"],
            ).pack(side="left")
            ctk.CTkLabel(
                row,
                text=str(value),
                font=ctk.CTkFont("Segoe UI", 11, "bold" if label_text == "Total" else "normal"),
                text_color=color,
            ).pack(side="right")

    def _show_sales_details_error(self, message):
        if self.sales_details_popup is not None and self.sales_details_popup.winfo_exists():
            self.sales_details_popup.destroy()

        popup = ctk.CTkToplevel(self)
        popup.title("Sale Details")
        popup.geometry("420x180")
        popup.configure(fg_color=self.c["bg"])
        popup.transient(self.winfo_toplevel())
        popup.grab_set()
        popup.protocol("WM_DELETE_WINDOW", lambda: self._close_sales_details_popup(popup))
        self.sales_details_popup = popup

        card, body = self._build_card(popup, "Sale Details", "")
        card.pack(fill="both", expand=True, padx=18, pady=18)
        ctk.CTkLabel(
            body,
            text=message,
            font=ctk.CTkFont("Segoe UI", 12),
            text_color=ERROR_RED,
            justify="left",
            wraplength=340,
        ).pack(anchor="w", pady=(0, 12))
        ctk.CTkButton(
            body,
            text="Close",
            width=88,
            height=36,
            fg_color=self.c["input"],
            hover_color=self.c["border"],
            text_color=self.c["text"],
            corner_radius=10,
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            command=lambda: self._close_sales_details_popup(popup),
        ).pack(anchor="e")

    def _close_sales_details_popup(self, popup):
        if popup is not None and popup.winfo_exists():
            popup.destroy()
        self.sales_details_popup = None

    def _open_product_details_popup(
        self,
        product_id=None,
        fallback_name="Unknown Product",
        fallback_category="-",
        source_title="Product Details",
        source_note="This product detail view is loaded from the report selection.",
        extra_rows=None,
    ):
        product = ProductDB.get_product(product_id) if product_id else None
        if self.product_details_popup is not None and self.product_details_popup.winfo_exists():
            self.product_details_popup.destroy()

        c = self.c
        display_name = product.name if product is not None else fallback_name
        display_category = product.category if product is not None else (fallback_category or "-")
        display_id = product.product_id if product is not None else (product_id if product_id is not None else "-")
        display_price = self._money(product.price) if product is not None else "-"
        display_shelf_life = str(product.shelf_life_days) if product is not None else "-"

        popup = ctk.CTkToplevel(self)
        popup.title(display_name)
        popup.geometry("560x460")
        popup.minsize(500, 420)
        popup.configure(fg_color=c["bg"])
        popup.transient(self.winfo_toplevel())
        popup.grab_set()
        popup.protocol("WM_DELETE_WINDOW", lambda: self._close_product_details_popup(popup))
        self.product_details_popup = popup

        shell = ctk.CTkFrame(popup, fg_color="transparent")
        shell.pack(fill="both", expand=True, padx=20, pady=18)

        header = ctk.CTkFrame(shell, fg_color="transparent")
        header.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(
            header,
            text=source_title,
            font=ctk.CTkFont("Georgia", 22, "bold"),
            text_color=c["text"],
        ).pack(side="left")
        ctk.CTkButton(
            header,
            text="Close",
            width=88,
            height=36,
            fg_color=c["input"],
            hover_color=c["border"],
            text_color=c["text"],
            corner_radius=10,
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            command=lambda: self._close_product_details_popup(popup),
        ).pack(side="right")

        summary_card, summary_body = self._build_card(
            shell,
            display_name,
            source_note,
        )
        summary_card.pack(fill="x", pady=(0, 12))

        summary_rows = [
            ("Product ID", str(display_id)),
            ("Name", display_name),
            ("Category", display_category),
            ("Current Price", display_price),
            ("Shelf Life (Days)", display_shelf_life),
            ("Catalog Status", "Active Product" if product is not None else "Not currently in the catalog"),
        ]
        if extra_rows:
            summary_rows.extend(extra_rows)

        for label_text, value in summary_rows:
            row = ctk.CTkFrame(summary_body, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(
                row,
                text=label_text,
                font=ctk.CTkFont("Segoe UI", 11, "bold"),
                text_color=c["text_muted"],
                anchor="w",
            ).pack(side="left")
            ctk.CTkLabel(
                row,
                text=str(value),
                font=ctk.CTkFont("Segoe UI", 11),
                text_color=c["text"],
                anchor="e",
            ).pack(side="right")

        note_card, note_body = self._build_card(
            shell,
            "Report Context",
            "These details come from the report selection and the current product table.",
        )
        note_card.pack(fill="both", expand=True)
        note_text = (
            "The clicked report row is now linked to the product details view. "
            "If the product still exists in the catalog, the current product record is shown here. "
            "If it was removed later, the report still opens using the saved fallback values."
        )
        ctk.CTkLabel(
            note_body,
            text=note_text,
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=c["text_gray"],
            justify="left",
            wraplength=460,
        ).pack(anchor="w")

    def _close_product_details_popup(self, popup):
        if popup is not None and popup.winfo_exists():
            popup.destroy()
        self.product_details_popup = None

    def _show_bestsellers(self):
        self._build_sales_filters(self.content, include_metric=True)
        report_body = ctk.CTkFrame(self.content, fg_color="transparent")
        report_body.pack(fill="both", expand=True)
        self.bestseller_list_host = None
        self._show_loading(report_body, "Loading best sellers...")
        self._run_async(
            "bestsellers",
            self._fetch_bestseller_report,
            lambda data: self._render_bestsellers(report_body, data),
            lambda error: self._show_error(report_body, error),
        )

    def _fetch_bestseller_report(self):
        start_date, end_date, range_label = self._resolve_selected_range()
        category = self._selected_category()
        group_by, group_label = self._resolve_grouping(start_date, end_date)
        metric = self._selected_metric_key()
        fetched = self._fetch_parallel(
            {
                "summary": lambda: TransactionDB.get_sales_summary(start_date, end_date, category=category),
                "ranked": lambda: TransactionDB.get_best_sellers(
                    limit=None,
                    start_date=start_date,
                    end_date=end_date,
                    category=category,
                    sort_by=metric,
                ),
                "trend_rows": lambda: TransactionDB.get_sales_trend(
                    start_date,
                    end_date,
                    group_by=group_by,
                    category=category,
                ),
            }
        )
        summary = fetched["summary"]
        ranked = fetched["ranked"]
        trend_rows = fetched["trend_rows"]
        leader = ranked[0] if ranked else None
        ranked_rows, page, page_count, total_count = self._slice_page_rows(ranked, self.bestseller_page)
        return {
            "range_label": range_label,
            "category_label": category or "All Categories",
            "group_label": group_label,
            "metric_label": self.best_metric_var.get(),
            "summary": summary,
            "ranked": ranked,
            "ranked_rows": ranked_rows,
            "leader": leader,
            "trend_points": self._fill_trend_points(start_date, end_date, group_by, trend_rows),
            "chart_points": [
                {"label": item["product_name"], "value": float(item["sales_total"] if metric == "revenue" else item["quantity_sold"])}
                for item in ranked[:6]
            ],
            "bestseller_page": page,
            "bestseller_page_count": page_count,
            "bestseller_total_count": total_count,
        }

    def _render_bestsellers(self, parent, data):
        for widget in parent.winfo_children():
            widget.destroy()
        self.bestseller_data_cache = data
        self.bestseller_page = data["bestseller_page"]

        cards = ctk.CTkFrame(parent, fg_color="transparent")
        cards.pack(fill="x", pady=(0, 16))
        for column in range(4):
            cards.grid_columnconfigure(column, weight=1)

        leader = data["leader"]
        lead_name = leader["product_name"] if leader else "No item sales yet"
        lead_quantity = f"{leader['quantity_sold']} sold" if leader else "0 sold"
        lead_revenue = self._money(leader["sales_total"]) if leader else self._money(0)
        metric_cards = [
            ("Lead Product", lead_name, "Same range and category filters as Sales Summary.", AMBER),
            ("Units Sold", lead_quantity, data["range_label"], BLUE),
            ("Lead Revenue", lead_revenue, data["category_label"], SUCCESS),
            ("Ranked By", data["metric_label"], "Switch between quantity and revenue from the filter bar.", WARNING),
        ]
        for index, (title, value, caption, accent) in enumerate(metric_cards):
            card = self._build_metric_card(cards, title, value, caption, accent)
            card.grid(row=0, column=index, padx=6, sticky="nsew")

        chart_row = ctk.CTkFrame(parent, fg_color="transparent")
        chart_row.pack(fill="x", pady=(0, 16))
        chart_row.grid_columnconfigure(0, weight=2)
        chart_row.grid_columnconfigure(1, weight=3)

        ranking_card, ranking_body = self._build_card(
            chart_row,
            "Best Seller Graph",
            f"Top products by {data['metric_label'].lower()} for {data['range_label']}.",
        )
        ranking_card.grid(row=0, column=0, padx=(0, 8), sticky="nsew")
        self._mount_bar_chart(
            ranking_body,
            data["chart_points"],
            color=AMBER,
            money=data["metric_label"] == "Revenue",
            empty_text="No ranked products are available for this range.",
        )

        linked_card, linked_body = self._build_card(
            chart_row,
            "Linked Sales Trend",
            f"This trend follows the searched range using {data['group_label'].lower()} buckets.",
        )
        linked_card.grid(row=0, column=1, padx=(8, 0), sticky="nsew")
        self._mount_line_chart(
            linked_body,
            data["trend_points"],
            color=BLUE,
            money=True,
            empty_text="No sales trend data is available for this selection.",
        )

        list_card, list_body = self._build_card(
            parent,
            "Best Seller List",
            "Products are ranked from highest to lowest based on your selected ranking metric. Click a product row to view its details.",
        )
        list_card.pack(fill="x", pady=(0, 16))
        self.bestseller_list_host = list_body

        if not data["ranked"]:
            message = "No item-level sales were found for the current range."
            if data["summary"]["transaction_count"] > 0:
                message = (
                    "Sales exist in this range, but best seller rankings need transaction line items. "
                    "New POS transactions saved in this build will populate this section."
                )
            ctk.CTkLabel(
                list_body,
                text=message,
                font=ctk.CTkFont("Segoe UI", 12),
                text_color=WARNING,
                justify="left",
                wraplength=860,
            ).pack(anchor="w", pady=8)
            return

        self._render_bestseller_list_section(list_body, data)

    def _rerender_bestseller_list(self):
        if (
            self.active_tab.get() != "bestsellers"
            or self.bestseller_list_host is None
            or not self.bestseller_list_host.winfo_exists()
            or not self.bestseller_data_cache
        ):
            self._reload_current_tab()
            return
        self._render_bestseller_list_section(self.bestseller_list_host, self.bestseller_data_cache)

    def _change_bestseller_page(self, step):
        if not self.bestseller_data_cache:
            return
        page_count = self.bestseller_data_cache.get("bestseller_page_count", 1)
        next_page = min(max(self.bestseller_page + step, 0), page_count - 1)
        if next_page == self.bestseller_page:
            return
        self.bestseller_page = next_page
        self._rerender_bestseller_list()

    def _render_bestseller_list_section(self, parent, data):
        for widget in parent.winfo_children():
            widget.destroy()

        ranked_rows, page, page_count, total_count = self._slice_page_rows(data["ranked"], self.bestseller_page)
        self.bestseller_page = page
        data["ranked_rows"] = ranked_rows
        data["bestseller_page"] = page
        data["bestseller_page_count"] = page_count
        data["bestseller_total_count"] = total_count

        self._render_bestseller_table(parent, ranked_rows, rank_offset=page * SALES_PAGE_SIZE)
        self._render_pagination_footer(
            parent,
            "bestsellers",
            page,
            page_count,
            total_count,
            len(ranked_rows),
            self._change_bestseller_page,
        )

    def _render_bestseller_table(self, parent, ranked, rank_offset=0):
        c = self.c
        header = ctk.CTkFrame(parent, fg_color=c["thead"], corner_radius=10)
        header.pack(fill="x", pady=(0, 6))
        columns = [("Rank", 1), ("Product", 3), ("Category", 2), ("Units", 1), ("Revenue", 1)]
        for index, (label, weight) in enumerate(columns):
            header.grid_columnconfigure(index, weight=weight)
            ctk.CTkLabel(
                header,
                text=label,
                font=ctk.CTkFont("Segoe UI", 11, "bold"),
                text_color=c["text_muted"],
                anchor="w",
            ).grid(row=0, column=index, sticky="ew", padx=12, pady=10)

        for index, item in enumerate(ranked, start=1):
            row = ctk.CTkFrame(parent, fg_color=c["input"] if index % 2 else c["row_alt"], corner_radius=10)
            row.pack(fill="x", pady=2)
            for column, weight in enumerate([1, 3, 2, 1, 1]):
                row.grid_columnconfigure(column, weight=weight)
            values = [
                (f"#{rank_offset + index}", AMBER),
                (item["product_name"], c["text"]),
                (item["category"], c["text_gray"]),
                (str(item["quantity_sold"]), c["text_gray"]),
                (self._money(item["sales_total"]), c["text"]),
            ]
            for column, (value, text_color) in enumerate(values):
                ctk.CTkLabel(
                    row,
                    text=value,
                    font=ctk.CTkFont("Segoe UI", 12, "bold" if column in {0, 1, 4} else "normal"),
                    text_color=text_color,
                    anchor="w",
                ).grid(row=0, column=column, sticky="ew", padx=12, pady=10)

    def _show_low_stock(self):
        self._build_stock_filters(self.content)
        info_card, info_body = self._build_card(
            self.content,
            "Current Stock Snapshot",
            "This tab reads the ingredient table and never writes to stock from the report.",
        )
        info_card.pack(fill="x", pady=(0, 16))
        ctk.CTkLabel(
            info_body,
            text="The queue below shows ingredients at or below reorder level using the latest saved quantities.",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=self.c["text_gray"],
            justify="left",
            wraplength=860,
        ).pack(anchor="w")

        report_body = ctk.CTkFrame(self.content, fg_color="transparent")
        report_body.pack(fill="both", expand=True)
        self.low_stock_list_host = None
        self._show_loading(report_body, "Loading low stock report...")
        self._run_async(
            "lowstock",
            self._fetch_low_stock_report,
            lambda data: self._render_low_stock(report_body, data),
            lambda error: self._show_error(report_body, error),
        )

    def _fetch_low_stock_report(self):
        start_date, end_date, range_label = self._resolve_selected_range()
        group_by, group_label = self._resolve_grouping(start_date, end_date)
        summary = IngredientDB.get_low_stock_history_report(start_date, end_date, group_by=group_by)
        summary.update(
            {
                "range_label": range_label,
                "group_label": group_label,
            }
        )
        return summary

    def _render_low_stock(self, parent, summary):
        for widget in parent.winfo_children():
            widget.destroy()
        self.low_stock_data_cache = summary

        if summary.get("history_available") and summary["available_from"] and summary["range_start"] < summary["available_from"]:
            ctk.CTkLabel(
                parent,
                text=(
                    f"Stock history is available starting {summary['available_from']}. "
                    "Earlier dates in the searched range have no logged stock snapshots yet."
                ),
                font=ctk.CTkFont("Segoe UI", 11),
                text_color=WARNING,
                justify="left",
                wraplength=860,
            ).pack(anchor="w", pady=(0, 12))

        cards = ctk.CTkFrame(parent, fg_color="transparent")
        cards.pack(fill="x", pady=(0, 16))
        for column in range(4):
            cards.grid_columnconfigure(column, weight=1)

        metric_cards = [
            (
                "Snapshot As Of",
                summary["snapshot_date"].isoformat() if summary["snapshot_date"] else "No snapshot",
                summary["range_label"],
                BLUE,
            ),
            ("Critical", str(summary["critical_count"]), "Items at zero stock in the latest snapshot.", ERROR_RED),
            ("Low", str(summary["low_count"]), "Items at or below reorder level in the latest snapshot.", WARNING),
            (
                "Data Source",
                "Live Stock" if not summary.get("history_available") else summary["available_from"].isoformat(),
                f"Graph scale: {summary['group_label']}",
                SUCCESS,
            ),
        ]
        for index, (title, value, caption, accent) in enumerate(metric_cards):
            card = self._build_metric_card(cards, title, value, caption, accent)
            card.grid(row=0, column=index, padx=6, sticky="nsew")

        chart_row = ctk.CTkFrame(parent, fg_color="transparent")
        chart_row.pack(fill="x", pady=(0, 16))
        chart_row.grid_columnconfigure(0, weight=2)
        chart_row.grid_columnconfigure(1, weight=3)

        distribution_card, distribution_body = self._build_card(
            chart_row,
            "Low Stock Trend",
            f"Current low-stock count across {summary['range_label']} using {summary['group_label'].lower()} buckets.",
        )
        distribution_card.grid(row=0, column=0, padx=(0, 8), sticky="nsew")
        self._mount_line_chart(
            distribution_body,
            summary["timeline_points"],
            color=WARNING,
            money=False,
            empty_text="No low-stock items were found for the selected range.",
        )

        urgent_card, urgent_body = self._build_card(
            chart_row,
            "Snapshot Distribution",
            "Status counts from the latest stock snapshot.",
        )
        urgent_card.grid(row=0, column=1, padx=(8, 0), sticky="nsew")
        self._mount_bar_chart(
            urgent_body,
            [
                {"label": "Critical", "value": summary["critical_count"]},
                {"label": "Low", "value": summary["low_count"]},
                {"label": "Healthy", "value": summary["healthy_count"]},
            ],
            color=ERROR_RED,
            money=False,
            empty_text="No snapshot distribution is available for the selected range.",
        )

        meter_card, meter_body = self._build_card(
            parent,
            "Most Urgent Restocks",
            "Coverage bars show how close each ingredient is to its reorder level.",
        )
        meter_card.pack(fill="x", pady=(0, 16))
        self._render_low_stock_meters(meter_body, summary["rows"][:6])

        list_card, list_body = self._build_card(
            parent,
            "Restock Queue",
            "The highest-risk ingredients are listed first.",
        )
        list_card.pack(fill="x", pady=(0, 16))
        self.low_stock_list_host = list_body
        self._render_low_stock_list_section(list_body, summary)

    def _rerender_low_stock_list(self):
        if (
            self.active_tab.get() != "lowstock"
            or self.low_stock_list_host is None
            or not self.low_stock_list_host.winfo_exists()
            or not self.low_stock_data_cache
        ):
            self._reload_current_tab()
            return
        self._render_low_stock_list_section(self.low_stock_list_host, self.low_stock_data_cache)

    def _change_low_stock_page(self, step):
        if not self.low_stock_data_cache:
            return
        page_count = self._page_count(len(self.low_stock_data_cache.get("rows", [])))
        next_page = min(max(self.low_stock_page + step, 0), page_count - 1)
        if next_page == self.low_stock_page:
            return
        self.low_stock_page = next_page
        self._rerender_low_stock_list()

    def _render_low_stock_list_section(self, parent, summary):
        for widget in parent.winfo_children():
            widget.destroy()

        page_rows, page, page_count, total_count = self._slice_page_rows(summary["rows"], self.low_stock_page)
        self.low_stock_page = page
        self._render_low_stock_table(parent, page_rows)
        self._render_pagination_footer(
            parent,
            "lowstock",
            page,
            page_count,
            total_count,
            len(page_rows),
            self._change_low_stock_page,
        )

    def _render_low_stock_meters(self, parent, rows):
        c = self.c
        if not rows:
            ctk.CTkLabel(
                parent,
                text="All ingredients are safely stocked.",
                font=ctk.CTkFont("Segoe UI", 12),
                text_color=SUCCESS,
            ).pack(anchor="w", pady=8)
            return

        for item in rows:
            ingredient = item["ingredient"]
            status_color = ERROR_RED if item["status"] == "Critical" else WARNING
            row = ctk.CTkFrame(parent, fg_color=c["input"], corner_radius=10)
            row.pack(fill="x", pady=4)
            top = ctk.CTkFrame(row, fg_color="transparent")
            top.pack(fill="x", padx=14, pady=(12, 6))
            ctk.CTkLabel(
                top,
                text=ingredient.name,
                font=ctk.CTkFont("Segoe UI", 12, "bold"),
                text_color=c["text"],
            ).pack(side="left")
            ctk.CTkLabel(
                top,
                text=item["status"],
                font=ctk.CTkFont("Segoe UI", 10, "bold"),
                text_color=status_color,
            ).pack(side="right")
            ctk.CTkLabel(
                row,
                text=f"{item['quantity']:g} {ingredient.unit} available | reorder at {item['reorder_level']:g} {ingredient.unit}",
                font=ctk.CTkFont("Segoe UI", 11),
                text_color=c["text_gray"],
            ).pack(anchor="w", padx=14)
            progress = ctk.CTkProgressBar(
                row,
                height=10,
                corner_radius=999,
                progress_color=status_color,
                fg_color=c["border"],
            )
            progress.pack(fill="x", padx=14, pady=(8, 8))
            progress.set(item["coverage_ratio"])
            ctk.CTkLabel(
                row,
                text=f"Short by {item['shortage']:g} {ingredient.unit}",
                font=ctk.CTkFont("Segoe UI", 10),
                text_color=status_color,
            ).pack(anchor="w", padx=14, pady=(0, 12))

    def _render_low_stock_table(self, parent, rows):
        c = self.c
        if not rows:
            ctk.CTkLabel(
                parent,
                text="No ingredients currently need restocking.",
                font=ctk.CTkFont("Segoe UI", 12),
                text_color=SUCCESS,
            ).pack(anchor="w", pady=8)
            return

        header = ctk.CTkFrame(parent, fg_color=c["thead"], corner_radius=10)
        header.pack(fill="x", pady=(0, 6))
        columns = [("Ingredient", 3), ("Qty", 1), ("Reorder", 1), ("Shortage", 1), ("Status", 1)]
        for index, (label, weight) in enumerate(columns):
            header.grid_columnconfigure(index, weight=weight)
            ctk.CTkLabel(
                header,
                text=label,
                font=ctk.CTkFont("Segoe UI", 11, "bold"),
                text_color=c["text_muted"],
                anchor="w",
            ).grid(row=0, column=index, sticky="ew", padx=12, pady=10)

        for index, item in enumerate(rows):
            ingredient = item["ingredient"]
            status_color = ERROR_RED if item["status"] == "Critical" else WARNING
            row = ctk.CTkFrame(parent, fg_color=c["input"] if index % 2 == 0 else c["row_alt"], corner_radius=10)
            row.pack(fill="x", pady=2)
            for column, weight in enumerate([3, 1, 1, 1, 1]):
                row.grid_columnconfigure(column, weight=weight)
            values = [
                (ingredient.name, c["text"]),
                (f"{item['quantity']:g} {ingredient.unit}", c["text_gray"]),
                (f"{item['reorder_level']:g} {ingredient.unit}", c["text_gray"]),
                (f"{item['shortage']:g} {ingredient.unit}", status_color),
                (item["status"], status_color),
            ]
            for column, (value, text_color) in enumerate(values):
                ctk.CTkLabel(
                    row,
                    text=value,
                    font=ctk.CTkFont("Segoe UI", 12, "bold" if column in {0, 4} else "normal"),
                    text_color=text_color,
                    anchor="w",
                ).grid(row=0, column=column, sticky="ew", padx=12, pady=10)

    def _show_expiring(self):
        self._build_expiry_filters(self.content)
        report_body = ctk.CTkFrame(self.content, fg_color="transparent")
        report_body.pack(fill="both", expand=True)
        self.expiring_list_host = None
        self._show_loading(report_body, "Loading expiring inventory...")
        self._run_async(
            "expiring",
            self._fetch_expiring_report,
            lambda data: self._render_expiring(report_body, data),
            lambda error: self._show_error(report_body, error),
        )

    def _fetch_expiring_report(self):
        window_days = self._selected_expiry_days()
        return InventoryDB.get_expiring_report(days=window_days)

    def _build_expiry_timeline(self, rows, window_days):
        quantities_by_bucket = {}
        if window_days <= 14:
            for day_index in range(window_days + 1):
                label = "Today" if day_index == 0 else f"{day_index}d"
                quantities_by_bucket[label] = 0.0
            for item in rows:
                label = "Today" if item["days_left"] == 0 else f"{item['days_left']}d"
                quantities_by_bucket[label] = quantities_by_bucket.get(label, 0.0) + float(item["batch"].quantity)
        else:
            bucket_count = (window_days + 6) // 7
            for bucket in range(bucket_count):
                start_day = bucket * 7
                end_day = min(window_days, start_day + 6)
                quantities_by_bucket[f"{start_day}-{end_day}d"] = 0.0
            for item in rows:
                bucket = min(item["days_left"] // 7, bucket_count - 1)
                start_day = bucket * 7
                end_day = min(window_days, start_day + 6)
                label = f"{start_day}-{end_day}d"
                quantities_by_bucket[label] = quantities_by_bucket.get(label, 0.0) + float(item["batch"].quantity)

        return [{"label": label, "value": value} for label, value in quantities_by_bucket.items()]

    def _format_days_left(self, days_left):
        if days_left is None:
            return "No upcoming expirations"
        if days_left == 0:
            return "Today"
        if days_left == 1:
            return "1 day"
        return f"{days_left} days"

    def _render_expiring(self, parent, data):
        for widget in parent.winfo_children():
            widget.destroy()
        self.expiring_data_cache = data

        cards = ctk.CTkFrame(parent, fg_color="transparent")
        cards.pack(fill="x", pady=(0, 16))
        for column in range(4):
            cards.grid_columnconfigure(column, weight=1)

        metric_cards = [
            ("Batches", str(data["batch_count"]), f"Expiring within the next {data['window_days']} days.", WARNING),
            ("Products", str(data["product_count"]), "Unique products at risk in the selected window.", BLUE),
            ("Qty At Risk", self._compact_value(data["quantity_at_risk"]), "Total units that could expire soon.", AMBER),
            (
                "Nearest Expiry",
                self._format_days_left(data["nearest_expiry"]),
                "Most urgent batch in the current window.",
                ERROR_RED if data["nearest_expiry"] == 0 else WARNING,
            ),
        ]
        for index, (title, value, caption, accent) in enumerate(metric_cards):
            card = self._build_metric_card(cards, title, value, caption, accent)
            card.grid(row=0, column=index, padx=6, sticky="nsew")

        chart_row = ctk.CTkFrame(parent, fg_color="transparent")
        chart_row.pack(fill="x", pady=(0, 16))
        chart_row.grid_columnconfigure(0, weight=3)
        chart_row.grid_columnconfigure(1, weight=2)

        timeline_card, timeline_body = self._build_card(
            chart_row,
            "Expiry Timeline",
            "Quantity at risk over the next days or weeks, depending on the selected window.",
        )
        timeline_card.grid(row=0, column=0, padx=(0, 8), sticky="nsew")
        self._mount_bar_chart(
            timeline_body,
            data["timeline_points"],
            color=WARNING,
            money=False,
            empty_text="No items are expiring inside this window.",
        )

        products_card, products_body = self._build_card(
            chart_row,
            "Products At Risk",
            "Top products with the most quantity expiring inside the selected window.",
        )
        products_card.grid(row=0, column=1, padx=(8, 0), sticky="nsew")
        self._mount_bar_chart(
            products_body,
            data["product_points"],
            color=ERROR_RED,
            money=False,
            empty_text="No expiring products were found for this window.",
        )

        list_card, list_body = self._build_card(
            parent,
            "Expiring Batch List",
            "Soonest expirations are listed first so the bakery team can act quickly. Click a batch row to view its details.",
        )
        list_card.pack(fill="x", pady=(0, 16))
        self.expiring_list_host = list_body
        self._render_expiring_list_section(list_body, data)

    def _rerender_expiring_list(self):
        if (
            self.active_tab.get() != "expiring"
            or self.expiring_list_host is None
            or not self.expiring_list_host.winfo_exists()
            or not self.expiring_data_cache
        ):
            self._reload_current_tab()
            return
        self._render_expiring_list_section(self.expiring_list_host, self.expiring_data_cache)

    def _change_expiring_page(self, step):
        if not self.expiring_data_cache:
            return
        page_count = self._page_count(len(self.expiring_data_cache.get("rows", [])))
        next_page = min(max(self.expiring_page + step, 0), page_count - 1)
        if next_page == self.expiring_page:
            return
        self.expiring_page = next_page
        self._rerender_expiring_list()

    def _render_expiring_list_section(self, parent, data):
        for widget in parent.winfo_children():
            widget.destroy()

        page_rows, page, page_count, total_count = self._slice_page_rows(data["rows"], self.expiring_page)
        self.expiring_page = page
        self._render_expiring_table(parent, page_rows)
        self._render_pagination_footer(
            parent,
            "expiring",
            page,
            page_count,
            total_count,
            len(page_rows),
            self._change_expiring_page,
        )

    def _render_expiring_table(self, parent, rows):
        c = self.c
        if not rows:
            ctk.CTkLabel(
                parent,
                text="No items are expiring within the selected window.",
                font=ctk.CTkFont("Segoe UI", 12),
                text_color=SUCCESS,
            ).pack(anchor="w", pady=8)
            return

        header = ctk.CTkFrame(parent, fg_color=c["thead"], corner_radius=10)
        header.pack(fill="x", pady=(0, 6))
        columns = [("Product", 3), ("Batch", 1), ("Qty", 1), ("Expires", 1), ("Time Left", 1)]
        for index, (label, weight) in enumerate(columns):
            header.grid_columnconfigure(index, weight=weight)
            ctk.CTkLabel(
                header,
                text=label,
                font=ctk.CTkFont("Segoe UI", 11, "bold"),
                text_color=c["text_muted"],
                anchor="w",
            ).grid(row=0, column=index, sticky="ew", padx=12, pady=10)

        for index, item in enumerate(rows):
            batch = item["batch"]
            base_color = c["input"] if index % 2 == 0 else c["row_alt"]
            row = ctk.CTkFrame(parent, fg_color=base_color, corner_radius=10)
            row.pack(fill="x", pady=2)
            for column, weight in enumerate([3, 1, 1, 1, 1]):
                row.grid_columnconfigure(column, weight=weight)
            urgency_color = ERROR_RED if item["days_left"] <= 1 else WARNING

            def open_expiring_details(
                _event,
                batch=batch,
                item=item,
            ):
                self._open_product_details_popup(
                    product_id=batch.product.product_id,
                    fallback_name=batch.product.name,
                    fallback_category=batch.product.category,
                    source_title=f"Expiring Batch #{batch.batch_id}",
                    source_note="This view is loaded from the expiring-inventory backend snapshot for the selected report window.",
                    extra_rows=[
                        ("Batch ID", f"#{batch.batch_id}"),
                        ("Batch Quantity", str(batch.quantity)),
                        ("Production Date", str(batch.production_date)),
                        ("Expiry Date", str(batch.expiry_date)),
                        ("Days Left", self._format_days_left(item["days_left"])),
                        ("Freshness", f"{item['freshness_percent']:.1f}% ({item['freshness_label']})"),
                    ],
                )

            def on_enter(_event, target=row):
                target.configure(fg_color=c["border"])

            def on_leave(_event, target=row, color=base_color):
                target.configure(fg_color=color)

            row.bind("<Button-1>", open_expiring_details)
            row.bind("<Enter>", on_enter)
            row.bind("<Leave>", on_leave)

            values = [
                (batch.product.name, c["text"]),
                (f"#{batch.batch_id}", AMBER),
                (str(batch.quantity), c["text_gray"]),
                (str(batch.expiry_date), c["text_gray"]),
                (self._format_days_left(item["days_left"]), urgency_color),
            ]
            for column, (value, text_color) in enumerate(values):
                label = ctk.CTkLabel(
                    row,
                    text=value,
                    font=ctk.CTkFont("Segoe UI", 12, "bold" if column in {0, 4} else "normal"),
                    text_color=text_color,
                    anchor="w",
                )
                label.grid(row=0, column=column, sticky="ew", padx=12, pady=10)
                label.bind("<Button-1>", open_expiring_details)
                label.bind("<Enter>", on_enter)
                label.bind("<Leave>", on_leave)

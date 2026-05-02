import calendar
from datetime import date

import customtkinter as ctk


class TouchDatePicker(ctk.CTkToplevel):
    def __init__(self, parent, colors, initial_date, title, on_select, anchor_widget=None):
        super().__init__(parent)
        self.colors = colors
        self.on_select = on_select
        self.selected_date = initial_date or date.today()
        self.visible_year = self.selected_date.year
        self.visible_month = self.selected_date.month
        self.anchor_widget = anchor_widget
        self.day_buttons = []
        self.month_option_buttons = []
        self.month_dropdown = None
        self.month_dropdown_scroll = None
        self.year_option_buttons = []
        self.year_dropdown = None
        self.year_dropdown_scroll = None
        self.accent = colors.get("amber", AMBER)
        self.accent_dark = colors.get("amber_dark", AMBER_DARK)
        self.month_values = list(calendar.month_name[1:])
        self.month_var = ctk.StringVar(value=calendar.month_name[self.visible_month])
        self.year_var = ctk.StringVar(value=str(self.visible_year))
        self.year_values = self._build_year_values()
        self.month_field_width = 234
        self.year_field_width = 154
        self.field_gap = 8
        self.dropdown_gap = 6
        self.window_width = 436

        self.title(title)
        self.geometry(f"{self.window_width}x340")
        self.resizable(False, False)
        self.transient(parent)
        self.configure(fg_color=colors["bg"])

        self._build_ui(title)
        self._position_window(parent)
        self._render_days()
        self.after(50, self.lift)
        self.after(60, self.grab_set)

    def _build_ui(self, title):
        c = self.colors
        container = ctk.CTkFrame(
            self,
            fg_color=c["card"],
            corner_radius=18,
            border_width=1,
            border_color=c["border"],
        )
        container.pack(fill="both", expand=True, padx=8, pady=8)

        top_row = ctk.CTkFrame(container, fg_color="transparent")
        top_row.pack(fill="x", padx=12, pady=(10, 8))
        ctk.CTkLabel(
            top_row,
            text=title,
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            text_color=c["text"],
        ).pack(side="left")

        self.container = container
        controls_row = ctk.CTkFrame(
            container,
            fg_color="transparent",
            width=self.month_field_width + self.field_gap + self.year_field_width,
            height=36,
        )
        controls_row.pack(anchor="w", padx=12, pady=(0, 8))
        controls_row.pack_propagate(False)
        self.controls_row = controls_row

        month_wrap = ctk.CTkFrame(controls_row, fg_color="transparent", width=self.month_field_width, height=36)
        month_wrap.place(x=0, y=0)
        month_wrap.pack_propagate(False)
        self.month_wrap = month_wrap

        year_wrap = ctk.CTkFrame(controls_row, fg_color="transparent", width=self.year_field_width, height=36)
        year_wrap.place(x=self.month_field_width + self.field_gap, y=0)
        year_wrap.pack_propagate(False)
        self.year_wrap = year_wrap

        self.month_button = ctk.CTkButton(
            month_wrap,
            width=self.month_field_width,
            height=36,
            corner_radius=999,
            fg_color=c["input"],
            hover_color=c["border"],
            text_color=c["text"],
            border_width=1,
            border_color=c["border"],
            border_spacing=14,
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            anchor="w",
            command=self._toggle_month_dropdown,
        )
        self.month_button.pack(fill="x")
        self._update_month_button()

        self.year_button = ctk.CTkButton(
            year_wrap,
            text="",
            width=self.year_field_width,
            height=36,
            corner_radius=999,
            fg_color=c["input"],
            hover_color=c["border"],
            text_color=c["text"],
            border_width=1,
            border_color=c["border"],
            border_spacing=14,
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            anchor="w",
            command=self._toggle_year_dropdown,
        )
        self.year_button.pack(fill="x")
        self._update_year_button()

        weekdays = ctk.CTkFrame(container, fg_color="transparent")
        weekdays.pack(fill="x", padx=12, pady=(0, 4))
        for column, label in enumerate(["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]):
            weekdays.grid_columnconfigure(column, weight=1)
            ctk.CTkLabel(
                weekdays,
                text=label,
                font=ctk.CTkFont("Segoe UI", 8, "bold"),
                text_color=c["text_muted"],
            ).grid(row=0, column=column, sticky="nsew", padx=2)

        self.grid_frame = ctk.CTkFrame(container, fg_color="transparent")
        self.grid_frame.pack(fill="x", padx=12, pady=(0, 10))
        for column in range(7):
            self.grid_frame.grid_columnconfigure(column, weight=1)

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

    def _select_date(self, chosen_date):
        self._close_month_dropdown()
        self._close_year_dropdown()
        self.on_select(chosen_date)
        self.destroy()

    def _build_year_values(self):
        current_year = date.today().year
        start_year = 2000
        end_year = max(current_year + 25, self.selected_date.year + 10, self.visible_year + 10)
        return [str(year) for year in range(start_year, end_year + 1)]

    def _update_month_button(self):
        suffix = "  ^" if self.month_dropdown is not None else "  v"
        self.month_button.configure(text=f"{self.month_var.get()}{suffix}")

    def _field_position(self, widget):
        self.update_idletasks()
        field_x = widget.winfo_rootx() - self.container.winfo_rootx()
        field_y = widget.winfo_rooty() - self.container.winfo_rooty()
        field_width = widget.winfo_width()
        field_height = widget.winfo_height()

        if hasattr(self.container, "_reverse_widget_scaling"):
            field_x = self.container._reverse_widget_scaling(field_x)
            field_y = self.container._reverse_widget_scaling(field_y)
            field_width = self.container._reverse_widget_scaling(field_width)
            field_height = self.container._reverse_widget_scaling(field_height)

        return (
            int(round(field_x)),
            int(round(field_y)),
            int(round(field_width)),
            int(round(field_height)),
        )

    def _toggle_month_dropdown(self):
        if self.month_dropdown is not None:
            self._close_month_dropdown()
            return
        self._open_month_dropdown()

    def _open_month_dropdown(self):
        c = self.colors
        self._close_year_dropdown()
        self._close_month_dropdown()
        self.update_idletasks()

        x_position, y_position, field_width, field_height = self._field_position(self.month_wrap)
        dropdown_width = max(field_width, self.month_field_width)
        dropdown = ctk.CTkFrame(
            self.container,
            fg_color=c["card"],
            corner_radius=12,
            border_width=1,
            border_color=c["border"],
            width=dropdown_width,
            height=182,
        )
        self.month_dropdown = dropdown
        dropdown.pack_propagate(False)

        dropdown.place(x=x_position, y=y_position + field_height + self.dropdown_gap)
        dropdown.lift()

        scroll = ctk.CTkScrollableFrame(
            dropdown,
            fg_color="transparent",
            width=max(dropdown_width - 18, 140),
            height=158,
            corner_radius=0,
            scrollbar_button_color=c["border"],
            scrollbar_button_hover_color=self.accent,
        )
        scroll.pack(fill="both", expand=True, padx=6, pady=6)
        self.month_dropdown_scroll = scroll
        self.month_option_buttons = []

        selected_month = self.month_var.get()
        for value in self.month_values:
            is_selected = value == selected_month
            button = ctk.CTkButton(
                scroll,
                text=value,
                height=30,
                corner_radius=8,
                fg_color=self.accent if is_selected else c["input"],
                hover_color=self.accent_dark if is_selected else c["border"],
                text_color="#0F0F0F" if is_selected else c["text"],
                font=ctk.CTkFont("Segoe UI", 9, "bold" if is_selected else "normal"),
                anchor="w",
                command=lambda month_value=value: self._select_month_from_dropdown(month_value),
            )
            button.pack(fill="x", pady=1)
            self.month_option_buttons.append(button)

        self._update_month_button()
        self.after(10, self._scroll_month_dropdown_to_selection)

    def _close_month_dropdown(self):
        if self.month_dropdown is not None and self.month_dropdown.winfo_exists():
            self.month_dropdown.destroy()
        self.month_dropdown = None
        self.month_dropdown_scroll = None
        self.month_option_buttons = []
        if hasattr(self, "month_button") and self.month_button.winfo_exists():
            self._update_month_button()

    def _select_month_from_dropdown(self, month_value):
        self.month_var.set(month_value)
        try:
            self.visible_month = self.month_values.index(month_value) + 1
        except ValueError:
            self._close_month_dropdown()
            return
        self._close_month_dropdown()
        self._render_days()

    def _scroll_month_dropdown_to_selection(self):
        if self.month_dropdown_scroll is None or not self.month_option_buttons:
            return
        canvas = getattr(self.month_dropdown_scroll, "_parent_canvas", None)
        if canvas is None:
            return

        try:
            selected_index = self.month_values.index(self.month_var.get())
        except ValueError:
            selected_index = 0

        self.update_idletasks()
        button = self.month_option_buttons[selected_index]
        total_height = self.month_option_buttons[-1].winfo_y() + self.month_option_buttons[-1].winfo_height()
        viewport_height = canvas.winfo_height()
        if total_height <= viewport_height:
            canvas.yview_moveto(0)
            return

        target = button.winfo_y() + (button.winfo_height() / 2) - (viewport_height / 2)
        max_offset = max(total_height - viewport_height, 1)
        fraction = min(max(target / max_offset, 0), 1)
        canvas.yview_moveto(fraction)

    def _update_year_button(self):
        suffix = "  ^" if self.year_dropdown is not None else "  v"
        self.year_button.configure(text=f"{self.year_var.get()}{suffix}")

    def _toggle_year_dropdown(self):
        if self.year_dropdown is not None:
            self._close_year_dropdown()
            return
        self._open_year_dropdown()

    def _open_year_dropdown(self):
        c = self.colors
        self._close_month_dropdown()
        self._close_year_dropdown()
        self.update_idletasks()

        x_position, y_position, field_width, field_height = self._field_position(self.year_wrap)
        dropdown_width = max(field_width, self.year_field_width)
        dropdown_height = 182
        dropdown = ctk.CTkFrame(
            self.container,
            fg_color=c["card"],
            corner_radius=12,
            border_width=1,
            border_color=c["border"],
            width=dropdown_width,
            height=dropdown_height,
        )
        self.year_dropdown = dropdown
        dropdown.pack_propagate(False)

        dropdown.place(
            x=x_position,
            y=y_position + field_height + self.dropdown_gap,
        )
        dropdown.lift()

        scroll = ctk.CTkScrollableFrame(
            dropdown,
            fg_color="transparent",
            width=max(dropdown_width - 18, 104),
            height=158,
            corner_radius=0,
            scrollbar_button_color=c["border"],
            scrollbar_button_hover_color=self.accent,
        )
        scroll.pack(fill="both", expand=True, padx=6, pady=6)
        self.year_dropdown_scroll = scroll
        self.year_option_buttons = []

        selected_year = self.year_var.get()
        for value in self.year_values:
            is_selected = value == selected_year
            button = ctk.CTkButton(
                scroll,
                text=value,
                height=30,
                corner_radius=8,
                fg_color=self.accent if is_selected else c["input"],
                hover_color=self.accent_dark if is_selected else c["border"],
                text_color="#0F0F0F" if is_selected else c["text"],
                font=ctk.CTkFont("Segoe UI", 9, "bold" if is_selected else "normal"),
                command=lambda year_value=value: self._select_year_from_dropdown(year_value),
            )
            button.pack(fill="x", pady=1)
            self.year_option_buttons.append(button)

        self._update_year_button()
        self.after(10, self._scroll_year_dropdown_to_selection)

    def _close_year_dropdown(self):
        if self.year_dropdown is not None and self.year_dropdown.winfo_exists():
            self.year_dropdown.destroy()
        self.year_dropdown = None
        self.year_dropdown_scroll = None
        self.year_option_buttons = []
        if hasattr(self, "year_button") and self.year_button.winfo_exists():
            self._update_year_button()

    def _select_year_from_dropdown(self, year_value):
        self.year_var.set(year_value)
        try:
            self.visible_year = int(year_value)
        except (TypeError, ValueError):
            self._close_year_dropdown()
            return
        self._close_year_dropdown()
        self._render_days()

    def _scroll_year_dropdown_to_selection(self):
        if self.year_dropdown_scroll is None or not self.year_option_buttons:
            return
        canvas = getattr(self.year_dropdown_scroll, "_parent_canvas", None)
        if canvas is None:
            return

        try:
            selected_index = self.year_values.index(self.year_var.get())
        except ValueError:
            selected_index = 0

        self.update_idletasks()
        button = self.year_option_buttons[selected_index]
        total_height = self.year_option_buttons[-1].winfo_y() + self.year_option_buttons[-1].winfo_height()
        viewport_height = canvas.winfo_height()
        if total_height <= viewport_height:
            canvas.yview_moveto(0)
            return

        target = button.winfo_y() + (button.winfo_height() / 2) - (viewport_height / 2)
        max_offset = max(total_height - viewport_height, 1)
        fraction = min(max(target / max_offset, 0), 1)
        canvas.yview_moveto(fraction)

    def _calendar_weeks(self):
        return calendar.Calendar(firstweekday=0).monthdayscalendar(self.visible_year, self.visible_month)

    def _render_days(self):
        c = self.colors
        for button in self.day_buttons:
            button.destroy()
        self.day_buttons = []

        self.month_var.set(calendar.month_name[self.visible_month])
        self.year_var.set(str(self.visible_year))
        self._update_month_button()
        self._update_year_button()

        weeks = self._calendar_weeks()
        for row_index in range(6):
            self.grid_frame.grid_rowconfigure(row_index, weight=0, minsize=0)
        for row_index in range(len(weeks)):
            self.grid_frame.grid_rowconfigure(row_index, weight=1)

        today = date.today()
        for row_index, week in enumerate(weeks):
            for column_index, day_value in enumerate(week):
                if not day_value:
                    button = ctk.CTkLabel(self.grid_frame, text="", fg_color="transparent")
                else:
                    button_date = date(self.visible_year, self.visible_month, day_value)
                    is_selected = button_date == self.selected_date
                    is_today = button_date == today

                    fg_color = self.accent if is_selected else c["input"]
                    text_color = "#0F0F0F" if is_selected else c["text"]
                    hover_color = self.accent_dark if is_selected else c["border"]
                    border_width = 1 if is_today and not is_selected else 0
                    border_color = self.accent_dark if is_today and not is_selected else c["input"]

                    button = ctk.CTkButton(
                        self.grid_frame,
                        text=str(day_value),
                        width=32,
                        height=28,
                        corner_radius=8,
                        fg_color=fg_color,
                        hover_color=hover_color,
                        text_color=text_color,
                        border_width=border_width,
                        border_color=border_color,
                        font=ctk.CTkFont("Segoe UI", 8, "bold" if is_selected or is_today else "normal"),
                        command=lambda value=button_date: self._select_date(value),
                    )
                button.grid(row=row_index, column=column_index, padx=2, pady=2, sticky="nsew")
                self.day_buttons.append(button)
        self._update_compact_height(len(weeks))
        self.after(0, lambda week_count=len(weeks): self._update_compact_height(week_count))

    def _update_compact_height(self, week_count):
        if not self.winfo_exists():
            return
        self.update_idletasks()
        x_position = self.winfo_x()
        y_position = self.winfo_y()
        content_height = (
            16
            + self.container.winfo_reqheight()
        )
        minimum_height = 286 + (max(week_count, 4) * 18)
        window_height = max(minimum_height, content_height)
        self.geometry(f"{self.window_width}x{window_height}+{x_position}+{y_position}")


AMBER = "#F59E0B"
AMBER_DARK = "#B45309"

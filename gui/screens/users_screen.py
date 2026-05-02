from datetime import date, datetime
from tkinter import messagebox

import customtkinter as ctk

from database.user_db import UserDB
from gui.async_utils import run_in_thread
from gui.side_panel import SidePanelHost
from gui.theme import AMBER, AMBER_DARK, BLUE, ERROR_RED, SUCCESS, get_colors


class UsersScreen(ctk.CTkFrame):
    ROLE_COLORS = {"owner": AMBER, "cashier": BLUE, "baker": SUCCESS}
    TABLE_COLUMNS = [
        ("Account", 30),
        ("Username", 18),
        ("Role", 14),
        ("Status", 12),
        ("Last Login", 16),
        ("Actions", 18),
    ]

    def __init__(self, parent, user):
        self.c = get_colors()
        super().__init__(parent, fg_color=self.c["bg"], corner_radius=0)
        self.user = user
        self.is_owner = str(user.get("role", "")).strip().lower() == "owner"
        self.panel_host = SidePanelHost(self, self.c)
        self.users_cache = []
        self.user_history_cache = {}
        self.preview_user_id = None
        self.user_row_views = {}
        self.rows_frame = None
        self.table_status_label = None
        self.preview_name_label = None
        self.preview_meta_label = None
        self.preview_user_code_label = None
        self.preview_system_id_label = None
        self.preview_role_label = None
        self.preview_status_label = None
        self.preview_created_label = None
        self.preview_updated_label = None
        self.preview_login_label = None
        self.preview_logout_label = None
        self.preview_screen_label = None
        self.preview_history_frame = None
        self.role_filter_var = ctk.StringVar(value="All")
        self._users_load_token = None
        self._history_load_token = None
        self._users_loading = False
        self.pack(fill="both", expand=True)
        self._build_ui()

    def _selected_row_bg(self):
        return self.c["active_bg"]

    def _danger_button_colors(self):
        if ctk.get_appearance_mode() == "Dark":
            return "#311818", "#452020"
        return "#FEE2E2", "#FECACA"

    def _build_ui(self):
        c = self.c
        shell = ctk.CTkFrame(self, fg_color="transparent")
        shell.pack(fill="both", expand=True, padx=24, pady=22)

        header = ctk.CTkFrame(shell, fg_color="transparent")
        header.pack(fill="x")

        copy = ctk.CTkFrame(header, fg_color="transparent")
        copy.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            copy,
            text="User Management",
            font=ctk.CTkFont("Georgia", 28, "bold"),
            text_color=c["text"],
        ).pack(anchor="w")
        ctk.CTkLabel(
            copy,
            text=(
                "Select a user row to view account details and recent activity. "
                "Use the Actions column to edit or delete accounts."
            ),
            font=ctk.CTkFont("Segoe UI", 12),
            text_color=c["text_muted"],
            justify="left",
        ).pack(anchor="w", pady=(6, 0))

        header_actions = ctk.CTkFrame(header, fg_color="transparent")
        header_actions.pack(side="right")

        ctk.CTkButton(
            header_actions,
            text="Refresh",
            height=38,
            width=90,
            fg_color=c["card"],
            hover_color=c["border"],
            text_color=c["text"],
            corner_radius=8,
            border_width=1,
            border_color=c["border"],
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            command=self._load_users,
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            header_actions,
            text="+ Add User",
            height=38,
            fg_color=AMBER,
            hover_color=AMBER_DARK,
            text_color="#0F0F0F",
            corner_radius=8,
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            command=self._open_add_panel,
            state="normal" if self.is_owner else "disabled",
        ).pack(side="left")

        content = ctk.CTkFrame(shell, fg_color="transparent")
        content.pack(fill="both", expand=True, pady=(18, 0))
        content.grid_columnconfigure(0, weight=7, uniform="users")
        content.grid_columnconfigure(1, weight=4, uniform="users")
        content.grid_rowconfigure(0, weight=1)

        self._build_table(content)
        self._build_preview(content)
        self._load_users()

    def _build_table(self, parent):
        c = self.c
        card = ctk.CTkFrame(
            parent,
            fg_color=c["card"],
            corner_radius=14,
            border_width=1,
            border_color=c["border"],
        )
        card.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        title_row = ctk.CTkFrame(card, fg_color="transparent")
        title_row.pack(fill="x", padx=18, pady=(16, 8))
        ctk.CTkLabel(
            title_row,
            text="Users",
            font=ctk.CTkFont("Segoe UI", 15, "bold"),
            text_color=c["text"],
        ).pack(side="left")

        right_tools = ctk.CTkFrame(title_row, fg_color="transparent")
        right_tools.pack(side="right")

        self.table_status_label = ctk.CTkLabel(
            right_tools,
            text="",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=c["text_muted"],
        )
        self.table_status_label.pack(side="right")

        ctk.CTkOptionMenu(
            right_tools,
            values=["All", "Owner", "Cashier", "Baker"],
            variable=self.role_filter_var,
            width=110,
            height=30,
            fg_color=c["input"],
            button_color=c["border"],
            button_hover_color=c["input"],
            text_color=c["text"],
            dropdown_fg_color=c["card"],
            dropdown_text_color=c["text"],
            font=ctk.CTkFont("Segoe UI", 11),
            command=lambda _value: self._apply_users_filter(),
            dynamic_resizing=False,
        ).pack(side="right", padx=(0, 10))

        head = ctk.CTkFrame(card, fg_color=c["thead"], height=42, corner_radius=10)
        head.pack(fill="x", padx=12, pady=(0, 6))
        head.pack_propagate(False)
        for index, (text, weight) in enumerate(self.TABLE_COLUMNS):
            head.grid_columnconfigure(index, weight=weight, uniform="users_table")
            ctk.CTkLabel(
                head,
                text=text,
                font=ctk.CTkFont("Segoe UI", 11, "bold"),
                text_color=c["text_muted"],
                anchor="w",
            ).grid(
                row=0,
                column=index,
                sticky="ew",
                padx=((14, 8) if index == 0 else (8, 8)),
                pady=10,
            )

        self.rows_frame = ctk.CTkScrollableFrame(card, fg_color="transparent")
        self.rows_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def _build_preview(self, parent):
        c = self.c
        card = ctk.CTkFrame(
            parent,
            fg_color=c["card"],
            corner_radius=14,
            border_width=1,
            border_color=c["border"],
        )
        card.grid(row=0, column=1, sticky="nsew")

        ctk.CTkLabel(
            card,
            text="Account Details",
            font=ctk.CTkFont("Segoe UI", 15, "bold"),
            text_color=c["text"],
        ).pack(anchor="w", padx=18, pady=(16, 2))
        ctk.CTkLabel(
            card,
            text="Click a user row to keep that account selected for details. Use the Actions column to manage it.",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=c["text_muted"],
            justify="left",
            wraplength=320,
        ).pack(anchor="w", padx=18, pady=(0, 10))

        summary = ctk.CTkFrame(
            card,
            fg_color=c["input"],
            corner_radius=12,
            border_width=1,
            border_color=c["border"],
        )
        summary.pack(fill="x", padx=18, pady=(0, 10))

        self.preview_name_label = ctk.CTkLabel(
            summary,
            text="Select a user",
            font=ctk.CTkFont("Georgia", 22, "bold"),
            text_color=c["text"],
        )
        self.preview_name_label.pack(anchor="w", padx=14, pady=(14, 2))
        self.preview_meta_label = ctk.CTkLabel(
            summary,
            text="User details will appear here.",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=c["text_muted"],
        )
        self.preview_meta_label.pack(anchor="w", padx=14, pady=(0, 10))

        tag_row = ctk.CTkFrame(summary, fg_color="transparent")
        tag_row.pack(fill="x", padx=14, pady=(0, 8))
        self.preview_role_label = ctk.CTkLabel(
            tag_row,
            text="USER",
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            fg_color=c["border"],
            text_color=c["text"],
            corner_radius=6,
            padx=10,
            pady=4,
        )
        self.preview_role_label.pack(side="left")
        self.preview_status_label = ctk.CTkLabel(
            tag_row,
            text="Offline",
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            text_color=c["text_muted"],
        )
        self.preview_status_label.pack(side="left", padx=(10, 0))

        self.preview_user_code_label = self._detail_row(summary, "User ID")
        self.preview_system_id_label = self._detail_row(summary, "System ID")
        self.preview_created_label = self._detail_row(summary, "Created")
        self.preview_updated_label = self._detail_row(summary, "Updated")
        self.preview_login_label = self._detail_row(summary, "Last Login")
        self.preview_logout_label = self._detail_row(summary, "Last Logout")
        self.preview_screen_label = self._detail_row(summary, "Last Screen")

        ctk.CTkLabel(
            card,
            text="Recent Activity",
            font=ctk.CTkFont("Segoe UI", 13, "bold"),
            text_color=c["text"],
        ).pack(anchor="w", padx=18, pady=(0, 8))

        self.preview_history_frame = ctk.CTkScrollableFrame(card, fg_color="transparent")
        self.preview_history_frame.pack(fill="both", expand=True, padx=18, pady=(0, 14))

    def _detail_row(self, parent, caption):
        c = self.c
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=(0, 6))
        ctk.CTkLabel(
            row,
            text=f"{caption}:",
            width=88,
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            text_color=c["text_muted"],
            anchor="w",
        ).pack(side="left")
        value = ctk.CTkLabel(
            row,
            text="-",
            font=ctk.CTkFont("Segoe UI", 10),
            text_color=c["text"],
            anchor="w",
            justify="left",
        )
        value.pack(side="left", fill="x", expand=True)
        return value

    def _get_filtered_users(self):
        selected = self.role_filter_var.get().strip().lower()
        if selected == "all":
            return list(self.users_cache)
        return [
            row for row in self.users_cache
            if str(row.get("role", "")).strip().lower() == selected
        ]

    def _load_users(self):
        self._users_loading = True
        token = object()
        self._users_load_token = token
        self.user_row_views = {}
        self._clear_rows()
        self.table_status_label.configure(text="Loading...")
        self._set_rows_message("Loading users...")
        self._render_preview_empty("Loading user data...")

        run_in_thread(
            self,
            UserDB.get_all_users,
            on_success=lambda users: self._apply_loaded_users(token, users),
            on_error=lambda exc: self._handle_users_load_error(token, exc),
            is_current=lambda: self._users_load_token is token,
        )

    def _apply_loaded_users(self, token, users):
        if self._users_load_token is not token:
            return

        self._users_loading = False
        self.users_cache = users or []
        self.user_history_cache = {}
        self._apply_users_filter()

    def _handle_users_load_error(self, token, exc):
        if self._users_load_token is not token:
            return

        self._users_loading = False
        self.users_cache = []
        self.table_status_label.configure(text="Load failed")
        self._set_rows_message(f"Failed to load users: {exc}", color=ERROR_RED)
        self._render_preview_empty("User data is unavailable right now.")

    def _apply_users_filter(self):
        c = self.c
        if self._users_loading and not self.users_cache:
            return

        self.user_row_views = {}
        self._clear_rows()
        filtered_users = self._get_filtered_users()
        count = len(filtered_users)
        self.table_status_label.configure(text=f"{count} account{'s' if count != 1 else ''}")

        if not filtered_users:
            self._set_rows_message("No users found for this role filter.")
            self._render_preview_empty("No account matches the selected role filter.")
            return

        if self.preview_user_id is None or not any(row["user_id"] == self.preview_user_id for row in filtered_users):
            self.preview_user_id = filtered_users[0]["user_id"]

        selected_user = next((row for row in filtered_users if row["user_id"] == self.preview_user_id), filtered_users[0])
        self._show_preview(selected_user)

        for index, user in enumerate(filtered_users):
            self._build_user_row(user, index)

    def _clear_rows(self):
        for widget in self.rows_frame.winfo_children():
            widget.destroy()

    def _set_rows_message(self, message, color=None):
        ctk.CTkLabel(
            self.rows_frame,
            text=message,
            font=ctk.CTkFont("Segoe UI", 13),
            text_color=color or self.c["text_muted"],
            justify="left",
        ).pack(anchor="w", pady=24)

    def _build_user_row(self, user, index):
        c = self.c
        row_bg = c["card"] if index % 2 == 0 else c["row_alt"]
        hover_bg = c["active_bg"]
        selected_bg = self._selected_row_bg()
        role = str(user.get("role", "")).strip().lower()
        user_id = user.get("user_id")
        is_selected = user_id == self.preview_user_id
        status_text, status_color = self._account_status(user)

        row = ctk.CTkFrame(
            self.rows_frame,
            fg_color=selected_bg if is_selected else row_bg,
            corner_radius=10,
            height=82,
            border_width=1,
            border_color=AMBER if is_selected else c["border"],
        )
        row.pack(fill="x", pady=(0, 6))
        row.pack_propagate(False)
        for column, (_text, weight) in enumerate(self.TABLE_COLUMNS):
            row.grid_columnconfigure(column, weight=weight, uniform="users_table")

        widgets = [row]
        widgets.extend(self._row_account_cell(row, user, 0))
        widgets.append(self._row_label(row, user.get("username", ""), 1))

        role_frame = ctk.CTkFrame(row, fg_color="transparent")
        role_frame.grid(row=0, column=2, sticky="nsew", padx=8, pady=8)
        role_badge = ctk.CTkLabel(
            role_frame,
            text=role.upper(),
            font=ctk.CTkFont("Segoe UI", 9, "bold"),
            fg_color=self.ROLE_COLORS.get(role, c["text_gray"]),
            text_color="#0F0F0F",
            corner_radius=6,
            padx=8,
            pady=4,
            width=78,
            anchor="center",
        )
        role_badge.pack(anchor="center", expand=True)
        widgets.extend([role_frame, role_badge])

        widgets.append(
            self._row_label(
                row,
                status_text,
                3,
                bold=True,
                color=status_color,
            )
        )
        widgets.append(
            self._row_label(
                row,
                self._fmt_table_time(user.get("last_login_at")),
                4,
                color=c["text_muted"],
            )
        )

        actions = ctk.CTkFrame(row, fg_color="transparent")
        actions.grid(row=0, column=5, sticky="nsew", padx=(8, 14), pady=8)
        actions.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(
            actions,
            text="Edit",
            height=28,
            fg_color=c["input"],
            hover_color=c["border"],
            text_color=c["text"],
            corner_radius=8,
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            command=lambda selected=user: self._open_edit_panel(selected),
            state="normal" if self.is_owner else "disabled",
        ).grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(
            actions,
            text="Delete",
            height=28,
            fg_color=self._danger_button_colors()[0],
            hover_color=self._danger_button_colors()[1],
            text_color=ERROR_RED,
            corner_radius=8,
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            command=lambda selected=user: self._delete_user(selected),
            state="normal" if self.is_owner else "disabled",
        ).grid(row=1, column=0, sticky="ew", pady=(6, 0))

        def on_enter(_event=None):
            if self.preview_user_id != user_id:
                row.configure(fg_color=hover_bg, border_color=AMBER_DARK)

        def on_leave(_event=None):
            self._apply_row_selection_state(user_id)

        def on_click(_event=None):
            self._select_user(user)

        for widget in widgets:
            widget.bind("<Enter>", on_enter, add="+")
            widget.bind("<Leave>", on_leave, add="+")
            widget.bind("<Button-1>", on_click, add="+")

        self.user_row_views[user_id] = {
            "row": row,
            "row_bg": row_bg,
            "hover_bg": hover_bg,
            "selected_bg": selected_bg,
        }
        self._apply_row_selection_state(user_id)

    def _row_label(self, parent, text, column, bold=False, color=None):
        label = ctk.CTkLabel(
            parent,
            text=text,
            font=ctk.CTkFont("Segoe UI", 12, "bold" if bold else "normal"),
            text_color=color or self.c["text"],
            anchor="w",
        )
        label.grid(row=0, column=column, sticky="ew", padx=8, pady=8)
        return label

    def _row_account_cell(self, parent, user, column):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=0, column=column, sticky="nsew", padx=(14, 8), pady=8)
        name_label = ctk.CTkLabel(
            frame,
            text=user.get("name") or user.get("username", ""),
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            text_color=self.c["text"],
            anchor="w",
            justify="left",
        )
        name_label.pack(fill="x", pady=(8, 0))
        code_label = ctk.CTkLabel(
            frame,
            text=f"User ID: {user.get('user_code') or '-'}",
            font=ctk.CTkFont("Segoe UI", 10),
            text_color=self.c["text_muted"],
            anchor="w",
            justify="left",
        )
        code_label.pack(fill="x", pady=(2, 0))
        return [frame, name_label, code_label]

    def _apply_row_selection_state(self, user_id):
        view = self.user_row_views.get(user_id)
        if not view:
            return
        is_selected = user_id == self.preview_user_id
        view["row"].configure(
            fg_color=view["selected_bg"] if is_selected else view["row_bg"],
            border_color=AMBER if is_selected else self.c["border"],
        )

    def _select_user(self, user):
        if not user:
            return
        self.preview_user_id = user.get("user_id")
        self._show_preview(user)
        for user_id in self.user_row_views:
            self._apply_row_selection_state(user_id)

    def _show_preview(self, user):
        self._render_preview_summary(user)
        user_id = user.get("user_id")
        if user_id in self.user_history_cache:
            self._render_preview_history(self.user_history_cache[user_id])
            return

        self._render_preview_history_loading()
        token = object()
        self._history_load_token = token
        run_in_thread(
            self,
            lambda: self._fetch_user_history(user_id),
            on_success=lambda history: self._apply_user_history(token, user_id, history),
            on_error=lambda exc: self._handle_user_history_error(token, user_id, exc),
            is_current=lambda: self._history_load_token is token and self.preview_user_id == user_id,
        )

    def _render_preview_summary(self, user):
        role = str(user.get("role", "")).strip().lower()
        status_text, status_color = self._account_status(user, detailed=True)
        self.preview_user_id = user.get("user_id")
        self.preview_name_label.configure(text=user.get("name") or user.get("username", "User"))
        self.preview_meta_label.configure(
            text=f"@{user.get('username', '')}  |  User ID {user.get('user_code') or '-'}  |  System #{user.get('user_id')}"
        )
        self.preview_role_label.configure(
            text=role.upper() or "USER",
            fg_color=self.ROLE_COLORS.get(role, self.c["border"]),
            text_color="#0F0F0F",
        )
        self.preview_status_label.configure(
            text=status_text,
            text_color=status_color,
        )
        self.preview_user_code_label.configure(text=user.get("user_code") or "-")
        self.preview_system_id_label.configure(text=f"#{user.get('user_id')}" if user.get("user_id") is not None else "-")
        self.preview_created_label.configure(text=self._fmt_time(user.get("created_at"), include_seconds=False))
        self.preview_updated_label.configure(text=self._fmt_time(user.get("updated_at"), include_seconds=False))
        self.preview_login_label.configure(text=self._fmt_time(user.get("last_login_at"), include_seconds=False))
        self.preview_logout_label.configure(
            text="Still active" if bool(user.get("is_online")) else self._fmt_time(user.get("last_logout_at"), include_seconds=False)
        )
        self.preview_screen_label.configure(text=self._screen_name(user.get("last_screen")))

    def _fetch_user_history(self, user_id):
        if not hasattr(UserDB, "get_recent_user_history"):
            return []
        return UserDB.get_recent_user_history(user_id, limit=8) or []

    def _apply_user_history(self, token, user_id, history):
        if self._history_load_token is not token or self.preview_user_id != user_id:
            return

        self.user_history_cache[user_id] = history or []
        self._render_preview_history(self.user_history_cache[user_id])

    def _handle_user_history_error(self, token, user_id, _exc):
        if self._history_load_token is not token or self.preview_user_id != user_id:
            return

        self.user_history_cache[user_id] = []
        self._render_preview_history([])

    def _render_preview_history_loading(self):
        for widget in self.preview_history_frame.winfo_children():
            widget.destroy()
        ctk.CTkLabel(
            self.preview_history_frame,
            text="Loading recent activity...",
            font=ctk.CTkFont("Segoe UI", 12),
            text_color=self.c["text_muted"],
        ).pack(anchor="w", pady=16)

    def _render_preview_history(self, history):
        for widget in self.preview_history_frame.winfo_children():
            widget.destroy()
        if not history:
            ctk.CTkLabel(
                self.preview_history_frame,
                text="No session history yet for this user.",
                font=ctk.CTkFont("Segoe UI", 12),
                text_color=self.c["text_muted"],
            ).pack(anchor="w", pady=16)
            return

        for session in history:
            self._history_card(session)

    def _render_preview_empty(self, message):
        self._history_load_token = None
        self.preview_name_label.configure(text="Select a user")
        self.preview_meta_label.configure(text=message)
        self.preview_role_label.configure(text="USER", fg_color=self.c["border"], text_color=self.c["text"])
        self.preview_status_label.configure(text="Offline", text_color=self.c["text_muted"])
        for label in [
            self.preview_user_code_label,
            self.preview_system_id_label,
            self.preview_created_label,
            self.preview_updated_label,
            self.preview_login_label,
            self.preview_logout_label,
            self.preview_screen_label,
        ]:
            label.configure(text="-")
        for widget in self.preview_history_frame.winfo_children():
            widget.destroy()
        ctk.CTkLabel(
            self.preview_history_frame,
            text="No recent activity yet.",
            font=ctk.CTkFont("Segoe UI", 12),
            text_color=self.c["text_muted"],
        ).pack(anchor="w", pady=16)

    def _history_card(self, session):
        c = self.c
        is_live = session.get("logout_at") is None
        card = ctk.CTkFrame(
            self.preview_history_frame,
            fg_color=c["input"],
            corner_radius=10,
            border_width=1,
            border_color=c["border"],
        )
        card.pack(fill="x", pady=(0, 8))

        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(
            top,
            text=self._fmt_time(session.get("login_at"), include_seconds=False),
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            text_color=c["text"],
            anchor="w",
        ).pack(side="left")
        ctk.CTkLabel(
            top,
            text="LIVE" if is_live else "ENDED",
            font=ctk.CTkFont("Segoe UI", 9, "bold"),
            text_color=SUCCESS if is_live else c["text_muted"],
        ).pack(side="right")

        ctk.CTkLabel(
            card,
            text=f"Logout: {'Still active' if is_live else self._fmt_time(session.get('logout_at'), include_seconds=False)}",
            font=ctk.CTkFont("Segoe UI", 10),
            text_color=c["text_muted"],
            anchor="w",
        ).pack(fill="x", padx=12)
        ctk.CTkLabel(
            card,
            text=f"Last Screen: {self._screen_name(session.get('last_screen'))}",
            font=ctk.CTkFont("Segoe UI", 10),
            text_color=c["text_muted"],
            anchor="w",
        ).pack(fill="x", padx=12, pady=(2, 0))
        ctk.CTkLabel(
            card,
            text=f"Time Online: {self._fmt_duration(session.get('duration_seconds'))}",
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            text_color=AMBER,
            anchor="w",
        ).pack(fill="x", padx=12, pady=(2, 10))

    def _current_user_id(self):
        return self.user.get("user_id") or self.user.get("id")

    def _account_status(self, user, detailed=False):
        if bool(user.get("is_online")):
            return ("Currently Online" if detailed else "Online", SUCCESS)

        raw_status = str(user.get("status") or "").strip()
        if raw_status:
            status = raw_status.capitalize()
        elif "is_active" in user:
            status = "Active" if bool(user.get("is_active")) else "Inactive"
        else:
            status = "Offline"

        status_key = status.strip().lower()
        if status_key in {"active", "enabled"}:
            return status, SUCCESS
        if status_key in {"inactive", "disabled", "suspended"}:
            return status, ERROR_RED
        return status, self.c["text_muted"]

    def _open_add_panel(self):
        if not self.is_owner:
            messagebox.showerror("Add User", "Only the owner account can add users.", parent=self)
            return
        self._open_user_panel("add")

    def _open_edit_panel(self, user):
        if not self.is_owner:
            messagebox.showerror("Edit User", "Only the owner account can edit users.", parent=self)
            return
        self._open_user_panel("edit", user)

    def _open_user_panel(self, mode, user=None):
        c = self.c
        app = self.winfo_toplevel()
        is_edit = mode == "edit"
        body = self.panel_host.open("Edit User" if is_edit else "Add User", width=430)
        panel = self.panel_host.panel
        content = ctk.CTkFrame(body, fg_color="transparent")
        content.pack(fill="x", padx=18)

        ctk.CTkLabel(
            content,
            text=(
                "Update the selected user's basic account details."
                if is_edit
                else "Create a new BakeWise account."
            ),
            font=ctk.CTkFont("Segoe UI", 12),
            text_color=c["text"],
            wraplength=320,
            justify="left",
        ).pack(anchor="w", pady=(18, 10))

        fields = {}

        def add_field(label, key, show="", placeholder="", default=""):
            ctk.CTkLabel(
                content,
                text=label,
                font=ctk.CTkFont("Segoe UI", 11),
                text_color=c["text_muted"],
            ).pack(anchor="w", pady=(8, 2))
            entry = ctk.CTkEntry(
                content,
                height=40,
                fg_color=c["input"],
                border_color=c["border"],
                text_color=c["text"],
                corner_radius=8,
                font=ctk.CTkFont("Segoe UI", 12),
                show=show,
                placeholder_text=placeholder,
                placeholder_text_color=c["text_muted"],
            )
            if default:
                entry.insert(0, default)
            entry.pack(fill="x")
            fields[key] = entry
            return entry

        add_field("Full Name", "name", default=user.get("name", "") if is_edit else "")

        if is_edit:
            ctk.CTkLabel(
                content,
                text="Username",
                font=ctk.CTkFont("Segoe UI", 11),
                text_color=c["text_muted"],
            ).pack(anchor="w", pady=(8, 2))
            username_frame = ctk.CTkFrame(
                content,
                fg_color=c["input"],
                corner_radius=8,
                border_width=1,
                border_color=c["border"],
                height=40,
            )
            username_frame.pack(fill="x")
            username_frame.pack_propagate(False)
            ctk.CTkLabel(
                username_frame,
                text=user.get("username", ""),
                font=ctk.CTkFont("Segoe UI", 12),
                text_color=c["text"],
                anchor="w",
            ).pack(fill="both", padx=12, pady=8)
        else:
            add_field("Username", "username")

        password_entry = add_field(
            "New Password" if is_edit else "Password",
            "password",
            show="*",
            placeholder="Leave blank to keep the current password" if is_edit else "",
        )

        if is_edit:
            details = ctk.CTkFrame(
                content,
                fg_color=c["input"],
                corner_radius=10,
                border_width=1,
                border_color=c["border"],
            )
            details.pack(fill="x", pady=(10, 2))
            ctk.CTkLabel(
                details,
                text=f"System ID: #{user.get('user_id')}",
                font=ctk.CTkFont("Segoe UI", 11, "bold"),
                text_color=c["text"],
                anchor="w",
            ).pack(fill="x", padx=12, pady=(10, 2))
            ctk.CTkLabel(
                details,
                text=f"User ID: {user.get('user_code') or '-'}",
                font=ctk.CTkFont("Segoe UI", 10),
                text_color=c["text_muted"],
                anchor="w",
            ).pack(fill="x", padx=12, pady=(0, 10))

        ctk.CTkLabel(
            content,
            text="Role",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=c["text_muted"],
        ).pack(anchor="w", pady=(8, 2))
        role_var = ctk.StringVar(value=user.get("role", "cashier") if is_edit else "cashier")
        ctk.CTkOptionMenu(
            content,
            values=["owner", "cashier", "baker"],
            variable=role_var,
            fg_color=c["input"],
            button_color=c["border"],
            button_hover_color=c["input"],
            text_color=c["text"],
            dropdown_fg_color=c["card"],
            dropdown_text_color=c["text"],
            font=ctk.CTkFont("Segoe UI", 12),
            anchor="w",
            dynamic_resizing=False,
        ).pack(fill="x")

        error_label = ctk.CTkLabel(
            content,
            text="",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=ERROR_RED,
            wraplength=320,
            justify="left",
        )
        error_label.pack(anchor="w", pady=(8, 0))

        def save():
            name = fields["name"].get().strip()
            password = fields["password"].get().strip()
            try:
                if is_edit:
                    target_id = user.get("user_id") or user.get("id")
                    current_user_id = self._current_user_id()
                    if (
                        current_user_id is not None
                        and int(target_id) == int(current_user_id)
                        and role_var.get() != self.user.get("role")
                    ):
                        error_label.configure(text="Sign in as another owner first if you need to change your own role.")
                        return

                    if hasattr(UserDB, "update_user"):
                        UserDB.update_user(
                            target_id,
                            password=password or None,
                            role=role_var.get(),
                            name=name or None,
                        )
                    else:
                        error_label.configure(text="UserDB.update_user() is missing in your backend.")
                        return
                    self.preview_user_id = target_id
                else:
                    username = fields["username"].get().strip()
                    if not username or not password:
                        error_label.configure(text="Username, password, and role are required.")
                        return
                    created_user_id = UserDB.add_user(
                        username=username,
                        password=password,
                        role=role_var.get(),
                        name=name or username,
                    )
                    self.preview_user_id = created_user_id
                self.panel_host.close()
                self._load_users()
            except Exception as exc:
                error_label.configure(text=str(exc))

        if hasattr(app, "register_primary_action"):
            app.register_primary_action(panel, on_enter=save, on_escape=self.panel_host.close)
        if hasattr(app, "register_entry"):
            app.register_entry(
                fields["name"],
                "text",
                on_enter=password_entry.focus_set if is_edit else fields["username"].focus_set,
                popup_parent=panel,
            )
            if not is_edit:
                app.register_entry(fields["username"], "text", on_enter=password_entry.focus_set, popup_parent=panel)
            app.register_entry(password_entry, "text", on_enter=save, popup_parent=panel)

        self.after(80, fields["name"].focus_set)

        ctk.CTkButton(
            content,
            text="Save Changes" if is_edit else "Add User",
            height=42,
            fg_color=AMBER,
            hover_color=AMBER_DARK,
            text_color="#0F0F0F",
            corner_radius=8,
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            command=save,
        ).pack(fill="x", pady=16)

    def _delete_user(self, user):
        if not self.is_owner:
            messagebox.showerror("Delete User", "Only the owner account can delete users.", parent=self)
            return
        target_id = user.get("user_id") or user.get("id")
        current_user_id = self._current_user_id()
        if current_user_id is not None and int(target_id) == int(current_user_id):
            messagebox.showerror(
                "Delete User",
                "You cannot delete the account you are currently signed in with.",
                parent=self,
            )
            return
        if not messagebox.askyesno(
            "Delete User",
            f"Delete user @{user.get('username', '')}?\n\nThis also removes the saved login history for that account.",
            parent=self,
        ):
            return
        try:
            UserDB.delete_user(target_id, acting_user_id=current_user_id)
            if self.preview_user_id == target_id:
                self.preview_user_id = None
            self._load_users()
        except Exception as exc:
            messagebox.showerror("Delete User", str(exc), parent=self)

    def _coerce_dt(self, value):
        if isinstance(value, datetime):
            return value
        if isinstance(value, date):
            return datetime.combine(value, datetime.min.time())
        if isinstance(value, str) and value.strip():
            cleaned = value.strip().replace("T", " ")
            for pattern, size in [("%Y-%m-%d %H:%M:%S", 19), ("%Y-%m-%d %H:%M", 16), ("%Y-%m-%d", 10)]:
                try:
                    return datetime.strptime(cleaned[:size], pattern)
                except ValueError:
                    continue
        return None

    def _fmt_time(self, value, include_seconds=True):
        parsed = self._coerce_dt(value)
        if parsed is None:
            return "-"
        return parsed.strftime("%b %d, %Y %I:%M:%S %p" if include_seconds else "%b %d, %Y %I:%M %p")

    def _fmt_table_time(self, value):
        parsed = self._coerce_dt(value)
        if parsed is None:
            return "-"
        return parsed.strftime("%b %d, %I:%M %p")

    def _fmt_duration(self, seconds):
        try:
            total = max(int(seconds or 0), 0)
        except Exception:
            return "-"
        hours, remainder = divmod(total, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours:
            return f"{hours}h {minutes}m {secs}s"
        if minutes:
            return f"{minutes}m {secs}s"
        return f"{secs}s"

    def _screen_name(self, value):
        labels = {
            "login": "Login",
            "dashboard": "Dashboard",
            "products": "Products",
            "ingredients": "Ingredients",
            "recipes": "Recipes",
            "production": "Production",
            "inventory": "Inventory",
            "pos": "POS",
            "walkin_pos": "Walk-In POS",
            "online_orders": "Online Orders",
            "reports": "Reports",
            "users": "Users",
            "settings": "Settings",
            "transactions": "Transactions",
        }
        key = str(value or "").strip().lower()
        return labels.get(key, value or "-")

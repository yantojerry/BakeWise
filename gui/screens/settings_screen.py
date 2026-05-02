import customtkinter as ctk

from database.user_db import UserDB
from gui.theme import AMBER, AMBER_DARK, get_colors


class SettingsScreen(ctk.CTkFrame):
    APP_VERSION = "v1.1.0"

    def __init__(self, parent, user, on_theme_change=None, on_logout=None):
        self.c = get_colors()
        super().__init__(parent, fg_color=self.c["bg"], corner_radius=0)

        self.pack(fill="both", expand=True)

        self.user = user
        self.on_theme_change = on_theme_change
        self.on_logout = on_logout
        self.active_tab = "appearance"

        self._build_ui()
        self.show_tab("appearance")

    def _build_ui(self):
        c = self.c
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Main wrapper
        self.wrapper = ctk.CTkFrame(self, fg_color="transparent")
        self.wrapper.pack(fill="both", expand=True, padx=24, pady=20)

        # Header
        self.header = ctk.CTkFrame(self.wrapper, fg_color="transparent")
        self.header.pack(fill="x", pady=(0, 14))

        ctk.CTkLabel(
            self.header,
            text="Settings",
            font=ctk.CTkFont("Georgia", 20, "bold"),
            text_color=c["text"],
        ).pack(anchor="w")

        ctk.CTkLabel(
            self.header,
            text="Customize your system preferences and account options.",
            font=ctk.CTkFont("Segoe UI", 12),
            text_color=c["text_muted"],
        ).pack(anchor="w", pady=(4, 0))

        # Horizontal tabs
        self.tabs_bar = ctk.CTkFrame(
            self.wrapper,
            fg_color=c["card"],
            corner_radius=14,
            border_width=1,
            border_color=c["border"],
        )
        self.tabs_bar.pack(fill="x", pady=(0, 14))

        self.tab_buttons = {}

        tabs = [
            ("Appearance", "appearance"),
            ("Account Information", "account"),
            ("About", "about"),
        ]

        for i, (label, key) in enumerate(tabs):
            btn = ctk.CTkButton(
                self.tabs_bar,
                text=label,
                height=40,
                corner_radius=10,
                fg_color="transparent",
                hover_color=c["active_bg"],
                text_color=c["text_gray"],
                font=ctk.CTkFont("Segoe UI", 12, "bold"),
                command=lambda k=key: self.show_tab(k),
            )
            btn.grid(row=0, column=i, padx=8, pady=8, sticky="ew")
            self.tabs_bar.grid_columnconfigure(i, weight=1)
            self.tab_buttons[key] = btn

        # Content area
        self.content = ctk.CTkFrame(
            self.wrapper,
            fg_color=c["card"],
            corner_radius=18,
            border_width=1,
            border_color=c["border"],
        )
        self.content.pack(fill="both", expand=True)

    def _clear_content(self):
        for widget in self.content.winfo_children():
            widget.destroy()

    def _update_tabs(self, active_key):
        c = self.c
        self.active_tab = active_key
        for key, btn in self.tab_buttons.items():
            if key == active_key:
                btn.configure(
                    fg_color=c["blue_dark"],
                    text_color="#FFFFFF",
                    hover=False,
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=c["text_gray"],
                    hover=True,
                    hover_color=c["active_bg"],
                )

    def show_tab(self, key):
        self._update_tabs(key)
        self._clear_content()

        if key == "appearance":
            self._show_appearance()
        elif key == "account":
            self._show_account()
        elif key == "about":
            self._show_about()

    def _section_title(self, title, subtitle):
        c = self.c
        ctk.CTkLabel(
            self.content,
            text=title,
            font=ctk.CTkFont("Segoe UI", 20, "bold"),
            text_color=c["text"],
        ).pack(anchor="w", padx=22, pady=(20, 4))

        ctk.CTkLabel(
            self.content,
            text=subtitle,
            font=ctk.CTkFont("Segoe UI", 12),
            text_color=c["text_muted"],
        ).pack(anchor="w", padx=22, pady=(0, 14))

    def _show_appearance(self):
        c = self.c
        self._section_title(
            "Appearance",
            "Change how BakeWise looks across the system."
        )

        card = ctk.CTkFrame(
            self.content,
            fg_color=c["input"],
            corner_radius=16,
            border_width=1,
            border_color=c["border"],
        )
        card.pack(fill="x", padx=22, pady=(0, 18))

        ctk.CTkLabel(
            card,
            text="Theme Mode",
            font=ctk.CTkFont("Segoe UI", 16, "bold"),
            text_color=c["text"],
        ).pack(anchor="w", padx=18, pady=(16, 4))

        ctk.CTkLabel(
            card,
            text="Choose between light mode and dark mode.",
            font=ctk.CTkFont("Segoe UI", 12),
            text_color=c["text_muted"],
        ).pack(anchor="w", padx=18, pady=(0, 12))

        current_mode = ctk.get_appearance_mode().lower()
        self.theme_var = ctk.StringVar(value=current_mode)

        radios_wrap = ctk.CTkFrame(card, fg_color="transparent")
        radios_wrap.pack(fill="x", padx=18, pady=(0, 18))

        light_box = ctk.CTkFrame(
            radios_wrap,
            fg_color=c["card"],
            corner_radius=12,
            border_width=1,
            border_color=c["border"],
        )
        light_box.pack(fill="x", pady=(0, 10))

        ctk.CTkRadioButton(
            light_box,
            text="Light Mode",
            variable=self.theme_var,
            value="light",
            command=self.apply_theme,
            font=ctk.CTkFont("Segoe UI", 13, "bold"),
            text_color=c["text"],
            fg_color=AMBER,
            hover_color=AMBER_DARK,
        ).pack(anchor="w", padx=14, pady=14)

        dark_box = ctk.CTkFrame(
            radios_wrap,
            fg_color=c["card"],
            corner_radius=12,
            border_width=1,
            border_color=c["border"],
        )
        dark_box.pack(fill="x")

        ctk.CTkRadioButton(
            dark_box,
            text="Dark Mode",
            variable=self.theme_var,
            value="dark",
            command=self.apply_theme,
            font=ctk.CTkFont("Segoe UI", 13, "bold"),
            text_color=c["text"],
            fg_color=AMBER,
            hover_color=AMBER_DARK,
        ).pack(anchor="w", padx=14, pady=14)

    def _show_account(self):
        c = self.c
        self._section_title(
            "Account Information",
            "View your current account details and update your password."
        )

        card = ctk.CTkFrame(
            self.content,
            fg_color=c["input"],
            corner_radius=16,
            border_width=1,
            border_color=c["border"],
        )
        card.pack(fill="x", padx=22, pady=(0, 18))

        username = self.user.get("username", "Admin")
        role = self.user.get("role", "Owner")

        fields = [
            ("Full Name", str(self.user.get("name") or username)),
            ("Username / Email", str(self.user.get("email") or username)),
            ("Role", str(role).capitalize()),
        ]
        contact = self._contact_value()
        if contact:
            fields.append(("Contact Number", contact))
        status = self._status_value()
        if status:
            fields.append(("Status", status))

        for index, (label, value) in enumerate(fields):
            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=18, pady=(16 if index == 0 else 6, 0))

            ctk.CTkLabel(
                row,
                text=label,
                width=170,
                anchor="w",
                font=ctk.CTkFont("Segoe UI", 12, "bold"),
                text_color=c["text_muted"],
            ).pack(side="left")

            ctk.CTkLabel(
                row,
                text=value,
                anchor="w",
                font=ctk.CTkFont("Segoe UI", 12),
                text_color=c["text"],
            ).pack(side="left", fill="x", expand=True)

        ctk.CTkFrame(card, fg_color=c["border"], height=1).pack(fill="x", padx=18, pady=(16, 14))

        ctk.CTkLabel(
            card,
            text="Change Password",
            font=ctk.CTkFont("Segoe UI", 14, "bold"),
            text_color=c["text"],
        ).pack(anchor="w", padx=18, pady=(0, 8))

        password_row = ctk.CTkFrame(card, fg_color="transparent")
        password_row.pack(fill="x", padx=18)
        password_entry = ctk.CTkEntry(
            password_row,
            height=40,
            show="*",
            placeholder_text="Enter new password",
            placeholder_text_color=c["text_muted"],
            fg_color=c["card"],
            border_color=c["border"],
            text_color=c["text"],
            corner_radius=8,
            font=ctk.CTkFont("Segoe UI", 12),
        )
        password_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        password_status = ctk.CTkLabel(
            card,
            text="",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=c["text_muted"],
        )
        password_status.pack(anchor="w", padx=18, pady=(8, 0))

        ctk.CTkButton(
            password_row,
            text="Update",
            width=110,
            height=40,
            fg_color=c["blue_dark"],
            hover_color=c["blue"],
            text_color="#FFFFFF",
            corner_radius=8,
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            command=lambda: self._change_password(password_entry, password_status),
        ).pack(side="right")

        if self.on_logout:
            ctk.CTkButton(
                card,
                text="Logout",
                height=42,
                fg_color=c["error_bg"],
                hover_color=c["error_hover"],
                text_color=c["error"],
                corner_radius=8,
                font=ctk.CTkFont("Segoe UI", 12, "bold"),
                command=self.on_logout,
            ).pack(fill="x", padx=18, pady=(18, 16))
        else:
            ctk.CTkLabel(card, text="", text_color=c["text"]).pack(pady=8)

    def _show_about(self):
        c = self.c
        self._section_title(
            "About",
            "Basic information about the BakeWise system."
        )

        card = ctk.CTkFrame(
            self.content,
            fg_color=c["input"],
            corner_radius=16,
            border_width=1,
            border_color=c["border"],
        )
        card.pack(fill="x", padx=22, pady=(0, 18))

        info = [
            ("System Name", "BakeWise"),
            ("Version", self.APP_VERSION),
            ("Development Team", ""),
            ("Team Leader", "Litana, John Michael C."),
            ("Members", "Cal, John Erick S.\nCalleja, Justin Jose L.\nDelos Reyes, Princess Ann A.\nNucos, Ericka R."),
        ]

        for i, (label, value) in enumerate(info):
            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=18, pady=(16 if i == 0 else 8, 0))

            ctk.CTkLabel(
                row,
                text=label,
                width=170,
                anchor="w",
                font=ctk.CTkFont("Segoe UI", 12, "bold"),
                text_color=c["text_muted"],
            ).pack(side="left")

            ctk.CTkLabel(
                row,
                text=value,
                anchor="w",
                justify="left",
                font=ctk.CTkFont("Segoe UI", 12),
                text_color=c["text"],
            ).pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(card, text="").pack(pady=8)

    def _contact_value(self):
        for key in ("contact_number", "contact", "phone", "mobile"):
            value = self.user.get(key)
            if value not in (None, ""):
                return str(value)
        return None

    def _status_value(self):
        if "status" in self.user and self.user.get("status") not in (None, ""):
            return str(self.user.get("status")).capitalize()
        if "is_active" in self.user:
            return "Active" if bool(self.user.get("is_active")) else "Inactive"
        return None

    def _change_password(self, entry, status_label):
        new_password = entry.get().strip()
        if not new_password:
            status_label.configure(text="Enter a new password.", text_color=self.c["error"])
            return

        user_id = self.user.get("user_id") or self.user.get("id")
        if not user_id:
            status_label.configure(text="Current user ID is unavailable.", text_color=self.c["error"])
            return

        try:
            updated = UserDB.update_user(user_id, password=new_password)
        except Exception as exc:
            status_label.configure(text=f"Password update failed: {exc}", text_color=self.c["error"])
            return

        if updated:
            self.user["password"] = new_password
            entry.delete(0, "end")
            status_label.configure(text="Password updated.", text_color=self.c["success"])
        else:
            status_label.configure(text="No password change was saved.", text_color=self.c["text_muted"])

    def apply_theme(self):
        mode = self.theme_var.get()
        if self.on_theme_change:
            self.on_theme_change(mode)

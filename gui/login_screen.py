import customtkinter as ctk
from database.user_db import UserDB
from gui.async_utils import run_in_thread

# ── Theme ─────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

# ── Colors ────────────────────────────────────────────────
BG_DARK     = "#05070B"
BG_CARD     = "#10131A"
BG_INPUT    = "#151922"
AMBER       = "#F59E0B"
AMBER_DARK  = "#B45309"
AMBER_LIGHT = "#FCD34D"
TEXT_WHITE  = "#F8FAFC"
TEXT_GRAY   = "#CBD5E1"
TEXT_MUTED  = "#8B98AA"
BORDER      = "#273142"
ERROR_RED   = "#EF4444"
SUCCESS     = "#10B981"
LOGIN_TIMEOUT_MS = 10000


class LoginScreen(ctk.CTkFrame):
    def __init__(self, parent, on_login_success):
        super().__init__(parent, fg_color=BG_DARK, corner_radius=0)
        self.on_login_success = on_login_success
        self._login_token = None
        self._login_timeout_job = None
        self._build_ui()

    def _build_ui(self):
        self.pack(fill="both", expand=True)

        # ── Left panel — branding ──────────────────────────
        left = ctk.CTkFrame(self, fg_color="#030406", corner_radius=0, width=448)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

        # Decorative amber accent bar
        accent = ctk.CTkFrame(left, fg_color=AMBER, corner_radius=0, width=6)
        accent.pack(side="left", fill="y")

        branding = ctk.CTkFrame(left, fg_color="transparent")
        branding.place(relx=0.5, rely=0.5, anchor="center")

        # Logo circle
        logo_frame = ctk.CTkFrame(branding, fg_color=AMBER, corner_radius=999,
                                  width=88, height=88)
        logo_frame.pack(pady=(0, 20))
        logo_frame.pack_propagate(False)
        ctk.CTkLabel(logo_frame, text="🍞", font=("Segoe UI Emoji", 36),
                     fg_color="transparent").place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(branding, text="BakeWise",
                     font=ctk.CTkFont("Georgia", 42, "bold"),
                     text_color=TEXT_WHITE).pack()

        ctk.CTkLabel(branding, text="Bakery Management System",
                     font=ctk.CTkFont("Segoe UI", 13),
                     text_color=TEXT_MUTED).pack(pady=(4, 0))

        # Divider
        ctk.CTkFrame(branding, fg_color=BORDER, height=1, width=200).pack(pady=28)

        # Feature tags
        features = ["Point of Sale", "Inventory Tracking",
                    "Production Logging", "Sales Reports"]
        for f in features:
            row = ctk.CTkFrame(branding, fg_color="transparent")
            row.pack(anchor="w", pady=3)
            ctk.CTkLabel(row, text="▸", font=ctk.CTkFont("Segoe UI", 12),
                         text_color=AMBER, width=20).pack(side="left")
            ctk.CTkLabel(row, text=f, font=ctk.CTkFont("Segoe UI", 12),
                         text_color=TEXT_GRAY).pack(side="left")

        # Version tag
        ctk.CTkLabel(left, text="v1.1.0",
                     font=ctk.CTkFont("Segoe UI", 10),
                     text_color=TEXT_MUTED).place(relx=0.5, rely=0.95, anchor="center")

        # ── Right panel — login form ───────────────────────
        right = ctk.CTkFrame(self, fg_color="#0C1118", corner_radius=0)
        right.pack(side="right", fill="both", expand=True)

        form = ctk.CTkFrame(right, fg_color="transparent")
        form.place(relx=0.5, rely=0.5, anchor="center")

        # Header
        ctk.CTkLabel(form, text="Welcome back",
                     font=ctk.CTkFont("Georgia", 32, "bold"),
                     text_color=TEXT_WHITE).pack(anchor="w")
        ctk.CTkLabel(form, text="Sign in to your account to continue",
                     font=ctk.CTkFont("Segoe UI", 13),
                     text_color=TEXT_MUTED).pack(anchor="w", pady=(4, 32))

        # Card
        card = ctk.CTkFrame(form, fg_color=BG_CARD, corner_radius=16,
                            border_width=1, border_color=BORDER)
        card.pack(padx=0, pady=0, ipadx=32, ipady=32)

        # Username
        ctk.CTkLabel(card, text="USERNAME",
                     font=ctk.CTkFont("Segoe UI", 10, "bold"),
                     text_color=TEXT_MUTED).pack(anchor="w", padx=32, pady=(32, 6))
        self.username_entry = ctk.CTkEntry(
            card, width=336, height=48,
            fg_color=BG_INPUT, border_color=BORDER, border_width=1,
            text_color=TEXT_WHITE, corner_radius=8,
            font=ctk.CTkFont("Segoe UI", 13),
            placeholder_text="Enter your username",
            placeholder_text_color=TEXT_MUTED
        )
        self.username_entry.pack(padx=32)

        # Password
        ctk.CTkLabel(card, text="PASSWORD",
                     font=ctk.CTkFont("Segoe UI", 10, "bold"),
                     text_color=TEXT_MUTED).pack(anchor="w", padx=32, pady=(20, 6))
        self.password_entry = ctk.CTkEntry(
            card, width=336, height=48,
            fg_color=BG_INPUT, border_color=BORDER, border_width=1,
            text_color=TEXT_WHITE, corner_radius=8,
            font=ctk.CTkFont("Segoe UI", 13),
            placeholder_text="Enter your password",
            placeholder_text_color=TEXT_MUTED,
            show="●"
        )
        self.password_entry.pack(padx=32)

        # Error label
        self.error_label = ctk.CTkLabel(
            card, text="", font=ctk.CTkFont("Segoe UI", 11),
            text_color=ERROR_RED
        )
        self.error_label.pack(pady=(8, 0))

        # Login button
        self.login_btn = ctk.CTkButton(
            card, text="SIGN IN", width=336, height=50,
            fg_color=AMBER, hover_color=AMBER_DARK,
            text_color="#0F0F0F", corner_radius=8,
            font=ctk.CTkFont("Segoe UI", 13, "bold"),
            command=self._handle_login
        )
        self.login_btn.pack(padx=32, pady=(20, 32))

        # Bind Enter key
        self.username_entry.bind("<Return>", lambda e: self.password_entry.focus())
        self.password_entry.bind("<Return>", lambda e: self._handle_login())

        # Focus username on load
        self.after(100, self.username_entry.focus)

        # Footer
        ctk.CTkLabel(right,
                     text="© 2026 BakeWise — Bakery Management System",
                     font=ctk.CTkFont("Segoe UI", 10),
                     text_color=TEXT_MUTED).place(relx=0.5, rely=0.95, anchor="center")

    def _handle_login(self):
        if self.login_btn.cget("state") == "disabled":
            return

        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()

        if not username or not password:
            self._show_error("Please enter both username and password.")
            return

        self._show_error("")
        self.login_btn.configure(text="Signing in...", state="disabled")
        token = object()
        self._login_token = token
        self._schedule_login_timeout(token)
        self.after(300, lambda: self._start_login_request(username, password, token))

    def _attempt_login(self, username, password):
        try:
            user = UserDB.get_user(username, prefer_direct=True)
            stored_password = "" if not user else str(user.get("password") or "")
            return (
                {"ok": True, "user": user}
                if user and stored_password == password
                else {"ok": False, "message": "Invalid username or password."}
            )
        except Exception as exc:
            raise

    def _start_login_request(self, username, password, token):
        if self._login_token is not token or not self.winfo_exists():
            return

        try:
            run_in_thread(
                self,
                lambda: self._attempt_login(username, password),
                on_success=self._handle_login_result,
                on_error=self._handle_login_error,
                is_current=lambda: self._login_token is token,
            )
        except Exception as exc:
            try:
                result = self._attempt_login(username, password)
            except Exception as sync_exc:
                self._handle_login_error(sync_exc)
            else:
                self._handle_login_result(result)

    def _handle_login_result(self, result):
        self._clear_login_timeout()

        if not result.get("ok"):
            self._login_token = None
            self._show_error(result.get("message", "Invalid username or password."))
            self._reset_login_state(clear_password=True)
            return

        user = result["user"]
        self.login_btn.configure(text="✓  Welcome!", fg_color=SUCCESS)
        self.after(600, lambda: self._complete_successful_login(user))

    def _complete_successful_login(self, user):
        if not self.winfo_exists():
            return

        try:
            self.on_login_success(user)
        except Exception:
            self._login_token = None
            self._show_error("Unable to open the main window.")
            self._reset_login_state()

    def _handle_login_error(self, exc):
        self._login_token = None
        self._clear_login_timeout()
        print(f"[BakeWise] Login failed: {exc}")
        self._show_error("Database connection failed. Please try again.")
        self._reset_login_state()

    def _schedule_login_timeout(self, token):
        self._clear_login_timeout()
        self._login_timeout_job = self.after(
            LOGIN_TIMEOUT_MS,
            lambda: self._handle_login_timeout(token),
        )

    def _handle_login_timeout(self, token):
        self._login_timeout_job = None
        if self._login_token is not token or not self.winfo_exists():
            return

        self._login_token = None
        self._show_error("Sign in timed out. Please try again.")
        self._reset_login_state()

    def _clear_login_timeout(self):
        if self._login_timeout_job is not None:
            self.after_cancel(self._login_timeout_job)
            self._login_timeout_job = None

    def _reset_login_state(self, clear_password=False):
        self.login_btn.configure(text="SIGN IN", state="normal", fg_color=AMBER)
        if clear_password:
            self.password_entry.delete(0, "end")
            self.password_entry.focus()

    def _show_error(self, message):
        self.error_label.configure(text=message)


# ── Standalone test ───────────────────────────────────────
if __name__ == "__main__":
    app = ctk.CTk()
    app.title("BakeWise — Login")
    app.geometry("900x580")
    app.resizable(False, False)

    def on_success(user):
        app.destroy()

    LoginScreen(app, on_login_success=on_success)
    app.mainloop()

import customtkinter as ctk

from gui.theme import AMBER, AMBER_DARK, get_colors

MENU_ITEMS = {
    "owner": [
        ("Dashboard", "📊", "dashboard"),
        ("Products", "🧁", "products"),
        ("Ingredients", "🌾", "ingredients"),
        ("Recipes", "📋", "recipes"),
        ("Production", "🏭", "production"),
        ("Inventory", "📦", "inventory"),
        ("Walk-In POS", "🛒", "walkin_pos"),
        ("Online Orders", "🌐", "online_orders"),
        ("Reports", "📈", "reports"),
        ("Users", "👥", "users"),
        ("Settings", "⚙️", "settings"),
    ],
    "cashier": [
        ("Walk-In POS", "🛒", "walkin_pos"),
        ("Online Orders", "🌐", "online_orders"),
        ("Transactions", "🧾", "transactions"),
    ],
    "baker": [
        ("Production", "🏭", "production"),
        ("Inventory", "📦", "inventory"),
        ("Ingredients", "🌾", "ingredients"),
    ],
}


class MainWindow(ctk.CTkFrame):
    def __init__(self, parent, user, on_logout):
        self.c = get_colors()
        super().__init__(parent, fg_color=self.c["bg"], corner_radius=0)
        self.user = user
        self.on_logout = on_logout
        self.is_dark = ctk.get_appearance_mode() == "Dark"
        self.active_key = None
        self.nav_buttons = {}
        self.current_screen = None
        self.current_screen_key = None
        self.screen_cache = {}
        self.cacheable_screens = {
            "dashboard",
            "inventory",
            "production",
            "recipes",
            "reports",
            "users",
        }
        self.pack(fill="both", expand=True)
        self._build_ui()

        role = user.get("role", "owner")
        first = MENU_ITEMS.get(role, [])[0][2]
        self._navigate(first)

    def _build_ui(self):
        c = self.c

        self.sidebar = ctk.CTkFrame(
            self,
            fg_color=c["sidebar"],
            corner_radius=0,
            width=248,
            border_width=1,
            border_color=c["border"],
        )
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        ctk.CTkFrame(
            self.sidebar,
            fg_color=AMBER,
            corner_radius=0,
            width=4
        ).pack(side="left", fill="y")

        sidebar_inner = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        sidebar_inner.pack(fill="both", expand=True)

        logo_area = ctk.CTkFrame(sidebar_inner, fg_color="transparent", height=76)
        logo_area.pack(fill="x")
        logo_area.pack_propagate(False)

        ctk.CTkLabel(
            logo_area,
            text="🍞  BakeWise",
            font=ctk.CTkFont("Georgia", 21, "bold"),
            text_color=c["text"],
        ).pack(padx=22, pady=(20, 14), anchor="w")

        ctk.CTkFrame(sidebar_inner, fg_color=c["border"], height=1).pack(
            fill="x", padx=18, pady=(0, 12)
        )

        role = self.user.get("role", "").upper()
        badge_colors = {"OWNER": AMBER, "CASHIER": "#3B82F6", "BAKER": "#10B981"}
        badge_color = badge_colors.get(role, AMBER)

        badge_frame = ctk.CTkFrame(sidebar_inner, fg_color="transparent")
        badge_frame.pack(fill="x", padx=16, pady=(0, 12))

        ctk.CTkLabel(
            badge_frame,
            text=f"  {role}  ",
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            fg_color=badge_color,
            text_color="#0F0F0F",
            corner_radius=999,
        ).pack(anchor="w")

        nav_frame = ctk.CTkFrame(sidebar_inner, fg_color="transparent")
        nav_frame.pack(fill="x", padx=10, pady=(0, 8))

        role_key = self.user.get("role", "owner")
        for label, icon, key in MENU_ITEMS.get(role_key, []):
            btn = ctk.CTkButton(
                nav_frame,
                text=f"  {icon}  {label}",
                anchor="w",
                height=42,
                corner_radius=12,
                fg_color=c["sidebar"],
                hover_color=c["card_hover"],
                text_color=c["text_gray"],
                border_width=1,
                border_color=c["sidebar"],
                font=ctk.CTkFont("Segoe UI", 12),
                command=lambda k=key: self._navigate(k),
            )
            btn.pack(fill="x", pady=3)
            self.nav_buttons[key] = btn

        bottom = ctk.CTkFrame(sidebar_inner, fg_color="transparent")
        bottom.pack(fill="x", padx=18, pady=18, side="bottom")

        ctk.CTkFrame(bottom, fg_color=c["border"], height=1).pack(fill="x", pady=(0, 12))

        user_card = ctk.CTkFrame(
            bottom,
            fg_color=c["card"],
            corner_radius=14,
            border_width=1,
            border_color=c["border"],
        )
        user_card.pack(fill="x", pady=(0, 10))

        username = self.user.get("username", "User").capitalize()
        ctk.CTkLabel(
            user_card,
            text=f"👤  {username}",
            font=ctk.CTkFont("Segoe UI", 12),
            text_color=c["text"],
        ).pack(anchor="w", padx=14, pady=(12, 2))
        ctk.CTkLabel(
            user_card,
            text=role.title(),
            font=ctk.CTkFont("Segoe UI", 10),
            text_color=c["text_muted"],
        ).pack(anchor="w", padx=14, pady=(0, 12))

        ctk.CTkButton(
            bottom,
            text="Sign Out",
            height=40,
            fg_color=c["input"],
            hover_color=c["error_hover"],
            text_color=c["error"],
            corner_radius=12,
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            command=self._logout,
        ).pack(fill="x")

        self.content = ctk.CTkFrame(self, fg_color=self.c["bg"], corner_radius=0)
        self.content.pack(side="right", fill="both", expand=True)

    def _navigate(self, key):
        c = self.c
        self.active_key = key

        top = self.winfo_toplevel()
        if hasattr(top, "hide_keyboard"):
            top.hide_keyboard()
        if hasattr(top, "mark_active_screen"):
            top.mark_active_screen(key)

        for nav_key, btn in self.nav_buttons.items():
            if nav_key == key:
                btn.configure(
                    fg_color=c["card"],
                    text_color=AMBER if self.is_dark else AMBER_DARK,
                    border_color=c["focus"],
                )
            else:
                btn.configure(
                    fg_color=c["sidebar"],
                    text_color=c["text_gray"],
                    border_color=c["sidebar"],
                )

        if key == self.current_screen_key and self.current_screen and self.current_screen.winfo_exists():
            self._show_screen(self.current_screen, key)
            return

        self._hide_current_screen()
        screen = self._load_screen(key)
        if screen is None:
            return

        self.current_screen = screen
        self.current_screen_key = key
        self._show_screen(screen, key)

    def _hide_current_screen(self):
        if not self.current_screen or not self.current_screen.winfo_exists():
            return

        if hasattr(self.current_screen, "on_hide"):
            try:
                self.current_screen.on_hide()
            except Exception:
                pass

        if self.current_screen_key in self.cacheable_screens:
            self.current_screen.pack_forget()
        else:
            self.current_screen.destroy()

    def _show_screen(self, screen, key):
        if screen.winfo_exists():
            screen.pack(fill="both", expand=True)
            if hasattr(screen, "on_show"):
                try:
                    screen.on_show()
                except Exception:
                    pass

    def _load_screen(self, key):
        if key in self.cacheable_screens:
            cached = self.screen_cache.get(key)
            if cached and cached.winfo_exists():
                return cached

        try:
            if key == "dashboard":
                from gui.screens.dashboard_screen import DashboardScreen
                screen = DashboardScreen(self.content, self.user, on_navigate=self._navigate)

            elif key == "products":
                from gui.screens.products_screen import ProductsScreen
                screen = ProductsScreen(self.content, self.user)

            elif key == "ingredients":
                from gui.screens.ingredients_screen import IngredientsScreen
                screen = IngredientsScreen(self.content, self.user)

            elif key == "recipes":
                from gui.screens.recipes_screen import RecipesScreen
                screen = RecipesScreen(self.content, self.user)

            elif key == "production":
                from gui.screens.production_screen import ProductionScreen
                screen = ProductionScreen(self.content, self.user)

            elif key == "inventory":
                from gui.screens.inventory_screen import InventoryScreen
                screen = InventoryScreen(self.content, self.user)

            elif key == "walkin_pos":
                from gui.screens.pos_screen import POSScreen
                screen = POSScreen(
                    self.content,
                    self.user,
                    workspace_mode="Walk-In",
                    locked_workspace="Walk-In",
                    show_source_switcher=False,
                )

            elif key == "online_orders":
                from gui.screens.pos_screen import POSScreen
                screen = POSScreen(
                    self.content,
                    self.user,
                    workspace_mode="Online Orders",
                    locked_workspace="Online Orders",
                    show_source_switcher=False,
                )

            elif key == "pos":
                from gui.screens.pos_screen import POSScreen
                screen = POSScreen(self.content, self.user)

            elif key == "reports":
                from gui.screens.reports_screen import ReportsScreen
                screen = ReportsScreen(self.content, self.user)

            elif key == "users":
                from gui.screens.users_screen import UsersScreen
                screen = UsersScreen(self.content, self.user)

            elif key == "transactions":
                from gui.screens.transactions_screen import TransactionsScreen
                screen = TransactionsScreen(self.content, self.user)

            elif key == "settings":
                from gui.screens.settings_screen import SettingsScreen
                screen = SettingsScreen(
                    self.content,
                    self.user,
                    on_theme_change=self._on_theme_change,
                    on_logout=self._logout,
                )

            else:
                screen = self._placeholder(key)

        except Exception as e:
            screen = self._placeholder(f"{key}\nError: {e}")

        if key in self.cacheable_screens and screen.winfo_exists():
            self.screen_cache[key] = screen

        return screen

    def _on_theme_change(self, mode):
        ctk.set_appearance_mode(mode)

        top = self.winfo_toplevel()
        if hasattr(top, "hide_keyboard"):
            top.hide_keyboard()

        for widget in self.master.winfo_children():
            widget.destroy()

        MainWindow(self.master, user=self.user, on_logout=self.on_logout)

    def _placeholder(self, key):
        c = self.c
        frame = ctk.CTkFrame(self.content, fg_color="transparent")

        ctk.CTkLabel(
            frame,
            text=f"🚧  {key.capitalize()} screen\ncoming soon",
            font=ctk.CTkFont("Segoe UI", 20),
            text_color=c["text_muted"],
            justify="center",
        ).place(relx=0.5, rely=0.5, anchor="center")
        return frame

    def _toggle_theme(self):
        top = self.winfo_toplevel()
        if hasattr(top, "hide_keyboard"):
            top.hide_keyboard()

        if self.is_dark:
            ctk.set_appearance_mode("light")
            self.is_dark = False
        else:
            ctk.set_appearance_mode("dark")
            self.is_dark = True

        for widget in self.master.winfo_children():
            widget.destroy()

        MainWindow(self.master, user=self.user, on_logout=self.on_logout)

    def _logout(self):
        top = self.winfo_toplevel()
        if hasattr(top, "hide_keyboard"):
            top.hide_keyboard()

        for widget in self.master.winfo_children():
            widget.destroy()

        self.on_logout()

import customtkinter as ctk
from gui.login_screen import LoginScreen
from database.db import probe_and_connect, set_status_callback


def _on_db_status(source, status, color):
    label = f"[BakeWise DB] {source}"
    if status:
        label += f" — {status}"
    print(label)


set_status_callback(_on_db_status)

print("[BakeWise] Checking database connection...")
probe_and_connect()


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")


class BakeWiseApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("BakeWise — Bakery Management System")
        self.geometry("1280x780")
        self.minsize(1100, 680)
        self.current_user = None
        self._show_login()

    def _show_login(self):
        for widget in self.winfo_children():
            widget.destroy()
        LoginScreen(self, on_login_success=self._on_login_success)

    def _on_login_success(self, user):
        self.current_user = user
        for widget in self.winfo_children():
            widget.destroy()
        from gui.main_window import MainWindow

        MainWindow(self, user=user, on_logout=self._show_login)


if __name__ == "__main__":
    app = BakeWiseApp()
    app.mainloop()

import customtkinter as ctk
from database.ingredient_db import IngredientDB
from gui.async_utils import run_in_thread
from gui.theme import get_colors


class IngredientsScreen(ctk.CTkFrame):
    def __init__(self, parent, user):
        self.c = get_colors()
        super().__init__(parent, fg_color=self.c["bg"], corner_radius=0)
        self.user = user
        self._all_ingredients = []
        self._ingredients_load_token = None
        self.pack(fill="both", expand=True)
        self._build_ui()

    def _build_ui(self):
        c = self.c

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=32, pady=(26, 0))

        ctk.CTkLabel(
            header,
            text="Ingredients",
            font=ctk.CTkFont("Georgia", 30, "bold"),
            text_color=c["text"]
        ).pack(side="left")

        right = ctk.CTkFrame(header, fg_color="transparent")
        right.pack(side="right")

        ctk.CTkButton(
            right,
            text="+ Add Ingredient",
            width=165,
            height=40,
            fg_color=c["amber"],
            hover_color=c["amber_dark"],
            text_color="#0F0F0F",
            corner_radius=10,
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            command=self._open_add_modal
        ).pack(side="left", padx=(0, 12))

        self._search_var = ctk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._apply_filter())

        ctk.CTkEntry(
            right,
            textvariable=self._search_var,
            placeholder_text="Search ingredients...",
            width=220,
            height=38,
            fg_color=c["input"],
            border_color=c["border"],
            border_width=1,
            text_color=c["text"],
            corner_radius=10,
            font=ctk.CTkFont("Segoe UI", 12)
        ).pack(side="left")

        ctk.CTkFrame(self, fg_color=c["border"], height=1).pack(fill="x", padx=32, pady=(16, 0))

        filter_row = ctk.CTkFrame(self, fg_color="transparent")
        filter_row.pack(fill="x", padx=32, pady=(14, 0))

        self._filter_var = ctk.StringVar(value="All")
        ctk.CTkOptionMenu(
            filter_row,
            variable=self._filter_var,
            values=["All", "OK", "Low Stock", "Out of Stock"],
            width=150,
            height=36,
            fg_color=c["input"],
            button_color=c["border"],
            button_hover_color=c["amber_dark"],
            text_color=c["text"],
            dropdown_fg_color=c["card"],
            dropdown_text_color=c["text"],
            corner_radius=10,
            font=ctk.CTkFont("Segoe UI", 12),
            command=lambda _: self._apply_filter()
        ).pack(side="left")

        table_card = ctk.CTkFrame(
            self,
            fg_color=c["card"],
            corner_radius=14,
            border_width=1,
            border_color=c["border"]
        )
        table_card.pack(fill="both", expand=True, padx=32, pady=(14, 24))

        thead = ctk.CTkFrame(
            table_card,
            fg_color=c["thead"],
            height=46,
            corner_radius=0
        )
        thead.pack(fill="x", padx=1, pady=(1, 0))
        thead.pack_propagate(False)

        columns = [
            ("ID", 70),
            ("Name", 240),
            ("Unit", 110),
            ("Quantity", 130),
            ("Reorder Level", 150),
            ("Status", 120),
            ("Actions", 160),
        ]

        for col, width in columns:
            ctk.CTkLabel(
                thead,
                text=col,
                width=width,
                font=ctk.CTkFont("Segoe UI", 11, "bold"),
                text_color=c["text_muted"],
                anchor="w"
            ).pack(side="left", padx=10)

        self.rows_frame = ctk.CTkScrollableFrame(
            table_card,
            fg_color="transparent",
            corner_radius=0
        )
        self.rows_frame.pack(fill="both", expand=True, padx=1, pady=(0, 1))

        self._load_ingredients()

    def _load_ingredients(self):
        token = object()
        self._ingredients_load_token = token
        self._show_rows_message("Loading ingredients...")
        run_in_thread(
            self,
            lambda: IngredientDB.get_all_ingredients() or [],
            on_success=lambda ingredients: self._apply_loaded_ingredients(token, ingredients),
            on_error=lambda exc: self._handle_ingredients_load_error(token, exc),
            is_current=lambda: self._ingredients_load_token is token,
        )

    def _apply_loaded_ingredients(self, token, ingredients):
        if self._ingredients_load_token is not token:
            return
        self._all_ingredients = list(ingredients or [])
        self._apply_filter()

    def _handle_ingredients_load_error(self, token, _exc):
        if self._ingredients_load_token is not token:
            return
        self._all_ingredients = []
        self._show_rows_message("Ingredients could not be loaded.")

    def _show_rows_message(self, message):
        for widget in self.rows_frame.winfo_children():
            widget.destroy()
        ctk.CTkLabel(
            self.rows_frame,
            text=message,
            font=ctk.CTkFont("Segoe UI", 13),
            text_color=self.c["text_muted"],
        ).pack(pady=40)

    def _apply_filter(self):
        query = self._search_var.get().lower().strip()
        status = self._filter_var.get()

        filtered = []
        for ing in self._all_ingredients:
            s = ing.status if hasattr(ing, "status") else ("Low Stock" if ing.is_low_stock() else "OK")

            if status != "All" and s != status:
                continue
            if query and query not in ing.name.lower() and query not in ing.unit.lower():
                continue
            filtered.append(ing)

        self._render_rows(filtered)

    def _render_rows(self, ingredients):
        c = self.c

        for w in self.rows_frame.winfo_children():
            w.destroy()

        if not ingredients:
            empty_wrap = ctk.CTkFrame(self.rows_frame, fg_color="transparent")
            empty_wrap.pack(fill="both", expand=True, pady=48)

            ctk.CTkLabel(
                empty_wrap,
                text="No ingredients found.",
                font=ctk.CTkFont("Segoe UI", 13),
                text_color=c["text_muted"]
            ).pack()
            return

        for i, ing in enumerate(ingredients):
            row_bg = c["card"] if i % 2 == 0 else c["row_alt"]

            row = ctk.CTkFrame(
                self.rows_frame,
                fg_color=row_bg,
                corner_radius=0,
                height=50
            )
            row.pack(fill="x")
            row.pack_propagate(False)

            if hasattr(ing, "status"):
                s = ing.status
            else:
                s = "Low Stock" if ing.is_low_stock() else "OK"

            is_low = s == "Low Stock"
            is_out = s == "Out of Stock"

            status_color = c["error"] if is_out else (c["warning"] if is_low else c["success"])
            qty_color = c["error"] if is_out else (c["warning"] if is_low else c["text"])

            ctk.CTkLabel(
                row, text=str(ing.ingredient_id), width=70,
                font=ctk.CTkFont("Segoe UI", 12),
                text_color=c["amber"], anchor="w"
            ).pack(side="left", padx=10)

            ctk.CTkLabel(
                row, text=ing.name, width=240,
                font=ctk.CTkFont("Segoe UI", 12, "bold"),
                text_color=c["text"], anchor="w"
            ).pack(side="left", padx=10)

            ctk.CTkLabel(
                row, text=ing.unit, width=110,
                font=ctk.CTkFont("Segoe UI", 12),
                text_color=c["text_gray"], anchor="w"
            ).pack(side="left", padx=10)

            ctk.CTkLabel(
                row, text=str(ing.quantity), width=130,
                font=ctk.CTkFont("Segoe UI", 12),
                text_color=qty_color, anchor="w"
            ).pack(side="left", padx=10)

            ctk.CTkLabel(
                row, text=str(ing.reorder_level), width=150,
                font=ctk.CTkFont("Segoe UI", 12),
                text_color=c["text_gray"], anchor="w"
            ).pack(side="left", padx=10)

            badge_bg = c["error_bg"] if is_out else (c["warning_bg"] if is_low else c["success_bg"])
            badge = ctk.CTkFrame(row, fg_color=badge_bg, corner_radius=7, width=105, height=28)
            badge.pack(side="left", padx=10)
            badge.pack_propagate(False)

            ctk.CTkLabel(
                badge,
                text=s,
                font=ctk.CTkFont("Segoe UI", 10, "bold"),
                text_color=status_color
            ).place(relx=0.5, rely=0.5, anchor="center")

            actions = ctk.CTkFrame(row, fg_color="transparent")
            actions.pack(side="left", padx=10)

            ctk.CTkButton(
                actions,
                text="Edit",
                width=64,
                height=30,
                fg_color=c["success_bg"],
                hover_color=c["success_hover"],
                text_color=c["success"],
                corner_radius=7,
                font=ctk.CTkFont("Segoe UI", 11),
                command=lambda iid=ing.ingredient_id: self._open_edit_modal(iid)
            ).pack(side="left", padx=(0, 6))

            ctk.CTkButton(
                actions,
                text="Delete",
                width=64,
                height=30,
                fg_color=c["error_bg"],
                hover_color=c["error_hover"],
                text_color=c["error"],
                corner_radius=7,
                font=ctk.CTkFont("Segoe UI", 11),
                command=lambda iid=ing.ingredient_id, n=ing.name: self._delete(iid, n)
            ).pack(side="left")

    def _open_add_modal(self):
        self._open_modal("Add Ingredient")

    def _open_edit_modal(self, ingredient_id):
        ing = IngredientDB.get_ingredient(ingredient_id)
        if ing:
            self._open_modal("Edit Ingredient", ing)

    def _open_modal(self, title, ingredient=None):
        c = self.c

        modal = ctk.CTkToplevel(self)
        modal.title(title)
        modal.geometry("520x560")
        modal.resizable(False, False)
        modal.configure(fg_color=c["card"])
        modal.grab_set()

        ctk.CTkLabel(
            modal,
            text=title,
            font=ctk.CTkFont("Georgia", 30, "bold"),
            text_color=c["text"]
        ).pack(pady=(28, 24))

        fields = {}

        for label, key, default in [
            ("Ingredient Name", "name", ingredient.name if ingredient else ""),
            ("Unit (kg/pcs/liters)", "unit", ingredient.unit if ingredient else ""),
            ("Quantity", "quantity", str(ingredient.quantity) if ingredient else ""),
            ("Reorder Level", "reorder", str(ingredient.reorder_level) if ingredient else ""),
        ]:
            ctk.CTkLabel(
                modal,
                text=label,
                font=ctk.CTkFont("Segoe UI", 12),
                text_color=c["text_muted"]
            ).pack(anchor="w", padx=40, pady=(8, 6))

            entry = ctk.CTkEntry(
                modal,
                width=480,
                height=50,
                fg_color=c["input"],
                border_color=c["border"],
                border_width=1,
                text_color=c["text"],
                corner_radius=12,
                font=ctk.CTkFont("Segoe UI", 13)
            )
            entry.insert(0, default)
            entry.pack(padx=40)
            fields[key] = entry

        error_lbl = ctk.CTkLabel(
            modal,
            text="",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=c["error"]
        )
        error_lbl.pack(pady=(10, 0))

        def save():
            try:
                name = fields["name"].get().strip()
                unit = fields["unit"].get().strip()
                qty = float(fields["quantity"].get().strip())
                reorder = float(fields["reorder"].get().strip())

                if not name or not unit:
                    error_lbl.configure(text="Name and unit are required.")
                    return

                if ingredient:
                    IngredientDB.update_ingredient(ingredient.ingredient_id, qty, reorder)
                else:
                    IngredientDB.add_ingredient(name, unit, qty, reorder)

                modal.destroy()
                self._load_ingredients()

            except ValueError:
                error_lbl.configure(text="Invalid quantity or reorder level.")

        ctk.CTkButton(
            modal,
            text="Save",
            width=444,
            height=48,
            fg_color=c["amber"],
            hover_color=c["amber_dark"],
            text_color="#0F0F0F",
            corner_radius=10,
            font=ctk.CTkFont("Segoe UI", 13, "bold"),
            command=save
        ).pack(padx=32, pady=22)

    def _delete(self, ingredient_id, name):
        c = self.c

        confirm = ctk.CTkToplevel(self)
        confirm.title("Confirm Delete")
        confirm.geometry("380x190")
        confirm.resizable(False, False)
        confirm.configure(fg_color=c["card"])
        confirm.grab_set()

        ctk.CTkLabel(
            confirm,
            text=f"Delete '{name}'?",
            font=ctk.CTkFont("Segoe UI", 15, "bold"),
            text_color=c["text"]
        ).pack(pady=(26, 8))

        ctk.CTkLabel(
            confirm,
            text="This action cannot be undone.",
            font=ctk.CTkFont("Segoe UI", 12),
            text_color=c["text_muted"]
        ).pack()

        error_lbl = ctk.CTkLabel(
            confirm,
            text="",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=c["error"],
            wraplength=320,
        )
        error_lbl.pack(pady=(8, 0))

        btn_row = ctk.CTkFrame(confirm, fg_color="transparent")
        btn_row.pack(pady=14)

        ctk.CTkButton(
            btn_row,
            text="Cancel",
            width=145,
            height=42,
            fg_color=c["input"],
            hover_color=c["border"],
            text_color=c["text_gray"],
            corner_radius=10,
            command=confirm.destroy
        ).pack(side="left", padx=6)

        def apply_delete_result(deleted_count):
            if deleted_count <= 0:
                delete_button.configure(state="normal", text="Delete")
                error_lbl.configure(text="Ingredient was not found. Refreshing the list.")
                self._load_ingredients()
                return
            confirm.destroy()
            self._all_ingredients = [
                ing for ing in self._all_ingredients if ing.ingredient_id != ingredient_id
            ]
            self._apply_filter()
            self._load_ingredients()

        def handle_delete_error(exc):
            delete_button.configure(state="normal", text="Delete")
            error_lbl.configure(text=f"Could not delete ingredient: {exc}")

        def confirm_delete():
            delete_button.configure(state="disabled", text="Deleting...")
            error_lbl.configure(text="")
            run_in_thread(
                confirm,
                lambda: IngredientDB.delete_ingredient(ingredient_id),
                on_success=apply_delete_result,
                on_error=handle_delete_error,
                is_current=lambda: confirm.winfo_exists(),
            )

        delete_button = ctk.CTkButton(
            btn_row,
            text="Delete",
            width=145,
            height=42,
            fg_color=c["error"],
            hover_color="#B91C1C",
            text_color="#FFFFFF",
            corner_radius=10,
            command=confirm_delete,
        )
        delete_button.pack(side="left", padx=6)

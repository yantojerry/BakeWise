import customtkinter as ctk

from database.transaction_db import TransactionDB
from gui.async_utils import run_in_thread
from gui.theme import AMBER, ERROR_RED, SUCCESS, get_colors


class TransactionsScreen(ctk.CTkFrame):
    def __init__(self, parent, user):
        self.c = get_colors()
        super().__init__(parent, fg_color=self.c["bg"], corner_radius=0)
        self.user = user
        self._load_token = None
        self._transactions = []
        self.pack(fill="both", expand=True)
        self._build_ui()
        self._load_transactions()

    def _build_ui(self):
        c = self.c

        shell = ctk.CTkFrame(self, fg_color="transparent")
        shell.pack(fill="both", expand=True, padx=28, pady=24)

        header = ctk.CTkFrame(shell, fg_color="transparent")
        header.pack(fill="x")

        copy = ctk.CTkFrame(header, fg_color="transparent")
        copy.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            copy,
            text="Transaction History",
            font=ctk.CTkFont("Georgia", 30, "bold"),
            text_color=c["text"],
        ).pack(anchor="w")

        self.subtitle_label = ctk.CTkLabel(
            copy,
            text="",
            font=ctk.CTkFont("Segoe UI", 12),
            text_color=c["text_muted"],
        )
        self.subtitle_label.pack(anchor="w", pady=(4, 0))

        ctk.CTkButton(
            header,
            text="Refresh",
            height=40,
            width=96,
            fg_color=c["card"],
            hover_color=c["input"],
            text_color=c["text"],
            corner_radius=12,
            border_width=1,
            border_color=c["border"],
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            command=self._load_transactions,
        ).pack(side="right")

        ctk.CTkFrame(shell, fg_color=c["border"], height=1).pack(fill="x", pady=(18, 18))

        summary_row = ctk.CTkFrame(shell, fg_color="transparent")
        summary_row.pack(fill="x", pady=(0, 16))
        for column in range(3):
            summary_row.grid_columnconfigure(column, weight=1, uniform="tx_summary")

        self.summary_cards = {}
        for column, (key, label, accent) in enumerate(
            [
                ("total", "Transactions", AMBER),
                ("completed", "Completed", SUCCESS),
                ("voided", "Voided", ERROR_RED),
            ]
        ):
            card = ctk.CTkFrame(
                summary_row,
                fg_color=c["card"],
                corner_radius=14,
                border_width=1,
                border_color=c["border"],
            )
            card.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 6, 0 if column == 2 else 6))

            ctk.CTkLabel(
                card,
                text=label,
                font=ctk.CTkFont("Segoe UI", 10, "bold"),
                text_color=c["text_muted"],
            ).pack(anchor="w", padx=16, pady=(14, 4))

            value_label = ctk.CTkLabel(
                card,
                text="0",
                font=ctk.CTkFont("Georgia", 24, "bold"),
                text_color=accent,
            )
            value_label.pack(anchor="w", padx=16, pady=(0, 14))
            self.summary_cards[key] = value_label

        list_card = ctk.CTkFrame(
            shell,
            fg_color=c["card"],
            corner_radius=16,
            border_width=1,
            border_color=c["border"],
        )
        list_card.pack(fill="both", expand=True)

        list_header = ctk.CTkFrame(list_card, fg_color="transparent")
        list_header.pack(fill="x", padx=18, pady=(18, 10))

        ctk.CTkLabel(
            list_header,
            text="Recent activity",
            font=ctk.CTkFont("Segoe UI", 14, "bold"),
            text_color=c["text"],
        ).pack(side="left")

        self.status_pill = ctk.CTkLabel(
            list_header,
            text="",
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            text_color=c["text"],
            fg_color=c["input"],
            corner_radius=999,
            padx=10,
            pady=5,
        )
        self.status_pill.pack(side="right")

        ctk.CTkFrame(list_card, fg_color=c["border"], height=1).pack(fill="x", padx=18)

        self.body = ctk.CTkScrollableFrame(
            list_card,
            fg_color="transparent",
            scrollbar_button_color=c["card"],
            scrollbar_button_hover_color=c["input"],
        )
        self.body.pack(fill="both", expand=True, padx=8, pady=8)

    def _load_transactions(self):
        token = object()
        self._load_token = token
        self._set_status("Loading", self.c["text_muted"])
        self.subtitle_label.configure(text="Loading transactions...")
        self._set_summary(total=0, completed=0, voided=0)
        self._render_message_card("Loading transactions...")

        run_in_thread(
            self,
            TransactionDB.get_all_transactions,
            on_success=lambda rows: self._handle_transactions_loaded(token, rows),
            on_error=lambda exc: self._handle_transactions_error(token, exc),
            is_current=lambda: self._load_token is token,
        )

    def _handle_transactions_loaded(self, token, transactions):
        if self._load_token is not token:
            return

        self._transactions = transactions or []
        total_count = len(self._transactions)
        voided_count = sum(1 for tx in self._transactions if getattr(tx, "is_voided", False))
        completed_count = total_count - voided_count

        self._set_summary(
            total=total_count,
            completed=completed_count,
            voided=voided_count,
        )

        if not self._transactions:
            self._set_status("Empty", self.c["text_muted"])
            self.subtitle_label.configure(text="No transactions have been recorded yet.")
            self._render_message_card("No transactions yet.")
            return

        self._set_status("Up to date", SUCCESS)
        self.subtitle_label.configure(text=f"{total_count} transaction{'s' if total_count != 1 else ''} loaded.")
        self._render_transactions()

    def _handle_transactions_error(self, token, exc):
        if self._load_token is not token:
            return

        self._transactions = []
        self._set_summary(total=0, completed=0, voided=0)
        self._set_status("Error", ERROR_RED)
        self.subtitle_label.configure(text="Transactions could not be loaded.")
        print(f"[BakeWise] Transactions load failed: {exc}")
        self._render_message_card(
            "Unable to load transactions.",
            detail="Check the database connection and refresh again.",
            tone="error",
        )

    def _set_summary(self, total, completed, voided):
        self.summary_cards["total"].configure(text=str(total))
        self.summary_cards["completed"].configure(text=str(completed))
        self.summary_cards["voided"].configure(text=str(voided))

    def _set_status(self, text, color):
        self.status_pill.configure(text=text, text_color=color)

    def _clear_body(self):
        for widget in self.body.winfo_children():
            widget.destroy()

    def _render_message_card(self, message, detail=None, tone="neutral"):
        c = self.c
        self._clear_body()

        text_color = c["text_muted"]
        frame_color = c["input"]
        if tone == "error":
            text_color = ERROR_RED
            frame_color = "#2C1717" if ctk.get_appearance_mode() == "Dark" else "#FEE2E2"

        empty = ctk.CTkFrame(
            self.body,
            fg_color=frame_color,
            corner_radius=14,
            border_width=1,
            border_color=c["border"],
        )
        empty.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(
            empty,
            text=message,
            font=ctk.CTkFont("Segoe UI", 14, "bold"),
            text_color=text_color,
        ).pack(anchor="w", padx=18, pady=(18, 6))

        if detail:
            ctk.CTkLabel(
                empty,
                text=detail,
                font=ctk.CTkFont("Segoe UI", 11),
                text_color=c["text_muted"],
                wraplength=760,
                justify="left",
            ).pack(anchor="w", padx=18, pady=(0, 18))
        else:
            ctk.CTkLabel(
                empty,
                text="",
                font=ctk.CTkFont("Segoe UI", 1),
            ).pack(anchor="w", padx=18, pady=(0, 12))

    def _render_transactions(self):
        c = self.c
        self._clear_body()

        for index, transaction in enumerate(self._transactions):
            is_voided = bool(getattr(transaction, "is_voided", False))
            state_color = ERROR_RED if is_voided else SUCCESS
            state_text = "VOID" if is_voided else "OK"
            items_text = (
                ", ".join(
                    f"{item['product'].name} x{item['quantity']}"
                    for item in getattr(transaction, "items", []) or []
                )
                if getattr(transaction, "items", None)
                else "—"
            )

            card = ctk.CTkFrame(
                self.body,
                fg_color=c["input"] if index % 2 == 0 else c["row_alt"],
                corner_radius=14,
                border_width=1,
                border_color=c["border"],
            )
            card.pack(fill="x", padx=10, pady=6)

            top = ctk.CTkFrame(card, fg_color="transparent")
            top.pack(fill="x", padx=16, pady=(14, 10))

            ctk.CTkLabel(
                top,
                text=f"#{transaction.transaction_id}",
                font=ctk.CTkFont("Segoe UI", 13, "bold"),
                text_color=AMBER,
            ).pack(side="left")

            ctk.CTkLabel(
                top,
                text=str(transaction.date),
                font=ctk.CTkFont("Segoe UI", 11),
                text_color=c["text_muted"],
            ).pack(side="left", padx=(12, 0))

            state_badge = ctk.CTkLabel(
                top,
                text=state_text,
                font=ctk.CTkFont("Segoe UI", 10, "bold"),
                text_color=state_color,
                fg_color=c["card"],
                corner_radius=999,
                padx=10,
                pady=5,
            )
            state_badge.pack(side="right")

            middle = ctk.CTkFrame(card, fg_color="transparent")
            middle.pack(fill="x", padx=16, pady=(0, 10))

            self._meta_pair(middle, "Payment", transaction.payment_method or "—")
            self._meta_pair(middle, "Total", f"₱{transaction.get_total():,.2f}", value_color=c["text"])

            items = ctk.CTkFrame(card, fg_color="transparent")
            items.pack(fill="x", padx=16, pady=(0, 14))

            ctk.CTkLabel(
                items,
                text="Items",
                font=ctk.CTkFont("Segoe UI", 10, "bold"),
                text_color=c["text_muted"],
            ).pack(anchor="w")

            ctk.CTkLabel(
                items,
                text=items_text,
                font=ctk.CTkFont("Segoe UI", 11),
                text_color=c["text_gray"],
                justify="left",
                wraplength=760,
            ).pack(anchor="w", pady=(4, 0))

    def _meta_pair(self, parent, label, value, value_color=None):
        c = self.c
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(side="left", padx=(0, 28))

        ctk.CTkLabel(
            row,
            text=label,
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            text_color=c["text_muted"],
        ).pack(anchor="w")

        ctk.CTkLabel(
            row,
            text=value,
            font=ctk.CTkFont("Segoe UI", 12),
            text_color=value_color or c["text_gray"],
        ).pack(anchor="w", pady=(2, 0))

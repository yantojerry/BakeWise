import customtkinter as ctk


class SidePanelHost:
    def __init__(self, owner, colors, width=430, top_offset=96, side_offset=24, bottom_offset=24):
        self.owner = owner
        self.colors = colors
        self.default_width = width
        self.top_offset = top_offset
        self.side_offset = side_offset
        self.bottom_offset = bottom_offset

        self.panel = None
        self.header = None
        self.title_label = None
        self.close_button = None
        self.body = None
        self._current_width = width

        self.owner.bind("<Configure>", self._on_owner_configure, add="+")
        self.owner.bind("<Destroy>", self._on_owner_destroy, add="+")

    def open(self, title, width=None):
        self.close()

        panel_width = width or self.default_width
        c = self.colors
        self.panel = ctk.CTkFrame(
            self.owner,
            fg_color=c["card"],
            corner_radius=16,
            border_width=1,
            border_color=c["border"],
            width=panel_width,
        )
        self._current_width = panel_width
        self.panel.grid_columnconfigure(0, weight=1)
        self.panel.bind("<Destroy>", self._on_panel_destroy, add="+")

        self.header = ctk.CTkFrame(self.panel, fg_color="transparent", height=42)
        self.header.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 8))
        self.header.grid_columnconfigure(0, weight=1)

        self.title_label = ctk.CTkLabel(
            self.header,
            text=title,
            font=ctk.CTkFont("Georgia", 20, "bold"),
            text_color=c["text"],
            anchor="w",
        )
        self.title_label.grid(row=0, column=0, sticky="w")

        self.close_button = ctk.CTkButton(
            self.header,
            text="x",
            width=30,
            height=28,
            corner_radius=8,
            fg_color=c["input"],
            hover_color=c["border"],
            text_color=c["text"],
            command=self.close,
        )
        self.close_button.grid(row=0, column=1, sticky="e")

        ctk.CTkFrame(self.panel, fg_color=c["border"], height=1).grid(
            row=1,
            column=0,
            sticky="ew",
            padx=16,
            pady=(0, 12),
        )

        self.body = ctk.CTkScrollableFrame(self.panel, fg_color="transparent")
        self.body.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self.panel.grid_rowconfigure(2, weight=1)

        self._reposition()
        self.panel.lift()
        return self.body

    def close(self):
        if self.panel is not None and self.panel.winfo_exists():
            self.panel.destroy()
        self._clear_refs()

    def is_open(self):
        return self.panel is not None and self.panel.winfo_exists()

    def _reposition(self):
        if not self.is_open():
            return

        self.owner.update_idletasks()
        width = min(self._current_width, max(self.owner.winfo_width() - (self.side_offset * 2), 280))
        height = max(self.owner.winfo_height() - self.top_offset - self.bottom_offset, 280)
        y = self.top_offset

        self.panel.configure(width=width, height=height)
        self.panel.update_idletasks()
        actual_width = max(self.panel.winfo_reqwidth(), width)
        if self.body is not None and self.body.winfo_exists():
            body_width = max(actual_width - 44, 240)
            self.body.configure(width=body_width)
        self.panel.place(relx=1.0, x=-self.side_offset, y=y, anchor="ne")

    def _on_owner_configure(self, _event):
        self._reposition()

    def _on_owner_destroy(self, _event):
        self._clear_refs()

    def _on_panel_destroy(self, _event):
        self._clear_refs()

    def _clear_refs(self):
        self.panel = None
        self.header = None
        self.title_label = None
        self.close_button = None
        self.body = None

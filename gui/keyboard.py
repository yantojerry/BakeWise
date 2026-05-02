import customtkinter as ctk


class KeyboardController:
    """Keeps form shortcuts without rendering the old on-screen keypad."""

    def __init__(self, root):
        self.root = root
        self.entry_registry = {}
        self.primary_actions = {}
        self.container = None

        self.root.bind_all("<Return>", self._handle_return, add="+")
        self.root.bind_all("<Escape>", self._handle_escape, add="+")
        self.root.bind_all("<Delete>", self._handle_delete, add="+")

    def register_entry(
        self,
        widget,
        layout,
        on_enter=None,
        on_escape=None,
        popup_parent=None,
        popup_mode="floating",
    ):
        self.entry_registry[widget] = {
            "layout": layout,
            "on_enter": on_enter,
            "on_escape": on_escape,
            "popup_parent": popup_parent,
            "popup_mode": popup_mode,
        }
        widget.bind("<Destroy>", lambda _event, target=widget: self._cleanup_entry(target), add="+")

    def register_primary_action(self, scope, on_enter, on_escape=None, on_delete=None):
        self.primary_actions[scope] = {
            "on_enter": on_enter,
            "on_escape": on_escape,
            "on_delete": on_delete,
        }
        scope.bind("<Destroy>", lambda _event, target=scope: self._cleanup_scope(target), add="+")

    def hide(self):
        return None

    def show_for(self, _widget):
        return None

    def _handle_return(self, _event):
        focus_widget = self._resolve_registered_widget(self.root.focus_get())
        if isinstance(focus_widget, (ctk.CTkButton, ctk.CTkRadioButton, ctk.CTkOptionMenu)):
            return None

        entry_config = self.entry_registry.get(focus_widget)
        if entry_config and entry_config["on_enter"] is not None:
            entry_config["on_enter"]()
            return "break"

        scope_action = self._get_scope_action("on_enter")
        if scope_action is not None:
            scope_action()
            return "break"
        return None

    def _handle_escape(self, _event):
        entry_config = self.entry_registry.get(
            self._resolve_registered_widget(self.root.focus_get())
        )
        if entry_config and entry_config["on_escape"] is not None:
            entry_config["on_escape"]()
            return "break"

        scope_action = self._get_scope_action("on_escape")
        if scope_action is not None:
            scope_action()
            return "break"
        return None

    def _handle_delete(self, _event):
        if self._resolve_registered_widget(self.root.focus_get()) in self.entry_registry:
            return None

        scope_action = self._get_scope_action("on_delete")
        if scope_action is not None:
            scope_action()
            return "break"
        return None

    def _get_scope_action(self, action_name):
        focus_widget = self.root.focus_get()
        if focus_widget is None:
            return None

        widget = focus_widget
        while widget is not None:
            actions = self.primary_actions.get(widget)
            if actions and actions.get(action_name) is not None:
                return actions[action_name]
            widget = getattr(widget, "master", None)
        return None

    def _cleanup_entry(self, widget):
        self.entry_registry.pop(widget, None)

    def _cleanup_scope(self, scope):
        self.primary_actions.pop(scope, None)

    def _resolve_registered_widget(self, widget):
        while widget is not None:
            if widget in self.entry_registry:
                return widget
            widget = getattr(widget, "master", None)
        return None

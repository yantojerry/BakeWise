import customtkinter as ctk

# ── Fixed accent colors (same in both modes) ──────────────
AMBER       = "#F59E0B"
AMBER_DARK  = "#B45309"
AMBER_LIGHT = "#FCD34D"
SUCCESS     = "#10B981"
ERROR_RED   = "#EF4444"
WARNING     = "#F97316"
BLUE        = "#3B82F6"
BLUE_DARK   = "#1D4ED8"


def get_colors():
    """Returns a color dictionary based on current appearance mode."""
    is_dark = ctk.get_appearance_mode() == "Dark"

    if is_dark:
        return {
            "bg":           "#05070B",
            "bg_top":       "#030406",
            "bg_bottom":    "#0C1118",
            "sidebar":      "#080A0F",
            "card":         "#10131A",
            "card_hover":   "#151A24",
            "input":        "#151922",
            "active_bg":    "#1B2432",
            "text":         "#F8FAFC",
            "text_gray":    "#D7DEE8",
            "text_muted":   "#8B98AA",
            "border":       "#273142",
            "row_alt":      "#0B1018",
            "thead":        "#090D13",
            "panel":        "#070B10",
            "focus":        "#93C5FD",
            "amber":        AMBER,
            "amber_dark":   AMBER_DARK,
            "amber_light":  AMBER_LIGHT,
            "success":      SUCCESS,
            "error":        ERROR_RED,
            "warning":      WARNING,
            "blue":         BLUE,
            "blue_dark":    BLUE_DARK,
            "success_bg":   "#0D2A1D",
            "success_hover":"#113A28",
            "error_bg":     "#34131A",
            "error_hover":  "#4A1A24",
            "warning_bg":   "#33220B",
            "warning_hover":"#4A310E",
        }
    else:
        return {
            "bg":           "#F6F7F9",
            "bg_top":       "#FFFFFF",
            "bg_bottom":    "#ECEFF3",
            "sidebar":      "#FFFFFF",
            "card":         "#FFFFFF",
            "card_hover":   "#F2F4F7",
            "input":        "#EEF1F5",
            "active_bg":    "#E7ECF3",
            "text":         "#0B0F14",
            "text_gray":    "#2F3846",
            "text_muted":   "#667085",
            "border":       "#D6DCE5",
            "row_alt":      "#F9FAFB",
            "thead":        "#EEF2F6",
            "panel":        "#F1F4F8",
            "focus":        "#111827",
            "amber":        AMBER,
            "amber_dark":   AMBER_DARK,
            "amber_light":  AMBER_LIGHT,
            "success":      SUCCESS,
            "error":        ERROR_RED,
            "warning":      WARNING,
            "blue":         BLUE,
            "blue_dark":    BLUE_DARK,
            "success_bg":   "#DCFCE7",
            "success_hover":"#BBF7D0",
            "error_bg":     "#FEE2E2",
            "error_hover":  "#FECACA",
            "warning_bg":   "#FFEDD5",
            "warning_hover":"#FED7AA",
        }

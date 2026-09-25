from __future__ import annotations

from PySide6.QtCore import QTimer, QObject
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget
from loguru import logger

from doremi.native_rs import process_qss_template, compute_color_variants


class ThemeManager(QObject):
    """Centralizes all theme/accent application logic.

    Owns the debounce timer, QSS cache, transition overlay, and post-theme
    widget refresh.  MainWindow delegates to this class.
    """

    def __init__(self, main_window: QMainWindow) -> None:
        super().__init__(main_window)
        self._mw = main_window

        self._theme_base_qss = ""
        self._theme_refresh_pending = False
        self._pending_theme_mode = "dark"
        self._pending_accent = "#A78BFA"
        self._cached_base_qss: dict[str, str] = {}
        self._last_theme_key: tuple | None = None

        self._theme_apply_timer = QTimer(self)
        self._theme_apply_timer.setSingleShot(True)
        self._theme_apply_timer.timeout.connect(self._apply_debounced)

        from doremi.ui.widgets.theme_transition import ThemeTransitionOverlay
        self.theme_overlay = ThemeTransitionOverlay(main_window)
        self.theme_overlay.hide()

    # ── Public API ─────────────────────────────────────────────────────────

    def apply(self, theme_mode: str, accent: str, immediate: bool = False) -> None:
        """Schedule or directly apply a theme mode + accent combination."""
        self._pending_theme_mode = theme_mode
        self._pending_accent = accent
        if immediate:
            self._apply_actual()
        else:
            self._theme_apply_timer.stop()
            self._theme_apply_timer.start(150)

    def on_main_window_resized(self) -> None:
        """Keep the transition overlay aligned with the main window."""
        self.theme_overlay.setGeometry(self._mw.rect())

    # ── Internal ───────────────────────────────────────────────────────────

    def _apply_debounced(self) -> None:
        """Debounce wrapper — shows the transition overlay when visible."""
        theme_mode = self._pending_theme_mode
        accent = self._pending_accent

        theme_key = (theme_mode, accent)
        if self._last_theme_key == theme_key:
            return

        if not self._mw.isVisible():
            self._apply_actual()
            return

        self.theme_overlay.setGeometry(self._mw.rect())
        self.theme_overlay.start_transition(
            target_theme_mode=theme_mode,
            target_accent=accent,
            on_midpoint_callback=self._apply_actual,
        )

    def _apply_actual(self) -> None:
        """Regenerate QSS with custom theme colors and dynamic accent."""
        theme_mode = self._pending_theme_mode
        accent = self._pending_accent

        theme_key = (theme_mode, accent)
        if self._last_theme_key == theme_key:
            return
        self._last_theme_key = theme_key

        from doremi.ui.design import tokens

        # --- Resolve effective mode (system → dark|light) ------------------
        active_mode = theme_mode
        if active_mode == "system":
            import subprocess
            try:
                res = subprocess.run(
                    ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
                    capture_output=True, text=True, timeout=0.5,
                )
                if "prefer-light" in res.stdout:
                    active_mode = "light"
                else:
                    active_mode = "dark"
            except Exception:
                active_mode = "dark"

        base_scheme = tokens.LIGHT if active_mode == "light" else tokens.DARK
        from doremi.ui.stylesheet import DOREMI_QSS
        new_qss = DOREMI_QSS

        # --- Compute accent variants + QSS substitution (módulo nativo Rust) ---
        cv = compute_color_variants(accent, active_mode)
        vars_map: dict[str, str] = {
            "#A78BFA": accent,
            "#a78bfa": accent.lower(),
            "#BBA4FC": cv.bright_hex,
            "#bba4fc": cv.bright_hex.lower(),
            "#8B5CF6": cv.dark_hex,
            "#8b5cf6": cv.dark_hex.lower(),
            "167,139,250": f"{cv.r},{cv.g},{cv.b}",
            "167, 139, 250": f"{cv.r}, {cv.g}, {cv.b}",
            "139,92,246": f"{cv.dark_r},{cv.dark_g},{cv.dark_b}",
            "139, 92, 246": f"{cv.dark_r}, {cv.dark_g}, {cv.dark_b}",
        }
        new_qss = process_qss_template(new_qss, vars_map)
        bright_hex, dark_hex = cv.bright_hex, cv.dark_hex
        r, g, b = cv.r, cv.g, cv.b
        dark_r, dark_g, dark_b = cv.dark_r, cv.dark_g, cv.dark_b

        # --- Update global design tokens -----------------------------------
        accent_dim_rgba = f"rgba({r},{g},{b},0.15)"
        border_rgba = f"rgba({r},{g},{b},0.12)"
        border_focus_rgba = f"rgba({r},{g},{b},0.50)"

        tokens.CURRENT = tokens.ColorScheme(
            bg_base=base_scheme.bg_base,
            bg_surface=base_scheme.bg_surface,
            bg_elevated=base_scheme.bg_elevated,
            bg_high=base_scheme.bg_high,
            bg_overlay=base_scheme.bg_overlay,
            accent=accent,
            accent_bright=bright_hex,
            accent_dim=accent_dim_rgba,
            secondary=base_scheme.secondary,
            secondary_dim=base_scheme.secondary_dim,
            text_primary=base_scheme.text_primary,
            text_secondary=base_scheme.text_secondary,
            text_disabled=base_scheme.text_disabled,
            text_on_accent="#FFFFFF" if active_mode == "light" else "#0A0A14",
            border=border_rgba,
            border_focus=border_focus_rgba,
            success=base_scheme.success,
            warning=base_scheme.warning,
            error=base_scheme.error,
            info=base_scheme.info,
            like_color=base_scheme.like_color,
        )

        # --- Replace like-color placeholders --------------------------------
        new_qss = new_qss.replace("#FF4A70", tokens.CURRENT.like_color)
        new_qss = new_qss.replace("#ff4a70", tokens.CURRENT.like_color.lower())
        try:
            lc = QColor(tokens.CURRENT.like_color)
            if lc.isValid():
                new_qss = new_qss.replace("255, 74, 112", f"{lc.red()}, {lc.green()}, {lc.blue()}")
                new_qss = new_qss.replace("255,74,112", f"{lc.red()},{lc.green()},{lc.blue()}")
        except Exception as e:
            logger.debug(f"Could not compute like color RGB replacements: {e}")

        # --- Replace background/dark-mode colors ---------------------------
        new_qss = (
            new_qss
            .replace("#0A0A14", tokens.CURRENT.bg_base)
            .replace("#0a0a14", tokens.CURRENT.bg_base.lower())
            .replace("#10101E", tokens.CURRENT.bg_surface)
            .replace("#10101e", tokens.CURRENT.bg_surface.lower())
            .replace("#16162A", tokens.CURRENT.bg_elevated)
            .replace("#16162a", tokens.CURRENT.bg_elevated.lower())
            .replace("#1E1E38", tokens.CURRENT.bg_high)
            .replace("#1e1e38", tokens.CURRENT.bg_high.lower())
            .replace("#F1F0FF", tokens.CURRENT.text_primary)
            .replace("#f1f0ff", tokens.CURRENT.text_primary.lower())
            .replace("#9B9BC0", tokens.CURRENT.text_secondary)
            .replace("#9b9bc0", tokens.CURRENT.text_secondary.lower())
            .replace("#6B6B9B", tokens.CURRENT.text_secondary)
            .replace("#6b6b9b", tokens.CURRENT.text_secondary.lower())
            .replace("#4A4A6A", tokens.CURRENT.text_disabled)
            .replace("#4a4a6a", tokens.CURRENT.text_disabled.lower())
        )

        # --- Build qt-material base stylesheet (cached per mode) -----------
        app = QApplication.instance()
        if app:
            if active_mode not in self._cached_base_qss:
                from qt_material import build_stylesheet

                theme_xml = "light_purple.xml" if active_mode == "light" else "dark_purple.xml"
                try:
                    base_qss = build_stylesheet(
                        theme=theme_xml,
                        extra={
                            "primaryColor": "#A78BFA",
                            "primaryLightColor": "#A78BFA",
                            "secondaryColor": "#FFFFFF" if active_mode == "light" else "#1E1E2E",
                            "secondaryLightColor": "#DFDFE8" if active_mode == "light" else "#2A2A3E",
                            "secondaryDarkColor": "#F3F3F9" if active_mode == "light" else "#13131F",
                            "primaryTextColor": "#121224" if active_mode == "light" else "#FFFFFF",
                            "secondaryTextColor": "#5C5C8A" if active_mode == "light" else "#B0B0C0",
                            "density_scale": "-1",
                            "pyside6": True,
                            "linux": True,
                        },
                    )
                    base_qss = base_qss.replace("font-family: Roboto;", "")
                    base_qss = base_qss.replace("font-size: 13px;", "")
                    base_qss = base_qss.replace("line-height: 13px;", "")
                    self._cached_base_qss[active_mode] = base_qss
                except Exception as e:
                    logger.error(f"Error building qt_material stylesheet: {e}")
                    self._cached_base_qss[active_mode] = ""

            base_qss_template = self._cached_base_qss.get(active_mode, "")
            self._theme_base_qss = base_qss_template.replace("#A78BFA", accent).replace("#a78bfa", accent.lower())

        # --- Override slider groove color per mode -------------------------
        groove_color = "#D0D0DF" if active_mode == "light" else "#2A2A4A"
        new_qss = new_qss.replace("#2A2A4A", groove_color)
        new_qss = new_qss.replace("#2a2a4a", groove_color.lower())

        # --- Notify QML theme bridge (colors are runtime-dynamic) ----------
        try:
            from doremi.ui.theme_bridge import theme_bridge
            theme_bridge().push(tokens.CURRENT)
        except Exception as e:
            logger.debug(f"QML theme bridge push skipped: {e}")

        # --- Apply final stylesheet -----------------------------------------
        if app:
            tokens.THEME_APPLYING = True
            try:
                app.setStyleSheet(self._theme_base_qss + new_qss)
            finally:
                tokens.THEME_APPLYING = False

        self._schedule_refresh()

    def _schedule_refresh(self) -> None:
        """Queue a deferred post-theme widget refresh (single-shot)."""
        if self._theme_refresh_pending:
            return
        self._theme_refresh_pending = True
        QTimer.singleShot(0, self._refresh_dependents)

    def _refresh_dependents(self) -> None:
        """Walk known widgets and refresh their inline styles after a theme change."""
        self._theme_refresh_pending = False
        mw = self._mw

        for attr, method_name in (
            ("search_bar", "_update_search_bar_styles"),
            ("mini_player", "_update_mini_player_styles"),
            ("now_playing_screen", "_update_styles"),
            ("settings_screen", "_apply_sidebar_styles"),
            ("stats_screen", "_apply_theme_style"),
        ):
            widget = getattr(mw, attr, None)
            method = getattr(widget, method_name, None)
            if callable(method):
                try:
                    method()
                except Exception as e:
                    logger.debug(f"Theme refresh skipped for {attr}: {e}")

        current = getattr(getattr(mw, "stack", None), "currentWidget", lambda: None)()
        for method_name in ("_apply_theme_styles", "_update_theme_styles", "_refresh_theme", "_update_header_styles"):
            method_val = getattr(current, method_name, None)
            if callable(method_val):
                try:
                    method_val()
                except Exception as e:
                    logger.debug(f"Current screen theme refresh skipped: {e}")

        self._refresh_cards_batched(current)

    def _refresh_cards_batched(self, root: QWidget | None) -> None:
        """Refresh visible card widgets in batches to avoid UI stalls."""
        if root is None:
            return
        try:
            from doremi.ui.widgets.song_card import SongCard
            from doremi.ui.widgets.artist_card import ArtistCard
            from doremi.ui.widgets.album_card import AlbumCard
            from doremi.ui.widgets.playlist_card import PlaylistCard

            cards: list[QWidget] = []
            for card_cls in (SongCard, ArtistCard, AlbumCard, PlaylistCard):
                cards.extend(c for c in root.findChildren(card_cls) if c.isVisible())
        except Exception:
            return

        BATCH_SIZE = 24

        def refresh_batch(index: int = 0) -> None:
            for card in cards[index:index + BATCH_SIZE]:
                try:
                    card._update_card_styles()
                except Exception as e:
                    logger.debug(f"Card theme refresh skipped: {e}")
            if index + BATCH_SIZE < len(cards):
                QTimer.singleShot(0, lambda: refresh_batch(index + BATCH_SIZE))

        refresh_batch()

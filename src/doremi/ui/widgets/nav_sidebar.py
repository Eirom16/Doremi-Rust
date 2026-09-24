from __future__ import annotations

import asyncio

from PySide6.QtCore import QEasingCurve, QRectF, Qt, QPropertyAnimation, Signal
from PySide6.QtGui import QPixmap, QPainter, QPainterPath, QColor
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from doremi.ui.design.fonts import AppFont
from doremi.ui.design.icons import Icon
from doremi.utils.image_cache import ImageCache

_image_cache = ImageCache()

from doremi.ui.widgets.animated_mixins import HoverColorAnimationMixin

NAV_ITEMS = [
    ("home", "home", "Inicio"),
    ("library", "library_music", "Biblioteca"),
    ("history", "history", "Historial"),
    ("stats", "bar_chart", "Estadísticas"),
    ("downloads", "download", "Descargas"),
    ("settings", "settings", "Ajustes"),
]


class NavButton(QPushButton, HoverColorAnimationMixin):
    def __init__(
        self,
        route: str,
        icon_name: str,
        label: str,
        parent=None,
        thumbnail_url: str = "",
    ):
        super().__init__(parent)
        self.init_hover_animation(normal_color="transparent", hover_color="#1E1E38")
        self.route = route
        self.icon_name = icon_name
        self.label = label
        self.thumbnail_url = thumbnail_url
        self._collapsed = False
        self._thumbnail_task: asyncio.Task | None = None
        self._icon_width = 28 if thumbnail_url else 22
        self.setCheckable(True)
        self.setFixedHeight(44)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(label)
        self.setAccessibleName(label)

        self._row = QHBoxLayout(self)
        self._row.setContentsMargins(11, 0, 11, 0)
        self._row.setSpacing(12)

        from doremi.ui.design import tokens
        self.icon_label = Icon.label(icon_name, 22, tokens.CURRENT.text_secondary)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setFixedWidth(self._icon_width)
        self.text_label = QLabel(label)
        self.text_label.setFont(AppFont.body(13))
        self.text_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._row.addWidget(self.icon_label)
        self._row.addWidget(self.text_label)
        self._row.addStretch()

        self._apply_style(False)
        if thumbnail_url:
            self._load_thumbnail(thumbnail_url)

    def _load_thumbnail(self, url: str) -> None:
        """Carga la carátula de una playlist sin bloquear la navegación."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # Los tests de widgets no siempre tienen un bucle asyncio activo.
            return

        async def load() -> None:
            try:
                image_path = await _image_cache.download(url)
                import shiboken6
                if not image_path or not shiboken6.isValid(self):
                    return
                source = QPixmap(str(image_path))
                if source.isNull():
                    return

                size = 28
                scaled = source.scaled(
                    size, size,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
                x = (scaled.width() - size) // 2
                y = (scaled.height() - size) // 2
                cropped = scaled.copy(x, y, size, size)
                rounded = QPixmap(size, size)
                rounded.fill(Qt.GlobalColor.transparent)
                painter = QPainter(rounded)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                clip = QPainterPath()
                clip.addRoundedRect(QRectF(0, 0, size, size), 5, 5)
                painter.setClipPath(clip)
                painter.drawPixmap(0, 0, cropped)
                painter.end()
                if shiboken6.isValid(self):
                    self.icon_label.setPixmap(rounded)
            except asyncio.CancelledError:
                return
            except Exception as exc:
                from loguru import logger
                logger.debug(f"No se pudo cargar la miniatura de playlist: {exc}")

        self._thumbnail_task = loop.create_task(load())

    def set_active(self, active: bool) -> None:
        self.setChecked(active)
        self._apply_style(active)

    def set_collapsed(self, collapsed: bool) -> None:
        self._collapsed = collapsed
        self.text_label.setVisible(not collapsed)
        if collapsed:
            self._row.setContentsMargins(0, 0, 0, 0)
            self._row.setSpacing(0)
            self.icon_label.setFixedWidth(52)
        else:
            self._row.setContentsMargins(11, 0, 11, 0)
            self._row.setSpacing(12)
            self.icon_label.setFixedWidth(self._icon_width)

    def _update_hover_stylesheet(self):
        if not self.isChecked():
            from PySide6.QtGui import QColor
            bg = self._current_hover_color.name(QColor.HexArgb)
            self.setStyleSheet(f"""
                QPushButton {{
                    background: {bg};
                    border: none;
                    border-radius: 12px;
                    text-align: left;
                    padding: 0;
                }}
            """)

    def _apply_style(self, active: bool) -> None:
        from doremi.ui.design import tokens
        from PySide6.QtGui import QColor
        accent = tokens.CURRENT.accent
        c = QColor(accent)
        r, g, b, _ = c.getRgb()

        color = accent if active else tokens.CURRENT.text_secondary
        weight = "700" if active else "500"
        self.icon_label.setStyleSheet(f"color: {color}; background: transparent; font-family: 'Material Symbols Rounded'; font-size: 24px;")
        self.text_label.setStyleSheet(f"color: {color}; background: transparent; font-weight: {weight};")
        
        if active:
            bg = f"rgba({r},{g},{b},0.14)"
            self.setStyleSheet(f"""
                QPushButton {{
                    background: {bg};
                    border: none;
                    border-radius: 12px;
                    text-align: left;
                    padding: 0;
                }}
            """)
        else:
            self._update_hover_stylesheet()

    def changeEvent(self, event) -> None:
        from PySide6.QtCore import QEvent
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.StyleChange, QEvent.Type.ApplicationPaletteChange):
            if hasattr(self, 'icon_label') and self.icon_label:
                if not getattr(self, '_in_style_change', False):
                    self._in_style_change = True
                    try:
                        self._apply_style(self.isChecked())
                    finally:
                        self._in_style_change = False
        super().changeEvent(event)


class NavSidebar(QWidget):
    on_navigate = Signal(str)

    EXPANDED_WIDTH = 214
    COLLAPSED_WIDTH = 64

    def __init__(self, on_navigate):
        super().__init__()
        self._on_navigate = on_navigate
        self._is_function = callable(on_navigate) and not hasattr(on_navigate, "emit")
        self._active = "home"
        self._collapsed = False
        self._nav_buttons: dict[str, NavButton] = {}
        self._playlist_buttons: list[NavButton] = []

        self.setObjectName("navSidebar")
        self.setFixedWidth(self.EXPANDED_WIDTH)
        self._width_anim = QPropertyAnimation(self, b"minimumWidth", self)
        self._width_anim.setDuration(280)
        self._width_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._max_anim = QPropertyAnimation(self, b"maximumWidth", self)
        self._max_anim.setDuration(280)
        self._max_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 12, 6, 16)
        layout.setSpacing(4)

        self._logo_row = QWidget()
        self._logo_row.setObjectName("logoRow")
        self._logo_row.setStyleSheet("#logoRow { background: transparent; border: none; }")
        logo_layout = QHBoxLayout(self._logo_row)
        logo_layout.setContentsMargins(0, 0, 0, 12)
        logo_layout.setSpacing(10)
        from doremi.config.paths import AppDirs
        icon_path = AppDirs.root / "assets" / "icon.png"
        if icon_path.exists():
            self._app_icon = QLabel()
            self._app_icon.setFixedSize(52, 52)
            self._app_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pixmap = QPixmap(str(icon_path))
            self._app_icon_source = pixmap.scaled(52, 52, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self._app_icon.setPixmap(self._app_icon_source)
            self._app_icon.setStyleSheet("background: transparent; border: none;")
            self._app_icon_is_custom = True
        else:
            self._app_icon = Icon.label("music_note", 26, "#A78BFA")
            self._app_icon.setFixedSize(52, 52)
            self._app_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._app_icon_is_custom = False
            
        self._app_title = QLabel("Doremi")
        self._app_title.setFont(AppFont.display(21))
        self._update_header_style()
        logo_layout.addWidget(self._app_icon)
        logo_layout.addWidget(self._app_title)
        logo_layout.addStretch()
        layout.addWidget(self._logo_row)

        for route, icon_name, label in NAV_ITEMS:
            btn = NavButton(route, icon_name, label)
            btn.clicked.connect(lambda checked=False, r=route: self._navigate(r))
            self._nav_buttons[route] = btn
            layout.addWidget(btn)

        self._playlist_section = QWidget(self)
        playlist_layout = QVBoxLayout(self._playlist_section)
        playlist_layout.setContentsMargins(0, 12, 0, 0)
        playlist_layout.setSpacing(4)
        self._playlist_heading = QLabel("Tus playlists")
        self._playlist_heading.setFont(AppFont.body(11))
        self._playlist_heading.setContentsMargins(11, 0, 0, 4)
        playlist_layout.addWidget(self._playlist_heading)
        self._playlist_list_layout = playlist_layout
        self._playlist_section.hide()
        layout.addWidget(self._playlist_section)

        layout.addStretch()

        # Collapse/expand toggle
        self._toggle_btn = QPushButton()
        self._toggle_btn.setFixedHeight(40)
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.setFont(Icon.font(20))
        self._toggle_btn.clicked.connect(self.toggle_collapse)
        self._toggle_btn.setAccessibleName("Contraer barra lateral")
        layout.addWidget(self._toggle_btn)

        previous = None
        for btn in self._nav_buttons.values():
            if previous:
                QWidget.setTabOrder(previous, btn)
            previous = btn
        QWidget.setTabOrder(previous, self._toggle_btn)

        self._update_sidebar_styles()
        self._update_toggle_icon()
        self._select("home")

    def set_playlists(self, playlists: list[dict]) -> None:
        """Muestra hasta cuatro playlists de acceso rápido en la barra lateral."""
        while self._playlist_buttons:
            button = self._playlist_buttons.pop()
            self._playlist_list_layout.removeWidget(button)
            button.deleteLater()

        for playlist in playlists[:4]:
            title = str(playlist.get("title", "")).strip()
            route = str(playlist.get("navigate", "")).strip()
            if not title or not route:
                continue
            button = NavButton(
                route,
                "playlist_play",
                title,
                self._playlist_section,
                thumbnail_url=str(playlist.get("thumbnail_url", "")),
            )
            button.clicked.connect(lambda checked=False, r=route: self._navigate(r))
            button.set_collapsed(self._collapsed)
            self._playlist_list_layout.addWidget(button)
            self._playlist_buttons.append(button)

        self._update_playlist_visibility()

    def _update_playlist_visibility(self) -> None:
        self._playlist_section.setVisible(bool(self._playlist_buttons) and not self._collapsed)

    def toggle_collapse(self) -> None:
        self._collapsed = not self._collapsed
        target = self.COLLAPSED_WIDTH if self._collapsed else self.EXPANDED_WIDTH
        self.setProperty("collapsed", "true" if self._collapsed else "false")
        self.style().unpolish(self)
        self.style().polish(self)

        self._width_anim.stop()
        self._width_anim.setStartValue(self.minimumWidth())
        self._width_anim.setEndValue(target)
        self._width_anim.start()
        self._max_anim.stop()
        self._max_anim.setStartValue(self.maximumWidth())
        self._max_anim.setEndValue(target)
        self._max_anim.start()

        for btn in self._nav_buttons.values():
            btn.set_collapsed(self._collapsed)
        for btn in self._playlist_buttons:
            btn.set_collapsed(self._collapsed)
        self._app_title.setVisible(not self._collapsed)
        self._update_playlist_visibility()
        self._update_toggle_icon()

    def _update_toggle_icon(self) -> None:
        self._toggle_btn.setText(Icon.get("chevron_right" if self._collapsed else "chevron_left"))
        self._toggle_btn.setAccessibleName("Expandir barra lateral" if self._collapsed else "Contraer barra lateral")

    def _navigate(self, route: str) -> None:
        self._select(route)
        if self._is_function:
            self._on_navigate(route)
        else:
            self._on_navigate.emit(route)
        self.on_navigate.emit(route)

    def _select(self, route: str) -> None:
        self._active = route
        for key, btn in self._nav_buttons.items():
            btn.set_active(key == route)
        for btn in self._playlist_buttons:
            btn.set_active(btn.route == route)

    def setEnabled(self, enabled: bool) -> None:
        for btn in self.findChildren(QPushButton):
            btn.setEnabled(enabled)

    def _update_header_style(self) -> None:
        from doremi.ui.design import tokens
        accent = tokens.CURRENT.accent
        if hasattr(self, '_app_title') and self._app_title:
            self._app_title.setStyleSheet(f"color: {accent}; background: transparent;")
        if hasattr(self, '_app_icon') and self._app_icon:
            if hasattr(self, '_app_icon_is_custom') and self._app_icon_is_custom:
                self._app_icon.setGraphicsEffect(None)
                source = getattr(self, "_app_icon_source", None)
                if source and not source.isNull():
                    self._app_icon.setPixmap(source)
                self._app_icon.setStyleSheet("background: transparent; border: none;")
                return
            if isinstance(self._app_icon, QLabel) and self._app_icon.text():
                self._app_icon.setStyleSheet(f"color: {accent}; background: transparent; font-size: 24px;")

    def _update_sidebar_styles(self) -> None:
        from doremi.ui.design import tokens
        border_color = tokens.CURRENT.border
        text_secondary = tokens.CURRENT.text_secondary
        text_primary = tokens.CURRENT.text_primary
        
        self.setStyleSheet(f"""
            #navSidebar {{
                background-color: {tokens.CURRENT.bg_base};
                border-right: none;
            }}
        """)
        
        if hasattr(self, '_toggle_btn'):
            self._toggle_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: none;
                    border-radius: 10px;
                    color: {text_secondary};
                    font-size: 24px;
                }}
                QPushButton:hover {{
                    background: {tokens.CURRENT.bg_elevated};
                    color: {text_primary};
                }}
            """)
        self._update_header_style()
        if hasattr(self, "_playlist_heading"):
            self._playlist_heading.setStyleSheet(
                f"color: {text_secondary}; background: transparent;"
            )

    def changeEvent(self, event) -> None:
        from PySide6.QtCore import QEvent
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.StyleChange, QEvent.Type.ApplicationPaletteChange):
            if not getattr(self, '_in_style_change', False):
                self._in_style_change = True
                try:
                    self._update_sidebar_styles()
                finally:
                    self._in_style_change = False
        super().changeEvent(event)

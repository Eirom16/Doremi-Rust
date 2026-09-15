from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget

from doremi.ui.screens.settings.components import AccentColorPicker, SettingsRow, SettingsSection, page_title
from doremi.ui.widgets.animated_toggle import AnimatedToggle
from doremi.ui.widgets.glass_combobox import GlassComboBox
from doremi.utils.i18n import _


class AppearanceSettingsScreen(QWidget):
    def __init__(self, settings, on_changed):
        super().__init__()
        self.settings = settings
        self.on_changed = on_changed
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(page_title(_("Apariencia")))

        theme = SettingsSection(_("Tema"))
        picker = AccentColorPicker(self.settings.appearance.accent_color)
        picker.color_changed.connect(self._on_accent_changed)
        theme.add_row(SettingsRow(_("Color de acento"), _("Color principal de la interfaz"), picker))

        dynamic = AnimatedToggle()
        dynamic.setChecked(self.settings.appearance.use_dynamic_color)
        dynamic.toggled.connect(lambda checked: self._set_appearance("use_dynamic_color", checked))
        theme.add_row(SettingsRow(_("Color dinámico"), _("Cambia el acento según el artwork actual"), dynamic))

        mode = GlassComboBox()
        mode.addItems(["dark", "light", "system"])
        mode.setCurrentText(self.settings.appearance.theme_mode)
        mode.currentTextChanged.connect(lambda value: self._set_appearance("theme_mode", value))
        
        self.mode_combo = mode
        theme.add_row(SettingsRow(_("Tema"), _("Modo visual preferido"), mode))
        layout.addWidget(theme)

        interface = SettingsSection(_("Interfaz"))
        compact = AnimatedToggle()
        compact.setChecked(self.settings.appearance.compact_sidebar)
        compact.toggled.connect(lambda checked: self._set_appearance("compact_sidebar", checked))
        interface.add_row(SettingsRow(_("Barra lateral compacta"), _("Reduce la barra lateral a iconos"), compact))

        blur = AnimatedToggle()
        blur.setChecked(self.settings.appearance.show_artwork_blur_bg)
        blur.toggled.connect(lambda checked: self._set_appearance("show_artwork_blur_bg", checked))
        interface.add_row(SettingsRow(_("Brillo de carátula en fondo"), _("Usa el artwork como atmósfera del reproductor"), blur))
        
        # Selector de idioma
        lang_combo = GlassComboBox()
        lang_combo.addItems([_("Español"), _("Inglés")])
        lang_combo.setCurrentText(_("Español") if self.settings.language == "es" else _("Inglés"))
        lang_combo.currentTextChanged.connect(self._on_language_changed)
        interface.add_row(SettingsRow(_("Idioma"), _("Idioma de la aplicación"), lang_combo))
        
        layout.addWidget(interface)
        layout.addStretch()

    def _on_accent_changed(self, color: str) -> None:
        self.settings.appearance.accent_color = color
        self.on_changed(self.settings)

    def _set_appearance(self, key: str, value) -> None:
        setattr(self.settings.appearance, key, value)
        self.on_changed(self.settings)

    def _on_language_changed(self, lang_text: str) -> None:
        lang_code = "es" if lang_text == _("Español") else "en"
        self.settings.language = lang_code
        from doremi.utils.i18n import set_language
        set_language(lang_code)
        self.on_changed(self.settings)
        
        from doremi.ui.widgets.toast import ToastNotification
        ToastNotification.show(self, _("Idioma cambiado. Reinicia la aplicación para aplicarlo en toda la interfaz."), "success")



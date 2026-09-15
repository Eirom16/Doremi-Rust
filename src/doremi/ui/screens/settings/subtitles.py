from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget, QHBoxLayout, QPushButton, QLabel

from doremi.ui.screens.settings.components import SettingsRow, SettingsSection, page_title
from doremi.ui.widgets.animated_toggle import AnimatedToggle
from doremi.ui.widgets.glass_combobox import GlassComboBox
from doremi.ui.design.fonts import AppFont

class ValueAdjuster(QWidget):
    def __init__(self, value, step, suffix, on_change, min_val=None, max_val=None):
        super().__init__()
        self.value = value
        self.step = step
        self.suffix = suffix
        self.on_change = on_change
        self.min_val = min_val
        self.max_val = max_val
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        self.btn_dec = QPushButton("-")
        self.btn_dec.setFixedSize(32, 32)
        self.btn_dec.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_dec.clicked.connect(self._dec)
        
        self.lbl_val = QLabel(f"{self.value}{self.suffix}")
        self.lbl_val.setFont(AppFont.body(13))
        self.lbl_val.setFixedWidth(80)
        self.lbl_val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.btn_inc = QPushButton("+")
        self.btn_inc.setFixedSize(32, 32)
        self.btn_inc.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_inc.clicked.connect(self._inc)
        
        layout.addWidget(self.btn_dec)
        layout.addWidget(self.lbl_val)
        layout.addWidget(self.btn_inc)
        
        self._style_buttons()
        
    def _style_buttons(self):
        from doremi.ui.design import tokens
        style = f"""
            QPushButton {{
                background-color: {tokens.CURRENT.bg_elevated};
                color: {tokens.CURRENT.text_primary};
                border: 1px solid {tokens.CURRENT.border};
                border-radius: 8px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {tokens.CURRENT.bg_high};
                color: {tokens.CURRENT.accent};
                border-color: {tokens.CURRENT.accent};
            }}
        """
        self.btn_dec.setStyleSheet(style)
        self.btn_inc.setStyleSheet(style)
        self.lbl_val.setStyleSheet(f" background: transparent; color: {tokens.CURRENT.text_primary};")

    def changeEvent(self, event) -> None:
        from PySide6.QtCore import QEvent
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.StyleChange):
            self._style_buttons()
        super().changeEvent(event)

    def _dec(self):
        self.value -= self.step
        if self.min_val is not None and self.value < self.min_val:
            self.value = self.min_val
        self.lbl_val.setText(f"{self.value}{self.suffix}")
        self.on_change(self.value)

    def _inc(self):
        self.value += self.step
        if self.max_val is not None and self.value > self.max_val:
            self.value = self.max_val
        self.lbl_val.setText(f"{self.value}{self.suffix}")
        self.on_change(self.value)

class SubtitlesSettingsScreen(QWidget):
    def __init__(self, settings, on_changed):
        super().__init__()
        self.settings = settings
        self.on_changed = on_changed
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(page_title("Letras y Subtítulos"))

        visual = SettingsSection("Visualización")
        
        # Alignment Combo
        align_map = {"Centrado": "center", "Izquierda": "left", "Derecha": "right"}
        align_map_rev = {v: k for k, v in align_map.items()}
        align_combo = GlassComboBox()
        align_combo.addItems(["Centrado", "Izquierda", "Derecha"])
        align_combo.setCurrentText(align_map_rev.get(self.settings.subtitles.alignment, "Centrado"))
        align_combo.currentTextChanged.connect(lambda val: self._set_subtitle_pref("alignment", align_map[val]))
        visual.add_row(SettingsRow("Alineación del texto", "Alinea las letras horizontalmente", align_combo))

        # Font Size Adjuster
        font_size_adjuster = ValueAdjuster(
            value=self.settings.subtitles.font_size,
            step=1,
            suffix=" pt",
            on_change=lambda val: self._set_subtitle_pref("font_size", val),
            min_val=10,
            max_val=36
        )
        visual.add_row(SettingsRow("Tamaño de letra", "Tamaño de la fuente de las letras", font_size_adjuster))
        
        # Line Spacing Adjuster
        line_spacing_adjuster = ValueAdjuster(
            value=int(self.settings.subtitles.line_spacing * 10),
            step=1,
            suffix="x",
            on_change=lambda val: self._set_subtitle_pref("line_spacing", val / 10.0),
            min_val=10,
            max_val=30
        )
        # Modify the display value to divide by 10 to show e.g. "1.5x"
        line_spacing_adjuster.lbl_val.setText(f"{self.settings.subtitles.line_spacing}x")
        def custom_dec():
            line_spacing_adjuster.value -= line_spacing_adjuster.step
            if line_spacing_adjuster.value < 10:
                line_spacing_adjuster.value = 10
            val = line_spacing_adjuster.value / 10.0
            line_spacing_adjuster.lbl_val.setText(f"{val}x")
            self._set_subtitle_pref("line_spacing", val)
        def custom_inc():
            line_spacing_adjuster.value += line_spacing_adjuster.step
            if line_spacing_adjuster.value > 30:
                line_spacing_adjuster.value = 30
            val = line_spacing_adjuster.value / 10.0
            line_spacing_adjuster.lbl_val.setText(f"{val}x")
            self._set_subtitle_pref("line_spacing", val)
        line_spacing_adjuster.btn_dec.clicked.disconnect()
        line_spacing_adjuster.btn_dec.clicked.connect(custom_dec)
        line_spacing_adjuster.btn_inc.clicked.disconnect()
        line_spacing_adjuster.btn_inc.clicked.connect(custom_inc)
        
        visual.add_row(SettingsRow("Espacio entre líneas", "Ajusta la separación entre párrafos de letra", line_spacing_adjuster))

        layout.addWidget(visual)

        sync_sec = SettingsSection("Sincronización")
        
        # Delay Adjuster
        delay_adjuster = ValueAdjuster(
            value=self.settings.subtitles.delay_ms,
            step=100,
            suffix=" ms",
            on_change=lambda val: self._set_subtitle_pref("delay_ms", val),
            min_val=-5000,
            max_val=5000
        )
        sync_sec.add_row(SettingsRow("Retraso de letras", "Retrasa/adelanta manualmente las letras respecto al audio", delay_adjuster))

        # Auto-scroll Toggle
        scroll_toggle = AnimatedToggle()
        scroll_toggle.setChecked(self.settings.subtitles.auto_scroll)
        scroll_toggle.toggled.connect(lambda checked: self._set_subtitle_pref("auto_scroll", checked))
        sync_sec.add_row(SettingsRow("Auto-desplazamiento", "Desplaza verticalmente de manera automática al cantar", scroll_toggle))
        
        layout.addWidget(sync_sec)

        effects_sec = SettingsSection("Efectos")
        
        # Animation Combo
        anim_map = {"Ninguno": "none", "Desvanecer": "fade", "Brillar": "glow", "Slide": "slide", "Karaoke": "karaoke"}
        anim_map_rev = {v: k for k, v in anim_map.items()}
        anim_combo = GlassComboBox()
        anim_combo.addItems(["Ninguno", "Desvanecer", "Brillar", "Slide", "Karaoke"])
        anim_combo.setCurrentText(anim_map_rev.get(self.settings.subtitles.animation_style, "Brillar"))
        anim_combo.currentTextChanged.connect(lambda val: self._set_subtitle_pref("animation_style", anim_map[val]))
        effects_sec.add_row(SettingsRow("Efecto de Desplazamiento", "Estilo de la animación al pasar de línea", anim_combo))

        # Glow Toggle
        glow_toggle = AnimatedToggle()
        glow_toggle.setChecked(self.settings.subtitles.glow_effect)
        glow_toggle.toggled.connect(lambda checked: self._set_subtitle_pref("glow_effect", checked))
        effects_sec.add_row(SettingsRow("Efecto de Brillo Activo", "Resalta e ilumina la línea que se está cantando", glow_toggle))
        
        layout.addWidget(effects_sec)
        layout.addStretch()

    def _set_subtitle_pref(self, key: str, value) -> None:
        setattr(self.settings.subtitles, key, value)
        self.on_changed(self.settings)

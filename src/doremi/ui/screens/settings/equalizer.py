from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSlider, QVBoxLayout, QWidget

from doremi.config.themes import EQ_BAND_LABELS, EQ_PRESETS
from doremi.ui.design.fonts import AppFont
from doremi.ui.screens.settings.components import SettingsRow, SettingsSection, page_title
from doremi.ui.widgets.animated_toggle import AnimatedToggle
from doremi.ui.widgets.ripple_button import RippleButton
from doremi.ui.widgets.glass_combobox import GlassComboBox


class EqBandSlider(QWidget):
    value_changed = Signal(int, float)

    def __init__(self, band_index: int, label: str, parent=None):
        super().__init__(parent)
        self.band_index = band_index
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.value_label = QLabel("0 dB")
        self.value_label.setFont(AppFont.caption(10))
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.value_label)

        self.slider = QSlider(Qt.Orientation.Vertical)
        self.slider.setRange(-120, 120)
        self.slider.setFixedSize(28, 180)
        self.slider.valueChanged.connect(self._on_value)
        layout.addWidget(self.slider, alignment=Qt.AlignmentFlag.AlignHCenter)

        self._freq_label = QLabel(label)
        self._freq_label.setFont(AppFont.caption(9))
        self._freq_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._freq_label)

        self._update_band_styles()

    def _on_value(self, value: int) -> None:
        db = value / 10.0
        self.value_label.setText(f"{'+' if db > 0 else ''}{db:.1f} dB")
        self._update_band_styles()
        self.value_changed.emit(self.band_index, db)

    def _update_band_styles(self) -> None:
        from doremi.ui.design import tokens
        db = self.slider.value() / 10.0
        color = tokens.CURRENT.accent if db != 0 else tokens.CURRENT.text_secondary
        self.value_label.setStyleSheet(f"color: {color}; background: transparent;")
        if hasattr(self, "_freq_label") and self._freq_label:
            self._freq_label.setStyleSheet(f" background: transparent;")

    def changeEvent(self, event) -> None:
        from PySide6.QtCore import QEvent
        if event.type() in (QEvent.Type.PaletteChange,):
            if not getattr(self, '_in_style_change', False):
                self._in_style_change = True
                try:
                    self._update_band_styles()
                finally:
                    self._in_style_change = False
        super().changeEvent(event)

    def set_value(self, db: float) -> None:
        self.slider.blockSignals(True)
        self.slider.setValue(int(db * 10))
        self.slider.blockSignals(False)
        self._on_value(int(db * 10))


class EqualizerSettingsScreen(QWidget):
    def __init__(self, settings, on_changed):
        super().__init__()
        self.settings = settings
        self.on_changed = on_changed
        self.band_sliders: list[EqBandSlider] = []
        self._build_ui()
        self._load_from_settings()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(page_title("Ecualizador"))

        controls = SettingsSection("Control")
        enabled = AnimatedToggle()
        enabled.setChecked(self.settings.equalizer.enabled)
        enabled.toggled.connect(self._on_enabled_changed)
        controls.add_row(SettingsRow("Activado", "Aplica el ecualizador de 10 bandas", enabled))

        self.preset_combo = GlassComboBox()
        self.preset_combo.addItems(list(EQ_PRESETS.keys()))
        self.preset_combo.setCurrentText(self.settings.equalizer.preset_name)
        self.preset_combo.currentTextChanged.connect(self._on_preset_changed)
        
        controls.add_row(SettingsRow("Preset", "Curva base para ajustar rapido", self.preset_combo))
        layout.addWidget(controls)

        preamp_section = SettingsSection("Ganancia")
        preamp_row = QWidget()
        row = QHBoxLayout(preamp_row)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        self.preamp_slider = QSlider(Qt.Orientation.Horizontal)
        self.preamp_slider.setRange(-120, 120)
        self.preamp_slider.valueChanged.connect(lambda value: (self._update_preamp_label(value), self._emit_eq()))
        self.preamp_value = QLabel("0.0 dB")
        self.preamp_value.setFont(AppFont.mono(12))
        row.addWidget(self.preamp_slider)
        row.addWidget(self.preamp_value)
        preamp_section.add_row(SettingsRow("Preamp", "Nivel general antes de las bandas", preamp_row))
        layout.addWidget(preamp_section)

        self.eq_card = QFrame()
        self.eq_card.setObjectName("eqCard")
        band_layout = QHBoxLayout(self.eq_card)
        band_layout.setContentsMargins(24, 20, 24, 20)
        band_layout.setSpacing(12)
        for i, label in enumerate(EQ_BAND_LABELS):
            slider = EqBandSlider(i, label)
            slider.value_changed.connect(lambda index, db: self._emit_eq())
            self.band_sliders.append(slider)
            band_layout.addWidget(slider)
        layout.addWidget(self.eq_card)

        reset = RippleButton("Reiniciar", "ghost")
        reset.clicked.connect(self._reset)
        layout.addWidget(reset, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addStretch()

        self._update_eq_styles()

    def _update_eq_styles(self) -> None:
        from doremi.ui.design import tokens
        from PySide6.QtGui import QColor
        accent = tokens.CURRENT.accent
        c = QColor(accent)
        r, g, b = c.red(), c.green(), c.blue()
        
        # 1. Card styles
        if hasattr(self, "eq_card") and self.eq_card:
            self.eq_card.setStyleSheet(f"""
                QFrame#eqCard {{
                    background: {tokens.CURRENT.bg_elevated};
                    border-radius: 18px;
                    border: 1px solid rgba({r},{g},{b},0.08);
                }}
            """)

            
        # 3. Preamp value text color
        if hasattr(self, "preamp_value") and self.preamp_value:
            self.preamp_value.setStyleSheet(f"color: {tokens.CURRENT.accent}; min-width: 60px; background: transparent;")

    def changeEvent(self, event) -> None:
        from PySide6.QtCore import QEvent
        if event.type() in (QEvent.Type.PaletteChange,):
            if not getattr(self, '_in_style_change', False):
                self._in_style_change = True
                try:
                    self._update_eq_styles()
                finally:
                    self._in_style_change = False
        super().changeEvent(event)

    def _load_from_settings(self) -> None:
        eq = self.settings.equalizer
        self.preamp_slider.setValue(int(eq.preamp * 10))
        for i, gain in enumerate(eq.bands[:10]):
            self.band_sliders[i].set_value(gain)

    def _on_enabled_changed(self, checked: bool) -> None:
        self.settings.equalizer.enabled = checked
        self._emit_eq()

    def _on_preset_changed(self, preset_name: str) -> None:
        preamp, bands = EQ_PRESETS.get(preset_name, (0.0, [0.0] * 10))
        self.settings.equalizer.preset_name = preset_name
        self.preamp_slider.setValue(int(preamp * 10))
        for i, gain in enumerate(bands[:10]):
            self.band_sliders[i].set_value(gain)
        self._emit_eq()

    def _reset(self) -> None:
        self._on_preset_changed("Flat")

    def _update_preamp_label(self, value: int) -> None:
        db = value / 10.0
        self.preamp_value.setText(f"{'+' if db > 0 else ''}{db:.1f} dB")

    def _emit_eq(self) -> None:
        self.settings.equalizer.preamp = self.preamp_slider.value() / 10.0
        self.settings.equalizer.bands = [slider.slider.value() / 10.0 for slider in self.band_sliders]
        # Debounce: apply_equalizer (VLC) + settings save are expensive, so only
        # fire after the user stops moving sliders instead of on every tick.
        if not hasattr(self, "_eq_apply_timer"):
            self._eq_apply_timer = QTimer(self)
            self._eq_apply_timer.setSingleShot(True)
            self._eq_apply_timer.timeout.connect(lambda: self.on_changed(self.settings))
        self._eq_apply_timer.start(200)


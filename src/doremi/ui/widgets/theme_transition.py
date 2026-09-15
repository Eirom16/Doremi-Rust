from PySide6.QtWidgets import QWidget, QFrame, QVBoxLayout, QLabel, QProgressBar
from PySide6.QtCore import Qt, QVariantAnimation, QPropertyAnimation, QEasingCurve, QSize, Property
from PySide6.QtGui import QPainter, QColor, QFont

class ThemeTransitionOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)

        self._overlay_opacity = 1.0

        # Centered Layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Centered Glassmorphic Card
        self.card = QFrame()
        self.card.setObjectName("transitionCard")
        self.card.setFixedSize(360, 160)
        
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(28, 24, 28, 24)
        card_layout.setSpacing(14)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Status Label
        self.status_lbl = QLabel("Aplicando apariencia...")
        self.status_lbl.setFont(QFont("Inter", 15, QFont.Weight.Bold))
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.status_lbl)
        
        # Sleek Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        card_layout.addWidget(self.progress_bar)
        
        # Percentage Label
        self.percent_lbl = QLabel("0%")
        self.percent_lbl.setFont(QFont("Inter", 11, QFont.Weight.Medium))
        self.percent_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.percent_lbl)
        
        self.main_layout.addWidget(self.card)
        
        self.midpoint_fired = False
        self.on_midpoint_callback = None
        self._update_styles()

    def _update_styles(self):
        """Stylize the overlay and centered card based on the current theme tokens."""
        from doremi.ui.design import tokens
        
        bg_surface = tokens.CURRENT.bg_surface
        bg_high = tokens.CURRENT.bg_high
        accent = tokens.CURRENT.accent
        text_primary = tokens.CURRENT.text_primary
        text_secondary = tokens.CURRENT.text_secondary
        border = tokens.CURRENT.border
        
        # Apply premium card border, rounded corners, and background
        self.card.setStyleSheet(f"""
            QFrame#transitionCard {{
                background-color: {bg_surface};
                border: 1.5px solid {border};
                border-radius: 20px;
            }}
        """)
        
        self.status_lbl.setStyleSheet(f"color: {text_primary}; background: transparent; border: none;")
        self.percent_lbl.setStyleSheet(f"color: {text_secondary}; background: transparent; border: none;")
        
        # Smooth progress bar styling
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {bg_high};
                border-radius: 3px;
                border: none;
            }}
            QProgressBar::chunk {{
                background-color: {accent};
                border-radius: 3px;
            }}
        """)

    def _get_overlay_opacity(self) -> float:
        return self._overlay_opacity

    def _set_overlay_opacity(self, value: float) -> None:
        self._overlay_opacity = value
        self.update()

    overlay_opacity = Property(float, _get_overlay_opacity, _set_overlay_opacity)

    def paintEvent(self, event):
        """Draws a full-screen overlay mask to cover style adjustments cleanly."""
        from doremi.ui.design import tokens
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setOpacity(self._overlay_opacity)
        
        # Get theme base color and set a clean 88% opacity
        base_color = QColor(tokens.CURRENT.bg_base)
        base_color.setAlpha(225)  # Premium semi-transparent mask
        
        painter.fillRect(self.rect(), base_color)
        painter.end()

    def start_transition(self, target_theme_mode, target_accent, on_midpoint_callback):
        """Launches the overlay, runs the progress bar animation, and triggers the theme update."""
        self.on_midpoint_callback = on_midpoint_callback
        self.midpoint_fired = False
        
        # Setup styles for current theme before starting the transition
        self._update_styles()
        self._set_overlay_opacity(1.0)
        self.progress_bar.setValue(0)
        self.percent_lbl.setText("0%")
        
        # Pop up instantly
        self.show()
        self.raise_()
        
        # Smooth variant animation from 0 to 100
        self.progress_anim = QVariantAnimation(self)
        self.progress_anim.setDuration(450)  # Short and responsive feel (450ms)
        self.progress_anim.setStartValue(0)
        self.progress_anim.setEndValue(100)
        self.progress_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        def on_value_changed(val):
            self.progress_bar.setValue(val)
            self.percent_lbl.setText(f"{val}%")
            
            # Midpoint (50%): Apply style changes in the background seamlessly
            if val >= 50 and not self.midpoint_fired:
                self.midpoint_fired = True
                if self.on_midpoint_callback:
                    self.on_midpoint_callback()
                    # Re-apply styles with target theme tokens for the fade-out phase
                    self._update_styles()
                    self.update()
        
        self.progress_anim.valueChanged.connect(on_value_changed)
        
        def on_finished():
            # Fade out from 1.0 to 0.0 over 250ms
            self.fade_anim = QPropertyAnimation(self, b"overlay_opacity", self)
            self.fade_anim.setDuration(250)
            self.fade_anim.setStartValue(1.0)
            self.fade_anim.setEndValue(0.0)
            self.fade_anim.setEasingCurve(QEasingCurve.Type.InOutSine)
            self.fade_anim.finished.connect(self.hide)
            self.fade_anim.start()
            
        self.progress_anim.finished.connect(on_finished)
        self.progress_anim.start()

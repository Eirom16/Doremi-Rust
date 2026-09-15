import random
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QVariantAnimation, QPointF, QEasingCurve
from PySide6.QtGui import QPainter, QRadialGradient, QColor
from loguru import logger

from doremi.utils.thread_pool import CPU_POOL
from doremi.native_rs import extract_n_colors as _extract_rust, update_blobs as _blobs_rust

def extract_colors_from_image(image_data: bytes) -> list[QColor]:
    """Extrae 3 colores dominantes con el módulo nativo Rust."""
    try:
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(image_data))
        img = img.convert("RGB").resize((30, 30), Image.LANCZOS)
        raw = list(img.tobytes())
        w, h = img.size
        rgb_list = _extract_rust(raw, w, h, 3)
        if rgb_list and len(rgb_list) == 3:
            return [QColor(r, g, b) for r, g, b in rgb_list]
    except Exception as e:
        logger.warning(f"Error extracting colors: {e}")
    return [QColor(20, 20, 20), QColor(40, 40, 40), QColor(30, 30, 30)]

class AmbientBlob:
    def __init__(self, color: QColor, x_ratio: float, y_ratio: float, radius_ratio: float):
        self.target_color = color
        self.current_color = color
        self.x_ratio = x_ratio
        self.y_ratio = y_ratio
        self.target_x_ratio = x_ratio
        self.target_y_ratio = y_ratio
        self.radius_ratio = radius_ratio

class AmbientBackgroundWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        
        self._blobs = [
            AmbientBlob(QColor(10, 10, 10), 0.2, 0.2, 0.8),
            AmbientBlob(QColor(15, 15, 15), 0.8, 0.8, 0.9),
            AmbientBlob(QColor(20, 20, 20), 0.5, 0.5, 1.0)
        ]
        self._raw_colors = []
        self._last_paint_time = 0.0  # throttle repaints to ~20fps
        
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(15000) # 15 seconds for a full fluid movement cycle
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setLoopCount(-1) # infinite
        self._anim.valueChanged.connect(self._on_anim_step)
        
        # Fade animation for color transitions
        self._color_anim = QVariantAnimation(self)
        self._color_anim.setDuration(2000)
        self._color_anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._color_anim.valueChanged.connect(self._on_color_fade)
        
        self._generate_new_targets()
        self._anim.start()
        self.update_theme_styles()

    def _generate_new_targets(self):
        """Genera nuevas posiciones objetivo para que los blobs se muevan suavemente."""
        for blob in self._blobs:
            blob.target_x_ratio = random.uniform(0.1, 0.9)
            blob.target_y_ratio = random.uniform(0.1, 0.9)

    def _on_anim_step(self, val):
        import time

        # ── Throttle a 20fps (los blobs se mueven en 15s, imperceptible a 60fps) ──
        now = time.monotonic()
        if not hasattr(self, '_last_paint_time'):
            self._last_paint_time = 0.0
        if now - self._last_paint_time < 0.050:  # 50ms = 20fps
            return
        self._last_paint_time = now

        # ── Paso de animación de blobs (módulo nativo Rust) ───────────────────
        xs  = [b.x_ratio for b in self._blobs]
        ys  = [b.y_ratio for b in self._blobs]
        txs = [b.target_x_ratio for b in self._blobs]
        tys = [b.target_y_ratio for b in self._blobs]

        new_xs, new_ys, reached = _blobs_rust(xs, ys, txs, tys, 0.005, 0.0025)
        for i, blob in enumerate(self._blobs):
            blob.x_ratio = new_xs[i]
            blob.y_ratio = new_ys[i]
        if reached == len(self._blobs):
            self._generate_new_targets()
        self.update()

    def _on_color_fade(self, progress: float):
        for blob in self._blobs:
            # Interpolar color actual hacia el objetivo
            r = int(blob.current_color.red() + (blob.target_color.red() - blob.current_color.red()) * progress)
            g = int(blob.current_color.green() + (blob.target_color.green() - blob.current_color.green()) * progress)
            b = int(blob.current_color.blue() + (blob.target_color.blue() - blob.current_color.blue()) * progress)
            blob.current_color = QColor(r, g, b)
        self.update()

    def update_theme_styles(self):
        """Refreshes the dynamic blob colors when the theme changes."""
        from doremi.ui.design import tokens
        from PySide6.QtGui import QColor
        is_light = QColor(tokens.CURRENT.bg_base).lightness() > 128
        
        if getattr(self, "_using_default_colors", True) or not getattr(self, "_raw_colors", None):
            self._using_default_colors = True
            if is_light:
                self._raw_colors = [QColor(230, 230, 250), QColor(240, 248, 255), QColor(245, 245, 250)]
            else:
                self._raw_colors = [QColor(30, 20, 50), QColor(20, 40, 50), QColor(40, 20, 40)]
        
        self._set_colors(self._raw_colors)

    def set_image(self, image_data: bytes):
        """Actualiza el fondo extrayendo colores de los bytes de la imagen."""
        from doremi.ui.design import tokens
        from PySide6.QtGui import QColor
        is_light = QColor(tokens.CURRENT.bg_base).lightness() > 128
        
        if not image_data:
            self._using_default_colors = True
            if is_light:
                default_colors = [QColor(230, 230, 250), QColor(240, 248, 255), QColor(245, 245, 250)]
            else:
                default_colors = [QColor(30, 20, 50), QColor(20, 40, 50), QColor(40, 20, 40)]
            self._raw_colors = default_colors
            self._set_colors(default_colors)
            return
            
        def on_done(future):
            try:
                colors = future.result()
            except Exception:
                if is_light:
                    colors = [QColor(230, 230, 250), QColor(240, 248, 255), QColor(245, 245, 250)]
                else:
                    colors = [QColor(30, 20, 50), QColor(20, 40, 50), QColor(40, 20, 40)]
            
            # Ejecutar en hilo principal
            import shiboken6
            if shiboken6.isValid(self):
                from PySide6.QtCore import QTimer
                def apply_colors():
                    self._using_default_colors = False
                    self._raw_colors = colors
                    self._set_colors(colors)
                QTimer.singleShot(0, self, apply_colors)

        future = CPU_POOL.submit(extract_colors_from_image, image_data)
        future.add_done_callback(on_done)

    def _set_colors(self, colors: list[QColor]):
        from doremi.ui.design import tokens
        is_light = QColor(tokens.CURRENT.bg_base).lightness() > 128
        
        if len(colors) >= len(self._blobs):
            for i, blob in enumerate(self._blobs):
                c = colors[i]
                # Convert to HSV to manipulate
                h, s, v, a = c.getHsv()
                
                if is_light:
                    # Light mode: bright, soft pastel colors
                    s = min(80, int(s * 0.4))       # Low saturation (pastel)
                    v = max(220, int(255 - (255 - v) * 0.3)) # High brightness
                    alpha = 100                     # Subtle opacity for blending
                else:
                    # Dark mode: vibrant, visible glowing aura
                    s = max(100, min(255, int(s * 1.5))) # Boost saturation for rich depth
                    v = max(55, min(115, int(v * 0.8)))   # Make it bright enough to be visible, but dark enough to keep text readable
                    alpha = 150                     # Ideal opacity for dark atmospheric glow
                
                new_color = QColor.fromHsv(h, s, v)
                new_color.setAlpha(alpha)
                blob.target_color = new_color
                
            self._color_anim.stop()
            self._color_anim.setStartValue(0.0)
            self._color_anim.setEndValue(1.0)
            self._color_anim.start()

    def paintEvent(self, event):
        from doremi.ui.design import tokens
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Base background: dynamic base theme color
        painter.fillRect(self.rect(), QColor(tokens.CURRENT.bg_base))
        
        w = self.width()
        h = self.height()
        
        # Draw blobs
        for blob in self._blobs:
            cx = w * blob.x_ratio
            cy = h * blob.y_ratio
            # Reduce radius slightly to create more distinct light pools
            radius = max(w, h) * (blob.radius_ratio * 0.7)
            
            grad = QRadialGradient(QPointF(cx, cy), radius)
            grad.setColorAt(0, blob.current_color)
            
            # Fade out to fully transparent
            transparent_color = QColor(blob.current_color)
            transparent_color.setAlpha(0)
            grad.setColorAt(1, transparent_color)
            
            painter.setBrush(grad)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(self.rect())
            
        # Añadir un overlay de ruido oscuro sutil si se desea, o simplemente desenfoque extra
        # Se asume que el radial gradient ya se ve desenfocado.

import asyncio
import datetime
from collections import Counter
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QGraphicsOpacityEffect, QFrame
)
from PySide6.QtGui import QFont, QPainter, QColor, QLinearGradient, QBrush, QPen
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, Signal
from loguru import logger
from qasync import asyncSlot

from doremi.ui.widgets.song_card import SongCard
from doremi.ui.widgets.error_state import ErrorStateWidget
from doremi.ui.design import tokens


class CustomBarChart(QWidget):
    def __init__(self, data: list[tuple[str, int]], parent=None):
        super().__init__(parent)
        self.data = data
        self.setMinimumHeight(280)
        self.setMaximumHeight(350)

    def set_data(self, data: list[tuple[str, int]]):
        self.data = data
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        accent_color = QColor(tokens.CURRENT.accent)
        border_color = QColor(tokens.CURRENT.border)
        bg_color = QColor(tokens.CURRENT.bg_elevated)
        text_primary = QColor(tokens.CURRENT.text_primary)
        text_secondary = QColor(tokens.CURRENT.text_secondary)

        rect = self.rect()
        
        # Draw background rounded frame
        painter.setBrush(QBrush(bg_color))
        painter.setPen(QPen(border_color, 1))
        painter.drawRoundedRect(rect.adjusted(2, 2, -2, -2), 16, 16)

        if not self.data:
            painter.setPen(QPen(text_secondary))
            painter.setFont(QFont("Inter", 12))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "Sin datos suficientes para graficar")
            painter.end()
            return

        # Title
        painter.setPen(QPen(text_primary))
        painter.setFont(QFont("Inter", 11, QFont.Weight.Bold))
        painter.drawText(20, 30, "Canciones Reproducidas por Día")

        # Graph area dimensions
        margin_left = 45
        margin_right = 20
        margin_top = 65
        margin_bottom = 40
        width = rect.width() - margin_left - margin_right
        height = rect.height() - margin_top - margin_bottom

        # Get max value
        max_val = max([val for _, val in self.data]) if self.data else 1
        if max_val == 0:
            max_val = 1

        # Draw grid lines & values
        grid_lines = 4
        painter.setPen(QPen(QColor(border_color.red(), border_color.green(), border_color.blue(), 50), 1))
        painter.setFont(QFont("Inter", 8))
        for i in range(grid_lines + 1):
            y = margin_top + int(height * (1 - i / grid_lines))
            painter.drawLine(margin_left, y, margin_left + width, y)
            grid_val = int(max_val * i / grid_lines)
            painter.setPen(QPen(text_secondary))
            painter.drawText(margin_left - 35, y + 4, str(grid_val))
            painter.setPen(QPen(QColor(border_color.red(), border_color.green(), border_color.blue(), 50), 1))

        # Draw bars
        bar_count = len(self.data)
        bar_width = int(width / (bar_count * 1.6 + 0.6))
        gap = int(bar_width * 0.6)

        for idx, (label, val) in enumerate(self.data):
            x = margin_left + gap + idx * (bar_width + gap)
            bar_height = int(height * (val / max_val))
            y = margin_top + height - bar_height

            # Gradient brush for premium visual aesthetic
            grad = QLinearGradient(x, y, x, y + bar_height)
            grad.setColorAt(0, accent_color)
            grad.setColorAt(1, QColor(accent_color.red(), accent_color.green(), accent_color.blue(), 40))

            painter.setBrush(QBrush(grad))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(x, y, bar_width, bar_height, 6, 6)

            # Draw top value label
            painter.setPen(QPen(text_primary))
            painter.setFont(QFont("Inter", 9, QFont.Weight.Bold))
            painter.drawText(x, y - 18, bar_width, 15, Qt.AlignmentFlag.AlignCenter, str(val))

            # Draw day/label
            painter.setPen(QPen(text_secondary))
            painter.setFont(QFont("Inter", 9))
            painter.drawText(x - gap//2, margin_top + height + 8, bar_width + gap, 20, Qt.AlignmentFlag.AlignCenter, label)

        painter.end()


class StatCard(QFrame):
    def __init__(self, title: str, value: str, icon_text: str, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._build_ui(title, value, icon_text)

    def _build_ui(self, title: str, value: str, icon_text: str):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        from doremi.ui.design.icons import Icon
        
        # Rounded icon badge
        self.icon_badge = QLabel()
        self.icon_badge.setFixedSize(48, 48)
        self.icon_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_badge.setFont(Icon.font(22))
        self.icon_badge.setText(Icon.get(icon_text))
        
        # Value & Label info column
        info_col = QVBoxLayout()
        info_col.setSpacing(2)
        
        self.val_label = QLabel(value)
        self.val_label.setFont(QFont("Inter", 18, QFont.Weight.Bold))
        
        self.title_label = QLabel(title)
        self.title_label.setFont(QFont("Inter", 11, QFont.Weight.Medium))
        
        info_col.addWidget(self.val_label)
        info_col.addWidget(self.title_label)
        
        layout.addWidget(self.icon_badge)
        layout.addLayout(info_col)
        layout.addStretch()
        
        self._apply_theme_style()

    def update_value(self, value: str):
        self.val_label.setText(value)

    def _apply_theme_style(self):
        from doremi.ui.design import tokens
        from PySide6.QtGui import QColor
        accent = tokens.CURRENT.accent
        c = QColor(accent)
        r, g, b, _ = c.getRgb()

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {tokens.CURRENT.bg_elevated};
                border: 1px solid {tokens.CURRENT.border};
                border-radius: 16px;
            }}
        """)
        self.icon_badge.setStyleSheet(f"""
            QLabel {{
                background-color: rgba({r},{g},{b},0.15);
                color: {accent};
                border: none;
                border-radius: 24px;
            }}
        """)
        self.val_label.setStyleSheet(f" border: none; background: transparent;")
        self.title_label.setStyleSheet(f" border: none; background: transparent;")


class StatsScreen(QWidget):
    download_requested = Signal(str, str, str, str)
    play_next_requested = Signal(str, str, str, str)
    add_to_queue_requested = Signal(str, str, str, str)
    like_requested = Signal(str, object)
    add_to_playlist_requested = Signal(str, str)
    delete_download_requested = Signal(str)
    artist_clicked = Signal(str)
    album_clicked = Signal(str)

    def __init__(self, yt_client, on_play_song):
        super().__init__()
        self.yt = yt_client
        self.on_play_song = on_play_song
        self._build_ui()

    def _connect_card_signals(self, card):
        card.download_requested.connect(lambda *a: self.download_requested.emit(*a))
        card.play_next_requested.connect(lambda *a: self.play_next_requested.emit(*a))
        card.add_to_queue_requested.connect(lambda *a: self.add_to_queue_requested.emit(*a))
        card.like_requested.connect(lambda *a: self.like_requested.emit(*a))
        card.add_to_playlist_requested.connect(lambda *a: self.add_to_playlist_requested.emit(*a))
        card.delete_download_requested.connect(lambda *a: self.delete_download_requested.emit(*a))
        if hasattr(card, "artist_clicked"):
            card.artist_clicked.connect(lambda *a: self.artist_clicked.emit(*a))
        if hasattr(card, "album_clicked"):
            card.album_clicked.connect(lambda *a: self.album_clicked.emit(*a))

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(16)

        # Header section
        header_row = QHBoxLayout()
        header_col = QVBoxLayout()
        header_col.setSpacing(2)
        
        self.header = QLabel("Tus Estadísticas")
        self.header.setFont(QFont("Inter", 24, QFont.Weight.Bold))
        self.header.setStyleSheet(f"")
        
        self.subtitle = QLabel("Analiza tus hábitos musicales y descubre tus canciones favoritas")
        self.subtitle.setFont(QFont("Inter", 12))
        self.subtitle.setStyleSheet(f"")
        
        header_col.addWidget(self.header)
        header_col.addWidget(self.subtitle)
        header_row.addLayout(header_col)
        header_row.addStretch()
        main_layout.addLayout(header_row)

        # Scroll Area for premium responsively scrollable dashboard
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("background: transparent; border: none;")
        
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 112)
        self.content_layout.setSpacing(24)

        # 1. Cards Row
        self.cards_layout = QHBoxLayout()
        self.cards_layout.setSpacing(16)
        
        self.time_card = StatCard("Tiempo Escuchado", "0m", "schedule")
        self.plays_card = StatCard("Total Reproducidas", "0", "play_arrow")
        self.artists_card = StatCard("Artistas Únicos", "0", "artist")
        
        self.cards_layout.addWidget(self.time_card)
        self.cards_layout.addWidget(self.plays_card)
        self.cards_layout.addWidget(self.artists_card)
        self.content_layout.addLayout(self.cards_layout)

        # 2. Main Columns Layout
        self.columns_layout = QHBoxLayout()
        self.columns_layout.setSpacing(20)

        # Left: Top Songs Column
        self.songs_col = QVBoxLayout()
        self.songs_col.setSpacing(12)
        
        self.songs_title = QLabel("Tus 5 Más Escuchadas")
        self.songs_title.setFont(QFont("Inter", 14, QFont.Weight.Bold))
        self.songs_title.setStyleSheet(f"")
        self.songs_col.addWidget(self.songs_title)
        
        self.songs_container = QVBoxLayout()
        self.songs_container.setSpacing(8)
        self.songs_col.addLayout(self.songs_container)
        self.songs_col.addStretch()

        # Right: Bar Chart Column
        self.chart_col = QVBoxLayout()
        self.chart_col.setSpacing(12)
        
        self.chart_title = QLabel("Actividad de Escucha")
        self.chart_title.setFont(QFont("Inter", 14, QFont.Weight.Bold))
        self.chart_title.setStyleSheet(f"")
        self.chart_col.addWidget(self.chart_title)
        
        self.bar_chart = CustomBarChart([])
        self.chart_col.addWidget(self.bar_chart)
        self.chart_col.addStretch()

        self.columns_layout.addLayout(self.songs_col, 5)
        self.columns_layout.addLayout(self.chart_col, 5)
        self.content_layout.addLayout(self.columns_layout)

        self.scroll.setWidget(self.content_widget)
        main_layout.addWidget(self.scroll)

    def _format_duration(self, ms):
        if not ms:
            return ""
        seconds = ms // 1000
        mins = seconds // 60
        secs = seconds % 60
        return f"{mins}:{secs:02d}"

    def _handle_play(self, video_id, title, artists, thumbnail_url, duration_ms=0):
        try:
            if self.on_play_song:
                self.on_play_song(video_id, title, artists, "", duration_ms, thumbnail_url)
        except Exception as e:
            logger.error(f"Play error: {e}")

    def _fade_in_content(self):
        effect = QGraphicsOpacityEffect(self.content_widget)
        self.content_widget.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(300)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.finished.connect(lambda: self.content_widget.setGraphicsEffect(None))
        anim.start()

    async def load(self):
        try:
            await self._load_async()
        except Exception as e:
            logger.error(f"Error loading stats: {e}")
            while self.songs_container.count():
                item = self.songs_container.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            self.songs_container.addWidget(ErrorStateWidget(
                "No se pudieron cargar las estadísticas",
                retry_callback=lambda: asyncio.ensure_future(self.load()),
            ))
            self.bar_chart.set_data([])

    async def _load_async(self):
        # Fetch local history and calculate stats
        from doremi.db.repository import HistoryRepository, SongRepository
        history_repo = HistoryRepository()
        
        # Load all history items to get robust aggregates
        all_history_raw = await history_repo.get_history(limit=500)
        all_history = [entry for entry, _ in all_history_raw]
        liked_ids = await SongRepository().get_liked_video_ids()

        # Clear existing top songs in column
        while self.songs_container.count():
            item = self.songs_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not all_history:
            # Set visual empty placeholders
            self.time_card.update_value("0m")
            self.plays_card.update_value("0")
            self.artists_card.update_value("0")
            
            empty_lbl = QLabel("No hay suficientes reproducciones registradas.")
            empty_lbl.setFont(QFont("Inter", 11))
            empty_lbl.setStyleSheet(f"")
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.songs_container.addWidget(empty_lbl)
            
            self.bar_chart.set_data([])
            self._fade_in_content()
            return

        # 1. Total Listening Time
        total_ms = sum([entry.duration_ms for entry in all_history if entry.duration_ms])
        total_mins = total_ms // 60000
        if total_mins >= 60:
            time_val = f"{total_mins // 60}h {total_mins % 60}m"
        else:
            time_val = f"{total_mins}m"
        self.time_card.update_value(time_val)

        # 2. Total Plays
        self.plays_card.update_value(str(len(all_history)))

        # 3. Unique Artists
        artists = [entry.artist for entry in all_history if entry.artist]
        unique_artists = len(set(artists))
        self.artists_card.update_value(str(unique_artists))

        # 4. Top 5 Played Songs
        song_counter = Counter([(entry.video_id, entry.title, entry.artist) for entry in all_history])
        top_songs = song_counter.most_common(5)

        song_repo = SongRepository()
        from doremi.db.repository import DownloadRepository
        dl_repo = DownloadRepository()

        for (video_id, title, artist), count in top_songs:
            # Suffix/badge text for play counts
            count_suffix = f" — 🔥 {count} veces" if count > 1 else " — 1 vez"
            
            # Retrieve thumbnail url from database
            thumbnail_url = ""
            db_song = await song_repo.get_song(video_id)
            if db_song and db_song.thumbnail_url:
                thumbnail_url = db_song.thumbnail_url
            else:
                db_download = await dl_repo.get_download(video_id)
                if db_download and db_download.thumbnail_url:
                    thumbnail_url = db_download.thumbnail_url
            
            card = SongCard(
                title=title,
                artist=artist + count_suffix,
                duration="",
                on_play=lambda v=video_id, t=title, a=artist, th=thumbnail_url: self._handle_play(v, t, a, th),
                video_id=video_id,
                is_liked=video_id in liked_ids,
                thumbnail_url=thumbnail_url
            )
            self._connect_card_signals(card)
            self.songs_container.addWidget(card)

        # 5. Last 7 Days Activity for the Custom Chart
        # Calculate play count per day of week
        weekday_map = {0: "Lun", 1: "Mar", 2: "Mié", 3: "Jue", 4: "Vie", 5: "Sáb", 6: "Dom"}
        
        # Initialize counts for last 7 days starting from today backwards
        today = datetime.date.today()
        days_data = []
        for i in range(6, -1, -1):
            d = today - datetime.timedelta(days=i)
            days_data.append((d, weekday_map[d.weekday()], 0))

        for entry in all_history:
            if not entry.played_at:
                continue
            entry_date = entry.played_at.date()
            for idx, (d, label, count) in enumerate(days_data):
                if entry_date == d:
                    days_data[idx] = (d, label, count + 1)
                    break

        chart_data = [(label, count) for _, label, count in days_data]
        self.bar_chart.set_data(chart_data)

        self._fade_in_content()

    def _update_stats_styles(self) -> None:
        self.header.setStyleSheet(f" background: transparent;")
        self.subtitle.setStyleSheet(f" background: transparent;")
        self.songs_title.setStyleSheet(f" background: transparent;")
        self.chart_title.setStyleSheet(f" background: transparent;")
        
        # Update cards
        self.time_card._apply_theme_style()
        self.plays_card._apply_theme_style()
        self.artists_card._apply_theme_style()
        
        # Force styles to refresh and chart to repaint
        self.style().unpolish(self)
        self.style().polish(self)
        self.bar_chart.update()

    def changeEvent(self, event) -> None:
        from PySide6.QtCore import QEvent
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.StyleChange):
            if not getattr(self, '_in_style_change', False):
                self._in_style_change = True
                try:
                    self._update_stats_styles()
                finally:
                    self._in_style_change = False
        super().changeEvent(event)

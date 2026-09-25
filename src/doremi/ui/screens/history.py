from functools import partial
import asyncio
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from qasync import asyncSlot
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, Signal
from loguru import logger
from doremi.ui.widgets.song_card import SongCard
from doremi.ui.widgets.error_state import ErrorStateWidget
from doremi.ui.widgets.load_more import PaginatorFooter
from doremi.ui.screens.history_data import gather_history

class HistoryScreen(QWidget):
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
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)

        from doremi.ui.design import tokens
        header_row = QHBoxLayout()
        header = QLabel("Historial")
        header.setFont(QFont("Inter", 24, QFont.Weight.Bold))
        header.setStyleSheet("")
        header_row.addWidget(header)
        header_row.addStretch()

        self.clear_history_btn = QPushButton("Limpiar historial")
        self.clear_history_btn.setObjectName("dangerButton")
        self.clear_history_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_history_btn.clicked.connect(self._on_clear_history_clicked)
        header_row.addWidget(self.clear_history_btn)
        layout.addLayout(header_row)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("background: transparent; border: none;")
        
        self.content_widget = QWidget()
        self._content_wrapper_layout = QVBoxLayout(self.content_widget)
        self._content_wrapper_layout.setContentsMargins(0, 0, 0, 0)
        
        self.content_layout = QVBoxLayout()
        self.content_layout.setSpacing(16)
        self.content_layout.setContentsMargins(24, 0, 24, 112)
        
        self._content_wrapper_layout.addLayout(self.content_layout)
        self._content_wrapper_layout.addStretch()
        
        self.scroll.setWidget(self.content_widget)
        layout.addWidget(self.scroll)

    def _handle_play(self, video_id, title, artists, thumbnail_url="", duration_ms=0):
        try:
            if self.on_play_song:
                self.on_play_song(video_id, title, artists, "", duration_ms, thumbnail_url)
        except Exception as e:
            logger.error(f"Play error: {e}")

    def _fade_in_content(self):
        """Smooth fade-in animation when content finishes loading."""
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
            logger.error(f"Error loading history: {e}")
            self._clear_content()
            self.content_layout.addWidget(ErrorStateWidget(
                "No se pudo cargar el historial",
                retry_callback=lambda: asyncio.ensure_future(self.load()),
            ))

    def _clear_content(self):
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    async def _load_async(self):
        self._clear_content()

        # Show loading skeleton
        from doremi.ui.widgets.skeleton_loader import SkeletonListLoader
        skeleton = SkeletonListLoader(row_count=5)
        self.content_layout.addWidget(skeleton)

        header = QLabel("Reproducido recientemente")
        header.setFont(QFont("Inter", 16, QFont.Weight.Bold))

        combined_history, liked_ids, local_count = await gather_history(self.yt)
        self.clear_history_btn.setEnabled(bool(local_count))

        # Clear skeleton
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.content_layout.addWidget(header)

        # Render combined history
        if combined_history:
            self._history_items = combined_history
            self._history_render_idx = 0
            self._liked_ids = liked_ids
            self._history_paginator = PaginatorFooter()
            self._history_paginator.load_requested.connect(self._on_history_load_more)
            self._render_history_chunk(20)
        else:
            msg = QLabel("Tu historial está vacío\n\nLas canciones que reproduzcas aparecerán aquí")
            msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
            msg.setObjectName("libraryEmptyMessage")
            self.content_layout.addWidget(msg)
            self.content_layout.addStretch()
            self._fade_in_content()

    def _on_clear_history_clicked(self):
        result = QMessageBox.question(
            self,
            "Limpiar historial",
            "¿Eliminar todo el historial local de reproducción?",
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes,
            QMessageBox.StandardButton.Cancel,
        )
        if result != QMessageBox.StandardButton.Yes:
            return

        import asyncio
        asyncio.ensure_future(self._clear_history_async())

    async def _clear_history_async(self):
        try:
            from doremi.db.repository import HistoryRepository
            deleted = await HistoryRepository().clear_history()
            logger.info(f"Cleared {deleted} local history entries")
            await self.load()
        except Exception as e:
            logger.error(f"Error clearing history: {e}")

    def _render_history_chunk(self, chunk_size=20):
        if not hasattr(self, "_history_items") or not self._history_items:
            return
            
        if hasattr(self, "_history_paginator"):
            self.content_layout.removeWidget(self._history_paginator)
            self._history_paginator.setParent(None)
            
        items = self._history_items
        start = self._history_render_idx
        end = min(start + chunk_size, len(items))
        
        for i in range(start, end):
            entry = items[i]
            card = SongCard(
                title=entry['title'],
                artist=entry['artist'],
                duration=entry['duration'],
                thumbnail_url=entry['thumbnail_url'],
                on_play=partial(self._handle_play, entry['videoId'], entry['title'], entry['artist'], entry['thumbnail_url'], entry.get('duration_ms', 0)),
                video_id=entry['videoId'],
                is_liked=entry['videoId'] in self._liked_ids,
            )
            self._connect_card_signals(card)
            self.content_layout.addWidget(card)
            
        self._history_render_idx = end
        
        if self._history_render_idx < len(items):
            self.content_layout.addWidget(self._history_paginator)
            self._history_paginator.set_state("button")
        else:
            self.content_layout.addStretch()
            
        if start == 0:
            self._fade_in_content()

    def _on_history_load_more(self):
        from PySide6.QtCore import QTimer
        QTimer.singleShot(100, lambda: self._render_history_chunk(20))

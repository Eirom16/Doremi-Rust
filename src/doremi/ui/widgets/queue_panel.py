from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea
from PySide6.QtCore import Qt, Signal
from functools import partial
from doremi.utils.time_utils import format_duration_short
from doremi.ui.design.icons import Icon

class QueuePanel(QWidget):
    artist_clicked = Signal(str)
    album_clicked = Signal(str)
    like_requested = Signal(str, object)  # video_id, btn_like widget
    download_requested = Signal(str, str, str, str)
    play_next_requested = Signal(str, str, str, str)
    add_to_queue_requested = Signal(str, str, str, str)
    add_to_playlist_requested = Signal(str, str)
    delete_download_requested = Signal(str)
    queue_move_requested = Signal(int, int)  # from_index, to_index

    def __init__(self, on_play_item=None):
        super().__init__()
        self.on_play_item = on_play_item
        self._build_ui()

    def _build_ui(self):
        self.setObjectName("queuePanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        self.header_lbl = QLabel("Cola de reproducción")
        self.header_lbl.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(self.header_lbl)

        self._apply_style()

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("QScrollArea { background: transparent; border: none; } QScrollArea > QWidget > QWidget { background: transparent; }")
        
        self.queue_list = QWidget()
        self.queue_list.setObjectName("queueList")
        self.queue_layout = QVBoxLayout(self.queue_list)
        self.queue_layout.setContentsMargins(0, 0, 0, 112)
        self.queue_layout.setSpacing(8)
        
        self.scroll_area.setWidget(self.queue_list)
        layout.addWidget(self.scroll_area)

    def set_queue(self, items, liked_ids=None):
        """Update the queue display. liked_ids is a set of video_ids that are liked."""
        if liked_ids is None:
            liked_ids = set()

        while self.queue_layout.count():
            item = self.queue_layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget:
                widget.deleteLater()

        total = len(items)
        for i, item in enumerate(items):
            from doremi.ui.widgets.song_card import SongCard
            duration_str = format_duration_short(item.duration_ms) if getattr(item, 'duration_ms', 0) else ""
            video_id = getattr(item, 'video_id', '')
            
            on_play_cb = partial(self.on_play_item, i) if self.on_play_item else None
            card = SongCard(
                title=item.title,
                artist=item.artist,
                duration=duration_str,
                thumbnail_url=getattr(item, 'thumbnail_url', ''),
                video_id=video_id,
                is_liked=video_id in liked_ids,
                on_play=on_play_cb,
                album=getattr(item, 'album', ''),
            )
            
            # Connect artist_clicked signal
            card.artist_clicked.connect(self.artist_clicked.emit)
            card.album_clicked.connect(self.album_clicked.emit)
            
            # Connect like signal
            card.like_requested.connect(lambda vid, btn: self.like_requested.emit(vid, btn))
            
            # Connect other context menu signals
            card.download_requested.connect(lambda *a: self.download_requested.emit(*a))
            card.play_next_requested.connect(lambda *a: self.play_next_requested.emit(*a))
            card.add_to_queue_requested.connect(lambda *a: self.add_to_queue_requested.emit(*a))
            card.add_to_playlist_requested.connect(lambda *a: self.add_to_playlist_requested.emit(*a))
            card.delete_download_requested.connect(lambda *a: self.delete_download_requested.emit(*a))

            row = QWidget()
            row.setObjectName("queueRow")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)
            row_layout.addWidget(card, stretch=1)

            reorder = QVBoxLayout()
            reorder.setContentsMargins(0, 4, 0, 4)
            reorder.setSpacing(2)

            btn_up = self._make_reorder_button("arrow_upward", "Subir en la cola")
            btn_up.setEnabled(i > 0)
            btn_up.clicked.connect(lambda checked=False, from_i=i: self.queue_move_requested.emit(from_i, from_i - 1))
            reorder.addWidget(btn_up)

            btn_down = self._make_reorder_button("arrow_downward", "Bajar en la cola")
            btn_down.setEnabled(i < total - 1)
            btn_down.clicked.connect(lambda checked=False, from_i=i: self.queue_move_requested.emit(from_i, from_i + 1))
            reorder.addWidget(btn_down)

            row_layout.addLayout(reorder)
            self.queue_layout.addWidget(row)
            
        self.queue_layout.addStretch()

    def _make_reorder_button(self, icon_name: str, accessible_name: str) -> QPushButton:
        btn = QPushButton()
        btn.setText(Icon.get(icon_name))
        btn.setFont(Icon.font(16))
        btn.setFixedSize(28, 28)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setAccessibleName(accessible_name)
        btn.setStyleSheet(self._reorder_button_style())
        return btn

    def _reorder_button_style(self) -> str:
        from doremi.ui.design import tokens
        return f"""
            QPushButton {{
                background: transparent;
                color: {tokens.CURRENT.text_secondary};
                border: none;
                border-radius: 8px;
                font-family: 'Material Symbols Rounded';
            }}
            QPushButton:hover:enabled {{
                background: {tokens.CURRENT.accent_dim};
                color: {tokens.CURRENT.accent};
            }}
            QPushButton:disabled {{
                color: {tokens.CURRENT.text_disabled};
            }}
        """

    def _apply_style(self):
        self.setStyleSheet("""
            #queuePanel {
                background: transparent;
            }
            #queueList {
                background: transparent;
            }
        """)
        if hasattr(self, "header_lbl") and self.header_lbl:
            self.header_lbl.setStyleSheet("background: transparent;")

    def changeEvent(self, event):
        from PySide6.QtCore import QEvent
        if event.type() in (QEvent.Type.PaletteChange,):
            if not getattr(self, '_in_style_change', False):
                self._in_style_change = True
                try:
                    self._apply_style()
                finally:
                    self._in_style_change = False
        super().changeEvent(event)

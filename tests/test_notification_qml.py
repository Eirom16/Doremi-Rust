"""Tests de la isla QML — Panel de notificaciones."""
from __future__ import annotations

import pytest


@pytest.fixture(scope="module")
def qapp():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


class TestNotificationViewModel:
    def test_state_flags(self, qapp):
        from doremi.ui.viewmodels.notification_vm import NotificationViewModel

        vm = NotificationViewModel(qapp)
        assert vm.isEmpty is True
        assert vm.hasActive is False

        vm.add_history("Hola", "info")
        assert vm.isEmpty is False
        assert vm.hasHistory is True

        vm.add_active_download("v1", "Song", "Artista")
        assert vm.hasActive is True
        assert vm.active.rowCount() == 1

        vm.update_active_progress("v1", 55.0, "2MB/s")
        row = vm.active.find_row("v1")
        assert vm.active.data(vm.active.index(row, 0), vm.active.ProgressRole) == 55.0

        vm.finish_active_download("v1")
        assert vm.hasActive is False

        vm.clear_history()
        assert vm.isEmpty is True

    def test_releases_and_signals(self, qapp):
        from doremi.ui.viewmodels.notification_vm import NotificationViewModel

        vm = NotificationViewModel(qapp)
        vm.set_releases([{
            "video_id": "r1", "title": "Nuevo single", "artist": "Artistas",
            "artist_id": "UCx", "thumbnail_url": "", "time": "hace 2 h", "kind": "release",
        }])
        assert vm.hasReleases is True

        songs: list[tuple] = []
        artists: list[tuple] = []
        vm.song_clicked.connect(lambda *a: songs.append(a))
        vm.artist_clicked.connect(lambda *a: artists.append(a))
        vm.play_release("r1", "Nuevo single", "Artistas", "")
        vm.open_artist("Artistas", "UCx")
        assert songs == [("r1", "Nuevo single", "Artistas", "")]
        assert artists == [("Artistas", "UCx")]


class TestNotificationPanelQml:
    def test_qml_loads_and_hidden_by_default(self, qapp):
        from doremi.ui.widgets.notification_panel_qml import NotificationPanelQml

        panel = NotificationPanelQml(None)
        assert panel.is_ok
        assert panel.maximumWidth() == 0

    def test_unread_badge_flow(self, qapp):
        from doremi.ui.widgets.notification_panel_qml import NotificationPanelQml

        panel = NotificationPanelQml(None)
        unread: list[bool] = []
        panel.unread_changed.connect(unread.append)
        panel.add_custom_notification("X", "info")
        assert unread == [True]
        assert panel.has_unread is True

    def test_song_and_artist_signals(self, qapp):
        from doremi.ui.widgets.notification_panel_qml import NotificationPanelQml

        panel = NotificationPanelQml(None)
        songs: list[tuple] = []
        artists: list[tuple] = []
        panel.song_clicked.connect(lambda *a: songs.append(a))
        panel.artist_clicked.connect(lambda *a: artists.append(a))
        panel._vm.play_release("v", "t", "a", "th")
        panel._vm.open_artist("a", "id1")
        assert songs == [("v", "t", "a", "th")]
        assert artists == [("a", "id1")]

    def test_toggle_and_close_anim_methods_exist(self, qapp):
        from doremi.ui.widgets.notification_panel_qml import NotificationPanelQml

        panel = NotificationPanelQml(None)
        assert callable(panel.toggle_panel)
        assert callable(panel._close_anim)
        assert callable(panel.load_db_notifications)

    def test_load_db_notifications_schedules_existing_coro(self, qapp, monkeypatch):
        """Regresión: load_db_notifications programaba un método inexistente
        (_load_db_notifications_async) y lanzaba AttributeError al abrir el panel."""
        import asyncio

        from doremi.ui.widgets.notification_panel_qml import NotificationPanelQml

        panel = NotificationPanelQml(None)
        scheduled: list = []
        monkeypatch.setattr(asyncio, "ensure_future", lambda coro: scheduled.append(coro))
        panel.load_db_notifications()
        assert len(scheduled) == 1
        scheduled[0].close()  # la corutina nunca se ejecuta: cerrarla limpio

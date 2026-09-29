"""Reglas de arquitectura para la retirada gradual de QtWidgets."""
import os
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


def test_main_window_has_no_legacy_screen_fallbacks():
    source = Path("src/doremi/ui/main_window.py").read_text(encoding="utf-8")

    # QML no puede ser opcional por ruta: una pantalla rota debe fallar de forma
    # visible para corregirla, no reconstruirse con una interfaz diferente.
    assert "DOREMI_QML_" not in source
    assert "def _qml_enabled" not in source

    legacy_screens = (
        ("home", "HomeScreen"), ("library", "LibraryScreen"),
        ("history", "HistoryScreen"), ("downloads", "DownloadsScreen"),
        ("settings", "SettingsScreen"), ("playlist", "PlaylistScreen"),
        ("album", "AlbumScreen"), ("artist", "ArtistScreen"),
        ("now_playing", "NowPlayingScreen"), ("search", "SearchScreen"),
        ("stats", "StatsScreen"),
    )
    for module, screen in legacy_screens:
        assert f"from doremi.ui.screens.{module} import {screen}" not in source

    assert "MiniPlayerWidget" not in source
    assert "NotificationPanel(self)" not in source
    assert "NavSidebar(" not in source
    assert "NavSidebarQml" in source
    assert "GlobalSearchBarQml" in source
    assert "OfflineStateQml" in source
    assert "ErrorStateWidget" not in source
    assert "global_search import" not in source
    assert "QMessageBox" not in source
    assert "_require_qml" in source


def test_navigation_sidebar_is_a_theme_bound_qml_surface():
    source = Path("src/doremi/ui/qml/Doremi/NavigationSidebar.qml").read_text(encoding="utf-8")

    assert "themeBridge.colors" in source
    assert "NavigationItem" in source
    assert "navigationController.navigate(route)" in source
    assert "#" not in source

    for icon, label in (
        ("home", "Inicio"),
        ("library_music", "Biblioteca"),
        ("history", "Historial"),
        ("bar_chart", "Estadísticas"),
        ("download", "Descargas"),
        ("settings", "Ajustes"),
    ):
        assert icon in source
        assert label in source

    assert "ToolTip.visible" in source
    # Playlist shortcuts must match their full route (including the id), not
    # merely the generic route name shared by every playlist.
    assert "navigationController.activePath === route" in source

    presenter = Path("src/doremi/ui/widgets/nav_sidebar_qml.py").read_text(encoding="utf-8")
    assert '"Doremi.png"' in presenter


def test_offline_banner_is_a_theme_bound_qml_surface():
    source = Path("src/doremi/ui/qml/Doremi/OfflineBanner.qml").read_text(encoding="utf-8")

    assert "themeBridge.colors" in source
    assert "offlineController.shown" in source
    assert "#" not in source


def test_qml_surfaces_do_not_need_imperative_theme_refreshes():
    source = Path("src/doremi/ui/theme_manager.py").read_text(encoding="utf-8")

    assert '("sidebar", "_update_sidebar_styles")' not in source
    assert '("offline_banner", "_apply_style")' not in source


def test_qml_uses_theme_tokens_instead_of_embedded_color_palettes():
    """Todas las superficies QML activas comparten el tema dinámico."""
    qml_dir = Path("src/doremi/ui/qml")
    for source in qml_dir.rglob("*.qml"):
        content = source.read_text(encoding="utf-8")
        assert "#" not in content, source
        assert "Qt.rgba(0, 0, 0" not in content, source
        assert "Qt.rgba(1, 1, 1" not in content, source


def test_transient_notifications_are_rendered_by_qml():
    source = Path("src/doremi/ui/widgets/toast.py").read_text(encoding="utf-8")
    qml = Path("src/doremi/ui/qml/Toast.qml").read_text(encoding="utf-8")

    assert "QQuickWidget" in source
    assert "themeBridge.colors" in qml
    assert "#" not in qml


def test_global_header_is_a_theme_bound_qml_surface():
    source = Path("src/doremi/ui/widgets/global_search_qml.py").read_text(encoding="utf-8")
    header = Path("src/doremi/ui/qml/HeaderBar.qml").read_text(encoding="utf-8")
    suggestions = Path("src/doremi/ui/qml/SearchSuggestions.qml").read_text(encoding="utf-8")

    assert "class GlobalSearchBarQml(QObject)" in source
    assert "QQuickWidget" not in source
    assert "SearchHistory" in source
    assert "themeBridge.colors" in header
    assert "themeBridge.colors" in suggestions
    assert "#" not in header
    assert "#" not in suggestions
    assert not Path("src/doremi/ui/widgets/global_search.py").exists()


def test_offline_state_is_a_theme_bound_qml_surface():
    source = Path("src/doremi/ui/widgets/offline_state_qml.py").read_text(encoding="utf-8")
    qml = Path("src/doremi/ui/qml/OfflineState.qml").read_text(encoding="utf-8")

    assert "class OfflineStateQml(QObject)" in source
    assert "QQuickWidget" not in source
    assert "themeBridge.colors" in qml
    assert "screenVm.retry()" in qml
    assert "#" not in qml


def test_qml_history_does_not_import_the_widget_screen_for_data():
    source = Path("src/doremi/ui/screens/history_qml.py").read_text(encoding="utf-8")
    data_source = Path("src/doremi/ui/screens/history_data.py").read_text(encoding="utf-8")

    assert "from doremi.ui.screens.history import gather_history" not in source
    assert "from doremi.ui.screens.history_data import gather_history" in source
    assert "PySide6" not in data_source


def test_primary_qml_screens_do_not_wrap_quick_widgets_in_qwidgets():
    for screen in (
        "home", "library", "history", "downloads", "settings",
        "playlist", "album", "artist", "search", "stats", "now_playing",
    ):
        source = Path(f"src/doremi/ui/screens/{screen}_qml.py").read_text(encoding="utf-8")
        assert "QVBoxLayout(self)" not in source
        assert "QQuickWidget(self)" not in source

    notifications = Path("src/doremi/ui/widgets/notification_panel_qml.py").read_text(encoding="utf-8")
    assert "QVBoxLayout(self)" not in notifications
    assert "QQuickWidget(self)" not in notifications


def test_qml_screen_host_can_replace_the_widget_stack():
    source = Path("src/doremi/ui/qml/ScreenHost.qml").read_text(encoding="utf-8")

    assert "Loader" in source
    assert "screenVm" in source
    assert "fadeIn" in source
    assert "QStackedWidget" not in source

    router = Path("src/doremi/ui/widgets/screen_host_qml.py").read_text(encoding="utf-8")
    assert "QmlRouteStack" in router
    assert "show_screen" in router


def test_screen_host_delivers_source_and_viewmodel_atomically():
    source = Path("src/doremi/ui/qml/ScreenHost.qml").read_text(encoding="utf-8")

    # Separate root properties cross-wired a newly selected VM into the old
    # route for an event-loop turn. The host now accepts both values in one
    # call and uses the VM as an initial property of the Loader item.
    assert "function showScreen(source, vm)" in source
    assert 'screenLoader.setSource(source, { "screenVm": vm })' in source
    assert "onScreenVmChanged" not in source


def test_screen_host_never_cross_wires_adjacent_route_viewmodels(qapp):
    """Home → Now Playing used to hand HomeViewModel to the video route.

    QML reacts synchronously to each property change, so setting source and VM
    as separate Python properties is not atomic even when calls are adjacent.
    """
    from PySide6.QtCore import QCoreApplication, QEvent, QObject, QUrl
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    from doremi.ui.theme_bridge import theme_bridge
    from doremi.ui.viewmodels.home_vm import HomeViewModel
    from doremi.ui.viewmodels.now_playing_vm import NowPlayingViewModel

    qml_dir = Path("src/doremi/ui/qml").resolve()
    engine = QQmlEngine()
    engine.addImportPath(str(qml_dir))
    engine.rootContext().setContextProperty("themeBridge", theme_bridge())
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(qml_dir / "ScreenHost.qml")))
    host = component.create()
    assert host is not None, [error.toString() for error in component.errors()]
    loader = host.findChild(QObject, "screenLoader")
    assert loader is not None

    home_vm = HomeViewModel(qapp)
    now_vm = NowPlayingViewModel(qapp)
    host.showScreen(QUrl.fromLocalFile(str(qml_dir / "HomeScreen.qml")), home_vm)
    qapp.processEvents()
    assert loader.property("item").property("screenVm") is home_vm

    host.showScreen(QUrl.fromLocalFile(str(qml_dir / "NowPlayingScreen.qml")), now_vm)
    qapp.processEvents()
    assert loader.property("item").property("screenVm") is now_vm
    host.showScreen(QUrl.fromLocalFile(str(qml_dir / "HomeScreen.qml")), home_vm)
    qapp.processEvents()
    assert loader.property("item").property("screenVm") is home_vm

    host.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    engine.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def test_now_playing_uses_valid_accessible_tab_role_and_robust_lyric_updates():
    source = Path("src/doremi/ui/qml/NowPlayingScreen.qml").read_text(encoding="utf-8")

    assert "Accessible.PageTab" in source
    assert "onLyricIndexChanged" not in source
    assert "Timer {" in source
    assert "Accessible.Tab" not in source


def test_main_shell_composes_the_qml_application_frame():
    source = Path("src/doremi/ui/qml/MainShell.qml").read_text(encoding="utf-8")

    for component in (
        "NavigationSidebar", "HeaderBar", "OfflineBanner", "ScreenHost",
        "NotificationPanel", "MiniPlayer", "ModalDialog",
    ):
        assert component in source
    assert "FadeStackedWidget" not in source
    assert "closeConfirmationVisible" in source
    assert "readonly property bool shouldShow" in source
    assert "Behavior on opacity" in source
    assert "Behavior on y" in source


def test_update_dialog_is_a_theme_bound_qml_overlay():
    source = Path("src/doremi/ui/widgets/update_dialog_qml.py").read_text(encoding="utf-8")
    qml = Path("src/doremi/ui/qml/UpdateDialog.qml").read_text(encoding="utf-8")

    assert "QQuickWidget" in source
    assert "QDialog" not in source
    assert "themeBridge.colors" in qml
    assert "#" not in qml
    assert not Path("src/doremi/ui/widgets/update_dialog.py").exists()


def test_settings_logout_confirmation_is_qml_backed():
    source = Path("src/doremi/ui/screens/settings_qml.py").read_text(encoding="utf-8")
    qml = Path("src/doremi/ui/qml/SettingsScreen.qml").read_text(encoding="utf-8")
    vm = Path("src/doremi/ui/viewmodels/settings_vm.py").read_text(encoding="utf-8")

    assert "QMessageBox" not in source
    assert "ModalDialog" in qml
    assert "screenVm.confirm_logout()" in qml
    assert "logout_confirmation_requested" in vm
    assert "screenVm.confirm_clear_downloads()" in qml
    assert "download_clear_confirmation_requested" in vm
    assert "logoutConfirmationPending" in qml
    assert "downloadClearConfirmationPending" in qml
    assert "onLogoutConfirmationRequested" not in qml
    assert "onDownloadClearConfirmationRequested" not in qml

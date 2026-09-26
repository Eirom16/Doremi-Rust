"""Reglas de arquitectura para la retirada gradual de QtWidgets."""
from pathlib import Path


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
    assert 'navigationController.activeRoute === "playlist"' in source


def test_offline_banner_is_a_theme_bound_qml_surface():
    source = Path("src/doremi/ui/qml/Doremi/OfflineBanner.qml").read_text(encoding="utf-8")

    assert "themeBridge.colors" in source
    assert "offlineController.shown" in source
    assert "#" not in source


def test_qml_surfaces_do_not_need_imperative_theme_refreshes():
    source = Path("src/doremi/ui/theme_manager.py").read_text(encoding="utf-8")

    assert '("sidebar", "_update_sidebar_styles")' not in source
    assert '("offline_banner", "_apply_style")' not in source


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


def test_main_shell_composes_the_qml_application_frame():
    source = Path("src/doremi/ui/qml/MainShell.qml").read_text(encoding="utf-8")

    for component in (
        "NavigationSidebar", "HeaderBar", "OfflineBanner", "ScreenHost",
        "NotificationPanel", "MiniPlayer",
    ):
        assert component in source
    assert "FadeStackedWidget" not in source


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

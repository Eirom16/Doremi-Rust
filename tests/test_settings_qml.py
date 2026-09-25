"""Tests de la isla QML — Ajustes."""
from __future__ import annotations

import pytest

from doremi.config.settings import AppSettings


@pytest.fixture(scope="module")
def qapp():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


class TestSettingsViewModel:
    def test_categories(self, qapp):
        from doremi.ui.viewmodels.settings_vm import SettingsViewModel

        vm = SettingsViewModel(AppSettings(), None, qapp)
        keys = [c["key"] for c in vm.categories]
        assert keys == ["appearance", "player", "equalizer", "subtitles",
                        "accounts", "storage", "about"]
        assert vm.currentTitle == "Apariencia"

    def test_navigate_rebuilds_rows(self, qapp):
        from doremi.ui.viewmodels.settings_vm import SettingsViewModel

        vm = SettingsViewModel(AppSettings(), None, qapp)
        n_appearance = vm.rows.rowCount()
        vm.set_category(1)  # player
        assert vm.currentTitle == "Reproductor"
        assert vm.rows.rowCount() > 0
        assert vm.rows.rowCount() != n_appearance

        # ids de la página player
        ids = [vm.rows.data(vm.rows.index(i, 0), vm.rows.RowIdRole)
               for i in range(vm.rows.rowCount())]
        assert "player.volume" in ids
        assert "appearance.compact_sidebar" not in ids

    def test_set_value_generic_paths(self, qapp):
        from doremi.ui.viewmodels.settings_vm import SettingsViewModel

        settings = AppSettings()
        vm = SettingsViewModel(settings, None, qapp)
        fired: list[str] = []
        vm.settings_changed.connect(lambda: fired.append("x"))

        vm.set_value("appearance.compact_sidebar", True)
        vm.set_value("player.volume", 95)
        vm.set_value("player.sleep_timer_minutes", "30")
        vm.set_value("subtitles.line_spacing", 2.5)

        assert settings.appearance.compact_sidebar is True
        assert settings.player.volume == 95
        assert settings.player.sleep_timer_minutes == 30  # coerción a int
        assert settings.subtitles.line_spacing == 2.5
        assert len(fired) == 4

    def test_crossfade_toggle_rebuilds_rows(self, qapp):
        from doremi.ui.viewmodels.settings_vm import SettingsViewModel

        vm = SettingsViewModel(AppSettings(), None, qapp)
        vm.set_category(1)  # player
        vm.set_value("player.crossfade_enabled", False)
        # la fila crossfade_duration_sec debe quedar deshabilitada tras rebuild
        for i in range(vm.rows.rowCount()):
            rid = vm.rows.data(vm.rows.index(i, 0), vm.rows.RowIdRole)
            if rid == "player.crossfade_duration_sec":
                assert vm.rows.data(vm.rows.index(i, 0), vm.rows.EnabledRole) is False
                break
        else:
            raise AssertionError("fila crossfade_duration_sec no encontrada")

    def test_eq_preset_and_bands(self, qapp):
        from doremi.ui.viewmodels.settings_vm import SettingsViewModel

        settings = AppSettings()
        vm = SettingsViewModel(settings, None, qapp)
        vm.set_value("equalizer.preset_name", "Bass Boost")
        assert settings.equalizer.preset_name == "Bass Boost"
        assert settings.equalizer.bands == vm.eqBands

        vm.set_eq_band(0, 12.0)  # clamp al máximo conceptual lo hace el caller
        assert settings.equalizer.bands[0] == 12.0

    def test_eq_reset_action(self, qapp):
        from doremi.ui.viewmodels.settings_vm import SettingsViewModel

        settings = AppSettings()
        vm = SettingsViewModel(settings, None, qapp)
        vm.set_eq_band(5, 9.0)
        vm.action("equalizer.reset")
        assert settings.equalizer.preset_name == "Flat"
        assert all(b == 0.0 for b in settings.equalizer.bands)

    def test_accounts_rows_depend_on_auth(self, qapp):
        from doremi.ui.viewmodels.settings_vm import SettingsViewModel

        vm = SettingsViewModel(AppSettings(), None, qapp)
        vm.set_category(4)  # accounts
        ids = [vm.rows.data(vm.rows.index(i, 0), vm.rows.RowIdRole)
               for i in range(vm.rows.rowCount())]
        assert "accounts.login" in ids

        class _FakeYt:
            is_authenticated = True

        vm._yt = _FakeYt()
        vm.refresh()
        ids = [vm.rows.data(vm.rows.index(i, 0), vm.rows.RowIdRole)
               for i in range(vm.rows.rowCount())]
        assert "accounts.logout" in ids

    def test_storage_rows_have_metrics(self, qapp):
        from doremi.ui.viewmodels.settings_vm import SettingsViewModel

        vm = SettingsViewModel(AppSettings(), None, qapp)
        vm.set_category(5)  # storage
        ids = [vm.rows.data(vm.rows.index(i, 0), vm.rows.RowIdRole)
               for i in range(vm.rows.rowCount())]
        assert "storage.clear_cache" in ids
        assert "storage.export_backup" in ids

    def test_buttons_emit_action_requested(self, qapp):
        from doremi.ui.viewmodels.settings_vm import SettingsViewModel

        vm = SettingsViewModel(AppSettings(), None, qapp)
        acts: list[str] = []
        vm.action_requested.connect(acts.append)
        vm.action("accounts.login")
        vm.action("storage.clear_cache")
        assert acts == ["accounts.login", "storage.clear_cache"]

    def test_logout_requires_a_separate_confirmation(self, qapp):
        from doremi.ui.viewmodels.settings_vm import SettingsViewModel

        vm = SettingsViewModel(AppSettings(), None, qapp)
        requested: list[bool] = []
        confirmed: list[bool] = []
        actions: list[str] = []
        vm.logout_confirmation_requested.connect(lambda: requested.append(True))
        vm.logout_confirmed.connect(lambda: confirmed.append(True))
        vm.action_requested.connect(actions.append)

        vm.action("accounts.logout")
        assert requested == [True]
        assert confirmed == []
        assert actions == []

        vm.confirm_logout()
        assert confirmed == [True]


class TestSettingsScreenQml:
    def test_qml_loads(self, qapp):
        from doremi.ui.screens.settings_qml import SettingsScreenQml

        screen = SettingsScreenQml(None, AppSettings(), lambda s: None, lambda *a: None)
        assert screen.is_ok
        assert screen._qml_island is True

    def test_settings_changed_reaches_callback(self, qapp):
        from doremi.ui.screens.settings_qml import SettingsScreenQml

        hits: list[bool] = []
        screen = SettingsScreenQml(None, AppSettings(), lambda s: hits.append(True), lambda *a: None)
        screen._vm.set_value("appearance.compact_sidebar", True)
        assert hits == [True]

    def test_yt_setter_propagates(self, qapp):
        from doremi.ui.screens.settings_qml import SettingsScreenQml

        screen = SettingsScreenQml(None, AppSettings(), lambda s: None, lambda *a: None)

        class _FakeYt:
            is_authenticated = True

        screen.yt = _FakeYt()
        assert screen.yt is not None
        assert screen._vm._yt is not None

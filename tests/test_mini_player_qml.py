"""Tests del view-model del mini-player (isla QML)."""
from __future__ import annotations

import pytest


@pytest.fixture(scope="module")
def qapp():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


class TestMiniPlayerViewModel:
    def test_property_roundtrip(self, qapp):
        from doremi.ui.viewmodels.mini_player_vm import MiniPlayerViewModel

        vm = MiniPlayerViewModel(qapp)
        vm.set_title("Billie Jean")
        vm.set_artist("Michael Jackson")
        vm.set_playing(True)
        vm.set_loading(False)
        vm.set_progress(0.5)
        vm.set_position_text("2:27")
        vm.set_duration_text("4:54")
        vm.set_expand_less(False)

        assert vm.title == "Billie Jean"
        assert vm.artist == "Michael Jackson"
        assert vm.playing is True
        assert vm.progress == 0.5
        assert vm.positionText == "2:27"
        assert vm.durationText == "4:54"
        assert vm.expandLess is False

    def test_intent_signals(self, qapp):
        from doremi.ui.viewmodels.mini_player_vm import MiniPlayerViewModel

        vm = MiniPlayerViewModel(qapp)
        fired: list = []
        vm.prev_requested.connect(lambda: fired.append("prev"))
        vm.play_pause_requested.connect(lambda: fired.append("play_pause"))
        vm.next_requested.connect(lambda: fired.append("next"))
        vm.expand_requested.connect(lambda: fired.append("expand"))
        vm.artist_clicked.connect(lambda a: fired.append(("artist", a)))
        vm.seek_fraction.connect(lambda f: fired.append(("seek", f)))

        vm.emit_prev()
        vm.emit_play_pause()
        vm.emit_next()
        vm.emit_expand()
        vm.emit_artist_clicked("MJ")
        vm.emit_artist_clicked("")          # vacío: no emite
        vm.emit_seek(0.25)
        vm.emit_seek(1.5)                   # fuera de rango: clamp a 1.0

        assert fired == [
            "prev", "play_pause", "next", "expand",
            ("artist", "MJ"), ("seek", 0.25), ("seek", 1.0),
        ]

    def test_emit_methods_are_qml_visible_slots(self, qapp):
        """Regresión: sin @Slot, QML no puede llamar emit_* (TypeError:
        'Property ... is not a function'). Deben estar en el meta-object."""
        from doremi.ui.viewmodels.mini_player_vm import MiniPlayerViewModel

        vm = MiniPlayerViewModel(qapp)
        meta = vm.metaObject()
        for signature in (
            "emit_prev()",
            "emit_play_pause()",
            "emit_next()",
            "emit_seek(double)",
            "emit_expand()",
            "emit_artist_clicked(QString)",
        ):
            assert meta.indexOfMethod(signature) >= 0, signature


class TestExpandButtonShim:
    def test_glyph_translation(self, qapp):
        from doremi.ui.viewmodels.mini_player_vm import MiniPlayerViewModel
        from doremi.ui.widgets.mini_player_qml import _ExpandButtonShim
        from doremi.ui.design.icons import Icon

        vm = MiniPlayerViewModel(qapp)
        shim = _ExpandButtonShim(vm)
        shim.setText(Icon.get("expand_less"))
        assert vm.expandLess is True
        shim.setText(Icon.get("expand_more"))
        assert vm.expandLess is False

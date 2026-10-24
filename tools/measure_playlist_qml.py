#!/usr/bin/env python3
"""Cold offscreen playlist renderer measurement, never using app config/DB.

Usage: python tools/measure_playlist_qml.py REPOSITORY_ROOT ROW_COUNT
Run in separate processes for before/after comparisons. Delegates are counted
by their existing setVideoId role, so this also measures the old Repeater.
"""
import json
import os
from pathlib import Path
import sys
import tempfile
import time


def main():
    repository, count = Path(sys.argv[1]).resolve(), int(sys.argv[2])
    sys.dont_write_bytecode = True
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    os.environ['QT_QUICK_BACKEND'] = 'software'
    with tempfile.TemporaryDirectory(prefix='doremi-qml-perf-') as temporary:
        for kind in ('CONFIG', 'CACHE', 'DATA'):
            os.environ['XDG_'+kind+'_HOME'] = str(Path(temporary)/kind.lower())
        sys.path.insert(0, str(repository/'src'))
        from PySide6.QtWidgets import QApplication
        from PySide6.QtQuickWidgets import QQuickWidget
        from PySide6.QtCore import QUrl, qVersion
        from doremi.ui.design.fonts import load_fonts
        from doremi.ui.viewmodels.playlist_vm import PlaylistViewModel
        from doremi.ui.theme_bridge import ThemeBridge
        app = QApplication([])
        load_fonts()
        vm = PlaylistViewModel(app)
        vm.set_data(dict(playlist_id='local-list:perf', title='Synthetic performance fixture',
            tracks=[dict(videoId=str(i), title=str(i), artist='Fixture', duration='1:00', duration_ms=60000,
                         thumbnail_url='', is_downloaded=False, setVideoId='') for i in range(count)],
            limit=1000, offset=0, has_more=False))
        vm.set_loading(False)
        def rss():
            p = Path('/proc/self/statm')
            return int(p.read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')//1024 if p.exists() else None
        before = rss()
        started = time.perf_counter()
        bridge = ThemeBridge(app)
        widget = QQuickWidget()
        widget.resize(1000,720)
        widget.setResizeMode(QQuickWidget.SizeRootObjectToView)
        widget.engine().addImportPath(str(repository/'src/doremi/ui/qml'))
        widget.rootContext().setContextProperty('themeBridge',bridge)
        widget.setInitialProperties({'screenVm':vm})
        widget.setSource(QUrl.fromLocalFile(str(repository/'src/doremi/ui/qml/PlaylistScreen.qml')))
        widget.show()
        for _ in range(10): app.processEvents()
        def delegates(item):
            return int(item.metaObject().indexOfProperty('setVideoId') >= 0) + sum(delegates(c) for c in item.childItems())
        after = rss()
        result = dict(count=count, qt=qVersion(), python=sys.version.split()[0], status=str(widget.status()),
            rows=delegates(widget.rootObject()) if widget.rootObject() else -1,
            elapsed_ms=round((time.perf_counter()-started)*1000,2),
            rss_delta_kib=after-before if before is not None and after is not None else None,
            errors=[e.toString() for e in widget.errors()])
        print(json.dumps(result))
        widget.setSource(QUrl()); widget.close()
        return 0 if result['status']=='Status.Ready' and not result['errors'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

from __future__ import annotations

from pathlib import Path
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget, QFileDialog
from doremi.config.paths import AppDirs
from doremi.ui.screens.settings.components import SettingsRow, SettingsSection, page_title
from doremi.ui.widgets.ripple_button import RippleButton
from doremi.utils.i18n import _


class StorageSettingsScreen(QWidget):
    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(page_title(_("Almacenamiento")))

        usage = SettingsSection(_("Uso"))
        usage.add_row(SettingsRow(_("Base de datos"), _("Historial y biblioteca local"), self._metric(AppDirs.database)))
        usage.add_row(SettingsRow(_("Cache"), _("Imagenes y datos temporales"), self._metric(AppDirs.cache)))
        usage.add_row(SettingsRow(_("Descargas"), _("Canciones guardadas offline"), self._metric(AppDirs.downloads)))
        layout.addWidget(usage)

        actions = SettingsSection(_("Limpieza"))
        clear_cache = RippleButton(_("Limpiar cache"), "secondary")
        clear_cache.clicked.connect(self._clear_cache)
        actions.add_row(SettingsRow(_("Cache"), _("Elimina archivos temporales"), clear_cache))
        clear_downloads = RippleButton(_("Eliminar descargas"), "danger")
        clear_downloads.clicked.connect(self._clear_downloads)
        actions.add_row(SettingsRow(_("Descargas"), _("Elimina los archivos descargados"), clear_downloads))
        layout.addWidget(actions)

        # Nueva sección: Copias de seguridad
        backups = SettingsSection(_("Copia de seguridad"))
        
        btn_export = RippleButton(_("Exportar copia"), "primary")
        btn_export.clicked.connect(self._export_backup)
        backups.add_row(SettingsRow(_("Exportar"), _("Exporta tu biblioteca y configuraciones en un zip"), btn_export))
        
        btn_import = RippleButton(_("Restaurar copia"), "secondary")
        btn_import.clicked.connect(self._import_backup)
        backups.add_row(SettingsRow(_("Restaurar"), _("Restaura tu biblioteca y configuraciones desde un zip"), btn_import))
        
        layout.addWidget(backups)
        layout.addStretch()

    def _metric(self, path: Path) -> QLabel:
        from doremi.ui.design import tokens
        label = QLabel(self._get_size(path))
        label.setStyleSheet(f"color: {tokens.CURRENT.accent}; background: transparent; font-weight: 700;")
        if not hasattr(self, "_metric_labels"):
            self._metric_labels = []
        self._metric_labels.append(label)
        return label

    def _get_size(self, path: Path) -> str:
        if not path.exists():
            return "0 MB"
        total = sum(file.stat().st_size for file in path.rglob("*") if file.is_file())
        return f"{total / (1024 * 1024):.1f} MB"

    def _clear_cache(self) -> None:
        for file in AppDirs.cache.glob("*"):
            if file.is_file():
                file.unlink()
        from doremi.ui.widgets.toast import ToastNotification
        ToastNotification.show(self, _("Caché limpiada con éxito"), "success")

    def _clear_downloads(self) -> None:
        for file in AppDirs.downloads.glob("*"):
            if file.is_file():
                file.unlink()
        from doremi.ui.widgets.toast import ToastNotification
        ToastNotification.show(self, _("Descargas eliminadas con éxito"), "success")

    def _export_backup(self) -> None:
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            _("Exportar copia de seguridad"),
            str(Path.home() / "doremi_backup.zip"),
            "Zip Files (*.zip)"
        )
        if file_path:
            from doremi.utils.backup import BackupManager
            from doremi.ui.widgets.toast import ToastNotification
            
            success = BackupManager.export_backup(Path(file_path))
            if success:
                ToastNotification.show(self, _("Copia de seguridad exportada con éxito"), "success")
            else:
                ToastNotification.show(self, _("Error al exportar copia de seguridad"), "error")

    def _import_backup(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            _("Importar copia de seguridad"),
            str(Path.home()),
            "Zip Files (*.zip)"
        )
        if file_path:
            import asyncio
            from doremi.utils.backup import BackupManager
            from doremi.ui.widgets.toast import ToastNotification
            
            async def run_import():
                toast = ToastNotification.show(self, _("Restaurando copia de seguridad..."), "info")
                success = await BackupManager.import_backup_async(Path(file_path))
                if success:
                    ToastNotification.show(self, _("Copia de seguridad restaurada. Por favor reinicia la aplicación."), "success")
                else:
                    ToastNotification.show(self, _("Error al restaurar la copia de seguridad"), "error")
                    
            asyncio.create_task(run_import())

    def _update_metric_labels_style(self) -> None:
        if not hasattr(self, "_metric_labels"):
            return
        from doremi.ui.design import tokens
        for label in self._metric_labels:
            label.setStyleSheet(f"color: {tokens.CURRENT.accent}; background: transparent; font-weight: 700;")

    def changeEvent(self, event) -> None:
        from PySide6.QtCore import QEvent
        if event.type() in (QEvent.Type.PaletteChange,):
            if not getattr(self, '_in_style_change', False):
                self._in_style_change = True
                try:
                    self._update_metric_labels_style()
                finally:
                    self._in_style_change = False
        super().changeEvent(event)


from __future__ import annotations
import zipfile
import shutil
import tempfile
import stat
from pathlib import Path
from loguru import logger
from doremi.config.paths import AppDirs

class BackupManager:
    @staticmethod
    def export_backup(zip_path: Path) -> bool:
        """
        Creates a zip file backup containing the SQLite database and settings.toml.
        """
        try:
            zip_path = Path(zip_path).expanduser()
            zip_path.parent.mkdir(parents=True, exist_ok=True)
            # A unique staging directory avoids mixing artifacts from a failed
            # export with a later backup, and is removed on every exit path.
            with tempfile.TemporaryDirectory(prefix="doremi-backup-", dir=zip_path.parent) as temp_name:
                temp_dir = Path(temp_name)
                db_file = AppDirs.database
                if db_file.exists():
                    shutil.copy2(db_file, temp_dir / "doremi.db")

                settings_file = AppDirs.settings_file
                if settings_file.exists():
                    shutil.copy2(settings_file, temp_dir / "settings.toml")

                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                    for file_path in temp_dir.glob("*"):
                        zip_file.write(file_path, file_path.name)
            logger.info(f"Copia de seguridad exportada con éxito en: {zip_path}")
            return True
        except Exception as e:
            logger.error(f"Error al exportar copia de seguridad: {e}")
            return False

    @staticmethod
    async def import_backup_async(zip_path: Path) -> bool:
        """
        Restores SQLite database and settings.toml from a zip backup.
        """
        try:
            zip_path = Path(zip_path).expanduser()
            allowed = {"doremi.db", "settings.toml"}
            with tempfile.TemporaryDirectory(prefix="doremi-restore-", dir=zip_path.parent) as temp_name:
                temp_dir = Path(temp_name)
                with zipfile.ZipFile(zip_path, 'r') as zip_file:
                    members = zip_file.infolist()
                    names = [member.filename for member in members]
                    # Never use extractall for a user-selected archive.  A
                    # backup has a deliberately tiny, flat contract, so reject
                    # path traversal, duplicate names, symlinks and extras.
                    if (
                        not names
                        or len(names) != len(set(names))
                        or any(
                            name not in allowed
                            or stat.S_IFMT(member.external_attr >> 16) == stat.S_IFLNK
                            for name, member in zip(names, members)
                        )
                    ):
                        logger.error("Copia de seguridad inválida: contiene archivos no permitidos.")
                        return False
                    for member in members:
                        destination = temp_dir / member.filename
                        with zip_file.open(member, "r") as source, destination.open("wb") as target:
                            shutil.copyfileobj(source, target)

                restored_db = temp_dir / "doremi.db"
                restored_settings = temp_dir / "settings.toml"
                if not restored_db.exists() and not restored_settings.exists():
                    logger.error("Copia de seguridad inválida: faltan base de datos y ajustes.")
                    return False

                # Validation completed without mutating runtime resources.  We
                # only release connections once a real restore is ready.
                from doremi.db.database import get_engine
                engine = get_engine()
                if engine:
                    logger.info("Cerrando motor de base de datos para restauración de backup...")
                    await engine.dispose()

                def atomic_copy(source: Path, destination: Path) -> None:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    staged = destination.with_name(destination.name + ".restore.tmp")
                    shutil.copy2(source, staged)
                    staged.replace(destination)

                if restored_db.exists():
                    atomic_copy(restored_db, AppDirs.database)
                    logger.info("Base de datos restaurada con éxito.")
                if restored_settings.exists():
                    atomic_copy(restored_settings, AppDirs.settings_file)
                    logger.info("Ajustes de configuración restaurados con éxito.")
                return True
        except Exception as e:
            logger.error(f"Error al restaurar copia de seguridad: {e}")
            return False

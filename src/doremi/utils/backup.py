from __future__ import annotations
import zipfile
import shutil
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
            temp_dir = zip_path.parent / "_doremi_backup_temp"
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            # Copy database if exists
            db_file = AppDirs.database
            if db_file.exists():
                shutil.copy2(db_file, temp_dir / "doremi.db")
                
            # Copy settings if exists
            settings_file = AppDirs.settings_file
            if settings_file.exists():
                shutil.copy2(settings_file, temp_dir / "settings.toml")
                
            # Zip the temp dir contents
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for file_path in temp_dir.glob("*"):
                    zip_file.write(file_path, file_path.name)
                    
            # Cleanup temp dir
            shutil.rmtree(temp_dir)
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
            # 1. Close SQLAlchemy database engine to release file locks
            from doremi.db.database import get_engine
            engine = get_engine()
            if engine:
                logger.info("Cerrando motor de base de datos para restauración de backup...")
                await engine.dispose()
                
            temp_dir = zip_path.parent / "_doremi_restore_temp"
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            # Extract zip contents to temp directory
            with zipfile.ZipFile(zip_path, 'r') as zip_file:
                zip_file.extractall(temp_dir)
                
            # 2. Verify backup integrity
            restored_db = temp_dir / "doremi.db"
            restored_settings = temp_dir / "settings.toml"
            
            if not restored_db.exists() and not restored_settings.exists():
                logger.error("Copia de seguridad inválida: faltan base de datos y ajustes.")
                shutil.rmtree(temp_dir)
                return False
                
            # 3. Copy files to production paths
            if restored_db.exists():
                AppDirs.database.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(restored_db, AppDirs.database)
                logger.info("Base de datos restaurada con éxito.")
                
            if restored_settings.exists():
                AppDirs.settings_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(restored_settings, AppDirs.settings_file)
                logger.info("Ajustes de configuración restaurados con éxito.")
                
            # Cleanup temp dir
            shutil.rmtree(temp_dir)
            return True
        except Exception as e:
            logger.error(f"Error al restaurar copia de seguridad: {e}")
            return False

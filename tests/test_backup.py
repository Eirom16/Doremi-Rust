import pytest
from pathlib import Path

@pytest.mark.asyncio
async def test_backup_and_restore(tmp_path, monkeypatch):
    from doremi.utils.backup import BackupManager
    import doremi.utils.backup as backup_mod
    
    # Define temporary files representing our mock AppDirs database and settings
    mock_db = tmp_path / "doremi.db"
    mock_settings = tmp_path / "settings.toml"
    
    mock_db.write_text("dummy database content")
    mock_settings.write_text("dummy settings content")
    
    # Patch AppDirs properties dynamically
    class MockAppDirs:
        database = mock_db
        settings_file = mock_settings
        
    monkeypatch.setattr(backup_mod, "AppDirs", MockAppDirs)
    
    # Export backup zip
    backup_zip = tmp_path / "backup.zip"
    export_success = BackupManager.export_backup(backup_zip)
    assert export_success is True
    assert backup_zip.exists()
    
    # Now modify original files
    mock_db.write_text("different database")
    mock_settings.write_text("different settings")
    
    # Mock database engine dispose
    import unittest.mock
    mock_engine = unittest.mock.AsyncMock()
    monkeypatch.setattr("doremi.db.database.get_engine", lambda: mock_engine)
    
    # Restore from backup
    restore_success = await BackupManager.import_backup_async(backup_zip)
    assert restore_success is True
    
    # Check that original files have been restored to their dummy contents
    assert mock_db.read_text() == "dummy database content"
    assert mock_settings.read_text() == "dummy settings content"

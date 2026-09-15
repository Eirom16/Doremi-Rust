import json
import unittest.mock
import pytest
from pathlib import Path

@pytest.fixture
def mock_keyring(monkeypatch):
    """Fixture to mock keyring methods."""
    storage = {}
    
    def set_password(service, username, password):
        storage[(service, username)] = password

    def get_password(service, username):
        return storage.get((service, username))

    def delete_password(service, username):
        storage.pop((service, username), None)

    monkeypatch.setattr("keyring.set_password", set_password)
    monkeypatch.setattr("keyring.get_password", get_password)
    monkeypatch.setattr("keyring.delete_password", delete_password)
    return storage

def test_secure_storage_youtube_auth(mock_keyring):
    from doremi.utils.secure_storage import SecureStorage
    
    # Enable keyring functionality
    SecureStorage._is_functional = lambda: True
    
    headers = {"cookie": "test_cookie", "authorization": "SAPISIDHASH 1"}
    
    # Save headers
    saved = SecureStorage.save_youtube_headers(headers)
    assert saved is True
    
    # Read headers
    loaded = SecureStorage.load_youtube_headers()
    assert loaded == headers
    
    # Delete headers
    SecureStorage.delete_youtube_headers()
    loaded_after = SecureStorage.load_youtube_headers()
    assert loaded_after is None

def test_secure_storage_lastfm_auth(mock_keyring):
    from doremi.utils.secure_storage import SecureStorage
    
    # Enable keyring functionality
    SecureStorage._is_functional = lambda: True
    
    # Save credentials
    SecureStorage.save_lastfm_credentials("my_api_key", "my_api_secret", "my_session_key")
    
    # Load credentials
    api_key, api_secret, session_key = SecureStorage.load_lastfm_credentials()
    assert api_key == "my_api_key"
    assert api_secret == "my_api_secret"
    assert session_key == "my_session_key"
    
    # Delete credentials
    SecureStorage.delete_lastfm_credentials()
    api_key, api_secret, session_key = SecureStorage.load_lastfm_credentials()
    assert api_key == ""
    assert api_secret == ""
    assert session_key == ""

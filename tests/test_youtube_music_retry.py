from doremi.api.youtube_music import YouTubeMusicClient


def _client():
    return YouTubeMusicClient.__new__(YouTubeMusicClient)


def test_youtube_music_detects_retryable_status_codes():
    client = _client()

    class ResponseError(Exception):
        def __init__(self, status_code):
            super().__init__("request failed")
            self.response = type("Response", (), {"status_code": status_code})()

    assert client._is_retryable_error(ResponseError(429))
    assert client._is_retryable_error(ResponseError(503))
    assert not client._is_retryable_error(ResponseError(404))


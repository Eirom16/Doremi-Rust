from doremi.utils.time_utils import parse_duration_to_ms, format_duration, format_duration_short


def test_parse_none_returns_zero():
    assert parse_duration_to_ms(None) == 0
    assert parse_duration_to_ms("") == 0


def test_parse_int_seconds():
    assert parse_duration_to_ms(215) == 215000
    assert parse_duration_to_ms(295) == 295000


def test_parse_float_seconds():
    assert parse_duration_to_ms(215.5) == 215500


def test_parse_mmss_string():
    # 3:35 -> 215s
    assert parse_duration_to_ms("3:35") == 215000


def test_parse_hhmmss_string():
    # 1:03:35 -> 3815s
    assert parse_duration_to_ms("1:03:35") == 3815000


def test_parse_plain_numeric_string():
    assert parse_duration_to_ms("215") == 215000
    assert parse_duration_to_ms("215.0") == 215000


def test_parse_invalid_returns_zero():
    assert parse_duration_to_ms("abc") == 0
    assert parse_duration_to_ms("3:xx") == 0
    assert parse_duration_to_ms(object()) == 0


def test_real_world_billie_jean():
    # Billie Jean is ~294s; ensure no 10s regression
    assert parse_duration_to_ms(294) == 294000
    assert parse_duration_to_ms("4:54") == 294000


def test_format_duration_roundtrip():
    assert format_duration(294000) == "4:54"
    assert format_duration(3815000) == "1:03:35"
    assert format_duration_short(10000) == "0:10"
    assert format_duration_short(294000) == "4:54"

#!/usr/bin/env python3
"""Strict validation shared by the clean-container harness and its tests."""
import json
import sys

REQUIRED_CHECKS = frozenset({
    'qt_app', 'vlc', 'app_dirs', 'db_migrations', 'fonts', 'rust',
    'theme_bridge', 'qml_files', 'qml_shell',
})


def validate(path):
    with open(path, encoding='utf-8') as stream:
        result = json.load(stream)
    assert result.get('ok') is True, 'smoke ok must be true'
    assert result.get('frozen') is True, 'must execute the frozen AppImage'
    checks = result.get('checks')
    assert isinstance(checks, dict), 'missing checks'
    assert REQUIRED_CHECKS <= checks.keys(), f'missing mandatory checks: {REQUIRED_CHECKS - checks.keys()}'
    assert all(value is True for value in checks.values()), checks
    print(f"SMOKE_JSON_VALID: {len(checks)} checks; frozen=true; ok=true")
    return result


if __name__ == '__main__':
    try:
        validate(sys.argv[1])
    except (AssertionError, OSError, ValueError, TypeError, IndexError) as exc:
        print(f'SMOKE_JSON_INVALID: {exc}', file=sys.stderr)
        raise SystemExit(1)

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
    if not isinstance(result, dict) or result.get('ok') is not True:
        raise ValueError('smoke ok must be true')
    if result.get('frozen') is not True:
        raise ValueError('must execute the frozen AppImage')
    checks = result.get('checks')
    if not isinstance(checks, dict):
        raise ValueError('missing checks')
    if not REQUIRED_CHECKS <= checks.keys():
        raise ValueError(f'missing mandatory checks: {REQUIRED_CHECKS - checks.keys()}')
    if not all(value is True for value in checks.values()):
        raise ValueError(f'failed checks: {checks}')
    print(f"SMOKE_JSON_VALID: {len(checks)} checks; frozen=true; ok=true")
    return result


if __name__ == '__main__':
    try:
        validate(sys.argv[1])
    except (AssertionError, OSError, ValueError, TypeError, IndexError) as exc:
        print(f'SMOKE_JSON_INVALID: {exc}', file=sys.stderr)
        raise SystemExit(1)

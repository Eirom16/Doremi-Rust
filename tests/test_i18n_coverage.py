import ast
import json
from pathlib import Path


def _used_translation_keys(src_dir: Path) -> set[str]:
    keys: set[str] = set()
    for path in src_dir.rglob("*.py"):
        if "native_rs/target" in path.as_posix():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Name) or node.func.id != "_":
                continue
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                keys.add(node.args[0].value)
    return keys


def test_locale_files_cover_static_translation_keys():
    root = Path(__file__).resolve().parents[1]
    src_dir = root / "src" / "doremi"
    locale_dir = src_dir / "locales"
    used_keys = _used_translation_keys(src_dir)

    assert used_keys, "No static translation keys were detected"

    missing_by_locale: dict[str, list[str]] = {}
    for locale_path in sorted(locale_dir.glob("*.json")):
        translations = json.loads(locale_path.read_text(encoding="utf-8"))
        missing = sorted(used_keys - set(translations))
        if missing:
            missing_by_locale[locale_path.name] = missing

    assert missing_by_locale == {}

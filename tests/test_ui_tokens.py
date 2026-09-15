import ast
from pathlib import Path

from doremi.ui.design.tokens import ColorScheme


def test_current_token_references_exist():
    valid_fields = set(ColorScheme.__dataclass_fields__)
    missing = []

    for path in Path("src/doremi").rglob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Attribute):
                continue
            value = node.value
            if (
                isinstance(value, ast.Attribute)
                and value.attr == "CURRENT"
                and isinstance(value.value, ast.Name)
                and value.value.id == "tokens"
                and node.attr not in valid_fields
            ):
                missing.append(f"{path}:{node.lineno} tokens.CURRENT.{node.attr}")

    assert missing == []

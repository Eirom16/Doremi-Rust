#!/usr/bin/env python3
"""Stamp packaging/windows/installer.iss with the version from pyproject.toml.

Reads ``[project].version`` and rewrites in place:
  AppVersion=<ver>
  AppVerName=Doremi v<ver>
  VersionInfoVersion=<ver>.0  (pads to 4 numeric parts)
  OutputBaseFilename=Doremi-v<ver>-Setup

Fails loudly if installer.iss still contains VERSION_PLACEHOLDER or points
at the wrong GitHub repo. Idempotent.

Usage (from repo root):
    python packaging/windows/stamp_installer_version.py
    python packaging/windows/stamp_installer_version.py --check   # verify only
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
ISS = ROOT / "packaging" / "windows" / "installer.iss"
PYPROJECT = ROOT / "pyproject.toml"
EXPECTED_ARTIFACT_PREFIX = "Doremi-v"
WRONG_REPO = "github.com/Eirom16/doremi"


def read_version() -> str:
    with open(PYPROJECT, "rb") as f:
        ver = tomllib.load(f)["project"]["version"]
    if not re.fullmatch(r"\d+\.\d+\.\d+", ver):
        raise SystemExit(f"unexpected version format in pyproject.toml: {ver!r}")
    return ver


def version_info_version(ver: str) -> str:
    parts = [int(p) for p in ver.split(".")]
    while len(parts) < 4:
        parts.append(0)
    return ".".join(str(p) for p in parts[:4])


def check(text: str) -> list[str]:
    problems: list[str] = []
    # Only non-comment lines count (Inno comments start with ';').
    code = "\n".join(
        ln for ln in text.splitlines() if not ln.lstrip().startswith(";")
    )
    if "VERSION_PLACEHOLDER" in code:
        problems.append("installer.iss still contains VERSION_PLACEHOLDER")
    if WRONG_REPO in code:
        problems.append(f"installer.iss still references wrong repo ({WRONG_REPO})")
    if "[UninstallDelete]" in code:
        problems.append("installer.iss contains [UninstallDelete] (data-loss risk)")
    if "{localappdata}" in code.lower():
        problems.append("installer.iss references {localappdata} deletion")
    if "ArchitecturesInstallIn64BitMode=x64\n" in text or "ArchitecturesInstallIn64BitMode=x64\r" in text:
        problems.append("deprecated bare 'x64' arch identifier; use 'x64compatible'")
    if "{userstartmenu}" in text:
        problems.append("duplicate top-level {userstartmenu} shortcut present")
    return problems


def main() -> int:
    ver = read_version()
    text = ISS.read_text(encoding="utf-8")
    problems = check(text)
    if "--check" in sys.argv:
        if problems:
            for p in problems:
                print(f"FAIL: {p}")
            return 1
        # also verify stamped version matches pyproject
        m = re.search(r"^AppVersion=(.+)$", text, re.M)
        mv = m.group(1).strip() if m else None
        if mv != ver:
            print(f"FAIL: AppVersion={mv!r} != pyproject {ver!r}")
            return 1
        m2 = re.search(r"^OutputBaseFilename=(.+)$", text, re.M)
        expected = f"Doremi-v{ver}-Setup"
        if not m2 or m2.group(1).strip() != expected:
            print(f"FAIL: OutputBaseFilename={m2.group(1) if m2 else None!r} != {expected!r}")
            return 1
        print(f"OK: installer.iss stamped for {ver} ({expected}.exe)")
        return 0

    new = text
    new = re.sub(r"^AppVersion=.*$", f"AppVersion={ver}", new, flags=re.M)
    new = re.sub(r"^AppVerName=.*$", f"Doremi v{ver}", new, flags=re.M)
    # If AppVerName line is missing (legacy file), insert after AppVersion.
    if "AppVerName=" not in new:
        new = re.sub(
            r"^(AppVersion=.*)$",
            f"\\1\nAppVerName=Doremi v{ver}",
            new,
            flags=re.M,
        )
    new = re.sub(
        r"^VersionInfoVersion=.*$",
        f"VersionInfoVersion={version_info_version(ver)}",
        new,
        flags=re.M,
    )
    new = re.sub(
        r"^OutputBaseFilename=.*$",
        f"OutputBaseFilename=Doremi-v{ver}-Setup",
        new,
        flags=re.M,
    )
    if new != text:
        ISS.write_text(new, encoding="utf-8")
        print(f"stamped installer.iss -> {ver} (Doremi-v{ver}-Setup.exe)")
    else:
        print(f"installer.iss already stamped for {ver}")
    problems = check(new)
    if problems:
        for p in problems:
            print(f"FAIL: {p}")
        return 1
    print("OK: no placeholders, correct repo, no UninstallDelete, x64compatible")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

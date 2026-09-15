# src/doremi/utils/updater.py
"""
Sistema de actualizaciones de Doremi.
Consulta la API de GitHub Releases, compara versiones,
descarga el paquete correcto para la plataforma actual
y notifica al usuario con una barra de progreso.
"""
from __future__ import annotations

import asyncio
import os
import platform
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
import httpx
from loguru import logger

# ── Constantes ────────────────────────────────────────────────────────────────
try:
    from doremi import __version__
except Exception:
    __version__ = "0.0.0"

CURRENT_VERSION = f"v{__version__}"
GITHUB_API_URL  = (
    "https://api.github.com/repos/Eirom16/doremi/releases/latest"
)
GITHUB_HEADERS  = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


def is_dev_build() -> bool:
    """
    Dev/commit builds are always the latest by definition, so the updater
    must never report an available update for them.

    A build is considered development when:
      - DOREMI_DEV env var is set, or
      - the current version carries a commit/dev suffix (e.g. "2.1.4-4-g1842402"
        produced by `git describe`), which only happens for source builds.
    Frozen release builds report a plain "X.Y.Z" stamped from the git tag.
    """
    if os.environ.get("DOREMI_DEV"):
        return True
    return "-" in CURRENT_VERSION


@dataclass
class ReleaseInfo:
    version: str           # ej. "v1.2.0"
    release_notes: str     # markdown con los cambios
    html_url: str          # URL de la página del release en GitHub
    assets: list[dict]     # lista de assets del release (archivos adjuntos)

    def get_asset_for_platform(self) -> dict | None:
        """
        Devuelve el asset correcto para la plataforma actual:
        - Windows x64  → Doremi-vX.Y.Z-Setup.exe
        - Linux x64    → doremi_X.Y.Z_amd64.deb  (si apt disponible)
                       → doremi-X.Y.Z-1.x86_64.rpm (si dnf/rpm disponible)
                       → doremi-X.Y.Z-1-x86_64.pkg.tar.zst (si pacman)
        """
        system = platform.system()

        if system == "Windows":
            suffix = "-Setup.exe"
            return next(
                (a for a in self.assets if a["name"].endswith(suffix)), None
            )

        if system == "Linux":
            pkg_mgr = _detect_package_manager()
            suffixes = {
                "pacman": ".pkg.tar.zst",
                "apt":    "_amd64.deb",
                "dnf":    ".x86_64.rpm",
                "zypper": ".x86_64.rpm",
                "emerge": ".x86_64.rpm",  # fallback
            }
            suffix = suffixes.get(pkg_mgr, ".pkg.tar.zst")
            return next(
                (a for a in self.assets if a["name"].endswith(suffix)), None
            )

        return None


def _detect_package_manager() -> str:
    """Detecta el gestor de paquetes del sistema."""
    managers = ["pacman", "apt", "dnf", "zypper", "emerge"]
    for mgr in managers:
        if shutil.which(mgr):
            return mgr
    return "unknown"


def _parse_version(tag: str) -> tuple[int, ...]:
    """Convierte 'v1.2.3' (o 'v1.2.3-4-gabc' de git describe) en (1, 2, 3)."""
    core = tag.lstrip("v").split("-")[0]
    return tuple(int(x) for x in core.split("."))


async def check_for_updates() -> ReleaseInfo | None:
    """
    Consulta la API de GitHub.
    Devuelve ReleaseInfo si hay una versión más nueva, None si no.
    No lanza excepciones — falla silenciosamente en caso de error de red.
    """
    if is_dev_build():
        logger.debug("Update check skipped: development/commit build")
        return None

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(GITHUB_API_URL, headers=GITHUB_HEADERS)
            r.raise_for_status()

        data = r.json()
        latest_tag = data.get("tag_name", "")

        if not latest_tag:
            return None

        # Comparar versiones numéricamente
        try:
            if _parse_version(latest_tag) <= _parse_version(CURRENT_VERSION):
                return None
        except (ValueError, AttributeError):
            return None

        return ReleaseInfo(
            version=latest_tag,
            release_notes=data.get("body", "Sin notas de versión."),
            html_url=data.get("html_url", ""),
            assets=data.get("assets", []),
        )

    except httpx.TimeoutException:
        logger.debug("Update check timed out")
    except httpx.HTTPStatusError as e:
        logger.debug(f"Update check HTTP error: {e.response.status_code}")
    except Exception as e:
        logger.debug(f"Update check failed: {e}")

    return None


async def download_update(
    asset: dict,
    progress_callback: Callable[[float, str], None] | None = None,
) -> Path | None:
    """
    Descarga el asset del release con barra de progreso.

    progress_callback(porcentaje: float, mensaje: str)
    Devuelve la ruta al archivo descargado en /tmp, o None si falla.
    """
    url  = asset["browser_download_url"]
    name = asset["name"]
    dest = Path(tempfile.gettempdir()) / name

    try:
        async with httpx.AsyncClient(
            timeout=None,   # sin timeout para descargas grandes
            follow_redirects=True,
        ) as client:
            async with client.stream("GET", url, headers=GITHUB_HEADERS) as r:
                r.raise_for_status()
                total = int(r.headers.get("content-length", 0))
                downloaded = 0

                with open(dest, "wb") as f:
                    async for chunk in r.aiter_bytes(chunk_size=65536):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total and progress_callback:
                            pct = downloaded / total * 100
                            mb_done  = downloaded / 1_048_576
                            mb_total = total / 1_048_576
                            await asyncio.sleep(0)   # ceder al event loop de Qt
                            progress_callback(
                                pct,
                                f"Descargando {mb_done:.1f} / {mb_total:.1f} MB"
                            )

        logger.info(f"Update downloaded to {dest}")
        return dest

    except Exception as e:
        logger.error(f"Download failed: {e}")
        if dest.exists():
            dest.unlink()
        return None


def install_update(package_path: Path) -> bool:
    """
    Instala el paquete descargado usando el gestor nativo (síncrono, pkexec/Windows).
    Devuelve True si el comando se lanzó correctamente.

    IMPORTANTE: en Linux requiere pkexec o sudo para elevar privilegios.
    La instalación se lanza en background — la app NO espera a que termine.
    En Windows ejecuta el instalador .exe directamente.
    """
    system = platform.system()
    path   = str(package_path)

    if system == "Windows":
        # Lanzar el instalador Inno Setup y cerrar la app
        subprocess.Popen([path, "/SILENT", "/NORESTART"])
        return True

    if system == "Linux":
        mgr = _detect_package_manager()

        # pkexec permite elevar sin abrir una terminal nueva
        install_cmds = {
            "pacman": ["pkexec", "pacman", "-U", "--noconfirm", path],
            "apt":    ["pkexec", "apt",    "install", "-y", path],
            "dnf":    ["pkexec", "dnf",    "install", "-y", path],
            "zypper": ["pkexec", "zypper", "install", "-y", path],
        }

        cmd = install_cmds.get(mgr)
        if not cmd:
            logger.warning(f"Unknown package manager: {mgr}")
            return False

        try:
            subprocess.Popen(cmd, start_new_session=True)
            return True
        except FileNotFoundError:
            # pkexec no disponible — intentar con sudo en terminal
            terminal_cmds = {
                "pacman": f"sudo pacman -U --noconfirm {path}",
                "apt":    f"sudo apt install -y {path}",
                "dnf":    f"sudo dnf install -y {path}",
                "zypper": f"sudo zypper install -y {path}",
            }
            cmd_str = terminal_cmds.get(mgr, "")
            if cmd_str:
                # Abrir en la terminal disponible
                for term in ["konsole", "gnome-terminal", "xterm", "alacritty"]:
                    if shutil.which(term):
                        subprocess.Popen([term, "-e", "bash", "-c",
                                         f"{cmd_str}; read -p 'Presiona Enter para cerrar'"],
                                         start_new_session=True)
                        return True
        return False

    return False


async def install_update_async(package_path: Path, password: str | None = None) -> bool:
    """
    Instala el paquete descargado de manera asíncrona usando el gestor nativo.
    Si se proporciona password (en Linux), se utiliza sudo -S para ejecutar
    el comando de instalación escribiendo la contraseña por stdin sin pkexec,
    esperando a que termine el proceso para confirmar que se aplicó.
    """
    system = platform.system()
    path   = str(package_path)

    if system == "Windows":
        # Lanzar el instalador Inno Setup y cerrar la app (Windows no requiere elevación previa)
        subprocess.Popen([path, "/SILENT", "/NORESTART"])
        return True

    if system == "Linux":
        mgr = _detect_package_manager()

        install_cmds = {
            "pacman": ["pkexec", "pacman", "-U", "--noconfirm", path],
            "apt":    ["pkexec", "apt",    "install", "-y", path],
            "dnf":    ["pkexec", "dnf",    "install", "-y", path],
            "zypper": ["pkexec", "zypper", "install", "-y", path],
        }

        cmd = install_cmds.get(mgr)
        if not cmd:
            logger.warning(f"Unknown package manager: {mgr}")
            return False

        try:
            # Esperamos a que termine pkexec, que mostrará el diálogo del sistema
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await proc.communicate()
            
            logger.info(f"Installation process finished with return code: {proc.returncode}")
            if proc.returncode == 0:
                return True
            else:
                err_msg = stderr.decode().strip()
                logger.error(f"Installation failed: {err_msg}")
                # Fallback to terminal if pkexec fails or is not available
                terminal_cmds = {
                    "pacman": f"sudo pacman -U --noconfirm {path}",
                    "apt":    f"sudo apt install -y {path}",
                    "dnf":    f"sudo dnf install -y {path}",
                    "zypper": f"sudo zypper install -y {path}",
                }
                cmd_str = terminal_cmds.get(mgr, "")
                if cmd_str:
                    for term in ["konsole", "gnome-terminal", "xterm", "alacritty"]:
                        if shutil.which(term):
                            subprocess.Popen([term, "-e", "bash", "-c",
                                             f"{cmd_str}; read -p 'Presiona Enter para cerrar'"],
                                             start_new_session=True)
                            return True
                return False
        except Exception as e:
            logger.error(f"Async installation execution failed: {e}")
            return False

    return False


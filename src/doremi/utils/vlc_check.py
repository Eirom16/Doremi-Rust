import sys
import os
import platform
from pathlib import Path
from loguru import logger


def _find_vlc_lib() -> Path | None:
    """Busca libvlc en el directorio VLC embebido y en rutas del sistema."""
    from doremi.config.paths import AppDirs
    import sys

    is_win = sys.platform.startswith('win')
    lib_name = "libvlc.dll" if is_win else "libvlc.so.5"
    alternative_name = "libvlc.dll" if is_win else "libvlc.so"

    candidates: list[Path] = []

    # 0. VLC empaquetado en PyInstaller
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        meipass_vlc = Path(sys._MEIPASS) / "vlc_libs"
        if meipass_vlc.exists():
            candidates.append(meipass_vlc / lib_name)
            candidates.append(meipass_vlc / alternative_name)
            if is_win:
                for dll in meipass_vlc.rglob("*.dll"):
                    if "libvlc.dll" in dll.name.lower():
                        candidates.append(dll)
            else:
                for so in meipass_vlc.rglob("libvlc.so*"):
                    candidates.append(so)

    # 1. VLC embebido
    vlc_dir = AppDirs.vlc_dir
    if vlc_dir.exists():
        candidates.append(vlc_dir / lib_name)
        candidates.append(vlc_dir / alternative_name)
        if is_win:
            for dll in vlc_dir.rglob("*.dll"):
                if "libvlc.dll" in dll.name.lower():
                    candidates.append(dll)
        else:
            for so in vlc_dir.rglob("libvlc.so*"):
                candidates.append(so)

    # 2. Rutas estándar del sistema
    if is_win:
        system_paths = [
            r"C:\Program Files\VideoLAN\VLC\libvlc.dll",
            r"C:\Program Files (x86)\VideoLAN\VLC\libvlc.dll",
        ]
        candidates.extend(Path(p) for p in system_paths)
    else:
        system_paths = [
            "/usr/lib/libvlc.so.5",
            "/usr/lib64/libvlc.so.5",
            "/usr/lib/x86_64-linux-gnu/libvlc.so.5",
            "/usr/lib/aarch64-linux-gnu/libvlc.so.5",
            "/usr/lib/libvlc.so",
            "/usr/lib64/libvlc.so",
            "/usr/lib/x86_64-linux-gnu/libvlc.so",
            "/usr/lib/aarch64-linux-gnu/libvlc.so",
        ]
        candidates.extend(Path(p) for p in system_paths)

    for p in candidates:
        if p.exists():
            logger.info(f"Found libvlc at {p}")
            return p

    return None


def setup_vlc_env() -> None:
    """Configura las variables de entorno para que python-vlc encuentre libvlc."""
    from doremi.config.paths import AppDirs
    import sys

    vlc_dir = AppDirs.vlc_dir

    # Si está congelado con PyInstaller, priorizar el vlc_libs empaquetado
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        meipass_vlc = Path(sys._MEIPASS) / "vlc_libs"
        if meipass_vlc.exists():
            vlc_dir = meipass_vlc

    # Si es Windows y no existe vlc_dir, probar rutas comunes de instalación antes de rendirse
    if not vlc_dir.exists() and sys.platform.startswith('win'):
        for p in [r"C:\Program Files\VideoLAN\VLC", r"C:\Program Files (x86)\VideoLAN\VLC"]:
            if Path(p).exists():
                vlc_dir = Path(p)
                break

    if not vlc_dir.exists():
        return

    # Configuración de variables según plataforma
    if sys.platform.startswith('win'):
        dll_path = vlc_dir / "libvlc.dll"
        if dll_path.exists():
            os.environ["PYTHON_VLC_LIB_PATH"] = str(dll_path)
            logger.info(f"Setting PYTHON_VLC_LIB_PATH to {dll_path}")
        
        # Agregar al PATH para compatibilidad general
        os.environ["PATH"] = f"{vlc_dir};{os.environ.get('PATH', '')}"
        
        # add_dll_directory para Python 3.8+ (crítico para ctypes y dependencias como libvlccore.dll)
        if hasattr(os, "add_dll_directory"):
            try:
                os.add_dll_directory(str(vlc_dir))
                logger.info(f"Added DLL search directory: {vlc_dir}")
            except Exception as e:
                logger.warning(f"Failed to add DLL directory {vlc_dir}: {e}")
    else:
        vlc_lib = str(vlc_dir)
        os.environ["LD_LIBRARY_PATH"] = f"{vlc_lib}:{os.environ.get('LD_LIBRARY_PATH', '')}"

    if not os.environ.get("VLC_PLUGIN_PATH"):
        plugin_dir = vlc_dir / "plugins"
        if plugin_dir.exists():
            os.environ["VLC_PLUGIN_PATH"] = str(plugin_dir)
            logger.info(f"Setting VLC_PLUGIN_PATH to {plugin_dir}")


def check_vlc_available() -> bool:
    """Verifica que libvlc está disponible (embebido o del sistema)."""
    lib_path = _find_vlc_lib()
    if lib_path:
        try:
            import vlc
            instance = vlc.Instance("--quiet")
            if instance is None:
                raise RuntimeError("VLC instance returned None")
            instance.release()
            logger.info("VLC detected successfully")
            return True
        except Exception as e:
            logger.error(f"VLC available but failed to initialize: {e}")
            return False
    return False


def get_vlc_install_command() -> str:
    """Detecta la distro y devuelve el comando de instalación correcto."""
    if not platform.system() == "Linux":
        return "Instala VLC desde https://www.videolan.org"

    if os.path.exists("/usr/bin/apt") or os.path.exists("/usr/bin/apt-get"):
        return "sudo apt install vlc libvlc-dev"
    elif os.path.exists("/usr/bin/dnf"):
        return "sudo dnf install vlc vlc-devel"
    elif os.path.exists("/usr/bin/pacman"):
        return "sudo pacman -S vlc"
    elif os.path.exists("/usr/bin/zypper"):
        return "sudo zypper install vlc"
    elif os.path.exists("/usr/bin/emerge"):
        return "sudo emerge media-video/vlc"
    else:
        return "Instala VLC desde tu gestor de paquetes o https://www.videolan.org"


def show_vlc_error_and_exit(app) -> None:
    """Muestra un QMessageBox con las instrucciones y termina."""
    from PySide6.QtWidgets import QMessageBox

    cmd = get_vlc_install_command()
    msg = QMessageBox()
    msg.setWindowTitle("VLC no encontrado — Doremi")
    msg.setIcon(QMessageBox.Icon.Critical)
    msg.setText("Doremi necesita VLC para reproducir música.")
    msg.setInformativeText(
        f"VLC (libvlc) no está disponible en tu sistema.\n\n"
        f"Instálalo con el siguiente comando:\n\n"
        f"    {cmd}\n\n"
        f"O coloca los archivos de VLC en:\n"
        f"    ~/.local/share/doremi/vlc/\n\n"
        f"Luego reinicia Doremi."
    )
    msg.setDetailedText(
        "Doremi usa libvlc para:\n"
        "• Reproducir streams de audio de YouTube Music\n"
        "• Aplicar el ecualizador paramétrico\n"
        "• Controlar velocidad, tono y volumen\n\n"
        "Sin libvlc, la reproducción de audio es imposible."
    )
    msg.setStandardButtons(QMessageBox.StandardButton.Ok)
    msg.exec()
    sys.exit(1)

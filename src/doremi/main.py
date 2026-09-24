import sys
import os
import multiprocessing

# Desviar hijos congelados antes de inicializar Qt o sus integraciones.
if __name__ == "__main__":
    multiprocessing.freeze_support()

from loguru import logger

# Desactivar GPU en QtWebEngine/Chromium en Linux de forma universal para evitar caídas catastróficas
# del controlador gráfico en diálogos embebidos de login (especialmente en Wayland/Xwayland).
# Forzar renderizado por software completo solo en entornos congelados (AppImage) o sin pantalla (headless).
if sys.platform.startswith('linux'):
    # Asegurar locale UTF-8 para evitar fallos de codificación/conversión interna de strings de Chromium/Qt
    for env_var in ["LC_ALL", "LC_CTYPE", "LANG"]:
        val = os.environ.get(env_var, "")
        if not val or val == "C" or "ANSI" in val or val.lower() == "posix":
            os.environ[env_var] = "C.UTF-8"

    # Desactivar GPU y Sandbox de Chromium para evitar fallos del controlador en Wayland
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
        "--disable-gpu "
        "--disable-gpu-compositing "
        "--disable-gpu-rasterization "
        "--disable-gpu-sandbox "
        "--no-sandbox "
        "--disable-dev-shm-usage"
    )
    os.environ["QTWEBENGINE_DISABLE_SANDBOX"] = "1"
    
    is_headless = not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY")
    is_frozen = getattr(sys, 'frozen', False)
    if is_frozen or is_headless:
        os.environ.setdefault("QT_QPA_PLATFORM", "xcb")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        os.environ.setdefault("QT_RHI_BACKEND", "software")
        os.environ.setdefault("QT_XCB_GL_INTEGRATION", "none")

# Monkey-patch gettext to prevent FileNotFoundError when translation files (e.g. ytmusicapi) are missing
import gettext
orig_translation = gettext.translation
def patched_translation(*args, **kwargs):
    try:
        return orig_translation(*args, **kwargs)
    except FileNotFoundError:
        return gettext.NullTranslations()
gettext.translation = patched_translation

# Monkey-patch to fix PySide6 6.7+ event dispatcher compatibility with qasync
try:
    from PySide6.QtCore import QAbstractEventDispatcher, QEventLoop
    orig_process_events = QAbstractEventDispatcher.processEvents

    def patched_process_events(self, flags):
        if not isinstance(flags, QEventLoop.ProcessEventsFlag):
            try:
                flags = QEventLoop.ProcessEventsFlag(int(flags))
            except Exception as e:
                logger.debug(f"Could not normalize Qt processEvents flags: {e}")
        return orig_process_events(self, flags)

    QAbstractEventDispatcher.processEvents = patched_process_events
except Exception as e:
    logger.debug(f"PySide6 qasync compatibility patch not applied: {e}")

import subprocess

# Prevenir parpadeo de ventanas de consola secundarias en Windows
if sys.platform.startswith('win'):
    _orig_popen_init = subprocess.Popen.__init__
    def _patched_popen_init(self, *args, **kwargs):
        creationflags = kwargs.get('creationflags', 0)
        kwargs['creationflags'] = creationflags | 0x08000000 # CREATE_NO_WINDOW
        _orig_popen_init(self, *args, **kwargs)
    subprocess.Popen.__init__ = _patched_popen_init

import asyncio
import qasync
import warnings
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from doremi import __version__
from doremi.utils.vlc_check import check_vlc_available, show_vlc_error_and_exit, setup_vlc_env
from doremi.config.paths import AppDirs
from doremi.config.settings import AppSettings
from doremi.db.database import init_db

warnings.filterwarnings("ignore")


def _install_qpainter_trace() -> None:
    """Opt-in diagnostic: when DOREMI_PAINTER_TRACE=1 is set, capture the Python
    stack trace of any Qt 'painter' warning to a log file. Use this to pinpoint
    the exact location of 'QPainter::begin: A paint device can only be painted by
    one painter at a time' warnings that are hard to reproduce headlessly."""
    if not os.environ.get("DOREMI_PAINTER_TRACE"):
        return
    import tempfile
    import traceback as _tb
    from PySide6.QtCore import qInstallMessageHandler

    log_path = os.path.join(tempfile.gettempdir(), "doremi_painter_trace.log")
    try:
        _fh = open(log_path, "a", encoding="utf-8")
    except OSError:
        return

    def _handler(msg_type, context, message):
        if "painter" in message.lower():
            _fh.write("\n=== QPainter warning ===\n")
            _fh.write(f"{message}\n")
            _tb.print_stack(file=_fh)
            _fh.flush()

    qInstallMessageHandler(_handler)
    logger.warning(f"QPainter trace enabled -> {log_path}")


def setup_logging() -> None:
    log_file = AppDirs.logs / "doremi_{time:YYYY-MM-DD}.log"
    logger.add(
        log_file,
        rotation="10 MB",
        retention="7 days",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {name}:{line} | {message}",
    )


def handle_async_exception(loop, context):
    msg = context.get("message", "Unhandled exception in event loop")
    exception = context.get("exception")
    
    # Ignore harmless asyncio/qasync shutdown exceptions
    if isinstance(exception, RuntimeError) and "is not the running loop" in str(exception):
        return
    if "is not the running loop" in msg:
        return

    if exception:
        logger.exception(f"{msg}: {exception}", exc_info=exception)
    else:
        logger.error(msg)


async def main_async(app: QApplication, settings: AppSettings, loop: qasync.QEventLoop) -> None:
    loop.set_exception_handler(handle_async_exception)
    
    await init_db()
    from doremi.ui.main_window import MainWindow
    window = MainWindow(settings, loop)
    window.show()

    quit_future = loop.create_future()

    def cleanup():
        if not quit_future.done():
            quit_future.set_result(None)

    app.aboutToQuit.connect(cleanup)

    try:
        await quit_future
    except Exception as e:
        logger.debug(f"Quit future interrupted during shutdown: {e}")
    finally:
        # Graceful async shutdown
        try:
            await window.async_shutdown()
        except Exception as e:
            logger.error(f"Error during async shutdown: {e}")
        
        from doremi.db.database import close_db
        try:
            await close_db()
        except Exception as e:
            logger.warning(f"Error disposing database engine: {e}")



def main() -> None:
    multiprocessing.freeze_support()
    import os
    # En Linux congelado (AppImage), forzar xcb y renderizado por software
    # para evitar fallos de Wayland EGL y de GLX dentro del sandbox del AppImage
    if sys.platform.startswith('linux') and getattr(sys, 'frozen', False):
        if not os.environ.get("QT_QPA_PLATFORM"):
            os.environ["QT_QPA_PLATFORM"] = "xcb"
        # Forzar renderizado por software para Qt Quick (QQuickWidget)
        # El AppImage no puede resolver los drivers GLX/EGL del host correctamente
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        # Deshabilitar GPU en QtWebEngine/Chromium embebido
        os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu")

    if sys.platform.startswith('linux'):
        # VAAPI/libva puede terminar en SIGSEGV al mapear superficies GPU en el
        # backend FFmpeg de Qt Multimedia (visor de videoclips de Now Playing).
        # Lista vacía = decodificar siempre por software (variable privada, ver
        # "Advanced FFmpeg Configuration" de la doc de Qt Multimedia).
        os.environ.setdefault("QT_FFMPEG_DECODING_HW_DEVICE_TYPES", ",")
        # Añadir argumentos directamente a sys.argv antes de inicializar QApplication
        # Esto asegura que Chromium herede los flags correctos bajo cualquier circunstancia
        chromium_args = [
            "--disable-gpu",
            "--disable-gpu-compositing",
            "--disable-gpu-rasterization",
            "--disable-gpu-sandbox",
            "--no-sandbox",
            "--disable-dev-shm-usage"
        ]
        for arg in chromium_args:
            if arg not in sys.argv:
                sys.argv.append(arg)
            
    _install_qpainter_trace()
    app = QApplication(sys.argv)
    app.setApplicationName("Doremi")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("doremi")
    # En Flatpak el desktop file se instala como org.doremi.Doremi.desktop; en
    # deb/arch/dev como doremi.desktop. El portal rechaza IDs sin desktop file
    # registrado, así que el ID debe coincidir con el realmente instalado.
    if sys.platform.startswith('linux') and (os.environ.get("FLATPAK_ID") or os.path.exists("/.flatpak-info")):
        app.setDesktopFileName("org.doremi.Doremi")
    else:
        app.setDesktopFileName("doremi")

    setup_vlc_env()
    vlc_ok = check_vlc_available()
    if not vlc_ok:
        logger.warning("VLC no encontrado. La app funcionará pero no podrá reproducir música sin VLC.")

    AppDirs.setup()
    
    from PySide6.QtGui import QIcon, QPixmapCache
    QPixmapCache.setCacheLimit(524288)  # 512 MB cache for covers
    icon_path = AppDirs.root / "assets" / "icon.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    
    from doremi.ui.design.fonts import load_fonts, AppFont
    load_fonts()
    app.setFont(AppFont.body())

    settings = AppSettings.load(AppDirs.settings_file)
    from doremi.utils.i18n import set_language
    set_language(settings.language)
    setup_logging()

    # Styles are applied immediately within MainWindow during initialization


    with qasync.QEventLoop(app) as loop:
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(main_async(app, settings, loop))
        except RuntimeError as e:
            if "Event loop stopped" not in str(e):
                raise


if __name__ == "__main__":
    main()

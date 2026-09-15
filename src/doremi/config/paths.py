import os
from pathlib import Path


class _AppDirs:
    _name = "doremi"

    @property
    def root(self) -> Path:
        """Project root directory."""
        import sys
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            return Path(sys._MEIPASS)
        return Path(__file__).parent.parent.parent.parent

    @property
    def config(self) -> Path:
        base = os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
        return Path(base) / self._name

    @property
    def data(self) -> Path:
        base = os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share"))
        return Path(base) / self._name

    @property
    def cache(self) -> Path:
        base = os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))
        return Path(base) / self._name

    @property
    def artwork_cache(self) -> Path:
        return self.cache / "artwork"

    @property
    def lyrics_cache(self) -> Path:
        return self.cache / "lyrics"

    @property
    def downloads(self) -> Path:
        return self.data / "downloads"

    @property
    def database(self) -> Path:
        return self.data / "doremi.db"

    @property
    def settings_file(self) -> Path:
        return self.config / "settings.toml"



    @property
    def logs(self) -> Path:
        return self.data / "logs"

    @property
    def vlc_dir(self) -> Path:
        return self.data / "vlc"

    def setup(self) -> None:
        for d in [self.config, self.data, self.cache,
                  self.artwork_cache, self.lyrics_cache, self.downloads, self.logs, self.vlc_dir]:
            d.mkdir(parents=True, exist_ok=True)


AppDirs = _AppDirs()

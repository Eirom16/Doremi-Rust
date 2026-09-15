from __future__ import annotations
from pathlib import Path
from pydantic import BaseModel, Field
import tomllib
import tomli_w


class AppearanceSettings(BaseModel):
    theme_mode: str = "dark"
    accent_color: str = "#7C4DFF"
    use_dynamic_color: bool = True
    show_artwork_blur_bg: bool = True
    compact_sidebar: bool = False
    font_size: int = 13

class PlayerSettings(BaseModel):
    volume: int = 80
    normalize_audio: bool = True
    skip_silence: bool = False
    crossfade_enabled: bool = True
    crossfade_duration_sec: int = 5
    resume_on_startup: bool = True
    gapless_playback: bool = True
    stop_on_close: bool = False
    sleep_timer_minutes: int = 0
    minimize_to_tray: bool = True
    shuffle_enabled: bool = False
    repeat_mode: str = "off"

class EqualizerSettings(BaseModel):
    enabled: bool = False
    preamp: float = 0.0
    bands: list[float] = Field(default_factory=lambda: [0.0] * 10)
    preset_name: str = "Flat"

class NetworkSettings(BaseModel):
    proxy_url: str | None = None
    stream_quality: str = "best"
    preload_next: bool = True

class IntegrationsSettings(BaseModel):
    lastfm_enabled: bool = False
    lastfm_session_key: str = ""
    lastfm_api_key: str = ""
    lastfm_api_secret: str = ""
    discord_rpc_enabled: bool = False
    mpris_enabled: bool = True

class SubtitleSettings(BaseModel):
    alignment: str = "center"          # "left", "center", "right"
    font_size: int = 22                # Tamaño de fuente en pt
    line_spacing: float = 1.5          # Interlineado de párrafos
    delay_ms: int = 0                  # Retraso/Adelanto manual en milisegundos
    auto_scroll: bool = True           # Auto-desplazamiento vertical al cantar
    animation_style: str = "glow"      # "none", "fade", "glow", "slide", "karaoke"
    glow_effect: bool = True           # Animación de brillo y aumento de escala
    text_color_active: str = "#FFFFFF"  # Color de la línea cantándose
    text_color_inactive: str = "#6E6E77" # Color de las líneas previas/siguientes

class AppSettings(BaseModel):
    google_client_id: str = ""
    google_client_secret: str = ""
    appearance: AppearanceSettings = Field(default_factory=AppearanceSettings)
    player: PlayerSettings = Field(default_factory=PlayerSettings)
    equalizer: EqualizerSettings = Field(default_factory=EqualizerSettings)
    network: NetworkSettings = Field(default_factory=NetworkSettings)
    integrations: IntegrationsSettings = Field(default_factory=IntegrationsSettings)
    subtitles: SubtitleSettings = Field(default_factory=SubtitleSettings)
    language: str = "es"
    last_video_id: str | None = None

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        
        data = self.model_dump(exclude_none=True)
        
        # Exclude secrets from the saved settings.toml file
        if "integrations" in data:
            data["integrations"].pop("lastfm_api_key", None)
            data["integrations"].pop("lastfm_api_secret", None)
            data["integrations"].pop("lastfm_session_key", None)
            
        with open(path, "wb") as f:
            tomli_w.dump(data, f)

    @classmethod
    def load(cls, path: Path) -> AppSettings:
        settings = cls()
        if path.exists():
            try:
                with open(path, "rb") as f:
                    data = tomllib.load(f)
                settings = cls(**data)
            except Exception:
                pass
                
        # Load Last.fm credentials securely from keyring
        try:
            from doremi.utils.secure_storage import SecureStorage
            api_key, api_secret, session_key = SecureStorage.load_lastfm_credentials()
            if api_key:
                settings.integrations.lastfm_api_key = api_key
            if api_secret:
                settings.integrations.lastfm_api_secret = api_secret
            if session_key:
                settings.integrations.lastfm_session_key = session_key
        except Exception:
            pass
            
        return settings

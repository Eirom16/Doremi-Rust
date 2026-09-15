import platform
from loguru import logger

_DBUS_OK = False
if platform.system() == "Linux":
    try:
        import dbus
        import dbus.service
        import dbus.mainloop.glib
        _DBUS_OK = True
    except ImportError:
        logger.warning("dbus-python not available. MPRIS2 disabled.")

MPRIS2_IFACE = "org.mpris.MediaPlayer2"
PLAYER_IFACE = "org.mpris.MediaPlayer2.Player"
BUS_NAME = "org.mpris.MediaPlayer2.doremi"
OBJECT_PATH = "/org/mpris/MediaPlayer2"


if _DBUS_OK:
    class MprisPlayerService(dbus.service.Object):
        def __init__(self, bus, mpris_wrapper):
            dbus.service.Object.__init__(self, bus, OBJECT_PATH)
            self.mpris = mpris_wrapper
            
        @dbus.service.method(MPRIS2_IFACE, in_signature="", out_signature="")
        def Raise(self):
            if self.mpris.on_raise:
                self.mpris.on_raise()

        @dbus.service.method(MPRIS2_IFACE, in_signature="", out_signature="")
        def Quit(self):
            if self.mpris.on_quit:
                self.mpris.on_quit()

        @dbus.service.method(PLAYER_IFACE, in_signature="", out_signature="")
        def Next(self):
            if self.mpris.on_next:
                self.mpris.on_next()

        @dbus.service.method(PLAYER_IFACE, in_signature="", out_signature="")
        def Previous(self):
            if self.mpris.on_prev:
                self.mpris.on_prev()

        @dbus.service.method(PLAYER_IFACE, in_signature="", out_signature="")
        def Pause(self):
            if self.mpris.on_pause:
                self.mpris.on_pause()

        @dbus.service.method(PLAYER_IFACE, in_signature="", out_signature="")
        def PlayPause(self):
            if self.mpris.on_play_pause:
                self.mpris.on_play_pause()

        @dbus.service.method(PLAYER_IFACE, in_signature="", out_signature="")
        def Play(self):
            if self.mpris.on_play:
                self.mpris.on_play()

        @dbus.service.method(PLAYER_IFACE, in_signature="", out_signature="")
        def Stop(self):
            if self.mpris.on_stop:
                self.mpris.on_stop()

        @dbus.service.method(PLAYER_IFACE, in_signature="x", out_signature="")
        def Seek(self, offset_us):
            if self.mpris.on_seek:
                self.mpris.on_seek(offset_us)

        @dbus.service.method(PLAYER_IFACE, in_signature="ox", out_signature="")
        def SetPosition(self, track_id, position_us):
            if self.mpris.on_set_position:
                self.mpris.on_set_position(track_id, position_us)

        @dbus.service.method("org.freedesktop.DBus.Properties", in_signature="ss", out_signature="v")
        def Get(self, interface_name, property_name):
            return self.GetAll(interface_name)[property_name]

        @dbus.service.method("org.freedesktop.DBus.Properties", in_signature="s", out_signature="a{sv}")
        def GetAll(self, interface_name):
            if interface_name == MPRIS2_IFACE:
                return {
                    "CanQuit": dbus.Boolean(True),
                    "Fullscreen": dbus.Boolean(False),
                    "CanSetFullscreen": dbus.Boolean(False),
                    "HasTrackList": dbus.Boolean(False),
                    "Identity": dbus.String("Doremi"),
                    "DesktopEntry": dbus.String("doremi"),
                    "SupportedUriSchemes": dbus.Array([], signature="s"),
                    "SupportedMimeTypes": dbus.Array([], signature="s"),
                }
            elif interface_name == PLAYER_IFACE:
                return {
                    "PlaybackStatus": dbus.String(self.mpris.playback_status),
                    "LoopStatus": dbus.String(self.mpris.loop_status),
                    "Rate": dbus.Double(1.0),
                    "Shuffle": dbus.Boolean(self.mpris.shuffle),
                    "Metadata": self.mpris.metadata,
                    "Volume": dbus.Double(self.mpris.volume),
                    "Position": dbus.Int64(self.mpris.position_us),
                    "MinimumRate": dbus.Double(1.0),
                    "MaximumRate": dbus.Double(1.0),
                    "CanGoNext": dbus.Boolean(True),
                    "CanGoPrevious": dbus.Boolean(True),
                    "CanPlay": dbus.Boolean(True),
                    "CanPause": dbus.Boolean(True),
                    "CanSeek": dbus.Boolean(True),
                    "CanControl": dbus.Boolean(True),
                }
            else:
                raise dbus.exceptions.DBusException("Unknown interface")

        @dbus.service.method("org.freedesktop.DBus.Properties", in_signature="ssv", out_signature="")
        def Set(self, interface_name, property_name, new_value):
            if interface_name == PLAYER_IFACE:
                if property_name == "Volume":
                    if self.mpris.on_set_volume:
                        self.mpris.on_set_volume(float(new_value))
                elif property_name == "Shuffle":
                    if self.mpris.on_set_shuffle:
                        self.mpris.on_set_shuffle(bool(new_value))
                elif property_name == "LoopStatus":
                    if self.mpris.on_set_loop_status:
                        self.mpris.on_set_loop_status(str(new_value))

        @dbus.service.signal("org.freedesktop.DBus.Properties", signature="sa{sv}as")
        def PropertiesChanged(self, interface_name, changed_properties, invalidated_properties):
            pass

        @dbus.service.signal(PLAYER_IFACE, signature="x")
        def Seeked(self, position_us):
            pass

        def notify_properties_changed(self, interface_name, changed_properties):
            self.PropertiesChanged(interface_name, changed_properties, [])

        def notify_seeked(self, position_us):
            self.Seeked(position_us)


class MprisPlayer:
    def __init__(self, player, queue):
        self.player = player
        self.queue = queue
        self._bus = None
        self._service = None
        self._active = False
        
        # State stored for MPRIS properties
        self.playback_status = "Stopped"
        self.metadata = dbus.Dictionary({}, signature="sv") if _DBUS_OK else {}
        self.volume = 1.0
        self.position_us = 0
        self.shuffle = False
        self.loop_status = self._loop_status_from_queue()

        # Callbacks to wire to MainWindow
        self.on_play_pause = None
        self.on_play = None
        self.on_pause = None
        self.on_stop = None
        self.on_next = None
        self.on_prev = None
        self.on_seek = None
        self.on_set_position = None
        self.on_set_volume = None
        self.on_set_shuffle = None
        self.on_set_loop_status = None
        self.on_raise = None
        self.on_quit = None

    def _loop_status_from_queue(self) -> str:
        from doremi.audio.queue import RepeatMode
        if self.queue.repeat_mode == RepeatMode.ALL:
            return "Playlist"
        if self.queue.repeat_mode == RepeatMode.ONE:
            return "Track"
        return "None"

    def start(self) -> None:
        if not _DBUS_OK:
            return
        try:
            dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
            self._bus = dbus.SessionBus()
            self._bus.request_name(BUS_NAME)
            self._service = MprisPlayerService(self._bus, self)
            self._active = True
            logger.info(f"MPRIS2 registered as {BUS_NAME}")
        except Exception as e:
            logger.error(f"MPRIS2 registration failed: {e}")
            self._active = False

    def update_metadata(
        self,
        title: str,
        artist: str,
        album: str,
        duration_us: int,
        artwork_url: str,
        video_id: str = "",
    ) -> None:
        if not self._active or not _DBUS_OK:
            return
        try:
            # clean track ID for dbus
            clean_title = "".join(c for c in title if c.isalnum() or c in "_/").strip()
            if not clean_title:
                clean_title = "track"
            track_id = f"/track/{clean_title[:30]}"
            
            self.metadata = dbus.Dictionary({
                "mpris:trackid": dbus.ObjectPath(track_id),
                "mpris:length": dbus.Int64(duration_us),
                "xesam:title": dbus.String(title),
                "xesam:artist": dbus.Array([dbus.String(artist)], signature="s"),
                "xesam:album": dbus.String(album),
                "xesam:albumArtist": dbus.Array([dbus.String(artist)], signature="s"),
            }, signature="sv")
            
            if artwork_url:
                self.metadata["mpris:artUrl"] = dbus.String(artwork_url)
            if video_id and video_id != "local":
                self.metadata["xesam:url"] = dbus.String(f"https://music.youtube.com/watch?v={video_id}")
                
            self._service.notify_properties_changed(PLAYER_IFACE, {"Metadata": self.metadata})
        except Exception as e:
            logger.debug(f"MPRIS2 metadata notify failed: {e}")

    def update_playback_status(self, is_playing: bool) -> None:
        if not self._active or not _DBUS_OK:
            return
        status = "Playing" if is_playing else "Paused"
        if status != self.playback_status:
            self.playback_status = status
            try:
                self._service.notify_properties_changed(PLAYER_IFACE, {"PlaybackStatus": dbus.String(status)})
            except Exception as e:
                logger.debug(f"MPRIS2 playback status notify failed: {e}")

    def update_position(self, position_ms: int) -> None:
        self.position_us = int(position_ms * 1000)

    def emit_seeked(self, position_ms: int) -> None:
        self.update_position(position_ms)
        if not self._active or not _DBUS_OK:
            return
        try:
            self._service.notify_seeked(self.position_us)
        except Exception as e:
            logger.debug(f"MPRIS2 Seeked notify failed: {e}")

    def update_volume(self, volume_percent: int) -> None:
        if not self._active or not _DBUS_OK:
            return
        vol = max(0.0, min(1.0, volume_percent / 100.0))
        if vol != self.volume:
            self.volume = vol
            try:
                self._service.notify_properties_changed(PLAYER_IFACE, {"Volume": dbus.Double(vol)})
            except Exception as e:
                logger.debug(f"MPRIS2 volume notify failed: {e}")

    def update_shuffle(self, shuffle_enabled: bool) -> None:
        if not self._active or not _DBUS_OK:
            return
        if shuffle_enabled != self.shuffle:
            self.shuffle = shuffle_enabled
            try:
                self._service.notify_properties_changed(PLAYER_IFACE, {"Shuffle": dbus.Boolean(shuffle_enabled)})
            except Exception as e:
                logger.debug(f"MPRIS2 shuffle notify failed: {e}")

    def update_loop_status(self) -> None:
        if not self._active or not _DBUS_OK:
            return
        loop_status = self._loop_status_from_queue()
        if loop_status != self.loop_status:
            self.loop_status = loop_status
            try:
                self._service.notify_properties_changed(
                    PLAYER_IFACE, {"LoopStatus": dbus.String(loop_status)}
                )
            except Exception as e:
                logger.debug(f"MPRIS2 loop status notify failed: {e}")

    def stop(self) -> None:
        if not self._active:
            return
        try:
            if self._bus:
                self._bus.release_name(BUS_NAME)
        except Exception:
            pass
        self._active = False

import asyncio
from loguru import logger


class NetworkMonitor:

    def __init__(self, on_connectivity_change):
        self.on_connectivity_change = on_connectivity_change
        self._is_connected = True
        self._task = None
        self._dbus_unavailable_logged = False
        
    async def start(self):
        self._is_connected = await self.check_connectivity()
        self._task = asyncio.create_task(self._monitor())
        logger.info("Network monitor started")

    async def stop(self):
        if self._task:
            self._task.cancel()

    async def check_connectivity(self) -> bool:
        def _check_networkmanager() -> bool | None:
            try:
                import dbus

                bus = dbus.SystemBus()
                proxy = bus.get_object(
                    "org.freedesktop.NetworkManager",
                    "/org/freedesktop/NetworkManager",
                )
                props = dbus.Interface(proxy, "org.freedesktop.DBus.Properties")
                state = int(props.Get("org.freedesktop.NetworkManager", "State"))
                return state in {50, 60, 70}
            except Exception as e:
                if not self._dbus_unavailable_logged:
                    logger.debug(f"NetworkManager/DBus connectivity check unavailable: {e}")
                    self._dbus_unavailable_logged = True
                return None

        def _check() -> bool:
            nm_state = _check_networkmanager()
            if nm_state is not None:
                return nm_state

            try:
                import socket
                with socket.create_connection(("8.8.8.8", 53), timeout=3):
                    return True
            except Exception as e:
                logger.debug(f"Socket connectivity check failed: {e}")
                return False

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _check)

    async def _monitor(self):
        while True:
            await asyncio.sleep(30)
            was_connected = self._is_connected
            self._is_connected = await self.check_connectivity()
            
            if was_connected != self._is_connected:
                logger.info(f"Network connectivity changed: {self._is_connected}")
                if self.on_connectivity_change:
                    self.on_connectivity_change(self._is_connected)

    @property
    def is_connected(self) -> bool:
        return self._is_connected

import asyncio
import socket
from json import load as json_load

from zeroconf import ServiceInfo, Zeroconf
from zeroconf.asyncio import AsyncZeroconf


class DesignerPlugin:
    """When used as a context manager (using the `with` statement), publish a plugin using DNS-SD for the Disguise Designer application"""

    def __init__(
        self,
        name: str,
        port: int,
        hostname: str | None = None,
        url: str | None = None,
        requires_session: bool = False,
        is_disguise: bool = False,
    ):
        self.name = name
        self.port = port
        self.hostname = hostname or socket.gethostname()
        self.custom_url = url
        self.url = url or f"http://{self.hostname}:{port}"
        self.requires_session = requires_session
        self.is_disguise = is_disguise

        self._zeroconf: Zeroconf | None = None
        self._azeroconf: AsyncZeroconf | None = None

    @staticmethod
    def default_init(port: int, hostname: str | None = None) -> "DesignerPlugin":
        """Initialize the plugin options with the values in d3plugin.json."""
        return DesignerPlugin.from_json_file(
            file_path="./d3plugin.json", port=port, hostname=hostname
        )

    @staticmethod
    def from_json_file(file_path: str, port: int, hostname: str | None = None) -> "DesignerPlugin":
        """Convert a JSON file (expected d3plugin.json) to PluginOptions. hostname and port are required."""
        with open(file_path) as f:
            options = json_load(f)
            return DesignerPlugin(
                name=options["name"],
                port=port,
                hostname=hostname,
                url=options.get("url", None),
                requires_session=options.get("requiresSession", False),
                is_disguise=options.get("isDisguise", False),
            )

    @property
    def service_info(self) -> ServiceInfo:
        """Convert the options to a dictionary suitable for DNS-SD service properties."""
        properties = {
            b"t": b"web",
            b"s": b"true" if self.requires_session else b"false",
            b"d": b"true" if self.is_disguise else b"false",
        }
        if self.custom_url:
            properties[b"u"] = self.custom_url.encode()

        return ServiceInfo(
            "_d3plugin._tcp.local.",
            name=f"{self.name}._d3plugin._tcp.local.",
            port=self.port,
            properties=properties,
            server=f"{self.hostname}.local.",
        )

    def __enter__(self) -> "DesignerPlugin":
        self._zeroconf = Zeroconf()
        self._zeroconf.register_service(self.service_info)
        return self

    def __exit__(self, exc_type, exc_value, traceback):  # type: ignore
        if self._zeroconf:
            self._zeroconf.close()
            self._zeroconf = None

    async def __aenter__(self) -> "DesignerPlugin":
        self._azeroconf = AsyncZeroconf()
        asyncio.create_task(self._azeroconf.async_register_service(self.service_info))
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):  # type: ignore
        if self._azeroconf:
            await self._azeroconf.async_close()
            self._azeroconf = None

from zeroconf import ServiceInfo, Zeroconf
from zeroconf.asyncio import AsyncZeroconf
import asyncio, socket
from typing import Dict, Optional
from json import load as json_load

class DesignerPlugin:
    """When used as a context manager (using the `with` statement), publish a plugin using DNS-SD for the Disguise Designer application"""

    def __init__(self,
                 name: str,
                 port: int,
                 hostname: Optional[str] = None,
                 url: Optional[str] = None,
                 requires_session: bool = False):
        self.name = name
        self.port = port
        self.hostname = hostname or socket.gethostname()
        self.url = url or f"http://{self.hostname}:{port}"
        self.requires_session = requires_session

    @staticmethod
    def default_init(port: int, hostname: Optional[str] = None):
        """Initialize the plugin options with the values in d3plugin.json."""
        return DesignerPlugin.from_json_file(
            file_path="./d3plugin.json",
            port=port,
            hostname=hostname
        )

    @staticmethod
    def from_json_file(file_path, port: int, hostname: Optional[str] = None):
        """Convert a JSON file (expected d3plugin.json) to PluginOptions. hostname and port are required."""
        with open(file_path, 'r') as f:
            options = json_load(f)
            return DesignerPlugin(
                name=options['name'],
                port=port,
                hostname=hostname,
                url=options.get('url', None),
                requires_session=options.get('requiresSession', False)
            )
    
    @property
    def service_info(self):
        """Convert the options to a dictionary suitable for DNS-SD service properties."""
        return ServiceInfo(
            "_d3plugin._tcp.local.",
            name=f"{self.name}._d3plugin._tcp.local.",
            port=self.port,
            properties={
                b"u": self.url.encode(),
                b"t": b'web',
                b"s": b'true' if self.requires_session else b'false',
            },
            server=f"{self.hostname}.local."
        )

    def __enter__(self):
        self.zeroconf = Zeroconf()
        self.zeroconf.register_service(self.service_info)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.zeroconf.close()

    async def __aenter__(self):
        self.zeroconf = AsyncZeroconf()
        asyncio.create_task(self.zeroconf.async_register_service(self.service_info))
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.zeroconf.async_close()

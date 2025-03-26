from zeroconf import ServiceInfo, Zeroconf
from zeroconf.asyncio import AsyncZeroconf
import asyncio, socket

class DesignerPlugin:
    "Publish a plugin for the Disguise Designer application."
    def __init__(self, name, port):
        self.name = name
        self.port = port
        self.hostname = socket.gethostname()

    @property
    def service_info(self):
        """Create and return the ServiceInfo object."""
        return ServiceInfo(
            "_d3plugin._tcp.local.",
            f"{self.name}._d3plugin._tcp.local.",
            port=self.port,
            properties={
                'pluginType': 'web',
                'hostname': self.hostname
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

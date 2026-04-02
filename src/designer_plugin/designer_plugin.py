"""
MIT License
Copyright (c) 2025 Disguise Technologies ltd
"""

import asyncio
import socket
from json import load as json_load

from zeroconf import ServiceInfo, Zeroconf
from zeroconf.asyncio import AsyncZeroconf


class DesignerPlugin:
    """Publish a plugin via DNS-SD so the Disguise Designer application can discover it.

    Use as a context manager (sync or async) to register and unregister the service
    automatically.

    Examples:
        Sync context manager:

        ```python
        from designer_plugin import DesignerPlugin

        with DesignerPlugin("MyPlugin", 9999) as plugin:
            # Plugin is now discoverable via DNS-SD by Designer
            input("Press Enter to stop...")
        ```

        Async context manager:

        ```python
        import asyncio
        from designer_plugin import DesignerPlugin

        async def main():
            async with DesignerPlugin("MyPlugin", 9999) as plugin:
                await asyncio.sleep(60)  # Keep plugin discoverable for 60 seconds

        asyncio.run(main())
        ```
    """

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
        """Initialize the plugin options with the values in d3plugin.json.

        Reads `name`, `url`, `requiresSession`, and `isDisguise` from `./d3plugin.json`
        in the current working directory.

        Args:
            port: The port number to publish the plugin on.
            hostname: Optional hostname override. Defaults to the machine hostname.

        Returns:
            A DesignerPlugin instance configured from d3plugin.json.

        Examples:
            ```python
            # Reads name/url from ./d3plugin.json, uses provided port
            with DesignerPlugin.default_init(port=9999) as plugin:
                input("Press Enter to stop...")
            ```
        """
        return DesignerPlugin.from_json_file(
            file_path="./d3plugin.json", port=port, hostname=hostname
        )

    @staticmethod
    def from_json_file(
        file_path: str, port: int, hostname: str | None = None
    ) -> "DesignerPlugin":
        """Load plugin options from a JSON file (d3plugin.json format).

        Args:
            file_path: Path to the JSON configuration file.
            port: The port number to publish the plugin on.
            hostname: Optional hostname override. Defaults to the machine hostname.

        Returns:
            A DesignerPlugin instance configured from the JSON file.

        Examples:
            ```python
            with DesignerPlugin.from_json_file("config/my_plugin.json", port=9999) as plugin:
                input("Press Enter to stop...")
            ```
        """
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

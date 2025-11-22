"""
MIT License
Copyright (c) 2025 Disguise Technologies ltd
"""

from typing import Any, Unpack

import aiohttp

from designer_plugin.api import (
    Method,
    d3_api_aplugin,
    d3_api_aregister_module,
    d3_api_arequest,
    d3_api_plugin,
    d3_api_register_module,
    d3_api_request,
)
from designer_plugin.d3sdk.function import D3Function
from designer_plugin.models import (
    PluginPayload,
    PluginResponse,
    RegisterPayload,
    RetType,
)


class D3SessionBase:
    """Base class for Designer session management."""

    def __init__(self, hostname: str, port: int, context_modules: list[str]) -> None:
        """Initialize base session with connection details and module context.

        Args:
            hostname: The hostname of the Designer instance.
            port: The port number of the Designer instance.
            context_modules: List of module names to register when entering session context.
        """
        self.hostname: str = hostname
        self.port: int = port
        self.context_modules: list[str] = context_modules


class D3Session(D3SessionBase):
    """Synchronous session for executing plugins on Designer.

    Manages connection to a Designer instance and provides synchronous API for
    plugin execution, module registration, and generic HTTP requests.
    """

    def __init__(
        self, hostname: str, port: int, context_modules: list[str] | None = None
    ) -> None:
        """Initialize synchronous Designer session.

        Args:
            hostname: The hostname of the Designer instance.
            port: The port number of the Designer instance.
            context_modules: Optional list of module names to register when entering session context.
        """
        super().__init__(hostname, port, context_modules or [])

    def __enter__(self) -> "D3Session":
        """Enter context manager and register all context modules.

        Returns:
            The session instance.

        Raises:
            RuntimeError: If any context module is not registered with @d3function.
        """
        for module_name in self.context_modules:
            is_registered: bool = self.register_module(module_name)
            if not is_registered:
                raise RuntimeError(
                    f"module {module_name} is not registered with d3function"
                )
        return self

    def __exit__(self, _type, _value, _traceback) -> None:
        """Exit context manager."""
        pass

    def rpc(
        self, payload: PluginPayload[RetType], timeout_sec: float | None = None
    ) -> RetType:
        """Execute a remote procedure call and return only the return value.

        Args:
            payload: Plugin payload containing script and optional module name.
            timeout_sec: Optional timeout in seconds for the request.

        Returns:
            The return value from the plugin execution.

        Raises:
            PluginException: If the plugin execution fails.
        """
        return self.plugin(payload, timeout_sec).returnValue

    def plugin(
        self, payload: PluginPayload[RetType], timeout_sec: float | None = None
    ) -> PluginResponse[RetType]:
        """Execute a plugin script on Designer.

        Args:
            payload: Plugin payload containing script and optional module name.
            timeout_sec: Optional timeout in seconds for the request.

        Returns:
            PluginResponse containing status, logs, and return value.

        Raises:
            PluginException: If the plugin execution fails.
        """
        return d3_api_plugin(self.hostname, self.port, payload, timeout_sec)

    def request(self, method: Method, url_endpoint: str, **kwargs):
        """Make a generic HTTP request to Designer API.

        Args:
            method: HTTP method to use.
            url_endpoint: The API endpoint path.
            **kwargs: Additional arguments to pass to requests.request.

        Returns:
            JSON response from the API.
        """
        return d3_api_request(method, self.hostname, self.port, url_endpoint, **kwargs)

    def register_module(
        self, module_name: str, timeout_sec: float | None = None
    ) -> bool:
        """Register a module with Designer.

        Args:
            module_name: Name of the module to register.
            timeout_sec: Optional timeout in seconds for the request.

        Returns:
            True if module was registered successfully, False if module not found.

        Raises:
            PluginException: If module registration fails on Designer side.
        """
        payload: RegisterPayload | None = D3Function.get_module_register_payload(
            module_name
        )
        if payload:
            d3_api_register_module(self.hostname, self.port, payload, timeout_sec)
            return True
        return False

    def register_all_modules(self, timeout_sec: float | None = None) -> dict[str, bool]:
        """Register all modules decorated with @d3function.

        Args:
            timeout_sec: Optional timeout in seconds for each registration request.

        Returns:
            Dictionary mapping module names to registration success status.

        Raises:
            PluginException: If any module registration fails on Designer side.
        """
        modules: list[str] = list(D3Function._available_d3functions.keys())
        register_success: dict[str, bool] = {}
        for module_name in modules:
            is_registered: bool = self.register_module(module_name, timeout_sec)
            register_success[module_name] = is_registered
        return register_success


class D3AsyncSession(D3SessionBase):
    """Asynchronous session for executing plugins on Designer.

    Manages connection to a Designer instance and provides asynchronous API for
    plugin execution, module registration, and generic HTTP requests.
    """

    def __init__(
        self, hostname: str, port: int, context_modules: list[str] | None = None
    ) -> None:
        """Initialize asynchronous Designer session.

        Args:
            hostname: The hostname of the Designer instance.
            port: The port number of the Designer instance.
            context_modules: Optional list of module names to register when entering session context.
        """
        super().__init__(hostname, port, context_modules or [])

    async def __aenter__(self) -> "D3AsyncSession":
        """Enter async context manager and register all context modules.

        Returns:
            The session instance.

        Raises:
            RuntimeError: If any context module is not registered with @d3function.
        """
        for module_name in self.context_modules:
            is_registered: bool = await self.register_module(module_name)
            if not is_registered:
                raise RuntimeError(
                    f"module {module_name} is not registered with d3function"
                )
        return self

    async def __aexit__(self, _exc_type, _exc, _tb) -> None:
        """Exit async context manager."""
        pass

    async def request(
        self,
        method: Method,
        url_endpoint: str,
        **kwargs: Unpack[aiohttp.client._RequestOptions],
    ) -> Any:
        """Make a generic HTTP request to Designer API asynchronously.

        Args:
            method: HTTP method to use.
            url_endpoint: The API endpoint path.
            **kwargs: Additional arguments to pass to aiohttp session.request.

        Returns:
            JSON response from the API.
        """
        return await d3_api_arequest(
            method, self.hostname, self.port, url_endpoint, **kwargs
        )

    async def rpc(
        self, payload: PluginPayload[RetType], timeout_sec: float | None = None
    ) -> RetType:
        """Execute a remote procedure call asynchronously and return only the return value.

        Args:
            payload: Plugin payload containing script and optional module name.
            timeout_sec: Optional timeout in seconds for the request.

        Returns:
            The return value from the plugin execution.

        Raises:
            PluginException: If the plugin execution fails.
        """
        return (await self.plugin(payload, timeout_sec)).returnValue

    async def plugin(
        self, payload: PluginPayload[RetType], timeout_sec: float | None = None
    ) -> PluginResponse[RetType]:
        """Execute a plugin script on Designer asynchronously.

        Args:
            payload: Plugin payload containing script and optional module name.
            timeout_sec: Optional timeout in seconds for the request.

        Returns:
            PluginResponse containing status, logs, and return value.

        Raises:
            PluginException: If the plugin execution fails.
        """
        return await d3_api_aplugin(self.hostname, self.port, payload, timeout_sec)

    async def register_module(
        self, module_name: str, timeout_sec: float | None = None
    ) -> bool:
        """Register a module with Designer asynchronously.

        Args:
            module_name: Name of the module to register.
            timeout_sec: Optional timeout in seconds for the request.

        Returns:
            True if module was registered successfully, False if module not found.

        Raises:
            PluginException: If module registration fails on Designer side.
        """
        payload: RegisterPayload | None = D3Function.get_module_register_payload(
            module_name
        )
        if payload:
            await d3_api_aregister_module(
                self.hostname, self.port, payload, timeout_sec
            )
            return True
        return False

    async def register_all_modules(
        self, timeout_sec: float | None = None
    ) -> dict[str, bool]:
        """Register all modules decorated with @d3function asynchronously.

        Args:
            timeout_sec: Optional timeout in seconds for each registration request.

        Returns:
            Dictionary mapping module names to registration success status.

        Raises:
            PluginException: If any module registration fails on Designer side.
        """
        modules: list[str] = list(D3Function._available_d3functions.keys())
        register_success: dict[str, bool] = {}
        for module_name in modules:
            is_registered: bool = await self.register_module(module_name, timeout_sec)
            register_success[module_name] = is_registered
        return register_success

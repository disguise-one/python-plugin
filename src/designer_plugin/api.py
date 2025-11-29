"""
MIT License
Copyright (c) 2025 Disguise Technologies ltd
"""

import logging
from enum import StrEnum
from typing import Any, Unpack

import aiohttp
import requests
from pydantic import ValidationError

from designer_plugin.models import (
    D3_PLUGIN_ENDPOINT,
    D3_PLUGIN_MODULE_REG_ENDPOINT,
    PluginError,
    PluginException,
    PluginPayload,
    PluginRegisterResponse,
    PluginResponse,
    RegisterPayload,
    RetType,
)

logger: logging.Logger = logging.getLogger(__name__)

###############################################################################
# Plugin endpoint constants
def get_plugin_endpoint_url(hostname: str, port: int) -> str:
    """Get the full URL for the plugin execution endpoint.

    Args:
        hostname: The hostname of the Designer instance.
        port: The port number of the Designer instance.

    Returns:
        Full HTTP URL for plugin execution endpoint.
    """
    return f"http://{hostname}:{port}/{D3_PLUGIN_ENDPOINT}"


def get_plugin_module_register_url(hostname: str, port: int) -> str:
    """Get the full URL for the module registration endpoint.

    Args:
        hostname: The hostname of the Designer instance.
        port: The port number of the Designer instance.

    Returns:
        Full HTTP URL for module registration endpoint.
    """
    return f"http://{hostname}:{port}/{D3_PLUGIN_MODULE_REG_ENDPOINT}"


###############################################################################
# Low level request
class Method(StrEnum):
    GET = "GET"
    OPTIONS = "OPTIONS"
    HEAD = "HEAD"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


def d3_api_request(
    method: Method,
    hostname: str,
    port: int,
    url_endpoint: str,
    **kwargs,
) -> Any:
    """Make a synchronous HTTP request to Designer API.

    Args:
        method: HTTP method to use.
        hostname: The hostname of the Designer instance.
        port: The port number of the Designer instance.
        url_endpoint: The API endpoint path.
        **kwargs: Additional arguments to pass to requests.request.

    Returns:
        JSON response from the API.
    """
    url: str = f"http://{hostname}:{port}/{url_endpoint.lstrip('/')}"
    response = requests.request(
        method,
        url,
        **kwargs,
    )
    return response.json()


async def d3_api_arequest(
    method: Method,
    hostname: str,
    port: int,
    url_endpoint: str,
    **kwargs: Unpack[aiohttp.client._RequestOptions],
) -> Any:
    """Make an asynchronous HTTP request to Designer API.

    Args:
        method: HTTP method to use.
        hostname: The hostname of the Designer instance.
        port: The port number of the Designer instance.
        url_endpoint: The API endpoint path.
        **kwargs: Additional arguments to pass to aiohttp session.request.

    Returns:
        JSON response from the API.
    """
    url: str = f"http://{hostname}:{port}/{url_endpoint.lstrip('/')}"
    async with aiohttp.ClientSession() as session:
        async with session.request(
            method,
            url,
            **kwargs,
        ) as response:
            return await response.json()


###############################################################################
# API async interface
async def d3_api_aplugin(
    hostname: str,
    port: int,
    payload: PluginPayload[RetType],
    timeout_sec: float | None = None,
) -> PluginResponse[RetType]:
    """Execute a plugin script asynchronously on Designer with type-safe payload.

    Args:
        hostname: The hostname of the Designer instance.
        port: The port number of the Designer instance.
        payload: PluginPayload containing script and optional module name.
        timeout_sec: Optional timeout in seconds for the request.

    Returns:
        PluginResponse with typed return value.

    Raises:
        PluginException: If the plugin execution fails.
    """
    logger.debug(f"Send plugin api:{payload.debug_string()}")
    response: Any = await d3_api_arequest(
        Method.POST,
        hostname,
        port,
        D3_PLUGIN_ENDPOINT,
        json=payload.model_dump(),
        timeout=aiohttp.ClientTimeout(timeout_sec) if timeout_sec else None,
    )
    try:
        plugin_response: PluginResponse[RetType] = PluginResponse[RetType].model_validate(response)

        if plugin_response.pythonLog:
            print(plugin_response.pythonLog)
        logger.debug(f"PluginResponse:{plugin_response.debug_string()}")

        return plugin_response
    except ValidationError:
        error_response: PluginError = PluginError.model_validate(response)
        raise PluginException(
            status=error_response.status,
            d3Log=error_response.d3Log,
            pythonLog=error_response.pythonLog,
        ) from None


async def d3_api_aregister_module(
    hostname: str, port: int, payload: RegisterPayload, timeout_sec: float | None = None
) -> PluginRegisterResponse:
    """Register a module asynchronously with Designer.

    Args:
        hostname: The hostname of the Designer instance.
        port: The port number of the Designer instance.
        payload: RegisterPayload containing module name and contents.
        timeout_sec: Optional timeout in seconds for the request.

    Returns:
        PluginRegisterResponse confirming successful registration.

    Raises:
        Exception: If the network request fails.
        PluginException: If module registration fails on Designer side.
    """
    try:
        # logger.debug(f"Register module: {payload.moduleName}\n{payload.contents}")
        logger.debug(f"Register module:{payload.debug_string()}")
        response: Any = await d3_api_arequest(
            Method.POST,
            hostname,
            port,
            D3_PLUGIN_MODULE_REG_ENDPOINT,
            json=payload.model_dump(),
            timeout=aiohttp.ClientTimeout(timeout_sec) if timeout_sec else None,
        )
    except Exception as e:
        raise Exception(f"Failed to register module '{payload.moduleName}") from e

    plugin_response: PluginRegisterResponse = PluginRegisterResponse.model_validate(
        response
    )

    # if we fail to register module, all d3functions plugin will fail.
    # therefore, we should raise exception
    if plugin_response.status.code != 0:
        raise PluginException(status=plugin_response.status)

    return plugin_response


###############################################################################
# API sync interface
def d3_api_plugin(
    hostname: str,
    port: int,
    payload: PluginPayload[RetType],
    timeout_sec: float | None = None,
) -> PluginResponse[RetType]:
    """Execute a plugin script synchronously on Designer with type-safe payload.

    Args:
        hostname: The hostname of the Designer instance.
        port: The port number of the Designer instance.
        payload: PluginPayload containing script and optional module name.
        timeout_sec: Optional timeout in seconds for the request.

    Returns:
        PluginResponse with typed return value.

    Raises:
        PluginException: If the plugin execution fails.
    """

    logger.debug(f"Send plugin api:{payload.debug_string()}")
    response = d3_api_request(
        Method.POST,
        hostname,
        port,
        D3_PLUGIN_ENDPOINT,
        json=payload.model_dump(),
        timeout=timeout_sec if timeout_sec else None,
    )

    try:
        plugin_response: PluginResponse[RetType] = PluginResponse[RetType].model_validate(response)

        if plugin_response.pythonLog:
            print(plugin_response.pythonLog)
        logger.debug(f"PluginResponse:{plugin_response.debug_string()}")

        return plugin_response
    except ValidationError:
        error_response: PluginError = PluginError.model_validate(response)
        raise PluginException(
            status=error_response.status,
            d3Log=error_response.d3Log,
            pythonLog=error_response.pythonLog,
        ) from None


def d3_api_register_module(
    hostname: str,
    port: int,
    payload: RegisterPayload,
    timeout_sec: float | None = None,
) -> PluginRegisterResponse:
    """Register a module synchronously with Designer.

    Args:
        hostname: The hostname of the Designer instance.
        port: The port number of the Designer instance.
        payload: RegisterPayload containing module name and contents.
        timeout_sec: Optional timeout in seconds for the request.

    Returns:
        PluginRegisterResponse confirming successful registration.

    Raises:
        Exception: If the network request fails.
        PluginException: If module registration fails on Designer side.
    """
    try:
        logger.debug(f"Register module:{payload.debug_string()}")
        response: Any = d3_api_request(
            Method.POST,
            hostname,
            port,
            D3_PLUGIN_MODULE_REG_ENDPOINT,
            json=payload.model_dump(),
            timeout=timeout_sec if timeout_sec else None,
        )
    except Exception as e:
        raise Exception(f"Failed to register module: {payload.moduleName}") from e

    plugin_response: PluginRegisterResponse = PluginRegisterResponse.model_validate(
        response
    )

    # if we fail to register module, all d3functions plugin will fail.
    # therefore, we should raise exception
    if plugin_response.status.code != 0:
        raise PluginException(status=plugin_response.status)

    return plugin_response

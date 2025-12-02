"""
MIT License
Copyright (c) 2025 Disguise Technologies ltd
"""

import ast
import functools
import inspect
import logging
import types
from collections.abc import Callable
from contextlib import asynccontextmanager, contextmanager
from typing import Any, ParamSpec, TypeVar

from designer_plugin.api import (
    d3_api_aplugin,
    d3_api_aregister_module,
    d3_api_plugin,
    d3_api_register_module,
)
from designer_plugin.d3sdk.ast_utils import (
    convert_class_to_py27,
    filter_base_classes,
    filter_init_args,
    get_class_node,
    get_source,
    validate_and_extract_args,
)
from designer_plugin.models import (
    D3_PLUGIN_DEFAULT_PORT,
    PluginPayload,
    PluginResponse,
    RegisterPayload,
)

logger = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


def build_payload(
    self: Any, method_name: str, args: tuple[Any, ...], kwargs: dict[str, Any]
) -> PluginPayload[Any]:
    """Build plugin payload for remote method execution.

    Args:
        self: The plugin client instance.
        method_name: Name of the method to execute remotely.
        args: Positional arguments for the method.
        kwargs: Keyword arguments for the method.

    Returns:
        PluginPayload containing the script to execute remotely.
    """
    # Serialize arguments to string representation for remote execution
    args_parts: list[str] = [repr(arg) for arg in args]
    kwargs_parts: list[str] = [f"{key}={repr(value)}" for key, value in kwargs.items()]
    all_args: str = ", ".join(args_parts + kwargs_parts)

    # Build the Python script that will execute remotely on Designer
    script = f"return plugin.{method_name}({all_args})"

    # Create payload containing script and module info
    return PluginPayload[Any](moduleName=self.module_name, script=script)


def session_runtime_error_message(class_name: str) -> str:
    return f"""\
{class_name} is not in an active session.

Usage:
    with plugin.session('localhost', 80):
        plugin.your_method()
"""


def create_d3_plugin_method_wrapper(
    method_name: str, original_method: Callable[P, T]
) -> Callable[..., Any]:
    """Create a wrapper that executes a method remotely via Designer API calls.

    This wrapper intercepts method calls and instead of executing locally:
    1. Validates arguments against the original method signature
    2. Serializes the arguments using repr()
    3. Builds a script string in the form: "return plugin.{method_name}({args})"
    4. Creates a PluginPayload with the script and module information
    5. Sends it to Designer via d3_api_plugin or d3_api_aplugin
    6. Returns the result from the remote execution

    Args:
        method_name: Name of the method to wrap
        original_method: The original method object (used for type hints and async detection)

    Returns:
        An async wrapper if the original method is async, otherwise a sync wrapper.
        Both wrappers preserve the original method's metadata and signature validation.
    """
    # Get the signature for argument validation
    sig = inspect.signature(original_method)

    # Determine whether to create async or sync wrapper based on original method
    if inspect.iscoroutinefunction(original_method):
        # Create async wrapper that uses async Designer API call
        @functools.wraps(original_method)
        async def async_wrapper(self, *args, **kwargs):  # type: ignore
            positional, keyword = validate_and_extract_args(
                sig, True, (self,) + args, kwargs
            )
            if not self.in_session():
                raise RuntimeError(
                    session_runtime_error_message(self.__class__.__name__)
                )
            payload = build_payload(self, method_name, positional, keyword)
            response: PluginResponse[T] = await d3_api_aplugin(
                self._hostname, self._port, payload
            )
            return response.returnValue

        return async_wrapper
    else:
        # Create sync wrapper that uses synchronous Designer API call
        @functools.wraps(original_method)
        def sync_wrapper(self, *args, **kwargs):  # type: ignore
            positional, keyword = validate_and_extract_args(
                sig, True, (self,) + args, kwargs
            )
            if not self.in_session():
                raise RuntimeError(
                    session_runtime_error_message(self.__class__.__name__)
                )
            payload = build_payload(self, method_name, positional, keyword)
            response: PluginResponse[T] = d3_api_plugin(
                self._hostname, self._port, payload
            )
            return response.returnValue

        return sync_wrapper


def create_d3_payload_wrapper(
    method_name: str, original_method: Callable[P, T]
) -> Callable[..., PluginPayload[T]]:
    """Create a wrapper that generates plugin payload without executing.

    Args:
        method_name: Name of the method to wrap.
        original_method: The original method object for type hints.

    Returns:
        Wrapper function that returns PluginPayload instead of executing remotely.
    """

    @functools.wraps(original_method)
    def sync_wrapper(self, *args, **kwargs) -> PluginPayload[T]:  # type: ignore
        return build_payload(self, method_name, args, kwargs)

    return sync_wrapper


class D3PluginClientMeta(type):
    """Metaclass for Designer plugin clients that enables remote method execution.

    This metaclass intercepts class creation to perform several transformations:

    1. Source Code Extraction:
       - Extracts the source code of the class being defined using frame inspection
       - Parses it into an AST for manipulation

    2. Code Filtering:
       - Removes client-side-only class variables (e.g., module_name)
       - Filters out client-side-only __init__ parameters (hostname, port)

    3. Python 2.7 Conversion:
       - Converts async methods to sync for Designer's Python 2.7 runtime
       - Generates both Python 3 and Python 2.7 versions of the source code

    4. Method Wrapping:
       - Wraps all user-defined methods to execute remotely via Designer API
       - Preserves async/sync nature of original methods

    5. Code Generation:
       - Creates templates for instantiating the plugin on the remote side
       - Stores metadata needed for module registration

    Class Attributes (set dynamically on subclasses):
        filtered_init_args: List of __init__ parameter names after filtering
        source_code: Python 3 source code with filtered variables
        source_code_py27: Python 2.7 compatible source code
        module_name: Name used to register the module with Designer
        instance_code_template: Template string for instantiating the plugin remotely
        instance_code: Actual instantiation code with concrete argument values
    """

    # Type hints for dynamically set class attributes
    filtered_init_args: list[str]
    source_code: str
    source_code_py27: str
    module_name: str
    instance_code_template: str
    instance_code: str

    def __new__(cls, name: str, bases: tuple[type, ...], attrs: dict[str, Any]) -> type:
        # Skip the base class
        if name == "D3PluginClient":
            return super().__new__(cls, name, bases, attrs)

        # Use class name as default module_name if not explicitly provided
        attrs["module_name"] = name

        # Get the caller's frame (where the class is being defined in user code)
        frame: types.FrameType | None = inspect.currentframe()
        if not frame:
            raise ValueError(
                f"D3PluginClientMeta: Failed to extract source code for {name}"
            )

        caller_frame = frame.f_back
        if not caller_frame:
            raise ValueError(
                f"D3PluginClientMeta: Failed to extract source code for {name}"
            )

        # Extract full source code from the calling frame's file
        source_code: str | None = get_source(caller_frame)
        if not source_code:
            raise ValueError(
                f"D3PluginClientMeta: Failed to extract source code for {name}"
            )

        # Parse source code into Abstract Syntax Tree for manipulation
        tree: ast.Module = ast.parse(source_code)

        # Locate the specific class definition node within the AST
        class_node: ast.ClassDef | None = get_class_node(tree, name)
        if not class_node:
            raise ValueError(
                f"D3PluginClientMeta: Failed to find class definition for {name}"
            )

        # Remove all base class for now as we don't support inheritance
        filter_base_classes(class_node)

        # Filter out client-side-only __init__ arguments and get remaining params
        filtered_init_args: list[str] = filter_init_args(class_node)
        formated_filtered_init_args: list[str] = [
            f"{{{arg}}}" for arg in filtered_init_args
        ]

        # Unparse modified AST back to Python 3 source code (clean, no comments)
        attrs["source_code"] = f"{ast.unparse(class_node)}"
        # Create template for instantiating the plugin remotely with placeholders
        attrs["instance_code_template"] = (
            f"plugin = {name}({','.join(formated_filtered_init_args)})"
        )
        attrs["filtered_init_args"] = filtered_init_args

        # Convert async methods to Python 2.7 compatible sync methods
        convert_class_to_py27(class_node)
        attrs["source_code_py27"] = f"{ast.unparse(class_node)}"

        # Wrap all user-defined public methods to execute remotely via D3 API
        # Skip internal framework methods
        for attr_name, attr_value in attrs.items():
            if callable(attr_value) and not attr_name.startswith("__"):
                attrs[attr_name] = create_d3_plugin_method_wrapper(
                    attr_name, attr_value
                )

        return super().__new__(cls, name, bases, attrs)

    def __call__(cls, *args, **kwargs):  # type: ignore
        """Create an instance and generate its remote instantiation code.

        This method is called when a class instance is created (e.g., MyPlugin(...)).
        It maps the provided arguments to the filtered parameter names and generates
        the instance_code that will be used to instantiate the plugin remotely.

        Args:
            *args: Positional arguments for the plugin __init__
            **kwargs: Keyword arguments for the plugin __init__

        Returns:
            An instance of the plugin class with instance_code attribute set
        """
        # Build mapping from parameter names to their repr() values for remote instantiation
        param_names: list[str] = cls.filtered_init_args
        arg_mapping: dict[str, str] = {}

        # Map positional arguments
        for i, param_name in enumerate(param_names):
            filtered_idx = i  # Account for excluded client-side args
            if filtered_idx < len(args):
                arg_mapping[param_name] = repr(args[filtered_idx])

        # Map keyword arguments that match filtered parameter names
        for key, value in kwargs.items():
            if key in param_names:
                arg_mapping[key] = repr(value)

        # Replace placeholders in template with actual serialized argument values
        instance_code: str = cls.instance_code_template.format(**arg_mapping)

        # Create the actual client instance with all original arguments
        instance = super().__call__(*args, **kwargs)

        # Attach the generated instance_code for use during module registration
        instance.instance_code = instance_code

        return instance


class D3PluginClient(metaclass=D3PluginClientMeta):
    """Base class for creating Designer plugin clients.

    This class provides the foundation for building plugins that execute remotely
    on Designer. When you subclass D3PluginClient, the metaclass automatically:
    - Extracts and processes your class source code
    - Converts it to Python 2.7 compatible code
    - Wraps all your methods to execute remotely
    - Manages module registration with Designer

    Usage:
    ```python
    from typing import TYPE_CHECKING
    if TYPE_CHECKING:
        from d3blobgen.scripts.d3 import *

    class MyPlugin(D3PluginClient):
        def __init__(self, arg1: int, arg2: str):
            # Passed argument will be cached and used on register
            self.arg1: int = arg1
            self.arg2: str = arg2

        def get_surface_uid(self, surface_name: str) -> dict[str, str]:
            surface: Screen2 = resourceManager.load(
                Path('objects/screen2/{}.apx'.format(surface_name)),
                Screen2
            )
            return {
                "name": surface.description,
                "uid": surface.uid,
            }

    # Instantiate MyPlugin
    plugin = MyPlugin(1, "myplugin")

    # Use as sync context manager
    with plugin.session("localhost", 80):
        result = plugin.get_surface_uid("surface 1")
    ```
    Attributes:
        instance_code: The code used to instantiate the plugin remotely (set on init)
    """

    def __init__(self) -> None:
        self._hostname: str | None = None
        self._port: int | None = None
        self._override_module_name: str | None = None

    def in_session(self) -> bool:
        """Check if the client is currently in an active session.

        Returns:
            True if both hostname and port are set, False otherwise.
        """
        return bool(self._hostname) and bool(self._port)

    @asynccontextmanager
    async def async_session(  # type: ignore
        self,
        hostname: str,
        port: int = D3_PLUGIN_DEFAULT_PORT,
        register_module: bool = True,
        module_name: str | None = None,
    ):
        """Async context manager for plugin session with Designer.

        Args:
            hostname: The hostname of the Designer instance.
            port: The port number of the Designer instance.
            register_module: Whether to register the module. Set to False when the
                module has already been registered with Designer.
            module_name: Optional module name to override the default.

        Yields:
            The plugin client instance with active session.
        """
        try:
            if module_name:
                self._override_module_name = module_name

            self._hostname = hostname
            self._port = port
            if register_module:
                await self._aregister(hostname, port)
            logger.debug("Entering D3PluginModule context")
            yield self
        finally:
            self._hostname = None
            self._port = None
            self._override_module_name = None
            logger.debug("Exiting D3PluginModule context")

    @contextmanager
    def session(  # type: ignore
        self,
        hostname: str,
        port: int = D3_PLUGIN_DEFAULT_PORT,
        register_module: bool = True,
        module_name: str | None = None,
    ):
        """Sync context manager for plugin session with Designer.

        Args:
            hostname: The hostname of the Designer instance.
            port: The port number of the Designer instance.
            register_module: Whether to register the module.
                Set to False when the module has already been registered with Designer.
            module_name: Optional module name to override the default.

        Yields:
            The plugin client instance with active session.
        """
        try:
            if module_name:
                self._override_module_name = module_name

            self._hostname = hostname
            self._port = port
            if register_module:
                self._register(hostname, port)
            logger.debug("Entering D3PluginModule context")
            yield self
        finally:
            self._hostname = None
            self._port = None
            self._override_module_name = None
            logger.debug("Exiting D3PluginModule context")

    async def _aregister(self, hostname: str, port: int) -> None:
        """Register the plugin module with Designer asynchronously.

        Args:
            hostname: The hostname of the Designer instance.
            port: The port number of the Designer instance.
        """
        await d3_api_aregister_module(
            hostname, port, self._get_register_module_payload()
        )

    def _register(self, hostname: str, port: int) -> None:
        """Register the plugin module with Designer synchronously.

        Args:
            hostname: The hostname of the Designer instance.
            port: The port number of the Designer instance.
        """
        d3_api_register_module(hostname, port, self._get_register_module_payload())

    def _get_register_module_content(self) -> str:
        """Generate the complete module content to register with Designer.

        Returns:
            String containing the full module code to execute on Designer.
        """
        return f"{self.source_code_py27}\n\n{self.instance_code}"  # type: ignore[attr-defined]

    def _get_register_module_payload(self) -> RegisterPayload:
        """Build the module registration payload for Designer.

        Returns:
            RegisterPayload containing moduleName and contents for registration.
        """
        module_name: str = self._override_module_name or self.module_name  # type: ignore[attr-defined]
        return RegisterPayload(
            moduleName=module_name,
            contents=self._get_register_module_content(),
        )

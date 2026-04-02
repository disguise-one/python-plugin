"""
MIT License
Copyright (c) 2025 Disguise Technologies ltd
"""

import ast
import functools
import inspect
import logging
import textwrap
from collections import defaultdict
from collections.abc import Callable
from typing import Any, Generic, ParamSpec, TypeVar

from pydantic import BaseModel, Field

from designer_plugin.d3sdk.ast_utils import (
    PackageInfo,
    convert_function_to_py27,
    find_imports_for_function,
    validate_and_bind_signature,
    validate_and_extract_args,
)
from designer_plugin.models import (
    PluginPayload,
    RegisterPayload,
)

logger = logging.getLogger(__name__)


###############################################################################
# Plugin function related implementations
class FunctionInfo(BaseModel):
    """Container for parsed function information extracted from Python source code.

    This model holds all the essential components of a function after parsing,
    including its complete definition, name, body statements, and argument list.
    """

    source_code: str = Field(
        description="full body of function blob without decorator (Function definition + body)"
    )
    source_code_py27: str = Field(
        description="full body of function blob without decorator in python2.7 format (Function definition + body)"
    )
    name: str = Field(description="name of extracted function")
    body: str = Field(description="body of extracted function in str format")
    body_py27: str = Field(
        description="body of extracted function in python2.7 str format"
    )
    args: list[str] = Field(
        default=[], description="list of arguments from extracted function"
    )
    packages: list[PackageInfo] = Field(
        default=[], description="list of packages/imports used by the function"
    )


def extract_function_info(func: Callable[..., Any]) -> FunctionInfo:
    """Parse function source code and extract name, body statements, and argument list.

    This function uses AST parsing to extract function information from the source code
    of a callable Python function. It removes decorators and provides the clean function
    definition along with parsed components.

    Args:
        func: A callable Python function to analyse.

    Returns:
        FunctionInfo: Object containing function name, body code, and argument names.

    Raises:
        ValueError: If the input is not a function or cannot be parsed.
    """

    source_code = inspect.getsource(func)
    # Remove common leading whitespace to handle functions defined with indentation
    source_code = textwrap.dedent(source_code)
    tree: ast.Module = ast.parse(source_code)

    # Check if first node exists and is a function
    if not tree.body:
        raise ValueError(f"Given input is not a function\ninput:{source_code}")

    first_node = tree.body[0]
    if not isinstance(first_node, ast.FunctionDef) and not isinstance(
        first_node, ast.AsyncFunctionDef
    ):
        raise ValueError(f"Given input is not a function\ninput:{source_code}")

    # Extract function blob without decorator
    first_node.decorator_list.clear()

    # Extract blob in python 3 format
    source_code_py3: str = ast.unparse(first_node)

    # Extract function name
    function_name: str = first_node.name

    # Extract body statements
    body_nodes: list[ast.stmt] = first_node.body

    # Convert back to source code
    body: str = ""
    for stmt in body_nodes:
        body += ast.unparse(stmt) + "\n"

    # Extract function arguments
    sig: inspect.Signature = inspect.signature(func)
    args: list[str] = list(sig.parameters.keys())

    first_node_py27 = convert_function_to_py27(first_node)
    source_code_py27: str = ast.unparse(first_node_py27)

    body_nodes_py27: list[ast.stmt] = first_node_py27.body
    body_py27: str = ""
    for stmt in body_nodes_py27:
        body_py27 += ast.unparse(stmt) + "\n"

    packages = find_imports_for_function(func)

    return FunctionInfo(
        source_code=source_code_py3,
        source_code_py27=source_code_py27,
        name=function_name,
        body=body.strip(),
        body_py27=body_py27.strip(),
        args=args,
        packages=packages,
    )


P = ParamSpec("P")
T = TypeVar("T")


class D3PythonScript(Generic[P, T]):
    """Wrapper for standalone Designer script execution using the @d3pythonscript decorator.

    The function body is inlined with argument assignments into a single script payload,
    so no module registration is required before execution.

    Examples:
        ```python
        from designer_plugin.d3sdk import d3pythonscript, D3Session
        from designer_plugin.pystub import *

        @d3pythonscript
        def rename_surface(surface_name: str, new_name: str):
            surface: Screen2 = resourceManager.load(
                Path(f'objects/screen2/{surface_name}.apx'), Screen2)
            surface.rename(surface.path.replaceFilename(new_name))

        with D3Session('localhost', 80) as session:
            session.rpc(rename_surface.payload("surface 1", "surface 2"))
        ```
    """

    def __init__(self, func: Callable[P, T]):
        """Initialise a D3PythonScript wrapper around a Python function.

        Args:
            func: The Python function to wrap for execution within Designer.
        """
        self._function: Callable[P, T] = func
        self._function_info: FunctionInfo = extract_function_info(func)

        # Update wrapper to preserve function metadata for IDE
        functools.update_wrapper(self, func)

    @property
    def __signature__(self) -> inspect.Signature:
        """Expose function signature for IDE introspection.

        Returns:
            The signature of the wrapped function for IDE support.
        """
        return inspect.signature(self._function)

    @property
    def function_info(self) -> FunctionInfo:
        """Get the parsed function information.

        Returns:
            FunctionInfo object containing parsed details about the wrapped function.
        """
        return self._function_info

    @property
    def name(self) -> str:
        """Get the name of the wrapped function.

        Returns:
            The name of the wrapped function.
        """
        return self._function_info.name

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> T:
        return self._function(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        """Proxy attribute access to the original function for IDE support.

        Args:
            name: The attribute name to retrieve from the wrapped function.

        Returns:
            The attribute value from the wrapped function.
        """
        return getattr(self._function, name)

    def _args_to_assign(self, *args: Any, **kwargs: Any) -> str:
        """Convert function arguments to assignment statements for standalone execution.

        Args:
            *args: Positional arguments to convert.
            **kwargs: Keyword arguments to convert.

        Returns:
            String containing variable assignment statements, one per line.

        Raises:
            TypeError: If arguments don't match the function signature.
        """
        sig: inspect.Signature = inspect.signature(self._function)
        positional, keyword_args = validate_and_extract_args(sig, False, args, kwargs)

        # Create assignment strings for positional arguments using parameter names from signature
        param_names = list(sig.parameters.keys())
        assignments = [
            f"{param_names[i]}={repr(arg)}" for i, arg in enumerate(positional)
        ]

        kwargs_parts = [f"{name}={repr(value)}" for name, value in keyword_args.items()]
        return "\n".join(assignments + kwargs_parts)

    def payload(self, *args: P.args, **kwargs: P.kwargs) -> PluginPayload[T]:
        """Generate an execution payload for standalone script execution.

        Creates a payload by inlining the function body with argument assignments.

        Args:
            *args: Positional arguments to pass to the function.
            **kwargs: Keyword arguments to pass to the function.

        Returns:
            PluginPayload containing the script with argument assignments and function body.

        Raises:
            TypeError: If arguments don't match the function signature.
        """
        all_args: str = self._args_to_assign(*args, **kwargs)
        return PluginPayload[T](script=f"{all_args}\n{self._function_info.body_py27}")


class D3Function(D3PythonScript[P, T]):
    """Wrapper class for Python functions to be executed in Designer environment.

    This class transforms regular Python functions into Designer plugin compatible functions
    that can be registered as modules and executed remotely. Unlike D3PythonScript which
    inlines function bodies, D3Function registers the complete function definition as part
    of a module, allowing efficient reuse across multiple executions.

    Class Attributes:
        _available_packages: Registry mapping module names to their required import packages.
        _available_d3functions: Registry mapping module names to their D3Function instances.

    Examples:
        ```python
        from designer_plugin.d3sdk import d3function, D3Session
        from designer_plugin.pystub import *

        @d3function("surface_utils")
        def get_surface_uid(surface_name: str) -> str:
            surface: Screen2 = resourceManager.load(
                Path(f'objects/screen2/{surface_name}.apx'), Screen2)
            return str(surface.uid)

        # "surface_utils" module is auto-registered on first execute
        with D3Session('localhost', 80) as session:
            uid = session.rpc(get_surface_uid.payload("surface 1"))
        ```
    """

    _available_packages: defaultdict[str, set[str]] = defaultdict(set)
    _available_d3functions: defaultdict[str, set["D3Function"]] = defaultdict(set)

    def __init__(self, module_name: str, func: Callable[P, T]):
        """Initialise a D3Function wrapper around a Python function.

        Registers the function in the module's function registry for later module registration.

        Args:
            module_name: Name of the module to register this function under.
            func: The Python function to wrap for execution in Designer.
        """
        # Add this function into available_d3_functions
        self._module_name: str = module_name

        super().__init__(func)

        # Update the function in case the function was updated in the same session.
        # For example, jupyter notebook server can be running, but function signature can
        # change constantly.
        is_replacement = self in D3Function._available_d3functions[module_name]
        if is_replacement:
            logger.debug(
                "Function '%s' in module '%s' is being replaced.",
                self.name,
                module_name,
            )
            D3Function._available_d3functions[module_name].discard(self)
        D3Function._available_d3functions[module_name].add(self)

        if is_replacement:
            # Full rebuild needed to evict stale imports from the replaced function.
            D3Function._available_packages[module_name] = {
                pkg.to_import_statement()
                for f in D3Function._available_d3functions[module_name]
                for pkg in f._function_info.packages
            }
        else:
            # New function: incrementally add its packages. No stale imports to remove.
            D3Function._available_packages[module_name].update(
                pkg.to_import_statement() for pkg in self._function_info.packages
            )

    def __eq__(self, other: object) -> bool:
        """Check equality based on function name for unique registration.

        Returns:
            True if both are D3Functions with the same name, False otherwise.
        """
        if not isinstance(other, D3Function):
            return False
        return self.name == other.name

    def __hash__(self) -> int:
        """Generate hash based on function name for unique registration.

        Returns:
            Hash value of the function name.
        """
        return hash(self.name)

    def get_register_payload(self) -> RegisterPayload | None:
        """Get the registration payload for this function's module.

        Returns:
            RegisterPayload for the module containing this function, or None if module not found.
        """
        return self.get_module_register_payload(self.module_name)

    @staticmethod
    def get_module_register_payload(module_name: str) -> RegisterPayload | None:
        """Generate a registration payload for all functions in a specific module.

        Combines all package imports and function definitions registered under the module name.

        Args:
            module_name: The name of the module to generate the payload for.

        Returns:
            RegisterPayload containing module name and combined package imports and function definitions,
            or None if the module has no registered functions.
        """
        if module_name not in D3Function._available_d3functions:
            return None

        contents_packages: str = "\n".join(
            sorted(D3Function._available_packages[module_name])
        )
        contents_functions: str = "\n\n".join(
            [
                func.function_info.source_code_py27
                for func in D3Function._available_d3functions[module_name]
            ]
        )
        return RegisterPayload(
            moduleName=module_name,
            contents=f"{contents_packages}\n\n{contents_functions}",
        )

    @property
    def module_name(self) -> str:
        """Get the module name this function is registered under.

        Returns:
            The module name for this function.
        """
        return self._module_name

    def _args_to_string(self, *args, **kwargs) -> str:  # type: ignore
        """Convert function arguments to a string representation for function call generation.

        Args:
            *args: Positional arguments to convert.
            **kwargs: Keyword arguments to convert.

        Returns:
            Comma-separated string representation of all arguments suitable for function calls.

        Raises:
            TypeError: If arguments don't match the function signature.
        """
        # Validate arguments against signature using shared utility
        sig = inspect.signature(self._function)
        validate_and_bind_signature(
            sig, *args, **kwargs
        )  # This validates and raises TypeError if invalid

        # Convert positional args
        args_parts = [repr(arg) for arg in args]
        # Convert keyword args
        kwargs_parts = [f"{key}={repr(value)}" for key, value in kwargs.items()]
        # Combine them
        all_parts = args_parts + kwargs_parts
        return f"{', '.join(all_parts)}"

    def payload(self, *args: P.args, **kwargs: P.kwargs) -> PluginPayload[T]:
        """Generate an execution payload for module-based function execution.

        Creates a payload that calls the registered function by name within its module.

        Args:
            *args: Positional arguments to pass to the function.
            **kwargs: Keyword arguments to pass to the function.

        Returns:
            PluginPayload containing the module name and script that calls the function by name.

        Raises:
            TypeError: If arguments don't match the function signature.
        """
        return PluginPayload[T](
            moduleName=self._module_name,
            script=f"return {self._function_info.name}({self._args_to_string(*args, **kwargs)})",
        )


###############################################################################
# d3function API
def d3pythonscript(func: Callable[P, T]) -> D3PythonScript[P, T]:
    """Decorator to wrap a Python function for standalone Designer script execution.

    This decorator transforms a regular Python function into a D3PythonScript that generates
    execution payloads for direct script execution in Designer. Unlike @d3function, this
    decorator does not register the function as a module and is intended for one-off script
    execution where the function body is inlined with the arguments.

    Args:
        func: The Python function to wrap.

    Returns:
        D3PythonScript instance that wraps the function and provides payload generation.

    Examples:
        ```python
        from designer_plugin.d3sdk import d3pythonscript, D3Session

        @d3pythonscript
        def my_add(a: int, b: int) -> int:
            return a + b

        # Generate payload for execution
        payload = my_add.payload(5, 3)
        # The payload.script will contain:
        # a=5
        # b=3
        # return a + b

        with D3Session('localhost', 80) as session:
            result = session.rpc(my_add.payload(5, 3))
            print(result)  # 8
        ```
    """
    return D3PythonScript(func)


# Actual implementation
def d3function(module_name: str = "") -> Callable[[Callable[P, T]], D3Function[P, T]]:
    """Decorator to wrap a Python function for Designer module registration and execution.

    This decorator transforms a regular Python function into a D3Function that can be registered
    as a reusable module in Designer and executed remotely. The decorated function is added to
    the module's function registry and can be called by name after module registration.

    Unlike @d3pythonscript which inlines the function body, @d3function registers the complete
    function definition as part of a module, allowing efficient reuse across multiple executions.

    Args:
        module_name: The module name to register this function under. This should be a unique
                    identifier for the module that will contain this function. Multiple functions
                    can share the same module_name to be registered together as a single module.

    Returns:
        A decorator function that wraps the target function in a D3Function instance.

    Examples:
        ```python
        from designer_plugin.d3sdk import d3function, D3Session
        from designer_plugin.pystub import *

        @d3function("my_d3module")
        def get_camera_uid(cam_name: str) -> str:
            camera = resourceManager.load(
                Path(f'objects/camera/{cam_name}.apx'),
                Camera
            )
            return str(camera.uid)

        # Generate payload for execution (calls the function by name)
        payload = get_camera_uid.payload("camera1")
        # payload.script == "return get_camera_uid('camera1')"

        # "my_d3module" is auto-registered when entering the session
        with D3Session('localhost', 80, ["my_d3module"]) as session:
            uid = session.rpc(get_camera_uid.payload("camera1"))
        ```
    """

    def decorator(func: Callable[P, T]) -> D3Function[P, T]:
        return D3Function(module_name, func)

    return decorator


def get_register_payload(module_name: str) -> RegisterPayload | None:
    """Get the registration payload for a specific module.

    Args:
        module_name: The name of the module to get the payload for.

    Returns:
        RegisterPayload for the module, or None if the module has no registered d3function.

    Examples:
        ```python
        payload = get_register_payload("mymodule")
        if payload:
            print(payload.contents)
        ```
    """
    return D3Function.get_module_register_payload(module_name)


def get_all_d3functions() -> list[tuple[str, str]]:
    """Retrieve all available d3function as module_name-function_name pairs.

    Returns:
        List of tuples containing (module_name, function_name) for all registered d3function.

    Examples:
        ```python
        functions = get_all_d3functions()
        # [("mymodule", "get_time"), ("mymodule", "get_surface_uid")]
        ```
    """
    module_function_pairs: list[tuple[str, str]] = []
    for module_name, funcs in D3Function._available_d3functions.items():
        module_function_pairs += [
            (module_name, func.function_info.name) for func in funcs
        ]
    return module_function_pairs


def get_all_modules() -> list[str]:
    """Retrieve names of all modules registered with @d3function decorator.

    Returns:
        List of module names that have registered d3function.

    Examples:
        ```python
        modules = get_all_modules()
        # ["mymodule", "surface_utils"]
        ```
    """
    return list(D3Function._available_d3functions.keys())

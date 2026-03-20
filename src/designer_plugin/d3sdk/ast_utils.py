"""
MIT License
Copyright (c) 2025 Disguise Technologies ltd
"""

import ast
import functools
import inspect
import logging
import textwrap
import types
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field

from designer_plugin.d3sdk.builtin_modules import SUPPORTED_MODULES

logger = logging.getLogger(__name__)


###############################################################################
# Package info models
class ImportAlias(BaseModel):
    """Represents a single imported name with an optional alias.

    Mirrors the structure of ast.alias for Pydantic compatibility.
    """

    name: str = Field(
        description="The imported name (e.g., 'Path' in 'from pathlib import Path')"
    )
    asname: str | None = Field(
        default=None,
        description="The alias (e.g., 'np' in 'import numpy as np')",
    )


class PackageInfo(BaseModel):
    """Structured representation of a Python import statement.

    Rendering rules (via to_import_statement using ast.unparse):
    - package only              → import package
    - package + alias           → import package as alias
    - package + methods         → from package import method1, method2
    - package + methods w/alias → from package import method1 as alias1
    """

    package: str = Field(description="The module/package name to import")
    alias: str | None = Field(
        default=None,
        description="Alias for the package (e.g., 'np' in 'import numpy as np')",
    )
    methods: list[ImportAlias] = Field(
        default_factory=list,
        description="Imported names for 'from X import ...' style imports",
    )

    def to_import_statement(self) -> str:
        """Render back to a Python import statement using ast.unparse."""
        node: ast.stmt
        if self.methods:
            node = ast.ImportFrom(
                module=self.package,
                names=[ast.alias(name=m.name, asname=m.asname) for m in self.methods],
                level=0,
            )
        else:
            node = ast.Import(names=[ast.alias(name=self.package, asname=self.alias)])
        return ast.unparse(node)


###############################################################################
# Source code extraction utilities
def get_source(frame: types.FrameType) -> str | None:
    """Extract and dedent source code from a frame object.

    Args:
        frame: The frame object to extract source code from

    Returns:
        Dedented source code as a string, or None if source cannot be found

    Raises:
        OSError: If the source file cannot be found or read
    """
    source_lines, _ = inspect.findsource(frame)
    return textwrap.dedent("".join(source_lines)) if source_lines else None


def get_class_node(tree: ast.Module, class_name: str) -> ast.ClassDef | None:
    """Find a class definition node by name in an AST.

    Args:
        tree: The AST tree to search
        class_name: The name of the class to find

    Returns:
        The ClassDef node if found, None otherwise
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return node
    return None


###############################################################################
# AST node filtering utilities
def filter_base_classes(class_node: ast.ClassDef) -> None:
    """Remove all base classes from a class definition for Python 2.7 compatibility.

    This function modifies the class_node in-place by clearing its base class list.
    Inheritance is not supported in the current Designer plugin system.

    Args:
        class_node: The class definition node to process
    """
    class_node.bases = []


def filter_init_args(class_node: ast.ClassDef) -> list[str]:
    """Extract parameter names from the __init__ method of a class.

    Args:
        class_node: The class definition node to process

    Returns:
        List of parameter names from __init__ (excluding 'self'), or empty list if no __init__ found
    """
    for node in class_node.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        if node.name != "__init__":
            continue

        # Return filtered parameter names (excluding 'self' which is implicit)
        return [arg.arg for arg in node.args.args if arg.arg != "self"]

    return []


###############################################################################
# Type hint removal utilities
class ConvertToPython27(ast.NodeTransformer):
    """AST transformer to convert Python 3 code to Python 2.7 compatible format.

    This transformer performs the following conversions:
    - Removes function return type annotations (def func() -> int)
    - Removes argument type annotations (def func(x: int))
    - Converts annotated assignments to regular assignments (x: int = 5 → x = 5)
    - Removes await keywords from async expressions (await func() → func())
    - Converts f-strings to .format() style (f"Hello {name}" → "Hello {}".format(name))
    """

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        """Remove return type annotation from function definitions.

        Transforms 'def func() -> int:' to 'def func():' for Python 2.7 compatibility.

        Args:
            node: The function definition AST node to transform.

        Returns:
            The function node without return type annotation.
        """
        node.returns = None
        self.generic_visit(node)
        return node

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.FunctionDef:
        """Convert async function to regular function for Python 2.7 compatibility.

        Transforms 'async def func() -> int:' to 'def func():' by:
        1. Creating a new FunctionDef node with the same properties
        2. Removing return type annotation via visit_FunctionDef
        3. Returning the FunctionDef to replace the AsyncFunctionDef in the AST

        Args:
            node: The async function definition AST node to transform.

        Returns:
            A regular FunctionDef node without async keyword or return type annotation.
        """
        # Build the replacement FunctionDef
        new = ast.FunctionDef(
            name=node.name,
            args=node.args,
            body=node.body,
            decorator_list=node.decorator_list,
            returns=node.returns,
            type_comment=getattr(node, "type_comment", None),
        )

        # Preserve source location
        new = ast.copy_location(new, node)

        # Now run normal FunctionDef logic + recurse
        return self.visit_FunctionDef(new)

    def visit_arg(self, node: ast.arg) -> ast.arg:
        """Remove type annotation from argument.

        Args:
            node: The argument AST node to transform.

        Returns:
            The argument node without type annotation.
        """
        node.annotation = None
        return node

    def visit_AnnAssign(self, node: ast.AnnAssign) -> ast.Assign | None:
        """Remove type hint.

        Converts type-annotated variable assignments (e.g., 'x: int = 5') into regular
        assignments (e.g., 'x = 5'). If the annotated assignment has no value (e.g., 'x: int'),
        it is removed entirely as Python 2.7 does not support variable declarations without values.

        Args:
            node: The annotated assignment AST node to transform.

        Returns:
            Regular Assign node without type annotation if value exists, None otherwise.
        """
        if node.value is None:
            return None

        return ast.Assign(
            targets=[node.target],
            value=self.visit(node.value),  # Recursively transform the value
            lineno=node.lineno,
            col_offset=node.col_offset,
        )

    def visit_Await(self, node: ast.Await) -> Any:
        """Remove await keyword.

        Remove await keyword and return the underlying expression.
        Transforms 'await expr()' to 'expr()'.

        Args:
            node: The await AST node to transform.

        Returns:
            The underlying expression without the await wrapper.
        """
        return self.visit(node.value)

    def visit_JoinedStr(self, node: ast.JoinedStr) -> ast.Call:
        # Don't use generic_visit here because we need to handle format_spec specially
        # Process the node values manually to preserve format specs

        fmt_parts = []
        args = []

        for value in node.values:
            # Literal pieces of the f-string
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                # Escape braces so they are not taken as format fields
                text = value.value.replace("{", "{{").replace("}", "}}")
                fmt_parts.append(text)

            # { … } expressions
            elif isinstance(value, ast.FormattedValue):
                placeholder = "{"

                # Handle !r / !s / !a
                if value.conversion != -1:
                    placeholder += "!" + chr(value.conversion)

                # Handle format specs, e.g. {x:.2f}
                if value.format_spec is not None:
                    # f-string format specs themselves are JoinedStr nodes
                    fspec = value.format_spec
                    if (
                        isinstance(fspec, ast.JoinedStr)
                        and len(fspec.values) == 1
                        and isinstance(fspec.values[0], ast.Constant)
                        and isinstance(fspec.values[0].value, str)
                    ):
                        placeholder += ":" + fspec.values[0].value
                    else:
                        # For more complex specs we could fall back, but let's keep it simple
                        pass

                placeholder += "}"
                fmt_parts.append(placeholder)

                # Transform the expression value (but not the format_spec)
                args.append(self.visit(value.value))

            else:
                # Unusual case for f-strings – just in case
                raise NotImplementedError(
                    f"Unsupported JoinedStr part: {ast.dump(value)}"
                )

        # Build "string".format(*args)
        fmt_str = ast.Constant("".join(fmt_parts))
        new_node = ast.Call(
            func=ast.Attribute(value=fmt_str, attr="format", ctx=ast.Load()),
            args=args,
            keywords=[],
        )
        return ast.copy_location(new_node, node)


###############################################################################
# Python 2.7 conversion utilities
def convert_function_to_py27(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> ast.FunctionDef:
    """Convert a function AST node to Python 2.7 compatible format.

    This function removes all type annotations from a function definition,
    including return type annotations, parameter type annotations, and
    type hints within the function body to ensure Python 2.7 compatibility.

    WARNING: This function modifies the input node in-place for FunctionDef nodes.
    For AsyncFunctionDef nodes, a new FunctionDef node is created.

    Args:
        function_node: The function AST node to convert to Python 2.7 format.
                      This node will be modified in-place if it's a FunctionDef.

    Returns:
        The converted FunctionDef node. For FunctionDef input, returns the same
        (modified) node. For AsyncFunctionDef input, returns a new FunctionDef node.
    """
    transformer = ConvertToPython27()
    return transformer.visit(function_node)  #  type: ignore


def convert_class_to_py27(class_node: ast.ClassDef) -> None:
    """Convert all methods in a class to Python 2.7 compatible format.

    This function modifies the class_node in-place by converting all function definitions
    (both sync and async) to Python 2.7 compatible format. This includes:
    1. Converting AsyncFunctionDef nodes to regular FunctionDef nodes
    2. Removing type annotations from all methods
    3. Recursively processing method bodies using convert_function_to_py27

    Args:
        class_node: The class definition node to convert
    """
    for i, node in enumerate(class_node.body):
        if isinstance(node, ast.AsyncFunctionDef) or isinstance(node, ast.FunctionDef):
            class_node.body[i] = convert_function_to_py27(node)


###############################################################################
# Signature validation utilities
def validate_and_bind_signature(
    sig: inspect.Signature, *args: Any, **kwargs: Any
) -> inspect.BoundArguments:
    """Validate arguments against a function signature and return bound arguments.

    This is a shared utility used by both D3PluginClient and D3PythonScript
    to ensure consistent argument validation across the codebase.

    Args:
        sig: The function signature to validate against
        *args: Positional arguments to validate
        **kwargs: Keyword arguments to validate

    Returns:
        BoundArguments object with validated and bound arguments

    Raises:
        TypeError: If arguments don't match the signature (too many args,
                  missing required args, unexpected kwargs, etc.)
    """
    bound_args = sig.bind(*args, **kwargs)
    bound_args.apply_defaults()
    return bound_args


def validate_and_extract_args(
    sig: inspect.Signature,
    exclude_self: bool,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> tuple[tuple[Any, ...], dict[str, Any]]:
    """Validate arguments and extract them into positional and keyword arguments.

    This is a shared utility that validates arguments against a signature and
    separates them into positional and keyword arguments for remote execution.

    Args:
        sig: The function signature to validate against
        exclude_self: If True, exclude 'self' parameter from extracted arguments
        args: Positional arguments to validate
        kwargs: Keyword arguments to validate

    Returns:
        Tuple of (positional_args, keyword_args) ready for remote execution

    Raises:
        TypeError: If arguments don't match the signature
    """
    # Validate arguments using shared validation utility
    bound_args = validate_and_bind_signature(sig, *args, **kwargs)

    # Extract arguments
    args_dict = dict(bound_args.arguments)
    if exclude_self:
        args_dict.pop("self", None)

    # Separate back into positional and keyword arguments
    positional = []
    keyword = {}
    for param_name, param in sig.parameters.items():
        if exclude_self and param_name == "self":
            continue
        if param_name in args_dict:
            if param.kind in (param.POSITIONAL_ONLY, param.POSITIONAL_OR_KEYWORD):
                positional.append(args_dict[param_name])
            elif param.kind == param.VAR_POSITIONAL:
                # Unpack *args into positional list
                positional.extend(args_dict[param_name])
            elif param.kind == param.VAR_KEYWORD:
                # Unpack **kwargs into keyword dict
                keyword.update(args_dict[param_name])
            else:
                # KEYWORD_ONLY parameters
                keyword[param_name] = args_dict[param_name]

    return tuple(positional), keyword


###############################################################################
# Function-scoped import extraction utility
def _collect_used_names(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """Collect all identifier names used inside a function body.

    Walks the function's AST body and extracts:
    - Simple names (ast.Name nodes, e.g., ``foo`` in ``foo()``)
    - Root names of attribute chains (e.g., ``np`` in ``np.array()``)

    Args:
        func_node: The function AST node to analyse.

    Returns:
        Set of identifier strings used in the function body.
    """
    names: set[str] = set()
    for node in ast.walk(func_node):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            # Walk down the attribute chain to find the root name
            root: ast.expr = node
            while isinstance(root, ast.Attribute):
                root = root.value
            if isinstance(root, ast.Name):
                names.add(root.id)
    return names


def _is_type_checking_block(node: ast.If) -> bool:
    """Check if an if statement is ``if TYPE_CHECKING:``."""
    if isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING":
        return True
    # Also match `if typing.TYPE_CHECKING:`
    if isinstance(node.test, ast.Attribute):
        return (
            node.test.attr == "TYPE_CHECKING"
            and isinstance(node.test.value, ast.Name)
            and node.test.value.id == "typing"
        )
    return False


def _is_supported_module(module_name: str) -> bool:
    """Check if a module (or its top-level parent) is Designer-supported."""
    top_level = module_name.split(".")[0]
    return top_level in SUPPORTED_MODULES


@functools.cache
def _get_module_ast(module: types.ModuleType) -> ast.Module | None:
    """Return the parsed AST for *module*, cached by module identity."""
    try:
        return ast.parse(inspect.getsource(module))
    except (OSError, TypeError):
        return None


def find_imports_for_function(func: Callable[..., Any]) -> list[PackageInfo]:
    """Extract import statements used by a function from its source file.

    Inspects the module containing *func*, parses all top-level imports, then
    filters them down to only those whose imported names are actually referenced
    inside the function body.

    Args:
        func: The callable to analyse.

    Returns:
        Sorted list of :class:`PackageInfo` objects representing the imports
        used by *func*.

    Filters applied:
        - Excludes imports inside ``if TYPE_CHECKING:`` blocks
        - Only includes imports from Designer-supported builtin modules
          (see ``SUPPORTED_MODULES`` in ``builtin_modules.py``)
        - Only includes imports whose names are actually used in the function body
    """
    # --- 1. Get the function's module source ---
    module = inspect.getmodule(func)
    if not module:
        return []

    module_tree = _get_module_ast(module)
    if module_tree is None:
        logger.warning(
            "Cannot detect file-level imports for '%s': module source unavailable "
            "(e.g. Jupyter notebook). Place imports inside the function body instead.",
            func.__qualname__,
        )
        return []

    # --- 2. Collect names used inside the function body ---
    func_source = textwrap.dedent(inspect.getsource(func))
    func_tree = ast.parse(func_source)
    if not func_tree.body:
        return []

    func_node = func_tree.body[0]
    if not isinstance(func_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return []

    used_names = _collect_used_names(func_node)

    # --- 3. Parse file-level imports and filter to used ones ---
    packages: list[PackageInfo] = []
    for node in module_tree.body:
        # Skip TYPE_CHECKING blocks
        if isinstance(node, ast.If) and _is_type_checking_block(node):
            continue

        if isinstance(node, ast.Import):
            for alias in node.names:
                if not _is_supported_module(alias.name):
                    continue

                # The name used in code is the alias if present, otherwise the top-level
                # package name (e.g. "import logging.handlers" binds "logging", not
                # "logging.handlers").
                effective_name = (
                    alias.asname if alias.asname else alias.name.split(".")[0]
                )
                if effective_name in used_names:
                    packages.append(
                        PackageInfo(
                            package=alias.name,
                            alias=alias.asname,
                        )
                    )

        elif isinstance(node, ast.ImportFrom):
            if not node.module:
                continue
            if not _is_supported_module(node.module):
                continue

            # Filter to only methods actually used by the function
            matched_methods: list[ImportAlias] = []
            for alias in node.names:
                effective_name = alias.asname if alias.asname else alias.name
                if effective_name in used_names:
                    matched_methods.append(
                        ImportAlias(name=alias.name, asname=alias.asname)
                    )

            if matched_methods:
                packages.append(
                    PackageInfo(
                        package=node.module,
                        methods=matched_methods,
                    )
                )

    # Sort by import statement string for deterministic output
    return sorted(packages, key=lambda p: p.to_import_statement())

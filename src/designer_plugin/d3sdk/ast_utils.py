"""
MIT License
Copyright (c) 2025 Disguise Technologies ltd
"""

import ast
import inspect
import textwrap
import types


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


def get_class_node(tree, class_name: str) -> ast.ClassDef | None:
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
def filter_base_classes(class_node: ast.ClassDef):
    """Remove all base classes from a class definition for Python 2.7 compatibility.

    This function modifies the class_node in-place by clearing its base class list.
    Inheritance is not supported in the current D3 Designer plugin system.

    Args:
        class_node: The class definition node to process
    """
    class_node.bases = []


def filter_init_args(class_node: ast.ClassDef) -> list[str]:
    """Remove excluded arguments from __init__ method and extract parameter names.

    This function modifies the class_node in-place by:
    1. Removing excluded parameters from __init__ signature
    2. Removing excluded arguments from super().__init__() calls
    3. Returning the list of remaining parameter names (excluding 'self')

    Args:
        class_node: The class definition node to process

    Returns:
        List of parameter names that remain after filtering (excluding 'self')
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

    def visit_FunctionDef(self, node: ast.FunctionDef):
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

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
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

    def visit_arg(self, node: ast.arg):
        """Remove type annotation from argument.

        Args:
            node: The argument AST node to transform.

        Returns:
            The argument node without type annotation.
        """
        node.annotation = None
        return node

    def visit_AnnAssign(self, node: ast.AnnAssign):
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
            value=node.value,
            lineno=node.lineno,
            col_offset=node.col_offset,
        )

    def visit_Await(self, node: ast.Await):
        """Remove await keyword.

        Remove await keyword and return the underlying expression.
        Transforms 'await expr()' to 'expr()'.

        Args:
            node: The await AST node to transform.

        Returns:
            The underlying expression without the await wrapper.
        """
        return self.visit(node.value)

    def visit_JoinedStr(self, node: ast.JoinedStr):
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
    return transformer.visit(function_node)


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
# Python package finder utility
def find_packages_in_current_file(caller_stack: int = 1) -> list[str]:
    """Find all import statements in the caller's file by inspecting the call stack.

    This function walks up the call stack to find the module where it was called from,
    then parses that module's source code to extract all import statements that are
    compatible with Python 2.7 and safe to send to D3 Designer.

    Args:
        caller_stack: Number of frames to go up the call stack. Default is 1 (immediate caller).
                     Use higher values to inspect files further up the call chain.

    Returns:
        Sorted list of unique import statement strings (e.g., "import ast", "from pathlib import Path").

    Filters applied:
        - Excludes imports inside `if TYPE_CHECKING:` blocks (type checking only)
        - Excludes imports from the 'd3blobgen' package (client-side only)
        - Excludes imports from the 'typing' module (not supported in Python 2.7)
        - Excludes imports of this function itself to avoid circular references
    """
    # Get the this file frame
    current_frame: types.FrameType | None = inspect.currentframe()
    if not current_frame:
        return []

    # Get the caller's frame (file where this function is called)
    caller_frame: types.FrameType | None = current_frame
    for _ in range(caller_stack):
        if not caller_frame or not caller_frame.f_back:
            return []
        caller_frame = caller_frame.f_back

    if not caller_frame:
        return []

    modules: types.ModuleType | None = inspect.getmodule(caller_frame)
    if not modules:
        return []

    source: str = inspect.getsource(modules)

    # Parse the source code
    tree = ast.parse(source)

    # Get the name of this function to filter it out
    # For example, we don't want `from core import find_packages_in_current_file`
    function_name: str = current_frame.f_code.co_name
    # Skip any package from d3blobgen
    d3blobgen_package_name: str = "d3blobgen"
    # typing not supported in python2.7
    typing_package_name: str = "typing"

    def is_type_checking_block(node: ast.If) -> bool:
        """Check if an if statement is 'if TYPE_CHECKING:'"""
        return isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING"

    imports: list[str] = []
    for node in tree.body:
        # Skip TYPE_CHECKING blocks entirely
        if isinstance(node, ast.If) and is_type_checking_block(node):
            continue

        if isinstance(node, ast.Import):
            imported_modules: list[str] = [alias.name for alias in node.names]
            # Skip imports that include d3blobgen
            if any(d3blobgen_package_name in module for module in imported_modules):
                continue
            if any(typing_package_name in module for module in imported_modules):
                continue
            import_text: str = f"import {', '.join(imported_modules)}"
            imports.append(import_text)

        elif isinstance(node, ast.ImportFrom):
            imported_module: str | None = node.module
            imported_names: list[str] = [alias.name for alias in node.names]
            if not imported_module:
                continue
            # Skip imports that include d3blobgen
            if d3blobgen_package_name in imported_module:
                continue
            elif typing_package_name in imported_module:
                continue
            # Skip imports that include this function itself
            if function_name in imported_names:
                continue

            line_text = f"from {imported_module} import {', '.join(imported_names)}"
            imports.append(line_text)

    return sorted(set(imports))

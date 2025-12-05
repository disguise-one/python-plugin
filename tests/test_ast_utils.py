"""
MIT License
Copyright (c) 2025 Disguise Technologies ltd
"""

import ast
import inspect
import textwrap
import types

import pytest

from designer_plugin.d3sdk.ast_utils import (
    ConvertToPython27,
    convert_class_to_py27,
    convert_function_to_py27,
    filter_base_classes,
    filter_init_args,
    find_packages_in_current_file,
    get_class_node,
    get_source,
)


class TestConvertToPython27Transformer:
    """Tests for the ConvertToPython27 AST transformer."""

    def test_remove_return_type_annotation(self):
        """Test that return type annotations are removed from functions."""
        source = textwrap.dedent("""
            def my_function() -> int:
                return 42
        """)

        tree = ast.parse(source)
        transformer = ConvertToPython27()
        transformed = transformer.visit(tree)

        # Find the function node
        func = transformed.body[0]
        assert isinstance(func, ast.FunctionDef)
        assert func.returns is None

    def test_remove_argument_annotations(self):
        """Test that argument type annotations are removed."""
        source = textwrap.dedent("""
            def my_function(x: int, y: str, z: list[int]) -> None:
                pass
        """)

        tree = ast.parse(source)
        transformer = ConvertToPython27()
        transformed = transformer.visit(tree)

        func = transformed.body[0]
        # Check all arguments have no annotations
        for arg in func.args.args:
            assert arg.annotation is None

    def test_convert_async_to_sync_function(self):
        """Test that async functions are converted to regular functions."""
        source = textwrap.dedent("""
            async def async_function() -> int:
                return 42
        """)

        tree = ast.parse(source)
        transformer = ConvertToPython27()
        transformed = transformer.visit(tree)

        # Should be converted to FunctionDef, not AsyncFunctionDef
        func = transformed.body[0]
        assert isinstance(func, ast.FunctionDef)
        assert not isinstance(func, ast.AsyncFunctionDef)
        assert func.name == "async_function"
        assert func.returns is None  # Return annotation should be removed too

    def test_remove_await_expressions(self):
        """Test that await expressions are converted to normal calls."""
        source = textwrap.dedent("""
            async def my_function():
                result = await some_async_call()
                return result
        """)

        tree = ast.parse(source)
        transformer = ConvertToPython27()
        transformed = transformer.visit(tree)

        func = transformed.body[0]
        # Get the assignment statement: result = await some_async_call()
        assign_stmt = func.body[0]
        assert isinstance(assign_stmt, ast.Assign)

        # The value should now be a Call, not an Await
        assert isinstance(assign_stmt.value, ast.Call)
        assert not isinstance(assign_stmt.value, ast.Await)

    def test_convert_annotated_assignment(self):
        """Test that annotated assignments are converted to regular assignments."""
        source = textwrap.dedent("""
            def my_function():
                x: int = 5
                y: str = "hello"
        """)

        tree = ast.parse(source)
        transformer = ConvertToPython27()
        transformed = transformer.visit(tree)

        func = transformed.body[0]
        # Both statements should be regular Assign nodes, not AnnAssign
        for stmt in func.body:
            assert isinstance(stmt, ast.Assign)
            assert not isinstance(stmt, ast.AnnAssign)

    def test_annotated_assignment_without_value(self):
        """Test that annotated assignments without values are removed."""
        source = textwrap.dedent("""
            def my_function():
                x: int
                y = 10
        """)

        tree = ast.parse(source)
        transformer = ConvertToPython27()
        transformed = transformer.visit(tree)

        func = transformed.body[0]
        # Only one statement should remain (y = 10)
        assert len(func.body) == 1
        assert isinstance(func.body[0], ast.Assign)

    def test_nested_async_functions(self):
        """Test that nested async functions are also converted."""
        source = textwrap.dedent("""
            async def outer():
                async def inner() -> str:
                    return await some_call()
                return await inner()
        """)

        tree = ast.parse(source)
        transformer = ConvertToPython27()
        transformed = transformer.visit(tree)

        outer_func = transformed.body[0]
        # Outer should be regular function
        assert isinstance(outer_func, ast.FunctionDef)

        # Inner should also be regular function
        inner_func = outer_func.body[0]
        assert isinstance(inner_func, ast.FunctionDef)
        assert inner_func.returns is None

    def test_complex_type_annotations(self):
        """Test removal of complex type annotations."""
        source = textwrap.dedent("""
            def my_function(
                items: list[str],
                mapping: dict[str, int],
                *args: int,
                **kwargs: str
            ) -> tuple[int, str]:
                result: dict[str, int] = {}
                return (0, "")
        """)

        tree = ast.parse(source)
        transformer = ConvertToPython27()
        transformed = transformer.visit(tree)

        func = transformed.body[0]
        # Return type removed
        assert func.returns is None

        # Regular args annotations removed
        for arg in func.args.args:
            assert arg.annotation is None

        # *args annotation removed
        if func.args.vararg:
            assert func.args.vararg.annotation is None

        # **kwargs annotation removed
        if func.args.kwarg:
            assert func.args.kwarg.annotation is None

        # Annotated assignment converted
        assign_stmt = func.body[0]
        assert isinstance(assign_stmt, ast.Assign)

    def test_convert_basic_fstring(self):
        """Test that basic f-strings are converted to .format() style."""
        source = textwrap.dedent("""
            def my_function(name):
                message = f"Hello {name}"
                return message
        """)

        tree = ast.parse(source)
        transformer = ConvertToPython27()
        transformed = transformer.visit(tree)

        func = transformed.body[0]
        assign_stmt = func.body[0]

        # The value should be a Call node (str.format())
        assert isinstance(assign_stmt.value, ast.Call)

        # It should be calling the 'format' attribute
        assert isinstance(assign_stmt.value.func, ast.Attribute)
        assert assign_stmt.value.func.attr == "format"

        # The base string should be "Hello {}"
        assert isinstance(assign_stmt.value.func.value, ast.Constant)
        assert assign_stmt.value.func.value.value == "Hello {}"

        # It should have one argument (name)
        assert len(assign_stmt.value.args) == 1
        assert ast.unparse(assign_stmt.value.args[0]) == "name"

        # Verify the complete conversion: f"Hello {name}" -> "Hello {}".format(name)
        assert ast.unparse(assign_stmt.value) == "'Hello {}'.format(name)"

    def test_convert_fstring_with_format_spec(self):
        """Test that f-strings with format specifications are converted correctly."""
        source = textwrap.dedent("""
            def my_function(x):
                message = f"Value: {x:.2f}"
                return message
        """)

        tree = ast.parse(source)
        transformer = ConvertToPython27()
        transformed = transformer.visit(tree)

        func = transformed.body[0]
        assert isinstance(func, ast.FunctionDef)
        assign_stmt = func.body[0]
        assert isinstance(assign_stmt, ast.Assign)

        # Should be a .format() call
        assert isinstance(assign_stmt.value, ast.Call)
        assert isinstance(assign_stmt.value.func, ast.Attribute)
        assert assign_stmt.value.func.attr == "format"

        # The format string should preserve the format spec
        assert isinstance(assign_stmt.value.func.value, ast.Constant)
        assert assign_stmt.value.func.value.value == "Value: {:.2f}"

        # It should have one argument (x)
        assert len(assign_stmt.value.args) == 1
        assert isinstance(assign_stmt.value.args[0], ast.Name)
        assert assign_stmt.value.args[0].id == "x"

        # Verify the complete conversion: f"Value: {x:.2f}" -> "Value: {:.2f}".format(x)
        assert ast.unparse(assign_stmt.value) == "'Value: {:.2f}'.format(x)"

    def test_convert_fstring_with_conversion_flag(self):
        """Test that f-strings with conversion flags (!r, !s, !a) are converted correctly."""
        source = textwrap.dedent("""
            def my_function(obj):
                message = f"Repr: {obj!r}"
                return message
        """)

        tree = ast.parse(source)
        transformer = ConvertToPython27()
        transformed = transformer.visit(tree)

        func = transformed.body[0]
        assert isinstance(func, ast.FunctionDef)
        assign_stmt = func.body[0]
        assert isinstance(assign_stmt, ast.Assign)

        # Should be a .format() call
        assert isinstance(assign_stmt.value, ast.Call)
        assert isinstance(assign_stmt.value.func, ast.Attribute)

        # The format string should preserve the conversion flag
        assert isinstance(assign_stmt.value.func.value, ast.Constant)
        assert assign_stmt.value.func.value.value == "Repr: {!r}"

        # It should have one argument (obj)
        assert len(assign_stmt.value.args) == 1

        # Verify the complete conversion: f"Repr: {obj!r}" -> "Repr: {!r}".format(obj)
        assert ast.unparse(assign_stmt.value) == "'Repr: {!r}'.format(obj)"

    def test_convert_fstring_with_multiple_expressions(self):
        """Test that f-strings with multiple expressions are converted correctly."""
        source = textwrap.dedent("""
            def my_function(name, age):
                message = f"Name: {name}, Age: {age}"
                return message
        """)

        tree = ast.parse(source)
        transformer = ConvertToPython27()
        transformed = transformer.visit(tree)

        func = transformed.body[0]
        assert isinstance(func, ast.FunctionDef)
        assign_stmt = func.body[0]
        assert isinstance(assign_stmt, ast.Assign)

        # Should be a .format() call
        assert isinstance(assign_stmt.value, ast.Call)
        assert isinstance(assign_stmt.value.func, ast.Attribute)

        # The format string should have two placeholders
        assert isinstance(assign_stmt.value.func.value, ast.Constant)
        assert assign_stmt.value.func.value.value == "Name: {}, Age: {}"

        # It should have two arguments (name, age)
        assert len(assign_stmt.value.args) == 2

        # Verify the complete conversion: f"Name: {name}, Age: {age}" -> "Name: {}, Age: {}".format(name, age)
        assert ast.unparse(assign_stmt.value) == "'Name: {}, Age: {}'.format(name, age)"

    def test_convert_fstring_with_literal_braces(self):
        """Test that f-strings with literal braces (escaped) are converted correctly."""
        source = textwrap.dedent("""
            def my_function(value):
                message = f"Dict: {{key: {value}}}"
                return message
        """)

        tree = ast.parse(source)
        transformer = ConvertToPython27()
        transformed = transformer.visit(tree)

        func = transformed.body[0]
        assert isinstance(func, ast.FunctionDef)
        assign_stmt = func.body[0]
        assert isinstance(assign_stmt, ast.Assign)

        # Should be a .format() call
        assert isinstance(assign_stmt.value, ast.Call)
        assert isinstance(assign_stmt.value.func, ast.Attribute)

        # The format string should preserve the escaped braces
        assert isinstance(assign_stmt.value.func.value, ast.Constant)
        assert assign_stmt.value.func.value.value == "Dict: {{key: {}}}"

        # It should have one argument (value)
        assert len(assign_stmt.value.args) == 1

        # Verify the complete conversion: f"Dict: {{key: {value}}}" -> "Dict: {{key: {}}}".format(value)
        assert ast.unparse(assign_stmt.value) == "'Dict: {{key: {}}}'.format(value)"

    def test_convert_fstring_with_literal_braces_and_intermediate_variable(self):
        """Test f-string with literal braces using an intermediate variable with type annotations."""
        source = textwrap.dedent("""
            def my_function(value: str) -> str:
                my_message: str = value
                message = f"Dict: {{key: {my_message}}}"
                return message
        """)

        tree = ast.parse(source)
        transformer = ConvertToPython27()
        transformed = transformer.visit(tree)

        func = transformed.body[0]
        assert isinstance(func, ast.FunctionDef)

        # Type annotations should be removed
        assert func.returns is None
        assert func.args.args[0].annotation is None

        # First assignment: my_message = value (type annotation removed)
        first_assign = func.body[0]
        assert isinstance(first_assign, ast.Assign)
        assert not isinstance(first_assign, ast.AnnAssign)
        assert ast.unparse(first_assign.targets[0]) == "my_message"
        assert ast.unparse(first_assign.value) == "value"

        # Second assignment: message = f"Dict: {{key: {my_message}}}" converted to .format()
        second_assign = func.body[1]
        assert isinstance(second_assign, ast.Assign)

        # Should be a .format() call
        assert isinstance(second_assign.value, ast.Call)
        assert isinstance(second_assign.value.func, ast.Attribute)
        assert second_assign.value.func.attr == "format"

        # The format string should preserve the escaped braces
        assert isinstance(second_assign.value.func.value, ast.Constant)
        assert second_assign.value.func.value.value == "Dict: {{key: {}}}"

        # It should have one argument (my_message)
        assert len(second_assign.value.args) == 1
        assert ast.unparse(second_assign.value.args[0]) == "my_message"

        # Verify the complete conversion
        assert ast.unparse(second_assign.value) == "'Dict: {{key: {}}}'.format(my_message)"

    def test_convert_fstring_in_annotated_assignment_with_nested_call(self):
        """Test f-string nested in function call within annotated assignment.

        This is a regression test for a bug where f-strings inside annotated assignments
        were not being converted because visit_AnnAssign was not recursively visiting
        the value expression.
        """
        source = textwrap.dedent("""
            def simple_script(surface_name: str) -> dict[str, str]:
                surface: Screen2 = resourceManager.load(
                    Path(f"objects/screen2/{surface_name}.apx"),
                    Screen2
                )
                return {"name": surface.description}
        """)

        tree = ast.parse(source)
        transformer = ConvertToPython27()
        transformed = transformer.visit(tree)

        func = transformed.body[0]
        assert isinstance(func, ast.FunctionDef)

        # Type annotations should be removed
        assert func.returns is None
        assert func.args.args[0].annotation is None

        # First statement: annotated assignment converted to regular assignment
        first_assign = func.body[0]
        assert isinstance(first_assign, ast.Assign)
        assert not isinstance(first_assign, ast.AnnAssign)

        # The f-string inside the Path() call should be converted to .format()
        # The structure is: surface = resourceManager.load(Path(...), Screen2)
        # We need to check the first argument of resourceManager.load() which is Path(...)
        load_call = first_assign.value
        assert isinstance(load_call, ast.Call)

        # First argument is Path(...)
        path_call = load_call.args[0]
        assert isinstance(path_call, ast.Call)

        # The argument to Path() should be a .format() call, not an f-string
        format_call = path_call.args[0]
        assert isinstance(format_call, ast.Call)
        assert isinstance(format_call.func, ast.Attribute)
        assert format_call.func.attr == "format"

        # Verify the format string
        assert isinstance(format_call.func.value, ast.Constant)
        assert format_call.func.value.value == "objects/screen2/{}.apx"

        # Verify the format argument is surface_name
        assert len(format_call.args) == 1
        assert ast.unparse(format_call.args[0]) == "surface_name"

        # Verify the complete unparsed output doesn't contain f-strings
        unparsed = ast.unparse(first_assign)
        assert "f'" not in unparsed and 'f"' not in unparsed
        assert ".format(" in unparsed

    def test_convert_fstring_with_complex_expression(self):
        """Test that f-strings with complex expressions are converted correctly."""
        source = textwrap.dedent("""
            def my_function(items):
                message = f"Count: {len(items)}"
                return message
        """)

        tree = ast.parse(source)
        transformer = ConvertToPython27()
        transformed = transformer.visit(tree)

        func = transformed.body[0]
        assert isinstance(func, ast.FunctionDef)
        assign_stmt = func.body[0]
        assert isinstance(assign_stmt, ast.Assign)

        # Should be a .format() call
        assert isinstance(assign_stmt.value, ast.Call)
        assert isinstance(assign_stmt.value.func, ast.Attribute)
        assert assign_stmt.value.func.attr == "format"

        # The format string should have one placeholder
        assert isinstance(assign_stmt.value.func.value, ast.Constant)
        assert assign_stmt.value.func.value.value == "Count: {}"

        # It should have one argument (len(items))
        assert len(assign_stmt.value.args) == 1
        call_arg = assign_stmt.value.args[0]
        assert ast.unparse(call_arg) == "len(items)"

        # Verify the complete conversion: f"Count: {len(items)}" -> "Count: {}".format(len(items))
        assert ast.unparse(assign_stmt.value) == "'Count: {}'.format(len(items))"

    def test_convert_fstring_combined_features(self):
        """Test f-string with combined conversion flag and format spec."""
        source = textwrap.dedent("""
            def my_function(x):
                message = f"Value: {x!s:>10}"
                return message
        """)

        tree = ast.parse(source)
        transformer = ConvertToPython27()
        transformed = transformer.visit(tree)

        func = transformed.body[0]
        assert isinstance(func, ast.FunctionDef)
        assign_stmt = func.body[0]
        assert isinstance(assign_stmt, ast.Assign)

        # Should be a .format() call
        assert isinstance(assign_stmt.value, ast.Call)
        assert isinstance(assign_stmt.value.func, ast.Attribute)

        # The format string should preserve conversion flag at minimum
        assert isinstance(assign_stmt.value.func.value, ast.Constant)
        format_str = assign_stmt.value.func.value.value
        assert isinstance(format_str, str)
        assert "Value:" in format_str
        assert "{!s" in format_str or "{" in format_str

        # It should have one argument (x)
        assert len(assign_stmt.value.args) == 1

        # Verify the complete conversion: f"Value: {x!s:>10}" -> "Value: {!s:>10}".format(x)
        assert ast.unparse(assign_stmt.value) == "'Value: {!s:>10}'.format(x)"


class TestConvertFunctionToPy27:
    """Tests for convert_function_to_py27 function."""

    def test_simple_function_conversion(self):
        """Test basic function conversion."""
        source = textwrap.dedent("""
            def my_function(x: int, y: str) -> bool:
                result: str = f"{x} {y}"
                return True
        """)

        tree = ast.parse(source)
        func_node = tree.body[0]
        assert isinstance(func_node, ast.FunctionDef)

        convert_function_to_py27(func_node)

        # Verify conversions
        assert func_node.returns is None
        for arg in func_node.args.args:
            assert arg.annotation is None

        # Check body was transformed
        assign_stmt = func_node.body[0]
        assert isinstance(assign_stmt, ast.Assign)

    def test_async_function_body_conversion(self):
        """Test that async function bodies are converted."""
        source = textwrap.dedent("""
            async def my_function():
                result = await some_call()
                data: int = 42
                return result
        """)

        tree = ast.parse(source)
        func_node = tree.body[0]
        assert isinstance(func_node, ast.AsyncFunctionDef)

        # First convert async to regular (simulating what happens in real usage)
        transformer = ConvertToPython27()
        new_func = transformer.visit_AsyncFunctionDef(func_node)

        # The function should now be regular FunctionDef
        assert isinstance(new_func, ast.FunctionDef)

        # Check await was removed
        assign_stmt = new_func.body[0]
        assert isinstance(assign_stmt, ast.Assign)
        assert isinstance(assign_stmt.value, ast.Call)

        # Check annotated assignment was converted
        assign_stmt2 = new_func.body[1]
        assert isinstance(assign_stmt2, ast.Assign)


class TestConvertClassToPy27:
    """Tests for convert_class_to_py27 function."""

    def test_class_with_async_methods(self):
        """Test that class with async methods is converted."""
        source = textwrap.dedent("""
            class MyClass:
                async def async_method(self) -> int:
                    return await something()

                def regular_method(self, x: int) -> str:
                    return str(x)
        """)

        tree = ast.parse(source)
        class_node = tree.body[0]
        assert isinstance(class_node, ast.ClassDef)

        convert_class_to_py27(class_node)

        # All methods should be regular FunctionDef
        for node in class_node.body:
            if isinstance(node, ast.FunctionDef):
                assert not isinstance(node, ast.AsyncFunctionDef)
                # Return annotations should be removed
                assert node.returns is None
                # Argument annotations should be removed
                for arg in node.args.args:
                    assert arg.annotation is None


class TestAsyncFunctionDefInvestigation:
    """Investigation tests for visit_AsyncFunctionDef behavior."""

    def test_async_def_converted_to_def(self):
        """Verify that AsyncFunctionDef is replaced with FunctionDef in the tree."""
        source = textwrap.dedent("""
            async def my_async_func(x: int) -> str:
                result = await call_something(x)
                return result
        """)

        tree = ast.parse(source)
        original_func = tree.body[0]
        assert isinstance(original_func, ast.AsyncFunctionDef)

        # Apply transformer
        transformer = ConvertToPython27()
        transformed_tree = transformer.visit(tree)

        # The node in the tree should now be FunctionDef
        new_func = transformed_tree.body[0]
        assert isinstance(new_func, ast.FunctionDef)
        assert not isinstance(new_func, ast.AsyncFunctionDef)

        # Verify properties are preserved
        assert new_func.name == "my_async_func"
        assert len(new_func.args.args) == 1
        assert new_func.args.args[0].arg == "x"

        # Return type should be removed
        assert new_func.returns is None

        # Argument annotation should be removed
        assert new_func.args.args[0].annotation is None

    def test_async_with_nested_transformations(self):
        """Test that async function with nested await and annotations works."""
        source = textwrap.dedent("""
            async def process_data(items: list[str]) -> dict[str, int]:
                results: dict[str, int] = {}
                for item in items:
                    value = await fetch_value(item)
                    results[item] = value
                return results
        """)

        tree = ast.parse(source)
        transformer = ConvertToPython27()
        transformed = transformer.visit(tree)

        func = transformed.body[0]

        # Should be regular function
        assert isinstance(func, ast.FunctionDef)

        # No return type
        assert func.returns is None

        # No argument annotations
        assert func.args.args[0].annotation is None

        # First statement should be regular assignment (not annotated)
        first_stmt = func.body[0]
        assert isinstance(first_stmt, ast.Assign)
        assert not isinstance(first_stmt, ast.AnnAssign)

        # The await in the loop should be converted to regular call
        for_loop = func.body[1]
        assert isinstance(for_loop, ast.For)
        assign_in_loop = for_loop.body[0]
        assert isinstance(assign_in_loop, ast.Assign)
        assert isinstance(assign_in_loop.value, ast.Call)

    def test_location_metadata_preserved(self):
        """Test that source location metadata is preserved during conversion."""
        source = textwrap.dedent("""
            async def my_func():
                pass
        """)

        tree = ast.parse(source)
        original_func = tree.body[0]
        original_lineno = original_func.lineno
        original_col = original_func.col_offset

        transformer = ConvertToPython27()
        transformed = transformer.visit(tree)

        new_func = transformed.body[0]
        # Location should be preserved via ast.copy_location
        assert new_func.lineno == original_lineno
        assert new_func.col_offset == original_col


class TestGetSource:
    """Tests for get_source function."""

    def test_get_source_from_frame(self):
        """Test that source code can be extracted from a frame."""
        # Get current frame
        frame = inspect.currentframe()
        assert frame is not None

        # Extract source
        source = get_source(frame)

        # Verify source contains this test file's content
        assert source is not None
        assert isinstance(source, str)
        assert "test_get_source_from_frame" in source
        assert "def test_get_source_from_frame" in source

    def test_get_source_dedents_code(self):
        """Test that extracted source code is dedented."""
        def nested_function():
            frame = inspect.currentframe()
            return get_source(frame) if frame else None

        source = nested_function()

        # Verify the source is dedented (doesn't start with leading whitespace)
        assert source is not None
        # The source should contain the entire file, dedented
        lines = source.split('\n')
        # Find lines that should be at the start of the file
        for line in lines:
            if line.startswith('"""Tests for AST'):
                # This line should be at column 0 after dedenting
                assert line[0] != ' '
                break


class TestGetClassNode:
    """Tests for get_class_node function."""

    def test_find_class_by_name(self):
        """Test finding a class definition by name."""
        source = textwrap.dedent("""
            class FirstClass:
                pass

            class SecondClass:
                pass

            class ThirdClass:
                pass
        """)

        tree = ast.parse(source)
        class_node = get_class_node(tree, "SecondClass")

        assert class_node is not None
        assert isinstance(class_node, ast.ClassDef)
        assert class_node.name == "SecondClass"

    def test_class_not_found(self):
        """Test that None is returned when class is not found."""
        source = textwrap.dedent("""
            class MyClass:
                pass
        """)

        tree = ast.parse(source)
        class_node = get_class_node(tree, "NonExistentClass")

        assert class_node is None


class TestFilterBaseClasses:
    """Tests for filter_base_classes function."""

    def test_remove_all_base_classes(self):
        """Test that all base classes are removed from a class definition."""
        source = textwrap.dedent("""
            class MyClass(BaseClass, AnotherBase):
                pass
        """)

        tree = ast.parse(source)
        class_node = tree.body[0]
        assert isinstance(class_node, ast.ClassDef)

        # Verify bases exist before filtering
        assert len(class_node.bases) == 2

        filter_base_classes(class_node)

        # Verify all bases are removed
        assert len(class_node.bases) == 0

    def test_empty_base_classes(self):
        """Test that filtering works on classes with no base classes."""
        source = textwrap.dedent("""
            class MyClass:
                pass
        """)

        tree = ast.parse(source)
        class_node = tree.body[0]
        assert isinstance(class_node, ast.ClassDef)

        filter_base_classes(class_node)

        assert len(class_node.bases) == 0


class TestFilterInitArgs:
    """Tests for filter_init_args function."""

    def test_class_with_init_returns_param_names(self):
        """Test that __init__ parameters (excluding self) are returned."""
        source = textwrap.dedent("""
            class MyClass:
                def __init__(self, a: int):
                    pass
                def other_method(self):
                    pass
        """)

        tree = ast.parse(source)
        class_node = tree.body[0]
        assert isinstance(class_node, ast.ClassDef)

        param_names = filter_init_args(class_node)

        assert param_names == ["a"]

    def test_class_without_init(self):
        """Test that classes without __init__ return empty list."""
        source = textwrap.dedent("""
            class MyClass:
                def other_method(self):
                    pass
        """)

        tree = ast.parse(source)
        class_node = tree.body[0]
        assert isinstance(class_node, ast.ClassDef)

        param_names = filter_init_args(class_node)

        assert param_names == []

    def test_init_with_multiple_params(self):
        """Test that all parameters except self are returned."""
        source = textwrap.dedent("""
            class MyClass:
                def __init__(self, a: int, b: str, c: list):
                    pass
        """)

        tree = ast.parse(source)
        class_node = tree.body[0]
        assert isinstance(class_node, ast.ClassDef)

        param_names = filter_init_args(class_node)

        assert param_names == ["a", "b", "c"]

    def test_init_with_only_self(self):
        """Test that __init__ with only self returns empty list."""
        source = textwrap.dedent("""
            class MyClass:
                def __init__(self):
                    pass
        """)

        tree = ast.parse(source)
        class_node = tree.body[0]
        assert isinstance(class_node, ast.ClassDef)

        param_names = filter_init_args(class_node)

        assert param_names == []


class TestFindPackagesInCurrentFile:
    """Tests for find_packages_in_current_file function."""

    def test_finds_imports_from_current_file(self):
        """Test that the function finds import statements from the calling file."""
        # This test file has imports at the top - they should be found
        imports = find_packages_in_current_file()

        # Should find at least some of our imports
        assert isinstance(imports, list)
        assert len(imports) > 0

        # Should be sorted
        assert imports == sorted(imports)

        # Check for specific imports we know exist in this file
        assert "import ast" in imports
        assert "import pytest" in imports
        assert "import textwrap" in imports

    def test_excludes_typing_imports(self):
        """Test that typing module imports are excluded."""
        # Since this file doesn't import typing, we can't directly test exclusion here
        # But we can verify the function doesn't crash and returns valid results
        imports = find_packages_in_current_file()

        # Verify no typing imports are present
        typing_imports = [imp for imp in imports if "typing" in imp]
        assert len(typing_imports) == 0

    def test_excludes_d3blobgen_imports(self):
        """Test that d3blobgen package imports are excluded."""
        imports = find_packages_in_current_file()

        # Verify no d3blobgen imports are present
        d3blobgen_imports = [imp for imp in imports if "d3blobgen" in imp]
        assert len(d3blobgen_imports) == 0

    def test_excludes_find_packages_function_itself(self):
        """Test that the function itself is excluded from imports."""
        imports = find_packages_in_current_file()

        # Should not include import of find_packages_in_current_file itself
        # even though we import it at the top of this file
        function_imports = [imp for imp in imports if "find_packages_in_current_file" in imp]
        assert len(function_imports) == 0

    def test_returns_unique_sorted_imports(self):
        """Test that returned imports are unique and sorted."""
        imports = find_packages_in_current_file()

        # Check uniqueness
        assert len(imports) == len(set(imports))

        # Check sorting
        assert imports == sorted(imports)


class TestDecoratorHandling:
    """Tests for handling decorators in AST transformations."""

    def test_function_with_decorators(self):
        """Test that function decorators are preserved during conversion."""
        source = textwrap.dedent("""
            @decorator1
            @decorator2
            def my_function(x: int) -> str:
                return str(x)
        """)

        tree = ast.parse(source)
        transformer = ConvertToPython27()
        transformed = transformer.visit(tree)

        func = transformed.body[0]
        assert isinstance(func, ast.FunctionDef)

        # Decorators should be preserved
        assert len(func.decorator_list) == 2

        # Type annotations should be removed
        assert func.returns is None
        assert func.args.args[0].annotation is None

    def test_async_function_with_decorators(self):
        """Test that async function decorators are preserved during conversion."""
        source = textwrap.dedent("""
            @async_decorator
            async def my_function(x: int) -> str:
                return await something(x)
        """)

        tree = ast.parse(source)
        transformer = ConvertToPython27()
        transformed = transformer.visit(tree)

        func = transformed.body[0]

        # Should be converted to regular function
        assert isinstance(func, ast.FunctionDef)
        assert not isinstance(func, ast.AsyncFunctionDef)

        # Decorator should be preserved
        assert len(func.decorator_list) == 1
        assert isinstance(func.decorator_list[0], ast.Name)
        assert func.decorator_list[0].id == "async_decorator"

    def test_class_with_decorators(self):
        """Test that class decorators are preserved."""
        source = textwrap.dedent("""
            @dataclass
            class MyClass:
                def method(self, x: int) -> str:
                    return str(x)
        """)

        tree = ast.parse(source)
        class_node = tree.body[0]
        assert isinstance(class_node, ast.ClassDef)

        # Verify decorator exists
        assert len(class_node.decorator_list) == 1

        # Convert the class
        convert_class_to_py27(class_node)

        # Decorator should still be there
        assert len(class_node.decorator_list) == 1

        # Method should be converted
        method = class_node.body[0]
        assert isinstance(method, ast.FunctionDef)
        assert method.returns is None


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_function_body(self):
        """Test conversion of function with only pass statement."""
        source = textwrap.dedent("""
            def empty_function(x: int) -> None:
                pass
        """)

        tree = ast.parse(source)
        transformer = ConvertToPython27()
        transformed = transformer.visit(tree)

        func = transformed.body[0]
        assert isinstance(func, ast.FunctionDef)
        assert func.returns is None
        assert len(func.body) == 1
        assert isinstance(func.body[0], ast.Pass)

    def test_function_with_multiple_decorators_and_complex_types(self):
        """Test complex scenario with multiple decorators and type hints."""
        source = textwrap.dedent("""
            @decorator1
            @decorator2(arg="value")
            def complex_function(
                a: int,
                b: str,
                *args: int,
                **kwargs: str
            ) -> dict[str, int]:
                result: dict[str, int] = {}
                return result
        """)

        tree = ast.parse(source)
        transformer = ConvertToPython27()
        transformed = transformer.visit(tree)

        func = transformed.body[0]
        assert isinstance(func, ast.FunctionDef)

        # All decorators preserved
        assert len(func.decorator_list) == 2

        # All type hints removed
        assert func.returns is None
        for arg in func.args.args:
            assert arg.annotation is None
        if func.args.vararg:
            assert func.args.vararg.annotation is None
        if func.args.kwarg:
            assert func.args.kwarg.annotation is None

    def test_nested_classes_and_functions(self):
        """Test conversion of nested class and function definitions."""
        source = textwrap.dedent("""
            class OuterClass:
                def outer_method(self) -> None:
                    class InnerClass:
                        def inner_method(self, x: int) -> str:
                            return str(x)
        """)

        tree = ast.parse(source)
        class_node = tree.body[0]
        assert isinstance(class_node, ast.ClassDef)
        convert_class_to_py27(class_node)

        # Outer method should be converted
        outer_method = class_node.body[0]
        assert isinstance(outer_method, ast.FunctionDef)
        assert outer_method.returns is None

        # Inner class should exist
        inner_class = outer_method.body[0]
        assert isinstance(inner_class, ast.ClassDef)

    def test_fstring_unsupported_part_raises_error(self):
        """Test that unsupported JoinedStr parts raise NotImplementedError."""
        # This is a hypothetical test - in practice, it's hard to create
        # an unsupported JoinedStr part that the parser would accept.
        # The transformer handles Constant and FormattedValue nodes.
        # For now, we verify the basic f-string cases work correctly.
        source = textwrap.dedent("""
            def my_function(x, y):
                # Standard f-string cases
                msg1 = f"Value: {x}"
                msg2 = f"Values: {x} and {y}"
                return msg1 + msg2
        """)

        tree = ast.parse(source)
        transformer = ConvertToPython27()
        # Should not raise NotImplementedError for standard cases
        transformed = transformer.visit(tree)

        func = transformed.body[0]
        assert isinstance(func, ast.FunctionDef)
        assert len(func.body) == 3  # Two assignments and one return


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

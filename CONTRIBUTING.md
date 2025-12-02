# Contributing to designer-plugin

Thank you for your interest in contributing to designer-plugin! This document provides guidelines and instructions for contributing.

## Development Setup

### Prerequisites

- Python 3.11 or higher
- [uv](https://github.com/astral-sh/uv) package manager

### Getting Started

1. **Clone the repository:**
   ```bash
   git clone https://github.com/disguise-one/python-plugin.git
   cd python-plugin
   ```

2. **Install dependencies:**
   ```bash
   uv sync --dev
   ```

3. **Install pre-commit hooks:**
   ```bash
   uv run pre-commit install
   ```

## Development Workflow

### Running Tests

Run the full test suite:
```bash
uv run pytest
```

Run tests with verbose output:
```bash
uv run pytest -v
```

Run specific test file:
```bash
uv run pytest tests/test_core.py
```

### Code Quality Checks

**Linting:**
```bash
uv run ruff check
```

**Auto-fix linting issues:**
```bash
uv run ruff check --fix
```

**Formatting:**
```bash
uv run ruff format
```

**Type checking:**
```bash
uv run mypy
```

**Run all checks:**
```bash
uv run ruff check && uv run ruff format --check && uv run mypy && uv run pytest
```

### Pre-commit Hooks

Pre-commit hooks are configured to automatically run:
- `ruff check --fix` - Linting with auto-fix
- `ruff format` - Code formatting

These run automatically on `git commit`. To run manually:
```bash
uv run pre-commit run --all-files
```

## Code Style

### General Guidelines

- Follow PEP 8 style guidelines
- Use type hints for all function signatures
- Write docstrings for all public APIs
- Prefer explicit over implicit

### Type Hints

All code must include type hints:
```python
def my_function(name: str, count: int = 0) -> dict[str, int]:
    """Do something useful.

    Args:
        name: The name parameter.
        count: The count parameter.

    Returns:
        A dictionary mapping name to count.
    """
    return {name: count}
```

### Docstrings

Use Google-style docstrings:
```python
def example_function(param1: str, param2: int) -> bool:
    """Brief description of the function.

    More detailed explanation if needed. Can span
    multiple lines.

    Args:
        param1: Description of param1.
        param2: Description of param2.

    Returns:
        Description of return value.

    Raises:
        ValueError: When param2 is negative.
    """
    if param2 < 0:
        raise ValueError("param2 must be non-negative")
    return True
```

### Code Organization

- Group related functionality together
- Use clear, descriptive names
- Avoid circular imports

## Testing Guidelines

### Test Structure

- Place tests in the `tests/` directory
- Name test files `test_*.py`
- Name test classes `Test*`
- Name test functions `test_*`

### Writing Tests

```python
class TestMyFeature:
    """Test suite for my feature."""

    def test_basic_functionality(self) -> None:
        """Test basic functionality works correctly."""
        result = my_function("test", 42)
        assert result == {"test": 42}

    def test_error_handling(self) -> None:
        """Test error handling for invalid input."""
        with pytest.raises(ValueError):
            my_function("test", -1)
```

### Test Coverage

- Aim for high test coverage
- Test both success and error cases
- Test edge cases and boundary conditions
- Use mocks for external dependencies

## Pull Request Process

### Before Submitting

1. **Create a feature branch:**
   ```bash
   git checkout -b feature/my-new-feature
   ```

2. **Make your changes:**
   - Write code
   - Add tests
   - Update documentation

3. **Run all checks:**
   ```bash
   uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest
   ```

4. **Commit your changes:**
   ```bash
   git add .
   git commit -m "Add my new feature"
   ```

   Commit messages should:
   - Use present tense ("Add feature" not "Added feature")
   - Be clear and descriptive
   - Reference issue numbers if applicable

5. **Push to your fork:**
   ```bash
   git push origin feature/my-new-feature
   ```

### Submitting the PR

1. Open a Pull Request on GitHub
2. Fill out the PR template
3. Link any related issues
4. Wait for CI checks to pass
5. Address review feedback

### PR Requirements

- All tests must pass
- Code must pass linting and type checking
- New features must include tests
- Documentation must be updated

## Reporting Issues

### Bug Reports

When reporting bugs, please include:
- Description of the issue
- Steps to reproduce
- Expected behavior
- Actual behavior
- Python version
- Package version
- Minimal code example (if applicable)

### Feature Requests

When requesting features, please include:
- Clear description of the feature
- Use case and motivation
- Example API or usage (if applicable)
- Any alternatives you've considered

## Documentation

### Updating Documentation

- Update README.md for user facing changes
- Update docstrings for API changes
- Update CHANGELOG.md following Keep a Changelog format
- Add examples for new features

### Documentation Style

- Write clear, concise documentation
- Include code examples
- Explain the "why" not just the "what"
- Keep documentation up to date with code

## Release Process

Releases are managed by project maintainers:

1. Update version in `pyproject.toml`
2. Update `CHANGELOG.md`
3. Create git tag: `git tag -a v1.2.0 -m "Release v1.2.0"`
4. Push tag: `git push origin v1.2.0`
5. Build distributions: `uv build`
6. Upload to PyPI: `twine upload dist/*`

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help others learn and grow
- Assume good intentions

## Questions?

If you have questions about contributing:
- Open a [GitHub Issue](https://github.com/disguise-one/python-plugin/issues)
- Check existing issues and PRs
- Review the documentation

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

"""
MIT License
Copyright (c) 2025 Disguise Technologies ltd

Logging configuration for designer_plugin.

By default, logging is disabled.
To see logs from this package, configure logging in your application:

    import logging
    logging.basicConfig(level=logging.INFO)

Or configure the designer_plugin logger specifically:

    logging.getLogger('designer_plugin').setLevel(logging.DEBUG)

For quick debugging, you can use the convenience function:

    from designer_plugin.logger import enable_debug_logging
    enable_debug_logging()

Internal Usage (for library developers):

Module-level loggers should be created using standard Python logging:

    import logging
    logger = logging.getLogger(__name__)

Advanced Usage - Granular Control:

This library uses module-level loggers, allowing you to control logging
for specific submodules independently:

    # Enable DEBUG only for d3sdk submodule
    logging.getLogger('designer_plugin.d3sdk').setLevel(logging.DEBUG)

    # Enable INFO for the main package
    logging.getLogger('designer_plugin').setLevel(logging.INFO)

    # Enable DEBUG only for the API module
    logging.getLogger('designer_plugin.api').setLevel(logging.DEBUG)

Log messages will show their source module:

    2025-11-29 10:15:23 [designer_plugin.api:INFO] API initialized
    2025-11-29 10:15:24 [designer_plugin.d3sdk.client:DEBUG] Connecting to server
    2025-11-29 10:15:25 [designer_plugin.models:INFO] Model loaded

This module hierarchy allows you to troubleshoot specific components
without being overwhelmed by logs from the entire package.
"""

import logging
import sys
from typing import Any

# Package root logger name
LOGGER_NAME = "designer_plugin"

# Add NullHandler by default to prevent "No handler found" warnings
logging.getLogger(LOGGER_NAME).addHandler(logging.NullHandler())


def enable_debug_logging(
    level: int = logging.DEBUG,
    stream: Any | None = None,
    format_string: str | None = None,
) -> None:
    """
    Enable debug logging for designer_plugin.

    For the production environments, it is advised to configure logging through
    the application's logging configuration:
    - i.e. `logging.basicConfig()` or `dictConfig()`

    Note: This will remove any existing handlers on the designer_plugin logger
    to avoid duplicate log messages.

    Args:
        level: Logging level (default: `logging.DEBUG`)
        stream: Output stream (default: `sys.stderr`)
        format_string: Custom format string for log messages
                      (default: `'%(asctime)s [%(name)s:%(levelname)s] %(message)s'`)

    Example:
        ```python
        from designer_plugin.logger import enable_debug_logging
        enable_debug_logging()

        # With custom level
        enable_debug_logging(level=logging.INFO)

        # With custom format
        enable_debug_logging(format_string='[%(levelname)s] %(message)s')
        ```
    """
    logger = logging.getLogger(LOGGER_NAME)

    # Remove existing handlers to avoid duplicates
    # Keep the NullHandler removal to prevent accumulation
    logger.handlers.clear()

    # Create and configure handler
    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setLevel(level)

    # Create and set formatter
    fmt = format_string or "%(asctime)s [%(name)s:%(levelname)s] %(message)s"
    formatter = logging.Formatter(fmt)
    handler.setFormatter(formatter)

    # Configure logger
    logger.addHandler(handler)
    logger.setLevel(level)

    # Prevent propagation to avoid duplicate logs if root logger is also configured
    logger.propagate = False


def disable_logging() -> None:
    """
    Disable all logging from designer_plugin.

    This removes all handlers and adds back the NullHandler.
    Useful for silencing logs during testing or in production.

    Example:
        ```python
        from designer_plugin.logger import disable_logging
        disable_logging()
        ```
    """
    logger = logging.getLogger(LOGGER_NAME)
    logger.handlers.clear()
    logger.addHandler(logging.NullHandler())
    logger.setLevel(logging.NOTSET)
    logger.propagate = True

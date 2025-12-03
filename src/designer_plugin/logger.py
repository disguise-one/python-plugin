"""
MIT License
Copyright (c) 2025 Disguise Technologies ltd

Logging configuration for designer_plugin.

By default, logging is disabled.
To see logs from this package, configure logging in your application:

    import logging
    logging.basicConfig(level=logging.INFO)

Or configure the designer_plugin logger specifically:

    from designer_plugin.logger import get_logger
    get_logger().setLevel(logging.DEBUG)

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

# Package root logger name
LOGGER_NAME = "designer_plugin"


def get_logger() -> logging.Logger:
    return logging.getLogger(LOGGER_NAME)

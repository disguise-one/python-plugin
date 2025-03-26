# python-plugin

A small Python library which publishes the DNS-SD service for a plugin.

## Installation

To install the plugin, use pip:

```bash
pip install disguise-designer-plugin
```

## Usage

The `DesignerPlugin` class allows you to publish a plugin for the Disguise Designer application. Below is an example of how to use it:

```python
from designer_plugin import DesignerPlugin

# Synchronous usage
with DesignerPlugin(name="MyPlugin", port=12345) as plugin:
    print("Plugin is published. Press Ctrl+C to stop.")

# Asynchronous usage
import asyncio

async def main():
    async with DesignerPlugin(name="MyPlugin", port=12345) as plugin:
        print("Plugin is published. Press Ctrl+C to stop.")
        await asyncio.Event().wait()

asyncio.run(main())
```

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.


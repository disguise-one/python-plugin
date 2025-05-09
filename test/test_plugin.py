from unittest.mock import patch, mock_open
from unittest import TestCase
from json import dumps as json_dumps, JSONDecodeError
from . import DesignerPlugin

def _escaped(name):
    """Escape the name for Zeroconf."""
    invalid_removed = ''.join(c if 0x20 <= ord(c) <= 0x7E else '\\%02X' % ord(c) for c in name)
    return invalid_removed.replace('.', '\\.')

class RegistrationTests(TestCase):
    def test_registration(self):
        """Test that the DesignerPlugin registers a service with Zeroconf."""
        with (
            patch("designer_plugin.designer_plugin.Zeroconf") as _zeroconf
        ):
            with DesignerPlugin("test_name", 9999) as plugin:
                pass

            _zeroconf.assert_called_once()
            _zeroconf().register_service.assert_called_once()
            _zeroconf().close.assert_called_once()


class ParsingTests(TestCase):
    def test_file_path_exception(self):
        """Test that the DesignerPlugin.default_init raises a FileNotFoundError when the file is missing."""
        with (
            patch("builtins.open", mock_open()) as _open,
            patch("designer_plugin.designer_plugin.Zeroconf") as _zeroconf
        ):
            _open.return_value.__enter__.side_effect = FileNotFoundError

            with self.assertRaises(FileNotFoundError):
                DesignerPlugin.default_init("test_name", 9999)

    def test_file_empty_error(self):
        """Test that the DesignerPlugin raises a JSONDecodeError when the file is empty/invalid."""
        with (
            patch("builtins.open", mock_open(read_data='')) as _open,
            patch("designer_plugin.designer_plugin.Zeroconf") as _zeroconf
        ):
            with self.assertRaises(JSONDecodeError):
                DesignerPlugin.from_json_file('test.json', 9999)

    def test_defaults(self):
        """Test that the DesignerPlugin registers a service with Zeroconf."""
        with (
            patch("builtins.open", mock_open()) as _open,
            patch("designer_plugin.designer_plugin.Zeroconf") as _zeroconf
        ):
            _open.return_value.__enter__.side_effect = FileNotFoundError
            with DesignerPlugin("test_name", 9999) as plugin:
                _zeroconf().register_service.assert_called_once()
                service_info = _zeroconf(
                ).register_service.mock_calls[0].args[0]
                self.assertEqual(service_info.name, f"{plugin.name}._d3plugin._tcp.local.")
                self.assertEqual(service_info.type, "_d3plugin._tcp.local.")
                self.assertEqual(service_info.port, 9999)
                self.assertEqual(service_info.server, f"{plugin.hostname}.local.")
                self.assertFalse(b"u" in service_info.properties)
                self.assertEqual(service_info.properties[b"t"], b"web")
                self.assertEqual(service_info.properties[b"s"], b"false")

    def test_name_override(self):
        """Test that the DesignerPlugin registers a service with Zeroconf."""
        json = json_dumps({
            "name": "Different Name",
        })
        with (
            patch("builtins.open", mock_open(read_data=json)) as _open,
            patch("designer_plugin.designer_plugin.Zeroconf") as _zeroconf
        ):

            with DesignerPlugin.default_init(9999) as plugin:
                _zeroconf().register_service.assert_called_once()
                service_info = _zeroconf(
                ).register_service.mock_calls[0].args[0]
                self.assertEqual(service_info.name, f"Different Name._d3plugin._tcp.local.")
                self.assertEqual(service_info.type, "_d3plugin._tcp.local.")
                self.assertEqual(service_info.port, 9999)
                self.assertEqual(service_info.server, f"{plugin.hostname}.local.")
                self.assertFalse(b"u" in service_info.properties)
                self.assertEqual(service_info.properties[b"t"], b"web")

    def test_url_override(self):
        """Test that the DesignerPlugin registers a service with Zeroconf."""
        json = json_dumps({
            "name": "Test name",
            "url": "http://my.plugin.url:9999",
        })
        with (
            patch("builtins.open", mock_open(read_data=json)) as _open,
            patch("designer_plugin.designer_plugin.Zeroconf") as _zeroconf
        ):

            with DesignerPlugin.default_init(9999) as plugin:
                _zeroconf().register_service.assert_called_once()
                service_info = _zeroconf(
                ).register_service.mock_calls[0].args[0]
                self.assertEqual(service_info.name, f"{_escaped(plugin.name)}._d3plugin._tcp.local.")
                self.assertEqual(service_info.type, "_d3plugin._tcp.local.")
                self.assertEqual(service_info.port, 9999)
                self.assertEqual(service_info.server, f"{plugin.hostname}.local.")
                self.assertEqual(service_info.properties[b"u"], b"http://my.plugin.url:9999")
                self.assertEqual(service_info.properties[b"t"], b"web")
                self.assertEqual(service_info.properties[b"s"], b"false")

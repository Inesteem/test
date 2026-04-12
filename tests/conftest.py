"""pytest bootstrap: stub out Linux/USB-only modules on platforms that lack them.

Without this, test_buzzer.py and test_klopfklopf.py fail at collection time
with ModuleNotFoundError for `evdev` (Linux-only) or `usb.core` (needs libusb
+ pyusb). The tests mock these modules heavily anyway, so stubbing them here
just lets the module imports succeed.
"""

import sys
import types


def _stub_evdev():
    """Provide a minimal evdev stub so buzzers.buzzer can import it."""
    if "evdev" in sys.modules:
        return

    ecodes = types.ModuleType("evdev.ecodes")
    ecodes.EV_KEY = 1
    ecodes.KEY_K = 37

    evdev = types.ModuleType("evdev")
    evdev.ecodes = ecodes
    evdev.list_devices = lambda: []
    evdev.InputDevice = type("InputDevice", (), {})

    sys.modules["evdev"] = evdev
    sys.modules["evdev.ecodes"] = ecodes


def _stub_usb():
    """Provide a minimal usb.core / usb.util stub for LED controller imports."""
    if "usb" in sys.modules and "usb.core" in sys.modules:
        return

    class _FakeUSBError(Exception):
        pass

    usb_core = types.ModuleType("usb.core")
    usb_core.find = lambda **kw: None
    usb_core.USBError = _FakeUSBError

    usb_util = types.ModuleType("usb.util")
    usb_util.claim_interface = lambda dev, i: None
    usb_util.dispose_resources = lambda dev: None

    usb = types.ModuleType("usb")
    usb.core = usb_core
    usb.util = usb_util

    sys.modules["usb"] = usb
    sys.modules["usb.core"] = usb_core
    sys.modules["usb.util"] = usb_util


try:
    import evdev as _evdev_probe  # type: ignore  # noqa: F401
except ImportError:
    _stub_evdev()

try:
    import usb.core as _usb_probe  # type: ignore  # noqa: F401
except ImportError:
    _stub_usb()

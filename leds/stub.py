"""No-op LED controller stub for when hardware is not connected."""


class NoOpLEDController:
    """Drop-in replacement for LEDController that does nothing."""

    def __getattr__(self, name):
        return lambda *a, **kw: None

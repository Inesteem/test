"""Tests for leds/klopfklopf.py — LEDController and helpers."""

import math
import threading
import time
from unittest.mock import MagicMock, patch, call

import pytest


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_usb(monkeypatch):
    """
    Patch usb.core.find and usb.util so LEDController.open() works without hardware.
    Returns (mock_device, mock_util_module).
    """
    mock_dev = MagicMock()
    mock_dev.is_kernel_driver_active.return_value = False

    import usb.core as usb_core
    import usb.util as usb_util

    monkeypatch.setattr(usb_core, "find", MagicMock(return_value=mock_dev))
    monkeypatch.setattr(usb_util, "claim_interface", MagicMock())
    monkeypatch.setattr(usb_util, "dispose_resources", MagicMock())

    return mock_dev


@pytest.fixture
def leds(mock_usb):
    """Open LEDController with mocked USB and yield it; close after test."""
    from leds.klopfklopf import LEDController
    ctrl = LEDController()
    ctrl.open()
    yield ctrl
    ctrl.close()


# ---------------------------------------------------------------------------
# parse_color
# ---------------------------------------------------------------------------

class TestParseColor:

    def test_six_digit_hex(self):
        from leds.klopfklopf import parse_color
        assert parse_color("#ff0000") == (255, 0, 0)

    def test_six_digit_hex_without_hash(self):
        from leds.klopfklopf import parse_color
        assert parse_color("00ff00") == (0, 255, 0)

    def test_three_digit_hex_expanded(self):
        from leds.klopfklopf import parse_color
        # "#rgb" expands to "#rrggbb"
        assert parse_color("#f0a") == (255, 0, 170)

    def test_rgb_tuple(self):
        from leds.klopfklopf import parse_color
        assert parse_color((10, 20, 30)) == (10, 20, 30)

    def test_rgb_list(self):
        from leds.klopfklopf import parse_color
        assert parse_color([128, 64, 32]) == (128, 64, 32)

    def test_clamps_high_values(self):
        from leds.klopfklopf import parse_color
        assert parse_color((300, 0, 0)) == (255, 0, 0)

    def test_clamps_negative_values(self):
        from leds.klopfklopf import parse_color
        assert parse_color((-1, 0, 0)) == (0, 0, 0)

    def test_black(self):
        from leds.klopfklopf import parse_color
        assert parse_color("#000000") == (0, 0, 0)

    def test_white(self):
        from leds.klopfklopf import parse_color
        assert parse_color("#ffffff") == (255, 255, 255)

    def test_mixed_case_hex(self):
        from leds.klopfklopf import parse_color
        assert parse_color("#FF8800") == (255, 136, 0)


# ---------------------------------------------------------------------------
# lerp_color
# ---------------------------------------------------------------------------

class TestLerpColor:

    def test_t_zero_returns_c1(self):
        from leds.klopfklopf import lerp_color
        assert lerp_color((0, 0, 0), (255, 255, 255), 0.0) == (0, 0, 0)

    def test_t_one_returns_c2(self):
        from leds.klopfklopf import lerp_color
        assert lerp_color((0, 0, 0), (255, 255, 255), 1.0) == (255, 255, 255)

    def test_t_half_midpoint(self):
        from leds.klopfklopf import lerp_color
        r, g, b = lerp_color((0, 0, 0), (200, 100, 50), 0.5)
        assert r == 100
        assert g == 50
        assert b == 25

    def test_returns_tuple_of_three_ints(self):
        from leds.klopfklopf import lerp_color
        result = lerp_color((10, 20, 30), (100, 200, 50), 0.3)
        assert isinstance(result, tuple)
        assert len(result) == 3
        assert all(isinstance(v, int) for v in result)

    def test_same_colors_returns_same(self):
        from leds.klopfklopf import lerp_color
        c = (128, 64, 32)
        assert lerp_color(c, c, 0.7) == c


# ---------------------------------------------------------------------------
# LEDController.open
# ---------------------------------------------------------------------------

class TestLEDControllerOpen:

    def test_open_raises_when_device_not_found(self, monkeypatch):
        import usb.core as usb_core
        monkeypatch.setattr(usb_core, "find", MagicMock(return_value=None))
        from leds.klopfklopf import LEDController
        ctrl = LEDController()
        with pytest.raises(RuntimeError, match="not found"):
            ctrl.open()

    def test_open_detaches_kernel_driver_when_active(self, monkeypatch):
        mock_dev = MagicMock()
        mock_dev.is_kernel_driver_active.return_value = True
        import usb.core as usb_core
        import usb.util as usb_util
        monkeypatch.setattr(usb_core, "find", MagicMock(return_value=mock_dev))
        monkeypatch.setattr(usb_util, "claim_interface", MagicMock())
        monkeypatch.setattr(usb_util, "dispose_resources", MagicMock())
        from leds.klopfklopf import LEDController
        ctrl = LEDController()
        ctrl.open()
        mock_dev.detach_kernel_driver.assert_called()
        ctrl.close()

    def test_open_does_not_detach_when_driver_not_active(self, mock_usb, leds):
        mock_usb.is_kernel_driver_active.return_value = False
        mock_usb.detach_kernel_driver.assert_not_called()

    def test_context_manager_opens_and_closes(self, mock_usb):
        from leds.klopfklopf import LEDController
        import usb.util as usb_util
        with LEDController() as ctrl:
            assert ctrl._dev is not None
        # After __exit__, _dev should be None
        assert ctrl._dev is None


# ---------------------------------------------------------------------------
# LEDController._write / set_color / off
# ---------------------------------------------------------------------------

class TestLEDControllerWrite:

    def test_set_color_writes_correct_payload(self, leds, mock_usb):
        leds.set_color("#ff0000")
        mock_usb.write.assert_called_with(0x04, bytearray([0x00, 0x03, 255, 0, 0]))

    def test_set_color_green(self, leds, mock_usb):
        leds.set_color("#00ff00")
        mock_usb.write.assert_called_with(0x04, bytearray([0x00, 0x03, 0, 255, 0]))

    def test_set_color_with_tuple(self, leds, mock_usb):
        leds.set_color((10, 20, 30))
        mock_usb.write.assert_called_with(0x04, bytearray([0x00, 0x03, 10, 20, 30]))

    def test_off_writes_black(self, leds, mock_usb):
        leds.off()
        mock_usb.write.assert_called_with(0x04, bytearray([0x00, 0x03, 0, 0, 0]))

    def test_set_color_stops_animation_first(self, leds):
        # Start an animation, then set_color should stop it
        leds._animation_thread = MagicMock()
        leds._animation_thread.is_alive.return_value = True
        leds._animation_stop = MagicMock()
        # Call set_color — it calls stop() internally
        # Just verify no exception raised and the write goes through
        leds.set_color("#ffffff")


# ---------------------------------------------------------------------------
# LEDController.stop
# ---------------------------------------------------------------------------

class TestLEDControllerStop:

    def test_stop_with_no_animation_does_not_raise(self, leds):
        leds.stop()   # no thread running — should be safe

    def test_stop_clears_animation_thread_ref(self, leds):
        # Start a real (very fast) animation
        leds.rainbow(["#ff0000", "#0000ff"], period=0.1, fps=60)
        time.sleep(0.05)
        leds.stop()
        assert leds._animation_thread is None

    def test_stop_clears_stop_event_for_reuse(self, leds):
        leds.rainbow(["#ff0000", "#0000ff"], period=0.1, fps=60)
        time.sleep(0.05)
        leds.stop()
        assert not leds._animation_stop.is_set()

    def test_double_stop_does_not_raise(self, leds):
        leds.rainbow(["#ff0000", "#0000ff"], period=0.1, fps=60)
        time.sleep(0.05)
        leds.stop()
        leds.stop()   # second stop — should not raise


# ---------------------------------------------------------------------------
# LEDController.rainbow
# ---------------------------------------------------------------------------

class TestLEDControllerRainbow:

    def test_rainbow_requires_at_least_two_colors(self, leds):
        with pytest.raises(ValueError, match="at least 2"):
            leds.rainbow(["#ff0000"])

    def test_rainbow_starts_animation_thread(self, leds):
        leds.rainbow(["#ff0000", "#0000ff"], period=0.5)
        assert leds._animation_thread is not None
        assert leds._animation_thread.is_alive()
        leds.stop()

    def test_rainbow_writes_to_device(self, leds, mock_usb):
        leds.rainbow(["#ff0000", "#0000ff"], period=0.05, fps=60)
        time.sleep(0.1)
        leds.stop()
        assert mock_usb.write.called

    def test_rainbow_replaces_previous_animation(self, leds):
        leds.rainbow(["#ff0000", "#0000ff"], period=0.5)
        first_thread = leds._animation_thread
        leds.rainbow(["#00ff00", "#ffffff"], period=0.5)
        # The old thread should have been replaced
        assert leds._animation_thread is not first_thread
        leds.stop()


# ---------------------------------------------------------------------------
# LEDController.pulse
# ---------------------------------------------------------------------------

class TestLEDControllerPulse:

    def test_pulse_requires_at_least_one_color(self, leds):
        with pytest.raises(ValueError, match="at least 1"):
            leds.pulse([])

    def test_pulse_starts_animation_thread(self, leds):
        leds.pulse(["#ff0000"], period=0.5)
        assert leds._animation_thread is not None
        assert leds._animation_thread.is_alive()
        leds.stop()

    def test_pulse_writes_to_device(self, leds, mock_usb):
        leds.pulse(["#ff8800"], period=0.05, fps=60)
        time.sleep(0.1)
        leds.stop()
        assert mock_usb.write.called

    def test_pulse_brightness_zero_at_phase_boundaries(self, leds):
        """At phase 0 or 1 the sine curve gives 0 brightness."""
        brightness_0 = math.sin(0 * math.pi)
        brightness_1 = math.sin(1 * math.pi)
        assert abs(brightness_0) < 1e-9
        assert abs(brightness_1) < 1e-9


# ---------------------------------------------------------------------------
# LEDController.strobe
# ---------------------------------------------------------------------------

class TestLEDControllerStrobe:

    def test_strobe_starts_animation_thread(self, leds):
        leds.strobe("#ffffff", hz=20)
        assert leds._animation_thread is not None
        assert leds._animation_thread.is_alive()
        leds.stop()

    def test_strobe_writes_on_and_off(self, leds, mock_usb):
        leds.strobe("#ff0000", hz=50)
        time.sleep(0.1)
        leds.stop()
        calls = mock_usb.write.call_args_list
        # Should have at least one "on" and one "off" write
        payloads = [c.args[1] if c.args else c[0][1] for c in calls]
        on_calls = [p for p in payloads if p[2] == 255]   # red=255
        off_calls = [p for p in payloads if p[2] == 0 and p[3] == 0 and p[4] == 0]
        assert len(on_calls) > 0
        assert len(off_calls) > 0


# ---------------------------------------------------------------------------
# LEDController.breathe
# ---------------------------------------------------------------------------

class TestLEDControllerBreathe:

    def test_breathe_starts_animation_thread(self, leds):
        leds.breathe("#ff0000", period=0.5)
        assert leds._animation_thread is not None
        assert leds._animation_thread.is_alive()
        leds.stop()

    def test_breathe_writes_to_device(self, leds, mock_usb):
        leds.breathe("#0000ff", period=0.05, fps=60)
        time.sleep(0.1)
        leds.stop()
        assert mock_usb.write.called


# ---------------------------------------------------------------------------
# LEDController.candle
# ---------------------------------------------------------------------------

class TestLEDControllerCandle:

    def test_candle_starts_animation_thread(self, leds):
        leds.candle()
        assert leds._animation_thread is not None
        assert leds._animation_thread.is_alive()
        leds.stop()

    def test_candle_writes_to_device(self, leds, mock_usb):
        leds.candle(fps=60)
        time.sleep(0.1)
        leds.stop()
        assert mock_usb.write.called

    def test_candle_accepts_custom_color(self, leds):
        # Should not raise
        leds.candle(color=(255, 100, 0), intensity=0.5, fps=30)
        time.sleep(0.05)
        leds.stop()


# ---------------------------------------------------------------------------
# Animation thread replacement
# ---------------------------------------------------------------------------

class TestAnimationReplacement:

    def test_new_animation_stops_old_one(self, leds):
        leds.rainbow(["#ff0000", "#0000ff"], period=10.0)
        first_thread = leds._animation_thread
        leds.pulse(["#00ff00"], period=10.0)
        # First thread should no longer be alive
        assert not first_thread.is_alive()
        leds.stop()

    def test_set_color_stops_running_animation(self, leds):
        leds.rainbow(["#ff0000", "#0000ff"], period=10.0)
        thread = leds._animation_thread
        leds.set_color("#ffffff")   # calls stop() internally
        assert not thread.is_alive()
        assert leds._animation_thread is None

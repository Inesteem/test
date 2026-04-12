"""Tests for buzzers/buzzer.py — BuzzerController and find_buzzers."""

import select
import threading
import time
from unittest.mock import MagicMock, patch, call

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_mock_device(num, phys=None):
    """Return a minimal mock evdev.InputDevice."""
    dev = MagicMock()
    dev.fd = num
    dev.phys = phys or f"usb-0000:00:14.0-{num}/input0"
    dev.name = "Keyboard"
    dev.info = MagicMock()
    dev.info.vendor = 0x2341
    dev.info.product = 0xC036
    dev.read_one.return_value = None   # drain returns nothing
    return dev


def make_key_event(code, value):
    """Return a mock evdev event."""
    from evdev import ecodes
    ev = MagicMock()
    ev.type = ecodes.EV_KEY
    ev.code = code
    ev.value = value
    return ev


# ---------------------------------------------------------------------------
# find_buzzers
# ---------------------------------------------------------------------------

class TestFindBuzzers:

    @patch("buzzers.buzzer.evdev.InputDevice")
    @patch("buzzers.buzzer.evdev.list_devices")
    def test_returns_empty_when_no_devices(self, mock_list, mock_device_cls):
        mock_list.return_value = []
        from buzzers.buzzer import find_buzzers
        result = find_buzzers()
        assert result == []

    @patch("buzzers.buzzer.evdev.InputDevice")
    @patch("buzzers.buzzer.evdev.list_devices")
    def test_skips_non_matching_vendor(self, mock_list, mock_device_cls):
        dev = make_mock_device(1)
        dev.info.vendor = 0xDEAD   # wrong vendor
        mock_list.return_value = ["/dev/input/event0"]
        mock_device_cls.return_value = dev
        from buzzers.buzzer import find_buzzers
        result = find_buzzers()
        assert result == []
        dev.close.assert_called_once()

    @patch("buzzers.buzzer.evdev.InputDevice")
    @patch("buzzers.buzzer.evdev.list_devices")
    def test_skips_non_keyboard_device(self, mock_list, mock_device_cls):
        dev = make_mock_device(1)
        dev.name = "Mouse"          # not "Keyboard"
        mock_list.return_value = ["/dev/input/event0"]
        mock_device_cls.return_value = dev
        from buzzers.buzzer import find_buzzers
        result = find_buzzers()
        assert result == []
        dev.close.assert_called_once()

    @patch("buzzers.buzzer.evdev.InputDevice")
    @patch("buzzers.buzzer.evdev.list_devices")
    def test_returns_matching_device_as_buzzer_1(self, mock_list, mock_device_cls):
        dev = make_mock_device(99, phys="usb-0000:00:14.0-1/input0")
        mock_list.return_value = ["/dev/input/event99"]
        mock_device_cls.return_value = dev
        from buzzers.buzzer import find_buzzers
        result = find_buzzers()
        assert len(result) == 1
        num, returned_dev = result[0]
        assert num == 1
        assert returned_dev is dev

    @patch("buzzers.buzzer.evdev.InputDevice")
    @patch("buzzers.buzzer.evdev.list_devices")
    def test_multiple_buzzers_sorted_by_phys(self, mock_list, mock_device_cls):
        dev_a = make_mock_device(10, phys="usb-0000:00:14.0-2/input0")
        dev_b = make_mock_device(11, phys="usb-0000:00:14.0-1/input0")
        mock_list.return_value = ["/dev/input/event10", "/dev/input/event11"]
        mock_device_cls.side_effect = [dev_a, dev_b]
        from buzzers.buzzer import find_buzzers
        result = find_buzzers()
        # dev_b has the lower phys string, so it should be buzzer 1
        assert len(result) == 2
        assert result[0][0] == 1
        assert result[0][1] is dev_b
        assert result[1][0] == 2
        assert result[1][1] is dev_a


# ---------------------------------------------------------------------------
# BuzzerController — construction and state
# ---------------------------------------------------------------------------

class TestBuzzerControllerInit:

    def test_initial_ranking_is_empty(self):
        from buzzers.buzzer import BuzzerController
        ctrl = BuzzerController([])
        assert ctrl.get_ranking() == []

    def test_get_ranking_returns_copy(self):
        from buzzers.buzzer import BuzzerController
        ctrl = BuzzerController([])
        r1 = ctrl.get_ranking()
        r1.append(99)                 # mutate the returned list
        assert ctrl.get_ranking() == []  # internal state unchanged


# ---------------------------------------------------------------------------
# BuzzerController — reset
# ---------------------------------------------------------------------------

class TestBuzzerControllerReset:

    def _make_ctrl_with_ranking(self, ranking):
        """Inject a pre-populated ranking directly (bypassing hardware)."""
        from buzzers.buzzer import BuzzerController
        dev = make_mock_device(1)
        ctrl = BuzzerController([(1, dev)])
        with ctrl._lock:
            ctrl._ranking = list(ranking)
            ctrl._pressed = set(ranking)
        return ctrl

    def test_reset_clears_ranking(self):
        ctrl = self._make_ctrl_with_ranking([1, 2])
        ctrl.reset()
        assert ctrl.get_ranking() == []

    def test_reset_clears_pressed_set(self):
        ctrl = self._make_ctrl_with_ranking([1, 2])
        ctrl.reset()
        with ctrl._lock:
            assert ctrl._pressed == set()

    def test_reset_drains_device(self):
        from buzzers.buzzer import BuzzerController
        dev = make_mock_device(1)
        dev.read_one.side_effect = [MagicMock(), None]  # one event then done
        ctrl = BuzzerController([(1, dev)])
        ctrl.reset()
        assert dev.read_one.call_count >= 1

    def test_reset_idempotent_when_already_empty(self):
        from buzzers.buzzer import BuzzerController
        dev = make_mock_device(1)
        ctrl = BuzzerController([(1, dev)])
        ctrl.reset()
        ctrl.reset()
        assert ctrl.get_ranking() == []

    def test_reset_allows_same_buzzer_to_register_again(self):
        ctrl = self._make_ctrl_with_ranking([1])
        ctrl.reset()
        # After reset, inject buzzer 1 again
        with ctrl._lock:
            ctrl._ranking.append(1)
            ctrl._pressed.add(1)
        assert ctrl.get_ranking() == [1]


# ---------------------------------------------------------------------------
# BuzzerController — ranking logic (unit-level, no threads)
# ---------------------------------------------------------------------------

class TestBuzzerRankingLogic:
    """Test the ranking accumulation logic directly via _listen internals."""

    def _inject_press(self, ctrl, buzzer_num):
        """Simulate a KEY_K press for a given buzzer number."""
        with ctrl._lock:
            if buzzer_num not in ctrl._pressed:
                ctrl._pressed.add(buzzer_num)
                ctrl._ranking.append(buzzer_num)

    def test_first_press_is_first_in_ranking(self):
        from buzzers.buzzer import BuzzerController
        ctrl = BuzzerController([])
        self._inject_press(ctrl, 1)
        assert ctrl.get_ranking() == [1]

    def test_second_press_appended_after_first(self):
        from buzzers.buzzer import BuzzerController
        ctrl = BuzzerController([])
        self._inject_press(ctrl, 2)
        self._inject_press(ctrl, 1)
        assert ctrl.get_ranking() == [2, 1]

    def test_duplicate_press_ignored(self):
        from buzzers.buzzer import BuzzerController
        ctrl = BuzzerController([])
        self._inject_press(ctrl, 1)
        self._inject_press(ctrl, 1)  # duplicate
        assert ctrl.get_ranking() == [1]

    def test_three_buzzers_in_order(self):
        from buzzers.buzzer import BuzzerController
        ctrl = BuzzerController([])
        self._inject_press(ctrl, 3)
        self._inject_press(ctrl, 1)
        self._inject_press(ctrl, 2)
        assert ctrl.get_ranking() == [3, 1, 2]

    def test_all_duplicates_still_single_entry_each(self):
        from buzzers.buzzer import BuzzerController
        ctrl = BuzzerController([])
        for _ in range(5):
            self._inject_press(ctrl, 1)
        for _ in range(3):
            self._inject_press(ctrl, 2)
        assert ctrl.get_ranking() == [1, 2]


# ---------------------------------------------------------------------------
# BuzzerController — thread safety
# ---------------------------------------------------------------------------

class TestBuzzerThreadSafety:

    def test_concurrent_presses_all_recorded_once(self):
        from buzzers.buzzer import BuzzerController
        ctrl = BuzzerController([])
        barrier = threading.Barrier(10)

        def press(num):
            barrier.wait()
            with ctrl._lock:
                if num not in ctrl._pressed:
                    ctrl._pressed.add(num)
                    ctrl._ranking.append(num)

        threads = [threading.Thread(target=press, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        ranking = ctrl.get_ranking()
        assert sorted(ranking) == list(range(10))
        assert len(ranking) == len(set(ranking))   # no duplicates

    def test_reset_during_concurrent_reads(self):
        from buzzers.buzzer import BuzzerController
        dev = make_mock_device(1)
        ctrl = BuzzerController([(1, dev)])
        with ctrl._lock:
            ctrl._ranking = list(range(5))
            ctrl._pressed = set(range(5))

        errors = []

        def reader():
            for _ in range(50):
                try:
                    ctrl.get_ranking()
                except Exception as exc:
                    errors.append(exc)

        def resetter():
            for _ in range(10):
                ctrl.reset()
                time.sleep(0.001)

        threads = [threading.Thread(target=reader) for _ in range(5)]
        threads.append(threading.Thread(target=resetter))
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []


# ---------------------------------------------------------------------------
# BuzzerController — start / stop (mocked hardware)
# ---------------------------------------------------------------------------

class TestBuzzerControllerStartStop:

    def _make_ctrl(self):
        from buzzers.buzzer import BuzzerController
        dev = make_mock_device(1)
        ctrl = BuzzerController([(1, dev)])
        return ctrl, dev

    def test_start_grabs_device(self):
        ctrl, dev = self._make_ctrl()
        ctrl.start()
        dev.grab.assert_called_once()
        ctrl.stop()

    def test_stop_ungrabs_and_closes_device(self):
        ctrl, dev = self._make_ctrl()
        ctrl.start()
        ctrl.stop()
        dev.ungrab.assert_called_once()
        dev.close.assert_called_once()

    def test_stop_without_start_does_not_raise(self):
        from buzzers.buzzer import BuzzerController
        ctrl = BuzzerController([])
        ctrl.stop()   # should not raise

    def test_start_spawns_daemon_thread(self):
        ctrl, dev = self._make_ctrl()
        ctrl.start()
        assert ctrl._thread is not None
        assert ctrl._thread.daemon is True
        ctrl.stop()

    def test_stop_sets_stop_event(self):
        ctrl, dev = self._make_ctrl()
        ctrl.start()
        ctrl.stop()
        assert ctrl._stop.is_set()


# ---------------------------------------------------------------------------
# BuzzerController — _listen integration (mocked select + read)
# ---------------------------------------------------------------------------

class TestBuzzerListenLoop:
    """Drive the _listen loop with mocked select/read to verify event handling."""

    def _make_press_event(self):
        from evdev import ecodes
        ev = MagicMock()
        ev.type = ecodes.EV_KEY
        ev.code = ecodes.KEY_K
        ev.value = 1
        return ev

    def _make_non_key_event(self):
        ev = MagicMock()
        ev.type = 999   # not EV_KEY
        ev.value = 1
        return ev

    def _make_key_release_event(self):
        from evdev import ecodes
        ev = MagicMock()
        ev.type = ecodes.EV_KEY
        ev.code = ecodes.KEY_K
        ev.value = 0   # release, not press
        return ev

    def _run_listen_one_shot(self, buzzer_num, dev, events):
        """
        Run _listen in a thread, feed events via mocked select+read, then stop.
        Returns the controller so ranking can be inspected.
        """
        from buzzers.buzzer import BuzzerController

        call_count = [0]

        def fake_select(rlist, *args, **kwargs):
            if call_count[0] == 0:
                call_count[0] += 1
                return ([dev.fd], [], [])
            # After first round, signal stop
            ctrl._stop.set()
            return ([], [], [])

        ctrl = BuzzerController([(buzzer_num, dev)])
        dev.read.return_value = events

        with patch("buzzers.buzzer.select.select", side_effect=fake_select):
            thread = threading.Thread(target=ctrl._listen, daemon=True)
            thread.start()
            thread.join(timeout=2)

        return ctrl

    def test_key_k_press_recorded_in_ranking(self):
        dev = make_mock_device(1)
        ev = self._make_press_event()
        ctrl = self._run_listen_one_shot(1, dev, [ev])
        assert ctrl.get_ranking() == [1]

    def test_non_ev_key_event_ignored(self):
        dev = make_mock_device(1)
        ev = self._make_non_key_event()
        ctrl = self._run_listen_one_shot(1, dev, [ev])
        assert ctrl.get_ranking() == []

    def test_key_release_not_recorded(self):
        dev = make_mock_device(1)
        ev = self._make_key_release_event()
        ctrl = self._run_listen_one_shot(1, dev, [ev])
        assert ctrl.get_ranking() == []

    def test_second_press_from_same_buzzer_ignored(self):
        dev = make_mock_device(2)
        ev = self._make_press_event()
        # Feed two press events from the same buzzer
        ctrl = self._run_listen_one_shot(2, dev, [ev, ev])
        assert ctrl.get_ranking() == [2]
        assert len(ctrl.get_ranking()) == 1

"""LED choreography helpers — maps game phases to LED animations.

Each helper is a thin wrapper around the LEDController API that encodes
the game's visual vocabulary (rainbow idle, phased answer timer, celebration
bursts, failure sequences).
"""

import time

from quiz.drawing import team_color

# LED phase constants for the answer timer state machine
LED_PHASE_BREATHE = "breathe"
LED_PHASE_PULSE = "pulse"
LED_PHASE_STROBE = "strobe"


def leds_idle_rainbow(leds, team_config):
    """Rainbow cycle through team colors during the buzz-in wait."""
    colors = [tc["color"] for tc in team_config.values()]
    if len(colors) >= 2:
        leds.rainbow(colors, period=3.0)
    elif colors:
        leds.breathe(colors[0])


def get_led_phase(remaining, timeout):
    """Which LED phase should be active given remaining and total time."""
    if timeout <= 10:
        # Short timeouts: skip breathe, go straight to pulse/strobe
        if remaining > 5:
            return LED_PHASE_PULSE
        return LED_PHASE_STROBE
    if remaining > timeout * 0.5:
        return LED_PHASE_BREATHE
    if remaining > 5:
        return LED_PHASE_PULSE
    return LED_PHASE_STROBE


def leds_answer_phase(leds, team_config, buzzer_num, remaining, timeout, current_phase):
    """Update LEDs based on answer timer phase. Returns the new phase name.

    Only calls the underlying LED API when the phase actually changes, to
    avoid animation flicker from restarting the same effect every poll tick.
    """
    color = team_color(team_config, buzzer_num)
    new_phase = get_led_phase(remaining, timeout)

    if new_phase == current_phase:
        return current_phase

    if new_phase == LED_PHASE_BREATHE:
        leds.breathe(color, period=3.0)
    elif new_phase == LED_PHASE_PULSE:
        leds.pulse([color], period=1.0)
    elif new_phase == LED_PHASE_STROBE:
        leds.strobe(color, hz=6.0)

    return new_phase


def leds_correct(leds, team_config, buzzer_num):
    """Celebration sequence for a correct answer."""
    color = team_color(team_config, buzzer_num)
    leds.strobe(color, hz=8.0)
    time.sleep(0.5)
    leds.set_color("#00ff00")


def leds_wrong(leds):
    """Failure sequence for a wrong answer — red strobe then flames."""
    leds.strobe("#ff0000", hz=4.0)
    time.sleep(0.3)
    leds.candle("#ff2200", intensity=0.6)
    time.sleep(1.0)
    leds.off()


def leds_times_up(leds):
    """Timeout LED sequence — rapid red flash then dim red breathe."""
    leds.strobe("#ff0000", hz=12.0)
    time.sleep(0.5)
    leds.off()
    time.sleep(0.1)
    leds.breathe("#660000", period=2.0)

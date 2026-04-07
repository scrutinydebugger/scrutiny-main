#    throttler.py
#        Allow to do some throttling to reduce the transmission speed
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2022 Scrutiny Debugger

__all__ = ['Throttler']

import time
from scrutiny.tools.typing import *


class Throttler:
    """Class that allows us to do throttling on a given communication channel.

    It measures the throughput rate and tells us if we should wait or go ahead when we
    need to send data.

    It works with two low pass filters, one fast to get an instantaneous measurement of the rate.
    One slow to get a long-term (relatively speaking) measurement of the rate. We allow data
    transfer only when both of these filters are below the target.

    :param mean_rate: Target mean rate (default 0).
    :param estimation_window: Filters updated at this rate (default 0.1).
    """

    __slots__ = (
        "enabled",
        "mean_rate",
        "estimation_window_ns",
        "slow_tau",
        "fast_tau",
        "last_process_timestamp_ns",
        "estimated_rate_slow",
        "estimated_rate_fast",
        "consumed_since_last_estimation",
    )

    enabled: bool
    """Whether the throttler is enabled."""
    mean_rate: float
    """Target mean rate."""
    estimation_window_ns: int
    """Filters updated at this rate."""
    slow_tau: float
    """Time constant of first IIR filter (slow one)."""
    fast_tau: float
    """Time constant of second IIR filter (fast one)."""
    last_process_timestamp_ns: int
    """Timestamp of last process call."""
    estimated_rate_slow: float
    """Estimated rate using slow filter."""
    estimated_rate_fast: float
    """Estimated rate using fast filter."""
    consumed_since_last_estimation: int
    """Amount consumed since last estimation."""

    def __init__(self, mean_rate: float, estimation_window: float = 0.1, slow_tau: float = 1.0, fast_tau: float = 0.05) -> None:
        self.enabled = False
        self.mean_rate = float(mean_rate)
        self.estimation_window_ns = int(round(estimation_window * 1e9))
        # 1 sec time constant, but we can't be smaller than the window  (otherwise unstable)
        self.slow_tau = max(slow_tau, fast_tau)
        # 0.05 sec time constant, but we can't be smaller than the window (otherwise unstable)
        self.fast_tau = fast_tau
        self.reset()

    def set_rate(self, mean_rate: float) -> None:
        """ Sets the target mean rate to respect"""
        self.mean_rate = float(mean_rate)

    def enable(self) -> None:
        """ Enable the throttler. Will allow everything when disabled"""
        self.enabled = True
        self.reset()
        self.mean_rate = float(self.mean_rate)

    def disable(self) -> None:
        """ Disable the throttler"""
        self.enabled = False

    def is_enabled(self) -> bool:
        """Returns True if the Throttler is enabled"""
        return self.enabled

    def get_rate(self) -> float:
        """Return the target average rate"""
        return self.mean_rate

    def reset(self) -> None:
        """ Sets the throttler to its initial state"""
        self.last_process_timestamp_ns = time.perf_counter_ns()
        self.estimated_rate_slow = 0
        self.estimated_rate_fast = 0
        self.consumed_since_last_estimation = 0

    def force_estimated_rate(self, rate: float) -> None:
        self.estimated_rate_fast = rate
        self.estimated_rate_slow = rate

    def process(self) -> None:
        """To be called periodically as fast as possible."""
        if not self.enabled:
            self.reset()
            return

        t = time.perf_counter_ns()
        dt = t - self.last_process_timestamp_ns
        if dt > self.estimation_window_ns:
            dt_sec_float = (float(dt) * 1e-9)
            # We need to update the filters, e.g. our estimation of the rate
            # The time delta (dT) is variable because of thread resolution. We need to recompute the
            # filters weights every time
            instant_rate = float(self.consumed_since_last_estimation) / dt_sec_float  # Filters inputs

            # Fast filter
            b = min(1, dt_sec_float / self.fast_tau)
            a = 1 - b
            self.estimated_rate_fast = b * instant_rate + a * self.estimated_rate_fast

            # Slow filter
            b = min(1, dt_sec_float / self.slow_tau)
            a = 1 - b
            self.estimated_rate_slow = b * instant_rate + a * self.estimated_rate_slow

            # Reset instant measurement
            self.consumed_since_last_estimation = 0     # Reset the data counter
            self.last_process_timestamp_ns = t          # Sets new timestamp

    def get_estimated_rate(self) -> float:
        """ Estimated rate is the long average. Fast average is only to avoid peak at startup."""
        return self.estimated_rate_slow

    def allowed(self, amount: int) -> bool:
        """ Tells if this chunk of data can be sent right now or we should wait"""
        if not self.enabled:
            return True

        allowed = True
        approx_rate = max(self.estimated_rate_slow, self.estimated_rate_fast)

        # rate + amount compared with rate. Units don't match, this is not a mistake.
        if approx_rate + self.consumed_since_last_estimation > self.mean_rate:
            allowed = False

        return allowed

    def consume(self, amount: int) -> None:
        """ Indicates to the throttler that data has been sent"""
        if self.enabled:
            self.consumed_since_last_estimation += amount

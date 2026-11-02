"""Heartbeat thread lifecycle, loss and stop are independent of model duration."""

from threading import Event
from types import SimpleNamespace

import pytest

from rag_platform.embeddings.heartbeat import LeasePulse
from rag_platform.ingestion.claims import ClaimExpired
from rag_platform.ingestion.worker_policy import StopRequested


def test_pulse_refreshes_while_inference_waits_and_joins_on_exit():
    refreshed = Event()
    calls = []

    def heartbeat(_):
        calls.append(True)
        if len(calls) > 1:
            refreshed.set()
        return True

    queue = SimpleNamespace(lease_seconds=1, heartbeat=heartbeat)
    with LeasePulse(queue, object(), lambda: False, interval=0.01) as pulse:
        assert refreshed.wait(1)
        pulse.check()
    assert len(calls) >= 2 and not pulse.thread.is_alive()


@pytest.mark.parametrize("failure", ["false", "exception"])
def test_lost_heartbeat_cancels_commit_without_exposing_error(failure):
    refreshed = Event()
    calls = []

    def heartbeat(_):
        calls.append(True)
        if len(calls) == 1:
            return True
        refreshed.set()
        if failure == "exception":
            raise RuntimeError("PRIVATE_PROVIDER_ERROR")
        return False

    queue = SimpleNamespace(lease_seconds=1, heartbeat=heartbeat)
    with pytest.raises(ClaimExpired, match="CLAIM_EXPIRED"):
        with LeasePulse(queue, object(), lambda: False, interval=0.01) as pulse:
            assert refreshed.wait(1)
            assert pulse.lost.wait(1)
    assert not pulse.thread.is_alive()


def test_stop_after_inference_blocks_commit_and_stops_thread():
    stop = Event()
    queue = SimpleNamespace(lease_seconds=1, heartbeat=lambda _: True)
    with pytest.raises(StopRequested):
        with LeasePulse(queue, object(), stop.is_set, interval=0.01) as pulse:
            stop.set()
    assert not pulse.thread.is_alive()


@pytest.mark.parametrize("interval", [True, 0, -1, 1, float("nan"), float("inf"), "private"])
def test_invalid_heartbeat_interval_refused(interval):
    with pytest.raises(ValueError, match="Invalid lease heartbeat"):
        LeasePulse(SimpleNamespace(lease_seconds=1), None, lambda: False, interval=interval)

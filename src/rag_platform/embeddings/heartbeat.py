"""Keep only the control lease alive during inference; hold no tenant transaction."""

from threading import Event, Thread

from rag_platform.ingestion.claims import ClaimExpired
from rag_platform.ingestion.worker_policy import StopRequested


class LeasePulse:
    def __init__(self, queue, claim, stopped, *, interval=None):
        self.queue, self.claim, self.stopped = queue, claim, stopped
        self.interval = min(30.0, queue.lease_seconds / 3) if interval is None else interval
        if (
            type(self.interval) not in (int, float)
            or not 0 < self.interval <= queue.lease_seconds / 3
        ):
            raise ValueError("Invalid lease heartbeat interval")
        self.finished, self.lost = Event(), Event()
        self.thread = None

    def _run(self):
        while not self.finished.wait(self.interval):
            try:
                if self.stopped() or not self.queue.heartbeat(self.claim):
                    self.lost.set()
                    return
            except Exception:
                self.lost.set()
                return

    def check(self):
        if self.stopped():
            raise StopRequested()
        if self.lost.is_set():
            raise ClaimExpired()

    def __enter__(self):
        self.check()
        if not self.queue.heartbeat(self.claim):
            raise ClaimExpired()
        self.thread = Thread(target=self._run, name="embedding-lease", daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.finished.set()
        self.thread.join(timeout=15)
        if self.thread.is_alive():
            self.lost.set()
        self.check()

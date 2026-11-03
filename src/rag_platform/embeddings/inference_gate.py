"""One model/tokenizer operation per process; index waits retain their lease heartbeat."""

import time
from contextlib import contextmanager
from threading import Condition

from rag_platform.embeddings.contracts import EmbeddingError


class InferenceGate:
    def __init__(self, ready, *, query_wait=2):
        if type(query_wait) not in (int, float) or not 0 < query_wait <= 2:
            raise ValueError("Bounded query wait required")
        self.ready, self.query_wait = ready, query_wait
        self.condition, self.held, self.pending_index, self.closed = Condition(), False, 0, False

    @contextmanager
    def enter(self, *, index=False):
        deadline = None if index else time.monotonic() + self.query_wait
        with self.condition:
            if index:
                self.pending_index += 1
            try:
                while True:
                    if self.closed or not self.ready():
                        raise EmbeddingError("DEPENDENCY_UNAVAILABLE")
                    if not self.held and (index or self.pending_index == 0):
                        self.held = True
                        break
                    if deadline is not None and time.monotonic() >= deadline:
                        raise EmbeddingError("LIMIT_EXCEEDED")
                    remaining = (
                        0.2
                        if deadline is None
                        else min(0.2, max(0.001, deadline - time.monotonic()))
                    )
                    self.condition.wait(remaining)
            finally:
                if index:
                    self.pending_index -= 1
                    self.condition.notify_all()
        try:
            yield
        finally:
            with self.condition:
                self.held = False
                self.condition.notify_all()

    def close(self):
        with self.condition:
            self.closed = True
            self.condition.notify_all()


class GatedProvider:
    def __init__(self, provider, gate, *, index):
        self.base, self.gate, self.index, self.profile = provider, gate, index, provider.profile

    def count_tokens(self, text, kind):
        with self.gate.enter(index=self.index):
            return self.base.count_tokens(text, kind)

    def embed(self, texts, kind):
        with self.gate.enter(index=self.index):
            return self.base.embed(texts, kind)

    def __repr__(self):
        return "GatedProvider(<private inputs>)"

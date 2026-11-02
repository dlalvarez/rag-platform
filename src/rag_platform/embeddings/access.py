"""Fail closed before the worker's private handoff expires; never renew a bearer."""

import time

from rag_platform.providers.application_handoff import NAME, FileApplicationStore, read_record
from rag_platform.providers.secrets import SecretErrorCode, SecretStoreError

MARGIN_SECONDS = 180


class ExpiringStore(FileApplicationStore):
    def __init__(self, *args, **kwargs):
        self._denied = False
        super().__init__(*args, **kwargs)

    def ready(self):
        if self._closed or self._denied:
            return False
        try:
            return read_record(self.path / NAME)["expires_at"] - time.time() > MARGIN_SECONDS
        except Exception:
            return False

    def read(self, ref):
        try:
            return super().read(ref)
        except SecretStoreError as error:
            if error.code in {SecretErrorCode.DENIED, SecretErrorCode.INVALID}:
                self._denied = True
            raise

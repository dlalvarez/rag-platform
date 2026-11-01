"""Authenticated cursors bound to actor, tenant and collection; no physical references."""

import base64
import hmac
import json
from uuid import UUID

from rag_platform.documents.errors import DocumentError


class Pagination:
    def __init__(self, key):
        if not isinstance(key, bytes) or len(key) != 32:
            raise ValueError("Invalid pagination key")
        self._key = key

    def encode(self, context, collection, last):
        body = json.dumps(
            [str(context.principal_id), str(context.tenant_id), collection, str(last)],
            separators=(",", ":"),
        ).encode()
        mac = hmac.digest(self._key, b"F03/cursor/v1:" + body, "sha256")
        return base64.urlsafe_b64encode(body + mac).decode().rstrip("=")

    def decode(self, context, collection, cursor, limit):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise DocumentError("INPUT_INVALID")
        if cursor is None:
            return None
        try:
            if not isinstance(cursor, str) or not 1 <= len(cursor) <= 512:
                raise ValueError
            raw = base64.b64decode(cursor + "=" * (-len(cursor) % 4), altchars=b"-_", validate=True)
            if base64.urlsafe_b64encode(raw).decode().rstrip("=") != cursor:
                raise ValueError
            body, mac = raw[:-32], raw[-32:]
            expected = hmac.digest(self._key, b"F03/cursor/v1:" + body, "sha256")
            if not hmac.compare_digest(mac, expected):
                raise ValueError
            actor, tenant, purpose, last = json.loads(body)
            if (actor, tenant, purpose) != (
                str(context.principal_id),
                str(context.tenant_id),
                collection,
            ) or str(UUID(last)) != last:
                raise ValueError
            return UUID(last)
        except Exception:
            raise DocumentError("INPUT_INVALID") from None

    def page(self, context, collection, rows, limit, *, key, serialize):
        return {
            "items": [serialize(row) for row in rows[:limit]],
            "next_cursor": self.encode(context, collection, key(rows[limit - 1]))
            if len(rows) > limit
            else None,
        }

"""Closed document error vocabulary; never echo provider bodies or rejected input."""


class DocumentError(RuntimeError):
    STATUS = {
        "INPUT_INVALID": 422,
        "ROLE_DENIED": 403,
        "NOT_FOUND": 404,
        "STATE_CONFLICT": 409,
        "LAST_OWNER": 409,
        "TOO_LARGE": 413,
        "QUOTA_EXCEEDED": 429,
        "DEPENDENCY_UNAVAILABLE": 503,
    }

    def __init__(self, code="DEPENDENCY_UNAVAILABLE"):
        self.code = (
            code if isinstance(code, str) and code in self.STATUS else "DEPENDENCY_UNAVAILABLE"
        )
        self.status = self.STATUS[self.code]
        super().__init__(self.code)
